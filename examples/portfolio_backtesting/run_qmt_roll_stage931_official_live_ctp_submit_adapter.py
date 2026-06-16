from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION
from qmt_roll_official_live_execution_ledger import (
    append_execution_ledger_event,
    duplicate_blocker,
    intent_fingerprint,
    ledger_order_api_counts,
    read_execution_ledger,
    reserve_execution_ledger_intent,
)
from qmt_roll_official_live_phase_d_config import (
    KILL_SWITCH_PATH,
    LIVE_EXECUTION_LEDGER_PATH,
    PHASE_D_CONFIRM_TEXT,
    PHASE_D_REAL_ADAPTER_ENV,
    PHASE_D_REAL_ENABLED_ENV,
    build_phase_d_config,
)
from qmt_roll_official_live_email_notify import send_official_live_email_notification
from run_qmt_alignment_backtest import OUTPUT_DIR
from vnpy.event import EventEngine
from vnpy.trader.constant import Direction, Exchange, Offset, OrderType, Status
from vnpy.trader.engine import MainEngine
from vnpy.trader.event import EVENT_ACCOUNT, EVENT_LOG, EVENT_ORDER, EVENT_POSITION, EVENT_TRADE
from vnpy.trader.object import CancelRequest, OrderRequest


MODEL_TAG = "stage931_official_live_ctp_submit_adapter_v1"
OUTPUT_PREFIX = "qmt_roll_stage931_official_live_ctp_submit_adapter"
EMAIL_THROTTLE_PATH = OUTPUT_DIR / "qmt_roll_stage931_official_live_email_throttle.json"
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


def _stage905_summary_path(target_date: str) -> Path:
    key = target_date.replace("-", "") if target_date else "latest"
    return OUTPUT_DIR / f"{STAGE905_PREFIX}_summary_{key}_{STAGE905_MODEL_TAG}.json"


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


def _log_messages(rows: list[dict[str, Any]]) -> list[str]:
    messages: list[str] = []
    for row in rows:
        for key in ("msg", "message", "value"):
            text = str(row.get(key, "")).strip()
            if text:
                messages.append(text)
    return messages


def _ctp_connection_flags(rows: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    messages = _log_messages(rows.get("logs", []))
    return {
        "td_connected": any("交易服务器连接成功" in msg for msg in messages),
        "td_auth_success": any("交易服务器授权验证成功" in msg for msg in messages),
        "td_login_success": any("交易服务器登录成功" in msg for msg in messages),
        "td_login_failed": any("交易服务器登录失败" in msg for msg in messages),
        "settlement_confirmed": any("结算信息确认成功" in msg for msg in messages),
        "account_rows": len(rows.get("accounts", [])),
        "position_rows": len(rows.get("positions", [])),
        "position_query_last_seen": any(bool(row.get("last")) for row in rows.get("position_query_callbacks", [])),
        "order_rows": len(rows.get("orders", [])),
        "trade_rows": len(rows.get("trades", [])),
        "latest_log_messages": messages[-12:],
    }


def _ctp_connection_ready(flags: dict[str, Any]) -> tuple[bool, list[str]]:
    blockers: list[str] = []
    for key in ("td_connected", "td_auth_success", "td_login_success", "settlement_confirmed"):
        if not flags.get(key):
            blockers.append(f"ctp_{key}_missing")
    if int(flags.get("account_rows", 0)) <= 0:
        blockers.append("ctp_account_callback_missing")
    if not flags.get("position_query_last_seen"):
        blockers.append("ctp_position_query_last_missing")
    return not blockers, blockers


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


def _vt_symbol_from_row(row: dict[str, Any]) -> str:
    vt_symbol = str(row.get("vt_symbol", "") or "").strip()
    if vt_symbol:
        return vt_symbol
    symbol = str(row.get("symbol", "") or "").strip()
    exchange = str(row.get("exchange", "") or "").strip()
    return f"{symbol}.{exchange}" if symbol and exchange else symbol


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


def _latest_order_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return []
    frame = pd.DataFrame(rows)
    key_source = frame.get("vt_orderid", frame.get("orderid", pd.Series([""] * len(frame))))
    frame["_order_key"] = key_source.fillna("").astype(str)
    empty_key = frame["_order_key"].eq("")
    frame.loc[empty_key, "_order_key"] = [f"row_{idx}" for idx in frame.index[empty_key]]
    frame["_dt"] = pd.to_datetime(frame.get("datetime", frame.get("received_at", "")), errors="coerce")
    frame["_row_order"] = range(len(frame))
    latest = frame.sort_values(["_order_key", "_dt", "_row_order"]).drop_duplicates("_order_key", keep="last")
    return latest.drop(columns=[col for col in ("_order_key", "_dt", "_row_order") if col in latest.columns]).to_dict(orient="records")


def _active_order_count(rows: list[dict[str, Any]]) -> int:
    active = {"submitting", "submitted", "not traded", "nottraded", "part traded", "parttraded", "未成交", "提交中", "部分成交"}
    return sum(1 for row in _latest_order_rows(rows) if str(row.get("status", "")).strip().lower() in active)


def _opposite_position_direction(order_direction: str) -> str:
    if order_direction == "short":
        return "long"
    if order_direction == "long":
        return "short"
    return ""


def _trade_delta_volume(rows: list[dict[str, Any]], start_trade_count: int, vt_orderid: str) -> float:
    total = 0.0
    for row in rows[start_trade_count:]:
        if vt_orderid and str(row.get("vt_orderid", "")) != vt_orderid:
            continue
        volume = pd.to_numeric(row.get("volume", 0.0), errors="coerce")
        if not pd.isna(volume):
            total += float(volume)
    return total


def _trade_delta_vwap(rows: list[dict[str, Any]], start_trade_count: int, vt_orderid: str) -> tuple[float, float, str]:
    total_volume = 0.0
    total_notional = 0.0
    for row in rows[start_trade_count:]:
        if vt_orderid and str(row.get("vt_orderid", "")) != vt_orderid:
            continue
        volume = pd.to_numeric(row.get("volume", 0.0), errors="coerce")
        price = pd.to_numeric(row.get("price", 0.0), errors="coerce")
        if pd.isna(volume) or pd.isna(price) or float(volume) <= 0 or float(price) <= 0:
            continue
        total_volume += float(volume)
        total_notional += float(volume) * float(price)
    if total_volume <= 0:
        return 0.0, 0.0, "order_traded_without_trade_price"
    return total_volume, total_notional / total_volume, "event_trade_weighted_avg"


def _final_pre_send_blockers(rows: dict[str, list[dict[str, Any]]], req: OrderRequest, vt_symbol: str) -> list[str]:
    blockers: list[str] = []
    active_count = _active_order_count(rows.get("orders", []))
    if active_count > 0:
        blockers.append(f"final_active_order_count={active_count}")
    if _normalize_offset_text(req.offset.value) == "close":
        position_direction = _opposite_position_direction(_normalize_direction_text(req.direction.value))
        final_volume = _position_volume(rows.get("positions", []), vt_symbol, position_direction)
        if final_volume <= 0:
            blockers.append(f"final_no_matching_{position_direction}_broker_position_to_close")
        elif final_volume < float(req.volume):
            blockers.append(f"final_insufficient_broker_position:{final_volume}<{req.volume}")
    return blockers


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
    text = str(status_value).strip().lower()
    return text in {"submitting", "submitted", "not traded", "nottraded", "part traded", "parttraded", "未成交", "提交中", "部分成交"}


def _latest_order(orders: list[dict[str, Any]], vt_orderid: str) -> dict[str, Any] | None:
    gateway, _, orderid = vt_orderid.partition(".")
    matched = [row for row in orders if str(row.get("gateway_name", "")) == gateway and str(row.get("orderid", "")) == orderid]
    return matched[-1] if matched else None


def _order_traded_volume(latest_order: dict[str, Any] | None, fallback: float) -> float:
    if not latest_order:
        return fallback
    traded = pd.to_numeric(latest_order.get("traded", fallback), errors="coerce")
    return fallback if pd.isna(traded) else float(traded)


def _wait_order_completion(rows: dict[str, list[dict[str, Any]]], vt_orderid: str, req_volume: float, deadline: float) -> dict[str, Any]:
    latest: dict[str, Any] | None = None
    while time.time() < deadline:
        latest = _latest_order(rows["orders"], vt_orderid)
        traded_volume = _order_traded_volume(latest, 0.0)
        if latest and (not _status_is_active(latest.get("status")) or traded_volume >= req_volume):
            break
        time.sleep(0.2)
    latest = _latest_order(rows["orders"], vt_orderid)
    return latest or {}


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
        f"[C9/15w][Stage931][{severity}] {summary['target_date']} "
        f"{summary['adapter_status']} order_api={summary['order_api_called_count']} trades={summary['trade_row_count']}"
    )
    body_lines = [
        "C9/15w Stage931 订单提交适配器产生关键事件。",
        "",
        f"生成时间: {summary['generated_at']}",
        f"目标日期: {summary['target_date']}",
        f"模式: {summary['mode']}",
        f"状态: {summary['adapter_status']}",
        f"Ready intents: {summary['ready_intent_count']}",
        f"Blockers: {summary['blockers']}",
        f"Send API: {summary['send_order_api_called_count']}",
        f"Cancel API: {summary['cancel_order_api_called_count']}",
        f"Order rows: {summary['order_row_count']}",
        f"Trade rows: {summary['trade_row_count']}",
    ]
    if not submitted.empty:
        body_lines.extend(["", "Submitted tail:", submitted.tail(10).to_string(index=False)])
    attachments = [
        paths["report_md"],
        paths["summary_json"],
        paths["submitted_csv"],
    ]
    if _env_enabled("OFFICIAL_LIVE_EMAIL_ATTACH_RAW_CTP"):
        attachments.extend([paths["orders_csv"], paths["trades_csv"], paths["logs_csv"]])
        body_lines.extend(["", "附件包含 Stage931 report/summary/submitted/未脱敏 raw CTP orders/trades/logs，仅用于显式取证。"])
    else:
        body_lines.extend(
            [
                "",
                "附件包含 Stage931 report/summary/submitted；raw CTP orders/trades/logs 默认不邮件外发。",
                "如需未脱敏取证附件，显式设置 OFFICIAL_LIVE_EMAIL_ATTACH_RAW_CTP=1 后重跑。",
            ]
        )
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Official-live CTP submit adapter, hard-gated by Stage927.")
    parser.add_argument("--target-date", required=True)
    parser.add_argument("--mode", choices=["dry-run", "live-real"], default="dry-run")
    parser.add_argument("--confirm-live-real", default="")
    parser.add_argument("--max-orders", type=int, default=1)
    parser.add_argument("--connect-wait-seconds", type=int, default=8)
    parser.add_argument("--fill-wait-seconds", type=int, default=8)
    parser.add_argument("--post-cancel-wait-seconds", type=int, default=4)
    parser.add_argument("--max-stage927-age-seconds", type=int, default=180)
    parser.add_argument("--max-stage905-age-seconds", type=int, default=180)
    parser.add_argument("--max-target-date-age-days", type=int, default=4)
    parser.add_argument("--close-retry-after-cancel-seconds", type=int, default=30)
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    paths = _paths(args.target_date)
    ready = _ready_intents(args.target_date)
    stage905 = _read_json(_stage905_summary_path(args.target_date))
    stage927 = _read_json(_stage927_summary_path(args.target_date))
    kill_switch = _read_json(KILL_SWITCH_PATH)
    config = build_phase_d_config()
    ledger_rows = read_execution_ledger()
    ledger_counts = ledger_order_api_counts(ledger_rows, args.target_date)
    target_age_days = _target_age_days(args.target_date)
    current_phase_d_sessions = _current_phase_d_sessions()
    in_execution_session = any(row.get("role") == "market_and_execution" for row in current_phase_d_sessions)
    submitted_rows: list[dict[str, Any]] = []
    rows: dict[str, list[dict[str, Any]]] = {
        "orders": [],
        "trades": [],
        "accounts": [],
        "positions": [],
        "logs": [],
        "position_query_callbacks": [],
    }

    blockers: list[str] = []
    if ready.empty:
        blockers.append("no_ready_stage905_intents")
    if len(ready) > min(args.max_orders, config.hard_limits.max_order_count_per_cycle):
        blockers.append("ready_intent_count_above_limit")
    if ledger_counts["send_order_called"] >= config.hard_limits.max_order_count_per_day:
        blockers.append("ledger_daily_send_order_limit_reached")
    if ledger_counts["cancel_order_called"] >= config.hard_limits.max_cancel_count_per_day:
        blockers.append("ledger_daily_cancel_order_limit_reached")
    if bool(kill_switch.get("enabled", False) or kill_switch.get("kill_switch_active", False)):
        blockers.append("kill_switch_active")
    if args.mode == "live-real":
        if stage927.get("real_submit_permitted") != 1:
            blockers.append("stage927_real_submit_not_permitted")
        stage927_age = _age_seconds(stage927.get("generated_at"))
        if stage927_age is None or stage927_age > args.max_stage927_age_seconds:
            blockers.append(f"stage927_summary_stale_or_missing:{stage927_age}")
        stage905_age = _age_seconds(stage905.get("generated_at"))
        if stage905_age is None or stage905_age > args.max_stage905_age_seconds:
            blockers.append(f"stage905_summary_stale_or_missing:{stage905_age}")
        if stage905.get("target_date") != args.target_date:
            blockers.append("stage905_target_date_mismatch")
        if not in_execution_session:
            blockers.append("live_real_not_in_execution_session")
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

    ledger_intent_rows: list[dict[str, Any]] = []
    for row in ready.head(args.max_orders).to_dict(orient="records"):
        try:
            payload = json.loads(str(row.get("order_request_json", "{}")))
        except json.JSONDecodeError as exc:
            blockers.append(f"invalid_order_request_json:{row.get('intent_id', '')}:{exc}")
            continue
        duplicate, fingerprint, fingerprint_payload, latest = duplicate_blocker(
            rows=ledger_rows,
            target_date=args.target_date,
            row=row,
            order_request=payload,
            close_retry_after_cancel_seconds=max(1, args.close_retry_after_cancel_seconds),
        )
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
        original_position_rsp: Any = None
        ctp_gateway_module: Any = None
        try:
            from vnpy_ctp import CtpGateway
            from vnpy_ctp.gateway import ctp_gateway as ctp_gateway_module

            original_position_rsp = ctp_gateway_module.CtpTdApi.onRspQryInvestorPosition

            def instrumented_position_rsp(self: Any, data: dict, error: dict, reqid: int, last: bool) -> None:
                rows["position_query_callbacks"].append(
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
            connection_flags = _ctp_connection_flags(rows)
            connection_ready, connection_blockers = _ctp_connection_ready(connection_flags)
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
                    continue
                active_reserved_context = {
                    "target_date": args.target_date,
                    "intent_id": row.get("intent_id", ""),
                    "intent_fingerprint": fingerprint,
                    "vt_symbol": row.get("vt_symbol", ""),
                    "adapter": "Stage931",
                }
                final_blockers = _final_pre_send_blockers(rows, req, str(row.get("vt_symbol", "")))
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
                            "order_request_json": row.get("order_request_json", ""),
                        }
                    )
                    active_reserved_context = None
                    continue
                send_count += 1
                start_trade_count = len(rows["trades"])
                vt_orderid = main_engine.send_order(req, "CTP")
                append_execution_ledger_event(
                    {
                        "event_type": "send_order_called",
                        "target_date": args.target_date,
                        "intent_id": row.get("intent_id", ""),
                        "intent_fingerprint": fingerprint,
                        "vt_symbol": row.get("vt_symbol", ""),
                        "vt_orderid": vt_orderid,
                        "direction": req.direction.value,
                        "offset": req.offset.value,
                        "volume": req.volume,
                        "price": req.price,
                        "adapter": "Stage931",
                    }
                )
                if not vt_orderid:
                    append_execution_ledger_event(
                        {
                            "event_type": "send_order_returned_empty",
                            "target_date": args.target_date,
                            "intent_id": row.get("intent_id", ""),
                            "intent_fingerprint": fingerprint,
                            "vt_symbol": row.get("vt_symbol", ""),
                            "adapter": "Stage931",
                        }
                    )
                    submitted_rows.append(
                        {
                            "intent_id": row.get("intent_id", ""),
                            "vt_symbol": row.get("vt_symbol", ""),
                            "mode": "live-real",
                            "submit_status": "send_order_returned_empty",
                            "intent_fingerprint": fingerprint,
                            "vt_orderid": "",
                            "direction": req.direction.value,
                            "offset": req.offset.value,
                            "volume": req.volume,
                            "price": req.price,
                        }
                    )
                    active_reserved_context = None
                    continue
                deadline = time.time() + max(1, args.fill_wait_seconds)
                latest = _wait_order_completion(rows, vt_orderid, float(req.volume), deadline)
                traded_after_send = len(rows["trades"]) > start_trade_count
                trade_event_volume, trade_event_vwap, fill_price_source = _trade_delta_vwap(rows["trades"], start_trade_count, vt_orderid)
                traded_volume_after_send = trade_event_volume
                latest_order_traded = _order_traded_volume(latest, traded_volume_after_send)
                effective_traded_volume = max(traded_volume_after_send, latest_order_traded)
                ledger_fill_price = trade_event_vwap if trade_event_vwap > 0 else 0.0
                residual_volume = max(0.0, float(req.volume) - effective_traded_volume)
                if effective_traded_volume > 0:
                    append_execution_ledger_event(
                        {
                            "event_type": "filled_or_part_filled",
                            "target_date": args.target_date,
                            "intent_id": row.get("intent_id", ""),
                            "intent_fingerprint": fingerprint,
                            "vt_symbol": row.get("vt_symbol", ""),
                            "vt_orderid": vt_orderid,
                            "direction": req.direction.value,
                            "offset": req.offset.value,
                            "volume": req.volume,
                            "price": ledger_fill_price,
                            "order_limit_price": req.price,
                            "fill_price_source": fill_price_source,
                            "adapter": "Stage931",
                            "trade_rows_delta": len(rows["trades"]) - start_trade_count,
                            "trade_volume_delta": effective_traded_volume,
                            "residual_volume": residual_volume,
                        }
                    )
                should_cancel_residual = residual_volume > 0 and (not latest or _status_is_active(latest.get("status")))
                submit_status = "submitted_to_ctp"
                if should_cancel_residual:
                    _, _, orderid = vt_orderid.partition(".")
                    cancel_count += 1
                    main_engine.cancel_order(CancelRequest(orderid=orderid, symbol=req.symbol, exchange=req.exchange), "CTP")
                    submit_status = "submitted_partial_or_unknown_cancel_requested" if effective_traded_volume > 0 else "submitted_unfilled_cancel_requested"
                    append_execution_ledger_event(
                        {
                            "event_type": "cancel_order_called",
                            "target_date": args.target_date,
                            "intent_id": row.get("intent_id", ""),
                            "intent_fingerprint": fingerprint,
                            "vt_symbol": row.get("vt_symbol", ""),
                            "vt_orderid": vt_orderid,
                            "adapter": "Stage931",
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
                    post_cancel_trade_volume, post_cancel_vwap, post_cancel_price_source = _trade_delta_vwap(
                        rows,
                        start_trade_count,
                        vt_orderid,
                    )
                    post_cancel_effective_traded = max(post_cancel_trade_volume, _order_traded_volume(latest_after_cancel, effective_traded_volume))
                    residual_volume = max(0.0, float(req.volume) - post_cancel_effective_traded)
                    effective_traded_volume = post_cancel_effective_traded
                    if post_cancel_vwap > 0 and post_cancel_trade_volume > trade_event_volume:
                        ledger_fill_price = post_cancel_vwap
                        fill_price_source = post_cancel_price_source
                    cancel_status_known = bool(latest_after_cancel and str(latest_after_cancel.get("status", "")).strip())
                    if residual_volume > 0 and (not cancel_status_known or _status_is_active(latest_after_cancel.get("status"))):
                        residual_event_type = (
                            "residual_order_active_after_cancel"
                            if cancel_status_known
                            else "residual_order_unknown_after_cancel"
                        )
                        blockers.append(residual_event_type)
                        adapter_status = f"adapter_blocked_{residual_event_type}"
                        append_execution_ledger_event(
                            {
                                "event_type": residual_event_type,
                                "target_date": args.target_date,
                                "intent_id": row.get("intent_id", ""),
                                "intent_fingerprint": fingerprint,
                                "vt_symbol": row.get("vt_symbol", ""),
                                "vt_orderid": vt_orderid,
                                "direction": req.direction.value,
                                "offset": req.offset.value,
                                "adapter": "Stage931",
                                "latest_order_status": latest_after_cancel.get("status", "") if latest_after_cancel else "",
                                "trade_volume_delta": effective_traded_volume,
                                "residual_volume": residual_volume,
                            }
                        )
                    latest = latest_after_cancel or latest
                elif not traded_after_send:
                    append_execution_ledger_event(
                        {
                            "event_type": "rejected_or_inactive",
                            "target_date": args.target_date,
                            "intent_id": row.get("intent_id", ""),
                            "intent_fingerprint": fingerprint,
                            "vt_symbol": row.get("vt_symbol", ""),
                            "vt_orderid": vt_orderid,
                            "adapter": "Stage931",
                            "latest_order_status": latest.get("status", ""),
                        }
                    )
                active_reserved_context = None
                submitted_rows.append(
                    {
                        "intent_id": row.get("intent_id", ""),
                        "vt_symbol": row.get("vt_symbol", ""),
                        "mode": "live-real",
                        "submit_status": submit_status,
                        "intent_fingerprint": fingerprint,
                        "vt_orderid": vt_orderid,
                        "direction": req.direction.value,
                        "offset": req.offset.value,
                        "volume": req.volume,
                        "price": req.price,
                        "trade_volume_delta": effective_traded_volume,
                        "residual_volume": residual_volume,
                        "fill_price": ledger_fill_price,
                        "fill_price_source": fill_price_source,
                        "latest_order_status": latest.get("status", ""),
                    }
                )
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
            if original_position_rsp is not None and ctp_gateway_module is not None:
                ctp_gateway_module.CtpTdApi.onRspQryInvestorPosition = original_position_rsp

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
        "stage905_summary_age_seconds": stage905_age,
        "stage927_summary_age_seconds": stage927_age,
        "target_date_age_days": target_age_days,
        "current_phase_d_sessions": current_phase_d_sessions,
        "ledger_path": str(LIVE_EXECUTION_LEDGER_PATH.resolve()),
        "ledger_counts_before": ledger_counts,
        "ledger_intents": ledger_intent_rows,
        "ctp_connection_flags": connection_flags,
        "send_order_api_called_count": send_count,
        "cancel_order_api_called_count": cancel_count,
        "order_api_called_count": send_count + cancel_count,
        "order_row_count": len(rows["orders"]),
        "trade_row_count": len(rows["trades"]),
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
    summary["email_notification"] = _send_submit_email(paths, summary, submitted)
    paths["summary_json"].write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
