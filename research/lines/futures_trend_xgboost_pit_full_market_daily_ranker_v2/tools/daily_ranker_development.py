from __future__ import annotations

import hashlib
from typing import Any, Callable, Mapping, Sequence

import numpy as np
import pandas as pd
from xgboost import XGBRanker


MODEL_PARAMS: dict[str, Any] = {
    "objective": "rank:ndcg",
    "eval_metric": "ndcg@10",
    "n_estimators": 64,
    "max_depth": 2,
    "learning_rate": 0.03,
    "min_child_weight": 5,
    "gamma": 0,
    "subsample": 1,
    "colsample_bytree": 1,
    "reg_alpha": 0,
    "reg_lambda": 10,
    "tree_method": "hist",
    "lambdarank_pair_method": "topk",
    "lambdarank_num_pair_per_sample": 10,
    "lambdarank_normalization": True,
    "lambdarank_score_normalization": True,
    "ndcg_exp_gain": False,
    "random_state": 42,
    "n_jobs": 1,
}


class DevelopmentError(RuntimeError):
    pass


class ContractPriceIndex:
    def __init__(self, contract_prices: pd.DataFrame) -> None:
        if set(contract_prices.columns) != {
            "date",
            "contract_vt_symbol",
            "close_price",
        }:
            raise DevelopmentError("price_columns_invalid")
        prices = contract_prices.copy()
        prices["date"] = _normalise_date(prices["date"])
        prices["contract_vt_symbol"] = prices["contract_vt_symbol"].astype(str)
        prices["close_price"] = pd.to_numeric(
            prices["close_price"], errors="coerce"
        ).astype(float)
        if prices.duplicated(["date", "contract_vt_symbol"]).any():
            raise DevelopmentError("duplicate_contract_price")
        self._prices = prices.set_index(["date", "contract_vt_symbol"])[
            "close_price"
        ]
        self._lookup_count = 0

    @property
    def lookup_count(self) -> int:
        return self._lookup_count

    def lookup(
        self,
        dates: pd.Series,
        contracts: pd.Series,
    ) -> np.ndarray:
        normalised_dates = _normalise_date(pd.Series(dates).reset_index(drop=True))
        normalised_contracts = pd.Series(contracts).reset_index(drop=True).astype(str)
        keys = pd.MultiIndex.from_arrays(
            [normalised_dates, normalised_contracts],
            names=["date", "contract_vt_symbol"],
        )
        self._lookup_count += len(keys)
        return self._prices.reindex(keys).to_numpy(dtype="float64")


def _normalise_date(series: pd.Series) -> pd.Series:
    result = pd.to_datetime(series, errors="coerce").dt.normalize()
    if result.isna().any():
        raise DevelopmentError("invalid_date")
    return result


def _require_columns(
    frame: pd.DataFrame, columns: Sequence[str], frame_name: str
) -> None:
    missing = sorted(set(columns).difference(frame.columns))
    if missing:
        raise DevelopmentError(
            f"missing_columns:{frame_name}:{','.join(missing)}"
        )


def generate_label_values(
    label_plan: pd.DataFrame,
    contract_prices: pd.DataFrame | ContractPriceIndex,
) -> tuple[pd.DataFrame, dict[str, int]]:
    _require_columns(
        label_plan,
        [
            "query_date",
            "product_vt_symbol",
            "main_contract_vt",
            "entry_date",
            "label_end",
        ],
        "label_plan",
    )
    plan = label_plan[
        [
            "query_date",
            "product_vt_symbol",
            "main_contract_vt",
            "entry_date",
            "label_end",
        ]
    ].copy()
    for column in ("query_date", "entry_date", "label_end"):
        plan[column] = _normalise_date(plan[column])
    for column in ("product_vt_symbol", "main_contract_vt"):
        plan[column] = plan[column].astype(str)
    if plan.duplicated(["query_date", "product_vt_symbol"]).any():
        raise DevelopmentError("duplicate_label_plan_row")
    if plan["entry_date"].ge(plan["label_end"]).any():
        raise DevelopmentError("label_date_order_invalid")

    price_index = (
        contract_prices
        if isinstance(contract_prices, ContractPriceIndex)
        else ContractPriceIndex(contract_prices)
    )
    lookup_before = price_index.lookup_count
    result = plan.copy()
    result["entry_close"] = price_index.lookup(
        result["entry_date"], result["main_contract_vt"]
    )
    result["exit_close"] = price_index.lookup(
        result["label_end"], result["main_contract_vt"]
    )
    missing = int(result[["entry_close", "exit_close"]].isna().any(axis=1).sum())
    if missing:
        raise DevelopmentError(f"label_price_missing:{missing}")
    valid_prices = (
        np.isfinite(result["entry_close"])
        & np.isfinite(result["exit_close"])
        & result["entry_close"].gt(0)
        & result["exit_close"].gt(0)
    )
    if not valid_prices.all():
        raise DevelopmentError("label_price_nonpositive_or_nonfinite")
    result["forward_log_return"] = np.log(
        result["exit_close"] / result["entry_close"]
    )
    if not np.isfinite(result["forward_log_return"]).all():
        raise DevelopmentError("label_return_nonfinite")
    audit = {
        "label_rows": int(len(result)),
        "close_value_reads": int(price_index.lookup_count - lookup_before),
        "future_return_calculations": int(len(result)),
        "missing_price_rows": 0,
    }
    output = result[
        [
            "query_date",
            "product_vt_symbol",
            "main_contract_vt",
            "entry_date",
            "label_end",
            "forward_log_return",
        ]
    ].sort_values(["query_date", "product_vt_symbol"], kind="mergesort")
    return output.reset_index(drop=True), audit


def add_cross_sectional_relevance(labels: pd.DataFrame) -> pd.DataFrame:
    _require_columns(
        labels,
        ["query_date", "product_vt_symbol", "forward_log_return"],
        "labels",
    )
    result = labels.copy()
    result["query_date"] = _normalise_date(result["query_date"])
    result["product_vt_symbol"] = result["product_vt_symbol"].astype(str)
    result["forward_log_return"] = pd.to_numeric(
        result["forward_log_return"], errors="coerce"
    ).astype(float)
    if result.duplicated(["query_date", "product_vt_symbol"]).any():
        raise DevelopmentError("duplicate_label_row")
    if not np.isfinite(result["forward_log_return"]).all():
        raise DevelopmentError("label_return_nonfinite")
    result = result.sort_values(
        ["query_date", "product_vt_symbol"], kind="mergesort"
    ).reset_index(drop=True)
    group_size = result.groupby("query_date", sort=False)[
        "product_vt_symbol"
    ].transform("size")
    if group_size.lt(5).any():
        raise DevelopmentError("label_qid_width_below_five")
    percentile_rank = result.groupby("query_date", sort=False)[
        "forward_log_return"
    ].rank(method="average", pct=True)
    result["relevance"] = (
        np.ceil(percentile_rank * 5).sub(1).clip(lower=0, upper=4).astype(int)
    )
    level_counts = result.groupby("query_date", sort=False)["relevance"].nunique()
    if level_counts.lt(2).any():
        raise DevelopmentError("relevance_degenerate")
    return result.sort_values(
        ["query_date", "product_vt_symbol"], kind="mergesort"
    ).reset_index(drop=True)


def build_ranker_arrays(
    training_frame: pd.DataFrame,
    feature_columns: Sequence[str],
) -> tuple[pd.DataFrame, pd.DataFrame, np.ndarray, np.ndarray]:
    _require_columns(
        training_frame,
        ["query_date", "product_vt_symbol", "relevance", *feature_columns],
        "training_frame",
    )
    if len(feature_columns) != len(set(feature_columns)) or not feature_columns:
        raise DevelopmentError("feature_order_invalid")
    ordered = training_frame.copy()
    ordered["query_date"] = _normalise_date(ordered["query_date"])
    ordered["product_vt_symbol"] = ordered["product_vt_symbol"].astype(str)
    ordered = ordered.sort_values(
        ["query_date", "product_vt_symbol"], kind="mergesort"
    ).reset_index(drop=True)
    if ordered.duplicated(["query_date", "product_vt_symbol"]).any():
        raise DevelopmentError("duplicate_training_row")
    features = ordered[list(feature_columns)].apply(
        pd.to_numeric, errors="coerce"
    ).astype(float)
    if not np.isfinite(features.to_numpy(float)).all():
        raise DevelopmentError("training_feature_nonfinite")
    target = pd.to_numeric(ordered["relevance"], errors="coerce").to_numpy()
    if not np.isfinite(target).all() or not np.equal(target, np.floor(target)).all():
        raise DevelopmentError("training_target_invalid")
    target = target.astype("int64")
    if ((target < 0) | (target > 4)).any():
        raise DevelopmentError("training_target_out_of_range")
    qid = ordered.groupby("query_date", sort=True).ngroup().to_numpy("int64")
    if len(qid) and (qid[0] != 0 or np.any(np.diff(qid) < 0)):
        raise DevelopmentError("qid_not_sorted_contiguous")
    return ordered, features, target, qid


def select_one_slot(scored: pd.DataFrame) -> dict[str, object]:
    _require_columns(
        scored,
        ["test_eval_date", "product_vt_symbol", "role", "xgb_score"],
        "scored",
    )
    frame = scored.copy()
    frame["test_eval_date"] = _normalise_date(frame["test_eval_date"])
    frame["product_vt_symbol"] = frame["product_vt_symbol"].astype(str)
    frame["xgb_score"] = pd.to_numeric(frame["xgb_score"], errors="coerce").astype(
        float
    )
    if frame["test_eval_date"].nunique() != 1:
        raise DevelopmentError("selection_month_count_invalid")
    if not np.isfinite(frame["xgb_score"]).all():
        raise DevelopmentError("selection_score_nonfinite")
    anchors = frame[frame["role"].eq("formal_rank10")]
    challengers = frame[frame["role"].eq("challenger")]
    if len(anchors) != 1 or challengers.empty:
        raise DevelopmentError("selection_role_count_invalid")
    challenger = challengers.sort_values(
        ["xgb_score", "product_vt_symbol"],
        ascending=[False, True],
        kind="mergesort",
    ).iloc[0]
    anchor = anchors.iloc[0]
    replaced = bool(challenger["xgb_score"] > anchor["xgb_score"])
    return {
        "test_eval_date": frame["test_eval_date"].iloc[0],
        "anchor_product": str(anchor["product_vt_symbol"]),
        "anchor_score": float(anchor["xgb_score"]),
        "challenger_product": str(challenger["product_vt_symbol"]),
        "challenger_score": float(challenger["xgb_score"]),
        "selected_product": str(
            challenger["product_vt_symbol"]
            if replaced
            else anchor["product_vt_symbol"]
        ),
        "replaced": replaced,
    }


def _maximum_drawdown(returns: np.ndarray) -> float:
    cumulative = np.cumsum(np.asarray(returns, dtype="float64"))
    path = np.concatenate(([0.0], cumulative))
    return float((path - np.maximum.accumulate(path)).min())


def compute_effect_metrics(effect_monthly: pd.DataFrame) -> dict[str, object]:
    _require_columns(
        effect_monthly,
        ["test_eval_date", "replaced", "a_return", "c_return"],
        "effect_monthly",
    )
    frame = effect_monthly.copy()
    frame["test_eval_date"] = _normalise_date(frame["test_eval_date"])
    frame["replaced"] = frame["replaced"].astype(bool)
    for column in ("a_return", "c_return"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce").astype(float)
    if not np.isfinite(frame[["a_return", "c_return"]].to_numpy(float)).all():
        raise DevelopmentError("effect_return_nonfinite")
    if frame.duplicated("test_eval_date").any():
        raise DevelopmentError("duplicate_effect_month")
    frame = frame.sort_values("test_eval_date", kind="mergesort").reset_index(
        drop=True
    )
    frame["return_delta"] = frame["c_return"] - frame["a_return"]
    if not np.allclose(
        frame.loc[~frame["replaced"], "return_delta"], 0.0, rtol=0.0, atol=1e-15
    ):
        raise DevelopmentError("nonreplacement_effect_nonzero")
    replacement_delta = frame.loc[frame["replaced"], "return_delta"]
    replacement_count = int(len(replacement_delta))
    positive_rate = (
        float(replacement_delta.gt(0).mean()) if replacement_count else 0.0
    )
    median_delta = float(replacement_delta.median()) if replacement_count else 0.0
    total_delta = float(frame["return_delta"].sum())
    best_delta = float(frame["return_delta"].max()) if len(frame) else 0.0
    a_drawdown = _maximum_drawdown(frame["a_return"].to_numpy(float))
    c_drawdown = _maximum_drawdown(frame["c_return"].to_numpy(float))
    yearly = frame.groupby(frame["test_eval_date"].dt.year, sort=True)[
        "return_delta"
    ].sum()
    return {
        "effect_month_count": int(len(frame)),
        "replacement_count": replacement_count,
        "replacement_positive_rate": positive_rate,
        "replacement_median_return_delta": median_delta,
        "sum_return_delta": total_delta,
        "leave_best_month_out_return_delta": float(total_delta - best_delta),
        "a_max_drawdown": a_drawdown,
        "c_max_drawdown": c_drawdown,
        "drawdown_improvement": float(c_drawdown - a_drawdown),
        "positive_year_count": int(yearly.gt(0).sum()),
        "yearly_return_delta": {
            str(int(year)): float(value) for year, value in yearly.items()
        },
    }


def assess_effect_gates(metrics: Mapping[str, object]) -> dict[str, object]:
    replacement_count = int(metrics.get("replacement_count", 0))
    gates = {
        "replacement_count_in_range": 8 <= replacement_count <= 32,
        "replacement_positive_rate_above_half": float(
            metrics.get("replacement_positive_rate", 0.0)
        )
        > 0.5,
        "replacement_median_delta_positive": float(
            metrics.get("replacement_median_return_delta", 0.0)
        )
        > 0.0,
        "sum_return_delta_positive": float(metrics.get("sum_return_delta", 0.0))
        > 0.0,
        "leave_best_return_delta_positive": float(
            metrics.get("leave_best_month_out_return_delta", 0.0)
        )
        > 0.0,
        "drawdown_improvement_positive": float(
            metrics.get("drawdown_improvement", 0.0)
        )
        > 0.0,
        "positive_year_count_at_least_three": int(
            metrics.get("positive_year_count", 0)
        )
        >= 3,
    }
    return {"passed": all(gates.values()), "gates": gates}


def fit_repeated_ranker(
    train_features: pd.DataFrame,
    train_target: np.ndarray,
    train_qid: np.ndarray,
    predict_features: pd.DataFrame,
    *,
    params: Mapping[str, Any] = MODEL_PARAMS,
    tolerance: float = 1e-12,
    ranker_factory: Callable[..., Any] = XGBRanker,
) -> dict[str, object]:
    if list(train_features.columns) != list(predict_features.columns):
        raise DevelopmentError("ranker_feature_order_mismatch")
    if not len(train_features) or len(train_features) != len(train_target):
        raise DevelopmentError("ranker_training_shape_invalid")
    qid = np.asarray(train_qid, dtype="int64")
    target = np.asarray(train_target, dtype="int64")
    if len(qid) != len(train_features):
        raise DevelopmentError("ranker_qid_shape_invalid")
    if len(qid) and (qid[0] != 0 or np.any(np.diff(qid) < 0)):
        raise DevelopmentError("ranker_qid_not_sorted")
    predictions: list[np.ndarray] = []
    payloads: list[bytes] = []
    split_counts: list[int] = []
    for _ in range(2):
        model = ranker_factory(**dict(params))
        model.fit(train_features, target, qid=qid, verbose=False)
        prediction = np.asarray(model.predict(predict_features), dtype="float64")
        if not np.isfinite(prediction).all():
            raise DevelopmentError("ranker_prediction_nonfinite")
        booster = model.get_booster()
        if booster.feature_names != list(train_features.columns):
            raise DevelopmentError("ranker_booster_feature_order_mismatch")
        payload = bytes(booster.save_raw(raw_format="ubj"))
        tree_frame = booster.trees_to_dataframe()
        split_counts.append(int(tree_frame["Feature"].ne("Leaf").sum()))
        predictions.append(prediction)
        payloads.append(payload)
    max_difference = float(
        np.max(np.abs(predictions[0] - predictions[1]), initial=0.0)
    )
    hashes = [hashlib.sha256(payload).hexdigest() for payload in payloads]
    if max_difference > tolerance:
        raise DevelopmentError(f"ranker_prediction_nondeterministic:{max_difference}")
    if hashes[0] != hashes[1]:
        raise DevelopmentError("ranker_model_bytes_nondeterministic")
    if len(np.unique(predictions[0])) < 2:
        raise DevelopmentError("ranker_prediction_constant")
    if min(split_counts) < 1:
        raise DevelopmentError("ranker_model_no_split")
    return {
        "predictions": predictions[0],
        "primary_model_raw": payloads[0],
        "repeat_model_raw": payloads[1],
        "primary_model_sha256": hashes[0],
        "repeat_model_sha256": hashes[1],
        "prediction_repeat_max_abs_difference": max_difference,
        "unique_prediction_count": int(len(np.unique(predictions[0]))),
        "split_count": int(split_counts[0]),
    }


def build_estimator_audit(
    ranker_factory: Callable[..., Any], params: Mapping[str, Any]
) -> dict[str, object]:
    factory_exact = ranker_factory is XGBRanker
    params_exact = dict(params) == MODEL_PARAMS
    return {
        "passed": bool(factory_exact and params_exact),
        "factory_exact": bool(factory_exact),
        "actual_factory_module": getattr(ranker_factory, "__module__", None),
        "actual_factory_qualname": getattr(ranker_factory, "__qualname__", None),
        "expected_factory_module": XGBRanker.__module__,
        "expected_factory_qualname": XGBRanker.__qualname__,
        "params_exact": bool(params_exact),
        "actual_params": dict(params),
        "expected_params": MODEL_PARAMS,
    }
