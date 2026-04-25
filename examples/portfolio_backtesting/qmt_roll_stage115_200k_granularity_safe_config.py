from __future__ import annotations

from pathlib import Path
from typing import Any

from qmt_roll_stage111_400k_margin_safe_config import (
    STAGE111_MARGIN_PROFILE,
    STAGE111_VERSION,
    build_stage111_overrides,
)
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

STAGE115_VERSION: str = "stage115_stage111_200k_granularity_safe_candidate_v1"
STAGE115_PROFILE_NAME: str = "stage111_200k_single_margin_le_20pct"
STAGE115_ROLE: str = "stage111_200k_research_candidate"
STAGE115_FORMAL_PREFIX: str = "qmt_roll_stage115_200k_granularity_safe_candidate"
STAGE115_EXPERIMENT_TAG: str = "qmt_roll_stage115_200k_granularity_safe_candidate"
STAGE115_CAPITAL: float = 200_000.0
STAGE115_SINGLE_CONTRACT_MARGIN_LIMIT_PCT: float = 20.0
STAGE115_UNIVERSE_PATH: Path = (
    OUTPUT_DIR
    / "qmt_roll_stage111_200k_contract_granularity_filter_universe_threshold_20p0_"
    "stage113_stage111_200k_contract_granularity_filter_v1.csv"
)

STAGE115_REFERENCE_METRICS: dict[str, dict[str, float]] = {
    "full_2020_2026_200k": {
        "end_balance": 932_280.0,
        "total_return_pct": 366.1400,
        "max_dd_percent": -24.6971165496,
        "sharpe_ratio": 1.0500579097,
        "total_slippage": 53_700.0,
        "total_trade_count": 512.0,
        "win_ratio_pct": 40.3041825095,
        "max_margin_to_balance_pct": 51.3696078327,
        "max_single_contract_margin_pct_capital": 10.77,
        "worst_5d_pct_capital": -76.2450,
    },
}

STAGE115_QUARTERLY_VALIDATION: dict[str, dict[str, float]] = {
    "63d": {
        "window_count": 25,
        "positive_return_rate_pct": 64.0,
        "worst_return_pct": -3.0550,
        "median_return_pct": 5.7550,
        "worst_max_dd_percent": -28.9600153787,
        "max_margin_to_balance_pct": 46.7592277776,
        "windows_margin_gt_80pct": 0,
        "windows_margin_gt_100pct": 0,
        "worst_5d_pct_capital": -33.7975,
        "worst_20d_pct_capital": -41.6725,
    },
    "126d": {
        "window_count": 24,
        "positive_return_rate_pct": 79.1666666667,
        "worst_return_pct": -5.5700,
        "median_return_pct": 11.12875,
        "worst_max_dd_percent": -28.9600153787,
        "max_margin_to_balance_pct": 46.7592277776,
        "windows_margin_gt_80pct": 0,
        "windows_margin_gt_100pct": 0,
        "worst_5d_pct_capital": -33.7975,
        "worst_20d_pct_capital": -41.6725,
    },
    "252d": {
        "window_count": 22,
        "positive_return_rate_pct": 77.2727272727,
        "worst_return_pct": -5.7800,
        "median_return_pct": 24.1625,
        "worst_max_dd_percent": -28.9600153787,
        "max_margin_to_balance_pct": 46.7592277776,
        "windows_margin_gt_80pct": 0,
        "windows_margin_gt_100pct": 0,
        "worst_5d_pct_capital": -39.9050,
        "worst_20d_pct_capital": -49.0550,
    },
}

STAGE115_REJECTED_BASELINE: dict[str, Any] = {
    "raw_stage111_200k": {
        "decision": "REJECT_200K_AS_IS",
        "reason": "single-contract margin and worst-5d path risk are too large before granularity filtering",
        "end_balance": 1_355_600.0,
        "total_return_pct": 577.8000,
        "max_single_contract_margin_pct_capital": 32.4750,
        "worst_5d_pct_capital": -85.8125,
    },
}

STAGE115_RESEARCH_SWITCH_POLICY: dict[str, str] = {
    "default_for_new_independent_research": "off",
    "use_when": (
        "Use this profile only for 200k small-capital research, granularity-safe deployment audits, "
        "or incremental improvements on the filtered Stage111 profile."
    ),
    "do_not_use_when": (
        "Do not use it for raw alpha discovery; the product universe is already structurally filtered for capital size."
    ),
    "comparison_rule": (
        "Compare against raw Stage111-200k, Stage111-400k, and official Stage78 when discussing deployment tradeoffs."
    ),
}


def build_stage115_overrides() -> dict[str, Any]:
    """Return Stage111 overrides with the 200k single-contract granularity filtered universe."""
    if not STAGE115_UNIVERSE_PATH.exists():
        raise FileNotFoundError(STAGE115_UNIVERSE_PATH)
    overrides = build_stage111_overrides()
    overrides["product_universe_csv_path"] = str(STAGE115_UNIVERSE_PATH)
    return overrides


def build_stage115_manifest() -> dict[str, Any]:
    strategy_overrides = build_stage115_overrides()
    return {
        "version": STAGE115_VERSION,
        "profile_name": STAGE115_PROFILE_NAME,
        "role": STAGE115_ROLE,
        "base_version": STAGE111_VERSION,
        "capital": STAGE115_CAPITAL,
        "base_risk_ratio": BASE_RISK_RATIO,
        "formal_prefix": STAGE115_FORMAL_PREFIX,
        "experiment_tag": STAGE115_EXPERIMENT_TAG,
        "single_contract_margin_limit_pct": STAGE115_SINGLE_CONTRACT_MARGIN_LIMIT_PCT,
        "product_universe_csv_path": str(STAGE115_UNIVERSE_PATH),
        "margin_profile": STAGE111_MARGIN_PROFILE,
        "strategy_overrides": strategy_overrides,
        "reference_metrics": STAGE115_REFERENCE_METRICS,
        "quarterly_validation": STAGE115_QUARTERLY_VALIDATION,
        "rejected_baseline": STAGE115_REJECTED_BASELINE,
        "research_switch_policy": STAGE115_RESEARCH_SWITCH_POLICY,
        "promotion_boundary": {
            "formal": (
                "Stage115 is a 200k research candidate, not a formal deployment version yet, because "
                "quarterly positive-return rates are weaker than the 400k Stage111 profile."
            ),
            "not_formal": (
                "It solves the single-contract and margin hard blockers, but still needs improvement in cold-start hit rate."
            ),
            "promotion_rule": (
                "Promote only after improving quarterly positive-return stability without reintroducing margin or granularity risk."
            ),
        },
    }
