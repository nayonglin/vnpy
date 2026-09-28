from __future__ import annotations

import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[2]
OUTPUT = ROOT / "artifacts/stage019_member_concentration_source"
SOURCE = ROOT.parent / "futures_trend_rebuilt_c9_15w_optimization/outputs/stage080_member_rank_2022_backfill_feasibility/rebuilt_c9_stage080_member_rank_2022_backfill_feasibility_combined_raw_stage080_member_rank_2022_backfill_feasibility_v1.csv"
EVENTS = ROOT / "artifacts/stage001_history_qualification/event_features.csv"
LIFECYCLE = ROOT / "artifacts/stage003_cancelled_lifecycle/event_lifecycles.csv"
CALENDAR = ROOT.parent / "futures_trend_xgboost_formal_signal_marginal_utility_v4/artifacts/stage004_counterfactual_validation/workers/A/daily.csv"
CONTRACT = ROOT / "stages/20260906_0456_stage019_member_concentration_source_contract.md"
EXPECTED = {
    SOURCE: "9b22de83f4530859bcb440e016ab89017d5e453f1660dd4b841aa792ce43afbf",
    EVENTS: "33c48a4a3976e644365ceeccfadbf236f24bc327ae17413c363b43de7e69bcf1",
    LIFECYCLE: "d87652c9bb77612afbb03bf8cada3d63a00224a95e31be03cfd21495addee57b",
    CALENDAR: "ec4838ed9f67e263cbce59352b9d908f069374dd04cd88ea312b795a651dc981",
}
FAMILIES = ("long_open_interest", "short_open_interest", "vol")
QUANTITIES = [f"{family}_top{rank}" for family in FAMILIES for rank in (5, 10, 15, 20)]
EVENT_COLUMNS = ["event_id", "decision_date", "product_vt_symbol", "contract_vt_symbol", "direction"]
STATUSES = ["available", "no_previous_session", "outside_source_range", "missing_contract", "invalid_exact"]


def helpers():
    path = ROOT / "tools/stage011_basis_source_audit.py"
    spec = importlib.util.spec_from_file_location("stage019_source_helpers", path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def identity(path):
    before = path.stat()
    with path.open("rb") as stream:
        sha = hashlib.file_digest(stream, "sha256").hexdigest()
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise RuntimeError(f"source_changed_during_hash:{path}")
    return {"path": str(path.resolve()), "size": before.st_size, "mtime_ns": before.st_mtime_ns, "sha256": sha}


def normalize(raw):
    frame = raw[["symbol", "variety", "date", *QUANTITIES]].copy().reset_index(drop=True)
    frame["source_date"] = helpers().dates(frame.date, "%Y%m%d").dt.strftime("%Y-%m-%d")
    frame["source_symbol"] = frame.symbol.astype(str).str.upper()
    frame["source_product"] = frame.variety.astype(str).str.upper()
    if not frame.source_symbol.str.fullmatch(r"[A-Z]+(?:[0-9]{3,4})?").all():
        raise RuntimeError("source_symbol_invalid")
    prefix = frame.source_symbol.str.extract(r"^([A-Z]+)", expand=False)
    if not frame.source_product.str.fullmatch(r"[A-Z]+").all() or not prefix.eq(frame.source_product).all():
        raise RuntimeError("source_variety_mismatch")
    if frame.duplicated(["source_date", "source_symbol"]).any():
        raise RuntimeError("source_duplicate_keys")
    numeric = frame[QUANTITIES].apply(pd.to_numeric, errors="coerce")
    finite_nonnegative = np.isfinite(numeric).all(axis=1) & numeric.ge(0).all(axis=1)
    integral = numeric.eq(np.floor(numeric)).all(axis=1)
    monotone = pd.Series(True, index=frame.index)
    positive = pd.Series(True, index=frame.index)
    for family in FAMILIES:
        values = numeric[[f"{family}_top{rank}" for rank in (5, 10, 15, 20)]]
        monotone &= values.diff(axis=1).iloc[:, 1:].ge(0).all(axis=1)
        positive &= values.iloc[:, -1].gt(0)
    frame["is_aggregate"] = frame.source_symbol.eq(frame.source_product)
    frame["quality_ok"] = finite_nonnegative & integral & monotone & positive
    frame["quality_reason"] = np.select(
        [~finite_nonnegative, ~integral, ~monotone, ~positive],
        ["nonfinite_or_negative", "noninteger", "cumulative_decrease", "nonpositive_top20"], default="ok")
    return frame


def coverage(events, source, calendar):
    ev = events[EVENT_COLUMNS].copy().reset_index(drop=True)
    dates = helpers().dates
    days = dates(calendar.date).dt.strftime("%Y-%m-%d")
    if days.empty or days.duplicated().any() or not days.is_monotonic_increasing:
        raise RuntimeError("calendar_inventory_invalid")
    dates(ev.decision_date)
    if ev.event_id.isna().any() or ev.event_id.duplicated().any():
        raise RuntimeError("event_inventory_invalid")
    products = ev.product_vt_symbol.str.extract(r"^([A-Za-z]+)\.([A-Z]+)$")
    contracts = ev.contract_vt_symbol.str.extract(r"^([A-Za-z]+)([0-9]{3,4})\.([A-Z]+)$")
    if (products.isna().any().any() or contracts.isna().any().any()
            or not products[0].str.upper().eq(contracts[0].str.upper()).all()
            or not products[1].eq(contracts[2]).all() or not ev.direction.isin(["long", "short"]).all()):
        raise RuntimeError("event_contract_identity_invalid")
    previous = dict(zip(days, [None, *days.iloc[:-1].tolist()]))
    if not ev.decision_date.isin(days).all():
        raise RuntimeError("event_date_not_in_calendar")
    exact = {(row.source_date, row.source_symbol): row for row in source.itertuples()}
    groups = {(day, product): group for (day, product), group in source.groupby(["source_date", "source_product"])}
    lower, upper = source.source_date.min(), source.source_date.max()
    rows = []
    for event in ev.to_dict("records"):
        required = previous[event["decision_date"]]
        symbol = event["contract_vt_symbol"].split(".")[0].upper()
        product = event["product_vt_symbol"].split(".")[0].upper()
        match = exact.get((required, symbol))
        group = groups.get((required, product))
        if required is None:
            status = "no_previous_session"
        elif required < lower or required > upper:
            status = "outside_source_range"
        elif match is None:
            status = "missing_contract"
        else:
            status = "available" if match.quality_ok else "invalid_exact"
        rows.append({**event, "required_source_date": required, "coverage_status": status,
                     "source_quality_reason": match.quality_reason if match is not None else None,
                     "same_day_aggregate_present": bool(group is not None and group.is_aggregate.any()),
                     "same_day_other_contract_count": int((~group.is_aggregate & group.source_symbol.ne(symbol)).sum())
                     if group is not None else 0})
    return pd.DataFrame(rows)


def grouped_counts(rows, key):
    return (rows.groupby([key, "coverage_status"]).size().unstack(fill_value=0)
            .reindex(columns=STATUSES, fill_value=0).reset_index())


def run():
    if OUTPUT.exists():
        raise RuntimeError("member_source_output_already_exists")
    bound = list(EXPECTED) + [Path(__file__), CONTRACT, ROOT / "tests/test_stage019_member_concentration_source.py",
                             ROOT / "tools/stage011_basis_source_audit.py",
                             REPO / ".py311/lib/python3.11/site-packages/akshare/futures/cot.py"]
    inputs = {str(path): identity(path) for path in bound}
    for path, sha in EXPECTED.items():
        if inputs[str(path)]["sha256"] != sha:
            raise RuntimeError(f"member_source_hash_mismatch:{path}")
    OUTPUT.mkdir(parents=True)
    write_json = helpers().write_json
    write_json(OUTPUT / "input_manifest.json", inputs)
    try:
        raw = pd.read_csv(SOURCE, usecols=["symbol", "variety", "date", *QUANTITIES], dtype={"date": str})
        events = pd.read_csv(EVENTS, usecols=EVENT_COLUMNS)
        lifecycle = pd.read_csv(LIFECYCLE, usecols=["event_id", "end_date", "status"])
        calendar = pd.read_csv(CALENDAR, usecols=["date"])
        source = normalize(raw)
        rows = coverage(events, source, calendar)
        if len(rows) != 276:
            raise RuntimeError("full_event_inventory_not_276")
        rows["year"] = rows.decision_date.str[:4]
        cutoffs = pd.date_range("2020-01-01", "2026-08-01", freq="MS").strftime("%Y-%m-%d").tolist()
        mature = helpers().maturity_counts(rows, lifecycle, cutoffs)
        source_dates = source.source_date.unique()
        date_gaps = calendar.loc[~calendar.date.isin(source_dates)].copy()
        date_gaps["gap_kind"] = np.select(
            [date_gaps.date.lt(source.source_date.min()), date_gaps.date.gt(source.source_date.max())],
            ["before_source_start", "after_source_end"], default="interior_no_any_source_row")
        frames = {"event_coverage.csv": rows, "product_coverage.csv": grouped_counts(rows, "product_vt_symbol"),
                  "year_coverage.csv": grouped_counts(rows, "year"), "maturity_counts.csv": mature,
                  "calendar_source_date_gaps.csv": date_gaps,
                  "source_quality.csv": source[["source_date", "source_symbol", "source_product", "is_aggregate", "quality_ok", "quality_reason"]]}
        for name, frame in frames.items():
            frame.to_csv(OUTPUT / name, index=False)
        qualified_months = mature.loc[mature.available_mature_count.ge(60), "cutoff"]
        summary = {
            "stage": "stage019_member_concentration_source", "status": "audit_completed",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "decision": "necessary_event_coverage_pass_more_provenance_required" if rows.coverage_status.eq("available").all()
            else "source_insufficient_no_feature_or_training",
            "event_count": len(rows), "event_status_counts": rows.coverage_status.value_counts().to_dict(),
            "raw_row_count": len(source), "source_first_date": source.source_date.min(),
            "source_last_date": source.source_date.max(), "source_date_count": len(source_dates),
            "source_product_count": int(source.source_product.nunique()),
            "raw_aggregate_count": int(source.is_aggregate.sum()),
            "raw_contract_row_count": int((~source.is_aggregate).sum()),
            "source_quality_counts": source.quality_reason.value_counts().to_dict(),
            "unavailable_event_with_aggregate_count": int((rows.coverage_status.ne("available") & rows.same_day_aggregate_present).sum()),
            "unavailable_event_with_other_contract_count": int((rows.coverage_status.ne("available") & rows.same_day_other_contract_count.gt(0)).sum()),
            "first_60_mature_available_cutoff": qualified_months.iloc[0] if len(qualified_months) else None,
            "calendar_source_gap_counts": date_gaps.gap_kind.value_counts().to_dict(),
            "source_count": len(inputs), "historical_publication_verified": False,
            "historical_revision_verified": False, "raw_rank_member_completeness_verified": False,
            "full_runtime_contract_coverage_verified": False,
            "future_target_columns_read": [], "new_label_count": 0, "new_fit_count": 0,
            "new_prediction_count": 0, "new_strategy_replay_count": 0, "network_attempt_count": 0,
            "reviewer_started": False, "outputs": {name: identity(OUTPUT / name) for name in frames},
        }
        summary["outputs"]["input_manifest.json"] = identity(OUTPUT / "input_manifest.json")
        for path, before in inputs.items():
            if identity(Path(path)) != before:
                raise RuntimeError(f"member_input_changed:{path}")
        write_json(OUTPUT / "summary.json", summary)
        print(json.dumps(summary, indent=2, allow_nan=False))
    except Exception as exc:
        write_json(OUTPUT / "failure.json", {"stage": "stage019_member_concentration_source",
                   "error": f"{type(exc).__name__}:{exc}", "created_at_utc": datetime.now(timezone.utc).isoformat()})
        raise


if __name__ == "__main__":
    run()
