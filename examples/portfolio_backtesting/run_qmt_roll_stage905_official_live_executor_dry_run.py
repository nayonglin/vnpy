from __future__ import annotations

import argparse
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from pandas.errors import EmptyDataError

from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION
from qmt_roll_official_live_phase_d_config import (
    READONLY_CONTRACTS_PATH,
    READONLY_ORDERS_PATH,
    READONLY_POSITIONS_PATH,
    STAGE901_PENDING_ORDERS_PATH,
    build_phase_d_config,
)
from run_qmt_alignment_backtest import OUTPUT_DIR
from vnpy.trader.constant import Direction, Exchange, Offset, OrderType
from vnpy.trader.object import OrderRequest


MODEL_TAG = "stage905_official_live_executor_dry_run_v1"
OUTPUT_PREFIX = "qmt_roll_stage905_official_live_executor_dry_run"
STAGE902_MODEL_TAG = "stage902_official_live_phase_d_readiness_gate_v1"
STAGE902_PREFIX = "qmt_roll_stage902_official_live_phase_d_readiness_gate"
STAGE904_MODEL_TAG = "stage904_official_live_c9_intraday_monitor_v1"
STAGE904_PREFIX = "qmt_roll_stage904_official_live_c9_intraday_monitor"
STAGE260_MODEL_TAG = "stage260_official_live_daily_execution_gate_v1"
STAGE260_PREFIX = "qmt_roll_stage260_official_live_daily_execution_gate"


def _paths(target_date: str) -> dict[str, Path]:
    date_key = target_date.replace("-", "") if target_date else "latest"
    return {
        "intents_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_intents_{date_key}_{MODEL_TAG}.csv",
        "summary_json": OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{date_key}_{MODEL_TAG}.json",
        "report_md": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{date_key}_{MODEL_TAG}.md",
    }


def _stage902_summary_path(target_date: str) -> Path:
    date_key = target_date.replace("-", "") if target_date else "latest"
    return OUTPUT_DIR / f"{STAGE902_PREFIX}_summary_{date_key}_{STAGE902_MODEL_TAG}.json"


def _stage904_actions_path(target_date: str) -> Path:
    date_key = target_date.replace("-", "") if target_date else "latest"
    return OUTPUT_DIR / f"{STAGE904_PREFIX}_actions_{date_key}_{STAGE904_MODEL_TAG}.csv"


def _stage260_summary_path(target_date: str) -> Path:
    date_key = target_date.replace("-", "") if target_date else "latest"
    return OUTPUT_DIR / f"{STAGE260_PREFIX}_summary_{date_key}_{STAGE260_MODEL_TAG}.json"


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


def _normalize_direction_text(value: Any) -> str:
    text = _clean(value).lower()
    if text in {"long", "多", "direction.long"}:
        return "long"
    if text in {"short", "空", "direction.short"}:
        return "short"
    return text


def _normalize_offset_text(value: Any) -> str:
    text = _clean(value).lower()
    if text in {"open", "开", "offset.open"}:
        return "open"
    if text in {"close", "平", "closetoday", "closeyesterday", "平今", "平昨", "offset.close", "offset.closetoday", "offset.closeyesterday"}:
        return "close"
    return text


def _normalize_direction(value: Any) -> Direction | None:
    text = _normalize_direction_text(value)
    if text == "long":
        return Direction.LONG
    if text == "short":
        return Direction.SHORT
    return None


def _normalize_offset(value: Any) -> Offset | None:
    text = _normalize_offset_text(value)
    if text == "open":
        return Offset.OPEN
    if text == "close":
        return Offset.CLOSE
    return None


def _split_vt_symbol(vt_symbol: str) -> tuple[str, str]:
    if "." not in vt_symbol:
        return vt_symbol, ""
    return vt_symbol.rsplit(".", 1)


def _contract_row(contracts: pd.DataFrame, vt_symbol: str) -> dict[str, Any] | None:
    if contracts.empty:
        return None
    symbol, exchange = _split_vt_symbol(vt_symbol)
    if "vt_symbol" in contracts.columns:
        matched = contracts[contracts["vt_symbol"].fillna("").astype(str).eq(vt_symbol)]
        if not matched.empty:
            return matched.iloc[0].to_dict()
    if "symbol" in contracts.columns and "exchange" in contracts.columns:
        matched = contracts[
            contracts["symbol"].fillna("").astype(str).eq(symbol)
            & contracts["exchange"].fillna("").astype(str).eq(exchange)
        ]
        if not matched.empty:
            return matched.iloc[0].to_dict()
    return None


def _price_on_tick(price: float, pricetick: float) -> bool:
    if price <= 0 or pricetick <= 0:
        return False
    units = price / pricetick
    return math.isclose(units, round(units), rel_tol=0.0, abs_tol=1e-8)


def _snap_price_to_tick(price: float, pricetick: float, direction: str) -> float:
    if price <= 0 or pricetick <= 0:
        return price
    units = price / pricetick
    if direction == "short":
        return round(math.floor(units) * pricetick, 10)
    if direction == "long":
        return round(math.ceil(units) * pricetick, 10)
    return price


def _opposite_position_direction(order_direction: str) -> str:
    if order_direction == "long":
        return "short"
    if order_direction == "short":
        return "long"
    return ""


def _position_volume(positions: pd.DataFrame, vt_symbol: str, direction: str) -> float:
    if positions.empty:
        return 0.0
    frame = positions.drop_duplicates().copy()
    if "vt_symbol" in frame.columns:
        vt = frame["vt_symbol"].fillna("").astype(str)
    elif "symbol" in frame.columns and "exchange" in frame.columns:
        vt = frame["symbol"].fillna("").astype(str) + "." + frame["exchange"].fillna("").astype(str)
    elif "instrument" in frame.columns:
        vt = frame["instrument"].fillna("").astype(str)
    else:
        return 0.0
    pos_direction = frame.get("direction", pd.Series([""] * len(frame))).map(_normalize_direction_text)
    volume = pd.to_numeric(frame.get("volume", frame.get("position", frame.get("pos", 0.0))), errors="coerce").fillna(0.0)
    frozen = pd.to_numeric(frame.get("frozen", 0.0), errors="coerce").fillna(0.0)
    available = (volume - frozen).clip(lower=0.0)
    return float(available[vt.eq(vt_symbol) & pos_direction.eq(direction)].sum())


def _active_order_count(orders: pd.DataFrame) -> int:
    if orders.empty or "status" not in orders.columns:
        return 0
    active = {"submitting", "submitted", "not traded", "nottraded", "part traded", "parttraded", "未成交", "提交中", "部分成交"}
    return int(orders["status"].fillna("").astype(str).str.strip().str.lower().isin(active).sum())


def _pending_order_intents(pending_orders: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx, row in enumerate(pending_orders.to_dict(orient="records"), start=1):
        vt_symbol = _clean(row.get("vt_symbol"))
        rows.append(
            {
                "intent_id": f"STAGE905-PENDING-{idx:03d}",
                "source": "stage901_pending_order",
                "vt_symbol": vt_symbol,
                "direction": _normalize_direction_text(row.get("direction")),
                "offset": _normalize_offset_text(row.get("offset")),
                "planned_volume": _to_float(row.get("volume"), 0.0),
                "limit_price": _to_float(row.get("price"), 0.0),
                "source_reason": _clean(row.get("status")),
            }
        )
    return rows


def _stage904_intents(stage904_actions: pd.DataFrame) -> list[dict[str, Any]]:
    if stage904_actions.empty or "monitor_action" not in stage904_actions.columns:
        return []
    rows: list[dict[str, Any]] = []
    close_actions = stage904_actions[stage904_actions["monitor_action"].astype(str).eq("close_dry_run")]
    for idx, row in enumerate(close_actions.to_dict(orient="records"), start=1):
        current_direction = _normalize_direction_text(row.get("direction"))
        close_direction = "short" if current_direction == "long" else "long" if current_direction == "short" else ""
        rows.append(
            {
                "intent_id": f"STAGE905-C9MON-{idx:03d}",
                "source": "stage904_c9_intraday_close",
                "vt_symbol": _clean(row.get("vt_symbol")),
                "direction": close_direction,
                "offset": "close",
                "planned_volume": _to_float(row.get("volume"), 0.0),
                "limit_price": _to_float(row.get("stage847_stop_price"), 0.0),
                "source_reason": _clean(row.get("monitor_reason")),
            }
        )
    return rows


def _dedupe_close_intents(intents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    passthrough: list[dict[str, Any]] = []
    for intent in intents:
        vt_symbol = _clean(intent.get("vt_symbol"))
        direction = _normalize_direction_text(intent.get("direction"))
        offset = _normalize_offset_text(intent.get("offset"))
        if offset != "close":
            passthrough.append(intent)
            continue
        grouped.setdefault((vt_symbol, direction, offset), []).append(intent)

    def priority(row: dict[str, Any]) -> tuple[int, float]:
        source = _clean(row.get("source"))
        source_priority = 0 if source == "stage904_c9_intraday_close" else 1 if source == "stage901_pending_order" else 9
        return source_priority, -_to_float(row.get("planned_volume"), 0.0)

    deduped: list[dict[str, Any]] = list(passthrough)
    for rows in grouped.values():
        if len(rows) == 1:
            deduped.append(rows[0])
            continue
        ordered = sorted(rows, key=priority)
        kept = dict(ordered[0])
        removed = ordered[1:]
        removed_sources = ",".join(_clean(row.get("source")) for row in removed)
        kept["dedupe_removed_count"] = len(removed)
        kept["dedupe_removed_sources"] = removed_sources
        reason = _clean(kept.get("source_reason"))
        suffix = f"deduped_close_intents_removed={len(removed)}:{removed_sources}"
        kept["source_reason"] = f"{reason};{suffix}" if reason else suffix
        deduped.append(kept)
    return deduped


def _validate_intent(
    intent: dict[str, Any],
    *,
    contracts: pd.DataFrame,
    positions: pd.DataFrame,
    orders: pd.DataFrame,
    stage902_summary: dict[str, Any],
    stage260_summary: dict[str, Any],
    mode: str,
) -> dict[str, Any]:
    config = build_phase_d_config()
    reasons: list[str] = []
    vt_symbol = _clean(intent.get("vt_symbol"))
    symbol, exchange_value = _split_vt_symbol(vt_symbol)
    direction_text = _normalize_direction_text(intent.get("direction"))
    offset_text = _normalize_offset_text(intent.get("offset"))
    direction = _normalize_direction(direction_text)
    offset = _normalize_offset(offset_text)
    price = _to_float(intent.get("limit_price"), 0.0)
    volume = _to_float(intent.get("planned_volume"), 0.0)
    contract = _contract_row(contracts, vt_symbol)
    active_orders = _active_order_count(orders)
    stage902_blocking = int(_to_float(stage902_summary.get("blocking_failure_count"), 999))
    stage260_executable = int(_to_float(stage260_summary.get("executable_count"), 0))

    if stage902_blocking > 0:
        reasons.append(f"stage902_blocking_failure_count={stage902_blocking}")
    if mode != "dry-run":
        reasons.append("stage905_never_submits_live_orders")
    if active_orders > config.hard_limits.max_open_order_count:
        reasons.append(f"active_order_count={active_orders}")
    if not symbol or not exchange_value:
        reasons.append("invalid_vt_symbol")
    if direction is None:
        reasons.append("invalid_direction")
    if offset is None:
        reasons.append("invalid_offset")
    if contract is None:
        reasons.append("contract_not_found")
    if volume <= 0:
        reasons.append("invalid_volume")
    if volume > config.hard_limits.max_single_order_volume:
        reasons.append(f"volume_above_phase_d_limit:{volume}>{config.hard_limits.max_single_order_volume}")
    if not float(volume).is_integer():
        reasons.append("volume_not_integer_lots")
    if price <= 0:
        reasons.append("invalid_price")

    pricetick = _to_float(contract.get("pricetick") if contract else None, 0.0)
    min_volume = _to_float(contract.get("min_volume") if contract else None, 0.0)
    max_volume = _to_float(contract.get("max_volume") if contract else None, 0.0)
    price_adjustment_reason = ""
    if pricetick and price > 0 and not _price_on_tick(price, pricetick):
        original_price = price
        price = _snap_price_to_tick(price, pricetick, direction_text)
        price_adjustment_reason = f"limit_price_snapped_to_tick:{original_price}->{price}"
    if pricetick and not _price_on_tick(price, pricetick):
        reasons.append("price_not_on_tick")
    if min_volume and volume < min_volume:
        reasons.append("volume_below_min")
    if max_volume and volume > max_volume:
        reasons.append("volume_above_contract_max")
    broker_match_volume = 0.0
    if offset_text == "close":
        broker_match_direction = _opposite_position_direction(direction_text)
        broker_match_volume = _position_volume(positions, vt_symbol, broker_match_direction)
        if broker_match_volume <= 0:
            reasons.append(f"no_matching_{broker_match_direction}_broker_position_to_close")
        elif broker_match_volume < volume:
            reasons.append(f"insufficient_broker_position:{broker_match_volume}<{volume}")
        if stage260_executable <= 0:
            reasons.append("stage260_no_executable_close_gate")
    elif offset_text == "open":
        if stage260_executable <= 0:
            reasons.append("stage260_no_executable_open_gate")

    order_request_payload: dict[str, Any] = {}
    status = "blocked" if reasons else "dry_run_order_request_payload_ready"
    if not reasons and direction and offset:
        req = OrderRequest(
            symbol=symbol,
            exchange=Exchange(exchange_value),
            direction=direction,
            type=OrderType.LIMIT,
            volume=volume,
            price=price,
            offset=offset,
            reference=f"Stage905PhaseD:{intent.get('intent_id')}",
        )
        order_request_payload = {
            "symbol": req.symbol,
            "exchange": req.exchange.value,
            "direction": req.direction.value,
            "type": req.type.value,
            "volume": req.volume,
            "price": req.price,
            "offset": req.offset.value,
            "reference": req.reference,
            "vt_symbol": req.vt_symbol,
            "gateway_name": _clean(contract.get("gateway_name") if contract else "CTP") or "CTP",
        }

    return {
        **intent,
        "executor_mode": mode,
        "executor_status": status,
        "executor_reason": ";".join(dict.fromkeys(reasons)),
        "symbol": symbol,
        "exchange": exchange_value,
        "pricetick": pricetick,
        "price_adjustment_reason": price_adjustment_reason,
        "broker_matching_position_volume": broker_match_volume,
        "active_order_count": active_orders,
        "order_request_json": json.dumps(order_request_payload, ensure_ascii=False, sort_keys=True),
        "send_order_api_called": 0,
        "cancel_order_api_called": 0,
        "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def _to_markdown(df: pd.DataFrame, columns: list[str], max_rows: int = 80) -> str:
    if df.empty:
        return "_empty_"
    return df.loc[:, [column for column in columns if column in df.columns]].head(max_rows).to_markdown(index=False)


def _build_report(summary: dict[str, Any], intents: pd.DataFrame) -> str:
    return "\n".join(
        [
            "# Stage905 Official Live Executor Dry Run",
            "",
            f"- 生成时间：`{summary['generated_at']}`",
            f"- 当前官方实盘：`{summary['official_live_version']}` / `{summary['official_live_alias']}`",
            f"- 目标日期：`{summary['target_date']}`",
            f"- executor 状态：`{summary['executor_status']}`",
            f"- intent 数：`{summary['intent_count']}`",
            f"- ready 数：`{summary['ready_count']}`",
            f"- blocked 数：`{summary['blocked_count']}`",
            f"- send_order 调用次数：`{summary['send_order_api_called_count']}`",
            f"- cancel_order 调用次数：`{summary['cancel_order_api_called_count']}`",
            "",
            "## Intents",
            "",
            _to_markdown(
                intents,
                [
                    "intent_id",
                    "source",
                    "vt_symbol",
                    "direction",
                    "offset",
                    "planned_volume",
                    "limit_price",
                    "price_adjustment_reason",
                    "dedupe_removed_count",
                    "dedupe_removed_sources",
                    "executor_status",
                    "executor_reason",
                ],
            ),
            "",
            "## 说明",
            "",
            "- Stage905 只生成 dry-run `OrderRequest` payload，不连接 CTP，不调用 `send_order` 或 `cancel_order`。",
            "- 平仓必须有 broker 持仓快照和 Stage260 executable gate；影子持仓不能替代真实账户持仓。",
            "- 合约快照、持仓快照、活跃委托、Stage902、Stage260 任一缺失都必须 fail-closed。",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Official-live Phase D executor dry-run.")
    parser.add_argument("--target-date", required=True)
    parser.add_argument("--mode", choices=["dry-run"], default="dry-run")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    paths = _paths(args.target_date)
    pending_orders = _read_csv_maybe(STAGE901_PENDING_ORDERS_PATH)
    stage904_actions = _read_csv_maybe(_stage904_actions_path(args.target_date))
    contracts = _read_csv_maybe(READONLY_CONTRACTS_PATH)
    positions = _read_csv_maybe(READONLY_POSITIONS_PATH)
    orders = _read_csv_maybe(READONLY_ORDERS_PATH)
    stage902_summary = _read_json(_stage902_summary_path(args.target_date))
    stage260_summary = _read_json(_stage260_summary_path(args.target_date))

    raw_intents = _dedupe_close_intents(_pending_order_intents(pending_orders) + _stage904_intents(stage904_actions))
    intents = pd.DataFrame(
        [
            _validate_intent(
                row,
                contracts=contracts,
                positions=positions,
                orders=orders,
                stage902_summary=stage902_summary,
                stage260_summary=stage260_summary,
                mode=args.mode,
            )
            for row in raw_intents
        ]
    )
    ready_count = int(intents.get("executor_status", pd.Series(dtype=str)).astype(str).eq("dry_run_order_request_payload_ready").sum()) if not intents.empty else 0
    blocked_count = int(intents.get("executor_status", pd.Series(dtype=str)).astype(str).eq("blocked").sum()) if not intents.empty else 0
    send_count = int(intents.get("send_order_api_called", pd.Series(dtype=float)).sum()) if not intents.empty else 0
    cancel_count = int(intents.get("cancel_order_api_called", pd.Series(dtype=float)).sum()) if not intents.empty else 0
    executor_status = "executor_dry_run_ready" if ready_count and not blocked_count else "executor_dry_run_blocked"
    if intents.empty:
        executor_status = "executor_no_intents"

    summary = {
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "target_date": args.target_date,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "executor_status": executor_status,
        "intent_count": int(len(intents)),
        "ready_count": ready_count,
        "blocked_count": blocked_count,
        "send_order_api_called_count": send_count,
        "cancel_order_api_called_count": cancel_count,
        "stage902_overall_status": stage902_summary.get("overall_status", ""),
        "stage260_executable_count": stage260_summary.get("executable_count", 0),
        "outputs": {key: str(value.resolve()) for key, value in paths.items()},
        "judgement": {
            "overfit_before": "否。executor dry-run 是执行层，不改信号或策略参数。",
            "continue_before": "是。全自动必须能把信号变成可审计 OrderRequest，并在缺少 broker 证据时阻断。",
            "overfit_after": "否。没有根据 executor 结果调整策略。",
            "continue_after": "是。下一步应把 Stage905 接入 Stage903，并补 broker read-only/Stage260 fresh 自动刷新。",
        },
    }
    intents.to_csv(paths["intents_csv"], index=False, encoding="utf-8-sig")
    paths["summary_json"].write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths["report_md"].write_text(_build_report(summary, intents), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
