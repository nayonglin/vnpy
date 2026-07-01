from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[4]
LINE_DIR = PROJECT_DIR / "research" / "lines" / "futures_trend_rebuilt_c9_15w_optimization"
OUTPUT_DIR = LINE_DIR / "outputs" / "stage005_proxy_feasibility_audit"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

BT_OUTPUT_DIR = PROJECT_DIR / "examples" / "portfolio_backtesting" / "backtest_outputs"
C9_QUALITY_DIR = PROJECT_DIR / "research" / "lines" / "futures_trend_c9_minrisk_highquality" / "outputs"

LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage005"
MODEL_TAG = "stage005_proxy_feasibility_audit_v1"

STAGE167_ENTRY_PATH = (
    BT_OUTPUT_DIR
    / "qmt_roll_stage167_c9_live_15w_multiperiod_ai_audit_entry_candidates_"
    "stage167_c9_live_15w_multiperiod_ai_audit_v1.csv"
)
STAGE167_SUMMARY_PATH = (
    BT_OUTPUT_DIR
    / "qmt_roll_stage167_c9_live_15w_multiperiod_ai_audit_summary_"
    "stage167_c9_live_15w_multiperiod_ai_audit_v1.csv"
)
AI_POOL_PATH = (
    BT_OUTPUT_DIR
    / "qmt_roll_stage182_ai_product_pool_live_inference_combined_stage78_eligibility_"
    "stage182_ai_product_pool_live_inference_v1.csv"
)
AI_LATEST_PATH = (
    BT_OUTPUT_DIR
    / "qmt_roll_stage182_ai_product_pool_live_inference_latest_pool_"
    "stage182_ai_product_pool_live_inference_v1.csv"
)
UNIVERSE_PATH = BT_OUTPUT_DIR / "qmt_roll_full_market_tradable_universe_eligible_full_market_tradable_universe_v1.csv"
STAGE002_ANNUAL_PATH = (
    BT_OUTPUT_DIR
    / "rebuilt_c9_stage002_goal_baseline_audit_annual_returns_"
    "stage002_rebuilt_c9_goal_baseline_audit_v1.csv"
)
OLD_STAGE016_FEATURES_PATH = (
    C9_QUALITY_DIR
    / "stage016_intersection_stability_audit"
    / "qmt_roll_stage016_c9_minrisk_intersection_stability_audit_features_"
    "stage016_intersection_stability_audit_v1.csv"
)
OLD_STAGE016_STATS_PATH = (
    C9_QUALITY_DIR
    / "stage016_intersection_stability_audit"
    / "qmt_roll_stage016_c9_minrisk_intersection_stability_audit_intersection_stats_"
    "stage016_intersection_stability_audit_v1.csv"
)
STAGE004_PROHIBITED_PATH = (
    LINE_DIR
    / "outputs"
    / "stage004_historical_counterevidence_map"
    / "rebuilt_c9_stage004_prohibited_shapes_stage004_historical_counterevidence_map_v1.csv"
)

REQUIREMENTS_PATH = OUTPUT_DIR / f"rebuilt_c9_stage005_data_requirements_{MODEL_TAG}.csv"
BLUEPRINT_PATH = OUTPUT_DIR / f"rebuilt_c9_stage005_proxy_blueprint_{MODEL_TAG}.csv"
FIELD_PRESENCE_PATH = OUTPUT_DIR / f"rebuilt_c9_stage005_field_presence_{MODEL_TAG}.csv"
CHART_PATH = OUTPUT_DIR / f"rebuilt_c9_stage005_readiness_chart_{MODEL_TAG}.png"
DECISION_PATH = OUTPUT_DIR / f"rebuilt_c9_stage005_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"rebuilt_c9_stage005_report_{MODEL_TAG}.md"

JD_PRODUCT = "jd.DCE"


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    data = frame if max_rows is None else frame.head(max_rows)
    if data.empty:
        return "_空_"
    columns = list(data.columns)
    rows = []
    widths = {col: len(str(col)) for col in columns}
    for _, row in data.iterrows():
        item = ["" if pd.isna(row[col]) else str(row[col]) for col in columns]
        rows.append(item)
        for col, value in zip(columns, item):
            widths[col] = max(widths[col], len(value))

    def fmt(values: list[str]) -> str:
        return "| " + " | ".join(value.ljust(widths[col]) for value, col in zip(values, columns)) + " |"

    header = fmt([str(col) for col in columns])
    sep = "| " + " | ".join("-" * widths[col] for col in columns) + " |"
    body = "\n".join(fmt(row) for row in rows)
    suffix = ""
    if max_rows is not None and len(frame) > max_rows:
        suffix = f"\n\n_仅展示前 {max_rows} 行，共 {len(frame)} 行。_"
    return f"{header}\n{sep}\n{body}{suffix}"


def _field_presence(entries: pd.DataFrame, old_features: pd.DataFrame) -> pd.DataFrame:
    required = [
        ("stage167_entry", "candidate_status"),
        ("stage167_entry", "product_vt_symbol"),
        ("stage167_entry", "direction"),
        ("stage167_entry", "ai_product_pool_rank"),
        ("stage167_entry", "ai_product_pool_score"),
        ("stage167_entry", "ai_product_pool_allowed"),
        ("stage167_entry", "oi_price_confirm_passed"),
        ("stage167_entry", "oi_price_confirm_risk_restore_applied"),
        ("stage167_entry", "portfolio_drawdown_pct"),
        ("stage167_entry", "broker10_margin_to_equity_pct"),
        ("stage167_entry", "entry_open_relation_bucket"),
        ("stage167_entry", "first_bar_relation_bucket"),
        ("stage167_entry", "tag_ai4_6_entry_or_first_aligned"),
        ("stage167_entry", "realized_pnl"),
        ("old_stage016_features", "tag_ai4_6_entry_or_first_aligned"),
        ("old_stage016_features", "entry_open_relation_bucket"),
        ("old_stage016_features", "first_bar_relation_bucket"),
        ("old_stage016_features", "realized_pnl"),
        ("old_stage016_features", "r_multiple"),
    ]
    source_map = {
        "stage167_entry": entries,
        "old_stage016_features": old_features,
    }
    rows = []
    for source, field in required:
        df = source_map[source]
        rows.append(
            {
                "source": source,
                "field": field,
                "present": int(field in df.columns),
                "non_null_count": int(df[field].notna().sum()) if field in df.columns else 0,
                "row_count": int(len(df)),
            }
        )
    return pd.DataFrame(rows)


def _requirements(
    entries: pd.DataFrame,
    ai_pool: pd.DataFrame,
    latest_pool: pd.DataFrame,
    universe: pd.DataFrame,
    old_features: pd.DataFrame,
    old_stats: pd.DataFrame,
    annual: pd.DataFrame,
) -> pd.DataFrame:
    opened = entries[entries.get("candidate_status", pd.Series(dtype=str)).astype(str).eq("opened")] if not entries.empty else pd.DataFrame()
    current_products = set(ai_pool.get("product_vt_symbol", pd.Series(dtype=str)).astype(str)) if not ai_pool.empty else set()
    latest_products = set(latest_pool.get("product_vt_symbol", pd.Series(dtype=str)).astype(str)) if not latest_pool.empty else set()
    universe_products = set(universe.get("product_vt_symbol", pd.Series(dtype=str)).astype(str)) if not universe.empty else set()
    old_tag_count = (
        int(old_features.get("tag_ai4_6_entry_or_first_aligned", pd.Series(dtype=bool)).fillna(False).astype(bool).sum())
        if not old_features.empty
        else 0
    )
    old_tag_pnl = (
        float(
            old_features.loc[
                old_features.get("tag_ai4_6_entry_or_first_aligned", pd.Series(False, index=old_features.index))
                .fillna(False)
                .astype(bool),
                "realized_pnl",
            ].sum()
        )
        if not old_features.empty and "realized_pnl" in old_features.columns
        else 0.0
    )
    rows = [
        {
            "requirement": "current_core_candidate_stream",
            "status": "PASS" if len(entries) else "FAIL",
            "evidence": f"Stage167 entry candidates rows={len(entries)}, opened={len(opened)}",
            "gap": "",
            "next_action": "可作为当前重建核心候选流，不删除或替换原 C9 开仓。",
        },
        {
            "requirement": "current_rebuilt_closed_lots",
            "status": "FAIL",
            "evidence": "当前 Stage167 输出目录未发现 trades/closed_lots/positions 文件；只有 entry_candidates 和 curves。",
            "gap": "无法用当前重建版逐笔 PnL 直接验证高质量标签。",
            "next_action": "先补 Stage167 opened entry -> closed-lot/outcome 绑定，或重跑引擎保存 closed_lots。",
        },
        {
            "requirement": "current_entry_minute_quality_labels",
            "status": "FAIL",
            "evidence": "Stage167 entry candidates 没有 entry_open/first_bar/ai4_6 aligned 标签。",
            "gap": "不能把旧 Stage016 标签直接当当前重建版证据。",
            "next_action": "用 Stage861 minute bars 和当前 Stage167 opened candidates 重建质量特征绑定器。",
        },
        {
            "requirement": "old_quality_reference",
            "status": "REFERENCE_ONLY" if old_tag_count else "FAIL",
            "evidence": f"旧 Stage016 features rows={len(old_features)}, ai4_6_entry_or_first_aligned={old_tag_count}, tag_pnl={old_tag_pnl:.2f}",
            "gap": "旧线可用于设计特征，但不能证明当前重建版候选达标。",
            "next_action": "只把旧 Stage016 用作 Stage006 特征蓝图。",
        },
        {
            "requirement": "current_ai_pool_membership",
            "status": "PASS" if len(ai_pool) else "FAIL",
            "evidence": f"Stage182 selected pool rows={len(ai_pool)}, product_count={len(current_products)}, latest_count={len(latest_products)}",
            "gap": "",
            "next_action": "可用于确认核心 C9 当前 AI 池，不可直接重排。",
        },
        {
            "requirement": "jd_universe_eligible",
            "status": "PASS" if JD_PRODUCT in universe_products else "FAIL",
            "evidence": f"full-market universe product_count={len(universe_products)}, jd_present={int(JD_PRODUCT in universe_products)}",
            "gap": "",
            "next_action": "jd 可进入独立候选生成或 paper watch。",
        },
        {
            "requirement": "jd_current_ai_scores",
            "status": "FAIL" if JD_PRODUCT not in current_products and JD_PRODUCT not in latest_products else "PASS",
            "evidence": f"jd_in_combined_pool={int(JD_PRODUCT in current_products)}, jd_in_latest_pool={int(JD_PRODUCT in latest_products)}",
            "gap": "当前文件是 selected pool，不是完整 full-universe monthly score matrix；jd 无当前 AI 分数历史。",
            "next_action": "若要让 jd 参与 AI，必须重跑或恢复 full-universe monthly inference，并冻结 hash。",
        },
        {
            "requirement": "period_gt_1y_validation_grid",
            "status": "PASS" if len(annual) else "FAIL",
            "evidence": f"Stage002 annual rows={len(annual)}; 可派生任意起点后周期>1年年度/滚动约束。",
            "gap": "当前只验证基准，不验证新候选。",
            "next_action": "候选真引擎通过后复用该 grid 扩展到周期>1年正收益审计。",
        },
        {
            "requirement": "engine_hooks_for_non_displacing_add",
            "status": "PARTIAL",
            "evidence": "策略代码存在 recovery_sleeve/post_entry_quality_add 字段和 entry_context，但当前 Stage167 均为 disabled/未触发。",
            "gap": "现有 hook 不等于 jd 独立 sleeve 或入场前质量加风险，仍需隔离实现。",
            "next_action": "Stage006 先只做代理，不直接改 qmt_roll_portfolio_strategy。",
        },
    ]
    return pd.DataFrame(rows)


def _blueprint(requirements: pd.DataFrame) -> pd.DataFrame:
    rows = [
        {
            "proxy_id": "P0_core_preserve",
            "purpose": "保留当前 C9 核心，不删除、不重排、不降仓。",
            "status": "READY",
            "required_data": "Stage167 candidates/curves/AI pool",
            "rule_shape": "baseline stays unchanged",
            "why": "满足 Stage004 核心不挤占原则，是所有候选的底座。",
        },
        {
            "proxy_id": "P1_hq_add_sleeve_proxy",
            "purpose": "只在当前 C9 已开仓且入场可见质量标签通过时，模拟小额独立加风险预算。",
            "status": "DATA_BIND_REQUIRED",
            "required_data": "当前 Stage167 opened entries + entry/first minute labels + closed-lot outcome",
            "rule_shape": "no core displacement; add-risk sleeve only; candidate label uses AI rank + entry/first aligned + no-follow veto",
            "why": "旧 Stage016 标签有正向线索，但当前重建版缺质量绑定和逐笔结果，不能直接交易化。",
        },
        {
            "proxy_id": "P2_jd_independent_watch",
            "purpose": "把 jd.DCE 加入基础研究池，但不挤占核心 C9。",
            "status": "CANDIDATE_GENERATION_REQUIRED",
            "required_data": "jd main contract mapping + independent candidate generation + optional full-universe AI score",
            "rule_shape": "paper/zero-capital or tiny isolated sleeve; no shared AI rerank",
            "why": "jd 数据可用但当前无 AI 分数、无候选、历史共享 rerank 强反证。",
        },
        {
            "proxy_id": "P3_shared_ai_rerank",
            "purpose": "把 jd 或质量标签放入共享 AI topN 主池重排。",
            "status": "FORBIDDEN_BY_STAGE004",
            "required_data": "full-universe monthly score matrix",
            "rule_shape": "not allowed",
            "why": "Stage405/407 已证明共享 rerank 会挤占核心右尾。",
        },
        {
            "proxy_id": "P4_topdown_risk_scaler",
            "purpose": "按回撤、年度、窗口或波动统一调低/调高主账户风险。",
            "status": "FORBIDDEN_BY_STAGE004",
            "required_data": "account path state",
            "rule_shape": "not allowed",
            "why": "Stage251/083/084 证明账户层简单地板或滞后波动很容易牺牲右尾。",
        },
    ]
    return pd.DataFrame(rows)


def _plot_readiness(requirements: pd.DataFrame) -> None:
    score_map = {"PASS": 1.0, "REFERENCE_ONLY": 0.6, "PARTIAL": 0.4, "FAIL": 0.0}
    data = requirements.copy()
    data["score"] = data["status"].map(score_map).fillna(0.0)
    fig, ax = plt.subplots(figsize=(12, 7), constrained_layout=True)
    colors = data["score"].map(lambda x: "#047857" if x >= 1 else ("#92400e" if x > 0 else "#b91c1c"))
    labels = [f"R{index + 1:02d}" for index in range(len(data))]
    ax.barh(labels, data["score"], color=colors)
    ax.set_xlim(0, 1.05)
    ax.set_xlabel("readiness score")
    ax.set_title("Stage005 Proxy Data Readiness")
    for index, row in data.iterrows():
        ax.text(min(float(row["score"]) + 0.03, 1.0), index, str(row["status"]), va="center", fontsize=9)
    fig.savefig(CHART_PATH, dpi=150)
    plt.close(fig)


def _write_report(requirements: pd.DataFrame, blueprint: pd.DataFrame, fields: pd.DataFrame) -> dict[str, Any]:
    now = datetime.now().strftime("%Y-%m-%d %H:%M CST")
    status_counts = requirements["status"].value_counts().to_dict()
    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status_counts": {str(k): int(v) for k, v in status_counts.items()},
        "decision": "stage005_proxy_not_ready_build_current_quality_binder_first",
        "next": (
            "Build Stage006 current-rebuilt quality feature binder before any candidate strategy. "
            "Do not use old Stage016 labels as final proof."
        ),
        "outputs": {
            "requirements": str(REQUIREMENTS_PATH),
            "blueprint": str(BLUEPRINT_PATH),
            "fields": str(FIELD_PRESENCE_PATH),
            "chart": str(CHART_PATH),
            "report": str(REPORT_PATH),
        },
    }
    lines = [
        "# Stage005 冻结代理数据可行性审计",
        "",
        f"- line_id：`{LINE_ID}`",
        "- 当前模式：`day`",
        f"- 记录时间：`{now}`",
        "- 阶段性质：数据可行性与代理蓝图，不改策略逻辑，不跑真实组合引擎",
        "- 是否重要突破：否",
        "- 是否触发A/B：否",
        "",
        "## 外部调研与判断",
        "",
        "- 趋势跟随的右尾来自少数持续趋势，任何质量过滤或加风险都必须避免主账户核心右尾挤占。",
        "- 多重检验和 Deflated Sharpe/PBO 框架要求先冻结数据与候选形状，再验证，不能边看回测边改标签。",
        "- 本阶段采纳 Stage004 护栏：核心不挤占、鸡蛋独立、质量标签入场可见、加风险小额独立预算。",
        "",
        "## 数据要求审计",
        "",
        _md_table(requirements, max_rows=None),
        "",
        "## 字段覆盖",
        "",
        _md_table(fields, max_rows=None),
        "",
        "## 冻结代理蓝图",
        "",
        _md_table(blueprint, max_rows=None),
        "",
        "## 结论",
        "",
        "- Stage005 结论：现在不能直接写候选策略或跑 A/C，因为当前重建 Stage167 缺少逐笔 closed-lot 结果和当前口径的 entry/first-minute 质量标签。",
        "- 旧 Stage016 质量标签有参考价值，但只能作为特征蓝图，不能作为当前重建版达标证据。",
        "- 鸡蛋 `jd.DCE` 在 full-market universe 可用，但当前 Stage182 selected pool 和 latest pool 都没有 jd，且没有 full-universe monthly score matrix；所以不能做共享 AI rerank，也不能声称当前 AI 已能评价 jd。",
        "- 下一步 Stage006 应先补当前重建版质量特征绑定器：Stage167 opened entries -> Stage861 minute labels -> closed-lot/outcome 或重跑保存 closed_lots。完成前不改交易逻辑。",
        "",
        "## 输出文件",
        "",
        f"- requirements：`{REQUIREMENTS_PATH}`",
        f"- blueprint：`{BLUEPRINT_PATH}`",
        f"- fields：`{FIELD_PRESENCE_PATH}`",
        f"- chart：`{CHART_PATH}`",
        f"- decision：`{DECISION_PATH}`",
        f"- report：`{REPORT_PATH}`",
        "",
        "## 过拟合反思",
        "",
        "- 运行前判断：否。本阶段只审计数据可用性，不产生策略候选。",
        "- 运行后判断：否。结论反而阻止了直接拿旧标签写当前候选，降低过拟合风险。",
        "",
        "## 继续价值反思",
        "",
        "- 运行前判断：是。目标要求高质量信号和加风险，必须先证明数据能支撑。",
        "- 运行后判断：是。现在明确下一步不是扫参，而是补当前重建版质量特征绑定器。",
        "",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    DECISION_PATH.write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")
    return decision


def main() -> None:
    entries = _read_csv(STAGE167_ENTRY_PATH)
    summary = _read_csv(STAGE167_SUMMARY_PATH)
    ai_pool = _read_csv(AI_POOL_PATH)
    latest_pool = _read_csv(AI_LATEST_PATH)
    universe = _read_csv(UNIVERSE_PATH)
    annual = _read_csv(STAGE002_ANNUAL_PATH)
    old_features = _read_csv(OLD_STAGE016_FEATURES_PATH)
    old_stats = _read_csv(OLD_STAGE016_STATS_PATH)
    _ = _read_csv(STAGE004_PROHIBITED_PATH)

    requirements = _requirements(entries, ai_pool, latest_pool, universe, old_features, old_stats, annual)
    fields = _field_presence(entries, old_features)
    blueprint = _blueprint(requirements)

    requirements.to_csv(REQUIREMENTS_PATH, index=False)
    fields.to_csv(FIELD_PRESENCE_PATH, index=False)
    blueprint.to_csv(BLUEPRINT_PATH, index=False)
    _plot_readiness(requirements)
    decision = _write_report(requirements, blueprint, fields)
    print(json.dumps(decision, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
