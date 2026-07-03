import sys
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "research" / "lines" / "futures_trend_rebuilt_c9_15w_optimization" / "tools"
sys.path.insert(0, str(TOOLS))

from stage038_candidate_pit_feature_matrix_audit import (  # noqa: E402
    ConditionSpec,
    attach_pit_monthly_features,
    build_purged_time_splits,
    build_feature_matrix,
    summarize_condition_oos,
)


class Stage038PitFeatureMatrixTest(unittest.TestCase):
    def test_monthly_feature_join_uses_latest_known_eval_date_only(self) -> None:
        entries = pd.DataFrame(
            [
                {
                    "entry_date": "2022-01-15",
                    "product_vt_symbol": "rb.SHFE",
                    "realized_pnl": 100.0,
                }
            ]
        )
        monthly = pd.DataFrame(
            [
                {
                    "eval_date": "2021-12-31",
                    "product_vt_symbol": "rb.SHFE",
                    "ai_rank_desc": 5,
                    "simple_rank_desc": 7,
                    "stage021_consensus_top8": False,
                },
                {
                    "eval_date": "2022-01-31",
                    "product_vt_symbol": "rb.SHFE",
                    "ai_rank_desc": 1,
                    "simple_rank_desc": 1,
                    "stage021_consensus_top8": True,
                },
            ]
        )

        attached = attach_pit_monthly_features(entries, monthly)

        self.assertEqual(attached.loc[0, "full_market_eval_date"], pd.Timestamp("2021-12-31"))
        self.assertEqual(attached.loc[0, "full_market_ai_rank_desc"], 5)
        self.assertFalse(bool(attached.loc[0, "full_market_consensus_top8"]))

    def test_purged_splits_do_not_train_inside_embargo_or_after_test_start(self) -> None:
        frame = pd.DataFrame({"entry_date": pd.date_range("2020-01-01", periods=240, freq="D")})

        splits = build_purged_time_splits(frame, date_column="entry_date", n_splits=3, embargo_days=20)

        self.assertEqual(len(splits), 3)
        for split in splits:
            train_dates = frame.loc[split.train_mask, "entry_date"]
            test_dates = frame.loc[split.test_mask, "entry_date"]
            self.assertGreater(len(test_dates), 0)
            self.assertLessEqual(train_dates.max(), test_dates.min() - pd.Timedelta(days=20))
            self.assertFalse((train_dates >= test_dates.min()).any())

    def test_condition_oos_requires_each_test_fold_to_be_profitable(self) -> None:
        matrix = pd.DataFrame(
            {
                "entry_date": pd.to_datetime(
                    ["2020-01-10", "2020-04-10", "2020-07-10", "2020-10-10"]
                ),
                "realized_pnl": [1000.0, 800.0, -1500.0, 200.0],
                "ai_rank_1_3": [True, True, True, True],
                "post_entry_quality_add_passed": [True, True, True, True],
            }
        )
        splits = build_purged_time_splits(matrix, date_column="entry_date", n_splits=2, embargo_days=0)

        summary = summarize_condition_oos(
            matrix,
            splits,
            [
                ConditionSpec(
                    name="ai_rank_1_3",
                    description="AI rank 1-3",
                    feature_family="ai_rank",
                    eligible=True,
                    mask=matrix["ai_rank_1_3"],
                ),
                ConditionSpec(
                    name="post_entry_quality_add_passed",
                    description="开仓后质量确认",
                    feature_family="post_entry",
                    eligible=False,
                    mask=matrix["post_entry_quality_add_passed"],
                ),
            ],
            min_count=1,
            min_test_folds=2,
        )

        ai_row = summary.set_index("condition").loc["ai_rank_1_3"]
        self.assertEqual(ai_row["oos_test_fold_count"], 2)
        self.assertEqual(ai_row["oos_positive_fold_count"], 1)
        self.assertFalse(bool(ai_row["stable_oos_candidate"]))

        post_entry_row = summary.set_index("condition").loc["post_entry_quality_add_passed"]
        self.assertFalse(bool(post_entry_row["candidate_eligible"]))
        self.assertFalse(bool(post_entry_row["stable_oos_candidate"]))

    def test_feature_matrix_restores_oi_confirmation_from_entry_candidates(self) -> None:
        quality = pd.DataFrame(
            [
                {
                    "requested_start_month": "2020-01",
                    "open_trade_id": "BACKTESTING.1",
                    "lot_id": "lot1",
                    "vt_symbol": "rb2005.SHFE",
                    "product": "rb.SHFE",
                    "direction": "long",
                    "entry_date": "2020-01-10",
                    "exit_date": "2020-01-15",
                    "entry_context": "flat_entry",
                    "layer_kind": "base",
                    "realized_pnl": 1000.0,
                    "risk_amount": 500.0,
                    "volume": 1,
                    "selected_volume": 1,
                    "ai_product_pool_rank": 2,
                    "ai_product_pool_score": 0.8,
                    "portfolio_drawdown_pct": 0.01,
                    "loss_streak": 0,
                }
            ]
        )
        candidates = pd.DataFrame(
            [
                {
                    "requested_start_month": "2020-01",
                    "date": "2020-01-10",
                    "product_vt_symbol": "rb.SHFE",
                    "direction": "long",
                    "entry_context": "flat_entry",
                    "is_opened": 1,
                    "oi_price_confirm_passed": 1,
                }
            ]
        )

        matrix = build_feature_matrix(quality, pd.DataFrame(), entry_candidates=candidates)

        self.assertEqual(len(matrix), 1)
        self.assertTrue(bool(matrix.loc[0, "oi_confirmed"]))


if __name__ == "__main__":
    unittest.main()
