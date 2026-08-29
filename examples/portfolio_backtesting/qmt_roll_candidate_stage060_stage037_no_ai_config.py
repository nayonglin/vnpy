from __future__ import annotations

from typing import Any

import qmt_roll_official_live_config as live_cfg


BASE_RULESET_VERSION = "stage037_stage034_long_short_mirror_hard_block_v1"
CANDIDATE_VERSION = "stage060_stage037_no_ai_static18_plus_fu_v1"


def build_candidate_overrides() -> dict[str, Any]:
    """Keep Stage037 intact and disable only its AI membership filter."""

    overrides = live_cfg.build_official_live_strategy_overrides()
    overrides["enable_ai_product_pool_filter"] = False
    return overrides


def override_diff() -> dict[str, tuple[Any, Any]]:
    formal = live_cfg.build_official_live_strategy_overrides()
    candidate = build_candidate_overrides()
    return {
        key: (formal.get(key), candidate.get(key))
        for key in sorted(set(formal) | set(candidate))
        if formal.get(key) != candidate.get(key)
    }
