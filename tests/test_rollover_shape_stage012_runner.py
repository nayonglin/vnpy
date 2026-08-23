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

import stage012_asymmetric_double_volume_full_period_achi as stage012  # noqa: E402


class Stage012AsymmetricDoubleVolumeRunnerTest(unittest.TestCase):
    def test_identity_reuses_three_arms_and_runs_only_i(self) -> None:
        self.assertEqual(["A", "C", "H", "I"], [arm["arm"] for arm in stage012.ARMS])
        self.assertEqual({"A", "C", "H"}, stage012.REUSED_ARMS)
        self.assertEqual({"I"}, stage012.NEW_RUN_ARMS)
        i = next(arm for arm in stage012.ARMS if arm["arm"] == "I")
        self.assertEqual(2.0, i["volume_ratio_threshold"])
        self.assertEqual(1.5, i["confirmation_multiplier"])
        self.assertEqual(0.5, i["nonconfirmation_multiplier"])

    def test_i_contract_requires_exact_hit_and_nonconfirmation_risk(self) -> None:
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
                    "directional_30d_risk_nonconfirmation_multiplier": 0.5,
                    "directional_30d_risk_boost_multiplier": 1.5,
                    "risk_amount_before_directional_30d_boost": 100.0,
                    "target_risk_amount": 150.0,
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
                    "directional_30d_risk_nonconfirmation_multiplier": 0.5,
                    "directional_30d_risk_boost_multiplier": 0.5,
                    "risk_amount_before_directional_30d_boost": 200.0,
                    "target_risk_amount": 100.0,
                },
            ]
        )

        summary = stage012._risk_split_contract_summary(diagnostics)
        total = summary[summary["group_type"].eq("total")].iloc[0]

        self.assertEqual(2, int(total["diagnostic_intent_count"]))
        self.assertEqual(1, int(total["confirmation_count"]))
        self.assertEqual(1, int(total["nonconfirmation_count"]))
        self.assertEqual(1, int(total["threshold_contract_pass"]))
        self.assertEqual(1, int(total["risk_amount_contract_pass"]))

    def test_decision_requires_i_to_pass_official_and_rollover(self) -> None:
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
                for name in ["A_vs_C", "A_vs_H", "C_vs_H", "A_vs_I", "C_vs_I", "H_vs_I"]
            ]
        )
        comparison.loc[comparison["comparison"].eq("C_vs_I"), "right_slippage"] = 106.0
        contract = pd.DataFrame(
            [
                {
                    "group_type": "total",
                    "group_value": "all",
                    "diagnostic_intent_count": 10,
                    "confirmation_count": 2,
                    "nonconfirmation_count": 8,
                    "threshold_contract_pass": 1,
                    "risk_amount_contract_pass": 1,
                }
            ]
        )

        decision = stage012._decision(comparison, contract)

        self.assertFalse(decision["escalate_to_multicycle"])
        self.assertEqual("stop_asymmetric_double_volume_risk_after_full_period", decision["decision"])


if __name__ == "__main__":
    unittest.main()
