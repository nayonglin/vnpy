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

MODEL_TAG = "stage745_quarter_risk_no_streak_multiperiod_v1"
OUTPUT_PREFIX = "qmt_roll_stage745_quarter_risk_no_streak_multiperiod"
LINE_ID = "futures_trend_quarter_risk_no_streak"

BASE_VARIANT = s707.BASE_VARIANT
CANDIDATE_VARIANT = "stage526_200k_force95_to80_r020_pc25_maxpos4_no_streak_no_recovery_stage745"

FORMAL_RISK_MULTIPLIER = 0.80
QUARTER_RISK_MULTIPLIER = FORMAL_RISK_MULTIPLIER * 0.25
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
        label="Stage745 quarter formal risk, no loss-streak throttle",
        risk_multiplier=QUARTER_RISK_MULTIPLIER,
        note=(
            "Official Stage372 signal/universe/margin shell, but single-trade risk is 0.25x the formal "
            "risk budget. Loss-streak multipliers and recovery sleeve are disabled."
        ),
    )
    overrides = {
        **base.overrides,
        "streak_risk_multipliers": NO_STREAK_MULTIPLIERS,
        "enable_streak_entry_structure_risk_recovery": False,
        "enable_recovery_sleeve": False,
    }
    return replace(base, capital=capital, overrides=overrides, profile="official_stage372_r020_no_streak_stage745")


def _check_rows(summary: pd.DataFrame, comparison: pd.DataFrame, cost: pd.DataFrame) -> pd.DataFrame:
    checks: list[dict[str, Any]] = []

    def add(name: str, status: str, value: float, threshold: str, comment: str) -> None:
        checks.append({"check_name": name, "status": status, "value": value, "threshold": threshold, "comment": comment})

    full = comparison[comparison["window_name"].eq("full_2020_20260430")].iloc[0]
    start_years = comparison[comparison["window_group"].eq("start_year")].copy()
    phases = comparison[comparison["window_group"].eq("phase")].copy()
    cand_summary = summary[summary["variant"].eq(CANDIDATE_VARIANT)].copy()
    cand_cost2 = cost[(cost["variant"].eq(CANDIDATE_VARIANT)) & (cost["cost_multiplier"].eq(2.0))].copy()

    add(
        "full_return_retention_ge20",
        "pass" if float(full["return_retention_pct"]) >= 20.0 else "fail",
        float(full["return_retention_pct"]),
        ">= 20%",
        "风险资金只有正式版0.25倍，收益保留低于20%说明资金效率明显不足。",
    )
    add(
        "full_return_retention_ge25_watch",
        "pass" if float(full["return_retention_pct"]) >= 25.0 else "watch",
        float(full["return_retention_pct"]),
        ">= 25% preferred",
        "粗略线性预期是保留约四分之一收益；低于此值只能算更保守口径。",
    )
    add(
        "full_dd30_pass",
        "pass" if float(full["candidate_max_dd_pct"]) >= -30.0 else "fail",
        float(full["candidate_max_dd_pct"]),
        ">= -30%",
        "降风险版本必须先兑现回撤压缩，否则没有研究价值。",
    )
    add(
        "full_dd_improves_by_10pp",
        "pass" if float(full["delta_max_dd_pct"]) >= 10.0 else "watch",
        float(full["delta_max_dd_pct"]),
        ">= +10pp",
        "低风险版本至少应显著改善全周期最大回撤。",
    )
    add(
        "full_sharpe_not_much_lower",
        "pass" if float(full["delta_sharpe"]) >= -0.25 else "fail",
        float(full["delta_sharpe"]),
        ">= -0.25",
        "收益降低可以接受，但风险调整后质量不能明显塌陷。",
    )
    add(
        "full_broker10_100_pass",
        "pass" if int(cand_summary[cand_summary["window_name"].eq("full_2020_20260430")]["broker10_100_pass"].iloc[0]) == 1 else "fail",
        float(full["candidate_max_broker10_margin_to_equity_pct"]),
        "<= 100%",
        "不能用看似低风险但保证金仍穿线的路径。",
    )
    add(
        "cost2_full_dd30_pass",
        "pass"
        if float(cand_cost2[cand_cost2["window_name"].eq("full_2020_20260430")]["max_dd_pct"].iloc[0]) >= -30.0
        else "fail",
        float(cand_cost2[cand_cost2["window_name"].eq("full_2020_20260430")]["max_dd_pct"].iloc[0]),
        "2x cost max DD >= -30%",
        "如果低风险口径在2x成本仍不能压住DD30，则没有防守意义。",
    )
    add(
        "start_years_dd30_all_pass",
        "pass" if int(cand_summary[cand_summary["window_group"].eq("start_year")]["dd30_pass"].min()) == 1 else "fail",
        float(cand_summary[cand_summary["window_group"].eq("start_year")]["max_dd_pct"].min()),
        "all start-year DD >= -30%",
        "逐年冷启动要看生存体验，而不是只看2020全周期。",
    )
    add(
        "start_years_min_return_positive_watch",
        "pass" if float(start_years["candidate_total_return_pct"].min()) > 0.0 else "watch",
        float(start_years["candidate_total_return_pct"].min()),
        "> 0 preferred",
        "短样本起点允许观察，但若大量负收益说明过度降风险牺牲了机会。",
    )
    add(
        "phase_dd30_all_pass",
        "pass" if int(cand_summary[cand_summary["window_group"].eq("phase")]["dd30_pass"].min()) == 1 else "fail",
        float(cand_summary[cand_summary["window_group"].eq("phase")]["max_dd_pct"].min()),
        "all phase DD >= -30%",
        "分段独立启动不能只靠某一段行情成立。",
    )
    add(
        "phase_min_return_positive_watch",
        "pass" if float(phases["candidate_total_return_pct"].min()) > 0.0 else "watch",
        float(phases["candidate_total_return_pct"].min()),
        "> 0 preferred",
        "低风险口径至少不能在完整市场阶段里普遍失效。",
    )
    return pd.DataFrame(checks)


def _decision(summary: pd.DataFrame, comparison: pd.DataFrame, cost: pd.DataFrame, checks: pd.DataFrame) -> dict[str, Any]:
    hard_fail = checks[checks["status"].eq("fail")]["check_name"].astype(str).tolist()
    watch = checks[checks["status"].eq("watch")]["check_name"].astype(str).tolist()
    label = (
        "quarter_risk_no_streak_low_risk_candidate_watch"
        if not hard_fail
        else "quarter_risk_no_streak_not_promoted"
    )
    return {
        "stage": "Stage434",
        "script_stage": "Stage745",
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
            "risk_multiplier_before": FORMAL_RISK_MULTIPLIER,
            "risk_multiplier_after": QUARTER_RISK_MULTIPLIER,
            "risk_multiplier_scale_to_formal": 0.25,
            "streak_risk_multipliers_before": "1.0,1.0,1.0,0.1",
            "streak_risk_multipliers_after": NO_STREAK_MULTIPLIERS,
            "enable_streak_entry_structure_risk_recovery_before": True,
            "enable_streak_entry_structure_risk_recovery_after": False,
            "enable_recovery_sleeve_before": True,
            "enable_recovery_sleeve_after": False,
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
    plot_data = curves[curves["window_name"].isin(["full_2020_20260430", "since_2023", "phase_2024_2025"])].copy()
    labels = {
        BASE_VARIANT: "A official",
        CANDIDATE_VARIANT: "C 0.25x risk no streak",
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
        "base_max_broker10_margin_to_equity_pct",
        "candidate_max_broker10_margin_to_equity_pct",
        "base_total_trade_count",
        "candidate_total_trade_count",
    ]
    lines = [
        "# Stage434 / Script745 Quarter Risk No Streak Multiperiod Validation",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        f"- 当前 official live：`{s707.OFFICIAL_LIVE_VERSION}` / `{s707.OFFICIAL_LIVE_PROFILE_NAME}`",
        "- A：当前正式 Stage372/20w，风险倍率 `0.80`，保留全局连败 `1,1,1,0.1` 与原 `case1a` recovery sleeve。",
        "- C：同信号、同品种池、同保证金强制减仓壳；风险倍率改为 `0.20`，即正式版风险资金的 `0.25` 倍；`streak_risk_multipliers=1,1,1,1`，关闭 `enable_streak_entry_structure_risk_recovery` 与 `enable_recovery_sleeve`。",
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
