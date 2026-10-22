"""只读已冻结完整分钟CSV，整理首分钟候选；冲突键全拒绝，不替换原缓存。"""
from pathlib import Path
import hashlib,json
import pandas as pd,numpy as np
ROOT=Path(__file__).resolve().parents[4];SOURCE=Path('/Users/mac/Desktop/fian');LINE=ROOT/'research/lines/futures_weekly_formal_no_half_r';OUT=LINE/'outputs/stage003_anchor_catalog'
VALUES=['open','high','low','close','volume','open_oi','close_oi']
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def main():
 OUT.mkdir(exist_ok=True)
 if (OUT/'manifest.json').exists():raise ValueError('catalog_exists')
 frozen=json.loads((SOURCE/'research/lines/futures_trend_rollover_shape_same_volume/outputs/stage251_half_r_ab/C_final/input_manifest.json').read_text())
 pieces=[];sources={};excluded=[]
 for p in sorted((SOURCE/'examples/portfolio_backtesting/downloaded_futures').glob('*/*/*_completed_minute_backtest.csv')):
  key=str(p.relative_to(SOURCE));digest=frozen.get(key)
  if not digest or sha(p)!=digest:excluded.append(str(p));continue
  sources[str(p)]=digest
  for frame in pd.read_csv(p,usecols=['vt_symbol','bar_datetime',*VALUES],chunksize=100000):
   selected=frame.loc[frame.bar_datetime.astype(str).str[11:16].isin(['09:00','21:00'])].copy()
   if len(selected):selected['source_path']=str(p);pieces.append(selected)
 data=pd.concat(pieces,ignore_index=True);data['bar_datetime']=pd.to_datetime(data.bar_datetime)
 price=data[['open','high','low','close']]
 valid=np.isfinite(data[VALUES].to_numpy(float)).all(axis=1)&price.gt(0).all(axis=1)&data[['volume','open_oi','close_oi']].ge(0).all(axis=1)&data.low.le(price.min(axis=1))&data.high.ge(price.max(axis=1))
 invalid=data.loc[~valid].copy();data=data.loc[valid].copy()
 groups=data.groupby(['vt_symbol','bar_datetime'])[VALUES];conflicts=(groups.max()-groups.min()).gt(1e-8).any(axis=1);badkeys=conflicts.index[conflicts]
 rejected=data.loc[pd.MultiIndex.from_frame(data[['vt_symbol','bar_datetime']]).isin(badkeys)]
 data=data.loc[~pd.MultiIndex.from_frame(data[['vt_symbol','bar_datetime']]).isin(badkeys)].drop_duplicates(['vt_symbol','bar_datetime']).sort_values(['vt_symbol','bar_datetime'])
 data['bar_date']=data.bar_datetime.dt.normalize();data['minute_source']='stage003_frozen_completed_first_minute'
 data.to_csv(OUT/'catalog.csv',index=False);rejected.to_csv(OUT/'conflicting_candidates.csv',index=False);invalid.to_csv(OUT/'invalid_candidates.csv',index=False)
 manifest=dict(kind='frozen_completed_first_minute_catalog',catalog_sha256=sha(OUT/'catalog.csv'),rows=len(data),source_files=sources,excluded_unfrozen_sources=excluded,conflicting_keys=len(badkeys),invalid_rows=len(invalid),source_files_unchanged=all(sha(p)==h for p,h in sources.items()),order_api_calls=0,cancel_api_calls=0)
 (OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in manifest.items() if k not in {'source_files','excluded_unfrozen_sources'}},ensure_ascii=False))
if __name__=='__main__':main()
