from __future__ import annotations

from typing import Any

import qmt_roll_candidate_stage034_ordered_drawdown_4atr_config as stage034_cfg


CANDIDATE_VERSION: str = "stage037_stage034_long_short_mirror_hard_block_v1"
BASE_CANDIDATE_VERSION: str = stage034_cfg.CANDIDATE_VERSION
BASE_COMMIT: str = "a8774b517ff76d56ff74a35743e66d2628167c1b"
BASE_RULESET_VERSION: str = stage034_cfg.BASE_RULESET_VERSION


def build_candidate_overrides() -> dict[str, Any]:
    """Build Stage037 by enabling the frozen Stage034 filter for shorts too."""
    overrides = stage034_cfg.build_candidate_overrides()
    if not bool(overrides.get("enable_long_signal_range_atr_filter")):
        raise RuntimeError("stage037_requires_stage034_long_filter")
    if "enable_short_signal_range_atr_filter" in overrides:
        raise RuntimeError("stage037_unexpected_base_short_filter_switch")
    overrides["enable_short_signal_range_atr_filter"] = True
    return overrides
