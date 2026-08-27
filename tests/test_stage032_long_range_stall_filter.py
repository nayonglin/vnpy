from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PORTFOLIO_DIR = ROOT / "examples" / "portfolio_backtesting"
TOOLS_DIR = ROOT / "research" / "lines" / "futures_trend_rollover_shape_same_volume" / "tools"
for path in (PORTFOLIO_DIR, TOOLS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import qmt_roll_candidate_stage028_delayed_rollover_config as stage028_cfg
import qmt_roll_candidate_stage031_long_range_atr_filter_config as stage031_cfg
import qmt_roll_candidate_stage032_long_range_stall_filter_config as stage032_cfg
import stage032_stage028_long_range_stall_filter_abc as stage032
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy


class Stage032LongRangeStallFilterTest(unittest.TestCase):
    @staticmethod
    def strategy() -> QmtRollPortfolioStrategy:
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
        return strategy

    @staticmethod
    def stalled_history() -> pd.DataFrame:
        return pd.DataFrame(
            {
                "close": [100.0, 100.0, 104.0, 104.0, 104.0, 104.0, 104.0, 104.0, 104.0, 104.0],
                "high": [100.5, 100.5, 104.5, 104.5, 104.5, 104.5, 104.5, 104.5, 104.5, 104.5],
                "low": [99.5, 99.5, 103.5, 103.5, 103.5, 103.5, 103.5, 103.5, 103.5, 103.5],
            },
            index=pd.bdate_range("2026-08-13", periods=10),
        )

    @staticmethod
    def continuing_history() -> pd.DataFrame:
        closes = [100.0] * 6 + [101.0, 102.0, 103.0, 104.0]
        return pd.DataFrame(
            {
                "close": closes,
                "high": [value + 0.5 for value in closes],
                "low": [value - 0.5 for value in closes],
            },
            index=pd.bdate_range("2026-08-13", periods=10),
        )

    def test_candidate_inherits_stage028_with_exact_frozen_diff(self) -> None:
        stage028 = stage028_cfg.build_candidate_overrides()
        stage032 = stage032_cfg.build_candidate_overrides()
        keys = set(stage028) | set(stage032)
        diff = {
            key: (stage028.get(key), stage032.get(key))
            for key in sorted(keys)
            if stage028.get(key) != stage032.get(key)
        }
        self.assertEqual(
            {
                "enable_long_signal_range_atr_filter": (None, True),
                "long_signal_range_atr_entry_contexts": (
                    None,
                    "flat_entry,reverse_entry,rollover_reopen",
                ),
                "long_signal_range_atr_multiplier": (None, 3.0),
                "long_signal_range_atr_period": (None, 5),
                "long_signal_range_lookback": (None, 10),
                "long_signal_range_recent_gain_atr_multiplier": (None, 0.5),
                "long_signal_range_recent_gain_lookback": (None, 3),
                "long_signal_range_require_recent_stall": (None, True),
            },
            diff,
        )
        self.assertEqual(5, stage032["rollover_delay_trading_days"])

    def test_expanded_but_stalled_long_is_blocked(self) -> None:
        snapshot = self.strategy()._long_signal_range_atr_snapshot(
            "long", self.stalled_history(), "flat_entry"
        )
        self.assertEqual(5.0, snapshot["long_signal_range_value"])
        self.assertEqual(1.0, snapshot["long_signal_range_prior_atr"])
        self.assertEqual(0.0, snapshot["long_signal_range_recent_gain"])
        self.assertEqual(0.5, snapshot["long_signal_range_recent_gain_atr_threshold"])
        self.assertEqual(1, snapshot["long_signal_range_recent_stall_condition_met"])
        self.assertEqual(1, snapshot["long_signal_range_atr_condition_met"])

    def test_expanded_and_continuing_long_is_allowed(self) -> None:
        snapshot = self.strategy()._long_signal_range_atr_snapshot(
            "long", self.continuing_history(), "flat_entry"
        )
        self.assertGreater(
            snapshot["long_signal_range_value"],
            snapshot["long_signal_range_atr_threshold"],
        )
        self.assertGreaterEqual(
            snapshot["long_signal_range_recent_gain"],
            snapshot["long_signal_range_recent_gain_atr_threshold"],
        )
        self.assertEqual(0, snapshot["long_signal_range_recent_stall_condition_met"])
        self.assertEqual(0, snapshot["long_signal_range_atr_condition_met"])
        self.assertEqual(
            "range_above_but_recent_gain_not_stalled",
            snapshot["long_signal_range_atr_reason"],
        )

    def test_recent_gain_equal_to_half_atr_is_allowed(self) -> None:
        history = self.stalled_history()
        history.iloc[-1, history.columns.get_loc("close")] = 104.5
        snapshot = self.strategy()._long_signal_range_atr_snapshot(
            "long", history, "flat_entry"
        )
        self.assertEqual(0.5, snapshot["long_signal_range_recent_gain"])
        self.assertEqual(0.5, snapshot["long_signal_range_recent_gain_atr_threshold"])
        self.assertEqual(0, snapshot["long_signal_range_atr_condition_met"])

    def test_stage031_semantics_remain_range_only(self) -> None:
        stage031 = stage031_cfg.build_candidate_overrides()
        self.assertNotIn("long_signal_range_require_recent_stall", stage031)
        strategy = self.strategy()
        strategy.long_signal_range_require_recent_stall = False
        snapshot = strategy._long_signal_range_atr_snapshot(
            "long", self.continuing_history(), "flat_entry"
        )
        self.assertEqual(1, snapshot["long_signal_range_atr_condition_met"])
        self.assertEqual(
            "range_strictly_above_threshold",
            snapshot["long_signal_range_atr_reason"],
        )

    def test_runner_contract_accepts_blocked_stall_and_continuing_bypass(self) -> None:
        common = {
            "experiment_arm": "C",
            "long_signal_range_atr_enabled": 1,
            "long_signal_range_lookback": 10,
            "long_signal_range_atr_period": 5,
            "long_signal_range_atr_multiplier": 3.0,
            "long_signal_range_require_recent_stall": 1,
            "long_signal_range_recent_gain_lookback": 3,
            "long_signal_range_recent_gain_atr_multiplier": 0.5,
            "long_signal_range_value": 5.0,
            "long_signal_range_prior_atr": 1.0,
            "long_signal_range_atr_threshold": 3.0,
            "long_signal_range_recent_gain_atr_threshold": 0.5,
        }
        diagnostics = pd.DataFrame(
            [
                {
                    **common,
                    "direction": "long",
                    "entry_context": "flat_entry",
                    "long_signal_range_recent_gain": 0.2,
                    "long_signal_range_recent_stall_condition_met": 1,
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
                    "direction": "long",
                    "entry_context": "flat_entry",
                    "long_signal_range_recent_gain": 0.8,
                    "long_signal_range_recent_stall_condition_met": 0,
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
        result = stage032._filter_contract(diagnostics)
        self.assertTrue(result["all_pass"])
        self.assertEqual(1, result["actual_incremental_block_count"])

    def test_named_case_contract_blocks_cu_and_allows_fg(self) -> None:
        diagnostics = pd.DataFrame(
            [
                {
                    "experiment_arm": "C",
                    "contract_vt_symbol": "cu2109.SHFE",
                    "date": "2021-07-30",
                    "long_signal_range_value": 5340.0,
                    "long_signal_range_prior_atr": 1218.0,
                    "long_signal_range_recent_gain": 50.0,
                    "long_signal_range_atr_blocked": 1,
                    "long_signal_range_atr_selected_volume_before": 4,
                    "long_signal_range_atr_selected_volume_after": 0,
                    "long_signal_range_atr_reason": (
                        "range_strictly_above_and_recent_gain_below_threshold"
                    ),
                },
                {
                    "experiment_arm": "C",
                    "contract_vt_symbol": "FG009.CZCE",
                    "date": "2020-07-02",
                    "long_signal_range_value": 67.0,
                    "long_signal_range_prior_atr": 18.4,
                    "long_signal_range_recent_gain": 24.0,
                    "long_signal_range_atr_blocked": 0,
                    "long_signal_range_atr_selected_volume_before": 19,
                    "long_signal_range_atr_selected_volume_after": 19,
                    "long_signal_range_atr_reason": (
                        "range_above_but_recent_gain_not_stalled"
                    ),
                },
            ]
        )
        result = stage032._named_case_contract(diagnostics)
        self.assertTrue(result["all_pass"])

    def test_published_report_round_trips_from_frozen_artifacts(self) -> None:
        artifact_dir = (
            ROOT
            / "research/lines/futures_trend_rollover_shape_same_volume/artifacts/stage032"
        )
        summary = pd.read_csv(artifact_dir / "stage032_abc_summary.csv")
        comparison = pd.read_csv(artifact_dir / "stage032_abc_comparison.csv")
        decision = json.loads((artifact_dir / "stage032_decision.json").read_text())
        report = stage032._report(summary, comparison, decision)
        self.assertEqual((artifact_dir / "stage032_report.md").read_text(), report)
        self.assertTrue(decision["named_case_contract"]["cu2109_blocked_pass"])
        self.assertTrue(decision["named_case_contract"]["fg009_allowed_pass"])
        self.assertFalse(decision["escalate_to_multicycle"])


if __name__ == "__main__":
    unittest.main()
