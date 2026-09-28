"""Frozen stacked monthly XGBoost ranker and proxy evaluation primitives."""

from __future__ import annotations

import hashlib
from pathlib import Path
import sys
from typing import Any, NamedTuple

import numpy as np
import pandas as pd
from xgboost import XGBRanker


TOOL_DIR = Path(__file__).resolve().parent
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

import market_context_features as feature_core  # noqa: E402


FEATURE_COLUMNS = list(feature_core.FEATURE_COLUMNS)
PASS_DECISION = "stage003_stacked_ranker_pass_allow_engine_preregistration"
FAIL_DECISION = "stage003_stacked_ranker_fail_stop_no_backtest"
RANKER_SCORE_COLUMN = "ranker_score"
RANKER_PARAMS: dict[str, Any] = {
    "objective": "rank:ndcg",
    "eval_metric": "ndcg@1",
    "n_estimators": 64,
    "max_depth": 2,
    "learning_rate": 0.03,
    "min_child_weight": 1.0,
    "gamma": 0.0,
    "subsample": 0.8,
    "colsample_bytree": 1.0,
    "reg_alpha": 1.0,
    "reg_lambda": 10.0,
    "lambdarank_pair_method": "topk",
    "lambdarank_num_pair_per_sample": 3,
    "ndcg_exp_gain": True,
    "tree_method": "hist",
    "random_state": 42,
    "n_jobs": 1,
    "verbosity": 0,
}


class StackedRankerError(RuntimeError):
    """Raised when the frozen stacked-ranker contract is violated."""


class StackedWalkForwardFold(NamedTuple):
    test_date: pd.Timestamp
    train_dates: tuple[pd.Timestamp, ...]
    train_label_end_max: pd.Timestamp
    train_rows: int


def _require_columns(frame: pd.DataFrame, columns: set[str], name: str) -> None:
    if missing := sorted(columns - set(frame.columns)):
        raise StackedRankerError(f"{name}_columns_missing:{','.join(missing)}")


def _as_bool(series: pd.Series, name: str) -> pd.Series:
    if pd.api.types.is_bool_dtype(series.dtype):
        return series.fillna(False).astype(bool)
    values = series.astype(str).str.strip().str.lower()
    if not set(values.unique()).issubset({"true", "false"}):
        raise StackedRankerError(f"{name}_boolean_invalid")
    return values.eq("true")


def normalise_labels(labels: pd.DataFrame) -> pd.DataFrame:
    required = {
        "eval_date",
        "product_vt_symbol",
        "future_net_pnl_60d",
        "future_label_end_date",
        "full_horizon_label",
    }
    _require_columns(labels, required, "labels")
    frame = labels.loc[:, sorted(required)].copy()
    frame["eval_date"] = pd.to_datetime(frame["eval_date"], errors="raise").dt.normalize()
    frame["future_label_end_date"] = pd.to_datetime(
        frame["future_label_end_date"], errors="raise"
    ).dt.normalize()
    frame["product_vt_symbol"] = frame["product_vt_symbol"].astype(str)
    frame["future_net_pnl_60d"] = pd.to_numeric(
        frame["future_net_pnl_60d"], errors="raise"
    ).astype(float)
    frame["full_horizon_label"] = _as_bool(frame["full_horizon_label"], "full_horizon_label")
    if frame.duplicated(["eval_date", "product_vt_symbol"]).any():
        raise StackedRankerError("label_eval_product_duplicate")
    if not np.isfinite(frame["future_net_pnl_60d"].to_numpy(float)).all():
        raise StackedRankerError("future_net_pnl_nonfinite")
    return frame


def attach_relevance_labels(feature_panel: pd.DataFrame, labels: pd.DataFrame) -> pd.DataFrame:
    required = {
        "eval_date",
        "product_vt_symbol",
        "window_id",
        "a_rank",
        "role",
        "pit_logistic_probability",
        *FEATURE_COLUMNS,
    }
    _require_columns(feature_panel, required, "feature_panel")
    features = feature_panel.loc[:, sorted(required)].copy()
    features["eval_date"] = pd.to_datetime(features["eval_date"], errors="raise").dt.normalize()
    features["product_vt_symbol"] = features["product_vt_symbol"].astype(str)
    if features.duplicated(["eval_date", "product_vt_symbol"]).any():
        raise StackedRankerError("feature_eval_product_duplicate")
    matrix = features[FEATURE_COLUMNS].apply(pd.to_numeric, errors="raise").to_numpy(float)
    if not np.isfinite(matrix).all():
        raise StackedRankerError("feature_value_nonfinite")
    label_frame = normalise_labels(labels)
    joined = features.merge(
        label_frame,
        on=["eval_date", "product_vt_symbol"],
        how="left",
        validate="one_to_one",
    )
    if len(joined) != len(features) or joined["future_label_end_date"].isna().any():
        raise StackedRankerError("feature_label_join_incomplete")
    if not joined["full_horizon_label"].all():
        raise StackedRankerError("feature_label_horizon_incomplete")
    if joined.groupby("eval_date")["future_label_end_date"].nunique().gt(1).any():
        raise StackedRankerError("month_label_end_not_unique")
    joined["rank_relevance"] = (
        joined.groupby("eval_date")["future_net_pnl_60d"]
        .rank(method="dense", ascending=True)
        .astype(int)
        - 1
    )
    if joined["rank_relevance"].lt(0).any() or joined["rank_relevance"].gt(31).any():
        raise StackedRankerError("rank_relevance_out_of_range")
    return joined.sort_values(
        ["eval_date", "a_rank", "product_vt_symbol"], kind="mergesort"
    ).reset_index(drop=True)


def build_stacked_walk_forward_folds(
    labelled_panel: pd.DataFrame,
    *,
    minimum_train_months: int,
    minimum_train_rows: int,
) -> list[StackedWalkForwardFold]:
    if minimum_train_months <= 0 or minimum_train_rows <= 0:
        raise StackedRankerError("minimum_training_contract_invalid")
    _require_columns(
        labelled_panel,
        {"eval_date", "future_label_end_date", "rank_relevance"},
        "labelled_panel",
    )
    frame = labelled_panel.copy()
    frame["eval_date"] = pd.to_datetime(frame["eval_date"], errors="raise").dt.normalize()
    frame["future_label_end_date"] = pd.to_datetime(
        frame["future_label_end_date"], errors="raise"
    ).dt.normalize()
    month_end = frame.groupby("eval_date")["future_label_end_date"].agg(["min", "max"])
    if not month_end["min"].equals(month_end["max"]):
        raise StackedRankerError("month_label_end_not_unique")
    dates = tuple(pd.Timestamp(date) for date in sorted(frame["eval_date"].unique()))
    folds: list[StackedWalkForwardFold] = []
    for test_date in dates:
        train_dates = tuple(
            date
            for date in dates
            if date < test_date and pd.Timestamp(month_end.loc[date, "max"]) < test_date
        )
        train_rows = int(frame["eval_date"].isin(train_dates).sum())
        if len(train_dates) < minimum_train_months or train_rows < minimum_train_rows:
            continue
        train_label_end_max = pd.Timestamp(month_end.loc[list(train_dates), "max"].max())
        if train_label_end_max >= test_date:
            raise StackedRankerError("walk_forward_label_overlap")
        folds.append(
            StackedWalkForwardFold(
                test_date=test_date,
                train_dates=train_dates,
                train_label_end_max=train_label_end_max,
                train_rows=train_rows,
            )
        )
    return folds


def _prepare_training(frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    ordered = frame.sort_values(
        ["eval_date", "a_rank", "product_vt_symbol"], kind="mergesort"
    )
    x = ordered[FEATURE_COLUMNS].to_numpy(dtype=float)
    y = ordered["rank_relevance"].to_numpy(dtype=np.int32)
    qid, _ = pd.factorize(ordered["eval_date"], sort=True)
    if np.any(np.diff(qid) < 0):
        raise StackedRankerError("training_qid_not_sorted")
    return x, y, qid.astype(np.int32)


def fit_ranker(
    train: pd.DataFrame,
    *,
    params: dict[str, Any] | None = None,
) -> XGBRanker:
    x, y, qid = _prepare_training(train)
    model = XGBRanker(**(RANKER_PARAMS if params is None else params))
    model.fit(x, y, qid=qid, verbose=False)
    return model


def predict_ranker(model: XGBRanker, frame: pd.DataFrame) -> np.ndarray:
    ordered = frame.sort_values(["a_rank", "product_vt_symbol"], kind="mergesort")
    return np.asarray(model.predict(ordered[FEATURE_COLUMNS].to_numpy(float)), dtype=float)


def booster_dump_sha256(model: XGBRanker) -> str:
    payload = "\n".join(model.get_booster().get_dump(dump_format="json"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def split_node_count(model: XGBRanker) -> int:
    trees = model.get_booster().trees_to_dataframe()
    return int(trees["Feature"].ne("Leaf").sum())


def select_b_candidate(month: pd.DataFrame) -> str:
    _require_columns(month, {"product_vt_symbol", "a_rank", RANKER_SCORE_COLUMN}, "month")
    ordered = month.sort_values(
        [RANKER_SCORE_COLUMN, "a_rank", "product_vt_symbol"],
        ascending=[False, True, True],
        kind="mergesort",
    )
    if ordered.empty:
        raise StackedRankerError("candidate_month_empty")
    return str(ordered.iloc[0]["product_vt_symbol"])


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
        raise StackedRankerError("product_return_date_product_duplicate")
    return frame


def future_equal_weight_drawdown(
    product_returns: pd.DataFrame,
    *,
    eval_date: pd.Timestamp,
    products: list[str] | tuple[str, ...],
    horizon: int,
) -> float:
    if horizon <= 0:
        raise StackedRankerError("future_horizon_invalid")
    returns = _normalise_returns(product_returns)
    selected = tuple(sorted(set(str(product) for product in products)))
    if len(selected) != len(products):
        raise StackedRankerError("selected_product_duplicate")
    future_dates = pd.DatetimeIndex(
        sorted(returns.loc[returns["return_date"].gt(pd.Timestamp(eval_date)), "return_date"].unique())
    )[:horizon]
    if len(future_dates) != horizon:
        raise StackedRankerError(f"future_market_dates_incomplete:{len(future_dates)}")
    path = returns[
        returns["return_date"].isin(future_dates)
        & returns["product_vt_symbol"].isin(selected)
    ].copy()
    expected_rows = horizon * len(selected)
    if len(path) != expected_rows:
        raise StackedRankerError(f"future_market_rows_incomplete:{len(path)}:{expected_rows}")
    valid = (
        path["status"].eq("ok")
        & np.isfinite(path["product_return"].to_numpy(float))
        & path["product_return"].gt(-1.0)
        & path["selection_date"].lt(path["return_date"])
        & ~path["fallback_used"]
        & ~path["cross_contract_price_used"]
        & path["selected_contract_vt"].ne("")
    )
    if not valid.all():
        raise StackedRankerError("future_market_row_invalid")
    pivot = path.pivot(
        index="return_date", columns="product_vt_symbol", values="product_return"
    ).reindex(index=future_dates, columns=list(selected))
    if pivot.isna().any().any():
        raise StackedRankerError("future_market_pivot_incomplete")
    portfolio_return = pivot.mean(axis=1).to_numpy(float)
    wealth = np.cumprod(1.0 + portfolio_return)
    peaks = np.maximum.accumulate(np.concatenate(([1.0], wealth)))[1:]
    result = float(np.min(wealth / peaks - 1.0))
    if not np.isfinite(result) or result > 0.0:
        raise StackedRankerError("future_market_drawdown_invalid")
    return result


def build_monthly_proxy_metrics(
    predictions: pd.DataFrame,
    ranked_a_panel: pd.DataFrame,
    labels: pd.DataFrame,
    product_returns: pd.DataFrame,
    *,
    top_rank_count: int,
    future_market_horizon: int,
) -> pd.DataFrame:
    label_frame = normalise_labels(labels)
    if not label_frame["full_horizon_label"].all():
        raise StackedRankerError("proxy_label_horizon_incomplete")
    label_lookup = label_frame.set_index(["eval_date", "product_vt_symbol"])
    ranked = ranked_a_panel.copy()
    ranked["eval_date"] = pd.to_datetime(ranked["eval_date"], errors="raise").dt.normalize()
    rows: list[dict[str, Any]] = []
    for eval_date, month in predictions.groupby("eval_date", sort=True):
        date = pd.Timestamp(eval_date)
        month = month.sort_values(["a_rank", "product_vt_symbol"], kind="mergesort")
        anchor = month[month["role"].eq("a_rank10")]
        if len(anchor) != 1:
            raise StackedRankerError("proxy_anchor_count_invalid")
        a_product = str(anchor.iloc[0]["product_vt_symbol"])
        b_product = select_b_candidate(month)
        ranked_month = ranked[ranked["eval_date"].eq(date)].sort_values("a_rank")
        top9 = ranked_month[ranked_month["role"].eq("top9")]["product_vt_symbol"].astype(str).tolist()
        if len(top9) != top_rank_count:
            raise StackedRankerError("proxy_top_count_invalid")
        a_products = tuple(top9 + [a_product])
        c_products = tuple(top9 + [b_product])

        def total_pnl(products: tuple[str, ...]) -> float:
            values = []
            for product in products:
                key = (date, product)
                if key not in label_lookup.index:
                    raise StackedRankerError(f"proxy_label_missing:{date.date()}:{product}")
                values.append(float(label_lookup.loc[key, "future_net_pnl_60d"]))
            return float(sum(values))

        a_total = total_pnl(a_products)
        c_total = total_pnl(c_products)
        a_rank_ic = float(
            month["pit_logistic_probability"].corr(month["future_net_pnl_60d"], method="spearman")
        )
        b_rank_ic = float(month[RANKER_SCORE_COLUMN].corr(month["future_net_pnl_60d"], method="spearman"))
        if not np.isfinite(a_rank_ic) or not np.isfinite(b_rank_ic):
            raise StackedRankerError("proxy_rank_ic_nonfinite")
        a_drawdown = future_equal_weight_drawdown(
            product_returns,
            eval_date=date,
            products=a_products,
            horizon=future_market_horizon,
        )
        c_drawdown = future_equal_weight_drawdown(
            product_returns,
            eval_date=date,
            products=c_products,
            horizon=future_market_horizon,
        )
        rows.append(
            {
                "eval_date": date,
                "year": int(date.year),
                "candidate_count": int(len(month)),
                "a_rank_ic": a_rank_ic,
                "b_rank_ic": b_rank_ic,
                "a_product": a_product,
                "b_product": b_product,
                "replaced": b_product != a_product,
                "top9_products": "|".join(top9),
                "a_top10_products": "|".join(a_products),
                "c_top10_products": "|".join(c_products),
                "a_total_future_net_pnl_60d": a_total,
                "c_total_future_net_pnl_60d": c_total,
                "future_net_pnl_delta": c_total - a_total,
                "a_future_market_drawdown_60d": a_drawdown,
                "c_future_market_drawdown_60d": c_drawdown,
                "future_market_drawdown_delta": c_drawdown - a_drawdown,
            }
        )
    return pd.DataFrame(rows)


def summarize_proxy_effects(monthly: pd.DataFrame) -> dict[str, Any]:
    pnl_delta = monthly["future_net_pnl_delta"].astype(float)
    dd_delta = monthly["future_market_drawdown_delta"].astype(float)
    yearly_pnl = monthly.groupby("year")["future_net_pnl_delta"].sum()
    yearly_dd = monthly.groupby("year")["future_market_drawdown_delta"].mean()
    return {
        "replacement_months": int(monthly["replaced"].astype(bool).sum()),
        "a_mean_rank_ic": float(monthly["a_rank_ic"].mean()),
        "b_mean_rank_ic": float(monthly["b_rank_ic"].mean()),
        "a_median_rank_ic": float(monthly["a_rank_ic"].median()),
        "b_median_rank_ic": float(monthly["b_rank_ic"].median()),
        "a_mean_future_pnl": float(monthly["a_total_future_net_pnl_60d"].mean()),
        "c_mean_future_pnl": float(monthly["c_total_future_net_pnl_60d"].mean()),
        "median_future_pnl_delta": float(pnl_delta.median()),
        "a_p10_future_pnl": float(monthly["a_total_future_net_pnl_60d"].quantile(0.10)),
        "c_p10_future_pnl": float(monthly["c_total_future_net_pnl_60d"].quantile(0.10)),
        "positive_future_pnl_delta_rate": float(pnl_delta.gt(0.0).mean()),
        "yearly_future_pnl_delta": {
            str(int(year)): float(value) for year, value in yearly_pnl.items()
        },
        "leave_best_month_future_pnl_delta": float(pnl_delta.sum() - pnl_delta.max()),
        "a_mean_market_drawdown": float(monthly["a_future_market_drawdown_60d"].mean()),
        "c_mean_market_drawdown": float(monthly["c_future_market_drawdown_60d"].mean()),
        "a_p10_market_drawdown": float(monthly["a_future_market_drawdown_60d"].quantile(0.10)),
        "c_p10_market_drawdown": float(monthly["c_future_market_drawdown_60d"].quantile(0.10)),
        "yearly_mean_market_drawdown_delta": {
            str(int(year)): float(value) for year, value in yearly_dd.items()
        },
    }


def evaluate_effect_gates(
    summary: dict[str, Any],
    *,
    minimum_replacement_months: int,
    required_years: list[int] | tuple[int, ...] | None = None,
) -> dict[str, bool]:
    years = (
        [str(int(year)) for year in required_years]
        if required_years is not None
        else sorted(summary["yearly_future_pnl_delta"])
    )
    return {
        "replacement_months_minimum": int(summary["replacement_months"])
        >= minimum_replacement_months,
        "mean_rank_ic_strictly_better": float(summary["b_mean_rank_ic"])
        > float(summary["a_mean_rank_ic"]),
        "median_rank_ic_noninferior": float(summary["b_median_rank_ic"])
        >= float(summary["a_median_rank_ic"]),
        "mean_future_pnl_strictly_better": float(summary["c_mean_future_pnl"])
        > float(summary["a_mean_future_pnl"]),
        "median_future_pnl_delta_nonnegative": float(summary["median_future_pnl_delta"])
        >= 0.0,
        "p10_future_pnl_noninferior": float(summary["c_p10_future_pnl"])
        >= float(summary["a_p10_future_pnl"]),
        "positive_future_pnl_delta_rate_minimum": float(
            summary["positive_future_pnl_delta_rate"]
        )
        >= 0.55,
        "yearly_future_pnl_delta_nonnegative": all(
            year in summary["yearly_future_pnl_delta"]
            and float(summary["yearly_future_pnl_delta"][year]) >= 0.0
            for year in years
        ),
        "leave_best_month_future_pnl_delta_positive": float(
            summary["leave_best_month_future_pnl_delta"]
        )
        > 0.0,
        "mean_market_drawdown_strictly_better": float(summary["c_mean_market_drawdown"])
        > float(summary["a_mean_market_drawdown"]),
        "p10_market_drawdown_strictly_better": float(summary["c_p10_market_drawdown"])
        > float(summary["a_p10_market_drawdown"]),
        "yearly_market_drawdown_delta_nonnegative": all(
            year in summary["yearly_mean_market_drawdown_delta"]
            and float(summary["yearly_mean_market_drawdown_delta"][year]) >= 0.0
            for year in years
        ),
    }
