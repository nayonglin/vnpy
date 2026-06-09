from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

import analyze_qmt_roll_stage666_stage372_500k_risk005_ag_ab as s666
import analyze_qmt_roll_stage680_stage372_500k_trade_risk002_no_ai_plus25_jd_v_short_cases123 as s680
import analyze_qmt_roll_stage681_stage393_pvc_trade_count_attribution as s681
import analyze_qmt_roll_stage682_stage393_c2_no_loss_streak as s682
import analyze_qmt_roll_stage683_stage395_no_loss_streak_trade_risk005 as s683
import analyze_qmt_roll_stage684_stage395_no_loss_streak_trade_risk001 as s684
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
MODEL_TAG = "stage685_stage397_ma20_initial_stop_no_prev2day_v1"
OUTPUT_PREFIX = "qmt_roll_stage685_stage397_ma20_initial_stop_no_prev2day"

TARGET_TRADE_RISK_RATIO = 0.01
NO_STREAK_MULTIPLIERS = "1.0,1.0,1.0,1.0"
MA_STOP_WINDOW = 20
BASE_STAGE397_VARIANT = s684.TARGET_VARIANT
BASE_STAGE396_VARIANT = s683.TARGET_VARIANT
BASE_STAGE393_VARIANT = s682.BASELINE_VARIANT
TARGET_VARIANT = "stage372_500k_trade_risk001_no_ai_plus25_jd_v_short_cases123_no_loss_streak_ma20stop_no_prev2day_maxpos25"
TARGET_RUN_NAME = "stage398_c2_plus25_pvc_no_loss_streak_risk001_ma20stop_no_prev2day"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
ANNUAL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_{MODEL_TAG}.csv"
MONTHLY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_monthly_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
PRODUCT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_{MODEL_TAG}.csv"
CANDIDATE_STATUS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_candidate_status_{MODEL_TAG}.csv"
CANDIDATE_PRODUCT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_candidate_product_{MODEL_TAG}.csv"
SIZING_LIMIT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_sizing_limit_{MODEL_TAG}.csv"
RISK_BREAKDOWN_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_risk_breakdown_{MODEL_TAG}.csv"
STOP_DISTANCE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stop_distance_{MODEL_TAG}.csv"
POSITIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_positions_{MODEL_TAG}.csv"
CANDIDATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_candidates_{MODEL_TAG}.csv"
RISKS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_risk_{MODEL_TAG}.csv"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

_ORIGINAL_ENTRY_STOP_PRICE = QmtRollPortfolioStrategy._entry_stop_price


def _json_safe(value: Any) -> Any:
    return s681._json_safe(value)


def _ma20_initial_stop_price(
    self: QmtRollPortfolioStrategy,
    direction: str,
    bar: Any,
    history: pd.DataFrame,
    use_day_extreme: bool,
) -> float:
    fallback = _ORIGINAL_ENTRY_STOP_PRICE(self, direction, bar, history, use_day_extreme)
    if history is None or history.empty or "close" not in history.columns:
        return fallback
    closes = pd.to_numeric(history["close"], errors="coerce")
    closes = closes[closes.gt(0)].dropna()
    if len(closes) < MA_STOP_WINDOW:
        return fallback
    ma20 = float(closes.tail(MA_STOP_WINDOW).mean())
    close_price = float(bar.close_price)
    if not pd.notna(ma20) or ma20 <= 0 or close_price <= 0:
        return fallback
    if direction == "long" and ma20 < close_price:
        return ma20
    if direction == "short" and ma20 > close_price:
        return ma20
    return fallback


def _build_target_spec() -> tuple[Any, dict[str, Any]]:
    spec, metadata = s684._build_target_spec()
    capital = replace(
        spec.capital,
        variant=TARGET_VARIANT,
        label="Stage398 C2 plus25 PVC risk 1% MA20 initial stop no prev2day",
        note=(
            "Stage685: continue Stage397 risk1/no-loss-streak branch; use MA20 as the "
            "initial stop for sizing/entry layer when it is on the valid side, and disable "
            "prev2day stop exits."
        ),
    )
    overrides = {
        **spec.overrides,
        "enable_prev2day_stop": False,
        "enable_profit_lock_trend_relaxed_prev2day_stop": False,
        "streak_risk_multipliers": NO_STREAK_MULTIPLIERS,
    }
    return replace(spec, capital=capital, overrides=overrides, profile=TARGET_VARIANT), metadata


def _comparison(target_summary: dict[str, Any], target_cost: pd.DataFrame) -> pd.DataFrame:
    baselines = [
        (
            "stage397_risk001_default_stop_prev2day",
            s684._load_full_row(s684.SUMMARY_PATH, BASE_STAGE397_VARIANT),
            s684._load_cost_rows(s684.COST_PATH, BASE_STAGE397_VARIANT),
        ),
        (
            "stage396_risk0005_default_stop_prev2day",
            s684._load_full_row(s683.SUMMARY_PATH, BASE_STAGE396_VARIANT),
            s684._load_cost_rows(s683.COST_PATH, BASE_STAGE396_VARIANT),
        ),
        (
            "stage393_c2",
            s684._load_full_row(s682.BASELINE_SUMMARY_PATH, BASE_STAGE393_VARIANT),
            s684._load_cost_rows(s682.BASELINE_COST_PATH, BASE_STAGE393_VARIANT),
        ),
    ]
    target_cost_lookup = {str(float(row["cost_multiplier"])): row.to_dict() for _, row in target_cost.iterrows()}
    metrics = [
        ("rebased_end_equity", "end_equity"),
        ("rebased_total_return_pct", "return_pct"),
        ("rebased_max_dd_pct", "max_dd_pct"),
        ("rebased_sharpe", "sharpe"),
        ("total_slippage", "slippage"),
        ("total_trade_count", "trade_count"),
        ("nonzero_daily_win_rate_pct", "win_rate_pct"),
        ("max_broker10_margin_to_rebased_equity_pct", "max_margin_pct"),
        ("p95_broker10_margin_to_rebased_equity_pct", "p95_margin_pct"),
    ]
    rows: list[dict[str, Any]] = []
    for baseline_name, baseline, baseline_cost in baselines:
        for source_field, metric in metrics:
            baseline_value = float(baseline[source_field])
            target_value = float(target_summary[source_field])
            rows.append(
                {
                    "baseline": baseline_name,
                    "metric": metric,
                    "baseline_value": baseline_value,
                    "target_value": target_value,
                    "delta": target_value - baseline_value,
                }
            )
        for multiplier in ("2.0", "3.0"):
            if multiplier not in baseline_cost or multiplier not in target_cost_lookup:
                continue
            baseline_dd = float(baseline_cost[multiplier]["max_dd_pct"])
            target_dd = float(target_cost_lookup[multiplier]["max_dd_pct"])
            baseline_equity = float(baseline_cost[multiplier]["end_equity"])
            target_equity = float(target_cost_lookup[multiplier]["end_equity"])
            rows.append(
                {
                    "baseline": baseline_name,
                    "metric": f"{multiplier}x_cost_max_dd_pct",
                    "baseline_value": baseline_dd,
                    "target_value": target_dd,
                    "delta": target_dd - baseline_dd,
                }
            )
            rows.append(
                {
                    "baseline": baseline_name,
                    "metric": f"{multiplier}x_cost_end_equity",
                    "baseline_value": baseline_equity,
                    "target_value": target_equity,
                    "delta": target_equity - baseline_equity,
                }
            )
    return pd.DataFrame(rows)


def _stop_distance_summary(risks: pd.DataFrame) -> pd.DataFrame:
    if risks.empty:
        return pd.DataFrame()
    data = risks.copy()
    for column in [
        "stop_distance",
        "risk_per_contract",
        "actual_risk_amount",
        "margin_per_contract",
        "volume",
        "selected_volume",
    ]:
        data[column] = pd.to_numeric(data.get(column, 0.0), errors="coerce").fillna(0.0)
    rows = []
    for scope, frame in [("all_entry_risk", data), ("opened", data[data["selected_volume"].gt(0)])]:
        if frame.empty:
            rows.append({"scope": scope, "count": 0})
            continue
        rows.append(
            {
                "scope": scope,
                "count": int(len(frame)),
                "median_stop_distance": float(frame["stop_distance"].median()),
                "median_risk_per_contract": float(frame["risk_per_contract"].median()),
                "median_actual_risk_amount": float(frame["actual_risk_amount"].median()),
                "median_margin_per_contract": float(frame["margin_per_contract"].median()),
                "median_selected_volume": float(frame["selected_volume"].median()),
                "p95_risk_per_contract": float(frame["risk_per_contract"].quantile(0.95)),
            }
        )
    return pd.DataFrame(rows)


def _plot_curve(curve: pd.DataFrame, summary_row: dict[str, Any]) -> None:
    full = curve[curve["window_name"].astype(str).eq("full_2020_20260430")].copy()
    if full.empty:
        return
    full["date"] = pd.to_datetime(full["date"], errors="coerce")
    full.sort_values("date", inplace=True)
    fig, axes = plt.subplots(2, 1, figsize=(13, 7.5), sharex=True, gridspec_kw={"height_ratios": [2, 1]})
    axes[0].plot(full["date"], full["rebased_equity"], color="#0f766e", linewidth=1.4)
    axes[0].axhline(500_000, color="#64748b", linewidth=0.9, linestyle="--", alpha=0.8)
    axes[0].set_title(
        "Stage398 risk 1% MA20 stop sizing, no prev2day "
        f"(end {float(summary_row['rebased_end_equity']):,.0f}, "
        f"DD {float(summary_row['rebased_max_dd_pct']):.2f}%)"
    )
    axes[0].set_ylabel("Equity")
    axes[0].grid(True, linestyle="--", linewidth=0.5, alpha=0.35)

    axes[1].plot(full["date"], full["broker10_margin_to_rebased_equity_pct"], color="#b45309", linewidth=1.1)
    axes[1].axhline(90, color="#ef4444", linewidth=0.8, linestyle="--", alpha=0.55)
    axes[1].axhline(100, color="#991b1b", linewidth=0.8, linestyle="--", alpha=0.55)
    axes[1].set_title("Broker10 margin / equity")
    axes[1].set_ylabel("Margin %")
    axes[1].grid(True, linestyle="--", linewidth=0.5, alpha=0.35)

    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=170)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    cost: pd.DataFrame,
    comparison: pd.DataFrame,
    annual: pd.DataFrame,
    product: pd.DataFrame,
    status: pd.DataFrame,
    sizing: pd.DataFrame,
    risk_breakdown: pd.DataFrame,
    stop_distance: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    lines = [
        "# Stage685 Stage397 MA20 initial stop sizing no prev2day",
        "",
        "- 口径：基于 Stage397 risk1/no-loss-streak C2。",
        "- 变更：用 MA20 作为有效方向上的初始止损/手数计算距离；关闭 `enable_prev2day_stop`。",
        "- 其余保持：plus25 含 PVC、no-AI、`short_case1a/2/3`、`maxpos25`、`streak_risk_multipliers=1.0,1.0,1.0,1.0`。",
        "- 本阶段不修改正式配置、不连接 CTP、不调用下单。",
        "",
        "## Full Summary",
        "",
        summary.to_markdown(index=False),
        "",
        "## Comparison",
        "",
        comparison.to_markdown(index=False),
        "",
        "## Cost Stress",
        "",
        cost.to_markdown(index=False),
        "",
        "## Annual",
        "",
        annual.to_markdown(index=False),
        "",
        "## Candidate Status",
        "",
        status.to_markdown(index=False),
        "",
        "## Sizing Limit",
        "",
        sizing.to_markdown(index=False),
        "",
        "## Risk Breakdown",
        "",
        risk_breakdown.to_markdown(index=False),
        "",
        "## Stop Distance",
        "",
        stop_distance.to_markdown(index=False),
        "",
        "## Product",
        "",
        product.to_markdown(index=False),
        "",
        "## Decision",
        "",
        f"- decision: `{decision['decision']}`",
        f"- main conclusion: {decision['main_conclusion']}",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    spec, metadata = _build_target_spec()
    original_can_open_short = QmtRollPortfolioStrategy._can_open_short_signal
    original_entry_stop_price = QmtRollPortfolioStrategy._entry_stop_price
    try:
        QmtRollPortfolioStrategy._can_open_short_signal = s680._allow_short_cases123
        QmtRollPortfolioStrategy._entry_stop_price = _ma20_initial_stop_price
        result = s681._run_full_with_diagnostics(TARGET_RUN_NAME, spec, metadata)
    finally:
        QmtRollPortfolioStrategy._can_open_short_signal = original_can_open_short
        QmtRollPortfolioStrategy._entry_stop_price = original_entry_stop_price

    summary_row, curve, cost_rows = s666._window_metrics(
        result["daily"],
        spec=spec,
        window_name="full_2020_20260430",
        window_label="2020-2026Q2历史全周期",
        group="historical_full",
        source_name=f"{TARGET_VARIANT}_full_path",
        caveat="Stage685 risk1 MA20 initial stop sizing and prev2day disabled full-window rerun.",
        forced_events=result["forced_events"],
    )
    summary = pd.DataFrame([summary_row])
    cost = pd.DataFrame(cost_rows)
    comparison = _comparison(summary_row, cost)
    annual, monthly = s666._annual_monthly(curve, f"{TARGET_VARIANT}_full_path")
    product = s681._position_product_summary(result["positions"])
    candidates = result["candidates"]
    risks = result["risks"]
    status = s681._candidate_status(candidates)
    candidate_product = s681._candidate_product(candidates)
    sizing = s681._sizing_limit(candidates)
    risk_breakdown = s684._risk_breakdown(candidates)
    stop_distance = _stop_distance_summary(risks)

    result["positions"].to_csv(POSITIONS_PATH, index=False, encoding="utf-8-sig")
    candidates.to_csv(CANDIDATES_PATH, index=False, encoding="utf-8-sig")
    risks.to_csv(RISKS_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    annual.to_csv(ANNUAL_PATH, index=False, encoding="utf-8-sig")
    monthly.to_csv(MONTHLY_PATH, index=False, encoding="utf-8-sig")
    curve.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    product.to_csv(PRODUCT_PATH, index=False, encoding="utf-8-sig")
    status.to_csv(CANDIDATE_STATUS_PATH, index=False, encoding="utf-8-sig")
    candidate_product.to_csv(CANDIDATE_PRODUCT_PATH, index=False, encoding="utf-8-sig")
    sizing.to_csv(SIZING_LIMIT_PATH, index=False, encoding="utf-8-sig")
    risk_breakdown.to_csv(RISK_BREAKDOWN_PATH, index=False, encoding="utf-8-sig")
    stop_distance.to_csv(STOP_DISTANCE_PATH, index=False, encoding="utf-8-sig")
    _plot_curve(curve, summary_row)

    decision = {
        "stage": "Stage398",
        "script_stage": "Stage685",
        "model_tag": MODEL_TAG,
        "variant": TARGET_VARIANT,
        "based_on": BASE_STAGE397_VARIANT,
        "change": {
            "risk_ratio_all_fields": TARGET_TRADE_RISK_RATIO,
            "initial_stop_for_sizing": "ma20_when_valid_side_else_original_fallback",
            "ma_stop_window": MA_STOP_WINDOW,
            "enable_prev2day_stop": False,
            "enable_profit_lock_trend_relaxed_prev2day_stop": False,
            "streak_risk_multipliers": NO_STREAK_MULTIPLIERS,
            "official_config_changed": False,
            "ctp_connected": False,
            "order_api_called": False,
        },
        "summary": summary_row,
        "comparison": comparison.to_dict("records"),
        "candidate_status": status.to_dict("records"),
        "risk_breakdown": risk_breakdown.to_dict("records"),
        "stop_distance": stop_distance.to_dict("records"),
        "decision": "stage397_ma20_initial_stop_no_prev2day_ablation_pending_review",
        "main_conclusion": "ma20_stop_sizing_and_no_prev2day_requires_result_review",
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "cost": str(COST_PATH),
            "comparison": str(COMPARISON_PATH),
            "annual": str(ANNUAL_PATH),
            "monthly": str(MONTHLY_PATH),
            "curves": str(CURVES_PATH),
            "product": str(PRODUCT_PATH),
            "candidate_status": str(CANDIDATE_STATUS_PATH),
            "candidate_product": str(CANDIDATE_PRODUCT_PATH),
            "sizing_limit": str(SIZING_LIMIT_PATH),
            "risk_breakdown": str(RISK_BREAKDOWN_PATH),
            "stop_distance": str(STOP_DISTANCE_PATH),
            "report": str(REPORT_PATH),
            "decision": str(DECISION_PATH),
            "chart": str(CHART_PATH),
        },
    }
    _write_report(summary, cost, comparison, annual, product, status, sizing, risk_breakdown, stop_distance, decision)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
