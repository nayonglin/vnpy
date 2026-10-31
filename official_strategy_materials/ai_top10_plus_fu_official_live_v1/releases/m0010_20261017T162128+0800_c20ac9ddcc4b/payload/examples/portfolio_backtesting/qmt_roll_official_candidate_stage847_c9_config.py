from __future__ import annotations

from pathlib import Path
from typing import Any

import qmt_roll_official_candidate_stage819_30w_config as stage819_cfg
from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import (
    AI_SATELLITE_POST_SIGNAL_STRATEGY_NAME,
)


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

OFFICIAL_CANDIDATE_STAGE847_C9_VERSION: str = (
    "official_candidate_stage847_c9_30w_stage819_05r_stop_retry_once_v1"
)
OFFICIAL_CANDIDATE_STAGE847_C9_ALIAS: str = "Stage847-C9-30w-Stage819-0.5RStopRetry"
OFFICIAL_CANDIDATE_STAGE847_C9_SOURCE_STAGE: str = "Stage847"
OFFICIAL_CANDIDATE_STAGE847_C9_BASE_STAGE: str = "Stage819"
OFFICIAL_CANDIDATE_STAGE847_C9_FAMILY_VERSION: str = "stage819_c9_intraday_stop_retry"
OFFICIAL_CANDIDATE_STAGE847_C9_PROFILE_NAME: str = "stage847_c9_30w_stage819_05r_stop_retry"
OFFICIAL_CANDIDATE_STAGE847_C9_ROLE: str = "official_live_default_operator_override_high_risk"
OFFICIAL_CANDIDATE_STAGE847_C9_STATUS: str = "promoted_to_live_default_operator_override_high_risk_watch"
OFFICIAL_CANDIDATE_STAGE847_C9_CAPITAL: float = (
    stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_CAPITAL
)
OFFICIAL_CANDIDATE_STAGE847_C9_CAPITAL_LABEL: str = (
    stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_CAPITAL_LABEL
)
OFFICIAL_CANDIDATE_STAGE847_C9_STRATEGY_CLASS: str = (
    "analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine."
    "QmtRollPortfolioStrategyStage847C9StopRetry"
)

OFFICIAL_CANDIDATE_STAGE847_C9_INTRADAY_C2_STOP: bool = True
OFFICIAL_CANDIDATE_STAGE847_C9_BROKER10_MARGIN_CAP: bool = True
OFFICIAL_CANDIDATE_STAGE847_C9_STOP_RETRY_ENABLED: bool = True
OFFICIAL_CANDIDATE_STAGE847_C9_STOP_RETRY_R: float = 0.5
OFFICIAL_CANDIDATE_STAGE847_C9_MAX_RETRIES: int = 1

OFFICIAL_CANDIDATE_STAGE847_C9_REFERENCE_METRICS: dict[str, Any] = {
    "stage900_gap_backfill": {
        "missing_symbol_date_before": 8.0,
        "covered_symbol_date": 8.0,
        "local_cache_symbol_date": 6.0,
        "tqbacktest_symbol_date": 2.0,
        "patch_minute_bars": 2_999.0,
        "stage861_full_minute_bars_after_rebuild": 1_482_591.0,
        "stage861_full_minute_symbols_after_rebuild": 220.0,
    },
    "full_20180102_20260529_stage863_c9": {
        "end_equity": 51_297_786.20,
        "total_return_pct": 16_999.2621,
        "max_dd_pct": -41.6664,
        "sharpe": 1.6404,
        "total_slippage": 3_646_200.0,
        "total_trade_count": 790.0,
        "win_rate_pct": 53.5299,
        "broker10_peak_margin_to_equity_pct": 115.0507,
    },
    "stage896_halfyear_rolling3y_vs_stage372": {
        "complete_window_count": 7.0,
        "positive_count": 7.0,
        "median_return_pct": 562.2128,
        "worst_max_dd_pct": -56.1208,
        "dd40_fail_count": 4.0,
        "dd50_fail_count": 1.0,
        "broker100_fail_count": 2.0,
        "return_win_vs_stage372_count": 7.0,
        "sharpe_win_vs_stage372_count": 6.0,
        "dd_win_vs_stage372_count": 1.0,
        "broker10_win_vs_stage372_count": 0.0,
        "decision": "stage896_c9_right_tail_with_risk_tail_not_official_replacement",
    },
    "stage897_jan_jun_rolling1y": {
        "complete_window_count": 15.0,
        "positive_count": 12.0,
        "median_return_pct": 60.8912,
        "worst_max_dd_pct": -35.0696,
        "negative_windows": ["2018-01", "2018-06", "2022-01"],
    },
    "stage898_integrity_audit": {
        "metric_check_count": 225.0,
        "metric_fail_count": 0.0,
        "p0_fail_count": 0.0,
        "c9_open_missing_full_minute_entry_day_count": 0.0,
        "decision": "pass_with_execution_semantics_watch",
    },
    "stage899_monthly_time_to_positive": {
        "monthly_start_count": 101.0,
        "ever_positive_count": 99.0,
        "unresolved_count": 2.0,
        "unresolved_windows": ["2026-04", "2026-05"],
        "mature_1y_start_count": 89.0,
        "mature_1y_ever_positive_count": 89.0,
        "mature_1y_current_positive_count": 89.0,
        "longest_wait_calendar_days": 158.0,
        "longest_wait_trading_days": 108.0,
        "longest_wait_start": "2018-03",
        "worst_max_dd_pct": -58.0872,
    },
}

OFFICIAL_CANDIDATE_STAGE847_C9_PROMOTION_BOUNDARY: dict[str, Any] = {
    "promoted_to": "official_live_default_by_operator_override",
    "live_default": True,
    "current_live_default": "official_live_stage847_c9_15w_stage819_05r_stop_retry_once",
    "previous_live_default": "official_live_stage847_c9_30w_stage819_05r_stop_retry_once",
    "legacy_stage372_live_default": "official_live_stage372_20w_recovery_sleeve",
    "base_candidate": stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION,
    "operator_override_risk_note": (
        "C9 has cleared the Stage898 data P0 audit after Stage900 gap backfill and "
        "has strong right-tail return. It is promoted to live default by explicit "
        "operator request, while still carrying a high-risk account path: "
        "Stage896 has DD40/DD50/broker100 failures, Stage899 worst monthly-start "
        "drawdown is near 58%, and full-period broker10 peaks above 100%. Real "
        "orders still require fresh read-only checks, dry-run, broker-state "
        "reconciliation, and explicit order confirmation."
    ),
    "must_pass_before_real_orders": [
        "fresh C9 live-default shadow run on the latest completed trading day",
        "same-window A/C comparison against previous live Stage372 20w after candidate registration",
        "execution dry-run and broker-state reconciliation with order_api_called=0",
        "explicit risk acceptance for historical DD50 tail and broker10 over-100 behavior",
        "engineering promotion or explicit approval of the Stage847 C9 research wrapper import boundary",
        "cost/TCA stress and slippage sensitivity review under the 30w account assumption",
        "paper or shadow observation period before any SimNow or live submit gate",
        "CTP runtime/env read-only gate if and only if an execution test is explicitly requested",
    ],
}


def build_official_candidate_stage847_c9_paths() -> tuple[Path, Path]:
    """Build and return the frozen product universe and old official AI eligibility files."""
    return stage819_cfg.build_official_candidate_stage819_30w_paths()


def _build_official_candidate_stage847_c9_overrides(
    universe_path: Path,
    eligibility_path: Path,
) -> dict[str, Any]:
    overrides = stage819_cfg._build_official_candidate_stage819_30w_overrides(
        universe_path,
        eligibility_path,
    )
    return {
        **overrides,
        "enable_stage827_intraday_c2_stop": OFFICIAL_CANDIDATE_STAGE847_C9_INTRADAY_C2_STOP,
        "enable_stage830_broker10_margin_cap": OFFICIAL_CANDIDATE_STAGE847_C9_BROKER10_MARGIN_CAP,
        "enable_stage847_half_r_stop_retry": OFFICIAL_CANDIDATE_STAGE847_C9_STOP_RETRY_ENABLED,
        "stage847_stop_retry_r": OFFICIAL_CANDIDATE_STAGE847_C9_STOP_RETRY_R,
        "stage847_max_retries": OFFICIAL_CANDIDATE_STAGE847_C9_MAX_RETRIES,
    }


def build_official_candidate_stage847_c9_overrides() -> dict[str, Any]:
    """Return strategy overrides for the frozen Stage847 C9 official candidate profile."""
    universe_path, eligibility_path = build_official_candidate_stage847_c9_paths()
    return _build_official_candidate_stage847_c9_overrides(universe_path, eligibility_path)


def build_official_candidate_stage847_c9_manifest() -> dict[str, Any]:
    """Build a reproducible manifest for the Stage847 C9 official candidate."""
    universe_path, eligibility_path = build_official_candidate_stage847_c9_paths()
    strategy_overrides = _build_official_candidate_stage847_c9_overrides(
        universe_path,
        eligibility_path,
    )
    base_manifest = stage819_cfg.build_official_candidate_stage819_30w_manifest()
    return {
        "alias": OFFICIAL_CANDIDATE_STAGE847_C9_ALIAS,
        "version": OFFICIAL_CANDIDATE_STAGE847_C9_VERSION,
        "family_version": OFFICIAL_CANDIDATE_STAGE847_C9_FAMILY_VERSION,
        "source_stage": OFFICIAL_CANDIDATE_STAGE847_C9_SOURCE_STAGE,
        "base_stage": OFFICIAL_CANDIDATE_STAGE847_C9_BASE_STAGE,
        "base_candidate": stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION,
        "profile_name": OFFICIAL_CANDIDATE_STAGE847_C9_PROFILE_NAME,
        "role": OFFICIAL_CANDIDATE_STAGE847_C9_ROLE,
        "status": OFFICIAL_CANDIDATE_STAGE847_C9_STATUS,
        "capital": OFFICIAL_CANDIDATE_STAGE847_C9_CAPITAL,
        "capital_label": OFFICIAL_CANDIDATE_STAGE847_C9_CAPITAL_LABEL,
        "base_risk_multiplier": base_manifest["base_risk_multiplier"],
        "oi_restore_multiplier": base_manifest["oi_restore_multiplier"],
        "effective_oi_risk_multiplier": base_manifest["effective_oi_risk_multiplier"],
        "array_manager_size": base_manifest["array_manager_size"],
        "strategy_class": OFFICIAL_CANDIDATE_STAGE847_C9_STRATEGY_CLASS,
        "product_universe_csv_path": str(universe_path),
        "ai_product_pool_eligibility_path": str(eligibility_path),
        "ai_product_pool_strategy": AI_SATELLITE_POST_SIGNAL_STRATEGY_NAME,
        "strategy_overrides": strategy_overrides,
        "reference_metrics": OFFICIAL_CANDIDATE_STAGE847_C9_REFERENCE_METRICS,
        "promotion_boundary": OFFICIAL_CANDIDATE_STAGE847_C9_PROMOTION_BOUNDARY,
    }
