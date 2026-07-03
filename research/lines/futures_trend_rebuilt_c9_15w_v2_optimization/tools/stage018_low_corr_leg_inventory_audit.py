from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any, Iterable

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[4]
PORTFOLIO_OUTPUT_DIR = PROJECT_DIR / "examples" / "portfolio_backtesting" / "backtest_outputs"
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage018"
MODEL_TAG = "stage018_low_corr_leg_inventory_audit_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage018_low_corr_leg_inventory_audit"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage018_low_corr_leg_inventory_audit"
STAGES_DIR = LINE_DIR / "stages"

INVENTORY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_inventory_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
STAGE_RECORD_PATH = STAGES_DIR / "20260702_0612_stage018_low_corr_leg_inventory_audit.md"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return str(value)
    return value


def _read_columns(path: Path) -> list[str]:
    if path.suffix.lower() != ".csv":
        return []
    try:
        return list(pd.read_csv(path, nrows=5, encoding="utf-8-sig").columns)
    except Exception:
        return []


def inventory_file(
    name: str,
    path: Path,
    *,
    required_for: str,
    required_columns: Iterable[str] = (),
    group: str = "general",
) -> dict[str, Any]:
    required = tuple(required_columns)
    exists = path.exists()
    columns = _read_columns(path) if exists else []
    missing_columns = tuple(column for column in required if column not in columns)
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "name": name,
        "group": group,
        "path": str(path.relative_to(PROJECT_DIR) if path.is_absolute() and path.is_relative_to(PROJECT_DIR) else path),
        "required_for": required_for,
        "exists": bool(exists),
        "size_bytes": int(path.stat().st_size) if exists else 0,
        "status": "present" if exists else "missing",
        "required_columns": ",".join(required),
        "observed_columns": ",".join(columns[:80]),
        "missing_columns": ",".join(missing_columns),
        "has_required_columns": bool(exists and not missing_columns),
    }


def _has_present_group(inventory: list[dict[str, Any]], group: str) -> bool:
    rows = [row for row in inventory if row.get("group") == group]
    return bool(rows) and all(row.get("status") == "present" and row.get("has_required_columns", True) for row in rows)


def _any_present_group(inventory: list[dict[str, Any]], group: str) -> bool:
    return any(
        row.get("group") == group and row.get("status") == "present" and row.get("has_required_columns", True)
        for row in inventory
    )


def _missing_names(inventory: list[dict[str, Any]], group: str) -> list[str]:
    return [
        str(row.get("name"))
        for row in inventory
        if row.get("group") == group and (row.get("status") != "present" or not row.get("has_required_columns", True))
    ]


def assess_reuse_gate(inventory: list[dict[str, Any]]) -> dict[str, Any]:
    old_outputs_present = _has_present_group(inventory, "old_xsmom_output")
    raw_inputs_present = _has_present_group(inventory, "xsmom_raw_input")
    c9_curve_margin_available = _any_present_group(inventory, "current_c9_margin")
    c9_full_positions_available = _has_present_group(inventory, "current_c9_full_period_positions")
    can_true_combo_now = raw_inputs_present and c9_curve_margin_available and c9_full_positions_available

    if not raw_inputs_present:
        decision = "stage018_rebuild_xsmom_inputs_first_keep_readonly"
        next_step = "先重建 Stage345 product_returns/satellite_daily，再按当前 C9 独立资金袖做非挤占 proxy。"
    elif not c9_full_positions_available:
        decision = "stage018_rebuild_c9_positions_before_true_combo_keep_readonly"
        next_step = "xsmom 输入可用后，还要补当前 C9 全周期逐日 positions/product margin，才能做真组合保证金。"
    elif can_true_combo_now:
        decision = "stage018_ready_for_stage019_true_combo_ab"
        next_step = "进入 Stage019：固定 xsmom 规则 + 当前 C9 资金袖/保证金约束真组合 A/B。"
    else:
        decision = "stage018_inventory_incomplete_keep_readonly"
        next_step = "补齐缺失输入后再评估，不做策略变更。"

    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "decision": decision,
        "can_directly_reuse_old_xsmom_outputs": bool(old_outputs_present),
        "can_rebuild_standalone_xsmom_now": bool(raw_inputs_present),
        "current_c9_curve_margin_available": bool(c9_curve_margin_available),
        "current_c9_full_period_positions_available": bool(c9_full_positions_available),
        "can_run_current_c9_true_xsmom_combo_now": bool(can_true_combo_now),
        "missing_old_xsmom_outputs": _missing_names(inventory, "old_xsmom_output"),
        "missing_xsmom_raw_inputs": _missing_names(inventory, "xsmom_raw_input"),
        "missing_current_c9_full_period_positions": _missing_names(inventory, "current_c9_full_period_positions"),
        "next_step": next_step,
    }


def build_inventory() -> list[dict[str, Any]]:
    stage167_curve_columns = ("account_equity", "total_margin_exact", "broker10_margin_to_equity_pct")
    specs = [
        (
            "stage208_record",
            PROJECT_DIR
            / "research/lines/futures_trend_drawdown30_preserve_return/stages/20260601_1809_stage208_xsmom_true_carry_replay.md",
            "historical_xsmom_evidence",
            "历史 xsmom 真承载正向证据",
            (),
        ),
        (
            "stage214_record",
            PROJECT_DIR
            / "research/lines/futures_trend_drawdown30_preserve_return/stages/20260601_1851_stage214_stage208_exact_position_margin_audit.md",
            "historical_xsmom_evidence",
            "历史 xsmom 精确保证金否决证据",
            (),
        ),
        (
            "stage352_combo_daily",
            PORTFOLIO_OUTPUT_DIR
            / "qmt_roll_stage352_xsmom_overlay_cash_multiperiod_combo_daily_stage352_xsmom_overlay_cash_multiperiod_v1.csv",
            "old_xsmom_output",
            "旧 Stage402/403 xsmom 复用输入",
            (),
        ),
        (
            "stage352_margin",
            PORTFOLIO_OUTPUT_DIR
            / "qmt_roll_stage352_xsmom_overlay_cash_multiperiod_margin_stage352_xsmom_overlay_cash_multiperiod_v1.csv",
            "old_xsmom_output",
            "旧 Stage402/403 xsmom 保证金输入",
            (),
        ),
        (
            "stage508_true_xsmom_daily",
            PORTFOLIO_OUTPUT_DIR
            / "qmt_roll_stage508_xsmom_true_carry_replay_daily_stage508_xsmom_true_carry_replay_v1.csv",
            "old_xsmom_output",
            "旧 Stage508 真承载日度输出",
            (),
        ),
        (
            "stage513_exact_margin_daily",
            PORTFOLIO_OUTPUT_DIR
            / "qmt_roll_stage513_stage208_exact_position_margin_audit_margin_daily_stage513_stage208_exact_position_margin_audit_v1.csv",
            "old_xsmom_output",
            "旧 Stage513 精确保证金输出",
            (),
        ),
        (
            "stage345_product_returns",
            PORTFOLIO_OUTPUT_DIR
            / "qmt_roll_stage345_cross_sectional_momentum_satellite_product_returns_stage345_cross_sectional_momentum_satellite_v1.csv",
            "xsmom_raw_input",
            "重建 standalone xsmom 的产品收益输入",
            ("date", "product_vt_symbol", "main_contract_vt", "main_close", "product_return"),
        ),
        (
            "stage345_satellite_daily",
            PORTFOLIO_OUTPUT_DIR
            / "qmt_roll_stage345_cross_sectional_momentum_satellite_satellite_daily_stage345_cross_sectional_momentum_satellite_v1.csv",
            "xsmom_raw_input",
            "重建 standalone xsmom 的横截面信号输入",
            ("date", "long_products", "short_products"),
        ),
        (
            "stage167_c9_curves",
            PORTFOLIO_OUTPUT_DIR
            / "qmt_roll_stage167_c9_live_15w_multiperiod_ai_audit_curves_stage167_c9_live_15w_multiperiod_ai_audit_v1.csv",
            "current_c9_margin",
            "当前重建 C9 多起点曲线和保证金字段",
            stage167_curve_columns,
        ),
        (
            "stage847_c9_curve",
            PORTFOLIO_OUTPUT_DIR / "qmt_roll_stage847_stage830_c4_stop_retry_engine_curve_stage847_stage830_c4_stop_retry_engine_v1.csv",
            "current_c9_curve",
            "当前 C9 单母本曲线",
            ("account_equity", "broker10_margin_to_equity_pct"),
        ),
        (
            "stage847_c9_closed_lots",
            PORTFOLIO_OUTPUT_DIR
            / "qmt_roll_stage847_stage830_c4_stop_retry_engine_closed_lots_stage847_stage830_c4_stop_retry_engine_v1.csv",
            "current_c9_trade_lots",
            "当前 C9 成交 lot 归因",
            ("entry_date", "exit_date", "product", "direction", "volume", "realized_pnl"),
        ),
        (
            "stage847_c9_full_period_positions",
            PORTFOLIO_OUTPUT_DIR
            / "qmt_roll_stage847_stage830_c4_stop_retry_engine_positions_stage847_stage830_c4_stop_retry_engine_v1.csv",
            "current_c9_full_period_positions",
            "当前 C9 全周期逐日持仓，用于真组合保证金叠加",
            ("date", "vt_symbol", "end_pos", "margin"),
        ),
    ]
    return [
        inventory_file(name, path, group=group, required_for=required_for, required_columns=required_columns)
        for name, path, group, required_for, required_columns in specs
    ]


def _markdown_table(frame: pd.DataFrame, columns: list[str]) -> str:
    if frame.empty:
        return ""
    data = frame[columns].copy()
    return data.to_markdown(index=False)


def write_report(inventory: list[dict[str, Any]], decision: dict[str, Any]) -> None:
    frame = pd.DataFrame(inventory)
    missing = frame[frame["status"].ne("present") | frame["has_required_columns"].eq(False)].copy()
    present = frame[frame["status"].eq("present") & frame["has_required_columns"].eq(True)].copy()
    lines = [
        "# Stage018 低相关收益腿库存审计",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 阶段性质：只读输入链/复用可行性审计，不产生策略候选，不改官方实盘。",
        f"- 决策：`{decision['decision']}`",
        "",
        "## 调研判断",
        "",
        "- 外部资料支持趋势系统通过跨规则、跨市场、低相关收益源提升稳健性；但公开简化回测不能替代本仓库的整数手、保证金、成交约束。",
        "- 历史 Stage208 说明 xsmom 低相关腿有过正向路径价值；Stage214 说明旧候选在精确保证金下不能直接部署。",
        "- 因此本阶段只判断输入链是否可复用，不把旧 Stage079 口径硬套到当前 C9/15w。",
        "",
        "## 缺失项",
        "",
        _markdown_table(
            missing,
            ["name", "group", "required_for", "status", "missing_columns", "path"],
        ),
        "",
        "## 可用项",
        "",
        _markdown_table(
            present,
            ["name", "group", "required_for", "size_bytes", "path"],
        ),
        "",
        "## 结论",
        "",
        f"- 能否直接复用旧 xsmom 输出：`{decision['can_directly_reuse_old_xsmom_outputs']}`。",
        f"- 能否现在重建 standalone xsmom：`{decision['can_rebuild_standalone_xsmom_now']}`。",
        f"- 当前 C9 曲线/保证金字段是否可用：`{decision['current_c9_curve_margin_available']}`。",
        f"- 当前 C9 全周期逐日 positions 是否可用：`{decision['current_c9_full_period_positions_available']}`。",
        f"- 能否现在跑当前 C9 + xsmom 真组合：`{decision['can_run_current_c9_true_xsmom_combo_now']}`。",
        f"- 下一步：{decision['next_step']}",
        "",
        "## 过拟合反思",
        "",
        "- 运行前判断：否。原因：本阶段不调参数、不筛日期/品种/方向，只审计输入链和历史证据。",
        "- 运行后判断：否。原因：负向缺口被保留，没有为了目标强行把旧输出当现成候选。",
        "",
        "## 继续价值反思",
        "",
        "- 运行前判断：是。原因：目标需要低相关收益源或新外生 PIT 信息，xsmom 是已有历史正向线索。",
        "- 运行后判断：是，但必须先补输入链。原因：当前缺的是可复验的当前口径 xsmom 原始输入和 C9 全周期持仓，而不是再扫 C9 风控小参数。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    STAGE_RECORD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    inventory = build_inventory()
    decision = assess_reuse_gate(inventory)
    pd.DataFrame(inventory).to_csv(INVENTORY_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_report(inventory, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
