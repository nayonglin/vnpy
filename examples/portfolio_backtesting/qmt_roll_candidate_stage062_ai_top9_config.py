from __future__ import annotations

from pathlib import Path
from typing import Any

import qmt_roll_official_live_config as live_cfg


BASE_RULESET_VERSION = "stage037_stage034_long_short_mirror_hard_block_v1"
CANDIDATE_VERSION = "stage062_stage037_ai_top9_boundary_check_v1"
STRATEGY = "ai_top9_plus_fu_boundary_check"


def build_candidate_overrides(eligibility_path: Path) -> dict[str, Any]:
    """Keep Stage037 unchanged and replace only its enabled AI membership material."""

    overrides = live_cfg.build_official_live_strategy_overrides()
    overrides["enable_ai_product_pool_filter"] = True
    overrides["ai_product_pool_eligibility_path"] = str(eligibility_path.resolve())
    overrides["ai_product_pool_strategy"] = STRATEGY
    return overrides


def override_diff(eligibility_path: Path) -> dict[str, tuple[Any, Any]]:
    formal = live_cfg.build_official_live_strategy_overrides()
    candidate = build_candidate_overrides(eligibility_path)
    return {
        key: (formal.get(key), candidate.get(key))
        for key in sorted(set(formal) | set(candidate))
        if formal.get(key) != candidate.get(key)
    }
