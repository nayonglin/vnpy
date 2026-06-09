from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

import analyze_qmt_roll_stage707_recovery_all_cases_multiperiod as s707
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage711_loss_streak_severity_gate_multiperiod_v1"
OUTPUT_PREFIX = "qmt_roll_stage711_loss_streak_severity_gate_multiperiod"
LINE_ID = "futures_trend_drawdown30_preserve_return"

BASE_VARIANT = s707.BASE_VARIANT
CANDIDATE_VARIANT = (
    "stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4_"
    "loss_streak_severity_gate1pct_stage711"
)

SEVERITY_MODE = "stage711_loss_streak_severity_gate"
SEVERITY_MIN_CUM_LOSS_RATIO = 0.01
BASE_STREAK_MULTIPLIERS = "1.0,1.0,1.0,0.1"
GATE_AUDIT: dict[str, float] = {
    "severity_mode_calls": 0.0,
    "severe_tier_calls": 0.0,
    "severe_floor_kept_calls": 0.0,
    "mild_streak_bypass_calls": 0.0,
    "min_loss_to_threshold_ratio": 999.0,
    "max_loss_to_threshold_ratio": 0.0,
}

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
ANNUAL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_{MODEL_TAG}.csv"
MONTHLY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_monthly_{MODEL_TAG}.csv"
CHECKS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_checks_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

_ORIGINAL_CURRENT_STREAK_MULTIPLIER = QmtRollPortfolioStrategy._current_streak_multiplier
_ORIGINAL_UPDATE_STREAK_RISK_STATE = QmtRollPortfolioStrategy._update_streak_risk_state


def _severity_mode_enabled(strategy: QmtRollPortfolioStrategy) -> bool:
    return str(getattr(strategy, "streak_profit_recovery_mode", "") or "").strip() == SEVERITY_MODE


def _sizing_equity_for_gate(strategy: QmtRollPortfolioStrategy) -> float:
    for value in (
        getattr(strategy, "estimated_equity", 0.0),
        getattr(strategy, "capital_base", 0.0),
        getattr(strategy, "base_capital", 0.0),
    ):
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if number > 0.0 and pd.notna(number):
            return number
    return float(s707.OFFICIAL_LIVE_CAPITAL)


def _patched_current_streak_multiplier(strategy: QmtRollPortfolioStrategy) -> float:
    raw = float(_ORIGINAL_CURRENT_STREAK_MULTIPLIER(strategy))
    if not _severity_mode_enabled(strategy):
        return raw

    GATE_AUDIT["severity_mode_calls"] += 1.0
    loss_streak = int(getattr(strategy, "loss_streak", 0) or 0)
    if loss_streak < 3 or raw > 0.1000001:
        return raw

    GATE_AUDIT["severe_tier_calls"] += 1.0
    cumulative_loss = float(getattr(strategy, "_stage711_loss_streak_cum_loss", 0.0) or 0.0)
    threshold = _sizing_equity_for_gate(strategy) * SEVERITY_MIN_CUM_LOSS_RATIO
    ratio = cumulative_loss / threshold if threshold > 0.0 else 999.0
    GATE_AUDIT["min_loss_to_threshold_ratio"] = min(GATE_AUDIT["min_loss_to_threshold_ratio"], ratio)
    GATE_AUDIT["max_loss_to_threshold_ratio"] = max(GATE_AUDIT["max_loss_to_threshold_ratio"], ratio)
    if cumulative_loss >= threshold:
        GATE_AUDIT["severe_floor_kept_calls"] += 1.0
        return raw
    GATE_AUDIT["mild_streak_bypass_calls"] += 1.0
    return 1.0


def _patched_update_streak_risk_state(
    strategy: QmtRollPortfolioStrategy,
    realized_pnl: float,
    product_vt_symbol: str | None = None,
    *,
    exit_reason: str | None = None,
    profit_giveback_context: bool = False,
) -> None:
    if not _severity_mode_enabled(strategy):
        _ORIGINAL_UPDATE_STREAK_RISK_STATE(
            strategy,
            realized_pnl,
            product_vt_symbol,
            exit_reason=exit_reason,
            profit_giveback_context=profit_giveback_context,
        )
        return

    before_streak = int(getattr(strategy, "loss_streak", 0) or 0)
    before_cum_loss = float(getattr(strategy, "_stage711_loss_streak_cum_loss", 0.0) or 0.0)
    _ORIGINAL_UPDATE_STREAK_RISK_STATE(
        strategy,
        realized_pnl,
        product_vt_symbol,
        exit_reason=exit_reason,
        profit_giveback_context=profit_giveback_context,
    )
    after_streak = int(getattr(strategy, "loss_streak", 0) or 0)

    if float(realized_pnl or 0.0) < 0.0 and after_streak > before_streak:
        if before_streak <= 0:
            cumulative_loss = abs(float(realized_pnl))
        else:
            cumulative_loss = before_cum_loss + abs(float(realized_pnl))
    elif after_streak <= 0:
        cumulative_loss = 0.0
    elif after_streak < before_streak:
        cumulative_loss = 0.0
    else:
        cumulative_loss = before_cum_loss

    setattr(strategy, "_stage711_loss_streak_cum_loss", float(max(0.0, cumulative_loss)))
    strategy.risk_multiplier = strategy._current_streak_multiplier()


def _candidate_spec(metadata: dict[str, Any]) -> s707.s653.ForcedVariant:
    base = s707.s660._official_spec(metadata)
    capital = replace(
        base.capital,
        variant=CANDIDATE_VARIANT,
        label="Stage711 loss-streak severity gate 1pct",
        note=(
            "Keep the original loss-streak table, but activate the severe 0.1 floor only after the current "
            "loss streak has realized at least one standard 1pct risk unit."
        ),
    )
    overrides = {
        **base.overrides,
        "streak_risk_multipliers": BASE_STREAK_MULTIPLIERS,
        "streak_profit_recovery_mode": SEVERITY_MODE,
    }
    return replace(base, capital=capital, overrides=overrides, profile="official_stage372_loss_streak_severity_gate_stage711")


def _decision(summary: pd.DataFrame, comparison: pd.DataFrame, cost: pd.DataFrame, checks: pd.DataFrame) -> dict[str, Any]:
    hard_fail = checks[checks["status"].eq("fail")]["check_name"].astype(str).tolist()
    watch = checks[checks["status"].eq("watch")]["check_name"].astype(str).tolist()
    label = "loss_streak_severity_gate_next_validation" if not hard_fail else "loss_streak_severity_gate_not_promoted"
    return {
        "stage": "Stage425",
        "script_stage": "Stage711",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "official_live_version": s707.OFFICIAL_LIVE_VERSION,
        "baseline": BASE_VARIANT,
        "candidate": CANDIDATE_VARIANT,
        "decision": label,
        "hard_fail_checks": hard_fail,
        "watch_checks": watch,
        "change": {
            "official_config_changed": False,
            "ctp_connected": False,
            "order_api_called": False,
            "streak_risk_multipliers_before": BASE_STREAK_MULTIPLIERS,
            "streak_risk_multipliers_after": BASE_STREAK_MULTIPLIERS,
            "severity_mode": SEVERITY_MODE,
            "severity_min_cum_loss_ratio": SEVERITY_MIN_CUM_LOSS_RATIO,
            "severity_threshold_interpretation": "one standard 1pct risk unit of current equity/base capital",
        },
        "gate_audit": GATE_AUDIT.copy(),
        "checks": checks.to_dict("records"),
        "summary": summary.to_dict("records"),
        "comparison": comparison.to_dict("records"),
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "cost": str(COST_PATH),
            "comparison": str(COMPARISON_PATH),
            "curves": str(CURVES_PATH),
            "annual": str(ANNUAL_PATH),
            "monthly": str(MONTHLY_PATH),
            "checks": str(CHECKS_PATH),
            "report": str(REPORT_PATH),
            "chart": str(CHART_PATH),
            "decision": str(DECISION_PATH),
        },
    }


def _plot(curves: pd.DataFrame) -> None:
    if curves.empty:
        return
    plot_data = curves[curves["window_name"].isin(["full_2020_20260430", "since_2022", "phase_2024_2025"])].copy()
    labels = {
        BASE_VARIANT: "A official",
        CANDIDATE_VARIANT: "C severity-gated streak",
    }
    colors = {
        BASE_VARIANT: "#ea580c",
        CANDIDATE_VARIANT: "#4f46e5",
    }
    fig, axes = plt.subplots(3, 1, figsize=(14, 11), sharex=False)
    for ax, (window_name, group) in zip(axes, plot_data.groupby("window_name", sort=False)):
        for variant, series in group.sort_values("date").groupby("variant", sort=False):
            ax.plot(
                series["date"],
                series["account_equity"],
                label=labels.get(variant, variant),
                linewidth=1.5,
                color=colors.get(variant),
            )
        ax.axhline(s707.OFFICIAL_LIVE_CAPITAL, color="#94a3b8", linestyle="--", linewidth=0.8)
        ax.set_title(window_name)
        ax.set_ylabel("equity")
        ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.35)
        ax.legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=170)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    comparison: pd.DataFrame,
    cost: pd.DataFrame,
    annual: pd.DataFrame,
    checks: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    key_cols = [
        "window_name",
        "return_retention_pct",
        "base_total_return_pct",
        "candidate_total_return_pct",
        "base_max_dd_pct",
        "candidate_max_dd_pct",
        "delta_max_dd_pct",
        "base_sharpe",
        "candidate_sharpe",
        "delta_sharpe",
    ]
    lines = [
        "# Stage425 / Script711 Loss-Streak Severity Gate",
        "",
        f"- Generated at: `{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id: `{LINE_ID}`",
        f"- current official live: `{s707.OFFICIAL_LIVE_VERSION}` / `{s707.OFFICIAL_LIVE_PROFILE_NAME}`",
        "- A: current official Stage372/20w with the original `1,1,1,0.1` loss-streak table.",
        "- C: same table, but the severe `0.1` tier is active only when the current consecutive-loss segment "
        "has realized at least one 1pct risk unit.",
        "- Formal config is unchanged; no CTP connection; no order API call.",
        "",
        "## Checks",
        "",
        s707._md_table(checks),
        "",
        "## Comparison",
        "",
        s707._md_table(comparison[key_cols], max_rows=40),
        "",
        "## Summary",
        "",
        s707._md_table(summary, max_rows=80),
        "",
        "## Cost Stress",
        "",
        s707._md_table(cost, max_rows=120),
        "",
        "## Annual Full Path",
        "",
        s707._md_table(annual, max_rows=80),
        "",
        "## Decision",
        "",
        f"- decision: `{decision['decision']}`",
        f"- hard_fail_checks: `{', '.join(decision['hard_fail_checks']) or 'none'}`",
        f"- watch_checks: `{', '.join(decision['watch_checks']) or 'none'}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    for key in GATE_AUDIT:
        GATE_AUDIT[key] = 999.0 if key == "min_loss_to_threshold_ratio" else 0.0

    s707.MODEL_TAG = MODEL_TAG
    s707.OUTPUT_PREFIX = OUTPUT_PREFIX
    s707.CANDIDATE_VARIANT = CANDIDATE_VARIANT
    s707.SUMMARY_PATH = SUMMARY_PATH
    s707.COST_PATH = COST_PATH
    s707.COMPARISON_PATH = COMPARISON_PATH
    s707.CURVES_PATH = CURVES_PATH
    s707.ANNUAL_PATH = ANNUAL_PATH
    s707.MONTHLY_PATH = MONTHLY_PATH
    s707.CHECKS_PATH = CHECKS_PATH
    s707.DECISION_PATH = DECISION_PATH
    s707.REPORT_PATH = REPORT_PATH
    s707.CHART_PATH = CHART_PATH
    s707._candidate_spec = _candidate_spec
    s707._decision = _decision
    s707._plot = _plot
    s707._write_report = _write_report

    QmtRollPortfolioStrategy._current_streak_multiplier = _patched_current_streak_multiplier
    QmtRollPortfolioStrategy._update_streak_risk_state = _patched_update_streak_risk_state
    try:
        s707.main()
    finally:
        QmtRollPortfolioStrategy._current_streak_multiplier = _ORIGINAL_CURRENT_STREAK_MULTIPLIER
        QmtRollPortfolioStrategy._update_streak_risk_state = _ORIGINAL_UPDATE_STREAK_RISK_STATE


if __name__ == "__main__":
    main()
