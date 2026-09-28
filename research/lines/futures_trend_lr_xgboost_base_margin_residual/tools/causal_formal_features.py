"""Label-free reconstruction of the causal half of the formal AI feature panel."""

from __future__ import annotations

import math
import warnings
from typing import Iterable

import numpy as np
import pandas as pd


ROLLING_WINDOWS: tuple[int, ...] = (20, 60, 120)
FORBIDDEN_COLUMN_PREFIXES: tuple[str, ...] = (
    "future_",
    "target_",
    "sample_weight_",
)

SUM_COLUMNS: tuple[str, ...] = (
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
)

MEAN_COLUMNS: tuple[str, ...] = (
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
)

NET_PNL_FEATURE_TEMPLATES: tuple[str, ...] = (
    "net_pnl_mean_{window}d",
    "net_pnl_std_{window}d",
    "net_pnl_sharpe_like_{window}d",
    "net_pnl_min_day_{window}d",
    "net_pnl_max_day_{window}d",
    "net_pnl_drawdown_{window}d",
)


def formal_feature_columns() -> list[str]:
    columns: list[str] = []
    for window in ROLLING_WINDOWS:
        columns.extend(f"{column}_sum_{window}d" for column in SUM_COLUMNS)
        columns.extend(f"{column}_mean_{window}d" for column in MEAN_COLUMNS)
        columns.extend(template.format(window=window) for template in NET_PNL_FEATURE_TEMPLATES)
    return sorted(columns)


def _assert_no_forbidden_columns(columns: Iterable[str]) -> None:
    forbidden = [
        str(column)
        for column in columns
        if str(column).startswith(FORBIDDEN_COLUMN_PREFIXES)
    ]
    if forbidden:
        raise ValueError(f"forbidden_label_columns:{','.join(sorted(forbidden))}")


def _rolling_drawdown(values: pd.Series, window: int) -> pd.Series:
    cumulative = values.cumsum()

    def drawdown(window_values: np.ndarray) -> float:
        high_water = np.maximum.accumulate(window_values)
        return float(np.min(window_values - high_water))

    return cumulative.rolling(
        window,
        min_periods=max(10, window // 2),
    ).apply(drawdown, raw=True)


def build_causal_rolling_features(daily: pd.DataFrame) -> pd.DataFrame:
    """Reproduce the formal 108 rolling features without computing future values."""

    warnings.simplefilter("ignore", category=pd.errors.PerformanceWarning)
    _assert_no_forbidden_columns(daily.columns)
    required = {
        "date",
        "product_vt_symbol",
        *SUM_COLUMNS,
        *(column for column in MEAN_COLUMNS if column not in {
            "pnl_positive_day",
            "trade_day",
            "candidate_day",
            "opened_day",
        }),
    }
    missing = sorted(required - set(daily.columns))
    if missing:
        raise ValueError(f"missing_daily_columns:{','.join(missing)}")

    result = daily.copy()
    result["date"] = pd.to_datetime(result["date"]).dt.normalize()
    result["pnl_positive_day"] = (result["net_pnl"] > 0).astype("float64")
    result["trade_day"] = (result["trade_count"] > 0).astype("float64")
    result["candidate_day"] = (result["candidate_count"] > 0).astype("float64")
    result["opened_day"] = (result["opened_count"] > 0).astype("float64")

    frames: list[pd.DataFrame] = []
    for _, group in result.groupby("product_vt_symbol", sort=False):
        group = group.sort_values("date").copy()
        for window in ROLLING_WINDOWS:
            rolling = group.rolling(
                window=window,
                min_periods=max(10, window // 2),
            )
            for column in SUM_COLUMNS:
                group[f"{column}_sum_{window}d"] = rolling[column].sum()
            for column in MEAN_COLUMNS:
                group[f"{column}_mean_{window}d"] = rolling[column].mean()
            group[f"net_pnl_mean_{window}d"] = rolling["net_pnl"].mean()
            group[f"net_pnl_std_{window}d"] = rolling["net_pnl"].std()
            group[f"net_pnl_sharpe_like_{window}d"] = (
                group[f"net_pnl_mean_{window}d"]
                / group[f"net_pnl_std_{window}d"].replace(0.0, np.nan)
            ) * math.sqrt(window)
            group[f"net_pnl_min_day_{window}d"] = rolling["net_pnl"].min()
            group[f"net_pnl_max_day_{window}d"] = rolling["net_pnl"].max()
            group[f"net_pnl_drawdown_{window}d"] = _rolling_drawdown(
                group["net_pnl"],
                window,
            )
        frames.append(group)

    featured = pd.concat(frames, ignore_index=True)
    feature_columns = formal_feature_columns()
    featured[feature_columns] = (
        featured[feature_columns]
        .replace([np.inf, -np.inf], np.nan)
        .fillna(0.0)
    )
    featured.sort_values(["product_vt_symbol", "date"], inplace=True)
    featured.reset_index(drop=True, inplace=True)
    _assert_no_forbidden_columns(featured.columns)
    return featured


def build_label_free_monthly_samples(
    featured_daily: pd.DataFrame,
    *,
    minimum_cross_section: int = 1,
) -> tuple[pd.DataFrame, list[str]]:
    """Select month-end feature rows without constructing or reading labels."""

    _assert_no_forbidden_columns(featured_daily.columns)
    daily = featured_daily.copy()
    daily["date"] = pd.to_datetime(daily["date"]).dt.normalize()
    daily["month"] = daily["date"].dt.to_period("M")
    eval_dates = daily.groupby("month")["date"].max().sort_values()
    samples = daily[daily["date"].isin(eval_dates)].copy()
    samples.rename(columns={"date": "eval_date"}, inplace=True)
    samples["cross_section_count"] = samples.groupby("eval_date")[
        "product_vt_symbol"
    ].transform("size")
    samples = samples[
        samples["cross_section_count"] >= int(minimum_cross_section)
    ].copy()

    feature_columns = formal_feature_columns()
    missing = sorted(set(feature_columns) - set(samples.columns))
    if missing:
        raise ValueError(f"missing_formal_features:{','.join(missing)}")
    samples[feature_columns] = (
        samples[feature_columns]
        .replace([np.inf, -np.inf], np.nan)
        .fillna(0.0)
        .astype("float64")
    )
    samples.sort_values(["eval_date", "product_vt_symbol"], inplace=True)
    samples.reset_index(drop=True, inplace=True)
    _assert_no_forbidden_columns(samples.columns)
    return samples, feature_columns


def build_label_end_calendar(
    trading_dates: Iterable[pd.Timestamp],
    eval_dates: Iterable[pd.Timestamp],
    *,
    horizon: int = 60,
) -> pd.DataFrame:
    """Map each evaluation date to the last date in its future trading-day label path."""

    if horizon <= 0:
        raise ValueError("horizon_must_be_positive")
    dates = pd.DatetimeIndex(pd.to_datetime(list(trading_dates))).normalize().unique().sort_values()
    positions = {pd.Timestamp(date): index for index, date in enumerate(dates)}
    rows: list[dict[str, object]] = []
    for raw_eval_date in sorted(pd.to_datetime(list(eval_dates)).normalize().unique()):
        eval_date = pd.Timestamp(raw_eval_date)
        if eval_date not in positions:
            raise ValueError(f"eval_date_not_in_trading_calendar:{eval_date.date().isoformat()}")
        end_index = positions[eval_date] + int(horizon)
        label_end = dates[end_index] if end_index < len(dates) else pd.NaT
        rows.append(
            {
                "eval_date": eval_date,
                "label_end": label_end,
                "horizon_trading_days": int(horizon),
                "label_value_read": False,
            }
        )
    return pd.DataFrame(rows)


def build_pit_fold_plan(
    label_calendar: pd.DataFrame,
    *,
    minimum_train_months: int = 24,
) -> pd.DataFrame:
    """Build expanding monthly folds using only value-free label maturity dates."""

    required = {"eval_date", "label_end"}
    missing = sorted(required - set(label_calendar.columns))
    if missing:
        raise ValueError(f"missing_label_calendar_columns:{','.join(missing)}")
    frame = label_calendar[list(required)].copy()
    frame["eval_date"] = pd.to_datetime(frame["eval_date"]).dt.normalize()
    frame["label_end"] = pd.to_datetime(frame["label_end"]).dt.normalize()

    for eval_date, group in frame.groupby("eval_date", sort=True):
        values = group["label_end"].drop_duplicates()
        if len(values) != 1:
            raise ValueError(
                f"inconsistent_label_end:{pd.Timestamp(eval_date).date().isoformat()}"
            )
    frame = frame.drop_duplicates("eval_date").sort_values("eval_date").reset_index(drop=True)

    rows: list[dict[str, object]] = []
    for test_date in pd.DatetimeIndex(frame["eval_date"]):
        prior = frame[frame["eval_date"] < test_date].copy()
        eligible = prior[
            prior["label_end"].notna() & (prior["label_end"] <= test_date)
        ].copy()
        if len(eligible) < int(minimum_train_months):
            continue
        violation_rows = int(
            (eligible["label_end"].isna() | (eligible["label_end"] > test_date)).sum()
        )
        test_label_end = frame.loc[
            frame["eval_date"].eq(test_date),
            "label_end",
        ].iloc[0]
        rows.append(
            {
                "fold_id": f"pit_{len(rows) + 1:03d}",
                "test_eval_date": pd.Timestamp(test_date),
                "test_label_end": test_label_end,
                "effect_evaluable": bool(pd.notna(test_label_end)),
                "train_months": int(len(eligible)),
                "train_start": pd.Timestamp(eligible["eval_date"].min()),
                "train_end": pd.Timestamp(eligible["eval_date"].max()),
                "train_label_end_max": pd.Timestamp(eligible["label_end"].max()),
                "purged_prior_months": int(len(prior) - len(eligible)),
                "train_eval_dates": ",".join(
                    pd.Timestamp(value).date().isoformat()
                    for value in eligible["eval_date"]
                ),
                "pit_violation_rows": violation_rows,
            }
        )
    return pd.DataFrame(rows)
