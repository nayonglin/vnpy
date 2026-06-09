from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

import analyze_qmt_roll_stage707_recovery_all_cases_multiperiod as s707
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage712_loss_streak_equity_ma_gate_multiperiod_v1"
OUTPUT_PREFIX = "qmt_roll_stage712_loss_streak_equity_ma_gate_multiperiod"
LINE_ID = "futures_trend_drawdown30_preserve_return"

BASE_VARIANT = s707.BASE_VARIANT
CANDIDATE_VARIANT = (
    "stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4_"
    "loss_streak_equity_ma200_gate_stage712"
)

EQUITY_MA_MODE = "stage712_loss_streak_equity_ma_gate"
EQUITY_MA_LOOKBACK = 200
BASE_STREAK_MULTIPLIERS = "1.0,1.0,1.0,0.1"
GATE_AUDIT: dict[str, float] = {
    "equity_ma_mode_calls": 0.0,
    "severe_tier_calls": 0.0,
    "insufficient_history_keep_calls": 0.0,
    "below_ma_keep_calls": 0.0,
    "above_ma_bypass_calls": 0.0,
    "min_equity_to_ma_ratio": 999.0,
    "max_equity_to_ma_ratio": 0.0,
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
_ORIGINAL_ON_BARS = QmtRollPortfolioStrategy.on_bars


def _equity_ma_mode_enabled(strategy: QmtRollPortfolioStrategy) -> bool:
    return str(getattr(strategy, "streak_profit_recovery_mode", "") or "").strip() == EQUITY_MA_MODE


def _current_equity(strategy: QmtRollPortfolioStrategy) -> float:
    for value in (
        getattr(strategy, "estimated_equity", 0.0),
        getattr(strategy, "settled_balance", 0.0),
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
    if not _equity_ma_mode_enabled(strategy):
        return raw

    GATE_AUDIT["equity_ma_mode_calls"] += 1.0
    loss_streak = int(getattr(strategy, "loss_streak", 0) or 0)
    if loss_streak < 3 or raw > 0.1000001:
        return raw

    GATE_AUDIT["severe_tier_calls"] += 1.0
    history = list(getattr(strategy, "_stage712_equity_history", []) or [])
    if len(history) < EQUITY_MA_LOOKBACK:
        GATE_AUDIT["insufficient_history_keep_calls"] += 1.0
        return raw

    window = [float(value) for value in history[-EQUITY_MA_LOOKBACK:] if float(value) > 0.0]
    if len(window) < EQUITY_MA_LOOKBACK:
        GATE_AUDIT["insufficient_history_keep_calls"] += 1.0
        return raw

    ma_value = sum(window) / float(EQUITY_MA_LOOKBACK)
    equity = _current_equity(strategy)
    ratio = equity / ma_value if ma_value > 0.0 else 999.0
    GATE_AUDIT["min_equity_to_ma_ratio"] = min(GATE_AUDIT["min_equity_to_ma_ratio"], ratio)
    GATE_AUDIT["max_equity_to_ma_ratio"] = max(GATE_AUDIT["max_equity_to_ma_ratio"], ratio)

    if equity < ma_value:
        GATE_AUDIT["below_ma_keep_calls"] += 1.0
        return raw

    GATE_AUDIT["above_ma_bypass_calls"] += 1.0
    return 1.0


def _patched_on_bars(strategy: QmtRollPortfolioStrategy, bars: dict[str, Any]) -> None:
    _ORIGINAL_ON_BARS(strategy, bars)
    if not _equity_ma_mode_enabled(strategy):
        return
    current_bar_date = getattr(strategy, "current_bar_date", None)
    if current_bar_date is None:
        return
    current_bar_date = pd.Timestamp(current_bar_date).normalize()
    last_date = getattr(strategy, "_stage712_last_equity_history_date", None)
    if last_date is not None and pd.Timestamp(last_date).normalize() == current_bar_date:
        return

    history = list(getattr(strategy, "_stage712_equity_history", []) or [])
    history.append(float(_current_equity(strategy)))
    setattr(strategy, "_stage712_equity_history", history)
    setattr(strategy, "_stage712_last_equity_history_date", current_bar_date)


def _candidate_spec(metadata: dict[str, Any]) -> s707.s653.ForcedVariant:
    base = s707.s660._official_spec(metadata)
    capital = replace(
        base.capital,
        variant=CANDIDATE_VARIANT,
        label="Stage712 loss-streak equity MA200 gate",
        note=(
            "Keep the original loss-streak table, but only activate the severe 0.1 tier when account equity "
            "is below its prior 200-trading-day equity moving average."
        ),
    )
    overrides = {
        **base.overrides,
        "streak_risk_multipliers": BASE_STREAK_MULTIPLIERS,
        "streak_profit_recovery_mode": EQUITY_MA_MODE,
    }
    return replace(base, capital=capital, overrides=overrides, profile="official_stage372_loss_streak_equity_ma_gate_stage712")


def _decision(summary: pd.DataFrame, comparison: pd.DataFrame, cost: pd.DataFrame, checks: pd.DataFrame) -> dict[str, Any]:
    hard_fail = checks[checks["status"].eq("fail")]["check_name"].astype(str).tolist()
    watch = checks[checks["status"].eq("watch")]["check_name"].astype(str).tolist()
    label = "loss_streak_equity_ma_gate_next_validation" if not hard_fail else "loss_streak_equity_ma_gate_not_promoted"
    return {
        "stage": "Stage426",
        "script_stage": "Stage712",
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
            "equity_ma_mode": EQUITY_MA_MODE,
            "equity_ma_lookback_trading_days": EQUITY_MA_LOOKBACK,
            "history_semantics": "prior-day strategy equity history; insufficient history keeps official 0.1 behavior",
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
        CANDIDATE_VARIANT: "C equity-MA-gated streak",
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
        "# Stage426 / Script712 Loss-Streak Equity MA Gate",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        f"- 当前 official live：`{s707.OFFICIAL_LIVE_VERSION}` / `{s707.OFFICIAL_LIVE_PROFILE_NAME}`",
        "- A：当前正式 Stage372/20w，原始 `1,1,1,0.1` 连败风险表。",
        "- C：连败表不变，但三连败后的严重 `0.1` 只有在账户权益低于前 200 个交易日权益均线时生效。",
        "- 权益历史只使用上一交易日及以前的策略权益；历史不足 200 天时保持正式 `0.1` 行为。",
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
        "## Gate Audit",
        "",
        s707._md_table(pd.DataFrame([decision["gate_audit"]])),
        "",
        "## Decision",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- hard_fail_checks：`{', '.join(decision['hard_fail_checks']) or '无'}`",
        f"- watch_checks：`{', '.join(decision['watch_checks']) or '无'}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    for key in GATE_AUDIT:
        GATE_AUDIT[key] = 999.0 if key == "min_equity_to_ma_ratio" else 0.0

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
    QmtRollPortfolioStrategy.on_bars = _patched_on_bars
    try:
        s707.main()
    finally:
        QmtRollPortfolioStrategy._current_streak_multiplier = _ORIGINAL_CURRENT_STREAK_MULTIPLIER
        QmtRollPortfolioStrategy.on_bars = _ORIGINAL_ON_BARS


if __name__ == "__main__":
    main()
