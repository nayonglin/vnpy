"""Frozen 23 start-to-cutoff research windows and immutable checkpoints."""
from pathlib import Path
import hashlib,json,math,os
ROOT=Path(__file__).resolve().parents[4]
LINE=ROOT/'research/lines/futures_weekly_short_ma_slope_gate'
STARTS=tuple(f'{y}-{m:02d}-01' for y in range(2015,2027) for m in (1,6) if (y,m)<=(2026,1))
CUTOFF='2026-10-29'
IDENTITY_KEYS={'daily_sqlite_sha256','mapping_sha256','physical_epoch_daily_sha256','receipt_sha256'}
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for c in iter(lambda:f.read(4194304),b''):h.update(c)
 return h.hexdigest()
def load(path):return json.loads(Path(path).read_text())
def atomic_json(path,obj):
 p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name(p.name+'.tmp');tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n');os.replace(tmp,p)
def validate_start(start):
 if start not in STARTS:raise ValueError('stage008_start_not_in_frozen23')
 return start

def first_trading_day(start,calendar):
 validate_start(start);days=sorted({str(x)[:10] for x in calendar if start<=str(x)[:10]<=CUTOFF})
 if not days:raise ValueError('stage008_empty_requested_calendar')
 return days[0]
def metric_close(a,b):
 return math.isfinite(float(a)) and math.isfinite(float(b)) and math.isclose(float(a),float(b),rel_tol=1e-10,abs_tol=1e-6)
def checkpoint_key(freeze,freeze_sha,arm,start):
 validate_start(start)
 if arm not in {'A','C'}:raise ValueError('stage008_unknown_arm')
 return hashlib.sha256(json.dumps(dict(source_head=freeze['source_head'],freeze_sha256=freeze_sha,cutoff=freeze['cutoff'],arm=arm,start=start),sort_keys=True).encode()).hexdigest()
def validate_freeze(path):
 p=Path(path).resolve();f=load(p)
 if f.get('starts')!=list(STARTS) or f.get('cutoff')!=CUTOFF:raise ValueError('stage008_freeze_window_manifest_mismatch')
 head=f.get('source_head','')
 if len(head)!=40 or any(c not in '0123456789abcdef' for c in head):raise ValueError('stage008_frozen_head_required')
 if set(f.get('data_identity',{}))!=IDENTITY_KEYS:raise ValueError('stage008_data_identity_required')
 sources=f.get('source_files_sha256')
 if not isinstance(sources,dict) or not sources:raise ValueError('stage008_frozen_source_hashes_required')
 for name,h in sources.items():
  q=Path(name);q=q if q.is_absolute() else ROOT/q
  if not q.is_file() or sha(q)!=h:raise ValueError('stage008_frozen_source_changed:'+str(q))
 return f,sha(p)
def snapshot_dir(path):return {str(p.resolve()):sha(p) for p in sorted(Path(path).iterdir()) if p.is_file()}
def validate_run(path,freeze,arm,start):
 """Read real output identity and terminal gates, never relabel a curve."""
 import pandas as pd
 p=Path(path).resolve();pre=load(p/'preflight.json');t=load(p/'terminal.json');post=load(p/'postflight.json')
 if t.get('status')!='completed_pending_independent_review' or t.get('error') is not None or post.get('inputs_unchanged') is not True:raise ValueError('stage008_incomplete_run:'+str(p))
 if pre.get('arm')!=arm or pre.get('start')!=start or pre.get('end')!=freeze['cutoff'] or pre.get('data_identity')!=freeze['data_identity']:raise ValueError('stage008_run_identity_mismatch')
 if pre.get('short_ma_slope_gate_enabled') is not False or pre.get('long_ma_slope_gate_enabled',False) is not False or pre.get('long_price_range_gate_enabled',False) is not False:raise ValueError('stage008_forbidden_long_or_slope_gate')
 for name in ['long_ma_slope_acceptance.json','long_price_range_acceptance.json']:
  q=p/name
  if q.exists() and (load(q).get('enabled') is not False or load(q).get('applied_block_count')!=0):raise ValueError('stage008_actual_long_filter_on:'+name)
 short=load(p/'short_ma_slope_acceptance.json')
 if short.get('enabled') is not False or short.get('applied_block_count')!=0:raise ValueError('stage008_actual_short_slope_gate_on')
 proof=p/'short_price_range_acceptance.json'
 if arm=='C' and (not proof.is_file() or load(proof).get('enabled') is not True or pre.get('short_price_range_gate_enabled') is not True):raise ValueError('stage008_actual_short_bottom20_not_on')
 if arm=='A' and (pre.get('short_price_range_gate_enabled',False) is not False or (proof.is_file() and (load(proof).get('enabled') is not False or load(proof).get('applied_block_count')!=0))):raise ValueError('stage008_actual_original_has_range_gate')
 for q in p.glob('*_acceptance.json'):
  if load(q).get('accepted') is not True:raise ValueError('stage008_acceptance_failed:'+q.name)
 for name,h in load(p/'input_manifest.json').items():
  if not Path(name).is_file() or sha(name)!=h:raise ValueError('stage008_input_changed:'+name)
 settings=load(p/'actual_strategy_settings.json')
 if len(settings)!=1 or settings[0]['actual'].get('trade_start_date')!=start:raise ValueError('stage008_actual_trade_start_wrong')
 actual=settings[0]['actual']
 if actual.get('capital_base')!=150000 or actual.get('enable_add_position') is not False:raise ValueError('stage008_capital_or_addon_changed')
 d=pd.read_csv(p/'daily.csv');mapping=pd.read_csv(settings[0]['actual']['mapping_csv_path']);expected=sorted(set(mapping.loc[mapping.date.ge(start)&mapping.date.le(freeze['cutoff']),'date'].astype(str)))
 dates=d.date.astype(str).str[:10].tolist()
 if dates!=expected or not dates or dates[0]!=first_trading_day(start,expected):raise ValueError('stage008_full_fresh_window_required')
 if not metric_close(d.account_equity.iloc[0],150000) or float(d.trade_count.iloc[0])!=0:raise ValueError('stage008_first_day_not_fresh150000')
 if not all(math.isfinite(float(x)) for x in d.account_equity):raise ValueError('stage008_nonfinite_equity')
 m=load(p/'metrics.json');checks={'end_equity':float(d.account_equity.iloc[-1]),'total_return_pct':(float(d.account_equity.iloc[-1])/150000-1)*100,'total_slippage':float(d.slippage.sum()),'total_trade_count':float(d.trade_count.sum())}
 for key,value in checks.items():
  if not metric_close(value,m[key]):raise ValueError('stage008_metrics_drift:'+key)
 return dict(path=str(p),arm=arm,start=start,end=freeze['cutoff'],actual_start=dates[0],actual_end=dates[-1],trading_days=len(d),metrics={k:m[k] for k in ['end_equity','total_return_pct','max_dd_pct','sharpe','total_slippage','total_trade_count']})
def validate_run_freeze_identity(path,freeze,freeze_sha,arm,start,reused):
 p=Path(path).resolve();pre=load(p/'preflight.json')
 if type(reused) is not bool:raise ValueError('stage008_reuse_flag_must_be_bool')
 if reused:
  k=start+'|'+arm;allowed={'2015-01-01|A','2015-01-01|C','2020-01-01|A','2020-01-01|C'}
  if k not in allowed or k not in freeze.get('reuse_runs',{}) or Path(freeze['reuse_runs'][k]).resolve()!=p:raise ValueError('stage008_reuse_exact_frozen_path_required')
 else:
  if pre.get('freeze_sha256')!=freeze_sha or pre.get('frozen_source_head')!=freeze['source_head']:raise ValueError('stage008_run_freeze_or_source_head_mismatch')

def make_checkpoint(path,checkpoint,freeze,freeze_sha,arm,start,reused=False):
 validate_run_freeze_identity(path,freeze,freeze_sha,arm,start,reused)
 info=validate_run(path,freeze,arm,start);info.update(schema='stage008_checked_run_v1',checkpoint_key=checkpoint_key(freeze,freeze_sha,arm,start),freeze_sha256=freeze_sha,source_head=freeze['source_head'],reused=bool(reused),files_sha256=snapshot_dir(path))
 atomic_json(checkpoint,info);return info

def read_checkpoint(checkpoint,freeze,freeze_sha,arm,start):
 r=load(checkpoint)
 if r.get('checkpoint_key')!=checkpoint_key(freeze,freeze_sha,arm,start):raise ValueError('stage008_checkpoint_identity_mismatch')
 if r.get('files_sha256')!=snapshot_dir(r['path']):raise ValueError('stage008_checkpoint_output_changed')
 validate_run_freeze_identity(r['path'],freeze,freeze_sha,arm,start,r.get('reused'))
 current=validate_run(r['path'],freeze,arm,start)
 for key,value in current['metrics'].items():
  if not metric_close(value,r['metrics'][key]):raise ValueError('stage008_checkpoint_metric_changed:'+key)
 return r
