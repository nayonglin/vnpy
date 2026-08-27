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
TOOLS_DIR = ROOT / "research" / "lines" / "futures_trend_rollover_shape_same_volume" / "tools"
for path in (PORTFOLIO_DIR, TOOLS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import qmt_roll_candidate_stage028_delayed_rollover_config as stage028_cfg
import qmt_roll_candidate_stage031_long_range_atr_filter_config as stage031_cfg
import stage031_stage028_long_range_atr_filter_abc as stage031
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy


class Stage031LongRangeAtrFilterTest(unittest.TestCase):
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
        strategy.long_signal_range_atr_diagnostics = []
        strategy.source_symbol_by_contract = {"rb2510.SHFE": "rb.SHFE"}
        return strategy

    @staticmethod
    def history(signal_high: float, signal_low: float, signal_close: float) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "close": [100.0] * 9 + [signal_close],
                "high": [100.5] * 9 + [signal_high],
                "low": [99.5] * 9 + [signal_low],
            },
            index=pd.bdate_range("2026-08-13", periods=10),
        )

    def test_candidate_inherits_stage028_and_only_enables_frozen_filter(self) -> None:
        stage028 = stage028_cfg.build_candidate_overrides()
        stage031 = stage031_cfg.build_candidate_overrides()
        keys = set(stage028) | set(stage031)
        diff = {
            key: (stage028.get(key), stage031.get(key))
            for key in sorted(keys)
            if stage028.get(key) != stage031.get(key)
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
            },
            diff,
        )
        self.assertEqual(5, stage031["rollover_delay_trading_days"])

    def test_strictly_above_three_prior_atr5_blocks_long(self) -> None:
        strategy = self.strategy()
        snapshot = strategy._long_signal_range_atr_snapshot(
            "long",
            self.history(signal_high=104.5, signal_low=103.5, signal_close=104.0),
            "flat_entry",
        )
        self.assertEqual(1.0, snapshot["long_signal_range_prior_atr"])
        self.assertEqual(5.0, snapshot["long_signal_range_value"])
        self.assertEqual(3.0, snapshot["long_signal_range_atr_threshold"])
        self.assertEqual(1, snapshot["long_signal_range_atr_condition_met"])

        sizing = strategy._apply_long_signal_range_atr_to_sizing(
            {"selected_volume": 4},
            snapshot,
            vt_symbol="rb2510.SHFE",
            direction="long",
            bar=SimpleNamespace(datetime=datetime(2026, 8, 26, 15, 0)),
            entry_context="flat_entry",
        )
        self.assertEqual(1, sizing["long_signal_range_atr_blocked"])
        self.assertEqual(4, sizing["long_signal_range_atr_selected_volume_before"])
        self.assertEqual(0, sizing["selected_volume"])

    def test_equal_to_three_atr_is_allowed(self) -> None:
        strategy = self.strategy()
        snapshot = strategy._long_signal_range_atr_snapshot(
            "long",
            self.history(signal_high=102.5, signal_low=101.5, signal_close=102.0),
            "flat_entry",
        )
        self.assertEqual(3.0, snapshot["long_signal_range_value"])
        self.assertEqual(3.0, snapshot["long_signal_range_atr_threshold"])
        self.assertEqual(0, snapshot["long_signal_range_atr_condition_met"])

    def test_signal_day_is_included_in_ten_day_range(self) -> None:
        strategy = self.strategy()
        history = self.history(signal_high=104.5, signal_low=103.5, signal_close=104.0)
        self.assertEqual(1.0, history.iloc[:-1]["high"].max() - history.iloc[:-1]["low"].min())
        snapshot = strategy._long_signal_range_atr_snapshot("long", history, "flat_entry")
        self.assertEqual(5.0, snapshot["long_signal_range_value"])
        self.assertEqual(1, snapshot["long_signal_range_atr_condition_met"])

    def test_short_and_add_context_are_excluded(self) -> None:
        strategy = self.strategy()
        history = self.history(signal_high=104.5, signal_low=103.5, signal_close=104.0)
        short = strategy._long_signal_range_atr_snapshot("short", history, "flat_entry")
        add = strategy._long_signal_range_atr_snapshot("long", history, "regular_add")
        self.assertEqual("direction_excluded", short["long_signal_range_atr_reason"])
        self.assertEqual("entry_context_excluded", add["long_signal_range_atr_reason"])
        self.assertEqual(0, short["long_signal_range_atr_condition_met"])
        self.assertEqual(0, add["long_signal_range_atr_condition_met"])

    def test_condition_after_existing_zero_volume_is_not_double_counted(self) -> None:
        strategy = self.strategy()
        snapshot = strategy._long_signal_range_atr_snapshot(
            "long",
            self.history(signal_high=104.5, signal_low=103.5, signal_close=104.0),
            "rollover_reopen",
        )
        sizing = strategy._apply_long_signal_range_atr_to_sizing(
            {"selected_volume": 0},
            snapshot,
            vt_symbol="rb2510.SHFE",
            direction="long",
            bar=SimpleNamespace(datetime=datetime(2026, 8, 26, 15, 0)),
            entry_context="rollover_reopen",
        )
        self.assertEqual(1, sizing["long_signal_range_atr_condition_met"])
        self.assertEqual(0, sizing["long_signal_range_atr_blocked"])
        self.assertEqual(0, sizing["selected_volume"])

    def test_insufficient_history_does_not_invent_a_block(self) -> None:
        strategy = self.strategy()
        snapshot = strategy._long_signal_range_atr_snapshot(
            "long",
            self.history(signal_high=104.5, signal_low=103.5, signal_close=104.0).tail(9),
            "flat_entry",
        )
        self.assertEqual("insufficient_history", snapshot["long_signal_range_atr_reason"])
        self.assertEqual(0, snapshot["long_signal_range_atr_condition_met"])

    def test_filter_contract_accepts_incremental_block_and_prior_zero_overlap(self) -> None:
        common = {
            "experiment_arm": "C",
            "long_signal_range_atr_enabled": 1,
            "long_signal_range_lookback": 10,
            "long_signal_range_atr_period": 5,
            "long_signal_range_atr_multiplier": 3.0,
            "long_signal_range_value": 5.0,
            "long_signal_range_prior_atr": 1.0,
            "long_signal_range_atr_threshold": 3.0,
            "long_signal_range_atr_condition_met": 1,
            "long_signal_range_atr_reason": "range_strictly_above_threshold",
        }
        diagnostics = pd.DataFrame(
            [
                {
                    **common,
                    "direction": "long",
                    "entry_context": "flat_entry",
                    "long_signal_range_atr_blocked": 1,
                    "long_signal_range_atr_selected_volume_before": 3,
                    "long_signal_range_atr_selected_volume_after": 0,
                },
                {
                    **common,
                    "direction": "long",
                    "entry_context": "rollover_reopen",
                    "long_signal_range_atr_blocked": 0,
                    "long_signal_range_atr_selected_volume_before": 0,
                    "long_signal_range_atr_selected_volume_after": 0,
                },
                {
                    **common,
                    "direction": "short",
                    "entry_context": "flat_entry",
                    "long_signal_range_value": float("nan"),
                    "long_signal_range_prior_atr": float("nan"),
                    "long_signal_range_atr_threshold": float("nan"),
                    "long_signal_range_atr_condition_met": 0,
                    "long_signal_range_atr_reason": "direction_excluded",
                    "long_signal_range_atr_blocked": 0,
                    "long_signal_range_atr_selected_volume_before": 2,
                    "long_signal_range_atr_selected_volume_after": 2,
                },
            ]
        )
        result = stage031._filter_contract(diagnostics)
        self.assertTrue(result["all_pass"])
        self.assertEqual(1, result["actual_incremental_block_count"])
        self.assertEqual(1, result["matched_after_prior_zero_count"])

    def test_full_period_coverage_rejects_late_start(self) -> None:
        summary = pd.DataFrame(
            {
                "experiment_arm": ["A", "B", "C"],
                "analysis_start": ["2018-01-02", "2018-01-02", "2018-01-03"],
                "analysis_end": ["2026-08-25"] * 3,
            }
        )
        reference_curve = pd.read_csv(
            ROOT
            / "research/lines/futures_trend_rollover_shape_same_volume/artifacts/stage028/stage028_abc_curve.csv"
        )
        dates = pd.to_datetime(
            reference_curve.loc[
                reference_curve["experiment_arm"].astype(str).eq("A"), "date"
            ],
            format="mixed",
        )
        curve = pd.concat(
            [
                pd.DataFrame({"experiment_arm": arm, "date": dates})
                for arm in ("A", "B", "C")
            ],
            ignore_index=True,
        )
        with self.assertRaisesRegex(RuntimeError, "full_period_coverage_failed"):
            stage031._assert_full_period_coverage(summary, curve)

    def test_report_preserves_candidate_event_boundary(self) -> None:
        artifact_dir = (
            ROOT
            / "research/lines/futures_trend_rollover_shape_same_volume/artifacts/stage031"
        )
        summary = pd.read_csv(artifact_dir / "stage031_abc_summary.csv")
        comparison = pd.read_csv(artifact_dir / "stage031_abc_comparison.csv")
        decision = json.loads((artifact_dir / "stage031_decision.json").read_text())
        report = stage031._report(summary, comparison, decision)
        self.assertEqual((artifact_dir / "stage031_report.md").read_text(), report)
        self.assertIn("sizing候选事件 `310` 个", report)
        self.assertIn("不是B路径原本必然成交的310笔反事实交易", report)


if __name__ == "__main__":
    unittest.main()
