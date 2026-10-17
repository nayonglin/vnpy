"""Fixed Stage001 weekly screen. Reads derived returns only, never strategy PnL.

The supplied calendar defines real source trading days. Product rows are scoped
to the input date span; the full calendar is retained for partial-week checks.
Only the preceding completed ISO week's state is exposed to a date.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

FORMAL19 = frozenset({"GFEX.LC", "SHFE.AU", "SHFE.CU", "CZCE.MA", "CZCE.OI",
    "CZCE.AP", "CZCE.SM", "CZCE.SA", "SHFE.RB", "DCE.JM", "SHFE.HC",
    "CZCE.CF", "CZCE.FG", "CZCE.SH", "GFEX.SI", "SHFE.RU", "DCE.LH",
    "SHFE.SP", "SHFE.FU"})


def source_calendar(values):
    raw = np.asarray(values)
    if np.issubdtype(raw.dtype, np.integer):
        parsed = pd.to_datetime(raw.astype(str), format="%Y%m%d", errors="raise")
    elif raw.dtype.kind in {"O", "U", "S"} and len(raw) and all(
            len(str(v)) == 8 and str(v).isdigit() for v in raw):
        parsed = pd.to_datetime(raw.astype(str), format="%Y%m%d", errors="raise")
    else:
        parsed = pd.to_datetime(values, errors="raise")
    cal = pd.DatetimeIndex(parsed).normalize()
    if not len(cal) or cal.hasnans or cal.has_duplicates or not cal.is_monotonic_increasing:
        raise ValueError("calendar must contain unique increasing finite source dates")
    return cal


def build_weekly_features(product_features, calendar, products=None):
    """Return date/product states; unknowns must fall back to baseline behavior.

    Required input: date, product_id, r (same-contract causal log returns).
    No raw close, rolling main-contract price, or strategy results are read.
    An incomplete week interrupts the index and both EMA histories. EMA
    adjust=False, min_periods=12/26/9, with 35 valid weeks for two histograms.
    """
    required = {"date", "product_id", "r"}
    if not required.issubset(product_features.columns):
        raise ValueError(f"missing input fields: {sorted(required-set(product_features.columns))}")
    f = product_features[["date", "product_id", "r"]].copy()
    if f.empty:
        raise ValueError("empty return source")
    f["date"] = pd.to_datetime(f.date, errors="raise").dt.normalize()
    if f.duplicated(["date", "product_id"]).any():
        raise ValueError("duplicate product date")
    cal = source_calendar(calendar)
    if not f.date.isin(cal).all():
        raise ValueError("return source date is outside source calendar")
    f["r"] = pd.to_numeric(f.r, errors="raise").replace([np.inf, -np.inf], np.nan)
    selected = sorted(FORMAL19 if products is None else set(products))
    if not selected:
        raise ValueError("empty product selection")
    lo, hi = f.date.min(), f.date.max()
    output_days = cal[(cal >= lo) & (cal <= hi)]
    begin = lo - pd.Timedelta(days=lo.dayofweek)
    finish = hi + pd.Timedelta(days=6-hi.dayofweek)
    week_cal = cal[(cal >= begin) & (cal <= finish)]
    iso = week_cal.isocalendar()
    week_ids = (iso.year * 100 + iso.week).to_numpy()
    keys = list(dict.fromkeys(week_ids))
    week_positions = {key: i for i, key in enumerate(keys)}
    week_dates = {key: week_cal[week_ids == key] for key in keys}
    output_iso = output_days.isocalendar()
    output_keys = (output_iso.year * 100 + output_iso.week).to_numpy()
    output = []
    for product in selected:
        pf = f.loc[f.product_id.eq(product)].set_index("date").r
        entirely_missing = pf.empty or not np.isfinite(pf.to_numpy()).any()
        r = pf.reindex(week_cal)
        weeks = pd.DataFrame({
            "key": keys,
            "asof": [week_dates[key][-1] for key in keys],
            "complete": [np.isfinite(r.reindex(week_dates[key]).to_numpy()).all() for key in keys],
            "week_return": [r.reindex(week_dates[key]).sum(min_count=len(week_dates[key])) for key in keys],
        }).set_index("key")
        weeks["hist"] = np.nan
        weeks["hist_prev"] = np.nan
        weeks["complete_weeks"] = 0
        segments = (~weeks.complete).cumsum()
        for _, valid in weeks.loc[weeks.complete].groupby(segments.loc[weeks.complete], sort=False):
            index = 100.0 * np.exp(valid.week_return.cumsum())
            fast = index.ewm(span=12, adjust=False, min_periods=12).mean()
            slow = index.ewm(span=26, adjust=False, min_periods=26).mean()
            macd = fast - slow
            hist = macd - macd.ewm(span=9, adjust=False, min_periods=9).mean()
            weeks.loc[valid.index, "hist"] = hist
            weeks.loc[valid.index, "hist_prev"] = hist.shift(1)
            weeks.loc[valid.index, "complete_weeks"] = np.arange(1, len(valid)+1)
        for date, key in zip(output_days, output_keys):
            pos = week_positions[key]
            prev = weeks.loc[keys[pos-1]] if pos else None
            ready = bool(prev is not None and prev.complete and prev.complete_weeks >= 35
                         and np.isfinite(prev["hist"]) and np.isfinite(prev.hist_prev))
            direction = int(np.sign(prev["hist"]-prev.hist_prev)) if ready else 0
            if entirely_missing:
                reason = "missing_product_returns"
            elif prev is None:
                reason = "no_completed_week"
            elif not prev.complete:
                reason = "missing_previous_week_returns"
            elif not ready:
                reason = "warming_up" if prev.complete_weeks < 35 else "nonfinite_weekly_indicator"
            else:
                reason = "flat_weekly_histogram" if direction == 0 else "ready"
            output.append({"date": date, "product_id": product, "weekly_ready": ready,
                "weekly_direction": direction, "weekly_hist": float(prev["hist"]) if prev is not None else np.nan,
                "weekly_hist_prev": float(prev.hist_prev) if prev is not None else np.nan,
                "weekly_asof": prev["asof"] if prev is not None else pd.NaT,
                "weekly_complete_weeks": int(prev.complete_weeks) if prev is not None else 0,
                "reason": reason})
    return pd.DataFrame(output).sort_values(["date", "product_id"]).reset_index(drop=True)


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024*1024), b""):
            h.update(block)
    return h.hexdigest()


def main():
    repo = Path(__file__).resolve().parents[4]
    old = repo / "research/lines/futures_trend_rollover_shape_same_volume/outputs"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=old / "stage269_market_efficiency_validation/market/product_features.csv.gz")
    parser.add_argument("--calendar", type=Path, default=old / "stage265_deep_daily/rqalpha/trading_dates.npy")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "outputs/stage001_weekly_features")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    output = args.output / "weekly_daily.csv"
    if output.exists():
        raise FileExistsError("frozen weekly output already exists; do not silently rerun")
    started = datetime.now().astimezone().isoformat(timespec="seconds")
    source_hash, calendar_hash = sha256(args.source), sha256(args.calendar)
    f = pd.read_csv(args.source, usecols=["date", "product_id", "r"])
    f = f.loc[f.product_id.isin(FORMAL19)].copy()
    cal = np.load(args.calendar, allow_pickle=False)
    result = build_weekly_features(f, cal)
    result.to_csv(output, index=False, date_format="%Y-%m-%d")
    focus = result.loc[result.date.ge("2020-01-01")].copy()
    focus["year"] = focus.date.dt.year
    coverage = focus.groupby(["year", "product_id"], as_index=False).agg(
        product_days=("weekly_ready", "size"), ready_days=("weekly_ready", "sum"))
    coverage["ready_ratio"] = coverage.ready_days / coverage.product_days
    coverage.to_csv(args.output / "coverage_by_year_product.csv", index=False)
    summary = {
        "started_at": started, "completed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "line_id": "futures_trend_triple_screen", "stage": "stage001",
        "PnL_accessed": False, "strategy_PnL_accessed": False,
        "source_path": str(args.source.resolve()), "source_sha256": source_hash,
        "calendar_path": str(args.calendar.resolve()), "calendar_sha256": calendar_hash,
        "module_sha256": sha256(__file__), "tests_sha256": sha256(Path(__file__).with_name("test_stage001_weekly_features.py")),
        "output_path": str(output.resolve()), "output_sha256": sha256(output), "source_rows_read_selected_products": len(f),
        "products": sorted(FORMAL19), "rows": len(result), "start_date": str(result.date.min().date()),
        "end_date": str(result.date.max().date()), "date_basis": "source trading date, previous completed ISO week only",
        "macd": {"fast": 12, "slow": 26, "signal": 9, "adjust": False, "min_weeks": 35, "index_initial": 100.0},
        "missing_policy": "missing return invalidates whole ISO week and restarts index/EMA segment",
        "unknown_policy": "fall back to A0; weekly_direction=0 has no meaning unless weekly_ready=true",
        "full_reason_counts": result.reason.value_counts().to_dict(),
        "coverage_denominator": "all source days x fixed formal19, includes prelisting days; diagnostic only, not candidate-signal coverage",
        "research_2020_plus": {"product_days": len(focus), "ready_days": int(focus.weekly_ready.sum()),
            "ready_ratio": float(focus.weekly_ready.mean()), "fallback_days": int((~focus.weekly_ready).sum()),
            "reason_counts": focus.reason.value_counts().to_dict()},
    }
    (args.output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
