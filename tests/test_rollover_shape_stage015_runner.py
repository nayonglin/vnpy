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
    import stage015_long_only_triple_volume_full_period_achkl as stage015
except ModuleNotFoundError:
    stage015 = None


class Stage015LongOnlyTripleVolumeRunnerTest(unittest.TestCase):
    def setUp(self) -> None:
        if stage015 is None:
            self.fail("Stage015 runner is not implemented")

    def test_identity_reuses_four_arms_and_runs_only_l(self) -> None:
        self.assertEqual(["A", "C", "H", "K", "L"], [arm["arm"] for arm in stage015.ARMS])
        self.assertEqual({"A", "C", "H", "K"}, stage015.REUSED_ARMS)
        self.assertEqual({"L"}, stage015.NEW_RUN_ARMS)
        candidate = next(arm for arm in stage015.ARMS if arm["arm"] == "L")
        self.assertEqual(3.0, candidate["volume_ratio_threshold"])
        self.assertEqual(1.5, candidate["confirmation_multiplier"])
        self.assertEqual(1.0, candidate["nonconfirmation_multiplier"])
        self.assertTrue(candidate["long_only"])

    def test_l_contract_uses_strict_three_times_and_bypasses_shorts(self) -> None:
        diagnostics = pd.DataFrame(
            [
                {
                    "direction": "long",
                    "entry_context": "flat_entry",
                    "directional_30d_risk_boost_enabled": 1,
                    "directional_30d_volume_confirmation_enabled": 1,
                    "directional_30d_risk_adjust_long_only": 1,
                    "directional_30d_risk_boost_aligned": 1,
                    "directional_30d_volume_ratio_threshold": 3.0,
                    "directional_30d_recent_volume_sum": 3_001.0,
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
                    "directional_30d_volume_ratio_threshold": 3.0,
                    "directional_30d_recent_volume_sum": 3_000.0,
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
                    "directional_30d_risk_boost_aligned": 0,
                    "directional_30d_volume_ratio_threshold": 3.0,
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

        summary = stage015._risk_split_contract_summary(diagnostics)
        total = summary[summary["group_type"].eq("total")].iloc[0]

        self.assertEqual(1, int(total["long_confirmation_count"]))
        self.assertEqual(1, int(total["long_nonconfirmation_count"]))
        self.assertEqual(1, int(total["short_bypass_count"]))
        self.assertEqual(1, int(total["threshold_contract_pass"]))
        self.assertEqual(1, int(total["risk_amount_contract_pass"]))

    def test_decision_requires_l_to_pass_official_and_rollover(self) -> None:
        comparisons = [name for name, _, _ in stage015.COMPARISONS]
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
        comparison.loc[comparison["comparison"].eq("C_vs_L"), "right_slippage"] = 106.0
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

        decision = stage015._decision(comparison, contract)

        self.assertFalse(decision["escalate_to_multicycle"])
        self.assertEqual("stop_long_only_triple_volume_after_full_period", decision["decision"])
        self.assertEqual(
            "c122cc4e53bd93b1ff56d2477bdf4e2dc09aa1e5",
            decision["run_provenance"]["reused_source_commit"],
        )


if __name__ == "__main__":
    unittest.main()
