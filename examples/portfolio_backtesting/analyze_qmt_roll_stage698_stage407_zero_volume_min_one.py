from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

import analyze_qmt_roll_stage696_stage407_soft_streak_risk as s696
from qmt_roll_official_live_config import OFFICIAL_LIVE_AI_ELIGIBILITY_PATH
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy


MODEL_TAG = "stage698_stage407_zero_volume_min_one_v1"
OUTPUT_PREFIX = "qmt_roll_stage698_stage407_zero_volume_min_one"
OFFICIAL_MIN_ONE_VARIANT = "stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4_zero_volume_min_one"
TARGET_VARIANT = (
    "stage526_200k_force95_to80_recovery_sleeve_r080_pc25_original_ai_plus_jd_ai_rerank_top9_"
    "maxpos5_zero_volume_min_one"
)
AI_STRATEGY = "stage698_original_ai_pool_plus_jd_probability_rerank_top9_entry_filter"
AI_SCORE_TYPE = "stage698_original_ai_pool_plus_jd_probability_rerank_top9"
AI_PRE_COVERAGE_SCORE_TYPE = "stage698_official_ai_pre_full_market_coverage"
MIN_ONE_BROKER_MARGIN_MULTIPLIER = 1.65
MIN_ONE_MAX_SINGLE_CONTRACT_BROKER_MARGIN_TO_EQUITY = 0.20

_ORIGINAL_CALCULATE = QmtRollPortfolioStrategy._calculate_entry_sizing
_BASE_RUN_VARIANT = s696._run_variant_with_diagnostics
_BASE_DECISION = s696._decision
_BASE_ENTRY_RISK_SUMMARY = s696._entry_risk_summary


def _reconfigure_paths() -> None:
    s696.MODEL_TAG = MODEL_TAG
    s696.OUTPUT_PREFIX = OUTPUT_PREFIX
    s696.OFFICIAL_SOFT_VARIANT = OFFICIAL_MIN_ONE_VARIANT
    s696.TARGET_VARIANT = TARGET_VARIANT
    s696.AI_STRATEGY = AI_STRATEGY
    s696.AI_SCORE_TYPE = AI_SCORE_TYPE
    s696.AI_PRE_COVERAGE_SCORE_TYPE = AI_PRE_COVERAGE_SCORE_TYPE
    s696.SOFT_STREAK_MULTIPLIERS = s696.BASE_STREAK_MULTIPLIERS

    s696.GENERATED_DIR = s696.OUTPUT_DIR / "stage698_generated_inputs"
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


def _official_min_one_spec(identity_map: str) -> s696.s692.s653.ForcedVariant:
    base = s696._official_spec(identity_map)
    capital = replace(
        base.capital,
        variant=OFFICIAL_MIN_ONE_VARIANT,
        label="Stage411 official zero-volume min-one",
        note=(
            "Official Stage372 unchanged except a runtime zero-volume min-one participation patch is "
            "applied only when risk budget is the binding zero-contract constraint at the 0.1 loss-streak floor."
        ),
    )
    overrides = {
        **base.overrides,
        "ai_product_pool_eligibility_path": str(OFFICIAL_LIVE_AI_ELIGIBILITY_PATH),
        "streak_risk_multipliers": s696.BASE_STREAK_MULTIPLIERS,
    }
    return replace(base, capital=capital, overrides=overrides, profile="official_stage372_zero_volume_min_one")


def _stage407_spec(identity_map: str, *, soft_streak: bool) -> s696.s692.s653.ForcedVariant:
    base = s696._official_spec(identity_map)
    variant = TARGET_VARIANT if soft_streak else s696.STAGE407_VARIANT
    label = "Stage411 Stage407 zero-volume min-one" if soft_streak else "Stage407 baseline rerun"
    note = (
        "Stage411 C: Stage407 original AI pool plus jd AI rerank top9 maxpos5, with only zero-volume "
        "risk-budget candidates lifted to one contract under the existing 0.1 loss-streak floor."
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
    profile = "stage407_original_ai_plus_jd_ai_rerank_top9_maxpos5_zero_volume_min_one" if soft_streak else "stage407_original_ai_plus_jd_ai_rerank_top9_maxpos5"
    return replace(base, capital=capital, overrides=overrides, profile=profile)


def _patched_calculate_entry_sizing(self: QmtRollPortfolioStrategy, *args: Any, **kwargs: Any) -> dict[str, Any]:
    sizing = dict(_ORIGINAL_CALCULATE(self, *args, **kwargs))
    entry_context = str(kwargs.get("entry_context", "flat_entry"))
    selected_before = int(sizing.get("selected_volume") or 0)
    sizing["zero_volume_min_one_enabled"] = 1
    sizing["zero_volume_min_one_applied"] = 0
    sizing["zero_volume_min_one_selected_volume_before"] = selected_before
    sizing["zero_volume_min_one_selected_volume_after"] = selected_before
    sizing["zero_volume_min_one_reason"] = ""

    if entry_context != "flat_entry":
        sizing["zero_volume_min_one_reason"] = "not_flat_entry"
        return sizing
    if selected_before > 0:
        sizing["zero_volume_min_one_reason"] = "already_openable"
        return sizing
    if str(sizing.get("sizing_method") or "") != "risk_budget":
        sizing["zero_volume_min_one_reason"] = "not_risk_budget"
        return sizing

    contracts_by_risk = int(sizing.get("contracts_by_risk") or 0)
    contracts_by_margin = int(sizing.get("contracts_by_margin") or 0)
    contracts_by_single = int(sizing.get("contracts_by_single_trade_cap") or 0)
    cluster_max = int(sizing.get("risk_cluster_max_volume") or 0)
    risk_multiplier = float(sizing.get("risk_multiplier") or 0.0)
    margin_per_contract = float(sizing.get("margin_per_contract") or 0.0)
    sizing_equity = float(
        sizing.get("sizing_equity")
        or sizing.get("effective_sizing_equity_cap")
        or self.estimated_equity
        or self.base_capital
        or 0.0
    )
    min_volume = max(1, int(getattr(self, "min_position_size", 1) or 1))
    broker_single_ratio = (
        margin_per_contract * MIN_ONE_BROKER_MARGIN_MULTIPLIER * min_volume / sizing_equity
        if sizing_equity > 0.0 and margin_per_contract > 0.0
        else 999.0
    )
    sizing["zero_volume_min_one_broker_margin_multiplier"] = MIN_ONE_BROKER_MARGIN_MULTIPLIER
    sizing["zero_volume_min_one_single_contract_broker_margin_to_equity"] = broker_single_ratio
    sizing["zero_volume_min_one_max_single_contract_broker_margin_to_equity"] = (
        MIN_ONE_MAX_SINGLE_CONTRACT_BROKER_MARGIN_TO_EQUITY
    )

    if risk_multiplier > 0.1000001:
        sizing["zero_volume_min_one_reason"] = "not_loss_streak_floor"
        return sizing
    if contracts_by_risk > 0:
        sizing["zero_volume_min_one_reason"] = "not_risk_zero"
        return sizing
    if contracts_by_margin < min_volume:
        sizing["zero_volume_min_one_reason"] = "margin_not_enough"
        return sizing
    if contracts_by_single < min_volume:
        sizing["zero_volume_min_one_reason"] = "single_trade_cap_not_enough"
        return sizing
    if cluster_max < min_volume:
        sizing["zero_volume_min_one_reason"] = "risk_cluster_cap_not_enough"
        return sizing
    if broker_single_ratio > MIN_ONE_MAX_SINGLE_CONTRACT_BROKER_MARGIN_TO_EQUITY:
        sizing["zero_volume_min_one_reason"] = "single_contract_margin_too_high"
        return sizing

    sizing["selected_volume"] = min_volume
    sizing["zero_volume_min_one_applied"] = 1
    sizing["zero_volume_min_one_selected_volume_after"] = min_volume
    sizing["zero_volume_min_one_reason"] = "risk_zero_margin_openable_min_one"
    return sizing


def _run_variant_with_patch(
    spec: s696.s692.s653.ForcedVariant,
    metadata: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    patched_variants = {OFFICIAL_MIN_ONE_VARIANT, TARGET_VARIANT}
    QmtRollPortfolioStrategy._calculate_entry_sizing = (
        _patched_calculate_entry_sizing if spec.capital.variant in patched_variants else _ORIGINAL_CALCULATE
    )
    try:
        return _BASE_RUN_VARIANT(spec, metadata)
    finally:
        QmtRollPortfolioStrategy._calculate_entry_sizing = _ORIGINAL_CALCULATE


def _entry_risk_summary(candidates: pd.DataFrame, entry_risk: pd.DataFrame) -> pd.DataFrame:
    summary = _BASE_ENTRY_RISK_SUMMARY(candidates, entry_risk)
    if candidates.empty or summary.empty:
        return summary
    cand = candidates.copy()
    cand["date"] = pd.to_datetime(cand["date"], errors="coerce").dt.normalize()
    for column in ["selected_volume", "contracts_by_risk", "contracts_by_margin", "risk_multiplier", "loss_streak"]:
        cand[column] = pd.to_numeric(cand.get(column, 0.0), errors="coerce").fillna(0.0)
    cand["scope"] = "all_candidates"
    cand_window = cand[(cand["date"] >= pd.Timestamp(s696.WINDOW_START)) & (cand["date"] <= pd.Timestamp(s696.WINDOW_END))].copy()
    cand_window["scope"] = "window_candidates"
    data = pd.concat([cand, cand_window], ignore_index=True, sort=False)
    inferred_rows: list[dict[str, Any]] = []
    for (variant, scope), group in data.groupby(["variant", "scope"], sort=True):
        inferred = group[
            group["selected_volume"].eq(1)
            & group["contracts_by_risk"].le(0)
            & group["contracts_by_margin"].ge(1)
            & group["risk_multiplier"].le(0.1000001)
        ]
        inferred_rows.append(
            {
                "variant": variant,
                "scope": scope,
                "zero_volume_min_one_inferred_rows": int(len(inferred)),
                "zero_volume_min_one_inferred_selected_volume_sum": float(inferred["selected_volume"].sum()),
                "zero_volume_min_one_inferred_loss_streak_ge3_rows": int(inferred["loss_streak"].ge(3).sum()),
            }
        )
    inferred_frame = pd.DataFrame(inferred_rows)
    return summary.merge(inferred_frame, on=["variant", "scope"], how="left")


def _plot(daily: pd.DataFrame) -> None:
    if daily.empty:
        return
    data = daily.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data["label"] = data["variant"].map(
        {
            s696.BASE_VARIANT: "A Official current",
            OFFICIAL_MIN_ONE_VARIANT: "D Official zero-min1",
            s696.STAGE407_VARIANT: "B Stage407 current",
            TARGET_VARIANT: "C Stage407 zero-min1",
        }
    ).fillna(data["variant"])
    colors = {
        "A Official current": "#ea580c",
        "D Official zero-min1": "#a855f7",
        "B Stage407 current": "#16a34a",
        "C Stage407 zero-min1": "#2563eb",
    }
    fig, axes = plt.subplots(3, 1, figsize=(13, 10), sharex=True, gridspec_kw={"height_ratios": [2, 1, 1]})
    for label, group in data.sort_values("date").groupby("label", sort=False):
        equity = group["account_equity"].astype(float)
        drawdown = (equity / equity.cummax() - 1.0) * 100.0
        axes[0].plot(group["date"], equity, label=label, linewidth=1.25, color=colors.get(label))
        axes[1].plot(group["date"], drawdown, label=label, linewidth=1.05, color=colors.get(label))
        axes[2].plot(
            group["date"],
            group["broker10_margin_to_equity_pct"],
            label=label,
            linewidth=1.05,
            color=colors.get(label),
        )
    for ax in axes:
        ax.axvspan(pd.Timestamp(s696.WINDOW_START), pd.Timestamp(s696.WINDOW_END), color="#ef4444", alpha=0.10)
        ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.35)
        ax.legend(loc="upper left")
    axes[0].axhline(200_000, color="#94a3b8", linestyle="--", linewidth=0.8)
    axes[0].set_title("Stage411 / Script698: zero-volume min-one participation")
    axes[0].set_ylabel("Equity")
    axes[1].axhline(-30, color="#f59e0b", linestyle="--", linewidth=0.8, alpha=0.8)
    axes[1].axhline(-40, color="#ef4444", linestyle="--", linewidth=0.8, alpha=0.8)
    axes[1].set_title("Drawdown")
    axes[1].set_ylabel("DD %")
    axes[2].axhline(90, color="#ef4444", linestyle="--", linewidth=0.8, alpha=0.55)
    axes[2].axhline(100, color="#991b1b", linestyle="--", linewidth=0.8, alpha=0.55)
    axes[2].set_title("Broker10 margin / equity")
    axes[2].set_ylabel("Margin %")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(s696.CHART_PATH, dpi=170)
    plt.close(fig)

    fig2, ax = plt.subplots(figsize=(15, 7))
    for label, group in data.sort_values("date").groupby("label", sort=False):
        ax.plot(group["date"], group["account_equity"].astype(float), label=label, linewidth=1.8, color=colors.get(label))
    ax.axhline(200_000, color="#94a3b8", linestyle="--", linewidth=0.9, label="Initial capital")
    ax.axvspan(pd.Timestamp(s696.WINDOW_START), pd.Timestamp(s696.WINDOW_END), color="#ef4444", alpha=0.10)
    ax.set_title("Stage411 Equity Curves: zero-volume min-one participation")
    ax.set_xlabel("Date")
    ax.set_ylabel("Account equity")
    ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.35)
    ax.legend(loc="upper left")
    fig2.autofmt_xdate()
    fig2.tight_layout()
    fig2.savefig(s696.EQUITY_CHART_PATH, dpi=170)
    plt.close(fig2)


def _decision(
    summary: pd.DataFrame,
    cost: pd.DataFrame,
    comparison: pd.DataFrame,
    window_growth: pd.DataFrame,
    entry_risk_summary: pd.DataFrame,
    inputs: dict[str, Any],
) -> dict[str, Any]:
    decision = _BASE_DECISION(summary, cost, comparison, window_growth, entry_risk_summary, inputs)
    decision["stage"] = "Stage411"
    decision["script_stage"] = "Stage698"
    decision["model_tag"] = MODEL_TAG
    decision["official_soft"] = OFFICIAL_MIN_ONE_VARIANT
    decision["target"] = TARGET_VARIANT
    change = dict(decision.get("change", {}))
    change.update(
        {
            "candidate_hypothesis": (
                "Do not lift all loss-streak trades. Only when the 0.1 loss-streak floor makes risk-budget sizing "
                "return zero contracts while margin, single-trade cap, and risk-cluster cap can support the minimum "
                "contract, lift that candidate to the minimum participation size."
            ),
            "streak_risk_multipliers_before": s696.BASE_STREAK_MULTIPLIERS,
            "streak_risk_multipliers_after": s696.BASE_STREAK_MULTIPLIERS,
            "zero_volume_min_one_broker_margin_multiplier": MIN_ONE_BROKER_MARGIN_MULTIPLIER,
            "zero_volume_min_one_max_single_contract_broker_margin_to_equity": (
                MIN_ONE_MAX_SINGLE_CONTRACT_BROKER_MARGIN_TO_EQUITY
            ),
        }
    )
    decision["change"] = change
    hard_fail = list(decision.get("hard_fail_checks", []))
    decision["decision"] = "stage407_zero_volume_min_one_not_promoted" if hard_fail else "stage407_zero_volume_min_one_watch"
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
        "# Stage411 / Script698 Stage407 Zero-Volume Min-One",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{s696.LINE_ID}`",
        "- A：当前正式 Stage372/20w，正式 AI，`maxpos4`，原连败倍率 `1,1,1,0.1`。",
        "- D：A 仅加 0 手补最小参与仓规则，不改变非零仓位。",
        "- B：Stage407 基线，原正式 AI 池 + `jd.DCE` 参与 AI 重排 top9，`maxpos5`，原连败倍率 `1,1,1,0.1`。",
        "- C：B 仅加 0 手补最小参与仓规则，不改变非零仓位。",
        "- 补仓硬条件：`selected_volume=0`、`contracts_by_risk=0`、`contracts_by_margin>=1`、`contracts_by_single_trade_cap>=1`、风险簇允许、`risk_multiplier<=0.1`、单手 broker 保证金估算不超过权益 `20%`。",
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
    s696._official_soft_spec = _official_min_one_spec
    s696._stage407_spec = _stage407_spec
    s696._run_variant_with_diagnostics = _run_variant_with_patch
    s696._entry_risk_summary = _entry_risk_summary
    s696._plot = _plot
    s696._decision = _decision
    s696._write_report = _write_report
    s696.main()


if __name__ == "__main__":
    main()
