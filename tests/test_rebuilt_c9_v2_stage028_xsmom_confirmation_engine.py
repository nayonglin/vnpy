from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_DIR / "research" / "lines" / "futures_trend_rebuilt_c9_15w_v2_optimization" / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage028_xsmom_confirmation_add_risk_engine as s028


class Stage028XsmomConfirmationEngineTest(unittest.TestCase):
    def test_product_key_normalizes_contract_to_product_vt_symbol(self) -> None:
        self.assertEqual(s028._stage028_product_key("FG005.CZCE"), "FG.CZCE")
        self.assertEqual(s028._stage028_product_key("FG.CZCE"), "FG.CZCE")
        self.assertEqual(s028._stage028_product_key("jd.DCE"), "jd.DCE")

    def test_prior_xsmom_context_uses_previous_trading_day_not_current_day(self) -> None:
        satellite = pd.DataFrame(
            [
                {
                    "date": "2020-09-01",
                    "spec": "mom_12m_skip1m",
                    "active_products": 6,
                    "long_products": "FG.CZCE,au.SHFE,jm.DCE",
                    "short_products": "AP.CZCE,SA.CZCE,jd.DCE",
                },
                {
                    "date": "2020-09-02",
                    "spec": "mom_12m_skip1m",
                    "active_products": 6,
                    "long_products": "AP.CZCE",
                    "short_products": "FG.CZCE",
                },
            ]
        )
        context = s028._stage028_build_prior_xsmom_context(satellite)

        long_fg = s028._stage028_xsmom_confirmation_fields(
            product_vt_symbol="FG005.CZCE",
            direction="long",
            entry_date=pd.Timestamp("2020-09-02"),
            prior_context=context,
        )
        short_fg = s028._stage028_xsmom_confirmation_fields(
            product_vt_symbol="FG005.CZCE",
            direction="short",
            entry_date=pd.Timestamp("2020-09-02"),
            prior_context=context,
        )
        long_ap = s028._stage028_xsmom_confirmation_fields(
            product_vt_symbol="AP.CZCE",
            direction="long",
            entry_date=pd.Timestamp("2020-09-02"),
            prior_context=context,
        )

        self.assertEqual(long_fg["stage028_xsmom_prior_signal_date"], "2020-09-01")
        self.assertEqual(long_fg["stage028_xsmom_not_opposed"], 1)
        self.assertEqual(long_fg["stage028_xsmom_aligned"], 1)
        self.assertEqual(short_fg["stage028_xsmom_not_opposed"], 0)
        self.assertEqual(short_fg["stage028_xsmom_opposed"], 1)
        self.assertEqual(long_ap["stage028_xsmom_not_opposed"], 0)
        self.assertEqual(long_ap["stage028_xsmom_opposed"], 1)

    def test_prior_xsmom_context_treats_tz_aware_entry_datetime_as_trade_date(self) -> None:
        satellite = pd.DataFrame(
            [
                {
                    "date": "2020-09-01",
                    "spec": "mom_12m_skip1m",
                    "active_products": 6,
                    "long_products": "FG.CZCE,au.SHFE,jm.DCE",
                    "short_products": "AP.CZCE,SA.CZCE,jd.DCE",
                },
                {
                    "date": "2020-09-02",
                    "spec": "mom_12m_skip1m",
                    "active_products": 6,
                    "long_products": "AP.CZCE",
                    "short_products": "FG.CZCE",
                },
            ]
        )
        context = s028._stage028_build_prior_xsmom_context(satellite)

        fields = s028._stage028_xsmom_confirmation_fields(
            product_vt_symbol="FG005.CZCE",
            direction="long",
            entry_date=pd.Timestamp("2020-09-02 00:00:00+08:00"),
            prior_context=context,
        )

        self.assertEqual(fields["stage028_xsmom_prior_signal_date"], "2020-09-01")
        self.assertEqual(fields["stage028_xsmom_not_opposed"], 1)

    def test_xsmom_confirmed_guarded_quality_adds_floor25_integer_risk(self) -> None:
        satellite = pd.DataFrame(
            [
                {
                    "date": "2020-09-01",
                    "spec": "mom_12m_skip1m",
                    "active_products": 6,
                    "long_products": "FG.CZCE,au.SHFE,jm.DCE",
                    "short_products": "AP.CZCE,SA.CZCE,jd.DCE",
                },
                {
                    "date": "2020-09-02",
                    "spec": "mom_12m_skip1m",
                    "active_products": 6,
                    "long_products": "AP.CZCE",
                    "short_products": "FG.CZCE",
                },
            ]
        )
        context = s028._stage028_build_prior_xsmom_context(satellite)

        selected, fields = s028._stage028_apply_xsmom_confirmed_add_risk(
            sizing={"selected_volume": 8, "ai_product_pool_rank": 6, "risk_multiplier": 1},
            direction="long",
            entry_context="flat_entry",
            product_vt_symbol="FG005.CZCE",
            entry_date=pd.Timestamp("2020-09-02"),
            prior_context=context,
            enabled=True,
        )

        self.assertEqual(selected, 10)
        self.assertEqual(fields["stage028_xsmom_add_risk_applied"], 1)
        self.assertEqual(fields["stage028_xsmom_add_risk_added_volume"], 2)
        self.assertEqual(fields["stage028_xsmom_add_risk_reason"], "stage028_xsmom_confirmed_floor25_add_risk")

    def test_xsmom_confirmed_guarded_quality_preserves_failed_conditions(self) -> None:
        satellite = pd.DataFrame(
            [
                {
                    "date": "2020-09-01",
                    "spec": "mom_12m_skip1m",
                    "active_products": 6,
                    "long_products": "FG.CZCE",
                    "short_products": "AP.CZCE",
                },
                {
                    "date": "2020-09-02",
                    "spec": "mom_12m_skip1m",
                    "active_products": 6,
                    "long_products": "AP.CZCE",
                    "short_products": "FG.CZCE",
                },
            ]
        )
        context = s028._stage028_build_prior_xsmom_context(satellite)
        cases = [
            ({"selected_volume": 8, "ai_product_pool_rank": 9, "risk_multiplier": 1}, "long", "FG005.CZCE", "ai_rank_outside_stage028_guarded_band"),
            ({"selected_volume": 8, "ai_product_pool_rank": 6, "risk_multiplier": 2}, "long", "FG005.CZCE", "risk_multiplier_not_below_stage028_floor"),
            ({"selected_volume": 8, "ai_product_pool_rank": 6, "risk_multiplier": 1}, "short", "FG005.CZCE", "xsmom12_opposed_or_inactive"),
            ({"selected_volume": 3, "ai_product_pool_rank": 6, "risk_multiplier": 1}, "long", "FG005.CZCE", "floor25_no_integer_increment"),
            ({"selected_volume": 8, "ai_product_pool_rank": 6, "risk_multiplier": 1}, "long", "FG005.CZCE", "non_flat_entry_context"),
        ]

        for idx, (sizing, direction, symbol, reason) in enumerate(cases):
            with self.subTest(reason=reason):
                entry_context = "regular_add" if idx == 4 else "flat_entry"
                selected, fields = s028._stage028_apply_xsmom_confirmed_add_risk(
                    sizing=sizing,
                    direction=direction,
                    entry_context=entry_context,
                    product_vt_symbol=symbol,
                    entry_date=pd.Timestamp("2020-09-02"),
                    prior_context=context,
                    enabled=True,
                )

                self.assertEqual(selected, int(sizing["selected_volume"]))
                self.assertEqual(fields["stage028_xsmom_add_risk_applied"], 0)
                self.assertEqual(fields["stage028_xsmom_add_risk_reason"], reason)


if __name__ == "__main__":
    unittest.main()
