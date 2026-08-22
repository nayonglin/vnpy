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

import stage007_directional_boost_multicycle_acd as stage007


def _window_summary() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for window in stage007.WINDOWS:
        for arm in stage007.ARMS:
            rows.append(
                {
                    "window_id": window["window_id"],
                    "window_group": window["window_group"],
                    "duration_years": window["duration_years"],
                    "requested_start": str(pd.Timestamp(window["start"]).date()),
                    "requested_end": str(pd.Timestamp(window["end"]).date()),
                    "complete_window": int(window["complete"]),
                    "terminal_near_complete": int(window["terminal_near_complete"]),
                    "promotion_arm": arm["arm"],
                    "start_month_num": int(pd.Timestamp(window["start"]).month),
                    "end_equity": 100.0,
                    "total_return_pct": 10.0,
                    "max_dd_pct": -5.0,
                    "sharpe": 1.0,
                    "total_slippage": 10.0,
                    "total_trade_count": 5,
                    "nonzero_daily_win_rate_pct": 50.0,
                    "account_survival_pass": 1,
                    "broker10_100_pass": 1,
                    "max_broker10_margin_to_equity_pct": 80.0,
                    "days_over_100pct": 0,
                }
            )
    return pd.DataFrame(rows)


class Stage007DirectionalBoostMulticycleRunnerTest(unittest.TestCase):
    def test_frozen_windows_and_three_arm_identity(self) -> None:
        windows = pd.DataFrame(stage007.WINDOWS)

        self.assertEqual(43, len(windows))
        self.assertEqual(["A", "C", "D"], [arm["arm"] for arm in stage007.ARMS])
        self.assertEqual(129, len(stage007.WINDOWS) * len(stage007.ARMS))
        for years, january_count, june_count in [(1, 8, 7), (2, 7, 6), (3, 6, 5)]:
            complete = windows[
                windows["duration_years"].eq(years) & windows["complete"].eq(True)
            ]
            self.assertEqual(january_count, int(complete["start"].map(pd.Timestamp).dt.month.eq(1).sum()))
            self.assertEqual(june_count, int(complete["start"].map(pd.Timestamp).dt.month.eq(6).sum()))

    def test_pairwise_aggregate_has_combined_january_and_june_rows(self) -> None:
        summary = _window_summary()
        comparison = stage007._comparison(summary)
        aggregate = stage007._aggregate(comparison)

        self.assertEqual(129, len(comparison))
        self.assertEqual(27, len(aggregate))
        self.assertEqual(
            {"combined", "january", "june"},
            set(aggregate["start_cohort"]),
        )
        self.assertEqual(
            {"A_vs_C", "A_vs_D", "C_vs_D"},
            set(aggregate["comparison"]),
        )

    def test_decision_fails_closed_when_one_d_cohort_gate_fails(self) -> None:
        summary = _window_summary()
        comparison = stage007._comparison(summary)
        aggregate = stage007._aggregate(comparison)
        target = (
            aggregate["comparison"].eq("C_vs_D")
            & aggregate["duration_years"].eq(2)
            & aggregate["start_cohort"].eq("june")
        )
        aggregate.loc[target, "slippage_ratio"] = 1.06

        decision = stage007._decision(comparison, aggregate)

        self.assertFalse(decision["directional_boost_all_multicycle_gates_pass"])
        self.assertEqual(
            "confirm_directional_boost_not_promotable_after_multicycle",
            decision["decision"],
        )
        failed = [
            row
            for row in decision["cycle_gates"]
            if row["comparison"] == "C_vs_D"
            and row["duration_years"] == 2
            and row["start_cohort"] == "june"
        ]
        self.assertEqual(1, len(failed))
        self.assertFalse(failed[0]["gates"]["slippage_ratio_le_105pct"])

    def test_output_validation_rejects_nonfinite_or_missing_arm_data(self) -> None:
        summary = _window_summary()
        curves = summary[["window_id", "promotion_arm"]].copy()
        curves["account_equity"] = 100.0

        summary.loc[0, "sharpe"] = float("inf")
        with self.assertRaisesRegex(RuntimeError, "stage007_critical_metric_missing"):
            stage007._validate_outputs(summary, curves)

        summary.loc[0, "sharpe"] = 1.0
        with self.assertRaisesRegex(RuntimeError, "stage007_window_arm_identity_mismatch"):
            stage007._validate_outputs(summary.iloc[1:].copy(), curves)


if __name__ == "__main__":
    unittest.main()
