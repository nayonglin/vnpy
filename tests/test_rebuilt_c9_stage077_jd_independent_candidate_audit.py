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


from stage077_jd_independent_candidate_audit import (  # noqa: E402
    build_jd_selector_conditions,
    extract_product_monthly_predictions,
    summarize_jd_conditions,
)


class Stage077JdIndependentCandidateAuditTest(unittest.TestCase):
    def test_extract_product_monthly_predictions_normalizes_product_and_boolean_flags(self) -> None:
        predictions = pd.DataFrame(
            [
                {
                    "eval_date": "2025-01-31",
                    "product_vt_symbol": "JD.DCE",
                    "ai_rank_desc": 5,
                    "simple_rank_desc": 11,
                    "stage021_ai_top8": "True",
                    "stage021_simple_top8": "0",
                    "stage021_consensus_top8": False,
                    "future_net_pnl_60d": 1000,
                },
                {
                    "eval_date": "2025-01-31",
                    "product_vt_symbol": "rb.SHFE",
                    "ai_rank_desc": 1,
                    "simple_rank_desc": 1,
                    "stage021_ai_top8": True,
                    "stage021_simple_top8": True,
                    "stage021_consensus_top8": True,
                    "future_net_pnl_60d": 2000,
                },
            ]
        )

        jd = extract_product_monthly_predictions(predictions, product_vt_symbol="jd.DCE")

        self.assertEqual(len(jd), 1)
        self.assertEqual(jd.loc[0, "product_key"], "jd.dce")
        self.assertEqual(jd.loc[0, "eval_date"], pd.Timestamp("2025-01-31"))
        self.assertTrue(bool(jd.loc[0, "jd_ai_top8"]))
        self.assertFalse(bool(jd.loc[0, "jd_simple_top8"]))
        self.assertFalse(bool(jd.loc[0, "jd_consensus_top8"]))

    def test_build_jd_selector_conditions_keeps_shared_rerank_out_of_candidate_set(self) -> None:
        frame = pd.DataFrame(
            [
                {"jd_ai_top8": True, "jd_simple_top8": True, "jd_consensus_top8": True},
                {"jd_ai_top8": True, "jd_simple_top8": False, "jd_consensus_top8": False},
                {"jd_ai_top8": False, "jd_simple_top8": True, "jd_consensus_top8": False},
            ]
        )

        conditions = build_jd_selector_conditions(frame)
        names = {condition.name for condition in conditions}

        self.assertIn("jd_consensus_top8_independent", names)
        self.assertIn("jd_ai_top8_independent", names)
        self.assertNotIn("jd_shared_ai_rerank", names)

    def test_summarize_jd_conditions_rejects_negative_year_even_if_total_pnl_positive(self) -> None:
        frame = pd.DataFrame(
            [
                {"eval_date": "2022-01-31", "eval_year": 2022, "future_net_pnl_60d": 100.0, "jd_ai_top8": True, "jd_simple_top8": False, "jd_consensus_top8": False},
                {"eval_date": "2022-02-28", "eval_year": 2022, "future_net_pnl_60d": -200.0, "jd_ai_top8": True, "jd_simple_top8": False, "jd_consensus_top8": False},
                {"eval_date": "2023-01-31", "eval_year": 2023, "future_net_pnl_60d": 1000.0, "jd_ai_top8": True, "jd_simple_top8": False, "jd_consensus_top8": False},
                {"eval_date": "2024-01-31", "eval_year": 2024, "future_net_pnl_60d": 500.0, "jd_ai_top8": True, "jd_simple_top8": False, "jd_consensus_top8": False},
            ]
        )

        summary = summarize_jd_conditions(
            frame,
            build_jd_selector_conditions(frame),
            min_count=3,
            min_years=3,
            min_total_pnl=100.0,
        )

        row = summary[summary["condition"].eq("jd_ai_top8_independent")].iloc[0]
        self.assertGreater(float(row["total_future_net_pnl_60d"]), 0.0)
        self.assertEqual(int(row["negative_year_count"]), 1)
        self.assertFalse(bool(row["stage077_independent_candidate"]))


if __name__ == "__main__":
    unittest.main()
