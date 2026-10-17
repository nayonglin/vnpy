"""Recover selected missing daily references for an actual B_TS request, once.

Offline preflight is separate from the single bounded provider connection.
Original CSVs/database/base/strategy are never opened for write.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime
from importlib import metadata
import hashlib
import io
import json
import logging
import os
import re
from pathlib import Path
import resource
import signal
import sqlite3
import subprocess
import sys
import time

import numpy as np
import pandas as pd

import stage002_local_minute_overlay as old
import stage007_tqsdk_stream_probe as safety
import stage013_missing_daily_recovery as daily013
import stage037_b_ts_request_provider as request_provider
import stage021_blocking_data_gate as gate
import stage015_daily_recovered_minute_delta as daily_refs

ROOT, LINE, PROJECT = old.ROOT, old.LINE, old.PROJECT
OUTPUT_ROOT = LINE/"outputs/stage051_generic_exact_daily_recovery"
OUTPUT = OUTPUT_ROOT
ATTEMPT = OUTPUT/"network_attempt1"
PROTOCOL = LINE/"stages/20261018_0450_stage051_generic_exact_daily_recovery_protocol.md"
DATABASE, MAPPING = safety.DATABASE, safety.MAPPING
DB_SHA = "273f0bc18de3070e4e085e4d6585fba71d6e1bb1256e3c7fb5adfc6532836a54"
DB_FIELDS = ['open','high','low','close','volume','open_interest']
FROZEN_013 = daily013.OUTPUT/'preflight.json'
FROZEN_013_SHA = 'f5e463b5e1380c8e50aa40ac4bf51a298625e2a913f96429e11d9f0ac867d6c3'
R013 = LINE/'outputs/stage013_independent_review/review_receipt.json'
R013_SHA = '194e48847c9e0927772c482cd5bacc3529a625ac76aeec2a157089924177c795'
REQUEST_DIGEST = None
SOFT_SECONDS, HARD_SECONDS, MEMORY_BYTES = 570, 600, 1_500_000_000
RAW = ["id","datetime",*old.VALUES]
DAILY = ["vt_symbol","tq_symbol","trade_date","datetime",*old.VALUES,
         "source_bar_id","source_datetime_ns","successor_id","successor_datetime_ns","successor_time"]


daily_trade_date = daily013.daily_trade_date
qualify_daily_snapshot = daily013.qualify_daily_snapshot


def atomic_csv(path, frame):
    path = Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary = path.with_suffix(path.suffix+".tmp")
    frame.to_csv(temporary,index=False)
    os.replace(temporary,path)


def select_requirements(request,symbols,calendar):
    if request.get('schema')!=gate.REQUEST_SCHEMA or gate.request_sha256(request)!=request.get('request_sha256'):
        raise ValueError('actual_request_canonical_or_schema_mismatch')
    # The existing reader validates every requirement/order/date/grid even if
    # this recovery only selects a subset of its real contracts.
    request_provider.packet_targets(request,calendar,0)
    available={row['vt_symbol']:row for row in request['requirements']}
    chosen=list(available)if symbols is None else list(symbols)
    if not 1<=len(chosen)<=8 or len(set(chosen))!=len(chosen)or not set(chosen).issubset(available):
        raise ValueError('selected_daily_subset_must_be_1_to_8_real_request_contracts')
    for symbol in chosen:
        if not re.fullmatch(r'[A-Za-z]+[0-9]{3,4}\.(SHFE|DCE|CZCE|GFEX|INE|CFFEX)',symbol):
            raise ValueError('original_real_contract_required_not_continuous')
    return [dict(available[symbol])for symbol in sorted(chosen)]


def require_missing_reference(key,csv_exists,approved,rejected):
    if csv_exists or key in approved or key in rejected:
        raise ValueError('existing_original_or_reviewed_daily_scope_must_not_be_overridden')


def database_targets(selected):
    if old.sha256(DATABASE)!=DB_SHA:raise ValueError('accepted_database_changed')
    wal=Path(str(DATABASE)+'-wal')
    if wal.exists()and wal.stat().st_size:raise ValueError('nonempty_database_wal')
    frames=[]
    with sqlite3.connect(DATABASE.resolve().as_uri()+'?mode=ro&immutable=1',uri=True)as db:
        db.execute('PRAGMA query_only=ON')
        for target in selected:
            symbol=target['vt_symbol'];native,exchange=symbol.rsplit('.',1);day=target['execution_trade_date']
            rows=pd.read_sql_query("SELECT substr(datetime,1,10) AS trade_date,open_price AS open,high_price AS high,"
                "low_price AS low,close_price AS close,volume,open_interest FROM dbbardata "
                "WHERE symbol=? AND exchange=? AND interval='d' AND substr(datetime,1,10)=? ORDER BY datetime",db,
                params=[native,exchange,day])
            values=rows[DB_FIELDS].to_numpy(dtype=float)
            if len(rows)!=1 or not np.isfinite(values).all():raise ValueError('exact_database_six_fields_missing_nonunique_or_invalid')
            row=rows.iloc[0]
            if min(row.open,row.high,row.low,row.close)<=0 or min(row.volume,row.open_interest)<0 or row.low>min(row.open,row.close)or row.high<max(row.open,row.close):
                raise ValueError('exact_database_six_fields_illegal')
            rows.insert(0,'vt_symbol',symbol);rows.insert(2,'requirement_kind',target['requirement_kind']);frames.append(rows)
    return pd.concat(frames,ignore_index=True)


def frozen_inputs(request_path,request_file_sha,symbols=None):
    request,inputs=request_provider.read_request(request_path,request_file_sha)
    audit=json.loads((request_provider.REQUEST_ROOT/'audit.json').read_text())
    if not audit or audit[-1].get('status')!='waiting_for_independent_data'or audit[-1].get('request_sha256')!=request['request_sha256']:
        raise ValueError('actual_request_not_current_engine_wait')
    calendar=pd.DatetimeIndex(pd.to_datetime(pd.read_csv(MAPPING,usecols=['date']).date.unique())).sort_values()
    selected=select_requirements(request,symbols,calendar)
    if old.sha256(R013)!=R013_SHA:raise ValueError('accepted_daily_review_changed')
    review=json.loads(R013.read_text());inputs[str(R013)]=R013_SHA
    frames={}
    for key in ['qualified_daily_path','target_qualification_path']:
        path=Path(review[key]);expected=review['source_fingerprints'][str(path)]
        if old.sha256(path)!=expected:raise ValueError('accepted_daily_reference_table_changed')
        inputs[str(path)]=expected;frames[key]=pd.read_csv(path)
    approved=daily_refs.approved_references(frames['qualified_daily_path'],frames['target_qualification_path'],review)
    rejected={(str(row['vt_symbol']),str(row['trade_date']))for row in review['rejected_targets']}
    for target in selected:
        symbol=target['vt_symbol'];native,exchange=symbol.rsplit('.',1)
        original=PROJECT/'downloaded_futures/tqsdk_daily_2010_2026_04'/exchange/(native+'.csv')
        require_missing_reference((symbol,target['execution_trade_date']),original.is_file(),approved,rejected)
    return request,database_targets(selected),inputs


def preflight(request_path,request_file_sha,symbols=None):
    if metadata.version('tqsdk')!='3.10.2':
        raise ValueError('frozen_sdk_version_changed')
    if any(os.environ.get(key) for key in safety.ENDPOINT_ENV):
        raise ValueError('nondefault_provider_endpoint_environment')
    safety.load_credentials()  # Presence only; never serialize credentials.
    request,targets,request_inputs=frozen_inputs(request_path,request_file_sha,symbols)
    excluded=pd.DataFrame(columns=['vt_symbol','execution_trade_date','reason'])
    if old.sha256(FROZEN_013)!=FROZEN_013_SHA:
        raise ValueError('accepted_daily_sdk_preflight_changed')
    sdk=Path(metadata.distribution('tqsdk').locate_file('tqsdk'))
    sdk_paths=[sdk/name for name in ['api.py','auth.py','tradeable/sim/tqsim.py']]
    verified=json.loads(FROZEN_013.read_text())['source_fingerprints']
    for path in sdk_paths:
        if old.sha256(path)!=verified[str(path)]:raise ValueError('normal_sdk_or_auth_source_changed')
    paths=[Path(__file__),PROTOCOL,Path(old.__file__),Path(safety.__file__),Path(daily013.__file__),
        Path(request_provider.__file__),Path(gate.__file__),DATABASE,MAPPING,FROZEN_013,
        Path(daily_refs.__file__),*sdk_paths]
    hashes={str(path):old.sha256(path) for path in paths};hashes.update(request_inputs)
    result=dict(schema='stage051_exact_request_daily_preflight_v1',status='passed_offline_preflight_no_provider_connection',
        request_path=str(Path(request_path).resolve()),request_sha256=request['request_sha256'],request_file_sha256=request_file_sha,
        selected_symbols=targets.vt_symbol.tolist(),
        contracts=targets.vt_symbol.nunique(),source_missing_csv_demands=len(targets),target_real_days=len(targets),
        target_full_session_days=int(targets.requirement_kind.eq('full_session').sum()),
        target_anchor_days=int(targets.requirement_kind.eq('anchor').sum()),excluded_no_real_days=0,duration_seconds=86400,data_length=10000,
        target_manifest_sha256=hashlib.sha256(targets.to_csv(index=False).encode()).hexdigest(),
        excluded_constraints_sha256=hashlib.sha256(excluded.to_csv(index=False).encode()).hexdigest(),
        source_fingerprints=hashes,sdk_version=metadata.version('tqsdk'),
        provider_connections=0,TqBacktest_instances=0,financial_replays=0,orders=0,cancels=0,
        planned_TqApi_max=1,planned_TqSim_max=1,soft_seconds=SOFT_SECONDS,hard_seconds=HARD_SECONDS,
        memory_budget_bytes=MEMORY_BYTES,memory_guard='worker peak RSS around wait/subscription; parent hard wall-clock kill',
        credentials_fields_present=True,credential_values_saved=False,normal_grants_unmodified=True,
        sdk_raw_output_policy='DEVNULL_stdout_stderr_logging',automatic_retry=False,
        database_contract='OHLCV plus DB.open_interest equals provider.open_oi; DB.closeOI=N/A',
        completion_contract='strictly greater same-symbol source id and later valid daily timestamp',
        independent_review_signed=False,response_written=False,old_CSV_or_DB_write=False,production_qualified=False)
    return result,targets,excluded


def peak_memory():
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if sys.platform=="darwin" else value*1024)


def budget_guard(began):
    if peak_memory()>MEMORY_BYTES:
        raise MemoryError("memory_budget_reached")
    if time.monotonic()-began>=SOFT_SECONDS:
        raise TimeoutError("soft_time_budget_reached")


def bind_preflight(preflight_path):
    global OUTPUT,ATTEMPT,REQUEST_DIGEST
    path=Path(preflight_path).resolve();frozen=json.loads(path.read_text());digest=frozen['request_sha256']
    if(path.name!='preflight.json'or path.parent!=OUTPUT_ROOT.resolve()/('request_'+digest)or
        frozen.get('schema')!='stage051_exact_request_daily_preflight_v1'):
        raise ValueError('preflight_scope_or_schema_mismatch')
    OUTPUT=path.parent;ATTEMPT=OUTPUT/'network_attempt1';REQUEST_DIGEST=digest
    return frozen


def worker(parent_pid,preflight_path):
    bind_preflight(preflight_path)
    if os.getppid()!=parent_pid or not(ATTEMPT/"attempt_started.json").is_file():
        return 2
    frozen = json.loads((OUTPUT/"preflight.json").read_text())
    if any(old.sha256(path)!=digest for path,digest in frozen["source_fingerprints"].items()):return 2
    if old.sha256(OUTPUT/"target_manifest.csv")!=frozen["target_manifest_sha256"]:
        return 2
    targets = pd.read_csv(OUTPUT/"target_manifest.csv")
    api=None;sim_created=False;provider_started=False;status="initializing"
    began=time.monotonic();receipts=[];qualified_frames=[];audit_frames=[]
    def save_progress():
        qualified = pd.concat(qualified_frames,ignore_index=True) if qualified_frames else pd.DataFrame(columns=DAILY)
        audits = pd.concat(audit_frames,ignore_index=True) if audit_frames else pd.DataFrame(columns=["vt_symbol","trade_date","accepted","reason"])
        atomic_csv(ATTEMPT/"qualified_daily.csv",qualified)
        atomic_csv(ATTEMPT/"target_qualification.csv",audits)
        old.write_json(ATTEMPT/"symbol_receipts.json",receipts)
        old.write_json(ATTEMPT/"progress.json",dict(completed_symbols=len(receipts),qualified_target_days=len(qualified),
            checked_target_days=len(audits),peak_memory_bytes=peak_memory(),elapsed_seconds=time.monotonic()-began))
    with open(os.devnull,"w") as discard,redirect_stdout(discard),redirect_stderr(discard):
        logging.disable(logging.CRITICAL)
        try:
            from tqsdk import TqApi,TqAuth,TqSim
            username,password=safety.load_credentials()
            budget_guard(began)
            sim=TqSim();sim_created=True;provider_started=True
            api=TqApi(account=sim,auth=TqAuth(username,password),debug=False,web_gui=False)
            username=password=None
            for symbol,group in targets.groupby("vt_symbol",sort=True):
                budget_guard(began)
                native,exchange=symbol.rsplit(".",1)
                holder={}
                async def subscribe():
                    holder["serial"]=api.get_kline_serial(f"{exchange}.{native}",86400,data_length=10000)
                api.create_task(subscribe())
                symbol_began=time.monotonic()
                while "serial" not in holder or not api.is_serial_ready(holder["serial"]):
                    budget_guard(began)
                    if time.monotonic()-symbol_began>85:
                        raise TimeoutError("symbol_initialization_timeout")
                    remaining=SOFT_SECONDS-(time.monotonic()-began)
                    api.wait_update(deadline=time.time()+max(.01,min(10.,remaining)))
                budget_guard(began)
                snapshot=holder["serial"].reindex(columns=RAW).copy()
                raw_path=ATTEMPT/"raw"/exchange/f"{native}.csv"
                atomic_csv(raw_path,snapshot)
                qualified,audit=qualify_daily_snapshot(symbol,snapshot,group)
                qualified_frames.append(qualified);audit_frames.append(audit)
                receipts.append(dict(vt_symbol=symbol,tq_symbol=f"{exchange}.{native}",
                    raw_path=str(raw_path),raw_sha256=old.sha256(raw_path),raw_rows=len(snapshot),
                    target_days=len(group),accepted_days=len(qualified),rejected_days=len(audit)-len(qualified),
                    database_closeOI="N/A_not_independently_available"))
                save_progress()
            status="all_exact_snapshots_collected"
        except BaseException as error:
            status="provider_or_local_failed"
            safe=safety.safe_error(error)
            if isinstance(error,MemoryError):safe["category"]="memory_budget_reached"
            old.write_json(ATTEMPT/"safe_error.json",safe)
        finally:
            save_progress()
            if api is not None:
                try:api.close()
                except BaseException as error:
                    status="close_failed";old.write_json(ATTEMPT/"safe_error.json",safety.safe_error(error))
    qualified_count=sum(len(x)for x in qualified_frames)
    if status=="all_exact_snapshots_collected":
        status="completed_all_targets_qualified" if qualified_count==len(targets) else "completed_with_target_rejections"
    result=dict(status=status,provider_connections_attempted=int(provider_started),TqApi_max=1,
        TqSim_created=sim_created,TqBacktest_instances=0,collected_contracts=len(receipts),target_contracts=targets.vt_symbol.nunique(),
        accepted_target_days=qualified_count,target_days=len(targets),elapsed_seconds=time.monotonic()-began,
        peak_memory_bytes=peak_memory(),automatic_retry=False,financial_replays=0,orders=0,cancels=0,
        broker_or_ctp_connections=0,model_fits=0,source_writes=0,raw_sdk_output_saved=False,
        credential_values_saved=False,old_CSV_or_DB_written=False,production_qualified=False,
        request_sha256=REQUEST_DIGEST,independent_review_signed=False,response_written=False,
        financial_metrics="N/A",database_closeOI="N/A_not_independently_available")
    old.write_json(ATTEMPT/"worker_receipt.json",result)
    return 0 if status=="completed_all_targets_qualified" else 1


def run_once(preflight_path,source_sha):
    if not source_sha or old.sha256(__file__)!=source_sha:raise ValueError('explicit_reviewed_source_SHA_required')
    bind_preflight(preflight_path)
    if ATTEMPT.exists():raise FileExistsError("existing_provider_attempt_refusing_retry")
    frozen=json.loads((OUTPUT/"preflight.json").read_text())
    current,_,_=preflight(frozen['request_path'],frozen['request_file_sha256'],frozen['selected_symbols'])
    if current!=frozen:raise ValueError("preflight_changed_since_review")
    for name,key in [("target_manifest.csv","target_manifest_sha256"),("excluded_constraints.csv","excluded_constraints_sha256")]:
        if old.sha256(OUTPUT/name)!=frozen[key]:raise ValueError("frozen_targets_changed")
    ATTEMPT.mkdir(parents=True,exist_ok=False)
    old.write_json(ATTEMPT/"attempt_started.json",dict(started_at=datetime.now().astimezone().isoformat(),
        provider_connections_max=1,soft_seconds=SOFT_SECONDS,hard_seconds=HARD_SECONDS,memory_budget_bytes=MEMORY_BYTES,
        TqBacktest_instances=0,financial_replays=0,automatic_retry=False))
    began=time.monotonic();process=None;killed=False
    try:
        process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),"--_worker",str(os.getpid()),"--preflight",str(Path(preflight_path).resolve())],
            cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
        try:code=process.wait(timeout=max(.01,HARD_SECONDS-(time.monotonic()-began)))
        except subprocess.TimeoutExpired:
            killed=True;os.killpg(process.pid,signal.SIGKILL);process.wait();code=-9
        unchanged=all(old.sha256(path)==digest for path,digest in frozen["source_fingerprints"].items())
        receipt=dict(status="hard_timeout" if killed else "worker_terminal",exit_code=code,
            elapsed_seconds=time.monotonic()-began,hard_kill=killed,all_inputs_unchanged=unchanged,
            provider_connections_max=1,TqBacktest_instances=0,automatic_retry=False,financial_replays=0,
            orders=0,cancels=0,broker_or_ctp_connections=0,raw_sdk_output_saved=False,
            credential_values_saved=False,old_CSV_or_DB_written=False,production_qualified=False,
            preflight_sha256=old.sha256(OUTPUT/"preflight.json"),
            request_sha256=REQUEST_DIGEST,independent_review_signed=False,response_written=False)
        receipt["artifact_sha256"]={str(p.relative_to(ATTEMPT)):old.sha256(p)for p in ATTEMPT.rglob("*")if p.is_file()}
        old.write_json(ATTEMPT/"parent_receipt.json",receipt)
        print(json.dumps({k:receipt[k]for k in ["status","exit_code","elapsed_seconds","all_inputs_unchanged"]}))
        return 0 if code==0 and unchanged else 1
    finally:
        if process is not None and process.poll() is None:
            os.killpg(process.pid,signal.SIGKILL);process.wait()


def main():
    parser=argparse.ArgumentParser(description=__doc__);modes=parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--prepare',action='store_true');modes.add_argument('--run',action='store_true')
    modes.add_argument('--_worker',type=int,help=argparse.SUPPRESS)
    parser.add_argument('--request');parser.add_argument('--request-file-sha256');parser.add_argument('--symbols',nargs='+')
    parser.add_argument('--preflight',type=Path);parser.add_argument('--source-sha256');args=parser.parse_args()
    try:
        if args._worker is not None:return worker(args._worker,args.preflight)
        if args.run:return run_once(args.preflight,args.source_sha256)
        if not args.request or not args.request_file_sha256:raise ValueError('actual_request_path_and_file_SHA_required')
        result,targets,excluded=preflight(args.request,args.request_file_sha256,args.symbols)
        folder=OUTPUT_ROOT/('request_'+result['request_sha256'])
        if folder.exists():raise FileExistsError('existing_request_preparation_refusing_overwrite')
        folder.mkdir(parents=True,exist_ok=False);atomic_csv(folder/'target_manifest.csv',targets)
        atomic_csv(folder/'excluded_constraints.csv',excluded);old.write_json(folder/'preflight.json',result)
        print(json.dumps(dict(status=result['status'],preflight_path=str((folder/'preflight.json').resolve()),
            preflight_sha256=old.sha256(folder/'preflight.json'),request_sha256=result['request_sha256'],
            contracts=result['contracts'],target_real_days=result['target_real_days'],provider_connections=0)))
        return 0
    except BaseException as error:
        if isinstance(error,SystemExit):raise
        print(json.dumps(safety.safe_error(error)));return 1


if __name__=='__main__':raise SystemExit(main())
