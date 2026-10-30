"""Stage005 original19 short bottom20 all-cached-epoch-range gate; both MA slope gates off."""
from copy import deepcopy
from pathlib import Path
from datetime import datetime
from dataclasses import asdict
from zoneinfo import ZoneInfo
import argparse,hashlib,json,os,sqlite3,sys,time,subprocess
ROOT=Path(__file__).resolve().parents[4];LINE=ROOT/'research/lines/futures_weekly_short_ma_slope_gate'; BASETOOLS=ROOT/'research/lines/futures_weekly_formal_no_half_r/tools'; FROZEN=LINE/'outputs/frozen_baseline';DATA=LINE/'outputs/stage005_data';SOURCE=Path('/Users/mac/Desktop/fian')
VENDOR=Path('/Users/mac/Documents/Codex/fian-handoff-20261014/vnpy_handoff_20261014/vendor')
os.chdir(ROOT);sys.path[:0]=[str(ROOT),str(VENDOR),str(ROOT/'examples/portfolio_backtesting'),str(BASETOOLS),str(Path(__file__).parent)]
os.environ.update(TZ='Asia/Shanghai',OFFICIAL_LIVE_PHASE_D_REAL_SUBMIT_ENABLED='0',OFFICIAL_LIVE_PHASE_D_SESSION_DAEMON_ENABLED='0',OFFICIAL_LIVE_SIGNAL_INPUT_DIR=str(LINE/'outputs/empty_signals'),OFFICIAL_LIVE_OUTPUT_DIR=str(LINE/'outputs/empty_signals'),MPLCONFIGDIR='/private/tmp/weekly-research-mpl');time.tzset()
MODEL='declared_daily_bar_open_next_bar_v1'
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def dump(p,obj):Path(p).write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=str)+'\n')

def actual_addon_configuration(strategy,enabled):
 actual=getattr(strategy,'research_daily_addon_enabled',None)
 if actual is not enabled:raise ValueError('actual_daily_addon_flag_mismatch')
 return dict(enabled=actual,up_days=2,volume=1,max_adds_per_parent=2,max_active_per_product=1,stop_rule='fixed_prior2_low_daily_close_next_open')

def validate_window(start_day,end_day,receipt):
 if start_day!='2020-01-01' or end_day<'2020-01-01' or receipt.get('date_end')!=end_day or receipt.get('data_ready') is not True or receipt.get('data_ready_for_bounded_replay') is not True:raise ValueError('stage032_complete_2020_window_required')
 return start_day,end_day

def _margin(text):
 result={}
 for part in str(text).split(','):
  if not part.strip():continue
  key,value=part.split('=',1)
  if key.strip() in result:raise ValueError('duplicate_margin_key')
  result[key.strip()]=float(value)
 return result

def normalize_settings(current,reference,mapping,approved):
 result=deepcopy(current)
 for field,value in [('mapping_csv_path',str(mapping)),('trade_start_date','2020-01-01')]:
  if field in current:
   if current[field]!=value:raise ValueError('declared_window_mapping_mismatch:'+field)
   result[field]=reference[field]
 if 'margin_ratio_overrides' in current or 'margin_ratio_overrides' in reference:
  old,new=_margin(reference['margin_ratio_overrides']),_margin(current['margin_ratio_overrides'])
  if any(new.get(k)!=v for k,v in old.items()):raise ValueError('existing_margin_changed')
  if set(new)-set(old)!=set(approved):raise ValueError('unapproved_new_margin')
  if any(new[k]!=approved[k]['margin_ratio'] for k in set(new)-set(old)):raise ValueError('approved_margin_value_changed')
  result['margin_ratio_overrides']=reference['margin_ratio_overrides']
 # Only checkout-location differences are normalized; all relative paths and
 # existing file bytes remain pinned to the frozen baseline.
 old_root='/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian'
 for field,value in list(result.items()):
  previous=reference.get(field)
  if isinstance(value,str) and isinstance(previous,str) and value.startswith(str(ROOT)+'/') and previous==old_root+value[len(str(ROOT)):] and field!='mapping_csv_path':
   if Path(value).is_file() and Path(previous).is_file() and sha(value)!=sha(previous):raise ValueError('relocated_asset_bytes_changed:'+field)
   result[field]=previous
 field='supply_demand_signal_path'
 if result.get(field)!=reference.get(field):
  expected=LINE/'outputs/empty_signals'/Path(reference[field]).name
  if result.get(field)!=str(expected) or expected.exists() or Path(reference[field]).exists():raise ValueError('empty_signal_path_not_empty_or_not_declared')
  result[field]=reference[field]
 if result!=reference:raise ValueError('nondeclared_settings_changed')
 return result

def normalize_effective(current,reference,mapping,approved):
 result=deepcopy(current)
 result['spec']['overrides']=normalize_settings(current['spec']['overrides'],reference['spec']['overrides'],mapping,approved)
 for field,source in [('sizes','size'),('slippages','slippage'),('rates','rate')]:
  old,new=reference[field],current[field]
  if any(new.get(k)!=v for k,v in old.items()):raise ValueError('existing_metadata_changed:'+field)
  if set(new)-set(old)!=set(approved):raise ValueError('unapproved_metadata_additions:'+field)
  for k in set(new)-set(old):
   if new[k]!=approved[k][source]:raise ValueError('approved_metadata_value_changed:'+field)
   del result[field][k]
 if result!=reference:raise ValueError('nondeclared_effective_changed')
 return result

def main():
 global DATA
 ap=argparse.ArgumentParser();ap.add_argument('--arm',choices=['C'],required=True);ap.add_argument('--data-dir',type=Path,required=True);ap.add_argument('--attempt',required=True);ap.add_argument('--end',required=True);args=ap.parse_args()
 DATA=args.data_dir.resolve();start_day='2020-01-01';end_day=args.end
 out=LINE/'outputs'/('stage005_'+args.arm+'_attempt'+args.attempt)
 if out.exists():raise ValueError('immutable_output_exists')
 out.mkdir(parents=True)
 receipt=json.loads((DATA/'receipt.json').read_text());validate_window(start_day,end_day,receipt);approved=receipt.get('approved_new_metadata',{})
 if receipt.get('data_ready') is not True or receipt.get('date_end')!=end_day or receipt.get('units')!='single_sided_volume_close_oi':raise ValueError('normalized_history_data_not_ready')

 if receipt.get('data_ready_for_bounded_replay') is not True or receipt.get('historical_main_reconstruction_complete') is not False:raise ValueError('bounded_data_scope_required')
 manifest=json.loads((DATA/'source_manifest.json').read_text());inputs={**manifest['files'],str(DATA/'source_manifest.json'):sha(DATA/'source_manifest.json'),str(DATA/'receipt.json'):sha(DATA/'receipt.json')}
 for p,d in inputs.items():
  if sha(p)!=d:raise ValueError('daily_data_source_changed:'+p)
 from qmt_roll_official_baseline_identity import assert_official_checkout_matches_active_material
 identity=asdict(assert_official_checkout_matches_active_material(ROOT))
 if identity!=asdict(assert_official_checkout_matches_active_material(SOURCE)):raise ValueError('material_identity_drift')
 import pandas as pd
 from vnpy.trader.setting import SETTINGS
 SETTINGS.update({'log.active':False,'log.file':False,'log.console':False})
 import vnpy_sqlite.sqlite_database as driver
 if not driver.db.is_closed():driver.db.close()
 driver.db.init(str(DATA/'daily.sqlite'))
 import vnpy.trader.database as database_module
 database_module.database=driver.SqliteDatabase()
 binding=driver.db.execute_sql('pragma database_list').fetchall()
 if Path(binding[0][2]).resolve()!=(DATA/'daily.sqlite').resolve():raise ValueError('daily_database_binding_mismatch')
 dump(out/'actual_database_binding.json',dict(database_list=binding,expected=str(DATA/'daily.sqlite')))
 import contract_metadata as cm
 cm.ALL_FUTURES_CONTRACT_METADATA_PATH=DATA/'metadata.csv'
 import replay_audit_helpers as audit
 accepted_path=SOURCE/'research/lines/futures_trend_rollover_shape_same_volume/outputs/stage251_half_r_ab/accepted_common_patch_manifest.json'
 accepted=json.loads(accepted_path.read_text());inputs[str(accepted_path)]=sha(accepted_path)
 for name,digest in accepted['source_files'].items():
  if sha(ROOT/name)!=digest:raise ValueError('formal_source_changed:'+name)
  inputs[str(ROOT/name)]=digest
 from qmt_roll_official_strategy_material_resolver import load_active_material_release,verify_material_file
 active=load_active_material_release(ROOT/'official_strategy_materials/CURRENT.json',repo_root=ROOT)
 for row in active.manifest['files']:
  name=str(row.get('source_path',''))
  if row.get('role') not in {'runtime_code','strategy_config','operational_config'} or name.startswith('promotion_source:') or name in audit.ALLOWED_PATCHES or name=='skills/futures-live-execution-sop/SKILL.md':continue
  verify_material_file(ROOT/name,row);inputs[str(ROOT/name)]=sha(ROOT/name)
 import analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow as s901
 import main_contract_mapping as mm
 from weekly_adapter import completed_weeks,weekly_strategy_class
 from stage018_short_case2 import short_case2_weekly_strategy_class
 from stage029_week_close_exits_v2 import week_close_exit_strategy_class,audit_week_close_exits
 from stage032_daily_addon import daily_addon_strategy_class,daily_addon_engine_class,audit_daily_addon
 from stage005_short_bottom20 import RangeHistory,range_strategy_class
 from stage022_historical_safety import historical_strategy_class,historical_engine_class
 from stage020_no_position_cap import universe_capacity_profile,require_only_position_cap_delta
 from stage011_bar_open_execution import bar_open_order_context
 from stage011_bar_open_audit import audit_bar_open_records
 from stage012_ai_selection_off import disable_ai_selection,audit_ai_selection_off,AI_FLAGS
 for row in json.loads((LINE/'stages/stage001_runtime_assets.json').read_text()).values():
  if sha(row['source'])!=row['sha256']:raise ValueError('frozen_runtime_asset_source_changed')
 for path,row in json.loads((LINE/'stages/stage001_runtime_assets.json').read_text()).items():
  if sha(path)!=row['sha256']:raise ValueError('frozen_runtime_asset_copy_changed')
  inputs[path]=row['sha256']
 inputs[str(LINE/'stages/stage001_runtime_assets.json')]=sha(LINE/'stages/stage001_runtime_assets.json')
 mapping=DATA/'mapping.csv';original=s901.build_official_live_strategy_overrides
 def overrides():return disable_ai_selection({**original(),'mapping_csv_path':str(mapping),'enable_stage847_half_r_stop_retry':False,'enable_stage827_intraday_c2_stop':False,'max_concurrent_positions':19,'enable_rsi_partial_exit':False})
 s901.build_official_live_strategy_overrides=overrides;s901.ALL_FUTURES_MAPPING_PATH=mapping
 settings=overrides();products=mm.load_product_universe_symbols(settings['product_universe_csv_path'])
 reference=json.loads((FROZEN/'M_attempt001/preflight.json').read_text())
 if len(products)!=19 or set(products)!=set(reference['universe_products']):raise ValueError('original19_universe_mismatch')
 inputs[str(Path(settings['product_universe_csv_path']))]=sha(settings['product_universe_csv_path'])
 metadata=mm.build_contract_metadata(mapping_path=mapping,supported_symbols=products)
 if end_day=='2026-10-26' and (metadata['priceticks'].get('cu2612.SHFE')!=10.0 or metadata['margin_ratios'].get('cu2612.SHFE')!=0.12):raise ValueError('new_copper_tick_or_margin_mismatch')
 calendar=sorted(pd.read_csv(mapping).date.astype(str).unique());weeks=completed_weeks(calendar)
 counts=dict(minute_reads=0,proxy_reads=0,ai_selection_model_load_attempts=0,empty_minute_initializer_calls=0,empty_proxy_initializer_calls=0)
 import qmt_roll_portfolio_strategy as strategy_module
 def forbidden_ai(*a,**kw):counts['ai_selection_model_load_attempts']+=1;raise ValueError('AI_selection_model_load_forbidden')
 strategy_module.SelectionPairwiseRuntimeModel=forbidden_ai
 def forbidden_minute(*a,**kw):counts['minute_reads']+=1;raise ValueError('minute_read_forbidden_in_bar_open_model')
 def empty_minute(_):
  counts['empty_minute_initializer_calls']+=1;s901.s847.s827._GLOBAL_MINUTE_BY_SYMBOL={}
  return dict(source=MODEL,loaded_symbol_count=0,requested_symbol_count=len(metadata['vt_symbols']),minute_quote_confirmed=False)
 s901._load_stage861_full_minute_bars=forbidden_minute;s901._ensure_c9_minute_bars=empty_minute
 def empty_proxy():counts['empty_proxy_initializer_calls']+=1;return {},{}
 s901.s847.s827.s778.s653.s517.s506.s501._seed_proxy_maps=empty_proxy
 from stage005_sessions import execution
 execution.EXECUTION_POLICY=MODEL
 epoch_frame=pd.read_csv(DATA/'physical_epoch_daily.csv',dtype=str)
 if epoch_frame.duplicated(['vt_symbol','date']).any():raise ValueError('duplicate_physical_epoch_daily_key')
 epoch_lookup={(r.vt_symbol,r.date):r.contract_epoch_id for r in epoch_frame.itertuples()}
 range_history=RangeHistory(epoch_frame)
 engines=[];base_engine=daily_addon_engine_class(historical_engine_class(s901.s847.Stage847StopRetryEngine,epoch_lookup))
 class Engine(base_engine):
  def __init__(self,*a,**kw):super().__init__(*a,**kw);engines.append(self)
  def _resolve_trade_price(self,*a,**kw):counts['proxy_reads']+=1;raise ValueError('proxy_read_forbidden_in_bar_open_model')
  def _stage827_order_context(self,order,bar):return bar_open_order_context(self,order,bar,calendar)
 s901.s847.Stage847StopRetryEngine=Engine
 old_profile=s901.s847._c9_profile
 def profile(meta):
  value=universe_capacity_profile(dict(old_profile(meta)),len(products))
  value['strategy_cls']=historical_strategy_class(range_strategy_class(daily_addon_strategy_class(value['strategy_cls'],weeks,calendar,epoch_lookup,enabled=False),range_history,enabled=args.arm=='C'),start_day);return value
 s901.s847._c9_profile=profile
 pointer=FROZEN/'stage029_contract_pointer_v2.json';contract=json.loads(pointer.read_text())
 for p in [pointer,Path(contract['path']),Path(contract['base_contract_path']),Path(__file__),*[BASETOOLS/name for name in ['stage029_week_close_exits.py','test_stage029_week_close_exits.py','stage029_week_close_exits_v2.py','test_stage029_week_close_exits_v2.py','stage029_metadata_delta.py','test_stage029_metadata_delta.py']]]:inputs[str(p)]=sha(p)
 if sha(contract['path'])!=contract['sha256'] or sha(contract['base_contract_path'])!=contract['base_contract_sha256']:raise ValueError('stage029_v2_contract_changed')
 ai_pointer=FROZEN/'stage012_ai_off_contract_pointer.json';ai_contract=json.loads(ai_pointer.read_text())
 if not ai_contract['all_ai_selection_disabled'] or sha(ai_contract['path'])!=ai_contract['sha256']:raise ValueError('AI_off_contract_changed')
 for p in [ai_pointer,Path(ai_contract['path'])]:inputs[str(p)]=sha(p)
 control=FROZEN/'R_attempt003'
 for name in ['preflight.json','actual_strategy_settings.json','effective_parameters.json','input_manifest.json']:
  p=control/name;inputs[str(p)]=sha(p)
 for p,d in json.loads((control/'input_manifest.json').read_text()).items():
  if sha(p)!=d:raise ValueError('frozen_M_control_input_changed:'+p)
  if p in inputs and inputs[p]!=d:raise ValueError('M_history_input_identity_conflict:'+p)
  inputs[p]=d
 for p in [Path(__file__),Path(__file__).with_name('stage005_short_bottom20.py'),Path(__file__).with_name('test_stage005_short_bottom20.py'),BASETOOLS/'stage032_daily_addon.py',BASETOOLS/'test_stage032_daily_addon.py',BASETOOLS/'test_stage032_runner_contract.py',LINE/'stages/20261030_stage005_short_bottom20_design_plan.md']:inputs[str(p)]=sha(p)
 dump(out/'input_manifest.json',inputs)
 dump(out/'preflight.json',dict(arm=args.arm,head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),identity=identity,start=start_day,end=end_day,execution_model=MODEL,minute_quote_confirmed=False,universe_products=products,universe_product_count=19,storage_capacity=41,ready_need=21,macd_disabled=True,control_path=str(control),week_close_technical_exits=True,short_case2_allowed=False,rsi_exit_enabled=False,daily_addon_enabled=False,short_ma_slope_gate_enabled=False,long_ma_slope_gate_enabled=False,short_price_range_gate_enabled=True,short_price_range_threshold=.2,short_price_range_history='all_available_same_physical_epoch_daily_through_signal',baseline_configuration='stage029_v2_week_close_exits_no_short_case2_no_RSI',data_identity={name:sha(DATA/file) for name,file in [('daily_sqlite_sha256','daily.sqlite'),('mapping_sha256','mapping.csv'),('physical_epoch_daily_sha256','physical_epoch_daily.csv'),('receipt_sha256','receipt.json')]},production_qualified=False))
 started=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat();state='failed';error=None;captured={};actual=[]
 try:
  with audit.capture_actual_settings(Engine) as actual,audit.capture_execution_proxy_usage(Engine) as captured:
   daily,frames,spec=s901._run_live_c9(metadata,pd.Timestamp(start_day),pd.Timestamp(end_day))
  if len(actual)!=1 or any(actual[0]['actual'][key] is not False for key in ['enable_stage847_half_r_stop_retry','enable_stage827_intraday_c2_stop',*AI_FLAGS]):raise ValueError('disabled_flags_mismatch')
  if engines[0].strategy.ai_product_pool_load_status!='disabled' or engines[0].strategy.ai_product_pool_eval_dates:raise ValueError('AI_not_disabled')
  ai_quality=audit_ai_selection_off(engines[0].strategy,frames,counts['ai_selection_model_load_attempts'])
  dump(out/'ai_selection_acceptance.json',ai_quality)
  if not ai_quality['accepted']:raise ValueError('all_AI_selection_off_gate_failed')
  st=engines[0].strategy
  dump(out/'actual_daily_addon_configuration.json',actual_addon_configuration(st,False))
  if st.research_short_ma_slope_gate_enabled is not False or st.research_long_ma_slope_gate_enabled is not False or st.short_ma_slope_decisions or st.long_ma_slope_decisions:raise ValueError('MA_slope_gate_not_fully_disabled')
  for side in ['short','long']:
   dump(out/(side+'_ma_slope_decisions.json'),[])
   dump(out/(side+'_ma_slope_acceptance.json'),dict(accepted=True,enabled=False,decision_count=0,applied_block_count=0,MA_periods=[],rule='disabled_no_slope_wrapper'))
  if st.research_short_price_range_gate_enabled is not True:raise ValueError('actual_price_range_gate_flag_mismatch')
  dump(out/'short_price_range_decisions.json',st.short_price_range_decisions)
  pd.DataFrame(st.short_price_range_decisions).to_csv(out/'short_price_range_decisions.csv',index=False)
  dump(out/'short_price_range_acceptance.json',dict(accepted=True,enabled=True,decision_count=len(st.short_price_range_decisions),would_block_count=sum(r['would_block'] for r in st.short_price_range_decisions),applied_block_count=sum(r['applied_block'] for r in st.short_price_range_decisions),threshold_fraction=.2,comparison='signal_close_lte_low_plus_fraction_times_range',history_scope='all_available_same_physical_epoch_daily_through_signal',price_field='signal_day_close',range_fields=['low','high'],includes_signal_day=True,rollover_gate_applied=False,flat_range_policy='reject',listing_start_completeness_proven=False))
  candidates=frames['entry_candidates']
  case3=int(candidates['signal'].astype(str).str.contains('case3').sum()) if not candidates.empty else 0
  unknown=int((~candidates['signal'].isin(['long_case1a','short_case1a','long_case2','short_case2'])).sum()) if not candidates.empty else 0
  roll=frames['rollover_shape_same_volume']
  hist_nonnull=int(pd.to_numeric(roll['macd_hist'],errors='coerce').notna().sum()) if 'macd_hist' in roll else 0
  proof=dict(schema='stage014_macd_disabled_acceptance_v1',strategy_class=type(st).__name__,macd_disabled=st.research_macd_disabled is True,macd_calculation_attempts=int(st.research_macd_call_attempts),candidate_case3_count=case3,unknown_candidate_signals=unknown,rollover_macd_hist_non_null_count=hist_nonnull,removed_consumers=['entry_hist_direction','macd_case3_trigger','shape_rollover_hist','nonshape_rollover_hist'])
  proof['accepted']=bool(proof['macd_disabled'] and type(st).__name__=='HistoricalSafetyStrategy' and proof['macd_calculation_attempts']==case3==unknown==hist_nonnull==0)
  dump(out/'macd_acceptance.json',proof)
  if not proof['accepted']:raise ValueError('MACD_off_acceptance_failed')
  short_proof=dict(schema='stage018_short_case2_acceptance_v1',strategy_class=type(st).__name__,accepted_signals=['short_case1a','short_case2'],short_case2_gate_allowed=bool(st._can_open_short_signal('short_case2')),short_case1a_gate_allowed=bool(st._can_open_short_signal('short_case1a')),case3_gate_allowed=bool(st._can_open_short_signal('short_case3')),short_signal_rejected_count=int(candidates['skip_reason'].eq('short_signal_rejected').sum()),short_case2_candidates=int(candidates['signal'].eq('short_case2').sum()),short_case2_opened=int((candidates['signal'].eq('short_case2') & candidates['candidate_status'].eq('opened')).sum()),MA_decision_periods=[5,10,20],MA40_decision_enabled=False)
  short_proof['accepted']=bool(st.research_short_case2_enabled is False and short_proof['short_case2_gate_allowed'] is False and short_proof['short_case1a_gate_allowed'] and not short_proof['case3_gate_allowed'] and short_proof['short_case2_opened']==0)
  short_proof['accepted_signals']=['short_case1a']
  dump(out/'short_case2_acceptance.json',short_proof)
  if not short_proof['accepted']:raise ValueError('stage029_short_case2_acceptance_failed')
  limits=sorted(pd.to_numeric(candidates['effective_max_concurrent_positions'],errors='raise').astype(int).unique().tolist())
  configured_limits=sorted(pd.to_numeric(candidates['max_concurrent_positions'],errors='raise').astype(int).unique().tolist())
  nonzero=frames['positions'].loc[frames['positions']['end_pos'].ne(0)].copy()
  nonzero['native_product']=nonzero['vt_symbol'].astype(str).str.replace(r'[0-9]+(?=\.)','',regex=True)
  max_daily=int(nonzero.groupby('date')['native_product'].nunique().max()) if len(nonzero) else 0
  cap_proof=dict(schema='stage020_no_position_cap_acceptance_v1',strategy_class=type(st).__name__,universe_product_count=len(products),original_position_limit=4,candidate_effective_limit=19,configured_position_limit=int(st.max_concurrent_positions),candidate_effective_limit_values=limits,candidate_configured_limit_values=configured_limits,concurrent_limit=int(candidates['skip_reason'].eq('concurrent_limit').sum()),portfolio_env_gate_enabled=bool(st.enable_portfolio_env_gate),max_daily_product_positions=max_daily,implementation='universe_capacity_19_nonbinding_for_fixed_original19',MA40_decision_enabled=False,MA_decision_periods=[5,10,20])
  cap_proof['accepted']=bool(len(products)==19 and limits==configured_limits==[19] and st.max_concurrent_positions==19 and not st.enable_portfolio_env_gate and cap_proof['concurrent_limit']==0 and max_daily<=19)
  dump(out/'no_position_cap_acceptance.json',cap_proof)
  if not cap_proof['accepted']:raise ValueError('nonbinding_position_cap_acceptance_failed')
  expected_settings=json.loads((control/'actual_strategy_settings.json').read_text())
  if len(expected_settings)!=1:raise ValueError('one_control_settings_required')
  for key in ['setting','actual']:
   normalize_settings(actual[0][key],expected_settings[0][key],str(mapping),approved)
  if type(st).__name__!='HistoricalSafetyStrategy' or not st.research_historical_safety_enabled:raise ValueError('historical_safety_class_required')
  if captured['minute_requests'] or any(not frames[k].empty for k in ['intraday_events','stop_retry_events','c2_events']):raise ValueError('disabled_module_events')
  if engines[0].strategy.stage827_minute_by_symbol:raise ValueError('minute_data_unexpectedly_loaded')
  clock=audit.canonical_trade_enums(pd.DataFrame(captured['trades']))
  frames['trades']=audit.attach_trading_dates(audit.canonical_trade_enums(frames['trades']),clock)
  scope='stage005_2020_short_historical_bottom20_'+args.arm
  for name,frame in [('daily',daily),*frames.items(),('execution_clock',clock),('internal_equity_daily',pd.DataFrame(captured['equity'])),('execution_proxy_usage',pd.DataFrame(captured['usage'])),('execution_anchor_requests',pd.DataFrame(captured['anchor_requests']))]:
   if not len(frame.columns):frame=pd.DataFrame(columns=['date','vt_symbol','event','reason'])
   frame['result_scope']=scope;frame['profile']='research_'+args.arm
   frame.to_csv(out/(name+'.csv'),index=False)
  dump(out/'effective_parameters.json',s901._json_safe(dict(spec=asdict(spec),sizes=metadata['sizes'],slippages=metadata['slippages'],rates=metadata['rates'])))
  expected_effective=json.loads((control/'effective_parameters.json').read_text());normalized_effective=json.loads((out/'effective_parameters.json').read_text())
  normalize_effective(normalized_effective,expected_effective,str(mapping),approved)
  dump(out/'metadata_delta_acceptance.json',dict(accepted=True,approved_new_contracts=sorted(approved),old_keys_values_unchanged=True))
  if st.research_week_close_exits_enabled:
   for name in ['weekly_stop_audit','initial_stop_audit','weekly_stop_guard_failures','invalid_weekly_stop_rejections']:
    rows=getattr(st,name);pd.DataFrame(rows).to_csv(out/(name+'.csv'),index=False)
   week_proof=audit_week_close_exits(st,{**frames,'execution_clock':clock,'execution_anchor_requests':pd.DataFrame(captured['anchor_requests'])})
   dump(out/'week_close_exit_acceptance.json',week_proof)
   if week_proof.get('accepted') is not True:raise ValueError('week_close_exit_acceptance_failed')
  addon_proof=audit_daily_addon(st,{**frames,'execution_clock':clock,'execution_anchor_requests':pd.DataFrame(captured['anchor_requests'])})
  dump(out/'daily_addon_acceptance.json',addon_proof)
  if addon_proof.get('accepted') is not True:raise ValueError('stage032_addon_acceptance_failed')
  for name in ['events','decisions','rounds','allocations','snapshots','guard_failures']:
   rows=getattr(st,'daily_addon_'+name,[])
   pd.DataFrame(rows,columns=None if rows else ['date','vt_symbol','event','reason']).to_csv(out/('daily_addon_'+name+'.csv'),index=False)
  from daily_coverage import daily_coverage_gaps
  with sqlite3.connect(f'file:{DATA/"daily.sqlite"}?mode=ro',uri=True) as db:
   gaps=daily_coverage_gaps(frames['positions'].to_dict('records'),db)
   def lookup(symbol,day):
    code,exchange=symbol.split('.')
    rows=db.execute("select open_price,high_price,low_price,close_price,volume from dbbardata where symbol=? and exchange=? and interval='d' and substr(datetime,1,10)=?",(code,exchange,day)).fetchall()
    return [dict(zip(['open','high','low','close','volume'],row)) for row in rows]
   quality=audit_bar_open_records(clock.to_dict('records'),captured['anchor_requests'],lookup,calendar,counts)
   zero_days=[]
   for row in frames['positions'].to_dict('records'):
    if not any(float(row[k]) for k in ['start_pos','end_pos','trade_count']):continue
    source=lookup(row['vt_symbol'],str(row['date'])[:10])
    if len(source)!=1 or not source[0]['volume']>0:zero_days.append(dict(vt_symbol=row['vt_symbol'],date=str(row['date'])[:10]))
  dump(out/'bar_open_acceptance.json',quality)
  dump(out/'data_quality.json',dict(held_or_traded_daily_gaps=gaps,held_or_traded_zero_volume=zero_days,captured_bar_failures=captured['failures']))
  if gaps or zero_days:raise ValueError('held_or_traded_daily_data_gate_failed')
  strategy=engines[0].strategy
  pd.DataFrame(strategy.historical_weekly_readiness).to_csv(out/'weekly_readiness.csv',index=False)
  weekly_rows=[]
  for symbol,am in strategy.ams.items():
   for row in am.completed:
    epochs={epoch_lookup.get((symbol,day)) for day in row['source_days']}
    if None in epochs or len(epochs)!=1:raise ValueError('weekly_bar_crosses_or_lacks_physical_epoch:'+symbol)
    weekly_rows.append(dict(vt_symbol=symbol,contract_epoch_id=next(iter(epochs)),**row))
  pd.DataFrame(weekly_rows).to_csv(out/'weekly_bars.csv',index=False)
  dump(out/'weekly_coverage.json',dict(symbols=len(strategy.ams),ready_need=21,max_week_count=max(am.max_count for am in strategy.ams.values()),symbols_ever_ready=sum(am.max_count>=21 for am in strategy.ams.values()),rejected_incomplete_weeks=sum(len(am.rejected) for am in strategy.ams.values())))
  pd.DataFrame(strategy.historical_target_cleanup,columns=['date','vt_symbol','previous_target','actual_position','new_target','reason']).to_csv(out/'historical_target_cleanup.csv',index=False)
  dump(out/'historical_epoch_transitions.json',getattr(engines[0],'historical_epoch_transitions',[]))
  dump(out/'historical_epoch_failures.json',getattr(engines[0],'historical_epoch_failures',[]))
  expected_days=[d for d in calendar if start_day<=d<=end_day]
  actual_days=pd.to_datetime(daily.date).dt.strftime('%Y-%m-%d').tolist()
  ready_days=[str(row['date'])[:10] for row in strategy.historical_weekly_readiness]
  history_proof=dict(schema='stage023_historical_safety_acceptance_v1',arm=args.arm,strategy_class=type(strategy).__name__,original_strategy_class='Stage029WeekCloseExitV2WithStage032OptionalAddon',historical_safety_enabled=bool(strategy.research_historical_safety_enabled),requested_start=start_day,requested_end=end_day,actual_calendar_matches=actual_days==expected_days,readiness_calendar_matches=ready_days==expected_days,account_days=len(actual_days),epoch_failure_count=len(getattr(engines[0],'historical_epoch_failures',[])),epoch_transition_count=len(getattr(engines[0],'historical_epoch_transitions',[])),target_cleanup_count=len(strategy.historical_target_cleanup),quantity_units='single_sided_volume_close_oi',data_scope='stage032_approved_additive_history_with_inherited_gaps',historical_main_reconstruction_complete=False,source_receipt_sha256=sha(DATA/'receipt.json'),strict_next_trading_day_open=True)
  history_proof['accepted']=bool(history_proof['historical_safety_enabled'] and history_proof['actual_calendar_matches'] and history_proof['readiness_calendar_matches'] and history_proof['epoch_failure_count']==0)
  dump(out/'historical_safety_acceptance.json',history_proof)
  if not history_proof['accepted']:raise ValueError('historical_safety_acceptance_failed')
  metrics=s901.s650._metrics(daily,spec.capital,1.)
  metrics.update(arm=args.arm,result_scope=scope,start=start_day,end=end_day,actual_start=str(daily.date.min())[:10],actual_end=str(daily.date.max())[:10],execution_model=MODEL,production_qualified=False)
  dump(out/'metrics.json',s901._json_safe(metrics));state='completed_pending_independent_review' if quality['accepted'] else 'rejected_execution_bar_open'
 except BaseException as exc:error=repr(exc);raise
 finally:
  dump(out/'actual_strategy_settings.json',s901._json_safe(actual));dump(out/'execution_audit.json',captured);dump(out/'data_read_counts.json',counts)
  if engines:
   obj=getattr(engines[0],'strategy',None)
   if obj is not None:
    dump(out/'short_ma_slope_decisions.json',getattr(obj,'short_ma_slope_decisions',[]))
    dump(out/'short_price_range_decisions.json',getattr(obj,'short_price_range_decisions',[]))
    for name in ['weekly_stop_audit','initial_stop_audit','weekly_stop_guard_failures','invalid_weekly_stop_rejections',*['daily_addon_'+x for x in ['events','decisions','rounds','allocations','snapshots','guard_failures']]]:
     rows=getattr(obj,name,[])
     pd.DataFrame(rows,columns=None if rows else ['date','vt_symbol','event','reason']).to_csv(out/(name+'.csv'),index=False)
  bad=[p for p,d in inputs.items() if sha(p)!=d];dump(out/'postflight.json',dict(inputs_unchanged=not bad,mismatches=bad))
  if bad:state='rejected_input_changed'
  dump(out/'terminal.json',dict(status=state,error=error,started_at=started,completed_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),production_qualified=False,order_api_count=0))
 if state in ['completed_pending_independent_review','rejected_execution_bar_open']:
  dump(LINE/'outputs'/('stage005_'+args.arm+'_completed_attempt.json'),dict(path=str(out),review_status='pending_independent_review',execution_model=MODEL))
 print(json.dumps(s901._json_safe(metrics),ensure_ascii=False))
if __name__=='__main__':main()
