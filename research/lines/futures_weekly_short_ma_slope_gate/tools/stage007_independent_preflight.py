"""Independent Stage007 immutable-input audit; no financial replay."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[4]
L=ROOT/'research/lines/futures_weekly_short_ma_slope_gate'
cache={}
def sha(p):
 p=Path(p)
 if str(p) not in cache:
  h=hashlib.sha256()
  with p.open('rb') as f:
   for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
  cache[str(p)]=h.hexdigest()
 return cache[str(p)]
def main():
 manifests={};counts={};failures=[]
 for name in ['stage001_delivery_manifest.json','stage002_delivery_manifest.json','stage003_delivery_manifest.json','stage004_delivery_manifest.json','stage004_delivery_manifest_v2.json','stage005_delivery_manifest.json','stage006_delivery_manifest.json']:
  p=L/'stages'/name;rows=json.loads(p.read_text())['files_sha256'];counts[name]=len(rows);manifests[str(p)]=sha(p)
  failures.extend(dict(manifest=name,path=q) for q,h in rows.items() if not Path(q).is_file() or sha(q)!=h)
 source=L/'tools/stage005_short_bottom20.py'
 assert sha(source)=='18dd15baf43677974a99b365dd09463b2e4a2336ee377d29182c9ff2e4ce34a9'
 result=dict(status='PASS_FROZEN_INPUTS' if not failures else 'FAIL',frozen_delivery_counts=counts,old_manifest_sha256=manifests,unique_files_checked=len(cache),unchanged_short_gate_sha256=sha(source),failures=failures,financial_replays=0,market_downloads=0)
 (L/'stages/stage007_independent_preflight.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(result,ensure_ascii=False))
 assert not failures
if __name__=='__main__':main()
