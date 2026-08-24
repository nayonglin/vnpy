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
    import stage017_long_triple_volume_with_low_volume_discount_full_period_aclm as stage017
except ModuleNotFoundError:
    stage017 = None


class Stage017LongTripleVolumeWithLowVolumeDiscountRunnerTest(unittest.TestCase):
    def setUp(self) -> None:
        if stage017 is None:
            self.fail("Stage017 runner is not implemented")

    def test_identity_reuses_a_c_l_and_runs_only_m(self) -> None:
        self.assertEqual(["A", "C", "L", "M"], [arm["arm"] for arm in stage017.ARMS])
        self.assertEqual({"A", "C", "L"}, stage017.REUSED_ARMS)
        self.assertEqual({"M"}, stage017.NEW_RUN_ARMS)
        candidate = next(arm for arm in stage017.ARMS if arm["arm"] == "M")
        self.assertEqual(3.0, candidate["high_volume_ratio_threshold"])
        self.assertEqual(1.5, candidate["high_volume_multiplier"])
        self.assertEqual(0.5, candidate["low_volume_ratio_threshold"])
        self.assertEqual(0.5, candidate["low_volume_multiplier"])
        self.assertTrue(candidate["long_only"])

    def test_m_contract_has_strict_low_high_boundaries_and_short_bypass(self) -> None:
        common = {
            "entry_context": "flat_entry",
            "directional_30d_risk_boost_enabled": 1,
            "directional_30d_volume_confirmation_enabled": 1,
            "directional_30d_risk_adjust_long_only": 1,
            "directional_30d_volume_ratio_threshold": 3.0,
            "directional_30d_low_volume_discount_enabled": 1,
            "directional_30d_low_volume_ratio_threshold": 0.5,
            "directional_30d_low_volume_risk_multiplier": 0.5,
            "directional_30d_risk_nonconfirmation_multiplier": 1.0,
            "risk_amount_before_directional_30d_boost": 100.0,
        }
        diagnostics = pd.DataFrame(
            [
                {
                    **common,
                    "direction": "long",
                    "directional_30d_risk_boost_aligned": 1,
                    "directional_30d_recent_volume_sum": 3_001.0,
                    "directional_30d_prior_volume_sum": 1_000.0,
                    "directional_30d_risk_boost_applied": 1,
                    "directional_30d_low_volume_discount_applied": 0,
                    "directional_30d_risk_boost_multiplier": 1.5,
                    "directional_30d_risk_boost_reason": "direction_and_volume_confirmed",
                    "target_risk_amount": 150.0,
                },
                {
                    **common,
                    "direction": "long",
                    "directional_30d_risk_boost_aligned": 0,
                    "directional_30d_recent_volume_sum": 499.0,
                    "directional_30d_prior_volume_sum": 1_000.0,
                    "directional_30d_risk_boost_applied": 0,
                    "directional_30d_low_volume_discount_applied": 1,
                    "directional_30d_risk_boost_multiplier": 0.5,
                    "directional_30d_risk_boost_reason": "low_volume_discount",
                    "target_risk_amount": 50.0,
                },
                {
                    **common,
                    "direction": "long",
                    "directional_30d_risk_boost_aligned": 1,
                    "directional_30d_recent_volume_sum": 500.0,
                    "directional_30d_prior_volume_sum": 1_000.0,
                    "directional_30d_risk_boost_applied": 0,
                    "directional_30d_low_volume_discount_applied": 0,
                    "directional_30d_risk_boost_multiplier": 1.0,
                    "directional_30d_risk_boost_reason": "volume_not_expanding",
                    "target_risk_amount": 100.0,
                },
                {
                    **common,
                    "direction": "short",
                    "directional_30d_risk_boost_aligned": 0,
                    "directional_30d_recent_volume_sum": pd.NA,
                    "directional_30d_prior_volume_sum": pd.NA,
                    "directional_30d_risk_boost_applied": 0,
                    "directional_30d_low_volume_discount_applied": 0,
                    "directional_30d_risk_boost_multiplier": 1.0,
                    "directional_30d_risk_boost_reason": "direction_excluded",
                    "target_risk_amount": 100.0,
                },
            ]
        )

        summary = stage017._risk_split_contract_summary(diagnostics)
        total = summary[summary["group_type"].eq("total")].iloc[0]

        self.assertEqual(1, int(total["long_high_volume_count"]))
        self.assertEqual(1, int(total["long_low_volume_count"]))
        self.assertEqual(1, int(total["long_base_volume_count"]))
        self.assertEqual(1, int(total["short_bypass_count"]))
        self.assertEqual(1, int(total["threshold_contract_pass"]))
        self.assertEqual(1, int(total["risk_amount_contract_pass"]))

    def test_decision_requires_m_to_pass_official_and_rollover(self) -> None:
        comparisons = [name for name, _, _ in stage017.COMPARISONS]
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
                for name in comparisons
            ]
        )
        comparison.loc[comparison["comparison"].eq("C_vs_M"), "right_slippage"] = 106.0
        contract = pd.DataFrame(
            [
                {
                    "group_type": "total",
                    "group_value": "all",
                    "diagnostic_intent_count": 10,
                    "long_high_volume_count": 2,
                    "long_low_volume_count": 1,
                    "long_base_volume_count": 4,
                    "short_bypass_count": 3,
                    "threshold_contract_pass": 1,
                    "risk_amount_contract_pass": 1,
                }
            ]
        )

        decision = stage017._decision(comparison, contract)

        self.assertFalse(decision["escalate_to_multicycle"])
        self.assertEqual(
            "stop_long_triple_volume_with_low_volume_discount_after_full_period",
            decision["decision"],
        )


if __name__ == "__main__":
    unittest.main()
