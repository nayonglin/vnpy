"""One unchanged provider batch with idle waits bounded by one total budget."""
from __future__ import annotations
import argparse
from contextlib import redirect_stdout,redirect_stderr
from datetime import datetime
from importlib import metadata
import json
import logging
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import pandas as pd

import stage002_local_minute_overlay as validation
import stage007_tqsdk_stream_probe as safety
import stage012_provider_batch as core

ROOT,LINE=validation.ROOT,validation.LINE
OLD=LINE/'outputs/stage017_required_ap210_batch'
OUTPUT=LINE/'outputs/stage018_provider_wait_budget'
ATTEMPT=OUTPUT/'network_attempt1'
PROTOCOL=LINE/'stages/20261018_0058_stage018_provider_wait_budget_protocol.md'
OLD_MANIFEST_SHA='a58a875df23d2dda6c797d94e7f46275f0b832377325ef7cf68423b7601a0219'
OLD_PREFLIGHT_SHA='2ec49fcb7d5b537697b70325a6eedbbda6a55af474cee28f4377228e436ab331'
AP=('AP210.CZCE','2022-04-06')
SOFT,HARD=570,600


def read_manifest():
    path=OUTPUT/'batch_manifest.json'
    if validation.sha256(path)!=OLD_MANIFEST_SHA:raise ValueError('frozen_stage017_manifest_changed')
    manifest=json.loads(path.read_text());expected={}
    for target in manifest['targets']:
        grid=pd.DatetimeIndex(target['expected_timestamps'])
        if len(grid)!=target['expected_minutes']or grid.has_duplicates:raise ValueError('invalid_target_grid')
        expected.setdefault(target['vt_symbol'],[]).extend(grid)
    if any(len(value)!=len(set(value))for value in expected.values()):raise ValueError('duplicate_target_minute')
    ap=[t for t in manifest['targets']if(t['vt_symbol'],t['execution_trade_date'])==AP]
    if(len(expected),len(manifest['targets']),sum(map(len,expected.values())))!=(8,39,12945):raise ValueError('frozen_batch_scope_changed')
    if len(ap)!=1 or ap[0]['expected_minutes']!=225:raise ValueError('mandatory_ap210_target_invalid')
    core.BatchCollector(expected)
    return manifest,expected


def prepare():
    if OUTPUT.exists():raise FileExistsError('existing_stage018_refusing_reprepare')
    if validation.sha256(OLD/'batch_manifest.json')!=OLD_MANIFEST_SHA:raise ValueError('old_manifest_changed')
    if validation.sha256(OLD/'preflight.json')!=OLD_PREFLIGHT_SHA:raise ValueError('old_preflight_changed')
    OUTPUT.mkdir(parents=True,exist_ok=False)
    (OUTPUT/'batch_manifest.json').write_bytes((OLD/'batch_manifest.json').read_bytes())


def preflight():
    manifest,expected=read_manifest()
    if validation.sha256(OLD/'preflight.json')!=OLD_PREFLIGHT_SHA:raise ValueError('old_preflight_changed')
    previous=json.loads((OLD/'preflight.json').read_text())
    fingerprints=previous['source_fingerprints'].copy()
    for path,digest in fingerprints.items():
        if validation.sha256(path)!=digest:raise ValueError('frozen_original_input_changed')
    if metadata.version('tqsdk')!='3.10.2':raise ValueError('frozen_sdk_version_changed')
    if any(os.environ.get(key)for key in safety.ENDPOINT_ENV):raise ValueError('provider_endpoint_override')
    safety.load_credentials()
    for path in [Path(__file__),PROTOCOL,OLD/'preflight.json',OUTPUT/'batch_manifest.json']:
        fingerprints[str(path)]=validation.sha256(path)
    return dict(status='passed_offline_preflight_no_connection',provider_connections=0,
        contracts=len(expected),target_sessions=len(manifest['targets']),target_minutes=sum(map(len,expected.values())),
        mandatory_AP210_date=AP[1],mandatory_AP210_minutes=225,provider_start=manifest['provider_start'],
        provider_end=manifest['provider_end'],soft_seconds=SOFT,hard_seconds=HARD,provider_attempts_max=1,
        idle_wait_return_false='continue_same_api_until_total_budget',wait_slice_seconds=30,
        copied_manifest_sha256=OLD_MANIFEST_SHA,normal_authorization_required=True,
        credentials_present=True,credential_values_saved=False,auth_checks_unmodified=True,
        tq_dl_not_yet_queried=True,independent_string_series_only=True,no_retry=True,
        raw_sdk_output_policy='DEVNULL',source_fingerprints=fingerprints,financial_replays=0,orders=0,
        prior_timeout_branch_inference_not_proven=True,production_qualified=False)


def collect_with_budget(api,collector,serials,began,diagnostic,save_callback,
                        monotonic=time.monotonic,wall_clock=time.time):
    """False is an idle interval, not a failed provider attempt. Never recreate API."""
    diagnostic.update(idle_waits=0,update_calls=0,ready_serial_count=0)
    last_stamp={};saved=monotonic()
    while len(collector.records)<collector.target_count:
        remaining=SOFT-(monotonic()-began)
        diagnostic['elapsed_seconds']=monotonic()-began
        if remaining<=0:
            diagnostic['phase']='total_soft_budget_reached'
            return 'soft_time_budget_reached'
        diagnostic['phase']='wait_update_call'
        try:updated=api.wait_update(deadline=wall_clock()+min(30.,remaining))
        except BaseException:
            diagnostic['phase']='wait_update_raised'
            raise
        diagnostic['update_calls']+=1
        if not updated:
            diagnostic['idle_waits']+=1
            diagnostic['phase']='wait_update_returned_false'
            diagnostic['elapsed_seconds']=monotonic()-began
            save_callback()
            continue
        diagnostic['phase']='observe_ready_serials';ready=0
        for symbol,serial in serials.items():
            if not api.is_serial_ready(serial):continue
            ready+=1;stamp=serial.iloc[-1]['datetime']
            if last_stamp.get(symbol)==stamp:continue
            initial=symbol not in last_stamp;last_stamp[symbol]=stamp
            collector.observe(symbol,serial,initial=initial)
        diagnostic['ready_serial_count']=ready
        if monotonic()-saved>=15:save_callback();saved=monotonic()
    diagnostic['phase']='all_target_minutes_completed'
    return 'all_target_minutes_completed'


def save(collector,diagnostic):
    raw,evidence=collector.frames()
    for name,frame in [('raw_completed_minutes.csv',raw),('completion_evidence.csv',evidence)]:
        temporary=ATTEMPT/(name+'.tmp');frame.to_csv(temporary,index=False);os.replace(temporary,ATTEMPT/name)
    validation.write_json(ATTEMPT/'progress.json',dict(completed_minutes=len(raw),target_minutes=collector.target_count,
        updated_at=datetime.now().astimezone().isoformat(),diagnostic=dict(diagnostic),financial_replays=0))


def qualify(collector,manifest):
    raw,evidence=collector.frames();raw=validation.normal_times(raw);empty=raw.iloc[:0].copy()
    proofs={(r.vt_symbol,pd.Timestamp(r.bar_datetime))for r in evidence.itertuples()
        if r.completed and pd.Timestamp(r.successor_time)>=pd.Timestamp(r.bar_datetime)+pd.Timedelta(minutes=1)}
    checks=[]
    for target in manifest['targets']:
        grid=pd.DatetimeIndex(target['expected_timestamps'])
        _,check=validation.validate_session(raw.loc[raw.vt_symbol.eq(target['vt_symbol'])],grid,target['daily_reference'],empty)
        complete=all((target['vt_symbol'],stamp)in proofs for stamp in grid)
        checks.append(dict(vt_symbol=target['vt_symbol'],execution_trade_date=target['execution_trade_date'],
            accepted=bool(check['status']=='accepted'and complete),completion_evidence_complete=complete,**check))
    ap=next(item for item in checks if(item['vt_symbol'],item['execution_trade_date'])==AP)
    quality=dict(sessions=checks,accepted_sessions=sum(item['accepted']for item in checks),target_sessions=len(checks),
        all_sessions_accepted=all(item['accepted']for item in checks),required_ap210_accepted=ap['accepted'],
        raw_rows=len(raw),financial_replays=0,cache_or_overlay_written=False)
    validation.write_json(ATTEMPT/'quality.json',quality)
    return quality


def worker(parent_pid):
    if os.getppid()!=parent_pid or not(ATTEMPT/'attempt_started.json').is_file():return 2
    manifest,expected=read_manifest();collector=core.BatchCollector(expected)
    api=None;created=False;provider=False;tq_dl=None;status='initializing';finished_types=()
    began=time.monotonic();diagnostic=dict(phase='initializing',elapsed_seconds=0.)
    with open(os.devnull,'w')as discard,redirect_stdout(discard),redirect_stderr(discard):
        logging.disable(logging.CRITICAL)
        try:
            from tqsdk import TqApi,TqAuth,TqBacktest,TqSim,BacktestFinished
            finished_types=(BacktestFinished,)
            diagnostic['phase']='credential_loading';username,password=safety.load_credentials()
            sim=TqSim();created=True;provider=True;diagnostic['phase']='api_initializing'
            api=TqApi(account=sim,auth=TqAuth(username,password),
                backtest=TqBacktest(start_dt=datetime.fromisoformat(manifest['provider_start']),
                    end_dt=datetime.fromisoformat(manifest['provider_end'])),debug=False,web_gui=False)
            username=password=None
            diagnostic['phase']='permission_boolean_check';tq_dl=bool(api._auth._has_feature('tq_dl'))
            serials={}
            async def subscribe():
                for symbol in sorted(expected):
                    native,exchange=symbol.rsplit('.',1)
                    serials[symbol]=api.get_kline_serial(f'{exchange}.{native}',60,data_length=10000)
            diagnostic['phase']='schedule_subscriptions';api.create_task(subscribe())
            status=collect_with_budget(api,collector,serials,began,diagnostic,lambda:save(collector,diagnostic))
        except finished_types:status='provider_finished';diagnostic['phase']='provider_finished'
        except BaseException as error:
            status='provider_or_local_failed'
            validation.write_json(ATTEMPT/'safe_error.json',{**safety.safe_error(error),'phase':diagnostic['phase']})
        finally:
            diagnostic['elapsed_seconds']=time.monotonic()-began;save(collector,diagnostic)
            if api is not None:
                try:api.close()
                except BaseException as error:
                    status='close_failed'
                    validation.write_json(ATTEMPT/'safe_close_error.json',{**safety.safe_error(error),'phase':'api_close'})
    quality=qualify(collector,manifest)
    validation.write_json(ATTEMPT/'worker_receipt.json',dict(status=status,provider_attempts=int(provider),
        local_TqSim_created=created,tq_dl_permission=tq_dl,tq_dl_check_readonly=True,download_interface_switched=False,
        completed_minutes=len(collector.records),target_minutes=collector.target_count,diagnostic=diagnostic,
        required_ap210_accepted=quality['required_ap210_accepted'],accepted_sessions=quality['accepted_sessions'],
        financial_replays=0,orders=0,cancels=0,broker_or_ctp_connections=0,model_fits=0,
        raw_sdk_output_saved=False,credential_values_saved=False,cache_or_overlay_written=False,production_qualified=False))
    return 0 if quality['all_sessions_accepted']and status=='all_target_minutes_completed'else 1


def run_once():
    if ATTEMPT.exists():raise FileExistsError('existing_stage018_attempt_refusing_retry')
    frozen=json.loads((OUTPUT/'preflight.json').read_text())
    if preflight()!=frozen:raise ValueError('preflight_changed_since_review')
    ATTEMPT.mkdir(exist_ok=False)
    validation.write_json(ATTEMPT/'attempt_started.json',dict(started_at=datetime.now().astimezone().isoformat(),
        provider_attempts_max=1,soft_seconds=SOFT,hard_seconds=HARD,automatic_retry=False,financial_replays=0,orders=0))
    began=time.monotonic();process=None;killed=False
    try:
        process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--worker',str(os.getpid())],
            cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
        try:code=process.wait(timeout=HARD)
        except subprocess.TimeoutExpired:
            killed=True;os.killpg(process.pid,signal.SIGKILL);process.wait();code=-9
        unchanged=all(validation.sha256(path)==digest for path,digest in frozen['source_fingerprints'].items())
        result=dict(status='hard_timeout'if killed else'worker_terminal',exit_code=code,hard_kill=killed,
            elapsed_seconds=time.monotonic()-began,all_inputs_unchanged=unchanged,provider_attempts_max=1,
            automatic_retry=False,financial_replays=0,orders=0,cancels=0,broker_or_ctp_connections=0,
            raw_sdk_output_saved=False,credential_values_saved=False,cache_or_overlay_written=False,production_qualified=False)
        result['artifact_sha256']={p.name:validation.sha256(p)for p in ATTEMPT.iterdir()if p.is_file()}
        validation.write_json(ATTEMPT/'parent_receipt.json',result)
        print(json.dumps({key:result[key]for key in ['status','exit_code','elapsed_seconds','all_inputs_unchanged']}))
        return 0 if code==0 and unchanged else 1
    finally:
        if process is not None and process.poll()is None:os.killpg(process.pid,signal.SIGKILL);process.wait()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);modes=parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--preflight',action='store_true');modes.add_argument('--run',action='store_true')
    modes.add_argument('--worker',type=int,help=argparse.SUPPRESS);args=parser.parse_args()
    try:
        if args.worker is not None:raise SystemExit(worker(args.worker))
        if args.run:raise SystemExit(run_once())
        prepare();result=preflight();validation.write_json(OUTPUT/'preflight.json',result)
        print(json.dumps({key:result[key]for key in ['status','contracts','target_sessions','target_minutes','provider_start','provider_end']}))
    except BaseException as error:
        if isinstance(error,SystemExit):raise
        print(json.dumps(safety.safe_error(error)));raise SystemExit(1)
