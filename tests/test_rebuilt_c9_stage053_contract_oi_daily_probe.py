import sys
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "research" / "lines" / "futures_trend_rebuilt_c9_15w_optimization" / "tools"
sys.path.insert(0, str(TOOLS))

from stage053_contract_oi_share_daily_probe import (  # noqa: E402
    _build_proxy_curve,
    _select_probe_start_dates,
    build_contract_oi_lot_deltas,
)


class Stage053ContractOiDailyProbeTest(unittest.TestCase):
    def test_selects_unique_probe_starts_by_stage052_and_stage013_buckets(self) -> None:
        worst = pd.DataFrame(
            [
                {
                    "variant": "stage052_contract_oi_share_ge50_add_risk_proxy",
                    "start_date": "2022-07-15",
                    "end_date": "2023-07-17",
                    "return_pct": -40.0,
                },
                {
                    "variant": "stage052_contract_oi_share_ge50_add_risk_proxy",
                    "start_date": "2022-07-15",
                    "end_date": "2023-07-18",
                    "return_pct": -39.0,
                },
                {
                    "variant": "stage052_contract_oi_share_ge50_add_risk_proxy",
                    "start_date": "2022-07-19",
                    "end_date": "2023-07-20",
                    "return_pct": -38.0,
                },
                {
                    "variant": "stage013_engine",
                    "start_date": "2022-03-07",
                    "end_date": "2023-03-08",
                    "return_pct": -37.0,
                },
                {
                    "variant": "stage013_engine",
                    "start_date": "2022-07-19",
                    "end_date": "2023-07-20",
                    "return_pct": -36.0,
                },
            ]
        )

        selected = _select_probe_start_dates(
            worst,
            bucket_quotas={"stage052_worst": 2, "stage013_worst": 2},
        )

        self.assertEqual(selected["requested_start"].tolist(), ["2022-07-15", "2022-07-19", "2022-03-07"])
        self.assertEqual(selected["requested_start"].nunique(), len(selected))
        self.assertEqual(
            selected["probe_bucket"].value_counts().to_dict(),
            {"stage052_worst": 2, "stage013_worst": 1},
        )

    def test_contract_oi_lot_deltas_rebind_by_entry_date_product_and_contract(self) -> None:
        closed = pd.DataFrame(
            [
                {
                    "requested_start_month": "2022-07-15",
                    "lot_id": "a",
                    "open_trade_id": "new-a",
                    "vt_symbol": "rb2210.SHFE",
                    "product": "rb.SHFE",
                    "direction": "long",
                    "entry_date": "2022-07-20",
                    "exit_date": "2022-08-01",
                    "volume": 1,
                    "realized_pnl": 1000.0,
                },
                {
                    "requested_start_month": "2022-07-15",
                    "lot_id": "b",
                    "open_trade_id": "new-b",
                    "vt_symbol": "rb2210.SHFE",
                    "product": "rb.SHFE",
                    "direction": "long",
                    "entry_date": "2022-07-21",
                    "exit_date": "2022-08-02",
                    "volume": 1,
                    "realized_pnl": 2000.0,
                },
            ]
        )
        snapshots = pd.DataFrame(
            [
                _snapshot("2022-07-19", "2022-07-20", "rb2210.SHFE", 0.65, 1),
                _snapshot("2022-07-20", "2022-07-21", "rb2210.SHFE", 0.42, 2),
            ]
        )

        deltas = build_contract_oi_lot_deltas(closed, snapshots, add_risk_fraction=0.25)

        self.assertEqual(deltas["lot_id"].tolist(), ["a"])
        self.assertEqual(deltas.iloc[0]["open_trade_id"], "new-a")
        self.assertTrue(bool(deltas.iloc[0]["stage053_oi_feature_matched"]))
        self.assertAlmostEqual(float(deltas.iloc[0]["contract_oi_share"]), 0.65)
        self.assertAlmostEqual(float(deltas.iloc[0]["stage053_proxy_delta_pnl"]), 250.0)

    def test_proxy_curve_applies_exit_date_delta(self) -> None:
        curves = pd.DataFrame(
            [
                {"requested_start_month": "2022-07-15", "date": "2022-08-01", "account_equity": 150000.0},
                {"requested_start_month": "2022-07-15", "date": "2022-08-02", "account_equity": 151000.0},
            ]
        )
        lot_deltas = pd.DataFrame(
            [
                {
                    "requested_start_month": "2022-07-15",
                    "exit_date": pd.Timestamp("2022-08-02"),
                    "stage053_proxy_delta_pnl": 250.0,
                }
            ]
        )

        proxy, unmatched = _build_proxy_curve(curves, lot_deltas)

        self.assertEqual(unmatched, 0)
        self.assertEqual(float(proxy.loc[1, "stage053_account_equity"]), 151250.0)
        self.assertEqual(float(proxy.loc[1, "stage053_cum_delta"]), 250.0)


def _snapshot(feature_date: str, asof_date: str, contract: str, share: float, rank: int) -> dict[str, object]:
    return {
        "product_key": "rb.shfe",
        "product_vt_symbol": "rb.SHFE",
        "feature_date": pd.Timestamp(feature_date),
        "asof_date": pd.Timestamp(asof_date),
        "contract_vt_symbol": contract,
        "contract_open_interest": share * 1000.0,
        "product_total_oi": 1000.0,
        "contract_oi_share": share,
        "oi_rank": rank,
        "contract_count": 2,
        "top1_contract_vt": "rb2210.SHFE",
        "top1_oi_share": 0.65,
        "top2_contract_vt": "rb2301.SHFE",
        "top2_oi_share": 0.35,
        "top2_cumulative_oi_share": 1.0,
        "main_contract_vt": "rb2210.SHFE",
        "mapping_main_oi_share": 0.65,
        "contract_is_mapping_main": rank == 1,
        "contract_is_top1_oi": rank == 1,
        "contract_is_top2_oi": True,
        "mapping_main_changed_today": False,
        "days_since_mapping_main_change": 3,
    }


if __name__ == "__main__":
    unittest.main()
