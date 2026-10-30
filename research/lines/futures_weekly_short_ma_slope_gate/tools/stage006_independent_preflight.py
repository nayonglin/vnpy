"""2015 cold-start source/date checkpoint; no finance or market download."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib,json
import pandas as pd
ROOT=Path(__file__).resolve().parents[4];L=ROOT/'research/lines/futures_weekly_short_ma_slope_gate';D=L/'outputs/data_stage001_20261029/data_approved'
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for c in iter(lambda:f.read(8*1024*1024),b''):h.update(c)
 return h.hexdigest()
counts={};manifest_shas={};bounds={}
for n in ['stage001_delivery_manifest.json','stage002_delivery_manifest.json','stage003_delivery_manifest.json','stage004_delivery_manifest.json','stage004_delivery_manifest_v2.json','stage005_delivery_manifest.json']:
 p=L/'stages'/n;rows=json.loads(p.read_text())['files_sha256'];bad=[q for q,h in rows.items() if not Path(q).is_file() or sha(q)!=h];assert not bad,(n,bad);counts[n]=len(rows);manifest_shas[str(p)]=sha(p);bounds.update(rows)
 b=json.loads((D/'source_manifest.json').read_text())['files'];assert all(Path(q).is_file() and sha(q)==h for q,h in b.items())
mapdf=pd.read_csv(D/'mapping.csv');days=sorted(mapdf.date.unique());window=[d for d in days if '2015-01-01'<=d<='2026-10-29'];assert window[0]=='2015-01-05' and window[-1]=='2026-10-29' and len(window)==2871
source=L/'tools/stage005_short_bottom20.py';assert bounds[str(source)]==sha(source)
r=dict(status='PASS_BOUNDED_2015_SOURCE_PREFLIGHT',time=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),old_delivery_binding_counts=counts,old_manifest_sha256=manifest_shas,unchanged_range_module_sha256=sha(source),data_cutoff='2026-10-29',requested_start='2015-01-01',actual_calendar_start=window[0],actual_calendar_end=window[-1],financial_calendar_days=len(window),cached_2014_trading_calendar_days=sum(d.startswith('2014') for d in days),data_receipt_financial_start='2020 legacy experiment tag; not a coverage cutoff',limitations=['A/C must each genuinely start150000/zero inventory in2015; implementation and post-run checks pending.','2014 cache has inherited main/alias/lifecycle gaps;21-ready must remain unchanged, not force all products ready on first day.','Same-epoch range uses all available approved daily history, not proven complete listing history.'],financial_replays=0,market_downloads=0,production_accesses=0)
(L/'stages/stage006_independent_preflight.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in r.items() if k!='old_manifest_sha256'},ensure_ascii=False))
