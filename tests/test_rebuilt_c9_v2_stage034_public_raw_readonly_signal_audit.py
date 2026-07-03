from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_DIR / "research" / "lines" / "futures_trend_rebuilt_c9_15w_v2_optimization" / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage034_public_raw_readonly_signal_audit as s034


class Stage034PublicRawReadonlySignalAuditTest(unittest.TestCase):
    def test_lot_signal_panel_directionally_adjusts_supply_and_member_flow(self) -> None:
        rows = pd.DataFrame(
            [
                {
                    "lot_id": 1,
                    "product_root": "MA",
                    "direction": "long",
                    "entry_date": "2020-01-10",
                    "target_date": "20200102",
                    "preentry_trading_day_offset": 2,
                    "source_family": "member_rank",
                    "numeric_binding_ready": True,
                    "member_rank_long_oi_sum": 100,
                    "member_rank_short_oi_sum": 80,
                    "member_rank_volume_sum": 1_000,
                    "realized_pnl": 1000,
                    "right_tail_top10": 0,
                },
                {
                    "lot_id": 1,
                    "product_root": "MA",
                    "direction": "long",
                    "entry_date": "2020-01-10",
                    "target_date": "20200109",
                    "preentry_trading_day_offset": 1,
                    "source_family": "member_rank",
                    "numeric_binding_ready": True,
                    "member_rank_long_oi_sum": 140,
                    "member_rank_short_oi_sum": 70,
                    "member_rank_volume_sum": 1_500,
                    "realized_pnl": 1000,
                    "right_tail_top10": 0,
                },
                {
                    "lot_id": 1,
                    "product_root": "MA",
                    "direction": "long",
                    "entry_date": "2020-01-10",
                    "target_date": "20200102",
                    "preentry_trading_day_offset": 2,
                    "source_family": "warehouse",
                    "numeric_binding_ready": True,
                    "warehouse_receipt_qty_sum": 900,
                    "realized_pnl": 1000,
                    "right_tail_top10": 0,
                },
                {
                    "lot_id": 1,
                    "product_root": "MA",
                    "direction": "long",
                    "entry_date": "2020-01-10",
                    "target_date": "20200109",
                    "preentry_trading_day_offset": 1,
                    "source_family": "warehouse",
                    "numeric_binding_ready": True,
                    "warehouse_receipt_qty_sum": 700,
                    "realized_pnl": 1000,
                    "right_tail_top10": 0,
                },
            ]
        )

        panel = s034.build_lot_signal_panel(rows)

        self.assertEqual(len(panel), 1)
        self.assertGreater(float(panel.loc[0, "member_net_oi_directional_delta"]), 0)
        self.assertLess(float(panel.loc[0, "supply_directional_delta"]), 0)
        self.assertEqual(panel.loc[0, "H1_supply_member_alignment"], "both_support")
        self.assertEqual(panel.loc[0, "H3_full_support_rising_volume"], "full_support_rising_volume")

    def test_candidate_summary_requires_year_product_right_tail_and_min_year_stability(self) -> None:
        panel = pd.DataFrame(
            [
                {
                    "lot_id": i,
                    "product_root": f"P{i % 4}",
                    "entry_year": 2020 + (i % 4),
                    "realized_pnl": 1000 + i,
                    "right_tail_top10": 1 if i in {1, 9} else 0,
                    "H1_supply_member_alignment": "both_support",
                    "H2_participation_without_alignment": "not_participation_without_full_alignment",
                    "H3_full_support_rising_volume": "full_support_rising_volume",
                }
                for i in range(20)
            ]
        )

        summary = s034.summarize_signal_states(panel)
        candidates = s034.evaluate_readonly_candidates(summary)

        promoted = candidates[candidates["readonly_candidate_allowed"]]
        self.assertIn("H1_supply_member_alignment", set(promoted["hypothesis_id"]))
        self.assertTrue((promoted["right_tail_protected"]).all())
        self.assertTrue((promoted["min_year_pnl"] >= 0).all())

    def test_decision_never_creates_strategy_rule_from_readonly_candidate(self) -> None:
        candidates = pd.DataFrame(
            [
                {
                    "hypothesis_id": "H1_supply_member_alignment",
                    "hypothesis_state": "both_support",
                    "readonly_candidate_allowed": True,
                }
            ]
        )
        panel = pd.DataFrame([{"lot_id": 1}, {"lot_id": 2}])

        decision = s034.make_readonly_signal_decision(panel, candidates)

        self.assertEqual(decision["readonly_candidate_count"], 1)
        self.assertEqual(decision["immediate_strategy_candidate_count"], 0)
        self.assertTrue(decision["proxy_audit_allowed_next"])
        self.assertFalse(decision["strategy_rule_created"])
        self.assertFalse(decision["true_engine"])
        self.assertFalse(decision["order_api_called"])


if __name__ == "__main__":
    unittest.main()
