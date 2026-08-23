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

try:
    import stage014_long_only_confirmation_only_full_period_achjk as stage014
except ModuleNotFoundError:
    stage014 = None


class Stage014LongOnlyConfirmationOnlyRunnerTest(unittest.TestCase):
    def setUp(self) -> None:
        if stage014 is None:
            self.fail("Stage014 runner is not implemented")

    def test_identity_reuses_four_arms_and_runs_only_k(self) -> None:
        self.assertEqual(["A", "C", "H", "J", "K"], [arm["arm"] for arm in stage014.ARMS])
        self.assertEqual({"A", "C", "H", "J"}, stage014.REUSED_ARMS)
        self.assertEqual({"K"}, stage014.NEW_RUN_ARMS)
        k = next(arm for arm in stage014.ARMS if arm["arm"] == "K")
        self.assertEqual(2.0, k["volume_ratio_threshold"])
        self.assertEqual(1.5, k["confirmation_multiplier"])
        self.assertEqual(1.0, k["nonconfirmation_multiplier"])
        self.assertTrue(k["long_only"])

    def test_k_contract_keeps_long_miss_and_short_bypass_at_one(self) -> None:
        diagnostics = pd.DataFrame(
            [
                {
                    "direction": "long",
                    "entry_context": "flat_entry",
                    "directional_30d_risk_boost_enabled": 1,
                    "directional_30d_volume_confirmation_enabled": 1,
                    "directional_30d_risk_adjust_long_only": 1,
                    "directional_30d_risk_boost_aligned": 1,
                    "directional_30d_volume_ratio_threshold": 2.0,
                    "directional_30d_recent_volume_sum": 2_001.0,
                    "directional_30d_prior_volume_sum": 1_000.0,
                    "directional_30d_risk_boost_applied": 1,
                    "directional_30d_risk_nonconfirmation_multiplier": 1.0,
                    "directional_30d_risk_boost_multiplier": 1.5,
                    "directional_30d_risk_boost_reason": "aligned_and_volume_confirmed",
                    "risk_amount_before_directional_30d_boost": 100.0,
                    "target_risk_amount": 150.0,
                },
                {
                    "direction": "long",
                    "entry_context": "rollover_reopen",
                    "directional_30d_risk_boost_enabled": 1,
                    "directional_30d_volume_confirmation_enabled": 1,
                    "directional_30d_risk_adjust_long_only": 1,
                    "directional_30d_risk_boost_aligned": 1,
                    "directional_30d_volume_ratio_threshold": 2.0,
                    "directional_30d_recent_volume_sum": 2_000.0,
                    "directional_30d_prior_volume_sum": 1_000.0,
                    "directional_30d_risk_boost_applied": 0,
                    "directional_30d_risk_nonconfirmation_multiplier": 1.0,
                    "directional_30d_risk_boost_multiplier": 1.0,
                    "directional_30d_risk_boost_reason": "volume_not_confirmed",
                    "risk_amount_before_directional_30d_boost": 200.0,
                    "target_risk_amount": 200.0,
                },
                {
                    "direction": "short",
                    "entry_context": "flat_entry",
                    "directional_30d_risk_boost_enabled": 1,
                    "directional_30d_volume_confirmation_enabled": 1,
                    "directional_30d_risk_adjust_long_only": 1,
                    "directional_30d_risk_boost_aligned": pd.NA,
                    "directional_30d_volume_ratio_threshold": 2.0,
                    "directional_30d_recent_volume_sum": pd.NA,
                    "directional_30d_prior_volume_sum": pd.NA,
                    "directional_30d_risk_boost_applied": 0,
                    "directional_30d_risk_nonconfirmation_multiplier": 1.0,
                    "directional_30d_risk_boost_multiplier": 1.0,
                    "directional_30d_risk_boost_reason": "direction_excluded",
                    "risk_amount_before_directional_30d_boost": 300.0,
                    "target_risk_amount": 300.0,
                },
            ]
        )

        summary = stage014._risk_split_contract_summary(diagnostics)
        total = summary[summary["group_type"].eq("total")].iloc[0]

        self.assertEqual(3, int(total["diagnostic_intent_count"]))
        self.assertEqual(1, int(total["long_confirmation_count"]))
        self.assertEqual(1, int(total["long_nonconfirmation_count"]))
        self.assertEqual(1, int(total["short_bypass_count"]))
        self.assertEqual(1, int(total["threshold_contract_pass"]))
        self.assertEqual(1, int(total["risk_amount_contract_pass"]))

    def test_decision_requires_k_to_pass_official_and_rollover(self) -> None:
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
                for name in [
                    "A_vs_C",
                    "A_vs_H",
                    "C_vs_H",
                    "A_vs_J",
                    "C_vs_J",
                    "H_vs_J",
                    "A_vs_K",
                    "C_vs_K",
                    "H_vs_K",
                    "J_vs_K",
                ]
            ]
        )
        comparison.loc[comparison["comparison"].eq("C_vs_K"), "right_slippage"] = 106.0
        contract = pd.DataFrame(
            [
                {
                    "group_type": "total",
                    "group_value": "all",
                    "diagnostic_intent_count": 10,
                    "long_confirmation_count": 2,
                    "long_nonconfirmation_count": 5,
                    "short_bypass_count": 3,
                    "threshold_contract_pass": 1,
                    "risk_amount_contract_pass": 1,
                }
            ]
        )

        decision = stage014._decision(comparison, contract)

        self.assertFalse(decision["escalate_to_multicycle"])
        self.assertEqual("stop_long_only_confirmation_only_after_full_period", decision["decision"])


if __name__ == "__main__":
    unittest.main()
