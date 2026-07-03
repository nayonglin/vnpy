from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_DIR / "research" / "lines" / "futures_trend_rebuilt_c9_15w_v2_optimization" / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage021_xsmom_non_crowding_overlay_proxy as s021


class Stage021XsmomOverlayProxyTest(unittest.TestCase):
    def test_non_crowding_overlay_adds_satellite_pnl_without_reducing_c9_equity(self) -> None:
        c9 = pd.DataFrame(
            [
                {"requested_start_month": "2020-01", "date": "2020-01-02", "account_equity": 100.0},
                {"requested_start_month": "2020-01", "date": "2020-01-03", "account_equity": 110.0},
                {"requested_start_month": "2020-01", "date": "2020-01-06", "account_equity": 121.0},
            ]
        )
        satellite = pd.DataFrame(
            [
                {"date": "2020-01-02", "spec": "mom_12m_skip1m", "satellite_return_cost10bps": 0.0},
                {"date": "2020-01-03", "spec": "mom_12m_skip1m", "satellite_return_cost10bps": 0.10},
                {"date": "2020-01-06", "spec": "mom_12m_skip1m", "satellite_return_cost10bps": -0.05},
            ]
        )

        curves = s021.build_non_crowding_overlay_curves(
            c9,
            satellite,
            weights=(0.20,),
            specs=("mom_12m_skip1m",),
            cost_bps=10.0,
            capital=100.0,
        )

        base = curves[curves["variant"].eq("c9_base")].sort_values("date")
        overlay = curves[curves["variant"].eq("c9_plus_xsmom_mom_12m_skip1m_w20_cost10bps")].sort_values("date")
        self.assertEqual(base["account_equity"].tolist(), [100.0, 110.0, 121.0])
        self.assertAlmostEqual(overlay.iloc[0]["account_equity"], 100.0)
        self.assertAlmostEqual(overlay.iloc[1]["account_equity"], 112.0)
        self.assertAlmostEqual(overlay.iloc[2]["xsmom_nav"], 1.045)
        self.assertAlmostEqual(overlay.iloc[2]["account_equity"], 121.9)
        self.assertTrue((overlay["c9_account_equity"] == base["account_equity"].to_numpy()).all())

    def test_retention_vs_base_flags_80pct_full_cycle_return_gate(self) -> None:
        summary = pd.DataFrame(
            [
                {"variant": "c9_base", "requested_start_month": "2020-01", "total_return_pct": 100.0},
                {"variant": "candidate_good", "requested_start_month": "2020-01", "total_return_pct": 90.0},
                {"variant": "candidate_bad", "requested_start_month": "2020-01", "total_return_pct": 70.0},
            ]
        )

        retention = s021.retention_vs_base(summary)

        good = retention[retention["variant"].eq("candidate_good")].iloc[0]
        bad = retention[retention["variant"].eq("candidate_bad")].iloc[0]
        self.assertAlmostEqual(good["return_retention_vs_c9"], 0.90)
        self.assertEqual(int(good["passes_80pct_retention"]), 1)
        self.assertAlmostEqual(bad["return_retention_vs_c9"], 0.70)
        self.assertEqual(int(bad["passes_80pct_retention"]), 0)

    def test_goal_audit_uses_dense_gt365_day_windows(self) -> None:
        dates = pd.date_range("2020-01-02", "2021-02-05", freq="B")
        rows = []
        for idx, date in enumerate(dates):
            rows.append(
                {
                    "requested_start_month": "2020-01",
                    "date": date,
                    "variant": "c9_base",
                    "account_equity": 100.0 + idx * 0.01,
                }
            )
            rows.append(
                {
                    "requested_start_month": "2020-01",
                    "date": date,
                    "variant": "candidate",
                    "account_equity": 100.0 - idx * 0.01,
                }
            )
        curves = pd.DataFrame(rows)

        aggregate, _, _, worst = s021.audit_goal_windows(curves)

        candidate = aggregate[
            aggregate["variant"].eq("candidate")
            & aggregate["audit_scope"].eq("all_trading_end_dates_gt_1y")
        ].iloc[0]
        self.assertGreater(int(candidate["window_count"]), 0)
        self.assertGreater(int(candidate["negative_count"]), 0)
        self.assertFalse(worst.empty)


if __name__ == "__main__":
    unittest.main()
