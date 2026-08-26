from __future__ import annotations

from pathlib import Path
import sys
import unittest

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = ROOT / "research" / "lines" / "futures_trend_rollover_shape_same_volume" / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage029_stage028_multicycle_abc as stage029


class Stage029Stage028MulticycleRunnerTest(unittest.TestCase):
    def test_fixed_matrix_has_43_windows_and_129_arm_windows(self) -> None:
        self.assertEqual(43, len(stage029.WINDOWS))
        self.assertEqual(["A", "B", "C"], [arm["arm"] for arm in stage029.ARMS])
        self.assertEqual(129, len(stage029.WINDOWS) * len(stage029.ARMS))
        counts = {
            years: sum(
                1
                for window in stage029.WINDOWS
                if window["duration_years"] == years and window["complete"]
            )
            for years in (1, 2, 3)
        }
        self.assertEqual({1: 16, 2: 14, 3: 12}, counts)

    def test_each_duration_has_january_and_june_starts(self) -> None:
        for years in (1, 2, 3):
            starts = {
                pd.Timestamp(window["start"]).month
                for window in stage029.WINDOWS
                if window["duration_years"] == years and window["complete"]
            }
            self.assertEqual({1, 6}, starts)

    def test_report_contract_has_exactly_five_charts(self) -> None:
        self.assertEqual(
            {"full_period", "1y", "2y", "3y", "aggregate"},
            set(stage029.CHART_FILES),
        )
        self.assertEqual(5, len(set(stage029.CHART_FILES.values())))

    def test_candidate_scope_is_only_five_session_delay(self) -> None:
        self.assertEqual(
            {"rollover_delay_trading_days": (None, 5)},
            stage029.s28.override_diff("B", "C"),
        )

    def test_failed_full_period_cannot_be_rescued_by_cycles(self) -> None:
        comparison_rows = []
        for name, left, right in stage029.COMPARISONS:
            comparison_rows.append(
                {
                    "comparison": name,
                    "window_group": "full_period",
                    "right_return_pct": 10.0,
                    "left_return_pct": 10.0,
                    "dd_worsening_pp": 0.0,
                    "delta_sharpe": 0.0,
                    "slippage_ratio": 1.0,
                    "right_survival_pass": 1,
                    "right_days_over_100pct": 0,
                    "left_days_over_100pct": 0,
                }
            )
        comparison = pd.DataFrame(comparison_rows)
        comparison.loc[comparison["comparison"].eq("A_vs_C"), "delta_sharpe"] = -0.03
        aggregate_rows = []
        for name, _, _ in stage029.COMPARISONS:
            for years in (1, 2, 3):
                for cohort, _month in stage029.COHORTS:
                    aggregate_rows.append(
                        {
                            "comparison": name,
                            "duration_years": years,
                            "start_cohort": cohort,
                            "return_win_rate_pct": 100.0,
                            "median_return_delta_pct": 1.0,
                            "dd_noninferior_2pp_rate_pct": 100.0,
                            "right_dd50_fail_count": 0,
                            "left_dd50_fail_count": 0,
                            "sharpe_noninferior_005_rate_pct": 100.0,
                            "slippage_ratio": 1.0,
                            "all_right_survival": 1,
                            "right_broker100_fail_count": 0,
                            "left_broker100_fail_count": 0,
                        }
                    )
        preflight = {
            "formal_identity": {"manifest_sha256": "x"},
            "database_sha256": "y",
            "runtime_contract_sha256": "z",
        }
        decision = stage029._decision(
            preflight, comparison, pd.DataFrame(aggregate_rows), 0, 126
        )
        self.assertTrue(decision["full_period_failure_is_binding"])
        self.assertFalse(decision["stage028_all_multicycle_gates_pass"])
        self.assertEqual(
            "confirm_stage028_not_promotable_after_multicycle",
            decision["decision"],
        )


if __name__ == "__main__":
    unittest.main()
