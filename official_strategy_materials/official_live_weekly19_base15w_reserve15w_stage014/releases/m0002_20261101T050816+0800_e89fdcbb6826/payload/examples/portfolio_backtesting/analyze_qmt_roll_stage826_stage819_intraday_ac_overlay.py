from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage719_official_winner_trade_forensics as s719
import analyze_qmt_roll_stage825_stage819_intraday_rule_forensics as s825
import qmt_roll_official_candidate_stage819_30w_config as stage819_cfg


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage826"
MODEL_TAG = "stage826_stage819_intraday_ac_overlay_v1"
OUTPUT_PREFIX = "qmt_roll_stage826_stage819_intraday_ac_overlay"

START = pd.Timestamp("2018-01-01")
END = pd.Timestamp("2026-05-29")
CAPITAL = stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_CAPITAL

FAILFAST_WINDOW_BARS = 30
FAILFAST_STOP_R = 0.5
FAILFAST_CONFIRM_R = 0.5
FAILFAST_MAX_RETRIES = 2
QUALITY_STOP_R = 1.0
QUALITY_CONFIRM_R = 1.0

PER_PAGE = 4
MAX_CHANGED_ATLAS_PAGES = 12

STAGE825_CLOSED_PATH = OUTPUT_DIR / (
    "qmt_roll_stage825_stage819_intraday_rule_forensics_closed_lots_"
    "stage825_stage819_intraday_rule_forensics_v1.csv"
)
STAGE825_SUMMARY_PATH = OUTPUT_DIR / (
    "qmt_roll_stage825_stage819_intraday_rule_forensics_summary_"
    "stage825_stage819_intraday_rule_forensics_v1.csv"
)
STAGE825_CURVE_PATH = OUTPUT_DIR / (
    "qmt_roll_stage825_stage819_intraday_rule_forensics_curve_"
    "stage825_stage819_intraday_rule_forensics_v1.csv"
)

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CURVE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
LOT_OUTCOMES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_lot_outcomes_{MODEL_TAG}.csv"
EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_events_{MODEL_TAG}.csv"
YEARLY_DELTA_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_yearly_delta_{MODEL_TAG}.csv"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
ATLAS_MANIFEST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_changed_atlas_manifest_{MODEL_TAG}.csv"
CHART_PATH_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_changed_atlas_page{{page:03d}}_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    return s825._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s825._md_table(frame, max_rows=max_rows)


def _safe_float(value: Any, default: float = np.nan) -> float:
    return s825._safe_float(value, default=default)


def _direction_sign(direction: Any) -> float:
    return 1.0 if str(direction) == "long" else -1.0


def _date(value: Any) -> pd.Timestamp:
    return pd.Timestamp(value).normalize()


def _load_stage825_closed() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    missing = [
        path
        for path in [STAGE825_CLOSED_PATH, STAGE825_SUMMARY_PATH, STAGE825_CURVE_PATH]
        if not path.exists()
    ]
    if missing:
        raise RuntimeError(
            "Stage825 outputs are required before Stage826. Missing: "
            + ", ".join(str(path) for path in missing)
        )
    closed = pd.read_csv(STAGE825_CLOSED_PATH, encoding="utf-8-sig")
    summary = pd.read_csv(STAGE825_SUMMARY_PATH, encoding="utf-8-sig")
    curve = pd.read_csv(STAGE825_CURVE_PATH, encoding="utf-8-sig")
    for column in ["entry_date", "exit_date"]:
        closed[column] = pd.to_datetime(closed[column], errors="coerce").dt.normalize()
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    return closed, summary, curve


def _load_minute_bars(closed: pd.DataFrame) -> pd.DataFrame:
    vt_symbols = set(closed["vt_symbol"].astype(str).dropna().unique())
    return s825._load_minute_bars(vt_symbols)


def _minute_groups(minute_bars: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return s825._minute_groups(minute_bars)


_DAILY_BAR_CACHE: dict[str, pd.DataFrame] = {}


def _daily_bars(vt_symbol: str) -> pd.DataFrame:
    if vt_symbol not in _DAILY_BAR_CACHE:
        bars = s719._read_contract_bars(vt_symbol).copy()
        if bars.empty:
            bars = pd.DataFrame(columns=["date", "open", "high", "low", "close"])
        bars["date"] = pd.to_datetime(bars.get("date"), errors="coerce").dt.normalize()
        for column in ["open", "high", "low", "close"]:
            bars[column] = pd.to_numeric(bars.get(column), errors="coerce")
        bars = bars.dropna(subset=["date", "close"]).drop_duplicates("date").sort_values("date")
        _DAILY_BAR_CACHE[vt_symbol] = bars.reset_index(drop=True)
    return _DAILY_BAR_CACHE[vt_symbol]


def _exec_slippage(row: pd.Series, metadata: dict[str, Any]) -> float:
    vt_symbol = str(row["vt_symbol"])
    slip = float(metadata["slippages"].get(vt_symbol, 0.0) or 0.0)
    size = float(metadata["sizes"].get(vt_symbol, _safe_float(row.get("size"), 1.0)) or 1.0)
    volume = _safe_float(row.get("volume"), 0.0)
    return slip * size * volume


def _gross_trade_pnl(
    *,
    direction: str,
    entry_price: float,
    exit_price: float,
    size: float,
    volume: float,
) -> float:
    sign = _direction_sign(direction)
    return sign * (exit_price - entry_price) * size * volume


def _position_daily_gross_path(
    row: pd.Series,
    *,
    exit_date: pd.Timestamp,
    exit_price: float,
) -> list[dict[str, Any]]:
    vt_symbol = str(row["vt_symbol"])
    direction = str(row["direction"])
    entry_date = _date(row["entry_date"])
    entry_price = _safe_float(row.get("entry_price"))
    size = _safe_float(row.get("size"), 1.0)
    volume = _safe_float(row.get("volume"), 0.0)
    exit_date = _date(exit_date)

    if exit_date <= entry_date:
        pnl = _gross_trade_pnl(
            direction=direction,
            entry_price=entry_price,
            exit_price=exit_price,
            size=size,
            volume=volume,
        )
        return [{"date": entry_date, "gross_pnl": pnl, "source": "same_day_exit"}]

    bars = _daily_bars(vt_symbol)
    bars = bars[(bars["date"] >= entry_date) & (bars["date"] <= exit_date)].copy()
    if bars.empty or entry_price <= 0 or volume <= 0:
        pnl = _gross_trade_pnl(
            direction=direction,
            entry_price=entry_price,
            exit_price=exit_price,
            size=size,
            volume=volume,
        )
        return [{"date": exit_date, "gross_pnl": pnl, "source": "fallback_realized"}]

    sign = _direction_sign(direction)
    multiplier = size * volume
    prev_mark = entry_price
    rows: list[dict[str, Any]] = []
    seen_exit = False
    for item in bars.itertuples(index=False):
        current_date = _date(item.date)
        if current_date >= exit_date:
            pnl = sign * (exit_price - prev_mark) * multiplier
            rows.append({"date": exit_date, "gross_pnl": pnl, "source": "exit_mark"})
            seen_exit = True
            break
        mark = float(item.close)
        pnl = sign * (mark - prev_mark) * multiplier
        rows.append({"date": current_date, "gross_pnl": pnl, "source": "daily_mark"})
        prev_mark = mark

    if not seen_exit:
        pnl = sign * (exit_price - prev_mark) * multiplier
        rows.append({"date": exit_date, "gross_pnl": pnl, "source": "exit_fallback"})
    return rows


def _hit_stop(row: Any, *, direction: str, stop_price: float) -> bool:
    if direction == "long":
        return float(row.low) <= stop_price
    return float(row.high) >= stop_price


def _hit_target(row: Any, *, direction: str, target_price: float) -> bool:
    if direction == "long":
        return float(row.high) >= target_price
    return float(row.low) <= target_price


def _hit_reentry(row: Any, *, direction: str, entry_price: float) -> bool:
    if direction == "long":
        return float(row.high) >= entry_price
    return float(row.low) <= entry_price


def _event_record(
    *,
    rule_id: str,
    row: pd.Series,
    event_type: str,
    event_time: Any,
    price: float,
    note: str = "",
) -> dict[str, Any]:
    return {
        "rule_id": rule_id,
        "lot_id": int(row["lot_id"]),
        "vt_symbol": str(row["vt_symbol"]),
        "direction": str(row["direction"]),
        "event_type": event_type,
        "event_time": pd.Timestamp(event_time).isoformat() if event_time is not None and event_time != "" else "",
        "event_date": _date(event_time).strftime("%Y-%m-%d") if event_time is not None and event_time != "" else "",
        "price": price,
        "note": note,
    }


def _c1_failfast_retry_decision(
    row: pd.Series,
    entry_day: pd.DataFrame,
) -> dict[str, Any]:
    rule_id = "C1_failfast30_05r_retry2"
    direction = str(row["direction"])
    entry_date = _date(row["entry_date"])
    entry_price = _safe_float(row.get("entry_price"))
    risk_pct = _safe_float(row.get("entry_risk_distance_pct"))
    if not np.isfinite(risk_pct) or risk_pct <= 0:
        risk_pct = _safe_float(row.get("risk_pct"))
    if entry_day.empty or entry_price <= 0 or not np.isfinite(risk_pct) or risk_pct <= 0:
        return {
            "rule_id": rule_id,
            "final_open": True,
            "final_exit_date": _date(row["exit_date"]),
            "final_exit_price": _safe_float(row.get("exit_price")),
            "entry_day_extra_gross": 0.0,
            "stop_count": 0,
            "reentry_count": 0,
            "attempt_count": 1,
            "action": "missing_minutes_keep_original" if entry_day.empty else "invalid_risk_keep_original",
            "events": [],
            "first_event_time": "",
        }

    sign = _direction_sign(direction)
    risk_price = entry_price * risk_pct
    stop_price = entry_price - sign * FAILFAST_STOP_R * risk_price
    confirm_price = entry_price + sign * FAILFAST_CONFIRM_R * risk_price
    open_position = True
    confirmed = False
    bars_since_attempt = 0
    stop_count = 0
    reentry_count = 0
    entry_day_extra_gross = 0.0
    first_event_time = ""
    events: list[dict[str, Any]] = []

    for item in entry_day.itertuples(index=False):
        if open_position:
            bars_since_attempt += 1
            if confirmed:
                continue
            if bars_since_attempt > FAILFAST_WINDOW_BARS:
                confirmed = True
                events.append(
                    _event_record(
                        rule_id=rule_id,
                        row=row,
                        event_type="window_survived",
                        event_time=item.bar_datetime,
                        price=entry_price,
                        note="30 bars passed without unconfirmed 0.5R stop",
                    )
                )
                if not first_event_time:
                    first_event_time = pd.Timestamp(item.bar_datetime).isoformat()
                continue
            stop_hit = _hit_stop(item, direction=direction, stop_price=stop_price)
            target_hit = _hit_target(item, direction=direction, target_price=confirm_price)
            if stop_hit:
                stop_count += 1
                gross = _gross_trade_pnl(
                    direction=direction,
                    entry_price=entry_price,
                    exit_price=stop_price,
                    size=_safe_float(row.get("size"), 1.0),
                    volume=_safe_float(row.get("volume"), 0.0),
                )
                entry_day_extra_gross += gross
                open_position = False
                bars_since_attempt = 0
                note = "same_bar_conservative_stop_first" if target_hit else "failfast_stop_before_confirm"
                events.append(
                    _event_record(
                        rule_id=rule_id,
                        row=row,
                        event_type="stop",
                        event_time=item.bar_datetime,
                        price=stop_price,
                        note=note,
                    )
                )
                if not first_event_time:
                    first_event_time = pd.Timestamp(item.bar_datetime).isoformat()
                continue
            if target_hit:
                confirmed = True
                events.append(
                    _event_record(
                        rule_id=rule_id,
                        row=row,
                        event_type="confirm",
                        event_time=item.bar_datetime,
                        price=confirm_price,
                        note="0.5R favorable move before failfast stop",
                    )
                )
                if not first_event_time:
                    first_event_time = pd.Timestamp(item.bar_datetime).isoformat()
                continue
        else:
            if reentry_count >= FAILFAST_MAX_RETRIES:
                continue
            if _hit_reentry(item, direction=direction, entry_price=entry_price):
                reentry_count += 1
                open_position = True
                confirmed = False
                bars_since_attempt = 0
                events.append(
                    _event_record(
                        rule_id=rule_id,
                        row=row,
                        event_type="reentry",
                        event_time=item.bar_datetime,
                        price=entry_price,
                        note="price crossed original entry after stop",
                    )
                )
                if not first_event_time:
                    first_event_time = pd.Timestamp(item.bar_datetime).isoformat()

    if open_position:
        action = "survived_original_exit"
        if stop_count and reentry_count:
            action = "stopped_reentered_then_original_exit"
        return {
            "rule_id": rule_id,
            "final_open": True,
            "final_exit_date": _date(row["exit_date"]),
            "final_exit_price": _safe_float(row.get("exit_price")),
            "entry_day_extra_gross": entry_day_extra_gross,
            "stop_count": stop_count,
            "reentry_count": reentry_count,
            "attempt_count": 1 + reentry_count,
            "action": action,
            "events": events,
            "first_event_time": first_event_time,
        }

    return {
        "rule_id": rule_id,
        "final_open": False,
        "final_exit_date": entry_date,
        "final_exit_price": stop_price,
        "entry_day_extra_gross": entry_day_extra_gross,
        "stop_count": stop_count,
        "reentry_count": reentry_count,
        "attempt_count": 1 + reentry_count,
        "action": "stopped_no_final_reentry",
        "events": events,
        "first_event_time": first_event_time,
    }


def _c2_quality_1r_stop_decision(row: pd.Series, entry_day: pd.DataFrame) -> dict[str, Any]:
    rule_id = "C2_first1r_stop_if_before_target"
    direction = str(row["direction"])
    entry_date = _date(row["entry_date"])
    entry_price = _safe_float(row.get("entry_price"))
    risk_pct = _safe_float(row.get("entry_risk_distance_pct"))
    if not np.isfinite(risk_pct) or risk_pct <= 0:
        risk_pct = _safe_float(row.get("risk_pct"))
    if entry_day.empty or entry_price <= 0 or not np.isfinite(risk_pct) or risk_pct <= 0:
        return {
            "rule_id": rule_id,
            "final_open": True,
            "final_exit_date": _date(row["exit_date"]),
            "final_exit_price": _safe_float(row.get("exit_price")),
            "entry_day_extra_gross": 0.0,
            "stop_count": 0,
            "reentry_count": 0,
            "attempt_count": 1,
            "action": "missing_minutes_keep_original" if entry_day.empty else "invalid_risk_keep_original",
            "events": [],
            "first_event_time": "",
        }

    sign = _direction_sign(direction)
    risk_price = entry_price * risk_pct
    stop_price = entry_price - sign * QUALITY_STOP_R * risk_price
    target_price = entry_price + sign * QUALITY_CONFIRM_R * risk_price
    events: list[dict[str, Any]] = []
    for item in entry_day.itertuples(index=False):
        stop_hit = _hit_stop(item, direction=direction, stop_price=stop_price)
        target_hit = _hit_target(item, direction=direction, target_price=target_price)
        if stop_hit:
            gross = _gross_trade_pnl(
                direction=direction,
                entry_price=entry_price,
                exit_price=stop_price,
                size=_safe_float(row.get("size"), 1.0),
                volume=_safe_float(row.get("volume"), 0.0),
            )
            note = "same_bar_conservative_stop_first" if target_hit else "1R stop before 1R target"
            events.append(
                _event_record(
                    rule_id=rule_id,
                    row=row,
                    event_type="stop",
                    event_time=item.bar_datetime,
                    price=stop_price,
                    note=note,
                )
            )
            return {
                "rule_id": rule_id,
                "final_open": False,
                "final_exit_date": entry_date,
                "final_exit_price": stop_price,
                "entry_day_extra_gross": gross,
                "stop_count": 1,
                "reentry_count": 0,
                "attempt_count": 1,
                "action": "stopped_before_1r_confirm",
                "events": events,
                "first_event_time": pd.Timestamp(item.bar_datetime).isoformat(),
            }
        if target_hit:
            events.append(
                _event_record(
                    rule_id=rule_id,
                    row=row,
                    event_type="confirm",
                    event_time=item.bar_datetime,
                    price=target_price,
                    note="1R favorable move before 1R stop",
                )
            )
            return {
                "rule_id": rule_id,
                "final_open": True,
                "final_exit_date": _date(row["exit_date"]),
                "final_exit_price": _safe_float(row.get("exit_price")),
                "entry_day_extra_gross": 0.0,
                "stop_count": 0,
                "reentry_count": 0,
                "attempt_count": 1,
                "action": "confirmed_original_exit",
                "events": events,
                "first_event_time": pd.Timestamp(item.bar_datetime).isoformat(),
            }

    return {
        "rule_id": rule_id,
        "final_open": True,
        "final_exit_date": _date(row["exit_date"]),
        "final_exit_price": _safe_float(row.get("exit_price")),
        "entry_day_extra_gross": 0.0,
        "stop_count": 0,
        "reentry_count": 0,
        "attempt_count": 1,
        "action": "neither_keep_original",
        "events": events,
        "first_event_time": "",
    }


def _entry_day_bars(row: pd.Series, minute_by_symbol: dict[str, pd.DataFrame]) -> pd.DataFrame:
    bars = minute_by_symbol.get(str(row["vt_symbol"]), pd.DataFrame())
    if bars.empty:
        return pd.DataFrame()
    entry_date = _date(row["entry_date"])
    return bars[bars["bar_date"].eq(entry_date)].copy().reset_index(drop=True)


def _simulate_rule(
    rule_id: str,
    closed: pd.DataFrame,
    minute_by_symbol: dict[str, pd.DataFrame],
    metadata: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    lot_rows: list[dict[str, Any]] = []
    event_rows: list[dict[str, Any]] = []
    for _, row in closed.iterrows():
        entry_day = _entry_day_bars(row, minute_by_symbol)
        original_gross = _safe_float(row.get("realized_pnl"), 0.0)
        base_exec_cost = _exec_slippage(row, metadata)
        original_slippage = 2.0 * base_exec_cost
        original_net = original_gross - original_slippage

        if rule_id == "A_original_lot_mark":
            decision = {
                "rule_id": rule_id,
                "final_open": True,
                "final_exit_date": _date(row["exit_date"]),
                "final_exit_price": _safe_float(row.get("exit_price")),
                "entry_day_extra_gross": 0.0,
                "stop_count": 0,
                "reentry_count": 0,
                "attempt_count": 1,
                "action": "original",
                "events": [],
                "first_event_time": "",
            }
        elif rule_id == "C1_failfast30_05r_retry2":
            decision = _c1_failfast_retry_decision(row, entry_day)
        elif rule_id == "C2_first1r_stop_if_before_target":
            decision = _c2_quality_1r_stop_decision(row, entry_day)
        else:
            raise ValueError(f"Unknown rule_id: {rule_id}")

        gross_events: list[dict[str, Any]] = []
        if float(decision["entry_day_extra_gross"]):
            gross_events.append(
                {
                    "date": _date(row["entry_date"]),
                    "gross_pnl": float(decision["entry_day_extra_gross"]),
                    "source": "entry_day_overlay",
                }
            )
        if bool(decision["final_open"]):
            gross_events.extend(
                _position_daily_gross_path(
                    row,
                    exit_date=_date(decision["final_exit_date"]),
                    exit_price=float(decision["final_exit_price"]),
                )
            )
        adjusted_gross = float(sum(float(item["gross_pnl"]) for item in gross_events))

        exec_count = 1 + int(decision["stop_count"]) + int(decision["reentry_count"])
        if bool(decision["final_open"]):
            exec_count += 1
        adjusted_slippage = exec_count * base_exec_cost
        adjusted_net = adjusted_gross - adjusted_slippage

        for item in gross_events:
            event_rows.append(
                {
                    "rule_id": rule_id,
                    "lot_id": int(row["lot_id"]),
                    "date": _date(item["date"]).strftime("%Y-%m-%d"),
                    "event_type": "gross_pnl",
                    "gross_pnl": float(item["gross_pnl"]),
                    "slippage": 0.0,
                    "trade_count": 0,
                    "source": item["source"],
                }
            )
        entry_date = _date(row["entry_date"])
        event_rows.append(
            {
                "rule_id": rule_id,
                "lot_id": int(row["lot_id"]),
                "date": entry_date.strftime("%Y-%m-%d"),
                "event_type": "slippage",
                "gross_pnl": 0.0,
                "slippage": base_exec_cost,
                "trade_count": 0,
                "source": "open",
            }
        )
        for _ in range(int(decision["stop_count"])):
            event_rows.append(
                {
                    "rule_id": rule_id,
                    "lot_id": int(row["lot_id"]),
                    "date": entry_date.strftime("%Y-%m-%d"),
                    "event_type": "slippage",
                    "gross_pnl": 0.0,
                    "slippage": base_exec_cost,
                    "trade_count": 0,
                    "source": "stop_close",
                }
            )
        for _ in range(int(decision["reentry_count"])):
            event_rows.append(
                {
                    "rule_id": rule_id,
                    "lot_id": int(row["lot_id"]),
                    "date": entry_date.strftime("%Y-%m-%d"),
                    "event_type": "slippage",
                    "gross_pnl": 0.0,
                    "slippage": base_exec_cost,
                    "trade_count": 0,
                    "source": "reentry_open",
                }
            )
        if bool(decision["final_open"]):
            event_rows.append(
                {
                    "rule_id": rule_id,
                    "lot_id": int(row["lot_id"]),
                    "date": _date(decision["final_exit_date"]).strftime("%Y-%m-%d"),
                    "event_type": "slippage",
                    "gross_pnl": 0.0,
                    "slippage": base_exec_cost,
                    "trade_count": 0,
                    "source": "final_close",
                }
            )

        for event in decision.get("events", []):
            event_rows.append(
                {
                    "rule_id": rule_id,
                    "lot_id": int(row["lot_id"]),
                    "date": str(event.get("event_date", "")),
                    "event_type": str(event.get("event_type", "")),
                    "gross_pnl": 0.0,
                    "slippage": 0.0,
                    "trade_count": 0,
                    "source": str(event.get("note", "")),
                    "event_time": str(event.get("event_time", "")),
                    "price": event.get("price", np.nan),
                }
            )

        lot_rows.append(
            {
                "rule_id": rule_id,
                "lot_id": int(row["lot_id"]),
                "open_trade_id": str(row.get("open_trade_id", "")),
                "close_trade_id": str(row.get("close_trade_id", "")),
                "vt_symbol": str(row["vt_symbol"]),
                "product": str(row.get("product", "")),
                "direction": str(row["direction"]),
                "entry_date": entry_date.strftime("%Y-%m-%d"),
                "original_exit_date": _date(row["exit_date"]).strftime("%Y-%m-%d"),
                "adjusted_exit_date": _date(decision["final_exit_date"]).strftime("%Y-%m-%d"),
                "entry_price": _safe_float(row.get("entry_price")),
                "original_exit_price": _safe_float(row.get("exit_price")),
                "adjusted_exit_price": _safe_float(decision["final_exit_price"]),
                "volume": _safe_float(row.get("volume"), 0.0),
                "size": _safe_float(row.get("size"), 1.0),
                "risk_pct": _safe_float(row.get("entry_risk_distance_pct")),
                "original_gross_pnl": original_gross,
                "adjusted_gross_pnl": adjusted_gross,
                "gross_delta": adjusted_gross - original_gross,
                "original_slippage": original_slippage,
                "adjusted_slippage": adjusted_slippage,
                "slippage_delta": adjusted_slippage - original_slippage,
                "original_net_pnl": original_net,
                "adjusted_net_pnl": adjusted_net,
                "net_delta": adjusted_net - original_net,
                "original_trade_count": np.nan,
                "adjusted_trade_count": np.nan,
                "trade_count_delta": np.nan,
                "lot_level_exec_count_proxy": exec_count,
                "stop_count": int(decision["stop_count"]),
                "reentry_count": int(decision["reentry_count"]),
                "attempt_count": int(decision["attempt_count"]),
                "final_open": int(bool(decision["final_open"])),
                "action": str(decision["action"]),
                "first_event_time": str(decision.get("first_event_time", "")),
                "minute_covered": int(not entry_day.empty),
                "entry_day_minute_bars": int(len(entry_day)),
                "original_r_multiple": _safe_float(row.get("r_multiple")),
                "adjusted_r_multiple": adjusted_gross / _safe_float(row.get("risk_amount"), np.nan),
                "exit_reason": str(row.get("exit_reason", "")),
                "signal": str(row.get("signal", "")),
            }
        )
    lot_frame = pd.DataFrame(lot_rows)
    event_rows.extend(_trade_count_events(rule_id, lot_frame))
    return lot_frame, pd.DataFrame(event_rows)


def _trade_count_events(rule_id: str, lot_frame: pd.DataFrame) -> list[dict[str, Any]]:
    if lot_frame.empty:
        return []
    rows: list[dict[str, Any]] = []

    def _add_grouped_counts(frame: pd.DataFrame, *, date_column: str, source: str) -> None:
        if frame.empty:
            return
        data = frame.copy()
        data["date"] = pd.to_datetime(data[date_column], errors="coerce").dt.normalize()
        for date, group in data.groupby("date", dropna=True):
            rows.append(
                {
                    "rule_id": rule_id,
                    "lot_id": 0,
                    "date": pd.Timestamp(date).strftime("%Y-%m-%d"),
                    "event_type": "trade_count",
                    "gross_pnl": 0.0,
                    "slippage": 0.0,
                    "trade_count": float(len(group)),
                    "source": source,
                }
            )

    opened = lot_frame[["open_trade_id", "entry_date"]].dropna().copy()
    opened = opened[opened["open_trade_id"].astype(str).ne("")]
    opened = opened.drop_duplicates("open_trade_id")
    _add_grouped_counts(opened, date_column="entry_date", source="unique_original_open")

    final_closed = lot_frame[pd.to_numeric(lot_frame["final_open"], errors="coerce").fillna(0).eq(1)].copy()
    final_closed = final_closed[["close_trade_id", "adjusted_exit_date"]].dropna()
    final_closed = final_closed[final_closed["close_trade_id"].astype(str).ne("")]
    final_closed = final_closed.drop_duplicates("close_trade_id")
    _add_grouped_counts(final_closed, date_column="adjusted_exit_date", source="unique_original_close")

    synthetic = lot_frame.copy()
    synthetic["entry_date"] = pd.to_datetime(synthetic["entry_date"], errors="coerce").dt.normalize()
    synthetic["stop_count"] = pd.to_numeric(synthetic["stop_count"], errors="coerce").fillna(0.0)
    synthetic["reentry_count"] = pd.to_numeric(synthetic["reentry_count"], errors="coerce").fillna(0.0)
    for date, group in synthetic.groupby("entry_date", dropna=True):
        stop_count = float(group["stop_count"].sum())
        reentry_count = float(group["reentry_count"].sum())
        if stop_count:
            rows.append(
                {
                    "rule_id": rule_id,
                    "lot_id": 0,
                    "date": pd.Timestamp(date).strftime("%Y-%m-%d"),
                    "event_type": "trade_count",
                    "gross_pnl": 0.0,
                    "slippage": 0.0,
                    "trade_count": stop_count,
                    "source": "synthetic_stop_close",
                }
            )
        if reentry_count:
            rows.append(
                {
                    "rule_id": rule_id,
                    "lot_id": 0,
                    "date": pd.Timestamp(date).strftime("%Y-%m-%d"),
                    "event_type": "trade_count",
                    "gross_pnl": 0.0,
                    "slippage": 0.0,
                    "trade_count": reentry_count,
                    "source": "synthetic_reentry_open",
                }
            )
    return rows


def _build_curves(events: pd.DataFrame, base_dates: pd.Series) -> tuple[pd.DataFrame, pd.DataFrame]:
    all_dates = pd.DataFrame({"date": pd.to_datetime(base_dates, errors="coerce").dt.normalize().dropna().unique()})
    all_dates = all_dates.sort_values("date").reset_index(drop=True)
    curve_rows: list[pd.DataFrame] = []
    summary_rows: list[dict[str, Any]] = []
    for rule_id, group in events.groupby("rule_id", sort=False):
        daily = group.copy()
        daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
        daily["gross_pnl"] = pd.to_numeric(daily.get("gross_pnl"), errors="coerce").fillna(0.0)
        daily["slippage"] = pd.to_numeric(daily.get("slippage"), errors="coerce").fillna(0.0)
        daily["trade_count"] = pd.to_numeric(daily.get("trade_count"), errors="coerce").fillna(0.0)
        agg = (
            daily.groupby("date", dropna=True)[["gross_pnl", "slippage", "trade_count"]]
            .sum()
            .reset_index()
        )
        curve = all_dates.merge(agg, on="date", how="left").fillna({"gross_pnl": 0.0, "slippage": 0.0, "trade_count": 0.0})
        curve["rule_id"] = rule_id
        curve["net_pnl"] = curve["gross_pnl"] - curve["slippage"]
        curve["equity"] = CAPITAL + curve["net_pnl"].cumsum()
        curve["nav"] = curve["equity"] / CAPITAL
        curve["running_max"] = curve["equity"].cummax()
        curve["drawdown_pct"] = (curve["equity"] / curve["running_max"] - 1.0) * 100.0
        prev_equity = curve["equity"].shift(1).fillna(CAPITAL)
        curve["daily_return"] = np.where(prev_equity.ne(0), curve["net_pnl"] / prev_equity, 0.0)
        curve_rows.append(curve)

        returns = curve["daily_return"].replace([np.inf, -np.inf], np.nan).fillna(0.0)
        std = float(returns.std(ddof=1))
        sharpe = float(returns.mean() / std * math.sqrt(252.0)) if std > 0 else np.nan
        nonzero = curve[curve["net_pnl"].abs().gt(1e-9)]
        win_rate = float(nonzero["net_pnl"].gt(0).mean() * 100.0) if len(nonzero) else np.nan
        summary_rows.append(
            {
                "rule_id": rule_id,
                "end_equity": float(curve["equity"].iloc[-1]) if len(curve) else CAPITAL,
                "total_return_pct": float((curve["equity"].iloc[-1] / CAPITAL - 1.0) * 100.0) if len(curve) else 0.0,
                "max_dd_pct": float(curve["drawdown_pct"].min()) if len(curve) else 0.0,
                "sharpe": sharpe,
                "total_slippage": float(curve["slippage"].sum()),
                "total_trade_count": float(curve["trade_count"].sum()),
                "nonzero_daily_win_rate_pct": win_rate,
                "total_gross_pnl": float(curve["gross_pnl"].sum()),
                "total_net_pnl": float(curve["net_pnl"].sum()),
                "active_days": int(len(nonzero)),
            }
        )
    curves = pd.concat(curve_rows, ignore_index=True, sort=False) if curve_rows else pd.DataFrame()
    summary = pd.DataFrame(summary_rows)
    if not summary.empty:
        summary.sort_values("rule_id", inplace=True)
    return summary, curves


def _yearly_delta(lots: pd.DataFrame) -> pd.DataFrame:
    if lots.empty:
        return pd.DataFrame()
    data = lots.copy()
    data["entry_year"] = pd.to_datetime(data["entry_date"], errors="coerce").dt.year
    rows: list[dict[str, Any]] = []
    for keys, group in data.groupby(["rule_id", "entry_year"], dropna=False):
        rows.append(
            {
                "rule_id": keys[0],
                "entry_year": int(keys[1]) if not pd.isna(keys[1]) else 0,
                "lots": int(len(group)),
                "minute_covered_lots": int(pd.to_numeric(group["minute_covered"], errors="coerce").fillna(0).sum()),
                "changed_lots": int(group["action"].astype(str).ne("original").sum())
                if keys[0] == "A_original_lot_mark"
                else int(group["net_delta"].abs().gt(1e-9).sum()),
                "stop_lots": int(pd.to_numeric(group["stop_count"], errors="coerce").fillna(0).gt(0).sum()),
                "reentry_lots": int(pd.to_numeric(group["reentry_count"], errors="coerce").fillna(0).gt(0).sum()),
                "gross_delta": float(pd.to_numeric(group["gross_delta"], errors="coerce").sum()),
                "slippage_delta": float(pd.to_numeric(group["slippage_delta"], errors="coerce").sum()),
                "net_delta": float(pd.to_numeric(group["net_delta"], errors="coerce").sum()),
            }
        )
    return pd.DataFrame(rows).sort_values(["rule_id", "entry_year"]).reset_index(drop=True)


def _action_stats(lots: pd.DataFrame) -> pd.DataFrame:
    if lots.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for keys, group in lots.groupby(["rule_id", "action"], dropna=False):
        rows.append(
            {
                "rule_id": keys[0],
                "action": keys[1],
                "lots": int(len(group)),
                "gross_delta": float(pd.to_numeric(group["gross_delta"], errors="coerce").sum()),
                "slippage_delta": float(pd.to_numeric(group["slippage_delta"], errors="coerce").sum()),
                "net_delta": float(pd.to_numeric(group["net_delta"], errors="coerce").sum()),
                "avg_net_delta": float(pd.to_numeric(group["net_delta"], errors="coerce").mean()),
                "stop_lots": int(pd.to_numeric(group["stop_count"], errors="coerce").fillna(0).gt(0).sum()),
                "reentry_lots": int(pd.to_numeric(group["reentry_count"], errors="coerce").fillna(0).gt(0).sum()),
            }
        )
    return pd.DataFrame(rows).sort_values(["rule_id", "net_delta"], ascending=[True, False]).reset_index(drop=True)


def _plot_candles(ax: plt.Axes, bars: pd.DataFrame) -> None:
    width = 0.64
    for idx, row in enumerate(bars.itertuples(index=False)):
        open_price = float(row.open)
        high_price = float(row.high)
        low_price = float(row.low)
        close_price = float(row.close)
        color = "#dc2626" if close_price >= open_price else "#059669"
        ax.vlines(idx, low_price, high_price, color=color, linewidth=0.7, alpha=0.9)
        lower = min(open_price, close_price)
        height = abs(close_price - open_price)
        if height <= 0:
            height = max(high_price - low_price, 1.0) * 0.006
            lower -= height / 2.0
        ax.add_patch(
            plt.Rectangle(
                (idx - width / 2.0, lower),
                width,
                height,
                facecolor=color,
                edgecolor=color,
                linewidth=0.35,
                alpha=0.75,
            )
        )


def _event_x_positions(events: pd.DataFrame, bars: pd.DataFrame) -> list[tuple[int, str, float]]:
    if events.empty or bars.empty:
        return []
    bar_times = pd.to_datetime(bars["bar_datetime"], errors="coerce").reset_index(drop=True)
    rows: list[tuple[int, str, float]] = []
    data = events.copy()
    data["event_time"] = pd.to_datetime(data.get("event_time"), errors="coerce")
    data["price"] = pd.to_numeric(data.get("price"), errors="coerce")
    data = data.dropna(subset=["event_time"])
    for event in data.itertuples(index=False):
        diffs = (bar_times - event.event_time).abs()
        if diffs.empty:
            continue
        idx = int(diffs.idxmin())
        rows.append((idx, str(event.event_type), float(event.price) if np.isfinite(event.price) else np.nan))
    return rows


def _plot_changed_lot(
    ax: plt.Axes,
    row: pd.Series,
    minute_by_symbol: dict[str, pd.DataFrame],
    event_lookup: dict[tuple[str, int], pd.DataFrame],
) -> dict[str, Any]:
    lot_id = int(row["lot_id"])
    vt_symbol = str(row["vt_symbol"])
    rule_id = str(row["rule_id"])
    entry_date = _date(row["entry_date"])
    bars = minute_by_symbol.get(vt_symbol, pd.DataFrame())
    entry_day = bars[bars["bar_date"].eq(entry_date)].copy() if not bars.empty else pd.DataFrame()
    record = {"rule_id": rule_id, "lot_id": lot_id, "chart_missing_minutes": int(entry_day.empty), "chart_page": 0}
    if entry_day.empty:
        ax.axis("off")
        ax.text(
            0.5,
            0.5,
            f"missing entry-day minute bars\n{rule_id} lot{lot_id} {vt_symbol}\nnet_delta={float(row.net_delta):,.0f}",
            ha="center",
            va="center",
            fontsize=10,
            color="#991b1b",
        )
        return record

    window = entry_day.head(240).copy().reset_index(drop=True)
    _plot_candles(ax, window)
    x = np.arange(len(window))
    ax.plot(x, window["close"].rolling(5).mean(), color="#f59e0b", linewidth=0.8, alpha=0.8)
    ax.plot(x, window["close"].rolling(20).mean(), color="#2563eb", linewidth=0.8, alpha=0.75)
    entry_price = float(row.entry_price)
    risk_pct = _safe_float(row.get("risk_pct"))
    direction = str(row.direction)
    sign = _direction_sign(direction)
    ax.axhline(entry_price, color="#1d4ed8", linewidth=1.0, alpha=0.85)
    if risk_pct > 0 and entry_price > 0:
        ax.axhline(entry_price * (1.0 - sign * 0.5 * risk_pct), color="#ef4444", linewidth=0.9, alpha=0.75)
        ax.axhline(entry_price * (1.0 + sign * 0.5 * risk_pct), color="#16a34a", linewidth=0.75, alpha=0.55)
        ax.axhline(entry_price * (1.0 - sign * 1.0 * risk_pct), color="#991b1b", linewidth=0.9, alpha=0.85)
        ax.axhline(entry_price * (1.0 + sign * 1.0 * risk_pct), color="#15803d", linewidth=0.9, alpha=0.85)
    events = event_lookup.get((rule_id, lot_id), pd.DataFrame())
    colors = {"stop": "#b91c1c", "reentry": "#7c3aed", "confirm": "#15803d", "window_survived": "#475569"}
    for idx, event_type, price in _event_x_positions(events, window):
        color = colors.get(event_type, "#111827")
        ax.axvline(idx, color=color, linestyle="--", linewidth=0.8, alpha=0.8)
        if np.isfinite(price):
            ax.scatter([idx], [price], color=color, s=18, zorder=5)
        ax.text(idx, ax.get_ylim()[1], event_type, rotation=90, va="top", fontsize=6, color=color)
    ticks = np.linspace(0, len(window) - 1, num=min(7, len(window)), dtype=int)
    labels = [pd.Timestamp(window.loc[pos, "bar_datetime"]).strftime("%H:%M") for pos in ticks]
    ax.set_xticks(ticks)
    ax.set_xticklabels(labels, rotation=0, fontsize=7)
    ax.tick_params(axis="y", labelsize=7)
    ax.grid(True, alpha=0.18, linewidth=0.5)
    ax.set_title(
        (
            f"{rule_id} lot{lot_id} {vt_symbol} {direction} {entry_date:%Y-%m-%d} "
            f"action={row.action} net_delta={float(row.net_delta):,.0f} "
            f"orig={float(row.original_net_pnl):,.0f} adj={float(row.adjusted_net_pnl):,.0f}"
        ),
        fontsize=8.5,
        loc="left",
    )
    return record


def _plot_changed_atlas(
    lots: pd.DataFrame,
    events: pd.DataFrame,
    minute_bars: pd.DataFrame,
) -> tuple[list[Path], pd.DataFrame]:
    candidates = lots[lots["rule_id"].ne("A_original_lot_mark")].copy()
    candidates = candidates[candidates["net_delta"].abs().gt(1e-9)].copy()
    if candidates.empty:
        return [], pd.DataFrame()
    candidates["abs_delta"] = pd.to_numeric(candidates["net_delta"], errors="coerce").abs()
    candidates.sort_values(["abs_delta", "entry_date", "lot_id"], ascending=[False, True, True], inplace=True)
    total_pages = int(math.ceil(len(candidates) / PER_PAGE))
    total_pages = min(total_pages, MAX_CHANGED_ATLAS_PAGES)
    minute_by_symbol = _minute_groups(minute_bars)
    event_lookup = {
        (str(rule_id), int(lot_id)): group.copy()
        for (rule_id, lot_id), group in events.groupby(["rule_id", "lot_id"], dropna=False)
        if str(rule_id) != "A_original_lot_mark"
    }
    paths: list[Path] = []
    records: list[dict[str, Any]] = []
    for page in range(1, total_pages + 1):
        part = candidates.iloc[(page - 1) * PER_PAGE : page * PER_PAGE].copy()
        fig, axes = plt.subplots(len(part), 1, figsize=(18, max(4.0, 3.2 * len(part))), constrained_layout=True)
        if len(part) == 1:
            axes = [axes]
        for ax, (_, row) in zip(axes, part.iterrows(), strict=False):
            rec = _plot_changed_lot(ax, row, minute_by_symbol, event_lookup)
            rec["chart_page"] = page
            records.append(rec)
        fig.suptitle(
            (
                "Stage826 changed-lot minute overlay atlas "
                f"(page {page}/{total_pages}; blue=entry, red=0.5R/1R stop, green=0.5R/1R confirm)"
            ),
            fontsize=13,
        )
        path = Path(str(CHART_PATH_TEMPLATE).format(page=page))
        fig.savefig(path, dpi=150)
        plt.close(fig)
        paths.append(path)
    return paths, pd.DataFrame(records)


def _write_report(
    official_summary: pd.DataFrame,
    summary: pd.DataFrame,
    lots: pd.DataFrame,
    yearly: pd.DataFrame,
    action_stats: pd.DataFrame,
    chart_paths: list[Path],
) -> None:
    official = official_summary.iloc[0].to_dict()
    original = summary[summary["rule_id"].eq("A_original_lot_mark")].iloc[0].to_dict()
    validation = pd.DataFrame(
        [
            {
                "check": "official_vs_lot_sim_end_equity",
                "official": official.get("end_equity"),
                "lot_sim": original.get("end_equity"),
                "diff": float(original.get("end_equity", np.nan)) - float(official.get("end_equity", np.nan)),
            },
            {
                "check": "official_vs_lot_sim_slippage",
                "official": official.get("total_slippage"),
                "lot_sim": original.get("total_slippage"),
                "diff": float(original.get("total_slippage", np.nan)) - float(official.get("total_slippage", np.nan)),
            },
            {
                "check": "official_vs_lot_sim_trade_count",
                "official": official.get("total_trade_count"),
                "lot_sim": original.get("total_trade_count"),
                "diff": float(original.get("total_trade_count", np.nan)) - float(official.get("total_trade_count", np.nan)),
            },
        ]
    )
    delta = summary.merge(
        summary[summary["rule_id"].eq("A_original_lot_mark")][
            ["end_equity", "total_return_pct", "max_dd_pct", "sharpe", "total_slippage", "total_trade_count"]
        ].rename(
            columns={
                "end_equity": "base_end_equity",
                "total_return_pct": "base_total_return_pct",
                "max_dd_pct": "base_max_dd_pct",
                "sharpe": "base_sharpe",
                "total_slippage": "base_total_slippage",
                "total_trade_count": "base_total_trade_count",
            }
        ),
        how="cross",
    )
    for column in ["end_equity", "total_return_pct", "max_dd_pct", "sharpe", "total_slippage", "total_trade_count"]:
        delta[f"{column}_delta_vs_A"] = delta[column] - delta[f"base_{column}"]
    display_summary = delta[
        [
            "rule_id",
            "end_equity",
            "end_equity_delta_vs_A",
            "total_return_pct",
            "max_dd_pct",
            "max_dd_pct_delta_vs_A",
            "sharpe",
            "sharpe_delta_vs_A",
            "total_slippage",
            "total_slippage_delta_vs_A",
            "total_trade_count",
            "total_trade_count_delta_vs_A",
            "nonzero_daily_win_rate_pct",
        ]
    ].copy()

    lines = [
        "# Stage826 Stage819候选分钟级A/C overlay",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 源候选：`{stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION}`",
        f"- 区间：`{START.date()}` 到 `{END.date()}`",
        "- 阶段性质：候选内部 lot-level minute overlay A/C；不改正式配置、不连接 CTP、不调用下单。",
        "",
        "## 规则语义",
        "",
        "- A：原始 Stage819 closed lots，按日线逐日盯市复算，用来校验 overlay 口径。",
        f"- C1：入场后 `{FAILFAST_WINDOW_BARS}` 根1分钟K内，若先打到 `{FAILFAST_STOP_R}R` 逆向且未先到 `{FAILFAST_CONFIRM_R}R` 顺向，则实时止损；之后价格重新穿越原入场价允许最多 `{FAILFAST_MAX_RETRIES}` 次重试。",
        f"- C2：入场日逐分钟比较 `{QUALITY_STOP_R}R` 逆向止损与 `{QUALITY_CONFIRM_R}R` 顺向确认；若止损先发生则立即退出，确认先发生或都未发生则保持原始退出。",
        "- 同一根K同时触发止损与确认时，按保守口径视为止损先发生。",
        "- 分钟缺失的 lot 保持原始退出，不用缺失数据制造收益。",
        "",
        "## 外部调研判断",
        "",
        "- 公开 ORB/日内策略资料普遍强调固定开盘区间、固定止损止盈、收盘或失败退出；本阶段只借用这些通用执行纪律。",
        "- 本阶段没有引入 AI，也没有新增小数参数搜索；C1/C2 是 Stage001 预声明信号的冻结版本。",
        "",
        "## Baseline Validation",
        "",
        _md_table(validation, max_rows=10),
        "",
        "## A/C Result",
        "",
        _md_table(display_summary, max_rows=10),
        "",
        "## Action Stats",
        "",
        _md_table(action_stats, max_rows=30),
        "",
        "## Yearly Delta",
        "",
        _md_table(yearly[yearly["rule_id"].ne("A_original_lot_mark")], max_rows=80),
        "",
        "## Changed-Lot Atlas",
        "",
        *[f"- `{path}`" for path in chart_paths],
        "",
        "## Judgment",
        "",
        "- 本阶段是更接近可执行语义的 A/C，但仍不是完整组合引擎重放；它不重算后续信号、保证金占用和资金联动。",
        "- 过拟合判断：当前不属于新增扫参，但 C1/C2 如果失败后继续改 `30`、`0.5R`、`1R`、`2次` 等数值就会过拟合。",
        "- 继续价值判断：只有当 C1 或 C2 在同口径下改善净值且没有明显恶化回撤/交易成本，才值得进入完整组合引擎验证。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    closed, official_summary, official_curve = _load_stage825_closed()
    metadata = s513._metadata()
    minute_bars = _load_minute_bars(closed)
    minute_by_symbol = _minute_groups(minute_bars)

    rule_ids = [
        "A_original_lot_mark",
        "C1_failfast30_05r_retry2",
        "C2_first1r_stop_if_before_target",
    ]
    lot_frames: list[pd.DataFrame] = []
    event_frames: list[pd.DataFrame] = []
    for rule_id in rule_ids:
        lot_frame, event_frame = _simulate_rule(rule_id, closed, minute_by_symbol, metadata)
        lot_frames.append(lot_frame)
        event_frames.append(event_frame)
    lots = pd.concat(lot_frames, ignore_index=True, sort=False)
    events = pd.concat(event_frames, ignore_index=True, sort=False)
    summary, curves = _build_curves(events, official_curve["date"])
    yearly = _yearly_delta(lots)
    actions = _action_stats(lots)
    chart_paths, atlas_records = _plot_changed_atlas(lots, events, minute_bars)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVE_PATH, index=False, encoding="utf-8-sig")
    lots.to_csv(LOT_OUTCOMES_PATH, index=False, encoding="utf-8-sig")
    events.to_csv(EVENTS_PATH, index=False, encoding="utf-8-sig")
    yearly.to_csv(YEARLY_DELTA_PATH, index=False, encoding="utf-8-sig")
    atlas_records.to_csv(ATLAS_MANIFEST_PATH, index=False, encoding="utf-8-sig")
    _write_report(official_summary, summary, lots, yearly, actions, chart_paths)

    base = summary[summary["rule_id"].eq("A_original_lot_mark")].iloc[0].to_dict()
    candidates = summary[summary["rule_id"].ne("A_original_lot_mark")].copy()
    candidates["end_equity_delta_vs_A"] = candidates["end_equity"] - float(base["end_equity"])
    candidates["max_dd_delta_vs_A"] = candidates["max_dd_pct"] - float(base["max_dd_pct"])
    candidates["sharpe_delta_vs_A"] = candidates["sharpe"] - float(base["sharpe"])
    candidates["slippage_delta_vs_A"] = candidates["total_slippage"] - float(base["total_slippage"])
    best = candidates.sort_values(["end_equity_delta_vs_A", "sharpe_delta_vs_A"], ascending=[False, False])
    best_row = best.iloc[0].to_dict() if not best.empty else {}
    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "source_candidate": stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION,
        "strategy_changed": False,
        "ctp_connected": False,
        "order_api_called": False,
        "formal_ab_triggered": False,
        "ab_gate_judgment": "candidate_internal_overlay_only_not_formal_stage372_ab",
        "rules": {
            "C1_failfast30_05r_retry2": {
                "window_bars": FAILFAST_WINDOW_BARS,
                "stop_r": FAILFAST_STOP_R,
                "confirm_r": FAILFAST_CONFIRM_R,
                "max_retries": FAILFAST_MAX_RETRIES,
            },
            "C2_first1r_stop_if_before_target": {
                "stop_r": QUALITY_STOP_R,
                "confirm_r": QUALITY_CONFIRM_R,
            },
        },
        "summary": summary.to_dict("records"),
        "action_stats": actions.to_dict("records"),
        "best_candidate": best_row,
        "decision": "overlay_diagnostic_only_not_promoted",
        "overfit_reflection": (
            "Stage826 freezes Stage001 rule shapes. It is not a parameter sweep; changing the window/R/retry values "
            "after seeing this result would be overfitting."
        ),
        "continue_value": (
            "Continue only if a frozen rule improves the lot-level overlay without materially worsening drawdown, "
            "trade count, or slippage; otherwise stop this rule shape."
        ),
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "curves": str(CURVE_PATH),
            "lot_outcomes": str(LOT_OUTCOMES_PATH),
            "events": str(EVENTS_PATH),
            "yearly_delta": str(YEARLY_DELTA_PATH),
            "report": str(REPORT_PATH),
            "atlas_manifest": str(ATLAS_MANIFEST_PATH),
            "atlas_pages": [str(path) for path in chart_paths],
        },
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print("summary")
    print(summary.to_string(index=False))
    print("action_stats")
    print(actions.to_string(index=False))


if __name__ == "__main__":
    main()
