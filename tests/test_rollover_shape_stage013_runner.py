from __future__ import annotations

import sys
import unittest
from pathlib import Path

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

import stage013_long_only_asymmetric_double_volume_multicycle_achij as stage013  # noqa: E402


def _window_summary() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for window in stage013.WINDOWS:
        for arm in stage013.ARMS:
            rows.append(
                {
                    "window_id": window["window_id"],
                    "window_group": window["window_group"],
                    "duration_years": window["duration_years"],
                    "requested_start": str(pd.Timestamp(window["start"]).date()),
                    "requested_end": str(pd.Timestamp(window["end"]).date()),
                    "complete_window": int(window["complete"]),
                    "terminal_near_complete": int(window["terminal_near_complete"]),
                    "promotion_arm": arm["arm"],
                    "start_month_num": int(pd.Timestamp(window["start"]).month),
                    "end_equity": 100.0,
                    "total_return_pct": 10.0,
                    "max_dd_pct": -5.0,
                    "sharpe": 1.0,
                    "total_slippage": 10.0,
                    "total_trade_count": 5,
                    "nonzero_daily_win_rate_pct": 50.0,
                    "account_survival_pass": 1,
                    "broker10_100_pass": 1,
                    "max_broker10_margin_to_equity_pct": 80.0,
                    "days_over_100pct": 0,
                }
            )
    return pd.DataFrame(rows)


class Stage013LongOnlyAsymmetricMulticycleRunnerTest(unittest.TestCase):
    def test_date_identity_ignores_midnight_string_format_only(self) -> None:
        normalize = getattr(
            stage013,
            "_date_keys",
            lambda values: values.astype(str).tolist(),
        )

        self.assertEqual(
            ["2018-01-02", "2026-05-29"],
            normalize(pd.Series(["2018-01-02 00:00:00", "2026-05-29"])),
        )

    def test_frozen_windows_five_arms_and_run_identity(self) -> None:
        self.assertEqual(43, len(stage013.WINDOWS))
        self.assertEqual(["A", "C", "H", "I", "J"], [arm["arm"] for arm in stage013.ARMS])
        self.assertEqual(215, len(stage013.WINDOWS) * len(stage013.ARMS))
        self.assertEqual({"A", "C", "H"}, stage013.REUSED_ARMS)
        self.assertEqual({"I", "J"}, stage013.NEW_RUN_ARMS)
        j = next(arm for arm in stage013.ARMS if arm["arm"] == "J")
        self.assertEqual(2.0, j["volume_ratio_threshold"])
        self.assertEqual(1.5, j["confirmation_multiplier"])
        self.assertEqual(0.5, j["nonconfirmation_multiplier"])
        self.assertTrue(j["long_only"])

    def test_pairwise_outputs_cover_ten_comparisons_and_three_cohorts(self) -> None:
        comparison = stage013._comparison(_window_summary())
        aggregate = stage013._aggregate(comparison)

        self.assertEqual(430, len(comparison))
        self.assertEqual(90, len(aggregate))
        self.assertEqual(10, len(set(comparison["comparison"])))
        self.assertEqual({"combined", "january", "june"}, set(aggregate["start_cohort"]))

    def test_j_contract_requires_long_split_and_short_bypass(self) -> None:
        rows = [
            {
                "direction": "long",
                "entry_context": "flat_entry",
                "directional_30d_risk_boost_enabled": 1,
                "directional_30d_volume_confirmation_enabled": 1,
                "directional_30d_risk_adjust_long_only": 1,
                "directional_30d_risk_boost_aligned": 1,
                "directional_30d_volume_ratio_threshold": 2.0,
                "directional_30d_recent_volume_sum": 201.0,
                "directional_30d_prior_volume_sum": 100.0,
                "directional_30d_risk_boost_applied": 1,
                "directional_30d_risk_nonconfirmation_multiplier": 0.5,
                "directional_30d_risk_boost_multiplier": 1.5,
                "directional_30d_risk_boost_reason": "direction_and_volume_confirmed",
                "risk_amount_before_directional_30d_boost": 1000.0,
                "target_risk_amount": 1500.0,
            },
            {
                "direction": "long",
                "entry_context": "rollover_reopen",
                "directional_30d_risk_boost_enabled": 1,
                "directional_30d_volume_confirmation_enabled": 1,
                "directional_30d_risk_adjust_long_only": 1,
                "directional_30d_risk_boost_aligned": 1,
                "directional_30d_volume_ratio_threshold": 2.0,
                "directional_30d_recent_volume_sum": 200.0,
                "directional_30d_prior_volume_sum": 100.0,
                "directional_30d_risk_boost_applied": 0,
                "directional_30d_risk_nonconfirmation_multiplier": 0.5,
                "directional_30d_risk_boost_multiplier": 0.5,
                "directional_30d_risk_boost_reason": "volume_not_expanding",
                "risk_amount_before_directional_30d_boost": 1000.0,
                "target_risk_amount": 500.0,
            },
            {
                "direction": "short",
                "entry_context": "flat_entry",
                "directional_30d_risk_boost_enabled": 1,
                "directional_30d_volume_confirmation_enabled": 1,
                "directional_30d_risk_adjust_long_only": 1,
                "directional_30d_risk_boost_aligned": 0,
                "directional_30d_volume_ratio_threshold": 2.0,
                "directional_30d_recent_volume_sum": float("nan"),
                "directional_30d_prior_volume_sum": float("nan"),
                "directional_30d_risk_boost_applied": 0,
                "directional_30d_risk_nonconfirmation_multiplier": 0.5,
                "directional_30d_risk_boost_multiplier": 1.0,
                "directional_30d_risk_boost_reason": "direction_excluded",
                "risk_amount_before_directional_30d_boost": 1000.0,
                "target_risk_amount": 1000.0,
            },
        ]

        contract = stage013._risk_split_contract_summary(pd.DataFrame(rows))
        total = contract[contract["group_type"].eq("total")].iloc[0]

        self.assertEqual(1, int(total["long_confirmation_count"]))
        self.assertEqual(1, int(total["long_nonconfirmation_count"]))
        self.assertEqual(1, int(total["short_bypass_count"]))
        self.assertEqual(1, int(total["threshold_contract_pass"]))
        self.assertEqual(1, int(total["risk_amount_contract_pass"]))


if __name__ == "__main__":
    unittest.main()
