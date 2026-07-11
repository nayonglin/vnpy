#!/usr/bin/env python3
"""Focused aggregate tests for Stage008 slippage stress."""

from __future__ import annotations

import importlib
import unittest

import pandas as pd


class Stage008SlippageStressTest(unittest.TestCase):
    @staticmethod
    def _module():
        try:
            return importlib.import_module(
                "stage008_reconciled_equity_slippage_stress"
            )
        except ModuleNotFoundError as exc:
            raise AssertionError("Stage008 implementation module is missing") from exc

    def test_all_cost_reconciliations_require_each_multiplier(self) -> None:
        module = self._module()
        frame = pd.DataFrame(
            {
                "slippage_multiplier": [1.0, 2.0, 3.0],
                "reconciliation_pass": [True, True, True],
                "missing_date_count": [0, 0, 0],
                "duplicate_date_count": [0, 0, 0],
                "post_end_audit_count": [0, 0, 0],
                "pre_start_invalid_count": [0, 0, 0],
                "in_range_extra_audit_count": [0, 0, 0],
                "future_trade_violation_count": [0, 0, 0],
            }
        )

        self.assertTrue(module._all_cost_reconciliations_pass(frame))
        frame.loc[2, "post_end_audit_count"] = 1
        self.assertFalse(module._all_cost_reconciliations_pass(frame))

    def test_paired_gate_uses_same_cost_control(self) -> None:
        module = self._module()
        result = module._paired_gate_row(
            3.0,
            {
                "total_return_pct": 100.0,
                "max_drawdown_pct": -50.0,
                "max_broker10_margin_to_equity_pct": 80.0,
            },
            {
                "total_return_pct": 75.0,
                "max_drawdown_pct": -40.0,
                "max_broker10_margin_to_equity_pct": 79.0,
            },
            {"year_2022": -35.0, "main_2022_2024_stress": -45.0},
            {"year_2022": -29.0, "main_2022_2024_stress": -40.0},
        )

        self.assertAlmostEqual(result["same_cost_return_retention_ratio"], 0.75)
        self.assertTrue(result["performance_gate_pass"])


if __name__ == "__main__":
    unittest.main()
