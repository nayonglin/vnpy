import sys,time,json,resource,gc,os,tempfile
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
sys.path.insert(0,str(Path.cwd()/'examples/portfolio_backtesting'));sys.path.insert(0,str(Path.cwd()))
import qmt_roll_weekly19_data as data
import qmt_roll_weekly19_runtime as r
import qmt_roll_weekly19_funding as f
from tests.test_weekly19_runtime import broker,ACCOUNT,RELEASE
out=Path('/private/tmp/weekly19_runtime_benchmark_locked.json')
report=dict(schema='weekly19.technical-benchmark.v1',strict_fixture_broker=True,financial_replays=0,on_bars_calls=0,market_downloads=0,order_api_calls=0,production_qualified=False,phases={})
report['source_runtime_sha256_before']=data._sha(r.__file__)
report['source_reader_sha256_before']=data._sha(data.__file__)
def phase(name,fn):
    start=time.perf_counter();value=fn();report['phases'][name]=dict(seconds=time.perf_counter()-start,maxrss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss);out.write_text(json.dumps(report,indent=2));print(name,report['phases'][name],flush=True);return value
pin=json.loads(Path('research/lines/futures_weekly_short_ma_slope_gate/stages/20261031_stage016_runtime_real_sqlite_physical_parity.json').read_text())['source_hashes_before']
root=Path('/Users/mac/.codex/worktrees/weekly-short-ma-slope-20261029/fian/research/lines/futures_weekly_short_ma_slope_gate/outputs/data_stage014_20261030/data_approved')
x=phase('read_inputs',lambda:data.load_weekly19_inputs(root,material_release_id=RELEASE,target_date='2026-10-30',forward_calendar=['2026-11-02','2026-11-03','2026-11-04','2026-11-05','2026-11-06'],expected_hashes=pin))
now=datetime.now(ZoneInfo('Asia/Shanghai'));snap=broker(now=now,day='2026-11-02');cash=f.initial_state(ACCOUNT,RELEASE,'2026-11-02')
a=phase('build',lambda:r.build_weekly19_runtime(r.DEFAULT_SETTINGS_ASSET,x['metadata'],x['calendar'],x['physical_epoch_daily'],snap,None,cash,clock=lambda:now))
phase('pure_warmup',lambda:a.warmup(list(x['bars_by_day'].values())))
saved=phase('export',a.export_state);report['durable_json_bytes']=len(json.dumps(saved,separators=(',',':')));out.write_text(json.dumps(report,indent=2));del saved;gc.collect()
b=phase('sizing_clone',lambda:a._clone_for_sizing(snap,cash));del b;gc.collect()
# A source-bound real bar/history with an explicitly synthetic sizing request:
# no on_bars, candidate performance, order send, or real permission is inferred.
symbol=x['metadata']['daily_mapping']['2026-10-30']['rb.SHFE'];am=a.strategy.ams[symbol]
history=a.strategy._build_history_df(am);bar=x['bars_by_day']['2026-10-30'][symbol]
signal=dict(a.strategy._generate_signal(am,history));signal['signal']='long_case2'
context=dict(vt_symbol=symbol,direction='long',bar=bar,history=history,signal_data=signal,
 risk_mode_override=None,entry_context='flat_entry',apply_env_gate=True,active_positions_before=None,correlation_snapshot=None,
 execution_day='2026-11-02',history_sha256=r._hash(r._encode(history)),data_receipt_sha256=r._hash(x['receipt']))
a.open_contexts['benchmark-synthetic-open']=context
sid='W19.benchmark-synthetic-open';a.engine.order_intents[sid]=dict(intent_id='benchmark-synthetic-open',offset='open',planned_volume=1,signal_order_id=sid)
a.engine.order_filled[sid]=0;a.last_processed_day='2026-10-30'
quote=dict(symbol=symbol,observed_at=now.isoformat(),bid=bar.close_price,ask=bar.close_price+x['metadata']['priceticks'][symbol],session_id='BENCHMARK_ONLY_NO_REAL_SESSION',trading_date='2026-11-02')
report['revalidate_context']='synthetic_request_real_approved_history_no_signal_qualification'
proof=phase('revalidate_open_intent',lambda:a.revalidate_open_intent('benchmark-synthetic-open',broker_snapshot=snap,confirmed_cash_state=cash,quote_snapshot=quote))
saved=phase('export_for_fsync_restore',a.export_state)
def fsync_state():
 raw=json.dumps(saved,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode();report['durable_json_bytes']=len(raw)
 with tempfile.NamedTemporaryFile(dir='/private/tmp',delete=True) as out:
  out.write(raw);out.flush();os.fsync(out.fileno());out.seek(0);return json.load(out)
saved2=phase('json_fsync_read',fsync_state)
b=phase('restore',lambda:r.build_weekly19_runtime(r.DEFAULT_SETTINGS_ASSET,x['metadata'],x['calendar'],x['physical_epoch_daily'],snap,saved2,cash,clock=lambda:now))
report['restore_state_sha_equal']=saved2['state_sha256']==b.export_state()['state_sha256'];report['bundle_two_states_under_64MiB']=report['durable_json_bytes']*2<64*1024*1024
# Store the actual two-runtime-state bundle through the production-facing
# atomic store, with an explicitly synthetic decision and no strategy dayloop.
from qmt_roll_weekly19_pipeline_state import PipelineStateStore
synthetic=dict(schema='weekly19.runtime-decision.v1',trading_date='2026-10-30',account_fingerprint=ACCOUNT,
 material_release_id=RELEASE,confirmed_cash_state=cash,data_receipt_sha256=r._hash(x['receipt']),after_state_sha256='',
 technical_benchmark_synthetic_decision=True,production_qualified=False)
a.current_receipt_hash=synthetic['data_receipt_sha256'];a.days['2026-10-30']=dict(request_hash='benchmark-only',decision=synthetic)
synthetic['after_state_sha256']=a.export_state()['state_sha256'];origin=a.export_state()
report['synthetic_decision_binding_ok']=synthetic['after_state_sha256']==origin['state_sha256']
bundle=dict(schema='weekly19.pipeline-state.v1',account_key=ACCOUNT,material_release_id=RELEASE,revision=0,
 runtime_mode='preview',funding=cash,runtime=origin,decision_state=origin,decision=synthetic)
with tempfile.TemporaryDirectory(dir='/private/tmp') as temporary:
 store=PipelineStateStore(Path(temporary)/'state.json',ACCOUNT,RELEASE)
 phase('pipeline_bundle_initialize_fsync',lambda:store.initialize(bundle))
 loaded=phase('pipeline_bundle_read_validate',store.read)
 report['actual_pipeline_bundle_bytes']=(Path(temporary)/'state.json').stat().st_size
 report['actual_pipeline_bundle_under_64000000']=report['actual_pipeline_bundle_bytes']<64000000
 report['actual_pipeline_bundle_sha_preserved']=loaded['runtime']['state_sha256']==origin['state_sha256']
report['source_runtime_sha256']=data._sha(r.__file__)
report['source_files_unchanged_during_benchmark']=(report['source_runtime_sha256']==report['source_runtime_sha256_before'] and data._sha(data.__file__)==report['source_reader_sha256_before'])
out.write_text(json.dumps(report,indent=2))
