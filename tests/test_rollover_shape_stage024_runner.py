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

import stage024_q_double_volume_full_period_acqs as stage024


class Stage024QDoubleVolumeRunnerTest(unittest.TestCase):
    def test_identity_reuses_a_c_q_and_runs_only_s(self) -> None:
        self.assertEqual(["A", "C", "Q", "S"], [arm["arm"] for arm in stage024.ARMS])
        self.assertEqual({"A", "C", "Q"}, stage024.REUSED_ARMS)
        self.assertEqual({"S"}, stage024.NEW_RUN_ARMS)
        candidate = next(arm for arm in stage024.ARMS if arm["arm"] == "S")
        self.assertEqual("Q", candidate["base_arm"])
        self.assertEqual(2.0, candidate["high_volume_ratio_threshold"])
        self.assertEqual(1.5, candidate["high_volume_multiplier"])
        self.assertEqual(0.5, candidate["low_volume_ratio_threshold"])
        self.assertEqual(0.5, candidate["low_volume_multiplier"])
        self.assertFalse(candidate["risk_adjust_long_only"])

    def test_s_overrides_change_only_high_volume_threshold_from_q(self) -> None:
        q = stage024.s21._q_overrides(candidate=True)
        s = stage024._s_overrides(candidate=True)
        differences = {key for key in set(q) | set(s) if q.get(key) != s.get(key)}
        self.assertEqual({"directional_30d_volume_ratio_threshold"}, differences)
        self.assertEqual(3.0, q["directional_30d_volume_ratio_threshold"])
        self.assertEqual(2.0, s["directional_30d_volume_ratio_threshold"])
        self.assertEqual(1.5, s["directional_30d_risk_boost_multiplier"])
        self.assertEqual(0.5, s["directional_30d_low_volume_ratio_threshold"])
        self.assertEqual(0.5, s["directional_30d_low_volume_risk_multiplier"])
        self.assertTrue(s["enable_short_signal_atr_shock_filter"])

    def test_volume_contract_uses_strict_2x_and_05_boundaries_for_both_directions(self) -> None:
        common = {
            "entry_context": "flat_entry",
            "directional_30d_risk_boost_enabled": 1,
            "directional_30d_volume_confirmation_enabled": 1,
            "directional_30d_risk_adjust_long_only": 0,
            "directional_30d_volume_ratio_threshold": 2.0,
            "directional_30d_low_volume_discount_enabled": 1,
            "directional_30d_low_volume_ratio_threshold": 0.5,
            "directional_30d_low_volume_risk_multiplier": 0.5,
            "directional_30d_risk_nonconfirmation_multiplier": 1.0,
            "risk_amount_before_directional_30d_boost": 100.0,
        }
        rows = []
        for direction in ("long", "short"):
            rows.extend([
                {**common, "direction": direction, "directional_30d_risk_boost_aligned": 0,
                 "directional_30d_recent_volume_sum": 499.0, "directional_30d_prior_volume_sum": 1000.0,
                 "directional_30d_risk_boost_applied": 0, "directional_30d_low_volume_discount_applied": 1,
                 "directional_30d_risk_boost_multiplier": 0.5, "target_risk_amount": 50.0},
                {**common, "direction": direction, "directional_30d_risk_boost_aligned": 0,
                 "directional_30d_recent_volume_sum": 500.0, "directional_30d_prior_volume_sum": 1000.0,
                 "directional_30d_risk_boost_applied": 0, "directional_30d_low_volume_discount_applied": 0,
                 "directional_30d_risk_boost_multiplier": 1.0, "target_risk_amount": 100.0},
                {**common, "direction": direction, "directional_30d_risk_boost_aligned": 1,
                 "directional_30d_recent_volume_sum": 2000.0, "directional_30d_prior_volume_sum": 1000.0,
                 "directional_30d_risk_boost_applied": 0, "directional_30d_low_volume_discount_applied": 0,
                 "directional_30d_risk_boost_multiplier": 1.0, "target_risk_amount": 100.0},
                {**common, "direction": direction, "directional_30d_risk_boost_aligned": 1,
                 "directional_30d_recent_volume_sum": 2001.0, "directional_30d_prior_volume_sum": 1000.0,
                 "directional_30d_risk_boost_applied": 1, "directional_30d_low_volume_discount_applied": 0,
                 "directional_30d_risk_boost_multiplier": 1.5, "target_risk_amount": 150.0},
            ])
        summary = stage024._volume_risk_contract_summary(pd.DataFrame(rows))
        total = summary[summary["group_type"].eq("total")].iloc[0]
        self.assertEqual(1, int(total["long_high_volume_count"]))
        self.assertEqual(1, int(total["short_high_volume_count"]))
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
            for name, _, _ in stage024.COMPARISONS
        ])
        volume = pd.DataFrame([{
            "group_type": "total", "threshold_contract_pass": 1, "risk_amount_contract_pass": 1,
            "long_high_volume_count": 1, "short_high_volume_count": 1,
            "long_low_volume_count": 1, "short_low_volume_count": 1,
        }])
        atr = pd.DataFrame([{
            "group_type": "total", "configuration_contract_pass": 1, "blocking_contract_pass": 1,
            "positive_volume_blocked_count": 1,
        }])
        effect = {"effect_present": True, "changed_metrics": ["end_equity"], "metric_differences": {}, "actual_trade_count": 1}
        decision = stage024._decision(comparison, volume, atr, effect)
        self.assertTrue(decision["escalate_to_multicycle"])
        self.assertEqual("run_s_double_volume_multicycle", decision["decision"])


if __name__ == "__main__":
    unittest.main()
