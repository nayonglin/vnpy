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


from stage080_member_rank_2022_backfill_feasibility import (  # noqa: E402
    build_member_rank_fetch_windows,
    combine_member_rank_histories,
    extract_required_member_rank_products,
    summarize_backfill_coverage_change,
)


class Stage080MemberRankBackfillFeasibilityTest(unittest.TestCase):
    def test_extract_required_member_rank_products_excludes_dce_left_tail(self) -> None:
        windows = pd.DataFrame(
            [
                {"entry_date": "2022-02-09", "product": "sp.SHFE", "stage071_base_loss_abs": 2172600.0},
                {"entry_date": "2022-08-22", "product": "SM.CZCE", "stage071_base_loss_abs": 1606380.0},
                {"entry_date": "2022-09-01", "product": "fu", "stage071_base_loss_abs": 285800.0},
                {"entry_date": "2022-10-10", "product": "jm.DCE", "stage071_base_loss_abs": 757470.0},
                {"entry_date": "2024-01-01", "product": "rb.SHFE", "stage071_base_loss_abs": 10.0},
            ]
        )

        products = extract_required_member_rank_products(
            windows,
            start="2022-01-01",
            end="2022-12-31",
            exclude_dce=True,
        )

        self.assertEqual(products, ["FU", "SM", "SP"])

    def test_build_member_rank_fetch_windows_chunks_required_year(self) -> None:
        fetch_windows = build_member_rank_fetch_windows(
            start="2022-01-01",
            end="2022-03-05",
            chunk_days=31,
        )

        self.assertEqual(
            fetch_windows,
            [
                ("20220101", "20220131"),
                ("20220201", "20220303"),
                ("20220304", "20220305"),
            ],
        )

    def test_combine_member_rank_histories_deduplicates_existing_rows(self) -> None:
        existing = pd.DataFrame(
            [
                {"date": "20230103", "symbol": "RB2305", "variety": "RB", "long_open_interest_top20": 10},
                {"date": "20230104", "symbol": "RB2305", "variety": "RB", "long_open_interest_top20": 20},
            ]
        )
        fetched = pd.DataFrame(
            [
                {"date": "20230104", "symbol": "rb2305", "variety": "rb", "long_open_interest_top20": 99},
                {"date": 20220104, "symbol": "SM205", "variety": "SM", "long_open_interest_top20": 30},
            ]
        )

        combined = combine_member_rank_histories(existing, fetched)

        key_rows = combined[["date", "symbol", "variety", "long_open_interest_top20"]].to_dict("records")
        self.assertEqual(
            key_rows,
            [
                {"date": "20220104", "symbol": "SM205", "variety": "SM", "long_open_interest_top20": 30},
                {"date": "20230103", "symbol": "RB2305", "variety": "RB", "long_open_interest_top20": 10},
                {"date": "20230104", "symbol": "RB2305", "variety": "RB", "long_open_interest_top20": 20},
            ],
        )

    def test_summarize_backfill_coverage_change_requires_loss_coverage_gain(self) -> None:
        before = pd.DataFrame(
            [
                {"entry_date": "2022-02-09", "member_rank_available": False, "stage071_base_loss_abs": 900.0},
                {"entry_date": "2023-02-01", "member_rank_available": True, "stage071_base_loss_abs": 100.0},
            ]
        )
        after = pd.DataFrame(
            [
                {"entry_date": "2022-02-09", "member_rank_available": True, "stage071_base_loss_abs": 900.0},
                {"entry_date": "2023-02-01", "member_rank_available": True, "stage071_base_loss_abs": 100.0},
            ]
        )

        summary = summarize_backfill_coverage_change(before, after, min_after_loss_coverage_pct=80.0)

        self.assertEqual(summary["decision"], "stage080_member_rank_backfill_coverage_ready_for_signal_audit")
        self.assertAlmostEqual(summary["before_left_tail_loss_coverage_pct"], 10.0)
        self.assertAlmostEqual(summary["after_left_tail_loss_coverage_pct"], 100.0)
        self.assertAlmostEqual(summary["left_tail_loss_coverage_gain_pp"], 90.0)


if __name__ == "__main__":
    unittest.main()
