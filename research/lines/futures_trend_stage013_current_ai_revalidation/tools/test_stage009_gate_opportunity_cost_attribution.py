#!/usr/bin/env python3
"""Focused tests for Stage009 gate opportunity-cost attribution."""

from __future__ import annotations

import importlib
from pathlib import Path
import sys
import tempfile
import unittest

import pandas as pd


TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


class Stage009GateOpportunityCostTest(unittest.TestCase):
    @staticmethod
    def _module():
        return importlib.import_module("stage009_gate_opportunity_cost_attribution")

    def test_window_drawdown_keeps_account_history_high_water(self) -> None:
        module = self._module()
        daily = pd.DataFrame(
            {
                "date": ["2021-06-01", "2021-12-31", "2022-01-03", "2022-02-01"],
                "account_equity": [200.0, 100.0, 90.0, 120.0],
            }
        )

        result = module._window_drawdown_metrics(
            daily,
            start=pd.Timestamp("2022-01-01"),
            end=pd.Timestamp("2022-12-31"),
        )

        self.assertAlmostEqual(result["historical_hwm_at_window_start"], 200.0)
        self.assertAlmostEqual(
            result["account_history_max_drawdown_pct"], -55.0
        )
        self.assertAlmostEqual(
            result["local_window_reset_max_drawdown_pct"], -10.0
        )

    def test_event_mapping_includes_same_day_retry_trade(self) -> None:
        module = self._module()
        event = pd.Series(
            {
                "date": "2022-01-03",
                "vt_symbol": "rb2205.SHFE",
                "direction": "long",
                "signal": "long_case2",
            }
        )
        candidates = pd.DataFrame(
            [
                {
                    "date": "2022-01-03",
                    "contract_vt_symbol": "rb2205.SHFE",
                    "direction": "long",
                    "signal": "long_case2",
                    "candidate_status": "opened",
                    "selected_volume": 1,
                    "ai_product_pool_rank": 2,
                }
            ]
        )
        trades = pd.DataFrame(
            [
                {
                    "trade_id": "open-1",
                    "date": "2022-01-04",
                    "vt_symbol": "rb2205.SHFE",
                    "direction": "Long",
                    "offset": "Open",
                    "volume": 1.0,
                },
                {
                    "trade_id": "open-2",
                    "date": "2022-01-04",
                    "vt_symbol": "rb2205.SHFE",
                    "direction": "Long",
                    "offset": "Open",
                    "volume": 1.0,
                },
            ]
        )
        closed_lots = pd.DataFrame(
            [
                {
                    "open_trade_id": "open-1",
                    "entry_date": "2022-01-04",
                    "exit_date": "2022-01-04",
                    "volume": 1,
                    "realized_pnl": -100.0,
                    "r_multiple": -1.0,
                },
                {
                    "open_trade_id": "open-2",
                    "entry_date": "2022-01-04",
                    "exit_date": "2022-01-05",
                    "volume": 1,
                    "realized_pnl": 250.0,
                    "r_multiple": 2.5,
                },
            ]
        )

        result = module._map_event_to_arm(
            event,
            candidates=candidates,
            trades=trades,
            closed_lots=closed_lots,
            arm_prefix="c",
            trading_dates=pd.Series(["2022-01-03", "2022-01-04", "2022-01-05"]),
        )

        self.assertEqual(result["c_mapping_status"], "mapped")
        self.assertEqual(result["c_open_trade_count"], 2)
        self.assertEqual(result["c_closed_lot_count"], 2)
        self.assertEqual(result["c_planned_volume"], 1.0)
        self.assertEqual(result["c_opened_volume_sum"], 2.0)
        self.assertEqual(result["c_realized_pnl"], 150.0)
        self.assertEqual(result["c_entry_date"], "2022-01-04")
        self.assertEqual(result["c_last_exit_date"], "2022-01-05")

    def test_event_mapping_rejects_ambiguous_opened_candidate(self) -> None:
        module = self._module()
        event = pd.Series(
            {
                "date": "2022-01-03",
                "vt_symbol": "rb2205.SHFE",
                "direction": "long",
                "signal": "long_case2",
            }
        )
        candidate = {
            "date": "2022-01-03",
            "contract_vt_symbol": "rb2205.SHFE",
            "direction": "long",
            "signal": "long_case2",
            "candidate_status": "opened",
            "selected_volume": 1,
        }

        with self.assertRaisesRegex(ValueError, "ambiguous opened candidate"):
            module._map_event_to_arm(
                event,
                candidates=pd.DataFrame([candidate, candidate]),
                trades=pd.DataFrame(),
                closed_lots=pd.DataFrame(),
                arm_prefix="c",
                trading_dates=pd.Series(["2022-01-03", "2022-01-04"]),
            )

    def test_event_mapping_rejects_open_after_next_trading_day(self) -> None:
        module = self._module()
        event = pd.Series(
            {
                "date": "2022-01-03",
                "vt_symbol": "rb2205.SHFE",
                "direction": "long",
                "signal": "long_case2",
            }
        )
        candidates = pd.DataFrame(
            [
                {
                    "date": "2022-01-03",
                    "contract_vt_symbol": "rb2205.SHFE",
                    "direction": "long",
                    "signal": "long_case2",
                    "candidate_status": "opened",
                    "selected_volume": 1,
                }
            ]
        )
        trades = pd.DataFrame(
            [
                {
                    "trade_id": "late-open",
                    "date": "2022-01-05",
                    "vt_symbol": "rb2205.SHFE",
                    "direction": "Long",
                    "offset": "Open",
                    "volume": 1,
                }
            ]
        )

        result = module._map_event_to_arm(
            event,
            candidates=candidates,
            trades=trades,
            closed_lots=pd.DataFrame(),
            arm_prefix="c",
            trading_dates=pd.Series(["2022-01-03", "2022-01-04", "2022-01-05"]),
        )

        self.assertEqual(result["c_mapping_status"], "open_not_next_trading_day")

    def test_event_mapping_accepts_partial_closes_only_when_volume_balances(self) -> None:
        module = self._module()
        event = pd.Series(
            {
                "date": "2022-01-03",
                "vt_symbol": "rb2205.SHFE",
                "direction": "long",
                "signal": "long_case2",
            }
        )
        candidates = pd.DataFrame(
            [
                {
                    "date": "2022-01-03",
                    "contract_vt_symbol": "rb2205.SHFE",
                    "direction": "long",
                    "signal": "long_case2",
                    "candidate_status": "opened",
                    "selected_volume": 2,
                }
            ]
        )
        trades = pd.DataFrame(
            [
                {
                    "trade_id": "open-1",
                    "date": "2022-01-04",
                    "vt_symbol": "rb2205.SHFE",
                    "direction": "Long",
                    "offset": "Open",
                    "volume": 2,
                }
            ]
        )
        lots = pd.DataFrame(
            [
                {
                    "open_trade_id": "open-1",
                    "entry_date": "2022-01-04",
                    "exit_date": "2022-01-05",
                    "volume": 1.0,
                    "realized_pnl": 10.0,
                    "r_multiple": 0.1,
                    "signal": "long_case2",
                },
                {
                    "open_trade_id": "open-1",
                    "entry_date": "2022-01-04",
                    "exit_date": "2022-01-06",
                    "volume": 1.0,
                    "realized_pnl": 20.0,
                    "r_multiple": 0.2,
                    "signal": "long_case2",
                },
            ]
        )
        clean = module._map_event_to_arm(
            event,
            candidates=candidates,
            trades=trades,
            closed_lots=lots,
            arm_prefix="c",
            trading_dates=pd.Series(["2022-01-03", "2022-01-04"]),
        )
        self.assertEqual(clean["c_mapping_status"], "mapped")
        self.assertEqual(clean["c_closed_lot_count"], 2)

        lots.loc[1, "volume"] = 0.5
        dirty = module._map_event_to_arm(
            event,
            candidates=candidates,
            trades=trades,
            closed_lots=lots,
            arm_prefix="c",
            trading_dates=pd.Series(["2022-01-03", "2022-01-04"]),
        )
        self.assertEqual(dirty["c_mapping_status"], "closed_volume_mismatch")

    def test_linear_counterfactual_is_explicitly_same_path(self) -> None:
        module = self._module()
        winner = module._linear_counterfactual_fields(
            realized_pnl=150.0,
            selected_volume_before=3.0,
            selected_volume_after=1.0,
        )
        loser = module._linear_counterfactual_fields(
            realized_pnl=-150.0,
            selected_volume_before=3.0,
            selected_volume_after=1.0,
        )

        self.assertEqual(winner["same_path_linear_pnl_at_before"], 450.0)
        self.assertEqual(winner["same_path_linear_delta_vs_actual"], 300.0)
        self.assertEqual(winner["suppressed_gain_same_path"], 300.0)
        self.assertEqual(winner["avoided_loss_same_path"], 0.0)
        self.assertEqual(loser["same_path_linear_delta_vs_actual"], -300.0)
        self.assertEqual(loser["suppressed_gain_same_path"], 0.0)
        self.assertEqual(loser["avoided_loss_same_path"], 300.0)

    def test_coverage_keeps_zero_event_starts_and_fails_unmapped_rows(self) -> None:
        module = self._module()
        expected = pd.DataFrame(
            {
                "requested_start_month": ["2022-01", "2023-01"],
                "rows": [1, 0],
            }
        )
        mapped = pd.DataFrame(
            {
                "requested_start_month": ["2022-01"],
                "c_mapping_status": ["mapped"],
                "a_mapping_status": ["mapped"],
            }
        )

        clean = module._coverage(expected, mapped)
        self.assertEqual(clean["requested_start_month"].tolist(), ["2022-01", "2023-01"])
        self.assertTrue(module._coverage_pass(clean))

        mapped.loc[0, "a_mapping_status"] = "missing_open_trade"
        dirty = module._coverage(expected, mapped)
        self.assertFalse(module._coverage_pass(dirty))

    def test_manifest_verifier_fails_closed_after_file_change(self) -> None:
        module = self._module()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact = root / "artifact.txt"
            artifact.write_text("stable", encoding="utf-8")
            manifest = pd.DataFrame(
                [
                    {
                        "file": artifact.name,
                        "bytes": artifact.stat().st_size,
                        "sha256": module._sha256(artifact),
                    }
                ]
            )
            manifest_path = root / "manifest.csv"
            manifest.to_csv(manifest_path, index=False)

            self.assertTrue(module._verify_manifest(root, manifest_path)["pass"])
            artifact.write_text("changed", encoding="utf-8")
            self.assertFalse(module._verify_manifest(root, manifest_path)["pass"])


if __name__ == "__main__":
    unittest.main()
