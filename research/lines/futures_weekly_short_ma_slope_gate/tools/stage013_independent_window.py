"""Independent fresh100k audit and proved-reuse receipts; never runs finance.

Raw150k FIFO/MTM/fee/calendar/weekly/next-open audit remains exactly the accepted
Stage008 function with the accepted Stage009 auxiliary Sharpe adapter. A narrow
explicit source adapter changes only the surrounding wallet's R150k/W300k to
R100k/W250k. Original files/functions and every earlier-stage file remain unchanged.
"""
from pathlib import Path
from copy import deepcopy
import argparse,ast,hashlib,inspect,json,math,time
import numpy as np
import pandas as pd
import stage009_independent_window as oldaudit
ROOT=Path(__file__).resolve().parents[4];LINE=ROOT/'research/lines/futures_weekly_short_ma_slope_gate';STAGES=LINE/'stages';BASE=LINE/'outputs/stage013_multistart';checks=0
TIERS={'regular':.018,'breakout':.018,'ma_cross_breakout':.018,'volume_open_interest_surge':.06,'open_interest_surge':.06,'open_interest_decline':.025}
def ok(v,label):
 global checks
 checks+=1
 if not v:raise AssertionError(label)
def near(a,b,label):ok(math.isfinite(float(a)) and math.isfinite(float(b)) and math.isclose(float(a),float(b),rel_tol=1e-10,abs_tol=1e-6),label)
def plain_sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def load(p):return json.loads(Path(p).read_text())
def fingerprint(p):
 s=Path(p).stat();return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
def install_cache():
 admission=load(STAGES/'stage013_independent_reuse_admission.json');p=Path(admission['source_hash_cache']);ok(plain_sha(p)==admission['source_hash_cache_sha256'],'new_stage013_hash_cache_binding');cache=load(p)['files'];counts={'admitted_stat_hits':0,'new_hashes':0,'new_bytes':0}
 def sha(q):
  q=str(Path(q).resolve());s=fingerprint(q);before=cache.get(q)
  if before is not None and before['stat']==s:counts['admitted_stat_hits']+=1;return before['sha256']
  h=plain_sha(q);ok(s==fingerprint(q),'stable_hash_read:'+q)
  if before is not None:ok(h==before['sha256'],'admitted_content_drift:'+q)
  cache[q]={'sha256':h,'stat':s};counts['new_hashes']+=1;counts['new_bytes']+=Path(q).stat().st_size;return h
 oldaudit.sha=sha;oldaudit.raw_audit.sha=sha;return sha,counts
def frozen_scope(f):
 return f['candidate_windows']==f['planned_arm_windows']==23 and f['planned_financial_replays']==4 and f['planned_proven_reuse']==19 and f['arms']==['C']
def funding_adapter():
 source=inspect.getsource(oldaudit.audit);original=ast.parse(source)
 changes=[
  ("frozen['planned_arm_windows']==46 and frozen['planned_financial_replays']==46","_stage013_frozen_scope(frozen)",1),
  ("frozen['engine_initial_capital']==frozen['reserve_initial_capital']==150000 and frozen['total_initial_capital']==300000","frozen['engine_initial_capital']==150000 and frozen['reserve_initial_capital']==100000 and frozen['total_initial_capital']==250000",1),
  ("pre['engine_initial_capital']==pre['reserve_initial_capital']==150000 and pre['total_initial_capital']==300000","pre['engine_initial_capital']==150000 and pre['reserve_initial_capital']==100000 and pre['total_initial_capital']==250000",1),
  ('reserve=150000.;eventindex=0','reserve=100000.;eventindex=0',1),
  ("rawvalue+150000.,'wealth_does_not_change_on_transfer'","rawvalue+100000.,'wealth_does_not_change_on_transfer'",1),
  ('R=150000.-cumulative;W=float(d.account_equity)+150000.','R=100000.-cumulative;W=float(d.account_equity)+100000.',1),
  ("0<=cum_s<=150000,'snapshot_flow_bounds'","0<=cum_s<=100000,'snapshot_flow_bounds'",1),
  ("150000.-cum_s,'snapshot_true_reserve'","100000.-cum_s,'snapshot_true_reserve'",1),
  ("raw_s+150000.,'snapshot_true_wealth'","raw_s+100000.,'snapshot_true_wealth'",1),
  ('300000.','250000.',6),
 ]
 proof=[]
 for old,new,count in changes:
  ok(source.count(old)==count,'exact_wallet_adapter_expression_count:'+old);source=source.replace(old,new);proof.append({'old':old,'new':new,'occurrences':count})
 tree=ast.parse(source);tree.body[0].name='_stage013_funding_audit';env=vars(oldaudit);env['_stage013_frozen_scope']=frozen_scope;exec(compile(ast.fix_missing_locations(tree),str(Path(__file__))+'::explicit_wallet100k_adapter','exec'),env)
 return env['_stage013_funding_audit'],dict(original_AST_sha256=hashlib.sha256(ast.dump(original,include_attributes=False).encode()).hexdigest(),adapted_AST_sha256=hashlib.sha256(ast.dump(tree,include_attributes=False).encode()).hexdigest(),explicit_replacements=proof,raw150k_FIFOMTM_core_unchanged=True,ordinary150k_funding_floor_unchanged=True,original_auditor_file_sha256=plain_sha(Path(oldaudit.__file__)))
def parameter_audit(path,oldpath):
 s=load(path/'actual_strategy_settings.json');old=load(oldpath/'actual_strategy_settings.json');e=load(path/'effective_parameters.json');oe=load(oldpath/'effective_parameters.json');ok(s==old and e==oe and len(s)==1,'all_settings_and_effective_exact_original_C');a=s[0]['actual']
 for k,v in [('risk_ratio_of_total_assets',.018),('risk_ratio_breakout',.018),('risk_ratio_ma_cross_breakout',.018),('risk_ratio_volume_open_interest_surge',.06),('risk_ratio_open_interest_surge',.06),('risk_ratio_open_interest_decline',.025),('min_risk_per_trade',1000.),('oi_price_confirm_risk_restore_multiplier',2.),('directional_30d_risk_boost_multiplier',1.5),('directional_30d_low_volume_risk_multiplier',.5)]:near(a[k],v,'original_parameter:'+k)
 rows=pd.read_csv(path/'entry_risk.csv');ok(not rows.empty,'actual_entry_risk_nonempty')
 for r in rows.itertuples():
  ok(r.risk_mode in TIERS,'preserved_signal_classification');near(r.risk_ratio,TIERS[r.risk_mode],'actual_original_risk_tier');before=min(float(a['max_risk_per_trade']),max(1000.,float(r.limited_balance)*TIERS[r.risk_mode]))*max(0.,float(r.risk_multiplier));near(r.risk_amount_before_directional_30d_boost,before,'independent_risk_budget_floor_no_second04');near(r.target_risk_amount,before*float(r.directional_30d_risk_boost_multiplier),'independent_target_risk');want=2. if int(r.oi_price_confirm_risk_restore_applied) else 1.;near(r.risk_multiplier,want,'preserved_OI_applied_double');near(r.oi_price_confirm_risk_restore_effective_multiplier,want,'preserved_OI_effective_double');wantdir=1.5 if int(r.directional_30d_risk_boost_applied) else .5 if int(r.directional_30d_low_volume_discount_applied) else 1.;near(r.directional_30d_risk_boost_multiplier,wantdir,'preserved_directional_multiplier')
 return {'all_actual_settings_unchanged':True,'all_effective_parameters_unchanged':True,'actual_risk_tiers':TIERS,'entry_rows':len(rows),'risk_mode_counts':rows.risk_mode.value_counts().to_dict()}
def curve(e,initial,positive=False):
 e=np.asarray(e,float);prev=np.r_[initial,e[:-1]];valid=(prev>0) if positive else (prev!=0);defined=bool(np.isfinite(e).all() and valid.all());r=(e-prev)/prev if defined else None;defined=defined and bool(np.isfinite(r).all());std=float(r.std(ddof=1)) if defined else 0.
 return dict(initial_capital=initial,end_equity=float(e[-1]),total_return_pct=float((e[-1]/initial-1)*100),max_dd_pct=float((e/np.maximum.accumulate(np.r_[initial,e])[1:]-1).min()*100),sharpe=float(r.mean()/std*np.sqrt(252)) if defined and std>0 else 0.,returns_defined=defined)
def prefix_audit(path,oldpath,start,admission):
 witness=next(w for w in admission['windows'] if w['start']==start)['first_binding'];ok(witness is not None,'fresh_window_must_have_binding_witness');day=witness['date'];new=pd.read_csv(path/'daily.csv',float_precision='round_trip');old=pd.read_csv(oldpath/'daily.csv',float_precision='round_trip');a=new.loc[new.date.astype(str).str[:10].lt(day)];b=old.loc[old.date.astype(str).str[:10].lt(day)];ok(a.date.astype(str).tolist()==b.date.astype(str).tolist(),'binding_prefix_calendar')
 for name in ['account_equity','net_pnl','slippage','commission','trade_count','total_margin_exact']:ok(np.allclose(a[name],b[name],rtol=1e-10,atol=1e-6),'binding_prefix_daily:'+name)
 na=pd.read_csv(path/'reserve_daily.csv');oa=pd.read_csv(oldpath/'reserve_daily.csv');na=na.loc[na.date.astype(str).str[:10].lt(day)];oa=oa.loc[oa.date.astype(str).str[:10].lt(day)]
 for name in ['trading_account_equity','cumulative_transfer','transfer_amount']:ok(np.allclose(na[name],oa[name],rtol=1e-10,atol=1e-6),'binding_prefix_wallet:'+name)
 fa=pd.read_csv(path/'trades.csv');fb=pd.read_csv(oldpath/'trades.csv');fa=fa.loc[fa.trading_date.lt(day)];fb=fb.loc[fb.trading_date.lt(day)];cols=['trade_id','order_id','vt_symbol','trading_date','direction','offset','price','volume'];ok(fa[cols].reset_index(drop=True).equals(fb[cols].reset_index(drop=True)),'binding_prefix_actual_fills_exact')
 row=next(r for r in load(path/'reserve_checks.json') if r['candidate_key']==witness['candidate_key']);near(row['transfer_amount'],witness['new100k_transfer'],'first_binding_actual_partial_transfer');near(row['cumulative_transfer'],100000.,'first_binding_exhausts_exact100k')
 return dict(first_binding=witness,unchanged_daily_rows_before_binding=len(a),unchanged_fill_rows_before_binding=len(fa),actual_first_binding_transfer=row['transfer_amount'],all_trading_fields_identical_before_binding=True,after_binding='Real fresh engine independently audited; no old-curve truncation or scaling')
def audit(path,start,freeze,checkpoint):
 started=time.monotonic();sha,hash_counts=install_cache();f=load(freeze);fsha=sha(freeze);cp=load(checkpoint);admission=load(STAGES/'stage013_independent_reuse_admission.json');oldreg=load(f['baseline_registry']);job=oldreg['jobs'][start+'|C'];oldpath=Path(job['path']);method=cp['method'];ok(cp['start']==start and cp['arm']=='C' and cp['freeze_sha256']==fsha and cp['source_head']==f['source_head'],'checkpoint_exact_frozen_scope');ok(frozen_scope(f) and f['reserve_initial_capital']==100000 and f['total_initial_capital']==250000,'only100k_reserve_250k_auxiliary_wealth')
 for q,h in f['source_files_sha256'].items():ok(sha(q)==h,'frozen_financial_source:'+q)
 parameters=parameter_audit(path,oldpath)
 if method=='fresh_engine':
  ok(start in admission['fresh_starts'] and cp['reused'] is False and path.resolve()!=oldpath.resolve(),'four_true_fresh_engines');oldaudit.checks=0;fn,adapter=funding_adapter();r=fn(path,'C',start,f['cutoff'],freeze,None);prefix=prefix_audit(path,oldpath,start,admission);r.update(wallet100k_adapter=adapter,first_binding_prefix=prefix,method=method,reused=False)
 elif method=='proven_nonbinding_reuse':
  ok(start in admission['reuse_starts'] and cp['reused'] is True and path.resolve()==oldpath.resolve(),'nineteen_true_proven_reuses');proof=next(w for w in admission['windows'] if w['start']==start);ok(proof['nonbinding'] and proof['first_binding'] is None,'whole_check_induction_not_terminal_T_only');ok(cp['source_files_sha256']==job['files_sha256'],'reuse_all_real_ledger_files_exact');coupling=cp['coupling'];ok(coupling['accepted'] is True and coupling['check_count']==proof['signal_checks'] and coupling['event_count']==proof['positive_transfer_events'],'reuse_implementation_check_counts');near(coupling['cumulative_transfer'],proof['cumulative_transfer'],'reuse_implementation_cumulative_T');near(coupling['reserve_balance_end'],100000.-proof['cumulative_transfer'],'reuse_implementation_R100')
  oldr=load(STAGES/'stage009_independent_receipts'/f'{start}_C.json');ok(oldr['source_files_sha256']==job['files_sha256'],'original_complete_finance_receipt_bound')
  for q,h in job['files_sha256'].items():ok(sha(q)==h,'original_full_finance_ledger_unchanged:'+q)
  r=deepcopy(oldr);raw=pd.read_csv(path/'daily.csv');E=pd.read_csv(path/'reserve_daily.csv').trading_account_equity.to_numpy();metrics=curve(raw.account_equity.to_numpy()+100000.,250000.);metrics.update(total_slippage=oldr['metrics']['total_slippage'],total_trade_count=oldr['metrics']['total_trade_count'],rounds=oldr['metrics']['rounds'],open_round_net_mtm=oldr['metrics']['open_round_net_mtm']);r.update(metrics=metrics,method=method,reused=True,reused_engine_source_head=oldr['frozen_source_head'],frozen_source_head=f['source_head'],freeze_sha256=fsha,raw_core_checks=0,funding_checks=0,reuse_independent_proof=proof,reuse_admission_sha256=sha(STAGES/'stage013_independent_reuse_admission.json'),reserve_diagnostics={**oldr['reserve_diagnostics'],'reserve_end':100000.-proof['cumulative_transfer'],'total_end':float(raw.account_equity.iloc[-1]+100000.)},raw_metrics=oldr['raw_metrics'])
 else:raise AssertionError('unknown_candidate_method')
 raw=pd.read_csv(path/'daily.csv');cum=raw.net_pnl.cumsum().to_numpy();events=load(path/'reserve_events.json');amounts={}
 for e in events:amounts[str(e['date'])[:10]]=amounts.get(str(e['date'])[:10],0.)+float(e['transfer_amount'])
 T=np.array([amounts.get(str(d)[:10],0.) for d in raw.date]).cumsum();E=150000.+cum+T;R=100000.-T;W=250000.+cum;ok(np.allclose(E+R,W,rtol=1e-10,atol=1e-6) and (R>=-1e-6).all(),'all_days_E_R_W250k_conservation');near(r['metrics']['rounds']['closed_net_pnl']+r['metrics']['open_round_net_mtm'],cum[-1],'real_PnL_complete_round_plus_open_MTM');account=curve(E,150000.,True);account['definition']='E/150000 includes transferred deposits; unused100k outside; not strategy return';margin=np.divide(raw.total_margin_exact.to_numpy()*165.,E,out=np.full_like(E,np.nan),where=E>0)
 r.update(schema='stage013_independent_window_review_v1',status='PASS_WITH_LIMITATIONS',P0=0,P1=0,P2=0,failures=0,path=str(path),arm='C',requested_start=start,end=f['cutoff'],account_display=account,real_net_pnl=float(cum[-1]),stage013_parameter_review=parameters,stage013_checks=checks,hash_verification=hash_counts,source_files_sha256={str(p):sha(p) for p in path.iterdir() if p.is_file()},checkpoint_sha256=sha(checkpoint),auditor_source_sha256=sha(__file__),financial_replays=0,market_downloads=0,production_accesses=0,promotion_decision='NO_PROMOTION',seconds=time.monotonic()-started,risk=dict(nonpositive_trading_equity_days=int((E<=0).sum()),nonpositive_total_equity_days=int((W<=0).sum()),configured_margin_max_trading_pct=float(np.nanmax(margin)) if np.isfinite(margin).any() else None,configured_margin_over100_trading_days=int((margin>100).sum()),minimum_trading_equity=float(E.min()),minimum_total_equity=float(W.min())))
 return r
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--path','--run-dir',type=Path,required=True);ap.add_argument('--arm',choices=['C'],default='C');ap.add_argument('--start',required=True);ap.add_argument('--freeze',type=Path,default=STAGES/'stage013_freeze.json');ap.add_argument('--checkpoint',type=Path);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args();cp=args.checkpoint or BASE/'checkpoints'/f'{args.start}_C.json'
 if args.output.exists():raise ValueError('immutable_independent_receipt_exists')
 r=audit(args.path,args.start,args.freeze,cp);args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(r,ensure_ascii=False,indent=2,default=lambda x:x.item() if hasattr(x,'item') else str(x))+'\n');print(json.dumps({k:r[k] for k in ['status','method','requested_start','metrics','stage013_checks','raw_core_checks','funding_checks','seconds']},ensure_ascii=False,default=str))
if __name__=='__main__':main()
