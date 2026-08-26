from __future__ import annotations

from pathlib import Path
import sys
from types import SimpleNamespace

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
PORTFOLIO_DIR = PROJECT_DIR / "examples" / "portfolio_backtesting"
TOOL_DIR = (
    PROJECT_DIR
    / "research"
    / "lines"
    / "futures_trend_rollover_shape_same_volume"
    / "tools"
)
sys.path.insert(0, str(PORTFOLIO_DIR))
sys.path.insert(0, str(TOOL_DIR))

import qmt_roll_candidate_stage027_target_contract_history_config as candidate_cfg  # noqa: E402
import qmt_roll_official_live_config as live_cfg  # noqa: E402
import stage027_q_target_contract_history_ac as stage027  # noqa: E402
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy  # noqa: E402


def test_candidate_is_current_formal_q_with_only_history_mode_changed() -> None:
    baseline = live_cfg.build_official_live_strategy_overrides()
    candidate = candidate_cfg.build_candidate_overrides()

    assert live_cfg.OFFICIAL_LIVE_RULESET_VERSION == candidate_cfg.BASE_RULESET_VERSION
    assert candidate_cfg.CANDIDATE_VERSION == "stage027_q_target_contract_history_v1"
    assert candidate_cfg.BASE_COMMIT == "09aa96a03fb91124be90bd69861be3f834ab6299"
    assert stage027.override_diff() == {
        "rollover_shape_history_mode": (
            "backwards_ratio_continuous",
            "target_contract_only",
        )
    }
    assert candidate["enable_rollover_shape_same_volume_reopen"] is True
    assert candidate["rollover_shape_volume_policy"] == "shrink_to_allowed"
    assert candidate["rollover_shape_history_mode"] == "target_contract_only"
    assert {key: value for key, value in candidate.items() if key != "rollover_shape_history_mode"} == {
        key: value for key, value in baseline.items() if key != "rollover_shape_history_mode"
    }


def test_target_contract_only_fails_closed_when_target_readiness_is_not_ready() -> None:
    strategy = QmtRollPortfolioStrategy.__new__(QmtRollPortfolioStrategy)
    strategy.rollover_shape_history_mode = "target_contract_only"
    strategy.ams = {}
    target_history = pd.DataFrame(
        {
            "open": [1.0] * 41,
            "high": [1.0] * 41,
            "low": [1.0] * 41,
            "close": [1.0] * 41,
            "volume": [1.0] * 41,
            "open_interest": [1.0] * 41,
        }
    )
    strategy._build_observed_array_manager_history = lambda _am: target_history.copy()
    strategy._rollover_target_readiness_snapshot = lambda **_kwargs: {
        "same_day_bar_ready": 0,
        "market_data_ready": 0,
        "metadata_ready": 0,
        "target_contract_size": 0,
        "target_price_tick": 0.0,
        "target_margin_ratio": 0.0,
        "target_readiness_reason": "target_bar_not_same_day",
    }

    history, snapshot = strategy._build_rollover_shape_history(
        old_contract="jm2609.DCE",
        target_contract="jm2701.DCE",
        old_bar=SimpleNamespace(),
        new_bar=SimpleNamespace(),
        target_am=SimpleNamespace(),
        target_bar_from_current=False,
    )

    assert history.empty
    assert snapshot["history_input_ready"] == 0
    assert snapshot["history_input_reason"] == "target_bar_not_same_day"
    assert snapshot["same_day_bar_ready"] == 0
    assert snapshot["market_data_ready"] == 0
    assert snapshot["metadata_ready"] == 0
