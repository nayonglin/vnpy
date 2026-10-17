"""C0 attempt3 with a qualified data stack and bounded same-engine waits.

The accepted Stage249 repair is verified by bytes rather than masquerading as
the active m0008 payload. Old replay adapters and their identity gates stay intact.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager, nullcontext, redirect_stderr, redirect_stdout
import csv
from dataclasses import asdict
from datetime import date, datetime, timedelta
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
LINE = ROOT/'research/lines/futures_trend_triple_screen'
OUTPUT = LINE/'outputs/stage001_first_screen'
FEATURES = LINE/'outputs/stage001_weekly_features/weekly_daily.csv'
PROTOCOL = LINE/'stages/20261018_0122_stage022_qualified_wait_runner_protocol.md'
SOURCE001 = LINE/'tools/stage001_run_first_screen.py'
SOURCE001_SHA = '928df4baae38548ba54126efc157d04174cec1bbe641cdb5e7be38cfd26969d4'
SOURCE_PROTOCOL = LINE/'stages/20261017_2229_stage001_first_screen_protocol.md'
DESIGN = LINE/'outputs/stage022_qualified_wait'
STACK_PATH = DESIGN/'data_stack_manifest.json'
WAIT_SECONDS, RUN_SECONDS = 1800, 7200
OLD = ROOT/'research/lines/futures_trend_rollover_shape_same_volume/outputs/stage251_half_r_ab/A_final3'
PROJECT = ROOT/'examples/portfolio_backtesting'
VENDOR = Path('/Users/mac/Documents/Codex/fian-handoff-20261014/vnpy_handoff_20261014/vendor')
FROZEN_SITE = Path('/Users/mac/Documents/Codex/fian-research-20261014/.py311/lib/python3.11/site-packages')
START, END = '2020-01-01', '2026-10-14'
EXPECTED_MINUTE = '5c06124fac52ff37a19d1abe89f6f6a80d36b8ece874eb647286377317289189'
EXPECTED_FEATURES = 'd8bae99069a24195975aac62fd47a1cfbdf5f024f15861a6772e424faf6c5f8e'
EXPECTED_OVERLAY_SUMMARY = 'abb5d723f186d0bc8a7e6d172719c84572eb844600dd8b4106d1a1a911993d4b'
OVERLAY_REVIEW = LINE/'outputs/stage002_independent_review/overlay_independent_checks.json'
EXPECTED_OVERLAY_REVIEW = '2c57a48e5d0dd4d44d885af4da87266a3c7b5bc389360bcd31a942d000911e27'
ACCEPTED_CODE = {
 'examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py':'6d6aa534715200c40a5743697114f73080111d609b29980d924dcb1d362792e9',
 'examples/portfolio_backtesting/analyze_qmt_roll_stage827_stage819_intraday_c2_engine_ac.py':'fe4df78d5621b0de0a74bec2eaa679f145f702a36e5fb73f85f50b840e636fe2',
 'examples/portfolio_backtesting/analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine.py':'755187283ceb9282ee0f0e1e0b2c79c2cf7b8fb737815487e5ee8f02e09d2a64',
 'examples/portfolio_backtesting/qmt_roll_intraday_execution.py':'95de37e240ed5f34e8370cf9652e958c3c44fa3f36bef1d905c3e757a8304272',
}
IDENTITY = dict(strategy_version='ai_top10_plus_fu_official_live_v1',
 ruleset_version='stage037_stage034_long_short_mirror_hard_block_v1',
 source_commit='2a7420a9f9550ab912b5c4a302a61acc5740b04c',
 material_release_id='m0008_20261008T204054+0800_2a7420a9f955',
 release_commit='334d18f069de06df3aa7728203e942e3ecb94ce9',
 manifest_sha256='94b6936ab4b338430981f4c2f7e0f4ff38f24534c32f1d16722c8d1367d89474')


def sha256(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda:handle.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def json_safe(value):
    if isinstance(value,dict):return {str(k):json_safe(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [json_safe(v) for v in value]
    if isinstance(value,(datetime,date,Path)):return str(value)
    if hasattr(value,'item'):return json_safe(value.item())
    if isinstance(value,float) and not math.isfinite(value):return None
    return value


def write_json(path,payload):
    Path(path).write_text(json.dumps(json_safe(payload),ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def ready_bool(value):
    if value in (True,'True','true','1',1):return True
    if value in (False,'False','false','0',0):return False
    raise ValueError('invalid_ready')


class WeeklyLookup:
    def __init__(self,rows):
        self.rows={}
        for row in rows:
            day=date.fromisoformat(str(row['date'])[:10])
            product=str(row['product_id']).upper()
            key=(day.isoformat(),product)
            if key in self.rows:raise ValueError('duplicate_weekly_feature')
            readiness=row.get('weekly_ready',row.get('ready'))
            ready=ready_bool(readiness)
            if 'weekly_ready' in row and 'ready' in row and ready != ready_bool(row['ready']):
                raise ValueError('conflicting_ready_columns')
            raw=row.get('weekly_direction',row.get('direction',0))
            direction=int(raw) if str(raw).strip() not in ('','nan','None') else 0
            if direction not in (-1,0,1):raise ValueError('invalid_weekly_direction')
            if 'weekly_direction' in row and 'direction' in row and direction != int(row['direction']):
                raise ValueError('conflicting_direction_columns')
            asof=str(row.get('weekly_asof','') or '')[:10]
            if ready:
                prior=date.fromisoformat(asof)
                if prior >= day-timedelta(days=day.weekday()):
                    raise ValueError('weekly_asof_not_prior_week')
            self.rows[key]=dict(ready=ready,direction=direction,weekly_asof=asof,
                reason=str(row.get('reason','not_ready' if not ready else 'ready')))

    @classmethod
    def read(cls,path):
        with Path(path).open(encoding='utf-8-sig',newline='') as handle:
            return cls(csv.DictReader(handle))

    def get(self,day,product):
        return self.rows.get((day,product.upper()),dict(ready=False,direction=0,weekly_asof='',reason='feature_row_missing'))


def build_research_strategy(base,lookup,arm):
    if arm not in ('A0','C0'):raise ValueError('unregistered_arm')
    class FirstScreenResearch(base):
        def _build_flat_entry_candidate_plan(self,context,base_active_positions):
            plan=super()._build_flat_entry_candidate_plan(context,base_active_positions)
            if plan is None:return None
            # This method is called only for an initial flat-entry plan. Rollover,
            # existing-position exits/adds and intraday retries do not pass here.
            day=context.target_bar.datetime.date().isoformat()
            product,exchange=context.product_vt_symbol.rsplit('.',1)
            product_id=f'{exchange}.{product}'.upper()
            feature=lookup.get(day,product_id)
            native_before=bool(plan['native_openable'])
            sign=1 if plan['direction']=='long' else -1
            opposed=bool(feature['ready'] and feature['direction'] != sign)
            blocked=bool(arm=='C0' and native_before and opposed)
            if blocked:
                plan['native_openable']=False
                plan['candidate_status']='skipped'
                plan['skip_reason']='weekly_first_screen_neutral' if feature['direction']==0 else 'weekly_first_screen_opposed'
            if arm=='A0':decision='control_keep_baseline'
            elif not feature['ready']:decision='unknown_keep_baseline'
            elif blocked:decision='blocked'
            elif not native_before:decision='baseline_already_blocked'
            else:decision='aligned_keep_baseline'
            if not hasattr(self,'weekly_gate_audit'):self.weekly_gate_audit=[]
            audit=dict(date=day,product_vt_symbol=context.product_vt_symbol,
                product_id=product_id,target_contract=context.target_contract,
                direction=plan['direction'],signal=plan['signal'],weekly_ready=feature['ready'],
                weekly_direction=feature['direction'],weekly_asof=feature['weekly_asof'],
                unknown_reason=feature['reason'] if not feature['ready'] else '',
                native_openable_before=native_before,native_openable_after=bool(plan['native_openable']),
                weekly_opposed=opposed,gate_blocked=blocked,decision=decision,
                original_volume=int(plan['volume']),skip_reason=plan['skip_reason'],arm=arm)
            self.weekly_gate_audit.append(audit)
            return plan
    FirstScreenResearch.__name__=f'Stage001FirstScreen{arm}'
    return FirstScreenResearch


def reserve_attempt(output):
    output=Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.mkdir(exist_ok=False)
    write_json(output/'attempt_started.json',dict(started_at=datetime.now().astimezone(),
        status='started_no_retry_or_overwrite',pid=os.getpid(),argv=sys.argv))


def resolve_attempt_output(root,arm,attempt):
    if attempt < 1:raise ValueError('attempt_must_be_positive')
    root=Path(root)
    if attempt > 1:
        previous=root/(arm if attempt==2 else f'{arm}_attempt{attempt-1}')
        if not (previous/'run_failure.json').is_file() or (previous/'summary.json').exists():
            raise ValueError('previous_attempt_not_failed')
    return root/(arm if attempt==1 else f'{arm}_attempt{attempt}')


@contextmanager
def replace_strategy_class(module,strategy):
    original=module._c9_profile
    def build(metadata):return {**original(metadata),'strategy_cls':strategy}
    module._c9_profile=build
    try:yield
    finally:module._c9_profile=original


def capture_formal_profile(s901,metadata,start,end):
    """Let the unchanged official assembler run, then stop before engine creation."""
    original=s901.s847._run_profile
    original_ensure=s901._ensure_c9_minute_bars
    captured=[]
    class ProfileReady(Exception):pass
    def stop_before_engine(profile,metadata):
        captured.append(profile)
        raise ProfileReady
    s901.s847._run_profile=stop_before_engine
    s901._ensure_c9_minute_bars=lambda metadata:{}
    try:
        try:s901._run_live_c9(metadata,start,end)
        except ProfileReady:pass
    finally:
        s901.s847._run_profile=original
        s901._ensure_c9_minute_bars=original_ensure
    if len(captured) != 1:raise ValueError('formal_profile_not_captured_once')
    return captured[0]


@contextmanager
def capture_actual_settings(engine_class):
    local='add_strategy' in engine_class.__dict__
    original=engine_class.add_strategy
    captured=[]
    def add(engine,strategy_class,setting):
        result=original(engine,strategy_class,setting)
        actual={key:getattr(engine.strategy,key) for key in setting if hasattr(engine.strategy,key)}
        non_strategy={key:value for key,value in setting.items() if key not in actual and key in ('account_capital','c3_capital')}
        if any(value != engine.capital for value in non_strategy.values()):raise ValueError('engine_capital_metadata_mismatch')
        expected={key:value for key,value in setting.items() if key not in non_strategy}
        if actual != expected:raise ValueError('actual_strategy_settings_mismatch')
        captured.append(dict(strategy_class=strategy_class.__name__,setting=dict(setting),actual=actual,
            non_strategy_fields=non_strategy,engine_capital=engine.capital,
            supply_demand_signal_rows=len(getattr(engine.strategy,'supply_demand_signals',[]))))
        return result
    engine_class.add_strategy=add
    try:yield captured
    finally:
        if local:engine_class.add_strategy=original
        else:delattr(engine_class,'add_strategy')


@contextmanager
def capture_engine(engine_class):
    names=('new_bars','calculate_result')
    originals={name:(name in engine_class.__dict__,getattr(engine_class,name)) for name in names}
    result=dict(usage=[],equity=[],trades=[],minute_requests=[],anchor_requests=[],failures=[],weekly_gate=[])
    errors=[]
    def new_bars(engine,dt):
        try:
            value=originals['new_bars'][1](engine,dt)
            strategy=getattr(engine,'strategy',None)
            if strategy is not None and getattr(strategy,'trading',False):
                result['equity'].append(dict(date=str(dt.date()),estimated_equity=float(strategy.estimated_equity),settled_balance=float(strategy.settled_balance)))
            return value
        except Exception as error:
            result['failures'].append(dict(datetime=str(dt),error=repr(error)))
            errors.append(error)
            raise
    def calculate(engine,*args,**kwargs):
        value=originals['calculate_result'][1](engine,*args,**kwargs)
        strategy=getattr(engine,'strategy',None)
        result['usage']=[dict(x) for x in getattr(engine,'trade_usage_rows',[])]
        result['anchor_requests']=[dict(x) for x in getattr(engine,'execution_anchor_requests',[])]
        result['minute_requests']=[dict(x) for obj in (engine,strategy) if obj is not None for x in getattr(obj,'minute_scan_requests',[])]
        result['weekly_gate']=[dict(x) for x in getattr(strategy,'weekly_gate_audit',[])]
        result['trades']=[dict(trade_id=t.vt_tradeid,vt_symbol=t.vt_symbol,
            engine_datetime=str(t.datetime),trading_date=str(getattr(t,'trading_date',t.datetime.date())),
            execution_datetime=str(getattr(t,'execution_datetime',t.datetime)),
            exit_reason=getattr(strategy,'trade_reason_by_trade_id',{}).get(t.vt_tradeid) or getattr(t,'exit_reason',''),
            direction=t.direction.value,offset=t.offset.value,price=float(t.price),volume=float(t.volume)) for t in engine.get_all_trades()]
        return value
    engine_class.new_bars=new_bars
    engine_class.calculate_result=calculate
    try:
        try:yield result
        except Exception:
            if errors:raise RuntimeError(f'backtest_bar_failed:{result["failures"][0]}') from errors[0]
            raise
        if errors:raise RuntimeError(f'backtest_bar_failed:{result["failures"][0]}') from errors[0]
    finally:
        for name,(local,original) in originals.items():
            if local:setattr(engine_class,name,original)
            else:delattr(engine_class,name)


def canonical_trade_enums(frame):
    result=frame.copy()
    mappings={'direction':{'Long':'多','Short':'空','多':'多','空':'空'},
        'offset':{'Open':'开','Close':'平','Close Today':'平今','Close Yesterday':'平昨','开':'开','平':'平','平今':'平今','平昨':'平昨'}}
    for column,mapping in mappings.items():
        if column not in result:
            if result.empty:result[column]=[];continue
            raise ValueError(f'trade_enum_column_missing:{column}')
        normalized=result[column].map(mapping)
        if normalized.isna().any():raise ValueError(f'unknown_trade_enum:{column}')
        result[column]=normalized
    return result


def attach_trading_dates(trades,clock):
    if trades.empty and clock.empty:return trades.copy()
    if trades.trade_id.duplicated().any() or clock.trade_id.duplicated().any() or set(trades.trade_id) != set(clock.trade_id):
        raise ValueError('trade_clock_identity_mismatch')
    result=trades.copy()
    result['natural_date']=result['datetime'].astype(str).str[:10]
    result['trading_date']=result.trade_id.map(clock.set_index('trade_id').trading_date)
    result['date']=result['trading_date']
    mapped=result.trade_id.map(clock.set_index('trade_id').exit_reason.fillna(''))
    previous=result.get('exit_reason',mapped).fillna('')
    result['exit_reason']=mapped.where(mapped.ne(''),previous)
    return result


class InputRecorder:
    """Fingerprint actual read-only research data, not every unrelated old output.

    Python audit records CSV/model reads and SQLite connects before they occur.
    Known old inputs must retain accepted bytes; every consumed file is rehashed
    at scope end. The hook is inert outside this process's explicit scope.
    """
    def __init__(self,accepted):
        self.accepted=accepted;self.files={};self.enabled=False;self.busy=False
        self.roots=(PROJECT/'backtest_outputs',PROJECT/'downloaded_futures',ROOT/'official_strategy_materials')
        self.extra={ROOT/'.vntrader/database.db',FEATURES,PROTOCOL,Path(__file__).resolve(),OLD/'effective_parameters.json',OLD/'actual_strategy_settings.json'}

    def record(self,path):
        if isinstance(path,int):return
        try:path=Path(os.fsdecode(path)).resolve()
        except (TypeError,ValueError):return
        if path in self.files:return
        if path not in self.extra and not any(path.is_relative_to(root) for root in self.roots):return
        if path.suffix.lower() not in ('.csv','.json','.joblib','.npy','.db','.pkl','.py','.md'):return
        if not path.is_file():return
        self.busy=True
        try:
            digest=sha256(path)
            relative=str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
            previous=self.accepted.get(relative)
            if previous is not None and digest != previous:raise ValueError(f'accepted_data_input_changed:{relative}')
            self.files[str(path)]=dict(sha256=digest,bytes=path.stat().st_size,accepted_stage251_match=previous is not None)
        finally:self.busy=False

    def audit(self,event,args):
        if not self.enabled or self.busy:return
        if event=='open':
            mode=args[1]
            if mode is not None and any(c in str(mode) for c in 'wax+'):return
            self.record(args[0])
        elif event=='sqlite3.connect':
            self.record(str(args[0]).removeprefix('file:').split('?',1)[0])

    def verify(self):
        self.enabled=False
        changed=[path for path,value in self.files.items() if sha256(path) != value['sha256']]
        if changed:raise ValueError(f'consumed_input_changed_during_run:{changed}')


def configure_runtime(shared):
    if not VENDOR.is_dir() or not FROZEN_SITE.is_dir():raise RuntimeError('frozen_runtime_missing')
    shared.mkdir(parents=True,exist_ok=True)
    if any(shared.iterdir()):raise ValueError('historical_shared_signal_input_not_empty')
    os.chdir(ROOT)
    mpl=OUTPUT/'runtime/matplotlib';mpl.mkdir(parents=True,exist_ok=True)
    os.environ.update(OFFICIAL_LIVE_SIGNAL_INPUT_DIR=str(shared),OFFICIAL_LIVE_OUTPUT_DIR=str(shared),
        OFFICIAL_LIVE_PHASE_D_REAL_SUBMIT_ENABLED='0',OFFICIAL_LIVE_PHASE_D_SESSION_DAEMON_ENABLED='0',
        TZ='Asia/Shanghai',QT_QPA_PLATFORM='offscreen',MPLCONFIGDIR=str(mpl))
    if hasattr(time,'tzset'):time.tzset()
    if time.localtime(0).tm_hour != 8:raise RuntimeError('wrong_process_timezone')
    # The persisted pairwise artifact was written with sklearn 1.8.0. The local
    # 1.6.1 installation cannot read its LogisticRegression prediction contract.
    # Reuse the whole already accepted Stage263/267 frozen numerical stack;
    # never patch estimator attributes, change model bytes or retrain it.
    for name in ('numpy','pandas','scipy','sklearn','joblib'):
        module=sys.modules.get(name)
        if module is not None and not Path(module.__file__).resolve().is_relative_to(FROZEN_SITE):
            raise RuntimeError(f'numerical_package_imported_before_frozen_runtime:{name}')
    sys.path[:0]=[str(ROOT),str(VENDOR),str(PROJECT),str(FROZEN_SITE)]


def model_runtime_smoke(model_path,summary_path):
    """Check inference without orders, labels, model fitting or market outcomes."""
    import warnings
    import joblib
    import numpy as np
    import pandas as pd
    import scipy
    import sklearn
    from sklearn.exceptions import InconsistentVersionWarning
    if sklearn.__version__ != '1.8.0':raise RuntimeError('frozen_model_requires_sklearn_1_8_0')
    before=sha256(model_path)
    columns=json.loads(Path(summary_path).read_text())['model_metadata']['feature_columns']
    with warnings.catch_warnings():
        warnings.simplefilter('error',InconsistentVersionWarning)
        model=joblib.load(model_path)
    if list(model.named_steps) != ['scaler','classifier']:raise ValueError('unexpected_frozen_pipeline')
    scaler=model.named_steps['scaler'];classifier=model.named_steps['classifier']
    if list(classifier.classes_) != [0,1] or classifier.coef_.shape != (1,len(columns)):
        raise ValueError('unexpected_nonbinary_frozen_classifier')
    axis=np.linspace(-1.,1.,len(columns))
    values=np.vstack([np.zeros(len(columns)),np.ones(len(columns)),-np.ones(len(columns)),axis,-axis])
    features=pd.DataFrame(values,columns=columns)
    probabilities=np.asarray(model.predict_proba(features),dtype=float)
    transformed=values.copy()
    if scaler.with_mean:transformed-=scaler.mean_
    if scaler.with_std:transformed/=scaler.scale_
    logit=(transformed@classifier.coef_.T+classifier.intercept_).ravel()
    manual=np.empty_like(logit);positive=logit>=0
    manual[positive]=1/(1+np.exp(-logit[positive]))
    negative_exp=np.exp(logit[~positive]);manual[~positive]=negative_exp/(1+negative_exp)
    expected=np.column_stack([1-manual,manual])
    error=float(np.max(np.abs(probabilities-expected)))
    if not np.isfinite(probabilities).all() or error > 1e-12:raise ValueError('frozen_probability_manual_check_failed')
    if sha256(model_path) != before:raise ValueError('frozen_model_mutated_during_smoke')
    return dict(status='passed_binary_probability_smoke',model_sha256=before,
        sklearn_version=sklearn.__version__,numpy_version=np.__version__,pandas_version=pd.__version__,
        scipy_version=scipy.__version__,joblib_version=joblib.__version__,
        package_paths={m.__name__:m.__file__ for m in (sklearn,np,pd,scipy,joblib)},
        probe_rows=5,feature_columns=len(columns),max_probability_error=error,
        model_fits=0,financial_replays=0,model_bytes_unchanged=True)


def read_overlay_receipt(summary_path,*,expected_summary_sha256=EXPECTED_OVERLAY_SUMMARY,
                         review_path=OVERLAY_REVIEW,expected_review_sha256=EXPECTED_OVERLAY_REVIEW):
    summary_path=Path(summary_path).resolve();folder=summary_path.parent
    if sha256(summary_path)!=expected_summary_sha256:raise ValueError('overlay_summary_fingerprint_changed')
    if sha256(review_path)!=expected_review_sha256:raise ValueError('overlay_independent_review_fingerprint_changed')
    review=json.loads(Path(review_path).read_text())
    summary=json.loads(summary_path.read_text())
    equality=json.loads((folder/'a0_path_equivalence.json').read_text())
    if summary.get('status')!='completed_local_overlay_pending_independent_review':raise ValueError('overlay_build_not_completed')
    if summary.get('base_cache_sha256')!=EXPECTED_MINUTE or not summary.get('all_inputs_unchanged'):
        raise ValueError('overlay_base_identity_or_input_verification_failed')
    if equality!=summary.get('a0_path_equivalence')or not equality.get('path_equivalent')or equality.get('intersection_count')!=0 or equality.get('original_read_keys_missing_in_base')!=0:
        raise ValueError('overlay_a0_path_equivalence_failed')
    if review.get('status')!='independent_overlay_and_A0_path_equivalence_pass' or review.get('A0_path_equivalent')is not True:
        raise ValueError('overlay_independent_review_not_passed')
    if Path(review.get('source','')).resolve()!=folder or review.get('original_base_SHA_unchanged')!=EXPECTED_MINUTE:
        raise ValueError('overlay_review_source_or_base_mismatch')
    for name,digest in review.get('source_hashes',{}).items():
        if sha256(folder/name)!=digest:raise ValueError(f'overlay_fingerprint_changed:{name}')
    for name,key in [('overlay.csv','overlay_sha256'),('session_manifest.csv','session_manifest_sha256'),
                     ('source_manifest.json','source_manifest_sha256'),('protocol_used.md','protocol_sha256')]:
        if sha256(folder/name)!=summary.get(key):raise ValueError(f'overlay_fingerprint_changed:{name}')
    builder=Path(__file__).with_name('stage002_local_minute_overlay.py')
    if sha256(builder)!=summary.get('builder_sha256'):raise ValueError('overlay_builder_changed_after_build')
    return dict(summary_path=str(summary_path),overlay_path=str(folder/'overlay.csv'),
        overlay_sha256=summary['overlay_sha256'],source_manifest_sha256=summary['source_manifest_sha256'],
        added_minutes=summary.get('added_minutes'),a0_path_equivalent=True,a0_actual_read_keys=equality.get('distinct_actual_read_keys'),
        added_intersection_with_a0_reads=0,base_original_keys_unchanged=True,financial_replays_for_a0_equivalence=0,
        builder_sha256=summary['builder_sha256'],protocol_used_sha256=summary['protocol_sha256'],
        summary_sha256=expected_summary_sha256,independent_review_path=str(Path(review_path).resolve()),
        independent_review_sha256=expected_review_sha256)


def normalize_reference(value,shared,reference_shared):
    if isinstance(value,dict):return {k:normalize_reference(v,shared,reference_shared) for k,v in value.items()}
    if isinstance(value,list):return [normalize_reference(v,shared,reference_shared) for v in value]
    if isinstance(value,str):return value.replace(str(shared),'{historical_empty_signal_dir}').replace(str(reference_shared),'{historical_empty_signal_dir}')
    return value


def atomic_json(path,payload):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.tmp')
    with temporary.open('w')as handle:
        handle.write(json.dumps(json_safe(payload),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
        handle.flush();os.fsync(handle.fileno())
    os.replace(temporary,path)


def canonical_request_sha256(request):
    payload={key:value for key,value in request.items()if key!='request_sha256'}
    return hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


class FileWaitResolver:
    """No provider: publish one request and accept only a hash-bound review."""
    def __init__(self,root,recorder,audit,run_began,*,clock=time.monotonic,sleep=time.sleep,delivery_factory=None):
        self.root=Path(root);self.recorder=recorder;self.audit=audit;self.run_began=run_began
        self.clock=clock;self.sleep=sleep;self.delivery_factory=delivery_factory

    def bind(self,path,expected):
        path=Path(path)
        if not path.is_absolute()or sha256(path)!=expected:raise ValueError('delivery_input_hash_mismatch')
        path=path.resolve();self.recorder.extra.add(path);self.recorder.record(path)
        if self.recorder.files[str(path)]['sha256']!=expected:raise ValueError('delivery_changed_before_record')
        return path

    def __call__(self,request):
        digest=request.get('request_sha256','')
        if len(digest)!=64 or any(c not in '0123456789abcdef'for c in digest):raise ValueError('invalid_request_sha256')
        folder=self.root/('request_'+digest);folder.mkdir(parents=True,exist_ok=True)
        path=folder/'request.json'
        if path.exists():
            if json.loads(path.read_text())!=request:raise ValueError('existing_request_payload_changed')
        if canonical_request_sha256(request)!=digest:raise ValueError('request_payload_digest_mismatch')
        if not path.exists():atomic_json(path,request)
        request_file_sha=sha256(path)
        self.bind(path.resolve(),request_file_sha)
        fingerprint_path=folder/'request_fingerprint.json'
        fingerprint=dict(request_sha256=digest,request_file_sha256=request_file_sha,request_path=str(path.resolve()))
        if fingerprint_path.exists()and json.loads(fingerprint_path.read_text())!=fingerprint:
            raise ValueError('existing_request_fingerprint_changed')
        if not fingerprint_path.exists():atomic_json(fingerprint_path,fingerprint)
        self.bind(fingerprint_path.resolve(),sha256(fingerprint_path))
        began=self.clock()
        row=dict(status='waiting_for_independent_data',request_sha256=digest,request_path=str(path.resolve()),
            request_file_sha256=sha256(path),response_path=str((folder/'response.json').resolve()),
            started_at=datetime.now().astimezone().isoformat(),wait_seconds_max=WAIT_SECONDS)
        self.audit.append(row)
        atomic_json(self.root/'audit.json',self.audit)
        while True:
            now=self.clock()
            if now-began>=WAIT_SECONDS or now-self.run_began>=RUN_SECONDS:
                row.update(status='wait_budget_exceeded',elapsed_wait_seconds=now-began)
                atomic_json(self.root/'audit.json',self.audit)
                raise TimeoutError('qualified_data_wait_budget_exceeded')
            response_path=folder/'response.json'
            if response_path.exists():
                response_sha=sha256(response_path);response=json.loads(response_path.read_text())
                if response.get('schema')!='stage022_delivery_pointer_v1'or response.get('request_sha256')!=digest:
                    raise ValueError('response_request_mismatch')
                self.bind(response_path.resolve(),response_sha)
                receipt_path=self.bind(Path(response['receipt_path']),response['receipt_sha256'])
                receipt=json.loads(receipt_path.read_text())
                if receipt.get('schema')!='stage021_independent_minute_delivery_v1'or receipt.get('request_sha256')!=digest:
                    raise ValueError('independent_receipt_request_mismatch')
                if (receipt.get('independent_review')is not True or not receipt.get('reviewer')or
                    receipt.get('qualified_research_data')is not True or receipt.get('p0_findings',0)or receipt.get('p1_findings',0)):
                    raise ValueError('independent_receipt_not_qualified')
                data_path=str(Path(receipt['data_path']))
                fingerprints=receipt.get('source_fingerprints',{})
                if fingerprints.get(data_path)!=receipt['data_sha256']:raise ValueError('delivery_data_not_review_bound')
                for source,value in fingerprints.items():self.bind(Path(source),value)
                row.update(status='qualified_delivery_pointer_accepted',receipt_path=str(receipt_path),
                    receipt_sha256=response['receipt_sha256'],response_sha256=response_sha,
                    data_path=data_path,data_sha256=receipt['data_sha256'],source_fingerprints=dict(fingerprints),
                    elapsed_wait_seconds=now-began)
                atomic_json(self.root/'audit.json',self.audit)
                factory=self.delivery_factory
                if factory is None:
                    from stage021_blocking_data_gate import QualifiedDelivery
                    factory=QualifiedDelivery
                return factory(receipt_path,response['receipt_sha256'])
            self.sleep(min(1.,WAIT_SECONDS-(now-began),RUN_SECONDS-(now-self.run_began)))


@contextmanager
def whole_run_budget(seconds=RUN_SECONDS):
    """A process-local wall-clock bound, including waits inside the same engine."""
    previous=signal.getsignal(signal.SIGALRM);previous_timer=signal.getitimer(signal.ITIMER_REAL)
    def timeout(signum,frame):raise WholeRunBudgetExceeded('C0_whole_run_7200_second_budget_exceeded')
    signal.signal(signal.SIGALRM,timeout);signal.setitimer(signal.ITIMER_REAL,seconds)
    try:yield
    finally:
        signal.setitimer(signal.ITIMER_REAL,*previous_timer);signal.signal(signal.SIGALRM,previous)


class WholeRunBudgetExceeded(BaseException):
    """Escape third-party Exception handlers so the resource bound cannot reset."""


def freeze_data_stack(review020_sha,review021_sha):
    """Only trusted completed upstream receipts may create the once-frozen stack."""
    if STACK_PATH.exists():raise FileExistsError('existing_data_stack_refuse_refreeze')
    if sha256(SOURCE001)!=SOURCE001_SHA or sha256(DESIGN/'source_stage001_original.py')!=SOURCE001_SHA:
        raise ValueError('original_runner_source_changed')
    files={}
    def bind(path,expected=None):
        path=Path(path).resolve();value=sha256(path)
        if expected is not None and expected!=value:raise ValueError(f'data_stack_input_changed:{path}')
        if str(path)in files and files[str(path)]!=value:raise ValueError('conflicting_data_stack_fingerprint')
        files[str(path)]=value;return path
    def read(path,expected=None):return json.loads(bind(path,expected).read_text())
    overlays=[];bundles=[]
    receipt002=read_overlay_receipt(LINE/'outputs/stage002_local_minute_overlay/attempt2/summary.json')
    folder002=Path(receipt002['overlay_path']).parent
    for path in folder002.iterdir():
        if path.is_file()and path.suffix in {'.csv','.json','.md'}:bind(path)
    bind(OVERLAY_REVIEW,EXPECTED_OVERLAY_REVIEW)
    source002=read(folder002/'source_manifest.json',receipt002['source_manifest_sha256'])
    for section in ['sources','daily_sources']:
        for item in source002.get(section,[]):bind(item['path'],item['sha256'])
    overlays.append(dict(stage='002',path=receipt002['overlay_path'],sha256=receipt002['overlay_sha256']))
    bundle_specs=[('011','stage011_needed_local_completed','stage011_independent_review',
        '8cdfdbba2a15d12e04c6792b9073d53744f4cb0e711f2f67e452fed7705528fa','qualified_research_overlay'),
        ('015','stage015_daily_recovered_minute_delta','stage015_independent_review',
        '3512261d2191384f1099e7fbb77eda9622c9610ca855ad1d4607ad33e76552c9','qualified_research_overlay'),
        ('020','stage020_reviewed_provider_overlay','stage020_independent_review',review020_sha,'qualified_research_overlay')]
    for label,dirname,reviewdir,reviewsha,flag in bundle_specs:
        folder=LINE/'outputs'/dirname;review_path=LINE/'outputs'/reviewdir/'review_receipt.json'
        review=read(review_path,reviewsha)
        if review.get(flag)is not True or review.get('p0_findings',0)or review.get('p1_findings',0):raise ValueError('stack_review_not_passed')
        summary=read(folder/'summary.json',review['source_summary_sha256'])
        if label=='011':
            if (summary.get('original_sources_never_opened_for_write')is not True or
                review.get('base_and_Stage002_current_SHA_unchanged')is not True or
                summary['artifact_sha256']['input_manifest.json']!=review['source_input_manifest_sha256']):
                raise ValueError('stage011_signed_source_commitment_missing')
        elif summary.get('all_inputs_unchanged')is not True:raise ValueError('stack_inputs_not_unchanged')
        for name,value in summary['artifact_sha256'].items():bind(folder/name,value)
        inputs=read(folder/'input_manifest.json',summary['artifact_sha256']['input_manifest.json'])
        for path,value in inputs.items():bind(path,value)
        for path,value in review.get('source_fingerprints',{}).items():bind(path,value)
        overlays.append(dict(stage=label,path=str(folder/'overlay.csv'),sha256=summary['artifact_sha256']['overlay.csv']))
        bundles.append(dict(stage=label,summary_path=str(folder/'summary.json'),summary_sha256=review['source_summary_sha256'],
            review_path=str(review_path),review_sha256=reviewsha))
    folder016=LINE/'outputs/stage016_source859_qualification'
    review016_path=LINE/'outputs/stage016_independent_review/review_receipt.json'
    if str(review016_path)not in files:raise ValueError('stage020_did_not_bind_stage016_review')
    review016=read(review016_path,files[str(review016_path)])
    if review016.get('qualified_research_source859_delta')is not True or review016.get('p0_findings',0)or review016.get('p1_findings',0):
        raise ValueError('stage016_review_not_passed')
    summary016=read(folder016/'summary.json',review016['source_summary_sha256'])
    for name,value in summary016['artifact_sha256'].items():bind(folder016/name,value)
    inputs016=read(folder016/'input_manifest.json',summary016['artifact_sha256']['input_manifest.json'])
    for path,value in inputs016.items():bind(path,value)
    for path,value in review016.get('source_fingerprints',{}).items():bind(path,value)
    review021_path=LINE/'outputs/stage021_independent_review/review_receipt.json'
    review021=read(review021_path,review021_sha)
    if review021.get('qualified_research_wait_gate')is not True or review021.get('p0_findings',0)or review021.get('p1_findings',0):
        raise ValueError('stage021_review_not_passed')
    gate_path=Path(__file__).with_name('stage021_blocking_data_gate.py').resolve()
    if str(gate_path)not in review021.get('source_fingerprints',{}):raise ValueError('stage021_module_not_review_bound')
    for path,value in review021['source_fingerprints'].items():bind(path,value)
    for path in [Path(__file__),PROTOCOL,SOURCE001,SOURCE_PROTOCOL,DESIGN/'source_stage001_original.py',DESIGN/'source_diff.patch']:
        bind(path)
    demand=LINE/'outputs/stage010_reachable_demand/demand.csv'
    if str(demand)not in files:raise ValueError('stage010_demand_not_in_frozen_stack')
    manifest=dict(schema='stage022_qualified_data_stack_v1',status='frozen_ready_for_offline_preflight',
        source001_sha256=SOURCE001_SHA,base_minute_sha256=EXPECTED_MINUTE,append_order=['002','011','015','020'],
        overlays=overlays,bundles=bundles,outer_correction=dict(summary_path=str(folder016/'summary.json'),
            summary_sha256=review016['source_summary_sha256'],review_path=str(review016_path),review_sha256=files[str(review016_path)]),
        gate_review_path=str(review021_path),gate_review_sha256=review021_sha,demand_path=str(demand),
        initial_qualification='inherited_accepted_baseline_plus_usage_limited859_not_global_price_recertification',
        full_excludes_remaining_source859=True,anchor859_only_stage010_canonical_first_key=True,
        source_fingerprints=files,financial_replays=0,orders=0,production_qualified=False)
    atomic_json(STACK_PATH,manifest)
    print(json.dumps(dict(status=manifest['status'],path=str(STACK_PATH),sha256=sha256(STACK_PATH),input_files=len(files))))


def read_data_stack(path,expected_sha):
    if sha256(path)!=expected_sha:raise ValueError('data_stack_manifest_changed')
    manifest=json.loads(Path(path).read_text())
    if manifest.get('schema')!='stage022_qualified_data_stack_v1'or manifest.get('append_order')!=['002','011','015','020']:
        raise ValueError('data_stack_shape_changed')
    if manifest.get('source001_sha256')!=SOURCE001_SHA or manifest.get('base_minute_sha256')!=EXPECTED_MINUTE:
        raise ValueError('data_stack_source_identity_changed')
    for source,digest in manifest['source_fingerprints'].items():
        if sha256(source)!=digest:raise ValueError(f'data_stack_input_changed:{source}')
    return dict(manifest,path=str(Path(path).resolve()),sha256=expected_sha)


def inherited_qualification_predicates(groups,allowed016,demand,calendar):
    """Two compact indexes: an anchor-only 859 key must never grant full usage."""
    import pandas as pd
    import stage002_local_minute_overlay as local_minutes
    full={};anchor_only={};remaining859={};total=0;actual016=0
    for symbol,frame in groups.items():
        stamps=pd.DatetimeIndex(frame.bar_datetime);source=frame.get('minute_source',pd.Series('',index=frame.index))
        bad=source.eq('stage859_tqsdk_backtest').to_numpy()
        admitted={stamp for s,stamp in allowed016 if s==str(symbol)and stamp in stamps}
        actual016+=len(admitted)
        full[str(symbol)]=pd.DatetimeIndex(stamps[~bad]).union(pd.DatetimeIndex(sorted(admitted))).unique()
        remaining859[str(symbol)]=set(stamps[bad]);total+=len(stamps)
    for row in demand.loc[demand.requirement_kind.eq('anchor')].itertuples():
        symbol=str(row.vt_symbol)
        if symbol not in remaining859 or not remaining859[symbol]:continue
        first=local_minutes.session_grid(symbol,row.execution_trade_date,calendar)[0]
        if first in remaining859[symbol]:anchor_only.setdefault(symbol,set()).add(first)
    anchor={symbol:stamps.union(pd.DatetimeIndex(sorted(anchor_only.get(symbol,set())))).unique()for symbol,stamps in full.items()}
    def predicate(index):
        return lambda symbol,stamp:bool(str(symbol)in index and pd.Timestamp(stamp)in index[str(symbol)])
    audit=dict(scope='inherited_accepted_baseline_plus_usage_limited859_not_global_price_recertification',
        loaded_rows=total,qualified_full_keys=sum(map(len,full.values())),
        extra_anchor_only859_keys=sum(map(len,anchor_only.values())),stage016_scope_keys=len(allowed016),
        stage016_scope_keys_actually_present=actual016,
        remaining_source859_rows=sum(map(len,remaining859.values())))
    return predicate(full),predicate(anchor),audit


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arm',choices=['C0'],default='C0')
    parser.add_argument('--attempt',type=int,default=3,help='Only preserved C0 attempt3; never overwrites.')
    parser.add_argument('--data-stack-manifest',type=Path,default=STACK_PATH)
    parser.add_argument('--data-stack-sha256')
    parser.add_argument('--stage020-review-sha256')
    parser.add_argument('--stage021-review-sha256')
    action=parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--preflight',action='store_true');action.add_argument('--run',action='store_true')
    action.add_argument('--freeze-data-stack',action='store_true')
    args=parser.parse_args()
    if args.freeze_data_stack:
        if not args.stage020_review_sha256 or not args.stage021_review_sha256:parser.error('both upstream review SHA values required')
        freeze_data_stack(args.stage020_review_sha256,args.stage021_review_sha256);return
    if args.attempt!=3 or not args.data_stack_sha256:parser.error('only C0 attempt3 with fixed --data-stack-sha256')
    arm=args.arm;output=resolve_attempt_output(OUTPUT,arm,args.attempt);shared=OUTPUT/'shared_empty_signal_inputs'
    if args.run and output.exists():raise FileExistsError(f'existing_attempt_refusing_repeat:{output}')
    configure_runtime(shared)
    minute_overlay=read_data_stack(args.data_stack_manifest,args.data_stack_sha256)
    if sha256(SOURCE001)!=SOURCE001_SHA:raise ValueError('source001_changed')
    for name,digest in ACCEPTED_CODE.items():
        if sha256(ROOT/name) != digest:raise ValueError(f'accepted_correctness_code_changed:{name}')
    if sha256(FEATURES) != EXPECTED_FEATURES:raise ValueError('weekly_features_changed')
    lookup=WeeklyLookup.read(FEATURES)
    accepted=json.loads((OLD/'input_manifest.json').read_text())
    recorder=InputRecorder(accepted)
    recorder.extra.update(Path(path).resolve()for path in minute_overlay['source_fingerprints'])
    recorder.extra.update([args.data_stack_manifest.resolve(),SOURCE001,SOURCE_PROTOCOL,
        DESIGN/'source_stage001_original.py',DESIGN/'source_diff.patch'])
    sys.addaudithook(recorder.audit)
    recorder.enabled=True
    for path in recorder.extra:
        recorder.record(path)
        resolved=path.resolve()
        if resolved.is_file()and str(resolved)not in recorder.files:
            # Frozen source_diff.patch is an input too; the unchanged recorder's
            # extension allowlist intentionally predates this evidence format.
            recorder.files[str(resolved)]=dict(sha256=sha256(resolved),bytes=resolved.stat().st_size,
                accepted_stage251_match=False,explicit_qualified_data_stack_input=True)
    import pandas as pd
    import vnpy_portfoliostrategy
    import analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow as s901
    import stage002_local_minute_overlay as local_minutes
    import stage016_source859_qualification as qualified_delta
    import stage021_blocking_data_gate as wait_gate
    overlay_parts=[]
    for item in minute_overlay['overlays']:
        frame=local_minutes.normal_times(pd.read_csv(item['path']))
        frame['qualified_stack_layer']=item['stage'];overlay_parts.append(frame)
    overlay_frame=pd.concat(overlay_parts,ignore_index=True,sort=False)
    del overlay_parts
    if overlay_frame.duplicated(['vt_symbol','bar_datetime']).any():raise ValueError('data_stack_append_key_overlap')
    correction=minute_overlay['outer_correction']
    qualified=qualified_delta.read_qualified_delta(correction['summary_path'],correction['summary_sha256'],
        correction['review_path'],correction['review_sha256'])
    demand=pd.read_csv(minute_overlay['demand_path'])
    calendar=pd.DatetimeIndex(pd.to_datetime(pd.read_csv(local_minutes.MAPPING,usecols=['date']).date).drop_duplicates().sort_values())
    from qmt_backtest_runtime_guard import assert_stage196_database_sentinels
    from qmt_roll_official_baseline_identity import assert_official_checkout_matches_active_material
    from qmt_roll_official_strategy_material_resolver import load_active_material_release,assert_runtime_materials_match_checkout,verify_material_file,ActiveMaterialError
    identity=asdict(assert_official_checkout_matches_active_material(ROOT))
    if identity != IDENTITY:raise ValueError('formal_parameter_identity_changed')
    active=load_active_material_release(ROOT/'official_strategy_materials/CURRENT.json',repo_root=ROOT)
    drift=''
    try:assert_runtime_materials_match_checkout(active)
    except ActiveMaterialError as error:drift=str(error)
    # Explicit, bounded accepted source overlay. Unrelated material drift fails.
    allowed=set(ACCEPTED_CODE)|{'skills/futures-live-execution-sop/SKILL.md'}
    for row in active.manifest['files']:
        name=str(row.get('source_path',''))
        if row.get('role') not in ('runtime_code','strategy_config','operational_config') or name.startswith('promotion_source:') or name in allowed:continue
        verify_material_file(ROOT/name,row)
    assert_stage196_database_sentinels()
    if not Path(vnpy_portfoliostrategy.__file__).resolve().is_relative_to(VENDOR):raise ValueError('portfolio_vendor_changed')
    if sha256(s901.s861.FULL_MINUTE_BARS_PATH) != EXPECTED_MINUTE:raise ValueError('accepted_minute_cache_changed')
    recorder.record(s901.s861.FULL_MINUTE_BARS_PATH)
    metadata=s901.s513._metadata()
    import qmt_roll_ai_selection_pairwise_runtime as pairwise
    model_smoke=model_runtime_smoke(pairwise.DEFAULT_MODEL_PATH,pairwise.DEFAULT_SUMMARY_PATH)
    if s901.build_official_live_strategy_overrides().get('enable_stage847_half_r_stop_retry') is not True:raise ValueError('half_r_must_remain_enabled')
    external=Path(s901.s513._c3_overrides(pd.Timestamp(START).to_pydatetime())['supply_demand_signal_path'])
    if external.parent != shared or external.exists():raise ValueError('historical_supply_demand_input_mismatch')
    ai_path=s901.OFFICIAL_LIVE_AI_ELIGIBILITY_PATH
    # Use the existing accepted historical AI validator as an imported function;
    # no old main or old identity gate is changed or executed.
    sys.path.insert(0,str(ROOT/'research/lines/futures_trend_rollover_shape_same_volume/tools'))
    from stage249_historical_replay import audit_historical_ai_pool
    ai_audit=audit_historical_ai_pool(ai_path,s901._required_ai_eval_dates(pd.Timestamp(START),pd.Timestamp(END)))
    if ai_audit['eligibility_sha256'] != accepted[str(Path(ai_path).relative_to(ROOT))]:raise ValueError('historical_ai_changed')
    old_settings=json.loads((OLD/'actual_strategy_settings.json').read_text())[0]['actual']
    reference_shared=Path(old_settings['supply_demand_signal_path']).parent
    profile=capture_formal_profile(s901,metadata,pd.Timestamp(START),pd.Timestamp(END))
    predicted_parameters=dict(spec=asdict(profile['spec']),contract_sizes=metadata['sizes'],
        rates=metadata['rates'],slippages=metadata['slippages'],priceticks=metadata['priceticks'])
    reference=json.loads((OLD/'effective_parameters.json').read_text())
    if normalize_reference(json_safe(predicted_parameters),shared,reference_shared) != normalize_reference(reference,shared,reference_shared):
        raise ValueError('preflight_effective_parameters_drift_from_accepted_A')
    predicted_settings=s901.s847.s827.s772._build_setting(metadata=metadata,spec=profile['spec'],
        base_c3_overrides=dict(s901.s513._c3_overrides(pd.Timestamp(START).to_pydatetime())),start=pd.Timestamp(START))
    predicted_actual={k:v for k,v in predicted_settings.items() if k in old_settings}
    if normalize_reference(json_safe(predicted_actual),shared,reference_shared) != normalize_reference(old_settings,shared,reference_shared):
        raise ValueError('preflight_requested_settings_drift_from_accepted_A')
    # Imported project/vendor sources are cheap to freeze and cover helper drift
    # without hashing unrelated raw datasets or treating CURRENT as a code guard.
    runtime_code={}
    for module in list(sys.modules.values()):
        filename=getattr(module,'__file__',None)
        if not filename:continue
        path=Path(filename).resolve()
        if path.suffix=='.py' and path.is_file() and (path.is_relative_to(PROJECT) or path.is_relative_to(VENDOR)):
            recorder.extra.add(path);recorder.record(path);runtime_code[str(path)]=recorder.files[str(path)]['sha256']
    preflight=dict(status='passed_offline_preflight_no_financial_replay',arm=arm,attempt=args.attempt,
        financial_replays=0,production_qualified=False,formal_identity_gate='not_passed_for_production',
        active_parameter_identity=identity,runtime_material_drift=drift,accepted_correctness_code=ACCEPTED_CODE,
        input_fingerprints=recorder.files,weekly_feature_sha256=EXPECTED_FEATURES,weekly_rows=len(lookup.rows),
        minute_sha256=EXPECTED_MINUTE,strict_minutes=True,period=[START,END],capital=150000,
        metadata_contract_count=len(metadata['vt_symbols']),shared_empty_signal_dir=str(shared),
        ai_pool_audit=ai_audit,runtime=dict(python=sys.executable,portfolio=vnpy_portfoliostrategy.__file__,
            pandas=pd.__version__,source_head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()),
        parameters_equal_accepted_A=True,requested_settings_equal_accepted_A=True,runtime_code_sha256=runtime_code,
        model_runtime_smoke=model_smoke,local_minute_overlay=minute_overlay,
        data_adapter='Stage022 qualified stack plus Stage021 bounded same-engine wait; alpha unchanged C0',
        source001_sha256=SOURCE001_SHA,data_stack_sha256=args.data_stack_sha256,
        wait_seconds_max=WAIT_SECONDS,whole_run_seconds_max=RUN_SECONDS,
        broker_connections=0,order_api_calls=0,cancel_api_calls=0)
    if args.preflight:
        recorder.verify()
        folder=OUTPUT/'preflight';folder.mkdir(parents=True,exist_ok=True)
        write_json(folder/f'{output.name}.json',preflight)
        print(json.dumps({k:preflight[k] for k in ('status','arm','financial_replays','production_qualified','weekly_rows','metadata_contract_count','strict_minutes')}))
        return
    reserve_attempt(output)
    started=datetime.now().astimezone();began=time.monotonic()
    source_bytes=Path(__file__).read_bytes()
    (output/'runner_used.py').write_bytes(source_bytes)
    if sha256(output/'runner_used.py')!=sha256(Path(__file__)):raise ValueError('runner_snapshot_failed')
    (output/'source_stage001_original.py').write_bytes((DESIGN/'source_stage001_original.py').read_bytes())
    (output/'source_diff.patch').write_bytes((DESIGN/'source_diff.patch').read_bytes())
    (output/'data_stack_manifest.json').write_bytes(args.data_stack_manifest.read_bytes())
    strategy=build_research_strategy(s901.s847.QmtRollPortfolioStrategyStage847C9StopRetry,lookup,arm)
    strategy.stage827_require_complete_minutes=True
    capture={};actual=[];wait_audit=[];resolver_audit=[];qualification_audit={}
    resolver=FileWaitResolver(output/'data_wait',recorder,resolver_audit,began)
    try:
        with (output/'engine.log').open('w',buffering=1) as log,redirect_stdout(log),redirect_stderr(log):
            with whole_run_budget(),local_minutes.temporary_minute_overlay(s901,overlay_frame),qualified_delta.temporary_qualified_minute_delta(s901,qualified),replace_strategy_class(s901.s847,strategy),capture_actual_settings(s901.s847.Stage847StopRetryEngine) as actual,capture_engine(s901.s847.Stage847StopRetryEngine) as capture:
                s901._ensure_c9_minute_bars(metadata)
                full_keys,anchor_keys,qualification_audit=inherited_qualification_predicates(
                    s901._FULL_MINUTE_BY_SYMBOL_CACHE,qualified.allowed_keys,demand,calendar)
                with wait_gate.qualified_wait_scope(s901.s847.Stage847StopRetryEngine,resolver,wait_audit,
                    qualified_existing_keys=full_keys,qualified_anchor_existing_keys=anchor_keys):
                    combined,frames,spec=s901._run_live_c9(metadata,pd.Timestamp(START),pd.Timestamp(END))
        if len(actual) != 1 or actual[0]['supply_demand_signal_rows'] != 0:raise ValueError('unexpected_actual_strategy_or_supply_rows')
        if normalize_reference(json_safe(actual[0]['actual']),shared,reference_shared) != normalize_reference(old_settings,shared,reference_shared):
            write_json(output/'actual_strategy_settings_mismatch.json',dict(actual=actual[0]['actual'],reference=old_settings))
            raise ValueError('actual_settings_drift_from_accepted_A')
        parameters=dict(spec=asdict(spec),contract_sizes=metadata['sizes'],rates=metadata['rates'],slippages=metadata['slippages'],priceticks=metadata['priceticks'])
        reference=json.loads((OLD/'effective_parameters.json').read_text())
        if normalize_reference(json_safe(parameters),shared,reference_shared) != normalize_reference(reference,shared,reference_shared):
            write_json(output/'effective_parameters_mismatch.json',parameters)
            raise ValueError('effective_parameters_drift_from_accepted_A')
        write_json(output/'qualified_wait_audit.json',dict(gate=wait_audit,resolver=resolver_audit,initial_qualification=qualification_audit))
        recorder.verify()
        if any(shared.iterdir()):raise ValueError('historical_shared_signal_input_was_written')
        for name,digest in ACCEPTED_CODE.items():
            if sha256(ROOT/name) != digest:raise ValueError(f'accepted_correctness_code_changed_during_run:{name}')
        clock=canonical_trade_enums(pd.DataFrame(capture['trades']))
        trades=canonical_trade_enums(frames['trades'])
        usage=pd.DataFrame(capture['usage'])
        if trades.empty:raise ValueError('no_trades_not_a_successful_candidate')
        if len(usage) != len(trades) or usage.trade_id.duplicated().any() or set(usage.trade_id) != set(trades.trade_id):raise ValueError('execution_usage_not_one_to_one')
        sources=clock.trade_id.map(usage.set_index('trade_id').price_source).fillna('')
        synthetic=clock.offset.ne('开') & sources.str.startswith('stage')
        clock.loc[synthetic,'exit_reason']=sources[synthetic]
        frames['trades']=attach_trading_dates(trades,clock)
        stats=s901.s650._metrics(combined,spec.capital,1.0)
        stats['result_scope']='offline_first_screen_A0_C0';stats['production_qualified']=False
        for name,frame in frames.items():
            if frame.empty and not len(frame.columns):frame=pd.DataFrame(columns=['date','vt_symbol','event','reason'])
            frame=frame.copy();frame['research_arm']=arm;frame['production_qualified']=False
            frame.to_csv(output/f'{name}.csv',index=False,encoding='utf-8-sig')
        combined.to_csv(output/'daily.csv',index=False,encoding='utf-8-sig')
        clock.to_csv(output/'execution_clock.csv',index=False,encoding='utf-8-sig')
        usage.to_csv(output/'execution_proxy_usage.csv',index=False,encoding='utf-8-sig')
        pd.DataFrame(capture['equity']).to_csv(output/'internal_equity_daily.csv',index=False)
        pd.DataFrame(capture['minute_requests']).to_csv(output/'minute_scan_requests.csv',index=False)
        pd.DataFrame(capture['anchor_requests']).to_csv(output/'execution_anchor_requests.csv',index=False)
        audit=pd.DataFrame(capture['weekly_gate'])
        audit.to_csv(output/'weekly_gate_audit.csv',index=False,encoding='utf-8-sig')
        counts=dict(flat_entry_plans=len(audit),ready_plans=int(audit.weekly_ready.sum()),
            unknown_plans=int((~audit.weekly_ready).sum()),original_native_openable_plans=int(audit.native_openable_before.sum()),
            blocked_plans=int(audit.gate_blocked.sum()),decision_counts=dict(Counter(audit.decision)),
            unknown_reasons=dict(Counter(audit.loc[~audit.weekly_ready,'unknown_reason'])))
        minutes=pd.DataFrame(capture['minute_requests'])
        minute_summary=dict(strict_required=True,request_rows=len(minutes),captured_bar_failures=len(capture['failures']),
            coverage_status_counts=dict(Counter(minutes.get('coverage_status',[]))),
            missing_bar_count=int(pd.to_numeric(minutes.get('missing_bar_count',pd.Series(dtype=float)),errors='coerce').fillna(0).sum()))
        if minute_summary['missing_bar_count']:raise ValueError('strict_minutes_incomplete')
        provenance=dict(status='completed_pending_independent_review',arm=arm,attempt=args.attempt,started_at=started,
            completed_at=datetime.now().astimezone(),elapsed_seconds=time.monotonic()-began,
            result_scope='offline_first_screen_A0_C0',production_qualified=False,
            correctness_code_sha256=ACCEPTED_CODE,minute_input_sha256=EXPECTED_MINUTE,
            all_consumed_inputs_unchanged_during_run=True,input_fingerprints=recorder.files,
            weekly_feature_sha256=EXPECTED_FEATURES,protocol_sha256=sha256(PROTOCOL),
            source_adapter_sha256=sha256(output/'runner_used.py'),active_parameter_identity=identity,
            source001_sha256=SOURCE001_SHA,source_diff_sha256=sha256(output/'source_diff.patch'),
            data_stack_sha256=args.data_stack_sha256,qualified_wait_audit_sha256=sha256(output/'qualified_wait_audit.json'),
            data_adapter_changed=True,alpha_unchanged_from_original_C0=True,
            strict_minutes=True,captured_bar_failure_count=0,source_head=preflight['runtime']['source_head'],
            actual_settings_equal_accepted_A=True,parameters_equal_accepted_A=True,
            only_candidate_delta='ready completed-week MACD slope permission on initial flat entry' if arm=='C0' else 'none; observe weekly state only',
            vendor_swallowed_bar_exception_guard=True,order_api_count=0,cancel_api_count=0,
            shared_empty_signal_dir=str(shared),runtime=preflight['runtime'],model_runtime_smoke=model_smoke,local_minute_overlay=minute_overlay)
        write_json(output/'actual_strategy_settings.json',actual)
        write_json(output/'effective_parameters.json',parameters)
        write_json(output/'input_manifest.json',recorder.files)
        write_json(output/'run_provenance.json',provenance)
        write_json(output/'metrics.json',stats)
        summary=dict(status=provenance['status'],arm=arm,attempt=args.attempt,statistics=stats,gate_counts=counts,
            strict_minutes=minute_summary,actual_settings=actual,input_fingerprints=recorder.files,
            weekly_feature_sha256=EXPECTED_FEATURES,financial_replays=1,production_qualified=False,
            output_directory=str(output),model_runtime_smoke=model_smoke,local_minute_overlay=minute_overlay,broker_connections=0,order_api_calls=0,cancel_api_calls=0)
        write_json(output/'summary.json',summary)
        print(json.dumps(json_safe(dict(status=summary['status'],arm=arm,statistics=stats,gate_counts=counts)),ensure_ascii=False))
    except BaseException as error:
        recorder.enabled=False
        write_json(output/'run_failure.json',dict(status='failed_closed_no_accepted_performance',arm=arm,attempt=args.attempt,
            error=repr(error),started_at=started,failed_at=datetime.now().astimezone(),
            financial_replay_attempts=1,production_qualified=False,input_fingerprints=recorder.files,
            captured_bar_failures=capture.get('failures',[]),actual_settings=actual,
            minute_requests=capture.get('minute_requests',[]),local_minute_overlay=minute_overlay,
            qualified_wait_gate_audit=wait_audit,resolver_audit=resolver_audit,initial_qualification=qualification_audit,
            source001_sha256=SOURCE001_SHA,data_stack_sha256=args.data_stack_sha256,
            data_adapter_changed=True,alpha_unchanged_from_original_C0=True,order_api_count=0,cancel_api_count=0))
        raise


if __name__=='__main__':main()
