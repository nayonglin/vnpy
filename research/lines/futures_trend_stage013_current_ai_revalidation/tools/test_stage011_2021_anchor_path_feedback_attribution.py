#!/usr/bin/env python3
"""Focused tests for the Stage011 2021-anchor path-feedback attribution."""

from __future__ import annotations

import importlib
from pathlib import Path
import sys
import unittest

import pandas as pd


TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


class Stage011PathFeedbackAttributionTest(unittest.TestCase):
    @staticmethod
    def _module():
        return importlib.import_module("stage011_2021_anchor_path_feedback_attribution")

    def test_account_history_peak_trough_uses_new_high_inside_window(self) -> None:
        module = self._module()
        daily = pd.DataFrame(
            {
                "date": ["2021-12-31", "2022-01-03", "2022-02-01", "2022-03-01"],
                "account_equity": [100.0, 90.0, 120.0, 60.0],
            }
        )

        result = module._account_history_peak_trough(
            daily,
            window_start="2022-01-01",
            window_end="2022-12-31",
        )

        self.assertEqual(result["peak_date"], "2022-02-01")
        self.assertEqual(result["trough_date"], "2022-03-01")
        self.assertEqual(result["peak_equity"], 120.0)
        self.assertEqual(result["trough_equity"], 60.0)
        self.assertAlmostEqual(result["max_drawdown_pct"], -50.0)

    def test_pretrade_equity_audit_uses_same_day_official_account_equity(self) -> None:
        module = self._module()
        daily = pd.DataFrame(
            {
                "date": ["2022-01-03", "2022-01-04"],
                "account_capital": [100.0, 100.0],
                "account_equity": [100.0, 105.0],
                "holding_pnl": [0.0, -10.0],
                "trading_pnl": [0.0, 20.0],
                "commission": [0.0, 2.0],
                "slippage": [0.0, 3.0],
            }
        )
        candidates = pd.DataFrame(
            {
                "date": ["2022-01-04", "2022-01-04"],
                "estimated_equity": [120.0, 120.0],
            }
        )

        result = module._pretrade_equity_audit(candidates, daily)

        self.assertEqual(len(result), 1)
        self.assertEqual(result.loc[0, "official_same_day_equity"], 105.0)
        self.assertEqual(result.loc[0, "legacy_estimated_equity"], 120.0)
        self.assertEqual(result.loc[0, "legacy_minus_official_same_day"], 15.0)
        self.assertEqual(result.loc[0, "official_daily_identity_error"], 0.0)
        self.assertEqual(result.loc[0, "within_day_estimated_equity_range"], 0.0)

    def test_signal_key_normalizes_date_direction_and_exact_signal(self) -> None:
        module = self._module()
        row = pd.Series(
            {
                "date": "2022-01-11 16:00:00",
                "contract_vt_symbol": "CF205.CZCE",
                "direction": "Long",
                "signal": "long_case2",
            }
        )

        self.assertEqual(
            module._signal_key(row),
            ("2022-01-11", "CF205.CZCE", "long", "long_case2"),
        )

    def test_source_path_uses_stage010_persisted_arm_naming(self) -> None:
        module = self._module()

        path = module._source_path("a", "daily")

        self.assertEqual(
            path.name,
            "stage013_current_ai_stage010_drawdown_recovery_progress_ramp_"
            "2021-01_a_current_ai_c9_control_daily_"
            "stage010_drawdown_recovery_progress_ramp_v1.csv.gz",
        )

    def test_manifest_uses_shared_fail_closed_verifier_schema(self) -> None:
        module = self._module()

        manifest = module._manifest()

        self.assertEqual(list(manifest.columns), ["file", "bytes", "sha256"])

    def test_daily_path_keeps_history_needed_for_account_hwm(self) -> None:
        module = self._module()
        a = pd.DataFrame(
            {
                "date": ["2021-10-26", "2022-01-03"],
                "account_equity": [110.0, 100.0],
                "net_pnl": [10.0, -10.0],
            }
        )
        c = a.copy()

        result = module._daily_path(a, c)

        self.assertEqual(result["date"].dt.date.astype(str).tolist(), ["2021-10-26", "2022-01-03"])

    def test_frozen_stage010_signal_partition_and_residual(self) -> None:
        module = self._module()
        source_manifest = module.s9._verify_manifest(
            module.s10.OUT, module.s10.MANIFEST_PATH
        )
        self.assertTrue(source_manifest["pass"])
        frames = {}
        for arm in module.ARM_FILES:
            for kind in ("daily", "entry_candidates", "trades", "closed_lots"):
                frames[(arm, kind)] = module._load(arm, kind)
        c_peak = module._account_history_peak_trough(
            frames[("c", "daily")],
            window_start=module.WINDOW_START,
            window_end=module.WINDOW_END,
        )
        signals = module._map_signal_union(
            frames,
            module._load("c", "stage010_ramp_events"),
            pd.Timestamp(c_peak["trough_date"]),
        )
        groups = module._signal_groups(signals)

        self.assertEqual(len(signals), 35)
        self.assertEqual(int(signals["direct_ramp_signal"].sum()), 19)
        self.assertEqual(int((~signals["direct_ramp_signal"]).sum()), 16)
        self.assertEqual(
            signals.groupby(["a_mapping_status", "c_mapping_status"]).size().to_dict(),
            {("mapped", "mapped"): 34, ("missing_opened_candidate", "mapped"): 1},
        )
        closed = groups[groups["scope"].eq("both_closed_by_c_trough")].set_index(
            "path_bucket"
        )
        self.assertEqual(int(closed.loc["direct_ramp", "signal_count"]), 17)
        self.assertEqual(
            int(closed.loc["indirect_path_feedback", "signal_count"]), 14
        )
        self.assertAlmostEqual(
            closed.loc["direct_ramp", "c_minus_a_realized_pnl"], 109_980.0
        )
        self.assertAlmostEqual(
            closed.loc["indirect_path_feedback", "c_minus_a_realized_pnl"],
            -195_522.4,
        )
        self.assertAlmostEqual(
            module._unexplained_equity_residual(
                c_minus_a_equity=-101_122.4,
                explained_realized_pnl=109_980.0 - 195_522.4,
            ),
            -15_580.0,
        )


if __name__ == "__main__":
    unittest.main()
