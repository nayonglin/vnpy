"""A bounded public history wrapper around the unchanged Stage012 collector."""
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
import numpy as np
import pandas as pd

import stage002_local_minute_overlay as validation
import stage007_tqsdk_stream_probe as safety
import stage012_provider_batch as core

ROOT,LINE,PROJECT=validation.ROOT,validation.LINE,validation.PROJECT
OUTPUT=LINE/"outputs/stage017_required_ap210_batch"
ATTEMPT=OUTPUT/"network_attempt1"
PROTOCOL=LINE/"stages/20261018_0044_stage017_required_ap210_batch_protocol.md"
S015=LINE/"outputs/stage015_daily_recovered_minute_delta"
R015=LINE/"outputs/stage015_independent_review/review_receipt.json"
R015_SHA="3512261d2191384f1099e7fbb77eda9622c9610ca855ad1d4607ad33e76552c9"
WINDOW=("2022-03-28","2022-04-06")
AP=("AP210.CZCE","2022-04-06")
SOFT,HARD=570,600


def select_bounded_targets(candidates,mandatory):
    if (mandatory["vt_symbol"],mandatory["execution_trade_date"])!=AP or mandatory["expected_minutes"]!=225:
        raise ValueError("mandatory_ap210_target_invalid")
    symbols={AP[0],*sorted({x["vt_symbol"]for x in candidates if x["vt_symbol"]!=AP[0]})[:7]}
    chosen=[mandatory];seen={AP};total=225
    for item in sorted(candidates,key=lambda x:(x["vt_symbol"],x["execution_trade_date"])):
        key=(item["vt_symbol"],item["execution_trade_date"])
        if item["vt_symbol"]not in symbols or key in seen:continue
        if total+item["expected_minutes"]>20000:continue
        chosen.append(item);seen.add(key);total+=item["expected_minutes"]
    return sorted(chosen,key=lambda x:(x["vt_symbol"],x["execution_trade_date"]))


def prepare():
    if OUTPUT.exists():raise FileExistsError("existing_stage017_refusing_reselection")
    if validation.sha256(R015)!=R015_SHA:raise ValueError("stage015_review_changed")
    summary=json.loads((S015/"summary.json").read_text())
    remaining_path=S015/"remaining_demand.csv"
    if validation.sha256(remaining_path)!=summary["artifact_sha256"]["remaining_demand.csv"]:
        raise ValueError("stage015_remaining_changed")
    frame=pd.read_csv(remaining_path)
    frame=frame.loc[frame.real_daily_present.astype(str).str.lower().eq("true") &
        frame.execution_trade_date.between(*WINDOW)]
    old_path=validation.OLD/"input_manifest.json"
    declared=json.loads(old_path.read_text())
    hashes={str(p):validation.sha256(p)for p in [remaining_path,S015/"summary.json",R015,old_path,validation.MAPPING]}
    if hashes[str(validation.MAPPING)]!=declared[str(validation.MAPPING.relative_to(ROOT))]:
        raise ValueError("source_calendar_changed")
    calendar=pd.DatetimeIndex(pd.to_datetime(pd.read_csv(validation.MAPPING,usecols=["date"]).date).drop_duplicates().sort_values())
    daily_cache={};skipped=0
    def item(symbol,day,kind,required=False):
        nonlocal skipped
        native,exchange=symbol.rsplit(".",1)
        path=PROJECT/"downloaded_futures/tqsdk_daily_2010_2026_04"/exchange/f"{native}.csv"
        if symbol not in daily_cache:
            if not path.is_file():
                if required:raise ValueError("mandatory_ap_daily_csv_missing")
                skipped+=1;return None
            digest=validation.sha256(path)
            if digest!=declared.get(str(path.relative_to(ROOT))):raise ValueError("original_daily_csv_changed")
            hashes[str(path)]=digest
            daily=pd.read_csv(path)
            daily["trade_date"]=pd.to_datetime(daily.trade_date).dt.strftime("%Y-%m-%d")
            daily_cache[symbol]=daily
        daily=daily_cache[symbol]
        hit=daily.loc[daily.trade_date.eq(day)]
        if len(hit)!=1 or any(field not in hit or not np.isfinite(float(hit.iloc[0][field]))for field in validation.VALUES):
            if required:raise ValueError("mandatory_ap_daily_seven_fields_invalid")
            skipped+=1;return None
        grid=validation.session_grid(symbol,day,calendar)
        return dict(vt_symbol=symbol,execution_trade_date=day,original_requirement_kind=kind,
            daily_csv_path=str(path),daily_reference={k:float(hit.iloc[0][k])for k in validation.VALUES},
            mandatory_ap210=required,expected_minutes=len(grid),expected_timestamps=[x.isoformat()for x in grid],
            session_start=grid[0].isoformat(),session_end_exclusive=(grid[-1]+pd.Timedelta(minutes=1)).isoformat())
    required=item(*AP,"full_session",required=True)
    candidates=[]
    for row in frame.itertuples():
        target=item(str(row.vt_symbol),str(row.execution_trade_date),str(row.requirement_kind))
        if target is not None:candidates.append(target)
    targets=select_bounded_targets(candidates,required)
    manifest=dict(status="frozen_before_connection",selection="mandatory_AP210_then_code_sorted_other7_contracts_cap20000",
        eligible_remaining_sessions=len(candidates),skipped_missing_or_invalid_original_daily=skipped,
        window=list(WINDOW),targets=targets,contracts=sorted({t["vt_symbol"]for t in targets}),
        target_minutes=sum(t["expected_minutes"]for t in targets),provider_start="2022-04-07T09:01:00",
        provider_end="2022-04-07T09:05:00",serial_data_length=10000,
        collector="unchanged_stage012_BatchCollector_observe_frames",input_sha256=hashes,
        protocol_sha256=validation.sha256(PROTOCOL),financial_replays=0,orders=0)
    OUTPUT.mkdir(parents=True,exist_ok=False)
    validation.write_json(OUTPUT/"batch_manifest.json",manifest)


def read_manifest():
    manifest=json.loads((OUTPUT/"batch_manifest.json").read_text());expected={}
    ap=[t for t in manifest["targets"]if(t["vt_symbol"],t["execution_trade_date"])==AP]
    if len(ap)!=1 or ap[0]["expected_minutes"]!=225:raise ValueError("mandatory_ap210_target_invalid")
    for target in manifest["targets"]:
        grid=pd.DatetimeIndex(target["expected_timestamps"])
        if len(grid)!=target["expected_minutes"] or grid.has_duplicates:raise ValueError("invalid_target_grid")
        expected.setdefault(target["vt_symbol"],[]).extend(grid)
    if any(len(v)!=len(set(v))for v in expected.values()):raise ValueError("duplicate_target_minute")
    core.BatchCollector(expected)  # Reuse its fixed 8-contract/20000 gate.
    return manifest,expected


def preflight():
    manifest,expected=read_manifest()
    if metadata.version("tqsdk")!="3.10.2":raise ValueError("frozen_sdk_version_changed")
    if any(os.environ.get(key)for key in safety.ENDPOINT_ENV):raise ValueError("provider_endpoint_override")
    safety.load_credentials()
    original=json.loads((core.OUTPUT/"preflight.json").read_text())["source_fingerprints"]
    paths=[Path(__file__),PROTOCOL,OUTPUT/"batch_manifest.json",Path(core.__file__),core.OUTPUT/"preflight.json",
        Path(validation.__file__),Path(safety.__file__)]
    sdk=Path(metadata.distribution("tqsdk").locate_file("tqsdk"))
    for name in ["api.py","auth.py","tradeable/sim/tqsim.py","backtest/backtest.py","tools/downloader.py"]:
        path=sdk/name
        if validation.sha256(path)!=original[str(path)]:raise ValueError("verified_sdk_changed")
        paths.append(path)
    if validation.sha256(Path(core.__file__))!=original[str(Path(core.__file__))]:raise ValueError("frozen_collector_changed")
    for path,digest in manifest["input_sha256"].items():
        if validation.sha256(path)!=digest:raise ValueError("batch_input_changed")
        paths.append(Path(path))
    if validation.sha256(PROTOCOL)!=manifest["protocol_sha256"]:raise ValueError("protocol_changed")
    return dict(status="passed_offline_preflight_no_connection",provider_connections=0,
        contracts=len(expected),target_sessions=len(manifest["targets"]),target_minutes=sum(map(len,expected.values())),
        mandatory_AP210_date=AP[1],mandatory_AP210_minutes=225,provider_start=manifest["provider_start"],
        provider_end=manifest["provider_end"],soft_seconds=SOFT,hard_seconds=HARD,provider_attempts_max=1,
        normal_authorization_required=True,credentials_present=True,credential_values_saved=False,
        auth_checks_unmodified=True,tq_dl_not_yet_queried=True,tq_dl_check="SDK _has_feature boolean as DataDownloader",
        independent_string_series_only=True,no_retry=True,raw_sdk_output_policy="DEVNULL",
        source_fingerprints={str(path):validation.sha256(path)for path in paths},financial_replays=0,orders=0)


def save(collector):
    raw,evidence=collector.frames()
    for name,frame in [("raw_completed_minutes.csv",raw),("completion_evidence.csv",evidence)]:
        temporary=ATTEMPT/(name+".tmp");frame.to_csv(temporary,index=False);os.replace(temporary,ATTEMPT/name)
    validation.write_json(ATTEMPT/"progress.json",dict(completed_minutes=len(raw),target_minutes=collector.target_count,
        updated_at=datetime.now().astimezone().isoformat(),network_attempts=1,financial_replays=0))


def qualify(collector,manifest):
    raw,evidence=collector.frames()
    raw=validation.normal_times(raw);empty=raw.iloc[:0].copy()
    proofs={(r.vt_symbol,pd.Timestamp(r.bar_datetime))for r in evidence.itertuples()
        if r.completed and pd.Timestamp(r.successor_time)>=pd.Timestamp(r.bar_datetime)+pd.Timedelta(minutes=1)}
    checks=[]
    for target in manifest["targets"]:
        grid=pd.DatetimeIndex(target["expected_timestamps"])
        _,check=validation.validate_session(raw.loc[raw.vt_symbol.eq(target["vt_symbol"])],grid,target["daily_reference"],empty)
        complete=all((target["vt_symbol"],t)in proofs for t in grid)
        checks.append(dict(vt_symbol=target["vt_symbol"],execution_trade_date=target["execution_trade_date"],
            accepted=bool(check["status"]=="accepted"and complete),completion_evidence_complete=complete,**check))
    ap=next(x for x in checks if(x["vt_symbol"],x["execution_trade_date"])==AP)
    quality=dict(sessions=checks,accepted_sessions=sum(x["accepted"]for x in checks),target_sessions=len(checks),
        all_sessions_accepted=all(x["accepted"]for x in checks),required_ap210_accepted=ap["accepted"],
        raw_rows=len(raw),financial_replays=0,cache_or_overlay_written=False)
    validation.write_json(ATTEMPT/"quality.json",quality)
    return quality


def worker(parent_pid):
    if os.getppid()!=parent_pid or not(ATTEMPT/"attempt_started.json").is_file():return 2
    manifest,expected=read_manifest();collector=core.BatchCollector(expected)
    api=None;created=False;provider=False;tq_dl=None;status="initializing";finished_types=()
    began=time.monotonic()
    with open(os.devnull,"w")as discard,redirect_stdout(discard),redirect_stderr(discard):
        logging.disable(logging.CRITICAL)
        try:
            from tqsdk import TqApi,TqAuth,TqBacktest,TqSim,BacktestFinished
            finished_types=(BacktestFinished,)
            username,password=safety.load_credentials();sim=TqSim();created=True;provider=True
            api=TqApi(account=sim,auth=TqAuth(username,password),
                backtest=TqBacktest(start_dt=datetime.fromisoformat(manifest["provider_start"]),
                    end_dt=datetime.fromisoformat(manifest["provider_end"])),debug=False,web_gui=False)
            username=password=None
            tq_dl=bool(api._auth._has_feature("tq_dl"))  # Same read-only boolean gate as DataDownloader.
            serials={}
            async def subscribe():
                for symbol in sorted(expected):
                    native,exchange=symbol.rsplit(".",1)
                    serials[symbol]=api.get_kline_serial(f"{exchange}.{native}",60,data_length=10000)
            api.create_task(subscribe());last_stamp={};saved=time.monotonic()
            while len(collector.records)<collector.target_count:
                if time.monotonic()-began>=SOFT:status="soft_time_budget_reached";break
                if not api.wait_update(deadline=time.time()+min(30,max(.01,SOFT-(time.monotonic()-began)))):
                    raise TimeoutError("provider_wait_timeout")
                for symbol,serial in serials.items():
                    if not api.is_serial_ready(serial):continue
                    stamp=serial.iloc[-1]["datetime"]
                    if last_stamp.get(symbol)==stamp:continue
                    initial=symbol not in last_stamp;last_stamp[symbol]=stamp
                    collector.observe(symbol,serial,initial=initial)
                if time.monotonic()-saved>=15:save(collector);saved=time.monotonic()
            else:status="all_target_minutes_completed"
        except finished_types:status="provider_finished"
        except BaseException as error:
            status="provider_or_local_failed";validation.write_json(ATTEMPT/"safe_error.json",safety.safe_error(error))
        finally:
            save(collector)
            if api is not None:
                try:api.close()
                except BaseException as error:
                    status="close_failed";validation.write_json(ATTEMPT/"safe_error.json",safety.safe_error(error))
    quality=qualify(collector,manifest)
    validation.write_json(ATTEMPT/"worker_receipt.json",dict(status=status,provider_attempts=int(provider),
        local_TqSim_created=created,tq_dl_permission=tq_dl,tq_dl_check_readonly=True,download_interface_switched=False,
        completed_minutes=len(collector.records),target_minutes=collector.target_count,
        required_ap210_accepted=quality["required_ap210_accepted"],accepted_sessions=quality["accepted_sessions"],
        financial_replays=0,orders=0,cancels=0,broker_or_ctp_connections=0,model_fits=0,
        raw_sdk_output_saved=False,credential_values_saved=False,cache_or_overlay_written=False,production_qualified=False))
    return 0 if quality["all_sessions_accepted"] else 1


def run_once():
    if ATTEMPT.exists():raise FileExistsError("existing_stage017_attempt_refusing_retry")
    frozen=json.loads((OUTPUT/"preflight.json").read_text())
    if preflight()!=frozen:raise ValueError("preflight_changed_since_review")
    ATTEMPT.mkdir(exist_ok=False)
    validation.write_json(ATTEMPT/"attempt_started.json",dict(started_at=datetime.now().astimezone().isoformat(),
        provider_attempts_max=1,soft_seconds=SOFT,hard_seconds=HARD,automatic_retry=False,financial_replays=0,orders=0))
    began=time.monotonic();process=None;killed=False
    try:
        process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),"--worker",str(os.getpid())],
            cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
        try:code=process.wait(timeout=HARD)
        except subprocess.TimeoutExpired:
            killed=True;os.killpg(process.pid,signal.SIGKILL);process.wait();code=-9
        unchanged=all(validation.sha256(path)==digest for path,digest in frozen["source_fingerprints"].items())
        result=dict(status="hard_timeout"if killed else"worker_terminal",exit_code=code,hard_kill=killed,
            elapsed_seconds=time.monotonic()-began,all_inputs_unchanged=unchanged,provider_attempts_max=1,
            automatic_retry=False,financial_replays=0,orders=0,cancels=0,broker_or_ctp_connections=0,
            raw_sdk_output_saved=False,credential_values_saved=False,cache_or_overlay_written=False,production_qualified=False)
        result["artifact_sha256"]={p.name:validation.sha256(p)for p in ATTEMPT.iterdir()if p.is_file()}
        validation.write_json(ATTEMPT/"parent_receipt.json",result)
        print(json.dumps({k:result[k]for k in ["status","exit_code","elapsed_seconds","all_inputs_unchanged"]}))
        return 0 if code==0 and unchanged else 1
    finally:
        if process is not None and process.poll()is None:os.killpg(process.pid,signal.SIGKILL);process.wait()


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    modes=parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--preflight",action="store_true");modes.add_argument("--run",action="store_true")
    modes.add_argument("--worker",type=int,help=argparse.SUPPRESS)
    args=parser.parse_args()
    try:
        if args.worker is not None:raise SystemExit(worker(args.worker))
        if args.run:raise SystemExit(run_once())
        prepare();result=preflight();validation.write_json(OUTPUT/"preflight.json",result)
        print(json.dumps({k:result[k]for k in ["status","contracts","target_sessions","target_minutes","mandatory_AP210_minutes","provider_start","provider_end"]}))
    except BaseException as error:
        if isinstance(error,SystemExit):raise
        print(json.dumps(safety.safe_error(error)));raise SystemExit(1)
