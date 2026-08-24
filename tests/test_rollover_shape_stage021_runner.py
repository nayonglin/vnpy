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
    import stage021_p_symmetric_atr_shock_filter_full_period_acpq as stage021
except ModuleNotFoundError:
    stage021 = None


class Stage021PSymmetricAtrShockFilterRunnerTest(unittest.TestCase):
    def setUp(self) -> None:
        if stage021 is None:
            self.fail("Stage021 runner is not implemented")

    def test_identity_reuses_a_c_p_and_runs_only_q_with_both_filters(self) -> None:
        self.assertEqual(["A", "C", "P", "Q"], [arm["arm"] for arm in stage021.ARMS])
        self.assertEqual({"A", "C", "P"}, stage021.REUSED_ARMS)
        self.assertEqual({"Q"}, stage021.NEW_RUN_ARMS)
        candidate = next(arm for arm in stage021.ARMS if arm["arm"] == "Q")
        self.assertEqual("P", candidate["base_arm"])
        self.assertFalse(candidate["risk_adjust_long_only"])
        self.assertEqual({"long", "short"}, set(candidate["atr_filter_directions"]))
        self.assertEqual(1.0, candidate["atr_multiplier"])

    def test_q_runtime_overrides_preserve_n_scaling_and_enable_both_filters(self) -> None:
        overrides = stage021._q_overrides(
            candidate=True,
            volume_policy="shrink_to_allowed",
            history_mode="backwards_ratio_continuous",
        )

        self.assertFalse(overrides["directional_30d_risk_adjust_long_only"])
        self.assertEqual(3.0, overrides["directional_30d_volume_ratio_threshold"])
        self.assertEqual(1.5, overrides["directional_30d_risk_boost_multiplier"])
        self.assertEqual(0.5, overrides["directional_30d_low_volume_ratio_threshold"])
        self.assertEqual(0.5, overrides["directional_30d_low_volume_risk_multiplier"])
        self.assertTrue(overrides["enable_long_signal_atr_shock_filter"])
        self.assertTrue(overrides["enable_short_signal_atr_shock_filter"])
        self.assertEqual(1.0, overrides["long_signal_atr_shock_multiplier"])

    def test_filter_contract_blocks_strict_adverse_move_in_both_directions(self) -> None:
        common = {
            "long_signal_atr_shock_enabled": 1,
            "short_signal_atr_shock_enabled": 1,
            "long_signal_atr_shock_period": 5,
            "long_signal_atr_shock_multiplier": 1.0,
            "long_signal_atr_shock_atr": 2.0,
            "long_signal_atr_shock_threshold": 2.0,
        }
        rows = [
            {
                **common,
                "direction": "long", "entry_context": "flat_entry",
                "signal_atr_shock_adverse_move": 2.1,
                "signal_atr_shock_move_kind": "signal_day_drop",
                "long_signal_atr_shock_blocked": 1,
                "long_signal_atr_shock_reason": "drop_strictly_above_threshold",
                "long_signal_atr_shock_selected_volume_before": 10,
                "long_signal_atr_shock_selected_volume_after": 0,
            },
            {
                **common,
                "direction": "short", "entry_context": "rollover_reopen",
                "signal_atr_shock_adverse_move": 2.2,
                "signal_atr_shock_move_kind": "signal_day_rise",
                "long_signal_atr_shock_blocked": 1,
                "long_signal_atr_shock_reason": "rise_strictly_above_threshold",
                "long_signal_atr_shock_selected_volume_before": 8,
                "long_signal_atr_shock_selected_volume_after": 0,
            },
            {
                **common,
                "direction": "short", "entry_context": "flat_entry",
                "signal_atr_shock_adverse_move": 2.0,
                "signal_atr_shock_move_kind": "signal_day_rise",
                "long_signal_atr_shock_blocked": 0,
                "long_signal_atr_shock_reason": "rise_not_above_threshold",
                "long_signal_atr_shock_selected_volume_before": 7,
                "long_signal_atr_shock_selected_volume_after": 7,
            },
            {
                **common,
                "direction": "long", "entry_context": "regular_add",
                "signal_atr_shock_adverse_move": 3.0,
                "signal_atr_shock_move_kind": "signal_day_drop",
                "long_signal_atr_shock_blocked": 0,
                "long_signal_atr_shock_reason": "entry_context_excluded",
                "long_signal_atr_shock_selected_volume_before": 6,
                "long_signal_atr_shock_selected_volume_after": 6,
            },
        ]

        summary = stage021._atr_filter_contract_summary(pd.DataFrame(rows))
        total = summary[summary["group_type"].eq("total")].iloc[0]

        self.assertEqual(2, int(total["blocked_count"]))
        self.assertEqual(1, int(total["long_blocked_count"]))
        self.assertEqual(1, int(total["short_blocked_count"]))
        self.assertEqual(1, int(total["configuration_contract_pass"]))
        self.assertEqual(1, int(total["blocking_contract_pass"]))

    def test_decision_requires_q_to_pass_official_and_rollover(self) -> None:
        comparison = pd.DataFrame(
            [
                {
                    "comparison": name,
                    "right_return_pct": 10.0, "left_return_pct": 10.0,
                    "dd_worsening_pp": 0.0, "delta_sharpe": 0.0,
                    "right_slippage": 100.0, "left_slippage": 100.0,
                    "right_survival_pass": 1,
                    "right_broker10_peak_pct": 80.0, "left_broker10_peak_pct": 80.0,
                    "right_days_over_100pct": 0, "left_days_over_100pct": 0,
                }
                for name, _, _ in stage021.COMPARISONS
            ]
        )
        comparison.loc[comparison["comparison"].eq("A_vs_Q"), "right_return_pct"] = 9.0
        contract = pd.DataFrame(
            [{
                "group_type": "total", "group_value": "all", "diagnostic_count": 10,
                "blocked_count": 2, "long_blocked_count": 1, "short_blocked_count": 1,
                "configuration_contract_pass": 1, "blocking_contract_pass": 1,
            }]
        )

        decision = stage021._decision(comparison, contract)

        self.assertFalse(decision["escalate_to_multicycle"])
        self.assertEqual("stop_p_symmetric_atr_shock_filter_after_full_period", decision["decision"])


if __name__ == "__main__":
    unittest.main()
