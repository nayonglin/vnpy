from pathlib import Path
import json,hashlib
from datetime import datetime
from zoneinfo import ZoneInfo
L=Path(__file__).resolve().parents[1];S=L/'stages'
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for c in iter(lambda:f.read(4194304),b''):h.update(c)
 return h.hexdigest()
def load(p):return json.loads(Path(p).read_text())
first=S/'stage004_delivery_manifest.json';r=load(first);files=dict(r['files_sha256'])
assert all(sha(p)==h for p,h in files.items())
reconcile=S/'stage004_visual_review_reconciliation.json';v=load(reconcile)
assert (S/'stage004_visual_review_reconciliation.md').is_file()
assert load(S/'stage004_independent_final.json')['status']=='PASS_WITH_LIMITATIONS'
for p in [first,*S.glob('*stage004*'),*L.joinpath('tools').glob('*stage004*'),*L.joinpath('artifacts').glob('*stage004*')]:
 if p.is_file():files[str(p)]=sha(p)
assert all(sha(p)==h for p,h in files.items())
out=S/'stage004_delivery_manifest_v2.json';assert not out.exists()
out.write_text(json.dumps(dict(schema='stage004_delivery_v2',accepted=True,created_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),review_status='PASS_WITH_LIMITATIONS',promotion_decision='NO_PROMOTION',production_qualified=False,financial_replays=1,market_downloads=0,first_delivery_superseded_for_visual_review_binding=True,visual_reconciliation=str(reconcile),files_sha256=files,self_hash_excluded=True),ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(accepted=True,bound_files=len(files),manifest=str(out),sha256=sha(out))))
