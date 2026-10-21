import itertools
import unittest

import numpy as np
import pandas as pd

from stage002_cohort_contract import build_cohort_bounds


def cohort(values, missing=0):
    rows = []
    for i, value in enumerate([*values, *([np.nan] * missing)]):
        rows.append(dict(eval_date="2024-01-31", product_vt_symbol=f"p{i}.X",
                         history_ok=True, feature_coverage_ok=True, tradable_asof=True,
                         label_complete=True, label_coverage_ok=np.isfinite(value),
                         label_end="2024-04-30", future_net_pnl_60d=value))
    return pd.DataFrame(rows)


class CohortContractTests(unittest.TestCase):
    def test_unknown_future_member_stays_in_decision_universe(self):
        result = build_cohort_bounds(cohort([1, 2, 3], 1))
        self.assertEqual(len(result), 4)
        self.assertEqual(result.asof_member.sum(), 4)
        self.assertTrue(result.iloc[-1].rank_lower != result.iloc[-1].rank_lower)
        self.assertEqual(result.iloc[1].target_state, "ambiguous")

    def test_bounds_cover_every_missing_extreme_and_tie(self):
        frame = cohort([0, 0, 2, 5], 2)
        result = build_cohort_bounds(frame)
        for missing_values in itertools.product([-10, 0, 1, 2, 5, 10], repeat=2):
            truth = pd.Series([0, 0, 2, 5, *missing_values]).rank(pct=True)
            for i in range(4):
                self.assertLessEqual(result.iloc[i].rank_lower, truth.iloc[i] + 1e-12)
                self.assertGreaterEqual(result.iloc[i].rank_upper, truth.iloc[i] - 1e-12)

    def test_universe_does_not_depend_on_future_values(self):
        before = build_cohort_bounds(cohort([1, 2, 3], 1))
        changed = cohort([1, 2, 3, -999])
        after = build_cohort_bounds(changed)
        self.assertListEqual(before.asof_member.tolist(), after.asof_member.tolist())

    def test_past_ineligible_member_does_not_enter_rank_denominator(self):
        frame = cohort([1, 2, 3, 999])
        frame.loc[3, "feature_coverage_ok"] = False
        result = build_cohort_bounds(frame)
        self.assertEqual(result.iloc[0].asof_universe_count, 3)
        self.assertFalse(result.iloc[3].asof_member)
        self.assertTrue(pd.isna(result.iloc[3].rank_lower))

    def test_immature_labels_remain_unknown(self):
        frame = cohort([1, 2, 3])
        frame["label_complete"] = False
        frame["label_end"] = None
        result = build_cohort_bounds(frame)
        self.assertFalse(result.label_observable.any())
        self.assertTrue(result.rank_lower.isna().all())

    def test_all_ties_never_create_single_class_training_month(self):
        result = build_cohort_bounds(cohort([0, 0, 0]))
        self.assertTrue(result.constant_observed_target.all())
        self.assertFalse(result.point_target_identified.any())
        self.assertTrue((result.target_state == "constant_uninformative").all())

    def test_zero_is_a_real_observed_value(self):
        result = build_cohort_bounds(cohort([-1, 0, 1]))
        self.assertTrue(result.iloc[1].label_observable)
        self.assertAlmostEqual(result.iloc[1].rank_lower, 2 / 3)

    def test_missing_boolean_is_rejected(self):
        frame = cohort([1, 2])
        frame["tradable_asof"] = frame.tradable_asof.astype(object)
        frame.loc[0, "tradable_asof"] = "unknown"
        with self.assertRaisesRegex(ValueError, "boolean"):
            build_cohort_bounds(frame)

    def test_duplicate_member_is_rejected(self):
        frame = cohort([1, 2])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            build_cohort_bounds(pd.concat([frame, frame.iloc[:1]]))

    def test_coverage_true_with_missing_value_is_rejected(self):
        frame = cohort([1, 2], 1)
        frame.loc[2, "label_coverage_ok"] = True
        with self.assertRaisesRegex(ValueError, "finite"):
            build_cohort_bounds(frame)

    def test_label_end_must_be_after_evaluation(self):
        frame = cohort([1, 2])
        frame.loc[0, "label_end"] = "2024-01-31"
        with self.assertRaisesRegex(ValueError, "after"):
            build_cohort_bounds(frame)

    def test_missing_evaluation_date_is_rejected(self):
        frame = cohort([1, 2])
        frame.loc[0, "eval_date"] = None
        with self.assertRaisesRegex(ValueError, "date"):
            build_cohort_bounds(frame)

    def test_missing_or_blank_product_is_rejected(self):
        for value in (None, "", "   "):
            frame = cohort([1, 2])
            frame.loc[0, "product_vt_symbol"] = value
            with self.assertRaisesRegex(ValueError, "product"):
                build_cohort_bounds(frame)

    def test_evaluation_date_must_be_midnight(self):
        frame = cohort([1, 2])
        frame["eval_date"] = "2024-01-31 15:00:00"
        with self.assertRaisesRegex(ValueError, "date"):
            build_cohort_bounds(frame)


if __name__ == "__main__":
    unittest.main()
