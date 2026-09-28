from __future__ import annotations

import sys
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[4]
V2_TOOLS = (
    REPO_ROOT
    / "research/lines/futures_trend_xgboost_pit_full_market_daily_ranker_v2/tools"
)
V1_TOOLS = (
    REPO_ROOT
    / "research/lines/futures_trend_xgboost_pit_full_market_daily_ranker/tools"
)
for tools_dir in (V2_TOOLS, V1_TOOLS):
    if str(tools_dir) not in sys.path:
        sys.path.insert(0, str(tools_dir))

from daily_ranker_contract import MODEL_FEATURES
from daily_ranker_development import (
    MODEL_PARAMS,
    build_estimator_audit,
    build_ranker_arrays,
    fit_repeated_ranker,
)


LABEL_COLUMNS = [
    "future_trend_capture_quality",
    "future_abs_log_return",
    "future_oriented_max_drawdown",
    "trend_quality_relevance",
]
FIXED_PRODUCT = "fu.SHFE"
EFFECT_COMPONENTS = {
    "quality": "future_trend_capture_quality",
    "abs_log_return": "future_abs_log_return",
    "oriented_max_drawdown": "future_oriented_max_drawdown",
}


class TrendQualityRankerError(RuntimeError):
    pass


def _normalise_date(series: pd.Series) -> pd.Series:
    result = pd.to_datetime(series, errors="coerce").dt.normalize()
    if result.isna().any():
        raise TrendQualityRankerError("invalid_date")
    return result


def _require_columns(
    frame: pd.DataFrame, columns: Sequence[str], frame_name: str
) -> None:
    missing = sorted(set(columns).difference(frame.columns))
    if missing:
        raise TrendQualityRankerError(
            f"missing_columns:{frame_name}:{','.join(missing)}"
        )


def _as_finite_float(frame: pd.DataFrame, columns: Sequence[str]) -> pd.DataFrame:
    result = frame.copy()
    result[list(columns)] = result[list(columns)].apply(
        pd.to_numeric, errors="coerce"
    ).astype(float)
    if not np.isfinite(result[list(columns)].to_numpy(dtype=float)).all():
        raise TrendQualityRankerError("nonfinite_numeric_value")
    return result


def prepare_ai_universe_labels(
    labels: pd.DataFrame,
    *,
    fixed_product: str = FIXED_PRODUCT,
    levels: int = 5,
    minimum_qid_width: int = 30,
) -> tuple[pd.DataFrame, dict[str, int]]:
    _require_columns(
        labels,
        ["query_date", "product_vt_symbol", *LABEL_COLUMNS],
        "labels",
    )
    if levels < 2 or minimum_qid_width < levels:
        raise TrendQualityRankerError("relevance_contract_invalid")
    result = labels.copy()
    result["query_date"] = _normalise_date(result["query_date"])
    result["product_vt_symbol"] = result["product_vt_symbol"].astype(str)
    result = _as_finite_float(result, LABEL_COLUMNS)
    if result.duplicated(["query_date", "product_vt_symbol"]).any():
        raise TrendQualityRankerError("duplicate_label_row")
    fixed_mask = result["product_vt_symbol"].eq(str(fixed_product))
    fixed_rows = int(fixed_mask.sum())
    fixed_qids = int(result.loc[fixed_mask, "query_date"].nunique())
    result = result.loc[~fixed_mask].copy()
    if result.empty or result["product_vt_symbol"].eq(str(fixed_product)).any():
        raise TrendQualityRankerError("fixed_product_exclusion_failed")
    grouped = result.groupby("query_date", sort=False)
    widths = grouped["product_vt_symbol"].size()
    if widths.lt(int(minimum_qid_width)).any():
        raise TrendQualityRankerError("ai_qid_width_below_minimum")
    unique_targets = grouped["future_trend_capture_quality"].nunique(
        dropna=False
    )
    if unique_targets.lt(int(levels)).any():
        raise TrendQualityRankerError("ai_qid_target_unique_below_levels")
    percentile = grouped["future_trend_capture_quality"].rank(
        method="average", pct=True
    )
    result["trend_quality_relevance"] = (
        np.ceil(percentile * int(levels))
        .sub(1)
        .clip(lower=0, upper=int(levels) - 1)
        .astype(int)
    )
    relevance_counts = result.groupby("query_date", sort=False)[
        "trend_quality_relevance"
    ].nunique()
    relevance_failures = int(relevance_counts.lt(int(levels)).sum())
    if relevance_failures:
        raise TrendQualityRankerError("ai_qid_relevance_levels_incomplete")
    result = result.sort_values(
        ["query_date", "product_vt_symbol"], kind="mergesort"
    ).reset_index(drop=True)
    return result, {
        "input_label_rows": int(len(labels)),
        "fixed_product_rows_excluded": fixed_rows,
        "fixed_product_qids_excluded": fixed_qids,
        "ai_label_rows": int(len(result)),
        "ai_label_qids": int(result["query_date"].nunique()),
        "minimum_ai_qid_width": int(widths.min()),
        "maximum_ai_qid_width": int(widths.max()),
        "relevance_level_failure_count": relevance_failures,
    }


def select_consensus_one_slot(
    full_scored: pd.DataFrame,
    formal_scoring: pd.DataFrame,
    *,
    top_k: int = 10,
) -> dict[str, object]:
    _require_columns(
        full_scored,
        ["query_date", "product_vt_symbol", "xgb_score"],
        "full_scored",
    )
    _require_columns(
        formal_scoring,
        ["test_eval_date", "product_vt_symbol", "role"],
        "formal_scoring",
    )
    full = full_scored[
        ["query_date", "product_vt_symbol", "xgb_score"]
    ].copy()
    scoring = formal_scoring[
        ["test_eval_date", "product_vt_symbol", "role"]
    ].copy()
    full["query_date"] = _normalise_date(full["query_date"])
    scoring["test_eval_date"] = _normalise_date(scoring["test_eval_date"])
    full["product_vt_symbol"] = full["product_vt_symbol"].astype(str)
    scoring["product_vt_symbol"] = scoring["product_vt_symbol"].astype(str)
    full = _as_finite_float(full, ["xgb_score"])
    if full["query_date"].nunique() != 1 or scoring["test_eval_date"].nunique() != 1:
        raise TrendQualityRankerError("selection_month_count_invalid")
    test_date = pd.Timestamp(scoring["test_eval_date"].iloc[0])
    if pd.Timestamp(full["query_date"].iloc[0]) != test_date:
        raise TrendQualityRankerError("selection_date_mismatch")
    if full.duplicated("product_vt_symbol").any() or scoring.duplicated(
        "product_vt_symbol"
    ).any():
        raise TrendQualityRankerError("selection_product_duplicate")
    if not 1 <= int(top_k) <= len(full):
        raise TrendQualityRankerError("selection_top_k_invalid")
    if full["product_vt_symbol"].eq(FIXED_PRODUCT).any():
        raise TrendQualityRankerError("fixed_product_in_selector_universe")
    if not set(scoring["product_vt_symbol"]).issubset(
        set(full["product_vt_symbol"])
    ):
        raise TrendQualityRankerError("selection_product_missing_from_full_qid")
    anchors = scoring[scoring["role"].eq("formal_rank10")]
    challengers = scoring[scoring["role"].eq("challenger")]
    if len(anchors) != 1 or challengers.empty:
        raise TrendQualityRankerError("selection_role_count_invalid")
    if not set(scoring["role"]).issubset({"formal_rank10", "challenger"}):
        raise TrendQualityRankerError("selection_role_invalid")

    ranked = full.sort_values(
        ["xgb_score", "product_vt_symbol"],
        ascending=[False, True],
        kind="mergesort",
    ).reset_index(drop=True)
    ranked["xgb_rank"] = np.arange(1, len(ranked) + 1, dtype="int64")
    ranked_by_product = ranked.set_index("product_vt_symbol")
    anchor_product = str(anchors.iloc[0]["product_vt_symbol"])
    challenger_ranked = ranked[
        ranked["product_vt_symbol"].isin(challengers["product_vt_symbol"])
    ].copy()
    top_challengers = challenger_ranked[
        challenger_ranked["xgb_rank"].le(int(top_k))
    ]
    candidate = (
        top_challengers.iloc[0]
        if not top_challengers.empty
        else challenger_ranked.iloc[0]
    )
    anchor = ranked_by_product.loc[anchor_product]
    anchor_in_top = int(anchor["xgb_rank"]) <= int(top_k)
    challenger_in_top = int(candidate["xgb_rank"]) <= int(top_k)
    replaced = bool(not anchor_in_top and challenger_in_top)
    if anchor_in_top:
        reason = "anchor_in_xgb_top10"
    elif challenger_in_top:
        reason = "xgb_top10_disagrees"
    else:
        reason = "no_challenger_in_xgb_top10"
    challenger_product = str(candidate["product_vt_symbol"])
    return {
        "test_eval_date": test_date,
        "anchor_product": anchor_product,
        "anchor_score": float(anchor["xgb_score"]),
        "anchor_xgb_rank": int(anchor["xgb_rank"]),
        "challenger_product": challenger_product,
        "challenger_score": float(candidate["xgb_score"]),
        "challenger_xgb_rank": int(candidate["xgb_rank"]),
        "selected_product": challenger_product if replaced else anchor_product,
        "replaced": replaced,
        "replacement_reason": reason,
        "xgb_top_k": int(top_k),
        "full_qid_width": int(len(ranked)),
    }


def linear_ndcg_at_k(frame: pd.DataFrame, *, k: int = 10) -> dict[str, float]:
    _require_columns(
        frame,
        ["product_vt_symbol", "xgb_score", "trend_quality_relevance"],
        "ndcg_frame",
    )
    data = frame[
        ["product_vt_symbol", "xgb_score", "trend_quality_relevance"]
    ].copy()
    data["product_vt_symbol"] = data["product_vt_symbol"].astype(str)
    data = _as_finite_float(data, ["xgb_score", "trend_quality_relevance"])
    if data.empty or data.duplicated("product_vt_symbol").any():
        raise TrendQualityRankerError("ndcg_rows_invalid")
    relevance = data["trend_quality_relevance"].to_numpy(dtype=float)
    if (relevance < 0).any() or not np.equal(relevance, np.floor(relevance)).all():
        raise TrendQualityRankerError("ndcg_relevance_invalid")
    cutoff = min(int(k), len(data))
    if cutoff < 1:
        raise TrendQualityRankerError("ndcg_k_invalid")
    discounts = 1.0 / np.log2(np.arange(cutoff, dtype=float) + 2.0)

    ordered = data.sort_values(
        ["xgb_score", "product_vt_symbol"],
        ascending=[False, True],
        kind="mergesort",
    ).reset_index(drop=True)
    expected_tie_dcg = 0.0
    start = 0
    while start < len(ordered) and start < cutoff:
        score = float(ordered.loc[start, "xgb_score"])
        end = start + 1
        while end < len(ordered) and float(ordered.loc[end, "xgb_score"]) == score:
            end += 1
        overlap_end = min(end, cutoff)
        if overlap_end > start:
            mean_gain = float(
                ordered.loc[start : end - 1, "trend_quality_relevance"].mean()
            )
            expected_tie_dcg += mean_gain * float(
                discounts[start:overlap_end].sum()
            )
        start = end

    ideal = np.sort(relevance)[::-1][:cutoff]
    ideal_dcg = float(np.dot(ideal, discounts))
    if ideal_dcg <= 0:
        raise TrendQualityRankerError("ndcg_ideal_nonpositive")
    random_expected_dcg = float(relevance.mean() * discounts.sum())
    return {
        "ndcg_at_k": float(expected_tie_dcg / ideal_dcg),
        "random_expected_ndcg_at_k": float(random_expected_dcg / ideal_dcg),
    }


def compute_month_rank_metrics(
    scored_labels: pd.DataFrame, *, k: int = 10
) -> dict[str, object]:
    _require_columns(
        scored_labels,
        [
            "query_date",
            "product_vt_symbol",
            "xgb_score",
            "future_trend_capture_quality",
            "trend_quality_relevance",
        ],
        "scored_labels",
    )
    frame = scored_labels.copy()
    frame["query_date"] = _normalise_date(frame["query_date"])
    frame["product_vt_symbol"] = frame["product_vt_symbol"].astype(str)
    frame = _as_finite_float(
        frame,
        [
            "xgb_score",
            "future_trend_capture_quality",
            "trend_quality_relevance",
        ],
    )
    if frame["query_date"].nunique() != 1 or frame.duplicated(
        "product_vt_symbol"
    ).any():
        raise TrendQualityRankerError("rank_metric_qid_invalid")
    score_rank = frame["xgb_score"].rank(method="average")
    quality_rank = frame["future_trend_capture_quality"].rank(method="average")
    rank_ic = float(score_rank.corr(quality_rank, method="pearson"))
    if not np.isfinite(rank_ic):
        raise TrendQualityRankerError("rank_ic_nonfinite")
    ndcg = linear_ndcg_at_k(frame, k=k)
    return {
        "test_eval_date": pd.Timestamp(frame["query_date"].iloc[0]),
        "test_label_row_count": int(len(frame)),
        "rank_ic": rank_ic,
        "ndcg_at_10": float(ndcg["ndcg_at_k"]),
        "random_expected_ndcg_at_10": float(
            ndcg["random_expected_ndcg_at_k"]
        ),
        "ndcg_delta_vs_random": float(
            ndcg["ndcg_at_k"] - ndcg["random_expected_ndcg_at_k"]
        ),
    }


def compute_predictive_metrics(monthly: pd.DataFrame) -> dict[str, object]:
    _require_columns(
        monthly,
        [
            "test_eval_date",
            "rank_ic",
            "ndcg_at_10",
            "random_expected_ndcg_at_10",
        ],
        "predictive_monthly",
    )
    frame = monthly.copy()
    frame["test_eval_date"] = _normalise_date(frame["test_eval_date"])
    frame = _as_finite_float(
        frame,
        ["rank_ic", "ndcg_at_10", "random_expected_ndcg_at_10"],
    )
    if frame.empty or frame.duplicated("test_eval_date").any():
        raise TrendQualityRankerError("predictive_monthly_invalid")
    frame = frame.sort_values("test_eval_date", kind="mergesort")
    frame["ndcg_delta_vs_random"] = (
        frame["ndcg_at_10"] - frame["random_expected_ndcg_at_10"]
    )
    yearly_rank_ic = frame.groupby(
        frame["test_eval_date"].dt.year, sort=True
    )["rank_ic"].mean()
    rank_ic_sum = float(frame["rank_ic"].sum())
    return {
        "effect_month_count": int(len(frame)),
        "mean_rank_ic": float(frame["rank_ic"].mean()),
        "median_rank_ic": float(frame["rank_ic"].median()),
        "positive_rank_ic_month_count": int(frame["rank_ic"].gt(0).sum()),
        "leave_best_month_out_rank_ic_sum": float(
            rank_ic_sum - frame["rank_ic"].max()
        ),
        "positive_rank_ic_year_count": int(yearly_rank_ic.gt(0).sum()),
        "yearly_mean_rank_ic": {
            str(int(year)): float(value) for year, value in yearly_rank_ic.items()
        },
        "mean_ndcg_at_10": float(frame["ndcg_at_10"].mean()),
        "mean_random_expected_ndcg_at_10": float(
            frame["random_expected_ndcg_at_10"].mean()
        ),
        "mean_ndcg_delta_vs_random": float(
            frame["ndcg_delta_vs_random"].mean()
        ),
        "ndcg_beats_random_month_count": int(
            frame["ndcg_delta_vs_random"].gt(0).sum()
        ),
    }


def assess_predictive_gates(metrics: Mapping[str, object]) -> dict[str, object]:
    gates = {
        "effect_month_count_exact": int(metrics.get("effect_month_count", -1))
        == 36,
        "mean_rank_ic_positive": float(metrics.get("mean_rank_ic", 0.0)) > 0.0,
        "median_rank_ic_positive": float(metrics.get("median_rank_ic", 0.0))
        > 0.0,
        "positive_rank_ic_months_at_least_22": int(
            metrics.get("positive_rank_ic_month_count", 0)
        )
        >= 22,
        "leave_best_rank_ic_sum_positive": float(
            metrics.get("leave_best_month_out_rank_ic_sum", 0.0)
        )
        > 0.0,
        "positive_rank_ic_years_at_least_three": int(
            metrics.get("positive_rank_ic_year_count", 0)
        )
        >= 3,
        "mean_ndcg_delta_vs_random_positive": float(
            metrics.get("mean_ndcg_delta_vs_random", 0.0)
        )
        > 0.0,
        "ndcg_beats_random_months_at_least_22": int(
            metrics.get("ndcg_beats_random_month_count", 0)
        )
        >= 22,
    }
    return {"passed": all(gates.values()), "gates": gates}


def build_effect_row(
    selection: Mapping[str, object], test_labels: pd.DataFrame
) -> dict[str, object]:
    _require_columns(
        test_labels,
        ["query_date", "product_vt_symbol", *LABEL_COLUMNS],
        "test_labels",
    )
    frame = test_labels.copy()
    frame["query_date"] = _normalise_date(frame["query_date"])
    frame["product_vt_symbol"] = frame["product_vt_symbol"].astype(str)
    frame = _as_finite_float(frame, LABEL_COLUMNS)
    test_date = pd.Timestamp(selection["test_eval_date"]).normalize()
    if frame["query_date"].nunique() != 1 or pd.Timestamp(
        frame["query_date"].iloc[0]
    ) != test_date:
        raise TrendQualityRankerError("effect_date_mismatch")
    if frame.duplicated("product_vt_symbol").any():
        raise TrendQualityRankerError("effect_product_duplicate")
    indexed = frame.set_index("product_vt_symbol")
    anchor_product = str(selection["anchor_product"])
    selected_product = str(selection["selected_product"])
    for product in (anchor_product, selected_product):
        if product not in indexed.index:
            raise TrendQualityRankerError(f"effect_product_missing:{product}")
    replaced = bool(selection["replaced"])
    if replaced != (anchor_product != selected_product):
        raise TrendQualityRankerError("effect_selection_inconsistent")
    row: dict[str, object] = {
        "test_eval_date": test_date,
        "anchor_product": anchor_product,
        "challenger_product": str(selection["challenger_product"]),
        "selected_product": selected_product,
        "replaced": replaced,
    }
    for short_name, source_name in EFFECT_COMPONENTS.items():
        a_value = float(indexed.loc[anchor_product, source_name])
        c_value = float(indexed.loc[selected_product, source_name])
        row[f"a_{short_name}"] = a_value
        row[f"c_{short_name}"] = c_value
        row[f"{short_name}_delta"] = c_value - a_value
    return row


def compute_effect_metrics(effect_monthly: pd.DataFrame) -> dict[str, object]:
    required = ["test_eval_date", "replaced"]
    for short_name in EFFECT_COMPONENTS:
        required.extend([f"a_{short_name}", f"c_{short_name}"])
    _require_columns(effect_monthly, required, "effect_monthly")
    frame = effect_monthly.copy()
    frame["test_eval_date"] = _normalise_date(frame["test_eval_date"])
    if frame.empty or frame.duplicated("test_eval_date").any():
        raise TrendQualityRankerError("effect_monthly_invalid")
    if not pd.api.types.is_bool_dtype(frame["replaced"]):
        values = frame["replaced"].astype(str).str.lower()
        if not values.isin({"true", "false"}).all():
            raise TrendQualityRankerError("effect_replaced_invalid")
        frame["replaced"] = values.eq("true")
    numeric_columns = [
        column
        for short_name in EFFECT_COMPONENTS
        for column in (f"a_{short_name}", f"c_{short_name}")
    ]
    frame = _as_finite_float(frame, numeric_columns)
    frame = frame.sort_values("test_eval_date", kind="mergesort").reset_index(
        drop=True
    )
    for short_name in EFFECT_COMPONENTS:
        frame[f"{short_name}_delta"] = (
            frame[f"c_{short_name}"] - frame[f"a_{short_name}"]
        )
        if not np.allclose(
            frame.loc[~frame["replaced"], f"{short_name}_delta"],
            0.0,
            rtol=0.0,
            atol=1e-15,
        ):
            raise TrendQualityRankerError(
                f"nonreplacement_{short_name}_effect_nonzero"
            )
    replacement_quality = frame.loc[frame["replaced"], "quality_delta"]
    replacement_count = int(len(replacement_quality))
    yearly_quality = frame.groupby(
        frame["test_eval_date"].dt.year, sort=True
    )["quality_delta"].sum()
    metrics: dict[str, object] = {
        "effect_month_count": int(len(frame)),
        "replacement_count": replacement_count,
        "replacement_quality_positive_rate": (
            float(replacement_quality.gt(0).mean()) if replacement_count else 0.0
        ),
        "replacement_median_quality_delta": (
            float(replacement_quality.median()) if replacement_count else 0.0
        ),
        "positive_quality_year_count": int(yearly_quality.gt(0).sum()),
        "yearly_quality_delta": {
            str(int(year)): float(value) for year, value in yearly_quality.items()
        },
    }
    for short_name in EFFECT_COMPONENTS:
        delta = frame[f"{short_name}_delta"]
        total = float(delta.sum())
        metrics[f"sum_{short_name}_delta"] = total
        metrics[f"leave_best_month_out_{short_name}_delta"] = float(
            total - delta.max()
        )
    return metrics


def assess_effect_gates(metrics: Mapping[str, object]) -> dict[str, object]:
    replacement_count = int(metrics.get("replacement_count", 0))
    gates = {
        "effect_month_count_exact": int(metrics.get("effect_month_count", -1))
        == 36,
        "replacement_count_in_range": 8 <= replacement_count <= 32,
        "replacement_quality_positive_rate_above_half": float(
            metrics.get("replacement_quality_positive_rate", 0.0)
        )
        > 0.5,
        "replacement_median_quality_delta_positive": float(
            metrics.get("replacement_median_quality_delta", 0.0)
        )
        > 0.0,
        "sum_quality_delta_positive": float(
            metrics.get("sum_quality_delta", 0.0)
        )
        > 0.0,
        "leave_best_quality_delta_positive": float(
            metrics.get("leave_best_month_out_quality_delta", 0.0)
        )
        > 0.0,
        "positive_quality_years_at_least_three": int(
            metrics.get("positive_quality_year_count", 0)
        )
        >= 3,
        "sum_abs_log_return_delta_positive": float(
            metrics.get("sum_abs_log_return_delta", 0.0)
        )
        > 0.0,
        "leave_best_abs_log_return_delta_positive": float(
            metrics.get("leave_best_month_out_abs_log_return_delta", 0.0)
        )
        > 0.0,
        "sum_oriented_max_drawdown_delta_positive": float(
            metrics.get("sum_oriented_max_drawdown_delta", 0.0)
        )
        > 0.0,
        "leave_best_oriented_max_drawdown_delta_positive": float(
            metrics.get(
                "leave_best_month_out_oriented_max_drawdown_delta", 0.0
            )
        )
        > 0.0,
    }
    return {"passed": all(gates.values()), "gates": gates}


class PhaseGatedTrendQualityStore:
    def __init__(self, labels: pd.DataFrame, paths: pd.DataFrame) -> None:
        _require_columns(
            labels,
            ["query_date", "product_vt_symbol", *LABEL_COLUMNS],
            "labels",
        )
        _require_columns(
            paths,
            ["query_date", "product_vt_symbol", "label_end"],
            "paths",
        )
        clean_labels = labels[
            ["query_date", "product_vt_symbol", *LABEL_COLUMNS]
        ].copy()
        clean_paths = paths[
            ["query_date", "product_vt_symbol", "label_end"]
        ].copy()
        for frame in (clean_labels, clean_paths):
            frame["query_date"] = _normalise_date(frame["query_date"])
            frame["product_vt_symbol"] = frame["product_vt_symbol"].astype(str)
            if frame.duplicated(["query_date", "product_vt_symbol"]).any():
                raise TrendQualityRankerError("label_or_path_duplicate")
        clean_paths["label_end"] = _normalise_date(clean_paths["label_end"])
        clean_labels = _as_finite_float(clean_labels, LABEL_COLUMNS)
        if not np.equal(
            clean_labels["trend_quality_relevance"],
            np.floor(clean_labels["trend_quality_relevance"]),
        ).all():
            raise TrendQualityRankerError("label_relevance_invalid")
        merged = clean_labels.merge(
            clean_paths,
            on=["query_date", "product_vt_symbol"],
            how="inner",
            validate="one_to_one",
        )
        if len(merged) != len(clean_labels) or len(merged) != len(clean_paths):
            raise TrendQualityRankerError("label_path_join_mismatch")
        if merged.groupby("query_date", sort=False)["label_end"].nunique().ne(1).any():
            raise TrendQualityRankerError("qid_label_end_inconsistent")
        self._data = merged.sort_values(
            ["query_date", "product_vt_symbol"], kind="mergesort"
        ).reset_index(drop=True)
        self._training_keys: set[tuple[str, str]] = set()
        self._effect_keys: set[tuple[str, str]] = set()
        self._training_qids: set[str] = set()
        self._authorized_effect_qids: set[str] = set()
        self._opened_effect_qids: set[str] = set()

    @staticmethod
    def _date_key(value: pd.Timestamp) -> str:
        return pd.Timestamp(value).normalize().date().isoformat()

    @classmethod
    def _row_key(cls, date: pd.Timestamp, product: str) -> tuple[str, str]:
        return cls._date_key(date), str(product)

    def open_training_labels(self, test_eval_date: pd.Timestamp) -> pd.DataFrame:
        test_date = pd.Timestamp(test_eval_date).normalize()
        opened = self._data[self._data["label_end"].lt(test_date)].copy()
        for row in opened[["query_date", "product_vt_symbol"]].itertuples(
            index=False
        ):
            self._training_keys.add(self._row_key(row.query_date, row.product_vt_symbol))
            self._training_qids.add(self._date_key(row.query_date))
        return opened.reset_index(drop=True)

    def label_rows_opened_for(self, test_eval_date: pd.Timestamp) -> int:
        date_key = self._date_key(test_eval_date)
        return sum(
            1
            for query_date, _ in self._training_keys | self._effect_keys
            if query_date == date_key
        )

    def qid_row_count(self, query_date: pd.Timestamp) -> int:
        date = pd.Timestamp(query_date).normalize()
        return int(self._data["query_date"].eq(date).sum())

    def authorize_effect_qid(self, test_eval_date: pd.Timestamp) -> None:
        date_key = self._date_key(test_eval_date)
        if date_key in self._authorized_effect_qids:
            raise TrendQualityRankerError(f"effect_already_authorized:{date_key}")
        if not self._data["query_date"].eq(pd.Timestamp(test_eval_date).normalize()).any():
            raise TrendQualityRankerError(f"effect_qid_missing:{date_key}")
        self._authorized_effect_qids.add(date_key)

    def open_effect_qid(self, test_eval_date: pd.Timestamp) -> pd.DataFrame:
        test_date = pd.Timestamp(test_eval_date).normalize()
        date_key = self._date_key(test_date)
        if date_key not in self._authorized_effect_qids:
            raise TrendQualityRankerError(f"effect_not_authorized:{date_key}")
        if date_key in self._opened_effect_qids:
            raise TrendQualityRankerError(f"effect_already_opened:{date_key}")
        opened = self._data[self._data["query_date"].eq(test_date)].copy()
        if opened.empty:
            raise TrendQualityRankerError(f"effect_qid_missing:{date_key}")
        for row in opened[["query_date", "product_vt_symbol"]].itertuples(
            index=False
        ):
            self._effect_keys.add(self._row_key(row.query_date, row.product_vt_symbol))
        self._opened_effect_qids.add(date_key)
        return opened.reset_index(drop=True)

    def audit(self) -> dict[str, int]:
        return {
            "label_rows": int(len(self._data)),
            "label_qids": int(self._data["query_date"].nunique()),
            "opened_training_qids": int(len(self._training_qids)),
            "unique_training_label_rows_opened": int(len(self._training_keys)),
            "opened_effect_qids": int(len(self._opened_effect_qids)),
            "unique_effect_label_rows_opened": int(len(self._effect_keys)),
        }
