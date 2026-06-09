from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

import analyze_qmt_roll_stage707_recovery_all_cases_multiperiod as s707


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage710_no_streak_vol_budget_multiperiod_v1"
OUTPUT_PREFIX = "qmt_roll_stage710_no_streak_vol_budget_multiperiod"
LINE_ID = "futures_trend_drawdown30_preserve_return"

BASE_VARIANT = s707.BASE_VARIANT
CANDIDATE_VARIANT = "stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4_no_streak_vol60_t60_min50_stage710"

VOL_LOOKBACK = 60
VOL_TARGET_ANNUAL = 0.60
VOL_MIN_SCALE = 0.50
VOL_CONTEXTS = "flat_entry,reverse_entry,rollover_reopen,regular_add,donchian_add"
NO_STREAK_MULTIPLIERS = "1.0,1.0,1.0,1.0"

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
        label="Stage710 no global loss streak + 60d portfolio vol budget",
        note=(
            "Replace the discontinuous account-level loss-streak cliff with a continuous portfolio realized-vol "
            "entry budget. Existing positions are not forcibly deleveraged."
        ),
    )
    overrides = {
        **base.overrides,
        "streak_risk_multipliers": NO_STREAK_MULTIPLIERS,
        "enable_portfolio_volatility_budget": True,
        "portfolio_volatility_budget_lookback": VOL_LOOKBACK,
        "portfolio_volatility_budget_target_annual_vol": VOL_TARGET_ANNUAL,
        "portfolio_volatility_budget_min_scale": VOL_MIN_SCALE,
        "portfolio_volatility_budget_entry_contexts": VOL_CONTEXTS,
        "enable_portfolio_volatility_budget_deleverage": False,
    }
    return replace(base, capital=capital, overrides=overrides, profile="official_stage372_no_streak_vol_budget_stage710")


def _decision(summary: pd.DataFrame, comparison: pd.DataFrame, cost: pd.DataFrame, checks: pd.DataFrame) -> dict[str, Any]:
    hard_fail = checks[checks["status"].eq("fail")]["check_name"].astype(str).tolist()
    watch = checks[checks["status"].eq("watch")]["check_name"].astype(str).tolist()
    label = "no_streak_vol_budget_next_validation" if not hard_fail else "no_streak_vol_budget_not_promoted"
    return {
        "stage": "Stage424",
        "script_stage": "Stage710",
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
            "streak_risk_multipliers_before": "1.0,1.0,1.0,0.1",
            "streak_risk_multipliers_after": NO_STREAK_MULTIPLIERS,
            "enable_portfolio_volatility_budget": True,
            "portfolio_volatility_budget_lookback": VOL_LOOKBACK,
            "portfolio_volatility_budget_target_annual_vol": VOL_TARGET_ANNUAL,
            "portfolio_volatility_budget_min_scale": VOL_MIN_SCALE,
            "portfolio_volatility_budget_entry_contexts": VOL_CONTEXTS,
            "enable_portfolio_volatility_budget_deleverage": False,
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
        CANDIDATE_VARIANT: "C no streak + vol budget",
    }
    colors = {
        BASE_VARIANT: "#ea580c",
        CANDIDATE_VARIANT: "#0f766e",
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
        "# Stage424 / Script710 No Streak With Portfolio Vol Budget",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        f"- 当前 official live：`{s707.OFFICIAL_LIVE_VERSION}` / `{s707.OFFICIAL_LIVE_PROFILE_NAME}`",
        "- A：当前正式 Stage372/20w，保留全局连败 `1,1,1,0.1` 和原 `case1a` recovery sleeve。",
        "- C：关闭全局连败 cliff，改用 60日组合实现波动预算缩放新开仓/反手/换月重开/加仓，目标年化 `60%`，最低 `0.5` 倍，不强平已有仓位。",
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
        f"- watch_checks：`{', '.join(decision['watch_checks']) or '无'}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
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
    s707.main()


if __name__ == "__main__":
    main()
