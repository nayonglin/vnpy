"""Exact nonbinding coupling of the original C trading path with a 50k reserve.

No new financial run or fabricated candidate settings are produced.  Every
source byte, cash check and output remains bound to its original checkpoint.
"""
from pathlib import Path
import ast,math
import stage012_contract as contract
from stage012_contract import ROOT,LINE,STARTS,FRESH_STARTS,REUSE_STARTS,RESERVE_CAPITAL,ENGINE_CAPITAL,TOTAL_CAPITAL,sha,load,atomic_json,metric_close

FORBIDDEN={'reserve_balance','reserve_cumulative_transfer','total_account_equity'}

def reject_reserve_reads(source,name):
 tree=ast.parse(source,filename=str(name))
 for node in ast.walk(tree):
  value=node.attr if isinstance(node,ast.Attribute) else node.value if isinstance(node,ast.Constant) and isinstance(node.value,str) else ''
  if value in FORBIDDEN or value.startswith('research_reserve'):raise ValueError('stage012_parent_consumes_reserve:'+str(name)+':'+value)
 return True

def source_independence(source_paths=None):
 tools=LINE/'tools';old=ast.parse((tools/'stage009_reserve.py').read_text());new=ast.parse((tools/'stage012_reserve.py').read_text())
 changed=False
 for node in new.body:
  if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='RESERVE_INITIAL' for t in node.targets):
   if not isinstance(node.value,ast.Constant) or node.value.value!=RESERVE_CAPITAL:raise ValueError('stage012_reserve_constant_not50k')
   node.value.value=150000.;changed=True
 if not changed or ast.dump(old,include_attributes=False)!=ast.dump(new,include_attributes=False):raise ValueError('stage012_reserve_wrapper_has_nondeclared_delta')
 if source_paths is None:
  manifest=load(LINE/'outputs/stage009_C_20150101_attempt001/input_manifest.json')
  source_paths=[Path(p) for p in manifest if p.endswith('.py') and not Path(p).resolve().is_relative_to(LINE.resolve()) and not Path(p).name.startswith('test_')]
  expected=manifest
 else:expected=None
 checked={}
 for path in sorted(set(map(Path,source_paths))):
  h=sha(path)
  if expected is not None and expected.get(str(path))!=h:raise ValueError('stage012_parent_source_hash_changed:'+str(path))
  reject_reserve_reads(path.read_text(),path);checked[str(path.resolve())]=h
 return dict(accepted=True,wrapper_ast_only_reserve_constant_changed=True,parent_reserve_read_count=0,parent_sources_sha256=checked,reserve_wrapper_sources_sha256={str((tools/name).resolve()):sha(tools/name) for name in ['stage009_reserve.py','stage012_reserve.py']})

def prove_checks(checks,events,start):
 contract.validate_start(start);cum=0.;seen=set();positive=[];previous='';traces=[]
 for row in checks:
  day=str(row['date'])[:10];amount=float(row['transfer_amount']);before=float(row['trading_equity_before']);reserve_old=150000.-cum;reserve_new=RESERVE_CAPITAL-cum
  numbers=['trading_equity_before','trading_equity_after','reserve_before','reserve_after','transfer_amount','cumulative_transfer','raw_account_equity','total_account_equity','selected_volume_after_parent']
  if any(not math.isfinite(float(row[k])) for k in numbers) or amount<0 or day<start or day>contract.CUTOFF or day<previous or int(row['selected_volume_after_parent'])!=float(row['selected_volume_after_parent']) or int(row['selected_volume_after_parent'])<0:raise ValueError('stage012_invalid_nonbinding_check')
  if row.get('enabled') is not True or row.get('phase')!='before_parent_sizing':raise ValueError('stage012_nonbinding_check_wrong_phase_or_disabled')
  expected={'reserve_before':reserve_old,'reserve_after':reserve_old-amount,'cumulative_transfer':cum+amount,'trading_equity_after':before+amount,'raw_account_equity':before-cum,'total_account_equity':before+reserve_old}
  if any(not metric_close(row[k],v) for k,v in expected.items()):raise ValueError('stage012_nonbinding_old_cash_bridge_changed')
  eligible=row.get('eligible') is True and row.get('duplicate') is False
  if eligible:
   if row.get('entry_context') not in {'flat_entry','reverse_entry'} or row.get('weekly_stop_valid') is not True or row.get('range_would_block') is True:raise ValueError('stage012_nonbinding_ineligible_source_check')
   signal=row.get('signal');direction=row.get('direction')
   if signal not in {'long_case1a','long_case2','short_case1a'} or direction not in {'long','short'} or not str(signal).startswith(direction+'_'):raise ValueError('stage012_nonbinding_wrong_signal')
   if direction=='short' and (row.get('range_checked') is not True or row.get('range_would_block') is not False):raise ValueError('stage012_nonbinding_C_gate_not_proven')
   if row['candidate_key'] in seen:raise ValueError('stage012_nonbinding_duplicate_candidate')
   seen.add(row['candidate_key']);wanted=min(max(ENGINE_CAPITAL-before,0.),reserve_old)
  else:wanted=0.
  if not metric_close(amount,wanted) or amount>reserve_new+1e-6 or not metric_close(amount,min(max(ENGINE_CAPITAL-before,0.),reserve_new) if eligible else 0.):raise ValueError('stage012_reserve50k_binds_cannot_reuse')
  if before+amount<=0 and int(row['selected_volume_after_parent'])!=0:raise ValueError('stage012_nonpositive_equity_has_purchase_power')
  if amount>0:positive.append(row)
  traces.append(dict(date=day,candidate_key=row['candidate_key'],original_transfer=amount,candidate_transfer=amount,candidate_reserve_before=reserve_new,candidate_reserve_after=reserve_new-amount,unchanged_trading_equity_before=before,unchanged_trading_equity_after=before+amount,unchanged_selected_volume=int(row['selected_volume_after_parent'])))
  cum+=amount;previous=day
 if len(positive)!=len(events):raise ValueError('stage012_nonbinding_event_count_changed')
 for index,(check,event) in enumerate(zip(positive,events)):
  if event.get('event_id')!=index+1 or event.get('candidate_key')!=check['candidate_key'] or any(not metric_close(event[k],check[k]) for k in ['transfer_amount','trading_equity_before','trading_equity_after','reserve_before','reserve_after','cumulative_transfer','raw_account_equity','total_account_equity']):raise ValueError('stage012_nonbinding_event_not_actual_check')
 return dict(accepted=True,check_count=len(checks),event_count=len(events),cumulative_transfer=cum,reserve_balance_end=RESERVE_CAPITAL-cum,all_original_transfers_payable=True,all_selected_volumes_unchanged=True,check_coupling=traces)

def adjusted_events(events):
 result=[]
 for row in events:
  out=dict(row)
  for key in ['reserve_before','reserve_after','total_account_equity']:out[key]=float(out[key])-100000.
  result.append(out)
 return result

def prove_nonbinding(freeze,start,job=None,source_proof=None):
 import pandas as pd
 import numpy as np
 if start not in REUSE_STARTS:raise ValueError('stage012_fixed_reuse_window_required')
 if source_proof is not None and (source_proof.get('accepted') is not True or source_proof.get('wrapper_ast_only_reserve_constant_changed') is not True or source_proof.get('parent_reserve_read_count')!=0 or not source_proof.get('parent_sources_sha256') or not source_proof.get('reserve_wrapper_sources_sha256')):raise ValueError('stage012_source_independence_required')
 actual_source_proof=source_independence()
 if source_proof is not None and source_proof!=actual_source_proof:raise ValueError('stage012_source_independence_proof_changed')
 source_proof=actual_source_proof;expected_job=contract.baseline_job(freeze,'C',start,verify=job is None)
 if job is not None and job!=expected_job:raise ValueError('stage012_baseline_job_not_actual')
 job=expected_job;p=Path(job['path'])
 for name,h in job['files_sha256'].items():
  if sha(name)!=h:raise ValueError('stage012_reuse_output_changed:'+name)
 for mapping in ['parent_sources_sha256','reserve_wrapper_sources_sha256']:
  for name,h in source_proof[mapping].items():
   if sha(name)!=h:raise ValueError('stage012_reuse_source_changed:'+name)
 settings=load(p/'actual_strategy_settings.json');effective=load(p/'effective_parameters.json');contract.settings_equivalent(settings,settings,effective,effective);contract.validate_entry_tiers(pd.read_csv(p/'entry_risk.csv'))
 pre=load(p/'preflight.json')
 if pre.get('short_price_range_gate_enabled') is not True or pre.get('reserve_topup_enabled') is not True or pre.get('data_identity')!=freeze['data_identity']:raise ValueError('stage012_reuse_wrong_baseline_gate_or_data')
 checks=load(p/'reserve_checks.json');events=load(p/'reserve_events.json');coupling=prove_checks(checks,events,start)
 raw=pd.read_csv(p/'daily.csv');bridge=contract.reserve_daily_bridge(raw,adjusted_events(events),start);old=pd.read_csv(p/'reserve_daily.csv')
 for key in ['raw_account_equity','cumulative_transfer','trading_account_equity','net_pnl','slippage','commission','trade_count']:
  if any(not metric_close(a,b) for a,b in zip(bridge[key],old[key])) or len(bridge)!=len(old):raise ValueError('stage012_nonbinding_trading_path_changed:'+key)
 for key in ['reserve_balance','total_account_equity']:
  if any(not metric_close(a,b-100000.) for a,b in zip(bridge[key],old[key])):raise ValueError('stage012_nonbinding_auxiliary_wealth_bridge_changed:'+key)
 wealth=bridge.total_account_equity;ret=wealth.pct_change().replace([np.inf,-np.inf],np.nan).fillna(0.);std=float(ret.std(ddof=1))
 metrics=dict(end_equity=float(wealth.iloc[-1]),total_return_pct=(float(wealth.iloc[-1])/TOTAL_CAPITAL-1)*100.,max_dd_pct=float(((wealth/wealth.cummax()-1)*100.).min()),sharpe=float(ret.mean()/std*math.sqrt(252.)) if math.isfinite(std) and std>0 else 0.,total_slippage=float(raw.slippage.sum()),total_trade_count=float(raw.trade_count.sum()),account_capital=TOTAL_CAPITAL,initial_capital=TOTAL_CAPITAL,equity_basis='total_account_equity')
 old_metrics=load(p/'metrics.json');raw_metrics={k:old_metrics[k] for k in ['end_equity','total_return_pct','max_dd_pct','sharpe','total_slippage','total_trade_count']}
 return dict(schema='stage012_proven_nonbinding_reuse_v1',accepted=True,method='proven_nonbinding_reuse',reused=True,source_path=str(p.resolve()),path=str(p.resolve()),start=start,arm='C',end=contract.CUTOFF,actual_start=str(bridge.date.iloc[0]),actual_end=str(bridge.date.iloc[-1]),trading_days=len(bridge),financial_replays=0,engine_initial_capital=ENGINE_CAPITAL,reserve_initial_capital=RESERVE_CAPITAL,total_initial_capital=TOTAL_CAPITAL,metrics=metrics,raw_metrics=raw_metrics,cumulative_transfer=coupling['cumulative_transfer'],reserve_balance_end=coupling['reserve_balance_end'],transfer_event_count=len(events),baseline_checkpoint=job['checkpoint'],baseline_checkpoint_sha256=job['checkpoint_sha256'],source_files_sha256=job['files_sha256'],source_independence=source_proof,coupling=coupling,trading_rows=len(bridge),all_raw_trading_positions_orders_PnL_costs_unchanged=True,auxiliary_wealth_offset=-100000.,production_qualified=False)

def make_reuse_checkpoint(checkpoint,freeze,freeze_sha,start,job=None,source_proof=None):
 if Path(checkpoint).exists():raise ValueError('stage012_reuse_checkpoint_exists')
 result=prove_nonbinding(freeze,start,job,source_proof);result.update(freeze_sha256=freeze_sha,source_head=freeze['source_head'],checkpoint_key=contract.checkpoint_key(freeze,freeze_sha,'C',start));atomic_json(checkpoint,result);return result

def read_reuse_checkpoint(checkpoint,freeze,freeze_sha,start,job=None,source_proof=None):
 r=load(checkpoint)
 if r.get('freeze_sha256')!=freeze_sha or r.get('source_head')!=freeze['source_head'] or r.get('checkpoint_key')!=contract.checkpoint_key(freeze,freeze_sha,'C',start):raise ValueError('stage012_reuse_checkpoint_identity_changed')
 expected=prove_nonbinding(freeze,start,job,source_proof);expected.update(freeze_sha256=freeze_sha,source_head=freeze['source_head'],checkpoint_key=contract.checkpoint_key(freeze,freeze_sha,'C',start))
 if r!=expected:raise ValueError('stage012_reuse_checkpoint_proof_changed')
 return r
