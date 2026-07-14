from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

from research.lines.futures_trend_ai_rank_year_jackknife_qualification.tools import (
    stage001_year_jackknife_qualification as stage,
)


def _month_frame(eval_date: str = "2022-01-31") -> pd.DataFrame:
    products = ["A.DCE", "B.DCE", "C.DCE", "D.DCE"]
    rows: list[dict[str, object]] = []
    for index, product in enumerate(products):
        rank = (index + 1) / len(products)
        rows.append(
            {
                "eval_date": eval_date,
                "product_vt_symbol": product,
                "data_available": 1,
                "cumulative_net_pnl_to_date": float((index + 1) * 100),
                "rank_all_cycle_profit": rank,
                "score_before_history_gate": 0.5 + 0.24 * rank,
                "score": 0.5 + 0.24 * rank,
                "selected_topn": int(product in {"C.DCE", "D.DCE"}),
            }
        )
    return pd.DataFrame(rows)


class Stage001YearJackknifeTest(unittest.TestCase):
    def test_rank_pct_matches_fixed_average_semantics(self) -> None:
        values = pd.Series([10.0, 20.0, 20.0, np.nan], index=list("abcd"))
        ranked = stage.rank_pct(values)
        self.assertAlmostEqual(float(ranked["a"]), 0.25)
        self.assertAlmostEqual(float(ranked["b"]), 0.75)
        self.assertAlmostEqual(float(ranked["c"]), 0.75)
        self.assertAlmostEqual(float(ranked["d"]), 0.75)

    def test_deleted_year_must_be_completed_and_changes_only_all_cycle_component(self) -> None:
        month = _month_frame()
        annual = pd.DataFrame(
            {
                "eval_date": pd.to_datetime(["2022-01-31"] * 4),
                "product_vt_symbol": month["product_vt_symbol"],
                "year": [2020, 2020, 2020, 2020],
                "net_pnl": [0.0, 0.0, 300.0, 0.0],
            }
        )

        variant = stage.build_variant_ranking(
            month,
            annual_pnl=annual,
            omitted_year=2020,
            top_n=2,
        )

        base_other = month["score_before_history_gate"] - 0.24 * month["rank_all_cycle_profit"]
        variant_other = variant["score_before_history_gate_variant"] - 0.24 * variant["rank_all_cycle_profit_variant"]
        pd.testing.assert_series_equal(
            base_other.reset_index(drop=True),
            variant_other.reset_index(drop=True),
            check_names=False,
        )
        with self.assertRaises(stage.IntegrityError):
            stage.build_variant_ranking(month, annual_pnl=annual, omitted_year=2022, top_n=2)
        with self.assertRaises(stage.IntegrityError):
            stage.build_variant_ranking(month, annual_pnl=annual, omitted_year=2023, top_n=2)

    def test_variant_selection_uses_score_then_symbol_tie_break(self) -> None:
        month = _month_frame()
        month["score_before_history_gate"] = 0.5
        month["score"] = 0.5
        month["rank_all_cycle_profit"] = 0.5
        month["cumulative_net_pnl_to_date"] = 100.0
        annual = pd.DataFrame(
            columns=["eval_date", "product_vt_symbol", "year", "net_pnl"]
        )

        variant = stage.build_variant_ranking(
            month,
            annual_pnl=annual,
            omitted_year=None,
            top_n=2,
        )

        selected = variant.loc[variant["selected_variant"], "product_vt_symbol"].tolist()
        self.assertEqual(selected, ["A.DCE", "B.DCE"])

    def test_consensus_is_mean_ordinal_rank_then_symbol(self) -> None:
        variants = pd.DataFrame(
            [
                {"variant": "base", "product_vt_symbol": "A.DCE", "ordinal_rank": 1},
                {"variant": "base", "product_vt_symbol": "B.DCE", "ordinal_rank": 2},
                {"variant": "base", "product_vt_symbol": "C.DCE", "ordinal_rank": 3},
                {"variant": "drop2020", "product_vt_symbol": "A.DCE", "ordinal_rank": 3},
                {"variant": "drop2020", "product_vt_symbol": "B.DCE", "ordinal_rank": 1},
                {"variant": "drop2020", "product_vt_symbol": "C.DCE", "ordinal_rank": 2},
            ]
        )

        consensus = stage.build_consensus_selection(variants, top_n=2)

        self.assertEqual(
            consensus.loc[consensus["selected_consensus"], "product_vt_symbol"].tolist(),
            ["B.DCE", "A.DCE"],
        )
        self.assertEqual(consensus["variant_count"].unique().tolist(), [2])

    def test_future_horizon_is_strictly_after_eval_and_requires_all_dates(self) -> None:
        calendar = pd.DatetimeIndex(pd.date_range("2022-01-03", periods=70, freq="B"))
        eval_date = calendar[4]
        future = calendar[calendar > eval_date][:60]
        daily = {
            "A.DCE": pd.DataFrame(
                {"date": calendar, "net_pnl": np.arange(len(calendar), dtype=float)}
            ),
            "B.DCE": pd.DataFrame(
                {
                    "date": calendar.delete(10),
                    "net_pnl": np.arange(len(calendar) - 1, dtype=float),
                }
            ),
        }

        labels, audit = stage.build_future60_labels(
            eval_date=eval_date,
            products=["A.DCE", "B.DCE"],
            global_dates=calendar,
            daily_by_product=daily,
            horizon=60,
        )

        a = labels.set_index("product_vt_symbol").loc["A.DCE"]
        b = labels.set_index("product_vt_symbol").loc["B.DCE"]
        self.assertEqual(pd.Timestamp(a["label_start_date"]), future[0])
        self.assertEqual(pd.Timestamp(a["label_end_date"]), future[-1])
        self.assertEqual(int(a["observed_date_count"]), 60)
        self.assertTrue(bool(a["label_complete"]))
        self.assertFalse(bool(b["label_complete"]))
        self.assertEqual(audit["eval_date_in_label_count"], 0)

    def test_compare_selection_conserves_swaps_and_does_not_fake_zero_edge(self) -> None:
        labels = pd.DataFrame(
            {
                "product_vt_symbol": ["A.DCE", "B.DCE", "C.DCE", "D.DCE"],
                "future60_net_pnl": [10.0, 20.0, 30.0, 40.0],
                "future60_percentile": [0.25, 0.5, 0.75, 1.0],
                "label_complete": [True, True, True, True],
            }
        )
        swapped = stage.compare_selections(
            eval_date=pd.Timestamp("2022-01-31"),
            baseline={"A.DCE", "B.DCE"},
            consensus={"B.DCE", "C.DCE"},
            labels=labels,
        )
        self.assertEqual(swapped["added_count"], 1)
        self.assertEqual(swapped["removed_count"], 1)
        self.assertTrue(swapped["swap_conservation_pass"])
        self.assertEqual(swapped["raw_edge"], 20.0)
        self.assertEqual(swapped["percentile_edge"], 0.5)
        self.assertTrue(swapped["comparison_eligible"])

        unchanged = stage.compare_selections(
            eval_date=pd.Timestamp("2022-02-28"),
            baseline={"A.DCE", "B.DCE"},
            consensus={"A.DCE", "B.DCE"},
            labels=labels,
        )
        self.assertEqual(unchanged["swap_count"], 0)
        self.assertFalse(unchanged["comparison_eligible"])
        self.assertTrue(np.isnan(unchanged["raw_edge"]))

    def test_decision_fails_year_sample_shortfall_even_if_aggregate_positive(self) -> None:
        rows = []
        for index in range(42):
            year = 2022 if index < 22 else 2023 + (index % 4)
            rows.append(
                {
                    "eval_date": pd.Timestamp(year=year, month=(index % 12) + 1, day=1),
                    "label_window_complete": True,
                    "comparison_eligible": index < 22 or index in {22, 23},
                    "raw_edge": 10.0 if index < 22 or index in {22, 23} else np.nan,
                    "percentile_edge": 0.1 if index < 22 or index in {22, 23} else np.nan,
                }
            )
        monthly = pd.DataFrame(rows)

        decision, yearly, gates = stage.build_decision(monthly)

        self.assertEqual(decision["decision"], "CLOSE_LINE_YEAR_JACKKNIFE_RANK_INELIGIBLE")
        self.assertFalse(bool(gates.set_index("gate").loc["effective_year_min_swap_months", "pass"]))
        self.assertTrue((yearly["raw_edge_sum"] >= 0).all())

    def test_decision_can_pass_only_when_every_frozen_gate_passes(self) -> None:
        rows = []
        for year in range(2022, 2027):
            for month in range(1, 10):
                rows.append(
                    {
                        "eval_date": pd.Timestamp(year=year, month=month, day=1),
                        "label_window_complete": True,
                        "comparison_eligible": True,
                        "raw_edge": 10.0,
                        "percentile_edge": 0.1,
                    }
                )
        decision, _yearly, gates = stage.build_decision(pd.DataFrame(rows))
        self.assertTrue(bool(gates["pass"].all()))
        self.assertEqual(
            decision["decision"],
            "ALLOW_STAGE002_FOUR_ANCHOR_CANARY_PREDECL_ONLY",
        )
        self.assertFalse(decision["ready_for_backtest"])
        self.assertFalse(decision["ready_for_live"])


if __name__ == "__main__":
    unittest.main()
