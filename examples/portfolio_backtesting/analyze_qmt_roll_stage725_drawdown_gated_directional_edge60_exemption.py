from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

import analyze_qmt_roll_stage707_recovery_all_cases_multiperiod as s707
import analyze_qmt_roll_stage724_directional_edge60_exemption_multiperiod as s724


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage725_drawdown_gated_directional_edge60_exemption_v1"
OUTPUT_PREFIX = "qmt_roll_stage725_drawdown_gated_directional_edge60_exemption"
LINE_ID = "futures_trend_winner_trade_forensics"

BASE_VARIANT = s707.BASE_VARIANT
CANDIDATE_VARIANT = (
    "stage526_200k_force95_to80_drawdown_gated_directional_edge60_exemption_stage725"
)
RECOVERY_SIGNALS = "long_case1a,long_case2,long_case3,short_case1a,short_case2,short_case3"
DIRECTIONAL_EDGE_PERIOD = 60
LONG_CLOSE_POSITION_MIN = 0.80
SHORT_CLOSE_POSITION_MAX = 0.20
ACCOUNT_HEALTH_MAX_DRAWDOWN = 0.05

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


def _candidate_spec(metadata: dict[str, Any]) -> s707.s653.ForcedVariant:
    base = s707.s660._official_spec(metadata)
    capital = replace(
        base.capital,
        variant=CANDIDATE_VARIANT,
        label="Stage725 drawdown-gated edge60 normal-risk exemption",
        note=(
            "Official Stage372 unchanged except the 0.1-floor clean-book recovery lift is allowed for all native "
            "entry cases only when close remains near the directional 60-day range edge and the account is within "
            "5% drawdown from high water. Recovery sleeve is disabled so a passed setup gets normal risk sizing."
        ),
    )
    overrides = {
        **base.overrides,
        "enable_streak_entry_structure_risk_recovery": True,
        "streak_entry_structure_recovery_signals": RECOVERY_SIGNALS,
        "streak_entry_structure_recovery_min_multiplier": 1.0,
        "streak_entry_structure_recovery_require_flat_portfolio": True,
        "streak_entry_structure_recovery_max_same_direction_corr": 0.30,
        "streak_entry_structure_recovery_require_rsi_confirmation": False,
        "streak_entry_structure_recovery_require_directional_edge60": True,
        "streak_entry_structure_recovery_directional_edge_period": DIRECTIONAL_EDGE_PERIOD,
        "streak_entry_structure_recovery_long_close_position_min": LONG_CLOSE_POSITION_MIN,
        "streak_entry_structure_recovery_short_close_position_max": SHORT_CLOSE_POSITION_MAX,
        "streak_entry_structure_recovery_max_portfolio_drawdown_pct": ACCOUNT_HEALTH_MAX_DRAWDOWN,
        "enable_recovery_sleeve": False,
        "streak_risk_multipliers": "1.0,1.0,1.0,0.1",
    }
    return replace(
        base,
        capital=capital,
        overrides=overrides,
        profile="official_stage372_drawdown_gated_directional_edge60_exemption_stage725",
    )


def _check_rows(summary: pd.DataFrame, comparison: pd.DataFrame, cost: pd.DataFrame) -> pd.DataFrame:
    s724.CANDIDATE_VARIANT = CANDIDATE_VARIANT
    s724.BASE_VARIANT = BASE_VARIANT
    return s724._check_rows(summary, comparison, cost)


def _decision(summary: pd.DataFrame, comparison: pd.DataFrame, cost: pd.DataFrame, checks: pd.DataFrame) -> dict[str, Any]:
    hard_fail = checks[checks["status"].eq("fail")]["check_name"].astype(str).tolist()
    label = (
        "drawdown_gated_directional_edge60_exemption_next_validation"
        if not hard_fail
        else "drawdown_gated_directional_edge60_exemption_not_promoted"
    )
    return {
        "stage": "Stage725",
        "script_stage": "Stage725",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "official_live_version": s707.OFFICIAL_LIVE_VERSION,
        "baseline": BASE_VARIANT,
        "candidate": CANDIDATE_VARIANT,
        "decision": label,
        "hard_fail_checks": hard_fail,
        "watch_checks": [],
        "change": {
            "official_config_changed": False,
            "ctp_connected": False,
            "order_api_called": False,
            "streak_risk_multipliers_before": "1.0,1.0,1.0,0.1",
            "streak_risk_multipliers_after": "1.0,1.0,1.0,0.1",
            "recovery_signals_before": "long_case1a,short_case1a",
            "recovery_signals_after": RECOVERY_SIGNALS,
            "recovery_requires_flat_portfolio": True,
            "recovery_max_same_direction_corr": 0.30,
            "recovery_requires_directional_edge60": True,
            "directional_edge_period": DIRECTIONAL_EDGE_PERIOD,
            "long_close_position_min": LONG_CLOSE_POSITION_MIN,
            "short_close_position_max": SHORT_CLOSE_POSITION_MAX,
            "account_health_max_portfolio_drawdown": ACCOUNT_HEALTH_MAX_DRAWDOWN,
            "recovery_sleeve_before": True,
            "recovery_sleeve_after": False,
        },
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
        CANDIDATE_VARIANT: "C edge60 + DD<=5%",
    }
    colors = {
        BASE_VARIANT: "#ea580c",
        CANDIDATE_VARIANT: "#0891b2",
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
        "# Stage725 Drawdown-Gated Directional Edge60 Exemption",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        f"- 当前 official live：`{s707.OFFICIAL_LIVE_VERSION}` / `{s707.OFFICIAL_LIVE_PROFILE_NAME}`",
        "- A：当前正式 Stage372/20w，`case1a` 恢复规则 + one-lot recovery sleeve。",
        "- C：保持 `streak_risk_multipliers=1,1,1,0.1`，把 clean-book recovery lift 扩到所有原生趋势入场 case，但同时要求 `directional_edge60` 与账户回撤 `<=5%`；C 关闭 recovery sleeve，使通过条件的机会恢复正常风险 sizing。",
        f"- directional_edge60：long close position >= `{LONG_CLOSE_POSITION_MIN:g}`；short close position <= `{SHORT_CLOSE_POSITION_MAX:g}`；lookback `{DIRECTIONAL_EDGE_PERIOD}`。",
        f"- account health：portfolio drawdown <= `{ACCOUNT_HEALTH_MAX_DRAWDOWN:g}`。",
        "- 不修改正式配置、不连接 CTP、不调用下单。",
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
        f"- 决策：`{decision['decision']}`",
        f"- hard_fail_checks：`{', '.join(decision['hard_fail_checks']) or '无'}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    s707.MODEL_TAG = MODEL_TAG
    s707.OUTPUT_PREFIX = OUTPUT_PREFIX
    s707.LINE_ID = LINE_ID
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
    s707._check_rows = _check_rows
    s707._decision = _decision
    s707._plot = _plot
    s707._write_report = _write_report
    s707.main()


if __name__ == "__main__":
    main()
