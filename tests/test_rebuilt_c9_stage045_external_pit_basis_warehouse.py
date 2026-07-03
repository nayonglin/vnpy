import sys
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "research" / "lines" / "futures_trend_rebuilt_c9_15w_optimization" / "tools"
sys.path.insert(0, str(TOOLS))

from stage045_external_pit_basis_warehouse_audit import (  # noqa: E402
    ConditionSpec,
    attach_t1_external_features,
    build_external_daily_features,
    build_purged_time_splits,
    summarize_condition_oos,
)


class Stage045ExternalPitBasisWarehouseTest(unittest.TestCase):
    def test_t1_attach_does_not_use_same_day_external_data(self) -> None:
        entries = pd.DataFrame(
            [
                {"entry_date": "2020-01-02", "product": "rb.SHFE", "realized_pnl": -100.0},
                {"entry_date": "2020-01-03", "product": "rb.SHFE", "realized_pnl": 200.0},
            ]
        )
        basis = pd.DataFrame(
            [
                {
                    "date": 20200102,
                    "symbol": "rb",
                    "dom_basis_rate": 0.12,
                    "near_basis_rate": 0.10,
                }
            ]
        )
        warehouse = pd.DataFrame(
            [
                {
                    "date": 20200102,
                    "product_code": "RB",
                    "warehouse_receipt_quantity": 1000.0,
                    "warehouse_receipt_change": -50.0,
                }
            ]
        )

        features = build_external_daily_features(basis, warehouse, min_history=1)
        attached = attach_t1_external_features(entries, features)

        self.assertTrue(pd.isna(attached.loc[0, "external_dom_basis_rate"]))
        self.assertEqual(attached.loc[1, "external_feature_date"], pd.Timestamp("2020-01-02"))
        self.assertEqual(attached.loc[1, "external_asof_date"], pd.Timestamp("2020-01-03"))
        self.assertAlmostEqual(attached.loc[1, "external_dom_basis_rate"], 0.12)
        self.assertAlmostEqual(attached.loc[1, "external_warehouse_receipt_change"], -50.0)

    def test_daily_feature_builder_normalises_product_codes(self) -> None:
        basis = pd.DataFrame(
            [
                {"date": "2020-01-02", "symbol": "FG.CZCE", "dom_basis_rate": -0.02},
                {"date": "2020-01-03", "symbol": "fg", "dom_basis_rate": 0.04},
            ]
        )
        warehouse = pd.DataFrame(
            [
                {
                    "date": "2020-01-03",
                    "product_code": "FG",
                    "warehouse_receipt_quantity": 200.0,
                    "warehouse_receipt_change": 20.0,
                }
            ]
        )

        features = build_external_daily_features(basis, warehouse, min_history=1)

        self.assertEqual(set(features["product_code"]), {"FG"})
        last = features.sort_values("feature_date").iloc[-1]
        self.assertEqual(last["feature_date"], pd.Timestamp("2020-01-03"))
        self.assertEqual(last["asof_date"], pd.Timestamp("2020-01-04"))
        self.assertAlmostEqual(last["dom_basis_rate"], 0.04)
        self.assertAlmostEqual(last["warehouse_receipt_quantity"], 200.0)

    def test_condition_oos_requires_positive_test_folds(self) -> None:
        matrix = pd.DataFrame(
            {
                "entry_date": pd.to_datetime(["2020-01-10", "2020-04-10", "2020-07-10", "2020-10-10"]),
                "realized_pnl": [100.0, 200.0, -500.0, 300.0],
                "external_basis_high_p80": [True, True, True, True],
            }
        )
        splits = build_purged_time_splits(matrix, date_column="entry_date", n_splits=2, embargo_days=0)

        summary = summarize_condition_oos(
            matrix,
            splits,
            [
                ConditionSpec(
                    name="external_basis_high_p80",
                    description="basis high",
                    feature_family="external_basis",
                    eligible=True,
                    mask=matrix["external_basis_high_p80"],
                )
            ],
            min_count=1,
            min_test_folds=2,
        )

        row = summary.set_index("condition").loc["external_basis_high_p80"]
        self.assertEqual(row["oos_test_fold_count"], 2)
        self.assertEqual(row["oos_positive_fold_count"], 1)
        self.assertFalse(bool(row["stable_oos_candidate"]))


if __name__ == "__main__":
    unittest.main()
