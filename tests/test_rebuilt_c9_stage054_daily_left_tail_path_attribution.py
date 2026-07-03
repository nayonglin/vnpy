import sys
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "research" / "lines" / "futures_trend_rebuilt_c9_15w_optimization" / "tools"
sys.path.insert(0, str(TOOLS))

from stage054_daily_left_tail_path_attribution import (  # noqa: E402
    classify_window_positions,
    select_worst_windows_from_stage053_summary,
    summarize_curve_window,
)


class Stage054DailyLeftTailPathAttributionTest(unittest.TestCase):
    def test_selects_top_worst_windows_per_variant_from_stage053_summary(self) -> None:
        summary = pd.DataFrame(
            [
                {
                    "requested_start": "2022-07-15",
                    "variant": "stage013_daily_cold_start_engine",
                    "actual_start": "2022-07-15",
                    "actual_end": "2026-06-30",
                    "min_return_pct": -31.0,
                    "worst_end_date": "2023-07-17",
                },
                {
                    "requested_start": "2022-03-07",
                    "variant": "stage013_daily_cold_start_engine",
                    "actual_start": "2022-03-07",
                    "actual_end": "2026-06-30",
                    "min_return_pct": -35.0,
                    "worst_end_date": "2023-03-08",
                },
                {
                    "requested_start": "2022-07-15",
                    "variant": "stage053_daily_cold_start_contract_oi_share_proxy",
                    "actual_start": "2022-07-15",
                    "actual_end": "2026-06-30",
                    "min_return_pct": -36.0,
                    "worst_end_date": "2023-07-17",
                },
                {
                    "requested_start": "2022-03-07",
                    "variant": "stage053_daily_cold_start_contract_oi_share_proxy",
                    "actual_start": "2022-03-07",
                    "actual_end": "2026-06-30",
                    "min_return_pct": -30.0,
                    "worst_end_date": "2023-03-08",
                },
            ]
        )

        selected = select_worst_windows_from_stage053_summary(summary, top_n_per_variant=1)

        self.assertEqual(selected["variant"].tolist(), [
            "stage013_daily_cold_start_engine",
            "stage053_daily_cold_start_contract_oi_share_proxy",
        ])
        self.assertEqual(selected["requested_start"].tolist(), ["2022-03-07", "2022-07-15"])
        self.assertEqual(selected["window_start_date"].dt.strftime("%Y-%m-%d").tolist(), ["2022-03-07", "2022-07-15"])
        self.assertEqual(selected["window_end_date"].dt.strftime("%Y-%m-%d").tolist(), ["2023-03-08", "2023-07-17"])

    def test_curve_window_uses_variant_equity_and_daily_delta(self) -> None:
        curves = pd.DataFrame(
            [
                {
                    "requested_start": "2022-07-15",
                    "date": "2022-07-15",
                    "account_equity": 200000.0,
                    "stage053_account_equity": 200000.0,
                    "net_pnl": 0.0,
                    "holding_pnl": 0.0,
                    "trading_pnl": 0.0,
                    "commission": 0.0,
                    "slippage": 0.0,
                    "stage053_daily_delta": 0.0,
                    "stage053_drawdown_pct": 0.0,
                    "broker10_margin_to_equity_pct": 20.0,
                },
                {
                    "requested_start": "2022-07-15",
                    "date": "2022-07-16",
                    "account_equity": 199000.0,
                    "stage053_account_equity": 198900.0,
                    "net_pnl": -1000.0,
                    "holding_pnl": -900.0,
                    "trading_pnl": -100.0,
                    "commission": 5.0,
                    "slippage": 10.0,
                    "stage053_daily_delta": -100.0,
                    "stage053_drawdown_pct": -0.55,
                    "broker10_margin_to_equity_pct": 21.0,
                },
                {
                    "requested_start": "2022-07-15",
                    "date": "2022-07-17",
                    "account_equity": 201000.0,
                    "stage053_account_equity": 200800.0,
                    "net_pnl": 2000.0,
                    "holding_pnl": 1800.0,
                    "trading_pnl": 200.0,
                    "commission": 5.0,
                    "slippage": 10.0,
                    "stage053_daily_delta": -100.0,
                    "stage053_drawdown_pct": -0.10,
                    "broker10_margin_to_equity_pct": 19.0,
                },
            ]
        )

        row = summarize_curve_window(
            curves,
            requested_start="2022-07-15",
            variant="stage053_daily_cold_start_contract_oi_share_proxy",
            window_start_date=pd.Timestamp("2022-07-15"),
            window_end_date=pd.Timestamp("2022-07-17"),
        )

        self.assertAlmostEqual(row["start_equity"], 200000.0)
        self.assertAlmostEqual(row["end_equity"], 200800.0)
        self.assertAlmostEqual(row["equity_change"], 800.0)
        self.assertAlmostEqual(row["curve_net_pnl"], 1000.0)
        self.assertAlmostEqual(row["stage053_delta_pnl"], -200.0)
        self.assertAlmostEqual(row["curve_net_plus_stage053_delta"], 800.0)
        self.assertEqual(row["worst_day"], "2022-07-16")

    def test_classifies_positions_existing_vs_opened_after_window_start(self) -> None:
        positions = pd.DataFrame(
            [
                {
                    "requested_start": "2022-07-15",
                    "date": "2022-07-15",
                    "vt_symbol": "rb2210.SHFE",
                    "start_pos": 0,
                    "end_pos": 1,
                    "pos_change": 1,
                    "trade_count": 1,
                    "net_pnl": 0.0,
                    "holding_pnl": 0.0,
                    "trading_pnl": 0.0,
                },
                {
                    "requested_start": "2022-07-15",
                    "date": "2022-07-16",
                    "vt_symbol": "rb2210.SHFE",
                    "start_pos": 1,
                    "end_pos": 1,
                    "pos_change": 0,
                    "trade_count": 0,
                    "net_pnl": -100.0,
                    "holding_pnl": -100.0,
                    "trading_pnl": 0.0,
                },
                {
                    "requested_start": "2022-07-15",
                    "date": "2022-07-16",
                    "vt_symbol": "SM209.CZCE",
                    "start_pos": 0,
                    "end_pos": -1,
                    "pos_change": -1,
                    "trade_count": 1,
                    "net_pnl": -200.0,
                    "holding_pnl": 0.0,
                    "trading_pnl": -200.0,
                },
            ]
        )

        classified = classify_window_positions(
            positions,
            requested_start="2022-07-15",
            window_start_date=pd.Timestamp("2022-07-15"),
            window_end_date=pd.Timestamp("2022-07-16"),
        )

        by_symbol = dict(zip(classified["vt_symbol"], classified["source_bucket"]))
        self.assertEqual(by_symbol["rb2210.SHFE"], "existing_at_window_start")
        self.assertEqual(by_symbol["SM209.CZCE"], "opened_or_traded_after_window_start")
        self.assertEqual(int(classified["existing_contract_count_at_window_start"].max()), 1)


if __name__ == "__main__":
    unittest.main()
