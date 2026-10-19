"""Independent original-intent lifetime reconstruction; no strategy imports."""
from pathlib import Path
from collections import defaultdict
from bisect import bisect_right
import pandas as pd
import hashlib,json,math
P=Path('/Users/mac/.codex/worktrees/full-market-noai-one-lot/fian/research/lines/futures_trend_full_market_noai_one_lot/outputs/run_20261020_contract_weekly_risk05_v3')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rd(n):
 try:return pd.read_csv(P/(n+'.csv'),keep_default_na=False,float_precision='round_trip')
 except pd.errors.EmptyDataError:return pd.DataFrame()
m=rd('market_daily');meta=rd('contract_metadata').set_index('vt_symbol');a=rd('account_snapshots').set_index('date');r=rd('entry_risk');t=rd('trades');events=rd('pending_open_lifecycle_events');aud=rd('open_budget_audit');forced=rd('unfilled_intent_cancellations');par=json.loads((P/'manifest.json').read_text())['parameters']
errors=[]
def ck(n,v,d=None):
 if not v:errors.append(dict(check=n,detail=d))
def near(x,y):return abs(float(x)-float(y))<1e-6
cm=dict(x.split('=') for x in par['risk_cluster_map'].split(','))
def cluster(vt):
 p=meta.loc[vt,'product_vt_symbol'];return cm.get(p,cm.get(p.split('.')[0].lower()+'.'+p.split('.')[1].upper(),''))
prices={v:g.set_index('date').close.to_dict() for v,g in m.groupby('vt_symbol')};dates={v:sorted(p) for v,p in prices.items()}
def close(v,day):return float(prices[v][dates[v][bisect_right(dates[v],day)-1]])
def key(q):return (q['signal_datetime'][:10],q['contract_vt_symbol'],q['direction'],q['signal'])
book={}
for x in r.itertuples():
 k=(x.date,x.contract_vt_symbol,x.direction,x.signal);ck('unique_original_entry_intent',k not in book,k)
 book[k]=dict(born=x.date,vt=x.contract_vt_symbol,qty=int(x.volume),terminal=None,terminal_reasons=[])
def end(q,day,reason):
 k=key(q);ck('terminal_bound_original_entry',k in book,[k,day,reason])
 if k not in book:return
 b=book[k];ck('terminal_original_qty',b['qty']==q['authorized_volume'],k)
 if b['terminal'] is None or day<b['terminal']:b['terminal']=day
 b['terminal_reasons'].append([day,reason])
for x in t.loc[t.offset.eq('open')].itertuples():end(json.loads(x.stage068_signal_snapshot),x.date,'actual_OPEN')
for x in aud.loc[~aud.filled.astype(str).str.lower().eq('true')].itertuples():
 q=json.loads(x.signal_snapshot)
 if q:end(q,x.date,'open_rejected:'+x.reason)
for x in forced.itertuples():
 for q in json.loads(x.receipt_json):
  if q:end(q,x.date,'forced_intent_cancel')
for x in events.loc[events.event.eq('cancel')].itertuples():
 for q in json.loads(x.receipt_json):
  if q:end(q,x.date,'lifecycle_cancel:'+x.reason)
# Actual broker fills are the sole factual-position source.
active={};tradedays={d:g for d,g in t.groupby('date')};maxerr=defaultdict(float);examples=[];endintent=[]
for day,row in a.iterrows():
 for x in tradedays.get(day,pd.DataFrame()).itertuples():
  vt=x.vt_symbol
  if x.offset=='open':ck('actual_no_add',vt not in active,[day,vt]);active[vt]=[int(x.volume),float(x.price),1 if x.direction=='long' else -1]
  else:
   active[vt][0]-=int(x.volume)
   if not active[vt][0]:del active[vt]
 actual=defaultdict(float);pnl=defaultdict(float)
 for vt,(qty,ep,sgn) in active.items():
  price=close(vt,day);size=float(meta.loc[vt,'size']);cl=cluster(vt)
  actual[cl]+=qty*price*size*float(meta.loc[vt,'margin_ratio']);pnl[cl]+=qty*(price-ep)*size*sgn
 pending=defaultdict(float);fresh=0.;pend=[]
 for b in book.values():
  if b['born']<=day and (b['terminal'] is None or day<b['terminal']):
   vt=b['vt'];amount=b['qty']*close(vt,day)*float(meta.loc[vt,'size'])*float(meta.loc[vt,'margin_ratio']);pending[cluster(vt)]+=amount;pend.append(b)
   if b['born']==day:fresh+=amount
 expect=dict(actual)
 for cl,v in pending.items():expect[cl]=expect.get(cl,0.)+v
 got=json.loads(row.funding_by_cluster_json);pgot=json.loads(row.actual_pnl_by_cluster_json)
 for cl in set(expect)|set(got):
  delta=abs(expect.get(cl,0.)-got.get(cl,0.));maxerr['funding_cluster']=max(maxerr['funding_cluster'],delta);ck('exact_actual_plus_original_pending_cluster',delta<1e-6,[day,cl,expect.get(cl,0.),got.get(cl,0.)])
 for cl in set(pnl)|set(pgot):
  delta=abs(pnl.get(cl,0.)-pgot.get(cl,0.));maxerr['actual_pnl_cluster']=max(maxerr['actual_pnl_cluster'],delta);ck('exact_actual_costbasis_cluster_PnL',delta<1e-6,[day,cl,pnl.get(cl,0.),pgot.get(cl,0.)])
 for field,val in [('actual_margin',sum(actual.values())),('actual_plus_pending_margin',sum(expect.values())),('reserved_margin',sum(expect.values())),('pending_margin_reservation',fresh)]:
  delta=abs(float(row[field])-val);maxerr[field]=max(maxerr[field],delta);ck('exact_EOD_'+field,delta<1e-6,[day,val,float(row[field])])
 if pending and len(examples)<12:examples.append(dict(date=day,actual_margin=sum(actual.values()),original_pending_margin=sum(pending.values()),fresh_margin=fresh,pending=[dict(vt=b['vt'],qty=b['qty'],born=b['born'],terminal=b['terminal']) for b in pend]))
 if day==a.index[-1]:endintent=pend
R=dict(source_manifest_sha256=sha(P/'manifest.json'),audit_script_sha256=sha(__file__),financial_replays=0,original_entry_intents=len(book),terminal_intents=sum(x['terminal'] is not None for x in book.values()),ending_unfilled_intents=endintent,eod_days=len(a),max_errors=dict(maxerr),examples=examples,errors=errors,error_count=len(errors),method='Entry-risk diagnostics create original signal-keyed intentions; actual OPEN, all opening rejection, forced archived receipts and092 cancellation receipts terminate them. EOD live original-authorized qty added to actual-fill positions. Actual cost-basis PnL, current causal marks, native string cluster identity reconstructed independently; no finance generator/ledger/risk imports.',limitations=['Only exported EOD books and all observed lifetime terminations can be reconstructed, not private intermediate intraday mutation order or forced candidate-ranking input sets.'])
Path('/private/tmp/stage100_parent_funding_reader_probe_result.json').write_text(json.dumps(R,ensure_ascii=False,indent=2));print(json.dumps(R,ensure_ascii=False,indent=2))
