"""Independent EOD actual + every original unfilled-intent book; no financial algo import."""
from pathlib import Path
from collections import defaultdict
from bisect import bisect_right
import json,hashlib,math
import pandas as pd
P=Path('/Users/mac/.codex/worktrees/full-market-noai-one-lot/fian/research/lines/futures_trend_full_market_noai_one_lot/outputs/run_20261020_risk025_contract_weekly_v1')
EXPECTED_MANIFEST_SHA256='7614f09d8dab584fae901901bfafc6dae7f72bca1beba4b6193195642f323d35'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
if not (P/'manifest.json').exists() or not EXPECTED_MANIFEST_SHA256 or sha(P/'manifest.json')!=EXPECTED_MANIFEST_SHA256:raise SystemExit('Need trusted completed enabled manifest.')
manifest=json.loads((P/'manifest.json').read_text());assert manifest['weekly_filter']=='enabled' and manifest['fractional_risk_policy']['risk_fraction']==.0025
errors=[]
def ck(n,v,d=None):
 if not v:errors.append(dict(check=n,detail=d))
def rd(n):
 try:return pd.read_csv(P/(n+'.csv'),keep_default_na=False,float_precision='round_trip')
 except pd.errors.EmptyDataError:return pd.DataFrame()
def flag(v):return str(v).lower()=='true'
meta=rd('contract_metadata').set_index('vt_symbol');market=rd('market_daily');daily=rd('daily');account=rd('account_snapshots').set_index('date');diag=rd('entry_risk');tr=rd('trades');aud=rd('open_budget_audit');events=rd('pending_open_lifecycle_events');forced=rd('unfilled_intent_cancellations');weekly=rd('weekly_execution_audit');dead=rd('lifecycle_deadlines').set_index('vt_symbol');cal=rd('trading_calendar').date.tolist();ix={d:i for i,d in enumerate(cal)}
price={v:g.set_index('date').close.to_dict() for v,g in market.groupby('vt_symbol')};dates={v:sorted(g) for v,g in price.items()}
def mark(v,d):
 ds=dates[v];j=bisect_right(ds,d)-1
 if j<0:raise AssertionError(('no causal mark',v,d))
 return float(price[v][ds[j]])
mp=dict(x.split('=') for x in manifest['parameters']['risk_cluster_map'].split(','))
def cluster(v):
 p=meta.loc[v,'product_vt_symbol'];return mp.get(v,mp.get(p,mp.get(p.split('.')[0].lower()+'.'+p.split('.')[1],'')))
def key_snap(q):return (q['signal_datetime'][:10],q['contract_vt_symbol'],q['direction'],q['signal'])
entries={};terminal=defaultdict(list)
for x in diag.to_dict('records'):
 k=(x['date'],x['contract_vt_symbol'],x['direction'],x['signal']);ck('unique_original_entry_diagnostic',k not in entries,k);entries[k]=x
for x in tr.to_dict('records'):
 if x['offset']=='open':terminal[key_snap(json.loads(x['stage068_signal_snapshot']))].append((x['date'],'actual_fill'))
for x in aud.to_dict('records'):
 q=json.loads(x['signal_snapshot'])
 if q:terminal[key_snap(q)].append((x['date'],'budget_attempt_terminal'))
 if not q:ck('no_unbound_budget_intent',False,[x['date'],x['vt_symbol'],x['reason']])
for x in forced.to_dict('records'):
 for q in json.loads(x['receipt_json']):
  if q:terminal[key_snap(q)].append((x['date'],'forced_cancel'))
for x in events.to_dict('records'):
 if x['event']=='cancel':
  for q in json.loads(x['receipt_json']):
   if q:terminal[key_snap(q)].append((x['date'],'lifecycle_cancel'))
for x in weekly.to_dict('records'):
 if not flag(x['weekly_allowed']):
  candidates=[k for k in entries if k[:3]==(x['original_signal_date'],x['vt_symbol'],'long')]
  ck('weekly_reject_binds_original_entry',len(candidates)==1,[x['date'],x['vt_symbol']])
  if len(candidates)==1:terminal[candidates[0]].append((x['date'],'weekly_cancel'))
for k,v in terminal.items():
 ck('terminal_binds_original_entry',k in entries,k);ck('single_terminal_date',len({x[0] for x in v})==1,[k,v])
# Original intention exists EOD from signal creation through session before its
# factual fill/cancel. No reauthorization or partial authorization is invented.
pending=defaultdict(dict);unterminated=[]
for k,x in entries.items():
 stop=min(v[0] for v in terminal[k]) if terminal.get(k) else None
 if stop is None:unterminated.append(dict(date=k[0],contract=k[1],direction=k[2],signal=k[3],quantity=int(x['volume'])))
 end=min(ix[stop]-1 if stop else ix[daily.date.iloc[-1]],ix[daily.date.iloc[-1]])
 for j in range(ix[k[0]],end+1):
  day=cal[j];pending[day][k]=x
  ck('pending_lifetime_before_deadline',day<dead.loc[k[1],'deadline'],[day,k])
# Reconstruct EOD factual cash positions and entry basis with all partial closes.
active={};fills={d:g.to_dict('records') for d,g in tr.groupby('date')};maxerr=defaultdict(float);pending_days=0;fresh_days=0;maxpending=0.;mixed=[];endpending=[];records=[]
for day,ar in account.iterrows():
 for t in fills.get(day,[]):
  v=t['vt_symbol']
  if t['offset']=='open':ck('actual_entry_once',v not in active,[day,v]);active[v]=[int(t['volume']),float(t['price']),1 if t['direction']=='long' else -1]
  else:
   active[v][0]-=int(t['volume']);ck('partial_close_not_overdrawn',active[v][0]>=0,[day,v])
   if active[v][0]==0:del active[v]
 actual_positions={v:q*s for v,(q,ep,s) in active.items()};ck('actual_eod_positions',actual_positions==json.loads(ar.positions),day)
 funds=defaultdict(float);pnl=defaultdict(float);actualmargin=0.
 for v,(q,ep,s) in active.items():
  size=float(meta.loc[v,'size']);marked=mark(v,day);margin=q*marked*size*float(meta.loc[v,'margin_ratio']);actualmargin+=margin;funds[cluster(v)]+=margin;pnl[cluster(v)]+=q*(marked-ep)*size*s
 pm=fresh=0.
 for k,x in pending.get(day,{}).items():
  v=k[1];margin=int(x['volume'])*mark(v,day)*float(meta.loc[v,'size'])*float(meta.loc[v,'margin_ratio']);pm+=margin;funds[cluster(v)]+=margin
  if k[0]==day:fresh+=margin
  ck('pending_actual_same_contract_zero',v not in active,[day,v])
 total=actualmargin+pm
 values={'actual_margin':actualmargin,'actual_plus_pending_margin':total,'reserved_margin':total,'pending_margin_reservation':fresh}
 for f,want in values.items():
  delta=abs(float(ar[f])-want);maxerr[f]=max(maxerr[f],delta);ck('eod_'+f,delta<1e-6,[day,float(ar[f]),want])
 for field,want in [('funding_by_cluster_json',dict(funds)),('actual_pnl_by_cluster_json',dict(pnl))]:
  got=json.loads(ar[field]);ck('cluster_keys_'+field,set(got)==set(want),[day,got,want])
  for cl in set(got)|set(want):
   delta=abs(float(got.get(cl,0))-float(want.get(cl,0)));maxerr[field]=max(maxerr[field],delta);ck('eod_'+field,delta<1e-6,[day,cl,got.get(cl),want.get(cl)])
 pending_days+=int(pm>0);fresh_days+=int(fresh>0);maxpending=max(maxpending,pm)
 if pm and actualmargin:mixed.append(dict(date=day,actual_margin=actualmargin,pending_margin=pm,total=total,fresh_margin=fresh))
 records.append(dict(date=day,actual_margin=actualmargin,pending_margin=pm,actual_plus_pending_margin=total,reserved_margin=float(ar.reserved_margin),fresh_pending_margin=fresh,actual_gross_unrealized_pnl=sum(pnl.values()),pending_intentions=len(pending.get(day,{}))))
 if day==daily.date.iloc[-1]:endpending=[dict(signal_date=k[0],contract=k[1],direction=k[2],signal=k[3],quantity=int(x['volume'])) for k,x in pending.get(day,{}).items()]
pd.DataFrame(records).to_csv('/private/tmp/stage101_actual_enabled_books_daily.csv',index=False)
R=dict(source_manifest_sha256=sha(P/'manifest.json'),audit_script_sha256=sha(__file__),financial_replays=0,method='All original entry diagnostics partitioned by actual fill/budget or weekly rejection/forced or lifecycle cancellation; EOD pending originals from causal lifetime; factual basis exclusively from actual fills with partial closes. Native financial algorithms not imported.',original_intentions=len(entries),terminal_intentions=len(terminal),unterminated_intentions=unterminated,ending_pending_intentions=endpending,account_days=len(account),pending_days=pending_days,fresh_pending_days=fresh_days,max_pending_margin=maxpending,mixed_actual_pending_days=len(mixed),mixed_examples=mixed[:12],max_abs_errors=dict(maxerr),errors=errors,error_count=len(errors))
Path('/private/tmp/stage101_actual_enabled_books_result.json').write_text(json.dumps(R,ensure_ascii=False,indent=2));print(json.dumps(R,ensure_ascii=False,indent=2))
