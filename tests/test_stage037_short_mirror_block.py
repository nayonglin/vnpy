from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PORTFOLIO_DIR = ROOT / "examples" / "portfolio_backtesting"
TOOLS_DIR = ROOT / "research/lines/futures_trend_rollover_shape_same_volume/tools"
for path in (PORTFOLIO_DIR, TOOLS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import qmt_roll_candidate_stage034_ordered_drawdown_4atr_config as stage034_cfg
import qmt_roll_candidate_stage037_short_mirror_block_config as stage037_cfg
import stage037_stage034_short_mirror_block_abc as stage037
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy


class Stage037ShortMirrorBlockTest(unittest.TestCase):
    @staticmethod
    def strategy(*, short_enabled: bool = True) -> QmtRollPortfolioStrategy:
        strategy = QmtRollPortfolioStrategy.__new__(QmtRollPortfolioStrategy)
        strategy.enable_long_signal_range_atr_filter = True
        strategy.enable_short_signal_range_atr_filter = short_enabled
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
        strategy.long_signal_range_ordered_drawdown_atr_multiplier = 4.0
        strategy.long_signal_range_atr_diagnostics = []
        strategy.source_symbol_by_contract = {"rb2510.SHFE": "rb.SHFE"}
        return strategy

    @staticmethod
    def stable_history() -> pd.DataFrame:
        return pd.DataFrame(
            {
                "close": [100.0] * 10,
                "high": [100.5] * 9 + [103.5],
                "low": [99.5] * 10,
            },
            index=pd.bdate_range("2026-08-13", periods=10),
        )

    @staticmethod
    def long_ordered_drawdown() -> pd.DataFrame:
        frame = pd.DataFrame(
            {
                "close": [104.0, 103.0, 100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0],
                "high": [105.0, 104.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0, 108.0],
                "low": [103.0, 102.0, 96.9, 100.0, 101.0, 102.0, 103.0, 104.0, 105.0, 106.0],
            },
            index=pd.bdate_range("2026-08-13", periods=10),
        )
        return frame

    @staticmethod
    def mirror_prices(frame: pd.DataFrame, center: float = 100.0) -> pd.DataFrame:
        mirrored = frame.copy()
        mirrored["close"] = 2 * center - frame["close"]
        mirrored["high"] = 2 * center - frame["low"]
        mirrored["low"] = 2 * center - frame["high"]
        return mirrored

    def test_candidate_changes_only_short_enable_switch(self) -> None:
        stage034 = stage034_cfg.build_candidate_overrides()
        stage037_overrides = stage037_cfg.build_candidate_overrides()
        keys = set(stage034) | set(stage037_overrides)
        diff = {
            key: (stage034.get(key), stage037_overrides.get(key))
            for key in sorted(keys)
            if stage034.get(key) != stage037_overrides.get(key)
        }
        self.assertEqual(
            {"enable_short_signal_range_atr_filter": (None, True)},
            diff,
        )
        self.assertEqual(diff, stage037._expected_override_diff())

    def test_recovery_contract_binds_database_candidate_period_and_overrides(self) -> None:
        identity = {"runtime_binding": {"database_sha256": "db-sha"}}
        contract = stage037._recovery_contract(identity)
        self.assertEqual("db-sha", contract["database_sha256"])
        self.assertEqual(stage037_cfg.CANDIDATE_VERSION, contract["candidate_version"])
        self.assertEqual(
            {"start": "2018-01-01", "end": "2026-08-25"},
            contract["period"],
        )
        self.assertEqual(64, len(contract["candidate_overrides_sha256"]))

    def test_stage034_keeps_short_direction_excluded(self) -> None:
        snapshot = self.strategy(short_enabled=False)._long_signal_range_atr_snapshot(
            "short", self.stable_history(), "flat_entry"
        )
        self.assertEqual("direction_excluded", snapshot["long_signal_range_atr_reason"])
        self.assertEqual(0, snapshot["long_signal_range_atr_condition_met"])

    def test_short_range_expansion_with_weak_recent_decline_is_blocked(self) -> None:
        snapshot = self.strategy()._long_signal_range_atr_snapshot(
            "short", self.stable_history(), "flat_entry"
        )
        self.assertEqual(1.0, snapshot["long_signal_range_prior_atr"])
        self.assertEqual(4.0, snapshot["long_signal_range_value"])
        self.assertEqual(0.0, snapshot["long_signal_range_directional_recent_move"])
        self.assertEqual(1, snapshot["long_signal_range_expansion_stall_condition_met"])
        self.assertEqual(1, snapshot["long_signal_range_atr_condition_met"])
        self.assertEqual(
            "short_range_strictly_above_and_recent_decline_below_threshold",
            snapshot["long_signal_range_atr_reason"],
        )

    def test_short_range_expansion_with_strong_recent_decline_is_allowed(self) -> None:
        history = self.stable_history()
        history.iloc[-1] = {"close": 96.5, "high": 97.0, "low": 96.0}
        snapshot = self.strategy()._long_signal_range_atr_snapshot(
            "short", history, "flat_entry"
        )
        self.assertGreater(snapshot["long_signal_range_value"], snapshot["long_signal_range_atr_threshold"])
        self.assertGreaterEqual(
            snapshot["long_signal_range_directional_recent_move"],
            snapshot["long_signal_range_recent_gain_atr_threshold"],
        )
        self.assertEqual(0, snapshot["long_signal_range_expansion_stall_condition_met"])
        self.assertEqual(0, snapshot["long_signal_range_ordered_drawdown_condition_met"])
        self.assertEqual(0, snapshot["long_signal_range_atr_condition_met"])

    def test_short_ordered_rebound_strictly_above_four_atr_is_blocked(self) -> None:
        history = self.mirror_prices(self.long_ordered_drawdown())
        snapshot = self.strategy()._long_signal_range_atr_snapshot(
            "short", history, "flat_entry"
        )
        self.assertAlmostEqual(8.1, snapshot["long_signal_range_ordered_drawdown_value"])
        self.assertEqual(2.0, snapshot["long_signal_range_prior_atr"])
        self.assertLess(
            snapshot["long_signal_range_ordered_drawdown_trough_index"],
            snapshot["long_signal_range_ordered_drawdown_peak_index"],
        )
        self.assertEqual("rebound", snapshot["long_signal_range_ordered_move_kind"])
        self.assertEqual(1, snapshot["long_signal_range_ordered_drawdown_condition_met"])
        self.assertEqual(
            "short_ordered_rebound_strictly_above_threshold",
            snapshot["long_signal_range_atr_reason"],
        )

    def test_short_ordered_rebound_equal_to_four_atr_is_allowed(self) -> None:
        history = self.long_ordered_drawdown()
        history.iloc[2, history.columns.get_loc("low")] = 97.0
        snapshot = self.strategy()._long_signal_range_atr_snapshot(
            "short", self.mirror_prices(history), "flat_entry"
        )
        self.assertEqual(
            snapshot["long_signal_range_ordered_drawdown_value"],
            snapshot["long_signal_range_ordered_drawdown_atr_threshold"],
        )
        self.assertEqual(0, snapshot["long_signal_range_ordered_drawdown_condition_met"])

    def test_long_and_mirrored_short_have_identical_conditions(self) -> None:
        long_history = self.long_ordered_drawdown()
        short_history = self.mirror_prices(long_history)
        long_snapshot = self.strategy()._long_signal_range_atr_snapshot(
            "long", long_history, "flat_entry"
        )
        short_snapshot = self.strategy()._long_signal_range_atr_snapshot(
            "short", short_history, "flat_entry"
        )
        for field in (
            "long_signal_range_value",
            "long_signal_range_prior_atr",
            "long_signal_range_directional_recent_move",
            "long_signal_range_ordered_drawdown_value",
            "long_signal_range_expansion_stall_condition_met",
            "long_signal_range_ordered_drawdown_condition_met",
            "long_signal_range_atr_condition_met",
        ):
            self.assertAlmostEqual(long_snapshot[field], short_snapshot[field])

    def test_short_match_hard_blocks_positive_volume(self) -> None:
        strategy = self.strategy()
        snapshot = strategy._long_signal_range_atr_snapshot(
            "short", self.stable_history(), "reverse_entry"
        )
        sizing = strategy._apply_long_signal_range_atr_to_sizing(
            {"selected_volume": 3},
            snapshot,
            vt_symbol="rb2510.SHFE",
            direction="short",
            bar=SimpleNamespace(datetime=datetime(2026, 8, 26, 15, 0)),
            entry_context="reverse_entry",
        )
        self.assertEqual(1, sizing["long_signal_range_atr_blocked"])
        self.assertEqual(3, sizing["long_signal_range_atr_selected_volume_before"])
        self.assertEqual(0, sizing["selected_volume"])

    def test_published_report_round_trips_from_frozen_artifacts(self) -> None:
        artifact_dir = (
            ROOT
            / "research/lines/futures_trend_rollover_shape_same_volume/artifacts/stage037"
        )
        summary = pd.read_csv(artifact_dir / "stage037_abc_summary.csv")
        comparison = pd.read_csv(artifact_dir / "stage037_abc_comparison.csv")
        decision = json.loads((artifact_dir / "stage037_decision.json").read_text())
        self.assertEqual(
            (artifact_dir / "stage037_report.md").read_text(),
            stage037._report(summary, comparison, decision),
        )
        self.assertTrue(decision["reference_reuse"]["A_and_B_from_stage034"])
        self.assertTrue(decision["reference_reuse"]["only_C_new_engine_run"])
        self.assertTrue(decision["filter_contract"]["all_pass"])
        self.assertEqual(73, decision["filter_contract"]["short_condition_met_count"])
        self.assertEqual(71, decision["filter_contract"]["short_incremental_block_count"])
        self.assertFalse(decision["gates"]["C_slippage_not_above_105pct_of_B"])
        self.assertFalse(decision["escalate_to_multicycle"])


if __name__ == "__main__":
    unittest.main()
