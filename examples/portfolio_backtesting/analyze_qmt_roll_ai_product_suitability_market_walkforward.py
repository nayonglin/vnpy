from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.database import get_database

from analyze_qmt_roll_ai_product_suitability_walkforward import (
    DATE_COLUMN,
    ENTRY_SNAPSHOTS_PATH,
    FUTURE_HORIZON_DAYS,
    LOGISTIC_C,
    MIN_TEST_ROWS,
    MIN_TRAIN_ROWS,
    POSITION_CHANGES_PATH,
    PROBABILITY_COLUMN,
    RANDOM_STATE,
    ROLLING_WINDOWS,
    SIMPLE_SCORE_COLUMN,
    SIMPLE_SCORE_PERCENTILE_COLUMN,
    SOURCE_PREFIX,
    STEP_DAYS,
    TARGET_COLUMN,
    TEST_WINDOW_DAYS,
    TOP_N_PRODUCTS,
    TRAIN_WINDOW_DAYS,
    WEIGHT_COLUMN,
    add_rolling_features,
    build_monthly_samples,
    build_product_daily,
    build_report,
    build_bucket_analysis,
    compute_binary_metrics,
    run_walk_forward,
    summarize_top_overall,
    summarize_top_products,
    to_markdown_table,
)
from main_contract_mapping import load_mapping_df
from qmt_universe import VT_SYMBOLS


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "product_suitability_market_wf_v2"
OUTPUT_PREFIX: str = "qmt_roll_ai_product_suitability_market_walkforward"

MARKET_DAILY_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_market_daily_{MODEL_TAG}.csv"
FEATURED_DAILY_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_featured_daily_{MODEL_TAG}.csv"
SAMPLES_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_samples_{MODEL_TAG}.csv"
PREDICTIONS_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_predictions_{MODEL_TAG}.csv"
WINDOW_METRICS_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_metrics_{MODEL_TAG}.csv"
BUCKET_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_analysis_{MODEL_TAG}.csv"
TOP_PRODUCTS_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_top_products_{MODEL_TAG}.csv"
COEFFICIENT_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_coefficients_{MODEL_TAG}.csv"
SUMMARY_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or math.isinf(result):
        return default
    return result


def _parse_vt_symbol(vt_symbol: str) -> tuple[str, Exchange]:
    symbol, exchange = vt_symbol.split(".", 1)
    return symbol, Exchange(exchange)


def _load_contract_bars(vt_symbols: list[str], start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    database = get_database()
    rows: list[dict[str, Any]] = []
    start_dt = start.to_pydatetime()
    end_dt = end.to_pydatetime()

    for vt_symbol in sorted(set(vt_symbols)):
        if not vt_symbol or vt_symbol == "nan":
            continue
        symbol, exchange = _parse_vt_symbol(vt_symbol)
        bars = database.load_bar_data(symbol, exchange, Interval.DAILY, start_dt, end_dt)
        for bar in bars:
            rows.append(
                {
                    "date": pd.Timestamp(bar.datetime).tz_localize(None).normalize(),
                    "main_contract_vt": vt_symbol,
                    "open": float(bar.open_price),
                    "high": float(bar.high_price),
                    "low": float(bar.low_price),
                    "close": float(bar.close_price),
                    "volume": float(getattr(bar, "volume", 0.0) or 0.0),
                    "open_interest": float(getattr(bar, "open_interest", 0.0) or 0.0),
                }
            )

    if not rows:
        return pd.DataFrame(columns=["date", "main_contract_vt", "open", "high", "low", "close", "volume", "open_interest"])
    return pd.DataFrame(rows).drop_duplicates(subset=["date", "main_contract_vt"]).sort_values(["main_contract_vt", "date"])


def build_market_daily(base_daily: pd.DataFrame) -> pd.DataFrame:
    dates = pd.DatetimeIndex(sorted(base_daily["date"].unique()))
    products = sorted(set(VT_SYMBOLS) & set(base_daily["product_vt_symbol"].unique()))
    start = dates.min() - pd.Timedelta(days=220)
    end = dates.max() + pd.Timedelta(days=5)

    mapping = load_mapping_df()
    mapping["date"] = pd.to_datetime(mapping["date"])
    mapping = mapping[
        (mapping["continuous_symbol_vt"].isin(products))
        & (mapping["date"] >= start)
        & (mapping["date"] <= end)
        & (mapping["main_contract_vt"].astype(str) != "")
    ].copy()
    mapping.rename(columns={"continuous_symbol_vt": "product_vt_symbol"}, inplace=True)

    contract_bars = _load_contract_bars(mapping["main_contract_vt"].dropna().astype(str).unique().tolist(), start, end)
    market = mapping[["date", "product_vt_symbol", "main_contract_vt"]].merge(
        contract_bars,
        on=["date", "main_contract_vt"],
        how="left",
    )
    index = pd.MultiIndex.from_product([dates, products], names=["date", "product_vt_symbol"])
    market = market.set_index(["date", "product_vt_symbol"]).reindex(index).reset_index()
    market.sort_values(["product_vt_symbol", "date"], inplace=True)
    for column in ["open", "high", "low", "close"]:
        market[column] = market.groupby("product_vt_symbol")[column].ffill()
    market[["volume", "open_interest"]] = market[["volume", "open_interest"]].fillna(0.0)
    market["main_contract_vt"] = market["main_contract_vt"].fillna("")
    return add_market_features(market)


def _trend_efficiency(close: pd.Series, window: int) -> pd.Series:
    net_move = (close - close.shift(window)).abs()
    path_move = close.diff().abs().rolling(window, min_periods=max(10, window // 2)).sum()
    return (net_move / path_move.replace(0.0, np.nan)).replace([np.inf, -np.inf], np.nan)


def add_market_features(market: pd.DataFrame) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for _, group in market.groupby("product_vt_symbol", sort=False):
        group = group.sort_values("date").copy()
        close = pd.to_numeric(group["close"], errors="coerce")
        high = pd.to_numeric(group["high"], errors="coerce")
        low = pd.to_numeric(group["low"], errors="coerce")
        volume = pd.to_numeric(group["volume"], errors="coerce").fillna(0.0)
        open_interest = pd.to_numeric(group["open_interest"], errors="coerce").fillna(0.0)
        daily_ret = close.pct_change().replace([np.inf, -np.inf], np.nan)
        range_pct = ((high - low) / close.replace(0.0, np.nan)).replace([np.inf, -np.inf], np.nan)

        for window in ROLLING_WINDOWS:
            min_periods = max(10, window // 2)
            group[f"market_ret_{window}d"] = close.pct_change(window)
            group[f"market_realized_vol_{window}d"] = daily_ret.rolling(window, min_periods=min_periods).std() * math.sqrt(window)
            group[f"market_range_pct_mean_{window}d"] = range_pct.rolling(window, min_periods=min_periods).mean()
            group[f"market_trend_efficiency_{window}d"] = _trend_efficiency(close, window)
            rolling_high = close.rolling(window, min_periods=min_periods).max()
            rolling_low = close.rolling(window, min_periods=min_periods).min()
            group[f"market_close_position_{window}d"] = (
                (close - rolling_low) / (rolling_high - rolling_low).replace(0.0, np.nan)
            )
            group[f"market_breakout_rate_{window}d"] = (
                close >= close.shift(1).rolling(window, min_periods=min_periods).max()
            ).astype("float64")
            group[f"market_volume_ratio_{window}d"] = volume / volume.rolling(window, min_periods=min_periods).mean().replace(0.0, np.nan)
            group[f"market_open_interest_change_{window}d"] = open_interest.pct_change(window)

        ma20 = close.rolling(20, min_periods=10).mean()
        ma60 = close.rolling(60, min_periods=30).mean()
        ma120 = close.rolling(120, min_periods=60).mean()
        group["market_ma20_over_ma60_60d"] = ma20 / ma60.replace(0.0, np.nan) - 1.0
        group["market_ma60_over_ma120_120d"] = ma60 / ma120.replace(0.0, np.nan) - 1.0
        group["market_volume_zscore_60d"] = (
            (volume - volume.rolling(60, min_periods=30).mean())
            / volume.rolling(60, min_periods=30).std().replace(0.0, np.nan)
        )
        group["market_open_interest_zscore_60d"] = (
            (open_interest - open_interest.rolling(60, min_periods=30).mean())
            / open_interest.rolling(60, min_periods=30).std().replace(0.0, np.nan)
        )
        frames.append(group)

    featured = pd.concat(frames, ignore_index=True)
    market_feature_columns = [column for column in featured.columns if column.startswith("market_")]
    featured[market_feature_columns] = featured[market_feature_columns].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return featured


def build_market_report(summary: dict[str, Any], bucket_df: pd.DataFrame, top_overall_df: pd.DataFrame) -> str:
    ai_metrics = summary.get("ai_prediction_metrics", {})
    simple_metrics = summary.get("simple_score_metrics_on_ai_test_period", {})
    lines = [
        "# Product Suitability Market Walk-Forward",
        "",
        "## Current Judgement",
        "",
        f"- Source strategy: `{SOURCE_PREFIX}`",
        f"- Target: next `{FUTURE_HORIZON_DAYS}` trading days product net contribution top half.",
        f"- Market feature count: `{summary.get('market_feature_count', 0)}`",
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
        "- This V2 adds main-contract market terrain features.",
        "- It remains a shadow study, not a trade switch.",
        "- Any trading use still requires full portfolio backtest with dynamic product eligibility.",
    ]
    return "\n".join(lines)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    product_daily = build_product_daily()
    system_featured_daily = add_rolling_features(product_daily)
    market_daily = build_market_daily(product_daily)
    market_feature_columns = [column for column in market_daily.columns if column.startswith("market_")]
    featured_daily = system_featured_daily.merge(
        market_daily[["date", "product_vt_symbol", "main_contract_vt"] + market_feature_columns],
        on=["date", "product_vt_symbol"],
        how="left",
    )
    featured_daily[market_feature_columns] = featured_daily[market_feature_columns].fillna(0.0)

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
            "sample_rows": int(len(samples)),
            "prediction_rows": int(len(predictions)),
            "eval_months": int(samples[DATE_COLUMN].nunique()),
            "prediction_months": int(predictions[DATE_COLUMN].nunique()),
            "products": int(samples["product_vt_symbol"].nunique()),
            "feature_count": int(len(feature_columns)),
        },
        "market_feature_count": int(len([column for column in feature_columns if column.startswith("market_")])),
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
            "market_daily_csv": str(MARKET_DAILY_OUTPUT_PATH),
            "featured_daily_csv": str(FEATURED_DAILY_OUTPUT_PATH),
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
            "V2 adds independent market terrain features. It must show stronger and more stable out-of-sample "
            "ranking before any dynamic product filter is considered."
        ),
    }

    market_daily.to_csv(MARKET_DAILY_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    featured_daily.to_csv(FEATURED_DAILY_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    samples.to_csv(SAMPLES_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    predictions.to_csv(PREDICTIONS_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    window_metrics.to_csv(WINDOW_METRICS_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    bucket_df.to_csv(BUCKET_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    top_products_df.to_csv(TOP_PRODUCTS_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    coefficients.to_csv(COEFFICIENT_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    SUMMARY_OUTPUT_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_OUTPUT_PATH.write_text(build_market_report(summary, bucket_df, top_overall_df), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
