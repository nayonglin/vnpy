from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
UPSTREAM_LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage029"
MODEL_TAG = "stage029_next_route_eligibility_audit_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage029_next_route_eligibility_audit"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
UPSTREAM_LINE_DIR = PROJECT_DIR / "research" / "lines" / UPSTREAM_LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage029_next_route_eligibility_audit"
STAGES_DIR = LINE_DIR / "stages"

ROUTE_INVENTORY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_route_inventory_{MODEL_TAG}.csv"
FAMILY_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_family_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


REFUTED_STATES = {
    "true_engine_failed",
    "expanded_probe_failed",
    "daily_probe_failed",
    "proxy_improved_but_daily_probe_failed",
    "no_stable_candidate",
    "coverage_or_oos_failed",
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
    if isinstance(value, (pd.Timestamp, datetime)):
        if pd.isna(value):
            return ""
        return value.isoformat()
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
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


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or pd.isna(value):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float = np.nan) -> float:
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def classify_route(route: dict[str, Any] | pd.Series) -> dict[str, Any]:
    data = dict(route)
    state = str(data.get("evidence_state", "") or "")
    known_refuted = bool(_as_int(data.get("known_refuted"), 0))
    param_rescue_forbidden = bool(_as_int(data.get("param_rescue_forbidden"), 0))
    local_history_available = bool(_as_int(data.get("local_history_available"), 1))
    stable_candidate_count = _as_int(data.get("stable_candidate_count"), 0)
    source_coverage_pct = _as_float(data.get("source_coverage_pct"), np.nan)
    daily_probe_delta = _as_float(data.get("daily_probe_worst_return_delta_pp"), np.nan)

    reasons: list[str] = []
    if state in REFUTED_STATES or known_refuted:
        reasons.append(state if state else "known_refuted")
    if "daily_probe" in state or (np.isfinite(daily_probe_delta) and daily_probe_delta < 0):
        reasons.append("daily_probe_failed")
    if param_rescue_forbidden:
        reasons.append("param_rescue_forbidden")
    if not local_history_available:
        reasons.append("no_local_pit_history")
    if np.isfinite(source_coverage_pct) and source_coverage_pct < 80.0:
        reasons.append("coverage_below_80pct")
    if state == "no_stable_candidate" or stable_candidate_count == 0 and data.get("requires_stable_candidate", 0):
        reasons.append("no_stable_candidate")

    if (state in REFUTED_STATES or known_refuted) and param_rescue_forbidden:
        status = "rejected_no_param_rescue"
        action = "do_not_continue_this_route"
        priority = 0
    elif not local_history_available:
        status = "needs_data_acquisition"
        action = "acquire_or_build_pit_history_before_any_rule"
        priority = 60
    elif np.isfinite(source_coverage_pct) and source_coverage_pct < 80.0:
        status = "coverage_gap"
        action = "fix_pit_coverage_before_signal_audit"
        priority = 35
    elif stable_candidate_count > 0 and not known_refuted:
        status = "eligible_for_readonly_proxy_or_true_engine_review"
        action = "freeze_one_low_degree_hypothesis_then_test"
        priority = 75
    else:
        status = "diagnostic_only"
        action = "keep_as_evidence_not_strategy"
        priority = 20

    result = dict(data)
    result["route_status"] = status
    result["recommended_next_action"] = action
    result["priority_score"] = int(priority)
    result["exclusion_reasons"] = ",".join(list(dict.fromkeys([item for item in reasons if item])))
    result["parameter_rescue_allowed"] = bool(priority > 0 and status.startswith("eligible"))
    return result


def make_route_decision(routes: pd.DataFrame) -> dict[str, Any]:
    data = routes.copy()
    immediate = data[data["route_status"].astype(str).eq("eligible_for_readonly_proxy_or_true_engine_review")]
    acquisition = data[data["route_status"].astype(str).eq("needs_data_acquisition")]
    top = (
        data.sort_values(["priority_score", "route_id"], ascending=[False, True]).head(1).to_dict("records")
        if not data.empty
        else []
    )
    if not immediate.empty:
        decision = "stage029_has_local_unrefuted_route_freeze_before_engine"
        best_next_direction = str(immediate.sort_values("priority_score", ascending=False).iloc[0]["route_id"])
    elif not acquisition.empty:
        decision = "stage029_no_local_unrefuted_route_need_new_pit_or_independent_sleeve"
        best_next_direction = "new_pit_source_acquisition_or_independent_sleeve_design"
    else:
        decision = "stage029_no_local_unrefuted_route_need_new_pit_or_independent_sleeve"
        best_next_direction = "new_pit_source_or_non_crowding_account_structure"
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "decision": decision,
        "best_next_direction": best_next_direction,
        "route_count": int(len(data)),
        "immediate_strategy_candidate_count": int(len(immediate)),
        "data_acquisition_candidate_count": int(len(acquisition)),
        "rejected_no_param_rescue_count": int(data["route_status"].astype(str).eq("rejected_no_param_rescue").sum()),
        "top_route": top[0] if top else {},
        "parameter_rescue_allowed": False,
        "strategy_changed": False,
        "official_live_strategy_changed": False,
        "true_engine": False,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "external_research_judgment": (
            "Managed-futures and time-series momentum research supports diversification and robust PIT sizing, "
            "but the local evidence has already refuted xsmom, OI, warehouse, breadth, member-rank and simple "
            "account-state parameter rescue. GitHub examples are useful as framework references, not directly "
            "copyable alpha for this objective."
        ),
        "overfit_reflection_before": (
            "否。Stage029 只做冻结证据路线资格审计，不新增交易规则、不按坏窗口调参。"
        ),
        "overfit_reflection_after": (
            "否。结论是阻止已反证路线救参；若继续在 xsmom/OI/仓单/TopN/账户阈值上扫相邻参数，就是过拟合。"
        ),
        "continue_value_before": (
            "有。Stage028 反证唯一前沿后，必须先决定下一类信息源，否则会在失败字段上空转。"
        ),
        "continue_value_after": (
            "有，但下一步价值来自新 PIT 数据或结构不同的独立 sleeve，而不是当前本地字段的阈值救参。"
        ),
    }


def build_route_inventory() -> pd.DataFrame:
    routes = [
        {
            "route_id": "stage028_xsmom12_not_opposed_add_risk",
            "family": "xsmom_confirmation",
            "evidence_state": "true_engine_failed",
            "known_refuted": 1,
            "param_rescue_forbidden": 1,
            "summary": "Stage022 proxy frontier failed in Stage028 true engine; do not sweep xsmom lookback/topN/weights.",
            "stage_refs": "Stage022,Stage027,Stage028",
        },
        {
            "route_id": "stage026_ai_quality_floor25_add_risk",
            "family": "ai_quality_add_risk",
            "evidence_state": "true_engine_failed",
            "known_refuted": 1,
            "param_rescue_forbidden": 1,
            "summary": "Top AI cool-quality add-risk true engine worsened dense left tail and to-final windows.",
            "stage_refs": "Stage013,Stage026",
        },
        {
            "route_id": "stage036_overheat_recovery_cap",
            "family": "account_state_overheat",
            "evidence_state": "true_engine_failed",
            "known_refuted": 1,
            "param_rescue_forbidden": 1,
            "summary": "Overheat cap with recovery exemption triggered narrowly and damaged longer account paths.",
            "stage_refs": "Stage035,Stage036",
        },
        {
            "route_id": "stage052_053_contract_oi_share_ge50",
            "family": "external_pit_contract_oi",
            "evidence_state": "proxy_improved_but_daily_probe_failed",
            "proxy_negative_delta": -78_813,
            "daily_probe_worst_return_delta_pp": -7.2241,
            "known_refuted": 1,
            "param_rescue_forbidden": 1,
            "summary": "OI concentration proxy improved endpoint/right tail but pressure daily probe worsened worst path.",
            "stage_refs": "Stage049,Stage051,Stage052,Stage053",
        },
        {
            "route_id": "stage046_047_warehouse_build_20d",
            "family": "external_pit_warehouse",
            "evidence_state": "proxy_improved_but_daily_probe_failed",
            "known_refuted": 1,
            "param_rescue_forbidden": 1,
            "summary": "Warehouse build had candidate-level lift but daily pressure probe did not solve left tail.",
            "stage_refs": "Stage045,Stage046,Stage047",
        },
        {
            "route_id": "stage056_non_full_market_top8_budget_cap",
            "family": "ai_budget_cap",
            "evidence_state": "true_engine_failed",
            "known_refuted": 1,
            "param_rescue_forbidden": 1,
            "summary": "Hard cap reduced drawdown depth but multiplied negative windows and cut right tail.",
            "stage_refs": "Stage055,Stage056,Stage057",
        },
        {
            "route_id": "stage062_oi_confirmed_cap_to_one",
            "family": "oi_confirmed_reverse_budget",
            "evidence_state": "true_engine_failed",
            "known_refuted": 1,
            "param_rescue_forbidden": 1,
            "summary": "OI-confirmed reverse budget proxy failed in true engine; no hand/threshold rescue.",
            "stage_refs": "Stage060,Stage061,Stage062",
        },
        {
            "route_id": "stage067_breakeven_after_1r",
            "family": "exit_path_management",
            "evidence_state": "expanded_probe_failed",
            "known_refuted": 1,
            "param_rescue_forbidden": 1,
            "summary": "Breakeven after +1R improved narrow pressure set but failed expanded daily probe.",
            "stage_refs": "Stage065,Stage066,Stage067",
        },
        {
            "route_id": "stage073_term_structure_front_next",
            "family": "external_pit_term_structure",
            "evidence_state": "no_stable_candidate",
            "stable_candidate_count": 0,
            "known_refuted": 1,
            "param_rescue_forbidden": 1,
            "requires_stable_candidate": 1,
            "summary": "Front/next term structure PIT audit found no stable OOS candidate.",
            "stage_refs": "Stage073",
        },
        {
            "route_id": "stage076_trend_breadth",
            "family": "market_breadth",
            "evidence_state": "coverage_or_oos_failed",
            "source_coverage_pct": 97.5601,
            "stable_candidate_count": 0,
            "known_refuted": 1,
            "param_rescue_forbidden": 1,
            "requires_stable_candidate": 1,
            "summary": "Trend breadth raw signal failed robust year stability and had recent market gap.",
            "stage_refs": "Stage076",
        },
        {
            "route_id": "stage077_jd_independent_candidate",
            "family": "jd_independent_sleeve",
            "evidence_state": "no_stable_candidate",
            "stable_candidate_count": 0,
            "known_refuted": 1,
            "param_rescue_forbidden": 1,
            "requires_stable_candidate": 1,
            "summary": "jd data asset exists, but independent AI/top8 evidence is too small and OOS unstable.",
            "stage_refs": "Stage077",
        },
        {
            "route_id": "stage081_member_rank_position_flow",
            "family": "external_pit_member_rank",
            "evidence_state": "no_stable_candidate",
            "stable_candidate_count": 0,
            "known_refuted": 1,
            "param_rescue_forbidden": 1,
            "requires_stable_candidate": 1,
            "summary": "Member-rank coverage was repaired, but simple position/flow direction failed worst-year stability.",
            "stage_refs": "Stage080,Stage081",
        },
        {
            "route_id": "options_iv_skew_or_intraday_orderflow",
            "family": "new_external_pit",
            "evidence_state": "no_local_history",
            "local_history_available": 0,
            "known_refuted": 0,
            "param_rescue_forbidden": 0,
            "summary": "Potentially new PIT source; must acquire point-in-time history before any selector or sizing rule.",
            "stage_refs": "new_data_required",
        },
        {
            "route_id": "independent_sleeve_from_separate_range_or_carry_line",
            "family": "independent_sleeve",
            "evidence_state": "no_local_history",
            "local_history_available": 0,
            "known_refuted": 0,
            "param_rescue_forbidden": 0,
            "summary": "Could address start-date luck only if a separate sleeve proves stable standalone OOS first.",
            "stage_refs": "new_structure_required",
        },
    ]
    return pd.DataFrame([classify_route(route) for route in routes]).sort_values(
        ["priority_score", "route_id"], ascending=[False, True]
    ).reset_index(drop=True)


def summarize_families(routes: pd.DataFrame) -> pd.DataFrame:
    return (
        routes.groupby("family", as_index=False)
        .agg(
            route_count=("route_id", "size"),
            max_priority_score=("priority_score", "max"),
            rejected_no_param_rescue_count=("route_status", lambda s: int((s == "rejected_no_param_rescue").sum())),
            needs_data_acquisition_count=("route_status", lambda s: int((s == "needs_data_acquisition").sum())),
            immediate_candidate_count=(
                "route_status",
                lambda s: int((s == "eligible_for_readonly_proxy_or_true_engine_review").sum()),
            ),
        )
        .sort_values(["max_priority_score", "family"], ascending=[False, True])
        .reset_index(drop=True)
    )


def _write_report(decision: dict[str, Any], routes: pd.DataFrame, family_summary: pd.DataFrame) -> None:
    report = f"""# Stage029 下一路线资格审计

- 生成时间：`{decision['generated_at']}`
- line_id：`{LINE_ID}`
- model_tag：`{MODEL_TAG}`
- 阶段性质：只读路线资格审计；不回测、不改策略、不连接 CTP、不调用下单
- 决策：`{decision['decision']}`

## 外部调研判断

- time-series momentum / managed futures 资料支持跨市场分散、右尾捕获和风险预算，但不能为局部左尾牺牲趋势右尾。
- meta-labeling / bet sizing 资料支持用 PIT 二级确认层决定是否加风险，但 Stage026/028 已证明当前本地 AI/xsmom 质量层不能直接落成真引擎。
- GitHub trend-following/backtesting 项目更适合做框架参考；没有发现可直接复制为当前目标 alpha 的实现。

## 路线表

{_md_table(routes, max_rows=40)}

## 家族汇总

{_md_table(family_summary, max_rows=40)}

## 结论

- 立即可写策略/真引擎候选数：`{decision['immediate_strategy_candidate_count']}`
- 需要新数据/新结构候选数：`{decision['data_acquisition_candidate_count']}`
- 已反证且禁止救参数路线数：`{decision['rejected_no_param_rescue_count']}`
- 下一方向：`{decision['best_next_direction']}`
- 过拟合反思：{decision['overfit_reflection_after']}
- 继续价值反思：{decision['continue_value_after']}

## 输出

- route_inventory: `{ROUTE_INVENTORY_PATH}`
- family_summary: `{FAMILY_SUMMARY_PATH}`
- decision: `{DECISION_PATH}`
- report: `{REPORT_PATH}`
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def _write_stage_record(decision: dict[str, Any]) -> Path:
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    path = STAGES_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M')}_stage029_next_route_eligibility_audit.md"
    content = f"""# Stage029 下一路线资格审计

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{decision['generated_at']}
- 阶段性质：只读路线资格审计；不回测、不改策略、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考方向：time-series momentum / managed futures、meta-labeling / bet sizing、pysystemtrade 类风险预算框架、GitHub trend-following/backtesting 示例。
- 我的判断：这些资料支持“新 PIT 信息源 + 低自由度 sizing 验证”或“独立稳定 sleeve”，但不支持继续在已反证的 xsmom/OI/仓单/TopN/账户阈值上救参。

## 本次变更

- 新增脚本：`research/lines/{LINE_ID}/tools/stage029_next_route_eligibility_audit.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage029_next_route_eligibility_audit.py`
- 新增参数：无交易参数；仅使用路线分类字段。
- 修改参数：无
- 删除参数：无

## 结果

- route_count：`{decision['route_count']}`
- immediate_strategy_candidate_count：`{decision['immediate_strategy_candidate_count']}`
- data_acquisition_candidate_count：`{decision['data_acquisition_candidate_count']}`
- rejected_no_param_rescue_count：`{decision['rejected_no_param_rescue_count']}`
- 决策：`{decision['decision']}`
- 下一方向：`{decision['best_next_direction']}`

## 输出文件

- route_inventory：`{ROUTE_INVENTORY_PATH}`
- family_summary：`{FAMILY_SUMMARY_PATH}`
- decision：`{DECISION_PATH}`
- report：`{REPORT_PATH}`

## 过拟合反思

- 运行前判断：{decision['overfit_reflection_before']}
- 运行后判断：{decision['overfit_reflection_after']}

## 继续价值反思

- 运行前判断：{decision['continue_value_before']}
- 运行后判断：{decision['continue_value_after']}

## 合入建议

- 更新本线 `LINE.md`：是。
- 更新 `research/registry.md`：是。
- 追加根目录 `memory.md/back_log.md`：否，本阶段不是正式候选或重要突破，只是路线审计。
"""
    path.write_text(content, encoding="utf-8")
    return path


def main() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    routes = build_route_inventory()
    family_summary = summarize_families(routes)
    decision = make_route_decision(routes)
    decision["outputs"] = {
        "route_inventory": str(ROUTE_INVENTORY_PATH),
        "family_summary": str(FAMILY_SUMMARY_PATH),
        "decision": str(DECISION_PATH),
        "report": str(REPORT_PATH),
    }
    routes.to_csv(ROUTE_INVENTORY_PATH, index=False, encoding="utf-8-sig")
    family_summary.to_csv(FAMILY_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    _write_report(decision, routes, family_summary)
    decision["outputs"]["stage_record"] = str(_write_stage_record(decision))
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    return decision


if __name__ == "__main__":
    main()
