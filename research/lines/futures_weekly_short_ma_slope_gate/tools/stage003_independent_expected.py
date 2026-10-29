"""Independent read-only source truth for35 Stage002 applied-block candidate events."""
from pathlib import Path
import json,hashlib,math
import pandas as pd
ROOT=Path(__file__).resolve().parents[4];L=ROOT/'research/lines/futures_weekly_short_ma_slope_gate';RUN=L/'outputs/stage002_C_attempt001';D=L/'outputs/data_stage001_20261029/data_approved'
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for c in iter(lambda:f.read(8*1024*1024),b''):h.update(c)
 return h.hexdigest()
physical=pd.read_csv(D/'physical_epoch_daily.csv');lookup={(r.vt_symbol,r.date):r for r in physical.itertuples()};weeks=pd.read_csv(RUN/'weekly_bars.csv');weeklookup={(r.vt_symbol,r.week_end):r for r in weeks.itertuples()};expected=[]
for direction,baselinearm in [('long','C'),('short','A')]:
 dec=json.loads((RUN/f'{direction}_ma_slope_decisions.json').read_text());selected=[r for r in dec if r['applied_block']];assert len(selected)==(20 if direction=='long' else 15)
 base=L/'outputs'/f'stage001_{baselinearm}_attempt003';can=pd.read_csv(base/'entry_candidates.csv');a=pd.read_csv(base/'execution_anchor_requests.csv');fills=pd.read_csv(base/'trades.csv')
 for g in selected:
  assert g['selected_volume_before']>0 and g['selected_volume_after']==0;key=[g['signal_date'],g['vt_symbol'],direction,g['signal']];src=lookup[(g['vt_symbol'],g['signal_date'])];assert src.volume>0;w=weeklookup[(g['vt_symbol'],g['week_end'])];assert src.contract_epoch_id==w.contract_epoch_id and g['week_end']==g['signal_date'];assert math.isclose(src.close,g['source_week_closes'][-1]);vals=g['source_week_closes'];ma={}
  for n in [5,10]:
   current=sum(vals[-n:])/n;previous=sum(vals[-n-1:-1])/n;assert math.isclose(g[f'ma{n}_current'],current,rel_tol=1e-10);assert math.isclose(g[f'ma{n}_previous'],previous,rel_tol=1e-10);ma[f'ma{n}_delta']=current-previous
  assert (ma['ma5_delta']<0 or ma['ma10_delta']<0) if direction=='long' else (ma['ma5_delta']>0 or ma['ma10_delta']>0)
  c=can.loc[can.date.astype(str).str[:10].eq(g['signal_date'])&can.contract_vt_symbol.eq(g['vt_symbol'])&can.direction.eq(direction)&can.signal.eq(g['signal'])];orders=a.loc[a.signal_date.astype(str).str[:10].eq(g['signal_date'])&a.vt_symbol.eq(g['vt_symbol'])&a.offset.eq('开')];actual=fills.loc[fills.order_id.astype(str).isin(orders.order_id.astype(str))&fills.vt_symbol.eq(g['vt_symbol'])&fills.direction.eq('多' if direction=='long' else '空')&fills.offset.eq('开')]
  if c.empty:status='no_candidate';actual=actual.iloc[:0]
  elif not c.candidate_status.eq('opened').any():status='candidate_not_opened';actual=actual.iloc[:0]
  elif actual.empty:status='candidate_opened_no_actual_fill'
  else:status='actual_open_matched'
  expected.append(dict(key=key,signal_price=float(src.close),physical_epoch_id=src.contract_epoch_id,gate=g,baseline_role='Stage001_C_short_only' if direction=='long' else 'Stage001_A_original',baseline_status=status,baseline_candidate_count=len(c),baseline_actual_fills=actual[['trade_id','order_id','vt_symbol','direction','offset','price','volume','trading_date']].to_dict('records'),baseline_actual_open_volume=float(actual.volume.sum()) if len(actual) else None))
assert len(expected)==35 and len({tuple(x['key']) for x in expected})==35
bindings={}
for name in ['stage001_delivery_manifest.json','stage002_delivery_manifest.json']:
 m=json.loads((L/'stages'/name).read_text())['files_sha256'];bad=[p for p,h in m.items() if not Path(p).is_file() or sha(p)!=h];assert not bad,bad;bindings[name]=len(m)
result=dict(status='PASS_SOURCE_CANDIDATE_TRUTH',count=35,long_count=20,short_count=15,events=expected,old_bound_counts=bindings,financial_replays=0,market_downloads=0,production_accesses=0)
(L/'stages/stage003_independent_expected.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(status=result['status'],count=35,long_count=20,short_count=15,baseline_status_counts=pd.Series([x['baseline_status'] for x in expected]).value_counts().to_dict(),bindings=bindings),ensure_ascii=False))
