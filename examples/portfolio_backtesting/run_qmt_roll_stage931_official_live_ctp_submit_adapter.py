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
from qmt_roll_official_live_phase_d_config import (
    KILL_SWITCH_PATH,
    PHASE_D_CONFIRM_TEXT,
    PHASE_D_REAL_ADAPTER_ENV,
    PHASE_D_REAL_ENABLED_ENV,
    build_phase_d_config,
)
from run_qmt_alignment_backtest import OUTPUT_DIR
from vnpy.event import EventEngine
from vnpy.trader.constant import Direction, Exchange, Offset, OrderType, Status
from vnpy.trader.engine import MainEngine
from vnpy.trader.event import EVENT_ACCOUNT, EVENT_LOG, EVENT_ORDER, EVENT_POSITION, EVENT_TRADE
from vnpy.trader.object import CancelRequest, OrderRequest


MODEL_TAG = "stage931_official_live_ctp_submit_adapter_v1"
OUTPUT_PREFIX = "qmt_roll_stage931_official_live_ctp_submit_adapter"
STAGE905_MODEL_TAG = "stage905_official_live_executor_dry_run_v1"
STAGE905_PREFIX = "qmt_roll_stage905_official_live_executor_dry_run"
STAGE927_MODEL_TAG = "stage927_official_live_real_submit_arming_gate_v1"
STAGE927_PREFIX = "qmt_roll_stage927_official_live_real_submit_arming_gate"

CTP_ENV_KEYS = ("CTP_USERID", "CTP_PASSWORD", "CTP_BROKERID", "CTP_TD_ADDRESS", "CTP_MD_ADDRESS", "CTP_APPID", "CTP_AUTH_CODE")


def _paths(target_date: str) -> dict[str, Path]:
    key = target_date.replace("-", "") if target_date else "latest"
    return {
        "summary_json": OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{key}_{MODEL_TAG}.json",
        "orders_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_orders_{key}_{MODEL_TAG}.csv",
        "trades_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_trades_{key}_{MODEL_TAG}.csv",
        "accounts_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_accounts_{key}_{MODEL_TAG}.csv",
        "positions_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_positions_{key}_{MODEL_TAG}.csv",
        "logs_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_logs_{key}_{MODEL_TAG}.csv",
        "submitted_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_submitted_{key}_{MODEL_TAG}.csv",
        "report_md": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{key}_{MODEL_TAG}.md",
    }


def _stage905_intents_path(target_date: str) -> Path:
    key = target_date.replace("-", "") if target_date else "latest"
    return OUTPUT_DIR / f"{STAGE905_PREFIX}_intents_{key}_{STAGE905_MODEL_TAG}.csv"


def _stage927_summary_path(target_date: str) -> Path:
    key = target_date.replace("-", "") if target_date else "latest"
    return OUTPUT_DIR / f"{STAGE927_PREFIX}_summary_{key}_{STAGE927_MODEL_TAG}.json"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_read_error": repr(exc)}


def _read_csv_maybe(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, encoding="utf-8-sig")
    except Exception:
        return pd.DataFrame()


def _env_enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _missing_env() -> list[str]:
    return [key for key in CTP_ENV_KEYS if not os.getenv(key, "")]


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
    for attr in ("vt_symbol", "vt_orderid", "vt_tradeid", "vt_positionid", "vt_accountid"):
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


def _write_df(path: Path, rows: list[dict[str, Any]]) -> None:
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")


def _ready_intents(target_date: str) -> pd.DataFrame:
    intents = _read_csv_maybe(_stage905_intents_path(target_date))
    if intents.empty or "executor_status" not in intents.columns:
        return pd.DataFrame()
    return intents[intents["executor_status"].astype(str).eq("dry_run_order_request_payload_ready")].copy()


def _order_request_from_payload(payload: dict[str, Any]) -> OrderRequest:
    return OrderRequest(
        symbol=str(payload["symbol"]),
        exchange=Exchange(str(payload["exchange"])),
        direction=Direction(str(payload["direction"])),
        type=OrderType(str(payload.get("type") or OrderType.LIMIT.value)),
        volume=float(payload["volume"]),
        price=float(payload["price"]),
        offset=Offset(str(payload["offset"])),
        reference=str(payload.get("reference", "Stage931OfficialLive")),
    )


def _status_is_active(status_value: Any) -> bool:
    text = str(status_value)
    return text in {Status.SUBMITTING.value, Status.NOTTRADED.value, Status.PARTTRADED.value, "SUBMITTING", "NOTTRADED", "PARTTRADED"}


def _latest_active_order(orders: list[dict[str, Any]], vt_orderid: str) -> dict[str, Any] | None:
    gateway, _, orderid = vt_orderid.partition(".")
    matched = [row for row in orders if str(row.get("gateway_name", "")) == gateway and str(row.get("orderid", "")) == orderid]
    return matched[-1] if matched else None


def _build_report(summary: dict[str, Any], submitted: pd.DataFrame) -> str:
    return "\n".join(
        [
            "# Stage931 Official Live CTP Submit Adapter",
            "",
            f"- generated_at: `{summary['generated_at']}`",
            f"- official_live: `{summary['official_live_version']}` / `{summary['official_live_alias']}`",
            f"- target_date: `{summary['target_date']}`",
            f"- mode: `{summary['mode']}`",
            f"- adapter_status: `{summary['adapter_status']}`",
            f"- ready_intent_count: `{summary['ready_intent_count']}`",
            f"- send_order_api_called_count: `{summary['send_order_api_called_count']}`",
            f"- cancel_order_api_called_count: `{summary['cancel_order_api_called_count']}`",
            "",
            "## Submitted",
            "",
            submitted.head(80).to_markdown(index=False) if not submitted.empty else "_empty_",
            "",
            "## Notes",
            "",
            "- Dry-run mode never connects CTP and never calls send_order/cancel_order.",
            "- Live-real mode requires Stage927 real_submit_permitted=1, env switches, exact confirm text, and inactive kill switch.",
            "- Unfilled active orders are cancelled after the configured fill wait.",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Official-live CTP submit adapter, hard-gated by Stage927.")
    parser.add_argument("--target-date", required=True)
    parser.add_argument("--mode", choices=["dry-run", "live-real"], default="dry-run")
    parser.add_argument("--confirm-live-real", default="")
    parser.add_argument("--max-orders", type=int, default=1)
    parser.add_argument("--connect-wait-seconds", type=int, default=8)
    parser.add_argument("--fill-wait-seconds", type=int, default=8)
    parser.add_argument("--post-cancel-wait-seconds", type=int, default=4)
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    paths = _paths(args.target_date)
    ready = _ready_intents(args.target_date)
    stage927 = _read_json(_stage927_summary_path(args.target_date))
    kill_switch = _read_json(KILL_SWITCH_PATH)
    config = build_phase_d_config()
    submitted_rows: list[dict[str, Any]] = []
    rows: dict[str, list[dict[str, Any]]] = {"orders": [], "trades": [], "accounts": [], "positions": [], "logs": []}

    blockers: list[str] = []
    if ready.empty:
        blockers.append("no_ready_stage905_intents")
    if len(ready) > min(args.max_orders, config.hard_limits.max_order_count_per_cycle):
        blockers.append("ready_intent_count_above_limit")
    if bool(kill_switch.get("enabled", False) or kill_switch.get("kill_switch_active", False)):
        blockers.append("kill_switch_active")
    if args.mode == "live-real":
        if stage927.get("real_submit_permitted") != 1:
            blockers.append("stage927_real_submit_not_permitted")
        if not _env_enabled(PHASE_D_REAL_ADAPTER_ENV):
            blockers.append("real_adapter_env_missing")
        if not _env_enabled(PHASE_D_REAL_ENABLED_ENV):
            blockers.append("real_submit_env_missing")
        if args.confirm_live_real != PHASE_D_CONFIRM_TEXT:
            blockers.append("confirm_live_real_missing")
        missing = _missing_env()
        if missing:
            blockers.append("missing_ctp_env:" + ",".join(missing))

    send_count = 0
    cancel_count = 0
    adapter_status = "adapter_dry_run_ready" if not blockers else "adapter_blocked"
    if args.mode == "dry-run":
        for row in ready.head(args.max_orders).to_dict(orient="records"):
            submitted_rows.append(
                {
                    "intent_id": row.get("intent_id", ""),
                    "vt_symbol": row.get("vt_symbol", ""),
                    "mode": "dry-run",
                    "submit_status": "dry_run_not_submitted",
                    "order_request_json": row.get("order_request_json", ""),
                }
            )
    elif not blockers:
        main_engine: MainEngine | None = None
        try:
            from vnpy_ctp import CtpGateway

            event_engine = EventEngine()
            main_engine = MainEngine(event_engine)
            main_engine.add_gateway(CtpGateway)

            def on_order(event: Any) -> None:
                rows["orders"].append(_object_to_row(event.data))

            def on_trade(event: Any) -> None:
                rows["trades"].append(_object_to_row(event.data))

            def on_account(event: Any) -> None:
                rows["accounts"].append(_object_to_row(event.data))

            def on_position(event: Any) -> None:
                rows["positions"].append(_object_to_row(event.data))

            def on_log(event: Any) -> None:
                rows["logs"].append(_object_to_row(event.data))

            event_engine.register(EVENT_ORDER, on_order)
            event_engine.register(EVENT_TRADE, on_trade)
            event_engine.register(EVENT_ACCOUNT, on_account)
            event_engine.register(EVENT_POSITION, on_position)
            event_engine.register(EVENT_LOG, on_log)
            main_engine.connect(_ctp_setting_from_env(), "CTP")
            time.sleep(max(1, args.connect_wait_seconds))
            for row in ready.head(args.max_orders).to_dict(orient="records"):
                payload = json.loads(str(row.get("order_request_json", "{}")))
                req = _order_request_from_payload(payload)
                send_count += 1
                vt_orderid = main_engine.send_order(req, "CTP")
                start_trade_count = len(rows["trades"])
                deadline = time.time() + max(1, args.fill_wait_seconds)
                while time.time() < deadline and len(rows["trades"]) == start_trade_count:
                    time.sleep(0.2)
                latest = _latest_active_order(rows["orders"], vt_orderid)
                if latest and _status_is_active(latest.get("status")):
                    _, _, orderid = vt_orderid.partition(".")
                    cancel_count += 1
                    main_engine.cancel_order(CancelRequest(orderid=orderid, symbol=req.symbol, exchange=req.exchange), "CTP")
                    time.sleep(max(1, args.post_cancel_wait_seconds))
                submitted_rows.append(
                    {
                        "intent_id": row.get("intent_id", ""),
                        "vt_symbol": row.get("vt_symbol", ""),
                        "mode": "live-real",
                        "submit_status": "submitted_to_ctp",
                        "vt_orderid": vt_orderid,
                        "direction": req.direction.value,
                        "offset": req.offset.value,
                        "volume": req.volume,
                        "price": req.price,
                    }
                )
            adapter_status = "adapter_live_real_completed"
        except Exception as exc:
            adapter_status = "adapter_exception"
            blockers.append(repr(exc))
        finally:
            if main_engine is not None:
                try:
                    main_engine.close()
                except Exception as exc:
                    rows["logs"].append(
                        {
                            "received_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "level": "ERROR",
                            "message": f"main_engine.close failed: {exc!r}",
                        }
                    )

    summary = {
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "target_date": args.target_date,
        "mode": args.mode,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "adapter_status": adapter_status,
        "ready_intent_count": int(len(ready)),
        "blocking_failure_count": len(blockers),
        "blockers": blockers,
        "send_order_api_called_count": send_count,
        "cancel_order_api_called_count": cancel_count,
        "order_api_called_count": send_count + cancel_count,
        "outputs": {key: str(value.resolve()) for key, value in paths.items()},
        "judgement": {
            "overfit_before": "否。Stage931 是执行适配器，不改策略参数。",
            "continue_before": "是。全自动开平仓需要最后一层受控 submit adapter。",
            "overfit_after": "否。结果只影响执行证据。",
            "continue_after": "是。上线前必须先有小额 smoke/live gate 证据和 TCA/对账闭环。",
        },
    }
    submitted = pd.DataFrame(submitted_rows)
    submitted.to_csv(paths["submitted_csv"], index=False, encoding="utf-8-sig")
    _write_df(paths["orders_csv"], rows["orders"])
    _write_df(paths["trades_csv"], rows["trades"])
    _write_df(paths["accounts_csv"], rows["accounts"])
    _write_df(paths["positions_csv"], rows["positions"])
    _write_df(paths["logs_csv"], rows["logs"])
    paths["summary_json"].write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths["report_md"].write_text(_build_report(summary, submitted), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
