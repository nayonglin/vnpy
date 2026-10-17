"""One normally authorized TqBacktest data probe; offline preflight first."""
from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
from datetime import date, datetime
from importlib import metadata
import json
import logging
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import time

import numpy as np
import pandas as pd

import stage002_local_minute_overlay as validation

ROOT=Path(__file__).resolve().parents[4]
LINE=ROOT/'research/lines/futures_trend_triple_screen'
PROJECT=ROOT/'examples/portfolio_backtesting'
OUTPUT=LINE/'outputs/stage007_tqsdk_stream_probe'
ATTEMPT=OUTPUT/'network_attempt1'
PROTOCOL=LINE/'stages/20261017_2338_stage007_tqsdk_official_stream_probe_protocol.md'
CONFIG=ROOT/'.vntrader/vt_setting.json'
DATABASE=ROOT/'.vntrader/database.db'
MAPPING=PROJECT/'backtest_outputs/tqsdk_all_futures_main_contract_mapping_2010_2026_04.csv'
DAILY_CSV=PROJECT/'downloaded_futures/tqsdk_daily_2010_2026_04/SHFE/rb2010.csv'
SYMBOL='rb2010.SHFE'
TQ_SYMBOL='SHFE.rb2010'
TARGET='2020-08-12'
TIMEOUT=180
RAW_FIELDS=['vt_symbol','bar_datetime',*validation.VALUES]
ENDPOINT_ENV=['TQ_AUTH_URL','TQ_MD_URL','TQ_INS_URL','TQ_TD_URL']


def safe_error(error):
    """Classify in memory; never persist exception text, identity or token."""
    text=str(error).lower()
    if isinstance(error,FileNotFoundError):category='local_source_missing'
    elif any(word in text for word in ['quota','次数','流控','回测上限']):category='quota_rejected'
    elif any(word in text for word in ['认证','authentication','unauthorized','invalid credentials','登录失败']):category='authentication_rejected'
    elif isinstance(error,PermissionError) or any(word in text for word in ['permission','权限','专业版','不支持下载']):category='permission_rejected'
    elif isinstance(error,TimeoutError) or any(word in text for word in ['timeout','timed out','超时']):category='network_or_wait_timeout'
    elif isinstance(error,(ConnectionError,OSError)) or any(word in text for word in ['connect','network','dns','websocket','连接']):category='network_rejected'
    elif isinstance(error,ValueError):category='data_or_preflight_rejected'
    else:category='sdk_or_local_error'
    return dict(category=category,exception_type=type(error).__name__,raw_exception_text_saved=False)


def load_credentials():
    setting=json.loads(CONFIG.read_text())
    values=tuple(str(setting.get(key,''))for key in ['datafeed.username','datafeed.password'])
    if not all(value.strip()for value in values):raise ValueError('local_credentials_missing')
    return values


def tq_local_time(value):
    result=pd.to_datetime(value,unit='ns',utc=True,errors='coerce')
    return result.tz_convert('Asia/Shanghai').tz_localize(None)if pd.notna(result)else pd.NaT


class CompletedCollector:
    def __init__(self,expected):
        self.expected=set(pd.DatetimeIndex(expected));self.records={};self.evidence={}

    def observe(self,serial):
        # Every accepted row has a strictly later observed K-line.  The final
        # forming row is never promoted merely because a replay terminates.
        if len(serial)<2:return
        moments=pd.to_datetime(pd.to_numeric(serial.datetime,errors='coerce'),unit='ns',utc=True,errors='coerce').dt.tz_convert('Asia/Shanghai').dt.tz_localize(None)
        candidates=np.flatnonzero(moments.iloc[:-1].isin(self.expected).to_numpy())
        for position in candidates:
            item=serial.iloc[position];successor=serial.iloc[position+1]
            if not np.isfinite(item['datetime'])or item['datetime']<=0:continue
            stamp=tq_local_time(int(item['datetime']))
            if stamp not in self.expected:continue
            if not np.isfinite(successor['datetime'])or successor['datetime']<=0:continue
            next_time=tq_local_time(int(successor['datetime']))
            if next_time<stamp+pd.Timedelta(minutes=1):raise ValueError('nonforward_successor')
            row=dict(vt_symbol=SYMBOL,bar_datetime=stamp,**{key:float(item[key])for key in validation.VALUES})
            if stamp in self.records:
                if any(not np.isclose(self.records[stamp][key],row[key],rtol=0,atol=0,equal_nan=True)for key in validation.VALUES):
                    raise ValueError('conflicting_completed_bar')
            else:
                self.records[stamp]=row
                self.evidence[stamp]=dict(vt_symbol=SYMBOL,bar_datetime=stamp.isoformat(),
                    successor_time=next_time.isoformat(),method='observed_later_serial_kline',completed=True)

    def frames(self):
        keys=sorted(self.records)
        return (pd.DataFrame([self.records[key]for key in keys],columns=RAW_FIELDS),
            pd.DataFrame([self.evidence[key]for key in keys],columns=['vt_symbol','bar_datetime','successor_time','method','completed']))

    def save(self):
        raw,evidence=self.frames()
        raw.to_csv(ATTEMPT/'raw_completed_minutes.csv',index=False)
        evidence.to_csv(ATTEMPT/'completion_evidence.csv',index=False)


def validate_target(collector,expected,csv_daily,db_daily):
    raw,evidence=collector.frames();empty_base=pd.DataFrame(columns=RAW_FIELDS)
    expected=pd.DatetimeIndex(expected)
    evidence_valid=(set(collector.evidence)==set(expected))and all(
        pd.Timestamp(item['successor_time'])>=stamp+pd.Timedelta(minutes=1)
        for stamp,item in collector.evidence.items())
    _,csv_check=validation.validate_session(raw,expected,csv_daily,empty_base)
    _,database_check=validation.validate_session(raw,expected,db_daily,empty_base)
    return dict(accepted=bool(evidence_valid and csv_check['status']=='accepted'and database_check['status']=='accepted'),
        completion_evidence_complete=bool(evidence_valid),daily_csv_check=csv_check,database_check=database_check,
        expected_minutes=len(expected),raw_rows=len(raw),raw_unique_keys=not raw.bar_datetime.duplicated().any(),
        base_or_overlay_written=False)


def target_grid():
    dates=pd.to_datetime(pd.read_csv(MAPPING,usecols=['date']).date).drop_duplicates().sort_values()
    return validation.session_grid(SYMBOL,TARGET,dates)


def load_daily_references():
    daily=pd.read_csv(DAILY_CSV)
    selected=daily.loc[pd.to_datetime(daily.trade_date).dt.normalize().eq(pd.Timestamp(TARGET))]
    if len(selected)!=1:raise ValueError('daily_csv_target_not_unique')
    csv_daily={key:float(selected.iloc[0][key])for key in validation.VALUES}
    wal=Path(str(DATABASE)+'-wal')
    if wal.exists()and wal.stat().st_size:raise ValueError('nonempty_database_wal')
    with sqlite3.connect(DATABASE.resolve().as_uri()+'?mode=ro&immutable=1',uri=True)as database:
        rows=database.execute("SELECT open_price,high_price,low_price,close_price,volume,open_interest FROM dbbardata WHERE symbol=? AND exchange=? AND interval='d' AND datetime>=? AND datetime<?",('rb2010','SHFE',TARGET,'2020-08-13')).fetchall()
    if len(rows)!=1:raise ValueError('real_database_daily_target_not_unique')
    db_daily=dict(zip(['open','high','low','close','volume','close_oi'],map(float,rows[0])))
    db_daily['open_oi']=float('nan')
    return csv_daily,db_daily


def fingerprints():
    sdk=Path(metadata.distribution('tqsdk').locate_file('tqsdk'))
    paths=[Path(__file__),PROTOCOL,Path(validation.__file__),validation.PROJECT/'qmt_roll_intraday_execution.py',
        MAPPING,DATABASE,DAILY_CSV,*[sdk/item for item in ['api.py','auth.py','tradeable/sim/tqsim.py','backtest/backtest.py','tools/downloader.py']]]
    return {str(path):validation.sha256(path)for path in paths}


def offline_preflight():
    if metadata.version('tqsdk')!='3.10.2':raise ValueError('frozen_sdk_version_changed')
    if any(os.environ.get(key)for key in ENDPOINT_ENV):raise ValueError('nondefault_provider_endpoint_environment')
    load_credentials()  # Only a presence check; never serialize its return.
    expected=target_grid()
    if len(expected)!=345 or expected[0]!=pd.Timestamp('2020-08-11 21:00')or expected[-1]!=pd.Timestamp('2020-08-12 14:59'):
        raise ValueError('frozen_target_grid_changed')
    load_daily_references()  # Exact target availability, not a provider connection.
    hashes=fingerprints()
    old=json.loads((validation.OLD/'input_manifest.json').read_text())
    for path in [DATABASE,MAPPING,DAILY_CSV]:
        if hashes[str(path)]!=old.get(str(path.relative_to(ROOT))):raise ValueError('accepted_reference_source_changed')
    return dict(status='passed_offline_preflight_no_provider_connection',provider_replays=0,
        sdk_version=metadata.version('tqsdk'),tq_symbol=TQ_SYMBOL,duration_seconds=60,
        provider_window=['2020-08-11','2020-08-13'],target_trading_date=TARGET,expected_minutes=len(expected),
        expected_first=expected[0].isoformat(),expected_last=expected[-1].isoformat(),
        parent_wall_clock_timeout_seconds=TIMEOUT,credentials_fields_present=True,credential_values_saved=False,
        auth_checks_unmodified=True,normal_sdk_authorization_required=True,
        explicit_local_TqSim_planned=True,may_consume_one_provider_backtest_quota=True,
        sdk_stdout_stderr_policy='discard_raw_output_and_emit_only_allowlisted_receipt_fields',
        no_retry=True,no_orders=True,no_cache_or_overlay_write=True,financial_strategy_replays=0,
        source_fingerprints=hashes)


def worker(parent_pid):
    if os.getppid()!=parent_pid or not(ATTEMPT/'attempt_started.json').is_file():return 2
    collector=CompletedCollector(target_grid());api=None;sim_created=False;provider_started=False;status='initializing';finished_types=()
    # Raw SDK stdout/stderr and logging are never persisted. The parent also
    # redirects file descriptors to DEVNULL, including native/background output.
    with open(os.devnull,'w')as discard,redirect_stdout(discard),redirect_stderr(discard):
        logging.disable(logging.CRITICAL)
        try:
            from tqsdk import TqApi,TqAuth,TqBacktest,TqSim,BacktestFinished
            finished_types=(BacktestFinished,)
            username,password=load_credentials()
            sim=TqSim();sim_created=True
            provider_started=True
            api=TqApi(account=sim,auth=TqAuth(username,password),
                backtest=TqBacktest(start_dt=date(2020,8,11),end_dt=date(2020,8,13)),debug=False,web_gui=False)
            username=password=None
            serial=api.get_kline_serial(TQ_SYMBOL,60,data_length=1024)
            collector.observe(serial);last_saved=-1
            while len(collector.records)<len(collector.expected):
                if not api.wait_update(deadline=time.time()+30):raise TimeoutError('provider_wait_timeout')
                if not api.is_changing(serial.iloc[-1],'datetime'):continue
                collector.observe(serial)
                if len(collector.records)!=last_saved:
                    collector.save();last_saved=len(collector.records)
            status='target_completed_with_successor_evidence'
        except finished_types:
            status='provider_finished'
        except BaseException as error:
            status='failed'
            validation.write_json(ATTEMPT/'safe_error.json',safe_error(error))
        finally:
            collector.save()
            if api is not None:
                try:api.close()
                except BaseException as error:
                    status='failed';validation.write_json(ATTEMPT/'safe_error.json',safe_error(error))
    quality=None
    if status!='failed':
        try:
            csv_daily,db_daily=load_daily_references()
            quality=validate_target(collector,target_grid(),csv_daily,db_daily)
            validation.write_json(ATTEMPT/'quality.json',quality)
            status='completed_quality_accepted'if quality['accepted']else'completed_quality_rejected'
        except BaseException as error:
            status='failed';validation.write_json(ATTEMPT/'safe_error.json',safe_error(error))
    validation.write_json(ATTEMPT/'worker_receipt.json',dict(status=status,
        provider_replay_attempts=int(provider_started),local_TqSim_created=sim_created,
        financial_strategy_replays=0,broker_or_ctp_connections=0,order_calls=0,cancel_calls=0,
        completed_target_minutes=len(collector.records),sdk_raw_output_saved=False,
        credential_values_saved=False,execution_fallback_enabled=False,production_qualified=False))
    return 0 if status=='completed_quality_accepted'else 1


def run_once():
    began=time.monotonic();deadline=began+TIMEOUT
    if ATTEMPT.exists():raise FileExistsError('existing_provider_attempt_refusing_retry')
    frozen=json.loads((OUTPUT/'preflight.json').read_text())
    current=offline_preflight()
    if frozen!=current:raise ValueError('preflight_changed_since_review')
    ATTEMPT.mkdir(parents=True,exist_ok=False)
    validation.write_json(ATTEMPT/'attempt_started.json',dict(started_at=datetime.now().astimezone().isoformat(),
        target=TQ_SYMBOL,target_trading_date=TARGET,provider_replay_attempts_max=1,timeout_seconds=TIMEOUT,
        local_TqSim_planned=True,financial_strategy_replays=0,credential_values_saved=False))
    process=None;timed_out=False
    try:
        process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--_worker',str(os.getpid())],
            cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
        try:exit_code=process.wait(timeout=max(.01,deadline-time.monotonic()))
        except subprocess.TimeoutExpired:
            timed_out=True;os.killpg(process.pid,signal.SIGKILL);process.wait();exit_code=-9
        unchanged=all(validation.sha256(path)==value for path,value in frozen['source_fingerprints'].items())
        result=dict(status='parent_wall_clock_timeout'if timed_out else'provider_worker_exited',exit_code=exit_code,
            elapsed_seconds=time.monotonic()-began,parent_timeout_seconds=TIMEOUT,hard_kill_on_timeout=timed_out,
            all_inputs_unchanged=unchanged,provider_replay_attempts_max=1,no_automatic_retry=True,
            financial_strategy_replays=0,broker_or_ctp_connections=0,order_calls=0,cancel_calls=0,
            raw_sdk_output_saved=False,credential_values_saved=False,cache_or_overlay_written=False,
            execution_fallback_enabled=False,production_qualified=False,
            preflight_sha256=validation.sha256(OUTPUT/'preflight.json'))
        result['artifact_sha256']={path.name:validation.sha256(path)for path in ATTEMPT.iterdir()if path.is_file()}
        validation.write_json(ATTEMPT/'parent_receipt.json',result)
        print(json.dumps({key:result[key]for key in ['status','exit_code','elapsed_seconds','all_inputs_unchanged']}))
        return 0 if exit_code==0 and unchanged else 1
    finally:
        if process is not None and process.poll()is None:os.killpg(process.pid,signal.SIGKILL);process.wait()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    modes=parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--preflight',action='store_true');modes.add_argument('--run',action='store_true')
    modes.add_argument('--_worker',type=int,help=argparse.SUPPRESS)
    args=parser.parse_args()
    try:
        if args._worker is not None:return worker(args._worker)
        if args.run:return run_once()
        OUTPUT.mkdir(parents=True,exist_ok=True)
        if (OUTPUT/'preflight.json').exists():raise FileExistsError('existing_preflight_refusing_overwrite')
        result=offline_preflight();validation.write_json(OUTPUT/'preflight.json',result)
        print(json.dumps({key:result[key]for key in ['status','provider_replays','sdk_version','expected_minutes','parent_wall_clock_timeout_seconds']}))
        return 0
    except BaseException as error:
        print(json.dumps(safe_error(error)))
        return 1


if __name__=='__main__':raise SystemExit(main())
