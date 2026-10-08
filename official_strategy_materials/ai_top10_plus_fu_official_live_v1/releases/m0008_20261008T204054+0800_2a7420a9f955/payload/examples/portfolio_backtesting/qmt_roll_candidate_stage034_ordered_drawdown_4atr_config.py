from __future__ import annotations

from typing import Any

import qmt_roll_candidate_stage033_ordered_drawdown_or_filter_config as stage033_cfg


CANDIDATE_VERSION: str = "stage034_stage033_long_ordered_drawdown_4atr_or_stall_filter_v1"
BASE_CANDIDATE_VERSION: str = stage033_cfg.CANDIDATE_VERSION
BASE_COMMIT: str = "9b439481e105329c9678d73318eaad41fe62ce34"
BASE_RULESET_VERSION: str = stage033_cfg.BASE_RULESET_VERSION


def build_candidate_overrides() -> dict[str, Any]:
    """Build Stage034 by changing only ordered drawdown from 3x to 4x ATR5."""
    overrides = stage033_cfg.build_candidate_overrides()
    if not bool(overrides.get("long_signal_range_enable_ordered_drawdown_filter")):
        raise RuntimeError("stage034_requires_stage033_ordered_drawdown_filter")
    if "long_signal_range_ordered_drawdown_atr_multiplier" in overrides:
        raise RuntimeError("stage034_unexpected_base_ordered_drawdown_multiplier")
    overrides["long_signal_range_ordered_drawdown_atr_multiplier"] = 4.0
    return overrides
