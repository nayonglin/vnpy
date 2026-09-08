from __future__ import annotations

from typing import Any, Mapping

import qmt_roll_official_stage021_q_ruleset_config as stage021_q_cfg


RULESET_VERSION: str = "stage037_stage034_long_short_mirror_hard_block_v1"
PREVIOUS_RULESET_VERSION: str = stage021_q_cfg.RULESET_VERSION
RESEARCH_CANDIDATE_VERSION: str = RULESET_VERSION

STAGE037_RELATIVE_OVERRIDES: dict[str, Any] = {
    "enable_long_signal_range_atr_filter": True,
    "enable_short_signal_range_atr_filter": True,
    "long_signal_range_atr_entry_contexts": (
        "flat_entry,reverse_entry,rollover_reopen"
    ),
    "long_signal_range_atr_multiplier": 3.0,
    "long_signal_range_atr_period": 5,
    "long_signal_range_enable_ordered_drawdown_filter": True,
    "long_signal_range_lookback": 10,
    "long_signal_range_ordered_drawdown_atr_multiplier": 4.0,
    "long_signal_range_recent_gain_atr_multiplier": 0.5,
    "long_signal_range_recent_gain_lookback": 3,
    "long_signal_range_require_recent_stall": True,
    "rollover_delay_trading_days": 5,
    "rollover_shape_history_mode": "target_contract_only",
}


def apply_stage037_ruleset(base_overrides: Mapping[str, Any]) -> dict[str, Any]:
    """Apply Q and then Stage037's exact thirteen-field formal delta."""

    overrides = stage021_q_cfg.apply_stage021_q_ruleset(base_overrides)
    overrides.update(STAGE037_RELATIVE_OVERRIDES)
    return overrides
