"""Additional read-only actual-native-entry 21 completed-week readiness audit."""
from pathlib import Path
from bisect import bisect_right
import argparse,hashlib,json
import pandas as pd
L=Path(__file__).resolve().parents[1];B=L/'outputs/stage008_multistart';S=L/'stages'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--require-all',action='store_true');ap.add_argument('--output',type=Path,required=True);args=ap.parse_args();fpath=S/'stage008_freeze.json';f=json.loads(fpath.read_text());reg=json.loads((B/'registry.json').read_text());jobs={k:v for k,v in reg['jobs'].items() if v['status']=='validated'}
 if args.require_all:assert len(jobs)==46
 if args.output.exists():raise ValueError('immutable_warmup_evidence_exists')
 results={};total=0;bindings={};failures=[]
 for key,job in sorted(jobs.items()):
  p=Path(job['path']);w=pd.read_csv(p/'weekly_bars.csv',dtype={'contract_epoch_id':str});a=pd.read_csv(p/'execution_anchor_requests.csv',dtype={'order_id':str});t=pd.read_csv(p/'trades.csv',dtype={'order_id':str});c=pd.read_csv(p/'entry_candidates.csv');groups={sym:g.sort_values('week_end') for sym,g in w.groupby('vt_symbol')};counts=[]
  for q in t.loc[t.offset.eq('开')].itertuples():
   anchor=a.loc[a.order_id.eq(q.order_id)];assert len(anchor)==1;day=str(anchor.iloc[0].signal_date)[:10];side={'多':'long','空':'short'}[q.direction];native=c.loc[c.date.astype(str).str[:10].eq(day)&c.contract_vt_symbol.eq(q.vt_symbol)&c.direction.eq(side)&c.candidate_status.eq('opened')]
   if native.empty:continue
   g=groups[q.vt_symbol];prefix=g.loc[g.week_end.le(day)];last=prefix.iloc[-1];epoch=last.contract_epoch_id;same=prefix.loc[prefix.contract_epoch_id.eq(epoch)];n=len(same);counts.append(n);total+=1
   if n<21 or str(last.week_end)!=day:failures.append(dict(key=key,trade_id=q.trade_id,vt_symbol=q.vt_symbol,signal_date=day,accepted_week_count=n,last_accepted_week_end=last.week_end,epoch=epoch))
  results[key]=dict(actual_native_fills=len(counts),minimum_same_epoch_accepted_weeks=min(counts) if counts else None)
  bindings[str(p/'weekly_bars.csv')]=sha(p/'weekly_bars.csv');bindings[str(p/'execution_anchor_requests.csv')]=sha(p/'execution_anchor_requests.csv');bindings[str(p/'entry_candidates.csv')]=sha(p/'entry_candidates.csv');bindings[str(p/'trades.csv')]=sha(p/'trades.csv')
 r=dict(status='PASS_ACTUAL_NATIVE21_COMPLETED_WEEK_READINESS' if not failures else 'FAIL',freeze_sha256=sha(fpath),window_count=len(jobs),actual_native_fills_checked=total,results=results,failures=failures,source_files_sha256=bindings,auditor_source_sha256=sha(Path(__file__)),financial_replays=0,market_downloads=0);args.output.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in r.items() if k not in ['source_files_sha256','results']},ensure_ascii=False));assert not failures
if __name__=='__main__':main()
