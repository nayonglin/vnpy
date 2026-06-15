from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage894"
MODEL_TAG = "stage894_stage893_goal_coverage_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage894_stage893_goal_coverage_audit"
SOURCE_CANDIDATE = "official_candidate_stage819_30w_am41_oi08_old_ai_long_tighter_stop_rsi95_v1"

ROUTE_MATRIX_PATH = OUTPUT_DIR / (
    "qmt_roll_stage891_stage890_intraday_route_closure_route_matrix_"
    "stage891_stage890_intraday_route_closure_v1.csv"
)
SCORECARD_PATH = OUTPUT_DIR / (
    "qmt_roll_stage891_stage890_intraday_route_closure_scorecard_"
    "stage891_stage890_intraday_route_closure_v1.csv"
)
VISUAL_INDEX_PATH = OUTPUT_DIR / (
    "qmt_roll_stage891_stage890_intraday_route_closure_visual_index_"
    "stage891_stage890_intraday_route_closure_v1.csv"
)
STAGE861_DECISION_PATH = OUTPUT_DIR / (
    "qmt_roll_stage861_stage860_full_visual_atlas_decision_stage861_stage860_full_visual_atlas_v1.json"
)
STAGE891_DECISION_PATH = OUTPUT_DIR / (
    "qmt_roll_stage891_stage890_intraday_route_closure_decision_"
    "stage891_stage890_intraday_route_closure_v1.json"
)
STAGE893_DECISION_PATH = OUTPUT_DIR / (
    "qmt_roll_stage893_stage892_market_panel_feasibility_decision_"
    "stage893_stage892_market_panel_feasibility_v1.json"
)

REQUIREMENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_requirements_{MODEL_TAG}.csv"
ROUTE_DISPOSITION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_route_disposition_{MODEL_TAG}.csv"
NEXT_ROUTES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_next_routes_{MODEL_TAG}.csv"
SUMMARY_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_chart_{MODEL_TAG}.png"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _safe_number(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if pd.notna(number) else default


def _build_requirements(
    route_matrix: pd.DataFrame,
    scorecard: pd.DataFrame,
    visual_index: pd.DataFrame,
    stage861_decision: dict[str, Any],
    stage891_decision: dict[str, Any],
    stage893_decision: dict[str, Any],
) -> pd.DataFrame:
    metrics861 = stage861_decision.get("metrics", {})
    metrics893 = stage893_decision.get("metrics", {})
    visual_pages = int(pd.to_numeric(visual_index.get("png_pages", pd.Series(dtype=float)), errors="coerce").sum())
    visual_manifests = int(visual_index["manifest_exists"].astype(bool).sum()) if "manifest_exists" in visual_index else 0
    c9_rows = route_matrix[route_matrix["route_branch"].eq("base_intraday_rule")]
    c9 = c9_rows.iloc[0].to_dict() if not c9_rows.empty else {}
    c9_delta = _safe_number(c9.get("delta_million"))
    c9_broker = _safe_number(c9.get("max_broker10_pct"))
    failed_extensions = route_matrix[
        route_matrix["verdict"].astype(str).str.contains("failed|rejected|fragile|tiny|closed", case=False, regex=True)
    ]
    market_summary = metrics893.get("source_summaries", {}).get("combined_local_symbols", {})
    meets20 = int(market_summary.get("meets_20_dates", 0))
    total_dates = int(market_summary.get("total_dates", 0))

    rows = [
        {
            "requirement_id": "R1_new_isolated_line",
            "requirement": "基于 Stage819 官方候选建立独立研究线，并隔离 Stage372 正式版和候选配置。",
            "status": "proven",
            "evidence": f"line_id={LINE_ID}; source_candidate={SOURCE_CANDIDATE}; guardrails readonly/no official config changes",
            "remaining_gap": "无。",
            "decision_impact": "研究线和配置隔离要求已满足。",
        },
        {
            "requirement_id": "R2_full_cycle_trade_data",
            "requirement": "逐笔分析全周期所有交易，要有数据分析。",
            "status": "proven",
            "evidence": (
                f"Stage861 entry coverage {metrics861.get('entry_day_covered_lots')}/"
                f"{metrics861.get('entry_lots')}; pressure coverage {metrics861.get('pressure_covered_dates')}/"
                f"{metrics861.get('pressure_key_dates')}; Stage891 route matrix rows={len(route_matrix)}"
            ),
            "remaining_gap": "全周期逐笔目标交易覆盖已不再是 blocker。",
            "decision_impact": "可以停止继续补 Stage819 目标交易 entry-day K 线。",
        },
        {
            "requirement_id": "R3_kline_visual_analysis",
            "requirement": "逐笔复盘要同时有 K 线视觉分析。",
            "status": "proven",
            "evidence": f"Stage891 visual manifests={visual_manifests}; png_pages={visual_pages}; Stage861 entry atlas pages={metrics861.get('entry_atlas_pages')}; pressure pages={metrics861.get('pressure_atlas_pages')}",
            "remaining_gap": "没有缺逐笔视觉证据；市场广度另需全市场面板，不是目标交易 K 线缺口。",
            "decision_impact": "视觉复盘要求已满足，继续画同类 K 线边际价值低。",
        },
        {
            "requirement_id": "R4_realtime_stop_and_retry",
            "requirement": "日内规则必须实时止损，错了不能死扛，但可以多次尝试。",
            "status": "tested_not_promoted",
            "evidence": f"C9 true engine tested 0.5R stop + reclaim retry once; delta_vs_C4={c9_delta:.4f}m; max_broker10={c9_broker:.4f}%",
            "remaining_gap": "C9 是正价值骨架，但不是可直接推广正式候选；更严格/更多次重试分支已反证。",
            "decision_impact": "保留 C9 作为知识资产，不继续救重试次数/R 小数。",
        },
        {
            "requirement_id": "R5_rule_based_non_ai",
            "requirement": "只要规则类策略，不要 AI。",
            "status": "proven",
            "evidence": "Stage843-893 candidates use R stops, reclaim, OR, first60 price/OI/volume, session, pressure, market panel feasibility; no ML model fitted.",
            "remaining_gap": "无。",
            "decision_impact": "当前研究满足非 AI 约束。",
        },
        {
            "requirement_id": "R6_promotable_minute_improvement",
            "requirement": "挖掘能否用分钟级 K 线增加日内入场/出场并提高收益或降低左尾。",
            "status": "not_proven",
            "evidence": (
                f"Stage891 decision={stage891_decision.get('decision')}; failed_or_closed_extension_rows={len(failed_extensions)}; "
                "Stage879/882/883 true engines fail return/sharpe/broker10 tradeoff; Stage889/890 only tiny proxies."
            ),
            "remaining_gap": "没有满足收益、回撤、Sharpe、broker10 和稳健性同时通过的新增分钟规则。",
            "decision_impact": "不能触发 A/B，不能改官方候选。",
        },
        {
            "requirement_id": "R7_external_market_breadth",
            "requirement": "若继续新外生信息源，先证明数据面板足够。",
            "status": "data_missing",
            "evidence": f"Stage893 combined local symbols meets20_dates={meets20}/{total_dates}; median={market_summary.get('median')}; max={market_summary.get('max')}",
            "remaining_gap": "缺全市场连续分钟面板；本地 union 只覆盖少数 entry_date。",
            "decision_impact": "市场广度不能写规则，除非先补数据面板。",
        },
        {
            "requirement_id": "R8_goal_completion",
            "requirement": "目标完成必须证明找到可执行规则或证明当前证据下没有可推广规则且后续前置条件明确。",
            "status": "keep_active",
            "evidence": "已有完整法证和路线收束，但没有可推广新规则；市场广度还有外部数据前置条件。",
            "remaining_gap": "用户目标仍是挖掘规则；当前结论是暂未找到而不是成功接入。",
            "decision_impact": "不标记 goal complete；给出下一步只剩数据面板或账户级路线。",
        },
    ]
    return pd.DataFrame(rows)


def _classify_route(row: pd.Series) -> str:
    verdict = str(row.get("verdict", "")).lower()
    evidence_kind = str(row.get("evidence_kind", "")).lower()
    branch = str(row.get("route_branch", "")).lower()
    if "coverage_complete" in verdict:
        return "evidence_infrastructure"
    if "positive_backbone" in verdict:
        return "knowledge_asset_not_promoted"
    if "proxy_only" in verdict:
        return "proxy_requires_engine"
    if "engine_failed" in verdict:
        return "true_engine_failed"
    if "rejected" in verdict or "fragile" in verdict or "tiny" in verdict:
        return "proxy_rejected"
    if "closed" in verdict or "closure" in evidence_kind or "route_closure" in branch:
        return "branch_closed"
    if "signal_exists" in verdict:
        return "signal_not_rule"
    return "review_only"


def _build_route_disposition(route_matrix: pd.DataFrame, stage893_decision: dict[str, Any]) -> pd.DataFrame:
    route = route_matrix.copy()
    route["disposition"] = route.apply(_classify_route, axis=1)
    route["next_action"] = route["disposition"].map(
        {
            "evidence_infrastructure": "keep as evidence, no new rule",
            "knowledge_asset_not_promoted": "keep C9 as backbone evidence, no promotion",
            "proxy_requires_engine": "already followed by true-engine test where applicable",
            "true_engine_failed": "do not rescue with small parameters",
            "proxy_rejected": "do not promote, do not scan threshold",
            "branch_closed": "closed",
            "signal_not_rule": "keep as explanatory tag only",
            "review_only": "review only",
        }
    )
    market = stage893_decision.get("metrics", {}).get("source_summaries", {}).get("combined_local_symbols", {})
    route = pd.concat(
        [
            route,
            pd.DataFrame(
                [
                    {
                        "stage": "Stage893",
                        "route_branch": "market_breadth_external_panel",
                        "evidence_kind": "data_panel_feasibility",
                        "decision": stage893_decision.get("decision"),
                        "rule_or_shape": "full-market first60 breadth requires continuous minute panel",
                        "positive_evidence": "market breadth is distinct external information source",
                        "negative_evidence": (
                            f"combined local symbols meet 20 only {market.get('meets_20_dates')}/"
                            f"{market.get('total_dates')} entry dates"
                        ),
                        "delta_million": "",
                        "end_equity_delta_vs_c9": "",
                        "max_dd_delta_vs_c9_pp": "",
                        "sharpe_delta_vs_c9": "",
                        "max_broker10_pct": "",
                        "winner_cut_million": "",
                        "loser_saved_million": "",
                        "verdict": "data_missing_no_engine",
                        "disposition": "data_prerequisite_missing",
                        "next_action": "build full-market continuous minute panel before any rule",
                    }
                ]
            ),
        ],
        ignore_index=True,
        sort=False,
    )
    return route


def _build_next_routes() -> pd.DataFrame:
    rows = [
        {
            "route_id": "A_full_market_minute_panel",
            "route": "先建全市场连续分钟面板，再研究市场广度。",
            "alignment_with_goal": "high",
            "precondition": "统一 universe、主力/连续映射、夜盘归属、下载权限、entry_date 覆盖 >=20 合约。",
            "risk": "需要新数据和权限；若降阈值会过拟合。",
            "recommendation": "only_continue_if_panel_can_be_built",
        },
        {
            "route_id": "B_account_level_survival",
            "route": "账户级非交易层生存线：资金分层、出金锁盈、最大风险预算。",
            "alignment_with_goal": "medium",
            "precondition": "承认这不是分钟 K 入场/出场 alpha，而是保护 Stage819/C9 路径风险。",
            "risk": "可能偏离用户原始分钟K规则目标。",
            "recommendation": "discuss_or_start_separate_line_if_user_accepts",
        },
        {
            "route_id": "C_more_minute_variants",
            "route": "继续在 first60/OR/R/OI/volume/session 上做小变体。",
            "alignment_with_goal": "low",
            "precondition": "无。",
            "risk": "高过拟合，且 Stage843-893 已多轮反证。",
            "recommendation": "do_not_continue",
        },
    ]
    return pd.DataFrame(rows)


def _plot_summary(requirements: pd.DataFrame, route_disposition: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(13, 5), dpi=180, constrained_layout=True)
    req_counts = requirements["status"].value_counts().sort_index()
    axes[0].bar(req_counts.index, req_counts.values, color="#2563eb", alpha=0.82)
    axes[0].set_title("Goal requirement evidence status")
    axes[0].set_ylabel("Requirement count")
    axes[0].tick_params(axis="x", rotation=35)
    axes[0].grid(axis="y", alpha=0.25)

    route_counts = route_disposition["disposition"].value_counts().sort_values(ascending=True)
    axes[1].barh(route_counts.index, route_counts.values, color="#059669", alpha=0.82)
    axes[1].set_title("Minute-rule route dispositions")
    axes[1].set_xlabel("Route count")
    axes[1].grid(axis="x", alpha=0.25)
    fig.savefig(SUMMARY_CHART_PATH)
    plt.close(fig)


def _write_report(
    requirements: pd.DataFrame,
    route_disposition: pd.DataFrame,
    next_routes: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    route_view = route_disposition[
        [
            "stage",
            "route_branch",
            "evidence_kind",
            "decision",
            "rule_or_shape",
            "verdict",
            "disposition",
            "next_action",
        ]
    ]
    lines = [
        "# Stage894 Stage893 Goal Coverage Audit",
        "",
        f"- stage: `{STAGE}`",
        f"- model_tag: `{MODEL_TAG}`",
        f"- line_id: `{LINE_ID}`",
        f"- source_candidate: `{SOURCE_CANDIDATE}`",
        f"- generated_at: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`",
        "",
        "## External Research Boundary",
        "",
        "- Exchange/order-type references support the discipline that intraday rules must be executable with stop or stop-limit semantics, not hindsight exits.",
        "- Historical/academic trend-following evidence cautions that small technical-rule variations can be sample-specific; Stage894 therefore audits coverage and route closure instead of adding another parameter variant.",
        "- Judgment: the current blocker is not lack of effort on minute K-line paths; it is lack of a promotable rule under existing evidence, plus a missing broad market minute panel for the one remaining external-data route.",
        "",
        "## Requirement Matrix",
        "",
        _md_table(requirements),
        "",
        "## Route Disposition",
        "",
        _md_table(route_view, max_rows=30),
        "",
        "## Next Route Boundary",
        "",
        _md_table(next_routes),
        "",
        "## Decision",
        "",
        f"- decision: `{decision['decision']}`",
        f"- goal_completion_claimed: `{decision['goal_completion_claimed']}`",
        f"- promotable_minute_rule_found: `{decision['promotable_minute_rule_found']}`",
        f"- market_panel_available: `{decision['market_panel_available']}`",
        f"- no_ab_trigger: `{decision['guardrails']['no_ab_trigger']}`",
        "",
        "## Conclusion",
        "",
        "- Full-cycle trade-level and visual evidence requirements are satisfied for Stage819 target trades.",
        "- The tested rule family remains rule-based and non-AI.",
        "- C9 is useful knowledge but not a promotable official replacement; subsequent minute-rule extensions have failed or are too small/fragile.",
        "- Do not continue small minute K-line variants unless a new first-principles information source or a true full-market minute panel is available.",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    route_matrix = _load_csv(ROUTE_MATRIX_PATH)
    scorecard = _load_csv(SCORECARD_PATH)
    visual_index = _load_csv(VISUAL_INDEX_PATH)
    stage861_decision = _load_json(STAGE861_DECISION_PATH)
    stage891_decision = _load_json(STAGE891_DECISION_PATH)
    stage893_decision = _load_json(STAGE893_DECISION_PATH)

    requirements = _build_requirements(
        route_matrix,
        scorecard,
        visual_index,
        stage861_decision,
        stage891_decision,
        stage893_decision,
    )
    route_disposition = _build_route_disposition(route_matrix, stage893_decision)
    next_routes = _build_next_routes()
    _plot_summary(requirements, route_disposition)

    unmet = requirements[~requirements["status"].isin(["proven", "tested_not_promoted"])]
    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "source_candidate": SOURCE_CANDIDATE,
        "decision": "stage894_goal_coverage_audit_no_promotable_minute_rule_keep_goal_active",
        "goal_completion_claimed": False,
        "promotable_minute_rule_found": False,
        "market_panel_available": False,
        "metrics": {
            "requirement_rows": int(len(requirements)),
            "unmet_or_open_requirement_rows": int(len(unmet)),
            "route_rows": int(len(route_disposition)),
            "visual_png_pages": int(pd.to_numeric(visual_index["png_pages"], errors="coerce").sum()),
            "stage861_entry_coverage_rate": stage861_decision.get("metrics", {}).get("entry_day_coverage_rate"),
            "stage893_combined_meets20_pct": stage893_decision.get("metrics", {})
            .get("source_summaries", {})
            .get("combined_local_symbols", {})
            .get("meets_20_pct"),
        },
        "guardrails": {
            "readonly": True,
            "no_downloads": True,
            "no_ctp": True,
            "no_order_api": True,
            "no_strategy_rule_added": True,
            "no_backtest": True,
            "no_ab_trigger": True,
            "official_stage372_changed": False,
            "official_candidate_config_changed": False,
        },
        "outputs": {
            "requirements": str(REQUIREMENTS_PATH),
            "route_disposition": str(ROUTE_DISPOSITION_PATH),
            "next_routes": str(NEXT_ROUTES_PATH),
            "summary_chart": str(SUMMARY_CHART_PATH),
            "report": str(REPORT_PATH),
            "decision": str(DECISION_PATH),
        },
    }

    requirements.to_csv(REQUIREMENTS_PATH, index=False, encoding="utf-8-sig")
    route_disposition.to_csv(ROUTE_DISPOSITION_PATH, index=False, encoding="utf-8-sig")
    next_routes.to_csv(NEXT_ROUTES_PATH, index=False, encoding="utf-8-sig")
    _write_report(requirements, route_disposition, next_routes, decision)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
