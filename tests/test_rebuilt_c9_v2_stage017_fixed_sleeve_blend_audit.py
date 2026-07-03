from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_DIR / "research" / "lines" / "futures_trend_rebuilt_c9_15w_v2_optimization" / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage017_fixed_sleeve_blend_audit as s017


class Stage017FixedSleeveBlendAuditTest(unittest.TestCase):
    def test_build_fixed_weight_combo_curves_blends_normalized_nav_not_raw_capital(self) -> None:
        c9 = pd.DataFrame(
            [
                {"requested_start_month": "2020-01", "date": "2020-01-02", "account_equity": 150_000.0},
                {"requested_start_month": "2020-01", "date": "2020-01-03", "account_equity": 180_000.0},
            ]
        )
        official = pd.DataFrame(
            [
                {"requested_start_month": "2020-01", "date": "2020-01-02", "account_equity": 200_000.0},
                {"requested_start_month": "2020-01", "date": "2020-01-03", "account_equity": 220_000.0},
            ]
        )

        combo = s017.build_fixed_weight_combo_curves(c9, official, {"c9_70_official_30": 0.70})

        self.assertEqual(combo["variant"].unique().tolist(), ["c9_70_official_30"])
        self.assertAlmostEqual(combo.loc[0, "account_equity"], 150_000.0)
        self.assertAlmostEqual(combo.loc[1, "combo_nav"], 0.70 * 1.20 + 0.30 * 1.10)
        self.assertAlmostEqual(combo.loc[1, "account_equity"], 150_000.0 * (0.70 * 1.20 + 0.30 * 1.10))

    def test_summarize_curve_reports_return_drawdown_and_sharpe_from_equity_path(self) -> None:
        curve = pd.DataFrame(
            [
                {"requested_start_month": "2020-01", "date": "2020-01-02", "account_equity": 100.0},
                {"requested_start_month": "2020-01", "date": "2020-01-03", "account_equity": 120.0},
                {"requested_start_month": "2020-01", "date": "2020-01-04", "account_equity": 90.0},
                {"requested_start_month": "2020-01", "date": "2020-01-05", "account_equity": 150.0},
            ]
        )

        row = s017.summarize_curve(curve, variant="demo", requested_start_month="2020-01")

        self.assertAlmostEqual(row["total_return_pct"], 50.0)
        self.assertAlmostEqual(row["max_drawdown_pct"], -25.0)
        self.assertEqual(row["trading_days"], 4)
        self.assertGreater(row["sharpe"], 0.0)

    def test_legacy_stage372_spec_is_explicit_not_current_live_default(self) -> None:
        metadata = s017.s513._metadata()

        spec = s017._legacy_stage372_spec(metadata)

        self.assertEqual(spec.capital.variant, s017.LEGACY_STAGE372_LIVE_PROFILE_NAME)
        self.assertNotEqual(spec.capital.variant, s017.s660.OFFICIAL_LIVE_PROFILE_NAME)


if __name__ == "__main__":
    unittest.main()
