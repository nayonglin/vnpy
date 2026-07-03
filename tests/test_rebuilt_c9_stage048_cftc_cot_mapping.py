import sys
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "research" / "lines" / "futures_trend_rebuilt_c9_15w_optimization" / "tools"
sys.path.insert(0, str(TOOLS))

from stage048_cftc_cot_mapping_audit import (  # noqa: E402
    ProductCotMapping,
    attach_lagged_cot_features,
    build_cot_signals,
)


class Stage048CftcCotMappingTest(unittest.TestCase):
    def test_cot_signal_is_only_visible_after_release_lag(self) -> None:
        features = pd.DataFrame(
            [
                {
                    "Market_and_Exchange_Names": "SOYBEAN OIL - CHICAGO BOARD OF TRADE",
                    "Report_Date_as_YYYY-MM-DD": pd.Timestamp("2020-01-07"),
                    "available_datetime": pd.Timestamp("2020-01-11 08:00:00"),
                    "cot_directional_component": 0.6,
                    "managed_money_net_oi": 0.1,
                    "managed_money_flow_oi": 0.2,
                    "managed_money_net_z": 1.0,
                    "managed_money_flow_z": 1.2,
                }
            ]
        )
        mappings = (
            ProductCotMapping(
                product_vt_symbol="OI.CZCE",
                cftc_market_name="SOYBEAN OIL - CHICAGO BOARD OF TRADE",
                source_name="CFTC COT Soybean Oil",
                mapping_type="oilseed_proxy",
                confidence=0.60,
            ),
        )
        signals, _ = build_cot_signals(features, mappings)
        entries = pd.DataFrame(
            [
                {"entry_date": "2020-01-10", "product_vt_symbol": "OI.CZCE", "direction": "long"},
                {"entry_date": "2020-01-13", "product_vt_symbol": "OI.CZCE", "direction": "long"},
            ]
        )

        attached = attach_lagged_cot_features(entries, signals, max_signal_age_days=45)

        self.assertFalse(bool(attached.loc[0, "cot_matched"]))
        self.assertTrue(bool(attached.loc[1, "cot_matched"]))
        self.assertEqual(attached.loc[1, "cot_report_date"], pd.Timestamp("2020-01-07"))
        self.assertAlmostEqual(float(attached.loc[1, "cot_external_quality_score"]), 0.6)

    def test_short_direction_flips_cot_quality_score(self) -> None:
        features = pd.DataFrame(
            [
                {
                    "Market_and_Exchange_Names": "COTTON NO. 2 - ICE FUTURES U.S.",
                    "Report_Date_as_YYYY-MM-DD": pd.Timestamp("2020-01-07"),
                    "available_datetime": pd.Timestamp("2020-01-11 08:00:00"),
                    "cot_directional_component": 0.5,
                    "managed_money_net_oi": 0.1,
                    "managed_money_flow_oi": 0.2,
                    "managed_money_net_z": 1.0,
                    "managed_money_flow_z": 1.2,
                }
            ]
        )
        mappings = (
            ProductCotMapping(
                product_vt_symbol="CF.CZCE",
                cftc_market_name="COTTON NO. 2 - ICE FUTURES U.S.",
                source_name="CFTC COT Cotton No.2",
                mapping_type="direct_global_proxy",
                confidence=0.70,
            ),
        )

        signals, _ = build_cot_signals(features, mappings)

        long_score = signals[signals["direction"].eq("long")]["cot_external_quality_score"].iloc[0]
        short_score = signals[signals["direction"].eq("short")]["cot_external_quality_score"].iloc[0]
        self.assertAlmostEqual(float(long_score), 0.5)
        self.assertAlmostEqual(float(short_score), -0.5)


if __name__ == "__main__":
    unittest.main()
