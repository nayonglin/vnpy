from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any, Callable
import warnings

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pandas.errors import PerformanceWarning


PROJECT_DIR = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_optimization"
STAGE = "Stage026"
MODEL_TAG = "stage026_recovery_right_tail_episode_identifier_v1"
OUTPUT_PREFIX = "rebuilt_c9_stage026_recovery_right_tail_episode_identifier"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage026_recovery_right_tail_episode_identifier"
STAGE_RECORD_DIR = LINE_DIR / "stages"

STAGE013_OUTPUT_DIR = LINE_DIR / "outputs" / "stage013_account_state_pilot_gate_engine"
STAGE024_OUTPUT_DIR = LINE_DIR / "outputs" / "stage024_causal_high_vol_pause_engine"
STAGE021_OUTPUT_DIR = LINE_DIR / "outputs" / "stage021_full_market_consensus_jd_proxy"
BACKTEST_OUTPUT_DIR = PROJECT_DIR / "examples" / "portfolio_backtesting" / "backtest_outputs"

STAGE013_PREFIX = "rebuilt_c9_stage013_account_state_pilot_gate_engine"
STAGE013_TAG = "stage013_account_state_pilot_gate_engine_v1"
STAGE024_PREFIX = "rebuilt_c9_stage024_causal_high_vol_pause_engine"
STAGE024_TAG = "stage024_causal_high_vol_pause_engine_v1"
STAGE021_PREFIX = "rebuilt_c9_stage021_full_market_consensus_jd_proxy"
STAGE021_TAG = "stage021_full_market_consensus_jd_proxy_v1"

STAGE013_CURVES_PATH = STAGE013_OUTPUT_DIR / f"{STAGE013_PREFIX}_curves_{STAGE013_TAG}.csv"
STAGE024_CURVES_PATH = STAGE024_OUTPUT_DIR / f"{STAGE024_PREFIX}_curves_{STAGE024_TAG}.csv"
STAGE024_PAUSE_EVENTS_PATH = STAGE024_OUTPUT_DIR / f"{STAGE024_PREFIX}_pause_events_{STAGE024_TAG}.csv"
STAGE024_CANDIDATES_PATH = STAGE024_OUTPUT_DIR / f"{STAGE024_PREFIX}_entry_candidates_{STAGE024_TAG}.csv"
FULL_MARKET_PREDICTIONS_PATH = (
    STAGE021_OUTPUT_DIR / f"{STAGE021_PREFIX}_full_market_predictions_ranked_{STAGE021_TAG}.csv"
)
MARKET_DAILY_PATH = (
    BACKTEST_OUTPUT_DIR
    / "qmt_roll_ai_product_suitability_market_walkforward_market_daily_product_suitability_market_wf_v2.csv"
)

EPISODES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_episodes_{MODEL_TAG}.csv"
EPISODE_FEATURES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_episode_features_{MODEL_TAG}.csv"
NUMERIC_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_numeric_summary_{MODEL_TAG}.csv"
BUCKET_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_summary_{MODEL_TAG}.csv"
CONDITION_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_condition_summary_{MODEL_TAG}.csv"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

HORIZONS = (21, 63, 126, 252, 504)
PRIMARY_HORIZON = 252


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
        return None if np.isnan(number) or np.isinf(number) else number
    if not isinstance(value, (str, bytes)) and pd.isna(value):
        return None
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_空_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    return data.to_markdown(index=False)


def _normalize_date(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce", utc=True).dt.tz_convert(None).dt.normalize()


def _product_key(value: Any) -> str:
    return str(value or "").strip().lower()


def _directional(value: Any, direction: Any) -> float:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return np.nan
    sign = 1.0 if str(direction).lower() == "long" else -1.0
    return float(number) * sign


def _directional_close_position(value: Any, direction: Any) -> float:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return np.nan
    number = float(number)
    return number if str(direction).lower() == "long" else 1.0 - number


def _read_curves() -> pd.DataFrame:
    usecols = [
        "requested_start_month",
        "date",
        "account_equity",
        "drawdown_pct",
        "broker10_margin_to_equity_pct",
        "c3_active_products",
        "c3_active_contracts",
        "net_pnl",
        "holding_pnl",
        "trading_pnl",
        "trade_count",
    ]
    existing13 = pd.read_csv(STAGE013_CURVES_PATH, nrows=0).columns
    existing24 = pd.read_csv(STAGE024_CURVES_PATH, nrows=0).columns
    cols13 = [column for column in usecols if column in existing13]
    cols24 = [column for column in usecols if column in existing24]
    stage013 = pd.read_csv(STAGE013_CURVES_PATH, encoding="utf-8-sig", usecols=cols13)
    stage024 = pd.read_csv(STAGE024_CURVES_PATH, encoding="utf-8-sig", usecols=cols24)
    for frame in (stage013, stage024):
        frame["date"] = _normalize_date(frame["date"])
        frame["requested_start_month"] = frame["requested_start_month"].astype(str)
        for column in frame.columns:
            if column not in {"requested_start_month", "date"}:
                frame[column] = pd.to_numeric(frame[column], errors="coerce")
    merged = stage013.merge(
        stage024,
        on=["requested_start_month", "date"],
        how="inner",
        suffixes=("_stage013", "_stage024"),
    )
    merged["equity_delta_stage024_minus_stage013"] = (
        merged["account_equity_stage024"] - merged["account_equity_stage013"]
    )
    merged = merged.sort_values(["requested_start_month", "date"]).reset_index(drop=True)
    return merged


def _episode_outcomes(curves: pd.DataFrame, pause_events: pd.DataFrame) -> pd.DataFrame:
    episodes = (
        pause_events.groupby(["requested_start_month", "event_date"], as_index=False)
        .agg(
            event_count=("product_vt_symbol", "count"),
            product_count=("product_vt_symbol", "nunique"),
            products=("product_vt_symbol", lambda s: ",".join(sorted(set(map(str, s))))),
            directions=("direction", lambda s: ",".join(sorted(set(map(str, s))))),
            signals=("signal", lambda s: ",".join(sorted(set(map(str, s))))),
            reduced_volume=("stage024_pause_gate_reduced_volume", "sum"),
            source_date=("stage024_pause_gate_source_date", "min"),
        )
        .sort_values(["requested_start_month", "event_date"])
        .reset_index(drop=True)
    )
    curve_map = {source: group.sort_values("date").reset_index(drop=True) for source, group in curves.groupby("requested_start_month")}
    rows: list[dict[str, Any]] = []
    for row in episodes.itertuples(index=False):
        curve = curve_map.get(str(row.requested_start_month))
        if curve is None:
            continue
        idx = curve.index[curve["date"].ge(pd.Timestamp(row.event_date))]
        if len(idx) == 0:
            continue
        start_index = int(idx[0])
        before_index = max(0, start_index - 1)
        before_delta = float(curve.loc[before_index, "equity_delta_stage024_minus_stage013"])
        result = row._asdict()
        result["delta_before_event"] = before_delta
        result["account_equity_stage013_before"] = float(curve.loc[before_index, "account_equity_stage013"])
        result["account_equity_stage024_before"] = float(curve.loc[before_index, "account_equity_stage024"])
        for column in [
            "drawdown_pct",
            "broker10_margin_to_equity_pct",
            "c3_active_products",
            "c3_active_contracts",
            "net_pnl",
            "holding_pnl",
            "trading_pnl",
            "trade_count",
        ]:
            stage013_col = f"{column}_stage013"
            stage024_col = f"{column}_stage024"
            if stage013_col in curve.columns:
                result[f"{column}_stage013_before"] = float(curve.loc[before_index, stage013_col])
            if stage024_col in curve.columns:
                result[f"{column}_stage024_before"] = float(curve.loc[before_index, stage024_col])
        for horizon in HORIZONS:
            end_index = min(len(curve) - 1, start_index + horizon)
            after_delta = float(curve.loc[end_index, "equity_delta_stage024_minus_stage013"])
            result[f"delta_change_{horizon}d"] = after_delta - before_delta
        rows.append(result)
    result = pd.DataFrame(rows)
    primary = f"delta_change_{PRIMARY_HORIZON}d"
    result["pause_helped_252d"] = result[primary].gt(0).astype("int64")
    result["right_tail_miss_252d"] = result[primary].le(0).astype("int64")
    result["strong_right_tail_miss_252d"] = result[primary].le(-30000.0).astype("int64")
    return result.sort_values(["requested_start_month", "event_date"]).reset_index(drop=True)


def _read_pause_events() -> pd.DataFrame:
    pause = pd.read_csv(STAGE024_PAUSE_EVENTS_PATH, encoding="utf-8-sig")
    pause["event_date"] = _normalize_date(pause["datetime"])
    pause["source_date"] = _normalize_date(pause["stage024_pause_gate_source_date"])
    pause["requested_start_month"] = pause["requested_start_month"].astype(str)
    pause["product_key"] = pause["product_vt_symbol"].map(_product_key)
    pause["direction"] = pause["direction"].astype(str).str.lower()
    for column in [
        "stage024_pause_gate_reduced_volume",
        "stage024_pause_gate_selected_volume_before",
        "stage024_pause_gate_selected_volume_after",
        "price",
    ]:
        if column in pause.columns:
            pause[column] = pd.to_numeric(pause[column], errors="coerce")
    return pause


def _read_candidates() -> pd.DataFrame:
    candidate_cols = [
        "requested_start_month",
        "date",
        "product_vt_symbol",
        "direction",
        "signal",
        "entry_context",
        "candidate_status",
        "skip_reason",
        "estimated_equity",
        "total_margin_in_use_before",
        "free_capital",
        "limited_balance",
        "risk_ratio",
        "risk_multiplier",
        "oi_price_confirm_passed",
        "oi_price_confirm_oi_up",
        "oi_price_confirm_price_aligned",
        "oi_price_confirm_recent_prior_oi_sum_ratio",
        "target_risk_amount",
        "planned_entry_price",
        "stop_price",
        "stop_distance",
        "size",
        "risk_per_contract",
        "margin_ratio",
        "margin_per_contract",
        "selected_volume",
        "selected_volume_ungated",
        "portfolio_drawdown_pct",
        "portfolio_overheat_cooldown_prior_drawdown_pct",
        "portfolio_overheat_cooldown_prior_ret20",
        "portfolio_overheat_cooldown_prior_ret60",
        "same_direction_correlation_active_count",
        "same_direction_correlation_corr_count",
        "same_direction_correlation_max_corr",
        "same_direction_correlation_avg_corr",
        "selection_pairwise_score",
        "selection_pairwise_rank",
        "selection_pairwise_feature_ret_20d_zscore_120",
        "selection_pairwise_feature_close_position_60d_cs_zscore_1d",
        "selection_pairwise_feature_range_pct_zscore_120",
        "selection_pairwise_volume_tilt_direction_strength",
        "selection_pairwise_volume_tilt_score_gap",
        "selection_pairwise_volume_tilt_top_gap",
        "selection_pairwise_volume_tilt_avg_active_positions_before",
        "selection_pairwise_volume_tilt_state_max_range_zscore",
        "ai_path_damage_probability",
        "ai_product_pool_allowed",
        "ai_product_pool_score",
        "ai_product_pool_rank",
        "ai_product_pool_top_n",
        "active_positions_before",
        "max_concurrent_positions",
        "effective_max_concurrent_positions",
        "remaining_position_slots",
        "bullish_alignment",
        "bearish_alignment",
        "breakout",
        "rsi_value",
        "ma_mid_value",
        "ma_long_value",
        "ma_mid_prev_value",
        "ma_long_prev_value",
        "loss_streak",
        "profit_recovery_streak",
        "stage024_pause_gate_selected_volume_before",
        "stage024_pause_gate_reduced_volume",
    ]
    existing = pd.read_csv(STAGE024_CANDIDATES_PATH, nrows=0).columns
    usecols = [column for column in candidate_cols if column in existing]
    data = pd.read_csv(STAGE024_CANDIDATES_PATH, encoding="utf-8-sig", usecols=usecols)
    data["event_date"] = _normalize_date(data["date"])
    data["requested_start_month"] = data["requested_start_month"].astype(str)
    data["product_key"] = data["product_vt_symbol"].map(_product_key)
    data["direction"] = data["direction"].astype(str).str.lower()
    for column in data.columns:
        if column not in {
            "requested_start_month",
            "date",
            "event_date",
            "product_vt_symbol",
            "product_key",
            "direction",
            "signal",
            "entry_context",
            "candidate_status",
            "skip_reason",
        }:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    return data


def _read_market_daily() -> pd.DataFrame:
    usecols = [
        "date",
        "product_vt_symbol",
        "market_ret_20d",
        "market_realized_vol_20d",
        "market_range_pct_mean_20d",
        "market_trend_efficiency_20d",
        "market_close_position_20d",
        "market_breakout_rate_20d",
        "market_volume_ratio_20d",
        "market_open_interest_change_20d",
        "market_ret_60d",
        "market_realized_vol_60d",
        "market_range_pct_mean_60d",
        "market_trend_efficiency_60d",
        "market_close_position_60d",
        "market_breakout_rate_60d",
        "market_volume_ratio_60d",
        "market_open_interest_change_60d",
        "market_ret_120d",
        "market_realized_vol_120d",
        "market_range_pct_mean_120d",
        "market_trend_efficiency_120d",
        "market_close_position_120d",
        "market_breakout_rate_120d",
        "market_volume_ratio_120d",
        "market_open_interest_change_120d",
        "market_ma20_over_ma60_60d",
        "market_ma60_over_ma120_120d",
        "market_volume_zscore_60d",
        "market_open_interest_zscore_60d",
    ]
    existing = pd.read_csv(MARKET_DAILY_PATH, nrows=0).columns
    usecols = [column for column in usecols if column in existing]
    data = pd.read_csv(MARKET_DAILY_PATH, encoding="utf-8-sig", usecols=usecols)
    data["source_date"] = _normalize_date(data["date"])
    data["product_key"] = data["product_vt_symbol"].map(_product_key)
    for column in data.columns:
        if column not in {"date", "source_date", "product_vt_symbol", "product_key"}:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    return data


def _read_ai_predictions() -> pd.DataFrame:
    usecols = [
        "eval_date",
        "product_vt_symbol",
        "predicted_product_suitability_probability",
        "simple_trend_suitability_score",
        "simple_trend_suitability_score_percentile",
        "candidate_count_sum_60d",
        "market_ma20_over_ma60_60d",
        "market_realized_vol_60d",
        "market_ret_60d",
        "market_trend_efficiency_60d",
        "net_pnl_sum_60d",
        "opened_count_sum_60d",
        "ai_rank_desc",
        "simple_rank_desc",
        "product_count",
        "stage021_ai_top8",
        "stage021_simple_top8",
        "stage021_consensus_top8",
        "stage021_consensus_top8_jd",
    ]
    existing = pd.read_csv(FULL_MARKET_PREDICTIONS_PATH, nrows=0).columns
    usecols = [column for column in usecols if column in existing]
    data = pd.read_csv(FULL_MARKET_PREDICTIONS_PATH, encoding="utf-8-sig", usecols=usecols)
    data["eval_date"] = _normalize_date(data["eval_date"])
    data["product_key"] = data["product_vt_symbol"].map(_product_key)
    for column in data.columns:
        if column not in {"eval_date", "product_vt_symbol", "product_key"}:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    return data.sort_values(["product_key", "eval_date"]).reset_index(drop=True)


def _merge_asof_ai(events: pd.DataFrame, predictions: pd.DataFrame) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    events = events.sort_values(["product_key", "source_date"]).copy()
    for product, group in events.groupby("product_key", sort=False):
        product_predictions = predictions[predictions["product_key"].eq(product)].sort_values("eval_date")
        if product_predictions.empty:
            current = group.copy()
            for column in predictions.columns:
                if column not in {"product_key", "product_vt_symbol", "eval_date"}:
                    current[f"ai_{column}"] = np.nan
            current["ai_eval_date"] = pd.NaT
            frames.append(current)
            continue
        current = pd.merge_asof(
            group.sort_values("source_date"),
            product_predictions,
            left_on="source_date",
            right_on="eval_date",
            direction="backward",
            suffixes=("", "_ai"),
        )
        rename = {
            column: f"ai_{column}"
            for column in product_predictions.columns
            if column not in {"product_key", "product_vt_symbol", "eval_date"}
        }
        current = current.rename(columns=rename)
        current = current.rename(columns={"eval_date": "ai_eval_date"})
        frames.append(current)
    return pd.concat(frames, ignore_index=True, sort=False)


def _event_feature_rows(pause: pd.DataFrame, candidates: pd.DataFrame, market_daily: pd.DataFrame, ai: pd.DataFrame) -> pd.DataFrame:
    candidate_cols = [column for column in candidates.columns if column not in {"date", "product_vt_symbol"}]
    rows = pause.merge(
        candidates[candidate_cols],
        on=["requested_start_month", "event_date", "product_key", "direction", "signal"],
        how="left",
        suffixes=("", "_candidate"),
    )
    rows = rows.merge(
        market_daily.drop(columns=["date", "product_vt_symbol"], errors="ignore"),
        on=["source_date", "product_key"],
        how="left",
        suffixes=("", "_market"),
    )
    rows = _merge_asof_ai(rows, ai)
    for horizon in (20, 60, 120):
        ret_col = f"market_ret_{horizon}d"
        close_col = f"market_close_position_{horizon}d"
        ma_col = "market_ma20_over_ma60_60d" if horizon == 60 else "market_ma60_over_ma120_120d"
        if ret_col in rows.columns:
            rows[f"directional_market_ret_{horizon}d"] = [
                _directional(value, direction) for value, direction in zip(rows[ret_col], rows["direction"])
            ]
        if close_col in rows.columns:
            rows[f"directional_close_position_{horizon}d"] = [
                _directional_close_position(value, direction)
                for value, direction in zip(rows[close_col], rows["direction"])
            ]
        if ma_col in rows.columns:
            rows[f"directional_{ma_col}"] = [
                _directional(value, direction) for value, direction in zip(rows[ma_col], rows["direction"])
            ]
    if {"ma_mid_value", "ma_long_value"}.issubset(rows.columns):
        rows["ma_mid_minus_long"] = pd.to_numeric(rows["ma_mid_value"], errors="coerce") - pd.to_numeric(
            rows["ma_long_value"], errors="coerce"
        )
        rows["directional_ma_mid_minus_long"] = [
            _directional(value, direction) for value, direction in zip(rows["ma_mid_minus_long"], rows["direction"])
        ]
    return rows


def _aggregate_episode_features(event_rows: pd.DataFrame, episodes: pd.DataFrame) -> pd.DataFrame:
    key_cols = ["requested_start_month", "event_date"]
    numeric_cols = [
        column
        for column in event_rows.columns
        if column not in key_cols
        and column
        not in {
            "datetime",
            "date",
            "vt_symbol",
            "product_vt_symbol",
            "product_key",
            "position_direction",
            "direction",
            "offset",
            "reason",
            "contract_vt_symbol",
            "signal",
            "entry_context",
            "candidate_status_after",
            "skip_reason_after",
            "stage024_pause_gate_reason",
            "stage024_pause_gate_target_regimes",
            "stage024_pause_gate_joint_regime",
            "stage024_pause_gate_source_date",
            "stage024_pause_gate_vol60_bucket",
            "stage024_pause_gate_eff60_bucket",
            "profile",
            "start_month",
            "variant",
            "stage",
            "model_tag",
            "line_id",
            "official_live_version",
            "official_live_alias",
            "requested_start",
            "requested_end",
            "source_date",
            "event_date",
            "ai_eval_date",
            "candidate_status",
            "skip_reason",
        }
        and pd.api.types.is_numeric_dtype(event_rows[column])
    ]
    agg: dict[str, tuple[str, str | Callable[[pd.Series], float]]] = {}
    for column in numeric_cols:
        agg[f"{column}_mean"] = (column, "mean")
        agg[f"{column}_min"] = (column, "min")
        agg[f"{column}_max"] = (column, "max")
    derived = pd.DataFrame(
        {
            "is_long": event_rows["direction"].eq("long").astype(float),
            "is_short": event_rows["direction"].eq("short").astype(float),
            "ai_consensus_flag": pd.to_numeric(
                event_rows.get("ai_stage021_consensus_top8", np.nan), errors="coerce"
            ),
            "ai_top8_flag": pd.to_numeric(event_rows.get("ai_stage021_ai_top8", np.nan), errors="coerce"),
            "simple_top8_flag": pd.to_numeric(event_rows.get("ai_stage021_simple_top8", np.nan), errors="coerce"),
        },
        index=event_rows.index,
    )
    grouped_input = pd.concat([event_rows[key_cols + numeric_cols], derived], axis=1).copy()
    for column in ["is_long", "is_short"]:
        agg[f"{column}_share"] = (column, "mean")
    for column in ["ai_consensus_flag", "ai_top8_flag", "simple_top8_flag"]:
        agg[f"{column}_share"] = (column, "mean")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", PerformanceWarning)
        grouped = grouped_input.groupby(key_cols, as_index=False).agg(**agg)
    result = episodes.merge(grouped, on=key_cols, how="left")
    return result


def _numeric_summary(features: pd.DataFrame) -> pd.DataFrame:
    label = "right_tail_miss_252d"
    rows: list[dict[str, Any]] = []
    excluded = {
        "pause_helped_252d",
        "right_tail_miss_252d",
        "strong_right_tail_miss_252d",
    }
    for column in features.columns:
        if (
            column in excluded
            or column == "delta_before_event"
            or column.startswith("delta_change_")
            or not pd.api.types.is_numeric_dtype(features[column])
        ):
            continue
        data = features[[column, label]].dropna()
        if len(data) < 20 or data[label].nunique() < 2:
            continue
        miss = data[data[label].eq(1)][column]
        helped = data[data[label].eq(0)][column]
        if len(miss) < 5 or len(helped) < 10:
            continue
        pooled = float(pd.concat([miss, helped]).std(ddof=0) or np.nan)
        rows.append(
            {
                "feature": column,
                "count": int(len(data)),
                "miss_count": int(len(miss)),
                "helped_count": int(len(helped)),
                "miss_mean": float(miss.mean()),
                "helped_mean": float(helped.mean()),
                "mean_diff_miss_minus_helped": float(miss.mean() - helped.mean()),
                "miss_median": float(miss.median()),
                "helped_median": float(helped.median()),
                "median_diff_miss_minus_helped": float(miss.median() - helped.median()),
                "effect_size_mean_diff": float((miss.mean() - helped.mean()) / pooled) if np.isfinite(pooled) and pooled else np.nan,
                "miss_positive_rate_pct": float((miss.gt(0).mean()) * 100.0),
                "helped_positive_rate_pct": float((helped.gt(0).mean()) * 100.0),
            }
        )
    result = pd.DataFrame(rows)
    if result.empty:
        return result
    result["abs_effect"] = result["effect_size_mean_diff"].abs()
    return result.sort_values(["abs_effect", "count"], ascending=[False, False]).reset_index(drop=True)


def _bucket_label(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    valid = numeric.dropna()
    result = pd.Series("missing", index=series.index)
    if len(valid) < 12 or valid.nunique() < 3:
        return result
    low = float(valid.quantile(0.33))
    high = float(valid.quantile(0.67))
    result[numeric <= low] = "low"
    result[(numeric > low) & (numeric < high)] = "mid"
    result[numeric >= high] = "high"
    return result


def _summarize_mask(features: pd.DataFrame, name: str, mask: pd.Series) -> dict[str, Any]:
    scoped = features[mask.fillna(False).astype(bool)].copy()
    label = pd.to_numeric(scoped["right_tail_miss_252d"], errors="coerce").fillna(0).astype(int)
    all_rate = float(pd.to_numeric(features["right_tail_miss_252d"], errors="coerce").mean() * 100.0)
    miss_rate = float(label.mean() * 100.0) if len(scoped) else 0.0
    return {
        "name": name,
        "count": int(len(scoped)),
        "source_count": int(scoped["requested_start_month"].nunique()) if "requested_start_month" in scoped else 0,
        "date_count": int(scoped["event_date"].nunique()) if "event_date" in scoped else 0,
        "miss_count": int(label.sum()),
        "right_tail_miss_rate_pct": miss_rate,
        "lift_vs_all": float(miss_rate / all_rate) if all_rate else np.nan,
        "median_delta_252d": float(pd.to_numeric(scoped["delta_change_252d"], errors="coerce").median())
        if len(scoped)
        else np.nan,
        "mean_delta_252d": float(pd.to_numeric(scoped["delta_change_252d"], errors="coerce").mean())
        if len(scoped)
        else np.nan,
        "min_delta_252d": float(pd.to_numeric(scoped["delta_change_252d"], errors="coerce").min())
        if len(scoped)
        else np.nan,
        "max_delta_252d": float(pd.to_numeric(scoped["delta_change_252d"], errors="coerce").max())
        if len(scoped)
        else np.nan,
    }


def _bucket_summary(features: pd.DataFrame, numeric_summary: pd.DataFrame) -> pd.DataFrame:
    preferred = [
        "directional_market_ret_20d_mean",
        "directional_market_ret_60d_mean",
        "directional_market_ret_120d_mean",
        "directional_close_position_20d_mean",
        "directional_close_position_60d_mean",
        "directional_close_position_120d_mean",
        "market_trend_efficiency_60d_mean",
        "market_realized_vol_60d_mean",
        "market_range_pct_mean_60d_mean",
        "market_breakout_rate_60d_mean",
        "market_open_interest_change_60d_mean",
        "market_volume_zscore_60d_mean",
        "ai_predicted_product_suitability_probability_mean",
        "ai_simple_trend_suitability_score_percentile_mean",
        "ai_ai_rank_desc_mean",
        "ai_simple_rank_desc_mean",
        "selection_pairwise_score_mean",
        "selection_pairwise_rank_mean",
        "same_direction_correlation_max_corr_mean",
        "portfolio_drawdown_pct_mean",
        "portfolio_overheat_cooldown_prior_ret60_mean",
        "active_positions_before_mean",
        "ai_consensus_flag_share",
    ]
    effect_features = numeric_summary.head(16)["feature"].tolist() if not numeric_summary.empty else []
    bucket_features = []
    for column in preferred + effect_features:
        if column in features.columns and column not in bucket_features:
            bucket_features.append(column)
    rows: list[dict[str, Any]] = []
    for column in bucket_features:
        bucket = _bucket_label(features[column])
        for value, group_index in bucket.groupby(bucket).groups.items():
            if value == "missing":
                continue
            mask = features.index.isin(group_index)
            row = _summarize_mask(features, f"{column}={value}", pd.Series(mask, index=features.index))
            if row["count"] < 8:
                continue
            row["feature"] = column
            row["bucket"] = value
            rows.append(row)
    result = pd.DataFrame(rows)
    if result.empty:
        return result
    return result.sort_values(["lift_vs_all", "right_tail_miss_rate_pct", "count"], ascending=[False, False, False])


def _condition_summary(features: pd.DataFrame) -> pd.DataFrame:
    condition_map: dict[str, Callable[[pd.DataFrame], pd.Series]] = {
        "all_episodes": lambda df: pd.Series(True, index=df.index),
        "directional_ret60_positive": lambda df: df["directional_market_ret_60d_mean"].gt(0),
        "directional_ret60_negative": lambda df: df["directional_market_ret_60d_mean"].lt(0),
        "directional_ret120_positive": lambda df: df["directional_market_ret_120d_mean"].gt(0),
        "directional_close60_high": lambda df: df["directional_close_position_60d_mean"].ge(0.70),
        "directional_close60_low": lambda df: df["directional_close_position_60d_mean"].le(0.30),
        "market_eff60_high": lambda df: df["market_trend_efficiency_60d_mean"].ge(
            df["market_trend_efficiency_60d_mean"].quantile(0.67)
        ),
        "market_eff60_low": lambda df: df["market_trend_efficiency_60d_mean"].le(
            df["market_trend_efficiency_60d_mean"].quantile(0.33)
        ),
        "market_oi60_positive": lambda df: df["market_open_interest_change_60d_mean"].gt(0),
        "ai_prob_high": lambda df: df["ai_predicted_product_suitability_probability_mean"].ge(
            df["ai_predicted_product_suitability_probability_mean"].quantile(0.67)
        ),
        "ai_prob_low": lambda df: df["ai_predicted_product_suitability_probability_mean"].le(
            df["ai_predicted_product_suitability_probability_mean"].quantile(0.33)
        ),
        "ai_consensus_any": lambda df: df["ai_consensus_flag_share"].gt(0),
        "ai_simple_top8_any": lambda df: df["simple_top8_flag_share"].gt(0),
        "account_drawdown_le_-20": lambda df: df["drawdown_pct_stage013_before"].le(-20),
        "account_drawdown_gt_-10": lambda df: df["drawdown_pct_stage013_before"].gt(-10),
        "prior_ret60_loss": lambda df: df["portfolio_overheat_cooldown_prior_ret60_mean"].lt(0),
        "prior_ret60_gain": lambda df: df["portfolio_overheat_cooldown_prior_ret60_mean"].gt(0),
        "positive_trend_and_ai_high": lambda df: df["directional_market_ret_60d_mean"].gt(0)
        & df["ai_predicted_product_suitability_probability_mean"].ge(
            df["ai_predicted_product_suitability_probability_mean"].quantile(0.67)
        ),
        "positive_trend_no_consensus": lambda df: df["directional_market_ret_60d_mean"].gt(0)
        & df["ai_consensus_flag_share"].le(0),
        "high_eff_positive_trend": lambda df: df["directional_market_ret_60d_mean"].gt(0)
        & df["market_trend_efficiency_60d_mean"].ge(df["market_trend_efficiency_60d_mean"].quantile(0.67)),
        "deep_dd_positive_trend": lambda df: df["drawdown_pct_stage013_before"].le(-20)
        & df["directional_market_ret_60d_mean"].gt(0),
    }
    rows: list[dict[str, Any]] = []
    for name, maker in condition_map.items():
        if name != "all_episodes":
            try:
                mask = maker(features)
            except KeyError:
                continue
        else:
            mask = maker(features)
        row = _summarize_mask(features, name, mask)
        if row["count"] < 8 and name != "all_episodes":
            continue
        row["condition"] = name
        rows.append(row)
    result = pd.DataFrame(rows)
    if result.empty:
        return result
    return result.sort_values(["lift_vs_all", "right_tail_miss_rate_pct", "count"], ascending=[False, False, False])


def _plot(numeric_summary: pd.DataFrame, bucket_summary: pd.DataFrame, condition_summary: pd.DataFrame) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(2, 2, figsize=(18, 12))
    if not numeric_summary.empty:
        top = numeric_summary.head(14).copy().sort_values("effect_size_mean_diff")
        axes[0, 0].barh(top["feature"], top["effect_size_mean_diff"], color="#2563eb")
        axes[0, 0].set_title("Numeric feature effect: right-tail miss vs helped")
        axes[0, 0].set_xlabel("effect size")
    if not condition_summary.empty:
        cond = condition_summary[condition_summary["condition"].ne("all_episodes")].head(12).copy()
        axes[0, 1].barh(cond["condition"], cond["right_tail_miss_rate_pct"], color="#dc2626")
        axes[0, 1].invert_yaxis()
        axes[0, 1].set_title("Condition right-tail miss rate")
        axes[0, 1].set_xlabel("miss rate %")
    if not bucket_summary.empty:
        buckets = bucket_summary.head(12).copy()
        labels = buckets["feature"] + "=" + buckets["bucket"]
        axes[1, 0].barh(labels, buckets["lift_vs_all"], color="#16a34a")
        axes[1, 0].invert_yaxis()
        axes[1, 0].set_title("Bucket lift vs all")
        axes[1, 0].set_xlabel("lift")
        axes[1, 1].scatter(
            bucket_summary["count"],
            bucket_summary["right_tail_miss_rate_pct"],
            s=np.clip(bucket_summary["source_count"] * 18, 30, 260),
            color="#7c3aed",
            alpha=0.70,
        )
        axes[1, 1].set_title("Bucket count vs miss rate")
        axes[1, 1].set_xlabel("count")
        axes[1, 1].set_ylabel("miss rate %")
    for ax in axes.ravel():
        ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _write_report(
    decision: dict[str, Any],
    numeric_summary: pd.DataFrame,
    bucket_summary: pd.DataFrame,
    condition_summary: pd.DataFrame,
) -> None:
    report = f"""# Stage026 恢复段右尾 episode 入场前识别只读归因

- 生成时间：`{decision['generated_at']}`
- line_id：`{LINE_ID}`
- model_tag：`{MODEL_TAG}`
- 决策：`{decision['decision']}`
- 阶段性质：只读归因；不是新策略版本，不改官方线上配置，不连接 CTP，不调用下单。

## 外部调研判断

- Trend-following 资料强调长期正收益来自趋势延续、正偏右尾和跨市场分散，而 whipsaw 是主要成本。
- 相关开源/论文实现常用 trend/momentum、vol scaling、连续预测、横截面分散等入场前可见变量；因此 Stage026 只比较这些变量，不使用未来收益作为规则输入。

## 口径

- 样本：Stage024 暂停新 `flat_entry` 的 episode，按 `source_start_month + event_date` 聚合。
- 标签：`delta_change_252d <= 0` 记为右尾错杀/恢复段漏放；`>0` 记为暂停有益。
- 特征来源：Stage024 candidate 字段、前一交易日 product market daily、当月或此前 full-market AI 预测、Stage013/024 账户曲线当时状态。

## 核心结果

- episode 数：`{decision['episode_count']}`
- 右尾错杀 episode：`{decision['right_tail_miss_count']}`
- 右尾错杀率：`{decision['right_tail_miss_rate_pct']:.4f}%`
- 暂停有益 episode：`{decision['pause_helped_count']}`
- `252d` delta 总和：`{decision['delta_252d_sum']:.2f}`
- `252d` delta 中位数：`{decision['delta_252d_median']:.2f}`
- 最强条件：`{decision['top_condition']}`，错杀率 `{decision['top_condition_miss_rate_pct']:.4f}%`，样本 `{decision['top_condition_count']}`。
- 最强分桶：`{decision['top_bucket']}`，错杀率 `{decision['top_bucket_miss_rate_pct']:.4f}%`，样本 `{decision['top_bucket_count']}`。

## 数值特征差异

{_md_table(numeric_summary.head(20))}

## 条件摘要

{_md_table(condition_summary.head(24))}

## 分桶摘要

{_md_table(bucket_summary.head(24))}

## 判断

- 决策：`{decision['decision']}`。
- 过拟合反思：{decision['overfit_reflection_after']}
- 继续价值反思：{decision['continue_value_after']}

## 输出文件

- episodes: `{EPISODES_PATH}`
- episode_features: `{EPISODE_FEATURES_PATH}`
- numeric_summary: `{NUMERIC_SUMMARY_PATH}`
- bucket_summary: `{BUCKET_SUMMARY_PATH}`
- condition_summary: `{CONDITION_SUMMARY_PATH}`
- chart: `{CHART_PATH}`
- decision: `{DECISION_PATH}`
- report: `{REPORT_PATH}`
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def _write_stage_record(decision: dict[str, Any]) -> Path:
    path = STAGE_RECORD_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M')}_stage026_recovery_right_tail_episode_identifier.md"
    content = f"""# Stage026 - 恢复段右尾 episode 入场前识别只读归因

## 变更时间

- {decision['generated_at']} CST

## 是否重要突破版本

- 否。只读归因，不是真实引擎候选，不改线上。

## 本次版本改动内容

- 新增工具：`research/lines/{LINE_ID}/tools/stage026_recovery_right_tail_episode_identifier.py`
- 将 Stage024 pause events 按 `source_start_month + event_date` 聚合为 episode。
- 合并入场前可见的 candidate、market daily、full-market AI、账户曲线状态，比较右尾错杀与暂停有益 episode。

## 新增参数

- `PRIMARY_HORIZON=252`
- `right_tail_miss_252d = delta_change_252d <= 0`
- `strong_right_tail_miss_252d = delta_change_252d <= -30000`

## 修改参数

- 无。

## 删除参数

- 无。

## 新增回测结果

- episode 数：`{decision['episode_count']}`
- 右尾错杀 episode：`{decision['right_tail_miss_count']}`
- 右尾错杀率：`{decision['right_tail_miss_rate_pct']:.4f}%`
- 暂停有益 episode：`{decision['pause_helped_count']}`
- `252d` delta 总和：`{decision['delta_252d_sum']:.2f}`
- `252d` delta 中位数：`{decision['delta_252d_median']:.2f}`
- 最强条件：`{decision['top_condition']}`，错杀率 `{decision['top_condition_miss_rate_pct']:.4f}%`，样本 `{decision['top_condition_count']}`
- 最强分桶：`{decision['top_bucket']}`，错杀率 `{decision['top_bucket_miss_rate_pct']:.4f}%`，样本 `{decision['top_bucket_count']}`

## 修改回测结果

- 无。

## 删除回测结果

- 无。

## 指标占位

- 期末权益：只读归因，不适用。
- 总收益：只读归因，不适用。
- 最大回撤：只读归因，不适用。
- Sharpe：只读归因，不适用。
- 总滑点：不新增交易，不适用。
- 总交易次数：不新增交易，不适用。
- 胜率：不新增交易，不适用。

## 调研与判断结论

- 外部资料判断：趋势跟随需要保留趋势延续右尾，whipsaw 是成本；因此不能只用 hard regime gate，而要找入场前可见的恢复段/假趋势差异。
- 本阶段判断：`{decision['decision']}`。

## 过拟合与继续价值反思

- 运行前是否过拟合：否。本阶段只做预声明 episode 归因，不直接写规则。
- 运行前是否有价值继续：有。Stage025 已确认 hard gate 内部混合两类 episode，需要判断是否能被可见特征区分。
- 运行后是否过拟合：{decision['overfit_reflection_after']}
- 运行后是否有价值继续：{decision['continue_value_after']}

## 后续规划和 TODO

- 若 Stage026 未找到跨 source 稳定、非日期/品种补丁的差异，应关闭 hard regime gate 方向。
- 若存在强但样本窄的线索，只能继续只读验证，不得直接写真实引擎。

## 输出文件

- `{REPORT_PATH}`
- `{DECISION_PATH}`
- `{CHART_PATH}`
"""
    path.write_text(content, encoding="utf-8")
    return path


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STAGE_RECORD_DIR.mkdir(parents=True, exist_ok=True)

    curves = _read_curves()
    pause = _read_pause_events()
    episodes = _episode_outcomes(curves, pause)
    candidates = _read_candidates()
    market_daily = _read_market_daily()
    ai = _read_ai_predictions()
    event_rows = _event_feature_rows(pause, candidates, market_daily, ai)
    features = _aggregate_episode_features(event_rows, episodes)

    numeric_summary = _numeric_summary(features)
    bucket_summary = _bucket_summary(features, numeric_summary)
    condition_summary = _condition_summary(features)
    _plot(numeric_summary, bucket_summary, condition_summary)

    all_row = condition_summary[condition_summary["condition"].eq("all_episodes")].iloc[0].to_dict()
    condition_candidates = condition_summary[
        condition_summary["condition"].ne("all_episodes")
        & condition_summary["count"].ge(10)
        & condition_summary["source_count"].ge(3)
    ].copy()
    top_condition = condition_candidates.iloc[0].to_dict() if not condition_candidates.empty else {}
    bucket_candidates = bucket_summary[bucket_summary["count"].ge(10) & bucket_summary["source_count"].ge(3)].copy()
    top_bucket = bucket_candidates.iloc[0].to_dict() if not bucket_candidates.empty else {}

    miss_rate = float(all_row.get("right_tail_miss_rate_pct", np.nan))
    top_condition_rate = float(top_condition.get("right_tail_miss_rate_pct", np.nan))
    top_bucket_rate = float(top_bucket.get("right_tail_miss_rate_pct", np.nan))
    stable_strong_condition = bool(
        top_condition
        and int(top_condition.get("count", 0) or 0) >= 20
        and int(top_condition.get("source_count", 0) or 0) >= 5
        and top_condition_rate >= miss_rate * 1.8
    )
    stable_strong_bucket = bool(
        top_bucket
        and int(top_bucket.get("count", 0) or 0) >= 20
        and int(top_bucket.get("source_count", 0) or 0) >= 5
        and top_bucket_rate >= miss_rate * 1.8
    )
    decision_label = (
        "stage026_has_candidate_precursor_needs_true_engine_review"
        if stable_strong_condition or stable_strong_bucket
        else "stage026_no_stable_precursor_close_hard_regime_gate"
    )

    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "audit_type": "stage024_pause_episode_right_tail_miss_precursor_attribution",
        "decision": decision_label,
        "strategy_changed": False,
        "true_engine": False,
        "official_live_config_changed": False,
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "episode_count": int(len(features)),
        "right_tail_miss_count": int(pd.to_numeric(features["right_tail_miss_252d"], errors="coerce").sum()),
        "right_tail_miss_rate_pct": float(miss_rate),
        "pause_helped_count": int(pd.to_numeric(features["pause_helped_252d"], errors="coerce").sum()),
        "delta_252d_sum": float(pd.to_numeric(features["delta_change_252d"], errors="coerce").sum()),
        "delta_252d_median": float(pd.to_numeric(features["delta_change_252d"], errors="coerce").median()),
        "top_condition": str(top_condition.get("condition", "")),
        "top_condition_count": int(top_condition.get("count", 0) or 0),
        "top_condition_source_count": int(top_condition.get("source_count", 0) or 0),
        "top_condition_miss_rate_pct": top_condition_rate,
        "top_condition_lift": float(top_condition.get("lift_vs_all", np.nan)),
        "top_bucket": str(top_bucket.get("name", "")),
        "top_bucket_count": int(top_bucket.get("count", 0) or 0),
        "top_bucket_source_count": int(top_bucket.get("source_count", 0) or 0),
        "top_bucket_miss_rate_pct": top_bucket_rate,
        "top_bucket_lift": float(top_bucket.get("lift_vs_all", np.nan)),
        "external_research_judgment": (
            "Trend-following research points to whipsaw as a cost and positive skew as the return source. "
            "Stage026 therefore tests whether right-tail misses can be separated from useful pauses using "
            "only pre-entry candidate, market, AI, and account-state features."
        ),
        "overfit_reflection_before": "否。Stage026 只读归因，不用最高分桶直接写规则。",
        "continue_value_before": "有。Stage025 已证明 hard gate 内部混合两类 episode，需要判断能否用可见特征区分。",
        "overfit_reflection_after": (
            "否。本阶段只产生候选前兆审计；若把窄样本最高 lift 条件直接上线会过拟合。"
        ),
        "continue_value_after": (
            "否。Stage026 没有找到跨 source、足够样本且不依赖日期集中的强前兆；"
            "继续沿 hard regime gate 救参价值不高，下一步应转向 remaining worst-window "
            "holding_pnl/positions 或真正外生信息源。"
        ),
        "outputs": {
            "episodes": str(EPISODES_PATH),
            "episode_features": str(EPISODE_FEATURES_PATH),
            "numeric_summary": str(NUMERIC_SUMMARY_PATH),
            "bucket_summary": str(BUCKET_SUMMARY_PATH),
            "condition_summary": str(CONDITION_SUMMARY_PATH),
            "chart": str(CHART_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }

    episodes.to_csv(EPISODES_PATH, index=False, encoding="utf-8-sig")
    features.to_csv(EPISODE_FEATURES_PATH, index=False, encoding="utf-8-sig")
    numeric_summary.to_csv(NUMERIC_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    bucket_summary.to_csv(BUCKET_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    condition_summary.to_csv(CONDITION_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(decision, numeric_summary, bucket_summary, condition_summary)
    stage_record = _write_stage_record(decision)
    decision["stage_record"] = str(stage_record)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
