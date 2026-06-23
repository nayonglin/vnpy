from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import json
import math
from pathlib import Path
from typing import Any
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage010"
MODEL_TAG = "stage010_authoritative_minute_coverage_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
TOOL_DIR = SCRIPT_PATH.parent
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
for item in [str(TOOL_DIR), str(EXAMPLE_DIR)]:
    if item not in sys.path:
        sys.path.insert(0, item)

import stage008_no_follow_reduce_true_engine as s008
from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage010_authoritative_minute_coverage_audit"

ARM = "A_official_stage847_c9_15w"
FULL_WINDOW_ID = "2018_01_to_2026_06_15"
START = pd.Timestamp("2018-01-01")
END = pd.Timestamp("2026-06-15")
CAPITAL = 150_000.0
FIRST_N_BARS = 30
PER_PAGE = 4
MAX_ATLAS_ROWS = 20

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CURVE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_curve_{MODEL_TAG}.csv"
TRADES_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_trades_{MODEL_TAG}.csv"
ENTRY_RISK_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_entry_risk_{MODEL_TAG}.csv"
ENTRY_CANDIDATES_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_entry_candidates_{MODEL_TAG}.csv"
TRADE_EVENTS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_trade_events_{MODEL_TAG}.csv"
INTRADAY_EVENTS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_intraday_events_{MODEL_TAG}.csv"
CLOSED_LOTS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_closed_lots_{MODEL_TAG}.csv"
COVERAGE_FEATURES_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_coverage_features_{MODEL_TAG}.csv"
COVERAGE_STATS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_coverage_stats_{MODEL_TAG}.csv"
YEAR_COVERAGE_STATS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_coverage_stats_{MODEL_TAG}.csv"
CONTRIBUTION_CURVE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_coverage_contribution_curve_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_chart_{MODEL_TAG}.png"
COVERAGE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_coverage_chart_{MODEL_TAG}.png"
CONTRIBUTION_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_coverage_contribution_chart_{MODEL_TAG}.png"
ATLAS_MANIFEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_page{{page:03d}}_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    return s008._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s008._md_table(frame, max_rows=max_rows)


def _safe_float(value: Any, default: float = np.nan) -> float:
    return s008._safe_float(value, default=default)


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    return s008._drawdown_pct(equity)


def _normalize_day(value: Any) -> pd.Timestamp:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return pd.NaT
    ts = pd.Timestamp(ts)
    if ts.tzinfo is not None:
        ts = ts.tz_localize(None)
    return ts.normalize()


def _official_profile(metadata: dict[str, Any]) -> dict[str, Any]:
    window = {"start": START, "end": END, "start_month": "2018-01", "window_id": FULL_WINDOW_ID}
    legacy_state = s008.s928._with_legacy_stage372_spec()
    try:
        profile = s008.s928._c9_15w_profile(metadata, window)
    finally:
        s008.s928._restore_legacy_state(legacy_state)
    spec = profile["spec"]
    capital = replace(
        spec.capital,
        variant="stage010_official_c9_15w_coverage_audit_2018_01",
        label="Stage010 official C9/15w authoritative minute coverage audit",
        account_capital=CAPITAL,
        c3_capital=CAPITAL,
        note=(
            f"{spec.capital.note} | Stage010 read-only coverage audit. "
            "No trading rule is added; official C9/15w is replayed only to bind closed lots to Stage861 full minute coverage."
        ),
    )
    result = dict(profile)
    result["profile"] = ARM
    result["spec"] = replace(spec, capital=capital, profile=ARM)
    return result


def _run_official(metadata: dict[str, Any]) -> tuple[dict[str, Any], pd.DataFrame, dict[str, pd.DataFrame]]:
    profile = _official_profile(metadata)
    original_start = s008.s847.START
    original_end = s008.s847.END
    legacy_state = s008.s928._with_legacy_stage372_spec()
    try:
        s008.s847.START = START
        s008.s847.END = END
        combined, frames = s008.s847._run_profile(profile, metadata)
    finally:
        s008.s847.START = original_start
        s008.s847.END = original_end
        s008.s928._restore_legacy_state(legacy_state)
    return profile, combined, frames


def _summary(profile: dict[str, Any], combined: pd.DataFrame, frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    row = s008.s650._metrics(combined, profile["spec"].capital, cost_multiplier=1.0)
    trade_events = frames.get("trade_events", pd.DataFrame())
    stop_retry_events = frames.get("stop_retry_events", pd.DataFrame())
    broker10_cap_event_count = 0
    if not trade_events.empty and "reason" in trade_events.columns:
        broker10_cap_event_count = int(trade_events["reason"].astype(str).str.startswith("broker10_margin_cap", na=False).sum())
    row.update(
        {
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "arm": ARM,
            "official_live_version": OFFICIAL_LIVE_VERSION,
            "official_live_alias": OFFICIAL_LIVE_ALIAS,
            "window_id": FULL_WINDOW_ID,
            "window_start": START.date().isoformat(),
            "window_end": END.date().isoformat(),
            "actual_start": pd.to_datetime(combined["date"], errors="coerce").min().date().isoformat(),
            "actual_end": pd.to_datetime(combined["date"], errors="coerce").max().date().isoformat(),
            "trading_days": int(len(combined)),
            "stop_retry_event_count": int(len(stop_retry_events)),
            "broker10_cap_event_count": broker10_cap_event_count,
            "closed_trade_rows": int(len(frames.get("trades", pd.DataFrame()))),
        }
    )
    return row


def _curve(combined: pd.DataFrame, profile: dict[str, Any]) -> pd.DataFrame:
    curve = combined.copy()
    curve["stage"] = STAGE
    curve["model_tag"] = MODEL_TAG
    curve["line_id"] = LINE_ID
    curve["arm"] = ARM
    curve["window_id"] = FULL_WINDOW_ID
    curve["account_capital"] = CAPITAL
    curve["nav"] = pd.to_numeric(curve["account_equity"], errors="coerce") / CAPITAL
    curve["drawdown_pct"] = _drawdown_pct(curve["account_equity"])
    curve["variant"] = profile["spec"].capital.variant
    return curve


def _day_for_symbol(groups: dict[str, pd.DataFrame], vt_symbol: str, entry_day: pd.Timestamp) -> pd.DataFrame:
    bars = groups.get(vt_symbol, pd.DataFrame())
    if bars.empty or pd.isna(entry_day):
        return pd.DataFrame()
    return bars[bars["bar_date"].eq(entry_day)].copy().sort_values("bar_datetime").reset_index(drop=True)


def _nearest_dates(groups: dict[str, pd.DataFrame], vt_symbol: str, entry_day: pd.Timestamp) -> tuple[float, float, str, str]:
    bars = groups.get(vt_symbol, pd.DataFrame())
    if bars.empty or pd.isna(entry_day):
        return np.nan, np.nan, "", ""
    dates = pd.to_datetime(bars["bar_date"], errors="coerce").dropna().drop_duplicates().sort_values()
    before = dates[dates.lt(entry_day)]
    after = dates[dates.gt(entry_day)]
    before_days = float((entry_day - before.iloc[-1]).days) if not before.empty else np.nan
    after_days = float((after.iloc[0] - entry_day).days) if not after.empty else np.nan
    return (
        before_days,
        after_days,
        before.iloc[-1].date().isoformat() if not before.empty else "",
        after.iloc[0].date().isoformat() if not after.empty else "",
    )


def _risk_price(row: pd.Series) -> float:
    stop_distance = _safe_float(row.get("stop_distance"))
    if np.isfinite(stop_distance) and stop_distance > 0:
        return stop_distance
    risk_amount = _safe_float(row.get("risk_amount"))
    volume = _safe_float(row.get("volume"))
    size = _safe_float(row.get("size"))
    if np.isfinite(risk_amount) and np.isfinite(volume) and np.isfinite(size) and volume > 0 and size > 0:
        risk = abs(risk_amount) / (volume * size)
        return risk if risk > 0 else np.nan
    return np.nan


def _minute_features(row: pd.Series, full_day: pd.DataFrame) -> dict[str, Any]:
    entry_price = _safe_float(row.get("entry_price"))
    risk = _risk_price(row)
    direction = str(row.get("direction"))
    if full_day.empty or not np.isfinite(entry_price) or not np.isfinite(risk) or risk <= 0:
        return {
            "first_30m_directional_r": np.nan,
            "first_30m_mfe_r": np.nan,
            "first_30m_mae_r": np.nan,
            "entry_day_mfe_r": np.nan,
            "entry_day_mae_r": np.nan,
            "clean_continuation_30m": 0,
            "no_follow_30m": 0,
            "risk_price": risk,
            "risk_valid": int(np.isfinite(risk) and risk > 0),
        }
    first = full_day.head(FIRST_N_BARS).copy()
    if first.empty:
        return {
            "first_30m_directional_r": np.nan,
            "first_30m_mfe_r": np.nan,
            "first_30m_mae_r": np.nan,
            "entry_day_mfe_r": np.nan,
            "entry_day_mae_r": np.nan,
            "clean_continuation_30m": 0,
            "no_follow_30m": 0,
            "risk_price": risk,
            "risk_valid": 1,
        }
    if direction == "short":
        first_directional = (entry_price - float(first.iloc[-1]["close"])) / risk
        first_mfe = (entry_price - pd.to_numeric(first["low"], errors="coerce").min()) / risk
        first_mae = (pd.to_numeric(first["high"], errors="coerce").max() - entry_price) / risk
        day_mfe = (entry_price - pd.to_numeric(full_day["low"], errors="coerce").min()) / risk
        day_mae = (pd.to_numeric(full_day["high"], errors="coerce").max() - entry_price) / risk
    else:
        first_directional = (float(first.iloc[-1]["close"]) - entry_price) / risk
        first_mfe = (pd.to_numeric(first["high"], errors="coerce").max() - entry_price) / risk
        first_mae = (entry_price - pd.to_numeric(first["low"], errors="coerce").min()) / risk
        day_mfe = (pd.to_numeric(full_day["high"], errors="coerce").max() - entry_price) / risk
        day_mae = (entry_price - pd.to_numeric(full_day["low"], errors="coerce").min()) / risk
    first_mfe = max(0.0, first_mfe) if np.isfinite(first_mfe) else np.nan
    first_mae = max(0.0, first_mae) if np.isfinite(first_mae) else np.nan
    day_mfe = max(0.0, day_mfe) if np.isfinite(day_mfe) else np.nan
    day_mae = max(0.0, day_mae) if np.isfinite(day_mae) else np.nan
    clean = int(np.isfinite(first_directional) and np.isfinite(first_mae) and first_directional > 0 and first_mae <= 0.5)
    no_follow = int(np.isfinite(first_directional) and first_directional <= 0)
    return {
        "first_30m_directional_r": first_directional,
        "first_30m_mfe_r": first_mfe,
        "first_30m_mae_r": first_mae,
        "entry_day_mfe_r": day_mfe,
        "entry_day_mae_r": day_mae,
        "clean_continuation_30m": clean,
        "no_follow_30m": no_follow,
        "risk_price": risk,
        "risk_valid": 1,
    }


def _coverage_features(
    closed_lots: pd.DataFrame,
    full_groups: dict[str, pd.DataFrame],
    legacy_groups: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, row in closed_lots.iterrows():
        vt_symbol = str(row.get("vt_symbol", ""))
        entry_day = _normalize_day(row.get("entry_date"))
        full_day = _day_for_symbol(full_groups, vt_symbol, entry_day)
        legacy_day = _day_for_symbol(legacy_groups, vt_symbol, entry_day)
        before_days, after_days, before_date, after_date = _nearest_dates(full_groups, vt_symbol, entry_day)
        has_exchange = int("." in vt_symbol)
        full_covered = int(not full_day.empty)
        legacy_covered = int(not legacy_day.empty)
        if not has_exchange:
            bucket = "invalid_vt_symbol"
        elif full_covered and legacy_covered:
            bucket = "full_and_legacy_covered"
        elif full_covered and not legacy_covered:
            bucket = "repaired_by_stage861_full"
        elif legacy_covered and not full_covered:
            bucket = "legacy_only_unexpected"
        else:
            bucket = "still_missing_stage861_entry_day"
        item = row.to_dict()
        item.update(
            {
                "entry_day": entry_day.date().isoformat() if not pd.isna(entry_day) else "",
                "vt_symbol_has_exchange": has_exchange,
                "stage861_entry_day_minute_bars": int(len(full_day)),
                "legacy_entry_day_minute_bars": int(len(legacy_day)),
                "stage861_covered": full_covered,
                "legacy_covered": legacy_covered,
                "coverage_bucket": bucket,
                "stage861_sources": ",".join(sorted(full_day.get("minute_source", pd.Series(dtype=str)).astype(str).unique())[:5])
                if not full_day.empty
                else "",
                "legacy_sources": ",".join(sorted(legacy_day.get("minute_source", pd.Series(dtype=str)).astype(str).unique())[:5])
                if not legacy_day.empty
                else "",
                "stage861_nearest_before_days": before_days,
                "stage861_nearest_after_days": after_days,
                "stage861_nearest_before_date": before_date,
                "stage861_nearest_after_date": after_date,
            }
        )
        item.update(_minute_features(row, full_day))
        rows.append(item)
    data = pd.DataFrame(rows)
    for column in ["realized_pnl", "r_multiple", "volume", "risk_price", "first_30m_directional_r", "first_30m_mfe_r", "first_30m_mae_r", "entry_day_mfe_r", "entry_day_mae_r"]:
        data[column] = pd.to_numeric(data.get(column), errors="coerce")
    data["positive_pnl"] = (data["realized_pnl"] > 0).astype(int)
    data["negative_pnl"] = (data["realized_pnl"] < 0).astype(int)
    data["entry_year"] = pd.to_datetime(data["entry_day"], errors="coerce").dt.year
    data["exit_date_ts"] = pd.to_datetime(data["exit_date"], errors="coerce")
    return data


def _coverage_stats(features: pd.DataFrame) -> pd.DataFrame:
    total_pnl = float(features["realized_pnl"].fillna(0.0).sum()) or np.nan
    total_positive = float(features.loc[features["realized_pnl"] > 0, "realized_pnl"].sum()) or np.nan
    total_negative = abs(float(features.loc[features["realized_pnl"] < 0, "realized_pnl"].sum())) or np.nan
    rows: list[dict[str, Any]] = []
    for bucket, group in features.groupby("coverage_bucket", dropna=False):
        pnl = float(group["realized_pnl"].fillna(0.0).sum())
        pos = float(group.loc[group["realized_pnl"] > 0, "realized_pnl"].sum())
        neg = float(group.loc[group["realized_pnl"] < 0, "realized_pnl"].sum())
        rows.append(
            {
                "coverage_bucket": str(bucket),
                "lots": int(len(group)),
                "products": int(group["product"].astype(str).nunique()) if "product" in group.columns else 0,
                "years": int(group["entry_year"].nunique()),
                "net_pnl": pnl,
                "net_pnl_share_pct": pnl / total_pnl * 100.0 if np.isfinite(total_pnl) else np.nan,
                "positive_pnl_sum": pos,
                "positive_pnl_share_pct": pos / total_positive * 100.0 if np.isfinite(total_positive) else np.nan,
                "negative_pnl_sum": neg,
                "negative_pnl_abs_share_pct": abs(neg) / total_negative * 100.0 if np.isfinite(total_negative) else np.nan,
                "median_first_30m_directional_r": float(group["first_30m_directional_r"].median()),
                "clean_lots": int(group["clean_continuation_30m"].fillna(0).sum()),
                "no_follow_lots": int(group["no_follow_30m"].fillna(0).sum()),
            }
        )
    rows.append(
        {
            "coverage_bucket": "ALL",
            "lots": int(len(features)),
            "products": int(features["product"].astype(str).nunique()) if "product" in features.columns else 0,
            "years": int(features["entry_year"].nunique()),
            "net_pnl": float(features["realized_pnl"].fillna(0.0).sum()),
            "net_pnl_share_pct": 100.0,
            "positive_pnl_sum": float(features.loc[features["realized_pnl"] > 0, "realized_pnl"].sum()),
            "positive_pnl_share_pct": 100.0,
            "negative_pnl_sum": float(features.loc[features["realized_pnl"] < 0, "realized_pnl"].sum()),
            "negative_pnl_abs_share_pct": 100.0,
            "median_first_30m_directional_r": float(features["first_30m_directional_r"].median()),
            "clean_lots": int(features["clean_continuation_30m"].fillna(0).sum()),
            "no_follow_lots": int(features["no_follow_30m"].fillna(0).sum()),
        }
    )
    return pd.DataFrame(rows)


def _year_stats(features: pd.DataFrame) -> pd.DataFrame:
    data = features.copy()
    rows: list[dict[str, Any]] = []
    for year, group in data.groupby("entry_year", dropna=False):
        rows.append(
            {
                "entry_year": int(year) if not pd.isna(year) else 0,
                "lots": int(len(group)),
                "stage861_covered_lots": int(group["stage861_covered"].sum()),
                "legacy_covered_lots": int(group["legacy_covered"].sum()),
                "repaired_by_stage861_lots": int(group["coverage_bucket"].eq("repaired_by_stage861_full").sum()),
                "still_missing_lots": int(group["coverage_bucket"].eq("still_missing_stage861_entry_day").sum()),
                "net_pnl": float(group["realized_pnl"].fillna(0.0).sum()),
                "stage861_covered_net_pnl": float(group.loc[group["stage861_covered"].eq(1), "realized_pnl"].fillna(0.0).sum()),
                "still_missing_net_pnl": float(group.loc[group["coverage_bucket"].eq("still_missing_stage861_entry_day"), "realized_pnl"].fillna(0.0).sum()),
            }
        )
    return pd.DataFrame(rows).sort_values("entry_year")


def _contribution_curve(features: pd.DataFrame) -> pd.DataFrame:
    data = features.copy()
    data["exit_date_ts"] = pd.to_datetime(data["exit_date"], errors="coerce")
    data = data.dropna(subset=["exit_date_ts"]).sort_values(["exit_date_ts", "lot_id"])
    rows: list[dict[str, Any]] = []
    buckets = sorted(data["coverage_bucket"].astype(str).unique())
    cumulative = {bucket: 0.0 for bucket in buckets}
    cumulative["ALL"] = 0.0
    for _, row in data.iterrows():
        bucket = str(row["coverage_bucket"])
        pnl = _safe_float(row.get("realized_pnl"), 0.0)
        cumulative[bucket] += pnl
        cumulative["ALL"] += pnl
        item = {
            "date": pd.Timestamp(row["exit_date_ts"]).date().isoformat(),
            "lot_id": row.get("lot_id"),
            "vt_symbol": row.get("vt_symbol"),
            "coverage_bucket": bucket,
            "realized_pnl": pnl,
        }
        for key, value in cumulative.items():
            item[f"cum_pnl_{key}"] = value
        rows.append(item)
    return pd.DataFrame(rows)


def _plot_path(curve: pd.DataFrame) -> None:
    data = curve.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce", format="mixed")
    fig, axes = plt.subplots(3, 1, figsize=(18, 11), sharex=True, constrained_layout=True)
    axes[0].plot(data["date"], data["account_equity"], color="#2563eb", label="official C9/15w")
    axes[1].plot(data["date"], data["drawdown_pct"], color="#dc2626", label="drawdown")
    axes[2].plot(data["date"], data["broker10_margin_to_equity_pct"], color="#0f766e", label="broker10")
    axes[2].axhline(100.0, color="#dc2626", linestyle="--", linewidth=0.9)
    axes[0].set_title("Stage010 official C9/15w equity")
    axes[1].set_title("Official drawdown")
    axes[2].set_title("Official broker10 margin to equity pct")
    for ax in axes:
        ax.grid(True, alpha=0.25)
        ax.legend(loc="best")
    fig.savefig(PATH_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_coverage(year_stats: pd.DataFrame) -> None:
    data = year_stats.copy()
    years = data["entry_year"].astype(int).astype(str)
    x = np.arange(len(data))
    fig, axes = plt.subplots(2, 1, figsize=(18, 10), sharex=True, constrained_layout=True)
    covered = pd.to_numeric(data["stage861_covered_lots"], errors="coerce").fillna(0)
    repaired = pd.to_numeric(data["repaired_by_stage861_lots"], errors="coerce").fillna(0)
    missing = pd.to_numeric(data["still_missing_lots"], errors="coerce").fillna(0)
    legacy = pd.to_numeric(data["legacy_covered_lots"], errors="coerce").fillna(0)
    axes[0].bar(x, covered, color="#2563eb", label="Stage861 covered lots")
    axes[0].bar(x, missing, bottom=covered, color="#dc2626", label="Still missing lots")
    axes[0].plot(x, legacy, color="#f59e0b", marker="o", linewidth=1.2, label="Legacy covered lots")
    axes[0].bar(x, repaired, color="#16a34a", alpha=0.45, label="Repaired by Stage861 subset")
    axes[0].set_title("Entry-day minute coverage by entry year")
    axes[0].legend(loc="best")
    axes[0].grid(True, axis="y", alpha=0.25)

    axes[1].bar(x, pd.to_numeric(data["net_pnl"], errors="coerce").fillna(0), color="#64748b", label="all net pnl")
    axes[1].bar(x, pd.to_numeric(data["still_missing_net_pnl"], errors="coerce").fillna(0), color="#dc2626", alpha=0.65, label="still missing net pnl")
    axes[1].axhline(0.0, color="#111827", linewidth=0.8)
    axes[1].set_title("Coverage bucket PnL by entry year")
    axes[1].legend(loc="best")
    axes[1].grid(True, axis="y", alpha=0.25)
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(years, rotation=0)
    fig.savefig(COVERAGE_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_contribution(contrib: pd.DataFrame) -> None:
    if contrib.empty:
        return
    data = contrib.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    fig, ax = plt.subplots(figsize=(18, 7), constrained_layout=True)
    colors = {
        "cum_pnl_ALL": "#111827",
        "cum_pnl_full_and_legacy_covered": "#2563eb",
        "cum_pnl_repaired_by_stage861_full": "#16a34a",
        "cum_pnl_still_missing_stage861_entry_day": "#dc2626",
        "cum_pnl_invalid_vt_symbol": "#64748b",
        "cum_pnl_legacy_only_unexpected": "#f59e0b",
    }
    for column in [col for col in data.columns if col.startswith("cum_pnl_")]:
        ax.plot(data["date"], pd.to_numeric(data[column], errors="coerce"), label=column.replace("cum_pnl_", ""), color=colors.get(column), linewidth=1.3)
    ax.axhline(0.0, color="#111827", linewidth=0.8)
    ax.set_title("Closed-lot cumulative realized PnL by minute coverage bucket")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best")
    fig.savefig(CONTRIBUTION_CHART_OUT, dpi=170)
    plt.close(fig)


def _select_atlas_rows(features: pd.DataFrame) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    repaired = features[features["coverage_bucket"].eq("repaired_by_stage861_full")].copy()
    missing = features[features["coverage_bucket"].eq("still_missing_stage861_entry_day")].copy()
    covered_no_follow = features[(features["stage861_covered"].eq(1)) & (features["no_follow_30m"].eq(1))].copy()
    for frame in [repaired.nlargest(5, "realized_pnl"), repaired.nsmallest(5, "realized_pnl")]:
        if not frame.empty:
            parts.append(frame)
    if not missing.empty:
        parts.append(missing.nlargest(5, "realized_pnl"))
        parts.append(missing.nsmallest(5, "realized_pnl"))
    if not covered_no_follow.empty:
        parts.append(covered_no_follow.nlargest(5, "realized_pnl"))
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, ignore_index=True, sort=False).drop_duplicates(["lot_id"]).head(MAX_ATLAS_ROWS)


def _plot_atlas(features: pd.DataFrame, full_groups: dict[str, pd.DataFrame]) -> tuple[list[Path], pd.DataFrame]:
    selected = _select_atlas_rows(features)
    if selected.empty:
        return [], pd.DataFrame()
    pages = int(math.ceil(len(selected) / PER_PAGE))
    paths: list[Path] = []
    manifest: list[dict[str, Any]] = []
    for page in range(1, pages + 1):
        part = selected.iloc[(page - 1) * PER_PAGE : page * PER_PAGE].copy()
        fig, axes = plt.subplots(len(part), 1, figsize=(18, max(4.2, 3.4 * len(part))), constrained_layout=True)
        axes_list = list(np.atleast_1d(axes))
        for ax, (_, row) in zip(axes_list, part.iterrows(), strict=False):
            vt_symbol = str(row.get("vt_symbol"))
            entry_day = _normalize_day(row.get("entry_date"))
            day = _day_for_symbol(full_groups, vt_symbol, entry_day)
            if day.empty:
                ax.axis("off")
                ax.text(
                    0.5,
                    0.5,
                    (
                        f"missing Stage861 entry-day minutes\n{vt_symbol} {entry_day.date() if not pd.isna(entry_day) else ''}\n"
                        f"nearest before {row.get('stage861_nearest_before_date', '')} ({row.get('stage861_nearest_before_days', '')}d)\n"
                        f"nearest after {row.get('stage861_nearest_after_date', '')} ({row.get('stage861_nearest_after_days', '')}d)"
                    ),
                    ha="center",
                    va="center",
                    fontsize=10,
                )
            else:
                plot_day = day.head(520).reset_index(drop=True)
                s008.s825._plot_candles(ax, plot_day)
                entry = _safe_float(row.get("entry_price"))
                risk = _safe_float(row.get("risk_price"))
                direction = str(row.get("direction"))
                if np.isfinite(entry):
                    ax.axhline(entry, color="#2563eb", linewidth=0.9, label="entry")
                if np.isfinite(entry) and np.isfinite(risk):
                    sign = -1 if direction == "short" else 1
                    ax.axhline(entry + sign * 0.5 * risk, color="#16a34a", linestyle="--", linewidth=0.8, label="+0.5R")
                    ax.axhline(entry - sign * 0.5 * risk, color="#dc2626", linestyle="--", linewidth=0.8, label="-0.5R")
                if len(plot_day) > FIRST_N_BARS:
                    ax.axvline(FIRST_N_BARS - 1, color="#64748b", linewidth=1.0, label="30m")
                ticks = np.linspace(0, len(plot_day) - 1, num=min(8, len(plot_day)), dtype=int)
                ax.set_xticks(ticks)
                ax.set_xticklabels([pd.Timestamp(plot_day.loc[pos, "bar_datetime"]).strftime("%H:%M") for pos in ticks], fontsize=7)
                handles, labels = ax.get_legend_handles_labels()
                if handles:
                    dedup = dict(zip(labels, handles))
                    ax.legend(dedup.values(), dedup.keys(), loc="best", fontsize=7)
                ax.grid(True, alpha=0.18)
            ax.set_title(
                (
                    f"lot{row.get('lot_id')} {vt_symbol} {row.get('direction')} {row.get('entry_day')} "
                    f"{row.get('coverage_bucket')} pnl={_safe_float(row.get('realized_pnl'), 0):,.0f} "
                    f"dir30={_safe_float(row.get('first_30m_directional_r'), 0):.2f}"
                ),
                fontsize=8.2,
                loc="left",
            )
            manifest.append(
                {
                    "page": page,
                    "lot_id": row.get("lot_id"),
                    "vt_symbol": vt_symbol,
                    "entry_day": row.get("entry_day"),
                    "direction": row.get("direction"),
                    "coverage_bucket": row.get("coverage_bucket"),
                    "stage861_entry_day_minute_bars": row.get("stage861_entry_day_minute_bars"),
                    "legacy_entry_day_minute_bars": row.get("legacy_entry_day_minute_bars"),
                    "realized_pnl": _safe_float(row.get("realized_pnl")),
                    "first_30m_directional_r": _safe_float(row.get("first_30m_directional_r")),
                }
            )
        fig.suptitle("Stage010 authoritative Stage861 minute coverage atlas", fontsize=12)
        path = Path(str(ATLAS_TEMPLATE).format(page=page))
        fig.savefig(path, dpi=170)
        plt.close(fig)
        paths.append(path)
    return paths, pd.DataFrame(manifest)


def _decision(summary: dict[str, Any], coverage_stats: pd.DataFrame, features: pd.DataFrame, atlas_paths: list[Path]) -> dict[str, Any]:
    stage861_covered = int(features["stage861_covered"].sum())
    legacy_covered = int(features["legacy_covered"].sum())
    repaired = int(features["coverage_bucket"].eq("repaired_by_stage861_full").sum())
    still_missing = int(features["coverage_bucket"].eq("still_missing_stage861_entry_day").sum())
    still_missing_pnl = float(features.loc[features["coverage_bucket"].eq("still_missing_stage861_entry_day"), "realized_pnl"].fillna(0.0).sum())
    if still_missing == 0:
        label = "stage010_stage861_full_minute_coverage_ready"
    elif repaired > 0 and stage861_covered > legacy_covered:
        label = "stage010_stage861_improves_coverage_but_missing_tail_remains"
    else:
        label = "stage010_minute_coverage_still_blocked"
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "decision": label,
        "official_summary": summary,
        "coverage": {
            "closed_lots": int(len(features)),
            "stage861_covered_lots": stage861_covered,
            "legacy_covered_lots": legacy_covered,
            "repaired_by_stage861_lots": repaired,
            "still_missing_stage861_lots": still_missing,
            "still_missing_stage861_net_pnl": still_missing_pnl,
            "stage861_coverage_pct": stage861_covered / len(features) * 100.0 if len(features) else 0.0,
            "legacy_coverage_pct": legacy_covered / len(features) * 100.0 if len(features) else 0.0,
        },
        "coverage_stats": coverage_stats.to_dict(orient="records"),
        "outputs": {
            "summary": str(SUMMARY_OUT),
            "official_curve": str(CURVE_OUT),
            "coverage_features": str(COVERAGE_FEATURES_OUT),
            "coverage_stats": str(COVERAGE_STATS_OUT),
            "year_coverage_stats": str(YEAR_COVERAGE_STATS_OUT),
            "path_chart": str(PATH_CHART_OUT),
            "coverage_chart": str(COVERAGE_CHART_OUT),
            "contribution_chart": str(CONTRIBUTION_CHART_OUT),
            "atlas_manifest": str(ATLAS_MANIFEST_OUT),
            "report": str(REPORT_OUT),
        },
        "external_research_judgment": (
            "Data-quality and lookahead-bias references support treating minute coverage as a hard prerequisite. "
            "A minute execution rule should not be promoted if key entry-day bars are missing or fabricated."
        ),
        "overfit_reflection_before": (
            "No: Stage010 does not create or tune a trading rule. It audits whether the minute dataset can support any "
            "future entry-day rule without silent coverage bias."
        ),
        "continue_value_before": (
            "Yes: Stage007 found important missing-minute right-tail samples under legacy minute sources; after Stage008/009 "
            "failed, verifying authoritative coverage is the highest-value next prerequisite."
        ),
        "overfit_reflection_after": (
            "No: the output is a coverage ledger, official path chart, and atlas. No product, year, direction, or parameter "
            "branch is used to alter trades."
        ),
        "continue_value_after": "",
        "order_api_called": False,
        "ctp_connected": False,
    }


def _write_report(
    summary_df: pd.DataFrame,
    coverage_stats: pd.DataFrame,
    year_stats: pd.DataFrame,
    atlas_paths: list[Path],
    decision: dict[str, Any],
) -> None:
    view_cols = [
        "arm",
        "end_equity",
        "total_return_pct",
        "max_dd_pct",
        "sharpe",
        "total_slippage",
        "total_trade_count",
        "nonzero_daily_win_rate_pct",
        "max_broker10_margin_to_equity_pct",
        "days_over_100pct",
        "stop_retry_event_count",
        "broker10_cap_event_count",
    ]
    decision["continue_value_after"] = (
        "Yes for coverage repair/audit if Stage861 materially improves entry-day coverage; only after coverage is accepted "
        "should future work return to entry-time structure. No trading promotion is implied by this stage."
        if decision["decision"] != "stage010_minute_coverage_still_blocked"
        else "Limited: minute-entry rules remain blocked until missing right-tail entry days are repaired from authoritative sources."
    )
    lines = [
        "# Stage010 权威分钟覆盖审计",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M')}`",
        f"- line_id：`{LINE_ID}`",
        f"- 当前官方正式版本：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`",
        "- 阶段性质：只读数据覆盖审计；复跑官方 C9/15w，不新增交易规则、不改正式配置、不连接 CTP、不调用订单 API。",
        "",
        "## 外部调研与判断",
        "",
        "- Freqtrade lookahead-analysis 文档强调回测框架容易预先装载完整 dataframe，必须检查策略是否使用未来信息。",
        "- pysystemtrade 文档和仓库把期货数据存储、回测与生产执行分层处理，说明数据层是系统交易工程的独立前置资产。",
        "- Concretum 的数据质量案例显示，同一策略在不同数据源上可能出现显著差异，因此分钟规则前必须先审计源覆盖和缺口。",
        "- 我的判断：Stage008/009 连续失败后，不应继续调分钟硬退出；先确认 Stage861 full minute 源是否修复 Stage007 的缺口，否则任何分钟规则都会带覆盖偏差。",
        "",
        "## Official Path",
        "",
        _md_table(summary_df[view_cols], max_rows=5),
        "",
        "## Coverage Stats",
        "",
        _md_table(coverage_stats, max_rows=20),
        "",
        "## Year Coverage",
        "",
        _md_table(year_stats, max_rows=30),
        "",
        "## Visual Outputs",
        "",
        f"- official path chart：`{PATH_CHART_OUT}`",
        f"- coverage chart：`{COVERAGE_CHART_OUT}`",
        f"- contribution chart：`{CONTRIBUTION_CHART_OUT}`",
        *[f"- minute atlas：`{path}`" for path in atlas_paths],
        "",
        "## Decision",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- 覆盖摘要：`{decision['coverage']}`",
        f"- 过拟合反思：`{decision['overfit_reflection_after']}`",
        f"- 继续价值：`{decision['continue_value_after']}`",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print("[stage010] loading metadata and minute sources", flush=True)
    metadata = s008.s513._metadata()
    vt_symbols = set(str(item) for item in metadata["vt_symbols"])
    full_minute_bars = s008.s928._load_stage861_full_minute_bars(vt_symbols)
    legacy_minute_bars = s008.s825._load_minute_bars(vt_symbols)
    full_groups = s008.s825._minute_groups(full_minute_bars)
    legacy_groups = s008.s825._minute_groups(legacy_minute_bars)
    s008.s847.s827._GLOBAL_MINUTE_BY_SYMBOL = full_groups

    print("[stage010] replaying official C9/15w", flush=True)
    profile, combined, frames = _run_official(metadata)
    summary_row = _summary(profile, combined, frames)
    summary_df = pd.DataFrame([summary_row])
    curve = _curve(combined, profile)
    closed_lots = s008.s719._build_closed_lots(
        frames.get("trades", pd.DataFrame()).copy(),
        frames.get("entry_risk", pd.DataFrame()).copy(),
        frames.get("entry_candidates", pd.DataFrame()).copy(),
        metadata,
    )
    if closed_lots.empty:
        raise RuntimeError("official closed lots are empty")
    for column in ["entry_date", "exit_date"]:
        closed_lots[column] = pd.to_datetime(closed_lots[column], errors="coerce").dt.normalize()
    coverage_features = _coverage_features(closed_lots, full_groups, legacy_groups)
    coverage_stats = _coverage_stats(coverage_features)
    year_stats = _year_stats(coverage_features)
    contrib = _contribution_curve(coverage_features)
    _plot_path(curve)
    _plot_coverage(year_stats)
    _plot_contribution(contrib)
    atlas_paths, atlas_manifest = _plot_atlas(coverage_features, full_groups)
    decision = _decision(summary_row, coverage_stats, coverage_features, atlas_paths)
    _write_report(summary_df, coverage_stats, year_stats, atlas_paths, decision)

    summary_df.to_csv(SUMMARY_OUT, index=False, encoding="utf-8-sig")
    curve.to_csv(CURVE_OUT, index=False, encoding="utf-8-sig")
    frames.get("trades", pd.DataFrame()).to_csv(TRADES_OUT, index=False, encoding="utf-8-sig")
    frames.get("entry_risk", pd.DataFrame()).to_csv(ENTRY_RISK_OUT, index=False, encoding="utf-8-sig")
    frames.get("entry_candidates", pd.DataFrame()).to_csv(ENTRY_CANDIDATES_OUT, index=False, encoding="utf-8-sig")
    frames.get("trade_events", pd.DataFrame()).to_csv(TRADE_EVENTS_OUT, index=False, encoding="utf-8-sig")
    frames.get("intraday_events", pd.DataFrame()).to_csv(INTRADAY_EVENTS_OUT, index=False, encoding="utf-8-sig")
    closed_lots.to_csv(CLOSED_LOTS_OUT, index=False, encoding="utf-8-sig")
    coverage_features.to_csv(COVERAGE_FEATURES_OUT, index=False, encoding="utf-8-sig")
    coverage_stats.to_csv(COVERAGE_STATS_OUT, index=False, encoding="utf-8-sig")
    year_stats.to_csv(YEAR_COVERAGE_STATS_OUT, index=False, encoding="utf-8-sig")
    contrib.to_csv(CONTRIBUTION_CURVE_OUT, index=False, encoding="utf-8-sig")
    atlas_manifest.to_csv(ATLAS_MANIFEST_OUT, index=False, encoding="utf-8-sig")
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"[stage010] decision={decision['decision']}", flush=True)
    print(f"[stage010] coverage={decision['coverage']}", flush=True)
    print(f"[stage010] report={REPORT_OUT}", flush=True)


if __name__ == "__main__":
    main()
