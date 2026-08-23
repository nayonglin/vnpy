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

import stage010_directional_double_volume_full_period_acfh as stage010  # noqa: E402


class Stage010DirectionalDoubleVolumeRunnerTest(unittest.TestCase):
    def test_four_arm_identity_and_frozen_thresholds(self) -> None:
        self.assertEqual(["A", "C", "F", "H"], [arm["arm"] for arm in stage010.ARMS])
        f = next(arm for arm in stage010.ARMS if arm["arm"] == "F")
        h = next(arm for arm in stage010.ARMS if arm["arm"] == "H")
        self.assertEqual(1.0, f["volume_ratio_threshold"])
        self.assertEqual(2.0, h["volume_ratio_threshold"])
        self.assertTrue(h["risk_boost"])
        self.assertTrue(h["volume_confirmation"])

    def test_h_contract_requires_strict_double_volume_and_exact_risk(self) -> None:
        diagnostics = pd.DataFrame(
            [
                {
                    "direction": "long",
                    "entry_context": "flat_entry",
                    "directional_30d_risk_boost_enabled": 1,
                    "directional_30d_volume_confirmation_enabled": 1,
                    "directional_30d_risk_boost_aligned": 1,
                    "directional_30d_volume_ratio_threshold": 2.0,
                    "directional_30d_recent_volume_sum": 2_001.0,
                    "directional_30d_prior_volume_sum": 1_000.0,
                    "directional_30d_risk_boost_applied": 1,
                    "directional_30d_risk_boost_multiplier": 1.2,
                    "risk_amount_before_directional_30d_boost": 100.0,
                    "target_risk_amount": 120.0,
                },
                {
                    "direction": "short",
                    "entry_context": "rollover_reopen",
                    "directional_30d_risk_boost_enabled": 1,
                    "directional_30d_volume_confirmation_enabled": 1,
                    "directional_30d_risk_boost_aligned": 1,
                    "directional_30d_volume_ratio_threshold": 2.0,
                    "directional_30d_recent_volume_sum": 2_000.0,
                    "directional_30d_prior_volume_sum": 1_000.0,
                    "directional_30d_risk_boost_applied": 0,
                    "directional_30d_risk_boost_multiplier": 1.0,
                    "risk_amount_before_directional_30d_boost": 200.0,
                    "target_risk_amount": 200.0,
                },
            ]
        )

        summary = stage010._volume_contract_summary(diagnostics)
        total = summary[summary["group_type"].eq("total")].iloc[0]

        self.assertEqual(2, int(total["diagnostic_intent_count"]))
        self.assertEqual(1, int(total["boost_applied_count"]))
        self.assertEqual(1, int(total["boost_suppressed_by_volume_count"]))
        self.assertEqual(1, int(total["threshold_contract_pass"]))
        self.assertEqual(1, int(total["risk_amount_contract_pass"]))

    def test_decision_requires_both_official_and_rollover_comparisons(self) -> None:
        comparison = pd.DataFrame(
            [
                {
                    "comparison": name,
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
                for name in ["A_vs_C", "A_vs_F", "C_vs_F", "A_vs_H", "C_vs_H", "F_vs_H"]
            ]
        )
        comparison.loc[comparison["comparison"].eq("C_vs_H"), "right_slippage"] = 106.0
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

        decision = stage010._decision(comparison, contract)

        self.assertFalse(decision["escalate_to_multicycle"])
        self.assertEqual("stop_double_volume_boost_after_full_period", decision["decision"])


if __name__ == "__main__":
    unittest.main()
