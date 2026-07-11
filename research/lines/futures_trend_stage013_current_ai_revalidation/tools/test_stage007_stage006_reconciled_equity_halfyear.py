#!/usr/bin/env python3
"""Focused aggregate-gate tests for Stage007."""

from __future__ import annotations

import importlib
import unittest

import pandas as pd


class Stage007AggregateGateTest(unittest.TestCase):
    @staticmethod
    def _module():
        try:
            return importlib.import_module(
                "stage007_stage006_reconciled_equity_halfyear"
            )
        except ModuleNotFoundError as exc:
            raise AssertionError("Stage007 implementation module is missing") from exc

    def test_reconciliation_gate_requires_every_start_to_pass(self) -> None:
        module = self._module()
        frame = pd.DataFrame(
            {
                "requested_start_month": ["2020-01", "2020-07"],
                "reconciliation_pass": [True, True],
                "missing_date_count": [0, 0],
                "duplicate_date_count": [0, 0],
                "future_trade_violation_count": [0, 0],
            }
        )

        self.assertTrue(module._all_reconciliations_pass(frame, expected_count=2))
        frame.loc[1, "reconciliation_pass"] = False
        self.assertFalse(module._all_reconciliations_pass(frame, expected_count=2))

    def test_pilot_gate_rejects_any_semantic_violation(self) -> None:
        module = self._module()
        clean = pd.DataFrame(
            {
                "rows": [2, 0],
                "official_dd_below_trigger_count": [0, 0],
                "authoritative_dd_below_trigger_count": [0, 0],
                "non_flat_entry_count": [0, 0],
                "not_applied_count": [0, 0],
                "wrong_reason_count": [0, 0],
                "not_opened_count": [0, 0],
                "after_not_one_count": [0, 0],
                "above_active_limit_count": [0, 0],
                "event_equity_mismatch_count": [0, 0],
            }
        )

        self.assertTrue(module._all_pilot_semantics_pass(clean))
        clean.loc[1, "non_flat_entry_count"] = 1
        self.assertFalse(module._all_pilot_semantics_pass(clean))

    def test_tag_overrides_legacy_start_month_with_requested_start(self) -> None:
        module = self._module()
        frame = pd.DataFrame(
            {"start_month": ["2020-01"], "value": [1.0]}
        )

        tagged = module._tag(
            frame, pd.Timestamp("2022-07-01"), "candidate"
        )

        self.assertEqual(tagged.loc[0, "start_month"], "2022-07")
        self.assertEqual(tagged.loc[0, "requested_start_month"], "2022-07")


if __name__ == "__main__":
    unittest.main()
