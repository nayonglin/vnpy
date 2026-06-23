from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage035"
MODEL_TAG = "stage035_entry_session_microstructure_forensics_v1"
OUTPUT_PREFIX = "qmt_roll_stage035_c9_minrisk_entry_session_microstructure_forensics"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
TOOL_DIR = SCRIPT_PATH.parent
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
for item in [str(TOOL_DIR), str(EXAMPLE_DIR)]:
    if item not in sys.path:
        sys.path.insert(0, item)

import stage010_authoritative_minute_coverage_audit as s010
from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
STAGE010_DIR = LINE_DIR / "outputs" / "stage010_authoritative_minute_coverage_audit"
OUTPUT_DIR = LINE_DIR / "outputs" / "stage035_entry_session_microstructure_forensics"

FEATURES_IN = (
    STAGE010_DIR
    / "qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_coverage_features_"
    "stage010_authoritative_minute_coverage_audit_v1.csv"
)
CURVE_IN = (
    STAGE010_DIR
    / "qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_official_curve_"
    "stage010_authoritative_minute_coverage_audit_v1.csv"
)
SUMMARY_IN = (
    STAGE010_DIR
    / "qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_summary_"
    "stage010_authoritative_minute_coverage_audit_v1.csv"
)
TRADES_IN = (
    STAGE010_DIR
    / "qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_official_trades_"
    "stage010_authoritative_minute_coverage_audit_v1.csv"
)

FEATURES_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_features_{MODEL_TAG}.csv"
SESSION_STATS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_session_template_stats_{MODEL_TAG}.csv"
CLOCK_STATS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_first_clock_stats_{MODEL_TAG}.csv"
YEAR_MATRIX_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_session_year_matrix_{MODEL_TAG}.csv"
PRODUCT_MATRIX_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_session_matrix_{MODEL_TAG}.csv"
CONTRIBUTION_CURVE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_contribution_curve_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_session_path_chart_{MODEL_TAG}.png"
YEAR_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_session_year_heatmap_{MODEL_TAG}.png"
CLOCK_DISTRIBUTION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_clock_distribution_{MODEL_TAG}.png"
SCATTER_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_session_first30_scatter_{MODEL_TAG}.png"
ATLAS_MANIFEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_page{{page:03d}}_{MODEL_TAG}.png"

CAPITAL = 150_000.0
FIRST_N_BARS = 30
ATLAS_WINDOW_BARS = 180
PER_PAGE = 4
MAX_ATLAS_ROWS = 20
TRADING_DAYS_PER_YEAR = 252


def _json_safe(value: Any) -> Any:
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        if np.isnan(value) or np.isinf(value):
            return None
        return float(value)
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if np.isfinite(result) else default


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    data = frame.copy()
    if max_rows is not None:
        data = data.head(max_rows)
    display = data.copy()
    for column in display.columns:
        if pd.api.types.is_float_dtype(display[column]):
            display[column] = display[column].map(lambda value: "" if pd.isna(value) else f"{value:.4f}")
    headers = [str(column) for column in display.columns]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for _, row in display.iterrows():
        lines.append("| " + " | ".join(str(row[column]) for column in display.columns) + " |")
    return "\n".join(lines)


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    equity = pd.to_numeric(equity, errors="coerce").ffill()
    hwm = equity.cummax()
    return (equity / hwm - 1.0) * 100.0


def _normalize_day(value: Any) -> pd.Timestamp:
    return s010._normalize_day(value)


def _minute_of_day(ts: Any) -> float:
    item = pd.to_datetime(ts, errors="coerce")
    if pd.isna(item):
        return np.nan
    return float(item.hour * 60 + item.minute)


def _hhmm(ts: Any) -> str:
    item = pd.to_datetime(ts, errors="coerce")
    if pd.isna(item):
        return ""
    return item.strftime("%H:%M")


def _load_curve() -> pd.DataFrame:
    curve = _read_csv(CURVE_IN)
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    curve = curve.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    for column in ["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct", "slippage", "trade_count"]:
        curve[column] = pd.to_numeric(curve.get(column, 0.0), errors="coerce").fillna(0.0)
    curve["drawdown_pct"] = _drawdown_pct(curve["account_equity"])
    prev_equity = curve["account_equity"].shift(1)
    prev_equity.iloc[0] = CAPITAL
    curve["daily_return"] = (curve["account_equity"] / prev_equity - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return curve


def _load_stage010_summary() -> dict[str, Any]:
    if not SUMMARY_IN.exists():
        return {}
    frame = _read_csv(SUMMARY_IN)
    return frame.iloc[0].to_dict() if not frame.empty else {}


def _official_metrics(curve: pd.DataFrame, features: pd.DataFrame) -> dict[str, float]:
    stage010 = _load_stage010_summary()
    returns = pd.to_numeric(curve["daily_return"], errors="coerce").fillna(0.0)
    std = float(returns.std(ddof=1)) if len(returns) > 1 else 0.0
    end = float(curve["account_equity"].iloc[-1]) if not curve.empty else CAPITAL
    pnl = pd.to_numeric(features["realized_pnl"], errors="coerce").fillna(0.0)
    return {
        "end_equity": _safe_float(stage010.get("end_equity"), end),
        "total_return_pct": _safe_float(stage010.get("total_return_pct"), (end / CAPITAL - 1.0) * 100.0),
        "max_drawdown_pct": _safe_float(
            stage010.get("max_dd_pct", stage010.get("max_drawdown_pct")),
            float(curve["drawdown_pct"].min()),
        ),
        "sharpe": _safe_float(stage010.get("sharpe"), float(returns.mean() / std * np.sqrt(TRADING_DAYS_PER_YEAR)) if std > 0 else 0.0),
        "total_slippage": _safe_float(stage010.get("total_slippage"), float(curve["slippage"].sum())),
        "total_trade_count": _safe_float(stage010.get("total_trade_count"), float(curve["trade_count"].sum())),
        "closed_lot_win_rate_pct": float((pnl > 0.0).mean() * 100.0) if len(pnl) else 0.0,
        "max_broker10_margin_to_equity_pct": _safe_float(
            stage010.get("max_broker10_margin_to_equity_pct"),
            float(curve["broker10_margin_to_equity_pct"].max()),
        ),
    }


def _load_base_features() -> pd.DataFrame:
    data = _read_csv(FEATURES_IN)
    for column in ["entry_date", "exit_date", "entry_day", "exit_date_ts"]:
        if column in data.columns:
            data[column] = pd.to_datetime(data[column], errors="coerce").dt.normalize()
    numeric_cols = [
        "lot_id",
        "realized_pnl",
        "r_multiple",
        "volume",
        "size",
        "entry_price",
        "exit_price",
        "risk_price",
        "risk_valid",
        "stage861_covered",
        "stage861_entry_day_minute_bars",
        "first_30m_directional_r",
        "first_30m_mfe_r",
        "first_30m_mae_r",
        "entry_day_mfe_r",
        "entry_day_mae_r",
    ]
    for column in numeric_cols:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    for column in ["vt_symbol", "product", "direction", "coverage_bucket", "open_trade_id"]:
        if column in data.columns:
            data[column] = data[column].astype(str)
    if "entry_year" not in data.columns:
        data["entry_year"] = pd.to_datetime(data["entry_date"], errors="coerce").dt.year
    else:
        data["entry_year"] = pd.to_numeric(data["entry_year"], errors="coerce")
    return data


def _load_open_trade_times() -> dict[str, dict[str, Any]]:
    if not TRADES_IN.exists():
        return {}
    trades = _read_csv(TRADES_IN)
    trades = trades[trades.get("offset", "").astype(str).str.lower().eq("open")].copy()
    if trades.empty:
        return {}
    trades["datetime_ts"] = pd.to_datetime(trades["datetime"], errors="coerce")
    result: dict[str, dict[str, Any]] = {}
    for _, row in trades.iterrows():
        trade_id = str(row.get("trade_id", ""))
        if not trade_id:
            continue
        dt = row.get("datetime_ts")
        time_text = str(row.get("time", ""))
        result[trade_id] = {
            "open_trade_datetime": dt.strftime("%Y-%m-%d %H:%M:%S%z") if pd.notna(dt) else str(row.get("datetime", "")),
            "open_trade_time": time_text,
            "open_trade_time_is_daily_placeholder": int(time_text in {"00:00:00", "0:00:00", "00:00"}),
        }
    return result


def _session_template(first_minute: float, last_minute: float, covered: bool) -> str:
    if not covered or not np.isfinite(first_minute) or not np.isfinite(last_minute):
        return "missing_stage861_session"
    if first_minute >= 14 * 60:
        return "late_partial_entry_day"
    if first_minute < 3 * 60:
        return "midnight_cross_entry_day"
    if last_minute <= 15 * 60 + 15:
        return "day_session_only"
    if last_minute < 23 * 60 + 15:
        return "day_plus_night_2300"
    if last_minute < 23 * 60 + 45:
        return "day_plus_night_2330"
    return "day_plus_night_2400"


def _first_clock_bucket(first_minute: float, covered: bool) -> str:
    if not covered or not np.isfinite(first_minute):
        return "missing_first_clock"
    if 8 * 60 + 55 <= first_minute <= 9 * 60 + 5:
        return "first_bar_around_day_open_0900"
    if 0 <= first_minute <= 5:
        return "first_bar_midnight_continuation"
    if 14 * 60 + 30 <= first_minute <= 15 * 60:
        return "first_bar_late_afternoon_partial"
    return "first_bar_other"


def _directional_close_path(row: pd.Series, day: pd.DataFrame, n_bars: int) -> pd.Series:
    entry = _safe_float(row.get("entry_price"))
    risk = _safe_float(row.get("risk_price"))
    direction = str(row.get("direction"))
    first = day.head(n_bars).copy()
    closes = pd.to_numeric(first["close"], errors="coerce")
    if first.empty or not np.isfinite(entry) or not np.isfinite(risk) or risk <= 0:
        return pd.Series(dtype=float)
    if direction == "short":
        return (entry - closes) / risk
    return (closes - entry) / risk


def _directional_pct_path(row: pd.Series, day: pd.DataFrame, n_bars: int) -> pd.Series:
    entry = _safe_float(row.get("entry_price"))
    direction = str(row.get("direction"))
    first = day.head(n_bars).copy()
    closes = pd.to_numeric(first["close"], errors="coerce")
    if first.empty or not np.isfinite(entry) or entry <= 0:
        return pd.Series(dtype=float)
    if direction == "short":
        return (entry - closes) / entry * 100.0
    return (closes - entry) / entry * 100.0


def _session_metrics(
    row: pd.Series,
    minute_groups: dict[str, pd.DataFrame],
    open_trade_times: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    vt_symbol = str(row.get("vt_symbol"))
    entry_day = _normalize_day(row.get("entry_day"))
    if pd.isna(entry_day):
        entry_day = _normalize_day(row.get("entry_date"))
    day = s010._day_for_symbol(minute_groups, vt_symbol, entry_day)
    covered = not day.empty and int(_safe_float(row.get("stage861_covered"), 0.0)) == 1
    open_info = open_trade_times.get(str(row.get("open_trade_id")), {})
    base = {
        "open_trade_datetime": open_info.get("open_trade_datetime", ""),
        "open_trade_time": open_info.get("open_trade_time", ""),
        "open_trade_time_is_daily_placeholder": int(open_info.get("open_trade_time_is_daily_placeholder", 1)),
        "session_first_datetime": "",
        "session_last_datetime": "",
        "session_first_time": "",
        "session_last_time": "",
        "session_first_minute_of_day": np.nan,
        "session_last_minute_of_day": np.nan,
        "session_span_minutes": np.nan,
        "session_gap_count_ge30m": np.nan,
        "session_segment_count": np.nan,
        "session_template": "missing_stage861_session",
        "first_clock_bucket": "missing_first_clock",
        "entry_price_to_first_open_delta": np.nan,
        "entry_price_to_first_close_delta": np.nan,
        "first_30m_abs_move_r": np.nan,
        "first_30m_path_end_r": np.nan,
        "first_30m_path_min_r": np.nan,
        "first_30m_path_max_r": np.nan,
    }
    if not covered:
        return base
    day = day.sort_values("bar_datetime").reset_index(drop=True)
    first_dt = pd.to_datetime(day["bar_datetime"].iloc[0], errors="coerce")
    last_dt = pd.to_datetime(day["bar_datetime"].iloc[-1], errors="coerce")
    first_minute = _minute_of_day(first_dt)
    last_minute = _minute_of_day(last_dt)
    deltas = pd.to_datetime(day["bar_datetime"], errors="coerce").diff().dt.total_seconds().div(60.0)
    gap_count = int((deltas > 30.0).sum())
    entry_price = _safe_float(row.get("entry_price"))
    first_open = _safe_float(day["open"].iloc[0])
    first_close = _safe_float(day["close"].iloc[0])
    path = _directional_close_path(row, day, FIRST_N_BARS).dropna()
    mfe = _safe_float(row.get("first_30m_mfe_r"))
    mae = _safe_float(row.get("first_30m_mae_r"))
    base.update(
        {
            "session_first_datetime": first_dt.strftime("%Y-%m-%d %H:%M:%S") if pd.notna(first_dt) else "",
            "session_last_datetime": last_dt.strftime("%Y-%m-%d %H:%M:%S") if pd.notna(last_dt) else "",
            "session_first_time": _hhmm(first_dt),
            "session_last_time": _hhmm(last_dt),
            "session_first_minute_of_day": first_minute,
            "session_last_minute_of_day": last_minute,
            "session_span_minutes": float((last_dt - first_dt).total_seconds() / 60.0) if pd.notna(first_dt) and pd.notna(last_dt) else np.nan,
            "session_gap_count_ge30m": gap_count,
            "session_segment_count": gap_count + 1,
            "session_template": _session_template(first_minute, last_minute, covered),
            "first_clock_bucket": _first_clock_bucket(first_minute, covered),
            "entry_price_to_first_open_delta": entry_price - first_open if np.isfinite(entry_price) and np.isfinite(first_open) else np.nan,
            "entry_price_to_first_close_delta": entry_price - first_close if np.isfinite(entry_price) and np.isfinite(first_close) else np.nan,
            "first_30m_abs_move_r": (mfe + mae) if np.isfinite(mfe) and np.isfinite(mae) else np.nan,
            "first_30m_path_end_r": float(path.iloc[-1]) if not path.empty else np.nan,
            "first_30m_path_min_r": float(path.min()) if not path.empty else np.nan,
            "first_30m_path_max_r": float(path.max()) if not path.empty else np.nan,
        }
    )
    return base


def _augment_features(data: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    vt_symbols = sorted(data["vt_symbol"].dropna().astype(str).unique())
    minute_bars = s010.s008.s928._load_stage861_full_minute_bars(vt_symbols)
    minute_groups = s010.s008.s825._minute_groups(minute_bars)
    open_trade_times = _load_open_trade_times()
    metrics = pd.DataFrame([_session_metrics(row, minute_groups, open_trade_times) for _, row in data.iterrows()])
    out = pd.concat([data.reset_index(drop=True), metrics], axis=1)
    out["positive_pnl"] = pd.to_numeric(out["realized_pnl"], errors="coerce").clip(lower=0.0)
    out["negative_pnl"] = pd.to_numeric(out["realized_pnl"], errors="coerce").clip(upper=0.0)
    return out, minute_groups


def _bucket_stats(features: pd.DataFrame, bucket_col: str) -> pd.DataFrame:
    total_pnl = float(features["realized_pnl"].fillna(0.0).sum())
    total_positive = float(features["positive_pnl"].fillna(0.0).sum())
    total_negative_abs = abs(float(features["negative_pnl"].fillna(0.0).sum()))
    rows: list[dict[str, Any]] = []
    for bucket, group in features.groupby(bucket_col, dropna=False):
        pnl = float(group["realized_pnl"].fillna(0.0).sum())
        positive = float(group["positive_pnl"].fillna(0.0).sum())
        negative = float(group["negative_pnl"].fillna(0.0).sum())
        year_pnl = group.groupby("entry_year")["realized_pnl"].sum()
        product_pnl = group.groupby("product")["realized_pnl"].sum()
        abs_product = product_pnl.abs().sort_values(ascending=False)
        abs_year = year_pnl.abs().sort_values(ascending=False)
        rows.append(
            {
                bucket_col: str(bucket),
                "lots": int(len(group)),
                "products": int(group["product"].astype(str).nunique()) if "product" in group.columns else 0,
                "years": int(group["entry_year"].dropna().nunique()),
                "positive_years": int((year_pnl > 0).sum()),
                "negative_years": int((year_pnl < 0).sum()),
                "net_pnl": pnl,
                "net_pnl_share_pct": pnl / total_pnl * 100.0 if total_pnl else np.nan,
                "positive_pnl": positive,
                "positive_pnl_share_pct": positive / total_positive * 100.0 if total_positive else np.nan,
                "negative_pnl": negative,
                "negative_pnl_abs_share_pct": abs(negative) / total_negative_abs * 100.0 if total_negative_abs else np.nan,
                "avg_pnl_per_lot": pnl / len(group) if len(group) else np.nan,
                "median_first_30m_directional_r": float(pd.to_numeric(group["first_30m_directional_r"], errors="coerce").median()),
                "median_first_30m_abs_move_r": float(pd.to_numeric(group["first_30m_abs_move_r"], errors="coerce").median()),
                "median_first_30m_mae_r": float(pd.to_numeric(group["first_30m_mae_r"], errors="coerce").median()),
                "median_session_bars": float(pd.to_numeric(group["stage861_entry_day_minute_bars"], errors="coerce").median()),
                "top1_product_abs_pnl_share_pct": float(abs_product.iloc[0] / abs_product.sum() * 100.0) if len(abs_product) and abs_product.sum() else np.nan,
                "top3_product_abs_pnl_share_pct": float(abs_product.head(3).sum() / abs_product.sum() * 100.0) if len(abs_product) and abs_product.sum() else np.nan,
                "top1_year_abs_pnl_share_pct": float(abs_year.iloc[0] / abs_year.sum() * 100.0) if len(abs_year) and abs_year.sum() else np.nan,
            }
        )
    result = pd.DataFrame(rows)
    return result.sort_values(["net_pnl"], ascending=False).reset_index(drop=True)


def _year_matrix(features: pd.DataFrame) -> pd.DataFrame:
    matrix = (
        features.pivot_table(
            index="session_template",
            columns="entry_year",
            values="realized_pnl",
            aggfunc="sum",
            fill_value=0.0,
        )
        .sort_index()
        .reset_index()
    )
    return matrix


def _product_matrix(features: pd.DataFrame) -> pd.DataFrame:
    matrix = (
        features.pivot_table(
            index="product",
            columns="session_template",
            values="realized_pnl",
            aggfunc="sum",
            fill_value=0.0,
        )
        .reset_index()
    )
    value_cols = [col for col in matrix.columns if col != "product"]
    matrix["abs_total"] = matrix[value_cols].abs().sum(axis=1)
    return matrix.sort_values("abs_total", ascending=False).drop(columns=["abs_total"]).reset_index(drop=True)


def _contribution_curve(curve: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
    out = curve[["date", "account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]].copy()
    lots = features.copy()
    lots["exit_date_ts"] = pd.to_datetime(lots.get("exit_date_ts", lots.get("exit_date")), errors="coerce").dt.normalize()
    lots["realized_pnl"] = pd.to_numeric(lots["realized_pnl"], errors="coerce").fillna(0.0)
    daily_all = lots.groupby("exit_date_ts")["realized_pnl"].sum()
    out["cum_pnl_all_closed_lots"] = out["date"].map(daily_all).fillna(0.0).cumsum()
    for bucket in sorted(lots["session_template"].dropna().astype(str).unique()):
        daily = lots[lots["session_template"].astype(str).eq(bucket)].groupby("exit_date_ts")["realized_pnl"].sum()
        out[f"cum_pnl_session_{bucket}"] = out["date"].map(daily).fillna(0.0).cumsum()
    return out


def _plot_path(contrib: pd.DataFrame) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(16, 12), sharex=True, constrained_layout=True)
    axes[0].plot(contrib["date"], contrib["account_equity"], color="#111827", linewidth=1.1, label="official equity")
    axes[0].set_title("Official C9/15w equity")
    axes[0].grid(True, alpha=0.25)
    axes[0].legend(loc="best")

    axes[1].plot(contrib["date"], contrib["drawdown_pct"], color="#dc2626", linewidth=1.0, label="drawdown %")
    axes[1].set_title("Official drawdown and broker10")
    axes[1].grid(True, alpha=0.25)
    ax2 = axes[1].twinx()
    ax2.plot(contrib["date"], contrib["broker10_margin_to_equity_pct"], color="#2563eb", linewidth=0.8, alpha=0.75)
    ax2.set_ylabel("broker10 margin/equity %")

    colors = {
        "day_session_only": "#16a34a",
        "day_plus_night_2300": "#2563eb",
        "day_plus_night_2330": "#7c3aed",
        "day_plus_night_2400": "#f97316",
        "midnight_cross_entry_day": "#0891b2",
        "late_partial_entry_day": "#dc2626",
        "missing_stage861_session": "#6b7280",
    }
    axes[2].plot(contrib["date"], contrib["cum_pnl_all_closed_lots"], color="#111827", linewidth=1.2, label="all closed lots")
    for bucket, color in colors.items():
        column = f"cum_pnl_session_{bucket}"
        if column in contrib.columns:
            axes[2].plot(contrib["date"], contrib[column], color=color, linewidth=1.0, label=bucket)
    axes[2].axhline(0, color="#6b7280", linewidth=0.8)
    axes[2].set_title("Cumulative realized PnL by entry-day session template")
    axes[2].grid(True, alpha=0.25)
    axes[2].legend(loc="best", fontsize=8)
    fig.suptitle("Stage035 entry-day session microstructure forensics", fontsize=14)
    fig.savefig(PATH_CHART_OUT, dpi=150)
    plt.close(fig)


def _plot_year_heatmap(matrix: pd.DataFrame) -> None:
    if matrix.empty:
        return
    data = matrix.set_index("session_template")
    columns = [col for col in data.columns]
    values = data.to_numpy(dtype=float)
    max_abs = float(np.nanmax(np.abs(values))) if values.size else 1.0
    max_abs = max_abs if max_abs > 0 else 1.0
    fig, ax = plt.subplots(figsize=(13, max(4, 0.55 * len(data.index) + 2)), constrained_layout=True)
    im = ax.imshow(values, aspect="auto", cmap="RdYlGn", vmin=-max_abs, vmax=max_abs)
    ax.set_yticks(np.arange(len(data.index)))
    ax.set_yticklabels(data.index, fontsize=8)
    ax.set_xticks(np.arange(len(columns)))
    ax.set_xticklabels([str(int(col)) if pd.notna(col) else "" for col in columns], fontsize=8, rotation=45)
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            ax.text(j, i, f"{values[i, j] / 10000:.0f}w", ha="center", va="center", fontsize=7)
    ax.set_title("Net PnL by entry year and session template")
    fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02, label="net PnL")
    fig.savefig(YEAR_HEATMAP_OUT, dpi=150)
    plt.close(fig)


def _plot_clock_distribution(session_stats: pd.DataFrame, clock_stats: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(15, 10), constrained_layout=True)
    for ax, stats, bucket_col, title in [
        (axes[0, 0], session_stats, "session_template", "Lots by session template"),
        (axes[0, 1], session_stats, "session_template", "Net PnL by session template"),
        (axes[1, 0], clock_stats, "first_clock_bucket", "Lots by first clock bucket"),
        (axes[1, 1], clock_stats, "first_clock_bucket", "Net PnL by first clock bucket"),
    ]:
        values = stats["lots"] if "Lots" in title else stats["net_pnl"] / 10000.0
        ax.bar(stats[bucket_col].astype(str), values, color="#2563eb" if "Lots" in title else "#16a34a")
        ax.set_title(title)
        ax.tick_params(axis="x", labelrotation=30, labelsize=8)
        ax.grid(True, axis="y", alpha=0.25)
        if "PnL" in title:
            ax.axhline(0, color="#6b7280", linewidth=0.8)
            ax.set_ylabel("net PnL, 10k")
    fig.savefig(CLOCK_DISTRIBUTION_OUT, dpi=150)
    plt.close(fig)


def _plot_scatter(features: pd.DataFrame) -> None:
    data = features[features["session_template"].ne("missing_stage861_session")].copy()
    if data.empty:
        return
    data["realized_pnl"] = pd.to_numeric(data["realized_pnl"], errors="coerce").fillna(0.0)
    colors = data["realized_pnl"].clip(lower=-500_000, upper=500_000)
    fig, ax = plt.subplots(figsize=(11, 7), constrained_layout=True)
    scatter = ax.scatter(
        data["first_30m_directional_r"],
        data["first_30m_abs_move_r"],
        c=colors,
        cmap="RdYlGn",
        s=np.sqrt(pd.to_numeric(data["volume"], errors="coerce").fillna(1.0).clip(lower=1.0)) * 9,
        alpha=0.72,
        edgecolors="#374151",
        linewidths=0.25,
    )
    ax.axvline(0, color="#6b7280", linewidth=0.8)
    ax.set_xlabel("first-30m directional R")
    ax.set_ylabel("first-30m absolute move R (MFE + MAE)")
    ax.set_title("Entry-day first-30m path vs realized PnL")
    ax.grid(True, alpha=0.25)
    fig.colorbar(scatter, ax=ax, fraction=0.025, pad=0.02, label="realized PnL clipped")
    fig.savefig(SCATTER_OUT, dpi=150)
    plt.close(fig)


def _select_atlas_rows(features: pd.DataFrame) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    for bucket in [
        "day_session_only",
        "day_plus_night_2300",
        "day_plus_night_2330",
        "day_plus_night_2400",
        "midnight_cross_entry_day",
        "late_partial_entry_day",
    ]:
        group = features[features["session_template"].eq(bucket)].copy()
        if group.empty:
            continue
        parts.append(group.nsmallest(2, "realized_pnl"))
        parts.append(group.nlargest(2, "realized_pnl"))
    out = pd.concat(parts, ignore_index=True, sort=False) if parts else pd.DataFrame()
    if out.empty:
        return out
    return out.drop_duplicates(subset=["lot_id", "vt_symbol", "entry_date"]).head(MAX_ATLAS_ROWS).reset_index(drop=True)


def _plot_atlas(features: pd.DataFrame, minute_groups: dict[str, pd.DataFrame]) -> tuple[list[Path], pd.DataFrame]:
    rows = _select_atlas_rows(features)
    if rows.empty:
        return [], pd.DataFrame()
    paths: list[Path] = []
    manifest: list[dict[str, Any]] = []
    for page_idx, start in enumerate(range(0, len(rows), PER_PAGE), start=1):
        subset = rows.iloc[start : start + PER_PAGE].reset_index(drop=True)
        fig, axes = plt.subplots(len(subset), 1, figsize=(13, 3.4 * len(subset)), constrained_layout=True)
        if len(subset) == 1:
            axes = np.array([axes])
        for ax, (_, row) in zip(axes, subset.iterrows()):
            vt_symbol = str(row.get("vt_symbol"))
            entry_day = _normalize_day(row.get("entry_day"))
            day = s010._day_for_symbol(minute_groups, vt_symbol, entry_day)
            day = day.sort_values("bar_datetime").reset_index(drop=True).head(ATLAS_WINDOW_BARS) if not day.empty else day
            path = _directional_close_path(row, day, ATLAS_WINDOW_BARS)
            axis_label = "directional R"
            path_mode = "R"
            if path.empty:
                path = _directional_pct_path(row, day, ATLAS_WINDOW_BARS)
                axis_label = "directional %"
                path_mode = "pct_fallback"
            if path.empty:
                ax.text(0.5, 0.5, "missing minute close path", transform=ax.transAxes, ha="center", va="center")
            else:
                x = np.arange(1, len(path) + 1)
                y = path.to_numpy(dtype=float)
                ax.plot(x, y, color="#111827", linewidth=1.1)
                ax.axvline(FIRST_N_BARS, color="#2563eb", linestyle="--", linewidth=0.8, alpha=0.8)
                dts = pd.to_datetime(day["bar_datetime"], errors="coerce")
                gaps = dts.diff().dt.total_seconds().div(60.0)
                for gap_idx in list(np.where(gaps.to_numpy(dtype=float) > 30.0)[0]):
                    ax.axvline(gap_idx, color="#f97316", linestyle=":", linewidth=0.8, alpha=0.8)
                ax.axhline(0, color="#6b7280", linewidth=0.8)
                ax.fill_between(x, 0, y, where=y >= 0, color="#16a34a", alpha=0.12)
                ax.fill_between(x, 0, y, where=y < 0, color="#dc2626", alpha=0.12)
                ticks = np.linspace(0, len(path) - 1, min(7, len(path)), dtype=int)
                ax.set_xticks(ticks + 1)
                ax.set_xticklabels([pd.Timestamp(day.loc[pos, "bar_datetime"]).strftime("%H:%M") for pos in ticks], fontsize=7)
            title = (
                f"{row.get('session_template')} | {vt_symbol} {row.get('direction')} "
                f"{pd.Timestamp(row.get('entry_day')).date() if pd.notna(row.get('entry_day')) else ''} "
                f"PnL={_safe_float(row.get('realized_pnl')):,.0f} first={row.get('session_first_time')} last={row.get('session_last_time')} "
                f"first30R={_safe_float(row.get('first_30m_directional_r')):.2f} mode={path_mode}"
            )
            ax.set_title(title, fontsize=9)
            ax.set_ylabel(axis_label)
            ax.grid(True, alpha=0.25)
            manifest.append(
                {
                    "page": page_idx,
                    "lot_id": row.get("lot_id"),
                    "vt_symbol": vt_symbol,
                    "entry_day": pd.Timestamp(row.get("entry_day")).date().isoformat() if pd.notna(row.get("entry_day")) else "",
                    "direction": row.get("direction"),
                    "session_template": row.get("session_template"),
                    "first_clock_bucket": row.get("first_clock_bucket"),
                    "realized_pnl": row.get("realized_pnl"),
                    "first_30m_directional_r": row.get("first_30m_directional_r"),
                }
            )
        page_path = Path(str(ATLAS_TEMPLATE).format(page=page_idx))
        fig.suptitle("Stage035 entry-day session atlas", fontsize=13)
        fig.savefig(page_path, dpi=150)
        plt.close(fig)
        paths.append(page_path)
    manifest_frame = pd.DataFrame(manifest)
    _write_csv(manifest_frame, ATLAS_MANIFEST_OUT)
    return paths, manifest_frame


def _build_summary(
    features: pd.DataFrame,
    session_stats: pd.DataFrame,
    clock_stats: pd.DataFrame,
    official: dict[str, float],
) -> pd.DataFrame:
    placeholder_count = int(pd.to_numeric(features["open_trade_time_is_daily_placeholder"], errors="coerce").fillna(1).sum())
    exact_time_ready = int(len(features) - placeholder_count)
    covered = int(pd.to_numeric(features["stage861_covered"], errors="coerce").fillna(0).sum())
    top_session = session_stats.iloc[0].to_dict() if not session_stats.empty else {}
    worst_session = session_stats.sort_values("net_pnl", ascending=True).iloc[0].to_dict() if not session_stats.empty else {}
    top_clock = clock_stats.iloc[0].to_dict() if not clock_stats.empty else {}
    rows = [
        {
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "official_live_version": OFFICIAL_LIVE_VERSION,
            "official_live_alias": OFFICIAL_LIVE_ALIAS,
            "closed_lots": int(len(features)),
            "stage861_session_covered_lots": covered,
            "stage861_session_coverage_pct": covered / len(features) * 100.0 if len(features) else 0.0,
            "open_trade_exact_minute_ready_lots": exact_time_ready,
            "open_trade_daily_placeholder_lots": placeholder_count,
            "official_end_equity": official["end_equity"],
            "official_total_return_pct": official["total_return_pct"],
            "official_max_drawdown_pct": official["max_drawdown_pct"],
            "official_sharpe": official["sharpe"],
            "official_total_slippage": official["total_slippage"],
            "official_total_trade_count": official["total_trade_count"],
            "official_closed_lot_win_rate_pct": official["closed_lot_win_rate_pct"],
            "top_session_template_by_net_pnl": top_session.get("session_template", ""),
            "top_session_template_net_pnl": top_session.get("net_pnl", np.nan),
            "worst_session_template_by_net_pnl": worst_session.get("session_template", ""),
            "worst_session_template_net_pnl": worst_session.get("net_pnl", np.nan),
            "top_first_clock_bucket_by_net_pnl": top_clock.get("first_clock_bucket", ""),
            "decision": "stage035_session_microstructure_readonly_no_trade_rule",
            "candidate_ready": 0,
            "ab_triggered": 0,
        }
    ]
    return pd.DataFrame(rows)


def _write_report(
    summary: pd.DataFrame,
    session_stats: pd.DataFrame,
    clock_stats: pd.DataFrame,
    atlas_paths: list[Path],
) -> None:
    row = summary.iloc[0].to_dict()
    lines = [
        f"# {STAGE} entry-day session microstructure forensics",
        "",
        f"- Generated: `{datetime.now().strftime('%Y-%m-%d %H:%M')}`",
        f"- Official live version: `{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`",
        "- Scope: read-only forensics. No trading rule, no live config edit, no CTP connection, no order API.",
        "- Evidence boundary: official open trades use daily placeholder timestamps; this stage audits Stage861 entry-day session exposure, not exact fill-minute timing.",
        "",
        "## Official baseline",
        "",
        _md_table(
            pd.DataFrame(
                [
                    {
                        "end_equity": row["official_end_equity"],
                        "total_return_pct": row["official_total_return_pct"],
                        "max_drawdown_pct": row["official_max_drawdown_pct"],
                        "sharpe": row["official_sharpe"],
                        "total_slippage": row["official_total_slippage"],
                        "total_trade_count": row["official_total_trade_count"],
                        "closed_lot_win_rate_pct": row["official_closed_lot_win_rate_pct"],
                    }
                ]
            )
        ),
        "",
        "## Coverage",
        "",
        _md_table(
            pd.DataFrame(
                [
                    {
                        "closed_lots": row["closed_lots"],
                        "stage861_session_covered_lots": row["stage861_session_covered_lots"],
                        "stage861_session_coverage_pct": row["stage861_session_coverage_pct"],
                        "open_trade_exact_minute_ready_lots": row["open_trade_exact_minute_ready_lots"],
                        "open_trade_daily_placeholder_lots": row["open_trade_daily_placeholder_lots"],
                    }
                ]
            )
        ),
        "",
        "## Session Template Stats",
        "",
        _md_table(session_stats, max_rows=20),
        "",
        "## First Clock Stats",
        "",
        _md_table(clock_stats, max_rows=20),
        "",
        "## Visual Outputs",
        "",
        f"- Path chart: `{PATH_CHART_OUT}`",
        f"- Session-year heatmap: `{YEAR_HEATMAP_OUT}`",
        f"- Clock distribution: `{CLOCK_DISTRIBUTION_OUT}`",
        f"- First-30m scatter: `{SCATTER_OUT}`",
        f"- Atlas pages: `{len(atlas_paths)}`",
        "",
        "## Read-only Judgment",
        "",
        "- Session/open-close microstructure is broad enough to audit, but exact fill-minute evidence is not available in the official trade ledger.",
        "- Session templates and first-clock buckets are diagnostic exposure labels only; they must not be turned into entry, restore, reduce, or exit rules from this stage alone.",
        "- A future candidate would require an independently visible pre-entry source or a true minute-level execution engine, plus OOS and cost-pressure checks.",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curve = _load_curve()
    features = _load_base_features()
    official = _official_metrics(curve, features)
    features, minute_groups = _augment_features(features)
    session_stats = _bucket_stats(features, "session_template")
    clock_stats = _bucket_stats(features, "first_clock_bucket")
    year_matrix = _year_matrix(features)
    product_matrix = _product_matrix(features)
    contribution = _contribution_curve(curve, features)
    summary = _build_summary(features, session_stats, clock_stats, official)

    _write_csv(features, FEATURES_OUT)
    _write_csv(session_stats, SESSION_STATS_OUT)
    _write_csv(clock_stats, CLOCK_STATS_OUT)
    _write_csv(year_matrix, YEAR_MATRIX_OUT)
    _write_csv(product_matrix, PRODUCT_MATRIX_OUT)
    _write_csv(contribution, CONTRIBUTION_CURVE_OUT)
    _write_csv(summary, SUMMARY_OUT)

    _plot_path(contribution)
    _plot_year_heatmap(year_matrix)
    _plot_clock_distribution(session_stats, clock_stats)
    _plot_scatter(features)
    atlas_paths, _ = _plot_atlas(features, minute_groups)
    _write_report(summary, session_stats, clock_stats, atlas_paths)

    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "decision": "stage035_session_microstructure_readonly_no_trade_rule",
        "candidate_ready": 0,
        "ab_triggered": 0,
        "reason": (
            "Official open trade timestamps are daily placeholders, while Stage861 only supports "
            "entry-day session exposure and close-path visuals. Session buckets are non-causal "
            "diagnostics unless joined with independently visible pre-entry evidence."
        ),
        "metrics": _json_safe(summary.iloc[0].to_dict()),
        "outputs": {
            "features": FEATURES_OUT,
            "session_stats": SESSION_STATS_OUT,
            "clock_stats": CLOCK_STATS_OUT,
            "year_matrix": YEAR_MATRIX_OUT,
            "product_matrix": PRODUCT_MATRIX_OUT,
            "contribution_curve": CONTRIBUTION_CURVE_OUT,
            "summary": SUMMARY_OUT,
            "report": REPORT_OUT,
            "path_chart": PATH_CHART_OUT,
            "year_heatmap": YEAR_HEATMAP_OUT,
            "clock_distribution": CLOCK_DISTRIBUTION_OUT,
            "scatter": SCATTER_OUT,
            "atlas_manifest": ATLAS_MANIFEST_OUT,
            "atlas_pages": atlas_paths,
        },
    }
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
