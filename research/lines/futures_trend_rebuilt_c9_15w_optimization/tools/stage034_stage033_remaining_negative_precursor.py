from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any, Callable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage034"
MODEL_TAG = "stage034_stage033_remaining_negative_precursor_v1"
OUTPUT_PREFIX = "rebuilt_c9_stage034_stage033_remaining_negative_precursor"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage034_stage033_remaining_negative_precursor"
STAGE_RECORD_DIR = LINE_DIR / "stages"

STAGE017_OUTPUT_DIR = LINE_DIR / "outputs" / "stage017_external_regime_volatility_attribution"
STAGE021_OUTPUT_DIR = LINE_DIR / "outputs" / "stage021_full_market_consensus_jd_proxy"
STAGE033_OUTPUT_DIR = LINE_DIR / "outputs" / "stage033_rank19_early_quality_add_risk_proxy"

STAGE017_PREFIX = "rebuilt_c9_stage017_external_regime_volatility_attribution"
STAGE017_TAG = "stage017_external_regime_volatility_attribution_v1"
STAGE021_PREFIX = "rebuilt_c9_stage021_full_market_consensus_jd_proxy"
STAGE021_TAG = "stage021_full_market_consensus_jd_proxy_v1"
STAGE033_PREFIX = "rebuilt_c9_stage033_rank19_early_quality_add_risk_proxy"
STAGE033_TAG = "stage033_rank19_early_quality_add_risk_proxy_v1"

STAGE033_CURVES_PATH = STAGE033_OUTPUT_DIR / f"{STAGE033_PREFIX}_curves_{STAGE033_TAG}.csv"
MARKET_DAILY_PATH = STAGE017_OUTPUT_DIR / f"{STAGE017_PREFIX}_market_daily_summary_{STAGE017_TAG}.csv"
FULL_MARKET_PREDICTIONS_PATH = (
    STAGE021_OUTPUT_DIR / f"{STAGE021_PREFIX}_full_market_predictions_ranked_{STAGE021_TAG}.csv"
)

START_OUTCOMES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_start_outcomes_{MODEL_TAG}.csv"
FEATURE_MATRIX_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_matrix_{MODEL_TAG}.csv"
BUCKET_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_summary_{MODEL_TAG}.csv"
CONDITION_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_condition_summary_{MODEL_TAG}.csv"
STABILITY_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stability_summary_{MODEL_TAG}.csv"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

OBJECTIVE_START_MIN = pd.Timestamp("2020-01-01")
OBJECTIVE_START_MAX = pd.Timestamp("2025-06-30")
MIN_PERIOD_DAYS = 365


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return None if not np.isfinite(number) else number
    if not isinstance(value, (str, bytes)) and pd.isna(value):
        return None
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_空_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    return data.to_markdown(index=False)


def _bucket_number(value: Any, bins: list[tuple[float, str]], default: str) -> str:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return "missing"
    number = float(number)
    for upper, label in bins:
        if number <= upper:
            return label
    return default


def _drawdown_bucket(value: Any) -> str:
    return _bucket_number(
        value,
        [
            (-40.0, "dd_le_-40"),
            (-30.0, "dd_-40_-30"),
            (-20.0, "dd_-30_-20"),
            (-10.0, "dd_-20_-10"),
        ],
        "dd_gt_-10",
    )


def _return_bucket(value: Any) -> str:
    return _bucket_number(
        value,
        [
            (-20.0, "ret_le_-20"),
            (-10.0, "ret_-20_-10"),
            (0.0, "ret_-10_0"),
            (20.0, "ret_0_20"),
        ],
        "ret_gt_20",
    )


def _broker_bucket(value: Any) -> str:
    return _bucket_number(
        value,
        [
            (0.0, "broker_0"),
            (40.0, "broker_0_40"),
            (60.0, "broker_40_60"),
            (70.0, "broker_60_70"),
            (80.0, "broker_70_80"),
        ],
        "broker_ge80",
    )


def _active_bucket(value: Any) -> str:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return "missing"
    number = int(number)
    if number >= 4:
        return "active_4plus"
    return f"active_{number}"


def _read_stage033_curves() -> pd.DataFrame:
    usecols = [
        "requested_start_month",
        "date",
        "account_equity",
        "stage020_account_equity",
        "broker10_margin_to_equity_pct",
        "c3_active_products",
        "c3_active_contracts",
        "net_pnl",
        "holding_pnl",
        "trading_pnl",
        "trade_count",
        "drawdown_pct",
        "stage020_drawdown_pct",
    ]
    curves = pd.read_csv(STAGE033_CURVES_PATH, encoding="utf-8-sig", usecols=usecols, parse_dates=["date"])
    curves["date"] = curves["date"].dt.normalize()
    curves["requested_start_month"] = curves["requested_start_month"].astype(str)
    for column in usecols:
        if column not in {"requested_start_month", "date"}:
            curves[column] = pd.to_numeric(curves[column], errors="coerce").fillna(0.0)
    curves.rename(
        columns={
            "account_equity": "stage013_account_equity",
            "stage020_account_equity": "stage033_account_equity",
            "drawdown_pct": "stage013_drawdown_pct",
            "stage020_drawdown_pct": "stage033_drawdown_pct",
        },
        inplace=True,
    )
    frames: list[pd.DataFrame] = []
    for _, group in curves.groupby("requested_start_month", sort=True):
        g = group.sort_values("date").reset_index(drop=True).copy()
        equity = g["stage033_account_equity"].replace(0.0, np.nan)
        for window in (21, 63, 126):
            previous = equity.shift(window)
            g[f"stage033_return_{window}d_pct"] = (equity / previous - 1.0) * 100.0
            g[f"net_pnl_sum_{window}d"] = g["net_pnl"].rolling(window, min_periods=1).sum()
            g[f"holding_pnl_sum_{window}d"] = g["holding_pnl"].rolling(window, min_periods=1).sum()
            g[f"broker_max_{window}d"] = g["broker10_margin_to_equity_pct"].rolling(window, min_periods=1).max()
            g[f"active_max_{window}d"] = g["c3_active_products"].rolling(window, min_periods=1).max()
        frames.append(g)
    return pd.concat(frames, ignore_index=True, sort=False)


def _start_outcomes(curves: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for source, group in curves.groupby("requested_start_month", sort=True):
        g = group.sort_values("date").reset_index(drop=True)
        dates = pd.to_datetime(g["date"], errors="coerce")
        date_values = dates.to_numpy(dtype="datetime64[ns]")
        equity = pd.to_numeric(g["stage033_account_equity"], errors="coerce").to_numpy(dtype=float)
        final_equity = float(equity[-1]) if len(equity) else np.nan
        for start_idx, start_date in enumerate(dates):
            if start_date < OBJECTIVE_START_MIN or start_date > OBJECTIVE_START_MAX:
                continue
            if not np.isfinite(equity[start_idx]) or equity[start_idx] <= 0.0:
                continue
            first_valid_end = np.datetime64((start_date + pd.Timedelta(days=MIN_PERIOD_DAYS + 1)).to_datetime64(), "ns")
            end_start_idx = int(np.searchsorted(date_values, first_valid_end))
            if end_start_idx >= len(g):
                continue
            future = equity[end_start_idx:]
            valid_future = future[np.isfinite(future)]
            if valid_future.size == 0:
                continue
            returns = (valid_future / equity[start_idx] - 1.0) * 100.0
            min_pos = int(np.argmin(returns))
            end_idx = end_start_idx + min_pos
            rows.append(
                {
                    "variant": "stage033_rank19_early_quality_proxy",
                    "source_start_month": source,
                    "start_date": start_date,
                    "worst_end_date": dates.iloc[end_idx],
                    "start_equity": float(equity[start_idx]),
                    "worst_end_equity": float(equity[end_idx]),
                    "min_future_return_pct": float(returns[min_pos]),
                    "to_final_return_pct": float((final_equity / equity[start_idx] - 1.0) * 100.0),
                    "strict_negative_start": int(float(returns[min_pos]) < 0.0),
                    "severe_negative_start": int(float(returns[min_pos]) <= -10.0),
                    "period_calendar_days_at_worst": int((dates.iloc[end_idx] - start_date).days),
                    "period_trading_days_at_worst": int(end_idx - start_idx + 1),
                }
            )
    return pd.DataFrame(rows).sort_values(["source_start_month", "start_date"]).reset_index(drop=True)


def _ai_monthly_summary() -> pd.DataFrame:
    usecols = [
        "eval_date",
        "product_vt_symbol",
        "predicted_product_suitability_probability",
        "simple_trend_suitability_score",
        "simple_trend_suitability_score_percentile",
        "candidate_count_sum_60d",
        "opened_count_sum_60d",
        "market_ma20_over_ma60_60d",
        "market_realized_vol_60d",
        "market_ret_60d",
        "market_trend_efficiency_60d",
        "stage021_ai_top8",
        "stage021_simple_top8",
        "stage021_consensus_top8",
        "stage021_consensus_top8_jd",
    ]
    data = pd.read_csv(FULL_MARKET_PREDICTIONS_PATH, encoding="utf-8-sig", usecols=usecols, parse_dates=["eval_date"])
    data["eval_date"] = data["eval_date"].dt.normalize()
    for column in usecols:
        if column not in {"eval_date", "product_vt_symbol"}:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    for column in ["stage021_ai_top8", "stage021_simple_top8", "stage021_consensus_top8", "stage021_consensus_top8_jd"]:
        data[column] = data[column].astype(bool)

    top = data[data["stage021_ai_top8"]].copy()
    consensus = data[data["stage021_consensus_top8"]].copy()
    monthly = (
        data.groupby("eval_date", dropna=False)
        .agg(
            full_market_product_count=("product_vt_symbol", "nunique"),
            all_prob_mean=("predicted_product_suitability_probability", "mean"),
            all_prob_std=("predicted_product_suitability_probability", "std"),
            all_simple_score_mean=("simple_trend_suitability_score", "mean"),
            all_candidate_count_60d_sum=("candidate_count_sum_60d", "sum"),
            all_opened_count_60d_sum=("opened_count_sum_60d", "sum"),
            all_market_breadth_median=("market_ma20_over_ma60_60d", "median"),
            all_market_eff_median=("market_trend_efficiency_60d", "median"),
        )
        .reset_index()
    )
    top_monthly = (
        top.groupby("eval_date", dropna=False)
        .agg(
            ai_top8_count=("product_vt_symbol", "nunique"),
            ai_top8_prob_mean=("predicted_product_suitability_probability", "mean"),
            ai_top8_prob_min=("predicted_product_suitability_probability", "min"),
            ai_top8_prob_std=("predicted_product_suitability_probability", "std"),
            ai_top8_simple_pct_median=("simple_trend_suitability_score_percentile", "median"),
            ai_top8_candidate_count_60d_sum=("candidate_count_sum_60d", "sum"),
            ai_top8_opened_count_60d_sum=("opened_count_sum_60d", "sum"),
            ai_top8_market_eff_median=("market_trend_efficiency_60d", "median"),
            ai_top8_market_vol_median=("market_realized_vol_60d", "median"),
        )
        .reset_index()
    )
    consensus_monthly = (
        consensus.groupby("eval_date", dropna=False)
        .agg(
            consensus_top8_count=("product_vt_symbol", "nunique"),
            consensus_prob_mean=("predicted_product_suitability_probability", "mean"),
            consensus_simple_pct_median=("simple_trend_suitability_score_percentile", "median"),
            consensus_candidate_count_60d_sum=("candidate_count_sum_60d", "sum"),
            jd_consensus_count=("stage021_consensus_top8_jd", "sum"),
        )
        .reset_index()
    )
    result = monthly.merge(top_monthly, on="eval_date", how="left").merge(consensus_monthly, on="eval_date", how="left")
    for column in result.columns:
        if column != "eval_date":
            result[column] = pd.to_numeric(result[column], errors="coerce").fillna(0.0)
    result = result.sort_values("eval_date").reset_index(drop=True)
    for column in ("ai_top8_prob_mean", "ai_top8_prob_min", "consensus_top8_count", "all_market_eff_median"):
        buckets: list[str] = []
        history: list[float] = []
        for value in pd.to_numeric(result[column], errors="coerce"):
            if len(history) < 12 or not np.isfinite(value):
                buckets.append("warmup")
            else:
                low = float(np.nanquantile(history, 0.33))
                high = float(np.nanquantile(history, 0.67))
                if value <= low:
                    buckets.append("low")
                elif value >= high:
                    buckets.append("high")
                else:
                    buckets.append("mid")
            if np.isfinite(value):
                history.append(float(value))
        result[f"{column}_exp_bucket"] = buckets
    return result


def _feature_matrix(curves: pd.DataFrame, outcomes: pd.DataFrame, market_daily: pd.DataFrame, ai_monthly: pd.DataFrame) -> pd.DataFrame:
    start_features = curves.rename(columns={"requested_start_month": "source_start_month", "date": "start_date"})
    feature_cols = [
        "source_start_month",
        "start_date",
        "stage013_account_equity",
        "stage033_account_equity",
        "broker10_margin_to_equity_pct",
        "c3_active_products",
        "c3_active_contracts",
        "net_pnl",
        "holding_pnl",
        "trading_pnl",
        "trade_count",
        "stage013_drawdown_pct",
        "stage033_drawdown_pct",
        "stage033_return_21d_pct",
        "stage033_return_63d_pct",
        "stage033_return_126d_pct",
        "net_pnl_sum_21d",
        "net_pnl_sum_63d",
        "net_pnl_sum_126d",
        "holding_pnl_sum_21d",
        "holding_pnl_sum_63d",
        "holding_pnl_sum_126d",
        "broker_max_21d",
        "broker_max_63d",
        "broker_max_126d",
        "active_max_21d",
        "active_max_63d",
        "active_max_126d",
    ]
    features = outcomes.merge(start_features[feature_cols], on=["source_start_month", "start_date"], how="left")
    market = market_daily.copy()
    market["date"] = pd.to_datetime(market["date"], errors="coerce").dt.normalize()
    features = features.merge(market.rename(columns={"date": "start_date"}), on="start_date", how="left")
    ai = ai_monthly.sort_values("eval_date").copy()
    features = features.sort_values("start_date")
    features = pd.merge_asof(features, ai, left_on="start_date", right_on="eval_date", direction="backward")

    features["stage033_drawdown_bucket"] = features["stage033_drawdown_pct"].map(_drawdown_bucket)
    features["stage013_drawdown_bucket"] = features["stage013_drawdown_pct"].map(_drawdown_bucket)
    features["broker_bucket"] = features["broker10_margin_to_equity_pct"].map(_broker_bucket)
    features["active_products_bucket"] = features["c3_active_products"].map(_active_bucket)
    for window in (21, 63, 126):
        features[f"stage033_return_{window}d_bucket"] = features[f"stage033_return_{window}d_pct"].map(_return_bucket)
    features["consensus_count_bucket"] = features["consensus_top8_count"].map(
        lambda value: "consensus_0"
        if float(value or 0.0) <= 0
        else ("consensus_1_3" if float(value) <= 3 else "consensus_4plus")
    )
    return features.sort_values(["source_start_month", "start_date"]).reset_index(drop=True)


def _summarize_group(frame: pd.DataFrame, name: str, group: pd.DataFrame) -> dict[str, Any]:
    strict = pd.to_numeric(group["strict_negative_start"], errors="coerce").fillna(0).astype(int)
    severe = pd.to_numeric(group["severe_negative_start"], errors="coerce").fillna(0).astype(int)
    min_ret = pd.to_numeric(group["min_future_return_pct"], errors="coerce")
    base_rate = float(pd.to_numeric(frame["strict_negative_start"], errors="coerce").fillna(0).mean() * 100.0)
    negative_rate = float(strict.mean() * 100.0) if len(group) else 0.0
    return {
        "name": name,
        "count": int(len(group)),
        "source_start_count": int(group["source_start_month"].nunique()),
        "date_count": int(group["start_date"].nunique()),
        "strict_negative_count": int(strict.sum()),
        "strict_negative_rate_pct": negative_rate,
        "lift_vs_all": float(negative_rate / base_rate) if base_rate else np.nan,
        "severe_negative_count": int(severe.sum()),
        "severe_negative_rate_pct": float(severe.mean() * 100.0) if len(group) else 0.0,
        "min_of_min_future_return_pct": float(min_ret.min()),
        "p10_min_future_return_pct": float(min_ret.quantile(0.10)),
        "median_min_future_return_pct": float(min_ret.median()),
        "mean_min_future_return_pct": float(min_ret.mean()),
        "median_to_final_return_pct": float(pd.to_numeric(group["to_final_return_pct"], errors="coerce").median()),
    }


def _bucket_summary(features: pd.DataFrame) -> pd.DataFrame:
    bucket_features = [
        "stage033_drawdown_bucket",
        "stage013_drawdown_bucket",
        "broker_bucket",
        "active_products_bucket",
        "stage033_return_21d_bucket",
        "stage033_return_63d_bucket",
        "stage033_return_126d_bucket",
        "joint_regime",
        "vol60_bucket",
        "trend_eff60_bucket",
        "trend_breadth_bucket",
        "close_extreme_bucket",
        "ai_top8_prob_mean_exp_bucket",
        "ai_top8_prob_min_exp_bucket",
        "consensus_top8_count_exp_bucket",
        "consensus_count_bucket",
        "all_market_eff_median_exp_bucket",
    ]
    rows: list[dict[str, Any]] = []
    for feature in bucket_features:
        if feature not in features.columns:
            continue
        for value, group in features.groupby(feature, dropna=False):
            if len(group) < 30:
                continue
            row = _summarize_group(features, str(value), group)
            row["feature"] = feature
            row["feature_value"] = str(value)
            rows.append(row)
    return pd.DataFrame(rows).sort_values(
        ["lift_vs_all", "strict_negative_rate_pct", "count"], ascending=[False, False, False]
    )


def _condition_summary(features: pd.DataFrame) -> pd.DataFrame:
    condition_map: dict[str, Callable[[pd.DataFrame], pd.Series]] = {
        "all_starts": lambda df: pd.Series(True, index=df.index),
        "stage033_dd_le_-20": lambda df: df["stage033_drawdown_pct"].le(-20),
        "stage033_dd_le_-30": lambda df: df["stage033_drawdown_pct"].le(-30),
        "stage033_63d_loss": lambda df: df["stage033_return_63d_pct"].lt(0),
        "stage033_126d_loss": lambda df: df["stage033_return_126d_pct"].lt(0),
        "active3plus_63d_loss": lambda df: df["c3_active_products"].ge(3) & df["stage033_return_63d_pct"].lt(0),
        "broker60_or_active4": lambda df: df["broker10_margin_to_equity_pct"].ge(60) | df["c3_active_products"].ge(4),
        "market_high_vol_low_eff": lambda df: df["joint_regime"].eq("high_vol_low_eff"),
        "market_high_vol_high_eff": lambda df: df["joint_regime"].eq("high_vol_high_eff"),
        "market_narrow_chop": lambda df: df["joint_regime"].eq("narrow_chop"),
        "market_breadth_low": lambda df: df["trend_breadth_bucket"].eq("breadth_low"),
        "ai_prob_mean_low": lambda df: df["ai_top8_prob_mean_exp_bucket"].eq("low"),
        "ai_prob_min_low": lambda df: df["ai_top8_prob_min_exp_bucket"].eq("low"),
        "ai_consensus_low": lambda df: df["consensus_top8_count_exp_bucket"].eq("low"),
        "loss_and_high_vol_low_eff": lambda df: df["stage033_return_63d_pct"].lt(0)
        & df["joint_regime"].eq("high_vol_low_eff"),
        "loss_and_high_vol_high_eff": lambda df: df["stage033_return_63d_pct"].lt(0)
        & df["joint_regime"].eq("high_vol_high_eff"),
        "loss_and_breadth_low": lambda df: df["stage033_return_63d_pct"].lt(0)
        & df["trend_breadth_bucket"].eq("breadth_low"),
        "loss_and_ai_low": lambda df: df["stage033_return_63d_pct"].lt(0)
        & df["ai_top8_prob_mean_exp_bucket"].eq("low"),
        "ai_low_and_breadth_low": lambda df: df["ai_top8_prob_mean_exp_bucket"].eq("low")
        & df["trend_breadth_bucket"].eq("breadth_low"),
        "risk_stack_loss_market_ai": lambda df: df["stage033_return_63d_pct"].lt(0)
        & df["ai_top8_prob_mean_exp_bucket"].eq("low")
        & df["joint_regime"].isin(["high_vol_low_eff", "narrow_chop", "quiet_low_eff"]),
        "risk_stack_active_loss_chop": lambda df: df["c3_active_products"].ge(3)
        & df["stage033_return_63d_pct"].lt(0)
        & df["joint_regime"].isin(["high_vol_low_eff", "narrow_chop"]),
    }
    rows: list[dict[str, Any]] = []
    for name, maker in condition_map.items():
        mask = maker(features).fillna(False).astype(bool)
        group = features[mask].copy()
        if group.empty:
            continue
        row = _summarize_group(features, name, group)
        row["condition"] = name
        rows.append(row)
    return pd.DataFrame(rows).sort_values(
        ["lift_vs_all", "strict_negative_rate_pct", "count"], ascending=[False, False, False]
    )


def _stability_summary(features: pd.DataFrame) -> pd.DataFrame:
    specs: dict[str, Callable[[pd.DataFrame], pd.Series]] = {
        "condition_loss_and_high_vol_low_eff": lambda df: df["stage033_return_63d_pct"].lt(0)
        & df["joint_regime"].eq("high_vol_low_eff"),
        "condition_loss_and_high_vol_high_eff": lambda df: df["stage033_return_63d_pct"].lt(0)
        & df["joint_regime"].eq("high_vol_high_eff"),
        "condition_risk_stack_loss_market_ai": lambda df: df["stage033_return_63d_pct"].lt(0)
        & df["ai_top8_prob_mean_exp_bucket"].eq("low")
        & df["joint_regime"].isin(["high_vol_low_eff", "narrow_chop", "quiet_low_eff"]),
        "bucket_stage033_dd_le_-30": lambda df: df["stage033_drawdown_pct"].le(-30),
    }
    rows: list[dict[str, Any]] = []
    for name, maker in specs.items():
        mask = maker(features).fillna(False).astype(bool)
        scoped = features[mask].copy()
        if scoped.empty:
            continue
        for source, group in scoped.groupby("source_start_month", dropna=False):
            row = _summarize_group(features, name, group)
            row["stability_axis"] = "source_start_month"
            row["stability_value"] = str(source)
            rows.append(row)
        for year, group in scoped.groupby(scoped["start_date"].dt.year, dropna=False):
            row = _summarize_group(features, name, group)
            row["stability_axis"] = "start_year"
            row["stability_value"] = str(int(year)) if pd.notna(year) else "missing"
            rows.append(row)
    return pd.DataFrame(rows).sort_values(["name", "stability_axis", "stability_value"]).reset_index(drop=True)


def _plot(condition_summary: pd.DataFrame, bucket_summary: pd.DataFrame) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(2, 2, figsize=(18, 12))
    top_conditions = condition_summary[condition_summary["condition"].ne("all_starts")].head(12).copy()
    axes[0, 0].barh(top_conditions["condition"], top_conditions["strict_negative_rate_pct"], color="#2563eb")
    axes[0, 0].invert_yaxis()
    axes[0, 0].set_title("Stage034 Condition Strict Negative Rate")
    axes[0, 0].set_xlabel("strict negative rate %")

    axes[0, 1].scatter(
        condition_summary["count"],
        condition_summary["strict_negative_rate_pct"],
        s=np.clip(condition_summary["source_start_count"] * 12, 30, 220),
        color="#dc2626",
        alpha=0.75,
    )
    for row in condition_summary.head(8).itertuples(index=False):
        axes[0, 1].annotate(row.condition, (row.count, row.strict_negative_rate_pct), fontsize=8)
    axes[0, 1].set_xscale("log")
    axes[0, 1].set_title("Condition Count vs Negative Rate")
    axes[0, 1].set_xlabel("count (log)")
    axes[0, 1].set_ylabel("strict negative rate %")

    top_buckets = bucket_summary.head(14).copy()
    labels = top_buckets["feature"] + "=" + top_buckets["feature_value"]
    axes[1, 0].barh(labels, top_buckets["lift_vs_all"], color="#16a34a")
    axes[1, 0].invert_yaxis()
    axes[1, 0].set_title("Top Bucket Lift vs All")
    axes[1, 0].set_xlabel("lift")

    axes[1, 1].scatter(
        bucket_summary["count"],
        bucket_summary["strict_negative_rate_pct"],
        s=np.clip(bucket_summary["source_start_count"] * 8, 25, 200),
        color="#7c3aed",
        alpha=0.70,
    )
    for row in bucket_summary.head(8).itertuples(index=False):
        axes[1, 1].annotate(f"{row.feature_value}", (row.count, row.strict_negative_rate_pct), fontsize=8)
    axes[1, 1].set_xscale("log")
    axes[1, 1].set_title("Bucket Count vs Negative Rate")
    axes[1, 1].set_xlabel("count (log)")
    axes[1, 1].set_ylabel("strict negative rate %")

    for axis in axes.ravel():
        axis.grid(True, alpha=0.22)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _decision(
    outcomes: pd.DataFrame,
    condition_summary: pd.DataFrame,
    bucket_summary: pd.DataFrame,
) -> dict[str, Any]:
    all_row = condition_summary[condition_summary["condition"].eq("all_starts")].iloc[0].to_dict()
    candidates = condition_summary[
        condition_summary["condition"].ne("all_starts")
        & condition_summary["count"].ge(100)
        & condition_summary["source_start_count"].ge(3)
    ].copy()
    top_condition = candidates.iloc[0].to_dict() if not candidates.empty else {}
    bucket_candidates = bucket_summary[
        bucket_summary["count"].ge(100)
        & bucket_summary["source_start_count"].ge(3)
        & bucket_summary["feature_value"].ne("warmup")
    ].copy()
    top_bucket = bucket_candidates.iloc[0].to_dict() if not bucket_candidates.empty else {}
    strict_count = int(pd.to_numeric(outcomes["strict_negative_start"], errors="coerce").sum())
    start_count = int(len(outcomes))
    top_lift = float(top_condition.get("lift_vs_all", np.nan))
    top_rate = float(top_condition.get("strict_negative_rate_pct", np.nan))
    top_count = int(top_condition.get("count", 0) or 0)
    decision_label = "stage034_precursor_attribution_only_no_engine_candidate"
    if str(top_condition.get("condition", "")) == "market_high_vol_high_eff":
        decision_label = "stage034_known_regime_precursor_persists_hard_gate_already_failed"
    elif top_count >= 500 and np.isfinite(top_lift) and top_lift >= 2.0 and top_rate >= 50.0:
        decision_label = "stage034_new_precursor_found_needs_causal_engine_validation"
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "audit_type": "stage033_strict_gt_1y_negative_start_precursor_attribution",
        "decision": decision_label,
        "start_row_count": start_count,
        "strict_negative_start_count": strict_count,
        "strict_negative_start_rate_pct": float(all_row.get("strict_negative_rate_pct", np.nan)),
        "severe_negative_start_count": int(pd.to_numeric(outcomes["severe_negative_start"], errors="coerce").sum()),
        "min_future_return_pct": float(pd.to_numeric(outcomes["min_future_return_pct"], errors="coerce").min()),
        "top_condition": str(top_condition.get("condition", "")),
        "top_condition_count": top_count,
        "top_condition_negative_rate_pct": top_rate,
        "top_condition_lift": top_lift,
        "top_bucket_feature": str(top_bucket.get("feature", "")),
        "top_bucket_value": str(top_bucket.get("feature_value", "")),
        "top_bucket_count": int(top_bucket.get("count", 0) or 0),
        "top_bucket_negative_rate_pct": float(top_bucket.get("strict_negative_rate_pct", np.nan)),
        "top_bucket_lift": float(top_bucket.get("lift_vs_all", np.nan)),
        "strategy_changed": False,
        "true_engine": False,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "external_research_judgment": (
            "Recent managed-futures research points to market mix, horizon mix, and governable risk choices as "
            "more robust than isolated add-size rules. Stage034 therefore audits Stage033's remaining negative "
            "starts against causal account, market-regime, and AI-pool state features before designing any engine rule."
        ),
        "overfit_reflection_before": (
            "否。Stage034 不改策略、不扫参数，只解释 Stage033 剩余严格负窗口的前置信号。"
        ),
        "continue_value_before": (
            "有。Stage033 已确认早段质量加风险有增益但不达标，必须定位剩余左尾是否有稳定 selector。"
        ),
        "overfit_reflection_after": (
            "否。本阶段没有把最高 lift 条件直接变成交易规则；若下一步按局部年份/source 调条件会过拟合。"
        ),
        "continue_value_after": (
            "有，但不是重复 high_vol_high_eff hard gate。Stage034 证明 Stage033 后剩余左尾仍由同一坏环境前兆主导，"
            "而 Stage024/025/026 已反证单一暂停规则；下一步必须拆分该 regime 内右尾错杀与真坏窗口，或转外生信息源。"
        ),
        "outputs": {
            "start_outcomes": str(START_OUTCOMES_PATH),
            "feature_matrix": str(FEATURE_MATRIX_PATH),
            "bucket_summary": str(BUCKET_SUMMARY_PATH),
            "condition_summary": str(CONDITION_SUMMARY_PATH),
            "stability_summary": str(STABILITY_SUMMARY_PATH),
            "chart": str(CHART_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }


def _write_report(
    decision: dict[str, Any],
    condition_summary: pd.DataFrame,
    bucket_summary: pd.DataFrame,
    stability_summary: pd.DataFrame,
) -> None:
    lines = [
        "# Stage034 Stage033 剩余负窗口前置信号归因",
        "",
        f"- 生成时间：`{decision['generated_at']}`",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 决策：`{decision['decision']}`",
        "- 阶段性质：只读归因；不是真实组合引擎，不改 C9，不连接 CTP，不调用下单。",
        "",
        "## 外部调研判断",
        "",
        "- 趋势跟随资料提示稳健改进更可能来自市场组合、horizon 组合和可治理风险预算，而不是单一加仓标签。",
        "- Stage034 因此只解释 Stage033 剩余负窗口，不把最高 lift 条件直接上线。",
        "",
        "## 总体结果",
        "",
        f"- 可审计起点行：`{decision['start_row_count']}`。",
        f"- 严格负起点：`{decision['strict_negative_start_count']}`，负起点率 `{decision['strict_negative_start_rate_pct']:.4f}%`。",
        f"- 最差未来任意 `>1` 年收益：`{decision['min_future_return_pct']:.4f}%`。",
        f"- 最强条件：`{decision['top_condition']}`，负起点率 `{decision['top_condition_negative_rate_pct']:.4f}%`，lift `{decision['top_condition_lift']:.4f}`，样本 `{decision['top_condition_count']}`。",
        f"- 最强分桶：`{decision['top_bucket_feature']}={decision['top_bucket_value']}`，负起点率 `{decision['top_bucket_negative_rate_pct']:.4f}%`，lift `{decision['top_bucket_lift']:.4f}`，样本 `{decision['top_bucket_count']}`。",
        "",
        "## 条件摘要",
        "",
        _md_table(condition_summary.head(20)),
        "",
        "## 分桶摘要",
        "",
        _md_table(bucket_summary.head(20)),
        "",
        "## 稳定性摘要",
        "",
        _md_table(stability_summary.head(32)),
        "",
        "## 判断",
        "",
        f"- 决策：`{decision['decision']}`。",
        f"- 过拟合反思：{decision['overfit_reflection_after']}",
        f"- 继续价值反思：{decision['continue_value_after']}",
        "",
        "## 输出文件",
        "",
    ]
    for key, path in decision["outputs"].items():
        lines.append(f"- {key}: `{path}`")
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_stage_record(decision: dict[str, Any]) -> Path:
    timestamp = datetime.now()
    record_path = STAGE_RECORD_DIR / f"{timestamp:%Y%m%d_%H%M}_stage034_stage033_remaining_negative_precursor.md"
    lines = [
        "# Stage034 - Stage033 剩余负窗口前置信号归因",
        "",
        f"- 记录时间：`{timestamp.isoformat(timespec='minutes')}`",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        "- 是否重要突破版本：`否`",
        f"- 决策：`{decision['decision']}`",
        "",
        "## 本次版本变更",
        "",
        "- 新增工具：`research/lines/futures_trend_rebuilt_c9_15w_optimization/tools/stage034_stage033_remaining_negative_precursor.py`。",
        "- 使用 Stage033 proxy 曲线，将 `2020-01-01` 到 `2025-06-30` 每个可审计起点压成一行，标记未来任意 `>365` 天结束是否出现负收益。",
        "- 合并当时可见的账户状态、市场 regime、AI 月度信心/共识度；不使用未来 PnL 或事后标签作为条件。",
        "",
        "## 新增参数",
        "",
        "- `OBJECTIVE_START_MIN=2020-01-01`",
        "- `OBJECTIVE_START_MAX=2025-06-30`",
        "- `MIN_PERIOD_DAYS=365`",
        "",
        "## 结果",
        "",
        f"- 可审计起点行：`{decision['start_row_count']}`。",
        f"- 严格负起点数：`{decision['strict_negative_start_count']}`。",
        f"- 严格负起点率：`{decision['strict_negative_start_rate_pct']:.4f}%`。",
        f"- 最差未来任意 `>1` 年收益：`{decision['min_future_return_pct']:.4f}%`。",
        f"- 最强条件：`{decision['top_condition']}`，负起点率 `{decision['top_condition_negative_rate_pct']:.4f}%`，lift `{decision['top_condition_lift']:.4f}`，样本 `{decision['top_condition_count']}`。",
        f"- 最强分桶：`{decision['top_bucket_feature']}={decision['top_bucket_value']}`，负起点率 `{decision['top_bucket_negative_rate_pct']:.4f}%`，lift `{decision['top_bucket_lift']:.4f}`，样本 `{decision['top_bucket_count']}`。",
        "",
        "## 调研与判断结论",
        "",
        "- 调研结论：趋势跟随稳健性更依赖市场组合、horizon 和风险预算，而不是单一固定加仓标签；因此本阶段做 causal precursor 审计。",
        f"- 判断结论：`{decision['decision']}`。当前只读归因不能声明目标达成，也不能直接上线。",
        "",
        "## 反思",
        "",
        f"- 运行前是否过拟合：{decision['overfit_reflection_before']}",
        f"- 运行前是否有价值继续：{decision['continue_value_before']}",
        f"- 运行后是否过拟合：{decision['overfit_reflection_after']}",
        f"- 运行后是否有价值继续：{decision['continue_value_after']}",
        "",
        "## 后续规划和 TODO",
        "",
        "- 若前兆具备足够样本和跨 source 稳定性，下一阶段只能做冻结真实引擎验证，不能微调年份/source/阈值。",
        "- 若前兆不稳定，转外生信息源或账户外层资金安排。",
        "",
        "## 输出文件",
        "",
    ]
    for key, path in decision["outputs"].items():
        lines.append(f"- {key}: `{path}`")
    record_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return record_path


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STAGE_RECORD_DIR.mkdir(parents=True, exist_ok=True)
    curves = _read_stage033_curves()
    outcomes = _start_outcomes(curves)
    market_daily = pd.read_csv(MARKET_DAILY_PATH, encoding="utf-8-sig", parse_dates=["date"])
    ai_monthly = _ai_monthly_summary()
    features = _feature_matrix(curves, outcomes, market_daily, ai_monthly)
    bucket_summary = _bucket_summary(features)
    condition_summary = _condition_summary(features)
    stability_summary = _stability_summary(features)
    _plot(condition_summary, bucket_summary)

    decision = _decision(outcomes, condition_summary, bucket_summary)
    outcomes.to_csv(START_OUTCOMES_PATH, index=False, encoding="utf-8-sig")
    features.to_csv(FEATURE_MATRIX_PATH, index=False, encoding="utf-8-sig")
    bucket_summary.to_csv(BUCKET_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    condition_summary.to_csv(CONDITION_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    stability_summary.to_csv(STABILITY_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(decision, condition_summary, bucket_summary, stability_summary)
    stage_record = _write_stage_record(decision)
    decision["stage_record"] = str(stage_record)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
