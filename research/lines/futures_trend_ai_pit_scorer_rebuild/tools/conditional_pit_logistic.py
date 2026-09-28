"""Conditional PIT sample and logistic-baseline primitives."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


TOOL_DIR = Path(__file__).resolve().parent
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

import pit_scorer_audit as audit_core  # noqa: E402


DATE_COLUMN = "eval_date"
PRODUCT_COLUMN = "product_vt_symbol"
TARGET_COLUMN = "target_future_top_half_60d"
WEIGHT_COLUMN = "sample_weight_future_rank_60d"
FUTURE_PNL_COLUMN = "future_net_pnl_60d"
FUTURE_RANK_COLUMN = "pit_future_rank_centered_60d"
PROBABILITY_COLUMN = "pit_logistic_probability"
RANDOM_STATE = 42
LOGISTIC_C = 0.20
TOP_N = 10

PASS_DECISION = "stage002_conditional_pit_logistic_pass_allow_frozen_xgboost_design"
FAIL_DECISION = "stage002_conditional_pit_logistic_fail_stop_no_xgboost"


@dataclass(frozen=True)
class ConditionalPitFold:
    window_id: str
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp
    train_dates: pd.DatetimeIndex
    test_dates: pd.DatetimeIndex
    train_label_end_max: pd.Timestamp
    train_rows: int
    test_rows: int


class ConditionalPitError(RuntimeError):
    """Raised when conditional PIT data violates the frozen contract."""


def discover_feature_columns(frame: pd.DataFrame) -> list[str]:
    forbidden_prefixes = (
        "future_",
        "target_",
        "sample_weight_",
        "pit_future_",
        "pit_target_",
    )
    columns = [
        column
        for column in frame.columns
        if any(column.endswith(f"_{window}d") for window in (20, 60, 120))
        and not column.startswith(forbidden_prefixes)
    ]
    return sorted(set(columns))


def _as_bool(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.astype(bool)
    values = series.astype(str).str.strip().str.lower()
    invalid = ~values.isin({"true", "false", "1", "0"})
    if invalid.any():
        raise ConditionalPitError("boolean_column_invalid")
    return values.isin({"true", "1"})


def build_conditional_samples(
    samples: pd.DataFrame,
    boundaries: pd.DataFrame,
    effective_listing_dates: dict[str, pd.Timestamp],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    key = [DATE_COLUMN, PRODUCT_COLUMN]
    needed_boundary = {
        *key,
        "future_label_end_date",
        "future_observation_count",
        "full_horizon_label",
    }
    missing = sorted(needed_boundary - set(boundaries.columns))
    if missing:
        raise ConditionalPitError(f"boundary_columns_missing:{','.join(missing)}")
    if samples.duplicated(key).any() or boundaries.duplicated(key).any():
        raise ConditionalPitError("sample_boundary_key_duplicate")

    sample = samples.copy()
    boundary = boundaries[
        key
        + [
            "future_label_end_date",
            "future_observation_count",
            "full_horizon_label",
        ]
    ].copy()
    sample[DATE_COLUMN] = pd.to_datetime(sample[DATE_COLUMN], errors="raise").dt.normalize()
    boundary[DATE_COLUMN] = pd.to_datetime(boundary[DATE_COLUMN], errors="raise").dt.normalize()
    boundary["future_label_end_date"] = pd.to_datetime(
        boundary["future_label_end_date"], errors="raise"
    ).dt.normalize()
    boundary["full_horizon_label"] = _as_bool(boundary["full_horizon_label"])
    merged = sample.merge(boundary, on=key, how="left", validate="one_to_one")
    if merged["future_label_end_date"].isna().any():
        raise ConditionalPitError("sample_boundary_join_missing")
    if len(merged) != len(sample):
        raise ConditionalPitError("sample_boundary_row_count_drift")

    partial_count = int((~merged["full_horizon_label"]).sum())
    full = merged[merged["full_horizon_label"]].copy()
    eligible, listing_month_audit = audit_core.apply_listing_filter_before_target(
        full, effective_listing_dates
    )
    unlisted_count = int(listing_month_audit["ineligible_sample_rows"].sum())
    eligible[TARGET_COLUMN] = eligible[audit_core.PIT_TARGET_COLUMN].astype("int64")
    eligible[WEIGHT_COLUMN] = (
        eligible[FUTURE_RANK_COLUMN].abs().clip(lower=0.20, upper=0.60)
    )
    eligible.sort_values([DATE_COLUMN, PRODUCT_COLUMN], inplace=True, kind="mergesort")
    eligible.reset_index(drop=True, inplace=True)
    return eligible, {
        "legacy_rows": int(len(samples)),
        "partial_horizon_rows_removed": partial_count,
        "unlisted_rows_removed": unlisted_count,
        "conditional_rows": int(len(eligible)),
        "conditional_months": int(eligible[DATE_COLUMN].nunique()),
        "conditional_products": int(eligible[PRODUCT_COLUMN].nunique()),
        "minimum_monthly_cross_section": int(
            eligible.groupby(DATE_COLUMN).size().min()
        ),
        "maximum_monthly_cross_section": int(
            eligible.groupby(DATE_COLUMN).size().max()
        ),
        "listing_target_changed_rows": int(
            listing_month_audit["eligible_target_changed_rows"].sum()
        ),
    }


def build_fold_contracts(
    panel: pd.DataFrame,
    windows: pd.DataFrame,
    *,
    min_train_rows: int = 180,
    min_test_rows: int = 45,
) -> tuple[list[ConditionalPitFold], pd.DataFrame]:
    required_panel = {
        DATE_COLUMN,
        PRODUCT_COLUMN,
        "future_label_end_date",
        TARGET_COLUMN,
    }
    missing_panel = sorted(required_panel - set(panel.columns))
    if missing_panel:
        raise ConditionalPitError(f"panel_columns_missing:{','.join(missing_panel)}")
    required_window = {"window_id", "train_start", "train_end", "test_start", "test_end"}
    missing_window = sorted(required_window - set(windows.columns))
    if missing_window:
        raise ConditionalPitError(f"window_columns_missing:{','.join(missing_window)}")

    frame = panel.copy()
    frame[DATE_COLUMN] = pd.to_datetime(frame[DATE_COLUMN], errors="raise").dt.normalize()
    frame["future_label_end_date"] = pd.to_datetime(
        frame["future_label_end_date"], errors="raise"
    ).dt.normalize()
    fold_rows = windows[list(required_window)].drop_duplicates().copy()
    for column in ("train_start", "train_end", "test_start", "test_end"):
        fold_rows[column] = pd.to_datetime(fold_rows[column], errors="raise").dt.normalize()
    if fold_rows["window_id"].duplicated().any():
        raise ConditionalPitError("window_boundary_duplicate")

    folds: list[ConditionalPitFold] = []
    audits: list[dict[str, Any]] = []
    for row in fold_rows.sort_values("window_id", kind="mergesort").itertuples(index=False):
        calendar_train = frame[
            frame[DATE_COLUMN].ge(row.train_start)
            & frame[DATE_COLUMN].lt(row.train_end)
        ].copy()
        train = calendar_train[
            calendar_train["future_label_end_date"].lt(row.test_start)
        ].copy()
        test = frame[
            frame[DATE_COLUMN].ge(row.test_start)
            & frame[DATE_COLUMN].lt(row.test_end)
        ].copy()
        reject_reason = ""
        if len(train) < min_train_rows:
            reject_reason = "train_rows_below_minimum"
        elif len(test) < min_test_rows:
            reject_reason = "test_rows_below_minimum"
        elif train[TARGET_COLUMN].nunique() < 2:
            reject_reason = "train_target_single_class"
        elif test[TARGET_COLUMN].nunique() < 2:
            reject_reason = "test_target_single_class"
        accepted = not reject_reason
        train_dates = pd.DatetimeIndex(sorted(train[DATE_COLUMN].unique()))
        test_dates = pd.DatetimeIndex(sorted(test[DATE_COLUMN].unique()))
        train_label_end_max = (
            pd.Timestamp(train["future_label_end_date"].max())
            if not train.empty
            else pd.NaT
        )
        pit_violations = int(
            train["future_label_end_date"].ge(row.test_start).sum()
        )
        audits.append(
            {
                "window_id": str(row.window_id),
                "train_start": pd.Timestamp(row.train_start),
                "train_end": pd.Timestamp(row.train_end),
                "test_start": pd.Timestamp(row.test_start),
                "test_end": pd.Timestamp(row.test_end),
                "calendar_train_rows": int(len(calendar_train)),
                "purged_train_rows": int(len(calendar_train) - len(train)),
                "train_rows": int(len(train)),
                "train_months": int(len(train_dates)),
                "test_rows": int(len(test)),
                "test_months": int(len(test_dates)),
                "train_label_end_max": train_label_end_max,
                "pit_violation_rows": pit_violations,
                "accepted": bool(accepted),
                "reject_reason": reject_reason,
            }
        )
        if accepted:
            folds.append(
                ConditionalPitFold(
                    window_id=str(row.window_id),
                    train_start=pd.Timestamp(row.train_start),
                    train_end=pd.Timestamp(row.train_end),
                    test_start=pd.Timestamp(row.test_start),
                    test_end=pd.Timestamp(row.test_end),
                    train_dates=train_dates,
                    test_dates=test_dates,
                    train_label_end_max=train_label_end_max,
                    train_rows=int(len(train)),
                    test_rows=int(len(test)),
                )
            )
    return folds, pd.DataFrame(audits)


def prepare_x(frame: pd.DataFrame, feature_columns: list[str]) -> pd.DataFrame:
    missing = sorted(set(feature_columns) - set(frame.columns))
    if missing:
        raise ConditionalPitError(f"feature_columns_missing:{','.join(missing)}")
    return (
        frame[feature_columns]
        .replace([np.inf, -np.inf], np.nan)
        .fillna(0.0)
        .astype("float64")
    )


def fit_logistic(train: pd.DataFrame, feature_columns: list[str]) -> Pipeline:
    pipeline = Pipeline(
        [
            ("scaler", StandardScaler()),
            (
                "classifier",
                LogisticRegression(
                    C=LOGISTIC_C,
                    solver="lbfgs",
                    max_iter=3000,
                    random_state=RANDOM_STATE,
                ),
            ),
        ]
    )
    pipeline.fit(
        prepare_x(train, feature_columns),
        train[TARGET_COLUMN].astype("int64"),
        classifier__sample_weight=train[WEIGHT_COLUMN].astype("float64"),
    )
    return pipeline


def predict_probability(
    pipeline: Pipeline,
    frame: pd.DataFrame,
    feature_columns: list[str],
) -> np.ndarray:
    return np.asarray(
        pipeline.predict_proba(prepare_x(frame, feature_columns))[:, 1],
        dtype="float64",
    )


def _model_state(pipeline: Pipeline) -> np.ndarray:
    scaler: StandardScaler = pipeline.named_steps["scaler"]
    classifier: LogisticRegression = pipeline.named_steps["classifier"]
    return np.concatenate(
        [
            np.asarray(scaler.mean_, dtype="float64").ravel(),
            np.asarray(scaler.scale_, dtype="float64").ravel(),
            np.asarray(classifier.coef_, dtype="float64").ravel(),
            np.asarray(classifier.intercept_, dtype="float64").ravel(),
        ]
    )


def model_state_max_abs_diff(first: Pipeline, second: Pipeline) -> float:
    left = _model_state(first)
    right = _model_state(second)
    if left.shape != right.shape:
        return float("inf")
    return float(np.max(np.abs(left - right))) if left.size else 0.0


def model_parameter_rows(
    pipeline: Pipeline,
    feature_columns: list[str],
    *,
    window_id: str,
) -> pd.DataFrame:
    scaler: StandardScaler = pipeline.named_steps["scaler"]
    classifier: LogisticRegression = pipeline.named_steps["classifier"]
    return pd.DataFrame(
        {
            "window_id": window_id,
            "feature": feature_columns,
            "scaler_mean": np.asarray(scaler.mean_, dtype="float64"),
            "scaler_scale": np.asarray(scaler.scale_, dtype="float64"),
            "logistic_coefficient": np.asarray(classifier.coef_[0], dtype="float64"),
            "logistic_intercept": float(classifier.intercept_[0]),
        }
    )


def build_monthly_metrics(predictions: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for eval_date, month in predictions.groupby(DATE_COLUMN, sort=True):
        ordered = month.sort_values(
            [PROBABILITY_COLUMN, PRODUCT_COLUMN],
            ascending=[False, True],
            kind="mergesort",
        )
        top = ordered.head(min(TOP_N, len(ordered)))
        rows.append(
            {
                DATE_COLUMN: pd.Timestamp(eval_date),
                "window_id": str(month["window_id"].iloc[0]),
                "candidate_count": int(len(month)),
                "rank_ic": float(
                    month[PROBABILITY_COLUMN].corr(
                        month[FUTURE_RANK_COLUMN], method="spearman"
                    )
                ),
                "top10_products": ",".join(top[PRODUCT_COLUMN].astype(str)),
                "top10_total_future_net_pnl_60d": float(top[FUTURE_PNL_COLUMN].sum()),
                "top10_mean_future_net_pnl_60d": float(top[FUTURE_PNL_COLUMN].mean()),
                "top10_target_rate": float(top[TARGET_COLUMN].mean()),
            }
        )
    return pd.DataFrame(rows)


def prediction_metrics(
    predictions: pd.DataFrame,
    monthly_metrics: pd.DataFrame,
) -> dict[str, Any]:
    actual = predictions[TARGET_COLUMN].astype("int64")
    probability = predictions[PROBABILITY_COLUMN].astype("float64").clip(
        1e-6, 1.0 - 1e-6
    )
    return {
        "rows": int(len(predictions)),
        "months": int(predictions[DATE_COLUMN].nunique()),
        "products": int(predictions[PRODUCT_COLUMN].nunique()),
        "roc_auc": float(roc_auc_score(actual, probability)),
        "log_loss": float(log_loss(actual, probability, labels=[0, 1])),
        "brier_score": float(brier_score_loss(actual, probability)),
        "mean_monthly_rank_ic": float(monthly_metrics["rank_ic"].mean()),
        "median_monthly_rank_ic": float(monthly_metrics["rank_ic"].median()),
        "top10_mean_monthly_future_net_pnl_60d": float(
            monthly_metrics["top10_total_future_net_pnl_60d"].mean()
        ),
        "top10_p10_monthly_future_net_pnl_60d": float(
            monthly_metrics["top10_total_future_net_pnl_60d"].quantile(0.10)
        ),
        "top10_mean_target_rate": float(monthly_metrics["top10_target_rate"].mean()),
    }


def stage002_decision(gates: dict[str, bool]) -> str:
    return PASS_DECISION if gates and all(bool(value) for value in gates.values()) else FAIL_DECISION
