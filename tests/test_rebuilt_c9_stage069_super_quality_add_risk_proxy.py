from __future__ import annotations

from pathlib import Path
import sys
import unittest

import pandas as pd


TOOLS_DIR = (
    Path(__file__).resolve().parents[1]
    / "research"
    / "lines"
    / "futures_trend_rebuilt_c9_15w_optimization"
    / "tools"
)
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


from stage069_super_quality_add_risk_proxy import (  # noqa: E402
    _build_lot_deltas_from_frames,
    _build_proxy_curves,
    _summary,
    select_super_quality_open_trades,
)


class RebuiltC9Stage069SuperQualityAddRiskProxyTest(unittest.TestCase):
    def test_selector_requires_full_market_ai_top8_and_account_injured(self) -> None:
        matrix = pd.DataFrame(
            [
                {"open_trade_id": "A", "full_market_ai_top8": True, "account_injured": True},
                {"open_trade_id": "B", "full_market_ai_top8": True, "account_injured": False},
                {"open_trade_id": "C", "full_market_ai_top8": False, "account_injured": True},
            ]
        )

        selected = select_super_quality_open_trades(matrix)

        self.assertEqual(selected["open_trade_id"].tolist(), ["A"])

    def test_lot_deltas_bind_stage038_features_by_open_trade(self) -> None:
        closed = pd.DataFrame(
            [
                {
                    "requested_start_month": "2020-01",
                    "lot_id": "lot1",
                    "open_trade_id": "A",
                    "vt_symbol": "rb2005.SHFE",
                    "product": "rb.SHFE",
                    "direction": "long",
                    "entry_date": "2020-01-02",
                    "exit_date": "2020-01-10",
                    "volume": 2,
                    "realized_pnl": 1000.0,
                },
                {
                    "requested_start_month": "2020-01",
                    "lot_id": "lot2",
                    "open_trade_id": "B",
                    "vt_symbol": "MA005.CZCE",
                    "product": "MA.CZCE",
                    "direction": "short",
                    "entry_date": "2020-01-03",
                    "exit_date": "2020-01-11",
                    "volume": 1,
                    "realized_pnl": -500.0,
                },
            ]
        )
        matrix = pd.DataFrame(
            [
                {
                    "requested_start_month": "2020-01",
                    "open_trade_id": "A",
                    "full_market_ai_top8": True,
                    "account_injured": True,
                    "ai_rank_1_6": True,
                    "stage038_oos_fold": "fold_02",
                },
                {
                    "requested_start_month": "2020-01",
                    "open_trade_id": "B",
                    "full_market_ai_top8": True,
                    "account_injured": False,
                    "ai_rank_1_6": True,
                    "stage038_oos_fold": "fold_02",
                },
            ]
        )

        deltas, audit = _build_lot_deltas_from_frames(closed, matrix)

        self.assertEqual(len(deltas), 1)
        self.assertEqual(deltas.iloc[0]["open_trade_id"], "A")
        self.assertAlmostEqual(float(deltas.iloc[0]["stage069_proxy_delta_pnl"]), 250.0)
        self.assertEqual(audit["selected_lots"], 1)
        self.assertEqual(audit["selected_open_trades"], 1)

    def test_proxy_curve_applies_delta_on_exit_date(self) -> None:
        curves = pd.DataFrame(
            [
                {"requested_start_month": "2020-01", "date": "2020-01-10", "account_equity": 150000.0},
                {"requested_start_month": "2020-01", "date": "2020-01-11", "account_equity": 151000.0},
            ]
        )
        lot_deltas = pd.DataFrame(
            [
                {
                    "requested_start_month": "2020-01",
                    "exit_date": pd.Timestamp("2020-01-11"),
                    "stage069_proxy_delta_pnl": 250.0,
                }
            ]
        )

        proxy, unmatched = _build_proxy_curves(curves, lot_deltas)

        self.assertEqual(unmatched, 0)
        self.assertAlmostEqual(float(proxy.loc[1, "stage069_account_equity"]), 151250.0)
        self.assertAlmostEqual(float(proxy.loc[1, "stage069_cum_delta"]), 250.0)

    def test_summary_includes_stage013_and_stage069_variants(self) -> None:
        proxy = pd.DataFrame(
            [
                {
                    "requested_start_month": "2020-01",
                    "date": "2020-01-10",
                    "account_equity": 150000.0,
                    "stage069_account_equity": 150000.0,
                },
                {
                    "requested_start_month": "2020-01",
                    "date": "2020-01-11",
                    "account_equity": 151000.0,
                    "stage069_account_equity": 151250.0,
                },
            ]
        )

        summary = _summary(proxy)

        self.assertEqual(set(summary["variant"]), {"stage013_engine", "stage069_super_quality_add_risk_proxy"})


if __name__ == "__main__":
    unittest.main()
