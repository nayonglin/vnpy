from __future__ import annotations

import os
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parent
SHARED_INPUT_DIR = PROJECT_DIR / "backtest_outputs"

PROFILE_KEY = "stage372-20w"
OFFICIAL_VERSION = "official_live_stage372_20w_recovery_sleeve"
OFFICIAL_ALIAS = "Stage372-20w"
BASE_PROFILE_NAME = (
    "stage526_200k_force95_to80_largest_margin_r080_pc25_maxpos4"
)
PROFILE_NAME = "stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4"
CAPITAL = 200_000.0
CAPITAL_LABEL = "20w"
ANALYSIS_START = "2026-01-01"
MODEL_TAG = "stage659_stage372_2026_ytd_latest_ai_shadow_v1"
OUTPUT_PREFIX = "qmt_roll_stage659_stage372_2026_ytd_latest_ai_shadow"

AI_ELIGIBILITY_PATH = Path(
    os.environ.get(
        "OFFICIAL_LIVE_AI_ELIGIBILITY_PATH",
        SHARED_INPUT_DIR
        / "qmt_roll_stage182_ai_product_pool_live_inference_combined_stage78_eligibility_"
        "stage182_ai_product_pool_live_inference_v1.csv",
    )
).expanduser().resolve(strict=False)

STRATEGY_OVERRIDES: dict[str, Any] = {
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


__all__ = [
    "AI_ELIGIBILITY_PATH",
    "ANALYSIS_START",
    "BASE_PROFILE_NAME",
    "CAPITAL",
    "CAPITAL_LABEL",
    "MODEL_TAG",
    "OFFICIAL_ALIAS",
    "OFFICIAL_VERSION",
    "OUTPUT_PREFIX",
    "PROFILE_KEY",
    "PROFILE_NAME",
    "STRATEGY_OVERRIDES",
]
