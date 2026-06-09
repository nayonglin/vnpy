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

MODEL_TAG = "stage724_directional_edge60_exemption_multiperiod_v1"
OUTPUT_PREFIX = "qmt_roll_stage724_directional_edge60_exemption_multiperiod"
LINE_ID = "futures_trend_winner_trade_forensics"

BASE_VARIANT = s707.BASE_VARIANT
CANDIDATE_VARIANT = (
    "stage526_200k_force95_to80_directional_edge60_normal_risk_exemption_stage724"
)
RECOVERY_SIGNALS = "long_case1a,long_case2,long_case3,short_case1a,short_case2,short_case3"
DIRECTIONAL_EDGE_PERIOD = 60
LONG_CLOSE_POSITION_MIN = 0.80
SHORT_CLOSE_POSITION_MAX = 0.20

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
        label="Stage724 directional-edge60 normal-risk exemption",
        note=(
            "Official Stage372 unchanged except the 0.1-floor clean-book recovery lift is allowed for all native "
            "entry cases only when close remains near the directional 60-day range edge. Recovery sleeve is disabled "
            "for the candidate so a passed high-quality setup gets normal risk sizing rather than a one-lot scout."
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
        "enable_recovery_sleeve": False,
        "streak_risk_multipliers": "1.0,1.0,1.0,0.1",
    }
    return replace(
        base,
        capital=capital,
        overrides=overrides,
        profile="official_stage372_directional_edge60_normal_risk_exemption_stage724",
    )


def _check_rows(summary: pd.DataFrame, comparison: pd.DataFrame, cost: pd.DataFrame) -> pd.DataFrame:
    checks: list[dict[str, Any]] = []

    def add(name: str, status: str, value: float, threshold: str, comment: str) -> None:
        checks.append({"check_name": name, "status": status, "value": value, "threshold": threshold, "comment": comment})

    full = comparison[comparison["window_name"].eq("full_2020_20260430")].iloc[0]
    start_years = comparison[comparison["window_group"].eq("start_year")].copy()
    phases = comparison[comparison["window_group"].eq("phase")].copy()
    candidate_summary = summary[summary["variant"].eq(CANDIDATE_VARIANT)].copy()
    base_summary = summary[summary["variant"].eq(BASE_VARIANT)].copy()
    candidate_cost2 = cost[(cost["variant"].eq(CANDIDATE_VARIANT)) & (cost["cost_multiplier"].eq(2.0))].copy()
    base_cost2 = cost[(cost["variant"].eq(BASE_VARIANT)) & (cost["cost_multiplier"].eq(2.0))].copy()
    full_candidate_cost2 = candidate_cost2[candidate_cost2["window_name"].eq("full_2020_20260430")].iloc[0]
    full_base_cost2 = base_cost2[base_cost2["window_name"].eq("full_2020_20260430")].iloc[0]
    full_candidate = candidate_summary[candidate_summary["window_name"].eq("full_2020_20260430")].iloc[0]
    full_base = base_summary[base_summary["window_name"].eq("full_2020_20260430")].iloc[0]

    add(
        "full_return_not_lower",
        "pass" if float(full["return_retention_pct"]) >= 100.0 else "fail",
        float(full["return_retention_pct"]),
        ">= 100%",
        "高质量豁免如果恢复正常仓位，至少不能牺牲全周期收益。",
    )
    add(
        "full_dd_not_worse_by_3pp",
        "pass" if float(full["delta_max_dd_pct"]) >= -3.0 else "fail",
        float(full["delta_max_dd_pct"]),
        ">= -3pp",
        "正常仓位豁免不能明显加深正式版全周期回撤。",
    )
    add(
        "full_sharpe_not_worse_by_005",
        "pass" if float(full["delta_sharpe"]) >= -0.05 else "fail",
        float(full["delta_sharpe"]),
        ">= -0.05",
        "收益改善不能靠明显降低单位风险质量换来。",
    )
    add(
        "full_slippage_growth_le40pct",
        "pass"
        if float(full["candidate_total_slippage"]) <= float(full["base_total_slippage"]) * 1.40
        else "fail",
        float(full["candidate_total_slippage"] / max(float(full["base_total_slippage"]), 1.0) * 100.0),
        "<= 140% of A",
        "豁免不能把交易成本放大成主矛盾。",
    )
    add(
        "full_trade_count_growth_le40pct",
        "pass"
        if float(full["candidate_total_trade_count"]) <= float(full["base_total_trade_count"]) * 1.40
        else "fail",
        float(full["candidate_total_trade_count"] / max(float(full["base_total_trade_count"]), 1.0) * 100.0),
        "<= 140% of A",
        "机会增加必须受控，不能变成全市场多交易。",
    )
    add(
        "cost2_full_dd_not_worse_by_3pp",
        "pass"
        if float(full_candidate_cost2["max_dd_pct"]) - float(full_base_cost2["max_dd_pct"]) >= -3.0
        else "fail",
        float(full_candidate_cost2["max_dd_pct"]) - float(full_base_cost2["max_dd_pct"]),
        ">= -3pp vs A",
        "成本翻倍下不能明显更脆。",
    )
    add(
        "broker10_100_pass",
        "pass" if int(full_candidate["broker10_100_pass"]) == 1 else "fail",
        float(full_candidate["max_broker10_margin_to_equity_pct"]),
        "<= 100%",
        "正常仓位豁免不能穿 broker10 保证金约束。",
    )
    add(
        "start_years_min_retention_ge70",
        "pass" if float(start_years["return_retention_pct"].min()) >= 70.0 else "fail",
        float(start_years["return_retention_pct"].min()),
        ">= 70%",
        "不能只救2025红框或单一全周期起点。",
    )
    add(
        "start_years_dd_not_worse_by_5pp",
        "pass" if float(start_years["delta_max_dd_pct"].min()) >= -5.0 else "fail",
        float(start_years["delta_max_dd_pct"].min()),
        ">= -5pp",
        "任一起始年份不能显著打穿防守路径。",
    )
    add(
        "phase_min_retention_ge65",
        "pass" if float(phases["return_retention_pct"].min()) >= 65.0 else "fail",
        float(phases["return_retention_pct"].min()),
        ">= 65%",
        "分段独立启动不能只有趋势富集期好看。",
    )
    add(
        "phase_dd_not_worse_by_5pp",
        "pass" if float(phases["delta_max_dd_pct"].min()) >= -5.0 else "fail",
        float(phases["delta_max_dd_pct"].min()),
        ">= -5pp",
        "弱阶段不能明显恶化。",
    )
    add(
        "account_survival_pass",
        "pass" if int(full_candidate["account_survival_pass"]) == 1 and int(full_base["account_survival_pass"]) == 1 else "fail",
        float(full_candidate["min_equity"]),
        "> 0",
        "恢复正常仓位不能带来账户破产路径。",
    )
    return pd.DataFrame(checks)


def _decision(summary: pd.DataFrame, comparison: pd.DataFrame, cost: pd.DataFrame, checks: pd.DataFrame) -> dict[str, Any]:
    hard_fail = checks[checks["status"].eq("fail")]["check_name"].astype(str).tolist()
    label = (
        "directional_edge60_exemption_next_validation"
        if not hard_fail
        else "directional_edge60_exemption_not_promoted"
    )
    return {
        "stage": "Stage724",
        "script_stage": "Stage724",
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
        CANDIDATE_VARIANT: "C edge60 normal risk",
    }
    colors = {
        BASE_VARIANT: "#ea580c",
        CANDIDATE_VARIANT: "#16a34a",
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
        "# Stage724 Directional Edge60 Normal-Risk Exemption Multiperiod Validation",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        f"- 当前 official live：`{s707.OFFICIAL_LIVE_VERSION}` / `{s707.OFFICIAL_LIVE_PROFILE_NAME}`",
        "- A：当前正式 Stage372/20w，`case1a` 恢复规则 + one-lot recovery sleeve。",
        "- C：保持 `streak_risk_multipliers=1,1,1,0.1`，把 clean-book recovery lift 扩到所有原生趋势入场 case，但要求 `directional_edge60`；C 关闭 recovery sleeve，使通过条件的机会恢复正常风险 sizing。",
        f"- directional_edge60：long close position >= `{LONG_CLOSE_POSITION_MIN:g}`；short close position <= `{SHORT_CLOSE_POSITION_MAX:g}`；lookback `{DIRECTIONAL_EDGE_PERIOD}`。",
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
