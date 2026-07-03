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


from stage075_staggered_sleeve_deployment_proxy import (  # noqa: E402
    apply_staggered_sleeve_deployment_to_equity,
    compute_staggered_sleeve_multiplier,
    run_dense_staggered_goal_audit,
)


class RebuiltC9Stage075StaggeredSleeveDeploymentTest(unittest.TestCase):
    def test_compute_multiplier_is_stepwise_active_sleeve_share(self) -> None:
        multiplier = compute_staggered_sleeve_multiplier(5, sleeve_offsets=(0, 2))

        self.assertEqual(multiplier.tolist(), [0.50, 0.50, 1.0, 1.0, 1.0])

    def test_apply_staggered_deployment_keeps_initial_equity_and_scales_daily_pnl(self) -> None:
        equity = pd.Series([100.0, 80.0, 120.0, 140.0, 100.0])

        result = apply_staggered_sleeve_deployment_to_equity(equity, sleeve_offsets=(0, 2))

        self.assertEqual(result.tolist(), [100.0, 90.0, 130.0, 150.0, 110.0])

    def test_dense_audit_resets_sleeves_for_each_candidate_start_date(self) -> None:
        curves = pd.DataFrame(
            [
                {"variant": "base", "requested_start_month": "2020-01", "date": "2020-01-01", "equity": 100.0},
                {"variant": "base", "requested_start_month": "2020-01", "date": "2020-01-02", "equity": 80.0},
                {"variant": "base", "requested_start_month": "2020-01", "date": "2020-01-03", "equity": 120.0},
                {"variant": "base", "requested_start_month": "2020-01", "date": "2020-01-04", "equity": 100.0},
            ]
        )

        aggregate, _worst = run_dense_staggered_goal_audit(
            curves,
            target_variants=["base"],
            sleeve_offsets=(0, 2),
            objective_start_min=pd.Timestamp("2020-01-01"),
            objective_start_max=pd.Timestamp("2020-01-02"),
            min_period_calendar_days=1,
            worst_per_start=2,
        )

        row = aggregate[
            aggregate["variant"].eq("base_staggered_sleeve")
            & aggregate["audit_scope"].eq("all_trading_end_dates_gt_1y")
        ].iloc[0]
        self.assertEqual(int(row["window_count"]), 5)
        self.assertEqual(int(row["negative_count"]), 1)
        self.assertAlmostEqual(float(row["min_return_pct"]), -10.0)


if __name__ == "__main__":
    unittest.main()
