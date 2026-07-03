import sys
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "research" / "lines" / "futures_trend_rebuilt_c9_15w_optimization" / "tools"
sys.path.insert(0, str(TOOLS))

from stage051_contract_oi_repaired_rerun import (  # noqa: E402
    decide_repaired_contract_oi,
    merge_repaired_jd_bars,
    merge_repaired_jd_mapping,
)


class Stage051RepairedContractOiTest(unittest.TestCase):
    def test_merge_repaired_jd_bars_replaces_gap_period_only(self) -> None:
        base = pd.DataFrame(
            [
                {"symbol": "jd2603", "exchange": "DCE", "datetime": "2026-03-26", "open_interest": 10},
                {"symbol": "jd2604", "exchange": "DCE", "datetime": "2026-03-27", "open_interest": 1},
                {"symbol": "rb2610", "exchange": "SHFE", "datetime": "2026-03-27", "open_interest": 99},
            ]
        )
        repair = pd.DataFrame(
            [
                {"symbol": "jd2604", "exchange": "DCE", "datetime": "2026-03-27", "open_interest": 30},
                {"symbol": "jd2605", "exchange": "DCE", "datetime": "2026-03-28", "open_interest": 40},
            ]
        )

        merged = merge_repaired_jd_bars(base, repair, repair_start=pd.Timestamp("2026-03-27"))

        self.assertEqual(len(merged), 4)
        old_gap = merged[merged["symbol"].eq("jd2604") & merged["datetime"].eq(pd.Timestamp("2026-03-27"))]
        self.assertEqual(float(old_gap.iloc[0]["open_interest"]), 30.0)
        self.assertEqual(old_gap.iloc[0]["feature_date"], pd.Timestamp("2026-03-27"))
        self.assertEqual(old_gap.iloc[0]["product_vt_symbol"], "jd.DCE")
        self.assertEqual(old_gap.iloc[0]["product_key"], "jd.dce")
        self.assertTrue((merged["symbol"].eq("jd2603") & merged["datetime"].eq(pd.Timestamp("2026-03-26"))).any())
        self.assertTrue(merged["symbol"].eq("rb2610").any())

    def test_merge_repaired_jd_mapping_replaces_all_jd_rows_with_repair(self) -> None:
        base = pd.DataFrame(
            [
                {"date": "2026-06-30", "continuous_symbol_vt": "jd.DCE", "main_contract_vt": ""},
                {"date": "2026-06-30", "continuous_symbol_vt": "rb.SHFE", "main_contract_vt": "rb2610.SHFE"},
            ]
        )
        repair = pd.DataFrame(
            [
                {"date": "2026-06-30", "continuous_symbol_vt": "jd.DCE", "main_contract_vt": "jd2608.DCE"},
            ]
        )

        merged = merge_repaired_jd_mapping(base, repair)

        self.assertEqual(len(merged), 2)
        jd = merged[merged["continuous_symbol_vt"].eq("jd.DCE")].iloc[0]
        self.assertEqual(jd["main_contract_vt"], "jd2608.DCE")
        self.assertEqual(jd["product_key"], "jd.dce")
        self.assertEqual(jd["product_vt_symbol"], "jd.DCE")
        self.assertTrue(merged["continuous_symbol_vt"].eq("rb.SHFE").any())

    def test_decide_repaired_contract_oi_promotes_only_when_stable_and_no_source_gap(self) -> None:
        decision = decide_repaired_contract_oi(
            stable_conditions=["contract_oi_share_ge50"],
            matched_rate=1.0,
            source_gap_products=[],
        )

        self.assertEqual(decision, "stage051_contract_oi_migration_source_gap_cleared_ready_for_proxy")


if __name__ == "__main__":
    unittest.main()
