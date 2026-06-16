from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from pandas.errors import EmptyDataError

from qmt_roll_official_live_execution_ledger import read_execution_ledger, weighted_open_fill
from qmt_roll_official_live_config import (
    OFFICIAL_LIVE_ALIAS,
    OFFICIAL_LIVE_CURRENT_POSITIONS_PATH,
    OFFICIAL_LIVE_SUMMARY_PATH,
    OFFICIAL_LIVE_VERSION,
)
from qmt_roll_official_live_phase_d_config import (
    READONLY_SUMMARY_PATH,
    READONLY_POSITIONS_PATH,
    READONLY_TRADES_PATH,
    READONLY_TICKS_PATH,
    STAGE901_ENTRY_RISK_PATH,
    STAGE901_TRADES_PATH,
    build_phase_d_config,
)
from run_qmt_alignment_backtest import OUTPUT_DIR


MODEL_TAG = "stage904_official_live_c9_intraday_monitor_v1"
OUTPUT_PREFIX = "qmt_roll_stage904_official_live_c9_intraday_monitor"
STOP_RETRY_R = 0.5


def _paths(target_date: str) -> dict[str, Path]:
    date_key = target_date.replace("-", "") if target_date else "latest"
    return {
        "actions_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_actions_{date_key}_{MODEL_TAG}.csv",
        "summary_json": OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{date_key}_{MODEL_TAG}.json",
        "report_md": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{date_key}_{MODEL_TAG}.md",
    }


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_read_error": repr(exc)}


def _read_csv_maybe(path: str | Path | None) -> pd.DataFrame:
    if not path:
        return pd.DataFrame()
    p = Path(path)
    if not p.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(p, encoding="utf-8-sig")
    except EmptyDataError:
        return pd.DataFrame()


def _clean(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def _to_float(value: Any, default: float = 0.0) -> float:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return default
    return float(number)


def _parse_dt(value: Any) -> datetime | None:
    text = _clean(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _age_seconds(value: Any) -> float | None:
    dt = _parse_dt(value)
    if dt is None:
        return None
    now = datetime.now(dt.tzinfo) if dt.tzinfo is not None else datetime.now()
    return round((now - dt).total_seconds(), 3)


def _normalize_direction(value: Any) -> str:
    text = _clean(value).lower()
    if text in {"long", "多", "direction.long"}:
        return "long"
    if text in {"short", "空", "direction.short"}:
        return "short"
    return text


def _normalize_offset(value: Any) -> str:
    text = _clean(value).lower()
    if text in {"open", "开", "offset.open"}:
        return "open"
    if text in {"close", "平", "closetoday", "closeyesterday", "平今", "平昨", "offset.close", "offset.closetoday", "offset.closeyesterday"}:
        return "close"
    return text


def _vt_symbol(row: dict[str, Any]) -> str:
    vt_symbol = _clean(row.get("vt_symbol"))
    if vt_symbol:
        return vt_symbol
    symbol = _clean(row.get("symbol") or row.get("instrument") or row.get("instrument_id"))
    exchange = _clean(row.get("exchange"))
    if symbol and exchange and "." not in symbol:
        return f"{symbol}.{exchange}"
    return symbol


def _date_only(value: Any) -> str:
    text = _clean(value)
    if not text:
        return ""
    try:
        return pd.Timestamp(text).date().isoformat()
    except Exception:
        return text[:10]


def _latest_open_trade(trades: pd.DataFrame, vt_symbol: str, direction: str, target_date: str) -> dict[str, Any] | None:
    if trades.empty:
        return None
    frame = trades.copy()
    frame["direction_norm"] = frame.get("direction", "").map(_normalize_direction)
    frame["offset_norm"] = frame.get("offset", "").map(_normalize_offset)
    frame["date_norm"] = frame.get("date", "").map(_date_only)
    matched = frame[
        frame.get("vt_symbol", "").astype(str).eq(vt_symbol)
        & frame["direction_norm"].eq(direction)
        & frame["offset_norm"].eq("open")
        & frame["date_norm"].le(target_date)
    ].copy()
    if matched.empty:
        return None
    matched["_dt"] = pd.to_datetime(matched.get("datetime", matched["date_norm"]), errors="coerce")
    return matched.sort_values("_dt").iloc[-1].to_dict()


def _weighted_broker_open_trade(trades: pd.DataFrame, vt_symbol: str, direction: str, target_date: str) -> dict[str, Any] | None:
    if trades.empty:
        return None
    frame = trades.copy()
    frame["direction_norm"] = frame.get("direction", "").map(_normalize_direction)
    frame["offset_norm"] = frame.get("offset", "").map(_normalize_offset)
    date_source = frame.get("datetime", frame.get("date", frame.get("trading_day", "")))
    frame["date_norm"] = date_source.map(_date_only) if hasattr(date_source, "map") else ""
    matched = frame[
        frame.get("vt_symbol", "").astype(str).eq(vt_symbol)
        & frame["direction_norm"].eq(direction)
        & frame["offset_norm"].eq("open")
        & frame["date_norm"].eq(target_date)
    ].copy()
    if matched.empty:
        return None
    matched["price_num"] = pd.to_numeric(matched.get("price", 0.0), errors="coerce").fillna(0.0)
    matched["volume_num"] = pd.to_numeric(matched.get("volume", 0.0), errors="coerce").fillna(0.0)
    matched = matched[matched["price_num"].gt(0) & matched["volume_num"].gt(0)]
    if matched.empty:
        return None
    total_volume = float(matched["volume_num"].sum())
    weighted_price = float((matched["price_num"] * matched["volume_num"]).sum() / total_volume)
    matched["_dt"] = pd.to_datetime(matched.get("datetime", matched["date_norm"]), errors="coerce")
    latest = matched.sort_values("_dt").iloc[-1].to_dict()
    return {
        **latest,
        "price": weighted_price,
        "volume": total_volume,
        "trade_count": int(len(matched)),
        "date": target_date,
    }


def _latest_entry_risk(entry_risk: pd.DataFrame, vt_symbol: str, direction: str, target_date: str) -> dict[str, Any] | None:
    if entry_risk.empty:
        return None
    frame = entry_risk.copy()
    frame["direction_norm"] = frame.get("direction", "").map(_normalize_direction)
    frame["date_norm"] = frame.get("date", "").map(_date_only)
    matched = frame[
        frame.get("contract_vt_symbol", "").astype(str).eq(vt_symbol)
        & frame["direction_norm"].eq(direction)
        & frame["date_norm"].le(target_date)
    ].copy()
    if matched.empty:
        return None
    matched["_dt"] = pd.to_datetime(matched.get("datetime", matched["date_norm"]), errors="coerce")
    return matched.sort_values("_dt").iloc[-1].to_dict()


def _tick_frame(ticks: pd.DataFrame, vt_symbol: str) -> pd.DataFrame:
    if ticks.empty:
        return pd.DataFrame()
    if "vt_symbol" in ticks.columns:
        matched = ticks[ticks["vt_symbol"].fillna("").astype(str).eq(vt_symbol)].copy()
    elif "symbol" in ticks.columns and "exchange" in ticks.columns:
        key = ticks["symbol"].fillna("").astype(str) + "." + ticks["exchange"].fillna("").astype(str)
        matched = ticks[key.eq(vt_symbol)].copy()
    else:
        return pd.DataFrame()
    return matched


def _tick_dt_series(frame: pd.DataFrame) -> pd.Series:
    for key in ("localtime", "datetime", "snapshot_at", "generated_at"):
        if key in frame.columns:
            return pd.to_datetime(frame[key], errors="coerce")
    return pd.Series(pd.NaT, index=frame.index)


def _fresh_tick_frame(ticks: pd.DataFrame, vt_symbol: str, max_tick_age_seconds: int) -> pd.DataFrame:
    matched = _tick_frame(ticks, vt_symbol)
    if matched.empty:
        return matched
    matched = matched.copy()
    matched["_dt"] = _tick_dt_series(matched)
    matched = matched.dropna(subset=["_dt"])
    if matched.empty:
        return matched
    now = pd.Timestamp.now(tz=matched["_dt"].dt.tz) if matched["_dt"].dt.tz is not None else pd.Timestamp.now()
    ages = (now - matched["_dt"]).dt.total_seconds()
    return matched[ages.le(max_tick_age_seconds)].copy()


def _tick_row(ticks: pd.DataFrame, vt_symbol: str) -> dict[str, Any] | None:
    matched = _tick_frame(ticks, vt_symbol)
    if matched.empty:
        return None
    matched = matched.copy()
    matched["_dt"] = _tick_dt_series(matched)
    if matched["_dt"].notna().any():
        return matched.sort_values("_dt").iloc[-1].to_dict()
    return matched.iloc[-1].to_dict()


def _tick_age(row: dict[str, Any] | None) -> float | None:
    if not row:
        return None
    for key in ("localtime", "datetime", "snapshot_at", "generated_at"):
        if key in row:
            age = _age_seconds(row.get(key))
            if age is not None:
                return age
    return None


def _tick_price(row: dict[str, Any] | None) -> tuple[float, str]:
    if not row:
        return 0.0, "missing_tick"
    for key in ("last_price", "last", "price", "close_price"):
        value = _to_float(row.get(key), 0.0)
        if value > 0:
            return value, key
    bid = _to_float(row.get("bid_price_1"), 0.0)
    ask = _to_float(row.get("ask_price_1"), 0.0)
    if bid > 0 and ask > 0:
        return round((bid + ask) / 2, 10), "mid_bid_ask"
    if bid > 0:
        return bid, "bid_price_1"
    if ask > 0:
        return ask, "ask_price_1"
    return 0.0, "missing_tick_price"


def _tick_value(row: dict[str, Any] | None, *keys: str) -> float:
    if not row:
        return 0.0
    for key in keys:
        value = _to_float(row.get(key), 0.0)
        if value > 0:
            return value
    return 0.0


def _fresh_extreme_price(frame: pd.DataFrame, direction: str, kind: str) -> tuple[float, str]:
    if frame.empty:
        return 0.0, "missing_fresh_tick_batch"
    if kind == "adverse" and direction == "long":
        keys = ("last_price", "last", "price", "close_price", "bid_price_1")
        method = "min"
    elif kind == "adverse" and direction == "short":
        keys = ("last_price", "last", "price", "close_price", "ask_price_1")
        method = "max"
    elif kind == "progress" and direction == "long":
        keys = ("last_price", "last", "price", "close_price", "ask_price_1")
        method = "max"
    else:
        keys = ("last_price", "last", "price", "close_price", "bid_price_1")
        method = "min"
    values: list[tuple[str, float]] = []
    for key in keys:
        if key not in frame.columns:
            continue
        series = pd.to_numeric(frame[key], errors="coerce").dropna()
        series = series[series.gt(0)]
        if series.empty:
            continue
        value = float(series.min() if method == "min" else series.max())
        values.append((key, value))
    if not values:
        return 0.0, "missing_fresh_tick_price_batch"
    if method == "min":
        source, value = min(values, key=lambda item: item[1])
    else:
        source, value = max(values, key=lambda item: item[1])
    return value, f"{method}_{source}_fresh_batch"


def _broker_position_price(row: dict[str, Any]) -> tuple[float, str]:
    for key in ("price", "avg_price", "open_price", "cost_price"):
        price = _to_float(row.get(key), 0.0)
        if price > 0:
            return price, key
    return 0.0, "broker_fill_price_missing"


def _broker_position_volume(row: dict[str, Any]) -> float:
    volume = _to_float(row.get("volume", row.get("position", row.get("pos", 0.0))), 0.0)
    frozen = _to_float(row.get("frozen", row.get("frozen_volume", 0.0)), 0.0)
    return max(0.0, volume - frozen)


def _monitor_positions(shadow_positions: pd.DataFrame, broker_positions: pd.DataFrame) -> pd.DataFrame:
    keyed: dict[tuple[str, str], dict[str, Any]] = {}
    for row in shadow_positions.to_dict(orient="records"):
        vt_symbol = _clean(row.get("vt_symbol"))
        direction = _normalize_direction(row.get("direction"))
        volume = _to_float(row.get("end_pos", row.get("volume", 0.0)), 0.0)
        if not vt_symbol or direction not in {"long", "short"} or volume <= 0:
            continue
        item = dict(row)
        item["position_source"] = "shadow"
        item["volume"] = volume
        keyed[(vt_symbol, direction)] = item

    for row in broker_positions.drop_duplicates().to_dict(orient="records"):
        vt_symbol = _vt_symbol(row)
        direction = _normalize_direction(row.get("direction"))
        volume = _broker_position_volume(row)
        if not vt_symbol or direction not in {"long", "short"} or volume <= 0:
            continue
        price, price_source = _broker_position_price(row)
        item = dict(row)
        item["vt_symbol"] = vt_symbol
        item["direction"] = direction
        item["position_source"] = "broker"
        item["volume"] = volume
        item["end_pos"] = volume
        item["broker_fill_price"] = price
        item["broker_fill_price_source"] = price_source
        keyed[(vt_symbol, direction)] = item

    return pd.DataFrame(list(keyed.values()))


def _action_for_position(
    position: dict[str, Any],
    *,
    trades: pd.DataFrame,
    broker_trades: pd.DataFrame,
    execution_ledger_rows: list[dict[str, Any]],
    entry_risk: pd.DataFrame,
    ticks: pd.DataFrame,
    target_date: str,
    max_tick_age_seconds: int,
    require_broker_fill_price: bool,
) -> dict[str, Any]:
    vt_symbol = _clean(position.get("vt_symbol"))
    direction = _normalize_direction(position.get("direction"))
    volume = _to_float(position.get("end_pos", position.get("volume", 0.0)), 0.0)
    mark_price = _to_float(position.get("close_price"), 0.0)
    position_source = _clean(position.get("position_source")) or "shadow"
    broker_position_avg_price = _to_float(position.get("broker_fill_price"), 0.0)
    broker_position_avg_price_source = _clean(position.get("broker_fill_price_source"))
    reasons: list[str] = []
    action = "block"

    open_trade = _latest_open_trade(trades, vt_symbol, direction, target_date)
    ledger_open_trade = weighted_open_fill(execution_ledger_rows, target_date, vt_symbol, direction)
    broker_open_trade = _weighted_broker_open_trade(broker_trades, vt_symbol, direction, target_date)
    risk_row = _latest_entry_risk(entry_risk, vt_symbol, direction, target_date)
    tick = _tick_row(ticks, vt_symbol)
    fresh_ticks = _fresh_tick_frame(ticks, vt_symbol, max_tick_age_seconds)
    tick_age = _tick_age(tick)
    live_price, live_price_source = _tick_price(tick)
    adverse_extreme_price, adverse_extreme_source = _fresh_extreme_price(fresh_ticks, direction, "adverse")
    progress_extreme_price, progress_extreme_source = _fresh_extreme_price(fresh_ticks, direction, "progress")

    if not vt_symbol:
        reasons.append("missing_vt_symbol")
    if direction not in {"long", "short"}:
        reasons.append("invalid_direction")
    if volume <= 0:
        reasons.append("no_open_volume")
    ledger_fill_price = _to_float(ledger_open_trade.get("price") if ledger_open_trade else None, 0.0)
    broker_fill_price = _to_float(broker_open_trade.get("price") if broker_open_trade else None, 0.0)
    if open_trade is None and ledger_fill_price <= 0 and broker_fill_price <= 0:
        reasons.append("matching_open_trade_missing")
    if risk_row is None:
        reasons.append("matching_entry_risk_missing")
    if require_broker_fill_price and ledger_fill_price <= 0 and broker_fill_price <= 0:
        reasons.append("broker_or_execution_open_trade_fill_price_missing_for_live_real_monitor")
    if tick is None:
        reasons.append("fresh_tick_missing")
    if tick_age is None or tick_age > max_tick_age_seconds:
        reasons.append("fresh_tick_missing_or_stale")
    if live_price <= 0:
        reasons.append("live_price_missing")

    shadow_fill_price = _to_float(open_trade.get("price") if open_trade else None, 0.0)
    if ledger_fill_price > 0:
        fill_price = ledger_fill_price
        fill_price_source = "stage931_execution_ledger_open_fill_weighted_avg"
    elif broker_fill_price > 0:
        fill_price = broker_fill_price
        fill_price_source = "readonly_broker_open_trade_weighted_avg"
    else:
        fill_price = shadow_fill_price
        fill_price_source = "shadow_open_trade_price"
    initial_stop_price = _to_float(risk_row.get("stop_price") if risk_row else None, 0.0)
    open_trade_date = _date_only(open_trade.get("date") if open_trade else "")
    risk_date = _date_only(risk_row.get("date") if risk_row else "")
    broker_open_trade_date = _date_only(broker_open_trade.get("date") if broker_open_trade else "")
    ledger_open_trade_date = _date_only(ledger_open_trade.get("date") if ledger_open_trade else "")
    entry_day_active = bool(
        (open_trade_date and open_trade_date == target_date)
        or (
            position_source == "broker"
            and risk_date == target_date
            and (ledger_open_trade_date == target_date or broker_open_trade_date == target_date)
        )
    )
    if not entry_day_active:
        reasons.append("c9_entry_day_monitor_not_active")
    risk_price = abs(fill_price - initial_stop_price) if fill_price > 0 and initial_stop_price > 0 else 0.0
    if risk_price <= 0:
        reasons.append("invalid_risk_price")

    sign = 1.0 if direction == "long" else -1.0
    stop_price = fill_price - sign * STOP_RETRY_R * risk_price if risk_price > 0 else 0.0
    progress_price = fill_price + sign * STOP_RETRY_R * risk_price if risk_price > 0 else 0.0
    adverse_hit = False
    progress_hit = False
    if risk_price > 0:
        if direction == "long":
            adverse_hit = adverse_extreme_price > 0 and adverse_extreme_price <= stop_price
            progress_hit = progress_extreme_price > 0 and progress_extreme_price >= progress_price
        else:
            adverse_hit = adverse_extreme_price > 0 and adverse_extreme_price >= stop_price
            progress_hit = progress_extreme_price > 0 and progress_extreme_price <= progress_price

    if not reasons:
        if adverse_hit:
            action = "close_dry_run"
            reasons.append("stage847_initial_05r_stop_triggered")
        elif progress_hit:
            action = "watch_progress_hit_no_initial_stop"
            reasons.append("stage847_progress_hit_before_adverse")
        else:
            action = "watch"
            reasons.append("no_stage847_intraday_action")

    return {
        "target_date": target_date,
        "vt_symbol": vt_symbol,
        "direction": direction,
        "position_source": position_source,
        "volume": volume,
        "open_trade_id": _clean(open_trade.get("trade_id") if open_trade else ""),
        "open_trade_date": open_trade_date,
        "ledger_open_trade_date": ledger_open_trade_date,
        "ledger_open_trade_count": int(_to_float(ledger_open_trade.get("trade_count") if ledger_open_trade else 0, 0.0)),
        "ledger_open_trade_volume": _to_float(ledger_open_trade.get("volume") if ledger_open_trade else 0.0, 0.0),
        "broker_open_trade_date": broker_open_trade_date,
        "broker_open_trade_count": int(_to_float(broker_open_trade.get("trade_count") if broker_open_trade else 0, 0.0)),
        "broker_open_trade_volume": _to_float(broker_open_trade.get("volume") if broker_open_trade else 0.0, 0.0),
        "entry_risk_date": risk_date,
        "entry_day_active": int(entry_day_active),
        "fill_price": fill_price,
        "fill_price_source": fill_price_source,
        "ledger_fill_price": ledger_fill_price,
        "broker_fill_price": broker_fill_price,
        "broker_position_avg_price": broker_position_avg_price,
        "broker_position_avg_price_source": broker_position_avg_price_source,
        "initial_stop_price": initial_stop_price,
        "risk_price": risk_price,
        "stop_retry_r": STOP_RETRY_R,
        "stage847_stop_price": stop_price,
        "stage847_progress_price": progress_price,
        "live_price": live_price,
        "live_price_source": live_price_source,
        "live_bid_price_1": _tick_value(tick, "bid_price_1"),
        "live_ask_price_1": _tick_value(tick, "ask_price_1"),
        "live_limit_up": _tick_value(tick, "limit_up", "upper_limit", "limit_up_price"),
        "live_limit_down": _tick_value(tick, "limit_down", "lower_limit", "limit_down_price"),
        "adverse_extreme_price": adverse_extreme_price,
        "adverse_extreme_source": adverse_extreme_source,
        "progress_extreme_price": progress_extreme_price,
        "progress_extreme_source": progress_extreme_source,
        "tick_batch_count": int(len(_tick_frame(ticks, vt_symbol))),
        "fresh_tick_batch_count": int(len(fresh_ticks)),
        "tick_age_seconds": tick_age,
        "mark_price_fallback": mark_price,
        "adverse_hit": int(adverse_hit),
        "progress_hit": int(progress_hit),
        "monitor_action": action,
        "monitor_reason": ";".join(dict.fromkeys(reasons)),
        "order_api_called": 0,
        "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def _to_markdown(df: pd.DataFrame, columns: list[str], max_rows: int = 80) -> str:
    if df.empty:
        return "_empty_"
    return df.loc[:, [column for column in columns if column in df.columns]].head(max_rows).to_markdown(index=False)


def _build_report(summary: dict[str, Any], actions: pd.DataFrame) -> str:
    return "\n".join(
        [
            "# Stage904 Official Live C9 Intraday Monitor",
            "",
            f"- 生成时间：`{summary['generated_at']}`",
            f"- 当前官方实盘：`{summary['official_live_version']}` / `{summary['official_live_alias']}`",
            f"- 目标日期：`{summary['target_date']}`",
            f"- monitor 状态：`{summary['monitor_status']}`",
            f"- 动作数：`{summary['action_count']}`",
            f"- close dry-run 数：`{summary['close_dry_run_count']}`",
            f"- order API 调用次数：`{summary['order_api_called_count']}`",
            "",
            "## Actions",
            "",
            _to_markdown(
                actions,
                [
                    "vt_symbol",
                    "direction",
                    "position_source",
                    "volume",
                    "fill_price",
                    "fill_price_source",
                    "initial_stop_price",
                    "stage847_stop_price",
                    "stage847_progress_price",
                    "live_price",
                    "adverse_extreme_price",
                    "fresh_tick_batch_count",
                    "tick_age_seconds",
                    "monitor_action",
                    "monitor_reason",
                ],
            ),
            "",
            "## 说明",
            "",
            "- 本阶段只计算 C9 入场日 `0.5R` 止损/重试状态，不连接 CTP，不下单。",
            "- 没有 fresh tick 时必须 fail-closed，不能用历史收盘价触发实盘动作。",
            "- 重试执行还需要真实订单/成交回报状态机，本阶段只覆盖初始 0.5R 监控 dry-run。",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Dry-run C9 intraday 0.5R stop/retry monitor for official live.")
    parser.add_argument("--target-date", default="", help="Target completed trading day. Defaults to official summary analysis_end.")
    parser.add_argument("--max-tick-age-seconds", type=int, default=10)
    parser.add_argument("--require-broker-fill-price", action="store_true")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    official_summary = _read_json(OFFICIAL_LIVE_SUMMARY_PATH)
    target_date = args.target_date or str(official_summary.get("analysis_end", ""))
    paths = _paths(target_date)
    positions = _read_csv_maybe(OFFICIAL_LIVE_CURRENT_POSITIONS_PATH)
    broker_positions = _read_csv_maybe(READONLY_POSITIONS_PATH)
    broker_trades = _read_csv_maybe(READONLY_TRADES_PATH)
    execution_ledger_rows = read_execution_ledger()
    trades = _read_csv_maybe(STAGE901_TRADES_PATH)
    entry_risk = _read_csv_maybe(STAGE901_ENTRY_RISK_PATH)
    ticks = _read_csv_maybe(READONLY_TICKS_PATH)
    readonly_summary = _read_json(READONLY_SUMMARY_PATH)
    config = build_phase_d_config()
    monitor_positions = _monitor_positions(positions, broker_positions)

    actions = pd.DataFrame(
        [
            _action_for_position(
                row,
                trades=trades,
                broker_trades=broker_trades,
                execution_ledger_rows=execution_ledger_rows,
                entry_risk=entry_risk,
                ticks=ticks,
                target_date=target_date,
                max_tick_age_seconds=args.max_tick_age_seconds,
                require_broker_fill_price=bool(args.require_broker_fill_price),
            )
            for row in monitor_positions.to_dict(orient="records")
        ]
    )
    close_dry_run_count = int(actions.get("monitor_action", pd.Series(dtype=str)).astype(str).eq("close_dry_run").sum()) if not actions.empty else 0
    blocked_count = int(actions.get("monitor_action", pd.Series(dtype=str)).astype(str).eq("block").sum()) if not actions.empty else 0
    order_api_called = int(actions.get("order_api_called", pd.Series(dtype=float)).sum()) if not actions.empty else 0
    monitor_status = "intraday_monitor_blocked" if blocked_count else "intraday_monitor_ready"
    if close_dry_run_count:
        monitor_status = "intraday_monitor_close_dry_run"

    summary = {
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "target_date": target_date,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "monitor_status": monitor_status,
        "action_count": int(len(actions)),
        "blocked_count": blocked_count,
        "close_dry_run_count": close_dry_run_count,
        "order_api_called_count": order_api_called,
        "readonly_status": readonly_summary.get("status", ""),
        "tick_path": str(READONLY_TICKS_PATH.resolve()),
        "require_broker_fill_price": int(bool(args.require_broker_fill_price)),
        "shadow_position_rows": int(len(positions)),
        "broker_position_rows": int(len(broker_positions)),
        "broker_trade_rows": int(len(broker_trades)),
        "execution_ledger_rows": int(len(execution_ledger_rows)),
        "monitor_position_rows": int(len(monitor_positions)),
        "phase_d_hard_limits": config.hard_limits.__dict__,
        "outputs": {key: str(value.resolve()) for key, value in paths.items()},
        "judgement": {
            "overfit_before": "否。C9 盘中监控只复刻已冻结的 0.5R 止损/重试状态机，不改参数。",
            "continue_before": "是。没有盘中监控，C9 无法全自动执行入场日风控。",
            "overfit_after": "否。没有根据监控结果调整策略。",
            "continue_after": "是。下一步需要把该 monitor 接入 Stage903，并补订单/成交状态机以支持 retry。",
        },
    }
    actions.to_csv(paths["actions_csv"], index=False, encoding="utf-8-sig")
    paths["summary_json"].write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths["report_md"].write_text(_build_report(summary, actions), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
