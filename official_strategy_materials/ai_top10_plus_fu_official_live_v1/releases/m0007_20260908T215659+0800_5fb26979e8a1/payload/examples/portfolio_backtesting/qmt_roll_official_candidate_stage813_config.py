from __future__ import annotations

from pathlib import Path
from typing import Any

import qmt_roll_official_candidate_stage777_config as stage777_cfg
from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import (
    AI_SATELLITE_POST_SIGNAL_STRATEGY_NAME,
)


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

OFFICIAL_CANDIDATE_STAGE813_VERSION: str = (
    "official_candidate_stage813_50w_am41_oi08_old_ai_long_tighter_stop_rsi95_v1"
)
OFFICIAL_CANDIDATE_STAGE813_ALIAS: str = "Stage813-50w-AM41-OI0.8-oldAI-longTightStop-RSI95"
OFFICIAL_CANDIDATE_STAGE813_SOURCE_STAGE: str = "Stage813"
OFFICIAL_CANDIDATE_STAGE813_FAMILY_VERSION: str = "stage813_stage804_rsi_partial_exit"
OFFICIAL_CANDIDATE_STAGE813_PROFILE_NAME: str = "stage813_50w_am41_oi08_old_ai_long_tight_rsi95"
OFFICIAL_CANDIDATE_STAGE813_ROLE: str = "official_candidate_aggressive_not_live_default"
OFFICIAL_CANDIDATE_STAGE813_STATUS: str = "official_candidate_not_live_default"
OFFICIAL_CANDIDATE_STAGE813_CAPITAL: float = stage777_cfg.OFFICIAL_CANDIDATE_STAGE777_CAPITAL
OFFICIAL_CANDIDATE_STAGE813_CAPITAL_LABEL: str = stage777_cfg.OFFICIAL_CANDIDATE_STAGE777_CAPITAL_LABEL
OFFICIAL_CANDIDATE_STAGE813_BASE_RISK_MULTIPLIER: float = (
    stage777_cfg.OFFICIAL_CANDIDATE_STAGE777_BASE_RISK_MULTIPLIER
)
OFFICIAL_CANDIDATE_STAGE813_OI_RESTORE_MULTIPLIER: float = (
    stage777_cfg.OFFICIAL_CANDIDATE_STAGE777_OI_RESTORE_MULTIPLIER
)
OFFICIAL_CANDIDATE_STAGE813_EFFECTIVE_OI_RISK_MULTIPLIER: float = (
    stage777_cfg.OFFICIAL_CANDIDATE_STAGE777_EFFECTIVE_OI_RISK_MULTIPLIER
)
OFFICIAL_CANDIDATE_STAGE813_ARRAY_MANAGER_SIZE: int = (
    stage777_cfg.OFFICIAL_CANDIDATE_STAGE777_ARRAY_MANAGER_SIZE
)
OFFICIAL_CANDIDATE_STAGE813_ARRAY_MANAGER_READY_FLOOR: int = (
    stage777_cfg.OFFICIAL_CANDIDATE_STAGE777_ARRAY_MANAGER_READY_FLOOR
)
OFFICIAL_CANDIDATE_STAGE813_MAX_CONCURRENT_POSITIONS: int = (
    stage777_cfg.OFFICIAL_CANDIDATE_STAGE777_MAX_CONCURRENT_POSITIONS
)
OFFICIAL_CANDIDATE_STAGE813_STREAK_RISK_MULTIPLIERS: str = (
    stage777_cfg.OFFICIAL_CANDIDATE_STAGE777_STREAK_RISK_MULTIPLIERS
)
OFFICIAL_CANDIDATE_STAGE813_STRATEGY_CLASS: str = (
    "analyze_qmt_roll_stage804_stage777_long_tighter_initial_stop_yearly."
    "QmtRollPortfolioStrategyLongTighterInitialStop"
)

OFFICIAL_CANDIDATE_STAGE813_LONG_TIGHTER_INITIAL_STOP: bool = True
OFFICIAL_CANDIDATE_STAGE813_RSI_PROFIT_LOCK_ENABLED: bool = True
OFFICIAL_CANDIDATE_STAGE813_RSI_PARTIAL_EXIT_THRESHOLD: float = 95.0
OFFICIAL_CANDIDATE_STAGE813_RSI_PARTIAL_EXIT_RATIO: float = 0.5
OFFICIAL_CANDIDATE_STAGE813_TRAILING_STOP_ENABLED: bool = True
OFFICIAL_CANDIDATE_STAGE813_TRAILING_STOP_PCT: float = 0.0
OFFICIAL_CANDIDATE_STAGE813_PROFIT_LOCK_TIERS: str = ""

OFFICIAL_CANDIDATE_STAGE813_REFERENCE_METRICS: dict[str, Any] = {
    "stage813_corrected_on_vs_off_yearly": {
        "sample_count": 9.0,
        "return_win_count": 5.0,
        "dd_win_count": 3.0,
        "sharpe_win_count": 6.0,
        "double_win_count": 2.0,
        "median_return_delta_pp": 10.8440,
        "median_dd_delta_pp": 0.0,
        "median_sharpe_delta": 0.0226,
        "base_dd40_fail_count": 4.0,
        "candidate_dd40_fail_count": 4.0,
        "base_dd50_fail_count": 2.0,
        "candidate_dd50_fail_count": 2.0,
        "rsi_partial_exit_count": 31.0,
        "rsi_partial_exit_volume": 1_520.0,
    },
    "stage813_corrected_on_vs_off_mature_2018_2025": {
        "sample_count": 8.0,
        "return_win_count": 5.0,
        "dd_win_count": 3.0,
        "sharpe_win_count": 6.0,
        "double_win_count": 2.0,
        "median_return_delta_pp": 13.6920,
        "median_dd_delta_pp": 0.0,
        "median_sharpe_delta": 0.0311,
        "base_dd40_fail_count": 4.0,
        "candidate_dd40_fail_count": 4.0,
        "base_dd50_fail_count": 2.0,
        "candidate_dd50_fail_count": 2.0,
    },
    "yearly_rows_stage813_rsi_on": {
        "2018-01": {
            "end_equity": 26_293_495.0,
            "total_return_pct": 5_158.6990,
            "max_dd_pct": -46.5025,
            "sharpe": 1.3618,
            "trade_count": 673.0,
            "total_slippage": 2_029_740.0,
        },
        "2019-01": {
            "end_equity": 30_146_230.0,
            "total_return_pct": 5_929.2460,
            "max_dd_pct": -53.9421,
            "sharpe": 1.4465,
            "trade_count": 620.0,
            "total_slippage": 2_445_290.0,
        },
        "2020-01": {
            "end_equity": 27_577_760.0,
            "total_return_pct": 5_415.5520,
            "max_dd_pct": -56.0975,
            "sharpe": 1.5525,
            "trade_count": 525.0,
            "total_slippage": 2_296_860.0,
        },
        "2021-01": {
            "end_equity": 6_393_110.0,
            "total_return_pct": 1_178.6220,
            "max_dd_pct": -42.9311,
            "sharpe": 1.2905,
            "trade_count": 386.0,
            "total_slippage": 758_780.0,
        },
        "2022-01": {
            "end_equity": 978_280.0,
            "total_return_pct": 95.6560,
            "max_dd_pct": -33.6344,
            "sharpe": 0.6541,
            "trade_count": 272.0,
        },
        "2023-01": {
            "end_equity": 841_395.0,
            "total_return_pct": 68.2790,
            "max_dd_pct": -28.6321,
            "sharpe": 0.7687,
            "trade_count": 179.0,
        },
        "2024-01": {
            "end_equity": 705_975.0,
            "total_return_pct": 41.1950,
            "max_dd_pct": -22.8831,
            "sharpe": 0.7296,
            "trade_count": 120.0,
        },
        "2025-01": {
            "end_equity": 909_715.0,
            "total_return_pct": 81.9430,
            "max_dd_pct": -17.9172,
            "sharpe": 1.3728,
            "trade_count": 72.0,
        },
        "2026-01": {
            "end_equity": 421_660.0,
            "total_return_pct": -15.6680,
            "max_dd_pct": -19.8127,
            "sharpe": -1.7638,
            "trade_count": 24.0,
        },
    },
}

OFFICIAL_CANDIDATE_STAGE813_PROMOTION_BOUNDARY: dict[str, Any] = {
    "promoted_to": "official_candidate_by_operator_request",
    "live_default": False,
    "current_live_default_remains": "official_live_stage372_20w_recovery_sleeve",
    "not_direct_live_reason": (
        "Stage813 improves some return and Sharpe paths after correcting the Stage812 "
        "baseline-contamination bug, but it does not reduce DD40/DD50 failures and still "
        "depends on the Stage804 research-only long tighter initial stop wrapper."
    ),
    "must_pass_before_live": [
        "fresh official-candidate shadow run on the latest completed trading day",
        "monthly/rolling validation against Stage777 and current live Stage372",
        "candidate execution dry-run and order reconciliation with broker state",
        "explicit risk review for DD40/DD50 tolerance and the 500k capital assumption",
        "engineering promotion of the Stage804 long tighter initial stop wrapper if selected for live",
    ],
}


def build_official_candidate_stage813_paths() -> tuple[Path, Path]:
    """Build and return the frozen product universe and old official AI eligibility files."""
    return stage777_cfg.build_official_candidate_stage777_paths()


def _build_official_candidate_stage813_overrides(
    universe_path: Path,
    eligibility_path: Path,
) -> dict[str, Any]:
    overrides = stage777_cfg._build_official_candidate_stage777_overrides(universe_path, eligibility_path)
    return {
        **overrides,
        "long_tighter_initial_stop": OFFICIAL_CANDIDATE_STAGE813_LONG_TIGHTER_INITIAL_STOP,
        "enable_rsi_partial_exit": OFFICIAL_CANDIDATE_STAGE813_RSI_PROFIT_LOCK_ENABLED,
        "rsi_partial_exit_threshold": OFFICIAL_CANDIDATE_STAGE813_RSI_PARTIAL_EXIT_THRESHOLD,
        "rsi_partial_exit_ratio": OFFICIAL_CANDIDATE_STAGE813_RSI_PARTIAL_EXIT_RATIO,
        "trailing_stop_enabled": OFFICIAL_CANDIDATE_STAGE813_TRAILING_STOP_ENABLED,
        "trailing_stop_pct": OFFICIAL_CANDIDATE_STAGE813_TRAILING_STOP_PCT,
        "profit_lock_tiers": OFFICIAL_CANDIDATE_STAGE813_PROFIT_LOCK_TIERS,
    }


def build_official_candidate_stage813_overrides() -> dict[str, Any]:
    """Return strategy overrides for the frozen Stage813 official candidate profile."""
    universe_path, eligibility_path = build_official_candidate_stage813_paths()
    return _build_official_candidate_stage813_overrides(universe_path, eligibility_path)


def build_official_candidate_stage813_manifest() -> dict[str, Any]:
    """Build a reproducible manifest for the Stage813 official candidate."""
    universe_path, eligibility_path = build_official_candidate_stage813_paths()
    strategy_overrides = _build_official_candidate_stage813_overrides(universe_path, eligibility_path)
    return {
        "alias": OFFICIAL_CANDIDATE_STAGE813_ALIAS,
        "version": OFFICIAL_CANDIDATE_STAGE813_VERSION,
        "family_version": OFFICIAL_CANDIDATE_STAGE813_FAMILY_VERSION,
        "source_stage": OFFICIAL_CANDIDATE_STAGE813_SOURCE_STAGE,
        "profile_name": OFFICIAL_CANDIDATE_STAGE813_PROFILE_NAME,
        "role": OFFICIAL_CANDIDATE_STAGE813_ROLE,
        "status": OFFICIAL_CANDIDATE_STAGE813_STATUS,
        "capital": OFFICIAL_CANDIDATE_STAGE813_CAPITAL,
        "capital_label": OFFICIAL_CANDIDATE_STAGE813_CAPITAL_LABEL,
        "base_risk_multiplier": OFFICIAL_CANDIDATE_STAGE813_BASE_RISK_MULTIPLIER,
        "oi_restore_multiplier": OFFICIAL_CANDIDATE_STAGE813_OI_RESTORE_MULTIPLIER,
        "effective_oi_risk_multiplier": OFFICIAL_CANDIDATE_STAGE813_EFFECTIVE_OI_RISK_MULTIPLIER,
        "array_manager_size": OFFICIAL_CANDIDATE_STAGE813_ARRAY_MANAGER_SIZE,
        "strategy_class": OFFICIAL_CANDIDATE_STAGE813_STRATEGY_CLASS,
        "product_universe_csv_path": str(universe_path),
        "ai_product_pool_eligibility_path": str(eligibility_path),
        "ai_product_pool_strategy": AI_SATELLITE_POST_SIGNAL_STRATEGY_NAME,
        "strategy_overrides": strategy_overrides,
        "reference_metrics": OFFICIAL_CANDIDATE_STAGE813_REFERENCE_METRICS,
        "promotion_boundary": OFFICIAL_CANDIDATE_STAGE813_PROMOTION_BOUNDARY,
    }
