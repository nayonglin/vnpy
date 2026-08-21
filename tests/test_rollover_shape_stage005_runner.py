from __future__ import annotations

import sys
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

import stage005_multicycle_equity_comparison as stage005


class Stage005RunnerTest(unittest.TestCase):
    def test_frozen_window_counts(self) -> None:
        windows = pd.DataFrame(stage005.WINDOWS)
        self.assertEqual(43, len(windows))
        self.assertEqual(1, int(windows["window_group"].eq("full_period").sum()))
        for years, complete_count in [(1, 15), (2, 13), (3, 11)]:
            group = windows[windows["duration_years"].eq(years)]
            self.assertEqual(complete_count, int(group["complete"].sum()))
            self.assertEqual(1, int(group["terminal_near_complete"].sum()))

    def test_decision_fails_closed_when_one_cycle_gate_fails(self) -> None:
        comparison = pd.DataFrame(
            [
                {
                    "window_group": "full_period",
                    "C_return_pct": 1.0,
                    "A_return_pct": 0.0,
                    "dd_worsening_pp": 0.0,
                    "delta_sharpe": 0.0,
                    "C_slippage": 100.0,
                    "A_slippage": 100.0,
                    "C_survival_pass": 1,
                }
            ]
        )
        aggregate = pd.DataFrame(
            [
                {
                    "duration_years": years,
                    "return_win_rate_pct": 100.0,
                    "median_return_delta_pct": 1.0,
                    "dd_noninferior_2pp_rate_pct": 100.0,
                    "C_dd50_fail_count": 0,
                    "A_dd50_fail_count": 0,
                    "sharpe_noninferior_005_rate_pct": 100.0,
                    "slippage_ratio": 1.06 if years == 2 else 1.0,
                    "all_candidate_survival": 1,
                    "C_broker100_fail_count": 0,
                    "A_broker100_fail_count": 0,
                }
                for years in stage005.DURATIONS_YEARS
            ]
        )

        decision = stage005._decision(comparison, aggregate)

        self.assertFalse(decision["all_multicycle_gates_pass"])
        self.assertEqual("confirm_do_not_promote_after_multicycle", decision["decision"])


if __name__ == "__main__":
    unittest.main()
