from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_DIR / "research" / "lines" / "futures_trend_rebuilt_c9_15w_v2_optimization" / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage015_purged_meta_label_oos_audit as s015


class Stage015PurgedMetaLabelOosAuditTest(unittest.TestCase):
    def test_build_purged_walk_forward_splits_uses_only_prior_non_overlapping_rows(self) -> None:
        samples = pd.DataFrame(
            [
                {"entry_date": "2020-01-05", "exit_date": "2020-01-20"},
                {"entry_date": "2021-12-20", "exit_date": "2022-01-05"},
                {"entry_date": "2022-01-10", "exit_date": "2022-01-20"},
                {"entry_date": "2023-01-10", "exit_date": "2023-01-20"},
            ]
        )

        splits = s015.build_purged_walk_forward_splits(samples, test_years=[2022], embargo_days=20)

        self.assertEqual(len(splits), 1)
        split = splits[0]
        self.assertEqual(samples.loc[split.train_index, "entry_date"].tolist(), ["2020-01-05"])
        self.assertEqual(samples.loc[split.test_index, "entry_date"].tolist(), ["2022-01-10"])

    def test_assign_yearly_score_buckets_ranks_within_each_test_year(self) -> None:
        scored = pd.DataFrame(
            [
                {"entry_year": 2022, "oos_score": 0.10},
                {"entry_year": 2022, "oos_score": 0.20},
                {"entry_year": 2022, "oos_score": 0.90},
                {"entry_year": 2023, "oos_score": 0.30},
                {"entry_year": 2023, "oos_score": 0.60},
                {"entry_year": 2023, "oos_score": 0.70},
            ]
        )

        bucketed = s015.assign_yearly_score_buckets(scored)

        self.assertEqual(bucketed.loc[0, "score_bucket"], "low")
        self.assertEqual(bucketed.loc[2, "score_bucket"], "high")
        self.assertEqual(bucketed.loc[3, "score_bucket"], "low")
        self.assertEqual(bucketed.loc[5, "score_bucket"], "high")


if __name__ == "__main__":
    unittest.main()
