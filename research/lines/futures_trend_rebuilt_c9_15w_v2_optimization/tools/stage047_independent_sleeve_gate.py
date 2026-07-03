from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage047"
MODEL_TAG = "stage047_independent_sleeve_gate_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage047_independent_sleeve_gate"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage047_independent_sleeve_gate"
STAGES_DIR = LINE_DIR / "stages"

CANDIDATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_candidate_inventory_{MODEL_TAG}.csv"
GATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_table_{MODEL_TAG}.csv"
FAMILY_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_family_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

SOURCE_LINKS = {
    "aqr_demystifying_managed_futures": "https://www.aqr.com/-/media/AQR/Documents/Insights/Journal-Article/Demystifying-Managed-Futures.pdf",
    "moskowitz_time_series_momentum": "https://w4.stern.nyu.edu/facdir/lpederse/papers/TimeSeriesMomentum.pdf",
    "commodity_momentum_term_structure_idvol": "https://openaccess.city.ac.uk/id/eprint/6418/",
    "pysystemtrade_diversification_multiplier": "https://qoppac.blogspot.com/2016/01/correlations-weights-multipliers.html",
}


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        result = float(value)
        if np.isnan(result) or np.isinf(result):
            return None
        return result
    if isinstance(value, (pd.Timestamp, datetime)):
        if pd.isna(value):
            return ""
        return value.isoformat()
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_无记录_"
    data = frame.head(max_rows).copy() if max_rows else frame.copy()
    return data.to_markdown(index=False)


def _exists(path_text: str) -> bool:
    if not path_text:
        return False
    first = path_text.split(",")[0].strip()
    if not first or first.startswith("stage") or first == "synthetic":
        return False
    return (PROJECT_DIR / first).exists()


def build_candidate_inventory() -> list[dict[str, Any]]:
    return [
        {
            "candidate_id": "historical_stage208_xsmom_true_carry",
            "structure_family": "independent_xsmom_carry_sleeve",
            "evidence_scope": "historical_different_baseline",
            "evidence_summary": (
                "Stage208/209 曾把冻结 xsmom 规则按下一真实窗口成交，risk070_clean+xsmom 改善回撤并保留约 67.69% 收益；"
                "但属于 Stage079/旧资金口径，不是当前重建 C9/15w。"
            ),
            "true_engine_current_rebuild": False,
            "historical_true_engine": True,
            "materiality_score": 2,
            "right_tail_preserved": True,
            "current_dense_goal_pass": False,
            "current_artifacts_available": False,
            "known_current_refuted": False,
            "param_rescue_forbidden": False,
            "source_paths": "research/lines/futures_trend_drawdown30_preserve_return/stages/20260601_1809_stage208_xsmom_true_carry_replay.md",
            "recommended_next_action": "rebuild_current_c9_true_independent_xsmom_sleeve_from_stage020_inputs_before_any_promotion",
        },
        {
            "candidate_id": "stage021_current_xsmom_curve_overlay",
            "structure_family": "independent_xsmom_curve_overlay",
            "evidence_scope": "current_rebuilt_c9",
            "evidence_summary": "Stage021 固定 xsmom 非挤占 curve-level overlay 未改善左尾，最差收益略恶化。",
            "true_engine_current_rebuild": False,
            "historical_true_engine": False,
            "materiality_score": 0,
            "right_tail_preserved": True,
            "current_dense_goal_pass": False,
            "current_artifacts_available": True,
            "known_current_refuted": True,
            "param_rescue_forbidden": True,
            "source_paths": "research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/stages/20260702_0635_stage021_xsmom_non_crowding_overlay_proxy.md",
            "recommended_next_action": "do_not_sweep_xsmom_weight_cost_or_lookback",
        },
        {
            "candidate_id": "stage022_028_xsmom_confirmation",
            "structure_family": "xsmom_confirmation_add_risk",
            "evidence_scope": "current_rebuilt_c9",
            "evidence_summary": "Stage022 proxy 有前沿价值，但 Stage028 当前真引擎恶化左尾和到终点窗口。",
            "true_engine_current_rebuild": True,
            "historical_true_engine": False,
            "materiality_score": 1,
            "right_tail_preserved": False,
            "current_dense_goal_pass": False,
            "current_artifacts_available": True,
            "known_current_refuted": True,
            "param_rescue_forbidden": True,
            "source_paths": "research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/stages/20260702_0624_stage022_xsmom_entry_confirmation_proxy.md,research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/stages/20260702_0742_stage028_xsmom_confirmation_add_risk_engine.md",
            "recommended_next_action": "do_not_sweep_confirmation_thresholds_or_rounding",
        },
        {
            "candidate_id": "historical_stage418_jd_independent_sleeve",
            "structure_family": "jd_independent_sleeve",
            "evidence_scope": "historical_different_baseline",
            "evidence_summary": "JD 独立风险槽保留核心右尾，但 20k/50k 全周期贡献约 +140/-290，材料性不足。",
            "true_engine_current_rebuild": False,
            "historical_true_engine": True,
            "materiality_score": 0,
            "right_tail_preserved": True,
            "current_dense_goal_pass": False,
            "current_artifacts_available": False,
            "known_current_refuted": True,
            "param_rescue_forbidden": True,
            "source_paths": "research/lines/futures_trend_drawdown30_preserve_return/stages/20260608_1323_stage418_stage407_jd_independent_sleeve.md",
            "recommended_next_action": "keep_independent_risk_slot_as_structure_principle_but_do_not_rescue_jd",
        },
        {
            "candidate_id": "historical_stage420_low_risk_scout_sleeve",
            "structure_family": "low_risk_scout_sleeve",
            "evidence_scope": "historical_different_baseline",
            "evidence_summary": "低风险候选补偿槽在正式源亏损且恶化成本压力回撤。",
            "true_engine_current_rebuild": False,
            "historical_true_engine": True,
            "materiality_score": 0,
            "right_tail_preserved": False,
            "current_dense_goal_pass": False,
            "current_artifacts_available": False,
            "known_current_refuted": True,
            "param_rescue_forbidden": True,
            "source_paths": "research/lines/futures_trend_drawdown30_preserve_return/stages/20260608_1342_stage420_low_risk_scout_sleeve.md",
            "recommended_next_action": "do_not_continue_low_risk_scout_capital_or_maxpos_sweep",
        },
        {
            "candidate_id": "upstream_stage073_term_structure",
            "structure_family": "term_structure_carry",
            "evidence_scope": "upstream_current_rebuild_family",
            "evidence_summary": "期限结构特征有 PIT 数据资产，但 Stage073 稳定 OOS 候选数为 0。",
            "true_engine_current_rebuild": False,
            "historical_true_engine": False,
            "materiality_score": 0,
            "right_tail_preserved": False,
            "current_dense_goal_pass": False,
            "current_artifacts_available": True,
            "known_current_refuted": True,
            "param_rescue_forbidden": True,
            "source_paths": "research/lines/futures_trend_rebuilt_c9_15w_optimization/stages/20260702_0103_stage073_term_structure_pit_audit.md",
            "recommended_next_action": "do_not_sweep_term_structure_percentiles_or_month_gap",
        },
        {
            "candidate_id": "futures_range_line_current",
            "structure_family": "range_reversion",
            "evidence_scope": "separate_line_no_structured_current_history",
            "evidence_summary": "futures_range 线有方向性记录，但当前目录无可直接组合的结构化回测产物。",
            "true_engine_current_rebuild": False,
            "historical_true_engine": False,
            "materiality_score": 0,
            "right_tail_preserved": False,
            "current_dense_goal_pass": False,
            "current_artifacts_available": False,
            "known_current_refuted": False,
            "param_rescue_forbidden": False,
            "source_paths": "research/lines/futures_range/LINE.md",
            "recommended_next_action": "continue_range_line_inside_its_own_isolation_before_any_combo",
        },
    ]


def evaluate_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    row = dict(candidate)
    reasons: list[str] = []

    current = bool(row.get("evidence_scope") == "current_rebuilt_c9")
    true_current = bool(row.get("true_engine_current_rebuild"))
    historical_true = bool(row.get("historical_true_engine"))
    current_pass = bool(row.get("current_dense_goal_pass"))
    material = int(row.get("materiality_score") or 0) >= 1
    right_tail = bool(row.get("right_tail_preserved"))
    refuted = bool(row.get("known_current_refuted"))
    param_forbidden = bool(row.get("param_rescue_forbidden"))
    artifacts = bool(row.get("current_artifacts_available"))

    if refuted and true_current:
        reasons.append("current_true_engine_refuted")
    elif refuted:
        reasons.append("known_refuted_or_materiality_failed")
    if param_forbidden:
        reasons.append("parameter_rescue_forbidden")
    if not current:
        reasons.append(str(row.get("evidence_scope") or "not_current_rebuilt_c9"))
    if not artifacts:
        reasons.append("current_artifacts_missing_or_not_current")
    if not true_current:
        reasons.append("no_current_true_engine_evidence")
    if not current_pass:
        reasons.append("current_dense_goal_not_passed")
    if not material:
        reasons.append("materiality_not_proven")
    if not right_tail:
        reasons.append("right_tail_not_preserved")

    if current and true_current and current_pass and material and right_tail and not refuted and not param_forbidden:
        gate_status = "promotion_candidate"
        promote_now = True
        needs_current_rebuild = False
        reasons = []
    elif historical_true and material and right_tail and not param_forbidden and not refuted:
        gate_status = "rebuild_priority"
        promote_now = False
        needs_current_rebuild = True
    elif param_forbidden or refuted:
        gate_status = "rejected_no_param_rescue"
        promote_now = False
        needs_current_rebuild = False
    elif not artifacts:
        gate_status = "needs_separate_line_evidence"
        promote_now = False
        needs_current_rebuild = False
    else:
        gate_status = "diagnostic_only"
        promote_now = False
        needs_current_rebuild = False

    row.update(
        {
            "source_path_exists": bool(_exists(str(row.get("source_paths", "")))),
            "gate_status": gate_status,
            "promote_now": bool(promote_now),
            "needs_current_rebuild": bool(needs_current_rebuild),
            "blocking_reasons": ",".join(list(dict.fromkeys(reasons))),
        }
    )
    return row


def summarize_family(gate_table: pd.DataFrame) -> pd.DataFrame:
    if gate_table.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for family, group in gate_table.groupby("structure_family", sort=True):
        rows.append(
            {
                "structure_family": family,
                "candidate_count": int(len(group)),
                "promotion_candidate_count": int(group["promote_now"].astype(bool).sum()),
                "rebuild_priority_count": int(group["needs_current_rebuild"].astype(bool).sum()),
                "rejected_count": int(group["gate_status"].astype(str).eq("rejected_no_param_rescue").sum()),
                "best_gate_status": ",".join(sorted(set(group["gate_status"].astype(str)))),
                "candidate_ids": ",".join(group["candidate_id"].astype(str)),
            }
        )
    return pd.DataFrame(rows)


def make_stage047_decision(gate_table: pd.DataFrame) -> dict[str, Any]:
    promotion = gate_table[gate_table["promote_now"].astype(bool)].copy() if not gate_table.empty else pd.DataFrame()
    rebuild = gate_table[gate_table["needs_current_rebuild"].astype(bool)].copy() if not gate_table.empty else pd.DataFrame()
    rejected = gate_table[gate_table["gate_status"].astype(str).eq("rejected_no_param_rescue")].copy() if not gate_table.empty else pd.DataFrame()

    if not promotion.empty:
        decision = "stage047_independent_sleeve_has_promotion_candidate_needs_ab"
        best_next = str(promotion.iloc[0]["candidate_id"])
    elif not rebuild.empty:
        decision = "stage047_independent_sleeve_no_current_promotion_rebuild_xsmom_first"
        best_next = str(rebuild.iloc[0]["candidate_id"])
    else:
        decision = "stage047_independent_sleeve_no_current_route_freeze_forward_oos"
        best_next = "freeze_forward_oos_or_build_separate_line"

    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "decision": decision,
        "best_next_rebuild_route": best_next,
        "candidate_count": int(len(gate_table)),
        "promotion_candidate_count": int(len(promotion)),
        "rebuild_priority_count": int(len(rebuild)),
        "rejected_no_param_rescue_count": int(len(rejected)),
        "immediate_strategy_candidate_count": int(len(promotion)),
        "strategy_rule_created": False,
        "official_live_strategy_changed": False,
        "true_engine": False,
        "ab_triggered": False,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "source_links": SOURCE_LINKS,
        "external_research_judgment": (
            "外部 managed futures 与 commodity factor 文献支持多市场、多期限和 carry/momentum 等不同收益源的分散价值；"
            "pysystemtrade 也强调相关性越低的规则组合才可能提高组合尺度。"
            "但本仓库当前证据要求更严格：只有当前重建 C9 口径、真实引擎、密集多起点目标通过且保留右尾，才可晋级。"
        ),
        "overfit_reflection_before": "否。本阶段不扫参数，只审计现有独立 sleeve 证据是否足够进入当前 C9 重建验证。",
        "overfit_reflection_after": "否。只有 Stage208 历史 xsmom true-carry 被列为重建优先，不把旧结果当当前候选。",
        "continue_value_before": "有。当前本地字段和外部数据合同都没有立即候选，必须寻找结构不同的独立收益源。",
        "continue_value_after": (
            "有但应聚焦：先复建当前 C9 口径的 true independent xsmom sleeve；若仍失败，则转 forward OOS 或完全独立策略线。"
        ),
    }


def write_report(gate_table: pd.DataFrame, family_summary: pd.DataFrame, decision: dict[str, Any]) -> None:
    lines = [
        "# Stage047 独立收益腿资格闸门",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- 记录时间：{decision['generated_at']}",
        f"- 决策：`{decision['decision']}`",
        "- 阶段性质：只读候选资格审计；不回测、不改策略、不连接 CTP、不调用订单 API。",
        "",
        "## 外部调研与判断",
        "",
        "- AQR/Hurst/Ooi/Pedersen 与 Moskowitz 等文献支持趋势跟随、跨市场分散和多期限趋势的长期价值。",
        "- 商品期货因子研究支持 momentum、term structure/carry、idiosyncratic volatility 等不同信号可能不是完全重叠。",
        "- pysystemtrade 的规则组合思想强调要看规则相关性和分散乘数，低相关结构比同源阈值调参更符合第一性原理。",
        "- 我的判断：当前不能直接晋级任何独立 sleeve；只有历史 Stage208 xsmom true-carry 值得在当前重建 C9 口径重建验证。",
        "",
        "## Gate Table",
        "",
        _md_table(
            gate_table[
                [
                    "candidate_id",
                    "structure_family",
                    "evidence_scope",
                    "gate_status",
                    "promote_now",
                    "needs_current_rebuild",
                    "blocking_reasons",
                    "recommended_next_action",
                ]
            ],
            max_rows=80,
        ),
        "",
        "## Family Summary",
        "",
        _md_table(family_summary),
        "",
        "## 过拟合反思",
        "",
        f"- 运行前：{decision['overfit_reflection_before']}",
        f"- 运行后：{decision['overfit_reflection_after']}",
        "",
        "## 继续价值反思",
        "",
        f"- 运行前：{decision['continue_value_before']}",
        f"- 运行后：{decision['continue_value_after']}",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_stage_record(gate_table: pd.DataFrame, family_summary: pd.DataFrame, decision: dict[str, Any]) -> Path:
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    path = STAGES_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M')}_stage047_independent_sleeve_gate.md"
    text = f"""# Stage047 独立收益腿资格闸门

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{decision['generated_at']}
- 阶段性质：只读候选资格审计；不回测、不改策略、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：AQR Demystifying Managed Futures、Moskowitz/Ooi/Pedersen Time Series Momentum、Fuertes/Miffre/Fernandez-Perez commodity momentum/term-structure/idiosyncratic volatility、pysystemtrade diversification multiplier。
- 我的判断：独立收益腿是当前目标继续推进的正确大方向，但只有当前重建 C9 口径、真实引擎、密集多起点目标通过、右尾保留的候选才可晋级；历史旧口径只能作为重建优先级。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage047_independent_sleeve_gate.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage047_independent_sleeve_gate.py`
- 新增参数：无交易参数
- 修改参数：无正式策略参数修改
- 删除参数：无

## 结果

- decision：`{decision['decision']}`
- best_next_rebuild_route：`{decision['best_next_rebuild_route']}`
- candidate_count：`{decision['candidate_count']}`
- promotion_candidate_count：`{decision['promotion_candidate_count']}`
- rebuild_priority_count：`{decision['rebuild_priority_count']}`
- rejected_no_param_rescue_count：`{decision['rejected_no_param_rescue_count']}`
- immediate_strategy_candidate_count：`{decision['immediate_strategy_candidate_count']}`
- 策略变更：`False`
- true engine：`False`
- order API：`0`
- CTP：`False`

## Gate Table

{_md_table(gate_table[["candidate_id", "structure_family", "evidence_scope", "gate_status", "promote_now", "needs_current_rebuild", "blocking_reasons", "recommended_next_action"]], max_rows=80)}

## Family Summary

{_md_table(family_summary)}

## 过拟合反思

- 运行前判断：{decision['overfit_reflection_before']}
- 运行后判断：{decision['overfit_reflection_after']}

## 继续价值反思

- 运行前判断：{decision['continue_value_before']}
- 运行后判断：{decision['continue_value_after']}

## 输出文件

- candidate_inventory：`{CANDIDATE_PATH}`
- gate_table：`{GATE_PATH}`
- family_summary：`{FAMILY_SUMMARY_PATH}`
- decision：`{DECISION_PATH}`
- report：`{REPORT_PATH}`
"""
    path.write_text(text, encoding="utf-8")
    return path


def run() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    candidate_inventory = pd.DataFrame(build_candidate_inventory())
    gate_table = pd.DataFrame([evaluate_candidate(row) for row in candidate_inventory.to_dict("records")])
    family_summary = summarize_family(gate_table)
    decision = make_stage047_decision(gate_table)

    candidate_inventory.to_csv(CANDIDATE_PATH, index=False)
    gate_table.to_csv(GATE_PATH, index=False)
    family_summary.to_csv(FAMILY_SUMMARY_PATH, index=False)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_report(gate_table, family_summary, decision)
    stage_record = write_stage_record(gate_table, family_summary, decision)
    decision["stage_record_path"] = str(stage_record)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return decision


if __name__ == "__main__":
    print(json.dumps(_json_safe(run()), ensure_ascii=False, indent=2))
