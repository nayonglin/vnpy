from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_DIR / "research" / "lines" / "futures_trend_rebuilt_c9_15w_v2_optimization" / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage025_stage024_opened_entry_state_audit as s025


class Stage025Stage024OpenedEntryStateAuditTest(unittest.TestCase):
    def test_prepare_window_loss_rows_keeps_only_stage024_opened_negative_rows(self) -> None:
        raw = pd.DataFrame(
            [
                {
                    "window_id": "w1",
                    "source_start_month": "2022-07",
                    "window_start_date": "2022-07-15",
                    "window_end_date": "2023-07-17",
                    "product": "sp.SHFE",
                    "direction": "long",
                    "source_bucket": "opened_or_traded_after_window_start",
                    "holding_pnl": -80.0,
                    "net_pnl": -100.0,
                },
                {
                    "window_id": "w1",
                    "source_start_month": "2022-07",
                    "window_start_date": "2022-07-15",
                    "window_end_date": "2023-07-17",
                    "product": "rb.SHFE",
                    "direction": "short",
                    "source_bucket": "existing_at_window_start",
                    "holding_pnl": -120.0,
                    "net_pnl": -130.0,
                },
                {
                    "window_id": "w1",
                    "source_start_month": "2022-07",
                    "window_start_date": "2022-07-15",
                    "window_end_date": "2023-07-17",
                    "product": "fu.SHFE",
                    "direction": "long",
                    "source_bucket": "opened_or_traded_after_window_start",
                    "holding_pnl": -20.0,
                    "net_pnl": 10.0,
                },
            ]
        )

        prepared = s025.prepare_window_loss_rows(raw)

        self.assertEqual(len(prepared), 1)
        row = prepared.iloc[0]
        self.assertEqual(row["window_row_id"], 0)
        self.assertEqual(row["product"], "sp.SHFE")
        self.assertAlmostEqual(float(row["window_net_loss_abs"]), 100.0)
        self.assertAlmostEqual(float(row["window_holding_loss_abs"]), 80.0)

    def test_match_entry_exposures_maps_lots_by_source_product_direction_and_entry_window(self) -> None:
        window_rows = s025.prepare_window_loss_rows(
            pd.DataFrame(
                [
                    {
                        "window_id": "w1",
                        "source_start_month": "2022-07",
                        "window_start_date": "2022-07-15",
                        "window_end_date": "2023-07-17",
                        "product": "sp.SHFE",
                        "direction": "long",
                        "source_bucket": "opened_or_traded_after_window_start",
                        "holding_pnl": -80.0,
                        "net_pnl": -100.0,
                    }
                ]
            )
        )
        lots = s025.prepare_closed_lots(
            pd.DataFrame(
                [
                    {
                        "lot_id": 1,
                        "requested_start_month": "2022-07",
                        "product": "sp.SHFE",
                        "direction": "long",
                        "entry_date": "2022-07-15",
                        "realized_pnl": -10.0,
                    },
                    {
                        "lot_id": 2,
                        "requested_start_month": "2022-07",
                        "product": "sp.SHFE",
                        "direction": "long",
                        "entry_date": "2022-11-25",
                        "realized_pnl": -20.0,
                    },
                    {
                        "lot_id": 3,
                        "requested_start_month": "2022-07",
                        "product": "sp.SHFE",
                        "direction": "long",
                        "entry_date": "2023-07-17",
                        "realized_pnl": -30.0,
                    },
                    {
                        "lot_id": 4,
                        "requested_start_month": "2022-07",
                        "product": "sp.SHFE",
                        "direction": "short",
                        "entry_date": "2022-11-25",
                        "realized_pnl": -40.0,
                    },
                ]
            )
        )

        exposures, unmatched = s025.match_entry_exposures(window_rows, lots)

        self.assertTrue(unmatched.empty)
        self.assertEqual(exposures["lot_id"].tolist(), [2, 3])
        self.assertAlmostEqual(float(exposures["allocated_window_net_loss_abs"].sum()), 100.0)
        self.assertAlmostEqual(float(exposures["allocated_window_holding_loss_abs"].sum()), 80.0)
        self.assertTrue((exposures["matched_lot_count"] == 2).all())

    def test_summarize_condition_table_flags_loss_lift_for_pit_quality_condition(self) -> None:
        background = pd.DataFrame(
            [
                {
                    "requested_start_month": "2022-07",
                    "entry_date": "2022-08-01",
                    "lot_key": "2022-07|1",
                    "residual_exposed": True,
                    "residual_exposure_count": 1,
                    "allocated_window_net_loss_abs": 80.0,
                    "allocated_window_holding_loss_abs": 70.0,
                    "ai_product_pool_rank": 5,
                    "selected_volume": 3,
                    "risk_multiplier": 1,
                    "xsmom12_not_opposed": 1,
                },
                {
                    "requested_start_month": "2022-07",
                    "entry_date": "2022-09-01",
                    "lot_key": "2022-07|2",
                    "residual_exposed": True,
                    "residual_exposure_count": 1,
                    "allocated_window_net_loss_abs": 10.0,
                    "allocated_window_holding_loss_abs": 10.0,
                    "ai_product_pool_rank": 4,
                    "selected_volume": 1,
                    "risk_multiplier": 1,
                    "xsmom12_not_opposed": 1,
                },
                {
                    "requested_start_month": "2022-07",
                    "entry_date": "2022-10-01",
                    "lot_key": "2022-07|3",
                    "residual_exposed": False,
                    "residual_exposure_count": 0,
                    "allocated_window_net_loss_abs": 0.0,
                    "allocated_window_holding_loss_abs": 0.0,
                    "ai_product_pool_rank": 3,
                    "selected_volume": 1,
                    "risk_multiplier": 1,
                    "xsmom12_not_opposed": 1,
                },
                {
                    "requested_start_month": "2022-07",
                    "entry_date": "2022-11-01",
                    "lot_key": "2022-07|4",
                    "residual_exposed": False,
                    "residual_exposure_count": 0,
                    "allocated_window_net_loss_abs": 0.0,
                    "allocated_window_holding_loss_abs": 0.0,
                    "ai_product_pool_rank": 9,
                    "selected_volume": 4,
                    "risk_multiplier": 1,
                    "xsmom12_not_opposed": 0,
                },
            ]
        )

        summary = s025.summarize_condition_table(
            background,
            min_population_count=1,
            min_source_count=1,
            min_loss_share_pct=1.0,
            min_lift=1.25,
        )

        condition = summary.set_index("condition").loc["ai_rank_1_8_and_selected_volume_gt1"]
        self.assertTrue(bool(condition["stable_candidate"]))
        self.assertAlmostEqual(float(condition["allocated_net_loss_share_pct"]), 80.0 / 90.0 * 100.0)
        self.assertGreater(float(condition["net_loss_lift_vs_population"]), 1.25)


if __name__ == "__main__":
    unittest.main()
