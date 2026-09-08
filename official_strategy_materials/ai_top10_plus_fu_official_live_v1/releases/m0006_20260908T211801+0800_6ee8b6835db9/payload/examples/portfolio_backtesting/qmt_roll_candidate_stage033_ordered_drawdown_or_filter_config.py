from __future__ import annotations

from typing import Any

import qmt_roll_candidate_stage032_long_range_stall_filter_config as stage032_cfg


CANDIDATE_VERSION: str = "stage033_stage032_long_ordered_drawdown_or_stall_filter_v1"
BASE_CANDIDATE_VERSION: str = stage032_cfg.CANDIDATE_VERSION
BASE_COMMIT: str = "8862b527a8460f274645277f8a6b8dc1965c2a97"
BASE_RULESET_VERSION: str = stage032_cfg.BASE_RULESET_VERSION


def build_candidate_overrides() -> dict[str, Any]:
    """Build Stage033 from Stage032 with the frozen ordered-drawdown OR filter."""
    overrides = stage032_cfg.build_candidate_overrides()
    if not bool(overrides.get("long_signal_range_require_recent_stall")):
        raise RuntimeError("stage033_requires_stage032_recent_stall_filter")
    if "long_signal_range_enable_ordered_drawdown_filter" in overrides:
        raise RuntimeError("stage033_unexpected_base_ordered_drawdown_filter")
    overrides["long_signal_range_enable_ordered_drawdown_filter"] = True
    return overrides
