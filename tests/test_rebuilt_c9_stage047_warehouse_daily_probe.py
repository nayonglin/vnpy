import sys
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "research" / "lines" / "futures_trend_rebuilt_c9_15w_optimization" / "tools"
sys.path.insert(0, str(TOOLS))

from stage047_warehouse_build_daily_probe import (  # noqa: E402
    _select_probe_start_dates,
    build_warehouse_lot_deltas,
)


class Stage047WarehouseDailyProbeTest(unittest.TestCase):
    def test_selects_unique_probe_starts_by_variant_bucket(self) -> None:
        worst = pd.DataFrame(
            [
                {
                    "variant": "stage046_warehouse_build_add_risk_proxy",
                    "start_date": "2022-07-15",
                    "return_pct": -44.0,
                },
                {
                    "variant": "stage046_warehouse_build_add_risk_proxy",
                    "start_date": "2022-07-15",
                    "return_pct": -43.0,
                },
                {
                    "variant": "stage046_warehouse_build_add_risk_proxy",
                    "start_date": "2022-07-19",
                    "return_pct": -42.0,
                },
                {
                    "variant": "stage013_engine",
                    "start_date": "2022-03-07",
                    "return_pct": -41.0,
                },
                {
                    "variant": "stage013_engine",
                    "start_date": "2022-07-19",
                    "return_pct": -40.0,
                },
            ]
        )

        selected = _select_probe_start_dates(
            worst,
            bucket_quotas={"stage046_worst": 2, "stage013_worst": 2},
        )

        self.assertEqual(selected["requested_start"].tolist(), ["2022-07-15", "2022-07-19", "2022-03-07"])
        self.assertEqual(selected["requested_start"].nunique(), len(selected))
        self.assertEqual(
            selected["probe_bucket"].value_counts().to_dict(),
            {"stage046_worst": 2, "stage013_worst": 1},
        )

    def test_build_warehouse_lot_deltas_uses_t1_positive_build_only(self) -> None:
        closed = pd.DataFrame(
            [
                {
                    "requested_start_month": "2022-07-15",
                    "lot_id": "a",
                    "product": "rb",
                    "entry_date": "2022-07-20",
                    "exit_date": "2022-08-01",
                    "realized_pnl": 1000.0,
                },
                {
                    "requested_start_month": "2022-07-15",
                    "lot_id": "b",
                    "product": "rb",
                    "entry_date": "2022-07-21",
                    "exit_date": "2022-08-02",
                    "realized_pnl": 2000.0,
                },
            ]
        )
        external = pd.DataFrame(
            [
                {
                    "product": "rb",
                    "data_date": pd.Timestamp("2022-07-19"),
                    "asof_date": pd.Timestamp("2022-07-20"),
                    "external_warehouse_change_20d_sum": 5.0,
                },
                {
                    "product": "rb",
                    "data_date": pd.Timestamp("2022-07-20"),
                    "asof_date": pd.Timestamp("2022-07-21"),
                    "external_warehouse_change_20d_sum": -3.0,
                },
            ]
        )

        deltas = build_warehouse_lot_deltas(closed, external, add_risk_fraction=0.25)

        self.assertEqual(deltas["lot_id"].tolist(), ["a"])
        self.assertAlmostEqual(float(deltas.iloc[0]["stage047_proxy_delta_pnl"]), 250.0)


if __name__ == "__main__":
    unittest.main()
