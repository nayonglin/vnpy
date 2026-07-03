from __future__ import annotations

from pathlib import Path
import sys
import unittest

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = (
    PROJECT_DIR
    / "research"
    / "lines"
    / "futures_trend_rebuilt_c9_15w_v2_optimization"
    / "tools"
)
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage007_new_position_entry_state_audit as s007


class Stage007NewPositionEntryStateAuditTest(unittest.TestCase):
    def test_match_entry_exposures_uses_product_column_and_allocates_loss(self) -> None:
        window_rows = pd.DataFrame(
            [
                {
                    "window_id": "001_2021-07_a",
                    "source_start_month": "2021-07",
                    "window_start_date": "2021-10-01",
                    "window_end_date": "2021-12-31",
                    "product": "fu.SHFE",
                    "direction": "long",
                    "source_bucket": "opened_or_traded_after_window_start",
                    "stage074_scaled_holding_pnl": -100.0,
                    "stage074_scaled_net_pnl": -110.0,
                },
                {
                    "window_id": "002_2021-07_b",
                    "source_start_month": "2021-07",
                    "window_start_date": "2021-10-01",
                    "window_end_date": "2021-12-31",
                    "product": "SM.CZCE",
                    "direction": "short",
                    "source_bucket": "opened_or_traded_after_window_start",
                    "stage074_scaled_holding_pnl": -20.0,
                    "stage074_scaled_net_pnl": -22.0,
                },
            ]
        )
        lots = pd.DataFrame(
            [
                {
                    "lot_id": 1,
                    "requested_start_month": "2021-07",
                    "product": "fu.SHFE",
                    "direction": "long",
                    "entry_date": "2021-10-15",
                    "ai_product_pool_rank": 3.0,
                    "active_positions_before": 1.0,
                },
                {
                    "lot_id": 2,
                    "requested_start_month": "2021-07",
                    "product": "fu.SHFE",
                    "direction": "long",
                    "entry_date": "2021-11-01",
                    "ai_product_pool_rank": 9.0,
                    "active_positions_before": 4.0,
                },
                {
                    "lot_id": 3,
                    "requested_start_month": "2021-07",
                    "product": "fu.SHFE",
                    "direction": "short",
                    "entry_date": "2021-10-20",
                    "ai_product_pool_rank": 1.0,
                    "active_positions_before": 0.0,
                },
            ]
        )

        exposures, unmatched = s007.match_entry_exposures(
            s007.prepare_window_loss_rows(window_rows),
            s007.prepare_closed_lots(lots),
        )

        self.assertEqual(len(exposures), 2)
        self.assertEqual(len(unmatched), 1)
        self.assertEqual(set(exposures["lot_id"].astype(int)), {1, 2})
        self.assertAlmostEqual(float(exposures["allocated_window_holding_loss_abs"].sum()), 100.0)
        self.assertTrue((exposures["allocated_window_holding_loss_abs"] == 50.0).all())

    def test_condition_summary_measures_loss_lift_without_product_blacklist(self) -> None:
        lots = pd.DataFrame(
            [
                {
                    "lot_id": 1,
                    "requested_start_month": "2021-07",
                    "product": "fu.SHFE",
                    "direction": "long",
                    "entry_date": "2021-10-15",
                    "active_positions_before": 4.0,
                    "ai_product_pool_rank": 9.0,
                },
                {
                    "lot_id": 2,
                    "requested_start_month": "2022-01",
                    "product": "SM.CZCE",
                    "direction": "short",
                    "entry_date": "2022-08-01",
                    "active_positions_before": 4.0,
                    "ai_product_pool_rank": 10.0,
                },
                {
                    "lot_id": 3,
                    "requested_start_month": "2021-07",
                    "product": "rb.SHFE",
                    "direction": "long",
                    "entry_date": "2021-11-01",
                    "active_positions_before": 1.0,
                    "ai_product_pool_rank": 2.0,
                },
                {
                    "lot_id": 4,
                    "requested_start_month": "2022-01",
                    "product": "au.SHFE",
                    "direction": "long",
                    "entry_date": "2022-08-02",
                    "active_positions_before": 0.0,
                    "ai_product_pool_rank": 1.0,
                },
            ]
        )
        lots = s007.prepare_closed_lots(lots)
        exposure_rows = pd.DataFrame(
            [
                {"lot_key": lots.iloc[0]["lot_key"], "allocated_window_holding_loss_abs": 60.0},
                {"lot_key": lots.iloc[1]["lot_key"], "allocated_window_holding_loss_abs": 40.0},
            ]
        )
        background = s007.attach_exposure_weights(lots, exposure_rows)

        summary = s007.summarize_condition_table(
            background,
            min_population_count=1,
            min_source_count=1,
            min_loss_share_pct=1.0,
            min_lift=1.25,
        )
        row = summary.loc[summary["condition"].eq("active_positions_ge3")].iloc[0]

        self.assertAlmostEqual(float(row["population_share_pct"]), 50.0)
        self.assertAlmostEqual(float(row["allocated_loss_share_pct"]), 100.0)
        self.assertAlmostEqual(float(row["loss_lift_vs_population"]), 2.0)
        self.assertTrue(bool(row["stable_candidate"]))
        self.assertFalse(summary["condition"].str.contains("SM|fu|product_direction", regex=True).any())


if __name__ == "__main__":
    unittest.main()
