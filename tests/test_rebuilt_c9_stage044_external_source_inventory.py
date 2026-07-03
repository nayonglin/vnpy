import sys
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "research" / "lines" / "futures_trend_rebuilt_c9_15w_optimization" / "tools"
sys.path.insert(0, str(TOOLS))

from stage044_external_source_inventory import (  # noqa: E402
    _classify_source_readiness,
    _summarize_table_coverage,
)


class Stage044ExternalSourceInventoryTest(unittest.TestCase):
    def test_summarize_table_coverage_counts_dates_and_products(self) -> None:
        frame = pd.DataFrame(
            [
                {"date": "2020-01-02", "product_code": "SA", "value": 1.0},
                {"date": "2020-01-03", "product_code": "SA", "value": 2.0},
                {"date": "2020-01-03", "product_code": "FG", "value": 3.0},
                {"date": "2026-06-30", "product_code": "FG", "value": 4.0},
            ]
        )

        summary = _summarize_table_coverage(
            frame,
            source_name="synthetic_history",
            date_column="date",
            product_column="product_code",
        )

        self.assertEqual(summary["row_count"], 4)
        self.assertEqual(summary["date_min"], "2020-01-02")
        self.assertEqual(summary["date_max"], "2026-06-30")
        self.assertEqual(summary["unique_date_count"], 3)
        self.assertEqual(summary["product_count"], 2)
        self.assertEqual(summary["covers_2022_left_tail"], 1)

    def test_summarize_table_coverage_parses_yyyymmdd_integer_dates(self) -> None:
        frame = pd.DataFrame(
            [
                {"date": 20200102, "symbol": "SA"},
                {"date": 20231231, "symbol": "FG"},
            ]
        )

        summary = _summarize_table_coverage(
            frame,
            source_name="synthetic_integer_dates",
            date_column="date",
            product_column="symbol",
        )

        self.assertEqual(summary["date_min"], "2020-01-02")
        self.assertEqual(summary["date_max"], "2023-12-31")
        self.assertEqual(summary["covers_2022_left_tail"], 1)

    def test_summarize_table_coverage_parses_yyyymmdd_float_dates(self) -> None:
        frame = pd.DataFrame(
            [
                {"source_date": 20260601.0, "product_code": "SA"},
                {"source_date": 20260603.0, "product_code": "FG"},
            ]
        )

        summary = _summarize_table_coverage(
            frame,
            source_name="synthetic_float_dates",
            date_column="source_date",
            product_column="product_code",
        )

        self.assertEqual(summary["date_min"], "2026-06-01")
        self.assertEqual(summary["date_max"], "2026-06-03")

    def test_classify_readiness_requires_history_and_pit_validation(self) -> None:
        history = {
            "source_name": "basis_history",
            "date_min": "2020-01-02",
            "date_max": "2026-06-30",
            "product_count": 20,
            "covers_2022_left_tail": 1,
            "point_in_time_validated": 0,
        }
        forward_only = {
            "source_name": "forward_ledger",
            "date_min": "2026-06-01",
            "date_max": "2026-06-03",
            "product_count": 3,
            "covers_2022_left_tail": 0,
            "point_in_time_validated": 1,
        }

        self.assertEqual(_classify_source_readiness(history), "history_candidate_needs_pit_validation")
        self.assertEqual(_classify_source_readiness(forward_only), "forward_monitor_only")


if __name__ == "__main__":
    unittest.main()
