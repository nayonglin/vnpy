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
    BASE_RISK_RATIO,
    CORR20_06_08_FLOOR35_OVERRIDES,
)


OFFICIAL_STAGE78_FAMILY_VERSION: str = "official_stage78_defensive_v1"
OFFICIAL_STAGE78_VERSION: str = "official_stage78_1_defensive_50w_no_sizing_cap"
OFFICIAL_STAGE78_SHORT_ALIAS: str = "78-1"
OFFICIAL_STAGE78_PROFILE_NAME: str = "stage78_1_ai_top8_plus_fu_satellite_post_signal_50w_no_sizing_cap"
OFFICIAL_STAGE78_ROLE: str = "defensive_risk_governance_formal"
OFFICIAL_STAGE78_FORMAL_PREFIX: str = "qmt_roll_official_stage78_defensive_formal"
OFFICIAL_STAGE78_EXPERIMENT_TAG: str = "qmt_roll_official_stage78_defensive"
OFFICIAL_STAGE78_CAPITAL: float = 500_000.0
OFFICIAL_STAGE78_SIZING_EQUITY_CAP: float = 0.0
OFFICIAL_STAGE78_PROFIT_SHIELD_MODE: str = "profit_only"

RESEARCH_SWITCH_POLICY: dict[str, str] = {
    "default_for_new_independent_research": "off",
    "use_when": "Use this profile only when the research question is an incremental change on the frozen formal baseline.",
    "do_not_use_when": "Do not enable it for independent raw idea discovery, otherwise the baseline edge and the new idea become mixed.",
    "comparison_rule": "Every new research branch should compare against 78-1 before promotion.",
}

OFFICIAL_STAGE78_REFERENCE_METRICS: dict[str, dict[str, float]] = {
    "full_2020_2026": {
        "end_balance": 25_542_885.0,
        "total_return_pct": 5_008.5770,
        "max_dd_percent": -40.0607,
        "sharpe_ratio": 1.1295,
        "total_slippage": 1_968_150.0,
        "total_trade_count": 880.0,
    },
    "latest_2026": {
        "end_balance": 450_540.0,
        "total_return_pct": -9.8920,
        "max_dd_percent": -28.5861,
        "sharpe_ratio": -0.6975,
        "total_slippage": 4_660.0,
        "total_trade_count": 27.0,
    },
}

OFFICIAL_STAGE78_COMPARISON_BASELINES: dict[str, dict[str, float]] = {
    "stage78_30w_no_sizing_cap_previous_formal": {
        "end_balance": 16_607_885.0,
        "total_return_pct": 5_435.9617,
        "max_dd_percent": -39.7620,
        "sharpe_ratio": 1.1235,
        "total_slippage": 1_358_150.0,
        "total_trade_count": 863.0,
    },
    "stage78_30w_sizing_cap_1m_previous_formal": {
        "end_balance": 5_388_370.0,
        "total_return_pct": 1_696.1233,
        "max_dd_percent": -39.5952,
        "sharpe_ratio": 1.3113,
        "total_slippage": 283_680.0,
        "total_trade_count": 811.0,
    },
    "stage75_return_ceiling": {
        "end_balance": 4_644_365.0,
        "total_return_pct": 2_222.1825,
        "max_dd_percent": -36.9907,
        "sharpe_ratio": 1.2926,
        "total_slippage": 289_960.0,
        "total_trade_count": 791.0,
    },
    "stage68_71_ai_top8": {
        "end_balance": 3_894_190.0,
        "total_return_pct": 1_847.0950,
        "max_dd_percent": -36.9907,
        "sharpe_ratio": 1.2080,
        "total_slippage": 257_880.0,
        "total_trade_count": 720.0,
    },
    "no_ai_product_pool_baseline": {
        "end_balance": 2_902_355.0,
        "total_return_pct": 1_351.1775,
        "max_dd_percent": -36.9907,
        "sharpe_ratio": 1.0225,
        "total_slippage": 349_080.0,
        "total_trade_count": 1_158.0,
    },
}


def build_official_stage78_paths() -> tuple[Path, Path]:
    """Build and return the frozen product universe and AI eligibility files."""
    universe_path = build_static18_plus_fu_universe()
    eligibility_path = build_ai_satellite_post_signal_eligibility()
    return universe_path, eligibility_path


def _build_official_stage78_overrides(universe_path: Path, eligibility_path: Path) -> dict[str, Any]:
    return {
        **CORR20_06_08_FLOOR35_OVERRIDES,
        "product_universe_csv_path": str(universe_path),
        "sizing_equity_cap": OFFICIAL_STAGE78_SIZING_EQUITY_CAP,
        "enable_ai_product_pool_filter": True,
        "ai_product_pool_eligibility_path": str(eligibility_path),
        "ai_product_pool_strategy": AI_SATELLITE_POST_SIGNAL_STRATEGY_NAME,
        "streak_risk_state_excluded_products": FU_PRODUCT,
        "streak_risk_state_exclusion_mode": OFFICIAL_STAGE78_PROFIT_SHIELD_MODE,
    }


def build_official_stage78_overrides() -> dict[str, Any]:
    """Return strategy overrides for the frozen Stage78 defensive formal profile."""
    universe_path, eligibility_path = build_official_stage78_paths()
    return _build_official_stage78_overrides(universe_path, eligibility_path)


def build_official_stage78_manifest() -> dict[str, Any]:
    """Build a reproducible manifest for the official Stage78 profile."""
    universe_path, eligibility_path = build_official_stage78_paths()
    strategy_overrides = _build_official_stage78_overrides(universe_path, eligibility_path)
    return {
        "short_alias": OFFICIAL_STAGE78_SHORT_ALIAS,
        "version": OFFICIAL_STAGE78_VERSION,
        "family_version": OFFICIAL_STAGE78_FAMILY_VERSION,
        "profile_name": OFFICIAL_STAGE78_PROFILE_NAME,
        "role": OFFICIAL_STAGE78_ROLE,
        "capital": OFFICIAL_STAGE78_CAPITAL,
        "sizing_equity_cap": OFFICIAL_STAGE78_SIZING_EQUITY_CAP,
        "base_risk_ratio": BASE_RISK_RATIO,
        "formal_prefix": OFFICIAL_STAGE78_FORMAL_PREFIX,
        "experiment_tag": OFFICIAL_STAGE78_EXPERIMENT_TAG,
        "product_universe_csv_path": str(universe_path),
        "ai_product_pool_eligibility_path": str(eligibility_path),
        "ai_product_pool_strategy": AI_SATELLITE_POST_SIGNAL_STRATEGY_NAME,
        "strategy_overrides": strategy_overrides,
        "reference_metrics": OFFICIAL_STAGE78_REFERENCE_METRICS,
        "comparison_baselines": OFFICIAL_STAGE78_COMPARISON_BASELINES,
        "research_switch_policy": RESEARCH_SWITCH_POLICY,
        "promotion_boundary": {
            "formal": "Stage78-1 is the current defensive formal baseline.",
            "not_formal": "Stage75 remains the return ceiling reference; Stage86 and Stage90 remain research-only.",
            "promotion_rule": "Promote a new branch only after it beats or clearly complements Stage78 under multi-cycle, start-year and slippage checks.",
        },
    }
