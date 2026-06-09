from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

import analyze_qmt_roll_stage696_stage407_soft_streak_risk as s696
from qmt_roll_official_live_config import OFFICIAL_LIVE_AI_ELIGIBILITY_PATH
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy


MODEL_TAG = "stage704_stage407_local_last_loss_relevance_v1"
OUTPUT_PREFIX = "qmt_roll_stage704_stage407_local_last_loss_relevance"
OFFICIAL_RELEVANCE_VARIANT = "stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4_local_last_loss_relevance"
TARGET_VARIANT = (
    "stage526_200k_force95_to80_recovery_sleeve_r080_pc25_original_ai_plus_jd_ai_rerank_top9_"
    "maxpos5_local_last_loss_relevance"
)
AI_STRATEGY = "stage704_original_ai_pool_plus_jd_probability_rerank_top9_entry_filter"
AI_SCORE_TYPE = "stage704_original_ai_pool_plus_jd_probability_rerank_top9"
AI_PRE_COVERAGE_SCORE_TYPE = "stage704_official_ai_pre_full_market_coverage"
LOCAL_RELEVANCE_LOOKBACK_DAYS = 252

_ORIGINAL_CURRENT_STREAK_MULTIPLIER = QmtRollPortfolioStrategy._current_streak_multiplier
_ORIGINAL_CALCULATE_ENTRY_SIZING = QmtRollPortfolioStrategy._calculate_entry_sizing
_BASE_RUN_VARIANT = s696._run_variant_with_diagnostics
_BASE_DECISION = s696._decision


def _reconfigure_paths() -> None:
    s696.MODEL_TAG = MODEL_TAG
    s696.OUTPUT_PREFIX = OUTPUT_PREFIX
    s696.OFFICIAL_SOFT_VARIANT = OFFICIAL_RELEVANCE_VARIANT
    s696.TARGET_VARIANT = TARGET_VARIANT
    s696.AI_STRATEGY = AI_STRATEGY
    s696.AI_SCORE_TYPE = AI_SCORE_TYPE
    s696.AI_PRE_COVERAGE_SCORE_TYPE = AI_PRE_COVERAGE_SCORE_TYPE
    s696.SOFT_STREAK_MULTIPLIERS = s696.BASE_STREAK_MULTIPLIERS

    s696.GENERATED_DIR = s696.OUTPUT_DIR / "stage704_generated_inputs"
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


def _local_relevance_overrides(base_overrides: dict[str, Any]) -> dict[str, Any]:
    return {
        **base_overrides,
        "streak_risk_multipliers": s696.BASE_STREAK_MULTIPLIERS,
        # Enable local product+direction outcome history without changing size by itself.
        "enable_failure_memory_micro_sizing": True,
        "failure_memory_micro_sizing_lookback_days": LOCAL_RELEVANCE_LOOKBACK_DAYS,
        "failure_memory_micro_sizing_min_consecutive_failures": 999,
        "failure_memory_micro_sizing_multiplier": 1.0,
        "failure_memory_micro_sizing_entry_contexts": "flat_entry",
    }


def _official_local_relevance_spec(identity_map: str) -> s696.s692.s653.ForcedVariant:
    base = s696._official_spec(identity_map)
    capital = replace(
        base.capital,
        variant=OFFICIAL_RELEVANCE_VARIANT,
        label="Stage417 official local last-loss relevance",
        note=(
            "Official Stage372 with the 0.1 account loss-streak floor applied only when the current "
            "product+direction also had a recent local loss."
        ),
    )
    overrides = _local_relevance_overrides(
        {
            **base.overrides,
            "ai_product_pool_eligibility_path": str(OFFICIAL_LIVE_AI_ELIGIBILITY_PATH),
        }
    )
    return replace(base, capital=capital, overrides=overrides, profile="official_stage372_local_last_loss_relevance")


def _stage407_spec(identity_map: str, *, soft_streak: bool) -> s696.s692.s653.ForcedVariant:
    base = s696._official_spec(identity_map)
    variant = TARGET_VARIANT if soft_streak else s696.STAGE407_VARIANT
    label = "Stage417 Stage407 local last-loss relevance" if soft_streak else "Stage407 baseline rerun"
    note = (
        "Stage417 C: Stage407 original AI pool plus jd AI rerank top9 maxpos5, with the severe 0.1 "
        "loss-streak floor applied only when current product+direction also had a recent local loss."
        if soft_streak
        else "Stage407 B rerun: original AI pool plus jd AI rerank top9 maxpos5 with the original hard 0.1 account loss-streak floor."
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
    if soft_streak:
        overrides = _local_relevance_overrides(overrides)
    profile = "stage407_original_ai_plus_jd_ai_rerank_top9_maxpos5_local_last_loss_relevance" if soft_streak else "stage407_original_ai_plus_jd_ai_rerank_top9_maxpos5"
    return replace(base, capital=capital, overrides=overrides, profile=profile)


def _candidate_product(self: QmtRollPortfolioStrategy, vt_symbol: str) -> str:
    return str(self.source_symbol_by_contract.get(vt_symbol, self._product_vt_symbol(vt_symbol)) or "")


def _patched_calculate_entry_sizing(self: QmtRollPortfolioStrategy, vt_symbol: str, direction: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
    self._stage704_candidate_product = _candidate_product(self, vt_symbol)
    self._stage704_candidate_direction = str(direction or "")
    try:
        return _ORIGINAL_CALCULATE_ENTRY_SIZING(self, vt_symbol, direction, *args, **kwargs)
    finally:
        self._stage704_candidate_product = ""
        self._stage704_candidate_direction = ""


def _recent_local_last_trade_was_loss(self: QmtRollPortfolioStrategy, product: str, direction: str) -> bool:
    history = list(self.product_direction_outcome_history.get((product, direction), []))
    if not history:
        return False
    asof = getattr(self, "current_bar_date", None)
    asof_date = (
        pd.Timestamp(asof).tz_localize(None).normalize()
        if asof is not None
        else pd.Timestamp(datetime.now()).normalize()
    )
    lookback_start = asof_date - pd.Timedelta(days=LOCAL_RELEVANCE_LOOKBACK_DAYS)
    valid = []
    for item in history:
        exit_date = pd.Timestamp(item.get("exit_date")).tz_localize(None).normalize()
        if lookback_start <= exit_date < asof_date:
            valid.append((exit_date, float(item.get("realized_pnl", 0.0) or 0.0)))
    if not valid:
        return False
    valid.sort(key=lambda item: item[0])
    return valid[-1][1] < 0.0


def _patched_current_streak_multiplier(self: QmtRollPortfolioStrategy) -> float:
    raw_multiplier = float(_ORIGINAL_CURRENT_STREAK_MULTIPLIER(self))
    if int(getattr(self, "loss_streak", 0) or 0) < 3:
        return raw_multiplier
    if raw_multiplier > 0.1000001:
        return raw_multiplier

    product = str(getattr(self, "_stage704_candidate_product", "") or "")
    direction = str(getattr(self, "_stage704_candidate_direction", "") or "")
    if not product or direction not in {"long", "short"}:
        return raw_multiplier
    if _recent_local_last_trade_was_loss(self, product, direction):
        return raw_multiplier
    return 1.0


def _run_variant_with_patch(
    spec: s696.s692.s653.ForcedVariant,
    metadata: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    patched_variants = {OFFICIAL_RELEVANCE_VARIANT, TARGET_VARIANT}
    if spec.capital.variant in patched_variants:
        QmtRollPortfolioStrategy._current_streak_multiplier = _patched_current_streak_multiplier
        QmtRollPortfolioStrategy._calculate_entry_sizing = _patched_calculate_entry_sizing
    else:
        QmtRollPortfolioStrategy._current_streak_multiplier = _ORIGINAL_CURRENT_STREAK_MULTIPLIER
        QmtRollPortfolioStrategy._calculate_entry_sizing = _ORIGINAL_CALCULATE_ENTRY_SIZING
    try:
        return _BASE_RUN_VARIANT(spec, metadata)
    finally:
        QmtRollPortfolioStrategy._current_streak_multiplier = _ORIGINAL_CURRENT_STREAK_MULTIPLIER
        QmtRollPortfolioStrategy._calculate_entry_sizing = _ORIGINAL_CALCULATE_ENTRY_SIZING


def _plot(daily: pd.DataFrame) -> None:
    if daily.empty:
        return
    data = daily.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data["label"] = data["variant"].map(
        {
            s696.BASE_VARIANT: "A Official current",
            OFFICIAL_RELEVANCE_VARIANT: "D Official local relevance",
            s696.STAGE407_VARIANT: "B Stage407 current",
            TARGET_VARIANT: "C Stage407 local relevance",
        }
    ).fillna(data["variant"])
    colors = {
        "A Official current": "#ea580c",
        "D Official local relevance": "#a855f7",
        "B Stage407 current": "#16a34a",
        "C Stage407 local relevance": "#2563eb",
    }
    fig, ax = plt.subplots(figsize=(15, 7))
    for label, group in data.sort_values("date").groupby("label", sort=False):
        ax.plot(group["date"], group["account_equity"].astype(float), label=label, linewidth=1.8, color=colors.get(label))
    ax.axhline(200_000, color="#94a3b8", linestyle="--", linewidth=0.9, label="Initial capital")
    ax.axvspan(pd.Timestamp(s696.WINDOW_START), pd.Timestamp(s696.WINDOW_END), color="#ef4444", alpha=0.10)
    ax.set_title("Stage417 Equity Curves: local last-loss relevance for 0.1 streak floor")
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
    decision["stage"] = "Stage417"
    decision["script_stage"] = "Stage704"
    decision["model_tag"] = MODEL_TAG
    decision["official_soft"] = OFFICIAL_RELEVANCE_VARIANT
    decision["target"] = TARGET_VARIANT
    change = dict(decision.get("change", {}))
    change.update(
        {
            "candidate_hypothesis": (
                "The account-level 0.1 loss-streak floor is only causally relevant when the current "
                "product+direction also had a recent local loss; unrelated products should not be cut "
                "to near-zero risk solely because the global account had three losing exits."
            ),
            "streak_risk_multipliers_before": s696.BASE_STREAK_MULTIPLIERS,
            "streak_risk_multipliers_after": s696.BASE_STREAK_MULTIPLIERS,
            "local_relevance_lookback_days": LOCAL_RELEVANCE_LOOKBACK_DAYS,
        }
    )
    decision["change"] = change
    hard_fail = list(decision.get("hard_fail_checks", []))
    decision["decision"] = "stage407_local_last_loss_relevance_not_promoted" if hard_fail else "stage407_local_last_loss_relevance_watch"
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
        "# Stage417 / Script704 Stage407 Local Last-Loss Relevance",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{s696.LINE_ID}`",
        "- A：当前正式 Stage372/20w，正式 AI，`maxpos4`，原连败倍率。",
        "- D：A 仅把全局三连败后的 `0.1` 限定到当前品种+方向最近一笔也亏损时生效。",
        "- B：Stage407 基线，原正式 AI 池 + `jd.DCE` 参与 AI 重排 top9，`maxpos5`，原连败倍率。",
        "- C：B 仅把全局三连败后的 `0.1` 限定到当前品种+方向最近一笔也亏损时生效。",
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
        "## Forced Deleveraging",
        "",
        s696._md_table(forced_summary, max_rows=80),
        "",
        "## AI Audit",
        "",
        s696._md_table(ai_audit, max_rows=80),
        "",
        "## Decision",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- 硬失败项：`{decision.get('hard_fail_checks', [])}`",
        "",
    ]
    s696.REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    _reconfigure_paths()
    s696._official_soft_spec = _official_local_relevance_spec
    s696._stage407_spec = _stage407_spec
    s696._run_variant_with_diagnostics = _run_variant_with_patch
    s696._plot = _plot
    s696._decision = _decision
    s696._write_report = _write_report
    s696.main()


if __name__ == "__main__":
    main()
