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


from stage072_q90_vol_overlay_proxy import (  # noqa: E402
    OVERLAY_FLOOR,
    apply_multiplier_to_equity,
    build_overlay_panel_from_frames,
    compute_q90_vol_multiplier,
)


class RebuiltC9Stage072Q90VolOverlayProxyTest(unittest.TestCase):
    def test_compute_q90_vol_multiplier_is_point_in_time_and_floored(self) -> None:
        equity = pd.Series(
            [
                100.0,
                101.0,
                100.0,
                101.0,
                100.0,
                101.0,
                100.0,
                160.0,
            ]
        )

        multiplier = compute_q90_vol_multiplier(
            equity,
            lookback=3,
            min_periods=2,
            quantile=0.50,
            min_history=2,
            floor=0.50,
        )

        self.assertEqual(multiplier.iloc[0], 1.0)
        self.assertEqual(multiplier.iloc[-1], 1.0)
        self.assertGreaterEqual(float(multiplier.min()), 0.50)
        self.assertLess(float(multiplier.iloc[-2]), 1.0)

    def test_apply_multiplier_to_equity_scales_next_pnl_not_starting_equity(self) -> None:
        equity = pd.Series([100.0, 110.0, 90.0, 120.0])
        multiplier = pd.Series([1.0, 0.5, 0.25, 1.0])

        result = apply_multiplier_to_equity(equity, multiplier)

        self.assertEqual(result.tolist(), [100.0, 105.0, 100.0, 130.0])

    def test_build_overlay_panel_adds_base_and_overlay_variants(self) -> None:
        panel = pd.DataFrame(
            [
                {"variant": "stage013_engine", "requested_start_month": "2020-01", "date": "2020-01-01", "equity": 100.0},
                {"variant": "stage013_engine", "requested_start_month": "2020-01", "date": "2020-01-02", "equity": 110.0},
                {"variant": "target", "requested_start_month": "2020-01", "date": "2020-01-01", "equity": 100.0},
                {"variant": "target", "requested_start_month": "2020-01", "date": "2020-01-02", "equity": 90.0},
            ]
        )

        result = build_overlay_panel_from_frames(panel, target_variants=["target"], overlay_suffix="_q90")

        self.assertEqual(set(result["variant"]), {"stage013_engine", "target", "target_q90"})
        overlay = result[result["variant"].eq("target_q90")].sort_values("date")
        self.assertEqual(overlay["equity"].tolist(), [100.0, 90.0])
        self.assertTrue((overlay["stage072_vol_multiplier"] <= 1.0).all())
        self.assertGreaterEqual(float(overlay["stage072_vol_multiplier"].min()), OVERLAY_FLOOR)


if __name__ == "__main__":
    unittest.main()
