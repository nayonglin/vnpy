from __future__ import annotations

from pathlib import Path
from typing import Any

from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import (
    AI_SATELLITE_POST_SIGNAL_STRATEGY_NAME,
    FU_PRODUCT,
    build_ai_satellite_post_signal_eligibility,
    build_static18_plus_fu_universe,
)
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import (
    CORR20_06_08_FLOOR35_OVERRIDES,
)


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

OFFICIAL_CANDIDATE_STAGE777_VERSION: str = "official_candidate_stage777_50w_am41_oi08_old_ai_v1"
OFFICIAL_CANDIDATE_STAGE777_ALIAS: str = "Stage777-50w-AM41-OI0.8-oldAI"
OFFICIAL_CANDIDATE_STAGE777_SOURCE_STAGE: str = "Stage777"
OFFICIAL_CANDIDATE_STAGE777_FAMILY_VERSION: str = "stage777_50w_am41_oi08_old_ai"
OFFICIAL_CANDIDATE_STAGE777_PROFILE_NAME: str = "stage777_50w_am41_oi08_old_ai"
OFFICIAL_CANDIDATE_STAGE777_ROLE: str = "official_candidate_high_return_high_drawdown"
OFFICIAL_CANDIDATE_STAGE777_STATUS: str = "official_candidate_not_live_default"
OFFICIAL_CANDIDATE_STAGE777_CAPITAL: float = 500_000.0
OFFICIAL_CANDIDATE_STAGE777_CAPITAL_LABEL: str = "50w"
OFFICIAL_CANDIDATE_STAGE777_BASE_RISK_MULTIPLIER: float = 0.40
OFFICIAL_CANDIDATE_STAGE777_OI_RESTORE_MULTIPLIER: float = 2.00
OFFICIAL_CANDIDATE_STAGE777_EFFECTIVE_OI_RISK_MULTIPLIER: float = 0.80
OFFICIAL_CANDIDATE_STAGE777_ARRAY_MANAGER_SIZE: int = 41
OFFICIAL_CANDIDATE_STAGE777_ARRAY_MANAGER_READY_FLOOR: int = 40
OFFICIAL_CANDIDATE_STAGE777_MAX_CONCURRENT_POSITIONS: int = 4
OFFICIAL_CANDIDATE_STAGE777_STREAK_RISK_MULTIPLIERS: str = "1.0,1.0,1.0,1.0"
OFFICIAL_CANDIDATE_STAGE777_PROFIT_SHIELD_MODE: str = "profit_only"
OFFICIAL_CANDIDATE_STAGE777_STRATEGY_CLASS: str = (
    "analyze_qmt_roll_stage772_am40_80_120_oi_monthly.QmtRollPortfolioStrategyExactAm"
)

OFFICIAL_CANDIDATE_STAGE777_REFERENCE_METRICS: dict[str, Any] = {
    "monthly_start_2018_2026_stage777": {
        "sample_count": 101.0,
        "positive_count": 96.0,
        "median_return_pct": 170.7890,
        "p10_return_pct": 56.2340,
        "min_return_pct": -7.6440,
        "median_max_dd_pct": -35.3554,
        "worst_max_dd_pct": -50.1325,
        "dd40_fail_count": 47.0,
        "dd50_fail_count": 1.0,
        "median_sharpe": 1.3341,
        "total_trade_count": 29_862.0,
    },
    "monthly_start_mature_2018_2026_stage777": {
        "sample_count": 89.0,
        "positive_count": 89.0,
        "median_return_pct": 272.3490,
        "p10_return_pct": 83.7680,
        "min_return_pct": 56.2340,
        "median_max_dd_pct": -43.5538,
        "worst_max_dd_pct": -50.1325,
        "dd40_fail_count": 47.0,
        "dd50_fail_count": 1.0,
        "median_sharpe": 1.3847,
    },
    "yearly_start_2018_2026_stage777_old_ai": {
        "sample_count": 9.0,
        "positive_count": 8.0,
        "median_return_pct": 179.5130,
        "min_return_pct": -4.9740,
        "worst_max_dd_pct": -49.4213,
        "dd40_fail_count": 4.0,
        "dd50_fail_count": 0.0,
    },
    "yearly_start_mature_2018_2025_stage777_old_ai": {
        "sample_count": 8.0,
        "positive_count": 8.0,
        "median_return_pct": 653.1200,
        "p10_return_pct": 83.3988,
        "min_return_pct": 82.3880,
        "median_max_dd_pct": -42.0124,
        "worst_max_dd_pct": -49.4213,
        "dd40_fail_count": 4.0,
        "dd50_fail_count": 0.0,
    },
    "yearly_rows_stage791": {
        "2018-01": {
            "end_equity": 18_251_265.0,
            "total_return_pct": 3550.2530,
            "max_dd_pct": -49.4213,
            "sharpe": 1.3671,
            "trade_count": 648.0,
            "total_slippage": 1_145_460.0,
        },
        "2019-01": {
            "end_equity": 21_189_950.0,
            "total_return_pct": 4137.9900,
            "max_dd_pct": -49.3661,
            "sharpe": 1.5261,
            "trade_count": 602.0,
            "total_slippage": 1_295_330.0,
        },
        "2020-01": {
            "end_equity": 12_614_810.0,
            "total_return_pct": 2422.9620,
            "max_dd_pct": -49.1145,
            "sharpe": 1.4717,
            "trade_count": 512.0,
        },
        "2021-01": {
            "end_equity": 6_133_635.0,
            "total_return_pct": 1126.7270,
            "max_dd_pct": -48.6695,
            "sharpe": 1.3478,
            "trade_count": 382.0,
        },
        "2022-01": {
            "end_equity": 1_106_350.0,
            "total_return_pct": 121.2700,
            "max_dd_pct": -35.3554,
            "sharpe": 0.7607,
            "trade_count": 262.0,
        },
        "2023-01": {
            "end_equity": 1_397_565.0,
            "total_return_pct": 179.5130,
            "max_dd_pct": -22.1100,
            "sharpe": 1.2604,
            "trade_count": 178.0,
        },
        "2024-01": {
            "end_equity": 911_940.0,
            "total_return_pct": 82.3880,
            "max_dd_pct": -23.3469,
            "sharpe": 1.0578,
            "trade_count": 122.0,
        },
        "2025-01": {
            "end_equity": 919_160.0,
            "total_return_pct": 83.8320,
            "max_dd_pct": -16.2147,
            "sharpe": 1.4744,
            "trade_count": 69.0,
        },
        "2026-01": {
            "end_equity": 475_130.0,
            "total_return_pct": -4.9740,
            "max_dd_pct": -15.5310,
            "sharpe": -0.1741,
            "trade_count": 22.0,
        },
    },
}

OFFICIAL_CANDIDATE_STAGE777_PROMOTION_BOUNDARY: dict[str, Any] = {
    "promoted_to": "official_candidate",
    "live_default": False,
    "current_live_default_remains": "official_live_stage372_20w_recovery_sleeve",
    "not_direct_live_reason": (
        "Stage777 keeps a strong right tail, but the early-start drawdown cluster is still "
        "near 49% and the exact-AM41 implementation is a research wrapper."
    ),
    "must_pass_before_live": [
        "fresh shadow run using the current trade calendar and latest daily data",
        "candidate execution dry-run and order reconciliation",
        "explicit risk review for DD40/DD50 tolerance and 500k capital assumption",
        "engineering promotion of exact AM41 from research wrapper if selected for live",
    ],
}


def build_official_candidate_stage777_paths() -> tuple[Path, Path]:
    """Build and return the frozen product universe and old official AI eligibility files."""
    universe_path = build_static18_plus_fu_universe()
    eligibility_path = build_ai_satellite_post_signal_eligibility()
    return universe_path, eligibility_path


def _build_official_candidate_stage777_overrides(
    universe_path: Path,
    eligibility_path: Path,
) -> dict[str, Any]:
    return {
        **CORR20_06_08_FLOOR35_OVERRIDES,
        "product_universe_csv_path": str(universe_path),
        "max_concurrent_positions": OFFICIAL_CANDIDATE_STAGE777_MAX_CONCURRENT_POSITIONS,
        "enable_ai_product_pool_filter": True,
        "ai_product_pool_eligibility_path": str(eligibility_path),
        "ai_product_pool_strategy": AI_SATELLITE_POST_SIGNAL_STRATEGY_NAME,
        "streak_risk_state_excluded_products": FU_PRODUCT,
        "streak_risk_state_exclusion_mode": OFFICIAL_CANDIDATE_STAGE777_PROFIT_SHIELD_MODE,
        "streak_risk_multipliers": OFFICIAL_CANDIDATE_STAGE777_STREAK_RISK_MULTIPLIERS,
        "enable_streak_entry_structure_risk_recovery": False,
        "enable_recovery_sleeve": False,
        "enable_oi_price_confirm_risk_restore": True,
        "oi_price_confirm_risk_restore_multiplier": OFFICIAL_CANDIDATE_STAGE777_OI_RESTORE_MULTIPLIER,
        "oi_price_confirm_risk_restore_entry_contexts": "flat_entry,reverse_entry,rollover_reopen",
        "array_manager_size_floor": OFFICIAL_CANDIDATE_STAGE777_ARRAY_MANAGER_READY_FLOOR,
        "research_exact_array_manager_size": OFFICIAL_CANDIDATE_STAGE777_ARRAY_MANAGER_SIZE,
    }


def build_official_candidate_stage777_overrides() -> dict[str, Any]:
    """Return strategy overrides for the frozen Stage777 official candidate profile."""
    universe_path, eligibility_path = build_official_candidate_stage777_paths()
    return _build_official_candidate_stage777_overrides(universe_path, eligibility_path)


def build_official_candidate_stage777_manifest() -> dict[str, Any]:
    """Build a reproducible manifest for the Stage777 official candidate."""
    universe_path, eligibility_path = build_official_candidate_stage777_paths()
    strategy_overrides = _build_official_candidate_stage777_overrides(universe_path, eligibility_path)
    return {
        "alias": OFFICIAL_CANDIDATE_STAGE777_ALIAS,
        "version": OFFICIAL_CANDIDATE_STAGE777_VERSION,
        "family_version": OFFICIAL_CANDIDATE_STAGE777_FAMILY_VERSION,
        "source_stage": OFFICIAL_CANDIDATE_STAGE777_SOURCE_STAGE,
        "profile_name": OFFICIAL_CANDIDATE_STAGE777_PROFILE_NAME,
        "role": OFFICIAL_CANDIDATE_STAGE777_ROLE,
        "status": OFFICIAL_CANDIDATE_STAGE777_STATUS,
        "capital": OFFICIAL_CANDIDATE_STAGE777_CAPITAL,
        "capital_label": OFFICIAL_CANDIDATE_STAGE777_CAPITAL_LABEL,
        "base_risk_multiplier": OFFICIAL_CANDIDATE_STAGE777_BASE_RISK_MULTIPLIER,
        "oi_restore_multiplier": OFFICIAL_CANDIDATE_STAGE777_OI_RESTORE_MULTIPLIER,
        "effective_oi_risk_multiplier": OFFICIAL_CANDIDATE_STAGE777_EFFECTIVE_OI_RISK_MULTIPLIER,
        "array_manager_size": OFFICIAL_CANDIDATE_STAGE777_ARRAY_MANAGER_SIZE,
        "strategy_class": OFFICIAL_CANDIDATE_STAGE777_STRATEGY_CLASS,
        "product_universe_csv_path": str(universe_path),
        "ai_product_pool_eligibility_path": str(eligibility_path),
        "ai_product_pool_strategy": AI_SATELLITE_POST_SIGNAL_STRATEGY_NAME,
        "strategy_overrides": strategy_overrides,
        "reference_metrics": OFFICIAL_CANDIDATE_STAGE777_REFERENCE_METRICS,
        "promotion_boundary": OFFICIAL_CANDIDATE_STAGE777_PROMOTION_BOUNDARY,
    }
