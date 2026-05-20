from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
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
MODEL_TAG = "stage285_simnow_open_close_proof_v1"
OUTPUT_PREFIX = "qmt_roll_stage285_simnow_open_close_proof"
READONLY_SUMMARY_PATH = OUTPUT_DIR / "qmt_roll_stage174_ctp_vnpy_readonly_probe_summary_stage174_ctp_vnpy_readonly_probe_v1.json"
CONTRACT_PATH = OUTPUT_DIR / "qmt_roll_stage174_ctp_vnpy_readonly_probe_contracts_stage174_ctp_vnpy_readonly_probe_v1.csv"

CONFIRM_TEXT = "I_UNDERSTAND_THIS_SENDS_CTP_TEST_ORDERS"


def _paths(run_id: str) -> dict[str, Path]:
    return {
        "summary_json": OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{run_id}_{MODEL_TAG}.json",
        "report_md": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{run_id}_{MODEL_TAG}.md",
        "console_txt": OUTPUT_DIR / f"{OUTPUT_PREFIX}_console_{run_id}_{MODEL_TAG}.txt",
        "ticks_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_ticks_{run_id}_{MODEL_TAG}.csv",
        "orders_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_orders_{run_id}_{MODEL_TAG}.csv",
        "trades_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_trades_{run_id}_{MODEL_TAG}.csv",
        "positions_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_positions_{run_id}_{MODEL_TAG}.csv",
        "accounts_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_accounts_{run_id}_{MODEL_TAG}.csv",
        "logs_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_logs_{run_id}_{MODEL_TAG}.csv",
    }


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _env_enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_generated_at(value: str) -> datetime | None:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


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
        "connection_target": summary.get("connection_target", {}),
    }


def _required_env_missing() -> list[str]:
    keys = ["CTP_USERID", "CTP_PASSWORD", "CTP_BROKERID", "CTP_TD_ADDRESS", "CTP_MD_ADDRESS", "CTP_APPID", "CTP_AUTH_CODE"]
    return [key for key in keys if not os.getenv(key, "")]


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


def _split_vt_symbol(vt_symbol: str) -> tuple[str, Exchange | None]:
    if "." not in vt_symbol:
        return vt_symbol, None
    symbol, exchange_value = vt_symbol.rsplit(".", 1)
    try:
        return symbol, Exchange(exchange_value)
    except ValueError:
        return symbol, None


def _read_contract(vt_symbol: str) -> dict[str, Any] | None:
    if not CONTRACT_PATH.exists() or "." not in vt_symbol:
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


def _safe_float(value: Any, default: float = 0.0) -> float:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return default
    return float(number)


def _round_to_tick(price: float, pricetick: float) -> float:
    if pricetick <= 0:
        return price
    return round(round(price / pricetick) * pricetick, 10)


def _tick_age_seconds(tick: dict[str, Any]) -> float | None:
    raw = str(tick.get("datetime", ""))
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc).astimezone()
    return round((datetime.now(dt.tzinfo) - dt).total_seconds(), 3)


def _aggressive_price(tick: dict[str, Any], contract: dict[str, Any], direction: Direction, extra_ticks: int) -> tuple[float, list[str]]:
    pricetick = _safe_float(contract.get("pricetick"), 0.0)
    bid = _safe_float(tick.get("bid_price_1"), 0.0)
    ask = _safe_float(tick.get("ask_price_1"), 0.0)
    last = _safe_float(tick.get("last_price"), 0.0)
    limit_up = _safe_float(tick.get("limit_up"), 0.0)
    limit_down = _safe_float(tick.get("limit_down"), 0.0)
    ticks = max(int(extra_ticks), 1)
    reasons: list[str] = []

    if direction == Direction.LONG:
        anchor = ask if ask > 0 else last
        if ask <= 0:
            reasons.append("open_used_last_price_anchor")
        price = anchor + ticks * pricetick
        if limit_up > 0:
            price = min(price, limit_up)
    else:
        anchor = bid if bid > 0 else last
        if bid <= 0:
            reasons.append("close_used_last_price_anchor")
        price = anchor - ticks * pricetick
        if limit_down > 0:
            price = max(price, limit_down)

    if anchor <= 0 or pricetick <= 0:
        return 0.0, reasons + ["missing_tick_or_pricetick"]
    return _round_to_tick(price, pricetick), reasons


def _status_is_active(status_value: Any) -> bool:
    text = str(status_value)
    return text in {Status.SUBMITTING.value, Status.NOTTRADED.value, Status.PARTTRADED.value, "SUBMITTING", "NOTTRADED", "PARTTRADED"}


def _latest_order_by_vt_orderid(orders: list[dict[str, Any]], vt_orderid: str) -> dict[str, Any] | None:
    if not vt_orderid:
        return None
    gateway, _, orderid = vt_orderid.partition(".")
    matched = [
        row for row in orders
        if str(row.get("gateway_name", "")) == gateway and str(row.get("orderid", "")) == orderid
    ]
    return matched[-1] if matched else None


def _cancel_if_active(main_engine: MainEngine, orders: list[dict[str, Any]], vt_orderid: str, symbol: str, exchange: Exchange) -> bool:
    latest_order = _latest_order_by_vt_orderid(orders, vt_orderid)
    if latest_order and _status_is_active(latest_order.get("status")):
        _, _, orderid = vt_orderid.partition(".")
        main_engine.cancel_order(CancelRequest(orderid=orderid, symbol=symbol, exchange=exchange), "CTP")
        return True
    return False


def _build_report(summary: dict[str, Any], rows: dict[str, list[dict[str, Any]]]) -> str:
    order_lines = [
        f"| {row.get('datetime', '')} | {row.get('vt_orderid', '')} | {row.get('vt_symbol', '')} | {row.get('direction', '')} | {row.get('offset', '')} | {row.get('price', '')} | {row.get('volume', '')} | {row.get('traded', '')} | {row.get('status', '')} |"
        for row in rows["orders"]
    ] or ["| _empty_ | | | | | | | | |"]
    trade_lines = [
        f"| {row.get('datetime', '')} | {row.get('vt_symbol', '')} | {row.get('direction', '')} | {row.get('offset', '')} | {row.get('price', '')} | {row.get('volume', '')} | {row.get('tradeid', '')} | {row.get('orderid', '')} |"
        for row in rows["trades"]
    ] or ["| _empty_ | | | | | | | |"]
    return "\n".join(
        [
            "# Stage285 SimNow Open/Close Proof",
            "",
            f"- 状态：`{summary['status']}`",
            f"- 合约：`{summary['vt_symbol']}`",
            f"- 前置：`{summary['front_profile']}`",
            f"- 只读快照闸门：`{summary['readonly_gate'].get('passed')}`",
            f"- send_order 调用次数：`{summary['send_order_api_called_count']}`",
            f"- cancel_order 调用次数：`{summary['cancel_order_api_called_count']}`",
            f"- 开仓委托：`{summary['open_order'].get('vt_orderid', '')}`，成交：`{summary['open_order'].get('filled_volume', 0)}`",
            f"- 平仓委托：`{summary['close_order'].get('vt_orderid', '')}`，成交：`{summary['close_order'].get('filled_volume', 0)}`",
            "",
            "## 委托回报",
            "",
            "| datetime | vt_orderid | vt_symbol | direction | offset | price | volume | traded | status |",
            "|:--|:--|:--|:--|:--|--:|--:|--:|:--|",
            *order_lines,
            "",
            "## 成交回报",
            "",
            "| datetime | vt_symbol | direction | offset | price | volume | tradeid | orderid |",
            "|:--|:--|:--|:--|--:|--:|:--|:--|",
            *trade_lines,
            "",
            "## 说明",
            "",
            "- 本脚本仅用于 CTP/SimNow/券商测试环境 1 手开平仓链路证明。",
            "- 需要 `CTP_SMOKE_ORDER_ENABLED=1` 和确认文本，默认不会发单。",
            "- 本脚本不用于策略正常手数，也不用于真实资金账户。",
            "",
        ]
    )


class ConsoleRecorder:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def log(self, message: str) -> None:
        line = f"{_now()} | {message}"
        self.lines.append(line)
        print(line, flush=True)


def run(args: argparse.Namespace) -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    paths = _paths(run_id)
    recorder = ConsoleRecorder()

    vt_symbol = args.vt_symbol.strip()
    symbol, exchange = _split_vt_symbol(vt_symbol)
    contract = _read_contract(vt_symbol)
    missing_env = _required_env_missing()
    readonly_gate = _readonly_gate(args.max_snapshot_age_seconds)
    submit_enabled = _env_enabled("CTP_SMOKE_ORDER_ENABLED") or _env_enabled("SIMNOW_SMOKE_ORDER_ENABLED")
    confirm_ok = args.confirm_submit == CONFIRM_TEXT

    rows: dict[str, list[dict[str, Any]]] = {
        "ticks": [],
        "orders": [],
        "trades": [],
        "positions": [],
        "accounts": [],
        "logs": [],
    }
    summary: dict[str, Any] = {
        "model_tag": MODEL_TAG,
        "generated_at": _now(),
        "mode": args.mode,
        "front_profile": os.getenv("SIMNOW_FRONT", ""),
        "vt_symbol": vt_symbol,
        "status": "initialized",
        "failure_reason": "",
        "readonly_gate": readonly_gate,
        "missing_required_env": missing_env,
        "contract_found": bool(contract),
        "submit_enabled_env": submit_enabled,
        "confirm_submit_ok": confirm_ok,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "open_order": {},
        "close_order": {},
        "outputs": {key: str(value.resolve()) for key, value in paths.items()},
        "judgement": {
            "overfit_before": "否。1手开平仓证明只验证执行链路，不修改策略参数。",
            "continue_before": "是。券商需要开仓和平仓成交证据，最小手数测试有明确工程价值。",
        },
    }

    recorder.log("Stage285 open-close proof starting")
    recorder.log(f"mode={args.mode} front={summary['front_profile']} vt_symbol={vt_symbol} volume={args.volume}")
    recorder.log(f"readonly_gate_passed={readonly_gate.get('passed')} status={readonly_gate.get('status')} position_state={readonly_gate.get('position_snapshot_state')}")
    recorder.log(f"CTP_USERID=set(len={len(os.getenv('CTP_USERID', ''))}) CTP_PASSWORD=set(len={len(os.getenv('CTP_PASSWORD', ''))})")
    recorder.log(f"CTP_BROKERID={os.getenv('CTP_BROKERID', '')} TD={os.getenv('CTP_TD_ADDRESS', '')} MD={os.getenv('CTP_MD_ADDRESS', '')}")

    def finish(status: str, reason: str = "") -> dict[str, Any]:
        summary["status"] = status
        summary["failure_reason"] = reason
        summary["row_counts"] = {key: len(value) for key, value in rows.items()}
        summary["judgement"]["overfit_after"] = "否。本阶段只做测试环境最小开平仓链路验证，不影响策略收益。"
        summary["judgement"]["continue_after"] = "是。若成功，可把原始控制台与CSV发给券商确认；若失败，失败原因可直接定位执行通道。"
        paths["console_txt"].write_text("\n".join(recorder.lines) + "\n", encoding="utf-8")
        return summary | {"rows": rows}

    if missing_env:
        return finish("blocked_missing_env", ",".join(missing_env))
    if exchange is None:
        return finish("blocked_invalid_vt_symbol", "invalid_vt_symbol")
    if not contract:
        return finish("blocked_contract_not_found", "contract_not_found")
    if args.volume != 1:
        return finish("blocked_volume_must_be_one", "volume_must_be_one")
    if args.mode == "submit-open-close":
        if not readonly_gate["passed"]:
            return finish("blocked_readonly_gate_not_passed", "readonly_gate_not_passed")
        if not submit_enabled:
            return finish("blocked_submit_env_disabled", "CTP_SMOKE_ORDER_ENABLED_not_enabled")
        if not confirm_ok:
            return finish("blocked_confirmation_missing", "confirm_submit_text_missing")

    from vnpy_ctp import CtpGateway

    event_engine = EventEngine()
    main_engine = MainEngine(event_engine)
    main_engine.add_gateway(CtpGateway)

    def on_tick(event: Any) -> None:
        row = _object_to_row(event.data)
        if row.get("vt_symbol") == vt_symbol:
            rows["ticks"].append(row)
            if len(rows["ticks"]) <= 3:
                recorder.log(
                    "EVENT_TICK "
                    f"vt_symbol={row.get('vt_symbol')} datetime={row.get('datetime')} "
                    f"last={row.get('last_price')} bid1={row.get('bid_price_1')} ask1={row.get('ask_price_1')}"
                )

    def on_order(event: Any) -> None:
        row = _object_to_row(event.data)
        rows["orders"].append(row)
        recorder.log(
            "EVENT_ORDER "
            f"vt_orderid={row.get('vt_orderid')} vt_symbol={row.get('vt_symbol')} "
            f"direction={row.get('direction')} offset={row.get('offset')} "
            f"price={row.get('price')} volume={row.get('volume')} traded={row.get('traded')} status={row.get('status')}"
        )

    def on_trade(event: Any) -> None:
        row = _object_to_row(event.data)
        rows["trades"].append(row)
        recorder.log(
            "EVENT_TRADE "
            f"tradeid={row.get('tradeid')} orderid={row.get('orderid')} vt_symbol={row.get('vt_symbol')} "
            f"direction={row.get('direction')} offset={row.get('offset')} price={row.get('price')} volume={row.get('volume')}"
        )

    def on_position(event: Any) -> None:
        row = _object_to_row(event.data)
        rows["positions"].append(row)
        recorder.log(
            "EVENT_POSITION "
            f"vt_symbol={row.get('vt_symbol')} direction={row.get('direction')} volume={row.get('volume')} yd_volume={row.get('yd_volume')}"
        )

    def on_account(event: Any) -> None:
        row = _object_to_row(event.data)
        rows["accounts"].append(row)
        if len(rows["accounts"]) <= 3:
            recorder.log(
                "EVENT_ACCOUNT "
                f"accountid={row.get('accountid')} balance={row.get('balance')} available={row.get('available')}"
            )

    def on_log(event: Any) -> None:
        row = _object_to_row(event.data)
        rows["logs"].append(row)
        recorder.log(f"EVENT_LOG {row.get('msg', row)}")

    event_engine.register(EVENT_TICK, on_tick)
    event_engine.register(EVENT_ORDER, on_order)
    event_engine.register(EVENT_TRADE, on_trade)
    event_engine.register(EVENT_POSITION, on_position)
    event_engine.register(EVENT_ACCOUNT, on_account)
    event_engine.register(EVENT_LOG, on_log)

    def wait_for_tick() -> dict[str, Any] | None:
        deadline = time.time() + args.tick_wait_seconds
        while time.time() < deadline:
            if rows["ticks"]:
                tick = rows["ticks"][-1]
                age = _tick_age_seconds(tick)
                if age is None or age <= args.max_tick_age_seconds:
                    return tick
            time.sleep(0.2)
        return rows["ticks"][-1] if rows["ticks"] else None

    def wait_for_fill(start_trade_count: int, direction: Direction, offset: Offset) -> float:
        deadline = time.time() + args.fill_wait_seconds
        filled = 0.0
        while time.time() < deadline:
            recent = rows["trades"][start_trade_count:]
            filled = sum(
                _safe_float(row.get("volume"), 0.0)
                for row in recent
                if row.get("vt_symbol") == vt_symbol
                and str(row.get("direction")) == direction.value
                and str(row.get("offset")) == offset.value
            )
            if filled >= args.volume:
                return filled
            time.sleep(0.2)
        return filled

    try:
        recorder.log("CONNECT begin")
        main_engine.connect(_ctp_setting_from_env(), "CTP")
        time.sleep(max(args.connect_wait_seconds, 1))
        recorder.log("SUBSCRIBE begin")
        main_engine.subscribe(SubscribeRequest(symbol=symbol, exchange=exchange), "CTP")
        tick = wait_for_tick()
        if not tick:
            return finish("blocked_no_tick", "no_tick_after_subscribe")
        tick_age = _tick_age_seconds(tick)
        summary["latest_tick"] = tick
        summary["latest_tick_age_seconds"] = tick_age
        if tick_age is not None and tick_age > args.max_tick_age_seconds:
            return finish("blocked_stale_tick", f"tick_age_seconds={tick_age}")

        open_price, open_reasons = _aggressive_price(tick, contract, Direction.LONG, args.aggressive_ticks)
        if open_price <= 0:
            return finish("blocked_invalid_open_price", ";".join(open_reasons))
        open_req = OrderRequest(
            symbol=symbol,
            exchange=exchange,
            direction=Direction.LONG,
            type=OrderType.LIMIT,
            volume=args.volume,
            price=open_price,
            offset=Offset.OPEN,
            reference=f"Stage285Open:{run_id}",
        )
        summary["open_order"] = {
            "request": _object_to_row(open_req),
            "price_reasons": open_reasons,
        }

        if args.mode == "dry-run":
            recorder.log(f"DRY_RUN open_request price={open_price} no send_order")
            return finish("dry_run_request_ready")

        start_trades = len(rows["trades"])
        recorder.log(f"SEND_OPEN OrderRequest={summary['open_order']['request']}")
        vt_orderid = main_engine.send_order(open_req, "CTP")
        summary["send_order_api_called_count"] += 1
        summary["open_order"]["vt_orderid"] = vt_orderid
        recorder.log(f"SEND_OPEN_RETURN vt_orderid={vt_orderid}")
        if not vt_orderid:
            return finish("submit_failed_open_no_vt_orderid", "open_send_order_returned_empty")
        open_filled = wait_for_fill(start_trades, Direction.LONG, Offset.OPEN)
        summary["open_order"]["filled_volume"] = open_filled
        if open_filled < args.volume:
            if _cancel_if_active(main_engine, rows["orders"], vt_orderid, symbol, exchange):
                summary["cancel_order_api_called_count"] += 1
                time.sleep(args.post_cancel_wait_seconds)
            return finish("open_not_filled", f"open_filled={open_filled}")

        tick = wait_for_tick() or tick
        close_price, close_reasons = _aggressive_price(tick, contract, Direction.SHORT, args.aggressive_ticks)
        if close_price <= 0:
            return finish("blocked_invalid_close_price", ";".join(close_reasons))
        close_req = OrderRequest(
            symbol=symbol,
            exchange=exchange,
            direction=Direction.SHORT,
            type=OrderType.LIMIT,
            volume=args.volume,
            price=close_price,
            offset=Offset.CLOSE,
            reference=f"Stage285Close:{run_id}",
        )
        summary["close_order"] = {
            "request": _object_to_row(close_req),
            "price_reasons": close_reasons,
        }

        start_trades = len(rows["trades"])
        recorder.log(f"SEND_CLOSE OrderRequest={summary['close_order']['request']}")
        close_vt_orderid = main_engine.send_order(close_req, "CTP")
        summary["send_order_api_called_count"] += 1
        summary["close_order"]["vt_orderid"] = close_vt_orderid
        recorder.log(f"SEND_CLOSE_RETURN vt_orderid={close_vt_orderid}")
        if not close_vt_orderid:
            return finish("submit_failed_close_no_vt_orderid", "close_send_order_returned_empty")
        close_filled = wait_for_fill(start_trades, Direction.SHORT, Offset.CLOSE)
        summary["close_order"]["filled_volume"] = close_filled
        if close_filled < args.volume:
            if _cancel_if_active(main_engine, rows["orders"], close_vt_orderid, symbol, exchange):
                summary["cancel_order_api_called_count"] += 1
                time.sleep(args.post_cancel_wait_seconds)
            return finish("close_not_filled", f"close_filled={close_filled}")

        time.sleep(args.final_wait_seconds)
        return finish("open_close_all_traded")
    except Exception as exc:
        return finish("exception", repr(exc))
    finally:
        main_engine.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage285 SimNow/test CTP one-lot open-close proof.")
    parser.add_argument("--mode", choices=["dry-run", "submit-open-close"], default="dry-run")
    parser.add_argument("--vt-symbol", default="MA609.CZCE")
    parser.add_argument("--volume", type=int, default=1)
    parser.add_argument("--connect-wait-seconds", type=int, default=8)
    parser.add_argument("--tick-wait-seconds", type=int, default=30)
    parser.add_argument("--fill-wait-seconds", type=int, default=20)
    parser.add_argument("--final-wait-seconds", type=int, default=3)
    parser.add_argument("--post-cancel-wait-seconds", type=int, default=5)
    parser.add_argument("--aggressive-ticks", type=int, default=3)
    parser.add_argument("--max-snapshot-age-seconds", type=int, default=300)
    parser.add_argument("--max-tick-age-seconds", type=int, default=20)
    parser.add_argument("--confirm-submit", default="")
    args = parser.parse_args()

    result = run(args)
    rows = result.pop("rows")
    paths = {key: Path(value) for key, value in result["outputs"].items()}

    _write_df(paths["ticks_csv"], rows["ticks"])
    _write_df(paths["orders_csv"], rows["orders"])
    _write_df(paths["trades_csv"], rows["trades"])
    _write_df(paths["positions_csv"], rows["positions"])
    _write_df(paths["accounts_csv"], rows["accounts"])
    _write_df(paths["logs_csv"], rows["logs"])
    paths["summary_json"].write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths["report_md"].write_text(_build_report(result, rows), encoding="utf-8")

    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
