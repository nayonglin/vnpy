from __future__ import annotations

from pathlib import Path
from typing import Any

import qmt_roll_official_live_config as live_cfg


BASE_RULESET_VERSION = "stage037_stage034_long_short_mirror_hard_block_v1"
CANDIDATE_VERSION = "stage061_stage037_ai_top10_to_top19_width_sweep_v1"
MIN_TOP_N = 10
MAX_TOP_N = 19


def _strategy(top_n: int) -> str:
    if top_n not in range(MIN_TOP_N, MAX_TOP_N + 1):
        raise ValueError(f"stage061_top_n_out_of_range:{top_n}")
    return f"ai_top{top_n}_plus_fu_width_sweep"


def build_candidate_overrides(top_n: int, eligibility_path: Path) -> dict[str, Any]:
    """Keep Stage037 unchanged and replace only its enabled AI membership material."""

    overrides = live_cfg.build_official_live_strategy_overrides()
    overrides["enable_ai_product_pool_filter"] = True
    overrides["ai_product_pool_eligibility_path"] = str(eligibility_path.resolve())
    overrides["ai_product_pool_strategy"] = _strategy(top_n)
    return overrides


def override_diff(top_n: int, eligibility_path: Path) -> dict[str, tuple[Any, Any]]:
    formal = live_cfg.build_official_live_strategy_overrides()
    candidate = build_candidate_overrides(top_n, eligibility_path)
    return {
        key: (formal.get(key), candidate.get(key))
        for key in sorted(set(formal) | set(candidate))
        if formal.get(key) != candidate.get(key)
    }
