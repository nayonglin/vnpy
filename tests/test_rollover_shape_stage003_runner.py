from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd


TOOLS_DIR = (
    Path(__file__).resolve().parents[1]
    / "research"
    / "lines"
    / "futures_trend_rollover_shape_same_volume"
    / "tools"
)
sys.path.insert(0, str(TOOLS_DIR))

import stage003_rollover_same_day_continuous_abc as stage003


class Stage003RunnerTest(unittest.TestCase):
    @staticmethod
    def _continuous_diagnostic(**overrides: object) -> pd.DataFrame:
        row: dict[str, object] = {
            "history_mode": "backwards_ratio_continuous",
            "target_observed_bar_count": 1,
            "source_observed_bar_count": 41,
            "observed_bar_count": 41,
            "required_bar_count": 40,
            "history_input_ready": 1,
            "same_day_bar_ready": 1,
            "market_data_ready": 1,
            "metadata_ready": 1,
            "roll_adjustment_ratio": 0.4,
            "reason": "previous_volume_fully_allowed",
        }
        row.update(overrides)
        return pd.DataFrame([row])

    def test_continuous_contract_accepts_one_target_bar(self) -> None:
        passed, bypass_count = stage003._history_contract_pass(
            self._continuous_diagnostic(),
            expected_mode="backwards_ratio_continuous",
            rollover_close_count=1,
        )

        self.assertTrue(passed)
        self.assertEqual(1, bypass_count)

    def test_continuous_contract_rejects_hidden_target_history_gate(self) -> None:
        passed, bypass_count = stage003._history_contract_pass(
            self._continuous_diagnostic(reason="insufficient_indicator_history"),
            expected_mode="backwards_ratio_continuous",
            rollover_close_count=1,
        )

        self.assertFalse(passed)
        self.assertEqual(1, bypass_count)

    def test_continuous_contract_rejects_missing_metadata(self) -> None:
        passed, _bypass_count = stage003._history_contract_pass(
            self._continuous_diagnostic(metadata_ready=0),
            expected_mode="backwards_ratio_continuous",
            rollover_close_count=1,
        )

        self.assertFalse(passed)

    def test_atomic_publish_uses_stage_specific_decision_filename(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_root:
            output_dir = Path(temporary_root) / "stage003"

            stage003.s2._publish_outputs_atomically(
                output_dir,
                {"result.csv": pd.DataFrame([{"value": 1}])},
                {"stage": "Stage003"},
                decision_filename="stage003_decision.json",
            )

            self.assertTrue((output_dir / "stage003_decision.json").exists())
            self.assertFalse((output_dir / "stage002_decision.json").exists())


if __name__ == "__main__":
    unittest.main()
