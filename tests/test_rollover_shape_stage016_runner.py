from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


TOOLS_DIR = (
    Path(__file__).resolve().parents[1]
    / "research"
    / "lines"
    / "futures_trend_rollover_shape_same_volume"
    / "tools"
)
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

try:
    import stage016_long_only_triple_volume_multicycle_ackl as stage016
except ModuleNotFoundError:
    stage016 = None


class Stage016LongOnlyTripleVolumeMulticycleRunnerTest(unittest.TestCase):
    def setUp(self) -> None:
        if stage016 is None:
            self.fail("Stage016 multicycle runner is not implemented")

    def test_matrix_reuses_ac_and_runs_k_l_for_all_43_independent_windows(self) -> None:
        self.assertEqual(43, len(stage016.WINDOWS))
        self.assertEqual(["A", "C", "K", "L"], [arm["arm"] for arm in stage016.ARMS])
        self.assertEqual({"A", "C"}, stage016.REUSED_ARMS)
        self.assertEqual({"K", "L"}, stage016.NEW_RUN_ARMS)
        self.assertEqual(86, len(stage016.WINDOWS) * len(stage016.NEW_RUN_ARMS))

        k = next(arm for arm in stage016.ARMS if arm["arm"] == "K")
        l = next(arm for arm in stage016.ARMS if arm["arm"] == "L")
        self.assertEqual((2.0, 1.5, 1.0, True), (
            k["volume_ratio_threshold"], k["confirmation_multiplier"],
            k["nonconfirmation_multiplier"], k["long_only"],
        ))
        self.assertEqual((3.0, 1.5, 1.0, True), (
            l["volume_ratio_threshold"], l["confirmation_multiplier"],
            l["nonconfirmation_multiplier"], l["long_only"],
        ))

    def test_each_duration_has_january_and_june_starts(self) -> None:
        finite = [window for window in stage016.WINDOWS if window["duration_years"] in {1, 2, 3}]
        for years in (1, 2, 3):
            starts = {
                pd.Timestamp(window["start"]).month
                for window in finite
                if window["duration_years"] == years
            }
            self.assertEqual({1, 6}, starts)

    def test_fixed_report_contains_exactly_five_chart_slots(self) -> None:
        self.assertEqual(
            {"full_period", "1y", "2y", "3y", "aggregate"},
            set(stage016.CHART_FILES),
        )
        self.assertEqual(5, len(set(stage016.CHART_FILES.values())))

    def test_full_identity_accepts_one_csv_ulp_but_rejects_real_drift(self) -> None:
        self.assertTrue(
            stage016._csv_equity_values_match(
                np.array([14_447_993.800000003]),
                np.array([14_447_993.800000004]),
            )
        )
        self.assertFalse(
            stage016._csv_equity_values_match(
                np.array([14_447_993.800001]),
                np.array([14_447_993.800000]),
            )
        )

    def test_failed_full_period_gate_cannot_be_rescued_by_multicycle(self) -> None:
        comparisons = [name for name, _, _ in stage016.COMPARISONS]
        full_rows = []
        for name in comparisons:
            full_rows.append(
                {
                    "comparison": name,
                    "window_group": "full_period",
                    "right_return_pct": 10.0,
                    "left_return_pct": 10.0,
                    "dd_worsening_pp": 0.0,
                    "delta_sharpe": 0.0,
                    "right_slippage": 100.0,
                    "left_slippage": 100.0,
                    "right_survival_pass": 1,
                    "right_broker10_peak_pct": 80.0,
                    "left_broker10_peak_pct": 80.0,
                    "right_days_over_100pct": 0,
                    "left_days_over_100pct": 0,
                }
            )
        comparison = pd.DataFrame(full_rows)
        comparison.loc[comparison["comparison"].eq("C_vs_L"), "right_slippage"] = 106.0

        aggregate_rows = []
        for name in comparisons:
            for years in (1, 2, 3):
                for cohort in ("combined", "january", "june"):
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
        contract = pd.DataFrame(
            [
                {
                    "group_type": "total",
                    "long_confirmation_count": 2,
                    "long_nonconfirmation_count": 5,
                    "short_bypass_count": 3,
                    "threshold_contract_pass": 1,
                    "risk_amount_contract_pass": 1,
                }
            ]
        )

        decision = stage016._decision(comparison, pd.DataFrame(aggregate_rows), contract)

        self.assertFalse(decision["long_only_triple_volume_all_gates_pass"])
        self.assertTrue(decision["full_period_failure_is_binding"])
        self.assertEqual(
            "confirm_long_only_triple_volume_not_promotable_after_multicycle",
            decision["decision"],
        )


if __name__ == "__main__":
    unittest.main()
