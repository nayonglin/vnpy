from __future__ import annotations

import argparse
from collections.abc import Callable, Iterator, Mapping
import hashlib
import json
import math
import os
import signal
import sys
import tempfile
import threading
import time
import uuid
from contextlib import contextmanager, nullcontext
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import date, datetime
from pathlib import Path
from threading import Event, Lock, Thread, local
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from qmt_roll_official_execution_profile import (
    C9_15W_PROFILE,
    ExecutionStrategyMode,
    OfficialExecutionProfile,
    resolve_execution_profile,
)
from qmt_roll_official_live_execution_ledger import (
    advance_cancel_duty_state,
    append_post_api_slot_no_native_safe_terminal,
    append_broker_callback_event_once,
    append_pre_api_slot_no_side_effect_terminal,
    append_execution_ledger_event,
    duplicate_blocker,
    ledger_order_api_counts,
    read_execution_ledger,
    reserve_execution_api_slot,
    reserve_execution_api_slots,
    reserve_execution_ledger_intent,
)
from qmt_roll_official_live_execution_service import (
    ExecutionResult,
    ExecutorServicePaths,
    SQLiteIntentSpool,
    TdReadinessLease,
    revoke_readiness,
    serve_executor,
    singleton_executor_lock,
)
from qmt_roll_official_live_authorization_lock import (
    shared_submit_authorization_lock,
    submit_authorization_lock_path,
)
from qmt_roll_official_live_intent_spool import open_spool
from qmt_roll_official_live_submit_authorization import (
    authorized_submit_intent_records,
    read_submit_authorization,
    submit_authorization_path,
    validate_submit_authorization,
)
from qmt_roll_official_live_phase_d_config import (
    KILL_SWITCH_PATH,
    LIVE_EXECUTION_LEDGER_PATH,
    PHASE_D_CONFIRM_TEXT,
    PHASE_D_REAL_ADAPTER_ENV,
    PHASE_D_REAL_ENABLED_ENV,
    READONLY_ORDERS_PATH,
    READONLY_TICKS_PATH,
    build_phase_d_config,
)
from qmt_roll_official_live_c9_intraday_state import (
    INITIAL_STOP_ACTION_ROLE,
    RETRY_OPEN_ACTION_ROLE,
    RETRY_STOP_ACTION_ROLE,
    generate_position_cycle_id,
    generate_root_position_id,
)
from qmt_roll_official_live_email_notify import send_official_live_email_notification
from qmt_roll_official_live_runtime_profile import (
    ExecutionRuntimeProfile,
    OrderScope,
    RuntimeProfileError,
    resolve_runtime_profile,
)
from run_qmt_roll_stage914_official_live_ctp_runtime_preflight import (
    evaluate_stage179_pre_adapter_gate,
)
from run_qmt_alignment_backtest import OUTPUT_DIR
from vnpy.event import EVENT_TIMER, EventEngine
from vnpy.trader.constant import Direction, Exchange, Offset, OrderType
from vnpy.trader.engine import MainEngine
from vnpy.trader.event import EVENT_ACCOUNT, EVENT_LOG, EVENT_ORDER, EVENT_POSITION, EVENT_TICK, EVENT_TRADE
from vnpy.trader.object import CancelRequest, OrderRequest, SubscribeRequest


MODEL_TAG = "stage931_official_live_ctp_submit_adapter_v1"
OUTPUT_PREFIX = "qmt_roll_stage931_official_live_ctp_submit_adapter"
EMAIL_THROTTLE_PATH = OUTPUT_DIR / "qmt_roll_stage931_official_live_email_throttle.json"
STAGE905_MODEL_TAG = "stage905_official_live_executor_dry_run_v1"
STAGE905_PREFIX = "qmt_roll_stage905_official_live_executor_dry_run"
STAGE904_MODEL_TAG = "stage904_official_live_c9_intraday_monitor_v1"
STAGE904_PREFIX = "qmt_roll_stage904_official_live_c9_intraday_monitor"
STAGE902_MODEL_TAG = "stage902_official_live_phase_d_readiness_gate_v1"
STAGE902_PREFIX = "qmt_roll_stage902_official_live_phase_d_readiness_gate"
STAGE927_MODEL_TAG = "stage927_official_live_real_submit_arming_gate_v1"
STAGE927_PREFIX = "qmt_roll_stage927_official_live_real_submit_arming_gate"
ALLOWED_TICK_CLOCK_SKEW_SECONDS = 2.0
MAX_EXACT_FLOAT_INTEGER = 2**53
CTP_QUERY_INTERVAL_SECONDS = 1.1
CTP_DIRECTION_BUY = "0"
CTP_DIRECTION_SELL = "1"
CTP_OFFSET_OPEN = "0"
CTP_OFFSET_CLOSE = "1"
CTP_OFFSET_CLOSE_TODAY = "3"
CTP_OFFSET_CLOSE_YESTERDAY = "4"
CTP_HEDGE_SPECULATION = "1"
CTP_NUMERIC_SENTINEL_FLOOR = sys.float_info.max / 10.0
CTP_ACTIVE_ORDER_STATUSES = {"1", "3", "a", "b", "c"}
CTP_TERMINAL_ORDER_STATUSES = {"0", "2", "4", "5"}
FAK_OPEN_EXCHANGES = {
    Exchange.CFFEX,
    Exchange.SHFE,
    Exchange.INE,
    Exchange.DCE,
    Exchange.CZCE,
    Exchange.GFEX,
}
_ORDER_QUERY_FORWARD_CONTEXT = local()

CTP_ENV_KEYS = ("CTP_USERID", "CTP_PASSWORD", "CTP_BROKERID", "CTP_TD_ADDRESS", "CTP_MD_ADDRESS", "CTP_APPID", "CTP_AUTH_CODE")
ACTIVE_ORDER_STATUSES = {"submitting", "submitted", "not traded", "nottraded", "part traded", "parttraded", "未成交", "提交中", "部分成交"}
TERMINAL_ORDER_STATUSES = {
    "all traded",
    "alltraded",
    "filled",
    "cancelled",
    "canceled",
    "rejected",
    "全部成交",
    "已成交",
    "已撤单",
    "已撤销",
    "撤单",
    "拒单",
    "已拒绝",
    "废单",
}
CANCELLED_ORDER_STATUSES = {
    "cancelled",
    "canceled",
    "已撤单",
    "已撤销",
    "撤单",
}
REJECTED_ORDER_STATUSES = {
    "rejected",
    "拒单",
    "已拒绝",
    "废单",
}
CLOSE_RETRY_AUDIT_VERSION = 1
FINGERPRINT_SCOPED_NONRETRYABLE_CLOSE_BLOCKERS = frozenset(
    {
        "ledger_duplicate_close_intent:filled_or_part_filled",
        "ledger_duplicate_close_intent:close_volume_reconciled_without_trade_detail",
        "ledger_duplicate_close_intent:order_traded_volume_observed_without_trade_detail",
        "ledger_duplicate_close_intent:fill_reconciliation_pending",
        "ledger_duplicate_close_intent:unknown_order_status_after_send",
        "ledger_duplicate_close_intent:residual_order_active_after_cancel",
        "ledger_duplicate_close_intent:residual_order_unknown_after_cancel",
        "ledger_duplicate_close_intent:send_order_side_effect_unknown_after_exception",
        "ledger_duplicate_close_intent:unversioned_or_unknown_submit_attempt",
        "ledger_duplicate_close_intent:known_zero_retry_limit_reached",
        "ledger_duplicate_close_intent:submit_attempt_not_explicit_known_zero",
        "ledger_duplicate_close_intent:known_zero_audit_missing_send_call",
        "ledger_duplicate_close_intent:submit_attempt_after_known_zero_unresolved",
        "ledger_duplicate_close_intent:known_zero_retry_timestamp_missing",
        "ledger_duplicate_close_intent:send_order_called",
        "ledger_duplicate_close_intent:send_order_returned_empty",
        "ledger_duplicate_close_intent:rejected_or_inactive",
        "ledger_duplicate_close_intent:api_slot_reserved",
    }
)
LEDGER_METADATA_FIELDS = (
    "root_position_id",
    "position_epoch_id",
    "position_cycle_id",
    "position_cycle_no",
    "parent_position_cycle_id",
    "parent_intent_fingerprint",
    "intent_role",
    "position_direction",
    "entry_risk_date",
    "open_trade_id",
    "strategy_entry_price",
    "strategy_initial_stop_price",
    "strategy_stop_price",
    "retry_trigger_price",
    "retry_stop_price",
    "retry_original_fill_price",
    "root_entry_price",
    "root_initial_stop_price",
    "root_entry_volume",
    "action_id",
    "logical_close_root_id",
    "prior_close_terminal_checksum",
    "close_execution_attempt_no",
    "manual_intervention_required",
    "risk_alert_level",
    "migration_blocker",
    "recommended_operator_action",
    "stage904_monitor_status",
    "stage904_summary_generated_at",
)

STAGE904_ONLY_INTENT_FIELDS = (
    "action_id",
    "logical_close_root_id",
    "prior_close_terminal_checksum",
    "close_execution_attempt_no",
    "monitor_run_id",
    "manual_intervention_required",
    "risk_alert_level",
    "migration_blocker",
    "recommended_operator_action",
    "stage904_monitor_status",
    "stage904_summary_generated_at",
    "entry_risk_date",
    "open_trade_id",
    "parent_position_cycle_id",
    "parent_intent_fingerprint",
    "retry_trigger_price",
    "retry_stop_price",
    "retry_original_fill_price",
    "strategy_stop_price",
    "stop_trigger_price",
    "trigger_price",
    "triggered_at",
)


def _intent_ledger_metadata(row: dict[str, Any]) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    for key in LEDGER_METADATA_FIELDS:
        value = row.get(key)
        if value is None:
            continue
        if isinstance(value, float) and pd.isna(value):
            continue
        if str(value).strip() == "":
            continue
        metadata[key] = value
    return metadata


def _paths(target_date: str) -> dict[str, Path]:
    key = target_date.replace("-", "") if target_date else "latest"
    return {
        "summary_json": OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{key}_{MODEL_TAG}.json",
        "orders_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_orders_{key}_{MODEL_TAG}.csv",
        "trades_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_trades_{key}_{MODEL_TAG}.csv",
        "accounts_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_accounts_{key}_{MODEL_TAG}.csv",
        "positions_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_positions_{key}_{MODEL_TAG}.csv",
        "logs_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_logs_{key}_{MODEL_TAG}.csv",
        "ticks_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_ticks_{key}_{MODEL_TAG}.csv",
        "submitted_csv": OUTPUT_DIR / f"{OUTPUT_PREFIX}_submitted_{key}_{MODEL_TAG}.csv",
        "report_md": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{key}_{MODEL_TAG}.md",
    }


def _stage905_intents_path(target_date: str) -> Path:
    key = target_date.replace("-", "") if target_date else "latest"
    return OUTPUT_DIR / f"{STAGE905_PREFIX}_intents_{key}_{STAGE905_MODEL_TAG}.csv"


def _stage905_summary_path(target_date: str) -> Path:
    key = target_date.replace("-", "") if target_date else "latest"
    return OUTPUT_DIR / f"{STAGE905_PREFIX}_summary_{key}_{STAGE905_MODEL_TAG}.json"


def _stage904_summary_path(target_date: str) -> Path:
    key = target_date.replace("-", "") if target_date else "latest"
    return OUTPUT_DIR / f"{STAGE904_PREFIX}_summary_{key}_{STAGE904_MODEL_TAG}.json"


def _stage902_summary_path(target_date: str) -> Path:
    key = target_date.replace("-", "") if target_date else "latest"
    return OUTPUT_DIR / f"{STAGE902_PREFIX}_summary_{key}_{STAGE902_MODEL_TAG}.json"


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


def _kill_switch_blockers(path: Path = KILL_SWITCH_PATH) -> list[str]:
    payload = _read_json(path)
    if payload.get("_read_error"):
        return ["kill_switch_unreadable"]
    if bool(
        payload.get("enabled", False)
        or payload.get("kill_switch_active", False)
    ):
        return ["kill_switch_active"]
    return []


def _read_csv_maybe(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, encoding="utf-8-sig")
    except Exception:
        return pd.DataFrame()


def _env_enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _parse_dt(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _age_seconds(value: Any) -> float | None:
    parsed = _parse_dt(value)
    if parsed is None:
        return None
    return max(0.0, (datetime.now() - parsed).total_seconds())


def _to_int(value: Any, default: int = 0) -> int:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return default
    return int(number)


def _to_float(value: Any, default: float = 0.0) -> float:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return default
    return float(number)


def _canonical_binary_flag(value: Any) -> tuple[bool, int]:
    """Accept only numeric 0/1; strings/bools cannot grant execution authority."""

    if value is None or pd.api.types.is_bool(value) or isinstance(value, str):
        return False, 0
    try:
        if bool(pd.isna(value)):
            return False, 0
        number = float(value)
    except (TypeError, ValueError):
        return False, 0
    if not math.isfinite(number) or number not in {0.0, 1.0}:
        return False, 0
    return True, int(number)


def _canonical_binary_flag_series(values: pd.Series) -> tuple[pd.Series, pd.Series]:
    parsed = values.map(_canonical_binary_flag)
    valid = parsed.map(lambda item: bool(item[0]))
    enabled = parsed.map(lambda item: bool(item[0] and item[1] == 1))
    return valid, enabled


def _file_age_seconds(path: Path) -> float | None:
    if not path.exists():
        return None
    return max(0.0, time.time() - path.stat().st_mtime)


def _readonly_order_snapshot_diagnostic(
    age_seconds: float | None,
    *,
    max_age_seconds: float,
) -> dict[str, Any]:
    """Describe legacy Stage174 evidence without granting it send authority."""

    return {
        "readonly_order_snapshot_age_seconds": age_seconds,
        "readonly_order_snapshot_confirmed": int(
            age_seconds is not None and age_seconds <= max_age_seconds
        ),
        "readonly_order_snapshot_authoritative_for_send": 0,
        "readonly_order_snapshot_role": "diagnostic_only_final_opo_is_authoritative",
    }


def _target_age_days(target_date: str) -> int | None:
    try:
        return (date.today() - datetime.strptime(target_date, "%Y-%m-%d").date()).days
    except ValueError:
        return None


def _current_phase_d_sessions() -> list[dict[str, str]]:
    config = build_phase_d_config()
    now = datetime.now().time()
    active: list[dict[str, str]] = []
    for session in config.sessions:
        start_h, start_m = [int(part) for part in session.start.split(":", 1)]
        end_h, end_m = [int(part) for part in session.end.split(":", 1)]
        start = now.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
        end = now.replace(hour=end_h, minute=end_m, second=0, microsecond=0)
        in_session = start <= now <= end if start <= end else now >= start or now <= end
        if in_session:
            active.append({"name": session.name, "role": session.role})
    return active


def _minute_of_day(now: datetime | None = None) -> int:
    current = now or datetime.now()
    return current.hour * 60 + current.minute


def _continuous_submit_blockers(now: datetime | None = None) -> list[str]:
    minute = _minute_of_day(now)
    blocked_windows = [
        ("night_open_auction_2055_2100", 20 * 60 + 55, 21 * 60),
        ("day_open_auction_0855_0900", 8 * 60 + 55, 9 * 60),
        ("day_mid_break_1015_1030", 10 * 60 + 15, 10 * 60 + 30),
        ("day_lunch_break_1130_1330", 11 * 60 + 30, 13 * 60 + 30),
        ("day_close_buffer_1500_1510", 15 * 60, 15 * 60 + 10),
    ]
    return [f"live_real_not_continuous_auction_or_break:{name}" for name, start, end in blocked_windows if start <= minute < end]


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


def _stage179_callback_key(kind: str, payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        {key: payload[key] for key in sorted(payload)},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return f"stage179-{kind}-" + hashlib.sha256(encoded).hexdigest()


def _stage179_warm_callback_base(
    context: Mapping[str, Any],
    callback: Mapping[str, Any],
) -> dict[str, Any]:
    row = dict(context.get("row", {}))
    request = context.get("request")
    direction = _normalize_direction_text(
        callback.get("direction")
        or row.get("direction")
        or getattr(getattr(request, "direction", None), "value", "")
    )
    offset = _normalize_offset_text(
        callback.get("offset")
        or row.get("offset")
        or getattr(getattr(request, "offset", None), "value", "")
    )
    return {
        "target_date": str(context.get("target_date", "")),
        "intent_id": str(context.get("intent_id", "")),
        "intent_payload_sha256": str(
            context.get("intent_payload_sha256", "")
        ),
        "intent_kind": str(context.get("intent_kind", offset)),
        "intent_fingerprint": str(context.get("fingerprint", "")),
        "parent_intent_fingerprint": str(context.get("fingerprint", "")),
        "vt_symbol": str(callback.get("vt_symbol") or row.get("vt_symbol") or ""),
        "direction": direction,
        "offset": offset,
        "source": str(row.get("source", "")),
        "adapter": "Stage931Warm",
        "service_generation": str(context.get("service_generation", "")),
        "connection_generation": str(context.get("connection_generation", "")),
        "spool_lease_owner": str(context.get("spool_lease_owner", "")),
        "spool_lease_token": str(context.get("spool_lease_token", "")),
        "child_order_id": str(context.get("child_order_id", "")),
        "child_order_index": int(context.get("child_order_index", 0) or 0),
        "child_order_count": int(context.get("child_order_count", 1) or 1),
        "close_submit_attempt_no": int(
            context.get("close_submit_attempt_no", 0) or 0
        ),
        "close_attempt_lease_token": str(
            context.get("close_attempt_lease_token", "")
        ),
        **_intent_ledger_metadata(row),
    }


def _persist_stage179_warm_broker_callback(
    *,
    kind: str,
    callback: Mapping[str, Any],
    context: Mapping[str, Any] | None,
    target_date: str,
    ledger_path: Path,
) -> list[dict[str, Any]]:
    """Normalize durable broker evidence without inferring fills from position."""

    vt_orderid = str(callback.get("vt_orderid", "") or "").strip()
    vt_symbol = str(callback.get("vt_symbol", "") or "").strip()
    if context is None:
        raw_identity = {
            "target_date": target_date,
            "kind": kind,
            "vt_orderid": vt_orderid,
            "vt_tradeid": str(callback.get("vt_tradeid", "") or ""),
            "tradeid": str(callback.get("tradeid", "") or ""),
            "status": str(callback.get("status", "") or ""),
            "traded": _to_float(callback.get("traded"), 0.0),
            "volume": _to_float(callback.get("volume"), 0.0),
            "price": _to_float(callback.get("price"), 0.0),
            "vt_symbol": vt_symbol,
            "exchange": str(callback.get("exchange", "") or ""),
            "datetime": str(callback.get("datetime", "") or ""),
            "broker_trade_at": str(
                callback.get("broker_trade_at")
                or callback.get("datetime")
                or ""
            ),
        }
        event = {
            "event_type": f"broker_{kind}_callback_unbound",
            **raw_identity,
            "broker_callback_key": _stage179_callback_key(
                f"{kind}-unbound", raw_identity
            ),
            "execution_inference_authority": "none_until_intent_bound",
        }
        return [append_broker_callback_event_once(event, ledger_path)]

    base = _stage179_warm_callback_base(context, callback)
    results: list[dict[str, Any]] = []
    if kind == "trade":
        vt_tradeid = str(callback.get("vt_tradeid", "") or "").strip()
        tradeid = str(callback.get("tradeid", "") or "").strip()
        exchange = str(callback.get("exchange", "") or "").strip() or (
            vt_symbol.rpartition(".")[2] if "." in vt_symbol else ""
        )
        price = _to_float(callback.get("price"), 0.0)
        volume = _to_float(callback.get("volume"), 0.0)
        if not tradeid and vt_tradeid.startswith("CTP."):
            tradeid = vt_tradeid[len("CTP.") :].split(".")[-1]
        trade_identity = (
            f"ctp:{exchange}:{tradeid}"
            if exchange and tradeid
            else vt_tradeid
        )
        identity = {
            "target_date": base.get("target_date", target_date),
            "intent_fingerprint": base.get("intent_fingerprint", ""),
            "child_order_id": base.get("child_order_id", ""),
            "vt_orderid": vt_orderid,
            "trade_identity": trade_identity,
        }
        confirmed = bool(vt_orderid and trade_identity and price > 0 and volume > 0)
        event = {
            "event_type": (
                "filled_or_part_filled"
                if confirmed
                else "broker_trade_callback_unidentified"
            ),
            **base,
            "vt_orderid": vt_orderid,
            "vt_tradeid": vt_tradeid,
            "tradeid": tradeid,
            "trade_fill_key": trade_identity,
            "price": price,
            "volume": volume,
            "trade_volume_delta": volume if confirmed else 0.0,
            "trade_event_volume_delta": volume if confirmed else 0.0,
            "trade_event_priced_volume_delta": volume if confirmed else 0.0,
            "trade_rows_delta": 1 if confirmed else 0,
            "fill_price_source": "event_trade_weighted_avg",
            "broker_callback_adapter": "stage931_warm_event_trade",
            "broker_callback_key": _stage179_callback_key("trade", identity),
            "broker_fill_confirmed": int(confirmed),
        }
        broker_trade_at = str(
            callback.get("broker_trade_at")
            or callback.get("datetime")
            or ""
        ).strip()
        if broker_trade_at:
            event["broker_trade_at"] = broker_trade_at
            event["generated_at"] = broker_trade_at
        results.append(append_broker_callback_event_once(event, ledger_path))
        return results

    if kind == "position":
        identity = {
            "target_date": base.get("target_date", target_date),
            "connection_generation": base.get("connection_generation", ""),
            "vt_symbol": vt_symbol,
            "direction": str(callback.get("direction", "")),
            "volume": _to_float(callback.get("volume"), 0.0),
            "yd_volume": _to_float(callback.get("yd_volume"), 0.0),
            "price": _to_float(callback.get("price"), 0.0),
        }
        event = {
            "event_type": "broker_position_callback_observed",
            **base,
            **identity,
            "broker_callback_key": _stage179_callback_key("position", identity),
            "execution_inference_authority": "diagnostic_only_not_fill",
        }
        results.append(append_broker_callback_event_once(event, ledger_path))
        return results

    status = str(callback.get("status", "") or "").strip().lower()
    traded = _to_float(callback.get("traded"), 0.0)
    order_volume = _to_float(callback.get("volume"), 0.0)
    order_identity = {
        "target_date": base.get("target_date", target_date),
        "intent_fingerprint": base.get("intent_fingerprint", ""),
        "child_order_id": base.get("child_order_id", ""),
        "vt_orderid": vt_orderid,
        "status": status,
        "traded": traded,
        "volume": order_volume,
    }
    status_class = (
        "local_api_accepted"
        if status in {"submitting", "提交中"}
        else "broker_rejected"
        if status in REJECTED_ORDER_STATUSES
        else "broker_cancelled"
        if status in CANCELLED_ORDER_STATUSES
        else "broker_all_traded"
        if status in {"all traded", "alltraded", "全部成交", "已成交"}
        else "broker_part_traded"
        if status in {"part traded", "parttraded", "部分成交"}
        else "broker_acknowledged"
    )
    event = {
        "event_type": "broker_order_status_observed",
        **base,
        **order_identity,
        "broker_order_status_class": status_class,
        "broker_acknowledged": int(status_class != "local_api_accepted"),
        "broker_callback_key": _stage179_callback_key("order", order_identity),
    }
    results.append(append_broker_callback_event_once(event, ledger_path))
    if status_class in {"broker_rejected", "broker_cancelled"}:
        request = context.get("request")
        if isinstance(request, OrderRequest):
            trade_total = _to_float(
                context.get("trade_event_total_volume"), 0.0
            )
            priced_total = _to_float(
                context.get("trade_event_priced_volume"), 0.0
            )
            unpriced_volume = max(0.0, traded - priced_total)
            residual_volume = max(
                0.0,
                float(request.volume) - max(traded, trade_total),
            )
            terminal = {
                "event_type": "rejected_or_inactive",
                **base,
                **order_identity,
                "broker_order_status_class": status_class,
                "volume": float(request.volume),
                "broker_callback_key": _stage179_callback_key(
                    "order-terminal-zero-audit", order_identity
                ),
                **_close_retry_terminal_audit_fields(
                    req=request,
                    context=dict(context),
                    insert_audit=dict(context.get("insert_audit", {})),
                    vt_orderid=vt_orderid,
                    latest_order=dict(callback),
                    order_traded_volume=traded,
                    trade_event_total_volume=trade_total,
                    trade_event_priced_volume=priced_total,
                    unpriced_volume=unpriced_volume,
                    residual_volume=residual_volume,
                    trade_callback_count=int(
                        context.get("trade_callback_count", 0) or 0
                    ),
                ),
            }
            results.append(
                append_broker_callback_event_once(terminal, ledger_path)
            )
    if traded > 0:
        unpriced = {
            "event_type": "order_traded_volume_observed_without_trade_detail",
            **base,
            **order_identity,
            "order_traded_volume": traded,
            "unpriced_volume": traded,
            "residual_volume": max(0.0, order_volume - traded),
            "fill_price_reconciliation_pending": 1,
            "broker_callback_key": _stage179_callback_key(
                "order-unpriced-fill", order_identity
            ),
        }
        results.append(append_broker_callback_event_once(unpriced, ledger_path))
    return results


TICK_INGRESS_MONOTONIC_ATTR = "_stage931_tick_ingress_monotonic"


def _stamp_tick_before_event_enqueue(
    tick: Any,
    *,
    monotonic: Callable[[], float] = time.monotonic,
) -> Any:
    """Stamp market-data ingress before BaseGateway enqueues EVENT_TICK."""

    setattr(tick, TICK_INGRESS_MONOTONIC_ATTR, float(monotonic()))
    return tick


def _tick_event_row(
    tick: Any,
    *,
    monotonic: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    """Preserve ingress time; handler time is diagnostic only.

    EventEngine is single-threaded and can be backlogged.  Dating a tick when
    this consumer runs would let a pre-Q2 event masquerade as post-Q2.
    """

    row = _object_to_row(tick)
    ingress = pd.to_numeric(
        getattr(tick, TICK_INGRESS_MONOTONIC_ATTR, None), errors="coerce"
    )
    row["received_monotonic"] = "" if pd.isna(ingress) else float(ingress)
    row["handler_received_monotonic"] = float(monotonic())
    return row


def _log_messages(rows: list[dict[str, Any]]) -> list[str]:
    messages: list[str] = []
    for row in rows:
        for key in ("msg", "message", "value"):
            text = str(row.get(key, "")).strip()
            if text:
                messages.append(text)
    return messages


@dataclass
class CtpReadinessState:
    """State owned by one Stage931 cold CTP connection attempt."""

    account_required: bool
    started_monotonic: float = 0.0
    deadline_monotonic: float = 0.0
    elapsed_seconds: float = 0.0
    expected_account_reqid: int | None = None
    expected_position_reqid: int | None = None
    account_query_attempts: list[dict[str, Any]] = field(default_factory=list)
    position_query_attempts: list[dict[str, Any]] = field(default_factory=list)
    fatal_error: str = ""

    def to_summary(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BrokerSendBatchResult:
    order_ids: tuple[str, ...]
    send_order_call_count: int


class BrokerSendBatchError(RuntimeError):
    def __init__(self, message: str, *, send_order_call_count: int) -> None:
        super().__init__(message)
        self.send_order_call_count = max(0, int(send_order_call_count))


class CtpExecutionSession:
    """Generation-bound owner of one warm CTP transport.

    Connection setup is intentionally injected.  The production builder owns
    vn.py/CTP construction, while this lifecycle object enforces the same
    readiness generation and absolute-deadline rules in both production and
    deterministic tests.
    """

    def __init__(
        self,
        *,
        runtime: Any,
        service_generation: str,
        official_version: str,
        capital: float,
        readiness_ttl_seconds: float,
        connect_startup_bundle: Callable[[], dict[str, Any]],
        disconnect_transport: Callable[[], None],
        fresh_bundle: Callable[[Any, float], Any],
        reserve_api_slot: Callable[[Any], str],
        send_order: Callable[[Any], Any],
        revoke_readiness: Callable[[str], None] | None = None,
        transport_probe: Callable[[], list[str]] | None = None,
        pre_api_slot_blockers: Callable[[Any], list[str]] | None = None,
        pre_api_slot_safe_terminal: (
            Callable[[Any, list[str], str], dict[str, Any]] | None
        ) = None,
        post_api_slot_safe_terminal: (
            Callable[[Any, str, list[str], str], dict[str, Any]] | None
        ) = None,
        pre_lease_blockers: Callable[[], list[str]] | None = None,
        pre_lease_authorized_intents: (
            Callable[[], Mapping[str, str] | None] | None
        ) = None,
        lease_execution_guard: Callable[[], Any] | None = None,
        post_lease_blockers: Callable[[Any], list[str]] | None = None,
        connection_generation_observer: Callable[[str], None] | None = None,
        epoch_ns: Callable[[], int] = time.time_ns,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        if readiness_ttl_seconds <= 0:
            raise ValueError("stage179_readiness_ttl_must_be_positive")
        self.runtime = runtime
        self.service_generation = str(service_generation)
        self.official_version = str(official_version)
        self.capital = float(capital)
        self.readiness_ttl_seconds = float(readiness_ttl_seconds)
        self._connect_startup_bundle = connect_startup_bundle
        self._disconnect_transport = disconnect_transport
        self._revoke_readiness = revoke_readiness or (lambda _: None)
        self._transport_probe = transport_probe or (lambda: [])
        self._fresh_bundle = fresh_bundle
        self._reserve_api_slot = reserve_api_slot
        self._send_order = send_order
        self._pre_api_slot_blockers = pre_api_slot_blockers or (lambda _: [])
        self._pre_api_slot_safe_terminal = pre_api_slot_safe_terminal
        self._post_api_slot_safe_terminal = post_api_slot_safe_terminal
        self._pre_lease_blockers = pre_lease_blockers or (lambda: [])
        self._pre_lease_authorized_intents = pre_lease_authorized_intents
        self._lease_execution_guard = lease_execution_guard
        self._post_lease_blockers = post_lease_blockers or (lambda _: [])
        self._connection_generation_observer = (
            connection_generation_observer or (lambda _: None)
        )
        self._epoch_ns = epoch_ns
        self._monotonic = monotonic
        self._connected = False
        self._connection_generation = ""
        self._last_complete_startup_bundle_epoch_ns = 0
        self._lifecycle_lock = Lock()
        self.api_slot_call_count = 0
        self.send_order_call_count = 0

    @classmethod
    def for_callbacks(cls, **kwargs: Any) -> CtpExecutionSession:
        return cls(**kwargs)

    @property
    def connection_generation(self) -> str:
        with self._lifecycle_lock:
            return self._connection_generation

    def connect(self) -> None:
        with self._lifecycle_lock:
            if self._connected:
                return
            startup = self._connect_startup_bundle()
            if not isinstance(startup, dict) or startup.get("ready") is not True:
                try:
                    self._revoke_readiness("ctp_startup_bundle_not_ready")
                finally:
                    self._disconnect_transport()
                raise RuntimeError("stage179_ctp_startup_bundle_not_ready")
            self._connection_generation = uuid.uuid4().hex
            self._connection_generation_observer(self._connection_generation)
            self._last_complete_startup_bundle_epoch_ns = int(self._epoch_ns())
            self._connected = True

    def _revoke_in_memory(self) -> bool:
        with self._lifecycle_lock:
            was_connected = self._connected
            self._connected = False
            self._connection_generation = ""
            self._connection_generation_observer("")
            self._last_complete_startup_bundle_epoch_ns = 0
            return was_connected

    def disconnect(self) -> None:
        was_connected = self._revoke_in_memory()
        if was_connected:
            try:
                self._revoke_readiness("ctp_session_disconnected")
            finally:
                self._disconnect_transport()

    def reconnect(self) -> None:
        self.disconnect()
        self.connect()

    def close(self) -> None:
        self.disconnect()

    def readiness_lease(self, *, now_epoch_ns: int) -> TdReadinessLease:
        with self._lifecycle_lock:
            if not self._connected or not self._connection_generation:
                raise RuntimeError("stage179_ctp_readiness_revoked")
            issued = int(now_epoch_ns)
            ttl_ns = int(self.readiness_ttl_seconds * 1_000_000_000)
            profile = getattr(getattr(self.runtime, "profile", ""), "value", "")
            return TdReadinessLease(
                service_generation=self.service_generation,
                connection_generation=self._connection_generation,
                runtime_profile=str(profile),
                official_version=self.official_version,
                capital=self.capital,
                issued_epoch_ns=issued,
                expires_epoch_ns=issued + ttl_ns,
                last_complete_startup_bundle_epoch_ns=(
                    self._last_complete_startup_bundle_epoch_ns
                ),
            )

    def transport_blockers(self) -> list[str]:
        blockers: list[str] = []
        with self._lifecycle_lock:
            if not self._connected or not self._connection_generation:
                blockers.append("stage179_ctp_transport_not_connected")
        try:
            blockers.extend(self._transport_probe())
        except BaseException as exc:
            blockers.append(
                f"stage179_ctp_transport_probe_exception:{type(exc).__name__}"
            )
        return list(dict.fromkeys(str(item) for item in blockers if str(item)))

    @staticmethod
    def _bundle_blockers(bundle: Any) -> list[str]:
        if bundle is None:
            return []
        if isinstance(bundle, dict):
            return [str(item) for item in bundle.get("blockers", []) if str(item)]
        if isinstance(bundle, (list, tuple)):
            return [str(item) for item in bundle if str(item)]
        raise RuntimeError("stage179_fresh_bundle_result_invalid")

    def _deadline_blocker(self, phase: str, hard_deadline_monotonic: float) -> str:
        if self._monotonic() >= hard_deadline_monotonic:
            return f"stage179_execution_deadline_exceeded:{phase}"
        return ""

    def _readiness_blockers(
        self,
        readiness: TdReadinessLease,
        *,
        check_expiry: bool = True,
    ) -> list[str]:
        now_epoch = int(self._epoch_ns())
        with self._lifecycle_lock:
            current_generation = self._connection_generation
            connected = self._connected
        blockers: list[str] = []
        if not connected:
            blockers.append("stage179_readiness_revoked")
        if readiness.service_generation != self.service_generation:
            blockers.append("stage179_readiness_service_generation_mismatch")
        if readiness.connection_generation != current_generation:
            blockers.append("stage179_readiness_connection_generation_mismatch")
        if check_expiry and now_epoch >= readiness.expires_epoch_ns:
            blockers.append("stage179_readiness_lease_expired")
        profile = getattr(getattr(self.runtime, "profile", ""), "value", "")
        if readiness.runtime_profile != str(profile):
            blockers.append("stage179_readiness_runtime_profile_mismatch")
        blockers.extend(self.transport_blockers())
        return list(dict.fromkeys(blockers))

    def pre_lease_blockers(self) -> list[str]:
        try:
            return list(
                dict.fromkeys(
                    str(item)
                    for item in self._pre_lease_blockers()
                    if str(item)
                )
            )
        except BaseException as exc:
            return [
                "stage179_pre_lease_authorization_exception:"
                f"{type(exc).__name__}"
            ]

    def pre_lease_authorized_intents(self) -> Mapping[str, str] | None:
        if self._pre_lease_authorized_intents is None:
            return None
        try:
            result = self._pre_lease_authorized_intents()
        except BaseException:
            return {}
        if result is None:
            return None
        return {
            str(intent_id): str(payload_sha256)
            for intent_id, payload_sha256 in result.items()
        }

    @contextmanager
    def lease_execution_guard(self) -> Iterator[None]:
        guard = self._lease_execution_guard
        if guard is None:
            yield
            return
        with guard():
            yield

    def post_lease_blockers(self, lease: Any) -> list[str]:
        try:
            return list(
                dict.fromkeys(
                    str(item)
                    for item in self._post_lease_blockers(lease)
                    if str(item)
                )
            )
        except BaseException as exc:
            return [
                "stage179_post_lease_authorization_exception:"
                f"{type(exc).__name__}"
            ]

    def execute_with_readiness(
        self,
        *,
        readiness: TdReadinessLease,
        lease: Any,
        hard_deadline_monotonic: float,
        api_slot_durable: Callable[[str], bool] | None = None,
    ) -> ExecutionResult:
        intent_id = str(lease.intent.intent_id)

        post_lease_blockers = self.post_lease_blockers(lease)
        if post_lease_blockers:
            return ExecutionResult.blocked(intent_id, post_lease_blockers[0])

        def terminalize_before_api_slot(
            current_blockers: list[str],
            *,
            phase: str,
            ledger_fingerprint: str,
        ) -> ExecutionResult:
            normalized = list(
                dict.fromkeys(str(item) for item in current_blockers if str(item))
            )
            if not ledger_fingerprint or self._pre_api_slot_safe_terminal is None:
                return ExecutionResult.blocked(
                    intent_id,
                    normalized[0] if normalized else "stage179_pre_api_slot_blocked",
                )
            try:
                terminal = self._pre_api_slot_safe_terminal(
                    lease,
                    normalized,
                    phase,
                )
            except BaseException as exc:
                return ExecutionResult(
                    intent_id=intent_id,
                    disposition="blocked",
                    ledger_fingerprint=ledger_fingerprint,
                    api_slot_batch_id="",
                    blockers=(
                        "stage179_pre_api_safe_terminal_exception:"
                        f"{type(exc).__name__}",
                    ),
                    send_order_call_count=0,
                    cancel_order_call_count=0,
                )
            if bool(terminal.get("appended")) or bool(
                terminal.get("idempotent_replay")
            ):
                return ExecutionResult.no_side_effect_retryable(
                    intent_id,
                    ledger_fingerprint=ledger_fingerprint,
                    blockers=normalized,
                )
            return ExecutionResult(
                intent_id=intent_id,
                disposition="blocked",
                ledger_fingerprint=ledger_fingerprint,
                api_slot_batch_id="",
                blockers=(
                    "stage179_pre_api_safe_terminal_failed:"
                    f"{terminal.get('blocker') or 'unknown'}",
                ),
                send_order_call_count=0,
                cancel_order_call_count=0,
            )

        def terminalize_after_api_slot(
            current_blockers: list[str],
            *,
            phase: str,
            ledger_fingerprint: str,
            api_slot_batch_id: str,
        ) -> ExecutionResult:
            normalized = list(dict.fromkeys(str(item) for item in current_blockers if str(item)))
            if self._post_api_slot_safe_terminal is None:
                return ExecutionResult(
                    intent_id=intent_id,
                    disposition="side_effect_unknown",
                    ledger_fingerprint=ledger_fingerprint,
                    api_slot_batch_id=api_slot_batch_id,
                    blockers=tuple(normalized),
                    send_order_call_count=0,
                    cancel_order_call_count=0,
                )
            terminal = self._post_api_slot_safe_terminal(
                lease, api_slot_batch_id, normalized, phase
            )
            if terminal.get("appended") or terminal.get("idempotent_replay"):
                return ExecutionResult.post_slot_no_native_retryable(
                    intent_id,
                    ledger_fingerprint=ledger_fingerprint,
                    api_slot_batch_id=api_slot_batch_id,
                    blockers=normalized,
                    safe_terminal_record_checksum=str(
                        dict(terminal.get("ledger_event", {})).get(
                            "record_checksum", ""
                        )
                    ),
                )
            return ExecutionResult(
                intent_id=intent_id,
                disposition="side_effect_unknown",
                ledger_fingerprint=ledger_fingerprint,
                api_slot_batch_id=api_slot_batch_id,
                blockers=(
                    f"stage179_post_slot_safe_terminal_failed:{terminal.get('blocker') or 'unknown'}",
                ),
                send_order_call_count=0,
                cancel_order_call_count=0,
            )

        blockers = self._readiness_blockers(readiness)
        if blockers:
            return ExecutionResult.blocked(intent_id, blockers[0])
        deadline = self._deadline_blocker("fresh_bundle", hard_deadline_monotonic)
        if deadline:
            return ExecutionResult.blocked(intent_id, deadline)

        bundle = self._fresh_bundle(lease, hard_deadline_monotonic)
        ledger_fingerprint = (
            str(bundle.get("ledger_fingerprint", ""))
            if isinstance(bundle, dict)
            else ""
        )
        blockers = self._bundle_blockers(bundle)
        blockers.extend(self._readiness_blockers(readiness, check_expiry=False))
        deadline = self._deadline_blocker("post_fresh_bundle", hard_deadline_monotonic)
        if deadline:
            blockers.append(deadline)
        blockers = list(dict.fromkeys(blockers))
        if blockers:
            return terminalize_before_api_slot(
                blockers,
                phase="post_fresh_bundle",
                ledger_fingerprint=ledger_fingerprint,
            )

        blockers = list(self._pre_api_slot_blockers(lease))
        deadline = self._deadline_blocker("pre_api_slot", hard_deadline_monotonic)
        if deadline:
            blockers.append(deadline)
        blockers.extend(self._readiness_blockers(readiness, check_expiry=False))
        blockers = list(dict.fromkeys(str(item) for item in blockers if str(item)))
        if blockers:
            return terminalize_before_api_slot(
                blockers,
                phase="pre_api_slot",
                ledger_fingerprint=ledger_fingerprint,
            )

        api_slot_batch_id = ""
        send_called = 0
        try:
            self.api_slot_call_count += 1
            api_slot_batch_id = str(self._reserve_api_slot(lease))
            if not api_slot_batch_id:
                return terminalize_before_api_slot(
                    ["stage179_api_slot_reservation_failed"],
                    phase="api_slot_reservation_failed",
                    ledger_fingerprint=ledger_fingerprint,
                )
            if api_slot_durable is not None and not api_slot_durable(
                api_slot_batch_id
            ):
                return ExecutionResult(
                    intent_id=intent_id,
                    disposition="side_effect_unknown",
                    ledger_fingerprint=ledger_fingerprint,
                    api_slot_batch_id=api_slot_batch_id,
                    blockers=("stage179_spool_sending_cas_lost_after_api_slot",),
                    send_order_call_count=0,
                    cancel_order_call_count=0,
                )
            post_slot_blockers = self._readiness_blockers(
                readiness,
                check_expiry=False,
            )
            if post_slot_blockers:
                return terminalize_after_api_slot(
                    post_slot_blockers,
                    phase="post_api_slot_readiness",
                    ledger_fingerprint=ledger_fingerprint,
                    api_slot_batch_id=api_slot_batch_id,
                )
            deadline = self._deadline_blocker("pre_send_order", hard_deadline_monotonic)
            if deadline:
                return terminalize_after_api_slot(
                    [deadline],
                    phase="pre_send_order_deadline",
                    ledger_fingerprint=ledger_fingerprint,
                    api_slot_batch_id=api_slot_batch_id,
                )
            raw_send_result = self._send_order(lease)
            if isinstance(raw_send_result, BrokerSendBatchResult):
                order_ids = tuple(str(item) for item in raw_send_result.order_ids)
                send_called = int(raw_send_result.send_order_call_count)
            else:
                order_ids = (str(raw_send_result or ""),)
                send_called = 1
            self.send_order_call_count += send_called
        except BaseException as exc:
            send_called = max(
                send_called,
                int(getattr(exc, "send_order_call_count", 0) or 0),
            )
            self.send_order_call_count += send_called
            if not api_slot_batch_id and send_called == 0:
                return terminalize_before_api_slot(
                    [f"stage179_execution_exception:{type(exc).__name__}"],
                    phase="api_slot_reservation_exception",
                    ledger_fingerprint=ledger_fingerprint,
                )
            if api_slot_batch_id and send_called == 0:
                return terminalize_after_api_slot(
                    [f"stage179_execution_exception:{type(exc).__name__}"],
                    phase="child_blocked_before_native_insert",
                    ledger_fingerprint=ledger_fingerprint,
                    api_slot_batch_id=api_slot_batch_id,
                )
            return ExecutionResult(
                intent_id=intent_id,
                disposition="side_effect_unknown" if api_slot_batch_id else "blocked",
                ledger_fingerprint=ledger_fingerprint,
                api_slot_batch_id=api_slot_batch_id,
                blockers=(f"stage179_execution_exception:{type(exc).__name__}",),
                send_order_call_count=send_called,
                cancel_order_call_count=0,
            )
        if send_called <= 0 or not order_ids or any(not item for item in order_ids):
            return ExecutionResult(
                intent_id=intent_id,
                disposition="side_effect_unknown",
                ledger_fingerprint=ledger_fingerprint,
                api_slot_batch_id=api_slot_batch_id,
                blockers=("stage179_send_order_returned_empty",),
                send_order_call_count=send_called,
                cancel_order_call_count=0,
            )
        return ExecutionResult(
            intent_id=intent_id,
            disposition="sent",
            ledger_fingerprint=ledger_fingerprint,
            api_slot_batch_id=api_slot_batch_id,
            blockers=(),
            send_order_call_count=send_called,
            cancel_order_call_count=0,
        )

    def execute_spool_lease(
        self,
        *,
        lease: Any,
        hard_deadline_monotonic: float,
        api_slot_durable: Callable[[str], bool] | None = None,
    ) -> ExecutionResult:
        return self.execute_with_readiness(
            readiness=self.readiness_lease(now_epoch_ns=int(self._epoch_ns())),
            lease=lease,
            hard_deadline_monotonic=hard_deadline_monotonic,
            api_slot_durable=api_slot_durable,
        )


def _callback_result(
    callback_rows: list[dict[str, Any]],
    expected_reqid: int | None,
    *,
    require_account_id: bool = False,
) -> dict[str, Any]:
    if expected_reqid is None:
        return {
            "matching_count": 0,
            "last_seen": False,
            "has_data": False,
            "identity_seen": False,
            "error_ids": [],
            "success": False,
        }
    matching = [row for row in list(callback_rows) if _to_int(row.get("reqid"), -1) == expected_reqid]
    error_ids = sorted(
        {_to_int(row.get("error_id"), -1) for row in matching if _to_int(row.get("error_id"), -1) != 0}
    )
    last_seen = any(bool(row.get("last")) for row in matching)
    has_data = any(bool(row.get("has_data")) for row in matching)
    identity_seen = any(bool(str(row.get("account_id", "") or "").strip()) for row in matching)
    success = bool(last_seen and not error_ids and (identity_seen if require_account_id else True))
    return {
        "matching_count": len(matching),
        "last_seen": last_seen,
        "has_data": has_data,
        "identity_seen": identity_seen,
        "error_ids": error_ids,
        "success": success,
    }


def _raw_ctp_position_row(
    data: Any,
    *,
    reqid: int,
    vt_symbol_by_instrument: dict[str, str],
) -> dict[str, Any] | None:
    """Convert one reqid-bound CTP position callback into gate evidence."""

    if not isinstance(data, dict):
        return None
    instrument = str(data.get("InstrumentID", "") or "").strip()
    if not instrument:
        return None
    raw_direction = str(data.get("PosiDirection", "") or "").strip()
    if raw_direction in {"2", "long", "LONG", "多"}:
        direction = "long"
        frozen = _to_float(data.get("ShortFrozen"), 0.0)
    elif raw_direction in {"3", "short", "SHORT", "空"}:
        direction = "short"
        frozen = _to_float(data.get("LongFrozen"), 0.0)
    else:
        direction = ""
        frozen = 0.0
    volume = _to_float(data.get("Position"), 0.0)
    today_volume = min(volume, max(0.0, _to_float(data.get("TodayPosition"), 0.0)))
    yesterday_volume = max(0.0, volume - today_volume)
    vt_symbol = vt_symbol_by_instrument.get(instrument.upper(), "")
    exchange = str(data.get("ExchangeID", "") or "").strip()
    if not vt_symbol and exchange:
        vt_symbol = f"{instrument}.{exchange}"
    return {
        "symbol": instrument,
        "exchange": exchange,
        "vt_symbol": vt_symbol or instrument,
        "direction": direction,
        "volume": volume,
        "today_volume": today_volume,
        "yesterday_volume": yesterday_volume,
        "frozen": frozen,
        "position_query_reqid": reqid,
        "received_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def _raw_ctp_order_row(
    data: Any,
    *,
    reqid: int,
    row_index: int,
) -> tuple[dict[str, Any] | None, list[str]]:
    """Validate one reqid-bound CTP order row without EVENT_ORDER state."""

    if data is None or data == {}:
        return None, []
    prefix = f"final_order_query_row_invalid:index={row_index}"
    if not isinstance(data, dict):
        return None, [f"{prefix}:not_mapping"]

    broker_id = str(data.get("BrokerID", "") or "").strip()
    investor_id = str(data.get("InvestorID", "") or "").strip()
    instrument = str(data.get("InstrumentID", "") or "").strip()
    exchange = str(data.get("ExchangeID", "") or "").strip()
    order_ref = str(data.get("OrderRef", "") or "").strip()
    order_sys_id = str(data.get("OrderSysID", "") or "").strip()
    front_id_raw = data.get("FrontID")
    session_id_raw = data.get("SessionID")
    front_id = str(front_id_raw).strip() if front_id_raw is not None else ""
    session_id = str(session_id_raw).strip() if session_id_raw is not None else ""
    raw_status = str(data.get("OrderStatus", "") or "").strip()
    raw_direction = str(data.get("Direction", "") or "").strip()
    raw_offset = str(data.get("CombOffsetFlag", "") or "").strip()

    missing: list[str] = []
    for field_name, value in (
        ("BrokerID", broker_id),
        ("InvestorID", investor_id),
        ("InstrumentID", instrument),
        ("ExchangeID", exchange),
        ("OrderRef", order_ref),
        ("OrderStatus", raw_status),
        ("Direction", raw_direction),
        ("CombOffsetFlag", raw_offset),
    ):
        if not value:
            missing.append(field_name)
    if not order_sys_id and not (front_id and session_id and order_ref):
        missing.append("OrderSysID_or_FrontID_SessionID_OrderRef")

    volume_original = pd.to_numeric(data.get("VolumeTotalOriginal"), errors="coerce")
    volume_traded = pd.to_numeric(data.get("VolumeTraded"), errors="coerce")
    if pd.isna(volume_original):
        missing.append("VolumeTotalOriginal")
    if pd.isna(volume_traded):
        missing.append("VolumeTraded")
    if missing:
        return None, [f"{prefix}:missing={','.join(missing)}"]

    original = float(volume_original)
    traded = float(volume_traded)
    if original <= 0 or traded < 0 or traded > original + 1e-9:
        return None, [
            f"{prefix}:invalid_volume:original={original};traded={traded}"
        ]

    if raw_status in CTP_ACTIVE_ORDER_STATUSES:
        status_class = "active"
    elif raw_status in CTP_TERMINAL_ORDER_STATUSES:
        status_class = "terminal"
    else:
        return None, [f"{prefix}:unsupported_order_status={raw_status}"]

    if raw_direction == "0":
        direction = "long"
    elif raw_direction == "1":
        direction = "short"
    else:
        return None, [f"{prefix}:unsupported_direction={raw_direction}"]

    offset_code = raw_offset[:1]
    if offset_code == "0":
        offset = "open"
    elif offset_code in {"1", "2", "3", "4", "5", "6"}:
        offset = "close"
    else:
        return None, [f"{prefix}:unsupported_offset={raw_offset}"]

    order_identity = (
        f"sys:{exchange}:{order_sys_id}"
        if order_sys_id
        else f"front:{front_id}:{session_id}:{order_ref}"
    )
    return {
        "broker_id": broker_id,
        "investor_id": investor_id,
        "symbol": instrument,
        "exchange": exchange,
        "vt_symbol": f"{instrument}.{exchange}",
        "order_ref": order_ref,
        "order_sys_id": order_sys_id,
        "front_id": front_id,
        "session_id": session_id,
        "order_identity": order_identity,
        "vt_orderid": (
            f"CTP.{front_id}_{session_id}_{order_ref}"
            if front_id and session_id and order_ref
            else ""
        ),
        "raw_order_status": raw_status,
        "status_class": status_class,
        "active": int(status_class == "active"),
        "direction": direction,
        "offset": offset,
        "volume": original,
        "traded": traded,
        "order_query_reqid": reqid,
        "received_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }, []


def _raw_ctp_trade_row(
    data: Any, *, reqid: int, row_index: int
) -> tuple[dict[str, Any] | None, list[str]]:
    """Strict reqQryTrade row keyed by exchange OrderSysID and TradeID."""

    if data is None or data == {}:
        return None, []
    prefix = f"final_trade_query_row_invalid:index={row_index}"
    if not isinstance(data, dict):
        return None, [f"{prefix}:not_mapping"]
    required = {
        name: str(data.get(name, "") or "").strip()
        for name in (
            "BrokerID", "InvestorID", "InstrumentID", "ExchangeID",
            "OrderSysID", "TradeID", "Direction", "OffsetFlag",
            "TradeDate", "TradeTime",
        )
    }
    missing = [name for name, value in required.items() if not value]
    price = pd.to_numeric(data.get("Price"), errors="coerce")
    volume = pd.to_numeric(data.get("Volume"), errors="coerce")
    if pd.isna(price) or float(price) <= 0:
        missing.append("Price")
    if pd.isna(volume) or float(volume) <= 0:
        missing.append("Volume")
    if missing:
        return None, [f"{prefix}:missing_or_invalid={','.join(missing)}"]
    direction = "long" if required["Direction"] == "0" else "short" if required["Direction"] == "1" else ""
    offset = "open" if required["OffsetFlag"][:1] == "0" else "close" if required["OffsetFlag"][:1] in {"1", "2", "3", "4", "5", "6"} else ""
    if not direction or not offset:
        return None, [f"{prefix}:direction_or_offset_invalid"]
    trade_time_text = required["TradeTime"].replace(":", "")
    try:
        broker_trade_at = datetime.strptime(
            required["TradeDate"] + trade_time_text, "%Y%m%d%H%M%S"
        ).replace(tzinfo=ZoneInfo("Asia/Shanghai")).isoformat()
    except ValueError:
        return None, [f"{prefix}:broker_trade_time_invalid"]
    return {
        "broker_id": required["BrokerID"],
        "investor_id": required["InvestorID"],
        "symbol": required["InstrumentID"],
        "exchange": required["ExchangeID"],
        "order_sys_id": required["OrderSysID"],
        "tradeid": required["TradeID"],
        "vt_tradeid": f"CTP.{required['TradeID']}",
        "direction": direction,
        "offset": offset,
        "price": float(price),
        "volume": float(volume),
        "broker_trade_at": broker_trade_at,
        "trade_query_reqid": reqid,
    }, []


def _settlement_callback_result(callback_rows: list[dict[str, Any]]) -> dict[str, Any]:
    callbacks = list(callback_rows)
    error_ids = sorted(
        {_to_int(row.get("error_id"), -1) for row in callbacks if _to_int(row.get("error_id"), -1) != 0}
    )
    last_seen = any(bool(row.get("last")) for row in callbacks)
    return {
        "callback_count": len(callbacks),
        "last_seen": last_seen,
        "error_ids": error_ids,
        "success": bool(last_seen and not error_ids),
    }


def _ctp_connection_flags(
    rows: dict[str, list[dict[str, Any]]],
    *,
    td_api: Any | None = None,
    readiness_state: CtpReadinessState | None = None,
) -> dict[str, Any]:
    messages = _log_messages(rows.get("logs", []))
    settlement_result = _settlement_callback_result(rows.get("settlement_callbacks", []))
    account_result = _callback_result(
        rows.get("account_query_callbacks", []),
        readiness_state.expected_account_reqid if readiness_state else None,
        require_account_id=True,
    )
    position_result = _callback_result(
        rows.get("position_query_callbacks", []),
        readiness_state.expected_position_reqid if readiness_state else None,
    )
    account_rows = len(rows.get("accounts", []))
    position_rows = len(rows.get("positions", []))
    td_login_success = any("交易服务器登录成功" in msg for msg in messages)
    td_login_live = bool(getattr(td_api, "login_status", td_login_success))
    contract_inited = bool(
        getattr(td_api, "contract_inited", any("合约信息查询成功" in msg for msg in messages))
    )
    return {
        "td_connected": any("交易服务器连接成功" in msg for msg in messages),
        "td_auth_success": any("交易服务器授权验证成功" in msg for msg in messages),
        "td_auth_failed": any("交易服务器授权验证失败" in msg for msg in messages),
        "td_login_success": td_login_success,
        "td_login_live": td_login_live,
        "td_login_failed": any("交易服务器登录失败" in msg for msg in messages),
        "td_disconnected_after_connect": any("交易服务器连接断开" in msg for msg in messages),
        "settlement_confirmed": settlement_result["success"],
        "settlement_callback_last_seen": settlement_result["last_seen"],
        "settlement_callback_error_ids": settlement_result["error_ids"],
        "contract_inited": contract_inited,
        "account_rows": account_rows,
        "account_expected_reqid": readiness_state.expected_account_reqid if readiness_state else None,
        "account_query_last_seen": account_result["last_seen"],
        "account_query_identity_seen": account_result["identity_seen"],
        "account_query_error_ids": account_result["error_ids"],
        "account_query_success": account_result["success"],
        "account_snapshot_processed": bool(account_result["success"] and account_rows > 0),
        "position_rows": position_rows,
        "position_expected_reqid": readiness_state.expected_position_reqid if readiness_state else None,
        "position_query_last_seen": position_result["last_seen"],
        "position_query_has_data": position_result["has_data"],
        "position_query_error_ids": position_result["error_ids"],
        "position_query_success": position_result["success"],
        "position_snapshot_processed": bool(
            position_result["success"] and (not position_result["has_data"] or position_rows > 0)
        ),
        "readiness_fatal_error": readiness_state.fatal_error if readiness_state else "",
        "order_rows": len(rows.get("orders", [])),
        "trade_rows": len(rows.get("trades", [])),
        "latest_log_messages": messages[-16:],
    }


def _append_unique(values: list[str], value: str) -> None:
    if value and value not in values:
        values.append(value)


def _ctp_connection_ready(flags: dict[str, Any], *, account_required: bool = True) -> tuple[bool, list[str]]:
    blockers: list[str] = []
    for key in ("td_connected", "td_auth_success", "td_login_success", "td_login_live"):
        if not flags.get(key):
            _append_unique(blockers, f"ctp_{key}_missing")
    if flags.get("td_auth_failed"):
        _append_unique(blockers, "ctp_td_auth_failed")
    if flags.get("td_login_failed"):
        _append_unique(blockers, "ctp_td_login_failed")
    if flags.get("td_disconnected_after_connect"):
        _append_unique(blockers, "ctp_td_disconnected_after_connect")
    if flags.get("settlement_callback_error_ids"):
        _append_unique(blockers, f"ctp_settlement_callback_error:{flags['settlement_callback_error_ids']}")
    if not flags.get("settlement_confirmed"):
        _append_unique(blockers, "ctp_settlement_callback_missing_or_incomplete")
    if not flags.get("contract_inited"):
        _append_unique(blockers, "ctp_contract_query_not_complete")
    if account_required:
        if flags.get("account_query_error_ids"):
            _append_unique(blockers, f"ctp_account_query_error:{flags['account_query_error_ids']}")
        if not flags.get("account_query_success"):
            _append_unique(blockers, "ctp_account_callback_missing")
        elif not flags.get("account_snapshot_processed"):
            _append_unique(blockers, "ctp_account_event_not_processed")
    if flags.get("position_query_error_ids"):
        _append_unique(blockers, f"ctp_position_query_error:{flags['position_query_error_ids']}")
    if not flags.get("position_query_success"):
        _append_unique(blockers, "ctp_position_query_last_missing")
    elif not flags.get("position_snapshot_processed"):
        _append_unique(blockers, "ctp_position_event_not_processed")
    if flags.get("readiness_fatal_error"):
        _append_unique(blockers, f"ctp_readiness_fatal:{flags['readiness_fatal_error']}")
    return not blockers, blockers


def _fatal_ctp_readiness_blockers(flags: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if flags.get("td_auth_failed"):
        blockers.append("ctp_td_auth_failed")
    if flags.get("td_login_failed"):
        blockers.append("ctp_td_login_failed")
    if flags.get("td_login_success") and not flags.get("td_login_live"):
        blockers.append("ctp_td_current_login_lost")
    if flags.get("td_disconnected_after_connect"):
        blockers.append("ctp_td_disconnected_after_connect")
    if flags.get("settlement_callback_error_ids"):
        blockers.append(f"ctp_settlement_callback_error:{flags['settlement_callback_error_ids']}")
    if flags.get("account_query_error_ids"):
        blockers.append(f"ctp_account_query_error:{flags['account_query_error_ids']}")
    if flags.get("position_query_error_ids"):
        blockers.append(f"ctp_position_query_error:{flags['position_query_error_ids']}")
    if flags.get("readiness_fatal_error"):
        blockers.append(f"ctp_readiness_fatal:{flags['readiness_fatal_error']}")
    return blockers


def _ctp_query_prerequisites_ready(flags: dict[str, Any]) -> bool:
    return bool(
        flags.get("td_connected")
        and flags.get("td_auth_success")
        and flags.get("td_login_success")
        and flags.get("td_login_live")
        and flags.get("settlement_confirmed")
        and flags.get("contract_inited")
        and not _fatal_ctp_readiness_blockers(flags)
    )


def _issue_ctp_read_query(
    td_api: Any,
    readiness_state: CtpReadinessState,
    rows: dict[str, Any],
    query_kind: str,
    requested_at_monotonic: float,
) -> dict[str, Any]:
    if query_kind not in {"account", "position"}:
        raise ValueError(f"unsupported CTP read query: {query_kind}")
    reqid = _to_int(getattr(td_api, "reqid", 0), 0) + 1
    td_api.reqid = reqid
    if query_kind == "account":
        readiness_state.expected_account_reqid = reqid
    else:
        readiness_state.expected_position_reqid = reqid
        # CTP position callbacks are a multi-row snapshot.  A later query must
        # never inherit rows emitted by an earlier (or automatic) query epoch.
        rows.setdefault("positions", []).clear()
        rows.setdefault("position_query_callbacks", []).clear()
        rows["_position_query_epoch"] = {
            "active_reqid": reqid,
            "complete_reqid": None,
            "requested_at_monotonic": requested_at_monotonic,
            "pending_callbacks": [],
        }
    attempt: dict[str, Any] = {
        "query_kind": query_kind,
        "reqid": reqid,
        "requested_at_monotonic": requested_at_monotonic,
        "request_ret": "",
        "exception": "",
    }
    # All CTP read queries share the broker's one-query-per-second flow gate.
    # Preserve the last attempted call even when CTP rejects it or raises.
    rows["_ctp_last_query_monotonic"] = requested_at_monotonic
    try:
        if query_kind == "account":
            raw_ret = td_api.reqQryTradingAccount(
                {"BrokerID": str(getattr(td_api, "brokerid", "")), "InvestorID": str(getattr(td_api, "userid", ""))},
                reqid,
            )
        else:
            raw_ret = td_api.reqQryInvestorPosition(
                {"BrokerID": str(getattr(td_api, "brokerid", "")), "InvestorID": str(getattr(td_api, "userid", ""))},
                reqid,
            )
        request_ret = _to_int(raw_ret, -1)
        attempt["request_ret"] = request_ret
        if request_ret != 0:
            if query_kind == "account":
                readiness_state.expected_account_reqid = None
            else:
                readiness_state.expected_position_reqid = None
                rows["_position_query_epoch"]["active_reqid"] = None
    except Exception as exc:
        attempt["exception"] = repr(exc)
        readiness_state.fatal_error = f"{query_kind}_query_exception:{exc!r}"
        if query_kind == "account":
            readiness_state.expected_account_reqid = None
        else:
            readiness_state.expected_position_reqid = None
            rows["_position_query_epoch"]["active_reqid"] = None
    target = readiness_state.account_query_attempts if query_kind == "account" else readiness_state.position_query_attempts
    target.append(attempt)
    return attempt


def _wait_for_ctp_readiness(
    td_api: Any,
    rows: dict[str, list[dict[str, Any]]],
    *,
    account_required: bool,
    max_wait_seconds: float,
    monotonic: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
    query_interval_seconds: float = 1.1,
    poll_seconds: float = 0.05,
    hard_deadline_monotonic: float | None = None,
) -> tuple[bool, dict[str, Any], list[str], CtpReadinessState]:
    started = monotonic()
    deadline = started + max(0.0, float(max_wait_seconds))
    if hard_deadline_monotonic is not None:
        deadline = min(deadline, float(hard_deadline_monotonic))
    state = CtpReadinessState(
        account_required=bool(account_required),
        started_monotonic=started,
        deadline_monotonic=deadline,
    )
    next_query_at = started
    fatal_blockers: list[str] = []
    while True:
        flags = _ctp_connection_flags(rows, td_api=td_api, readiness_state=state)
        ready, _ = _ctp_connection_ready(flags, account_required=account_required)
        fatal_blockers = _fatal_ctp_readiness_blockers(flags)
        now = monotonic()
        if ready or fatal_blockers or now >= deadline:
            break
        if _ctp_query_prerequisites_ready(flags) and now >= next_query_at:
            if account_required and not flags.get("account_query_success"):
                if state.expected_account_reqid is None:
                    _issue_ctp_read_query(td_api, state, rows, "account", now)
                    next_query_at = now + max(1.0, float(query_interval_seconds))
            elif not flags.get("position_query_success") and state.expected_position_reqid is None:
                _issue_ctp_read_query(td_api, state, rows, "position", now)
                next_query_at = now + max(1.0, float(query_interval_seconds))
        remaining = deadline - monotonic()
        if remaining <= 0:
            break
        sleeper(min(max(0.001, float(poll_seconds)), remaining))

    state.elapsed_seconds = max(0.0, monotonic() - started)
    flags = _ctp_connection_flags(rows, td_api=td_api, readiness_state=state)
    ready, blockers = _ctp_connection_ready(flags, account_required=account_required)
    for blocker in fatal_blockers:
        _append_unique(blockers, blocker)
    if not ready and state.elapsed_seconds >= max(0.0, float(max_wait_seconds)):
        _append_unique(blockers, f"ctp_readiness_timeout:{state.elapsed_seconds:.3f}s")
    if (
        not ready
        and hard_deadline_monotonic is not None
        and monotonic() >= float(hard_deadline_monotonic)
    ):
        _append_unique(
            blockers,
            "stage179_execution_deadline_exceeded:ctp_readiness",
        )
    return ready, flags, blockers, state


def _final_order_query_epoch(
    td_api: Any,
    rows: dict[str, Any],
    *,
    max_wait_seconds: float,
    monotonic: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
    query_interval_seconds: float = CTP_QUERY_INTERVAL_SECONDS,
    poll_seconds: float = 0.05,
    hard_deadline_monotonic: float | None = None,
) -> dict[str, Any]:
    """Obtain one complete, reqid-bound order snapshot from this CTP session."""

    started = monotonic()
    deadline = started + max(0.0, float(max_wait_seconds))
    if hard_deadline_monotonic is not None:
        deadline = min(deadline, float(hard_deadline_monotonic))
    result: dict[str, Any] = {
        "success": False,
        "confirmed": False,
        "reqid": None,
        "requested_at_monotonic": None,
        "request_ret": "",
        "blockers": [],
        "orders": [],
        "active_orders": [],
        "callback_count": 0,
        "ignored_callback_count": 0,
        "elapsed_seconds": 0.0,
    }
    if (
        hard_deadline_monotonic is not None
        and monotonic() >= float(hard_deadline_monotonic)
    ):
        result["blockers"] = [
            "stage179_execution_deadline_exceeded:final_order_query"
        ]
        return result
    broker_id = str(getattr(td_api, "brokerid", "") or "").strip()
    investor_id = str(getattr(td_api, "userid", "") or "").strip()
    if not broker_id or not investor_id:
        result["blockers"] = ["final_order_query_request_identity_missing"]
        return result

    last_query_raw = pd.to_numeric(
        rows.get("_ctp_last_query_monotonic"),
        errors="coerce",
    )
    next_allowed = (
        started
        if pd.isna(last_query_raw)
        else float(last_query_raw) + max(1.0, float(query_interval_seconds))
    )
    while monotonic() + 1e-9 < next_allowed:
        remaining = min(next_allowed, deadline) - monotonic()
        if remaining <= 0:
            result["elapsed_seconds"] = max(0.0, monotonic() - started)
            result["blockers"] = [
                "stage179_execution_deadline_exceeded:final_order_query"
                if hard_deadline_monotonic is not None
                and monotonic() >= float(hard_deadline_monotonic)
                else "final_order_query_pacing_timeout"
            ]
            return result
        sleeper(min(max(0.001, float(poll_seconds)), remaining))

    requested_at = monotonic()
    if requested_at > deadline + 1e-9:
        result["elapsed_seconds"] = max(0.0, requested_at - started)
        result["blockers"] = ["final_order_query_pacing_timeout"]
        return result

    reqid = _to_int(getattr(td_api, "reqid", 0), 0) + 1
    td_api.reqid = reqid
    result["reqid"] = reqid
    result["requested_at_monotonic"] = requested_at
    rows.setdefault("order_query_callbacks", []).clear()
    epoch: dict[str, Any] = {
        "active_reqid": reqid,
        "complete_reqid": None,
        "requested_at_monotonic": requested_at,
        "pending_callbacks": [],
        "authoritative_orders": [],
        "identity_blockers": [],
    }
    rows["_order_query_epoch"] = epoch
    rows["_ctp_last_query_monotonic"] = requested_at
    try:
        raw_ret = td_api.reqQryOrder(
            {"BrokerID": broker_id, "InvestorID": investor_id},
            reqid,
        )
        request_ret = _to_int(raw_ret, -1)
        result["request_ret"] = request_ret
    except Exception as exc:
        result["elapsed_seconds"] = max(0.0, monotonic() - started)
        result["blockers"] = [f"final_order_query_exception:{exc!r}"]
        epoch["active_reqid"] = None
        return result
    if request_ret != 0:
        result["elapsed_seconds"] = max(0.0, monotonic() - started)
        result["blockers"] = [f"final_order_query_request_ret={request_ret}"]
        epoch["active_reqid"] = None
        return result

    while True:
        callbacks = list(rows.get("order_query_callbacks", []))
        callback_result = _callback_result(callbacks, reqid)
        result["callback_count"] = callback_result["matching_count"]
        result["ignored_callback_count"] = sum(
            int(bool(row.get("ignored_outside_active_epoch")))
            for row in callbacks
        )
        if callback_result["error_ids"]:
            result["blockers"] = [
                f"final_order_query_error_ids={callback_result['error_ids']}"
            ]
            break
        complete_reqid = _to_int(epoch.get("complete_reqid"), -1)
        if callback_result["last_seen"] and complete_reqid == reqid:
            identity_blockers = list(epoch.get("identity_blockers", []))
            if identity_blockers:
                result["blockers"] = identity_blockers
                break
            authoritative = list(epoch.get("authoritative_orders", []))
            for index, order in enumerate(authoritative):
                if str(order.get("broker_id", "")) != broker_id:
                    result["blockers"].append(
                        "final_order_query_account_identity_mismatch:"
                        f"index={index};field=BrokerID"
                    )
                if str(order.get("investor_id", "")) != investor_id:
                    result["blockers"].append(
                        "final_order_query_account_identity_mismatch:"
                        f"index={index};field=InvestorID"
                    )
                if _to_int(order.get("order_query_reqid"), -1) != reqid:
                    result["blockers"].append(
                        "final_order_query_row_reqid_mismatch:"
                        f"index={index}"
                    )
            if result["blockers"]:
                break
            active_orders = [
                order for order in authoritative if bool(order.get("active"))
            ]
            result.update(
                {
                    "success": True,
                    "confirmed": True,
                    "orders": authoritative,
                    "active_orders": active_orders,
                }
            )
            break
        if monotonic() >= deadline:
            result["blockers"] = [
                "stage179_execution_deadline_exceeded:final_order_query"
                if hard_deadline_monotonic is not None
                and monotonic() >= float(hard_deadline_monotonic)
                else f"final_order_query_timeout:reqid={reqid}"
            ]
            break
        remaining = deadline - monotonic()
        sleeper(min(max(0.001, float(poll_seconds)), remaining))

    result["elapsed_seconds"] = max(0.0, monotonic() - started)
    epoch["active_reqid"] = None
    return result


def _final_trade_query_epoch(
    td_api: Any,
    rows: dict[str, Any],
    *,
    max_wait_seconds: float,
    monotonic: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Obtain one complete reqid-bound trade snapshot."""

    started = monotonic()
    deadline = started + max(0.0, float(max_wait_seconds))
    result: dict[str, Any] = {
        "confirmed": False, "trades": [], "blockers": [], "reqid": None,
    }
    broker_id = str(getattr(td_api, "brokerid", "") or "").strip()
    investor_id = str(getattr(td_api, "userid", "") or "").strip()
    if not broker_id or not investor_id or not callable(getattr(td_api, "reqQryTrade", None)):
        result["blockers"] = ["final_trade_query_prerequisite_missing"]
        return result
    last_query = _to_float(rows.get("_ctp_last_query_monotonic"), 0.0)
    next_allowed = last_query + CTP_QUERY_INTERVAL_SECONDS if last_query else started
    while monotonic() < next_allowed:
        remaining = min(next_allowed, deadline) - monotonic()
        if remaining <= 0:
            result["blockers"] = ["final_trade_query_pacing_timeout"]
            return result
        sleeper(min(0.05, remaining))
    reqid = _to_int(getattr(td_api, "reqid", 0), 0) + 1
    td_api.reqid = reqid
    result["reqid"] = reqid
    rows.setdefault("trade_query_callbacks", []).clear()
    epoch = {
        "active_reqid": reqid, "complete_reqid": None,
        "pending_callbacks": [], "authoritative_trades": [],
        "identity_blockers": [],
    }
    rows["_trade_query_epoch"] = epoch
    rows["_ctp_last_query_monotonic"] = monotonic()
    try:
        request_ret = _to_int(
            td_api.reqQryTrade(
                {"BrokerID": broker_id, "InvestorID": investor_id}, reqid
            ),
            -1,
        )
    except Exception as exc:
        result["blockers"] = [f"final_trade_query_exception:{exc!r}"]
        epoch["active_reqid"] = None
        return result
    if request_ret != 0:
        result["blockers"] = [f"final_trade_query_request_ret={request_ret}"]
        epoch["active_reqid"] = None
        return result
    while monotonic() < deadline:
        callbacks = list(rows.get("trade_query_callbacks", []))
        callback_result = _callback_result(callbacks, reqid)
        if callback_result["error_ids"]:
            result["blockers"] = [
                f"final_trade_query_error_ids={callback_result['error_ids']}"
            ]
            break
        if callback_result["last_seen"] and _to_int(epoch.get("complete_reqid"), -1) == reqid:
            blockers = list(epoch.get("identity_blockers", []))
            trades = list(epoch.get("authoritative_trades", []))
            for index, trade in enumerate(trades):
                if trade.get("broker_id") != broker_id or trade.get("investor_id") != investor_id:
                    blockers.append(f"final_trade_query_account_identity_mismatch:index={index}")
            if blockers:
                result["blockers"] = blockers
            else:
                result.update({"confirmed": True, "trades": trades})
            break
        sleeper(min(0.05, max(0.0, deadline - monotonic())))
    else:
        result["blockers"] = [f"final_trade_query_timeout:reqid={reqid}"]
    epoch["active_reqid"] = None
    return result


def _final_position_query_epoch(
    td_api: Any,
    rows: dict[str, Any],
    *,
    max_wait_seconds: float,
    monotonic: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
    query_interval_seconds: float = CTP_QUERY_INTERVAL_SECONDS,
    poll_seconds: float = 0.05,
    hard_deadline_monotonic: float | None = None,
) -> dict[str, Any]:
    """Replace readiness-era positions with one fresh reqid-bound snapshot."""

    started = monotonic()
    deadline = started + max(0.0, float(max_wait_seconds))
    if hard_deadline_monotonic is not None:
        deadline = min(deadline, float(hard_deadline_monotonic))
    result: dict[str, Any] = {
        "success": False,
        "confirmed": False,
        "reqid": None,
        "requested_at_monotonic": None,
        "request_ret": "",
        "blockers": [],
        "positions": [],
        "callback_count": 0,
        "ignored_callback_count": 0,
        "elapsed_seconds": 0.0,
    }
    if (
        hard_deadline_monotonic is not None
        and monotonic() >= float(hard_deadline_monotonic)
    ):
        result["blockers"] = [
            "stage179_execution_deadline_exceeded:final_position_query"
        ]
        return result
    broker_id = str(getattr(td_api, "brokerid", "") or "").strip()
    investor_id = str(getattr(td_api, "userid", "") or "").strip()
    if not broker_id or not investor_id:
        result["blockers"] = ["final_position_query_request_identity_missing"]
        return result

    last_query_raw = pd.to_numeric(
        rows.get("_ctp_last_query_monotonic"), errors="coerce"
    )
    next_allowed = (
        started
        if pd.isna(last_query_raw)
        else float(last_query_raw) + max(1.0, float(query_interval_seconds))
    )
    while monotonic() + 1e-9 < next_allowed:
        remaining = min(next_allowed, deadline) - monotonic()
        if remaining <= 0:
            result["elapsed_seconds"] = max(0.0, monotonic() - started)
            result["blockers"] = [
                "stage179_execution_deadline_exceeded:final_position_query"
                if hard_deadline_monotonic is not None
                and monotonic() >= float(hard_deadline_monotonic)
                else "final_position_query_pacing_timeout"
            ]
            return result
        sleeper(min(max(0.001, float(poll_seconds)), remaining))

    requested_at = monotonic()
    if requested_at > deadline + 1e-9:
        result["elapsed_seconds"] = max(0.0, requested_at - started)
        result["blockers"] = ["final_position_query_pacing_timeout"]
        return result

    reqid = _to_int(getattr(td_api, "reqid", 0), 0) + 1
    td_api.reqid = reqid
    result["reqid"] = reqid
    result["requested_at_monotonic"] = requested_at
    rows.setdefault("position_query_callbacks", []).clear()
    # Clear before issuing the request: a timeout must fail closed and must not
    # leave the readiness-era snapshot available to the final gate.
    rows.setdefault("positions", []).clear()
    epoch: dict[str, Any] = {
        "active_reqid": reqid,
        "complete_reqid": None,
        "requested_at_monotonic": requested_at,
        "pending_callbacks": [],
        "authoritative_position_rows": 0,
        "identity_blockers": [],
        "strict_identity": True,
        "expected_broker_id": broker_id,
        "expected_investor_id": investor_id,
    }
    rows["_position_query_epoch"] = epoch
    rows["_ctp_last_query_monotonic"] = requested_at
    try:
        raw_ret = td_api.reqQryInvestorPosition(
            {"BrokerID": broker_id, "InvestorID": investor_id}, reqid
        )
        request_ret = _to_int(raw_ret, -1)
        result["request_ret"] = request_ret
    except Exception as exc:
        result["elapsed_seconds"] = max(0.0, monotonic() - started)
        result["blockers"] = [f"final_position_query_exception:{exc!r}"]
        epoch["active_reqid"] = None
        return result
    if request_ret != 0:
        result["elapsed_seconds"] = max(0.0, monotonic() - started)
        result["blockers"] = [
            f"final_position_query_request_ret={request_ret}"
        ]
        epoch["active_reqid"] = None
        return result

    while True:
        callbacks = list(rows.get("position_query_callbacks", []))
        callback_result = _callback_result(callbacks, reqid)
        result["callback_count"] = callback_result["matching_count"]
        result["ignored_callback_count"] = sum(
            int(bool(row.get("ignored_outside_active_epoch")))
            for row in callbacks
        )
        if callback_result["error_ids"]:
            result["blockers"] = [
                f"final_position_query_error_ids={callback_result['error_ids']}"
            ]
            break
        complete_reqid = _to_int(epoch.get("complete_reqid"), -1)
        if callback_result["last_seen"] and complete_reqid == reqid:
            identity_blockers = list(epoch.get("identity_blockers", []))
            if identity_blockers:
                result["blockers"] = identity_blockers
                break
            authoritative = list(rows.get("positions", []))
            bad_reqids = [
                index
                for index, position in enumerate(authoritative)
                if _to_int(position.get("position_query_reqid"), -1) != reqid
            ]
            if bad_reqids:
                result["blockers"] = [
                    "final_position_query_row_reqid_mismatch:"
                    + ",".join(str(index) for index in bad_reqids)
                ]
                break
            result.update(
                {
                    "success": True,
                    "confirmed": True,
                    "positions": authoritative,
                }
            )
            break
        if monotonic() >= deadline:
            result["blockers"] = [
                "stage179_execution_deadline_exceeded:final_position_query"
                if hard_deadline_monotonic is not None
                and monotonic() >= float(hard_deadline_monotonic)
                else f"final_position_query_timeout:reqid={reqid}"
            ]
            break
        remaining = deadline - monotonic()
        sleeper(min(max(0.001, float(poll_seconds)), remaining))

    result["elapsed_seconds"] = max(0.0, monotonic() - started)
    epoch["active_reqid"] = None
    return result


def _canonical_evidence_sha256(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()


def _strict_ctp_account_number(value: Any) -> float | None:
    parsed = pd.to_numeric(value, errors="coerce")
    if pd.isna(parsed):
        return None
    number = float(parsed)
    if (
        not math.isfinite(number)
        or abs(number) >= CTP_NUMERIC_SENTINEL_FLOOR
    ):
        return None
    return number


def _wait_for_ctp_query_pacing(
    rows: dict[str, Any],
    *,
    started: float,
    deadline: float,
    blocker_namespace: str,
    monotonic: Callable[[], float],
    sleeper: Callable[[float], None],
    query_interval_seconds: float,
    poll_seconds: float,
) -> str:
    last_query_raw = pd.to_numeric(
        rows.get("_ctp_last_query_monotonic"), errors="coerce"
    )
    next_allowed = (
        started
        if pd.isna(last_query_raw)
        else float(last_query_raw)
        + max(1.0, float(query_interval_seconds))
    )
    while monotonic() + 1e-9 < next_allowed:
        remaining = min(next_allowed, deadline) - monotonic()
        if remaining <= 0:
            return f"{blocker_namespace}_pacing_timeout"
        sleeper(min(max(0.001, float(poll_seconds)), remaining))
    if monotonic() > deadline + 1e-9:
        return f"{blocker_namespace}_pacing_timeout"
    return ""


def _final_open_account_funds_query_epoch(
    td_api: Any,
    rows: dict[str, Any],
    *,
    max_wait_seconds: float,
    monotonic: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
    query_interval_seconds: float = CTP_QUERY_INTERVAL_SECONDS,
    poll_seconds: float = 0.05,
    hard_deadline_monotonic: float | None = None,
) -> dict[str, Any]:
    """Return one fresh raw, reqid-bound TradingAccount funds row."""

    started = monotonic()
    deadline = started + max(0.0, float(max_wait_seconds))
    if hard_deadline_monotonic is not None:
        deadline = min(deadline, float(hard_deadline_monotonic))
    result: dict[str, Any] = {
        "success": False,
        "confirmed": False,
        "reqid": None,
        "requested_at_monotonic": None,
        "request_ret": "",
        "query_api_called_count": 0,
        "blockers": [],
        "callback_count": 0,
        "ignored_callback_count": 0,
        "broker_id": "",
        "account_id": "",
        "available": None,
        "curr_margin": None,
        "raw_evidence_sha256": "",
        "elapsed_seconds": 0.0,
    }
    broker_id = str(getattr(td_api, "brokerid", "") or "").strip()
    investor_id = str(getattr(td_api, "userid", "") or "").strip()
    query = getattr(td_api, "reqQryTradingAccount", None)
    if not broker_id or not investor_id:
        result["blockers"] = [
            "final_open_account_funds_request_identity_missing"
        ]
        return result
    if not callable(query):
        result["blockers"] = [
            "final_open_account_funds_query_api_missing"
        ]
        return result
    pacing_blocker = _wait_for_ctp_query_pacing(
        rows,
        started=started,
        deadline=deadline,
        blocker_namespace="final_open_account_funds_query",
        monotonic=monotonic,
        sleeper=sleeper,
        query_interval_seconds=query_interval_seconds,
        poll_seconds=poll_seconds,
    )
    if pacing_blocker:
        result["elapsed_seconds"] = max(0.0, monotonic() - started)
        result["blockers"] = [pacing_blocker]
        return result

    reqid = _to_int(getattr(td_api, "reqid", 0), 0) + 1
    td_api.reqid = reqid
    result["reqid"] = reqid
    requested_at = monotonic()
    result["requested_at_monotonic"] = requested_at
    epoch: dict[str, Any] = {
        "active_reqid": reqid,
        "complete_reqid": None,
        "requested_at_monotonic": requested_at,
        "raw_rows": [],
        "expected_broker_id": broker_id,
        "expected_account_id": investor_id,
    }
    rows["_final_account_funds_epoch"] = epoch
    rows["_ctp_last_query_monotonic"] = requested_at
    request = {"BrokerID": broker_id, "InvestorID": investor_id}
    result["request"] = dict(request)
    result["query_api_called_count"] = 1
    try:
        request_ret = _to_int(query(request, reqid), -1)
        result["request_ret"] = request_ret
    except Exception as exc:
        result["elapsed_seconds"] = max(0.0, monotonic() - started)
        result["blockers"] = [
            f"final_open_account_funds_query_exception:{exc!r}"
        ]
        epoch["active_reqid"] = None
        return result
    if request_ret != 0:
        result["elapsed_seconds"] = max(0.0, monotonic() - started)
        result["blockers"] = [
            f"final_open_account_funds_query_request_ret={request_ret}"
        ]
        epoch["active_reqid"] = None
        return result

    while True:
        callbacks = list(rows.get("account_query_callbacks", []))
        matching = [
            row
            for row in callbacks
            if _to_int(row.get("reqid"), -1) == reqid
        ]
        result["callback_count"] = len(matching)
        result["ignored_callback_count"] = sum(
            int(bool(row.get("ignored_outside_active_epoch")))
            for row in matching
        )
        callback_result = _callback_result(
            matching, reqid, require_account_id=True
        )
        if callback_result["error_ids"]:
            result["blockers"] = [
                "final_open_account_funds_query_error_ids="
                f"{callback_result['error_ids']}"
            ]
            break
        if (
            callback_result["last_seen"]
            and _to_int(epoch.get("complete_reqid"), -1) == reqid
        ):
            raw_rows = list(epoch.get("raw_rows", []))
            if len(raw_rows) != 1:
                result["blockers"] = [
                    "final_open_account_funds_row_count_invalid:"
                    f"{len(raw_rows)}"
                ]
                break
            raw = dict(raw_rows[0])
            raw_broker_id = str(raw.get("BrokerID", "") or "").strip()
            raw_account_id = str(raw.get("AccountID", "") or "").strip()
            if raw_broker_id != broker_id:
                result["blockers"].append(
                    "final_open_account_funds_broker_identity_mismatch"
                )
            if raw_account_id != investor_id:
                result["blockers"].append(
                    "final_open_account_funds_account_identity_mismatch"
                )
            available = _strict_ctp_account_number(raw.get("Available"))
            curr_margin = _strict_ctp_account_number(
                raw.get("CurrMargin")
            )
            if available is None:
                result["blockers"].append(
                    "final_open_account_funds_available_invalid"
                )
            elif available <= 0:
                result["blockers"].append(
                    "final_open_account_funds_available_not_positive"
                )
            if curr_margin is None:
                result["blockers"].append(
                    "final_open_account_funds_curr_margin_invalid"
                )
            elif curr_margin < 0:
                result["blockers"].append(
                    "final_open_account_funds_curr_margin_negative"
                )
            result.update(
                {
                    "broker_id": raw_broker_id,
                    "account_id": raw_account_id,
                    "available": available,
                    "curr_margin": curr_margin,
                    "raw_evidence_sha256": _canonical_evidence_sha256(
                        raw
                    ),
                }
            )
            result["blockers"] = list(
                dict.fromkeys(result["blockers"])
            )
            if not result["blockers"]:
                result.update({"success": True, "confirmed": True})
            break
        if monotonic() >= deadline:
            result["blockers"] = [
                "stage179_execution_deadline_exceeded:"
                "final_open_account_funds_query"
                if hard_deadline_monotonic is not None
                and monotonic() >= float(hard_deadline_monotonic)
                else f"final_open_account_funds_query_timeout:reqid={reqid}"
            ]
            break
        sleeper(
            min(
                max(0.001, float(poll_seconds)),
                max(0.0, deadline - monotonic()),
            )
        )
    result["elapsed_seconds"] = max(0.0, monotonic() - started)
    epoch["active_reqid"] = None
    return result


def _physical_open_request_groups(
    requests: list[OrderRequest],
) -> tuple[list[dict[str, Any]], list[str]]:
    groups: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    blockers: list[str] = []
    for index, request in enumerate(requests):
        if not isinstance(request, OrderRequest):
            blockers.append(
                "final_open_funds_physical_request_invalid:"
                f"index={index};type={type(request).__name__}"
            )
            continue
        if request.offset != Offset.OPEN:
            continue
        direction_code = (
            CTP_DIRECTION_BUY
            if request.direction == Direction.LONG
            else CTP_DIRECTION_SELL
            if request.direction == Direction.SHORT
            else ""
        )
        symbol = str(request.symbol or "").strip()
        exchange = str(request.exchange.value or "").strip()
        volume = _strict_ctp_account_number(request.volume)
        item_blockers: list[str] = []
        if not symbol or request.exchange not in FAK_OPEN_EXCHANGES:
            item_blockers.append(
                "final_open_funds_physical_identity_invalid:"
                f"index={index};symbol={symbol};exchange={exchange}"
            )
        if not direction_code:
            item_blockers.append(
                f"final_open_funds_direction_invalid:index={index}"
            )
        if (
            volume is None
            or volume <= 0
            or not math.isclose(
                volume, round(volume), rel_tol=0.0, abs_tol=1e-9
            )
        ):
            item_blockers.append(
                "final_open_funds_volume_invalid:"
                f"index={index};volume={request.volume}"
            )
        if item_blockers:
            blockers.extend(item_blockers)
            continue
        key = (
            symbol,
            exchange,
            direction_code,
            CTP_OFFSET_OPEN,
            CTP_HEDGE_SPECULATION,
        )
        group = groups.setdefault(
            key,
            {
                "symbol": symbol,
                "exchange": exchange,
                "direction": direction_code,
                "offset_flag": CTP_OFFSET_OPEN,
                "hedge_flag": CTP_HEDGE_SPECULATION,
                "required_volume": 0,
                "child_count": 0,
            },
        )
        group["required_volume"] += int(round(float(volume)))
        group["child_count"] += 1
    return list(groups.values()), list(dict.fromkeys(blockers))


def _physical_request_bundle(requests: list[OrderRequest]) -> list[dict[str, Any]]:
    bundle: list[dict[str, Any]] = []
    for request in requests:
        if not isinstance(request, OrderRequest):
            bundle.append({"invalid_type": type(request).__name__})
            continue
        bundle.append(
            {
                "symbol": request.symbol,
                "exchange": request.exchange.value,
                "direction": request.direction.value,
                "offset": request.offset.value,
                "type": request.type.value,
                "volume": float(request.volume),
                "price": float(request.price),
                "reference": request.reference,
            }
        )
    return bundle


def _final_open_max_order_volume_query_epoch(
    td_api: Any,
    rows: dict[str, Any],
    group: Mapping[str, Any],
    *,
    max_wait_seconds: float,
    monotonic: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
    query_interval_seconds: float = CTP_QUERY_INTERVAL_SECONDS,
    poll_seconds: float = 0.05,
    hard_deadline_monotonic: float | None = None,
) -> dict[str, Any]:
    """Query broker-authoritative OPEN capacity for one exact CTP tuple."""

    started = monotonic()
    deadline = started + max(0.0, float(max_wait_seconds))
    if hard_deadline_monotonic is not None:
        deadline = min(deadline, float(hard_deadline_monotonic))
    result: dict[str, Any] = {
        "success": False,
        "confirmed": False,
        "reqid": None,
        "requested_at_monotonic": None,
        "request_ret": "",
        "query_api_called_count": 0,
        "blockers": [],
        "callback_count": 0,
        "ignored_callback_count": 0,
        "max_volume": None,
        "required_volume": _to_int(group.get("required_volume"), -1),
        "raw_evidence_sha256": "",
        "elapsed_seconds": 0.0,
    }
    broker_id = str(getattr(td_api, "brokerid", "") or "").strip()
    investor_id = str(getattr(td_api, "userid", "") or "").strip()
    query = getattr(td_api, "reqQryMaxOrderVolume", None)
    if not broker_id or not investor_id:
        result["blockers"] = [
            "final_open_max_volume_request_identity_missing"
        ]
        return result
    if not callable(query):
        result["blockers"] = [
            "final_open_max_volume_query_api_missing"
        ]
        return result
    required_volume = _to_int(group.get("required_volume"), -1)
    if required_volume <= 0:
        result["blockers"] = [
            "final_open_max_volume_required_volume_invalid"
        ]
        return result
    expected = {
        "BrokerID": broker_id,
        "InvestorID": investor_id,
        "InstrumentID": str(group.get("symbol", "") or ""),
        "ExchangeID": str(group.get("exchange", "") or ""),
        "Direction": str(group.get("direction", "") or ""),
        "OffsetFlag": str(group.get("offset_flag", "") or ""),
        "HedgeFlag": str(group.get("hedge_flag", "") or ""),
        # The official vnpy_ctp wrapper maps this native field even though
        # CtpTdApi does not configure investment-unit routing. Bind the
        # intentionally empty value so a callback for another unit cannot
        # authorize this request.
        "InvestUnitID": "",
    }
    if any(
        not value
        for field_name, value in expected.items()
        if field_name != "InvestUnitID"
    ):
        result["blockers"] = [
            "final_open_max_volume_query_tuple_incomplete"
        ]
        return result
    request = {**expected, "MaxVolume": 0}
    result["request"] = dict(request)
    pacing_blocker = _wait_for_ctp_query_pacing(
        rows,
        started=started,
        deadline=deadline,
        blocker_namespace="final_open_max_volume_query",
        monotonic=monotonic,
        sleeper=sleeper,
        query_interval_seconds=query_interval_seconds,
        poll_seconds=poll_seconds,
    )
    if pacing_blocker:
        result["elapsed_seconds"] = max(0.0, monotonic() - started)
        result["blockers"] = [pacing_blocker]
        return result

    reqid = _to_int(getattr(td_api, "reqid", 0), 0) + 1
    td_api.reqid = reqid
    result["reqid"] = reqid
    requested_at = monotonic()
    result["requested_at_monotonic"] = requested_at
    epoch: dict[str, Any] = {
        "active_reqid": reqid,
        "complete_reqid": None,
        "requested_at_monotonic": requested_at,
        "raw_rows": [],
        "expected": dict(expected),
    }
    rows["_max_order_volume_query_epoch"] = epoch
    rows["_ctp_last_query_monotonic"] = requested_at
    result["query_api_called_count"] = 1
    try:
        request_ret = _to_int(query(request, reqid), -1)
        result["request_ret"] = request_ret
    except Exception as exc:
        result["elapsed_seconds"] = max(0.0, monotonic() - started)
        result["blockers"] = [
            f"final_open_max_volume_query_exception:{exc!r}"
        ]
        epoch["active_reqid"] = None
        return result
    if request_ret != 0:
        result["elapsed_seconds"] = max(0.0, monotonic() - started)
        result["blockers"] = [
            f"final_open_max_volume_query_request_ret={request_ret}"
        ]
        epoch["active_reqid"] = None
        return result

    while True:
        callbacks = list(
            rows.get("max_order_volume_query_callbacks", [])
        )
        matching = [
            row
            for row in callbacks
            if _to_int(row.get("reqid"), -1) == reqid
        ]
        result["callback_count"] = len(matching)
        result["ignored_callback_count"] = sum(
            int(bool(row.get("ignored_outside_active_epoch")))
            for row in matching
        )
        callback_result = _callback_result(matching, reqid)
        if callback_result["error_ids"]:
            result["blockers"] = [
                "final_open_max_volume_query_error_ids="
                f"{callback_result['error_ids']}"
            ]
            break
        if (
            callback_result["last_seen"]
            and _to_int(epoch.get("complete_reqid"), -1) == reqid
        ):
            raw_rows = list(epoch.get("raw_rows", []))
            if len(raw_rows) != 1:
                result["blockers"] = [
                    "final_open_max_volume_row_count_invalid:"
                    f"{len(raw_rows)}"
                ]
                break
            raw = dict(raw_rows[0])
            for field_name, expected_value in expected.items():
                if field_name not in raw:
                    result["blockers"].append(
                        "final_open_max_volume_identity_mismatch:"
                        f"field={field_name};expected={expected_value};"
                        "actual=<missing>"
                    )
                    continue
                raw_value = raw[field_name]
                actual = (
                    "<null>" if raw_value is None else str(raw_value)
                )
                if actual != expected_value:
                    result["blockers"].append(
                        "final_open_max_volume_identity_mismatch:"
                        f"field={field_name};expected={expected_value};"
                        f"actual={actual}"
                    )
            raw_max_volume = pd.to_numeric(
                raw.get("MaxVolume"), errors="coerce"
            )
            max_volume: int | None = None
            if (
                pd.isna(raw_max_volume)
                or not math.isfinite(float(raw_max_volume))
                or float(raw_max_volume) < 0
                or float(raw_max_volume) >= CTP_NUMERIC_SENTINEL_FLOOR
                or not math.isclose(
                    float(raw_max_volume),
                    round(float(raw_max_volume)),
                    rel_tol=0.0,
                    abs_tol=1e-9,
                )
            ):
                result["blockers"].append(
                    "final_open_max_volume_value_invalid"
                )
            else:
                max_volume = int(round(float(raw_max_volume)))
                if max_volume < required_volume:
                    result["blockers"].append(
                        "final_open_max_volume_insufficient:"
                        f"max={max_volume};required={required_volume}"
                    )
            result.update(
                {
                    "max_volume": max_volume,
                    "raw_evidence_sha256": _canonical_evidence_sha256(
                        raw
                    ),
                }
            )
            result["blockers"] = list(
                dict.fromkeys(result["blockers"])
            )
            if not result["blockers"]:
                result.update({"success": True, "confirmed": True})
            break
        if monotonic() >= deadline:
            result["blockers"] = [
                "stage179_execution_deadline_exceeded:"
                "final_open_max_volume_query"
                if hard_deadline_monotonic is not None
                and monotonic() >= float(hard_deadline_monotonic)
                else f"final_open_max_volume_query_timeout:reqid={reqid}"
            ]
            break
        sleeper(
            min(
                max(0.001, float(poll_seconds)),
                max(0.0, deadline - monotonic()),
            )
        )
    result["elapsed_seconds"] = max(0.0, monotonic() - started)
    epoch["active_reqid"] = None
    return result


def _final_open_funds_margin_gate(
    td_api: Any,
    rows: dict[str, Any],
    requests: list[OrderRequest],
    *,
    max_wait_seconds: float,
    readiness_state: CtpReadinessState | None = None,
    monotonic: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
    hard_deadline_monotonic: float | None = None,
) -> dict[str, Any]:
    """Authorize OPEN only with fresh raw funds and broker max volume."""

    started = monotonic()
    deadline = started + max(0.0, float(max_wait_seconds))
    if hard_deadline_monotonic is not None:
        deadline = min(deadline, float(hard_deadline_monotonic))
    bundle = _physical_request_bundle(requests)
    groups, group_blockers = _physical_open_request_groups(requests)
    open_child_count = sum(int(group["child_count"]) for group in groups)
    result: dict[str, Any] = {
        "success": False,
        "confirmed": False,
        "status": "blocked",
        "bypassed_close_only": 0,
        "query_api_called_count": 0,
        "open_child_count": open_child_count,
        "request_bundle": bundle,
        "request_bundle_sha256": _canonical_evidence_sha256(bundle),
        "account": {},
        "max_volume_queries": [],
        "blockers": list(group_blockers),
        "event_watermark": _execution_event_watermark(rows),
        "query_watermark": {},
        "elapsed_seconds": 0.0,
    }
    has_raw_open = any(
        isinstance(request, OrderRequest) and request.offset == Offset.OPEN
        for request in requests
    )
    if not has_raw_open:
        result.update(
            {
                "success": True,
                "confirmed": True,
                "status": "bypassed_close_only",
                "bypassed_close_only": 1,
                "blockers": [],
                "elapsed_seconds": max(0.0, monotonic() - started),
            }
        )
        return result
    if result["blockers"] or not groups:
        if not groups:
            result["blockers"].append(
                "final_open_funds_no_valid_open_group"
            )
        result["blockers"] = list(dict.fromkeys(result["blockers"]))
        return result

    account_result = _final_open_account_funds_query_epoch(
        td_api,
        rows,
        max_wait_seconds=max(0.0, deadline - monotonic()),
        monotonic=monotonic,
        sleeper=sleeper,
        hard_deadline_monotonic=hard_deadline_monotonic,
    )
    result["account"] = account_result
    result["query_api_called_count"] += _to_int(
        account_result.get("query_api_called_count"), 0
    )
    result["blockers"].extend(account_result.get("blockers", []))
    if account_result.get("confirmed"):
        for group in groups:
            max_result = _final_open_max_order_volume_query_epoch(
                td_api,
                rows,
                group,
                max_wait_seconds=max(0.0, deadline - monotonic()),
                monotonic=monotonic,
                sleeper=sleeper,
                hard_deadline_monotonic=hard_deadline_monotonic,
            )
            result["max_volume_queries"].append(max_result)
            result["query_api_called_count"] += _to_int(
                max_result.get("query_api_called_count"), 0
            )
            result["blockers"].extend(max_result.get("blockers", []))
            if not max_result.get("confirmed"):
                break
    result["blockers"] = list(
        dict.fromkeys(str(item) for item in result["blockers"] if str(item))
    )
    if (
        not result["blockers"]
        and account_result.get("confirmed")
        and len(result["max_volume_queries"]) == len(groups)
        and all(
            item.get("confirmed")
            for item in result["max_volume_queries"]
        )
    ):
        result.update(
            {"success": True, "confirmed": True, "status": "confirmed"}
        )
        if readiness_state is not None:
            readiness_state.expected_account_reqid = _to_int(
                account_result.get("reqid"), -1
            )
    result["event_watermark"] = _execution_event_watermark(rows)
    account_reqid = _to_int(account_result.get("reqid"), -1)
    max_reqids = [
        _to_int(item.get("reqid"), -1)
        for item in result["max_volume_queries"]
    ]
    account_callbacks = [
        row
        for row in rows.get("account_query_callbacks", [])
        if _to_int(row.get("reqid"), -1) == account_reqid
    ]
    max_callbacks = [
        row
        for row in rows.get("max_order_volume_query_callbacks", [])
        if _to_int(row.get("reqid"), -1) in set(max_reqids)
    ]
    last_owned_query = (
        result["max_volume_queries"][-1]
        if result["max_volume_queries"]
        else account_result
    )
    result["query_watermark"] = {
        "broker_id": str(getattr(td_api, "brokerid", "") or ""),
        "investor_id": str(getattr(td_api, "userid", "") or ""),
        # These are the exact values owned by the last query in this gate.
        # Reading the mutable session values here could absorb a concurrent
        # unrelated query into the baseline and authorize a stale bundle.
        "td_reqid_after": _to_int(
            last_owned_query.get("reqid"), -1
        ),
        "ctp_last_query_monotonic": last_owned_query.get(
            "requested_at_monotonic"
        ),
        "account_reqid": account_reqid,
        "max_volume_reqids": max_reqids,
        "account_callback_count": len(account_callbacks),
        "max_volume_callback_count": len(max_callbacks),
        "account_callbacks_sha256": _canonical_evidence_sha256(
            account_callbacks
        ),
        "max_volume_callbacks_sha256": _canonical_evidence_sha256(
            max_callbacks
        ),
    }
    result["evidence_sha256"] = _canonical_evidence_sha256(
        {
            "request_bundle_sha256": result["request_bundle_sha256"],
            "account": account_result,
            "max_volume_queries": result["max_volume_queries"],
            "event_watermark": result["event_watermark"],
            "query_watermark": result["query_watermark"],
        }
    )
    result["elapsed_seconds"] = max(0.0, monotonic() - started)
    return result


def _open_funds_gate_consistency_blockers(
    td_api: Any,
    rows: dict[str, Any],
    requests: list[OrderRequest],
    gate: Mapping[str, Any],
    *,
    owned_native_insert_count: int = 0,
    owned_event_watermark: Mapping[str, Any] | None = None,
) -> list[str]:
    """Zero-I/O proof that the exact priced OPEN bundle still owns its gate."""

    has_open = any(
        isinstance(request, OrderRequest) and request.offset == Offset.OPEN
        for request in requests
    )
    if not has_open:
        # A protective CLOSE must never be delayed or blocked by OPEN funds.
        return []
    blockers: list[str] = []
    if not gate or gate.get("confirmed") is not True:
        return ["final_open_funds_gate_missing_or_unconfirmed"]
    if gate.get("status") != "confirmed":
        blockers.append("final_open_funds_gate_status_invalid")
    bundle_sha256 = _canonical_evidence_sha256(
        _physical_request_bundle(requests)
    )
    if bundle_sha256 != str(gate.get("request_bundle_sha256", "")):
        blockers.append("final_open_funds_request_bundle_changed")
    watermark = dict(gate.get("query_watermark", {}))
    broker_id = str(getattr(td_api, "brokerid", "") or "")
    investor_id = str(getattr(td_api, "userid", "") or "")
    if broker_id != str(watermark.get("broker_id", "")):
        blockers.append("final_open_funds_broker_identity_changed")
    if investor_id != str(watermark.get("investor_id", "")):
        blockers.append("final_open_funds_investor_identity_changed")
    expected_owned_count = _to_int(owned_native_insert_count, -1)
    if expected_owned_count < 0:
        blockers.append(
            "final_open_funds_owned_native_insert_count_invalid"
        )
        expected_owned_count = 0
    expected_td_reqid = (
        _to_int(watermark.get("td_reqid_after"), -2)
        + expected_owned_count
    )
    if _to_int(getattr(td_api, "reqid", -1), -1) != expected_td_reqid:
        blockers.append("final_open_funds_td_reqid_watermark_changed")
    expected_last_query = pd.to_numeric(
        watermark.get("ctp_last_query_monotonic"), errors="coerce"
    )
    current_last_query = pd.to_numeric(
        rows.get("_ctp_last_query_monotonic"), errors="coerce"
    )
    if (
        pd.isna(expected_last_query)
        or pd.isna(current_last_query)
        or not math.isclose(
            float(expected_last_query),
            float(current_last_query),
            rel_tol=0.0,
            abs_tol=1e-12,
        )
    ):
        blockers.append("final_open_funds_query_watermark_changed")
    blockers.extend(
        _event_watermark_blockers(
            dict(
                owned_event_watermark
                if owned_event_watermark is not None
                else gate.get("event_watermark", {})
            ),
            _execution_event_watermark(rows),
            phase="final_open_funds_consistency",
        )
    )
    account_reqid = _to_int(watermark.get("account_reqid"), -1)
    max_reqids = {
        _to_int(value, -1)
        for value in watermark.get("max_volume_reqids", [])
    }
    account_callbacks = [
        row
        for row in rows.get("account_query_callbacks", [])
        if _to_int(row.get("reqid"), -1) == account_reqid
    ]
    max_callbacks = [
        row
        for row in rows.get("max_order_volume_query_callbacks", [])
        if _to_int(row.get("reqid"), -1) in max_reqids
    ]
    if len(account_callbacks) != _to_int(
        watermark.get("account_callback_count"), -1
    ) or _canonical_evidence_sha256(account_callbacks) != str(
        watermark.get("account_callbacks_sha256", "")
    ):
        blockers.append("final_open_funds_account_evidence_changed")
    if len(max_callbacks) != _to_int(
        watermark.get("max_volume_callback_count"), -1
    ) or _canonical_evidence_sha256(max_callbacks) != str(
        watermark.get("max_volume_callbacks_sha256", "")
    ):
        blockers.append("final_open_funds_max_volume_evidence_changed")
    return list(dict.fromkeys(blockers))


def _physical_batch_query_watermark(
    td_api: Any,
    rows: Mapping[str, Any],
) -> dict[str, Any]:
    """Bind one physical batch to the current CTP connection/query epoch."""

    return {
        "broker_id": str(getattr(td_api, "brokerid", "") or ""),
        "investor_id": str(getattr(td_api, "userid", "") or ""),
        "td_reqid_before_batch": _to_int(
            getattr(td_api, "reqid", -1), -1
        ),
        "ctp_last_query_monotonic": rows.get(
            "_ctp_last_query_monotonic"
        ),
    }


def _physical_batch_query_watermark_blockers(
    td_api: Any,
    rows: Mapping[str, Any],
    watermark: Mapping[str, Any],
    *,
    owned_native_insert_count: int,
) -> list[str]:
    """Allow only the exact reqid increments owned by this physical batch."""

    blockers: list[str] = []
    if not watermark:
        return ["physical_batch_query_watermark_missing"]
    owned_count = _to_int(owned_native_insert_count, -1)
    if owned_count < 0:
        blockers.append("physical_batch_native_insert_count_invalid")
        owned_count = 0
    broker_id = str(getattr(td_api, "brokerid", "") or "")
    investor_id = str(getattr(td_api, "userid", "") or "")
    if broker_id != str(watermark.get("broker_id", "")):
        blockers.append("physical_batch_broker_identity_changed")
    if investor_id != str(watermark.get("investor_id", "")):
        blockers.append("physical_batch_investor_identity_changed")
    base_reqid = _to_int(
        watermark.get("td_reqid_before_batch"), -2
    )
    expected_reqid = base_reqid + owned_count
    actual_reqid = _to_int(getattr(td_api, "reqid", -1), -1)
    if base_reqid < 0 or actual_reqid != expected_reqid:
        blockers.append(
            "physical_batch_td_reqid_not_exact_owned_sequence:"
            f"base={base_reqid};owned={owned_count};"
            f"expected={expected_reqid};actual={actual_reqid}"
        )
    expected_last_query = pd.to_numeric(
        watermark.get("ctp_last_query_monotonic"), errors="coerce"
    )
    current_last_query = pd.to_numeric(
        rows.get("_ctp_last_query_monotonic"), errors="coerce"
    )
    if (
        pd.isna(expected_last_query)
        or pd.isna(current_last_query)
        or not math.isclose(
            float(expected_last_query),
            float(current_last_query),
            rel_tol=0.0,
            abs_tol=1e-12,
        )
    ):
        blockers.append("physical_batch_query_watermark_changed")
    return list(dict.fromkeys(blockers))


def _physical_offset_identity(value: Any) -> str:
    text = str(getattr(value, "value", value) or "").strip().lower()
    compact = "".join(
        character
        for character in text
        if character.isalnum()
    )
    return {
        "open": "open",
        "close": "close",
        "closetoday": "close_today",
        "closeyesterday": "close_yesterday",
    }.get(compact, compact)


def _native_insert_request_blockers(
    native_td_api: Any,
    expected_td_api: Any,
    native_request: Mapping[str, Any],
    request: OrderRequest,
) -> list[str]:
    """Bind the native insert payload to the exact current physical child."""

    if native_td_api is not expected_td_api:
        return ["physical_batch_native_td_api_identity_mismatch"]
    direction = {
        Direction.LONG: CTP_DIRECTION_BUY,
        Direction.SHORT: CTP_DIRECTION_SELL,
    }.get(request.direction, "")
    offset = {
        Offset.OPEN: CTP_OFFSET_OPEN,
        Offset.CLOSE: CTP_OFFSET_CLOSE,
        Offset.CLOSETODAY: CTP_OFFSET_CLOSE_TODAY,
        Offset.CLOSEYESTERDAY: CTP_OFFSET_CLOSE_YESTERDAY,
    }.get(request.offset, "")
    order_type = {
        OrderType.LIMIT: ("2", "3", "1"),
        OrderType.FAK: ("2", "1", "1"),
        OrderType.FOK: ("2", "1", "3"),
    }.get(request.type)
    expected: dict[str, str] = {
        "BrokerID": str(getattr(expected_td_api, "brokerid", "") or ""),
        "InvestorID": str(getattr(expected_td_api, "userid", "") or ""),
        "UserID": str(getattr(expected_td_api, "userid", "") or ""),
        "InstrumentID": str(request.symbol or ""),
        "ExchangeID": str(request.exchange.value or ""),
        "Direction": direction,
        "CombOffsetFlag": offset,
        "CombHedgeFlag": CTP_HEDGE_SPECULATION,
    }
    if order_type is not None:
        expected.update(
            {
                "OrderPriceType": order_type[0],
                "TimeCondition": order_type[1],
                "VolumeCondition": order_type[2],
            }
        )
    blockers: list[str] = []
    if not direction or not offset or order_type is None:
        blockers.append("physical_batch_native_request_enum_invalid")
    for field_name, expected_value in expected.items():
        if field_name not in native_request:
            blockers.append(
                "physical_batch_native_request_field_missing:"
                f"{field_name}"
            )
            continue
        actual = native_request.get(field_name)
        actual_text = "<null>" if actual is None else str(actual)
        if actual_text != expected_value:
            blockers.append(
                "physical_batch_native_request_field_mismatch:"
                f"{field_name};expected={expected_value};actual={actual_text}"
            )
    volume = _strict_ctp_account_number(
        native_request.get("VolumeTotalOriginal")
    )
    if (
        volume is None
        or not math.isclose(
            volume,
            float(request.volume),
            rel_tol=0.0,
            abs_tol=1e-9,
        )
    ):
        blockers.append("physical_batch_native_request_volume_mismatch")
    price = _strict_ctp_account_number(native_request.get("LimitPrice"))
    if (
        price is None
        or not math.isclose(
            price,
            float(request.price),
            rel_tol=0.0,
            abs_tol=1e-9,
        )
    ):
        blockers.append("physical_batch_native_request_price_mismatch")
    if not str(native_request.get("OrderRef", "") or "").strip():
        blockers.append("physical_batch_native_request_order_ref_missing")
    return list(dict.fromkeys(blockers))


def _canonical_order_snapshot(
    orders: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Return an order-state representation suitable for sandwich equality."""

    canonical: list[dict[str, Any]] = []
    seen: set[str] = set()
    blockers: list[str] = []
    for index, order in enumerate(orders):
        identity = str(order.get("order_identity", "") or "")
        if not identity:
            blockers.append(f"final_order_snapshot_identity_missing:index={index}")
            continue
        if identity in seen:
            blockers.append(
                f"final_order_snapshot_duplicate_identity:{identity}"
            )
            continue
        seen.add(identity)
        canonical.append(
            {
                "order_identity": identity,
                "vt_symbol": str(order.get("vt_symbol", "") or ""),
                "raw_order_status": str(
                    order.get("raw_order_status", "") or ""
                ),
                "status_class": str(order.get("status_class", "") or ""),
                "traded": float(order.get("traded", 0.0)),
                "volume": float(order.get("volume", 0.0)),
                "direction": str(order.get("direction", "") or ""),
                "offset": str(order.get("offset", "") or ""),
            }
        )
    canonical.sort(key=lambda row: row["order_identity"])
    return canonical, blockers


def _canonical_position_snapshot(
    positions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Normalize a complete position query so two epochs can be compared.

    CTP may split one symbol/direction over several callback rows.  Exposure,
    not callback order or query reqid, is the invariant needed at send time.
    """

    aggregated: dict[tuple[str, str], dict[str, Any]] = {}
    for position in positions:
        vt_symbol = _vt_symbol_from_row(position)
        direction = _normalize_direction_text(position.get("direction"))
        key = (vt_symbol, direction)
        item = aggregated.setdefault(
            key,
            {
                "vt_symbol": vt_symbol,
                "direction": direction,
                "volume": 0.0,
                "today_volume": 0.0,
                "yesterday_volume": 0.0,
                "frozen": 0.0,
            },
        )
        for field_name in (
            "volume",
            "today_volume",
            "yesterday_volume",
            "frozen",
        ):
            item[field_name] = round(
                float(item[field_name])
                + _to_float(position.get(field_name), 0.0),
                10,
            )
    return [aggregated[key] for key in sorted(aggregated)]


def _execution_event_watermark(rows: dict[str, Any]) -> dict[str, int]:
    """Return ingress-aware event counts relevant to a submit race.

    The EventEngine consumer can be backlogged.  In live mode gateway ingress
    counters are advanced before enqueue; list lengths remain the fallback for
    unit tests and older callers.
    """

    ingress = rows.get("_execution_event_ingress_counts", {})
    if not isinstance(ingress, dict):
        ingress = {}

    def count(event_name: str, rows_key: str) -> int:
        # In live mode the ingress counter is authoritative.  Order-query
        # callbacks may legitimately append EVENT_ORDER rows, but the gateway
        # wrapper deliberately excludes those synchronous query echoes from
        # the ingress counter.  Taking max(list length, ingress) would undo
        # that distinction and force every non-empty broker history to block.
        if event_name in ingress:
            return max(0, _to_int(ingress.get(event_name), 0))
        return len(rows.get(rows_key, []))

    return {
        "event_order_count": count("order", "orders"),
        "event_trade_count": count("trade", "trades"),
        "event_position_count": count(
            "position", "position_events_unscoped"
        ),
    }


def _final_pre_send_snapshot_epoch(
    td_api: Any,
    rows: dict[str, Any],
    *,
    max_wait_seconds: float,
    readiness_state: CtpReadinessState | None = None,
    monotonic: Callable[[], float] = time.monotonic,
    sleeper: Callable[[float], None] = time.sleep,
    hard_deadline_monotonic: float | None = None,
) -> dict[str, Any]:
    """Run order-position-order under one bounded final pre-send budget."""

    started = monotonic()
    deadline = started + max(0.0, float(max_wait_seconds))
    if hard_deadline_monotonic is not None:
        deadline = min(deadline, float(hard_deadline_monotonic))
    result: dict[str, Any] = {
        "success": False,
        "confirmed": False,
        "stable": False,
        "blockers": [],
        "order_q1": {},
        "position": {},
        "order_q2": {},
        "positions": [],
        "orders": [],
        "active_orders": [],
        "canonical_q1": [],
        "canonical_q2": [],
        "canonical_positions": [],
        "event_watermark_before_q2": {},
        "event_watermark_after_q2": {},
        "query_watermark": {},
        "q2_completed_monotonic": None,
        "elapsed_seconds": 0.0,
    }

    def remaining_budget() -> float:
        return max(0.0, deadline - monotonic())

    order_q1 = _final_order_query_epoch(
        td_api,
        rows,
        max_wait_seconds=remaining_budget(),
        monotonic=monotonic,
        sleeper=sleeper,
        hard_deadline_monotonic=hard_deadline_monotonic,
    )
    result["order_q1"] = order_q1
    if not order_q1.get("confirmed"):
        result["blockers"] = [
            f"final_snapshot_q1:{blocker}"
            for blocker in order_q1.get("blockers", [])
        ] or ["final_snapshot_q1:unconfirmed"]
        result["elapsed_seconds"] = max(0.0, monotonic() - started)
        return result

    position = _final_position_query_epoch(
        td_api,
        rows,
        max_wait_seconds=remaining_budget(),
        monotonic=monotonic,
        sleeper=sleeper,
        hard_deadline_monotonic=hard_deadline_monotonic,
    )
    result["position"] = position
    if not position.get("confirmed"):
        result["blockers"] = [
            f"final_snapshot_position:{blocker}"
            for blocker in position.get("blockers", [])
        ] or ["final_snapshot_position:unconfirmed"]
        result["elapsed_seconds"] = max(0.0, monotonic() - started)
        return result
    if readiness_state is not None:
        # The final position epoch supersedes the readiness-era reqid.  Keep
        # the later transport gate bound to the same fresh evidence instead of
        # making it re-evaluate callbacks against a stale expected reqid.
        readiness_state.expected_position_reqid = _to_int(
            position.get("reqid"), -1
        )

    # EVENT_POSITION generated by our own position query is unscoped and may
    # be drained later by EventEngine.  Keep its count for audit, while the
    # second authoritative position epoch below is what resolves its meaning.
    # EVENT_ORDER/TRADE changes after this point are always fail-closed.
    result["event_watermark_before_q2"] = _execution_event_watermark(rows)
    order_q2 = _final_order_query_epoch(
        td_api,
        rows,
        max_wait_seconds=remaining_budget(),
        monotonic=monotonic,
        sleeper=sleeper,
        hard_deadline_monotonic=hard_deadline_monotonic,
    )
    # This cutoff shares the same monotonic clock as EVENT_TICK collection.
    # A quote already buffered before the final Q2 callback cannot authorize
    # the subsequent send, even when its exchange timestamp is still fresh.
    result["q2_completed_monotonic"] = monotonic()
    result["event_watermark_after_q2"] = _execution_event_watermark(rows)
    result["order_q2"] = order_q2
    # Bind the later physical batch to the exact final Q2 owned by this
    # snapshot.  Never recapture td_api.reqid/last-query at bundle assembly:
    # an unrelated query could race after Q2 and otherwise become the
    # accepted baseline.
    result["query_watermark"] = {
        "broker_id": str(getattr(td_api, "brokerid", "") or ""),
        "investor_id": str(getattr(td_api, "userid", "") or ""),
        "td_reqid_before_batch": _to_int(order_q2.get("reqid"), -1),
        "ctp_last_query_monotonic": order_q2.get(
            "requested_at_monotonic"
        ),
    }
    if not order_q2.get("confirmed"):
        result["blockers"] = [
            f"final_snapshot_q2:{blocker}"
            for blocker in order_q2.get("blockers", [])
        ] or ["final_snapshot_q2:unconfirmed"]
        result["elapsed_seconds"] = max(0.0, monotonic() - started)
        return result

    canonical_q1, canonical_q1_blockers = _canonical_order_snapshot(
        list(order_q1.get("orders", []))
    )
    canonical_q2, canonical_q2_blockers = _canonical_order_snapshot(
        list(order_q2.get("orders", []))
    )
    result["canonical_q1"] = canonical_q1
    result["canonical_q2"] = canonical_q2
    result["positions"] = list(position.get("positions", []))
    result["canonical_positions"] = _canonical_position_snapshot(
        result["positions"]
    )
    result["orders"] = list(order_q2.get("orders", []))
    result["active_orders"] = list(order_q2.get("active_orders", []))
    result["blockers"].extend(canonical_q1_blockers)
    result["blockers"].extend(canonical_q2_blockers)
    if canonical_q1 != canonical_q2:
        result["blockers"].append("final_order_snapshot_changed_during_sandwich")
    result["blockers"] = list(dict.fromkeys(result["blockers"]))
    if not result["blockers"]:
        result.update({"success": True, "confirmed": True, "stable": True})
    result["elapsed_seconds"] = max(0.0, monotonic() - started)
    return result


def _final_ctp_transport_blockers(
    td_api: Any,
    rows: dict[str, list[dict[str, Any]]],
    readiness_state: CtpReadinessState,
) -> list[str]:
    flags = _ctp_connection_flags(rows, td_api=td_api, readiness_state=readiness_state)
    _, blockers = _ctp_connection_ready(flags, account_required=readiness_state.account_required)
    return blockers


def _connect_ctp_without_timer_queries(
    main_engine: Any,
    ctp_gateway: Any,
    event_engine: Any,
) -> None:
    """Connect while suppressing vn.py's automatic timer-driven read queries."""

    original_init_query = ctp_gateway.init_query
    ctp_gateway.init_query = lambda: None
    try:
        main_engine.connect(_ctp_setting_from_env(), "CTP")
    finally:
        ctp_gateway.init_query = original_init_query
    # Defensive cleanup for gateway variants that register outside init_query.
    event_engine.unregister(EVENT_TIMER, ctp_gateway.process_timer_event)


@contextmanager
def _instrument_ctp_readiness_callbacks(
    td_api_class: Any,
    rows: dict[str, list[dict[str, Any]]],
    *,
    on_front_disconnected: Callable[[int], None] | None = None,
) -> Iterator[None]:
    original_settlement_rsp = td_api_class.onRspSettlementInfoConfirm
    original_account_rsp = td_api_class.onRspQryTradingAccount
    max_order_volume_rsp_existed = hasattr(
        td_api_class, "onRspQryMaxOrderVolume"
    )
    original_max_order_volume_rsp = getattr(
        td_api_class, "onRspQryMaxOrderVolume", None
    )
    original_position_rsp = td_api_class.onRspQryInvestorPosition
    order_rsp_existed = hasattr(td_api_class, "onRspQryOrder")
    original_order_rsp = getattr(td_api_class, "onRspQryOrder", None)
    trade_rsp_existed = hasattr(td_api_class, "onRspQryTrade")
    original_trade_rsp = getattr(td_api_class, "onRspQryTrade", None)
    order_insert_existed = hasattr(td_api_class, "reqOrderInsert")
    original_order_insert = getattr(td_api_class, "reqOrderInsert", None)
    order_action_existed = hasattr(td_api_class, "reqOrderAction")
    original_order_action = getattr(td_api_class, "reqOrderAction", None)
    front_disconnected_existed = hasattr(td_api_class, "onFrontDisconnected")
    original_front_disconnected = getattr(
        td_api_class,
        "onFrontDisconnected",
        None,
    )

    def _callback_row(data: Any, error: Any, reqid: int, last: bool) -> dict[str, Any]:
        if error is None or error == {}:
            error_id = 0
        elif isinstance(error, dict):
            error_id = _to_int(error.get("ErrorID"), 0)
        else:
            error_id = -1
        return {
            "reqid": reqid,
            "last": bool(last),
            "has_data": bool(data),
            "error_id": error_id,
            "error_msg": str(error.get("ErrorMsg", "") or "") if isinstance(error, dict) else "",
            "received_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    def instrumented_settlement_rsp(self: Any, data: dict, error: dict, reqid: int, last: bool) -> Any:
        row = _callback_row(data, error, reqid, last)
        rows["settlement_callbacks"].append(row)
        if row["error_id"] or not row["last"]:
            return None
        return original_settlement_rsp(self, data, error, reqid, last)

    def instrumented_account_rsp(self: Any, data: dict, error: dict, reqid: int, last: bool) -> Any:
        row = _callback_row(data, error, reqid, last)
        row["account_id"] = str(data.get("AccountID", "") or "") if isinstance(data, dict) else ""
        if isinstance(data, dict):
            row.update(
                {
                    "broker_id": str(data.get("BrokerID", "") or ""),
                    "available": data.get("Available"),
                    "curr_margin": data.get("CurrMargin"),
                    "raw_evidence_sha256": hashlib.sha256(
                        json.dumps(
                            data,
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                            default=str,
                        ).encode("utf-8")
                    ).hexdigest(),
                }
            )
        rows["account_query_callbacks"].append(row)
        epoch = rows.get("_final_account_funds_epoch", {})
        active_reqid = (
            _to_int(epoch.get("active_reqid"), -1)
            if isinstance(epoch, dict)
            else -1
        )
        if active_reqid >= 0 and reqid == active_reqid:
            if row["error_id"] == 0 and isinstance(data, dict) and data:
                epoch.setdefault("raw_rows", []).append(dict(data))
            if row["last"]:
                epoch["complete_reqid"] = reqid
        if row["error_id"] or not isinstance(data, dict):
            return None
        return original_account_rsp(self, data, error, reqid, last)

    def instrumented_max_order_volume_rsp(
        self: Any,
        data: dict,
        error: dict,
        reqid: int,
        last: bool,
    ) -> Any:
        row = _callback_row(data, error, reqid, last)
        if isinstance(data, dict):
            for field_name in (
                "BrokerID",
                "InvestorID",
                "InstrumentID",
                "ExchangeID",
                "Direction",
                "OffsetFlag",
                "HedgeFlag",
                "InvestUnitID",
                "MaxVolume",
            ):
                row[field_name] = data.get(field_name)
            row["raw_evidence_sha256"] = hashlib.sha256(
                json.dumps(
                    data,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                    default=str,
                ).encode("utf-8")
            ).hexdigest()
        epoch = rows.get("_max_order_volume_query_epoch", {})
        active_reqid = (
            _to_int(epoch.get("active_reqid"), -1)
            if isinstance(epoch, dict)
            else -1
        )
        if active_reqid >= 0 and reqid != active_reqid:
            row["ignored_outside_active_epoch"] = True
            rows.setdefault("max_order_volume_query_callbacks", []).append(row)
            return None
        rows.setdefault("max_order_volume_query_callbacks", []).append(row)
        if row["error_id"]:
            return None
        if isinstance(epoch, dict) and active_reqid == reqid:
            if isinstance(data, dict) and data:
                epoch.setdefault("raw_rows", []).append(dict(data))
            if row["last"]:
                epoch["complete_reqid"] = reqid
        if callable(original_max_order_volume_rsp):
            return original_max_order_volume_rsp(
                self, data, error, reqid, last
            )
        return None

    def instrumented_position_rsp(self: Any, data: dict, error: dict, reqid: int, last: bool) -> Any:
        row = _callback_row(data, error, reqid, last)
        row["instrument"] = str(data.get("InstrumentID", "") or "") if isinstance(data, dict) else ""
        row["position"] = data.get("Position", "") if isinstance(data, dict) else ""
        epoch = rows.get("_position_query_epoch", {})
        active_reqid = _to_int(epoch.get("active_reqid"), -1) if isinstance(epoch, dict) else -1
        if active_reqid >= 0 and reqid != active_reqid:
            row["ignored_outside_active_epoch"] = True
            rows["position_query_callbacks"].append(row)
            return None
        rows["position_query_callbacks"].append(row)
        if row["error_id"]:
            if isinstance(epoch, dict) and active_reqid == reqid:
                epoch["pending_callbacks"] = []
            return None
        if not isinstance(epoch, dict) or active_reqid < 0:
            return original_position_rsp(self, data, error, reqid, last)
        pending = epoch.setdefault("pending_callbacks", [])
        pending.append((data, error, reqid, last))
        if not row["last"]:
            return None
        epoch["complete_reqid"] = reqid
        symbol_map = rows.get("_position_vt_symbol_by_instrument", {})
        authoritative_rows: list[dict[str, Any]] = []
        identity_blockers: list[str] = []
        strict_identity = bool(epoch.get("strict_identity"))
        expected_broker_id = str(epoch.get("expected_broker_id", "") or "")
        expected_investor_id = str(epoch.get("expected_investor_id", "") or "")
        for row_index, (callback_data, _, callback_reqid, _) in enumerate(
            list(pending)
        ):
            if callback_data is None or callback_data == {}:
                continue
            converted = _raw_ctp_position_row(
                callback_data,
                reqid=callback_reqid,
                vt_symbol_by_instrument=(
                    symbol_map if isinstance(symbol_map, dict) else {}
                ),
            )
            if strict_identity:
                prefix = f"final_position_query_row_invalid:index={row_index}"
                if not isinstance(callback_data, dict):
                    identity_blockers.append(f"{prefix}:not_mapping")
                    continue
                broker_id = str(callback_data.get("BrokerID", "") or "").strip()
                investor_id = str(
                    callback_data.get("InvestorID", "") or ""
                ).strip()
                raw_direction = str(
                    callback_data.get("PosiDirection", "") or ""
                ).strip()
                raw_position = pd.to_numeric(
                    callback_data.get("Position"), errors="coerce"
                )
                if broker_id != expected_broker_id:
                    identity_blockers.append(
                        f"{prefix}:BrokerID={broker_id or '<missing>'}"
                    )
                if investor_id != expected_investor_id:
                    identity_blockers.append(
                        f"{prefix}:InvestorID={investor_id or '<missing>'}"
                    )
                if raw_direction not in {"2", "3"}:
                    identity_blockers.append(
                        f"{prefix}:PosiDirection={raw_direction or '<missing>'}"
                    )
                if pd.isna(raw_position) or float(raw_position) < 0:
                    identity_blockers.append(
                        f"{prefix}:Position={callback_data.get('Position', '<missing>')}"
                    )
                if converted is None:
                    identity_blockers.append(f"{prefix}:InstrumentID=<missing>")
                    continue
            if converted is not None:
                authoritative_rows.append(converted)
        rows.setdefault("positions", []).clear()
        rows["positions"].extend(authoritative_rows)
        epoch["authoritative_position_rows"] = len(authoritative_rows)
        epoch["identity_blockers"] = list(dict.fromkeys(identity_blockers))
        result: Any = None
        for callback_args in list(pending):
            result = original_position_rsp(self, *callback_args)
        epoch["pending_callbacks"] = []
        return result

    def forward_original_order_query_callback(
        self: Any,
        data: dict,
        error: dict,
        reqid: int,
        last: bool,
    ) -> Any:
        """Let upstream publish query rows without counting them as async races."""

        if not callable(original_order_rsp):
            return None
        previous_depth = int(
            getattr(_ORDER_QUERY_FORWARD_CONTEXT, "depth", 0)
        )
        _ORDER_QUERY_FORWARD_CONTEXT.depth = previous_depth + 1
        try:
            return original_order_rsp(self, data, error, reqid, last)
        finally:
            _ORDER_QUERY_FORWARD_CONTEXT.depth = previous_depth

    def instrumented_order_rsp(self: Any, data: dict, error: dict, reqid: int, last: bool) -> Any:
        row = _callback_row(data, error, reqid, last)
        if isinstance(data, dict):
            row.update(
                {
                    "instrument": str(data.get("InstrumentID", "") or ""),
                    "exchange": str(data.get("ExchangeID", "") or ""),
                    "order_ref": str(data.get("OrderRef", "") or ""),
                    "order_sys_id": str(data.get("OrderSysID", "") or ""),
                    "order_status": str(data.get("OrderStatus", "") or ""),
                }
            )
        epoch = rows.get("_order_query_epoch", {})
        active_reqid = (
            _to_int(epoch.get("active_reqid"), -1)
            if isinstance(epoch, dict)
            else -1
        )
        if active_reqid >= 0 and reqid != active_reqid:
            row["ignored_outside_active_epoch"] = True
            rows.setdefault("order_query_callbacks", []).append(row)
            return None
        rows.setdefault("order_query_callbacks", []).append(row)
        if row["error_id"]:
            if isinstance(epoch, dict) and active_reqid == reqid:
                epoch["pending_callbacks"] = []
            return None
        if not isinstance(epoch, dict) or active_reqid < 0:
            return forward_original_order_query_callback(
                self, data, error, reqid, last
            )

        pending = epoch.setdefault("pending_callbacks", [])
        pending.append((data, error, reqid, last))
        if not row["last"]:
            return None

        epoch["complete_reqid"] = reqid
        authoritative_rows: list[dict[str, Any]] = []
        identity_blockers: list[str] = []
        for row_index, (callback_data, _, callback_reqid, _) in enumerate(
            list(pending)
        ):
            converted, converted_blockers = _raw_ctp_order_row(
                callback_data,
                reqid=callback_reqid,
                row_index=row_index,
            )
            identity_blockers.extend(converted_blockers)
            if converted is not None:
                authoritative_rows.append(converted)
        epoch["authoritative_orders"] = authoritative_rows
        epoch["identity_blockers"] = identity_blockers
        epoch["authoritative_order_rows"] = len(authoritative_rows)

        result: Any = None
        if not identity_blockers and callable(original_order_rsp):
            for callback_args in list(pending):
                result = forward_original_order_query_callback(
                    self, *callback_args
                )
        epoch["pending_callbacks"] = []
        return result

    def instrumented_trade_rsp(self: Any, data: dict, error: dict, reqid: int, last: bool) -> Any:
        row = _callback_row(data, error, reqid, last)
        rows.setdefault("trade_query_callbacks", []).append(row)
        epoch = rows.get("_trade_query_epoch", {})
        active_reqid = _to_int(epoch.get("active_reqid"), -1) if isinstance(epoch, dict) else -1
        if active_reqid >= 0 and reqid != active_reqid:
            row["ignored_outside_active_epoch"] = True
            return None
        if row["error_id"]:
            return None
        if not isinstance(epoch, dict) or active_reqid < 0:
            return original_trade_rsp(self, data, error, reqid, last) if callable(original_trade_rsp) else None
        pending = epoch.setdefault("pending_callbacks", [])
        pending.append((data, error, reqid, last))
        if not last:
            return None
        converted_rows: list[dict[str, Any]] = []
        identity_blockers: list[str] = []
        for index, (callback_data, _, callback_reqid, _) in enumerate(pending):
            converted, converted_blockers = _raw_ctp_trade_row(
                callback_data, reqid=callback_reqid, row_index=index
            )
            identity_blockers.extend(converted_blockers)
            if converted is not None:
                converted_rows.append(converted)
        # CTP TradeID is not globally unique across exchanges.  Keep query
        # duplicate detection aligned with the durable canonical identity
        # ``ctp:<exchange>:<tradeid>`` so DCE/SHFE may legitimately reuse the
        # same textual TradeID while a repeated identity within one exchange
        # remains fail-closed.
        identities = [
            (
                str(row.get("exchange", "") or "").strip().lower(),
                str(row.get("tradeid", "") or "").strip(),
            )
            for row in converted_rows
        ]
        if len(identities) != len(set(identities)):
            identity_blockers.append("final_trade_query_duplicate_trade_identity")
        epoch["authoritative_trades"] = converted_rows
        epoch["identity_blockers"] = identity_blockers
        epoch["complete_reqid"] = reqid
        epoch["pending_callbacks"] = []
        return None

    def instrumented_order_insert(self: Any, data: dict, reqid: int) -> Any:
        audit: dict[str, Any] = {
            "reqid": reqid,
            "requested_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "request_ret": "",
            "exception": "",
            "front_id": str(getattr(self, "frontid", "") or ""),
            "session_id": str(getattr(self, "sessionid", "") or ""),
            "order_ref": str(data.get("OrderRef", "") or ""),
        }
        try:
            ingress_lock = rows.get("_execution_event_ingress_lock")
            guard = (
                ingress_lock
                if hasattr(ingress_lock, "__enter__")
                else nullcontext()
            )
            # Keep the final dynamic gate and the native boundary in one
            # ingress critical section.  Without this shared RLock an
            # external order/trade/position callback could arrive after the
            # gate returned but before reqOrderInsert crossed the process
            # boundary.  The lock is re-entrant because the gate itself takes
            # the same lock while attributing the current batch watermark.
            with guard:
                before_native = rows.get("_before_native_order_insert")
                if not callable(before_native):
                    raise RuntimeError(
                        "stage179_before_native_order_insert_hook_missing"
                    )
                # The hook must durably persist the exact native identity
                # before reqOrderInsert can cross the process boundary.  Any
                # append failure aborts here and therefore proves no native
                # side effect.
                before_native(self, dict(data), reqid)
                result = original_order_insert(self, data, reqid)
            audit["request_ret"] = _to_int(result, -1)
            return result
        except Exception as exc:
            audit["exception"] = repr(exc)
            raise
        finally:
            rows.setdefault("order_insert_requests", []).append(audit)

    def instrumented_order_action(self: Any, data: dict, reqid: int) -> Any:
        audit: dict[str, Any] = {
            "reqid": reqid, "request_ret": "", "exception": "",
            "requested_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        try:
            result = original_order_action(self, data, reqid)
            audit["request_ret"] = _to_int(result, -1)
            return result
        except Exception as exc:
            audit["exception"] = repr(exc)
            raise
        finally:
            rows.setdefault("order_action_requests", []).append(audit)

    def instrumented_front_disconnected(self: Any, reason: int) -> Any:
        ingress_lock = rows.get("_execution_event_ingress_lock")
        guard = (
            ingress_lock
            if hasattr(ingress_lock, "__enter__")
            else nullcontext()
        )
        # Serialize transport invalidation with the same final-native
        # boundary.  A disconnect that wins the lock is visible to the gate;
        # one that loses can only be observed after the native call returns.
        with guard:
            rows["_stage179_transport_disconnect_count"] = (
                _to_int(
                    rows.get("_stage179_transport_disconnect_count"), 0
                )
                + 1
            )
            if on_front_disconnected is not None:
                on_front_disconnected(int(reason))
            if callable(original_front_disconnected):
                return original_front_disconnected(self, reason)
            return None

    try:
        td_api_class.onRspSettlementInfoConfirm = instrumented_settlement_rsp
        td_api_class.onRspQryTradingAccount = instrumented_account_rsp
        td_api_class.onRspQryMaxOrderVolume = (
            instrumented_max_order_volume_rsp
        )
        td_api_class.onRspQryInvestorPosition = instrumented_position_rsp
        td_api_class.onRspQryOrder = instrumented_order_rsp
        td_api_class.onRspQryTrade = instrumented_trade_rsp
        if order_insert_existed and callable(original_order_insert):
            td_api_class.reqOrderInsert = instrumented_order_insert
        if order_action_existed and callable(original_order_action):
            td_api_class.reqOrderAction = instrumented_order_action
        if front_disconnected_existed:
            td_api_class.onFrontDisconnected = instrumented_front_disconnected
        yield
    finally:
        td_api_class.onRspSettlementInfoConfirm = original_settlement_rsp
        td_api_class.onRspQryTradingAccount = original_account_rsp
        if max_order_volume_rsp_existed:
            td_api_class.onRspQryMaxOrderVolume = (
                original_max_order_volume_rsp
            )
        else:
            delattr(td_api_class, "onRspQryMaxOrderVolume")
        td_api_class.onRspQryInvestorPosition = original_position_rsp
        if order_rsp_existed:
            td_api_class.onRspQryOrder = original_order_rsp
        else:
            delattr(td_api_class, "onRspQryOrder")
        if trade_rsp_existed:
            td_api_class.onRspQryTrade = original_trade_rsp
        else:
            delattr(td_api_class, "onRspQryTrade")
        if order_insert_existed:
            td_api_class.reqOrderInsert = original_order_insert
        if order_action_existed:
            td_api_class.reqOrderAction = original_order_action
        if front_disconnected_existed:
            td_api_class.onFrontDisconnected = original_front_disconnected


def _normalize_direction_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"long", "多", "direction.long"}:
        return "long"
    if text in {"short", "空", "direction.short"}:
        return "short"
    return text


def _normalize_offset_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"close", "closetoday", "closeyesterday", "平", "平今", "平昨", "offset.close", "offset.closetoday", "offset.closeyesterday"}:
        return "close"
    if text in {"open", "开", "offset.open"}:
        return "open"
    return text


def _direction_from_payload(value: Any) -> Direction:
    text = _normalize_direction_text(value)
    if text == "long":
        return Direction.LONG
    if text == "short":
        return Direction.SHORT
    raw = str(value or "").strip()
    upper = raw.upper()
    if upper in Direction.__members__:
        return Direction[upper]
    return Direction(raw)


def _offset_from_payload(value: Any) -> Offset:
    text = _normalize_offset_text(value)
    if text == "open":
        return Offset.OPEN
    if text == "close":
        return Offset.CLOSE
    raw = str(value or "").strip()
    upper = raw.upper()
    if upper in Offset.__members__:
        return Offset[upper]
    return Offset(raw)


def _order_type_from_payload(value: Any) -> OrderType:
    raw = str(value or OrderType.LIMIT.value).strip()
    text = raw.lower()
    if text in {"limit", "限价", "ordertype.limit"}:
        return OrderType.LIMIT
    if text in {"market", "市价", "ordertype.market"}:
        return OrderType.MARKET
    upper = raw.upper()
    if upper in OrderType.__members__:
        return OrderType[upper]
    return OrderType(raw)


def _vt_symbol_from_row(row: dict[str, Any]) -> str:
    vt_symbol = str(row.get("vt_symbol", "") or "").strip()
    if vt_symbol:
        return vt_symbol
    symbol = str(row.get("symbol", "") or "").strip()
    exchange = str(row.get("exchange", "") or "").strip()
    return f"{symbol}.{exchange}" if symbol and exchange else symbol


def _split_vt_symbol(vt_symbol: str) -> tuple[str, Exchange | None]:
    if "." not in vt_symbol:
        return vt_symbol, None
    symbol, exchange_text = vt_symbol.rsplit(".", 1)
    try:
        return symbol, Exchange(exchange_text)
    except ValueError:
        return symbol, None


def _price_on_tick(price: float, pricetick: float) -> bool:
    if pricetick <= 0 or price <= 0:
        return True
    units = price / pricetick
    if not math.isfinite(units):
        return False
    return math.isclose(units, round(units), rel_tol=0.0, abs_tol=1e-8)


def _snap_price_to_tick(price: float, pricetick: float, direction: str) -> float:
    if pricetick <= 0 or price <= 0:
        return price
    units = price / pricetick
    if not math.isfinite(units):
        return 0.0
    if direction == "short":
        return round(math.floor(units) * pricetick, 10)
    if direction == "long":
        return round(math.ceil(units) * pricetick, 10)
    return round(round(units) * pricetick, 10)


def _clip_price(price: float, lower: float, upper: float) -> float:
    if lower > 0:
        price = max(price, lower)
    if upper > 0:
        price = min(price, upper)
    return price


def _tick_aligned_price_band(
    lower: float,
    upper: float,
    pricetick: float,
) -> tuple[float, float] | None:
    """Return the inclusive, tick-aligned subset of an exchange price band."""

    if not all(math.isfinite(value) and value > 0 for value in (lower, upper, pricetick)):
        return None
    if lower >= upper:
        return None
    # The epsilon only neutralizes binary float noise at an exact tick.  It is
    # deliberately much smaller than the tolerance used by _price_on_tick.
    lower_units = lower / pricetick
    upper_units = upper / pricetick
    if not math.isfinite(lower_units) or not math.isfinite(upper_units):
        return None
    epsilon = 1e-10
    aligned_lower = math.ceil(lower_units - epsilon) * pricetick
    aligned_upper = math.floor(upper_units + epsilon) * pricetick
    if aligned_lower > aligned_upper or aligned_lower <= 0:
        return None
    return aligned_lower, aligned_upper


def _valid_ctp_market_price(value: Any) -> float:
    """Normalize a CTP price and reject missing/MAX_FLOAT sentinel values."""

    number = _to_float(value, 0.0)
    if (
        not math.isfinite(number)
        or number <= 0
        or number >= sys.float_info.max / 2
    ):
        return 0.0
    return number


def _retry_reclaim_trigger(
    intent_row: Mapping[str, Any],
) -> tuple[float, str, str]:
    """Return a finite CTP trigger, preserving explicit-invalid evidence."""

    for field_name in (
        "retry_trigger_price",
        "strategy_entry_price",
        "retry_original_fill_price",
    ):
        if field_name not in intent_row:
            continue
        raw_value = intent_row.get(field_name)
        if raw_value is None or (
            isinstance(raw_value, str) and not raw_value.strip()
        ):
            continue
        invalid_explicit_value = isinstance(raw_value, bool)
        if not invalid_explicit_value:
            try:
                invalid_explicit_value = bool(pd.isna(raw_value))
            except (TypeError, ValueError):
                invalid_explicit_value = True
        candidate = _valid_ctp_market_price(raw_value)
        if invalid_explicit_value or candidate <= 0:
            return 0.0, field_name, "invalid"
        return candidate, field_name, "valid"
    return 0.0, "", "missing"


def _tick_datetime(row: dict[str, Any]) -> datetime | None:
    for key in ("localtime", "datetime", "snapshot_at", "generated_at", "received_at"):
        if key not in row:
            continue
        parsed = _parse_dt(row.get(key))
        if parsed is not None:
            return parsed
    return None


def _tick_age_seconds(row: dict[str, Any] | None) -> float | None:
    if not row:
        return None
    parsed = _tick_datetime(row)
    if parsed is None:
        return None
    now = datetime.now(parsed.tzinfo) if parsed.tzinfo is not None else datetime.now()
    return round((now - parsed).total_seconds(), 3)


def _tick_age_is_fresh(age_seconds: float | None, max_tick_age_seconds: int) -> bool:
    return bool(
        age_seconds is not None
        and age_seconds >= -ALLOWED_TICK_CLOCK_SKEW_SECONDS
        and age_seconds <= max_tick_age_seconds
    )


def _latest_fresh_tick(rows: list[dict[str, Any]], vt_symbol: str, max_tick_age_seconds: int) -> tuple[dict[str, Any] | None, float | None]:
    candidates: list[tuple[float, int, dict[str, Any], float | None]] = []
    for index, row in enumerate(rows):
        if _vt_symbol_from_row(row) != vt_symbol:
            continue
        dt = _tick_datetime(row)
        age = _tick_age_seconds(row)
        if dt is None or not _tick_age_is_fresh(age, max_tick_age_seconds):
            continue
        candidates.append((dt.timestamp(), index, row, age))
    if not candidates:
        return None, None
    _, _, row, age = sorted(candidates, key=lambda item: (item[0], item[1]))[-1]
    return row, age


def _latest_fresh_tick_from_file(vt_symbol: str, max_tick_age_seconds: int) -> tuple[dict[str, Any] | None, float | None]:
    ticks = _read_csv_maybe(READONLY_TICKS_PATH)
    if ticks.empty:
        return None, None
    return _latest_fresh_tick(ticks.to_dict(orient="records"), vt_symbol, max_tick_age_seconds)


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


def _subscribe_and_wait_fresh_tick(
    main_engine: MainEngine,
    vt_symbol: str,
    rows: dict[str, list[dict[str, Any]]],
    *,
    wait_seconds: float,
    max_tick_age_seconds: int,
    not_before_received_monotonic: float | None = None,
) -> tuple[dict[str, Any] | None, float | None, str]:
    symbol, exchange = _split_vt_symbol(vt_symbol)
    if not symbol or exchange is None:
        return None, None, "final_reprice_invalid_vt_symbol"
    try:
        main_engine.subscribe(SubscribeRequest(symbol=symbol, exchange=exchange), "CTP")
    except Exception as exc:
        return None, None, f"final_reprice_subscribe_exception:{exc!r}"
    deadline = time.monotonic() + max(0.0, float(wait_seconds))
    while True:
        tick_rows = rows.get("ticks", [])
        if not_before_received_monotonic is not None:
            causal_rows: list[dict[str, Any]] = []
            for row in tick_rows:
                received = pd.to_numeric(
                    row.get("received_monotonic"), errors="coerce"
                )
                if pd.isna(received):
                    continue
                if float(received) > float(not_before_received_monotonic):
                    causal_rows.append(row)
            tick_rows = causal_rows
        tick, age = _latest_fresh_tick(
            tick_rows, vt_symbol, max_tick_age_seconds
        )
        if tick is not None:
            return tick, age, "ctp_event_tick"
        if time.monotonic() >= deadline:
            break
        time.sleep(min(0.1, max(0.0, deadline - time.monotonic())))
    return None, None, "no_fresh_ctp_tick_after_subscribe"


def _final_close_reprice(
    main_engine: MainEngine,
    rows: dict[str, list[dict[str, Any]]],
    intent_row: dict[str, Any],
    req: OrderRequest,
    *,
    max_tick_age_seconds: int,
    tick_wait_seconds: int,
    not_before_tick_received_monotonic: float | None = None,
    allow_tick_file_fallback: bool = True,
) -> dict[str, Any]:
    source = str(intent_row.get("source", "") or "").strip()
    offset_text = _normalize_offset_text(req.offset.value)
    intraday_close = source == "stage904_c9_intraday_close" and offset_text == "close"
    intraday_retry_open = source == "stage904_c9_intraday_retry_open" and offset_text == "open"
    vt_symbol = str(intent_row.get("vt_symbol", "") or req.vt_symbol).strip()
    original_price = float(req.price)
    result: dict[str, Any] = {
        "final_reprice_status": "skipped_not_stage904_intraday_close",
        "final_reprice_source": "",
        "final_reprice_reason": "",
        "final_reprice_price_before": original_price,
        "final_reprice_price_after": original_price,
        "final_reprice_tick_age_seconds": "",
        "final_reprice_bid_price_1": "",
        "final_reprice_ask_price_1": "",
        "final_reprice_live_price": "",
        "final_reprice_basis_price": "",
        "final_reprice_protection_ticks": "",
        "final_reprice_tick_not_before_monotonic": (
            not_before_tick_received_monotonic
            if not_before_tick_received_monotonic is not None
            else ""
        ),
        "final_reprice_tick_file_fallback_allowed": int(
            bool(allow_tick_file_fallback)
        ),
    }
    if not intraday_close and not intraday_retry_open:
        return result

    tick, tick_age, tick_source = _subscribe_and_wait_fresh_tick(
        main_engine,
        vt_symbol,
        rows,
        wait_seconds=tick_wait_seconds,
        max_tick_age_seconds=max_tick_age_seconds,
        not_before_received_monotonic=not_before_tick_received_monotonic,
    )
    if tick is None and allow_tick_file_fallback:
        tick, tick_age = _latest_fresh_tick_from_file(vt_symbol, max_tick_age_seconds)
        tick_source = "stage608_tick_file" if tick is not None else tick_source
    if tick is None:
        result["final_reprice_status"] = "skipped_no_fresh_tick_keep_stage905_price"
        result["final_reprice_reason"] = tick_source
        return result

    config = build_phase_d_config()
    protection_ticks = max(1, int(config.hard_limits.max_slippage_ticks))
    pricetick = _to_float(intent_row.get("pricetick"), 0.0)
    direction_text = _normalize_direction_text(req.direction.value)
    live_price, live_price_source = _tick_price(tick)
    bid = _tick_value(tick, "bid_price_1")
    ask = _tick_value(tick, "ask_price_1")
    lower = _tick_value(tick, "limit_down", "lower_limit", "limit_down_price") or _to_float(intent_row.get("live_limit_down"), 0.0)
    upper = _tick_value(tick, "limit_up", "upper_limit", "limit_up_price") or _to_float(intent_row.get("live_limit_up"), 0.0)
    tick_value = pricetick if pricetick > 0 else 0.0

    if intraday_retry_open:
        retry_trigger, retry_trigger_source, retry_trigger_status = (
            _retry_reclaim_trigger(intent_row)
        )
        if retry_trigger_status == "invalid":
            result["final_reprice_status"] = (
                "blocked_retry_reclaim_trigger_invalid"
            )
            result["final_reprice_reason"] = (
                f"{retry_trigger_source}="
                f"{intent_row.get(retry_trigger_source)}"
            )
            return result
        if retry_trigger_status == "missing":
            result["final_reprice_status"] = "blocked_retry_reclaim_trigger_missing"
            result["final_reprice_reason"] = "retry_trigger_price/strategy_entry_price/retry_original_fill_price missing"
            return result
        if bid <= 0 or ask <= 0:
            result["final_reprice_status"] = "blocked_retry_reclaim_executable_quote_missing"
            result["final_reprice_reason"] = f"bid={bid};ask={ask};live_price_source={live_price_source}"
            return result
        if bid > ask:
            result["final_reprice_status"] = "blocked_retry_reclaim_crossed_quote"
            result["final_reprice_reason"] = f"bid={bid};ask={ask}"
            return result
        if direction_text == "short":
            executable_price = bid
            executable_price_source = "bid_price_1"
        elif direction_text == "long":
            executable_price = ask
            executable_price_source = "ask_price_1"
        else:
            result["final_reprice_status"] = "blocked_retry_reclaim_invalid_direction"
            result["final_reprice_reason"] = f"direction={direction_text}"
            return result
        reclaim_still_favorable = (
            direction_text == "short" and executable_price <= retry_trigger
        ) or (
            direction_text == "long" and executable_price >= retry_trigger
        )
        if not reclaim_still_favorable:
            result["final_reprice_status"] = "blocked_retry_reclaim_no_longer_favorable"
            result["final_reprice_reason"] = (
                f"direction={direction_text};executable_price={executable_price};retry_trigger={retry_trigger};"
                f"retry_trigger_source={retry_trigger_source};"
                f"executable_price_source={executable_price_source}"
            )
            result["final_reprice_tick_age_seconds"] = tick_age if tick_age is not None else ""
            result["final_reprice_bid_price_1"] = bid
            result["final_reprice_ask_price_1"] = ask
            result["final_reprice_live_price"] = live_price
            return result

    if direction_text == "short":
        basis = bid if intraday_retry_open else bid if bid > 0 else live_price if live_price > 0 else original_price
        price = basis - protection_ticks * tick_value if tick_value > 0 else basis
        side_reason = "marketable_sell_retry_open_final_reprice" if intraday_retry_open else "marketable_sell_close_final_reprice"
    elif direction_text == "long":
        basis = ask if intraday_retry_open else ask if ask > 0 else live_price if live_price > 0 else original_price
        price = basis + protection_ticks * tick_value if tick_value > 0 else basis
        side_reason = "marketable_buy_retry_open_final_reprice" if intraday_retry_open else "marketable_buy_close_final_reprice"
    else:
        result["final_reprice_status"] = "skipped_invalid_direction_keep_stage905_price"
        result["final_reprice_reason"] = f"direction={direction_text}"
        return result

    price = _clip_price(price, lower, upper)
    snap_reason = ""
    if pricetick and price > 0 and not _price_on_tick(price, pricetick):
        before_snap = price
        price = _snap_price_to_tick(price, pricetick, direction_text)
        snap_reason = f";snapped_to_tick:{before_snap}->{price}"
    if price <= 0:
        result["final_reprice_status"] = "skipped_invalid_reprice_keep_stage905_price"
        result["final_reprice_reason"] = f"{side_reason};basis={basis};live_price_source={live_price_source}"
        return result

    req.price = float(price)
    result.update(
        {
            "final_reprice_status": "applied",
            "final_reprice_source": tick_source,
            "final_reprice_reason": (
                f"{side_reason};basis={basis};live_price_source={live_price_source};"
                f"protection_ticks={protection_ticks};pricetick={pricetick}{snap_reason}"
            ),
            "final_reprice_price_after": req.price,
            "final_reprice_tick_age_seconds": tick_age if tick_age is not None else "",
            "final_reprice_bid_price_1": bid,
            "final_reprice_ask_price_1": ask,
            "final_reprice_live_price": live_price,
            "final_reprice_basis_price": basis,
            "final_reprice_protection_ticks": protection_ticks,
        }
    )
    return result


def _strict_post_q2_final_reprice(
    main_engine: MainEngine,
    rows: dict[str, list[dict[str, Any]]],
    intent_row: dict[str, Any],
    req: OrderRequest,
    *,
    max_tick_age_seconds: int,
    q2_completed_monotonic: float | None,
    tick_wait_seconds: int,
    status_namespace: str,
    expected_offset: str | None = None,
    retry_reclaim_required: bool = False,
) -> dict[str, Any]:
    """Build one executable limit price from a single causal CTP session.

    The Stage905 theoretical price is never an execution fallback here.  A
    missing live contract, post-Q2 CTP tick, executable quote, price tick, or
    exchange price band blocks the order before the broker API slot.
    """

    if status_namespace not in {"stage372", "c9"}:
        raise ValueError("strict_reprice_status_namespace_invalid")

    def blocked(suffix: str) -> str:
        return f"blocked_{status_namespace}_{suffix}"

    original_price = float(req.price)
    vt_symbol = str(intent_row.get("vt_symbol", "") or req.vt_symbol).strip()
    result: dict[str, Any] = {
        "final_reprice_status": blocked("price_gate_not_evaluated"),
        "final_reprice_source": "",
        "final_reprice_reason": "",
        "final_reprice_price_before": original_price,
        "final_reprice_price_after": original_price,
        "final_reprice_tick_age_seconds": "",
        "final_reprice_bid_price_1": "",
        "final_reprice_ask_price_1": "",
        "final_reprice_live_price": "",
        "final_reprice_basis_price": "",
        "final_reprice_protection_ticks": "",
        "final_reprice_intent_pricetick": "",
        "final_reprice_live_contract_pricetick": "",
        "final_reprice_limit_down": "",
        "final_reprice_limit_up": "",
        "final_reprice_aligned_limit_down": "",
        "final_reprice_aligned_limit_up": "",
        "final_reprice_tick_not_before_monotonic": "",
        "final_reprice_tick_file_fallback_allowed": 0,
        "post_sandwich_reprice": 1,
    }

    offset_text = _normalize_offset_text(req.offset.value)
    if expected_offset is not None and offset_text != expected_offset:
        result["final_reprice_status"] = blocked("source_offset_mismatch")
        result["final_reprice_reason"] = (
            f"expected_offset={expected_offset};actual_offset={offset_text}"
        )
        return result

    cutoff = pd.to_numeric(q2_completed_monotonic, errors="coerce")
    if (
        pd.isna(cutoff)
        or not math.isfinite(float(cutoff))
        or float(cutoff) <= 0
    ):
        result["final_reprice_status"] = "blocked_post_snapshot_tick_cutoff_missing"
        result["final_reprice_reason"] = "q2_completed_monotonic missing or invalid"
        return result
    cutoff_value = float(cutoff)
    result["final_reprice_tick_not_before_monotonic"] = cutoff_value

    if vt_symbol != req.vt_symbol:
        result["final_reprice_status"] = blocked("vt_symbol_mismatch")
        result["final_reprice_reason"] = (
            f"intent_vt_symbol={vt_symbol};request_vt_symbol={req.vt_symbol}"
        )
        return result

    tick, tick_age, tick_source = _subscribe_and_wait_fresh_tick(
        main_engine,
        vt_symbol,
        rows,
        wait_seconds=max(0.0, float(tick_wait_seconds)),
        max_tick_age_seconds=max_tick_age_seconds,
        not_before_received_monotonic=cutoff_value,
    )
    if tick is None:
        result["final_reprice_status"] = (
            blocked("no_fresh_post_q2_ctp_tick")
        )
        result["final_reprice_reason"] = tick_source
        return result
    result["final_reprice_source"] = tick_source
    result["final_reprice_tick_age_seconds"] = (
        tick_age if tick_age is not None else ""
    )
    if tick_source != "ctp_event_tick":
        result["final_reprice_status"] = blocked("non_ctp_event_tick")
        result["final_reprice_reason"] = f"tick_source={tick_source}"
        return result
    tick_gateway_name = str(tick.get("gateway_name", "") or "").strip().upper()
    if tick_gateway_name != "CTP":
        result["final_reprice_status"] = blocked("tick_not_ctp")
        result["final_reprice_reason"] = f"gateway_name={tick_gateway_name}"
        return result

    received_monotonic = pd.to_numeric(
        tick.get("received_monotonic"), errors="coerce"
    )
    if (
        pd.isna(received_monotonic)
        or not math.isfinite(float(received_monotonic))
        or float(received_monotonic) <= 0
        or float(received_monotonic) <= cutoff_value
    ):
        result["final_reprice_status"] = (
            blocked("tick_not_strictly_after_q2")
        )
        result["final_reprice_reason"] = (
            f"received_monotonic={tick.get('received_monotonic')};q2={cutoff_value}"
        )
        return result
    if not _tick_age_is_fresh(tick_age, max_tick_age_seconds):
        result["final_reprice_status"] = blocked("tick_not_fresh")
        result["final_reprice_reason"] = f"tick_age_seconds={tick_age}"
        return result

    get_contract = getattr(main_engine, "get_contract", None)
    contract = None
    if callable(get_contract):
        try:
            contract = get_contract(req.vt_symbol)
        except Exception as exc:
            result["final_reprice_status"] = (
                blocked("live_contract_query_exception")
            )
            result["final_reprice_reason"] = repr(exc)
            return result
    if contract is None:
        result["final_reprice_status"] = blocked("live_contract_missing")
        result["final_reprice_reason"] = f"vt_symbol={req.vt_symbol}"
        return result
    gateway_name = str(getattr(contract, "gateway_name", "") or "").strip().upper()
    if gateway_name != "CTP":
        result["final_reprice_status"] = blocked("live_contract_not_ctp")
        result["final_reprice_reason"] = f"gateway_name={gateway_name}"
        return result
    contract_vt_symbol = str(getattr(contract, "vt_symbol", "") or "").strip()
    if contract_vt_symbol != req.vt_symbol:
        result["final_reprice_status"] = (
            blocked("live_contract_vt_symbol_mismatch")
        )
        result["final_reprice_reason"] = (
            f"contract_vt_symbol={contract_vt_symbol};request_vt_symbol={req.vt_symbol}"
        )
        return result

    intent_pricetick = _valid_ctp_market_price(intent_row.get("pricetick"))
    live_pricetick = _valid_ctp_market_price(getattr(contract, "pricetick", 0.0))
    result["final_reprice_intent_pricetick"] = intent_pricetick or ""
    result["final_reprice_live_contract_pricetick"] = live_pricetick or ""
    if intent_pricetick <= 0:
        result["final_reprice_status"] = (
            blocked("intent_pricetick_missing")
        )
        result["final_reprice_reason"] = f"intent_pricetick={intent_row.get('pricetick')}"
        return result
    if live_pricetick <= 0:
        result["final_reprice_status"] = (
            blocked("live_contract_pricetick_missing")
        )
        result["final_reprice_reason"] = (
            f"live_contract_pricetick={getattr(contract, 'pricetick', None)}"
        )
        return result
    if intent_pricetick != live_pricetick:
        result["final_reprice_status"] = blocked("pricetick_mismatch")
        result["final_reprice_reason"] = (
            f"intent_pricetick={intent_pricetick};live_pricetick={live_pricetick}"
        )
        return result

    bid = _valid_ctp_market_price(tick.get("bid_price_1"))
    ask = _valid_ctp_market_price(tick.get("ask_price_1"))
    lower = _valid_ctp_market_price(tick.get("limit_down"))
    upper = _valid_ctp_market_price(tick.get("limit_up"))
    raw_live_price, live_price_source = _tick_price(tick)
    live_price = _valid_ctp_market_price(raw_live_price)
    result.update(
        {
            "final_reprice_bid_price_1": bid or "",
            "final_reprice_ask_price_1": ask or "",
            "final_reprice_live_price": live_price,
            "final_reprice_limit_down": lower or "",
            "final_reprice_limit_up": upper or "",
        }
    )
    if bid <= 0 or ask <= 0:
        result["final_reprice_status"] = (
            blocked("executable_quote_missing")
        )
        result["final_reprice_reason"] = (
            f"bid={tick.get('bid_price_1')};ask={tick.get('ask_price_1')}"
        )
        return result
    if bid > ask:
        result["final_reprice_status"] = blocked("crossed_quote")
        result["final_reprice_reason"] = f"bid={bid};ask={ask}"
        return result
    if lower <= 0 or upper <= 0:
        result["final_reprice_status"] = blocked("price_limits_missing")
        result["final_reprice_reason"] = (
            f"limit_down={tick.get('limit_down')};limit_up={tick.get('limit_up')}"
        )
        return result
    if lower >= upper:
        result["final_reprice_status"] = blocked("invalid_price_limits")
        result["final_reprice_reason"] = f"limit_down={lower};limit_up={upper}"
        return result
    if bid < lower or ask > upper:
        result["final_reprice_status"] = (
            blocked("quote_outside_price_limits")
        )
        result["final_reprice_reason"] = (
            f"limit_down={lower};bid={bid};ask={ask};limit_up={upper}"
        )
        return result
    protection_ticks = min(
        5,
        max(1, int(build_phase_d_config().hard_limits.max_slippage_ticks)),
    )
    unit_values = {
        "limit_down": lower / live_pricetick,
        "bid": bid / live_pricetick,
        "ask": ask / live_pricetick,
        "limit_up": upper / live_pricetick,
    }
    max_safe_units = MAX_EXACT_FLOAT_INTEGER - protection_ticks - 1
    if any(
        not math.isfinite(units)
        or units <= 0
        or units > max_safe_units
        for units in unit_values.values()
    ):
        result["final_reprice_status"] = (
            blocked("pricetick_not_representable")
        )
        result["final_reprice_reason"] = (
            f"pricetick={live_pricetick};price_units={unit_values};"
            f"max_safe_units={max_safe_units}"
        )
        return result
    if not _price_on_tick(bid, live_pricetick) or not _price_on_tick(
        ask, live_pricetick
    ):
        result["final_reprice_status"] = blocked("quote_not_on_tick")
        result["final_reprice_reason"] = (
            f"bid={bid};ask={ask};pricetick={live_pricetick}"
        )
        return result

    aligned_band = _tick_aligned_price_band(lower, upper, live_pricetick)
    if aligned_band is None:
        result["final_reprice_status"] = (
            blocked("no_tick_aligned_price_within_limits")
        )
        result["final_reprice_reason"] = (
            f"limit_down={lower};limit_up={upper};pricetick={live_pricetick}"
        )
        return result
    aligned_lower, aligned_upper = aligned_band
    result["final_reprice_aligned_limit_down"] = aligned_lower
    result["final_reprice_aligned_limit_up"] = aligned_upper

    direction_text = _normalize_direction_text(req.direction.value)
    if retry_reclaim_required:
        retry_trigger, retry_trigger_source, retry_trigger_status = (
            _retry_reclaim_trigger(intent_row)
        )
        if retry_trigger_status == "invalid":
            result["final_reprice_status"] = (
                "blocked_retry_reclaim_trigger_invalid"
            )
            result["final_reprice_reason"] = (
                f"{retry_trigger_source}="
                f"{intent_row.get(retry_trigger_source)}"
            )
            return result
        if retry_trigger_status == "missing":
            result["final_reprice_status"] = (
                "blocked_retry_reclaim_trigger_missing"
            )
            result["final_reprice_reason"] = (
                "retry_trigger_price/strategy_entry_price/"
                "retry_original_fill_price missing"
            )
            return result
        if direction_text == "short":
            executable_price = bid
            executable_price_source = "bid_price_1"
            reclaim_still_favorable = executable_price <= retry_trigger
        elif direction_text == "long":
            executable_price = ask
            executable_price_source = "ask_price_1"
            reclaim_still_favorable = executable_price >= retry_trigger
        else:
            result["final_reprice_status"] = (
                "blocked_retry_reclaim_invalid_direction"
            )
            result["final_reprice_reason"] = f"direction={direction_text}"
            return result
        if not reclaim_still_favorable:
            result["final_reprice_status"] = (
                "blocked_retry_reclaim_no_longer_favorable"
            )
            result["final_reprice_reason"] = (
                f"direction={direction_text};"
                f"executable_price={executable_price};"
                f"retry_trigger={retry_trigger};"
                f"retry_trigger_source={retry_trigger_source};"
                f"executable_price_source={executable_price_source}"
            )
            return result

    aligned_lower_units = math.ceil(lower / live_pricetick - 1e-10)
    aligned_upper_units = math.floor(upper / live_pricetick + 1e-10)
    bid_units = round(bid / live_pricetick)
    ask_units = round(ask / live_pricetick)
    if direction_text == "long":
        basis = ask
        desired_units = ask_units + protection_ticks
        price_units = min(
            max(desired_units, aligned_lower_units),
            aligned_upper_units,
        )
        marketable = price_units >= ask_units
        side_reason = (
            f"marketable_buy_{status_namespace}_post_q2_final_reprice"
        )
    elif direction_text == "short":
        basis = bid
        desired_units = bid_units - protection_ticks
        price_units = min(
            max(desired_units, aligned_lower_units),
            aligned_upper_units,
        )
        marketable = price_units <= bid_units
        side_reason = (
            f"marketable_sell_{status_namespace}_post_q2_final_reprice"
        )
    else:
        result["final_reprice_status"] = blocked("invalid_direction")
        result["final_reprice_reason"] = f"direction={direction_text}"
        return result

    price = float(price_units * live_pricetick)
    if direction_text == "long":
        marketable = marketable and price >= ask
    else:
        marketable = marketable and price <= bid
    if (
        not math.isfinite(price)
        or price <= 0
        or not _price_on_tick(price, live_pricetick)
        or price < lower
        or price > upper
    ):
        result["final_reprice_status"] = blocked("invalid_final_price")
        result["final_reprice_reason"] = (
            f"price={price};limit_down={lower};limit_up={upper};"
            f"pricetick={live_pricetick}"
        )
        return result
    if not marketable:
        result["final_reprice_status"] = (
            blocked("no_executable_price_within_limits")
        )
        result["final_reprice_reason"] = (
            f"direction={direction_text};price={price};bid={bid};ask={ask};"
            f"limit_down={lower};limit_up={upper}"
        )
        return result

    req.price = price
    result.update(
        {
            "final_reprice_status": "applied",
            "final_reprice_reason": (
                f"{side_reason};basis={basis};live_price_source={live_price_source};"
                f"protection_ticks={protection_ticks};pricetick={live_pricetick}"
            ),
            "final_reprice_price_after": price,
            "final_reprice_basis_price": basis,
            "final_reprice_protection_ticks": protection_ticks,
        }
    )
    return result


def _post_snapshot_final_reprice(
    main_engine: MainEngine,
    rows: dict[str, list[dict[str, Any]]],
    intent_row: dict[str, Any],
    req: OrderRequest,
    *,
    max_tick_age_seconds: int,
    q2_completed_monotonic: float | None,
    tick_wait_seconds: int,
) -> dict[str, Any]:
    """Revalidate quote/reclaim using only an EVENT_TICK received after Q2."""

    source = str(intent_row.get("source", "") or "").strip()
    if source == "stage260_stage372_daily":
        return _strict_post_q2_final_reprice(
            main_engine,
            rows,
            intent_row,
            req,
            max_tick_age_seconds=max_tick_age_seconds,
            q2_completed_monotonic=q2_completed_monotonic,
            tick_wait_seconds=tick_wait_seconds,
            status_namespace="stage372",
        )

    c9_source_policy = {
        "stage901_pending_order": ("open", False),
        "stage904_c9_intraday_close": ("close", False),
        "stage904_c9_intraday_retry_open": ("open", True),
    }
    if source in c9_source_policy:
        expected_offset, retry_reclaim_required = c9_source_policy[source]
        return _strict_post_q2_final_reprice(
            main_engine,
            rows,
            intent_row,
            req,
            max_tick_age_seconds=max_tick_age_seconds,
            q2_completed_monotonic=q2_completed_monotonic,
            tick_wait_seconds=tick_wait_seconds,
            status_namespace="c9",
            expected_offset=expected_offset,
            retry_reclaim_required=retry_reclaim_required,
        )

    parsed_cutoff = pd.to_numeric(q2_completed_monotonic, errors="coerce")
    if pd.isna(parsed_cutoff):
        # Use an impossible causal cutoff to obtain the normal audit shape,
        # then replace the status with the explicit fail-closed cause.
        result = _final_close_reprice(
            main_engine,
            rows,
            intent_row,
            req,
            max_tick_age_seconds=max_tick_age_seconds,
            tick_wait_seconds=0,
            not_before_tick_received_monotonic=float("inf"),
            allow_tick_file_fallback=False,
        )
        if result.get("final_reprice_status") != "skipped_not_stage904_intraday_close":
            result["final_reprice_status"] = (
                "blocked_post_snapshot_tick_cutoff_missing"
            )
            result["final_reprice_reason"] = (
                "q2_completed_monotonic missing or invalid"
            )
        result["post_sandwich_reprice"] = 1
        return result

    result = _final_close_reprice(
        main_engine,
        rows,
        intent_row,
        req,
        max_tick_age_seconds=max_tick_age_seconds,
        tick_wait_seconds=max(0, int(tick_wait_seconds)),
        not_before_tick_received_monotonic=float(parsed_cutoff),
        # A Stage608 file timestamp is in a different clock domain and cannot
        # prove it was observed after this connection's Q2 callback.
        allow_tick_file_fallback=False,
    )
    result["post_sandwich_reprice"] = 1
    return result


def _position_volume(rows: list[dict[str, Any]], vt_symbol: str, direction: str) -> float:
    volume = 0.0
    for row in rows:
        if _vt_symbol_from_row(row) != vt_symbol:
            continue
        if _normalize_direction_text(row.get("direction")) != direction:
            continue
        raw_volume = pd.to_numeric(row.get("volume", row.get("position", row.get("pos", 0.0))), errors="coerce")
        frozen = pd.to_numeric(row.get("frozen", row.get("frozen_volume", 0.0)), errors="coerce")
        volume += max(0.0, (0.0 if pd.isna(raw_volume) else float(raw_volume)) - (0.0 if pd.isna(frozen) else float(frozen)))
    return float(volume)


def _position_gross_volume(rows: list[dict[str, Any]], vt_symbol: str, direction: str) -> float:
    volume = 0.0
    for row in rows:
        if _vt_symbol_from_row(row) != vt_symbol:
            continue
        if _normalize_direction_text(row.get("direction")) != direction:
            continue
        raw_volume = pd.to_numeric(row.get("volume", row.get("position", row.get("pos", 0.0))), errors="coerce")
        volume += max(0.0, 0.0 if pd.isna(raw_volume) else float(raw_volume))
    return float(volume)


def _symbol_gross_position_volume(rows: list[dict[str, Any]], vt_symbol: str) -> float:
    volume = 0.0
    for row in rows:
        if _vt_symbol_from_row(row) != vt_symbol:
            continue
        raw_volume = pd.to_numeric(
            row.get("volume", row.get("position", row.get("pos", 0.0))),
            errors="coerce",
        )
        volume += max(0.0, 0.0 if pd.isna(raw_volume) else float(raw_volume))
    return float(volume)


def _latest_order_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return []
    frame = pd.DataFrame(rows)
    key_source = frame.get("vt_orderid", frame.get("orderid", pd.Series([""] * len(frame))))
    frame["_order_key"] = key_source.fillna("").astype(str)
    empty_key = frame["_order_key"].eq("")
    frame.loc[empty_key, "_order_key"] = [f"row_{idx}" for idx in frame.index[empty_key]]
    frame["_row_order"] = range(len(frame))
    latest = frame.sort_values(["_order_key", "_row_order"]).drop_duplicates("_order_key", keep="last")
    return latest.drop(columns=[col for col in ("_order_key", "_row_order") if col in latest.columns]).to_dict(orient="records")


def _active_order_count(rows: list[dict[str, Any]]) -> int:
    return sum(1 for row in _latest_order_rows(rows) if _status_is_active(row.get("status")))


def _unknown_order_status_count(rows: list[dict[str, Any]]) -> int:
    return sum(1 for row in _latest_order_rows(rows) if _status_is_unknown(row.get("status")))


def _opposite_position_direction(order_direction: str) -> str:
    if order_direction == "short":
        return "long"
    if order_direction == "long":
        return "short"
    return ""


def _trade_delta_volume(rows: list[dict[str, Any]], start_trade_count: int, vt_orderid: str) -> float:
    return _trade_delta_details(rows, start_trade_count, vt_orderid)["volume"]


def _trade_row_identity(row: dict[str, Any], absolute_index: int) -> str:
    vt_tradeid = str(row.get("vt_tradeid", "") or "").strip()
    if vt_tradeid:
        return f"vt:{vt_tradeid}"
    tradeid = str(row.get("tradeid", row.get("trade_id", "")) or "").strip()
    if tradeid:
        gateway = str(row.get("gateway_name", "") or "").strip()
        return f"trade:{gateway}:{tradeid}"
    return f"runtime_row:{absolute_index}"


def _first_trade_at(rows: list[dict[str, Any]]) -> str:
    """Return the earliest broker trade time without substituting receipt time."""

    earliest: tuple[float, str] | None = None
    for row in rows:
        value = next(
            (
                row.get(key)
                for key in ("broker_trade_at", "datetime", "trade_at")
                if str(row.get(key, "") or "").strip()
            ),
            None,
        )
        parsed = _parse_dt(value)
        if parsed is None:
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=ZoneInfo("Asia/Shanghai"))
        candidate = (parsed.timestamp(), str(value).strip())
        if earliest is None or candidate[0] < earliest[0]:
            earliest = candidate
    return earliest[1] if earliest is not None else ""


def _trade_delta_details(rows: list[dict[str, Any]], start_trade_count: int, vt_orderid: str) -> dict[str, Any]:
    unique_rows: list[tuple[str, dict[str, Any]]] = []
    seen: set[str] = set()
    for absolute_index, row in enumerate(rows[start_trade_count:], start=start_trade_count):
        if vt_orderid and str(row.get("vt_orderid", "")) != vt_orderid:
            continue
        identity = _trade_row_identity(row, absolute_index)
        if identity in seen:
            continue
        seen.add(identity)
        unique_rows.append((identity, row))
    total_volume = 0.0
    priced_volume = 0.0
    total_notional = 0.0
    priced_rows: list[tuple[str, dict[str, Any]]] = []
    for identity, row in unique_rows:
        volume = pd.to_numeric(row.get("volume", 0.0), errors="coerce")
        price = pd.to_numeric(row.get("price", 0.0), errors="coerce")
        if pd.isna(volume) or float(volume) <= 0:
            continue
        total_volume += float(volume)
        if not pd.isna(price) and float(price) > 0:
            priced_volume += float(volume)
            total_notional += float(volume) * float(price)
            priced_rows.append((identity, row))
    vwap = total_notional / priced_volume if priced_volume > 0 else 0.0
    return {
        # ``volume`` remains the total callback volume for compatibility with
        # the wait loop.  Pricing and durable fill accounting must use the
        # explicit priced fields below.
        "volume": total_volume,
        "total_volume": total_volume,
        "priced_volume": priced_volume,
        "unpriced_volume": max(0.0, total_volume - priced_volume),
        "vwap": vwap,
        "fill_price_source": "event_trade_weighted_avg" if priced_volume > 0 else "order_traded_without_trade_price",
        "identities": [identity for identity, _ in unique_rows],
        "rows": [row for _, row in unique_rows],
        "priced_identities": [identity for identity, _ in priced_rows],
        "priced_rows": [row for _, row in priced_rows],
        "first_trade_at": _first_trade_at([row for _, row in priced_rows]),
    }


def _trade_rows_vwap(rows: list[dict[str, Any]]) -> tuple[float, float]:
    volume = 0.0
    notional = 0.0
    for row in rows:
        row_volume = pd.to_numeric(row.get("volume", 0.0), errors="coerce")
        row_price = pd.to_numeric(row.get("price", 0.0), errors="coerce")
        if pd.isna(row_volume) or pd.isna(row_price) or float(row_volume) <= 0 or float(row_price) <= 0:
            continue
        volume += float(row_volume)
        notional += float(row_volume) * float(row_price)
    return volume, notional / volume if volume > 0 else 0.0


def _aggregate_trade_fill_key(vt_orderid: str, identities: list[str], suffix: str) -> str:
    digest = hashlib.sha256(
        json.dumps(sorted(identities), ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:20]
    return f"aggregate:{vt_orderid}:{suffix}:{digest}"


def _trade_delta_vwap(rows: list[dict[str, Any]], start_trade_count: int, vt_orderid: str) -> tuple[float, float, str]:
    details = _trade_delta_details(rows, start_trade_count, vt_orderid)
    return details["priced_volume"], details["vwap"], details["fill_price_source"]


def _wait_trade_details(
    rows: list[dict[str, Any]],
    start_trade_count: int,
    vt_orderid: str,
    expected_volume: float,
    deadline: float,
    *,
    clock: Callable[[], float] = time.time,
    sleeper: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Allow EVENT_TRADE to catch up when EVENT_ORDER reports fills first."""
    details = _trade_delta_details(rows, start_trade_count, vt_orderid)
    while details["total_volume"] + 1e-9 < expected_volume and clock() < deadline:
        sleeper(min(0.1, max(0.0, deadline - clock())))
        details = _trade_delta_details(rows, start_trade_count, vt_orderid)
    return details


def _final_pre_send_blockers(
    rows: dict[str, list[dict[str, Any]]],
    req: OrderRequest,
    vt_symbol: str,
    *,
    authoritative_active_orders: list[dict[str, Any]],
    order_query_confirmed: bool,
) -> list[str]:
    blockers: list[str] = []
    if not order_query_confirmed:
        blockers.append("final_order_query_missing_or_incomplete")
    # Only the complete reqid-bound CTP query epoch is authoritative here.
    # EVENT_ORDER rows and the earlier Stage174 file remain diagnostics and
    # cannot prove that another session has no newly inserted active order.
    active_count = len(authoritative_active_orders)
    if active_count > 0:
        blockers.append(f"final_order_query_active_order_count={active_count}")
    offset_text = _normalize_offset_text(req.offset.value)
    direction_text = _normalize_direction_text(req.direction.value)
    if offset_text == "close":
        position_direction = _opposite_position_direction(direction_text)
        final_volume = _position_volume(rows.get("positions", []), vt_symbol, position_direction)
        if final_volume <= 0:
            blockers.append(f"final_no_matching_{position_direction}_broker_position_to_close")
        elif abs(final_volume - float(req.volume)) > 1e-9:
            blockers.append(
                "final_broker_position_volume_mismatch_for_exact_reduce_close:"
                f"broker={final_volume};request={req.volume}"
            )
    elif offset_text == "open":
        symbol_gross_volume = _symbol_gross_position_volume(
            rows.get("positions", []), vt_symbol
        )
        if symbol_gross_volume > 0:
            blockers.append(
                "final_target_symbol_gross_position_exists_for_open:"
                f"{symbol_gross_volume}"
            )
    return blockers


def _final_reprice_blockers(reprice_result: dict[str, Any]) -> list[str]:
    status = str(reprice_result.get("final_reprice_status", "") or "")
    if not status or status in {"skipped_not_stage904_intraday_close", "applied"}:
        return []
    return [f"final_close_reprice_not_applied:{status}"]


def _event_watermark_blockers(
    baseline: dict[str, Any],
    current: dict[str, Any],
    *,
    phase: str,
) -> list[str]:
    """Fail closed on asynchronous order/fill evidence after an O-P-O gate.

    EVENT_POSITION is deliberately not an unconditional blocker: every
    reqid-bound position query emits unscoped vn.py position events, which can
    be drained after Q2.  The two complete position snapshots are compared by
    the caller instead.  A real fill still changes EVENT_TRADE and the broker
    position epoch, so it cannot be hidden by this exception.
    """

    blockers: list[str] = []
    for event_name in ("order", "trade"):
        key = f"event_{event_name}_count"
        before = _to_int(baseline.get(key), -1)
        after = _to_int(current.get(key), -1)
        if before < 0 or after < 0:
            blockers.append(f"{phase}_event_{event_name}_watermark_missing")
        elif before != after:
            blockers.append(
                f"{phase}_event_{event_name}_watermark_changed:"
                f"before={before};after={after}"
            )
    return blockers


def _physical_batch_event_identity_blockers(
    batch: dict[str, Any],
    kind: str,
    row: Mapping[str, Any],
) -> tuple[list[str], dict[str, Any] | None]:
    """Prove an ingress event belongs to one already-persisted batch child."""

    vt_orderid = str(row.get("vt_orderid", "") or "").strip()
    child = dict(batch.get("owned_children", {})).get(vt_orderid)
    if not vt_orderid or not isinstance(child, dict):
        return [
            "physical_batch_external_event_unbound:"
            f"kind={kind};vt_orderid={vt_orderid or '<missing>'}"
        ], None
    request = child.get("request")
    if not isinstance(request, OrderRequest):
        return ["physical_batch_owned_child_request_missing"], child
    blockers: list[str] = []
    expected_fields = {
        "gateway_name": "CTP",
        "vt_symbol": request.vt_symbol,
        "direction": str(request.direction.value),
    }
    for field_name, expected in expected_fields.items():
        actual = str(row.get(field_name, "") or "")
        if actual != expected:
            blockers.append(
                "physical_batch_event_identity_mismatch:"
                f"kind={kind};field={field_name};"
                f"expected={expected};actual={actual or '<missing>'}"
            )
    actual_offset = _physical_offset_identity(row.get("offset"))
    expected_offset = _physical_offset_identity(request.offset)
    if actual_offset != expected_offset:
        blockers.append(
            "physical_batch_event_identity_mismatch:"
            f"kind={kind};field=offset;expected={expected_offset};"
            f"actual={actual_offset or '<missing>'}"
        )
    if kind == "order":
        reference = str(row.get("reference", "") or "")
        if reference != str(request.reference or ""):
            blockers.append(
                "physical_batch_event_identity_mismatch:"
                f"kind=order;field=reference;"
                f"expected={request.reference};"
                f"actual={reference or '<missing>'}"
            )
        volume = _strict_ctp_account_number(row.get("volume"))
        price = _strict_ctp_account_number(row.get("price"))
        traded = _strict_ctp_account_number(row.get("traded", 0.0))
        if volume is None or not math.isclose(
            volume,
            float(request.volume),
            rel_tol=0.0,
            abs_tol=1e-9,
        ):
            blockers.append("physical_batch_order_volume_mismatch")
        if price is None or not math.isclose(
            price,
            float(request.price),
            rel_tol=0.0,
            abs_tol=1e-9,
        ):
            blockers.append("physical_batch_order_price_mismatch")
        if (
            traded is None
            or traded < 0
            or traded > float(request.volume) + 1e-9
        ):
            blockers.append("physical_batch_order_traded_volume_invalid")
    elif kind == "trade":
        trade_identity = str(
            row.get("vt_tradeid")
            or row.get("tradeid")
            or ""
        ).strip()
        trade_volume = _strict_ctp_account_number(row.get("volume"))
        trade_price = _strict_ctp_account_number(row.get("price"))
        if not trade_identity:
            blockers.append("physical_batch_trade_identity_missing")
        if trade_volume is None or trade_volume <= 0:
            blockers.append("physical_batch_trade_volume_invalid")
        if trade_price is None or trade_price <= 0:
            blockers.append("physical_batch_trade_price_invalid")
        if not blockers:
            identities = child.setdefault("trade_identities", {})
            prior = identities.get(trade_identity)
            observed = {
                "volume": float(trade_volume),
                "price": float(trade_price),
            }
            if prior is not None and prior != observed:
                blockers.append(
                    "physical_batch_trade_identity_conflict:"
                    f"{trade_identity}"
                )
            elif prior is None:
                total = sum(
                    float(item.get("volume", 0.0))
                    for item in identities.values()
                ) + float(trade_volume)
                if total > float(request.volume) + 1e-9:
                    blockers.append(
                        "physical_batch_trade_volume_exceeds_child:"
                        f"observed={total};child={request.volume}"
                    )
                else:
                    identities[trade_identity] = observed
    else:
        blockers.append(f"physical_batch_event_kind_invalid:{kind}")
    if _to_int(
        row.get("_stage179_callback_persistence_confirmed"), 0
    ) != 1:
        blockers.append(
            "physical_batch_event_callback_not_durably_persisted:"
            f"kind={kind};vt_orderid={vt_orderid}"
        )
    return list(dict.fromkeys(blockers)), child


def _advance_physical_batch_event_baseline(
    state: dict[str, Any],
    batch: dict[str, Any],
    *,
    ledger_path: Path,
) -> list[str]:
    """Attribute every event delta before advancing a physical-batch baseline."""

    rows = state.get("rows", {})
    ingress_lock = state.get("execution_event_ingress_lock")
    guard = ingress_lock if hasattr(ingress_lock, "__enter__") else nullcontext()
    with guard:
        baseline = dict(batch.get("event_watermark", {}))
        current = _execution_event_watermark(rows)
        blockers: list[str] = []
        order_start = _to_int(batch.get("order_row_index"), -1)
        trade_start = _to_int(batch.get("trade_row_index"), -1)
        if order_start < 0 or trade_start < 0:
            return ["physical_batch_event_row_baseline_missing"]
        new_rows = {
            "order": list(rows.get("orders", []))[order_start:],
            "trade": list(rows.get("trades", []))[trade_start:],
        }
        position_before = _to_int(
            baseline.get("event_position_count"), -1
        )
        position_after = _to_int(
            current.get("event_position_count"), -1
        )
        if position_before < 0 or position_after < position_before:
            blockers.append(
                "physical_batch_event_watermark_invalid:"
                "kind=position;"
                f"before={position_before};after={position_after}"
            )
        elif position_after != position_before:
            # No broker query is allowed while the physical-batch CTP lock is
            # held, and a native insert does not own a position callback.
            # Therefore any position ingress in this interval is external
            # execution evidence and must stop the remaining children.
            blockers.append(
                "physical_batch_external_position_event:"
                f"before={position_before};after={position_after}"
            )
        for kind, row_key in (("order", "event_order_count"), ("trade", "event_trade_count")):
            before = _to_int(baseline.get(row_key), -1)
            after = _to_int(current.get(row_key), -1)
            if before < 0 or after < before:
                blockers.append(
                    "physical_batch_event_watermark_invalid:"
                    f"kind={kind};before={before};after={after}"
                )
                continue
            delta = after - before
            if delta != len(new_rows[kind]):
                blockers.append(
                    "physical_batch_event_ingress_row_count_mismatch:"
                    f"kind={kind};delta={delta};rows={len(new_rows[kind])}"
                )
        if blockers:
            return list(dict.fromkeys(blockers))
        attributed: list[dict[str, Any]] = []
        for kind in ("order", "trade"):
            for row_offset, row in enumerate(new_rows[kind]):
                identity_blockers, child = (
                    _physical_batch_event_identity_blockers(
                        batch, kind, row
                    )
                )
                blockers.extend(identity_blockers)
                if identity_blockers or child is None:
                    continue
                attribution = {
                    "event_type": "physical_batch_event_attributed",
                    "target_date": batch.get("target_date", ""),
                    "intent_id": batch.get("intent_id", ""),
                    "intent_fingerprint": batch.get("fingerprint", ""),
                    "physical_batch_id": batch.get("batch_id", ""),
                    "child_order_id": child.get("child_order_id", ""),
                    "child_order_index": child.get("child_order_index", -1),
                    "callback_kind": kind,
                    "vt_orderid": str(row.get("vt_orderid", "") or ""),
                    "vt_tradeid": str(row.get("vt_tradeid", "") or ""),
                    "status": str(row.get("status", "") or ""),
                    "traded": _to_float(row.get("traded"), 0.0),
                    "volume": _to_float(row.get("volume"), 0.0),
                    "price": _to_float(row.get("price"), 0.0),
                    "ingress_row_offset": row_offset,
                }
                attribution["broker_callback_key"] = _stage179_callback_key(
                    "physical-batch-attribution", attribution
                )
                try:
                    result = append_broker_callback_event_once(
                        attribution, ledger_path
                    )
                except BaseException as exc:
                    blockers.append(
                        "physical_batch_event_attribution_append_exception:"
                        f"{type(exc).__name__}"
                    )
                    continue
                blocker = str(result.get("blocker", "") or "")
                if blocker:
                    blockers.append(
                        "physical_batch_event_attribution_append_failed:"
                        + blocker
                    )
                    continue
                attributed.append(attribution)
        blockers = list(dict.fromkeys(blockers))
        if blockers:
            return blockers
        if new_rows["order"] or new_rows["trade"]:
            try:
                append_execution_ledger_event(
                    {
                        "event_type": "physical_batch_event_baseline_advanced",
                        "target_date": batch.get("target_date", ""),
                        "intent_id": batch.get("intent_id", ""),
                        "intent_fingerprint": batch.get("fingerprint", ""),
                        "physical_batch_id": batch.get("batch_id", ""),
                        "event_watermark_before": baseline,
                        "event_watermark_after": current,
                        "attributed_event_count": len(attributed),
                        "reconciliation_required": 0,
                    },
                    path=ledger_path,
                )
            except BaseException as exc:
                return [
                    "physical_batch_event_rebaseline_append_exception:"
                    f"{type(exc).__name__}"
                ]
        batch["event_watermark"] = current
        batch["order_row_index"] = len(rows.get("orders", []))
        batch["trade_row_index"] = len(rows.get("trades", []))
        batch.setdefault("attributed_events", []).extend(attributed)
        return []


def _post_final_gate_pre_api_slot_blockers(
    rows: dict[str, Any],
    final_gate_watermark: dict[str, Any],
) -> list[str]:
    """One last zero-I/O event check immediately before API-slot reserve."""

    if not final_gate_watermark:
        return ["post_final_gate_event_watermark_missing_before_api_slot"]
    return _event_watermark_blockers(
        final_gate_watermark,
        _execution_event_watermark(rows),
        phase="post_final_gate_pre_api_slot",
    )


def _post_reprice_final_state_gate(
    main_engine: MainEngine,
    td_api: Any,
    rows: dict[str, Any],
    intent_row: dict[str, Any],
    req: OrderRequest,
    *,
    initial_snapshot: dict[str, Any],
    initial_reprice_result: dict[str, Any],
    max_tick_age_seconds: int,
    max_wait_seconds: float,
    readiness_state: CtpReadinessState,
    hard_deadline_monotonic: float | None = None,
) -> dict[str, Any]:
    """Close the Q2-to-send race without starting a query/tick loop.

    The first O-P-O proves broker state, then Stage931 may wait up to two
    seconds for an EVENT_TICK.  That wait invalidates the old proof.  After the
    price/reclaim check, run exactly one more reqid-bound O-P-O, compare the
    complete position epochs, re-check transport and the latest causal tick
    with zero additional waiting, and finally compare runtime event watermarks.
    Any uncertainty defers this cycle to the one-second fast lane.
    """

    preliminary_price_before = _to_float(
        initial_reprice_result.get("final_reprice_price_before"),
        float(req.price),
    )
    if not math.isfinite(preliminary_price_before) or preliminary_price_before <= 0:
        preliminary_price_before = float(req.price)

    q2_before_watermark = dict(
        initial_snapshot.get("event_watermark_before_q2", {})
    )
    baseline_watermark = dict(
        initial_snapshot.get("event_watermark_after_q2", {})
    )
    before_second_snapshot = _execution_event_watermark(rows)
    blockers: list[str] = []
    if not baseline_watermark:
        blockers.append("post_reprice_initial_event_watermark_missing")
    else:
        blockers.extend(
            _event_watermark_blockers(
                baseline_watermark,
                before_second_snapshot,
                phase="post_q2",
            )
        )
    # Synchronous reqQryOrder echoes are excluded from the gateway ingress
    # counter.  Any order/trade ingress change from immediately before Q2 to
    # immediately after it is therefore independent execution evidence,
    # including the narrow callback-to-watermark interval.
    if q2_before_watermark and baseline_watermark:
        blockers.extend(
            _event_watermark_blockers(
                q2_before_watermark,
                baseline_watermark,
                phase="final_q2",
            )
        )

    second_snapshot = _final_pre_send_snapshot_epoch(
        td_api,
        rows,
        max_wait_seconds=max(0.0, float(max_wait_seconds)),
        readiness_state=readiness_state,
        hard_deadline_monotonic=hard_deadline_monotonic,
    )
    blockers.extend(
        f"post_reprice_snapshot:{blocker}"
        for blocker in second_snapshot.get("blockers", [])
    )
    second_q2_before_watermark = dict(
        second_snapshot.get("event_watermark_before_q2", {})
    )
    second_q2_after_watermark = dict(
        second_snapshot.get("event_watermark_after_q2", {})
    )
    if second_q2_before_watermark:
        blockers.extend(
            _event_watermark_blockers(
                before_second_snapshot,
                second_q2_before_watermark,
                phase="post_reprice_query_window",
            )
        )
    if second_q2_before_watermark and second_q2_after_watermark:
        blockers.extend(
            _event_watermark_blockers(
                second_q2_before_watermark,
                second_q2_after_watermark,
                phase="post_reprice_final_q2",
            )
        )

    initial_positions = list(
        initial_snapshot.get("canonical_positions", [])
    )
    if not initial_positions and initial_snapshot.get("positions"):
        initial_positions = _canonical_position_snapshot(
            list(initial_snapshot.get("positions", []))
        )
    second_positions = list(
        second_snapshot.get("canonical_positions", [])
    )
    if not second_positions and second_snapshot.get("positions"):
        second_positions = _canonical_position_snapshot(
            list(second_snapshot.get("positions", []))
        )
    if initial_positions != second_positions:
        blockers.append("post_reprice_authoritative_position_changed")

    blockers.extend(
        _final_pre_send_blockers(
            rows,
            req,
            str(intent_row.get("vt_symbol", "") or req.vt_symbol),
            authoritative_active_orders=list(
                second_snapshot.get("active_orders", [])
            ),
            order_query_confirmed=bool(second_snapshot.get("confirmed")),
        )
    )
    blockers.extend(
        _final_ctp_transport_blockers(td_api, rows, readiness_state)
    )
    after_second_snapshot = _execution_event_watermark(rows)

    # Do not wait for another tick here.  Reuse only the newest causal
    # EVENT_TICK observed after the *second* Q2, with Stage608 fallback disabled.
    # If that evidence is no longer fresh/favourable, the fast lane retries the
    # whole bounded sequence instead of entering an unbounded query-tick loop.
    final_reprice_result = dict(initial_reprice_result)
    if not blockers:
        final_reprice_result = _post_snapshot_final_reprice(
            main_engine,
            rows,
            intent_row,
            req,
            max_tick_age_seconds=max_tick_age_seconds,
            q2_completed_monotonic=second_snapshot.get(
                "q2_completed_monotonic"
            ),
            tick_wait_seconds=(
                min(
                    2.0,
                    max(
                        0.0,
                        float(hard_deadline_monotonic) - time.monotonic(),
                    ),
                )
                if hard_deadline_monotonic is not None
                else 2.0
            ),
        )
        blockers.extend(_final_reprice_blockers(final_reprice_result))
        # The bounded post-Q2 tick wait must be followed by an immediate
        # zero-I/O transport check.  Authorization, kill switch and the same
        # watermark are revalidated again by pre_api_slot_blockers before the
        # durable API reservation.
        blockers.extend(
            _final_ctp_transport_blockers(td_api, rows, readiness_state)
        )

    final_watermark = _execution_event_watermark(rows)
    final_comparison_watermark = (
        second_q2_after_watermark or after_second_snapshot
    )
    blockers.extend(
        _event_watermark_blockers(
            final_comparison_watermark,
            final_watermark,
            phase="post_final_snapshot",
        )
    )
    blockers = list(dict.fromkeys(blockers))
    if blockers:
        # The first post-Q2 price is only a candidate.  Never leave the shared
        # OrderRequest mutated when the second O-P-O/causal-tick gate fails.
        req.price = preliminary_price_before
    return {
        "success": not blockers,
        "confirmed": bool(second_snapshot.get("confirmed")) and not blockers,
        "stable": bool(second_snapshot.get("stable")) and not blockers,
        "blockers": blockers,
        "q2_before_event_watermark": q2_before_watermark,
        "initial_event_watermark": baseline_watermark,
        "before_second_snapshot_event_watermark": before_second_snapshot,
        "second_q2_before_event_watermark": second_q2_before_watermark,
        "second_q2_after_event_watermark": second_q2_after_watermark,
        "after_second_snapshot_event_watermark": after_second_snapshot,
        "final_event_watermark": final_watermark,
        "query_watermark": dict(
            second_snapshot.get("query_watermark", {})
        ),
        "position_event_watermark_changed": int(
            _to_int(baseline_watermark.get("event_position_count"), -1)
            != _to_int(final_watermark.get("event_position_count"), -1)
        ) if baseline_watermark else 0,
        "initial_canonical_positions": initial_positions,
        "final_canonical_positions": second_positions,
        "snapshot": second_snapshot,
        "final_reprice_result": final_reprice_result,
        "request_price_restored_after_block": int(bool(blockers)),
    }


def _fsync_output_directory(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    directory_fd = os.open(str(path.parent), flags)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def _atomic_write_file(
    path: Path,
    writer: Callable[[Any], Any],
    *,
    encoding: str,
    durable: bool = False,
) -> None:
    """Write beside the destination and publish it with one atomic replace."""

    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary_path = Path(temporary_name)
    handle = None
    try:
        handle = os.fdopen(descriptor, "w", encoding=encoding, newline="")
        descriptor = -1
        with handle:
            writer(handle)
            handle.flush()
            if durable:
                os.fsync(handle.fileno())
        handle = None
        os.replace(temporary_path, path)
        if durable:
            # The file fsync covers content; directory fsync makes the replace
            # itself durable for the critical summary JSON.
            _fsync_output_directory(path)
    except BaseException:
        if handle is not None and not handle.closed:
            handle.close()
        if descriptor >= 0:
            os.close(descriptor)
        temporary_path.unlink(missing_ok=True)
        raise


def _atomic_write_text(path: Path, text: str, *, durable: bool = False) -> None:
    _atomic_write_file(
        path,
        lambda handle: handle.write(text),
        encoding="utf-8",
        durable=durable,
    )


def _atomic_write_dataframe(path: Path, frame: pd.DataFrame) -> None:
    _atomic_write_file(
        path,
        lambda handle: frame.to_csv(handle, index=False),
        encoding="utf-8-sig",
    )


def _write_df(path: Path, rows: list[dict[str, Any]]) -> None:
    _atomic_write_dataframe(path, pd.DataFrame(rows))


def _stage905_intents(target_date: str) -> pd.DataFrame:
    return _read_csv_maybe(_stage905_intents_path(target_date))


def _ready_intents_from_frame(intents: pd.DataFrame) -> pd.DataFrame:
    if intents.empty or "executor_status" not in intents.columns:
        return pd.DataFrame()
    return intents[intents["executor_status"].astype(str).eq("dry_run_order_request_payload_ready")].copy()


def _ready_intents(target_date: str) -> pd.DataFrame:
    return _ready_intents_from_frame(_stage905_intents(target_date))


def _stage904_close_mask(intents: pd.DataFrame) -> pd.Series:
    if intents.empty:
        return pd.Series(dtype=bool)
    sources = intents.get("source", pd.Series([""] * len(intents), index=intents.index)).fillna("").astype(str)
    offsets = intents.get("offset", pd.Series([""] * len(intents), index=intents.index)).fillna("").astype(str).str.lower()
    return sources.eq("stage904_c9_intraday_close") & offsets.eq("close")


def _stage905_snapshot_blockers(
    stage905: dict[str, Any],
    intents: pd.DataFrame,
    *,
    target_date: str,
    max_age_seconds: int,
    reduce_close_only: bool,
) -> list[str]:
    """Validate the complete Stage905 artifact, then gate only the requested scope.

    The summary counters are global and therefore remain a fail-closed file
    consistency check.  In reduce-close-only mode, unrelated blocked/open rows
    do not prevent an independently ready Stage904 protective close.
    """
    blockers: list[str] = []
    age = _age_seconds(stage905.get("generated_at"))
    if age is None or age > max_age_seconds:
        blockers.append(f"stage905_summary_stale_or_missing:{age}")
    if stage905.get("target_date") != target_date:
        blockers.append("stage905_target_date_mismatch")

    statuses = (
        intents.get("executor_status", pd.Series([""] * len(intents), index=intents.index))
        .fillna("")
        .astype(str)
    )
    actual_intent_count = int(len(intents))
    actual_ready_count = int(statuses.eq("dry_run_order_request_payload_ready").sum())
    actual_blocked_count = int(statuses.eq("blocked").sum())
    actual_skipped_count = int(statuses.str.startswith("skipped_").sum())
    declared_counts = {
        "intent_count": actual_intent_count,
        "ready_count": actual_ready_count,
        "blocked_count": actual_blocked_count,
        "skipped_count": actual_skipped_count,
    }
    for key, actual in declared_counts.items():
        declared = _to_int(stage905.get(key), -1)
        if declared != actual:
            blockers.append(f"stage905_{key}_mismatch:{declared}!={actual}")

    expected_status = (
        "executor_no_intents"
        if actual_intent_count == 0
        else "executor_dry_run_ready"
        if actual_ready_count and not actual_blocked_count
        else "executor_dry_run_blocked"
        if actual_blocked_count
        else "executor_no_ready_intents"
    )
    executor_status = str(stage905.get("executor_status", "") or "")
    if executor_status != expected_status:
        blockers.append(f"stage905_executor_status_inconsistent:{executor_status}!={expected_status}")
    if _to_int(stage905.get("send_order_api_called_count"), 0) != 0:
        blockers.append("stage905_unexpected_send_order_api_call")
    if _to_int(stage905.get("cancel_order_api_called_count"), 0) != 0:
        blockers.append("stage905_unexpected_cancel_order_api_call")

    if reduce_close_only:
        close_statuses = statuses[_stage904_close_mask(intents)]
        close_ready = int(close_statuses.eq("dry_run_order_request_payload_ready").sum())
        close_nonready = int(len(close_statuses) - close_ready)
        if close_ready <= 0:
            blockers.append("stage905_no_ready_stage904_close_intent")
        if close_nonready > 0:
            blockers.append(f"stage905_close_scope_nonready_count={close_nonready}")
    else:
        if executor_status != "executor_dry_run_ready":
            blockers.append(f"stage905_executor_not_clean_ready:{executor_status}")
        if actual_blocked_count != 0:
            blockers.append(f"stage905_blocked_count={actual_blocked_count}")
        ready_retry = intents[
            statuses.eq("dry_run_order_request_payload_ready")
            & intents.get(
                "source", pd.Series([""] * len(intents), index=intents.index)
            ).fillna("").astype(str).eq("stage904_c9_intraday_retry_open")
            & intents.get(
                "offset", pd.Series([""] * len(intents), index=intents.index)
            ).fillna("").astype(str).str.lower().eq("open")
        ]
        if not ready_retry.empty:
            manual_valid, manual = _canonical_binary_flag_series(
                ready_retry.get(
                    "manual_intervention_required",
                    pd.Series([None] * len(ready_retry), index=ready_retry.index),
                )
            )
            if not bool(manual_valid.all()):
                blockers.append("stage905_ready_retry_open_manual_flag_invalid")
            migration = ready_retry.get(
                "migration_blocker",
                pd.Series([""] * len(ready_retry), index=ready_retry.index),
            ).fillna("").astype(str).str.strip().ne("")
            risk = ready_retry.get(
                "risk_alert_level",
                pd.Series([""] * len(ready_retry), index=ready_retry.index),
            ).fillna("").astype(str).str.upper().isin({"P0", "P1"})
            if bool((manual | migration | risk).any()):
                blockers.append("stage905_ready_retry_open_manual_migration_blocked")
            blockers.extend(_stage904_retry_open_identity_blockers(ready_retry))
    return blockers


def _stage904_retry_open_snapshot_blockers(
    stage904: dict[str, Any],
    ready: pd.DataFrame,
    *,
    target_date: str,
    max_age_seconds: int,
) -> list[str]:
    """Bind every ready retry-open to the current exact Stage904 run."""

    if ready.empty:
        return []
    sources = ready.get(
        "source", pd.Series([""] * len(ready), index=ready.index)
    ).fillna("").astype(str)
    offsets = ready.get(
        "offset", pd.Series([""] * len(ready), index=ready.index)
    ).fillna("").astype(str).str.lower()
    retry = ready[sources.eq("stage904_c9_intraday_retry_open") & offsets.eq("open")]
    if retry.empty:
        return []

    blockers: list[str] = []
    age = _age_seconds(stage904.get("generated_at"))
    if age is None or age > max_age_seconds:
        blockers.append(f"stage904_retry_open_summary_stale_or_missing:{age}")
    if stage904.get("model_tag") != STAGE904_MODEL_TAG:
        blockers.append("stage904_retry_open_model_tag_mismatch")
    if stage904.get("target_date") != target_date:
        blockers.append("stage904_retry_open_target_date_mismatch")
    if stage904.get("monitor_status") != "intraday_monitor_retry_open_dry_run":
        blockers.append("stage904_retry_open_status_not_authoritative")
    monitor_run_id = str(
        stage904.get("monitor_run_id") or stage904.get("run_id") or ""
    ).strip()
    intent_run_ids = retry.get(
        "monitor_run_id", pd.Series([""] * len(retry), index=retry.index)
    ).fillna("").astype(str).str.strip()
    if (
        not monitor_run_id
        or intent_run_ids.eq("").any()
        or not bool(intent_run_ids.eq(monitor_run_id).all())
    ):
        blockers.append("stage904_retry_open_run_id_mismatch")
    manual_valid, manual = _canonical_binary_flag_series(
        retry.get(
            "manual_intervention_required",
            pd.Series([None] * len(retry), index=retry.index),
        )
    )
    if not bool(manual_valid.all()):
        blockers.append("stage904_ready_retry_open_manual_flag_invalid")
    migration = retry.get(
        "migration_blocker", pd.Series([""] * len(retry), index=retry.index)
    ).fillna("").astype(str).str.strip().ne("")
    risk = retry.get(
        "risk_alert_level", pd.Series([""] * len(retry), index=retry.index)
    ).fillna("").astype(str).str.upper().isin({"P0", "P1"})
    if bool((manual | migration | risk).any()):
        blockers.append("stage904_ready_retry_open_manual_migration_blocked")
    blockers.extend(_stage904_retry_open_identity_blockers(retry))
    return blockers


def _stage904_retry_open_identity_blockers(retry: pd.DataFrame) -> list[str]:
    blockers: list[str] = []
    intent_ids = retry.get(
        "intent_id", pd.Series([""] * len(retry), index=retry.index)
    ).fillna("").astype(str).str.strip()
    action_ids = retry.get(
        "action_id", pd.Series([""] * len(retry), index=retry.index)
    ).fillna("").astype(str).str.strip()
    roles = retry.get(
        "intent_role", pd.Series([""] * len(retry), index=retry.index)
    ).fillna("").astype(str).str.strip()
    if bool(intent_ids.eq("").any()):
        blockers.append("stage904_retry_open_intent_id_missing")
    if bool(action_ids.eq("").any()):
        blockers.append("stage904_retry_open_action_id_missing")
    if bool(intent_ids.ne(action_ids).any()):
        blockers.append("stage904_retry_open_action_identity_mismatch")
    if bool(roles.ne(RETRY_OPEN_ACTION_ROLE).any()):
        blockers.append("stage904_retry_open_intent_role_mismatch")
    return blockers


def _stage904_retry_open_pre_send_blockers(
    row: dict[str, Any],
    *,
    target_date: str,
    max_age_seconds: int,
) -> list[str]:
    """Re-read Stage904 immediately before each risk-increasing CTP call."""

    current = _read_json(_stage904_summary_path(target_date))
    return _stage904_retry_open_snapshot_blockers(
        current,
        pd.DataFrame([row]),
        target_date=target_date,
        max_age_seconds=max_age_seconds,
    )


def _stage905_ready_intent_artifact_blockers(intents: pd.DataFrame) -> list[str]:
    """Cross-bind every ready Stage905 row to its immutable order payload."""

    if intents.empty:
        return []
    statuses = intents.get(
        "executor_status", pd.Series([""] * len(intents), index=intents.index)
    ).fillna("").astype(str)
    ready = intents[statuses.eq("dry_run_order_request_payload_ready")]
    blockers: list[str] = []
    for index, row in ready.iterrows():
        intent_id = _artifact_text(row.get("intent_id"))
        label = intent_id or str(index)
        try:
            payload = json.loads(str(row.get("order_request_json", "")))
        except (TypeError, json.JSONDecodeError):
            blockers.append(f"stage905_order_payload_invalid_json:{label}")
            continue
        if not isinstance(payload, dict) or not payload:
            blockers.append(f"stage905_order_payload_missing:{label}")
            continue

        source = _artifact_text(row.get("source"))
        row_offset = _normalize_offset_text(row.get("offset"))
        payload_offset = _normalize_offset_text(payload.get("offset"))
        role = _artifact_text(row.get("intent_role"))
        if _artifact_text(payload.get("intent_id")) != intent_id:
            blockers.append(f"stage905_order_payload_intent_id_mismatch:{label}")
        if _artifact_text(payload.get("source")) != source:
            blockers.append(f"stage905_order_payload_source_mismatch:{label}")
        for key in (
            "execution_profile",
            "official_live_version",
            "capital_label",
        ):
            if _artifact_text(payload.get(key)) != _artifact_text(row.get(key)):
                blockers.append(
                    f"stage905_order_payload_{key}_mismatch:{label}"
                )
        payload_capital = _artifact_text(payload.get("capital"))
        row_capital = _artifact_text(row.get("capital"))
        if (payload_capital or row_capital) and abs(
            _to_float(payload_capital, -1.0)
            - _to_float(row_capital, -2.0)
        ) > 1e-9:
            blockers.append(f"stage905_order_payload_capital_mismatch:{label}")
        if _artifact_text(payload.get("target_date")) != _artifact_text(
            row.get("target_date")
        ):
            blockers.append(f"stage905_order_payload_target_date_mismatch:{label}")
        if _artifact_text(payload.get("vt_symbol")) != _artifact_text(
            row.get("vt_symbol")
        ):
            blockers.append(f"stage905_order_payload_vt_symbol_mismatch:{label}")
        if _artifact_text(payload.get("symbol")) != _artifact_text(row.get("symbol")):
            blockers.append(f"stage905_order_payload_symbol_mismatch:{label}")
        if _artifact_text(payload.get("exchange")) != _artifact_text(
            row.get("exchange")
        ):
            blockers.append(f"stage905_order_payload_exchange_mismatch:{label}")
        if _normalize_direction_text(payload.get("direction")) != _normalize_direction_text(
            row.get("direction")
        ):
            blockers.append(f"stage905_order_payload_direction_mismatch:{label}")
        if payload_offset != row_offset:
            blockers.append(f"stage905_order_payload_offset_mismatch:{label}")
        if abs(_to_float(payload.get("volume"), -1.0) - _to_float(row.get("planned_volume"), -2.0)) > 1e-9:
            blockers.append(f"stage905_order_payload_volume_mismatch:{label}")
        if _to_float(payload.get("price"), 0.0) <= 0:
            blockers.append(f"stage905_order_payload_price_invalid:{label}")
        try:
            actual_type = _order_type_from_payload(payload.get("type"))
            policy = _artifact_text(payload.get("physical_tif_policy_version"))
            expected_type: OrderType | None = None
            expected_policy = ""
            if (
                row_offset == "open"
                and (
                    (source == "stage901_pending_order" and role == "c9_initial_open")
                    or (
                        source == "stage904_c9_intraday_retry_open"
                        and role == "c9_retry_open_once"
                    )
                )
            ):
                expected_type = OrderType.FAK
                expected_policy = "stage179_open_fak_v1"
            elif (
                row_offset == "close"
                and source == "stage904_c9_intraday_close"
                and role in {"c9_initial_stop_close", "c9_retry_failed_stop_close"}
            ):
                expected_type = OrderType.LIMIT
                expected_policy = "stage179_limit_gfd_v1"
            if expected_type is None or actual_type != expected_type:
                blockers.append(f"stage905_order_payload_type_invalid:{label}")
            if not expected_policy or policy != expected_policy:
                blockers.append(f"stage905_order_payload_tif_policy_invalid:{label}")
        except ValueError:
            blockers.append(f"stage905_order_payload_type_invalid:{label}")
        if _artifact_text(payload.get("gateway_name")) != "CTP":
            blockers.append(f"stage905_order_payload_gateway_invalid:{label}")
        if abs(
            _to_float(payload.get("price"), -1.0)
            - _to_float(row.get("order_request_price"), -2.0)
        ) > 1e-9:
            blockers.append(f"stage905_order_payload_price_mismatch:{label}")
        if abs(
            _to_float(payload.get("volume"), -1.0)
            - _to_float(row.get("order_request_volume"), -2.0)
        ) > 1e-9:
            blockers.append(f"stage905_order_payload_request_volume_mismatch:{label}")
        if str(payload.get("reference", "") or "") != f"Stage905PhaseD:{intent_id}":
            blockers.append(f"stage905_order_payload_reference_mismatch:{label}")

        for key in (
            "action_id",
            "root_position_id",
            "position_cycle_id",
            "position_epoch_id",
            "intent_role",
            "monitor_run_id",
            "risk_alert_level",
            "migration_blocker",
            "recommended_operator_action",
        ):
            if _artifact_text(payload.get(key)) != _artifact_text(row.get(key)):
                blockers.append(f"stage905_order_payload_{key}_mismatch:{label}")
        row_cycle_raw = row.get("position_cycle_no")
        payload_cycle_raw = payload.get("position_cycle_no")
        row_cycle_present = row_cycle_raw is not None and not bool(pd.isna(row_cycle_raw))
        payload_cycle_present = payload_cycle_raw is not None and not bool(pd.isna(payload_cycle_raw))
        if row_cycle_present or payload_cycle_present:
            row_cycle_no = _to_int(row.get("position_cycle_no"), -1)
            payload_cycle_no = _to_int(payload.get("position_cycle_no"), -2)
            if row_cycle_no != payload_cycle_no:
                blockers.append(f"stage905_order_payload_position_cycle_no_mismatch:{label}")

        if source == "stage904_c9_intraday_retry_open":
            if row_offset != "open" or role != RETRY_OPEN_ACTION_ROLE:
                blockers.append(f"stage905_retry_open_source_role_offset_mismatch:{label}")
        elif source == "stage904_c9_intraday_close":
            if row_offset != "close" or role not in {
                INITIAL_STOP_ACTION_ROLE,
                RETRY_STOP_ACTION_ROLE,
            }:
                blockers.append(f"stage905_close_source_role_offset_mismatch:{label}")
        elif source == "stage901_pending_order":
            if row_offset != "open" or role != "c9_initial_open":
                blockers.append(
                    f"stage905_initial_open_source_role_offset_mismatch:{label}"
                )
            if role != "c9_initial_open":
                blockers.append(
                    f"stage905_initial_open_source_role_mismatch:{label}"
                )
            root_position_id = _artifact_text(row.get("root_position_id"))
            position_cycle_id = _artifact_text(row.get("position_cycle_id"))
            if not root_position_id or not position_cycle_id:
                blockers.append(
                    f"stage905_initial_open_cycle_identity_missing:{label}"
                )
            target_date = _artifact_text(row.get("target_date"))
            vt_symbol = _artifact_text(row.get("vt_symbol"))
            direction = _normalize_direction_text(row.get("direction"))
            if not target_date or not vt_symbol or direction not in {"long", "short"}:
                blockers.append(
                    f"stage905_initial_open_root_identity_input_missing:{label}"
                )
            elif root_position_id:
                expected_root_id = generate_root_position_id(
                    target_date=target_date,
                    vt_symbol=vt_symbol,
                    direction=direction,
                )
                if root_position_id != expected_root_id:
                    blockers.append(
                        f"stage905_initial_open_root_identity_mismatch:{label}"
                    )
            cycle_raw = row.get("position_cycle_no")
            cycle_numeric = pd.to_numeric(cycle_raw, errors="coerce")
            cycle_is_zero = (
                not isinstance(cycle_raw, bool)
                and not pd.isna(cycle_numeric)
                and float(cycle_numeric) == 0.0
            )
            if not cycle_is_zero:
                blockers.append(
                    f"stage905_initial_open_cycle_no_invalid:{label}"
                )
            if root_position_id and position_cycle_id and cycle_is_zero:
                expected_cycle_id = generate_position_cycle_id(
                    root_position_id=root_position_id,
                    cycle_no=0,
                )
                if position_cycle_id != expected_cycle_id:
                    blockers.append(
                        f"stage905_initial_open_cycle_identity_mismatch:{label}"
                    )
            forbidden_fields = [
                key
                for key in STAGE904_ONLY_INTENT_FIELDS
                if _artifact_text(row.get(key)) or _artifact_text(payload.get(key))
            ]
            if forbidden_fields:
                blockers.append(
                    "stage905_initial_open_stage904_lineage_forbidden:"
                    f"{label}:{','.join(forbidden_fields)}"
                )
        elif source == "stage260_stage372_daily":
            if role or any(
                _artifact_text(row.get(key))
                for key in (
                    "root_position_id",
                    "position_cycle_id",
                    "position_epoch_id",
                    "action_id",
                    "monitor_run_id",
                )
            ):
                blockers.append(
                    f"stage905_stage372_c9_metadata_forbidden:{label}"
                )
        else:
            blockers.append(f"stage905_ready_intent_source_unknown:{label}:{source}")

        if not intent_id:
            blockers.append(f"stage905_ready_intent_id_missing:{label}")
        if source.startswith("stage904_c9_intraday_"):
            action_id = _artifact_text(row.get("action_id"))
            required_identity = {
                "action_id": action_id,
                "root_position_id": _artifact_text(row.get("root_position_id")),
                "position_cycle_id": _artifact_text(row.get("position_cycle_id")),
                "position_epoch_id": _artifact_text(row.get("position_epoch_id")),
                "intent_role": role,
                "monitor_run_id": _artifact_text(row.get("monitor_run_id")),
            }
            missing = [key for key, value in required_identity.items() if not value]
            if missing:
                blockers.append(
                    f"stage905_stage904_identity_missing:{label}:{','.join(missing)}"
                )
            if action_id != intent_id:
                blockers.append(f"stage905_stage904_action_identity_mismatch:{label}")

        if source.startswith("stage904_c9_intraday_"):
            row_manual_valid, row_manual = _canonical_binary_flag(
                row.get("manual_intervention_required")
            )
            payload_manual_valid, payload_manual = _canonical_binary_flag(
                payload.get("manual_intervention_required")
            )
            if (
                not row_manual_valid
                or not payload_manual_valid
                or row_manual != payload_manual
            ):
                blockers.append(f"stage905_order_payload_manual_flag_mismatch:{label}")
    return list(dict.fromkeys(blockers))


def _artifact_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if bool(pd.isna(value)):
            return ""
    except (TypeError, ValueError):
        return ""
    return str(value).strip()


def _execution_profile_intent_blockers(
    profile: OfficialExecutionProfile,
    row: Mapping[str, Any],
) -> list[str]:
    blockers: list[str] = []
    if _artifact_text(row.get("execution_profile")) != profile.profile_key:
        blockers.append("execution_profile_mismatch")
    if _artifact_text(row.get("official_live_version")) != profile.official_version:
        blockers.append("execution_profile_version_mismatch")
    if abs(_to_float(row.get("capital"), -1.0) - profile.capital) > 1e-9:
        blockers.append("execution_profile_capital_mismatch")
    if _artifact_text(row.get("capital_label")) != profile.capital_label:
        blockers.append("execution_profile_capital_label_mismatch")
    source = _artifact_text(row.get("source"))
    if source not in profile.allowed_intent_sources:
        blockers.append("intent_source_not_allowed_for_execution_profile")
    if not profile.intraday_stop_retry_enabled:
        c9_metadata = (
            source.startswith("stage904_c9_intraday_")
            or _artifact_text(row.get("intent_role")).startswith("c9_")
            or any(
                _artifact_text(row.get(key))
                for key in (
                    "root_position_id",
                    "position_cycle_id",
                    "position_epoch_id",
                    "parent_position_cycle_id",
                    "action_id",
                    "monitor_run_id",
                )
            )
        )
        if c9_metadata:
            blockers.append("stage372_c9_intent_metadata_forbidden")
    return list(dict.fromkeys(blockers))


def _stage905_execution_profile_blockers(
    profile: OfficialExecutionProfile,
    intents: pd.DataFrame,
) -> list[str]:
    if intents.empty:
        return []
    statuses = intents.get(
        "executor_status",
        pd.Series([""] * len(intents), index=intents.index),
    ).fillna("").astype(str)
    blockers: list[str] = []
    for index, row in intents[statuses.eq(
        "dry_run_order_request_payload_ready"
    )].iterrows():
        label = _artifact_text(row.get("intent_id")) or str(index)
        blockers.extend(
            f"{blocker}:{label}"
            for blocker in _execution_profile_intent_blockers(
                profile,
                row.to_dict(),
            )
        )
    return list(dict.fromkeys(blockers))


def _pre_reserved_child_intent_blockers(
    row: dict[str, Any], req: OrderRequest
) -> list[str]:
    """Defend the final broker request against row/payload identity confusion."""

    source = _artifact_text(row.get("source"))
    if not source:
        return []  # Compatibility for isolated accounting tests, never official rows.
    candidate = dict(row)
    candidate["executor_status"] = "dry_run_order_request_payload_ready"
    blockers = _stage905_ready_intent_artifact_blockers(pd.DataFrame([candidate]))
    row_offset = _normalize_offset_text(row.get("offset"))
    request_offset = _normalize_offset_text(req.offset.value)
    request_is_close = req.offset in {
        Offset.CLOSE,
        Offset.CLOSETODAY,
        Offset.CLOSEYESTERDAY,
    }
    if row_offset == "open" and req.offset != Offset.OPEN:
        blockers.append("pre_send_row_request_offset_mismatch")
    if row_offset == "close" and not request_is_close:
        blockers.append("pre_send_row_request_offset_mismatch")
    if row_offset not in {"open", "close"} or request_offset not in {
        "open",
        "close",
    }:
        blockers.append("pre_send_request_offset_invalid")
    return list(dict.fromkeys(blockers))


def _ledger_daily_slot_blockers(
    ledger_counts: dict[str, Any],
    *,
    max_send_orders: int,
    max_cancel_orders: int,
) -> list[str]:
    blockers: list[str] = []
    if _to_int(ledger_counts.get("send_order_slot_usage"), 0) >= max_send_orders:
        blockers.append("ledger_daily_send_order_limit_reached")
    if _to_int(ledger_counts.get("cancel_order_slot_usage"), 0) >= max_cancel_orders:
        blockers.append("ledger_daily_cancel_order_limit_reached")
    return blockers


def _ready_intents_row_close_only(ready: pd.DataFrame) -> bool:
    if ready.empty:
        return False
    sources = ready.get("source", pd.Series([""] * len(ready))).fillna("").astype(str)
    offsets = ready.get("offset", pd.Series([""] * len(ready))).fillna("").astype(str).str.lower()
    return bool(sources.eq("stage904_c9_intraday_close").all() and offsets.eq("close").all())


def _ready_intents_close_only(ready: pd.DataFrame) -> bool:
    if not _ready_intents_row_close_only(ready):
        return False
    if _stage905_ready_intent_artifact_blockers(ready):
        return False
    for row in ready.to_dict(orient="records"):
        try:
            payload = json.loads(str(row.get("order_request_json", "")))
        except (TypeError, json.JSONDecodeError):
            return False
        if _normalize_offset_text(payload.get("offset")) != "close":
            return False
    return True


def _stage905_cycle_artifact_blockers(
    stage905_intents: pd.DataFrame,
    selected_ready: pd.DataFrame,
    *,
    reduce_close_only: bool,
) -> list[str]:
    """Keep unrelated open corruption from starving a proven close-only cycle."""

    if reduce_close_only and _ready_intents_close_only(selected_ready):
        return _stage905_ready_intent_artifact_blockers(selected_ready)
    return _stage905_ready_intent_artifact_blockers(stage905_intents)


def _bound_ready_intents_for_cycle(
    ready: pd.DataFrame,
    *,
    max_orders: int,
    reduce_close_only: bool,
) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    """Bound one adapter cycle without making all protective closes unreachable."""

    limit = max(0, int(max_orders))
    if len(ready) <= limit:
        return ready.copy(), ready.iloc[0:0].copy(), ""
    if not reduce_close_only or not _ready_intents_row_close_only(ready):
        return ready.copy(), ready.iloc[0:0].copy(), "ready_intent_count_above_limit"

    ordered = ready.copy()
    sort_columns = [
        key
        for key in ("checked_at", "action_id", "intent_id", "vt_symbol", "direction")
        if key in ordered.columns
    ]
    if sort_columns:
        ordered = ordered.sort_values(sort_columns, kind="stable", na_position="last")
    selected = ordered.head(limit).copy()
    deferred = ordered.iloc[limit:].copy()
    return selected, deferred, ""


def _drop_terminal_duplicate_close_intents(
    ready: pd.DataFrame,
    *,
    ledger_rows: list[dict[str, Any]],
    target_date: str,
    close_retry_after_cancel_seconds: int,
    reduce_close_only: bool,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Partition fingerprint-scoped nonretryable closes before ``head(1)``.

    A permanently blocked close must remain visible in the audit output, but
    it must not starve a later healthy symbol forever.  This optimization is
    legal only in an explicitly reduce-close-only queue.  Mixed close/open
    queues retain their original global limit blocker so unresolved risk can
    never be converted into permission to open new risk.

    The allowlist is intentionally explicit.  Throttles/active leases,
    ledger-integrity failures and unknown future blockers remain selectable
    and therefore fail the whole cycle closed.

    The historical function name is retained because existing offline tools
    import it directly.
    """

    if ready.empty:
        return ready.copy(), ready.copy()
    if not reduce_close_only or not _ready_intents_row_close_only(ready):
        return ready.copy(), ready.iloc[0:0].copy()
    keep_indices: list[Any] = []
    skipped_indices: list[Any] = []
    blocker_by_index: dict[Any, str] = {}
    fingerprint_by_index: dict[Any, str] = {}
    evidence_event_by_index: dict[Any, str] = {}
    for index, row in ready.iterrows():
        try:
            payload = json.loads(str(row.get("order_request_json", "{}")))
            blocker, fingerprint, _, evidence = duplicate_blocker(
                rows=ledger_rows,
                target_date=target_date,
                row=row.to_dict(),
                order_request=payload,
                close_retry_after_cancel_seconds=close_retry_after_cancel_seconds,
            )
        except (json.JSONDecodeError, ValueError):
            keep_indices.append(index)
            continue
        if blocker in FINGERPRINT_SCOPED_NONRETRYABLE_CLOSE_BLOCKERS:
            skipped_indices.append(index)
            blocker_by_index[index] = blocker
            fingerprint_by_index[index] = fingerprint
            evidence_event_by_index[index] = str(
                (evidence or {}).get("event_type", "") or ""
            )
        else:
            keep_indices.append(index)
    eligible = ready.loc[keep_indices].copy()
    nonretryable = ready.loc[skipped_indices].copy()
    if not nonretryable.empty:
        nonretryable["ledger_preselection_blocker"] = [
            blocker_by_index[index] for index in skipped_indices
        ]
        nonretryable["ledger_preselection_fingerprint"] = [
            fingerprint_by_index[index] for index in skipped_indices
        ]
        nonretryable["ledger_preselection_evidence_event"] = [
            evidence_event_by_index[index] for index in skipped_indices
        ]
    return eligible, nonretryable


def _order_request_from_payload(payload: dict[str, Any]) -> OrderRequest:
    return OrderRequest(
        symbol=str(payload["symbol"]),
        exchange=Exchange(str(payload["exchange"])),
        direction=_direction_from_payload(payload["direction"]),
        type=_order_type_from_payload(payload.get("type")),
        volume=float(payload["volume"]),
        price=float(payload["price"]),
        offset=_offset_from_payload(payload["offset"]),
        reference=str(payload.get("reference", "Stage931OfficialLive")),
    )


def _final_offset_conversion(
    main_engine: Any,
    rows: dict[str, list[dict[str, Any]]],
    req: OrderRequest,
) -> dict[str, Any]:
    """Convert one final SHFE/INE close into auditable broker child requests.

    Conversion deliberately happens only after the ordinary final pre-send
    gates.  The converter must already contain the same reqid-bound position
    snapshot used by those gates; otherwise Stage931 fails closed instead of
    guessing whether the position is today or yesterday inventory.
    """

    result: dict[str, Any] = {
        "requests": [req],
        "blockers": [],
        "converted": False,
        "diagnostics": {},
    }
    if req.offset != Offset.CLOSE or req.exchange not in {Exchange.SHFE, Exchange.INE}:
        return result

    get_converter = getattr(main_engine, "get_converter", None)
    if not callable(get_converter):
        result["requests"] = []
        result["blockers"] = ["final_offset_converter_accessor_missing"]
        return result
    converter = get_converter("CTP")
    if converter is None:
        result["requests"] = []
        result["blockers"] = ["final_offset_converter_missing:CTP"]
        return result

    get_holding = getattr(converter, "get_position_holding", None)
    if not callable(get_holding):
        result["requests"] = []
        result["blockers"] = ["final_offset_converter_holding_accessor_missing"]
        return result
    holding = get_holding(req.vt_symbol)
    if holding is None:
        result["requests"] = []
        result["blockers"] = [f"final_offset_converter_holding_missing:{req.vt_symbol}"]
        return result

    position_direction = _opposite_position_direction(_normalize_direction_text(req.direction.value))
    matching_rows = [
        row
        for row in rows.get("positions", [])
        if _vt_symbol_from_row(row) == req.vt_symbol
        and _normalize_direction_text(row.get("direction")) == position_direction
    ]
    if not matching_rows or any(
        "today_volume" not in row or "yesterday_volume" not in row for row in matching_rows
    ):
        result["requests"] = []
        result["blockers"] = [f"final_offset_authoritative_position_components_missing:{req.vt_symbol}"]
        return result

    raw_total = sum(max(0.0, _to_float(row.get("volume"), 0.0)) for row in matching_rows)
    raw_today = sum(max(0.0, _to_float(row.get("today_volume"), 0.0)) for row in matching_rows)
    raw_yesterday = sum(max(0.0, _to_float(row.get("yesterday_volume"), 0.0)) for row in matching_rows)
    raw_frozen = sum(max(0.0, _to_float(row.get("frozen"), 0.0)) for row in matching_rows)
    if req.direction == Direction.LONG:
        holding_total = float(holding.short_pos)
        holding_today = float(holding.short_td)
        holding_yesterday = float(holding.short_yd)
        holding_frozen = float(holding.short_pos_frozen)
    else:
        holding_total = float(holding.long_pos)
        holding_today = float(holding.long_td)
        holding_yesterday = float(holding.long_yd)
        holding_frozen = float(holding.long_pos_frozen)

    diagnostics = {
        "raw_total": raw_total,
        "raw_today": raw_today,
        "raw_yesterday": raw_yesterday,
        "raw_frozen": raw_frozen,
        "converter_total": holding_total,
        "converter_today": holding_today,
        "converter_yesterday": holding_yesterday,
        "converter_frozen": holding_frozen,
        "requested_volume": float(req.volume),
    }
    result["diagnostics"] = diagnostics
    component_pairs = (
        ("total", raw_total, holding_total),
        ("today", raw_today, holding_today),
        ("yesterday", raw_yesterday, holding_yesterday),
        ("frozen", raw_frozen, holding_frozen),
    )
    component_blockers = [
        f"final_offset_converter_snapshot_mismatch:{name}:raw={raw};converter={converted}"
        for name, raw, converted in component_pairs
        if not math.isclose(raw, converted, rel_tol=0.0, abs_tol=1e-9)
    ]
    if not math.isclose(raw_today + raw_yesterday, raw_total, rel_tol=0.0, abs_tol=1e-9):
        component_blockers.append(
            "final_offset_authoritative_components_do_not_sum_to_total:"
            f"today={raw_today};yesterday={raw_yesterday};total={raw_total}"
        )
    if not math.isclose(
        holding_today + holding_yesterday,
        holding_total,
        rel_tol=0.0,
        abs_tol=1e-9,
    ):
        component_blockers.append(
            "final_offset_converter_components_do_not_sum_to_total:"
            f"today={holding_today};yesterday={holding_yesterday};total={holding_total}"
        )
    raw_available = max(0.0, raw_total - raw_frozen)
    converter_available = max(0.0, holding_total - holding_frozen)
    if not math.isclose(raw_available, float(req.volume), rel_tol=0.0, abs_tol=1e-9):
        component_blockers.append(
            "final_offset_authoritative_available_volume_mismatch:"
            f"available={raw_available};request={req.volume}"
        )
    if not math.isclose(converter_available, float(req.volume), rel_tol=0.0, abs_tol=1e-9):
        component_blockers.append(
            "final_offset_converter_available_volume_mismatch:"
            f"available={converter_available};request={req.volume}"
        )
    if component_blockers:
        result["requests"] = []
        result["blockers"] = component_blockers
        return result

    try:
        children = list(converter.convert_order_request(req, lock=False, net=False))
    except Exception as exc:
        result["requests"] = []
        result["blockers"] = [f"final_offset_conversion_exception:{exc!r}"]
        return result
    if not children:
        result["requests"] = []
        result["blockers"] = ["final_offset_conversion_returned_empty"]
        return result

    child_blockers: list[str] = []
    total_volume = 0.0
    for index, child in enumerate(children):
        prefix = f"final_offset_child_invalid:index={index}"
        if not isinstance(child, OrderRequest):
            child_blockers.append(f"{prefix}:type={type(child).__name__}")
            continue
        total_volume += float(child.volume)
        if child.symbol != req.symbol:
            child_blockers.append(f"{prefix}:symbol={child.symbol}!={req.symbol}")
        if child.exchange != req.exchange:
            child_blockers.append(f"{prefix}:exchange={child.exchange.value}!={req.exchange.value}")
        if child.direction != req.direction:
            child_blockers.append(f"{prefix}:direction={child.direction.value}!={req.direction.value}")
        if child.type != req.type:
            child_blockers.append(
                f"{prefix}:order_type={child.type.name}!={req.type.name}"
            )
        if float(child.price) != float(req.price):
            child_blockers.append(f"{prefix}:price={child.price}!={req.price}")
        if float(child.volume) <= 0:
            child_blockers.append(f"{prefix}:nonpositive_volume={child.volume}")
        if child.offset not in {Offset.CLOSETODAY, Offset.CLOSEYESTERDAY}:
            child_blockers.append(f"{prefix}:offset={child.offset.value}")
    if not math.isclose(total_volume, float(req.volume), rel_tol=0.0, abs_tol=1e-9):
        child_blockers.append(
            f"final_offset_child_volume_mismatch:children={total_volume};request={req.volume}"
        )
    if child_blockers:
        result["requests"] = []
        result["blockers"] = child_blockers
        return result

    result["requests"] = children
    result["converted"] = True
    result["diagnostics"] = {
        **diagnostics,
        "child_count": len(children),
        "child_offsets": [child.offset.value for child in children],
        "child_volumes": [float(child.volume) for child in children],
    }
    return result


def _enforce_physical_order_time_in_force(
    requests: list[OrderRequest],
) -> list[str]:
    blockers: list[str] = []
    for request in requests:
        if request.offset in {
            Offset.CLOSE,
            Offset.CLOSETODAY,
            Offset.CLOSEYESTERDAY,
        }:
            if request.type != OrderType.LIMIT:
                blockers.append(
                    "stage179_close_physical_type_not_limit:"
                    f"{request.offset.name}"
                )
            continue
        if request.offset != Offset.OPEN:
            continue
        if request.exchange not in FAK_OPEN_EXCHANGES:
            blockers.append(
                f"stage179_open_fak_exchange_not_allowlisted:{request.exchange.value}"
            )
            continue
        if request.type != OrderType.FAK:
            blockers.append("stage179_open_physical_type_not_fak")
    return blockers


def _converted_child_cycle_blocker(
    *,
    child_count: int,
    max_physical_orders: int,
    send_count: int,
) -> str:
    """Bound physical API calls independently of the logical-intent limit."""

    remaining = max(0, int(max_physical_orders) - int(send_count))
    if int(child_count) <= remaining:
        return ""
    return (
        "final_converted_child_count_above_cycle_limit:"
        f"children={int(child_count)};remaining={remaining}"
    )


def _status_is_active(status_value: Any) -> bool:
    text = str(status_value).strip().lower()
    return text in ACTIVE_ORDER_STATUSES


def _status_is_terminal(status_value: Any) -> bool:
    text = str(status_value).strip().lower()
    return text in TERMINAL_ORDER_STATUSES


def _status_is_unknown(status_value: Any) -> bool:
    text = str(status_value).strip().lower()
    return text not in ACTIVE_ORDER_STATUSES and text not in TERMINAL_ORDER_STATUSES


def _close_terminal_status_class(status_value: Any) -> str:
    text = str(status_value or "").strip().lower()
    if text in CANCELLED_ORDER_STATUSES:
        return "cancelled"
    if text in REJECTED_ORDER_STATUSES:
        return "rejected"
    return ""


def _req_order_insert_audit_since(
    rows: dict[str, Any], start_index: int
) -> dict[str, Any]:
    attempts = list(rows.get("order_insert_requests", []))[start_index:]
    result: dict[str, Any] = {
        "req_order_insert_audit_observed": 0,
        "req_order_insert_audit_row_count": len(attempts),
        "req_order_insert_reqid": "",
        "req_order_insert_request_ret": "",
        "req_order_insert_accepted": "",
        "req_order_insert_exception": "",
    }
    if len(attempts) != 1 or not isinstance(attempts[0], dict):
        return result
    attempt = attempts[0]
    result["req_order_insert_reqid"] = attempt.get("reqid", "")
    result["req_order_insert_exception"] = str(
        attempt.get("exception", "") or ""
    )
    request_ret = pd.to_numeric(attempt.get("request_ret"), errors="coerce")
    if result["req_order_insert_exception"] or pd.isna(request_ret):
        return result
    result["req_order_insert_audit_observed"] = 1
    result["req_order_insert_request_ret"] = int(request_ret)
    result["req_order_insert_accepted"] = int(int(request_ret) == 0)
    return result


def _close_retry_terminal_audit_fields(
    *,
    req: OrderRequest,
    context: dict[str, Any],
    insert_audit: dict[str, Any],
    vt_orderid: str,
    latest_order: dict[str, Any] | None,
    order_traded_volume: float,
    trade_event_total_volume: float,
    trade_event_priced_volume: float,
    unpriced_volume: float,
    residual_volume: float,
    trade_callback_count: int,
    send_order_returned_empty: bool = False,
) -> dict[str, Any]:
    """Build explicit audit fields; absence or ambiguity never unlocks retry."""

    if req.offset == Offset.OPEN:
        return {}
    latest = latest_order or {}
    status_class = _close_terminal_status_class(latest.get("status"))
    attempt_no = _to_int(context.get("close_submit_attempt_no"), 0)
    requested_volume = float(req.volume)
    zero_volume_evidence = bool(
        requested_volume > 0.0
        and math.isclose(float(order_traded_volume), 0.0, abs_tol=1e-9)
        and math.isclose(float(trade_event_total_volume), 0.0, abs_tol=1e-9)
        and math.isclose(float(trade_event_priced_volume), 0.0, abs_tol=1e-9)
        and math.isclose(float(unpriced_volume), 0.0, abs_tol=1e-9)
        and math.isclose(
            float(residual_volume), requested_volume, rel_tol=0.0, abs_tol=1e-9
        )
        and int(trade_callback_count) == 0
    )
    insert_observed = _to_int(
        insert_audit.get("req_order_insert_audit_observed"), 0
    ) == 1
    insert_accepted = _to_int(
        insert_audit.get("req_order_insert_accepted"), -1
    )
    request_ret = pd.to_numeric(
        insert_audit.get("req_order_insert_request_ret"), errors="coerce"
    )
    reason = ""
    known_zero = False
    if send_order_returned_empty:
        known_zero = bool(
            not vt_orderid
            and insert_observed
            and insert_accepted == 0
            and not pd.isna(request_ret)
            and float(request_ret) != 0.0
            and zero_volume_evidence
            and attempt_no in {1, 2}
        )
        if known_zero:
            reason = "req_order_insert_not_accepted"
    elif latest and status_class in {"cancelled", "rejected"}:
        known_zero = bool(
            vt_orderid
            and insert_observed
            and insert_accepted == 1
            and zero_volume_evidence
            and attempt_no in {1, 2}
        )
        if known_zero:
            reason = f"terminal_{status_class}_zero_fill"

    return {
        "close_retry_audit_version": CLOSE_RETRY_AUDIT_VERSION,
        "close_submit_attempt_no": attempt_no,
        "close_retry_known_zero": int(known_zero),
        "close_retry_unlock_eligible": int(known_zero and attempt_no == 1),
        "close_retry_known_zero_reason": reason,
        "main_engine_send_order_returned_empty": int(send_order_returned_empty),
        "order_callback_observed": int(bool(latest_order)),
        "close_terminal_status_class": status_class,
        "order_traded_volume": float(order_traded_volume),
        "trade_event_total_volume": float(trade_event_total_volume),
        "trade_event_priced_volume": float(trade_event_priced_volume),
        "trade_callback_count": int(trade_callback_count),
        "unpriced_volume": float(unpriced_volume),
        "residual_volume": float(residual_volume),
        **insert_audit,
    }


def _latest_order(orders: list[dict[str, Any]], vt_orderid: str) -> dict[str, Any] | None:
    gateway, _, orderid = vt_orderid.partition(".")
    matched = [
        row
        for row in orders
        if str(row.get("vt_orderid", "")) == vt_orderid
        or (
            str(row.get("gateway_name", "")) == gateway
            and str(row.get("orderid", "")) == orderid
        )
    ]
    return matched[-1] if matched else None


def _match_reqid_bound_ctp_order(
    orders: list[dict[str, Any]], vt_orderid: str
) -> tuple[dict[str, Any] | None, str]:
    """Bind vn.py CTP.<front>_<session>_<ref> to one raw query row."""

    gateway, separator, local_orderid = str(vt_orderid).partition(".")
    parts = local_orderid.split("_", 2)
    if gateway != "CTP" or not separator or len(parts) != 3 or not all(parts):
        return None, "stage179_recovery_vt_orderid_identity_invalid"
    front_id, session_id, order_ref = parts
    matches = [
        row
        for row in orders
        if str(row.get("front_id", "")) == front_id
        and str(row.get("session_id", "")) == session_id
        and str(row.get("order_ref", "")) == order_ref
    ]
    if len(matches) != 1:
        return None, (
            "stage179_recovery_order_identity_absent"
            if not matches
            else "stage179_recovery_order_identity_ambiguous"
        )
    return matches[0], ""


def _unique_trade_callback_totals(
    trades: list[dict[str, Any]], vt_orderid: str
) -> tuple[dict[str, Any], str]:
    unique: dict[str, tuple[float, float]] = {}
    for row in trades:
        if str(row.get("vt_orderid", "")) != vt_orderid:
            continue
        vt_symbol = str(row.get("vt_symbol", "") or "")
        exchange = str(row.get("exchange", "") or "") or (
            vt_symbol.rpartition(".")[2] if "." in vt_symbol else ""
        )
        tradeid = str(row.get("tradeid", "") or "")
        vt_tradeid = str(row.get("vt_tradeid", "") or "")
        if not tradeid and vt_tradeid.startswith("CTP."):
            tradeid = vt_tradeid[len("CTP.") :].split(".")[-1]
        identity = f"ctp:{exchange}:{tradeid}" if exchange and tradeid else vt_tradeid
        if not identity:
            return {}, f"stage179_trade_identity_missing:{vt_orderid}"
        payload = (
            _to_float(row.get("price"), 0.0),
            max(0.0, _to_float(row.get("volume"), 0.0)),
        )
        if identity in unique and unique[identity] != payload:
            return {}, f"stage179_trade_identity_payload_mismatch:{identity}"
        unique[identity] = payload
    return {
        "count": len(unique),
        "total_volume": sum(item[1] for item in unique.values()),
        "priced_volume": sum(item[1] for item in unique.values() if item[0] > 0),
    }, ""


def _exact_durable_priced_volume(
    ledger_rows: list[dict[str, Any]],
    *,
    context: Mapping[str, Any],
    vt_orderid: str,
) -> tuple[float, str]:
    """Sum fsynced fills only inside one exact spool lease/child identity."""

    expected = {
        "target_date": str(context.get("target_date", "") or ""),
        "intent_fingerprint": str(
            context.get("intent_fingerprint")
            or context.get("fingerprint")
            or ""
        ),
        "spool_lease_owner": str(context.get("spool_lease_owner", "") or ""),
        "spool_lease_token": str(context.get("spool_lease_token", "") or ""),
        "child_order_id": str(context.get("child_order_id", "") or ""),
    }
    missing = [key for key, value in expected.items() if not value]
    if missing or not vt_orderid:
        return 0.0, "stage179_durable_fill_identity_missing:" + ",".join(
            [*missing, *( ["vt_orderid"] if not vt_orderid else [])]
        )
    unique: dict[str, tuple[float, float]] = {}
    for row in ledger_rows:
        if row.get("event_type") != "filled_or_part_filled":
            continue
        if str(row.get("vt_orderid", "") or "") != vt_orderid:
            continue
        if any(
            str(row.get(key, "") or "") != value
            for key, value in expected.items()
        ):
            continue
        identity = str(
            row.get("vt_tradeid")
            or row.get("trade_fill_key")
            or row.get("broker_callback_key")
            or ""
        )
        if not identity:
            return 0.0, "stage179_durable_fill_trade_identity_missing"
        payload = (
            _to_float(row.get("price"), 0.0),
            max(0.0, _to_float(row.get("trade_volume_delta"), 0.0)),
        )
        if identity in unique and unique[identity] != payload:
            return 0.0, (
                "stage179_durable_fill_trade_identity_conflict:" + identity
            )
        unique[identity] = payload
    return sum(volume for price, volume in unique.values() if price > 0), ""


class _RecoverableReconciliationBlockers:
    """Key transient reconciliation failures by physical order identity."""

    def __init__(self, lock: threading.RLock | None = None) -> None:
        self._values: dict[str, str] = {}
        self._lock = lock or threading.RLock()

    @staticmethod
    def _key(value: Any) -> str:
        text = str(value or "")
        marker = text.rfind(":CTP.")
        return text[marker + 1 :] if marker >= 0 else text

    def append(self, value: Any) -> None:
        text = str(value or "")
        if text:
            with self._lock:
                self._values[self._key(text)] = text

    def extend(self, values: Any) -> None:
        for value in values:
            self.append(value)

    def resolve(self, vt_orderid: str) -> None:
        with self._lock:
            self._values.pop(str(vt_orderid), None)

    def __iter__(self):
        with self._lock:
            return iter(tuple(self._values.values()))

    def __bool__(self) -> bool:
        with self._lock:
            return bool(self._values)


class _ThreadSafeIdentitySet:
    def __init__(self, lock: threading.RLock) -> None:
        self._values: set[str] = set()
        self._lock = lock

    def add(self, value: Any) -> None:
        with self._lock:
            self._values.add(str(value))

    def discard(self, value: Any) -> None:
        with self._lock:
            self._values.discard(str(value))

    def __iter__(self):
        with self._lock:
            return iter(tuple(self._values))

    def __bool__(self) -> bool:
        with self._lock:
            return bool(self._values)


def _resolve_reconciliation_order(state: dict[str, Any], vt_orderid: str) -> None:
    lock = state.get("reconciliation_lock")
    manager = lock if hasattr(lock, "__enter__") else nullcontext()
    with manager:
        state.get("reconciliation_pending_order_ids", set()).discard(vt_orderid)
        blockers = state.get("reconciliation_blockers")
        if isinstance(blockers, _RecoverableReconciliationBlockers):
            blockers.resolve(vt_orderid)


def _order_traded_volume(latest_order: dict[str, Any] | None, fallback: float) -> float:
    if not latest_order:
        return fallback
    traded = pd.to_numeric(latest_order.get("traded", fallback), errors="coerce")
    return fallback if pd.isna(traded) else float(traded)


def _monotonic_order_traded_volume(latest_order: dict[str, Any] | None, observed_volume: float) -> float:
    return max(max(0.0, float(observed_volume)), _order_traded_volume(latest_order, observed_volume))


def _fill_reconciliation_state(
    *,
    order_traded_volume: float,
    trade_event_volume: float,
    requested_volume: float,
    trade_event_total_volume: float | None = None,
) -> dict[str, Any]:
    """Classify filled volume that has no durable EVENT_TRADE price/detail yet."""
    order_volume = max(0.0, float(order_traded_volume))
    priced_event_volume = max(0.0, float(trade_event_volume))
    total_event_volume = max(
        priced_event_volume,
        max(0.0, float(trade_event_total_volume))
        if trade_event_total_volume is not None
        else priced_event_volume,
    )
    requested = max(0.0, float(requested_volume))
    effective = max(order_volume, total_event_volume)
    unpriced = max(0.0, effective - priced_event_volume)
    return {
        "pending": bool(unpriced > 1e-9),
        "blocker": "fill_reconciliation_pending" if unpriced > 1e-9 else "",
        "effective_traded_volume": effective,
        "order_traded_volume": order_volume,
        # Backward-compatible name: this is the volume with a positive
        # EVENT_TRADE price and therefore the only volume safe to ledger as a
        # priced fill.
        "trade_event_volume": priced_event_volume,
        "trade_event_priced_volume": priced_event_volume,
        "trade_event_total_volume": total_event_volume,
        "unpriced_volume": unpriced,
        "residual_volume": max(0.0, requested - effective),
    }


def _wait_order_completion(rows: dict[str, list[dict[str, Any]]], vt_orderid: str, req_volume: float, deadline: float) -> dict[str, Any]:
    latest: dict[str, Any] | None = None
    while time.time() < deadline:
        latest = _latest_order(rows["orders"], vt_orderid)
        traded_volume = _order_traded_volume(latest, 0.0)
        if latest and (_status_is_terminal(latest.get("status")) or traded_volume >= req_volume):
            break
        time.sleep(0.2)
    latest = _latest_order(rows["orders"], vt_orderid)
    return latest or {}


def _build_report(summary: dict[str, Any], submitted: pd.DataFrame) -> str:
    return "\n".join(
        [
            "# Stage931 官方实盘 CTP 提交适配器报告",
            "",
            f"- 生成时间：`{summary['generated_at']}`",
            f"- 官方版本：`{summary['official_live_version']}` / `{summary['official_live_alias']}`",
            f"- 目标交易日：`{summary['target_date']}`",
            f"- 模式：`{summary['mode']}`",
            f"- 适配器状态：`{summary['adapter_status']}`",
            f"- 待提交意图数量：`{summary['ready_intent_count']}`",
            f"- 报单 API 调用次数：`{summary['send_order_api_called_count']}`",
            f"- 撤单 API 调用次数：`{summary['cancel_order_api_called_count']}`",
            "",
            "## 本次处理的指令",
            "",
            submitted.head(80).to_markdown(index=False) if not submitted.empty else "_empty_",
            "",
            "## 执行纪律",
            "",
            "- dry-run 模式不会连接 CTP，也不会调用 send_order/cancel_order。",
            "- live-real 模式必须同时满足 Stage927 放行、真实提交环境变量、精确确认文本和 kill switch 未启用。",
            "- 已提交但未成交的活动委托，会在配置的等待时间后尝试撤单。",
            "",
        ]
    )


def _should_notify(summary: dict[str, Any]) -> bool:
    if summary.get("mode") == "live-real":
        return (
            int(summary.get("ready_intent_count", 0)) > 0
            or int(summary.get("order_api_called_count", 0)) > 0
            or str(summary.get("adapter_status", "")) == "adapter_exception"
            or int(summary.get("trade_row_count", 0)) > 0
            or int(summary.get("blocking_failure_count", 0)) > 0
        )
    return int(summary.get("ready_intent_count", 0)) > 0


def _email_throttle_key(summary: dict[str, Any]) -> str:
    normalized_blockers = []
    for blocker in summary.get("blockers", []):
        text = str(blocker)
        if text.startswith(("stage927_summary_stale_or_missing:", "stage905_summary_stale_or_missing:", "live_real_target_date_stale_or_invalid:")):
            text = text.split(":", 1)[0]
        normalized_blockers.append(text)
    payload = {
        "target_date": summary.get("target_date"),
        "mode": summary.get("mode"),
        "adapter_status": summary.get("adapter_status"),
        "blockers": normalized_blockers,
    }
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _email_throttle_allows(summary: dict[str, Any], min_seconds: int = 1800) -> tuple[bool, str]:
    if int(summary.get("order_api_called_count", 0)) > 0 or int(summary.get("trade_row_count", 0)) > 0:
        return True, "order_or_trade_never_throttled"
    key = _email_throttle_key(summary)
    state = _read_json(EMAIL_THROTTLE_PATH)
    last_sent = _parse_dt((state.get(key) or {}).get("last_sent_at") if isinstance(state.get(key), dict) else "")
    if last_sent is not None and (datetime.now() - last_sent).total_seconds() < min_seconds:
        return False, f"email_throttled:{key}"
    state[key] = {"last_sent_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "summary": summary.get("adapter_status")}
    EMAIL_THROTTLE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return True, key


def _send_submit_email(paths: dict[str, Path], summary: dict[str, Any], submitted: pd.DataFrame) -> dict[str, Any]:
    if not _should_notify(summary):
        return {
            "email_status": "skipped_no_key_event",
            "reason": "no ready intent/order api/trade/exception",
        }
    throttle_allowed, throttle_key = _email_throttle_allows(summary)
    if not throttle_allowed:
        return {"email_status": "skipped_throttled", "reason": throttle_key, "throttle_path": str(EMAIL_THROTTLE_PATH.resolve())}
    severity = "info"
    if int(summary.get("trade_row_count", 0)) > 0 or int(summary.get("order_api_called_count", 0)) > 0:
        severity = "critical"
    elif int(summary.get("blocking_failure_count", 0)) > 0 or summary.get("adapter_status") == "adapter_exception":
        severity = "warning"
    subject = (
        f"[C9/15w 真实提交][{severity}] {summary['target_date']} "
        f"{summary['adapter_status']} 下单API={summary['order_api_called_count']} 成交行={summary['trade_row_count']}"
    )
    if int(summary.get("order_api_called_count", 0)) > 0:
        action_text = "本次已经调用真实报单/撤单 API，请马上核对委托、成交、持仓、资金和执行台账。"
    elif int(summary.get("blocking_failure_count", 0)) > 0:
        action_text = "本次被闸门阻断，没有真实报单；请先看阻断原因，不要手工追单。"
    elif int(summary.get("ready_intent_count", 0)) > 0:
        action_text = "存在待提交意图，但当前邮件显示没有触发真实 API；请确认模式和闸门状态。"
    else:
        action_text = "没有待提交意图，也没有真实报单。"
    blockers_text = ";".join(str(item) for item in summary.get("blockers", [])) or "无"
    if len(blockers_text) > 500:
        blockers_text = blockers_text[:500] + "..."
    body_lines = [
        f"结论：{action_text}",
        f"日期：{summary['target_date']}；模式：{summary['mode']}",
        f"状态：{summary['adapter_status']}",
        f"待提交/报单API/撤单API：{summary['ready_intent_count']}/{summary['send_order_api_called_count']}/{summary['cancel_order_api_called_count']}",
        f"委托/成交回报：{summary['order_row_count']}/{summary['trade_row_count']}",
        f"阻断原因：{blockers_text}",
    ]
    attachments = [
        paths["report_md"],
        paths["summary_json"],
        paths["submitted_csv"],
    ]
    if _env_enabled("OFFICIAL_LIVE_EMAIL_ATTACH_RAW_CTP"):
        attachments.extend([paths["orders_csv"], paths["trades_csv"], paths["logs_csv"]])
    return send_official_live_email_notification(
        subject=subject,
        body="\n".join(body_lines),
        event_type="stage931_submit_adapter",
        severity=severity,
        attachments=attachments,
        metadata={
            "target_date": summary["target_date"],
            "mode": summary["mode"],
            "adapter_status": summary["adapter_status"],
            "ready_intent_count": summary["ready_intent_count"],
            "order_api_called_count": summary["order_api_called_count"],
            "trade_row_count": summary["trade_row_count"],
            "blockers": summary["blockers"],
        },
    )


def _submit_pre_reserved_child(
    *,
    main_engine: Any,
    rows: dict[str, list[dict[str, Any]]],
    req: OrderRequest,
    args: Any,
    config: Any,
    row: dict[str, Any],
    fingerprint: str,
    intent_metadata: dict[str, Any],
    reprice_result: dict[str, Any],
    child_index: int,
    child_count: int,
    send_slot_batch_id: str,
) -> dict[str, Any]:
    """Submit and reconcile one already quota-reserved broker child order."""

    child_id = f"{fingerprint}:{child_index + 1}/{child_count}"
    context = {
        **intent_metadata,
        "target_date": args.target_date,
        "intent_id": row.get("intent_id", ""),
        "intent_fingerprint": fingerprint,
        "parent_intent_fingerprint": fingerprint,
        "vt_symbol": row.get("vt_symbol", ""),
        "adapter": "Stage931",
        "send_slot_reserved": 1,
        "api_slot_batch_id": send_slot_batch_id,
        "child_order_id": child_id,
        "child_order_index": child_index,
        "child_order_count": child_count,
    }
    result: dict[str, Any] = {
        "blockers": [],
        "adapter_status": "",
        "send_called": 0,
        "cancel_called": 0,
        "submitted_row": {},
    }
    pre_send_blockers = _pre_reserved_child_intent_blockers(row, req)
    retry_open = (
        str(row.get("source", "")).strip() == "stage904_c9_intraday_retry_open"
        and str(row.get("offset", "")).strip().lower() == "open"
    )
    if retry_open and not pre_send_blockers:
        pre_send_blockers.extend(
            _stage904_retry_open_pre_send_blockers(
                row,
                target_date=args.target_date,
                max_age_seconds=args.max_stage904_age_seconds,
            )
        )
    if pre_send_blockers:
        result["blockers"] = pre_send_blockers
        result["adapter_status"] = "adapter_blocked_stage904_rebind_before_send"
        result["submitted_row"] = {
            "intent_id": row.get("intent_id", ""),
            "vt_symbol": row.get("vt_symbol", ""),
            "mode": "live-real",
            "submit_status": "stage904_rebind_blocked_before_send_order",
            "intent_fingerprint": fingerprint,
            "final_blockers": ";".join(pre_send_blockers),
            **reprice_result,
        }
        append_execution_ledger_event(
            {
                "event_type": "stage904_rebind_blocked_before_send_order",
                **context,
                "blockers": pre_send_blockers,
            }
        )
        return result
    start_trade_count = len(rows["trades"])
    order_insert_audit_start = len(rows.setdefault("order_insert_requests", []))
    order_insert_audit = _req_order_insert_audit_since(
        rows, order_insert_audit_start
    )
    vt_orderid = ""
    latest: dict[str, Any] = {}
    submit_status = "submitted_to_ctp"
    ledger_fill_price = 0.0
    fill_price_source = "event_trade_missing"
    effective_traded_volume = 0.0
    residual_volume = float(req.volume)
    ledgered_priced_trade_identities: set[str] = set()
    reconciliation_state = _fill_reconciliation_state(
        order_traded_volume=0.0,
        trade_event_volume=0.0,
        requested_volume=float(req.volume),
    )
    try:
        # The atomic batch reservation is durable before this call.  Mark the
        # attempted call before invoking CTP so an exception is never treated
        # as proof that no broker side effect occurred.
        result["send_called"] = 1
        vt_orderid = main_engine.send_order(req, "CTP")
        order_insert_audit = _req_order_insert_audit_since(
            rows, order_insert_audit_start
        )
        context.update(order_insert_audit)
        append_execution_ledger_event(
            {
                "event_type": "send_order_called",
                **context,
                "vt_orderid": vt_orderid,
                "direction": req.direction.value,
                "offset": req.offset.value,
                "volume": req.volume,
                "price": req.price,
            }
        )
        if not vt_orderid:
            blocker = f"converted_child_send_order_returned_empty:{child_id}"
            result["blockers"].append(blocker)
            result["adapter_status"] = "adapter_blocked_converted_child_send_order_returned_empty"
            submit_status = "send_order_returned_empty"
            append_execution_ledger_event(
                {
                    "event_type": "send_order_returned_empty",
                    **context,
                    **_close_retry_terminal_audit_fields(
                        req=req,
                        context=context,
                        insert_audit=order_insert_audit,
                        vt_orderid="",
                        latest_order=None,
                        order_traded_volume=0.0,
                        trade_event_total_volume=0.0,
                        trade_event_priced_volume=0.0,
                        unpriced_volume=0.0,
                        residual_volume=float(req.volume),
                        trade_callback_count=0,
                        send_order_returned_empty=True,
                    ),
                    "direction": req.direction.value,
                    "offset": req.offset.value,
                    "volume": req.volume,
                    "price": req.price,
                }
            )
        else:
            latest = _wait_order_completion(
                rows,
                vt_orderid,
                float(req.volume),
                time.time() + max(1, args.fill_wait_seconds),
            )
            initial_trade_details = _trade_delta_details(rows["trades"], start_trade_count, vt_orderid)
            latest_order_traded = _order_traded_volume(
                latest,
                float(initial_trade_details["total_volume"]),
            )
            if latest_order_traded > float(initial_trade_details["total_volume"]) + 1e-9:
                initial_trade_details = _wait_trade_details(
                    rows["trades"],
                    start_trade_count,
                    vt_orderid,
                    min(float(req.volume), latest_order_traded),
                    time.time() + max(0.0, float(args.trade_detail_wait_seconds)),
                )
            trade_event_total_volume = float(initial_trade_details["total_volume"])
            trade_event_priced_volume = float(initial_trade_details["priced_volume"])
            trade_event_vwap = float(initial_trade_details["vwap"])
            fill_price_source = str(initial_trade_details["fill_price_source"])
            initial_trade_identities = set(initial_trade_details["identities"])
            initial_priced_trade_identities = set(
                initial_trade_details["priced_identities"]
            )
            reconciliation_state = _fill_reconciliation_state(
                order_traded_volume=_order_traded_volume(
                    latest,
                    trade_event_total_volume,
                ),
                trade_event_volume=trade_event_priced_volume,
                trade_event_total_volume=trade_event_total_volume,
                requested_volume=float(req.volume),
            )
            effective_traded_volume = float(reconciliation_state["effective_traded_volume"])
            residual_volume = float(reconciliation_state["residual_volume"])
            ledger_fill_price = trade_event_vwap if trade_event_vwap > 0 else 0.0
            if trade_event_priced_volume > 0:
                append_execution_ledger_event(
                    {
                        "event_type": "filled_or_part_filled",
                        **context,
                        "vt_orderid": vt_orderid,
                        "direction": req.direction.value,
                        "offset": req.offset.value,
                        "volume": req.volume,
                        "price": ledger_fill_price,
                        "order_limit_price": req.price,
                        "fill_price_source": fill_price_source,
                        "trade_rows_delta": len(initial_trade_details["priced_rows"]),
                        "trade_volume_delta": trade_event_priced_volume,
                        "trade_event_priced_volume": trade_event_priced_volume,
                        "trade_event_total_volume": trade_event_total_volume,
                        "unpriced_volume": reconciliation_state["unpriced_volume"],
                        "trade_fill_key": _aggregate_trade_fill_key(
                            vt_orderid,
                            list(initial_priced_trade_identities),
                            "initial",
                        ),
                        "trade_identities": sorted(initial_priced_trade_identities),
                        "first_trade_at": initial_trade_details["first_trade_at"],
                        "residual_volume": residual_volume,
                    }
                )
                ledgered_priced_trade_identities.update(
                    initial_priced_trade_identities
                )
            if reconciliation_state["unpriced_volume"] > 1e-9:
                append_execution_ledger_event(
                    {
                        "event_type": "order_traded_volume_observed_without_trade_detail",
                        **context,
                        "vt_orderid": vt_orderid,
                        "direction": req.direction.value,
                        "offset": req.offset.value,
                        "order_traded_volume": effective_traded_volume,
                        "trade_event_volume": trade_event_priced_volume,
                        "trade_event_priced_volume": trade_event_priced_volume,
                        "trade_event_total_volume": trade_event_total_volume,
                        "unpriced_volume": reconciliation_state["unpriced_volume"],
                    }
                )

            should_cancel_residual = residual_volume > 0 and (
                not latest
                or _status_is_active(latest.get("status"))
                or _status_is_unknown(latest.get("status"))
            )
            if should_cancel_residual:
                cancel_slot = reserve_execution_api_slot(
                    target_date=args.target_date,
                    slot_type="cancel_order",
                    daily_limit=config.hard_limits.max_cancel_count_per_day,
                    base_event={**context, "vt_orderid": vt_orderid},
                )
                if not cancel_slot.get("reserved"):
                    blocker = str(
                        cancel_slot.get("blocker")
                        or "cancel_order_api_slot_reservation_failed"
                    )
                    result["blockers"].append(blocker)
                    result["adapter_status"] = "adapter_blocked_cancel_order_api_slot"
                    submit_status = "cancel_order_api_slot_blocked_before_call"
                    append_execution_ledger_event(
                        {
                            "event_type": "api_slot_reservation_blocked",
                            **context,
                            "api_slot_type": "cancel_order",
                            "api_slot_blocker": blocker,
                            "vt_orderid": vt_orderid,
                            "residual_volume": residual_volume,
                        }
                    )
                else:
                    context["cancel_slot_reserved"] = 1
                    result["cancel_called"] = 1
                    _, _, orderid = vt_orderid.partition(".")
                    main_engine.cancel_order(
                        CancelRequest(orderid=orderid, symbol=req.symbol, exchange=req.exchange),
                        "CTP",
                    )
                    submit_status = (
                        "submitted_partial_or_unknown_cancel_requested"
                        if effective_traded_volume > 0
                        else "submitted_unfilled_cancel_requested"
                    )
                    append_execution_ledger_event(
                        {
                            "event_type": "cancel_order_called",
                            **context,
                            "vt_orderid": vt_orderid,
                            "direction": req.direction.value,
                            "offset": req.offset.value,
                            "traded_volume_before_cancel": effective_traded_volume,
                            "residual_volume_before_cancel": residual_volume,
                        }
                    )
                    time.sleep(max(1, args.post_cancel_wait_seconds))
                    latest_after_cancel = _wait_order_completion(
                        rows,
                        vt_orderid,
                        float(req.volume),
                        time.time() + max(1, args.post_cancel_wait_seconds),
                    )
                    post_details = _trade_delta_details(rows["trades"], start_trade_count, vt_orderid)
                    post_order_traded = _monotonic_order_traded_volume(
                        latest_after_cancel, effective_traded_volume
                    )
                    if post_order_traded > float(post_details["total_volume"]) + 1e-9:
                        post_details = _wait_trade_details(
                            rows["trades"],
                            start_trade_count,
                            vt_orderid,
                            min(float(req.volume), post_order_traded),
                            time.time() + max(0.0, float(args.trade_detail_wait_seconds)),
                        )
                    post_trade_total_volume = float(post_details["total_volume"])
                    post_trade_priced_volume = float(post_details["priced_volume"])
                    post_vwap = float(post_details["vwap"])
                    post_effective = max(post_trade_total_volume, post_order_traded)
                    late_pairs = [
                        (identity, trade_row)
                        for identity, trade_row in zip(post_details["identities"], post_details["rows"])
                        if identity not in initial_trade_identities
                    ]
                    post_priced_identities = set(post_details["priced_identities"])
                    late_priced_pairs = [
                        (identity, trade_row)
                        for identity, trade_row in late_pairs
                        if identity in post_priced_identities
                    ]
                    late_trade_priced_volume, late_trade_vwap = _trade_rows_vwap(
                        [trade_row for _, trade_row in late_priced_pairs]
                    )
                    if late_trade_priced_volume > 0:
                        append_execution_ledger_event(
                            {
                                "event_type": "filled_or_part_filled",
                                **context,
                                "vt_orderid": vt_orderid,
                                "direction": req.direction.value,
                                "offset": req.offset.value,
                                "volume": req.volume,
                                "price": late_trade_vwap if late_trade_vwap > 0 else post_vwap,
                                "order_limit_price": req.price,
                                "fill_price_source": (
                                    "event_trade_weighted_avg"
                                    if late_trade_vwap > 0
                                    else str(post_details["fill_price_source"])
                                ),
                                "trade_rows_delta": len(late_priced_pairs),
                                "trade_volume_delta": late_trade_priced_volume,
                                "trade_event_volume_delta": late_trade_priced_volume,
                                "trade_event_priced_volume_delta": late_trade_priced_volume,
                                "trade_event_total_volume": post_trade_total_volume,
                                "unpriced_volume": max(
                                    0.0,
                                    post_effective - post_trade_priced_volume,
                                ),
                                "trade_fill_key": _aggregate_trade_fill_key(
                                    vt_orderid,
                                    [identity for identity, _ in late_priced_pairs],
                                    "post_cancel",
                                ),
                                "trade_identities": [
                                    identity for identity, _ in late_priced_pairs
                                ],
                                "first_trade_at": _first_trade_at(
                                    [trade_row for _, trade_row in late_priced_pairs]
                                ),
                                "residual_volume": max(0.0, float(req.volume) - post_effective),
                                "late_fill_after_cancel": 1,
                            }
                        )
                        ledgered_priced_trade_identities.update(
                            identity for identity, _ in late_priced_pairs
                        )
                    effective_traded_volume = post_effective
                    residual_volume = max(0.0, float(req.volume) - post_effective)
                    if (
                        post_vwap > 0
                        and post_trade_priced_volume > trade_event_priced_volume
                    ):
                        ledger_fill_price = post_vwap
                        fill_price_source = str(post_details["fill_price_source"])
                    cancel_status_known = bool(
                        latest_after_cancel
                        and str(latest_after_cancel.get("status", "")).strip()
                    )
                    cancel_status_unknown = bool(
                        latest_after_cancel
                        and _status_is_unknown(latest_after_cancel.get("status"))
                    )
                    if residual_volume > 0 and (
                        not cancel_status_known
                        or _status_is_active(latest_after_cancel.get("status"))
                        or cancel_status_unknown
                    ):
                        residual_event_type = (
                            "residual_order_active_after_cancel"
                            if cancel_status_known and not cancel_status_unknown
                            else "residual_order_unknown_after_cancel"
                        )
                        result["blockers"].append(residual_event_type)
                        result["adapter_status"] = f"adapter_blocked_{residual_event_type}"
                        append_execution_ledger_event(
                            {
                                "event_type": residual_event_type,
                                **context,
                                "vt_orderid": vt_orderid,
                                "direction": req.direction.value,
                                "offset": req.offset.value,
                                "latest_order_status": (
                                    latest_after_cancel.get("status", "")
                                    if latest_after_cancel
                                    else ""
                                ),
                                "trade_volume_delta": effective_traded_volume,
                                "residual_volume": residual_volume,
                            }
                        )
                    elif residual_volume > 0 and latest_after_cancel:
                        terminal_audit = _close_retry_terminal_audit_fields(
                            req=req,
                            context=context,
                            insert_audit=order_insert_audit,
                            vt_orderid=vt_orderid,
                            latest_order=latest_after_cancel,
                            order_traded_volume=post_order_traded,
                            trade_event_total_volume=post_trade_total_volume,
                            trade_event_priced_volume=post_trade_priced_volume,
                            unpriced_volume=max(
                                0.0, post_effective - post_trade_priced_volume
                            ),
                            residual_volume=residual_volume,
                            trade_callback_count=len(post_details["identities"]),
                        )
                        append_execution_ledger_event(
                            {
                                "event_type": "rejected_or_inactive",
                                **context,
                                **terminal_audit,
                                "vt_orderid": vt_orderid,
                                "direction": req.direction.value,
                                "offset": req.offset.value,
                                "volume": req.volume,
                                "latest_order_status": latest_after_cancel.get(
                                    "status", ""
                                ),
                            }
                        )
                        if req.offset != Offset.OPEN:
                            blocker = (
                                "protective_close_terminal_zero_fill_retry_cooldown"
                                if _to_int(
                                    terminal_audit.get(
                                        "close_retry_unlock_eligible"
                                    ),
                                    0,
                                )
                                == 1
                                else "protective_close_terminal_without_fill_fail_closed"
                            )
                            _append_unique(result["blockers"], blocker)
                            result["adapter_status"] = f"adapter_blocked_{blocker}"
                    latest = latest_after_cancel or latest
            elif trade_event_priced_volume <= 0:
                if reconciliation_state["pending"]:
                    submit_status = "submitted_fill_reconciliation_pending"
                elif not latest:
                    result["blockers"].append("unknown_order_status_after_send")
                    result["adapter_status"] = "adapter_blocked_unknown_order_status_after_send"
                    submit_status = "submitted_missing_order_callback_fail_closed"
                    append_execution_ledger_event(
                        {
                            "event_type": "unknown_order_status_after_send",
                            **context,
                            "vt_orderid": vt_orderid,
                            "direction": req.direction.value,
                            "offset": req.offset.value,
                            "latest_order_status": "",
                            "order_callback_observed": 0,
                            "trade_volume_delta": effective_traded_volume,
                            "residual_volume": residual_volume,
                        }
                    )
                elif _status_is_unknown(latest.get("status")):
                    result["blockers"].append("unknown_order_status_after_send")
                    result["adapter_status"] = "adapter_blocked_unknown_order_status_after_send"
                    submit_status = "submitted_unknown_order_status_fail_closed"
                    append_execution_ledger_event(
                        {
                            "event_type": "unknown_order_status_after_send",
                            **context,
                            "vt_orderid": vt_orderid,
                            "direction": req.direction.value,
                            "offset": req.offset.value,
                            "latest_order_status": latest.get("status", ""),
                            "trade_volume_delta": effective_traded_volume,
                            "residual_volume": residual_volume,
                        }
                    )
                else:
                    terminal_audit = _close_retry_terminal_audit_fields(
                        req=req,
                        context=context,
                        insert_audit=order_insert_audit,
                        vt_orderid=vt_orderid,
                        latest_order=latest,
                        order_traded_volume=reconciliation_state[
                            "order_traded_volume"
                        ],
                        trade_event_total_volume=reconciliation_state[
                            "trade_event_total_volume"
                        ],
                        trade_event_priced_volume=reconciliation_state[
                            "trade_event_priced_volume"
                        ],
                        unpriced_volume=reconciliation_state["unpriced_volume"],
                        residual_volume=residual_volume,
                        trade_callback_count=len(initial_trade_details["identities"]),
                    )
                    append_execution_ledger_event(
                        {
                            "event_type": "rejected_or_inactive",
                            **context,
                            **terminal_audit,
                            "vt_orderid": vt_orderid,
                            "direction": req.direction.value,
                            "offset": req.offset.value,
                            "volume": req.volume,
                            "latest_order_status": latest.get("status", ""),
                        }
                    )
                    if req.offset != Offset.OPEN:
                        blocker = (
                            "protective_close_terminal_zero_fill_retry_cooldown"
                            if _to_int(
                                terminal_audit.get("close_retry_unlock_eligible"),
                                0,
                            )
                            == 1
                            else "protective_close_terminal_without_fill_fail_closed"
                        )
                        _append_unique(result["blockers"], blocker)
                        result["adapter_status"] = f"adapter_blocked_{blocker}"

            final_details = _trade_delta_details(rows["trades"], start_trade_count, vt_orderid)
            reconciliation_state = _fill_reconciliation_state(
                order_traded_volume=_monotonic_order_traded_volume(latest, effective_traded_volume),
                trade_event_volume=float(final_details["priced_volume"]),
                trade_event_total_volume=float(final_details["total_volume"]),
                requested_volume=float(req.volume),
            )
            effective_traded_volume = float(reconciliation_state["effective_traded_volume"])
            residual_volume = float(reconciliation_state["residual_volume"])
            final_priced_identities = set(final_details["priced_identities"])
            final_unledgered_pairs = [
                (identity, trade_row)
                for identity, trade_row in zip(
                    final_details["identities"],
                    final_details["rows"],
                )
                if identity in final_priced_identities
                and identity not in ledgered_priced_trade_identities
            ]
            final_unledgered_volume, final_unledgered_vwap = _trade_rows_vwap(
                [trade_row for _, trade_row in final_unledgered_pairs]
            )
            if final_unledgered_volume > 0:
                final_unledgered_identities = [
                    identity for identity, _ in final_unledgered_pairs
                ]
                append_execution_ledger_event(
                    {
                        "event_type": "filled_or_part_filled",
                        **context,
                        "vt_orderid": vt_orderid,
                        "direction": req.direction.value,
                        "offset": req.offset.value,
                        "volume": req.volume,
                        "price": final_unledgered_vwap,
                        "order_limit_price": req.price,
                        "fill_price_source": "event_trade_weighted_avg",
                        "trade_rows_delta": len(final_unledgered_pairs),
                        "trade_volume_delta": final_unledgered_volume,
                        "trade_event_volume_delta": final_unledgered_volume,
                        "trade_event_priced_volume_delta": final_unledgered_volume,
                        "trade_event_total_volume": reconciliation_state[
                            "trade_event_total_volume"
                        ],
                        "unpriced_volume": reconciliation_state["unpriced_volume"],
                        "trade_fill_key": _aggregate_trade_fill_key(
                            vt_orderid,
                            final_unledgered_identities,
                            "final_reconciliation",
                        ),
                        "trade_identities": final_unledgered_identities,
                        "first_trade_at": _first_trade_at(
                            [trade_row for _, trade_row in final_unledgered_pairs]
                        ),
                        "residual_volume": residual_volume,
                        "late_fill_at_final_reconciliation": 1,
                    }
                )
                ledgered_priced_trade_identities.update(
                    final_unledgered_identities
                )
                ledger_fill_price = float(final_details["vwap"])
                fill_price_source = str(final_details["fill_price_source"])
            if reconciliation_state["pending"]:
                _append_unique(result["blockers"], str(reconciliation_state["blocker"]))
                result["adapter_status"] = "adapter_blocked_fill_reconciliation_pending"
                submit_status = "submitted_fill_reconciliation_pending"
                append_execution_ledger_event(
                    {
                        "event_type": "fill_reconciliation_pending",
                        **context,
                        "vt_orderid": vt_orderid,
                        "direction": req.direction.value,
                        "offset": req.offset.value,
                        "latest_order_status": latest.get("status", "") if latest else "",
                        "order_traded_volume": reconciliation_state["order_traded_volume"],
                        "trade_event_volume": reconciliation_state["trade_event_volume"],
                        "trade_event_priced_volume": reconciliation_state[
                            "trade_event_priced_volume"
                        ],
                        "trade_event_total_volume": reconciliation_state[
                            "trade_event_total_volume"
                        ],
                        "unpriced_volume": reconciliation_state["unpriced_volume"],
                        "residual_volume": reconciliation_state["residual_volume"],
                    }
                )
            if child_count > 1 and residual_volume > 1e-9 and not result["blockers"]:
                blocker = (
                    f"converted_child_not_fully_filled:{child_id}:"
                    f"filled={effective_traded_volume};request={req.volume}"
                )
                result["blockers"].append(blocker)
                result["adapter_status"] = "adapter_blocked_converted_child_not_fully_filled"
    except Exception as exc:
        order_insert_audit = _req_order_insert_audit_since(
            rows, order_insert_audit_start
        )
        context.update(order_insert_audit)
        result["blockers"].append(f"converted_child_adapter_exception:{child_id}:{exc!r}")
        result["adapter_status"] = "adapter_exception"
        append_execution_ledger_event(
            {
                "event_type": "adapter_exception_after_reserve",
                **context,
                "vt_orderid": vt_orderid,
                "direction": req.direction.value,
                "offset": req.offset.value,
                "exception": repr(exc),
            }
        )

    result["submitted_row"] = {
        "intent_id": row.get("intent_id", ""),
        "vt_symbol": row.get("vt_symbol", ""),
        "mode": "live-real",
        "submit_status": submit_status,
        "intent_fingerprint": fingerprint,
        "parent_intent_fingerprint": fingerprint,
        "child_order_id": child_id,
        "child_order_index": child_index,
        "child_order_count": child_count,
        "vt_orderid": vt_orderid,
        "direction": req.direction.value,
        "offset": req.offset.value,
        "volume": req.volume,
        "price": req.price,
        **reprice_result,
        "trade_volume_delta": effective_traded_volume,
        "trade_event_volume_delta": reconciliation_state["trade_event_volume"],
        "trade_event_priced_volume_delta": reconciliation_state[
            "trade_event_priced_volume"
        ],
        "trade_event_total_volume_delta": reconciliation_state[
            "trade_event_total_volume"
        ],
        "unpriced_volume": reconciliation_state["unpriced_volume"],
        "residual_volume": residual_volume,
        "fill_price": ledger_fill_price,
        "fill_price_volume": reconciliation_state["trade_event_priced_volume"],
        "fill_price_scope": (
            "priced_event_trade_volume_only"
            if reconciliation_state["unpriced_volume"] > 1e-9
            else "all_observed_fill_volume"
        ),
        "fill_price_source": fill_price_source,
        "latest_order_status": latest.get("status", "") if latest else "",
    }
    return result


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Official-live CTP submit adapter, hard-gated by Stage927.")
    parser.add_argument(
        "--command",
        choices=("once", "serve"),
        default="once",
        help=(
            "Run one backward-compatible dry-run cold cycle or the "
            "Stage179 warm executor. Production live submission is serve-only."
        ),
    )
    parser.add_argument("--target-date", default="")
    parser.add_argument(
        "--execution-profile",
        choices=[item.value for item in ExecutionStrategyMode],
        default=ExecutionStrategyMode.C9_15W.value,
    )
    parser.add_argument("--mode", choices=["dry-run", "live-real"], default="dry-run")
    parser.add_argument("--confirm-live-real", default="")
    parser.add_argument(
        "--stage179-warm-executor",
        action="store_true",
        help=(
            "Explicitly opt into the new Stage179 execution generation. "
            "Default keeps the existing legacy Stage931 path unchanged."
        ),
    )
    parser.add_argument(
        "--runtime-profile",
        choices=[item.value for item in ExecutionRuntimeProfile],
        default=ExecutionRuntimeProfile.OFFLINE.value,
    )
    parser.add_argument(
        "--order-scope",
        choices=[item.value for item in OrderScope],
        default=OrderScope.NONE.value,
    )
    parser.add_argument("--stage179-release-manifest", default="")
    parser.add_argument("--stage179-activation-receipt", default="")
    parser.add_argument("--stage179-runtime-root", default="")
    parser.add_argument("--confirm-stage179-activation", default="")
    parser.add_argument("--max-orders", type=int, default=1)
    parser.add_argument(
        "--reduce-close-only",
        action="store_true",
        help="Process only Stage904 risk-reducing close intents; used by the Stage930 fast lane.",
    )
    parser.add_argument(
        "--connect-wait-seconds",
        type=int,
        default=30,
        help="Maximum monotonic deadline for CTP login and explicit account/position readiness queries.",
    )
    parser.add_argument("--fill-wait-seconds", type=int, default=8)
    parser.add_argument(
        "--trade-detail-wait-seconds",
        type=float,
        default=2.0,
        help="Grace period for EVENT_TRADE after an order callback reports newly traded volume.",
    )
    parser.add_argument("--post-cancel-wait-seconds", type=int, default=4)
    parser.add_argument("--max-stage927-age-seconds", type=int, default=180)
    parser.add_argument("--max-stage905-age-seconds", type=int, default=180)
    parser.add_argument("--max-stage904-age-seconds", type=int, default=30)
    parser.add_argument("--max-target-date-age-days", type=int, default=4)
    parser.add_argument("--close-retry-after-cancel-seconds", type=int, default=30)
    parser.add_argument(
        "--final-reprice-tick-wait-seconds",
        type=int,
        default=2,
        help="Post-Q2 EVENT_TICK wait; hard-capped at two seconds before fail-close.",
    )
    parser.add_argument(
        "--final-order-query-wait-seconds",
        type=float,
        default=8.0,
        help=(
            "Bounded total deadline for the final reqid-bound "
            "order-position-order snapshot sandwich, including CTP pacing."
        ),
    )
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "once" and not str(args.target_date).strip():
        parser.error("--target-date is required when --command=once")
    if args.command == "serve" and not args.stage179_warm_executor:
        parser.error("--command=serve requires --stage179-warm-executor")
    if args.command == "once" and args.mode == "live-real":
        parser.error(
            "--command=once does not permit --mode=live-real; "
            "production submission requires --command=serve"
        )
    if args.mode == "live-real" and not args.stage179_warm_executor:
        parser.error("--mode=live-real requires --stage179-warm-executor")
    return args


def _execution_profile_for_args(
    args: argparse.Namespace,
) -> OfficialExecutionProfile:
    """Resolve explicit CLI identity; preserve legacy unit fixtures as C9."""

    return resolve_execution_profile(
        getattr(
            args,
            "execution_profile",
            ExecutionStrategyMode.C9_15W.value,
        )
    )


def run_once(args: argparse.Namespace) -> dict[str, Any]:
    if getattr(args, "mode", "dry-run") == "live-real":
        # Defense in depth for import-level callers that bypass parse_args.
        # Production has one execution protocol surface: warm serve only.
        raise RuntimeProfileError(
            "stage931_once_live_real_disabled_use_command_serve"
        )
    execution_profile = _execution_profile_for_args(args)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    paths = _paths(args.target_date)
    stage905_intents = _stage905_intents(args.target_date)
    ready = _ready_intents_from_frame(stage905_intents)
    unfiltered_ready_count = int(len(ready))
    if args.reduce_close_only and not ready.empty:
        sources = ready.get("source", pd.Series([""] * len(ready))).fillna("").astype(str)
        offsets = ready.get("offset", pd.Series([""] * len(ready))).fillna("").astype(str).str.lower()
        ready = ready[sources.eq("stage904_c9_intraday_close") & offsets.eq("close")].copy()
    stage905 = _read_json(_stage905_summary_path(args.target_date))
    stage904 = _read_json(_stage904_summary_path(args.target_date))
    stage902 = _read_json(_stage902_summary_path(args.target_date))
    stage927 = _read_json(_stage927_summary_path(args.target_date))
    readonly_order_snapshot_age = _file_age_seconds(READONLY_ORDERS_PATH)
    readonly_order_snapshot_diagnostic = _readonly_order_snapshot_diagnostic(
        readonly_order_snapshot_age,
        max_age_seconds=args.max_stage905_age_seconds,
    )
    kill_switch = _read_json(KILL_SWITCH_PATH)
    config = build_phase_d_config()
    ledger_rows = read_execution_ledger()
    ledger_counts = ledger_order_api_counts(ledger_rows, args.target_date)
    target_age_days = _target_age_days(args.target_date)
    current_phase_d_sessions = _current_phase_d_sessions()
    in_execution_session = any(row.get("role") == "market_and_execution" for row in current_phase_d_sessions)
    continuous_submit_blockers = _continuous_submit_blockers()
    ready, ledger_nonretryable_close_ready = _drop_terminal_duplicate_close_intents(
        ready,
        ledger_rows=ledger_rows,
        target_date=args.target_date,
        close_retry_after_cancel_seconds=max(1, args.close_retry_after_cancel_seconds),
        reduce_close_only=bool(args.reduce_close_only),
    )
    terminal_blockers = ledger_nonretryable_close_ready.get(
        "ledger_preselection_blocker", pd.Series([], dtype=str)
    ).fillna("").astype(str)
    terminal_duplicate_ready = ledger_nonretryable_close_ready[
        terminal_blockers.eq(
            "ledger_duplicate_close_intent:filled_or_part_filled"
        )
    ].copy()
    cycle_limit = min(args.max_orders, config.hard_limits.max_order_count_per_cycle)
    ready, deferred_ready, ready_limit_blocker = _bound_ready_intents_for_cycle(
        ready,
        max_orders=cycle_limit,
        reduce_close_only=bool(args.reduce_close_only),
    )
    close_only_reduce_risk = _ready_intents_close_only(ready)
    allow_reduce_close = _to_int(stage902.get("allow_reduce_close"), 0) == 1
    submitted_rows: list[dict[str, Any]] = []
    rows: dict[str, Any] = {
        "orders": [],
        "trades": [],
        "accounts": [],
        "positions": [],
        "ticks": [],
        "logs": [],
        "settlement_callbacks": [],
        "account_query_callbacks": [],
        "max_order_volume_query_callbacks": [],
        "position_query_callbacks": [],
        "order_query_callbacks": [],
        "order_insert_requests": [],
        "position_events_unscoped": [],
    }
    rows["_position_vt_symbol_by_instrument"] = {
        str(vt_symbol).split(".", 1)[0].upper(): str(vt_symbol)
        for vt_symbol in ready.get("vt_symbol", pd.Series([], dtype=str)).fillna("").tolist()
        if str(vt_symbol)
    }

    blockers: list[str] = []
    if args.mode == "live-real" and not args.stage179_warm_executor:
        blockers.append("live_real_requires_stage179_warm_executor")
    blockers.extend(
        _stage905_execution_profile_blockers(
            execution_profile,
            stage905_intents,
        )
    )
    if _artifact_text(stage905.get("execution_profile")) != execution_profile.profile_key:
        blockers.append("stage905_summary_execution_profile_mismatch")
    if _artifact_text(stage905.get("official_live_version")) != execution_profile.official_version:
        blockers.append("stage905_summary_official_version_mismatch")
    if abs(
        _to_float(stage905.get("capital"), -1.0)
        - execution_profile.capital
    ) > 1e-9:
        blockers.append("stage905_summary_capital_mismatch")
    if _artifact_text(stage905.get("capital_label")) != execution_profile.capital_label:
        blockers.append("stage905_summary_capital_label_mismatch")
    if ready.empty:
        blockers.append("no_ready_stage905_intents")
    if ready_limit_blocker:
        blockers.append(ready_limit_blocker)
    blockers.extend(
        _ledger_daily_slot_blockers(
            ledger_counts,
            max_send_orders=config.hard_limits.max_order_count_per_day,
            max_cancel_orders=config.hard_limits.max_cancel_count_per_day,
        )
    )
    if bool(kill_switch.get("enabled", False) or kill_switch.get("kill_switch_active", False)):
        blockers.append("kill_switch_active")
    if args.mode == "live-real":
        blockers.extend(
            _stage905_cycle_artifact_blockers(
                stage905_intents,
                ready,
                reduce_close_only=bool(args.reduce_close_only),
            )
        )
        if stage927.get("real_submit_permitted") != 1 and not close_only_reduce_risk:
            blockers.append("stage927_real_submit_not_permitted")
        if close_only_reduce_risk and not allow_reduce_close:
            blockers.append("stage902_reduce_close_not_allowed_for_close_only")
        stage927_age = _age_seconds(stage927.get("generated_at"))
        if (stage927_age is None or stage927_age > args.max_stage927_age_seconds) and not close_only_reduce_risk:
            blockers.append(f"stage927_summary_stale_or_missing:{stage927_age}")
        blockers.extend(
            _stage905_snapshot_blockers(
                stage905,
                stage905_intents,
                target_date=args.target_date,
                max_age_seconds=args.max_stage905_age_seconds,
                reduce_close_only=bool(args.reduce_close_only and close_only_reduce_risk),
            )
        )
        blockers.extend(
            _stage904_retry_open_snapshot_blockers(
                stage904,
                ready,
                target_date=args.target_date,
                max_age_seconds=args.max_stage904_age_seconds,
            )
        )
        # Stage174 order files remain useful telemetry, but cannot be a live
        # authority: they may be stale exactly when a risk-reducing close is
        # needed.  The same-session final O-P-O epoch below is the send gate.
        if not in_execution_session:
            blockers.append("live_real_not_in_execution_session")
        blockers.extend(continuous_submit_blockers)
        if target_age_days is None or target_age_days < 0 or target_age_days > args.max_target_date_age_days:
            blockers.append(f"live_real_target_date_stale_or_invalid:{target_age_days}")
        if not _env_enabled(PHASE_D_REAL_ADAPTER_ENV):
            blockers.append("real_adapter_env_missing")
        if not _env_enabled(PHASE_D_REAL_ENABLED_ENV):
            blockers.append("real_submit_env_missing")
        if args.confirm_live_real != PHASE_D_CONFIRM_TEXT:
            blockers.append("confirm_live_real_missing")
        missing = _missing_env()
        if missing:
            blockers.append("missing_ctp_env:" + ",".join(missing))

    stage179_gate_summary: dict[str, Any] = {
        "opted_in": int(bool(args.stage179_warm_executor)),
        "evaluated": 0,
        "runtime_profile": args.runtime_profile,
        "order_scope": args.order_scope,
        "manifest_sha256": "",
        "blockers": [],
        "adapter_created": 0,
    }
    if args.stage179_warm_executor:
        try:
            if args.mode == "live-real" and (
                args.runtime_profile != ExecutionRuntimeProfile.PRODUCTION_LIVE.value
                or args.order_scope != OrderScope.LIVE.value
            ):
                raise RuntimeProfileError(
                    "live_real_requires_production_live_profile_and_scope"
                )
            resolved_runtime = resolve_runtime_profile(
                profile=args.runtime_profile,
                order_scope=args.order_scope,
                repo_root=Path(__file__).resolve().parents[2],
            )
            gate_stage927_age = _age_seconds(stage927.get("generated_at"))
            stage179_gate = evaluate_stage179_pre_adapter_gate(
                resolved=resolved_runtime,
                release_manifest_path=args.stage179_release_manifest,
                repo_root=resolved_runtime.repo_root,
                expected_official_version=execution_profile.official_version,
                expected_capital=execution_profile.capital,
                expected_capital_label=execution_profile.capital_label,
                expected_execution_profile=execution_profile.profile_key,
                environment=os.environ,
                confirmation=args.confirm_stage179_activation,
                activation_receipt_path=(
                    args.stage179_activation_receipt or None
                ),
                phase_d_real_submit_ready=bool(
                    _env_enabled(PHASE_D_REAL_ADAPTER_ENV)
                    and _env_enabled(PHASE_D_REAL_ENABLED_ENV)
                    and args.confirm_live_real == PHASE_D_CONFIRM_TEXT
                    and not _missing_env()
                ),
                stage927_ready=bool(
                    stage927.get("real_submit_permitted") == 1
                    and gate_stage927_age is not None
                    and gate_stage927_age <= args.max_stage927_age_seconds
                ),
                kill_switch_clear=not bool(
                    kill_switch.get("enabled", False)
                    or kill_switch.get("kill_switch_active", False)
                ),
                broker_gates_fresh=not blockers,
            )
            stage179_gate_summary = {
                "opted_in": 1,
                "evaluated": 1,
                "runtime_profile": resolved_runtime.profile.value,
                "order_scope": resolved_runtime.order_scope.value,
                "manifest_sha256": stage179_gate.manifest_sha256,
                "blockers": list(stage179_gate.blockers),
                "adapter_created": int(stage179_gate.adapter_created),
            }
            blockers.extend(stage179_gate.blockers)
        except (RuntimeProfileError, OSError, ValueError) as exc:
            blocker = f"stage179_runtime_profile_invalid:{exc}"
            stage179_gate_summary["evaluated"] = 1
            stage179_gate_summary["blockers"] = [blocker]
            blockers.append(blocker)

    ledger_intent_rows: list[dict[str, Any]] = []
    for row in ready.to_dict(orient="records"):
        try:
            payload = json.loads(str(row.get("order_request_json", "{}")))
        except json.JSONDecodeError as exc:
            blockers.append(f"invalid_order_request_json:{row.get('intent_id', '')}:{exc}")
            continue
        try:
            duplicate, fingerprint, fingerprint_payload, latest = duplicate_blocker(
                rows=ledger_rows,
                target_date=args.target_date,
                row=row,
                order_request=payload,
                close_retry_after_cancel_seconds=max(1, args.close_retry_after_cancel_seconds),
            )
        except ValueError as exc:
            blockers.append(f"invalid_intent_identity:{row.get('intent_id', '')}:{exc}")
            continue
        if duplicate:
            blockers.append(duplicate)
        ledger_intent_rows.append(
            {
                "intent_id": row.get("intent_id", ""),
                "intent_fingerprint": fingerprint,
                "intent_fingerprint_payload": fingerprint_payload,
                "latest_ledger_event": latest or {},
                "ledger_duplicate_blocker": duplicate,
            }
        )

    send_count = 0
    cancel_count = 0
    adapter_status = "adapter_dry_run_ready" if not blockers else "adapter_blocked"
    ledger_by_intent = {str(row["intent_id"]): row for row in ledger_intent_rows}
    stage927_age = _age_seconds(stage927.get("generated_at"))
    stage905_age = _age_seconds(stage905.get("generated_at"))
    connection_flags: dict[str, Any] = {}
    readiness_state_summary: dict[str, Any] = {}
    final_snapshot_summaries: list[dict[str, Any]] = []
    active_reserved_context: dict[str, Any] | None = None
    if args.mode == "dry-run":
        for row in ready.head(args.max_orders).to_dict(orient="records"):
            ledger_row = ledger_by_intent.get(str(row.get("intent_id", "")), {})
            submitted_rows.append(
                {
                    "intent_id": row.get("intent_id", ""),
                    "vt_symbol": row.get("vt_symbol", ""),
                    "mode": "dry-run",
                    "submit_status": "dry_run_not_submitted",
                    "intent_fingerprint": ledger_row.get("intent_fingerprint", ""),
                    "ledger_duplicate_blocker": ledger_row.get("ledger_duplicate_blocker", ""),
                    "order_request_json": row.get("order_request_json", ""),
                }
            )
    elif not blockers:
        main_engine: MainEngine | None = None
        callback_context: Any = None
        callback_instrumented = False
        ctp_td_api: Any = None
        readiness_state: CtpReadinessState | None = None
        try:
            from vnpy_ctp import CtpGateway
            from vnpy_ctp.gateway import ctp_gateway as ctp_gateway_module

            callback_context = _instrument_ctp_readiness_callbacks(ctp_gateway_module.CtpTdApi, rows)
            callback_context.__enter__()
            callback_instrumented = True

            event_engine = EventEngine()
            main_engine = MainEngine(event_engine)
            ctp_gateway = main_engine.add_gateway(CtpGateway)
            ctp_td_api = ctp_gateway.td_api
            original_gateway_on_tick = ctp_gateway.on_tick
            original_gateway_on_order = ctp_gateway.on_order
            original_gateway_on_trade = ctp_gateway.on_trade
            original_gateway_on_position = ctp_gateway.on_position
            event_ingress_lock = Lock()
            event_ingress_counts = {
                "order": 0,
                "trade": 0,
                "position": 0,
            }
            rows["_execution_event_ingress_counts"] = event_ingress_counts

            def mark_execution_event_ingress(event_name: str) -> None:
                with event_ingress_lock:
                    event_ingress_counts[event_name] += 1

            def on_gateway_tick_before_enqueue(tick: Any) -> Any:
                _stamp_tick_before_event_enqueue(tick)
                return original_gateway_on_tick(tick)

            def on_gateway_order_before_enqueue(order: Any) -> Any:
                if not int(
                    getattr(_ORDER_QUERY_FORWARD_CONTEXT, "depth", 0)
                ):
                    mark_execution_event_ingress("order")
                return original_gateway_on_order(order)

            def on_gateway_trade_before_enqueue(trade: Any) -> Any:
                mark_execution_event_ingress("trade")
                return original_gateway_on_trade(trade)

            def on_gateway_position_before_enqueue(position: Any) -> Any:
                mark_execution_event_ingress("position")
                return original_gateway_on_position(position)

            # CtpMdApi calls this gateway method before BaseGateway publishes
            # EVENT_TICK, so the causal timestamp cannot be inflated by an
            # EventEngine backlog.
            ctp_gateway.on_tick = on_gateway_tick_before_enqueue
            ctp_gateway.on_order = on_gateway_order_before_enqueue
            ctp_gateway.on_trade = on_gateway_trade_before_enqueue
            ctp_gateway.on_position = on_gateway_position_before_enqueue

            def on_order(event: Any) -> None:
                rows["orders"].append(_object_to_row(event.data))

            def on_trade(event: Any) -> None:
                rows["trades"].append(_object_to_row(event.data))

            def on_account(event: Any) -> None:
                rows["accounts"].append(_object_to_row(event.data))

            def on_position(event: Any) -> None:
                # EVENT_POSITION is intentionally diagnostic only: vn.py does
                # not carry the CTP reqid on this async event, so queued rows
                # from an automatic/older query cannot prove the active final
                # position gate.  ``rows['positions']`` is published directly
                # from the reqid-bound raw callback epoch above.
                rows["position_events_unscoped"].append(_object_to_row(event.data))

            def on_tick(event: Any) -> None:
                rows["ticks"].append(_tick_event_row(event.data))

            def on_log(event: Any) -> None:
                rows["logs"].append(_object_to_row(event.data))

            event_engine.register(EVENT_ORDER, on_order)
            event_engine.register(EVENT_TRADE, on_trade)
            event_engine.register(EVENT_ACCOUNT, on_account)
            event_engine.register(EVENT_POSITION, on_position)
            event_engine.register(EVENT_TICK, on_tick)
            event_engine.register(EVENT_LOG, on_log)
            _connect_ctp_without_timer_queries(main_engine, ctp_gateway, event_engine)
            connection_ready, connection_flags, connection_blockers, readiness_state = _wait_for_ctp_readiness(
                ctp_td_api,
                rows,
                account_required=not close_only_reduce_risk,
                max_wait_seconds=max(0, args.connect_wait_seconds),
            )
            readiness_state_summary = readiness_state.to_summary()
            if not connection_ready:
                blockers.extend(connection_blockers)
                adapter_status = "adapter_blocked_ctp_connection_not_ready"
            else:
                rows["logs"].append(
                    {
                        "received_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "level": "INFO",
                        "msg": f"Stage931 CTP final connection gate passed: {json.dumps(connection_flags, ensure_ascii=False, default=str)}",
                    }
                )
            for row in ready.head(args.max_orders).to_dict(orient="records"):
                if not connection_ready:
                    break
                payload = json.loads(str(row.get("order_request_json", "{}")))
                req = _order_request_from_payload(payload)
                intent_metadata = _intent_ledger_metadata(row)
                reserve_result = reserve_execution_ledger_intent(
                    target_date=args.target_date,
                    row=row,
                    order_request=payload,
                    close_retry_after_cancel_seconds=max(1, args.close_retry_after_cancel_seconds),
                    base_event={
                        "intent_id": row.get("intent_id", ""),
                        "vt_symbol": row.get("vt_symbol", ""),
                        "mode": "live-real",
                        "adapter": "Stage931",
                        **intent_metadata,
                    },
                )
                fingerprint = str(reserve_result.get("intent_fingerprint", ""))
                if not reserve_result.get("reserved"):
                    blocker = str(reserve_result.get("duplicate_blocker", "ledger_duplicate_intent_after_atomic_reserve"))
                    blockers.append(blocker)
                    adapter_status = "adapter_blocked_ledger_duplicate_after_atomic_reserve"
                    submitted_rows.append(
                        {
                            "intent_id": row.get("intent_id", ""),
                            "vt_symbol": row.get("vt_symbol", ""),
                            "mode": "live-real",
                            "submit_status": "ledger_duplicate_blocked_after_atomic_reserve",
                            "intent_fingerprint": fingerprint,
                            "ledger_duplicate_blocker": blocker,
                            "order_request_json": row.get("order_request_json", ""),
                        }
                    )
                    break
                close_submit_attempt_no = _to_int(
                    reserve_result.get("close_submit_attempt_no"), 0
                )
                close_attempt_lease_token = str(
                    reserve_result.get("close_attempt_lease_token", "") or ""
                ).strip()
                if req.offset != Offset.OPEN:
                    if close_submit_attempt_no not in {1, 2}:
                        blocker = "close_submit_attempt_missing_after_reserve"
                        blockers.append(blocker)
                        adapter_status = "adapter_blocked_close_submit_attempt_missing"
                        submitted_rows.append(
                            {
                                "intent_id": row.get("intent_id", ""),
                                "vt_symbol": row.get("vt_symbol", ""),
                                "mode": "live-real",
                                "submit_status": "close_submit_attempt_missing_after_reserve",
                                "intent_fingerprint": fingerprint,
                            }
                        )
                        break
                    intent_metadata = {
                        **intent_metadata,
                        "close_submit_attempt_no": close_submit_attempt_no,
                    }
                    if not close_attempt_lease_token:
                        blocker = "close_attempt_lease_token_missing_after_reserve"
                        blockers.append(blocker)
                        adapter_status = "adapter_blocked_close_attempt_lease_token_missing"
                        submitted_rows.append(
                            {
                                "intent_id": row.get("intent_id", ""),
                                "vt_symbol": row.get("vt_symbol", ""),
                                "mode": "live-real",
                                "submit_status": "close_attempt_lease_token_missing_after_reserve",
                                "intent_fingerprint": fingerprint,
                            }
                        )
                        break
                    intent_metadata["close_attempt_lease_token"] = (
                        close_attempt_lease_token
                    )
                active_reserved_context = {
                    "target_date": args.target_date,
                    "intent_id": row.get("intent_id", ""),
                    "intent_fingerprint": fingerprint,
                    "vt_symbol": row.get("vt_symbol", ""),
                    "adapter": "Stage931",
                    **intent_metadata,
                }
                pre_snapshot_reprice_result = _final_close_reprice(
                    main_engine,
                    rows,
                    row,
                    req,
                    max_tick_age_seconds=int(config.hard_limits.max_tick_age_seconds),
                    tick_wait_seconds=max(0, args.final_reprice_tick_wait_seconds),
                )
                if pre_snapshot_reprice_result.get("final_reprice_status") != "skipped_not_stage904_intraday_close":
                    append_execution_ledger_event(
                        {
                            "event_type": "pre_snapshot_close_reprice_observation",
                            **active_reserved_context,
                            "post_sandwich_reprice": 0,
                            **pre_snapshot_reprice_result,
                        }
                    )
                reprice_result = {
                    **pre_snapshot_reprice_result,
                    "post_sandwich_reprice": 0,
                    "post_sandwich_reprice_skip_reason": (
                        "final_snapshot_or_transport_gate_not_passed"
                    ),
                }
                # The pre-snapshot quote is diagnostic/warm-up only.  The
                # actual send gate revalidates reclaim and price immediately
                # after Q2, so this earlier observation cannot authorize or
                # permanently veto a later send by itself.
                final_blockers: list[str] = []
                final_snapshot: dict[str, Any] = {
                    "success": False,
                    "confirmed": False,
                    "stable": False,
                    "blockers": ["final_snapshot_ctp_state_missing"],
                    "order_q1": {},
                    "position": {},
                    "order_q2": {},
                    "orders": [],
                    "active_orders": [],
                    "elapsed_seconds": 0.0,
                }
                if ctp_td_api is not None and readiness_state is not None:
                    final_snapshot = _final_pre_send_snapshot_epoch(
                        ctp_td_api,
                        rows,
                        max_wait_seconds=max(
                            0.0,
                            float(args.final_order_query_wait_seconds),
                        ),
                        readiness_state=readiness_state,
                    )
                    readiness_state_summary = readiness_state.to_summary()
                q1_audit = dict(final_snapshot.get("order_q1", {}))
                position_audit = dict(final_snapshot.get("position", {}))
                q2_audit = dict(final_snapshot.get("order_q2", {}))
                final_snapshot_audit = {
                    "intent_id": row.get("intent_id", ""),
                    "success": int(bool(final_snapshot.get("success"))),
                    "confirmed": int(bool(final_snapshot.get("confirmed"))),
                    "stable": int(bool(final_snapshot.get("stable"))),
                    "order_q1_reqid": q1_audit.get("reqid"),
                    "position_reqid": position_audit.get("reqid"),
                    "order_q2_reqid": q2_audit.get("reqid"),
                    "order_q1_request_ret": q1_audit.get("request_ret", ""),
                    "position_request_ret": position_audit.get("request_ret", ""),
                    "order_q2_request_ret": q2_audit.get("request_ret", ""),
                    "order_q1_count": len(q1_audit.get("orders", [])),
                    "position_count": len(position_audit.get("positions", [])),
                    "order_q2_count": len(q2_audit.get("orders", [])),
                    "order_q1_callback_count": int(
                        q1_audit.get("callback_count", 0)
                    ),
                    "position_callback_count": int(
                        position_audit.get("callback_count", 0)
                    ),
                    "order_q2_callback_count": int(
                        q2_audit.get("callback_count", 0)
                    ),
                    "order_q1_ignored_callback_count": int(
                        q1_audit.get("ignored_callback_count", 0)
                    ),
                    "position_ignored_callback_count": int(
                        position_audit.get("ignored_callback_count", 0)
                    ),
                    "order_q2_ignored_callback_count": int(
                        q2_audit.get("ignored_callback_count", 0)
                    ),
                    "order_q1_canonical": list(
                        final_snapshot.get("canonical_q1", [])
                    ),
                    "order_q2_canonical": list(
                        final_snapshot.get("canonical_q2", [])
                    ),
                    "final_position_rows": list(
                        final_snapshot.get("positions", [])
                    ),
                    "active_order_count": len(
                        final_snapshot.get("active_orders", [])
                    ),
                    "active_order_identities": [
                        str(order.get("order_identity", ""))
                        for order in final_snapshot.get("active_orders", [])
                    ],
                    "q2_completed_monotonic": final_snapshot.get(
                        "q2_completed_monotonic"
                    ),
                    "blockers": list(final_snapshot.get("blockers", [])),
                    "elapsed_seconds": final_snapshot.get(
                        "elapsed_seconds",
                        0.0,
                    ),
                }
                final_snapshot_summaries.append(final_snapshot_audit)
                append_execution_ledger_event(
                    {
                        "event_type": "final_order_position_order_snapshot_before_send",
                        **active_reserved_context,
                        **final_snapshot_audit,
                    }
                )
                final_blockers.extend(final_snapshot.get("blockers", []))
                final_blockers.extend(_final_pre_send_blockers(
                    rows,
                    req,
                    str(row.get("vt_symbol", "")),
                    authoritative_active_orders=list(
                        final_snapshot.get("active_orders", [])
                    ),
                    order_query_confirmed=bool(
                        final_snapshot.get("confirmed")
                    ),
                ))
                if ctp_td_api is None or readiness_state is None:
                    final_blockers.append("final_ctp_readiness_state_missing")
                else:
                    final_blockers.extend(_final_ctp_transport_blockers(ctp_td_api, rows, readiness_state))
                final_blockers = list(dict.fromkeys(final_blockers))
                if not final_blockers:
                    reprice_result = _post_snapshot_final_reprice(
                        main_engine,
                        rows,
                        row,
                        req,
                        max_tick_age_seconds=int(
                            config.hard_limits.max_tick_age_seconds
                        ),
                        q2_completed_monotonic=final_snapshot.get(
                            "q2_completed_monotonic"
                        ),
                        tick_wait_seconds=min(
                            2,
                            max(0, args.final_reprice_tick_wait_seconds),
                        ),
                    )
                    if reprice_result.get("final_reprice_status") != "skipped_not_stage904_intraday_close":
                        append_execution_ledger_event(
                            {
                                "event_type": "final_close_reprice_after_order_position_order_snapshot",
                                **active_reserved_context,
                                **reprice_result,
                            }
                        )
                    final_blockers.extend(
                        _final_reprice_blockers(reprice_result)
                    )
                    final_blockers = list(dict.fromkeys(final_blockers))
                post_reprice_final_gate: dict[str, Any] = {}
                if (
                    not final_blockers
                    and ctp_td_api is not None
                    and readiness_state is not None
                ):
                    post_reprice_final_gate = _post_reprice_final_state_gate(
                        main_engine,
                        ctp_td_api,
                        rows,
                        row,
                        req,
                        initial_snapshot=final_snapshot,
                        initial_reprice_result=reprice_result,
                        max_tick_age_seconds=int(
                            config.hard_limits.max_tick_age_seconds
                        ),
                        max_wait_seconds=max(
                            0.0,
                            float(args.final_order_query_wait_seconds),
                        ),
                        readiness_state=readiness_state,
                    )
                    readiness_state_summary = readiness_state.to_summary()
                    reprice_result = dict(
                        post_reprice_final_gate.get(
                            "final_reprice_result", reprice_result
                        )
                    )
                    final_blockers.extend(
                        post_reprice_final_gate.get("blockers", [])
                    )
                    final_blockers = list(dict.fromkeys(final_blockers))
                    second_snapshot = dict(
                        post_reprice_final_gate.get("snapshot", {})
                    )
                    append_execution_ledger_event(
                        {
                            "event_type": "post_reprice_final_state_gate_before_send",
                            **active_reserved_context,
                            "success": int(
                                bool(post_reprice_final_gate.get("success"))
                            ),
                            "blockers": list(
                                post_reprice_final_gate.get("blockers", [])
                            ),
                            "q2_before_event_watermark": dict(
                                post_reprice_final_gate.get(
                                    "q2_before_event_watermark", {}
                                )
                            ),
                            "initial_event_watermark": dict(
                                post_reprice_final_gate.get(
                                    "initial_event_watermark", {}
                                )
                            ),
                            "before_second_snapshot_event_watermark": dict(
                                post_reprice_final_gate.get(
                                    "before_second_snapshot_event_watermark", {}
                                )
                            ),
                            "second_q2_before_event_watermark": dict(
                                post_reprice_final_gate.get(
                                    "second_q2_before_event_watermark", {}
                                )
                            ),
                            "second_q2_after_event_watermark": dict(
                                post_reprice_final_gate.get(
                                    "second_q2_after_event_watermark", {}
                                )
                            ),
                            "after_second_snapshot_event_watermark": dict(
                                post_reprice_final_gate.get(
                                    "after_second_snapshot_event_watermark", {}
                                )
                            ),
                            "final_event_watermark": dict(
                                post_reprice_final_gate.get(
                                    "final_event_watermark", {}
                                )
                            ),
                            "position_event_watermark_changed": int(
                                post_reprice_final_gate.get(
                                    "position_event_watermark_changed", 0
                                )
                            ),
                            "initial_canonical_positions": list(
                                post_reprice_final_gate.get(
                                    "initial_canonical_positions", []
                                )
                            ),
                            "final_canonical_positions": list(
                                post_reprice_final_gate.get(
                                    "final_canonical_positions", []
                                )
                            ),
                            "second_order_q1_reqid": dict(
                                second_snapshot.get("order_q1", {})
                            ).get("reqid"),
                            "second_position_reqid": dict(
                                second_snapshot.get("position", {})
                            ).get("reqid"),
                            "second_order_q2_reqid": dict(
                                second_snapshot.get("order_q2", {})
                            ).get("reqid"),
                            "second_q2_completed_monotonic": (
                                second_snapshot.get("q2_completed_monotonic")
                            ),
                            **reprice_result,
                        }
                    )
                if final_blockers:
                    blockers.extend(final_blockers)
                    adapter_status = "adapter_blocked_final_pre_send_gate"
                    append_execution_ledger_event(
                        {
                            "event_type": "final_pre_send_gate_blocked_after_reserve",
                            **active_reserved_context,
                            "final_blockers": final_blockers,
                        }
                    )
                    submitted_rows.append(
                        {
                            "intent_id": row.get("intent_id", ""),
                            "vt_symbol": row.get("vt_symbol", ""),
                            "mode": "live-real",
                            "submit_status": "final_pre_send_gate_blocked_after_reserve",
                            "intent_fingerprint": fingerprint,
                            "final_blockers": ";".join(final_blockers),
                            **reprice_result,
                            "order_request_json": row.get("order_request_json", ""),
                        }
                    )
                    active_reserved_context = None
                    break
                conversion = _final_offset_conversion(main_engine, rows, req)
                conversion_blockers = list(conversion.get("blockers", []))
                final_requests = list(conversion.get("requests", []))
                conversion_diagnostics = dict(conversion.get("diagnostics", {}))
                if conversion_blockers:
                    blockers.extend(conversion_blockers)
                    adapter_status = "adapter_blocked_final_offset_conversion"
                    append_execution_ledger_event(
                        {
                            "event_type": "final_pre_send_gate_blocked_after_reserve",
                            **active_reserved_context,
                            "final_blockers": conversion_blockers,
                            "offset_conversion_diagnostics": conversion_diagnostics,
                        }
                    )
                    submitted_rows.append(
                        {
                            "intent_id": row.get("intent_id", ""),
                            "vt_symbol": row.get("vt_symbol", ""),
                            "mode": "live-real",
                            "submit_status": "final_offset_conversion_blocked_before_send",
                            "intent_fingerprint": fingerprint,
                            "final_blockers": ";".join(conversion_blockers),
                            **reprice_result,
                        }
                    )
                    active_reserved_context = None
                    break

                blocker = _converted_child_cycle_blocker(
                    child_count=len(final_requests),
                    max_physical_orders=config.hard_limits.max_order_count_per_cycle,
                    send_count=send_count,
                )
                if blocker:
                    blockers.append(blocker)
                    adapter_status = "adapter_blocked_converted_child_cycle_limit"
                    append_execution_ledger_event(
                        {
                            "event_type": "final_pre_send_gate_blocked_after_reserve",
                            **active_reserved_context,
                            "final_blockers": [blocker],
                            "offset_conversion_diagnostics": conversion_diagnostics,
                        }
                    )
                    submitted_rows.append(
                        {
                            "intent_id": row.get("intent_id", ""),
                            "vt_symbol": row.get("vt_symbol", ""),
                            "mode": "live-real",
                            "submit_status": "converted_child_cycle_limit_blocked_before_send",
                            "intent_fingerprint": fingerprint,
                            "final_blockers": blocker,
                            **reprice_result,
                        }
                    )
                    active_reserved_context = None
                    break

                if ctp_td_api is None:
                    open_funds_gate = {
                        "success": False,
                        "confirmed": False,
                        "status": "blocked",
                        "blockers": [
                            "final_open_funds_ctp_state_missing"
                        ],
                        "query_api_called_count": 0,
                    }
                else:
                    open_funds_gate = _final_open_funds_margin_gate(
                        ctp_td_api,
                        rows,
                        final_requests,
                        max_wait_seconds=max(
                            0.0,
                            float(args.final_order_query_wait_seconds),
                        ),
                        readiness_state=readiness_state,
                    )
                post_reprice_final_gate["open_funds_gate"] = dict(
                    open_funds_gate
                )
                post_reprice_final_gate[
                    "final_event_watermark_after_open_funds"
                ] = dict(open_funds_gate.get("event_watermark", {}))
                append_execution_ledger_event(
                    {
                        "event_type": "final_open_funds_margin_gate_before_send",
                        **active_reserved_context,
                        "open_funds_gate": open_funds_gate,
                        "funds_query_api_called_count": _to_int(
                            open_funds_gate.get("query_api_called_count"), 0
                        ),
                    }
                )
                open_funds_blockers = list(
                    open_funds_gate.get("blockers", [])
                )
                if open_funds_blockers:
                    blockers.extend(open_funds_blockers)
                    adapter_status = "adapter_blocked_final_open_funds_gate"
                    append_execution_ledger_event(
                        {
                            "event_type": "final_pre_send_gate_blocked_after_reserve",
                            **active_reserved_context,
                            "final_blockers": open_funds_blockers,
                            "open_funds_gate": open_funds_gate,
                        }
                    )
                    submitted_rows.append(
                        {
                            "intent_id": row.get("intent_id", ""),
                            "vt_symbol": row.get("vt_symbol", ""),
                            "mode": "live-real",
                            "submit_status": "final_open_funds_gate_blocked_before_send",
                            "intent_fingerprint": fingerprint,
                            "final_blockers": ";".join(open_funds_blockers),
                            **reprice_result,
                        }
                    )
                    active_reserved_context = None
                    break

                append_execution_ledger_event(
                    {
                        "event_type": "final_offset_conversion_before_send",
                        **active_reserved_context,
                        "offset_conversion_applied": int(bool(conversion.get("converted"))),
                        "offset_conversion_diagnostics": conversion_diagnostics,
                        "child_order_count": len(final_requests),
                        "child_order_offsets": [child.offset.value for child in final_requests],
                        "child_order_volumes": [float(child.volume) for child in final_requests],
                    }
                )
                pre_api_slot_blockers = _post_final_gate_pre_api_slot_blockers(
                    rows,
                    dict(
                        post_reprice_final_gate.get(
                            "final_event_watermark_after_open_funds",
                            post_reprice_final_gate.get(
                                "final_event_watermark", {}
                            ),
                        )
                    ),
                )
                pre_api_slot_blockers.extend(
                    _open_funds_gate_consistency_blockers(
                        ctp_td_api,
                        rows,
                        final_requests,
                        open_funds_gate,
                    )
                )
                if ctp_td_api is None or readiness_state is None:
                    pre_api_slot_blockers.append(
                        "post_final_gate_ctp_state_missing_before_api_slot"
                    )
                else:
                    pre_api_slot_blockers.extend(
                        _final_ctp_transport_blockers(
                            ctp_td_api, rows, readiness_state
                        )
                    )
                pre_api_slot_blockers = list(
                    dict.fromkeys(pre_api_slot_blockers)
                )
                if pre_api_slot_blockers:
                    blockers.extend(pre_api_slot_blockers)
                    adapter_status = (
                        "adapter_blocked_post_final_gate_before_api_slot"
                    )
                    append_execution_ledger_event(
                        {
                            "event_type": "post_final_gate_blocked_before_api_slot",
                            **active_reserved_context,
                            "final_blockers": pre_api_slot_blockers,
                            "final_gate_event_watermark": dict(
                                post_reprice_final_gate.get(
                                    "final_event_watermark", {}
                                )
                            ),
                            "pre_api_slot_event_watermark": (
                                _execution_event_watermark(rows)
                            ),
                        }
                    )
                    submitted_rows.append(
                        {
                            "intent_id": row.get("intent_id", ""),
                            "vt_symbol": row.get("vt_symbol", ""),
                            "mode": "live-real",
                            "submit_status": (
                                "post_final_gate_blocked_before_api_slot"
                            ),
                            "intent_fingerprint": fingerprint,
                            "final_blockers": ";".join(
                                pre_api_slot_blockers
                            ),
                            **reprice_result,
                        }
                    )
                    active_reserved_context = None
                    break
                send_slot_events = [
                    {
                        **active_reserved_context,
                        "parent_intent_fingerprint": fingerprint,
                        "child_order_id": f"{fingerprint}:{index + 1}/{len(final_requests)}",
                        "child_order_index": index,
                        "child_order_count": len(final_requests),
                        "child_order_offset": child.offset.value,
                        "child_order_volume": float(child.volume),
                    }
                    for index, child in enumerate(final_requests)
                ]
                send_slot_batch = reserve_execution_api_slots(
                    target_date=args.target_date,
                    slot_type="send_order",
                    daily_limit=config.hard_limits.max_order_count_per_day,
                    base_events=send_slot_events,
                )
                if not send_slot_batch.get("reserved"):
                    blocker = str(
                        send_slot_batch.get("blocker")
                        or "send_order_api_slot_batch_reservation_failed"
                    )
                    blockers.append(blocker)
                    adapter_status = "adapter_blocked_send_order_api_slot"
                    append_execution_ledger_event(
                        {
                            "event_type": "api_slot_reservation_blocked",
                            **active_reserved_context,
                            "api_slot_type": "send_order",
                            "api_slot_requested_count": len(final_requests),
                            "api_slot_blocker": blocker,
                        }
                    )
                    submitted_rows.append(
                        {
                            "intent_id": row.get("intent_id", ""),
                            "vt_symbol": row.get("vt_symbol", ""),
                            "mode": "live-real",
                            "submit_status": "send_order_api_slot_batch_blocked_before_call",
                            "intent_fingerprint": fingerprint,
                            "api_slot_blocker": blocker,
                            "child_order_count": len(final_requests),
                            **reprice_result,
                        }
                    )
                    active_reserved_context = None
                    break

                send_slot_batch_id = str(send_slot_batch.get("api_slot_batch_id", ""))
                active_reserved_context = None
                completed_children = 0
                for child_index, child_req in enumerate(final_requests):
                    child_result = _submit_pre_reserved_child(
                        main_engine=main_engine,
                        rows=rows,
                        req=child_req,
                        args=args,
                        config=config,
                        row=row,
                        fingerprint=fingerprint,
                        intent_metadata=intent_metadata,
                        reprice_result=reprice_result,
                        child_index=child_index,
                        child_count=len(final_requests),
                        send_slot_batch_id=send_slot_batch_id,
                    )
                    send_count += int(child_result.get("send_called", 0))
                    cancel_count += int(child_result.get("cancel_called", 0))
                    submitted_rows.append(dict(child_result.get("submitted_row", {})))
                    child_blockers = list(child_result.get("blockers", []))
                    if child_blockers:
                        blockers.extend(child_blockers)
                        adapter_status = str(
                            child_result.get("adapter_status")
                            or "adapter_blocked_converted_child_failure"
                        )
                        append_execution_ledger_event(
                            {
                                "event_type": "converted_order_batch_failed_closed",
                                "target_date": args.target_date,
                                "intent_id": row.get("intent_id", ""),
                                "intent_fingerprint": fingerprint,
                                "parent_intent_fingerprint": fingerprint,
                                "vt_symbol": row.get("vt_symbol", ""),
                                "adapter": "Stage931",
                                "failed_child_order_index": child_index,
                                "completed_child_order_count": completed_children,
                                "unsent_child_order_count": len(final_requests) - child_index - 1,
                                "child_blockers": child_blockers,
                                **intent_metadata,
                            }
                        )
                        break
                    completed_children += 1
                if blockers:
                    break
            if not blockers:
                adapter_status = "adapter_live_real_completed"
        except Exception as exc:
            adapter_status = "adapter_exception"
            blockers.append(repr(exc))
            if active_reserved_context is not None:
                append_execution_ledger_event(
                    {
                        "event_type": "adapter_exception_after_reserve",
                        **active_reserved_context,
                        "pre_send_exception_confirmed": 1,
                        "send_slot_reserved": 0,
                        "exception": repr(exc),
                    }
                )
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
            if callback_instrumented and callback_context is not None:
                callback_context.__exit__(None, None, None)

    summary = {
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "target_date": args.target_date,
        "mode": args.mode,
        "execution_profile": execution_profile.profile_key,
        "official_live_version": execution_profile.official_version,
        "official_live_alias": execution_profile.alias,
        "capital": execution_profile.capital,
        "capital_label": execution_profile.capital_label,
        "adapter_status": adapter_status,
        "ready_intent_count": int(len(ready)),
        "unfiltered_ready_intent_count": unfiltered_ready_count,
        "deferred_ready_intent_count": int(len(deferred_ready)),
        "deferred_ready_intent_ids": [
            str(value)
            for value in deferred_ready.get(
                "intent_id", pd.Series([], dtype=str)
            ).fillna("").tolist()
            if str(value)
        ],
        "terminal_duplicate_ready_intent_count": int(len(terminal_duplicate_ready)),
        "terminal_duplicate_ready_intent_ids": [
            str(value)
            for value in terminal_duplicate_ready.get(
                "intent_id", pd.Series([], dtype=str)
            ).fillna("").tolist()
            if str(value)
        ],
        "ledger_nonretryable_close_intent_count": int(
            len(ledger_nonretryable_close_ready)
        ),
        "ledger_nonretryable_close_intent_ids": [
            str(value)
            for value in ledger_nonretryable_close_ready.get(
                "intent_id", pd.Series([], dtype=str)
            ).fillna("").tolist()
            if str(value)
        ],
        "ledger_nonretryable_close_intents": [
            {
                "intent_id": str(item.get("intent_id", "") or ""),
                "vt_symbol": str(item.get("vt_symbol", "") or ""),
                "intent_fingerprint": str(
                    item.get("ledger_preselection_fingerprint", "") or ""
                ),
                "blocker": str(
                    item.get("ledger_preselection_blocker", "") or ""
                ),
                "evidence_event": str(
                    item.get("ledger_preselection_evidence_event", "") or ""
                ),
            }
            for item in ledger_nonretryable_close_ready.to_dict(orient="records")
        ],
        "reduce_close_only_requested": int(bool(args.reduce_close_only)),
        "blocking_failure_count": len(blockers),
        "blockers": blockers,
        "stage905_summary_age_seconds": stage905_age,
        "stage927_summary_age_seconds": stage927_age,
        "close_only_reduce_risk_override": int(close_only_reduce_risk),
        "stage902_allow_reduce_close": int(allow_reduce_close),
        **readonly_order_snapshot_diagnostic,
        "readonly_orders_confirmed": int(
            readonly_order_snapshot_diagnostic[
                "readonly_order_snapshot_confirmed"
            ]
        ),
        "target_date_age_days": target_age_days,
        "current_phase_d_sessions": current_phase_d_sessions,
        "continuous_submit_blockers": continuous_submit_blockers,
        "stage179_pre_adapter_gate": stage179_gate_summary,
        "ledger_path": str(LIVE_EXECUTION_LEDGER_PATH.resolve()),
        "ledger_counts_before": ledger_counts,
        "ledger_intents": ledger_intent_rows,
        "ctp_connection_flags": connection_flags,
        "ctp_readiness_state": readiness_state_summary,
        "final_pre_send_snapshot_epochs": final_snapshot_summaries,
        # Compatibility alias for existing report consumers; entries now
        # describe the stronger order-position-order composite epoch.
        "final_order_query_epochs": final_snapshot_summaries,
        "send_order_api_called_count": send_count,
        "cancel_order_api_called_count": cancel_count,
        "order_api_called_count": send_count + cancel_count,
        "order_api_evidence_complete": 1,
        "order_api_evidence_missing_fields": [],
        "order_row_count": len(rows["orders"]),
        "trade_row_count": len(rows["trades"]),
        "unscoped_position_event_count": len(rows["position_events_unscoped"]),
        "tick_row_count": len(rows["ticks"]),
        "outputs": {key: str(value.resolve()) for key, value in paths.items()},
        "judgement": {
            "overfit_before": "否。Stage931 是执行适配器，不改策略参数。",
            "continue_before": "是。全自动开平仓需要最后一层受控 submit adapter。",
            "overfit_after": "否。结果只影响执行证据。",
            "continue_after": "是。上线前必须先有小额 smoke/live gate 证据和 TCA/对账闭环。",
        },
    }
    submitted = pd.DataFrame(submitted_rows)
    _atomic_write_dataframe(paths["submitted_csv"], submitted)
    _write_df(paths["orders_csv"], rows["orders"])
    _write_df(paths["trades_csv"], rows["trades"])
    _write_df(paths["accounts_csv"], rows["accounts"])
    _write_df(paths["positions_csv"], rows["positions"])
    _write_df(paths["ticks_csv"], rows["ticks"])
    _write_df(paths["logs_csv"], rows["logs"])
    _atomic_write_text(
        paths["summary_json"],
        json.dumps(summary, ensure_ascii=False, indent=2, default=str),
        durable=True,
    )
    _atomic_write_text(paths["report_md"], _build_report(summary, submitted))
    summary["email_notification"] = _send_submit_email(paths, summary, submitted)
    _atomic_write_text(
        paths["summary_json"],
        json.dumps(summary, ensure_ascii=False, indent=2, default=str),
        durable=True,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    return summary


def _load_runtime_env_values(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            raise RuntimeProfileError("runtime_env_line_invalid")
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or not key.replace("_", "A").isalnum() or key[0].isdigit():
            raise RuntimeProfileError("runtime_env_key_invalid")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def _stage179_spool_lease_row(lease: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = dict(lease.intent.payload)
    order_payload = payload.get("order_request")
    if not isinstance(order_payload, dict) or not order_payload:
        raise ValueError("stage179_spool_order_request_missing")
    row = {
        **payload,
        "intent_id": lease.intent.intent_id,
        # The Task7 payload keeps this nested for stable hashing; legacy
        # Stage931 validators consume the equivalent materialized columns.
        "order_request_json": json.dumps(
            order_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ),
        "symbol": order_payload.get("symbol", ""),
        "exchange": order_payload.get("exchange", ""),
        "direction": order_payload.get("direction", ""),
        "offset": order_payload.get("offset", payload.get("offset", "")),
        "vt_symbol": order_payload.get(
            "vt_symbol",
            payload.get("vt_symbol", ""),
        ),
        "order_request_price": order_payload.get("price", 0.0),
        "order_request_volume": order_payload.get("volume", 0.0),
    }
    return row, dict(order_payload)


def _append_stage179_warm_pre_send_safe_terminal(
    *,
    lease: Any,
    context: dict[str, Any],
    blockers: list[str],
    ledger_path: Path,
    blocked_phase: str = "pre_api_slot",
) -> dict[str, Any]:
    """Close one reserved ledger lease before any broker/API side effect.

    This helper is only valid before ``reserve_execution_api_slots``.  The
    explicit zero-side-effect fields make that boundary reviewable and bind a
    close retry terminal to the exact attempt lease allocated by the ledger.
    """

    base_event: dict[str, Any] = {
        "vt_symbol": lease.intent.vt_symbol,
        "adapter": "Stage931Warm",
        "service_generation": lease.intent.lease_owner,
        "connection_generation": str(context.get("connection_generation", "")),
    }
    close_submit_attempt_no = int(
        context.get("close_submit_attempt_no", 0) or 0
    )
    close_attempt_lease_token = str(
        context.get("close_attempt_lease_token", "") or ""
    )
    if close_submit_attempt_no > 0:
        base_event["close_submit_attempt_no"] = close_submit_attempt_no
        base_event["close_attempt_lease_token"] = close_attempt_lease_token
    return append_pre_api_slot_no_side_effect_terminal(
        target_date=lease.intent.target_date,
        intent_id=lease.intent.intent_id,
        intent_payload_sha256=lease.intent.payload_sha256,
        intent_kind=lease.intent.intent_kind,
        intent_fingerprint=str(context.get("fingerprint", "")),
        reservation_record_checksum=str(
            context.get("reservation_record_checksum", "")
        ),
        spool_lease_owner=lease.intent.lease_owner,
        spool_lease_token=lease.lease_token,
        blockers=blockers,
        blocked_phase=blocked_phase,
        base_event=base_event,
        path=ledger_path,
    )


def _prune_stage179_warm_rows(rows: dict[str, Any]) -> None:
    """Bound long-lived diagnostic buffers without weakening ingress counts."""

    if _to_int(rows.get("_physical_batch_active"), 0) == 1:
        # Row indices are causal evidence while a batch is in flight. Prune
        # only after the batch lock is released and the final rebase is done.
        return
    limits = {
        "ticks": 4096,
        "logs": 2048,
        "orders": 2048,
        "trades": 2048,
        "accounts": 128,
        "account_query_callbacks": 256,
        "max_order_volume_query_callbacks": 256,
        "position_events_unscoped": 2048,
        "order_insert_requests": 2048,
    }
    for key, limit in limits.items():
        buffer = rows.get(key)
        if isinstance(buffer, list) and len(buffer) > limit * 2:
            # Slice deletion preserves the list object used by callbacks.  In
            # live mode order/trade race authority is the pre-enqueue ingress
            # counter, so pruning diagnostic rows cannot hide a send blocker.
            if key == "logs":
                # Readiness derives auth/login evidence from the startup log
                # prefix; retain that prefix as well as the recent tail.
                buffer[:] = buffer[:128] + buffer[-limit:]
            else:
                del buffer[:-limit]


def _build_stage179_warm_ctp_session(
    args: argparse.Namespace,
    runtime: Any,
    paths: ExecutorServicePaths,
) -> CtpExecutionSession:
    """Build the real warm backend only after the Task9 gate has passed."""

    execution_profile = _execution_profile_for_args(args)
    service_generation = uuid.uuid4().hex
    reconciliation_lock = threading.RLock()
    execution_event_ingress_lock = threading.RLock()
    state: dict[str, Any] = {
        "main_engine": None,
        "event_engine": None,
        "gateway": None,
        "td_api": None,
        "readiness_state": None,
        "callback_context": None,
        "transport_generation_invalidated": False,
        "rows": {
            "orders": [],
            "trades": [],
            "accounts": [],
            "positions": [],
            "ticks": [],
            "logs": [],
            "settlement_callbacks": [],
            "account_query_callbacks": [],
            "max_order_volume_query_callbacks": [],
            "position_query_callbacks": [],
            "order_query_callbacks": [],
            "trade_query_callbacks": [],
            "order_insert_requests": [],
            "order_action_requests": [],
            "position_events_unscoped": [],
            # The native reqOrderInsert wrapper reads this exact object.  Keep
            # the same RLock in state for callbacks/tests and in rows for the
            # instrumentation layer so production cannot silently fall back
            # to a nullcontext.
            "_execution_event_ingress_lock": (
                execution_event_ingress_lock
            ),
        },
        "intent_contexts": {},
        "order_contexts": {},
        "callback_persistence_blockers": [],
        "reconciliation_lock": reconciliation_lock,
        "reconciliation_blockers": _RecoverableReconciliationBlockers(
            reconciliation_lock
        ),
        "reconciliation_pending_order_ids": _ThreadSafeIdentitySet(
            reconciliation_lock
        ),
        "execution_event_ingress_lock": execution_event_ingress_lock,
        "authorization_pin": None,
        # One re-entrant lock spans the entire physical batch.  The nested
        # native-insert guard uses the same object so no query can interleave
        # between SHFE/INE children.
        "ctp_query_lock": threading.RLock(),
    }
    authorization_path = submit_authorization_path(runtime.output_root)
    authorization_lock_path = submit_authorization_lock_path(
        runtime.output_root
    )

    def authorization_blockers(
        *,
        target_date: str | None = None,
        intent_id: str | None = None,
        payload_sha256: str | None = None,
        intent_kind: str | None = None,
        child_offset: str | None = None,
    ) -> list[str]:
        return validate_submit_authorization(
            path=authorization_path,
            target_date=target_date,
            execution_profile=execution_profile.profile_key,
            runtime_profile=runtime.profile.value,
            order_scope=runtime.order_scope.value,
            service_generation=service_generation,
            connection_generation=str(state.get("connection_generation", "")),
            now_epoch_ns=time.time_ns(),
            intent_id=intent_id,
            payload_sha256=payload_sha256,
            intent_kind=intent_kind,
            child_offset=child_offset,
        )

    def admit_exact_authorized_intent() -> Mapping[str, str]:
        """Pin one canonical ready-row authorization under the shared flock."""

        state["authorization_pin"] = None
        before = read_submit_authorization(authorization_path)
        records = authorized_submit_intent_records(authorization_path)
        after = read_submit_authorization(authorization_path)
        before_digest = str(before.get("record_digest", "")).strip().lower()
        after_digest = str(after.get("record_digest", "")).strip().lower()
        if (
            len(records) != 1
            or len(before_digest) != 64
            or before_digest != after_digest
        ):
            return {}
        record = dict(records[0])
        required_record_fields = (
            "intent_id",
            "payload_sha256",
            "intent_kind",
            "vt_symbol",
            "source",
            "intent_role",
            "trace_id",
            "spool_sequence",
            "state_revision",
            "state_generation",
            "position_epoch_id",
            "root_position_id",
            "position_cycle_id",
            "deadline_epoch_ns",
        )
        if any(field_name not in record for field_name in required_record_fields):
            return {}
        lane = str(after.get("authorization_lane", "")).strip()
        scope = str(after.get("intent_scope", "")).strip()
        binding_digests = {
            field_name: str(after.get(field_name, "")).strip().lower()
            for field_name in (
                "spool_snapshot_digest",
                "cursor_digest",
                "stage902_evidence_digest",
                "stage927_evidence_digest",
            )
        }
        if (
            str(after.get("spool_path", "")).strip()
            != str(paths.spool_path.expanduser().resolve(strict=False))
            or any(
                len(value) != 64
                or any(character not in "0123456789abcdef" for character in value)
                for value in binding_digests.values()
            )
        ):
            return {}
        blockers = validate_submit_authorization(
            path=authorization_path,
            target_date=str(after.get("target_date", "")),
            execution_profile=execution_profile.profile_key,
            runtime_profile=runtime.profile.value,
            order_scope=runtime.order_scope.value,
            service_generation=service_generation,
            connection_generation=str(state.get("connection_generation", "")),
            now_epoch_ns=time.time_ns(),
            intent_id=str(record["intent_id"]),
            payload_sha256=str(record["payload_sha256"]),
            intent_kind=str(record["intent_kind"]),
            child_offset=str(record["intent_kind"]),
            authorization_lane=lane,
            intent_scope=scope,
            vt_symbol=str(record["vt_symbol"]),
            source=str(record["source"]),
            intent_role=str(record["intent_role"]),
            trace_id=str(record["trace_id"]),
            spool_sequence=int(record["spool_sequence"]),
            state_revision=int(record["state_revision"]),
            state_generation=str(record["state_generation"]),
            position_epoch_id=str(record["position_epoch_id"]),
            root_position_id=str(record["root_position_id"]),
            position_cycle_id=str(record["position_cycle_id"]),
            deadline_epoch_ns=int(record["deadline_epoch_ns"]),
            spool_path=paths.spool_path,
            **binding_digests,
        )
        if blockers:
            return {}
        state["authorization_pin"] = {
            "record_digest": after_digest,
            "record": record,
            "authorization_lane": lane,
            "intent_scope": scope,
            "target_date": str(after.get("target_date", "")),
            "spool_path": str(after.get("spool_path", "")),
            **binding_digests,
        }
        return {
            str(record["intent_id"]): str(record["payload_sha256"])
        }

    def leased_authorization_blockers(
        lease: Any,
        *,
        child_offset: str | None = None,
    ) -> list[str]:
        pin = state.get("authorization_pin")
        if not isinstance(pin, dict):
            return ["stage179_submit_authorization_pin_missing"]
        record = pin.get("record")
        if not isinstance(record, dict):
            return ["stage179_submit_authorization_pin_record_missing"]
        intent = lease.intent
        blockers: list[str] = []
        ready_revision = int(record.get("state_revision", -1))
        leased_revision = int(getattr(intent, "state_revision", -1))
        if leased_revision != ready_revision + 1:
            blockers.append(
                "stage179_submit_authorization_leased_state_revision_mismatch"
            )
        if str(getattr(intent, "state", "")) != "leased":
            blockers.append(
                "stage179_submit_authorization_leased_state_invalid"
            )
        if str(getattr(intent, "lease_owner", "")) != service_generation:
            blockers.append(
                "stage179_submit_authorization_lease_owner_mismatch"
            )
        payload = getattr(intent, "payload", {})
        if not isinstance(payload, Mapping):
            return blockers + [
                "stage179_submit_authorization_lease_payload_invalid"
            ]
        blockers.extend(
            validate_submit_authorization(
                path=authorization_path,
                target_date=str(getattr(intent, "target_date", "")),
                execution_profile=execution_profile.profile_key,
                runtime_profile=runtime.profile.value,
                order_scope=runtime.order_scope.value,
                service_generation=service_generation,
                connection_generation=str(
                    state.get("connection_generation", "")
                ),
                now_epoch_ns=time.time_ns(),
                intent_id=str(getattr(intent, "intent_id", "")),
                payload_sha256=str(
                    getattr(intent, "payload_sha256", "")
                ),
                intent_kind=str(getattr(intent, "intent_kind", "")),
                child_offset=(
                    child_offset
                    if child_offset is not None
                    else str(getattr(intent, "intent_kind", ""))
                ),
                authorization_lane=str(pin.get("authorization_lane", "")),
                intent_scope=str(pin.get("intent_scope", "")),
                vt_symbol=str(getattr(intent, "vt_symbol", "")),
                source=str(getattr(intent, "source", "")),
                intent_role=str(payload.get("intent_role", "")),
                trace_id=str(getattr(intent, "trace_id", "")),
                spool_sequence=int(getattr(intent, "spool_sequence", -1)),
                state_revision=leased_revision - 1,
                state_generation=str(
                    getattr(intent, "state_generation", "")
                ),
                position_epoch_id=str(
                    getattr(intent, "position_epoch_id", "")
                ),
                root_position_id=str(payload.get("root_position_id", "")),
                position_cycle_id=str(
                    payload.get("position_cycle_id", "")
                ),
                deadline_epoch_ns=int(
                    getattr(intent, "deadline_epoch_ns", -1)
                ),
                spool_path=paths.spool_path,
                spool_snapshot_digest=str(
                    pin.get("spool_snapshot_digest", "")
                ),
                cursor_digest=str(pin.get("cursor_digest", "")),
                stage902_evidence_digest=str(
                    pin.get("stage902_evidence_digest", "")
                ),
                stage927_evidence_digest=str(
                    pin.get("stage927_evidence_digest", "")
                ),
                allow_expired_if_record_digest=str(
                    pin.get("record_digest", "")
                ),
            )
        )
        return list(dict.fromkeys(str(item) for item in blockers if str(item)))

    @contextmanager
    def authorization_lease_guard() -> Iterator[None]:
        state["authorization_pin"] = None
        try:
            with shared_submit_authorization_lock(authorization_lock_path):
                yield
        finally:
            state["authorization_pin"] = None
            state["intent_contexts"].clear()

    def connect_startup_bundle() -> dict[str, Any]:
        # This import is deliberately inside the post-gate adapter factory.
        from vnpy_ctp import CtpGateway
        from vnpy_ctp.gateway import ctp_gateway as ctp_gateway_module

        rows = state["rows"]
        def on_front_disconnected(_reason: int) -> None:
            state["transport_generation_invalidated"] = True

        callback_context = _instrument_ctp_readiness_callbacks(
            ctp_gateway_module.CtpTdApi,
            rows,
            on_front_disconnected=on_front_disconnected,
        )
        callback_context.__enter__()
        state["callback_context"] = callback_context
        try:
            event_engine = EventEngine()
            main_engine = MainEngine(event_engine)
            gateway = main_engine.add_gateway(CtpGateway)
            td_api = gateway.td_api
            state.update(
                main_engine=main_engine,
                event_engine=event_engine,
                gateway=gateway,
                td_api=td_api,
            )

            ingress_lock = state["execution_event_ingress_lock"]
            callback_persistence_lock = Lock()
            ingress_counts = {"order": 0, "trade": 0, "position": 0}
            rows["_execution_event_ingress_counts"] = ingress_counts
            rows["_execution_event_ingress_lock"] = ingress_lock

            original_tick = gateway.on_tick
            original_order = gateway.on_order
            original_trade = gateway.on_trade
            original_position = gateway.on_position

            def increment(name: str) -> None:
                with ingress_lock:
                    ingress_counts[name] += 1

            def ingress_tick(tick: Any) -> Any:
                _stamp_tick_before_event_enqueue(tick)
                return original_tick(tick)

            def ingress_order(order: Any) -> Any:
                if not int(getattr(_ORDER_QUERY_FORWARD_CONTEXT, "depth", 0)):
                    with ingress_lock:
                        increment("order")
                        row = _object_to_row(order)
                        rows["orders"].append(row)
                        persist_callback("order", row)
                return original_order(order)

            def ingress_trade(trade: Any) -> Any:
                with ingress_lock:
                    increment("trade")
                    row = _object_to_row(trade)
                    rows["trades"].append(row)
                    persist_callback("trade", row)
                return original_trade(trade)

            def ingress_position(position: Any) -> Any:
                increment("position")
                row = _object_to_row(position)
                rows["position_events_unscoped"].append(row)
                persist_callback("position", row)
                return original_position(position)

            gateway.on_tick = ingress_tick
            gateway.on_order = ingress_order
            gateway.on_trade = ingress_trade
            gateway.on_position = ingress_position

            def callback_context(row: Mapping[str, Any]) -> dict[str, Any] | None:
                vt_orderid = str(row.get("vt_orderid", "") or "").strip()
                context = state["order_contexts"].get(vt_orderid)
                if context is not None:
                    return context
                reference = str(row.get("reference", "") or "").strip()
                prefix = "Stage905PhaseD:"
                referenced_intent_id = ""
                if reference.startswith(prefix):
                    intent_id = reference[len(prefix) :]
                    referenced_intent_id = intent_id
                    context = state["intent_contexts"].get(intent_id)
                    if context is not None and vt_orderid:
                        state["order_contexts"][vt_orderid] = context
                    if context is not None:
                        return context
                if vt_orderid:
                    # Reconstruct a prior-process correlation from the
                    # durable send-return row.  This keeps reconnect/restart
                    # callbacks bound without trusting volatile memory.
                    for ledger_row in reversed(
                        read_execution_ledger(paths.ledger_path)
                    ):
                        is_return_binding = bool(
                            str(ledger_row.get("event_type", ""))
                            in {
                                "send_order_returned",
                                "native_order_identity_persisted_before_insert",
                            }
                            and str(ledger_row.get("vt_orderid", "") or "")
                            == vt_orderid
                        )
                        is_reference_binding = bool(
                            referenced_intent_id
                            and str(ledger_row.get("event_type", ""))
                            == "send_order_called"
                            and str(ledger_row.get("intent_id", ""))
                            == referenced_intent_id
                            and (
                                not row.get("offset")
                                or _normalize_offset_text(row.get("offset"))
                                == _normalize_offset_text(ledger_row.get("offset"))
                            )
                        )
                        if not (is_return_binding or is_reference_binding):
                            continue
                        try:
                            request = _order_request_from_payload(
                                {
                                    "symbol": str(
                                        ledger_row.get("symbol", "")
                                        or str(ledger_row.get("vt_symbol", "")).split(".")[0]
                                    ),
                                    "exchange": str(
                                        ledger_row.get("exchange", "")
                                        or str(ledger_row.get("vt_symbol", "")).partition(".")[2]
                                    ),
                                    "direction": ledger_row.get("direction", ""),
                                    "type": ledger_row.get("order_type", "limit"),
                                    "volume": ledger_row.get("volume", 0),
                                    "price": ledger_row.get("price", 0),
                                    "offset": ledger_row.get("offset", ""),
                                    "reference": ledger_row.get("reference", ""),
                                }
                            )
                        except (KeyError, TypeError, ValueError):
                            return None
                        context = {
                            "target_date": ledger_row.get("target_date", ""),
                            "intent_id": ledger_row.get("intent_id", ""),
                            "intent_payload_sha256": ledger_row.get(
                                "intent_payload_sha256", ""
                            ),
                            "intent_kind": ledger_row.get("intent_kind", ""),
                            "fingerprint": ledger_row.get(
                                "intent_fingerprint", ""
                            ),
                            "row": dict(ledger_row),
                            "request": request,
                            "service_generation": ledger_row.get(
                                "service_generation", ""
                            ),
                            "connection_generation": ledger_row.get(
                                "connection_generation", ""
                            ),
                            "spool_lease_owner": ledger_row.get(
                                "spool_lease_owner", ""
                            ),
                            "spool_lease_token": ledger_row.get(
                                "spool_lease_token", ""
                            ),
                            "child_order_id": ledger_row.get(
                                "child_order_id", ""
                            ),
                            "child_order_index": ledger_row.get(
                                "child_order_index", 0
                            ),
                            "child_order_count": ledger_row.get(
                                "child_order_count", 1
                            ),
                            "close_submit_attempt_no": ledger_row.get(
                                "close_submit_attempt_no", 0
                            ),
                            "close_attempt_lease_token": ledger_row.get(
                                "close_attempt_lease_token", ""
                            ),
                            "insert_audit": dict(ledger_row),
                        }
                        state["order_contexts"][vt_orderid] = context
                        return context
                return None

            def persist_callback(kind: str, row: dict[str, Any]) -> bool:
                with callback_persistence_lock:
                    row["_stage179_callback_persistence_confirmed"] = 0
                    context = callback_context(row)
                    if context is not None:
                        vt_orderid = str(row.get("vt_orderid", "") or "")
                        totals, totals_blocker = _unique_trade_callback_totals(
                            rows["trades"], vt_orderid
                        )
                        if totals_blocker:
                            state["reconciliation_blockers"].append(totals_blocker)
                            return False
                        context["trade_callback_count"] = totals["count"]
                        context["trade_event_total_volume"] = totals["total_volume"]
                        context["trade_event_priced_volume"] = totals["priced_volume"]
                    if kind == "position" and context is None:
                        context = {
                            "target_date": args.target_date,
                            "row": {},
                            "connection_generation": state.get(
                                "connection_generation", ""
                            ),
                        }
                    try:
                        results = _persist_stage179_warm_broker_callback(
                            kind=kind,
                            callback=row,
                            context=context,
                            target_date=args.target_date,
                            ledger_path=paths.ledger_path,
                        )
                    except BaseException as exc:
                        blocker = (
                            "stage179_broker_callback_persistence_exception:"
                            f"{kind}:{type(exc).__name__}"
                        )
                        state["callback_persistence_blockers"].append(blocker)
                        state["transport_generation_invalidated"] = True
                        return False
                    persistence_confirmed = True
                    for result in results:
                        blocker = str(result.get("blocker", "") or "")
                        if blocker:
                            state["callback_persistence_blockers"].append(blocker)
                            state["transport_generation_invalidated"] = True
                            persistence_confirmed = False
                    if kind == "order" and context is not None:
                        vt_orderid = str(row.get("vt_orderid", "") or "")
                        for prior in read_execution_ledger(paths.ledger_path):
                            if (
                                prior.get("event_type")
                                == "broker_trade_callback_unbound"
                                and str(prior.get("vt_orderid", "") or "")
                                == vt_orderid
                            ):
                                _persist_stage179_warm_broker_callback(
                                    kind="trade",
                                    callback=prior,
                                    context=context,
                                    target_date=args.target_date,
                                    ledger_path=paths.ledger_path,
                                )
                    if kind == "order" and context is not None:
                        status = row.get("status")
                        order_traded = _to_float(row.get("traded"), 0.0)
                        priced_traded = _to_float(
                            context.get("trade_event_priced_volume"), 0.0
                        )
                        terminal = _status_is_terminal(status) or order_traded >= _to_float(
                            row.get("volume"), float("inf")
                        )
                        if terminal and priced_traded + 1e-9 >= order_traded:
                            _resolve_reconciliation_order(
                                state, str(row.get("vt_orderid", "") or "")
                            )
                        elif terminal:
                            state["reconciliation_pending_order_ids"].add(
                                str(row.get("vt_orderid", "") or "")
                            )
                    row["_stage179_callback_persistence_confirmed"] = int(
                        persistence_confirmed
                    )
                    return persistence_confirmed

            def on_warm_order(event: Any) -> None:
                row = _object_to_row(event.data)
                persist_callback("order", row)

            def on_warm_trade(event: Any) -> None:
                row = _object_to_row(event.data)
                persist_callback("trade", row)

            event_engine.register(EVENT_ORDER, on_warm_order)
            event_engine.register(EVENT_TRADE, on_warm_trade)
            event_engine.register(
                EVENT_ACCOUNT,
                lambda event: rows["accounts"].append(_object_to_row(event.data)),
            )
            def on_warm_position(event: Any) -> None:
                row = _object_to_row(event.data)
                persist_callback("position", row)

            event_engine.register(EVENT_POSITION, on_warm_position)
            event_engine.register(
                EVENT_TICK,
                lambda event: rows["ticks"].append(_tick_event_row(event.data)),
            )
            event_engine.register(
                EVENT_LOG,
                lambda event: rows["logs"].append(_object_to_row(event.data)),
            )

            def persist_before_native_order_insert(
                native_td_api: Any,
                native_request: dict[str, Any],
                reqid: int,
            ) -> None:
                native_gate = state.get("native_dynamic_gate")
                if not callable(native_gate):
                    raise RuntimeError("stage179_native_dynamic_gate_missing")
                native_gate_blockers = list(
                    native_gate(
                        native_td_api,
                        dict(native_request),
                        int(reqid),
                    )
                )
                if native_gate_blockers:
                    raise BrokerSendBatchError(
                        "stage179_native_dynamic_gate_blocked:"
                        + ";".join(native_gate_blockers),
                        send_order_call_count=int(
                            state.get("native_prior_send_order_call_count", 0) or 0
                        ),
                    )
                native_context = state.get("native_insert_context")
                if not isinstance(native_context, dict):
                    raise RuntimeError(
                        "stage179_native_insert_context_missing"
                    )
                front_id = str(getattr(native_td_api, "frontid", "") or "")
                session_id = str(
                    getattr(native_td_api, "sessionid", "") or ""
                )
                order_ref = str(native_request.get("OrderRef", "") or "")
                if not front_id or not session_id or not order_ref:
                    raise RuntimeError(
                        "stage179_native_order_identity_incomplete"
                    )
                vt_orderid = f"CTP.{front_id}_{session_id}_{order_ref}"
                identity = {
                    "target_date": native_context.get("target_date", ""),
                    "intent_id": native_context.get("intent_id", ""),
                    "intent_fingerprint": native_context.get(
                        "intent_fingerprint", ""
                    ),
                    "spool_lease_owner": native_context.get(
                        "spool_lease_owner", ""
                    ),
                    "spool_lease_token": native_context.get(
                        "spool_lease_token", ""
                    ),
                    "child_order_id": native_context.get(
                        "child_order_id", ""
                    ),
                    "connection_generation": native_context.get(
                        "connection_generation", ""
                    ),
                    "front_id": front_id,
                    "session_id": session_id,
                    "order_ref": order_ref,
                    "vt_orderid": vt_orderid,
                    "req_order_insert_reqid": int(reqid),
                }
                result = append_broker_callback_event_once(
                    {
                        **native_context,
                        **identity,
                        "event_type": (
                            "native_order_identity_persisted_before_insert"
                        ),
                        "broker_callback_key": _stage179_callback_key(
                            "native-order-insert-identity", identity
                        ),
                        "native_api_called": 0,
                    },
                    paths.ledger_path,
                )
                blocker = str(result.get("blocker", "") or "")
                if blocker:
                    raise RuntimeError(
                        "stage179_native_identity_durable_append_failed:"
                        + blocker
                    )
                state["native_insert_identity"] = identity
                child_context = state.get("native_child_context")
                batch = state.get("active_physical_batch")
                if not isinstance(child_context, dict) or not isinstance(
                    batch, dict
                ):
                    raise RuntimeError(
                        "stage179_physical_batch_native_context_missing"
                    )
                request = child_context.get("request")
                if not isinstance(request, OrderRequest):
                    raise RuntimeError(
                        "stage179_physical_batch_child_request_missing"
                    )
                owned_child = {
                    "child_order_id": child_context.get(
                        "child_order_id", ""
                    ),
                    "child_order_index": child_context.get(
                        "child_order_index", -1
                    ),
                    "native_reqid": int(reqid),
                    "vt_orderid": vt_orderid,
                    "request": request,
                    "trade_identities": {},
                }
                batch.setdefault("owned_children", {})[
                    vt_orderid
                ] = owned_child
                state["order_contexts"][vt_orderid] = child_context

            rows["_before_native_order_insert"] = (
                persist_before_native_order_insert
            )
            _connect_ctp_without_timer_queries(main_engine, gateway, event_engine)
            ready, flags, blockers, readiness_state = _wait_for_ctp_readiness(
                td_api,
                rows,
                account_required=True,
                max_wait_seconds=max(0.0, float(args.connect_wait_seconds)),
            )
            state["readiness_state"] = readiness_state
            if ready and not blockers:
                state["transport_generation_invalidated"] = False
                ledger_rows = read_execution_ledger(paths.ledger_path)
                recovered: set[str] = set()
                unresolved: list[tuple[str, dict[str, Any]]] = []
                for ledger_row in reversed(ledger_rows):
                    if (
                        ledger_row.get("target_date") != args.target_date
                        or ledger_row.get("event_type")
                        not in {
                            "send_order_returned",
                            "native_order_identity_persisted_before_insert",
                        }
                    ):
                        continue
                    vt_orderid = str(ledger_row.get("vt_orderid", "") or "")
                    if not vt_orderid or vt_orderid in recovered:
                        continue
                    recovered.add(vt_orderid)
                    terminal = any(
                        str(item.get("vt_orderid", "") or "") == vt_orderid
                        and (
                            item.get("event_type") == "rejected_or_inactive"
                            or (
                                item.get("event_type")
                                == "broker_order_query_terminal_observed"
                                and _to_int(
                                    item.get("fill_price_reconciliation_pending"), 1
                                ) == 0
                            )
                            or (
                                item.get("event_type") == "broker_order_status_observed"
                                and item.get("broker_order_status_class")
                                in {"broker_rejected", "broker_cancelled", "broker_all_traded"}
                            )
                        )
                        for item in ledger_rows
                    )
                    filled = sum(
                        max(0.0, _to_float(item.get("trade_volume_delta"), 0.0))
                        for item in ledger_rows
                        if str(item.get("vt_orderid", "") or "") == vt_orderid
                        and item.get("event_type") == "filled_or_part_filled"
                    )
                    if terminal or filled >= _to_float(ledger_row.get("volume"), float("inf")):
                        continue
                    unresolved.append((vt_orderid, ledger_row))
                if unresolved:
                    trade_query: dict[str, Any] = {
                        "confirmed": False,
                        "trades": [],
                        "blockers": ["stage179_recovery_trade_query_skipped"],
                    }
                    position_query: dict[str, Any] = {
                        "confirmed": False,
                        "positions": [],
                        "blockers": ["stage179_recovery_position_query_skipped"],
                    }
                    with state["ctp_query_lock"]:
                        recovery_query = _final_order_query_epoch(
                            td_api,
                            rows,
                            max_wait_seconds=max(
                                0.0, float(args.final_order_query_wait_seconds)
                            ),
                        )
                    if not recovery_query.get("confirmed"):
                        blockers.extend(
                            recovery_query.get("blockers", [])
                            or ["stage179_recovery_order_query_incomplete"]
                        )
                    authoritative = list(recovery_query.get("orders", []))
                    unresolved_ids = {item[0] for item in unresolved}
                    if recovery_query.get("confirmed"):
                        sysid_map = getattr(td_api, "sysid_orderid_map", None)
                        if not isinstance(sysid_map, dict):
                            blockers.append("stage179_recovery_sysid_orderid_map_missing")
                        else:
                            proposed: dict[str, str] = {}
                            for order in authoritative:
                                if str(order.get("vt_orderid", "")) not in unresolved_ids:
                                    continue
                                sysid = str(order.get("order_sys_id", "") or "")
                                vt_orderid = str(order.get("vt_orderid", "") or "")
                                local_orderid = vt_orderid.partition(".")[2]
                                if not sysid or not local_orderid:
                                    continue
                                if sysid in proposed and proposed[sysid] != local_orderid:
                                    blockers.append(
                                        f"stage179_recovery_sysid_binding_ambiguous:{sysid}"
                                    )
                                    continue
                                existing = str(sysid_map.get(sysid, "") or "")
                                if existing and existing != local_orderid:
                                    blockers.append(
                                        f"stage179_recovery_sysid_binding_conflict:{sysid}"
                                    )
                                    continue
                                proposed[sysid] = local_orderid
                            if not blockers:
                                sysid_map.update(proposed)
                        with state["ctp_query_lock"]:
                            trade_query = _final_trade_query_epoch(
                                td_api,
                                rows,
                                max_wait_seconds=max(
                                    0.0, float(args.final_order_query_wait_seconds)
                                ),
                            )
                            position_query = _final_position_query_epoch(
                                td_api,
                                rows,
                                max_wait_seconds=max(
                                    0.0, float(args.final_order_query_wait_seconds)
                                ),
                            )
                    if not trade_query.get("confirmed"):
                        blockers.extend(
                            trade_query.get("blockers", [])
                            or ["stage179_recovery_trade_query_incomplete"]
                        )
                    if not position_query.get("confirmed"):
                        blockers.extend(
                            position_query.get("blockers", [])
                            or ["stage179_recovery_position_query_incomplete"]
                        )
                    if (
                        recovery_query.get("confirmed")
                        and trade_query.get("confirmed")
                        and position_query.get("confirmed")
                    ):
                        for trade_row in trade_query.get("trades", []):
                            matching_orders = [
                                order
                                for order in authoritative
                                if order.get("exchange") == trade_row.get("exchange")
                                and order.get("order_sys_id") == trade_row.get("order_sys_id")
                                and order.get("vt_orderid")
                                and str(order.get("vt_orderid")) in unresolved_ids
                            ]
                            if not matching_orders:
                                # Account-wide reqQryTrade also returns manual
                                # and other-system activity.  It is diagnostic,
                                # never a Stage931 recovery blocker.
                                continue
                            if len(matching_orders) != 1:
                                blockers.append(
                                    "stage179_recovery_trade_order_identity_"
                                    + "ambiguous"
                                )
                                continue
                            bound_order = matching_orders[0]
                            vt_orderid = str(bound_order["vt_orderid"])
                            context = callback_context(bound_order)
                            if context is None:
                                blockers.append(
                                    f"stage179_recovery_trade_context_missing:{vt_orderid}"
                                )
                                continue
                            _persist_stage179_warm_broker_callback(
                                kind="trade",
                                callback={
                                    **trade_row,
                                    "vt_orderid": vt_orderid,
                                    "vt_symbol": bound_order.get("vt_symbol", ""),
                                },
                                context=context,
                                target_date=args.target_date,
                                ledger_path=paths.ledger_path,
                            )
                        ledger_rows = read_execution_ledger(paths.ledger_path)
                    recovery_bundle_confirmed = bool(
                        recovery_query.get("confirmed")
                        and trade_query.get("confirmed")
                        and position_query.get("confirmed")
                        and not blockers
                    )
                    for vt_orderid, _send_row in unresolved:
                        if not recovery_bundle_confirmed:
                            state["reconciliation_pending_order_ids"].add(vt_orderid)
                            continue
                        current, identity_blocker = _match_reqid_bound_ctp_order(
                            authoritative, vt_orderid
                        )
                        if current is None:
                            if (
                                identity_blocker
                                == "stage179_recovery_order_identity_absent"
                                and _send_row.get("event_type")
                                == "native_order_identity_persisted_before_insert"
                            ):
                                # The durable identity was written before the
                                # native call.  A complete same-generation
                                # Order+Trade+Position bundle with no exact
                                # identity proves the crash happened before
                                # CTP accepted the request.  Close this lease
                                # terminal; never make it sendable again.
                                no_side_effect_identity = {
                                    "target_date": args.target_date,
                                    "intent_id": _send_row.get("intent_id", ""),
                                    "intent_fingerprint": _send_row.get(
                                        "intent_fingerprint", ""
                                    ),
                                    "spool_lease_owner": _send_row.get(
                                        "spool_lease_owner", ""
                                    ),
                                    "spool_lease_token": _send_row.get(
                                        "spool_lease_token", ""
                                    ),
                                    "vt_orderid": vt_orderid,
                                    "order_identity": _send_row.get(
                                        "broker_callback_key", ""
                                    ),
                                    "raw_order_status": (
                                        "absent_from_complete_broker_query"
                                    ),
                                    "traded": 0.0,
                                    "volume": _to_float(
                                        _send_row.get("volume"), 0.0
                                    ),
                                    "durable_priced_volume": 0.0,
                                    "connection_generation": state.get(
                                        "connection_generation", ""
                                    ),
                                }
                                append_broker_callback_event_once(
                                    {
                                        "event_type": (
                                            "broker_order_query_terminal_observed"
                                        ),
                                        **no_side_effect_identity,
                                        "broker_callback_key": (
                                            _stage179_callback_key(
                                                "order-query-terminal",
                                                no_side_effect_identity,
                                            )
                                        ),
                                        "fill_price_reconciliation_pending": 0,
                                        "native_side_effect_absent_proven": 1,
                                    },
                                    paths.ledger_path,
                                )
                                _resolve_reconciliation_order(
                                    state, vt_orderid
                                )
                                continue
                            state["reconciliation_pending_order_ids"].add(vt_orderid)
                            blockers.append(
                                f"{identity_blocker}:{vt_orderid}"
                            )
                            continue
                        if current.get("status_class") == "terminal":
                            durable_priced, durable_fill_blocker = (
                                _exact_durable_priced_volume(
                                    ledger_rows,
                                    context=_send_row,
                                    vt_orderid=vt_orderid,
                                )
                            )
                            if durable_fill_blocker:
                                state["reconciliation_pending_order_ids"].add(
                                    vt_orderid
                                )
                                blockers.append(durable_fill_blocker)
                                continue
                            queried_traded = _to_float(current.get("traded"), 0.0)
                            query_terminal_identity = {
                                **_intent_ledger_metadata(
                                    dict(_send_row.get("row", {}))
                                    if isinstance(_send_row.get("row"), dict)
                                    else _send_row
                                ),
                                "target_date": args.target_date,
                                "intent_id": _send_row.get("intent_id", ""),
                                "intent_fingerprint": _send_row.get(
                                    "intent_fingerprint", ""
                                ),
                                "spool_lease_owner": _send_row.get(
                                    "spool_lease_owner", ""
                                ),
                                "spool_lease_token": _send_row.get(
                                    "spool_lease_token", ""
                                ),
                                "child_order_id": _send_row.get(
                                    "child_order_id", ""
                                ),
                                "child_order_index": _to_int(
                                    _send_row.get("child_order_index"), 0
                                ),
                                "child_order_count": _to_int(
                                    _send_row.get("child_order_count"), 1
                                ),
                                "vt_symbol": _send_row.get("vt_symbol", ""),
                                "direction": _send_row.get("direction", ""),
                                "offset": _send_row.get("offset", ""),
                                "close_submit_attempt_no": _to_int(
                                    _send_row.get("close_submit_attempt_no"), 0
                                ),
                                "vt_orderid": vt_orderid,
                                "order_identity": current.get("order_identity", ""),
                                "raw_order_status": current.get("raw_order_status", ""),
                                "traded": _to_float(current.get("traded"), 0.0),
                                "volume": _to_float(current.get("volume"), 0.0),
                                "durable_priced_volume": durable_priced,
                            }
                            append_broker_callback_event_once(
                                {
                                    "event_type": "broker_order_query_terminal_observed",
                                    **query_terminal_identity,
                                    "broker_callback_key": _stage179_callback_key(
                                        "order-query-terminal",
                                        query_terminal_identity,
                                    ),
                                    "fill_price_reconciliation_pending": int(
                                        queried_traded > durable_priced + 1e-9
                                    ),
                                },
                                paths.ledger_path,
                            )
                            if queried_traded > durable_priced + 1e-9:
                                state["reconciliation_pending_order_ids"].add(vt_orderid)
                                blockers.append(
                                    f"stage179_recovery_terminal_trade_detail_missing:{vt_orderid}"
                                )
                            else:
                                _resolve_reconciliation_order(
                                    state, vt_orderid
                                )
                            continue
                        if current.get("status_class") != "active":
                            state["reconciliation_pending_order_ids"].add(vt_orderid)
                            blockers.append(
                                f"stage179_recovery_order_status_unknown:{vt_orderid}"
                            )
                            continue
                        current = {**current, "vt_orderid": vt_orderid}
                        context = callback_context(current)
                        if context is None:
                            state["reconciliation_pending_order_ids"].add(vt_orderid)
                            blockers.append(
                                f"stage179_recovery_order_context_missing:{vt_orderid}"
                            )
                            continue
                        context["recovering_outstanding_order"] = 1
                        context["recovery_order"] = current
                        schedule_residual_cancel(vt_orderid, context)
                ready = bool(ready and not blockers)
            return {
                "ready": bool(ready and not blockers),
                "flags": flags,
                "blockers": blockers,
            }
        except BaseException:
            main_engine = state.get("main_engine")
            if main_engine is not None:
                main_engine.close()
            callback_context.__exit__(*sys.exc_info())
            state["callback_context"] = None
            raise

    def disconnect_transport() -> None:
        main_engine = state.get("main_engine")
        callback_context = state.get("callback_context")
        state.update(
            main_engine=None,
            event_engine=None,
            gateway=None,
            td_api=None,
            readiness_state=None,
            callback_context=None,
            transport_generation_invalidated=True,
        )
        if main_engine is not None:
            main_engine.close()
        if callback_context is not None:
            callback_context.__exit__(None, None, None)

    def fresh_bundle(lease: Any, hard_deadline_monotonic: float) -> dict[str, Any]:
        _prune_stage179_warm_rows(state["rows"])
        state["intent_contexts"].clear()
        rows = state["rows"]
        main_engine = state.get("main_engine")
        td_api = state.get("td_api")
        readiness_state = state.get("readiness_state")
        try:
            row, order_payload = _stage179_spool_lease_row(lease)
        except ValueError:
            return {"blockers": ["stage179_spool_order_request_missing"]}
        cycle_authorization_blockers = leased_authorization_blockers(lease)
        if cycle_authorization_blockers:
            return {"blockers": cycle_authorization_blockers}
        if main_engine is None or td_api is None or readiness_state is None:
            return {"blockers": ["stage179_ctp_session_state_missing"]}
        kill_switch_blockers = _kill_switch_blockers()
        if kill_switch_blockers:
            return {"blockers": kill_switch_blockers}
        if time.monotonic() >= hard_deadline_monotonic:
            return {
                "blockers": [
                    "stage179_execution_deadline_exceeded:final_snapshot"
                ]
            }

        req = _order_request_from_payload(dict(order_payload))
        rows["_position_vt_symbol_by_instrument"] = {
            req.symbol.upper(): req.vt_symbol
        }
        reserve = reserve_execution_ledger_intent(
            target_date=lease.intent.target_date,
            row=row,
            order_request=dict(order_payload),
            close_retry_after_cancel_seconds=max(
                1,
                int(args.close_retry_after_cancel_seconds),
            ),
            path=paths.ledger_path,
            base_event={
                "intent_id": lease.intent.intent_id,
                "intent_payload_sha256": lease.intent.payload_sha256,
                "intent_kind": lease.intent.intent_kind,
                "vt_symbol": lease.intent.vt_symbol,
                "mode": "live-real",
                "adapter": "Stage931Warm",
                "service_generation": lease.intent.lease_owner,
                "connection_generation": state.get("connection_generation", ""),
                "spool_lease_owner": lease.intent.lease_owner,
                "spool_lease_token": lease.lease_token,
            },
        )
        if not reserve.get("reserved"):
            return {
                "blockers": [
                    str(
                        reserve.get(
                            "duplicate_blocker",
                            "stage179_ledger_intent_reserve_failed",
                        )
                    )
                ]
            }

        remaining = max(0.0, hard_deadline_monotonic - time.monotonic())
        snapshot = _final_pre_send_snapshot_epoch(
            td_api,
            rows,
            max_wait_seconds=min(
                remaining,
                max(0.0, float(args.final_order_query_wait_seconds)),
            ),
            readiness_state=readiness_state,
            hard_deadline_monotonic=hard_deadline_monotonic,
        )
        blockers = list(snapshot.get("blockers", []))
        blockers.extend(
            _final_pre_send_blockers(
                rows,
                req,
                req.vt_symbol,
                authoritative_active_orders=list(snapshot.get("active_orders", [])),
                order_query_confirmed=bool(snapshot.get("confirmed")),
            )
        )
        blockers.extend(_final_ctp_transport_blockers(td_api, rows, readiness_state))
        reprice_result: dict[str, Any] = {}
        final_gate: dict[str, Any] = {}
        if not blockers:
            remaining = max(0.0, hard_deadline_monotonic - time.monotonic())
            reprice_result = _post_snapshot_final_reprice(
                main_engine,
                rows,
                row,
                req,
                max_tick_age_seconds=int(
                    build_phase_d_config().hard_limits.max_tick_age_seconds
                ),
                q2_completed_monotonic=snapshot.get("q2_completed_monotonic"),
                tick_wait_seconds=min(
                    2,
                    max(0, int(min(remaining, args.final_reprice_tick_wait_seconds))),
                ),
            )
            blockers.extend(_final_reprice_blockers(reprice_result))
        if not blockers:
            remaining = max(0.0, hard_deadline_monotonic - time.monotonic())
            final_gate = _post_reprice_final_state_gate(
                main_engine,
                td_api,
                rows,
                row,
                req,
                initial_snapshot=snapshot,
                initial_reprice_result=reprice_result,
                max_tick_age_seconds=int(
                    build_phase_d_config().hard_limits.max_tick_age_seconds
                ),
                max_wait_seconds=min(
                    remaining,
                    max(0.0, float(args.final_order_query_wait_seconds)),
                ),
                readiness_state=readiness_state,
                hard_deadline_monotonic=hard_deadline_monotonic,
            )
            blockers.extend(final_gate.get("blockers", []))
        conversion: dict[str, Any] = {}
        physical_requests: list[OrderRequest] = []
        open_funds_gate: dict[str, Any] = {}
        if not blockers:
            conversion = _final_offset_conversion(main_engine, rows, req)
            blockers.extend(conversion.get("blockers", []))
            physical_requests = list(conversion.get("requests", []))
            blockers.extend(
                _enforce_physical_order_time_in_force(physical_requests)
            )
            if not physical_requests:
                blockers.append("stage179_warm_executor_no_physical_order")
        if not blockers:
            has_open = any(
                request.offset == Offset.OPEN
                for request in physical_requests
            )
            if has_open:
                remaining = max(
                    0.0, hard_deadline_monotonic - time.monotonic()
                )
                acquired = state["ctp_query_lock"].acquire(
                    timeout=remaining
                )
                if not acquired:
                    open_funds_gate = {
                        "success": False,
                        "confirmed": False,
                        "status": "blocked",
                        "blockers": [
                            "stage179_execution_deadline_exceeded:"
                            "final_open_funds_query_lock"
                        ],
                        "query_api_called_count": 0,
                    }
                else:
                    try:
                        remaining = max(
                            0.0,
                            hard_deadline_monotonic - time.monotonic(),
                        )
                        open_funds_gate = _final_open_funds_margin_gate(
                            td_api,
                            rows,
                            physical_requests,
                            max_wait_seconds=min(
                                remaining,
                                max(
                                    0.0,
                                    float(
                                        args.final_order_query_wait_seconds
                                    ),
                                ),
                            ),
                            readiness_state=readiness_state,
                            hard_deadline_monotonic=(
                                hard_deadline_monotonic
                            ),
                        )
                    finally:
                        state["ctp_query_lock"].release()
            else:
                open_funds_gate = _final_open_funds_margin_gate(
                    td_api,
                    rows,
                    physical_requests,
                    max_wait_seconds=0.0,
                    readiness_state=readiness_state,
                    hard_deadline_monotonic=hard_deadline_monotonic,
                )
            blockers.extend(open_funds_gate.get("blockers", []))
            if open_funds_gate.get("confirmed"):
                final_gate["open_funds_gate"] = dict(open_funds_gate)
                final_gate["final_event_watermark_after_open_funds"] = dict(
                    open_funds_gate.get("event_watermark", {})
                )
            blockers.extend(
                _final_ctp_transport_blockers(
                    td_api, rows, readiness_state
                )
            )
        physical_batch_query_watermark = dict(
            final_gate.get("query_watermark", {})
        )
        if any(
            request.offset == Offset.OPEN
            for request in physical_requests
        ):
            funds_query_watermark = dict(
                open_funds_gate.get("query_watermark", {})
            )
            physical_batch_query_watermark = {
                "broker_id": str(
                    funds_query_watermark.get("broker_id", "") or ""
                ),
                "investor_id": str(
                    funds_query_watermark.get("investor_id", "") or ""
                ),
                "td_reqid_before_batch": _to_int(
                    funds_query_watermark.get("td_reqid_after"), -1
                ),
                "ctp_last_query_monotonic": (
                    funds_query_watermark.get(
                        "ctp_last_query_monotonic"
                    )
                ),
            }
        if not blockers:
            blockers.extend(
                _physical_batch_query_watermark_blockers(
                    td_api,
                    rows,
                    physical_batch_query_watermark,
                    owned_native_insert_count=0,
                )
            )
        blockers = list(dict.fromkeys(str(item) for item in blockers if str(item)))
        state["intent_contexts"][lease.intent.intent_id] = {
            "target_date": lease.intent.target_date,
            "intent_id": lease.intent.intent_id,
            "row": row,
            "request": (
                physical_requests[0] if not blockers else req
            ),
            "requests": (
                physical_requests if not blockers else []
            ),
            "fingerprint": str(reserve.get("intent_fingerprint", "")),
            "reservation_record_checksum": str(
                dict(reserve.get("latest_ledger_event", {})).get(
                    "record_checksum", ""
                )
            ),
            "intent_payload_sha256": lease.intent.payload_sha256,
            "intent_kind": lease.intent.intent_kind,
            "service_generation": lease.intent.lease_owner,
            "spool_lease_owner": lease.intent.lease_owner,
            "spool_lease_token": lease.lease_token,
            "connection_generation": str(state.get("connection_generation", "")),
            "close_submit_attempt_no": int(
                reserve.get("close_submit_attempt_no", 0) or 0
            ),
            "close_attempt_lease_token": str(
                reserve.get("close_attempt_lease_token", "") or ""
            ),
            "final_watermark": dict(
                open_funds_gate.get(
                    "event_watermark",
                    final_gate.get("final_event_watermark", {}),
                )
            ),
            "open_funds_gate": dict(open_funds_gate),
            "physical_batch_query_watermark": dict(
                physical_batch_query_watermark
            ),
            "hard_deadline_monotonic": float(hard_deadline_monotonic),
        }
        return {
            "blockers": blockers,
            "ledger_fingerprint": str(reserve.get("intent_fingerprint", "")),
        }

    def pre_api_slot_blockers(lease: Any) -> list[str]:
        context = state["intent_contexts"].get(lease.intent.intent_id, {})
        blockers = leased_authorization_blockers(lease)
        blockers.extend(_post_final_gate_pre_api_slot_blockers(
            state["rows"],
            dict(context.get("final_watermark", {})),
        ))
        blockers.extend(
            _open_funds_gate_consistency_blockers(
                state.get("td_api"),
                state["rows"],
                list(context.get("requests", [])),
                dict(context.get("open_funds_gate", {})),
            )
        )
        blockers.extend(
            _physical_batch_query_watermark_blockers(
                state.get("td_api"),
                state["rows"],
                dict(
                    context.get(
                        "physical_batch_query_watermark", {}
                    )
                ),
                owned_native_insert_count=0,
            )
        )
        for blocker in _kill_switch_blockers():
            blockers.append(f"{blocker}_before_api_slot")
        if not any(
            item.get("role") == "market_and_execution"
            for item in _current_phase_d_sessions()
        ):
            blockers.append("live_real_not_in_execution_session_before_api_slot")
        blockers.extend(_continuous_submit_blockers())
        row = dict(context.get("row", {}))
        blockers.extend(
            _execution_profile_intent_blockers(execution_profile, row)
        )
        requests = list(context.get("requests", []))
        request = context.get("request")
        if request is None or not requests:
            blockers.append("stage179_send_context_missing_before_api_slot")
        else:
            for child_request in requests:
                blockers.extend(
                    _pre_reserved_child_intent_blockers(row, child_request)
                )
            if (
                str(row.get("source", "")).strip()
                == "stage904_c9_intraday_retry_open"
                and _normalize_offset_text(request.offset.value) == "open"
            ):
                blockers.extend(
                    _stage904_retry_open_pre_send_blockers(
                        row,
                        target_date=lease.intent.target_date,
                        max_age_seconds=args.max_stage904_age_seconds,
                    )
                )
        return blockers

    def pre_api_slot_safe_terminal(
        lease: Any,
        blockers: list[str],
        blocked_phase: str,
    ) -> dict[str, Any]:
        context = state["intent_contexts"].get(lease.intent.intent_id, {})
        return _append_stage179_warm_pre_send_safe_terminal(
            lease=lease,
            context=context,
            blockers=blockers,
            ledger_path=paths.ledger_path,
            blocked_phase=blocked_phase,
        )

    def post_api_slot_safe_terminal(
        lease: Any,
        api_slot_batch_id: str,
        blockers: list[str],
        blocked_phase: str,
    ) -> dict[str, Any]:
        context = state["intent_contexts"].get(lease.intent.intent_id, {})
        identity = {
            "target_date": lease.intent.target_date,
            "intent_id": lease.intent.intent_id,
            "intent_payload_sha256": lease.intent.payload_sha256,
            "intent_kind": lease.intent.intent_kind,
            "intent_fingerprint": context.get("fingerprint", ""),
            "reservation_record_checksum": context.get(
                "reservation_record_checksum", ""
            ),
            "spool_lease_owner": lease.intent.lease_owner,
            "spool_lease_token": lease.lease_token,
            "close_submit_attempt_no": int(
                context.get("close_submit_attempt_no", 0) or 0
            ),
            "close_attempt_lease_token": str(
                context.get("close_attempt_lease_token", "") or ""
            ),
            **_intent_ledger_metadata(dict(context.get("row", {}))),
        }
        return append_post_api_slot_no_native_safe_terminal(
            identity=identity,
            api_slot_batch_id=api_slot_batch_id,
            blockers=blockers,
            blocked_phase=blocked_phase,
            path=paths.ledger_path,
        )

    def reserve_api_slot(lease: Any) -> str:
        context = state["intent_contexts"].get(lease.intent.intent_id, {})
        requests = list(context.get("requests", []))
        if not requests:
            return ""
        base_events: list[dict[str, Any]] = []
        for index, request in enumerate(requests):
            base_event = {
                "target_date": lease.intent.target_date,
                "intent_id": lease.intent.intent_id,
                "intent_payload_sha256": lease.intent.payload_sha256,
                "intent_kind": lease.intent.intent_kind,
                "intent_fingerprint": context.get("fingerprint", ""),
                "reservation_record_checksum": context.get(
                    "reservation_record_checksum", ""
                ),
                "parent_intent_fingerprint": context.get("fingerprint", ""),
                "vt_symbol": lease.intent.vt_symbol,
                "adapter": "Stage931Warm",
                "service_generation": lease.intent.lease_owner,
                "connection_generation": state.get("connection_generation", ""),
                "spool_lease_owner": lease.intent.lease_owner,
                "spool_lease_token": lease.lease_token,
                "child_order_id": (
                    f"{context.get('fingerprint', '')}:{index + 1}/{len(requests)}"
                ),
                "child_order_index": index,
                "child_order_count": len(requests),
                "child_order_offset": request.offset.value,
                "child_order_volume": float(request.volume),
            }
            if int(context.get("close_submit_attempt_no", 0)) > 0:
                base_event["close_submit_attempt_no"] = int(
                    context["close_submit_attempt_no"]
                )
                base_event["close_attempt_lease_token"] = str(
                    context.get("close_attempt_lease_token", "")
                )
            base_events.append(base_event)
        result = reserve_execution_api_slots(
            target_date=lease.intent.target_date,
            slot_type="send_order",
            daily_limit=build_phase_d_config().hard_limits.max_order_count_per_day,
            path=paths.ledger_path,
            base_events=base_events,
        )
        if not result.get("reserved"):
            blocker = str(
                result.get("blocker")
                or "send_order_api_slot_batch_reservation_failed"
            )
            context["api_slot_blocker"] = blocker
            append_execution_ledger_event(
                {
                    "event_type": "api_slot_reservation_blocked",
                    **base_events[0],
                    "target_date": lease.intent.target_date,
                    "api_slot_type": "send_order",
                    "api_slot_requested_count": len(base_events),
                    "api_slot_blocker": blocker,
                },
                path=paths.ledger_path,
            )
            return ""
        return str(result.get("api_slot_batch_id", ""))

    def schedule_residual_cancel(
        vt_orderid: str,
        child_context: dict[str, Any],
    ) -> None:
        """Cancel a GFD residual once the bounded fill window closes.

        EVENT_TRADE remains authoritative and is persisted before enqueue, so
        trades racing with or arriving after this cancel are still ledgered.
        """

        if child_context.get("cancel_worker_started"):
            return
        child_context["cancel_worker_started"] = 1
        cancel_worker_token = uuid.uuid4().hex
        child_context["cancel_worker_token"] = cancel_worker_token
        state["reconciliation_pending_order_ids"].add(vt_orderid)
        scheduled_engine = state.get("main_engine")
        scheduled_connection_generation = str(
            state.get("connection_generation", "")
        )

        def worker_once() -> None:
            def schedule_bounded_reconciliation_retry() -> bool:
                retries = int(
                    child_context.get("reconciliation_worker_retry_count", 0) or 0
                )
                if retries >= 1:
                    if not child_context.get(
                        "reconciliation_worker_retry_exhausted_recorded"
                    ):
                        state["transport_generation_invalidated"] = True
                        state["reconciliation_blockers"].append(
                            "stage179_cancel_reconciliation_retry_exhausted:"
                            f"{vt_orderid}"
                        )
                        revoke_readiness(
                            paths.readiness_path,
                            service_generation=service_generation,
                            reason=(
                                "cancel_reconciliation_retry_exhausted:"
                                f"{vt_orderid}"
                            ),
                        )
                        append_execution_ledger_event(
                            {
                                "event_type": (
                                    "cancel_reconciliation_retry_exhausted"
                                ),
                                "target_date": child_context.get(
                                    "target_date", ""
                                ),
                                "intent_id": child_context.get(
                                    "intent_id", ""
                                ),
                                "intent_fingerprint": child_context.get(
                                    "fingerprint", ""
                                ),
                                "child_order_id": child_context.get(
                                    "child_order_id", ""
                                ),
                                "vt_orderid": vt_orderid,
                                "connection_generation": (
                                    scheduled_connection_generation
                                ),
                                "reconciliation_worker_retry_count": retries,
                                "reconciliation_required": 1,
                            },
                            path=paths.ledger_path,
                        )
                        child_context[
                            "reconciliation_worker_retry_exhausted_recorded"
                        ] = 1
                    return False
                child_context["reconciliation_worker_retry_count"] = retries + 1
                child_context["cancel_worker_started"] = 0
                schedule_residual_cancel(vt_orderid, child_context)
                return True

            deadline = time.monotonic() + max(
                0.0,
                0.0
                if child_context.get("recovering_outstanding_order")
                else float(getattr(args, "fill_wait_seconds", 0.0)),
            )
            while time.monotonic() < deadline:
                latest = _latest_order(state["rows"]["orders"], vt_orderid)
                if latest and _status_is_terminal(latest.get("status")):
                    break
                time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))
            request = child_context.get("request")
            main_engine = state.get("main_engine")
            if (
                main_engine is not scheduled_engine
                or (
                    scheduled_connection_generation
                    and str(state.get("connection_generation", ""))
                    != scheduled_connection_generation
                )
            ):
                return
            if not isinstance(request, OrderRequest) or main_engine is None:
                state["reconciliation_blockers"].append(
                    "stage179_residual_cancel_context_missing"
                )
                return
            latest = _latest_order(state["rows"]["orders"], vt_orderid) or child_context.get(
                "recovery_order"
            )
            trade_totals, trade_totals_blocker = _unique_trade_callback_totals(
                state["rows"]["trades"], vt_orderid
            )
            if trade_totals_blocker:
                state["reconciliation_blockers"].append(trade_totals_blocker)
                return
            trade_volume = float(trade_totals["total_volume"])
            effective_traded = max(
                trade_volume,
                _to_float((latest or {}).get("traded"), 0.0),
            )
            residual = max(0.0, float(request.volume) - effective_traded)
            latest_terminal = bool(
                latest and _status_is_terminal(latest.get("status"))
            )
            durable_callback_priced, durable_fill_blocker = (
                _exact_durable_priced_volume(
                    read_execution_ledger(paths.ledger_path),
                    context=child_context,
                    vt_orderid=vt_orderid,
                )
            )
            if (
                latest_terminal
                and not durable_fill_blocker
                and not state.get("callback_persistence_blockers")
                and not state.get("transport_generation_invalidated")
                and durable_callback_priced + 1e-9 >= effective_traded
            ):
                _resolve_reconciliation_order(state, vt_orderid)
                return
            if (
                request.type == OrderType.FAK
                or latest_terminal
                or residual <= 1e-9
            ):
                append_execution_ledger_event(
                    {
                        "event_type": "fak_terminal_reconciliation_required",
                        "target_date": child_context.get("target_date", ""),
                        "intent_id": child_context.get("intent_id", ""),
                        "intent_fingerprint": child_context.get("fingerprint", ""),
                        "child_order_id": child_context.get("child_order_id", ""),
                        "vt_symbol": request.vt_symbol,
                        "vt_orderid": vt_orderid,
                        "residual_volume": residual,
                        "reconciliation_required": 1,
                    },
                    path=paths.ledger_path,
                )
                # FAK has no cancel duty, but callback loss must not leave an
                # order permanently unknown.  Perform one bounded, serialized
                # Order -> Trade -> Position query bundle in this exact
                # connection generation and fold only the owned order/trades.
                with state["ctp_query_lock"]:
                    order_query = _final_order_query_epoch(
                        state["td_api"],
                        state["rows"],
                        max_wait_seconds=max(
                            0.0, float(args.final_order_query_wait_seconds)
                        ),
                    )
                    trade_query = _final_trade_query_epoch(
                        state["td_api"],
                        state["rows"],
                        max_wait_seconds=max(
                            0.0, float(args.final_order_query_wait_seconds)
                        ),
                    )
                    position_query = _final_position_query_epoch(
                        state["td_api"],
                        state["rows"],
                        max_wait_seconds=max(
                            0.0, float(args.final_order_query_wait_seconds)
                        ),
                    )
                generation_still_current = bool(
                    state.get("main_engine") is scheduled_engine
                    and (
                        not scheduled_connection_generation
                        or str(state.get("connection_generation", ""))
                        == scheduled_connection_generation
                    )
                    and not state.get("transport_generation_invalidated")
                )
                query_blockers = [
                    *list(order_query.get("blockers", [])),
                    *list(trade_query.get("blockers", [])),
                    *list(position_query.get("blockers", [])),
                ]
                if not generation_still_current:
                    query_blockers.append(
                        "stage179_fak_reconciliation_generation_changed"
                    )
                if not (
                    order_query.get("confirmed")
                    and trade_query.get("confirmed")
                    and position_query.get("confirmed")
                    and generation_still_current
                ):
                    for blocker in (
                        query_blockers
                        or ["stage179_fak_reconciliation_query_bundle_incomplete"]
                    ):
                        state["reconciliation_blockers"].append(
                            f"{blocker}:{vt_orderid}"
                        )
                    schedule_bounded_reconciliation_retry()
                    return
                queried_order, identity_blocker = _match_reqid_bound_ctp_order(
                    list(order_query.get("orders", [])), vt_orderid
                )
                if queried_order is None:
                    state["reconciliation_blockers"].append(
                        f"stage179_fak_reconciliation_order_missing:{identity_blocker}:"
                        f"{vt_orderid}"
                    )
                    return
                for trade_row in trade_query.get("trades", []):
                    if (
                        trade_row.get("exchange")
                        == queried_order.get("exchange")
                        and trade_row.get("order_sys_id")
                        == queried_order.get("order_sys_id")
                    ):
                        _persist_stage179_warm_broker_callback(
                            kind="trade",
                            callback={
                                **trade_row,
                                "vt_orderid": vt_orderid,
                                "vt_symbol": queried_order.get("vt_symbol", ""),
                            },
                            context=child_context,
                            target_date=str(
                                child_context.get("target_date", "")
                            ),
                            ledger_path=paths.ledger_path,
                        )
                durable_priced, durable_fill_blocker = (
                    _exact_durable_priced_volume(
                        read_execution_ledger(paths.ledger_path),
                        context=child_context,
                        vt_orderid=vt_orderid,
                    )
                )
                if durable_fill_blocker:
                    state["reconciliation_blockers"].append(
                        f"{durable_fill_blocker}:{vt_orderid}"
                    )
                    return
                queried_traded = _to_float(queried_order.get("traded"), 0.0)
                query_terminal_identity = {
                    **_intent_ledger_metadata(
                        dict(child_context.get("row", {}))
                    ),
                    "target_date": child_context.get("target_date", ""),
                    "intent_id": child_context.get("intent_id", ""),
                    "intent_fingerprint": child_context.get("fingerprint", ""),
                    "spool_lease_owner": child_context.get(
                        "spool_lease_owner", ""
                    ),
                    "spool_lease_token": child_context.get(
                        "spool_lease_token", ""
                    ),
                    "vt_orderid": vt_orderid,
                    "child_order_index": int(
                        child_context.get("child_order_index", 0) or 0
                    ),
                    "child_order_count": int(
                        child_context.get("child_order_count", 1) or 1
                    ),
                    "vt_symbol": request.vt_symbol,
                    "direction": request.direction.value,
                    "offset": request.offset.value,
                    "close_submit_attempt_no": int(
                        child_context.get("close_submit_attempt_no", 0) or 0
                    ),
                    "order_identity": queried_order.get("order_identity", ""),
                    "raw_order_status": queried_order.get(
                        "raw_order_status", ""
                    ),
                    "traded": queried_traded,
                    "volume": _to_float(queried_order.get("volume"), 0.0),
                    "durable_priced_volume": durable_priced,
                    "connection_generation": scheduled_connection_generation,
                }
                fill_pending = bool(
                    queried_traded > durable_priced + 1e-9
                )
                if queried_order.get("status_class") == "terminal":
                    append_broker_callback_event_once(
                        {
                            "event_type": "broker_order_query_terminal_observed",
                            **query_terminal_identity,
                            "broker_callback_key": _stage179_callback_key(
                                "order-query-terminal",
                                query_terminal_identity,
                            ),
                            "fill_price_reconciliation_pending": int(
                                fill_pending
                            ),
                        },
                        paths.ledger_path,
                    )
                    if not fill_pending:
                        _resolve_reconciliation_order(state, vt_orderid)
                        return
                state["reconciliation_blockers"].append(
                    f"stage179_fak_terminal_or_priced_fill_unresolved:{vt_orderid}"
                )
                return
            cancel_duty_identity = {
                "target_date": child_context.get("target_date", ""),
                "vt_orderid": vt_orderid,
                "child_order_id": child_context.get("child_order_id", ""),
                "intent_fingerprint": child_context.get("fingerprint", ""),
                "spool_lease_owner": child_context.get("spool_lease_owner", ""),
                "spool_lease_token": child_context.get("spool_lease_token", ""),
                "close_submit_attempt_no": int(
                    child_context.get("close_submit_attempt_no", 0) or 0
                ),
            }
            cancel_duty_key = _stage179_callback_key(
                "cancel-duty", cancel_duty_identity
            )
            cancel_duty_event_identity = {
                **cancel_duty_identity,
                "connection_generation": scheduled_connection_generation,
                "cancel_duty_generation": 1,
            }
            cancel_duty_owner = (
                f"{os.getpid()}:{scheduled_connection_generation}:"
                f"{child_context.get('service_generation', '')}"
            )
            duty = advance_cancel_duty_state(
                target_date=str(child_context.get("target_date", "")),
                duty_key=cancel_duty_key,
                expected_states=("",),
                next_state="reserved",
                owner_id=cancel_duty_owner,
                lease_seconds=5,
                event=cancel_duty_event_identity,
                path=paths.ledger_path,
            )
            duty_row = dict(duty.get("ledger_event", {}))
            duty_state = str(duty_row.get("cancel_duty_state", "") or "")
            if not duty.get("advanced") and duty_state == "query_reconciled":
                _resolve_reconciliation_order(state, vt_orderid)
                return
            if not duty.get("advanced") and duty_state == "reserved":
                # A different process may take over only after its lease
                # expires and a fresh same-generation query proves the order
                # is still active.
                with state["ctp_query_lock"]:
                    takeover_query = _final_order_query_epoch(
                        state["td_api"],
                        state["rows"],
                        max_wait_seconds=max(
                            0.0, float(args.final_order_query_wait_seconds)
                        ),
                    )
                takeover_order, _ = _match_reqid_bound_ctp_order(
                    list(takeover_query.get("orders", [])), vt_orderid
                )
                if not (
                    takeover_query.get("confirmed")
                    and takeover_order is not None
                    and takeover_order.get("status_class") == "active"
                ):
                    state["reconciliation_blockers"].append(
                        f"stage179_cancel_duty_takeover_active_proof_missing:{vt_orderid}"
                    )
                    schedule_bounded_reconciliation_retry()
                    return
                duty = advance_cancel_duty_state(
                    target_date=str(child_context.get("target_date", "")),
                    duty_key=cancel_duty_key,
                    expected_states=("reserved",),
                    next_state="reserved",
                    owner_id=cancel_duty_owner,
                    lease_seconds=5,
                    event={
                        **cancel_duty_event_identity,
                        "cancel_duty_generation": int(
                            duty_row.get("cancel_duty_generation", 1) or 1
                        ),
                        "vt_orderid": vt_orderid,
                        "cancel_duty_takeover_active_query_reqid": takeover_query.get(
                            "reqid", ""
                        ),
                    },
                    allow_expired_takeover=True,
                    path=paths.ledger_path,
                )
                duty_row = dict(duty.get("ledger_event", {}))
            elif not duty.get("advanced") and duty_state in {"api_called", "api_returned"}:
                # Native cancel may already have happened.  Never call it
                # again; proceed directly to the exact O/T/P fold below.
                pass
            elif not duty.get("advanced"):
                state["reconciliation_blockers"].append(
                    f"{duty.get('blocker') or 'stage179_cancel_duty_reserve_failed'}:{vt_orderid}"
                )
                schedule_bounded_reconciliation_retry()
                return

            cancel_duty_generation = int(
                duty_row.get("cancel_duty_generation", 1) or 1
            )

            cancel_api_may_have_been_called = duty_state in {
                "api_called", "api_returned"
            }
            if not cancel_api_may_have_been_called:
                existing_slot = next(
                    (
                        row
                        for row in reversed(read_execution_ledger(paths.ledger_path))
                        if row.get("event_type") == "api_slot_reserved"
                        and row.get("api_slot_type") == "cancel_order"
                        and row.get("cancel_duty_key") == cancel_duty_key
                        and int(row.get("cancel_duty_generation", 1) or 1)
                        == cancel_duty_generation
                    ),
                    None,
                )
                cancel_slot = (
                    {"reserved": True, "ledger_event": existing_slot}
                    if existing_slot is not None
                    else reserve_execution_api_slot(
                        target_date=str(child_context.get("target_date", "")),
                        slot_type="cancel_order",
                        daily_limit=build_phase_d_config().hard_limits.max_cancel_count_per_day,
                        path=paths.ledger_path,
                        base_event={
                            "intent_id": child_context.get("intent_id", ""),
                            "intent_fingerprint": child_context.get("fingerprint", ""),
                            "child_order_id": child_context.get("child_order_id", ""),
                            "child_order_index": int(
                                child_context.get("child_order_index", 0) or 0
                            ),
                            "child_order_count": int(
                                child_context.get("child_order_count", 1) or 1
                            ),
                            "vt_orderid": vt_orderid,
                            "cancel_duty_key": cancel_duty_key,
                            "cancel_duty_generation": cancel_duty_generation,
                        },
                    )
                )
                if not cancel_slot.get("reserved"):
                    state["reconciliation_blockers"].append(
                        f"{cancel_slot.get('blocker') or 'stage179_residual_cancel_slot_blocked'}:{vt_orderid}"
                    )
                    return
            child_context["cancel_requested_epoch_ns"] = time.time_ns()
            cancel_event = {
                "event_type": "cancel_order_called",
                "target_date": child_context.get("target_date", ""),
                "intent_id": child_context.get("intent_id", ""),
                "intent_payload_sha256": child_context.get("intent_payload_sha256", ""),
                "intent_kind": child_context.get("intent_kind", ""),
                "intent_fingerprint": child_context.get("fingerprint", ""),
                "parent_intent_fingerprint": child_context.get("fingerprint", ""),
                "vt_symbol": request.vt_symbol,
                "vt_orderid": vt_orderid,
                "direction": request.direction.value,
                "offset": request.offset.value,
                "volume": float(request.volume),
                "traded_volume_before_cancel": effective_traded,
                "residual_volume_before_cancel": residual,
                "adapter": "Stage931Warm",
                "service_generation": child_context.get("service_generation", ""),
                "connection_generation": child_context.get("connection_generation", ""),
                "child_order_id": child_context.get("child_order_id", ""),
                "child_order_index": child_context.get("child_order_index", 0),
                "child_order_count": child_context.get("child_order_count", 1),
            }
            cancel_api_accepted = bool(
                duty_state == "api_returned"
                and _to_int(duty_row.get("cancel_api_accepted"), 0) == 1
            )
            if not cancel_api_may_have_been_called:
                called = advance_cancel_duty_state(
                    target_date=str(child_context.get("target_date", "")),
                    duty_key=cancel_duty_key,
                    expected_states=("reserved",),
                    next_state="api_called",
                    owner_id=cancel_duty_owner,
                    lease_seconds=5,
                    event=cancel_event,
                    path=paths.ledger_path,
                )
                if not called.get("advanced"):
                    state["reconciliation_blockers"].append(
                        f"{called.get('blocker') or 'stage179_cancel_duty_api_called_cas_failed'}:{vt_orderid}"
                    )
                    schedule_bounded_reconciliation_retry()
                    return
                append_execution_ledger_event(cancel_event, path=paths.ledger_path)
                _, _, orderid = vt_orderid.partition(".")
                action_audits: list[dict[str, Any]] = []
                try:
                    with state["ctp_query_lock"]:
                        action_start_index = len(
                            state["rows"]["order_action_requests"]
                        )
                        main_engine.cancel_order(
                            CancelRequest(
                                orderid=orderid,
                                symbol=request.symbol,
                                exchange=request.exchange,
                            ),
                            "CTP",
                        )
                        action_audits = list(
                            state["rows"]["order_action_requests"][
                                action_start_index:
                            ]
                        )
                except BaseException as exc:
                    state["reconciliation_blockers"].append(
                        f"stage179_residual_cancel_exception:{type(exc).__name__}:{vt_orderid}"
                    )
                    schedule_bounded_reconciliation_retry()
                    return
                action_audit = action_audits[0] if len(action_audits) == 1 else {}
                action_ret = pd.to_numeric(
                    action_audit.get("request_ret"), errors="coerce"
                )
                cancel_api_accepted = bool(
                    len(action_audits) == 1
                    and not action_audit.get("exception")
                    and not pd.isna(action_ret)
                    and int(action_ret) == 0
                )
                returned_event = {
                    **cancel_event,
                    "cancel_submit_attempt_no": cancel_duty_generation,
                    "req_order_action_audit_row_count": len(action_audits),
                    "req_order_action_reqid": action_audit.get("reqid", ""),
                    "req_order_action_request_ret": (
                        "" if pd.isna(action_ret) else int(action_ret)
                    ),
                    "req_order_action_exception": str(
                        action_audit.get("exception", "") or ""
                    ),
                    "cancel_api_accepted": int(cancel_api_accepted),
                }
                advance_cancel_duty_state(
                    target_date=str(child_context.get("target_date", "")),
                    duty_key=cancel_duty_key,
                    expected_states=("api_called",),
                    next_state="api_returned",
                    owner_id=cancel_duty_owner,
                    lease_seconds=5,
                    event=returned_event,
                    path=paths.ledger_path,
                )
                append_execution_ledger_event(
                    {**returned_event, "event_type": "cancel_order_api_returned"},
                    path=paths.ledger_path,
                )
            if not cancel_api_accepted:
                state["reconciliation_blockers"].append(
                    f"stage179_cancel_api_not_accepted:{vt_orderid}"
                )
            cancel_deadline = time.monotonic() + max(
                0.0,
                float(getattr(args, "post_cancel_wait_seconds", 0.0))
                if cancel_api_accepted
                else 0.0,
            )
            while time.monotonic() < cancel_deadline:
                latest = _latest_order(state["rows"]["orders"], vt_orderid)
                if latest and _status_is_terminal(latest.get("status")):
                    # Terminal ORDER is not priced-fill authority.  Continue
                    # into the serialized O/T/P fold below; only exact fsynced
                    # EVENT_TRADE volume may clear the pending order.
                    break
                time.sleep(
                    min(0.05, max(0.0, cancel_deadline - time.monotonic()))
                )
            with state["ctp_query_lock"]:
                order_query = _final_order_query_epoch(
                    state["td_api"], state["rows"],
                    max_wait_seconds=max(0.0, float(args.final_order_query_wait_seconds)),
                )
                trade_query = _final_trade_query_epoch(
                    state["td_api"], state["rows"],
                    max_wait_seconds=max(0.0, float(args.final_order_query_wait_seconds)),
                )
                position_query = _final_position_query_epoch(
                    state["td_api"], state["rows"],
                    max_wait_seconds=max(0.0, float(args.final_order_query_wait_seconds)),
                )
            if (
                order_query.get("confirmed")
                and trade_query.get("confirmed")
                and position_query.get("confirmed")
            ):
                queried_order, _ = _match_reqid_bound_ctp_order(
                    list(order_query.get("orders", [])), vt_orderid
                )
                if queried_order is not None:
                    for trade_row in trade_query.get("trades", []):
                        if (
                            trade_row.get("exchange") == queried_order.get("exchange")
                            and trade_row.get("order_sys_id") == queried_order.get("order_sys_id")
                        ):
                            _persist_stage179_warm_broker_callback(
                                kind="trade",
                                callback={
                                    **trade_row,
                                    "vt_orderid": vt_orderid,
                                    "vt_symbol": queried_order.get("vt_symbol", ""),
                                },
                                context=child_context,
                                target_date=str(child_context.get("target_date", "")),
                                ledger_path=paths.ledger_path,
                            )
                    durable_priced, durable_fill_blocker = (
                        _exact_durable_priced_volume(
                            read_execution_ledger(paths.ledger_path),
                            context=child_context,
                            vt_orderid=vt_orderid,
                        )
                    )
                    if durable_fill_blocker:
                        state["reconciliation_blockers"].append(
                            f"{durable_fill_blocker}:{vt_orderid}"
                        )
                        schedule_bounded_reconciliation_retry()
                        return
                    if (
                        queried_order.get("status_class") == "terminal"
                        and durable_priced + 1e-9
                        >= _to_float(queried_order.get("traded"), 0.0)
                    ):
                        terminal_identity = {
                            **_intent_ledger_metadata(
                                dict(child_context.get("row", {}))
                            ),
                            "target_date": child_context.get("target_date", ""),
                            "intent_id": child_context.get("intent_id", ""),
                            "intent_fingerprint": child_context.get("fingerprint", ""),
                            "spool_lease_owner": child_context.get("spool_lease_owner", ""),
                            "spool_lease_token": child_context.get("spool_lease_token", ""),
                            "child_order_id": child_context.get("child_order_id", ""),
                            "child_order_index": int(
                                child_context.get("child_order_index", 0) or 0
                            ),
                            "child_order_count": int(
                                child_context.get("child_order_count", 1) or 1
                            ),
                            "vt_orderid": vt_orderid,
                            "vt_symbol": request.vt_symbol,
                            "direction": request.direction.value,
                            "offset": request.offset.value,
                            "close_submit_attempt_no": int(
                                child_context.get("close_submit_attempt_no", 0) or 0
                            ),
                            "order_identity": queried_order.get("order_identity", ""),
                            "raw_order_status": queried_order.get("raw_order_status", ""),
                            "traded": _to_float(queried_order.get("traded"), 0.0),
                            "volume": _to_float(queried_order.get("volume"), 0.0),
                            "durable_priced_volume": durable_priced,
                            "connection_generation": scheduled_connection_generation,
                        }
                        terminal_result = append_broker_callback_event_once(
                            {
                                "event_type": "broker_order_query_terminal_observed",
                                **terminal_identity,
                                "broker_callback_key": _stage179_callback_key(
                                    "order-query-terminal", terminal_identity
                                ),
                                "fill_price_reconciliation_pending": 0,
                            },
                            paths.ledger_path,
                        )
                        if terminal_result.get("blocker"):
                            state["reconciliation_blockers"].append(
                                f"{terminal_result['blocker']}:{vt_orderid}"
                            )
                            return
                        reconciled = advance_cancel_duty_state(
                            target_date=str(child_context.get("target_date", "")),
                            duty_key=cancel_duty_key,
                            expected_states=("reserved", "api_called", "api_returned"),
                            next_state="query_reconciled",
                            owner_id=str(
                                duty_row.get("cancel_duty_owner_id")
                                or cancel_duty_owner
                            ),
                            lease_seconds=5,
                            event={
                                **cancel_duty_event_identity,
                                "vt_orderid": vt_orderid,
                                "query_order_reqid": order_query.get("reqid", ""),
                                "query_trade_reqid": trade_query.get("reqid", ""),
                                "query_position_reqid": position_query.get("reqid", ""),
                                "durable_priced_volume": durable_priced,
                            },
                            path=paths.ledger_path,
                        )
                        if not (
                            reconciled.get("advanced")
                            or reconciled.get("idempotent_replay")
                        ):
                            state["reconciliation_blockers"].append(
                                f"{reconciled.get('blocker') or 'stage179_cancel_duty_reconcile_cas_failed'}:{vt_orderid}"
                            )
                            schedule_bounded_reconciliation_retry()
                            return
                        _resolve_reconciliation_order(state, vt_orderid)
                        return
                    if (
                        queried_order.get("status_class") == "active"
                        and duty_state in {"api_called", "api_returned"}
                        and cancel_duty_generation < 2
                        and (
                            duty_state == "api_called"
                            or not cancel_api_accepted
                        )
                    ):
                        retry_duty = advance_cancel_duty_state(
                            target_date=str(child_context.get("target_date", "")),
                            duty_key=cancel_duty_key,
                            expected_states=(duty_state,),
                            next_state="reserved",
                            owner_id=cancel_duty_owner,
                            lease_seconds=5,
                            event={
                                **cancel_duty_event_identity,
                                "cancel_duty_generation": cancel_duty_generation + 1,
                                "cancel_retry_reason": (
                                    "api_called_outcome_unknown_order_still_active"
                                    if duty_state == "api_called"
                                    else "api_not_accepted_order_still_active"
                                ),
                                "cancel_retry_active_query_reqid": order_query.get(
                                    "reqid", ""
                                ),
                            },
                            allow_expired_takeover=True,
                            path=paths.ledger_path,
                        )
                        if retry_duty.get("advanced"):
                            child_context["cancel_worker_started"] = 0
                            child_context["reconciliation_worker_retry_count"] = 0
                            schedule_bounded_reconciliation_retry()
                            return
            append_execution_ledger_event(
                {
                    **cancel_event,
                    "event_type": "cancel_terminal_reconciliation_required",
                    "reconciliation_required": 1,
                },
                path=paths.ledger_path,
            )
            schedule_bounded_reconciliation_retry()

        def worker() -> None:
            try:
                worker_once()
            except BaseException as exc:
                try:
                    append_execution_ledger_event(
                        {
                            "event_type": "cancel_duty_worker_crashed",
                            "target_date": child_context.get("target_date", ""),
                            "intent_id": child_context.get("intent_id", ""),
                            "intent_fingerprint": child_context.get("fingerprint", ""),
                            "child_order_id": child_context.get("child_order_id", ""),
                            "vt_orderid": vt_orderid,
                            "connection_generation": scheduled_connection_generation,
                            "exception_type": type(exc).__name__,
                            "reconciliation_required": 1,
                        },
                        path=paths.ledger_path,
                    )
                except BaseException:
                    pass
                state["transport_generation_invalidated"] = True
                state["reconciliation_blockers"].append(
                    f"stage179_cancel_duty_worker_crashed:{type(exc).__name__}:{vt_orderid}"
                )
                child_context["cancel_worker_started"] = 0
                retries = int(
                    child_context.get("reconciliation_worker_retry_count", 0) or 0
                )
                if retries < 1:
                    child_context["reconciliation_worker_retry_count"] = retries + 1
                    schedule_residual_cancel(vt_orderid, child_context)
            finally:
                if child_context.get("cancel_worker_token") == cancel_worker_token:
                    child_context["cancel_worker_started"] = 0

        Thread(
            target=worker,
            name=f"stage179-cancel-{vt_orderid}",
            daemon=True,
        ).start()

    def _send_order_batch_locked(lease: Any) -> BrokerSendBatchResult:
        context = state["intent_contexts"].get(lease.intent.intent_id, {})
        requests = list(context.get("requests", []))
        main_engine = state.get("main_engine")
        if not requests or main_engine is None:
            raise RuntimeError("stage179_send_context_missing")
        order_ids: list[str] = []

        def dynamic_child_blockers(
            child_request: OrderRequest,
            *,
            native_td_api: Any | None = None,
            native_request: Mapping[str, Any] | None = None,
            native_reqid: int | None = None,
        ) -> list[str]:
            blockers = leased_authorization_blockers(
                lease, child_offset=child_request.offset.value
            )
            if "hard_deadline_monotonic" not in context:
                # Direct unit harnesses predating the production fresh-bundle
                # contract still exercise authorization revocation only.
                return blockers
            deadline = float(context.get("hard_deadline_monotonic", 0.0) or 0.0)
            if deadline <= 0 or time.monotonic() >= deadline:
                blockers.append("stage179_execution_deadline_exceeded:child_send")
            blockers.extend(
                f"{item}_before_child_send" for item in _kill_switch_blockers()
            )
            batch = state.get("active_physical_batch")
            native_insert_count = 0
            if isinstance(batch, dict):
                native_insert_count = _to_int(
                    batch.get("native_insert_count"), 0
                )
                blockers.extend(
                    _advance_physical_batch_event_baseline(
                        state,
                        batch,
                        ledger_path=paths.ledger_path,
                    )
                )
            else:
                blockers.extend(
                    _post_final_gate_pre_api_slot_blockers(
                        state["rows"],
                        dict(context.get("final_watermark", {})),
                    )
                )
            expected_owned_count = native_insert_count + int(
                native_reqid is not None
            )
            if isinstance(batch, dict):
                blockers.extend(
                    _physical_batch_query_watermark_blockers(
                        state.get("td_api"),
                        state["rows"],
                        dict(batch.get("query_watermark", {})),
                        owned_native_insert_count=expected_owned_count,
                    )
                )
            blockers.extend(
                _open_funds_gate_consistency_blockers(
                    state.get("td_api"),
                    state["rows"],
                    list(context.get("requests", [])),
                    dict(context.get("open_funds_gate", {})),
                    owned_native_insert_count=expected_owned_count,
                    owned_event_watermark=(
                        dict(batch.get("event_watermark", {}))
                        if isinstance(batch, dict)
                        else None
                    ),
                )
            )
            if native_reqid is not None:
                if native_td_api is None or native_request is None:
                    blockers.append(
                        "physical_batch_native_gate_arguments_missing"
                    )
                else:
                    if _to_int(
                        getattr(native_td_api, "reqid", -1), -1
                    ) != int(native_reqid):
                        blockers.append(
                            "physical_batch_native_reqid_argument_mismatch"
                        )
                    blockers.extend(
                        _native_insert_request_blockers(
                            native_td_api,
                            state.get("td_api"),
                            native_request,
                            child_request,
                        )
                    )
            if not any(
                item.get("role") == "market_and_execution"
                for item in _current_phase_d_sessions()
            ):
                blockers.append("live_real_not_in_execution_session_before_child_send")
            blockers.extend(_continuous_submit_blockers())
            blockers.extend(transport_probe())
            blockers.extend(
                _pre_reserved_child_intent_blockers(
                    dict(context.get("row", {})), child_request
                )
            )
            return list(dict.fromkeys(str(item) for item in blockers if str(item)))

        for index, request in enumerate(requests):
            child_context = {
                **context,
                "request": request,
                "child_order_id": (
                    f"{context.get('fingerprint', '')}:{index + 1}/{len(requests)}"
                ),
                "child_order_index": index,
                "child_order_count": len(requests),
                "child_order_offset": request.offset.value,
                "child_order_volume": float(request.volume),
            }
            # The vn.py callback may race ahead of send_order's return.  Keep
            # the currently entering child bound by the request reference;
            # once vt_orderid is known the durable per-order map is authority.
            state["intent_contexts"][lease.intent.intent_id] = child_context
            child_authorization_blockers = dynamic_child_blockers(request)
            if child_authorization_blockers:
                append_execution_ledger_event(
                    {
                        "event_type": "submit_authorization_blocked_before_child_send",
                        "target_date": lease.intent.target_date,
                        "intent_id": lease.intent.intent_id,
                        "intent_fingerprint": context.get("fingerprint", ""),
                        "vt_symbol": lease.intent.vt_symbol,
                        "adapter": "Stage931Warm",
                        "blockers": child_authorization_blockers,
                        "send_order_call_count": len(order_ids),
                        "child_order_index": index,
                        "child_order_count": len(requests),
                        "reconciliation_required": int(bool(order_ids)),
                    },
                    path=paths.ledger_path,
                )
                raise BrokerSendBatchError(
                    "stage179_submit_authorization_blocked_before_child_send",
                    send_order_call_count=len(order_ids),
                )
            send_base = {
                "target_date": lease.intent.target_date,
                "intent_id": lease.intent.intent_id,
                "intent_payload_sha256": lease.intent.payload_sha256,
                "intent_kind": lease.intent.intent_kind,
                "intent_fingerprint": context.get("fingerprint", ""),
                "parent_intent_fingerprint": context.get("fingerprint", ""),
                "vt_symbol": lease.intent.vt_symbol,
                "symbol": str(getattr(request, "symbol", "")),
                "exchange": str(
                    getattr(getattr(request, "exchange", ""), "value", getattr(request, "exchange", ""))
                ),
                "direction": str(
                    getattr(getattr(request, "direction", ""), "value", getattr(request, "direction", ""))
                ),
                "offset": str(
                    getattr(getattr(request, "offset", ""), "value", getattr(request, "offset", ""))
                ),
                "order_type": str(
                    getattr(getattr(request, "type", ""), "value", getattr(request, "type", ""))
                ),
                "price": float(getattr(request, "price", 0.0)),
                "volume": float(getattr(request, "volume", 0.0)),
                "reference": str(getattr(request, "reference", "")),
                "adapter": "Stage931Warm",
                "service_generation": lease.intent.lease_owner,
                "connection_generation": state.get("connection_generation", ""),
                "spool_lease_owner": lease.intent.lease_owner,
                "spool_lease_token": lease.lease_token,
                "child_order_id": child_context["child_order_id"],
                "child_order_index": index,
                "child_order_count": len(requests),
                "child_order_offset": request.offset.value,
                "child_order_volume": float(request.volume),
                **_intent_ledger_metadata(dict(context.get("row", {}))),
            }
            if int(context.get("close_submit_attempt_no", 0)) > 0:
                send_base["close_submit_attempt_no"] = int(
                    context["close_submit_attempt_no"]
                )
                send_base["close_attempt_lease_token"] = str(
                    context.get("close_attempt_lease_token", "")
                )
            insert_start_index = len(state["rows"]["order_insert_requests"])
            state.pop("native_insert_identity", None)
            state["native_insert_context"] = dict(send_base)
            state["native_child_context"] = child_context
            try:
                native_blockers = dynamic_child_blockers(request)
                if native_blockers:
                    append_execution_ledger_event(
                        {
                            "event_type": "child_dynamic_gate_blocked_before_native_insert",
                            **send_base,
                            "blockers": native_blockers,
                            "send_order_call_count": len(order_ids),
                            "reconciliation_required": int(bool(order_ids)),
                        },
                        path=paths.ledger_path,
                    )
                    raise BrokerSendBatchError(
                        "stage179_child_dynamic_gate_blocked_before_native_insert",
                        send_order_call_count=len(order_ids),
                    )
                with state["ctp_query_lock"]:
                    locked_blockers = dynamic_child_blockers(request)
                    if locked_blockers:
                        append_execution_ledger_event(
                            {
                                "event_type": "child_dynamic_gate_blocked_inside_native_lock",
                                **send_base,
                                "blockers": locked_blockers,
                                "send_order_call_count": len(order_ids),
                                "reconciliation_required": int(bool(order_ids)),
                                "native_api_called": 0,
                            },
                            path=paths.ledger_path,
                        )
                        raise BrokerSendBatchError(
                            "stage179_child_dynamic_gate_blocked_inside_native_lock",
                            send_order_call_count=len(order_ids),
                        )
                    append_execution_ledger_event(
                        {
                            "event_type": "send_order_called",
                            **send_base,
                            "send_order_called": 1,
                            "native_identity_protocol_version": (
                                "stage179_preinsert_v1"
                            ),
                            "native_api_called": 0,
                        },
                        path=paths.ledger_path,
                    )
                    state["native_prior_send_order_call_count"] = len(order_ids)
                    state["native_dynamic_gate"] = (
                        lambda native_td_api, native_request, native_reqid,
                        req=request: dynamic_child_blockers(
                            req,
                            native_td_api=native_td_api,
                            native_request=native_request,
                            native_reqid=native_reqid,
                        )
                    )
                    vt_orderid = str(main_engine.send_order(request, "CTP") or "")
                    batch = state.get("active_physical_batch")
                    if isinstance(batch, dict):
                        batch["native_insert_count"] = index + 1
            except BrokerSendBatchError:
                raise
            except BaseException as exc:
                audit_append_error = ""
                try:
                    append_execution_ledger_event(
                        {
                            "event_type": "adapter_exception_after_send",
                            "target_date": lease.intent.target_date,
                            "intent_id": lease.intent.intent_id,
                            "intent_fingerprint": context.get("fingerprint", ""),
                            "vt_symbol": lease.intent.vt_symbol,
                            "adapter": "Stage931Warm",
                            "exception_type": type(exc).__name__,
                            "send_order_call_count": len(order_ids) + 1,
                            "service_generation": lease.intent.lease_owner,
                            "connection_generation": state.get(
                                "connection_generation", ""
                            ),
                            "spool_lease_owner": lease.intent.lease_owner,
                            "spool_lease_token": lease.lease_token,
                            "child_order_index": index,
                            "child_order_count": len(requests),
                        },
                        path=paths.ledger_path,
                    )
                except BaseException as audit_exc:
                    audit_append_error = (
                        f":audit_append_failed:{type(audit_exc).__name__}"
                    )
                raise BrokerSendBatchError(
                    "stage179_broker_send_batch_exception:"
                    f"{type(exc).__name__}{audit_append_error}",
                    send_order_call_count=len(order_ids) + 1,
                ) from exc
            finally:
                state.pop("native_insert_context", None)
                state.pop("native_child_context", None)
                state.pop("native_dynamic_gate", None)
                state.pop("native_prior_send_order_call_count", None)
            post_native_call_count = len(order_ids) + 1
            try:
                native_identity = state.pop("native_insert_identity", None)
                expected_native_vt_orderid = (
                    str(native_identity.get("vt_orderid", "") or "")
                    if isinstance(native_identity, dict)
                    else ""
                )
                if (
                    not expected_native_vt_orderid
                    or not vt_orderid
                    or vt_orderid != expected_native_vt_orderid
                ):
                    append_execution_ledger_event(
                        {
                            "event_type": "native_order_identity_return_mismatch",
                            **send_base,
                            "native_expected_vt_orderid": expected_native_vt_orderid,
                            "send_order_returned_vt_orderid": vt_orderid,
                            "reconciliation_required": 1,
                        },
                        path=paths.ledger_path,
                    )
                    raise BrokerSendBatchError(
                        "stage179_native_order_identity_return_mismatch",
                        send_order_call_count=post_native_call_count,
                    )

                # The exact native identity proves that reqOrderInsert already
                # happened.  Account for that side effect before any audit
                # folding, callback rebinding, or cancel-worker scheduling can
                # fail; callers must never classify such failures as a
                # no-native retry.
                order_ids.append(vt_orderid)
                state["order_contexts"][vt_orderid] = child_context
                state["reconciliation_pending_order_ids"].add(vt_orderid)
                insert_audit = _req_order_insert_audit_since(
                    state["rows"], insert_start_index
                )
                child_context["insert_audit"] = insert_audit
                returned_event = {
                    "event_type": "send_order_returned",
                    **send_base,
                    "vt_orderid": vt_orderid,
                    "send_order_called": 1,
                    **insert_audit,
                }
                append_execution_ledger_event(
                    returned_event, path=paths.ledger_path
                )
                # Rebind callbacks which arrived before send_order returned.
                for callback_kind, row_key in (
                    ("order", "orders"),
                    ("trade", "trades"),
                ):
                    for callback_row in state["rows"][row_key]:
                        if str(callback_row.get("vt_orderid", "")) != vt_orderid:
                            continue
                        _persist_stage179_warm_broker_callback(
                            kind=callback_kind,
                            callback=callback_row,
                            context=child_context,
                            target_date=lease.intent.target_date,
                            ledger_path=paths.ledger_path,
                        )
                schedule_residual_cancel(vt_orderid, child_context)
            except BrokerSendBatchError as exc:
                if exc.send_order_call_count >= post_native_call_count:
                    raise
                raise BrokerSendBatchError(
                    str(exc), send_order_call_count=post_native_call_count
                ) from exc
            except BaseException as exc:
                audit_append_error = ""
                try:
                    append_execution_ledger_event(
                        {
                            "event_type": "adapter_exception_after_native_return",
                            **send_base,
                            "vt_orderid": vt_orderid,
                            "exception_type": type(exc).__name__,
                            "send_order_call_count": post_native_call_count,
                            "reconciliation_required": 1,
                        },
                        path=paths.ledger_path,
                    )
                except BaseException as audit_exc:
                    audit_append_error = (
                        f":audit_append_failed:{type(audit_exc).__name__}"
                    )
                raise BrokerSendBatchError(
                    "stage179_post_native_processing_failed:"
                    f"{type(exc).__name__}{audit_append_error}",
                    send_order_call_count=post_native_call_count,
                ) from exc
        return BrokerSendBatchResult(
            order_ids=tuple(order_ids),
            send_order_call_count=len(order_ids),
        )

    def send_order(lease: Any) -> BrokerSendBatchResult:
        """Hold one CTP lock and one causal baseline for the whole batch."""

        if not callable(schedule_residual_cancel):
            raise BrokerSendBatchError(
                "stage179_physical_batch_cancel_scheduler_missing",
                send_order_call_count=0,
            )
        context = state["intent_contexts"].get(
            lease.intent.intent_id, {}
        )
        strict_batch = "hard_deadline_monotonic" in context
        with state["ctp_query_lock"]:
            if not strict_batch:
                # Compatibility for isolated accounting/authorization
                # harnesses. Production fresh_bundle always supplies the
                # strict batch fields below.
                return _send_order_batch_locked(lease)
            if state.get("active_physical_batch") is not None:
                raise BrokerSendBatchError(
                    "stage179_physical_batch_reentry_forbidden",
                    send_order_call_count=0,
                )
            batch = {
                "batch_id": _canonical_evidence_sha256(
                    {
                        "intent_id": lease.intent.intent_id,
                        "fingerprint": context.get("fingerprint", ""),
                        "lease_token": lease.lease_token,
                        "connection_generation": state.get(
                            "connection_generation", ""
                        ),
                    }
                ),
                "target_date": lease.intent.target_date,
                "intent_id": lease.intent.intent_id,
                "fingerprint": context.get("fingerprint", ""),
                "query_watermark": dict(
                    context.get("physical_batch_query_watermark", {})
                ),
                "event_watermark": dict(
                    context.get("final_watermark", {})
                ),
                "order_row_index": len(state["rows"].get("orders", [])),
                "trade_row_index": len(state["rows"].get("trades", [])),
                "native_insert_count": 0,
                "owned_children": {},
                "attributed_events": [],
            }
            try:
                append_execution_ledger_event(
                    {
                        "event_type": "physical_batch_lock_acquired",
                        "target_date": batch["target_date"],
                        "intent_id": batch["intent_id"],
                        "intent_fingerprint": batch["fingerprint"],
                        "physical_batch_id": batch["batch_id"],
                        "physical_child_count": len(
                            context.get("requests", [])
                        ),
                        "query_watermark": batch["query_watermark"],
                        "event_watermark": batch["event_watermark"],
                        "native_api_called": 0,
                    },
                    path=paths.ledger_path,
                )
            except BaseException as exc:
                raise BrokerSendBatchError(
                    "stage179_physical_batch_begin_append_failed:"
                    f"{type(exc).__name__}",
                    send_order_call_count=0,
                ) from exc
            state["active_physical_batch"] = batch
            state["rows"]["_physical_batch_active"] = 1
            try:
                result = _send_order_batch_locked(lease)
                post_batch_blockers = (
                    _advance_physical_batch_event_baseline(
                        state,
                        batch,
                        ledger_path=paths.ledger_path,
                    )
                )
                if post_batch_blockers:
                    try:
                        append_execution_ledger_event(
                            {
                                "event_type": (
                                    "physical_batch_blocked_after_native_child"
                                ),
                                "target_date": batch["target_date"],
                                "intent_id": batch["intent_id"],
                                "intent_fingerprint": batch["fingerprint"],
                                "physical_batch_id": batch["batch_id"],
                                "blockers": post_batch_blockers,
                                "send_order_call_count": (
                                    result.send_order_call_count
                                ),
                                "reconciliation_required": int(
                                    result.send_order_call_count > 0
                                ),
                            },
                            path=paths.ledger_path,
                        )
                    except BaseException as exc:
                        post_batch_blockers.append(
                            "physical_batch_conflict_append_exception:"
                            f"{type(exc).__name__}"
                        )
                    raise BrokerSendBatchError(
                        "stage179_physical_batch_event_conflict_after_send:"
                        + ";".join(post_batch_blockers),
                        send_order_call_count=(
                            result.send_order_call_count
                        ),
                    )
                try:
                    append_execution_ledger_event(
                        {
                            "event_type": "physical_batch_completed",
                            "target_date": batch["target_date"],
                            "intent_id": batch["intent_id"],
                            "intent_fingerprint": batch["fingerprint"],
                            "physical_batch_id": batch["batch_id"],
                            "send_order_call_count": (
                                result.send_order_call_count
                            ),
                            "attributed_event_count": len(
                                batch.get("attributed_events", [])
                            ),
                            "native_reqid_count": batch.get(
                                "native_insert_count", 0
                            ),
                        },
                        path=paths.ledger_path,
                    )
                except BaseException as exc:
                    raise BrokerSendBatchError(
                        "stage179_physical_batch_complete_append_failed:"
                        f"{type(exc).__name__}",
                        send_order_call_count=result.send_order_call_count,
                    ) from exc
                return result
            finally:
                state["rows"].pop("_physical_batch_active", None)
                state.pop("active_physical_batch", None)

    def transport_probe() -> list[str]:
        _prune_stage179_warm_rows(state["rows"])
        blockers: list[str] = []
        if state.get("transport_generation_invalidated"):
            blockers.append("stage179_ctp_transport_generation_invalidated")
        blockers.extend(state.get("callback_persistence_blockers", []))
        td_api = state.get("td_api")
        readiness_state = state.get("readiness_state")
        if td_api is None or readiness_state is None:
            blockers.append("stage179_ctp_session_state_missing")
        else:
            blockers.extend(
                _final_ctp_transport_blockers(
                    td_api,
                    state["rows"],
                    readiness_state,
                )
            )
        return list(dict.fromkeys(blockers))

    def warm_pre_lease_blockers() -> list[str]:
        blockers = authorization_blockers(target_date=args.target_date)
        blockers.extend(
            f"stage179_order_reconciliation_pending:{vt_orderid}"
            for vt_orderid in sorted(
                state.get("reconciliation_pending_order_ids", set())
            )
        )
        blockers.extend(state.get("reconciliation_blockers", []))
        return list(dict.fromkeys(blockers))

    return CtpExecutionSession.for_callbacks(
        runtime=runtime,
        service_generation=service_generation,
        official_version=execution_profile.official_version,
        capital=execution_profile.capital,
        readiness_ttl_seconds=(
            build_phase_d_config().hard_limits.readiness_lease_ttl_seconds
        ),
        connect_startup_bundle=connect_startup_bundle,
        disconnect_transport=disconnect_transport,
        revoke_readiness=lambda reason: revoke_readiness(
            paths.readiness_path,
            service_generation=service_generation,
            reason=reason,
        ),
        transport_probe=transport_probe,
        pre_lease_blockers=warm_pre_lease_blockers,
        pre_lease_authorized_intents=admit_exact_authorized_intent,
        lease_execution_guard=authorization_lease_guard,
        post_lease_blockers=leased_authorization_blockers,
        fresh_bundle=fresh_bundle,
        pre_api_slot_blockers=pre_api_slot_blockers,
        pre_api_slot_safe_terminal=pre_api_slot_safe_terminal,
        post_api_slot_safe_terminal=post_api_slot_safe_terminal,
        connection_generation_observer=lambda generation: state.__setitem__(
            "connection_generation", generation
        ),
        reserve_api_slot=reserve_api_slot,
        send_order=send_order,
    )


def _atomic_write_stage179_status(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def _serve_stage179_no_submit_prewarm(runtime: Any) -> int:
    """Heartbeat-only process: never opens the spool or imports/loads CTP."""

    paths = ExecutorServicePaths.for_spool(
        spool_path=runtime.spool_path,
        ledger_path=runtime.ledger_path,
        readiness_path=runtime.readiness_path,
    )
    stop = Event()
    service_generation = uuid.uuid4().hex
    previous_handlers: dict[int, Any] = {}

    def request_stop(_signum: int, _frame: Any) -> None:
        stop.set()

    def write_status(status: str, *, reason: str = "") -> None:
        now = time.time_ns()
        _atomic_write_stage179_status(
            paths.readiness_path,
            {
                "schema_version": 1,
                "status": status,
                "service_kind": "no_submit_prewarm",
                "service_generation": service_generation,
                "connection_generation": "",
                "runtime_profile": runtime.profile.value,
                "order_scope": runtime.order_scope.value,
                "issued_epoch_ns": now,
                "expires_epoch_ns": now + 2_000_000_000,
                "reason": reason,
                "send_order_api_called_count": 0,
                "cancel_order_api_called_count": 0,
                "order_api_called_count": 0,
                "spool_opened": 0,
                "ctp_module_loaded": int("vnpy_ctp" in sys.modules),
            },
        )

    try:
        for signum in (signal.SIGINT, signal.SIGTERM):
            previous_handlers[signum] = signal.getsignal(signum)
            signal.signal(signum, request_stop)
        with singleton_executor_lock(paths.singleton_lock_path):
            while not stop.is_set():
                write_status("prewarm_no_submit")
                stop.wait(0.25)
    finally:
        write_status("revoked", reason="no_submit_prewarm_stopped")
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)
    return 0


def run_serve(args: argparse.Namespace) -> int:
    if not args.stage179_warm_executor:
        raise RuntimeProfileError("stage179_warm_executor_opt_in_missing")
    execution_profile = _execution_profile_for_args(args)
    runtime = resolve_runtime_profile(
        profile=args.runtime_profile,
        order_scope=args.order_scope,
        output_root=(
            Path(args.stage179_runtime_root)
            if str(args.stage179_runtime_root).strip()
            else None
        ),
        repo_root=Path(__file__).resolve().parents[2],
    )
    if args.mode != "live-real":
        permitted_no_submit_profiles = {
            (ExecutionRuntimeProfile.OFFLINE.value, OrderScope.NONE.value),
            (
                ExecutionRuntimeProfile.PRODUCTION_READONLY.value,
                OrderScope.READONLY.value,
            ),
        }
        if (args.runtime_profile, args.order_scope) not in permitted_no_submit_profiles:
            raise RuntimeProfileError(
                "stage179_no_submit_prewarm_profile_invalid"
            )
        return _serve_stage179_no_submit_prewarm(runtime)
    if not str(args.target_date).strip():
        raise RuntimeProfileError("stage179_serve_requires_target_date")
    permitted_submit_profiles = {
        (ExecutionRuntimeProfile.SIMNOW.value, OrderScope.TEST.value),
        (ExecutionRuntimeProfile.BROKER_TEST.value, OrderScope.TEST.value),
        (ExecutionRuntimeProfile.PRODUCTION_LIVE.value, OrderScope.LIVE.value),
    }
    if (args.runtime_profile, args.order_scope) not in permitted_submit_profiles:
        raise RuntimeProfileError(
            "stage179_serve_runtime_profile_does_not_permit_submit"
        )
    environment = dict(os.environ)
    environment.update(_load_runtime_env_values(runtime.env_file))
    if runtime.framework_path:
        existing_framework = environment.get("DYLD_FRAMEWORK_PATH", "")
        canonical_framework = [str(path) for path in runtime.framework_path]
        if existing_framework:
            canonical_framework.append(existing_framework)
        environment["DYLD_FRAMEWORK_PATH"] = ":".join(canonical_framework)
    submit_arming_blockers: list[str] = []
    if environment.get(PHASE_D_REAL_ADAPTER_ENV) != "1":
        submit_arming_blockers.append("real_adapter_env_missing")
    if environment.get(PHASE_D_REAL_ENABLED_ENV) != "1":
        submit_arming_blockers.append("real_submit_env_missing")
    if args.confirm_live_real != PHASE_D_CONFIRM_TEXT:
        submit_arming_blockers.append("confirm_live_real_missing")
    missing_ctp = [key for key in CTP_ENV_KEYS if not environment.get(key, "")]
    if missing_ctp:
        submit_arming_blockers.append("missing_ctp_env:" + ",".join(missing_ctp))
    if submit_arming_blockers:
        raise RuntimeProfileError(
            "stage179_submit_arming_blocked:"
            + ";".join(submit_arming_blockers)
        )
    gate = evaluate_stage179_pre_adapter_gate(
        resolved=runtime,
        release_manifest_path=args.stage179_release_manifest,
        repo_root=runtime.repo_root,
        expected_official_version=execution_profile.official_version,
        expected_capital=execution_profile.capital,
        expected_capital_label=execution_profile.capital_label,
        expected_execution_profile=execution_profile.profile_key,
        environment=environment,
        confirmation=args.confirm_stage179_activation,
        activation_receipt_path=(args.stage179_activation_receipt or None),
        phase_d_real_submit_ready=bool(
            environment.get(PHASE_D_REAL_ADAPTER_ENV) == "1"
            and environment.get(PHASE_D_REAL_ENABLED_ENV) == "1"
            and args.confirm_live_real == PHASE_D_CONFIRM_TEXT
            and not [key for key in CTP_ENV_KEYS if not environment.get(key, "")]
        ),
        stage927_ready=False,
        kill_switch_clear=not _kill_switch_blockers(),
        broker_gates_fresh=False,
        defer_cycle_authorization=True,
    )
    if gate.blockers:
        raise RuntimeProfileError(
            "stage179_warm_executor_gate_blocked:" + ";".join(gate.blockers)
        )

    # Secrets enter the process only after the pre-adapter gate succeeds.
    previous_environment = {key: os.environ.get(key) for key in environment}
    os.environ.update(environment)
    try:
        connection = open_spool(runtime.spool_path)
    except BaseException:
        for key, previous in previous_environment.items():
            if previous is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = previous
        raise
    paths = ExecutorServicePaths.for_spool(
        spool_path=runtime.spool_path,
        ledger_path=runtime.ledger_path,
        readiness_path=runtime.readiness_path,
    )
    stop = Event()
    previous_handlers: dict[int, Any] = {}

    def request_stop(_signum: int, _frame: Any) -> None:
        stop.set()

    try:
        for signum in (signal.SIGINT, signal.SIGTERM):
            previous_handlers[signum] = signal.getsignal(signum)
            signal.signal(signum, request_stop)
        return serve_executor(
            paths=paths,
            spool=SQLiteIntentSpool(
                connection,
                ledger_path=paths.ledger_path,
                close_retry_after_cancel_seconds=max(
                    1,
                    int(args.close_retry_after_cancel_seconds),
                ),
            ),
            backend_factory=lambda: _build_stage179_warm_ctp_session(
                args,
                runtime,
                paths,
            ),
            runtime=runtime,
            stop_requested=stop.is_set,
            poll_seconds=build_phase_d_config().hard_limits.executor_spool_poll_seconds,
            readiness_heartbeat_seconds=(
                build_phase_d_config().hard_limits.readiness_heartbeat_seconds
            ),
            max_dequeue_seconds=(
                build_phase_d_config().hard_limits.max_executor_dequeue_seconds
            ),
            dequeue_to_send_seconds=(
                build_phase_d_config().hard_limits.max_dequeue_to_send_seconds
            ),
            lease_seconds=build_phase_d_config().hard_limits.readiness_lease_ttl_seconds,
        )
    finally:
        connection.close()
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)
        for key, previous in previous_environment.items():
            if previous is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = previous


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    if args.command == "serve":
        raise SystemExit(run_serve(args))
    run_once(args)


if __name__ == "__main__":
    main()
