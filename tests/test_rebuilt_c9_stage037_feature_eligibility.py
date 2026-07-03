import unittest
from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "research" / "lines" / "futures_trend_rebuilt_c9_15w_optimization" / "tools"
sys.path.insert(0, str(TOOLS))

from stage037_feature_eligibility_audit import (  # noqa: E402
    classify_feature_status,
    summarize_forward_ledger,
    summarize_jd_full_market,
)


class Stage037FeatureEligibilityTest(unittest.TestCase):
    def test_post_entry_feature_is_confirmation_only(self) -> None:
        result = classify_feature_status(
            point_in_time=True,
            history_ready=True,
            forward_ready=True,
            post_entry_only=True,
        )

        self.assertEqual(result["eligibility"], "post_entry_confirmation_only")
        self.assertFalse(result["history_selector_allowed"])
        self.assertIn("开仓后", result["blocking_reason"])

    def test_shallow_forward_ledger_is_not_history_selector_ready(self) -> None:
        ledger = pd.DataFrame(
            [
                {
                    "run_id": "r1",
                    "received_at_local": "2026-06-02T01:00:00+08:00",
                    "route": "basis",
                    "product_vt_symbol": "j.DCE",
                    "usable_for_forward_monitor": 1,
                    "usable_for_history_selector": 0,
                },
                {
                    "run_id": "r2",
                    "received_at_local": "2026-06-03T01:00:00+08:00",
                    "route": "inventory",
                    "product_vt_symbol": "i.DCE",
                    "usable_for_forward_monitor": 1,
                    "usable_for_history_selector": 0,
                },
            ]
        )

        summary = summarize_forward_ledger(ledger, min_runs=20, min_dates=20)

        self.assertEqual(summary["runs"], 2)
        self.assertEqual(summary["received_dates"], 2)
        self.assertFalse(summary["history_selector_ready"])
        self.assertIn("20", summary["blocking_reason"])

    def test_jd_requires_stable_evidence_before_shared_ai_pool(self) -> None:
        predictions = pd.DataFrame(
            [
                {
                    "eval_date": "2022-01-31",
                    "product_vt_symbol": "jd.DCE",
                    "stage021_ai_top8": True,
                    "stage021_simple_top8": True,
                    "stage021_consensus_top8_jd": True,
                    "future_net_pnl_60d": -760.0,
                },
                {
                    "eval_date": "2022-02-28",
                    "product_vt_symbol": "jd.DCE",
                    "stage021_ai_top8": False,
                    "stage021_simple_top8": True,
                    "stage021_consensus_top8_jd": False,
                    "future_net_pnl_60d": 120.0,
                },
            ]
        )

        summary = summarize_jd_full_market(predictions)

        self.assertEqual(summary["jd_rows"], 2)
        self.assertEqual(summary["jd_consensus_months"], 1)
        self.assertEqual(summary["recommendation"], "jd_not_shared_ai_ready")


if __name__ == "__main__":
    unittest.main()
