from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = PROJECT_DIR / "research" / "lines" / "futures_trend_rebuilt_c9_15w_v2_optimization" / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage048_current_xsmom_sleeve_rebuild as s048


class Stage048CurrentXsmomSleeveRebuildTest(unittest.TestCase):
    def test_predeclared_specs_are_fixed_current_c9_rebuild_not_parameter_sweep(self) -> None:
        specs = s048.build_predeclared_sleeve_specs()

        self.assertLessEqual(len(specs), 2)
        self.assertEqual(set(specs["source_stage"]), {"Stage020"})
        self.assertEqual(set(specs["cost_bps"]), {10.0})
        self.assertEqual(set(specs["sleeve_capital"]), {15_000.0})
        self.assertTrue(specs["current_c9_only"].all())
        self.assertTrue(specs["no_parameter_sweep"].all())
        self.assertIn("mom_12m_skip1m", set(specs["xsmom_spec"]))

    def test_validate_stage020_inputs_blocks_missing_cost_return(self) -> None:
        satellite = pd.DataFrame(
            {
                "date": ["2020-01-02"],
                "spec": ["mom_12m_skip1m"],
                "active_products": [6],
                "turnover": [0.0],
                "long_products": ["rb.SHFE,MA.CZCE,SA.CZCE"],
                "short_products": ["jd.DCE,AP.CZCE,fu.SHFE"],
            }
        )

        readiness = s048.validate_stage020_sleeve_inputs(satellite, s048.build_predeclared_sleeve_specs())

        self.assertFalse(readiness["ready"])
        self.assertIn("missing_return_column:satellite_return_cost10bps", readiness["blocking_reasons"])

    def test_build_sleeve_curves_resets_independent_nav_per_requested_start(self) -> None:
        c9 = pd.DataFrame(
            {
                "requested_start_month": ["2020-01", "2020-01", "2020-07", "2020-07"],
                "date": ["2020-01-02", "2020-01-03", "2020-07-01", "2020-07-02"],
                "account_equity": [150_000.0, 151_000.0, 150_000.0, 152_000.0],
            }
        )
        satellite = pd.DataFrame(
            {
                "date": ["2020-01-02", "2020-01-03", "2020-07-01", "2020-07-02"],
                "spec": ["mom_12m_skip1m"] * 4,
                "satellite_return_cost10bps": [0.25, 0.10, 0.20, -0.05],
                "gross_exposure": [1.0] * 4,
                "turnover": [0.0, 0.5, 0.0, 0.5],
                "active_products": [6] * 4,
                "long_products": ["rb.SHFE,MA.CZCE,SA.CZCE"] * 4,
                "short_products": ["jd.DCE,AP.CZCE,fu.SHFE"] * 4,
            }
        )
        specs = pd.DataFrame(
            [
                {
                    "variant": "unit_spec",
                    "xsmom_spec": "mom_12m_skip1m",
                    "cost_bps": 10.0,
                    "sleeve_capital": 1_000.0,
                    "source_stage": "Stage020",
                    "current_c9_only": True,
                    "no_parameter_sweep": True,
                }
            ]
        )

        curves = s048.build_current_xsmom_sleeve_curves(c9, satellite, specs)
        variant = curves[curves["variant"].eq("unit_spec")].copy()
        starts = variant.groupby("requested_start_month", sort=True).first()

        self.assertEqual(float(starts.loc["2020-01", "xsmom_nav"]), 1.0)
        self.assertEqual(float(starts.loc["2020-07", "xsmom_nav"]), 1.0)
        self.assertEqual(float(starts.loc["2020-01", "sleeve_pnl_delta"]), 0.0)
        self.assertEqual(float(starts.loc["2020-07", "sleeve_pnl_delta"]), 0.0)
        day2 = variant[variant["date"].eq(pd.Timestamp("2020-01-03"))].iloc[0]
        self.assertAlmostEqual(float(day2["sleeve_pnl_delta"]), 100.0)
        self.assertAlmostEqual(float(day2["account_equity"]), 151_100.0)

    def test_decision_without_objective_pass_is_readonly_not_promoted(self) -> None:
        variant_goal = pd.DataFrame(
            [
                {
                    "variant": "c9_base",
                    "all_gt1y_negative_count": 10,
                    "all_gt1y_min_return_pct": -12.0,
                    "to_final_negative_count": 1,
                    "retention_80pct_pass_count": 1,
                    "retention_rows": 1,
                    "min_retention": 1.0,
                    "objective_pass": 0,
                    "median_total_return_pct": 100.0,
                    "worst_max_drawdown_pct": -50.0,
                },
                {
                    "variant": "unit_spec",
                    "all_gt1y_negative_count": 12,
                    "all_gt1y_min_return_pct": -15.0,
                    "to_final_negative_count": 1,
                    "retention_80pct_pass_count": 1,
                    "retention_rows": 1,
                    "min_retention": 0.95,
                    "objective_pass": 0,
                    "median_total_return_pct": 110.0,
                    "worst_max_drawdown_pct": -52.0,
                },
            ]
        )

        decision = s048.make_stage048_decision(variant_goal, {"ready": True})

        self.assertEqual(decision["decision"], "stage048_current_xsmom_sleeve_not_promoted_keep_readonly")
        self.assertFalse(decision["strategy_rule_created"])
        self.assertFalse(decision["order_api_called"])
        self.assertFalse(decision["ctp_connected"])


if __name__ == "__main__":
    unittest.main()
