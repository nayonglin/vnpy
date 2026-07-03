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


from stage076_trend_breadth_pit_audit import (  # noqa: E402
    add_breadth_condition_robustness,
    attach_pit_breadth_features,
    build_trend_breadth_condition_specs,
    summarize_breadth_feature_coverage,
)


class Stage076TrendBreadthPitAuditTest(unittest.TestCase):
    def test_attach_pit_breadth_features_uses_t_plus_one_asof_without_lookahead(self) -> None:
        entries = pd.DataFrame(
            [
                {"entry_date": "2026-01-02", "full_market_ai_top8": True},
                {"entry_date": "2026-01-03", "full_market_ai_top8": True},
                {"entry_date": "2026-01-08", "full_market_ai_top8": True},
            ]
        )
        market_daily = pd.DataFrame(
            [
                {
                    "date": "2026-01-02",
                    "ma20_over_ma60_share_60d": 0.72,
                    "cross_section_ret60_dispersion": 0.11,
                    "trend_breadth_bucket": "breadth_high",
                    "joint_regime": "broad_trend",
                    "product_count": 18,
                }
            ]
        )

        attached = attach_pit_breadth_features(entries, market_daily, max_feature_age_days=2)

        self.assertFalse(bool(attached.loc[0, "trend_breadth_matched"]))
        self.assertTrue(bool(attached.loc[1, "trend_breadth_matched"]))
        self.assertEqual(attached.loc[1, "trend_breadth_feature_date"], pd.Timestamp("2026-01-02"))
        self.assertEqual(attached.loc[1, "trend_breadth_asof_date"], pd.Timestamp("2026-01-03"))
        self.assertEqual(int(attached.loc[1, "trend_breadth_feature_age_days"]), 0)
        self.assertAlmostEqual(float(attached.loc[1, "trend_breadth_share"]), 0.72)
        self.assertFalse(bool(attached.loc[2, "trend_breadth_matched"]))

    def test_build_trend_breadth_condition_specs_uses_only_pre_entry_breadth_and_ai_fields(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    "trend_breadth_matched": True,
                    "trend_breadth_bucket": "breadth_high",
                    "trend_breadth_share": 0.75,
                    "trend_breadth_dispersion": 0.10,
                    "full_market_ai_top8": True,
                    "account_injured": False,
                },
                {
                    "trend_breadth_matched": True,
                    "trend_breadth_bucket": "breadth_low",
                    "trend_breadth_share": 0.20,
                    "trend_breadth_dispersion": 0.25,
                    "full_market_ai_top8": True,
                    "account_injured": True,
                },
                {
                    "trend_breadth_matched": False,
                    "trend_breadth_bucket": "",
                    "trend_breadth_share": float("nan"),
                    "trend_breadth_dispersion": float("nan"),
                    "full_market_ai_top8": False,
                    "account_injured": False,
                },
            ]
        )

        specs = build_trend_breadth_condition_specs(frame)
        by_name = {spec.name: spec for spec in specs}

        self.assertEqual(
            by_name["full_market_ai_top8_and_breadth_mid_or_high"].mask.tolist(),
            [True, False, False],
        )
        self.assertEqual(by_name["breadth_low_or_narrow_chop"].mask.tolist(), [False, True, False])
        self.assertTrue(all(spec.feature_family != "post_entry" for spec in specs))

    def test_summarize_breadth_feature_coverage_reports_missing_recent_gap(self) -> None:
        frame = pd.DataFrame(
            [
                {"entry_date": "2026-04-30", "trend_breadth_matched": True, "trend_breadth_feature_age_days": 0},
                {"entry_date": "2026-06-24", "trend_breadth_matched": False, "trend_breadth_feature_age_days": float("nan")},
            ]
        )

        summary = summarize_breadth_feature_coverage(
            frame,
            market_min_date=pd.Timestamp("2020-01-02"),
            market_max_date=pd.Timestamp("2026-04-30"),
        )

        self.assertEqual(int(summary["entry_count"]), 2)
        self.assertEqual(int(summary["matched_entry_count"]), 1)
        self.assertAlmostEqual(float(summary["matched_entry_pct"]), 50.0)
        self.assertEqual(summary["market_max_date"], "2026-04-30")
        self.assertEqual(summary["max_entry_date"], "2026-06-24")
        self.assertTrue(bool(summary["has_recent_market_gap"]))

    def test_add_breadth_condition_robustness_rejects_negative_year_or_concentrated_winner(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    "entry_year": 2020,
                    "product_vt_symbol": "rb.SHFE",
                    "realized_pnl": 100.0,
                    "trend_breadth_matched": True,
                    "trend_breadth_bucket": "breadth_low",
                    "trend_breadth_joint_regime": "narrow_chop",
                    "full_market_ai_top8": False,
                    "account_injured": False,
                },
                {
                    "entry_year": 2021,
                    "product_vt_symbol": "rb.SHFE",
                    "realized_pnl": -50.0,
                    "trend_breadth_matched": True,
                    "trend_breadth_bucket": "breadth_low",
                    "trend_breadth_joint_regime": "narrow_chop",
                    "full_market_ai_top8": False,
                    "account_injured": False,
                },
                {
                    "entry_year": 2022,
                    "product_vt_symbol": "lc.GFEX",
                    "realized_pnl": 1000.0,
                    "trend_breadth_matched": True,
                    "trend_breadth_bucket": "breadth_low",
                    "trend_breadth_joint_regime": "narrow_chop",
                    "full_market_ai_top8": True,
                    "account_injured": True,
                },
            ]
        )
        summary = pd.DataFrame(
            [
                {
                    "condition": "breadth_low_or_narrow_chop",
                    "stable_oos_candidate": True,
                }
            ]
        )

        robust = add_breadth_condition_robustness(
            frame,
            summary,
            build_trend_breadth_condition_specs(frame),
            max_top10_positive_pnl_share_pct=80.0,
        )

        row = robust.iloc[0]
        self.assertAlmostEqual(float(row["min_year_pnl"]), -50.0)
        self.assertGreater(float(row["top10_positive_pnl_share_pct"]), 80.0)
        self.assertFalse(bool(row["stage076_robust_candidate"]))


if __name__ == "__main__":
    unittest.main()
