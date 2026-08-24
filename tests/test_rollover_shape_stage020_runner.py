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
    import stage020_n_long_atr_shock_filter_full_period_acnp as stage020
except ModuleNotFoundError:
    stage020 = None


class Stage020NLongAtrShockFilterRunnerTest(unittest.TestCase):
    def setUp(self) -> None:
        if stage020 is None:
            self.fail("Stage020 runner is not implemented")

    def test_identity_reuses_a_c_n_and_runs_only_p_from_symmetric_n(self) -> None:
        self.assertEqual(["A", "C", "N", "P"], [arm["arm"] for arm in stage020.ARMS])
        self.assertEqual({"A", "C", "N"}, stage020.REUSED_ARMS)
        self.assertEqual({"P"}, stage020.NEW_RUN_ARMS)
        candidate = next(arm for arm in stage020.ARMS if arm["arm"] == "P")
        self.assertEqual("N", candidate["base_arm"])
        self.assertFalse(candidate["risk_adjust_long_only"])
        self.assertEqual(5, candidate["atr_period"])
        self.assertEqual(1.0, candidate["atr_multiplier"])
        self.assertEqual(
            {"flat_entry", "reverse_entry", "rollover_reopen"},
            set(candidate["entry_contexts"]),
        )

    def test_p_runtime_overrides_preserve_symmetric_n_and_use_one_atr(self) -> None:
        overrides = stage020._p_overrides(
            candidate=True,
            volume_policy="shrink_to_allowed",
            history_mode="backwards_ratio_continuous",
        )

        self.assertTrue(overrides["enable_directional_30d_risk_boost"])
        self.assertFalse(overrides["directional_30d_risk_adjust_long_only"])
        self.assertEqual(3.0, overrides["directional_30d_volume_ratio_threshold"])
        self.assertEqual(1.5, overrides["directional_30d_risk_boost_multiplier"])
        self.assertEqual(0.5, overrides["directional_30d_low_volume_ratio_threshold"])
        self.assertEqual(0.5, overrides["directional_30d_low_volume_risk_multiplier"])
        self.assertTrue(overrides["enable_long_signal_atr_shock_filter"])
        self.assertEqual(5, overrides["long_signal_atr_shock_period"])
        self.assertEqual(1.0, overrides["long_signal_atr_shock_multiplier"])

    def test_filter_contract_uses_strict_one_atr_boundary_and_preserves_exclusions(self) -> None:
        common = {
            "long_signal_atr_shock_enabled": 1,
            "long_signal_atr_shock_period": 5,
            "long_signal_atr_shock_multiplier": 1.0,
            "long_signal_atr_shock_atr": 2.0,
        }
        rows = [
            {
                **common,
                "direction": "long",
                "entry_context": "flat_entry",
                "long_signal_atr_shock_drop": 2.1,
                "long_signal_atr_shock_threshold": 2.0,
                "long_signal_atr_shock_blocked": 1,
                "long_signal_atr_shock_reason": "drop_strictly_above_threshold",
                "long_signal_atr_shock_selected_volume_before": 10,
                "long_signal_atr_shock_selected_volume_after": 0,
            },
            {
                **common,
                "direction": "long",
                "entry_context": "reverse_entry",
                "long_signal_atr_shock_drop": 2.0,
                "long_signal_atr_shock_threshold": 2.0,
                "long_signal_atr_shock_blocked": 0,
                "long_signal_atr_shock_reason": "drop_not_above_threshold",
                "long_signal_atr_shock_selected_volume_before": 8,
                "long_signal_atr_shock_selected_volume_after": 8,
            },
            {
                **common,
                "direction": "short",
                "entry_context": "flat_entry",
                "long_signal_atr_shock_drop": 3.0,
                "long_signal_atr_shock_threshold": 2.0,
                "long_signal_atr_shock_blocked": 0,
                "long_signal_atr_shock_reason": "direction_excluded",
                "long_signal_atr_shock_selected_volume_before": 7,
                "long_signal_atr_shock_selected_volume_after": 7,
            },
            {
                **common,
                "direction": "long",
                "entry_context": "regular_add",
                "long_signal_atr_shock_drop": 3.0,
                "long_signal_atr_shock_threshold": 2.0,
                "long_signal_atr_shock_blocked": 0,
                "long_signal_atr_shock_reason": "entry_context_excluded",
                "long_signal_atr_shock_selected_volume_before": 6,
                "long_signal_atr_shock_selected_volume_after": 6,
            },
        ]

        summary = stage020._atr_filter_contract_summary(pd.DataFrame(rows))
        total = summary[summary["group_type"].eq("total")].iloc[0]

        self.assertEqual(4, int(total["diagnostic_count"]))
        self.assertEqual(1, int(total["blocked_count"]))
        self.assertEqual(1, int(total["flat_entry_blocked_count"]))
        self.assertEqual(1, int(total["configuration_contract_pass"]))
        self.assertEqual(1, int(total["blocking_contract_pass"]))

    def test_decision_requires_p_to_pass_official_and_rollover(self) -> None:
        comparisons = [name for name, _, _ in stage020.COMPARISONS]
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
        comparison.loc[comparison["comparison"].eq("C_vs_P"), "right_return_pct"] = 9.0
        contract = pd.DataFrame(
            [
                {
                    "group_type": "total",
                    "group_value": "all",
                    "diagnostic_count": 10,
                    "blocked_count": 2,
                    "flat_entry_blocked_count": 2,
                    "reverse_entry_blocked_count": 0,
                    "rollover_reopen_blocked_count": 0,
                    "configuration_contract_pass": 1,
                    "blocking_contract_pass": 1,
                }
            ]
        )

        decision = stage020._decision(comparison, contract)

        self.assertFalse(decision["escalate_to_multicycle"])
        self.assertEqual("stop_n_long_atr_shock_filter_after_full_period", decision["decision"])


if __name__ == "__main__":
    unittest.main()
