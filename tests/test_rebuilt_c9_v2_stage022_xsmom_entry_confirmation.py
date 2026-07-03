from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_DIR / "research" / "lines" / "futures_trend_rebuilt_c9_15w_v2_optimization" / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage022_xsmom_entry_confirmation_proxy as s022


class Stage022XsmomEntryConfirmationTest(unittest.TestCase):
    def test_attach_prior_xsmom_context_uses_previous_trading_day_not_entry_day(self) -> None:
        events = pd.DataFrame(
            [
                {
                    "entry_date": "2020-01-03",
                    "product": "rb.SHFE",
                    "direction": "long",
                    "ai_product_pool_rank": 3,
                    "selected_volume": 2,
                    "risk_multiplier": 1,
                },
                {
                    "entry_date": "2020-01-03",
                    "product": "au.SHFE",
                    "direction": "long",
                    "ai_product_pool_rank": 3,
                    "selected_volume": 2,
                    "risk_multiplier": 1,
                },
            ]
        )
        satellite = pd.DataFrame(
            [
                {"date": "2020-01-02", "spec": "mom_12m_skip1m", "active_products": 6, "long_products": "rb.SHFE", "short_products": ""},
                {"date": "2020-01-03", "spec": "mom_12m_skip1m", "active_products": 6, "long_products": "au.SHFE", "short_products": ""},
            ]
        )

        tagged = s022.attach_prior_xsmom_context(events, satellite, specs=("mom_12m_skip1m",))

        self.assertEqual(tagged.loc[0, "xsmom12_prior_signal_date"], "2020-01-02")
        self.assertEqual(int(tagged.loc[0, "xsmom12_aligned"]), 1)
        self.assertEqual(int(tagged.loc[1, "xsmom12_aligned"]), 0)
        self.assertEqual(int(tagged.loc[1, "xsmom12_opposed"]), 0)

    def test_build_condition_lot_deltas_selects_quality_and_alignment(self) -> None:
        tagged = pd.DataFrame(
            [
                {
                    "requested_start_month": "2020-01",
                    "entry_date": "2020-01-03",
                    "exit_date": "2020-01-10",
                    "product": "rb.SHFE",
                    "direction": "long",
                    "realized_pnl": 1000.0,
                    "ai_product_pool_rank": 3,
                    "selected_volume": 2,
                    "risk_multiplier": 1,
                    "xsmom12_aligned": 1,
                    "xsmom12_active": 1,
                    "xsmom12_opposed": 0,
                },
                {
                    "requested_start_month": "2020-01",
                    "entry_date": "2020-01-04",
                    "exit_date": "2020-01-11",
                    "product": "au.SHFE",
                    "direction": "long",
                    "realized_pnl": 2000.0,
                    "ai_product_pool_rank": 3,
                    "selected_volume": 2,
                    "risk_multiplier": 1,
                    "xsmom12_aligned": 0,
                    "xsmom12_active": 1,
                    "xsmom12_opposed": 0,
                },
                {
                    "requested_start_month": "2020-01",
                    "entry_date": "2020-01-05",
                    "exit_date": "2020-01-12",
                    "product": "FG.CZCE",
                    "direction": "short",
                    "realized_pnl": 3000.0,
                    "ai_product_pool_rank": 10,
                    "selected_volume": 2,
                    "risk_multiplier": 1,
                    "xsmom12_aligned": 1,
                    "xsmom12_active": 1,
                    "xsmom12_opposed": 0,
                },
            ]
        )

        lot_deltas = s022.build_condition_lot_deltas(tagged, {"quality_xsmom12_aligned": tagged["xsmom12_aligned"].eq(1)})

        self.assertEqual(lot_deltas["condition"].unique().tolist(), ["quality_xsmom12_aligned"])
        self.assertEqual(len(lot_deltas), 1)
        self.assertAlmostEqual(float(lot_deltas.iloc[0]["stage022_proxy_delta_pnl"]), 250.0)

    def test_build_proxy_curves_applies_delta_on_exit_date_and_carries_forward(self) -> None:
        base = pd.DataFrame(
            [
                {"requested_start_month": "2020-01", "date": "2020-01-02", "account_equity": 100.0},
                {"requested_start_month": "2020-01", "date": "2020-01-03", "account_equity": 101.0},
                {"requested_start_month": "2020-01", "date": "2020-01-06", "account_equity": 102.0},
            ]
        )
        lot_deltas = pd.DataFrame(
            [
                {
                    "condition": "demo",
                    "requested_start_month": "2020-01",
                    "exit_date": "2020-01-03",
                    "stage022_proxy_delta_pnl": 10.0,
                }
            ]
        )

        curves, unmatched = s022.build_proxy_curves(base, lot_deltas)

        candidate = curves[curves["variant"].eq("stage022_demo")].sort_values("date")
        self.assertEqual(unmatched, 0)
        self.assertEqual(candidate["account_equity"].tolist(), [100.0, 111.0, 112.0])

    def test_retention_vs_base_excludes_starts_outside_objective_or_under_one_year(self) -> None:
        summary = pd.DataFrame(
            [
                {
                    "variant": "stage013_engine",
                    "condition": "stage013_engine",
                    "requested_start_month": "2025-01",
                    "start_date": "2025-01-02",
                    "end_date": "2026-06-30",
                    "total_return_pct": 100.0,
                },
                {
                    "variant": "stage022_demo",
                    "condition": "demo",
                    "requested_start_month": "2025-01",
                    "start_date": "2025-01-02",
                    "end_date": "2026-06-30",
                    "total_return_pct": 90.0,
                },
                {
                    "variant": "stage013_engine",
                    "condition": "stage013_engine",
                    "requested_start_month": "2026-01",
                    "start_date": "2026-01-02",
                    "end_date": "2026-06-30",
                    "total_return_pct": 100.0,
                },
                {
                    "variant": "stage022_demo",
                    "condition": "demo",
                    "requested_start_month": "2026-01",
                    "start_date": "2026-01-02",
                    "end_date": "2026-06-30",
                    "total_return_pct": 1.0,
                },
            ]
        )

        retention = s022.retention_vs_base(summary)

        self.assertEqual(retention["requested_start_month"].unique().tolist(), ["2025-01"])
        row = retention[retention["variant"].eq("stage022_demo")].iloc[0]
        self.assertAlmostEqual(float(row["return_retention_vs_base"]), 0.9)
        self.assertEqual(int(row["passes_80pct_retention"]), 1)


if __name__ == "__main__":
    unittest.main()
