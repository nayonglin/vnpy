from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage563_breadth_pool_product_selection_thesis_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage563_breadth_pool_product_selection_thesis_audit"

STAGE541_ANNUAL = OUTPUT_DIR / "qmt_roll_stage541_single_product_opportunity_map_annual_stage541_single_product_opportunity_map_v1.csv"
STAGE541_SUMMARY = OUTPUT_DIR / "qmt_roll_stage541_single_product_opportunity_map_summary_stage541_single_product_opportunity_map_v1.csv"
STAGE557_SUMMARY = OUTPUT_DIR / "qmt_roll_stage557_breadth_low_single_risk_pool_audit_summary_stage557_breadth_low_single_risk_pool_audit_v1.csv"
STAGE557_STANDALONE = OUTPUT_DIR / "qmt_roll_stage557_breadth_low_single_risk_pool_audit_satellite_standalone_stage557_breadth_low_single_risk_pool_audit_v1.csv"
STAGE557_PRODUCT = OUTPUT_DIR / "qmt_roll_stage557_breadth_low_single_risk_pool_audit_satellite_product_harvest_stage557_breadth_low_single_risk_pool_audit_v1.csv"
STAGE557_FAMILY = OUTPUT_DIR / "qmt_roll_stage557_breadth_low_single_risk_pool_audit_satellite_family_harvest_stage557_breadth_low_single_risk_pool_audit_v1.csv"
STAGE557_SELECTION = OUTPUT_DIR / "qmt_roll_stage557_breadth_low_single_risk_pool_audit_annual_selection_stage557_breadth_low_single_risk_pool_audit_v1.csv"
STAGE543_SELECTOR = OUTPUT_DIR / "qmt_roll_stage543_ex_ante_product_selector_diagnostic_summary_stage543_ex_ante_product_selector_diagnostic_v1.csv"
STAGE558_GATES = OUTPUT_DIR / "qmt_roll_stage558_external_state_selector_readiness_audit_readiness_gates_stage558_external_state_selector_readiness_audit_v1.csv"
STAGE561_DECISION = OUTPUT_DIR / "qmt_roll_stage561_selector_predictive_audit_protocol_decision_stage561_selector_predictive_audit_protocol_v1.json"

ANNUAL_OPPORTUNITY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_opportunity_{MODEL_TAG}.csv"
MATERIAL_PRODUCTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_material_products_{MODEL_TAG}.csv"
WIDTH_CAPTURE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_width_capture_{MODEL_TAG}.csv"
PRODUCT_CONTRIBUTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_contribution_{MODEL_TAG}.csv"
FAMILY_CONTRIBUTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_family_contribution_{MODEL_TAG}.csv"
GATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

ALL_NONCORE = "breadth_all_noncore_r020_famcap20_corr5075_maxpos8"
PREVPOS_R020 = "breadth_prevpos_r020_famcap20_corr5075_maxpos8"
PREVPOS_R015 = "breadth_prevpos_r015_famcap15_corr5075_maxpos10"
STAGE526 = "stage526_r080_pc25_maxpos4"
STAGE256 = "dynamic_prevtop6_r050_pc15_maxpos3"


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _num(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").fillna(default).astype(float)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        value = float(value)
        return None if math.isnan(value) or math.isinf(value) else value
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _max_drawdown_from_pnl(pnl: pd.Series, initial_equity: float = 115000.0) -> float:
    equity = initial_equity + pnl.fillna(0.0).cumsum()
    high = equity.cummax()
    drawdown = equity / high - 1.0
    return float(drawdown.min() * 100.0)


def build_annual_opportunity(annual: pd.DataFrame) -> pd.DataFrame:
    frame = annual[annual["is_core_product"].eq(0)].copy()
    frame["net_pnl"] = _num(frame, "net_pnl")
    frame["trade_count"] = _num(frame, "trade_count")
    rows: list[dict[str, Any]] = []
    for year, group in frame.groupby("year"):
        group = group.sort_values("net_pnl", ascending=False).copy()
        positive = group[group["net_pnl"] > 0.0]
        active = group[group["trade_count"] > 0.0]
        top1 = group.head(1)
        top3 = group.head(3)
        top6 = group.head(6)
        positive_sum = float(positive["net_pnl"].sum())
        top6_sum = float(top6["net_pnl"].sum())
        rows.append(
            {
                "year": int(year),
                "noncore_count": int(group["product_vt_symbol"].nunique()),
                "active_count": int(active["product_vt_symbol"].nunique()),
                "positive_count": int(positive["product_vt_symbol"].nunique()),
                "total_noncore_single_product_pnl": float(group["net_pnl"].sum()),
                "positive_noncore_single_product_pnl": positive_sum,
                "top1_pnl": float(top1["net_pnl"].sum()),
                "top3_pnl": float(top3["net_pnl"].sum()),
                "top6_pnl": top6_sum,
                "top6_share_of_positive_pnl_pct": (top6_sum / positive_sum * 100.0) if positive_sum > 0 else 0.0,
                "median_product_pnl": float(group["net_pnl"].median()),
                "worst6_pnl": float(group.tail(6)["net_pnl"].sum()),
                "top6_products": ",".join(top6["product_vt_symbol"].astype(str).tolist()),
                "best_product": str(top1["product_vt_symbol"].iloc[0]) if not top1.empty else "",
                "opportunity_exists": int(top6_sum > 0.0 and len(positive) >= 3),
            }
        )
    return pd.DataFrame(rows).sort_values("year")


def build_material_products(summary: pd.DataFrame) -> pd.DataFrame:
    frame = summary[summary["is_core_product"].eq(0)].copy()
    frame["candidate_materiality_pass"] = _num(frame, "candidate_materiality_pass").astype(int)
    frame["abs_core_daily_pnl_corr"] = _num(frame, "core_daily_pnl_corr").abs()
    keep = [
        "product_vt_symbol",
        "exchange",
        "product",
        "total_pnl",
        "total_return_pct",
        "max_dd_pct",
        "ulcer_pct",
        "sharpe",
        "active_year_count",
        "positive_active_years",
        "positive_active_year_rate_pct",
        "core_daily_pnl_corr",
        "abs_core_daily_pnl_corr",
        "max_broker10_margin_to_sleeve_equity_pct",
        "recent_median_volume",
        "candidate_materiality_pass",
        "opportunity_score",
    ]
    keep = [col for col in keep if col in frame.columns]
    return frame[keep].sort_values(["candidate_materiality_pass", "total_pnl"], ascending=[False, False])


def build_width_capture(summary: pd.DataFrame, standalone: pd.DataFrame, selection: pd.DataFrame) -> pd.DataFrame:
    rows = summary[summary["cost_multiplier"].eq(1.0)].copy()
    variants = [STAGE526, STAGE256, ALL_NONCORE, PREVPOS_R020, PREVPOS_R015]
    rows = rows[rows["variant"].isin(variants)].copy()
    stand = standalone[["variant", "sleeve_total_pnl", "sleeve_return_pct", "sleeve_max_dd_pct", "sleeve_sharpe", "sleeve_trade_count", "sleeve_slippage"]].copy()
    rows = rows.merge(stand, on="variant", how="left")

    annual_rows = []
    for variant, group in selection[selection["variant"].isin([ALL_NONCORE, PREVPOS_R020, PREVPOS_R015])].groupby("variant"):
        annual_rows.append(
            {
                "variant": variant,
                "avg_selected_count": float(_num(group, "selected_count").mean()),
                "avg_future_year_single_product_pnl_sum": float(_num(group, "future_year_single_product_pnl_sum").mean()),
                "positive_year_count_by_single_product_sum": int((_num(group, "future_year_single_product_pnl_sum") > 0).sum()),
                "year_count": int(group["year"].nunique()),
                "avg_oracle6_overlap": float(_num(group, "oracle6_overlap").mean()),
                "avg_abs_core_corr": float(_num(group, "avg_abs_core_corr").mean()),
                "max_abs_core_corr": float(_num(group, "max_abs_core_corr").max()),
            }
        )
    annual = pd.DataFrame(annual_rows)
    rows = rows.merge(annual, on="variant", how="left")
    rows["sleeve_cost_to_pnl_pct"] = np.where(
        rows["sleeve_total_pnl"].abs() > 0,
        rows["sleeve_slippage"] / rows["sleeve_total_pnl"].abs() * 100.0,
        np.nan,
    )
    return rows


def build_product_contribution(product: pd.DataFrame) -> pd.DataFrame:
    frame = product[product["variant"].eq(ALL_NONCORE) & product["year"].ge(2021)].copy()
    grouped = (
        frame.groupby("product_vt_symbol", as_index=False)
        .agg(
            satellite_product_net_pnl=("satellite_product_net_pnl", "sum"),
            active_days=("active_days", "sum"),
            max_margin=("max_margin", "max"),
        )
        .sort_values("satellite_product_net_pnl", ascending=False)
    )
    total_pos = grouped.loc[grouped["satellite_product_net_pnl"] > 0, "satellite_product_net_pnl"].sum()
    grouped["positive_pnl_share_pct"] = np.where(
        total_pos > 0,
        grouped["satellite_product_net_pnl"].clip(lower=0) / total_pos * 100.0,
        0.0,
    )
    return grouped


def build_family_contribution(family: pd.DataFrame) -> pd.DataFrame:
    frame = family[family["variant"].eq(ALL_NONCORE) & family["year"].ge(2021)].copy()
    return (
        frame.groupby("product_family", as_index=False)
        .agg(
            satellite_family_net_pnl=("satellite_family_net_pnl", "sum"),
            active_days=("active_days", "sum"),
            max_margin=("max_margin", "max"),
            product_count=("product_count", "max"),
        )
        .sort_values("satellite_family_net_pnl", ascending=False)
    )


def build_gates(
    annual_opportunity: pd.DataFrame,
    material_products: pd.DataFrame,
    width_capture: pd.DataFrame,
    selector_summary: pd.DataFrame,
    readiness_gates: pd.DataFrame,
    stage561_decision: dict[str, Any],
) -> pd.DataFrame:
    all_noncore = width_capture[width_capture["variant"].eq(ALL_NONCORE)].iloc[0]
    stage526 = width_capture[width_capture["variant"].eq(STAGE526)].iloc[0]
    stage256 = width_capture[width_capture["variant"].eq(STAGE256)].iloc[0]
    material = material_products[material_products["candidate_materiality_pass"].eq(1)]
    best_selector = selector_summary.sort_values(
        ["diagnostic_pass", "avg_edge_vs_all_future60", "avg_selected_mean_future120"],
        ascending=[False, False, False],
    ).head(1)
    best_selector_pass = int(best_selector["diagnostic_pass"].iloc[0]) if not best_selector.empty else 0
    readiness_pass_count = int(readiness_gates["passed"].sum()) if "passed" in readiness_gates.columns else 0
    readiness_total = int(len(readiness_gates))
    progress = stage561_decision.get("current_progress", {})
    qualified_runs = int(progress.get("qualified_forward_runs", progress.get("forward_runs", 0)))
    qualified_dates = int(progress.get("qualified_forward_dates", progress.get("forward_dates", 0)))
    real_sentiment = int(progress.get("real_sentiment_news_ledger_count", progress.get("real_sentiment_ledgers", 0)))

    rows = [
        {
            "gate": "opportunity_exists_across_years",
            "description": "非核心每年是否至少存在可观的少数趋势机会",
            "actual": f"{int(annual_opportunity['opportunity_exists'].sum())}/{len(annual_opportunity)} years",
            "threshold": "all years top6 positive and >=3 winners",
            "passed": int(annual_opportunity["opportunity_exists"].sum() == len(annual_opportunity)),
        },
        {
            "gate": "material_low_corr_candidates_exist",
            "description": "是否存在多年正贡献、低相关、保证金可承受的候选品种",
            "actual": f"{len(material)} material products, avg_abs_corr={material['abs_core_daily_pnl_corr'].mean():.4f}",
            "threshold": ">=6 products and avg_abs_corr <=0.20",
            "passed": int(len(material) >= 6 and material["abs_core_daily_pnl_corr"].mean() <= 0.20),
        },
        {
            "gate": "plain_breadth_capture_material",
            "description": "全非核心宽池是否能真实捕获足够卫星收益",
            "actual": f"pnl={all_noncore['sleeve_total_pnl']:.0f}, return={all_noncore['sleeve_return_pct']:.2f}%",
            "threshold": "sleeve pnl >=50000 and return >=30%",
            "passed": int(all_noncore["sleeve_total_pnl"] >= 50000.0 and all_noncore["sleeve_return_pct"] >= 30.0),
        },
        {
            "gate": "plain_breadth_no_path_degrade",
            "description": "全非核心宽池是否不劣化主账户路径",
            "actual": f"dd {all_noncore['max_dd_pct']:.4f}% vs {stage526['max_dd_pct']:.4f}%, ulcer {all_noncore['ulcer_pct']:.4f} vs {stage526['ulcer_pct']:.4f}",
            "threshold": "max_dd >= Stage526 and ulcer <= Stage526",
            "passed": int(all_noncore["max_dd_pct"] >= stage526["max_dd_pct"] and all_noncore["ulcer_pct"] <= stage526["ulcer_pct"]),
        },
        {
            "gate": "simple_selector_beats_breadth",
            "description": "现有事前 selector 是否比全宽池更能抓到趋势",
            "actual": f"best diagnostic_pass={best_selector_pass}; prevpos pnl={width_capture[width_capture['variant'].eq(PREVPOS_R020)]['sleeve_total_pnl'].iloc[0]:.0f}",
            "threshold": "diagnostic_pass=1 and prev-year positive sleeve pnl > all breadth",
            "passed": int(best_selector_pass == 1 and width_capture[width_capture["variant"].eq(PREVPOS_R020)]["sleeve_total_pnl"].iloc[0] > all_noncore["sleeve_total_pnl"]),
        },
        {
            "gate": "forward_selector_data_ready",
            "description": "外生/舆情 forward 数据是否够做选品预测力审计",
            "actual": f"qualified_runs={qualified_runs}/20, dates={qualified_dates}/20, real_sentiment={real_sentiment}/1, readiness={readiness_pass_count}/{readiness_total}",
            "threshold": "20 qualified runs, 20 dates, >=1 real sentiment/news ledger",
            "passed": int(qualified_runs >= 20 and qualified_dates >= 20 and real_sentiment >= 1),
        },
        {
            "gate": "hindsight_top6_is_not_deployable",
            "description": "Stage256/Oracle风格固定少数强品种是否只能当上限，不直接部署",
            "actual": f"Stage256 satellite pnl={stage256['satellite_cumulative_pnl']:.0f}, uses historical winners",
            "threshold": "must have point-in-time selector before promotion",
            "passed": 0,
        },
    ]
    return pd.DataFrame(rows)


def write_chart(
    annual_opportunity: pd.DataFrame,
    material_products: pd.DataFrame,
    width_capture: pd.DataFrame,
    product_contribution: pd.DataFrame,
    gates: pd.DataFrame,
) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))

    ax = axes[0, 0]
    years = annual_opportunity["year"].astype(str)
    ax.bar(years, annual_opportunity["total_noncore_single_product_pnl"], label="all noncore single-product sum", color="#9ca3af")
    ax.bar(years, annual_opportunity["top6_pnl"], label="hindsight top6 sum", color="#2563eb")
    ax.axhline(0, color="#111827", linewidth=0.8)
    ax.set_title("Opportunity exists but is concentrated")
    ax.set_ylabel("PnL")
    ax2 = ax.twinx()
    ax2.plot(years, annual_opportunity["positive_count"], color="#f97316", marker="o", label="positive product count")
    ax2.set_ylabel("positive products")
    lines, labels = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines + lines2, labels + labels2, loc="upper left", fontsize=8)

    ax = axes[0, 1]
    labels = {
        STAGE526: "Stage526",
        STAGE256: "fixed top6",
        ALL_NONCORE: "all breadth",
        PREVPOS_R020: "prevpos r020",
        PREVPOS_R015: "prevpos r015",
    }
    rows = width_capture.copy()
    rows["short_label"] = rows["variant"].map(labels).fillna(rows["variant"])
    colors = ["#111827", "#7c3aed", "#0f766e", "#dc2626", "#f97316"]
    ax.bar(rows["short_label"], rows["satellite_cumulative_pnl"].fillna(0.0), color=colors[: len(rows)])
    ax.axhline(0, color="#111827", linewidth=0.8)
    ax.set_title("Actual sleeve capture is weak")
    ax.set_ylabel("satellite pnl")
    ax.tick_params(axis="x", labelrotation=25)
    axb = ax.twinx()
    axb.plot(rows["short_label"], rows["max_dd_pct"], color="#ef4444", marker="o", label="combined max DD")
    axb.set_ylabel("max DD %")

    ax = axes[1, 0]
    frame = material_products.copy()
    frame["is_material"] = frame["candidate_materiality_pass"].astype(int)
    ax.scatter(
        frame["abs_core_daily_pnl_corr"],
        frame["total_pnl"],
        c=np.where(frame["is_material"].eq(1), "#16a34a", "#9ca3af"),
        s=np.where(frame["is_material"].eq(1), 70, 30),
        alpha=0.85,
    )
    for _, row in frame[frame["is_material"].eq(1)].iterrows():
        ax.annotate(str(row["product_vt_symbol"]), (row["abs_core_daily_pnl_corr"], row["total_pnl"]), fontsize=8, xytext=(3, 3), textcoords="offset points")
    ax.axvline(0.30, color="#ef4444", linestyle="--", linewidth=1)
    ax.axhline(0, color="#111827", linewidth=0.8)
    ax.set_title("There are low-corr material products")
    ax.set_xlabel("|corr with Stage526 daily pnl|")
    ax.set_ylabel("single-product pnl")

    ax = axes[1, 1]
    top = product_contribution.head(8)
    bottom = product_contribution.tail(8).sort_values("satellite_product_net_pnl")
    contrib = pd.concat([top, bottom]).drop_duplicates("product_vt_symbol")
    colors = np.where(contrib["satellite_product_net_pnl"] >= 0, "#16a34a", "#dc2626")
    ax.barh(contrib["product_vt_symbol"], contrib["satellite_product_net_pnl"], color=colors)
    ax.axvline(0, color="#111827", linewidth=0.8)
    ax.set_title("Broad sleeve winners are offset by tail losses")
    ax.set_xlabel("all-breadth satellite pnl")

    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=160)
    plt.close(fig)


def write_report(summary: pd.DataFrame, gates: pd.DataFrame, width_capture: pd.DataFrame, annual_opportunity: pd.DataFrame) -> None:
    all_noncore = width_capture[width_capture["variant"].eq(ALL_NONCORE)].iloc[0]
    stage526 = width_capture[width_capture["variant"].eq(STAGE526)].iloc[0]
    text = f"""# Stage563 Breadth / Product Selection Thesis Audit

生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Decision

`breadth_thesis_valid_selector_not_ready_no_promotion`

## Key Takeaways

- 非核心品种里确实存在趋势机会：年度 hindsight top6 在 {int(annual_opportunity['opportunity_exists'].sum())}/{len(annual_opportunity)} 年为正，且 Stage241 找到 6 个低相关材料性候选。
- 但宽池本身不是 alpha：全非核心低单笔风险 sleeve 只贡献 {all_noncore['sleeve_total_pnl']:.0f}，收益 {all_noncore['sleeve_return_pct']:.2f}%，同时组合最大回撤 {all_noncore['max_dd_pct']:.4f}% 差于 Stage526 的 {stage526['max_dd_pct']:.4f}%。
- 简单选品特征不够：上一年为正宽池亏损，Stage543 selector 没有 diagnostic pass。
- 结论：方向保留，但不能晋级交易版本；下一步只允许做 point-in-time 外生/舆情 selector forward 账本，不继续扫宽池 risk/cap/corr/maxpos 小数。

## Gates

{gates.to_markdown(index=False)}

## Summary

{summary.to_markdown(index=False)}

## Outputs

- chart: `{CHART_PATH}`
- gates: `{GATE_PATH}`
- summary: `{SUMMARY_PATH}`
- annual opportunity: `{ANNUAL_OPPORTUNITY_PATH}`
"""
    REPORT_PATH.write_text(text, encoding="utf-8")


def main() -> None:
    annual = _read_csv(STAGE541_ANNUAL)
    product_summary = _read_csv(STAGE541_SUMMARY)
    stage557_summary = _read_csv(STAGE557_SUMMARY)
    standalone = _read_csv(STAGE557_STANDALONE)
    product = _read_csv(STAGE557_PRODUCT)
    family = _read_csv(STAGE557_FAMILY)
    selection = _read_csv(STAGE557_SELECTION)
    selector_summary = _read_csv(STAGE543_SELECTOR)
    readiness_gates = _read_csv(STAGE558_GATES)
    stage561_decision = _read_json(STAGE561_DECISION)

    annual_opportunity = build_annual_opportunity(annual)
    material_products = build_material_products(product_summary)
    width_capture = build_width_capture(stage557_summary, standalone, selection)
    product_contribution = build_product_contribution(product)
    family_contribution = build_family_contribution(family)
    gates = build_gates(
        annual_opportunity,
        material_products,
        width_capture,
        selector_summary,
        readiness_gates,
        stage561_decision,
    )

    opportunity_years = int(annual_opportunity["opportunity_exists"].sum())
    material_count = int(material_products["candidate_materiality_pass"].sum())
    all_noncore = width_capture[width_capture["variant"].eq(ALL_NONCORE)].iloc[0]
    prevpos = width_capture[width_capture["variant"].eq(PREVPOS_R020)].iloc[0]
    stage526 = width_capture[width_capture["variant"].eq(STAGE526)].iloc[0]
    pass_count = int(gates["passed"].sum())
    fail_count = int(len(gates) - pass_count)

    summary = pd.DataFrame(
        [
            {
                "metric": "opportunity_years",
                "value": opportunity_years,
                "note": "年度非核心 hindsight top6 为正且至少3个赢家的年份数",
            },
            {
                "metric": "material_low_corr_products",
                "value": material_count,
                "note": "Stage241 单品种材料性候选数",
            },
            {
                "metric": "all_breadth_sleeve_pnl",
                "value": float(all_noncore["sleeve_total_pnl"]),
                "note": "全非核心低单笔风险 sleeve 实盘口径捕获",
            },
            {
                "metric": "all_breadth_sleeve_return_pct",
                "value": float(all_noncore["sleeve_return_pct"]),
                "note": "全非核心低单笔风险 sleeve 收益率",
            },
            {
                "metric": "all_breadth_combined_dd_delta_pp",
                "value": float(all_noncore["max_dd_pct"] - stage526["max_dd_pct"]),
                "note": "相对 Stage526 的最大回撤变化，负数为劣化",
            },
            {
                "metric": "prev_year_positive_sleeve_pnl",
                "value": float(prevpos["sleeve_total_pnl"]),
                "note": "上一年为正宽池 sleeve PnL",
            },
            {
                "metric": "passed_gate_count",
                "value": pass_count,
                "note": "通过的结构闸门数",
            },
            {
                "metric": "failed_gate_count",
                "value": fail_count,
                "note": "失败的结构闸门数",
            },
        ]
    )

    annual_opportunity.to_csv(ANNUAL_OPPORTUNITY_PATH, index=False, encoding="utf-8-sig")
    material_products.to_csv(MATERIAL_PRODUCTS_PATH, index=False, encoding="utf-8-sig")
    width_capture.to_csv(WIDTH_CAPTURE_PATH, index=False, encoding="utf-8-sig")
    product_contribution.to_csv(PRODUCT_CONTRIBUTION_PATH, index=False, encoding="utf-8-sig")
    family_contribution.to_csv(FAMILY_CONTRIBUTION_PATH, index=False, encoding="utf-8-sig")
    gates.to_csv(GATE_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")

    write_chart(annual_opportunity, material_products, width_capture, product_contribution, gates)
    write_report(summary, gates, width_capture, annual_opportunity)

    decision = {
        "model_tag": MODEL_TAG,
        "decision": "breadth_thesis_valid_selector_not_ready_no_promotion",
        "line_id": "futures_trend_drawdown30_preserve_return",
        "opportunity_years": opportunity_years,
        "annual_year_count": int(len(annual_opportunity)),
        "material_low_corr_products": material_count,
        "all_breadth_sleeve_pnl": float(all_noncore["sleeve_total_pnl"]),
        "all_breadth_sleeve_return_pct": float(all_noncore["sleeve_return_pct"]),
        "all_breadth_combined_max_dd_pct": float(all_noncore["max_dd_pct"]),
        "stage526_combined_max_dd_pct": float(stage526["max_dd_pct"]),
        "prev_year_positive_sleeve_pnl": float(prevpos["sleeve_total_pnl"]),
        "passed_gate_count": pass_count,
        "failed_gate_count": fail_count,
        "gates": gates.to_dict(orient="records"),
        "outputs": {
            "annual_opportunity": str(ANNUAL_OPPORTUNITY_PATH),
            "material_products": str(MATERIAL_PRODUCTS_PATH),
            "width_capture": str(WIDTH_CAPTURE_PATH),
            "product_contribution": str(PRODUCT_CONTRIBUTION_PATH),
            "family_contribution": str(FAMILY_CONTRIBUTION_PATH),
            "gates": str(GATE_PATH),
            "summary": str(SUMMARY_PATH),
            "chart": str(CHART_PATH),
            "report": str(REPORT_PATH),
        },
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
