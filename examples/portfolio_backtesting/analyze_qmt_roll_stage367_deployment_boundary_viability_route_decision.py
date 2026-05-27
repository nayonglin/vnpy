from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import (
    to_markdown_table,
)


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
MODEL_TAG = "stage367_deployment_boundary_viability_route_decision_v1"
OUTPUT_PREFIX = "qmt_roll_stage367_deployment_boundary_viability_route_decision"
LINE_ID = "futures_trend_drawdown30_preserve_return"

TARGET_MAX_DD_PCT = -30.0
STRICT_RETENTION_PCT = 80.0

STAGE365_SUMMARY = OUTPUT_DIR / "qmt_roll_stage365_smoothness_frontier_audit_summary_stage365_smoothness_frontier_audit_v1.csv"
STAGE365_ANNUAL = OUTPUT_DIR / "qmt_roll_stage365_smoothness_frontier_audit_annual_returns_stage365_smoothness_frontier_audit_v1.csv"
STAGE365_ROLLING = OUTPUT_DIR / "qmt_roll_stage365_smoothness_frontier_audit_rolling_windows_stage365_smoothness_frontier_audit_v1.csv"
STAGE359_SUMMARY = OUTPUT_DIR / "qmt_roll_stage359_c3_backfilled_supply_signal_validation_summary_stage359_c3_backfilled_supply_signal_validation_v1.csv"
STAGE359_DECISION = OUTPUT_DIR / "qmt_roll_stage359_c3_backfilled_supply_signal_validation_decision_stage359_c3_backfilled_supply_signal_validation_v1.json"
STAGE366_DECISION = OUTPUT_DIR / "qmt_roll_stage366_xsmom_carrying_failure_diagnostic_decision_stage366_xsmom_carrying_failure_diagnostic_v1.json"

COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
ROUTE_MATRIX_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_route_matrix_{MODEL_TAG}.csv"
SUPPLY_AUDIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_supply_audit_{MODEL_TAG}.csv"
ANNUAL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_focus_{MODEL_TAG}.csv"
ROLLING_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rolling_focus_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _fmt_pct(value: float | int | str | None, digits: int = 4) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):.{digits}f}%"
    except (TypeError, ValueError):
        return str(value)


def _fmt_num(value: float | int | str | None, digits: int = 2) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):,.{digits}f}"
    except (TypeError, ValueError):
        return str(value)


def _pick(summary: pd.DataFrame, variant: str) -> pd.Series:
    rows = summary[summary["variant"].eq(variant)]
    if rows.empty:
        raise ValueError(f"missing variant in Stage365 summary: {variant}")
    return rows.iloc[0]


def _build_comparison(summary: pd.DataFrame) -> pd.DataFrame:
    variants = [
        ("A_official78_1_50w", "正式78-1", "正式基准"),
        ("B_c3_current_50w", "C3当前研究基准", "当前最强单策略"),
        ("D_c3_50w_plus_115k_external_cash", "C3 50万下单 + 11.5万外部现金", "正常成本部署边界"),
        ("c3_92p5_xsmom_mom_12m_skip1m_7p5_cost20bps", "C3 92.5% + xsmom 7.5%", "净值层，不可直接承载"),
        ("R_xsmom_overlay_3w_cash", "C3原路径 + xsmom overlay + 3万现金", "真实引擎候选但已反证"),
        ("c3_90_carry_10_cost20bps", "C3 90% + Carry 10%", "更平滑但收益源不合格"),
    ]
    rows: list[dict[str, Any]] = []
    for variant, name, status in variants:
        row = _pick(summary, variant)
        rows.append(
            {
                "variant": variant,
                "名称": name,
                "状态": status,
                "总收益_pct": float(row["total_return_pct"]),
                "最大回撤_pct": float(row["max_dd_pct"]),
                "Ulcer_pct": float(row["ulcer_index_pct"]),
                "Sharpe": float(row["sharpe"]),
                "相对C3收益保留_pct": float(row["return_retention_vs_c3_pct"]),
                "最差504日收益_pct": float(row["worst_504d_return_pct"]),
                "最长水下交易日": int(row["longest_underwater_trading_days"]),
                "硬回撤过线": bool(row["hard_dd_pass"]),
                "收益保留过线": bool(row["strict_return_pass"]),
                "可直接晋级判断": "否",
            }
        )

    out = pd.DataFrame(rows)
    out.loc[out["variant"].eq("B_c3_current_50w"), "可直接晋级判断"] = "当前研究基准，未进30"
    out.loc[out["variant"].eq("D_c3_50w_plus_115k_external_cash"), "可直接晋级判断"] = "正常成本可部署，高滑点不通过"
    return out


def _build_supply_audit() -> pd.DataFrame:
    summary = pd.read_csv(STAGE359_SUMMARY)
    full = summary[summary["window_name"].eq("full_2020_2026")].copy()
    focus = full[full["variant"].isin(["C3_existing_2023plus", "C3_backfilled_2020_2026"])].copy()
    decision = _load_json(STAGE359_DECISION)
    focus["供需审计结论"] = focus["variant"].map(
        {
            "C3_existing_2023plus": "原2023+供需信号工程口径",
            "C3_backfilled_2020_2026": "2020-2022已补齐并合并复跑，但结果失败",
        }
    )
    focus["合并信号行数"] = int(decision["combined_signal_rows"])
    return focus[
        [
            "variant",
            "display_label",
            "window_name",
            "end_balance",
            "total_return_pct",
            "max_dd_percent",
            "sharpe_ratio",
            "total_trade_count",
            "win_ratio_pct",
            "合并信号行数",
            "供需审计结论",
        ]
    ]


def _build_route_matrix(xsmom_decision: dict[str, Any], supply_decision: dict[str, Any]) -> pd.DataFrame:
    rows = [
        {
            "路线": "补齐23年前供需数据",
            "证据阶段": "Stage057-059",
            "结论": "已补齐并复跑；不是市场没有数据，而是原工程只覆盖2023-2026",
            "是否继续作为主路径": "否",
            "原因": "补齐后C3总收益从6085.13%降到951.30%，最大回撤从-31.08%恶化到-48.02%",
            "下一步": "保留为审计/解释层；禁止继续调供需阈值、有效期或权重小数",
        },
        {
            "路线": "C3当前单策略",
            "证据阶段": "Stage018/065",
            "结论": "比正式78-1收益更高、曲线更平滑，但最大回撤仍为-31.08%",
            "是否继续作为主路径": "是，作为研究基准",
            "原因": "收益效率最好，且相对78-1明显降低回撤和Ulcer，但离30以内还差约1.08pp",
            "下一步": "不要用小数补丁救；只接受新独立收益源或部署层资金边界",
        },
        {
            "路线": "50万C3下单 + 11.5万外部现金",
            "证据阶段": "Stage055/065",
            "结论": "正常成本下达到30以内和80%收益保留",
            "是否继续作为主路径": "是，作为部署边界",
            "原因": "9/9多周期通过；但2x/3x滑点收益保留失败",
            "下一步": "如果接受正常低频成本假设，这是当前最低过拟合可执行方案",
        },
        {
            "路线": "xsmom期货卫星",
            "证据阶段": "Stage045-049/066",
            "结论": "xsmom有净值层价值，但当前期货卫星承载方式失败",
            "是否继续作为主路径": "否，当前承载方式停止",
            "原因": "净值层有效不等于3.75万或35/15真实整数手数可交易；多起点和滑点失败",
            "下一步": "停止当前期货卫星形状；除非换承载工具、显著提高资金口径，或仅作为监控/解释层",
        },
        {
            "路线": "Carry/季节性/同源周期稀释",
            "证据阶段": "Stage043/056/064/065",
            "结论": "能让净值更平滑，但主要来自稀释或负收益腿",
            "是否继续作为主路径": "否",
            "原因": "收益源自身不合格，多周期反证，不满足收益不显著降低",
            "下一步": "停止调月份、权重、周期相邻小数",
        },
    ]
    if supply_decision["decision"] != "fail_backfilled_supply_does_not_solve_drawdown30":
        rows[0]["是否继续作为主路径"] = "待复核"
    return pd.DataFrame(rows)


def _focus_annual(annual: pd.DataFrame) -> pd.DataFrame:
    keep = ["A_official78_1_50w", "B_c3_current_50w", "D_c3_50w_plus_115k_external_cash"]
    return annual[annual["variant"].isin(keep)].copy()


def _focus_rolling(rolling: pd.DataFrame) -> pd.DataFrame:
    keep = ["A_official78_1_50w", "B_c3_current_50w", "D_c3_50w_plus_115k_external_cash"]
    return rolling[rolling["variant"].isin(keep)].copy()


def _write_report(
    comparison: pd.DataFrame,
    route_matrix: pd.DataFrame,
    supply_audit: pd.DataFrame,
    annual_focus: pd.DataFrame,
    rolling_focus: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    c3 = comparison[comparison["variant"].eq("B_c3_current_50w")].iloc[0]
    deployment = comparison[comparison["variant"].eq("D_c3_50w_plus_115k_external_cash")].iloc[0]
    official = comparison[comparison["variant"].eq("A_official78_1_50w")].iloc[0]
    supply_backfilled = supply_audit[supply_audit["variant"].eq("C3_backfilled_2020_2026")].iloc[0]

    comparison_view = comparison[
        [
            "名称",
            "状态",
            "总收益_pct",
            "最大回撤_pct",
            "Ulcer_pct",
            "Sharpe",
            "相对C3收益保留_pct",
            "可直接晋级判断",
        ]
    ].copy()
    for col in ["总收益_pct", "最大回撤_pct", "Ulcer_pct", "相对C3收益保留_pct"]:
        comparison_view[col] = comparison_view[col].map(_fmt_pct)
    comparison_view["Sharpe"] = comparison_view["Sharpe"].map(lambda x: _fmt_num(x, 4))

    supply_view = supply_audit.copy()
    for col in ["total_return_pct", "max_dd_percent", "win_ratio_pct"]:
        supply_view[col] = supply_view[col].map(_fmt_pct)
    supply_view["end_balance"] = supply_view["end_balance"].map(lambda x: _fmt_num(x, 2))
    supply_view["sharpe_ratio"] = supply_view["sharpe_ratio"].map(lambda x: _fmt_num(x, 4))

    annual_view = annual_focus.copy()
    annual_view["annual_return_pct"] = annual_view["annual_return_pct"].map(_fmt_pct)
    rolling_view = rolling_focus.copy()
    for col in ["worst_return_pct", "nonpositive_ratio_pct"]:
        rolling_view[col] = rolling_view[col].map(_fmt_pct)

    lines = [
        "# Stage067 部署边界可行性与路线决策",
        "",
        f"- line_id：`{LINE_ID}`",
        "- 当前模式：day",
        "- 记录时间：2026-05-26 21:46 CST",
        "- 阶段性质：既有证据归档与路线决策；不新增策略参数",
        "- 是否重要突破：是，明确供需补齐不是剩余主路径，当前最低过拟合可执行边界仍是部署层现金方案",
        "- 是否触发A/B：否；本阶段不修改78-1/C3交易逻辑，不创建新策略候选。",
        "",
        "## 外部调研与判断",
        "",
        "- 趋势跟随长期研究通常强调跨市场分散、风险预算和独立收益源；这支持我们优先做低自由度风险治理，而不是事后品种/阈值补丁。",
        "- 时间序列动量和波动缩放文献说明风险缩放会显著影响趋势策略，但我们本地 Stage033-035 已证明日收益层缩放落到真实期货引擎会破坏趋势腿，不能直接照搬。",
        "- 我的判断：本线现在不是“少补一批供需数据”的问题，而是 C3 自然回撤边界约在31%附近；要进30以内，要么接受部署层现金边界，要么找到新的可承载独立收益源。",
        "",
        "## 先回答供需数据问题",
        "",
        "- 23年之前不是没有供需数据。",
        "- 之前缺口来自本地工程口径：Stage316 最早只生成了 2023-2026 的供需信号。",
        "- Stage058 已经补齐 2020-2022，Stage059 已经合并到 2020-2026 并复跑。",
        f"- 合并后供需信号共 `{int(supply_backfilled['合并信号行数'])}` 行。",
        f"- 结果：补齐供需 C3 总收益 `{_fmt_pct(supply_backfilled['total_return_pct'])}`，最大回撤 `{_fmt_pct(supply_backfilled['max_dd_percent'])}`，不如现有 C3。",
        "- 结论：补齐是必要审计，但当前强逆风过滤不能继续作为降回撤主路径。",
        "",
        "## 核心版本对比",
        "",
        to_markdown_table(comparison_view),
        "",
        "## 路线决策表",
        "",
        to_markdown_table(route_matrix),
        "",
        "## 供需补齐审计",
        "",
        to_markdown_table(
            supply_view[
                [
                    "display_label",
                    "end_balance",
                    "total_return_pct",
                    "max_dd_percent",
                    "sharpe_ratio",
                    "total_trade_count",
                    "win_ratio_pct",
                    "供需审计结论",
                ]
            ]
        ),
        "",
        "## 年度收益焦点",
        "",
        to_markdown_table(annual_view[["label", "year", "annual_return_pct"]]),
        "",
        "## 滚动窗口焦点",
        "",
        to_markdown_table(rolling_view[["label", "window_trading_days", "worst_return_pct", "worst_end_date", "nonpositive_ratio_pct"]]),
        "",
        "## 结论",
        "",
        f"- 正式78-1：总收益 `{_fmt_pct(official['总收益_pct'])}`，最大回撤 `{_fmt_pct(official['最大回撤_pct'])}`，Ulcer `{_fmt_pct(official['Ulcer_pct'])}`。",
        f"- C3：总收益 `{_fmt_pct(c3['总收益_pct'])}`，最大回撤 `{_fmt_pct(c3['最大回撤_pct'])}`，Ulcer `{_fmt_pct(c3['Ulcer_pct'])}`；相对78-1已经更平滑、收益也更高，但没有进30以内。",
        f"- 部署边界：`50万C3下单 + 11.5万外部现金` 总收益 `{_fmt_pct(deployment['总收益_pct'])}`，最大回撤 `{_fmt_pct(deployment['最大回撤_pct'])}`，相对C3收益保留 `{_fmt_pct(deployment['相对C3收益保留_pct'])}`。这是当前正常成本口径最低过拟合可执行方案。",
        "- 当前不应继续补供需阈值、xsmom权重、季节性月份、Carry权重或同源周期小数；这些方向已有明确反证。",
        "- 若目标必须是“单策略、不增加外部现金、且高滑点也稳健进30以内”，当前仍未完成，需要寻找全新的独立收益源或换承载工具。",
        "",
        "## 过拟合反思",
        "",
        "- 运行前判断：不是过拟合。本阶段只汇总已冻结证据，不新增参数。",
        "- 运行后判断：不是过拟合。失败路线被停止，候选边界被降级或限定使用条件，没有用结果反向调阈值。",
        "- 风险提示：如果继续围绕供需阈值、7天有效期、xsmom 7.5%、35/15、季节性10%等小数救援，会转为过拟合。",
        "",
        "## 继续价值反思",
        "",
        "- 运行前判断：有价值。需要把供需补齐事实和当前候选边界固化，避免重复研究。",
        "- 运行后判断：有价值，但继续方向必须变窄。",
        "- 继续有价值的方向只有两类：接受 Stage055 正常成本部署边界；或者寻找新的独立收益源/承载工具。",
        "",
        "## 输出文件",
        "",
        f"- comparison：`{COMPARISON_PATH.name}`",
        f"- route_matrix：`{ROUTE_MATRIX_PATH.name}`",
        f"- supply_audit：`{SUPPLY_AUDIT_PATH.name}`",
        f"- annual_focus：`{ANNUAL_PATH.name}`",
        f"- rolling_focus：`{ROLLING_PATH.name}`",
        f"- decision：`{DECISION_PATH.name}`",
        "",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    summary = pd.read_csv(STAGE365_SUMMARY)
    annual = pd.read_csv(STAGE365_ANNUAL)
    rolling = pd.read_csv(STAGE365_ROLLING)
    supply_decision = _load_json(STAGE359_DECISION)
    xsmom_decision = _load_json(STAGE366_DECISION)

    comparison = _build_comparison(summary)
    supply_audit = _build_supply_audit()
    route_matrix = _build_route_matrix(xsmom_decision, supply_decision)
    annual_focus = _focus_annual(annual)
    rolling_focus = _focus_rolling(rolling)

    blocked_routes = route_matrix[
        route_matrix["是否继续作为主路径"].astype(str).str.startswith("否")
    ]["路线"].tolist()

    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "decision": "normal_cost_deployment_boundary_is_current_best_low_overfit_route",
        "target_max_dd_pct": TARGET_MAX_DD_PCT,
        "strict_return_retention_pct": STRICT_RETENTION_PCT,
        "supply_before_2023_status": "backfilled_and_failed_as_direct_filter",
        "current_best_single_strategy": "B_c3_current_50w",
        "current_best_normal_cost_deployment_boundary": "D_c3_50w_plus_115k_external_cash",
        "strategy_internal_candidate_promotable": False,
        "deployment_boundary_promotable_under_normal_cost": True,
        "deployment_boundary_promotable_under_slippage_stress": False,
        "blocked_routes": blocked_routes,
        "next_action": "accept_stage055_normal_cost_boundary_or_search_new_independent_return_source",
        "outputs": {
            "comparison": COMPARISON_PATH.name,
            "route_matrix": ROUTE_MATRIX_PATH.name,
            "supply_audit": SUPPLY_AUDIT_PATH.name,
            "annual_focus": ANNUAL_PATH.name,
            "rolling_focus": ROLLING_PATH.name,
            "report": REPORT_PATH.name,
        },
    }

    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    route_matrix.to_csv(ROUTE_MATRIX_PATH, index=False, encoding="utf-8-sig")
    supply_audit.to_csv(SUPPLY_AUDIT_PATH, index=False, encoding="utf-8-sig")
    annual_focus.to_csv(ANNUAL_PATH, index=False, encoding="utf-8-sig")
    rolling_focus.to_csv(ROLLING_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(comparison, route_matrix, supply_audit, annual_focus, rolling_focus, decision)

    print(json.dumps(decision, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
