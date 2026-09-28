"""Build the frozen post-listing PIT market-context feature family."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd


PASS_DECISION = "stage002_market_context_features_pass_ready_for_ranker_preregistration"
FAIL_DECISION = "stage002_market_context_features_fail_stop_no_ranker"
FEATURE_COLUMNS = [
    "candidate_top9_corr_120d_delta_vs_rank10",
    "candidate_top9_downside_corr_120d_delta_vs_rank10",
    "candidate_volatility_120d_log_ratio_vs_rank10",
    "candidate_downside_deviation_120d_log_ratio_vs_rank10",
    "top9_plus_candidate_compound_drawdown_improvement_120d_vs_rank10",
    "top9_plus_candidate_sharpe_improvement_120d_vs_rank10",
]


class MarketContextFeatureError(RuntimeError):
    """Raised when a frozen feature-contract invariant is violated."""


def _require_columns(frame: pd.DataFrame, columns: set[str], name: str) -> None:
    if missing := sorted(columns - set(frame.columns)):
        raise MarketContextFeatureError(f"{name}_columns_missing:{','.join(missing)}")


def _as_bool(series: pd.Series, name: str) -> pd.Series:
    if pd.api.types.is_bool_dtype(series.dtype):
        return series.fillna(False).astype(bool)
    values = series.astype(str).str.strip().str.lower()
    if not set(values.unique()).issubset({"true", "false"}):
        raise MarketContextFeatureError(f"{name}_boolean_invalid")
    return values.eq("true")


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
    _require_columns(product_returns, required, "product_returns")
    frame = product_returns.loc[:, sorted(required)].copy()
    frame["product_vt_symbol"] = frame["product_vt_symbol"].astype(str)
    frame["selection_date"] = pd.to_datetime(frame["selection_date"], errors="raise").dt.normalize()
    frame["return_date"] = pd.to_datetime(frame["return_date"], errors="raise").dt.normalize()
    frame["selected_contract_vt"] = frame["selected_contract_vt"].fillna("").astype(str)
    frame["product_return"] = pd.to_numeric(frame["product_return"], errors="coerce")
    frame["status"] = frame["status"].astype(str)
    frame["fallback_used"] = _as_bool(frame["fallback_used"], "fallback_used")
    frame["cross_contract_price_used"] = _as_bool(
        frame["cross_contract_price_used"], "cross_contract_price_used"
    )
    if frame.duplicated(["return_date", "product_vt_symbol"]).any():
        raise MarketContextFeatureError("product_return_date_product_duplicate")
    return frame.sort_values(
        ["return_date", "product_vt_symbol"], kind="mergesort"
    ).reset_index(drop=True)


def _return_vector(
    indexed_returns: pd.DataFrame,
    window_dates: pd.DatetimeIndex,
    product: str,
) -> np.ndarray:
    values: list[float] = []
    for return_date in window_dates:
        key = (pd.Timestamp(return_date), str(product))
        if key not in indexed_returns.index:
            raise MarketContextFeatureError(
                f"required_return_missing:{product}:{pd.Timestamp(return_date).date()}"
            )
        row = indexed_returns.loc[key]
        value = float(row["product_return"])
        if (
            str(row["status"]) != "ok"
            or not np.isfinite(value)
            or value <= -1.0
            or pd.Timestamp(row["selection_date"]) >= pd.Timestamp(return_date)
            or bool(row["fallback_used"])
            or bool(row["cross_contract_price_used"])
            or str(row["selected_contract_vt"]) == ""
        ):
            raise MarketContextFeatureError(
                f"required_return_invalid:{product}:{pd.Timestamp(return_date).date()}"
            )
        values.append(value)
    return np.asarray(values, dtype=float)


def _std(values: np.ndarray, name: str) -> float:
    result = float(np.std(values, ddof=1))
    if not np.isfinite(result) or result <= 0.0:
        raise MarketContextFeatureError(f"{name}_std_not_positive")
    return result


def _corr(left: np.ndarray, right: np.ndarray, name: str) -> float:
    _std(left, f"{name}_left")
    _std(right, f"{name}_right")
    result = float(np.corrcoef(left, right)[0, 1])
    if not np.isfinite(result):
        raise MarketContextFeatureError(f"{name}_nonfinite")
    return result


def _downside_deviation(values: np.ndarray, name: str) -> float:
    result = float(np.sqrt(np.mean(np.minimum(values, 0.0) ** 2)) * np.sqrt(252.0))
    if not np.isfinite(result) or result <= 0.0:
        raise MarketContextFeatureError(f"{name}_not_positive")
    return result


def _compound_drawdown(returns: np.ndarray) -> float:
    if np.any(returns <= -1.0) or not np.isfinite(returns).all():
        raise MarketContextFeatureError("portfolio_return_invalid")
    wealth = np.cumprod(1.0 + returns)
    peaks = np.maximum.accumulate(np.concatenate(([1.0], wealth)))[1:]
    result = float(np.min(wealth / peaks - 1.0))
    if not np.isfinite(result) or result > 0.0:
        raise MarketContextFeatureError("compound_drawdown_invalid")
    return result


def _sharpe(returns: np.ndarray, name: str) -> float:
    result = float(np.mean(returns) / _std(returns, name) * np.sqrt(252.0))
    if not np.isfinite(result):
        raise MarketContextFeatureError(f"{name}_nonfinite")
    return result


def _feature_values(
    top9_return: np.ndarray,
    baseline_return: np.ndarray,
    candidate_return: np.ndarray,
    *,
    top_rank_count: int,
    minimum_downside_days: int,
) -> tuple[list[float], dict[str, float | int]]:
    downside = top9_return < 0.0
    downside_days = int(downside.sum())
    if downside_days < minimum_downside_days:
        raise MarketContextFeatureError(f"top9_downside_days_below_minimum:{downside_days}")

    baseline_corr = _corr(baseline_return, top9_return, "baseline_top9_corr")
    candidate_corr = _corr(candidate_return, top9_return, "candidate_top9_corr")
    baseline_down_corr = _corr(
        baseline_return[downside], top9_return[downside], "baseline_top9_down_corr"
    )
    candidate_down_corr = _corr(
        candidate_return[downside], top9_return[downside], "candidate_top9_down_corr"
    )
    baseline_vol = _std(baseline_return, "baseline_volatility") * np.sqrt(252.0)
    candidate_vol = _std(candidate_return, "candidate_volatility") * np.sqrt(252.0)
    baseline_down_dev = _downside_deviation(baseline_return, "baseline_downside_deviation")
    candidate_down_dev = _downside_deviation(candidate_return, "candidate_downside_deviation")

    denominator = float(top_rank_count + 1)
    baseline_portfolio = (top_rank_count * top9_return + baseline_return) / denominator
    candidate_portfolio = (top_rank_count * top9_return + candidate_return) / denominator
    baseline_drawdown = _compound_drawdown(baseline_portfolio)
    candidate_drawdown = _compound_drawdown(candidate_portfolio)
    baseline_sharpe = _sharpe(baseline_portfolio, "baseline_portfolio_sharpe")
    candidate_sharpe = _sharpe(candidate_portfolio, "candidate_portfolio_sharpe")
    values = [
        candidate_corr - baseline_corr,
        candidate_down_corr - baseline_down_corr,
        float(np.log(candidate_vol / baseline_vol)),
        float(np.log(candidate_down_dev / baseline_down_dev)),
        candidate_drawdown - baseline_drawdown,
        candidate_sharpe - baseline_sharpe,
    ]
    if not np.isfinite(np.asarray(values, dtype=float)).all():
        raise MarketContextFeatureError("feature_value_nonfinite")
    diagnostics: dict[str, float | int] = {
        "downside_day_count": downside_days,
        "baseline_portfolio_drawdown": baseline_drawdown,
        "baseline_portfolio_sharpe": baseline_sharpe,
    }
    return values, diagnostics


def build_market_context_features(
    ranked_a_panel: pd.DataFrame,
    coverage: pd.DataFrame,
    month_audit: pd.DataFrame,
    product_returns: pd.DataFrame,
    *,
    window_days: int,
    top_rank_count: int,
    minimum_downside_days: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Construct six frozen context features for active rank10+ rows."""
    if window_days <= 1 or top_rank_count <= 0 or minimum_downside_days < 2:
        raise MarketContextFeatureError("feature_contract_invalid")
    ranked_required = {
        "eval_date",
        "product_vt_symbol",
        "window_id",
        "pit_logistic_probability",
        "a_rank",
        "role",
    }
    coverage_required = ranked_required | {"window_complete", "context_eligible"}
    _require_columns(ranked_a_panel, ranked_required, "ranked_a_panel")
    _require_columns(coverage, coverage_required, "coverage")
    _require_columns(month_audit, {"eval_date", "window_id", "overlay_active"}, "month_audit")

    ranked = ranked_a_panel.loc[:, sorted(ranked_required)].copy()
    covered = coverage.loc[:, sorted(coverage_required)].copy()
    months = month_audit.loc[:, ["eval_date", "window_id", "overlay_active"]].copy()
    for frame in [ranked, covered, months]:
        frame["eval_date"] = pd.to_datetime(frame["eval_date"], errors="raise").dt.normalize()
    covered["window_complete"] = _as_bool(covered["window_complete"], "window_complete")
    covered["context_eligible"] = _as_bool(covered["context_eligible"], "context_eligible")
    months["overlay_active"] = _as_bool(months["overlay_active"], "overlay_active")
    if ranked.duplicated(["eval_date", "product_vt_symbol"]).any():
        raise MarketContextFeatureError("ranked_eval_product_duplicate")
    if covered.duplicated(["eval_date", "product_vt_symbol"]).any():
        raise MarketContextFeatureError("coverage_eval_product_duplicate")
    rank_identity = ranked.merge(
        covered,
        on=["eval_date", "product_vt_symbol"],
        suffixes=("_ranked", "_coverage"),
        validate="one_to_one",
    )
    for column in ["window_id", "a_rank", "role"]:
        if not rank_identity[f"{column}_ranked"].astype(str).equals(
            rank_identity[f"{column}_coverage"].astype(str)
        ):
            raise MarketContextFeatureError(f"rank_coverage_{column}_mismatch")

    returns = _normalise_returns(product_returns)
    indexed_returns = returns.set_index(["return_date", "product_vt_symbol"])
    all_dates = pd.DatetimeIndex(sorted(returns["return_date"].unique()))
    active_months = months[months["overlay_active"]].copy()
    feature_rows: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []
    for month_row in active_months.sort_values("eval_date").itertuples(index=False):
        eval_date = pd.Timestamp(month_row.eval_date)
        month_ranked = ranked[ranked["eval_date"].eq(eval_date)].sort_values("a_rank")
        top = month_ranked[month_ranked["role"].eq("top9")]
        if len(top) != top_rank_count:
            raise MarketContextFeatureError("active_month_top_count_invalid")
        month_coverage = covered[
            covered["eval_date"].eq(eval_date)
            & covered["role"].isin(["a_rank10", "challenger"])
            & covered["window_complete"]
            & covered["context_eligible"]
        ].sort_values("a_rank")
        anchor = month_coverage[month_coverage["role"].eq("a_rank10")]
        if len(anchor) != 1:
            raise MarketContextFeatureError("active_month_anchor_count_invalid")

        window_dates = all_dates[all_dates <= eval_date][-window_days:]
        if len(window_dates) != window_days:
            raise MarketContextFeatureError("window_date_count_invalid")
        top_vectors = [
            _return_vector(indexed_returns, window_dates, str(product))
            for product in top["product_vt_symbol"]
        ]
        top9_return = np.mean(np.vstack(top_vectors), axis=0)
        baseline_product = str(anchor.iloc[0]["product_vt_symbol"])
        baseline_return = _return_vector(indexed_returns, window_dates, baseline_product)
        downside_day_count = int((top9_return < 0.0).sum())
        month_feature_count = 0
        for candidate in month_coverage.itertuples(index=False):
            candidate_return = _return_vector(
                indexed_returns, window_dates, str(candidate.product_vt_symbol)
            )
            values, diagnostics = _feature_values(
                top9_return,
                baseline_return,
                candidate_return,
                top_rank_count=top_rank_count,
                minimum_downside_days=minimum_downside_days,
            )
            row: dict[str, Any] = {
                "eval_date": eval_date,
                "product_vt_symbol": str(candidate.product_vt_symbol),
                "window_id": str(candidate.window_id),
                "a_rank": int(candidate.a_rank),
                "role": str(candidate.role),
                "pit_logistic_probability": float(candidate.pit_logistic_probability),
                "window_start": window_dates.min(),
                "window_end": window_dates.max(),
                "window_date_count": int(len(window_dates)),
                "downside_day_count": int(diagnostics["downside_day_count"]),
                "top9_products": "|".join(top["product_vt_symbol"].astype(str)),
            }
            row.update(dict(zip(FEATURE_COLUMNS, values, strict=True)))
            feature_rows.append(row)
            month_feature_count += 1
        audit_rows.append(
            {
                "eval_date": eval_date,
                "window_id": str(month_row.window_id),
                "window_start": window_dates.min(),
                "window_end": window_dates.max(),
                "window_date_count": int(len(window_dates)),
                "top_count": int(len(top)),
                "feature_row_count": int(month_feature_count),
                "downside_day_count": downside_day_count,
                "future_return_rows_used": 0,
            }
        )
    features = pd.DataFrame(feature_rows).sort_values(
        ["eval_date", "a_rank", "product_vt_symbol"], kind="mergesort"
    ).reset_index(drop=True)
    audits = pd.DataFrame(audit_rows).sort_values("eval_date", kind="mergesort").reset_index(drop=True)
    return features, audits


def assess_feature_contract(
    features: pd.DataFrame,
    month_audit: pd.DataFrame,
    *,
    accepted_window_ids: Sequence[str],
    expected_rows: int,
    expected_months: int,
    expected_anchor_rows: int,
    expected_challenger_rows: int,
    expected_min_rows_per_month: int,
    expected_max_rows_per_month: int,
    window_days: int,
    minimum_downside_days: int,
    minimum_unique_challenger_values: int,
) -> dict[str, Any]:
    _require_columns(features, set(FEATURE_COLUMNS) | {"eval_date", "window_id", "role"}, "features")
    matrix = features[FEATURE_COLUMNS].to_numpy(float)
    anchor_matrix = features.loc[features["role"].eq("a_rank10"), FEATURE_COLUMNS].to_numpy(float)
    challengers = features[features["role"].eq("challenger")]
    month_counts = features.groupby("eval_date").size()
    unique_values = {
        feature: int(challengers[feature].nunique(dropna=True)) for feature in FEATURE_COLUMNS
    }
    standard_deviations = {
        feature: float(np.std(challengers[feature].to_numpy(float), ddof=0))
        for feature in FEATURE_COLUMNS
    }
    accepted_ids = sorted(str(item) for item in accepted_window_ids)
    nonzero_by_fold = {
        window_id: {
            feature: int(
                (
                    challengers.loc[
                        challengers["window_id"].astype(str).eq(window_id), feature
                    ].abs()
                    > 1e-12
                ).sum()
            )
            for feature in FEATURE_COLUMNS
        }
        for window_id in accepted_ids
    }
    gates = {
        "row_count_exact": len(features) == expected_rows,
        "month_count_exact": features["eval_date"].nunique() == expected_months,
        "feature_count_exact": len(FEATURE_COLUMNS) == 6,
        "anchor_row_count_exact": int(features["role"].eq("a_rank10").sum())
        == expected_anchor_rows,
        "challenger_row_count_exact": int(features["role"].eq("challenger").sum())
        == expected_challenger_rows,
        "month_row_min_exact": int(month_counts.min()) == expected_min_rows_per_month,
        "month_row_max_exact": int(month_counts.max()) == expected_max_rows_per_month,
        "feature_values_finite": bool(np.isfinite(matrix).all()),
        "anchor_features_exact_zero": bool(np.array_equal(anchor_matrix, np.zeros_like(anchor_matrix))),
        "challenger_unique_values_minimum": all(
            count >= minimum_unique_challenger_values for count in unique_values.values()
        ),
        "challenger_standard_deviation_positive": all(
            value > 1e-12 for value in standard_deviations.values()
        ),
        "feature_nonzero_in_every_fold": all(
            count > 0 for fold in nonzero_by_fold.values() for count in fold.values()
        ),
        "accepted_fold_identity_exact": set(features["window_id"].astype(str)) == set(accepted_ids),
        "window_days_exact": bool(month_audit["window_date_count"].eq(window_days).all()),
        "window_end_not_after_eval": bool(
            (
                pd.to_datetime(month_audit["window_end"])
                <= pd.to_datetime(month_audit["eval_date"])
            ).all()
        ),
        "downside_days_minimum": bool(
            month_audit["downside_day_count"].ge(minimum_downside_days).all()
        ),
        "future_return_rows_used_zero": int(month_audit["future_return_rows_used"].sum()) == 0,
    }
    passed = all(bool(value) for value in gates.values())
    return {
        "decision": PASS_DECISION if passed else FAIL_DECISION,
        "all_gates_passed": bool(passed),
        "gates": gates,
        "feature_rows": int(len(features)),
        "feature_months": int(features["eval_date"].nunique()),
        "feature_count": int(len(FEATURE_COLUMNS)),
        "feature_columns": list(FEATURE_COLUMNS),
        "anchor_rows": int(features["role"].eq("a_rank10").sum()),
        "challenger_rows": int(features["role"].eq("challenger").sum()),
        "month_row_min": int(month_counts.min()),
        "month_row_max": int(month_counts.max()),
        "minimum_downside_days_observed": int(month_audit["downside_day_count"].min()),
        "challenger_unique_values": unique_values,
        "challenger_standard_deviations": standard_deviations,
        "nonzero_values_by_fold": nonzero_by_fold,
    }

