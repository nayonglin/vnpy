from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
from typing import Any

import pandas as pd

import analyze_qmt_roll_stage666_stage372_500k_risk005_ag_ab as s666
import analyze_qmt_roll_stage680_stage372_500k_trade_risk002_no_ai_plus25_jd_v_short_cases123 as s680
import analyze_qmt_roll_stage681_stage393_pvc_trade_count_attribution as s681
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
MODEL_TAG = "stage682_stage393_c2_no_loss_streak_v1"
OUTPUT_PREFIX = "qmt_roll_stage682_stage393_c2_no_loss_streak"

BASELINE_VARIANT = "stage372_500k_trade_risk002_no_ai_plus25_jd_v_short_cases123_maxpos25"
NO_STREAK_VARIANT = "stage372_500k_trade_risk002_no_ai_plus25_jd_v_short_cases123_no_loss_streak_maxpos25"
NO_STREAK_RUN_NAME = "stage395_c2_plus25_with_pvc_no_loss_streak"
NO_STREAK_MULTIPLIERS = "1.0,1.0,1.0,1.0"

BASELINE_SUMMARY_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage680_stage372_500k_trade_risk002_no_ai_plus25_jd_v_short_cases123_summary_"
    "stage680_stage372_500k_trade_risk002_no_ai_plus25_jd_v_short_cases123_v1.csv"
)
BASELINE_COST_PATH = (
    OUTPUT_DIR
    / "qmt_roll_stage680_stage372_500k_trade_risk002_no_ai_plus25_jd_v_short_cases123_cost_stress_"
    "stage680_stage372_500k_trade_risk002_no_ai_plus25_jd_v_short_cases123_v1.csv"
)

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
ANNUAL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_annual_{MODEL_TAG}.csv"
MONTHLY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_monthly_{MODEL_TAG}.csv"
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


def _json_safe(value: Any) -> Any:
    return s681._json_safe(value)


def _build_no_loss_streak_spec() -> tuple[Any, dict[str, Any]]:
    spec, metadata = s681._build_stage393_spec()
    capital = replace(
        spec.capital,
        variant=NO_STREAK_VARIANT,
        label="Stage395 C2 plus25 PVC no loss-streak throttle",
        note=(
            "Stage682: keep Stage393 C2 universe/risk_ratio/no-AI/short cases, "
            "but set streak_risk_multipliers to 1.0,1.0,1.0,1.0."
        ),
    )
    overrides = {
        **spec.overrides,
        "streak_risk_multipliers": NO_STREAK_MULTIPLIERS,
    }
    return replace(spec, capital=capital, overrides=overrides, profile=NO_STREAK_VARIANT), metadata


def _load_baseline_summary() -> tuple[dict[str, Any], dict[str, Any]]:
    summary = pd.read_csv(BASELINE_SUMMARY_PATH, encoding="utf-8-sig")
    full = summary[
        summary["variant"].astype(str).eq(BASELINE_VARIANT)
        & summary["window_name"].astype(str).eq("full_2020_20260430")
    ]
    if full.empty:
        raise RuntimeError(f"missing baseline full summary: {BASELINE_SUMMARY_PATH}")
    base_row = full.iloc[0].to_dict()

    cost = pd.read_csv(BASELINE_COST_PATH, encoding="utf-8-sig")
    full_cost = cost[
        cost["variant"].astype(str).eq(BASELINE_VARIANT)
        & cost["window_name"].astype(str).eq("full_2020_20260430")
    ].copy()
    cost_by_multiplier = {
        str(float(row["cost_multiplier"])): row.to_dict()
        for _, row in full_cost.iterrows()
    }
    return base_row, cost_by_multiplier


def _comparison(no_streak_summary: dict[str, Any], no_streak_cost: pd.DataFrame) -> pd.DataFrame:
    base, base_cost = _load_baseline_summary()
    cost_lookup = {
        str(float(row["cost_multiplier"])): row.to_dict()
        for _, row in no_streak_cost.iterrows()
    }
    rows: list[dict[str, Any]] = []
    field_pairs = [
        ("rebased_end_equity", "end_equity"),
        ("rebased_total_return_pct", "return_pct"),
        ("rebased_max_dd_pct", "max_dd_pct"),
        ("rebased_sharpe", "sharpe"),
        ("total_slippage", "slippage"),
        ("total_trade_count", "trade_count"),
        ("nonzero_daily_win_rate_pct", "win_rate_pct"),
        ("max_broker10_margin_to_rebased_equity_pct", "max_margin_pct"),
        ("p95_broker10_margin_to_rebased_equity_pct", "p95_margin_pct"),
        ("days_over_100pct", "days_over_100pct"),
        ("days_over_90pct", "days_over_90pct"),
    ]
    for source_field, metric in field_pairs:
        baseline_value = float(base[source_field])
        no_streak_value = float(no_streak_summary[source_field])
        rows.append(
            {
                "metric": metric,
                "baseline_stage393_c2": baseline_value,
                "no_loss_streak": no_streak_value,
                "delta": no_streak_value - baseline_value,
            }
        )
    for multiplier in ("2.0", "3.0"):
        if multiplier not in base_cost or multiplier not in cost_lookup:
            continue
        rows.append(
            {
                "metric": f"{multiplier}x_cost_max_dd_pct",
                "baseline_stage393_c2": float(base_cost[multiplier]["max_dd_pct"]),
                "no_loss_streak": float(cost_lookup[multiplier]["max_dd_pct"]),
                "delta": float(cost_lookup[multiplier]["max_dd_pct"]) - float(base_cost[multiplier]["max_dd_pct"]),
            }
        )
        rows.append(
            {
                "metric": f"{multiplier}x_cost_end_equity",
                "baseline_stage393_c2": float(base_cost[multiplier]["end_equity"]),
                "no_loss_streak": float(cost_lookup[multiplier]["end_equity"]),
                "delta": float(cost_lookup[multiplier]["end_equity"]) - float(base_cost[multiplier]["end_equity"]),
            }
        )
    return pd.DataFrame(rows)


def _risk_breakdown(candidates: pd.DataFrame) -> pd.DataFrame:
    if candidates.empty:
        return pd.DataFrame()
    data = candidates.copy()
    zero = data[data["skip_reason"].fillna("").astype(str).eq("sizing_zero_volume")].copy()
    opened = data[data["candidate_status"].astype(str).eq("opened")].copy()
    frames = [("all_candidates", data), ("opened", opened), ("sizing_zero_volume", zero)]
    rows: list[dict[str, Any]] = []
    for scope, frame in frames:
        if frame.empty:
            rows.append({"scope": scope, "count": 0})
            continue
        risk_multiplier = pd.to_numeric(frame.get("risk_multiplier", 0.0), errors="coerce").fillna(0.0)
        loss_streak = pd.to_numeric(frame.get("loss_streak", 0.0), errors="coerce").fillna(0.0)
        contracts_by_risk = pd.to_numeric(frame.get("contracts_by_risk", 0.0), errors="coerce").fillna(0.0)
        contracts_by_margin = pd.to_numeric(frame.get("contracts_by_margin", 0.0), errors="coerce").fillna(0.0)
        rows.append(
            {
                "scope": scope,
                "count": int(len(frame)),
                "risk_multiplier_0_1_count": int((risk_multiplier <= 0.1000001).sum()),
                "risk_multiplier_1_count": int((risk_multiplier >= 0.999999).sum()),
                "loss_streak_ge3_count": int((loss_streak >= 3).sum()),
                "contracts_by_risk_zero_margin_positive_count": int(
                    ((contracts_by_risk <= 0) & (contracts_by_margin > 0)).sum()
                ),
                "median_target_risk_amount": float(
                    pd.to_numeric(frame.get("target_risk_amount", 0.0), errors="coerce").fillna(0.0).median()
                ),
                "median_risk_per_contract": float(
                    pd.to_numeric(frame.get("risk_per_contract", 0.0), errors="coerce").fillna(0.0).median()
                ),
                "median_estimated_equity": float(
                    pd.to_numeric(frame.get("estimated_equity", 0.0), errors="coerce").fillna(0.0).median()
                ),
                "median_contracts_by_risk": float(contracts_by_risk.median()),
                "median_contracts_by_margin": float(contracts_by_margin.median()),
                "median_selected_volume": float(
                    pd.to_numeric(frame.get("selected_volume", 0.0), errors="coerce").fillna(0.0).median()
                ),
            }
        )
    return pd.DataFrame(rows)


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
        "# Stage682 Stage393 C2 no loss-streak throttle",
        "",
        "- 口径：只关闭 `streak_risk_multipliers`，设置为 `1.0,1.0,1.0,1.0`。",
        "- 其余保持 Stage393 C2：plus25 含 PVC、no-AI、`risk_ratio_*=0.02`、`short_case1a/2/3`、`maxpos25`。",
        "- 本阶段不修改正式配置、不连接 CTP、不调用下单。",
        "",
        "## Full Summary",
        "",
        summary.to_markdown(index=False),
        "",
        "## Comparison Vs Stage393 C2",
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
    spec, metadata = _build_no_loss_streak_spec()
    original_can_open_short = QmtRollPortfolioStrategy._can_open_short_signal
    try:
        QmtRollPortfolioStrategy._can_open_short_signal = s680._allow_short_cases123
        result = s681._run_full_with_diagnostics(NO_STREAK_RUN_NAME, spec, metadata)
    finally:
        QmtRollPortfolioStrategy._can_open_short_signal = original_can_open_short

    summary_row, curve, cost_rows = s666._window_metrics(
        result["daily"],
        spec=spec,
        window_name="full_2020_20260430",
        window_label="2020-2026Q2历史全周期",
        group="historical_full",
        source_name=f"{NO_STREAK_VARIANT}_full_path",
        caveat="Stage682 no loss-streak throttle full-window rerun.",
        forced_events=result["forced_events"],
    )
    summary = pd.DataFrame([summary_row])
    cost = pd.DataFrame(cost_rows)
    comparison = _comparison(summary_row, cost)
    annual, monthly = s666._annual_monthly(curve, f"{NO_STREAK_VARIANT}_full_path")
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
    product.to_csv(PRODUCT_PATH, index=False, encoding="utf-8-sig")
    status.to_csv(CANDIDATE_STATUS_PATH, index=False, encoding="utf-8-sig")
    candidate_product.to_csv(CANDIDATE_PRODUCT_PATH, index=False, encoding="utf-8-sig")
    sizing.to_csv(SIZING_LIMIT_PATH, index=False, encoding="utf-8-sig")
    risk_breakdown.to_csv(RISK_BREAKDOWN_PATH, index=False, encoding="utf-8-sig")

    decision = {
        "stage": "Stage395",
        "script_stage": "Stage682",
        "model_tag": MODEL_TAG,
        "variant": NO_STREAK_VARIANT,
        "baseline_variant": BASELINE_VARIANT,
        "change": {
            "streak_risk_multipliers": NO_STREAK_MULTIPLIERS,
            "official_config_changed": False,
            "ctp_connected": False,
            "order_api_called": False,
        },
        "summary": summary_row,
        "comparison_vs_stage393_c2": comparison.to_dict("records"),
        "candidate_status": status.to_dict("records"),
        "risk_breakdown": risk_breakdown.to_dict("records"),
        "decision": "stage393_c2_no_loss_streak_ablation_only_not_promoted",
        "main_conclusion": "no_loss_streak_ablation_completed",
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "cost": str(COST_PATH),
            "comparison": str(COMPARISON_PATH),
            "annual": str(ANNUAL_PATH),
            "monthly": str(MONTHLY_PATH),
            "product": str(PRODUCT_PATH),
            "candidate_status": str(CANDIDATE_STATUS_PATH),
            "candidate_product": str(CANDIDATE_PRODUCT_PATH),
            "sizing_limit": str(SIZING_LIMIT_PATH),
            "risk_breakdown": str(RISK_BREAKDOWN_PATH),
            "report": str(REPORT_PATH),
            "decision": str(DECISION_PATH),
        },
    }
    _write_report(summary, cost, comparison, annual, product, status, sizing, risk_breakdown, decision)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
