from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage017"
MODEL_TAG = "stage017_external_regime_volatility_attribution_v1"
OUTPUT_PREFIX = "rebuilt_c9_stage017_external_regime_volatility_attribution"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage017_external_regime_volatility_attribution"
STAGE013_OUTPUT_DIR = LINE_DIR / "outputs" / "stage013_account_state_pilot_gate_engine"
STAGE015_OUTPUT_DIR = LINE_DIR / "outputs" / "stage015_pilot_confirmation_jd_feasibility"
BACKTEST_OUTPUT_DIR = PROJECT_DIR / "examples" / "portfolio_backtesting" / "backtest_outputs"

STAGE013_PREFIX = "rebuilt_c9_stage013_account_state_pilot_gate_engine"
STAGE013_TAG = "stage013_account_state_pilot_gate_engine_v1"
CURVES_PATH = STAGE013_OUTPUT_DIR / f"{STAGE013_PREFIX}_curves_{STAGE013_TAG}.csv"
WORST_WINDOWS_PATH = STAGE013_OUTPUT_DIR / f"{STAGE013_PREFIX}_goal_worst_windows_{STAGE013_TAG}.csv"
STAGE015_CLOSED_LOTS_PATH = (
    STAGE015_OUTPUT_DIR
    / "rebuilt_c9_stage015_pilot_confirmation_jd_feasibility_closed_lots_stage015_pilot_confirmation_jd_feasibility_v1.csv"
)

MARKET_DAILY_PATH = (
    BACKTEST_OUTPUT_DIR
    / "qmt_roll_ai_product_suitability_market_walkforward_market_daily_product_suitability_market_wf_v2.csv"
)
FULL_MARKET_PREDICTIONS_PATH = (
    BACKTEST_OUTPUT_DIR
    / "qmt_roll_ai_product_suitability_full_market_walkforward_predictions_product_suitability_full_market_wf_v1.csv"
)

MARKET_DAILY_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_market_daily_summary_{MODEL_TAG}.csv"
DAILY_FORWARD_REGIME_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_forward_regime_summary_{MODEL_TAG}.csv"
WORST_WINDOW_REGIME_DETAIL_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_worst_window_regime_detail_{MODEL_TAG}.csv"
WORST_WINDOW_REGIME_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_worst_window_regime_summary_{MODEL_TAG}.csv"
ENTRY_REGIME_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_regime_summary_{MODEL_TAG}.csv"
AI_MONTHLY_REGIME_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_ai_monthly_regime_summary_{MODEL_TAG}.csv"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

GOAL_SOURCE_START = pd.Timestamp("2020-01-01")
FOCUS_START = pd.Timestamp("2022-01-01")
FOCUS_END = pd.Timestamp("2023-12-31")
FORWARD_HORIZONS = (63, 126, 252, 366)
WORST_PATH_WINDOWS = (21, 63, 126, 252)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        number = float(value)
        return None if np.isnan(number) or np.isinf(number) else number
    if not isinstance(value, (str, bytes)) and pd.isna(value):
        return None
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_空_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    return data.to_markdown(index=False)


def _product_key(value: Any) -> str:
    return str(value or "").strip().lower()


def _quantile_bucket(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    valid = numeric.dropna()
    if valid.empty:
        return pd.Series("missing", index=series.index)
    low = float(valid.quantile(0.33))
    high = float(valid.quantile(0.67))
    result = pd.Series("mid", index=series.index)
    result[numeric.isna()] = "missing"
    result[numeric <= low] = "low"
    result[numeric >= high] = "high"
    return result


def _breadth_bucket(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    result = pd.Series("breadth_mid", index=series.index)
    result[numeric.isna()] = "missing"
    result[numeric <= 0.33] = "breadth_low"
    result[numeric >= 0.67] = "breadth_high"
    return result


def _extreme_bucket(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    result = pd.Series("extreme_mid", index=series.index)
    result[numeric.isna()] = "missing"
    result[numeric <= 0.33] = "extreme_low"
    result[numeric >= 0.50] = "extreme_high"
    return result


def _joint_regime(vol_bucket: pd.Series, trend_bucket: pd.Series, breadth_bucket: pd.Series) -> pd.Series:
    regime = pd.Series("neutral", index=vol_bucket.index)
    regime[(breadth_bucket == "breadth_high") & (trend_bucket != "low")] = "broad_trend"
    regime[(breadth_bucket == "breadth_low") & (trend_bucket == "low")] = "narrow_chop"
    regime[(vol_bucket == "low") & (trend_bucket == "low")] = "quiet_low_eff"
    regime[(trend_bucket == "high") & (vol_bucket != "high")] = "trend_clean"
    regime[(trend_bucket == "high") & (vol_bucket == "high")] = "high_vol_high_eff"
    regime[(vol_bucket == "high") & (trend_bucket == "low")] = "high_vol_low_eff"
    regime[(vol_bucket == "missing") | (trend_bucket == "missing") | (breadth_bucket == "missing")] = "missing"
    return regime


def _read_market_daily() -> tuple[pd.DataFrame, pd.DataFrame]:
    usecols = [
        "date",
        "product_vt_symbol",
        "market_realized_vol_60d",
        "market_trend_efficiency_60d",
        "market_close_position_60d",
        "market_breakout_rate_60d",
        "market_ma20_over_ma60_60d",
        "market_ret_60d",
        "market_range_pct_mean_60d",
    ]
    product_daily = pd.read_csv(MARKET_DAILY_PATH, encoding="utf-8-sig", usecols=usecols, parse_dates=["date"])
    product_daily["date"] = product_daily["date"].dt.normalize()
    product_daily["product_key"] = product_daily["product_vt_symbol"].map(_product_key)
    numeric_cols = [column for column in usecols if column not in {"date", "product_vt_symbol"}]
    for column in numeric_cols:
        product_daily[column] = pd.to_numeric(product_daily[column], errors="coerce")

    product_daily["product_vol60_bucket"] = _quantile_bucket(product_daily["market_realized_vol_60d"])
    product_daily["product_trend_eff60_bucket"] = _quantile_bucket(product_daily["market_trend_efficiency_60d"])
    product_daily["product_close_position_extreme"] = product_daily["market_close_position_60d"].between(
        0.0, 0.2, inclusive="both"
    ) | product_daily["market_close_position_60d"].between(0.8, 1.0, inclusive="both")
    product_daily["product_breadth_bucket"] = np.where(
        product_daily["market_ma20_over_ma60_60d"].gt(0.0), "ma20_over_ma60", "ma20_not_over_ma60"
    )
    product_daily["product_joint_regime"] = _joint_regime(
        product_daily["product_vol60_bucket"],
        product_daily["product_trend_eff60_bucket"],
        pd.Series(
            np.where(product_daily["market_ma20_over_ma60_60d"].gt(0.0), "breadth_high", "breadth_low"),
            index=product_daily.index,
        ),
    )

    daily = (
        product_daily.groupby("date", dropna=False)
        .agg(
            product_count=("product_vt_symbol", "nunique"),
            median_realized_vol_60d=("market_realized_vol_60d", "median"),
            mean_realized_vol_60d=("market_realized_vol_60d", "mean"),
            p75_realized_vol_60d=("market_realized_vol_60d", lambda value: float(value.quantile(0.75))),
            median_trend_efficiency_60d=("market_trend_efficiency_60d", "median"),
            mean_trend_efficiency_60d=("market_trend_efficiency_60d", "mean"),
            median_close_position_60d=("market_close_position_60d", "median"),
            close_extreme_share=("product_close_position_extreme", "mean"),
            breakout_share_60d=("market_breakout_rate_60d", "mean"),
            ma20_over_ma60_share_60d=("market_ma20_over_ma60_60d", lambda value: float(value.gt(0.0).mean())),
            median_ret_60d=("market_ret_60d", "median"),
            cross_section_ret60_dispersion=("market_ret_60d", "std"),
            median_range_pct_mean_60d=("market_range_pct_mean_60d", "median"),
        )
        .reset_index()
        .sort_values("date")
    )
    daily["vol60_bucket"] = _quantile_bucket(daily["median_realized_vol_60d"])
    daily["trend_eff60_bucket"] = _quantile_bucket(daily["median_trend_efficiency_60d"])
    daily["trend_breadth_bucket"] = _breadth_bucket(daily["ma20_over_ma60_share_60d"])
    daily["close_extreme_bucket"] = _extreme_bucket(daily["close_extreme_share"])
    daily["joint_regime"] = _joint_regime(
        daily["vol60_bucket"], daily["trend_eff60_bucket"], daily["trend_breadth_bucket"]
    )
    daily["regime_source"] = "qmt_roll_ai_product_suitability_market_walkforward_market_daily_v2"
    return product_daily, daily


def _read_curves() -> pd.DataFrame:
    usecols = [
        "requested_start_month",
        "date",
        "account_equity",
        "broker10_margin_to_equity_pct",
        "drawdown_pct",
        "c3_active_products",
        "c3_active_contracts",
        "net_pnl",
        "trade_count",
    ]
    curves = pd.read_csv(CURVES_PATH, encoding="utf-8-sig", usecols=usecols, parse_dates=["date"])
    curves["date"] = curves["date"].dt.normalize()
    curves["requested_start_month"] = curves["requested_start_month"].astype(str)
    curves["source_start_ts"] = pd.to_datetime(curves["requested_start_month"] + "-01", errors="coerce")
    for column in usecols:
        if column not in {"requested_start_month", "date"}:
            curves[column] = pd.to_numeric(curves[column], errors="coerce")
    curves = curves[curves["source_start_ts"].ge(GOAL_SOURCE_START)].copy()
    curves = curves.sort_values(["requested_start_month", "date"]).reset_index(drop=True)
    return curves


def _add_forward_returns(curves: pd.DataFrame) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for _, group in curves.groupby("requested_start_month", sort=True):
        current = group.sort_values("date").reset_index(drop=True).copy()
        equity = current["account_equity"].to_numpy(dtype=float)
        for horizon in FORWARD_HORIZONS:
            future = np.full(len(current), np.nan)
            if len(current) > horizon:
                future[:-horizon] = (equity[horizon:] / equity[:-horizon] - 1.0) * 100.0
            current[f"fwd_{horizon}d_return_pct"] = future
        frames.append(current)
    return pd.concat(frames, ignore_index=True, sort=False)


def _summarize_forward_by_regime(curves: pd.DataFrame, market_daily: pd.DataFrame) -> pd.DataFrame:
    data = _add_forward_returns(curves).merge(market_daily, on="date", how="inner")
    features = [
        "joint_regime",
        "vol60_bucket",
        "trend_eff60_bucket",
        "trend_breadth_bucket",
        "close_extreme_bucket",
    ]
    conditions = {
        "all_market_days": lambda df: pd.Series(True, index=df.index),
        "high_vol_low_eff": lambda df: df["joint_regime"].eq("high_vol_low_eff"),
        "trend_clean": lambda df: df["joint_regime"].eq("trend_clean"),
        "broad_trend": lambda df: df["joint_regime"].eq("broad_trend"),
        "narrow_chop": lambda df: df["joint_regime"].eq("narrow_chop"),
        "vol_high": lambda df: df["vol60_bucket"].eq("high"),
        "vol_low": lambda df: df["vol60_bucket"].eq("low"),
        "eff_low": lambda df: df["trend_eff60_bucket"].eq("low"),
        "eff_high": lambda df: df["trend_eff60_bucket"].eq("high"),
        "breadth_high": lambda df: df["trend_breadth_bucket"].eq("breadth_high"),
        "breadth_low": lambda df: df["trend_breadth_bucket"].eq("breadth_low"),
        "close_extreme_high": lambda df: df["close_extreme_bucket"].eq("extreme_high"),
    }
    rows: list[dict[str, Any]] = []
    for horizon in FORWARD_HORIZONS:
        ret_col = f"fwd_{horizon}d_return_pct"
        scoped = data.dropna(subset=[ret_col]).copy()
        for feature in features:
            for value, group in scoped.groupby(feature, dropna=False):
                ret = pd.to_numeric(group[ret_col], errors="coerce")
                rows.append(
                    {
                        "summary_type": "feature_bucket",
                        "feature": feature,
                        "feature_value": str(value),
                        "horizon_trading_days": horizon,
                        "count": int(len(group)),
                        "source_start_count": int(group["requested_start_month"].nunique()),
                        "date_count": int(group["date"].nunique()),
                        "negative_rate_pct": float(ret.lt(0).mean() * 100.0),
                        "min_return_pct": float(ret.min()),
                        "p10_return_pct": float(ret.quantile(0.10)),
                        "median_return_pct": float(ret.median()),
                        "mean_return_pct": float(ret.mean()),
                        "p90_return_pct": float(ret.quantile(0.90)),
                        "median_broker10_pct": float(group["broker10_margin_to_equity_pct"].median()),
                        "median_drawdown_pct": float(group["drawdown_pct"].median()),
                        "median_active_products": float(group["c3_active_products"].median()),
                        "median_market_vol60": float(group["median_realized_vol_60d"].median()),
                        "median_market_eff60": float(group["median_trend_efficiency_60d"].median()),
                    }
                )
        for name, maker in conditions.items():
            group = scoped[maker(scoped).fillna(False).astype(bool)].copy()
            if group.empty:
                continue
            ret = pd.to_numeric(group[ret_col], errors="coerce")
            rows.append(
                {
                    "summary_type": "condition",
                    "feature": "condition",
                    "feature_value": name,
                    "horizon_trading_days": horizon,
                    "count": int(len(group)),
                    "source_start_count": int(group["requested_start_month"].nunique()),
                    "date_count": int(group["date"].nunique()),
                    "negative_rate_pct": float(ret.lt(0).mean() * 100.0),
                    "min_return_pct": float(ret.min()),
                    "p10_return_pct": float(ret.quantile(0.10)),
                    "median_return_pct": float(ret.median()),
                    "mean_return_pct": float(ret.mean()),
                    "p90_return_pct": float(ret.quantile(0.90)),
                    "median_broker10_pct": float(group["broker10_margin_to_equity_pct"].median()),
                    "median_drawdown_pct": float(group["drawdown_pct"].median()),
                    "median_active_products": float(group["c3_active_products"].median()),
                    "median_market_vol60": float(group["median_realized_vol_60d"].median()),
                    "median_market_eff60": float(group["median_trend_efficiency_60d"].median()),
                }
            )
    return pd.DataFrame(rows).sort_values(
        ["horizon_trading_days", "summary_type", "feature", "negative_rate_pct"],
        ascending=[True, True, True, False],
    )


def _worst_window_regime_path(curves: pd.DataFrame, market_daily: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    worst = pd.read_csv(WORST_WINDOWS_PATH, encoding="utf-8-sig", parse_dates=["start_date", "end_date"]).head(100)
    worst["source_start_month"] = worst["source_start_month"].astype(str)
    rows: list[dict[str, Any]] = []
    joined = curves.merge(market_daily, on="date", how="inner")
    for window_id, item in enumerate(worst.itertuples(index=False), start=1):
        group = joined[
            (joined["requested_start_month"].eq(str(item.source_start_month)))
            & (joined["date"].ge(item.start_date))
            & (joined["date"].le(item.end_date))
        ].sort_values("date")
        if group.empty:
            continue
        for first_n in WORST_PATH_WINDOWS:
            segment = group.head(first_n)
            if segment.empty:
                continue
            rows.append(
                {
                    "window_id": window_id,
                    "source_start_month": item.source_start_month,
                    "window_start_date": item.start_date,
                    "window_end_date": item.end_date,
                    "return_pct": float(item.return_pct),
                    "first_trading_days": first_n,
                    "segment_days": int(len(segment)),
                    "high_vol_low_eff_day_rate_pct": float(
                        segment["joint_regime"].eq("high_vol_low_eff").mean() * 100.0
                    ),
                    "trend_clean_day_rate_pct": float(segment["joint_regime"].eq("trend_clean").mean() * 100.0),
                    "broad_trend_day_rate_pct": float(segment["joint_regime"].eq("broad_trend").mean() * 100.0),
                    "narrow_chop_day_rate_pct": float(segment["joint_regime"].eq("narrow_chop").mean() * 100.0),
                    "median_market_vol60": float(segment["median_realized_vol_60d"].median()),
                    "median_market_eff60": float(segment["median_trend_efficiency_60d"].median()),
                    "median_breadth_share": float(segment["ma20_over_ma60_share_60d"].median()),
                    "median_close_extreme_share": float(segment["close_extreme_share"].median()),
                    "median_broker10_pct": float(segment["broker10_margin_to_equity_pct"].median()),
                    "min_drawdown_pct": float(segment["drawdown_pct"].min()),
                    "max_active_products": float(segment["c3_active_products"].max()),
                    "sum_net_pnl": float(segment["net_pnl"].sum()),
                }
            )
    detail = pd.DataFrame(rows)
    if detail.empty:
        return detail, pd.DataFrame()
    summary = (
        detail.groupby("first_trading_days", dropna=False)
        .agg(
            window_count=("window_id", "count"),
            median_high_vol_low_eff_day_rate_pct=("high_vol_low_eff_day_rate_pct", "median"),
            median_trend_clean_day_rate_pct=("trend_clean_day_rate_pct", "median"),
            median_broad_trend_day_rate_pct=("broad_trend_day_rate_pct", "median"),
            median_narrow_chop_day_rate_pct=("narrow_chop_day_rate_pct", "median"),
            median_market_vol60=("median_market_vol60", "median"),
            median_market_eff60=("median_market_eff60", "median"),
            median_breadth_share=("median_breadth_share", "median"),
            median_close_extreme_share=("median_close_extreme_share", "median"),
            median_broker10_pct=("median_broker10_pct", "median"),
            median_min_drawdown_pct=("min_drawdown_pct", "median"),
            median_max_active_products=("max_active_products", "median"),
            median_sum_net_pnl=("sum_net_pnl", "median"),
        )
        .reset_index()
    )
    return detail, summary


def _read_closed_lots_with_regime(product_daily: pd.DataFrame, market_daily: pd.DataFrame) -> pd.DataFrame:
    data = pd.read_csv(STAGE015_CLOSED_LOTS_PATH, encoding="utf-8-sig", parse_dates=["entry_date", "exit_date"])
    data["entry_date"] = data["entry_date"].dt.normalize()
    data["requested_start_month"] = data["requested_start_month"].astype(str)
    data["source_start_ts"] = pd.to_datetime(data["requested_start_month"] + "-01", errors="coerce")
    data["product_key"] = data["product"].map(_product_key)
    numeric_cols = [
        "realized_pnl",
        "r_multiple",
        "selected_volume",
        "ai_product_pool_rank",
        "ai_product_pool_score",
        "portfolio_drawdown_pct",
        "same_direction_correlation_max_corr",
    ]
    for column in numeric_cols:
        data[column] = pd.to_numeric(data.get(column), errors="coerce")
    product_cols = [
        "date",
        "product_key",
        "market_realized_vol_60d",
        "market_trend_efficiency_60d",
        "market_close_position_60d",
        "market_ret_60d",
        "product_vol60_bucket",
        "product_trend_eff60_bucket",
        "product_joint_regime",
        "product_close_position_extreme",
    ]
    daily_cols = [
        "date",
        "joint_regime",
        "vol60_bucket",
        "trend_eff60_bucket",
        "trend_breadth_bucket",
        "close_extreme_bucket",
        "median_realized_vol_60d",
        "median_trend_efficiency_60d",
        "ma20_over_ma60_share_60d",
    ]
    data = data.merge(
        product_daily[product_cols].rename(columns={"date": "entry_date"}),
        on=["entry_date", "product_key"],
        how="left",
    )
    data = data.merge(
        market_daily[daily_cols].rename(columns={"date": "entry_date"}),
        on="entry_date",
        how="left",
        suffixes=("_product", "_market"),
    )
    return data


def _entry_regime_summary(data: pd.DataFrame) -> pd.DataFrame:
    scoped_masks = {
        "goal_sources_2020plus": data["source_start_ts"].ge(GOAL_SOURCE_START),
        "focus_2022_2023_entries": data["entry_date"].between(FOCUS_START, FOCUS_END, inclusive="both"),
        "all_matched_entries": data["joint_regime"].notna(),
    }
    feature_cols = [
        "joint_regime",
        "vol60_bucket",
        "trend_eff60_bucket",
        "trend_breadth_bucket",
        "product_joint_regime",
        "product_vol60_bucket",
        "product_trend_eff60_bucket",
    ]
    rows: list[dict[str, Any]] = []
    for scope_name, scope_mask in scoped_masks.items():
        scoped = data[scope_mask.fillna(False).astype(bool)].copy()
        for feature in feature_cols:
            if feature not in scoped.columns:
                continue
            for value, group in scoped.groupby(feature, dropna=False):
                if len(group) < 5:
                    continue
                pnl = pd.to_numeric(group["realized_pnl"], errors="coerce")
                r_mult = pd.to_numeric(group["r_multiple"], errors="coerce")
                rows.append(
                    {
                        "scope": scope_name,
                        "feature": feature,
                        "feature_value": str(value),
                        "count": int(len(group)),
                        "product_count": int(group["product"].nunique()),
                        "entry_year_count": int(group["entry_date"].dt.year.nunique()),
                        "win_rate_pct": float(pnl.gt(0).mean() * 100.0),
                        "total_pnl": float(pnl.sum()),
                        "mean_pnl": float(pnl.mean()),
                        "avg_r": float(r_mult.mean()),
                        "median_r": float(r_mult.median()),
                        "p10_r": float(r_mult.quantile(0.10)),
                        "p90_r": float(r_mult.quantile(0.90)),
                        "selected_volume_sum": float(
                            pd.to_numeric(group["selected_volume"], errors="coerce").fillna(0.0).sum()
                        ),
                        "median_ai_rank": float(
                            pd.to_numeric(group["ai_product_pool_rank"], errors="coerce").median()
                        ),
                        "median_drawdown_pct": float(
                            pd.to_numeric(group["portfolio_drawdown_pct"], errors="coerce").median()
                        ),
                    }
                )
    return pd.DataFrame(rows).sort_values(["scope", "feature", "total_pnl"], ascending=[True, True, True])


def _ai_monthly_regime_summary() -> pd.DataFrame:
    usecols = [
        "eval_date",
        "product_vt_symbol",
        "predicted_product_suitability_probability",
        "simple_trend_suitability_score",
        "future_net_pnl_60d",
        "future_rank_pct_60d",
        "target_future_top_half_60d",
        "market_realized_vol_60d",
        "market_trend_efficiency_60d",
        "market_close_position_60d",
        "market_breakout_rate_60d",
        "market_ma20_over_ma60_60d",
    ]
    data = pd.read_csv(FULL_MARKET_PREDICTIONS_PATH, encoding="utf-8-sig", usecols=usecols, parse_dates=["eval_date"])
    data["eval_date"] = data["eval_date"].dt.normalize()
    numeric_cols = [column for column in usecols if column not in {"eval_date", "product_vt_symbol"}]
    for column in numeric_cols:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    data["ai_rank"] = (
        data.groupby("eval_date")["predicted_product_suitability_probability"]
        .rank(method="first", ascending=False)
        .astype(int)
    )
    data["ai_top8"] = data["ai_rank"].le(8)
    data["product_vol60_bucket"] = _quantile_bucket(data["market_realized_vol_60d"])
    data["product_trend_eff60_bucket"] = _quantile_bucket(data["market_trend_efficiency_60d"])
    data["product_breadth_bucket"] = np.where(
        data["market_ma20_over_ma60_60d"].gt(0.0), "ma20_over_ma60", "ma20_not_over_ma60"
    )
    data["product_joint_regime"] = _joint_regime(
        data["product_vol60_bucket"],
        data["product_trend_eff60_bucket"],
        pd.Series(
            np.where(data["market_ma20_over_ma60_60d"].gt(0.0), "breadth_high", "breadth_low"),
            index=data.index,
        ),
    )
    data["eval_scope_focus_2022_2023"] = data["eval_date"].between(FOCUS_START, FOCUS_END, inclusive="both")
    feature_cols = [
        "product_joint_regime",
        "product_vol60_bucket",
        "product_trend_eff60_bucket",
        "product_breadth_bucket",
    ]
    rows: list[dict[str, Any]] = []
    for scope_name, scope_mask in {
        "all_eval_months": pd.Series(True, index=data.index),
        "focus_2022_2023_eval_months": data["eval_scope_focus_2022_2023"].fillna(False),
    }.items():
        scoped = data[scope_mask.astype(bool)].copy()
        for top_scope, top_mask in {
            "all_products": pd.Series(True, index=scoped.index),
            "ai_top8": scoped["ai_top8"].fillna(False),
            "ai_rank_9_16": scoped["ai_rank"].between(9, 16, inclusive="both"),
        }.items():
            top_scoped = scoped[top_mask.astype(bool)].copy()
            for feature in feature_cols:
                for value, group in top_scoped.groupby(feature, dropna=False):
                    if len(group) < 5:
                        continue
                    future = pd.to_numeric(group["future_net_pnl_60d"], errors="coerce")
                    rows.append(
                        {
                            "scope": scope_name,
                            "top_scope": top_scope,
                            "feature": feature,
                            "feature_value": str(value),
                            "count": int(len(group)),
                            "eval_month_count": int(group["eval_date"].nunique()),
                            "product_count": int(group["product_vt_symbol"].nunique()),
                            "mean_future_net_pnl_60d": float(future.mean()),
                            "median_future_net_pnl_60d": float(future.median()),
                            "p10_future_net_pnl_60d": float(future.quantile(0.10)),
                            "p90_future_net_pnl_60d": float(future.quantile(0.90)),
                            "future_top_half_rate_pct": float(
                                pd.to_numeric(group["target_future_top_half_60d"], errors="coerce")
                                .fillna(0)
                                .astype(int)
                                .mean()
                                * 100.0
                            ),
                            "mean_predicted_probability": float(
                                group["predicted_product_suitability_probability"].mean()
                            ),
                            "median_ai_rank": float(group["ai_rank"].median()),
                        }
                    )
    return pd.DataFrame(rows).sort_values(
        ["scope", "top_scope", "feature", "mean_future_net_pnl_60d"],
        ascending=[True, True, True, True],
    )


def _row(frame: pd.DataFrame, **filters: Any) -> dict[str, Any]:
    if frame.empty:
        return {}
    mask = pd.Series(True, index=frame.index)
    for column, value in filters.items():
        mask &= frame[column].eq(value)
    matched = frame[mask]
    return matched.to_dict("records")[0] if not matched.empty else {}


def _plot(
    daily_forward: pd.DataFrame,
    worst_summary: pd.DataFrame,
    entry_summary: pd.DataFrame,
    ai_summary: pd.DataFrame,
) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(17, 10), dpi=160)
    ax_daily, ax_worst, ax_entry, ax_ai = axes.flatten()

    daily = daily_forward[
        daily_forward["summary_type"].eq("feature_bucket")
        & daily_forward["feature"].eq("joint_regime")
        & daily_forward["horizon_trading_days"].eq(252)
    ].copy()
    if not daily.empty:
        daily = daily.sort_values("negative_rate_pct")
        ax_daily.barh(daily["feature_value"], daily["negative_rate_pct"], color="#2563eb", alpha=0.85)
        ax_daily.set_title("Next 252 trading-day negative rate by market regime")
        ax_daily.set_xlabel("negative rate %")
        ax_daily.grid(axis="x", alpha=0.25)

    if not worst_summary.empty:
        ax_worst.plot(
            worst_summary["first_trading_days"],
            worst_summary["median_high_vol_low_eff_day_rate_pct"],
            marker="o",
            color="#dc2626",
            label="high vol / low efficiency day rate",
        )
        ax_worst.plot(
            worst_summary["first_trading_days"],
            worst_summary["median_trend_clean_day_rate_pct"],
            marker="o",
            color="#059669",
            label="trend clean day rate",
        )
        ax_worst.set_title("Top100 worst windows: regime mix in first N days")
        ax_worst.set_xlabel("first N trading days")
        ax_worst.set_ylabel("median day rate %")
        ax_worst.legend()
        ax_worst.grid(alpha=0.25)

    entry = entry_summary[
        entry_summary["scope"].eq("focus_2022_2023_entries") & entry_summary["feature"].eq("joint_regime")
    ].copy()
    if not entry.empty:
        entry = entry.sort_values("total_pnl")
        ax_entry.barh(entry["feature_value"], entry["total_pnl"], color="#f97316", alpha=0.85)
        ax_entry.axvline(0.0, color="#111827", linewidth=0.8)
        ax_entry.set_title("Focus 2022-2023 entry PnL by market regime")
        ax_entry.grid(axis="x", alpha=0.25)

    ai = ai_summary[
        ai_summary["scope"].eq("focus_2022_2023_eval_months")
        & ai_summary["top_scope"].eq("ai_top8")
        & ai_summary["feature"].eq("product_joint_regime")
    ].copy()
    if not ai.empty:
        ai = ai.sort_values("mean_future_net_pnl_60d")
        ax_ai.barh(ai["feature_value"], ai["mean_future_net_pnl_60d"], color="#7c3aed", alpha=0.85)
        ax_ai.axvline(0.0, color="#111827", linewidth=0.8)
        ax_ai.set_title("AI top8 future 60d PnL by product regime")
        ax_ai.grid(axis="x", alpha=0.25)

    fig.suptitle("Stage017 External Regime / Volatility Attribution", fontsize=14)
    fig.tight_layout()
    fig.savefig(CHART_PATH)
    plt.close(fig)


def _decision(
    market_daily: pd.DataFrame,
    daily_forward: pd.DataFrame,
    worst_summary: pd.DataFrame,
    entry_summary: pd.DataFrame,
    ai_summary: pd.DataFrame,
) -> dict[str, Any]:
    all_252 = _row(
        daily_forward,
        summary_type="condition",
        feature="condition",
        feature_value="all_market_days",
        horizon_trading_days=252,
    )
    high_vol_low_eff_252 = _row(
        daily_forward,
        summary_type="condition",
        feature="condition",
        feature_value="high_vol_low_eff",
        horizon_trading_days=252,
    )
    trend_clean_252 = _row(
        daily_forward,
        summary_type="condition",
        feature="condition",
        feature_value="trend_clean",
        horizon_trading_days=252,
    )
    entry_focus_high_vol_low_eff = _row(
        entry_summary,
        scope="focus_2022_2023_entries",
        feature="joint_regime",
        feature_value="high_vol_low_eff",
    )
    entry_focus_trend_clean = _row(
        entry_summary,
        scope="focus_2022_2023_entries",
        feature="joint_regime",
        feature_value="trend_clean",
    )
    ai_focus_top8_high_vol_low_eff = _row(
        ai_summary,
        scope="focus_2022_2023_eval_months",
        top_scope="ai_top8",
        feature="product_joint_regime",
        feature_value="high_vol_low_eff",
    )
    ai_focus_top8_trend_clean = _row(
        ai_summary,
        scope="focus_2022_2023_eval_months",
        top_scope="ai_top8",
        feature="product_joint_regime",
        feature_value="trend_clean",
    )
    worst_63 = (
        worst_summary[worst_summary["first_trading_days"].eq(63)].to_dict("records")[0]
        if not worst_summary.empty and worst_summary["first_trading_days"].eq(63).any()
        else {}
    )

    all_neg = float(all_252.get("negative_rate_pct") or 0.0)
    hvle_neg = float(high_vol_low_eff_252.get("negative_rate_pct") or 0.0)
    hvle_entry_pnl = float(entry_focus_high_vol_low_eff.get("total_pnl") or 0.0)
    hvle_ai_mean = float(ai_focus_top8_high_vol_low_eff.get("mean_future_net_pnl_60d") or 0.0)
    if hvle_neg >= all_neg + 5.0 and hvle_entry_pnl < 0 and hvle_ai_mean < 0:
        decision = "stage017_regime_signal_has_engine_test_value"
        next_step = (
            "Write one frozen Stage018 true-engine test that only uses pre-entry market state: high-vol/low-efficiency "
            "risk release throttle or AI top8 demotion. Do not scan thresholds."
        )
    else:
        decision = "stage017_regime_signal_not_yet_engine_ready"
        next_step = (
            "Keep as attribution. If continuing, deepen with raw continuous-market correlation/breadth or a single "
            "predeclared Stage018 proxy before writing an engine."
        )

    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "stage_nature": "readonly_external_regime_volatility_attribution_no_strategy_change",
        "decision": decision,
        "strategy_changed": False,
        "official_live_strategy_changed": False,
        "market_daily_date_min": market_daily["date"].min(),
        "market_daily_date_max": market_daily["date"].max(),
        "market_daily_product_count_median": float(market_daily["product_count"].median()),
        "all_market_days_next252": all_252,
        "high_vol_low_eff_next252": high_vol_low_eff_252,
        "trend_clean_next252": trend_clean_252,
        "worst_top100_first63_regime": worst_63,
        "entry_focus_high_vol_low_eff": entry_focus_high_vol_low_eff,
        "entry_focus_trend_clean": entry_focus_trend_clean,
        "ai_focus_top8_high_vol_low_eff": ai_focus_top8_high_vol_low_eff,
        "ai_focus_top8_trend_clean": ai_focus_top8_trend_clean,
        "judgment": (
            "This stage uses already materialized market state features from the rebuilt AI data pipeline. It tests "
            "low-degree volatility/trend-efficiency/breadth labels only, so it is attribution evidence rather than a "
            "new trading rule."
        ),
        "next_step": next_step,
        "output_files": {
            "market_daily_summary": str(MARKET_DAILY_SUMMARY_PATH),
            "daily_forward_regime_summary": str(DAILY_FORWARD_REGIME_SUMMARY_PATH),
            "worst_window_regime_detail": str(WORST_WINDOW_REGIME_DETAIL_PATH),
            "worst_window_regime_summary": str(WORST_WINDOW_REGIME_SUMMARY_PATH),
            "entry_regime_summary": str(ENTRY_REGIME_SUMMARY_PATH),
            "ai_monthly_regime_summary": str(AI_MONTHLY_REGIME_SUMMARY_PATH),
            "chart": str(CHART_PATH),
            "report": str(REPORT_PATH),
        },
    }


def _write_report(
    market_daily: pd.DataFrame,
    daily_forward: pd.DataFrame,
    worst_summary: pd.DataFrame,
    entry_summary: pd.DataFrame,
    ai_summary: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    daily_focus = daily_forward[
        daily_forward["horizon_trading_days"].isin([252, 366])
        & (
            daily_forward["feature"].eq("condition")
            | daily_forward["feature"].isin(["joint_regime", "trend_eff60_bucket", "vol60_bucket"])
        )
    ].copy()
    entry_focus = entry_summary[
        entry_summary["scope"].eq("focus_2022_2023_entries")
        & entry_summary["feature"].isin(["joint_regime", "product_joint_regime"])
    ].copy()
    ai_focus = ai_summary[
        ai_summary["scope"].eq("focus_2022_2023_eval_months")
        & ai_summary["top_scope"].eq("ai_top8")
        & ai_summary["feature"].eq("product_joint_regime")
    ].copy()

    lines = [
        "# Stage017 External Regime / Volatility Attribution",
        "",
        f"- 记录时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        "- 阶段性质：只读外生/市场状态归因；不改策略、不连接 CTP、不调用下单 API。",
        f"- 决策：`{decision['decision']}`",
        "- 数据源：Stage013 曲线、Stage015 closed lots、AI product suitability market daily v2、full-market monthly predictions v1。",
        "",
        "## 核心判断",
        "",
        "- 本阶段使用的是当前重建数据管线已经物化的市场状态特征，不新引入供应链：`realized_vol_60d`、`trend_efficiency_60d`、`ma20_over_ma60` 广度、close-position 极端度。",
        "- 这不是交易规则；所有分桶阈值只作为只读诊断，避免在剩余左尾窗口上直接调参。",
        f"- `high_vol_low_eff_next252`：`{decision['high_vol_low_eff_next252']}`",
        f"- `trend_clean_next252`：`{decision['trend_clean_next252']}`",
        f"- `entry_focus_high_vol_low_eff`：`{decision['entry_focus_high_vol_low_eff']}`",
        f"- `ai_focus_top8_high_vol_low_eff`：`{decision['ai_focus_top8_high_vol_low_eff']}`",
        "",
        "## 市场状态日频样本",
        "",
        _md_table(market_daily.head(8)),
        "",
        "## 曲线日 forward return 归因",
        "",
        _md_table(daily_focus.head(40)),
        "",
        "## Top100 最差窗口前段 regime",
        "",
        _md_table(worst_summary),
        "",
        "## 逐笔 entry regime",
        "",
        _md_table(entry_focus.head(30)),
        "",
        "## AI top8 月度 regime",
        "",
        _md_table(ai_focus),
        "",
        "## 输出",
        "",
    ]
    for key, path in decision["output_files"].items():
        lines.append(f"- `{key}`：`{path}`")
    lines.extend(
        [
            "",
            "## 反思",
            "",
            "- 过拟合反思：否。本阶段只看低自由度市场状态标签，并保留不晋级的可能；没有按日期、品种、方向、source_start 或 horizon 写规则。",
            "- 继续价值反思：是。若 high-vol/low-efficiency 同时在曲线 forward、entry 和 AI top8 上呈现稳定劣化，才值得写一个冻结 Stage018 真实引擎；否则继续只读或换信息源。",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    product_daily, market_daily = _read_market_daily()
    curves = _read_curves()
    daily_forward = _summarize_forward_by_regime(curves, market_daily)
    worst_detail, worst_summary = _worst_window_regime_path(curves, market_daily)
    closed_with_regime = _read_closed_lots_with_regime(product_daily, market_daily)
    entry_summary = _entry_regime_summary(closed_with_regime)
    ai_summary = _ai_monthly_regime_summary()
    decision = _decision(market_daily, daily_forward, worst_summary, entry_summary, ai_summary)

    market_daily.to_csv(MARKET_DAILY_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    daily_forward.to_csv(DAILY_FORWARD_REGIME_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    worst_detail.to_csv(WORST_WINDOW_REGIME_DETAIL_PATH, index=False, encoding="utf-8-sig")
    worst_summary.to_csv(WORST_WINDOW_REGIME_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    entry_summary.to_csv(ENTRY_REGIME_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    ai_summary.to_csv(AI_MONTHLY_REGIME_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    _plot(daily_forward, worst_summary, entry_summary, ai_summary)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(market_daily, daily_forward, worst_summary, entry_summary, ai_summary, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
