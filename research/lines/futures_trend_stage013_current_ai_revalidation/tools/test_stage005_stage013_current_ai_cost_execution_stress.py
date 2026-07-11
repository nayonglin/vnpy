#!/usr/bin/env python3
"""Focused tests for the Stage005 cost-stress helpers."""

from __future__ import annotations

import importlib
from pathlib import Path
import tempfile
import unittest

import pandas as pd


class Stage005CostStressTest(unittest.TestCase):
    @staticmethod
    def _module():
        try:
            return importlib.import_module("stage005_stage013_current_ai_cost_execution_stress")
        except ModuleNotFoundError as exc:
            raise AssertionError("Stage005 implementation module is missing") from exc

    def test_scaled_metadata_is_exact_and_does_not_mutate_source(self) -> None:
        module = self._module()
        original = {
            "slippages": {"a.DCE": 1.5, "b.CZCE": 2.0},
            "sizes": {"a.DCE": 10.0, "b.CZCE": 5.0},
        }

        scaled, audit = module._scaled_metadata(original, 3.0)

        self.assertEqual(original["slippages"], {"a.DCE": 1.5, "b.CZCE": 2.0})
        self.assertEqual(scaled["slippages"], {"a.DCE": 4.5, "b.CZCE": 6.0})
        self.assertIsNot(scaled, original)
        self.assertIsNot(scaled["slippages"], original["slippages"])
        self.assertEqual(audit["symbol_count"], 2)
        self.assertEqual(audit["ratio_error_count"], 0)
        self.assertEqual(audit["missing_symbol_count"], 0)

    def test_pair_gate_compares_candidate_to_same_cost_control(self) -> None:
        module = self._module()
        a = {
            "total_return_pct": 100.0,
            "max_drawdown_pct": -40.0,
            "max_broker10_margin_to_equity_pct": 80.0,
        }
        c = {
            "total_return_pct": 75.0,
            "max_drawdown_pct": -35.0,
            "max_broker10_margin_to_equity_pct": 79.0,
        }
        a_windows = {"year_2022": -30.0, "main_2022_2024_stress": -45.0}
        c_windows = {"year_2022": -24.0, "main_2022_2024_stress": -40.0}

        result = module._paired_gate_row(2.0, a, c, a_windows, c_windows)

        self.assertAlmostEqual(result["same_cost_return_retention_ratio"], 0.75)
        self.assertAlmostEqual(result["full_drawdown_improvement_pct"], 5.0)
        self.assertAlmostEqual(result["year_2022_drawdown_improvement_pct"], 6.0)
        self.assertAlmostEqual(result["main_stress_drawdown_improvement_pct"], 5.0)
        self.assertAlmostEqual(result["broker10_peak_delta_pct"], -1.0)
        self.assertTrue(result["performance_gate_pass"])

    def test_persisted_daily_comparison_uses_two_serialized_artifacts(self) -> None:
        module = self._module()
        self.assertTrue(
            hasattr(module, "_compare_persisted_daily"),
            "persisted artifact comparison helper is missing",
        )
        row = {"date": "2026-01-01"}
        row.update({column: 1.234567890123 for column in module.CORE_DAILY_COLUMNS})
        with tempfile.TemporaryDirectory() as directory:
            reference = Path(directory) / "reference.csv.gz"
            fresh = Path(directory) / "fresh.csv.gz"
            pd.DataFrame([row]).to_csv(reference, index=False)
            pd.DataFrame([row]).to_csv(fresh, index=False)

            result = module._compare_persisted_daily(reference, fresh)

        self.assertEqual(result["missing_date_count"], 0)
        self.assertEqual(result["daily_mismatch_cell_count"], 0)
        self.assertEqual(result["daily_max_abs_difference"], 0.0)
        self.assertTrue(result["core_daily_hash_equal"])


if __name__ == "__main__":
    unittest.main()
