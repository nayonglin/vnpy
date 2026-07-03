import sys
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "research" / "lines" / "futures_trend_rebuilt_c9_15w_optimization" / "tools"
sys.path.insert(0, str(TOOLS))

from stage050_jd_contract_oi_source_repair import (  # noqa: E402
    build_jd_source_coverage,
    candidate_contract_vt_symbols,
    merge_mapping_rows,
)


class Stage050JdContractOiSourceRepairTest(unittest.TestCase):
    def test_candidate_contract_vt_symbols_cover_gap_and_forward_months(self) -> None:
        symbols = candidate_contract_vt_symbols(
            "jd.DCE",
            pd.Timestamp("2026-03-27"),
            pd.Timestamp("2026-06-30"),
            months_before=1,
            months_after=3,
        )

        self.assertEqual(symbols[0], "jd2602.DCE")
        self.assertIn("jd2605.DCE", symbols)
        self.assertIn("jd2609.DCE", symbols)
        self.assertEqual(symbols[-1], "jd2609.DCE")

    def test_merge_mapping_rows_replaces_overlap_and_extends_dates(self) -> None:
        existing = pd.DataFrame(
            [
                {
                    "date": "2026-04-30",
                    "product": "jd",
                    "exchange": "DCE",
                    "continuous_symbol_tq": "KQ.m@DCE.jd",
                    "continuous_symbol_vt": "jd.DCE",
                    "main_contract_tq": "DCE.jd2606",
                    "main_contract_vt": "jd2606.DCE",
                },
                {
                    "date": "2026-05-01",
                    "product": "jd",
                    "exchange": "DCE",
                    "continuous_symbol_tq": "KQ.m@DCE.jd",
                    "continuous_symbol_vt": "jd.DCE",
                    "main_contract_tq": "",
                    "main_contract_vt": "",
                },
            ]
        )
        fetched = pd.DataFrame(
            [
                {
                    "date": "2026-05-01",
                    "product": "jd",
                    "exchange": "DCE",
                    "continuous_symbol_tq": "KQ.m@DCE.jd",
                    "continuous_symbol_vt": "jd.DCE",
                    "main_contract_tq": "DCE.jd2607",
                    "main_contract_vt": "jd2607.DCE",
                },
                {
                    "date": "2026-05-04",
                    "product": "jd",
                    "exchange": "DCE",
                    "continuous_symbol_tq": "KQ.m@DCE.jd",
                    "continuous_symbol_vt": "jd.DCE",
                    "main_contract_tq": "DCE.jd2607",
                    "main_contract_vt": "jd2607.DCE",
                },
            ]
        )

        merged = merge_mapping_rows(existing, fetched)

        self.assertEqual(len(merged), 3)
        may_first = merged[merged["date"].eq(pd.Timestamp("2026-05-01"))].iloc[0]
        self.assertEqual(may_first["main_contract_vt"], "jd2607.DCE")
        self.assertEqual(str(merged["date"].max().date()), "2026-05-04")

    def test_build_jd_source_coverage_requires_mapping_and_bars_to_target_end(self) -> None:
        mapping = pd.DataFrame(
            [
                {"date": "2026-06-29", "continuous_symbol_vt": "jd.DCE", "main_contract_vt": "jd2608.DCE"},
                {"date": "2026-06-30", "continuous_symbol_vt": "jd.DCE", "main_contract_vt": "jd2608.DCE"},
            ]
        )
        bars = pd.DataFrame(
            [
                {"datetime": "2026-06-29", "contract_vt_symbol": "jd2608.DCE", "open_interest": 100},
                {"datetime": "2026-06-30", "contract_vt_symbol": "jd2608.DCE", "open_interest": 120},
            ]
        )

        coverage = build_jd_source_coverage(mapping, bars, target_end=pd.Timestamp("2026-06-30"))

        self.assertEqual(coverage["mapping_end"], "2026-06-30")
        self.assertEqual(coverage["bar_end"], "2026-06-30")
        self.assertTrue(coverage["mapping_covers_target_end"])
        self.assertTrue(coverage["bars_cover_target_tminus1"])


if __name__ == "__main__":
    unittest.main()
