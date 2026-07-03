import sys
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "research" / "lines" / "futures_trend_rebuilt_c9_15w_optimization" / "tools"
sys.path.insert(0, str(TOOLS))

from stage049_contract_oi_migration_audit import (  # noqa: E402
    attach_contract_oi_features,
    build_contract_oi_snapshots,
    contract_product_vt_symbol,
)


class Stage049ContractOiMigrationTest(unittest.TestCase):
    def test_contract_product_vt_symbol_preserves_product_case_by_exchange(self) -> None:
        self.assertEqual(contract_product_vt_symbol("rb2610.SHFE"), "rb.SHFE")
        self.assertEqual(contract_product_vt_symbol("MA609.CZCE"), "MA.CZCE")
        self.assertEqual(contract_product_vt_symbol("jd2601.DCE"), "jd.DCE")

    def test_build_contract_oi_snapshots_ranks_contracts_and_tracks_mapping_main(self) -> None:
        bars = pd.DataFrame(
            [
                {"symbol": "rb2605", "exchange": "SHFE", "datetime": "2026-01-02", "open_interest": 100},
                {"symbol": "rb2610", "exchange": "SHFE", "datetime": "2026-01-02", "open_interest": 300},
                {"symbol": "rb2605", "exchange": "SHFE", "datetime": "2026-01-05", "open_interest": 250},
                {"symbol": "rb2610", "exchange": "SHFE", "datetime": "2026-01-05", "open_interest": 200},
            ]
        )
        mapping = pd.DataFrame(
            [
                {
                    "date": "2026-01-02",
                    "continuous_symbol_vt": "rb.SHFE",
                    "main_contract_vt": "rb2605.SHFE",
                },
                {
                    "date": "2026-01-05",
                    "continuous_symbol_vt": "rb.SHFE",
                    "main_contract_vt": "rb2610.SHFE",
                },
            ]
        )

        snapshots = build_contract_oi_snapshots(bars, mapping)

        first_day_top = snapshots[
            snapshots["feature_date"].eq(pd.Timestamp("2026-01-02"))
            & snapshots["contract_vt_symbol"].eq("rb2610.SHFE")
        ].iloc[0]
        self.assertEqual(int(first_day_top["oi_rank"]), 1)
        self.assertAlmostEqual(float(first_day_top["contract_oi_share"]), 0.75)
        self.assertFalse(bool(first_day_top["contract_is_mapping_main"]))
        self.assertAlmostEqual(float(first_day_top["mapping_main_oi_share"]), 0.25)

        second_day_main = snapshots[
            snapshots["feature_date"].eq(pd.Timestamp("2026-01-05"))
            & snapshots["contract_vt_symbol"].eq("rb2610.SHFE")
        ].iloc[0]
        self.assertTrue(bool(second_day_main["mapping_main_changed_today"]))
        self.assertEqual(int(second_day_main["days_since_mapping_main_change"]), 0)

    def test_attach_contract_oi_features_uses_prior_visible_snapshot_only(self) -> None:
        bars = pd.DataFrame(
            [
                {"symbol": "rb2605", "exchange": "SHFE", "datetime": "2026-01-02", "open_interest": 100},
                {"symbol": "rb2610", "exchange": "SHFE", "datetime": "2026-01-02", "open_interest": 300},
            ]
        )
        mapping = pd.DataFrame(
            [
                {
                    "date": "2026-01-02",
                    "continuous_symbol_vt": "rb.SHFE",
                    "main_contract_vt": "rb2605.SHFE",
                }
            ]
        )
        snapshots = build_contract_oi_snapshots(bars, mapping)
        entries = pd.DataFrame(
            [
                {"entry_date": "2026-01-02", "product_vt_symbol": "rb.SHFE", "vt_symbol": "rb2610.SHFE"},
                {"entry_date": "2026-01-03", "product_vt_symbol": "rb.SHFE", "vt_symbol": "rb2610.SHFE"},
            ]
        )

        attached = attach_contract_oi_features(entries, snapshots, max_feature_age_days=3)

        self.assertFalse(bool(attached.loc[0, "contract_oi_matched"]))
        self.assertTrue(bool(attached.loc[1, "contract_oi_matched"]))
        self.assertEqual(attached.loc[1, "contract_oi_feature_date"], pd.Timestamp("2026-01-02"))
        self.assertEqual(attached.loc[1, "contract_oi_asof_date"], pd.Timestamp("2026-01-03"))
        self.assertAlmostEqual(float(attached.loc[1, "contract_oi_share"]), 0.75)


if __name__ == "__main__":
    unittest.main()
