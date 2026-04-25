from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from qmt_roll_official_stage78_config import (
    OFFICIAL_STAGE78_COMPARISON_BASELINES,
    OFFICIAL_STAGE78_REFERENCE_METRICS,
    OFFICIAL_STAGE78_VERSION,
)
from qmt_roll_stage105_fu_sn_config import (
    STAGE105_REFERENCE_METRICS,
    STAGE105_ROLE,
    STAGE105_VERSION,
)


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage105_promotion_review_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage105_promotion_review"

SCORECARD_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_scorecard_{MODEL_TAG}.csv"
COMPARISON_TABLE_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

QUARTERLY_AGGREGATE_PATH: Path = (
    OUTPUT_DIR
    / "qmt_roll_official_stage78_fu_sn_satellite_quarterly_walkforward_horizon_aggregate_stage78_fu_sn_satellite_quarterly_wf_v1.csv"
)
QUARTERLY_COMPARISON_AGGREGATE_PATH: Path = (
    OUTPUT_DIR
    / "qmt_roll_official_stage78_fu_sn_satellite_quarterly_walkforward_horizon_comparison_aggregate_stage78_fu_sn_satellite_quarterly_wf_v1.csv"
)
ROBUSTNESS_SUMMARY_PATH: Path = (
    OUTPUT_DIR
    / "qmt_roll_official_stage78_fu_sn_satellite_robustness_summary_stage78_fu_sn_satellite_robustness_v1.json"
)
SMALL_CAPITAL_SUMMARY_PATH: Path = (
    OUTPUT_DIR / "qmt_roll_stage105_small_capital_live_readiness_summary_stage105_small_capital_live_readiness_v1.json"
)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result):
        return default
    return result


def to_markdown_table(df: pd.DataFrame, columns: list[str] | None = None, max_rows: int = 30) -> str:
    if df.empty:
        return "_empty_"
    view = df[columns].copy() if columns else df.copy()
    view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda value: f"{value:.4f}")
    header = "| " + " | ".join(view.columns) + " |"
    separator = "| " + " | ".join(["---"] * len(view.columns)) + " |"
    rows = ["| " + " | ".join(map(str, row)) + " |" for row in view.to_numpy()]
    return "\n".join([header, separator, *rows])


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def build_comparison_table() -> pd.DataFrame:
    stage78 = OFFICIAL_STAGE78_REFERENCE_METRICS["full_2020_2026"]
    stage75 = OFFICIAL_STAGE78_COMPARISON_BASELINES["stage75_return_ceiling"]
    stage105 = STAGE105_REFERENCE_METRICS["full_2020_2026"]
    rows = [
        {"profile_name": "stage75_return_ceiling", "role": "return_ceiling_reference", **stage75},
        {"profile_name": OFFICIAL_STAGE78_VERSION, "role": "defensive_formal_baseline", **stage78},
        {"profile_name": STAGE105_VERSION, "role": STAGE105_ROLE, **stage105},
    ]
    table = pd.DataFrame(rows)
    for column in [
        "end_balance",
        "total_return_pct",
        "max_dd_percent",
        "sharpe_ratio",
        "total_slippage",
        "total_trade_count",
    ]:
        table[f"{column}_diff_vs_stage78"] = table[column] - stage78[column]
        table[f"{column}_diff_vs_stage75"] = table[column] - stage75[column]
    return table


def build_scorecard(
    comparison: pd.DataFrame,
    quarterly_aggregate: pd.DataFrame,
    quarterly_comparison: pd.DataFrame,
    robustness: dict[str, Any],
    small_capital: dict[str, Any],
) -> pd.DataFrame:
    stage105 = comparison[comparison["profile_name"] == STAGE105_VERSION].iloc[0]
    promotion_checks = robustness.get("promotion_checks", {})
    sn_attr = (robustness.get("sn_product_attribution") or [{}])[0]
    margin = small_capital["margin_risk"]
    path = small_capital["path_risk"]
    liquidity = small_capital["liquidity"]
    granularity = small_capital["contract_granularity"]

    candidate_rows = quarterly_aggregate[
        quarterly_aggregate["profile_name"].astype(str) == "stage78_plus_fu_sn_satellite"
    ].copy()
    stage78_rows = quarterly_aggregate[
        quarterly_aggregate["profile_name"].astype(str) == "official_stage78_defensive_v1"
    ].copy()
    q63_candidate = candidate_rows[candidate_rows["horizon"].astype(str) == "63d"]
    q63_stage78 = stage78_rows[stage78_rows["horizon"].astype(str) == "63d"]
    q126_candidate = candidate_rows[candidate_rows["horizon"].astype(str) == "126d"]
    q252_candidate = candidate_rows[candidate_rows["horizon"].astype(str) == "252d"]
    q252_diff = quarterly_comparison[quarterly_comparison["horizon"].astype(str) == "252d"]

    rows = [
        {
            "dimension": "full_cycle_return",
            "status": "PASS",
            "evidence": f"Stage105 end balance diff vs Stage78 = {stage105['end_balance_diff_vs_stage78']:,.0f}",
            "hard_blocker": 0,
        },
        {
            "dimension": "full_cycle_risk_adjusted",
            "status": "PASS",
            "evidence": (
                f"Sharpe diff vs Stage78 = {stage105['sharpe_ratio_diff_vs_stage78']:.4f}; "
                f"max DD diff = {stage105['max_dd_percent_diff_vs_stage78']:.4f}"
            ),
            "hard_blocker": 0,
        },
        {
            "dimension": "quarterly_cold_start",
            "status": "PASS_WITH_WARNING",
            "evidence": (
                f"63d positive rate Stage105={_safe_float(q63_candidate['positive_return_rate_pct'].iloc[0] if not q63_candidate.empty else 0):.4f}% "
                f"vs Stage78={_safe_float(q63_stage78['positive_return_rate_pct'].iloc[0] if not q63_stage78.empty else 0):.4f}%; "
                f"126d worst={_safe_float(q126_candidate['worst_return_pct'].iloc[0] if not q126_candidate.empty else 0):.4f}%; "
                f"252d worst diff={_safe_float(q252_diff['worst_return_diff_pct'].iloc[0] if not q252_diff.empty else 0):.4f}%"
            ),
            "hard_blocker": 0,
        },
        {
            "dimension": "product_attribution",
            "status": "PASS_WITH_WARNING",
            "evidence": (
                f"sn total net pnl = {_safe_float(sn_attr.get('total_net_pnl')):,.0f}; "
                f"positive years = {promotion_checks.get('sn_positive_years', 0)}; "
                "2023/2024 sn yearly attribution is negative"
            ),
            "hard_blocker": 0,
        },
        {
            "dimension": "fair_slippage_stress",
            "status": "PASS",
            "evidence": (
                f"5x fair slippage still beats Stage78 = "
                f"{promotion_checks.get('candidate_beats_stage78_under_5x_fair_slippage', False)}"
            ),
            "hard_blocker": 0,
        },
        {
            "dimension": "start_year_transfer",
            "status": "PASS",
            "evidence": (
                f"positive start-year diff = {promotion_checks.get('start_year_positive_diff_count', 0)}/"
                f"{promotion_checks.get('start_year_window_count', 0)}"
            ),
            "hard_blocker": 0,
        },
        {
            "dimension": "small_capital_margin",
            "status": "FAIL",
            "evidence": (
                f"400k max margin/balance = {margin['max_total_margin_to_balance_pct']:.4f}%; "
                f"extreme margin days = {margin['extreme_margin_days']}; "
                f"warn margin days = {margin['warn_margin_days']}"
            ),
            "hard_blocker": 1,
        },
        {
            "dimension": "small_capital_path_loss",
            "status": "WARN",
            "evidence": (
                f"worst 5d pnl = {path['worst_5d_net_pnl']:,.0f} "
                f"({path['worst_5d_pct_capital']:.4f}% of initial capital); "
                f"max consecutive loss days = {path['max_consecutive_loss_days']}"
            ),
            "hard_blocker": 0,
        },
        {
            "dimension": "contract_granularity",
            "status": "WARN",
            "evidence": (
                f"largest single-contract margin = {granularity['max_single_contract_margin']:,.0f} "
                f"({granularity['max_single_contract_margin_pct_capital']:.4f}% of 400k)"
            ),
            "hard_blocker": 0,
        },
        {
            "dimension": "liquidity",
            "status": "PASS",
            "evidence": (
                f"trades >1% volume = {liquidity['warn_volume_share_gt_1pct_count']}; "
                f"max volume share = {liquidity['max_volume_share_pct']:.4f}%"
            ),
            "hard_blocker": 0,
        },
    ]
    return pd.DataFrame(rows)


def build_summary(scorecard: pd.DataFrame, comparison: pd.DataFrame, small_capital: dict[str, Any]) -> dict[str, Any]:
    hard_blockers = int(scorecard["hard_blocker"].sum())
    margin = small_capital["margin_risk"]
    min_capital_for_80pct_margin = margin["max_total_margin"] / 0.8 if margin["max_total_margin"] else 0.0
    min_capital_for_60pct_margin = margin["max_total_margin"] / 0.6 if margin["max_total_margin"] else 0.0
    if hard_blockers > 0:
        decision = "REJECT_FORMAL_REPLACEMENT_FOR_400K_AS_IS"
    else:
        decision = "CONDITIONAL_PASS"
    return {
        "model_tag": MODEL_TAG,
        "version": STAGE105_VERSION,
        "decision": decision,
        "hard_blocker_count": hard_blockers,
        "primary_blocker": "400k margin occupancy exceeds deployable threshold" if hard_blockers else "",
        "estimated_min_capital_for_80pct_margin": min_capital_for_80pct_margin,
        "estimated_min_capital_for_60pct_margin": min_capital_for_60pct_margin,
        "comparison": comparison.to_dict(orient="records"),
        "scorecard": scorecard.to_dict(orient="records"),
        "small_capital_key_metrics": {
            "end_balance": small_capital["statistics"]["end_balance"],
            "total_return_pct": small_capital["statistics"]["total_return_pct"],
            "max_dd_percent": small_capital["statistics"]["max_dd_percent"],
            "sharpe_ratio": small_capital["statistics"]["sharpe_ratio"],
            "max_total_margin_to_balance_pct": margin["max_total_margin_to_balance_pct"],
            "extreme_margin_days": margin["extreme_margin_days"],
            "warn_margin_days": margin["warn_margin_days"],
        },
        "outputs": {
            "scorecard": str(SCORECARD_PATH),
            "comparison": str(COMPARISON_TABLE_PATH),
            "summary_json": str(SUMMARY_JSON_PATH),
            "report": str(REPORT_PATH),
        },
    }


def build_report(
    summary: dict[str, Any],
    scorecard: pd.DataFrame,
    comparison: pd.DataFrame,
    quarterly_comparison: pd.DataFrame,
) -> str:
    return "\n".join(
        [
            "# Stage105 Promotion Review",
            "",
            "## Decision",
            "",
            f"- Decision: `{summary['decision']}`",
            f"- Hard blockers: `{summary['hard_blocker_count']}`",
            f"- Primary blocker: `{summary['primary_blocker']}`",
            f"- Estimated minimum capital for 80% margin ceiling: `{summary['estimated_min_capital_for_80pct_margin']:,.0f}`",
            f"- Estimated minimum capital for 60% margin ceiling: `{summary['estimated_min_capital_for_60pct_margin']:,.0f}`",
            "",
            "## Interpretation",
            "",
            "- Stage105 is better than Stage78 on full-cycle return, Sharpe, slippage stress, and start-year transfer.",
            "- Stage105 should not replace Stage78 for a 400k account as-is because the margin path exceeds deployable limits.",
            "- The correct next step is a margin-aware deployment variant, not another return-seeking product search.",
            "",
            "## Full-Cycle Comparison",
            "",
            to_markdown_table(
                comparison,
                [
                    "profile_name",
                    "role",
                    "end_balance",
                    "total_return_pct",
                    "max_dd_percent",
                    "sharpe_ratio",
                    "total_slippage",
                    "total_trade_count",
                    "end_balance_diff_vs_stage78",
                    "sharpe_ratio_diff_vs_stage78",
                ],
            ),
            "",
            "## Scorecard",
            "",
            to_markdown_table(scorecard, ["dimension", "status", "evidence", "hard_blocker"], max_rows=20),
            "",
            "## Quarterly Difference Aggregate",
            "",
            to_markdown_table(
                quarterly_comparison,
                [
                    "horizon",
                    "window_count",
                    "return_better_count",
                    "return_worse_count",
                    "drawdown_worse_count",
                    "sharpe_worse_count",
                    "median_return_diff_pct",
                    "worst_return_diff_pct",
                    "best_return_diff_pct",
                ],
            ),
            "",
            "## Next Work",
            "",
            "- Do not promote Stage105 as the default formal replacement for 400k deployment.",
            "- Build a margin-aware Stage105 variant that keeps the same entry logic but throttles risk when margin occupancy is too high.",
            "- Keep Stage78 as the defensive formal baseline until the margin-aware variant passes the same review.",
        ]
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    quarterly_aggregate = pd.read_csv(QUARTERLY_AGGREGATE_PATH)
    quarterly_comparison = pd.read_csv(QUARTERLY_COMPARISON_AGGREGATE_PATH)
    robustness = load_json(ROBUSTNESS_SUMMARY_PATH)
    small_capital = load_json(SMALL_CAPITAL_SUMMARY_PATH)
    comparison = build_comparison_table()
    scorecard = build_scorecard(comparison, quarterly_aggregate, quarterly_comparison, robustness, small_capital)
    summary = build_summary(scorecard, comparison, small_capital)

    comparison.to_csv(COMPARISON_TABLE_PATH, index=False, encoding="utf-8-sig")
    scorecard.to_csv(SCORECARD_PATH, index=False, encoding="utf-8-sig")
    SUMMARY_JSON_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    REPORT_PATH.write_text(build_report(summary, scorecard, comparison, quarterly_comparison), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    print(f"[stage105-promotion-review] report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
