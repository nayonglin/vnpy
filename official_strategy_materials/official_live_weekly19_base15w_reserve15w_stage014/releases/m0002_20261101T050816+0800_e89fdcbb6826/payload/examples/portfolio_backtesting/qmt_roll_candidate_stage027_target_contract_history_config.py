from __future__ import annotations

from typing import Any

import qmt_roll_official_candidate_stage847_c9_config as stage847_c9_cfg
from qmt_roll_official_live_lightweight_context import OFFICIAL_LIVE_AI_ELIGIBILITY_PATH
import qmt_roll_official_stage021_q_ruleset_config as stage021_q_cfg


CANDIDATE_VERSION: str = "stage027_q_target_contract_history_v1"
BASE_COMMIT: str = "09aa96a03fb91124be90bd69861be3f834ab6299"
BASE_RULESET_VERSION: str = stage021_q_cfg.RULESET_VERSION
ROLLOVER_HISTORY_MODE: str = "target_contract_only"


def build_candidate_overrides() -> dict[str, Any]:
    """Build Stage027 from the immutable historical Q ruleset."""

    overrides = stage021_q_cfg.apply_stage021_q_ruleset(
        stage847_c9_cfg.build_official_candidate_stage847_c9_overrides()
    )
    overrides["account_capital"] = 150_000.0
    overrides["c3_capital"] = 150_000.0
    overrides["ai_product_pool_eligibility_path"] = str(
        OFFICIAL_LIVE_AI_ELIGIBILITY_PATH
    )
    if overrides.get("rollover_shape_history_mode") != "backwards_ratio_continuous":
        raise RuntimeError(
            "stage027_unexpected_formal_rollover_history_mode: "
            f"{overrides.get('rollover_shape_history_mode')}"
        )
    overrides["rollover_shape_history_mode"] = ROLLOVER_HISTORY_MODE
    return overrides
