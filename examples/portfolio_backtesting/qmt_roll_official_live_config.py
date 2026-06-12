from __future__ import annotations

from pathlib import Path
from typing import Any


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

OFFICIAL_LIVE_ALIAS: str = "Stage372-20w"
OFFICIAL_LIVE_VERSION: str = "official_live_stage372_20w_recovery_sleeve"
OFFICIAL_LIVE_SOURCE_STAGE: str = "Stage372"
OFFICIAL_LIVE_FAMILY_VERSION: str = "stage526_200k_margin_forced_deleverage_recovery_sleeve"
OFFICIAL_LIVE_BASE_PROFILE_NAME: str = "stage526_200k_force95_to80_largest_margin_r080_pc25_maxpos4"
OFFICIAL_LIVE_PROFILE_NAME: str = "stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4"
OFFICIAL_LIVE_PREVIOUS_VERSION: str = "official_live_stage653_20w_force95_to80"
OFFICIAL_LIVE_PREVIOUS_PROFILE_NAME: str = OFFICIAL_LIVE_BASE_PROFILE_NAME
OFFICIAL_LIVE_ROLE: str = "official_live_deployment_profile"
OFFICIAL_LIVE_CAPITAL: float = 200_000.0
OFFICIAL_LIVE_CAPITAL_LABEL: str = "20w"

LEGACY_STAGE78_VERSION: str = "official_stage78_1_defensive_50w_no_sizing_cap"
LEGACY_STAGE78_STATUS: str = "research_baseline_only_not_live_default"

OFFICIAL_CANDIDATE_STAGE777_VERSION: str = "official_candidate_stage777_50w_am41_oi08_old_ai_v1"
OFFICIAL_CANDIDATE_STAGE777_STATUS: str = "official_candidate_not_live_default"
OFFICIAL_CANDIDATE_STAGE777_CONFIG_MODULE: str = "qmt_roll_official_candidate_stage777_config"
OFFICIAL_CANDIDATE_STAGE819_30W_VERSION: str = (
    "official_candidate_stage819_30w_am41_oi08_old_ai_long_tighter_stop_rsi95_v1"
)
OFFICIAL_CANDIDATE_STAGE819_30W_STATUS: str = "official_candidate_not_live_default_watch"
OFFICIAL_CANDIDATE_STAGE819_30W_CONFIG_MODULE: str = "qmt_roll_official_candidate_stage819_30w_config"
OFFICIAL_CANDIDATE_STAGE813_VERSION: str = (
    "official_candidate_stage813_50w_am41_oi08_old_ai_long_tighter_stop_rsi95_v1"
)
OFFICIAL_CANDIDATE_STAGE813_STATUS: str = "official_candidate_not_live_default"
OFFICIAL_CANDIDATE_STAGE813_CONFIG_MODULE: str = "qmt_roll_official_candidate_stage813_config"
OFFICIAL_CANDIDATE_PRIMARY_VERSION: str = OFFICIAL_CANDIDATE_STAGE819_30W_VERSION
OFFICIAL_CANDIDATE_PRIMARY_CONFIG_MODULE: str = OFFICIAL_CANDIDATE_STAGE819_30W_CONFIG_MODULE
OFFICIAL_CANDIDATE_VERSIONS: dict[str, dict[str, Any]] = {
    OFFICIAL_CANDIDATE_STAGE819_30W_VERSION: {
        "alias": "Stage819-30w-AM41-OI0.8-oldAI-longTightStop-RSI95",
        "source_stage": "Stage819",
        "base_stage": "Stage813",
        "status": OFFICIAL_CANDIDATE_STAGE819_30W_STATUS,
        "config_module": OFFICIAL_CANDIDATE_STAGE819_30W_CONFIG_MODULE,
        "capital": 300_000.0,
        "capital_label": "30w",
        "live_default": False,
        "primary_official_candidate": True,
        "current_live_default_remains": OFFICIAL_LIVE_VERSION,
        "risk_note": (
            "Operator-promoted official candidate and watch arm. It keeps Stage813 "
            "AM41/OI0.8/old-AI/long tighter stop/RSI95 logic and changes only "
            "account_capital/c3_capital to 300000. Stage819 yearly and Stage821 "
            "annual-step rolling results were strong, but Stage822 monthly 3-year "
            "rolling validation did not show stable dominance over 50w and still "
            "had DD50 tail failures; do not use as live default without fresh "
            "shadow, execution dry-run, and explicit risk review."
        ),
    },
    OFFICIAL_CANDIDATE_STAGE813_VERSION: {
        "alias": "Stage813-50w-AM41-OI0.8-oldAI-longTightStop-RSI95",
        "source_stage": "Stage813",
        "status": OFFICIAL_CANDIDATE_STAGE813_STATUS,
        "config_module": OFFICIAL_CANDIDATE_STAGE813_CONFIG_MODULE,
        "capital": 500_000.0,
        "capital_label": "50w",
        "live_default": False,
        "primary_official_candidate": False,
        "current_live_default_remains": OFFICIAL_LIVE_VERSION,
        "risk_note": (
            "Aggressive official candidate by operator request. It explicitly enables "
            "RSI95 half-exit profit lock on top of Stage804 long tighter initial stop, "
            "while keeping Stage777 AM41/OI0.8/old-AI assumptions. Corrected Stage813 "
            "A/B did not improve DD40/DD50 failures, so this is not the live default."
        ),
    },
    OFFICIAL_CANDIDATE_STAGE777_VERSION: {
        "alias": "Stage777-50w-AM41-OI0.8-oldAI",
        "source_stage": "Stage777",
        "status": OFFICIAL_CANDIDATE_STAGE777_STATUS,
        "config_module": OFFICIAL_CANDIDATE_STAGE777_CONFIG_MODULE,
        "capital": 500_000.0,
        "capital_label": "50w",
        "live_default": False,
        "primary_official_candidate": False,
        "current_live_default_remains": OFFICIAL_LIVE_VERSION,
        "risk_note": (
            "High-return official candidate only. Stage777 keeps strong right-tail "
            "returns, but early-start drawdown remains near 49%; do not use as live "
            "default without fresh shadow, execution dry-run, and explicit risk review."
        ),
    },
}

OFFICIAL_LIVE_AI_ELIGIBILITY_PATH: Path = (
    OUTPUT_DIR
    / "qmt_roll_stage182_ai_product_pool_live_inference_combined_stage78_eligibility_"
    "stage182_ai_product_pool_live_inference_v1.csv"
)

OFFICIAL_LIVE_STAGE659_MODEL_TAG: str = "stage659_stage372_2026_ytd_latest_ai_shadow_v1"
OFFICIAL_LIVE_STAGE659_PREFIX: str = "qmt_roll_stage659_stage372_2026_ytd_latest_ai_shadow"
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

OFFICIAL_LIVE_STRATEGY_OVERRIDES: dict[str, Any] = {
    "enable_streak_entry_structure_risk_recovery": True,
    "streak_entry_structure_recovery_signals": "long_case1a,short_case1a",
    "streak_entry_structure_recovery_min_multiplier": 1.0,
    "streak_entry_structure_recovery_require_flat_portfolio": True,
    "streak_entry_structure_recovery_max_same_direction_corr": 0.30,
    "streak_entry_structure_recovery_require_rsi_confirmation": False,
    "enable_recovery_sleeve": True,
    "recovery_sleeve_base_multiplier_max": 0.1000001,
    "recovery_sleeve_broker_margin_multiplier": 1.65,
    "recovery_sleeve_max_single_contract_broker_margin_to_equity": 0.20,
    "recovery_sleeve_cooldown_days": 20,
    "recovery_sleeve_volume": 1,
}

OFFICIAL_LIVE_REFERENCE_METRICS: dict[str, dict[str, float]] = {
    "full_2020_2026_stage372": {
        "end_equity": 8_728_285.0,
        "total_return_pct": 4_264.1425,
        "max_dd_pct": -38.6713,
        "sharpe": 1.6279,
        "total_slippage": 506_220.0,
        "total_trade_count": 633.0,
        "win_rate_pct": 52.2586,
        "broker10_peak_margin_to_equity_pct": 79.6015,
        "forced_margin_deleverage_count": 6.0,
        "forced_margin_deleverage_closed_volume": 299.0,
        "cost2_max_dd_pct": -40.6555,
        "cost3_max_dd_pct": -42.7649,
        "since_2022_total_return_pct": 133.8550,
        "since_2022_max_dd_pct": -28.0550,
    },
    "latest_2026_to_20260604_stage372": {
        "end_equity": 222_440.0,
        "total_return_pct": 11.2200,
        "cagr_pct": 29.5553,
        "max_dd_pct": -16.3027,
        "sharpe": 1.0240,
        "total_slippage": 1_550.0,
        "total_trade_count": 22.0,
        "win_rate_pct": 48.7805,
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
        "base_profile_name": OFFICIAL_LIVE_BASE_PROFILE_NAME,
        "previous_version": OFFICIAL_LIVE_PREVIOUS_VERSION,
        "previous_profile_name": OFFICIAL_LIVE_PREVIOUS_PROFILE_NAME,
        "role": OFFICIAL_LIVE_ROLE,
        "capital": OFFICIAL_LIVE_CAPITAL,
        "capital_label": OFFICIAL_LIVE_CAPITAL_LABEL,
        "ai_eligibility_path": str(OFFICIAL_LIVE_AI_ELIGIBILITY_PATH),
        "summary_path": str(OFFICIAL_LIVE_SUMMARY_PATH),
        "signal_plan_path": str(OFFICIAL_LIVE_SIGNAL_PLAN_PATH),
        "current_positions_path": str(OFFICIAL_LIVE_CURRENT_POSITIONS_PATH),
        "report_path": str(OFFICIAL_LIVE_REPORT_PATH),
        "execution_policy": OFFICIAL_LIVE_EXECUTION_POLICY,
        "strategy_overrides": OFFICIAL_LIVE_STRATEGY_OVERRIDES,
        "reference_metrics": OFFICIAL_LIVE_REFERENCE_METRICS,
        "primary_official_candidate": {
            "version": OFFICIAL_CANDIDATE_PRIMARY_VERSION,
            "config_module": OFFICIAL_CANDIDATE_PRIMARY_CONFIG_MODULE,
            "live_default": False,
        },
        "official_candidates": OFFICIAL_CANDIDATE_VERSIONS,
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
        reasons.append("official_live_deployable_gate_failed")
    if days_over_100 > 0:
        reasons.append("broker10_margin_over_100")
    if days_over_90 > 0:
        reasons.append("broker10_margin_over_90")
    if max_margin >= 90:
        reasons.append("broker10_margin_watch")
    if not reasons:
        reasons.append("official_live_profile_normal")
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
