from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

import analyze_qmt_roll_stage696_stage407_soft_streak_risk as s696
from qmt_roll_official_live_config import OFFICIAL_LIVE_AI_ELIGIBILITY_PATH
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy


MODEL_TAG = "stage701_stage407_drawdown_gated_streak_v1"
OUTPUT_PREFIX = "qmt_roll_stage701_stage407_drawdown_gated_streak"
OFFICIAL_DD_GATE_VARIANT = "stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4_drawdown_gated_streak15"
TARGET_VARIANT = (
    "stage526_200k_force95_to80_recovery_sleeve_r080_pc25_original_ai_plus_jd_ai_rerank_top9_"
    "maxpos5_drawdown_gated_streak15"
)
AI_STRATEGY = "stage701_original_ai_pool_plus_jd_probability_rerank_top9_entry_filter"
AI_SCORE_TYPE = "stage701_original_ai_pool_plus_jd_probability_rerank_top9"
AI_PRE_COVERAGE_SCORE_TYPE = "stage701_official_ai_pre_full_market_coverage"
STREAK_SEVERE_DD_GATE_RATIO = 0.15

_ORIGINAL_CURRENT_STREAK_MULTIPLIER = QmtRollPortfolioStrategy._current_streak_multiplier
_BASE_RUN_VARIANT = s696._run_variant_with_diagnostics
_BASE_DECISION = s696._decision


def _reconfigure_paths() -> None:
    s696.MODEL_TAG = MODEL_TAG
    s696.OUTPUT_PREFIX = OUTPUT_PREFIX
    s696.OFFICIAL_SOFT_VARIANT = OFFICIAL_DD_GATE_VARIANT
    s696.TARGET_VARIANT = TARGET_VARIANT
    s696.AI_STRATEGY = AI_STRATEGY
    s696.AI_SCORE_TYPE = AI_SCORE_TYPE
    s696.AI_PRE_COVERAGE_SCORE_TYPE = AI_PRE_COVERAGE_SCORE_TYPE
    s696.SOFT_STREAK_MULTIPLIERS = s696.BASE_STREAK_MULTIPLIERS

    s696.GENERATED_DIR = s696.OUTPUT_DIR / "stage701_generated_inputs"
    s696.UNIVERSE_PLUS_JD_PATH = s696.GENERATED_DIR / f"{OUTPUT_PREFIX}_plus_jd_universe_{MODEL_TAG}.csv"
    s696.ELIGIBILITY_PATH = (
        s696.GENERATED_DIR / f"{OUTPUT_PREFIX}_original_ai_plus_jd_rerank_top9_eligibility_{MODEL_TAG}.csv"
    )
    s696.MISSING_PREDICTION_PATH = (
        s696.GENERATED_DIR / f"{OUTPUT_PREFIX}_missing_prediction_candidates_{MODEL_TAG}.csv"
    )

    s696.SUMMARY_PATH = s696.OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
    s696.COST_PATH = s696.OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
    s696.COMPARISON_PATH = s696.OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
    s696.ANNUAL_PATH = s696.OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_{MODEL_TAG}.csv"
    s696.MONTHLY_PATH = s696.OUTPUT_DIR / f"{OUTPUT_PREFIX}_monthly_{MODEL_TAG}.csv"
    s696.DAILY_PATH = s696.OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
    s696.POSITIONS_PATH = s696.OUTPUT_DIR / f"{OUTPUT_PREFIX}_positions_{MODEL_TAG}.csv"
    s696.PRODUCT_PATH = s696.OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_{MODEL_TAG}.csv"
    s696.PRODUCT_DELTA_PATH = s696.OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_delta_{MODEL_TAG}.csv"
    s696.PRODUCT_MARGIN_PATH = s696.OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_margin_{MODEL_TAG}.csv"
    s696.TRADE_USAGE_PATH = s696.OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_usage_{MODEL_TAG}.csv"
    s696.ENTRY_CANDIDATES_PATH = s696.OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_candidates_{MODEL_TAG}.csv"
    s696.ENTRY_RISK_PATH = s696.OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_risk_{MODEL_TAG}.csv"
    s696.ENTRY_RISK_SUMMARY_PATH = s696.OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_risk_summary_{MODEL_TAG}.csv"
    s696.WINDOW_GROWTH_PATH = s696.OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_growth_{MODEL_TAG}.csv"
    s696.WINDOW_PRODUCT_PATH = s696.OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_product_{MODEL_TAG}.csv"
    s696.FORCED_EVENTS_PATH = s696.OUTPUT_DIR / f"{OUTPUT_PREFIX}_forced_events_{MODEL_TAG}.csv"
    s696.FORCED_SUMMARY_PATH = s696.OUTPUT_DIR / f"{OUTPUT_PREFIX}_forced_summary_{MODEL_TAG}.csv"
    s696.AI_AUDIT_PATH = s696.OUTPUT_DIR / f"{OUTPUT_PREFIX}_ai_audit_{MODEL_TAG}.csv"
    s696.REPORT_PATH = s696.OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
    s696.DECISION_PATH = s696.OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
    s696.CHART_PATH = s696.OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"
    s696.EQUITY_CHART_PATH = s696.OUTPUT_DIR / f"{OUTPUT_PREFIX}_equity_only_{MODEL_TAG}.png"


def _official_dd_gate_spec(identity_map: str) -> s696.s692.s653.ForcedVariant:
    base = s696._official_spec(identity_map)
    capital = replace(
        base.capital,
        variant=OFFICIAL_DD_GATE_VARIANT,
        label="Stage414 official drawdown-gated streak 15pct",
        note=(
            "Official Stage372 unchanged except the severe 0.1 loss-streak floor is active only when "
            "portfolio drawdown is above 15%."
        ),
    )
    overrides = {
        **base.overrides,
        "ai_product_pool_eligibility_path": str(OFFICIAL_LIVE_AI_ELIGIBILITY_PATH),
        "streak_risk_multipliers": s696.BASE_STREAK_MULTIPLIERS,
    }
    return replace(base, capital=capital, overrides=overrides, profile="official_stage372_drawdown_gated_streak15")


def _stage407_spec(identity_map: str, *, soft_streak: bool) -> s696.s692.s653.ForcedVariant:
    base = s696._official_spec(identity_map)
    variant = TARGET_VARIANT if soft_streak else s696.STAGE407_VARIANT
    label = "Stage414 Stage407 drawdown-gated streak 15pct" if soft_streak else "Stage407 baseline rerun"
    note = (
        "Stage414 C: Stage407 original AI pool plus jd AI rerank top9 maxpos5, with severe 0.1 loss-streak "
        "risk only active when portfolio drawdown is above 15%."
        if soft_streak
        else "Stage407 B rerun: original AI pool plus jd AI rerank top9 maxpos5 with the original hard 0.1 loss-streak floor."
    )
    capital = replace(base.capital, variant=variant, label=label, max_concurrent_positions=5, note=note)
    overrides = {
        **base.overrides,
        "product_universe_csv_path": str(s696.UNIVERSE_PLUS_JD_PATH),
        "max_concurrent_positions": 5,
        "enable_ai_product_pool_filter": True,
        "ai_product_pool_eligibility_path": str(s696.ELIGIBILITY_PATH),
        "ai_product_pool_strategy": AI_STRATEGY,
        "streak_risk_multipliers": s696.BASE_STREAK_MULTIPLIERS,
    }
    profile = "stage407_original_ai_plus_jd_ai_rerank_top9_maxpos5_drawdown_gated_streak15" if soft_streak else "stage407_original_ai_plus_jd_ai_rerank_top9_maxpos5"
    return replace(base, capital=capital, overrides=overrides, profile=profile)


def _patched_current_streak_multiplier(self: QmtRollPortfolioStrategy) -> float:
    raw_multiplier = float(_ORIGINAL_CURRENT_STREAK_MULTIPLIER(self))
    if int(getattr(self, "loss_streak", 0) or 0) < 3:
        return raw_multiplier
    if raw_multiplier > 0.1000001:
        return raw_multiplier
    drawdown = float(getattr(self, "portfolio_drawdown_pct", 0.0) or 0.0)
    if drawdown < STREAK_SEVERE_DD_GATE_RATIO:
        return 1.0
    return raw_multiplier


def _run_variant_with_patch(
    spec: s696.s692.s653.ForcedVariant,
    metadata: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    patched_variants = {OFFICIAL_DD_GATE_VARIANT, TARGET_VARIANT}
    if spec.capital.variant in patched_variants:
        QmtRollPortfolioStrategy._current_streak_multiplier = _patched_current_streak_multiplier
    else:
        QmtRollPortfolioStrategy._current_streak_multiplier = _ORIGINAL_CURRENT_STREAK_MULTIPLIER
    try:
        return _BASE_RUN_VARIANT(spec, metadata)
    finally:
        QmtRollPortfolioStrategy._current_streak_multiplier = _ORIGINAL_CURRENT_STREAK_MULTIPLIER


def _plot(daily: pd.DataFrame) -> None:
    if daily.empty:
        return
    data = daily.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data["label"] = data["variant"].map(
        {
            s696.BASE_VARIANT: "A Official current",
            OFFICIAL_DD_GATE_VARIANT: "D Official DD-gated streak",
            s696.STAGE407_VARIANT: "B Stage407 current",
            TARGET_VARIANT: "C Stage407 DD-gated streak",
        }
    ).fillna(data["variant"])
    colors = {
        "A Official current": "#ea580c",
        "D Official DD-gated streak": "#a855f7",
        "B Stage407 current": "#16a34a",
        "C Stage407 DD-gated streak": "#2563eb",
    }
    fig, ax = plt.subplots(figsize=(15, 7))
    for label, group in data.sort_values("date").groupby("label", sort=False):
        ax.plot(group["date"], group["account_equity"].astype(float), label=label, linewidth=1.8, color=colors.get(label))
    ax.axhline(200_000, color="#94a3b8", linestyle="--", linewidth=0.9, label="Initial capital")
    ax.axvspan(pd.Timestamp(s696.WINDOW_START), pd.Timestamp(s696.WINDOW_END), color="#ef4444", alpha=0.10)
    ax.set_title("Stage414 Equity Curves: drawdown-gated loss-streak floor")
    ax.set_xlabel("Date")
    ax.set_ylabel("Account equity")
    ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.35)
    ax.legend(loc="upper left")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(s696.EQUITY_CHART_PATH, dpi=170)
    fig.savefig(s696.CHART_PATH, dpi=170)
    plt.close(fig)


def _decision(
    summary: pd.DataFrame,
    cost: pd.DataFrame,
    comparison: pd.DataFrame,
    window_growth: pd.DataFrame,
    entry_risk_summary: pd.DataFrame,
    inputs: dict[str, Any],
) -> dict[str, Any]:
    decision = _BASE_DECISION(summary, cost, comparison, window_growth, entry_risk_summary, inputs)
    decision["stage"] = "Stage414"
    decision["script_stage"] = "Stage701"
    decision["model_tag"] = MODEL_TAG
    decision["official_soft"] = OFFICIAL_DD_GATE_VARIANT
    decision["target"] = TARGET_VARIANT
    change = dict(decision.get("change", {}))
    change.update(
        {
            "candidate_hypothesis": (
                "Keep the original 1,1,1,0.1 loss-streak rule, but activate the severe 0.1 floor only when "
                "portfolio drawdown is above 15%; consecutive losses alone are treated as too noisy to cut "
                "all unrelated trend opportunities to near-zero size."
            ),
            "streak_risk_multipliers_before": s696.BASE_STREAK_MULTIPLIERS,
            "streak_risk_multipliers_after": s696.BASE_STREAK_MULTIPLIERS,
            "severe_streak_drawdown_gate_ratio": STREAK_SEVERE_DD_GATE_RATIO,
        }
    )
    decision["change"] = change
    hard_fail = list(decision.get("hard_fail_checks", []))
    decision["decision"] = "stage407_drawdown_gated_streak_not_promoted" if hard_fail else "stage407_drawdown_gated_streak_watch"
    return decision


def _write_report(
    summary: pd.DataFrame,
    cost: pd.DataFrame,
    comparison: pd.DataFrame,
    annual: pd.DataFrame,
    product_delta: pd.DataFrame,
    window_growth: pd.DataFrame,
    window_product: pd.DataFrame,
    entry_risk_summary: pd.DataFrame,
    forced_summary: pd.DataFrame,
    ai_audit: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    lines = [
        "# Stage414 / Script701 Stage407 Drawdown-Gated Loss-Streak Floor",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{s696.LINE_ID}`",
        "- A：当前正式 Stage372/20w，正式 AI，`maxpos4`，原连败倍率。",
        "- D：A 仅把三连败后 `0.1` 严重降仓限定在账户回撤超过 `15%` 后生效。",
        "- B：Stage407 基线，原正式 AI 池 + `jd.DCE` 参与 AI 重排 top9，`maxpos5`，原连败倍率。",
        "- C：B 仅把三连败后 `0.1` 严重降仓限定在账户回撤超过 `15%` 后生效。",
        "- 不修改正式配置、不连接 CTP、不调用下单。",
        "",
        "## Summary",
        "",
        s696._md_table(summary),
        "",
        "## Cost Stress",
        "",
        s696._md_table(cost, max_rows=120),
        "",
        "## Comparison",
        "",
        s696._md_table(comparison, max_rows=120),
        "",
        "## Highlight Window Growth",
        "",
        s696._md_table(window_growth, max_rows=40),
        "",
        "## Highlight Window Product Delta",
        "",
        s696._md_table(window_product, max_rows=80),
        "",
        "## Entry Risk Summary",
        "",
        s696._md_table(entry_risk_summary, max_rows=120),
        "",
        "## Annual",
        "",
        s696._md_table(annual, max_rows=120),
        "",
        "## Product Delta",
        "",
        s696._md_table(product_delta, max_rows=120),
        "",
        "## Forced Deleverage",
        "",
        s696._md_table(forced_summary),
        "",
        "## AI Audit",
        "",
        s696._md_table(ai_audit, max_rows=80),
        "",
        "## Decision",
        "",
        f"- decision: `{decision['decision']}`",
        f"- hard_fail_checks: `{', '.join(decision['hard_fail_checks']) or '无'}`",
        f"- watch_checks: `{', '.join(decision['watch_checks']) or '无'}`",
    ]
    s696.REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    _reconfigure_paths()
    s696._official_soft_spec = _official_dd_gate_spec
    s696._stage407_spec = _stage407_spec
    s696._run_variant_with_diagnostics = _run_variant_with_patch
    s696._plot = _plot
    s696._decision = _decision
    s696._write_report = _write_report
    s696.main()


if __name__ == "__main__":
    main()
