from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_DIR / "research" / "lines" / "futures_trend_rebuilt_c9_15w_v2_optimization" / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage020_sqlite_jd_repair_xsmom_inputs as s020


class Stage020SqliteJdRepairXsmomInputsTest(unittest.TestCase):
    def test_merge_close_sources_prefers_later_repair_source_on_overlap(self) -> None:
        sqlite = pd.DataFrame(
            [
                {"date": "2026-06-30", "main_contract_vt": "jd2706.DCE", "close_price": 3200, "source": "sqlite_db"},
            ]
        )
        repair = pd.DataFrame(
            [
                {"date": "2026-06-30", "main_contract_vt": "jd2706.DCE", "close_price": 3275, "source": "stage050_jd_repair"},
            ]
        )

        merged = s020.merge_close_sources([sqlite, repair])

        self.assertEqual(len(merged), 1)
        self.assertEqual(float(merged.iloc[0]["close_price"]), 3275.0)
        self.assertEqual(merged.iloc[0]["source"], "stage050_jd_repair")

    def test_normalise_contract_bar_source_accepts_stage050_like_bars(self) -> None:
        bars = pd.DataFrame(
            [
                {
                    "datetime": "2026-03-26",
                    "contract_vt_symbol": "jd2605.DCE",
                    "close_price": 3310,
                }
            ]
        )

        normalised = s020.normalise_contract_bar_source(bars, source_name="extra_jd_gap_fetch")

        self.assertEqual(normalised.iloc[0]["date"], pd.Timestamp("2026-03-26"))
        self.assertEqual(normalised.iloc[0]["main_contract_vt"], "jd2605.DCE")
        self.assertEqual(float(normalised.iloc[0]["close_price"]), 3310.0)
        self.assertEqual(normalised.iloc[0]["source"], "extra_jd_gap_fetch")

    def test_build_product_returns_does_not_hide_missing_close_rows(self) -> None:
        mapping = pd.DataFrame(
            [
                {"date": "2026-06-29", "continuous_symbol_vt": "jd.DCE", "main_contract_vt": "jd2706.DCE"},
                {"date": "2026-06-30", "continuous_symbol_vt": "jd.DCE", "main_contract_vt": "jd2706.DCE"},
                {"date": "2026-06-29", "continuous_symbol_vt": "rb.SHFE", "main_contract_vt": "rb2610.SHFE"},
                {"date": "2026-06-30", "continuous_symbol_vt": "rb.SHFE", "main_contract_vt": "rb2610.SHFE"},
            ]
        )
        closes = pd.DataFrame(
            [
                {"date": "2026-06-29", "main_contract_vt": "jd2706.DCE", "close_price": 3200, "source": "stage050_jd_repair"},
                {"date": "2026-06-30", "main_contract_vt": "jd2706.DCE", "close_price": 3280, "source": "stage050_jd_repair"},
                {"date": "2026-06-29", "main_contract_vt": "rb2610.SHFE", "close_price": 3000, "source": "sqlite_db"},
            ]
        )

        product_returns, missing = s020.build_product_returns(mapping, closes)

        self.assertEqual(len(product_returns), 4)
        self.assertEqual(len(missing), 1)
        self.assertEqual(missing.iloc[0]["continuous_symbol_vt"], "rb.SHFE")
        jd_last = product_returns[
            product_returns["product_vt_symbol"].eq("jd.DCE") & product_returns["date"].eq(pd.Timestamp("2026-06-30"))
        ].iloc[0]
        self.assertAlmostEqual(float(jd_last["product_return"]), 0.025)

    def test_assess_coverage_requires_target_date_and_reports_missing_rows(self) -> None:
        product_returns = pd.DataFrame(
            [
                {"date": "2026-06-29", "product_vt_symbol": "a", "main_close": 1.0},
                {"date": "2026-06-29", "product_vt_symbol": "b", "main_close": 1.0},
                {"date": "2026-06-30", "product_vt_symbol": "a", "main_close": 1.0},
                {"date": "2026-06-30", "product_vt_symbol": "b", "main_close": 1.0},
            ]
        )
        missing = pd.DataFrame([{"date": "2026-06-28", "continuous_symbol_vt": "b"}])

        summary = s020.assess_coverage(
            product_returns,
            missing,
            min_valid_products=2,
            target_end_date="2026-06-30",
        )

        self.assertTrue(summary["target_end_min_valid_covered"])
        self.assertEqual(summary["last_date_with_min_valid_products"], "2026-06-30")
        self.assertEqual(summary["missing_close_rows"], 1)
        self.assertEqual(summary["decision"], "stage020_xsmom_inputs_target_covered_with_gaps_keep_readonly")


if __name__ == "__main__":
    unittest.main()
