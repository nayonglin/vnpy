from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[2]
OUTPUT = ROOT / "artifacts/stage011_basis_source_audit"
CACHE = REPO / "examples/portfolio_backtesting/backtest_outputs/external_supply_demand_cache"
EARLY = CACHE / "supply_demand_basis_20200101_20221231.csv"
LATE = CACHE / "supply_demand_basis_20230101_20260417.csv"
EVENTS = ROOT / "artifacts/stage001_history_qualification/event_features.csv"
LIFECYCLE = ROOT / "artifacts/stage003_cancelled_lifecycle/event_lifecycles.csv"
CALENDAR = ROOT.parent / "futures_trend_xgboost_formal_signal_marginal_utility_v4/artifacts/stage004_counterfactual_validation/workers/A/daily.csv"
EXPECTED = {
    EARLY: "d32bac39fd9c4ce057291768bbb9032520469127c90b9ef13caf810611c6796a",
    LATE: "150b1f13c07bb02a3ce410e46fec4d4b5c491930c77a9133fd601f3f93f19170",
    EVENTS: "33c48a4a3976e644365ceeccfadbf236f24bc327ae17413c363b43de7e69bcf1",
    LIFECYCLE: "d87652c9bb77612afbb03bf8cada3d63a00224a95e31be03cfd21495addee57b",
    CALENDAR: "ec4838ed9f67e263cbce59352b9d908f069374dd04cd88ea312b795a651dc981",
}
EVENT_COLUMNS = ["event_id", "decision_date", "product_vt_symbol", "contract_vt_symbol", "direction"]
STATUSES = ["available", "no_prior", "stale", "invalid_latest"]
QUOTES = ["spot_price", "near_contract_price", "dominant_contract_price", "near_basis_rate", "dom_basis_rate"]


def identity(path):
    return {"path": str(path.resolve()), "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def dates(values, fmt="%Y-%m-%d"):
    text = values.astype(str)
    pattern = r"\d{8}" if fmt == "%Y%m%d" else r"\d{4}-\d{2}-\d{2}"
    if not text.str.fullmatch(pattern).all():
        raise RuntimeError("date_format_invalid")
    try:
        return pd.to_datetime(text, format=fmt, errors="raise")
    except (ValueError, TypeError) as exc:
        raise RuntimeError("date_value_invalid") from exc


def normalize_basis(data):
    result = data.copy().reset_index(drop=True)
    result["source_date"] = dates(result.date, "%Y%m%d").dt.strftime("%Y-%m-%d")
    if not result.symbol.astype(str).str.fullmatch("[A-Za-z]+").all():
        raise RuntimeError("source_product_invalid")
    result["source_symbol"] = result.symbol.str.upper()
    if result.duplicated(["source_date", "source_symbol"]).any():
        raise RuntimeError("source_duplicate_keys")
    numeric = result[QUOTES].apply(pd.to_numeric, errors="coerce")
    positive = np.isfinite(numeric).all(axis=1) & numeric[QUOTES[:3]].gt(0).all(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        near = numeric.near_contract_price / numeric.spot_price - 1
        dominant = numeric.dominant_contract_price / numeric.spot_price - 1
    formula = np.isclose(near, numeric.near_basis_rate, atol=1e-12, rtol=0) & np.isclose(
        dominant, numeric.dom_basis_rate, atol=1e-12, rtol=0)
    contracts = (result.near_contract.astype(str).str.fullmatch("[A-Za-z]+[0-9]{3,4}")
                 & result.dominant_contract.astype(str).str.fullmatch("[A-Za-z]+[0-9]{3,4}"))
    result["quality_ok"] = positive & formula & contracts
    result["quality_reason"] = np.select(
        [~positive, ~formula, ~contracts], ["nonpositive_or_nonfinite", "formula_mismatch", "contract_invalid"],
        default="ok")
    return result


def coverage(events, normalized_basis):
    ev = events[EVENT_COLUMNS].copy()
    if ev.event_id.isna().any() or ev.event_id.duplicated().any():
        raise RuntimeError("event_inventory_invalid")
    decision_dates = dates(ev.decision_date)
    products = ev.product_vt_symbol.str.extract(r"^([A-Za-z]+)\.[A-Z]+$", expand=False)
    if products.isna().any() or not ev.direction.isin(["long", "short"]).all():
        raise RuntimeError("event_identity_invalid")
    groups = {key: part.sort_values("source_date") for key, part in normalized_basis.groupby("source_symbol")}
    records = []
    for position, event in enumerate(ev.to_dict("records")):
        decision = decision_dates.iloc[position]
        source = groups.get(products.iloc[position].upper())
        prior = source.loc[source.source_date.lt(event["decision_date"])] if source is not None else None
        row = {**event, "source_date": None, "age_days": None, "coverage_status": "no_prior",
               "source_quality_reason": None, "source_dominant_contract": None,
               "same_vendor_dominant_contract": None, **{name: None for name in QUOTES}}
        if prior is not None and len(prior):
            latest = prior.iloc[-1]
            age = int((decision - pd.Timestamp(latest.source_date)).days)
            status = "invalid_latest" if not latest.quality_ok else ("stale" if age > 7 else "available")
            row.update(source_date=latest.source_date, age_days=age, coverage_status=status,
                       source_quality_reason=latest.quality_reason,
                       source_dominant_contract=latest.dominant_contract,
                       same_vendor_dominant_contract=str(latest.dominant_contract).lower()
                       == str(event["contract_vt_symbol"]).split(".")[0].lower())
            if status == "available":
                row.update({name: float(latest[name]) for name in QUOTES})
        records.append(row)
    return pd.DataFrame(records)


def maturity_counts(rows, lifecycle, cutoffs):
    for frame in (rows, lifecycle):
        if frame.event_id.isna().any() or frame.event_id.duplicated().any():
            raise RuntimeError("lifecycle_inventory_invalid")
    if set(rows.event_id) != set(lifecycle.event_id):
        raise RuntimeError("lifecycle_inventory_mismatch")
    joined = rows[["event_id", "decision_date", "coverage_status"]].merge(
        lifecycle[["event_id", "end_date", "status"]], on="event_id", validate="one_to_one")
    closed = joined.status.isin(["mature", "mature_cancelled_unfilled"])
    censored = joined.status.isin(["right_censored_open", "right_censored_pending_entry"])
    if not (closed | censored).all() or joined.loc[closed, "end_date"].isna().any():
        raise RuntimeError("lifecycle_status_invalid")
    if joined.loc[censored, "end_date"].notna().any():
        raise RuntimeError("censored_end_date_invalid")
    dates(joined.loc[closed, "end_date"])
    dates(joined.decision_date)
    dates(pd.Series(cutoffs))
    return pd.DataFrame([{"cutoff": cutoff, "available_mature_count": int((
        closed & joined.coverage_status.eq("available") & joined.decision_date.lt(cutoff)
        & joined.end_date.fillna("9999-12-31").lt(cutoff)).sum())} for cutoff in cutoffs])


def page_publication(html, requested_day):
    dates(pd.Series([requested_day]))
    page = BeautifulSoup(html, "html.parser")
    title = page.title.get_text(" ", strip=True) if page.title else ""
    pattern = r"(\d{4})\u5e74(\d{1,2})\u6708(\d{1,2})\u65e5"
    title_date = re.search(pattern, title)
    actual = "-".join([title_date[1], title_date[2].zfill(2), title_date[3].zfill(2)]) if title_date else None
    if actual != requested_day:
        raise RuntimeError("page_date_mismatch")
    matches = re.finditer(pattern + r"\s+(\d{1,2}):(\d{2})", page.get_text(" ", strip=True))
    timestamps = set()
    for match in matches:
        day = "-".join([match[1], match[2].zfill(2), match[3].zfill(2)])
        if day == requested_day:
            timestamp = f"{day}T{match[4].zfill(2)}:{match[5]}:00+08:00"
            datetime.fromisoformat(timestamp)
            timestamps.add(timestamp)
    return {"requested_date": requested_day, "title": title, "page_date_verified": True,
            "declared_publication_at": next(iter(timestamps)) if len(timestamps) == 1 else None,
            "publication_timestamp_candidates": sorted(timestamps),
            "html_table_count": len(page.find_all("table")), "historical_revision_verified": False}


def counts(frame, group):
    return (frame.groupby([group, "coverage_status"]).size().unstack(fill_value=0)
            .reindex(columns=STATUSES, fill_value=0).reset_index())


def gap_days(calendar, last_source_date, end="2026-08-28"):
    values = dates(calendar.date)
    if values.duplicated().any() or not values.is_monotonic_increasing:
        raise RuntimeError("calendar_inventory_invalid")
    return pd.DataFrame({"date": values.loc[(values > last_source_date) & (values <= end)].dt.strftime("%Y-%m-%d")})


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def run():
    if OUTPUT.exists():
        raise RuntimeError("basis_audit_output_already_exists")
    files = {str(path): identity(path) for path in EXPECTED}
    for path, expected in EXPECTED.items():
        if files[str(path)]["sha256"] != expected:
            raise RuntimeError(f"basis_input_hash_mismatch:{path.name}")
    provenance = [Path(__file__), ROOT / "tests/test_stage011_basis_source_audit.py",
                  ROOT / "stages/20260906_0241_stage011_basis_source_contract.md",
                  REPO / ".py311/lib/python3.11/site-packages/akshare/futures/futures_basis.py",
                  REPO / "examples/portfolio_backtesting/analyze_qmt_roll_stage316_supply_demand_quality_probe.py",
                  REPO / "examples/portfolio_backtesting/analyze_qmt_roll_stage358_supply_demand_backfill_2020_2022.py"]
    files.update({str(path): identity(path) for path in provenance})
    OUTPUT.mkdir(parents=True)
    write_json(OUTPUT / "input_manifest.json", files)
    raw = pd.concat([pd.read_csv(path, dtype={"date": str, "symbol": str}).assign(source_file=path.name)
                     for path in (EARLY, LATE)], ignore_index=True)
    normalized = normalize_basis(raw)
    ev = pd.read_csv(EVENTS, usecols=EVENT_COLUMNS)
    if len(ev) != 276:
        raise RuntimeError("frozen_event_inventory_mismatch")
    life = pd.read_csv(LIFECYCLE, usecols=["event_id", "end_date", "status"])
    covered = coverage(ev, normalized)
    months = pd.date_range("2020-01-01", "2026-08-01", freq="MS").strftime("%Y-%m-%d").tolist()
    maturity = maturity_counts(covered, life, months)
    gap = gap_days(pd.read_csv(CALENDAR, usecols=["date"]), normalized.source_date.max())
    tables = {"source_quality.csv": normalized, "event_coverage.csv": covered,
              "year_coverage.csv": counts(covered.assign(year=covered.decision_date.str[:4]), "year"),
              "product_coverage.csv": counts(covered, "product_vt_symbol"),
              "monthly_maturity.csv": maturity, "full_calendar_gap_plan.csv": gap}
    for name, frame in tables.items():
        frame.to_csv(OUTPUT / name, index=False)
    first = maturity.loc[maturity.available_mature_count.ge(60), "cutoff"]
    if any(identity(Path(path)) != original for path, original in files.items()):
        raise RuntimeError("basis_inputs_changed_during_audit")
    summary = {"status": "completed_conditional_coverage_audit", "created_at_utc": datetime.now(timezone.utc).isoformat(),
               "source_rows": len(normalized), "source_start": normalized.source_date.min(),
               "source_end": normalized.source_date.max(), "source_products": normalized.source_symbol.nunique(),
               "source_quality_counts": normalized.quality_reason.value_counts().to_dict(),
               "event_count": len(covered), "event_coverage_counts": covered.coverage_status.value_counts().to_dict(),
               "available_contract_mismatch_count": int((covered.coverage_status.eq("available")
                                                         & covered.same_vendor_dominant_contract.eq(False)).sum()),
               "first_month_with_60_available_mature": first.iloc[0] if len(first) else None,
               "gap_trading_days": len(gap), "gap_first": gap.date.min() if len(gap) else None,
               "gap_last": gap.date.max() if len(gap) else None,
               "pit_status": "conditional_previous_calendar_date_max_7_days_not_vintage_verified",
               "new_model_fits": 0, "new_model_predictions": 0, "new_labels": 0, "new_backtests": 0, "reviewers": 0,
               "input_manifest": identity(OUTPUT / "input_manifest.json"),
               "outputs": {name: identity(OUTPUT / name) for name in tables}}
    write_json(OUTPUT / "summary.json", summary)
    return summary


def probe():
    import requests

    destination = OUTPUT / "source_probe"
    if destination.exists():
        raise RuntimeError("basis_probe_already_exists")
    summary = json.loads((OUTPUT / "summary.json").read_text())
    for name, expected in summary["outputs"].items():
        if identity(OUTPUT / name) != expected:
            raise RuntimeError("basis_probe_audit_changed")
    days = list(dict.fromkeys(["2025-12-10", summary["gap_first"], summary["gap_last"]]))
    days = [day for day in days if day is not None]
    if len(days) > 3:
        raise RuntimeError("probe_budget_exceeded")
    destination.mkdir()
    records = []
    for day in days:
        url = f"https://www.100ppi.com/sf/day-{day}.html"
        record = {"date": day, "url": url, "fetch_started_at_utc": datetime.now(timezone.utc).isoformat(),
                  "attempts": 1, "http_status": None, "historical_revision_verified": False}
        try:
            response = requests.get(url, timeout=(5, 10), allow_redirects=False)
            record.update(http_status=response.status_code, response_url=response.url)
            body = destination / f"{day}.html"
            body.write_bytes(response.content)
            record["raw_response"] = identity(body)
            if response.status_code == 200:
                # BeautifulSoup handles declared encodings before interpreting date text.
                document = BeautifulSoup(response.content, "html.parser")
                record.update(page_publication(str(document), day))
                record["status"] = "page_identity_verified_table_values_not_qualified"
            else:
                record["status"] = "http_failure"
        except Exception as exc:
            record.update(status="probe_failed", error=f"{type(exc).__name__}:{exc}")
        record["fetch_finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        records.append(record)
        write_json(destination / f"{day}.json", record)
    report = {"audit_summary": identity(OUTPUT / "summary.json"), "probes": records,
              "requests": len(records), "retries": 0, "data_extension_performed": False}
    write_json(destination / "summary.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe", action="store_true")
    args = parser.parse_args()
    print(json.dumps(probe() if args.probe else run(), indent=2, allow_nan=False))
