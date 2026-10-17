"""One normally authorized, bounded multi-contract data replay; no orders."""
from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from importlib import metadata
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import time

import numpy as np
import pandas as pd

import stage002_local_minute_overlay as validation
import stage007_tqsdk_stream_probe as probe

ROOT=probe.ROOT
LINE=probe.LINE
OUTPUT=LINE/'outputs/stage012_provider_batch'
PROTOCOL=LINE/'stages/20261018_0009_stage012_bounded_provider_batch_protocol.md'
ATTEMPT=OUTPUT/'network_attempt1'
FIELDS=['vt_symbol','bar_datetime',*validation.VALUES]
SOFT_SECONDS=570
HARD_SECONDS=600


def ns_value(value):
    stamp=pd.Timestamp(value)
    stamp=stamp.tz_localize('Asia/Shanghai') if stamp.tz is None else stamp.tz_convert('Asia/Shanghai')
    return stamp.tz_convert('UTC').value


def local_iso(value):
    return pd.Timestamp(value,tz='UTC').tz_convert('Asia/Shanghai').tz_localize(None).isoformat()


def prepare():
    """Choose data density only. Never read outcomes or connect a provider."""
    remaining=LINE/'outputs/stage011_needed_local_completed/remaining_demand.csv'
    summary=remaining.with_name('summary.json')
    session_audit=remaining.with_name('session_manifest.csv')
    if OUTPUT.exists():raise FileExistsError('existing_batch_refuse_reselection')
    frame=pd.read_csv(remaining)
    frame=frame.loc[frame.real_daily_present.eq(True)].copy()
    audit=pd.read_csv(session_audit,usecols=['vt_symbol','execution_trade_date','reason','daily_source_status'])
    audit=audit.loc[audit.reason.eq('incomplete_session')&audit.daily_source_status.eq('accepted_source_bytes')]
    frame=frame.merge(audit[['vt_symbol','execution_trade_date']],on=['vt_symbol','execution_trade_date'],validate='one_to_one')
    calendar=pd.DatetimeIndex(pd.to_datetime(pd.read_csv(validation.MAPPING,usecols=['date']).date).drop_duplicates().sort_values())
    old_manifest=validation.OLD/'input_manifest.json'
    old_hashes=json.loads(old_manifest.read_text())
    eligible=[];daily_cache={};source_hashes={str(p):validation.sha256(p)for p in [remaining,summary,session_audit,validation.MAPPING,old_manifest]}
    skipped=dict(missing_csv=0,missing_or_invalid_daily_row=0)
    for row in frame.itertuples():
        native,exchange=row.vt_symbol.rsplit('.',1)
        daily_path=validation.PROJECT/'downloaded_futures/tqsdk_daily_2010_2026_04'/exchange/(native+'.csv')
        if not daily_path.is_file():skipped['missing_csv']+=1;continue
        if row.vt_symbol not in daily_cache:
            digest=validation.sha256(daily_path)
            if old_hashes.get(str(daily_path.relative_to(ROOT)))!=digest:raise ValueError('original_daily_csv_binding_changed')
            daily=pd.read_csv(daily_path)
            daily['trade_date']=pd.to_datetime(daily.trade_date).dt.normalize()
            daily_cache[row.vt_symbol]=daily
        daily=daily_cache[row.vt_symbol]
        hit=daily.loc[daily.trade_date.eq(pd.Timestamp(row.execution_trade_date))]
        if len(hit)!=1 or any(k not in hit or not np.isfinite(float(hit.iloc[0][k]))for k in validation.VALUES):
            skipped['missing_or_invalid_daily_row']+=1;continue
        eligible.append((row.vt_symbol,row.execution_trade_date,row.requirement_kind,str(daily_path)))
    if not eligible:raise ValueError('no_eligible_remaining_sessions')
    table=pd.DataFrame(eligible,columns=['vt_symbol','execution_trade_date','original_requirement_kind','daily_csv_path']).sort_values(['execution_trade_date','vt_symbol'])
    dates=pd.DatetimeIndex(sorted(pd.to_datetime(table.execution_trade_date).unique()))
    event_dates=pd.to_datetime(table.execution_trade_date)
    first=dates[0]
    for day in dates:
        count=((event_dates>=day)&(event_dates<day+pd.Timedelta(days=10))).sum()
        if count>=5:first=day;break
    chosen=table.loc[pd.to_datetime(table.execution_trade_date).between(first,first+pd.Timedelta(days=9))]
    symbols=sorted(chosen.vt_symbol.unique())[:8]
    chosen=chosen.loc[chosen.vt_symbol.isin(symbols)]
    targets=[];total=0
    for row in chosen.itertuples():
        grid=validation.session_grid(row.vt_symbol,row.execution_trade_date,calendar)
        if total+len(grid)>20000:break
        total+=len(grid)
        source_hashes[row.daily_csv_path]=validation.sha256(Path(row.daily_csv_path))
        targets.append(dict(vt_symbol=row.vt_symbol,execution_trade_date=row.execution_trade_date,
            original_requirement_kind=row.original_requirement_kind,daily_csv_path=row.daily_csv_path,
            session_start=grid[0].isoformat(),session_end_exclusive=(grid[-1]+pd.Timedelta(minutes=1)).isoformat(),
            expected_minutes=len(grid),expected_timestamps=[t.isoformat()for t in grid]))
    if not targets:raise ValueError('empty_bounded_selection')
    last=max(pd.Timestamp(t['execution_trade_date'])for t in targets)
    later=calendar[calendar>last]
    if len(later)==0:raise ValueError('no_later_observation_day')
    start=later[0]+pd.Timedelta(hours=9,minutes=1)
    manifest=dict(status='frozen_before_connection',selection='earliest_10_calendar_days_with_at_least5_eligible_gaps_first8_contracts_cap20000_minutes',
        eligible_remaining_sessions=len(table),selection_skipped=skipped,targets=targets,target_minutes=total,
        contracts=sorted({t['vt_symbol']for t in targets}),provider_start=start.isoformat(),
        provider_end=(start+pd.Timedelta(minutes=4)).isoformat(),serial_data_length=10000,
        retrieval_mode='public_serial_initial_warmup_history_then_successor_only',input_sha256=source_hashes,
        protocol_sha256=validation.sha256(PROTOCOL),financial_replays=0,orders=0)
    OUTPUT.mkdir(exist_ok=False)
    validation.write_json(OUTPUT/'batch_manifest.json',manifest)
    print(json.dumps({k:manifest[k]for k in ['status','contracts','target_minutes','provider_start','provider_end']}))


class BatchCollector:
    def __init__(self,expected):
        self.expected={symbol:{ns_value(t) for t in times}for symbol,times in expected.items()}
        self.records={}
        self.successors={}
        self.target_count=sum(map(len,self.expected.values()))
        if len(self.expected)>8 or self.target_count>20000:raise ValueError('batch_resource_limit')

    def observe(self,symbol,serial,*,initial=True):
        if len(serial)<2:return
        start=0 if initial else max(0,len(serial)-3)
        stamps=serial.datetime.to_numpy()
        positions=[p for p in range(start,len(serial)-1)if np.isfinite(stamps[p])and int(stamps[p])in self.expected[symbol]]
        for position in positions:
            row=serial.iloc[position]
            successor=serial.iloc[position+1]['datetime']
            if not np.isfinite(row['datetime']) or row['datetime']<=0 or not np.isfinite(successor):continue
            stamp,next_stamp=int(row['datetime']),int(successor)
            if stamp not in self.expected[symbol]:continue
            if next_stamp<stamp+60_000_000_000:raise ValueError('nonforward_successor')
            values=tuple(float(row[key])for key in validation.VALUES)
            key=(symbol,stamp)
            if key in self.records and self.records[key]!=values:raise ValueError('conflicting_completed_bar')
            if key not in self.records:
                self.records[key]=values
                self.successors[key]=next_stamp

    def frames(self):
        keys=sorted(self.records)
        raw=pd.DataFrame([[s,local_iso(t),*self.records[(s,t)]]for s,t in keys],columns=FIELDS)
        evidence=pd.DataFrame([[s,local_iso(t),local_iso(self.successors[(s,t)]),'observed_later_serial_kline',True]for s,t in keys],
            columns=['vt_symbol','bar_datetime','successor_time','method','completed'])
        return raw,evidence

    def save(self):
        raw,evidence=self.frames()
        for name,frame in [('raw_completed_minutes.csv',raw),('completion_evidence.csv',evidence)]:
            temporary=ATTEMPT/(name+'.tmp')
            frame.to_csv(temporary,index=False)
            os.replace(temporary,ATTEMPT/name)
        validation.write_json(ATTEMPT/'progress.json',dict(completed_minutes=len(raw),target_minutes=self.target_count,
            updated_at=datetime.now().astimezone().isoformat(),network_attempts=1,financial_replays=0))


def read_manifest():
    manifest=json.loads((OUTPUT/'batch_manifest.json').read_text())
    targets=manifest['targets']
    expected={}
    for item in targets:
        # Explicit grids retain exchange breaks and pandemic night suspensions.
        grid=pd.DatetimeIndex(item['expected_timestamps'])
        if len(grid)!=item['expected_minutes'] or grid.has_duplicates:raise ValueError('manifest_grid_invalid')
        expected.setdefault(item['vt_symbol'],[]).extend(grid)
    if any(len(v)!=len(set(v))for v in expected.values()):raise ValueError('duplicate_target_key')
    BatchCollector(expected)
    return manifest,expected


def preflight():
    manifest,expected=read_manifest()
    if metadata.version('tqsdk')!='3.10.2':raise ValueError('frozen_sdk_version_changed')
    if any(os.environ.get(key)for key in probe.ENDPOINT_ENV):raise ValueError('provider_endpoint_override')
    probe.load_credentials()
    old=json.loads((probe.OUTPUT/'preflight.json').read_text())['source_fingerprints']
    sdk=Path(metadata.distribution('tqsdk').locate_file('tqsdk'))
    paths=[Path(__file__),PROTOCOL,OUTPUT/'batch_manifest.json',Path(validation.__file__),Path(probe.__file__)]
    for name in ['api.py','auth.py','tradeable/sim/tqsim.py','backtest/backtest.py','tools/downloader.py']:
        p=sdk/name
        if validation.sha256(p)!=old[str(p)]:raise ValueError('previously_verified_sdk_source_changed')
        paths.append(p)
    for p,h in manifest['input_sha256'].items():
        path=Path(p)
        if validation.sha256(path)!=h:raise ValueError('batch_input_changed')
        paths.append(path)
    if validation.sha256(PROTOCOL)!=manifest['protocol_sha256']:raise ValueError('protocol_drift')
    return dict(status='passed_offline_preflight',normal_authorization_required=True,credentials_present=True,
        credential_values_saved=False,auth_checks_unmodified=True,contracts=len(expected),
        target_sessions=len(manifest['targets']),target_minutes=sum(map(len,expected.values())),
        provider_start=manifest['provider_start'],provider_end=manifest['provider_end'],
        soft_seconds=SOFT_SECONDS,hard_seconds=HARD_SECONDS,provider_attempts_max=1,
        source_fingerprints={str(p):validation.sha256(p)for p in paths},financial_replays=0,orders=0)


def qualify_saved(manifest):
    raw=pd.read_csv(ATTEMPT/'raw_completed_minutes.csv')
    evidence=pd.read_csv(ATTEMPT/'completion_evidence.csv')
    if len(raw):raw=validation.normal_times(raw)
    empty=pd.DataFrame(columns=FIELDS)
    evidence_keys={(row.vt_symbol,pd.Timestamp(row.bar_datetime))for row in evidence.itertuples()if bool(row.completed) and pd.Timestamp(row.successor_time)>=pd.Timestamp(row.bar_datetime)+pd.Timedelta(minutes=1)}
    rows=[]
    for item in manifest['targets']:
        grid=pd.DatetimeIndex(item['expected_timestamps'])
        selected=raw.loc[raw.vt_symbol.eq(item['vt_symbol'])] if len(raw)else empty
        daily=pd.read_csv(item['daily_csv_path'])
        day=daily.loc[pd.to_datetime(daily.trade_date).dt.normalize().eq(pd.Timestamp(item['execution_trade_date']))]
        reference=day.iloc[0].to_dict()if len(day)==1 else None
        _,check=validation.validate_session(selected,grid,reference,empty)
        proof=all((item['vt_symbol'],stamp)in evidence_keys for stamp in grid)
        rows.append(dict(vt_symbol=item['vt_symbol'],execution_trade_date=item['execution_trade_date'],
            accepted=bool(check['status']=='accepted'and proof),completion_evidence_complete=proof,
            **check))
    validation.write_json(ATTEMPT/'quality.json',dict(sessions=rows,accepted_sessions=sum(x['accepted']for x in rows),
        target_sessions=len(rows),all_sessions_accepted=all(x['accepted']for x in rows),raw_rows=len(raw),
        database_closeOI='N/A_not_used',financial_replays=0,cache_or_overlay_written=False))
    return sum(x['accepted']for x in rows)


def worker(parent_pid):
    if os.getppid()!=parent_pid or not(ATTEMPT/'attempt_started.json').is_file():return 2
    manifest,expected=read_manifest()
    collector=BatchCollector(expected)
    api=None;sim_created=False;provider_started=False;status='initializing';finished_types=()
    began=time.monotonic()
    with open(os.devnull,'w')as discard,redirect_stdout(discard),redirect_stderr(discard):
        logging.disable(logging.CRITICAL)
        try:
            from tqsdk import TqApi,TqAuth,TqBacktest,TqSim,BacktestFinished
            finished_types=(BacktestFinished,)
            username,password=probe.load_credentials()
            sim=TqSim();sim_created=True;provider_started=True
            api=TqApi(account=sim,auth=TqAuth(username,password),
                backtest=TqBacktest(start_dt=datetime.fromisoformat(manifest['provider_start']),end_dt=datetime.fromisoformat(manifest['provider_end'])),
                debug=False,web_gui=False)
            username=password=None
            serials={}
            async def subscribe_all():
                for symbol in sorted(expected):
                    native,exchange=symbol.rsplit('.',1)
                    serials[symbol]=api.get_kline_serial(exchange+'.'+native,60,data_length=10000)
            api.create_task(subscribe_all())
            last_saved=time.monotonic();last_stamp={};iterations=0
            while len(collector.records)<collector.target_count:
                if time.monotonic()-began>=SOFT_SECONDS:
                    status='soft_time_budget_reached';break
                if not api.wait_update(deadline=time.time()+30):raise TimeoutError('provider_wait_timeout')
                iterations+=1
                for symbol,serial in serials.items():
                    if not api.is_serial_ready(serial):continue
                    stamp=serial.iloc[-1]['datetime']
                    if last_stamp.get(symbol)==stamp:continue
                    initial=symbol not in last_stamp
                    last_stamp[symbol]=stamp
                    collector.observe(symbol,serial,initial=initial)
                if time.monotonic()-last_saved>=15:
                    collector.save();last_saved=time.monotonic()
            else:status='all_target_minutes_completed'
        except finished_types:
            status='provider_finished'
        except BaseException as error:
            status='provider_or_local_failed'
            validation.write_json(ATTEMPT/'safe_error.json',probe.safe_error(error))
        finally:
            collector.save()
            if api is not None:
                try:api.close()
                except BaseException as error:
                    status='close_failed';validation.write_json(ATTEMPT/'safe_error.json',probe.safe_error(error))
    accepted=qualify_saved(manifest)
    validation.write_json(ATTEMPT/'worker_receipt.json',dict(status=status,provider_attempts=int(provider_started),
        local_TqSim_created=sim_created,completed_target_minutes=len(collector.records),target_minutes=collector.target_count,
        accepted_sessions=accepted,target_sessions=len(manifest['targets']),elapsed_seconds=time.monotonic()-began,
        financial_replays=0,orders=0,cancels=0,broker_or_ctp_connections=0,model_fits=0,
        raw_sdk_output_saved=False,credential_values_saved=False,cache_or_overlay_written=False,production_qualified=False))
    return 0 if accepted==len(manifest['targets'])else 1


def run_once():
    if ATTEMPT.exists():raise FileExistsError('existing_attempt_refuse_retry')
    frozen=json.loads((OUTPUT/'preflight.json').read_text())
    if preflight()!=frozen:raise ValueError('preflight_drift')
    ATTEMPT.mkdir(exist_ok=False)
    validation.write_json(ATTEMPT/'attempt_started.json',dict(started_at=datetime.now().astimezone().isoformat(),
        provider_attempts_max=1,financial_replays=0,orders=0,automatic_retry=False))
    started=time.monotonic();killed=False
    with open(os.devnull,'w')as discard:
        process=subprocess.Popen([sys.executable,str(Path(__file__)),'--worker',str(os.getpid())],stdout=discard,stderr=discard)
        try:exit_code=process.wait(timeout=HARD_SECONDS)
        except subprocess.TimeoutExpired:
            killed=True;process.kill();exit_code=process.wait()
    changed=[p for p,h in frozen['source_fingerprints'].items()if validation.sha256(Path(p))!=h]
    validation.write_json(ATTEMPT/'parent_receipt.json',dict(status='worker_terminal',exit_code=exit_code,
        elapsed_seconds=time.monotonic()-started,hard_kill=killed,all_inputs_unchanged=not changed,
        automatic_retry=False,provider_attempts_max=1,financial_replays=0,orders=0,
        raw_sdk_output_saved=False,credential_values_saved=False,cache_or_overlay_written=False,production_qualified=False))
    print(json.dumps({'exit_code':exit_code,'hard_kill':killed,'all_inputs_unchanged':not changed}))
    return exit_code


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--prepare',action='store_true')
    parser.add_argument('--preflight',action='store_true')
    parser.add_argument('--run',action='store_true')
    parser.add_argument('--worker',type=int)
    args=parser.parse_args()
    if args.worker is not None:raise SystemExit(worker(args.worker))
    if args.prepare:prepare()
    elif args.preflight:
        if (OUTPUT/'preflight.json').exists():raise FileExistsError('preflight_already_exists')
        result=preflight();validation.write_json(OUTPUT/'preflight.json',result)
        print(json.dumps({k:result[k]for k in ['status','contracts','target_sessions','target_minutes','provider_start','provider_end']}))
    elif args.run:raise SystemExit(run_once())
    else:parser.error('choose --prepare, --preflight or --run')
