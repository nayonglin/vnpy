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


from stage079_member_rank_pit_coverage_audit import (  # noqa: E402
    MEMBER_RANK_PATH,
    attach_member_rank_asof,
    normalize_member_rank_history,
    summarize_member_rank_coverage,
)


class Stage079MemberRankPitCoverageAuditTest(unittest.TestCase):
    def test_member_rank_path_resolves_under_current_vnpy_workspace(self) -> None:
        self.assertEqual(MEMBER_RANK_PATH.parents[4].name, "vnpy")

    def test_normalize_member_rank_history_uses_t_plus_one_available_date(self) -> None:
        raw = pd.DataFrame(
            [
                {
                    "date": "20230103",
                    "variety": "rb",
                    "symbol": "RB2305",
                    "long_open_interest_top20": 120.0,
                    "short_open_interest_top20": 80.0,
                    "long_open_interest_chg_top20": 12.0,
                    "short_open_interest_chg_top20": -4.0,
                    "vol_top20": 1000.0,
                }
            ]
        )

        normalized = normalize_member_rank_history(raw)

        self.assertEqual(normalized.loc[0, "product_code"], "RB")
        self.assertEqual(str(normalized.loc[0, "member_date"].date()), "2023-01-03")
        self.assertEqual(str(normalized.loc[0, "available_date"].date()), "2023-01-04")
        self.assertAlmostEqual(float(normalized.loc[0, "net_position_ratio_top20"]), 0.2)
        self.assertAlmostEqual(float(normalized.loc[0, "net_position_chg_ratio_top20"]), 0.08)

    def test_attach_member_rank_asof_respects_available_date_and_max_age(self) -> None:
        entries = pd.DataFrame(
            [
                {"entry_id": "same_day_blocked", "entry_date": "2023-01-03", "product": "rb.SHFE"},
                {"entry_id": "next_day_attached", "entry_date": "2023-01-04", "product": "rb.SHFE"},
                {"entry_id": "too_old_blocked", "entry_date": "2023-01-20", "product": "rb.SHFE"},
            ]
        )
        member = pd.DataFrame(
            [
                {
                    "member_date": pd.Timestamp("2023-01-03"),
                    "available_date": pd.Timestamp("2023-01-04"),
                    "product_code": "RB",
                    "product": "rb.SHFE",
                    "net_position_ratio_top20": 0.2,
                    "net_position_chg_ratio_top20": 0.08,
                    "turnover_pressure_ratio_top20": 5.0,
                }
            ]
        )

        joined = attach_member_rank_asof(entries, member, max_age_days=7)

        by_id = joined.set_index("entry_id")
        self.assertFalse(bool(by_id.loc["same_day_blocked", "member_rank_available"]))
        self.assertTrue(bool(by_id.loc["next_day_attached", "member_rank_available"]))
        self.assertEqual(int(by_id.loc["next_day_attached", "member_rank_age_days"]), 0)
        self.assertFalse(bool(by_id.loc["too_old_blocked", "member_rank_available"]))

    def test_summarize_member_rank_coverage_rejects_missing_left_tail_history(self) -> None:
        joined_features = pd.DataFrame(
            [
                {"entry_date": "2022-08-22", "member_rank_available": False},
                {"entry_date": "2023-02-01", "member_rank_available": True},
                {"entry_date": "2024-02-01", "member_rank_available": True},
            ]
        )
        joined_windows = pd.DataFrame(
            [
                {"entry_date": "2022-08-22", "member_rank_available": False, "stage071_base_loss_abs": 9000.0},
                {"entry_date": "2023-02-01", "member_rank_available": True, "stage071_base_loss_abs": 1000.0},
            ]
        )

        summary = summarize_member_rank_coverage(
            joined_features,
            joined_windows,
            min_left_tail_entry_coverage_pct=50.0,
            min_left_tail_loss_coverage_pct=50.0,
        )

        self.assertFalse(bool(summary["history_selector_ready"]))
        self.assertEqual(summary["decision"], "stage079_member_rank_not_history_selector_missing_left_tail")
        self.assertAlmostEqual(float(summary["left_tail_entry_coverage_pct"]), 50.0)
        self.assertAlmostEqual(float(summary["left_tail_loss_coverage_pct"]), 10.0)


if __name__ == "__main__":
    unittest.main()
