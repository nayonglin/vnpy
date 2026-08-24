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

import stage023_q_low_volume_08_full_period_acqr as stage023


class Stage023QLowVolume08RunnerTest(unittest.TestCase):
    def test_identity_reuses_a_c_q_and_runs_only_r(self) -> None:
        self.assertEqual(["A", "C", "Q", "R"], [arm["arm"] for arm in stage023.ARMS])
        self.assertEqual({"A", "C", "Q"}, stage023.REUSED_ARMS)
        self.assertEqual({"R"}, stage023.NEW_RUN_ARMS)
        candidate = next(arm for arm in stage023.ARMS if arm["arm"] == "R")
        self.assertEqual("Q", candidate["base_arm"])
        self.assertEqual(0.8, candidate["low_volume_ratio_threshold"])
        self.assertEqual(0.5, candidate["low_volume_multiplier"])
        self.assertFalse(candidate["risk_adjust_long_only"])

    def test_r_overrides_change_only_low_volume_threshold_from_q(self) -> None:
        q = stage023.s21._q_overrides(candidate=True)
        r = stage023._r_overrides(candidate=True)
        differences = {key for key in set(q) | set(r) if q.get(key) != r.get(key)}
        self.assertEqual({"directional_30d_low_volume_ratio_threshold"}, differences)
        self.assertEqual(0.5, q["directional_30d_low_volume_ratio_threshold"])
        self.assertEqual(0.8, r["directional_30d_low_volume_ratio_threshold"])
        self.assertEqual(0.5, r["directional_30d_low_volume_risk_multiplier"])
        self.assertTrue(r["enable_short_signal_atr_shock_filter"])

    def test_volume_contract_uses_strict_08_boundary_for_both_directions(self) -> None:
        common = {
            "entry_context": "flat_entry",
            "directional_30d_risk_boost_enabled": 1,
            "directional_30d_volume_confirmation_enabled": 1,
            "directional_30d_risk_adjust_long_only": 0,
            "directional_30d_volume_ratio_threshold": 3.0,
            "directional_30d_low_volume_discount_enabled": 1,
            "directional_30d_low_volume_ratio_threshold": 0.8,
            "directional_30d_low_volume_risk_multiplier": 0.5,
            "directional_30d_risk_nonconfirmation_multiplier": 1.0,
            "risk_amount_before_directional_30d_boost": 100.0,
        }
        rows = []
        for direction in ("long", "short"):
            rows.extend([
                {**common, "direction": direction, "directional_30d_risk_boost_aligned": 0,
                 "directional_30d_recent_volume_sum": 799.0, "directional_30d_prior_volume_sum": 1000.0,
                 "directional_30d_risk_boost_applied": 0, "directional_30d_low_volume_discount_applied": 1,
                 "directional_30d_risk_boost_multiplier": 0.5, "target_risk_amount": 50.0},
                {**common, "direction": direction, "directional_30d_risk_boost_aligned": 0,
                 "directional_30d_recent_volume_sum": 800.0, "directional_30d_prior_volume_sum": 1000.0,
                 "directional_30d_risk_boost_applied": 0, "directional_30d_low_volume_discount_applied": 0,
                 "directional_30d_risk_boost_multiplier": 1.0, "target_risk_amount": 100.0},
                {**common, "direction": direction, "directional_30d_risk_boost_aligned": 1,
                 "directional_30d_recent_volume_sum": 3001.0, "directional_30d_prior_volume_sum": 1000.0,
                 "directional_30d_risk_boost_applied": 1, "directional_30d_low_volume_discount_applied": 0,
                 "directional_30d_risk_boost_multiplier": 1.5, "target_risk_amount": 150.0},
            ])
        summary = stage023._volume_risk_contract_summary(pd.DataFrame(rows))
        total = summary[summary["group_type"].eq("total")].iloc[0]
        self.assertEqual(1, int(total["long_low_volume_count"]))
        self.assertEqual(1, int(total["short_low_volume_count"]))
        self.assertEqual(1, int(total["threshold_contract_pass"]))
        self.assertEqual(1, int(total["risk_amount_contract_pass"]))

    def test_decision_requires_both_baselines_and_incremental_effect(self) -> None:
        comparison = pd.DataFrame([
            {
                "comparison": name, "right_return_pct": 10.0, "left_return_pct": 10.0,
                "dd_worsening_pp": 0.0, "delta_sharpe": 0.0,
                "right_slippage": 100.0, "left_slippage": 100.0,
                "right_survival_pass": 1, "right_broker10_peak_pct": 80.0,
                "left_broker10_peak_pct": 80.0, "right_days_over_100pct": 0,
                "left_days_over_100pct": 0,
            }
            for name, _, _ in stage023.COMPARISONS
        ])
        volume = pd.DataFrame([{
            "group_type": "total", "threshold_contract_pass": 1, "risk_amount_contract_pass": 1,
            "long_low_volume_count": 1, "short_low_volume_count": 1,
        }])
        atr = pd.DataFrame([{
            "group_type": "total", "configuration_contract_pass": 1, "blocking_contract_pass": 1,
            "positive_volume_blocked_count": 1, "zero_volume_rule_hit_count": 0,
        }])
        no_effect = {"effect_present": False, "changed_metrics": [], "metric_differences": {}, "actual_trade_count": 0}
        decision = stage023._decision(comparison, volume, atr, no_effect)
        self.assertFalse(decision["escalate_to_multicycle"])
        self.assertEqual("stop_r_low_volume_08_after_full_period", decision["decision"])

    def test_atr_contract_accounts_for_rule_hit_after_volume_layer_already_selected_zero(self) -> None:
        rows = [
            {
                "direction": "long", "entry_context": "flat_entry",
                "long_signal_atr_shock_enabled": 1, "short_signal_atr_shock_enabled": 1,
                "long_signal_atr_shock_period": 5, "long_signal_atr_shock_multiplier": 1.0,
                "long_signal_atr_shock_atr": 4.944, "long_signal_atr_shock_threshold": 4.944,
                "signal_atr_shock_adverse_move": 7.2, "signal_atr_shock_move_kind": "signal_day_drop",
                "long_signal_atr_shock_blocked": 1,
                "long_signal_atr_shock_reason": "drop_strictly_above_threshold",
                "long_signal_atr_shock_selected_volume_before": 0,
                "long_signal_atr_shock_selected_volume_after": 0,
            },
            {
                "direction": "short", "entry_context": "flat_entry",
                "long_signal_atr_shock_enabled": 1, "short_signal_atr_shock_enabled": 1,
                "long_signal_atr_shock_period": 5, "long_signal_atr_shock_multiplier": 1.0,
                "long_signal_atr_shock_atr": 2.0, "long_signal_atr_shock_threshold": 2.0,
                "signal_atr_shock_adverse_move": 2.1, "signal_atr_shock_move_kind": "signal_day_rise",
                "long_signal_atr_shock_blocked": 1,
                "long_signal_atr_shock_reason": "rise_strictly_above_threshold",
                "long_signal_atr_shock_selected_volume_before": 3,
                "long_signal_atr_shock_selected_volume_after": 0,
            },
        ]
        contract = stage023._atr_filter_contract_summary(pd.DataFrame(rows))
        total = contract[contract["group_type"].eq("total")].iloc[0]
        self.assertEqual(1, int(total["zero_volume_rule_hit_count"]))
        self.assertEqual(1, int(total["positive_volume_blocked_count"]))
        self.assertEqual(1, int(total["configuration_contract_pass"]))
        self.assertEqual(1, int(total["blocking_contract_pass"]))


if __name__ == "__main__":
    unittest.main()
