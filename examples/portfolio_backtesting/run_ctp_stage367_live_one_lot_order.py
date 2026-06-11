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

from vnpy.event import EventEngine
from vnpy.trader.constant import Direction, Exchange, Offset, OrderType, Status
from vnpy.trader.engine import MainEngine
from vnpy.trader.event import EVENT_ACCOUNT, EVENT_LOG, EVENT_ORDER, EVENT_POSITION, EVENT_TICK, EVENT_TRADE
from vnpy.trader.object import CancelRequest, OrderRequest, SubscribeRequest


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
MODEL_TAG = "stage367_live_one_lot_order_v1"
OUTPUT_PREFIX = "qmt_roll_stage367_live_one_lot_order"
READONLY_SUMMARY_PATH = (
    OUTPUT_DIR / "qmt_roll_stage655_readonly_account_margin_probe_summary_stage655_readonly_account_margin_probe_v1.json"
)
READONLY_POSITIONS_PATH = (
    OUTPUT_DIR / "qmt_roll_stage655_readonly_account_margin_probe_positions_stage655_readonly_account_margin_probe_v1.csv"
)

CONFIRM_TEXT = "I_UNDERSTAND_THIS_SENDS_REAL_CTP_LIVE_ORDER"
RESIDUAL_CONFIRM_TEXT = "I_UNDERSTAND_THIS_LEAVES_A_REAL_POSITION"
CLOSE_CONFIRM_TEXT = "I_UNDERSTAND_THIS_SENDS_REAL_CTP_LIVE_CLOSE_ORDER"

CONTRACT_SPECS: dict[str, dict[str, float]] = {
    # Broker mobile app showed FG2609 margin as 1028 * 20 * 15% = 3084.
    "FG.CZCE": {"volume_multiple": 20.0, "price_tick": 1.0, "margin_ratio": 0.15},
    "MA.CZCE": {"volume_multiple": 10.0, "price_tick": 1.0, "margin_ratio": 0.12},
    "SA.CZCE": {"volume_multiple": 20.0, "price_tick": 1.0, "margin_ratio": 0.07},
    "rb.SHFE": {"volume_multiple": 10.0, "price_tick": 1.0, "margin_ratio": 0.08},
    "hc.SHFE": {"volume_multiple": 10.0, "price_tick": 1.0, "margin_ratio": 0.08},
    "sp.SHFE": {"volume_multiple": 10.0, "price_tick": 2.0, "margin_ratio": 0.07},
    "jm.DCE": {"volume_multiple": 60.0, "price_tick": 0.5, "margin_ratio": 0.08},
}


def _paths(run_id: str) -> dict[str, Path]:
    return {
        "summary_json": OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{run_id}_{MODEL_TAG}.json",
        "ticks_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_ticks_{run_id}_{MODEL_TAG}.csv",
        "orders_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_orders_{run_id}_{MODEL_TAG}.csv",
        "trades_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_trades_{run_id}_{MODEL_TAG}.csv",
        "positions_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_positions_{run_id}_{MODEL_TAG}.csv",
        "accounts_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_accounts_{run_id}_{MODEL_TAG}.csv",
        "logs_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_logs_{run_id}_{MODEL_TAG}.csv",
    }


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_read_error": repr(exc)}


def _parse_dt(value: str) -> datetime | None:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _env_enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 4:
        return "*" * len(value)
    return f"{value[:2]}***{value[-2:]}"


def _env_status() -> dict[str, Any]:
    keys = {
        "userid": "CTP_USERID",
        "brokerid": "CTP_BROKERID",
        "td_address": "CTP_TD_ADDRESS",
        "md_address": "CTP_MD_ADDRESS",
        "appid": "CTP_APPID",
        "auth_code": "CTP_AUTH_CODE",
        "product_info": "CTP_PRODUCT_INFO",
    }
    status: dict[str, Any] = {}
    for logical, key in keys.items():
        value = os.getenv(key, "")
        status[logical] = {
            "env_key": key,
            "configured": bool(value),
            "masked_value": _mask(value) if logical in {"userid", "brokerid"} else "",
        }
    return status


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


def _object_to_row(obj: Any) -> dict[str, Any]:
    if obj is None:
        return {}
    if is_dataclass(obj):
        row = asdict(obj)
    elif hasattr(obj, "__dict__"):
        row = dict(obj.__dict__)
    else:
        row = {"value": str(obj)}
    for attr in ["vt_symbol", "vt_orderid", "vt_tradeid", "vt_positionid", "vt_accountid"]:
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
    row.setdefault("received_at", _now())
    return row


def _write_df(path: Path, rows: list[dict[str, Any]]) -> None:
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")


def _safe_float(value: Any, default: float = 0.0) -> float:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return default
    return float(number)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _split_vt_symbol(vt_symbol: str) -> tuple[str, Exchange | None, str]:
    if "." not in vt_symbol:
        return vt_symbol, None, ""
    symbol, exchange_value = vt_symbol.rsplit(".", 1)
    try:
        exchange = Exchange(exchange_value)
    except ValueError:
        exchange = None
    root = "".join(ch for ch in symbol if ch.isalpha())
    return symbol, exchange, f"{root}.{exchange_value}"


def _readonly_gate(max_age_seconds: int) -> dict[str, Any]:
    summary = _read_json(READONLY_SUMMARY_PATH)
    generated_at = str(summary.get("generated_at", ""))
    generated_dt = _parse_dt(generated_at)
    age_seconds = None
    if generated_dt:
        age_seconds = round((datetime.now() - generated_dt).total_seconds(), 3)
    return {
        "summary_path": str(READONLY_SUMMARY_PATH),
        "read_error": str(summary.get("_read_error", "")),
        "generated_at": generated_at,
        "age_seconds": age_seconds,
        "fresh": age_seconds is not None and age_seconds <= max_age_seconds,
        "status": summary.get("status", ""),
        "front_connected": bool(summary.get("front_connected")),
        "auth_ok": bool(summary.get("auth_ok")),
        "login_ok": bool(summary.get("login_ok")),
        "settlement_ok": bool(summary.get("settlement_ok")),
        "account_query_received": bool(summary.get("account_query_received")),
        "position_query_completed": bool(summary.get("position_query_completed")),
        "position_query_error_id": _safe_int(summary.get("position_query_error_id")),
        "position_query_error_msg": str(summary.get("position_query_error_msg") or ""),
        "position_query_ok": bool(summary.get("position_query_ok")),
        "account_rows": _safe_int(summary.get("account_rows")),
        "position_rows": _safe_int(summary.get("position_rows")),
        "explicit_margin_rows": _safe_int(summary.get("explicit_margin_rows")),
        "passed": (
            not summary.get("_read_error")
            and summary.get("status") == "readonly_account_margin_received"
            and bool(summary.get("front_connected"))
            and bool(summary.get("auth_ok"))
            and bool(summary.get("login_ok"))
            and bool(summary.get("settlement_ok"))
            and bool(summary.get("account_query_received"))
            and bool(summary.get("position_query_completed"))
            and bool(summary.get("position_query_ok"))
            and _safe_int(summary.get("account_rows")) >= 1
            and _safe_int(summary.get("explicit_margin_rows")) >= 1
            and _safe_int(summary.get("position_rows")) == 0
            and age_seconds is not None
            and age_seconds <= max_age_seconds
        ),
    }


def _position_side(value: Any) -> str:
    text = str(value).strip().lower()
    if text in {"2", "long", "多", "buy"}:
        return "long"
    if text in {"3", "short", "空", "sell"}:
        return "short"
    return text


def _position_gate(symbol: str, direction: Direction, volume: int) -> dict[str, Any]:
    if not READONLY_POSITIONS_PATH.exists():
        return {
            "positions_path": str(READONLY_POSITIONS_PATH),
            "passed": False,
            "reason": "positions_file_missing",
            "matched_position": 0.0,
            "target_position_side": "",
        }
    try:
        frame = pd.read_csv(READONLY_POSITIONS_PATH, encoding="utf-8-sig")
    except Exception as exc:
        return {
            "positions_path": str(READONLY_POSITIONS_PATH),
            "passed": False,
            "reason": f"positions_file_unreadable:{exc!r}",
            "matched_position": 0.0,
            "target_position_side": "",
        }
    if frame.empty:
        return {
            "positions_path": str(READONLY_POSITIONS_PATH),
            "passed": False,
            "reason": "positions_empty",
            "matched_position": 0.0,
            "target_position_side": "",
        }
    target_side = "long" if direction == Direction.SHORT else "short"
    if "instrument" not in frame.columns:
        return {
            "positions_path": str(READONLY_POSITIONS_PATH),
            "passed": False,
            "reason": "positions_file_missing_instrument_column",
            "matched_position": 0.0,
            "target_position_side": target_side,
        }
    view = frame[frame["instrument"].astype(str).eq(symbol)].copy()
    if view.empty:
        return {
            "positions_path": str(READONLY_POSITIONS_PATH),
            "passed": False,
            "reason": "instrument_position_missing",
            "matched_position": 0.0,
            "target_position_side": target_side,
        }
    view["position_side"] = view.get("direction", "").map(_position_side)
    view["position_num"] = pd.to_numeric(view.get("position", 0.0), errors="coerce").fillna(0.0)
    matched = view[view["position_side"].eq(target_side)]
    matched_position = float(matched["position_num"].sum()) if not matched.empty else 0.0
    return {
        "positions_path": str(READONLY_POSITIONS_PATH),
        "passed": matched_position >= int(volume),
        "reason": "" if matched_position >= int(volume) else "matching_position_insufficient",
        "matched_position": matched_position,
        "target_position_side": target_side,
        "matched_rows": matched.to_dict("records"),
    }


def _round_to_tick(price: float, price_tick: float) -> float:
    if price_tick <= 0:
        return price
    return round(round(price / price_tick) * price_tick, 10)


def _aggressive_price(tick: dict[str, Any], spec: dict[str, float], direction: Direction, aggressive_ticks: int) -> tuple[float, list[str]]:
    price_tick = float(spec["price_tick"])
    bid = _safe_float(tick.get("bid_price_1"), 0.0)
    ask = _safe_float(tick.get("ask_price_1"), 0.0)
    last = _safe_float(tick.get("last_price"), 0.0)
    limit_up = _safe_float(tick.get("limit_up"), 0.0)
    limit_down = _safe_float(tick.get("limit_down"), 0.0)
    reasons: list[str] = []
    ticks = max(int(aggressive_ticks), 0)
    if direction == Direction.LONG:
        anchor = ask if ask > 0 else last
        if ask <= 0:
            reasons.append("ask_missing_used_last")
        price = anchor + ticks * price_tick
        if limit_up > 0:
            price = min(price, limit_up)
    else:
        anchor = bid if bid > 0 else last
        if bid <= 0:
            reasons.append("bid_missing_used_last")
        price = anchor - ticks * price_tick
        if limit_down > 0:
            price = max(price, limit_down)
    return _round_to_tick(price, price_tick), reasons


def _latest_active_order(orders: list[dict[str, Any]], vt_orderid: str) -> dict[str, Any] | None:
    if not vt_orderid:
        return None
    gateway, _, orderid = vt_orderid.partition(".")
    matched = [
        row for row in orders
        if str(row.get("gateway_name", "")) == gateway and str(row.get("orderid", "")) == orderid
    ]
    return matched[-1] if matched else None


def _matching_trade_volume(
    trades: list[dict[str, Any]],
    *,
    vt_orderid: str,
    vt_symbol: str,
    direction: Direction,
    offset: Offset,
) -> tuple[float, int]:
    _, _, orderid = vt_orderid.partition(".")
    fallback_rows = 0
    filled = 0.0
    for row in trades:
        row_vt_orderid = str(row.get("vt_orderid") or "")
        row_orderid = str(row.get("orderid") or "")
        if row_vt_orderid:
            if row_vt_orderid != vt_orderid:
                continue
        elif row_orderid:
            if row_orderid != orderid:
                continue
        else:
            fallback_rows += 1

        if (
            row.get("vt_symbol") == vt_symbol
            and row.get("direction") == direction.value
            and row.get("offset") == offset.value
        ):
            filled += _safe_float(row.get("volume"), 0.0)
    return filled, fallback_rows


def _status_is_active(status_value: Any) -> bool:
    text = str(status_value)
    return text in {Status.SUBMITTING.value, Status.NOTTRADED.value, Status.PARTTRADED.value, "SUBMITTING", "NOTTRADED", "PARTTRADED"}


def run(args: argparse.Namespace) -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    paths = _paths(run_id)

    vt_symbol = args.vt_symbol.strip()
    symbol, exchange, spec_key = _split_vt_symbol(vt_symbol)
    spec = CONTRACT_SPECS.get(spec_key)
    direction = Direction.LONG if args.direction == "long" else Direction.SHORT
    readonly_gate = _readonly_gate(args.max_snapshot_age_seconds)
    submit_enabled = _env_enabled("CTP_LIVE_ONE_LOT_ENABLED")
    confirm_ok = args.confirm_submit == CONFIRM_TEXT
    residual_ok = args.confirm_residual_position == RESIDUAL_CONFIRM_TEXT
    close_confirm_ok = args.confirm_close_position == CLOSE_CONFIRM_TEXT
    is_close_mode = args.mode in {"dry-run-close", "submit-close"}
    position_gate = _position_gate(symbol, direction, int(args.volume)) if is_close_mode else {}

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
        "run_id": run_id,
        "mode": args.mode,
        "vt_symbol": vt_symbol,
        "direction": direction.value,
        "volume": int(args.volume),
        "status": "initialized",
        "failure_reason": "",
        "env_status": _env_status(),
        "missing_required_env": _required_env_missing(),
        "readonly_gate": readonly_gate,
        "submit_enabled_env": submit_enabled,
        "confirm_submit_ok": confirm_ok,
        "confirm_residual_position_ok": residual_ok,
        "confirm_close_position_ok": close_confirm_ok,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "vt_orderid": "",
        "position_gate": position_gate,
        "order_request": {},
        "latest_tick": {},
        "estimated": {},
        "outputs": {key: str(value.resolve()) for key, value in paths.items()},
    }

    def finish(status: str, reason: str = "") -> dict[str, Any]:
        summary["status"] = status
        summary["failure_reason"] = reason
        summary["row_counts"] = {key: len(value) for key, value in rows.items()}
        summary["rows"] = rows
        return summary

    if summary["missing_required_env"]:
        return finish("blocked_missing_env", ",".join(summary["missing_required_env"]))
    if exchange is None:
        return finish("blocked_invalid_vt_symbol", "invalid_vt_symbol")
    if spec is None:
        return finish("blocked_unsupported_contract_spec", f"missing_spec_for_{spec_key}")
    if int(args.volume) != 1:
        return finish("blocked_volume_must_be_one", "volume_must_be_one")
    if args.mode in {"submit-open", "submit-close"}:
        if not readonly_gate["passed"]:
            if args.mode == "submit-close" and (
                readonly_gate["fresh"]
                and readonly_gate["status"] == "readonly_account_margin_received"
                and readonly_gate["front_connected"]
                and readonly_gate["auth_ok"]
                and readonly_gate["login_ok"]
                and readonly_gate["settlement_ok"]
                and readonly_gate["account_query_received"]
                and readonly_gate["position_query_completed"]
                and readonly_gate["position_query_ok"]
                and readonly_gate["account_rows"] >= 1
                and readonly_gate["explicit_margin_rows"] >= 1
                and readonly_gate["position_rows"] >= 1
            ):
                pass
            else:
                return finish("blocked_readonly_gate_not_passed", "readonly_gate_not_passed")
        if not submit_enabled:
            return finish("blocked_submit_env_disabled", "CTP_LIVE_ONE_LOT_ENABLED_not_enabled")
        if not confirm_ok:
            return finish("blocked_confirmation_missing", "confirm_submit_text_missing")
        if args.mode == "submit-open" and not residual_ok:
            return finish("blocked_residual_position_confirmation_missing", "residual_position_confirm_text_missing")
        if args.mode == "submit-close":
            if not close_confirm_ok:
                return finish("blocked_close_position_confirmation_missing", "close_position_confirm_text_missing")
            if not position_gate.get("passed"):
                return finish("blocked_matching_position_missing", str(position_gate.get("reason", "")))

    try:
        from vnpy_ctp import CtpGateway
    except Exception as exc:
        return finish("blocked_ctp_gateway_import_error", repr(exc))

    try:
        event_engine = EventEngine()
        main_engine = MainEngine(event_engine)
        main_engine.add_gateway(CtpGateway)
    except Exception as exc:
        return finish("blocked_ctp_gateway_setup_error", repr(exc))

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
        deadline = time.time() + max(args.tick_wait_seconds, 1)
        while time.time() < deadline and not rows["ticks"]:
            time.sleep(0.2)
        if not rows["ticks"]:
            return finish("blocked_no_tick", "no_tick_after_subscribe")
        tick = rows["ticks"][-1]
        summary["latest_tick"] = tick
        bid = _safe_float(tick.get("bid_price_1"), 0.0)
        ask = _safe_float(tick.get("ask_price_1"), 0.0)
        last = _safe_float(tick.get("last_price"), 0.0)
        if bid <= 0 or ask <= 0 or last <= 0:
            return finish("blocked_invalid_bid_ask", "missing_bid_or_ask")

        price, price_reasons = _aggressive_price(tick, spec, direction, args.aggressive_ticks)
        notional = price * float(spec["volume_multiple"]) * int(args.volume)
        estimated_margin = notional * float(spec["margin_ratio"])
        summary["estimated"] = {
            "volume_multiple": spec["volume_multiple"],
            "price_tick": spec["price_tick"],
            "tick_value": spec["volume_multiple"] * spec["price_tick"],
            "margin_ratio": spec["margin_ratio"],
            "notional": notional,
            "estimated_margin": estimated_margin,
            "spread": ask - bid,
        }

        req = OrderRequest(
            symbol=symbol,
            exchange=exchange,
            direction=direction,
            type=OrderType.LIMIT,
            volume=int(args.volume),
            price=price,
            offset=Offset.CLOSE if is_close_mode else Offset.OPEN,
            reference=f"Stage367LiveOneLot:{run_id}",
        )
        summary["order_request"] = _object_to_row(req)
        summary["order_request"]["price_reasons"] = price_reasons
        if args.mode in {"dry-run", "dry-run-close"}:
            return finish("dry_run_close_request_ready" if is_close_mode else "dry_run_request_ready")

        start_trade_count = len(rows["trades"])
        summary["send_order_api_called_count"] = 1
        vt_orderid = main_engine.send_order(req, "CTP")
        summary["vt_orderid"] = vt_orderid
        if not vt_orderid:
            return finish("submit_failed_no_vt_orderid", "send_order_returned_empty")

        fill_deadline = time.time() + max(args.fill_wait_seconds, 1)
        filled = 0.0
        while time.time() < fill_deadline:
            recent = rows["trades"][start_trade_count:]
            filled, fallback_rows = _matching_trade_volume(
                recent,
                vt_orderid=vt_orderid,
                vt_symbol=vt_symbol,
                direction=direction,
                offset=req.offset,
            )
            summary["trade_match_fallback_rows"] = fallback_rows
            if filled >= int(args.volume):
                summary["filled_volume"] = filled
                time.sleep(max(args.final_wait_seconds, 0))
                if args.mode == "submit-close":
                    return finish("submit_close_filled_position_should_be_flat")
                return finish("submit_open_filled_residual_position_exists")
            time.sleep(0.2)
        summary["filled_volume"] = filled
        latest = _latest_active_order(rows["orders"], vt_orderid)
        if latest and _status_is_active(latest.get("status")):
            _, _, orderid = vt_orderid.partition(".")
            cancel_req = CancelRequest(orderid=orderid, symbol=symbol, exchange=exchange)
            summary["cancel_order_api_called_count"] = 1
            main_engine.cancel_order(cancel_req, "CTP")
            time.sleep(max(args.post_cancel_wait_seconds, 1))
            recent = rows["trades"][start_trade_count:]
            filled, fallback_rows = _matching_trade_volume(
                recent,
                vt_orderid=vt_orderid,
                vt_symbol=vt_symbol,
                direction=direction,
                offset=req.offset,
            )
            summary["trade_match_fallback_rows"] = fallback_rows
            summary["filled_volume"] = filled
            latest_after_cancel = _latest_active_order(rows["orders"], vt_orderid)
            summary["post_cancel_latest_order"] = latest_after_cancel or {}
            summary["post_cancel_order_active"] = bool(latest_after_cancel and _status_is_active(latest_after_cancel.get("status")))
            if filled >= int(args.volume):
                if args.mode == "submit-close":
                    return finish("submit_close_filled_position_should_be_flat", "filled_after_cancel_attempt")
                return finish("submit_open_filled_residual_position_exists", "filled_after_cancel_attempt")
            if latest_after_cancel and not _status_is_active(latest_after_cancel.get("status")):
                return finish(f"{args.mode}_not_filled_cancel_confirmed", f"filled_volume={filled}")
            return finish(f"{args.mode}_cancel_outcome_uncertain", f"filled_volume={filled}")
        return finish(f"{args.mode}_not_filled_order_not_active", f"filled_volume={filled}")
    except Exception as exc:
        return finish("exception", repr(exc))
    finally:
        try:
            main_engine.close()
        except Exception as exc:
            summary["main_engine_close_error"] = repr(exc)


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage367 real CTP one-lot live order gate.")
    parser.add_argument("--mode", choices=["dry-run", "dry-run-close", "submit-open", "submit-close"], default="dry-run")
    parser.add_argument("--vt-symbol", default="FG609.CZCE")
    parser.add_argument("--direction", choices=["long", "short"], default="long")
    parser.add_argument("--volume", type=int, default=1)
    parser.add_argument("--connect-wait-seconds", type=int, default=8)
    parser.add_argument("--tick-wait-seconds", type=int, default=20)
    parser.add_argument("--fill-wait-seconds", type=int, default=10)
    parser.add_argument("--final-wait-seconds", type=int, default=3)
    parser.add_argument("--post-cancel-wait-seconds", type=int, default=5)
    parser.add_argument("--aggressive-ticks", type=int, default=2)
    parser.add_argument("--max-snapshot-age-seconds", type=int, default=300)
    parser.add_argument("--confirm-submit", default="")
    parser.add_argument("--confirm-residual-position", default="")
    parser.add_argument("--confirm-close-position", default="")
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
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
