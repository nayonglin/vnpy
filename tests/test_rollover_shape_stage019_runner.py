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
    import stage019_m_long_atr_shock_filter_full_period_acmo as stage019
except ModuleNotFoundError:
    stage019 = None


class Stage019MLongAtrShockFilterRunnerTest(unittest.TestCase):
    def setUp(self) -> None:
        if stage019 is None:
            self.fail("Stage019 runner is not implemented")

    def test_identity_reuses_a_c_m_and_runs_only_o(self) -> None:
        self.assertEqual(["A", "C", "M", "O"], [arm["arm"] for arm in stage019.ARMS])
        self.assertEqual({"A", "C", "M"}, stage019.REUSED_ARMS)
        self.assertEqual({"O"}, stage019.NEW_RUN_ARMS)
        candidate = next(arm for arm in stage019.ARMS if arm["arm"] == "O")
        self.assertEqual(5, candidate["atr_period"])
        self.assertEqual(2.0, candidate["atr_multiplier"])
        self.assertEqual(
            {"flat_entry", "reverse_entry", "rollover_reopen"},
            set(candidate["entry_contexts"]),
        )
        self.assertTrue(candidate["long_only"])

    def test_filter_contract_requires_strict_block_and_preserves_excluded_paths(self) -> None:
        common = {
            "long_signal_atr_shock_enabled": 1,
            "long_signal_atr_shock_period": 5,
            "long_signal_atr_shock_multiplier": 2.0,
            "long_signal_atr_shock_atr": 1.0,
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

        summary = stage019._atr_filter_contract_summary(pd.DataFrame(rows))
        total = summary[summary["group_type"].eq("total")].iloc[0]

        self.assertEqual(4, int(total["diagnostic_count"]))
        self.assertEqual(1, int(total["blocked_count"]))
        self.assertEqual(1, int(total["flat_entry_blocked_count"]))
        self.assertEqual(0, int(total["reverse_entry_blocked_count"]))
        self.assertEqual(0, int(total["rollover_reopen_blocked_count"]))
        self.assertEqual(1, int(total["configuration_contract_pass"]))
        self.assertEqual(1, int(total["blocking_contract_pass"]))

    def test_decision_requires_o_to_pass_official_and_rollover(self) -> None:
        comparisons = [name for name, _, _ in stage019.COMPARISONS]
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
        comparison.loc[comparison["comparison"].eq("C_vs_O"), "right_return_pct"] = 9.0
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

        decision = stage019._decision(comparison, contract)

        self.assertFalse(decision["escalate_to_multicycle"])
        self.assertEqual("stop_m_long_atr_shock_filter_after_full_period", decision["decision"])


if __name__ == "__main__":
    unittest.main()
