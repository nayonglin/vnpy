"""Read-only check for entire absent RQ-positive weeks between consumed stored weeks."""
from pathlib import Path
import csv,json,hashlib,math
from datetime import datetime,timedelta
from collections import defaultdict
import h5py
L=Path(__file__).resolve().parents[1]
P=L/'outputs/stage028_2015_2020_kline_audit/signal_week_inputs.csv'
R=Path('/Users/mac/Desktop/fian/research/lines/futures_trend_rollover_shape_same_volume/outputs/stage265_deep_daily/rqalpha/futures.h5')
O=L/'outputs/stage028_root_whole_week_audit.json'
assert not O.exists()
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(4194304),b''):h.update(b)
 return h.hexdigest()
def monday(s):
 d=datetime.fromisoformat(s).date();return d-timedelta(days=d.weekday())
rows=list(csv.DictReader(P.open()));groups=defaultdict(list)
for r in rows: groups[r['trade_id']].append(r)
raw={};missing=[]
with h5py.File(R,'r') as h:
 for r in rows:
  eid=r['contract_epoch_id']
  if eid in raw:continue
  ex,prod,ym=eid.split('.');key=prod+ym[-4:];weeks=defaultdict(list)
  for i,v in enumerate(h[key][:]):
   s=str(int(v['datetime']))[:8];d=s[:4]+'-'+s[4:6]+'-'+s[6:8]
   prices=[float(v[f]) for f in ['open','high','low','close']]
   if float(v['volume'])>0 and all(math.isfinite(x) and x>0 for x in prices):weeks[monday(d)].append({'date':d,'raw_row_index':i})
  raw[eid]=weeks
for tid,g in groups.items():
 weeks={monday(r['week_end']) for r in g};lo,hi=min(weeks),max(weeks)
 for week,days in raw[g[0]['contract_epoch_id']].items():
  if lo<=week<=hi and week not in weeks:
   missing.append(dict(entry_trade_id=tid,contract_epoch_id=g[0]['contract_epoch_id'],week_monday=week.isoformat(),raw_positive_days=days))
result={'schema':'stage028_root_whole_week_omission_check_v1','actual_entries':len(groups),'physical_contracts':len(raw),'raw_source':'RQ H5 actual real-contract series; exact physical YYYYMM','whole_positive_weeks_omitted_between_consumed_oldest_and_latest_week':len(missing),'omissions':missing,'financial_replays':0,'source_files_sha256':{str(p):sha(p) for p in [P,R,Path(__file__).resolve()]},'boundary':'Only available RQ H5, within each actual entry oldest/latest consumed storage week inclusive; not a second independent source, not pre-oldest weeks, absent all-vendor data or full-calendar PIT proof.'}
O.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:result[k] for k in ['actual_entries','physical_contracts','whole_positive_weeks_omitted_between_consumed_oldest_and_latest_week']}))
