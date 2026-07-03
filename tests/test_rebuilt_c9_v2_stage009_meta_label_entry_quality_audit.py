from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_DIR / "research" / "lines" / "futures_trend_rebuilt_c9_15w_v2_optimization" / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage009_meta_label_entry_quality_audit as s009


class Stage009MetaLabelEntryQualityAuditTest(unittest.TestCase):
    def test_prepare_closed_lots_keeps_only_entry_visible_ai_flat_entries(self) -> None:
        raw = pd.DataFrame(
            [
                {
                    "entry_context": "flat_entry",
                    "direction": "long",
                    "entry_date": "2020-01-03",
                    "risk_amount": 1000,
                    "r_multiple": 2.0,
                    "realized_pnl": 2000,
                    "ai_product_pool_rank": 3,
                    "mae_r": 0.5,
                },
                {
                    "entry_context": "rollover_reopen",
                    "direction": "long",
                    "entry_date": "2020-01-03",
                    "risk_amount": 1000,
                    "r_multiple": 2.0,
                    "realized_pnl": 2000,
                    "ai_product_pool_rank": 3,
                    "mae_r": 0.5,
                },
                {
                    "entry_context": "flat_entry",
                    "direction": "short",
                    "entry_date": "2019-12-30",
                    "risk_amount": 1000,
                    "r_multiple": 2.0,
                    "realized_pnl": 2000,
                    "ai_product_pool_rank": 3,
                    "mae_r": 0.5,
                },
                {
                    "entry_context": "flat_entry",
                    "direction": "short",
                    "entry_date": "2020-01-03",
                    "risk_amount": 1000,
                    "r_multiple": 2.0,
                    "realized_pnl": 2000,
                    "ai_product_pool_rank": 0,
                    "mae_r": 0.5,
                },
            ]
        )

        prepared = s009.prepare_closed_lots_for_quality_audit(raw)

        self.assertEqual(len(prepared), 1)
        self.assertEqual(prepared.iloc[0]["direction"], "long")
        self.assertEqual(int(prepared.iloc[0]["entry_year"]), 2020)
        self.assertEqual(int(prepared.iloc[0]["winner"]), 1)
        self.assertEqual(int(prepared.iloc[0]["bad_path"]), 0)

    def test_evaluate_condition_reports_lift_and_year_stability(self) -> None:
        data = pd.DataFrame(
            [
                {"entry_year": 2020, "realized_pnl": 1000, "r_multiple": 2.0, "big_winner": 0, "bad_path": 0},
                {"entry_year": 2021, "realized_pnl": 2000, "r_multiple": 7.0, "big_winner": 1, "bad_path": 0},
                {"entry_year": 2020, "realized_pnl": -500, "r_multiple": -1.5, "big_winner": 0, "bad_path": 1},
                {"entry_year": 2021, "realized_pnl": -500, "r_multiple": -0.5, "big_winner": 0, "bad_path": 0},
            ]
        )
        mask = pd.Series([True, True, False, False], index=data.index)

        row = s009.evaluate_quality_condition(
            data,
            name="toy_quality",
            description="toy quality condition",
            mask=mask,
            min_event_count=2,
            min_year_count=2,
            min_mean_pnl_lift=2.0,
            max_bad_path_rate_delta_pp=0.0,
        )

        self.assertEqual(row["condition"], "toy_quality")
        self.assertEqual(row["event_count"], 2)
        self.assertAlmostEqual(row["event_share_pct"], 50.0)
        self.assertAlmostEqual(row["total_pnl_share_pct"], 150.0)
        self.assertAlmostEqual(row["mean_pnl_lift"], 3.0)
        self.assertAlmostEqual(row["big_winner_rate_lift"], 2.0)
        self.assertAlmostEqual(row["bad_path_rate_delta_pp"], -25.0)
        self.assertEqual(row["positive_year_count"], 2)
        self.assertTrue(row["stable_quality_candidate"])


if __name__ == "__main__":
    unittest.main()
