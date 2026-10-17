"""Boundary tests: false coverage and future labels must not become samples."""
import unittest

import pandas as pd

import stage262_ai_sample_contract as contract


class SampleContractTests(unittest.TestCase):
    def setUp(self):
        self.dates = pd.bdate_range("2020-01-01", periods=10)
        self.daily = pd.MultiIndex.from_product(
            [self.dates, ["a.DCE", "b.DCE"]], names=["date", "product_vt_symbol"]
        ).to_frame(index=False)
        self.coverage = self.daily.assign(observed=True, mapped=True)

    def metadata(self):
        return contract.build_window_metadata(self.daily, self.coverage, history=3, horizon=2)

    def row(self, frame, day, product="a.DCE"):
        return frame.set_index(["eval_date", "product_vt_symbol"]).loc[(self.dates[day], product)]

    def test_missing_or_precoverage_history_is_not_zero_history(self):
        self.coverage.loc[(self.coverage.product_vt_symbol == "b.DCE") &
                          (self.coverage.date < self.dates[3]), "observed"] = False
        data = self.metadata()
        self.assertFalse(self.row(data, 4, "b.DCE").feature_coverage_ok)
        self.assertTrue(self.row(data, 5, "b.DCE").feature_coverage_ok)
        self.assertFalse(self.row(data, 1).history_ok)
        self.assertEqual(self.row(data, 5).feature_start, self.dates[3])

    def test_mapping_gap_rejects_full_window_even_if_source_present(self):
        self.coverage.loc[(self.coverage.product_vt_symbol == "a.DCE") &
                          (self.coverage.date == self.dates[4]), "mapped"] = False
        data = self.metadata()
        self.assertFalse(self.row(data, 5).feature_coverage_ok)
        self.assertFalse(self.row(data, 3).label_coverage_ok)
        self.assertTrue(self.row(data, 7).feature_coverage_ok)

    def test_future_window_excludes_eval_day_and_requires_full_horizon(self):
        data = self.metadata()
        row = self.row(data, 6)
        self.assertEqual(row.label_start, self.dates[7])
        self.assertEqual(row.label_end, self.dates[8])
        self.assertEqual(row.label_observed_days, 2)
        tail = self.row(data, 8)
        self.assertEqual(tail.label_observed_days, 1)
        self.assertFalse(tail.label_complete)
        self.assertTrue(pd.isna(tail.label_end))

    def test_purge_uses_label_end_not_row_count_or_month(self):
        frame = pd.DataFrame({"eval_date": self.dates[:4],
                              "label_end": [self.dates[5], self.dates[6], self.dates[7], pd.NaT],
                              "label_complete": [True, True, True, False]})
        chosen = contract.mature_training(frame, self.dates[6])
        self.assertEqual(chosen.index.tolist(), [0, 1])

    def test_rank_targets_remove_ghost_products_without_changing_features(self):
        frame = pd.DataFrame({"eval_date": [self.dates[4]] * 4,
                              "product_vt_symbol": ["a", "b", "c", "ghost"],
                              "future_net_pnl_60d": [-10., -5., 4., 0.],
                              "original_feature": [11., 12., 13., 0.],
                              "eligible": [True, True, True, False]})
        ranked = contract.rerank_eligible(frame)
        self.assertEqual(ranked.product_vt_symbol.tolist(), ["a", "b", "c"])
        self.assertEqual(ranked.original_feature.tolist(), [11., 12., 13.])
        self.assertAlmostEqual(ranked.iloc[1].future_rank_pct_60d, 2 / 3)
        self.assertEqual(ranked[contract.TARGET].tolist(), [0, 1, 1])

    def test_month_metric_has_zero_lift_when_selecting_whole_universe(self):
        frame = pd.DataFrame({"product_vt_symbol": ["a", "b", "c"],
                              "future_net_pnl_60d": [1., 2., 3.], "score": [1., 2., 3.]})
        metrics = contract.month_metrics(frame, top_n=10)
        self.assertEqual(metrics["top_rank_lift"], 0)
        self.assertAlmostEqual(metrics["rank_ic"], 1)


if __name__ == "__main__":
    unittest.main()
