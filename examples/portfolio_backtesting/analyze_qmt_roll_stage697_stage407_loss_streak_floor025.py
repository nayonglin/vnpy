from __future__ import annotations

from datetime import datetime
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

import analyze_qmt_roll_stage696_stage407_soft_streak_risk as s696


MODEL_TAG = "stage697_stage407_loss_streak_floor025_v1"
OUTPUT_PREFIX = "qmt_roll_stage697_stage407_loss_streak_floor025"
OFFICIAL_FLOOR_VARIANT = "stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4_loss_streak_floor025"
TARGET_VARIANT = (
    "stage526_200k_force95_to80_recovery_sleeve_r080_pc25_original_ai_plus_jd_ai_rerank_top9_"
    "maxpos5_loss_streak_floor025"
)
AI_STRATEGY = "stage697_original_ai_pool_plus_jd_probability_rerank_top9_entry_filter"
AI_SCORE_TYPE = "stage697_original_ai_pool_plus_jd_probability_rerank_top9"
AI_PRE_COVERAGE_SCORE_TYPE = "stage697_official_ai_pre_full_market_coverage"
LOSS_STREAK_FLOOR_MULTIPLIERS = "1.0,1.0,1.0,0.25"

_BASE_DECISION = s696._decision


def _reconfigure() -> None:
    s696.MODEL_TAG = MODEL_TAG
    s696.OUTPUT_PREFIX = OUTPUT_PREFIX
    s696.OFFICIAL_SOFT_VARIANT = OFFICIAL_FLOOR_VARIANT
    s696.TARGET_VARIANT = TARGET_VARIANT
    s696.AI_STRATEGY = AI_STRATEGY
    s696.AI_SCORE_TYPE = AI_SCORE_TYPE
    s696.AI_PRE_COVERAGE_SCORE_TYPE = AI_PRE_COVERAGE_SCORE_TYPE
    s696.SOFT_STREAK_MULTIPLIERS = LOSS_STREAK_FLOOR_MULTIPLIERS

    s696.GENERATED_DIR = s696.OUTPUT_DIR / "stage697_generated_inputs"
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


def _plot(daily: pd.DataFrame) -> None:
    if daily.empty:
        return
    data = daily.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data["label"] = data["variant"].map(
        {
            s696.BASE_VARIANT: "A Official floor 0.1",
            OFFICIAL_FLOOR_VARIANT: "D Official floor 0.25",
            s696.STAGE407_VARIANT: "B Stage407 floor 0.1",
            TARGET_VARIANT: "C Stage407 floor 0.25",
        }
    ).fillna(data["variant"])
    colors = {
        "A Official floor 0.1": "#ea580c",
        "D Official floor 0.25": "#a855f7",
        "B Stage407 floor 0.1": "#16a34a",
        "C Stage407 floor 0.25": "#2563eb",
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
    axes[0].set_title("Stage410 / Script697: loss-streak floor 0.1 vs 0.25")
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
    ax.set_title("Stage410 Equity Curves: loss-streak floor 0.1 vs 0.25")
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
    decision["stage"] = "Stage410"
    decision["script_stage"] = "Stage697"
    decision["model_tag"] = MODEL_TAG
    decision["official_soft"] = OFFICIAL_FLOOR_VARIANT
    decision["target"] = TARGET_VARIANT
    change = dict(decision.get("change", {}))
    change.update(
        {
            "candidate_hypothesis": (
                "Keep 0/1/2-loss risk unchanged and lift only the 3+ loss-streak floor from 0.1 to 0.25, "
                "so the strategy keeps a minimal right-tail participation budget after a bad streak."
            ),
            "streak_risk_multipliers_before": s696.BASE_STREAK_MULTIPLIERS,
            "streak_risk_multipliers_after": LOSS_STREAK_FLOOR_MULTIPLIERS,
        }
    )
    decision["change"] = change
    hard_fail = list(decision.get("hard_fail_checks", []))
    decision["decision"] = "stage407_loss_streak_floor025_not_promoted" if hard_fail else "stage407_loss_streak_floor025_watch"
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
        "# Stage410 / Script697 Stage407 Loss-Streak Floor 0.25",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{s696.LINE_ID}`",
        "- A：当前正式 Stage372/20w，正式 AI，`maxpos4`，连败倍率 `1,1,1,0.1`。",
        "- D：当前正式 Stage372/20w，仅把三连败后风险底线改为 `0.25`，即 `1,1,1,0.25`。",
        "- B：Stage407 基线，原正式 AI 池 + `jd.DCE` 参与 AI 重排 top9，`maxpos5`，连败倍率 `1,1,1,0.1`。",
        "- C：B 仅把三连败后风险底线改为 `0.25`，即 `1,1,1,0.25`。",
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
    _reconfigure()
    s696._plot = _plot
    s696._decision = _decision
    s696._write_report = _write_report
    s696.main()


if __name__ == "__main__":
    main()
