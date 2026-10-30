"""Independent Stage011 audit: inherited raw inventory + wallet, new risk delta.

No runner/report assertions are used as a substitute for financial reconstruction.
The frozen Stage009 auditor independently reconstructs every fill, contract/day
MTM, complete round, open MTM, native funding qualification and fill phase. Its
raw Stage008 financial function is unchanged except its already reviewed raw
auxiliary Sharpe adapter. SHA reads are deduplicated only while stat identity is
exactly the same as the one-time independently hashed admission graph.
"""
from pathlib import Path
from copy import deepcopy
import argparse, hashlib, json, math, sys, time
import numpy as np
import pandas as pd
import stage009_independent_window as inherited

ROOT=Path(__file__).resolve().parents[4]
LINE=ROOT/'research/lines/futures_weekly_short_ma_slope_gate'
STAGES=LINE/'stages'
DELTA={'risk_ratio_volume_open_interest_surge':.06,
       'risk_ratio_open_interest_surge':.06,
       'risk_ratio_open_interest_decline':.025}
checks=0
def ok(v,label):
 global checks
 checks+=1
 if not v: raise AssertionError(label)
def near(a,b,label):
 ok(math.isfinite(float(a)) and math.isfinite(float(b)) and math.isclose(float(a),float(b),rel_tol=1e-10,abs_tol=1e-6),label)
def plain_sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def fingerprint(path):
 s=Path(path).stat()
 return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
def load(path):return json.loads(Path(path).read_text())
def install_hash_cache():
 cachepath=STAGES/'stage011_independent_hash_cache.json';admission=load(STAGES/'stage011_independent_data_review.json')
 ok(plain_sha(cachepath)==admission['hash_cache_sha256'],'admitted_hash_cache_binding')
 cache=load(cachepath)['files'];counts={'admitted_stat_hits':0,'new_hashes':0,'new_bytes':0}
 def sha(path):
  path=str(Path(path).resolve());stat=fingerprint(path);item=cache.get(path)
  if item is not None and item['stat']==stat:
   counts['admitted_stat_hits']+=1;return item['sha256']
  actual=plain_sha(path);ok(fingerprint(path)==stat,'file_stable_during_hash:'+path)
  # A changed admitted file is never silently accepted with refreshed hash.
  if item is not None:ok(actual==item['sha256'],'admitted_file_content_drift:'+path)
  cache[path]={'sha256':actual,'stat':stat};counts['new_hashes']+=1;counts['new_bytes']+=Path(path).stat().st_size
  return actual
 inherited.sha=sha;inherited.raw_audit.sha=sha
 return sha,counts
def strip_delta(value):
 if isinstance(value,dict):return {k:strip_delta(v) for k,v in value.items() if k not in DELTA}
 if isinstance(value,list):return [strip_delta(v) for v in value]
 return value
def parameter_audit(path,oldpath):
 current=load(path/'actual_strategy_settings.json');old=load(oldpath/'actual_strategy_settings.json')
 ok(len(current)==len(old)==1,'one_actual_strategy_configuration')
 for scope in ['setting','actual']:
  for name,prior in DELTA.items():
   near(old[0][scope][name],prior,'old_special_risk:'+scope+':'+name)
   near(current[0][scope][name],.018,'new_uniform_risk:'+scope+':'+name)
 normalized=deepcopy(current)
 for scope in ['setting','actual']:
  for name in DELTA:normalized[0][scope][name]=old[0][scope][name]
 ok(normalized==old,'only_three_strategy_parameter_deltas')
 ce=load(path/'effective_parameters.json');oe=load(oldpath/'effective_parameters.json')
 normalized_effective=deepcopy(ce)
 for name in DELTA:
  if name in oe['spec']['overrides']:normalized_effective['spec']['overrides'][name]=oe['spec']['overrides'][name]
  else:normalized_effective['spec']['overrides'].pop(name,None)
 ok(normalized_effective==oe,'only_three_effective_parameter_deltas')
 for name in DELTA:
  near(ce['spec']['overrides'][name],.018,'effective_override:'+name)
 a=current[0]['actual']
 for name,value in [('risk_ratio_of_total_assets',.018),('risk_ratio_breakout',.018),('risk_ratio_ma_cross_breakout',.018),('min_risk_per_trade',1000.),('oi_price_confirm_risk_restore_multiplier',2.),('directional_30d_risk_boost_multiplier',1.5),('directional_30d_low_volume_risk_multiplier',.5)]:
  near(a[name],value,'preserved_risk_parameter:'+name)
 ok(all(float(v)==0. for v in ce['rates'].values()),'frozen_zero_commission_explicit')
 risk=pd.read_csv(path/'entry_risk.csv')
 ok(not risk.empty and risk.sizing_method.eq('risk_budget').all(),'actual_entry_risk_budget_rows')
 ok(set(risk.risk_mode)<={'regular','breakout','ma_cross_breakout','volume_open_interest_surge','open_interest_surge','open_interest_decline'},'signal_classifications_preserved')
 for r in risk.itertuples():
  near(r.risk_ratio,.018,'every_actual_entry_base_rate_0018')
  base=min(float(a['max_risk_per_trade']),max(1000.,float(r.limited_balance)*.018))*max(0.,float(r.risk_multiplier))
  near(r.risk_amount_before_directional_30d_boost,base,'independent_floor_capped_scaled_risk_amount')
  mult=float(r.directional_30d_risk_boost_multiplier)
  ok(mult in {1.,1.5,.5},'preserved_directional_multipliers')
  near(r.target_risk_amount,base*mult,'independent_final_target_risk')
  near(r.oi_price_confirm_risk_restore_multiplier,2.,'entry_OI_configured_double')
  want=2. if int(r.oi_price_confirm_risk_restore_applied) else 1.
  near(r.oi_price_confirm_risk_restore_effective_multiplier,want,'entry_OI_applied_double_or_unity')
  near(r.risk_multiplier,want,'no_second_global_04_or_hidden_streak_multiplier')
  ok(not (int(r.directional_30d_risk_boost_applied) and int(r.directional_30d_low_volume_discount_applied)),'exclusive_directional_boost_discount')
  near(mult,1.5 if int(r.directional_30d_risk_boost_applied) else .5 if int(r.directional_30d_low_volume_discount_applied) else 1.,'directional_multiplier_actual_flags')
 return dict(actual_parameter_delta={name:{'old':prior,'new':.018} for name,prior in DELTA.items()},all_other_parameters_unchanged=True,entry_rows=len(risk),risk_mode_counts=risk.risk_mode.value_counts().to_dict(),actual_entry_base_rates=sorted(risk.risk_ratio.unique().tolist()),OI_double_rows=int(risk.oi_price_confirm_risk_restore_applied.sum()),directional_15_rows=int(risk.directional_30d_risk_boost_applied.sum()),low_volume_05_rows=int(risk.directional_30d_low_volume_discount_applied.sum()),minimum_risk=1000.,settings_sha256=plain_sha(path/'actual_strategy_settings.json'),old_settings_sha256=plain_sha(oldpath/'actual_strategy_settings.json'))
def audit(path,arm,start,end,freeze,control=None):
 started=time.monotonic();sha,hash_counts=install_hash_cache();f=load(freeze)
 oldregpath=LINE/'outputs/stage009_multistart/registry.json';oldreg=load(oldregpath);oldjob=oldreg['jobs'][start+'|'+arm];oldpath=Path(oldjob['path'])
 ok(sha(STAGES/'stage009_delivery_manifest.json')=='b4712560c72548106fb9e4273895e1bfc80c56a6813cdfe3d71b4190b5d5a424','old_control_final_binding')
 ok(start in f['starts'] and end==f['cutoff']=='2026-10-29' and len(f['starts'])==23,'exact_frozen_window')
 before={str(p):sha(p) for p in path.iterdir() if p.is_file()}
 for name in ['actual_strategy_settings.json','effective_parameters.json']:
  ok(sha(oldpath/name)==oldjob['files_sha256'][str(oldpath/name)],'old_settings_bound_to_control_checkpoint')
 parameters=parameter_audit(path,oldpath)
 inherited.checks=0
 receipt=inherited.audit(path,arm,start,end,freeze,control)
 ok(receipt['P0']==receipt['P1']==receipt['P2']==0,'inherited_financial_funding_pass')
 bridge=pd.read_csv(path/'reserve_daily.csv');daily=pd.read_csv(path/'daily.csv');cum=daily.net_pnl.cumsum().to_numpy();T=bridge.cumulative_transfer.to_numpy();E=bridge.trading_account_equity.to_numpy();R=bridge.reserve_balance.to_numpy();W=bridge.total_account_equity.to_numpy()
 for arr,want,label in [(E,150000.+cum+T,'E150k_plus_cumPnL_plus_T'),(R,150000.-T,'R150k_minus_T'),(W,300000.+cum,'W300k_plus_cumPnL'),(E+R,W,'EplusR_equals_W')]:ok(np.allclose(arr,want,rtol=1e-10,atol=1e-6),'all_days:'+label)
 ok(np.allclose(daily.commission,0.),'all_days_zero_commission')
 near(receipt['metrics']['rounds']['closed_net_pnl']+receipt['metrics']['open_round_net_mtm'],cum[-1],'complete_rounds_open_MTM_realPnL')
 previous=np.r_[150000.,E[:-1]];valid=np.isfinite(E)&np.isfinite(previous)&(previous>0);defined=bool(valid.all());account_returns=np.divide(E-previous,previous,out=np.full_like(E,np.nan),where=previous>0);defined=defined and bool(np.isfinite(account_returns).all());std=float(account_returns.std(ddof=1)) if defined else 0.;account=dict(initial_capital=150000.,end_equity=float(E[-1]),growth_including_deposits_pct=float((E[-1]/150000.-1)*100),max_dd_including_deposits_pct=float((E/np.maximum.accumulate(np.r_[150000.,E])[1:]-1).min()*100),sharpe_including_deposits=float(account_returns.mean()/std*np.sqrt(252.)) if defined and std>0 else 0.,nav_definition='E/150000; transferred deposits included; unused off-account reserve excluded; not strategy return',return_diagnostic_policy='Every previous E must be positive and finite; any undefined denominator -> whole Sharpe0 plus false flag; insolvency days reported separately',balance_returns_defined=defined,undefined_return_days=int((~valid).sum()))
 ok(before=={str(p):sha(p) for p in path.iterdir() if p.is_file()},'immutable_new_run_all_outputs')
 receipt.update(schema='stage011_independent_window_review_v1',stage011_parameter_review=parameters,account_display=account,real_net_pnl=float(cum[-1]),hash_verification=hash_counts,stage011_checks=checks,inherited_window_auditor_sha256=sha(Path(inherited.__file__)),auditor_source_sha256=sha(__file__),old_control_path=str(oldpath),old_control_registry_sha256=sha(oldregpath),promotion_decision='NO_PROMOTION',financial_replays=0,market_downloads=0,production_accesses=0,seconds=time.monotonic()-started)
 return receipt
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--path','--run-dir',type=Path,required=True);ap.add_argument('--arm',choices=['A','C'],required=True);ap.add_argument('--start',required=True);ap.add_argument('--end',default='2026-10-29');ap.add_argument('--freeze',type=Path,default=STAGES/'stage011_freeze.json');ap.add_argument('--output',type=Path,required=True);ap.add_argument('--control',type=Path);args=ap.parse_args()
 if args.output.exists():raise ValueError('immutable_independent_receipt_exists')
 r=audit(args.path,args.arm,args.start,args.end,args.freeze,args.control);args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(r,ensure_ascii=False,indent=2,default=lambda x:x.item() if hasattr(x,'item') else str(x))+'\n')
 print(json.dumps({k:r[k] for k in ['status','arm','requested_start','metrics','reserve_diagnostics','stage011_parameter_review','stage011_checks','raw_core_checks','funding_checks','hash_verification','seconds']},ensure_ascii=False,default=str))
if __name__=='__main__':main()
