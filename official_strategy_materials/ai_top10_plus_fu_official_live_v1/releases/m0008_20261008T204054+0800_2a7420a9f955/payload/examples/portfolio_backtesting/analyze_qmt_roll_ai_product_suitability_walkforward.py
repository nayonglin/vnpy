from __future__ import annotations

import json
import math
import re
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss, f1_score, log_loss, precision_score, recall_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from qmt_universe import VT_SYMBOLS


warnings.filterwarnings("ignore", category=pd.errors.PerformanceWarning)
warnings.filterwarnings("ignore", category=FutureWarning, message="DataFrameGroupBy.apply operated on the grouping columns.*")

PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "product_suitability_wf_v1"
SOURCE_PREFIX: str = "qmt_roll_selection_long015_volref30_corr_formal_floor35"
OUTPUT_PREFIX: str = "qmt_roll_ai_product_suitability_walkforward"

POSITION_CHANGES_PATH: Path = OUTPUT_DIR / f"{SOURCE_PREFIX}_position_changes_2020_2026_04.csv"
ENTRY_SNAPSHOTS_PATH: Path = OUTPUT_DIR / f"{SOURCE_PREFIX}_entry_candidate_snapshots_2020_2026_04.csv"

PRODUCT_DAILY_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
SAMPLES_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_samples_{MODEL_TAG}.csv"
PREDICTIONS_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_predictions_{MODEL_TAG}.csv"
WINDOW_METRICS_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_metrics_{MODEL_TAG}.csv"
BUCKET_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_analysis_{MODEL_TAG}.csv"
TOP_PRODUCTS_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_top_products_{MODEL_TAG}.csv"
COEFFICIENT_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_coefficients_{MODEL_TAG}.csv"
SUMMARY_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

FUTURE_HORIZON_DAYS: int = 60
ROLLING_WINDOWS: tuple[int, ...] = (20, 60, 120)
TRAIN_WINDOW_DAYS: int = 720
TEST_WINDOW_DAYS: int = 180
STEP_DAYS: int = 180
MIN_TRAIN_ROWS: int = 180
MIN_TEST_ROWS: int = 45
TOP_N_PRODUCTS: int = 5
LOGISTIC_C: float = 0.20
RANDOM_STATE: int = 42

DATE_COLUMN: str = "eval_date"
TARGET_COLUMN: str = "target_future_top_half_60d"
WEIGHT_COLUMN: str = "sample_weight_future_rank_60d"
PROBABILITY_COLUMN: str = "predicted_product_suitability_probability"
SIMPLE_SCORE_COLUMN: str = "simple_trend_suitability_score"
SIMPLE_SCORE_PERCENTILE_COLUMN: str = "simple_trend_suitability_score_percentile"


@dataclass(frozen=True)
class WalkForwardWindow:
    window_id: str
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or math.isinf(result):
        return default
    return result


def _numeric_series(df: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in df.columns:
        return pd.Series(default, index=df.index, dtype="float64")
    return pd.to_numeric(df[column], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(default)


def product_from_contract(vt_symbol: object) -> str:
    raw = str(vt_symbol)
    if "." not in raw:
        return raw
    symbol, exchange = raw.split(".", 1)
    match = re.match(r"^([A-Za-z]+)", symbol)
    product = match.group(1) if match else symbol
    return f"{product}.{exchange}"


def _complete_product_frame(df: pd.DataFrame, dates: pd.DatetimeIndex, products: list[str]) -> pd.DataFrame:
    index = pd.MultiIndex.from_product([dates, products], names=["date", "product_vt_symbol"])
    result = df.set_index(["date", "product_vt_symbol"]).reindex(index).reset_index()
    numeric_columns = [column for column in result.columns if column not in {"date", "product_vt_symbol"}]
    result[numeric_columns] = result[numeric_columns].fillna(0.0)
    return result


def load_product_pnl_daily() -> pd.DataFrame:
    if not POSITION_CHANGES_PATH.exists():
        raise FileNotFoundError(f"missing source position changes: {POSITION_CHANGES_PATH}")

    columns = [
        "date",
        "vt_symbol",
        "start_pos",
        "end_pos",
        "pos_change",
        "trade_count",
        "turnover",
        "commission",
        "slippage",
        "holding_pnl",
        "trading_pnl",
        "total_pnl",
        "net_pnl",
    ]
    df = pd.read_csv(POSITION_CHANGES_PATH, usecols=lambda column: column in columns)
    df["date"] = pd.to_datetime(df["date"])
    df["product_vt_symbol"] = df["vt_symbol"].map(product_from_contract)
    for column in columns:
        if column not in {"date", "vt_symbol"}:
            df[column] = _numeric_series(df, column)
    df["abs_end_pos"] = df["end_pos"].abs()
    df["abs_pos_change"] = df["pos_change"].abs()
    df["active_contract_flag"] = (df["abs_end_pos"] > 0).astype("float64")

    grouped = (
        df.groupby(["date", "product_vt_symbol"], as_index=False)
        .agg(
            net_pnl=("net_pnl", "sum"),
            total_pnl=("total_pnl", "sum"),
            trading_pnl=("trading_pnl", "sum"),
            holding_pnl=("holding_pnl", "sum"),
            slippage=("slippage", "sum"),
            commission=("commission", "sum"),
            turnover=("turnover", "sum"),
            trade_count=("trade_count", "sum"),
            abs_end_pos=("abs_end_pos", "sum"),
            abs_pos_change=("abs_pos_change", "sum"),
            active_contract_count=("active_contract_flag", "sum"),
        )
    )

    dates = pd.DatetimeIndex(sorted(grouped["date"].unique()))
    products = sorted(set(VT_SYMBOLS) | set(grouped["product_vt_symbol"].unique()))
    return _complete_product_frame(grouped, dates, products)


def load_candidate_daily(dates: pd.DatetimeIndex, products: list[str]) -> pd.DataFrame:
    base = pd.DataFrame({"date": dates})
    if not ENTRY_SNAPSHOTS_PATH.exists():
        empty = pd.MultiIndex.from_product([dates, products], names=["date", "product_vt_symbol"]).to_frame(index=False)
        return empty

    useful_columns = [
        "date",
        "product_vt_symbol",
        "candidate_status",
        "selected_volume",
        "selected_volume_ungated",
        "same_direction_correlation_gate_enabled",
        "same_direction_correlation_gate_weight",
        "same_direction_correlation_active_count",
        "same_direction_correlation_max_corr",
        "selection_pairwise_score",
        "selection_pairwise_rank",
        "selection_pairwise_volume_tilt_applied",
        "selection_pairwise_volume_tilt_multiplier",
        "selection_pairwise_volume_tilt_score_gap",
        "selection_pairwise_volume_tilt_top_gap",
        "active_positions_before",
        "breakout",
        "bullish_alignment",
        "bearish_alignment",
        "rsi_value",
        "loss_streak",
        "is_opened",
    ]
    df = pd.read_csv(ENTRY_SNAPSHOTS_PATH, usecols=lambda column: column in useful_columns)
    if df.empty:
        empty = pd.MultiIndex.from_product([dates, products], names=["date", "product_vt_symbol"]).to_frame(index=False)
        return empty

    df["date"] = pd.to_datetime(df["date"])
    for column in useful_columns:
        if column not in {"date", "product_vt_symbol", "candidate_status"}:
            df[column] = _numeric_series(df, column)
    df["opened_flag"] = (df.get("candidate_status", "") == "opened").astype("float64")

    grouped = (
        df.groupby(["date", "product_vt_symbol"], as_index=False)
        .agg(
            candidate_count=("product_vt_symbol", "size"),
            opened_count=("opened_flag", "sum"),
            selected_volume_sum=("selected_volume", "sum"),
            selected_volume_ungated_sum=("selected_volume_ungated", "sum"),
            corr_gate_enabled_count=("same_direction_correlation_gate_enabled", "sum"),
            avg_corr_gate_weight=("same_direction_correlation_gate_weight", "mean"),
            avg_same_direction_active_count=("same_direction_correlation_active_count", "mean"),
            avg_same_direction_max_corr=("same_direction_correlation_max_corr", "mean"),
            avg_pairwise_score=("selection_pairwise_score", "mean"),
            best_pairwise_rank=("selection_pairwise_rank", "min"),
            volume_tilt_applied_count=("selection_pairwise_volume_tilt_applied", "sum"),
            avg_volume_tilt_multiplier=("selection_pairwise_volume_tilt_multiplier", "mean"),
            avg_volume_tilt_score_gap=("selection_pairwise_volume_tilt_score_gap", "mean"),
            avg_volume_tilt_top_gap=("selection_pairwise_volume_tilt_top_gap", "mean"),
            avg_active_positions_before=("active_positions_before", "mean"),
            breakout_rate=("breakout", "mean"),
            bullish_alignment_rate=("bullish_alignment", "mean"),
            bearish_alignment_rate=("bearish_alignment", "mean"),
            avg_rsi=("rsi_value", "mean"),
            avg_loss_streak=("loss_streak", "mean"),
            opened_rate=("is_opened", "mean"),
        )
    )
    complete = _complete_product_frame(grouped, dates, products)
    # Missing candidate days are true zero-signal days; weights stay neutral for averages.
    neutral_columns = [
        "avg_corr_gate_weight",
        "avg_volume_tilt_multiplier",
    ]
    for column in neutral_columns:
        if column in complete.columns:
            complete[column] = complete[column].replace(0.0, 1.0)
    return base.merge(complete, on="date", how="right")


def build_product_daily() -> pd.DataFrame:
    pnl_daily = load_product_pnl_daily()
    dates = pd.DatetimeIndex(sorted(pnl_daily["date"].unique()))
    products = sorted(pnl_daily["product_vt_symbol"].unique())
    candidate_daily = load_candidate_daily(dates, products)
    daily = pnl_daily.merge(candidate_daily, on=["date", "product_vt_symbol"], how="left")
    numeric_columns = [column for column in daily.columns if column not in {"date", "product_vt_symbol"}]
    daily[numeric_columns] = daily[numeric_columns].fillna(0.0)
    daily.sort_values(["product_vt_symbol", "date"], inplace=True)
    daily.reset_index(drop=True, inplace=True)
    return daily


def _rolling_future_sum(series: pd.Series, horizon: int) -> pd.Series:
    return series.iloc[::-1].rolling(horizon, min_periods=max(20, horizon // 2)).sum().iloc[::-1].shift(-1)


def _rolling_drawdown(values: pd.Series, window: int) -> pd.Series:
    cumulative = values.cumsum()

    def drawdown(window_values: np.ndarray) -> float:
        high_water = np.maximum.accumulate(window_values)
        return float(np.min(window_values - high_water))

    return cumulative.rolling(window, min_periods=max(10, window // 2)).apply(drawdown, raw=True)


def add_rolling_features(daily: pd.DataFrame) -> pd.DataFrame:
    result = daily.copy()
    result["pnl_positive_day"] = (result["net_pnl"] > 0).astype("float64")
    result["trade_day"] = (result["trade_count"] > 0).astype("float64")
    result["candidate_day"] = (result["candidate_count"] > 0).astype("float64")
    result["opened_day"] = (result["opened_count"] > 0).astype("float64")

    sum_columns = [
        "net_pnl",
        "slippage",
        "turnover",
        "trade_count",
        "abs_pos_change",
        "active_contract_count",
        "candidate_count",
        "opened_count",
        "selected_volume_sum",
        "selected_volume_ungated_sum",
        "corr_gate_enabled_count",
        "volume_tilt_applied_count",
    ]
    mean_columns = [
        "pnl_positive_day",
        "trade_day",
        "candidate_day",
        "opened_day",
        "avg_corr_gate_weight",
        "avg_same_direction_active_count",
        "avg_same_direction_max_corr",
        "avg_pairwise_score",
        "best_pairwise_rank",
        "avg_volume_tilt_multiplier",
        "avg_volume_tilt_score_gap",
        "avg_volume_tilt_top_gap",
        "avg_active_positions_before",
        "breakout_rate",
        "bullish_alignment_rate",
        "bearish_alignment_rate",
        "avg_rsi",
        "avg_loss_streak",
    ]

    frames: list[pd.DataFrame] = []
    for _, group in result.groupby("product_vt_symbol", sort=False):
        group = group.sort_values("date").copy()
        for window in ROLLING_WINDOWS:
            min_periods = max(10, window // 2)
            rolling = group.rolling(window=window, min_periods=min_periods)
            for column in sum_columns:
                group[f"{column}_sum_{window}d"] = rolling[column].sum()
            for column in mean_columns:
                group[f"{column}_mean_{window}d"] = rolling[column].mean()
            group[f"net_pnl_mean_{window}d"] = rolling["net_pnl"].mean()
            group[f"net_pnl_std_{window}d"] = rolling["net_pnl"].std()
            group[f"net_pnl_sharpe_like_{window}d"] = (
                group[f"net_pnl_mean_{window}d"] / group[f"net_pnl_std_{window}d"].replace(0.0, np.nan)
            ) * math.sqrt(window)
            group[f"net_pnl_min_day_{window}d"] = rolling["net_pnl"].min()
            group[f"net_pnl_max_day_{window}d"] = rolling["net_pnl"].max()
            group[f"net_pnl_drawdown_{window}d"] = _rolling_drawdown(group["net_pnl"], window)
        group[f"future_net_pnl_{FUTURE_HORIZON_DAYS}d"] = _rolling_future_sum(group["net_pnl"], FUTURE_HORIZON_DAYS)
        frames.append(group)

    featured = pd.concat(frames, ignore_index=True)
    feature_like_columns = [
        column
        for column in featured.columns
        if column.endswith("d") and column != f"future_net_pnl_{FUTURE_HORIZON_DAYS}d"
    ]
    featured[feature_like_columns] = featured[feature_like_columns].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return featured


def build_monthly_samples(featured_daily: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    daily = featured_daily.copy()
    daily["month"] = daily["date"].dt.to_period("M")
    eval_dates = daily.groupby("month")["date"].max().sort_values().tolist()
    samples = daily[daily["date"].isin(eval_dates)].copy()
    samples.rename(columns={"date": DATE_COLUMN}, inplace=True)
    samples = samples.dropna(subset=[f"future_net_pnl_{FUTURE_HORIZON_DAYS}d"]).copy()
    samples["cross_section_count"] = samples.groupby(DATE_COLUMN)["product_vt_symbol"].transform("size")
    samples = samples[samples["cross_section_count"] >= 8].copy()

    future_column = f"future_net_pnl_{FUTURE_HORIZON_DAYS}d"
    samples["future_rank_pct_60d"] = samples.groupby(DATE_COLUMN)[future_column].rank(method="average", pct=True)
    samples["future_rank_centered_60d"] = samples["future_rank_pct_60d"] - 0.5
    samples[TARGET_COLUMN] = (samples["future_rank_centered_60d"] > 0.0).astype("int64")
    samples[WEIGHT_COLUMN] = samples["future_rank_centered_60d"].abs().clip(lower=0.20, upper=0.60)

    excluded_feature_columns = {
        DATE_COLUMN,
        "date",
        "month",
        "product_vt_symbol",
        "cross_section_count",
        f"future_net_pnl_{FUTURE_HORIZON_DAYS}d",
        "future_rank_pct_60d",
        "future_rank_centered_60d",
        TARGET_COLUMN,
        WEIGHT_COLUMN,
        SIMPLE_SCORE_COLUMN,
        PROBABILITY_COLUMN,
    }
    feature_columns = [
        column
        for column in samples.columns
        if any(column.endswith(f"_{window}d") for window in ROLLING_WINDOWS)
        and column not in excluded_feature_columns
        and not column.startswith("future_")
        and not column.startswith("target_")
        and not column.startswith("sample_weight_")
    ]
    feature_columns = sorted(set(feature_columns))
    samples[feature_columns] = samples[feature_columns].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    samples = add_simple_score(samples)
    samples.sort_values([DATE_COLUMN, "product_vt_symbol"], inplace=True)
    samples.reset_index(drop=True, inplace=True)
    return samples, feature_columns


def _cross_section_zscore(df: pd.DataFrame, column: str) -> pd.Series:
    values = _numeric_series(df, column)
    mean = values.groupby(df[DATE_COLUMN]).transform("mean")
    std = values.groupby(df[DATE_COLUMN]).transform("std").replace(0.0, np.nan)
    return ((values - mean) / std).replace([np.inf, -np.inf], np.nan).fillna(0.0)


def add_simple_score(samples: pd.DataFrame) -> pd.DataFrame:
    result = samples.copy()
    components = {
        "pnl120": _cross_section_zscore(result, "net_pnl_sum_120d"),
        "pnl60": _cross_section_zscore(result, "net_pnl_sum_60d"),
        "sharpe60": _cross_section_zscore(result, "net_pnl_sharpe_like_60d"),
        "win60": _cross_section_zscore(result, "pnl_positive_day_mean_60d"),
        "opened60": _cross_section_zscore(result, "opened_count_sum_60d"),
        "slippage60": _cross_section_zscore(result, "slippage_sum_60d"),
        "drawdown60": _cross_section_zscore(result, "net_pnl_drawdown_60d"),
    }
    result[SIMPLE_SCORE_COLUMN] = (
        components["pnl120"]
        + 0.60 * components["pnl60"]
        + 0.60 * components["sharpe60"]
        + 0.35 * components["win60"]
        + 0.20 * components["opened60"]
        - 0.25 * components["slippage60"]
        + 0.35 * components["drawdown60"]
    )
    return result


def build_walk_forward_windows(samples: pd.DataFrame) -> list[WalkForwardWindow]:
    min_date = pd.Timestamp(samples[DATE_COLUMN].min()).normalize()
    max_date = pd.Timestamp(samples[DATE_COLUMN].max()).normalize()
    windows: list[WalkForwardWindow] = []
    train_start = min_date
    index = 1

    while train_start < max_date:
        train_end = train_start + pd.Timedelta(days=TRAIN_WINDOW_DAYS)
        test_start = train_end
        test_end = test_start + pd.Timedelta(days=TEST_WINDOW_DAYS)
        if test_start > max_date:
            break

        train_df = samples[(samples[DATE_COLUMN] >= train_start) & (samples[DATE_COLUMN] < train_end)]
        test_df = samples[(samples[DATE_COLUMN] >= test_start) & (samples[DATE_COLUMN] < test_end)]
        if (
            len(train_df) >= MIN_TRAIN_ROWS
            and len(test_df) >= MIN_TEST_ROWS
            and train_df[TARGET_COLUMN].nunique() >= 2
            and test_df[TARGET_COLUMN].nunique() >= 2
        ):
            windows.append(
                WalkForwardWindow(
                    window_id=f"wf_{index:02d}",
                    train_start=train_start,
                    train_end=train_end,
                    test_start=test_start,
                    test_end=test_end,
                )
            )
            index += 1

        train_start = train_start + pd.Timedelta(days=STEP_DAYS)
    return windows


def prepare_x(df: pd.DataFrame, feature_columns: list[str]) -> pd.DataFrame:
    return df[feature_columns].replace([np.inf, -np.inf], np.nan).fillna(0.0).astype("float64")


def train_model(train_df: pd.DataFrame, feature_columns: list[str]) -> Pipeline:
    model = Pipeline(
        steps=[
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
    model.fit(
        prepare_x(train_df, feature_columns),
        train_df[TARGET_COLUMN].astype("int64"),
        classifier__sample_weight=train_df[WEIGHT_COLUMN].astype("float64"),
    )
    return model


def score_model(model: Pipeline, df: pd.DataFrame, feature_columns: list[str]) -> np.ndarray:
    return np.asarray(model.predict_proba(prepare_x(df, feature_columns))[:, 1], dtype="float64")


def compute_binary_metrics(df: pd.DataFrame, score_column: str) -> dict[str, Any]:
    if df.empty:
        return {}
    actual = df[TARGET_COLUMN].astype("int64")
    probability = _numeric_series(df, score_column, 0.5).clip(1e-6, 1.0 - 1e-6)
    predicted = (probability >= 0.5).astype("int64")
    try:
        auc = roc_auc_score(actual, probability) if actual.nunique() >= 2 else float("nan")
    except ValueError:
        auc = float("nan")
    future_column = f"future_net_pnl_{FUTURE_HORIZON_DAYS}d"
    return {
        "rows": int(len(df)),
        "eval_months": int(df[DATE_COLUMN].nunique()),
        "products": int(df["product_vt_symbol"].nunique()),
        "positive_rate": _safe_float(actual.mean()),
        "accuracy": _safe_float(accuracy_score(actual, predicted)),
        "precision": _safe_float(precision_score(actual, predicted, zero_division=0)),
        "recall": _safe_float(recall_score(actual, predicted, zero_division=0)),
        "f1": _safe_float(f1_score(actual, predicted, zero_division=0)),
        "roc_auc": _safe_float(auc),
        "log_loss": _safe_float(log_loss(actual, probability, labels=[0, 1])),
        "brier_score": _safe_float(brier_score_loss(actual, probability)),
        "spearman_vs_future_pnl": _safe_float(df[score_column].corr(df[future_column], method="spearman")),
        "spearman_vs_future_rank": _safe_float(df[score_column].corr(df["future_rank_centered_60d"], method="spearman")),
        "mean_rank_ic_by_month": _safe_float(
            df.groupby(DATE_COLUMN).apply(
                lambda group: group[score_column].corr(group["future_rank_centered_60d"], method="spearman")
            ).replace([np.inf, -np.inf], np.nan).dropna().mean()
        ),
    }


def summarize_top_products(df: pd.DataFrame, score_column: str, label: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    future_column = f"future_net_pnl_{FUTURE_HORIZON_DAYS}d"
    for eval_date, group in df.groupby(DATE_COLUMN, sort=True):
        group = group.sort_values(score_column, ascending=False).copy()
        selected = group.head(min(TOP_N_PRODUCTS, len(group))).copy()
        rows.append(
            {
                "score_type": label,
                "eval_date": pd.Timestamp(eval_date).date().isoformat(),
                "selected_products": ",".join(selected["product_vt_symbol"].astype(str).tolist()),
                "selected_count": int(len(selected)),
                "selected_mean_future_net_pnl_60d": _safe_float(selected[future_column].mean()),
                "selected_total_future_net_pnl_60d": _safe_float(selected[future_column].sum()),
                "selected_hit_rate_positive": _safe_float((selected[future_column] > 0).mean()),
                "selected_top_half_rate": _safe_float(selected[TARGET_COLUMN].mean()),
                "selected_avg_future_rank_centered": _safe_float(selected["future_rank_centered_60d"].mean()),
                "all_mean_future_net_pnl_60d": _safe_float(group[future_column].mean()),
                "edge_vs_all_mean_future_net_pnl_60d": _safe_float(selected[future_column].mean() - group[future_column].mean()),
                "all_top_half_rate": _safe_float(group[TARGET_COLUMN].mean()),
            }
        )
    return pd.DataFrame(rows)


def summarize_top_overall(top_df: pd.DataFrame) -> dict[str, Any]:
    if top_df.empty:
        return {}
    return {
        "months": int(top_df["eval_date"].nunique()),
        "avg_selected_mean_future_net_pnl_60d": _safe_float(top_df["selected_mean_future_net_pnl_60d"].mean()),
        "avg_edge_vs_all_mean_future_net_pnl_60d": _safe_float(top_df["edge_vs_all_mean_future_net_pnl_60d"].mean()),
        "avg_selected_hit_rate_positive": _safe_float(top_df["selected_hit_rate_positive"].mean()),
        "avg_selected_top_half_rate": _safe_float(top_df["selected_top_half_rate"].mean()),
        "avg_selected_future_rank_centered": _safe_float(top_df["selected_avg_future_rank_centered"].mean()),
    }


def build_bucket_analysis(df: pd.DataFrame, score_column: str, label: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    future_column = f"future_net_pnl_{FUTURE_HORIZON_DAYS}d"
    work = df.copy()
    try:
        work["score_bucket"] = pd.qcut(work[score_column], q=5, labels=["q1", "q2", "q3", "q4", "q5"], duplicates="drop")
    except ValueError:
        return pd.DataFrame()
    return (
        work.groupby("score_bucket", observed=False)
        .agg(
            score_type=(score_column, lambda _: label),
            row_count=(score_column, "size"),
            avg_score=(score_column, "mean"),
            actual_top_half_rate=(TARGET_COLUMN, "mean"),
            avg_future_net_pnl_60d=(future_column, "mean"),
            median_future_net_pnl_60d=(future_column, "median"),
            avg_future_rank_centered=("future_rank_centered_60d", "mean"),
            product_count=("product_vt_symbol", "nunique"),
            month_count=(DATE_COLUMN, "nunique"),
        )
        .reset_index()
    )


def build_coefficients(model: Pipeline, feature_columns: list[str], window: WalkForwardWindow) -> pd.DataFrame:
    classifier: LogisticRegression = model.named_steps["classifier"]
    coef = classifier.coef_[0]
    return pd.DataFrame(
        {
            "window_id": window.window_id,
            "train_start": window.train_start.date().isoformat(),
            "train_end": window.train_end.date().isoformat(),
            "test_start": window.test_start.date().isoformat(),
            "test_end": window.test_end.date().isoformat(),
            "feature": feature_columns,
            "coefficient": coef,
            "abs_coefficient": np.abs(coef),
        }
    ).sort_values(["window_id", "abs_coefficient"], ascending=[True, False])


def run_walk_forward(samples: pd.DataFrame, feature_columns: list[str]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    windows = build_walk_forward_windows(samples)
    predictions: list[pd.DataFrame] = []
    window_metrics: list[dict[str, Any]] = []
    coefficients: list[pd.DataFrame] = []

    for window in windows:
        train_df = samples[(samples[DATE_COLUMN] >= window.train_start) & (samples[DATE_COLUMN] < window.train_end)].copy()
        test_df = samples[(samples[DATE_COLUMN] >= window.test_start) & (samples[DATE_COLUMN] < window.test_end)].copy()
        model = train_model(train_df, feature_columns)
        test_df[PROBABILITY_COLUMN] = score_model(model, test_df, feature_columns)
        test_df["window_id"] = window.window_id
        test_df["train_start"] = window.train_start.date().isoformat()
        test_df["train_end"] = window.train_end.date().isoformat()
        test_df["test_start"] = window.test_start.date().isoformat()
        test_df["test_end"] = window.test_end.date().isoformat()
        predictions.append(test_df)

        metrics = compute_binary_metrics(test_df, PROBABILITY_COLUMN)
        metrics.update(
            {
                "window_id": window.window_id,
                "train_start": window.train_start.date().isoformat(),
                "train_end": window.train_end.date().isoformat(),
                "test_start": window.test_start.date().isoformat(),
                "test_end": window.test_end.date().isoformat(),
                "train_rows": int(len(train_df)),
                "test_rows": int(len(test_df)),
            }
        )
        window_metrics.append(metrics)
        coefficients.append(build_coefficients(model, feature_columns, window))

    if predictions:
        prediction_df = pd.concat(predictions, ignore_index=True)
    else:
        prediction_df = pd.DataFrame()
    window_metric_df = pd.DataFrame(window_metrics)
    coefficient_df = pd.concat(coefficients, ignore_index=True) if coefficients else pd.DataFrame()
    return prediction_df, window_metric_df, coefficient_df


def to_markdown_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_no rows_"
    compact = df.copy()
    for column in compact.columns:
        if pd.api.types.is_float_dtype(compact[column]):
            compact[column] = compact[column].map(lambda value: f"{float(value):.4f}")
    headers = [str(column) for column in compact.columns]
    rows = compact.astype(str).to_numpy().tolist()
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def build_report(summary: dict[str, Any], bucket_df: pd.DataFrame, top_overall_df: pd.DataFrame) -> str:
    ai_metrics = summary.get("ai_prediction_metrics", {})
    simple_metrics = summary.get("simple_score_metrics_on_ai_test_period", {})
    lines = [
        "# Product Suitability Walk-Forward",
        "",
        "## Current Judgement",
        "",
        f"- Source strategy: `{SOURCE_PREFIX}`",
        f"- Target: next `{FUTURE_HORIZON_DAYS}` trading days product net contribution top half.",
        f"- AI AUC: `{ai_metrics.get('roc_auc', 0.0):.4f}`",
        f"- AI monthly rank IC: `{ai_metrics.get('mean_rank_ic_by_month', 0.0):.4f}`",
        f"- Simple score monthly rank IC: `{simple_metrics.get('mean_rank_ic_by_month', 0.0):.4f}`",
        "",
        "## Top Product Summary",
        "",
        to_markdown_table(top_overall_df),
        "",
        "## AI Buckets",
        "",
        to_markdown_table(bucket_df[bucket_df["score_type"] == "ai_probability"] if not bucket_df.empty else bucket_df),
        "",
        "## Design Boundary",
        "",
        "- This is a shadow suitability study, not a trade switch.",
        "- It evaluates product terrain for the existing trend system, not standalone price direction.",
        "- Any live use must first beat a transparent simple score and then pass formal portfolio backtests.",
    ]
    return "\n".join(lines)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    product_daily = build_product_daily()
    featured_daily = add_rolling_features(product_daily)
    samples, feature_columns = build_monthly_samples(featured_daily)
    predictions, window_metrics, coefficients = run_walk_forward(samples, feature_columns)

    if predictions.empty:
        raise RuntimeError("walk-forward produced no prediction rows")

    predictions[SIMPLE_SCORE_PERCENTILE_COLUMN] = predictions.groupby(DATE_COLUMN)[SIMPLE_SCORE_COLUMN].rank(
        method="average",
        pct=True,
    )

    prediction_columns = [
        DATE_COLUMN,
        "product_vt_symbol",
        "window_id",
        PROBABILITY_COLUMN,
        SIMPLE_SCORE_COLUMN,
        SIMPLE_SCORE_PERCENTILE_COLUMN,
        f"future_net_pnl_{FUTURE_HORIZON_DAYS}d",
        "future_rank_pct_60d",
        "future_rank_centered_60d",
        TARGET_COLUMN,
        WEIGHT_COLUMN,
    ] + feature_columns
    prediction_columns = list(dict.fromkeys(column for column in prediction_columns if column in predictions.columns))
    predictions = predictions[prediction_columns].copy()

    ai_metrics = compute_binary_metrics(predictions, PROBABILITY_COLUMN)
    simple_metrics = compute_binary_metrics(predictions, SIMPLE_SCORE_PERCENTILE_COLUMN)
    ai_top_df = summarize_top_products(predictions, PROBABILITY_COLUMN, "ai_probability")
    simple_top_df = summarize_top_products(predictions, SIMPLE_SCORE_COLUMN, "simple_score")
    top_products_df = pd.concat([ai_top_df, simple_top_df], ignore_index=True)
    top_overall = [
        {"score_type": "ai_probability", **summarize_top_overall(ai_top_df)},
        {"score_type": "simple_score", **summarize_top_overall(simple_top_df)},
    ]
    top_overall_df = pd.DataFrame(top_overall)

    bucket_df = pd.concat(
        [
            build_bucket_analysis(predictions, PROBABILITY_COLUMN, "ai_probability"),
            build_bucket_analysis(predictions, SIMPLE_SCORE_COLUMN, "simple_score"),
        ],
        ignore_index=True,
    )

    summary: dict[str, Any] = {
        "model_tag": MODEL_TAG,
        "source_prefix": SOURCE_PREFIX,
        "source_paths": {
            "position_changes": str(POSITION_CHANGES_PATH),
            "entry_snapshots": str(ENTRY_SNAPSHOTS_PATH),
        },
        "target_definition": {
            "future_horizon_days": FUTURE_HORIZON_DAYS,
            "target_column": TARGET_COLUMN,
            "target_rule": "future product net contribution ranks in top half of same monthly cross-section",
            "weight_column": WEIGHT_COLUMN,
            "weight_rule": "clip(abs(future_rank_centered_60d), 0.20, 0.60)",
        },
        "walk_forward": {
            "train_window_days": TRAIN_WINDOW_DAYS,
            "test_window_days": TEST_WINDOW_DAYS,
            "step_days": STEP_DAYS,
            "min_train_rows": MIN_TRAIN_ROWS,
            "min_test_rows": MIN_TEST_ROWS,
            "window_count": int(window_metrics["window_id"].nunique()) if not window_metrics.empty else 0,
        },
        "coverage": {
            "daily_rows": int(len(product_daily)),
            "sample_rows": int(len(samples)),
            "prediction_rows": int(len(predictions)),
            "eval_months": int(samples[DATE_COLUMN].nunique()),
            "prediction_months": int(predictions[DATE_COLUMN].nunique()),
            "products": int(samples["product_vt_symbol"].nunique()),
            "feature_count": int(len(feature_columns)),
        },
        "model": {
            "type": "logistic_regression",
            "regularization_c": LOGISTIC_C,
            "random_state": RANDOM_STATE,
        },
        "ai_prediction_metrics": ai_metrics,
        "simple_score_metrics_on_ai_test_period": {
            "score_column": SIMPLE_SCORE_PERCENTILE_COLUMN,
            **simple_metrics,
        },
        "top_product_summary": top_overall,
        "artifacts": {
            "product_daily_csv": str(PRODUCT_DAILY_OUTPUT_PATH),
            "samples_csv": str(SAMPLES_OUTPUT_PATH),
            "predictions_csv": str(PREDICTIONS_OUTPUT_PATH),
            "window_metrics_csv": str(WINDOW_METRICS_OUTPUT_PATH),
            "bucket_analysis_csv": str(BUCKET_OUTPUT_PATH),
            "top_products_csv": str(TOP_PRODUCTS_OUTPUT_PATH),
            "coefficients_csv": str(COEFFICIENT_OUTPUT_PATH),
            "summary_json": str(SUMMARY_OUTPUT_PATH),
            "report_md": str(REPORT_OUTPUT_PATH),
        },
        "design_judgement": (
            "This validates whether AI can rank product terrain for the existing trend system. "
            "It should not be connected to trading unless it beats the simple score out of sample "
            "and then improves full portfolio backtests."
        ),
    }

    product_daily.to_csv(PRODUCT_DAILY_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    samples.to_csv(SAMPLES_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    predictions.to_csv(PREDICTIONS_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    window_metrics.to_csv(WINDOW_METRICS_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    bucket_df.to_csv(BUCKET_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    top_products_df.to_csv(TOP_PRODUCTS_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    coefficients.to_csv(COEFFICIENT_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    SUMMARY_OUTPUT_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_OUTPUT_PATH.write_text(build_report(summary, bucket_df, top_overall_df), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
