"""Sign only independently audited canary checkpoints; never run finance."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib,json
L=Path(__file__).resolve().parents[1];B=L/'outputs/stage008_multistart';S=L/'stages';R=S/'stage008_independent_receipts'
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(8388608),b''):h.update(b)
 return h.hexdigest()
def main():
 out=S/'stage008_canary_independent_review.json'
 if out.exists():raise ValueError('immutable_canary_approval_exists')
 freeze=S/'stage008_freeze.json';f=json.loads(freeze.read_text());freeze_sha=sha(freeze);reg=json.loads((B/'registry.json').read_text());assert reg['freeze_sha256']==freeze_sha
 reuse=S/'stage008_independent_reuse.json';reuse_doc=json.loads(reuse.read_text());assert reuse_doc['accepted'] is True and reuse_doc['freeze_sha256']==freeze_sha
 for v in reuse_doc['receipts'].values():assert sha(v['receipt'])==v['receipt_sha256']
 checkpoints={};receipts={};metrics={};checks={};auditor=L/'tools/stage008_independent_window.py'
 for arm in ['A','C']:
  key='2015-06-01|'+arm;job=reg['jobs'][key];assert job['status']=='validated'
  cp=(B/'checkpoints'/f'2015-06-01_{arm}.json').resolve();c=json.loads(cp.read_text());rp=R/f'2015-06-01_{arm}.json';r=json.loads(rp.read_text())
  assert r['status']=='PASS_WITH_LIMITATIONS' and r['failures']==r['P0']==r['P1']==r['P2']==0 and r['freeze_sha256']==freeze_sha and r['arm']==arm and r['requested_start']=='2015-06-01' and r['end']==f['cutoff']
  assert r['source_files_sha256']==c['files_sha256'] and r['auditor_source_sha256']==sha(auditor) and r['cold_start_warmup_evidence']['first_equity']==150000 and r['cold_start_warmup_evidence']['first_day_financial_positions']==0
  for p,h in c['files_sha256'].items():assert Path(p).is_file() and sha(p)==h,p
  checkpoints[str(cp)]=sha(cp);receipts[str(rp)]=sha(rp);metrics[arm]=r['metrics'];checks[arm]=r['checks']
 log=S/'stage008_independent_runner_tests.log';text=log.read_text();assert 'Ran 18 tests' in text and text.strip().endswith('OK')
 result=dict(accepted=True,status='PASS_CANARY_ACCOUNTING_AND_DATA_WITH_LIMITATIONS',canary_start='2015-06-01',end=f['cutoff'],freeze_sha256=freeze_sha,source_head=f['source_head'],checkpoints_sha256=checkpoints,independent_receipts_sha256=receipts,reused_full_period_acceptance_sha256=sha(reuse),auditor_source_sha256=sha(auditor),stream_source_sha256=sha(L/'tools/stage008_independent_stream_v2.py'),reviewed_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),P0=0,P1=0,P2=0,checks=checks,independent_tests_passed=18,metrics=metrics,financial_replays=0,market_downloads=0,production_accesses=0,scope='Permit remaining frozen40 new replays only; economic victory is not a canary accounting gate; no final robustness verdict or promotion.',limitations=['23 overlapping start-to-now windows are not independent samples or OOS.','Zero commission, static margin x1.65, incomplete listing-history and PIT/lifecycle/data limitations remain.'])
 out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(path=str(out),sha256=sha(out),checks=checks,status=result['status']),ensure_ascii=False))
if __name__=='__main__':main()
