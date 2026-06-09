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
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
MODEL_TAG = "stage684_stage395_no_loss_streak_trade_risk001_v1"
OUTPUT_PREFIX = "qmt_roll_stage684_stage395_no_loss_streak_trade_risk001"

TARGET_TRADE_RISK_RATIO = 0.01
NO_STREAK_MULTIPLIERS = "1.0,1.0,1.0,1.0"
BASE_NO_STREAK_VARIANT = s682.NO_STREAK_VARIANT
BASE_STAGE393_VARIANT = s682.BASELINE_VARIANT
BASE_RISK005_VARIANT = s683.TARGET_VARIANT
TARGET_VARIANT = "stage372_500k_trade_risk001_no_ai_plus25_jd_v_short_cases123_no_loss_streak_maxpos25"
TARGET_RUN_NAME = "stage397_c2_plus25_with_pvc_no_loss_streak_trade_risk001"

BASE_NO_STREAK_SUMMARY_PATH = s682.SUMMARY_PATH
BASE_NO_STREAK_COST_PATH = s682.COST_PATH
BASE_STAGE393_SUMMARY_PATH = s682.BASELINE_SUMMARY_PATH
BASE_STAGE393_COST_PATH = s682.BASELINE_COST_PATH
BASE_RISK005_SUMMARY_PATH = s683.SUMMARY_PATH
BASE_RISK005_COST_PATH = s683.COST_PATH

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
POSITIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_positions_{MODEL_TAG}.csv"
CANDIDATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_candidates_{MODEL_TAG}.csv"
RISKS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_risk_{MODEL_TAG}.csv"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    return s681._json_safe(value)


def _build_target_spec() -> tuple[Any, dict[str, Any]]:
    spec, metadata = s682._build_no_loss_streak_spec()
    capital = replace(
        spec.capital,
        variant=TARGET_VARIANT,
        label="Stage397 C2 plus25 PVC no loss-streak trade risk 1%",
        risk_multiplier=s681.s674._risk_multiplier_for_record(TARGET_TRADE_RISK_RATIO),
        note=(
            "Stage684: keep Stage395 no-loss-streak C2, but override all risk_ratio_* "
            "fields to 0.01."
        ),
    )
    overrides = {
        **spec.overrides,
        **s681.s674._risk_ratio_overrides(TARGET_TRADE_RISK_RATIO),
        "streak_risk_multipliers": NO_STREAK_MULTIPLIERS,
    }
    return replace(spec, capital=capital, overrides=overrides, profile=TARGET_VARIANT), metadata


def _load_full_row(path: Path, variant: str) -> dict[str, Any]:
    frame = pd.read_csv(path, encoding="utf-8-sig")
    row = frame[
        frame["variant"].astype(str).eq(variant)
        & frame["window_name"].astype(str).eq("full_2020_20260430")
    ]
    if row.empty:
        raise RuntimeError(f"missing full row: {path} {variant}")
    return row.iloc[0].to_dict()


def _load_cost_rows(path: Path, variant: str) -> dict[str, dict[str, Any]]:
    frame = pd.read_csv(path, encoding="utf-8-sig")
    full = frame[
        frame["variant"].astype(str).eq(variant)
        & frame["window_name"].astype(str).eq("full_2020_20260430")
    ].copy()
    return {str(float(row["cost_multiplier"])): row.to_dict() for _, row in full.iterrows()}


def _comparison(target_summary: dict[str, Any], target_cost: pd.DataFrame) -> pd.DataFrame:
    baselines = [
        (
            "stage393_c2",
            _load_full_row(BASE_STAGE393_SUMMARY_PATH, BASE_STAGE393_VARIANT),
            _load_cost_rows(BASE_STAGE393_COST_PATH, BASE_STAGE393_VARIANT),
        ),
        (
            "stage395_no_loss_streak_risk002",
            _load_full_row(BASE_NO_STREAK_SUMMARY_PATH, BASE_NO_STREAK_VARIANT),
            _load_cost_rows(BASE_NO_STREAK_COST_PATH, BASE_NO_STREAK_VARIANT),
        ),
        (
            "stage396_no_loss_streak_risk0005",
            _load_full_row(BASE_RISK005_SUMMARY_PATH, BASE_RISK005_VARIANT),
            _load_cost_rows(BASE_RISK005_COST_PATH, BASE_RISK005_VARIANT),
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


def _risk_breakdown(candidates: pd.DataFrame) -> pd.DataFrame:
    return s682._risk_breakdown(candidates)


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
        "Stage397 risk 1% equity curve "
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
    decision: dict[str, Any],
) -> None:
    lines = [
        "# Stage684 Stage395 no-loss-streak trade risk 1%",
        "",
        "- 口径：基于 Stage395 no-loss-streak C2，只把全部 `risk_ratio_*` 改为 `0.01`。",
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
    try:
        QmtRollPortfolioStrategy._can_open_short_signal = s680._allow_short_cases123
        result = s681._run_full_with_diagnostics(TARGET_RUN_NAME, spec, metadata)
    finally:
        QmtRollPortfolioStrategy._can_open_short_signal = original_can_open_short

    summary_row, curve, cost_rows = s666._window_metrics(
        result["daily"],
        spec=spec,
        window_name="full_2020_20260430",
        window_label="2020-2026Q2历史全周期",
        group="historical_full",
        source_name=f"{TARGET_VARIANT}_full_path",
        caveat="Stage684 no-loss-streak trade-risk1pct full-window rerun.",
        forced_events=result["forced_events"],
    )
    summary = pd.DataFrame([summary_row])
    cost = pd.DataFrame(cost_rows)
    comparison = _comparison(summary_row, cost)
    annual, monthly = s666._annual_monthly(curve, f"{TARGET_VARIANT}_full_path")
    product = s681._position_product_summary(result["positions"])
    candidates = result["candidates"]
    status = s681._candidate_status(candidates)
    candidate_product = s681._candidate_product(candidates)
    sizing = s681._sizing_limit(candidates)
    risk_breakdown = _risk_breakdown(candidates)

    result["positions"].to_csv(POSITIONS_PATH, index=False, encoding="utf-8-sig")
    candidates.to_csv(CANDIDATES_PATH, index=False, encoding="utf-8-sig")
    result["risks"].to_csv(RISKS_PATH, index=False, encoding="utf-8-sig")
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
    _plot_curve(curve, summary_row)

    decision = {
        "stage": "Stage397",
        "script_stage": "Stage684",
        "model_tag": MODEL_TAG,
        "variant": TARGET_VARIANT,
        "based_on": BASE_NO_STREAK_VARIANT,
        "change": {
            "risk_ratio_all_fields": TARGET_TRADE_RISK_RATIO,
            "streak_risk_multipliers": NO_STREAK_MULTIPLIERS,
            "official_config_changed": False,
            "ctp_connected": False,
            "order_api_called": False,
        },
        "summary": summary_row,
        "comparison": comparison.to_dict("records"),
        "candidate_status": status.to_dict("records"),
        "risk_breakdown": risk_breakdown.to_dict("records"),
        "decision": "stage395_no_loss_streak_trade_risk001_ablation_only_not_promoted",
        "main_conclusion": "trade_risk_001_recovers_some_opportunity_but_does_not_restore_stage393_quality",
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
            "report": str(REPORT_PATH),
            "decision": str(DECISION_PATH),
            "chart": str(CHART_PATH),
        },
    }
    _write_report(summary, cost, comparison, annual, product, status, sizing, risk_breakdown, decision)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
