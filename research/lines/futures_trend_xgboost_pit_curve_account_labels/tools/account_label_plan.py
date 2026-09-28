"""Build a label-free, path-consistent account marginal replay plan."""

from __future__ import annotations

import hashlib
from typing import Any, Iterable

import numpy as np
import pandas as pd


BLOCKED_DECISION = "stage003_account_label_plan_pass_smoke_blocked_on_runtime_preflight"
READY_DECISION = "stage003_account_label_plan_pass_ready_for_smoke_preregistration"
FAIL_DECISION = "stage003_account_label_plan_fail_stop_no_labels"
CLEAN_BASELINE_SCORE_TYPE = "stage003_clean_pit_logistic_top10_plus_fixed_fu"
CANDIDATE_SCORE_TYPE = "stage003_account_marginal_candidate_slot"
ELIGIBILITY_COLUMNS = [
    "strategy",
    "score_type",
    "eval_date",
    "product_vt_symbol",
    "score",
    "score_rank",
    "top_n",
]


class AccountLabelPlanError(RuntimeError):
    """Raised when the frozen account-label planning contract is violated."""


def _required_columns(frame: pd.DataFrame, required: Iterable[str], name: str) -> None:
    missing = set(required) - set(frame.columns)
    if missing:
        raise AccountLabelPlanError(f"{name}_columns_missing:{sorted(missing)}")


def _date_strings(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="raise").dt.normalize().dt.date.astype(str)


def dataframe_sha256(frame: pd.DataFrame) -> str:
    payload = frame.to_csv(
        index=False,
        lineterminator="\n",
        float_format="%.17g",
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def canonical_eligibility(formal: pd.DataFrame) -> pd.DataFrame:
    _required_columns(formal, ELIGIBILITY_COLUMNS, "formal_eligibility")
    frame = formal.loc[:, ELIGIBILITY_COLUMNS].copy()
    frame["eval_date"] = _date_strings(frame["eval_date"])
    frame["strategy"] = frame["strategy"].astype(str)
    frame["score_type"] = frame["score_type"].astype(str)
    frame["product_vt_symbol"] = frame["product_vt_symbol"].astype(str)
    frame["score"] = pd.to_numeric(frame["score"], errors="raise").astype(float)
    frame["score_rank"] = pd.to_numeric(
        frame["score_rank"], errors="raise"
    ).astype(int)
    frame["top_n"] = pd.to_numeric(frame["top_n"], errors="raise").astype(int)
    if not np.isfinite(frame["score"].to_numpy(float)).all():
        raise AccountLabelPlanError("formal_eligibility_score_nonfinite")
    if frame.duplicated(["eval_date", "score_rank"]).any():
        raise AccountLabelPlanError("formal_eligibility_date_rank_duplicate")
    frame.sort_values(["eval_date", "score_rank"], inplace=True, kind="mergesort")
    frame.reset_index(drop=True, inplace=True)
    return frame


def canonical_clean_ranking(ranking: pd.DataFrame) -> pd.DataFrame:
    required = {
        "eval_date",
        "product_vt_symbol",
        "pit_logistic_probability",
        "a_rank",
    }
    _required_columns(ranking, required, "clean_ranking")
    frame = ranking.copy()
    frame["eval_date"] = _date_strings(frame["eval_date"])
    frame["product_vt_symbol"] = frame["product_vt_symbol"].astype(str)
    frame["pit_logistic_probability"] = pd.to_numeric(
        frame["pit_logistic_probability"], errors="raise"
    ).astype(float)
    frame["a_rank"] = pd.to_numeric(frame["a_rank"], errors="raise").astype(int)
    if not np.isfinite(frame["pit_logistic_probability"].to_numpy(float)).all():
        raise AccountLabelPlanError("clean_ranking_probability_nonfinite")
    if frame.duplicated(["eval_date", "a_rank"]).any():
        raise AccountLabelPlanError("clean_ranking_date_rank_duplicate")
    if frame.duplicated(["eval_date", "product_vt_symbol"]).any():
        raise AccountLabelPlanError("clean_ranking_date_product_duplicate")
    for eval_date, month in frame.groupby("eval_date", sort=True):
        ranks = sorted(month["a_rank"].tolist())
        if ranks != list(range(1, max(ranks) + 1)) or max(ranks) < 10:
            raise AccountLabelPlanError(f"clean_ranking_rank_grid_invalid:{eval_date}")
    frame.sort_values(["eval_date", "a_rank"], inplace=True, kind="mergesort")
    frame.reset_index(drop=True, inplace=True)
    return frame


def _canonical_candidate_panel(panel: pd.DataFrame) -> pd.DataFrame:
    required = {"eval_date", "product_vt_symbol", "a_rank"}
    _required_columns(panel, required, "candidate_panel")
    frame = panel.copy()
    frame["eval_date"] = _date_strings(frame["eval_date"])
    frame["product_vt_symbol"] = frame["product_vt_symbol"].astype(str)
    frame["a_rank"] = pd.to_numeric(frame["a_rank"], errors="raise").astype(int)
    if frame.duplicated(["eval_date", "a_rank"]).any():
        raise AccountLabelPlanError("candidate_panel_date_rank_duplicate")
    if frame.duplicated(["eval_date", "product_vt_symbol"]).any():
        raise AccountLabelPlanError("candidate_panel_date_product_duplicate")
    for eval_date, month in frame.groupby("eval_date", sort=True):
        ranks = sorted(month["a_rank"].tolist())
        if ranks != list(range(10, max(ranks) + 1)):
            raise AccountLabelPlanError(f"candidate_rank_grid_invalid:{eval_date}")
    frame.sort_values(["eval_date", "a_rank"], inplace=True, kind="mergesort")
    frame.reset_index(drop=True, inplace=True)
    return frame


def build_time_split(
    candidate_panel: pd.DataFrame,
    formal_eligibility: pd.DataFrame,
    *,
    development_month_count: int,
    expected_month_count: int,
) -> pd.DataFrame:
    frame = _canonical_candidate_panel(candidate_panel)
    formal = canonical_eligibility(formal_eligibility)
    months = sorted(frame["eval_date"].unique())
    if len(months) != int(expected_month_count):
        raise AccountLabelPlanError(
            f"candidate_month_count:{len(months)}:{expected_month_count}"
        )
    if not 2 <= int(development_month_count) < len(months):
        raise AccountLabelPlanError("development_month_count_invalid")
    formal_dates = sorted(formal["eval_date"].unique())
    next_by_date: dict[str, str] = {}
    for eval_date in months:
        if eval_date not in formal_dates:
            raise AccountLabelPlanError(f"candidate_date_missing_in_formal:{eval_date}")
        later = [value for value in formal_dates if value > eval_date]
        if not later:
            raise AccountLabelPlanError(f"candidate_next_date_missing:{eval_date}")
        next_by_date[eval_date] = later[0]

    development_dates = set(months[:development_month_count])
    month_qid = {eval_date: index for index, eval_date in enumerate(months)}
    frame["next_eval_date"] = frame["eval_date"].map(next_by_date)
    frame["split"] = np.where(
        frame["eval_date"].isin(development_dates),
        "development",
        "sealed_account_label_holdout",
    )
    frame["label_values_read_allowed"] = frame["split"].eq("development")
    frame["account_label_qid"] = frame["eval_date"].map(month_qid).astype(int)
    frame.sort_values(["eval_date", "a_rank"], inplace=True, kind="mergesort")
    frame.reset_index(drop=True, inplace=True)
    return frame


def build_development_jobs(
    split_panel: pd.DataFrame,
    *,
    sentinel_month_indexes: tuple[int, ...],
) -> tuple[pd.DataFrame, tuple[str, ...]]:
    required = {
        "eval_date",
        "next_eval_date",
        "product_vt_symbol",
        "a_rank",
        "split",
        "label_values_read_allowed",
    }
    _required_columns(split_panel, required, "split_panel")
    frame = split_panel.copy()
    frame["eval_date"] = _date_strings(frame["eval_date"])
    frame["next_eval_date"] = _date_strings(frame["next_eval_date"])
    frame["a_rank"] = pd.to_numeric(frame["a_rank"], errors="raise").astype(int)
    main = frame[frame["split"].eq("development")].copy()
    if main.empty:
        raise AccountLabelPlanError("development_panel_empty")
    if not main["label_values_read_allowed"].astype(bool).all():
        raise AccountLabelPlanError("development_label_read_permission_missing")
    main.rename(columns={"a_rank": "candidate_rank"}, inplace=True)
    main["job_type"] = "main"
    main["job_id"] = main.apply(
        lambda row: (
            f"{str(row['eval_date']).replace('-', '')}_R{int(row['candidate_rank'])}"
        ),
        axis=1,
    )
    main["eligibility_key"] = main["job_id"]
    main = main[
        [
            "eval_date",
            "next_eval_date",
            "product_vt_symbol",
            "candidate_rank",
            "split",
            "job_type",
            "job_id",
            "eligibility_key",
        ]
    ].copy()

    months = sorted(main["eval_date"].unique())
    if len(set(sentinel_month_indexes)) != len(sentinel_month_indexes):
        raise AccountLabelPlanError("sentinel_month_index_duplicate")
    sentinels: list[dict[str, Any]] = []
    for month_index in sentinel_month_indexes:
        if month_index < 0 or month_index >= len(months):
            raise AccountLabelPlanError(f"sentinel_month_index_out_of_range:{month_index}")
        eval_date = months[month_index]
        anchor = main[
            main["eval_date"].eq(eval_date) & main["candidate_rank"].eq(10)
        ]
        if len(anchor) != 1:
            raise AccountLabelPlanError(f"sentinel_anchor_shape:{eval_date}:{len(anchor)}")
        row = anchor.iloc[0].to_dict()
        row["job_type"] = "A2_sentinel"
        row["job_id"] = f"{eval_date.replace('-', '')}_R10_A2"
        row["eligibility_key"] = str(anchor.iloc[0]["job_id"])
        sentinels.append(row)

    jobs = pd.concat([main, pd.DataFrame(sentinels)], ignore_index=True)
    type_order = pd.Categorical(
        jobs["job_type"], categories=["main", "A2_sentinel"], ordered=True
    )
    jobs = jobs.assign(_type_order=type_order)
    jobs.sort_values(
        ["eval_date", "candidate_rank", "_type_order"],
        inplace=True,
        kind="mergesort",
    )
    jobs.drop(columns="_type_order", inplace=True)
    jobs.reset_index(drop=True, inplace=True)
    if jobs["job_id"].duplicated().any():
        raise AccountLabelPlanError("development_job_id_duplicate")
    if jobs["split"].eq("sealed_account_label_holdout").any():
        raise AccountLabelPlanError("sealed_holdout_job_present")

    if len(months) < 2:
        raise AccountLabelPlanError("smoke_requires_two_development_months")
    first_date, second_date = months[:2]
    required_smoke = (
        f"{first_date.replace('-', '')}_R10",
        f"{first_date.replace('-', '')}_R10_A2",
        f"{second_date.replace('-', '')}_R10",
        f"{second_date.replace('-', '')}_R11",
    )
    missing_smoke = set(required_smoke) - set(jobs["job_id"])
    if missing_smoke:
        raise AccountLabelPlanError(f"smoke_job_missing:{sorted(missing_smoke)}")
    return jobs, required_smoke


def _assert_rows_equal(
    before: pd.DataFrame,
    after: pd.DataFrame,
    *,
    error: str,
) -> bool:
    left = before.reset_index(drop=True)
    right = after.reset_index(drop=True)
    if not left.equals(right):
        raise AccountLabelPlanError(error)
    return True


def build_path_consistent_eligibility(
    formal_eligibility: pd.DataFrame,
    clean_ranking: pd.DataFrame,
    *,
    eval_date: str,
    candidate_rank: int,
    fixed_product: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    formal = canonical_eligibility(formal_eligibility)
    ranking = canonical_clean_ranking(clean_ranking)
    if ranking["product_vt_symbol"].eq(str(fixed_product)).any():
        raise AccountLabelPlanError("fixed_product_in_clean_ranking")
    target_date = pd.Timestamp(eval_date).date().isoformat()
    target_source = ranking[
        ranking["eval_date"].eq(target_date)
        & ranking["a_rank"].eq(int(candidate_rank))
    ]
    if len(target_source) != 1:
        raise AccountLabelPlanError(
            f"candidate_source_shape:{target_date}:{candidate_rank}:{len(target_source)}"
        )
    clean_dates = sorted(ranking["eval_date"].unique())
    if target_date not in clean_dates:
        raise AccountLabelPlanError(f"target_date_not_clean:{target_date}")
    path_dates = [value for value in clean_dates if value <= target_date]
    first_clean_date = clean_dates[0]

    baseline = formal.copy()
    fixed_rows_checked = 0
    for clean_date in path_dates:
        formal_month = formal[formal["eval_date"].eq(clean_date)].sort_values("score_rank")
        if formal_month["score_rank"].tolist() != list(range(1, 12)):
            raise AccountLabelPlanError(f"formal_clean_month_shape:{clean_date}")
        fixed = formal_month[formal_month["score_rank"].eq(11)]
        if len(fixed) != 1 or str(fixed.iloc[0]["product_vt_symbol"]) != str(fixed_product):
            raise AccountLabelPlanError(f"formal_fixed_product_shape:{clean_date}")
        fixed_rows_checked += 1
        clean_top10 = ranking[
            ranking["eval_date"].eq(clean_date) & ranking["a_rank"].between(1, 10)
        ].sort_values("a_rank")
        if clean_top10["a_rank"].tolist() != list(range(1, 11)):
            raise AccountLabelPlanError(f"clean_top10_shape:{clean_date}")
        for row in clean_top10.itertuples(index=False):
            mask = baseline["eval_date"].eq(clean_date) & baseline["score_rank"].eq(
                int(row.a_rank)
            )
            if int(mask.sum()) != 1:
                raise AccountLabelPlanError(
                    f"formal_top10_target_shape:{clean_date}:{row.a_rank}:{int(mask.sum())}"
                )
            baseline.loc[mask, "product_vt_symbol"] = str(row.product_vt_symbol)
            baseline.loc[mask, "score"] = float(row.pit_logistic_probability)
            baseline.loc[mask, "score_type"] = CLEAN_BASELINE_SCORE_TYPE

    fixed_mask = formal["eval_date"].isin(path_dates) & formal["score_rank"].eq(11)
    _assert_rows_equal(
        formal.loc[fixed_mask],
        baseline.loc[fixed_mask],
        error="clean_baseline_fixed_product_drift",
    )
    preclean_mask = formal["eval_date"].lt(first_clean_date)
    _assert_rows_equal(
        formal.loc[preclean_mask],
        baseline.loc[preclean_mask],
        error="clean_baseline_preclean_drift",
    )
    future_mask = formal["eval_date"].gt(target_date)
    _assert_rows_equal(
        formal.loc[future_mask],
        baseline.loc[future_mask],
        error="clean_baseline_future_drift",
    )

    result = baseline.copy()
    if int(candidate_rank) > 10:
        target_mask = result["eval_date"].eq(target_date) & result["score_rank"].eq(10)
        if int(target_mask.sum()) != 1:
            raise AccountLabelPlanError(f"candidate_target_rank10_shape:{target_date}")
        source = target_source.iloc[0]
        result.loc[target_mask, "product_vt_symbol"] = str(source["product_vt_symbol"])
        result.loc[target_mask, "score"] = float(source["pit_logistic_probability"])
        result.loc[target_mask, "score_type"] = CANDIDATE_SCORE_TYPE

    diff = baseline.ne(result)
    changed_rows = diff.any(axis=1)
    allowed_change_columns = ["product_vt_symbol", "score", "score_type"]
    changed_columns = [column for column in allowed_change_columns if bool(diff[column].any())]
    forbidden_columns = [
        column
        for column in baseline.columns
        if column not in allowed_change_columns and bool(diff[column].any())
    ]
    if forbidden_columns:
        raise AccountLabelPlanError(f"candidate_forbidden_columns_changed:{forbidden_columns}")
    expected_changed_rows = 0 if int(candidate_rank) == 10 else 1
    if int(changed_rows.sum()) != expected_changed_rows:
        raise AccountLabelPlanError(
            f"candidate_changed_row_count:{int(changed_rows.sum())}:{expected_changed_rows}"
        )
    if expected_changed_rows:
        changed = result.loc[changed_rows]
        if not (
            changed["eval_date"].eq(target_date).all()
            and changed["score_rank"].eq(10).all()
        ):
            raise AccountLabelPlanError("candidate_change_outside_target_rank10")

    _assert_rows_equal(
        formal.loc[fixed_mask],
        result.loc[fixed_mask],
        error="candidate_fixed_product_drift",
    )
    _assert_rows_equal(
        formal.loc[preclean_mask],
        result.loc[preclean_mask],
        error="candidate_preclean_drift",
    )
    _assert_rows_equal(
        formal.loc[future_mask],
        result.loc[future_mask],
        error="candidate_future_drift",
    )
    result.sort_values(["eval_date", "score_rank"], inplace=True, kind="mergesort")
    result.reset_index(drop=True, inplace=True)
    baseline.sort_values(["eval_date", "score_rank"], inplace=True, kind="mergesort")
    baseline.reset_index(drop=True, inplace=True)
    return result, {
        "clean_baseline_sha256": dataframe_sha256(baseline),
        "candidate_eligibility_sha256": dataframe_sha256(result),
        "clean_months_overwritten": int(len(path_dates)),
        "clean_top10_rows_overwritten": int(len(path_dates) * 10),
        "fixed_product_rows_checked": int(fixed_rows_checked),
        "fixed_product_rows_unchanged": True,
        "preclean_rows_unchanged": True,
        "future_rows_unchanged": True,
        "candidate_changed_row_count_vs_clean_baseline": int(changed_rows.sum()),
        "candidate_changed_cell_count_vs_clean_baseline": int(diff.to_numpy().sum()),
        "candidate_changed_columns": changed_columns,
    }


def build_eligibility_audit(
    formal_eligibility: pd.DataFrame,
    clean_ranking: pd.DataFrame,
    jobs: pd.DataFrame,
    *,
    fixed_product: str,
) -> pd.DataFrame:
    main = jobs[jobs["job_type"].eq("main")].copy()
    rows: list[dict[str, Any]] = []
    for job in main.sort_values(["eval_date", "candidate_rank"]).itertuples(index=False):
        _, audit = build_path_consistent_eligibility(
            formal_eligibility,
            clean_ranking,
            eval_date=str(job.eval_date),
            candidate_rank=int(job.candidate_rank),
            fixed_product=fixed_product,
        )
        rows.append(
            {
                "job_id": str(job.job_id),
                "eval_date": str(job.eval_date),
                "next_eval_date": str(job.next_eval_date),
                "candidate_rank": int(job.candidate_rank),
                "product_vt_symbol": str(job.product_vt_symbol),
                **{
                    key: (
                        "|".join(value) if key == "candidate_changed_columns" else value
                    )
                    for key, value in audit.items()
                },
            }
        )
    result = pd.DataFrame(rows)
    if result["job_id"].duplicated().any():
        raise AccountLabelPlanError("eligibility_audit_job_duplicate")
    return result

