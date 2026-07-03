from __future__ import annotations

from pathlib import Path
import sys
import unittest

import pandas as pd


TOOLS_DIR = (
    Path(__file__).resolve().parents[1]
    / "research"
    / "lines"
    / "futures_trend_rebuilt_c9_15w_optimization"
    / "tools"
)
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


from stage068_super_quality_signal_audit import (  # noqa: E402
    Stage068CandidateSpec,
    _stage068_assign_oos_folds,
    _stage068_condition_summary,
    _stage068_decision_from_summary,
)


class RebuiltC9Stage068SuperQualitySignalAuditTest(unittest.TestCase):
    def test_assign_oos_folds_uses_stage038_test_windows(self) -> None:
        matrix = pd.DataFrame(
            {
                "entry_date": ["2020-01-10", "2021-01-05", "2022-06-01", "2024-01-01"],
                "realized_pnl": [1.0, 2.0, 3.0, 4.0],
            }
        )
        folds = pd.DataFrame(
            [
                {"split_id": "fold_01", "test_start": "2020-12-01", "test_end": "2021-12-31"},
                {"split_id": "fold_02", "test_start": "2022-01-01", "test_end": "2022-12-31"},
            ]
        )

        assigned = _stage068_assign_oos_folds(matrix, folds)

        self.assertEqual(assigned.loc[0, "stage038_oos_fold"], "")
        self.assertEqual(assigned.loc[1, "stage038_oos_fold"], "fold_01")
        self.assertEqual(assigned.loc[2, "stage038_oos_fold"], "fold_02")
        self.assertEqual(assigned.loc[3, "stage038_oos_fold"], "")

    def test_condition_summary_rejects_small_high_mean_sample(self) -> None:
        frame = pd.DataFrame(
            {
                "requested_start_month": ["2020-01", "2020-07", "2021-01", "2021-07"],
                "entry_date": pd.to_datetime(["2020-01-05", "2020-06-05", "2021-01-05", "2021-06-05"]),
                "entry_year": [2020, 2020, 2021, 2021],
                "product_vt_symbol": ["rb.SHFE", "SA.CZCE", "FG.CZCE", "MA.CZCE"],
                "realized_pnl": [1000.0, 900.0, 800.0, -100.0],
                "r_multiple_agg": [1.0, 1.2, 1.1, -0.2],
                "big_winner": [False, False, False, False],
                "stage038_oos_fold": ["fold_01", "fold_01", "fold_02", "fold_02"],
            }
        )
        specs = [
            Stage068CandidateSpec(
                name="tiny_high_mean",
                description="tiny sample",
                feature_family="test",
                mask=pd.Series([True, True, False, False], index=frame.index),
                promotion_eligible=True,
                new_composite=True,
            )
        ]

        summary = _stage068_condition_summary(
            frame,
            specs,
            min_count=3,
            min_source_count=2,
            min_year_count=2,
            min_product_count=2,
            min_oos_folds=2,
        )
        row = summary.set_index("condition").loc["tiny_high_mean"]

        self.assertEqual(int(row["count"]), 2)
        self.assertFalse(bool(row["super_quality_candidate"]))
        self.assertIn("count", str(row["failure_reasons"]))

    def test_decision_prefers_new_composite_candidate(self) -> None:
        summary = pd.DataFrame(
            [
                {
                    "condition": "full_market_ai_top8",
                    "super_quality_candidate": True,
                    "promotion_eligible": True,
                    "new_composite": False,
                    "count": 350,
                    "mean_pnl_lift_vs_base": 2.0,
                    "oos_min_fold_pnl": 100.0,
                },
                {
                    "condition": "full_market_ai_top8_and_ai_rank_1_6",
                    "super_quality_candidate": True,
                    "promotion_eligible": True,
                    "new_composite": True,
                    "count": 180,
                    "mean_pnl_lift_vs_base": 3.0,
                    "oos_min_fold_pnl": 80.0,
                },
            ]
        )

        decision = _stage068_decision_from_summary(summary, matrix_rows=1000)

        self.assertEqual(decision["decision"], "stage068_has_new_composite_super_quality_candidate_needs_proxy")
        self.assertEqual(decision["best_new_composite_candidate"]["condition"], "full_market_ai_top8_and_ai_rank_1_6")


if __name__ == "__main__":
    unittest.main()
