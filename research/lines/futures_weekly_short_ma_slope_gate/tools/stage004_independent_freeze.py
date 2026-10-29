"""Read-only source checkpoint before the Stage004 single declared rule change."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib,json
ROOT=Path(__file__).resolve().parents[4];L=ROOT/'research/lines/futures_weekly_short_ma_slope_gate'
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for c in iter(lambda:f.read(8*1024*1024),b''):h.update(c)
 return h.hexdigest()
counts={};snapshots={}
for n in ['stage001_delivery_manifest.json','stage002_delivery_manifest.json','stage003_delivery_manifest.json']:
 p=L/'stages'/n;m=json.loads(p.read_text());bad=[q for q,h in m['files_sha256'].items() if not Path(q).is_file() or sha(q)!=h];assert not bad,(n,bad);counts[n]=len(m['files_sha256']);snapshots[str(p)]=sha(p)
data=L/'outputs/data_stage001_20261029/data_approved';m=json.loads((data/'source_manifest.json').read_text())['files'];bad=[q for q,h in m.items() if not Path(q).is_file() or sha(q)!=h];assert not bad,bad;receipt=json.loads((data/'receipt.json').read_text());assert receipt['date_end']=='2026-10-29' and receipt['data_ready'] and receipt['data_ready_for_bounded_replay'];assert len(receipt['products'])==19
r=dict(status='PASS_FROZEN_SOURCE_CHECKPOINT',time=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),frozen_delivery_binding_counts=counts,frozen_manifest_sha256=snapshots,data_source_bindings=len(m),data_cutoff=receipt['date_end'],original19_count=19,market_downloads=0,financial_replays=0,production_accesses=0,limitations='Source checkpoint only; Stage004 strategy and actual financial result review pending.')
(L/'stages/stage004_independent_freeze.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps(r,ensure_ascii=False))
