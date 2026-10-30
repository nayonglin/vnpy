"""Stage014 standalone59 accounting/causality audit. No runner or engine invocation."""
from pathlib import Path
from copy import deepcopy
import argparse,ast,hashlib,inspect,json,math,time
import numpy as np
import pandas as pd
import stage009_independent_window as oldaudit
from stage014_independent_scope import scope,mature
ROOT=Path(__file__).resolve().parents[4];LINE=ROOT/'research/lines/futures_weekly_short_ma_slope_gate';STAGES=LINE/'stages';BASE=LINE/'outputs/stage014_multistart';checks=0
TIERS={'regular':.018,'breakout':.018,'ma_cross_breakout':.018,'volume_open_interest_surge':.06,'open_interest_surge':.06,'open_interest_decline':.025}
FORBIDDEN={'SM704.CZCE','SM706.CZCE','SM707.CZCE','SM708.CZCE'}
def ok(v,label):
 global checks
 checks+=1
 if not v:raise AssertionError(label)
def near(a,b,label):ok(np.allclose(a,b,rtol=1e-10,atol=1e-6,equal_nan=False),label)
def plain_sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
load=lambda p:json.loads(Path(p).read_text())
def fingerprint(p):
 s=Path(p).stat();return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
def install_cache():
 admission=load(STAGES/'stage014_independent_code_review.json');p=Path(admission['source_hash_cache']);ok(plain_sha(p)==admission['source_hash_cache_sha256'],'immutable_stage014_run_cache');cache=load(p)['files'];counts={'admitted_stat_hits':0,'new_hashes':0,'new_bytes':0}
 def sha(q):
  q=str(Path(q).resolve());s=fingerprint(q);old=cache.get(q)
  if old and old['stat']==s:counts['admitted_stat_hits']+=1;return old['sha256']
  h=plain_sha(q);ok(s==fingerprint(q),'stable_SHA_read')
  if old:ok(h==old['sha256'],'admitted_content_drift:'+q)
  cache[q]={'sha256':h,'stat':s};counts['new_hashes']+=1;counts['new_bytes']+=Path(q).stat().st_size;return h
 oldaudit.sha=sha;oldaudit.raw_audit.sha=sha;return sha,counts

def raw_adapter():
 tree=ast.parse(inspect.getsource(oldaudit.raw_audit.audit));original=deepcopy(tree);sharpe=empty=0
 for node in ast.walk(tree):
  if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='dict':
   keys={x.arg for x in node.keywords}
   if {'end_equity','total_return_pct','max_dd_pct','sharpe'}<=keys:
    for arg in node.keywords:
     if arg.arg=='sharpe':arg.value=ast.Call(func=ast.Name(id='_stage014_raw_aux_sharpe',ctx=ast.Load()),args=[ast.Name(id='eq',ctx=ast.Load())],keywords=[]);sharpe+=1
   for arg in node.keywords:
    if arg.arg=='first_open_signal_date':
     ok(isinstance(arg.value,ast.Call) and isinstance(arg.value.func,ast.Name) and arg.value.func.id=='min' and not arg.value.keywords,'exact_first_open_min_expression');arg.value.keywords=[ast.keyword(arg='default',value=ast.Constant(value=None))];empty+=1
 ok(sharpe==empty==1,'exact_auxiliary_sharpe_and_empty_first_open_only');tree.body[0].name='_stage014_raw_audit';env=vars(oldaudit.raw_audit);env['_stage014_raw_aux_sharpe']=oldaudit.raw_aux_sharpe;exec(compile(ast.fix_missing_locations(tree),str(Path(__file__))+'::raw_exact_adapters','exec'),env)
 return env['_stage014_raw_audit'],dict(original_AST_sha256=hashlib.sha256(ast.dump(original,include_attributes=False).encode()).hexdigest(),adapted_AST_sha256=hashlib.sha256(ast.dump(tree,include_attributes=False).encode()).hexdigest(),raw_auxiliary_Sharpe_convention_matches_accepted_Stage009=True,empty_first_open_signal_date_is_None=True,all_FIFO_MTM_cost_fill_weekly_data_causality_expressions_unchanged=True)

def funding_adapter(data):
 original=inspect.getsource(oldaudit.audit);needle="frozen['planned_arm_windows']==46 and frozen['planned_financial_replays']==46";ok(original.count(needle)==1,'exact_one_scope_expression');source=original.replace(needle,"_stage014_scope_ok(frozen)");tree=ast.parse(source);tree.body[0].name='_stage014_funding_audit';env=vars(oldaudit);env['DATA']=data;env['raw_audit_adapter']=raw_adapter;env['_stage014_scope_ok']=lambda f:scope(f)['windows']==59;oldaudit.raw_audit.DATA=data
 # Existing raw FIFO/MTM/fees/weekly/causality audit is unchanged. Only the
 # cashflow-neutral diagnostic raw Sharpe adapter from accepted Stage009 applies.
 exec(compile(ast.fix_missing_locations(tree),str(Path(__file__))+'::59_scope_only','exec'),env)
 return env['_stage014_funding_audit'],dict(original_AST_sha256=hashlib.sha256(ast.dump(ast.parse(original),include_attributes=False).encode()).hexdigest(),adapted_AST_sha256=hashlib.sha256(ast.dump(tree,include_attributes=False).encode()).hexdigest(),only_expression_changed=needle,capital_R150_W300_and_all_economic_audit_expressions_unchanged=True,data_global_redirected_to_frozen_new_snapshot=str(data),original_auditor_source_sha256=plain_sha(oldaudit.__file__))

def parameter_audit(path,start,data):
 reference=LINE/'outputs/stage009_C_20150101_attempt001';s=load(path/'actual_strategy_settings.json');old=load(reference/'actual_strategy_settings.json');e=load(path/'effective_parameters.json');oe=load(reference/'effective_parameters.json');ok(len(s)==len(old)==1,'single_actual_strategy');copy=deepcopy(s);delta={}
 for layer in ['setting','actual']:
  a=copy[0][layer];b=old[0][layer];delta[layer]={k:{'old':b.get(k),'new':a.get(k)} for k in set(a)|set(b) if a.get(k)!=b.get(k)};ok(set(delta[layer])<={'mapping_csv_path','trade_start_date'},'only_authorized_setting_delta:'+layer);ok(a['trade_start_date']==start and a['mapping_csv_path']==str(data/'mapping.csv'),'actual_start_and_new_mapping');a['trade_start_date']=b['trade_start_date'];a['mapping_csv_path']=b['mapping_csv_path']
 ok(copy==old,'all_other_actual_fields_exact_original_C');copy=deepcopy(e);over=copy['spec']['overrides'];before=oe['spec']['overrides'];edelta={k for k in set(over)|set(before) if over.get(k)!=before.get(k)};ok(edelta<={'mapping_csv_path','trade_start_date'},'only_authorized_effective_delta');ok(set(over)==set(before),'effective_keyset_exact');ok(over['mapping_csv_path']==str(data/'mapping.csv'),'effective_new_mapping');over['mapping_csv_path']=before['mapping_csv_path']
 if 'trade_start_date' in before:ok(over['trade_start_date']==start,'effective_actual_start');over['trade_start_date']=before['trade_start_date']
 ok(copy==oe,'all_remaining_effective_config_exact')
 a=s[0]['actual'];ok(load(path/'actual_daily_addon_configuration.json')['enabled'] is False and a['enable_add_position'] is False,'no_nonmain_addon_path')
 for k,v in [('risk_ratio_of_total_assets',.018),('risk_ratio_breakout',.018),('risk_ratio_ma_cross_breakout',.018),('risk_ratio_volume_open_interest_surge',.06),('risk_ratio_open_interest_surge',.06),('risk_ratio_open_interest_decline',.025),('min_risk_per_trade',1000.),('oi_price_confirm_risk_restore_multiplier',2.),('directional_30d_risk_boost_multiplier',1.5),('directional_30d_low_volume_risk_multiplier',.5)]:near(a[k],v,'original_parameter:'+k)
 rows=pd.read_csv(path/'entry_risk.csv')
 for r in rows.itertuples():
  ok(r.risk_mode in TIERS,'original_mode');near(r.risk_ratio,TIERS[r.risk_mode],'actual_entry_original_rate');budget=min(a['max_risk_per_trade'],max(1000.,r.limited_balance*TIERS[r.risk_mode]))*max(0.,r.risk_multiplier);near(r.risk_amount_before_directional_30d_boost,budget,'independent_risk_budget');near(r.target_risk_amount,budget*r.directional_30d_risk_boost_multiplier,'independent_directional_risk');near(r.risk_multiplier,2. if r.oi_price_confirm_risk_restore_applied else 1.,'OI_double_preserved');near(r.directional_30d_risk_boost_multiplier,1.5 if r.directional_30d_risk_boost_applied else .5 if r.directional_30d_low_volume_discount_applied else 1.,'directional_multiplier_preserved')
 return dict(all_actual_settings_unchanged_except_declared_start_and_mapping=True,all_effective_parameters_unchanged_except_declared_start_and_mapping=True,allowed_setting_deltas=delta,actual_risk_tiers=TIERS,entry_rows=len(rows),risk_mode_counts=rows.risk_mode.value_counts().to_dict())

def account_metrics(E):
 E=np.asarray(E,float);prev=np.r_[150000.,E[:-1]];defined=bool(np.isfinite(E).all() and (prev>0).all());r=(E-prev)/prev if defined else None;defined=defined and bool(np.isfinite(r).all());std=float(r.std(ddof=1)) if defined and len(r)>1 else 0.
 return dict(initial_capital=150000.,end_equity=float(E[-1]),total_return_pct=float((E[-1]/150000.-1)*100),max_dd_pct=float((E/np.maximum.accumulate(np.r_[150000.,E])[1:]-1).min()*100),sharpe=(float(r.mean()/std*np.sqrt(252)) if std>0 else 0.) if defined else None,returns_defined=defined,definition='E/150000 includes depositedT; unusedR excluded; not cashflow-adjusted alpha')

def prefix_audit(path,oldpath):
 result={}
 for name in ['daily.csv','reserve_daily.csv','trades.csv','execution_clock.csv','internal_equity_daily.csv','weekly_readiness.csv','weekly_bars.csv','execution_anchor_requests.csv']:
  old=pd.read_csv(oldpath/name,float_precision='round_trip');new=pd.read_csv(path/name,float_precision='round_trip');field='week_end' if name=='weekly_bars.csv' else 'trading_date' if name in ['trades.csv','execution_clock.csv'] else 'trading_date' if name=='execution_anchor_requests.csv' else 'date';old=old.loc[old[field].astype(str).str[:10].le('2026-10-29')];new=new.loc[new[field].astype(str).str[:10].le('2026-10-29')];cols=[k for k in old.columns if k!='result_scope'];ok(cols==[k for k in new.columns if k!='result_scope'] and len(old)==len(new),'prefix_exact_columns_counts:'+name)
  for k in cols:
   a=old[k].reset_index(drop=True);b=new[k].reset_index(drop=True)
   if pd.api.types.is_numeric_dtype(a):ok(np.allclose(a,b,rtol=1e-10,atol=1e-6,equal_nan=True),'prefix_numeric:'+name+':'+k)
   else:ok(a.fillna('').equals(b.fillna('')),'prefix_text:'+name+':'+k)
  result[name]=len(old)
 for name in ['reserve_events.json','reserve_checks.json','reserve_snapshots.json','reserve_fill_phases.json']:
  old=[x for x in load(oldpath/name) if str(x['date'])[:10]<='2026-10-29' and x.get('phase')!='runner_terminal'];new=[x for x in load(path/name) if str(x['date'])[:10]<='2026-10-29' and x.get('phase')!='runner_terminal'];ok(old==new,'full_causal_prefix_JSON:'+name);result[name]=len(old)
 return dict(prefix_through_2026_10_29_unchanged=True,compared_rows=result,excluded_fields=['result_scope management label','old29 runner_terminal snapshot only'],new30='All raw fills/position marks/daily MTM/weekly aggregates independently recomputed from frozen10/30 OHLCV/closeOI by raw core')

def audit(path,start,freeze,checkpoint):
 started=time.monotonic();sha,hashcounts=install_cache();f=load(freeze);sc=scope(f);ok(start in sc['starts'] and f['cutoff']=='2026-10-30','new59_scope');data=Path(f['data_directory']);cp=load(checkpoint);ok(cp['schema']=='stage014_checked_reserve_run_v1' and cp['method']=='fresh_engine' and cp['reused'] is False and cp['start']==start and cp['arm']=='C' and cp['end']==f['cutoff'] and cp['source_head']==f['source_head'] and cp['freeze_sha256']==sha(freeze) and cp['path']==str(path),'checkpoint_frozen_fresh_identity');ok(cp['files_sha256']=={str(p):sha(p) for p in path.iterdir() if p.is_file()},'checkpoint_complete_output_binding')
 parameters=parameter_audit(path,start,data);oldaudit.checks=0;fn,adapter=funding_adapter(data);r=fn(path,'C',start,f['cutoff'],freeze,None);raw=pd.read_csv(path/'daily.csv');bridge=pd.read_csv(path/'reserve_daily.csv');fills=pd.read_csv(path/'trades.csv');positions=pd.read_csv(path/'positions.csv',usecols=['vt_symbol','start_pos','end_pos']);ok(not fills.vt_symbol.isin(FORBIDDEN).any() and not positions.loc[positions.start_pos.ne(0)|positions.end_pos.ne(0),'vt_symbol'].isin(FORBIDDEN).any(),'four_nonmain_invalid_symbols_never_filled_or_held')
 PnL=raw.net_pnl.cumsum().to_numpy();T=bridge.cumulative_transfer.to_numpy();E=150000.+PnL+T;R=150000.-T;W=300000.+PnL;near(E,bridge.trading_account_equity,'E150_plus_PnL_plus_T');near(R,bridge.reserve_balance,'R150_minus_T');near(W,bridge.total_account_equity,'W300_plus_PnL');near(E+R,W,'full_daily_conservation');ok((R>=-1e-6).all(),'no_reserve_overdraft');near(r['metrics']['rounds']['closed_net_pnl']+r['metrics']['open_round_net_mtm'],PnL[-1],'closed_rounds_plus_open_MTM_real_PnL')
 prefix=prefix_audit(path,LINE/'outputs/stage009_C_20150101_attempt001') if start=='2015-01-01' else None
 r.update(schema='stage014_independent_window_review_v1',status='PASS_WITH_LIMITATIONS',P0=0,P1=0,P2=0,failures=0,method='fresh_engine',reused=False,requested_start=start,arm='C',end=f['cutoff'],mature=mature(start,f['cutoff']),cohort_month=int(start[5:7]),account_display=account_metrics(E),real_net_pnl=float(PnL[-1]),stage014_parameter_review=parameters,stage014_checks=checks,scope_data_adapter=adapter,canary_prefix=prefix,hash_verification=hashcounts,source_files_sha256={str(p):sha(p) for p in path.iterdir() if p.is_file()},checkpoint_sha256=sha(checkpoint),auditor_source_sha256=sha(__file__),financial_replays=0,market_downloads=0,production_accesses=0,promotion_decision='NO_PROMOTION',seconds=time.monotonic()-started)
 return r

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--path',type=Path,required=True);ap.add_argument('--start',required=True);ap.add_argument('--freeze',type=Path,default=STAGES/'stage014_freeze.json');ap.add_argument('--checkpoint',type=Path);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();cp=a.checkpoint or BASE/'checkpoints'/f'{a.start}_C.json'
 if a.output.exists():raise ValueError('immutable_window_receipt_exists')
 r=audit(a.path,a.start,a.freeze,cp);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2,default=lambda x:x.item() if hasattr(x,'item') else str(x))+'\n');print(json.dumps({k:r[k] for k in ['status','requested_start','account_display','real_net_pnl','raw_core_checks','funding_checks','stage014_checks']},ensure_ascii=False,default=str))
if __name__=='__main__':main()
