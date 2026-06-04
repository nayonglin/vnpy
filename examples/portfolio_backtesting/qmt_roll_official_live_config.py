from __future__ import annotations

from pathlib import Path
from typing import Any


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

OFFICIAL_LIVE_ALIAS: str = "Stage653-20w"
OFFICIAL_LIVE_VERSION: str = "official_live_stage653_20w_force95_to80"
OFFICIAL_LIVE_SOURCE_STAGE: str = "Stage653"
OFFICIAL_LIVE_FAMILY_VERSION: str = "stage526_200k_margin_forced_deleverage"
OFFICIAL_LIVE_PROFILE_NAME: str = "stage526_200k_force95_to80_largest_margin_r080_pc25_maxpos4"
OFFICIAL_LIVE_ROLE: str = "official_live_deployment_profile"
OFFICIAL_LIVE_CAPITAL: float = 200_000.0
OFFICIAL_LIVE_CAPITAL_LABEL: str = "20w"

LEGACY_STAGE78_VERSION: str = "official_stage78_1_defensive_50w_no_sizing_cap"
LEGACY_STAGE78_STATUS: str = "research_baseline_only_not_live_default"

OFFICIAL_LIVE_AI_ELIGIBILITY_PATH: Path = (
    OUTPUT_DIR
    / "qmt_roll_stage182_ai_product_pool_live_inference_combined_stage78_eligibility_"
    "stage182_ai_product_pool_live_inference_v1.csv"
)

OFFICIAL_LIVE_STAGE659_MODEL_TAG: str = "stage659_stage653_2026_ytd_latest_ai_shadow_v1"
OFFICIAL_LIVE_STAGE659_PREFIX: str = "qmt_roll_stage659_stage653_2026_ytd_latest_ai_shadow"
OFFICIAL_LIVE_SUMMARY_PATH: Path = (
    OUTPUT_DIR / f"{OFFICIAL_LIVE_STAGE659_PREFIX}_decision_{OFFICIAL_LIVE_STAGE659_MODEL_TAG}.json"
)
OFFICIAL_LIVE_SIGNAL_PLAN_PATH: Path = (
    OUTPUT_DIR / f"{OFFICIAL_LIVE_STAGE659_PREFIX}_signal_plan_{OFFICIAL_LIVE_STAGE659_MODEL_TAG}.csv"
)
OFFICIAL_LIVE_CURRENT_POSITIONS_PATH: Path = (
    OUTPUT_DIR / f"{OFFICIAL_LIVE_STAGE659_PREFIX}_current_positions_{OFFICIAL_LIVE_STAGE659_MODEL_TAG}.csv"
)
OFFICIAL_LIVE_REPORT_PATH: Path = (
    OUTPUT_DIR / f"{OFFICIAL_LIVE_STAGE659_PREFIX}_report_{OFFICIAL_LIVE_STAGE659_MODEL_TAG}.md"
)

OFFICIAL_LIVE_EXECUTION_POLICY: dict[str, Any] = {
    "default_profile": OFFICIAL_LIVE_VERSION,
    "capital": OFFICIAL_LIVE_CAPITAL,
    "normal_signal_source": str(OFFICIAL_LIVE_SIGNAL_PLAN_PATH),
    "position_source": str(OFFICIAL_LIVE_CURRENT_POSITIONS_PATH),
    "legacy_stage78_status": LEGACY_STAGE78_STATUS,
    "must_not_fallback_to_stage78_for_live": True,
    "order_discipline": "fresh_readonly -> dry_run -> explicit_operator_approval -> 1lot_smoke_or_live_submit_gate -> TCA/reconcile",
    "real_submit_default": "fail_closed",
}

OFFICIAL_LIVE_REFERENCE_METRICS: dict[str, dict[str, float]] = {
    "full_2020_2026_stage353": {
        "end_equity": 10_415_070.0,
        "total_return_pct": 5_107.5350,
        "max_dd_pct": -38.8730,
        "sharpe": 1.6384,
        "total_slippage": 597_710.0,
        "total_trade_count": 655.0,
        "win_rate_pct": 52.3156,
        "broker10_peak_margin_to_equity_pct": 83.3212,
        "forced_margin_deleverage_count": 6.0,
        "forced_margin_deleverage_closed_volume": 317.0,
        "return_retention_vs_allin_pct": 89.9664,
    },
    "latest_2026_to_20260604_stage359": {
        "end_equity": 201_140.0,
        "total_return_pct": 0.5700,
        "cagr_pct": 1.3936,
        "max_dd_pct": -14.5394,
        "sharpe": 0.1943,
        "total_slippage": 1_250.0,
        "total_trade_count": 18.0,
        "win_rate_pct": 44.0,
        "broker10_peak_margin_to_equity_pct": 55.1058,
        "forced_margin_deleverage_count": 0.0,
        "forced_margin_deleverage_closed_volume": 0.0,
    },
}


def build_official_live_manifest() -> dict[str, Any]:
    return {
        "alias": OFFICIAL_LIVE_ALIAS,
        "version": OFFICIAL_LIVE_VERSION,
        "family_version": OFFICIAL_LIVE_FAMILY_VERSION,
        "source_stage": OFFICIAL_LIVE_SOURCE_STAGE,
        "profile_name": OFFICIAL_LIVE_PROFILE_NAME,
        "role": OFFICIAL_LIVE_ROLE,
        "capital": OFFICIAL_LIVE_CAPITAL,
        "capital_label": OFFICIAL_LIVE_CAPITAL_LABEL,
        "ai_eligibility_path": str(OFFICIAL_LIVE_AI_ELIGIBILITY_PATH),
        "summary_path": str(OFFICIAL_LIVE_SUMMARY_PATH),
        "signal_plan_path": str(OFFICIAL_LIVE_SIGNAL_PLAN_PATH),
        "current_positions_path": str(OFFICIAL_LIVE_CURRENT_POSITIONS_PATH),
        "report_path": str(OFFICIAL_LIVE_REPORT_PATH),
        "execution_policy": OFFICIAL_LIVE_EXECUTION_POLICY,
        "reference_metrics": OFFICIAL_LIVE_REFERENCE_METRICS,
        "legacy_stage78": {
            "version": LEGACY_STAGE78_VERSION,
            "status": LEGACY_STAGE78_STATUS,
        },
    }


def build_official_live_risk_snapshot(summary: dict[str, Any]) -> dict[str, Any]:
    variant = summary.get("current_variant", {}) or {}
    deployable = int(float(variant.get("deployable_pass", 0) or 0)) == 1
    days_over_100 = int(float(variant.get("days_over_100pct", 0) or 0))
    days_over_90 = int(float(variant.get("days_over_90pct", 0) or 0))
    max_margin = float(variant.get("max_broker10_margin_to_equity_pct", 999.0) or 999.0)
    reasons: list[str] = []
    if not deployable:
        reasons.append("stage653_deployable_gate_failed")
    if days_over_100 > 0:
        reasons.append("broker10_margin_over_100")
    if days_over_90 > 0:
        reasons.append("broker10_margin_over_90")
    if max_margin >= 90:
        reasons.append("broker10_margin_watch")
    if not reasons:
        reasons.append("stage653_live_profile_normal")
    allow_real_new_orders = int(deployable and days_over_100 == 0 and max_margin < 90)
    return {
        "risk_level": "normal" if allow_real_new_orders else "review",
        "allow_shadow_record": 1,
        "allow_real_new_orders": allow_real_new_orders,
        "reasons": reasons,
        "drawdown_pct_abs": abs(float(variant.get("max_dd_pct", 0.0) or 0.0)),
        "daily_loss_cash": 0.0,
        "net_pnl": 0.0,
        "balance": float(variant.get("end_equity", 0.0) or 0.0),
        "execution_adverse_cash": 0.0,
    }
