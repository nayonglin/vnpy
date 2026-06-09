from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

import analyze_qmt_roll_stage685_stage397_ma20_initial_stop_no_prev2day as s685
import analyze_qmt_roll_stage707_recovery_all_cases_multiperiod as s707
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage715_official_ma20_initial_stop_multiperiod_v1"
OUTPUT_PREFIX = "qmt_roll_stage715_official_ma20_initial_stop_multiperiod"
LINE_ID = "futures_trend_drawdown30_preserve_return"

BASE_VARIANT = s707.BASE_VARIANT
CANDIDATE_VARIANT = "stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4_ma20_initial_stop_stage715"
MA_STOP_WINDOW = 20

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
        label="Stage715 official MA20 initial stop sizing",
        note=(
            "Official Stage372 unchanged except entry-layer initial stop distance for sizing "
            "uses MA20 when it is on the valid trend side; official AI, streak multipliers, "
            "recovery sleeve and exits are unchanged."
        ),
    )
    overrides = {
        **base.overrides,
        "streak_risk_multipliers": "1.0,1.0,1.0,0.1",
    }
    return replace(
        base,
        capital=capital,
        overrides=overrides,
        profile="official_stage372_ma20_initial_stop_stage715",
    )


def _decision(summary: pd.DataFrame, comparison: pd.DataFrame, cost: pd.DataFrame, checks: pd.DataFrame) -> dict[str, Any]:
    hard_fail = checks[checks["status"].eq("fail")]["check_name"].astype(str).tolist()
    watch = checks[checks["status"].eq("watch")]["check_name"].astype(str).tolist()
    label = "official_ma20_initial_stop_next_validation" if not hard_fail else "official_ma20_initial_stop_not_promoted"
    return {
        "stage": "Stage429",
        "script_stage": "Stage715",
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
            "ai_pool_changed": False,
            "streak_risk_multipliers_before": "1.0,1.0,1.0,0.1",
            "streak_risk_multipliers_after": "1.0,1.0,1.0,0.1",
            "initial_stop_for_sizing_before": "official_entry_stop_price",
            "initial_stop_for_sizing_after": "ma20_when_valid_side_else_official_fallback",
            "ma_stop_window": MA_STOP_WINDOW,
            "prev2day_stop_changed": False,
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
        CANDIDATE_VARIANT: "C MA20 initial stop",
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
        "# Stage429 / Script715 Official MA20 Initial Stop Multiperiod Validation",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        f"- 当前 official live：`{s707.OFFICIAL_LIVE_VERSION}` / `{s707.OFFICIAL_LIVE_PROFILE_NAME}`",
        "- A：当前正式 Stage372/20w，官方初始止损手数计算。",
        "- C：只把初始止损手数计算改为 MA20 有效侧距离；AI、品种池、连败倍率、recovery sleeve、退出逻辑均不变。",
        f"- MA 窗口固定 `{MA_STOP_WINDOW}`，来自前序 Stage399 线索，本阶段不扫窗口。",
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

    original_entry_stop_price = QmtRollPortfolioStrategy._entry_stop_price
    original_run_independent_window = s707.s660._run_independent_window

    def _run_independent_window_with_candidate_patch(**kwargs: Any) -> tuple[pd.DataFrame, pd.DataFrame]:
        spec = kwargs.get("spec")
        use_ma20 = bool(spec is not None and spec.capital.variant == CANDIDATE_VARIANT)
        QmtRollPortfolioStrategy._entry_stop_price = (
            s685._ma20_initial_stop_price if use_ma20 else original_entry_stop_price
        )
        try:
            return original_run_independent_window(**kwargs)
        finally:
            QmtRollPortfolioStrategy._entry_stop_price = original_entry_stop_price

    try:
        s707.s660._run_independent_window = _run_independent_window_with_candidate_patch
        s707.main()
    finally:
        s707.s660._run_independent_window = original_run_independent_window
        QmtRollPortfolioStrategy._entry_stop_price = original_entry_stop_price


if __name__ == "__main__":
    main()
