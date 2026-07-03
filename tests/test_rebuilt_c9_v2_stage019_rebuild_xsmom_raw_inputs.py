from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_DIR / "research" / "lines" / "futures_trend_rebuilt_c9_15w_v2_optimization" / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage019_rebuild_xsmom_raw_inputs as s019


class Stage019RebuildXsmomRawInputsTest(unittest.TestCase):
    def test_summarize_product_returns_counts_dates_products_missing_close_and_valid_end(self) -> None:
        frame = pd.DataFrame(
            [
                {"date": "2020-01-02", "product_vt_symbol": "rb.SHFE", "main_close": 3500, "product_return": 0.0},
                {"date": "2020-01-02", "product_vt_symbol": "SA.CZCE", "main_close": 2500, "product_return": 0.0},
                {"date": "2020-01-03", "product_vt_symbol": "rb.SHFE", "main_close": 3510, "product_return": 0.01},
                {"date": "2020-01-03", "product_vt_symbol": "SA.CZCE", "main_close": 2510, "product_return": 0.02},
                {"date": "2020-01-04", "product_vt_symbol": "rb.SHFE", "main_close": None, "product_return": 0.0},
                {"date": "2020-01-04", "product_vt_symbol": "SA.CZCE", "main_close": None, "product_return": 0.0},
            ]
        )

        summary = s019.summarize_product_returns(frame, min_valid_products=2)

        self.assertEqual(summary["rows"], 6)
        self.assertEqual(summary["products"], 2)
        self.assertEqual(summary["start_date"], "2020-01-02")
        self.assertEqual(summary["end_date"], "2020-01-04")
        self.assertEqual(summary["last_date_with_min_valid_products"], "2020-01-03")
        self.assertEqual(summary["all_missing_close_dates"], 1)
        self.assertEqual(summary["missing_main_close_rows"], 2)

    def test_summarize_satellite_signals_counts_active_rows_and_specs(self) -> None:
        frame = pd.DataFrame(
            [
                {"date": "2020-01-02", "spec": "mom_12m_skip1m", "long_products": "", "short_products": ""},
                {"date": "2020-02-03", "spec": "mom_12m_skip1m", "long_products": "rb.SHFE,SA.CZCE", "short_products": "fu.SHFE"},
                {"date": "2020-02-03", "spec": "mom_6m_skip1m", "long_products": "rb.SHFE", "short_products": ""},
            ]
        )

        summary = s019.summarize_satellite_signals(frame)

        self.assertEqual(summary["rows"], 3)
        self.assertEqual(summary["specs"], 2)
        self.assertEqual(summary["active_signal_rows"], 2)
        self.assertEqual(summary["max_long_count"], 2)
        self.assertEqual(summary["max_short_count"], 1)

    def test_assess_rebuild_requires_nonempty_returns_features_and_active_signals(self) -> None:
        ok = s019.assess_rebuild(
            product_summary={"rows": 10, "products": 8, "last_date_with_min_valid_products": "2026-06-30"},
            feature_rows=20,
            signal_summary={"rows": 5, "active_signal_rows": 2, "specs": 1},
            target_end_date="2026-06-30",
        )
        bad = s019.assess_rebuild(
            product_summary={"rows": 10, "products": 8, "last_date_with_min_valid_products": "2025-12-15"},
            feature_rows=20,
            signal_summary={"rows": 5, "active_signal_rows": 0, "specs": 1},
            target_end_date="2026-06-30",
        )
        stale = s019.assess_rebuild(
            product_summary={"rows": 10, "products": 8, "last_date_with_min_valid_products": "2025-12-15"},
            feature_rows=20,
            signal_summary={"rows": 5, "active_signal_rows": 2, "specs": 1},
            target_end_date="2026-06-30",
        )

        self.assertEqual(ok["decision"], "stage019_xsmom_raw_inputs_rebuilt_ready_for_proxy")
        self.assertEqual(bad["decision"], "stage019_xsmom_raw_inputs_incomplete_keep_readonly")
        self.assertEqual(stale["decision"], "stage019_xsmom_raw_inputs_need_daily_backfill_keep_readonly")


if __name__ == "__main__":
    unittest.main()
