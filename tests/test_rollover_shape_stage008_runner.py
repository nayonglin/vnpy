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

import stage008_directional_volume_confirmed_multicycle_acdf as stage008  # noqa: E402


def _window_summary() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for window in stage008.WINDOWS:
        for arm in stage008.ARMS:
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


class Stage008DirectionalVolumeConfirmedMulticycleRunnerTest(unittest.TestCase):
    def test_frozen_windows_and_four_arm_identity(self) -> None:
        self.assertEqual(43, len(stage008.WINDOWS))
        self.assertEqual(["A", "C", "D", "F"], [arm["arm"] for arm in stage008.ARMS])
        self.assertEqual(172, len(stage008.WINDOWS) * len(stage008.ARMS))
        f = next(arm for arm in stage008.ARMS if arm["arm"] == "F")
        self.assertTrue(f["risk_boost"])
        self.assertTrue(f["volume_confirmation"])

    def test_pairwise_outputs_cover_all_six_comparisons_and_three_cohorts(self) -> None:
        summary = _window_summary()
        comparison = stage008._comparison(summary)
        aggregate = stage008._aggregate(comparison)

        self.assertEqual(258, len(comparison))
        self.assertEqual(54, len(aggregate))
        self.assertEqual(
            {"A_vs_C", "A_vs_D", "C_vs_D", "A_vs_F", "C_vs_F", "D_vs_F"},
            set(comparison["comparison"]),
        )
        self.assertEqual({"combined", "january", "june"}, set(aggregate["start_cohort"]))

    def test_volume_contract_requires_selective_applied_rows_and_exact_risk(self) -> None:
        diagnostics = pd.DataFrame(
            [
                {
                    "direction": "long",
                    "entry_context": "flat_entry",
                    "directional_30d_risk_boost_enabled": 1,
                    "directional_30d_volume_confirmation_enabled": 1,
                    "directional_30d_risk_boost_aligned": 1,
                    "directional_30d_volume_expanding": 1,
                    "directional_30d_risk_boost_applied": 1,
                    "directional_30d_risk_boost_multiplier": 1.2,
                    "risk_amount_before_directional_30d_boost": 100.0,
                    "target_risk_amount": 120.0,
                },
                {
                    "direction": "long",
                    "entry_context": "rollover_reopen",
                    "directional_30d_risk_boost_enabled": 1,
                    "directional_30d_volume_confirmation_enabled": 1,
                    "directional_30d_risk_boost_aligned": 1,
                    "directional_30d_volume_expanding": 0,
                    "directional_30d_risk_boost_applied": 0,
                    "directional_30d_risk_boost_multiplier": 1.0,
                    "risk_amount_before_directional_30d_boost": 200.0,
                    "target_risk_amount": 200.0,
                },
            ]
        )

        summary = stage008._volume_contract_summary(diagnostics)
        total = summary[summary["group_type"].eq("total")].iloc[0]

        self.assertEqual(2, int(total["diagnostic_intent_count"]))
        self.assertEqual(2, int(total["price_aligned_count"]))
        self.assertEqual(1, int(total["boost_applied_count"]))
        self.assertEqual(1, int(total["boost_suppressed_by_volume_count"]))
        self.assertEqual(1, int(total["risk_amount_contract_pass"]))

    def test_decision_fails_closed_when_one_f_vs_c_cycle_gate_fails(self) -> None:
        comparison = stage008._comparison(_window_summary())
        aggregate = stage008._aggregate(comparison)
        target = (
            aggregate["comparison"].eq("C_vs_F")
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
                    "boost_applied_count": 4,
                    "boost_suppressed_by_volume_count": 4,
                    "risk_amount_contract_pass": 1,
                }
            ]
        )

        decision = stage008._decision(comparison, aggregate, contract)

        self.assertFalse(decision["volume_confirmed_candidate_all_gates_pass"])
        self.assertEqual("volume_confirmed_boost_not_promotable", decision["decision"])


if __name__ == "__main__":
    unittest.main()
