"""Recover exactly missing daily references through normal public TqApi.

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

ROOT, LINE, PROJECT = old.ROOT, old.LINE, old.PROJECT
OUTPUT = LINE/"outputs/stage013_missing_daily_recovery"
ATTEMPT = OUTPUT/"network_attempt1"
PROTOCOL = LINE/"stages/20261018_0023_stage013_missing_daily_recovery_protocol.md"
PRIOR = LINE/"outputs/stage011_needed_local_completed"
REVIEW = LINE/"outputs/stage011_independent_review/review_receipt.json"
IMPORTER = PROJECT/"import_tqsdk_all_futures_daily_to_db.py"
DOWNLOADER = PROJECT/"download_tqsdk_all_futures_daily_csv.py"
DATABASE, MAPPING = safety.DATABASE, safety.MAPPING
REVIEW_SHA = "8cdfdbba2a15d12e04c6792b9073d53744f4cb0e711f2f67e452fed7705528fa"
DB_SHA = "273f0bc18de3070e4e085e4d6585fba71d6e1bb1256e3c7fb5adfc6532836a54"
SOFT_SECONDS, HARD_SECONDS, MEMORY_BYTES = 570, 600, 1_500_000_000
RAW = ["id","datetime",*old.VALUES]
DAILY = ["vt_symbol","tq_symbol","trade_date","datetime",*old.VALUES,
         "source_bar_id","source_datetime_ns","successor_id","successor_datetime_ns","successor_time"]


def daily_trade_date(nanoseconds):
    return pd.to_datetime(int(nanoseconds),unit="ns",utc=True).tz_convert("Asia/Shanghai").strftime("%Y-%m-%d")


def qualify_daily_snapshot(symbol, snapshot, references):
    """Only exact target days with a later valid bar and six fixed DB matches."""
    frame = snapshot.reindex(columns=RAW).apply(pd.to_numeric,errors="coerce")
    numeric = frame.to_numpy(dtype=float)
    finite = np.isfinite(numeric).all(axis=1)
    valid = finite & frame.id.ge(0) & frame.datetime.gt(0) & frame.id.eq(np.floor(frame.id))
    valid &= frame[["open","high","low","close"]].gt(0).all(axis=1)
    valid &= frame[["volume","open_oi","close_oi"]].ge(0).all(axis=1)
    valid &= frame.low.le(frame[["open","close"]].min(axis=1))
    valid &= frame.high.ge(frame[["open","close"]].max(axis=1))
    frame = frame.loc[valid].drop_duplicates(RAW).copy()
    # Conflicting identity rows cannot be rescued by arbitrary row order.
    frame = frame.loc[~frame.id.duplicated(keep=False) & ~frame.datetime.duplicated(keep=False)].copy()
    frame["local_time"] = pd.to_datetime(frame.datetime,unit="ns",utc=True,errors="coerce").dt.tz_convert("Asia/Shanghai")
    frame = frame.loc[frame.local_time.notna()].sort_values(["id","datetime"])
    frame["trade_date"] = frame.local_time.dt.strftime("%Y-%m-%d")
    accepted, audits = [], []
    for reference in references.to_dict("records"):
        day = str(reference["trade_date"])
        selected = frame.loc[frame.trade_date.eq(day)]
        audit = dict(vt_symbol=symbol,trade_date=day,accepted=False,reason="target_missing_or_nonunique",
                     mismatch_fields="",database_closeOI="N/A_not_independently_available")
        if len(selected)==1:
            row = selected.iloc[0]
            later = frame.loc[frame.id.gt(row.id) & frame.datetime.gt(row.datetime)]
            if later.empty:
                audit["reason"] = "no_forward_successor"
            else:
                successor = later.sort_values(["datetime","id"]).iloc[0]
                mismatch = []
                for field in ["open","high","low","close","volume","open_oi"]:
                    dbfield = "open_interest" if field=="open_oi" else field
                    expected = float(reference[dbfield])
                    if not np.isfinite(expected) or not np.isclose(float(row[field]),expected,rtol=1e-12,atol=1e-8):
                        mismatch.append(field)
                audit.update(reason="database_six_field_mismatch" if mismatch else "completed_and_six_fields_matched",
                    mismatch_fields=",".join(mismatch),accepted=not mismatch,
                    source_bar_id=int(row.id),source_datetime_ns=int(row.datetime),
                    successor_id=int(successor.id),successor_datetime_ns=int(successor.datetime))
                if not mismatch:
                    native,exchange = symbol.rsplit(".",1)
                    accepted.append(dict(vt_symbol=symbol,tq_symbol=f"{exchange}.{native}",trade_date=day,
                        datetime=row.local_time.isoformat(),**{field:float(row[field])for field in old.VALUES},
                        source_bar_id=int(row.id),source_datetime_ns=int(row.datetime),
                        successor_id=int(successor.id),successor_datetime_ns=int(successor.datetime),
                        successor_time=successor.local_time.isoformat()))
        audits.append(audit)
    return pd.DataFrame(accepted,columns=DAILY),pd.DataFrame(audits)


def atomic_csv(path, frame):
    path = Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary = path.with_suffix(path.suffix+".tmp")
    frame.to_csv(temporary,index=False)
    os.replace(temporary,path)


def frozen_inputs():
    if old.sha256(REVIEW)!=REVIEW_SHA:
        raise ValueError("stage011_review_changed")
    review = json.loads(REVIEW.read_text())
    if not review["qualified_research_overlay"] or review["p1_findings"]:
        raise ValueError("stage011_not_accepted")
    if old.sha256(PRIOR/"summary.json")!=review["source_summary_sha256"]:
        raise ValueError("stage011_summary_changed")
    summary = json.loads((PRIOR/"summary.json").read_text())
    for name in ["quarantine.csv","remaining_demand.csv"]:
        if old.sha256(PRIOR/name)!=summary["artifact_sha256"][name]:
            raise ValueError("stage011_demand_changed")
    quarantine = pd.read_csv(PRIOR/"quarantine.csv")
    remaining = pd.read_csv(PRIOR/"remaining_demand.csv")
    wanted = quarantine.loc[quarantine.reason.eq("required_daily_csv_seven_fields_missing"),
                            ["vt_symbol","execution_trade_date","requirement_kind"]]
    wanted = wanted.merge(remaining[["vt_symbol","execution_trade_date","real_daily_present"]],
        on=["vt_symbol","execution_trade_date"],validate="one_to_one",how="left")
    if len(wanted)!=4518 or wanted.vt_symbol.nunique()!=94 or wanted.real_daily_present.isna().any():
        raise ValueError("frozen_94_contract_demand_changed")
    real = wanted.real_daily_present.astype(str).str.lower().eq("true")
    excluded = wanted.loc[~real].copy()
    wanted = wanted.loc[real].copy()
    if len(excluded)!=16 or len(wanted)!=4502 or wanted.vt_symbol.nunique()!=94:
        raise ValueError("frozen_no_real_exclusion_changed")
    wal = Path(str(DATABASE)+"-wal")
    if wal.exists() and wal.stat().st_size:
        raise ValueError("nonempty_database_wal")
    references = []
    with sqlite3.connect(DATABASE.resolve().as_uri()+"?mode=ro&immutable=1",uri=True) as db:
        db.execute("PRAGMA query_only=ON")
        for symbol, group in wanted.groupby("vt_symbol",sort=True):
            native,exchange = symbol.rsplit(".",1)
            frame = pd.read_sql_query("SELECT substr(datetime,1,10) AS trade_date,open_price AS open,"
                "high_price AS high,low_price AS low,close_price AS close,volume,open_interest "
                "FROM dbbardata WHERE symbol=? AND exchange=? AND interval='d' ORDER BY datetime",db,
                params=[native,exchange])
            needed = group.rename(columns={"execution_trade_date":"trade_date"})
            joined = needed.merge(frame,on="trade_date",how="left",validate="one_to_one")
            if not np.isfinite(joined[["open","high","low","close","volume","open_interest"]].to_numpy(dtype=float)).all():
                raise ValueError("database_target_not_unique_real_finite")
            references.append(joined)
    targets = pd.concat(references,ignore_index=True).sort_values(["vt_symbol","trade_date"]).reset_index(drop=True)
    return targets,excluded.sort_values(["vt_symbol","execution_trade_date"]).reset_index(drop=True)


def preflight():
    if metadata.version("tqsdk")!="3.10.2":
        raise ValueError("frozen_sdk_version_changed")
    if any(os.environ.get(key) for key in safety.ENDPOINT_ENV):
        raise ValueError("nondefault_provider_endpoint_environment")
    safety.load_credentials()  # Presence only; values never returned or saved.
    targets,excluded = frozen_inputs()
    sdk = Path(metadata.distribution("tqsdk").locate_file("tqsdk"))
    paths = [Path(__file__),PROTOCOL,Path(old.__file__),Path(safety.__file__),DATABASE,MAPPING,IMPORTER,DOWNLOADER,
        REVIEW,PRIOR/"summary.json",PRIOR/"quarantine.csv",PRIOR/"remaining_demand.csv",
        *[sdk/name for name in ["api.py","auth.py","tradeable/sim/tqsim.py"]]]
    hashes = {str(path):old.sha256(path)for path in paths}
    if hashes[str(DATABASE)]!=DB_SHA:
        raise ValueError("accepted_database_changed")
    result = dict(status="passed_offline_preflight_no_provider_connection",contracts=94,
        source_missing_csv_demands=4518,target_real_days=len(targets),target_full_session_days=159,
        target_anchor_days=4343,excluded_no_real_days=len(excluded),duration_seconds=86400,data_length=10000,
        target_manifest_sha256=hashlib.sha256(targets.to_csv(index=False).encode()).hexdigest(),
        excluded_constraints_sha256=hashlib.sha256(excluded.to_csv(index=False).encode()).hexdigest(),
        source_fingerprints=hashes,sdk_version=metadata.version("tqsdk"),
        provider_connections=0,TqBacktest_instances=0,financial_replays=0,orders=0,cancels=0,
        planned_TqApi_max=1,planned_TqSim_max=1,soft_seconds=SOFT_SECONDS,hard_seconds=HARD_SECONDS,
        memory_budget_bytes=MEMORY_BYTES,memory_guard="worker peak RSS checked around each wait/subscription; parent hard wall-clock kill",
        credentials_fields_present=True,credential_values_saved=False,normal_grants_unmodified=True,
        sdk_raw_output_policy="DEVNULL_stdout_stderr_logging",automatic_retry=False,
        database_contract="OHLCV plus DB.open_interest equals provider.open_oi; DB.closeOI=N/A",
        completion_contract="strictly greater same-symbol source id and later valid daily timestamp",
        old_CSV_or_DB_write=False,production_qualified=False)
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
            status="all_94_snapshots_collected"
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
    if status=="all_94_snapshots_collected":
        status="completed_all_targets_qualified" if qualified_count==4502 else "completed_with_target_rejections"
    result=dict(status=status,provider_connections_attempted=int(provider_started),TqApi_max=1,
        TqSim_created=sim_created,TqBacktest_instances=0,collected_contracts=len(receipts),target_contracts=94,
        accepted_target_days=qualified_count,target_days=4502,elapsed_seconds=time.monotonic()-began,
        peak_memory_bytes=peak_memory(),automatic_retry=False,financial_replays=0,orders=0,cancels=0,
        broker_or_ctp_connections=0,model_fits=0,source_writes=0,raw_sdk_output_saved=False,
        credential_values_saved=False,old_CSV_or_DB_written=False,production_qualified=False,
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
            preflight_sha256=old.sha256(OUTPUT/"preflight.json"))
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
    modes.add_argument("--preflight",action="store_true")
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
