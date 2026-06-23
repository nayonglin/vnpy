from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
import re
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage054"
MODEL_TAG = "stage054_c9_reentry_reclaim_quality_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage054_c9_minrisk_reentry_reclaim_quality_audit"

OFFICIAL_ARM = "A_official_stage847_c9_15w"
INITIAL_CAPITAL = 150_000.0
STOP_RETRY_R = 0.5
LOW_QUALITY_REENTRY_BARS = 120
LOW_QUALITY_EXTRA_ADVERSE_R = 0.5
FAST_RECLAIM_BARS = 30
MAX_ATLAS_ROWS = 12
ATLAS_PER_PAGE = 4

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
TOOL_DIR = SCRIPT_PATH.parent
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
for item in [str(TOOL_DIR), str(EXAMPLE_DIR)]:
    if item not in sys.path:
        sys.path.insert(0, item)

import stage008_no_follow_reduce_true_engine as s008
import stage038_order_event_replay_prototype_audit as s038
from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
STAGE010_DIR = LINE_DIR / "outputs" / "stage010_authoritative_minute_coverage_audit"
OUTPUT_DIR = LINE_DIR / "outputs" / "stage054_c9_reentry_reclaim_quality_audit"

OFFICIAL_CURVE_IN = (
    STAGE010_DIR
    / "qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_official_curve_"
    "stage010_authoritative_minute_coverage_audit_v1.csv"
)
OFFICIAL_TRADES_IN = (
    STAGE010_DIR
    / "qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_official_trades_"
    "stage010_authoritative_minute_coverage_audit_v1.csv"
)
OFFICIAL_CLOSED_LOTS_IN = (
    STAGE010_DIR
    / "qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_official_closed_lots_"
    "stage010_authoritative_minute_coverage_audit_v1.csv"
)
OFFICIAL_INTRADAY_EVENTS_IN = (
    STAGE010_DIR
    / "qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_official_intraday_events_"
    "stage010_authoritative_minute_coverage_audit_v1.csv"
)

FEATURES_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_features_{MODEL_TAG}.csv"
BUCKET_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_summary_{MODEL_TAG}.csv"
UPPER_CURVE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_upper_bound_curve_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
ATLAS_MANIFEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_upper_bound_path_chart_{MODEL_TAG}.png"
SCATTER_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_reentry_quality_scatter_{MODEL_TAG}.png"
BUCKET_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_pnl_chart_{MODEL_TAG}.png"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_page{{page:03d}}_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        if not np.isfinite(value):
            return None
        return float(value)
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if np.isfinite(out) else default


def _safe_int(value: Any, default: int = -1) -> int:
    number = _safe_float(value)
    if not np.isfinite(number):
        return default
    return int(number)


def _time_text(value: Any) -> str:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return ""
    return pd.Timestamp(ts).strftime("%Y-%m-%dT%H:%M:%S")


def _normalize_day(value: Any) -> pd.Timestamp:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return pd.NaT
    ts = pd.Timestamp(ts)
    if ts.tzinfo is not None:
        ts = ts.tz_convert(None)
    return ts.normalize()


def _direction_sign(direction: Any) -> int:
    text = str(direction).lower()
    return 1 if text == "long" else -1


def _normalize_product(vt_symbol: Any) -> str:
    symbol = "" if pd.isna(vt_symbol) else str(vt_symbol)
    if "." in symbol:
        code, exchange = symbol.split(".", 1)
        match = re.match(r"^([A-Za-z]+)", code)
        if match:
            return f"{match.group(1)}.{exchange}"
    match = re.match(r"^([A-Za-z]+)", symbol)
    return match.group(1) if match else symbol


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    display = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    for column in display.columns:
        if pd.api.types.is_float_dtype(display[column]):
            display[column] = display[column].map(lambda value: "" if pd.isna(value) else f"{value:.4f}")
    lines = [
        "| " + " | ".join(str(column) for column in display.columns) + " |",
        "| " + " | ".join(["---"] * len(display.columns)) + " |",
    ]
    for _, row in display.iterrows():
        lines.append("| " + " | ".join(str(row[column]) for column in display.columns) + " |")
    return "\n".join(lines)


def _fmt(value: Any, digits: int = 4) -> str:
    number = _safe_float(value)
    if not np.isfinite(number):
        return "NA"
    return f"{number:.{digits}f}"


def _equity_metrics(equity: pd.Series, date: pd.Series | None = None) -> dict[str, Any]:
    equity = pd.to_numeric(equity, errors="coerce").astype(float).reset_index(drop=True)
    running_max = equity.cummax()
    drawdown_pct = (equity / running_max - 1.0) * 100.0
    returns = equity.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    ret_std = returns.std(ddof=0)
    sharpe = float(returns.mean() / ret_std * np.sqrt(252.0)) if ret_std and ret_std > 0 else np.nan
    trough_idx = int(drawdown_pct.idxmin())
    metrics: dict[str, Any] = {
        "end_equity": float(equity.iloc[-1]),
        "total_return_pct": float((equity.iloc[-1] / INITIAL_CAPITAL - 1.0) * 100.0),
        "max_dd_pct": float(drawdown_pct.min()),
        "sharpe": sharpe,
    }
    if date is not None:
        dates = pd.to_datetime(date, errors="coerce").reset_index(drop=True)
        metrics["max_dd_date"] = dates.iloc[trough_idx].strftime("%Y-%m-%d")
    return metrics


def _load_official_curve() -> pd.DataFrame:
    curve = _read_csv(OFFICIAL_CURVE_IN)
    curve = curve[curve["arm"].astype(str).eq(OFFICIAL_ARM)].copy()
    if curve.empty:
        raise RuntimeError(f"official curve arm is empty: {OFFICIAL_ARM}")
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    curve = curve.sort_values("date").reset_index(drop=True)
    curve["official_drawdown_pct"] = (
        pd.to_numeric(curve["account_equity"], errors="coerce") / pd.to_numeric(curve["account_equity"], errors="coerce").cummax()
        - 1.0
    ) * 100.0
    return curve


def _official_metrics(curve: pd.DataFrame) -> dict[str, Any]:
    metrics = _equity_metrics(curve["account_equity"], curve["date"])
    nonzero = curve[pd.to_numeric(curve["net_pnl"], errors="coerce").ne(0)]
    metrics.update(
        {
            "total_slippage": float(pd.to_numeric(curve["slippage"], errors="coerce").sum()),
            "total_trade_count": float(pd.to_numeric(curve["trade_count"], errors="coerce").sum()),
            "win_rate_pct": float((pd.to_numeric(nonzero["net_pnl"], errors="coerce") > 0).mean() * 100.0)
            if len(nonzero)
            else np.nan,
            "broker10_peak_pct": float(pd.to_numeric(curve["broker10_margin_to_equity_pct"], errors="coerce").max()),
        }
    )
    return metrics


def _load_minute_groups(events: pd.DataFrame) -> dict[str, pd.DataFrame]:
    request = events[["vt_symbol"]].dropna().drop_duplicates().copy()
    return s038._load_minute_groups(request)


def _event_day_bars(row: pd.Series, minute_groups: dict[str, pd.DataFrame]) -> pd.DataFrame:
    bars = minute_groups.get(str(row.get("vt_symbol", "")), pd.DataFrame())
    if bars.empty:
        return pd.DataFrame()
    day = _normalize_day(row.get("datetime"))
    bar_dates = pd.to_datetime(bars["bar_date"], errors="coerce").dt.normalize()
    data = bars[bar_dates.eq(day)].copy()
    if data.empty:
        return pd.DataFrame()
    return data.sort_values("bar_datetime").reset_index(drop=True)


def _map_reentry_lots(events: pd.DataFrame, trades: pd.DataFrame, lots: pd.DataFrame) -> pd.DataFrame:
    trades = trades.copy()
    lots = lots.copy()
    for frame, columns in [
        (trades, ["price", "volume"]),
        (lots, ["entry_price", "exit_price", "volume", "realized_pnl"]),
    ]:
        for column in columns:
            if column in frame.columns:
                frame[column] = pd.to_numeric(frame[column], errors="coerce")
    rows: list[dict[str, Any]] = []
    for _, row in events.iterrows():
        initial_trade_id = str(row.get("trade_id", ""))
        initial = trades[trades["trade_id"].astype(str).eq(initial_trade_id)]
        initial_order_id = str(initial.iloc[0]["order_id"]) if not initial.empty else ""
        prefix = f"{initial_order_id}.stage847_c9."
        reentry_trades = trades[
            trades["order_id"].astype(str).eq(f"{prefix}2")
            & trades["offset"].astype(str).str.lower().eq("open")
        ].copy()
        reentry_ids = reentry_trades["trade_id"].astype(str).tolist()
        reentry_lots = lots[lots["open_trade_id"].astype(str).isin(reentry_ids)].copy()
        initial_lots = lots[lots["open_trade_id"].astype(str).eq(initial_trade_id)].copy()
        rows.append(
            {
                "trade_id": initial_trade_id,
                "initial_order_id": initial_order_id,
                "reentry_open_trade_ids": ",".join(reentry_ids),
                "reentry_open_trade_count": int(len(reentry_trades)),
                "reentry_lot_count": int(len(reentry_lots)),
                "reentry_lot_volume": float(reentry_lots["volume"].sum()) if "volume" in reentry_lots else 0.0,
                "reentry_lot_pnl": float(reentry_lots["realized_pnl"].sum()) if "realized_pnl" in reentry_lots else 0.0,
                "reentry_positive_pnl": float(reentry_lots["realized_pnl"].clip(lower=0).sum())
                if "realized_pnl" in reentry_lots
                else 0.0,
                "reentry_negative_pnl_abs": float((-reentry_lots["realized_pnl"].clip(upper=0)).sum())
                if "realized_pnl" in reentry_lots
                else 0.0,
                "reentry_exit_date": pd.to_datetime(reentry_lots["exit_date"], errors="coerce").max()
                if "exit_date" in reentry_lots and len(reentry_lots)
                else pd.NaT,
                "initial_stop_lot_count": int(len(initial_lots)),
                "initial_stop_pnl": float(initial_lots["realized_pnl"].sum()) if "realized_pnl" in initial_lots else 0.0,
            }
        )
    return pd.DataFrame(rows)


def _path_quality(row: pd.Series, minute_groups: dict[str, pd.DataFrame]) -> dict[str, Any]:
    day = _event_day_bars(row, minute_groups)
    stop_idx = _safe_int(row.get("first_stop_bar_index"))
    reentry_idx = _safe_int(row.get("reentry_bar_index"))
    entry_price = _safe_float(row.get("entry_price"))
    stop_price = _safe_float(row.get("stop_price"))
    risk_price = _safe_float(row.get("risk_price"))
    direction = str(row.get("direction", "")).lower()
    base = {
        "stage861_day_ready": int(not day.empty),
        "minute_bar_count": int(len(day)),
        "stop_to_reentry_bars": np.nan,
        "stop_to_reentry_elapsed_minutes": np.nan,
        "extra_adverse_after_stop_r": np.nan,
        "reclaim_range_r": np.nan,
        "recovery_efficiency": np.nan,
        "post_stop_min_price": np.nan,
        "post_stop_max_price": np.nan,
        "quality_bucket": "not_reentered_or_unready",
        "low_quality_reentry": 0,
    }
    if day.empty or stop_idx < 0 or reentry_idx < 0 or reentry_idx <= stop_idx:
        return base
    if not np.isfinite(entry_price) or not np.isfinite(stop_price) or not np.isfinite(risk_price) or risk_price <= 0:
        base["quality_bucket"] = "invalid_risk"
        return base
    if reentry_idx >= len(day):
        base["quality_bucket"] = "minute_index_out_of_range"
        return base

    segment = day.iloc[stop_idx : reentry_idx + 1].copy()
    if segment.empty:
        return base
    highs = pd.to_numeric(segment["high"], errors="coerce")
    lows = pd.to_numeric(segment["low"], errors="coerce")
    post_stop_min = float(lows.min())
    post_stop_max = float(highs.max())
    sign = _direction_sign(direction)
    if direction == "long":
        extra_adverse_r = max(0.0, (stop_price - post_stop_min) / risk_price)
    else:
        extra_adverse_r = max(0.0, (post_stop_max - stop_price) / risk_price)
    stop_to_reentry_bars = reentry_idx - stop_idx
    stop_time = pd.to_datetime(row.get("first_stop_time"), errors="coerce")
    reentry_time = pd.to_datetime(row.get("reentry_time"), errors="coerce")
    elapsed_minutes = (
        float((pd.Timestamp(reentry_time) - pd.Timestamp(stop_time)).total_seconds() / 60.0)
        if pd.notna(stop_time) and pd.notna(reentry_time)
        else np.nan
    )
    reclaim_range_r = abs(entry_price - stop_price) / risk_price
    path_distance_r = reclaim_range_r + extra_adverse_r
    recovery_efficiency = reclaim_range_r / path_distance_r if path_distance_r > 0 else np.nan
    if stop_to_reentry_bars >= LOW_QUALITY_REENTRY_BARS or extra_adverse_r >= LOW_QUALITY_EXTRA_ADVERSE_R:
        quality_bucket = "slow_or_deep_reclaim"
        low_quality = 1
    elif stop_to_reentry_bars <= FAST_RECLAIM_BARS and extra_adverse_r < 0.25:
        quality_bucket = "fast_clean_reclaim"
        low_quality = 0
    else:
        quality_bucket = "normal_reclaim"
        low_quality = 0
    base.update(
        {
            "stop_to_reentry_bars": float(stop_to_reentry_bars),
            "stop_to_reentry_elapsed_minutes": elapsed_minutes,
            "extra_adverse_after_stop_r": float(extra_adverse_r),
            "reclaim_range_r": float(reclaim_range_r),
            "recovery_efficiency": float(recovery_efficiency),
            "post_stop_min_price": post_stop_min,
            "post_stop_max_price": post_stop_max,
            "quality_bucket": quality_bucket,
            "low_quality_reentry": low_quality,
        }
    )
    return base


def _build_features() -> pd.DataFrame:
    intraday = _read_csv(OFFICIAL_INTRADAY_EVENTS_IN)
    trades = _read_csv(OFFICIAL_TRADES_IN)
    lots = _read_csv(OFFICIAL_CLOSED_LOTS_IN)
    events = intraday[
        pd.to_numeric(intraday.get("retry_reentered"), errors="coerce").fillna(0).eq(1)
        & intraday["first_stop_time"].notna()
        & intraday["reentry_time"].notna()
    ].copy()
    if events.empty:
        raise RuntimeError("no official C9 reentry events found")
    for column in [
        "entry_price",
        "stop_price",
        "progress_price",
        "risk_price",
        "volume",
        "first_stop_bar_index",
        "reentry_bar_index",
        "retry_failed_bar_index",
        "retry_reentered",
        "retry_failed",
    ]:
        if column in events.columns:
            events[column] = pd.to_numeric(events[column], errors="coerce")
    events["datetime_ts"] = pd.to_datetime(events["datetime"], errors="coerce")
    events["entry_year"] = events["datetime_ts"].dt.year.astype("Int64")
    events["normalized_product"] = events["vt_symbol"].map(_normalize_product)
    minute_groups = _load_minute_groups(events)
    quality_rows = [_path_quality(row, minute_groups) for _, row in events.iterrows()]
    mapped = _map_reentry_lots(events, trades, lots)
    features = pd.concat(
        [events.reset_index(drop=True), pd.DataFrame(quality_rows), mapped.drop(columns=["trade_id"]).reset_index(drop=True)],
        axis=1,
    )
    features["reentry_exit_day"] = pd.to_datetime(features["reentry_exit_date"], errors="coerce").dt.normalize()
    features["reentry_pnl_positive"] = pd.to_numeric(features["reentry_lot_pnl"], errors="coerce").clip(lower=0)
    features["reentry_pnl_negative_abs"] = -pd.to_numeric(features["reentry_lot_pnl"], errors="coerce").clip(upper=0)
    features["reentry_lot_missing"] = pd.to_numeric(features["reentry_lot_count"], errors="coerce").fillna(0).eq(0).astype(int)
    return features


def _bucket_summary(features: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for bucket, group in features.groupby("quality_bucket", dropna=False):
        rows.append(
            {
                "quality_bucket": bucket,
                "event_count": int(len(group)),
                "product_count": int(group["normalized_product"].nunique()),
                "year_count": int(group["entry_year"].nunique()),
                "retry_failed_count": int(pd.to_numeric(group["retry_failed"], errors="coerce").fillna(0).sum()),
                "reentry_lot_count": int(pd.to_numeric(group["reentry_lot_count"], errors="coerce").fillna(0).sum()),
                "reentry_lot_volume": float(pd.to_numeric(group["reentry_lot_volume"], errors="coerce").fillna(0).sum()),
                "initial_stop_pnl": float(pd.to_numeric(group["initial_stop_pnl"], errors="coerce").sum()),
                "reentry_lot_pnl": float(pd.to_numeric(group["reentry_lot_pnl"], errors="coerce").sum()),
                "reentry_positive_pnl": float(pd.to_numeric(group["reentry_positive_pnl"], errors="coerce").sum()),
                "reentry_negative_pnl_abs": float(pd.to_numeric(group["reentry_negative_pnl_abs"], errors="coerce").sum()),
                "median_stop_to_reentry_bars": float(pd.to_numeric(group["stop_to_reentry_bars"], errors="coerce").median()),
                "median_extra_adverse_after_stop_r": float(
                    pd.to_numeric(group["extra_adverse_after_stop_r"], errors="coerce").median()
                ),
                "median_recovery_efficiency": float(pd.to_numeric(group["recovery_efficiency"], errors="coerce").median()),
            }
        )
    return pd.DataFrame(rows).sort_values("reentry_lot_pnl").reset_index(drop=True)


def _build_upper_curve(curve: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
    target = features[features["low_quality_reentry"].eq(1)].copy()
    cashflow = (
        target.dropna(subset=["reentry_exit_day"])
        .groupby("reentry_exit_day", as_index=False)
        .agg(skipped_reentry_pnl=("reentry_lot_pnl", "sum"), skipped_reentry_events=("trade_id", "size"))
        .rename(columns={"reentry_exit_day": "date"})
    )
    out = curve.copy()
    out = out.merge(cashflow, on="date", how="left")
    out["skipped_reentry_pnl"] = out["skipped_reentry_pnl"].fillna(0.0)
    out["skipped_reentry_events"] = out["skipped_reentry_events"].fillna(0).astype(int)
    out["skipped_reentry_pnl_cumsum"] = out["skipped_reentry_pnl"].cumsum()
    out["upper_bound_equity"] = pd.to_numeric(out["account_equity"], errors="coerce") - out["skipped_reentry_pnl_cumsum"]
    out["upper_bound_drawdown_pct"] = (
        out["upper_bound_equity"] / out["upper_bound_equity"].cummax() - 1.0
    ) * 100.0
    out["upper_bound_broker10_margin_to_equity_pct"] = (
        pd.to_numeric(out["broker10_total_margin_exact"], errors="coerce") / out["upper_bound_equity"] * 100.0
    ).replace([np.inf, -np.inf], np.nan)
    return out


def _plot_path(curve: pd.DataFrame) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True, constrained_layout=True)
    axes[0].plot(curve["date"], curve["account_equity"], color="#111827", label="official C9/15w")
    axes[0].plot(curve["date"], curve["upper_bound_equity"], color="#dc2626", label="skip slow/deep reentry upper bound")
    axes[0].set_yscale("log")
    axes[0].set_title("Stage054 equity path")
    axes[0].set_ylabel("equity log")
    axes[1].plot(curve["date"], curve["official_drawdown_pct"], color="#111827", label="official DD")
    axes[1].plot(curve["date"], curve["upper_bound_drawdown_pct"], color="#dc2626", label="upper-bound DD")
    axes[1].set_title("Drawdown")
    axes[1].set_ylabel("drawdown %")
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#111827", label="official broker10")
    axes[2].plot(
        curve["date"],
        curve["upper_bound_broker10_margin_to_equity_pct"],
        color="#dc2626",
        label="same-margin / upper equity diagnostic",
    )
    axes[2].axhline(100.0, color="#7f1d1d", linestyle="--", linewidth=0.9)
    axes[2].set_title("Broker10 margin to equity pct")
    axes[2].set_ylabel("%")
    for ax in axes:
        ax.grid(True, alpha=0.25)
        ax.legend(loc="best")
    fig.savefig(PATH_CHART_OUT, dpi=150)
    plt.close(fig)


def _plot_scatter(features: pd.DataFrame) -> None:
    data = features.copy()
    data["stop_to_reentry_bars"] = pd.to_numeric(data["stop_to_reentry_bars"], errors="coerce")
    data["extra_adverse_after_stop_r"] = pd.to_numeric(data["extra_adverse_after_stop_r"], errors="coerce")
    data["reentry_lot_pnl"] = pd.to_numeric(data["reentry_lot_pnl"], errors="coerce")
    fig, ax = plt.subplots(figsize=(10, 7), constrained_layout=True)
    colors = np.where(data["low_quality_reentry"].eq(1), "#dc2626", "#2563eb")
    sizes = np.clip(pd.to_numeric(data["reentry_lot_volume"], errors="coerce").fillna(1.0) * 5.0, 30, 500)
    scatter = ax.scatter(
        data["stop_to_reentry_bars"],
        data["extra_adverse_after_stop_r"],
        s=sizes,
        c=data["reentry_lot_pnl"],
        cmap="RdYlGn",
        edgecolor=colors,
        linewidth=1.0,
        alpha=0.82,
    )
    ax.axvline(LOW_QUALITY_REENTRY_BARS, color="#111827", linestyle="--", linewidth=0.9)
    ax.axhline(LOW_QUALITY_EXTRA_ADVERSE_R, color="#111827", linestyle="--", linewidth=0.9)
    ax.set_xlabel("bars from first stop to reentry")
    ax.set_ylabel("extra adverse after stop (R)")
    ax.set_title("C9 reentry reclaim quality; red outline = slow/deep target")
    ax.grid(True, alpha=0.25)
    fig.colorbar(scatter, ax=ax, label="reentry lot PnL")
    fig.savefig(SCATTER_CHART_OUT, dpi=150)
    plt.close(fig)


def _plot_bucket(bucket: pd.DataFrame) -> None:
    ordered = bucket.sort_values("reentry_lot_pnl").copy()
    x = np.arange(len(ordered))
    fig, ax = plt.subplots(figsize=(11, 6), constrained_layout=True)
    ax.bar(x, ordered["reentry_lot_pnl"], color="#64748b", alpha=0.85, label="reentry lot pnl")
    ax.scatter(x, ordered["initial_stop_pnl"], color="#dc2626", label="initial stop pnl")
    ax.axhline(0.0, color="#111827", linewidth=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(ordered["quality_bucket"], rotation=20, ha="right")
    ax.set_title("Stage054 quality bucket PnL")
    ax.set_ylabel("PnL")
    ax.grid(True, axis="y", alpha=0.25)
    ax.legend(loc="best")
    fig.savefig(BUCKET_CHART_OUT, dpi=150)
    plt.close(fig)


def _select_atlas_rows(features: pd.DataFrame) -> pd.DataFrame:
    target = features[features["low_quality_reentry"].eq(1)].copy()
    if target.empty:
        return pd.DataFrame()
    target["abs_reentry_pnl"] = pd.to_numeric(target["reentry_lot_pnl"], errors="coerce").abs()
    parts = [
        target.sort_values("reentry_lot_pnl").head(6),
        target.sort_values("reentry_lot_pnl", ascending=False).head(4),
        target.sort_values("stop_to_reentry_bars", ascending=False).head(4),
        target.sort_values("extra_adverse_after_stop_r", ascending=False).head(4),
    ]
    return (
        pd.concat(parts, ignore_index=True, sort=False)
        .drop_duplicates(["trade_id"])
        .head(MAX_ATLAS_ROWS)
        .reset_index(drop=True)
    )


def _time_index(day: pd.DataFrame, value: Any) -> int:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts) or day.empty:
        return -1
    times = pd.to_datetime(day["bar_datetime"], errors="coerce")
    hits = np.where(times.eq(pd.Timestamp(ts)).to_numpy())[0]
    return int(hits[0]) if len(hits) else -1


def _plot_atlas(features: pd.DataFrame) -> pd.DataFrame:
    selected = _select_atlas_rows(features)
    if selected.empty:
        return pd.DataFrame()
    minute_groups = _load_minute_groups(selected)
    manifest: list[dict[str, Any]] = []
    pages = int(math.ceil(len(selected) / ATLAS_PER_PAGE))
    for page in range(1, pages + 1):
        chunk = selected.iloc[(page - 1) * ATLAS_PER_PAGE : page * ATLAS_PER_PAGE].copy()
        fig, axes = plt.subplots(len(chunk), 1, figsize=(14, max(4.0, 3.2 * len(chunk))), constrained_layout=True)
        axes_list = list(np.atleast_1d(axes))
        for ax, (_, row) in zip(axes_list, chunk.iterrows(), strict=False):
            day = _event_day_bars(row, minute_groups)
            if day.empty:
                ax.axis("off")
                ax.text(0.5, 0.5, f"missing minute bars {row.get('vt_symbol')} {row.get('datetime')}", ha="center")
                continue
            stop_idx = _safe_int(row.get("first_stop_bar_index"))
            reentry_idx = _safe_int(row.get("reentry_bar_index"))
            start = max(0, stop_idx - 30)
            end = min(len(day), max(reentry_idx + 90, stop_idx + 90))
            view = day.iloc[start:end].copy().reset_index(drop=True)
            s008.s825._plot_candles(ax, view)
            for price_col, color, linestyle, label in [
                ("entry_price", "#2563eb", "-", "entry/reentry"),
                ("stop_price", "#dc2626", "--", "0.5R stop"),
                ("progress_price", "#16a34a", "--", "0.5R progress"),
            ]:
                price = _safe_float(row.get(price_col))
                if np.isfinite(price):
                    ax.axhline(price, color=color, linestyle=linestyle, linewidth=0.9, label=label)
            for time_col, color, label in [
                ("first_stop_time", "#dc2626", "first stop"),
                ("reentry_time", "#16a34a", "reentry"),
                ("retry_failed_time", "#7c2d12", "retry failed"),
            ]:
                idx = _time_index(view, row.get(time_col))
                if idx >= 0:
                    ax.axvline(idx, color=color, linewidth=1.0, alpha=0.85, label=label)
            title = (
                f"{row.get('trade_id')} {row.get('vt_symbol')} {row.get('direction')} "
                f"bars={_fmt(row.get('stop_to_reentry_bars'), 0)} extraR={_fmt(row.get('extra_adverse_after_stop_r'), 2)} "
                f"reentryPnL={_fmt(row.get('reentry_lot_pnl'), 0)}"
            )
            ax.set_title(title, fontsize=9)
            ax.legend(loc="best", fontsize=7)
            manifest.append(
                {
                    "page": page,
                    "trade_id": row.get("trade_id"),
                    "vt_symbol": row.get("vt_symbol"),
                    "direction": row.get("direction"),
                    "quality_bucket": row.get("quality_bucket"),
                    "stop_to_reentry_bars": row.get("stop_to_reentry_bars"),
                    "extra_adverse_after_stop_r": row.get("extra_adverse_after_stop_r"),
                    "reentry_lot_pnl": row.get("reentry_lot_pnl"),
                }
            )
        path = Path(str(ATLAS_TEMPLATE).format(page=page))
        fig.savefig(path, dpi=150)
        plt.close(fig)
    return pd.DataFrame(manifest)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curve = _load_official_curve()
    official = _official_metrics(curve)
    features = _build_features()
    bucket = _bucket_summary(features)
    upper_curve = _build_upper_curve(curve, features)
    upper_metrics = _equity_metrics(upper_curve["upper_bound_equity"], upper_curve["date"])
    upper_broker10_peak = float(pd.to_numeric(upper_curve["upper_bound_broker10_margin_to_equity_pct"], errors="coerce").max())
    target = features[features["low_quality_reentry"].eq(1)].copy()
    target_reentry_pnl = float(pd.to_numeric(target["reentry_lot_pnl"], errors="coerce").sum()) if len(target) else 0.0
    dd_improvement_pp = float(upper_metrics["max_dd_pct"] - official["max_dd_pct"])
    return_retention_pct = float(upper_metrics["total_return_pct"] / official["total_return_pct"] * 100.0)
    candidate_like = bool(
        len(target) >= 10
        and target["normalized_product"].nunique() >= 6
        and target["entry_year"].nunique() >= 4
        and target_reentry_pnl < 0
        and dd_improvement_pp >= 3.0
        and return_retention_pct >= 80.0
        and upper_broker10_peak <= official["broker10_peak_pct"] + 1.0
    )
    if candidate_like:
        decision = "stage054_reentry_quality_upper_bound_promising_requires_true_engine_ab_skill"
    else:
        decision = "stage054_slow_deep_reentry_quality_no_engine"

    features.to_csv(FEATURES_OUT, index=False, encoding="utf-8-sig")
    bucket.to_csv(BUCKET_SUMMARY_OUT, index=False, encoding="utf-8-sig")
    upper_curve.to_csv(UPPER_CURVE_OUT, index=False, encoding="utf-8-sig")
    _plot_path(upper_curve)
    _plot_scatter(features)
    _plot_bucket(bucket)
    atlas_manifest = _plot_atlas(features)
    atlas_manifest.to_csv(ATLAS_MANIFEST_OUT, index=False, encoding="utf-8-sig")

    target_summary = {
        "target_event_count": int(len(target)),
        "target_product_count": int(target["normalized_product"].nunique()) if len(target) else 0,
        "target_year_count": int(target["entry_year"].nunique()) if len(target) else 0,
        "target_reentry_lot_pnl": target_reentry_pnl,
        "target_initial_stop_pnl": float(pd.to_numeric(target["initial_stop_pnl"], errors="coerce").sum()) if len(target) else 0.0,
        "target_reentry_positive_pnl": float(pd.to_numeric(target["reentry_positive_pnl"], errors="coerce").sum()) if len(target) else 0.0,
        "target_reentry_negative_pnl_abs": float(pd.to_numeric(target["reentry_negative_pnl_abs"], errors="coerce").sum())
        if len(target)
        else 0.0,
        "target_median_stop_to_reentry_bars": float(pd.to_numeric(target["stop_to_reentry_bars"], errors="coerce").median())
        if len(target)
        else np.nan,
        "target_median_extra_adverse_after_stop_r": float(
            pd.to_numeric(target["extra_adverse_after_stop_r"], errors="coerce").median()
        )
        if len(target)
        else np.nan,
    }
    decision_payload = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "line_id": LINE_ID,
        "official_version": OFFICIAL_LIVE_VERSION,
        "official_alias": OFFICIAL_LIVE_ALIAS,
        "decision": decision,
        "candidate_like": candidate_like,
        "parameters": {
            "low_quality_reentry_bars": LOW_QUALITY_REENTRY_BARS,
            "low_quality_extra_adverse_r": LOW_QUALITY_EXTRA_ADVERSE_R,
            "fast_reclaim_bars": FAST_RECLAIM_BARS,
            "target_condition": "stop_to_reentry_bars >= 120 OR extra_adverse_after_stop_r >= 0.5",
        },
        "official": official,
        "upper_bound": {
            **upper_metrics,
            "dd_improvement_pp": dd_improvement_pp,
            "return_retention_pct": return_retention_pct,
            "broker10_peak_pct_same_margin_diagnostic": upper_broker10_peak,
        },
        "target": target_summary,
        "outputs": {
            "features": FEATURES_OUT,
            "bucket_summary": BUCKET_SUMMARY_OUT,
            "upper_curve": UPPER_CURVE_OUT,
            "report": REPORT_OUT,
            "path_chart": PATH_CHART_OUT,
            "scatter_chart": SCATTER_CHART_OUT,
            "bucket_chart": BUCKET_CHART_OUT,
            "atlas_manifest": ATLAS_MANIFEST_OUT,
        },
    }
    DECISION_OUT.write_text(json.dumps(_json_safe(decision_payload), ensure_ascii=False, indent=2), encoding="utf-8")

    report = f"""# {STAGE} C9 reentry reclaim quality audit

## Positioning

- Official version: `{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`.
- This is a read-only upper-bound audit, not a true engine and not a trading rule.
- Predeclared visible-at-reentry target: `stop_to_reentry_bars >= {LOW_QUALITY_REENTRY_BARS}` OR `extra_adverse_after_stop_r >= {LOW_QUALITY_EXTRA_ADVERSE_R}`.
- Meaning: after the first C9 0.5R stop, slow or deeper adverse reclaim is treated as a low-quality retry candidate. At the reentry minute, both conditions are already visible.

## Official Baseline

| item | value |
| --- | ---: |
| end equity | {_fmt(official['end_equity'], 2)} |
| total return | {_fmt(official['total_return_pct'])}% |
| max DD | {_fmt(official['max_dd_pct'])}% |
| Sharpe | {_fmt(official['sharpe'])} |
| total slippage | {_fmt(official['total_slippage'], 2)} |
| total trades | {_fmt(official['total_trade_count'], 0)} |
| win rate | {_fmt(official['win_rate_pct'])}% |
| broker10 peak | {_fmt(official['broker10_peak_pct'])}% |

## Bucket Summary

{_md_table(bucket)}

## Target Summary

| item | value |
| --- | ---: |
| target events | {target_summary['target_event_count']} |
| products | {target_summary['target_product_count']} |
| years | {target_summary['target_year_count']} |
| target reentry PnL | {_fmt(target_summary['target_reentry_lot_pnl'], 2)} |
| target initial stop PnL | {_fmt(target_summary['target_initial_stop_pnl'], 2)} |
| median stop-to-reentry bars | {_fmt(target_summary['target_median_stop_to_reentry_bars'])} |
| median extra adverse R | {_fmt(target_summary['target_median_extra_adverse_after_stop_r'])} |

## Upper Bound

| item | value |
| --- | ---: |
| end equity | {_fmt(upper_metrics['end_equity'], 2)} |
| total return | {_fmt(upper_metrics['total_return_pct'])}% |
| max DD | {_fmt(upper_metrics['max_dd_pct'])}% |
| Sharpe | {_fmt(upper_metrics['sharpe'])} |
| DD improvement | {_fmt(dd_improvement_pp)}pp |
| return retention | {_fmt(return_retention_pct)}% |
| broker10 peak same-margin diagnostic | {_fmt(upper_broker10_peak)}% |

## Decision

- Decision: `{decision}`.
- Candidate-like under upper-bound gate: `{candidate_like}`.
- This stage cannot be promoted without a true engine, because skipping reentry would change later exposure, margin, and trade sequencing.

## Visuals

- Path chart: `{PATH_CHART_OUT.name}`.
- Reentry quality scatter: `{SCATTER_CHART_OUT.name}`.
- Bucket PnL chart: `{BUCKET_CHART_OUT.name}`.
- Atlas manifest: `{ATLAS_MANIFEST_OUT.name}`.
"""
    REPORT_OUT.write_text(report, encoding="utf-8")
    print(json.dumps(_json_safe(decision_payload), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
