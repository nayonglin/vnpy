from __future__ import annotations

from pathlib import Path
import sys
import unittest

import pandas as pd


TOOLS_DIR = (
    Path(__file__).resolve().parents[1]
    / "research"
    / "lines"
    / "futures_trend_rollover_shape_same_volume"
    / "tools"
)
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage006_directional_30d_risk_boost_acd as stage006  # noqa: E402


def _metric_row(
    arm: str,
    end_equity: float,
    total_return_pct: float,
    max_dd_pct: float,
    sharpe: float,
    total_slippage: float,
    total_trade_count: int,
    account_survival_pass: int,
    broker10_100_pass: int,
) -> dict[str, object]:
    return {
        "experiment_arm": arm,
        "end_equity": end_equity,
        "total_return_pct": total_return_pct,
        "max_dd_pct": max_dd_pct,
        "sharpe": sharpe,
        "total_slippage": total_slippage,
        "total_trade_count": total_trade_count,
        "account_survival_pass": account_survival_pass,
        "broker10_100_pass": broker10_100_pass,
        "max_broker10_margin_to_equity_pct": 90.0 if broker10_100_pass else 101.0,
        "days_over_100pct": 0 if broker10_100_pass else 1,
    }


class Stage006DirectionalRiskBoostRunnerTest(unittest.TestCase):
    def test_boost_contract_summary_proves_aligned_rows_are_1p2_and_unaligned_rows_are_1p0(self) -> None:
        entry_risk = pd.DataFrame(
            [
                {
                    "profile": stage006.BOOST_PROFILE,
                    "direction": "long",
                    "entry_context": "flat_entry",
                    "directional_30d_risk_boost_enabled": 1,
                    "directional_30d_risk_boost_aligned": 1,
                    "directional_30d_risk_boost_multiplier": 1.2,
                    "risk_amount_before_directional_30d_boost": 100.0,
                    "target_risk_amount": 120.0,
                },
                {
                    "profile": stage006.BOOST_PROFILE,
                    "direction": "short",
                    "entry_context": "reverse_entry",
                    "directional_30d_risk_boost_enabled": 1,
                    "directional_30d_risk_boost_aligned": 0,
                    "directional_30d_risk_boost_multiplier": 1.0,
                    "risk_amount_before_directional_30d_boost": 100.0,
                    "target_risk_amount": 100.0,
                },
                {
                    "profile": stage006.BOOST_PROFILE,
                    "direction": "long",
                    "entry_context": "rollover_reopen",
                    "directional_30d_risk_boost_enabled": 1,
                    "directional_30d_risk_boost_aligned": 1,
                    "directional_30d_risk_boost_multiplier": 1.2,
                    "risk_amount_before_directional_30d_boost": 200.0,
                    "target_risk_amount": 240.0,
                },
            ]
        )

        summary = stage006._boost_contract_summary(entry_risk)

        total = summary[summary["group_type"].eq("total")].iloc[0]
        self.assertEqual(3, int(total["entry_count"]))
        self.assertEqual(2, int(total["aligned_count"]))
        self.assertEqual(1, int(total["unaligned_count"]))
        self.assertEqual(1, int(total["risk_amount_contract_pass"]))
        contexts = set(summary[summary["group_type"].eq("entry_context")]["group_value"])
        self.assertEqual({"flat_entry", "reverse_entry", "rollover_reopen"}, contexts)

    def test_decision_passes_only_when_d_improves_c_without_material_risk_damage(self) -> None:
        summary = pd.DataFrame(
            [
                _metric_row("A", 1000.0, 100.0, -30.0, 1.00, 100.0, 100, 1, 1),
                _metric_row("C", 1100.0, 110.0, -31.0, 1.05, 105.0, 105, 1, 0),
                _metric_row("D", 1200.0, 120.0, -32.0, 1.04, 110.0, 110, 1, 0),
            ]
        )
        boost_summary = pd.DataFrame(
            [{"group_type": "total", "risk_amount_contract_pass": 1, "aligned_count": 2}]
        )

        decision = stage006._decision(summary, boost_summary)

        self.assertTrue(decision["escalate_to_multicycle"])
        self.assertTrue(all(decision["predeclared_gates"].values()))

    def test_decision_fails_when_d_drawdown_worsens_more_than_2pp(self) -> None:
        summary = pd.DataFrame(
            [
                _metric_row("A", 1000.0, 100.0, -30.0, 1.00, 100.0, 100, 1, 1),
                _metric_row("C", 1100.0, 110.0, -31.0, 1.05, 105.0, 105, 1, 0),
                _metric_row("D", 1200.0, 120.0, -34.0, 1.04, 110.0, 110, 1, 0),
            ]
        )
        boost_summary = pd.DataFrame(
            [{"group_type": "total", "risk_amount_contract_pass": 1, "aligned_count": 2}]
        )

        decision = stage006._decision(summary, boost_summary)

        self.assertFalse(decision["escalate_to_multicycle"])
        self.assertFalse(decision["predeclared_gates"]["D_dd_noninferior_2pp_vs_C"])

    def test_decision_detects_broker100_severity_worsening_even_when_both_arms_fail(self) -> None:
        rows = [
            _metric_row("A", 1000.0, 100.0, -30.0, 1.00, 100.0, 100, 1, 1),
            _metric_row("C", 1100.0, 110.0, -31.0, 1.05, 105.0, 105, 1, 0),
            _metric_row("D", 1200.0, 120.0, -32.0, 1.04, 110.0, 110, 1, 0),
        ]
        rows[1]["max_broker10_margin_to_equity_pct"] = 100.4
        rows[1]["days_over_100pct"] = 1
        rows[2]["max_broker10_margin_to_equity_pct"] = 114.6
        rows[2]["days_over_100pct"] = 4
        summary = pd.DataFrame(rows)
        boost_summary = pd.DataFrame(
            [{"group_type": "total", "risk_amount_contract_pass": 1, "aligned_count": 2}]
        )

        decision = stage006._decision(summary, boost_summary)

        self.assertFalse(decision["escalate_to_multicycle"])
        self.assertFalse(decision["predeclared_gates"]["D_broker100_not_worse_than_C"])


if __name__ == "__main__":
    unittest.main()
