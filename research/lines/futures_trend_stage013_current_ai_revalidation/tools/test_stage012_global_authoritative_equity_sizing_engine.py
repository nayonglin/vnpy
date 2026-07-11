#!/usr/bin/env python3
"""Focused tests for the Stage012 global authoritative-equity sizing engine."""

from __future__ import annotations

import importlib
from pathlib import Path
import sys
import unittest

import pandas as pd


TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


class Stage012GlobalAuthoritativeEquitySizingTest(unittest.TestCase):
    @staticmethod
    def _module():
        return importlib.import_module("stage012_global_authoritative_equity_sizing_engine")

    def test_immediate_trade_correction_subtracts_current_duplicate_only(self) -> None:
        module = self._module()

        result = module._immediate_trade_equity_correction(
            settled_balance=120.0,
            estimated_equity=118.0,
            cumulative_duplicate_before=10.0,
            cumulative_duplicate_after=13.0,
        )

        self.assertEqual(result["current_duplicate_pnl"], 3.0)
        self.assertEqual(result["corrected_settled_balance"], 117.0)
        self.assertEqual(result["corrected_estimated_equity"], 115.0)

    def test_legacy_counterfactual_reconciles_back_to_corrected_equity(self) -> None:
        module = self._module()

        legacy = module._legacy_counterfactual_equity(
            corrected_equity=100.0,
            cumulative_duplicate_pnl=30.0,
        )

        self.assertEqual(legacy, 130.0)
        self.assertEqual(
            module.s6._reconciled_equity_from_legacy(legacy, 30.0),
            100.0,
        )

    def test_sizing_alignment_requires_every_candidate_day_and_daily_identity(self) -> None:
        module = self._module()
        clean = pd.DataFrame(
            {
                "requested_start_month": ["2021-01", "2021-01"],
                "legacy_minus_official_same_day": [0.0, 1e-10],
                "official_daily_identity_error": [0.0, -1e-10],
            }
        )

        self.assertTrue(module._sizing_alignment_pass(clean, expected_starts={"2021-01"}))
        dirty = clean.copy()
        dirty.loc[1, "legacy_minus_official_same_day"] = 1.0
        self.assertFalse(module._sizing_alignment_pass(dirty, expected_starts={"2021-01"}))
        self.assertFalse(
            module._sizing_alignment_pass(clean.iloc[0:0], expected_starts={"2021-01"})
        )

    def test_output_directory_is_inside_current_repository_line(self) -> None:
        module = self._module()

        self.assertEqual(
            module.OUT,
            TOOLS_DIR.parent / "outputs" / module.STAGE_ID,
        )


if __name__ == "__main__":
    unittest.main()
