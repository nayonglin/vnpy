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


from stage061_oi_confirmed_reverse_budget_proxy import (  # noqa: E402
    _apply_oi_confirmed_reverse_budget,
    _evaluate_oi_reverse_budget,
    _summarize_oi_reverse_budget,
)


class RebuiltC9Stage061OiConfirmedReverseBudgetProxyTest(unittest.TestCase):
    def test_apply_oi_confirmed_cap_keeps_one_hand_and_leaves_other_rows_unchanged(self) -> None:
        entries = pd.DataFrame(
            [
                {"oi_confirmed": True, "selected_volume": 5, "realized_pnl": -1000.0},
                {"oi_confirmed": False, "selected_volume": 5, "realized_pnl": 1000.0},
                {"oi_confirmed": True, "selected_volume": 1, "realized_pnl": -500.0},
            ]
        )

        result = _apply_oi_confirmed_reverse_budget(entries, variant="oi_cap_to_one", sample_scope="unit")

        self.assertAlmostEqual(float(result.loc[0, "candidate_volume_proxy"]), 1.0)
        self.assertAlmostEqual(float(result.loc[0, "removed_volume_fraction"]), 0.8)
        self.assertAlmostEqual(float(result.loc[0, "removed_pnl_proxy"]), -800.0)
        self.assertAlmostEqual(float(result.loc[0, "candidate_pnl_proxy"]), -200.0)
        self.assertTrue(bool(result.loc[0, "oi_reverse_budget_applied"]))
        self.assertAlmostEqual(float(result.loc[1, "candidate_volume_proxy"]), 5.0)
        self.assertAlmostEqual(float(result.loc[1, "candidate_pnl_proxy"]), 1000.0)
        self.assertFalse(bool(result.loc[1, "oi_reverse_budget_applied"]))
        self.assertAlmostEqual(float(result.loc[2, "candidate_volume_proxy"]), 1.0)
        self.assertAlmostEqual(float(result.loc[2, "candidate_pnl_proxy"]), -500.0)

    def test_summarize_tracks_retention_and_removed_positive_negative_pnl(self) -> None:
        proxy = pd.DataFrame(
            [
                {
                    "sample_scope": "full",
                    "variant": "oi_cap_to_one",
                    "realized_pnl": 10000.0,
                    "candidate_pnl_proxy": 9000.0,
                    "removed_pnl_proxy": 1000.0,
                    "selected_volume": 5,
                    "candidate_volume_proxy": 1,
                    "oi_reverse_budget_applied": True,
                },
                {
                    "sample_scope": "pressure",
                    "variant": "oi_cap_to_one",
                    "realized_pnl": -1000.0,
                    "candidate_pnl_proxy": -200.0,
                    "removed_pnl_proxy": -800.0,
                    "selected_volume": 5,
                    "candidate_volume_proxy": 1,
                    "oi_reverse_budget_applied": True,
                },
                {
                    "sample_scope": "target_late_adverse",
                    "variant": "oi_cap_to_one",
                    "realized_pnl": -500.0,
                    "candidate_pnl_proxy": -100.0,
                    "removed_pnl_proxy": -400.0,
                    "selected_volume": 5,
                    "candidate_volume_proxy": 1,
                    "oi_reverse_budget_applied": True,
                },
            ]
        )

        summary = _summarize_oi_reverse_budget(proxy)
        by_scope = summary.set_index("sample_scope")

        self.assertAlmostEqual(float(by_scope.loc["full", "pnl_retention_pct"]), 90.0)
        self.assertAlmostEqual(float(by_scope.loc["full", "removed_positive_pnl_proxy"]), 1000.0)
        self.assertAlmostEqual(float(by_scope.loc["pressure", "candidate_delta_pnl"]), 800.0)
        self.assertAlmostEqual(float(by_scope.loc["pressure", "loss_reduction_pct"]), 80.0)
        self.assertAlmostEqual(float(by_scope.loc["target_late_adverse", "candidate_delta_pnl"]), 400.0)

    def test_evaluate_requires_full_retention_pressure_improvement_and_target_improvement(self) -> None:
        summary = pd.DataFrame(
            [
                {
                    "sample_scope": "full",
                    "variant": "oi_cap_to_one",
                    "pnl_retention_pct": 90.0,
                    "candidate_delta_pnl": -1000.0,
                },
                {
                    "sample_scope": "pressure",
                    "variant": "oi_cap_to_one",
                    "pnl_retention_pct": None,
                    "candidate_delta_pnl": 800.0,
                },
                {
                    "sample_scope": "target_late_adverse",
                    "variant": "oi_cap_to_one",
                    "pnl_retention_pct": None,
                    "candidate_delta_pnl": 400.0,
                },
            ]
        )

        evaluation = _evaluate_oi_reverse_budget(summary)
        row = evaluation.iloc[0]

        self.assertTrue(bool(row["passes_proxy_gate"]))
        self.assertAlmostEqual(float(row["full_pnl_retention_pct"]), 90.0)
        self.assertAlmostEqual(float(row["pressure_candidate_delta_pnl"]), 800.0)
        self.assertAlmostEqual(float(row["target_candidate_delta_pnl"]), 400.0)


if __name__ == "__main__":
    unittest.main()
