from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage543_ex_ante_product_selector_diagnostic_v1"
OUTPUT_PREFIX = "qmt_roll_stage543_ex_ante_product_selector_diagnostic"
LINE_ID = "futures_trend_drawdown30_preserve_return"

SLEEVE_CAPITAL = 115_000.0
TOP_KS = (3, 6)
FUTURE_HORIZONS = (60, 120)

STAGE541_TAG = "stage541_single_product_opportunity_map_v1"
STAGE541_PREFIX = "qmt_roll_stage541_single_product_opportunity_map"
STAGE541_SUMMARY_IN = OUTPUT_DIR / f"{STAGE541_PREFIX}_summary_{STAGE541_TAG}.csv"
STAGE541_DAILY_IN = OUTPUT_DIR / f"{STAGE541_PREFIX}_daily_{STAGE541_TAG}.csv"

STAGE526_TAG = "stage526_productcap25_breadth_frontier_v1"
STAGE526_PREFIX = "qmt_roll_stage526_productcap25_breadth_frontier"
STAGE526_DAILY_IN = OUTPUT_DIR / f"{STAGE526_PREFIX}_margin_daily_{STAGE526_TAG}.csv"
STAGE526_VARIANT = "r080_pc25_maxpos4"

WF_TAG = "product_suitability_full_market_wf_v1"
WF_PREFIX = "qmt_roll_ai_product_suitability_full_market_walkforward"
WF_PREDICTIONS_IN = OUTPUT_DIR / f"{WF_PREFIX}_predictions_{WF_TAG}.csv"

SCORED_SAMPLES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_scored_samples_{MODEL_TAG}.csv"
SELECTIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_selections_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
ORACLE_SELECTABILITY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_oracle_selectability_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"


SELECTOR_LABELS = {
    "ai_probability": "已有AI概率",
    "simple_trend": "已有simple趋势分",
    "market_terrain_equal": "市场地形等权",
    "strategy_memory_equal": "策略历史记忆等权",
    "hybrid_equal": "混合等权",
}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(result) or math.isinf(result):
        return default
    return result


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "无数据。"
    view = frame.copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda item: f"{item:.4f}" if pd.notna(item) else "")
    return view.to_markdown(index=False)


def _rolling_drawdown_abs(values: pd.Series, window: int) -> pd.Series:
    def _calc(items: np.ndarray) -> float:
        curve = np.cumsum(items)
        running_max = np.maximum.accumulate(curve)
        return float(np.min(curve - running_max))

    return values.rolling(window, min_periods=20).apply(_calc, raw=True)


def _future_sum(values: pd.Series, horizon: int) -> pd.Series:
    # At eval date t, use t+1...t+h. This keeps the selector side point-in-time.
    return values.shift(-1).rolling(horizon, min_periods=1).sum().shift(-(horizon - 1))


def _load_stage541() -> tuple[pd.DataFrame, pd.DataFrame, set[str], set[str]]:
    if not STAGE541_SUMMARY_IN.exists():
        raise FileNotFoundError(STAGE541_SUMMARY_IN)
    if not STAGE541_DAILY_IN.exists():
        raise FileNotFoundError(STAGE541_DAILY_IN)

    summary = pd.read_csv(STAGE541_SUMMARY_IN, encoding="utf-8-sig")
    summary["product_vt_symbol"] = summary["product_vt_symbol"].astype(str)
    summary["is_core_product"] = pd.to_numeric(summary["is_core_product"], errors="coerce").fillna(0).astype(int)
    summary["candidate_materiality_pass"] = (
        pd.to_numeric(summary["candidate_materiality_pass"], errors="coerce").fillna(0).astype(int)
    )
    noncore_products = set(summary.loc[summary["is_core_product"].eq(0), "product_vt_symbol"])
    oracle_products = set(summary.loc[summary["candidate_materiality_pass"].eq(1), "product_vt_symbol"])

    daily = pd.read_csv(STAGE541_DAILY_IN, encoding="utf-8-sig")
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.normalize()
    daily["product_vt_symbol"] = daily["product_vt_symbol"].astype(str)
    daily = daily[daily["product_vt_symbol"].isin(noncore_products)].copy()
    for column in ["net_pnl", "trade_count", "slippage"]:
        daily[column] = pd.to_numeric(daily[column], errors="coerce").fillna(0.0)
    daily.sort_values(["product_vt_symbol", "date"], inplace=True)
    return summary, daily, noncore_products, oracle_products


def _load_core_daily() -> pd.DataFrame:
    if not STAGE526_DAILY_IN.exists():
        raise FileNotFoundError(STAGE526_DAILY_IN)
    core = pd.read_csv(STAGE526_DAILY_IN, encoding="utf-8-sig")
    core = core[core["variant"].eq(STAGE526_VARIANT)].copy()
    core["date"] = pd.to_datetime(core["date"], errors="coerce").dt.normalize()
    core["core_net_pnl"] = pd.to_numeric(core["total_net_pnl"], errors="coerce").fillna(0.0)
    return core[["date", "core_net_pnl"]].dropna(subset=["date"]).sort_values("date")


def _build_daily_features(daily: pd.DataFrame, core_daily: pd.DataFrame) -> pd.DataFrame:
    merged = daily.merge(core_daily, on="date", how="left")
    merged["core_net_pnl"] = merged["core_net_pnl"].fillna(0.0)
    frames: list[pd.DataFrame] = []
    for product, frame in merged.groupby("product_vt_symbol", sort=False):
        item = frame.sort_values("date").reset_index(drop=True).copy()
        pnl = item["net_pnl"].astype(float)
        for window in (60, 120, 252):
            roll = pnl.rolling(window, min_periods=20)
            item[f"hist_pnl_{window}d"] = roll.sum().shift(1)
            std = roll.std(ddof=1).replace(0.0, np.nan)
            item[f"hist_sharpe_like_{window}d"] = (roll.mean() / std * math.sqrt(252.0)).shift(1)
            item[f"hist_active_days_{window}d"] = (pnl.abs() > 0).rolling(window, min_periods=20).sum().shift(1)
            item[f"hist_trade_count_{window}d"] = item["trade_count"].rolling(window, min_periods=20).sum().shift(1)
            item[f"hist_slippage_{window}d"] = item["slippage"].rolling(window, min_periods=20).sum().shift(1)
            item[f"hist_drawdown_{window}d"] = _rolling_drawdown_abs(pnl, window).shift(1)
        item["core_corr_252d"] = pnl.shift(1).rolling(252, min_periods=40).corr(item["core_net_pnl"].shift(1))
        for horizon in FUTURE_HORIZONS:
            item[f"future_stage541_pnl_{horizon}d"] = _future_sum(pnl, horizon)
        frames.append(item)
    featured = pd.concat(frames, ignore_index=True)
    feature_columns = [
        column
        for column in featured.columns
        if column.startswith("hist_") or column.startswith("future_stage541") or column == "core_corr_252d"
    ]
    featured[feature_columns] = featured[feature_columns].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return featured


def _rank_pct(frame: pd.DataFrame, column: str, *, lower_is_better: bool = False) -> pd.Series:
    values = pd.to_numeric(frame[column], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return values.groupby(frame["eval_date"]).rank(method="average", pct=True, ascending=not lower_is_better)


def _build_scored_samples(
    stage541_summary: pd.DataFrame,
    daily_features: pd.DataFrame,
    noncore_products: set[str],
    oracle_products: set[str],
) -> pd.DataFrame:
    if not WF_PREDICTIONS_IN.exists():
        raise FileNotFoundError(WF_PREDICTIONS_IN)
    predictions = pd.read_csv(WF_PREDICTIONS_IN, encoding="utf-8-sig")
    predictions["eval_date"] = pd.to_datetime(predictions["eval_date"], errors="coerce").dt.normalize()
    predictions["product_vt_symbol"] = predictions["product_vt_symbol"].astype(str)
    predictions = predictions[predictions["product_vt_symbol"].isin(noncore_products)].copy()

    static_columns = [
        "product_vt_symbol",
        "exchange",
        "product",
        "estimated_margin_per_contract",
        "recent_median_volume",
        "recent_bar_coverage_ratio",
        "max_broker10_margin_to_sleeve_equity_pct",
        "total_pnl",
        "candidate_materiality_pass",
    ]
    static = stage541_summary[[column for column in static_columns if column in stage541_summary.columns]].copy()
    samples = predictions.merge(static, on="product_vt_symbol", how="left")
    feature_slice = daily_features[
        [
            "date",
            "product_vt_symbol",
            "hist_pnl_60d",
            "hist_pnl_120d",
            "hist_pnl_252d",
            "hist_sharpe_like_120d",
            "hist_sharpe_like_252d",
            "hist_active_days_120d",
            "hist_trade_count_120d",
            "hist_drawdown_120d",
            "core_corr_252d",
            "future_stage541_pnl_60d",
            "future_stage541_pnl_120d",
        ]
    ].copy()
    samples = samples.merge(
        feature_slice,
        left_on=["eval_date", "product_vt_symbol"],
        right_on=["date", "product_vt_symbol"],
        how="left",
    )
    samples.drop(columns=["date"], inplace=True)

    numeric_columns = [
        "predicted_product_suitability_probability",
        "simple_trend_suitability_score_percentile",
        "market_trend_efficiency_60d",
        "market_trend_efficiency_120d",
        "market_realized_vol_60d",
        "market_range_pct_mean_60d",
        "market_volume_ratio_60d",
        "market_open_interest_change_60d",
        "market_ma20_over_ma60_60d",
        "estimated_margin_per_contract",
        "recent_median_volume",
        "recent_bar_coverage_ratio",
        "max_broker10_margin_to_sleeve_equity_pct",
        "total_pnl",
        "candidate_materiality_pass",
        "hist_pnl_60d",
        "hist_pnl_120d",
        "hist_pnl_252d",
        "hist_sharpe_like_120d",
        "hist_sharpe_like_252d",
        "hist_active_days_120d",
        "hist_trade_count_120d",
        "hist_drawdown_120d",
        "core_corr_252d",
        "future_stage541_pnl_60d",
        "future_stage541_pnl_120d",
    ]
    for column in numeric_columns:
        if column in samples.columns:
            samples[column] = pd.to_numeric(samples[column], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)

    high_good = [
        "predicted_product_suitability_probability",
        "simple_trend_suitability_score_percentile",
        "market_trend_efficiency_60d",
        "market_trend_efficiency_120d",
        "market_realized_vol_60d",
        "market_range_pct_mean_60d",
        "market_volume_ratio_60d",
        "market_open_interest_change_60d",
        "market_ma20_over_ma60_60d",
        "recent_median_volume",
        "recent_bar_coverage_ratio",
        "hist_pnl_60d",
        "hist_pnl_120d",
        "hist_pnl_252d",
        "hist_sharpe_like_120d",
        "hist_sharpe_like_252d",
        "hist_active_days_120d",
        "hist_trade_count_120d",
    ]
    for column in high_good:
        if column in samples.columns:
            samples[f"{column}_rank_pct"] = _rank_pct(samples, column)
    for column in ["estimated_margin_per_contract", "hist_drawdown_120d"]:
        samples[f"{column}_low_rank_pct"] = _rank_pct(samples, column, lower_is_better=True)
    samples["abs_core_corr_252d"] = samples["core_corr_252d"].abs().fillna(0.0)
    samples["low_core_corr_rank_pct"] = _rank_pct(samples, "abs_core_corr_252d", lower_is_better=True)

    samples["ai_probability"] = samples["predicted_product_suitability_probability"]
    samples["simple_trend"] = samples["simple_trend_suitability_score_percentile"]
    samples["market_terrain_equal"] = samples[
        [
            "market_trend_efficiency_60d_rank_pct",
            "market_trend_efficiency_120d_rank_pct",
            "market_realized_vol_60d_rank_pct",
            "market_range_pct_mean_60d_rank_pct",
            "market_volume_ratio_60d_rank_pct",
            "estimated_margin_per_contract_low_rank_pct",
            "low_core_corr_rank_pct",
        ]
    ].mean(axis=1)
    samples["strategy_memory_equal"] = samples[
        [
            "hist_pnl_60d_rank_pct",
            "hist_pnl_120d_rank_pct",
            "hist_pnl_252d_rank_pct",
            "hist_sharpe_like_120d_rank_pct",
            "hist_sharpe_like_252d_rank_pct",
            "hist_active_days_120d_rank_pct",
            "hist_drawdown_120d_low_rank_pct",
            "low_core_corr_rank_pct",
            "estimated_margin_per_contract_low_rank_pct",
        ]
    ].mean(axis=1)
    samples["hybrid_equal"] = samples[["simple_trend", "market_terrain_equal", "strategy_memory_equal"]].mean(axis=1)
    for selector in SELECTOR_LABELS:
        samples[f"{selector}_rank_pct"] = _rank_pct(samples, selector)
    samples["is_oracle6"] = samples["product_vt_symbol"].isin(oracle_products).astype(int)
    samples.sort_values(["eval_date", "product_vt_symbol"], inplace=True)
    samples.reset_index(drop=True, inplace=True)
    return samples


def _sample_dates(samples: pd.DataFrame, sample_type: str) -> list[pd.Timestamp]:
    dates = sorted(pd.to_datetime(samples["eval_date"].dropna().unique()))
    if sample_type == "monthly":
        return dates
    if sample_type == "quarterly_purged":
        quarterly = (
            pd.DataFrame({"eval_date": dates})
            .assign(quarter=lambda df: df["eval_date"].dt.to_period("Q"))
            .groupby("quarter")["eval_date"]
            .max()
            .tolist()
        )
        return sorted(pd.Timestamp(item) for item in quarterly)
    raise ValueError(sample_type)


def _evaluate_selectors(samples: pd.DataFrame, oracle_products: set[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    selection_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    samples = samples.copy()
    samples["future_rank_pct_60d_stage541"] = samples.groupby("eval_date")["future_stage541_pnl_60d"].rank(
        method="average", pct=True
    )
    samples["future_rank_pct_120d_stage541"] = samples.groupby("eval_date")["future_stage541_pnl_120d"].rank(
        method="average", pct=True
    )

    for sample_type in ("monthly", "quarterly_purged"):
        allowed_dates = set(_sample_dates(samples, sample_type))
        subset = samples[samples["eval_date"].isin(allowed_dates)].copy()
        for selector in SELECTOR_LABELS:
            for top_k in TOP_KS:
                month_rows: list[dict[str, Any]] = []
                for eval_date, frame in subset.groupby("eval_date", sort=True):
                    frame = frame.copy()
                    all_mean_60 = float(frame["future_stage541_pnl_60d"].mean())
                    all_mean_120 = float(frame["future_stage541_pnl_120d"].mean())
                    oracle_frame = frame[frame["product_vt_symbol"].isin(oracle_products)].copy()
                    oracle_mean_60 = float(oracle_frame["future_stage541_pnl_60d"].mean()) if not oracle_frame.empty else 0.0
                    oracle_mean_120 = float(oracle_frame["future_stage541_pnl_120d"].mean()) if not oracle_frame.empty else 0.0
                    selected = frame.sort_values([selector, "product_vt_symbol"], ascending=[False, True]).head(top_k).copy()
                    selected["selector"] = selector
                    selected["selector_label"] = SELECTOR_LABELS[selector]
                    selected["top_k"] = top_k
                    selected["sample_type"] = sample_type
                    selected["selected_rank"] = np.arange(1, len(selected) + 1)
                    selected["all_noncore_mean_future60"] = all_mean_60
                    selected["all_noncore_mean_future120"] = all_mean_120
                    selected["oracle6_mean_future60"] = oracle_mean_60
                    selected["oracle6_mean_future120"] = oracle_mean_120
                    selection_rows.extend(selected.to_dict("records"))

                    mean_60 = float(selected["future_stage541_pnl_60d"].mean()) if not selected.empty else 0.0
                    mean_120 = float(selected["future_stage541_pnl_120d"].mean()) if not selected.empty else 0.0
                    month_rows.append(
                        {
                            "selector": selector,
                            "selector_label": SELECTOR_LABELS[selector],
                            "top_k": top_k,
                            "sample_type": sample_type,
                            "eval_date": eval_date,
                            "selected_products": ",".join(selected["product_vt_symbol"].astype(str).tolist()),
                            "selected_mean_future60": mean_60,
                            "selected_mean_future120": mean_120,
                            "all_noncore_mean_future60": all_mean_60,
                            "all_noncore_mean_future120": all_mean_120,
                            "oracle6_mean_future60": oracle_mean_60,
                            "oracle6_mean_future120": oracle_mean_120,
                            "edge_vs_all_future60": mean_60 - all_mean_60,
                            "edge_vs_all_future120": mean_120 - all_mean_120,
                            "edge_vs_oracle6_future60": mean_60 - oracle_mean_60,
                            "edge_vs_oracle6_future120": mean_120 - oracle_mean_120,
                            "selected_oracle_count": int(selected["product_vt_symbol"].isin(oracle_products).sum()),
                            "avg_future_rank_pct_60d": float(selected["future_rank_pct_60d_stage541"].mean()),
                            "avg_future_rank_pct_120d": float(selected["future_rank_pct_120d_stage541"].mean()),
                        }
                    )
                month_df = pd.DataFrame(month_rows)
                if month_df.empty:
                    continue
                summary_rows.append(
                    {
                        "selector": selector,
                        "selector_label": SELECTOR_LABELS[selector],
                        "top_k": top_k,
                        "sample_type": sample_type,
                        "months": int(len(month_df)),
                        "avg_selected_mean_future60": float(month_df["selected_mean_future60"].mean()),
                        "avg_selected_mean_future120": float(month_df["selected_mean_future120"].mean()),
                        "avg_all_noncore_mean_future60": float(month_df["all_noncore_mean_future60"].mean()),
                        "avg_all_noncore_mean_future120": float(month_df["all_noncore_mean_future120"].mean()),
                        "avg_oracle6_mean_future60": float(month_df["oracle6_mean_future60"].mean()),
                        "avg_oracle6_mean_future120": float(month_df["oracle6_mean_future120"].mean()),
                        "avg_edge_vs_all_future60": float(month_df["edge_vs_all_future60"].mean()),
                        "avg_edge_vs_all_future120": float(month_df["edge_vs_all_future120"].mean()),
                        "avg_edge_vs_oracle6_future60": float(month_df["edge_vs_oracle6_future60"].mean()),
                        "avg_edge_vs_oracle6_future120": float(month_df["edge_vs_oracle6_future120"].mean()),
                        "positive_month_rate_future60_pct": float((month_df["selected_mean_future60"] > 0.0).mean() * 100.0),
                        "positive_month_rate_future120_pct": float((month_df["selected_mean_future120"] > 0.0).mean() * 100.0),
                        "avg_oracle_recall_count": float(month_df["selected_oracle_count"].mean()),
                        "at_least_one_oracle_month_rate_pct": float((month_df["selected_oracle_count"] > 0).mean() * 100.0),
                        "avg_future_rank_pct_60d": float(month_df["avg_future_rank_pct_60d"].mean()),
                        "avg_future_rank_pct_120d": float(month_df["avg_future_rank_pct_120d"].mean()),
                    }
                )
    selections = pd.DataFrame(selection_rows)
    summary = pd.DataFrame(summary_rows)
    if not summary.empty:
        summary["selected_vs_oracle_capture_ratio_60d"] = summary["avg_selected_mean_future60"] / summary[
            "avg_oracle6_mean_future60"
        ].replace(0.0, np.nan)
        summary["diagnostic_pass"] = (
            (summary["top_k"].eq(6))
            & (summary["sample_type"].eq("quarterly_purged"))
            & (summary["avg_edge_vs_all_future60"] >= 500.0)
            & (summary["selected_vs_oracle_capture_ratio_60d"] >= 0.50)
            & (summary["positive_month_rate_future60_pct"] >= 55.0)
            & (summary["avg_oracle_recall_count"] >= 2.0)
        ).astype(int)
        summary.sort_values(
            [
                "diagnostic_pass",
                "sample_type",
                "top_k",
                "avg_edge_vs_all_future60",
                "selected_vs_oracle_capture_ratio_60d",
            ],
            ascending=[False, True, False, False, False],
            inplace=True,
        )
    return selections, summary


def _build_oracle_selectability(samples: pd.DataFrame, oracle_products: set[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    oracle = samples[samples["product_vt_symbol"].isin(oracle_products)].copy()
    for product, product_frame in oracle.groupby("product_vt_symbol", sort=True):
        for selector in SELECTOR_LABELS:
            ranked = product_frame.sort_values("eval_date").copy()
            top6_threshold = 1 - 6 / 38
            top3_threshold = 1 - 3 / 38
            top6 = ranked[ranked[f"{selector}_rank_pct"] >= top6_threshold]
            first_top6 = top6["eval_date"].min() if not top6.empty else pd.NaT
            pre_2026 = ranked[ranked["eval_date"] < pd.Timestamp("2026-01-01")]
            rows.append(
                {
                    "product_vt_symbol": product,
                    "selector": selector,
                    "selector_label": SELECTOR_LABELS[selector],
                    "months": int(len(ranked)),
                    "avg_rank_pct": float(ranked[f"{selector}_rank_pct"].mean()),
                    "top6_month_rate_pct": float((ranked[f"{selector}_rank_pct"] >= top6_threshold).mean() * 100.0),
                    "top3_month_rate_pct": float((ranked[f"{selector}_rank_pct"] >= top3_threshold).mean() * 100.0),
                    "first_top6_date": first_top6,
                    "avg_future60": float(ranked["future_stage541_pnl_60d"].mean()),
                    "avg_future120": float(ranked["future_stage541_pnl_120d"].mean()),
                    "pre2026_avg_rank_pct": float(pre_2026[f"{selector}_rank_pct"].mean()) if not pre_2026.empty else 0.0,
                    "pre2026_avg_future60": float(pre_2026["future_stage541_pnl_60d"].mean()) if not pre_2026.empty else 0.0,
                }
            )
    result = pd.DataFrame(rows)
    if not result.empty:
        result.sort_values(["selector", "avg_rank_pct"], ascending=[True, False], inplace=True)
    return result


def _decision(summary: pd.DataFrame, oracle_selectability: pd.DataFrame, oracle_products: set[str]) -> dict[str, Any]:
    passed = summary[summary["diagnostic_pass"].eq(1)].copy() if "diagnostic_pass" in summary.columns else pd.DataFrame()
    best_pool = summary[(summary["sample_type"].eq("quarterly_purged")) & (summary["top_k"].eq(6))].copy()
    if best_pool.empty:
        best_pool = summary.copy()
    best = best_pool.sort_values(["avg_edge_vs_all_future60", "selected_vs_oracle_capture_ratio_60d"], ascending=False).head(1)
    best_record = best.iloc[0].to_dict() if not best.empty else {}
    selector_oracle_view = (
        oracle_selectability.groupby("selector")
        .agg(
            avg_oracle_rank_pct=("avg_rank_pct", "mean"),
            avg_oracle_top6_month_rate_pct=("top6_month_rate_pct", "mean"),
            pre2026_avg_oracle_rank_pct=("pre2026_avg_rank_pct", "mean"),
        )
        .reset_index()
        .sort_values("avg_oracle_rank_pct", ascending=False)
        .to_dict("records")
        if not oracle_selectability.empty
        else []
    )
    return {
        "stage": "Stage243",
        "script_stage": "Stage543",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": (
            "ex_ante_selector_candidates_for_formal_sleeve_backtest"
            if not passed.empty
            else "ex_ante_selector_not_ready_keep_oracle_as_upper_bound"
        ),
        "baseline": "Stage526 r080_pc25_maxpos4 + Stage542 Oracle6 upper bound",
        "oracle_products": sorted(oracle_products),
        "pass_definition": (
            "Top6 quarterly-purged selector must beat all-noncore future60 mean by >=500 yuan/product, "
            "capture >=50% of Oracle6 future60 mean, have >55% positive 60d months, and average >=2 Oracle6 products selected."
        ),
        "passed_rows": passed.to_dict("records"),
        "best_row": best_record,
        "selector_oracle_selectability": selector_oracle_view,
        "overfit_boundary": (
            "No product is promoted here. The selector uses only existing walk-forward predictions and pre-eval single-product ledger features; "
            "Oracle6 labels are used only for recall/selectability diagnostics."
        ),
        "next_step": (
            "If no pass, do not formalize Oracle6. Build a stronger point-in-time selector with fundamental availability, product-family risk budgets, "
            "and then run a dynamic formal sleeve only after ex-ante diagnostics improve."
        ),
    }


def _plot(samples: pd.DataFrame, selections: pd.DataFrame, summary: pd.DataFrame, oracle_products: set[str], decision: dict[str, Any]) -> None:
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(2, 2, figsize=(16, 9))
    ax_edge, ax_recall, ax_cum, ax_heat = axes.flatten()

    view = summary[(summary["top_k"].eq(6)) & (summary["sample_type"].isin(["monthly", "quarterly_purged"]))].copy()
    view["selector_short"] = view["selector"].map(SELECTOR_LABELS)
    pivot = view.pivot(index="selector_short", columns="sample_type", values="avg_edge_vs_all_future60").reindex(
        [SELECTOR_LABELS[item] for item in SELECTOR_LABELS]
    )
    pivot.plot(kind="barh", ax=ax_edge, color=["#64748b", "#2563eb"])
    ax_edge.axvline(0, color="#111827", linewidth=1, linestyle="--")
    ax_edge.axvline(500, color="#dc2626", linewidth=1, linestyle=":")
    ax_edge.set_title("Top6 future60 edge vs all noncore")
    ax_edge.grid(axis="x", alpha=0.25)
    ax_edge.legend(fontsize=8)

    recall = view.pivot(index="selector_short", columns="sample_type", values="avg_oracle_recall_count").reindex(
        [SELECTOR_LABELS[item] for item in SELECTOR_LABELS]
    )
    recall.plot(kind="barh", ax=ax_recall, color=["#94a3b8", "#059669"])
    ax_recall.axvline(2.0, color="#dc2626", linewidth=1, linestyle=":")
    ax_recall.set_title("Average Oracle6 names inside Top6")
    ax_recall.grid(axis="x", alpha=0.25)
    ax_recall.legend(fontsize=8)

    monthly_top6 = selections[(selections["top_k"].eq(6)) & (selections["sample_type"].eq("quarterly_purged"))].copy()
    if not monthly_top6.empty:
        for selector in SELECTOR_LABELS:
            series = (
                monthly_top6[monthly_top6["selector"].eq(selector)]
                .groupby("eval_date")["future_stage541_pnl_60d"]
                .mean()
                .sort_index()
                .cumsum()
            )
            ax_cum.plot(series.index, series.values, label=SELECTOR_LABELS[selector], linewidth=1.0)
        oracle_series = (
            samples[samples["product_vt_symbol"].isin(oracle_products)]
            .groupby("eval_date")["future_stage541_pnl_60d"]
            .mean()
            .loc[_sample_dates(samples, "quarterly_purged")]
            .sort_index()
            .cumsum()
        )
        all_series = (
            samples.groupby("eval_date")["future_stage541_pnl_60d"]
            .mean()
            .loc[_sample_dates(samples, "quarterly_purged")]
            .sort_index()
            .cumsum()
        )
        ax_cum.plot(oracle_series.index, oracle_series.values, label="Oracle6 reference", color="#dc2626", linewidth=1.5)
        ax_cum.plot(all_series.index, all_series.values, label="All noncore mean", color="#111827", linewidth=1.0, linestyle="--")
    ax_cum.axhline(0, color="#111827", linewidth=1, linestyle="--")
    ax_cum.set_title("Quarterly diagnostic cumulative future60 mean")
    ax_cum.grid(alpha=0.25)
    ax_cum.legend(fontsize=7)

    heat = samples[samples["product_vt_symbol"].isin(oracle_products)].copy()
    if not heat.empty:
        heat["date_label"] = heat["eval_date"].dt.strftime("%Y-%m")
        pivot_heat = heat.pivot(index="product_vt_symbol", columns="date_label", values="hybrid_equal_rank_pct").reindex(
            sorted(oracle_products)
        )
        image = ax_heat.imshow(pivot_heat.to_numpy(dtype=float), aspect="auto", cmap="RdYlGn", vmin=0.0, vmax=1.0)
        ax_heat.set_yticks(np.arange(len(pivot_heat.index)))
        ax_heat.set_yticklabels(pivot_heat.index)
        step = max(1, len(pivot_heat.columns) // 8)
        ax_heat.set_xticks(np.arange(0, len(pivot_heat.columns), step))
        ax_heat.set_xticklabels(pivot_heat.columns[::step], rotation=45, ha="right")
        ax_heat.set_title("Oracle6 hybrid rank percentile by month")
        fig.colorbar(image, ax=ax_heat, fraction=0.046, pad=0.04)

    fig.suptitle(f"Stage543 decision: {decision['decision']}", fontsize=12)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _write_report(summary: pd.DataFrame, oracle_selectability: pd.DataFrame, decision: dict[str, Any]) -> None:
    top6 = summary[(summary["top_k"].eq(6))].copy()
    top6_view = top6[
        [
            "selector_label",
            "sample_type",
            "months",
            "avg_selected_mean_future60",
            "avg_edge_vs_all_future60",
            "avg_oracle6_mean_future60",
            "selected_vs_oracle_capture_ratio_60d",
            "positive_month_rate_future60_pct",
            "avg_oracle_recall_count",
            "diagnostic_pass",
        ]
    ].sort_values(["sample_type", "avg_edge_vs_all_future60"], ascending=[True, False])
    oracle_view = (
        oracle_selectability[oracle_selectability["selector"].eq("hybrid_equal")][
            [
                "product_vt_symbol",
                "avg_rank_pct",
                "top6_month_rate_pct",
                "pre2026_avg_rank_pct",
                "avg_future60",
                "pre2026_avg_future60",
            ]
        ].sort_values("avg_rank_pct", ascending=False)
        if not oracle_selectability.empty
        else pd.DataFrame()
    )
    lines = [
        "# Stage543 事前选品诊断",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- 决策：`{decision['decision']}`。",
        "- 阶段性质：只读诊断；不新增交易规则，不把 Oracle6 直接晋级。",
        "- 核心问题：Stage241/242 的 `lu/v/al/y/c/ao` 是否能被当时可见数据提前选出。",
        "",
        "## 通过定义",
        "",
        decision["pass_definition"],
        "",
        "## Top6 选择器摘要",
        "",
        _md_table(top6_view),
        "",
        "## Oracle6 混合分可选性",
        "",
        _md_table(oracle_view),
        "",
        "## 判断",
        "",
        "- 如果一个选择器只比全非核心均值略好，但远低于 Oracle6 参考，并且 Oracle6 召回不足，就不能把 hindsight 上限变成实盘篮子。",
        "- 本阶段使用的历史策略账本特征全部滞后一日，已有 AI 概率来自 walk-forward 预测；Oracle6 只作为 recall 标签，不进入打分。",
        "- 这里仍不是正式组合回测。只有当事前选择器明显通过诊断，才值得进入动态 universe sleeve 的真实引擎 A/C。",
        "",
        "## 输出文件",
        "",
        f"- scored samples：`{SCORED_SAMPLES_PATH}`",
        f"- selections：`{SELECTIONS_PATH}`",
        f"- summary：`{SUMMARY_PATH}`",
        f"- oracle selectability：`{ORACLE_SELECTABILITY_PATH}`",
        f"- decision：`{DECISION_PATH}`",
        f"- chart：`{CHART_PATH}`",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stage541_summary, stage541_daily, noncore_products, oracle_products = _load_stage541()
    core_daily = _load_core_daily()
    daily_features = _build_daily_features(stage541_daily, core_daily)
    scored = _build_scored_samples(stage541_summary, daily_features, noncore_products, oracle_products)
    selections, summary = _evaluate_selectors(scored, oracle_products)
    oracle_selectability = _build_oracle_selectability(scored, oracle_products)
    decision = _decision(summary, oracle_selectability, oracle_products)

    scored.to_csv(SCORED_SAMPLES_PATH, index=False, encoding="utf-8-sig")
    selections.to_csv(SELECTIONS_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    oracle_selectability.to_csv(ORACLE_SELECTABILITY_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _plot(scored, selections, summary, oracle_products, decision)
    _write_report(summary, oracle_selectability, decision)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
