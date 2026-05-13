from __future__ import annotations

import argparse
import json
import math
import os
import time
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from vnpy.event import EventEngine
from vnpy.trader.constant import Direction, Exchange, Offset, OrderType, Status
from vnpy.trader.engine import MainEngine
from vnpy.trader.event import EVENT_ACCOUNT, EVENT_LOG, EVENT_ORDER, EVENT_POSITION, EVENT_TICK, EVENT_TRADE
from vnpy.trader.object import CancelRequest, OrderRequest, SubscribeRequest


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
MODEL_TAG = "stage258_simnow_smoke_order_v1"
OUTPUT_PREFIX = "qmt_roll_stage258_simnow_smoke_order"
READONLY_SUMMARY_PATH = OUTPUT_DIR / "qmt_roll_stage174_ctp_vnpy_readonly_probe_summary_stage174_ctp_vnpy_readonly_probe_v1.json"
CONTRACT_PATH = OUTPUT_DIR / "qmt_roll_stage174_ctp_vnpy_readonly_probe_contracts_stage174_ctp_vnpy_readonly_probe_v1.csv"

CONFIRM_TEXT = "I_UNDERSTAND_THIS_SENDS_SIMNOW_VIRTUAL_ORDERS"


def _paths(run_id: str) -> dict[str, Path]:
    return {
        "summary_json": OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{run_id}_{MODEL_TAG}.json",
        "report_md": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{run_id}_{MODEL_TAG}.md",
        "ticks_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_ticks_{run_id}_{MODEL_TAG}.csv",
        "orders_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_orders_{run_id}_{MODEL_TAG}.csv",
        "trades_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_trades_{run_id}_{MODEL_TAG}.csv",
        "positions_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_positions_{run_id}_{MODEL_TAG}.csv",
        "accounts_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_accounts_{run_id}_{MODEL_TAG}.csv",
        "logs_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_logs_{run_id}_{MODEL_TAG}.csv",
        "position_callbacks_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_position_callbacks_{run_id}_{MODEL_TAG}.csv",
    }


def _env_enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _parse_generated_at(value: str) -> datetime | None:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _read_contract(vt_symbol: str) -> dict[str, Any] | None:
    if not CONTRACT_PATH.exists():
        return None
    if "." not in vt_symbol:
        return None
    symbol, exchange = vt_symbol.rsplit(".", 1)
    contracts = pd.read_csv(CONTRACT_PATH, encoding="utf-8-sig")
    rows = contracts[
        contracts["symbol"].astype(str).eq(symbol)
        & contracts["exchange"].astype(str).eq(exchange)
        & contracts["product"].astype(str).eq("Futures")
    ]
    if rows.empty:
        return None
    return rows.iloc[0].to_dict()


def _object_to_row(obj: Any) -> dict[str, Any]:
    if obj is None:
        return {}
    if is_dataclass(obj):
        row = asdict(obj)
    elif hasattr(obj, "__dict__"):
        row = dict(obj.__dict__)
    else:
        row = {"value": str(obj)}
    for attr in ["vt_symbol", "vt_orderid", "vt_accountid"]:
        if hasattr(obj, attr):
            row[attr] = getattr(obj, attr)
    for key, value in list(row.items()):
        if isinstance(value, (datetime, pd.Timestamp)):
            row[key] = value.isoformat()
        elif hasattr(value, "value"):
            row[key] = value.value
        elif isinstance(value, (dict, list, tuple, set)):
            row[key] = json.dumps(value, ensure_ascii=False, default=str)
        elif value is None:
            row[key] = ""
    return row


def _write_df(path: Path, rows: list[dict[str, Any]]) -> None:
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")


def _split_vt_symbol(vt_symbol: str) -> tuple[str, Exchange | None]:
    if "." not in vt_symbol:
        return vt_symbol, None
    symbol, exchange_value = vt_symbol.rsplit(".", 1)
    try:
        return symbol, Exchange(exchange_value)
    except ValueError:
        return symbol, None


def _round_to_tick(price: float, pricetick: float) -> float:
    if pricetick <= 0:
        return price
    return round(round(price / pricetick) * pricetick, 10)


def _safe_float(value: Any, default: float = 0.0) -> float:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return default
    return float(number)


def _choose_price(tick: dict[str, Any], contract: dict[str, Any], direction: Direction, ticks_away: int, manual_price: float | None) -> tuple[float, list[str]]:
    reasons: list[str] = []
    pricetick = _safe_float(contract.get("pricetick"), 0.0)
    if manual_price is not None and manual_price > 0:
        return _round_to_tick(float(manual_price), pricetick), reasons

    bid = _safe_float(tick.get("bid_price_1"), 0.0)
    ask = _safe_float(tick.get("ask_price_1"), 0.0)
    last = _safe_float(tick.get("last_price"), 0.0)
    limit_up = _safe_float(tick.get("limit_up"), 0.0)
    limit_down = _safe_float(tick.get("limit_down"), 0.0)
    anchor = bid if direction == Direction.LONG else ask
    if anchor <= 0:
        anchor = last
        reasons.append("used_last_price_anchor")
    if anchor <= 0 or pricetick <= 0:
        return 0.0, reasons + ["missing_tick_or_pricetick"]

    ticks = max(int(ticks_away), 1)
    if direction == Direction.LONG:
        price = anchor - ticks * pricetick
        if limit_down > 0:
            price = max(price, limit_down)
    else:
        price = anchor + ticks * pricetick
        if limit_up > 0:
            price = min(price, limit_up)
    return _round_to_tick(price, pricetick), reasons


def _latest_active_order(orders: list[dict[str, Any]], vt_orderid: str) -> dict[str, Any] | None:
    if not vt_orderid:
        return None
    gateway, _, orderid = vt_orderid.partition(".")
    matched = [
        row for row in orders
        if str(row.get("gateway_name", "")) == gateway and str(row.get("orderid", "")) == orderid
    ]
    return matched[-1] if matched else None


def _status_is_active(status_value: Any) -> bool:
    text = str(status_value)
    return text in {Status.SUBMITTING.value, Status.NOTTRADED.value, Status.PARTTRADED.value, "SUBMITTING", "NOTTRADED", "PARTTRADED"}


def _ctp_setting_from_env() -> dict[str, Any]:
    return {
        "用户名": os.getenv("CTP_USERID", ""),
        "密码": os.getenv("CTP_PASSWORD", ""),
        "经纪商代码": os.getenv("CTP_BROKERID", ""),
        "交易服务器": os.getenv("CTP_TD_ADDRESS", ""),
        "行情服务器": os.getenv("CTP_MD_ADDRESS", ""),
        "产品名称": os.getenv("CTP_APPID", ""),
        "授权编码": os.getenv("CTP_AUTH_CODE", ""),
        "产品信息": os.getenv("CTP_PRODUCT_INFO", ""),
    }


def _required_env_missing() -> list[str]:
    keys = ["CTP_USERID", "CTP_PASSWORD", "CTP_BROKERID", "CTP_TD_ADDRESS", "CTP_MD_ADDRESS", "CTP_APPID", "CTP_AUTH_CODE"]
    return [key for key in keys if not os.getenv(key, "")]


def _readonly_gate(max_age_seconds: int) -> dict[str, Any]:
    summary = _read_json(READONLY_SUMMARY_PATH)
    generated_at = str(summary.get("generated_at", ""))
    generated_dt = _parse_generated_at(generated_at)
    age_seconds = None
    if generated_dt:
        age_seconds = round((datetime.now() - generated_dt).total_seconds(), 3)
    broker_snapshot = summary.get("broker_snapshot", {})
    position_state = str(broker_snapshot.get("position_snapshot_state", ""))
    return {
        "summary_path": str(READONLY_SUMMARY_PATH),
        "status": summary.get("status", ""),
        "position_snapshot_state": position_state,
        "generated_at": generated_at,
        "age_seconds": age_seconds,
        "fresh": age_seconds is not None and age_seconds <= max_age_seconds,
        "passed": (
            summary.get("status") == "readonly_snapshots_received"
            and position_state in {"confirmed_flat", "positions_received"}
            and age_seconds is not None
            and age_seconds <= max_age_seconds
        ),
    }


def _build_report(summary: dict[str, Any], rows: dict[str, list[dict[str, Any]]]) -> str:
    order_lines = [
        f"| {row.get('datetime', '')} | {row.get('vt_symbol', '')} | {row.get('direction', '')} | {row.get('offset', '')} | {row.get('price', '')} | {row.get('volume', '')} | {row.get('traded', '')} | {row.get('status', '')} |"
        for row in rows["orders"][-20:]
    ] or ["| _empty_ | | | | | | | |"]
    trade_lines = [
        f"| {row.get('datetime', '')} | {row.get('vt_symbol', '')} | {row.get('direction', '')} | {row.get('offset', '')} | {row.get('price', '')} | {row.get('volume', '')} |"
        for row in rows["trades"][-20:]
    ] or ["| _empty_ | | | | | | |"]
    return "\n".join(
        [
            "# Stage258 SimNow Smoke Order",
            "",
            f"- 运行模式：`{summary['mode']}`",
            f"- 合约：`{summary['vt_symbol']}`",
            f"- 前置：`{summary['simnow_front']}`",
            f"- 状态：`{summary['status']}`",
            f"- 发送委托API次数：`{summary['send_order_api_called_count']}`",
            f"- 撤单API次数：`{summary['cancel_order_api_called_count']}`",
            f"- vt_orderid：`{summary['vt_orderid']}`",
            f"- 请求价格：`{summary['order_request'].get('price', '')}`",
            f"- 只读快照闸门：`{summary['readonly_gate'].get('passed')}`",
            "",
            "## 委托回报",
            "",
            "| datetime | vt_symbol | direction | offset | price | volume | traded | status |",
            "|:--|:--|:--|:--|--:|--:|--:|:--|",
            *order_lines,
            "",
            "## 成交回报",
            "",
            "| datetime | vt_symbol | direction | offset | price | volume |",
            "|:--|:--|:--|:--|--:|--:|",
            *trade_lines,
            "",
            "## 说明",
            "",
            "- `dry-run` 模式连接、订阅并构造请求，但不调用 `send_order`。",
            "- `submit-cancel` 模式只用于 SimNow 虚拟盘，需要环境变量和命令行确认双开关。",
            "- 本脚本不用于真实资金账户。",
            "",
        ]
    )


def run(args: argparse.Namespace) -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    paths = _paths(run_id)

    vt_symbol = args.vt_symbol.strip()
    symbol, exchange = _split_vt_symbol(vt_symbol)
    contract = _read_contract(vt_symbol)
    missing_env = _required_env_missing()
    readonly_gate = _readonly_gate(args.max_snapshot_age_seconds)
    submit_enabled = _env_enabled("SIMNOW_SMOKE_ORDER_ENABLED")
    confirm_ok = args.confirm_submit == CONFIRM_TEXT

    rows: dict[str, list[dict[str, Any]]] = {
        "ticks": [],
        "orders": [],
        "trades": [],
        "positions": [],
        "accounts": [],
        "logs": [],
        "position_callbacks": [],
    }
    summary: dict[str, Any] = {
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mode": args.mode,
        "vt_symbol": vt_symbol,
        "simnow_front": os.getenv("SIMNOW_FRONT", ""),
        "status": "initialized",
        "failure_reason": "",
        "readonly_gate": readonly_gate,
        "missing_required_env": missing_env,
        "contract_found": bool(contract),
        "contract": contract or {},
        "submit_enabled_env": submit_enabled,
        "confirm_submit_ok": confirm_ok,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "vt_orderid": "",
        "order_request": {},
        "outputs": {key: str(value.resolve()) for key, value in paths.items()},
        "judgement": {
            "overfit_before": "否。1手链路测试只验证执行通道，不修改策略参数。",
            "continue_before": "是。SimNow通路已恢复，下一关是最小报单/撤单链路。",
        },
    }

    if missing_env:
        summary["status"] = "blocked_missing_env"
        summary["failure_reason"] = ",".join(missing_env)
        return summary | {"rows": rows}
    if exchange is None:
        summary["status"] = "blocked_invalid_vt_symbol"
        summary["failure_reason"] = "invalid_vt_symbol"
        return summary | {"rows": rows}
    if not contract:
        summary["status"] = "blocked_contract_not_found"
        summary["failure_reason"] = "contract_not_found"
        return summary | {"rows": rows}
    if args.mode == "submit-cancel":
        if not readonly_gate["passed"]:
            summary["status"] = "blocked_readonly_gate_not_passed"
            summary["failure_reason"] = "readonly_gate_not_passed"
            return summary | {"rows": rows}
        if not submit_enabled:
            summary["status"] = "blocked_submit_env_disabled"
            summary["failure_reason"] = "SIMNOW_SMOKE_ORDER_ENABLED_not_enabled"
            return summary | {"rows": rows}
        if not confirm_ok:
            summary["status"] = "blocked_confirmation_missing"
            summary["failure_reason"] = "confirm_submit_text_missing"
            return summary | {"rows": rows}

    from vnpy_ctp import CtpGateway
    from vnpy_ctp.gateway import ctp_gateway as ctp_gateway_module

    original_position_rsp = ctp_gateway_module.CtpTdApi.onRspQryInvestorPosition

    def instrumented_position_rsp(self: Any, data: dict, error: dict, reqid: int, last: bool) -> None:
        rows["position_callbacks"].append(
            {
                "reqid": reqid,
                "last": bool(last),
                "has_data": bool(data),
                "instrument": str(data.get("InstrumentID", "")) if isinstance(data, dict) else "",
                "position": data.get("Position", "") if isinstance(data, dict) else "",
                "error_id": error.get("ErrorID", 0) if isinstance(error, dict) else 0,
                "error_msg": error.get("ErrorMsg", "") if isinstance(error, dict) else "",
                "received_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
        return original_position_rsp(self, data, error, reqid, last)

    ctp_gateway_module.CtpTdApi.onRspQryInvestorPosition = instrumented_position_rsp
    event_engine = EventEngine()
    main_engine = MainEngine(event_engine)
    main_engine.add_gateway(CtpGateway)

    def on_tick(event: Any) -> None:
        row = _object_to_row(event.data)
        if row.get("vt_symbol") == vt_symbol:
            rows["ticks"].append(row)

    def on_order(event: Any) -> None:
        rows["orders"].append(_object_to_row(event.data))

    def on_trade(event: Any) -> None:
        rows["trades"].append(_object_to_row(event.data))

    def on_position(event: Any) -> None:
        rows["positions"].append(_object_to_row(event.data))

    def on_account(event: Any) -> None:
        rows["accounts"].append(_object_to_row(event.data))

    def on_log(event: Any) -> None:
        rows["logs"].append(_object_to_row(event.data))

    event_engine.register(EVENT_TICK, on_tick)
    event_engine.register(EVENT_ORDER, on_order)
    event_engine.register(EVENT_TRADE, on_trade)
    event_engine.register(EVENT_POSITION, on_position)
    event_engine.register(EVENT_ACCOUNT, on_account)
    event_engine.register(EVENT_LOG, on_log)

    try:
        main_engine.connect(_ctp_setting_from_env(), "CTP")
        time.sleep(max(args.connect_wait_seconds, 1))
        main_engine.subscribe(SubscribeRequest(symbol=symbol, exchange=exchange), "CTP")

        started = time.time()
        while time.time() - started < args.tick_wait_seconds:
            if rows["ticks"]:
                break
            time.sleep(0.5)
        if not rows["ticks"]:
            summary["status"] = "blocked_no_tick"
            summary["failure_reason"] = "no_tick_after_subscribe"
            return summary | {"rows": rows}

        direction = Direction.LONG if args.direction == "long" else Direction.SHORT
        offset = Offset.OPEN
        latest_tick = rows["ticks"][-1]
        price, price_reasons = _choose_price(
            latest_tick,
            contract,
            direction,
            ticks_away=args.passive_ticks_away,
            manual_price=args.manual_price,
        )
        if price <= 0:
            summary["status"] = "blocked_invalid_price"
            summary["failure_reason"] = ";".join(price_reasons or ["invalid_price"])
            return summary | {"rows": rows}

        volume = int(args.volume)
        req = OrderRequest(
            symbol=symbol,
            exchange=exchange,
            direction=direction,
            type=OrderType.LIMIT,
            volume=volume,
            price=price,
            offset=offset,
            reference=f"Stage258Smoke:{run_id}",
        )
        summary["order_request"] = {
            "symbol": req.symbol,
            "exchange": req.exchange.value,
            "direction": req.direction.value,
            "type": req.type.value,
            "volume": req.volume,
            "price": req.price,
            "offset": req.offset.value,
            "reference": req.reference,
            "vt_symbol": req.vt_symbol,
            "price_reasons": price_reasons,
            "latest_tick": latest_tick,
        }

        if args.mode == "dry-run":
            summary["status"] = "dry_run_request_ready"
            return summary | {"rows": rows}

        vt_orderid = main_engine.send_order(req, "CTP")
        summary["send_order_api_called_count"] = 1
        summary["vt_orderid"] = vt_orderid
        if not vt_orderid:
            summary["status"] = "submit_failed_no_vt_orderid"
            summary["failure_reason"] = "send_order_returned_empty"
            return summary | {"rows": rows}

        time.sleep(max(args.cancel_after_seconds, 1))
        latest_order = _latest_active_order(rows["orders"], vt_orderid)
        if latest_order and _status_is_active(latest_order.get("status")):
            _, _, orderid = vt_orderid.partition(".")
            cancel_req = CancelRequest(orderid=orderid, symbol=symbol, exchange=exchange)
            main_engine.cancel_order(cancel_req, "CTP")
            summary["cancel_order_api_called_count"] = 1
            time.sleep(max(args.post_cancel_wait_seconds, 1))
            summary["status"] = "submit_cancel_attempted"
        else:
            summary["status"] = "submit_seen_non_active_before_cancel"
            summary["failure_reason"] = "order_not_active_before_cancel"

        return summary | {"rows": rows}
    except Exception as exc:
        summary["status"] = "exception"
        summary["failure_reason"] = repr(exc)
        return summary | {"rows": rows}
    finally:
        main_engine.close()
        ctp_gateway_module.CtpTdApi.onRspQryInvestorPosition = original_position_rsp


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage258 SimNow-only 1-lot smoke order test.")
    parser.add_argument("--mode", choices=["dry-run", "submit-cancel"], default="dry-run")
    parser.add_argument("--vt-symbol", default="MA609.CZCE")
    parser.add_argument("--direction", choices=["long", "short"], default="long")
    parser.add_argument("--volume", type=int, default=1)
    parser.add_argument("--passive-ticks-away", type=int, default=20)
    parser.add_argument("--manual-price", type=float)
    parser.add_argument("--connect-wait-seconds", type=int, default=20)
    parser.add_argument("--tick-wait-seconds", type=int, default=30)
    parser.add_argument("--cancel-after-seconds", type=int, default=8)
    parser.add_argument("--post-cancel-wait-seconds", type=int, default=15)
    parser.add_argument("--max-snapshot-age-seconds", type=int, default=300)
    parser.add_argument("--confirm-submit", default="")
    args = parser.parse_args()

    result = run(args)
    rows = result.pop("rows")
    paths = {key: Path(value) for key, value in result["outputs"].items()}

    result["row_counts"] = {key: len(value) for key, value in rows.items()}
    result["judgement"]["overfit_after"] = "否。本阶段最多验证SimNow委托链路，不影响策略收益。"
    result["judgement"]["continue_after"] = "是。dry-run通过后，才值得在显式确认下做1手submit-cancel。"

    _write_df(paths["ticks_csv"], rows["ticks"])
    _write_df(paths["orders_csv"], rows["orders"])
    _write_df(paths["trades_csv"], rows["trades"])
    _write_df(paths["positions_csv"], rows["positions"])
    _write_df(paths["accounts_csv"], rows["accounts"])
    _write_df(paths["logs_csv"], rows["logs"])
    _write_df(paths["position_callbacks_csv"], rows["position_callbacks"])
    paths["summary_json"].write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths["report_md"].write_text(_build_report(result, rows), encoding="utf-8")

    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
