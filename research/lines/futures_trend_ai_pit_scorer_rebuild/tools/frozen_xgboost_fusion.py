"""Frozen XGBoost and logistic-rank fusion primitives."""

from __future__ import annotations

import hashlib
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd
from xgboost import XGBClassifier


TOOL_DIR = Path(__file__).resolve().parent
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

import conditional_pit_logistic as logistic_core  # noqa: E402


DATE_COLUMN = logistic_core.DATE_COLUMN
PRODUCT_COLUMN = logistic_core.PRODUCT_COLUMN
TARGET_COLUMN = logistic_core.TARGET_COLUMN
WEIGHT_COLUMN = logistic_core.WEIGHT_COLUMN
FUTURE_PNL_COLUMN = logistic_core.FUTURE_PNL_COLUMN
FUTURE_RANK_COLUMN = logistic_core.FUTURE_RANK_COLUMN
LR_SCORE_COLUMN = logistic_core.PROBABILITY_COLUMN
XGB_SCORE_COLUMN = "pit_xgboost_probability"
FUSION_SCORE_COLUMN = "pit_lr_xgb_rank_fusion"
TOP_N = 10
RANDOM_STATE = 42

XGBOOST_PARAMS: dict[str, Any] = {
    "objective": "binary:logistic",
    "eval_metric": "logloss",
    "n_estimators": 120,
    "max_depth": 2,
    "learning_rate": 0.03,
    "min_child_weight": 12.0,
    "gamma": 0.10,
    "subsample": 0.80,
    "colsample_bytree": 0.60,
    "reg_alpha": 1.0,
    "reg_lambda": 10.0,
    "tree_method": "hist",
    "random_state": RANDOM_STATE,
    "n_jobs": 1,
}


class FrozenXgboostError(RuntimeError):
    """Raised when the frozen fusion contract cannot be evaluated."""


def add_fixed_rank_fusion(
    frame: pd.DataFrame,
    score_a: str = LR_SCORE_COLUMN,
    score_b: str = XGB_SCORE_COLUMN,
) -> pd.DataFrame:
    result = frame.copy()
    result["score_a_percentile"] = result.groupby(DATE_COLUMN)[score_a].rank(
        method="average", pct=True, ascending=True
    )
    result["score_b_percentile"] = result.groupby(DATE_COLUMN)[score_b].rank(
        method="average", pct=True, ascending=True
    )
    result[FUSION_SCORE_COLUMN] = 0.5 * (
        result["score_a_percentile"] + result["score_b_percentile"]
    )
    return result


def fit_xgboost(train: pd.DataFrame, feature_columns: list[str]) -> XGBClassifier:
    model = XGBClassifier(**XGBOOST_PARAMS)
    model.fit(
        logistic_core.prepare_x(train, feature_columns),
        train[TARGET_COLUMN].astype("int64"),
        sample_weight=train[WEIGHT_COLUMN].astype("float64"),
        verbose=False,
    )
    return model


def predict_xgboost(
    model: XGBClassifier,
    frame: pd.DataFrame,
    feature_columns: list[str],
) -> np.ndarray:
    return np.asarray(
        model.predict_proba(logistic_core.prepare_x(frame, feature_columns))[:, 1],
        dtype="float64",
    )


def booster_dump_sha256(model: XGBClassifier) -> str:
    payload = "\n".join(model.get_booster().get_dump(dump_format="json"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def selected_future_path_drawdown(
    daily: pd.DataFrame,
    *,
    eval_date: pd.Timestamp,
    products: list[str] | tuple[str, ...],
    horizon: int = 60,
) -> float:
    required = {"date", PRODUCT_COLUMN, "net_pnl"}
    missing = sorted(required - set(daily.columns))
    if missing:
        raise FrozenXgboostError(f"daily_columns_missing:{','.join(missing)}")
    if horizon <= 0:
        raise FrozenXgboostError("horizon_must_be_positive")
    frame = daily[list(required)].copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="raise").dt.normalize()
    frame[PRODUCT_COLUMN] = frame[PRODUCT_COLUMN].astype(str)
    frame["net_pnl"] = pd.to_numeric(frame["net_pnl"], errors="raise").astype("float64")
    selected = sorted(set(map(str, products)))
    future_dates = pd.DatetimeIndex(
        sorted(frame.loc[frame["date"].gt(pd.Timestamp(eval_date).normalize()), "date"].unique())
    )[:horizon]
    if len(future_dates) != horizon:
        raise FrozenXgboostError(
            f"future_path_incomplete:{pd.Timestamp(eval_date).date().isoformat()}:{len(future_dates)}"
        )
    path = frame[
        frame["date"].isin(future_dates)
        & frame[PRODUCT_COLUMN].isin(selected)
    ].copy()
    expected_rows = horizon * len(selected)
    if len(path) != expected_rows or path.duplicated(["date", PRODUCT_COLUMN]).any():
        raise FrozenXgboostError(
            f"future_path_shape:{pd.Timestamp(eval_date).date().isoformat()}:{len(path)}:{expected_rows}"
        )
    daily_pnl = path.groupby("date", sort=True)["net_pnl"].sum().reindex(future_dates)
    if daily_pnl.isna().any():
        raise FrozenXgboostError("future_path_daily_gap")
    cumulative = daily_pnl.to_numpy(dtype="float64").cumsum()
    high_water = np.maximum.accumulate(np.concatenate([[0.0], cumulative]))[1:]
    return float(np.min(cumulative - high_water))


def mean_monthly_turnover(selections: dict[pd.Timestamp, tuple[str, ...]]) -> float:
    dates = sorted(selections)
    if len(dates) < 2:
        return 0.0
    values = []
    for previous, current in zip(dates, dates[1:]):
        old = set(selections[previous])
        new = set(selections[current])
        values.append(len(new - old) / max(1, len(new)))
    return float(np.mean(values))


def build_arm_monthly_metrics(
    predictions: pd.DataFrame,
    daily: pd.DataFrame,
    score_columns: dict[str, str],
) -> tuple[pd.DataFrame, dict[str, dict[pd.Timestamp, tuple[str, ...]]]]:
    rows: list[dict[str, Any]] = []
    selections: dict[str, dict[pd.Timestamp, tuple[str, ...]]] = {
        arm: {} for arm in score_columns
    }
    for eval_date, month in predictions.groupby(DATE_COLUMN, sort=True):
        date = pd.Timestamp(eval_date)
        for arm, score_column in score_columns.items():
            ordered = month.sort_values(
                [score_column, PRODUCT_COLUMN],
                ascending=[False, True],
                kind="mergesort",
            )
            selected = ordered.head(min(TOP_N, len(ordered)))
            products = tuple(selected[PRODUCT_COLUMN].astype(str))
            selections[arm][date] = products
            rows.append(
                {
                    DATE_COLUMN: date,
                    "year": int(date.year),
                    "arm": arm,
                    "candidate_count": int(len(month)),
                    "rank_ic": float(
                        month[score_column].corr(
                            month[FUTURE_RANK_COLUMN], method="spearman"
                        )
                    ),
                    "top10_products": ",".join(products),
                    "top10_total_future_net_pnl_60d": float(
                        selected[FUTURE_PNL_COLUMN].sum()
                    ),
                    "top10_target_rate": float(selected[TARGET_COLUMN].mean()),
                    "top10_future_path_drawdown_60d": selected_future_path_drawdown(
                        daily,
                        eval_date=date,
                        products=products,
                        horizon=60,
                    ),
                }
            )
    return pd.DataFrame(rows), selections


def summarize_arm(
    monthly: pd.DataFrame,
    selections: dict[str, dict[pd.Timestamp, tuple[str, ...]]],
    arm: str,
) -> dict[str, Any]:
    rows = monthly[monthly["arm"].eq(arm)].copy()
    return {
        "months": int(rows[DATE_COLUMN].nunique()),
        "mean_rank_ic": float(rows["rank_ic"].mean()),
        "median_rank_ic": float(rows["rank_ic"].median()),
        "top10_mean_future_pnl": float(
            rows["top10_total_future_net_pnl_60d"].mean()
        ),
        "top10_p10_future_pnl": float(
            rows["top10_total_future_net_pnl_60d"].quantile(0.10)
        ),
        "top10_target_rate": float(rows["top10_target_rate"].mean()),
        "mean_path_drawdown": float(
            rows["top10_future_path_drawdown_60d"].mean()
        ),
        "p10_path_drawdown": float(
            rows["top10_future_path_drawdown_60d"].quantile(0.10)
        ),
        "turnover": mean_monthly_turnover(selections[arm]),
    }


def build_effect_summary(monthly: pd.DataFrame, arm_summary: dict[str, dict[str, Any]]) -> dict[str, Any]:
    yearly = (
        monthly.groupby(["year", "arm"], as_index=False)["rank_ic"].mean()
        .pivot(index="year", columns="arm", values="rank_ic")
        .sort_index()
    )
    yearly_delta = yearly["C_fusion"] - yearly["A_logistic"]
    a = arm_summary["A_logistic"]
    c = arm_summary["C_fusion"]
    return {
        "a_mean_rank_ic": a["mean_rank_ic"],
        "c_mean_rank_ic": c["mean_rank_ic"],
        "a_median_rank_ic": a["median_rank_ic"],
        "c_median_rank_ic": c["median_rank_ic"],
        "a_top10_mean_future_pnl": a["top10_mean_future_pnl"],
        "c_top10_mean_future_pnl": c["top10_mean_future_pnl"],
        "a_top10_p10_future_pnl": a["top10_p10_future_pnl"],
        "c_top10_p10_future_pnl": c["top10_p10_future_pnl"],
        "a_top10_target_rate": a["top10_target_rate"],
        "c_top10_target_rate": c["top10_target_rate"],
        "a_mean_path_drawdown": a["mean_path_drawdown"],
        "c_mean_path_drawdown": c["mean_path_drawdown"],
        "a_p10_path_drawdown": a["p10_path_drawdown"],
        "c_p10_path_drawdown": c["p10_path_drawdown"],
        "a_turnover": a["turnover"],
        "c_turnover": c["turnover"],
        "yearly_c_rank_ic_wins": int((yearly_delta > 0.0).sum()),
        "worst_year_rank_ic_delta": float(yearly_delta.min()),
        "yearly_rank_ic": {
            str(int(year)): {
                arm: float(value)
                for arm, value in row.dropna().items()
            }
            for year, row in yearly.iterrows()
        },
    }


def evaluate_c_effect_gates(summary: dict[str, Any]) -> dict[str, bool]:
    return {
        "mean_rank_ic_strictly_better": float(summary["c_mean_rank_ic"])
        > float(summary["a_mean_rank_ic"]),
        "median_rank_ic_noninferior": float(summary["c_median_rank_ic"])
        >= float(summary["a_median_rank_ic"]),
        "top10_mean_future_pnl_strictly_better": float(
            summary["c_top10_mean_future_pnl"]
        )
        > float(summary["a_top10_mean_future_pnl"]),
        "top10_p10_future_pnl_noninferior": float(
            summary["c_top10_p10_future_pnl"]
        )
        >= float(summary["a_top10_p10_future_pnl"]),
        "top10_target_rate_noninferior": float(summary["c_top10_target_rate"])
        >= float(summary["a_top10_target_rate"]),
        "mean_path_drawdown_strictly_better": float(
            summary["c_mean_path_drawdown"]
        )
        > float(summary["a_mean_path_drawdown"]),
        "p10_path_drawdown_noninferior": float(summary["c_p10_path_drawdown"])
        >= float(summary["a_p10_path_drawdown"]),
        "turnover_le_105pct": float(summary["c_turnover"])
        <= 1.05 * float(summary["a_turnover"]) + 1e-12,
        "yearly_rank_ic_wins_ge_3": int(summary["yearly_c_rank_ic_wins"]) >= 3,
        "worst_year_rank_ic_delta_ge_minus_003": float(
            summary["worst_year_rank_ic_delta"]
        )
        >= -0.03,
    }

