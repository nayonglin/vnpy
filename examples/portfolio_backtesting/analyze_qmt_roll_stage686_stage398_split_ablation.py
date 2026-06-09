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
import analyze_qmt_roll_stage683_stage395_no_loss_streak_trade_risk005 as s683
import analyze_qmt_roll_stage684_stage395_no_loss_streak_trade_risk001 as s684
import analyze_qmt_roll_stage685_stage397_ma20_initial_stop_no_prev2day as s685
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
MODEL_TAG = "stage686_stage398_split_ablation_v1"
OUTPUT_PREFIX = "qmt_roll_stage686_stage398_split_ablation"

TARGET_TRADE_RISK_RATIO = 0.01
NO_STREAK_MULTIPLIERS = "1.0,1.0,1.0,1.0"
BASE_STAGE397_VARIANT = s684.TARGET_VARIANT
BASE_STAGE398_VARIANT = s685.TARGET_VARIANT
BASE_STAGE396_VARIANT = s683.TARGET_VARIANT

ARM_MA20_ONLY_VARIANT = (
    "stage372_500k_trade_risk001_no_ai_plus25_jd_v_short_cases123_"
    "no_loss_streak_ma20stop_prev2day_maxpos25"
)
ARM_NO_PREV2DAY_ONLY_VARIANT = (
    "stage372_500k_trade_risk001_no_ai_plus25_jd_v_short_cases123_"
    "no_loss_streak_defaultstop_no_prev2day_maxpos25"
)

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


ARMS = [
    {
        "ablation": "ma20_only",
        "run_name": "stage399_a_ma20_only_risk001_prev2day_on",
        "variant": ARM_MA20_ONLY_VARIANT,
        "label": "MA20 initial stop only; prev2day kept",
        "use_ma20_stop": True,
        "enable_prev2day_stop": True,
        "enable_profit_lock_trend_relaxed_prev2day_stop": False,
    },
    {
        "ablation": "no_prev2day_only",
        "run_name": "stage399_b_default_stop_no_prev2day_risk001",
        "variant": ARM_NO_PREV2DAY_ONLY_VARIANT,
        "label": "Original initial stop; prev2day disabled",
        "use_ma20_stop": False,
        "enable_prev2day_stop": False,
        "enable_profit_lock_trend_relaxed_prev2day_stop": False,
    },
]


def _json_safe(value: Any) -> Any:
    return s681._json_safe(value)


def _build_arm_spec(arm: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
    spec, metadata = s684._build_target_spec()
    capital = replace(
        spec.capital,
        variant=arm["variant"],
        label=f"Stage399 split ablation {arm['ablation']}",
        note=(
            "Stage686: split Stage398 into one-variable ablations. "
            f"{arm['label']}; risk_ratio remains 0.01 and loss-streak throttle remains off."
        ),
    )
    overrides = {
        **spec.overrides,
        "enable_prev2day_stop": bool(arm["enable_prev2day_stop"]),
        "enable_profit_lock_trend_relaxed_prev2day_stop": bool(
            arm["enable_profit_lock_trend_relaxed_prev2day_stop"]
        ),
        "streak_risk_multipliers": NO_STREAK_MULTIPLIERS,
    }
    return replace(spec, capital=capital, overrides=overrides, profile=arm["variant"]), metadata


def _cost_lookup(cost: pd.DataFrame) -> dict[str, dict[str, Any]]:
    return {str(float(row["cost_multiplier"])): row.to_dict() for _, row in cost.iterrows()}


def _comparison(summary: pd.DataFrame, cost: pd.DataFrame) -> pd.DataFrame:
    baselines = [
        (
            "stage397_risk001_default_stop_prev2day",
            s684._load_full_row(s684.SUMMARY_PATH, BASE_STAGE397_VARIANT),
            s684._load_cost_rows(s684.COST_PATH, BASE_STAGE397_VARIANT),
        ),
        (
            "stage398_ma20_plus_no_prev2day",
            s684._load_full_row(s685.SUMMARY_PATH, BASE_STAGE398_VARIANT),
            s684._load_cost_rows(s685.COST_PATH, BASE_STAGE398_VARIANT),
        ),
        (
            "stage396_risk0005_default_stop_prev2day",
            s684._load_full_row(s683.SUMMARY_PATH, BASE_STAGE396_VARIANT),
            s684._load_cost_rows(s683.COST_PATH, BASE_STAGE396_VARIANT),
        ),
    ]
    target_cost = {
        str(row["ablation"]): _cost_lookup(
            cost[cost["ablation"].astype(str).eq(str(row["ablation"]))]
        )
        for _, row in summary.iterrows()
    }
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
    for _, target in summary.iterrows():
        ablation = str(target["ablation"])
        for baseline_name, baseline, baseline_cost in baselines:
            for source_field, metric in metrics:
                baseline_value = float(baseline[source_field])
                target_value = float(target[source_field])
                rows.append(
                    {
                        "ablation": ablation,
                        "baseline": baseline_name,
                        "metric": metric,
                        "baseline_value": baseline_value,
                        "target_value": target_value,
                        "delta": target_value - baseline_value,
                    }
                )
            for multiplier in ("2.0", "3.0"):
                if multiplier not in baseline_cost or multiplier not in target_cost.get(ablation, {}):
                    continue
                baseline_dd = float(baseline_cost[multiplier]["max_dd_pct"])
                target_dd = float(target_cost[ablation][multiplier]["max_dd_pct"])
                baseline_equity = float(baseline_cost[multiplier]["end_equity"])
                target_equity = float(target_cost[ablation][multiplier]["end_equity"])
                rows.append(
                    {
                        "ablation": ablation,
                        "baseline": baseline_name,
                        "metric": f"{multiplier}x_cost_max_dd_pct",
                        "baseline_value": baseline_dd,
                        "target_value": target_dd,
                        "delta": target_dd - baseline_dd,
                    }
                )
                rows.append(
                    {
                        "ablation": ablation,
                        "baseline": baseline_name,
                        "metric": f"{multiplier}x_cost_end_equity",
                        "baseline_value": baseline_equity,
                        "target_value": target_equity,
                        "delta": target_equity - baseline_equity,
                    }
                )
    return pd.DataFrame(rows)


def _append_ablation(frame: pd.DataFrame, ablation: str, run_name: str) -> pd.DataFrame:
    data = frame.copy()
    if "run_name" in data.columns:
        data["run_name"] = run_name
    else:
        data.insert(0, "run_name", run_name)
    if "ablation" in data.columns:
        data["ablation"] = ablation
    else:
        data.insert(0, "ablation", ablation)
    return data


def _load_curve(path: Path, label: str) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(path, encoding="utf-8-sig")
    full = frame[frame["window_name"].astype(str).eq("full_2020_20260430")].copy()
    if full.empty:
        return pd.DataFrame()
    full["chart_label"] = label
    return full


def _plot_comparison(curves: pd.DataFrame) -> None:
    if curves.empty:
        return
    data = curves.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data.sort_values(["chart_label", "date"], inplace=True)
    colors = {
        "Stage397 default": "#64748b",
        "A MA20 only": "#0f766e",
        "B no prev2day only": "#b45309",
        "Stage398 combo": "#7c3aed",
    }
    fig, axes = plt.subplots(2, 1, figsize=(13.5, 8), sharex=True, gridspec_kw={"height_ratios": [2, 1]})
    for label, group in data.groupby("chart_label"):
        color = colors.get(label, None)
        axes[0].plot(group["date"], group["rebased_equity"], label=label, linewidth=1.25, color=color)
        if label in {"A MA20 only", "B no prev2day only"}:
            axes[1].plot(
                group["date"],
                group["broker10_margin_to_rebased_equity_pct"],
                label=label,
                linewidth=1.05,
                color=color,
            )
    axes[0].axhline(500_000, color="#94a3b8", linewidth=0.8, linestyle="--", alpha=0.8)
    axes[0].set_title("Stage399 split ablation: MA20 sizing vs no prev2day")
    axes[0].set_ylabel("Equity")
    axes[0].grid(True, linestyle="--", linewidth=0.5, alpha=0.35)
    axes[0].legend(loc="upper left")

    axes[1].axhline(90, color="#ef4444", linewidth=0.8, linestyle="--", alpha=0.55)
    axes[1].axhline(100, color="#991b1b", linewidth=0.8, linestyle="--", alpha=0.55)
    axes[1].set_title("Broker10 margin / equity for split arms")
    axes[1].set_ylabel("Margin %")
    axes[1].grid(True, linestyle="--", linewidth=0.5, alpha=0.35)
    axes[1].legend(loc="upper left")
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
        "# Stage686 Stage398 split ablation",
        "",
        "- 口径：基于 Stage397 risk1/no-loss-streak C2。",
        "- A：只改 MA20 初始止损手数计算，保留 prev2day。",
        "- B：只关闭 prev2day，保留原始最近几日初始止损手数计算。",
        "- 不修改正式配置、不连接 CTP、不调用下单。",
        "",
        "## Summary",
        "",
        summary.to_markdown(index=False),
        "",
        "## Cost Stress",
        "",
        cost.to_markdown(index=False),
        "",
        "## Comparison",
        "",
        comparison.to_markdown(index=False),
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
    original_can_open_short = QmtRollPortfolioStrategy._can_open_short_signal
    original_entry_stop_price = QmtRollPortfolioStrategy._entry_stop_price

    summary_frames: list[pd.DataFrame] = []
    cost_frames: list[pd.DataFrame] = []
    annual_frames: list[pd.DataFrame] = []
    monthly_frames: list[pd.DataFrame] = []
    curve_frames: list[pd.DataFrame] = []
    product_frames: list[pd.DataFrame] = []
    status_frames: list[pd.DataFrame] = []
    candidate_product_frames: list[pd.DataFrame] = []
    sizing_frames: list[pd.DataFrame] = []
    risk_breakdown_frames: list[pd.DataFrame] = []
    stop_distance_frames: list[pd.DataFrame] = []
    positions_frames: list[pd.DataFrame] = []
    candidate_frames: list[pd.DataFrame] = []
    risk_frames: list[pd.DataFrame] = []

    for arm in ARMS:
        spec, metadata = _build_arm_spec(arm)
        try:
            QmtRollPortfolioStrategy._can_open_short_signal = s680._allow_short_cases123
            if arm["use_ma20_stop"]:
                QmtRollPortfolioStrategy._entry_stop_price = s685._ma20_initial_stop_price
            else:
                QmtRollPortfolioStrategy._entry_stop_price = original_entry_stop_price
            result = s681._run_full_with_diagnostics(arm["run_name"], spec, metadata)
        finally:
            QmtRollPortfolioStrategy._can_open_short_signal = original_can_open_short
            QmtRollPortfolioStrategy._entry_stop_price = original_entry_stop_price

        summary_row, curve, cost_rows = s666._window_metrics(
            result["daily"],
            spec=spec,
            window_name="full_2020_20260430",
            window_label="2020-2026Q2历史全周期",
            group="historical_full",
            source_name=f"{arm['variant']}_full_path",
            caveat=f"Stage686 split ablation {arm['ablation']}.",
            forced_events=result["forced_events"],
        )
        summary = pd.DataFrame([{**summary_row, "ablation": arm["ablation"], "run_name": arm["run_name"]}])
        cost = _append_ablation(pd.DataFrame(cost_rows), arm["ablation"], arm["run_name"])
        annual, monthly = s666._annual_monthly(curve, f"{arm['variant']}_full_path")
        curve = curve.copy()
        curve.insert(0, "run_name", arm["run_name"])
        curve.insert(0, "ablation", arm["ablation"])
        curve["chart_label"] = "A MA20 only" if arm["ablation"] == "ma20_only" else "B no prev2day only"

        candidates = result["candidates"]
        risks = result["risks"]
        product = _append_ablation(s681._position_product_summary(result["positions"]), arm["ablation"], arm["run_name"])
        status = _append_ablation(s681._candidate_status(candidates), arm["ablation"], arm["run_name"])
        candidate_product = _append_ablation(s681._candidate_product(candidates), arm["ablation"], arm["run_name"])
        sizing = _append_ablation(s681._sizing_limit(candidates), arm["ablation"], arm["run_name"])
        risk_breakdown = _append_ablation(s684._risk_breakdown(candidates), arm["ablation"], arm["run_name"])
        stop_distance = _append_ablation(s685._stop_distance_summary(risks), arm["ablation"], arm["run_name"])

        positions_frames.append(_append_ablation(result["positions"], arm["ablation"], arm["run_name"]))
        candidate_frames.append(_append_ablation(candidates, arm["ablation"], arm["run_name"]))
        risk_frames.append(_append_ablation(risks, arm["ablation"], arm["run_name"]))
        summary_frames.append(summary)
        cost_frames.append(cost)
        annual_frames.append(_append_ablation(annual, arm["ablation"], arm["run_name"]))
        monthly_frames.append(_append_ablation(monthly, arm["ablation"], arm["run_name"]))
        curve_frames.append(curve)
        product_frames.append(product)
        status_frames.append(status)
        candidate_product_frames.append(candidate_product)
        sizing_frames.append(sizing)
        risk_breakdown_frames.append(risk_breakdown)
        stop_distance_frames.append(stop_distance)

    summary_all = pd.concat(summary_frames, ignore_index=True)
    cost_all = pd.concat(cost_frames, ignore_index=True)
    comparison = _comparison(summary_all, cost_all)
    annual_all = pd.concat(annual_frames, ignore_index=True)
    monthly_all = pd.concat(monthly_frames, ignore_index=True)
    curves_all = pd.concat(curve_frames, ignore_index=True)
    product_all = pd.concat(product_frames, ignore_index=True)
    status_all = pd.concat(status_frames, ignore_index=True)
    candidate_product_all = pd.concat(candidate_product_frames, ignore_index=True)
    sizing_all = pd.concat(sizing_frames, ignore_index=True)
    risk_breakdown_all = pd.concat(risk_breakdown_frames, ignore_index=True)
    stop_distance_all = pd.concat(stop_distance_frames, ignore_index=True)
    positions_all = pd.concat(positions_frames, ignore_index=True)
    candidates_all = pd.concat(candidate_frames, ignore_index=True)
    risks_all = pd.concat(risk_frames, ignore_index=True)

    baseline_curves = [
        _load_curve(s684.CURVES_PATH, "Stage397 default"),
        _load_curve(s685.CURVES_PATH, "Stage398 combo"),
    ]
    plot_curves = pd.concat([curves_all, *[frame for frame in baseline_curves if not frame.empty]], ignore_index=True)
    _plot_comparison(plot_curves)

    positions_all.to_csv(POSITIONS_PATH, index=False, encoding="utf-8-sig")
    candidates_all.to_csv(CANDIDATES_PATH, index=False, encoding="utf-8-sig")
    risks_all.to_csv(RISKS_PATH, index=False, encoding="utf-8-sig")
    summary_all.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost_all.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    annual_all.to_csv(ANNUAL_PATH, index=False, encoding="utf-8-sig")
    monthly_all.to_csv(MONTHLY_PATH, index=False, encoding="utf-8-sig")
    curves_all.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    product_all.to_csv(PRODUCT_PATH, index=False, encoding="utf-8-sig")
    status_all.to_csv(CANDIDATE_STATUS_PATH, index=False, encoding="utf-8-sig")
    candidate_product_all.to_csv(CANDIDATE_PRODUCT_PATH, index=False, encoding="utf-8-sig")
    sizing_all.to_csv(SIZING_LIMIT_PATH, index=False, encoding="utf-8-sig")
    risk_breakdown_all.to_csv(RISK_BREAKDOWN_PATH, index=False, encoding="utf-8-sig")
    stop_distance_all.to_csv(STOP_DISTANCE_PATH, index=False, encoding="utf-8-sig")

    decision = {
        "stage": "Stage399",
        "script_stage": "Stage686",
        "model_tag": MODEL_TAG,
        "based_on": BASE_STAGE397_VARIANT,
        "arms": ARMS,
        "summary": summary_all.to_dict("records"),
        "comparison": comparison.to_dict("records"),
        "candidate_status": status_all.to_dict("records"),
        "risk_breakdown": risk_breakdown_all.to_dict("records"),
        "stop_distance": stop_distance_all.to_dict("records"),
        "decision": "stage398_split_ablation_pending_review",
        "main_conclusion": "review_ma20_only_vs_no_prev2day_only_to_attribute_stage398",
        "change": {
            "risk_ratio_all_fields": TARGET_TRADE_RISK_RATIO,
            "streak_risk_multipliers": NO_STREAK_MULTIPLIERS,
            "official_config_changed": False,
            "ctp_connected": False,
            "order_api_called": False,
        },
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
    _write_report(
        summary_all,
        cost_all,
        comparison,
        annual_all,
        product_all,
        status_all,
        sizing_all,
        risk_breakdown_all,
        stop_distance_all,
        decision,
    )
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
