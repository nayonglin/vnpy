from __future__ import annotations

from typing import Any, Mapping


RULESET_VERSION: str = "stage021_q_rollover_volume_atr_v1"


def apply_stage021_q_ruleset(base_overrides: Mapping[str, Any]) -> dict[str, Any]:
    """Apply the immutable Stage021-Q ruleset to a C9 execution profile."""

    overrides = dict(base_overrides)
    overrides.update(
        {
            "enable_rollover_shape_same_volume_reopen": True,
            "rollover_shape_volume_policy": "shrink_to_allowed",
            "rollover_shape_history_mode": "backwards_ratio_continuous",
            "enable_directional_30d_risk_boost": True,
            "directional_30d_risk_boost_lookback": 30,
            "directional_30d_risk_boost_multiplier": 1.5,
            "directional_30d_risk_nonconfirmation_multiplier": 1.0,
            "directional_30d_risk_adjust_long_only": False,
            "directional_30d_risk_boost_require_volume_expansion": True,
            "directional_30d_volume_recent_days": 10,
            "directional_30d_volume_prior_days": 10,
            "directional_30d_volume_ratio_threshold": 3.0,
            "enable_directional_30d_low_volume_risk_discount": True,
            "directional_30d_low_volume_ratio_threshold": 0.5,
            "directional_30d_low_volume_risk_multiplier": 0.5,
            "enable_long_signal_atr_shock_filter": True,
            "enable_short_signal_atr_shock_filter": True,
            "long_signal_atr_shock_period": 5,
            "long_signal_atr_shock_multiplier": 1.0,
            "long_signal_atr_shock_entry_contexts": (
                "flat_entry,reverse_entry,rollover_reopen"
            ),
        }
    )
    return overrides
