import sys
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "research" / "lines" / "futures_trend_rebuilt_c9_15w_optimization" / "tools"
sys.path.insert(0, str(TOOLS))

from stage052_contract_oi_share_add_risk_proxy import (  # noqa: E402
    _build_lot_deltas_from_frames,
    _build_proxy_curves,
    _summary,
    select_contract_oi_share_ge50_entries,
)


class Stage052ContractOiProxyTest(unittest.TestCase):
    def test_selector_requires_contract_oi_match_and_share_ge50(self) -> None:
        matrix = pd.DataFrame(
            [
                {"open_trade_id": "A", "contract_oi_matched": True, "contract_oi_share_ge50": True},
                {"open_trade_id": "B", "contract_oi_matched": True, "contract_oi_share_ge50": False},
                {"open_trade_id": "C", "contract_oi_matched": False, "contract_oi_share_ge50": True},
            ]
        )

        selected = select_contract_oi_share_ge50_entries(matrix)

        self.assertEqual(selected["open_trade_id"].tolist(), ["A"])

    def test_lot_deltas_bind_oi_features_by_open_trade(self) -> None:
        closed = pd.DataFrame(
            [
                {
                    "requested_start_month": "2020-01",
                    "lot_id": 1,
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
                    "lot_id": 2,
                    "open_trade_id": "B",
                    "vt_symbol": "rb2005.SHFE",
                    "product": "rb.SHFE",
                    "direction": "long",
                    "entry_date": "2020-01-03",
                    "exit_date": "2020-01-11",
                    "volume": 1,
                    "realized_pnl": 500.0,
                },
            ]
        )
        matrix = pd.DataFrame(
            [
                {
                    "requested_start_month": "2020-01",
                    "open_trade_id": "A",
                    "contract_oi_matched": True,
                    "contract_oi_share_ge50": True,
                    "contract_oi_share": 0.65,
                    "contract_oi_rank": 1,
                    "contract_oi_feature_date": "2020-01-01",
                    "contract_oi_asof_date": "2020-01-02",
                    "contract_oi_feature_age_days": 1,
                },
                {
                    "requested_start_month": "2020-01",
                    "open_trade_id": "B",
                    "contract_oi_matched": True,
                    "contract_oi_share_ge50": False,
                    "contract_oi_share": 0.42,
                    "contract_oi_rank": 2,
                    "contract_oi_feature_date": "2020-01-02",
                    "contract_oi_asof_date": "2020-01-03",
                    "contract_oi_feature_age_days": 1,
                },
            ]
        )

        deltas, audit = _build_lot_deltas_from_frames(closed, matrix)

        self.assertEqual(len(deltas), 1)
        self.assertEqual(deltas.iloc[0]["open_trade_id"], "A")
        self.assertEqual(float(deltas.iloc[0]["stage052_proxy_delta_pnl"]), 250.0)
        self.assertEqual(audit["selected_lots"], 1)

    def test_proxy_curve_applies_exit_date_delta(self) -> None:
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
                    "stage052_proxy_delta_pnl": 250.0,
                }
            ]
        )

        proxy, unmatched = _build_proxy_curves(curves, lot_deltas)

        self.assertEqual(unmatched, 0)
        self.assertEqual(float(proxy.loc[1, "stage052_account_equity"]), 151250.0)
        self.assertEqual(float(proxy.loc[1, "stage052_cum_delta"]), 250.0)

    def test_summary_includes_stage013_and_stage052_variants(self) -> None:
        proxy = pd.DataFrame(
            [
                {
                    "requested_start_month": "2020-01",
                    "date": "2020-01-10",
                    "account_equity": 150000.0,
                    "stage052_account_equity": 150000.0,
                },
                {
                    "requested_start_month": "2020-01",
                    "date": "2020-01-11",
                    "account_equity": 151000.0,
                    "stage052_account_equity": 151250.0,
                },
            ]
        )

        summary = _summary(proxy)

        self.assertEqual(set(summary["variant"]), {"stage013_engine", "stage052_contract_oi_share_ge50_add_risk_proxy"})
        self.assertEqual(len(summary), 2)


if __name__ == "__main__":
    unittest.main()
