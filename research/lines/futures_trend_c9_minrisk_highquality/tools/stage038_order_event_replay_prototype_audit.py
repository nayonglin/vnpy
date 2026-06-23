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
STAGE = "Stage038"
MODEL_TAG = "stage038_order_event_replay_prototype_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage038_c9_minrisk_order_event_replay_prototype_audit"

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
OUTPUT_DIR = LINE_DIR / "outputs" / "stage038_order_event_replay_prototype_audit"

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
ENTRY_CANDIDATES_IN = (
    STAGE010_DIR
    / "qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_official_entry_candidates_"
    "stage010_authoritative_minute_coverage_audit_v1.csv"
)
INTRADAY_EVENTS_IN = (
    STAGE010_DIR
    / "qmt_roll_stage010_c9_minrisk_authoritative_minute_coverage_audit_official_intraday_events_"
    "stage010_authoritative_minute_coverage_audit_v1.csv"
)

ORDER_REPLAY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_order_replay_ledger_{MODEL_TAG}.csv"
CLOSED_LOT_SENSITIVITY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_closed_lot_entry_price_sensitivity_{MODEL_TAG}.csv"
EVENT_CONFUSION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_confusion_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
SENSITIVITY_CURVE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_same_exit_sensitivity_curve_{MODEL_TAG}.csv"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_same_exit_sensitivity_path_chart_{MODEL_TAG}.png"
CONFUSION_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_confusion_chart_{MODEL_TAG}.png"
SCATTER_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_fill_delta_scatter_{MODEL_TAG}.png"
ATLAS_MANIFEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_page{{page:03d}}_{MODEL_TAG}.png"

CAPITAL = 150_000.0
TRADING_DAYS_PER_YEAR = 252
STOP_RETRY_R = 0.5
MAX_RETRIES = 1
MAX_MATCH_CALENDAR_DAYS = 14
ATLAS_ROWS = 20
ATLAS_PER_PAGE = 4


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


def _time_text(value: Any) -> str:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return ""
    return pd.Timestamp(ts).strftime("%Y-%m-%dT%H:%M:%S")


def _hhmm(value: Any) -> str:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return ""
    return pd.Timestamp(ts).strftime("%H:%M")


def _trade_number(trade_id: Any) -> int:
    match = re.search(r"(\d+)$", str(trade_id))
    return int(match.group(1)) if match else 0


def _direction_text(value: Any) -> str:
    text = str(value).strip().lower()
    if text in {"long", "buy"}:
        return "long"
    if text in {"short", "sell"}:
        return "short"
    return text


def _direction_sign(direction: Any) -> int:
    return 1 if _direction_text(direction) == "long" else -1


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


def _prepare_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    curve = _load_curve()
    trades = _read_csv(TRADES_IN)
    candidates = _read_csv(ENTRY_CANDIDATES_IN)
    lots = _read_csv(CLOSED_LOTS_IN)
    intraday = _read_csv(INTRADAY_EVENTS_IN)
    open_trades = trades[trades["offset"].astype(str).str.lower().eq("open")].copy()
    for frame, columns in [
        (open_trades, ["date", "datetime"]),
        (candidates, ["date", "datetime"]),
        (lots, ["entry_date", "exit_date"]),
        (intraday, ["datetime"]),
    ]:
        for column in columns:
            if column in frame.columns:
                frame[f"{column}_ts"] = pd.to_datetime(frame[column], errors="coerce")
                if column in {"date", "entry_date", "exit_date"}:
                    frame[f"{column}_ts"] = frame[f"{column}_ts"].dt.normalize()
    for frame, columns in [
        (open_trades, ["price", "volume"]),
        (candidates, ["planned_entry_price", "stop_price", "selected_volume", "size"]),
        (lots, ["entry_price", "exit_price", "volume", "size", "realized_pnl"]),
    ]:
        for column in columns:
            if column in frame.columns:
                frame[column] = pd.to_numeric(frame[column], errors="coerce")
    open_trades["direction_norm"] = open_trades["direction"].map(_direction_text)
    candidates["direction_norm"] = candidates["direction"].map(_direction_text)
    lots["direction_norm"] = lots["direction"].map(_direction_text)
    open_trades["trade_number"] = open_trades["trade_id"].map(_trade_number)
    return curve, open_trades, candidates, lots, intraday, trades


def _match_initial_orders(candidates: pd.DataFrame, open_trades: pd.DataFrame) -> pd.DataFrame:
    opened = candidates[pd.to_numeric(candidates.get("is_opened"), errors="coerce").fillna(0).eq(1)].copy()
    opened = opened.sort_values(["date_ts", "contract_vt_symbol", "candidate_index"]).reset_index(drop=True)
    open_sorted = open_trades.sort_values(["date_ts", "trade_number"]).reset_index(drop=True)
    used_indexes: set[int] = set()
    rows: list[dict[str, Any]] = []
    for _, candidate in opened.iterrows():
        candidate_date = _normalize_day(candidate.get("date"))
        sym = str(candidate.get("contract_vt_symbol", ""))
        direction = _direction_text(candidate.get("direction"))
        pool = open_sorted[
            open_sorted["vt_symbol"].astype(str).eq(sym)
            & open_sorted["direction_norm"].eq(direction)
            & open_sorted["date_ts"].ge(candidate_date)
            & open_sorted["date_ts"].le(candidate_date + pd.Timedelta(days=MAX_MATCH_CALENDAR_DAYS))
        ].copy()
        pool = pool[~pool.index.isin(used_indexes)]
        if pool.empty:
            rows.append(
                {
                    "candidate_index": candidate.get("candidate_index"),
                    "candidate_date": candidate_date.date().isoformat() if pd.notna(candidate_date) else "",
                    "vt_symbol": sym,
                    "direction": direction,
                    "match_status": "no_initial_open_trade_match",
                }
            )
            continue
        trade = pool.sort_values(["date_ts", "trade_number"]).iloc[0]
        used_indexes.add(int(trade.name))
        trade_date = _normalize_day(trade.get("date"))
        rows.append(
            {
                "candidate_index": candidate.get("candidate_index"),
                "candidate_date": candidate_date.date().isoformat() if pd.notna(candidate_date) else "",
                "candidate_datetime": str(candidate.get("datetime", "")),
                "vt_symbol": sym,
                "product_vt_symbol": candidate.get("product_vt_symbol", ""),
                "direction": direction,
                "planned_entry_price": _safe_float(candidate.get("planned_entry_price")),
                "planned_stop_price": _safe_float(candidate.get("stop_price")),
                "planned_stop_distance": _safe_float(candidate.get("stop_distance")),
                "candidate_selected_volume": _safe_float(candidate.get("selected_volume"), 0.0),
                "size": _safe_float(candidate.get("size"), np.nan),
                "official_open_trade_id": trade.get("trade_id"),
                "official_open_datetime": str(trade.get("datetime", "")),
                "official_open_date": trade_date.date().isoformat() if pd.notna(trade_date) else "",
                "official_open_price": _safe_float(trade.get("price")),
                "official_open_volume": _safe_float(trade.get("volume"), 0.0),
                "candidate_to_open_calendar_days": int((trade_date - candidate_date).days)
                if pd.notna(trade_date) and pd.notna(candidate_date)
                else np.nan,
                "match_status": "matched_initial_open_trade",
            }
        )
    matched_trade_ids = {str(item["official_open_trade_id"]) for item in rows if item.get("official_open_trade_id")}
    unmatched_open = open_trades[~open_trades["trade_id"].astype(str).isin(matched_trade_ids)].copy()
    reentry_like_count = int(len(unmatched_open))
    result = pd.DataFrame(rows)
    result["unmatched_official_open_trades_after_initial_matching"] = reentry_like_count
    return result


def _load_minute_groups(order_matches: pd.DataFrame) -> dict[str, pd.DataFrame]:
    symbols = sorted(order_matches["vt_symbol"].dropna().astype(str).unique())
    minute_bars = s010.s008.s928._load_stage861_full_minute_bars(symbols)
    return s010.s008.s825._minute_groups(minute_bars)


def _first_c9_stop_or_progress(
    day: pd.DataFrame,
    *,
    entry_price: float,
    risk_price: float,
    direction: str,
    start_idx: int = 0,
) -> dict[str, Any]:
    sign = _direction_sign(direction)
    stop_price = entry_price - sign * STOP_RETRY_R * risk_price
    progress_price = entry_price + sign * STOP_RETRY_R * risk_price
    for idx in range(max(0, int(start_idx)), len(day)):
        item = day.iloc[idx]
        high = _safe_float(item.get("high"))
        low = _safe_float(item.get("low"))
        if direction == "long":
            adverse_hit = low <= stop_price
            progress_hit = high >= progress_price
        else:
            adverse_hit = high >= stop_price
            progress_hit = low <= progress_price
        if adverse_hit:
            return {
                "event": "stop",
                "idx": idx,
                "time": _time_text(item.get("bar_datetime")),
                "stop_price": stop_price,
                "progress_price": progress_price,
                "same_bar_progress": int(progress_hit),
            }
        if progress_hit:
            return {
                "event": "progress",
                "idx": idx,
                "time": _time_text(item.get("bar_datetime")),
                "stop_price": stop_price,
                "progress_price": progress_price,
                "same_bar_progress": 1,
            }
    return {
        "event": "none",
        "idx": -1,
        "time": "",
        "stop_price": stop_price,
        "progress_price": progress_price,
        "same_bar_progress": 0,
    }


def _reentry_after_stop(
    day: pd.DataFrame,
    *,
    direction: str,
    entry_price: float,
    stop_price: float,
    stop_idx: int,
) -> dict[str, Any]:
    reentry_idx = -1
    reentry_time = ""
    if MAX_RETRIES > 0:
        for idx in range(int(stop_idx) + 1, len(day)):
            item = day.iloc[idx]
            if direction == "long":
                reclaimed = _safe_float(item.get("high")) >= entry_price
            else:
                reclaimed = _safe_float(item.get("low")) <= entry_price
            if reclaimed:
                reentry_idx = idx
                reentry_time = _time_text(item.get("bar_datetime"))
                break
    retry_failed_idx = -1
    retry_failed_time = ""
    if reentry_idx >= 0:
        for idx in range(reentry_idx + 1, len(day)):
            item = day.iloc[idx]
            if direction == "long":
                retry_stop_hit = _safe_float(item.get("low")) <= stop_price
            else:
                retry_stop_hit = _safe_float(item.get("high")) >= stop_price
            if retry_stop_hit:
                retry_failed_idx = idx
                retry_failed_time = _time_text(item.get("bar_datetime"))
                break
    return {
        "reentry_idx": reentry_idx,
        "reentry_time": reentry_time,
        "retry_failed_idx": retry_failed_idx,
        "retry_failed_time": retry_failed_time,
    }


def _first_c2_stop_or_confirm(
    day: pd.DataFrame,
    *,
    entry_price: float,
    stop_price: float,
    risk_price: float,
    direction: str,
    start_idx: int = 0,
) -> dict[str, Any]:
    sign = _direction_sign(direction)
    confirm_price = entry_price + sign * risk_price
    for idx in range(max(0, int(start_idx)), len(day)):
        item = day.iloc[idx]
        high = _safe_float(item.get("high"))
        low = _safe_float(item.get("low"))
        if direction == "long":
            adverse_hit = low <= stop_price
            confirm_hit = high >= confirm_price
        else:
            adverse_hit = high >= stop_price
            confirm_hit = low <= confirm_price
        if adverse_hit:
            return {
                "event": "c2_stop",
                "idx": idx,
                "time": _time_text(item.get("bar_datetime")),
                "stop_price": stop_price,
                "confirm_price": confirm_price,
                "same_bar_confirm": int(confirm_hit),
            }
        if confirm_hit:
            return {
                "event": "confirm",
                "idx": idx,
                "time": _time_text(item.get("bar_datetime")),
                "stop_price": stop_price,
                "confirm_price": confirm_price,
                "same_bar_confirm": 1,
            }
    return {"event": "none", "idx": -1, "time": "", "stop_price": stop_price, "confirm_price": confirm_price}


def _official_event_lookup(intraday: pd.DataFrame) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    if intraday.empty:
        return lookup
    for _, row in intraday.iterrows():
        trade_id = str(row.get("trade_id", ""))
        if not trade_id:
            continue
        reason = str(row.get("exit_reason", ""))
        if reason.startswith("stage847_intraday_retry_failed"):
            family = "c9_flat_retry_failed"
        elif reason.startswith("stage847_intraday_05r_stop_no_reentry"):
            family = "c9_flat_no_reentry"
        elif reason.startswith("stage847_intraday_05r_stop_reentry_open"):
            family = "c9_open_after_reentry"
        elif reason.startswith("stage827_intraday_c2_1r_stop"):
            family = "c2_stop"
        else:
            family = "other_intraday_event"
        lookup[trade_id] = {
            "official_event_family": family,
            "official_exit_reason": reason,
            "official_first_stop_time": _time_text(row.get("first_stop_time")),
            "official_reentry_time": _time_text(row.get("reentry_time")),
            "official_retry_failed_time": _time_text(row.get("retry_failed_time")),
            "official_hit_time": _time_text(row.get("hit_time")),
            "official_final_state": str(row.get("final_state", "")),
            "official_final_exit_price": _safe_float(row.get("final_exit_price")),
        }
    return lookup


def _replay_one_order(row: pd.Series, groups: dict[str, pd.DataFrame], event_lookup: dict[str, dict[str, Any]]) -> dict[str, Any]:
    trade_id = str(row.get("official_open_trade_id", ""))
    vt_symbol = str(row.get("vt_symbol", ""))
    direction = _direction_text(row.get("direction"))
    entry_day = _normalize_day(row.get("official_open_date"))
    official_entry = _safe_float(row.get("official_open_price"))
    planned_stop = _safe_float(row.get("planned_stop_price"))
    official_volume = _safe_float(row.get("official_open_volume"), 0.0)
    selected_volume = _safe_float(row.get("candidate_selected_volume"), 0.0)
    base = row.to_dict()
    base.update(
        {
            "stage861_day_ready": 0,
            "stage861_bar_count": 0,
            "replay_open_datetime": "",
            "replay_open_time": "",
            "replay_open_price": np.nan,
            "replay_open_price_source": "missing_stage861_day",
            "replay_open_minus_official": np.nan,
            "replay_open_abs_delta": np.nan,
            "replay_risk_price": np.nan,
            "replay_c9_stop_price": np.nan,
            "replay_c9_progress_price": np.nan,
            "replay_c2_stop_price": np.nan,
            "replay_c2_confirm_price": np.nan,
            "replay_event_family": "missing_stage861_day",
            "replay_first_stop_time": "",
            "replay_reentry_time": "",
            "replay_retry_failed_time": "",
            "replay_c2_hit_time": "",
            "replay_final_exit_price": np.nan,
            "volume_match": int(np.isfinite(official_volume) and np.isfinite(selected_volume) and official_volume == selected_volume),
        }
    )
    if str(row.get("match_status", "")) != "matched_initial_open_trade" or pd.isna(entry_day):
        base["replay_event_family"] = "unmatched_initial_order"
        return base
    day = s010._day_for_symbol(groups, vt_symbol, entry_day)
    official = event_lookup.get(trade_id, {})
    base.update(
        {
            "official_event_family": official.get("official_event_family", "no_intraday_event"),
            "official_exit_reason": official.get("official_exit_reason", ""),
            "official_first_stop_time": official.get("official_first_stop_time", ""),
            "official_reentry_time": official.get("official_reentry_time", ""),
            "official_retry_failed_time": official.get("official_retry_failed_time", ""),
            "official_hit_time": official.get("official_hit_time", ""),
            "official_final_state": official.get("official_final_state", ""),
            "official_final_exit_price": official.get("official_final_exit_price", np.nan),
        }
    )
    if day.empty:
        return base
    day = day.sort_values("bar_datetime").reset_index(drop=True)
    first = day.iloc[0]
    replay_open = _safe_float(first.get("open"))
    if not np.isfinite(replay_open) or replay_open <= 0:
        replay_open = _safe_float(first.get("close"))
        price_source = "first_stage861_bar_close_fallback"
    else:
        price_source = "first_stage861_bar_open"
    risk_price = abs(replay_open - planned_stop) if np.isfinite(replay_open) and np.isfinite(planned_stop) else np.nan
    base.update(
        {
            "stage861_day_ready": 1,
            "stage861_bar_count": int(len(day)),
            "replay_open_datetime": _time_text(first.get("bar_datetime")),
            "replay_open_time": _hhmm(first.get("bar_datetime")),
            "replay_open_price": replay_open,
            "replay_open_price_source": price_source,
            "replay_open_minus_official": replay_open - official_entry if np.isfinite(official_entry) else np.nan,
            "replay_open_abs_delta": abs(replay_open - official_entry) if np.isfinite(official_entry) else np.nan,
            "replay_risk_price": risk_price,
            "replay_c2_stop_price": planned_stop,
            "replay_c2_confirm_price": replay_open + _direction_sign(direction) * risk_price
            if np.isfinite(risk_price)
            else np.nan,
        }
    )
    min_risk = max(1e-9, abs(replay_open) * 1e-12)
    if not np.isfinite(risk_price) or risk_price < min_risk:
        base["replay_event_family"] = "invalid_replay_risk"
        return base

    c9 = _first_c9_stop_or_progress(day, entry_price=replay_open, risk_price=risk_price, direction=direction)
    base.update(
        {
            "replay_c9_stop_price": c9["stop_price"],
            "replay_c9_progress_price": c9["progress_price"],
        }
    )
    if c9["event"] == "stop":
        retry = _reentry_after_stop(
            day,
            direction=direction,
            entry_price=replay_open,
            stop_price=float(c9["stop_price"]),
            stop_idx=int(c9["idx"]),
        )
        family = "c9_flat_no_reentry"
        final_exit = float(c9["stop_price"])
        if int(retry["reentry_idx"]) >= 0:
            family = "c9_open_after_reentry"
            final_exit = np.nan
            if int(retry["retry_failed_idx"]) >= 0:
                family = "c9_flat_retry_failed"
                final_exit = float(c9["stop_price"])
        base.update(
            {
                "replay_event_family": family,
                "replay_first_stop_time": str(c9["time"]),
                "replay_reentry_time": str(retry["reentry_time"]),
                "replay_retry_failed_time": str(retry["retry_failed_time"]),
                "replay_final_exit_price": final_exit,
                "replay_same_bar_progress": int(c9.get("same_bar_progress", 0)),
            }
        )
    else:
        c2 = _first_c2_stop_or_confirm(
            day,
            entry_price=replay_open,
            stop_price=planned_stop,
            risk_price=risk_price,
            direction=direction,
        )
        if c2["event"] == "c2_stop":
            family = "c2_stop"
            final_exit = planned_stop
            hit_time = str(c2["time"])
        else:
            family = "open_no_intraday_event"
            final_exit = np.nan
            hit_time = ""
        base.update(
            {
                "replay_event_family": family,
                "replay_c2_hit_time": hit_time,
                "replay_final_exit_price": final_exit,
                "replay_c2_same_bar_confirm": int(c2.get("same_bar_confirm", 0)),
            }
        )
    official_family = str(base.get("official_event_family", "no_intraday_event"))
    replay_family = str(base.get("replay_event_family", ""))
    base["event_family_match"] = int(
        (official_family == "no_intraday_event" and replay_family == "open_no_intraday_event")
        or official_family == replay_family
    )
    base["first_stop_time_match"] = int(
        bool(base.get("official_first_stop_time")) and base.get("official_first_stop_time") == base.get("replay_first_stop_time")
    )
    base["reentry_time_match"] = int(
        bool(base.get("official_reentry_time")) and base.get("official_reentry_time") == base.get("replay_reentry_time")
    )
    base["retry_failed_time_match"] = int(
        bool(base.get("official_retry_failed_time"))
        and base.get("official_retry_failed_time") == base.get("replay_retry_failed_time")
    )
    base["c2_hit_time_match"] = int(
        bool(base.get("official_hit_time")) and base.get("official_hit_time") == base.get("replay_c2_hit_time")
    )
    return base


def _build_order_replay(
    candidates: pd.DataFrame,
    open_trades: pd.DataFrame,
    intraday: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    matches = _match_initial_orders(candidates, open_trades)
    groups = _load_minute_groups(matches)
    event_lookup = _official_event_lookup(intraday)
    rows = [_replay_one_order(row, groups, event_lookup) for _, row in matches.iterrows()]
    replay = pd.DataFrame(rows)
    for column in [
        "official_open_price",
        "official_open_volume",
        "candidate_selected_volume",
        "replay_open_price",
        "replay_open_minus_official",
        "replay_open_abs_delta",
        "replay_risk_price",
    ]:
        if column in replay.columns:
            replay[column] = pd.to_numeric(replay[column], errors="coerce")
    return replay, groups


def _closed_lot_sensitivity(lots: pd.DataFrame, replay: pd.DataFrame) -> pd.DataFrame:
    keep = [
        "official_open_trade_id",
        "candidate_index",
        "candidate_date",
        "official_open_date",
        "replay_open_datetime",
        "replay_open_price",
        "replay_open_minus_official",
        "replay_event_family",
        "official_event_family",
        "event_family_match",
        "stage861_day_ready",
    ]
    out = lots.copy()
    out = out.merge(
        replay[[col for col in keep if col in replay.columns]],
        left_on="open_trade_id",
        right_on="official_open_trade_id",
        how="left",
    )
    for column in ["entry_price", "exit_price", "volume", "size", "realized_pnl", "replay_open_price"]:
        if column in out.columns:
            out[column] = pd.to_numeric(out[column], errors="coerce")
    signs = out["direction_norm"].map(lambda item: _direction_sign(item))
    price_delta = out["replay_open_price"] - out["entry_price"]
    out["entry_price_delta_pnl_same_exit"] = -signs * price_delta * out["volume"] * out["size"]
    out.loc[out["replay_open_price"].isna(), "entry_price_delta_pnl_same_exit"] = np.nan
    out["same_exit_replay_pnl"] = out["realized_pnl"] + out["entry_price_delta_pnl_same_exit"]
    out["replay_match_status"] = np.where(out["replay_open_price"].notna(), "initial_order_replay_ready", "unmatched_or_missing_replay")
    out["exit_date_ts"] = pd.to_datetime(out["exit_date"], errors="coerce").dt.normalize()
    return out


def _event_confusion(replay: pd.DataFrame) -> pd.DataFrame:
    data = replay.copy()
    data["official_event_family"] = data["official_event_family"].fillna("no_intraday_event")
    data["replay_event_family"] = data["replay_event_family"].fillna("missing")
    table = (
        data.groupby(["official_event_family", "replay_event_family"], dropna=False)
        .agg(
            orders=("candidate_index", "count"),
            abs_price_delta_median=("replay_open_abs_delta", "median"),
            event_family_match=("event_family_match", "sum"),
            first_stop_time_match=("first_stop_time_match", "sum"),
            reentry_time_match=("reentry_time_match", "sum"),
            retry_failed_time_match=("retry_failed_time_match", "sum"),
            c2_hit_time_match=("c2_hit_time_match", "sum"),
        )
        .reset_index()
        .sort_values(["official_event_family", "orders"], ascending=[True, False])
    )
    return table


def _sensitivity_curve(curve: pd.DataFrame, lot_sensitivity: pd.DataFrame) -> pd.DataFrame:
    out = curve[["date", "account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]].copy()
    lots = lot_sensitivity.copy()
    lots["exit_date_ts"] = pd.to_datetime(lots["exit_date_ts"], errors="coerce").dt.normalize()
    lots["delta_filled"] = pd.to_numeric(lots["entry_price_delta_pnl_same_exit"], errors="coerce").fillna(0.0)
    lots["delta_ready_only"] = pd.to_numeric(lots["entry_price_delta_pnl_same_exit"], errors="coerce")
    daily_delta = lots.groupby("exit_date_ts")["delta_filled"].sum()
    out["same_exit_entry_replay_delta"] = out["date"].map(daily_delta).fillna(0.0)
    out["cum_same_exit_entry_replay_delta"] = out["same_exit_entry_replay_delta"].cumsum()
    out["same_exit_replay_equity"] = out["account_equity"] + out["cum_same_exit_entry_replay_delta"]
    out["same_exit_replay_drawdown_pct"] = _drawdown_pct(out["same_exit_replay_equity"])
    return out


def _curve_metrics(curve: pd.DataFrame, equity_col: str) -> dict[str, float]:
    equity = pd.to_numeric(curve[equity_col], errors="coerce").ffill()
    previous = equity.shift(1)
    previous.iloc[0] = CAPITAL
    returns = (equity / previous - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    std = float(returns.std(ddof=1)) if len(returns) > 1 else 0.0
    return {
        "end_equity": float(equity.iloc[-1]),
        "total_return_pct": float((equity.iloc[-1] / CAPITAL - 1.0) * 100.0),
        "max_drawdown_pct": float(_drawdown_pct(equity).min()),
        "sharpe": float(returns.mean() / std * np.sqrt(TRADING_DAYS_PER_YEAR)) if std > 0 else 0.0,
    }


def _summary(
    curve: pd.DataFrame,
    lots: pd.DataFrame,
    replay: pd.DataFrame,
    lot_sensitivity: pd.DataFrame,
    sensitivity_curve: pd.DataFrame,
) -> pd.DataFrame:
    official = _official_metrics(curve, lots)
    audit = _curve_metrics(sensitivity_curve, "same_exit_replay_equity")
    replay_ready = replay[replay["stage861_day_ready"].eq(1)]
    matched = replay[replay["match_status"].astype(str).eq("matched_initial_open_trade")]
    delta = pd.to_numeric(lot_sensitivity["entry_price_delta_pnl_same_exit"], errors="coerce")
    event_match_rate = (
        float(pd.to_numeric(replay_ready["event_family_match"], errors="coerce").fillna(0).mean() * 100.0)
        if len(replay_ready)
        else 0.0
    )
    row = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        **official,
        "opened_candidates": int(len(replay)),
        "matched_initial_orders": int(len(matched)),
        "stage861_replay_ready_orders": int(len(replay_ready)),
        "unmatched_official_open_trades_after_initial_matching": int(
            pd.to_numeric(replay.get("unmatched_official_open_trades_after_initial_matching", 0), errors="coerce")
            .fillna(0)
            .max()
        ),
        "median_replay_open_abs_delta": float(pd.to_numeric(replay_ready["replay_open_abs_delta"], errors="coerce").median()),
        "p90_replay_open_abs_delta": float(pd.to_numeric(replay_ready["replay_open_abs_delta"], errors="coerce").quantile(0.9)),
        "max_replay_open_abs_delta": float(pd.to_numeric(replay_ready["replay_open_abs_delta"], errors="coerce").max()),
        "event_family_match_rate_pct": event_match_rate,
        "first_stop_time_match_count": int(pd.to_numeric(replay_ready.get("first_stop_time_match", 0), errors="coerce").fillna(0).sum()),
        "reentry_time_match_count": int(pd.to_numeric(replay_ready.get("reentry_time_match", 0), errors="coerce").fillna(0).sum()),
        "retry_failed_time_match_count": int(
            pd.to_numeric(replay_ready.get("retry_failed_time_match", 0), errors="coerce").fillna(0).sum()
        ),
        "c2_hit_time_match_count": int(pd.to_numeric(replay_ready.get("c2_hit_time_match", 0), errors="coerce").fillna(0).sum()),
        "closed_lots": int(len(lot_sensitivity)),
        "closed_lots_replay_ready": int(lot_sensitivity["replay_open_price"].notna().sum()),
        "same_exit_delta_pnl_sum_ready": float(delta.sum(skipna=True)),
        "same_exit_delta_pnl_median_ready": float(delta.median(skipna=True)),
        "same_exit_replay_end_equity": audit["end_equity"],
        "same_exit_replay_total_return_pct": audit["total_return_pct"],
        "same_exit_replay_max_drawdown_pct": audit["max_drawdown_pct"],
        "same_exit_replay_sharpe": audit["sharpe"],
        "decision": "stage038_order_event_replay_prototype_not_close_enough_no_trade_rule",
        "candidate_ready": 0,
        "ab_triggered": 0,
    }
    return pd.DataFrame([row])


def _plot_path(sensitivity: pd.DataFrame) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(16, 12), sharex=True, constrained_layout=True)
    axes[0].plot(sensitivity["date"], sensitivity["account_equity"], color="#111827", linewidth=1.2, label="official equity")
    axes[0].plot(
        sensitivity["date"],
        sensitivity["same_exit_replay_equity"],
        color="#dc2626",
        linewidth=1.0,
        label="same-exit first-minute replay entry sensitivity",
    )
    axes[0].set_title("Official equity vs same-exit replay-entry sensitivity")
    axes[0].grid(True, alpha=0.25)
    axes[0].legend(loc="best")

    axes[1].plot(sensitivity["date"], sensitivity["drawdown_pct"], color="#111827", linewidth=1.0, label="official DD")
    axes[1].plot(
        sensitivity["date"],
        sensitivity["same_exit_replay_drawdown_pct"],
        color="#dc2626",
        linewidth=1.0,
        label="same-exit replay DD",
    )
    axes[1].set_title("Drawdown comparison, audit only")
    axes[1].grid(True, alpha=0.25)
    axes[1].legend(loc="best")

    axes[2].plot(
        sensitivity["date"],
        sensitivity["cum_same_exit_entry_replay_delta"],
        color="#7c3aed",
        linewidth=1.1,
        label="cumulative entry price delta PnL",
    )
    axes[2].axhline(0, color="#6b7280", linewidth=0.8)
    axes[2].set_title("Cumulative PnL delta from replacing official entry with first Stage861 bar open")
    axes[2].grid(True, alpha=0.25)
    axes[2].legend(loc="best")
    fig.suptitle("Stage038 order-event replay prototype audit", fontsize=14)
    fig.savefig(PATH_CHART_OUT, dpi=150)
    plt.close(fig)


def _plot_confusion(confusion: pd.DataFrame) -> None:
    if confusion.empty:
        return
    pivot = confusion.pivot_table(
        index="official_event_family",
        columns="replay_event_family",
        values="orders",
        aggfunc="sum",
        fill_value=0,
    )
    fig, ax = plt.subplots(figsize=(12, 7), constrained_layout=True)
    im = ax.imshow(pivot.to_numpy(), cmap="Blues")
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=30, ha="right", fontsize=8)
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=8)
    for i in range(len(pivot.index)):
        for j in range(len(pivot.columns)):
            value = int(pivot.iloc[i, j])
            if value:
                ax.text(j, i, str(value), ha="center", va="center", color="#111827", fontsize=8)
    ax.set_title("Official intraday event family vs Stage038 replay event family")
    fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    fig.savefig(CONFUSION_CHART_OUT, dpi=150)
    plt.close(fig)


def _plot_scatter(replay: pd.DataFrame, lot_sensitivity: pd.DataFrame) -> None:
    agg = (
        lot_sensitivity.assign(realized_pnl=pd.to_numeric(lot_sensitivity["realized_pnl"], errors="coerce").fillna(0.0))
        .groupby("open_trade_id", dropna=False)
        .agg(open_trade_lot_pnl=("realized_pnl", "sum"))
        .reset_index()
    )
    data = replay.merge(agg, left_on="official_open_trade_id", right_on="open_trade_id", how="left")
    data = data[data["stage861_day_ready"].eq(1)].copy()
    if data.empty:
        return
    fig, ax = plt.subplots(figsize=(12, 7), constrained_layout=True)
    scatter = ax.scatter(
        data["official_open_price"],
        data["replay_open_minus_official"],
        c=pd.to_numeric(data["open_trade_lot_pnl"], errors="coerce").fillna(0.0).clip(-500_000, 500_000),
        cmap="RdYlGn",
        s=np.sqrt(pd.to_numeric(data["official_open_volume"], errors="coerce").fillna(1.0).clip(lower=1.0)) * 10,
        alpha=0.72,
        edgecolors="#374151",
        linewidths=0.25,
    )
    ax.axhline(0, color="#111827", linewidth=0.8)
    ax.set_xlabel("official open price")
    ax.set_ylabel("first Stage861 bar open - official open price")
    ax.set_title("Order replay fill delta by official open price")
    ax.grid(True, alpha=0.25)
    fig.colorbar(scatter, ax=ax, fraction=0.025, pad=0.02, label="official open-trade lot PnL clipped")
    fig.savefig(SCATTER_OUT, dpi=150)
    plt.close(fig)


def _select_atlas_rows(replay: pd.DataFrame) -> pd.DataFrame:
    data = replay.copy()
    data["event_family_match"] = pd.to_numeric(data.get("event_family_match"), errors="coerce").fillna(0)
    data["replay_open_abs_delta"] = pd.to_numeric(data.get("replay_open_abs_delta"), errors="coerce")
    mismatch = data[data["event_family_match"].eq(0) & data["stage861_day_ready"].eq(1)].copy()
    parts: list[pd.DataFrame] = []
    if not mismatch.empty:
        parts.append(mismatch.nlargest(ATLAS_ROWS // 2, "replay_open_abs_delta"))
    ready = data[data["stage861_day_ready"].eq(1)].copy()
    if not ready.empty:
        parts.append(ready.nlargest(ATLAS_ROWS // 2, "replay_open_abs_delta"))
    out = pd.concat(parts, ignore_index=True, sort=False) if parts else pd.DataFrame()
    if out.empty:
        return out
    return out.drop_duplicates(subset=["candidate_index", "official_open_trade_id"]).head(ATLAS_ROWS).reset_index(drop=True)


def _plot_atlas(replay: pd.DataFrame, groups: dict[str, pd.DataFrame]) -> tuple[list[Path], pd.DataFrame]:
    selected = _select_atlas_rows(replay)
    if selected.empty:
        _write_csv(pd.DataFrame(), ATLAS_MANIFEST_OUT)
        return [], pd.DataFrame()
    pages: list[Path] = []
    manifest_rows: list[dict[str, Any]] = []
    for page_idx, start in enumerate(range(0, len(selected), ATLAS_PER_PAGE), start=1):
        page_rows = selected.iloc[start : start + ATLAS_PER_PAGE].reset_index(drop=True)
        fig, axes = plt.subplots(len(page_rows), 1, figsize=(14, 3.4 * len(page_rows)), sharex=False, constrained_layout=True)
        if len(page_rows) == 1:
            axes = [axes]
        for ax, (_, row) in zip(axes, page_rows.iterrows()):
            day = s010._day_for_symbol(groups, str(row["vt_symbol"]), _normalize_day(row["official_open_date"]))
            if day.empty:
                ax.text(0.5, 0.5, "missing Stage861 day", ha="center", va="center")
                ax.set_axis_off()
            else:
                day = day.sort_values("bar_datetime").reset_index(drop=True)
                x = np.arange(len(day))
                close = pd.to_numeric(day["close"], errors="coerce")
                ax.plot(x, close, color="#2563eb", linewidth=0.9, label="Stage861 close")
                for column, color, label, style in [
                    ("official_open_price", "#111827", "official open", "--"),
                    ("replay_open_price", "#7c3aed", "replay open", "-"),
                    ("replay_c9_stop_price", "#dc2626", "C9 -0.5R stop", ":"),
                    ("replay_c9_progress_price", "#16a34a", "C9 +0.5R progress", ":"),
                    ("planned_stop_price", "#b91c1c", "planned/C2 stop", "-."),
                ]:
                    value = _safe_float(row.get(column))
                    if np.isfinite(value):
                        ax.axhline(value, color=color, linewidth=0.9, linestyle=style, label=label)
                for column, color, label in [
                    ("replay_open_datetime", "#7c3aed", "replay open time"),
                    ("replay_first_stop_time", "#dc2626", "replay C9 stop"),
                    ("replay_reentry_time", "#2563eb", "replay reentry"),
                    ("replay_retry_failed_time", "#7c2d12", "replay retry failed"),
                    ("replay_c2_hit_time", "#f97316", "replay C2 stop"),
                    ("official_first_stop_time", "#991b1b", "official first stop"),
                    ("official_hit_time", "#ea580c", "official C2 hit"),
                ]:
                    text = str(row.get(column, ""))
                    if not text or text == "nan":
                        continue
                    ts = pd.to_datetime(text, errors="coerce")
                    if pd.isna(ts):
                        continue
                    matches = np.flatnonzero(pd.to_datetime(day["bar_datetime"], errors="coerce").eq(ts).to_numpy())
                    if len(matches):
                        ax.axvline(int(matches[0]), color=color, linewidth=0.8, alpha=0.75, label=label)
                tick_positions = np.linspace(0, max(len(day) - 1, 0), num=min(6, len(day)), dtype=int)
                ax.set_xticks(tick_positions)
                ax.set_xticklabels([_hhmm(day.loc[pos, "bar_datetime"]) for pos in tick_positions], fontsize=8)
                ax.grid(True, alpha=0.25)
            title = (
                f"{row.get('official_open_trade_id')} {row.get('vt_symbol')} {row.get('official_open_date')} "
                f"{row.get('direction')} off={_safe_float(row.get('official_open_price')):g} "
                f"replay={_safe_float(row.get('replay_open_price')):g} "
                f"official={row.get('official_event_family')} replay={row.get('replay_event_family')} "
                f"match={int(_safe_float(row.get('event_family_match'), 0))}"
            )
            ax.set_title(title, fontsize=9)
            handles, labels = ax.get_legend_handles_labels()
            if handles:
                by_label = dict(zip(labels, handles))
                ax.legend(by_label.values(), by_label.keys(), loc="best", fontsize=7)
            manifest_rows.append(
                {
                    "page": page_idx,
                    "candidate_index": row.get("candidate_index"),
                    "official_open_trade_id": row.get("official_open_trade_id"),
                    "vt_symbol": row.get("vt_symbol"),
                    "official_open_date": row.get("official_open_date"),
                    "direction": row.get("direction"),
                    "official_open_price": row.get("official_open_price"),
                    "replay_open_price": row.get("replay_open_price"),
                    "replay_open_abs_delta": row.get("replay_open_abs_delta"),
                    "official_event_family": row.get("official_event_family"),
                    "replay_event_family": row.get("replay_event_family"),
                    "event_family_match": row.get("event_family_match"),
                }
            )
        output = Path(str(ATLAS_TEMPLATE).format(page=page_idx))
        fig.savefig(output, dpi=150)
        plt.close(fig)
        pages.append(output)
    manifest = pd.DataFrame(manifest_rows)
    _write_csv(manifest, ATLAS_MANIFEST_OUT)
    return pages, manifest


def _write_report(
    summary: pd.DataFrame,
    confusion: pd.DataFrame,
    replay: pd.DataFrame,
    lot_sensitivity: pd.DataFrame,
    atlas_paths: list[Path],
) -> None:
    row = summary.iloc[0].to_dict()
    top_delta = replay.sort_values("replay_open_abs_delta", ascending=False).head(10)
    event_counts = (
        replay.groupby(["official_event_family", "replay_event_family"], dropna=False)
        .size()
        .reset_index(name="orders")
        .sort_values("orders", ascending=False)
    )
    delta_ready = lot_sensitivity[lot_sensitivity["entry_price_delta_pnl_same_exit"].notna()].copy()
    lines = [
        "# Stage038 订单事件回放原型审计",
        "",
        "## 结论",
        "",
        "- 决策：`stage038_order_event_replay_prototype_not_close_enough_no_trade_rule`。",
        "- 本阶段只做 replay 账本审计，不新增交易规则、不改正式配置、不触发 A/B。",
        f"- opened candidates：`{int(row['opened_candidates'])}`；matched initial orders：`{int(row['matched_initial_orders'])}`；Stage861 replay ready：`{int(row['stage861_replay_ready_orders'])}`。",
        f"- replay first-bar open 与 official open 的绝对差：median `{row['median_replay_open_abs_delta']:.4f}`，p90 `{row['p90_replay_open_abs_delta']:.4f}`，max `{row['max_replay_open_abs_delta']:.4f}`。",
        f"- event family match rate：`{row['event_family_match_rate_pct']:.4f}%`；first-stop time match `{int(row['first_stop_time_match_count'])}`，reentry time match `{int(row['reentry_time_match_count'])}`，retry-failed time match `{int(row['retry_failed_time_match_count'])}`，C2 hit time match `{int(row['c2_hit_time_match_count'])}`。",
        "- 这说明 first Stage861 bar open + 固定 stop/retry/C2 顺序能形成独立审计账本，但还不能足够复现官方 ledger；在它通过前，不允许测试新的分钟进出场候选。",
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
        "## Same-Exit Entry Replay Sensitivity",
        "",
        "- 该曲线不是候选回测，只是把 matched initial orders 的 entry price 替换为 first Stage861 bar open，exit、volume、size 均保持 official ledger 不变，用于观察执行价差对路径的敏感性。",
        f"- same-exit replay 期末权益：`{row['same_exit_replay_end_equity']:.2f}`",
        f"- same-exit replay 总收益：`{row['same_exit_replay_total_return_pct']:.4f}%`",
        f"- same-exit replay 最大回撤：`{row['same_exit_replay_max_drawdown_pct']:.4f}%`",
        f"- same-exit replay Sharpe：`{row['same_exit_replay_sharpe']:.4f}`",
        f"- ready lots delta PnL sum：`{row['same_exit_delta_pnl_sum_ready']:.2f}`；median：`{row['same_exit_delta_pnl_median_ready']:.2f}`。",
        "",
        "## Event Confusion Top",
        "",
        _md_table(event_counts, max_rows=20),
        "",
        "## Confusion Metrics",
        "",
        _md_table(confusion, max_rows=30),
        "",
        "## Largest Replay Open Delta",
        "",
        _md_table(
            top_delta[
                [
                    "candidate_index",
                    "official_open_trade_id",
                    "vt_symbol",
                    "direction",
                    "official_open_date",
                    "official_open_price",
                    "replay_open_price",
                    "replay_open_abs_delta",
                    "official_event_family",
                    "replay_event_family",
                    "event_family_match",
                ]
            ],
            max_rows=10,
        ),
        "",
        "## Visuals",
        "",
        f"- same-exit sensitivity path chart：`{PATH_CHART_OUT}`",
        f"- event confusion chart：`{CONFUSION_CHART_OUT}`",
        f"- fill delta scatter：`{SCATTER_OUT}`",
        *[f"- atlas page：`{path}`" for path in atlas_paths],
        "",
        "## Files",
        "",
        f"- order replay ledger：`{ORDER_REPLAY_OUT}`",
        f"- closed lot sensitivity：`{CLOSED_LOT_SENSITIVITY_OUT}`",
        f"- event confusion：`{EVENT_CONFUSION_OUT}`",
        f"- sensitivity curve：`{SENSITIVITY_CURVE_OUT}`",
        f"- summary：`{SUMMARY_OUT}`",
        f"- decision：`{DECISION_OUT}`",
        "",
        "## 视觉观察",
        "",
        "- path chart 若与 official 明显偏离，说明只用 first Stage861 bar open 替代 official fill 会引入路径级执行误差；这不是收益候选。",
        "- confusion heatmap 若主对角线不足，说明 stop/retry/C2 事件顺序或 entry fill 仍未复现官方引擎，不能在此基础上测试分钟规则。",
        "- atlas 用最大价差和事件不匹配样本复核具体分钟路径，重点看偏差来自信号日/交易日、首 bar open、还是 stop/retry 触发顺序。",
        "",
        "## 后续",
        "",
        "- 下一步不是优化规则，而是修 order replay 与官方 engine 的一致性：优先解释 candidate -> open trade 匹配、first tradable minute 选择、bar open/close 时间戳、同 bar stop/progress 保守顺序和 reentry synthetic trade 计数差异。",
        "- 在 replay 账本没有通过一致性审计前，不测试任何新的分钟级开仓、恢复、降仓或退出规则。",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curve, open_trades, candidates, lots, intraday, _trades = _prepare_inputs()
    replay, groups = _build_order_replay(candidates, open_trades, intraday)
    lot_sensitivity = _closed_lot_sensitivity(lots, replay)
    confusion = _event_confusion(replay)
    sensitivity = _sensitivity_curve(curve, lot_sensitivity)
    summary = _summary(curve, lots, replay, lot_sensitivity, sensitivity)

    _write_csv(replay, ORDER_REPLAY_OUT)
    _write_csv(lot_sensitivity, CLOSED_LOT_SENSITIVITY_OUT)
    _write_csv(confusion, EVENT_CONFUSION_OUT)
    _write_csv(sensitivity, SENSITIVITY_CURVE_OUT)
    _write_csv(summary, SUMMARY_OUT)

    _plot_path(sensitivity)
    _plot_confusion(confusion)
    _plot_scatter(replay, lot_sensitivity)
    atlas_paths, _manifest = _plot_atlas(replay, groups)

    _write_report(summary, confusion, replay, lot_sensitivity, atlas_paths)

    row = summary.iloc[0].to_dict()
    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": row["decision"],
        "candidate_ready": 0,
        "ab_triggered": 0,
        "rule_added": 0,
        "official_config_changed": 0,
        "opened_candidates": int(row["opened_candidates"]),
        "matched_initial_orders": int(row["matched_initial_orders"]),
        "stage861_replay_ready_orders": int(row["stage861_replay_ready_orders"]),
        "event_family_match_rate_pct": float(row["event_family_match_rate_pct"]),
        "median_replay_open_abs_delta": float(row["median_replay_open_abs_delta"]),
        "p90_replay_open_abs_delta": float(row["p90_replay_open_abs_delta"]),
        "same_exit_delta_pnl_sum_ready": float(row["same_exit_delta_pnl_sum_ready"]),
        "judgment": (
            "The order-event replay prototype can create an independent audit ledger, "
            "but first-minute fills and replayed intraday events are not close enough to official trades."
        ),
        "overfit_guard": (
            "No year/product/direction/session/clock filter is promoted. The same-exit curve is a sensitivity audit, not a candidate."
        ),
        "next_step": (
            "Repair replay semantics against the official engine before testing any minute-level entry or exit rule."
        ),
        "outputs": {
            "order_replay": ORDER_REPLAY_OUT,
            "closed_lot_sensitivity": CLOSED_LOT_SENSITIVITY_OUT,
            "event_confusion": EVENT_CONFUSION_OUT,
            "sensitivity_curve": SENSITIVITY_CURVE_OUT,
            "summary": SUMMARY_OUT,
            "report": REPORT_OUT,
            "path_chart": PATH_CHART_OUT,
            "confusion_chart": CONFUSION_CHART_OUT,
            "scatter": SCATTER_OUT,
            "atlas_manifest": ATLAS_MANIFEST_OUT,
            "atlas_pages": atlas_paths,
        },
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
