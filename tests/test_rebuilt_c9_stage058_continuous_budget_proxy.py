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


from stage058_continuous_budget_proxy_audit import (  # noqa: E402
    _apply_continuous_budget,
    _compute_quality_score,
    _summarize_budget_proxy,
)


class RebuiltC9Stage058ContinuousBudgetProxyTest(unittest.TestCase):
    def test_compute_quality_score_uses_probability_ai_score_and_rank_score(self) -> None:
        entries = pd.DataFrame(
            [
                {"full_market_probability": 0.9, "ai_score": 0.6, "ai_rank": 1},
                {"full_market_probability": None, "ai_score": 0.5, "ai_rank": 9},
            ]
        )

        score = _compute_quality_score(entries)

        self.assertAlmostEqual(float(score.iloc[0]), (0.9 + 0.6 + 1.0) / 3.0)
        self.assertAlmostEqual(float(score.iloc[1]), (0.5 + (1.0 / 9.0)) / 2.0)

    def test_apply_continuous_budget_reduces_only_budget_above_one_hand(self) -> None:
        entries = pd.DataFrame(
            [
                {"selected_volume": 5, "realized_pnl": 1000.0},
                {"selected_volume": 1, "realized_pnl": -800.0},
            ]
        )
        multipliers = pd.Series([0.5, 0.25], index=entries.index)

        result = _apply_continuous_budget(entries, multipliers, variant="unit_variant", sample_scope="unit")

        self.assertAlmostEqual(float(result.loc[0, "candidate_volume_proxy"]), 3.0)
        self.assertAlmostEqual(float(result.loc[0, "removed_volume_fraction"]), 0.4)
        self.assertAlmostEqual(float(result.loc[0, "removed_pnl_proxy"]), 400.0)
        self.assertAlmostEqual(float(result.loc[0, "candidate_pnl_proxy"]), 600.0)
        self.assertAlmostEqual(float(result.loc[1, "candidate_volume_proxy"]), 1.0)
        self.assertAlmostEqual(float(result.loc[1, "removed_pnl_proxy"]), 0.0)
        self.assertAlmostEqual(float(result.loc[1, "candidate_pnl_proxy"]), -800.0)

    def test_summarize_budget_proxy_tracks_retention_and_pressure_improvement(self) -> None:
        proxy = pd.DataFrame(
            [
                {
                    "sample_scope": "pressure",
                    "variant": "v1",
                    "realized_pnl": -1000.0,
                    "candidate_pnl_proxy": -500.0,
                    "removed_pnl_proxy": -500.0,
                    "budget_multiplier": 0.5,
                    "selected_volume": 5,
                    "candidate_volume_proxy": 3,
                },
                {
                    "sample_scope": "full",
                    "variant": "v1",
                    "realized_pnl": 10000.0,
                    "candidate_pnl_proxy": 9000.0,
                    "removed_pnl_proxy": 1000.0,
                    "budget_multiplier": 0.9,
                    "selected_volume": 5,
                    "candidate_volume_proxy": 4.6,
                },
            ]
        )

        summary = _summarize_budget_proxy(proxy)
        by_scope = summary.set_index("sample_scope")

        self.assertAlmostEqual(float(by_scope.loc["pressure", "candidate_delta_pnl"]), 500.0)
        self.assertAlmostEqual(float(by_scope.loc["full", "pnl_retention_pct"]), 90.0)
        self.assertAlmostEqual(float(by_scope.loc["full", "avg_budget_multiplier"]), 0.9)


if __name__ == "__main__":
    unittest.main()
