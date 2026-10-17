"""Recover the one actual B_TS missing daily reference through normal public TqApi.

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

ROOT, LINE, PROJECT = old.ROOT, old.LINE, old.PROJECT
OUTPUT = LINE/"outputs/stage040_exact_request_daily_recovery"
ATTEMPT = OUTPUT/"network_attempt1"
PROTOCOL = LINE/"stages/20261018_0400_stage040_exact_actual_daily_recovery_protocol.md"
DATABASE, MAPPING = safety.DATABASE, safety.MAPPING
DB_SHA = "273f0bc18de3070e4e085e4d6585fba71d6e1bb1256e3c7fb5adfc6532836a54"
REQUEST_DIGEST = "53e251e1034a04c76c81f26838eec78388484bf2c14742953fb9efecfce040ae"
REQUEST = request_provider.REQUEST_ROOT/('request_'+REQUEST_DIGEST)/'request.json'
REQUEST_FILE_SHA = "f7ba04a28e5b0f99d695c567415c681c91cbd62672bd0469f4034e832302f420"
DB_FIELDS = ['open','high','low','close','volume','open_interest']
DB_EXPECTED = [6378.,6380.,6262.,6280.,76307.,68372.]
FROZEN_013 = daily013.OUTPUT/'preflight.json'
FROZEN_013_SHA = 'f5e463b5e1380c8e50aa40ac4bf51a298625e2a913f96429e11d9f0ac867d6c3'
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


def exact_target(request):
    if request.get('schema')!=gate.REQUEST_SCHEMA or gate.request_sha256(request)!=REQUEST_DIGEST or request.get('request_sha256')!=REQUEST_DIGEST:
        raise ValueError('exact_actual_request_identity_changed')
    if request.get('execution_trade_date')!='2020-01-06' or len(request.get('requirements',[]))!=1 or len(request.get('active_orders',[]))!=1:
        raise ValueError('exact_single_request_scope_changed')
    item=request['requirements'][0];order=request['active_orders'][0]
    if any(obj.get('vt_symbol')!='SM005.CZCE' or obj.get('requirement_kind')!='full_session' for obj in [item,order]):
        raise ValueError('real_contract_or_full_session_identity_changed')
    if item.get('execution_trade_date')!='2020-01-06' or len(item.get('required_timestamps',[]))!=225:
        raise ValueError('exact_225_minute_scope_changed')
    if item.get('existing_source_timestamps')!=[] or item.get('missing_or_unqualified_timestamps')!=item['required_timestamps']:
        raise ValueError('exact_missing_scope_changed')
    return item


def frozen_inputs():
    request,_=request_provider.read_request(REQUEST,REQUEST_FILE_SHA)
    item=exact_target(request)
    if old.sha256(DATABASE)!=DB_SHA:
        raise ValueError('accepted_database_changed')
    calendar=pd.DatetimeIndex(pd.to_datetime(pd.read_csv(MAPPING,usecols=['date']).date.unique())).sort_values()
    if item['required_timestamps']!=[stamp.isoformat() for stamp in old.session_grid('SM005.CZCE','2020-01-06',calendar)]:
        raise ValueError('exact_request_canonical_grid_changed')
    wal=Path(str(DATABASE)+'-wal')
    if wal.exists() and wal.stat().st_size:
        raise ValueError('nonempty_database_wal')
    with sqlite3.connect(DATABASE.resolve().as_uri()+'?mode=ro&immutable=1',uri=True) as db:
        db.execute('PRAGMA query_only=ON')
        rows=pd.read_sql_query("SELECT substr(datetime,1,10) AS trade_date,open_price AS open,high_price AS high,"
            "low_price AS low,close_price AS close,volume,open_interest FROM dbbardata "
            "WHERE symbol=? AND exchange=? AND interval='d' AND substr(datetime,1,10)=?",db,
            params=['SM005','CZCE','2020-01-06'])
    if len(rows)!=1 or not np.array_equal(rows[DB_FIELDS].to_numpy(dtype=float)[0],np.asarray(DB_EXPECTED)):
        raise ValueError('exact_database_six_fields_changed')
    rows.insert(0,'vt_symbol','SM005.CZCE');rows.insert(2,'requirement_kind','full_session')
    return rows,pd.DataFrame(columns=['vt_symbol','execution_trade_date','reason'])


def preflight():
    if metadata.version('tqsdk')!='3.10.2':
        raise ValueError('frozen_sdk_version_changed')
    if any(os.environ.get(key) for key in safety.ENDPOINT_ENV):
        raise ValueError('nondefault_provider_endpoint_environment')
    safety.load_credentials()  # Presence only; never serialize credentials.
    targets,excluded=frozen_inputs()
    if old.sha256(FROZEN_013)!=FROZEN_013_SHA:
        raise ValueError('accepted_daily_sdk_preflight_changed')
    sdk=Path(metadata.distribution('tqsdk').locate_file('tqsdk'))
    sdk_paths=[sdk/name for name in ['api.py','auth.py','tradeable/sim/tqsim.py']]
    verified=json.loads(FROZEN_013.read_text())['source_fingerprints']
    for path in sdk_paths:
        if old.sha256(path)!=verified[str(path)]:raise ValueError('normal_sdk_or_auth_source_changed')
    paths=[Path(__file__),PROTOCOL,Path(old.__file__),Path(safety.__file__),Path(daily013.__file__),
        Path(request_provider.__file__),Path(gate.__file__),DATABASE,MAPPING,FROZEN_013,
        REQUEST,REQUEST.parent/'request_fingerprint.json',*sdk_paths]
    hashes={str(path):old.sha256(path) for path in paths}
    result=dict(schema='stage040_exact_request_daily_preflight_v1',status='passed_offline_preflight_no_provider_connection',
        request_path=str(REQUEST),request_sha256=REQUEST_DIGEST,request_file_sha256=REQUEST_FILE_SHA,
        contracts=1,source_missing_csv_demands=1,target_real_days=1,target_full_session_days=1,
        target_anchor_days=0,excluded_no_real_days=0,duration_seconds=86400,data_length=10000,
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


def worker(parent_pid):
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


def run_once():
    if ATTEMPT.exists():raise FileExistsError("existing_provider_attempt_refusing_retry")
    frozen=json.loads((OUTPUT/"preflight.json").read_text())
    current,_,_=preflight()
    if current!=frozen:raise ValueError("preflight_changed_since_review")
    for name,key in [("target_manifest.csv","target_manifest_sha256"),("excluded_constraints.csv","excluded_constraints_sha256")]:
        if old.sha256(OUTPUT/name)!=frozen[key]:raise ValueError("frozen_targets_changed")
    ATTEMPT.mkdir(parents=True,exist_ok=False)
    old.write_json(ATTEMPT/"attempt_started.json",dict(started_at=datetime.now().astimezone().isoformat(),
        provider_connections_max=1,soft_seconds=SOFT_SECONDS,hard_seconds=HARD_SECONDS,memory_budget_bytes=MEMORY_BYTES,
        TqBacktest_instances=0,financial_replays=0,automatic_retry=False))
    began=time.monotonic();process=None;killed=False
    try:
        process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),"--_worker",str(os.getpid())],
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
    parser=argparse.ArgumentParser(description=__doc__)
    modes=parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--prepare", "--preflight",dest="prepare",action="store_true")
    modes.add_argument("--run",action="store_true")
    modes.add_argument("--_worker",type=int,help=argparse.SUPPRESS)
    args=parser.parse_args()
    try:
        if args._worker is not None:return worker(args._worker)
        if args.run:return run_once()
        if (OUTPUT/"preflight.json").exists():raise FileExistsError("existing_preflight_refusing_overwrite")
        result,targets,excluded=preflight()
        OUTPUT.mkdir(parents=True,exist_ok=True)
        atomic_csv(OUTPUT/"target_manifest.csv",targets)
        atomic_csv(OUTPUT/"excluded_constraints.csv",excluded)
        old.write_json(OUTPUT/"preflight.json",result)
        print(json.dumps({k:result[k]for k in ["status","contracts","target_real_days","excluded_no_real_days","provider_connections"]}))
        return 0
    except BaseException as error:
        if isinstance(error,SystemExit):raise
        print(json.dumps(safety.safe_error(error)))
        return 1


if __name__=="__main__":
    raise SystemExit(main())
