"""Coverage audit for post-listing PIT market-context inputs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import pandas as pd


PASS_DECISION = "stage001_market_context_coverage_pass_ready_for_feature_preregistration"
FAIL_DECISION = "stage001_market_context_coverage_fail_stop_no_features"


class MarketContextCoverageError(RuntimeError):
    """Raised when the frozen coverage contract cannot be evaluated."""


def _required_columns(frame: pd.DataFrame, columns: set[str], name: str) -> None:
    if missing := sorted(columns - set(frame.columns)):
        raise MarketContextCoverageError(f"{name}_columns_missing:{','.join(missing)}")


def _bool_values(series: pd.Series, name: str) -> pd.Series:
    if pd.api.types.is_bool_dtype(series.dtype):
        return series.fillna(False).astype(bool)
    normalised = series.astype(str).str.strip().str.lower()
    allowed = {"true", "false"}
    if not set(normalised.unique()).issubset(allowed):
        raise MarketContextCoverageError(f"{name}_boolean_invalid")
    return normalised.eq("true")


def assign_anchor_roles(scores: pd.DataFrame, *, top_rank_count: int) -> pd.DataFrame:
    """Build the stable conditional-PIT logistic anchor ranking."""
    if top_rank_count <= 0:
        raise MarketContextCoverageError("top_rank_count_invalid")
    _required_columns(
        scores,
        {"eval_date", "product_vt_symbol", "pit_logistic_probability", "window_id"},
        "scores",
    )
    frame = scores.loc[
        :, ["eval_date", "product_vt_symbol", "pit_logistic_probability", "window_id"]
    ].copy()
    frame["eval_date"] = pd.to_datetime(frame["eval_date"], errors="raise").dt.normalize()
    frame["product_vt_symbol"] = frame["product_vt_symbol"].astype(str)
    frame["window_id"] = frame["window_id"].astype(str)
    frame["pit_logistic_probability"] = pd.to_numeric(
        frame["pit_logistic_probability"], errors="raise"
    ).astype(float)
    if not np.isfinite(frame["pit_logistic_probability"].to_numpy(float)).all():
        raise MarketContextCoverageError("score_nonfinite")
    if frame.duplicated(["eval_date", "product_vt_symbol"]).any():
        raise MarketContextCoverageError("score_eval_product_duplicate")
    if frame["product_vt_symbol"].eq("").any():
        raise MarketContextCoverageError("score_product_empty")
    month_windows = frame[["eval_date", "window_id"]].drop_duplicates()
    if month_windows.duplicated("eval_date").any():
        raise MarketContextCoverageError("score_month_window_id_duplicate")

    frame = frame.sort_values(
        ["eval_date", "pit_logistic_probability", "product_vt_symbol"],
        ascending=[True, False, True],
        kind="mergesort",
    ).reset_index(drop=True)
    frame["a_rank"] = frame.groupby("eval_date", sort=False).cumcount() + 1
    minimum_products = int(frame.groupby("eval_date").size().min())
    if minimum_products <= top_rank_count + 1:
        raise MarketContextCoverageError("score_month_has_too_few_challengers")
    frame["role"] = np.select(
        [
            frame["a_rank"].le(top_rank_count),
            frame["a_rank"].eq(top_rank_count + 1),
        ],
        ["top9", "a_rank10"],
        default="challenger",
    )
    return frame


def _normalise_returns(product_returns: pd.DataFrame) -> pd.DataFrame:
    required = {
        "product_vt_symbol",
        "selection_date",
        "return_date",
        "selected_contract_vt",
        "product_return",
        "status",
        "fallback_used",
        "cross_contract_price_used",
    }
    _required_columns(product_returns, required, "product_returns")
    frame = product_returns.loc[:, sorted(required)].copy()
    frame["product_vt_symbol"] = frame["product_vt_symbol"].astype(str)
    frame["selection_date"] = pd.to_datetime(frame["selection_date"], errors="raise").dt.normalize()
    frame["return_date"] = pd.to_datetime(frame["return_date"], errors="raise").dt.normalize()
    frame["selected_contract_vt"] = frame["selected_contract_vt"].fillna("").astype(str)
    frame["product_return"] = pd.to_numeric(frame["product_return"], errors="coerce")
    frame["status"] = frame["status"].astype(str)
    frame["fallback_used"] = _bool_values(frame["fallback_used"], "fallback_used")
    frame["cross_contract_price_used"] = _bool_values(
        frame["cross_contract_price_used"], "cross_contract_price_used"
    )
    if frame.duplicated(["return_date", "product_vt_symbol"]).any():
        raise MarketContextCoverageError("product_return_date_product_duplicate")
    return frame.sort_values(
        ["return_date", "product_vt_symbol"], kind="mergesort"
    ).reset_index(drop=True)


def audit_context_windows(
    ranked_scores: pd.DataFrame,
    product_returns: pd.DataFrame,
    *,
    window_days: int,
    top_rank_count: int,
    minimum_complete_challengers: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Audit every anchor product without removing incomplete A rows."""
    if window_days <= 0 or minimum_complete_challengers <= 0:
        raise MarketContextCoverageError("window_contract_invalid")
    _required_columns(
        ranked_scores,
        {
            "eval_date",
            "product_vt_symbol",
            "pit_logistic_probability",
            "window_id",
            "a_rank",
            "role",
        },
        "ranked_scores",
    )
    ranked = ranked_scores.copy()
    ranked["eval_date"] = pd.to_datetime(ranked["eval_date"], errors="raise").dt.normalize()
    returns = _normalise_returns(product_returns)
    all_dates = pd.DatetimeIndex(sorted(returns["return_date"].unique()))
    indexed_returns = returns.set_index(["return_date", "product_vt_symbol"])

    coverage_rows: list[dict[str, Any]] = []
    missing_rows: list[dict[str, Any]] = []
    month_rows: list[dict[str, Any]] = []
    for eval_date, month in ranked.groupby("eval_date", sort=True):
        month = month.sort_values("a_rank", kind="mergesort")
        expected_ranks = list(range(1, len(month) + 1))
        if month["a_rank"].astype(int).tolist() != expected_ranks:
            raise MarketContextCoverageError("a_rank_not_contiguous")
        if int(month["role"].eq("top9").sum()) != top_rank_count:
            raise MarketContextCoverageError("top_role_count_invalid")
        if int(month["role"].eq("a_rank10").sum()) != 1:
            raise MarketContextCoverageError("anchor_role_count_invalid")

        window_dates = all_dates[all_dates <= eval_date][-window_days:]
        month_coverage: list[dict[str, Any]] = []
        for item in month.itertuples(index=False):
            valid_count = 0
            for return_date in window_dates:
                key = (pd.Timestamp(return_date), str(item.product_vt_symbol))
                if key not in indexed_returns.index:
                    status = "return_row_missing"
                    valid = False
                else:
                    source = indexed_returns.loc[key]
                    status = str(source["status"])
                    valid = (
                        status == "ok"
                        and np.isfinite(float(source["product_return"]))
                        and pd.Timestamp(source["selection_date"]) < pd.Timestamp(return_date)
                        and not bool(source["fallback_used"])
                        and not bool(source["cross_contract_price_used"])
                        and str(source["selected_contract_vt"]) != ""
                    )
                    if status == "ok" and pd.Timestamp(source["selection_date"]) >= pd.Timestamp(return_date):
                        status = "pit_selection_not_before_return"
                    elif status == "ok" and bool(source["fallback_used"]):
                        status = "fallback_used"
                    elif status == "ok" and bool(source["cross_contract_price_used"]):
                        status = "cross_contract_price_used"
                    elif status == "ok" and str(source["selected_contract_vt"]) == "":
                        status = "selected_contract_empty"
                    elif status == "ok" and not np.isfinite(float(source["product_return"])):
                        status = "ok_return_nonfinite"
                valid_count += int(valid)
                if not valid:
                    missing_rows.append(
                        {
                            "eval_date": pd.Timestamp(eval_date),
                            "return_date": pd.Timestamp(return_date),
                            "product_vt_symbol": str(item.product_vt_symbol),
                            "a_rank": int(item.a_rank),
                            "role": str(item.role),
                            "status": status,
                        }
                    )
            complete = len(window_dates) == window_days and valid_count == window_days
            row = {
                "eval_date": pd.Timestamp(eval_date),
                "product_vt_symbol": str(item.product_vt_symbol),
                "window_id": str(item.window_id),
                "pit_logistic_probability": float(item.pit_logistic_probability),
                "a_rank": int(item.a_rank),
                "role": str(item.role),
                "valid_return_count": int(valid_count),
                "required_return_count": int(window_days),
                "window_complete": bool(complete),
                "context_eligible": bool(
                    complete and str(item.role) in {"a_rank10", "challenger"}
                ),
            }
            month_coverage.append(row)
            coverage_rows.append(row)

        month_coverage_frame = pd.DataFrame(month_coverage)
        complete_top = int(
            (
                month_coverage_frame["role"].eq("top9")
                & month_coverage_frame["window_complete"]
            ).sum()
        )
        complete_anchor = int(
            (
                month_coverage_frame["role"].eq("a_rank10")
                & month_coverage_frame["window_complete"]
            ).sum()
        )
        complete_challengers = int(
            (
                month_coverage_frame["role"].eq("challenger")
                & month_coverage_frame["window_complete"]
            ).sum()
        )
        overlay_active = (
            len(window_dates) == window_days
            and complete_top == top_rank_count
            and complete_anchor == 1
            and complete_challengers >= minimum_complete_challengers
        )
        month_rows.append(
            {
                "eval_date": pd.Timestamp(eval_date),
                "window_id": str(month["window_id"].iloc[0]),
                "window_start": window_dates.min() if len(window_dates) else pd.NaT,
                "window_end": window_dates.max() if len(window_dates) else pd.NaT,
                "window_date_count": int(len(window_dates)),
                "product_count": int(len(month)),
                "top_count": int(month["role"].eq("top9").sum()),
                "complete_top_count": complete_top,
                "anchor_count": int(month["role"].eq("a_rank10").sum()),
                "complete_anchor_count": complete_anchor,
                "challenger_count": int(month["role"].eq("challenger").sum()),
                "complete_challenger_count": complete_challengers,
                "overlay_active": bool(overlay_active),
                "future_return_rows_used": 0,
            }
        )
    coverage = pd.DataFrame(coverage_rows)
    missing = pd.DataFrame(missing_rows).reindex(
        columns=["eval_date", "return_date", "product_vt_symbol", "a_rank", "role", "status"]
    )
    months = pd.DataFrame(month_rows)
    return coverage, missing, months


def assess_context_coverage(
    ranked_scores: pd.DataFrame,
    coverage: pd.DataFrame,
    missing: pd.DataFrame,
    month_audit: pd.DataFrame,
    product_returns: pd.DataFrame,
    *,
    accepted_window_ids: Sequence[str],
    expected_rows: int,
    expected_months: int,
    expected_min_products: int,
    expected_max_products: int,
    top_rank_count: int,
    expected_top_rows: int,
    expected_anchor_rows: int,
    expected_challenger_rows: int,
    window_days: int,
    minimum_active_months: int,
    minimum_active_months_by_year: Mapping[int, int],
    minimum_active_months_per_fold: int,
    minimum_complete_challengers: int,
) -> dict[str, Any]:
    returns = _normalise_returns(product_returns)
    active = month_audit[month_audit["overlay_active"].astype(bool)].copy()
    active["year"] = pd.to_datetime(active["eval_date"]).dt.year
    active_months_by_year = {
        str(year): int(active["year"].eq(int(year)).sum())
        for year in sorted(minimum_active_months_by_year)
    }
    accepted_ids = [str(item) for item in accepted_window_ids]
    active_months_by_fold = {
        window_id: int(active["window_id"].astype(str).eq(window_id).sum())
        for window_id in sorted(accepted_ids)
    }
    month_counts = ranked_scores.groupby("eval_date").size()
    pit_violation_rows = int((returns["selection_date"] >= returns["return_date"]).sum())
    fallback_rows = int(returns["fallback_used"].sum())
    cross_contract_rows = int(returns["cross_contract_price_used"].sum())
    ok_nonfinite_rows = int(
        (
            returns["status"].eq("ok")
            & ~np.isfinite(returns["product_return"].to_numpy(float))
        ).sum()
    )
    ok_empty_contract_rows = int(
        (returns["status"].eq("ok") & returns["selected_contract_vt"].eq("")).sum()
    )
    score_window_ids = set(ranked_scores["window_id"].astype(str))
    gates = {
        "score_row_count_exact": len(ranked_scores) == expected_rows,
        "coverage_row_count_exact": len(coverage) == expected_rows,
        "month_count_exact": ranked_scores["eval_date"].nunique() == expected_months,
        "month_product_min_exact": int(month_counts.min()) == expected_min_products,
        "month_product_max_exact": int(month_counts.max()) == expected_max_products,
        "top_row_count_exact": int(ranked_scores["role"].eq("top9").sum()) == expected_top_rows,
        "anchor_row_count_exact": int(ranked_scores["role"].eq("a_rank10").sum())
        == expected_anchor_rows,
        "challenger_row_count_exact": int(ranked_scores["role"].eq("challenger").sum())
        == expected_challenger_rows,
        "window_dates_complete": bool(month_audit["window_date_count"].eq(window_days).all()),
        "future_return_rows_used_zero": int(month_audit["future_return_rows_used"].sum()) == 0,
        "pit_violation_rows_zero": pit_violation_rows == 0,
        "fallback_rows_zero": fallback_rows == 0,
        "cross_contract_rows_zero": cross_contract_rows == 0,
        "ok_nonfinite_rows_zero": ok_nonfinite_rows == 0,
        "ok_empty_contract_rows_zero": ok_empty_contract_rows == 0,
        "accepted_fold_identity_exact": score_window_ids == set(accepted_ids),
        "active_months_minimum": len(active) >= minimum_active_months,
        "active_months_each_year_minimum": all(
            active_months_by_year[str(year)] >= int(minimum)
            for year, minimum in minimum_active_months_by_year.items()
        ),
        "active_months_each_fold_minimum": all(
            count >= minimum_active_months_per_fold
            for count in active_months_by_fold.values()
        ),
        "active_month_challenger_minimum": bool(
            active["complete_challenger_count"].ge(minimum_complete_challengers).all()
        ),
    }
    passed = all(bool(value) for value in gates.values())
    return {
        "decision": PASS_DECISION if passed else FAIL_DECISION,
        "all_gates_passed": bool(passed),
        "gates": gates,
        "score_rows": int(len(ranked_scores)),
        "coverage_rows": int(len(coverage)),
        "oos_months": int(ranked_scores["eval_date"].nunique()),
        "month_product_min": int(month_counts.min()),
        "month_product_max": int(month_counts.max()),
        "top_rows": int(ranked_scores["role"].eq("top9").sum()),
        "anchor_rows": int(ranked_scores["role"].eq("a_rank10").sum()),
        "challenger_rows": int(ranked_scores["role"].eq("challenger").sum()),
        "complete_top_rows": int(
            (coverage["role"].eq("top9") & coverage["window_complete"].astype(bool)).sum()
        ),
        "complete_anchor_rows": int(
            (coverage["role"].eq("a_rank10") & coverage["window_complete"].astype(bool)).sum()
        ),
        "complete_challenger_rows": int(
            (coverage["role"].eq("challenger") & coverage["window_complete"].astype(bool)).sum()
        ),
        "active_months": int(len(active)),
        "inactive_months": int(len(month_audit) - len(active)),
        "active_months_by_year": active_months_by_year,
        "active_months_by_fold": active_months_by_fold,
        "missing_window_cells": int(len(missing)),
        "pit_violation_rows": pit_violation_rows,
        "fallback_rows": fallback_rows,
        "cross_contract_rows": cross_contract_rows,
        "ok_nonfinite_rows": ok_nonfinite_rows,
        "ok_empty_contract_rows": ok_empty_contract_rows,
    }

