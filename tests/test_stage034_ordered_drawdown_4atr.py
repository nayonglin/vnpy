from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PORTFOLIO_DIR = ROOT / "examples" / "portfolio_backtesting"
TOOLS_DIR = ROOT / "research/lines/futures_trend_rollover_shape_same_volume/tools"
for path in (PORTFOLIO_DIR, TOOLS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import qmt_roll_candidate_stage033_ordered_drawdown_or_filter_config as stage033_cfg
import qmt_roll_candidate_stage034_ordered_drawdown_4atr_config as stage034_cfg
import stage034_stage033_ordered_drawdown_4atr_abc as stage034
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy


class Stage034OrderedDrawdown4AtrTest(unittest.TestCase):
    @staticmethod
    def strategy(multiplier: float) -> QmtRollPortfolioStrategy:
        strategy = QmtRollPortfolioStrategy.__new__(QmtRollPortfolioStrategy)
        strategy.enable_long_signal_range_atr_filter = True
        strategy.long_signal_range_lookback = 10
        strategy.long_signal_range_atr_period = 5
        strategy.long_signal_range_atr_multiplier = 3.0
        strategy.long_signal_range_atr_entry_contexts = (
            "flat_entry,reverse_entry,rollover_reopen"
        )
        strategy.long_signal_range_require_recent_stall = True
        strategy.long_signal_range_recent_gain_lookback = 3
        strategy.long_signal_range_recent_gain_atr_multiplier = 0.5
        strategy.long_signal_range_enable_ordered_drawdown_filter = True
        strategy.long_signal_range_ordered_drawdown_atr_multiplier = multiplier
        return strategy

    @staticmethod
    def ordered_drawdown_with_recovery() -> pd.DataFrame:
        return pd.DataFrame(
            {
                "close": [104.0, 103.0, 100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0],
                "high": [105.0, 104.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0, 108.0],
                "low": [103.0, 102.0, 98.0, 100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0],
            },
            index=pd.bdate_range("2026-08-13", periods=10),
        )

    def test_candidate_changes_only_ordered_drawdown_multiplier(self) -> None:
        stage033 = stage033_cfg.build_candidate_overrides()
        stage034 = stage034_cfg.build_candidate_overrides()
        keys = set(stage033) | set(stage034)
        diff = {
            key: (stage033.get(key), stage034.get(key))
            for key in sorted(keys)
            if stage033.get(key) != stage034.get(key)
        }
        self.assertEqual(
            {"long_signal_range_ordered_drawdown_atr_multiplier": (None, 4.0)},
            diff,
        )
        self.assertEqual(3.0, stage034["long_signal_range_atr_multiplier"])

    def test_runner_freezes_same_exact_override_diff(self) -> None:
        self.assertEqual(
            {"long_signal_range_ordered_drawdown_atr_multiplier": (None, 4.0)},
            stage034._expected_override_diff(),
        )

    def test_four_atr_allows_drawdown_that_three_atr_blocks(self) -> None:
        history = self.ordered_drawdown_with_recovery()
        stage033 = self.strategy(3.0)._long_signal_range_atr_snapshot(
            "long", history, "flat_entry"
        )
        stage034 = self.strategy(4.0)._long_signal_range_atr_snapshot(
            "long", history, "flat_entry"
        )
        self.assertEqual(2.0, stage034["long_signal_range_prior_atr"])
        self.assertEqual(6.0, stage034["long_signal_range_atr_threshold"])
        self.assertEqual(
            8.0, stage034["long_signal_range_ordered_drawdown_atr_threshold"]
        )
        self.assertEqual(7.0, stage034["long_signal_range_ordered_drawdown_value"])
        self.assertEqual(1, stage033["long_signal_range_ordered_drawdown_condition_met"])
        self.assertEqual(0, stage034["long_signal_range_ordered_drawdown_condition_met"])
        self.assertEqual(0, stage034["long_signal_range_atr_condition_met"])

    def test_ordered_drawdown_equal_to_four_atr_is_allowed(self) -> None:
        history = self.ordered_drawdown_with_recovery()
        history.iloc[2, history.columns.get_loc("low")] = 97.0
        snapshot = self.strategy(4.0)._long_signal_range_atr_snapshot(
            "long", history, "flat_entry"
        )
        self.assertEqual(
            snapshot["long_signal_range_ordered_drawdown_value"],
            snapshot["long_signal_range_ordered_drawdown_atr_threshold"],
        )
        self.assertEqual(0, snapshot["long_signal_range_ordered_drawdown_condition_met"])

    def test_original_three_atr_stall_condition_remains_independent_or_leg(self) -> None:
        history = self.ordered_drawdown_with_recovery()
        history.iloc[-4:, history.columns.get_loc("close")] = 104.0
        snapshot = self.strategy(4.0)._long_signal_range_atr_snapshot(
            "long", history, "flat_entry"
        )
        self.assertEqual(1, snapshot["long_signal_range_expansion_stall_condition_met"])
        self.assertEqual(0, snapshot["long_signal_range_ordered_drawdown_condition_met"])
        self.assertEqual(1, snapshot["long_signal_range_atr_condition_met"])
        self.assertEqual(
            "range_strictly_above_and_recent_gain_below_threshold",
            snapshot["long_signal_range_atr_reason"],
        )

    def test_ordered_drawdown_strictly_above_four_atr_is_blocked(self) -> None:
        history = self.ordered_drawdown_with_recovery()
        history.iloc[2, history.columns.get_loc("low")] = 96.9
        snapshot = self.strategy(4.0)._long_signal_range_atr_snapshot(
            "long", history, "flat_entry"
        )
        self.assertAlmostEqual(
            8.1, snapshot["long_signal_range_ordered_drawdown_value"]
        )
        self.assertGreater(
            snapshot["long_signal_range_ordered_drawdown_value"],
            snapshot["long_signal_range_ordered_drawdown_atr_threshold"],
        )
        self.assertEqual(1, snapshot["long_signal_range_ordered_drawdown_condition_met"])

    def test_published_report_round_trips_from_frozen_artifacts(self) -> None:
        artifact_dir = (
            ROOT
            / "research/lines/futures_trend_rollover_shape_same_volume/artifacts/stage034"
        )
        summary = pd.read_csv(artifact_dir / "stage034_abc_summary.csv")
        comparison = pd.read_csv(artifact_dir / "stage034_abc_comparison.csv")
        decision = json.loads((artifact_dir / "stage034_decision.json").read_text())
        self.assertEqual(
            (artifact_dir / "stage034_report.md").read_text(),
            stage034._report(summary, comparison, decision),
        )
        self.assertTrue(decision["reference_reuse"]["A_and_B_from_stage033"])
        self.assertTrue(decision["reference_reuse"]["only_C_new_engine_run"])
        self.assertTrue(decision["filter_contract"]["all_pass"])
        self.assertTrue(decision["named_case_contract"]["all_pass"])
        self.assertFalse(decision["gates"]["C_slippage_not_above_stage032"])
        self.assertFalse(decision["escalate_to_multicycle"])


if __name__ == "__main__":
    unittest.main()
