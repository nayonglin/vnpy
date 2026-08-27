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

import qmt_roll_candidate_stage032_long_range_stall_filter_config as stage032_cfg
import qmt_roll_candidate_stage033_ordered_drawdown_or_filter_config as stage033_cfg
import stage033_stage032_ordered_drawdown_or_filter_abc as stage033
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy


class Stage033OrderedDrawdownOrFilterTest(unittest.TestCase):
    @staticmethod
    def strategy(*, ordered: bool = True) -> QmtRollPortfolioStrategy:
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
        strategy.long_signal_range_enable_ordered_drawdown_filter = ordered
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

    @staticmethod
    def healthy_rise() -> pd.DataFrame:
        closes = [100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0, 108.0, 109.0]
        return pd.DataFrame(
            {
                "close": closes,
                "high": [value + 1.0 for value in closes],
                "low": [value - 1.0 for value in closes],
            },
            index=pd.bdate_range("2026-08-13", periods=10),
        )

    def test_candidate_inherits_stage032_with_one_frozen_switch(self) -> None:
        stage032 = stage032_cfg.build_candidate_overrides()
        stage033 = stage033_cfg.build_candidate_overrides()
        keys = set(stage032) | set(stage033)
        diff = {
            key: (stage032.get(key), stage033.get(key))
            for key in sorted(keys)
            if stage032.get(key) != stage033.get(key)
        }
        self.assertEqual(
            {"long_signal_range_enable_ordered_drawdown_filter": (None, True)},
            diff,
        )

    def test_ordered_drawdown_blocks_even_when_recent_gain_is_not_stalled(self) -> None:
        snapshot = self.strategy()._long_signal_range_atr_snapshot(
            "long", self.ordered_drawdown_with_recovery(), "flat_entry"
        )
        self.assertEqual(2.0, snapshot["long_signal_range_prior_atr"])
        self.assertEqual(6.0, snapshot["long_signal_range_atr_threshold"])
        self.assertEqual(7.0, snapshot["long_signal_range_ordered_drawdown_value"])
        self.assertEqual(0, snapshot["long_signal_range_recent_stall_condition_met"])
        self.assertEqual(0, snapshot["long_signal_range_expansion_stall_condition_met"])
        self.assertEqual(1, snapshot["long_signal_range_ordered_drawdown_condition_met"])
        self.assertEqual(1, snapshot["long_signal_range_atr_condition_met"])
        self.assertEqual(
            "ordered_drawdown_strictly_above_threshold",
            snapshot["long_signal_range_atr_reason"],
        )

    def test_stage032_same_history_remains_allowed_when_new_switch_is_off(self) -> None:
        snapshot = self.strategy(ordered=False)._long_signal_range_atr_snapshot(
            "long", self.ordered_drawdown_with_recovery(), "flat_entry"
        )
        self.assertEqual(0, snapshot["long_signal_range_ordered_drawdown_condition_met"])
        self.assertEqual(0, snapshot["long_signal_range_atr_condition_met"])
        self.assertEqual(
            "range_above_but_recent_gain_not_stalled",
            snapshot["long_signal_range_atr_reason"],
        )

    def test_low_before_high_healthy_rise_is_not_an_ordered_drawdown(self) -> None:
        snapshot = self.strategy()._long_signal_range_atr_snapshot(
            "long", self.healthy_rise(), "flat_entry"
        )
        self.assertLessEqual(
            snapshot["long_signal_range_ordered_drawdown_value"],
            snapshot["long_signal_range_atr_threshold"],
        )
        self.assertEqual(0, snapshot["long_signal_range_ordered_drawdown_condition_met"])
        self.assertEqual(0, snapshot["long_signal_range_atr_condition_met"])

    def test_ordered_drawdown_equal_to_threshold_is_allowed(self) -> None:
        history = self.ordered_drawdown_with_recovery()
        history.iloc[2, history.columns.get_loc("low")] = 99.0
        snapshot = self.strategy()._long_signal_range_atr_snapshot(
            "long", history, "flat_entry"
        )
        self.assertEqual(
            snapshot["long_signal_range_ordered_drawdown_value"],
            snapshot["long_signal_range_atr_threshold"],
        )
        self.assertEqual(0, snapshot["long_signal_range_ordered_drawdown_condition_met"])
        self.assertEqual(0, snapshot["long_signal_range_atr_condition_met"])

    def test_existing_stall_and_new_ordered_drawdown_are_or_conditions(self) -> None:
        history = self.ordered_drawdown_with_recovery()
        history.iloc[-4:, history.columns.get_loc("close")] = 104.0
        snapshot = self.strategy()._long_signal_range_atr_snapshot(
            "long", history, "flat_entry"
        )
        self.assertEqual(1, snapshot["long_signal_range_expansion_stall_condition_met"])
        self.assertEqual(1, snapshot["long_signal_range_ordered_drawdown_condition_met"])
        self.assertEqual(1, snapshot["long_signal_range_atr_condition_met"])
        self.assertEqual(
            "range_stall_and_ordered_drawdown_both",
            snapshot["long_signal_range_atr_reason"],
        )

    def test_lh_named_case_total_range_is_not_ordered_drawdown(self) -> None:
        history = pd.DataFrame(
            {
                "close": [15845.0, 16375.0, 16225.0, 15815.0, 16325.0, 17185.0, 17320.0, 17495.0, 17385.0, 16705.0],
                "high": [16220.0, 16455.0, 16600.0, 16480.0, 16350.0, 17470.0, 17330.0, 17620.0, 17670.0, 17530.0],
                "low": [15590.0, 15600.0, 15695.0, 15700.0, 15820.0, 16860.0, 16800.0, 17010.0, 16895.0, 16675.0],
            },
            index=pd.bdate_range("2021-10-18", periods=10),
        )
        snapshot = self.strategy()._long_signal_range_atr_snapshot(
            "long", history, "flat_entry"
        )
        self.assertEqual(2080.0, snapshot["long_signal_range_value"])
        self.assertEqual(995.0, snapshot["long_signal_range_ordered_drawdown_value"])
        self.assertEqual(719.0, snapshot["long_signal_range_prior_atr"])
        self.assertEqual(0, snapshot["long_signal_range_ordered_drawdown_condition_met"])
        self.assertEqual(0, snapshot["long_signal_range_atr_condition_met"])

    def test_runner_scope_and_or_contract(self) -> None:
        self.assertEqual(
            {"long_signal_range_enable_ordered_drawdown_filter": (None, True)},
            stage033._expected_override_diff(),
        )
        common = {
            "experiment_arm": "C",
            "direction": "long",
            "entry_context": "flat_entry",
            "long_signal_range_atr_enabled": 1,
            "long_signal_range_lookback": 10,
            "long_signal_range_atr_period": 5,
            "long_signal_range_atr_multiplier": 3.0,
            "long_signal_range_require_recent_stall": 1,
            "long_signal_range_recent_gain_lookback": 3,
            "long_signal_range_recent_gain_atr_multiplier": 0.5,
            "long_signal_range_enable_ordered_drawdown_filter": 1,
            "long_signal_range_value": 4.0,
            "long_signal_range_prior_atr": 1.0,
            "long_signal_range_atr_threshold": 3.0,
            "long_signal_range_recent_gain_atr_threshold": 0.5,
            "long_signal_range_ordered_drawdown_peak_index": 0,
            "long_signal_range_ordered_drawdown_trough_index": 2,
        }
        diagnostics = pd.DataFrame(
            [
                {
                    **common,
                    "long_signal_range_recent_gain": 0.2,
                    "long_signal_range_recent_stall_condition_met": 1,
                    "long_signal_range_expansion_stall_condition_met": 1,
                    "long_signal_range_ordered_drawdown_peak": 2.0,
                    "long_signal_range_ordered_drawdown_trough": 1.0,
                    "long_signal_range_ordered_drawdown_value": 1.0,
                    "long_signal_range_ordered_drawdown_condition_met": 0,
                    "long_signal_range_atr_condition_met": 1,
                    "long_signal_range_atr_reason": (
                        "range_strictly_above_and_recent_gain_below_threshold"
                    ),
                    "long_signal_range_atr_blocked": 1,
                    "long_signal_range_atr_selected_volume_before": 3,
                    "long_signal_range_atr_selected_volume_after": 0,
                },
                {
                    **common,
                    "long_signal_range_recent_gain": 0.8,
                    "long_signal_range_recent_stall_condition_met": 0,
                    "long_signal_range_expansion_stall_condition_met": 0,
                    "long_signal_range_ordered_drawdown_peak": 5.0,
                    "long_signal_range_ordered_drawdown_trough": 1.0,
                    "long_signal_range_ordered_drawdown_value": 4.0,
                    "long_signal_range_ordered_drawdown_condition_met": 1,
                    "long_signal_range_atr_condition_met": 1,
                    "long_signal_range_atr_reason": (
                        "ordered_drawdown_strictly_above_threshold"
                    ),
                    "long_signal_range_atr_blocked": 1,
                    "long_signal_range_atr_selected_volume_before": 2,
                    "long_signal_range_atr_selected_volume_after": 0,
                },
                {
                    **common,
                    "long_signal_range_recent_gain": 0.8,
                    "long_signal_range_recent_stall_condition_met": 0,
                    "long_signal_range_expansion_stall_condition_met": 0,
                    "long_signal_range_ordered_drawdown_peak": 3.0,
                    "long_signal_range_ordered_drawdown_trough": 1.0,
                    "long_signal_range_ordered_drawdown_value": 2.0,
                    "long_signal_range_ordered_drawdown_condition_met": 0,
                    "long_signal_range_atr_condition_met": 0,
                    "long_signal_range_atr_reason": (
                        "range_above_but_recent_gain_not_stalled"
                    ),
                    "long_signal_range_atr_blocked": 0,
                    "long_signal_range_atr_selected_volume_before": 2,
                    "long_signal_range_atr_selected_volume_after": 2,
                },
            ]
        )
        contract = stage033._filter_contract(diagnostics)
        self.assertTrue(contract["all_pass"])
        self.assertEqual(1, contract["expansion_stall_only_count"])
        self.assertEqual(1, contract["ordered_drawdown_only_count"])
        self.assertEqual(2, contract["actual_incremental_block_count"])

    def test_published_report_round_trips_from_frozen_artifacts(self) -> None:
        artifact_dir = (
            ROOT
            / "research/lines/futures_trend_rollover_shape_same_volume/artifacts/stage033"
        )
        summary = pd.read_csv(artifact_dir / "stage033_abc_summary.csv")
        comparison = pd.read_csv(artifact_dir / "stage033_abc_comparison.csv")
        decision = json.loads((artifact_dir / "stage033_decision.json").read_text())
        report = stage033._report(summary, comparison, decision)
        self.assertEqual((artifact_dir / "stage033_report.md").read_text(), report)
        self.assertTrue(decision["reproduction"]["all_pass"])
        self.assertTrue(decision["filter_contract"]["or_semantics_pass"])
        self.assertTrue(
            decision["named_case_contract"]["oi905_ordered_drawdown_blocked_pass"]
        )
        self.assertTrue(decision["named_case_contract"]["lh2201_allowed_pass"])
        self.assertFalse(decision["escalate_to_multicycle"])


if __name__ == "__main__":
    unittest.main()
