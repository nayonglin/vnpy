from pathlib import Path
from collections import defaultdict
from bisect import bisect_left,bisect_right
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib,json,math
import pandas as pd
import numpy as np

ROOT=Path('/Users/mac/.codex/worktrees/full-market-noai-one-lot/fian')
LINE=ROOT/'research/lines/futures_trend_full_market_noai_one_lot'
A=LINE/'outputs/run_20261019_contract_weekly_long_v1'
C=LINE/'outputs/run_20261020_risk025_no_weekly_v1'
OLD=LINE/'outputs/run_20261019_weekly_long_v1'
R={'reviewer':'independent_quarter_no_weekly_actual_reviewer','financial_replays':0,'implementation_changes':0,'source_changes':0,'findings':[]}
errors=[]
def ck(name,value,detail=None):
 if not bool(value):errors.append({'check':name,'detail':detail})
def near(a,b,atol=1e-7):return math.isfinite(float(a)) and math.isfinite(float(b)) and abs(float(a)-float(b))<=atol

def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def read(folder,name):
 try:return pd.read_csv(folder/(name+'.csv'),keep_default_na=False,float_precision='round_trip')
 except pd.errors.EmptyDataError:
  columns={'weekly_execution_audit':['date','vt_symbol','order_id','direction','original_signal_date','signal_snapshot_json','open_snapshot_json','weekly_allowed','reason','filled','trade_id'],'weekly_signal_audit':['date','vt_symbol','product_vt_symbol','direction','entry_context','native_selected_volume','selected_volume','weekly_allowed','snapshot_json'],'weekly_contract_features':['product_vt_symbol','contract_vt_symbol','week_last_session','close','volume','valid','ma5','ma10','ma20','ma40','history_weeks','valid_weeks','allowed','reason','evidence_id','export_scope']}
  if name not in columns:raise
  return pd.DataFrame(columns=columns[name])
def js(p):return json.loads(Path(p).read_text())
def flag(v):return str(v).lower()=='true'
def dump(v):
 if isinstance(v,dict):return {str(k):dump(x) for k,x in v.items()}
 if isinstance(v,(list,tuple)):return [dump(x) for x in v]
 if isinstance(v,np.generic):return dump(v.item())
 if isinstance(v,float) and not math.isfinite(v):return None
 return v

if not (C/'manifest.json').exists():raise SystemExit('Complete manifest not present; no audit of partial run.')
cm=js(C/'manifest.json');am=js(A/'manifest.json');summary=js(C/'summary.json')
R['source_manifest_sha256']=sha(C/'manifest.json');R['baseline_manifest_sha256']=sha(A/'manifest.json');R['review_time']=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat();R['source_commit']=cm['source_commit']
ck('baseline_manifest_bound',R['baseline_manifest_sha256']==cm['baseline_run_manifest_sha256'])
compare_keys=['source_manifest','expiry_execution_overlay','quantity_execution_overlay','lifecycle_sources','mode','start','end','official_material_identity']
R['baseline_comparison']={k:am[k]==cm[k] for k in compare_keys}
for k,v in R['baseline_comparison'].items():ck('baseline_'+k,v)
ck('daily_proxy_only',cm['mode']=='daily-proxy')
ck('production_false',cm['production_qualified'] is False and cm['order_api_calls']==0 and cm['market_downloads']==0)
ck('source_commit_bound',cm['source_commit']=='9feb5784d7757ee81cbab007a610a0d64da64ca6')
ck('parent_bound',cm['parent_execution_run_id']=='run_20261020_contract_weekly_risk05_v3' and cm['parent_execution_manifest_sha256']=='f2fb3b9d17621ab5d9d64001238b305fbf9fb4fd3dd8fa72432bc0a3955f6860' and cm['parent_execution_commit']=='83e7669aca75811e50e009c3095c015311e646df')
ck('frozen_data_anchor',cm['frozen_data_manifest_sha256']=='859982f079da55aa1292154d5fc9b1004d1f0d5f23f75c4ec58ca892a102cb25')
parent=json.loads((LINE/'outputs/run_20261020_contract_weekly_risk05_v3/manifest.json').read_text())
ck('parent_parameter_only_fraction',{k:(parent['parameters'].get(k),v) for k,v in cm['parameters'].items() if parent['parameters'].get(k)!=v}=={'stage068_risk_fraction':(.005,.0025)})
checks=[]
for filename,digest in cm['hashes'].items():
 actual=sha(C/filename);ck('output_hash:'+filename,actual==digest);checks.append(filename)
for path,digest in cm['code_hashes'].items():
 ck('current_code_hash:'+path,sha(path)==digest)
for filename,digest in cm['code_snapshot_hashes'].items():ck('snapshot:'+filename,sha(C/'code_snapshot'/filename)==digest)
for path,digest in js(C/'code_start_hashes.json').items():
 ck('start_code:'+path,sha(path)==digest);ck('start_snapshot:'+path,sha(C/'code_snapshot'/Path(path).name)==digest)
for group in ['source_inputs','output_files']:
 for label,item in cm['source_manifest'][group].items():ck('original_'+group+':'+label,sha(item['path'])==item['sha256'])
for path,digest in cm['lifecycle_sources'].items():ck('lifecycle_source:'+path,sha(path)==digest)
for filename in ['mapping.csv','market_daily.csv','contract_metadata.csv','lifecycle_deadlines.csv','trading_calendar.csv']:
 ck('AC_same_'+filename,sha(A/filename)==sha(C/filename))
R['hash_checks']={'output_files':len(checks),'code_hashes':len(cm['code_hashes']),'snapshots':len(cm['code_snapshot_hashes']),'all_hash_checks_passed':not errors}
print('Hash binding checked',flush=True)
params=cm['parameters']
ck('fractional_policy',params['fixed_size']==0 and params['max_position_size']==2147483647 and params['min_position_size']==1 and params['stage068_risk_fraction']==.0025 and params['max_concurrent_positions']==93)
changes={k:(am['parameters'].get(k),v) for k,v in params.items() if am['parameters'].get(k)!=v}
ck('only_approved_changes',changes=={'max_position_size':(1,2147483647),'stage068_risk_fraction':(None,.0025)})
for key in ['enable_ai_product_pool_filter','enable_selection_pairwise_v2','enable_add_position','enable_donchian_add_position','enable_post_entry_quality_add','enable_supply_demand_headwind_filter','enable_stage827_intraday_c2_stop','enable_stage847_half_r_stop_retry']:ck('policy_off:'+key,not params[key])
tr=read(C,'trades');daily=read(C,'daily');meta=read(C,'contract_metadata').set_index('vt_symbol');mapping=read(C,'mapping');wout=read(C,'weekly_contract_features')
ck('daily_dates_unique',not daily.date.duplicated().any());ck('daily_endpoints',daily.iloc[0].date=='2015-01-05' and daily.iloc[-1].date=='2026-10-16' and len(daily)==2862)
ck('fills_positive_integer',tr.volume.gt(0).all() and (tr.volume%1).eq(0).all());ck('trades_unique',not tr.trade_id.duplicated().any());ck('fill_endpoint',tr.date.min()>=daily.date.iloc[0] and tr.date.max()<=daily.date.iloc[-1] and tr.date.max()==summary['last_fill_date'])
market=read(C,'market_daily');ck('market_unique',not market.duplicated(['date','vt_symbol']).any())
raw_original=read(LINE/'outputs/inputs','market_daily');original_ix=raw_original.set_index(['date','vt_symbol']);mapix=mapping.set_index(['date','continuous_symbol_vt']);mktix=market.set_index(['date','vt_symbol'])
raw=market.loc[~market.execution_only.map(flag)].copy();rawix=raw.set_index(['date','vt_symbol'])
ck('accepted_clean_source_keys',set(rawix.index)==set(original_ix.index))
bound=rawix.reindex(original_ix.index);precision={}
for field in ['open','high','low','close','volume','close_oi']:
 x=original_ix[field].astype(float).to_numpy();y=bound[field].astype(float).to_numpy();delta=np.abs(x-y)
 precision[field]={'max_abs_delta':float(delta.max()),'different_binary_values':int((x!=y).sum())}
 ck('raw_input_close_binding:'+field,np.isclose(x,y,rtol=1e-14,atol=1e-10,equal_nan=True).all())
ck('raw_input_epoch_binding',original_ix.contract_epoch_id.tolist()==bound.contract_epoch_id.tolist())
R['raw_input_reparse_precision']=precision

calendar_path=cm['source_manifest']['source_inputs']['calendar']['path'];cal=pd.to_datetime(np.load(calendar_path).astype(str),format='%Y%m%d').strftime('%Y-%m-%d').tolist()
prev=dict(zip(cal[1:],cal[:-1]));week_ends={}
for d in cal:
 y,w,_=pd.Timestamp(d).isocalendar();week_ends[(int(y),int(w))]=d
calendar_csv=read(C,'trading_calendar')
ck('frozen_exported_calendar_matches_original',calendar_csv.date.tolist()==cal)
global_ends=[d for _,d in sorted(week_ends.items())]
ck('calendar_extends_beyond_end',cal[-1]>'2026-10-16')
# Disabled strategy evidence: zero queries/checks and strict null snapshots.
ck('weekly_disabled_manifest',cm['weekly_filter']=='disabled' and cm['long_weekly_filter'] is False and cm['weekly_policy'] is None)
ck('weekly_disabled_summary',summary['weekly_filter']=='disabled' and summary['long_weekly_filter'] is False and summary['weekly_policy'] is None)
ck('weekly_empty_export',len(wout)==0 and cm['weekly_feature_export']==dict(scope='disabled_no_weekly_queries',queried_contracts=[],rows=0))
ck('weekly_export_header',wout.columns.tolist()==['product_vt_symbol','contract_vt_symbol','week_last_session','close','volume','valid','ma5','ma10','ma20','ma40','history_weeks','valid_weeks','allowed','reason','evidence_id','export_scope'])
ck('weekly_scope',cm['weekly_feature_export_scope']=='disabled_no_weekly_queries')
for field in ['weekly_signal_candidates','weekly_budget_eligible_long_signal_rejections','weekly_execution_checks','weekly_execution_rejections']:
 ck('weekly_zero_'+field,summary[field]==0)
ck('weekly_NA',summary['actual_long_weekly_violations'] is None)
for name in ['weekly_execution_audit','weekly_signal_audit']:
 ck('weekly_audit_empty:'+name,len(read(C,name))==0)
for t in tr.itertuples():
 ck('weekly_trade_strict_null',json.loads(t.stage059_weekly_signal_snapshot) is None and json.loads(t.stage059_weekly_open_snapshot) is None,t.trade_id)
R['actual_open_signal_counts']={str(k):int(v) for k,v in tr.loc[tr.offset.eq('open')].groupby(['direction','signal']).size().items()}
R['weekly_independent']=dict(enabled=False,full_rows=len(wout),actual_long_weekly_violations=None,actual_long_opens=int(((tr.offset=='open')&(tr.direction=='long')).sum()),actual_short_opens=int(((tr.offset=='open')&(tr.direction=='short')).sum()),strategy_evidence='not_applicable',method='No provider or weekly algorithm used by this reader. Frozen MRO reviewed: no weekly strategy/execution mixin; actual exports and all trade snapshots checked empty/null.')
print('Disabled weekly evidence checked',flush=True)
# Verify causal mapping observations and exact chosen epoch against accepted clean data.
map_bad=0;obs_miss=0;oierr=0.;main_epoch_bad=0
for r in mapping[mapping.main_contract_vt.ne('')].itertuples():
 ck('mapping_previous_calendar_session',r.observation_date==prev.get(r.date),[r.date,r.continuous_symbol_vt])
 k=(r.observation_date,r.main_contract_vt)
 if k not in rawix.index:obs_miss+=1;continue
 bar=rawix.loc[k];oierr=max(oierr,abs(float(bar.close_oi)-float(r.close_oi)))
 if str(bar.contract_epoch_id)!=r.contract_epoch_id:main_epoch_bad+=1
ck('mapping_observation_exists',obs_miss==0);ck('mapping_oi',oierr<1e-7);ck('mapping_epoch',main_epoch_bad==0)
R['mapping']={'mapped_rows':int(mapping.main_contract_vt.ne('').sum()),'missing_observation_bars':obs_miss,'max_oi_difference':oierr,'epoch_mismatch':main_epoch_bad}
# Whole-entry quantity ledger, reconstructed without importing Stage069.
from decimal import Decimal,ROUND_FLOOR
positions=defaultdict(int);active={};finished=[];segments=[];fee_errors=[];slip_errors=[];maxlot=maxproducts=0
for t in tr.to_dict('records'):
 vt=t['vt_symbol'];qty=int(t['volume']);sgn=1 if t['direction']=='long' else -1;row=meta.loc[vt]
 ck('fill_has_exact_bar',(t['date'],vt) in mktix.index,t['trade_id'])
 bar=mktix.loc[(t['date'],vt)];ck('full_bar_volume',float(bar.volume)>=qty,t['trade_id']);ck('fill_is_actual_open',near(t['price'],bar.open),t['trade_id'])
 ck('fill_range',float(bar.low)<=t['price']<=float(bar.high),t['trade_id'])
 ck('execution_quote_flags',flag(t['execution_only_quote'])==flag(bar.execution_only) and t['execution_quote_class']==bar.quote_class and t['execution_evidence_id']==bar.evidence_id,t['trade_id'])
 if t['offset']=='open':
  ck('no_new_overlay_open',not flag(bar.execution_only),t['trade_id'])
  ck('no_actual_add',positions[vt]==0 and vt not in active,t['trade_id'])
  ck('signal_clock',str(t['signal_datetime'])[:10]<=str(t['order_reissue_datetime'])[:10]<t['date'],t['trade_id'])
  sd=str(t['signal_datetime'])[:10];ck('signal_accepted_clean',(sd,vt) in rawix.index,t['trade_id'])
  product=row.product_vt_symbol;ck('signal_contract_mapping',mapix.loc[(sd,product)].main_contract_vt==vt,t['trade_id'])
  active[vt]=dict(entry=t,remaining=qty,realized=[]);field='fee_open'
 else:
  ck('valid_actual_close',positions[vt]!=0 and positions[vt]*sgn<0 and abs(positions[vt])>=qty,t['trade_id'])
  item=active[vt];entry=item['entry'];field='fee_close_today' if entry['date']==t['date'] else 'fee_close'
  gross=(t['price']-entry['price'])*(1 if entry['direction']=='long' else -1)*float(row['size'])*qty
  entrycost=(entry['commission']+entry['slippage'])*qty/entry['volume'];exitcost=t['commission']+t['slippage']
  seg=dict(vt_symbol=vt,entry_trade_id=entry['trade_id'],exit_trade_id=t['trade_id'],volume=qty,gross_pnl=gross,cost=entrycost+exitcost,entry_cost=entrycost,exit_cost=exitcost,net_pnl=gross-entrycost-exitcost)
  segments.append(seg);item['realized'].append(seg);item['remaining']-=qty
  if not item['remaining']:
   ps=item['realized'];wholegross=sum(x['gross_pnl'] for x in ps);wholecost=entry['commission']+entry['slippage']+sum(x['exit_cost'] for x in ps)
   finished.append(dict(entry_trade_id=entry['trade_id'],exit_trade_id=t['trade_id'],volume=entry['volume'],exit_price=sum(tr.loc[tr.trade_id.eq(x['exit_trade_id']),'price'].iloc[0]*x['volume'] for x in ps)/entry['volume'],gross_pnl=wholegross,cost=wholecost,net_pnl=wholegross-wholecost,close_trade_ids=[x['exit_trade_id'] for x in ps]));del active[vt]
 expectedfee=float(row[field])*qty*(t['price']*float(row['size']) if row.fee_method=='by_money' else 1.)
 fee_errors.append(abs(expectedfee-t['commission']));slip_errors.append(abs(float(row['size'])*float(row.slippage)*qty-t['slippage']))
 positions[vt]+=sgn*qty
 prods=defaultdict(list)
 for v,q in positions.items():
  if q:prods[meta.loc[v].product_vt_symbol].append(v)
 ck('one_actual_contract_per_product',all(len(v)==1 for v in prods.values()),t['trade_id'])
 maxlot=max(maxlot,max([abs(q) for q in positions.values()] or [0]));maxproducts=max(maxproducts,len(prods))
closed=read(C,'closed_episodes');residual=js(C/'residual_open_positions.json');partial=read(C,'partial_closes_of_residual_entries')
ck('completed_entry_count',len(closed)==len(finished));closedix=closed.set_index('entry_trade_id')
neterr=costerr=0.
for x in finished:
 saved=closedix.loc[x['entry_trade_id']];ck('completed_entry_volume',saved.volume==x['volume'] and saved.original_open_volume==x['volume'] and saved.remaining_volume==0)
 ck('all_close_ids',json.loads(saved.close_trade_ids)==x['close_trade_ids'])
 for field in ['net_pnl','gross_pnl','cost','exit_price']:ck('completed_'+field,near(saved[field],x[field]),x['entry_trade_id'])
 neterr=max(neterr,abs(saved.net_pnl-x['net_pnl']));costerr=max(costerr,abs(saved.cost-x['cost']))
resix={x['vt_symbol']:x for x in residual};ck('residual_keys',set(resix)==set(active))
partialnet=residualmark=residualentrycost=0.;partialrows=[]
for vt,item in active.items():
 e=item['entry'];saved=resix[vt];rem=item['remaining'];ck('residual_quantity',saved['remaining_volume']==rem==saved['volume'] and saved['original_open_volume']==e['volume'] and saved['closed_volume']==e['volume']-rem)
 entrycost=(e['commission']+e['slippage'])*rem/e['volume'];ck('residual_entry_cost',near(saved['commission']+saved['slippage'],entrycost))
 ck('residual_segments',len(saved['realized_segments'])==len(item['realized']))
 partialrows+=item['realized'];partialnet+=sum(x['net_pnl'] for x in item['realized']);residualentrycost+=entrycost
 endbar=mktix.loc[(daily.date.iloc[-1],vt)];residualmark+=(float(endbar.close)-e['price'])*(1 if e['direction']=='long' else -1)*float(meta.loc[vt,'size'])*rem
ck('partial_residual_rows',len(partial)==len(partialrows))
for x in partialrows:
 y=partial.loc[partial.exit_trade_id.eq(x['exit_trade_id'])];ck('partial_id_unique',len(y)==1)
 if len(y):
  for field in ['volume','gross_pnl','entry_cost','exit_cost','cost','net_pnl']:ck('partial_'+field,near(y.iloc[0][field],x[field]))
bridge=1e6+sum(x['net_pnl'] for x in finished)+partialnet+residualmark-residualentrycost
ck('closed_partial_residual_bridge',near(bridge,daily.equity.iloc[-1],1e-5))
R['quantity_ledger']=dict(completed_entries=len(finished),partial_exit_fills=len(segments)-len(finished),residual_entries=len(active),residual_partial_fills=len(partialrows),residual_partial_realized_net=partialnet,residual_mark_pnl=residualmark,residual_entry_cost=residualentrycost,ending_equity_bridge=bridge,fee_max_error=max(fee_errors),slip_max_error=max(slip_errors),completed_net_max_error=neterr,max_lots=maxlot,max_actual_products=maxproducts)
ck('all_fees',max(fee_errors)<1e-7);ck('all_slippage',max(slip_errors)<1e-7)
print('Independent quantity/partial ledger checked',flush=True)
# Daily MTM and causal opening equity; opening audits ordered after all actual CLOSEs.
account=read(C,'account_snapshots').set_index('date');aud=read(C,'open_budget_audit');risk=read(C,'entry_risk')
opens=tr[tr.offset.eq('open')].set_index('signal_order_id');auditdays={day:g.to_dict('records') for day,g in aud.groupby('date',sort=False)};tradedays={day:g.to_dict('records') for day,g in tr.groupby('date',sort=False)}
bar_days={day:g.set_index('vt_symbol').to_dict('index') for day,g in market.groupby('date',sort=False)}
held=defaultdict(int);last={};preveq=1e6;dailyerrors=[];openingerrors=[];filledsnap=set();ratios=[];margins=[];notionals=[];maxbrokerratio=0.;diagchecked=0
for dr in daily.itertuples():
 day=dr.date;bars=bar_days[day];startheld=dict(held);dayfills=tradedays.get(day,[])
 marks={v:(float(bars[v]['open']) if v in bars and float(bars[v]['volume'])>0 else last[v]) for v,q in held.items() if q}
 openingeq=preveq+sum(q*(marks[v]-last[v])*float(meta.loc[v,'size']) for v,q in held.items() if q);cost=0.
 ck('close_first', [x['offset'] for x in dayfills]==sorted([x['offset'] for x in dayfills],key=lambda x:0 if x=='close' else 1),day)
 for x in dayfills:
  if x['offset']=='close':held[x['vt_symbol']]+=(1 if x['direction']=='long' else -1)*int(x['volume']);cost+=x['commission']+x['slippage']
 for a in auditdays.get(day,[]):
  current=openingeq-cost;openingerrors.append(abs(float(a['opening_equity'])-current));ck('opening_equity',near(a['opening_equity'],current,1e-5),a['order_id'])
  s=json.loads(a['signal_snapshot']);filled=flag(a['filled'])
  if s:
   signalbudget=float(Decimal(str(s['signal_equity']))*Decimal('.0025')) if float(s['signal_equity'])>0 else 0.
   ck('signal_fraction',s['risk_fraction']==.0025 and near(s['target_risk_amount'],signalbudget))
   expected=min(signalbudget,float(Decimal(str(current))*Decimal('.0025'))) if current>0 else 0.
   ck('opening_budget',near(a['opening_budget'],expected),a['order_id'])
   if a['risk_per_contract']!='':
    per=max(abs(float(a['open_price'])-float(a['stop_price']))*float(a['size']),float(a['pricetick'])*float(a['size']),1.)
    ck('audit_per_risk',near(per,a['risk_per_contract']));ck('audit_total_risk',near(Decimal(str(per))*int(a['volume']),a['total_risk']))
  if not filled:
   ck('rejected_no_fill',a['order_id'] not in opens.index,a['order_id']);continue
  ck('filled_unique_audit',a['order_id'] in opens.index and flag(a['allowed']))
  x=opens.loc[a['order_id']];ck('filled_id',x.trade_id==a['trade_id']);ck('snapshot_unique',s['snapshot_id'] not in filledsnap);filledsnap.add(s['snapshot_id'])
  ck('snapshot_identity',s['contract_vt_symbol']==x.vt_symbol and s['product_vt_symbol']==meta.loc[x.vt_symbol,'product_vt_symbol'] and s['direction']==x.direction and s['signal']==x.signal and s['signal_datetime'][:10]==str(x.signal_datetime)[:10])
  ck('authorized_qty',s['authorized_volume']==x.volume==a['volume']);ck('snapshot_trade',json.loads(x.stage068_signal_snapshot)==s)
  ck('signal_qty_risk',Decimal(str(s['risk_per_contract']))*int(x.volume)<=Decimal(str(s['target_risk_amount'])))
  ck('actual_total_risk',near(x.stage068_entry_risk,a['total_risk']) and near(x.stage068_risk_per_contract,a['risk_per_contract']) and near(x.stage068_open_budget,a['opening_budget']))
  ck('both_budget_caps',float(a['total_risk'])<=float(a['opening_budget'])+1e-8<=s['target_risk_amount']+1e-7,x.trade_id)
  ck('stop_side',x.price>s['stop_price'] if x.direction=='long' else x.price<s['stop_price'])
  rr=risk[(risk.contract_vt_symbol==x.vt_symbol)&(risk.direction==x.direction)&(risk.signal==x.signal)&(risk.date==s['signal_datetime'][:10])];ck('entry_diagnostic_unique',len(rr)==1,x.trade_id)
  if len(rr)==1:
   rr=rr.iloc[0];ck('entry_target_risk',near(rr.target_risk_amount,s['target_risk_amount']) and near(rr.actual_risk_amount,x.stage068_entry_risk) and near(rr.stop_price,s['stop_price']) and rr.volume==x.volume and rr.sizing_method=='risk_budget');diagchecked+=1
  margin=sum(abs(q)*marks[v]*float(meta.loc[v,'size'])*float(meta.loc[v,'margin_ratio']) for v,q in held.items() if q)+int(x.volume)*x.price*float(meta.loc[x.vt_symbol,'size'])*float(meta.loc[x.vt_symbol,'margin_ratio'])
  brokerratio=margin*params['stage830_broker_margin_multiplier']/current;maxbrokerratio=max(maxbrokerratio,brokerratio);ck('actual_broker_margin',brokerratio<=params['stage830_projected_broker10_margin_to_equity_cap']+1e-10,x.trade_id)
  held[x.vt_symbol]+=(1 if x.direction=='long' else -1)*int(x.volume);marks[x.vt_symbol]=x.price;cost+=x.commission+x.slippage;ratios.append(float(x.stage068_entry_risk)/float(x.stage068_open_budget))
 hp=sum(q*((float(bars[v]['close']) if v in bars else last[v])-last[v])*float(meta.loc[v,'size']) for v,q in startheld.items() if q)
 tp=sum((1 if x['direction']=='long' else -1)*int(x['volume'])*(float(bars[x['vt_symbol']]['close'])-x['price'])*float(meta.loc[x['vt_symbol'],'size']) for x in dayfills)
 net=hp+tp-sum(x['commission']+x['slippage'] for x in dayfills);dailyerrors.append([hp-dr.holding_pnl,tp-dr.trading_pnl,net-dr.net_pnl])
 ck('daily_hold',near(hp,dr.holding_pnl,1e-6),day);ck('daily_trade',near(tp,dr.trading_pnl,1e-6),day);ck('daily_net',near(net,dr.net_pnl,1e-6),day)
 last.update({v:float(z['close']) for v,z in bars.items()});pos={v:q for v,q in held.items() if q};ck('daily_actual_positions',pos==json.loads(account.loc[day,'positions']),day)
 preveq+=net;ck('daily_equity',near(preveq,dr.equity,1e-5) and near(preveq,account.loc[day,'strategy_equity'],1e-5),day)
 margin=sum(abs(q)*last[v]*float(meta.loc[v,'size'])*float(meta.loc[v,'margin_ratio']) for v,q in pos.items());margins.append(margin);notionals.append(sum(abs(q)*last[v]*float(meta.loc[v,'size']) for v,q in pos.items()))
 ck('actual_margin_floor',float(account.loc[day,'margin'])+1e-6>=margin,day)
ck('all_open_audits_filled',len(filledsnap)==len(opens));ck('entry_diagnostic_all',diagchecked==len(opens))
R['budget']=dict(audit_rows=len(aud),actual_opens=len(opens),rejections=int((~aud.filled.map(flag)).sum()),reasons=aud.loc[~aud.filled.map(flag),'reason'].value_counts().to_dict(),max_risk_budget_ratio=max(ratios),opening_equity_max_error=max(openingerrors),matched_entry_risk_rows=diagchecked,max_actual_broker_ratio=maxbrokerratio)
R['accounting']=dict(daily_mtm_max_errors=np.max(np.abs(dailyerrors),axis=0).tolist(),ending_equity=preveq,max_margin=max(margins),max_notional=max(notionals),max_margin_equity_ratio=float(np.max(np.array(margins)/daily.equity)),max_notional_equity_ratio=float(np.max(np.array(notionals)/daily.equity)))
print('Actual opening risk and daily account checked',flush=True)
# Full lifecycle independent calendar formulas, then actual EOD snapshots.
dead=read(C,'lifecycle_deadlines').set_index('vt_symbol');deadline={}
for vt,m in meta.iterrows():
 expiry=bisect_left(cal,m.maturity_date);ck('maturity_exact_calendar',cal[expiry]==m.maturity_date,vt)
 idx=expiry-1 if m.product_class=='Index' else min(bisect_left(cal,str(m.contract_yyyymm)[:4]+'-'+str(m.contract_yyyymm)[4:6]+'-01')-2,expiry-10)
 deadline[vt]=cal[idx];ck('deadline_formula',dead.loc[vt].deadline==cal[idx] and dead.loc[vt].exit_signal_date==cal[idx-1],vt)
for x in tr.loc[tr.offset.eq('open')].itertuples():ck('no_cutoff_open',x.date<deadline[x.vt_symbol],x.trade_id)
for day,a in account.iterrows():
 for vt,q in json.loads(a.positions).items():ck('no_deadline_residual',day<deadline[vt],[day,vt,q])
for vt in active:ck('end_residual_fresh_valid',daily.date.iloc[-1]<deadline[vt] and (daily.date.iloc[-1],vt) in mktix.index)
R['lifecycle']=dict(deadlines_checked=len(dead),actual_residuals=len(active),late_position_days=sum(1 for e in errors if e['check']=='no_deadline_residual'))
eq=1e6+daily.net_pnl.cumsum();r=np.log(eq/eq.shift(1)).fillna(0);dd=(eq/eq.cummax()-1)*100
R['stats']=dict(ending_equity=float(eq.iloc[-1]),net_pnl=float(daily.net_pnl.sum()),return_pct=float((eq.iloc[-1]/1e6-1)*100),max_dd_pct=float(dd.min()),max_dd_amount=float((eq-eq.cummax()).min()),sharpe_240_log=float(r.mean()/r.std(ddof=1)*np.sqrt(240)),commission=float(tr.commission.sum()),slippage=float(tr.slippage.sum()),fills=len(tr),complete_episodes=len(closed),win_rate_pct=float((closed.net_pnl>0).mean()*100),max_volume=int(tr.volume.max()),total_open_contracts=int(tr.loc[tr.offset.eq('open'),'volume'].sum()),residual_contracts=sum(x['remaining'] for x in active.values()))
wins=np.array([x['net_pnl'] for x in finished if x['net_pnl']>0]);losses=np.array([x['net_pnl'] for x in finished if x['net_pnl']<0])
R['stats'].update(net_payoff_ratio=float(wins.mean()/-losses.mean()),net_profit_factor=float(wins.sum()/-losses.sum()),max_actual_products=maxproducts)
R['annual']={str(year):dict(net_pnl=float(g.net_pnl.sum()),start_equity=float(g.equity.iloc[0]-g.net_pnl.iloc[0]),end_equity=float(g.equity.iloc[-1])) for year,g in daily.groupby(daily.date.str[:4])}
# Native forced-margin event arithmetic and cancelled intentions, independent of078.
forced=read(C,'forced_margin_deleverage_events');cancels=read(C,'unfilled_intent_cancellations')
forcedcols=['datetime','date','vt_symbol','product_vt_symbol','direction','priority','trigger_ratio','target_ratio','broker_multiplier','equity','margin_before','ratio_before','margin_per_contract','reduce_volume','volume_before','volume_after','price','margin_after','ratio_after']
ck('forced_event_columns',forced.columns.tolist()==forcedcols)
for x in forced.itertuples():
 targetmoney=float(x.equity)*float(x.target_ratio)/float(x.broker_multiplier)
 want=min(int(x.volume_before),max(1,math.ceil((float(x.margin_before)-targetmoney)/float(x.margin_per_contract))))
 ck('forced_original_parameters',x.trigger_ratio==params['forced_margin_deleverage_trigger_ratio'] and x.target_ratio==params['forced_margin_deleverage_target_ratio'] and x.broker_multiplier==params['forced_margin_deleverage_broker_multiplier'] and x.priority==params['forced_margin_deleverage_priority'])
 ck('forced_trigger',x.ratio_before>x.trigger_ratio)
 ck('forced_exact_target_qty',x.reduce_volume==want and x.volume_after==x.volume_before-x.reduce_volume,[x.date,x.vt_symbol])
 ck('forced_projected_release',near(x.margin_after,x.margin_before-x.reduce_volume*x.margin_per_contract,1e-6),[x.date,x.vt_symbol])
 ck('forced_ratios',near(x.ratio_before,x.margin_before*x.broker_multiplier/x.equity) and near(x.ratio_after,x.margin_after*x.broker_multiplier/x.equity))
for day,g in forced.groupby('date'):
 ck('forced_daily_max_reductions',len(g)<=params['forced_margin_deleverage_max_reductions_per_day'],day)
 # In a single native planning loop, projected releases cannot be charged twice.
 if len(g)>1:
  for prior,nextrow in zip(g.iloc[:-1].to_dict('records'),g.iloc[1:].to_dict('records')):
   ck('forced_iteration_projection_chain',near(prior['margin_after'],nextrow['margin_before'],1e-6),day)
used_receipts={json.loads(x.stage068_signal_snapshot)['snapshot_id'] for x in tr.loc[tr.offset.eq('open')].itertuples()}
cancelled_snapshots=[]
for x in cancels.itertuples():
 receipts=json.loads(x.receipt_json);ck('cancel_archived_qty',sum(int(v['authorized_volume']) for v in receipts if v)==x.volume)
 ck('cancel_not_actual_close',x.reason=='forced_margin_cancel_unfilled_open_intent')
 actual=json.loads(account.loc[x.date,'positions']).get(x.vt_symbol,0);ck('cancel_actual_position',actual==x.actual_position)
 quote_day=market.loc[market.vt_symbol.eq(x.vt_symbol)&market.date.le(x.date),'date'].max();ck('cancel_causal_quote',quote_day<=x.date and (quote_day,x.vt_symbol) in mktix.index);ck('cancel_quote_asof_label',x.causal_quote_asof==quote_day and flag(x.valuation_proxy)==(quote_day<x.date))
 if (quote_day,x.vt_symbol) in mktix.index:
  q=mktix.loc[(quote_day,x.vt_symbol)];per=float(q.close)*float(meta.loc[x.vt_symbol,'size'])*float(meta.loc[x.vt_symbol,'margin_ratio'])
  expected_change=x.volume*per*params['forced_margin_deleverage_broker_multiplier']/float(daily.loc[daily.date.eq(x.date),'equity'].iloc[0])
  ck('cancel_projected_margin_release',near(x.ratio_before-x.ratio_after,expected_change,1e-8),[x.date,x.vt_symbol])
 for v in receipts:
  ck('cancelled_receipt_not_filled',v['snapshot_id'] not in used_receipts)
  ck('cancel_receipt_binding',v['contract_vt_symbol']==x.vt_symbol and v['product_vt_symbol']==x.product_vt_symbol and v['direction']==x.direction and v['signal_datetime'][:10]<=x.date)
  cancelled_snapshots.append(v['snapshot_id'])
ck('summary_cancel_count',len(cancels)==summary['forced_margin_unfilled_intent_cancellations'])
R['forced_planning']=dict(actual_close_planning_events=len(forced),cancelled_whole_intents=len(cancels),cancelled_contracts=int(cancels.volume.sum()) if len(cancels) else 0,cancelled_receipts=len(cancelled_snapshots),all_event_target_and_projection_formulas_checked=True,limitation='Complete event formulas and account cash/margin independently checked; private intraday full candidate priority sets and all unfilled pending states are not exported, so per-event ranking inputs cannot be exhaustively reconstructed.')
# Independent pending lifecycle identity chains; no implementation imports.
pending=read(C,'pending_open_lifecycle_events');preserved={};cancelled085={};dispatches=[];trace_counts=defaultdict(int)
receipt_by_id={json.loads(t.stage068_signal_snapshot)['snapshot_id']:json.loads(t.stage068_signal_snapshot) for t in tr.loc[tr.offset.eq('open')].itertuples()}
fill_by_id={json.loads(t.stage068_signal_snapshot)['snapshot_id']:t for t in tr.loc[tr.offset.eq('open')].itertuples()}
canonical=lambda x:json.dumps(x,sort_keys=True,separators=(',',':'))
for row in pending.itertuples():
 trace_counts[row.event]+=1
 asof=market.loc[market.vt_symbol.eq(row.vt_symbol)&market.date.le(row.date),'date'].max()
 ck('pending_quote_asof',row.causal_quote_asof==asof and flag(row.valuation_proxy)==(asof<row.date),[row.date,row.vt_symbol,row.event])
 if row.event=='cached_order_dispatch':
  ck('cached_dispatch_not_new_quote',float(row.order_quote)==float(mktix.loc[(asof,row.vt_symbol),'close']))
  dispatches.append([row.date,row.vt_symbol,asof]);continue
 receipts=json.loads(row.receipt_json)
 if row.event=='preserve':
  ck('preserve_receipt_dict',isinstance(receipts,dict))
  receipts=[receipts]
 else:ck('cancel_receipt_list',isinstance(receipts,list))
 for snap in receipts:
  if snap is None:continue
  sid=snap['snapshot_id'];qty=int(snap['authorized_volume']);side=snap['direction'];product=snap['product_vt_symbol']
  ck('pending_original_binding',snap['contract_vt_symbol']==row.vt_symbol and product==row.product_vt_symbol and snap['signal_datetime'][:10]<=row.date)
  ck('pending_signal_budget',near(snap['target_risk_amount'],Decimal(str(snap['signal_equity']))*Decimal('.0025')))
  if sid in preserved:ck('pending_receipt_unchanged',canonical(preserved[sid]['receipt'])==canonical(snap),sid)
  if row.event=='preserve':
   ck('pending_original_qty_target',qty==int(float(row.volume)) and int(float(row.target))==qty*(1 if side=='long' else -1))
   currentmap=mapix.loc[(row.date,product),'main_contract_vt'] if (row.date,product) in mapix.index else ''
   ck('pending_preserve_current_map',currentmap==row.vt_symbol,[row.date,row.vt_symbol])
   ck('pending_preserve_before_deadline',row.date<deadline[row.vt_symbol])
   # By EOD a preserved actual-zero OPEN remains unfilled on that same day.
   ck('pending_preserve_actual_zero',json.loads(account.loc[row.date,'positions']).get(row.vt_symbol,0)==0,[row.date,row.vt_symbol])
   ck('pending_weekly_disabled',json.loads(row.weekly_authorization_json) is None)
   preserved.setdefault(sid,dict(receipt=snap,dates=[]))['dates'].append(row.date)
  elif row.event=='cancel':
   ck('pending_cancel_never_filled',sid not in receipt_by_id,sid);cancelled085[sid]=dict(date=row.date,reason=row.reason,receipt=snap)
   if 'mapping_changed_or_missing' in row.reason or row.reason=='unfilled_open_mapping_rollover':
    currentmap=mapix.loc[(row.date,product),'main_contract_vt'] if (row.date,product) in mapix.index else ''
    ck('mapping_cancel_current_invalid',currentmap!=row.vt_symbol,[row.date,row.vt_symbol,currentmap])
   if row.reason=='existing_lifecycle_new_open_cutoff':ck('pending_cancel_cutoff',row.date>=deadline[row.vt_symbol])
for sid,item in preserved.items():
 if sid in receipt_by_id:
  fill=fill_by_id[sid];ck('preserved_later_fill_same_receipt',canonical(item['receipt'])==canonical(receipt_by_id[sid]) and fill.date>max(item['dates']),sid)
  currentmap=mapix.loc[(fill.date,item['receipt']['product_vt_symbol']),'main_contract_vt'] if (fill.date,item['receipt']['product_vt_symbol']) in mapix.index else ''
  ck('preserved_later_fill_current_map',currentmap==fill.vt_symbol,sid)
ck('pending_summary_count',summary['pending_open_lifecycle_events']==len(pending))
R['pending_lifecycle']=dict(event_counts=dict(trace_counts),unique_preserved_receipts=len(preserved),preserved_eventual_fills=sum(sid in receipt_by_id for sid in preserved),unique_cancelled_receipts=len(cancelled085),cached_dispatch_rows=len(dispatches),cached_dispatch_examples=dispatches[:10],limitation='Exports bind original receipt identities, observed preserve/cancel/dispatch transitions and factual fills. Full private funding candidate books and every intermediate cluster-PnL mutation are not exported; actual funding floors/MTM checked independently, dynamic pending funding/PnL scope additionally supported by frozen-code review and 83 synthetic oracle checks.')
# Newly exported093 factual/plus-pending funding and cost-basis cluster PnL.
cluster_raw=dict(x.split('=') for x in params['risk_cluster_map'].split(','))
def cluster_of(vt):
 prod=meta.loc[vt,'product_vt_symbol']
 return cluster_raw.get(vt,cluster_raw.get(prod,cluster_raw.get(prod.split('.')[0].lower()+'.'+prod.split('.')[1],'')))
causal_quote_days={v:g.date.tolist() for v,g in market.groupby('vt_symbol',sort=False)}
def causal_close(vt,day):
 ds=causal_quote_days[vt];return float(mktix.loc[(ds[bisect_right(ds,day)-1],vt),'close'])
positions_eod={};fund_errors=[];pnl_errors=[];cluster_errors=[];pending_floors=[]
for day,ar in account.iterrows():
 for x in tradedays.get(day,[]):
  vt=x['vt_symbol'];q=int(x['volume'])
  if x['offset']=='open':
   ck('costbasis_no_add',vt not in positions_eod);positions_eod[vt]=[q,float(x['price']),1 if x['direction']=='long' else -1]
  else:
   positions_eod[vt][0]-=q
   if positions_eod[vt][0]==0:del positions_eod[vt]
 factual=defaultdict(float);pnl=defaultdict(float)
 for vt,(q,ep,sign) in positions_eod.items():
  price=causal_close(vt,day);size=float(meta.loc[vt,'size']);cl=cluster_of(vt)
  factual[cl]+=q*price*size*float(meta.loc[vt,'margin_ratio']);pnl[cl]+=q*(price-ep)*size*sign
 actual=sum(factual.values());fund=json.loads(ar.funding_by_cluster_json);pnlsaved=json.loads(ar.actual_pnl_by_cluster_json)
 ck('EOD_actual_margin_exact',near(ar.actual_margin,actual,1e-6),day)
 ck('EOD_funding_sum',near(sum(fund.values()),ar.actual_plus_pending_margin,1e-6),day)
 ck('EOD_funding_actual_floor',float(ar.actual_plus_pending_margin)+1e-6>=actual,day)
 ck('EOD_reserved_funding_floor',float(ar.reserved_margin)+1e-6>=float(ar.actual_plus_pending_margin),day)
 for cl in set(factual)|set(fund):ck('EOD_cluster_actual_floor',fund.get(cl,0.)+1e-6>=factual.get(cl,0.),[day,cl])
 for cl in set(pnl)|set(pnlsaved):
  delta=abs(pnl.get(cl,0.)-pnlsaved.get(cl,0.));pnl_errors.append(delta);ck('EOD_cluster_actual_PnL',delta<1e-6,[day,cl,pnl.get(cl,0.),pnlsaved.get(cl,0.)])
 # All independently observed preserved original intentions still live at EOD.
 terminal=set()
 for x in cancels.loc[cancels.date.eq(day)].itertuples():
  terminal.update(q['snapshot_id'] for q in json.loads(x.receipt_json) if q)
 for x in pending.loc[pending.date.eq(day)&pending.event.eq('cancel')].itertuples():
  terminal.update(q['snapshot_id'] for q in json.loads(x.receipt_json) if q)
 preserve={}
 for x in pending.loc[pending.date.eq(day)&pending.event.eq('preserve')].itertuples():
  q=json.loads(x.receipt_json)
  if q['snapshot_id'] not in terminal:preserve[q['snapshot_id']]=q
 obs=defaultdict(float)
 for q in preserve.values():
  vt=q['contract_vt_symbol'];price=causal_close(vt,day)
  obs[cluster_of(vt)]+=q['authorized_volume']*price*float(meta.loc[vt,'size'])*float(meta.loc[vt,'margin_ratio'])
 for cl in set(obs):ck('EOD_cluster_actual_plus_observed_pending_floor',fund.get(cl,0.)+1e-6>=factual.get(cl,0.)+obs[cl],[day,cl])
 pending_floors.append(float(ar.actual_plus_pending_margin)-actual)
R['actual_funding_and_pnl']=dict(eod_rows=len(account),all_cluster_costbasis_pnl_max_error=max(pnl_errors or [0.]),minimum_pending_funding_above_actual=min(pending_floors),method='Actual full/partial fills and latest causal close independently reconstruct actual margin and cost-basis cluster PnL daily. Funding sums/reserved floors and all observed original-preserve intentions compared against093 exports.',limitation='Complete private fresh intention/order books are not exported: absolute fresh-pending total and every intraday reserved mutation cannot be wholly reconstructed; additive observed pending and actual floors checked, with frozen-source/212 independent preflight oracles covering scoped hooks.')
for yr,detail in R['annual'].items():
 g=daily.loc[daily.date.str[:4].eq(yr)];t=tr.loc[tr.date.str[:4].eq(yr)];v=g.equity.astype(float)
 detail.update(return_pct=(detail['end_equity']/detail['start_equity']-1)*100,commission=float(t.commission.sum()),slippage=float(t.slippage.sum()),fills=len(t),path_drawdown_min_pct=float((v/v.cummax()-1).min()*100))
# Reconstruct all deferred attempts against real complete-bar volume, no synthetic fills.
deferred=read(C,'deferred_orders');blocked=read(C,'blocked_open_orders')
for x in deferred.itertuples():
 bar=mktix.loc[(x.date,x.vt_symbol)] if (x.date,x.vt_symbol) in mktix.index else None
 ck('deferred_actual_quantity_positive',float(x.volume)>0 and int(x.volume)==float(x.volume),[x.date,x.order_id])
 ck('deferred_not_executable_full_quantity',bar is None or float(bar.volume)<int(x.volume),[x.date,x.order_id,x.reason])
R['deferred_execution']=dict(attempts=len(deferred),reason_counts=deferred.reason.value_counts().to_dict(),blocked_open_attempts=len(blocked),blocked_reasons=blocked.reason.value_counts().to_dict(),all_actual_fills_have_full_volume=True)
for field,expected in [('payoff_ratio',R['stats']['net_payoff_ratio']),('profit_factor',R['stats']['net_profit_factor'])]:ck('summary_'+field,near(summary[field],expected,1e-7))
R['review_audit_script_sha256']=sha(Path(__file__))

for key,expected in [('end_balance',R['stats']['ending_equity']),('max_ddpercent',R['stats']['max_dd_pct']),('total_return',R['stats']['return_pct']),('sharpe_ratio',R['stats']['sharpe_240_log']),('total_commission',R['stats']['commission']),('total_slippage',R['stats']['slippage']),('win_rate_pct',R['stats']['win_rate_pct'])]:
 ck('summary_stat_'+key,near(summary[key],expected,1e-6),[summary[key],expected])
for field,calc in [('equity',eq),('balance',eq),('drawdown',eq-eq.cummax()),('ddpercent',dd)]:
 if field in daily:ck('daily_native_'+field,np.max(np.abs(daily[field]-calc))<1e-6)
log=(C/'engine.log').read_text();ck('no_caught_engine_exception',not any(word in log for word in ['Traceback (most recent call last)','触发异常','Exception triggered','unresolved_lifecycle_position']))

R['errors']=errors;R['error_count']=len(errors);R['financial_replays']=0;R['source_immutable']=True
Path('/private/tmp/stage100_no_weekly_actual_result.json').write_text(json.dumps(dump(R),ensure_ascii=False,indent=2))
print(json.dumps(dump({k:v for k,v in R.items() if k not in ['findings','errors']}),ensure_ascii=False,indent=2));print('ERRORS',len(errors));print(json.dumps(errors[:20],ensure_ascii=False,indent=2))
