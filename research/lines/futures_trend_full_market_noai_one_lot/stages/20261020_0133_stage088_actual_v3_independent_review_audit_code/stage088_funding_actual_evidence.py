from pathlib import Path
from collections import defaultdict,Counter
import pandas as pd,numpy as np,json,hashlib,math
ROOT=Path('/Users/mac/.codex/worktrees/full-market-noai-one-lot/fian');P=ROOT/'research/lines/futures_trend_full_market_noai_one_lot/outputs/run_20261020_contract_weekly_risk05_v3'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert sha(P/'manifest.json')=='f2fb3b9d17621ab5d9d64001238b305fbf9fb4fd3dd8fa72432bc0a3955f6860'
def rd(n):return pd.read_csv(P/(n+'.csv'),keep_default_na=False,float_precision='round_trip')
m=rd('market_daily');meta=rd('contract_metadata').set_index('vt_symbol');a=rd('account_snapshots').set_index('date');r=rd('entry_risk');events=rd('pending_open_lifecycle_events');t=rd('trades');aud=rd('open_budget_audit');c=rd('unfilled_intent_cancellations');errors=[]
ck=lambda n,v,d=None:errors.append(dict(check=n,detail=d)) if not v else None
prices={vt:g.set_index('date').close.to_dict() for vt,g in m.groupby('vt_symbol')};dates={vt:sorted(g) for vt,g in prices.items()};from bisect import bisect_right
def close(vt,day):
 ds=dates[vt];i=bisect_right(ds,day)-1;assert i>=0;return float(prices[vt][ds[i]])
par=json.loads((P/'manifest.json').read_text())['parameters'];cluster_raw=dict(x.split('=') for x in par['risk_cluster_map'].split(','))
def cluster(vt):
 prod=meta.loc[vt,'product_vt_symbol'];return cluster_raw.get(vt,cluster_raw.get(prod,cluster_raw.get(prod.split('.')[0].lower()+'.'+prod.split('.')[1],'')))
# Factual cost-basis PnL from actual OPEN/partial CLOSE only, never signal layers.
active={};actual_margin={};true_pnl={};pnl_by_cluster={};fills={d:g for d,g in t.groupby('date')}
for day,ar in a.iterrows():
 for x in fills.get(day,pd.DataFrame()).itertuples():
  if x.offset=='open':assert x.vt_symbol not in active;active[x.vt_symbol]=[int(x.volume),float(x.price),1 if x.direction=='long' else -1]
  else:
   active[x.vt_symbol][0]-=int(x.volume)
   if active[x.vt_symbol][0]==0:del active[x.vt_symbol]
 real=json.loads(ar.positions);ck('active_actual_qty',real=={v:q*sgn for v,(q,price,sgn) in active.items()},day)
 usage=defaultdict(float);pnl=defaultdict(float)
 for vt,(q,ep,sgn) in active.items():
  price=close(vt,day);size=float(meta.loc[vt,'size']);usage[cluster(vt)]+=q*price*size*float(meta.loc[vt,'margin_ratio']);pnl[cluster(vt)]+=q*(price-ep)*size*sgn
 actual_margin[day]=sum(usage.values());true_pnl[day]=sum(pnl.values());pnl_by_cluster[day]=dict(pnl)
 ck('account_actual_margin_floor',float(ar.margin)+1e-6>=actual_margin[day],day)
# All observed preserved intentions are independently additive to actual funds.
# Exclude any same-day terminal cancellation (could occur before another sizing).
terminal=set()
for x in c.itertuples():
 for q in json.loads(x.receipt_json):
  if q:terminal.add((x.date,q['snapshot_id']))
for x in events[events.event.eq('cancel')].itertuples():
 for q in json.loads(x.receipt_json):
  if q:terminal.add((x.date,q['snapshot_id']))
pres=defaultdict(dict)
for x in events[events.event.eq('preserve')].itertuples():
 q=json.loads(x.receipt_json)
 if (x.date,q['snapshot_id']) not in terminal:pres[x.date][q['snapshot_id']]=q
fund_checks=[];cluster_checks=[];minhead=float('inf');minequity=float('inf');maxeqerr=0.
for x in r.itertuples():
 actual=actual_margin[x.date];extra=sum(q['authorized_volume']*close(q['contract_vt_symbol'],x.date)*float(meta.loc[q['contract_vt_symbol'],'size'])*float(meta.loc[q['contract_vt_symbol'],'margin_ratio']) for q in pres.get(x.date,{}).values())
 head=float(x.total_margin_in_use_before)-(actual+extra);minhead=min(minhead,head);ck('entry_factual_plus_preserved_margin_floor',head>=-1e-6,[x.date,x.contract_vt_symbol,float(x.total_margin_in_use_before),actual,extra])
 eqerr=abs(float(x.estimated_equity)-float(a.loc[x.date,'strategy_equity']));maxeqerr=max(maxeqerr,eqerr);ck('entry_estimated_equity_factual',eqerr<1e-5,[x.date,x.contract_vt_symbol,eqerr])
 if extra:fund_checks.append(dict(date=x.date,contract=x.contract_vt_symbol,actual_margin=actual,preserved_margin=extra,reported_reserved=float(x.total_margin_in_use_before),headroom=head))
 cl=cluster(x.contract_vt_symbol)
 if int(x.risk_cluster_cap_enabled):
  actualcl=sum(abs(q)*close(v,x.date)*float(meta.loc[v,'size'])*float(meta.loc[v,'margin_ratio']) for v,q in json.loads(a.loc[x.date,'positions']).items() if cluster(v)==cl)
  extracl=sum(q['authorized_volume']*close(q['contract_vt_symbol'],x.date)*float(meta.loc[q['contract_vt_symbol'],'size'])*float(meta.loc[q['contract_vt_symbol'],'margin_ratio']) for q in pres.get(x.date,{}).values() if cluster(q['contract_vt_symbol'])==cl)
  # Rollover cap can intentionally project release of its own same-product old leg;
  # total factual funding is checked above, so inspect and report rather than
  # incorrectly imposing a different cap contract on the native planning field.
  if float(x.risk_cluster_reserved_margin_before)+1e-6<actualcl+extracl:cluster_checks.append(dict(date=x.date,contract=x.contract_vt_symbol,context=x.entry_context,reported=float(x.risk_cluster_reserved_margin_before),actual=actualcl,preserved=extracl))
ck('effective_heatgate_off',(r.risk_cluster_heat_gate_enabled.astype(int)==0).all())
R=dict(source_manifest_sha256=sha(P/'manifest.json'),audit_script_sha256=sha(__file__),financial_replays=0,entry_diagnostics_checked=len(r),entry_factual_plus_observed_preserved_checks=len(fund_checks),minimum_global_margin_headroom=minhead,entry_equity_max_error=maxeqerr,funding_examples=fund_checks[:15],cap_projection_below_factual_cases=cluster_checks,factual_cluster_pnl_days=len(pnl_by_cluster),factual_cluster_pnl_min=min(true_pnl.values()),factual_cluster_pnl_max=max(true_pnl.values()),effective_heatgate_all_diagnostics_off=bool((r.risk_cluster_heat_gate_enabled.astype(int)==0).all()),open_rejection_reasons=aud.loc[~aud.filled.astype(str).str.lower().eq('true'),'reason'].value_counts().to_dict(),limits=['Actual EOD PnL and margin reconstructed from fills. Private daily cluster-PnL cache and complete unfilled books are not exported, so their full intermediate values cannot be independently compared; observed preserved funds plus actual positions checked on all entry diagnostics; frozen code and independent scoped oracle cover remaining hooks.'],errors=errors,error_count=len(errors))
Path('/private/tmp/stage088_funding_actual_evidence.json').write_text(json.dumps(R,ensure_ascii=False,indent=2));print(json.dumps(R,ensure_ascii=False,indent=2))
