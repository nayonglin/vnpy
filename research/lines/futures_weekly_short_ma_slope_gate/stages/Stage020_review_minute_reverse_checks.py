"""Reverse-check qualified15m CSV against approved daily without qualification code."""
from pathlib import Path
import hashlib,json
import numpy as np
import pandas as pd
D=Path(__file__).resolve().parent;P=Path('/Users/mac/.codex/worktrees/weekly-short-ma-slope-20261029/fian/research/lines/futures_weekly_short_ma_slope_gate/outputs/data_stage014_20261030/data_approved');sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();p=pd.read_csv(P/'physical_epoch_daily.csv').set_index(['vt_symbol','date']);mapping=pd.read_csv(P/'mapping.csv');calendars={};results=[]
for suffix,name in [('', 'Stage020_review_qualified_15m.csv'),('_v2','Stage020_review_qualified_15m_warmup.csv')]:
 f=pd.read_csv(D/name);checks=0
 for (s,d),g in f.groupby(['vt_symbol','trading_day']):
  g=g.sort_values('bar_datetime');wanted=p.loc[(s,d)];actual=[g.open.iloc[0],g.high.max(),g.low.min(),g.close.iloc[-1],g.volume.sum(),g.close_oi.iloc[-1]];assert np.allclose(actual,wanted[['open','high','low','close','volume','close_oi']].to_numpy(dtype=float),rtol=0,atol=1e-7);checks+=1
  if s not in calendars:
   sym,ex=s.split('.');prod=''.join(c for c in sym if c.isalpha());calendars[s]=pd.DatetimeIndex(sorted(set(mapping.loc[mapping['product'].str.lower().eq(prod.lower())&mapping.exchange.eq(ex),'date'])))
  cal=calendars[s]
  for dt in pd.to_datetime(g.bar_datetime):
   boundary=dt.normalize()+pd.Timedelta(days=int(dt.hour>=18));assert str(cal[cal.searchsorted(boundary)].date())==d;assert dt.second==0 and dt.minute%15==0;checks+=1
 assert not f.duplicated(['vt_symbol','bar_datetime']).any()
 results.append(dict(csv=name,sha256=sha(D/name),unique_contract_days=f.groupby(['vt_symbol','trading_day']).ngroups,bar_rows=len(f),checks=checks))
result=dict(accepted=True,status='PASS',scope='Reverse daily OHLCVOI aggregation and each actual15m timestamp/day boundary; no download or engine',results=results,physical_sha256=sha(P/'physical_epoch_daily.csv'),mapping_sha256=sha(P/'mapping.csv'))
out=D/'Stage020_review_minute_reverse_checks.json';out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result))
