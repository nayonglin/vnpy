from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from qmt_roll_official_execution_profile import C9_15W_PROFILE
from qmt_roll_official_live_config import (
    OFFICIAL_LIVE_ALIAS,
    OFFICIAL_LIVE_SUMMARY_PATH,
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
STAGE935_SCRIPT = PROJECT_DIR / "run_qmt_roll_stage935_official_live_monthly_ai_pool_update.py"

MODEL_TAG = "stage929_official_live_15w_timed_cycle_v1"
OUTPUT_PREFIX = "qmt_roll_stage929_official_live_15w_timed_cycle"
LATEST_SUMMARY_PATH = OUTPUT_DIR / "qmt_roll_official_live_15w_timed_cycle_latest_summary.json"
LATEST_REPORT_PATH = OUTPUT_DIR / "qmt_roll_official_live_15w_timed_cycle_latest_report.md"
LATEST_COMMAND_LOG_PATH = OUTPUT_DIR / "qmt_roll_official_live_15w_timed_cycle_latest_command.log"
STAGE260_MODEL_TAG = "stage260_official_live_daily_execution_gate_v1"
STAGE260_PREFIX = "qmt_roll_stage260_official_live_daily_execution_gate"
POST_CLOSE_RECONCILE_MAX_SNAPSHOT_AGE_SECONDS = 7200
STAGE904_MODEL_TAG = "stage904_official_live_c9_intraday_monitor_v1"
STAGE904_PREFIX = "qmt_roll_stage904_official_live_c9_intraday_monitor"
STAGE905_MODEL_TAG = "stage905_official_live_executor_dry_run_v1"
STAGE905_PREFIX = "qmt_roll_stage905_official_live_executor_dry_run"
STAGE906_MODEL_TAG = "stage906_official_live_reconciliation_worker_v1"
STAGE906_PREFIX = "qmt_roll_stage906_official_live_reconciliation_worker"
STAGE901_ENTRY_CANDIDATES_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow_entry_candidates_"
    "stage901_stage847_c9_2026_ytd_live_shadow_v1.csv"
)
STAGE182_LATEST_POOL_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage182_ai_product_pool_live_inference_latest_pool_"
    "stage182_ai_product_pool_live_inference_v1.csv"
)
STAGE608_CONTRACTS_PATH = (
    OUTPUT_DIR / "qmt_roll_stage608_readonly_tick_snapshot_probe_contracts_stage608_readonly_tick_snapshot_probe_v1.csv"
)

SIGNAL_DETAIL_COLUMNS: list[tuple[str, str]] = [
    ("product_vt_symbol", "品种"),
    ("vt_symbol", "合约"),
    ("direction", "方向"),
    ("offset", "开平"),
    ("execution_interpretation", "执行含义"),
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
    ("shadow_matching_position_volume", "Shadow已持仓"),
]

BLOCKED_CANDIDATE_COLUMNS: list[tuple[str, str]] = [
    ("report_target_date", "报告日期"),
    ("candidate_date", "候选日期"),
    ("product_vt_symbol", "品种"),
    ("contract_vt_symbol", "合约"),
    ("direction", "方向"),
    ("signal", "底层信号"),
    ("skip_reason_text", "未成最终交易原因"),
    ("planned_entry_price", "计划入场价"),
    ("stop_price", "止损价"),
    ("stop_distance", "止损距离"),
    ("selected_volume", "理论手数"),
    ("margin_per_contract", "策略每手保证金"),
    ("risk_cluster_max_volume", "单产品上限手数"),
    ("remaining_position_slots", "剩余仓位槽"),
    ("ai_pool_signal_date", "AI池评估日"),
    ("ai_pool_entry_effective_date", "AI池生效日"),
    ("ai_pool_rank_text", "AI池排名"),
    ("ai_pool_score", "AI分数"),
    ("ai_pool_top8_threshold", "Top8门槛分"),
    ("ai_pool_gap_to_top8", "距Top8门槛"),
    ("simple_trend_suitability_score", "简单适配分"),
    ("ai_drag_reasons", "主要拖分项"),
]

SKIP_REASON_TEXT: dict[str, str] = {
    "ai_product_pool_blocked": "AI池未入选",
    "max_concurrent_positions_reached": "最大持仓数已满",
    "position_slot_blocked": "仓位槽不足",
    "zero_selected_volume": "风控后手数为0",
    "margin_blocked": "保证金约束阻断",
    "risk_cluster_blocked": "单产品保证金上限阻断",
}


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


def _stage904_summary_path(target_date: str) -> Path:
    return OUTPUT_DIR / f"{STAGE904_PREFIX}_summary_{_date_key(target_date)}_{STAGE904_MODEL_TAG}.json"


def _stage904_actions_path(target_date: str) -> Path:
    return OUTPUT_DIR / f"{STAGE904_PREFIX}_actions_{_date_key(target_date)}_{STAGE904_MODEL_TAG}.csv"


def _stage906_summary_path(target_date: str) -> Path:
    return OUTPUT_DIR / f"{STAGE906_PREFIX}_summary_{_date_key(target_date)}_{STAGE906_MODEL_TAG}.json"


def _stage906_position_diff_path(target_date: str) -> Path:
    return OUTPUT_DIR / f"{STAGE906_PREFIX}_position_diff_{_date_key(target_date)}_{STAGE906_MODEL_TAG}.csv"


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


def _execution_interpretation(gate_row: dict[str, Any], intent_row: dict[str, Any]) -> str:
    stage905_status = _clean(intent_row.get("executor_status"))
    stage260_action = _clean(gate_row.get("execution_action"))
    stage260_reason = _clean(gate_row.get("execution_reason"))
    execution_source = _clean(gate_row.get("execution_source"))
    if stage905_status == "dry_run_order_request_payload_ready":
        return "Stage905已生成dry-run候选，仍需Stage927/931放行"
    if "shadow_position_already_contains_signal_open" in stage260_reason:
        return "理论shadow已持仓，不是新的自动开仓"
    if stage260_action == "simnow_executable":
        return "Stage260闸门通过，但还不是最终报单许可"
    if stage260_action == "blocked":
        return "不可执行，执行闸门已阻断"
    if execution_source == "stage901_signal_plan":
        return "理论signal_plan展示项，未进入执行器"
    return ""


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
                "execution_source": _clean(gate_row.get("execution_source")),
                "execution_interpretation": _execution_interpretation(gate_row, intent_row),
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
                "shadow_matching_position_volume": _to_float(gate_row.get("shadow_matching_position_volume"), 0.0),
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
                "shadow_matching_position_volume",
                "selected_volume",
                "selected_volume_ungated",
                "risk_cluster_max_volume",
                "remaining_position_slots",
                "ai_pool_rank",
                "ai_pool_pool_size",
            }:
                values.append(_format_number(value, decimals=0))
            elif key in {"ai_pool_score", "ai_pool_top8_threshold", "ai_pool_gap_to_top8"}:
                values.append(_format_number(value, decimals=6))
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
                "planned_entry_price",
                "simple_trend_suitability_score",
                "net_pnl_sum_60d",
                "net_pnl_sum_120d",
                "net_pnl_min_day_60d",
                "net_pnl_std_120d",
            }:
                values.append(_format_number(value, decimals=2))
            else:
                values.append(_clean(value))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def _format_plain_value(key: str, value: Any) -> str:
    if key in {
        "margin_ratio",
        "margin_to_available_pct",
        "risk_to_equity_pct",
        "risk_cluster_cap_ratio",
    }:
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
        "shadow_matching_position_volume",
        "selected_volume",
        "selected_volume_ungated",
        "risk_cluster_max_volume",
        "remaining_position_slots",
        "ai_pool_rank",
        "ai_pool_pool_size",
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
        "planned_entry_price",
        "simple_trend_suitability_score",
        "net_pnl_sum_60d",
        "net_pnl_sum_120d",
        "net_pnl_min_day_60d",
        "net_pnl_std_120d",
    }:
        return _format_number(value, decimals=2)
    if key in {"ai_pool_score", "ai_pool_top8_threshold", "ai_pool_gap_to_top8"}:
        return _format_number(value, decimals=6)
    return _clean(value)


def _plain_signal_block(frame: pd.DataFrame, columns: list[tuple[str, str]]) -> str:
    if frame.empty:
        return "无"
    selected = [(key, label) for key, label in columns if key in frame.columns]
    if not selected:
        return "无"
    blocks: list[str] = []
    for index, row in enumerate(frame.head(12).to_dict(orient="records"), start=1):
        vt_symbol = (
            _clean(row.get("vt_symbol"))
            or _clean(row.get("contract_vt_symbol"))
            or _clean(row.get("product_vt_symbol"))
            or f"信号{index}"
        )
        lines = [f"信号 {index}：{vt_symbol}"]
        for key, label in selected:
            value = _format_plain_value(key, row.get(key, ""))
            lines.append(f"{label}：{value or '无'}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def _blocked_candidate_details_frame(wrapper: dict[str, Any]) -> pd.DataFrame:
    cached = wrapper.get("blocked_candidate_details")
    if isinstance(cached, list):
        return pd.DataFrame(cached)
    return _build_blocked_candidate_details(wrapper)


def _pool_row(pool: pd.DataFrame, product_vt_symbol: str) -> dict[str, Any]:
    if pool.empty or "product_vt_symbol" not in pool.columns:
        return {}
    matched = pool[pool["product_vt_symbol"].fillna("").astype(str).eq(product_vt_symbol)]
    if matched.empty:
        return {}
    return matched.iloc[0].to_dict()


def _pool_threshold(pool: pd.DataFrame) -> tuple[float, str]:
    if pool.empty or "ai_rank" not in pool.columns:
        return 0.0, ""
    ranked = pool.copy()
    ranked["ai_rank"] = pd.to_numeric(ranked["ai_rank"], errors="coerce")
    top8 = ranked[ranked["ai_rank"].eq(8)]
    if top8.empty:
        top8 = ranked.sort_values("ai_rank").head(8).tail(1)
    if top8.empty:
        return 0.0, ""
    row = top8.iloc[0]
    return _to_float(row.get("predicted_product_suitability_probability"), 0.0), _clean(row.get("product_vt_symbol"))


def _rank_text(pool: pd.DataFrame, product_vt_symbol: str, column: str, *, higher_is_better: bool) -> tuple[int, int, float]:
    if pool.empty or column not in pool.columns or "product_vt_symbol" not in pool.columns:
        return 0, 0, 0.0
    work = pool[["product_vt_symbol", column]].copy()
    work[column] = pd.to_numeric(work[column], errors="coerce")
    work = work.dropna(subset=[column])
    if work.empty:
        return 0, 0, 0.0
    work["_rank"] = work[column].rank(method="min", ascending=not higher_is_better)
    matched = work[work["product_vt_symbol"].fillna("").astype(str).eq(product_vt_symbol)]
    if matched.empty:
        return 0, int(len(work)), 0.0
    row = matched.iloc[0]
    return int(row["_rank"]), int(len(work)), _to_float(row[column], 0.0)


def _ai_drag_reasons(pool: pd.DataFrame, product_vt_symbol: str) -> str:
    if pool.empty:
        return ""
    reasons: list[str] = []
    specs = [
        ("net_pnl_sum_60d", "60日净贡献", True),
        ("net_pnl_sum_120d", "120日净贡献", True),
        ("net_pnl_min_day_60d", "60日最大单日亏损", True),
        ("net_pnl_std_120d", "120日波动", False),
        ("trade_count_sum_20d", "20日交易次数", True),
        ("opened_count_sum_20d", "20日开仓次数", True),
        ("simple_trend_suitability_score", "简单适配分", True),
    ]
    for column, label, higher_is_better in specs:
        rank, total, value = _rank_text(pool, product_vt_symbol, column, higher_is_better=higher_is_better)
        if not total or not rank:
            continue
        is_weak_rank = rank >= max(1, total - 2)
        is_zero_activity = column in {"trade_count_sum_20d", "opened_count_sum_20d"} and abs(value) < 1e-12
        if is_weak_rank or is_zero_activity:
            if is_zero_activity and column == "trade_count_sum_20d":
                reasons.append("最近20日无交易")
            elif is_zero_activity and column == "opened_count_sum_20d":
                reasons.append("最近20日无开仓")
            else:
                reasons.append(f"{label}{_format_number(value, decimals=2)}，排名{rank}/{total}")
        if len(reasons) >= 4:
            break
    return "；".join(reasons)


def _build_blocked_candidate_details(wrapper: dict[str, Any]) -> pd.DataFrame:
    candidates = _read_csv_maybe(STAGE901_ENTRY_CANDIDATES_PATH)
    if candidates.empty:
        return pd.DataFrame()
    target_date = str(wrapper.get("target_date", ""))
    if target_date:
        if "date" not in candidates.columns:
            return pd.DataFrame()
        candidate_dates = pd.to_datetime(candidates["date"], errors="coerce").dt.strftime("%Y-%m-%d").fillna("")
        candidates = candidates[candidate_dates.eq(target_date)].copy()
        if candidates.empty:
            return pd.DataFrame()

    status = candidates.get("candidate_status", pd.Series("", index=candidates.index)).fillna("").astype(str).str.lower()
    skip_reason = candidates.get("skip_reason", pd.Series("", index=candidates.index)).fillna("").astype(str)
    passed_source = (
        candidates["passed_initial_filter"]
        if "passed_initial_filter" in candidates.columns
        else pd.Series(1, index=candidates.index)
    )
    passed_initial = pd.to_numeric(passed_source, errors="coerce").fillna(1).astype(int)
    candidates = candidates[(status.ne("opened")) & (skip_reason.str.len().gt(0)) & (passed_initial.eq(1))].copy()
    if candidates.empty:
        return pd.DataFrame()

    pool = _read_csv_maybe(STAGE182_LATEST_POOL_PATH)
    top8_threshold, top8_product = _pool_threshold(pool)
    rows: list[dict[str, Any]] = []
    for raw in candidates.to_dict(orient="records"):
        product = _clean(raw.get("product_vt_symbol")) or _product_from_vt_symbol(_clean(raw.get("contract_vt_symbol")))
        pool_row = _pool_row(pool, product)
        pool_score = _to_float(
            pool_row.get(
                "predicted_product_suitability_probability",
                raw.get("ai_product_pool_score"),
            ),
            0.0,
        )
        pool_rank = _to_int(pool_row.get("ai_rank", raw.get("ai_product_pool_rank")), 0)
        pool_size = int(len(pool)) if not pool.empty else 0
        simple_score = _to_float(pool_row.get("simple_trend_suitability_score"), 0.0)
        gap_to_top8 = top8_threshold - pool_score if top8_threshold > 0 and pool_score > 0 else 0.0
        raw_skip = _clean(raw.get("skip_reason"))
        if raw_skip == "ai_product_pool_blocked" and pool_rank and pool_size:
            reason_text = (
                f"AI池未入选：排名{pool_rank}/{pool_size}，"
                f"分数{_format_number(pool_score, decimals=6)}，"
                f"Top8门槛{_format_number(top8_threshold, decimals=6)}"
            )
            if top8_product:
                reason_text += f"（门槛品种{top8_product}）"
        else:
            reason_text = SKIP_REASON_TEXT.get(raw_skip, raw_skip or "被策略过滤")

        rows.append(
            {
                "report_target_date": target_date,
                "candidate_date": _clean(raw.get("date"))[:10],
                "product_vt_symbol": product,
                "contract_vt_symbol": _clean(raw.get("contract_vt_symbol")),
                "direction": _normal_text(raw.get("direction")),
                "signal": _clean(raw.get("signal")),
                "candidate_status": _clean(raw.get("candidate_status")),
                "skip_reason": raw_skip,
                "skip_reason_text": reason_text,
                "planned_entry_price": _to_float(raw.get("planned_entry_price"), 0.0),
                "stop_price": _to_float(raw.get("stop_price"), 0.0),
                "stop_distance": _to_float(raw.get("stop_distance"), 0.0),
                "selected_volume": _to_float(raw.get("selected_volume"), 0.0),
                "selected_volume_ungated": _to_float(raw.get("selected_volume_ungated"), 0.0),
                "margin_per_contract": _to_float(raw.get("margin_per_contract"), 0.0),
                "risk_cluster_max_volume": _to_float(raw.get("risk_cluster_max_volume"), 0.0),
                "remaining_position_slots": _to_float(raw.get("remaining_position_slots"), 0.0),
                "ai_pool_signal_date": _clean(raw.get("ai_product_pool_signal_date")),
                "ai_pool_entry_effective_date": _clean(raw.get("ai_product_pool_entry_effective_date")),
                "ai_pool_rank": pool_rank,
                "ai_pool_pool_size": pool_size,
                "ai_pool_rank_text": f"{pool_rank}/{pool_size}" if pool_rank and pool_size else "无",
                "ai_pool_score": pool_score,
                "ai_pool_top8_threshold": top8_threshold,
                "ai_pool_gap_to_top8": gap_to_top8,
                "ai_pool_top8_product": top8_product,
                "simple_trend_suitability_score": simple_score,
                "net_pnl_sum_60d": _to_float(pool_row.get("net_pnl_sum_60d"), 0.0),
                "net_pnl_sum_120d": _to_float(pool_row.get("net_pnl_sum_120d"), 0.0),
                "net_pnl_min_day_60d": _to_float(pool_row.get("net_pnl_min_day_60d"), 0.0),
                "net_pnl_std_120d": _to_float(pool_row.get("net_pnl_std_120d"), 0.0),
                "trade_count_sum_20d": _to_float(pool_row.get("trade_count_sum_20d"), 0.0),
                "opened_count_sum_20d": _to_float(pool_row.get("opened_count_sum_20d"), 0.0),
                "ai_drag_reasons": _ai_drag_reasons(pool, product),
            }
        )
    result = pd.DataFrame(rows)
    if "ai_pool_rank" in result.columns:
        result.sort_values(["ai_pool_rank", "product_vt_symbol"], inplace=True, na_position="last")
    result.reset_index(drop=True, inplace=True)
    return result


def _signal_subject_suffix(details: pd.DataFrame) -> str:
    if details.empty:
        return ""
    if "stage905_status" not in details.columns:
        return ""
    actionable = details[details["stage905_status"].fillna("").astype(str).eq("dry_run_order_request_payload_ready")]
    if actionable.empty:
        return ""
    row = actionable.iloc[0].to_dict()
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


def _match_frame(frame: pd.DataFrame, vt_symbol: str, direction: str) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    matched = frame.copy()
    if "vt_symbol" not in matched.columns or "direction" not in matched.columns:
        return pd.DataFrame()
    return matched[
        matched["vt_symbol"].fillna("").astype(str).eq(vt_symbol)
        & matched["direction"].map(_normal_text).eq(direction)
    ].copy()


def _yes_no(condition: bool) -> str:
    return "是" if condition else "否"


def _build_manual_strategy_takeover_rows(
    *,
    stage905_intents: pd.DataFrame,
    stage904_actions: pd.DataFrame,
    position_diff: pd.DataFrame,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if position_diff.empty:
        return rows
    for raw in position_diff.to_dict(orient="records"):
        vt_symbol = _clean(raw.get("vt_symbol"))
        direction = _normal_text(raw.get("direction"))
        broker_volume = _to_float(raw.get("broker_volume"), 0.0)
        shadow_volume = _to_float(raw.get("shadow_volume"), 0.0)
        if not vt_symbol or direction not in {"long", "short"} or broker_volume <= shadow_volume:
            continue

        intent_rows = _match_frame(stage905_intents, vt_symbol, direction)
        skipped_strategy_open = intent_rows[
            intent_rows.get("executor_status", pd.Series("", index=intent_rows.index))
            .fillna("")
            .astype(str)
            .eq("skipped_existing_broker_position")
        ].copy()
        action_rows = _match_frame(stage904_actions, vt_symbol, direction)
        broker_action_rows = action_rows[
            action_rows.get("position_source", pd.Series("", index=action_rows.index)).fillna("").astype(str).eq("broker")
        ].copy()
        action = broker_action_rows.iloc[0].to_dict() if not broker_action_rows.empty else {}
        entry_day_active = _to_int(action.get("entry_day_active"), 0) == 1
        monitor_action = _clean(action.get("monitor_action"))
        realtime_takeover = bool(
            not skipped_strategy_open.empty
            and entry_day_active
            and monitor_action in {"watch", "watch_progress_hit_no_initial_stop", "close_dry_run"}
        )
        rows.append(
            {
                "vt_symbol": vt_symbol,
                "direction": direction,
                "shadow_volume": shadow_volume,
                "broker_volume": broker_volume,
                "delta_broker_minus_shadow": _to_float(raw.get("delta_broker_minus_shadow"), broker_volume - shadow_volume),
                "matches_stage901_open_signal": int(not skipped_strategy_open.empty),
                "realtime_c9_takeover": int(realtime_takeover),
                "daily_shadow_takeover": 0,
                "takeover_scope": (
                    "当日C9实时止损已接管，日线级退出仍需broker/shadow对齐"
                    if realtime_takeover
                    else "未接管或证据不足"
                ),
                "monitor_action": monitor_action,
                "monitor_reason": _clean(action.get("monitor_reason")),
                "entry_day_active": int(entry_day_active),
                "fill_price": _to_float(action.get("fill_price"), 0.0),
                "fill_price_source": _clean(action.get("fill_price_source")),
                "initial_stop_price": _to_float(action.get("initial_stop_price"), 0.0),
                "stage847_stop_price": _to_float(action.get("stage847_stop_price"), 0.0),
                "stage847_progress_price": _to_float(action.get("stage847_progress_price"), 0.0),
            }
        )
    return rows


def _build_execution_consistency_audit(wrapper: dict[str, Any], stage903: dict[str, Any]) -> dict[str, Any]:
    target_date = _clean(stage903.get("target_date")) or _clean(wrapper.get("target_date"))
    stage901 = _read_json(OFFICIAL_LIVE_SUMMARY_PATH)
    stage904_summary = _read_json(_stage904_summary_path(target_date))
    stage906_summary = _read_json(_stage906_summary_path(target_date))
    stage905_intents = _read_csv_maybe(_stage905_intents_path(target_date))
    stage904_actions = _read_csv_maybe(_stage904_actions_path(target_date))
    position_diff = _read_csv_maybe(_stage906_position_diff_path(target_date))
    ai_pool = wrapper.get("ai_pool_preflight") or {}
    minute_audit = stage901.get("minute_audit", {}) if isinstance(stage901.get("minute_audit"), dict) else {}
    live_stop_alignment = (
        stage901.get("live_stop_alignment", {}) if isinstance(stage901.get("live_stop_alignment"), dict) else {}
    )

    pending_count = _to_int(stage901.get("pending_order_count", stage903.get("pending_order_count", 0)), 0)
    stage903_pending = _to_int(stage903.get("pending_order_count"), 0)
    stage905_intent_count = int(len(stage905_intents))
    stage905_ready = _to_int(stage903.get("stage905_ready_count"), 0)
    stage905_skipped_existing = (
        int(
            stage905_intents.get("executor_status", pd.Series(dtype=str))
            .fillna("")
            .astype(str)
            .eq("skipped_existing_broker_position")
            .sum()
        )
        if not stage905_intents.empty
        else 0
    )
    stage901_date = _clean(stage901.get("analysis_end") or stage901.get("latest_available_data_date"))
    ai_expected = _clean(ai_pool.get("expected_eval_date"))
    ai_current = _clean(ai_pool.get("current_eval_date"))
    ai_pool_ok = bool(
        ai_pool.get("automation_status") in {"monthly_ai_pool_already_current", "monthly_ai_pool_updated"}
        and (not ai_expected or not ai_current or ai_expected == ai_current)
    )
    minute_ok = bool(minute_audit.get("source_exists") is True and _to_int(minute_audit.get("loaded_symbol_count"), 0) > 0)
    signal_ok = bool(stage901_date == target_date and stage903_pending == pending_count)
    intent_ok = bool((pending_count == 0 and stage905_intent_count == 0) or stage905_intent_count >= pending_count)
    reconciliation_status = _clean(stage906_summary.get("reconciliation_status", stage903.get("stage906_reconciliation_status")))
    broker_aligned = reconciliation_status == "reconcile_aligned"
    manual_rows = _build_manual_strategy_takeover_rows(
        stage905_intents=stage905_intents,
        stage904_actions=stage904_actions,
        position_diff=position_diff,
    )
    misaligned_position_rows = (
        int((pd.to_numeric(position_diff.get("aligned", pd.Series(dtype=float)), errors="coerce").fillna(0.0) != 1.0).sum())
        if not position_diff.empty
        else 0
    )
    manual_strategy_count = sum(1 for row in manual_rows if _to_int(row.get("matches_stage901_open_signal"), 0) == 1)
    realtime_takeover_count = sum(1 for row in manual_rows if _to_int(row.get("realtime_c9_takeover"), 0) == 1)
    if manual_strategy_count and realtime_takeover_count == manual_strategy_count:
        manual_status = "识别到手动补开的策略仓；当日C9实时止损已接管；日线级退出仍需broker/shadow对齐"
    elif manual_strategy_count:
        manual_status = "识别到手动补开的策略仓，但实时止损接管证据不足，请看明细原因"
    elif misaligned_position_rows > 0:
        manual_status = "存在broker/shadow仓位差异，但未识别为当日策略手动补仓"
    elif not broker_aligned and _to_int(stage906_summary.get("broker_snapshot_ready"), 0) != 1:
        manual_status = "broker快照过期或不可用，暂不能判断是否有手动策略仓差异"
    else:
        manual_status = "无手动策略仓差异"

    return {
        "target_date": target_date,
        "stage901_analysis_date": stage901_date,
        "signal_consistency": _yes_no(signal_ok),
        "ai_pool_consistency": _yes_no(ai_pool_ok),
        "minute_data_consistency": _yes_no(minute_ok),
        "execution_intent_consistency": _yes_no(intent_ok),
        "broker_position_consistency": _yes_no(broker_aligned),
        "stage901_pending_order_count": pending_count,
        "stage903_pending_order_count": stage903_pending,
        "stage905_intent_count": stage905_intent_count,
        "stage905_ready_count": stage905_ready,
        "stage905_skipped_existing_broker_position_count": stage905_skipped_existing,
        "stage904_monitor_status": _clean(stage904_summary.get("monitor_status", stage903.get("stage904_monitor_status"))),
        "stage904_close_dry_run_count": _to_int(stage904_summary.get("close_dry_run_count"), 0),
        "stage904_action_count": _to_int(stage904_summary.get("action_count"), 0),
        "stage906_reconciliation_status": reconciliation_status,
        "stage906_account_state_alignment": _clean(
            stage906_summary.get("account_state_alignment", stage903.get("stage906_account_state_alignment"))
        ),
        "stage906_broker_snapshot_ready": _to_int(stage906_summary.get("broker_snapshot_ready"), 0),
        "stage906_readonly_snapshot_age_seconds": _to_float(
            stage906_summary.get("readonly_snapshot_age_seconds"), 0.0
        ),
        "stage906_max_snapshot_age_seconds": _to_int(
            stage906_summary.get("max_snapshot_age_seconds", stage903.get("stage906_max_snapshot_age_seconds")), 0
        ),
        "stage906_position_diff_rows": _to_int(stage906_summary.get("position_diff_rows"), 0),
        "stage906_misaligned_position_rows": misaligned_position_rows,
        "manual_strategy_position_count": manual_strategy_count,
        "manual_strategy_realtime_takeover_count": realtime_takeover_count,
        "manual_strategy_takeover_status": manual_status,
        "manual_strategy_takeover_rows": manual_rows,
        "live_stop_alignment_event_count": _to_int(live_stop_alignment.get("event_count"), 0),
        "live_stop_alignment_position_adjustment_count": _to_int(
            live_stop_alignment.get("position_adjustment_count"), 0
        ),
        "live_stop_alignment_position_removed_count": _to_int(live_stop_alignment.get("position_removed_count"), 0),
        "live_stop_alignment_signal_plan_suppressed_count": _to_int(
            live_stop_alignment.get("signal_plan_suppressed_count"), 0
        ),
        "live_stop_alignment_pending_order_suppressed_count": _to_int(
            live_stop_alignment.get("pending_order_suppressed_count"), 0
        ),
        "minute_audit": minute_audit,
        "ai_pool_expected_eval_date": ai_expected,
        "ai_pool_current_eval_date": ai_current,
        "ai_pool_status": _clean(ai_pool.get("automation_status")),
        "stop_takeover_policy": (
            "匹配当日Stage901策略信号、broker只读成交可识别、Stage904显示entry_day_active=1时，"
            "C9 0.5R实时止损可由Stage904/905/931 close-only链路自动执行；"
            "日线级止盈/止损/退出必须等待broker/shadow对齐或明确接管，不能静默把非策略仓位当成策略仓。"
        ),
    }


def _execution_consistency_audit(wrapper: dict[str, Any], stage903: dict[str, Any]) -> dict[str, Any]:
    cached = wrapper.get("execution_consistency_audit")
    if isinstance(cached, dict):
        return cached
    return _build_execution_consistency_audit(wrapper, stage903)


def _manual_takeover_plain_block(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "无"
    blocks: list[str] = []
    for index, row in enumerate(rows[:12], start=1):
        blocks.append(
            "\n".join(
                [
                    f"仓位 {index}：{_clean(row.get('vt_symbol'))}",
                    f"方向：{_clean(row.get('direction'))}",
                    f"shadow手数：{_format_number(row.get('shadow_volume'), decimals=0) or '0'}",
                    f"broker手数：{_format_number(row.get('broker_volume'), decimals=0) or '0'}",
                    f"匹配策略开仓信号：{_yes_no(_to_int(row.get('matches_stage901_open_signal'), 0) == 1)}",
                    f"C9实时止损接管：{_yes_no(_to_int(row.get('realtime_c9_takeover'), 0) == 1)}",
                    f"日线级退出接管：{_yes_no(_to_int(row.get('daily_shadow_takeover'), 0) == 1)}",
                    f"接管范围：{_clean(row.get('takeover_scope'))}",
                    f"成交价来源：{_clean(row.get('fill_price_source')) or '无'}",
                    f"成交价：{_format_number(row.get('fill_price'), decimals=2) or '无'}",
                    f"初始止损：{_format_number(row.get('initial_stop_price'), decimals=2) or '无'}",
                    f"C9 0.5R止损：{_format_number(row.get('stage847_stop_price'), decimals=2) or '无'}",
                    f"C9进展价：{_format_number(row.get('stage847_progress_price'), decimals=2) or '无'}",
                    f"当前监控动作：{_clean(row.get('monitor_action')) or '无'}",
                    f"监控原因：{_clean(row.get('monitor_reason')) or '无'}",
                ]
            )
        )
    return "\n\n".join(blocks)


def _consistency_plain_block(audit: dict[str, Any]) -> str:
    minute_audit = audit.get("minute_audit", {}) if isinstance(audit.get("minute_audit"), dict) else {}
    lines = [
        "实盘/回测一致性：",
        f"策略信号一致：{audit.get('signal_consistency', '')}（Stage901数据日 {audit.get('stage901_analysis_date', '')}，目标日 {audit.get('target_date', '')}）",
        f"AI池一致：{audit.get('ai_pool_consistency', '')}（状态 {audit.get('ai_pool_status', '')}，应为 {audit.get('ai_pool_expected_eval_date', '')}，当前 {audit.get('ai_pool_current_eval_date', '')}）",
        f"分钟K接入：{audit.get('minute_data_consistency', '')}（已加载品种数 {minute_audit.get('loaded_symbol_count', '')}）",
        f"执行意图一致：{audit.get('execution_intent_consistency', '')}（Stage901待处理 {audit.get('stage901_pending_order_count', '')}，Stage905意图 {audit.get('stage905_intent_count', '')}，可提交 {audit.get('stage905_ready_count', '')}）",
        (
            "实盘仓位一致："
            f"{audit.get('broker_position_consistency', '')}"
            f"（Stage906 {audit.get('stage906_reconciliation_status', '')}，"
            f"差异行 {audit.get('stage906_position_diff_rows', '')}，"
            f"未对齐行 {audit.get('stage906_misaligned_position_rows', '')}，"
            f"快照年龄 {_format_number(audit.get('stage906_readonly_snapshot_age_seconds'), decimals=0) or '无'}秒/"
            f"上限 {audit.get('stage906_max_snapshot_age_seconds', '')}秒）"
        ),
        f"实时止损监控：{audit.get('stage904_monitor_status', '')}（动作 {audit.get('stage904_action_count', '')}，平仓dry-run {audit.get('stage904_close_dry_run_count', '')}）",
        (
            "Shadow实时止损对齐："
            f"事件 {audit.get('live_stop_alignment_event_count', '')}，"
            f"扣减 {audit.get('live_stop_alignment_position_adjustment_count', '')}，"
            f"移除持仓 {audit.get('live_stop_alignment_position_removed_count', '')}，"
            f"抑制理论开仓 {audit.get('live_stop_alignment_signal_plan_suppressed_count', '')}，"
            f"抑制pending {audit.get('live_stop_alignment_pending_order_suppressed_count', '')}"
        ),
        f"手动策略仓接管：{audit.get('manual_strategy_takeover_status', '')}",
        f"止盈止损接管规则：{audit.get('stop_takeover_policy', '')}",
        "",
        "手动/差异仓位明细：",
        _manual_takeover_plain_block(
            audit.get("manual_strategy_takeover_rows", [])
            if isinstance(audit.get("manual_strategy_takeover_rows"), list)
            else []
        ),
    ]
    return "\n".join(lines)


def _stage903_command(args: argparse.Namespace, target_date: str) -> list[str]:
    readonly_refresh_mode = str(args.readonly_refresh_mode)
    if args.phase == "post-close" and readonly_refresh_mode == "auto":
        readonly_refresh_mode = "plan-only"
    cmd = [
        str(PYTHON_PATH),
        str(STAGE903_SCRIPT),
        "--execution-profile",
        C9_15W_PROFILE.profile_key,
        "--target-date",
        target_date,
        "--mode",
        "dry-run",
        "--shadow-refresh-mode",
        args.shadow_refresh_mode,
        "--confirm-shadow-refresh",
        PHASE_D_SHADOW_REFRESH_CONFIRM_TEXT,
        "--readonly-refresh-mode",
        readonly_refresh_mode,
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
    if args.phase == "post-close":
        cmd.extend(
            [
                "--reconciliation-max-snapshot-age-seconds",
                str(args.post_close_reconcile_snapshot_age_seconds),
            ]
        )
    if args.phase == "evening-report":
        # Stage930 owns the single persistent tick stream and the only fast
        # Stage904/905 lane during the active night session.  Stage929 remains
        # a report/controller wrapper and must not cold-refresh or overwrite
        # those shared intraday artifacts at 21:05.
        cmd.extend(
            [
                "--intraday-tick-refresh-mode",
                "skip",
                "--intraday-execution-mode",
                "external",
            ]
        )
    return cmd


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


def _run_stage935_preflight(args: argparse.Namespace, log_path: Path) -> dict[str, Any]:
    mode = str(args.ai_pool_preflight_mode)
    if mode == "skip":
        return {
            "preflight_status": "ai_pool_preflight_skipped",
            "exit_code": 0,
            "automation_status": "skipped",
            "allowed_to_continue": 1,
        }
    cmd = [
        str(PYTHON_PATH),
        str(STAGE935_SCRIPT),
        "--mode",
        "run" if mode == "run" else "check",
        "--email-policy",
        "changes" if mode == "run" else "never",
    ]
    started = datetime.now()
    result = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=args.ai_pool_timeout_seconds,
        check=False,
    )
    finished = datetime.now()
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(
            "\n".join(
                [
                    f"stage935_started_at={started:%Y-%m-%d %H:%M:%S}",
                    f"stage935_finished_at={finished:%Y-%m-%d %H:%M:%S}",
                    f"stage935_exit_code={result.returncode}",
                    "$ " + " ".join(cmd),
                    "",
                    result.stdout,
                    "",
                ]
            )
        )
    summary = _parse_stage903_stdout(result.stdout)
    status = str(summary.get("automation_status", ""))
    allowed = int(result.returncode == 0 and status in {"monthly_ai_pool_already_current", "monthly_ai_pool_updated"})
    return {
        "preflight_status": "ai_pool_preflight_passed" if allowed else "ai_pool_preflight_blocked",
        "exit_code": result.returncode,
        "automation_status": status,
        "action": summary.get("action", ""),
        "expected_eval_date": summary.get("expected_eval_date", ""),
        "current_eval_date": summary.get("current_eval_date", ""),
        "resolved_target_date": summary.get("resolved_target_date", ""),
        "blockers": summary.get("blockers", []),
        "warnings": summary.get("warnings", []),
        "order_api_called_count": summary.get("order_api_called_count", 0),
        "allowed_to_continue": allowed,
        "summary": summary,
    }


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
    blocked_candidates = _blocked_candidate_details_frame(wrapper)
    ai_pool = wrapper.get("ai_pool_preflight") or {}
    consistency_audit = _execution_consistency_audit(wrapper, stage903)
    return "\n".join(
        [
            "# C9/15w 官方自动化晚间报告",
            "",
            f"- 生成时间：`{wrapper['generated_at']}`",
            f"- 运行阶段：`{wrapper['phase']}`",
            f"- 目标日期：`{wrapper['target_date']}`",
            f"- 当前版本：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`",
            f"- Shadow 起点：`{OFFICIAL_LIVE_SHADOW_ANALYSIS_START_DATE}`",
            f"- AI池检查：`{ai_pool.get('automation_status', '')}`，expected `{ai_pool.get('expected_eval_date', '')}`，current `{ai_pool.get('current_eval_date', '')}`",
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
            "## 实盘/回测一致性",
            "",
            _consistency_plain_block(consistency_audit),
            "",
            "## 交易信号明细",
            "",
            _markdown_table(signal_details, SIGNAL_DETAIL_COLUMNS),
            "",
            "## 底层候选但未成最终交易",
            "",
            _markdown_table(blocked_candidates, BLOCKED_CANDIDATE_COLUMNS),
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
                    ("execution_interpretation", "执行含义"),
                    ("risk_level", "风险级别"),
                    ("readonly_gate_passed", "只读通过"),
                    ("broker_position_state", "broker持仓状态"),
                    ("shadow_matching_position_volume", "Shadow已持仓"),
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


def _send_report_email(
    paths: dict[str, Path],
    wrapper: dict[str, Any],
    stage903: dict[str, Any],
    *,
    policy: str,
) -> dict[str, Any]:
    if policy == "never":
        return {"email_status": "skipped_by_policy", "email_policy": policy}
    severity = _email_severity(stage903, wrapper)
    pending = _to_int(stage903.get("pending_order_count", 0))
    ready = _to_int(stage903.get("stage905_ready_count", 0))
    order_api = _to_int(stage903.get("order_api_called_count", 0))
    account = wrapper.get("account_snapshot") or {}
    ai_pool = wrapper.get("ai_pool_preflight") or {}
    signal_details = _signal_details_frame(wrapper, stage903)
    blocked_candidates = _blocked_candidate_details_frame(wrapper)
    consistency_audit = _execution_consistency_audit(wrapper, stage903)
    blocked_count = int(len(blocked_candidates))
    if order_api > 0:
        action_text = "检测到真实下单 API 调用，请马上人工核对委托、成交、持仓和资金。"
    elif ready > 0:
        action_text = "有已经通过 dry-run 的候选指令，但这封报告本身不会真实下单，需要继续看 Stage927/Stage931 闸门。"
    elif pending > 0:
        action_text = "策略层有理论指令，但执行闸门没有放行；暂时不要手工追单，先看阻断原因。"
    elif blocked_count > 0:
        action_text = f"没有最终可执行指令；有 {blocked_count} 个底层候选被策略过滤，原因见下方。"
    else:
        action_text = "没有需要自动执行的开仓或平仓指令。"
    subject = (
        f"[C9/15w 官方报告][{severity}] {wrapper['target_date']} "
        f"待处理={pending} 可提交={ready} 过滤候选={blocked_count} "
        f"下单API={order_api}{_signal_subject_suffix(signal_details)}"
    )
    detail_text = _plain_signal_block(signal_details, SIGNAL_DETAIL_COLUMNS)
    blocked_text = _plain_signal_block(blocked_candidates, BLOCKED_CANDIDATE_COLUMNS)
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
            ("execution_interpretation", "执行含义"),
            ("risk_level", "风险级别"),
            ("readonly_gate_passed", "只读通过"),
            ("stage260_action", "执行闸门"),
            ("stage260_reason", "阻断/原因"),
            ("shadow_matching_position_volume", "Shadow已持仓"),
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
            f"AI池：{ai_pool.get('automation_status', '')}，应为 {ai_pool.get('expected_eval_date', '')}，当前 {ai_pool.get('current_eval_date', '')}",
            f"状态：{stage903.get('controller_status', '')}；{stage903.get('stage905_executor_status', '')}",
            "",
            _consistency_plain_block(consistency_audit),
            "",
            "交易信号明细：",
            detail_text,
            "",
            "底层候选但未成最终交易：",
            blocked_text,
            "",
            "风险与资金补充：",
            risk_text,
            "",
            "执行闸门：",
            gate_text,
            "",
            "字段说明：策略保证金/止损/风险来自 Stage901 entry_risk；单产品保证金上限是当前实盘采用的产品级 cap，例如 rb2610 归到 rb.SHFE；这不是黑色、能化等行业集群 cap；券商实际保证金以交易软件/CTP为准；提交许可仍以 Stage260/905/927/931 为准。",
            "16:35仓位对账：若15:08日盘收后只读快照可用，会用于提前预警broker/shadow是否一致；这不是下单许可，20:55/交易时段仍必须重新拉300秒内fresh快照和盘口。",
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
            "blocked_candidate_details": blocked_candidates.to_dict(orient="records"),
            "execution_consistency_audit": consistency_audit,
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
    parser.add_argument(
        "--post-close-reconcile-snapshot-age-seconds",
        type=int,
        default=POST_CLOSE_RECONCILE_MAX_SNAPSHOT_AGE_SECONDS,
        help="16:35 post-close preview reconciliation age limit; does not relax live submit gates.",
    )
    parser.add_argument("--timeout-seconds", type=int, default=1200)
    parser.add_argument("--ai-pool-preflight-mode", choices=["skip", "check", "run"], default="run")
    parser.add_argument("--ai-pool-timeout-seconds", type=int, default=3600)
    parser.add_argument("--email-policy", choices=["always", "never"], default="always")
    parser.add_argument("--allow-weekend", action="store_true")
    args = parser.parse_args()

    now = datetime.now()
    target_date = args.target_date or date.today().isoformat()
    run_id = now.strftime("%Y%m%d_%H%M%S")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    paths = _paths(args.phase, target_date, run_id)

    ai_pool_preflight = {"preflight_status": "not_run_weekend_noop", "allowed_to_continue": 1}
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
        ai_pool_preflight = _run_stage935_preflight(args, paths["command_log"])
        if int(ai_pool_preflight.get("allowed_to_continue", 0)) != 1:
            stage903_summary = {
                "controller_status": "stage929_ai_pool_preflight_blocked_fail_closed",
                "target_date": target_date,
                "order_api_called_count": 0,
                "signal_count": 0,
                "pending_order_count": 0,
                "current_position_count": 0,
                "stage260_executable_count": 0,
                "stage905_ready_count": 0,
                "stage905_executor_status": "executor_skipped_ai_pool_preflight_blocked",
                "ai_pool_preflight": ai_pool_preflight,
            }
            exit_code = 2
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
        "requested_readonly_refresh_mode": args.readonly_refresh_mode,
        "effective_readonly_refresh_mode": (
            "plan-only"
            if args.phase == "post-close" and str(args.readonly_refresh_mode) == "auto"
            else args.readonly_refresh_mode
        ),
        "effective_reconciliation_snapshot_age_seconds": (
            int(args.post_close_reconcile_snapshot_age_seconds)
            if args.phase == "post-close"
            else int(args.max_snapshot_age_seconds)
        ),
        "account_snapshot": _account_snapshot(),
        "ai_pool_preflight": ai_pool_preflight,
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
    wrapper["blocked_candidate_details"] = _build_blocked_candidate_details(wrapper).to_dict(orient="records")
    wrapper["execution_consistency_audit"] = _build_execution_consistency_audit(wrapper, stage903_summary)
    _write_outputs(paths, wrapper, stage903_summary)
    wrapper["email_notification"] = _send_report_email(
        paths,
        wrapper,
        stage903_summary,
        policy=str(args.email_policy),
    )
    _write_outputs(paths, wrapper, stage903_summary)
    print(json.dumps({"wrapper": wrapper, "stage903_summary": stage903_summary}, ensure_ascii=False, indent=2, default=str))
    raise SystemExit(int(exit_code or 0))


if __name__ == "__main__":
    main()
