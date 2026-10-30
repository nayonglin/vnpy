"""Frozen 59 fresh five-month start-to-cutoff research windows and immutable checkpoints."""
from pathlib import Path
from datetime import date
import stage009_contract as baseline
import hashlib,json,math,os
ROOT=Path(__file__).resolve().parents[4]
LINE=ROOT/'research/lines/futures_weekly_short_ma_slope_gate'
MONTHS=(1,3,6,9,11)
CUTOFF='2026-10-30'
STARTS=tuple(f'{y}-{m:02d}-01' for y in range(2015,2027) for m in MONTHS if f'{y}-{m:02d}-01'<=CUTOFF)
MATURE_STARTS=tuple(s for s in STARTS if f'{int(s[:4])+1}{s[4:]}'<=CUTOFF)
OBSERVATION_STARTS=tuple(s for s in STARTS if s not in MATURE_STARTS)
ENGINE_CAPITAL=150000.;RESERVE_CAPITAL=150000.;TOTAL_CAPITAL=300000.
IDENTITY_KEYS={'daily_sqlite_sha256','mapping_sha256','physical_epoch_daily_sha256','receipt_sha256'}
DATA_FILES=dict(daily_sqlite_sha256='daily.sqlite',mapping_sha256='mapping.csv',physical_epoch_daily_sha256='physical_epoch_daily.csv',receipt_sha256='receipt.json')
BASELINE_IDENTITIES=('baseline_freeze','baseline_registry','baseline_delivery_manifest','baseline_reporting_manifest')
MIN_FREE_DISK_BYTES=8*1024**3
ESTIMATED_BYTES_PER_RUN=256*1024**2

def required_financial_sources():
 tools=LINE/'tools';stages=LINE/'stages'
 return [tools/name for name in ['run_stage014.py','stage014_contract.py','stage014_reserve.py','stage014_coordinator.py','test_stage014_reserve.py','test_stage014_contract.py','test_stage014_runner.py','test_stage014_coordinator.py']]+[stages/name for name in ['20261030_stage014_five_starts_design.md','20261030_stage014_implementation_plan.md']]

def validate_freeze(path):
 p=Path(path).resolve();f=load(p)
 expected={'schema':'stage014_frozen_five_starts_R150_v1','start_months':list(MONTHS),'starts':list(STARTS),'arms':['C'],'cutoff':CUTOFF,'planned_arm_windows':59,'planned_financial_replays':59,'planned_reused_runs':0,'mature_window_count':54,'observation_window_count':5,'engine_initial_capital':ENGINE_CAPITAL,'reserve_initial_capital':RESERVE_CAPITAL,'total_initial_capital':TOTAL_CAPITAL,'max_workers':2,'canary_start':'2015-01-01','min_free_disk_bytes':MIN_FREE_DISK_BYTES,'estimated_bytes_per_run':ESTIMATED_BYTES_PER_RUN}
 for key,value in expected.items():
  if f.get(key)!=value:raise ValueError('stage014_frozen_scope_changed:'+key)
 head=f.get('source_head','')
 if len(head)!=40 or any(c not in '0123456789abcdef' for c in head):raise ValueError('stage014_frozen_head_required')
 known={'baseline_freeze':LINE/'stages/stage009_freeze.json','baseline_registry':LINE/'outputs/stage009_multistart/registry.json','baseline_delivery_manifest':LINE/'stages/stage009_delivery_manifest.json','baseline_reporting_manifest':LINE/'stages/stage010_delivery_manifest.json'}
 for key in BASELINE_IDENTITIES:
  if Path(f.get(key,'')).resolve()!=known[key].resolve() or sha(f[key])!=f.get(key+'_sha256'):raise ValueError('stage014_baseline_identity_changed:'+key)
 old,old_sha=baseline.validate_freeze(f['baseline_freeze'])
 if old_sha!=f['baseline_freeze_sha256']:raise ValueError('stage014_baseline_freeze_changed')
 sources=f.get('source_files_sha256',{})
 if not isinstance(sources,dict) or not sources:raise ValueError('stage014_frozen_sources_required')
 resolved={str((Path(k) if Path(k).is_absolute() else ROOT/k).resolve()):v for k,v in sources.items()}
 if not {str(q.resolve()) for q in required_financial_sources()}<=set(resolved):raise ValueError('stage014_required_financial_source_missing')
 for name,h in old['source_files_sha256'].items():
  q=Path(name);q=q if q.is_absolute() else ROOT/q
  if resolved.get(str(q.resolve()))!=h:raise ValueError('stage014_inherited_source_missing:'+name)
 for name,h in resolved.items():
  if not Path(name).is_file() or sha(name)!=h:raise ValueError('stage014_frozen_source_changed:'+name)
 directory=Path(f.get('data_directory','')).resolve()
 if directory!= (LINE/'outputs/data_stage014_20261030/data_approved').resolve() or set(f.get('data_identity',{}))!=IDENTITY_KEYS:raise ValueError('stage014_new_data_snapshot_required')
 for key,name in DATA_FILES.items():
  if sha(directory/name)!=f['data_identity'][key]:raise ValueError('stage014_frozen_data_changed:'+name)
 receipt=load(directory/'receipt.json')
 if receipt.get('date_end')!=CUTOFF or receipt.get('data_ready') is not True or receipt.get('data_ready_for_bounded_replay') is not True:raise ValueError('stage014_latest_complete_data_not_admitted')
 if not f.get('data_admission') or sha(f['data_admission'])!=f.get('data_admission_sha256'):raise ValueError('stage014_independent_data_admission_required')
 admission=load(f['data_admission'])
 if admission.get('accepted') is not True or admission.get('data_identity')!=f['data_identity']:raise ValueError('stage014_independent_data_admission_mismatch')
 return f,sha(p)

def validate_run(path,freeze,arm,start):
 if arm!='C':raise ValueError('stage014_C_only')
 validate_start(start);p=Path(path);info=_validate_reserve_run(p,freeze,arm,start)
 import run_stage014 as runner
 settings=load(p/'actual_strategy_settings.json');reference=load(runner.FROZEN/'R_attempt003/actual_strategy_settings.json');mapping=Path(freeze['data_directory'])/'mapping.csv';approved=load(Path(freeze['data_directory'])/'receipt.json').get('approved_new_metadata',{})
 for field in ['setting','actual']:runner.normalize_settings(settings[0][field],reference[0][field],mapping,approved,start)
 runner.normalize_effective(load(p/'effective_parameters.json'),load(runner.FROZEN/'R_attempt003/effective_parameters.json'),mapping,approved,start)
 pre=load(p/'preflight.json')
 if pre.get('method')!='fresh_engine' or pre.get('new_five_start_scope') is not True:raise ValueError('stage014_run_must_be_new_fresh_engine')
 manifest=load(p/'input_manifest.json');expected={str((Path(k) if Path(k).is_absolute() else ROOT/k).resolve()):v for k,v in freeze['source_files_sha256'].items()}
 expected.update({str((Path(freeze['data_directory'])/name).resolve()):freeze['data_identity'][key] for key,name in DATA_FILES.items()})
 expected.update({str(Path(freeze[k]).resolve()):freeze[k+'_sha256'] for k in BASELINE_IDENTITIES})
 expected[str(Path(freeze['data_admission']).resolve())]=freeze['data_admission_sha256']
 if not pre.get('freeze_path'):raise ValueError('stage014_actual_freeze_path_required')
 expected[str(Path(pre['freeze_path']).resolve())]=pre['freeze_sha256']
 for name,h in expected.items():
  if manifest.get(name)!=h or not Path(name).is_file() or sha(name)!=h:raise ValueError('stage014_run_input_missing_or_changed:'+name)
 return {**info,'method':'fresh_engine','source_path':str(p.resolve()),'mature':start in MATURE_STARTS,'cohort_month':int(start[5:7])}
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for c in iter(lambda:f.read(4194304),b''):h.update(c)
 return h.hexdigest()
def load(path):return json.loads(Path(path).read_text())
def atomic_json(path,obj):
 p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name(p.name+'.tmp');tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n');os.replace(tmp,p)
def validate_start(start):
 if start not in STARTS:raise ValueError('stage014_start_not_in_frozen59')
 return start

def first_trading_day(start,calendar):
 validate_start(start);days=sorted({str(x)[:10] for x in calendar if start<=str(x)[:10]<=CUTOFF})
 if not days:raise ValueError('stage014_empty_requested_calendar')
 return days[0]
def metric_close(a,b):
 return math.isfinite(float(a)) and math.isfinite(float(b)) and math.isclose(float(a),float(b),rel_tol=1e-10,abs_tol=1e-6)
def checkpoint_key(freeze,freeze_sha,arm,start):
 validate_start(start)
 if arm!='C':raise ValueError('stage014_C_only')
 return hashlib.sha256(json.dumps(dict(source_head=freeze['source_head'],freeze_sha256=freeze_sha,cutoff=freeze['cutoff'],arm=arm,start=start,engine_initial_capital=freeze.get('engine_initial_capital'),reserve_initial_capital=freeze.get('reserve_initial_capital'),total_initial_capital=freeze.get('total_initial_capital')),sort_keys=True).encode()).hexdigest()
def snapshot_dir(path):return {str(p.resolve()):sha(p) for p in sorted(Path(path).iterdir()) if p.is_file()}

def reserve_daily_bridge(raw,events,start):
 """Raw engine retains150k+PnL; internal transfers cancel in total wealth."""
 import pandas as pd
 import numpy as np
 validate_start(start);d=raw.copy();d['date']=pd.to_datetime(d.date).dt.strftime('%Y-%m-%d')
 if d.empty or d.date.duplicated().any() or not d.date.is_monotonic_increasing or d.date.iloc[0]<start or d.date.iloc[-1]>CUTOFF:raise ValueError('stage014_invalid_raw_calendar')
 for field in ['account_equity','net_pnl','slippage','commission','trade_count']:
  if field not in d or not np.isfinite(pd.to_numeric(d[field],errors='raise')).all():raise ValueError('stage014_nonfinite_raw_ledger:'+field)
 if not np.allclose(d.account_equity,ENGINE_CAPITAL+d.net_pnl.cumsum(),rtol=1e-10,atol=1e-6):raise ValueError('stage014_raw_equity_not150k_plus_real_PnL')
 amounts={};seen=set();cumulative=0.;previous_date=''
 for row in events:
  day=str(row['date'])[:10];event_id=str(row['event_id']);amount=float(row['transfer_amount']);before=float(row['trading_equity_before']);reserve=RESERVE_CAPITAL-cumulative
  if day<start or day not in set(d.date) or day<previous_date or event_id in seen:raise ValueError('stage014_event_date_order_or_duplicate')
  if not all(math.isfinite(float(row[k])) for k in ['transfer_amount','trading_equity_before','trading_equity_after','reserve_before','reserve_after','cumulative_transfer','raw_account_equity','total_account_equity']):raise ValueError('stage014_nonfinite_transfer')
  if amount<=0 or not metric_close(amount,min(max(ENGINE_CAPITAL-before,0.),reserve)) or amount>reserve+1e-6:raise ValueError('stage014_invalid_transfer_formula_or_reserve_overdraw')
  if row.get('entry_context') not in {'flat_entry','reverse_entry'} or row.get('phase')!='before_parent_sizing' or row.get('weekly_stop_valid') is not True or row.get('range_would_block') is True:raise ValueError('stage014_ineligible_transfer_event')
  if row.get('signal') not in {'long_case1a','long_case2','short_case1a'} or row.get('direction') not in {'long','short'} or row['signal'].split('_',1)[0]!=row['direction']:raise ValueError('stage014_invalid_native_transfer_signal')
  expected={'reserve_before':reserve,'reserve_after':reserve-amount,'trading_equity_after':before+amount,'cumulative_transfer':cumulative+amount,'raw_account_equity':before-cumulative,'total_account_equity':before-cumulative+RESERVE_CAPITAL}
  if any(not metric_close(row[k],v) for k,v in expected.items()):raise ValueError('stage014_transfer_conservation_failed')
  cumulative+=amount;seen.add(event_id);previous_date=day;amounts[day]=amounts.get(day,0.)+amount
 for row in events:
  if not metric_close(row['raw_account_equity'],d.loc[d.date.eq(str(row['date'])[:10]),'account_equity'].iloc[0]):raise ValueError('stage014_event_raw_equity_not_same_day_real_PnL')
 d=d.rename(columns={'account_equity':'raw_account_equity'});d['transfer_amount']=d.date.map(amounts).fillna(0.);d['cumulative_transfer']=d.transfer_amount.cumsum();d['trading_account_equity']=d.raw_account_equity+d.cumulative_transfer;d['reserve_balance']=RESERVE_CAPITAL-d.cumulative_transfer;d['total_account_equity']=d.raw_account_equity+RESERVE_CAPITAL
 if d.reserve_balance.lt(-1e-6).any() or not np.allclose(d.trading_account_equity+d.reserve_balance,d.total_account_equity,rtol=1e-10,atol=1e-6):raise ValueError('stage014_daily_conservation_failed')
 return d

def _validate_reserve_run(path,freeze,arm,start):
 import pandas as pd
 import numpy as np
 p=Path(path).resolve();raw_info=_validate_raw_run(p,freeze,arm,start);pre=load(p/'preflight.json');proof=load(p/'reserve_acceptance.json');events=load(p/'reserve_events.json');snapshots=load(p/'reserve_snapshots.json');checks=load(p/'reserve_checks.json')
 if pre.get('head')!=freeze['source_head'] or pre.get('reserve_topup_enabled') is not True or any(pre.get(k)!=v for k,v in [('engine_initial_capital',ENGINE_CAPITAL),('reserve_initial_capital',RESERVE_CAPITAL),('total_initial_capital',TOTAL_CAPITAL)]):raise ValueError('stage014_actual_capital_or_source_identity_mismatch')
 if proof.get('accepted') is not True or proof.get('enabled') is not True or proof.get('event_count')!=len(events) or proof.get('check_count')!=len(checks) or proof.get('snapshot_count')!=len(snapshots):raise ValueError('stage014_actual_reserve_proof_mismatch')
 raw=pd.read_csv(p/'daily.csv');bridge=reserve_daily_bridge(raw,events,start);actual=pd.read_csv(p/'reserve_daily.csv')
 snapshot_proof=validate_reserve_snapshots(bridge,snapshots,start);phase_proof=validate_event_daily_anchors(bridge,events,load(p/'reserve_fill_phases.json'));checks_proof=validate_reserve_checks(checks,events,arm,start)
 for name,value in [('snapshot_proof',snapshot_proof),('phase_proof',phase_proof),('checks_proof',checks_proof)]:
  if proof.get(name)!=value:raise ValueError('stage014_acceptance_proof_not_actual:'+name)
 expected_caps={'engine_initial_capital':ENGINE_CAPITAL,'strategy_capital_base':ENGINE_CAPITAL,'reserve_initial_capital':RESERVE_CAPITAL,'total_initial_capital':TOTAL_CAPITAL}
 if any(proof.get(k)!=v for k,v in expected_caps.items()):raise ValueError('stage014_acceptance_real_capital_changed')
 flags=proof.get('actual_risk_flags',{});required=['enable_portfolio_volatility_budget','enable_portfolio_volatility_budget_deleverage','enable_portfolio_overheat_cooldown','enable_portfolio_overheat_cooldown_deleverage','enable_portfolio_drawdown_gate','enable_portfolio_drawdown_deleverage','enable_risk_cluster_heat_gate','enable_risk_cluster_heat_deleverage','enable_risk_cluster_margin_cap']
 if set(flags)!=set(required) or any(type(v) is not bool for v in flags.values()) or flags!=pre.get('actual_reserve_risk_flags'):raise ValueError('stage014_missing_actual_risk_flag_identity')
 if any(flags[k] for k in required[:4]) or not all(flags[k] for k in required[-2:]):raise ValueError('stage014_original_risk_flags_changed')
 if actual.date.astype(str).str[:10].tolist()!=bridge.date.tolist():raise ValueError('stage014_reserve_calendar_mismatch')
 for k in ['raw_account_equity','cumulative_transfer','trading_account_equity','reserve_balance','total_account_equity','net_pnl','slippage','commission','trade_count']:
  if k not in actual or not np.allclose(actual[k],bridge[k],rtol=1e-10,atol=1e-6):raise ValueError('stage014_reserve_daily_bridge_changed:'+k)
 if not metric_close(actual.total_account_equity.iloc[0],TOTAL_CAPITAL) or not metric_close(actual.reserve_balance.iloc[0],RESERVE_CAPITAL):raise ValueError('stage014_not_fresh300k_two_buckets')
 for side in ['short','long']:
  q=load(p/(side+'_ma_slope_acceptance.json'))
  if q.get('enabled') is not False or q.get('decision_count')!=0 or q.get('applied_block_count')!=0:raise ValueError('stage014_MA_gate_not_disabled')
 terminal=load(p/'terminal.json');started=pd.Timestamp(terminal['started_at']);completed=pd.Timestamp(terminal['completed_at'])
 if completed<started or terminal.get('order_api_count')!=0:raise ValueError('stage014_terminal_clock_or_external_orders')
 m=load(p/'reserve_total_metrics.json');expected={'end_equity':float(actual.total_account_equity.iloc[-1]),'total_return_pct':(float(actual.total_account_equity.iloc[-1])/TOTAL_CAPITAL-1.)*100.,'total_slippage':float(raw.slippage.sum()),'total_trade_count':float(raw.trade_count.sum())}
 if m.get('account_capital')!=TOTAL_CAPITAL or m.get('initial_capital')!=TOTAL_CAPITAL or m.get('equity_basis')!='total_account_equity' or any(not metric_close(m[k],v) for k,v in expected.items()):raise ValueError('stage014_total300k_metrics_identity_mismatch')
 for basis,frame,metrics in [('raw',raw.account_equity,load(p/'metrics.json')),('total',actual.total_account_equity,m)]:
  dd=float(((frame/frame.cummax()-1.)*100.).min());ret=frame.pct_change().replace([np.inf,-np.inf],np.nan).fillna(0.);std=float(ret.std(ddof=1));sharpe=float(ret.mean()/std*math.sqrt(252.)) if math.isfinite(std) and std>0 else 0.
  if not metric_close(dd,metrics['max_dd_pct']) or not metric_close(sharpe,metrics['sharpe']):raise ValueError('stage014_equity_basis_DD_Sharpe_mismatch:'+basis)
 return {**raw_info,'metrics':{k:m[k] for k in ['end_equity','total_return_pct','max_dd_pct','sharpe','total_slippage','total_trade_count']},'raw_metrics':raw_info['metrics'],'engine_initial_capital':ENGINE_CAPITAL,'reserve_initial_capital':RESERVE_CAPITAL,'total_initial_capital':TOTAL_CAPITAL,'transfer_event_count':len(events),'cumulative_transfer':float(actual.cumulative_transfer.iloc[-1]),'reserve_balance_end':float(actual.reserve_balance.iloc[-1])}

def validate_run_freeze_identity(path,freeze,freeze_sha,arm,start):
 pre=load(Path(path)/'preflight.json')
 if pre.get('freeze_sha256')!=freeze_sha or pre.get('frozen_source_head')!=freeze['source_head'] or pre.get('head')!=freeze['source_head']:raise ValueError('stage014_run_freeze_or_source_head_mismatch')

def make_checkpoint(path,checkpoint,freeze,freeze_sha,arm,start):
 if Path(checkpoint).exists():raise ValueError('stage014_checkpoint_already_exists')
 validate_run_freeze_identity(path,freeze,freeze_sha,arm,start);info=validate_run(path,freeze,arm,start);info.update(method='fresh_engine',schema='stage014_checked_reserve_run_v1',checkpoint_key=checkpoint_key(freeze,freeze_sha,arm,start),freeze_sha256=freeze_sha,source_head=freeze['source_head'],reused=False,files_sha256=snapshot_dir(path));atomic_json(checkpoint,info);return info

def read_checkpoint(checkpoint,freeze,freeze_sha,arm,start):
 r=load(checkpoint)
 if any(r.get(k)!=v for k,v in [('schema','stage014_checked_reserve_run_v1'),('method','fresh_engine'),('source_head',freeze['source_head']),('freeze_sha256',freeze_sha),('arm',arm),('start',start),('end',freeze['cutoff'])]) or r.get('reused') is not False or r.get('checkpoint_key')!=checkpoint_key(freeze,freeze_sha,arm,start) or r.get('files_sha256')!=snapshot_dir(r['path']):raise ValueError('stage014_checkpoint_identity_or_output_changed')
 validate_run_freeze_identity(r['path'],freeze,freeze_sha,arm,start);current=validate_run(r['path'],freeze,arm,start)
 for basis in ['metrics','raw_metrics']:
  if any(not metric_close(value,r[basis][key]) for key,value in current[basis].items()):raise ValueError('stage014_checkpoint_metric_changed:'+basis)
 return r

def total_metric_frame(raw,bridge):
 """Temporary300k wealth curve for metrics; never rewrite original raw ledger."""
 import numpy as np
 if raw.date.astype(str).str[:10].tolist()!=bridge.date.astype(str).str[:10].tolist() or not np.allclose(raw.account_equity+RESERVE_CAPITAL,bridge.total_account_equity,rtol=1e-10,atol=1e-6):raise ValueError('stage014_total_metric_curve_identity')
 d=raw.copy();d['account_equity']=bridge.total_account_equity.to_numpy()
 if 'account_capital' in d:d['account_capital']=TOTAL_CAPITAL
 if 'c3_capital' in d:d['c3_capital']=ENGINE_CAPITAL
 return d

def validate_reserve_snapshots(bridge,snapshots,start):
 import pandas as pd
 validate_start(start)
 if not snapshots:raise ValueError('stage014_no_real_strategy_reserve_snapshots')
 last={};previous_sequence=0;previous_transfer=0.;previous_events=0
 for row in snapshots:
  day=str(row['date'])[:10];sequence=int(row['sequence']);cum=float(row['cumulative_transfer']);raw=float(row['raw_account_equity']);count=int(row['transfer_event_count'])
  if day<start or day not in set(bridge.date.astype(str)) or sequence<=previous_sequence or cum<previous_transfer-1e-6 or count<previous_events:raise ValueError('stage014_snapshot_date_sequence_or_flow_changed')
  expected={'reserve_balance':RESERVE_CAPITAL-cum,'trading_account_equity':raw+cum,'total_account_equity':raw+RESERVE_CAPITAL}
  if not all(math.isfinite(float(row[k])) for k in ['raw_account_equity','cumulative_transfer','trading_account_equity','reserve_balance','total_account_equity','trade_costs_total']) or cum<0 or cum>RESERVE_CAPITAL+1e-6 or any(not metric_close(row[k],v) for k,v in expected.items()):raise ValueError('stage014_strategy_snapshot_conservation_failed')
  last[day]=row;previous_sequence=sequence;previous_transfer=cum;previous_events=count
 if set(last)!=set(bridge.date.astype(str)):raise ValueError('stage014_strategy_snapshot_calendar_incomplete')
 fields=['raw_account_equity','cumulative_transfer','trading_account_equity','reserve_balance','total_account_equity']
 for row in bridge.to_dict('records'):
  if any(not metric_close(last[row['date']][k],row[k]) for k in fields):raise ValueError('stage014_real_strategy_snapshot_not_engine_daily_bridge:'+str(row['date']))
 return dict(accepted=True,day_count=len(last),snapshot_count=len(snapshots),last_sequence_is_daily_close=True,all_real_raw_trading_reserve_total_bridges_match=True)

def validate_event_daily_anchors(bridge,events,fill_phases):
 """A strict bounded-model proof, not an assumption about arbitrary engines."""
 daily=bridge.set_index('date');counts={day:0 for day in daily.index};post=0
 for row in fill_phases:
  day=str(row['date'])[:10];n=int(row['fill_count'])
  if day not in counts or n<0 or type(row.get('post_sizing_fill')) is not bool:raise ValueError('stage014_invalid_fill_phase_ledger')
  counts[day]+=n;post+=n if row['post_sizing_fill'] else 0
 if post:raise ValueError('stage014_post_sizing_fill_not_supported_for_daily_anchor')
 if any(counts[day]!=int(daily.loc[day,'trade_count']) for day in counts):raise ValueError('stage014_fill_phase_count_not_all_real_fills')
 for row in events:
  day=str(row['date'])[:10]
  if day not in daily.index or not metric_close(row['raw_account_equity'],daily.loc[day,'raw_account_equity']):raise ValueError('stage014_event_raw_equity_not_same_day_real_PnL')
 return dict(accepted=True,event_count=len(events),anchored_event_count=len(events),fill_phase_rows=len(fill_phases),real_fill_count=sum(counts.values()),post_sizing_fill_count=post,all_event_raw_account_equity_matches_same_day_raw_daily=True,model='pre_on_bars_complete_fill_queue_no_post_sizing_fill')

def validate_reserve_checks(checks,events,arm,start):
 if arm not in {'A','C'}:raise ValueError('stage014_invalid_arm')
 positive=[];keys=set()
 for row in checks:
  amount=float(row['transfer_amount'])
  if amount<0 or not math.isfinite(amount):raise ValueError('stage014_invalid_check_transfer')
  if row.get('enabled') is not True:raise ValueError('stage014_reserve_not_enabled_in_real_check')
  if float(row['trading_equity_after'])<=0 and int(row['selected_volume_after_parent'])!=0:raise ValueError('stage014_nonpositive_trading_equity_has_purchase_power')
  if amount==0:continue
  if row.get('eligible') is not True or row.get('duplicate') is not False or row.get('entry_context') not in {'flat_entry','reverse_entry'} or str(row['date'])[:10]<start or row.get('weekly_stop_valid') is not True:raise ValueError('stage014_ineligible_or_duplicate_funding_check')
  if arm=='C' and row.get('direction')=='short' and (row.get('range_checked') is not True or row.get('range_would_block') is not False):raise ValueError('stage014_C_rejected_short_funded')
  key=row['candidate_key']
  if key in keys:raise ValueError('stage014_candidate_funded_twice')
  keys.add(key);positive.append(row)
 if len(positive)!=len(events):raise ValueError('stage014_positive_checks_event_count_mismatch')
 for check,event in zip(positive,events):
  if check['candidate_key']!=event['candidate_key'] or any(not metric_close(check[k],event[k]) for k in ['transfer_amount','trading_equity_before','trading_equity_after','reserve_before','reserve_after','cumulative_transfer','raw_account_equity','total_account_equity']):raise ValueError('stage014_positive_check_event_source_mismatch')
 return dict(accepted=True,check_count=len(checks),positive_transfer_checks=len(positive),event_count=len(events),unique_funded_candidates=len(keys),nonpositive_equity_purchasing_power_guard=True)

def _validate_raw_run(path,freeze,arm,start):
 """Read real output identity and terminal gates, never relabel a curve."""
 import pandas as pd
 p=Path(path).resolve();pre=load(p/'preflight.json');t=load(p/'terminal.json');post=load(p/'postflight.json')
 if t.get('status')!='completed_pending_independent_review' or t.get('error') is not None or post.get('inputs_unchanged') is not True:raise ValueError('stage014_raw_incomplete_run:'+str(p))
 if pre.get('arm')!=arm or pre.get('start')!=start or pre.get('end')!=freeze['cutoff'] or pre.get('data_identity')!=freeze['data_identity']:raise ValueError('stage014_raw_run_identity_mismatch')
 if pre.get('short_ma_slope_gate_enabled') is not False or pre.get('long_ma_slope_gate_enabled',False) is not False or pre.get('long_price_range_gate_enabled',False) is not False:raise ValueError('stage014_raw_forbidden_long_or_slope_gate')
 for name in ['long_ma_slope_acceptance.json','long_price_range_acceptance.json']:
  q=p/name
  if q.exists() and (load(q).get('enabled') is not False or load(q).get('applied_block_count')!=0):raise ValueError('stage014_raw_actual_long_filter_on:'+name)
 short=load(p/'short_ma_slope_acceptance.json')
 if short.get('enabled') is not False or short.get('applied_block_count')!=0:raise ValueError('stage014_raw_actual_short_slope_gate_on')
 proof=p/'short_price_range_acceptance.json'
 if arm=='C' and (not proof.is_file() or load(proof).get('enabled') is not True or pre.get('short_price_range_gate_enabled') is not True):raise ValueError('stage014_raw_actual_short_bottom20_not_on')
 if arm=='A' and (pre.get('short_price_range_gate_enabled',False) is not False or (proof.is_file() and (load(proof).get('enabled') is not False or load(proof).get('applied_block_count')!=0))):raise ValueError('stage014_raw_actual_original_has_range_gate')
 for q in p.glob('*_acceptance.json'):
  if load(q).get('accepted') is not True:raise ValueError('stage014_raw_acceptance_failed:'+q.name)
 for name,h in load(p/'input_manifest.json').items():
  if not Path(name).is_file() or sha(name)!=h:raise ValueError('stage014_raw_input_changed:'+name)
 settings=load(p/'actual_strategy_settings.json')
 if len(settings)!=1 or settings[0]['actual'].get('trade_start_date')!=start:raise ValueError('stage014_raw_actual_trade_start_wrong')
 actual=settings[0]['actual']
 if actual.get('capital_base')!=150000 or actual.get('enable_add_position') is not False:raise ValueError('stage014_raw_capital_or_addon_changed')
 d=pd.read_csv(p/'daily.csv');mapping=pd.read_csv(settings[0]['actual']['mapping_csv_path']);expected=sorted(set(mapping.loc[mapping.date.ge(start)&mapping.date.le(freeze['cutoff']),'date'].astype(str)))
 dates=d.date.astype(str).str[:10].tolist()
 if dates!=expected or not dates or dates[0]!=first_trading_day(start,expected):raise ValueError('stage014_raw_full_fresh_window_required')
 if not metric_close(d.account_equity.iloc[0],150000) or float(d.trade_count.iloc[0])!=0:raise ValueError('stage014_raw_first_day_not_fresh150000')
 if not all(math.isfinite(float(x)) for x in d.account_equity):raise ValueError('stage014_raw_nonfinite_equity')
 m=load(p/'metrics.json');checks={'end_equity':float(d.account_equity.iloc[-1]),'total_return_pct':(float(d.account_equity.iloc[-1])/150000-1)*100,'total_slippage':float(d.slippage.sum()),'total_trade_count':float(d.trade_count.sum())}
 for key,value in checks.items():
  if not metric_close(value,m[key]):raise ValueError('stage014_raw_metrics_drift:'+key)
 return dict(path=str(p),arm=arm,start=start,end=freeze['cutoff'],actual_start=dates[0],actual_end=dates[-1],trading_days=len(d),metrics={k:m[k] for k in ['end_equity','total_return_pct','max_dd_pct','sharpe','total_slippage','total_trade_count']})
