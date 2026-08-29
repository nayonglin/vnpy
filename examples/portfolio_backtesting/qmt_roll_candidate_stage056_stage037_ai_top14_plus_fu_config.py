from __future__ import annotations

from pathlib import Path
from typing import Any

import qmt_roll_official_live_config as live_cfg


PROJECT_DIR = Path(__file__).resolve().parents[2]
BASE_RULESET_VERSION = "stage037_stage034_long_short_mirror_hard_block_v1"
CANDIDATE_VERSION = "stage056_stage037_ai_top14_plus_fu_v1"
CANDIDATE_AI_STRATEGY = "ai_top14_plus_fu_satellite_post_signal_entry_filter"
CANDIDATE_ELIGIBILITY_PATH = (
    PROJECT_DIR
    / "research"
    / "lines"
    / "futures_trend_rollover_shape_same_volume"
    / "artifacts"
    / "stage056_stage037_ai_top14_plus_fu"
    / "stage056_candidate_eligibility.csv"
)


def build_candidate_overrides() -> dict[str, Any]:
    """Keep formal Stage037 unchanged and replace only its AI membership material."""

    overrides = live_cfg.build_official_live_strategy_overrides()
    overrides["ai_product_pool_eligibility_path"] = str(CANDIDATE_ELIGIBILITY_PATH)
    overrides["ai_product_pool_strategy"] = CANDIDATE_AI_STRATEGY
    return overrides


def override_diff() -> dict[str, tuple[Any, Any]]:
    formal = live_cfg.build_official_live_strategy_overrides()
    candidate = build_candidate_overrides()
    return {
        key: (formal.get(key), candidate.get(key))
        for key in sorted(set(formal) | set(candidate))
        if formal.get(key) != candidate.get(key)
    }
