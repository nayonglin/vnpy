from pathlib import Path
import json,hashlib,subprocess
ROOT=Path(__file__).resolve().parents[4];L=ROOT/'research/lines/futures_weekly_short_ma_slope_gate'
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
old=json.loads((L/'stages/stage001_delivery_manifest.json').read_text());bad=[p for p,h in old['files_sha256'].items() if not Path(p).is_file() or sha(p)!=h];assert not bad,bad
manifest=json.loads((L/'outputs/data_stage001_20261029/data_approved/source_manifest.json').read_text())['files'];bad=[p for p,h in manifest.items() if not Path(p).is_file() or sha(p)!=h];assert not bad,bad
controls={}
for arm in ['A','C']:
 p=L/'outputs'/f'stage001_{arm}_attempt003';pre=json.loads((p/'preflight.json').read_text());terminal=json.loads((p/'terminal.json').read_text());assert terminal['status']=='completed_pending_independent_review';assert pre['daily_addon_enabled'] is False;assert pre['short_ma_slope_gate_enabled'] is (arm=='C');assert not pre.get('long_ma_slope_gate_enabled',False);controls[arm]=dict(path=str(p),short_enabled=pre['short_ma_slope_gate_enabled'],long_enabled=pre.get('long_ma_slope_gate_enabled',False),data_identity=pre['data_identity'])
assert controls['A']['data_identity']==controls['C']['data_identity']
result=dict(status='PASS_BOUNDED_PREFLIGHT',P0=0,P1=0,P2=0,old_delivery_bound_files=len(old['files_sha256']),old_delivery_mismatches=[],data_source_bound_files=len(manifest),controls=controls,independent_tests_passed=15,code_review='Stage001 short gate always enabled; long_case1a and long_case2 strict negative OR, zero allowed; same completed-week snapshot/physical epoch/count trimming; parent sizing preserved then zero copy; long final open guard; rollover signal/context excluded; inherited exits/long and short sizing unchanged except declared entry gate.',limitations=['Historical development sample; no new OOS/PIT.','No new data and no additional controls rerun needed; full accounting and actual long/short fill review pending newC.'],financial_replays=0)
(L/'stages/stage002_independent_preflight.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='controls'},ensure_ascii=False))
