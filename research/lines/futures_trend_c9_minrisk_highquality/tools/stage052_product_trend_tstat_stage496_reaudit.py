from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage052"
MODEL_TAG = "stage052_product_trend_tstat_stage496_reaudit_v1"
OUTPUT_PREFIX = "qmt_roll_stage052_c9_minrisk_product_trend_tstat_stage496_reaudit"

OFFICIAL_ARM = "A_official_stage847_c9_15w"
INITIAL_CAPITAL = 150_000.0
TREND_WINDOW = 252
TREND_MIN_PERIODS = 126
TREND_TSTAT_CUTOFF = 2.0
MAX_SIGNAL_AGE_DAYS = 7
TARGET_COHORT = "no_significant_aligned_trend"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
if str(EXAMPLE_DIR) not in sys.path:
    sys.path.insert(0, str(EXAMPLE_DIR))

from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage052_product_trend_tstat_stage496_reaudit"
BACKTEST_OUTPUT_DIR = EXAMPLE_DIR / "backtest_outputs"

STAGE049_DIR = LINE_DIR / "outputs" / "stage049_product_trend_tstat_preentry_audit"
STAGE046_DIR = LINE_DIR / "outputs" / "stage046_entry_day_confirmed_breakeven_true_engine"

FEATURES_IN = (
    STAGE049_DIR
    / "qmt_roll_stage049_c9_minrisk_product_trend_tstat_preentry_audit_features_"
    "stage049_product_trend_tstat_preentry_audit_v1.csv"
)
OFFICIAL_CURVE_IN = (
    STAGE046_DIR
    / "qmt_roll_stage046_c9_minrisk_entry_day_confirmed_breakeven_true_engine_curve_"
    "stage046_entry_day_confirmed_breakeven_true_engine_v1.csv"
)
STAGE496_SYNTHETIC_IN = (
    BACKTEST_OUTPUT_DIR
    / "qmt_roll_stage496_all_required_preclose_full_bar_after_all_backfill_synthetic_"
    "stage496_all_required_preclose_full_bar_after_all_backfill_v1.csv"
)
STAGE496_SUMMARY_IN = (
    BACKTEST_OUTPUT_DIR
    / "qmt_roll_stage496_all_required_preclose_full_bar_after_all_backfill_summary_"
    "stage496_all_required_preclose_full_bar_after_all_backfill_v1.csv"
)

PRODUCT_TREND_DAILY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_trend_daily_{MODEL_TAG}.csv"
FEATURES_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_features_{MODEL_TAG}.csv"
COHORT_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cohort_summary_{MODEL_TAG}.csv"
BUCKET_YEAR_MATRIX_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_year_matrix_{MODEL_TAG}.csv"
PRODUCT_BUCKET_MATRIX_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_bucket_matrix_{MODEL_TAG}.csv"
COVERAGE_BY_YEAR_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_coverage_by_year_{MODEL_TAG}.csv"
COVERAGE_BY_PRODUCT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_coverage_by_product_{MODEL_TAG}.csv"
TARGET_LOTS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_target_lots_{MODEL_TAG}.csv"
UPPER_BOUND_CURVE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_upper_bound_curve_{MODEL_TAG}.csv"
LEAVE_ONE_YEAR_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_leave_one_year_{MODEL_TAG}.csv"
LEAVE_ONE_PRODUCT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_leave_one_product_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_upper_bound_path_chart_{MODEL_TAG}.png"
CONTRIBUTION_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cohort_contribution_chart_{MODEL_TAG}.png"
COVERAGE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_coverage_improvement_chart_{MODEL_TAG}.png"
BUCKET_YEAR_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_year_heatmap_{MODEL_TAG}.png"
PRODUCT_BUCKET_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_bucket_heatmap_{MODEL_TAG}.png"
SCATTER_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trend_tstat_scatter_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        if np.isnan(value) or np.isinf(value):
            return None
        return float(value)
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig", **kwargs)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    display = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    for column in display.columns:
        if pd.api.types.is_float_dtype(display[column]):
            display[column] = display[column].map(lambda value: "" if pd.isna(value) else f"{value:.4f}")
    lines = [
        "| " + " | ".join(str(column) for column in display.columns) + " |",
        "| " + " | ".join(["---"] * len(display.columns)) + " |",
    ]
    for _, row in display.iterrows():
        lines.append("| " + " | ".join(str(row[column]) for column in display.columns) + " |")
    return "\n".join(lines)


def _fmt(value: Any, digits: int = 4) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "NA"
    if not np.isfinite(number):
        return "NA"
    return f"{number:.{digits}f}"


def _trend_stats(values: np.ndarray) -> tuple[float, float, float, float]:
    y = np.asarray(values, dtype=float)
    y = y[np.isfinite(y)]
    n = len(y)
    if n < TREND_MIN_PERIODS:
        return np.nan, np.nan, np.nan, np.nan
    x = np.arange(n, dtype=float)
    x_centered = x - x.mean()
    y_centered = y - y.mean()
    ssx = float(np.dot(x_centered, x_centered))
    if ssx <= 0:
        return np.nan, np.nan, np.nan, np.nan
    beta = float(np.dot(x_centered, y_centered) / ssx)
    alpha = float(y.mean() - beta * x.mean())
    fitted = alpha + beta * x
    residual = y - fitted
    rss = float(np.dot(residual, residual))
    tss = float(np.dot(y_centered, y_centered))
    if n <= 2 or rss <= 0:
        tstat = np.nan
    else:
        sigma2 = rss / (n - 2)
        se_beta = np.sqrt(sigma2 / ssx)
        tstat = float(beta / se_beta) if se_beta > 0 else np.nan
    r2 = float(1.0 - rss / tss) if tss > 0 else np.nan
    annualized_log_slope = float(beta * 252.0)
    total_log_return = float(y[-1] - y[0])
    return tstat, r2, annualized_log_slope, total_log_return


def _load_stage496_summary() -> dict[str, Any]:
    if not STAGE496_SUMMARY_IN.exists():
        return {}
    frame = _read_csv(STAGE496_SUMMARY_IN)
    if frame.empty:
        return {}
    return {str(column): _json_safe(frame.iloc[0][column]) for column in frame.columns}


def _build_product_trend_daily() -> pd.DataFrame:
    columns = [
        "date",
        "product_vt_symbol",
        "vt_symbol",
        "exchange",
        "full_bar_ready",
        "valid_ohlc",
        "strict_full_preclose_ready",
        "synthetic_close",
        "synthetic_volume",
        "synthetic_open_interest",
        "preclose_bar_count",
        "fill_bar_count",
    ]
    bars = _read_csv(STAGE496_SYNTHETIC_IN, usecols=lambda column: column in columns)
    bars["date"] = pd.to_datetime(bars["date"], errors="coerce")
    for column in [
        "full_bar_ready",
        "valid_ohlc",
        "strict_full_preclose_ready",
        "synthetic_close",
        "synthetic_volume",
        "synthetic_open_interest",
        "preclose_bar_count",
        "fill_bar_count",
    ]:
        bars[column] = pd.to_numeric(bars.get(column, np.nan), errors="coerce")
    bars["product_key"] = bars["product_vt_symbol"].fillna("").astype(str)
    bars = bars[
        bars["date"].notna()
        & bars["product_key"].ne("")
        & bars["strict_full_preclose_ready"].fillna(0.0).gt(0.0)
        & bars["synthetic_close"].notna()
        & bars["synthetic_close"].gt(0.0)
    ].copy()
    bars = bars.sort_values(
        ["product_key", "date", "synthetic_volume", "synthetic_open_interest"],
        ascending=[True, True, False, False],
    )
    bars = bars.drop_duplicates(["product_key", "date"], keep="first")

    rows: list[pd.DataFrame] = []
    for product, group in bars.groupby("product_key", sort=True):
        item = group.sort_values("date").copy()
        log_close = np.log(item["synthetic_close"].astype(float))
        item["trend_tstat_252_stage052"] = log_close.rolling(
            TREND_WINDOW,
            min_periods=TREND_MIN_PERIODS,
        ).apply(lambda values: _trend_stats(values)[0], raw=True)
        item["trend_r2_252_stage052"] = log_close.rolling(
            TREND_WINDOW,
            min_periods=TREND_MIN_PERIODS,
        ).apply(lambda values: _trend_stats(values)[1], raw=True)
        item["trend_annualized_log_slope_252_stage052"] = log_close.rolling(
            TREND_WINDOW,
            min_periods=TREND_MIN_PERIODS,
        ).apply(lambda values: _trend_stats(values)[2], raw=True)
        item["trend_total_log_return_252_stage052"] = log_close.rolling(
            TREND_WINDOW,
            min_periods=TREND_MIN_PERIODS,
        ).apply(lambda values: _trend_stats(values)[3], raw=True)
        item["trend_ready_stage052_daily"] = item["trend_tstat_252_stage052"].notna()
        rows.append(
            item[
                [
                    "date",
                    "product_key",
                    "vt_symbol",
                    "exchange",
                    "synthetic_close",
                    "synthetic_volume",
                    "synthetic_open_interest",
                    "preclose_bar_count",
                    "fill_bar_count",
                    "trend_tstat_252_stage052",
                    "trend_r2_252_stage052",
                    "trend_annualized_log_slope_252_stage052",
                    "trend_total_log_return_252_stage052",
                    "trend_ready_stage052_daily",
                ]
            ].copy()
        )
    return pd.concat(rows, ignore_index=True).sort_values(["product_key", "date"]).reset_index(drop=True)


def _load_features(trend_daily: pd.DataFrame) -> pd.DataFrame:
    features = _read_csv(FEATURES_IN)
    required = {
        "lot_id",
        "vt_symbol",
        "normalized_product",
        "direction",
        "entry_date",
        "prev_state_date",
        "exit_date",
        "realized_pnl",
        "trend_ready_stage049",
    }
    missing = required - set(features.columns)
    if missing:
        raise RuntimeError(f"Stage049 features missing columns: {sorted(missing)}")
    features = features.copy()
    features["entry_date"] = pd.to_datetime(features["entry_date"], errors="coerce")
    features["prev_state_date"] = pd.to_datetime(features["prev_state_date"], errors="coerce")
    features["exit_date"] = pd.to_datetime(features["exit_date"], errors="coerce")
    features["exit_day"] = features["exit_date"].dt.normalize()
    features["entry_year"] = features["entry_date"].dt.year.astype("Int64")
    features["exit_year"] = features["exit_date"].dt.year.astype("Int64")
    features["prev_state_year"] = features["prev_state_date"].dt.year.astype("Int64")
    features["realized_pnl"] = pd.to_numeric(features["realized_pnl"], errors="coerce").fillna(0.0)
    features["stage049_ready_bool"] = features["trend_ready_stage049"].fillna(False).astype(bool)

    trend_columns = [
        "date",
        "product_key",
        "trend_tstat_252_stage052",
        "trend_r2_252_stage052",
        "trend_annualized_log_slope_252_stage052",
        "trend_total_log_return_252_stage052",
    ]
    merged_parts: list[pd.DataFrame] = []
    for product, group in features.groupby("normalized_product", sort=False):
        daily = trend_daily[trend_daily["product_key"].eq(product)][trend_columns].sort_values("date")
        item = group.sort_values("prev_state_date").copy()
        if daily.empty:
            for column in trend_columns:
                if column not in {"date", "product_key"}:
                    item[column] = np.nan
            item["stage052_source_date"] = pd.NaT
            item["stage052_signal_age_days"] = np.nan
        else:
            item = pd.merge_asof(
                item,
                daily,
                left_on="prev_state_date",
                right_on="date",
                direction="backward",
            )
            item = item.rename(columns={"date": "stage052_source_date"})
            item = item.drop(columns=[column for column in ["product_key_y"] if column in item.columns])
            if "product_key_x" in item.columns:
                item = item.rename(columns={"product_key_x": "product_key"})
            item["stage052_signal_age_days"] = (
                item["prev_state_date"].dt.normalize() - item["stage052_source_date"].dt.normalize()
            ).dt.days
        merged_parts.append(item)
    merged = pd.concat(merged_parts, ignore_index=True)
    merged["trend_ready_stage052"] = (
        merged["trend_tstat_252_stage052"].notna()
        & merged["stage052_signal_age_days"].ge(0)
        & merged["stage052_signal_age_days"].le(MAX_SIGNAL_AGE_DAYS)
    )
    direction_sign = merged["direction"].map({"long": 1.0, "short": -1.0}).fillna(0.0)
    merged["direction_aligned_trend_tstat_252_stage052"] = merged["trend_tstat_252_stage052"] * direction_sign
    merged["direction_aligned_total_log_return_252_stage052"] = (
        merged["trend_total_log_return_252_stage052"] * direction_sign
    )
    merged["direction_aligned_slope_252_stage052"] = (
        merged["trend_annualized_log_slope_252_stage052"] * direction_sign
    )
    merged["stage052_trend_bucket"] = "trend_missing"
    ready = merged["trend_ready_stage052"]
    aligned = merged["direction_aligned_trend_tstat_252_stage052"]
    merged.loc[ready & aligned.ge(TREND_TSTAT_CUTOFF), "stage052_trend_bucket"] = "aligned_significant_ge2"
    merged.loc[ready & aligned.ge(0.0) & aligned.lt(TREND_TSTAT_CUTOFF), "stage052_trend_bucket"] = (
        "aligned_weak_0_2"
    )
    merged.loc[ready & aligned.lt(0.0) & aligned.gt(-TREND_TSTAT_CUTOFF), "stage052_trend_bucket"] = (
        "opposite_weak_neg2_0"
    )
    merged.loc[ready & aligned.le(-TREND_TSTAT_CUTOFF), "stage052_trend_bucket"] = (
        "opposite_significant_le_neg2"
    )
    merged["stage052_no_significant_aligned_trend"] = ready & aligned.lt(TREND_TSTAT_CUTOFF)
    return merged.sort_values(["entry_date", "lot_id"]).reset_index(drop=True)


def _load_official_curve() -> pd.DataFrame:
    curve = _read_csv(OFFICIAL_CURVE_IN)
    curve = curve[curve["arm"].eq(OFFICIAL_ARM)].copy()
    if curve.empty:
        raise RuntimeError(f"official curve arm is empty: {OFFICIAL_ARM}")
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce")
    return curve.sort_values("date").reset_index(drop=True)


def _equity_metrics(equity: pd.Series, date: pd.Series | None = None) -> dict[str, float | str]:
    equity = equity.astype(float).reset_index(drop=True)
    running_max = equity.cummax()
    drawdown_pct = (equity / running_max - 1.0) * 100.0
    returns = equity.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    ret_std = returns.std(ddof=0)
    sharpe = float(returns.mean() / ret_std * np.sqrt(252.0)) if ret_std and ret_std > 0 else np.nan
    trough_idx = int(drawdown_pct.idxmin())
    metrics: dict[str, float | str] = {
        "end_equity": float(equity.iloc[-1]),
        "total_return_pct": float((equity.iloc[-1] / INITIAL_CAPITAL - 1.0) * 100.0),
        "max_dd_pct": float(drawdown_pct.min()),
        "sharpe": sharpe,
    }
    if date is not None:
        dates = pd.to_datetime(date).reset_index(drop=True)
        metrics["max_dd_date"] = dates.iloc[trough_idx].strftime("%Y-%m-%d")
    return metrics


def _official_metrics(curve: pd.DataFrame) -> dict[str, float | str]:
    metrics = _equity_metrics(curve["account_equity"], curve["date"])
    nonzero = curve[curve["net_pnl"].ne(0)]
    metrics.update(
        {
            "total_slippage": float(curve["slippage"].sum()),
            "total_trade_count": float(curve["trade_count"].sum()),
            "win_rate_pct": float((nonzero["net_pnl"] > 0).mean() * 100.0) if len(nonzero) else np.nan,
            "max_broker10_margin_to_equity_pct": float(curve["broker10_margin_to_equity_pct"].max()),
            "days_over_100pct": float((curve["broker10_margin_to_equity_pct"] > 100.0).sum()),
        }
    )
    return metrics


def _summary_for_group(features: pd.DataFrame, bucket: str, group: pd.DataFrame) -> dict[str, Any]:
    total_positive = float(features["realized_pnl"].clip(lower=0).sum())
    total_negative_abs = float((-features["realized_pnl"].clip(upper=0)).sum())
    positive = float(group["realized_pnl"].clip(lower=0).sum())
    negative_abs = float((-group["realized_pnl"].clip(upper=0)).sum())
    yearly = group.groupby("exit_year")["realized_pnl"].sum().dropna()
    return {
        "bucket": bucket,
        "lot_count": int(len(group)),
        "product_count": int(group["normalized_product"].nunique()) if len(group) else 0,
        "year_count": int(group["exit_year"].nunique()) if len(group) else 0,
        "net_pnl": float(group["realized_pnl"].sum()),
        "positive_pnl": positive,
        "negative_pnl_abs": negative_abs,
        "positive_coverage_pct": positive / total_positive * 100.0 if total_positive else np.nan,
        "negative_coverage_pct": negative_abs / total_negative_abs * 100.0 if total_negative_abs else np.nan,
        "positive_year_count": int((yearly > 0.0).sum()),
        "negative_year_count": int((yearly < 0.0).sum()),
        "mean_aligned_tstat": float(group["direction_aligned_trend_tstat_252_stage052"].mean())
        if len(group)
        else np.nan,
        "mean_trend_r2": float(group["trend_r2_252_stage052"].mean()) if len(group) else np.nan,
        "mean_aligned_annualized_slope": float(group["direction_aligned_slope_252_stage052"].mean())
        if len(group)
        else np.nan,
    }


def _cohort_summary(features: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for bucket, group in features.groupby("stage052_trend_bucket", dropna=False):
        rows.append(_summary_for_group(features, str(bucket), group.copy()))
    target = features[features["stage052_no_significant_aligned_trend"]].copy()
    rows.append(_summary_for_group(features, TARGET_COHORT, target))
    rows.append(_summary_for_group(features, "trend_ready_all", features[features["trend_ready_stage052"]].copy()))
    rows.append(_summary_for_group(features, "all_lots", features.copy()))
    return pd.DataFrame(rows).sort_values("bucket").reset_index(drop=True)


def _build_upper_bound_curve(curve: pd.DataFrame, target: pd.DataFrame) -> pd.DataFrame:
    cashflow = (
        target.dropna(subset=["exit_day"])
        .groupby("exit_day", as_index=False)
        .agg(target_realized_pnl=("realized_pnl", "sum"), target_lot_count=("realized_pnl", "size"))
        .rename(columns={"exit_day": "date"})
    )
    upper = curve[
        ["date", "account_equity", "drawdown_pct", "nav", "broker10_margin_to_equity_pct"]
    ].copy()
    upper = upper.merge(cashflow, on="date", how="left")
    upper["target_realized_pnl"] = upper["target_realized_pnl"].fillna(0.0)
    upper["target_lot_count"] = upper["target_lot_count"].fillna(0).astype(int)
    upper["skipped_target_pnl_cumsum"] = upper["target_realized_pnl"].cumsum()
    upper["upper_bound_skip_target_equity"] = upper["account_equity"] - upper["skipped_target_pnl_cumsum"]
    upper["upper_bound_nav"] = upper["upper_bound_skip_target_equity"] / INITIAL_CAPITAL
    upper["official_drawdown_pct_recalc"] = (
        upper["account_equity"] / upper["account_equity"].cummax() - 1.0
    ) * 100.0
    upper["upper_bound_drawdown_pct"] = (
        upper["upper_bound_skip_target_equity"] / upper["upper_bound_skip_target_equity"].cummax() - 1.0
    ) * 100.0
    return upper


def _leave_one(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    total_pnl = float(frame["realized_pnl"].sum())
    total_count = int(len(frame))
    grouped = (
        frame.groupby(column, dropna=False)
        .agg(removed_count=("realized_pnl", "size"), removed_pnl=("realized_pnl", "sum"))
        .reset_index()
        .rename(columns={column: "removed_key"})
    )
    grouped["remaining_count"] = total_count - grouped["removed_count"]
    grouped["remaining_pnl"] = total_pnl - grouped["removed_pnl"]
    grouped["remaining_negative"] = grouped["remaining_pnl"] < 0
    return grouped.sort_values("remaining_pnl").reset_index(drop=True)


def _coverage_tables(features: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    by_year = (
        features.groupby("prev_state_year", dropna=False)
        .agg(
            lot_count=("lot_id", "size"),
            stage049_ready_lots=("stage049_ready_bool", "sum"),
            stage052_ready_lots=("trend_ready_stage052", "sum"),
            net_pnl=("realized_pnl", "sum"),
            stage052_missing_pnl=(
                "realized_pnl",
                lambda values: float(
                    values[~features.loc[values.index, "trend_ready_stage052"].astype(bool)].sum()
                ),
            ),
        )
        .reset_index()
    )
    by_year["stage049_ready_pct"] = by_year["stage049_ready_lots"] / by_year["lot_count"] * 100.0
    by_year["stage052_ready_pct"] = by_year["stage052_ready_lots"] / by_year["lot_count"] * 100.0

    by_product = (
        features.groupby("normalized_product", dropna=False)
        .agg(
            lot_count=("lot_id", "size"),
            stage049_ready_lots=("stage049_ready_bool", "sum"),
            stage052_ready_lots=("trend_ready_stage052", "sum"),
            net_pnl=("realized_pnl", "sum"),
            stage052_missing_pnl=(
                "realized_pnl",
                lambda values: float(
                    values[~features.loc[values.index, "trend_ready_stage052"].astype(bool)].sum()
                ),
            ),
        )
        .reset_index()
    )
    by_product["stage049_ready_pct"] = by_product["stage049_ready_lots"] / by_product["lot_count"] * 100.0
    by_product["stage052_ready_pct"] = by_product["stage052_ready_lots"] / by_product["lot_count"] * 100.0
    by_product = by_product.sort_values(["stage052_missing_pnl", "lot_count"]).reset_index(drop=True)
    return by_year, by_product


def _cumulative_bucket_series(features: pd.DataFrame, curve: pd.DataFrame, bucket: str) -> np.ndarray:
    group = features[features["stage052_trend_bucket"].eq(bucket)].dropna(subset=["exit_day"])
    by_day = group.groupby("exit_day")["realized_pnl"].sum()
    index = pd.DatetimeIndex(curve["date"].dt.normalize())
    return by_day.reindex(index, fill_value=0.0).cumsum().to_numpy(dtype=float)


def _write_charts(
    features: pd.DataFrame,
    curve: pd.DataFrame,
    upper_curve: pd.DataFrame,
    bucket_year: pd.DataFrame,
    product_bucket: pd.DataFrame,
    coverage_by_year: pd.DataFrame,
) -> None:
    plt.rcParams.update({"figure.dpi": 130, "font.size": 9})

    fig, axes = plt.subplots(3, 1, figsize=(12, 11), sharex=True)
    axes[0].plot(upper_curve["date"], upper_curve["account_equity"], label="official equity", linewidth=1.4)
    axes[0].plot(
        upper_curve["date"],
        upper_curve["upper_bound_skip_target_equity"],
        label="upper bound: skip no-significant-aligned-trend lots",
        linewidth=1.4,
    )
    axes[0].set_yscale("log")
    axes[0].set_ylabel("equity log")
    axes[0].legend(loc="upper left")
    axes[0].grid(True, alpha=0.25)
    axes[1].plot(upper_curve["date"], upper_curve["official_drawdown_pct_recalc"], label="official DD")
    axes[1].plot(upper_curve["date"], upper_curve["upper_bound_drawdown_pct"], label="upper-bound DD")
    axes[1].set_ylabel("drawdown %")
    axes[1].legend(loc="lower left")
    axes[1].grid(True, alpha=0.25)
    axes[2].plot(
        upper_curve["date"],
        -upper_curve["skipped_target_pnl_cumsum"],
        color="#7f3b08",
        label="equity impact from skipping target",
    )
    axes[2].bar(upper_curve["date"], -upper_curve["target_realized_pnl"], color="#d95f0e", alpha=0.25)
    axes[2].set_ylabel("cashflow impact")
    axes[2].legend(loc="upper left")
    axes[2].grid(True, alpha=0.25)
    fig.suptitle("Stage052 fixed t-stat target upper-bound path")
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT)
    plt.close(fig)

    fig, axes = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    axes[0].plot(curve["date"], curve["account_equity"], color="#2563eb", linewidth=1.3, label="official equity")
    axes[0].set_yscale("log")
    axes[0].set_ylabel("equity log")
    axes[0].legend(loc="upper left")
    axes[0].grid(True, alpha=0.25)
    for bucket in [
        "aligned_significant_ge2",
        "aligned_weak_0_2",
        "opposite_weak_neg2_0",
        "opposite_significant_le_neg2",
        "trend_missing",
    ]:
        axes[1].plot(curve["date"], _cumulative_bucket_series(features, curve, bucket), linewidth=1.1, label=bucket)
    axes[1].axhline(0.0, color="black", linewidth=0.8)
    axes[1].set_ylabel("closed-lot cumulative pnl")
    axes[1].legend(loc="upper left", ncol=2, fontsize=8)
    axes[1].grid(True, alpha=0.25)
    fig.suptitle("Stage052 trend-tstat bucket contribution")
    fig.tight_layout()
    fig.savefig(CONTRIBUTION_CHART_OUT)
    plt.close(fig)

    fig, ax1 = plt.subplots(figsize=(12, 6))
    x = np.arange(len(coverage_by_year))
    width = 0.36
    ax1.bar(
        x - width / 2,
        coverage_by_year["stage049_ready_pct"],
        width=width,
        label="Stage049 ready %",
        color="#9ecae1",
    )
    ax1.bar(
        x + width / 2,
        coverage_by_year["stage052_ready_pct"],
        width=width,
        label="Stage052 ready %",
        color="#3182bd",
    )
    ax1.set_xticks(x)
    ax1.set_xticklabels(coverage_by_year["prev_state_year"].astype(str), rotation=45, ha="right")
    ax1.set_ylabel("ready %")
    ax1.set_ylim(0, 105)
    ax1.legend(loc="upper left")
    ax1.grid(True, axis="y", alpha=0.25)
    ax2 = ax1.twinx()
    ax2.plot(x, coverage_by_year["stage052_missing_pnl"], color="#d94801", marker="o", label="Stage052 missing pnl")
    ax2.axhline(0.0, color="black", linewidth=0.8)
    ax2.set_ylabel("missing net pnl")
    ax2.legend(loc="upper right")
    fig.suptitle("Stage052 preclose trend coverage improvement by year")
    fig.tight_layout()
    fig.savefig(COVERAGE_CHART_OUT)
    plt.close(fig)

    matrix = bucket_year.pivot_table(
        index="stage052_trend_bucket",
        columns="exit_year",
        values="realized_pnl",
        aggfunc="sum",
        fill_value=0.0,
    )
    matrix = matrix.reindex(matrix.sum(axis=1).abs().sort_values(ascending=False).index)
    values = matrix.to_numpy(dtype=float)
    vmax = max(float(np.nanmax(np.abs(values))), 1.0)
    fig, ax = plt.subplots(figsize=(12, max(4, 0.5 * len(matrix))))
    image = ax.imshow(values, aspect="auto", cmap="RdYlGn", vmin=-vmax, vmax=vmax)
    ax.set_xticks(np.arange(len(matrix.columns)))
    ax.set_xticklabels([str(col) for col in matrix.columns], rotation=45, ha="right")
    ax.set_yticks(np.arange(len(matrix.index)))
    ax.set_yticklabels(matrix.index)
    ax.set_title("Stage052 trend bucket-year realized PnL")
    fig.colorbar(image, ax=ax, shrink=0.8, label="PnL")
    fig.tight_layout()
    fig.savefig(BUCKET_YEAR_HEATMAP_OUT)
    plt.close(fig)

    prod_matrix = product_bucket.pivot_table(
        index="normalized_product",
        columns="stage052_trend_bucket",
        values="realized_pnl",
        aggfunc="sum",
        fill_value=0.0,
    )
    prod_matrix = prod_matrix.reindex(prod_matrix.sum(axis=1).abs().sort_values(ascending=False).index[:30])
    values = prod_matrix.to_numpy(dtype=float)
    vmax = max(float(np.nanmax(np.abs(values))), 1.0)
    fig, ax = plt.subplots(figsize=(12, max(5, 0.35 * len(prod_matrix))))
    image = ax.imshow(values, aspect="auto", cmap="RdYlGn", vmin=-vmax, vmax=vmax)
    ax.set_xticks(np.arange(len(prod_matrix.columns)))
    ax.set_xticklabels(prod_matrix.columns, rotation=35, ha="right")
    ax.set_yticks(np.arange(len(prod_matrix.index)))
    ax.set_yticklabels(prod_matrix.index)
    ax.set_title("Stage052 product x trend bucket realized PnL")
    fig.colorbar(image, ax=ax, shrink=0.8, label="PnL")
    fig.tight_layout()
    fig.savefig(PRODUCT_BUCKET_HEATMAP_OUT)
    plt.close(fig)

    scatter = features[features["direction_aligned_trend_tstat_252_stage052"].notna()].copy()
    fig, ax = plt.subplots(figsize=(10, 6))
    colors = np.where(scatter["realized_pnl"] >= 0, "#238b45", "#cb181d")
    sizes = np.clip(np.abs(scatter["realized_pnl"]) / 50000.0, 12, 260)
    ax.scatter(
        scatter["direction_aligned_trend_tstat_252_stage052"],
        scatter["realized_pnl"],
        c=colors,
        s=sizes,
        alpha=0.5,
        edgecolor="white",
        linewidth=0.35,
    )
    ax.axvline(TREND_TSTAT_CUTOFF, color="black", linestyle="--", linewidth=0.9, label="+2 cutoff")
    ax.axvline(0.0, color="black", linestyle=":", linewidth=0.8)
    ax.axhline(0.0, color="black", linewidth=0.8)
    ax.set_xlabel("direction-aligned 252d trend t-stat")
    ax.set_ylabel("realized PnL")
    ax.set_title("Stage052 closed lots vs Stage496 pre-entry product trend t-stat")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(SCATTER_OUT)
    plt.close(fig)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stage496_summary = _load_stage496_summary()
    trend_daily = _build_product_trend_daily()
    features = _load_features(trend_daily)
    curve = _load_official_curve()
    official = _official_metrics(curve)

    target = features[features["stage052_no_significant_aligned_trend"]].copy()
    upper_curve = _build_upper_bound_curve(curve, target)
    upper_metrics = _equity_metrics(upper_curve["upper_bound_skip_target_equity"], upper_curve["date"])
    dd_improvement_pp = float(upper_metrics["max_dd_pct"] - official["max_dd_pct"])
    return_retention_pct = float(upper_metrics["total_return_pct"] / official["total_return_pct"] * 100.0)

    cohort_summary = _cohort_summary(features)
    bucket_year = (
        features.groupby(["stage052_trend_bucket", "exit_year"], dropna=False)["realized_pnl"]
        .sum()
        .reset_index()
    )
    product_bucket = (
        features.groupby(["normalized_product", "stage052_trend_bucket"], dropna=False)["realized_pnl"]
        .sum()
        .reset_index()
    )
    coverage_by_year, coverage_by_product = _coverage_tables(features)
    leave_year = _leave_one(target, "exit_year")
    leave_product = _leave_one(target, "normalized_product")

    target_summary = _summary_for_group(features, TARGET_COHORT, target)
    exclude_2026 = leave_year[leave_year["removed_key"].astype(str).eq("2026")]
    excluding_2026_pnl = float(exclude_2026["remaining_pnl"].iloc[0]) if len(exclude_2026) else np.nan
    worst_product_removed = leave_product.sort_values("removed_pnl").head(1)
    excluding_top_loss_product_pnl = (
        float(worst_product_removed["remaining_pnl"].iloc[0]) if len(worst_product_removed) else np.nan
    )

    stage049_ready_lots = int(features["stage049_ready_bool"].sum())
    stage052_ready_lots = int(features["trend_ready_stage052"].sum())
    stage049_ready_pct = float(features["stage049_ready_bool"].mean() * 100.0)
    stage052_ready_pct = float(features["trend_ready_stage052"].mean() * 100.0)
    missing_pnl = float(features.loc[~features["trend_ready_stage052"], "realized_pnl"].sum())

    strict_pass = bool(
        target_summary["net_pnl"] < 0
        and target_summary["lot_count"] >= 40
        and target_summary["year_count"] >= 4
        and dd_improvement_pp >= 3.0
        and return_retention_pct >= 80.0
        and excluding_2026_pnl < 0
        and excluding_top_loss_product_pnl < 0
    )
    if strict_pass:
        decision = "stage052_stage496_tstat_proxy_promising_requires_ab_skill_before_engine"
    elif stage052_ready_pct < 80.0:
        decision = "stage052_stage496_preclose_coverage_improved_but_not_full_no_engine"
    else:
        decision = "stage052_stage496_tstat_no_candidate_no_engine"
    if target_summary["net_pnl"] > 0 or dd_improvement_pp < 0:
        decision = "stage052_stage496_tstat_target_right_tail_no_engine"

    summary_row = {
        "stage": STAGE,
        "decision": decision,
        "official_version": OFFICIAL_LIVE_VERSION,
        "official_alias": OFFICIAL_LIVE_ALIAS,
        "trend_window": TREND_WINDOW,
        "trend_min_periods": TREND_MIN_PERIODS,
        "trend_tstat_cutoff": TREND_TSTAT_CUTOFF,
        "max_signal_age_days": MAX_SIGNAL_AGE_DAYS,
        "lot_count": int(len(features)),
        "stage049_ready_lot_count": stage049_ready_lots,
        "stage049_ready_pct": stage049_ready_pct,
        "stage052_ready_lot_count": stage052_ready_lots,
        "stage052_ready_pct": stage052_ready_pct,
        "stage052_missing_lot_count": int((~features["trend_ready_stage052"]).sum()),
        "stage052_missing_net_pnl": missing_pnl,
        "stage052_ready_product_count": int(features.loc[features["trend_ready_stage052"], "normalized_product"].nunique()),
        "target_cohort": TARGET_COHORT,
        "target_lot_count": target_summary["lot_count"],
        "target_product_count": target_summary["product_count"],
        "target_year_count": target_summary["year_count"],
        "target_net_pnl": target_summary["net_pnl"],
        "target_positive_pnl": target_summary["positive_pnl"],
        "target_negative_pnl_abs": target_summary["negative_pnl_abs"],
        "target_positive_coverage_pct": target_summary["positive_coverage_pct"],
        "target_negative_coverage_pct": target_summary["negative_coverage_pct"],
        "official_end_equity": official["end_equity"],
        "official_total_return_pct": official["total_return_pct"],
        "official_max_dd_pct": official["max_dd_pct"],
        "official_max_dd_date": official["max_dd_date"],
        "official_sharpe": official["sharpe"],
        "official_total_slippage": official["total_slippage"],
        "official_total_trade_count": official["total_trade_count"],
        "official_win_rate_pct": official["win_rate_pct"],
        "official_broker10_peak_pct": official["max_broker10_margin_to_equity_pct"],
        "upper_bound_end_equity": upper_metrics["end_equity"],
        "upper_bound_total_return_pct": upper_metrics["total_return_pct"],
        "upper_bound_max_dd_pct": upper_metrics["max_dd_pct"],
        "upper_bound_max_dd_date": upper_metrics["max_dd_date"],
        "upper_bound_sharpe": upper_metrics["sharpe"],
        "upper_bound_max_dd_improvement_pp": dd_improvement_pp,
        "upper_bound_return_retention_pct": return_retention_pct,
        "excluding_2026_remaining_pnl": excluding_2026_pnl,
        "excluding_top_loss_product_remaining_pnl": excluding_top_loss_product_pnl,
        "strict_precheck_pass": strict_pass,
        "stage496_required_key_count": stage496_summary.get("required_key_count"),
        "stage496_strict_ready_rate": stage496_summary.get("strict_full_preclose_ready_rate"),
    }

    trend_daily.to_csv(PRODUCT_TREND_DAILY_OUT, index=False, encoding="utf-8-sig")
    features.to_csv(FEATURES_OUT, index=False, encoding="utf-8-sig")
    cohort_summary.to_csv(COHORT_SUMMARY_OUT, index=False, encoding="utf-8-sig")
    bucket_year.to_csv(BUCKET_YEAR_MATRIX_OUT, index=False, encoding="utf-8-sig")
    product_bucket.to_csv(PRODUCT_BUCKET_MATRIX_OUT, index=False, encoding="utf-8-sig")
    coverage_by_year.to_csv(COVERAGE_BY_YEAR_OUT, index=False, encoding="utf-8-sig")
    coverage_by_product.to_csv(COVERAGE_BY_PRODUCT_OUT, index=False, encoding="utf-8-sig")
    target.to_csv(TARGET_LOTS_OUT, index=False, encoding="utf-8-sig")
    upper_curve.to_csv(UPPER_BOUND_CURVE_OUT, index=False, encoding="utf-8-sig")
    leave_year.to_csv(LEAVE_ONE_YEAR_OUT, index=False, encoding="utf-8-sig")
    leave_product.to_csv(LEAVE_ONE_PRODUCT_OUT, index=False, encoding="utf-8-sig")
    pd.DataFrame([summary_row]).to_csv(SUMMARY_OUT, index=False, encoding="utf-8-sig")

    _write_charts(features, curve, upper_curve, bucket_year, product_bucket, coverage_by_year)

    decision_payload = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "line_id": LINE_ID,
        "decision": decision,
        "strict_precheck_pass": strict_pass,
        "official_version": OFFICIAL_LIVE_VERSION,
        "trend_spec": {
            "window": TREND_WINDOW,
            "min_periods": TREND_MIN_PERIODS,
            "cutoff": TREND_TSTAT_CUTOFF,
            "max_signal_age_days": MAX_SIGNAL_AGE_DAYS,
            "source": str(STAGE496_SYNTHETIC_IN),
        },
        "summary": summary_row,
        "outputs": {
            "product_trend_daily": PRODUCT_TREND_DAILY_OUT,
            "features": FEATURES_OUT,
            "cohort_summary": COHORT_SUMMARY_OUT,
            "coverage_by_year": COVERAGE_BY_YEAR_OUT,
            "coverage_by_product": COVERAGE_BY_PRODUCT_OUT,
            "target_lots": TARGET_LOTS_OUT,
            "upper_bound_curve": UPPER_BOUND_CURVE_OUT,
            "decision": DECISION_OUT,
            "report": REPORT_OUT,
            "path_chart": PATH_CHART_OUT,
            "contribution_chart": CONTRIBUTION_CHART_OUT,
            "coverage_chart": COVERAGE_CHART_OUT,
            "bucket_year_heatmap": BUCKET_YEAR_HEATMAP_OUT,
            "product_bucket_heatmap": PRODUCT_BUCKET_HEATMAP_OUT,
            "scatter": SCATTER_OUT,
        },
    }
    DECISION_OUT.write_text(json.dumps(_json_safe(decision_payload), ensure_ascii=False, indent=2), encoding="utf-8")

    bucket_view = cohort_summary[
        cohort_summary["bucket"].isin(
            [
                "aligned_significant_ge2",
                "aligned_weak_0_2",
                "opposite_weak_neg2_0",
                "opposite_significant_le_neg2",
                "trend_missing",
                TARGET_COHORT,
                "all_lots",
            ]
        )
    ].copy()
    year_view = (
        target.groupby("exit_year")
        .agg(lots=("realized_pnl", "size"), net_pnl=("realized_pnl", "sum"))
        .reset_index()
        .sort_values("exit_year")
    )
    product_view = (
        target.groupby("normalized_product")
        .agg(lots=("realized_pnl", "size"), net_pnl=("realized_pnl", "sum"))
        .reset_index()
        .sort_values("net_pnl")
    )
    coverage_view = coverage_by_year[
        [
            "prev_state_year",
            "lot_count",
            "stage049_ready_pct",
            "stage052_ready_pct",
            "stage052_missing_pnl",
        ]
    ].copy()
    report = f"""# {STAGE} product trend t-stat Stage496 reaudit

## Positioning

- Official version: `{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`.
- This is a read-only data-engineering reaudit of Stage049's fixed trend t-stat specification.
- Source change only: Stage049 shard source is replaced by Stage496 all-required preclose full-bar source.
- No trading threshold, product, year, direction, or official execution setting is changed.

## Fixed Spec

- Product log-preclose linear trend t-stat window: `{TREND_WINDOW}` rows.
- Minimum rows: `{TREND_MIN_PERIODS}`.
- Direction-aligned significant trend cutoff: `+{TREND_TSTAT_CUTOFF}`.
- Target cohort for upper-bound test: `{TARGET_COHORT}`.
- Max signal age: `{MAX_SIGNAL_AGE_DAYS}` calendar days.

## Main Result

| item | value |
| --- | ---: |
| lots | {summary_row['lot_count']} |
| Stage049 ready lots | {summary_row['stage049_ready_lot_count']} |
| Stage049 ready pct | {_fmt(summary_row['stage049_ready_pct'])}% |
| Stage052 ready lots | {summary_row['stage052_ready_lot_count']} |
| Stage052 ready pct | {_fmt(summary_row['stage052_ready_pct'])}% |
| Stage052 missing net PnL | {_fmt(summary_row['stage052_missing_net_pnl'], 2)} |
| target lots | {summary_row['target_lot_count']} |
| target net PnL | {_fmt(summary_row['target_net_pnl'], 2)} |
| official end equity | {_fmt(summary_row['official_end_equity'], 2)} |
| official total return | {_fmt(summary_row['official_total_return_pct'])}% |
| official max DD | {_fmt(summary_row['official_max_dd_pct'])}% |
| upper-bound end equity | {_fmt(summary_row['upper_bound_end_equity'], 2)} |
| upper-bound total return | {_fmt(summary_row['upper_bound_total_return_pct'])}% |
| upper-bound max DD | {_fmt(summary_row['upper_bound_max_dd_pct'])}% |
| max DD improvement pp | {_fmt(summary_row['upper_bound_max_dd_improvement_pp'])} |
| return retention | {_fmt(summary_row['upper_bound_return_retention_pct'])}% |
| decision | `{decision}` |

## Cohort Summary

{_md_table(bucket_view)}

## Target Year Summary

{_md_table(year_view)}

## Target Product Summary

{_md_table(product_view, max_rows=30)}

## Coverage By Year

{_md_table(coverage_view)}

## Visual Notes

- Path chart: `{PATH_CHART_OUT.name}`.
- Contribution chart: `{CONTRIBUTION_CHART_OUT.name}`.
- Coverage improvement chart: `{COVERAGE_CHART_OUT.name}`.
- Bucket-year heatmap: `{BUCKET_YEAR_HEATMAP_OUT.name}`.
- Product-bucket heatmap: `{PRODUCT_BUCKET_HEATMAP_OUT.name}`.
- Scatter: `{SCATTER_OUT.name}`.

## Interpretation

- Stage496 materially improves the trend t-stat data coverage versus Stage049.
- The fixed target cohort remains a strong positive contribution cohort, so skipping it is not a drawdown repair.
- This result supports further data engineering only as infrastructure, not as a current trading candidate.
"""
    REPORT_OUT.write_text(report, encoding="utf-8")
    print(json.dumps(_json_safe(summary_row), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
