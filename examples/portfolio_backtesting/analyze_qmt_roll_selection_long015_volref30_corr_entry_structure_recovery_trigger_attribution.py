from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from analyze_qmt_roll_ai_product_suitability_walkforward import product_from_contract
from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import to_markdown_table


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "entry_structure_recovery_trigger_attribution_v1"
OUTPUT_PREFIX: str = "qmt_roll_selection_long015_volref30_corr_entry_structure_recovery_trigger_attribution"

RECOVERY_PREFIX: str = (
    "qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_entry_structure_recovery_formal"
)
SHIELD_PREFIX: str = "qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_streak_formal"
STAGE75_PREFIX: str = "qmt_roll_selection_long015_volref30_corr_fu_satellite_post_signal_formal"

HORIZONS: tuple[int, ...] = (5, 10, 20, 40, 60, 120)
KEY_COLUMNS: tuple[str, ...] = ("date", "product_vt_symbol", "direction", "signal")

EVENT_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_table_{MODEL_TAG}.csv"
CANDIDATE_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_candidate_summary_{MODEL_TAG}.csv"
PERIOD_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_period_summary_{MODEL_TAG}.csv"
FEATURE_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_summary_{MODEL_TAG}.csv"
HORIZON_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_summary_{MODEL_TAG}.csv"
SUMMARY_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(number) or math.isinf(number):
        return default
    return number


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, **kwargs)


def _numeric_series(df: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in df.columns:
        return pd.Series(default, index=df.index, dtype="float64")
    return pd.to_numeric(df[column], errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(default)


def _period_label(date: pd.Timestamp) -> str:
    if date <= pd.Timestamp("2021-12-31"):
        return "pre_ai_2020_2021"
    if date <= pd.Timestamp("2023-12-31"):
        return "early_ai_2022_2023"
    if date <= pd.Timestamp("2025-12-31"):
        return "trend_rich_2024_2025"
    return "latest_2026"


def _ai_rank_bucket(rank: float) -> str:
    if rank <= 3:
        return "ai_rank_1_3"
    if rank <= 5:
        return "ai_rank_4_5"
    if rank <= 8:
        return "ai_rank_6_8"
    return "ai_rank_gt8"


def _drawdown_bucket(drawdown: float) -> str:
    if drawdown <= 0.10:
        return "dd_lte_10pct"
    if drawdown <= 0.20:
        return "dd_10_20pct"
    if drawdown <= 0.30:
        return "dd_20_30pct"
    return "dd_gt_30pct"


def _signed_feature_aligned(direction: str, value: float) -> bool:
    if direction == "long":
        return value > 0.0
    if direction == "short":
        return value < 0.0
    return False


def _forward_sum(
    grouped_daily: dict[str, pd.DataFrame],
    product: str,
    date: pd.Timestamp,
    column: str,
    horizon: int,
) -> float:
    product_daily = grouped_daily.get(product)
    if product_daily is None or product_daily.empty:
        return 0.0
    dates = product_daily["date"].to_numpy(dtype="datetime64[ns]")
    idx = int(np.searchsorted(dates, np.datetime64(date), side="left"))
    if idx >= len(product_daily):
        return 0.0
    return float(product_daily.iloc[idx : idx + horizon][column].sum())


def _forward_strategy_sum(daily: pd.DataFrame, date: pd.Timestamp, column: str, horizon: int) -> float:
    dates = daily["date"].to_numpy(dtype="datetime64[ns]")
    idx = int(np.searchsorted(dates, np.datetime64(date), side="left"))
    if idx >= len(daily):
        return 0.0
    return float(daily.iloc[idx : idx + horizon][column].sum())


def load_product_daily(prefix: str) -> pd.DataFrame:
    path = OUTPUT_DIR / f"{prefix}_position_changes_2020_2026_04.csv"
    df = _read_csv(path)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df["product_vt_symbol"] = df["vt_symbol"].map(product_from_contract)
    for column in ("net_pnl", "total_pnl", "holding_pnl", "trading_pnl", "slippage", "trade_count", "pos_change"):
        df[column] = _numeric_series(df, column)
    return (
        df.groupby(["date", "product_vt_symbol"], as_index=False)
        .agg(
            net_pnl=("net_pnl", "sum"),
            total_pnl=("total_pnl", "sum"),
            holding_pnl=("holding_pnl", "sum"),
            trading_pnl=("trading_pnl", "sum"),
            slippage=("slippage", "sum"),
            trade_count=("trade_count", "sum"),
            abs_pos_change=("pos_change", lambda values: float(pd.to_numeric(values, errors="coerce").abs().sum())),
        )
        .sort_values(["product_vt_symbol", "date"])
        .reset_index(drop=True)
    )


def load_strategy_daily(prefix: str) -> pd.DataFrame:
    path = OUTPUT_DIR / f"{prefix}_daily.csv"
    df = _read_csv(path)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    for column in ("net_pnl", "balance", "drawdown", "ddpercent", "trade_count", "slippage"):
        df[column] = _numeric_series(df, column)
    return df.sort_values("date").reset_index(drop=True)


def load_variant_entries(prefix: str, variant: str) -> pd.DataFrame:
    path = OUTPUT_DIR / f"{prefix}_entry_candidate_snapshots_2020_2026_04.csv"
    df = _read_csv(path)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    for column in ("selected_volume", "target_risk_amount", "risk_multiplier", "risk_ratio", "is_opened"):
        df[column] = _numeric_series(df, column)
    view_columns = [
        *KEY_COLUMNS,
        "candidate_status",
        "selected_volume",
        "target_risk_amount",
        "risk_multiplier",
        "risk_ratio",
        "risk_mode",
        "skip_reason",
    ]
    result = df[view_columns].copy()
    result = result.rename(
        columns={
            "candidate_status": f"{variant}_candidate_status",
            "selected_volume": f"{variant}_selected_volume",
            "target_risk_amount": f"{variant}_target_risk_amount",
            "risk_multiplier": f"{variant}_risk_multiplier",
            "risk_ratio": f"{variant}_risk_ratio",
            "risk_mode": f"{variant}_risk_mode",
            "skip_reason": f"{variant}_skip_reason",
        }
    )
    return result.drop_duplicates(list(KEY_COLUMNS), keep="last")


def load_recovery_events() -> pd.DataFrame:
    path = OUTPUT_DIR / f"{RECOVERY_PREFIX}_entry_candidate_snapshots_2020_2026_04.csv"
    df = _read_csv(path)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    numeric_columns = [
        "selected_volume",
        "target_risk_amount",
        "risk_multiplier",
        "risk_ratio",
        "is_opened",
        "streak_entry_structure_risk_recovery_applied",
        "streak_entry_structure_risk_recovery_base_multiplier",
        "streak_entry_structure_risk_recovery_effective_multiplier",
        "breakout",
        "portfolio_drawdown_pct",
        "same_direction_correlation_active_count",
        "same_direction_correlation_max_corr",
        "selection_pairwise_rank",
        "selection_pairwise_feature_ret_20d_zscore_120",
        "selection_pairwise_feature_close_position_60d_cs_zscore_1d",
        "selection_pairwise_feature_range_pct_zscore_120",
        "ai_product_pool_rank",
        "rsi_value",
        "active_positions_before",
        "loss_streak",
    ]
    for column in numeric_columns:
        df[column] = _numeric_series(df, column)
    opened = (df["candidate_status"].astype(str) == "opened") | (df["is_opened"] > 0.0)
    triggered = df[(df["streak_entry_structure_risk_recovery_applied"] > 0.0) & opened].copy()
    triggered["period"] = triggered["date"].map(_period_label)
    triggered["year"] = triggered["date"].dt.year
    triggered["ai_rank_bucket"] = triggered["ai_product_pool_rank"].map(_ai_rank_bucket)
    triggered["drawdown_bucket"] = triggered["portfolio_drawdown_pct"].map(_drawdown_bucket)
    triggered["selected_volume_delta_vs_shield"] = 0.0
    return triggered.sort_values(["date", "product_vt_symbol", "direction", "signal"]).reset_index(drop=True)


def attach_variant_entry_comparison(events: pd.DataFrame) -> pd.DataFrame:
    result = events.copy()
    for prefix, variant in (
        (SHIELD_PREFIX, "shield"),
        (STAGE75_PREFIX, "stage75"),
    ):
        result = result.merge(load_variant_entries(prefix, variant), on=list(KEY_COLUMNS), how="left")
    result["shield_selected_volume"] = _numeric_series(result, "shield_selected_volume")
    result["stage75_selected_volume"] = _numeric_series(result, "stage75_selected_volume")
    result["selected_volume_delta_vs_shield"] = result["selected_volume"] - result["shield_selected_volume"]
    result["selected_volume_delta_vs_stage75"] = result["selected_volume"] - result["stage75_selected_volume"]
    return result


def attach_forward_outcomes(events: pd.DataFrame) -> pd.DataFrame:
    result = events.copy()
    variants = {
        "recovery": RECOVERY_PREFIX,
        "shield": SHIELD_PREFIX,
        "stage75": STAGE75_PREFIX,
    }
    product_daily_by_variant = {variant: load_product_daily(prefix) for variant, prefix in variants.items()}
    strategy_daily_by_variant = {variant: load_strategy_daily(prefix) for variant, prefix in variants.items()}
    grouped_by_variant = {
        variant: {
            product: group.sort_values("date").reset_index(drop=True)
            for product, group in product_daily.groupby("product_vt_symbol")
        }
        for variant, product_daily in product_daily_by_variant.items()
    }
    for variant in variants:
        grouped = grouped_by_variant[variant]
        daily = strategy_daily_by_variant[variant]
        for horizon in HORIZONS:
            result[f"{variant}_next{horizon}_product_net_pnl"] = [
                _forward_sum(grouped, row.product_vt_symbol, row.date, "net_pnl", horizon)
                for row in result.itertuples(index=False)
            ]
            result[f"{variant}_next{horizon}_product_abs_pos_change"] = [
                _forward_sum(grouped, row.product_vt_symbol, row.date, "abs_pos_change", horizon)
                for row in result.itertuples(index=False)
            ]
            result[f"{variant}_next{horizon}_strategy_net_pnl"] = [
                _forward_strategy_sum(daily, row.date, "net_pnl", horizon) for row in result.itertuples(index=False)
            ]
    for horizon in HORIZONS:
        result[f"delta_next{horizon}_product_net_pnl"] = (
            result[f"recovery_next{horizon}_product_net_pnl"] - result[f"shield_next{horizon}_product_net_pnl"]
        )
        result[f"delta_next{horizon}_strategy_net_pnl"] = (
            result[f"recovery_next{horizon}_strategy_net_pnl"] - result[f"shield_next{horizon}_strategy_net_pnl"]
        )
    result["recovery_better_flag"] = (result["delta_next20_product_net_pnl"] > 0.0).astype("int64")
    result["shield_better_flag"] = (result["delta_next20_product_net_pnl"] < 0.0).astype("int64")
    result["recovery_follow_through_flag"] = (result["recovery_next20_product_net_pnl"] > 0.0).astype("int64")
    result["outcome_label"] = np.select(
        [
            result["delta_next20_product_net_pnl"] > 0.0,
            result["delta_next20_product_net_pnl"] < 0.0,
        ],
        ["recovery_better", "shield_better"],
        default="flat",
    )
    return result


def add_candidate_flags(events: pd.DataFrame) -> pd.DataFrame:
    result = events.copy()
    direction = result["direction"].astype(str)
    ret20 = _numeric_series(result, "selection_pairwise_feature_ret_20d_zscore_120")
    close_pos = _numeric_series(result, "selection_pairwise_feature_close_position_60d_cs_zscore_1d")
    range_z = _numeric_series(result, "selection_pairwise_feature_range_pct_zscore_120")
    rsi = _numeric_series(result, "rsi_value")
    breakout = _numeric_series(result, "breakout") > 0.0
    ret20_aligned = pd.Series(
        [_signed_feature_aligned(direction_value, feature_value) for direction_value, feature_value in zip(direction, ret20)],
        index=result.index,
        dtype="bool",
    )
    close_aligned = pd.Series(
        [
            _signed_feature_aligned(direction_value, feature_value)
            for direction_value, feature_value in zip(direction, close_pos)
        ],
        index=result.index,
        dtype="bool",
    )
    rsi_continuation = ((direction == "long") & (rsi >= 60.0)) | ((direction == "short") & (rsi <= 40.0))
    rsi_not_exhausted = ((direction == "long") & (rsi <= 80.0)) | ((direction == "short") & (rsi >= 20.0))

    result["candidate_all_triggers"] = 1
    result["candidate_breakout_only"] = breakout.astype("int64")
    result["candidate_no_breakout"] = (~breakout).astype("int64")
    result["candidate_direction_ret20_aligned"] = ret20_aligned.astype("int64")
    result["candidate_direction_close_position_aligned"] = close_aligned.astype("int64")
    result["candidate_breakout_and_ret20_aligned"] = (breakout & ret20_aligned).astype("int64")
    result["candidate_breakout_or_ret20_aligned"] = (breakout | ret20_aligned).astype("int64")
    result["candidate_breakout_and_close_position_aligned"] = (breakout & close_aligned).astype("int64")
    result["candidate_regular_risk_mode"] = result["risk_mode"].astype(str).eq("regular").astype("int64")
    result["candidate_ai_rank_top5"] = (_numeric_series(result, "ai_product_pool_rank") <= 5.0).astype("int64")
    result["candidate_ai_rank_top3"] = (_numeric_series(result, "ai_product_pool_rank") <= 3.0).astype("int64")
    result["candidate_low_drawdown_lte15"] = (_numeric_series(result, "portfolio_drawdown_pct") <= 0.15).astype("int64")
    result["candidate_low_drawdown_lte25"] = (_numeric_series(result, "portfolio_drawdown_pct") <= 0.25).astype("int64")
    result["candidate_no_range_expansion_gt1"] = (range_z <= 1.0).astype("int64")
    result["candidate_rsi_continuation"] = rsi_continuation.astype("int64")
    result["candidate_rsi_continuation_not_exhausted"] = (rsi_continuation & rsi_not_exhausted).astype("int64")
    result["candidate_extra_volume_lte50"] = (_numeric_series(result, "selected_volume_delta_vs_shield") <= 50.0).astype(
        "int64"
    )
    result["candidate_extra_volume_lte100"] = (
        _numeric_series(result, "selected_volume_delta_vs_shield") <= 100.0
    ).astype("int64")
    result["candidate_non_fu_product"] = (result["product_vt_symbol"].astype(str) != "fu.SHFE").astype("int64")
    result["candidate_long_only"] = direction.eq("long").astype("int64")
    result["candidate_short_only"] = direction.eq("short").astype("int64")
    return result


def candidate_effect(events: pd.DataFrame, keep_mask: pd.Series) -> dict[str, Any]:
    keep = keep_mask.fillna(False).astype(bool)
    kept = events[keep]
    delta = events["delta_next20_product_net_pnl"].where(keep, 0.0)
    positive_delta_mask = events["delta_next20_product_net_pnl"] > 0.0
    return {
        "restore_event_count": int(keep.sum()),
        "recovery_better_event_count": int((keep & positive_delta_mask).sum()),
        "shield_better_event_count": int((keep & (events["delta_next20_product_net_pnl"] < 0.0)).sum()),
        "follow_through_event_count": int((keep & (events["recovery_next20_product_net_pnl"] > 0.0)).sum()),
        "recovery_next20_product_net_pnl": float(kept["recovery_next20_product_net_pnl"].sum()) if not kept.empty else 0.0,
        "shield_next20_product_net_pnl": float(kept["shield_next20_product_net_pnl"].sum()) if not kept.empty else 0.0,
        "candidate_value_vs_shield": float(delta.sum()),
        "candidate_negative_delta_cost": float(events["delta_next20_product_net_pnl"].where(keep & ~positive_delta_mask, 0.0).sum()),
        "missed_positive_delta": float(events["delta_next20_product_net_pnl"].where((~keep) & positive_delta_mask, 0.0).sum()),
        "recovery_hit_rate": float((keep & positive_delta_mask).sum() / keep.sum()) if keep.any() else 0.0,
        "follow_through_rate": float((keep & (events["recovery_next20_product_net_pnl"] > 0.0)).sum() / keep.sum())
        if keep.any()
        else 0.0,
        "avg_extra_volume_vs_shield": float(kept["selected_volume_delta_vs_shield"].mean()) if not kept.empty else 0.0,
    }


def build_candidate_summary(events: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = [
        {
            "candidate": "no_recovery",
            "is_baseline": 1,
            "direction_specific": 0,
            **candidate_effect(events, pd.Series(False, index=events.index)),
        }
    ]
    candidate_columns: list[str] = []
    for column in events.columns:
        if not column.startswith("candidate_"):
            continue
        values = pd.to_numeric(events[column], errors="coerce").dropna()
        if values.empty:
            continue
        unique_values = set(values.astype("int64").unique().tolist())
        if unique_values.issubset({0, 1}):
            candidate_columns.append(column)
    for column in candidate_columns:
        candidate = column.replace("candidate_", "")
        rows.append(
            {
                "candidate": candidate,
                "is_baseline": int(candidate == "all_triggers"),
                "direction_specific": int(candidate in {"long_only", "short_only"}),
                **candidate_effect(events, events[column] > 0),
            }
        )
    return (
        pd.DataFrame(rows)
        .sort_values(
            ["candidate_value_vs_shield", "direction_specific", "restore_event_count", "recovery_hit_rate"],
            ascending=[False, True, False, False],
        )
        .reset_index(drop=True)
    )


def build_period_summary(events: pd.DataFrame) -> pd.DataFrame:
    return (
        events.groupby("period", as_index=False)
        .agg(
            event_count=("date", "count"),
            product_count=("product_vt_symbol", "nunique"),
            recovery_better_event_count=("recovery_better_flag", "sum"),
            shield_better_event_count=("shield_better_flag", "sum"),
            follow_through_event_count=("recovery_follow_through_flag", "sum"),
            recovery_next20_product_net_pnl=("recovery_next20_product_net_pnl", "sum"),
            shield_next20_product_net_pnl=("shield_next20_product_net_pnl", "sum"),
            delta_next20_product_net_pnl=("delta_next20_product_net_pnl", "sum"),
            avg_extra_volume_vs_shield=("selected_volume_delta_vs_shield", "mean"),
        )
        .sort_values("period")
        .reset_index(drop=True)
    )


def build_feature_summary(events: pd.DataFrame) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for feature in ("period", "direction", "signal", "breakout", "ai_rank_bucket", "drawdown_bucket", "risk_mode"):
        grouped = (
            events.groupby(feature, as_index=False)
            .agg(
                event_count=("date", "count"),
                recovery_better_event_count=("recovery_better_flag", "sum"),
                shield_better_event_count=("shield_better_flag", "sum"),
                recovery_next20_product_net_pnl=("recovery_next20_product_net_pnl", "sum"),
                shield_next20_product_net_pnl=("shield_next20_product_net_pnl", "sum"),
                delta_next20_product_net_pnl=("delta_next20_product_net_pnl", "sum"),
                avg_extra_volume_vs_shield=("selected_volume_delta_vs_shield", "mean"),
            )
            .rename(columns={feature: "bucket"})
        )
        grouped.insert(0, "feature", feature)
        rows.append(grouped)
    return pd.concat(rows, ignore_index=True).sort_values(["feature", "delta_next20_product_net_pnl"]).reset_index(
        drop=True
    )


def build_horizon_summary(events: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for horizon in HORIZONS:
        delta_product = events[f"delta_next{horizon}_product_net_pnl"]
        delta_strategy = events[f"delta_next{horizon}_strategy_net_pnl"]
        rows.append(
            {
                "horizon": horizon,
                "event_count": int(len(events)),
                "recovery_better_event_count": int((delta_product > 0.0).sum()),
                "shield_better_event_count": int((delta_product < 0.0).sum()),
                "recovery_product_net_pnl": float(events[f"recovery_next{horizon}_product_net_pnl"].sum()),
                "shield_product_net_pnl": float(events[f"shield_next{horizon}_product_net_pnl"].sum()),
                "delta_product_net_pnl": float(delta_product.sum()),
                "recovery_strategy_net_pnl": float(events[f"recovery_next{horizon}_strategy_net_pnl"].sum()),
                "shield_strategy_net_pnl": float(events[f"shield_next{horizon}_strategy_net_pnl"].sum()),
                "delta_strategy_net_pnl": float(delta_strategy.sum()),
            }
        )
    return pd.DataFrame(rows)


def build_summary(
    events: pd.DataFrame,
    candidate_summary: pd.DataFrame,
    period_summary: pd.DataFrame,
    feature_summary: pd.DataFrame,
    horizon_summary: pd.DataFrame,
) -> dict[str, Any]:
    structural = candidate_summary[candidate_summary["direction_specific"] == 0].copy()
    best_structural = structural.iloc[0].to_dict() if not structural.empty else {}
    return {
        "model_tag": MODEL_TAG,
        "event_count": int(len(events)),
        "product_count": int(events["product_vt_symbol"].nunique()),
        "recovery_better_event_count": int(events["recovery_better_flag"].sum()),
        "shield_better_event_count": int(events["shield_better_flag"].sum()),
        "follow_through_event_count": int(events["recovery_follow_through_flag"].sum()),
        "recovery_next20_product_net_pnl": float(events["recovery_next20_product_net_pnl"].sum()),
        "shield_next20_product_net_pnl": float(events["shield_next20_product_net_pnl"].sum()),
        "delta_next20_product_net_pnl": float(events["delta_next20_product_net_pnl"].sum()),
        "best_structural_candidate": best_structural,
        "candidate_summary": candidate_summary.replace({np.nan: None}).to_dict(orient="records"),
        "period_summary": period_summary.replace({np.nan: None}).to_dict(orient="records"),
        "feature_summary": feature_summary.replace({np.nan: None}).to_dict(orient="records"),
        "horizon_summary": horizon_summary.replace({np.nan: None}).to_dict(orient="records"),
    }


def build_report(
    summary: dict[str, Any],
    events: pd.DataFrame,
    candidate_summary: pd.DataFrame,
    period_summary: pd.DataFrame,
    feature_summary: pd.DataFrame,
    horizon_summary: pd.DataFrame,
) -> str:
    best = summary.get("best_structural_candidate", {})
    display_candidates = candidate_summary[
        [
            "candidate",
            "is_baseline",
            "direction_specific",
            "restore_event_count",
            "recovery_better_event_count",
            "shield_better_event_count",
            "follow_through_event_count",
            "candidate_value_vs_shield",
            "candidate_negative_delta_cost",
            "missed_positive_delta",
            "recovery_hit_rate",
            "follow_through_rate",
            "avg_extra_volume_vs_shield",
        ]
    ].head(18)
    key_events = events[
        [
            "date",
            "period",
            "product_vt_symbol",
            "direction",
            "signal",
            "outcome_label",
            "selected_volume_delta_vs_shield",
            "breakout",
            "ai_product_pool_rank",
            "portfolio_drawdown_pct",
            "selection_pairwise_feature_ret_20d_zscore_120",
            "selection_pairwise_feature_close_position_60d_cs_zscore_1d",
            "recovery_next20_product_net_pnl",
            "shield_next20_product_net_pnl",
            "delta_next20_product_net_pnl",
        ]
    ].sort_values("delta_next20_product_net_pnl")
    feature_view = feature_summary[
        [
            "feature",
            "bucket",
            "event_count",
            "recovery_better_event_count",
            "shield_better_event_count",
            "delta_next20_product_net_pnl",
            "avg_extra_volume_vs_shield",
        ]
    ].head(20)

    lines = [
        f"# {MODEL_TAG}",
        "",
        "## 目的",
        "",
        "- 本阶段只做第84阶段实际触发事件的失败归因，不修改策略、不新增回测。",
        "- 评价对象是`early_cross_clean_book`恢复风险后的真实触发样本，标签用事件后20个交易日的产品级净损益差额：第84阶段减第78阶段。",
        "- 筛选条件只使用入场当下已有字段，避免把事件后的输赢写回规则。",
        "",
        "## 总览",
        "",
        f"- 触发事件`{int(summary.get('event_count', 0))}`笔，涉及产品`{int(summary.get('product_count', 0))}`个。",
        f"- 第84相对第78更好的事件`{int(summary.get('recovery_better_event_count', 0))}`笔，第78更好的事件`{int(summary.get('shield_better_event_count', 0))}`笔。",
        f"- 20日产品级净损益：第84`{_safe_float(summary.get('recovery_next20_product_net_pnl')):,.0f}`，第78`{_safe_float(summary.get('shield_next20_product_net_pnl')):,.0f}`，差额`{_safe_float(summary.get('delta_next20_product_net_pnl')):,.0f}`。",
        "",
        "## 候选过滤条件评分",
        "",
        to_markdown_table(display_candidates),
        "",
        "## 分周期表现",
        "",
        to_markdown_table(period_summary),
        "",
        "## 多窗口稳定性",
        "",
        to_markdown_table(horizon_summary),
        "",
        "## 特征分桶",
        "",
        to_markdown_table(feature_view),
        "",
        "## 最差事件",
        "",
        to_markdown_table(key_events.head(10)),
        "",
        "## 最好事件",
        "",
        to_markdown_table(key_events.tail(8).sort_values("delta_next20_product_net_pnl", ascending=False)),
        "",
        "## 判断",
        "",
        f"- 当前事件级最优非方向专属候选为`{best.get('candidate', '')}`，事件级相对第78贡献`{_safe_float(best.get('candidate_value_vs_shield')):,.0f}`。",
        "- 但样本只有21笔，任何单一阈值都不能直接升级成正式规则；本阶段更重要的结论是找出第84失败来自哪些周期和哪些结构。",
        "- 如果最优候选依赖方向、年份或成交量截断，应优先视为诊断线索，而不是策略参数；下一步只有在多周期回测和留出压力中仍有效，才值得写入策略。",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    events = load_recovery_events()
    events = attach_variant_entry_comparison(events)
    events = attach_forward_outcomes(events)
    events = add_candidate_flags(events)
    candidate_summary = build_candidate_summary(events)
    period_summary = build_period_summary(events)
    feature_summary = build_feature_summary(events)
    horizon_summary = build_horizon_summary(events)
    summary = build_summary(events, candidate_summary, period_summary, feature_summary, horizon_summary)
    report = build_report(summary, events, candidate_summary, period_summary, feature_summary, horizon_summary)

    events.to_csv(EVENT_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    candidate_summary.to_csv(CANDIDATE_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    period_summary.to_csv(PERIOD_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    feature_summary.to_csv(FEATURE_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    horizon_summary.to_csv(HORIZON_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    SUMMARY_OUTPUT_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_OUTPUT_PATH.write_text(report, encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"wrote {REPORT_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
