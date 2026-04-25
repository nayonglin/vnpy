from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from analyze_qmt_roll_selection_long015_volref30_corr_entry_structure_recovery_trigger_attribution import (
    HORIZONS,
    KEY_COLUMNS,
    _ai_rank_bucket,
    _drawdown_bucket,
    _forward_strategy_sum,
    _forward_sum,
    _numeric_series,
    _period_label,
    _read_csv,
    _safe_float,
    _signed_feature_aligned,
    load_product_daily,
    load_strategy_daily,
)
from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import to_markdown_table


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "entry_structure_rsi_recovery_half_event_branch_v1"
OUTPUT_PREFIX: str = (
    "qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_"
    "entry_structure_rsi_recovery_half_event_branch"
)

STAGE90_PREFIX: str = (
    "qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_"
    "entry_structure_rsi_recovery_half_formal"
)
STAGE86_PREFIX: str = (
    "qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_"
    "entry_structure_rsi_recovery_formal"
)
STAGE78_PREFIX: str = "qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_streak_formal"

EVENT_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_table_{MODEL_TAG}.csv"
CANDIDATE_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_candidate_summary_{MODEL_TAG}.csv"
PERIOD_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_period_summary_{MODEL_TAG}.csv"
FEATURE_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_summary_{MODEL_TAG}.csv"
PRODUCT_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_summary_{MODEL_TAG}.csv"
HORIZON_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_summary_{MODEL_TAG}.csv"
SUMMARY_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_OUTPUT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _finite_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(number) or math.isinf(number):
        return default
    return number


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


def load_stage90_recovery_events() -> pd.DataFrame:
    path = OUTPUT_DIR / f"{STAGE90_PREFIX}_entry_candidate_snapshots_2020_2026_04.csv"
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
        "streak_entry_structure_risk_recovery_rsi_value",
        "streak_entry_structure_risk_recovery_portfolio_drawdown_pct",
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
    triggered["rsi_extreme_bucket"] = np.select(
        [
            ((triggered["direction"].astype(str) == "long") & (triggered["rsi_value"] >= 80.0))
            | ((triggered["direction"].astype(str) == "short") & (triggered["rsi_value"] <= 20.0)),
            ((triggered["direction"].astype(str) == "long") & (triggered["rsi_value"] >= 70.0))
            | ((triggered["direction"].astype(str) == "short") & (triggered["rsi_value"] <= 30.0)),
        ],
        ["rsi_extreme", "rsi_strong"],
        default="rsi_moderate",
    )
    return triggered.sort_values(["date", "product_vt_symbol", "direction", "signal"]).reset_index(drop=True)


def attach_variant_entries(events: pd.DataFrame) -> pd.DataFrame:
    result = events.copy()
    for prefix, variant in (
        (STAGE78_PREFIX, "stage78"),
        (STAGE86_PREFIX, "stage86"),
    ):
        result = result.merge(load_variant_entries(prefix, variant), on=list(KEY_COLUMNS), how="left")
    for variant in ("stage78", "stage86"):
        result[f"{variant}_selected_volume"] = _numeric_series(result, f"{variant}_selected_volume")
        result[f"{variant}_risk_multiplier"] = _numeric_series(result, f"{variant}_risk_multiplier")
    result["selected_volume_delta_vs_stage78"] = result["selected_volume"] - result["stage78_selected_volume"]
    result["selected_volume_delta_vs_stage86"] = result["selected_volume"] - result["stage86_selected_volume"]
    return result


def attach_forward_outcomes(events: pd.DataFrame) -> pd.DataFrame:
    result = events.copy()
    variants = {
        "stage90": STAGE90_PREFIX,
        "stage86": STAGE86_PREFIX,
        "stage78": STAGE78_PREFIX,
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
            result[f"{variant}_next{horizon}_strategy_net_pnl"] = [
                _forward_strategy_sum(daily, row.date, "net_pnl", horizon) for row in result.itertuples(index=False)
            ]
    for horizon in HORIZONS:
        result[f"stage90_vs_stage78_next{horizon}_product_net_pnl"] = (
            result[f"stage90_next{horizon}_product_net_pnl"] - result[f"stage78_next{horizon}_product_net_pnl"]
        )
        result[f"stage86_vs_stage78_next{horizon}_product_net_pnl"] = (
            result[f"stage86_next{horizon}_product_net_pnl"] - result[f"stage78_next{horizon}_product_net_pnl"]
        )
        result[f"stage90_vs_stage86_next{horizon}_product_net_pnl"] = (
            result[f"stage90_next{horizon}_product_net_pnl"] - result[f"stage86_next{horizon}_product_net_pnl"]
        )
        result[f"stage90_vs_stage78_next{horizon}_strategy_net_pnl"] = (
            result[f"stage90_next{horizon}_strategy_net_pnl"] - result[f"stage78_next{horizon}_strategy_net_pnl"]
        )
    result["stage90_better_than_stage78_flag"] = (
        result["stage90_vs_stage78_next20_product_net_pnl"] > 0.0
    ).astype("int64")
    result["stage78_better_than_stage90_flag"] = (
        result["stage90_vs_stage78_next20_product_net_pnl"] < 0.0
    ).astype("int64")
    result["stage90_better_than_stage86_flag"] = (
        result["stage90_vs_stage86_next20_product_net_pnl"] > 0.0
    ).astype("int64")
    result["outcome_label"] = np.select(
        [
            result["stage90_vs_stage78_next20_product_net_pnl"] > 0.0,
            result["stage90_vs_stage78_next20_product_net_pnl"] < 0.0,
        ],
        ["stage90_better", "stage78_better"],
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
    drawdown = _numeric_series(result, "portfolio_drawdown_pct")
    max_corr = _numeric_series(result, "same_direction_correlation_max_corr")
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

    result["candidate_all_stage90_recovery_events"] = 1
    result["candidate_breakout_only"] = breakout.astype("int64")
    result["candidate_no_breakout"] = (~breakout).astype("int64")
    result["candidate_direction_ret20_aligned"] = ret20_aligned.astype("int64")
    result["candidate_direction_close_position_aligned"] = close_aligned.astype("int64")
    result["candidate_breakout_and_ret20_aligned"] = (breakout & ret20_aligned).astype("int64")
    result["candidate_breakout_or_ret20_aligned"] = (breakout | ret20_aligned).astype("int64")
    result["candidate_rsi_continuation_not_exhausted"] = (rsi_continuation & rsi_not_exhausted).astype("int64")
    result["candidate_portfolio_drawdown_lte10"] = (drawdown <= 0.10).astype("int64")
    result["candidate_portfolio_drawdown_lte20"] = (drawdown <= 0.20).astype("int64")
    result["candidate_portfolio_drawdown_lte30"] = (drawdown <= 0.30).astype("int64")
    result["candidate_same_direction_corr_lte10"] = (max_corr <= 0.10).astype("int64")
    result["candidate_same_direction_corr_lte20"] = (max_corr <= 0.20).astype("int64")
    result["candidate_same_direction_corr_lte30"] = (max_corr <= 0.30).astype("int64")
    result["candidate_ai_rank_top5"] = (_numeric_series(result, "ai_product_pool_rank") <= 5.0).astype("int64")
    result["candidate_ai_rank_gt5"] = (_numeric_series(result, "ai_product_pool_rank") > 5.0).astype("int64")
    result["candidate_no_range_expansion_gt1"] = (range_z <= 1.0).astype("int64")
    result["candidate_extra_volume_vs_stage78_lte10"] = (
        _numeric_series(result, "selected_volume_delta_vs_stage78") <= 10.0
    ).astype("int64")
    result["candidate_extra_volume_vs_stage78_lte20"] = (
        _numeric_series(result, "selected_volume_delta_vs_stage78") <= 20.0
    ).astype("int64")
    result["candidate_stage90_reduces_stage86_volume"] = (
        _numeric_series(result, "selected_volume_delta_vs_stage86") < 0.0
    ).astype("int64")
    result["candidate_long_only"] = direction.eq("long").astype("int64")
    result["candidate_short_only"] = direction.eq("short").astype("int64")
    return result


def candidate_effect(events: pd.DataFrame, keep_mask: pd.Series) -> dict[str, Any]:
    keep = keep_mask.fillna(False).astype(bool)
    kept = events[keep]
    delta = events["stage90_vs_stage78_next20_product_net_pnl"].where(keep, 0.0)
    positive_delta_mask = events["stage90_vs_stage78_next20_product_net_pnl"] > 0.0
    return {
        "restore_event_count": int(keep.sum()),
        "stage90_better_event_count": int((keep & positive_delta_mask).sum()),
        "stage78_better_event_count": int((keep & (events["stage90_vs_stage78_next20_product_net_pnl"] < 0.0)).sum()),
        "stage90_next20_product_net_pnl": float(kept["stage90_next20_product_net_pnl"].sum()) if not kept.empty else 0.0,
        "stage78_next20_product_net_pnl": float(kept["stage78_next20_product_net_pnl"].sum()) if not kept.empty else 0.0,
        "stage90_value_vs_stage78": float(delta.sum()),
        "negative_delta_cost": float(delta.where(delta < 0.0, 0.0).sum()),
        "missed_positive_delta": float(
            events["stage90_vs_stage78_next20_product_net_pnl"].where((~keep) & positive_delta_mask, 0.0).sum()
        ),
        "hit_rate": float((keep & positive_delta_mask).sum() / keep.sum()) if keep.any() else 0.0,
        "avg_extra_volume_vs_stage78": float(kept["selected_volume_delta_vs_stage78"].mean()) if not kept.empty else 0.0,
    }


def build_candidate_summary(events: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for column in events.columns:
        if not column.startswith("candidate_"):
            continue
        values = pd.to_numeric(events[column], errors="coerce").dropna()
        if values.empty:
            continue
        unique_values = set(values.astype("int64").unique().tolist())
        if unique_values.issubset({0, 1}):
            candidate = column.replace("candidate_", "")
            rows.append(
                {
                    "candidate": candidate,
                    "direction_specific": int(candidate in {"long_only", "short_only"}),
                    **candidate_effect(events, events[column] > 0),
                }
            )
    return (
        pd.DataFrame(rows)
        .sort_values(
            ["stage90_value_vs_stage78", "direction_specific", "restore_event_count", "hit_rate"],
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
            stage90_better_event_count=("stage90_better_than_stage78_flag", "sum"),
            stage78_better_event_count=("stage78_better_than_stage90_flag", "sum"),
            stage90_next20_product_net_pnl=("stage90_next20_product_net_pnl", "sum"),
            stage86_next20_product_net_pnl=("stage86_next20_product_net_pnl", "sum"),
            stage78_next20_product_net_pnl=("stage78_next20_product_net_pnl", "sum"),
            stage90_value_vs_stage78=("stage90_vs_stage78_next20_product_net_pnl", "sum"),
            stage86_value_vs_stage78=("stage86_vs_stage78_next20_product_net_pnl", "sum"),
            stage90_value_vs_stage86=("stage90_vs_stage86_next20_product_net_pnl", "sum"),
            avg_extra_volume_vs_stage78=("selected_volume_delta_vs_stage78", "mean"),
            avg_extra_volume_vs_stage86=("selected_volume_delta_vs_stage86", "mean"),
        )
        .sort_values("period")
        .reset_index(drop=True)
    )


def build_feature_summary(events: pd.DataFrame) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for feature in (
        "period",
        "direction",
        "signal",
        "product_vt_symbol",
        "ai_rank_bucket",
        "drawdown_bucket",
        "rsi_extreme_bucket",
        "risk_mode",
    ):
        grouped = (
            events.groupby(feature, as_index=False)
            .agg(
                event_count=("date", "count"),
                stage90_better_event_count=("stage90_better_than_stage78_flag", "sum"),
                stage78_better_event_count=("stage78_better_than_stage90_flag", "sum"),
                stage90_value_vs_stage78=("stage90_vs_stage78_next20_product_net_pnl", "sum"),
                stage90_value_vs_stage86=("stage90_vs_stage86_next20_product_net_pnl", "sum"),
                avg_extra_volume_vs_stage78=("selected_volume_delta_vs_stage78", "mean"),
            )
            .rename(columns={feature: "bucket"})
        )
        grouped.insert(0, "feature", feature)
        rows.append(grouped)
    return pd.concat(rows, ignore_index=True).sort_values(["feature", "stage90_value_vs_stage78"]).reset_index(
        drop=True
    )


def build_product_summary(events: pd.DataFrame) -> pd.DataFrame:
    return (
        events.groupby("product_vt_symbol", as_index=False)
        .agg(
            event_count=("date", "count"),
            stage90_better_event_count=("stage90_better_than_stage78_flag", "sum"),
            stage78_better_event_count=("stage78_better_than_stage90_flag", "sum"),
            stage90_next20_product_net_pnl=("stage90_next20_product_net_pnl", "sum"),
            stage78_next20_product_net_pnl=("stage78_next20_product_net_pnl", "sum"),
            stage90_value_vs_stage78=("stage90_vs_stage78_next20_product_net_pnl", "sum"),
            stage90_value_vs_stage86=("stage90_vs_stage86_next20_product_net_pnl", "sum"),
            avg_extra_volume_vs_stage78=("selected_volume_delta_vs_stage78", "mean"),
        )
        .sort_values("stage90_value_vs_stage78")
        .reset_index(drop=True)
    )


def build_horizon_summary(events: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for horizon in HORIZONS:
        delta90 = events[f"stage90_vs_stage78_next{horizon}_product_net_pnl"]
        delta86 = events[f"stage86_vs_stage78_next{horizon}_product_net_pnl"]
        rows.append(
            {
                "horizon": horizon,
                "event_count": int(len(events)),
                "stage90_better_event_count": int((delta90 > 0.0).sum()),
                "stage78_better_event_count": int((delta90 < 0.0).sum()),
                "stage90_product_net_pnl": float(events[f"stage90_next{horizon}_product_net_pnl"].sum()),
                "stage86_product_net_pnl": float(events[f"stage86_next{horizon}_product_net_pnl"].sum()),
                "stage78_product_net_pnl": float(events[f"stage78_next{horizon}_product_net_pnl"].sum()),
                "stage90_value_vs_stage78": float(delta90.sum()),
                "stage86_value_vs_stage78": float(delta86.sum()),
                "stage90_value_vs_stage86": float(events[f"stage90_vs_stage86_next{horizon}_product_net_pnl"].sum()),
                "stage90_strategy_value_vs_stage78": float(
                    events[f"stage90_vs_stage78_next{horizon}_strategy_net_pnl"].sum()
                ),
            }
        )
    return pd.DataFrame(rows)


def build_summary(
    events: pd.DataFrame,
    candidate_summary: pd.DataFrame,
    period_summary: pd.DataFrame,
    feature_summary: pd.DataFrame,
    product_summary: pd.DataFrame,
    horizon_summary: pd.DataFrame,
) -> dict[str, Any]:
    structural = candidate_summary[candidate_summary["direction_specific"] == 0].copy()
    best_structural = structural.iloc[0].to_dict() if not structural.empty else {}
    return {
        "model_tag": MODEL_TAG,
        "event_count": int(len(events)),
        "product_count": int(events["product_vt_symbol"].nunique()),
        "stage90_better_event_count": int(events["stage90_better_than_stage78_flag"].sum()),
        "stage78_better_event_count": int(events["stage78_better_than_stage90_flag"].sum()),
        "stage90_next20_product_net_pnl": float(events["stage90_next20_product_net_pnl"].sum()),
        "stage86_next20_product_net_pnl": float(events["stage86_next20_product_net_pnl"].sum()),
        "stage78_next20_product_net_pnl": float(events["stage78_next20_product_net_pnl"].sum()),
        "stage90_value_vs_stage78": float(events["stage90_vs_stage78_next20_product_net_pnl"].sum()),
        "stage86_value_vs_stage78": float(events["stage86_vs_stage78_next20_product_net_pnl"].sum()),
        "stage90_value_vs_stage86": float(events["stage90_vs_stage86_next20_product_net_pnl"].sum()),
        "best_structural_candidate": best_structural,
        "candidate_summary": candidate_summary.replace({np.nan: None}).to_dict(orient="records"),
        "period_summary": period_summary.replace({np.nan: None}).to_dict(orient="records"),
        "feature_summary": feature_summary.replace({np.nan: None}).to_dict(orient="records"),
        "product_summary": product_summary.replace({np.nan: None}).to_dict(orient="records"),
        "horizon_summary": horizon_summary.replace({np.nan: None}).to_dict(orient="records"),
    }


def build_report(
    summary: dict[str, Any],
    events: pd.DataFrame,
    candidate_summary: pd.DataFrame,
    period_summary: pd.DataFrame,
    feature_summary: pd.DataFrame,
    product_summary: pd.DataFrame,
    horizon_summary: pd.DataFrame,
) -> str:
    best = summary.get("best_structural_candidate", {})
    candidate_view = candidate_summary[
        [
            "candidate",
            "direction_specific",
            "restore_event_count",
            "stage90_better_event_count",
            "stage78_better_event_count",
            "stage90_value_vs_stage78",
            "negative_delta_cost",
            "missed_positive_delta",
            "hit_rate",
            "avg_extra_volume_vs_stage78",
        ]
    ].head(18)
    event_view = events[
        [
            "date",
            "period",
            "product_vt_symbol",
            "direction",
            "signal",
            "outcome_label",
            "selected_volume",
            "stage78_selected_volume",
            "stage86_selected_volume",
            "portfolio_drawdown_pct",
            "same_direction_correlation_max_corr",
            "ai_product_pool_rank",
            "rsi_value",
            "stage90_next20_product_net_pnl",
            "stage78_next20_product_net_pnl",
            "stage90_vs_stage78_next20_product_net_pnl",
        ]
    ].sort_values("stage90_vs_stage78_next20_product_net_pnl")
    feature_view = feature_summary[
        [
            "feature",
            "bucket",
            "event_count",
            "stage90_better_event_count",
            "stage78_better_event_count",
            "stage90_value_vs_stage78",
            "stage90_value_vs_stage86",
            "avg_extra_volume_vs_stage78",
        ]
    ].head(24)
    product_view = product_summary[
        [
            "product_vt_symbol",
            "event_count",
            "stage90_better_event_count",
            "stage78_better_event_count",
            "stage90_value_vs_stage78",
            "stage90_value_vs_stage86",
            "avg_extra_volume_vs_stage78",
        ]
    ]

    lines = [
        f"# {MODEL_TAG}",
        "",
        "## 目的",
        "",
        "- 另开恢复风险研究分支，不继续微调第90参数。",
        "- 以第90半恢复实际触发事件为样本，同时比较第90半恢复、第86满恢复、第78风险治理在事件后多个窗口的产品级与组合级贡献。",
        "- 只使用入场当下已有字段做分桶和候选条件，避免把事后收益直接写成规则。",
        "",
        "## 总览",
        "",
        f"- 第90恢复事件`{int(summary.get('event_count', 0))}`笔，涉及产品`{int(summary.get('product_count', 0))}`个。",
        f"- 20日产品级净损益：第90`{_safe_float(summary.get('stage90_next20_product_net_pnl')):,.0f}`，第78`{_safe_float(summary.get('stage78_next20_product_net_pnl')):,.0f}`，差额`{_safe_float(summary.get('stage90_value_vs_stage78')):,.0f}`。",
        f"- 同一事件集下第86相对第78差额`{_safe_float(summary.get('stage86_value_vs_stage78')):,.0f}`，第90相对第86差额`{_safe_float(summary.get('stage90_value_vs_stage86')):,.0f}`。",
        "",
        "## 候选条件评分",
        "",
        to_markdown_table(candidate_view),
        "",
        "## 分周期",
        "",
        to_markdown_table(period_summary),
        "",
        "## 多窗口",
        "",
        to_markdown_table(horizon_summary),
        "",
        "## 产品贡献",
        "",
        to_markdown_table(product_view),
        "",
        "## 特征分桶",
        "",
        to_markdown_table(feature_view),
        "",
        "## 最差事件",
        "",
        to_markdown_table(event_view.head(10)),
        "",
        "## 最好事件",
        "",
        to_markdown_table(event_view.tail(8).sort_values("stage90_vs_stage78_next20_product_net_pnl", ascending=False)),
        "",
        "## 判断",
        "",
        f"- 当前最优非方向专属候选为`{best.get('candidate', '')}`，20日产品级相对第78贡献`{_finite_float(best.get('stage90_value_vs_stage78')):,.0f}`。",
        "- 这只是事件研究，不是策略升级。若优势只来自产品、年份或少数事件，不能写入正式参数。",
        "- 下一步应把候选条件作为样本外假设，用薄弱起点和滑点压力反证，而不是继续扫描阈值。",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    events = load_stage90_recovery_events()
    events = attach_variant_entries(events)
    events = attach_forward_outcomes(events)
    events = add_candidate_flags(events)
    candidate_summary = build_candidate_summary(events)
    period_summary = build_period_summary(events)
    feature_summary = build_feature_summary(events)
    product_summary = build_product_summary(events)
    horizon_summary = build_horizon_summary(events)
    summary = build_summary(
        events,
        candidate_summary,
        period_summary,
        feature_summary,
        product_summary,
        horizon_summary,
    )
    report = build_report(
        summary,
        events,
        candidate_summary,
        period_summary,
        feature_summary,
        product_summary,
        horizon_summary,
    )

    events.to_csv(EVENT_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    candidate_summary.to_csv(CANDIDATE_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    period_summary.to_csv(PERIOD_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    feature_summary.to_csv(FEATURE_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    product_summary.to_csv(PRODUCT_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    horizon_summary.to_csv(HORIZON_OUTPUT_PATH, index=False, encoding="utf-8-sig")
    SUMMARY_OUTPUT_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_OUTPUT_PATH.write_text(report, encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"wrote {REPORT_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
