"""Frozen sources/data checkpoint; no strategy replay or new market reads."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib,json
import pandas as pd
import numpy as np
ROOT=Path(__file__).resolve().parents[4];L=ROOT/'research/lines/futures_weekly_short_ma_slope_gate';DATA=L/'outputs/data_stage001_20261029/data_approved'
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for c in iter(lambda:f.read(8*1024*1024),b''):h.update(c)
 return h.hexdigest()
counts={};manifests={}
for n in ['stage001_delivery_manifest.json','stage002_delivery_manifest.json','stage003_delivery_manifest.json','stage004_delivery_manifest.json','stage004_delivery_manifest_v2.json']:
 p=L/'stages'/n;d=json.loads(p.read_text());bound=d['files_sha256'];bad=[q for q,h in bound.items() if not Path(q).is_file() or sha(q)!=h];assert not bad,(n,bad);counts[n]=len(bound);manifests[str(p)]=sha(p)
bound=json.loads((DATA/'source_manifest.json').read_text())['files'];bad=[q for q,h in bound.items() if not Path(q).is_file() or sha(q)!=h];assert not bad,bad
f=pd.read_csv(DATA/'physical_epoch_daily.csv');cols=['open','high','low','close','volume'];a=f[cols].to_numpy(float);assert np.isfinite(a).all() and (a>0).all();assert (f.high>=f[['open','low','close']].max(axis=1)).all() and (f.low<=f[['open','high','close']].min(axis=1)).all();assert not f.duplicated(['vt_symbol','date']).any();assert f.date.max()=='2026-10-29'
can=pd.read_csv(L/'outputs/stage001_A_attempt003/entry_candidates.csv');can=can.loc[can.signal.eq('short_case1a')];rows=[]
for c in can.itertuples():
 day=str(c.date)[:10];match=f.loc[f.vt_symbol.eq(c.contract_vt_symbol)&f.date.eq(day)];assert len(match)==1;r=match.iloc[0];ep=f.loc[f.vt_symbol.eq(c.contract_vt_symbol)&f.contract_epoch_id.eq(r.contract_epoch_id)&f.date.le(day)];low=float(ep.low.min());high=float(ep.high.max());price=float(r.close);rows.append(dict(signal_date=day,vt_symbol=c.contract_vt_symbol,contract_epoch_id=r.contract_epoch_id,history_bar_count=len(ep),history_start=ep.date.min(),history_end=ep.date.max(),range_low=low,range_high=high,signal_close=price,threshold_price=low+.2*(high-low),would_block=price<=low+.2*(high-low)))
assert len(rows)==65
result=dict(status='PASS_BOUNDED_SOURCE_DATA_PREFLIGHT',time=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),frozen_delivery_binding_counts=counts,frozen_manifest_sha256=manifests,data_bindings=len(bound),physical_daily_valid_rows=len(f),data_cutoff='2026-10-29',baseline_short_candidates=65,baseline_full_available_epoch_prefixes=rows,history_completeness='Available approved same-epoch daily history only; complete listing-to-signal coverage not independently proven.',financial_replays=0,market_downloads=0,production_accesses=0)
(L/'stages/stage005_independent_preflight.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ['baseline_full_available_epoch_prefixes','frozen_manifest_sha256']},ensure_ascii=False))
