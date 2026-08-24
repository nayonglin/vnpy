from __future__ import annotations

from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

import qmt_roll_official_candidate_stage847_c9_config as stage847_c9_cfg
from qmt_roll_official_live_lightweight_context import (
    DATA_ASSET_DIR,
    OFFICIAL_LIVE_AI_ELIGIBILITY_PATH,
    OFFICIAL_LIVE_AI_LOGICAL_PATH,
    OFFICIAL_LIVE_ALIAS,
    OFFICIAL_LIVE_SHADOW_ANALYSIS_START_DATE,
    OFFICIAL_LIVE_STAGE901_MODEL_TAG,
    OFFICIAL_LIVE_STAGE901_PREFIX,
    OFFICIAL_LIVE_SUMMARY_PATH,
    OFFICIAL_LIVE_MATERIAL_MANIFEST_SHA256,
    OFFICIAL_LIVE_MATERIAL_RELEASE_COMMIT,
    OFFICIAL_LIVE_MATERIAL_RELEASE_ID,
    OFFICIAL_LIVE_VERSION,
    PROJECT_DIR,
    SIGNAL_INPUT_DIR,
)
from qmt_roll_official_live_phase_d_config import (
    PHASE_D_LIVE_REAL_POLICY_ENABLED_VALUE,
)


OUTPUT_DIR: Path = DATA_ASSET_DIR
OFFICIAL_LIVE_SOURCE_STAGE: str = "Stage847/Stage928 + Stage021-Q"
OFFICIAL_LIVE_FAMILY_VERSION: str = "stage819_c9_intraday_stop_retry_stage021_q"
OFFICIAL_LIVE_RULESET_VERSION: str = "stage021_q_rollover_volume_atr_v1"
OFFICIAL_LIVE_PREVIOUS_RULESET_VERSION: str = "stage847_c9_stage819_05r_stop_retry_v1"
OFFICIAL_LIVE_BASE_PROFILE_NAME: str = stage847_c9_cfg.OFFICIAL_CANDIDATE_STAGE847_C9_PROFILE_NAME
OFFICIAL_LIVE_PROFILE_NAME: str = "stage847_c9_15w_stage819_05r_stop_retry_live"
OFFICIAL_LIVE_PREVIOUS_VERSION: str = "official_live_stage847_c9_30w_stage819_05r_stop_retry_once"
OFFICIAL_LIVE_PREVIOUS_PROFILE_NAME: str = "stage847_c9_30w_stage819_05r_stop_retry_live"
OFFICIAL_LIVE_ROLE: str = "official_live_deployment_profile_operator_promoted_stage021_q"
OFFICIAL_LIVE_CAPITAL: float = 150_000.0
OFFICIAL_LIVE_CAPITAL_LABEL: str = "15w"

LEGACY_STAGE78_VERSION: str = "official_stage78_1_defensive_50w_no_sizing_cap"
LEGACY_STAGE78_STATUS: str = "research_baseline_only_not_live_default"
LEGACY_STAGE847_C9_30W_LIVE_VERSION: str = "official_live_stage847_c9_30w_stage819_05r_stop_retry_once"
LEGACY_STAGE847_C9_30W_LIVE_STATUS: str = "previous_live_capital_profile_superseded_by_15w_account_alignment"
LEGACY_STAGE847_C9_30W_PROFILE_NAME: str = "stage847_c9_30w_stage819_05r_stop_retry_live"
LEGACY_STAGE372_LIVE_VERSION: str = "official_live_stage372_20w_recovery_sleeve"
LEGACY_STAGE372_LIVE_STATUS: str = "legacy_previous_live_default_superseded_by_c9_operator_override"
LEGACY_STAGE372_LIVE_PROFILE_NAME: str = "stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4"

OFFICIAL_CANDIDATE_STAGE777_VERSION: str = "official_candidate_stage777_50w_am41_oi08_old_ai_v1"
OFFICIAL_CANDIDATE_STAGE777_STATUS: str = "official_candidate_not_live_default"
OFFICIAL_CANDIDATE_STAGE777_CONFIG_MODULE: str = "qmt_roll_official_candidate_stage777_config"
OFFICIAL_CANDIDATE_STAGE819_30W_VERSION: str = (
    "official_candidate_stage819_30w_am41_oi08_old_ai_long_tighter_stop_rsi95_v1"
)
OFFICIAL_CANDIDATE_STAGE819_30W_STATUS: str = "official_candidate_not_live_default_watch"
OFFICIAL_CANDIDATE_STAGE819_30W_CONFIG_MODULE: str = "qmt_roll_official_candidate_stage819_30w_config"
OFFICIAL_CANDIDATE_STAGE847_C9_VERSION: str = (
    "official_candidate_stage847_c9_30w_stage819_05r_stop_retry_once_v1"
)
OFFICIAL_CANDIDATE_STAGE847_C9_STATUS: str = "promoted_to_live_default_operator_override_high_risk_watch"
OFFICIAL_CANDIDATE_STAGE847_C9_CONFIG_MODULE: str = "qmt_roll_official_candidate_stage847_c9_config"
OFFICIAL_CANDIDATE_STAGE813_VERSION: str = (
    "official_candidate_stage813_50w_am41_oi08_old_ai_long_tighter_stop_rsi95_v1"
)
OFFICIAL_CANDIDATE_STAGE813_STATUS: str = "official_candidate_not_live_default"
OFFICIAL_CANDIDATE_STAGE813_CONFIG_MODULE: str = "qmt_roll_official_candidate_stage813_config"
OFFICIAL_CANDIDATE_PRIMARY_VERSION: str = OFFICIAL_CANDIDATE_STAGE847_C9_VERSION
OFFICIAL_CANDIDATE_PRIMARY_CONFIG_MODULE: str = OFFICIAL_CANDIDATE_STAGE847_C9_CONFIG_MODULE
OFFICIAL_CANDIDATE_VERSIONS: dict[str, dict[str, Any]] = {
    OFFICIAL_CANDIDATE_STAGE847_C9_VERSION: {
        "alias": "Stage847-C9-30w-Stage819-0.5RStopRetry",
        "source_stage": "Stage847",
        "base_stage": "Stage819",
        "status": OFFICIAL_CANDIDATE_STAGE847_C9_STATUS,
        "config_module": OFFICIAL_CANDIDATE_STAGE847_C9_CONFIG_MODULE,
        "capital": 300_000.0,
        "capital_label": "30w",
        "live_capital": OFFICIAL_LIVE_CAPITAL,
        "live_capital_label": OFFICIAL_LIVE_CAPITAL_LABEL,
        "live_default": True,
        "primary_official_candidate": True,
        "current_live_default": OFFICIAL_LIVE_VERSION,
        "previous_live_default": OFFICIAL_LIVE_PREVIOUS_VERSION,
        "risk_note": (
            "Operator-promoted live default and high-risk watch arm. "
            "It inherits the Stage819 30w candidate, then enables the C9 intraday "
            "0.5R stop/retry-once logic, C2 intraday stop, and broker10 entry cap. "
            "Stage900 cleared the prior C9 entry-day minute-data gap and Stage898 "
            "P0 audit now passes, but Stage896/899 still show DD50/broker100 and "
            "near-58% drawdown tails. Stage928 switches only the deployment capital "
            "profile to 15w after the account was funded to 150000; C9 signal logic "
            "is unchanged. This live-default switch is an explicit operator override; "
            "execution remains fail-closed until fresh shadow, execution dry-run, "
            "broker-state reconciliation, and wrapper engineering review are completed."
        ),
    },
    OFFICIAL_CANDIDATE_STAGE819_30W_VERSION: {
        "alias": "Stage819-30w-AM41-OI0.8-oldAI-longTightStop-RSI95",
        "source_stage": "Stage819",
        "base_stage": "Stage813",
        "status": OFFICIAL_CANDIDATE_STAGE819_30W_STATUS,
        "config_module": OFFICIAL_CANDIDATE_STAGE819_30W_CONFIG_MODULE,
        "capital": 300_000.0,
        "capital_label": "30w",
        "live_default": False,
        "primary_official_candidate": False,
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

OFFICIAL_LIVE_STAGE659_MODEL_TAG: str = OFFICIAL_LIVE_STAGE901_MODEL_TAG
OFFICIAL_LIVE_STAGE659_PREFIX: str = OFFICIAL_LIVE_STAGE901_PREFIX
OFFICIAL_LIVE_SIGNAL_PLAN_PATH: Path = (
    SIGNAL_INPUT_DIR
    / f"{OFFICIAL_LIVE_STAGE659_PREFIX}_signal_plan_{OFFICIAL_LIVE_STAGE659_MODEL_TAG}.csv"
)
OFFICIAL_LIVE_CURRENT_POSITIONS_PATH: Path = (
    SIGNAL_INPUT_DIR
    / f"{OFFICIAL_LIVE_STAGE659_PREFIX}_current_positions_{OFFICIAL_LIVE_STAGE659_MODEL_TAG}.csv"
)
OFFICIAL_LIVE_PENDING_ORDERS_PATH: Path = (
    SIGNAL_INPUT_DIR
    / f"{OFFICIAL_LIVE_STAGE659_PREFIX}_pending_orders_{OFFICIAL_LIVE_STAGE659_MODEL_TAG}.csv"
)
OFFICIAL_LIVE_REPORT_PATH: Path = (
    SIGNAL_INPUT_DIR
    / f"{OFFICIAL_LIVE_STAGE659_PREFIX}_report_{OFFICIAL_LIVE_STAGE659_MODEL_TAG}.md"
)

OFFICIAL_LIVE_EXECUTION_POLICY: dict[str, Any] = {
    "default_profile": OFFICIAL_LIVE_VERSION,
    "capital": OFFICIAL_LIVE_CAPITAL,
    "previous_live_default": OFFICIAL_LIVE_PREVIOUS_VERSION,
    "legacy_stage372_live_default": LEGACY_STAGE372_LIVE_VERSION,
    "shadow_runner": "examples/portfolio_backtesting/analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow.py",
    "normal_signal_source": str(OFFICIAL_LIVE_SIGNAL_PLAN_PATH),
    "position_source": str(OFFICIAL_LIVE_CURRENT_POSITIONS_PATH),
    "legacy_stage78_status": LEGACY_STAGE78_STATUS,
    "must_not_fallback_to_stage78_for_live": True,
    "operator_override_risk_acceptance": (
        "Stage021-Q was promoted by explicit operator request despite its historical "
        "A-relative broker peak gate failure. Q keeps the C9/15w control plane and adds "
        "risk-capped rollover continuation, symmetric volume risk scaling, and symmetric "
        "one-ATR5 adverse signal-day entry filters. Runtime execution remains fail-closed."
    ),
    "order_discipline": "fresh_readonly -> dry_run -> explicit_operator_approval -> 1lot_smoke_or_live_submit_gate -> TCA/reconcile",
    "real_submit_default": PHASE_D_LIVE_REAL_POLICY_ENABLED_VALUE,
}


def build_official_live_strategy_overrides() -> dict[str, Any]:
    overrides = stage847_c9_cfg.build_official_candidate_stage847_c9_overrides()
    overrides["account_capital"] = OFFICIAL_LIVE_CAPITAL
    overrides["c3_capital"] = OFFICIAL_LIVE_CAPITAL
    overrides["ai_product_pool_eligibility_path"] = str(OFFICIAL_LIVE_AI_ELIGIBILITY_PATH)
    overrides.update(
        {
            "enable_rollover_shape_same_volume_reopen": True,
            "rollover_shape_volume_policy": "shrink_to_allowed",
            "rollover_shape_history_mode": "backwards_ratio_continuous",
            "enable_directional_30d_risk_boost": True,
            "directional_30d_risk_boost_lookback": 30,
            "directional_30d_risk_boost_multiplier": 1.5,
            "directional_30d_risk_nonconfirmation_multiplier": 1.0,
            "directional_30d_risk_adjust_long_only": False,
            "directional_30d_risk_boost_require_volume_expansion": True,
            "directional_30d_volume_recent_days": 10,
            "directional_30d_volume_prior_days": 10,
            "directional_30d_volume_ratio_threshold": 3.0,
            "enable_directional_30d_low_volume_risk_discount": True,
            "directional_30d_low_volume_ratio_threshold": 0.5,
            "directional_30d_low_volume_risk_multiplier": 0.5,
            "enable_long_signal_atr_shock_filter": True,
            "enable_short_signal_atr_shock_filter": True,
            "long_signal_atr_shock_period": 5,
            "long_signal_atr_shock_multiplier": 1.0,
            "long_signal_atr_shock_entry_contexts": "flat_entry,reverse_entry,rollover_reopen",
        }
    )
    return overrides


class _LazyOfficialLiveStrategyOverrides(Mapping[str, Any]):
    def __init__(self) -> None:
        self._cache: dict[str, Any] | None = None

    def _load(self) -> dict[str, Any]:
        if self._cache is None:
            self._cache = build_official_live_strategy_overrides()
        return self._cache

    def __getitem__(self, key: str) -> Any:
        return self._load()[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._load())

    def __len__(self) -> int:
        return len(self._load())

    def copy(self) -> dict[str, Any]:
        return dict(self._load())


OFFICIAL_LIVE_STRATEGY_OVERRIDES: Mapping[str, Any] = _LazyOfficialLiveStrategyOverrides()

OFFICIAL_LIVE_REFERENCE_METRICS: dict[str, dict[str, float]] = {
    "stage021_q_full_20180101_20260529": {
        "end_equity": 15_135_800.10,
        "total_return_pct": 9_990.5334,
        "max_dd_pct": -44.9033,
        "sharpe": 1.495411,
        "total_slippage": 1_571_580.0,
        "total_trade_count": 821.0,
        "win_rate_pct": 52.8467,
        "broker10_peak_margin_to_equity_pct": 99.6724,
        "days_over_100pct": 0.0,
    },
    "full_20180102_20260529_stage847_c9": {
        "end_equity": 51_297_786.20,
        "total_return_pct": 16_999.2621,
        "max_dd_pct": -41.6664,
        "sharpe": 1.6404,
        "total_slippage": 3_646_200.0,
        "total_trade_count": 790.0,
        "win_rate_pct": 53.5299,
        "broker10_peak_margin_to_equity_pct": 115.0507,
        "stage896_worst_rolling3y_dd_pct": -56.1208,
        "stage899_worst_monthly_start_dd_pct": -58.0872,
    },
    "stage928_15w_halfyear_to_20260615_mature_windows": {
        "window_count": 18.0,
        "positive_window_count": 16.0,
        "mature_252d_window_count": 16.0,
        "mature_252d_positive_window_count": 16.0,
        "mature_252d_median_total_return_pct": 976.9086,
        "mature_252d_min_total_return_pct": 79.5363,
        "mature_252d_worst_max_dd_pct": -59.7794,
        "mature_252d_dd40_fail_count": 7.0,
        "mature_252d_dd50_fail_count": 2.0,
        "mature_252d_broker100_fail_count": 6.0,
        "mature_252d_survival_fail_count": 0.0,
        "mature_252d_peak_broker10_margin_to_equity_pct": 112.8549,
        "negative_short_windows": 2.0,
        "worst_short_window_total_return_pct": -19.48,
    },
    "previous_live_full_2020_2026_stage372": {
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
    "previous_live_latest_2026_to_20260604_stage372": {
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
        "ruleset_version": OFFICIAL_LIVE_RULESET_VERSION,
        "previous_ruleset_version": OFFICIAL_LIVE_PREVIOUS_RULESET_VERSION,
        "source_stage": OFFICIAL_LIVE_SOURCE_STAGE,
        "profile_name": OFFICIAL_LIVE_PROFILE_NAME,
        "base_profile_name": OFFICIAL_LIVE_BASE_PROFILE_NAME,
        "previous_version": OFFICIAL_LIVE_PREVIOUS_VERSION,
        "previous_profile_name": OFFICIAL_LIVE_PREVIOUS_PROFILE_NAME,
        "role": OFFICIAL_LIVE_ROLE,
        "capital": OFFICIAL_LIVE_CAPITAL,
        "capital_label": OFFICIAL_LIVE_CAPITAL_LABEL,
        "ai_eligibility_path": str(OFFICIAL_LIVE_AI_ELIGIBILITY_PATH),
        "ai_eligibility_logical_path": OFFICIAL_LIVE_AI_LOGICAL_PATH,
        "material_release_id": OFFICIAL_LIVE_MATERIAL_RELEASE_ID,
        "material_release_commit": OFFICIAL_LIVE_MATERIAL_RELEASE_COMMIT,
        "material_manifest_sha256": OFFICIAL_LIVE_MATERIAL_MANIFEST_SHA256,
        "summary_path": str(OFFICIAL_LIVE_SUMMARY_PATH),
        "signal_plan_path": str(OFFICIAL_LIVE_SIGNAL_PLAN_PATH),
        "current_positions_path": str(OFFICIAL_LIVE_CURRENT_POSITIONS_PATH),
        "pending_orders_path": str(OFFICIAL_LIVE_PENDING_ORDERS_PATH),
        "report_path": str(OFFICIAL_LIVE_REPORT_PATH),
        "execution_policy": OFFICIAL_LIVE_EXECUTION_POLICY,
        "strategy_overrides": OFFICIAL_LIVE_STRATEGY_OVERRIDES,
        "reference_metrics": OFFICIAL_LIVE_REFERENCE_METRICS,
        "primary_official_candidate": {
            "version": OFFICIAL_CANDIDATE_PRIMARY_VERSION,
            "config_module": OFFICIAL_CANDIDATE_PRIMARY_CONFIG_MODULE,
            "live_default": bool(
                OFFICIAL_CANDIDATE_VERSIONS.get(OFFICIAL_CANDIDATE_PRIMARY_VERSION, {}).get("live_default", False)
            ),
        },
        "official_candidates": OFFICIAL_CANDIDATE_VERSIONS,
        "legacy_stage78": {
            "version": LEGACY_STAGE78_VERSION,
            "status": LEGACY_STAGE78_STATUS,
        },
        "legacy_stage372_live": {
            "version": LEGACY_STAGE372_LIVE_VERSION,
            "status": LEGACY_STAGE372_LIVE_STATUS,
            "profile_name": LEGACY_STAGE372_LIVE_PROFILE_NAME,
        },
        "legacy_stage847_c9_30w_live": {
            "version": LEGACY_STAGE847_C9_30W_LIVE_VERSION,
            "status": LEGACY_STAGE847_C9_30W_LIVE_STATUS,
            "profile_name": LEGACY_STAGE847_C9_30W_PROFILE_NAME,
        },
    }


def _float_or_default(value: Any, default: float) -> float:
    if value is None or value == "":
        return default
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if result != result:
        return default
    return result


def build_official_live_risk_snapshot(summary: dict[str, Any]) -> dict[str, Any]:
    variant = summary.get("current_variant", {}) or {}
    deployable = int(_float_or_default(variant.get("deployable_pass"), 0.0)) == 1
    days_over_100 = int(_float_or_default(variant.get("days_over_100pct"), 0.0))
    days_over_90 = int(_float_or_default(variant.get("days_over_90pct"), 0.0))
    max_margin = _float_or_default(variant.get("max_broker10_margin_to_equity_pct"), 999.0)
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
        "drawdown_pct_abs": abs(_float_or_default(variant.get("max_dd_pct"), 0.0)),
        "daily_loss_cash": 0.0,
        "net_pnl": 0.0,
        "balance": _float_or_default(variant.get("end_equity"), 0.0),
        "execution_adverse_cash": 0.0,
    }
