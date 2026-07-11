#!/usr/bin/env python3
"""Focused tests for the Stage010 drawdown recovery-progress ramp."""

from __future__ import annotations

import importlib
from pathlib import Path
import sys
import unittest

import pandas as pd


TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


class Stage010RecoveryProgressRampTest(unittest.TestCase):
    @staticmethod
    def _module():
        return importlib.import_module("stage010_drawdown_recovery_progress_ramp")

    def test_episode_state_resets_below_trigger_and_tracks_new_low(self) -> None:
        module = self._module()

        entered = module._update_episode_state(
            episode_active=False,
            episode_peak_drawdown=0.0,
            current_drawdown=0.31,
            trigger_drawdown=0.30,
        )
        held = module._update_episode_state(
            episode_active=entered["episode_active"],
            episode_peak_drawdown=entered["episode_peak_drawdown"],
            current_drawdown=0.305,
            trigger_drawdown=0.30,
        )
        new_low = module._update_episode_state(
            episode_active=held["episode_active"],
            episode_peak_drawdown=held["episode_peak_drawdown"],
            current_drawdown=0.36,
            trigger_drawdown=0.30,
        )
        reset = module._update_episode_state(
            episode_active=new_low["episode_active"],
            episode_peak_drawdown=new_low["episode_peak_drawdown"],
            current_drawdown=0.29,
            trigger_drawdown=0.30,
        )

        self.assertEqual(entered, {"episode_active": True, "episode_peak_drawdown": 0.31})
        self.assertEqual(held, {"episode_active": True, "episode_peak_drawdown": 0.31})
        self.assertEqual(new_low, {"episode_active": True, "episode_peak_drawdown": 0.36})
        self.assertEqual(reset, {"episode_active": False, "episode_peak_drawdown": 0.0})

    def test_ramp_is_one_at_new_low_and_full_at_trigger(self) -> None:
        module = self._module()

        low = module._evaluate_recovery_ramp(
            selected_volume_before=10,
            entry_context="flat_entry",
            active_positions_before=0,
            current_drawdown=0.40,
            episode_peak_drawdown=0.40,
        )
        recovered = module._evaluate_recovery_ramp(
            selected_volume_before=10,
            entry_context="flat_entry",
            active_positions_before=0,
            current_drawdown=0.30,
            episode_peak_drawdown=0.40,
        )

        self.assertEqual(low["selected_volume_after"], 1)
        self.assertEqual(low["recovery_progress"], 0.0)
        self.assertEqual(recovered["selected_volume_after"], 10)
        self.assertEqual(recovered["recovery_progress"], 1.0)

    def test_ramp_uses_conservative_floor_at_half_recovery(self) -> None:
        module = self._module()

        result = module._evaluate_recovery_ramp(
            selected_volume_before=10,
            entry_context="flat_entry",
            active_positions_before=1,
            current_drawdown=0.35,
            episode_peak_drawdown=0.40,
        )

        self.assertAlmostEqual(result["recovery_progress"], 0.5)
        self.assertEqual(result["selected_volume_after"], 5)
        self.assertEqual(result["reduced_volume"], 5)
        self.assertEqual(result["applied"], 1)

    def test_ramp_does_not_apply_outside_frozen_gate(self) -> None:
        module = self._module()
        cases = (
            {"entry_context": "reverse_entry", "active": 0, "dd": 0.40},
            {"entry_context": "flat_entry", "active": 2, "dd": 0.40},
            {"entry_context": "flat_entry", "active": 0, "dd": 0.29},
        )
        for case in cases:
            with self.subTest(case=case):
                result = module._evaluate_recovery_ramp(
                    selected_volume_before=10,
                    entry_context=case["entry_context"],
                    active_positions_before=case["active"],
                    current_drawdown=case["dd"],
                    episode_peak_drawdown=max(case["dd"], 0.40),
                )
                self.assertEqual(result["selected_volume_after"], 10)
                self.assertEqual(result["applied"], 0)
                self.assertEqual(result["eligible"], 0)

    def test_ramp_audit_rejects_formula_or_state_violation(self) -> None:
        module = self._module()
        clean = pd.DataFrame(
            [
                {
                    "requested_start_month": "2022-01",
                    "stage010_ramp_eligible": 1,
                    "stage010_ramp_applied": 1,
                    "stage010_ramp_selected_volume_before": 10,
                    "stage010_ramp_selected_volume_after": 5,
                    "stage010_ramp_expected_volume_after": 5,
                    "stage010_ramp_recovery_progress": 0.5,
                    "stage010_ramp_current_drawdown": 0.35,
                    "stage010_ramp_episode_peak_drawdown": 0.40,
                    "stage010_ramp_trigger_drawdown": 0.30,
                    "stage010_ramp_active_positions_before": 1,
                    "stage010_ramp_active_positions_max": 1,
                }
            ]
        )

        self.assertTrue(module._ramp_semantics_pass(module._ramp_audit(clean)))
        clean.loc[0, "stage010_ramp_selected_volume_after"] = 6
        self.assertFalse(module._ramp_semantics_pass(module._ramp_audit(clean)))

    def test_anchor_gate_requires_return_drawdown_2022_and_broker(self) -> None:
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
        clean_rows = [
            module._anchor_gate_row(
                requested_start_month=start.strftime("%Y-%m"),
                a=a,
                c=c,
                a_2022_account_history_drawdown=-36.0,
                c_2022_account_history_drawdown=-34.0,
            )
            for start in module.ANCHOR_STARTS
        ]

        self.assertTrue(module._anchor_performance_pass(pd.DataFrame(clean_rows)))
        self.assertAlmostEqual(clean_rows[0]["return_retention_ratio"], 0.75)
        self.assertAlmostEqual(
            clean_rows[0]["account_history_2022_dd_improvement_pp"], 2.0
        )

        dirty = module._anchor_gate_row(
            requested_start_month="2021-01",
            a=a,
            c=c,
            a_2022_account_history_drawdown=-36.0,
            c_2022_account_history_drawdown=-37.0,
        )
        self.assertAlmostEqual(dirty["account_history_2022_dd_improvement_pp"], -1.0)
        self.assertFalse(dirty["account_history_2022_drawdown_pass"])
        self.assertFalse(dirty["anchor_performance_pass"])

        rows_with_failure = [
            row
            for row in clean_rows
            if row["requested_start_month"] != "2021-01"
        ]
        rows_with_failure.append(dirty)
        self.assertFalse(module._anchor_performance_pass(pd.DataFrame(rows_with_failure)))

    def test_candidate_event_coverage_reconstructs_eligibility_by_daily_state(self) -> None:
        module = self._module()
        candidates = pd.DataFrame(
            [
                {
                    "date": "2022-06-10",
                    "contract_vt_symbol": "MA209.CZCE",
                    "direction": "long",
                    "signal": "long_case2",
                    "entry_context": "flat_entry",
                    "candidate_status": "opened",
                    "active_positions_before": 0,
                    "selected_volume": 1,
                },
                {
                    "date": "2022-06-10",
                    "contract_vt_symbol": "rb2210.SHFE",
                    "direction": "short",
                    "signal": "short_case2",
                    "entry_context": "flat_entry",
                    "candidate_status": "opened",
                    "active_positions_before": 2,
                    "selected_volume": 3,
                },
            ]
        )
        episode = pd.DataFrame(
            [
                {
                    "date": "2022-06-10",
                    "stage010_episode_current_drawdown": 0.33,
                }
            ]
        )
        events = pd.DataFrame(
            [
                {
                    "date": "2022-06-10",
                    "vt_symbol": "MA209.CZCE",
                    "direction": "long",
                    "signal": "long_case2",
                    "stage010_ramp_selected_volume_after": 1,
                }
            ]
        )

        clean = module._candidate_event_coverage(candidates, episode, events)
        self.assertEqual(clean["candidate_eligible_count"], 1)
        self.assertEqual(clean["event_count"], 1)
        self.assertEqual(clean["candidate_event_mismatch_count"], 0)

        events.loc[0, "vt_symbol"] = "wrong.SHFE"
        dirty = module._candidate_event_coverage(candidates, episode, events)
        self.assertGreater(dirty["candidate_event_mismatch_count"], 0)


if __name__ == "__main__":
    unittest.main()
