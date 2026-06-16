from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from pandas.errors import EmptyDataError

from qmt_roll_official_live_config import (
    OFFICIAL_LIVE_ALIAS,
    OFFICIAL_LIVE_CURRENT_POSITIONS_PATH,
    OFFICIAL_LIVE_SUMMARY_PATH,
    OFFICIAL_LIVE_VERSION,
)
from qmt_roll_official_live_phase_d_config import (
    READONLY_SUMMARY_PATH,
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


def _tick_row(ticks: pd.DataFrame, vt_symbol: str) -> dict[str, Any] | None:
    if ticks.empty:
        return None
    if "vt_symbol" in ticks.columns:
        matched = ticks[ticks["vt_symbol"].fillna("").astype(str).eq(vt_symbol)].copy()
    elif "symbol" in ticks.columns and "exchange" in ticks.columns:
        key = ticks["symbol"].fillna("").astype(str) + "." + ticks["exchange"].fillna("").astype(str)
        matched = ticks[key.eq(vt_symbol)].copy()
    else:
        return None
    if matched.empty:
        return None
    for key in ("localtime", "datetime", "snapshot_at", "generated_at"):
        if key in matched.columns:
            matched["_dt"] = pd.to_datetime(matched[key], errors="coerce")
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


def _action_for_position(
    position: dict[str, Any],
    *,
    trades: pd.DataFrame,
    entry_risk: pd.DataFrame,
    ticks: pd.DataFrame,
    target_date: str,
    max_tick_age_seconds: int,
) -> dict[str, Any]:
    vt_symbol = _clean(position.get("vt_symbol"))
    direction = _normalize_direction(position.get("direction"))
    volume = _to_float(position.get("end_pos", position.get("volume", 0.0)), 0.0)
    mark_price = _to_float(position.get("close_price"), 0.0)
    reasons: list[str] = []
    action = "block"

    open_trade = _latest_open_trade(trades, vt_symbol, direction, target_date)
    risk_row = _latest_entry_risk(entry_risk, vt_symbol, direction, target_date)
    tick = _tick_row(ticks, vt_symbol)
    tick_age = _tick_age(tick)
    live_price, live_price_source = _tick_price(tick)

    if not vt_symbol:
        reasons.append("missing_vt_symbol")
    if direction not in {"long", "short"}:
        reasons.append("invalid_direction")
    if volume <= 0:
        reasons.append("no_open_volume")
    if open_trade is None:
        reasons.append("matching_open_trade_missing")
    if risk_row is None:
        reasons.append("matching_entry_risk_missing")
    if tick is None:
        reasons.append("fresh_tick_missing")
    if tick_age is None or tick_age > max_tick_age_seconds:
        reasons.append("fresh_tick_missing_or_stale")
    if live_price <= 0:
        reasons.append("live_price_missing")

    fill_price = _to_float(open_trade.get("price") if open_trade else None, 0.0)
    initial_stop_price = _to_float(risk_row.get("stop_price") if risk_row else None, 0.0)
    open_trade_date = _date_only(open_trade.get("date") if open_trade else "")
    entry_day_active = bool(open_trade_date and open_trade_date == target_date)
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
    if live_price > 0 and risk_price > 0:
        if direction == "long":
            adverse_hit = live_price <= stop_price
            progress_hit = live_price >= progress_price
        else:
            adverse_hit = live_price >= stop_price
            progress_hit = live_price <= progress_price

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
        "volume": volume,
        "open_trade_id": _clean(open_trade.get("trade_id") if open_trade else ""),
        "open_trade_date": open_trade_date,
        "entry_day_active": int(entry_day_active),
        "fill_price": fill_price,
        "initial_stop_price": initial_stop_price,
        "risk_price": risk_price,
        "stop_retry_r": STOP_RETRY_R,
        "stage847_stop_price": stop_price,
        "stage847_progress_price": progress_price,
        "live_price": live_price,
        "live_price_source": live_price_source,
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
                    "volume",
                    "fill_price",
                    "initial_stop_price",
                    "stage847_stop_price",
                    "stage847_progress_price",
                    "live_price",
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
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    official_summary = _read_json(OFFICIAL_LIVE_SUMMARY_PATH)
    target_date = args.target_date or str(official_summary.get("analysis_end", ""))
    paths = _paths(target_date)
    positions = _read_csv_maybe(OFFICIAL_LIVE_CURRENT_POSITIONS_PATH)
    trades = _read_csv_maybe(STAGE901_TRADES_PATH)
    entry_risk = _read_csv_maybe(STAGE901_ENTRY_RISK_PATH)
    ticks = _read_csv_maybe(READONLY_TICKS_PATH)
    readonly_summary = _read_json(READONLY_SUMMARY_PATH)
    config = build_phase_d_config()

    actions = pd.DataFrame(
        [
            _action_for_position(
                row,
                trades=trades,
                entry_risk=entry_risk,
                ticks=ticks,
                target_date=target_date,
                max_tick_age_seconds=args.max_tick_age_seconds,
            )
            for row in positions.to_dict(orient="records")
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
