"""Read-only failed-prefix audit; does not run the strategy or claim full performance."""
from pathlib import Path
from collections import defaultdict
from bisect import bisect_left
import hashlib,json,math
import pandas as pd
import numpy as np
ROOT=Path('/Users/mac/.codex/worktrees/full-market-noai-one-lot/fian');L=ROOT/'research/lines/futures_trend_full_market_noai_one_lot';P=L/'outputs/run_20261020_risk025_no_weekly_v1';N=L/'outputs/run_20261019_contract_weekly_long_v1'
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def rd(p):return pd.read_csv(p,keep_default_na=False,float_precision='round_trip')
errors=[]
def ck(n,v,d=None):
 if not v:errors.append(dict(check=n,detail=d))
def near(x,y,tol=1e-6):return abs(float(x)-float(y))<tol
q=json.loads((P/'protocol.json').read_text());failure=json.loads((P/'failure_snapshot.json').read_text());s=failure['snapshot'];n=json.loads((N/'manifest.json').read_text());code=json.loads((P/'code_start_hashes.json').read_text())
ck('complete_manifest_absent',not (P/'manifest.json').exists());ck('failure_invalid',failure['financial_metrics_valid'] is False and failure['status']=='failed_before_complete')
ck('freeze_commit',q['source_commit']=='9feb5784d7757ee81cbab007a610a0d64da64ca6');ck('off_risk_policy',q['weekly_filter']=='disabled' and q['long_weekly_filter'] is False and q['weekly_policy'] is None and q['parameters']['stage068_risk_fraction']==.0025)
ck('no_external_operations',q['market_downloads']==0 and q['order_api_calls']==0 and q['production_qualified'] is False)
for f,d in code.items():ck('code_current:'+f,sha(f)==d);ck('code_snapshot:'+f,sha(P/'code_snapshot'/Path(f).name)==d)
for group in ['source_inputs','output_files']:
 for label,item in q['source_manifest'][group].items():ck('source_'+group+':'+label,sha(item['path'])==item['sha256'])
for f,d in q['lifecycle_sources'].items():ck('lifecycle_source:'+f,sha(f)==d)
for k in ['source_manifest','expiry_execution_overlay','quantity_execution_overlay','lifecycle_sources']:ck('frozen_baseline_'+k,q[k]==n[k])
ck('N_identity',sha(N/'manifest.json')=='859982f079da55aa1292154d5fc9b1004d1f0d5f23f75c4ec58ca892a102cb25')
for f in ['market_daily.csv','mapping.csv','contract_metadata.csv','lifecycle_deadlines.csv','trading_calendar.csv']:ck('N_table:'+f,sha(N/f)==n['hashes'][f])
tr=rd(P/'failed_prefix_trades.csv');tr['date']=tr.datetime.str[:10];tr['direction']=tr.direction.str.replace('Direction.','',regex=False).str.lower();tr['offset']=tr.offset.str.replace('Offset.','',regex=False).str.lower()
market=rd(N/'market_daily.csv');meta=rd(N/'contract_metadata.csv').set_index('vt_symbol');ix=market.set_index(['date','vt_symbol']);calendar=rd(N/'trading_calendar.csv').date.tolist();end=failure['date'][:10]
held=defaultdict(int);entry={};last={};balance=1e6;fees=slips=0.;max_vol=0;opening_capture=None;jr_receipt=None
for e in s['pending_open_events']:
 if e['vt_symbol']=='JR201907.CZCE' and e['event']=='preserve':jr_receipt=json.loads(e['receipt_json'])
ck('JR_original_receipt_found',jr_receipt is not None)
byday={d:g.to_dict('records') for d,g in tr.groupby('date',sort=False)};barsbyday={d:g.set_index('vt_symbol').to_dict('index') for d,g in market.groupby('date',sort=False)}
for day in [d for d in calendar if '2015-01-05'<=d<=end]:
 bars=barsbyday[day];start=dict(held);fills=byday.get(day,[]);opening=balance+sum(q*((float(bars[v]['open']) if v in bars and float(bars[v]['volume'])>0 else last[v])-last[v])*float(meta.loc[v,'size']) for v,q in held.items() if q);cost=0.;hp=sum(q*((float(bars[v]['close']) if v in bars else last[v])-last[v])*float(meta.loc[v,'size']) for v,q in start.items() if q);tp=0.
 ck('close_first', [x['offset'] for x in fills]==sorted([x['offset'] for x in fills],key=lambda z:0 if z=='close' else 1),day)
 for t in fills:
  v=t['vt_symbol'];z=meta.loc[v];qty=int(t['volume']);sign=1 if t['direction']=='long' else -1;bar=ix.loc[(day,v)]
  ck('prefix_integer_positive',qty>0 and qty==float(t['volume']),t['trade_id']);ck('prefix_full_daily_volume',float(bar.volume)>=qty,t['trade_id']);ck('prefix_exact_open_price',near(t['price'],bar.open),t['trade_id'])
  if t['offset']=='open':
   ck('prefix_no_add',held[v]==0 and v not in entry,t['trade_id']);ck('no_overlay_OPEN',str(bar.execution_only).lower()=='false',t['trade_id']);field='fee_open'
   if v=='JR201907.CZCE' and day=='2019-06-21':
    current=opening-cost;orig=jr_receipt['signal_equity']*.0025;budget=min(orig,current*.0025);risk=max(abs(t['price']-jr_receipt['stop_price'])*float(z['size']),float(z.pricetick)*float(z['size']),1.)*qty
    opening_capture=dict(trade_id=t['trade_id'],signal_snapshot=jr_receipt,opening_equity_net_prior_actual_costs=current,signal_budget=orig,opening_budget=budget,actual_total_stop_risk=risk,actual_volume=qty,actual_price=t['price'],budget_ok=risk<=budget+1e-8)
    ck('JR_actual_budget',opening_capture['budget_ok']);ck('JR_auth_qty',qty==jr_receipt['authorized_volume']);ck('JR_signal_budget',near(orig,jr_receipt['target_risk_amount']))
   entry[v]=[day,t['price'],qty,sign]
  else:
   ck('prefix_valid_CLOSE',held[v]*sign<0 and abs(held[v])>=qty,t['trade_id']);field='fee_close_today' if entry[v][0]==day else 'fee_close';entry[v][2]-=qty
   if entry[v][2]==0:del entry[v]
  fee=float(z[field])*qty*(t['price']*float(z['size']) if z.fee_method=='by_money' else 1.);slip=float(z['size'])*float(z.slippage)*qty;cost+=fee+slip;fees+=fee;slips+=slip;tp+=sign*qty*(float(bar.close)-t['price'])*float(z['size']);held[v]+=sign*qty;max_vol=max(max_vol,qty)
  prod=defaultdict(int)
  for vt,qq in held.items():
   if qq:prod[meta.loc[vt,'product_vt_symbol']]+=1
  ck('prefix_one_contract_per_product',all(v==1 for v in prod.values()),t['trade_id'])
 balance+=hp+tp-cost;last.update({v:float(b['close']) for v,b in bars.items()})
actual={v:q for v,q in held.items() if q};ck('prefix_actual_positions_match',actual==s['actual_positions']);ck('prefix_cash_matches_failure',near(balance,s['marked_equity'],1e-5) and near(balance,s['settled_balance'],1e-5))
margin=sum(abs(q)*last[v]*float(meta.loc[v,'size'])*float(meta.loc[v,'margin_ratio']) for v,q in actual.items());ck('prefix_actual_margin_floor',float(s['total_margin_in_use'])+1e-6>=margin)
vt='JR201907.CZCE';m=meta.loc[vt];mi=bisect_left(calendar,m.maturity_date);first=bisect_left(calendar,'2019-07-01');deadline=calendar[min(first-2,mi-10)];ck('JR_deadline',deadline=='2019-06-27')
rows=market.loc[market.vt_symbol.eq(vt)&market.date.between('2019-06-19','2019-06-28')].to_dict('records');clean_rows=[{k:r[k] for k in ['date','open','high','low','close','volume','close_oi','quote_class','execution_only']} for r in rows]
qty=int(actual[vt]);cut=ix.loc[(deadline,vt)];ck('physical_unresolved12',qty==12 and s['targets'][vt]==0 and sum(int(x['volume']) for x in s['pending_close_lots'][vt])==12 and s['states']['JR.CZCE']['layers']==[])
ck('deadline_fullqty_not_executable',float(cut.volume)<qty)
exp=rd(L/'outputs/expiry_execution_overlay.csv');cons=rd(L/'outputs/stage023_quantity_price_overlay/execution_quotes.csv')
exp_rows=exp.loc[exp.vt_symbol.eq(vt)&exp.date.between('2019-06-19','2019-06-27')].to_dict('records');con_rows=cons.loc[cons.vt_symbol.eq(vt)&cons.date.between('2019-06-19','2019-06-27')].to_dict('records')
R=dict(status='FAIL_INCOMPLETE_LIFECYCLE',verdict='FAIL',remaining_p0=0,remaining_p1=1,performance_valid=False,source_manifest_sha256=None,source_protocol_sha256=sha(P/'protocol.json'),source_commit=q['source_commit'],financial_replays_by_reviewer=0,full_period_statistics=None,code_start_hashes=code,input_hashes=q['source_manifest'],run_file_hashes={str(p.relative_to(P)):sha(p) for p in P.rglob('*') if p.is_file()},audit_script_sha256=sha(__file__),partial_ledger_validation=dict(actual_fills=len(tr),last_fill_date=tr.date.max(),failure_day=end,actual_positions=actual,account_snapshot_reconciliation_equity=balance,account_snapshot_difference=balance-float(s['marked_equity']),commission_recomputed=fees,slippage_recomputed=slips,actual_margin_recomputed=margin,scope='failed-prefix reconciliation only; no full-period return/DD/Sharpe/win-rate claim'),JR_opening=opening_capture,JR_lifecycle=dict(deadline=deadline,exit_signal_date=calendar[calendar.index(deadline)-1],lifecycle_events=rd(P/'failed_lifecycle_events.csv').loc[lambda x:x.vt_symbol.eq(vt)].to_dict('records'),causal_daily_quotes=clean_rows,existing_expiry_overlay_rows=exp_rows,existing_quantity_overlay_rows=con_rows,deadline_volume=float(cut.volume),actual_close_order_qty=12,partial_deadline_only_max_fill=7,partial_deadline_only_remaining=5,current_order=[x for x in s['active_orders'] if x['vt_symbol']==vt],original_close_signal_time='Not uniquely exported; provisional exit2915 matches both2019-06-25 and2019-06-26. Only lifecycle intent2019-06-26 and current reissue2019-06-27 are proven. No order/deferred/trade-event history in failure artifacts.'),root_cause='Predeclared all-or-none full-quantity daily execution plus fixed lifecycle deadline conflict with this actually held low-volume position. Risk fraction .0025 and original authorization have not caused a budget arithmetic violation. Do not truncate at2019 or claim complete result.',honest_options=['Keep this execution contract: retain failed diagnosis, do not publish complete no-weekly performance.','Before a new paired experiment, declare a uniform causal advance-exit/liquidity-position policy applicable to both arms; it changes the common economic contract and cannot be chosen only forJR or tuned to this cutoff.','Uniform genuine partial CLOSE is an execution-policy change; if first close intent was only6/26, cutoff6/27 daily volume7 still leaves5, so it alone is not proven sufficient. It must conserve actual qty/cost and retain the deadline.'],prohibited_shortcuts=['No download or invented quote evidence','No later6/28volume49 execution beyond frozen deadline','No JR blacklist or hindsight no-entry','No synthetic settlement or closing12 against day volume7','No unilateral disabled-arm policy patch','No relabeling failed prefix as whole2015-2026 backtest'],limits=['Failure prefix does not export every trade risk receipt/open-budget audit, weekly-null CSV, daily account snapshots, or complete unfilled books. OnlyJR preserved original receipt is available for actual opening budget independent proof; cannot extend it to all1492fills.','Complete financial source hashes and inputs verified, but no final manifest/summary exists. No complete netwin/payoff/annual table or recap generated.','Exact first native CLOSE event is not exported; earliest known lifecycle intent6/26 is not proof that no earlier native intent existed.','Daily proxy, disabled intradayC2/C9 and supply CSV, non-PIT fee/margin and real bid/ask/execution capacity remain.'],errors=errors,error_count=len(errors))
Path('/tmp/stage100_failed_no_weekly_audit_result.json').write_text(json.dumps(R,ensure_ascii=False,indent=2,default=str));print(json.dumps({k:v for k,v in R.items() if k not in ['input_hashes','code_start_hashes','run_file_hashes']},ensure_ascii=False,indent=2,default=str))
