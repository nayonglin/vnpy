from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools/account_label_plan.py"
SPEC = importlib.util.spec_from_file_location("account_label_plan", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def _formal(dates: list[str]) -> pd.DataFrame:
    rows = [
        {
            "strategy": "formal_strategy",
            "score_type": "pre_clean",
            "eval_date": "2021-12-31",
            "product_vt_symbol": "legacy.X",
            "score": 0.0,
            "score_rank": 1,
            "top_n": 1,
        }
    ]
    for date_index, eval_date in enumerate(dates):
        for rank in range(1, 12):
            rows.append(
                {
                    "strategy": "formal_strategy",
                    "score_type": "formal_ai",
                    "eval_date": eval_date,
                    "product_vt_symbol": (
                        "fu.X" if rank == 11 else f"old_{date_index}_{rank}.X"
                    ),
                    "score": 1.0 - rank / 100.0,
                    "score_rank": rank,
                    "top_n": 11,
                }
            )
    return pd.DataFrame(rows)


def _ranking(dates: list[str], maximum_rank: int = 12) -> pd.DataFrame:
    rows = []
    for date_index, eval_date in enumerate(dates[:-1]):
        for rank in range(1, maximum_rank + 1):
            rows.append(
                {
                    "eval_date": eval_date,
                    "product_vt_symbol": f"clean_{date_index}_{rank}.X",
                    "pit_logistic_probability": 0.95 - rank / 100.0,
                    "a_rank": rank,
                    "window_id": "wf_01",
                    "role": "top9" if rank < 10 else "candidate",
                }
            )
    return pd.DataFrame(rows)


def _candidate_panel(ranking: pd.DataFrame) -> pd.DataFrame:
    return ranking[ranking["a_rank"].ge(10)].copy()


def test_path_consistent_candidate_rewrites_all_prior_clean_top10() -> None:
    dates = ["2022-01-31", "2022-02-28", "2022-03-31"]
    formal = _formal(dates)
    ranking = _ranking(dates)

    candidate, audit = module.build_path_consistent_eligibility(
        formal,
        ranking,
        eval_date="2022-02-28",
        candidate_rank=12,
        fixed_product="fu.X",
    )

    for eval_date in dates[:2]:
        month = candidate[candidate["eval_date"].eq(eval_date)].sort_values("score_rank")
        expected = [f"clean_{dates.index(eval_date)}_{rank}.X" for rank in range(1, 11)]
        if eval_date == "2022-02-28":
            expected[-1] = "clean_1_12.X"
        assert month[month["score_rank"].le(10)]["product_vt_symbol"].tolist() == expected
        assert month.loc[month["score_rank"].eq(11), "product_vt_symbol"].tolist() == [
            "fu.X"
        ]

    future_before = module.canonical_eligibility(formal)
    future_before = future_before[future_before["eval_date"].eq("2022-03-31")]
    future_after = candidate[candidate["eval_date"].eq("2022-03-31")]
    pd.testing.assert_frame_equal(
        future_before.reset_index(drop=True), future_after.reset_index(drop=True)
    )
    assert audit["clean_months_overwritten"] == 2
    assert audit["clean_top10_rows_overwritten"] == 20
    assert audit["candidate_changed_row_count_vs_clean_baseline"] == 1
    assert audit["candidate_changed_columns"] == [
        "product_vt_symbol",
        "score",
        "score_type",
    ]
    assert audit["fixed_product_rows_unchanged"] is True
    assert audit["future_rows_unchanged"] is True


def test_rank10_is_exact_clean_baseline() -> None:
    dates = ["2022-01-31", "2022-02-28"]
    formal = _formal(dates)
    ranking = _ranking(dates)

    candidate, audit = module.build_path_consistent_eligibility(
        formal,
        ranking,
        eval_date="2022-01-31",
        candidate_rank=10,
        fixed_product="fu.X",
    )

    assert audit["candidate_eligibility_sha256"] == audit["clean_baseline_sha256"]
    assert audit["candidate_changed_row_count_vs_clean_baseline"] == 0
    assert audit["candidate_changed_columns"] == []
    target = candidate[
        candidate["eval_date"].eq("2022-01-31") & candidate["score_rank"].eq(10)
    ].iloc[0]
    assert target["product_vt_symbol"] == "clean_0_10.X"


def test_split_jobs_and_smoke_are_mechanical() -> None:
    formal_dates = [
        "2022-01-31",
        "2022-02-28",
        "2022-03-31",
        "2022-04-29",
        "2022-05-31",
    ]
    ranking = _ranking(formal_dates)
    candidate = _candidate_panel(ranking)
    split = module.build_time_split(
        candidate,
        _formal(formal_dates),
        development_month_count=3,
        expected_month_count=4,
    )
    jobs, smoke_ids = module.build_development_jobs(
        split,
        sentinel_month_indexes=(0, 2),
    )

    assert split.groupby("split").size().to_dict() == {
        "development": 9,
        "sealed_account_label_holdout": 3,
    }
    assert len(jobs[jobs["job_type"].eq("main")]) == 9
    assert jobs[jobs["job_type"].eq("A2_sentinel")]["job_id"].tolist() == [
        "20220131_R10_A2",
        "20220331_R10_A2",
    ]
    assert smoke_ids == (
        "20220131_R10",
        "20220131_R10_A2",
        "20220228_R10",
        "20220228_R11",
    )
    assert not jobs["split"].eq("sealed_account_label_holdout").any()


def test_clean_ranking_rejects_fixed_product() -> None:
    dates = ["2022-01-31", "2022-02-28"]
    ranking = _ranking(dates)
    ranking.loc[ranking["a_rank"].eq(12), "product_vt_symbol"] = "fu.X"

    with pytest.raises(module.AccountLabelPlanError, match="fixed_product_in_clean_ranking"):
        module.build_path_consistent_eligibility(
            _formal(dates),
            ranking,
            eval_date="2022-01-31",
            candidate_rank=12,
            fixed_product="fu.X",
        )

