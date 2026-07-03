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


from stage057_stage056_failure_attribution import (  # noqa: E402
    _classify_stage056_window_effect,
    _match_cap_events_to_baseline_lots,
    _summarize_matched_cap_lots,
)


class RebuiltC9Stage057Stage056FailureAttributionTest(unittest.TestCase):
    def test_classifies_added_negative_and_denominator_effect(self) -> None:
        row = _classify_stage056_window_effect(
            source_start="2022-03-30",
            start_date=pd.Timestamp("2023-01-01"),
            end_date=pd.Timestamp("2024-01-05"),
            stage013_start_equity=100.0,
            stage013_end_equity=101.0,
            stage056_start_equity=150.0,
            stage056_end_equity=149.0,
        )

        self.assertEqual(row["window_class"], "added_negative_by_stage056")
        self.assertEqual(row["stage056_absolute_end_ge_stage013"], 1)
        self.assertEqual(row["stage056_added_negative_denominator_effect"], 1)

    def test_classifies_true_absolute_worse_added_negative(self) -> None:
        row = _classify_stage056_window_effect(
            source_start="2022-03-30",
            start_date=pd.Timestamp("2023-01-01"),
            end_date=pd.Timestamp("2024-01-05"),
            stage013_start_equity=100.0,
            stage013_end_equity=103.0,
            stage056_start_equity=100.0,
            stage056_end_equity=99.0,
        )

        self.assertEqual(row["window_class"], "added_negative_by_stage056")
        self.assertEqual(row["stage056_absolute_end_ge_stage013"], 0)
        self.assertEqual(row["stage056_added_negative_denominator_effect"], 0)

    def test_matches_cap_event_to_baseline_lot_and_computes_removed_pnl_proxy(self) -> None:
        events = pd.DataFrame(
            [
                {
                    "requested_start": "2022-03-30",
                    "date": "2022-04-15",
                    "contract_vt_symbol": "fu2209.SHFE",
                    "product_vt_symbol": "fu.SHFE",
                    "direction": "long",
                    "stage056_budget_cap_selected_volume_before": 5,
                    "stage056_budget_cap_selected_volume_after": 1,
                },
                {
                    "requested_start": "2022-03-30",
                    "date": "2022-04-19",
                    "contract_vt_symbol": "SM209.CZCE",
                    "product_vt_symbol": "SM.CZCE",
                    "direction": "long",
                    "stage056_budget_cap_selected_volume_before": 6,
                    "stage056_budget_cap_selected_volume_after": 1,
                },
            ]
        )
        lots = pd.DataFrame(
            [
                {
                    "requested_start": "2022-03-30",
                    "entry_date": "2022-04-18",
                    "vt_symbol": "fu2209.SHFE",
                    "product": "fu.SHFE",
                    "direction": "long",
                    "volume": 5,
                    "realized_pnl": 1000.0,
                },
                {
                    "requested_start": "2022-03-30",
                    "entry_date": "2022-04-19",
                    "vt_symbol": "SM209.CZCE",
                    "product": "SM.CZCE",
                    "direction": "long",
                    "volume": 6,
                    "realized_pnl": -600.0,
                },
            ]
        )

        matched = _match_cap_events_to_baseline_lots(events, lots)
        by_symbol = matched.set_index("contract_vt_symbol")

        self.assertAlmostEqual(float(by_symbol.loc["fu2209.SHFE", "removed_pnl_proxy"]), 800.0)
        self.assertAlmostEqual(float(by_symbol.loc["SM209.CZCE", "removed_pnl_proxy"]), -500.0)
        self.assertEqual(int(by_symbol.loc["fu2209.SHFE", "baseline_lot_matched"]), 1)

    def test_summarizes_removed_pnl_proxy_by_source(self) -> None:
        matched = pd.DataFrame(
            [
                {"requested_start": "2022-03-30", "removed_pnl_proxy": 800.0, "baseline_lot_matched": 1},
                {"requested_start": "2022-03-30", "removed_pnl_proxy": -500.0, "baseline_lot_matched": 1},
                {"requested_start": "2022-08-22", "removed_pnl_proxy": -1000.0, "baseline_lot_matched": 1},
            ]
        )

        summary = _summarize_matched_cap_lots(matched, group_columns=["requested_start"])
        by_start = summary.set_index("requested_start")

        self.assertAlmostEqual(float(by_start.loc["2022-03-30", "removed_pnl_proxy_sum"]), 300.0)
        self.assertAlmostEqual(float(by_start.loc["2022-03-30", "removed_positive_pnl_proxy"]), 800.0)
        self.assertAlmostEqual(float(by_start.loc["2022-03-30", "removed_negative_pnl_proxy"]), -500.0)
        self.assertAlmostEqual(float(by_start.loc["2022-08-22", "removed_pnl_proxy_sum"]), -1000.0)


if __name__ == "__main__":
    unittest.main()
