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

import stage011_double_volume_multicycle_acfh as stage011  # noqa: E402


def _window_summary() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for window in stage011.WINDOWS:
        for arm in stage011.ARMS:
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


class Stage011DoubleVolumeMulticycleRunnerTest(unittest.TestCase):
    def test_frozen_windows_four_arms_and_reuse_identity(self) -> None:
        self.assertEqual(43, len(stage011.WINDOWS))
        self.assertEqual(["A", "C", "F", "H"], [arm["arm"] for arm in stage011.ARMS])
        self.assertEqual(172, len(stage011.WINDOWS) * len(stage011.ARMS))
        self.assertEqual({"A", "C", "F"}, stage011.REUSED_ARMS)
        self.assertEqual({"H"}, stage011.NEW_RUN_ARMS)
        h = next(arm for arm in stage011.ARMS if arm["arm"] == "H")
        self.assertEqual(2.0, h["volume_ratio_threshold"])

    def test_pairwise_outputs_cover_six_comparisons_and_three_cohorts(self) -> None:
        comparison = stage011._comparison(_window_summary())
        aggregate = stage011._aggregate(comparison)

        self.assertEqual(258, len(comparison))
        self.assertEqual(54, len(aggregate))
        self.assertEqual(
            {"A_vs_C", "A_vs_F", "C_vs_F", "A_vs_H", "C_vs_H", "F_vs_H"},
            set(comparison["comparison"]),
        )
        self.assertEqual({"combined", "january", "june"}, set(aggregate["start_cohort"]))

    def test_machine_epsilon_return_delta_is_counted_as_tie(self) -> None:
        summary = _window_summary()
        target = (
            summary["window_id"].eq("roll_1y_2018_01")
            & summary["promotion_arm"].eq("H")
        )
        summary.loc[target, "total_return_pct"] -= 1e-12

        comparison = stage011._comparison(summary)
        row = comparison[
            comparison["window_id"].eq("roll_1y_2018_01")
            & comparison["comparison"].eq("C_vs_H")
        ].iloc[0]

        self.assertEqual(0.0, float(row["delta_return_pct"]))
        self.assertEqual(1, int(row["return_win"]))

    def test_decision_stays_not_promotable_when_h_cycle_gate_fails(self) -> None:
        comparison = stage011._comparison(_window_summary())
        aggregate = stage011._aggregate(comparison)
        target = (
            aggregate["comparison"].eq("C_vs_H")
            & aggregate["duration_years"].eq(2)
            & aggregate["start_cohort"].eq("june")
        )
        aggregate.loc[target, "slippage_ratio"] = 1.06
        contract = pd.DataFrame(
            [
                {
                    "group_type": "total",
                    "group_value": "all",
                    "diagnostic_intent_count": 10,
                    "price_aligned_count": 8,
                    "boost_applied_count": 2,
                    "boost_suppressed_by_volume_count": 6,
                    "threshold_contract_pass": 1,
                    "risk_amount_contract_pass": 1,
                }
            ]
        )

        decision = stage011._decision(comparison, aggregate, contract)

        self.assertFalse(decision["double_volume_all_multicycle_gates_pass"])
        self.assertEqual("confirm_double_volume_not_promotable_after_multicycle", decision["decision"])


if __name__ == "__main__":
    unittest.main()
