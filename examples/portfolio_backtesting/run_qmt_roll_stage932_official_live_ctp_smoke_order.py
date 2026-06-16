from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION
from qmt_roll_official_live_email_notify import send_official_live_email_notification
from qmt_roll_official_live_phase_d_config import PHASE_D_CONFIRM_TEXT, PHASE_D_REAL_ENABLED_ENV
from run_qmt_alignment_backtest import OUTPUT_DIR
from vnpy.event import EventEngine
from vnpy.trader.constant import Direction, Exchange, Offset, OrderType, Status
from vnpy.trader.engine import MainEngine
from vnpy.trader.event import EVENT_ACCOUNT, EVENT_LOG, EVENT_ORDER, EVENT_POSITION, EVENT_TICK, EVENT_TRADE
from vnpy.trader.object import CancelRequest, OrderRequest, SubscribeRequest


MODEL_TAG = "stage932_official_live_ctp_smoke_order_v1"
OUTPUT_PREFIX = "qmt_roll_stage932_official_live_ctp_smoke_order"
STAGE927_MODEL_TAG = "stage927_official_live_real_submit_arming_gate_v1"
STAGE927_PREFIX = "qmt_roll_stage927_official_live_real_submit_arming_gate"
READONLY_SUMMARY_PATH = OUTPUT_DIR / "qmt_roll_stage174_ctp_vnpy_readonly_probe_summary_stage174_ctp_vnpy_readonly_probe_v1.json"
CONTRACT_PATH = OUTPUT_DIR / "qmt_roll_stage174_ctp_vnpy_readonly_probe_contracts_stage174_ctp_vnpy_readonly_probe_v1.csv"
SMOKE_ENV = "OFFICIAL_LIVE_PHASE_D_REAL_SMOKE_ENABLED"
SMOKE_CONFIRM_TEXT = "I_UNDERSTAND_THIS_SENDS_CTP_LIVE_SMOKE_ORDERS"
CTP_ENV_KEYS = ("CTP_USERID", "CTP_PASSWORD", "CTP_BROKERID", "CTP_TD_ADDRESS", "CTP_MD_ADDRESS", "CTP_APPID", "CTP_AUTH_CODE")


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
        "raw_orders_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_raw_orders_{run_id}_{MODEL_TAG}.csv",
        "order_insert_errors_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_order_insert_errors_{run_id}_{MODEL_TAG}.csv",
        "order_action_errors_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_order_action_errors_{run_id}_{MODEL_TAG}.csv",
        "callback_capture_errors_csv": OUTPUT_DIR
        / f"{OUTPUT_PREFIX}_callback_capture_errors_{run_id}_{MODEL_TAG}.csv",
    }


def _stage927_summary_path(target_date: str) -> Path:
    return OUTPUT_DIR / f"{STAGE927_PREFIX}_summary_{target_date.replace('-', '')}_{STAGE927_MODEL_TAG}.json"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_read_error": repr(exc)}


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


def _parse_dt(value: str) -> datetime | None:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _env_enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _missing_ctp_env() -> list[str]:
    return [key for key in CTP_ENV_KEYS if not os.getenv(key, "")]


def _safe_float(value: Any, default: float = 0.0) -> float:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return default
    return float(number)


def _round_to_tick(price: float, pricetick: float) -> float:
    if pricetick <= 0:
        return price
    return round(round(price / pricetick) * pricetick, 10)


def _split_vt_symbol(vt_symbol: str) -> tuple[str, Exchange | None]:
    if "." not in vt_symbol:
        return vt_symbol, None
    symbol, exchange_text = vt_symbol.rsplit(".", 1)
    try:
        return symbol, Exchange(exchange_text)
    except ValueError:
        return symbol, None


def _object_to_row(obj: Any) -> dict[str, Any]:
    if obj is None:
        return {}
    if is_dataclass(obj):
        row = asdict(obj)
    elif hasattr(obj, "__dict__"):
        row = dict(obj.__dict__)
    else:
        row = {"value": str(obj)}
    for attr in ("vt_symbol", "vt_orderid", "vt_tradeid", "vt_accountid"):
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
    row.setdefault("received_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    return row


def _jsonable(value: Any) -> Any:
    if isinstance(value, bytes):
        for encoding in ("utf-8", "gbk", "gb2312"):
            try:
                return value.decode(encoding)
            except UnicodeDecodeError:
                continue
        return value.decode("utf-8", errors="replace")
    if isinstance(value, (datetime, pd.Timestamp)):
        return value.isoformat()
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    if value is None:
        return ""
    return value


def _raw_ctp_callback_row(
    callback: str,
    data: Any,
    error: Any | None = None,
    reqid: int | None = None,
    last: bool | None = None,
) -> dict[str, Any]:
    data_jsonable = _jsonable(data or {})
    error_jsonable = _jsonable(error or {})
    data_dict = data_jsonable if isinstance(data_jsonable, dict) else {}
    error_dict = error_jsonable if isinstance(error_jsonable, dict) else {}
    return {
        "received_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "callback": callback,
        "instrument_id": data_dict.get("InstrumentID", ""),
        "exchange_id": data_dict.get("ExchangeID", ""),
        "front_id": data_dict.get("FrontID", ""),
        "session_id": data_dict.get("SessionID", ""),
        "order_ref": data_dict.get("OrderRef", ""),
        "order_sys_id": data_dict.get("OrderSysID", ""),
        "order_local_id": data_dict.get("OrderLocalID", ""),
        "order_status": data_dict.get("OrderStatus", ""),
        "order_submit_status": data_dict.get("OrderSubmitStatus", ""),
        "status_msg": data_dict.get("StatusMsg", ""),
        "insert_date": data_dict.get("InsertDate", ""),
        "insert_time": data_dict.get("InsertTime", ""),
        "cancel_time": data_dict.get("CancelTime", ""),
        "direction": data_dict.get("Direction", ""),
        "comb_offset_flag": data_dict.get("CombOffsetFlag", ""),
        "limit_price": data_dict.get("LimitPrice", ""),
        "volume_total_original": data_dict.get("VolumeTotalOriginal", ""),
        "volume_traded": data_dict.get("VolumeTraded", ""),
        "error_id": error_dict.get("ErrorID", ""),
        "error_msg": error_dict.get("ErrorMsg", ""),
        "reqid": "" if reqid is None else reqid,
        "last": "" if last is None else int(bool(last)),
        "data_json": json.dumps(data_jsonable, ensure_ascii=False, default=str),
        "error_json": json.dumps(error_jsonable, ensure_ascii=False, default=str),
    }


def _unique_nonempty(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _message_values(rows: list[dict[str, Any]], *fields: str) -> list[str]:
    values: list[Any] = []
    for row in rows:
        for field in fields:
            values.append(row.get(field, ""))
    return _unique_nonempty(values)


def _rows_for_vt_orderid(rows: list[dict[str, Any]], vt_orderid: str) -> list[dict[str, Any]]:
    _, _, local_orderid = vt_orderid.partition(".")
    parts = local_orderid.split("_", 2)
    if len(parts) != 3:
        return []
    front_id, session_id, order_ref = parts
    return [
        row
        for row in rows
        if str(row.get("front_id", "")).strip() == front_id
        and str(row.get("session_id", "")).strip() == session_id
        and str(row.get("order_ref", "")).strip() == order_ref
    ]


def _install_ctp_callback_capture(rows: dict[str, list[dict[str, Any]]]) -> Any:
    from vnpy_ctp.gateway import ctp_gateway as ctp_gateway_module

    cls = ctp_gateway_module.CtpTdApi
    originals: dict[str, Any] = {}

    def capture(bucket: str, callback: str, data: Any, error: Any | None = None, reqid: int | None = None, last: bool | None = None) -> None:
        try:
            rows[bucket].append(_raw_ctp_callback_row(callback, data, error, reqid, last))
        except Exception as exc:
            rows["callback_capture_errors"].append(
                {
                    "received_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "callback": callback,
                    "failure_reason": repr(exc),
                }
            )

    def patch_rsp(name: str, bucket: str) -> None:
        original = getattr(cls, name)
        originals[name] = original

        def wrapper(self: Any, data: dict, error: dict, reqid: int, last: bool, _original: Any = original) -> Any:
            capture(bucket, name, data, error, reqid, last)
            return _original(self, data, error, reqid, last)

        setattr(cls, name, wrapper)

    def patch_err(name: str, bucket: str) -> None:
        original = getattr(cls, name)
        originals[name] = original

        def wrapper(self: Any, data: dict, error: dict, _original: Any = original) -> Any:
            capture(bucket, name, data, error)
            return _original(self, data, error)

        setattr(cls, name, wrapper)

    def patch_rtn_order() -> None:
        name = "onRtnOrder"
        original = getattr(cls, name)
        originals[name] = original

        def wrapper(self: Any, data: dict, _original: Any = original) -> Any:
            capture("raw_orders", name, data)
            return _original(self, data)

        setattr(cls, name, wrapper)

    for method_name, bucket_name in (
        ("onRspOrderInsert", "order_insert_errors"),
        ("onRspOrderAction", "order_action_errors"),
    ):
        if hasattr(cls, method_name):
            patch_rsp(method_name, bucket_name)
    for method_name, bucket_name in (
        ("onErrRtnOrderInsert", "order_insert_errors"),
        ("onErrRtnOrderAction", "order_action_errors"),
    ):
        if hasattr(cls, method_name):
            patch_err(method_name, bucket_name)
    if hasattr(cls, "onRtnOrder"):
        patch_rtn_order()

    def restore() -> None:
        for name, original in originals.items():
            setattr(cls, name, original)

    return restore


def _write_df(path: Path, rows: list[dict[str, Any]]) -> None:
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")


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


def _readonly_gate(max_age_seconds: int) -> dict[str, Any]:
    summary = _read_json(READONLY_SUMMARY_PATH)
    generated_at = str(summary.get("generated_at", ""))
    generated_dt = _parse_dt(generated_at)
    age_seconds = None if generated_dt is None else round((datetime.now() - generated_dt).total_seconds(), 3)
    broker = summary.get("broker_snapshot", {})
    position_state = str(broker.get("position_snapshot_state", ""))
    return {
        "summary_path": str(READONLY_SUMMARY_PATH.resolve()),
        "status": summary.get("status", ""),
        "generated_at": generated_at,
        "age_seconds": age_seconds,
        "position_snapshot_state": position_state,
        "nonzero_position_rows": broker.get("nonzero_position_rows", ""),
        "passed": (
            summary.get("status") == "readonly_snapshots_received"
            and position_state == "confirmed_flat"
            and age_seconds is not None
            and age_seconds <= max_age_seconds
        ),
    }


def _stage927_gate(target_date: str, max_age_seconds: int) -> dict[str, Any]:
    summary = _read_json(_stage927_summary_path(target_date))
    generated_at = str(summary.get("generated_at", ""))
    generated_dt = _parse_dt(generated_at)
    age_seconds = None if generated_dt is None else round((datetime.now() - generated_dt).total_seconds(), 3)
    return {
        "summary_path": str(_stage927_summary_path(target_date).resolve()),
        "generated_at": generated_at,
        "age_seconds": age_seconds,
        "arming_status": summary.get("arming_status", ""),
        "real_submit_permitted": summary.get("real_submit_permitted", 0),
        "blocking_failure_count": summary.get("blocking_failure_count", ""),
        "order_api_called_count": summary.get("order_api_called_count", ""),
        "passed": (
            summary.get("real_submit_permitted") == 1
            and summary.get("blocking_failure_count") == 0
            and summary.get("order_api_called_count") == 0
            and age_seconds is not None
            and age_seconds <= max_age_seconds
        ),
    }


def _choose_smoke_price(
    tick: dict[str, Any],
    contract: dict[str, Any],
    direction: Direction,
    ticks_away: int,
    manual_price: float | None,
) -> tuple[float, list[str]]:
    pricetick = _safe_float(contract.get("pricetick"), 0.0)
    reasons: list[str] = []
    if manual_price is not None and manual_price > 0:
        return _round_to_tick(manual_price, pricetick), ["manual_price"]
    limit_up = _safe_float(tick.get("limit_up"), 0.0)
    limit_down = _safe_float(tick.get("limit_down"), 0.0)
    bid = _safe_float(tick.get("bid_price_1"), 0.0)
    ask = _safe_float(tick.get("ask_price_1"), 0.0)
    last = _safe_float(tick.get("last_price"), 0.0)
    if direction == Direction.LONG and limit_down > 0:
        return _round_to_tick(limit_down, pricetick), ["limit_down_buy_open_far_passive"]
    if direction == Direction.SHORT and limit_up > 0:
        return _round_to_tick(limit_up, pricetick), ["limit_up_sell_open_far_passive"]
    anchor = bid if direction == Direction.LONG else ask
    if anchor <= 0:
        anchor = last
        reasons.append("used_last_price_anchor")
    if anchor <= 0 or pricetick <= 0:
        return 0.0, reasons + ["missing_tick_or_pricetick"]
    ticks = max(1, int(ticks_away))
    price = anchor - ticks * pricetick if direction == Direction.LONG else anchor + ticks * pricetick
    return _round_to_tick(price, pricetick), reasons + ["passive_ticks_away"]


def _latest_active_order(orders: list[dict[str, Any]], vt_orderid: str) -> dict[str, Any] | None:
    gateway, _, orderid = vt_orderid.partition(".")
    matched = [row for row in orders if str(row.get("gateway_name", "")) == gateway and str(row.get("orderid", "")) == orderid]
    return matched[-1] if matched else None


def _status_is_active(status_value: Any) -> bool:
    text = str(status_value)
    return text in {Status.SUBMITTING.value, Status.NOTTRADED.value, Status.PARTTRADED.value, "SUBMITTING", "NOTTRADED", "PARTTRADED"}


def _trade_volume(rows: list[dict[str, Any]], vt_orderid: str) -> float:
    gateway, _, orderid = vt_orderid.partition(".")
    total = 0.0
    for row in rows:
        if str(row.get("gateway_name", "")) == gateway and str(row.get("orderid", "")) == orderid:
            total += _safe_float(row.get("volume"), 0.0)
    return total


def _build_report(summary: dict[str, Any], rows: dict[str, list[dict[str, Any]]]) -> str:
    return "\n".join(
        [
            "# Stage932 Official Live CTP Smoke Order",
            "",
            f"- generated_at: `{summary['generated_at']}`",
            f"- official_live: `{summary['official_live_version']}` / `{summary['official_live_alias']}`",
            f"- mode: `{summary['mode']}`",
            f"- target_date: `{summary['target_date']}`",
            f"- vt_symbol: `{summary['vt_symbol']}`",
            f"- status: `{summary['status']}`",
            f"- smoke_passed: `{summary['smoke_passed']}`",
            f"- send_order_api_called_count: `{summary['send_order_api_called_count']}`",
            f"- cancel_order_api_called_count: `{summary['cancel_order_api_called_count']}`",
            f"- trade_volume: `{summary['trade_volume']}`",
            f"- vt_orderid: `{summary['vt_orderid']}`",
            f"- order_request: `{json.dumps(summary['order_request'], ensure_ascii=False, default=str)}`",
            "",
            "## Gates",
            "",
            f"- stage927_gate: `{summary['stage927_gate']}`",
            f"- readonly_gate: `{summary['readonly_gate']}`",
            "",
            "## Latest Orders",
            "",
            pd.DataFrame(rows["orders"]).tail(20).to_markdown(index=False) if rows["orders"] else "_empty_",
            "",
            "## Latest Trades",
            "",
            pd.DataFrame(rows["trades"]).tail(20).to_markdown(index=False) if rows["trades"] else "_empty_",
            "",
            "## Raw CTP Order Messages",
            "",
            pd.DataFrame(rows["raw_orders"]).tail(20).to_markdown(index=False) if rows["raw_orders"] else "_empty_",
            "",
            "## Order Insert Errors",
            "",
            pd.DataFrame(rows["order_insert_errors"]).tail(20).to_markdown(index=False)
            if rows["order_insert_errors"]
            else "_empty_",
            "",
            "## Order Action Errors",
            "",
            pd.DataFrame(rows["order_action_errors"]).tail(20).to_markdown(index=False)
            if rows["order_action_errors"]
            else "_empty_",
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
    missing_env = _missing_ctp_env()
    readonly_gate = _readonly_gate(args.max_snapshot_age_seconds)
    stage927_gate = _stage927_gate(args.target_date, args.max_stage927_age_seconds)
    real_submit_env = _env_enabled(PHASE_D_REAL_ENABLED_ENV)
    smoke_env = _env_enabled(SMOKE_ENV)
    live_confirm_ok = args.confirm_live_real == PHASE_D_CONFIRM_TEXT
    smoke_confirm_ok = args.confirm_smoke == SMOKE_CONFIRM_TEXT
    volume = int(args.volume)
    rows: dict[str, list[dict[str, Any]]] = {
        key: []
        for key in (
            "ticks",
            "orders",
            "trades",
            "positions",
            "accounts",
            "logs",
            "raw_orders",
            "order_insert_errors",
            "order_action_errors",
            "callback_capture_errors",
        )
    }

    summary: dict[str, Any] = {
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "target_date": args.target_date,
        "mode": args.mode,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "vt_symbol": vt_symbol,
        "status": "initialized",
        "failure_reason": "",
        "smoke_passed": 0,
        "stage927_gate": stage927_gate,
        "readonly_gate": readonly_gate,
        "missing_required_env": missing_env,
        "contract_found": bool(contract),
        "real_submit_env_enabled": int(real_submit_env),
        "smoke_env_enabled": int(smoke_env),
        "confirm_live_real_ok": int(live_confirm_ok),
        "confirm_smoke_ok": int(smoke_confirm_ok),
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "order_api_called_count": 0,
        "trade_volume": 0.0,
        "vt_orderid": "",
        "order_request": {},
        "latest_order": {},
        "order_insert_error_messages": [],
        "order_action_error_messages": [],
        "current_order_raw_status_messages": [],
        "raw_order_status_messages": [],
        "all_raw_order_status_messages": [],
        "observed_error_message_count": 0,
        "outputs": {key: str(value.resolve()) for key, value in paths.items()},
        "judgement": {
            "overfit_before": "否。Stage932 只验证生产 CTP 报撤链路，不修改 C9 参数。",
            "continue_before": "是。live-real 自动开平仓前需要最小真实报撤证据。",
        },
    }

    blockers: list[str] = []
    if missing_env:
        blockers.append("missing_ctp_env:" + ",".join(missing_env))
    if exchange is None:
        blockers.append("invalid_vt_symbol")
    if not contract:
        blockers.append("contract_not_found")
    if volume != 1:
        blockers.append("volume_must_equal_1")
    if args.mode == "submit-cancel":
        if not stage927_gate["passed"]:
            blockers.append("stage927_gate_not_passed")
        if not readonly_gate["passed"]:
            blockers.append("readonly_gate_not_passed")
        if not real_submit_env:
            blockers.append("real_submit_env_disabled")
        if not smoke_env:
            blockers.append("smoke_env_disabled")
        if not live_confirm_ok:
            blockers.append("live_confirm_missing")
        if not smoke_confirm_ok:
            blockers.append("smoke_confirm_missing")
    if blockers:
        summary["status"] = "blocked"
        summary["failure_reason"] = ";".join(blockers)
        return summary | {"rows": rows}

    from vnpy_ctp import CtpGateway

    event_engine = EventEngine()
    main_engine: MainEngine | None = MainEngine(event_engine)
    restore_ctp_callbacks = _install_ctp_callback_capture(rows)
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
        time.sleep(max(1, args.connect_wait_seconds))
        main_engine.subscribe(SubscribeRequest(symbol=symbol, exchange=exchange), "CTP")
        deadline = time.time() + max(1, args.tick_wait_seconds)
        while time.time() < deadline and not rows["ticks"]:
            time.sleep(0.2)
        if not rows["ticks"]:
            summary["status"] = "blocked_no_tick"
            summary["failure_reason"] = "no_tick_after_subscribe"
            return summary | {"rows": rows}

        direction = Direction.LONG if args.direction == "long" else Direction.SHORT
        price, price_reasons = _choose_smoke_price(rows["ticks"][-1], contract or {}, direction, args.passive_ticks_away, args.manual_price)
        if price <= 0:
            summary["status"] = "blocked_invalid_price"
            summary["failure_reason"] = ";".join(price_reasons)
            return summary | {"rows": rows}
        req = OrderRequest(
            symbol=symbol,
            exchange=exchange,
            direction=direction,
            type=OrderType.LIMIT,
            volume=float(volume),
            price=price,
            offset=Offset.OPEN,
            reference=f"Stage932LiveSmoke:{run_id}",
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
            "latest_tick": rows["ticks"][-1],
        }
        if args.mode == "dry-run":
            summary["status"] = "dry_run_request_ready"
            return summary | {"rows": rows}

        vt_orderid = main_engine.send_order(req, "CTP")
        summary["send_order_api_called_count"] = 1
        summary["order_api_called_count"] = 1
        summary["vt_orderid"] = vt_orderid
        if not vt_orderid:
            summary["status"] = "submit_failed_no_vt_orderid"
            summary["failure_reason"] = "send_order_returned_empty"
            return summary | {"rows": rows}
        latest_order = None
        deadline = time.time() + max(1, args.cancel_after_seconds)
        while time.time() < deadline:
            latest_order = _latest_active_order(rows["orders"], vt_orderid)
            if latest_order and _status_is_active(latest_order.get("status")):
                break
            time.sleep(0.1)
        if latest_order and _status_is_active(latest_order.get("status")):
            _, _, orderid = vt_orderid.partition(".")
            main_engine.cancel_order(CancelRequest(orderid=orderid, symbol=symbol, exchange=exchange), "CTP")
            summary["cancel_order_api_called_count"] = 1
            summary["order_api_called_count"] = 2
            time.sleep(max(1, args.post_cancel_wait_seconds))
            summary["status"] = "submit_cancel_attempted"
        else:
            summary["status"] = "submit_seen_non_active_before_cancel"
            summary["failure_reason"] = "order_not_active_before_cancel"
        summary["latest_order"] = latest_order or {}
        summary["trade_volume"] = _trade_volume(rows["trades"], vt_orderid)
        current_raw_orders = _rows_for_vt_orderid(rows["raw_orders"], vt_orderid)
        insert_messages = _message_values(rows["order_insert_errors"], "error_msg", "status_msg")
        action_messages = _message_values(rows["order_action_errors"], "error_msg", "status_msg")
        status_messages = _message_values(current_raw_orders, "status_msg")
        all_status_messages = _message_values(rows["raw_orders"], "status_msg")
        summary["order_insert_error_messages"] = insert_messages
        summary["order_action_error_messages"] = action_messages
        summary["current_order_raw_status_messages"] = status_messages
        summary["raw_order_status_messages"] = status_messages
        summary["all_raw_order_status_messages"] = all_status_messages
        summary["observed_error_message_count"] = len(insert_messages) + len(action_messages) + len(status_messages)
        if summary["status"] == "submit_seen_non_active_before_cancel" and summary["observed_error_message_count"]:
            summary["status"] = "submit_rejected_or_cancelled_before_cancel"
            summary["failure_reason"] = ";".join(
                _unique_nonempty(["order_not_active_before_cancel"] + insert_messages + status_messages)
            )
        if summary["status"] == "submit_cancel_attempted" and summary["trade_volume"] == 0:
            summary["smoke_passed"] = 1
        return summary | {"rows": rows}
    except Exception as exc:
        summary["status"] = "exception"
        summary["failure_reason"] = repr(exc)
        return summary | {"rows": rows}
    finally:
        if main_engine is not None:
            main_engine.close()
        restore_ctp_callbacks()


def main() -> None:
    parser = argparse.ArgumentParser(description="Official production-live CTP 1-lot smoke order.")
    parser.add_argument("--target-date", required=True)
    parser.add_argument("--mode", choices=["dry-run", "submit-cancel"], default="dry-run")
    parser.add_argument("--vt-symbol", default="MA609.CZCE")
    parser.add_argument("--direction", choices=["long", "short"], default="long")
    parser.add_argument("--volume", type=int, default=1)
    parser.add_argument("--passive-ticks-away", type=int, default=100)
    parser.add_argument("--manual-price", type=float)
    parser.add_argument("--connect-wait-seconds", type=int, default=8)
    parser.add_argument("--tick-wait-seconds", type=int, default=20)
    parser.add_argument("--cancel-after-seconds", type=int, default=2)
    parser.add_argument("--post-cancel-wait-seconds", type=int, default=5)
    parser.add_argument("--max-snapshot-age-seconds", type=int, default=300)
    parser.add_argument("--max-stage927-age-seconds", type=int, default=600)
    parser.add_argument("--confirm-live-real", default="")
    parser.add_argument("--confirm-smoke", default="")
    args = parser.parse_args()

    result = run(args)
    rows = result.pop("rows")
    paths = {key: Path(value) for key, value in result["outputs"].items()}
    result["row_counts"] = {key: len(value) for key, value in rows.items()}
    result["judgement"]["overfit_after"] = "否。Stage932 的输出只用于执行验收，不反馈策略优化。"
    result["judgement"]["continue_after"] = (
        "是。若 smoke_passed=1，可继续切 live-real；若有成交或撤单失败，必须先对账/恢复。"
    )
    _write_df(paths["ticks_csv"], rows["ticks"])
    _write_df(paths["orders_csv"], rows["orders"])
    _write_df(paths["trades_csv"], rows["trades"])
    _write_df(paths["positions_csv"], rows["positions"])
    _write_df(paths["accounts_csv"], rows["accounts"])
    _write_df(paths["logs_csv"], rows["logs"])
    _write_df(paths["raw_orders_csv"], rows["raw_orders"])
    _write_df(paths["order_insert_errors_csv"], rows["order_insert_errors"])
    _write_df(paths["order_action_errors_csv"], rows["order_action_errors"])
    _write_df(paths["callback_capture_errors_csv"], rows["callback_capture_errors"])
    paths["summary_json"].write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths["report_md"].write_text(_build_report(result, rows), encoding="utf-8")
    if args.mode == "submit-cancel" or result.get("status") == "exception":
        severity = "info" if result.get("smoke_passed") == 1 else "warning"
        if result.get("trade_volume", 0):
            severity = "critical"
        email_attachments = [
            paths["report_md"],
            paths["summary_json"],
        ]
        if _env_enabled("OFFICIAL_LIVE_EMAIL_ATTACH_RAW_CTP"):
            email_attachments.extend(
                [
                    paths["orders_csv"],
                    paths["trades_csv"],
                    paths["raw_orders_csv"],
                    paths["order_insert_errors_csv"],
                    paths["order_action_errors_csv"],
                ]
            )
            attachment_note = "附件包含 smoke report/summary/未脱敏 raw CTP callback evidence，仅用于显式取证。"
        else:
            attachment_note = (
                "附件包含 smoke report/summary；raw CTP callback evidence 默认不邮件外发，"
                "如需未脱敏取证附件请显式设置 OFFICIAL_LIVE_EMAIL_ATTACH_RAW_CTP=1 后重跑。"
            )
        result["email_notification"] = send_official_live_email_notification(
            subject=(
                f"[C9/15w][Stage932 smoke][{severity}] {result.get('vt_symbol')} "
                f"status={result.get('status')} trade_volume={result.get('trade_volume')}"
            ),
            body="\n".join(
                [
                    "C9/15w Stage932 实盘 smoke 报撤结果。",
                    "",
                    f"生成时间: {result.get('generated_at')}",
                    f"目标日期: {result.get('target_date')}",
                    f"合约: {result.get('vt_symbol')}",
                    f"状态: {result.get('status')}",
                    f"smoke_passed: {result.get('smoke_passed')}",
                    f"send_order_api_called_count: {result.get('send_order_api_called_count')}",
                    f"cancel_order_api_called_count: {result.get('cancel_order_api_called_count')}",
                    f"trade_volume: {result.get('trade_volume')}",
                    f"vt_orderid: {result.get('vt_orderid')}",
                    f"failure_reason: {result.get('failure_reason', '')}",
                    f"current_order_raw_status_messages: {result.get('current_order_raw_status_messages', [])}",
                    "",
                    attachment_note,
                ]
            ),
            event_type="stage932_smoke_order",
            severity=severity,
            attachments=email_attachments,
            metadata={
                "target_date": result.get("target_date"),
                "vt_symbol": result.get("vt_symbol"),
                "status": result.get("status"),
                "smoke_passed": result.get("smoke_passed"),
                "order_api_called_count": result.get("order_api_called_count"),
                "trade_volume": result.get("trade_volume"),
            },
        )
        paths["summary_json"].write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
