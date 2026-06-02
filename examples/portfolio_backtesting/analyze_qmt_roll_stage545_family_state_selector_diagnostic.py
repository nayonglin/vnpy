from __future__ import annotations

from dataclasses import dataclass
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

MODEL_TAG = "stage545_family_state_selector_diagnostic_v1"
OUTPUT_PREFIX = "qmt_roll_stage545_family_state_selector_diagnostic"
LINE_ID = "futures_trend_drawdown30_preserve_return"

STAGE543_TAG = "stage543_ex_ante_product_selector_diagnostic_v1"
STAGE543_PREFIX = "qmt_roll_stage543_ex_ante_product_selector_diagnostic"
STAGE543_SCORED_IN = OUTPUT_DIR / f"{STAGE543_PREFIX}_scored_samples_{STAGE543_TAG}.csv"

STAGE544_TAG = "stage544_family_constrained_selector_diagnostic_v1"
STAGE544_PREFIX = "qmt_roll_stage544_family_constrained_selector_diagnostic"
STAGE544_FAMILY_MAP_IN = OUTPUT_DIR / f"{STAGE544_PREFIX}_family_map_{STAGE544_TAG}.csv"
STAGE544_SELECTIONS_IN = OUTPUT_DIR / f"{STAGE544_PREFIX}_selections_{STAGE544_TAG}.csv"

FAMILY_SCORES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_family_scores_{MODEL_TAG}.csv"
SELECTIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_selections_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
FAMILY_SIGNAL_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_family_signal_summary_{MODEL_TAG}.csv"
FAMILY_CONTRIBUTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_family_contribution_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

TOP_K = 6
LOW_CORE_CORR_THRESHOLD = 0.30
HARD_EDGE_THRESHOLD = 500.0
HARD_CAPTURE_RATIO = 0.50
HARD_POSITIVE_MONTH_RATE = 55.0


@dataclass(frozen=True)
class SelectorMode:
    mode: str
    label: str
    family_score_column: str
    product_score_column: str
    family_count: int
    family_cap: int
    low_core_corr_threshold: float | None
    rationale: str


MODES: tuple[SelectorMode, ...] = (
    SelectorMode(
        "family_trend_state_best1",
        "产品族趋势土壤+族内1品种",
        "family_trend_state_score",
        "product_trend_state_score",
        TOP_K,
        1,
        None,
        "先选趋势效率/突破/趋势广度更好的产品族，再在族内选低相关且趋势分高的品种。",
    ),
    SelectorMode(
        "family_memory_state_best1",
        "产品族历史记忆+族内1品种",
        "family_memory_state_score",
        "product_memory_state_score",
        TOP_K,
        1,
        None,
        "先选近期策略账本更好的产品族，再在族内选历史记忆分高的品种。",
    ),
    SelectorMode(
        "family_flow_state_best1",
        "产品族量仓参与+族内1品种",
        "family_flow_state_score",
        "product_flow_state_score",
        TOP_K,
        1,
        None,
        "用成交量、持仓量变化和流动性作为趋势参与度代理。",
    ),
    SelectorMode(
        "family_blend_state_best1",
        "产品族综合状态+族内1品种",
        "family_blend_state_score",
        "product_blend_state_score",
        TOP_K,
        1,
        None,
        "趋势土壤、策略记忆、量仓参与和低核心相关的固定等方向融合。",
    ),
    SelectorMode(
        "family_blend_state_lowcorr030",
        "综合状态+低核心相关",
        "family_blend_state_score",
        "product_blend_state_score",
        TOP_K,
        1,
        LOW_CORE_CORR_THRESHOLD,
        "在综合状态基础上优先要求与Stage526核心252日相关绝对值不高于0.30。",
    ),
    SelectorMode(
        "family_blend_state_top4_cap2",
        "综合状态Top4族+族内2品种",
        "family_blend_state_score",
        "product_blend_state_score",
        4,
        2,
        LOW_CORE_CORR_THRESHOLD,
        "允许强状态产品族最多2个品种，检验族内第二名是否比强行六族分散更好。",
    ),
)

FAMILY_SCORE_COLUMNS = (
    "family_trend_state_score",
    "family_memory_state_score",
    "family_flow_state_score",
    "family_lowcorr_state_score",
    "family_blend_state_score",
)


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


def _rank_pct(frame: pd.DataFrame, column: str, *, lower_is_better: bool = False) -> pd.Series:
    values = pd.to_numeric(frame[column], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return values.groupby(frame["eval_date"]).rank(method="average", pct=True, ascending=not lower_is_better)


def _ensure_rank(samples: pd.DataFrame, column: str, *, source: str | None = None, lower_is_better: bool = False) -> str:
    rank_column = f"{column}_rank_pct"
    if rank_column in samples.columns:
        return rank_column
    raw_column = source or column
    if raw_column not in samples.columns:
        samples[raw_column] = 0.0
    samples[rank_column] = _rank_pct(samples, raw_column, lower_is_better=lower_is_better)
    return rank_column


def _sample_dates(samples: pd.DataFrame, sample_type: str) -> list[pd.Timestamp]:
    dates = sorted(pd.Timestamp(item) for item in samples["eval_date"].dropna().unique())
    if sample_type == "monthly":
        return dates
    if sample_type == "quarterly_purged":
        return sorted(
            pd.DataFrame({"eval_date": dates})
            .assign(quarter=lambda df: df["eval_date"].dt.to_period("Q"))
            .groupby("quarter")["eval_date"]
            .max()
            .map(pd.Timestamp)
            .tolist()
        )
    raise ValueError(sample_type)


def _load_samples() -> pd.DataFrame:
    if not STAGE543_SCORED_IN.exists():
        raise FileNotFoundError(STAGE543_SCORED_IN)
    if not STAGE544_FAMILY_MAP_IN.exists():
        raise FileNotFoundError(STAGE544_FAMILY_MAP_IN)

    samples = pd.read_csv(STAGE543_SCORED_IN, encoding="utf-8-sig")
    samples["eval_date"] = pd.to_datetime(samples["eval_date"], errors="coerce").dt.normalize()
    samples["product_vt_symbol"] = samples["product_vt_symbol"].astype(str)

    family_map = pd.read_csv(STAGE544_FAMILY_MAP_IN, encoding="utf-8-sig")
    family_map["product_vt_symbol"] = family_map["product_vt_symbol"].astype(str)
    samples = samples.merge(family_map[["product_vt_symbol", "product_family", "family_note"]], on="product_vt_symbol", how="left")
    samples["product_family"] = samples["product_family"].fillna("unknown")
    samples["family_note"] = samples["family_note"].fillna("未分类")

    numeric_columns = [
        "ai_probability",
        "simple_trend",
        "market_terrain_equal",
        "strategy_memory_equal",
        "hybrid_equal",
        "low_core_corr_rank_pct",
        "abs_core_corr_252d",
        "is_oracle6",
        "future_stage541_pnl_60d",
        "future_stage541_pnl_120d",
        "market_trend_efficiency_60d",
        "market_trend_efficiency_120d",
        "market_breakout_rate_60d",
        "market_ret_60d",
        "market_ret_120d",
        "market_volume_ratio_60d",
        "market_volume_zscore_60d",
        "market_open_interest_change_60d",
        "market_open_interest_zscore_60d",
        "recent_median_volume",
        "recent_bar_coverage_ratio",
        "estimated_margin_per_contract",
        "hist_pnl_60d",
        "hist_pnl_120d",
        "hist_sharpe_like_120d",
        "hist_active_days_120d",
        "hist_trade_count_120d",
        "hist_drawdown_120d",
    ]
    for column in numeric_columns:
        if column not in samples.columns:
            samples[column] = 0.0
        samples[column] = pd.to_numeric(samples[column], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0)

    samples["abs_market_ret_60d"] = samples["market_ret_60d"].abs()
    samples["abs_market_ret_120d"] = samples["market_ret_120d"].abs()

    rank_columns = {
        "trend_eff_60": _ensure_rank(samples, "market_trend_efficiency_60d"),
        "trend_eff_120": _ensure_rank(samples, "market_trend_efficiency_120d"),
        "breakout_60": _ensure_rank(samples, "market_breakout_rate_60d"),
        "abs_ret_60": _ensure_rank(samples, "abs_market_ret_60d"),
        "abs_ret_120": _ensure_rank(samples, "abs_market_ret_120d"),
        "volume_ratio_60": _ensure_rank(samples, "market_volume_ratio_60d"),
        "volume_z_60": _ensure_rank(samples, "market_volume_zscore_60d"),
        "oi_change_60": _ensure_rank(samples, "market_open_interest_change_60d"),
        "oi_z_60": _ensure_rank(samples, "market_open_interest_zscore_60d"),
        "liquidity": _ensure_rank(samples, "recent_median_volume"),
        "coverage": _ensure_rank(samples, "recent_bar_coverage_ratio"),
        "low_margin": _ensure_rank(samples, "estimated_margin_per_contract_low", source="estimated_margin_per_contract", lower_is_better=True),
        "hist_pnl_60": _ensure_rank(samples, "hist_pnl_60d"),
        "hist_pnl_120": _ensure_rank(samples, "hist_pnl_120d"),
        "hist_sharpe_120": _ensure_rank(samples, "hist_sharpe_like_120d"),
        "hist_active_120": _ensure_rank(samples, "hist_active_days_120d"),
        "hist_trade_120": _ensure_rank(samples, "hist_trade_count_120d"),
        "hist_drawdown_120_low": _ensure_rank(samples, "hist_drawdown_120d_low", source="hist_drawdown_120d", lower_is_better=True),
        "low_core_corr": _ensure_rank(samples, "abs_core_corr_252d_low", source="abs_core_corr_252d", lower_is_better=True),
    }
    if "low_core_corr_rank_pct" not in samples.columns or samples["low_core_corr_rank_pct"].eq(0.0).all():
        samples["low_core_corr_rank_pct"] = samples[rank_columns["low_core_corr"]]

    samples["product_trend_state_score"] = samples[
        [
            "simple_trend",
            "market_terrain_equal",
            rank_columns["trend_eff_60"],
            rank_columns["trend_eff_120"],
            rank_columns["breakout_60"],
            rank_columns["abs_ret_60"],
            "low_core_corr_rank_pct",
        ]
    ].mean(axis=1)
    samples["product_memory_state_score"] = samples[
        [
            "strategy_memory_equal",
            rank_columns["hist_pnl_60"],
            rank_columns["hist_pnl_120"],
            rank_columns["hist_sharpe_120"],
            rank_columns["hist_drawdown_120_low"],
            "low_core_corr_rank_pct",
        ]
    ].mean(axis=1)
    samples["product_flow_state_score"] = samples[
        [
            "market_terrain_equal",
            rank_columns["volume_ratio_60"],
            rank_columns["volume_z_60"],
            rank_columns["oi_change_60"],
            rank_columns["oi_z_60"],
            rank_columns["liquidity"],
            "low_core_corr_rank_pct",
        ]
    ].mean(axis=1)
    samples["product_blend_state_score"] = (
        0.35 * samples["product_trend_state_score"]
        + 0.30 * samples["product_memory_state_score"]
        + 0.20 * samples["product_flow_state_score"]
        + 0.15 * samples["low_core_corr_rank_pct"]
    )

    samples["trend_breadth_flag"] = (samples["simple_trend"] >= 0.60).astype(float)
    samples["memory_breadth_flag"] = (samples["strategy_memory_equal"] >= 0.60).astype(float)
    samples["lowcorr_breadth_flag"] = (samples["abs_core_corr_252d"] <= LOW_CORE_CORR_THRESHOLD).astype(float)

    group_cols = ["eval_date", "product_family"]
    family = (
        samples.groupby(group_cols, as_index=False)
        .agg(
            family_product_count=("product_vt_symbol", "count"),
            family_oracle_count=("is_oracle6", "sum"),
            family_future60_mean=("future_stage541_pnl_60d", "mean"),
            family_future120_mean=("future_stage541_pnl_120d", "mean"),
            family_simple_mean=("simple_trend", "mean"),
            family_market_terrain_mean=("market_terrain_equal", "mean"),
            family_memory_mean=("strategy_memory_equal", "mean"),
            family_hybrid_mean=("hybrid_equal", "mean"),
            family_trend_eff60_mean=(rank_columns["trend_eff_60"], "mean"),
            family_trend_eff120_mean=(rank_columns["trend_eff_120"], "mean"),
            family_breakout60_mean=(rank_columns["breakout_60"], "mean"),
            family_abs_ret60_mean=(rank_columns["abs_ret_60"], "mean"),
            family_abs_ret120_mean=(rank_columns["abs_ret_120"], "mean"),
            family_volume_ratio60_mean=(rank_columns["volume_ratio_60"], "mean"),
            family_volume_z60_mean=(rank_columns["volume_z_60"], "mean"),
            family_oi_change60_mean=(rank_columns["oi_change_60"], "mean"),
            family_oi_z60_mean=(rank_columns["oi_z_60"], "mean"),
            family_liquidity_mean=(rank_columns["liquidity"], "mean"),
            family_coverage_mean=(rank_columns["coverage"], "mean"),
            family_low_margin_mean=(rank_columns["low_margin"], "mean"),
            family_hist_pnl60_mean=(rank_columns["hist_pnl_60"], "mean"),
            family_hist_pnl120_mean=(rank_columns["hist_pnl_120"], "mean"),
            family_hist_sharpe120_mean=(rank_columns["hist_sharpe_120"], "mean"),
            family_hist_active120_mean=(rank_columns["hist_active_120"], "mean"),
            family_hist_drawdown120_low_mean=(rank_columns["hist_drawdown_120_low"], "mean"),
            family_lowcorr_mean=("low_core_corr_rank_pct", "mean"),
            family_avg_abs_core_corr=("abs_core_corr_252d", "mean"),
            family_trend_breadth=("trend_breadth_flag", "mean"),
            family_memory_breadth=("memory_breadth_flag", "mean"),
            family_lowcorr_breadth=("lowcorr_breadth_flag", "mean"),
        )
        .sort_values(group_cols)
    )
    family["family_trend_state_score"] = family[
        [
            "family_simple_mean",
            "family_market_terrain_mean",
            "family_trend_eff60_mean",
            "family_trend_eff120_mean",
            "family_breakout60_mean",
            "family_abs_ret60_mean",
            "family_trend_breadth",
        ]
    ].mean(axis=1)
    family["family_memory_state_score"] = family[
        [
            "family_memory_mean",
            "family_hybrid_mean",
            "family_hist_pnl60_mean",
            "family_hist_pnl120_mean",
            "family_hist_sharpe120_mean",
            "family_hist_drawdown120_low_mean",
            "family_memory_breadth",
        ]
    ].mean(axis=1)
    family["family_flow_state_score"] = family[
        [
            "family_volume_ratio60_mean",
            "family_volume_z60_mean",
            "family_oi_change60_mean",
            "family_oi_z60_mean",
            "family_liquidity_mean",
            "family_coverage_mean",
        ]
    ].mean(axis=1)
    family["family_lowcorr_state_score"] = family[["family_lowcorr_mean", "family_lowcorr_breadth", "family_low_margin_mean"]].mean(axis=1)
    family["family_blend_state_score"] = (
        0.35 * family["family_trend_state_score"]
        + 0.30 * family["family_memory_state_score"]
        + 0.20 * family["family_flow_state_score"]
        + 0.15 * family["family_lowcorr_state_score"]
    )

    samples = samples.merge(
        family[
            [
                "eval_date",
                "product_family",
                "family_product_count",
                "family_oracle_count",
                "family_future60_mean",
                "family_future120_mean",
                *FAMILY_SCORE_COLUMNS,
                "family_avg_abs_core_corr",
                "family_trend_breadth",
                "family_memory_breadth",
                "family_lowcorr_breadth",
            ]
        ],
        on=["eval_date", "product_family"],
        how="left",
    )
    return samples, family


def _select(frame: pd.DataFrame, mode: SelectorMode) -> pd.DataFrame:
    family_order = (
        frame[["product_family", mode.family_score_column, "family_avg_abs_core_corr"]]
        .drop_duplicates("product_family")
        .sort_values([mode.family_score_column, "family_avg_abs_core_corr", "product_family"], ascending=[False, True, True])
    )
    chosen: list[pd.Series] = []
    family_counts: dict[str, int] = {}

    def _try_take(candidates: pd.DataFrame, *, enforce_corr: bool) -> None:
        nonlocal chosen
        for _, row in candidates.iterrows():
            family = str(row["product_family"])
            if family_counts.get(family, 0) >= mode.family_cap:
                continue
            if enforce_corr and mode.low_core_corr_threshold is not None and float(row["abs_core_corr_252d"]) > mode.low_core_corr_threshold:
                continue
            chosen.append(row)
            family_counts[family] = family_counts.get(family, 0) + 1
            if len(chosen) >= TOP_K:
                break

    for _, family_row in family_order.head(mode.family_count).iterrows():
        family = str(family_row["product_family"])
        candidates = frame[frame["product_family"].eq(family)].sort_values(
            [mode.product_score_column, "abs_core_corr_252d", "product_vt_symbol"],
            ascending=[False, True, True],
        )
        _try_take(candidates, enforce_corr=True)
        if len(chosen) >= TOP_K:
            break

    if len(chosen) < TOP_K and mode.low_core_corr_threshold is not None:
        already = {str(item["product_vt_symbol"]) for item in chosen}
        for _, family_row in family_order.head(mode.family_count).iterrows():
            family = str(family_row["product_family"])
            candidates = frame[
                frame["product_family"].eq(family) & ~frame["product_vt_symbol"].astype(str).isin(already)
            ].sort_values(
                [mode.product_score_column, "abs_core_corr_252d", "product_vt_symbol"],
                ascending=[False, True, True],
            )
            _try_take(candidates, enforce_corr=False)
            if len(chosen) >= TOP_K:
                break

    if len(chosen) < TOP_K:
        already = {str(item["product_vt_symbol"]) for item in chosen}
        fallback = frame[~frame["product_vt_symbol"].astype(str).isin(already)].sort_values(
            [mode.family_score_column, mode.product_score_column, "abs_core_corr_252d", "product_vt_symbol"],
            ascending=[False, False, True, True],
        )
        _try_take(fallback, enforce_corr=False)

    selected = pd.DataFrame(chosen)
    if selected.empty:
        return selected
    selected = selected.head(TOP_K).reset_index(drop=True)
    selected["selected_rank"] = np.arange(1, len(selected) + 1)
    selected["selected_family_rank"] = selected["product_family"].map(
        {family: rank for rank, family in enumerate(family_order["product_family"].astype(str).tolist(), start=1)}
    )
    selected["family_cap"] = mode.family_cap
    selected["family_count_target"] = mode.family_count
    selected["low_core_corr_filter"] = mode.low_core_corr_threshold if mode.low_core_corr_threshold is not None else np.nan
    return selected


def _evaluate(samples: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    selection_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    contribution_rows: list[dict[str, Any]] = []

    for sample_type in ("monthly", "quarterly_purged"):
        allowed_dates = set(_sample_dates(samples, sample_type))
        subset = samples[samples["eval_date"].isin(allowed_dates)].copy()
        for mode in MODES:
            eval_rows: list[dict[str, Any]] = []
            for eval_date, frame in subset.groupby("eval_date", sort=True):
                selected = _select(frame, mode)
                if selected.empty:
                    continue
                all_mean60 = float(frame["future_stage541_pnl_60d"].mean())
                all_mean120 = float(frame["future_stage541_pnl_120d"].mean())
                oracle = frame[frame["is_oracle6"].eq(1)].copy()
                oracle_mean60 = float(oracle["future_stage541_pnl_60d"].mean())
                oracle_mean120 = float(oracle["future_stage541_pnl_120d"].mean())
                selected_mean60 = float(selected["future_stage541_pnl_60d"].mean())
                selected_mean120 = float(selected["future_stage541_pnl_120d"].mean())
                family_unique_count = int(selected["product_family"].nunique())
                family_max_count = int(selected["product_family"].value_counts().max())

                selected = selected.copy()
                selected["mode"] = mode.mode
                selected["mode_label"] = mode.label
                selected["sample_type"] = sample_type
                selected["all_noncore_mean_future60"] = all_mean60
                selected["all_noncore_mean_future120"] = all_mean120
                selected["oracle6_mean_future60"] = oracle_mean60
                selected["oracle6_mean_future120"] = oracle_mean120
                selection_rows.extend(selected.to_dict("records"))

                eval_rows.append(
                    {
                        "mode": mode.mode,
                        "mode_label": mode.label,
                        "family_score_column": mode.family_score_column,
                        "product_score_column": mode.product_score_column,
                        "sample_type": sample_type,
                        "eval_date": eval_date,
                        "selected_products": ",".join(selected["product_vt_symbol"].astype(str).tolist()),
                        "selected_families": ",".join(selected["product_family"].astype(str).tolist()),
                        "selected_mean_future60": selected_mean60,
                        "selected_mean_future120": selected_mean120,
                        "all_noncore_mean_future60": all_mean60,
                        "all_noncore_mean_future120": all_mean120,
                        "oracle6_mean_future60": oracle_mean60,
                        "oracle6_mean_future120": oracle_mean120,
                        "edge_vs_all_future60": selected_mean60 - all_mean60,
                        "edge_vs_all_future120": selected_mean120 - all_mean120,
                        "selected_oracle_count": int(selected["is_oracle6"].sum()),
                        "family_unique_count": family_unique_count,
                        "family_max_count": family_max_count,
                        "avg_abs_core_corr": float(selected["abs_core_corr_252d"].mean()),
                        "avg_family_state_score": float(selected[mode.family_score_column].mean()),
                    }
                )
                family_counts = selected.groupby("product_family", as_index=False).agg(
                    selected_count=("product_vt_symbol", "count"),
                    selected_future60_sum=("future_stage541_pnl_60d", "sum"),
                    selected_future120_sum=("future_stage541_pnl_120d", "sum"),
                    selected_oracle_count=("is_oracle6", "sum"),
                    avg_family_state_score=(mode.family_score_column, "mean"),
                )
                for _, row in family_counts.iterrows():
                    contribution_rows.append(
                        {
                            "mode": mode.mode,
                            "mode_label": mode.label,
                            "sample_type": sample_type,
                            "eval_date": eval_date,
                            "product_family": row["product_family"],
                            "selected_count": int(row["selected_count"]),
                            "selected_oracle_count": int(row["selected_oracle_count"]),
                            "selected_future60_sum": float(row["selected_future60_sum"]),
                            "selected_future120_sum": float(row["selected_future120_sum"]),
                            "avg_family_state_score": float(row["avg_family_state_score"]),
                        }
                    )
            eval_df = pd.DataFrame(eval_rows)
            if eval_df.empty:
                continue
            avg_oracle60 = float(eval_df["oracle6_mean_future60"].mean())
            avg_selected60 = float(eval_df["selected_mean_future60"].mean())
            summary_rows.append(
                {
                    "mode": mode.mode,
                    "mode_label": mode.label,
                    "family_score_column": mode.family_score_column,
                    "product_score_column": mode.product_score_column,
                    "sample_type": sample_type,
                    "months": int(len(eval_df)),
                    "avg_selected_mean_future60": avg_selected60,
                    "avg_selected_mean_future120": float(eval_df["selected_mean_future120"].mean()),
                    "avg_all_noncore_mean_future60": float(eval_df["all_noncore_mean_future60"].mean()),
                    "avg_all_noncore_mean_future120": float(eval_df["all_noncore_mean_future120"].mean()),
                    "avg_oracle6_mean_future60": avg_oracle60,
                    "avg_oracle6_mean_future120": float(eval_df["oracle6_mean_future120"].mean()),
                    "avg_edge_vs_all_future60": float(eval_df["edge_vs_all_future60"].mean()),
                    "avg_edge_vs_all_future120": float(eval_df["edge_vs_all_future120"].mean()),
                    "selected_vs_oracle_capture_ratio_60d": avg_selected60 / avg_oracle60 if avg_oracle60 else 0.0,
                    "positive_month_rate_future60_pct": float((eval_df["selected_mean_future60"] > 0.0).mean() * 100.0),
                    "positive_month_rate_future120_pct": float((eval_df["selected_mean_future120"] > 0.0).mean() * 100.0),
                    "avg_oracle_recall_count": float(eval_df["selected_oracle_count"].mean()),
                    "at_least_one_oracle_month_rate_pct": float((eval_df["selected_oracle_count"] > 0).mean() * 100.0),
                    "avg_family_unique_count": float(eval_df["family_unique_count"].mean()),
                    "avg_family_max_count": float(eval_df["family_max_count"].mean()),
                    "avg_abs_core_corr": float(eval_df["avg_abs_core_corr"].mean()),
                    "avg_family_state_score": float(eval_df["avg_family_state_score"].mean()),
                    "rationale": mode.rationale,
                }
            )

    selections = pd.DataFrame(selection_rows)
    summary = pd.DataFrame(summary_rows)
    if not summary.empty:
        summary["diagnostic_pass"] = (
            (summary["sample_type"].eq("quarterly_purged"))
            & (summary["avg_edge_vs_all_future60"] >= HARD_EDGE_THRESHOLD)
            & (summary["selected_vs_oracle_capture_ratio_60d"] >= HARD_CAPTURE_RATIO)
            & (summary["positive_month_rate_future60_pct"] >= HARD_POSITIVE_MONTH_RATE)
            & (summary["avg_oracle_recall_count"] >= 2.0)
            & (summary["avg_selected_mean_future120"] >= 0.0)
        ).astype(int)
        summary.sort_values(
            ["diagnostic_pass", "sample_type", "avg_edge_vs_all_future60", "positive_month_rate_future60_pct"],
            ascending=[False, True, False, False],
            inplace=True,
        )

    contribution = pd.DataFrame(contribution_rows)
    if not contribution.empty:
        contribution = (
            contribution.groupby(["mode", "mode_label", "sample_type", "product_family"], as_index=False)
            .agg(
                total_selected_count=("selected_count", "sum"),
                avg_selected_count=("selected_count", "mean"),
                total_oracle_count=("selected_oracle_count", "sum"),
                avg_selected_future60=("selected_future60_sum", "mean"),
                avg_selected_future120=("selected_future120_sum", "mean"),
                avg_family_state_score=("avg_family_state_score", "mean"),
            )
            .sort_values(["sample_type", "mode", "total_selected_count"], ascending=[True, True, False])
        )
    return selections, summary, contribution


def _evaluate_family_signals(family: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for sample_type in ("monthly", "quarterly_purged"):
        allowed_dates = set(_sample_dates(family, sample_type))
        subset = family[family["eval_date"].isin(allowed_dates)].copy()
        for score_column in FAMILY_SCORE_COLUMNS:
            eval_rows: list[dict[str, Any]] = []
            for eval_date, frame in subset.groupby("eval_date", sort=True):
                ranked = frame.sort_values([score_column, "family_avg_abs_core_corr", "product_family"], ascending=[False, True, True])
                selected = ranked.head(TOP_K).copy()
                if selected.empty:
                    continue
                oracle_family_set = set(frame.loc[frame["family_oracle_count"] > 0, "product_family"].astype(str))
                selected_family_set = set(selected["product_family"].astype(str))
                eval_rows.append(
                    {
                        "eval_date": eval_date,
                        "top_family_future60_mean": float(selected["family_future60_mean"].mean()),
                        "top_family_future120_mean": float(selected["family_future120_mean"].mean()),
                        "all_family_future60_mean": float(frame["family_future60_mean"].mean()),
                        "all_family_future120_mean": float(frame["family_future120_mean"].mean()),
                        "oracle_family_recall": len(selected_family_set & oracle_family_set),
                        "avg_family_score": float(selected[score_column].mean()),
                    }
                )
            eval_df = pd.DataFrame(eval_rows)
            if eval_df.empty:
                continue
            rows.append(
                {
                    "sample_type": sample_type,
                    "family_score_column": score_column,
                    "months": int(len(eval_df)),
                    "avg_top_family_future60_mean": float(eval_df["top_family_future60_mean"].mean()),
                    "avg_top_family_future120_mean": float(eval_df["top_family_future120_mean"].mean()),
                    "avg_all_family_future60_mean": float(eval_df["all_family_future60_mean"].mean()),
                    "avg_all_family_future120_mean": float(eval_df["all_family_future120_mean"].mean()),
                    "avg_edge_vs_all_family_future60": float(
                        (eval_df["top_family_future60_mean"] - eval_df["all_family_future60_mean"]).mean()
                    ),
                    "avg_edge_vs_all_family_future120": float(
                        (eval_df["top_family_future120_mean"] - eval_df["all_family_future120_mean"]).mean()
                    ),
                    "positive_month_rate_future60_pct": float((eval_df["top_family_future60_mean"] > 0.0).mean() * 100.0),
                    "avg_oracle_family_recall": float(eval_df["oracle_family_recall"].mean()),
                    "avg_family_score": float(eval_df["avg_family_score"].mean()),
                }
            )
    result = pd.DataFrame(rows)
    if not result.empty:
        result.sort_values(["sample_type", "avg_edge_vs_all_family_future60"], ascending=[True, False], inplace=True)
    return result


def _decision(summary: pd.DataFrame, family_signal_summary: pd.DataFrame) -> dict[str, Any]:
    passed = summary[summary["diagnostic_pass"].eq(1)].copy() if "diagnostic_pass" in summary.columns else pd.DataFrame()
    quarterly = summary[summary["sample_type"].eq("quarterly_purged")].copy()
    best = quarterly.sort_values(["avg_edge_vs_all_future60", "selected_vs_oracle_capture_ratio_60d"], ascending=False).head(1)
    best_record = best.iloc[0].to_dict() if not best.empty else {}

    family_quarterly = family_signal_summary[family_signal_summary["sample_type"].eq("quarterly_purged")].copy()
    best_family_signal = (
        family_quarterly.sort_values("avg_edge_vs_all_family_future60", ascending=False).head(1).iloc[0].to_dict()
        if not family_quarterly.empty
        else {}
    )
    return {
        "stage": "Stage245",
        "script_stage": "Stage545",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decision": (
            "family_state_selector_ready_for_dynamic_sleeve_probe"
            if not passed.empty
            else "family_state_selector_not_ready_external_state_needed"
        ),
        "baseline": "Stage243/244 ex-ante selectors; Stage542 Oracle6 remains only a hindsight upper bound.",
        "pass_definition": (
            "Quarterly-purged Top6 product-family-state selector must beat all-noncore future60 mean by >=500 yuan/product, "
            "capture >=50% of Oracle6 future60 reference, have >=55% positive 60d periods, average >=2 Oracle6 names, "
            "and keep future120 mean non-negative."
        ),
        "passed_rows": passed.to_dict("records"),
        "best_row": best_record,
        "best_family_signal": best_family_signal,
        "overfit_boundary": (
            "Family state scores use only eval-date visible cross-sectional ranks and lagged ledger/market features. "
            "No future PnL, Oracle labels, or full-sample product returns enter selection."
        ),
        "next_step": (
            "If not passed, stop tuning these price/ledger family scores. Move to point-in-time basis, warehouse/inventory, "
            "open-interest participant structure, and timestamped news/sentiment coverage before any formal dynamic sleeve."
        ),
    }


def _stage544_best_series(samples: pd.DataFrame) -> pd.Series:
    if not STAGE544_SELECTIONS_IN.exists():
        dates = _sample_dates(samples, "quarterly_purged")
        return pd.Series(0.0, index=pd.DatetimeIndex(dates))
    selections = pd.read_csv(STAGE544_SELECTIONS_IN, encoding="utf-8-sig")
    selections["eval_date"] = pd.to_datetime(selections["eval_date"], errors="coerce").dt.normalize()
    subset = selections[
        selections["sample_type"].eq("quarterly_purged")
        & selections["mode"].eq("simple_family_cap1_lowcorr030")
    ].copy()
    return subset.groupby("eval_date")["future_stage541_pnl_60d"].mean().sort_index()


def _plot(
    samples: pd.DataFrame,
    family: pd.DataFrame,
    selections: pd.DataFrame,
    summary: pd.DataFrame,
    family_signal_summary: pd.DataFrame,
    contribution: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    fig, axes = plt.subplots(2, 2, figsize=(17, 10))
    ax_edge, ax_quality, ax_cum, ax_family = axes.flatten()

    quarterly = summary[summary["sample_type"].eq("quarterly_purged")].copy()
    quarterly = quarterly.sort_values("avg_edge_vs_all_future60", ascending=True)
    ax_edge.barh(quarterly["mode_label"], quarterly["avg_edge_vs_all_future60"], color="#2563eb")
    ax_edge.axvline(0, color="#111827", linestyle="--", linewidth=1)
    ax_edge.axvline(HARD_EDGE_THRESHOLD, color="#dc2626", linestyle=":", linewidth=1)
    ax_edge.set_title("Quarterly product selection future60 edge")
    ax_edge.grid(axis="x", alpha=0.25)

    x = np.arange(len(quarterly))
    ax_quality.bar(x - 0.2, quarterly["positive_month_rate_future60_pct"], width=0.4, color="#059669", label="60d positive rate")
    ax_quality.bar(
        x + 0.2,
        quarterly["selected_vs_oracle_capture_ratio_60d"] * 100.0,
        width=0.4,
        color="#f97316",
        label="Oracle capture %",
    )
    ax_quality.axhline(HARD_POSITIVE_MONTH_RATE, color="#111827", linestyle="--", linewidth=1)
    ax_quality.axhline(HARD_CAPTURE_RATIO * 100.0, color="#dc2626", linestyle=":", linewidth=1)
    ax_quality.set_xticks(x)
    ax_quality.set_xticklabels(quarterly["mode_label"], rotation=35, ha="right", fontsize=8)
    ax_quality.set_title("Positive rate and Oracle capture")
    ax_quality.grid(axis="y", alpha=0.25)
    ax_quality.legend(fontsize=8)

    q_dates = _sample_dates(samples, "quarterly_purged")
    q_sel = selections[selections["sample_type"].eq("quarterly_purged")].copy()
    plot_modes = quarterly.sort_values("avg_edge_vs_all_future60", ascending=False)["mode"].head(3).tolist()
    for mode in plot_modes:
        series = q_sel[q_sel["mode"].eq(mode)].groupby("eval_date")["future_stage541_pnl_60d"].mean().reindex(q_dates).fillna(0.0).cumsum()
        label = str(quarterly.loc[quarterly["mode"].eq(mode), "mode_label"].iloc[0])
        ax_cum.plot(series.index, series.values, label=label, linewidth=1.1)
    stage544_best = _stage544_best_series(samples).reindex(q_dates).fillna(0.0).cumsum()
    ax_cum.plot(stage544_best.index, stage544_best.values, label="Stage544 best family cap", color="#7c3aed", linewidth=1.1)
    oracle_series = (
        samples[samples["is_oracle6"].eq(1)]
        .groupby("eval_date")["future_stage541_pnl_60d"]
        .mean()
        .reindex(q_dates)
        .fillna(0.0)
        .cumsum()
    )
    all_series = samples.groupby("eval_date")["future_stage541_pnl_60d"].mean().reindex(q_dates).fillna(0.0).cumsum()
    ax_cum.plot(oracle_series.index, oracle_series.values, label="Oracle6 reference", color="#dc2626", linewidth=1.6)
    ax_cum.plot(all_series.index, all_series.values, label="All noncore mean", color="#111827", linestyle="--", linewidth=1.0)
    ax_cum.axhline(0, color="#111827", linestyle="--", linewidth=1)
    ax_cum.set_title("Quarterly cumulative future60 mean")
    ax_cum.grid(alpha=0.25)
    ax_cum.legend(fontsize=7)

    best_mode = str(decision.get("best_row", {}).get("mode", ""))
    family_view = contribution[
        contribution["sample_type"].eq("quarterly_purged") & contribution["mode"].eq(best_mode)
    ].copy()
    if not family_view.empty:
        family_view.sort_values("total_selected_count", inplace=True)
        colors = ["#ef4444" if value < 0 else "#10b981" for value in family_view["avg_selected_future60"]]
        ax_family.barh(family_view["product_family"], family_view["total_selected_count"], color=colors)
        ax_family.set_title(f"Selected family frequency: {decision.get('best_row', {}).get('mode_label', '')}")
        ax_family.grid(axis="x", alpha=0.25)

    fig.suptitle(f"Stage545 decision: {decision['decision']}", fontsize=12)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=180)
    plt.close(fig)


def _write_report(summary: pd.DataFrame, family_signal_summary: pd.DataFrame, contribution: pd.DataFrame, decision: dict[str, Any]) -> None:
    quarterly_view = summary[summary["sample_type"].eq("quarterly_purged")][
        [
            "mode_label",
            "avg_selected_mean_future60",
            "avg_selected_mean_future120",
            "avg_edge_vs_all_future60",
            "avg_oracle6_mean_future60",
            "selected_vs_oracle_capture_ratio_60d",
            "positive_month_rate_future60_pct",
            "avg_oracle_recall_count",
            "avg_family_unique_count",
            "avg_abs_core_corr",
            "diagnostic_pass",
        ]
    ].sort_values("avg_edge_vs_all_future60", ascending=False)
    family_signal_view = family_signal_summary[family_signal_summary["sample_type"].eq("quarterly_purged")][
        [
            "family_score_column",
            "avg_top_family_future60_mean",
            "avg_edge_vs_all_family_future60",
            "positive_month_rate_future60_pct",
            "avg_oracle_family_recall",
        ]
    ].sort_values("avg_edge_vs_all_family_future60", ascending=False)
    best_mode = str(decision.get("best_row", {}).get("mode", ""))
    contribution_view = contribution[
        contribution["sample_type"].eq("quarterly_purged") & contribution["mode"].eq(best_mode)
    ][
        [
            "product_family",
            "total_selected_count",
            "avg_selected_future60",
            "avg_selected_future120",
            "avg_family_state_score",
        ]
    ].sort_values("total_selected_count", ascending=False)
    lines = [
        "# Stage545 产品族状态事前选品诊断",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- 决策：`{decision['decision']}`。",
        "- 阶段性质：只读诊断；不改策略交易规则，不生成真实交易候选。",
        "- 核心问题：能否先用当时可见的产品族趋势土壤/策略记忆/量仓参与度判断该启用哪些产品族，再在族内选低相关品种。",
        "",
        "## 通过定义",
        "",
        decision["pass_definition"],
        "",
        "## 季度去重产品选择摘要",
        "",
        _md_table(quarterly_view),
        "",
        "## 产品族状态信号摘要",
        "",
        _md_table(family_signal_view),
        "",
        "## 最佳模式产品族贡献",
        "",
        _md_table(contribution_view),
        "",
        "## 判断",
        "",
        "- 如果产品族状态只能改善边际 edge，但不能稳定提高正月份率和 Oracle 捕获，就不能进入动态 sleeve。",
        "- 当前所有状态分都只使用评估日前可见的价格、量仓、流动性、历史账本和核心相关特征；Oracle6 只用于召回诊断。",
        "- 若本阶段不通过，下一步不应继续扫状态分权重，而应补真正的点时化基本面/基差/仓单库存/产业新闻接收时间戳。",
        "",
        "## 输出文件",
        "",
        f"- family scores：`{FAMILY_SCORES_PATH}`",
        f"- selections：`{SELECTIONS_PATH}`",
        f"- summary：`{SUMMARY_PATH}`",
        f"- family signal summary：`{FAMILY_SIGNAL_SUMMARY_PATH}`",
        f"- contribution：`{FAMILY_CONTRIBUTION_PATH}`",
        f"- decision：`{DECISION_PATH}`",
        f"- chart：`{CHART_PATH}`",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    samples, family = _load_samples()
    selections, summary, contribution = _evaluate(samples)
    family_signal_summary = _evaluate_family_signals(family)
    decision = _decision(summary, family_signal_summary)

    family.to_csv(FAMILY_SCORES_PATH, index=False, encoding="utf-8-sig")
    selections.to_csv(SELECTIONS_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    family_signal_summary.to_csv(FAMILY_SIGNAL_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    contribution.to_csv(FAMILY_CONTRIBUTION_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _plot(samples, family, selections, summary, family_signal_summary, contribution, decision)
    _write_report(summary, family_signal_summary, contribution, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
