from __future__ import annotations

from typing import Any

from qmt_roll_stage105_fu_sn_config import (
    STAGE105_REFERENCE_METRICS,
    STAGE105_ROLE,
    STAGE105_VERSION,
    build_stage105_manifest,
    build_stage105_overrides,
)
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


STAGE111_VERSION: str = "stage111_stage105_400k_margin_safe_profile_v1"
STAGE111_PROFILE_NAME: str = "stage105_fu_sn_cap45_single20_400k_margin_safe"
STAGE111_ROLE: str = "stage105_400k_deployment_candidate"
STAGE111_FORMAL_PREFIX: str = "qmt_roll_stage111_400k_margin_safe_candidate"
STAGE111_EXPERIMENT_TAG: str = "qmt_roll_stage111_400k_margin_safe_candidate"
STAGE111_CAPITAL: float = 400_000.0

STAGE111_MARGIN_PROFILE: dict[str, float] = {
    "max_capital_usage_ratio": 0.45,
    "max_single_trade_capital_usage_ratio": 0.20,
}

STAGE111_REFERENCE_METRICS: dict[str, dict[str, float]] = {
    "full_2020_2026_400k": {
        "end_balance": 2_766_945.0,
        "total_return_pct": 591.73625,
        "max_dd_percent": -21.6475181963,
        "sharpe_ratio": 1.4757224614,
        "total_slippage": 118_860.0,
        "total_trade_count": 782.0,
        "max_total_margin_to_balance_pct": 51.7933144533,
        "max_total_margin_to_initial_capital_pct": 51.20805,
    },
}

STAGE111_QUARTERLY_VALIDATION: dict[str, dict[str, float]] = {
    "63d": {
        "window_count": 25,
        "positive_return_rate_pct": 72.0,
        "worst_return_pct": -9.4875,
        "median_return_pct": 9.2850,
        "worst_max_dd_percent": -26.1991103020,
        "max_margin_to_balance_pct": 60.6937464170,
        "windows_margin_gt_80pct": 0,
        "windows_margin_gt_100pct": 0,
        "worst_20d_pct_capital": -34.5575,
    },
    "126d": {
        "window_count": 24,
        "positive_return_rate_pct": 95.8333333333,
        "worst_return_pct": -1.20125,
        "median_return_pct": 20.664375,
        "worst_max_dd_percent": -26.1991103020,
        "max_margin_to_balance_pct": 63.3236506146,
        "windows_margin_gt_80pct": 0,
        "windows_margin_gt_100pct": 0,
        "worst_20d_pct_capital": -42.1325,
    },
    "252d": {
        "window_count": 22,
        "positive_return_rate_pct": 100.0,
        "worst_return_pct": 6.0625,
        "median_return_pct": 43.755625,
        "worst_max_dd_percent": -26.1991103020,
        "max_margin_to_balance_pct": 63.3236506146,
        "windows_margin_gt_80pct": 0,
        "windows_margin_gt_100pct": 0,
        "worst_20d_pct_capital": -44.3425,
    },
}

STAGE111_REJECTED_ALTERNATIVES: dict[str, dict[str, float | str]] = {
    "cap60_single30": {
        "reason": "Rejected for 400k formal deployment because quarterly cold starts exceed margin gates.",
        "full_2020_2026_return_pct": 880.95125,
        "full_2020_2026_max_margin_to_balance_pct": 72.2308538627,
        "quarterly_max_margin_to_balance_pct": 108.5601682026,
        "quarterly_windows_margin_gt_80pct_63d": 6,
        "quarterly_windows_margin_gt_100pct_63d": 2,
    },
}

STAGE111_RESEARCH_SWITCH_POLICY: dict[str, str] = {
    "default_for_new_independent_research": "off",
    "use_when": (
        "Use this profile when the research question is 400k small-capital deployment, "
        "Stage105 promotion review, or an incremental change on the validated margin-safe profile."
    ),
    "do_not_use_when": (
        "Do not use it for raw alpha discovery or full-market product-search experiments; "
        "that would mix the Stage105 fu/sn satellite edge with the capital constraint edge."
    ),
    "comparison_rule": (
        "Report every branch against official_stage78_defensive_v1, raw Stage105, and this Stage111 profile "
        "when the research target is deployability."
    ),
}


def build_stage111_overrides() -> dict[str, Any]:
    """Return Stage105 overrides plus the validated 400k margin-safe capital constraints."""
    overrides = build_stage105_overrides()
    overrides.update(STAGE111_MARGIN_PROFILE)
    return overrides


def build_stage111_manifest() -> dict[str, Any]:
    """Build a reproducible manifest for the Stage111 400k deployment candidate."""
    base_manifest = build_stage105_manifest()
    strategy_overrides = build_stage111_overrides()
    return {
        "version": STAGE111_VERSION,
        "profile_name": STAGE111_PROFILE_NAME,
        "role": STAGE111_ROLE,
        "base_version": STAGE105_VERSION,
        "base_role": STAGE105_ROLE,
        "capital": STAGE111_CAPITAL,
        "base_risk_ratio": BASE_RISK_RATIO,
        "formal_prefix": STAGE111_FORMAL_PREFIX,
        "experiment_tag": STAGE111_EXPERIMENT_TAG,
        "margin_profile": STAGE111_MARGIN_PROFILE,
        "strategy_overrides": strategy_overrides,
        "base_stage105_reference_metrics": STAGE105_REFERENCE_METRICS,
        "reference_metrics": STAGE111_REFERENCE_METRICS,
        "quarterly_validation": STAGE111_QUARTERLY_VALIDATION,
        "rejected_alternatives": STAGE111_REJECTED_ALTERNATIVES,
        "research_switch_policy": STAGE111_RESEARCH_SWITCH_POLICY,
        "product_universe_csv_path": base_manifest["product_universe_csv_path"],
        "ai_product_pool_eligibility_path": base_manifest["ai_product_pool_eligibility_path"],
        "ai_product_pool_strategy": base_manifest["ai_product_pool_strategy"],
        "satellite_products": base_manifest["satellite_products"],
        "promotion_boundary": {
            "formal": (
                "Stage111 is a validated 400k deployment candidate. It is not a universal replacement for "
                "official_stage78_defensive_v1 or raw Stage105."
            ),
            "not_formal": (
                "Stage78 remains the defensive formal baseline; raw Stage105 remains the higher-return research candidate."
            ),
            "promotion_rule": (
                "Promote for live 400k only after the user accepts the lower-return margin-safe tradeoff and "
                "future monitoring continues to respect the 80% margin gate."
            ),
        },
    }
