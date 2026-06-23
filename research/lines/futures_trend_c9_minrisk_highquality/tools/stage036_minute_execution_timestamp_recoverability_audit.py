from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
import re
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage036"
MODEL_TAG = "stage036_minute_execution_timestamp_recoverability_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage036_c9_minrisk_minute_execution_timestamp_recoverability_audit"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
STAGE010_DIR = LINE_DIR / "outputs" / "stage010_authoritative_minute_coverage_audit"
OUTPUT_DIR = LINE_DIR / "outputs" / "stage036_minute_execution_timestamp_recoverability_audit"

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
TRADE_EVENTS_IN = (
    STAGE010_DIR
    / "qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_official_trade_events_"
    "stage010_authoritative_minute_coverage_audit_v1.csv"
)
INTRADAY_EVENTS_IN = (
    STAGE010_DIR
    / "qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_official_intraday_events_"
    "stage010_authoritative_minute_coverage_audit_v1.csv"
)
ENTRY_CANDIDATES_IN = (
    STAGE010_DIR
    / "qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_official_entry_candidates_"
    "stage010_authoritative_minute_coverage_audit_v1.csv"
)

ARTIFACT_AUDIT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_artifact_timestamp_audit_{MODEL_TAG}.csv"
LOT_TIMESTAMP_FEATURES_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_lot_timestamp_features_{MODEL_TAG}.csv"
INTRADAY_EVENT_COVERAGE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_intraday_event_coverage_{MODEL_TAG}.csv"
INTRADAY_EVENT_TIMELINE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_intraday_event_timeline_{MODEL_TAG}.csv"
SOURCE_EVIDENCE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_code_evidence_{MODEL_TAG}.csv"
CONTRIBUTION_CURVE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_contribution_curve_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_open_timestamp_path_chart_{MODEL_TAG}.png"
ARTIFACT_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_artifact_timestamp_heatmap_{MODEL_TAG}.png"
INTRADAY_TIMELINE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_intraday_event_timeline_{MODEL_TAG}.png"

CAPITAL = 150_000.0
TRADING_DAYS_PER_YEAR = 252
TIME_CLASS_ORDER = [
    "exact_intraday",
    "daily_midnight_placeholder",
    "date_only_placeholder",
    "missing",
]
INTRADAY_EVENT_TIME_FIELDS = [
    "hit_time",
    "first_stop_time",
    "reentry_time",
    "retry_failed_time",
]


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


def _is_missing_text(text: str) -> bool:
    return text.strip() == "" or text.strip().lower() in {"nan", "nat", "none", "null"}


def _classify_time_value(value: Any) -> str:
    if pd.isna(value):
        return "missing"
    text = str(value).strip()
    if _is_missing_text(text):
        return "missing"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return "date_only_placeholder"
    if re.fullmatch(r"\d{1,2}:\d{2}(:\d{2})?", text):
        parts = [int(part) for part in text.split(":")]
        hour = parts[0]
        minute = parts[1] if len(parts) > 1 else 0
        second = parts[2] if len(parts) > 2 else 0
        if hour == 0 and minute == 0 and second == 0:
            return "daily_midnight_placeholder"
        return "exact_intraday"
    dt = pd.to_datetime(text, errors="coerce")
    if pd.isna(dt):
        return "missing"
    if dt.hour == 0 and dt.minute == 0 and dt.second == 0 and dt.microsecond == 0:
        return "daily_midnight_placeholder"
    return "exact_intraday"


def _parsed_year(value: Any) -> float:
    if pd.isna(value):
        return np.nan
    dt = pd.to_datetime(value, errors="coerce")
    if pd.isna(dt):
        return np.nan
    return float(dt.year)


def _artifact_row(
    frame: pd.DataFrame,
    artifact: str,
    field: str,
    subset: pd.Series | None,
    role: str,
    interpretation: str,
) -> dict[str, Any]:
    if field not in frame.columns:
        return {
            "artifact": artifact,
            "field": field,
            "role": role,
            "total_rows": 0,
            "exact_intraday_rows": 0,
            "daily_midnight_placeholder_rows": 0,
            "date_only_placeholder_rows": 0,
            "missing_rows": 0,
            "exact_intraday_pct": np.nan,
            "non_exact_pct": np.nan,
            "sample_values": "",
            "supports_open_fill_timestamp": 0,
            "interpretation": "field_missing",
        }
    data = frame.loc[subset].copy() if subset is not None else frame.copy()
    classes = data[field].map(_classify_time_value)
    counts = classes.value_counts().to_dict()
    total = int(len(data))
    exact = int(counts.get("exact_intraday", 0))
    daily = int(counts.get("daily_midnight_placeholder", 0))
    date_only = int(counts.get("date_only_placeholder", 0))
    missing = int(counts.get("missing", 0))
    samples = (
        data[field]
        .dropna()
        .astype(str)
        .loc[lambda item: ~item.str.lower().isin(["nan", "nat", "none", "null", ""])]
        .head(3)
        .tolist()
    )
    supports = int(role == "open_fill_time" and total > 0 and exact == total)
    return {
        "artifact": artifact,
        "field": field,
        "role": role,
        "total_rows": total,
        "exact_intraday_rows": exact,
        "daily_midnight_placeholder_rows": daily,
        "date_only_placeholder_rows": date_only,
        "missing_rows": missing,
        "exact_intraday_pct": exact / total * 100.0 if total else np.nan,
        "non_exact_pct": (total - exact) / total * 100.0 if total else np.nan,
        "sample_values": "; ".join(samples),
        "supports_open_fill_timestamp": supports,
        "interpretation": interpretation,
    }


def _artifact_timestamp_audit(
    trades: pd.DataFrame,
    trade_events: pd.DataFrame,
    intraday: pd.DataFrame,
    candidates: pd.DataFrame,
    closed_lots: pd.DataFrame,
    lot_features: pd.DataFrame,
) -> pd.DataFrame:
    open_trade_mask = trades.get("offset", pd.Series(dtype=str)).astype(str).str.lower().eq("open")
    close_trade_mask = trades.get("offset", pd.Series(dtype=str)).astype(str).str.lower().eq("close")
    risk_sizing_mask = trade_events.get("offset", pd.Series(dtype=str)).astype(str).str.lower().eq("risksizing")
    close_event_mask = trade_events.get("offset", pd.Series(dtype=str)).astype(str).str.lower().eq("close")
    rows = [
        _artifact_row(
            trades,
            "official_trades_open",
            "datetime",
            open_trade_mask,
            "open_fill_time",
            "official open trade datetime should be exact if recoverable",
        ),
        _artifact_row(
            trades,
            "official_trades_open",
            "time",
            open_trade_mask,
            "open_fill_time",
            "official open trade time field should be non-midnight if recoverable",
        ),
        _artifact_row(
            trades,
            "official_trades_close",
            "datetime",
            close_trade_mask,
            "close_fill_time",
            "close trade datetime is also daily-bar based in current ledger",
        ),
        _artifact_row(
            candidates,
            "official_entry_candidates",
            "datetime",
            None,
            "signal_or_candidate_time",
            "entry candidate datetime is strategy daily decision timestamp, not fill minute",
        ),
        _artifact_row(
            trade_events,
            "official_trade_events_risksizing",
            "datetime",
            risk_sizing_mask,
            "daily_signal_event_time",
            "risk sizing rows are daily decision records",
        ),
        _artifact_row(
            trade_events,
            "official_trade_events_close",
            "datetime",
            close_event_mask,
            "close_event_time",
            "close event rows inherit daily-bar engine timestamp",
        ),
        _artifact_row(
            intraday,
            "official_intraday_events",
            "datetime",
            None,
            "intraday_event_parent_date",
            "parent datetime is the daily trade date placeholder",
        ),
        _artifact_row(
            intraday,
            "official_intraday_events",
            "hit_time",
            None,
            "post_open_intraday_event_time",
            "C2 hit_time can be exact but is a post-open path event, not the original fill time",
        ),
        _artifact_row(
            intraday,
            "official_intraday_events",
            "first_stop_time",
            None,
            "post_open_intraday_event_time",
            "first stop time can be exact but occurs after the open fill",
        ),
        _artifact_row(
            intraday,
            "official_intraday_events",
            "reentry_time",
            None,
            "post_open_intraday_event_time",
            "retry reentry time is exact for retry events but is not the initial open fill",
        ),
        _artifact_row(
            intraday,
            "official_intraday_events",
            "retry_failed_time",
            None,
            "post_open_intraday_event_time",
            "retry failure time is exact for failed retry events but is not the initial open fill",
        ),
        _artifact_row(
            closed_lots,
            "official_closed_lots",
            "entry_date",
            None,
            "closed_lot_entry_date",
            "closed lot entry_date is a date-level ledger field",
        ),
        _artifact_row(
            lot_features,
            "closed_lots_join_open_trades",
            "open_trade_datetime",
            None,
            "open_fill_time_join",
            "closed lots joined to open trades; should be exact if current artifacts recover fill minutes",
        ),
        _artifact_row(
            lot_features,
            "closed_lots_join_open_trades",
            "open_trade_time",
            None,
            "open_fill_time_join",
            "open trade time text after closed-lot join",
        ),
    ]
    return pd.DataFrame(rows)


def _build_lot_timestamp_features(closed_lots: pd.DataFrame, trades: pd.DataFrame) -> pd.DataFrame:
    lots = closed_lots.copy()
    for column in ["entry_date", "exit_date"]:
        if column in lots.columns:
            lots[column] = pd.to_datetime(lots[column], errors="coerce").dt.normalize()
    for column in ["realized_pnl", "volume", "r_multiple"]:
        if column in lots.columns:
            lots[column] = pd.to_numeric(lots[column], errors="coerce")
    open_trades = trades[trades.get("offset", "").astype(str).str.lower().eq("open")].copy()
    open_cols = ["trade_id", "datetime", "date", "time", "price", "volume"]
    open_cols = [column for column in open_cols if column in open_trades.columns]
    open_trades = open_trades[open_cols].rename(
        columns={
            "trade_id": "open_trade_id",
            "datetime": "open_trade_datetime",
            "date": "open_trade_date",
            "time": "open_trade_time",
            "price": "open_trade_price",
            "volume": "open_trade_volume",
        }
    )
    out = lots.merge(open_trades, on="open_trade_id", how="left", validate="many_to_one")
    out["open_trade_datetime_class"] = out["open_trade_datetime"].map(_classify_time_value)
    out["open_trade_time_class"] = out["open_trade_time"].map(_classify_time_value)
    out["open_timestamp_bucket"] = np.select(
        [
            out["open_trade_datetime_class"].eq("exact_intraday") | out["open_trade_time_class"].eq("exact_intraday"),
            out["open_trade_datetime_class"].eq("missing") & out["open_trade_time_class"].eq("missing"),
        ],
        ["open_time_exact_ready", "open_time_missing_or_unjoined"],
        default="open_time_daily_placeholder",
    )
    out["open_timestamp_recoverable"] = out["open_timestamp_bucket"].eq("open_time_exact_ready").astype(int)
    out["exit_date_ts"] = pd.to_datetime(out.get("exit_date"), errors="coerce").dt.normalize()
    out["entry_year"] = pd.to_datetime(out.get("entry_date"), errors="coerce").dt.year
    keep = [
        "lot_id",
        "open_trade_id",
        "close_trade_id",
        "vt_symbol",
        "product",
        "direction",
        "entry_date",
        "exit_date",
        "entry_year",
        "entry_price",
        "exit_price",
        "volume",
        "realized_pnl",
        "r_multiple",
        "exit_reason",
        "open_trade_datetime",
        "open_trade_time",
        "open_trade_datetime_class",
        "open_trade_time_class",
        "open_timestamp_bucket",
        "open_timestamp_recoverable",
        "exit_date_ts",
    ]
    return out[[column for column in keep if column in out.columns]].copy()


def _intraday_event_coverage(intraday: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    timeline_rows: list[dict[str, Any]] = []
    total = len(intraday)
    for field in INTRADAY_EVENT_TIME_FIELDS:
        if field not in intraday.columns:
            rows.append(
                {
                    "event_field": field,
                    "event_rows": total,
                    "nonmissing_rows": 0,
                    "exact_intraday_rows": 0,
                    "daily_placeholder_rows": 0,
                    "missing_rows": total,
                    "exact_intraday_pct_of_all_rows": 0.0,
                    "distinct_products_exact": 0,
                    "distinct_years_exact": 0,
                    "interpretation": "field_missing",
                }
            )
            continue
        classes = intraday[field].map(_classify_time_value)
        exact_mask = classes.eq("exact_intraday")
        exact = intraday.loc[exact_mask].copy()
        exact["event_year"] = exact[field].map(_parsed_year)
        rows.append(
            {
                "event_field": field,
                "event_rows": total,
                "nonmissing_rows": int(classes.ne("missing").sum()),
                "exact_intraday_rows": int(exact_mask.sum()),
                "daily_placeholder_rows": int(classes.isin(["daily_midnight_placeholder", "date_only_placeholder"]).sum()),
                "missing_rows": int(classes.eq("missing").sum()),
                "exact_intraday_pct_of_all_rows": float(exact_mask.mean() * 100.0) if total else np.nan,
                "distinct_products_exact": int(exact.get("product_vt_symbol", pd.Series(dtype=str)).dropna().astype(str).nunique()),
                "distinct_years_exact": int(exact["event_year"].dropna().nunique()),
                "interpretation": "post_open_event_time_not_initial_open_fill",
            }
        )
        for _, event in exact.iterrows():
            timeline_rows.append(
                {
                    "event_field": field,
                    "event_time": event.get(field, ""),
                    "event_year": int(event["event_year"]) if pd.notna(event["event_year"]) else np.nan,
                    "vt_symbol": event.get("vt_symbol", ""),
                    "product": event.get("product_vt_symbol", ""),
                    "direction": event.get("direction", ""),
                    "trade_id": event.get("trade_id", ""),
                    "final_state": event.get("final_state", ""),
                    "exit_reason": event.get("exit_reason", ""),
                }
            )
    return pd.DataFrame(rows), pd.DataFrame(timeline_rows)


def _source_code_evidence() -> pd.DataFrame:
    backtesting = REPO_DIR / ".py311" / "lib" / "python3.11" / "site-packages" / "vnpy_ctastrategy" / "backtesting.py"
    utility = REPO_DIR / "vnpy" / "trader" / "utility.py"

    def find_line(path: Path, pattern: str, after_pattern: str | None = None) -> tuple[int, str]:
        if not path.exists():
            return 0, "missing_file"
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        start_index = 0
        if after_pattern:
            for index, line in enumerate(lines):
                if after_pattern in line:
                    start_index = index
                    break
        for lineno, line in enumerate(lines[start_index:], start=start_index + 1):
            if pattern in line:
                return lineno, line.strip()
        return 0, "pattern_not_found"

    specs = [
        (
            backtesting,
            "def new_bar",
            "vn.py bar backtest sets engine context from each bar before crossing orders",
        ),
        (
            backtesting,
            "self.datetime = bar.datetime",
            "trade timestamps inherit the current bar datetime",
        ),
        (
            backtesting,
            "def cross_limit_order",
            "limit orders are crossed against the current bar/tick snapshot",
        ),
        (
            backtesting,
            "long_best_price = self.bar.open_price",
            "bar-mode fill price uses the bar open price, but timestamp remains the bar datetime",
        ),
        (
            backtesting,
            "datetime=self.datetime",
            "TradeData datetime is written from engine self.datetime",
        ),
        (
            utility,
            "def update_bar_daily_window",
            "daily bar aggregation is handled by BarGenerator daily window",
        ),
        (
            utility,
            "hour=0,",
            "daily window resets completed daily bar hour to 0",
        ),
        (
            utility,
            "minute=0,",
            "daily window resets completed daily bar minute to 0",
        ),
        (
            utility,
            "second=0,",
            "daily window resets completed daily bar second to 0",
        ),
    ]
    rows = []
    for path, pattern, interpretation in specs:
        after_pattern = "def update_bar_daily_window" if path == utility and pattern != "def update_bar_daily_window" else None
        lineno, snippet = find_line(path, pattern, after_pattern=after_pattern)
        rows.append(
            {
                "source_file": str(path),
                "line": lineno,
                "pattern": pattern,
                "snippet": snippet,
                "interpretation": interpretation,
            }
        )
    return pd.DataFrame(rows)


def _contribution_curve(curve: pd.DataFrame, lot_features: pd.DataFrame) -> pd.DataFrame:
    out = curve[["date", "account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]].copy()
    lots = lot_features.copy()
    lots["exit_date_ts"] = pd.to_datetime(lots["exit_date_ts"], errors="coerce").dt.normalize()
    lots["realized_pnl"] = pd.to_numeric(lots["realized_pnl"], errors="coerce").fillna(0.0)
    daily_all = lots.groupby("exit_date_ts")["realized_pnl"].sum()
    out["cum_pnl_all_closed_lots"] = out["date"].map(daily_all).fillna(0.0).cumsum()
    for bucket in sorted(lots["open_timestamp_bucket"].dropna().astype(str).unique()):
        daily = lots[lots["open_timestamp_bucket"].astype(str).eq(bucket)].groupby("exit_date_ts")["realized_pnl"].sum()
        out[f"cum_pnl_{bucket}"] = out["date"].map(daily).fillna(0.0).cumsum()
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
        "open_time_daily_placeholder": "#2563eb",
        "open_time_exact_ready": "#16a34a",
        "open_time_missing_or_unjoined": "#6b7280",
    }
    axes[2].plot(contrib["date"], contrib["cum_pnl_all_closed_lots"], color="#111827", linewidth=1.2, label="all closed lots")
    for bucket, color in colors.items():
        column = f"cum_pnl_{bucket}"
        if column in contrib.columns:
            axes[2].plot(contrib["date"], contrib[column], color=color, linewidth=1.0, label=bucket)
    axes[2].axhline(0, color="#6b7280", linewidth=0.8)
    axes[2].set_title("Cumulative realized PnL by open timestamp recoverability")
    axes[2].grid(True, alpha=0.25)
    axes[2].legend(loc="best", fontsize=8)
    fig.suptitle("Stage036 minute execution timestamp recoverability audit", fontsize=14)
    fig.savefig(PATH_CHART_OUT, dpi=150)
    plt.close(fig)


def _plot_artifact_heatmap(audit: pd.DataFrame) -> None:
    data = audit.copy()
    data["row_label"] = data["artifact"] + "." + data["field"]
    metrics = [
        "exact_intraday_rows",
        "daily_midnight_placeholder_rows",
        "date_only_placeholder_rows",
        "missing_rows",
    ]
    fig, ax = plt.subplots(figsize=(14, max(7, 0.42 * len(data) + 2)), constrained_layout=True)
    y = np.arange(len(data))
    left = np.zeros(len(data))
    colors = ["#16a34a", "#2563eb", "#f97316", "#9ca3af"]
    labels = ["exact intraday", "midnight placeholder", "date-only", "missing"]
    for metric, color, label in zip(metrics, colors, labels):
        values = pd.to_numeric(data[metric], errors="coerce").fillna(0.0).to_numpy()
        ax.barh(y, values, left=left, color=color, label=label)
        for i, value in enumerate(values):
            if value > 0:
                ax.text(left[i] + value / 2, i, f"{int(value)}", va="center", ha="center", fontsize=7, color="white")
        left += values
    ax.set_yticks(y)
    ax.set_yticklabels(data["row_label"], fontsize=8)
    ax.invert_yaxis()
    ax.set_xlabel("rows")
    ax.set_title("Timestamp class by artifact and field")
    ax.legend(loc="lower right", fontsize=8)
    ax.grid(True, axis="x", alpha=0.2)
    fig.savefig(ARTIFACT_HEATMAP_OUT, dpi=150)
    plt.close(fig)


def _plot_intraday_timeline(timeline: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(12, 6), constrained_layout=True)
    if timeline.empty:
        ax.text(0.5, 0.5, "No exact intraday event times", ha="center", va="center")
        ax.axis("off")
    else:
        pivot = (
            timeline.pivot_table(index="event_field", columns="event_year", values="trade_id", aggfunc="count", fill_value=0)
            .reindex(index=INTRADAY_EVENT_TIME_FIELDS)
            .fillna(0)
        )
        values = pivot.to_numpy(dtype=float)
        vmax = max(1.0, float(np.nanmax(values)) if values.size else 1.0)
        im = ax.imshow(values, aspect="auto", cmap="YlGnBu", vmin=0, vmax=vmax)
        ax.set_yticks(np.arange(len(pivot.index)))
        ax.set_yticklabels(pivot.index, fontsize=9)
        ax.set_xticks(np.arange(len(pivot.columns)))
        ax.set_xticklabels([str(int(col)) for col in pivot.columns], fontsize=8, rotation=45)
        for i in range(values.shape[0]):
            for j in range(values.shape[1]):
                if values[i, j] > 0:
                    ax.text(j, i, str(int(values[i, j])), ha="center", va="center", fontsize=8)
        ax.set_title("Exact post-open intraday event times by year")
        fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02, label="event count")
    fig.savefig(INTRADAY_TIMELINE_CHART_OUT, dpi=150)
    plt.close(fig)


def _build_summary(
    curve: pd.DataFrame,
    closed_lots: pd.DataFrame,
    lot_features: pd.DataFrame,
    audit: pd.DataFrame,
    intraday_coverage: pd.DataFrame,
) -> pd.DataFrame:
    metrics = _official_metrics(curve, closed_lots)
    bucket_counts = lot_features["open_timestamp_bucket"].value_counts().to_dict()
    intraday_counts = {
        f"{row['event_field']}_exact_rows": int(row["exact_intraday_rows"])
        for _, row in intraday_coverage.iterrows()
    }
    summary = _load_summary()
    exact_open_artifact_rows = int(
        audit[
            audit["role"].isin(["open_fill_time", "open_fill_time_join"])
            & audit["exact_intraday_rows"].gt(0)
        ]["exact_intraday_rows"].sum()
    )
    row = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "official_live_version": summary.get("official_live_version", ""),
        "official_live_alias": summary.get("official_live_alias", ""),
        **metrics,
        "closed_lots": int(len(closed_lots)),
        "open_time_exact_ready_lots": int(bucket_counts.get("open_time_exact_ready", 0)),
        "open_time_daily_placeholder_lots": int(bucket_counts.get("open_time_daily_placeholder", 0)),
        "open_time_missing_or_unjoined_lots": int(bucket_counts.get("open_time_missing_or_unjoined", 0)),
        "open_fill_exact_artifact_rows": exact_open_artifact_rows,
        "artifact_rows": int(audit["total_rows"].sum()),
        "artifact_exact_intraday_rows": int(audit["exact_intraday_rows"].sum()),
        "artifact_daily_midnight_placeholder_rows": int(audit["daily_midnight_placeholder_rows"].sum()),
        "artifact_date_only_placeholder_rows": int(audit["date_only_placeholder_rows"].sum()),
        "artifact_missing_rows": int(audit["missing_rows"].sum()),
        "candidate_ready": 0,
        "ab_triggered": 0,
        "decision": "stage036_minute_execution_timestamp_not_recoverable_from_current_artifacts",
        **intraday_counts,
    }
    return pd.DataFrame([row])


def _build_report(
    summary: pd.DataFrame,
    audit: pd.DataFrame,
    lot_features: pd.DataFrame,
    intraday_coverage: pd.DataFrame,
    source_evidence: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    row = summary.iloc[0]
    open_bucket = (
        lot_features.groupby("open_timestamp_bucket", dropna=False)
        .agg(
            lots=("lot_id", "count"),
            net_pnl=("realized_pnl", "sum"),
            products=("product", lambda item: item.astype(str).nunique()),
            years=("entry_year", "nunique"),
        )
        .reset_index()
        .sort_values("lots", ascending=False)
    )
    top_audit = audit[
        [
            "artifact",
            "field",
            "role",
            "total_rows",
            "exact_intraday_rows",
            "daily_midnight_placeholder_rows",
            "date_only_placeholder_rows",
            "missing_rows",
            "interpretation",
        ]
    ]
    lines = [
        "# Stage036 分钟成交时间戳可恢复性审计",
        "",
        "## 结论",
        "",
        "- 决策：`stage036_minute_execution_timestamp_not_recoverable_from_current_artifacts`。",
        f"- official closed lots：`{int(row['closed_lots'])}`；open exact ready lots：`{int(row['open_time_exact_ready_lots'])}`；open daily placeholder lots：`{int(row['open_time_daily_placeholder_lots'])}`。",
        "- 当前产物中存在若干止损/重入/重试失败的精确日内事件时间，但这些是开仓后的路径事件，不是原始开仓成交分钟。",
        "- 因此，后续不能基于 `official_trades.open datetime/time` 或 `entry_date` 伪造开仓分钟 K 规则；必须先做真实分钟执行回放，或只使用真正入场前可见且覆盖完整的外生源。",
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
        "## Open Timestamp Bucket",
        "",
        _md_table(open_bucket),
        "",
        "## Artifact Timestamp Audit",
        "",
        _md_table(top_audit, max_rows=30),
        "",
        "## Intraday Event Coverage",
        "",
        _md_table(intraday_coverage),
        "",
        "## Source Evidence",
        "",
        _md_table(source_evidence),
        "",
        "## 视觉产物",
        "",
        f"- open timestamp path chart：`{PATH_CHART_OUT}`",
        f"- artifact timestamp heatmap：`{ARTIFACT_HEATMAP_OUT}`",
        f"- intraday event timeline：`{INTRADAY_TIMELINE_CHART_OUT}`",
        "",
        "## 文件",
        "",
        f"- artifact audit：`{ARTIFACT_AUDIT_OUT}`",
        f"- lot timestamp features：`{LOT_TIMESTAMP_FEATURES_OUT}`",
        f"- contribution curve：`{CONTRIBUTION_CURVE_OUT}`",
        f"- summary：`{SUMMARY_OUT}`",
        f"- decision：`{DECISION_OUT}`",
        "",
        "## 后续",
        "",
        "- 若继续分钟级进出场，应先实现可复验的真实分钟执行/成交时间回放，把日线信号、下一可交易分钟、夜盘跨日、合约会话和 C9 stop/retry 事件统一到同一个事件账本。",
        "- 在该事件账本完成前，只能做入场前外生源只读交叉，不能继续挖 session/clock/open placeholder 桶。",
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
    trade_events = _read_csv(TRADE_EVENTS_IN)
    intraday = _read_csv(INTRADAY_EVENTS_IN)
    candidates = _read_csv(ENTRY_CANDIDATES_IN)

    lot_features = _build_lot_timestamp_features(closed_lots, trades)
    audit = _artifact_timestamp_audit(trades, trade_events, intraday, candidates, closed_lots, lot_features)
    intraday_coverage, intraday_timeline = _intraday_event_coverage(intraday)
    source_evidence = _source_code_evidence()
    contrib = _contribution_curve(curve, lot_features)
    summary = _build_summary(curve, closed_lots, lot_features, audit, intraday_coverage)

    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": "stage036_minute_execution_timestamp_not_recoverable_from_current_artifacts",
        "candidate_ready": 0,
        "ab_triggered": 0,
        "rule_added": 0,
        "official_config_changed": 0,
        "true_open_fill_timestamp_ready_lots": int(summary.iloc[0]["open_time_exact_ready_lots"]),
        "open_time_daily_placeholder_lots": int(summary.iloc[0]["open_time_daily_placeholder_lots"]),
        "open_time_missing_or_unjoined_lots": int(summary.iloc[0]["open_time_missing_or_unjoined_lots"]),
        "post_open_intraday_event_exact_counts": {
            row["event_field"]: int(row["exact_intraday_rows"]) for _, row in intraday_coverage.iterrows()
        },
        "judgment": (
            "Current Stage010 artifacts do not recover true minute-level initial open fill timestamps. "
            "Exact hit/stop/reentry timestamps are post-open path events and cannot substitute for the initial fill minute."
        ),
        "overfit_guard": (
            "No trading rule is promoted. Session/clock/open-placeholder buckets are blocked from rule design until "
            "a real minute execution replay ledger is built."
        ),
        "next_step": (
            "Build a deterministic execution timestamp replay or switch to complete pre-entry external sources; "
            "do not mine daily placeholder time fields."
        ),
        "outputs": {
            "artifact_audit": ARTIFACT_AUDIT_OUT,
            "lot_timestamp_features": LOT_TIMESTAMP_FEATURES_OUT,
            "intraday_event_coverage": INTRADAY_EVENT_COVERAGE_OUT,
            "intraday_event_timeline": INTRADAY_EVENT_TIMELINE_OUT,
            "source_evidence": SOURCE_EVIDENCE_OUT,
            "contribution_curve": CONTRIBUTION_CURVE_OUT,
            "summary": SUMMARY_OUT,
            "report": REPORT_OUT,
            "path_chart": PATH_CHART_OUT,
            "artifact_heatmap": ARTIFACT_HEATMAP_OUT,
            "intraday_timeline_chart": INTRADAY_TIMELINE_CHART_OUT,
        },
    }

    _plot_path(contrib)
    _plot_artifact_heatmap(audit)
    _plot_intraday_timeline(intraday_timeline)

    _write_csv(audit, ARTIFACT_AUDIT_OUT)
    _write_csv(lot_features, LOT_TIMESTAMP_FEATURES_OUT)
    _write_csv(intraday_coverage, INTRADAY_EVENT_COVERAGE_OUT)
    _write_csv(intraday_timeline, INTRADAY_EVENT_TIMELINE_OUT)
    _write_csv(source_evidence, SOURCE_EVIDENCE_OUT)
    _write_csv(contrib, CONTRIBUTION_CURVE_OUT)
    _write_csv(summary, SUMMARY_OUT)
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _build_report(summary, audit, lot_features, intraday_coverage, source_evidence, decision)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
