from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


OUTPUT_DIR = Path(__file__).resolve().parent / "backtest_outputs"
MODEL_TAG = "stage642_low_single_risk_expanded_pool_decision_board_v1"
OUTPUT_PREFIX = "qmt_roll_stage642_low_single_risk_expanded_pool_decision_board"

STAGE638_ANNUAL = OUTPUT_DIR / (
    "qmt_roll_stage638_annual_independent_trend_slot_audit_annual_slot_opportunity_"
    "stage638_annual_independent_trend_slot_audit_v1.csv"
)
STAGE638_PRODUCT = OUTPUT_DIR / (
    "qmt_roll_stage638_annual_independent_trend_slot_audit_product_ladder_"
    "stage638_annual_independent_trend_slot_audit_v1.csv"
)
STAGE639_FAMILY = OUTPUT_DIR / (
    "qmt_roll_stage639_economic_driver_source_gap_board_family_driver_board_"
    "stage639_economic_driver_source_gap_board_v1.csv"
)
STAGE563_SUMMARY = OUTPUT_DIR / (
    "qmt_roll_stage563_breadth_pool_product_selection_thesis_audit_summary_"
    "stage563_breadth_pool_product_selection_thesis_audit_v1.csv"
)

CURRENT_EFFECTIVE_SLOTS = 4
TARGET_EFFECTIVE_SLOTS = 7
MATERIAL_BREADTH_PNL_THRESHOLD = 50_000

REFERENCE_LINKS = [
    "https://www.aqr.com/Insights/Research/Journal-Article/You-Cant-Always-Trend-When-You-Want",
    "https://www.man.com/insights/trend-following-optimal-market-mix",
    "https://www.aspectcapital.com/insight/diversification-trend-following/",
    "https://github.com/chrism2671/PyTrendFollow",
    "https://github.com/PyPortfolio/PyPortfolioOpt",
]


def _now_cst() -> str:
    return datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S CST")


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig")


def _num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _metric(summary: pd.DataFrame, name: str, default: float = np.nan) -> float:
    rows = summary.loc[summary["metric"].eq(name), "value"]
    if rows.empty:
        return default
    return float(rows.iloc[0])


def build_decision_board() -> dict[str, pd.DataFrame | dict]:
    annual = _read_csv(STAGE638_ANNUAL)
    product = _read_csv(STAGE638_PRODUCT)
    family = _read_csv(STAGE639_FAMILY)
    breadth_summary = _read_csv(STAGE563_SUMMARY)

    annual["top6_pnl"] = _num(annual["top6_pnl"])
    annual["top6_family_count"] = _num(annual["top6_family_count"])
    annual["top1_share_of_top6_pct"] = _num(annual["top1_share_of_top6_pct"])
    annual["top6_deployable_products"] = _num(annual["top6_deployable_products"])
    annual["annual_opportunity_exists"] = _num(annual["annual_opportunity_exists"])
    annual["annual_independent_family_pass"] = _num(annual["annual_independent_family_pass"])

    product["total_pnl"] = _num(product["total_pnl"])
    product["max_abs_corr_to_p0"] = _num(product["max_abs_corr_to_p0"])
    product["tail_abs_corr_to_p0_composite"] = _num(product["tail_abs_corr_to_p0_composite"])
    product["candidate_materiality_pass"] = _num(product["candidate_materiality_pass"])
    product["watch_corr_pass"] = _num(product["watch_corr_pass"])
    product["deployable_new_slot_now"] = _num(product["deployable_new_slot_now"])

    family["annual_top6_pnl_sum"] = _num(family["annual_top6_pnl_sum"])
    family["annual_top6_hits"] = _num(family["annual_top6_hits"])
    family["active_fetch_validated_rows"] = _num(family["active_fetch_validated_rows"])
    family["official_source_candidate_rows"] = _num(family["official_source_candidate_rows"])
    family["candidate_source_rows"] = _num(family["candidate_source_rows"])
    family["avg_max_abs_corr_to_p0"] = _num(family["avg_max_abs_corr_to_p0"])
    family["high_corr_reject_hits"] = _num(family["high_corr_reject_hits"])

    all_breadth_pnl = _metric(breadth_summary, "all_breadth_sleeve_pnl")
    all_breadth_return = _metric(breadth_summary, "all_breadth_sleeve_return_pct")
    combined_dd_delta = _metric(breadth_summary, "all_breadth_combined_dd_delta_pp")
    prev_year_positive_pnl = _metric(breadth_summary, "prev_year_positive_sleeve_pnl")

    years = int(annual["year"].nunique())
    opportunity_years = int(annual["annual_opportunity_exists"].sum())
    independent_family_years = int(annual["annual_independent_family_pass"].sum())
    top1_not_concentrated_years = int(annual["top1_share_of_top6_pct"].le(50).sum())
    deployable_top6_years = int(annual["top6_deployable_products"].gt(0).sum())

    # Stage563 uses the broader "material low-corr clue" definition. Stage638
    # deliberately tightens deployable/watch gates to zero, so keep these
    # concepts separate.
    material_low_corr_products = int(_metric(breadth_summary, "material_low_corr_products", 0))
    deployable_new_products = int(product["deployable_new_slot_now"].eq(1).sum())
    active_fetch_families = int(family["active_fetch_validated_rows"].gt(0).sum())
    high_corr_hit_families = int(family["high_corr_reject_hits"].gt(0).sum())

    gates = pd.DataFrame(
        [
            {
                "gate": "annual_opportunity_exists",
                "passed": int(opportunity_years == years),
                "current": f"{opportunity_years}/{years}",
                "required": "all years",
                "note": "非核心年度 oracle top6 每年都有正趋势机会。",
            },
            {
                "gate": "opportunity_not_single_family_only",
                "passed": int(independent_family_years >= max(1, years - 1)),
                "current": f"{independent_family_years}/{years}",
                "required": f">={max(1, years - 1)}/{years}",
                "note": "年度机会通常跨多个产品族，方向不是伪命题。",
            },
            {
                "gate": "single_winner_concentration_control",
                "passed": int(top1_not_concentrated_years >= max(1, years - 1)),
                "current": f"{top1_not_concentrated_years}/{years}",
                "required": f">={max(1, years - 1)}/{years}",
                "note": "多数年份 top1 不应吃掉 top6 过半；2026 仍提示强集中风险。",
            },
            {
                "gate": "plain_breadth_capture_material",
                "passed": int(all_breadth_pnl >= MATERIAL_BREADTH_PNL_THRESHOLD),
                "current": f"pnl={all_breadth_pnl:.0f},ret={all_breadth_return:.2f}%",
                "required": f"pnl>={MATERIAL_BREADTH_PNL_THRESHOLD}",
                "note": "简单低单笔宽池没有捕获足够收益。",
            },
            {
                "gate": "plain_breadth_no_path_degrade",
                "passed": int(combined_dd_delta >= 0),
                "current": f"dd_delta={combined_dd_delta:.4f}pp",
                "required": ">=0 vs Stage526",
                "note": "简单宽池相对 Stage526 最大回撤略劣化。",
            },
            {
                "gate": "prev_year_positive_selector_not_enough",
                "passed": int(prev_year_positive_pnl > 0),
                "current": f"pnl={prev_year_positive_pnl:.0f}",
                "required": ">0",
                "note": "上一年赢家延续在 Stage563 为负，不能当选品器。",
            },
            {
                "gate": "material_low_corr_candidates_exist",
                "passed": int(material_low_corr_products > 0),
                "current": str(material_low_corr_products),
                "required": ">0 monitor candidates",
                "note": "低相关材料性线索存在，但不等于可交易槽。",
            },
            {
                "gate": "target_effective_slots_met",
                "passed": int(CURRENT_EFFECTIVE_SLOTS >= TARGET_EFFECTIVE_SLOTS),
                "current": f"{CURRENT_EFFECTIVE_SLOTS}/{TARGET_EFFECTIVE_SLOTS}",
                "required": f">={TARGET_EFFECTIVE_SLOTS}",
                "note": "当前有效独立风险槽不足，单槽风险不能实际降到目标。",
            },
            {
                "gate": "deployable_new_slots_ready",
                "passed": int(deployable_new_products > 0 or deployable_top6_years > 0),
                "current": f"products={deployable_new_products},years={deployable_top6_years}/{years}",
                "required": ">0",
                "note": "没有新增 deployable selector slot。",
            },
            {
                "gate": "active_source_ready_for_new_families",
                "passed": int(active_fetch_families > 0),
                "current": f"{active_fetch_families}/{len(family)}",
                "required": ">0 families",
                "note": "年度赢家家族 source 候选存在，但 active fetch/PIT 仍未闭合。",
            },
            {
                "gate": "high_corr_risk_identified_and_rejected",
                "passed": int(high_corr_hit_families > 0),
                "current": f"{high_corr_hit_families}/{len(family)}",
                "required": ">0 rejected families",
                "note": "高相关重复风险已被识别，说明不能机械扩池。",
            },
            {
                "gate": "paper_and_whitelist_remain_zero",
                "passed": 1,
                "current": "0/0",
                "required": "0/0",
                "note": "本阶段只做决策板，不产生 paper 或交易白名单。",
            },
        ]
    )

    family_action = family.copy()
    action_map = {
        "energy_oil": "trend rich but high corr; require independent source/selector proof before any risk slot.",
        "base_metals": "official source valuable but public current route blocked; authorized/downloadable route first.",
        "grains_oilseeds": "mostly existing P0 or same-family depth; use as tie-break depth, not a new slot.",
        "petrochem": "trend rich but mostly P0/high-corr/data-gap; source and independence proof first.",
    }
    family_action["next_action"] = family_action["product_family"].map(action_map).fillna(
        "keep source/PIT/TCA monitor only."
    )

    product_focus = product.sort_values(
        ["ladder_bucket", "total_pnl", "max_abs_corr_to_p0"],
        ascending=[True, False, True],
    )[
        [
            "product_vt_symbol",
            "product_family",
            "ladder_bucket",
            "structural_bucket",
            "total_pnl",
            "max_abs_corr_to_p0",
            "tail_abs_corr_to_p0_composite",
            "watch_corr_pass",
            "deployable_new_slot_now",
        ]
    ].head(20)

    decision = {
        "generated_at_cst": _now_cst(),
        "decision": "low_single_risk_expand_pool_thesis_valid_selector_source_not_ready",
        "model_tag": MODEL_TAG,
        "current_effective_slots": CURRENT_EFFECTIVE_SLOTS,
        "target_effective_slots": TARGET_EFFECTIVE_SLOTS,
        "annual_opportunity_years": opportunity_years,
        "annual_years": years,
        "independent_family_years": independent_family_years,
        "plain_breadth_sleeve_pnl": all_breadth_pnl,
        "plain_breadth_sleeve_return_pct": all_breadth_return,
        "prev_year_positive_sleeve_pnl": prev_year_positive_pnl,
        "material_low_corr_products": material_low_corr_products,
        "deployable_new_products": deployable_new_products,
        "active_fetch_families": active_fetch_families,
        "high_corr_hit_families": high_corr_hit_families,
        "hard_gates_passed": int(gates["passed"].sum()),
        "hard_gates_total": int(len(gates)),
        "promotion_allowed": False,
        "paper_allowed_now": False,
        "trading_whitelist_allowed_now": False,
        "external_research_refs": REFERENCE_LINKS,
    }

    return {
        "annual": annual,
        "product": product,
        "family_action": family_action,
        "product_focus": product_focus,
        "gates": gates,
        "decision": decision,
    }


def write_outputs(board: dict[str, pd.DataFrame | dict]) -> dict[str, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    annual = board["annual"]
    product = board["product"]
    family_action = board["family_action"]
    product_focus = board["product_focus"]
    gates = board["gates"]
    decision = board["decision"]

    paths = {
        "annual_board": OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_board_{MODEL_TAG}.csv",
        "family_action": OUTPUT_DIR / f"{OUTPUT_PREFIX}_family_action_{MODEL_TAG}.csv",
        "product_focus": OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_focus_{MODEL_TAG}.csv",
        "gates": OUTPUT_DIR / f"{OUTPUT_PREFIX}_gates_{MODEL_TAG}.csv",
        "decision": OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json",
        "report": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md",
        "chart": OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png",
    }

    annual.to_csv(paths["annual_board"], index=False, encoding="utf-8-sig")
    family_action.to_csv(paths["family_action"], index=False, encoding="utf-8-sig")
    product_focus.to_csv(paths["product_focus"], index=False, encoding="utf-8-sig")
    gates.to_csv(paths["gates"], index=False, encoding="utf-8-sig")
    paths["decision"].write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")

    write_chart(
        annual=annual,
        product=product,
        family_action=family_action,
        gates=gates,
        chart_path=paths["chart"],
    )
    write_report(
        annual=annual,
        family_action=family_action,
        product_focus=product_focus,
        gates=gates,
        decision=decision,
        report_path=paths["report"],
        chart_path=paths["chart"],
    )
    return paths


def write_chart(
    annual: pd.DataFrame,
    product: pd.DataFrame,
    family_action: pd.DataFrame,
    gates: pd.DataFrame,
    chart_path: Path,
) -> None:
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, axes = plt.subplots(2, 2, figsize=(16, 11))
    fig.suptitle(
        "Stage642 low single-risk expanded pool decision board",
        fontsize=16,
        fontweight="bold",
    )

    ax = axes[0, 0]
    years = annual["year"].astype(str)
    ax.bar(years, annual["top6_pnl"], color="#2b6cb0", alpha=0.85, label="oracle top6 pnl")
    ax2 = ax.twinx()
    ax2.plot(years, annual["top6_family_count"], color="#dd6b20", marker="o", linewidth=2, label="family count")
    ax2.plot(years, annual["top1_share_of_top6_pct"], color="#805ad5", marker="s", linewidth=1.5, label="top1 share %")
    ax.set_title("Annual opportunity exists, but 2026 concentration risk is visible")
    ax.set_ylabel("top6 PnL")
    ax2.set_ylabel("families / top1 share")
    ax.legend(loc="upper left")
    ax2.legend(loc="upper right")

    ax = axes[0, 1]
    bucket_counts = product["ladder_bucket"].value_counts().sort_values()
    colors = ["#718096" if "reject" in idx else "#dd6b20" if "material" in idx else "#38a169" for idx in bucket_counts.index]
    ax.barh(bucket_counts.index, bucket_counts.values, color=colors)
    ax.set_title("Product ladder: material is not the same as deployable")
    ax.set_xlabel("product count")
    for i, value in enumerate(bucket_counts.values):
        ax.text(value + 0.2, i, str(value), va="center", fontsize=9)

    ax = axes[1, 0]
    family_action = family_action.sort_values("annual_top6_pnl_sum", ascending=False)
    sc = ax.scatter(
        family_action["avg_max_abs_corr_to_p0"],
        family_action["annual_top6_pnl_sum"],
        s=80 + 30 * family_action["official_source_candidate_rows"],
        c=family_action["active_fetch_validated_rows"],
        cmap="RdYlGn",
        vmin=0,
        vmax=max(1, int(family_action["active_fetch_validated_rows"].max())),
        edgecolor="#2d3748",
        linewidth=0.8,
    )
    for _, row in family_action.iterrows():
        ax.annotate(
            str(row["product_family"]),
            (float(row["avg_max_abs_corr_to_p0"]), float(row["annual_top6_pnl_sum"])),
            xytext=(5, 5),
            textcoords="offset points",
            fontsize=9,
        )
    ax.axvline(0.15, color="#e53e3e", linestyle="--", linewidth=1.2, label="corr watch 0.15")
    ax.set_title("Opportunity clusters are still correlated/source-incomplete")
    ax.set_xlabel("avg max abs corr to P0")
    ax.set_ylabel("annual top6 PnL sum")
    ax.legend(loc="best")
    fig.colorbar(sc, ax=ax, label="active fetch rows")

    ax = axes[1, 1]
    gate_values = gates[["passed"]].to_numpy(dtype=float).T
    ax.imshow(gate_values, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
    ax.set_yticks([0])
    ax.set_yticklabels(["pass"])
    ax.set_xticks(range(len(gates)))
    ax.set_xticklabels(gates["gate"], rotation=65, ha="right", fontsize=8)
    ax.set_title("Hard gates: thesis valid, implementation not ready")
    for col, passed in enumerate(gates["passed"].astype(int)):
        ax.text(col, 0, str(passed), ha="center", va="center", color="#1a202c", fontsize=9, fontweight="bold")

    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(chart_path, dpi=170)
    plt.close(fig)


def write_report(
    annual: pd.DataFrame,
    family_action: pd.DataFrame,
    product_focus: pd.DataFrame,
    gates: pd.DataFrame,
    decision: dict,
    report_path: Path,
    chart_path: Path,
) -> None:
    gate_pass = f"{decision['hard_gates_passed']}/{decision['hard_gates_total']}"
    family_cols = [
        "product_family",
        "annual_top6_years_present",
        "annual_top6_pnl_sum",
        "high_corr_reject_hits",
        "official_source_candidate_rows",
        "active_fetch_validated_rows",
        "avg_max_abs_corr_to_p0",
        "next_action",
    ]
    product_cols = [
        "product_vt_symbol",
        "product_family",
        "ladder_bucket",
        "structural_bucket",
        "total_pnl",
        "max_abs_corr_to_p0",
        "watch_corr_pass",
        "deployable_new_slot_now",
    ]
    report = f"""# Stage642 Low Single-Risk Expanded Pool Decision Board

- generated_at_cst: `{decision['generated_at_cst']}`
- decision: `{decision['decision']}`
- stage nature: answer whether lower single-trade risk + broader pool + correlation control can be a valid next structure.

## External Research Judgement

Managed futures / trend-following literature supports broad market diversification, but the useful diversification unit is an independent risk source, not the number of tickers. Mature implementations combine volatility sizing, instrument correlations, diversification multipliers, and liquidity limits. GitHub implementations such as PyTrendFollow and PyPortfolioOpt also point to the same engineering split: signal generation is separate from portfolio construction and correlation/risk allocation.

References:
{chr(10).join(f"- {link}" for link in REFERENCE_LINKS)}

## Key Numbers

- annual opportunity years: `{decision['annual_opportunity_years']}/{decision['annual_years']}`
- independent family years: `{decision['independent_family_years']}/{decision['annual_years']}`
- current / target effective slots: `{decision['current_effective_slots']}/{decision['target_effective_slots']}`
- plain breadth sleeve pnl: `{decision['plain_breadth_sleeve_pnl']:.0f}`
- plain breadth sleeve return: `{decision['plain_breadth_sleeve_return_pct']:.4f}%`
- prev-year-positive sleeve pnl: `{decision['prev_year_positive_sleeve_pnl']:.0f}`
- material low-corr products: `{decision['material_low_corr_products']}`
- deployable new products: `{decision['deployable_new_products']}`
- active fetch families: `{decision['active_fetch_families']}`
- hard gates: `{gate_pass}`

## Family Action Board

{family_action[family_cols].to_markdown(index=False)}

## Product Focus

{product_focus[product_cols].to_markdown(index=False)}

## Gates

{gates.to_markdown(index=False)}

## Interpretation

- 用户提出的结构方向成立：年度趋势机会在 `7/7` 年存在，而且多数年份不是单一家族独占。
- 但直接扩大品种池没有通过：Stage563 的全非核心低单笔 sleeve 只捕获 `9395` PnL，且最大回撤/Ulcer 相对 Stage526 略劣化。
- “上一年赚钱就选”也不能用：prev-year-positive sleeve PnL 为 `{decision['prev_year_positive_sleeve_pnl']:.0f}`。
- 当前最关键的缺口是 source/PIT/TCA/selector，而不是继续调单笔风险小数。有效目标仍是把可执行独立风险槽从 `4` 推到 `7`，但现在新增 deployable slot 仍为 `0`。

## Chart

- chart: `{chart_path}`
"""
    report_path.write_text(report, encoding="utf-8")


def main() -> None:
    board = build_decision_board()
    paths = write_outputs(board)
    decision = board["decision"]
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    print("outputs:")
    for key, value in paths.items():
        print(f"- {key}: {value}")


if __name__ == "__main__":
    main()
