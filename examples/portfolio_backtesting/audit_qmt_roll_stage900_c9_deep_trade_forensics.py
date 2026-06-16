from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import analyze_qmt_roll_stage501_asymmetric_entry_exit_execution as s501


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage900"
MODEL_TAG = "stage900_c9_deep_trade_forensics_v1"
OUTPUT_PREFIX = "qmt_roll_stage900_c9_deep_trade_forensics"

STAGE861_TAG = "stage861_stage860_full_visual_atlas_v1"
STAGE863_TAG = "stage863_stage847_c10_budget_lock_engine_v1"
STAGE898_TAG = "stage898_c9_backtest_integrity_audit_v1"

STAGE861_PREFIX = "qmt_roll_stage861_stage860_full_visual_atlas"
STAGE863_PREFIX = "qmt_roll_stage863_stage847_c10_budget_lock_engine"
STAGE898_PREFIX = "qmt_roll_stage898_c9_backtest_integrity_audit"

C4_ARM = "stage830_stage819_c2_broker10_100_cap"
C9_ARM = "stage847_stage819_c4_05r_stop_retry_once"
C10_ARM = "stage863_stage819_c4_c9_budget_lock"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
FINDINGS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_findings_{MODEL_TAG}.csv"
PER_LOT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_per_lot_audit_{MODEL_TAG}.csv"
TOP_LOTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_top_lots_{MODEL_TAG}.csv"
PNL_CONCENTRATION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_pnl_concentration_{MODEL_TAG}.csv"
YEAR_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_summary_{MODEL_TAG}.csv"
PRODUCT_DIRECTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_direction_summary_{MODEL_TAG}.csv"
EXIT_REASON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_exit_reason_summary_{MODEL_TAG}.csv"
C9_VS_C4_GROUP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_c9_vs_c4_group_delta_{MODEL_TAG}.csv"
ENTRY_EXECUTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_execution_audit_{MODEL_TAG}.csv"
EVENT_PRICE_AUDIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_price_audit_{MODEL_TAG}.csv"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"


def _csv(prefix: str, suffix: str, tag: str) -> Path:
    return OUTPUT_DIR / f"{prefix}_{suffix}_{tag}.csv"


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    try:
        return pd.read_csv(path, encoding="utf-8-sig", **kwargs)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if np.isfinite(result) else default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if pd.isna(value):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        result = float(value)
        return None if np.isnan(result) or np.isinf(result) else result
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "无数据。"
    view = frame.copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda item: f"{item:.4f}" if pd.notna(item) else "")
    return view.to_markdown(index=False)


def _normalize_date(value: Any) -> pd.Timestamp:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return pd.NaT
    if getattr(ts, "tzinfo", None) is not None:
        ts = ts.tz_convert("Asia/Shanghai").tz_localize(None) if hasattr(ts, "tz_convert") else ts.tz_localize(None)
    return pd.Timestamp(ts).normalize()


def _load_stage861_minute_subset(vt_symbols: set[str]) -> pd.DataFrame:
    path = _csv(STAGE861_PREFIX, "full_minute_bars", STAGE861_TAG)
    usecols = ["vt_symbol", "bar_datetime", "bar_date", "open", "high", "low", "close", "volume", "minute_source"]
    minute = pd.read_csv(path, usecols=lambda col: col in usecols, encoding="utf-8-sig")
    minute = minute[minute["vt_symbol"].astype(str).isin(vt_symbols)].copy()
    minute["bar_datetime"] = pd.to_datetime(minute["bar_datetime"], errors="coerce")
    if "bar_date" in minute.columns:
        minute["bar_date"] = pd.to_datetime(minute["bar_date"], errors="coerce").dt.normalize()
    else:
        minute["bar_date"] = minute["bar_datetime"].dt.normalize()
    for column in ["open", "high", "low", "close", "volume"]:
        if column in minute.columns:
            minute[column] = pd.to_numeric(minute[column], errors="coerce")
    return minute.dropna(subset=["vt_symbol", "bar_datetime", "bar_date", "open", "high", "low", "close"]).copy()


def _proxy_window(signal_date: Any, fill_date: Any, proxy_source: Any) -> tuple[pd.Timestamp, pd.Timestamp] | tuple[pd.NaT, pd.NaT]:
    source = str(proxy_source)
    signal = pd.Timestamp(signal_date).normalize() if pd.notna(signal_date) else pd.NaT
    fill = pd.Timestamp(fill_date).normalize() if pd.notna(fill_date) else pd.NaT
    if "night" in source and "2100_2105" in source and pd.notna(signal):
        start = signal + pd.Timedelta(hours=21)
        return start, start + pd.Timedelta(minutes=5)
    if "day" in source and "0900_0905" in source and pd.notna(fill):
        start = fill + pd.Timedelta(hours=9)
        return start, start + pd.Timedelta(minutes=5)
    return pd.NaT, pd.NaT


def _minute_window_range(minute: pd.DataFrame, vt_symbol: str, start: Any, end: Any) -> dict[str, Any]:
    if pd.isna(start) or pd.isna(end):
        return {
            "proxy_window_low": np.nan,
            "proxy_window_high": np.nan,
            "proxy_window_rows": 0,
            "proxy_window_degenerate_rows": 0,
            "proxy_window_sources": "",
        }
    window = minute[
        minute["vt_symbol"].astype(str).eq(str(vt_symbol))
        & minute["bar_datetime"].ge(pd.Timestamp(start))
        & minute["bar_datetime"].lt(pd.Timestamp(end))
    ].copy()
    if window.empty:
        return {
            "proxy_window_low": np.nan,
            "proxy_window_high": np.nan,
            "proxy_window_rows": 0,
            "proxy_window_degenerate_rows": 0,
            "proxy_window_sources": "",
        }
    degenerate = (
        window["open"].eq(window["high"])
        & window["high"].eq(window["low"])
        & window["low"].eq(window["close"])
    )
    return {
        "proxy_window_low": float(window["low"].min()),
        "proxy_window_high": float(window["high"].max()),
        "proxy_window_rows": int(len(window)),
        "proxy_window_degenerate_rows": int(degenerate.sum()),
        "proxy_window_sources": ";".join(sorted(window.get("minute_source", pd.Series(dtype=str)).astype(str).dropna().unique())),
    }


def _prepare_inputs() -> dict[str, pd.DataFrame]:
    return {
        "summary": _read_csv(_csv(STAGE863_PREFIX, "summary", STAGE863_TAG)),
        "comparison": _read_csv(_csv(STAGE863_PREFIX, "comparison", STAGE863_TAG)),
        "curve": _read_csv(_csv(STAGE863_PREFIX, "curve", STAGE863_TAG)),
        "trades": _read_csv(_csv(STAGE863_PREFIX, "trades", STAGE863_TAG)),
        "closed_lots": _read_csv(_csv(STAGE863_PREFIX, "closed_lots", STAGE863_TAG)),
        "entry_risk": _read_csv(_csv(STAGE863_PREFIX, "entry_risk", STAGE863_TAG)),
        "entry_candidates": _read_csv(_csv(STAGE863_PREFIX, "entry_candidates", STAGE863_TAG)),
        "intraday_events": _read_csv(_csv(STAGE863_PREFIX, "intraday_events", STAGE863_TAG)),
        "stop_retry_events": _read_csv(_csv(STAGE863_PREFIX, "stop_retry_events", STAGE863_TAG)),
        "stage898_gaps": _read_csv(_csv(STAGE898_PREFIX, "coverage_gaps", STAGE898_TAG)),
        "stage898_findings": _read_csv(_csv(STAGE898_PREFIX, "findings", STAGE898_TAG)),
    }


def _match_entry_signal_rows(trades: pd.DataFrame, entry_risk: pd.DataFrame) -> pd.DataFrame:
    original_opens = trades[
        trades["profile"].astype(str).eq(C9_ARM)
        & trades["offset"].astype(str).eq("Open")
        & ~trades["order_id"].astype(str).str.contains("stage847_c9", na=False)
    ].copy()
    risk = entry_risk[entry_risk["profile"].astype(str).eq(C9_ARM)].copy()
    original_opens["fill_date"] = pd.to_datetime(original_opens["datetime"], errors="coerce", utc=True).dt.tz_convert(
        "Asia/Shanghai"
    ).dt.tz_localize(None).dt.normalize()
    risk["signal_date"] = pd.to_datetime(risk["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    for frame in [original_opens, risk]:
        frame["direction_key"] = frame["direction"].astype(str).str.lower()
    risk["selected_volume_num"] = pd.to_numeric(risk.get("selected_volume", np.nan), errors="coerce")
    original_opens["volume_num"] = pd.to_numeric(original_opens["volume"], errors="coerce")
    original_opens = original_opens.sort_values(["fill_date", "vt_symbol", "trade_id"]).reset_index(drop=True)
    risk = risk.sort_values(["signal_date", "contract_vt_symbol", "entry_index"]).reset_index(drop=True)

    used: set[int] = set()
    rows: list[dict[str, Any]] = []
    for open_row in original_opens.itertuples(index=False):
        candidates = risk[
            risk["contract_vt_symbol"].astype(str).eq(str(open_row.vt_symbol))
            & risk["direction_key"].eq(str(open_row.direction_key))
            & risk["signal_date"].le(open_row.fill_date)
            & pd.to_numeric(risk["selected_volume_num"], errors="coerce").eq(float(open_row.volume_num))
        ].copy()
        candidates = candidates[[idx not in used for idx in candidates.index]]
        match_idx = None
        if not candidates.empty:
            candidates["_lag_days"] = (open_row.fill_date - candidates["signal_date"]).dt.days
            candidates = candidates.sort_values(["_lag_days", "entry_index"])
            match_idx = int(candidates.index[0])
            used.add(match_idx)
            matched = risk.loc[match_idx]
            signal_date = matched["signal_date"]
            planned_price = _safe_float(matched.get("planned_entry_price"))
            entry_index = _safe_int(matched.get("entry_index"), -1)
            signal = str(matched.get("signal", ""))
            ai_signal_date = str(matched.get("ai_product_pool_signal_date", ""))
            ai_effective = str(matched.get("ai_product_pool_entry_effective_date", ""))
            ai_use_next = _safe_int(matched.get("ai_product_pool_use_next_trade_date_for_entry"), 0)
        else:
            signal_date = pd.NaT
            planned_price = np.nan
            entry_index = -1
            signal = ""
            ai_signal_date = ""
            ai_effective = ""
            ai_use_next = 0
        rows.append(
            {
                "trade_id": str(open_row.trade_id),
                "order_id": str(open_row.order_id),
                "vt_symbol": str(open_row.vt_symbol),
                "direction": str(open_row.direction_key),
                "fill_date": open_row.fill_date,
                "trade_price": _safe_float(open_row.price),
                "volume": _safe_float(open_row.volume),
                "matched_entry_index": entry_index,
                "signal_date": signal_date,
                "signal_to_fill_days": (open_row.fill_date - signal_date).days if pd.notna(signal_date) else np.nan,
                "planned_entry_price": planned_price,
                "signal": signal,
                "ai_product_pool_signal_date": ai_signal_date,
                "ai_product_pool_entry_effective_date": ai_effective,
                "ai_product_pool_use_next_trade_date_for_entry": ai_use_next,
                "entry_match_found": int(match_idx is not None),
            }
        )
    return pd.DataFrame(rows)


def _entry_execution_audit(trades: pd.DataFrame, entry_risk: pd.DataFrame, minute: pd.DataFrame) -> pd.DataFrame:
    matched = _match_entry_signal_rows(trades, entry_risk)
    if matched.empty:
        return matched

    _, open_map = s501._seed_proxy_maps()
    day_range = (
        minute.groupby(["vt_symbol", "bar_date"], as_index=False)
        .agg(day_low=("low", "min"), day_high=("high", "max"), minute_rows=("close", "size"))
    )
    matched = matched.merge(
        day_range,
        left_on=["vt_symbol", "fill_date"],
        right_on=["vt_symbol", "bar_date"],
        how="left",
    )

    proxy_rows: list[dict[str, Any]] = []
    for row in matched.itertuples(index=False):
        signal_date = pd.Timestamp(row.signal_date).normalize() if pd.notna(row.signal_date) else pd.NaT
        fill_date = pd.Timestamp(row.fill_date).normalize() if pd.notna(row.fill_date) else pd.NaT
        proxy_source = "missing_signal_match"
        proxy_price = np.nan
        proxy_available = 0
        if pd.notna(signal_date) and pd.notna(fill_date):
            proxy = open_map.get((signal_date, fill_date, str(row.vt_symbol)))
            if proxy is None:
                proxy = s501._next_real_open_proxy_from_raw(str(row.vt_symbol), signal_date, fill_date)
            if proxy is not None and _safe_float(proxy.get("proxy_price")) > 0:
                proxy_source = str(proxy.get("price_source", "raw_proxy"))
                proxy_price = _safe_float(proxy.get("proxy_price"))
                proxy_available = 1
            else:
                proxy_source = "fallback_daily_next_open"
        window_start, window_end = _proxy_window(signal_date, fill_date, proxy_source)
        window_range = _minute_window_range(minute, str(row.vt_symbol), window_start, window_end)
        trade_price = _safe_float(row.trade_price)
        in_proxy_window = int(
            np.isfinite(trade_price)
            and window_range["proxy_window_rows"] > 0
            and window_range["proxy_window_low"] <= trade_price <= window_range["proxy_window_high"]
        )
        proxy_rows.append(
            {
                "trade_id": row.trade_id,
                "proxy_source": proxy_source,
                "proxy_price": proxy_price,
                "proxy_available": proxy_available,
                "trade_minus_proxy": _safe_float(row.trade_price) - proxy_price if np.isfinite(proxy_price) else np.nan,
                "proxy_window_start": "" if pd.isna(window_start) else pd.Timestamp(window_start).isoformat(),
                "proxy_window_end": "" if pd.isna(window_end) else pd.Timestamp(window_end).isoformat(),
                "proxy_window_low": window_range["proxy_window_low"],
                "proxy_window_high": window_range["proxy_window_high"],
                "proxy_window_rows": window_range["proxy_window_rows"],
                "proxy_window_degenerate_rows": window_range["proxy_window_degenerate_rows"],
                "proxy_window_sources": window_range["proxy_window_sources"],
                "trade_price_in_proxy_window_range": in_proxy_window,
            }
        )
    proxy_df = pd.DataFrame(proxy_rows)
    matched = matched.merge(proxy_df, on="trade_id", how="left")
    matched["trade_price_in_fill_day_minute_range"] = (
        pd.to_numeric(matched["trade_price"], errors="coerce").ge(pd.to_numeric(matched["day_low"], errors="coerce"))
        & pd.to_numeric(matched["trade_price"], errors="coerce").le(pd.to_numeric(matched["day_high"], errors="coerce"))
    ).astype(int)
    matched.loc[matched["minute_rows"].isna(), "trade_price_in_fill_day_minute_range"] = 0
    matched["signal_after_fill_bug"] = (
        pd.to_datetime(matched["signal_date"], errors="coerce") > pd.to_datetime(matched["fill_date"], errors="coerce")
    ).astype(int)
    matched["fallback_execution"] = matched["proxy_source"].astype(str).eq("fallback_daily_next_open").astype(int)
    return matched.sort_values(["fill_date", "vt_symbol", "trade_id"]).reset_index(drop=True)


def _event_price_audit(intraday_events: pd.DataFrame, stop_retry: pd.DataFrame, minute: pd.DataFrame) -> pd.DataFrame:
    minute_key = minute.copy()
    minute_key["bar_datetime_key"] = minute_key["bar_datetime"].dt.floor("min")
    bar_map = {
        (str(row.vt_symbol), pd.Timestamp(row.bar_datetime_key)): (
            _safe_float(row.open),
            _safe_float(row.low),
            _safe_float(row.high),
            _safe_float(row.close),
            str(getattr(row, "minute_source", "")),
        )
        for row in minute_key.itertuples(index=False)
    }
    rows: list[dict[str, Any]] = []

    def add_check(
        *,
        event_type: str,
        event_id: str,
        vt_symbol: str,
        event_time: Any,
        price: Any,
        direction: str,
        source_col: str,
        profile: str,
    ) -> None:
        ts = pd.to_datetime(event_time, errors="coerce")
        price_f = _safe_float(price)
        missing_time = int(pd.isna(ts))
        open_ = low = high = close = np.nan
        minute_source = ""
        found = 0
        in_range = 0
        trigger_met = 0
        degenerate = 0
        trigger_overshoot_points = np.nan
        if pd.notna(ts):
            ts = pd.Timestamp(ts).tz_localize(None).floor("min")
            key = (str(vt_symbol), ts)
            if key in bar_map:
                open_, low, high, close, minute_source = bar_map[key]
                found = 1
                in_range = int(np.isfinite(price_f) and low <= price_f <= high)
                degenerate = int(
                    np.isfinite(open_)
                    and np.isfinite(low)
                    and np.isfinite(high)
                    and np.isfinite(close)
                    and open_ == high == low == close
                )
                direction_key = str(direction).lower()
                event_key = str(event_type)
                if np.isfinite(price_f):
                    if "reentry" in event_key:
                        if direction_key == "long":
                            trigger_met = int(high >= price_f)
                            trigger_overshoot_points = high - price_f
                        else:
                            trigger_met = int(low <= price_f)
                            trigger_overshoot_points = price_f - low
                    else:
                        if direction_key == "long":
                            trigger_met = int(low <= price_f)
                            trigger_overshoot_points = price_f - low
                        else:
                            trigger_met = int(high >= price_f)
                            trigger_overshoot_points = high - price_f
        rows.append(
            {
                "event_type": event_type,
                "event_id": event_id,
                "profile": profile,
                "vt_symbol": vt_symbol,
                "direction": direction,
                "source_col": source_col,
                "event_time": "" if pd.isna(ts) else pd.Timestamp(ts).isoformat(),
                "price": price_f,
                "minute_bar_found": found,
                "price_in_minute_bar_range": in_range,
                "event_trigger_condition_met": trigger_met,
                "threshold_not_observed_inside_bar": int(found == 1 and trigger_met == 1 and in_range == 0),
                "trigger_overshoot_points": trigger_overshoot_points,
                "degenerate_minute_bar": degenerate,
                "minute_open": open_,
                "minute_low": low,
                "minute_high": high,
                "minute_close": close,
                "minute_source": minute_source,
                "missing_event_time": missing_time,
            }
        )

    c9_events = stop_retry[stop_retry["profile"].astype(str).eq(C9_ARM)].copy()
    for event in c9_events.itertuples(index=False):
        event_id = str(event.trade_id)
        add_check(
            event_type="c9_first_05r_stop",
            event_id=event_id,
            vt_symbol=str(event.vt_symbol),
            event_time=getattr(event, "first_stop_time", ""),
            price=getattr(event, "stop_price", np.nan),
            direction=str(event.direction),
            source_col="first_stop_time/stop_price",
            profile=str(event.profile),
        )
        if _safe_int(getattr(event, "retry_reentered", 0), 0) == 1:
            add_check(
                event_type="c9_reentry",
                event_id=event_id,
                vt_symbol=str(event.vt_symbol),
                event_time=getattr(event, "reentry_time", ""),
                price=getattr(event, "entry_price", np.nan),
                direction=str(event.direction),
                source_col="reentry_time/entry_price",
                profile=str(event.profile),
            )
        if _safe_int(getattr(event, "retry_failed", 0), 0) == 1:
            add_check(
                event_type="c9_retry_failed_stop",
                event_id=event_id,
                vt_symbol=str(event.vt_symbol),
                event_time=getattr(event, "retry_failed_time", ""),
                price=getattr(event, "stop_price", np.nan),
                direction=str(event.direction),
                source_col="retry_failed_time/stop_price",
                profile=str(event.profile),
            )

    c2_events = intraday_events[
        intraday_events["profile"].astype(str).eq(C9_ARM)
        & intraday_events["exit_reason"].astype(str).eq("stage827_intraday_c2_1r_stop")
    ].copy()
    for event in c2_events.itertuples(index=False):
        add_check(
            event_type="c9_inherited_c2_1r_stop",
            event_id=str(event.trade_id),
            vt_symbol=str(event.vt_symbol),
            event_time=getattr(event, "hit_time", ""),
            price=getattr(event, "stop_price", np.nan),
            direction=str(event.direction),
            source_col="hit_time/stop_price",
            profile=str(event.profile),
        )

    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values(["event_type", "event_time", "vt_symbol"]).reset_index(drop=True)
    return out


def _per_lot_audit(
    closed_lots: pd.DataFrame,
    trades: pd.DataFrame,
    entry_execution: pd.DataFrame,
    stage898_gaps: pd.DataFrame,
) -> pd.DataFrame:
    c9 = closed_lots[closed_lots["arm"].astype(str).eq(C9_ARM)].copy()
    numeric_cols = [
        "realized_pnl",
        "r_multiple",
        "volume",
        "risk_amount",
        "mfe_cash",
        "mae_cash",
        "selected_volume",
        "entry_price",
        "exit_price",
    ]
    for column in numeric_cols:
        if column in c9.columns:
            c9[column] = pd.to_numeric(c9[column], errors="coerce")
    c9["entry_date"] = pd.to_datetime(c9["entry_date"], errors="coerce").dt.normalize()
    c9["exit_date"] = pd.to_datetime(c9["exit_date"], errors="coerce").dt.normalize()
    c9["entry_year"] = c9["entry_date"].dt.year
    c9["product_direction"] = c9["product"].astype(str) + " " + c9["direction"].astype(str)

    open_trades = trades[trades["profile"].astype(str).eq(C9_ARM) & trades["offset"].astype(str).eq("Open")].copy()
    open_trades = open_trades[["trade_id", "order_id", "datetime", "price", "volume"]].rename(
        columns={
            "trade_id": "open_trade_id",
            "order_id": "open_order_id",
            "datetime": "open_trade_datetime",
            "price": "open_trade_price",
            "volume": "open_trade_volume",
        }
    )
    open_trades["synthetic_reentry_open"] = open_trades["open_order_id"].astype(str).str.contains("stage847_c9", na=False).astype(int)

    exec_map = entry_execution[
        [
            "trade_id",
            "signal_date",
            "fill_date",
            "proxy_source",
            "proxy_available",
            "fallback_execution",
            "signal_to_fill_days",
            "signal_after_fill_bug",
            "trade_price_in_fill_day_minute_range",
            "trade_minus_proxy",
        ]
    ].rename(columns={"trade_id": "open_trade_id"})

    out = c9.merge(open_trades, on="open_trade_id", how="left").merge(exec_map, on="open_trade_id", how="left")
    out["synthetic_reentry_open"] = out["synthetic_reentry_open"].fillna(0).astype(int)
    out.loc[out["synthetic_reentry_open"].eq(1), "proxy_source"] = "stage847_reentry_at_original_entry"
    out["fallback_execution"] = out["fallback_execution"].fillna(0).astype(int)
    out["proxy_available"] = out["proxy_available"].fillna(0).astype(int)

    if {"profile", "trade_id"}.issubset(stage898_gaps.columns):
        missing_ids = set(stage898_gaps[stage898_gaps["profile"].astype(str).eq(C9_ARM)]["trade_id"].astype(str))
    else:
        missing_ids = set()
    out["stage898_missing_full_minute_entry_day"] = out["open_trade_id"].astype(str).isin(missing_ids).astype(int)

    total_pnl = float(out["realized_pnl"].sum())
    gross_profit = float(out.loc[out["realized_pnl"].gt(0), "realized_pnl"].sum())
    out["net_pnl_contribution_pct"] = np.where(total_pnl != 0, out["realized_pnl"] / total_pnl * 100.0, np.nan)
    out["gross_profit_contribution_pct"] = np.where(
        (gross_profit != 0) & out["realized_pnl"].gt(0),
        out["realized_pnl"] / gross_profit * 100.0,
        0.0,
    )
    return out.sort_values("realized_pnl", ascending=False).reset_index(drop=True)


def _summary_rows(
    summary: pd.DataFrame,
    curve: pd.DataFrame,
    trades: pd.DataFrame,
    per_lot: pd.DataFrame,
    entry_execution: pd.DataFrame,
    event_price: pd.DataFrame,
    stop_retry: pd.DataFrame,
    entry_candidates: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    def add(metric: str, value: Any, note: str = "") -> None:
        rows.append({"metric": metric, "value": value, "note": note})

    c9_summary = summary[summary["arm"].astype(str).eq(C9_ARM)].iloc[0]
    c9_curve = curve[curve["arm"].astype(str).eq(C9_ARM)].copy()
    c9_trades = trades[trades["profile"].astype(str).eq(C9_ARM)].copy()
    net_pnl_curve = pd.to_numeric(c9_curve["net_pnl"], errors="coerce").fillna(0).sum()
    closed_pnl = pd.to_numeric(per_lot["realized_pnl"], errors="coerce").fillna(0).sum()
    total_slippage = _safe_float(c9_summary.get("total_slippage"), 0.0)
    trade_count_summary = _safe_float(c9_summary.get("total_trade_count"), 0.0)
    trade_count_actual = int(len(c9_trades))
    add("c9_end_equity", _safe_float(c9_summary.get("end_equity")), "Stage863 current local output")
    add("c9_total_return_pct", _safe_float(c9_summary.get("total_return_pct")), "")
    add("c9_max_dd_pct", _safe_float(c9_summary.get("max_dd_pct")), "")
    add("c9_sharpe", _safe_float(c9_summary.get("sharpe")), "")
    add("c9_total_trade_count_summary", trade_count_summary, "")
    add("c9_trade_rows_actual", trade_count_actual, "")
    add("c9_trade_count_diff_actual_minus_summary", trade_count_actual - trade_count_summary, "")
    add("c9_closed_lot_count", int(len(per_lot)), "")
    add("c9_closed_lot_realized_pnl_sum", float(closed_pnl), "gross realized lot PnL before daily cost reconciliation")
    add("c9_curve_net_pnl_sum", float(net_pnl_curve), "daily net PnL from backtest engine")
    add("c9_summary_total_slippage", total_slippage, "")
    add("c9_lot_minus_curve_net_pnl", float(closed_pnl - net_pnl_curve), "should mainly reflect costs/open-path accounting differences")

    winners = per_lot[per_lot["realized_pnl"].gt(0)]
    losers = per_lot[per_lot["realized_pnl"].lt(0)]
    gross_profit = float(winners["realized_pnl"].sum())
    gross_loss = float(losers["realized_pnl"].sum())
    net = float(per_lot["realized_pnl"].sum())
    add("winner_lot_count", int(len(winners)), "")
    add("loser_lot_count", int(len(losers)), "")
    add("gross_profit", gross_profit, "")
    add("gross_loss", gross_loss, "")
    add("profit_factor_gross", gross_profit / abs(gross_loss) if gross_loss else np.nan, "")
    for n in [1, 3, 5, 10, 20, 50]:
        top = winners.sort_values("realized_pnl", ascending=False).head(n)
        add(f"top_{n}_winner_pnl", float(top["realized_pnl"].sum()), "")
        add(f"top_{n}_winner_share_of_net_pct", float(top["realized_pnl"].sum() / net * 100.0) if net else np.nan, "")
        add(
            f"top_{n}_winner_share_of_gross_profit_pct",
            float(top["realized_pnl"].sum() / gross_profit * 100.0) if gross_profit else np.nan,
            "",
        )
    big = per_lot[pd.to_numeric(per_lot.get("big_winner", 0), errors="coerce").fillna(0).eq(1)]
    add("big_winner_lot_count", int(len(big)), "")
    add("big_winner_pnl", float(big["realized_pnl"].sum()), "")
    add("big_winner_share_of_net_pct", float(big["realized_pnl"].sum() / net * 100.0) if net else np.nan, "")

    add("entry_execution_rows", int(len(entry_execution)), "")
    add("entry_match_missing_count", int((entry_execution["entry_match_found"] == 0).sum()) if not entry_execution.empty else 0, "")
    add("signal_after_fill_bug_count", int(entry_execution["signal_after_fill_bug"].sum()) if not entry_execution.empty else 0, "")
    add("fallback_original_open_count", int(entry_execution["fallback_execution"].sum()) if not entry_execution.empty else 0, "")
    add("proxy_available_original_open_count", int(entry_execution["proxy_available"].sum()) if not entry_execution.empty else 0, "")
    proxy_check = entry_execution[
        entry_execution["proxy_source"].astype(str).str.contains("2100_2105|0900_0905", na=False)
        & pd.to_numeric(entry_execution["proxy_window_rows"], errors="coerce").gt(0)
    ] if not entry_execution.empty else pd.DataFrame()
    proxy_expected = entry_execution[
        entry_execution["proxy_source"].astype(str).str.contains("2100_2105|0900_0905", na=False)
    ] if not entry_execution.empty else pd.DataFrame()
    add("open_proxy_window_check_rows", int(len(proxy_check)), "excludes fallback rows without minute proxy window")
    add(
        "open_proxy_window_missing_count",
        int((pd.to_numeric(proxy_expected["proxy_window_rows"], errors="coerce").fillna(0) == 0).sum()) if not proxy_expected.empty else 0,
        "stage149/raw proxy rows whose matching Stage861 minute window is unavailable",
    )
    add(
        "open_trade_price_outside_proxy_window_count",
        int((pd.to_numeric(proxy_check["trade_price_in_proxy_window_range"], errors="coerce").fillna(0) == 0).sum()) if not proxy_check.empty else 0,
        "checked against signal-date night window or fill-date day window",
    )
    add(
        "open_proxy_window_degenerate_row_count",
        int(pd.to_numeric(proxy_check["proxy_window_degenerate_rows"], errors="coerce").fillna(0).sum()) if not proxy_check.empty else 0,
        "open=high=low=close rows in proxy windows",
    )
    add(
        "open_trade_price_outside_fill_day_minute_range_count",
        int((entry_execution["trade_price_in_fill_day_minute_range"] == 0).sum()) if not entry_execution.empty else 0,
        "diagnostic only; night-session fills are expected to mismatch fill-date calendar range",
    )

    if not event_price.empty:
        add("event_price_check_rows", int(len(event_price)), "")
        add("event_minute_bar_missing_count", int((event_price["minute_bar_found"] == 0).sum()), "")
        add("event_trigger_condition_failed_count", int((event_price["event_trigger_condition_met"] == 0).sum()), "")
        add(
            "event_threshold_not_observed_inside_bar_count",
            int((event_price["threshold_not_observed_inside_bar"] == 1).sum()),
            "threshold can be crossed by degenerate sampled minute bars without being an observed traded OHLC price",
        )
        add("event_degenerate_minute_bar_count", int((event_price["degenerate_minute_bar"] == 1).sum()), "")
        add("event_price_outside_minute_bar_range_count", int((event_price["price_in_minute_bar_range"] == 0).sum()), "legacy strict range check")
        overshoot = pd.to_numeric(event_price["trigger_overshoot_points"], errors="coerce").dropna()
        add("event_trigger_overshoot_points_median", float(overshoot.median()) if not overshoot.empty else np.nan, "")
        add("event_trigger_overshoot_points_max", float(overshoot.max()) if not overshoot.empty else np.nan, "")
    else:
        add("event_price_check_rows", 0, "")

    c9_events = stop_retry[stop_retry["profile"].astype(str).eq(C9_ARM)].copy()
    if not c9_events.empty:
        first_stop = pd.to_numeric(c9_events["first_stop_bar_index"], errors="coerce")
        reentry = pd.to_numeric(c9_events["reentry_bar_index"], errors="coerce")
        retry_failed = pd.to_numeric(c9_events["retry_failed_bar_index"], errors="coerce")
        retry_reentered_flag = pd.to_numeric(c9_events["retry_reentered"], errors="coerce").fillna(0).astype(int)
        retry_failed_flag = pd.to_numeric(c9_events["retry_failed"], errors="coerce").fillna(0).astype(int)
        add("c9_stop_retry_event_count", int(len(c9_events)), "")
        add("c9_retry_reentered_count", int(retry_reentered_flag.sum()), "")
        add("c9_retry_failed_count", int(retry_failed_flag.sum()), "")
        add("bad_reentry_time_order_count", int(((retry_reentered_flag == 1) & (reentry <= first_stop)).sum()), "")
        add("bad_retry_failed_time_order_count", int(((retry_failed_flag == 1) & (retry_failed <= reentry)).sum()), "")
        add("same_bar_conservative_stop_first_count", int(c9_events["note"].astype(str).str.contains("same_bar", na=False).sum()), "")

    c9_candidates = entry_candidates[entry_candidates["profile"].astype(str).eq(C9_ARM)].copy()
    if not c9_candidates.empty:
        add(
            "ai_product_pool_use_next_trade_date_for_entry_count",
            int(pd.to_numeric(c9_candidates["ai_product_pool_use_next_trade_date_for_entry"], errors="coerce").fillna(0).sum()),
            "0 means no explicit next-trade-date AI lookup flag in candidate snapshots",
        )
        add("ai_product_pool_allowed_opened_count", int(pd.to_numeric(c9_candidates["ai_product_pool_allowed"], errors="coerce").fillna(0).sum()), "")

    return pd.DataFrame(rows)


def _pnl_concentration(per_lot: pd.DataFrame) -> pd.DataFrame:
    winners = per_lot[per_lot["realized_pnl"].gt(0)].sort_values("realized_pnl", ascending=False).copy()
    losers = per_lot[per_lot["realized_pnl"].lt(0)].sort_values("realized_pnl").copy()
    net = float(per_lot["realized_pnl"].sum())
    gross_profit = float(winners["realized_pnl"].sum())
    gross_loss = float(losers["realized_pnl"].sum())
    rows: list[dict[str, Any]] = []
    for n in [1, 3, 5, 10, 20, 50, 100]:
        top = winners.head(n)
        rows.append(
            {
                "bucket": f"top_{n}_winners",
                "lot_count": int(len(top)),
                "pnl": float(top["realized_pnl"].sum()),
                "share_of_net_pct": float(top["realized_pnl"].sum() / net * 100.0) if net else np.nan,
                "share_of_gross_profit_pct": float(top["realized_pnl"].sum() / gross_profit * 100.0) if gross_profit else np.nan,
            }
        )
    for n in [1, 3, 5, 10, 20, 50, 100]:
        bottom = losers.head(n)
        rows.append(
            {
                "bucket": f"bottom_{n}_losers",
                "lot_count": int(len(bottom)),
                "pnl": float(bottom["realized_pnl"].sum()),
                "share_of_net_pct": float(bottom["realized_pnl"].sum() / net * 100.0) if net else np.nan,
                "share_of_gross_loss_pct": float(bottom["realized_pnl"].sum() / gross_loss * 100.0) if gross_loss else np.nan,
            }
        )
    rows.append(
        {
            "bucket": "all_winners",
            "lot_count": int(len(winners)),
            "pnl": gross_profit,
            "share_of_net_pct": float(gross_profit / net * 100.0) if net else np.nan,
        }
    )
    rows.append(
        {
            "bucket": "all_losers",
            "lot_count": int(len(losers)),
            "pnl": gross_loss,
            "share_of_net_pct": float(gross_loss / net * 100.0) if net else np.nan,
        }
    )
    return pd.DataFrame(rows)


def _group_summaries(per_lot: pd.DataFrame, closed_lots: pd.DataFrame) -> dict[str, pd.DataFrame]:
    def summarize(frame: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
        out = (
            frame.groupby(keys, dropna=False)
            .agg(
                lots=("lot_id", "size"),
                pnl=("realized_pnl", "sum"),
                avg_pnl=("realized_pnl", "mean"),
                winners=("winner", "sum"),
                big_winners=("big_winner", "sum"),
                max_pnl=("realized_pnl", "max"),
                min_pnl=("realized_pnl", "min"),
            )
            .reset_index()
        )
        out["win_rate_pct"] = np.where(out["lots"].gt(0), out["winners"] / out["lots"] * 100.0, np.nan)
        return out.sort_values("pnl", ascending=False).reset_index(drop=True)

    year_summary = summarize(per_lot, ["entry_year"])
    product_direction = summarize(per_lot, ["product_direction"])
    exit_reason = summarize(per_lot, ["exit_reason"])

    both = closed_lots[closed_lots["arm"].astype(str).isin([C4_ARM, C9_ARM])].copy()
    both["entry_date"] = pd.to_datetime(both["entry_date"], errors="coerce").dt.normalize()
    both["entry_year"] = both["entry_date"].dt.year
    both["product_direction"] = both["product"].astype(str) + " " + both["direction"].astype(str)
    both["realized_pnl"] = pd.to_numeric(both["realized_pnl"], errors="coerce").fillna(0.0)
    pivot = (
        both.groupby(["entry_year", "product_direction", "arm"], dropna=False)
        .agg(lots=("lot_id", "size"), pnl=("realized_pnl", "sum"))
        .reset_index()
    )
    wide = pivot.pivot_table(
        index=["entry_year", "product_direction"],
        columns="arm",
        values=["lots", "pnl"],
        fill_value=0,
        aggfunc="sum",
    )
    wide.columns = [f"{metric}_{arm}" for metric, arm in wide.columns]
    wide = wide.reset_index()
    for col in [
        f"pnl_{C9_ARM}",
        f"pnl_{C4_ARM}",
        f"lots_{C9_ARM}",
        f"lots_{C4_ARM}",
    ]:
        if col not in wide.columns:
            wide[col] = 0.0
    wide["pnl_delta_c9_minus_c4"] = wide[f"pnl_{C9_ARM}"] - wide[f"pnl_{C4_ARM}"]
    wide["lots_delta_c9_minus_c4"] = wide[f"lots_{C9_ARM}"] - wide[f"lots_{C4_ARM}"]
    wide = wide.sort_values("pnl_delta_c9_minus_c4", ascending=False).reset_index(drop=True)
    return {
        "year_summary": year_summary,
        "product_direction": product_direction,
        "exit_reason": exit_reason,
        "c9_vs_c4_group": wide,
    }


def _findings(
    summary_rows: pd.DataFrame,
    per_lot: pd.DataFrame,
    entry_execution: pd.DataFrame,
    event_price: pd.DataFrame,
    stage898_findings: pd.DataFrame,
) -> pd.DataFrame:
    metrics = summary_rows.set_index("metric")["value"].to_dict()
    rows: list[dict[str, Any]] = []

    def add(severity: str, finding: str, evidence: str, judgment: str) -> None:
        rows.append({"severity": severity, "finding": finding, "evidence": evidence, "judgment": judgment})

    severity_col = stage898_findings.get("severity", pd.Series(dtype=str)).astype(str)
    status_col = stage898_findings.get("status", pd.Series(["unknown"] * len(stage898_findings))).astype(str)
    stage898_p0 = stage898_findings[severity_col.eq("P0")]
    missing_stage898 = stage898_findings[severity_col.eq("P0") & ~status_col.eq("pass")]
    if not missing_stage898.empty:
        add(
            "P0",
            "Stage898 仍有 P0 失败项",
            "; ".join(missing_stage898["finding"].astype(str).head(3).tolist()),
            "必须补齐 exact contract/date 分钟K并重跑 Stage863/896/897/898/899/900。",
        )
    elif not stage898_p0.empty:
        add(
            "PASS",
            "Stage898 P0 完整性检查均通过",
            f"stage898_p0_checks={len(stage898_p0)}, failed=0。",
            "当前本地输出没有再显示旧版 entry-day 缺口；仍需注意 Stage898 标注的 P1 watch 项。",
        )

    if _safe_float(metrics.get("signal_after_fill_bug_count"), 0) == 0:
        add(
            "PASS",
            "未发现信号日晚于成交日",
            f"原始开仓匹配 {int(_safe_float(metrics.get('entry_execution_rows'), 0))} 行，signal_after_fill=0。",
            "这项不支持未来函数假设。",
        )
    else:
        add(
            "P0",
            "发现信号日晚于成交日",
            f"signal_after_fill_bug_count={metrics.get('signal_after_fill_bug_count')}",
            "这是硬未来函数，需要停用结果。",
        )

    event_missing = _safe_float(metrics.get("event_minute_bar_missing_count"), 0)
    event_trigger_failed = _safe_float(metrics.get("event_trigger_condition_failed_count"), 0)
    event_not_observed = _safe_float(metrics.get("event_threshold_not_observed_inside_bar_count"), 0)
    event_degenerate = _safe_float(metrics.get("event_degenerate_minute_bar_count"), 0)
    if event_missing == 0 and event_trigger_failed == 0:
        add(
            "PASS",
            "C9 日内事件触发条件成立",
            f"event_price_check_rows={metrics.get('event_price_check_rows')}, missing=0, trigger_failed=0。",
            "这项不支持日内 stop/retry 触发使用未来价格的假设。",
        )
    else:
        add(
            "P1",
            "日内事件分钟K或触发条件存在异常",
            f"missing={event_missing}, trigger_failed={event_trigger_failed}",
            "需要逐条复核事件时间和分钟K源。",
        )
    if event_not_observed > 0:
        add(
            "P2",
            "C9 日内成交价精度依赖采样分钟K",
            (
                f"threshold_not_observed_inside_bar={int(event_not_observed)}, "
                f"degenerate_minute_bar={int(event_degenerate)}, "
                f"median_overshoot={_safe_float(metrics.get('event_trigger_overshoot_points_median'), 0):.4f}, "
                f"max_overshoot={_safe_float(metrics.get('event_trigger_overshoot_points_max'), 0):.4f}"
            ),
            "这不是硬未来函数，但 stop/reentry 按阈值成交可能与真实 tick/盘口成交有偏差。",
        )

    top10_share = _safe_float(metrics.get("top_10_winner_share_of_net_pct"), 0)
    if top10_share > 80:
        severity = "P1"
    elif top10_share > 50:
        severity = "P2"
    else:
        severity = "INFO"
    add(
        severity,
        "收益右尾集中度高",
        f"top10 winners share of net={top10_share:.2f}%。big_winner_share={_safe_float(metrics.get('big_winner_share_of_net_pct'), 0):.2f}%。",
        "高收益更像趋势右尾复利和仓位放大，不像均匀小胜率套利；需要接受尾部依赖和回撤。",
    )

    fallback_count = _safe_float(metrics.get("fallback_original_open_count"), 0)
    if fallback_count > 0:
        fallback_pnl = float(per_lot.loc[per_lot["fallback_execution"].eq(1), "realized_pnl"].sum())
        add(
            "P1",
            "存在 fallback next-open 执行代理",
            f"fallback original opens={int(fallback_count)}; fallback-linked closed lot pnl={fallback_pnl:.2f}",
            "这不是未来函数，但 2018/2019 或缺代理窗口的成交质量要单独复核。",
        )
    else:
        add("PASS", "未发现 fallback original open", "fallback_original_open_count=0", "执行价代理覆盖较好。")

    proxy_outside = _safe_float(metrics.get("open_trade_price_outside_proxy_window_count"), 0)
    proxy_missing = _safe_float(metrics.get("open_proxy_window_missing_count"), 0)
    if proxy_outside > 0:
        add(
            "P1",
            "非 fallback 开仓代理窗口价格仍有不匹配",
            f"proxy_window_check_rows={metrics.get('open_proxy_window_check_rows')}, outside={int(proxy_outside)}",
            "需要比对 Stage149 明细和 Stage861/原始分钟源是否同源。",
        )
    elif proxy_missing > 0:
        add(
            "P1",
            "部分非 fallback 开仓代理缺少可复核分钟窗口",
            (
                f"proxy_window_check_rows={metrics.get('open_proxy_window_check_rows')}, "
                f"missing={int(proxy_missing)}, outside=0"
            ),
            "已核验窗口价格一致，但 Stage149 代理来源缺少同源分钟窗口，不能等同于全部逐笔已复核。",
        )
    else:
        add(
            "PASS",
            "非 fallback 开仓价格与日/夜盘代理窗口一致",
            f"proxy_window_check_rows={metrics.get('open_proxy_window_check_rows')}, outside=0",
            "夜盘自然日错配误报已排除。",
        )

    missing_pnl = float(per_lot.loc[per_lot["stage898_missing_full_minute_entry_day"].eq(1), "realized_pnl"].sum())
    missing_count = int(per_lot["stage898_missing_full_minute_entry_day"].sum())
    if missing_count > 0:
        add(
            "P0",
            "缺分钟K开仓样本有实际 PnL 暴露",
            f"missing-linked lots={missing_count}, pnl={missing_pnl:.2f}",
            "即使金额不一定解释高收益，也违反“数据不能有任何偏差”的要求。",
        )

    trade_count_diff = _safe_float(metrics.get("c9_trade_count_diff_actual_minus_summary"), 0)
    if abs(trade_count_diff) <= 0:
        add(
            "PASS",
            "交易行数与 summary 交易数一致",
            f"actual-summary diff={trade_count_diff}",
            "汇总口径未发现交易数漏算。",
        )
    else:
        add(
            "P1",
            "交易行数与 summary 交易数不一致",
            f"actual-summary diff={trade_count_diff}",
            "需要确认 summary 和 trades 是否来自同一次输出。",
        )

    return pd.DataFrame(rows)


def _write_report(
    summary_rows: pd.DataFrame,
    findings: pd.DataFrame,
    pnl_concentration: pd.DataFrame,
    top_lots: pd.DataFrame,
    year_summary: pd.DataFrame,
    product_direction: pd.DataFrame,
    c9_vs_c4: pd.DataFrame,
    entry_execution: pd.DataFrame,
    event_price: pd.DataFrame,
) -> None:
    metrics = summary_rows.set_index("metric")["value"].to_dict()
    p0_findings = int(findings["severity"].astype(str).eq("P0").sum()) if not findings.empty else 0
    trigger_failed = _safe_int(metrics.get("event_trigger_condition_failed_count"), 0)
    signal_after_fill = _safe_int(metrics.get("signal_after_fill_bug_count"), 0)
    proxy_outside = _safe_int(metrics.get("open_trade_price_outside_proxy_window_count"), 0)
    proxy_missing = _safe_int(metrics.get("open_proxy_window_missing_count"), 0)
    event_not_observed = _safe_int(metrics.get("event_threshold_not_observed_inside_bar_count"), 0)
    lines = [
        "# Stage900 C9 深度逐笔可信度审计",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        "- 阶段性质：只读法证审计；不重跑 C9 回测、不改策略、不连接 CTP、不调用下单。",
        "- 审计问题：C9 收益是否高得不合理，是否存在 bug / 未来函数 / 执行价或分钟K偏差。",
        "",
        "## 结论先行",
        "",
        f"- 当前证据不支持“硬未来函数”作为高收益主因：signal_after_fill={signal_after_fill}，event_trigger_failed={trigger_failed}。",
        f"- 当前本地输出没有硬 P0 失败：P0 failed findings={p0_findings}；但 fallback 执行代理、代理窗口缺失、采样分钟K成交精度仍要复核。",
        f"- 非 fallback 开仓代理窗口 outside={proxy_outside}、missing={proxy_missing}；日内阈值价未被采样 OHLC 直接包含={event_not_observed}，这更像成交精度/数据粒度问题，不是时间穿越证据。",
        "- C9 高收益更合理的解释是：Stage819/813 基础趋势右尾已经强，C9 增加日内失败切断和一次 reclaim 重试后保留了右尾，同时 30 万整数手和复利放大收益；这不是均匀小胜率策略。",
        "",
        "## Findings",
        "",
        _md_table(findings, max_rows=20),
        "",
        "## Key Metrics",
        "",
        _md_table(summary_rows, max_rows=80),
        "",
        "## PnL Concentration",
        "",
        _md_table(pnl_concentration, max_rows=20),
        "",
        "## Top Lots",
        "",
        _md_table(
            top_lots[
                [
                    "lot_id",
                    "open_trade_id",
                    "vt_symbol",
                    "product_direction",
                    "entry_date",
                    "exit_date",
                    "realized_pnl",
                    "r_multiple",
                    "exit_reason",
                    "signal",
                    "proxy_source",
                    "stage898_missing_full_minute_entry_day",
                ]
            ],
            max_rows=20,
        ),
        "",
        "## Year Summary",
        "",
        _md_table(year_summary, max_rows=20),
        "",
        "## Product Direction Summary",
        "",
        _md_table(product_direction, max_rows=20),
        "",
        "## C9 vs C4 Group Delta",
        "",
        _md_table(c9_vs_c4, max_rows=20),
        "",
        "## Execution Audit Snapshot",
        "",
        _md_table(
            entry_execution[
                [
                    "trade_id",
                    "vt_symbol",
                    "direction",
                    "signal_date",
                    "fill_date",
                    "signal_to_fill_days",
                    "trade_price",
                    "proxy_source",
                    "proxy_price",
                    "proxy_window_start",
                    "proxy_window_end",
                    "trade_price_in_proxy_window_range",
                    "fallback_execution",
                    "signal_after_fill_bug",
                    "trade_price_in_fill_day_minute_range",
                ]
            ].head(30)
            if not entry_execution.empty
            else pd.DataFrame(),
            max_rows=30,
        ),
        "",
        "## Event Price Audit Snapshot",
        "",
        _md_table(event_price.head(30), max_rows=30),
        "",
        "## 输出文件",
        "",
        f"- summary：`{SUMMARY_PATH}`",
        f"- findings：`{FINDINGS_PATH}`",
        f"- per_lot_audit：`{PER_LOT_PATH}`",
        f"- top_lots：`{TOP_LOTS_PATH}`",
        f"- pnl_concentration：`{PNL_CONCENTRATION_PATH}`",
        f"- year_summary：`{YEAR_SUMMARY_PATH}`",
        f"- product_direction：`{PRODUCT_DIRECTION_PATH}`",
        f"- c9_vs_c4_group_delta：`{C9_VS_C4_GROUP_PATH}`",
        f"- entry_execution_audit：`{ENTRY_EXECUTION_PATH}`",
        f"- event_price_audit：`{EVENT_PRICE_AUDIT_PATH}`",
        "",
        "## 过拟合与继续价值",
        "",
        "- 过拟合反思：本阶段没有新增规则或参数，只读审计，不构成过拟合；但 C9 自身仍是历史研究版本，不能因为审计未发现硬未来函数就直接晋级。",
        "- 继续价值反思：有价值。下一步最有价值的是补齐 Stage898 的 8 笔 exact contract/date 分钟K，清零 fallback/缺口疑点后重跑，而不是继续调 C9 参数。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    data = _prepare_inputs()
    for key in ["trades", "closed_lots", "entry_risk", "entry_candidates", "intraday_events", "stop_retry_events"]:
        if "profile" in data[key].columns:
            data[key]["profile"] = data[key]["profile"].astype(str)
    vt_symbols = set(data["trades"]["vt_symbol"].dropna().astype(str))
    minute = _load_stage861_minute_subset(vt_symbols)
    entry_execution = _entry_execution_audit(data["trades"], data["entry_risk"], minute)
    event_price = _event_price_audit(data["intraday_events"], data["stop_retry_events"], minute)
    per_lot = _per_lot_audit(data["closed_lots"], data["trades"], entry_execution, data["stage898_gaps"])
    pnl_concentration = _pnl_concentration(per_lot)
    groups = _group_summaries(per_lot, data["closed_lots"])
    top_lots = per_lot.sort_values("realized_pnl", ascending=False).head(50).copy()
    summary_rows = _summary_rows(
        data["summary"],
        data["curve"],
        data["trades"],
        per_lot,
        entry_execution,
        event_price,
        data["stop_retry_events"],
        data["entry_candidates"],
    )
    findings = _findings(summary_rows, per_lot, entry_execution, event_price, data["stage898_findings"])

    summary_rows.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    findings.to_csv(FINDINGS_PATH, index=False, encoding="utf-8-sig")
    per_lot.to_csv(PER_LOT_PATH, index=False, encoding="utf-8-sig")
    top_lots.to_csv(TOP_LOTS_PATH, index=False, encoding="utf-8-sig")
    pnl_concentration.to_csv(PNL_CONCENTRATION_PATH, index=False, encoding="utf-8-sig")
    groups["year_summary"].to_csv(YEAR_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    groups["product_direction"].to_csv(PRODUCT_DIRECTION_PATH, index=False, encoding="utf-8-sig")
    groups["exit_reason"].to_csv(EXIT_REASON_PATH, index=False, encoding="utf-8-sig")
    groups["c9_vs_c4_group"].to_csv(C9_VS_C4_GROUP_PATH, index=False, encoding="utf-8-sig")
    entry_execution.to_csv(ENTRY_EXECUTION_PATH, index=False, encoding="utf-8-sig")
    event_price.to_csv(EVENT_PRICE_AUDIT_PATH, index=False, encoding="utf-8-sig")
    _write_report(
        summary_rows,
        findings,
        pnl_concentration,
        top_lots,
        groups["year_summary"],
        groups["product_direction"],
        groups["c9_vs_c4_group"],
        entry_execution,
        event_price,
    )

    metric = summary_rows.set_index("metric")["value"].to_dict()
    hard_fail = findings[findings["severity"].astype(str).eq("P0")]["finding"].astype(str).tolist()
    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": "c9_high_return_plausible_but_not_clean_until_minute_gaps_fixed"
        if hard_fail
        else "c9_high_return_no_hard_bias_found_in_stage900_checks",
        "hard_fail_findings": hard_fail,
        "key_metrics": {str(k): _json_safe(v) for k, v in metric.items()},
        "outputs": {
            "report": str(REPORT_PATH),
            "summary": str(SUMMARY_PATH),
            "findings": str(FINDINGS_PATH),
            "per_lot_audit": str(PER_LOT_PATH),
            "entry_execution_audit": str(ENTRY_EXECUTION_PATH),
            "event_price_audit": str(EVENT_PRICE_AUDIT_PATH),
        },
        "overfit_reflection": {
            "before": "否。只读审计已有 C9 输出，不改参数。",
            "after": "否。没有基于结果新增规则或筛选样本。",
        },
        "continued_value_reflection": {
            "before": "有价值。C9 收益过高必须逐笔解释。",
            "after": "有价值，但下一步应补数据和复验，不应继续调参。",
        },
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
