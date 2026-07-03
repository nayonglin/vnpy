from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_DIR / "research" / "lines" / "futures_trend_rebuilt_c9_15w_v2_optimization" / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage056_combination_overlap_audit as s056


class Stage056CombinationOverlapAuditTest(unittest.TestCase):
    def test_normalize_id_keeps_trade_ids_and_removes_numeric_float_noise(self) -> None:
        self.assertEqual(s056._normalize_id("92.0"), "92")
        self.assertEqual(s056._normalize_id(92.0), "92")
        self.assertEqual(s056._normalize_id("BACKTESTING.180"), "BACKTESTING.180")

    def test_capped_combo_sums_distinct_events_and_caps_overlap(self) -> None:
        events = pd.DataFrame(
            [
                {
                    "module": "a",
                    "event_key": "k1",
                    "realized_pnl": 100.0,
                    "add_fraction": 0.25,
                    "delta_pnl": 25.0,
                },
                {
                    "module": "b",
                    "event_key": "k1",
                    "realized_pnl": 100.0,
                    "add_fraction": 0.40,
                    "delta_pnl": 40.0,
                },
                {
                    "module": "b",
                    "event_key": "k2",
                    "realized_pnl": -100.0,
                    "add_fraction": 0.25,
                    "delta_pnl": -25.0,
                },
            ]
        )

        audit = s056.build_capped_combo(events, "combo", ["a", "b"], cap_fraction=0.50)

        self.assertEqual(audit["event_count"], 2)
        self.assertEqual(audit["overlap_event_count"], 1)
        self.assertAlmostEqual(audit["raw_proxy_delta_sum_before_cap"], 40.0)
        self.assertAlmostEqual(audit["total_proxy_delta_pnl"], 25.0)
        self.assertAlmostEqual(audit["cap_or_max_penalty_pnl"], 15.0)

    def test_pairwise_overlap_uses_exact_event_keys(self) -> None:
        events = pd.DataFrame(
            [
                {
                    "module": "a",
                    "event_key": "k1",
                    "semantic_key": "s1",
                    "delta_pnl": 10.0,
                },
                {
                    "module": "a",
                    "event_key": "k2",
                    "semantic_key": "s2",
                    "delta_pnl": 20.0,
                },
                {
                    "module": "b",
                    "event_key": "k2",
                    "semantic_key": "s2",
                    "delta_pnl": 30.0,
                },
            ]
        )

        overlap = s056.build_pairwise_overlap(events)

        self.assertEqual(int(overlap.loc[0, "exact_overlap_count"]), 1)
        self.assertEqual(float(overlap.loc[0, "exact_overlap_a_pct"]), 50.0)
        self.assertEqual(float(overlap.loc[0, "exact_overlap_b_pct"]), 100.0)
        self.assertEqual(float(overlap.loc[0, "a_overlap_delta_pnl"]), 20.0)
        self.assertEqual(float(overlap.loc[0, "b_overlap_delta_pnl"]), 30.0)


if __name__ == "__main__":
    unittest.main()
