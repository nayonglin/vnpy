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
STAGE = "Stage037"
MODEL_TAG = "stage037_open_timestamp_price_replay_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage037_c9_minrisk_open_timestamp_price_replay_audit"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
TOOL_DIR = SCRIPT_PATH.parent
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
for item in [str(TOOL_DIR), str(EXAMPLE_DIR)]:
    if item not in sys.path:
        sys.path.insert(0, item)

import stage010_authoritative_minute_coverage_audit as s010


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
STAGE010_DIR = LINE_DIR / "outputs" / "stage010_authoritative_minute_coverage_audit"
OUTPUT_DIR = LINE_DIR / "outputs" / "stage037_open_timestamp_price_replay_audit"

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
CLOSED_LOTS_IN = (
    STAGE010_DIR
    / "qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_official_closed_lots_"
    "stage010_authoritative_minute_coverage_audit_v1.csv"
)
TRADES_IN = (
    STAGE010_DIR
    / "qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_official_trades_"
    "stage010_authoritative_minute_coverage_audit_v1.csv"
)

OPEN_TRADE_FEATURES_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_open_trade_replay_features_{MODEL_TAG}.csv"
CLOSED_LOT_FEATURES_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_closed_lot_replay_features_{MODEL_TAG}.csv"
STATUS_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_status_summary_{MODEL_TAG}.csv"
CONTRIBUTION_CURVE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_contribution_curve_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_replay_status_path_chart_{MODEL_TAG}.png"
STATUS_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_replay_status_summary_chart_{MODEL_TAG}.png"
SCATTER_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_price_match_scatter_{MODEL_TAG}.png"
ATLAS_MANIFEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_page{{page:03d}}_{MODEL_TAG}.png"

CAPITAL = 150_000.0
TRADING_DAYS_PER_YEAR = 252
ATLAS_ROWS = 20
ATLAS_PER_PAGE = 4
PRICE_TOL_REL = 1e-10


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
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return pd.NaT
    ts = pd.Timestamp(ts)
    if ts.tzinfo is not None:
        ts = ts.tz_localize(None)
    return ts.normalize()


def _load_curve() -> pd.DataFrame:
    curve = _read_csv(CURVE_IN)
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    curve = curve.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    for column in ["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct", "slippage", "trade_count"]:
        curve[column] = pd.to_numeric(curve.get(column, 0.0), errors="coerce").fillna(0.0)
    curve["drawdown_pct"] = _drawdown_pct(curve["account_equity"])
    previous = curve["account_equity"].shift(1)
    previous.iloc[0] = CAPITAL
    curve["daily_return"] = (curve["account_equity"] / previous - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return curve


def _load_summary() -> dict[str, Any]:
    if not SUMMARY_IN.exists():
        return {}
    frame = _read_csv(SUMMARY_IN)
    return frame.iloc[0].to_dict() if not frame.empty else {}


def _official_metrics(curve: pd.DataFrame, lots: pd.DataFrame) -> dict[str, float]:
    summary = _load_summary()
    returns = pd.to_numeric(curve["daily_return"], errors="coerce").fillna(0.0)
    std = float(returns.std(ddof=1)) if len(returns) > 1 else 0.0
    end = float(curve["account_equity"].iloc[-1]) if not curve.empty else CAPITAL
    pnl = pd.to_numeric(lots["realized_pnl"], errors="coerce").fillna(0.0)
    return {
        "end_equity": _safe_float(summary.get("end_equity"), end),
        "total_return_pct": _safe_float(summary.get("total_return_pct"), (end / CAPITAL - 1.0) * 100.0),
        "max_drawdown_pct": _safe_float(summary.get("max_dd_pct"), float(curve["drawdown_pct"].min())),
        "sharpe": _safe_float(
            summary.get("sharpe"),
            float(returns.mean() / std * np.sqrt(TRADING_DAYS_PER_YEAR)) if std > 0 else 0.0,
        ),
        "total_slippage": _safe_float(summary.get("total_slippage"), float(curve["slippage"].sum())),
        "total_trade_count": _safe_float(summary.get("total_trade_count"), float(curve["trade_count"].sum())),
        "closed_lot_win_rate_pct": float((pnl > 0.0).mean() * 100.0) if len(pnl) else 0.0,
        "max_broker10_margin_to_equity_pct": _safe_float(
            summary.get("max_broker10_margin_to_equity_pct"),
            float(curve["broker10_margin_to_equity_pct"].max()),
        ),
    }


def _price_tol(price: float) -> float:
    return max(1e-9, abs(float(price)) * PRICE_TOL_REL)


def _hhmm(value: Any) -> str:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return ""
    return pd.Timestamp(ts).strftime("%H:%M")


def _minute_of_day(value: Any) -> float:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return np.nan
    return float(pd.Timestamp(ts).hour * 60 + pd.Timestamp(ts).minute)


def _status(row: dict[str, Any]) -> str:
    if int(row["stage861_day_ready"]) == 0:
        return "missing_stage861_day"
    if int(row["first_bar_open_exact"]) == 1:
        return "first_bar_open_exact"
    if int(row["exact_price_match_count"]) == 1:
        return "single_later_exact_price"
    if int(row["exact_price_match_count"]) > 1:
        return "multi_exact_price_ambiguous"
    return "no_exact_price_on_entry_day"


def _replay_features_for_trade(row: pd.Series, groups: dict[str, pd.DataFrame]) -> dict[str, Any]:
    trade_id = str(row.get("trade_id", ""))
    vt_symbol = str(row.get("vt_symbol", ""))
    entry_day = _normalize_day(row.get("date", row.get("datetime")))
    price = _safe_float(row.get("price"))
    direction = str(row.get("direction", ""))
    volume = _safe_float(row.get("volume"), 0.0)
    day = s010._day_for_symbol(groups, vt_symbol, entry_day)
    base = {
        "trade_id": trade_id,
        "open_trade_id": trade_id,
        "vt_symbol": vt_symbol,
        "product": ".".join(vt_symbol.split(".")[-2:]) if "." in vt_symbol else vt_symbol,
        "direction": direction,
        "entry_date": entry_day.date().isoformat() if not pd.isna(entry_day) else "",
        "official_open_datetime": str(row.get("datetime", "")),
        "official_open_time": str(row.get("time", "")),
        "official_entry_price": price,
        "open_volume": volume,
        "stage861_day_ready": 0,
        "stage861_bar_count": 0,
        "minute_sources": "",
        "first_bar_datetime": "",
        "first_bar_time": "",
        "first_bar_open": np.nan,
        "first_bar_close": np.nan,
        "first_bar_open_delta": np.nan,
        "first_bar_open_abs_delta": np.nan,
        "first_bar_open_exact": 0,
        "exact_price_match_count": 0,
        "range_price_match_count": 0,
        "first_exact_match_datetime": "",
        "first_exact_match_time": "",
        "first_exact_match_bar_index": np.nan,
        "last_exact_match_datetime": "",
        "last_exact_match_time": "",
        "last_exact_match_bar_index": np.nan,
        "first_range_match_datetime": "",
        "first_range_match_time": "",
        "first_range_match_bar_index": np.nan,
        "price_match_span_minutes": np.nan,
        "replay_timestamp_status": "missing_stage861_day",
    }
    if day.empty or not np.isfinite(price):
        return base
    day = day.sort_values("bar_datetime").reset_index(drop=True)
    values = day[["open", "high", "low", "close"]].apply(pd.to_numeric, errors="coerce")
    tol = _price_tol(price)
    exact_mask = values.sub(price).abs().le(tol).any(axis=1)
    range_mask = values.min(axis=1).le(price + tol) & values.max(axis=1).ge(price - tol)
    exact_indexes = np.flatnonzero(exact_mask.to_numpy())
    range_indexes = np.flatnonzero(range_mask.to_numpy())
    first_dt = pd.to_datetime(day.loc[0, "bar_datetime"], errors="coerce")
    first_open = _safe_float(day.loc[0, "open"])
    first_close = _safe_float(day.loc[0, "close"])
    item = dict(base)
    item.update(
        {
            "stage861_day_ready": 1,
            "stage861_bar_count": int(len(day)),
            "minute_sources": ",".join(sorted(day.get("minute_source", pd.Series(dtype=str)).dropna().astype(str).unique())[:5]),
            "first_bar_datetime": first_dt.strftime("%Y-%m-%d %H:%M:%S") if pd.notna(first_dt) else "",
            "first_bar_time": _hhmm(first_dt),
            "first_bar_open": first_open,
            "first_bar_close": first_close,
            "first_bar_open_delta": first_open - price if np.isfinite(first_open) else np.nan,
            "first_bar_open_abs_delta": abs(first_open - price) if np.isfinite(first_open) else np.nan,
            "first_bar_open_exact": int(np.isfinite(first_open) and abs(first_open - price) <= tol),
            "exact_price_match_count": int(exact_mask.sum()),
            "range_price_match_count": int(range_mask.sum()),
        }
    )
    if len(exact_indexes):
        first_idx = int(exact_indexes[0])
        last_idx = int(exact_indexes[-1])
        first_match_dt = pd.to_datetime(day.loc[first_idx, "bar_datetime"], errors="coerce")
        last_match_dt = pd.to_datetime(day.loc[last_idx, "bar_datetime"], errors="coerce")
        item.update(
            {
                "first_exact_match_datetime": first_match_dt.strftime("%Y-%m-%d %H:%M:%S") if pd.notna(first_match_dt) else "",
                "first_exact_match_time": _hhmm(first_match_dt),
                "first_exact_match_bar_index": first_idx,
                "last_exact_match_datetime": last_match_dt.strftime("%Y-%m-%d %H:%M:%S") if pd.notna(last_match_dt) else "",
                "last_exact_match_time": _hhmm(last_match_dt),
                "last_exact_match_bar_index": last_idx,
                "price_match_span_minutes": float((last_match_dt - first_match_dt).total_seconds() / 60.0)
                if pd.notna(first_match_dt) and pd.notna(last_match_dt)
                else np.nan,
            }
        )
    if len(range_indexes):
        first_range_idx = int(range_indexes[0])
        first_range_dt = pd.to_datetime(day.loc[first_range_idx, "bar_datetime"], errors="coerce")
        item.update(
            {
                "first_range_match_datetime": first_range_dt.strftime("%Y-%m-%d %H:%M:%S") if pd.notna(first_range_dt) else "",
                "first_range_match_time": _hhmm(first_range_dt),
                "first_range_match_bar_index": first_range_idx,
            }
        )
    item["replay_timestamp_status"] = _status(item)
    return item


def _open_trade_features(open_trades: pd.DataFrame, closed_lots: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    vt_symbols = sorted(open_trades["vt_symbol"].dropna().astype(str).unique())
    minute_bars = s010.s008.s928._load_stage861_full_minute_bars(vt_symbols)
    groups = s010.s008.s825._minute_groups(minute_bars)
    rows = [_replay_features_for_trade(row, groups) for _, row in open_trades.iterrows()]
    features = pd.DataFrame(rows)
    lot_agg = (
        closed_lots.assign(realized_pnl=pd.to_numeric(closed_lots["realized_pnl"], errors="coerce").fillna(0.0))
        .groupby("open_trade_id", dropna=False)
        .agg(
            closed_lots=("lot_id", "count"),
            open_trade_lot_pnl=("realized_pnl", "sum"),
            winning_lots=("realized_pnl", lambda item: int((item > 0).sum())),
            losing_lots=("realized_pnl", lambda item: int((item < 0).sum())),
        )
        .reset_index()
    )
    features = features.merge(lot_agg, on="open_trade_id", how="left")
    for column in ["closed_lots", "open_trade_lot_pnl", "winning_lots", "losing_lots"]:
        features[column] = pd.to_numeric(features.get(column), errors="coerce").fillna(0.0)
    features["entry_year"] = pd.to_datetime(features["entry_date"], errors="coerce").dt.year
    return features, groups


def _closed_lot_features(closed_lots: pd.DataFrame, open_features: pd.DataFrame) -> pd.DataFrame:
    lots = closed_lots.copy()
    for column in ["entry_date", "exit_date"]:
        if column in lots.columns:
            lots[column] = pd.to_datetime(lots[column], errors="coerce").dt.normalize()
    for column in ["realized_pnl", "volume", "r_multiple"]:
        if column in lots.columns:
            lots[column] = pd.to_numeric(lots[column], errors="coerce")
    keep = [
        "open_trade_id",
        "replay_timestamp_status",
        "stage861_day_ready",
        "stage861_bar_count",
        "first_bar_datetime",
        "first_bar_time",
        "first_bar_open",
        "first_bar_open_delta",
        "first_bar_open_abs_delta",
        "first_bar_open_exact",
        "exact_price_match_count",
        "range_price_match_count",
        "first_exact_match_datetime",
        "first_exact_match_time",
        "first_exact_match_bar_index",
        "price_match_span_minutes",
    ]
    out = lots.merge(open_features[[col for col in keep if col in open_features.columns]], on="open_trade_id", how="left")
    out["replay_timestamp_status"] = out["replay_timestamp_status"].fillna("open_trade_not_found")
    out["exit_date_ts"] = pd.to_datetime(out.get("exit_date"), errors="coerce").dt.normalize()
    out["entry_year"] = pd.to_datetime(out.get("entry_date"), errors="coerce").dt.year
    return out


def _status_summary(open_features: pd.DataFrame, lot_features: pd.DataFrame) -> pd.DataFrame:
    total_open = len(open_features)
    total_lots = len(lot_features)
    total_pnl = float(pd.to_numeric(lot_features["realized_pnl"], errors="coerce").fillna(0.0).sum()) or np.nan
    positive_total = float(lot_features.loc[pd.to_numeric(lot_features["realized_pnl"], errors="coerce") > 0, "realized_pnl"].sum()) or np.nan
    negative_total = abs(float(lot_features.loc[pd.to_numeric(lot_features["realized_pnl"], errors="coerce") < 0, "realized_pnl"].sum())) or np.nan
    rows: list[dict[str, Any]] = []
    for status in sorted(open_features["replay_timestamp_status"].dropna().astype(str).unique()):
        trades = open_features[open_features["replay_timestamp_status"].astype(str).eq(status)]
        lots = lot_features[lot_features["replay_timestamp_status"].astype(str).eq(status)]
        pnl = pd.to_numeric(lots["realized_pnl"], errors="coerce").fillna(0.0)
        pos = float(pnl[pnl > 0].sum())
        neg = float(pnl[pnl < 0].sum())
        rows.append(
            {
                "replay_timestamp_status": status,
                "open_trades": int(len(trades)),
                "open_trade_share_pct": len(trades) / total_open * 100.0 if total_open else np.nan,
                "closed_lots": int(len(lots)),
                "closed_lot_share_pct": len(lots) / total_lots * 100.0 if total_lots else np.nan,
                "net_pnl": float(pnl.sum()),
                "net_pnl_share_pct": float(pnl.sum()) / total_pnl * 100.0 if total_pnl else np.nan,
                "positive_pnl": pos,
                "positive_pnl_share_pct": pos / positive_total * 100.0 if positive_total else np.nan,
                "negative_pnl": neg,
                "negative_abs_share_pct": abs(neg) / negative_total * 100.0 if negative_total else np.nan,
                "products": int(lots.get("product", pd.Series(dtype=str)).dropna().astype(str).nunique()) if not lots.empty else 0,
                "years": int(lots.get("entry_year", pd.Series(dtype=float)).dropna().nunique()) if not lots.empty else 0,
                "median_first_bar_abs_delta": float(pd.to_numeric(trades["first_bar_open_abs_delta"], errors="coerce").median()),
                "median_exact_match_count": float(pd.to_numeric(trades["exact_price_match_count"], errors="coerce").median()),
                "max_exact_match_count": float(pd.to_numeric(trades["exact_price_match_count"], errors="coerce").max()),
            }
        )
    order = {
        "first_bar_open_exact": 0,
        "single_later_exact_price": 1,
        "multi_exact_price_ambiguous": 2,
        "no_exact_price_on_entry_day": 3,
        "missing_stage861_day": 4,
        "open_trade_not_found": 5,
    }
    result = pd.DataFrame(rows)
    result["_order"] = result["replay_timestamp_status"].map(order).fillna(99)
    return result.sort_values("_order").drop(columns=["_order"]).reset_index(drop=True)


def _contribution_curve(curve: pd.DataFrame, lot_features: pd.DataFrame) -> pd.DataFrame:
    out = curve[["date", "account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]].copy()
    lots = lot_features.copy()
    lots["exit_date_ts"] = pd.to_datetime(lots["exit_date_ts"], errors="coerce").dt.normalize()
    lots["realized_pnl"] = pd.to_numeric(lots["realized_pnl"], errors="coerce").fillna(0.0)
    daily_all = lots.groupby("exit_date_ts")["realized_pnl"].sum()
    out["cum_pnl_all_closed_lots"] = out["date"].map(daily_all).fillna(0.0).cumsum()
    for status in sorted(lots["replay_timestamp_status"].dropna().astype(str).unique()):
        daily = lots[lots["replay_timestamp_status"].astype(str).eq(status)].groupby("exit_date_ts")["realized_pnl"].sum()
        out[f"cum_pnl_{status}"] = out["date"].map(daily).fillna(0.0).cumsum()
    return out


def _plot_path(contrib: pd.DataFrame) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(16, 12), sharex=True, constrained_layout=True)
    axes[0].plot(contrib["date"], contrib["account_equity"], color="#111827", linewidth=1.2, label="official equity")
    axes[0].set_title("Official C9/15w equity")
    axes[0].grid(True, alpha=0.25)
    axes[0].legend(loc="best")

    axes[1].plot(contrib["date"], contrib["drawdown_pct"], color="#dc2626", linewidth=1.0, label="drawdown %")
    axes[1].set_title("Official drawdown and broker10")
    axes[1].grid(True, alpha=0.25)
    axes[1].legend(loc="upper left")
    ax2 = axes[1].twinx()
    ax2.plot(contrib["date"], contrib["broker10_margin_to_equity_pct"], color="#2563eb", linewidth=0.9, alpha=0.75)
    ax2.set_ylabel("broker10 margin/equity %")

    colors = {
        "first_bar_open_exact": "#16a34a",
        "single_later_exact_price": "#0891b2",
        "multi_exact_price_ambiguous": "#f97316",
        "no_exact_price_on_entry_day": "#dc2626",
        "missing_stage861_day": "#6b7280",
        "open_trade_not_found": "#7c3aed",
    }
    axes[2].plot(contrib["date"], contrib["cum_pnl_all_closed_lots"], color="#111827", linewidth=1.2, label="all closed lots")
    for status, color in colors.items():
        column = f"cum_pnl_{status}"
        if column in contrib.columns:
            axes[2].plot(contrib["date"], contrib[column], color=color, linewidth=1.0, label=status)
    axes[2].axhline(0, color="#6b7280", linewidth=0.8)
    axes[2].set_title("Cumulative realized PnL by mechanical open timestamp replay status")
    axes[2].grid(True, alpha=0.25)
    axes[2].legend(loc="best", fontsize=8)
    fig.suptitle("Stage037 open timestamp price replay audit", fontsize=14)
    fig.savefig(PATH_CHART_OUT, dpi=150)
    plt.close(fig)


def _plot_status(summary: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(15, 10), constrained_layout=True)
    statuses = summary["replay_timestamp_status"].astype(str)
    axes[0, 0].bar(statuses, summary["open_trades"], color="#2563eb")
    axes[0, 0].set_title("Open trades by replay status")
    axes[0, 1].bar(statuses, summary["closed_lots"], color="#0891b2")
    axes[0, 1].set_title("Closed lots by replay status")
    axes[1, 0].bar(statuses, summary["net_pnl"] / 10000.0, color="#16a34a")
    axes[1, 0].axhline(0, color="#6b7280", linewidth=0.8)
    axes[1, 0].set_title("Net PnL by replay status, 10k")
    axes[1, 1].bar(statuses, summary["median_exact_match_count"], color="#f97316")
    axes[1, 1].set_title("Median exact price match count")
    for ax in axes.ravel():
        ax.tick_params(axis="x", labelrotation=30, labelsize=8)
        ax.grid(True, axis="y", alpha=0.25)
    fig.savefig(STATUS_CHART_OUT, dpi=150)
    plt.close(fig)


def _plot_scatter(open_features: pd.DataFrame) -> None:
    data = open_features[open_features["stage861_day_ready"].eq(1)].copy()
    if data.empty:
        return
    data["first_bar_open_delta"] = pd.to_numeric(data["first_bar_open_delta"], errors="coerce")
    data["first_exact_match_bar_index"] = pd.to_numeric(data["first_exact_match_bar_index"], errors="coerce")
    data["open_trade_lot_pnl"] = pd.to_numeric(data["open_trade_lot_pnl"], errors="coerce").fillna(0.0)
    y = data["first_exact_match_bar_index"].fillna(-20)
    fig, ax = plt.subplots(figsize=(12, 7), constrained_layout=True)
    scatter = ax.scatter(
        data["first_bar_open_delta"],
        y,
        c=data["open_trade_lot_pnl"].clip(lower=-500_000, upper=500_000),
        cmap="RdYlGn",
        s=np.sqrt(pd.to_numeric(data["open_volume"], errors="coerce").fillna(1.0).clip(lower=1.0)) * 10,
        alpha=0.72,
        edgecolors="#374151",
        linewidths=0.25,
    )
    ax.axvline(0, color="#111827", linewidth=0.8)
    ax.axhline(0, color="#6b7280", linewidth=0.8)
    ax.set_xlabel("first bar open - official entry price")
    ax.set_ylabel("first exact price match bar index (-20 means no exact match)")
    ax.set_title("Mechanical price replay: first-bar price delta vs first exact match")
    ax.grid(True, alpha=0.25)
    fig.colorbar(scatter, ax=ax, fraction=0.025, pad=0.02, label="open-trade lot PnL clipped")
    fig.savefig(SCATTER_OUT, dpi=150)
    plt.close(fig)


def _select_atlas_rows(open_features: pd.DataFrame) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    for status in [
        "first_bar_open_exact",
        "single_later_exact_price",
        "multi_exact_price_ambiguous",
        "no_exact_price_on_entry_day",
        "missing_stage861_day",
    ]:
        group = open_features[open_features["replay_timestamp_status"].eq(status)].copy()
        if group.empty:
            continue
        parts.append(group.nsmallest(2, "open_trade_lot_pnl"))
        parts.append(group.nlargest(2, "open_trade_lot_pnl"))
    out = pd.concat(parts, ignore_index=True, sort=False) if parts else pd.DataFrame()
    if out.empty:
        return out
    return out.drop_duplicates(subset=["trade_id", "vt_symbol", "entry_date"]).head(ATLAS_ROWS).reset_index(drop=True)


def _plot_atlas(open_features: pd.DataFrame, groups: dict[str, pd.DataFrame]) -> tuple[list[Path], pd.DataFrame]:
    selected = _select_atlas_rows(open_features)
    if selected.empty:
        _write_csv(pd.DataFrame(), ATLAS_MANIFEST_OUT)
        return [], pd.DataFrame()
    manifest_rows: list[dict[str, Any]] = []
    pages: list[Path] = []
    for page_idx, start in enumerate(range(0, len(selected), ATLAS_PER_PAGE), start=1):
        page_rows = selected.iloc[start : start + ATLAS_PER_PAGE].reset_index(drop=True)
        fig, axes = plt.subplots(len(page_rows), 1, figsize=(14, 3.4 * len(page_rows)), sharex=False, constrained_layout=True)
        if len(page_rows) == 1:
            axes = [axes]
        for ax, (_, row) in zip(axes, page_rows.iterrows()):
            day = s010._day_for_symbol(groups, str(row["vt_symbol"]), _normalize_day(row["entry_date"]))
            price = _safe_float(row["official_entry_price"])
            if day.empty:
                ax.text(0.5, 0.5, "missing Stage861 day", ha="center", va="center")
                ax.set_axis_off()
            else:
                day = day.sort_values("bar_datetime").reset_index(drop=True)
                x = np.arange(len(day))
                close = pd.to_numeric(day["close"], errors="coerce")
                ax.plot(x, close, color="#2563eb", linewidth=0.9, label="Stage861 close")
                ax.axhline(price, color="#111827", linewidth=1.0, linestyle="--", label="official entry price")
                if pd.notna(row.get("first_exact_match_bar_index")) and np.isfinite(_safe_float(row.get("first_exact_match_bar_index"))):
                    ax.axvline(_safe_float(row.get("first_exact_match_bar_index")), color="#16a34a", linewidth=1.0, label="first exact match")
                ax.axvline(0, color="#6b7280", linewidth=0.8, alpha=0.8, label="first bar")
                ax.grid(True, alpha=0.25)
                tick_positions = np.linspace(0, max(len(day) - 1, 0), num=min(6, len(day)), dtype=int)
                ax.set_xticks(tick_positions)
                ax.set_xticklabels([_hhmm(day.loc[pos, "bar_datetime"]) for pos in tick_positions], fontsize=8)
            title = (
                f"{row['trade_id']} {row['vt_symbol']} {row['entry_date']} {row['direction']} "
                f"price={price:g} status={row['replay_timestamp_status']} "
                f"matches={int(row['exact_price_match_count'])} pnl={_safe_float(row['open_trade_lot_pnl'], 0):,.0f}"
            )
            ax.set_title(title, fontsize=9)
            handles, labels = ax.get_legend_handles_labels()
            if handles:
                ax.legend(handles, labels, loc="best", fontsize=7)
            manifest_rows.append(
                {
                    "page": page_idx,
                    "trade_id": row["trade_id"],
                    "vt_symbol": row["vt_symbol"],
                    "entry_date": row["entry_date"],
                    "direction": row["direction"],
                    "official_entry_price": row["official_entry_price"],
                    "replay_timestamp_status": row["replay_timestamp_status"],
                    "exact_price_match_count": row["exact_price_match_count"],
                    "first_exact_match_datetime": row["first_exact_match_datetime"],
                    "first_bar_open_delta": row["first_bar_open_delta"],
                    "open_trade_lot_pnl": row["open_trade_lot_pnl"],
                }
            )
        output = Path(str(ATLAS_TEMPLATE).format(page=page_idx))
        fig.savefig(output, dpi=150)
        plt.close(fig)
        pages.append(output)
    manifest = pd.DataFrame(manifest_rows)
    _write_csv(manifest, ATLAS_MANIFEST_OUT)
    return pages, manifest


def _build_summary(curve: pd.DataFrame, closed_lots: pd.DataFrame, open_features: pd.DataFrame, lot_features: pd.DataFrame) -> pd.DataFrame:
    metrics = _official_metrics(curve, closed_lots)
    status_counts = open_features["replay_timestamp_status"].value_counts().to_dict()
    lot_status_counts = lot_features["replay_timestamp_status"].value_counts().to_dict()
    summary = _load_summary()
    row = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "official_live_version": summary.get("official_live_version", ""),
        "official_live_alias": summary.get("official_live_alias", ""),
        **metrics,
        "open_trade_rows": int(len(open_features)),
        "closed_lots": int(len(lot_features)),
        "first_bar_open_exact_open_trades": int(status_counts.get("first_bar_open_exact", 0)),
        "single_later_exact_price_open_trades": int(status_counts.get("single_later_exact_price", 0)),
        "multi_exact_price_ambiguous_open_trades": int(status_counts.get("multi_exact_price_ambiguous", 0)),
        "no_exact_price_on_entry_day_open_trades": int(status_counts.get("no_exact_price_on_entry_day", 0)),
        "missing_stage861_day_open_trades": int(status_counts.get("missing_stage861_day", 0)),
        "first_bar_open_exact_closed_lots": int(lot_status_counts.get("first_bar_open_exact", 0)),
        "single_later_exact_price_closed_lots": int(lot_status_counts.get("single_later_exact_price", 0)),
        "multi_exact_price_ambiguous_closed_lots": int(lot_status_counts.get("multi_exact_price_ambiguous", 0)),
        "no_exact_price_on_entry_day_closed_lots": int(lot_status_counts.get("no_exact_price_on_entry_day", 0)),
        "missing_stage861_day_closed_lots": int(lot_status_counts.get("missing_stage861_day", 0)),
        "first_bar_open_exact_rate_pct": float(status_counts.get("first_bar_open_exact", 0)) / len(open_features) * 100.0
        if len(open_features)
        else 0.0,
        "unambiguous_price_replay_open_trades": int(
            status_counts.get("first_bar_open_exact", 0) + status_counts.get("single_later_exact_price", 0)
        ),
        "ambiguous_or_missing_open_trades": int(
            status_counts.get("multi_exact_price_ambiguous", 0)
            + status_counts.get("no_exact_price_on_entry_day", 0)
            + status_counts.get("missing_stage861_day", 0)
        ),
        "median_first_bar_abs_delta": float(pd.to_numeric(open_features["first_bar_open_abs_delta"], errors="coerce").median()),
        "max_first_bar_abs_delta": float(pd.to_numeric(open_features["first_bar_open_abs_delta"], errors="coerce").max()),
        "decision": "stage037_price_replay_partial_ambiguous_no_trade_rule",
        "candidate_ready": 0,
        "ab_triggered": 0,
    }
    return pd.DataFrame([row])


def _build_report(
    summary: pd.DataFrame,
    status_summary: pd.DataFrame,
    open_features: pd.DataFrame,
    atlas_pages: list[Path],
    decision: dict[str, Any],
) -> None:
    row = summary.iloc[0]
    worst_delta = (
        open_features[open_features["stage861_day_ready"].eq(1)]
        .sort_values("first_bar_open_abs_delta", ascending=False)
        .head(10)[
            [
                "trade_id",
                "vt_symbol",
                "entry_date",
                "direction",
                "official_entry_price",
                "first_bar_open",
                "first_bar_open_delta",
                "replay_timestamp_status",
                "exact_price_match_count",
                "open_trade_lot_pnl",
            ]
        ]
    )
    lines = [
        "# Stage037 开仓分钟价格回放审计",
        "",
        "## 结论",
        "",
        "- 决策：`stage037_price_replay_partial_ambiguous_no_trade_rule`。",
        f"- open trade rows：`{int(row['open_trade_rows'])}`；首根 open 精确匹配：`{int(row['first_bar_open_exact_open_trades'])}`；单一后续精确价格：`{int(row['single_later_exact_price_open_trades'])}`；多重精确价格：`{int(row['multi_exact_price_ambiguous_open_trades'])}`；当日无精确价格：`{int(row['no_exact_price_on_entry_day_open_trades'])}`；Stage861 缺失日：`{int(row['missing_stage861_day_open_trades'])}`。",
        "- 这说明用 Stage861 分钟价格回放初始开仓时间只能得到部分线索：首根 open 精确匹配比例不足，后续价格匹配又存在大量多重命中或完全无命中。",
        "- 因此不能把 price-match timestamp 直接作为真实开仓分钟或交易规则；下一步若要分钟级进出场，必须做真正的订单事件回放，而不是 post-hoc 价格查找。",
        "",
        "## 官方基准",
        "",
        f"- 期末权益：`{row['end_equity']:.2f}`",
        f"- 总收益：`{row['total_return_pct']:.4f}%`",
        f"- 最大回撤：`{row['max_drawdown_pct']:.4f}%`",
        f"- Sharpe：`{row['sharpe']:.4f}`",
        f"- 总滑点：`{row['total_slippage']:.0f}`",
        f"- 总交易次数：`{row['total_trade_count']:.0f}`",
        f"- closed-lot 胜率：`{row['closed_lot_win_rate_pct']:.4f}%`",
        "",
        "## Replay Status Summary",
        "",
        _md_table(status_summary),
        "",
        "## First-Bar Delta Top10",
        "",
        _md_table(worst_delta),
        "",
        "## 视觉产物",
        "",
        f"- replay status path chart：`{PATH_CHART_OUT}`",
        f"- replay status summary chart：`{STATUS_CHART_OUT}`",
        f"- price match scatter：`{SCATTER_OUT}`",
        f"- atlas manifest：`{ATLAS_MANIFEST_OUT}`",
        *[f"- atlas page：`{path}`" for path in atlas_pages],
        "",
        "## 文件",
        "",
        f"- open trade features：`{OPEN_TRADE_FEATURES_OUT}`",
        f"- closed lot features：`{CLOSED_LOT_FEATURES_OUT}`",
        f"- status summary：`{STATUS_SUMMARY_OUT}`",
        f"- contribution curve：`{CONTRIBUTION_CURVE_OUT}`",
        f"- summary：`{SUMMARY_OUT}`",
        f"- decision：`{DECISION_OUT}`",
        "",
        "## 后续",
        "",
        "- 不继续挖 price-match 时间戳、首根 open、session/clock 或品种/年份补丁。",
        "- 下一步应实现订单事件回放原型：按官方日线信号产生 order，按 Stage861 分钟事件顺序撮合 open/stop/retry，输出独立 replay trades，再与官方 trade ledger 做价格/盈亏/事件一致性审计。",
        "",
        "## Decision JSON 摘要",
        "",
        "```json",
        json.dumps(_json_safe(decision), ensure_ascii=False, indent=2),
        "```",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curve = _load_curve()
    closed_lots = _read_csv(CLOSED_LOTS_IN)
    trades = _read_csv(TRADES_IN)
    open_trades = trades[trades.get("offset", "").astype(str).str.lower().eq("open")].copy()
    open_features, groups = _open_trade_features(open_trades, closed_lots)
    lot_features = _closed_lot_features(closed_lots, open_features)
    status_summary = _status_summary(open_features, lot_features)
    contrib = _contribution_curve(curve, lot_features)
    summary = _build_summary(curve, closed_lots, open_features, lot_features)

    _plot_path(contrib)
    _plot_status(status_summary)
    _plot_scatter(open_features)
    atlas_pages, atlas_manifest = _plot_atlas(open_features, groups)

    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": "stage037_price_replay_partial_ambiguous_no_trade_rule",
        "candidate_ready": 0,
        "ab_triggered": 0,
        "rule_added": 0,
        "official_config_changed": 0,
        "open_trade_rows": int(summary.iloc[0]["open_trade_rows"]),
        "first_bar_open_exact_open_trades": int(summary.iloc[0]["first_bar_open_exact_open_trades"]),
        "single_later_exact_price_open_trades": int(summary.iloc[0]["single_later_exact_price_open_trades"]),
        "multi_exact_price_ambiguous_open_trades": int(summary.iloc[0]["multi_exact_price_ambiguous_open_trades"]),
        "no_exact_price_on_entry_day_open_trades": int(summary.iloc[0]["no_exact_price_on_entry_day_open_trades"]),
        "missing_stage861_day_open_trades": int(summary.iloc[0]["missing_stage861_day_open_trades"]),
        "judgment": (
            "Stage861 price matching partially localizes official open prices, but most opens are ambiguous or unmatched. "
            "This is not a reliable initial open timestamp ledger."
        ),
        "overfit_guard": (
            "No threshold, product, direction, year, session or clock filter is promoted. Price-match timestamps are treated "
            "as a data-engineering diagnostic only."
        ),
        "next_step": (
            "Build an order-event replay prototype that emits independent replay trades before testing any minute-level entry or exit rule."
        ),
        "outputs": {
            "open_trade_features": OPEN_TRADE_FEATURES_OUT,
            "closed_lot_features": CLOSED_LOT_FEATURES_OUT,
            "status_summary": STATUS_SUMMARY_OUT,
            "contribution_curve": CONTRIBUTION_CURVE_OUT,
            "summary": SUMMARY_OUT,
            "report": REPORT_OUT,
            "path_chart": PATH_CHART_OUT,
            "status_chart": STATUS_CHART_OUT,
            "scatter": SCATTER_OUT,
            "atlas_manifest": ATLAS_MANIFEST_OUT,
            "atlas_pages": atlas_pages,
        },
    }

    _write_csv(open_features, OPEN_TRADE_FEATURES_OUT)
    _write_csv(lot_features, CLOSED_LOT_FEATURES_OUT)
    _write_csv(status_summary, STATUS_SUMMARY_OUT)
    _write_csv(contrib, CONTRIBUTION_CURVE_OUT)
    _write_csv(summary, SUMMARY_OUT)
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _build_report(summary, status_summary, open_features, atlas_pages, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
