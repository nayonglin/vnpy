from __future__ import annotations

import bisect
import importlib.util
import json
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("chain_coverage_base028", ROOT / "tools/stage024_contract_catalog.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
SOURCE = ROOT / "artifacts/stage027_native_chain_source"
CATALOG = ROOT / "artifacts/stage026_sdk_cache_catalog/catalog.csv.gz"
CALENDAR = ROOT.parent / "futures_trend_xgboost_formal_signal_marginal_utility_v4/artifacts/stage004_counterfactual_validation/workers/A/daily.csv"
DATABASE = base.WORKSPACE.parent / "vnpy_production_live/.vntrader/database.db"
OUTPUT = ROOT / "artifacts/stage028_chain_coverage"
CONTRACT = ROOT / "stages/20260906_0654_stage028_chain_coverage_contract.md"
EVENT_COLUMNS = ["event_id", "decision_date", "product_vt_symbol", "contract_vt_symbol", "direction"]
BAR_COLUMNS = ["tq_symbol", "trade_date", "volume", "open_oi", "close_oi"]


def dates(values):
    series = pd.Series(values, dtype=str)
    if not series.str.fullmatch(r"\d{4}-\d{2}-\d{2}").all():
        raise ValueError("invalid_date_format")
    pd.to_datetime(series, format="%Y-%m-%d", errors="raise")


def valid_calendar(calendar):
    dates(calendar)
    if not calendar or list(calendar) != sorted(set(calendar)):
        raise ValueError("invalid_calendar")


def audit_chain(bars, catalog, calendar):
    valid_calendar(calendar)
    dates(bars.trade_date)
    dates(catalog.expire_date)
    if (bars.duplicated(["tq_symbol", "trade_date"]).any() or catalog.tq_symbol.duplicated().any()
            or catalog.vt_symbol.duplicated().any() or set(bars.tq_symbol) != set(catalog.tq_symbol)
            or not bars.trade_date.isin(calendar).all()):
        raise ValueError("source_inventory_or_calendar_invalid")
    values = bars[["volume", "open_oi", "close_oi"]].to_numpy(float)
    if not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("source_quantities_invalid")
    data = bars[BAR_COLUMNS].merge(catalog[["tq_symbol", "product_vt_symbol", "expire_date"]],
        on="tq_symbol", how="left", validate="many_to_one")
    if data.trade_date.gt(data.expire_date).any():
        raise ValueError("source_after_expiry")
    expected = Counter()
    missing = []
    lifetime = []
    for symbol, rows in data.groupby("tq_symbol", sort=True):
        product = rows.product_vt_symbol.iloc[0]
        first, last = rows.trade_date.min(), rows.trade_date.max()
        expiry = rows.expire_date.iloc[0]
        active = calendar[bisect.bisect_left(calendar, first):bisect.bisect_right(calendar, expiry)]
        actual = set(rows.trade_date)
        for day in active:
            expected[(day, product)] += 1
            if day not in actual:
                missing.append(dict(trade_date=day, product_vt_symbol=product, tq_symbol=symbol))
        lifetime.append(dict(tq_symbol=symbol, product_vt_symbol=product, first_observed=first,
            last_observed=last, expire_date=expiry, observed_days=len(actual), expected_days=len(active),
            missing_days=len(active) - len(actual)))
    gaps = pd.DataFrame(missing, columns=["trade_date", "product_vt_symbol", "tq_symbol"])
    grid = pd.MultiIndex.from_product([calendar, sorted(catalog.product_vt_symbol.unique())],
        names=["trade_date", "product_vt_symbol"])
    grouped = data.groupby(["trade_date", "product_vt_symbol"])
    frame = grouped.agg(actual_contracts=("tq_symbol", "size"), total_close_oi=("close_oi", "sum"),
        positive_oi_contracts=("close_oi", lambda x: int(x.gt(0).sum()))).reindex(grid)
    frame["actual_contracts"] = frame.actual_contracts.fillna(0).astype(int)
    frame["positive_oi_contracts"] = frame.positive_oi_contracts.fillna(0).astype(int)
    frame["expected_contracts"] = [expected[key] for key in grid]
    frame["missing_contracts"] = frame.expected_contracts - frame.actual_contracts
    if frame.missing_contracts.lt(0).any():
        raise ValueError("unexpected_observed_contract")
    frame["coverage_status"] = np.select([frame.expected_contracts.eq(0), frame.missing_contracts.gt(0),
        frame.total_close_oi.isna() | frame.total_close_oi.le(0)],
        ["not_yet_observed", "missing_observed_contract", "nonpositive_chain_oi"], default="available")
    return frame.reset_index(), gaps, pd.DataFrame(lifetime)


def windows(decisions, products, chain, calendar):
    valid_calendar(calendar)
    lookup = {(r.trade_date, r.product_vt_symbol): r.coverage_status for r in chain.itertuples()}
    result = []
    for day, product in zip(decisions, products, strict=True):
        if day not in calendar:
            raise ValueError("decision_outside_calendar")
        index = bisect.bisect_left(calendar, day)
        prior = calendar[max(0, index - 6):index]
        state = [lookup.get((d, product), "missing_product") for d in prior]
        status = "insufficient_history" if len(prior) != 6 else "available" if set(state) == {"available"} else "incomplete_chain_window"
        result.append(dict(decision_date=day, product_vt_symbol=product, source_date=prior[-1] if prior else None,
            window_start=prior[0] if prior else None, coverage_status=status,
            bad_chain_dates=json.dumps([d for d, value in zip(prior, state) if value != "available"])))
    return pd.DataFrame(result)


def event_coverage(events, bars, catalog, chain, calendar):
    ev = events[EVENT_COLUMNS].copy().reset_index(drop=True)
    dates(ev.decision_date)
    if ev.isna().any().any() or ev.event_id.duplicated().any() or not ev.direction.isin(["long", "short"]).all():
        raise ValueError("event_identity_invalid")
    meta = catalog.set_index("vt_symbol").to_dict("index")
    for row in ev.itertuples():
        if (row.contract_vt_symbol not in meta or meta[row.contract_vt_symbol]["product_vt_symbol"] != row.product_vt_symbol
                or row.decision_date > meta[row.contract_vt_symbol]["expire_date"]):
            raise ValueError("event_contract_identity_invalid")
    result = windows(ev.decision_date, ev.product_vt_symbol, chain, calendar)
    actual = set(zip(bars.tq_symbol, bars.trade_date))
    for i, row in ev.iterrows():
        index = bisect.bisect_left(calendar, row.decision_date)
        symbol = meta[row.contract_vt_symbol]["tq_symbol"]
        prior = calendar[max(0, index - 6):index]
        missing = [day for day in prior if (symbol, day) not in actual]
        result.loc[i, "missing_actual_contract_dates"] = json.dumps(missing)
        if missing and result.loc[i, "coverage_status"] == "available":
            result.loc[i, "coverage_status"] = "actual_contract_history_missing"
    return pd.concat([ev, result.drop(columns=["decision_date", "product_vt_symbol"])], axis=1)


def run():
    if OUTPUT.exists():
        raise RuntimeError("chain_coverage_output_exists")
    expected = {SOURCE / "summary.json": "1cc361ac370fa3d300eaa86d51ac9f151d063b0c7668242e426d7067192969c4",
        CATALOG: "bb6b7fd68228a5074328e3cc8a2001e4e4c1b0bba86632a7158d9b9d0cb4679c",
        CALENDAR: "ec4838ed9f67e263cbce59352b9d908f069374dd04cd88ea312b795a651dc981",
        DATABASE: "a683e8d99c1925ef2af546e62b61f62c9946d21ea4e5be4af42737a80f77eef5",
        base.EVENTS: "33c48a4a3976e644365ceeccfadbf236f24bc327ae17413c363b43de7e69bcf1"}
    for path, sha in expected.items():
        if base.identity(path)["sha256"] != sha:
            raise RuntimeError("frozen_source_changed")
    source_summary = json.loads((SOURCE / "summary.json").read_text())
    if source_summary["status"] != "acquired_pending_chain_qualification":
        raise RuntimeError("source_not_acquired")
    source_inputs = json.loads((SOURCE / "input_manifest.json").read_text())
    sources = {**source_inputs, **{v["path"]: v for v in source_summary["outputs"].values()}}
    for path, value in sources.items():
        if base.identity(path) != value:
            raise RuntimeError("source_artifact_changed")
    paths = list(expected) + [Path(__file__), CONTRACT, ROOT / "tests/test_stage028_chain_coverage.py",
                            ROOT / "tools/stage024_contract_catalog.py"]
    sources.update({str(p): base.identity(p) for p in paths})
    OUTPUT.mkdir(parents=True)
    base.save(OUTPUT / "input_manifest.json", sources)
    report = dict(status="running", started_at=datetime.now().astimezone().isoformat(),
        model_feature_values_generated=False, label_read_count=0, model_fit_predict_count=0,
        strategy_backtest_count=0, reviewer_count=0, production_write_count=0,
        historical_listing_universe_proven=False, historical_vintage_proven=False)
    try:
        with sqlite3.connect(f"file:{DATABASE}?mode=ro", uri=True) as conn:
            conn.execute("PRAGMA query_only=ON")
            calendar = [r[0] for r in conn.execute("SELECT DISTINCT substr(datetime,1,10) AS day FROM dbbardata "
                "WHERE interval='d' AND datetime >= '2019-11-01' AND datetime < '2026-08-29' ORDER BY day")]
        a_days = pd.read_csv(CALENDAR, usecols=["date"]).date.tolist()
        if len(calendar) != 1657 or len(a_days) != 1614 or [d for d in calendar if d >= "2020-01-02"] != a_days:
            raise RuntimeError("calendar_scope_changed")
        catalog = pd.read_csv(CATALOG)
        events = pd.read_csv(base.EVENTS, usecols=EVENT_COLUMNS)
        parts = [pd.read_csv(SOURCE / name, usecols=BAR_COLUMNS, float_precision="round_trip")
                 for name in sorted(source_summary["outputs"]) if name.endswith(".daily.csv.gz")]
        bars = pd.concat(parts, ignore_index=True)
        if len(bars) != 272649 or len(catalog) != 1325 or len(events) != 276:
            raise RuntimeError("source_dimensions_changed")
        chain, gaps, lifetime = audit_chain(bars, catalog, calendar)
        covered = event_coverage(events, bars, catalog, chain, calendar)
        product_days = [(day, product) for day in a_days for product in sorted(catalog.product_vt_symbol.unique())]
        full = windows([v[0] for v in product_days], [v[1] for v in product_days], chain, calendar)
        for name, value in {"calendar.csv": pd.DataFrame({"date": calendar}), "chain_daily.csv.gz": chain,
            "missing_contract_days.csv.gz": gaps, "observed_lifetimes.csv": lifetime,
            "event_coverage.csv": covered, "a_calendar_coverage.csv.gz": full,
            "source_bars.csv.gz": bars}.items():
            value.to_csv(OUTPUT / name, index=False)
        ready = bool(covered.coverage_status.eq("available").all())
        report.update(status="event_source_qualified_not_model" if ready else "chain_event_coverage_fail_no_features",
            event_count=len(covered), event_status_counts=covered.coverage_status.value_counts().to_dict(),
            missing_contract_days=len(gaps), missing_contracts=int(gaps.tq_symbol.nunique()),
            chain_status_counts=chain.coverage_status.value_counts().to_dict(),
            calendar_status_counts=full.coverage_status.value_counts().to_dict(),
            source_calendar_days=len(calendar), a_calendar_days=len(a_days))
        if any(base.identity(path) != value for path, value in sources.items()):
            raise RuntimeError("inputs_changed_during_coverage")
        report["inputs_unchanged"] = True
    except Exception as exc:
        report.update(status="coverage_technical_failure", error_type=type(exc).__name__, error=str(exc))
        raise
    finally:
        report["finished_at"] = datetime.now().astimezone().isoformat()
        report["outputs"] = {p.name: base.identity(p) for p in sorted(OUTPUT.iterdir()) if p.name != "summary.json"}
        base.save(OUTPUT / "summary.json", report)
    print(json.dumps({k: v for k, v in report.items() if k != "outputs"}), flush=True)


if __name__ == "__main__":
    run()
