from __future__ import annotations

from pathlib import Path
from typing import Any

import qmt_roll_official_candidate_stage813_config as stage813_cfg


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

OFFICIAL_CANDIDATE_STAGE819_30W_VERSION: str = (
    "official_candidate_stage819_30w_am41_oi08_old_ai_long_tighter_stop_rsi95_v1"
)
OFFICIAL_CANDIDATE_STAGE819_30W_ALIAS: str = (
    "Stage819-30w-AM41-OI0.8-oldAI-longTightStop-RSI95"
)
OFFICIAL_CANDIDATE_STAGE819_30W_SOURCE_STAGE: str = "Stage819"
OFFICIAL_CANDIDATE_STAGE819_30W_BASE_STAGE: str = "Stage813"
OFFICIAL_CANDIDATE_STAGE819_30W_FAMILY_VERSION: str = "stage813_capital_30w"
OFFICIAL_CANDIDATE_STAGE819_30W_PROFILE_NAME: str = (
    "stage819_30w_stage813_am41_oi08_old_ai_long_tight_rsi95"
)
OFFICIAL_CANDIDATE_STAGE819_30W_ROLE: str = "official_candidate_operator_promoted_not_live_default"
OFFICIAL_CANDIDATE_STAGE819_30W_STATUS: str = "official_candidate_not_live_default_watch"
OFFICIAL_CANDIDATE_STAGE819_30W_CAPITAL: float = 300_000.0
OFFICIAL_CANDIDATE_STAGE819_30W_CAPITAL_LABEL: str = "30w"

OFFICIAL_CANDIDATE_STAGE819_30W_REFERENCE_METRICS: dict[str, Any] = {
    "yearly_start_2018_2026_stage819_30w": {
        "sample_count": 9.0,
        "positive_count": 8.0,
        "return_win_vs_stage813_50w_count": 8.0,
        "dd_win_vs_stage813_50w_count": 6.0,
        "sharpe_win_vs_stage813_50w_count": 8.0,
        "double_win_vs_stage813_50w_count": 6.0,
        "median_return_delta_vs_50w_pp": 157.7107,
        "median_dd_delta_vs_50w_pp": 0.3944,
        "median_sharpe_delta_vs_50w": 0.1055,
        "dd40_fail_count": 4.0,
        "dd50_fail_count": 1.0,
        "broker100_fail_count": 0.0,
        "survival_fail_count": 0.0,
    },
    "yearly_start_mature_2018_2025_stage819_30w": {
        "sample_count": 8.0,
        "positive_count": 8.0,
        "return_win_vs_stage813_50w_count": 7.0,
        "dd_win_vs_stage813_50w_count": 5.0,
        "sharpe_win_vs_stage813_50w_count": 7.0,
        "double_win_vs_stage813_50w_count": 5.0,
        "median_return_delta_vs_50w_pp": 402.8402,
        "median_dd_delta_vs_50w_pp": 0.2546,
        "median_sharpe_delta_vs_50w": 0.0944,
    },
    "rolling_3y_annual_step_stage821_30w": {
        "sample_count": 7.0,
        "positive_count": 7.0,
        "median_return_pct": 352.8550,
        "min_return_pct": 97.9583,
        "max_return_pct": 1885.8950,
        "median_max_dd_pct": -32.8556,
        "worst_max_dd_pct": -44.6223,
        "dd30_fail_count": 5.0,
        "dd40_fail_count": 2.0,
        "dd50_fail_count": 0.0,
        "median_sharpe": 1.6721,
        "return_win_vs_50w_count": 4.0,
        "dd_win_vs_50w_count": 5.0,
        "sharpe_win_vs_50w_count": 4.0,
    },
    "rolling_3y_monthly_step_stage822_30w": {
        "sample_count": 66.0,
        "positive_count": 66.0,
        "median_return_pct": 643.7725,
        "p10_return_pct": 75.4383,
        "min_return_pct": 28.9200,
        "max_return_pct": 3659.4817,
        "median_max_dd_pct": -37.6836,
        "worst_max_dd_pct": -56.7501,
        "dd30_fail_count": 52.0,
        "dd40_fail_count": 25.0,
        "dd50_fail_count": 2.0,
        "median_sharpe": 1.6939,
        "p10_sharpe": 0.7328,
        "total_slippage": 10_976_430.0,
        "total_trade_count": 17_530.0,
        "return_win_vs_50w_count": 30.0,
        "dd_win_vs_50w_count": 32.0,
        "sharpe_win_vs_50w_count": 35.0,
        "return_win_vs_20w_count": 41.0,
        "dd_win_vs_20w_count": 18.0,
        "sharpe_win_vs_20w_count": 38.0,
    },
    "representative_yearly_rows_stage819_30w": {
        "2018-01": {
            "end_equity": 26_322_730.0,
            "total_return_pct": 8674.2433,
            "max_dd_pct": -54.7546,
            "sharpe": 1.4363,
            "total_slippage": 2_149_150.0,
            "trade_count": 666.0,
            "win_rate_pct": 53.1069,
        },
        "2020-01": {
            "end_equity": 18_787_535.0,
            "total_return_pct": 6162.5117,
            "max_dd_pct": -44.6223,
            "sharpe": 1.5941,
            "total_slippage": 1_489_460.0,
            "trade_count": 529.0,
            "win_rate_pct": 54.7544,
        },
        "2022-01": {
            "end_equity": 1_060_100.0,
            "total_return_pct": 253.3667,
            "max_dd_pct": -37.8438,
            "sharpe": 0.9661,
            "total_slippage": 73_270.0,
            "trade_count": 272.0,
            "win_rate_pct": 50.5282,
        },
        "2026-01": {
            "end_equity": 265_800.0,
            "total_return_pct": -11.4000,
            "max_dd_pct": -14.8955,
            "sharpe": -1.3022,
            "total_slippage": 3_680.0,
            "trade_count": 24.0,
            "win_rate_pct": 44.8276,
        },
    },
}

OFFICIAL_CANDIDATE_STAGE819_30W_PROMOTION_BOUNDARY: dict[str, Any] = {
    "promoted_to": "official_candidate_by_operator_request",
    "live_default": False,
    "current_live_default_remains": "official_live_stage372_20w_recovery_sleeve",
    "base_candidate": stage813_cfg.OFFICIAL_CANDIDATE_STAGE813_VERSION,
    "not_direct_live_reason": (
        "Stage819 only changes account_capital/c3_capital to 300000. Stage819 yearly and "
        "Stage821 annual-step rolling results are strong, but Stage822 monthly 3-year "
        "rolling validation did not show stable dominance over the 50w candidate and "
        "still has DD50 tail failures."
    ),
    "must_pass_before_live": [
        "fresh official-candidate shadow run on the latest completed trading day",
        "candidate execution dry-run and broker-state reconciliation",
        "explicit risk review for DD40/DD50 tolerance under 30w capital",
        "same-window comparison against current live Stage372 20w before any live-default change",
        "engineering promotion of the Stage804 long tighter initial stop wrapper if selected for live",
    ],
}


def build_official_candidate_stage819_30w_paths() -> tuple[Path, Path]:
    """Build and return the frozen product universe and old official AI eligibility files."""
    return stage813_cfg.build_official_candidate_stage813_paths()


def _build_official_candidate_stage819_30w_overrides(
    universe_path: Path,
    eligibility_path: Path,
) -> dict[str, Any]:
    overrides = stage813_cfg._build_official_candidate_stage813_overrides(universe_path, eligibility_path)
    return {
        **overrides,
        "account_capital": OFFICIAL_CANDIDATE_STAGE819_30W_CAPITAL,
        "c3_capital": OFFICIAL_CANDIDATE_STAGE819_30W_CAPITAL,
    }


def build_official_candidate_stage819_30w_overrides() -> dict[str, Any]:
    """Return strategy overrides for the frozen Stage819 30w official candidate profile."""
    universe_path, eligibility_path = build_official_candidate_stage819_30w_paths()
    return _build_official_candidate_stage819_30w_overrides(universe_path, eligibility_path)


def build_official_candidate_stage819_30w_manifest() -> dict[str, Any]:
    """Build a reproducible manifest for the Stage819 30w official candidate."""
    universe_path, eligibility_path = build_official_candidate_stage819_30w_paths()
    strategy_overrides = _build_official_candidate_stage819_30w_overrides(universe_path, eligibility_path)
    return {
        "alias": OFFICIAL_CANDIDATE_STAGE819_30W_ALIAS,
        "version": OFFICIAL_CANDIDATE_STAGE819_30W_VERSION,
        "family_version": OFFICIAL_CANDIDATE_STAGE819_30W_FAMILY_VERSION,
        "source_stage": OFFICIAL_CANDIDATE_STAGE819_30W_SOURCE_STAGE,
        "base_stage": OFFICIAL_CANDIDATE_STAGE819_30W_BASE_STAGE,
        "profile_name": OFFICIAL_CANDIDATE_STAGE819_30W_PROFILE_NAME,
        "role": OFFICIAL_CANDIDATE_STAGE819_30W_ROLE,
        "status": OFFICIAL_CANDIDATE_STAGE819_30W_STATUS,
        "capital": OFFICIAL_CANDIDATE_STAGE819_30W_CAPITAL,
        "capital_label": OFFICIAL_CANDIDATE_STAGE819_30W_CAPITAL_LABEL,
        "base_risk_multiplier": stage813_cfg.OFFICIAL_CANDIDATE_STAGE813_BASE_RISK_MULTIPLIER,
        "oi_restore_multiplier": stage813_cfg.OFFICIAL_CANDIDATE_STAGE813_OI_RESTORE_MULTIPLIER,
        "effective_oi_risk_multiplier": (
            stage813_cfg.OFFICIAL_CANDIDATE_STAGE813_EFFECTIVE_OI_RISK_MULTIPLIER
        ),
        "array_manager_size": stage813_cfg.OFFICIAL_CANDIDATE_STAGE813_ARRAY_MANAGER_SIZE,
        "strategy_class": stage813_cfg.OFFICIAL_CANDIDATE_STAGE813_STRATEGY_CLASS,
        "product_universe_csv_path": str(universe_path),
        "ai_product_pool_eligibility_path": str(eligibility_path),
        "ai_product_pool_strategy": stage813_cfg.AI_SATELLITE_POST_SIGNAL_STRATEGY_NAME,
        "strategy_overrides": strategy_overrides,
        "reference_metrics": OFFICIAL_CANDIDATE_STAGE819_30W_REFERENCE_METRICS,
        "promotion_boundary": OFFICIAL_CANDIDATE_STAGE819_30W_PROMOTION_BOUNDARY,
    }
