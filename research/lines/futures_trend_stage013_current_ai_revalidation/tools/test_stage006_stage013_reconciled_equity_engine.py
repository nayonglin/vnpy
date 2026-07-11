#!/usr/bin/env python3
"""Focused tests for the Stage006 reconciled-equity helpers."""

from __future__ import annotations

import importlib
import unittest

import pandas as pd


class Stage006ReconciledEquityTest(unittest.TestCase):
    @staticmethod
    def _module():
        try:
            return importlib.import_module("stage006_stage013_reconciled_equity_engine")
        except ModuleNotFoundError as exc:
            raise AssertionError("Stage006 implementation module is missing") from exc

    def test_duplicate_close_to_close_term_for_open_trade(self) -> None:
        module = self._module()

        duplicate = module._close_to_close_duplicate_pnl(
            signed_volume=2.0,
            previous_close=100.0,
            current_close=110.0,
            contract_size=10.0,
        )

        self.assertEqual(duplicate, 200.0)

    def test_reconciled_equity_matches_official_daily_pnl_identity(self) -> None:
        module = self._module()
        previous_equity = 1_000.0
        start_position = 3.0
        signed_volume = 2.0
        previous_close = 100.0
        current_close = 110.0
        trade_price = 105.0
        contract_size = 10.0
        cost = 4.0

        legacy_equity = (
            previous_equity
            + signed_volume * (current_close - trade_price) * contract_size
            - cost
            + (start_position + signed_volume)
            * (current_close - previous_close)
            * contract_size
        )
        cumulative_duplicate = module._close_to_close_duplicate_pnl(
            signed_volume=signed_volume,
            previous_close=previous_close,
            current_close=current_close,
            contract_size=contract_size,
        )
        reconciled = module._reconciled_equity_from_legacy(
            legacy_equity, cumulative_duplicate
        )
        official = (
            previous_equity
            + start_position * (current_close - previous_close) * contract_size
            + signed_volume * (current_close - trade_price) * contract_size
            - cost
        )

        self.assertEqual(legacy_equity, 1_596.0)
        self.assertEqual(reconciled, official)
        self.assertEqual(reconciled, 1_396.0)

    def test_open_then_close_duplicate_terms_are_signed(self) -> None:
        module = self._module()
        open_duplicate = module._close_to_close_duplicate_pnl(
            signed_volume=4.0,
            previous_close=200.0,
            current_close=190.0,
            contract_size=5.0,
        )
        close_duplicate = module._close_to_close_duplicate_pnl(
            signed_volume=-3.0,
            previous_close=200.0,
            current_close=190.0,
            contract_size=5.0,
        )

        self.assertEqual(open_duplicate, -200.0)
        self.assertEqual(close_duplicate, 150.0)
        self.assertEqual(open_duplicate + close_duplicate, -50.0)

    def test_first_day_without_previous_close_has_zero_duplicate(self) -> None:
        module = self._module()

        duplicate = module._close_to_close_duplicate_pnl(
            signed_volume=8.0,
            previous_close=321.5,
            current_close=321.5,
            contract_size=20.0,
        )

        self.assertEqual(duplicate, 0.0)

    def test_same_day_synthetic_open_and_full_close_cancel_duplicate(self) -> None:
        module = self._module()
        changes = (12.0, -12.0)

        duplicate = sum(
            module._close_to_close_duplicate_pnl(
                signed_volume=change,
                previous_close=4_000.0,
                current_close=4_120.0,
                contract_size=10.0,
            )
            for change in changes
        )

        self.assertEqual(duplicate, 0.0)

    def test_multiple_same_day_trades_accumulate_linearly(self) -> None:
        module = self._module()
        changes = (5.0, -2.0, 4.0, -1.0)
        expected_net_change = sum(changes)

        duplicate = sum(
            module._close_to_close_duplicate_pnl(
                signed_volume=change,
                previous_close=700.0,
                current_close=680.0,
                contract_size=5.0,
            )
            for change in changes
        )
        expected = expected_net_change * (680.0 - 700.0) * 5.0

        self.assertEqual(duplicate, expected)

    def test_reconciliation_rejects_post_end_audit_rows(self) -> None:
        module = self._module()
        daily = pd.DataFrame(
            {
                "date": ["2026-01-02", "2026-01-05"],
                "account_equity": [150_000.0, 151_000.0],
            }
        )
        audit = pd.DataFrame(
            {
                "date": ["2026-01-01", "2026-01-02", "2026-01-05", "2026-01-06"],
                "stage006_authoritative_equity": [150_000.0, 150_000.0, 151_000.0, 151_000.0],
                "stage006_authoritative_high_water": [150_000.0, 150_000.0, 151_000.0, 151_000.0],
                "stage006_authoritative_drawdown_pct": [0.0, 0.0, 0.0, 0.0],
                "stage006_cumulative_duplicate_pnl": [0.0, 0.0, 0.0, 0.0],
            }
        )
        result = module._equity_reconciliation(
            daily,
            {
                "stage006_equity_daily": audit,
                "stage006_trade_corrections": pd.DataFrame(),
            },
        ).iloc[0]

        self.assertIn("post_end_audit_count", result.index)
        self.assertEqual(int(result["pre_start_audit_count"]), 1)
        self.assertEqual(int(result["post_end_audit_count"]), 1)
        self.assertFalse(bool(result["reconciliation_pass"]))


if __name__ == "__main__":
    unittest.main()
