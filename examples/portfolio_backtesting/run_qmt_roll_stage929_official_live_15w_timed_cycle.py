from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from qmt_roll_official_live_config import (
    OFFICIAL_LIVE_ALIAS,
    OFFICIAL_LIVE_SHADOW_ANALYSIS_START_DATE,
    OFFICIAL_LIVE_VERSION,
)
from qmt_roll_official_live_phase_d_config import (
    PHASE_D_READONLY_REFRESH_CONFIRM_TEXT,
    PHASE_D_READONLY_REFRESH_ENV,
    PHASE_D_REAL_ADAPTER_ENV,
    PHASE_D_REAL_ENABLED_ENV,
    PHASE_D_SESSION_DAEMON_ENV,
    PHASE_D_SHADOW_REFRESH_CONFIRM_TEXT,
    PHASE_D_SHADOW_REFRESH_ENV,
    READONLY_CONTRACTS_PATH,
    STAGE901_ENTRY_RISK_PATH,
    STAGE901_PENDING_ORDERS_PATH,
)
from qmt_roll_official_live_email_notify import send_official_live_email_notification
from run_qmt_alignment_backtest import OUTPUT_DIR


PROJECT_DIR = Path(__file__).resolve().parent
REPO_ROOT = PROJECT_DIR.parent.parent
PYTHON_PATH = REPO_ROOT / ".py311/bin/python"
STAGE903_SCRIPT = PROJECT_DIR / "run_qmt_roll_stage903_official_live_phase_d_controller.py"

MODEL_TAG = "stage929_official_live_15w_timed_cycle_v1"
OUTPUT_PREFIX = "qmt_roll_stage929_official_live_15w_timed_cycle"
LATEST_SUMMARY_PATH = OUTPUT_DIR / "qmt_roll_official_live_15w_timed_cycle_latest_summary.json"
LATEST_REPORT_PATH = OUTPUT_DIR / "qmt_roll_official_live_15w_timed_cycle_latest_report.md"
LATEST_COMMAND_LOG_PATH = OUTPUT_DIR / "qmt_roll_official_live_15w_timed_cycle_latest_command.log"
STAGE260_MODEL_TAG = "stage260_official_live_daily_execution_gate_v1"
STAGE260_PREFIX = "qmt_roll_stage260_official_live_daily_execution_gate"
STAGE905_MODEL_TAG = "stage905_official_live_executor_dry_run_v1"
STAGE905_PREFIX = "qmt_roll_stage905_official_live_executor_dry_run"
STAGE608_CONTRACTS_PATH = (
    OUTPUT_DIR / "qmt_roll_stage608_readonly_tick_snapshot_probe_contracts_stage608_readonly_tick_snapshot_probe_v1.csv"
)

SIGNAL_DETAIL_COLUMNS: list[tuple[str, str]] = [
    ("product_vt_symbol", "品种"),
    ("vt_symbol", "合约"),
    ("direction", "方向"),
    ("offset", "开平"),
    ("planned_volume", "手数"),
    ("order_price", "委托价"),
    ("strategy_entry_price", "策略入场价"),
    ("stop_price", "止损价"),
    ("stop_distance", "止损距离"),
    ("risk_per_contract", "单手风险"),
    ("total_risk", "总风险"),
    ("margin_ratio", "策略保证金率"),
    ("estimated_margin", "策略预估保证金"),
    ("margin_to_available_pct", "策略保证金/可用"),
    ("stage260_action", "执行闸门"),
    ("stage260_reason", "阻断/原因"),
]


def _date_key(value: str) -> str:
    return value.replace("-", "") if value else "latest"


def _paths(phase: str, target_date: str, run_id: str) -> dict[str, Path]:
    key = f"{phase}_{_date_key(target_date)}_{run_id}"
    return {
        "summary_json": OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{key}_{MODEL_TAG}.json",
        "report_md": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{key}_{MODEL_TAG}.md",
        "command_log": OUTPUT_DIR / f"{OUTPUT_PREFIX}_command_log_{key}_{MODEL_TAG}.log",
    }


def _read_json(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists():
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


def _stage260_decision_path(target_date: str) -> Path:
    return OUTPUT_DIR / f"{STAGE260_PREFIX}_decisions_{_date_key(target_date)}_{STAGE260_MODEL_TAG}.csv"


def _stage905_intents_path(target_date: str) -> Path:
    return OUTPUT_DIR / f"{STAGE905_PREFIX}_intents_{_date_key(target_date)}_{STAGE905_MODEL_TAG}.csv"


def _clean(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def _to_float(value: Any, default: float = 0.0) -> float:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return default
    return float(number)


def _format_number(value: Any, *, decimals: int = 2, pct: bool = False) -> str:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return ""
    formatted = f"{float(number):,.{decimals}f}"
    if decimals > 0:
        formatted = formatted.rstrip("0").rstrip(".")
    return f"{formatted}%" if pct else formatted


def _normal_text(value: Any) -> str:
    text = _clean(value).lower()
    if text in {"long", "direction.long", "多"}:
        return "long"
    if text in {"short", "direction.short", "空"}:
        return "short"
    if text in {"open", "offset.open", "开"}:
        return "open"
    if text in {"close", "offset.close", "closetoday", "closeyesterday", "平", "平今", "平昨"}:
        return "close"
    return text


def _first_match(frame: pd.DataFrame, *, vt_symbol: str, direction: str = "", offset: str = "") -> dict[str, Any]:
    if frame.empty:
        return {}
    mask = pd.Series(True, index=frame.index)
    if "vt_symbol" in frame.columns:
        mask &= frame["vt_symbol"].fillna("").astype(str).eq(vt_symbol)
    elif "contract_vt_symbol" in frame.columns:
        mask &= frame["contract_vt_symbol"].fillna("").astype(str).eq(vt_symbol)
    else:
        return {}
    if direction and "direction" in frame.columns:
        mask &= frame["direction"].map(_normal_text).eq(direction)
    if offset and "offset" in frame.columns:
        mask &= frame["offset"].map(_normal_text).eq(offset)
    matched = frame[mask]
    if matched.empty:
        return {}
    return matched.iloc[0].to_dict()


def _contract_row(vt_symbol: str) -> dict[str, Any]:
    contracts = _read_csv_maybe(READONLY_CONTRACTS_PATH)
    if contracts.empty:
        contracts = _read_csv_maybe(STAGE608_CONTRACTS_PATH)
    if contracts.empty:
        return {}
    if "vt_symbol" in contracts.columns:
        matched = contracts[contracts["vt_symbol"].fillna("").astype(str).eq(vt_symbol)]
        if not matched.empty:
            return matched.iloc[0].to_dict()
    if "." not in vt_symbol or "symbol" not in contracts.columns or "exchange" not in contracts.columns:
        return {}
    symbol, exchange = vt_symbol.rsplit(".", 1)
    matched = contracts[
        contracts["symbol"].fillna("").astype(str).eq(symbol)
        & contracts["exchange"].fillna("").astype(str).eq(exchange)
    ]
    if matched.empty:
        return {}
    return matched.iloc[0].to_dict()


def _product_from_vt_symbol(vt_symbol: str) -> str:
    if "." not in vt_symbol:
        return vt_symbol
    symbol, exchange = vt_symbol.rsplit(".", 1)
    product = "".join(ch for ch in symbol if not ch.isdigit())
    return f"{product}.{exchange}" if product else vt_symbol


def _money_ratio(amount: float, denominator: Any) -> float | None:
    base = _to_float(denominator, 0.0)
    if amount <= 0 or base <= 0:
        return None
    return amount / base * 100.0


def _build_signal_details(wrapper: dict[str, Any], stage903: dict[str, Any]) -> pd.DataFrame:
    target_date = str(wrapper.get("target_date", ""))
    pending_orders = _read_csv_maybe(STAGE901_PENDING_ORDERS_PATH)
    stage260_decisions = _read_csv_maybe(_stage260_decision_path(target_date))
    stage905_intents = _read_csv_maybe(_stage905_intents_path(target_date))
    entry_risk = _read_csv_maybe(STAGE901_ENTRY_RISK_PATH)
    base_rows = pending_orders
    if base_rows.empty and not stage260_decisions.empty:
        base_rows = stage260_decisions.rename(columns={"planned_volume": "volume", "theoretical_price": "price"})
    if base_rows.empty and not stage905_intents.empty:
        base_rows = stage905_intents.rename(columns={"planned_volume": "volume", "limit_price": "price"})

    account = wrapper.get("account_snapshot") or {}
    details: list[dict[str, Any]] = []
    for raw in base_rows.to_dict(orient="records"):
        vt_symbol = _clean(raw.get("vt_symbol"))
        if not vt_symbol:
            continue
        direction = _normal_text(raw.get("direction"))
        offset = _normal_text(raw.get("offset"))
        risk_row = _first_match(entry_risk, vt_symbol=vt_symbol, direction=direction)
        gate_row = _first_match(stage260_decisions, vt_symbol=vt_symbol, direction=direction, offset=offset)
        intent_row = _first_match(stage905_intents, vt_symbol=vt_symbol, direction=direction, offset=offset)
        contract = _contract_row(vt_symbol)

        planned_volume = _to_float(
            intent_row.get("planned_volume", raw.get("planned_volume", raw.get("volume", gate_row.get("planned_volume")))),
            0.0,
        )
        order_price = _to_float(
            intent_row.get("limit_price", raw.get("price", gate_row.get("theoretical_price", risk_row.get("planned_entry_price")))),
            0.0,
        )
        strategy_entry_price = _to_float(risk_row.get("entry_price", risk_row.get("planned_entry_price", order_price)), 0.0)
        stop_price = _to_float(risk_row.get("stop_price"), 0.0)
        stop_distance = _to_float(risk_row.get("stop_distance"), 0.0)
        size = _to_float(risk_row.get("size", contract.get("size")), 0.0)
        margin_ratio = _to_float(risk_row.get("margin_ratio"), 0.0)
        margin_per_contract = _to_float(risk_row.get("margin_per_contract"), 0.0)
        if margin_per_contract <= 0 and strategy_entry_price > 0 and size > 0 and margin_ratio > 0:
            margin_per_contract = strategy_entry_price * size * margin_ratio
        estimated_margin = _to_float(risk_row.get("actual_margin_amount"), 0.0)
        if estimated_margin <= 0 and margin_per_contract > 0 and planned_volume > 0:
            estimated_margin = margin_per_contract * planned_volume
        total_risk = _to_float(risk_row.get("actual_risk_amount"), 0.0)
        risk_per_contract = _to_float(risk_row.get("risk_per_contract"), 0.0)
        if total_risk <= 0 and risk_per_contract > 0 and planned_volume > 0:
            total_risk = risk_per_contract * planned_volume
        estimated_equity = _to_float(risk_row.get("estimated_equity", account.get("balance")), 0.0)
        stress_multiplier = _to_float(risk_row.get("recovery_sleeve_broker_margin_multiplier"), 0.0)
        stress_margin = estimated_margin * stress_multiplier if estimated_margin > 0 and stress_multiplier > 0 else 0.0

        details.append(
            {
                "product_vt_symbol": _clean(risk_row.get("product_vt_symbol")) or _product_from_vt_symbol(vt_symbol),
                "vt_symbol": vt_symbol,
                "direction": direction,
                "offset": offset,
                "planned_volume": planned_volume,
                "order_price": order_price,
                "strategy_entry_price": strategy_entry_price,
                "stop_price": stop_price,
                "stop_distance": stop_distance,
                "contract_size": size,
                "pricetick": _to_float(contract.get("pricetick", intent_row.get("pricetick")), 0.0),
                "risk_per_contract": risk_per_contract,
                "total_risk": total_risk,
                "risk_to_equity_pct": _money_ratio(total_risk, estimated_equity),
                "margin_ratio": margin_ratio * 100.0 if margin_ratio > 0 else None,
                "margin_per_contract": margin_per_contract,
                "estimated_margin": estimated_margin,
                "stress_margin_estimate": stress_margin,
                "margin_to_available_pct": _money_ratio(estimated_margin, account.get("available", estimated_equity)),
                "projected_total_margin_after": _to_float(risk_row.get("projected_total_margin_after"), 0.0),
                "contracts_by_risk": _to_float(risk_row.get("contracts_by_risk"), 0.0),
                "contracts_by_margin": _to_float(risk_row.get("contracts_by_margin"), 0.0),
                "contracts_by_single_trade_cap": _to_float(risk_row.get("contracts_by_single_trade_cap"), 0.0),
                "selected_volume": _to_float(risk_row.get("selected_volume", planned_volume), 0.0),
                "risk_cluster_cap_enabled": _to_float(risk_row.get("risk_cluster_cap_enabled"), 0.0),
                "risk_cluster_name": _clean(risk_row.get("risk_cluster_name")),
                "risk_cluster_cap_ratio": (
                    _to_float(risk_row.get("risk_cluster_cap_ratio"), 0.0) * 100.0
                    if _to_float(risk_row.get("risk_cluster_cap_ratio"), 0.0) > 0
                    else None
                ),
                "risk_cluster_cap_amount": _to_float(risk_row.get("risk_cluster_cap_amount"), 0.0),
                "risk_cluster_reserved_margin_before": _to_float(
                    risk_row.get("risk_cluster_reserved_margin_before"), 0.0
                ),
                "risk_cluster_max_volume": _to_float(risk_row.get("risk_cluster_max_volume"), 0.0),
                "risk_cluster_selected_volume_before": _to_float(
                    risk_row.get("risk_cluster_selected_volume_before"), 0.0
                ),
                "risk_cluster_selected_volume": _to_float(risk_row.get("risk_cluster_selected_volume"), 0.0),
                "risk_cluster_heat_gate_enabled": _to_float(risk_row.get("risk_cluster_heat_gate_enabled"), 0.0),
                "risk_cluster_heat_gate_weight": _to_float(risk_row.get("risk_cluster_heat_gate_weight"), 0.0),
                "risk_mode": _clean(risk_row.get("risk_mode")),
                "risk_multiplier": _to_float(risk_row.get("risk_multiplier"), 0.0),
                "entry_context": _clean(risk_row.get("env_gate_entry_context")),
                "stage260_action": _clean(gate_row.get("execution_action")),
                "stage260_reason": _clean(gate_row.get("execution_reason")),
                "risk_level": _clean(gate_row.get("risk_level", stage903.get("risk_level"))),
                "readonly_gate_passed": _clean(gate_row.get("readonly_gate_passed")),
                "broker_position_state": _clean(gate_row.get("broker_position_snapshot_state")),
                "broker_active_order_count": _to_float(gate_row.get("broker_active_order_count"), 0.0),
                "stage905_status": _clean(intent_row.get("executor_status")),
                "stage905_reason": _clean(intent_row.get("executor_reason")),
            }
        )
    return pd.DataFrame(details)


def _signal_details_frame(wrapper: dict[str, Any], stage903: dict[str, Any]) -> pd.DataFrame:
    cached = wrapper.get("signal_details")
    if isinstance(cached, list):
        return pd.DataFrame(cached)
    return _build_signal_details(wrapper, stage903)


def _markdown_table(frame: pd.DataFrame, columns: list[tuple[str, str]]) -> str:
    if frame.empty:
        return "_empty_"
    selected = [(key, label) for key, label in columns if key in frame.columns]
    if not selected:
        return "_empty_"
    lines = [
        "| " + " | ".join(label for _, label in selected) + " |",
        "| " + " | ".join("---" for _ in selected) + " |",
    ]
    for row in frame.head(12).to_dict(orient="records"):
        values = []
        for key, _ in selected:
            value = row.get(key, "")
            if key in {"margin_ratio", "margin_to_available_pct", "risk_to_equity_pct", "risk_cluster_cap_ratio"}:
                values.append(_format_number(value, decimals=2, pct=True))
            elif key in {
                "planned_volume",
                "contract_size",
                "contracts_by_risk",
                "contracts_by_margin",
                "contracts_by_single_trade_cap",
                "selected_volume",
                "risk_cluster_cap_enabled",
                "risk_cluster_max_volume",
                "risk_cluster_selected_volume_before",
                "risk_cluster_selected_volume",
                "risk_cluster_heat_gate_enabled",
                "broker_active_order_count",
            }:
                values.append(_format_number(value, decimals=0))
            elif key in {
                "order_price",
                "strategy_entry_price",
                "stop_price",
                "stop_distance",
                "risk_per_contract",
                "total_risk",
                "margin_per_contract",
                "estimated_margin",
                "stress_margin_estimate",
                "projected_total_margin_after",
                "risk_cluster_cap_amount",
                "risk_cluster_reserved_margin_before",
                "risk_cluster_heat_gate_weight",
                "pricetick",
            }:
                values.append(_format_number(value, decimals=2))
            else:
                values.append(_clean(value))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def _format_plain_value(key: str, value: Any) -> str:
    if key in {"margin_ratio", "margin_to_available_pct", "risk_to_equity_pct", "risk_cluster_cap_ratio"}:
        return _format_number(value, decimals=2, pct=True)
    if key in {
        "planned_volume",
        "contract_size",
        "contracts_by_risk",
        "contracts_by_margin",
        "contracts_by_single_trade_cap",
        "selected_volume",
        "risk_cluster_cap_enabled",
        "risk_cluster_max_volume",
        "risk_cluster_selected_volume_before",
        "risk_cluster_selected_volume",
        "risk_cluster_heat_gate_enabled",
        "broker_active_order_count",
    }:
        return _format_number(value, decimals=0)
    if key in {
        "order_price",
        "strategy_entry_price",
        "stop_price",
        "stop_distance",
        "risk_per_contract",
        "total_risk",
        "margin_per_contract",
        "estimated_margin",
        "stress_margin_estimate",
        "projected_total_margin_after",
        "risk_cluster_cap_amount",
        "risk_cluster_reserved_margin_before",
        "risk_cluster_heat_gate_weight",
        "pricetick",
    }:
        return _format_number(value, decimals=2)
    return _clean(value)


def _plain_signal_block(frame: pd.DataFrame, columns: list[tuple[str, str]]) -> str:
    if frame.empty:
        return "无"
    selected = [(key, label) for key, label in columns if key in frame.columns]
    if not selected:
        return "无"
    blocks: list[str] = []
    for index, row in enumerate(frame.head(12).to_dict(orient="records"), start=1):
        vt_symbol = _clean(row.get("vt_symbol")) or f"信号{index}"
        lines = [f"信号 {index}：{vt_symbol}"]
        for key, label in selected:
            value = _format_plain_value(key, row.get(key, ""))
            lines.append(f"{label}：{value or '无'}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def _signal_subject_suffix(details: pd.DataFrame) -> str:
    if details.empty:
        return ""
    row = details.iloc[0].to_dict()
    vt_symbol = _clean(row.get("vt_symbol"))
    direction = _clean(row.get("direction"))
    offset = _clean(row.get("offset"))
    volume = _format_number(row.get("planned_volume"), decimals=0)
    if not vt_symbol:
        return ""
    suffix = f" {vt_symbol}"
    if direction or offset:
        suffix += f" {direction}/{offset}".rstrip("/")
    if volume:
        suffix += f" {volume}手"
    return suffix


def _latest_stage903_summary() -> Path | None:
    rows = sorted(
        OUTPUT_DIR.glob("qmt_roll_stage903_official_live_phase_d_controller_summary_*_stage903_official_live_phase_d_controller_v1.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return rows[0] if rows else None


def _parse_stage903_stdout(text: str) -> dict[str, Any]:
    text = text.strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.rfind("\n{")
    if start >= 0:
        try:
            return json.loads(text[start + 1 :])
        except json.JSONDecodeError:
            return {}
    return {}


def _to_int(value: Any, default: int = 0) -> int:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return default
    return int(number)


def _account_snapshot() -> dict[str, Any]:
    accounts = _read_csv_maybe(
        OUTPUT_DIR / "qmt_roll_stage174_ctp_vnpy_readonly_probe_accounts_stage174_ctp_vnpy_readonly_probe_v1.csv"
    )
    positions = _read_csv_maybe(
        OUTPUT_DIR / "qmt_roll_stage174_ctp_vnpy_readonly_probe_positions_stage174_ctp_vnpy_readonly_probe_v1.csv"
    )
    snapshot: dict[str, Any] = {
        "account_rows": int(len(accounts)),
        "position_rows": int(len(positions)),
    }
    if not accounts.empty:
        row = accounts.iloc[-1]
        for column in ("balance", "available", "frozen"):
            if column in accounts.columns:
                snapshot[column] = float(pd.to_numeric(row[column], errors="coerce"))
    if not positions.empty:
        volume = pd.to_numeric(positions.get("volume", pd.Series(dtype=float)), errors="coerce").fillna(0.0)
        snapshot["nonzero_position_rows"] = int((volume != 0).sum())
        snapshot["position_volume_sum"] = float(volume.sum())
    return snapshot


def _stage903_command(args: argparse.Namespace, target_date: str) -> list[str]:
    return [
        str(PYTHON_PATH),
        str(STAGE903_SCRIPT),
        "--target-date",
        target_date,
        "--mode",
        "dry-run",
        "--shadow-refresh-mode",
        args.shadow_refresh_mode,
        "--confirm-shadow-refresh",
        PHASE_D_SHADOW_REFRESH_CONFIRM_TEXT,
        "--readonly-refresh-mode",
        args.readonly_refresh_mode,
        "--readonly-env-profile",
        "production-live",
        "--readonly-wait-seconds",
        str(args.readonly_wait_seconds),
        "--confirm-readonly-refresh",
        PHASE_D_READONLY_REFRESH_CONFIRM_TEXT,
        "--stage251-mode",
        "skip",
        "--max-snapshot-age-seconds",
        str(args.max_snapshot_age_seconds),
    ]


def _stage903_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{PROJECT_DIR}{os.pathsep}{env.get('PYTHONPATH', '')}".rstrip(os.pathsep)
    env[PHASE_D_SHADOW_REFRESH_ENV] = "1"
    env[PHASE_D_READONLY_REFRESH_ENV] = "1"
    env[PHASE_D_SESSION_DAEMON_ENV] = "1"
    env[PHASE_D_REAL_ADAPTER_ENV] = "1"
    env.pop(PHASE_D_REAL_ENABLED_ENV, None)
    return env


def _run_stage903(args: argparse.Namespace, target_date: str, log_path: Path) -> tuple[int, dict[str, Any]]:
    cmd = _stage903_command(args, target_date)
    env = _stage903_env()
    started = datetime.now()
    result = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=args.timeout_seconds,
        check=False,
    )
    finished = datetime.now()
    log_path.write_text(
        "\n".join(
            [
                f"started_at={started:%Y-%m-%d %H:%M:%S}",
                f"finished_at={finished:%Y-%m-%d %H:%M:%S}",
                f"exit_code={result.returncode}",
                "$ " + " ".join(cmd),
                "",
                result.stdout,
            ]
        ),
        encoding="utf-8",
    )
    summary = _parse_stage903_stdout(result.stdout)
    if not summary:
        summary = _read_json(_latest_stage903_summary())
    summary["_stage903_wrapper_exit_code"] = result.returncode
    summary["_stage903_command"] = cmd
    summary["_stage903_command_log"] = str(log_path.resolve())
    return result.returncode, summary


def _status_text(summary: dict[str, Any]) -> str:
    pending = _to_int(summary.get("pending_order_count", 0))
    executable = _to_int(summary.get("stage260_executable_count", 0))
    order_api = _to_int(summary.get("order_api_called_count", 0))
    controller_status = str(summary.get("controller_status", ""))
    if order_api:
        return "异常：检测到 order API 调用，必须立即人工复核。"
    if executable > 0:
        return "有 dry-run 可执行候选；真实报单仍未启用，需要人工复核后另走 live gate。"
    if pending > 0:
        return "有理论 pending order，但 broker/dry-run 闸门未放行或需要人工复核。"
    if "blocked" in controller_status:
        return "没有可自动执行交易；控制器处于 fail-closed/block 状态。"
    return "没有可自动执行交易；当前链路只生成报告和 dry-run 状态。"


def _build_report(wrapper: dict[str, Any], stage903: dict[str, Any]) -> str:
    account = wrapper.get("account_snapshot", {}) or {}
    stage903_outputs = stage903.get("outputs", {}) if isinstance(stage903.get("outputs"), dict) else {}
    signal_details = _signal_details_frame(wrapper, stage903)
    return "\n".join(
        [
            "# C9/15w 官方自动化晚间报告",
            "",
            f"- 生成时间：`{wrapper['generated_at']}`",
            f"- 运行阶段：`{wrapper['phase']}`",
            f"- 目标日期：`{wrapper['target_date']}`",
            f"- 当前版本：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`",
            f"- Shadow 起点：`{OFFICIAL_LIVE_SHADOW_ANALYSIS_START_DATE}`",
            f"- 总结：{_status_text(stage903)}",
            "",
            "## 核心状态",
            "",
            f"- Controller：`{stage903.get('controller_status', '')}`",
            f"- Session：`{stage903.get('current_session_names', '')}`",
            f"- Stage909 shadow：`{stage903.get('stage909_shadow_refresh_status', '')}`，effective mode `{stage903.get('stage909_effective_shadow_refresh_mode', '')}`，attempted `{stage903.get('stage909_refresh_attempted', '')}`",
            f"- Stage907 readonly：`{stage903.get('stage907_refresh_status', '')}`，effective mode `{stage903.get('stage907_effective_refresh_mode', '')}`",
            f"- Stage902 readiness：`{stage903.get('stage902_overall_status', '')}`，blockers `{stage903.get('stage902_blocking_failure_count', '')}`",
            f"- Stage260 execution gate：executable `{stage903.get('stage260_executable_count', '')}`，blocked `{stage903.get('stage260_blocked_count', '')}`，skipped_flat `{stage903.get('stage260_skipped_flat_count', '')}`",
            f"- Stage905 executor dry-run：`{stage903.get('stage905_executor_status', '')}`，ready `{stage903.get('stage905_ready_count', '')}`，blocked `{stage903.get('stage905_blocked_count', '')}`",
            f"- Signal rows：`{stage903.get('signal_count', '')}`，pending orders：`{stage903.get('pending_order_count', '')}`，current positions：`{stage903.get('current_position_count', '')}`",
            f"- Order API calls：`{stage903.get('order_api_called_count', '')}`",
            "",
            "## 交易信号明细",
            "",
            _markdown_table(signal_details, SIGNAL_DETAIL_COLUMNS),
            "",
            "## 风险与资金补充",
            "",
            _markdown_table(
                signal_details,
                [
                    ("vt_symbol", "合约"),
                    ("contract_size", "合约乘数"),
                    ("pricetick", "最小跳动"),
                    ("margin_per_contract", "策略每手保证金"),
                    ("stress_margin_estimate", "broker10压力保证金合计"),
                    ("risk_to_equity_pct", "风险/权益"),
                    ("contracts_by_risk", "风险上限手数"),
                    ("contracts_by_margin", "保证金上限手数"),
                    ("contracts_by_single_trade_cap", "单笔上限手数"),
                    ("risk_cluster_name", "单产品"),
                    ("risk_cluster_cap_ratio", "单产品保证金上限"),
                    ("risk_cluster_cap_amount", "单产品上限金额"),
                    ("risk_cluster_max_volume", "单产品上限手数"),
                    ("risk_cluster_selected_volume_before", "单产品限制前手数"),
                    ("risk_cluster_selected_volume", "单产品限制后手数"),
                    ("risk_mode", "风险模式"),
                    ("risk_multiplier", "风险倍率"),
                    ("entry_context", "入场状态"),
                ],
            ),
            "",
            "## 执行闸门补充",
            "",
            _markdown_table(
                signal_details,
                [
                    ("vt_symbol", "合约"),
                    ("risk_level", "风险级别"),
                    ("readonly_gate_passed", "只读通过"),
                    ("broker_position_state", "broker持仓状态"),
                    ("broker_active_order_count", "活跃委托"),
                    ("stage905_status", "Stage905"),
                    ("stage905_reason", "Stage905原因"),
                ],
            ),
            "",
            "## 账户只读快照",
            "",
            f"- balance：`{account.get('balance', '')}`",
            f"- available：`{account.get('available', '')}`",
            f"- position rows：`{account.get('position_rows', '')}`，nonzero rows：`{account.get('nonzero_position_rows', 0)}`",
            "",
            "## 报告文件",
            "",
            f"- Stage903 report：`{stage903_outputs.get('report_md', '')}`",
            f"- Stage903 summary：`{stage903_outputs.get('summary_json', '')}`",
            f"- Wrapper command log：`{wrapper.get('command_log', '')}`",
            "",
            "## 执行纪律",
            "",
            "- 本自动化只运行 shadow、read-only、dry-run 和报告链路。",
            "- `OFFICIAL_LIVE_PHASE_D_REAL_SUBMIT_ENABLED` 未设置，真实报单默认关闭。",
            "- 若出现 pending order，也必须先看 broker 持仓/资金对账和 readiness/dry-run 结果；空仓账户不得执行历史 shadow 平仓回放。",
            "",
        ]
    )


def _write_outputs(paths: dict[str, Path], wrapper: dict[str, Any], stage903: dict[str, Any]) -> None:
    payload = dict(wrapper)
    payload["stage903_summary"] = stage903
    report = _build_report(wrapper, stage903)
    paths["summary_json"].write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths["report_md"].write_text(report, encoding="utf-8")
    LATEST_SUMMARY_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    LATEST_REPORT_PATH.write_text(report, encoding="utf-8")
    if paths["command_log"].exists():
        LATEST_COMMAND_LOG_PATH.write_text(paths["command_log"].read_text(encoding="utf-8"), encoding="utf-8")


def _email_severity(stage903: dict[str, Any], wrapper: dict[str, Any]) -> str:
    if _to_int(stage903.get("order_api_called_count"), 0) > 0 or _to_int(wrapper.get("wrapper_exit_code"), 0) != 0:
        return "critical"
    if _to_int(stage903.get("stage260_executable_count"), 0) > 0 or _to_int(stage903.get("pending_order_count"), 0) > 0:
        return "warning"
    if "blocked" in str(stage903.get("controller_status", "")):
        return "warning"
    return "info"


def _send_report_email(paths: dict[str, Path], wrapper: dict[str, Any], stage903: dict[str, Any]) -> dict[str, Any]:
    severity = _email_severity(stage903, wrapper)
    pending = _to_int(stage903.get("pending_order_count", 0))
    ready = _to_int(stage903.get("stage905_ready_count", 0))
    order_api = _to_int(stage903.get("order_api_called_count", 0))
    account = wrapper.get("account_snapshot") or {}
    signal_details = _signal_details_frame(wrapper, stage903)
    if order_api > 0:
        action_text = "检测到真实下单 API 调用，请马上人工核对委托、成交、持仓和资金。"
    elif ready > 0:
        action_text = "有已经通过 dry-run 的候选指令，但这封报告本身不会真实下单，需要继续看 Stage927/Stage931 闸门。"
    elif pending > 0:
        action_text = "策略层有理论指令，但执行闸门没有放行；暂时不要手工追单，先看阻断原因。"
    else:
        action_text = "没有需要自动执行的开仓或平仓指令。"
    subject = (
        f"[C9/15w 官方报告][{severity}] {wrapper['target_date']} "
        f"待处理={pending} 可提交={ready} 下单API={order_api}{_signal_subject_suffix(signal_details)}"
    )
    detail_text = _plain_signal_block(signal_details, SIGNAL_DETAIL_COLUMNS)
    risk_text = _plain_signal_block(
        signal_details,
        [
            ("vt_symbol", "合约"),
            ("contract_size", "合约乘数"),
            ("pricetick", "最小跳动"),
            ("margin_per_contract", "策略每手保证金"),
            ("stress_margin_estimate", "broker10压力保证金合计"),
            ("risk_to_equity_pct", "风险/权益"),
            ("contracts_by_risk", "风险上限手数"),
            ("contracts_by_margin", "保证金上限手数"),
            ("contracts_by_single_trade_cap", "单笔上限手数"),
            ("risk_cluster_name", "单产品"),
            ("risk_cluster_cap_ratio", "单产品保证金上限"),
            ("risk_cluster_cap_amount", "单产品上限金额"),
            ("risk_cluster_max_volume", "单产品上限手数"),
            ("risk_cluster_selected_volume_before", "单产品限制前手数"),
            ("risk_cluster_selected_volume", "单产品限制后手数"),
        ],
    )
    gate_text = _plain_signal_block(
        signal_details,
        [
            ("vt_symbol", "合约"),
            ("risk_level", "风险级别"),
            ("readonly_gate_passed", "只读通过"),
            ("stage260_action", "执行闸门"),
            ("stage260_reason", "阻断/原因"),
            ("stage905_status", "Stage905"),
        ],
    )
    body = "\n".join(
        [
            f"结论：{action_text}",
            f"日期：{wrapper['target_date']}，阶段：{wrapper['phase']}",
            f"信号/待执行/可提交：{stage903.get('signal_count', '')}/{pending}/{ready}",
            f"下单API：{order_api}",
            f"账户：资金 {account.get('balance', '')}，非零持仓 {account.get('nonzero_position_rows', 0)}",
            f"状态：{stage903.get('controller_status', '')}；{stage903.get('stage905_executor_status', '')}",
            "",
            "交易信号明细：",
            detail_text,
            "",
            "风险与资金补充：",
            risk_text,
            "",
            "执行闸门：",
            gate_text,
            "",
            "字段说明：策略保证金/止损/风险来自 Stage901 entry_risk；单产品保证金上限是当前实盘采用的产品级 cap，例如 rb2610 归到 rb.SHFE；这不是黑色、能化等行业集群 cap；券商实际保证金以交易软件/CTP为准；提交许可仍以 Stage260/905/927/931 为准。",
            "需要你做：有下单API或可提交指令时看账户；否则不用处理。",
        ]
    )
    return send_official_live_email_notification(
        subject=subject,
        body=body,
        event_type=f"stage929_{wrapper['phase']}",
        severity=severity,
        attachments=[paths["report_md"], paths["summary_json"]],
        metadata={
            "phase": wrapper["phase"],
            "target_date": wrapper["target_date"],
            "controller_status": stage903.get("controller_status", ""),
            "pending_order_count": stage903.get("pending_order_count", 0),
            "stage905_ready_count": stage903.get("stage905_ready_count", 0),
            "order_api_called_count": stage903.get("order_api_called_count", 0),
            "signal_details": signal_details.to_dict(orient="records"),
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Timed dry-run/report wrapper for official C9/15w live automation.")
    parser.add_argument("--phase", choices=["post-close", "evening-report", "manual"], default="manual")
    parser.add_argument("--target-date", default="")
    parser.add_argument("--shadow-refresh-mode", choices=["plan-only", "run", "auto"], default="auto")
    parser.add_argument("--readonly-refresh-mode", choices=["plan-only", "refresh", "auto"], default="auto")
    parser.add_argument("--readonly-wait-seconds", type=int, default=30)
    parser.add_argument("--max-snapshot-age-seconds", type=int, default=300)
    parser.add_argument("--timeout-seconds", type=int, default=1200)
    parser.add_argument("--allow-weekend", action="store_true")
    args = parser.parse_args()

    now = datetime.now()
    target_date = args.target_date or date.today().isoformat()
    run_id = now.strftime("%Y%m%d_%H%M%S")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    paths = _paths(args.phase, target_date, run_id)

    if now.weekday() >= 5 and not args.allow_weekend:
        stage903_summary: dict[str, Any] = {
            "controller_status": "stage929_weekend_noop",
            "target_date": target_date,
            "order_api_called_count": 0,
            "signal_count": 0,
            "pending_order_count": 0,
            "current_position_count": 0,
        }
        exit_code = 0
        paths["command_log"].write_text("weekend_noop\n", encoding="utf-8")
    else:
        exit_code, stage903_summary = _run_stage903(args, target_date, paths["command_log"])

    wrapper = {
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "phase": args.phase,
        "target_date": target_date,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "official_live_shadow_analysis_start_date": OFFICIAL_LIVE_SHADOW_ANALYSIS_START_DATE,
        "wrapper_exit_code": exit_code,
        "order_api_called_count": stage903_summary.get("order_api_called_count", 0),
        "account_snapshot": _account_snapshot(),
        "command_log": str(paths["command_log"].resolve()),
        "outputs": {key: str(value.resolve()) for key, value in paths.items()},
        "latest_outputs": {
            "summary_json": str(LATEST_SUMMARY_PATH.resolve()),
            "report_md": str(LATEST_REPORT_PATH.resolve()),
            "command_log": str(LATEST_COMMAND_LOG_PATH.resolve()),
        },
        "judgement": {
            "overfit_before": "否。Stage929 是定时执行包装器，不改策略参数。",
            "continue_before": "是。用户需要 21 点后直接看稳定路径的报告。",
            "overfit_after": "否。包装器只汇总 Stage903/只读/dry-run 输出。",
            "continue_after": "是。下一步是看日终数据是否成功刷新以及 pending/dry-run 是否出现。",
        },
    }
    wrapper["signal_details"] = _build_signal_details(wrapper, stage903_summary).to_dict(orient="records")
    _write_outputs(paths, wrapper, stage903_summary)
    wrapper["email_notification"] = _send_report_email(paths, wrapper, stage903_summary)
    _write_outputs(paths, wrapper, stage903_summary)
    print(json.dumps({"wrapper": wrapper, "stage903_summary": stage903_summary}, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
