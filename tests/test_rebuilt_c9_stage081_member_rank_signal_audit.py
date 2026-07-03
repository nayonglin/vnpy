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


from stage081_member_rank_signal_audit import (  # noqa: E402
    Stage081ConditionSpec,
    add_directional_member_rank_features,
    decision_from_member_rank_summary,
    member_rank_condition_summary,
)


class RebuiltC9Stage081MemberRankSignalAuditTest(unittest.TestCase):
    def test_directional_member_rank_features_follow_trade_direction(self) -> None:
        frame = pd.DataFrame(
            {
                "direction": ["long", "short", "short", "long"],
                "member_rank_available": [True, True, True, False],
                "member_rank_net_position_ratio_top20": [0.20, 0.30, -0.40, 0.50],
                "member_rank_net_position_chg_ratio_top20": [0.03, -0.02, 0.04, 0.10],
            }
        )

        result = add_directional_member_rank_features(frame)

        self.assertAlmostEqual(result.loc[0, "member_rank_directional_net_position"], 0.20)
        self.assertAlmostEqual(result.loc[1, "member_rank_directional_net_position"], -0.30)
        self.assertAlmostEqual(result.loc[2, "member_rank_directional_net_position"], 0.40)
        self.assertFalse(bool(result.loc[3, "member_rank_net_position_aligned"]))
        self.assertTrue(bool(result.loc[0, "member_rank_net_position_aligned"]))
        self.assertFalse(bool(result.loc[1, "member_rank_net_position_aligned"]))
        self.assertFalse(bool(result.loc[2, "member_rank_net_flow_aligned"]))

    def test_member_rank_condition_summary_rejects_small_unstable_sample(self) -> None:
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
            Stage081ConditionSpec(
                name="tiny_member_rank",
                description="tiny sample",
                feature_family="member_rank_test",
                mask=pd.Series([True, True, False, False], index=frame.index),
                promotion_eligible=True,
            )
        ]

        summary = member_rank_condition_summary(
            frame,
            specs,
            min_count=3,
            min_source_count=2,
            min_year_count=2,
            min_product_count=2,
            min_oos_folds=2,
        )
        row = summary.set_index("condition").loc["tiny_member_rank"]

        self.assertEqual(int(row["count"]), 2)
        self.assertFalse(bool(row["member_rank_signal_candidate"]))
        self.assertIn("count", str(row["failure_reasons"]))

    def test_decision_from_member_rank_summary_requires_stable_candidate(self) -> None:
        summary = pd.DataFrame(
            [
                {
                    "condition": "member_rank_net_position_aligned",
                    "member_rank_signal_candidate": False,
                    "promotion_eligible": True,
                    "count": 500,
                    "mean_pnl_lift_vs_base": 0.8,
                    "oos_min_fold_pnl": -10.0,
                },
                {
                    "condition": "full_market_ai_top8_and_member_net_flow_aligned",
                    "member_rank_signal_candidate": True,
                    "promotion_eligible": True,
                    "count": 150,
                    "mean_pnl_lift_vs_base": 2.2,
                    "oos_min_fold_pnl": 100.0,
                },
            ]
        )

        decision = decision_from_member_rank_summary(summary, matrix_rows=1000, available_rows=700)

        self.assertEqual(decision["decision"], "stage081_member_rank_has_stable_signal_candidate_needs_proxy")
        self.assertEqual(
            decision["best_member_rank_candidate"]["condition"],
            "full_market_ai_top8_and_member_net_flow_aligned",
        )


if __name__ == "__main__":
    unittest.main()
