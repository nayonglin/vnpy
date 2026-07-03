import sys
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "research" / "lines" / "futures_trend_rebuilt_c9_15w_optimization" / "tools"
sys.path.insert(0, str(TOOLS))

from stage039_full_market_ai_top8_proxy import (  # noqa: E402
    _build_proxy_curves,
    attach_predictions_to_lots,
    select_ai_top8_lots,
)


class Stage039FullMarketAiTop8ProxyTest(unittest.TestCase):
    def test_prediction_join_never_uses_future_eval_date(self) -> None:
        lots = pd.DataFrame(
            [
                {
                    "entry_date": "2022-01-15",
                    "product": "rb.SHFE",
                    "vt_symbol": "rb2205.SHFE",
                    "realized_pnl": 100.0,
                }
            ]
        )
        predictions = pd.DataFrame(
            [
                {
                    "eval_date": "2021-12-31",
                    "product_vt_symbol": "rb.SHFE",
                    "ai_rank_desc": 5,
                    "stage021_ai_top8": True,
                    "stage021_simple_top8": False,
                },
                {
                    "eval_date": "2022-01-31",
                    "product_vt_symbol": "rb.SHFE",
                    "ai_rank_desc": 1,
                    "stage021_ai_top8": True,
                    "stage021_simple_top8": True,
                },
            ]
        )

        attached = attach_predictions_to_lots(lots, predictions)

        self.assertEqual(attached.loc[0, "eval_date"], pd.Timestamp("2021-12-31"))
        self.assertEqual(attached.loc[0, "ai_rank_desc"], 5)

    def test_ai_top8_selector_does_not_require_simple_top8_consensus(self) -> None:
        lots = pd.DataFrame(
            [
                {"stage021_ai_top8": True, "stage021_simple_top8": False, "realized_pnl": 10.0},
                {"stage021_ai_top8": False, "stage021_simple_top8": True, "realized_pnl": 20.0},
            ]
        )

        selected = select_ai_top8_lots(lots)

        self.assertEqual(len(selected), 1)
        self.assertEqual(float(selected.iloc[0]["realized_pnl"]), 10.0)

    def test_proxy_curve_applies_exit_date_delta_without_unmatched_error(self) -> None:
        curves = pd.DataFrame(
            [
                {"requested_start_month": "2020-01", "date": "2020-01-10", "account_equity": 150000.0},
                {"requested_start_month": "2020-01", "date": "2020-01-15", "account_equity": 151000.0},
            ]
        )
        lot_deltas = pd.DataFrame(
            [
                {
                    "requested_start_month": "2020-01",
                    "exit_date": pd.Timestamp("2020-01-15"),
                    "stage039_proxy_delta_pnl": 250.0,
                }
            ]
        )

        proxy, unmatched = _build_proxy_curves(curves, lot_deltas)

        self.assertEqual(unmatched, 0)
        self.assertEqual(float(proxy.loc[1, "stage039_account_equity"]), 151250.0)


if __name__ == "__main__":
    unittest.main()
