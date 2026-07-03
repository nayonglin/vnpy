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


from stage065_full_sample_exit_path_proxy_audit import (  # noqa: E402
    _apply_exit_proxy_variants,
    _classify_stage065_proxy,
    _stage065_decision,
    _summarize_exit_proxy,
)


class RebuiltC9Stage065ExitPathProxyTest(unittest.TestCase):
    def test_apply_exit_proxy_variants_cuts_hard_takeprofit_winner(self) -> None:
        lots = pd.DataFrame(
            [
                {"realized_pnl": 500.0, "risk_amount": 100.0, "r_multiple": 5.0, "mfe_r": 5.5},
                {"realized_pnl": -80.0, "risk_amount": 100.0, "r_multiple": -0.8, "mfe_r": 0.6},
            ]
        )

        result = _apply_exit_proxy_variants(lots)

        self.assertEqual(result.loc[0, "proxy_hard_tp_2r_pnl"], 200.0)
        self.assertEqual(result.loc[0, "delta_hard_tp_2r"], -300.0)
        self.assertEqual(result.loc[1, "proxy_hard_tp_2r_pnl"], -80.0)

    def test_breakeven_after_1r_only_saves_final_losers(self) -> None:
        lots = pd.DataFrame(
            [
                {"realized_pnl": -120.0, "risk_amount": 100.0, "r_multiple": -1.2, "mfe_r": 1.1},
                {"realized_pnl": 220.0, "risk_amount": 100.0, "r_multiple": 2.2, "mfe_r": 2.5},
            ]
        )

        result = _apply_exit_proxy_variants(lots)

        self.assertEqual(result.loc[0, "proxy_be_after_1r_pnl"], 0.0)
        self.assertEqual(result.loc[0, "delta_be_after_1r"], 120.0)
        self.assertEqual(result.loc[1, "proxy_be_after_1r_pnl"], 220.0)

    def test_pressure_path_r_multiple_agg_is_accepted_as_r_multiple(self) -> None:
        pressure_lots = pd.DataFrame(
            [
                {
                    "realized_pnl": -120.0,
                    "risk_amount": 100.0,
                    "r_multiple_agg": -1.2,
                    "mfe_r": 1.1,
                }
            ]
        )

        result = _apply_exit_proxy_variants(pressure_lots)

        self.assertTrue(bool(result.loc[0, "valid_proxy_sample"]))
        self.assertEqual(result.loc[0, "proxy_be_after_1r_pnl"], 0.0)

    def test_summarize_exit_proxy_reports_retention_and_winner_cut(self) -> None:
        full = _apply_exit_proxy_variants(
            pd.DataFrame(
                [
                    {"realized_pnl": 500.0, "risk_amount": 100.0, "r_multiple": 5.0, "mfe_r": 5.5, "big_winner": 1},
                    {"realized_pnl": -120.0, "risk_amount": 100.0, "r_multiple": -1.2, "mfe_r": 1.1, "big_winner": 0},
                ]
            )
        )
        pressure = _apply_exit_proxy_variants(
            pd.DataFrame(
                [{"realized_pnl": -120.0, "risk_amount": 100.0, "r_multiple": -1.2, "mfe_r": 1.1}]
            )
        )

        summary = _summarize_exit_proxy(full, pressure).set_index("proxy_id")

        self.assertEqual(summary.loc["optimistic_breakeven_after_1r", "pressure_delta"], 120.0)
        self.assertLess(summary.loc["hard_takeprofit_2r", "full_retention_pct"], 80.0)
        self.assertLess(summary.loc["hard_takeprofit_2r", "winner_cut"], 0.0)

    def test_classification_rejects_right_tail_collision_and_accepts_upper_bound_candidate(self) -> None:
        self.assertEqual(
            _classify_stage065_proxy(full_retention_pct=70.0, winner_cut=-1000.0, loser_saved=1500.0, pressure_delta=100.0),
            "right_tail_collision_or_retention_fail",
        )
        self.assertEqual(
            _classify_stage065_proxy(full_retention_pct=95.0, winner_cut=-100.0, loser_saved=500.0, pressure_delta=200.0),
            "proxy_candidate_needs_true_engine",
        )
        self.assertEqual(
            _classify_stage065_proxy(full_retention_pct=95.0, winner_cut=-100.0, loser_saved=500.0, pressure_delta=0.0),
            "no_pressure_value",
        )

    def test_decision_does_not_promote_when_no_proxy_candidate_exists(self) -> None:
        summary = pd.DataFrame(
            [
                {
                    "proxy_id": "hard_takeprofit_2r",
                    "full_retention_pct": 60.0,
                    "winner_cut": -1000.0,
                    "loser_saved": 200.0,
                    "pressure_delta": 100.0,
                    "proxy_class": "right_tail_collision_or_retention_fail",
                }
            ]
        )

        decision = _stage065_decision(summary)

        self.assertEqual(decision["decision"], "stage065_exit_proxy_no_candidate_keep_readonly")
        self.assertEqual(decision["best_proxy_id"], "hard_takeprofit_2r")


if __name__ == "__main__":
    unittest.main()
