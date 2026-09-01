from __future__ import annotations

from typing import Any

import qmt_roll_candidate_stage027_target_contract_history_config as stage027_cfg


CANDIDATE_VERSION: str = "stage028_q_target_contract_history_delay_5td_v1"
BASE_CANDIDATE_VERSION: str = stage027_cfg.CANDIDATE_VERSION
BASE_COMMIT: str = "d4b54531dee806321c4dd4ec6c921629fda04593"
BASE_RULESET_VERSION: str = stage027_cfg.BASE_RULESET_VERSION
ROLLOVER_DELAY_TRADING_DAYS: int = 5


def build_candidate_overrides() -> dict[str, Any]:
    """Build Stage028 from Stage027 with one fixed five-session rollover delay."""
    overrides = stage027_cfg.build_candidate_overrides()
    existing = int(overrides.get("rollover_delay_trading_days", 0) or 0)
    if existing != 0:
        raise RuntimeError(
            "stage028_unexpected_base_rollover_delay: "
            f"expected=0 actual={existing}"
        )
    overrides["rollover_delay_trading_days"] = ROLLOVER_DELAY_TRADING_DAYS
    return overrides
