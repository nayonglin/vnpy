from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

import analyze_qmt_roll_stage745_quarter_risk_no_streak_multiperiod as s745


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage746_half_risk_no_streak_multiperiod_v1"
OUTPUT_PREFIX = "qmt_roll_stage746_half_risk_no_streak_multiperiod"
LINE_ID = "futures_trend_quarter_risk_no_streak"

BASE_VARIANT = s745.BASE_VARIANT
CANDIDATE_VARIANT = "stage526_200k_force95_to80_r040_pc25_maxpos4_no_streak_no_recovery_stage746"

FORMAL_RISK_MULTIPLIER = 0.80
HALF_FORMAL_RISK_MULTIPLIER = FORMAL_RISK_MULTIPLIER * 0.50
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


def _candidate_spec(metadata: dict[str, Any]) -> s745.s707.s653.ForcedVariant:
    base = s745.s707.s660._official_spec(metadata)
    capital = replace(
        base.capital,
        variant=CANDIDATE_VARIANT,
        label="Stage746 half formal risk, no loss-streak throttle",
        risk_multiplier=HALF_FORMAL_RISK_MULTIPLIER,
        note=(
            "Official Stage372 signal/universe/margin shell, but single-trade risk is 0.50x the formal "
            "risk budget. Loss-streak multipliers and recovery sleeve are disabled."
        ),
    )
    overrides = {
        **base.overrides,
        "streak_risk_multipliers": NO_STREAK_MULTIPLIERS,
        "enable_streak_entry_structure_risk_recovery": False,
        "enable_recovery_sleeve": False,
    }
    return replace(base, capital=capital, overrides=overrides, profile="official_stage372_r040_no_streak_stage746")


def _check_rows(summary: pd.DataFrame, comparison: pd.DataFrame, cost: pd.DataFrame) -> pd.DataFrame:
    checks: list[dict[str, Any]] = []

    def add(name: str, status: str, value: float, threshold: str, comment: str) -> None:
        checks.append({"check_name": name, "status": status, "value": value, "threshold": threshold, "comment": comment})

    full = comparison[comparison["window_name"].eq("full_2020_20260430")].iloc[0]
    start_years = comparison[comparison["window_group"].eq("start_year")].copy()
    phases = comparison[comparison["window_group"].eq("phase")].copy()
    cand_summary = summary[summary["variant"].eq(CANDIDATE_VARIANT)].copy()
    cand_cost2 = cost[(cost["variant"].eq(CANDIDATE_VARIANT)) & (cost["cost_multiplier"].eq(2.0))].copy()
    full_summary = cand_summary[cand_summary["window_name"].eq("full_2020_20260430")].iloc[0]
    full_cost2 = cand_cost2[cand_cost2["window_name"].eq("full_2020_20260430")].iloc[0]

    add(
        "full_return_retention_ge35",
        "pass" if float(full["return_retention_pct"]) >= 35.0 else "fail",
        float(full["return_retention_pct"]),
        ">= 35%",
        "风险资金是正式版0.5倍，收益保留低于35%说明资金效率仍明显不足。",
    )
    add(
        "full_return_retention_ge50_watch",
        "pass" if float(full["return_retention_pct"]) >= 50.0 else "watch",
        float(full["return_retention_pct"]),
        ">= 50% preferred",
        "粗略线性预期是保留约一半收益；低于此值只能算降风险壳。",
    )
    add(
        "full_dd30_pass",
        "pass" if float(full["candidate_max_dd_pct"]) >= -30.0 else "fail",
        float(full["candidate_max_dd_pct"]),
        ">= -30%",
        "本线核心仍是低回撤体验，半风险不能重新打穿DD30。",
    )
    add(
        "full_sharpe_not_much_lower",
        "pass" if float(full["delta_sharpe"]) >= -0.25 else "fail",
        float(full["delta_sharpe"]),
        ">= -0.25",
        "收益降低时风险调整后质量不能明显塌陷。",
    )
    add(
        "full_broker10_100_pass",
        "pass" if int(full_summary["broker10_100_pass"]) == 1 else "fail",
        float(full["candidate_max_broker10_margin_to_equity_pct"]),
        "<= 100%",
        "不能用更危险保证金路径换收益。",
    )
    add(
        "cost2_full_dd40_pass",
        "pass" if int(full_cost2["deployable_pass"]) == 1 else "fail",
        float(full_cost2["max_dd_pct"]),
        "2x cost deployable",
        "2x成本压力下至少不能打穿DD40或broker100。",
    )
    add(
        "start_years_dd40_all_pass",
        "pass" if int(cand_summary[cand_summary["window_group"].eq("start_year")]["dd40_pass"].min()) == 1 else "fail",
        float(cand_summary[cand_summary["window_group"].eq("start_year")]["max_dd_pct"].min()),
        "all start-year DD >= -40%",
        "逐年冷启动必须先过生存边界。",
    )
    add(
        "start_years_min_return_positive_watch",
        "pass" if float(start_years["candidate_total_return_pct"].min()) > 0.0 else "watch",
        float(start_years["candidate_total_return_pct"].min()),
        "> 0 preferred",
        "短样本起点允许观察，但负收益说明半风险也不能稳定替代正式路径。",
    )
    add(
        "phase_dd40_all_pass",
        "pass" if int(cand_summary[cand_summary["window_group"].eq("phase")]["dd40_pass"].min()) == 1 else "fail",
        float(cand_summary[cand_summary["window_group"].eq("phase")]["max_dd_pct"].min()),
        "all phase DD >= -40%",
        "分段独立启动不能破生存边界。",
    )
    add(
        "phase_min_return_positive_watch",
        "pass" if float(phases["candidate_total_return_pct"].min()) > 0.0 else "watch",
        float(phases["candidate_total_return_pct"].min()),
        "> 0 preferred",
        "完整市场阶段最好不出现负收益。",
    )
    return pd.DataFrame(checks)


def _decision(summary: pd.DataFrame, comparison: pd.DataFrame, cost: pd.DataFrame, checks: pd.DataFrame) -> dict[str, Any]:
    hard_fail = checks[checks["status"].eq("fail")]["check_name"].astype(str).tolist()
    watch = checks[checks["status"].eq("watch")]["check_name"].astype(str).tolist()
    label = "half_risk_no_streak_candidate_watch" if not hard_fail else "half_risk_no_streak_not_promoted"
    return {
        "stage": "Stage435",
        "script_stage": "Stage746",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "official_live_version": s745.s707.OFFICIAL_LIVE_VERSION,
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
            "risk_multiplier_after": HALF_FORMAL_RISK_MULTIPLIER,
            "risk_multiplier_scale_to_formal": 0.50,
            "previous_stage745_risk_multiplier": s745.QUARTER_RISK_MULTIPLIER,
            "scale_to_stage745_candidate": 2.0,
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
        CANDIDATE_VARIANT: "C 0.5x risk no streak",
    }
    colors = {
        BASE_VARIANT: "#ea580c",
        CANDIDATE_VARIANT: "#2563eb",
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
        ax.axhline(s745.s707.OFFICIAL_LIVE_CAPITAL, color="#94a3b8", linestyle="--", linewidth=0.8)
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
        "# Stage435 / Script746 Half Risk No Streak Multiperiod Validation",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        f"- 当前 official live：`{s745.s707.OFFICIAL_LIVE_VERSION}` / `{s745.s707.OFFICIAL_LIVE_PROFILE_NAME}`",
        "- A：当前正式 Stage372/20w，风险倍率 `0.80`，保留全局连败 `1,1,1,0.1` 与原 `case1a` recovery sleeve。",
        "- C：同信号、同品种池、同保证金强制减仓壳；风险倍率改为 `0.40`，即正式版风险资金的 `0.50` 倍、Stage745 C 的 `2` 倍；`streak_risk_multipliers=1,1,1,1`，关闭 `enable_streak_entry_structure_risk_recovery` 与 `enable_recovery_sleeve`。",
        "- 不修改正式配置、不连接 CTP、不调用下单。",
        "",
        "## Checks",
        "",
        s745.s707._md_table(checks),
        "",
        "## Comparison",
        "",
        s745.s707._md_table(comparison[key_cols], max_rows=40),
        "",
        "## Summary",
        "",
        s745.s707._md_table(summary, max_rows=80),
        "",
        "## Cost Stress",
        "",
        s745.s707._md_table(cost, max_rows=120),
        "",
        "## Annual Full Path",
        "",
        s745.s707._md_table(annual, max_rows=80),
        "",
        "## Decision",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- hard_fail_checks：`{', '.join(decision['hard_fail_checks']) or '无'}`",
        f"- watch_checks：`{', '.join(decision['watch_checks']) or '无'}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    s745.s707.MODEL_TAG = MODEL_TAG
    s745.s707.OUTPUT_PREFIX = OUTPUT_PREFIX
    s745.s707.LINE_ID = LINE_ID
    s745.s707.CANDIDATE_VARIANT = CANDIDATE_VARIANT
    s745.s707.SUMMARY_PATH = SUMMARY_PATH
    s745.s707.COST_PATH = COST_PATH
    s745.s707.COMPARISON_PATH = COMPARISON_PATH
    s745.s707.CURVES_PATH = CURVES_PATH
    s745.s707.ANNUAL_PATH = ANNUAL_PATH
    s745.s707.MONTHLY_PATH = MONTHLY_PATH
    s745.s707.CHECKS_PATH = CHECKS_PATH
    s745.s707.DECISION_PATH = DECISION_PATH
    s745.s707.REPORT_PATH = REPORT_PATH
    s745.s707.CHART_PATH = CHART_PATH
    s745.s707._candidate_spec = _candidate_spec
    s745.s707._check_rows = _check_rows
    s745.s707._decision = _decision
    s745.s707._plot = _plot
    s745.s707._write_report = _write_report
    s745.s707.main()


if __name__ == "__main__":
    main()
