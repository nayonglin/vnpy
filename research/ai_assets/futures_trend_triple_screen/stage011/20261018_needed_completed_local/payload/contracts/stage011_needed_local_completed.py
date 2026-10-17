"""Qualify only needed local completed sessions, with append-only new keys.

No provider, financial engine, PnL, strategy initialization or source writes.
Stage010 must already exist; this tool never produces its own demand universe.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import hashlib
import io
import json
from pathlib import Path
import sys
import time

import numpy as np
import pandas as pd

import stage002_local_minute_overlay as old

ROOT = old.ROOT
LINE = old.LINE
PROJECT = old.PROJECT
OUTPUT = LINE / "outputs/stage011_needed_local_completed"
PROTOCOL = LINE / "stages/20261018_0005_stage011_needed_local_completed_protocol.md"
COVERAGE = LINE / "outputs/stage004_minute_coverage"
ACCEPTED = LINE / "outputs/stage002_local_minute_overlay/attempt2"
STAGE008 = LINE / "outputs/stage008_oi_requalification"
REVIEW008 = LINE / "outputs/stage008_independent_review/review_receipt.json"
SOURCE_FAMILIES = {
    "tqsdk_stage459_completed_preclose_full_bar_shard",
    "tqsdk_stage462_completed_preclose_full_dates_shard",
    "tqsdk_stage461_completed_preclose_full_dates_probe",
    "tqsdk_stage456_preclose_full_bar_probe",
}
EXPECTED_COVERAGE_SUMMARY = "d4edaf2926d9cd227afaba623201d2df3bd01c2b50eda33b3025d76702ba24f9"
EXPECTED_REVIEW008 = "aab0b7062ff32e67d4fdf2f3132b00188c5779cf59c1462144f002a7b25ddaa6"
VALUES = old.VALUES
COLUMNS = ["vt_symbol", "bar_datetime", *VALUES]


def read_bound_minute_source(path, expected_sha, symbol):
    """Read candidate bytes once; hash them before parsing and retain rejection."""
    path = Path(path)
    audit = dict(path=str(path), vt_symbol=symbol, expected_sha256=expected_sha,
                 status="quarantined_source", reason="", rows=0)
    if not path.is_file():
        audit["reason"] = "source_missing"
        return None, audit
    payload = path.read_bytes()
    audit.update(sha256=hashlib.sha256(payload).hexdigest(), bytes=len(payload))
    if not expected_sha or audit["sha256"] != expected_sha:
        audit["reason"] = "old_manifest_sha_mismatch"
        return None, audit
    try:
        frame = pd.read_csv(io.BytesIO(payload))
        if not set(COLUMNS).issubset(frame.columns):
            raise ValueError("required_minute_columns_missing")
        frame = old.normal_times(frame)
        if set(frame.vt_symbol.astype(str)) != {symbol}:
            raise ValueError("source_contract_identity_mismatch")
    except Exception as error:
        audit["reason"] = f"unusable_completed_source:{error}"
        return None, audit
    frame["source_row_number"] = np.arange(len(frame)) + 2
    audit.update(status="accepted_source_bytes", rows=len(frame))
    return frame, audit


def requirement_satisfied(existing, expected, kind):
    if kind not in {"full_session", "anchor"}:
        raise ValueError("unknown_requirement_kind")
    required = expected if kind == "full_session" else expected[:1]
    return len(required) > 0 and bool(pd.DatetimeIndex(required).isin(existing.bar_datetime).all())


def qualify_needed_session(sources, expected, daily, existing, requirement_kind):
    """Stitch consistent completed sources plus immutable existing minutes.

    Every addition, including an anchor request, needs the complete session and
    all seven independently available original CSV aggregate fields.
    """
    if requirement_kind not in {"full_session", "anchor"}:
        raise ValueError("unknown_requirement_kind")
    empty = existing.iloc[:0].copy()
    audit = dict(status="quarantined", reason="", requirement_kind=requirement_kind,
                 expected_minutes=len(expected), new_minutes=0, conflicting_minutes=0,
                 source_ids=[], source_rows=0)
    if daily is None or any(not np.isfinite(float(daily.get(k, np.nan))) for k in VALUES):
        audit["reason"] = "required_daily_csv_seven_fields_missing"
        return empty, audit
    parts = []
    for source_id, source in sources.items():
        selected = source.loc[source.bar_datetime.isin(expected), COLUMNS].copy()
        if selected.empty:
            continue
        audit["source_ids"].append(source_id)
        if selected.bar_datetime.duplicated().any():
            audit["reason"] = "duplicate_minute_within_completed_source"
            return empty, audit
        selected["source_ids"] = source_id
        parts.append(selected)
    audit["source_rows"] = sum(len(x) for x in parts)
    merged = pd.concat(parts, ignore_index=True) if parts else empty.reindex(columns=[*COLUMNS,"source_ids"])
    if len(merged):
        merged[VALUES] = merged[VALUES].apply(pd.to_numeric, errors="coerce")
        duplicates = merged.loc[merged.bar_datetime.duplicated(keep=False)]
        conflicts = 0
        if len(duplicates):
            grouped = duplicates.groupby("bar_datetime", sort=False)[VALUES]
            lower, upper = grouped.min().to_numpy(dtype=float), grouped.max().to_numpy(dtype=float)
            finite = grouped.count().eq(grouped.size(), axis=0).all(axis=1).to_numpy()
            consistent = np.isclose(lower, upper, rtol=1e-12, atol=1e-8, equal_nan=False).all(axis=1)
            conflicts = int((~(finite & consistent)).sum())
        if conflicts:
            audit.update(reason="completed_source_conflict", conflicting_minutes=conflicts)
            return empty, audit
        ids = merged.groupby("bar_datetime", sort=False).source_ids.agg(lambda x:";".join(sorted(set(x))))
        merged = merged.drop_duplicates("bar_datetime").copy()
        merged["source_ids"] = merged.bar_datetime.map(ids)
    previous = existing.loc[existing.bar_datetime.isin(expected), COLUMNS].copy()
    if previous.bar_datetime.duplicated().any():
        raise ValueError("duplicate_existing_minute_key")
    overlap = merged.loc[merged.bar_datetime.isin(previous.bar_datetime)]
    if len(overlap):
        before = previous.set_index("bar_datetime").loc[overlap.bar_datetime, VALUES].to_numpy(dtype=float)
        if not np.isclose(overlap[VALUES].to_numpy(dtype=float), before,
                          rtol=1e-12, atol=1e-8, equal_nan=False).all():
            audit["reason"] = "base_overlap_conflict"
            return empty, audit
    # Accepted old bytes may supply missing portions, but cannot be replaced.
    combined = pd.concat([previous, merged.loc[~merged.bar_datetime.isin(previous.bar_datetime)]],
                         ignore_index=True, sort=False)
    added, checked = old.validate_session(combined, expected, daily, previous)
    audit.update(checked)
    return added, audit


def read_bound_csv(path, expected, inputs, **kwargs):
    path = Path(path)
    payload = path.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    if not expected or digest != expected:
        raise ValueError(f"frozen_input_sha_mismatch:{path}")
    inputs[str(path)] = digest
    return pd.read_csv(io.BytesIO(payload), **kwargs)


def bound_json(path, expected, inputs):
    path = Path(path)
    payload = path.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    if expected and digest != expected:
        raise ValueError(f"frozen_json_sha_mismatch:{path}")
    inputs[str(path)] = digest
    return json.loads(payload)


def build(demand_dir, output=OUTPUT):
    demand_dir, output = Path(demand_dir).resolve(), Path(output).resolve()
    if output.exists():
        raise FileExistsError("existing_stage011_attempt_refusing_repeat")
    if not (demand_dir/"summary.json").is_file() or not (demand_dir/"demand.csv").is_file():
        raise FileNotFoundError("frozen_stage010_demand_not_ready")
    inputs = {}
    coverage_summary = bound_json(COVERAGE/"summary.json", EXPECTED_COVERAGE_SUMMARY, inputs)
    inherited = bound_json(COVERAGE/"input_manifest.json", coverage_summary["artifact_sha256"]["input_manifest.json"], inputs)
    inventory = read_bound_csv(COVERAGE/"local_source_candidates.csv",
        coverage_summary["artifact_sha256"]["local_source_candidates.csv"], inputs).fillna("")
    accepted_summary = bound_json(ACCEPTED/"summary.json", inherited[str(ACCEPTED/"summary.json")], inputs)
    old_sources = bound_json(ACCEPTED/"source_manifest.json", accepted_summary["source_manifest_sha256"], inputs)
    old_manifest_path = old.OLD/"input_manifest.json"
    declared = bound_json(old_manifest_path, old_sources["input_sha256"][str(old_manifest_path)], inputs)
    if old.sha256(Path(old.__file__)) != accepted_summary["builder_sha256"]:
        raise ValueError("accepted_stage002_helper_changed")
    inputs[str(Path(old.__file__))] = accepted_summary["builder_sha256"]
    summary010 = bound_json(demand_dir/"summary.json", None, inputs)
    if not str(summary010.get("status", "")).startswith("completed"):
        raise ValueError("stage010_demand_not_completed")
    artifacts010 = summary010.get("artifact_sha256", summary010.get("artifacts", {}))
    demand = read_bound_csv(demand_dir/"demand.csv", artifacts010.get("demand.csv"), inputs)
    required_columns = {"vt_symbol", "execution_trade_date", "requirement_kind"}
    if not required_columns.issubset(demand.columns):
        raise ValueError(f"stage010_demand_schema_missing:{sorted(required_columns-set(demand.columns))}")
    demand["execution_trade_date"] = pd.to_datetime(demand.execution_trade_date).dt.strftime("%Y-%m-%d")
    if demand.duplicated(["vt_symbol", "execution_trade_date"]).any():
        raise ValueError("duplicate_stage010_demand_identity")
    if not demand.requirement_kind.isin(["full_session", "anchor"]).all():
        raise ValueError("unknown_stage010_requirement_kind")
    mapping = read_bound_csv(old.MAPPING, inherited[str(old.MAPPING)], inputs, usecols=["date"])
    calendar = pd.DatetimeIndex(pd.to_datetime(sorted(mapping.date.unique())))
    base = old.normal_times(read_bound_csv(old.CACHE, inherited[str(old.CACHE)], inputs, usecols=COLUMNS))
    overlay002 = old.normal_times(read_bound_csv(ACCEPTED/"overlay.csv", accepted_summary["overlay_sha256"], inputs, usecols=COLUMNS))
    existing = pd.concat([base, overlay002], ignore_index=True)
    if old.minute_keys(existing).has_duplicates:
        raise ValueError("duplicate_frozen_base_overlay_key")
    by_symbol = {str(s):g for s,g in existing.groupby("vt_symbol", sort=False)}
    empty = existing.iloc[:0].copy()
    read_before = []
    for row in demand.itertuples():
        grid = old.session_grid(str(row.vt_symbol), row.execution_trade_date, calendar)
        available = by_symbol.get(str(row.vt_symbol), empty)
        read_before.append(requirement_satisfied(available, grid, row.requirement_kind))
    demand["ready_before"] = read_before
    needed = demand.loc[~demand.ready_before].copy()
    symbols = set(needed.vt_symbol.astype(str))
    selected = inventory.loc[inventory.workspace_root.eq(str(ROOT)) & inventory.family.isin(SOURCE_FAMILIES)
        & inventory.vt_symbol.astype(str).isin(symbols) & inventory.path.str.contains("_completed_minute_backtest.csv", regex=False)]
    if selected.path.duplicated().any():
        raise ValueError("duplicate_source_inventory_path")
    review008 = bound_json(REVIEW008, EXPECTED_REVIEW008, inputs)
    if not review008.get("qualified_research_data") or review008.get("p1_findings") != 0:
        raise ValueError("stage008_not_independently_accepted")
    qualification008 = bound_json(STAGE008/"requalification.json", review008["source_requalification_sha256"], inputs)
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    old.write_json(output/"attempt_started.json", dict(started_at=datetime.now().astimezone(),
        financial_replays=0, downloads=0, account_engines=0, model_fits=0))
    inputs.update({str(PROTOCOL):old.sha256(PROTOCOL), str(Path(__file__)):old.sha256(Path(__file__))})
    source_audits, daily_audits, session_audits, accepted_rows = [], [], [], []
    remaining_rows = []
    try:
        for number, symbol in enumerate(sorted(symbols)):
            sources = {}
            for record in selected.loc[selected.vt_symbol.eq(symbol)].to_dict("records"):
                path = Path(record["path"])
                if not path.resolve().is_relative_to((PROJECT/"downloaded_futures").resolve()):
                    raise ValueError("candidate_escapes_current_checkout")
                expected = declared.get(str(path.relative_to(ROOT)), "")
                if expected != record["manifest_declared_sha256"]:
                    raise ValueError("stage004_old_manifest_declaration_changed")
                frame, audit = read_bound_minute_source(path, expected, symbol)
                source_id = f"local_{len(source_audits):04d}"
                audit.update(source_id=source_id, family=record["family"])
                source_audits.append(audit)
                if frame is not None:
                    sources[source_id] = frame
                    inputs[str(path)] = audit["sha256"]
            if symbol == review008["qualified_symbol"]:
                frame, audit = read_bound_minute_source(qualification008["raw_path"], review008["raw_sha256"], symbol)
                audit.update(source_id="stage008_accepted_345", family="independently_accepted_completed_provider_probe")
                source_audits.append(audit)
                if frame is None or len(frame) != review008["qualified_rows"]:
                    raise ValueError("stage008_accepted_raw_changed")
                sources["stage008_accepted_345"] = frame
                inputs[qualification008["raw_path"]] = audit["sha256"]
            native, exchange = symbol.rsplit(".",1)
            daily_path = PROJECT/"downloaded_futures/tqsdk_daily_2010_2026_04"/exchange/f"{native}.csv"
            daily = None
            daily_audit = dict(vt_symbol=symbol, path=str(daily_path), status="rejected", reason="daily_csv_missing")
            if daily_path.is_file():
                expected = declared.get(str(daily_path.relative_to(ROOT)), "")
                payload = daily_path.read_bytes()
                digest = hashlib.sha256(payload).hexdigest()
                daily_audit.update(sha256=digest, expected_sha256=expected)
                if not expected or expected != digest:
                    daily_audit["reason"] = "old_manifest_daily_csv_sha_mismatch"
                else:
                    try:
                        daily = pd.read_csv(io.BytesIO(payload))
                        if not {"trade_date",*VALUES}.issubset(daily.columns):
                            raise ValueError("daily_seven_fields_missing")
                        daily["trade_date"] = pd.to_datetime(daily.trade_date).dt.strftime("%Y-%m-%d")
                        daily_audit.update(status="accepted_source_bytes", reason="")
                        inputs[str(daily_path)] = digest
                    except Exception as error:
                        daily = None
                        daily_audit["reason"] = str(error)
            daily_audits.append(daily_audit)
            available = by_symbol.get(symbol, empty)
            for row in needed.loc[needed.vt_symbol.eq(symbol)].itertuples():
                day = row.execution_trade_date
                grid = old.session_grid(symbol, day, calendar)
                candidates = daily.loc[daily.trade_date.eq(day)] if daily is not None else None
                daily_row = candidates.iloc[0].to_dict() if candidates is not None and len(candidates)==1 else None
                added, audit = qualify_needed_session(sources, grid, daily_row, available, row.requirement_kind)
                audit.update(vt_symbol=symbol, execution_trade_date=day,
                    session_start=str(grid[0]), session_last=str(grid[-1]),
                    daily_source_path=str(daily_path), daily_source_status=daily_audit["status"])
                session_audits.append(audit)
                if len(added):
                    added = added.copy()
                    added["trading_date"] = day
                    accepted_rows.append(added)
            if (number+1)%20 == 0:
                print(f"Stage011 needed contracts {number+1}/{len(symbols)}; checked sessions={len(session_audits)}", flush=True)
        overlay = pd.concat(accepted_rows, ignore_index=True, sort=False) if accepted_rows else empty.copy()
        if old.minute_keys(overlay).has_duplicates or len(old.minute_keys(existing).intersection(old.minute_keys(overlay))):
            raise ValueError("new_overlay_keys_not_unique_and_disjoint")
        new_by = {str(s):g for s,g in overlay.groupby("vt_symbol",sort=False)}
        for row in demand.to_dict("records"):
            symbol, day = str(row["vt_symbol"]), row["execution_trade_date"]
            grid = old.session_grid(symbol, day, calendar)
            before = by_symbol.get(symbol,empty)
            added = new_by.get(symbol,empty)
            old_count = int(grid.isin(before.bar_datetime).sum())
            add_count = int(grid.isin(added.bar_datetime).sum())
            after = pd.concat([before.loc[before.bar_datetime.isin(grid)], added.loc[added.bar_datetime.isin(grid)]], ignore_index=True)
            row.update(ready_after=requirement_satisfied(after,grid,row["requirement_kind"]),
                session_expected_minutes=len(grid), session_available_before=old_count,
                session_added_minutes=add_count, session_missing_after=len(grid)-old_count-add_count,
                anchor_present_after=bool(grid[0] in set(after.bar_datetime)))
            remaining_rows.append(row)
        anchors_path, scans_path = old.A0/"execution_anchor_requests.csv", old.A0/"minute_scan_requests.csv"
        anchors = read_bound_csv(anchors_path, old_sources["input_sha256"][str(anchors_path)], inputs)
        scans = read_bound_csv(scans_path, old_sources["input_sha256"][str(scans_path)], inputs)
        equivalence = old.prove_read_disjointness(overlay,anchors,scans,calendar)
        if equivalence["intersection_count"]:
            raise ValueError("new_keys_intersect_actual_A0_reads")
        overlay = overlay.reindex(columns=[*COLUMNS,"source_ids","trading_date"]).sort_values(["vt_symbol","bar_datetime"])
        overlay.to_csv(output/"overlay.csv",index=False,encoding="utf-8-sig")
        sessions = pd.DataFrame(session_audits)
        for field in ("source_ids","aggregate","daily_mismatch_fields"):
            if field in sessions:
                sessions[field] = sessions[field].map(lambda x:json.dumps(old.safe(x),ensure_ascii=False,sort_keys=True))
        sessions.to_csv(output/"session_manifest.csv",index=False,encoding="utf-8-sig")
        if len(sessions):
            sessions.loc[sessions.status.ne("accepted")].to_csv(output/"quarantine.csv",index=False,encoding="utf-8-sig")
        else:
            pd.DataFrame(columns=["status","reason"]).to_csv(output/"quarantine.csv",index=False)
        readiness = pd.DataFrame(remaining_rows)
        readiness.to_csv(output/"demand_readiness.csv",index=False,encoding="utf-8-sig")
        remaining = readiness.loc[~readiness.ready_after]
        remaining.to_csv(output/"remaining_demand.csv",index=False,encoding="utf-8-sig")
        old.write_json(output/"source_manifest.json",dict(sources=source_audits,daily_sources=daily_audits,
            minute_payload_reads_per_source=1,minute_payload_hashes_per_source=1,
            completion_scope="frozen completed-source declarations plus exact session and seven-field CSV qualification; not new provider successor observations"))
        old.write_json(output/"a0_path_equivalence.json",equivalence)
        old.write_json(output/"input_manifest.json",inputs)
        artifacts = {p.name:old.sha256(p) for p in output.iterdir() if p.is_file()}
        summary = dict(status="completed_needed_local_overlay_pending_independent_review",
            started_at=json.loads((output/"attempt_started.json").read_text())["started_at"],
            completed_at=str(datetime.now().astimezone()), elapsed_seconds=time.monotonic()-started,
            financial_replays=0, downloads=0, account_engines=0, strategy_initializations=0,
            model_fits=0, PnL_accessed=False, source_writes=0, order_api_calls=0, cancel_api_calls=0,
            input_demand_rows=len(demand), required_contracts=len(symbols), source_files=len(source_audits),
            accepted_source_files=sum(x["status"]=="accepted_source_bytes" for x in source_audits),
            requirements_ready_before=int(demand.ready_before.sum()), requirements_ready_after=int(readiness.ready_after.sum()),
            remaining_requirements=len(remaining), remaining_full_sessions=int(remaining.requirement_kind.eq("full_session").sum()),
            remaining_anchors=int(remaining.requirement_kind.eq("anchor").sum()),
            remaining_carry_or_missing_real_constraints=int((~remaining.real_daily_present.astype(str).str.lower().eq("true")).sum()),
            missing_full_session_minutes=int(remaining.loc[remaining.requirement_kind.eq("full_session"),"session_missing_after"].sum()),
            added_minutes=len(overlay), added_contracts=int(overlay.vt_symbol.nunique()),
            accepted_sessions=sum(x["status"]=="accepted" for x in session_audits),
            quarantined_sessions=sum(x["status"]!="accepted" for x in session_audits),
            quarantine_reasons=dict(Counter(x["reason"] for x in session_audits if x["status"]!="accepted")),
            new_key_intersection_with_base=0, a0_path_equivalence=equivalence,
            base_sha256=inputs[str(old.CACHE)], stage002_overlay_sha256=inputs[str(ACCEPTED/"overlay.csv")],
            original_sources_never_opened_for_write=True, financial_metrics="N/A", production_qualified=False,
            runtime=dict(python=sys.executable,numpy=np.__version__,pandas=pd.__version__),
            artifact_sha256=artifacts,
            limitations=["Demand is the frozen Stage010 conservative bound, not actual fills.",
                "Missing daily CSV remains rejected; no database fallback or isolated price repair.",
                "Research overlay awaits independent review; no provider or C0 replay is auto-started."])
        old.write_json(output/"summary.json",summary)
        print(json.dumps(old.safe(summary),ensure_ascii=False),flush=True)
    except Exception as error:
        old.write_json(output/"build_failure.json",dict(status="failed_no_accepted_overlay",error=repr(error),
            financial_replays=0,downloads=0,source_writes=0))
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build",action="store_true",required=True)
    parser.add_argument("--demand-dir",type=Path,required=True)
    args = parser.parse_args()
    build(args.demand_dir)
