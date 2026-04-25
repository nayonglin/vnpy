from __future__ import annotations

from pathlib import Path
from typing import Any

from qmt_roll_official_stage78_config import (
    OFFICIAL_STAGE78_REFERENCE_METRICS,
    OFFICIAL_STAGE78_VERSION,
)
from run_qmt_roll_official_stage78_fu_sn_satellite_candidate_backtest import (
    CAPITAL,
    ELIGIBILITY_PATH,
    EXCLUSION_MODE,
    EXPERIMENT_NAME,
    SATELLITE_PRODUCTS,
    SIZING_EQUITY_CAP,
    SN_PRODUCT,
    UNIVERSE_PATH,
    build_fu_sn_satellite_post_signal_eligibility,
    build_static18_plus_fu_sn_universe,
)
from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import (
    AI_SATELLITE_POST_SIGNAL_STRATEGY_NAME,
    FU_PRODUCT,
)
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import (
    BASE_RISK_RATIO,
    CORR20_06_08_FLOOR35_OVERRIDES,
)


STAGE105_VERSION: str = "stage105_fu_sn_satellite_successor_candidate_v1"
STAGE105_PROFILE_NAME: str = EXPERIMENT_NAME
STAGE105_ROLE: str = "stage78_successor_candidate"
STAGE105_FORMAL_PREFIX: str = "qmt_roll_stage105_fu_sn_satellite_successor_candidate"
STAGE105_EXPERIMENT_TAG: str = "qmt_roll_stage105_fu_sn_satellite_successor_candidate"
STAGE105_CAPITAL: float = CAPITAL
STAGE105_SIZING_EQUITY_CAP: float = SIZING_EQUITY_CAP
STAGE105_PROFIT_SHIELD_MODE: str = EXCLUSION_MODE

STAGE105_RESEARCH_SWITCH_POLICY: dict[str, str] = {
    "default_for_new_independent_research": "off",
    "use_when": (
        "Use this candidate only when the research question is an incremental improvement "
        "over official_stage78_defensive_v1 or a direct promotion audit of the fu/sn satellite profile."
    ),
    "do_not_use_when": (
        "Do not use it as the default baseline for independent raw idea discovery; otherwise the "
        "Stage78 defensive edge and the sn satellite edge become mixed."
    ),
    "comparison_rule": (
        "Every new branch using this candidate must still report its result against "
        "official_stage78_defensive_v1."
    ),
}

STAGE105_REFERENCE_METRICS: dict[str, dict[str, float]] = {
    "full_2020_2026": {
        "end_balance": 4_752_645.0,
        "total_return_pct": 2_276.3225,
        "max_dd_percent": -36.9907,
        "sharpe_ratio": 1.3067,
        "total_slippage": 248_610.0,
        "total_trade_count": 824.0,
    },
    "post_signal_2022_2026": {
        "end_balance": 2_960_100.0,
        "total_return_pct": 1_380.0500,
        "max_dd_percent": -36.5869,
        "sharpe_ratio": 1.2858,
        "total_slippage": 166_010.0,
        "total_trade_count": 493.0,
    },
    "latest_2026": {
        "end_balance": 223_145.0,
        "total_return_pct": 11.5725,
        "max_dd_percent": -29.1299,
        "sharpe_ratio": 0.4188,
        "total_slippage": 2_220.0,
        "total_trade_count": 26.0,
    },
}

STAGE105_ROBUSTNESS_EVIDENCE: dict[str, Any] = {
    "sn_product": SN_PRODUCT,
    "sn_total_net_pnl": 222_720.0,
    "sn_total_trade_count": 53.0,
    "sn_total_slippage": 2_380.0,
    "sn_negative_years": {
        "2023": -17_910.0,
        "2024": -113_550.0,
    },
    "fair_slippage_5x_end_balance_diff_vs_stage78": 198_555.0,
    "start_year_end_balance_diff_positive_count": 7,
    "start_year_window_count": 7,
}


def build_stage105_paths() -> tuple[Path, Path]:
    """Build and return the frozen product universe and AI eligibility files for Stage105."""
    universe_path = build_static18_plus_fu_sn_universe()
    eligibility_path = build_fu_sn_satellite_post_signal_eligibility()
    return universe_path, eligibility_path


def _build_stage105_overrides(universe_path: Path, eligibility_path: Path) -> dict[str, Any]:
    return {
        **CORR20_06_08_FLOOR35_OVERRIDES,
        "product_universe_csv_path": str(universe_path),
        "enable_ai_product_pool_filter": True,
        "ai_product_pool_eligibility_path": str(eligibility_path),
        "ai_product_pool_strategy": AI_SATELLITE_POST_SIGNAL_STRATEGY_NAME,
        "streak_risk_state_excluded_products": ",".join(SATELLITE_PRODUCTS),
        "streak_risk_state_exclusion_mode": STAGE105_PROFIT_SHIELD_MODE,
        "sizing_equity_cap": STAGE105_SIZING_EQUITY_CAP,
    }


def build_stage105_overrides() -> dict[str, Any]:
    """Return strategy overrides for the Stage105 fu/sn successor candidate."""
    universe_path, eligibility_path = build_stage105_paths()
    return _build_stage105_overrides(universe_path, eligibility_path)


def build_stage105_manifest() -> dict[str, Any]:
    """Build a reproducible manifest for the Stage105 successor candidate."""
    universe_path, eligibility_path = build_stage105_paths()
    strategy_overrides = _build_stage105_overrides(universe_path, eligibility_path)
    return {
        "version": STAGE105_VERSION,
        "profile_name": STAGE105_PROFILE_NAME,
        "role": STAGE105_ROLE,
        "base_version": OFFICIAL_STAGE78_VERSION,
        "capital": STAGE105_CAPITAL,
        "base_risk_ratio": BASE_RISK_RATIO,
        "formal_prefix": STAGE105_FORMAL_PREFIX,
        "experiment_tag": STAGE105_EXPERIMENT_TAG,
        "product_universe_csv_path": str(universe_path),
        "ai_product_pool_eligibility_path": str(eligibility_path),
        "ai_product_pool_strategy": AI_SATELLITE_POST_SIGNAL_STRATEGY_NAME,
        "satellite_products": list(SATELLITE_PRODUCTS),
        "base_satellite_product": FU_PRODUCT,
        "new_satellite_product": SN_PRODUCT,
        "sizing_equity_cap": STAGE105_SIZING_EQUITY_CAP,
        "strategy_overrides": strategy_overrides,
        "reference_metrics": STAGE105_REFERENCE_METRICS,
        "stage78_reference_metrics": OFFICIAL_STAGE78_REFERENCE_METRICS,
        "robustness_evidence": STAGE105_ROBUSTNESS_EVIDENCE,
        "research_switch_policy": STAGE105_RESEARCH_SWITCH_POLICY,
        "promotion_boundary": {
            "formal": (
                "Stage105 is a Stage78 successor candidate, not a replacement for "
                "official_stage78_defensive_v1 until the user explicitly promotes it."
            ),
            "not_formal": (
                "Keep Stage78 as the frozen defensive formal baseline and keep Stage105 as an opt-in candidate switch."
            ),
            "promotion_rule": (
                "Promote only after reviewing annual negative sn contribution and confirming that the added satellite "
                "still improves the intended deployment capital and review horizon."
            ),
        },
    }
