from __future__ import annotations

from typing import Any

import qmt_roll_candidate_stage028_delayed_rollover_config as stage028_cfg


CANDIDATE_VERSION: str = "stage031_stage028_long_10d_range_3atr_filter_v1"
BASE_CANDIDATE_VERSION: str = stage028_cfg.CANDIDATE_VERSION
BASE_COMMIT: str = "fed43773fed4de790d56ce2b6b9c9401fbd5450b"
BASE_RULESET_VERSION: str = stage028_cfg.BASE_RULESET_VERSION
RANGE_LOOKBACK: int = 10
ATR_PERIOD: int = 5
ATR_MULTIPLIER: float = 3.0
ENTRY_CONTEXTS: str = "flat_entry,reverse_entry,rollover_reopen"


def build_candidate_overrides() -> dict[str, Any]:
    """Build Stage031 from Stage028 with one long-only range-expansion filter."""
    overrides = stage028_cfg.build_candidate_overrides()
    if int(overrides.get("rollover_delay_trading_days", 0) or 0) != 5:
        raise RuntimeError("stage031_requires_stage028_five_session_delay")
    unexpected = {
        key: overrides.get(key)
        for key in (
            "enable_long_signal_range_atr_filter",
            "long_signal_range_lookback",
            "long_signal_range_atr_period",
            "long_signal_range_atr_multiplier",
            "long_signal_range_atr_entry_contexts",
        )
        if key in overrides
    }
    if unexpected:
        raise RuntimeError(f"stage031_unexpected_base_range_filter:{unexpected}")
    overrides.update(
        {
            "enable_long_signal_range_atr_filter": True,
            "long_signal_range_lookback": RANGE_LOOKBACK,
            "long_signal_range_atr_period": ATR_PERIOD,
            "long_signal_range_atr_multiplier": ATR_MULTIPLIER,
            "long_signal_range_atr_entry_contexts": ENTRY_CONTEXTS,
        }
    )
    return overrides
