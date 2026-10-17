"""Bounded minute-qualification delta from reviewed Stage013 daily references.

Only original remaining keys are reconsidered; no provider or financial engine.
"""
from __future__ import annotations

import argparse
from collections import Counter,defaultdict
from datetime import datetime
import hashlib
import io
import json
from pathlib import Path
import time

import numpy as np
import pandas as pd

import stage002_local_minute_overlay as old
import stage011_needed_local_completed as prior

ROOT,LINE,PROJECT=old.ROOT,old.LINE,old.PROJECT
OUTPUT=LINE/"outputs/stage015_daily_recovered_minute_delta"
PROTOCOL=LINE/"stages/20261018_0031_stage015_daily_recovered_minute_delta_protocol.md"
S011=LINE/"outputs/stage011_needed_local_completed"
R011=LINE/"outputs/stage011_independent_review/review_receipt.json"
S012=LINE/"outputs/stage012_provider_batch"
R012=LINE/"outputs/stage012_independent_review/review_receipt.json"
S013=LINE/"outputs/stage013_missing_daily_recovery"
R013=LINE/"outputs/stage013_independent_review/review_receipt.json"
R011_SHA="8cdfdbba2a15d12e04c6792b9073d53744f4cb0e711f2f67e452fed7705528fa"
R012_SHA="7992c3bdee73838d54769a9034148ef364be42a4f016efa2085d5a5bf4dbf7ef"
FIELDS=prior.COLUMNS


def approved_references(qualified,audits,review):
    if not review.get("qualified_research_daily") or review.get("p0_findings",0) or review.get("p1_findings",0):
        raise ValueError("daily_independent_review_not_accepted")
    accepted=audits.loc[audits.accepted.astype(str).str.lower().eq("true")]
    if qualified.duplicated(["vt_symbol","trade_date"]).any() or accepted.duplicated(["vt_symbol","trade_date"]).any():
        raise ValueError("duplicate_qualified_daily_identity")
    evidence={(str(r.vt_symbol),str(r.trade_date)):r._asdict()for r in accepted.itertuples(index=False)}
    result={}
    proof_fields=["source_bar_id","source_datetime_ns","successor_id","successor_datetime_ns"]
    for row in qualified.to_dict("records"):
        key=(str(row["vt_symbol"]),str(row["trade_date"]))
        proof=evidence.get(key)
        if proof is None:continue
        if any(not np.isfinite(float(row.get(f,np.nan)))for f in [*old.VALUES,*proof_fields]):continue
        if any(not np.isfinite(float(proof.get(f,np.nan)))or int(row[f])!=int(proof[f])for f in proof_fields):continue
        if not(row["successor_id"]>row["source_bar_id"] and row["successor_datetime_ns"]>row["source_datetime_ns"]):continue
        result[key]=row
    return result


def qualify_delta_session(symbol,day,references,sources,grid,existing,kind):
    reference=references.get((symbol,day))
    if reference is None:
        return existing.iloc[:0].copy(),dict(status="quarantined",reason="independently_qualified_daily_target_missing",
            new_minutes=0,source_ids=[])
    return prior.qualify_needed_session(sources,grid,reference,existing,kind)


class HashingReader(io.RawIOBase):
    def __init__(self,handle):self.handle=handle;self.digest=hashlib.sha256()
    def readable(self):return True
    def readinto(self,buffer):
        size=self.handle.readinto(buffer)
        if size:self.digest.update(memoryview(buffer)[:size])
        return size


def stream_relevant_existing(paths,requests,chunksize=200000):
    """Read/hash each frozen CSV once, retaining only exact requested keys."""
    pieces=[];manifest=[]
    indexes={s:pd.DatetimeIndex(grid)for s,grid in requests.items()}
    symbols=set(indexes)
    for path,expected in paths.items():
        path=Path(path);scanned=retained=0
        with path.open("rb") as handle:
            hashing=HashingReader(handle)
            with io.BufferedReader(hashing) as reader:
                for chunk in pd.read_csv(reader,usecols=FIELDS,chunksize=chunksize):
                    scanned+=len(chunk)
                    chosen=chunk.loc[chunk.vt_symbol.astype(str).isin(symbols)].copy()
                    if chosen.empty:continue
                    chosen=old.normal_times(chosen)
                    for symbol,group in chosen.groupby("vt_symbol",sort=False):
                        wanted=group.loc[group.bar_datetime.isin(indexes[str(symbol)])].copy()
                        if len(wanted):pieces.append(wanted);retained+=len(wanted)
            digest=hashing.digest.hexdigest()
        if digest!=expected:raise ValueError(f"existing_source_sha_changed:{path}")
        manifest.append(dict(path=str(path),sha256=digest,scanned_rows=scanned,retained_rows=retained))
    result=pd.concat(pieces,ignore_index=True)if pieces else pd.DataFrame(columns=FIELDS)
    if old.minute_keys(result).has_duplicates:raise ValueError("duplicate_existing_delta_scope_key")
    return result,manifest


def bind_json(path,expected,inputs):
    return prior.bound_json(path,expected,inputs)


def bind_review_sources(review,inputs):
    hashes=review.get("source_fingerprints",{})
    for path,digest in hashes.items():
        if old.sha256(path)!=digest:raise ValueError("reviewed_source_changed")
        inputs[path]=digest
    return hashes


def build(daily_review_sha):
    if OUTPUT.exists():raise FileExistsError("existing_stage015_attempt_refusing_repeat")
    inputs={}
    review011=bind_json(R011,R011_SHA,inputs)
    summary011=bind_json(S011/"summary.json",review011["source_summary_sha256"],inputs)
    input011=bind_json(S011/"input_manifest.json",summary011["artifact_sha256"]["input_manifest.json"],inputs)
    for module in [old,prior]:
        path=str(Path(module.__file__))
        if old.sha256(path)!=input011[path]:raise ValueError("previously_qualified_helper_changed")
        inputs[path]=input011[path]
    def read011(name):
        return prior.read_bound_csv(S011/name,summary011["artifact_sha256"][name],inputs)
    remaining=read011("remaining_demand.csv")
    readiness=read011("demand_readiness.csv")
    quarantine011=read011("quarantine.csv")
    sources011=bind_json(S011/"source_manifest.json",summary011["artifact_sha256"]["source_manifest.json"],inputs)
    review013=bind_json(R013,daily_review_sha,inputs)
    hashes013=bind_review_sources(review013,inputs)
    attempt013=S013/"network_attempt1"
    for name in ["qualified_daily.csv","target_qualification.csv","parent_receipt.json","worker_receipt.json"]:
        if str(attempt013/name)not in hashes013:raise ValueError("daily_review_missing_required_source_binding")
    parent013=json.loads((attempt013/"parent_receipt.json").read_text())
    if not parent013.get("all_inputs_unchanged"):raise ValueError("daily_parent_inputs_not_unchanged")
    qualified=prior.read_bound_csv(attempt013/"qualified_daily.csv",hashes013[str(attempt013/"qualified_daily.csv")],inputs)
    audits=prior.read_bound_csv(attempt013/"target_qualification.csv",hashes013[str(attempt013/"target_qualification.csv")],inputs)
    references=approved_references(qualified,audits,review013)
    missing_keys={(str(r.vt_symbol),str(r.execution_trade_date))for r in quarantine011.itertuples()
        if r.reason=="required_daily_csv_seven_fields_missing"}
    if not set(references).issubset(missing_keys):raise ValueError("daily_reference_outside_fixed_missing_csv_scope")
    review012=bind_json(R012,R012_SHA,inputs)
    if review012.get("p0_findings",0)or review012.get("p1_findings",0)or review012.get("qualified_precise_sessions")!=11:
        raise ValueError("stage012_not_independently_accepted")
    hashes012=bind_review_sources(review012,inputs)
    batch012=bind_json(S012/"batch_manifest.json",hashes012[str(S012/"batch_manifest.json")],inputs)
    parent012=bind_json(S012/"network_attempt1/parent_receipt.json",hashes012[str(S012/"network_attempt1/parent_receipt.json")],inputs)
    if not parent012.get("all_inputs_unchanged")or parent012.get("exit_code")!=0:
        raise ValueError("stage012_parent_not_accepted")
    source012=old.normal_times(prior.read_bound_csv(S012/"network_attempt1/raw_completed_minutes.csv",
        hashes012[str(S012/"network_attempt1/raw_completed_minutes.csv")],inputs))
    for target in batch012["targets"]:
        path=Path(target["daily_csv_path"])
        daily=prior.read_bound_csv(path,hashes012[str(path)] if str(path)in hashes012 else
            json.loads((S012/"preflight.json").read_text())["source_fingerprints"][str(path)],inputs)
        selected=daily.loc[pd.to_datetime(daily.trade_date).dt.strftime("%Y-%m-%d").eq(target["execution_trade_date"])]
        if len(selected)!=1:raise ValueError("stage012_daily_not_unique")
        references[(target["vt_symbol"],target["execution_trade_date"])]=selected.iloc[0].to_dict()
    scope=set(references)
    forbidden={(str(r.vt_symbol),str(r.execution_trade_date))for r in quarantine011.itertuples()if r.reason=="base_overlap_conflict"}
    if scope&forbidden:raise ValueError("original_base_conflict_cannot_be_reopened")
    bykey={(str(r.vt_symbol),str(r.execution_trade_date)):r._asdict()for r in remaining.itertuples(index=False)}
    if not scope.issubset(bykey):raise ValueError("delta_scope_not_remaining_only")
    if any(str(bykey[k]["real_daily_present"]).lower()!="true"for k in scope):
        raise ValueError("delta_scope_includes_no_real_constraint")
    old_manifest=bind_json(old.OLD/"input_manifest.json",input011[str(old.OLD/"input_manifest.json")],inputs)
    mapping=prior.read_bound_csv(old.MAPPING,old_manifest[str(old.MAPPING.relative_to(ROOT))],inputs,usecols=["date"])
    calendar=pd.DatetimeIndex(pd.to_datetime(sorted(mapping.date.unique())))
    grids={key:old.session_grid(key[0],key[1],calendar)for key in scope}
    requests=defaultdict(list)
    for (symbol,_),grid in grids.items():requests[symbol].append(grid)
    requests={symbol:pd.DatetimeIndex(np.unique(np.concatenate([g.to_numpy()for g in groups])))for symbol,groups in requests.items()}
    existing_paths={old.CACHE:summary011["base_sha256"],prior.ACCEPTED/"overlay.csv":summary011["stage002_overlay_sha256"],
        S011/"overlay.csv":summary011["artifact_sha256"]["overlay.csv"]}
    OUTPUT.mkdir(parents=True,exist_ok=False)
    began=time.monotonic()
    old.write_json(OUTPUT/"attempt_started.json",dict(started_at=datetime.now().astimezone(),financial_replays=0,downloads=0))
    try:
        existing,existing_manifest=stream_relevant_existing(existing_paths,requests)
        inputs.update({str(p):h for p,h in existing_paths.items()})
        bysymbol={str(s):g for s,g in existing.groupby("vt_symbol",sort=False)}
        empty=pd.DataFrame(columns=FIELDS)
        output_rows=[];session_audits=[];source_audits=[];updates={}
        symbols=sorted(requests)
        for number,symbol in enumerate(symbols):
            sources={}
            for source in sources011["sources"]:
                if source["vt_symbol"]!=symbol or source.get("family")not in prior.SOURCE_FAMILIES:continue
                if source["status"]!="accepted_source_bytes":continue
                path=Path(source["path"])
                if not path.resolve().is_relative_to((PROJECT/"downloaded_futures").resolve()):
                    raise ValueError("delta_source_outside_current_checkout")
                frame,audit=prior.read_bound_minute_source(path,source["sha256"],symbol)
                audit["source_id"]=source["source_id"];source_audits.append(audit)
                if frame is None:raise ValueError("previously_bound_completed_source_changed")
                sources[source["source_id"]]=frame.loc[frame.bar_datetime.isin(requests[symbol])]
                inputs[str(path)]=source["sha256"]
            provider=source012.loc[source012.vt_symbol.eq(symbol)]
            if len(provider):sources["stage012_reviewed_provider"]=provider
            available=bysymbol.get(symbol,empty)
            for key in sorted(k for k in scope if k[0]==symbol):
                row=bykey[key];grid=grids[key]
                added,audit=qualify_delta_session(symbol,key[1],references,sources,grid,available,row["requirement_kind"])
                audit.update(vt_symbol=symbol,execution_trade_date=key[1],requirement_kind=row["requirement_kind"])
                session_audits.append(audit)
                selected=available.loc[available.bar_datetime.isin(grid)]
                if len(added):
                    added=added.copy();added["trading_date"]=key[1];output_rows.append(added)
                after=pd.concat([selected,added],ignore_index=True,sort=False)
                updates[key]=dict(ready_after=prior.requirement_satisfied(after,grid,row["requirement_kind"]),
                    session_missing_after=len(grid)-len(after),anchor_present_after=bool(grid[0]in set(after.bar_datetime)),
                    stage015_added_minutes=len(added),stage015_status=audit["status"],stage015_reason=audit["reason"])
            if (number+1)%20==0:print(f"Stage015 delta contracts {number+1}/{len(symbols)}; sessions={len(session_audits)}",flush=True)
        overlay=pd.concat(output_rows,ignore_index=True,sort=False)if output_rows else empty.copy()
        if old.minute_keys(overlay).has_duplicates or len(old.minute_keys(overlay).intersection(old.minute_keys(existing))):
            raise ValueError("delta_keys_not_unique_disjoint")
        for r in overlay[["vt_symbol","bar_datetime"]].itertuples(index=False):
            if pd.Timestamp(r.bar_datetime)not in requests[str(r.vt_symbol)]:raise ValueError("new_key_outside_verified_existing_scope")
        source002=bind_json(prior.ACCEPTED/"source_manifest.json",input011[str(prior.ACCEPTED/"source_manifest.json")],inputs)
        paths002=source002["input_sha256"]
        anchors=prior.read_bound_csv(old.A0/"execution_anchor_requests.csv",paths002[str(old.A0/"execution_anchor_requests.csv")],inputs)
        scans=prior.read_bound_csv(old.A0/"minute_scan_requests.csv",paths002[str(old.A0/"minute_scan_requests.csv")],inputs)
        equality=old.prove_read_disjointness(overlay,anchors,scans,calendar)
        if equality["intersection_count"]:raise ValueError("new_delta_changes_actual_A0_read")
        merged=[]
        for row in readiness.to_dict("records"):
            key=(str(row["vt_symbol"]),str(row["execution_trade_date"]))
            row["stage015_checked"]=key in updates
            if key in updates:row.update(updates[key])
            merged.append(row)
        final=pd.DataFrame(merged)
        missing=final.loc[~final.ready_after.astype(str).str.lower().eq("true")]
        inputs.update({str(PROTOCOL):old.sha256(PROTOCOL),str(Path(__file__)):old.sha256(Path(__file__)),
            str(Path(prior.__file__)):old.sha256(Path(prior.__file__))})
        if any(old.sha256(path)!=digest for path,digest in inputs.items()):raise ValueError("source_changed_during_delta_build")
        overlay=overlay.reindex(columns=[*FIELDS,"source_ids","trading_date"]).sort_values(["vt_symbol","bar_datetime"])
        overlay.to_csv(OUTPUT/"overlay.csv",index=False)
        sessions=pd.DataFrame(session_audits)
        for field in ["source_ids","aggregate","daily_mismatch_fields"]:
            if field in sessions:sessions[field]=sessions[field].map(lambda x:json.dumps(old.safe(x),ensure_ascii=False,sort_keys=True))
        sessions.to_csv(OUTPUT/"session_manifest.csv",index=False)
        sessions.loc[sessions.status.ne("accepted")].to_csv(OUTPUT/"quarantine.csv",index=False)
        final.to_csv(OUTPUT/"demand_readiness.csv",index=False)
        missing.to_csv(OUTPUT/"remaining_demand.csv",index=False)
        old.write_json(OUTPUT/"source_manifest.json",dict(existing_scoped_read=existing_manifest,completed_sources=source_audits,
            daily_references=len(references),daily_review_sha256=daily_review_sha,source_fingerprints=inputs))
        old.write_json(OUTPUT/"input_manifest.json",inputs)
        old.write_json(OUTPUT/"a0_path_equivalence.json",equality)
        artifacts={p.name:old.sha256(p)for p in OUTPUT.iterdir()if p.is_file()}
        result=dict(status="completed_scoped_minute_delta_pending_independent_review",elapsed_seconds=time.monotonic()-began,
            delta_sessions=len(scope),delta_contracts=len(symbols),accepted_delta_sessions=int(sessions.status.eq("accepted").sum()),
            quarantine_reasons=dict(Counter(sessions.loc[sessions.status.ne("accepted"),"reason"])),
            added_minutes=len(overlay),added_contracts=int(overlay.vt_symbol.nunique()),
            input_required_sessions=len(readiness),ready_before=int(readiness.ready_after.astype(str).str.lower().eq("true").sum()),
            ready_after=len(final)-len(missing),remaining_requirements=len(missing),
            remaining_full_sessions=int(missing.requirement_kind.eq("full_session").sum()),
            remaining_anchors=int(missing.requirement_kind.eq("anchor").sum()),
            unrelated_readiness_rows_unchanged=len(readiness)-len(updates),original_13752_sessions_requalified=0,
            existing_rows_retained=len(existing),new_key_intersection_with_existing=0,a0_path_equivalence=equality,
            financial_replays=0,downloads=0,account_engines=0,orders=0,cancels=0,model_fits=0,PnL_accessed=False,
            source_writes=0,all_inputs_unchanged=True,financial_metrics="N/A",production_qualified=False,
            artifact_sha256=artifacts,
            limitations=["Only reviewed recovered target days and 11 reviewed provider sessions reconsidered.",
                "Missing/failed daily targets, 16 carry constraints and original conflicts are not waived.",
                "Original readiness retained for untouched keys; no new financial replay authorized."])
        old.write_json(OUTPUT/"summary.json",result)
        print(json.dumps(old.safe(result),ensure_ascii=False),flush=True)
    except Exception as error:
        old.write_json(OUTPUT/"build_failure.json",dict(status="failed_no_accepted_delta",error=repr(error),financial_replays=0,downloads=0))
        raise


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build",action="store_true",required=True)
    parser.add_argument("--daily-review-sha",required=True)
    args=parser.parse_args()
    build(args.daily_review_sha)
