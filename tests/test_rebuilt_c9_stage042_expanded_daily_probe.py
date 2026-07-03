import sys
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "research" / "lines" / "futures_trend_rebuilt_c9_15w_optimization" / "tools"
sys.path.insert(0, str(TOOLS))

from stage042_expanded_daily_cold_start_probe import (  # noqa: E402
    _aggregate_probe_summary,
    _select_expanded_probe_start_dates,
)


class Stage042ExpandedDailyProbeTest(unittest.TestCase):
    def test_expanded_selection_respects_bucket_quotas_and_unique_dates(self) -> None:
        top_windows = pd.DataFrame(
            [
                {
                    "window_class": "both_negative",
                    "start_date": "2022-07-15",
                    "stage039_return_pct": -40.0,
                    "stage013_return_pct": -39.0,
                    "stage039_absolute_end_ge_stage013": 0,
                },
                {
                    "window_class": "both_negative",
                    "start_date": "2022-07-15",
                    "stage039_return_pct": -39.0,
                    "stage013_return_pct": -38.0,
                    "stage039_absolute_end_ge_stage013": 0,
                },
                {
                    "window_class": "both_negative",
                    "start_date": "2022-07-19",
                    "stage039_return_pct": -30.0,
                    "stage013_return_pct": -29.0,
                    "stage039_absolute_end_ge_stage013": 0,
                },
                {
                    "window_class": "added_negative_by_stage039",
                    "start_date": "2024-01-02",
                    "stage039_return_pct": -0.2,
                    "stage013_return_pct": 0.1,
                    "stage039_absolute_end_ge_stage013": 0,
                },
                {
                    "window_class": "added_negative_by_stage039",
                    "start_date": "2023-05-08",
                    "stage039_return_pct": -0.1,
                    "stage013_return_pct": 0.2,
                    "stage039_absolute_end_ge_stage013": 1,
                },
                {
                    "window_class": "fixed_by_stage039",
                    "start_date": "2021-12-01",
                    "stage039_return_pct": 1.0,
                    "stage013_return_pct": -5.0,
                    "stage039_absolute_end_ge_stage013": 1,
                },
            ]
        )

        selected = _select_expanded_probe_start_dates(
            top_windows,
            bucket_quotas={
                "both_negative": 2,
                "added_negative_absolute_worse": 1,
                "added_negative_denominator": 1,
                "fixed_by_stage039": 1,
            },
        )

        self.assertEqual(len(selected), 5)
        self.assertEqual(selected["requested_start"].tolist()[0:2], ["2022-07-15", "2022-07-19"])
        self.assertEqual(selected["requested_start"].nunique(), len(selected))
        self.assertEqual(
            selected["probe_bucket"].value_counts().to_dict(),
            {
                "both_negative": 2,
                "added_negative_absolute_worse": 1,
                "added_negative_denominator": 1,
                "fixed_by_stage039": 1,
            },
        )

    def test_aggregate_probe_summary_counts_negative_starts_by_variant(self) -> None:
        summary = pd.DataFrame(
            [
                {
                    "variant": "stage013_daily_cold_start_engine",
                    "requested_start": "2022-07-15",
                    "negative_count": 2,
                    "min_return_pct": -3.0,
                    "to_final_return_pct": 50.0,
                },
                {
                    "variant": "stage013_daily_cold_start_engine",
                    "requested_start": "2022-07-19",
                    "negative_count": 0,
                    "min_return_pct": 1.0,
                    "to_final_return_pct": 40.0,
                },
                {
                    "variant": "stage042_daily_cold_start_stage039_ai_top8_proxy",
                    "requested_start": "2022-07-15",
                    "negative_count": 1,
                    "min_return_pct": -2.0,
                    "to_final_return_pct": 55.0,
                },
            ]
        )

        aggregate = _aggregate_probe_summary(summary)

        stage013 = aggregate[aggregate["variant"].eq("stage013_daily_cold_start_engine")].iloc[0]
        self.assertEqual(int(stage013["probe_start_count"]), 2)
        self.assertEqual(int(stage013["negative_probe_start_count"]), 1)
        self.assertAlmostEqual(float(stage013["min_return_pct"]), -3.0)


if __name__ == "__main__":
    unittest.main()
