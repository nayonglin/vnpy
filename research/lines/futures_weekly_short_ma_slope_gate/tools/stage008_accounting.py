"""Streaming read-only financial derivation for exactly the frozen 46 arm-windows.

No engine, network, source mutation, partial final-report publication or fake proof.
"""
from __future__ import annotations
import argparse,ast,copy,hashlib,json,math,os,tempfile,time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
import stage001_report as legacy
import stage006_report as range_contract
LINE=Path(__file__).resolve().parents[1];DATA=LINE/'outputs/data_stage001_20261029/data_approved';DERIVED=LINE/'outputs/stage008_derived';CACHE=DERIVED/'cache';REGISTRY=LINE/'outputs/stage008_multistart/registry.json';FREEZE=LINE/'stages/stage008_freeze.json';PREFLIGHT=LINE/'stages/stage008_data_preflight.json';END='2026-10-29';STARTS=sorted([f'{y}-01-01' for y in range(2015,2027)]+[f'{y}-06-01' for y in range(2015,2026)]);LEGACY_2020_A=LINE/'outputs/stage001_A_attempt003';CAPITAL=150000.
FREEZE_SHA='f285ede86164f43c906b498da3138bff7c479d783be96ec1a62ffc6907e6c992'
sha=legacy.sha;verify_sources=legacy.verify_sources;_calendar=None

def safe(x):
 if isinstance(x,dict):return {str(k):safe(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [safe(v) for v in x]
 if isinstance(x,np.generic):return safe(x.item())
 if isinstance(x,(Path,pd.Timestamp,datetime)):return str(x)
 if isinstance(x,float) and not math.isfinite(x):return None
 return x

def write_json(p,x):Path(p).write_text(json.dumps(safe(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def validate_key(start,arm):
 if start not in STARTS or arm not in {'A','C'}:raise ValueError('undeclared_arm_window')
 return start+'|'+arm

def window_meta(start):
 if start not in STARTS:raise ValueError('undeclared_start')
 d=json.loads(PREFLIGHT.read_text());return next(x for x in d['windows'] if x['requested_start']==start)

def expected_days(start):
 global _calendar
 if start not in STARTS:raise ValueError('undeclared_start')
 if _calendar is None:
  d=pd.read_csv(DATA/'mapping.csv',usecols=['date','continuous_symbol_vt'],dtype=str);products=set(json.loads((DATA/'receipt.json').read_text())['products']);_calendar=sorted(d.loc[d.continuous_symbol_vt.isin(products),'date'].unique())
 return [x for x in _calendar if start<=x<=END]

def validate_window(pre,daily,start):
 if pre.get('start')!=start or pre.get('end')!=END or daily.empty or daily.date.duplicated().any() or not daily.date.is_monotonic_increasing:raise ValueError('actual_complete_declared_window_required')
 if daily.date.dt.strftime('%Y-%m-%d').tolist()!=expected_days(start):raise ValueError('actual_calendar_not_full_fresh_window')
 return True

def is_legacy_2020_A(path,start,arm):return Path(path).resolve()==LEGACY_2020_A.resolve() and start=='2020-01-01' and arm=='A'

def normalize_settings(settings,start):
 out=copy.deepcopy(settings)
 if len(out)!=1:raise ValueError('one_settings_record_required')
 for key in ['setting','actual']:
  if out[0][key].get('trade_start_date')!=start:raise ValueError('actual_trade_start_date_not_declared_start')
  out[0][key]['trade_start_date']='<declared-independent-start>'
 return out

def loader_ast():
 source=Path(legacy.__file__);before=sha(source);tree=ast.parse(source.read_text());node=copy.deepcopy(next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='load_ledger'));gate=window=0;body=[]
 for n in node.body:
  values={x.value for x in ast.walk(n) if isinstance(x,ast.Constant) and isinstance(x.value,str)}
  if isinstance(n,ast.If) and 'slope_arm_flag_mismatch' in values:body.extend(ast.parse("price_gate=read('short_price_range_acceptance.json')\n_stage008_gate_identity(pre,gate,price_gate,role)").body);gate+=1
  elif isinstance(n,ast.If) and 'full_requested_2020_calendar_required' in values:body.extend(ast.parse('_stage008_window_identity(pre,daily)').body);window+=1
  else:body.append(n)
 if (gate,window)!=(1,1):raise ValueError('frozen_loader_contract_changed')
 node.body=body;node.name='_stage008_pure_accounting_loader';receipt=dict(schema='stage008_frozen_accounting_narrow_gate_window_adapter_v1',old_source=str(source.resolve()),old_source_sha256=before,gate_checks_replaced=gate,window_checks_replaced=window,arm_check_changed=False,old_source_unchanged=sha(source)==before,retained_string_literals=[n.value for n in ast.walk(node) if isinstance(n,ast.Constant) and isinstance(n.value,str)],adapted_ast_sha256=hashlib.sha256(ast.dump(node,include_attributes=False).encode()).hexdigest(),scope='Only gate identity and window identity validation replaced; financial arithmetic, fill/position/owner/risk audits remain original.')
 return ast.fix_missing_locations(ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0),node],type_ignores=[])),receipt

def freeze_contract():
 if sha(FREEZE)!=FREEZE_SHA:raise ValueError('financial_freeze_identity_drift')
 f=json.loads(FREEZE.read_text())
 if f['starts']!=STARTS or f['cutoff']!=END or f['planned_arm_windows']!=46 or f['planned_financial_replays']!=42:raise ValueError('fixed23_user_scope_required')
 verify_sources(f['source_files_sha256']);verify_sources(f['reused_delivery_sha256']);return f

def registered_job(start,arm,freeze=None):
 key=validate_key(start,arm);f=freeze or freeze_contract();reg=json.loads(REGISTRY.read_text());job=reg['jobs'][key]
 if reg['freeze_sha256']!=FREEZE_SHA or job.get('status')!='validated':raise ValueError('job_not_validated:'+key)
 expected=Path(f['reuse_runs'].get(key,str(LINE/'outputs'/f'stage008_{arm}_{start.replace("-","")}_attempt001'))).resolve()
 if Path(job['path']).resolve()!=expected or (job['start'],job['end'],job['arm'])!=(start,END,arm) or job['freeze_sha256']!=FREEZE_SHA:raise ValueError('registered_source_identity_mismatch')
 checkpoint=Path(job['checkpoint']);cp=json.loads(checkpoint.read_text())
 for k in ['checkpoint_key','freeze_sha256','path','arm','start','end','source_head']:
  if cp.get(k)!=job.get(k):raise ValueError('checkpoint_registration_mismatch:'+k)
 verify_sources(job['files_sha256']);return job

def check_registered_metrics(actual,registered):
 for key in ['end_equity','total_return_pct','max_dd_pct','sharpe','total_slippage']:
  if key not in registered or not np.isclose(actual[key],registered[key],rtol=1e-10,atol=1e-7):raise ValueError('checkpoint_financial_metric_drift:'+key)
 if actual['modeled_fill_count']!=registered['total_trade_count']:raise ValueError('checkpoint_fill_count_drift')

def validate_disabled_long(proofs,must_present):
 p=proofs.get('long_price_range_acceptance.json')
 if p is None:
  if must_present:raise ValueError('new_run_missing_long_price_gate_disabled_proof')
  return
 if p.get('enabled') is not False or p.get('decision_count')!=0 or p.get('applied_block_count')!=0:raise ValueError('long_price_gate_must_be_actually_disabled')

def load_window_ledger(path,start,arm,f):
 validate_key(start,arm);role='baseline' if arm=='A' else 'candidate'
 if is_legacy_2020_A(path,start,arm):
  x=legacy.load_ledger(path,'baseline');validate_window(x['preflight'],x['daily'],start);s=x['acceptances']['short_ma_slope_acceptance.json']
  if s.get('enabled') is not False or s.get('applied_block_count')!=0 or s.get('decision_count')!=65 or s.get('would_block_count')!=21 or s.get('MA_periods')!=[5,10] or (Path(path)/'short_price_range_acceptance.json').exists():raise ValueError('legacy2020_A_frozen_diagnostic_facts_mismatch')
  receipt=dict(schema='stage008_exact_registered_legacy2020_A_v1',source=str(path),original_loader_unmodified=True,no_price_certificate_in_source=True,short_slope_diagnostics=65,would_block=21,applied_block=0,source_flags_not_rewritten=True)
 else:
  tree,receipt=loader_ast();env=dict(vars(legacy));env['_stage008_gate_identity']=range_contract.validate_gate;env['_stage008_window_identity']=lambda pre,daily:validate_window(pre,daily,start);exec(compile(tree,str(Path(__file__))+'::frozen_accounting','exec'),env);x=env['_stage008_pure_accounting_loader'](path,role)
  for side in ['short','long']:
   s=x['acceptances'].get(side+'_ma_slope_acceptance.json',{})
   if s.get('enabled') is not False or s.get('decision_count')!=0 or s.get('applied_block_count')!=0 or s.get('MA_periods')!=[] or s.get('rule')!='disabled_no_slope_wrapper':raise ValueError('new_window_MA_gates_must_be_really_off_zero_diagnostics')
 if x['preflight']['data_identity']!=f['data_identity'] or x['preflight'].get('long_price_range_gate_enabled',False) is not False:raise ValueError('fixed_data_and_no_long_price_gate_required')
 if x['preflight']['arm']!=arm or x['preflight']['daily_addon_enabled'] is not False:raise ValueError('actual_arm_and_no_addon_required')
 if not is_legacy_2020_A(path,start,arm) and start+'|'+arm not in f['reuse_runs'] and x['preflight']['head']!=f['source_head']:raise ValueError('fresh_run_head_not_frozen_head')
 validate_disabled_long(x['acceptances'],start+'|'+arm not in f['reuse_runs'])
 normalize_settings(x['settings'],start);x['loader_adapter']=receipt;return x

def cache_path(start,arm):validate_key(start,arm);return CACHE/(start.replace('-','')+'_'+arm)

def verify_cache(path,job=None,deep=True):
 path=Path(path);m=json.loads((path/'delivery_manifest.json').read_text());verify_sources({str(path/k):v for k,v in m['files_sha256'].items()});d=json.loads((path/'ledger.json').read_text())
 if d['freeze_sha256']!=FREEZE_SHA or d['derivation_sources_sha256'].get(str(Path(__file__).resolve()))!=sha(__file__):raise ValueError('cache_derivation_identity_changed')
 verify_sources(d['derivation_sources_sha256'])
 if deep:verify_sources(d['source_files_sha256'])
 if legacy.snapshot_dir(d['source_path'])!=d['attempt_snapshot']:raise ValueError('source_attempt_set_or_bytes_changed')
 if job is not None and (d['checkpoint_key']!=job['checkpoint_key'] or d['checkpoint_sha256']!=sha(job['checkpoint']) or d['source_path']!=job['path']):raise ValueError('cache_checkpoint_identity_changed')
 return d

def cache_one(start,arm):
 f=freeze_contract();job=registered_job(start,arm,f);dest=cache_path(start,arm)
 if dest.exists():return verify_cache(dest,job),False
 print('Deriving actual financial ledger '+start+'|'+arm,flush=True);x=load_window_ledger(job['path'],start,arm,f);meta=window_meta(start);metrics=x['metrics']
 for k in ['end_equity','total_return_pct','max_dd_pct','sharpe','total_slippage','modeled_fill_count']:
  if metrics.get(k) is None or not math.isfinite(float(metrics[k])):raise ValueError('finite_complete_window_metrics_required:'+k)
 check_registered_metrics(metrics,job['metrics'])
 settings=normalize_settings(x['settings'],start);derivation={str(p.resolve()):sha(p) for p in [Path(__file__),Path(__file__).with_name('test_stage008_accounting.py'),Path(legacy.__file__),Path(range_contract.__file__),PREFLIGHT,FREEZE]}
 sources=dict(x['sources']);sources[str(Path(job['checkpoint']).resolve())]=sha(job['checkpoint'])
 doc=dict(schema='stage008_independent_window_financial_cache_v1',status='DERIVED_PENDING_INDEPENDENT_REVIEW_NOT_FINAL_REPORT',generated_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),key=start+'|'+arm,start=start,end=END,arm=arm,source_path=job['path'],reused=job['reused'],freeze_sha256=FREEZE_SHA,checkpoint_key=job['checkpoint_key'],checkpoint_sha256=sha(job['checkpoint']),window=meta,metrics=metrics,accounting=x['accounting'],risk=x['risk'],position_audit=x['position_audit'],preflight=x['preflight'],settings=x['settings'],normalized_settings=settings,effective=x['effective'],addon=x['addon'],gate_certificates={k:v for k,v in x['acceptances'].items() if 'slope' in k or 'price_range' in k},loader_adapter=x['loader_adapter'],source_files_sha256=sources,attempt_snapshot=x['attempt_snapshot'],derivation_sources_sha256=derivation,financial_replays=0,market_downloads=0,production_accesses=0)
 CACHE.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory(prefix='.derive_',dir=CACHE) as td:
  tmp=Path(td);daily=x['daily'][['date','account_equity','net_pnl','slippage','commission','trade_count']].copy();daily['nav'],daily['drawdown_pct']=range_contract.nav_drawdown(daily.account_equity);daily.to_csv(tmp/'daily.csv',index=False);x['rounds'].to_csv(tmp/'complete_rounds.csv',index=False);x['opened'].to_csv(tmp/'terminal_open_rounds.csv',index=False);pd.DataFrame(legacy.annual_rows(x)).to_csv(tmp/'annual.csv',index=False);write_json(tmp/'ledger.json',doc);write_json(tmp/'delivery_manifest.json',dict(schema='stage008_cache_delivery_v1',files_sha256={p.name:sha(p) for p in tmp.iterdir() if p.is_file()},self_hash_excluded=True,not_final_report=True));verify_sources(sources);verify_sources(derivation)
  if legacy.snapshot_dir(x['path'])!=x['attempt_snapshot']:raise ValueError('source_changed_during_financial_derivation')
  os.rename(tmp,dest)
 print('Derived '+doc['key']+' equity='+str(metrics['end_equity']),flush=True);return doc,True

def cache_ready(max_jobs=None):
 f=freeze_contract();r=json.loads(REGISTRY.read_text());jobs=[(key,x) for key,x in r['jobs'].items() if x.get('status')=='validated'];jobs.sort(key=lambda item:(bool(item[1].get('reused')),item[0]));done=0
 for key,job in jobs:
  start,arm=key.split('|')
  if cache_path(start,arm).exists():continue
  cache_one(start,arm);done+=1
  if max_jobs is not None and done>=max_jobs:break
 count=sum((cache_path(s,a)/'delivery_manifest.json').exists() for s in STARTS for a in ['A','C']);print(json.dumps(dict(derived_cache_count=count,expected=46,newly_derived=done,cache_only_not_final_report=True)),flush=True);return count

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--start',choices=STARTS);ap.add_argument('--arm',choices=['A','C']);ap.add_argument('--cache-ready',action='store_true');ap.add_argument('--watch',action='store_true');ap.add_argument('--max-jobs',type=int);x=ap.parse_args()
 if x.start or x.arm:
  if not x.start or not x.arm:raise ValueError('start_and_arm_required_together')
  cache_one(x.start,x.arm);return
 if x.watch:
  while cache_ready(x.max_jobs)<46:time.sleep(15)
 elif x.cache_ready:cache_ready(x.max_jobs)
 else:ap.error('choose cache-ready/watch or explicit start+arm')
if __name__=='__main__':main()
