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
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage022_q_symmetric_atr_shock_filter_multicycle_acpq as stage022


class Stage022QMulticycleRunnerTest(unittest.TestCase):
    def test_fixed_window_and_arm_contract(self) -> None:
        self.assertEqual(43, len(stage022.WINDOWS))
        self.assertEqual(["A", "C", "P", "Q"], [arm["arm"] for arm in stage022.ARMS])
        self.assertEqual({"A", "C"}, stage022.REUSED_ARMS)
        self.assertEqual({"P", "Q"}, stage022.NEW_RUN_ARMS)
        self.assertEqual(86, len(stage022.WINDOWS) * len(stage022.NEW_RUN_ARMS))
        self.assertEqual(172, len(stage022.WINDOWS) * len(stage022.ARMS))
        self.assertEqual(5, len(stage022.CHART_FILES))

    def test_each_duration_has_january_and_june_starts(self) -> None:
        finite = pd.DataFrame(
            [window for window in stage022.WINDOWS if int(window["duration_years"]) in {1, 2, 3}]
        )
        for years in (1, 2, 3):
            months = set(pd.to_datetime(finite[finite["duration_years"].eq(years)]["start"]).dt.month)
            self.assertEqual({1, 6}, months)

    def test_p_and_q_runtime_contracts_differ_only_by_short_filter(self) -> None:
        original = stage022.s1._overrides
        common = {
            "candidate": True,
            "volume_policy": "shrink_to_allowed",
            "history_mode": "backwards_ratio_continuous",
        }
        p = stage022._candidate_overrides("P", original, **common)
        q = stage022._candidate_overrides("Q", original, **common)
        self.assertTrue(p["enable_long_signal_atr_shock_filter"])
        self.assertFalse(p.get("enable_short_signal_atr_shock_filter", False))
        self.assertTrue(q["enable_long_signal_atr_shock_filter"])
        self.assertTrue(q["enable_short_signal_atr_shock_filter"])
        for key in (
            "directional_30d_risk_adjust_long_only",
            "directional_30d_volume_ratio_threshold",
            "directional_30d_risk_boost_multiplier",
            "directional_30d_low_volume_ratio_threshold",
            "directional_30d_low_volume_risk_multiplier",
            "long_signal_atr_shock_period",
            "long_signal_atr_shock_multiplier",
        ):
            self.assertEqual(p[key], q[key])

    def test_full_period_failure_remains_binding(self) -> None:
        comparison_rows = []
        for name, _, _ in stage022.COMPARISONS:
            comparison_rows.append(
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
        comparison = pd.DataFrame(comparison_rows)
        comparison.loc[comparison["comparison"].eq("A_vs_Q"), "right_broker10_peak_pct"] = 99.0
        aggregate = pd.DataFrame(
            [
                {
                    "comparison": name,
                    "duration_years": years,
                    "start_cohort": cohort,
                    "return_win_rate_pct": 100.0,
                    "median_return_delta_pct": 1.0,
                    "dd_noninferior_2pp_rate_pct": 100.0,
                    "left_dd50_fail_count": 0,
                    "right_dd50_fail_count": 0,
                    "sharpe_noninferior_005_rate_pct": 100.0,
                    "slippage_ratio": 1.0,
                    "all_right_survival": 1,
                    "left_broker100_fail_count": 0,
                    "right_broker100_fail_count": 0,
                }
                for name, _, _ in stage022.COMPARISONS
                for years in (1, 2, 3)
                for cohort, _ in stage022.COHORTS
            ]
        )
        contract = pd.DataFrame(
            [{
                "group_type": "total",
                "configuration_contract_pass": 1,
                "blocking_contract_pass": 1,
                "long_blocked_count": 1,
                "short_blocked_count": 1,
            }]
        )
        decision = stage022._decision(comparison, aggregate, contract)
        self.assertTrue(decision["full_period_failure_is_binding"])
        self.assertFalse(decision["q_all_multicycle_gates_pass"])
        self.assertEqual("confirm_q_not_promotable_after_multicycle", decision["decision"])


if __name__ == "__main__":
    unittest.main()
