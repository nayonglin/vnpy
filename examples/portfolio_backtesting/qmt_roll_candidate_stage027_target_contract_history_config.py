from __future__ import annotations

from typing import Any

import qmt_roll_official_live_config as live_cfg


CANDIDATE_VERSION: str = "stage027_q_target_contract_history_v1"
BASE_COMMIT: str = "09aa96a03fb91124be90bd69861be3f834ab6299"
BASE_RULESET_VERSION: str = "stage021_q_rollover_volume_atr_v1"
ROLLOVER_HISTORY_MODE: str = "target_contract_only"


def build_candidate_overrides() -> dict[str, Any]:
    """Build Stage027 from the current formal Q overrides with one semantic change."""
    if live_cfg.OFFICIAL_LIVE_RULESET_VERSION != BASE_RULESET_VERSION:
        raise RuntimeError(
            "stage027_formal_baseline_changed: "
            f"expected={BASE_RULESET_VERSION} "
            f"actual={live_cfg.OFFICIAL_LIVE_RULESET_VERSION}"
        )

    overrides = live_cfg.build_official_live_strategy_overrides()
    if overrides.get("rollover_shape_history_mode") != "backwards_ratio_continuous":
        raise RuntimeError(
            "stage027_unexpected_formal_rollover_history_mode: "
            f"{overrides.get('rollover_shape_history_mode')}"
        )
    overrides["rollover_shape_history_mode"] = ROLLOVER_HISTORY_MODE
    return overrides
