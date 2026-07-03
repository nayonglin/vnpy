import sys
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "research" / "lines" / "futures_trend_rebuilt_c9_15w_optimization" / "tools"
sys.path.insert(0, str(TOOLS))

from stage073_term_structure_pit_audit import (  # noqa: E402
    attach_term_structure_features,
    build_term_structure_snapshots,
    infer_contract_maturity,
)


class Stage073TermStructurePitAuditTest(unittest.TestCase):
    def test_infer_contract_maturity_handles_chinese_contract_code_widths(self) -> None:
        self.assertEqual(
            infer_contract_maturity("rb2605", "SHFE", pd.Timestamp("2025-12-01")),
            pd.Timestamp("2026-05-01"),
        )
        self.assertEqual(
            infer_contract_maturity("MA905", "CZCE", pd.Timestamp("2019-01-02")),
            pd.Timestamp("2019-05-01"),
        )
        self.assertEqual(
            infer_contract_maturity("FG101", "CZCE", pd.Timestamp("2020-06-01")),
            pd.Timestamp("2021-01-01"),
        )
        self.assertEqual(
            infer_contract_maturity("SA309", "CZCE", pd.Timestamp("2022-12-01")),
            pd.Timestamp("2023-09-01"),
        )

    def test_build_term_structure_snapshots_uses_maturity_front_next_and_t_plus_one_asof(self) -> None:
        bars = pd.DataFrame(
            [
                {
                    "symbol": "rb2610",
                    "exchange": "SHFE",
                    "datetime": "2026-01-02",
                    "close_price": 100.0,
                    "open_interest": 300,
                },
                {
                    "symbol": "rb2605",
                    "exchange": "SHFE",
                    "datetime": "2026-01-02",
                    "close_price": 103.0,
                    "open_interest": 100,
                },
                {
                    "symbol": "rb2701",
                    "exchange": "SHFE",
                    "datetime": "2026-01-02",
                    "close_price": 96.0,
                    "open_interest": 200,
                },
            ]
        )

        snapshots = build_term_structure_snapshots(bars)

        self.assertEqual(len(snapshots), 1)
        row = snapshots.iloc[0]
        self.assertEqual(row["front_contract_vt_symbol"], "rb2605.SHFE")
        self.assertEqual(row["next_contract_vt_symbol"], "rb2610.SHFE")
        self.assertEqual(row["term_structure_feature_date"], pd.Timestamp("2026-01-02"))
        self.assertEqual(row["term_structure_asof_date"], pd.Timestamp("2026-01-03"))
        self.assertAlmostEqual(float(row["term_structure_backwardation_pct"]), 3.0)
        self.assertEqual(int(row["term_structure_contract_count"]), 3)

    def test_attach_term_structure_features_uses_prior_visible_snapshot_and_directional_alignment(self) -> None:
        bars = pd.DataFrame(
            [
                {
                    "symbol": "rb2605",
                    "exchange": "SHFE",
                    "datetime": "2026-01-02",
                    "close_price": 103.0,
                    "open_interest": 100,
                },
                {
                    "symbol": "rb2610",
                    "exchange": "SHFE",
                    "datetime": "2026-01-02",
                    "close_price": 100.0,
                    "open_interest": 300,
                },
            ]
        )
        snapshots = build_term_structure_snapshots(bars)
        entries = pd.DataFrame(
            [
                {"entry_date": "2026-01-02", "product_vt_symbol": "rb.SHFE", "direction": "long"},
                {"entry_date": "2026-01-03", "product_vt_symbol": "rb.SHFE", "direction": "long"},
                {"entry_date": "2026-01-03", "product_vt_symbol": "rb.SHFE", "direction": "short"},
            ]
        )

        attached = attach_term_structure_features(entries, snapshots, max_feature_age_days=3)

        self.assertFalse(bool(attached.loc[0, "term_structure_matched"]))
        self.assertTrue(bool(attached.loc[1, "term_structure_matched"]))
        self.assertEqual(attached.loc[1, "term_structure_feature_date"], pd.Timestamp("2026-01-02"))
        self.assertEqual(attached.loc[1, "term_structure_asof_date"], pd.Timestamp("2026-01-03"))
        self.assertEqual(int(attached.loc[1, "term_structure_feature_age_days"]), 0)
        self.assertAlmostEqual(float(attached.loc[1, "term_structure_backwardation_pct"]), 3.0)
        self.assertTrue(bool(attached.loc[1, "term_structure_directional_carry_aligned"]))
        self.assertFalse(bool(attached.loc[2, "term_structure_directional_carry_aligned"]))


if __name__ == "__main__":
    unittest.main()
