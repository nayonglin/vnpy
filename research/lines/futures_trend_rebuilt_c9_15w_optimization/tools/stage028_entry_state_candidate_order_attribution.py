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
STAGE = "Stage028"
MODEL_TAG = "stage028_entry_state_candidate_order_attribution_v1"
OUTPUT_PREFIX = "rebuilt_c9_stage028_entry_state_candidate_order_attribution"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage028_entry_state_candidate_order_attribution"
STAGE024_OUTPUT_DIR = LINE_DIR / "outputs" / "stage024_causal_high_vol_pause_engine"
STAGE027_OUTPUT_DIR = LINE_DIR / "outputs" / "stage027_remaining_worst_window_position_attribution"

STAGE024_PREFIX = "rebuilt_c9_stage024_causal_high_vol_pause_engine"
STAGE024_TAG = "stage024_causal_high_vol_pause_engine_v1"
STAGE027_PREFIX = "rebuilt_c9_stage027_remaining_worst_window_position_attribution"
STAGE027_TAG = "stage027_remaining_worst_window_position_attribution_v1"

ENTRY_CANDIDATES_PATH = STAGE024_OUTPUT_DIR / f"{STAGE024_PREFIX}_entry_candidates_{STAGE024_TAG}.csv"
SELECTED_WINDOWS_PATH = STAGE027_OUTPUT_DIR / f"{STAGE027_PREFIX}_selected_windows_{STAGE027_TAG}.csv"
WINDOW_ATTRIBUTION_PATH = STAGE027_OUTPUT_DIR / f"{STAGE027_PREFIX}_window_attribution_{STAGE027_TAG}.csv"

ENTRY_EXPOSURE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_exposure_{MODEL_TAG}.csv"
FEATURE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_numeric_feature_summary_{MODEL_TAG}.csv"
CONDITION_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_condition_summary_{MODEL_TAG}.csv"
SOURCE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_source_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_condition_lift_chart_{MODEL_TAG}.png"

BROKER_MARGIN_MULTIPLIER = 1.10
MIN_CANDIDATE_COUNT = 50
MIN_CANDIDATE_SOURCE_COUNT = 3
MIN_CANDIDATE_BAD_DATE_COUNT = 15
MIN_CANDIDATE_LIFT = 1.25

KEY_COLUMNS = [
    "candidate_index",
    "datetime",
    "date",
    "product_vt_symbol",
    "contract_vt_symbol",
    "entry_context",
    "direction",
    "candidate_status",
    "skip_reason",
    "is_opened",
    "selected_volume",
    "selected_volume_ungated",
    "requested_start_month",
    "requested_end",
]

FEATURE_COLUMNS = [
    "estimated_equity",
    "total_margin_in_use_before",
    "free_capital",
    "limited_balance",
    "allowed_capital",
    "single_trade_capital_limit",
    "sizing_equity",
    "effective_capital_usage_ratio",
    "effective_single_trade_capital_usage_ratio",
    "risk_ratio",
    "risk_multiplier",
    "margin_ratio",
    "margin_per_contract",
    "projected_total_margin_after",
    "target_risk_amount",
    "risk_per_contract",
    "contracts_by_margin",
    "contracts_by_risk",
    "portfolio_drawdown_pct",
    "portfolio_overheat_cooldown_prior_drawdown_pct",
    "portfolio_overheat_cooldown_prior_ret20",
    "portfolio_overheat_cooldown_prior_ret60",
    "active_positions_before",
    "max_concurrent_positions",
    "effective_max_concurrent_positions",
    "remaining_position_slots",
    "same_direction_correlation_active_count",
    "same_direction_correlation_corr_count",
    "same_direction_correlation_max_corr",
    "same_direction_correlation_avg_corr",
    "selection_pairwise_score",
    "selection_pairwise_rank",
    "selection_pairwise_veto_flag",
    "selection_pairwise_feature_ret_20d_zscore_120",
    "selection_pairwise_feature_close_position_60d_cs_zscore_1d",
    "selection_pairwise_feature_range_pct_zscore_120",
    "selection_pairwise_volume_tilt_applied",
    "selection_pairwise_volume_tilt_multiplier",
    "selection_pairwise_volume_tilt_score_gap",
    "selection_pairwise_volume_tilt_top_gap",
    "selection_pairwise_volume_tilt_avg_active_positions_before",
    "selection_pairwise_volume_tilt_state_max_range_zscore",
    "ai_path_damage_probability",
    "ai_path_damage_discount_applied",
    "ai_product_pool_allowed",
    "ai_product_pool_score",
    "ai_product_pool_rank",
    "ai_product_pool_top_n",
    "loss_streak",
    "profit_recovery_streak",
    "recovery_sleeve_applied",
    "recovery_sleeve_normal_risk_bypassed",
    "recovery_sleeve_selected_volume_before",
    "recovery_sleeve_selected_volume_after",
    "recovery_sleeve_single_contract_broker_margin_to_equity",
    "recovery_sleeve_max_single_contract_broker_margin_to_equity",
    "product_direction_failure_cooldown_blocked",
    "product_direction_failure_cooldown_consecutive_failures",
    "product_direction_failure_cooldown_days_since_last_failure",
    "oi_price_confirm_passed",
    "oi_price_confirm_oi_up",
    "oi_price_confirm_price_aligned",
    "incremental_margin_budget_gate_passed",
    "incremental_margin_budget_gate_volume_reduced",
    "incremental_margin_budget_gate_projected_margin_after",
]

KEEP_EXPOSURE_COLUMNS = [
    "requested_start_month",
    "date",
    "product_vt_symbol",
    "direction",
    "selected_volume",
    "selected_volume_ungated",
    "estimated_equity",
    "portfolio_drawdown_abs_pct",
    "broker10_margin_to_equity_before_pct",
    "projected_broker10_margin_to_equity_after_pct",
    "active_positions_before",
    "remaining_position_slots",
    "same_direction_correlation_active_count",
    "same_direction_correlation_corr_count",
    "same_direction_correlation_max_corr",
    "selection_pairwise_rank",
    "selection_pairwise_score",
    "ai_product_pool_rank",
    "ai_product_pool_score",
    "ai_product_pool_allowed",
    "risk_multiplier",
    "risk_ratio",
    "loss_streak",
    "profit_recovery_streak",
    "exposure_count",
    "inside_selected_worst_window",
    "exposure_selected_rank_min",
    "exposure_min_return_pct",
    "first_exposure_window_start",
    "last_exposure_window_end",
]


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        if not np.isfinite(value):
            return None
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    if pd.isna(value):
        return None
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_无数据_"
    shown = frame.copy()
    if max_rows is not None:
        shown = shown.head(max_rows)
    return shown.to_markdown(index=False)


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig", **kwargs)


def _available_columns(path: Path) -> list[str]:
    return list(_read_csv(path, nrows=0).columns)


def _pctize(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    sample = values.replace([np.inf, -np.inf], np.nan).dropna().abs()
    if not sample.empty and sample.quantile(0.99) <= 1.5:
        values = values * 100.0
    return values


def _to_bool(series: pd.Series) -> pd.Series:
    text = series.astype(str).str.strip().str.lower()
    return text.isin(["1", "true", "yes", "y", "opened", "pass", "passed"])


def _prepare_windows() -> tuple[pd.DataFrame, pd.DataFrame]:
    windows = _read_csv(SELECTED_WINDOWS_PATH)
    windows = windows.copy()
    windows["source_start_month"] = windows["source_start_month"].astype(str)
    windows["start_date"] = pd.to_datetime(windows["start_date"], errors="coerce").dt.normalize()
    windows["end_date"] = pd.to_datetime(windows["end_date"], errors="coerce").dt.normalize()
    windows["return_pct"] = pd.to_numeric(windows["return_pct"], errors="coerce")
    windows = windows.dropna(subset=["source_start_month", "start_date", "end_date"]).sort_values("selected_rank")

    window_attr = _read_csv(WINDOW_ATTRIBUTION_PATH)
    if not window_attr.empty:
        window_attr["source_start_month"] = window_attr["source_start_month"].astype(str)
        window_attr["window_start_date"] = pd.to_datetime(
            window_attr["window_start_date"], errors="coerce"
        ).dt.normalize()
        window_attr["window_end_date"] = pd.to_datetime(window_attr["window_end_date"], errors="coerce").dt.normalize()
    return windows, window_attr


def _prepare_candidates(windows: pd.DataFrame) -> pd.DataFrame:
    all_columns = _available_columns(ENTRY_CANDIDATES_PATH)
    usecols = [column for column in [*KEY_COLUMNS, *FEATURE_COLUMNS] if column in all_columns]
    candidates = _read_csv(ENTRY_CANDIDATES_PATH, usecols=usecols)
    candidates["requested_start_month"] = candidates["requested_start_month"].astype(str)
    candidates["date"] = pd.to_datetime(candidates["date"], errors="coerce").dt.normalize()
    candidates = candidates.dropna(subset=["requested_start_month", "date"])

    for column in candidates.columns:
        if column in {"datetime", "date", "product_vt_symbol", "contract_vt_symbol", "entry_context", "direction", "candidate_status", "skip_reason", "requested_start_month", "requested_end"}:
            continue
        candidates[column] = pd.to_numeric(candidates[column], errors="coerce")

    if "is_opened" in candidates.columns:
        opened = pd.to_numeric(candidates["is_opened"], errors="coerce").fillna(0.0) > 0
    elif "candidate_status" in candidates.columns:
        opened = candidates["candidate_status"].astype(str).str.lower().eq("opened")
    else:
        opened = pd.to_numeric(candidates.get("selected_volume", 0.0), errors="coerce").fillna(0.0) > 0
    flat_entry = candidates.get("entry_context", pd.Series("", index=candidates.index)).astype(str).eq("flat_entry")

    sources = set(windows["source_start_month"].astype(str).dropna())
    max_date = windows["end_date"].max()
    scoped = candidates.loc[
        candidates["requested_start_month"].isin(sources)
        & (candidates["date"] <= max_date)
        & opened
        & flat_entry
    ].copy()

    if "portfolio_drawdown_pct" in scoped.columns:
        scoped["portfolio_drawdown_abs_pct"] = _pctize(scoped["portfolio_drawdown_pct"]).abs()
    else:
        scoped["portfolio_drawdown_abs_pct"] = np.nan

    equity = pd.to_numeric(scoped.get("estimated_equity"), errors="coerce")
    margin_before = pd.to_numeric(scoped.get("total_margin_in_use_before"), errors="coerce")
    scoped["broker10_margin_to_equity_before_pct"] = (
        margin_before * BROKER_MARGIN_MULTIPLIER / equity.replace(0.0, np.nan) * 100.0
    )
    if "projected_total_margin_after" in scoped.columns:
        projected = pd.to_numeric(scoped["projected_total_margin_after"], errors="coerce")
        scoped["projected_broker10_margin_to_equity_after_pct"] = (
            projected * BROKER_MARGIN_MULTIPLIER / equity.replace(0.0, np.nan) * 100.0
        )
    else:
        scoped["projected_broker10_margin_to_equity_after_pct"] = np.nan
    return scoped.sort_values(["requested_start_month", "date", "product_vt_symbol", "direction"]).reset_index(drop=True)


def _attach_window_exposure(opened_entries: pd.DataFrame, windows: pd.DataFrame) -> pd.DataFrame:
    result = opened_entries.copy()
    result["exposure_count"] = 0
    result["exposure_selected_rank_min"] = np.nan
    result["exposure_min_return_pct"] = np.nan
    result["first_exposure_window_start"] = pd.NaT
    result["last_exposure_window_end"] = pd.NaT

    for source, source_windows in windows.groupby("source_start_month"):
        mask_source = result["requested_start_month"].astype(str).eq(str(source))
        if not mask_source.any():
            continue
        source_index = result.index[mask_source]
        source_dates = result.loc[source_index, "date"]
        for _, window in source_windows.iterrows():
            # Stage027 labels "opened/traded after window start"; use strictly after start to align to that causal boundary.
            mask = (source_dates > window["start_date"]) & (source_dates <= window["end_date"])
            if not mask.any():
                continue
            idx = source_index[mask.to_numpy()]
            result.loc[idx, "exposure_count"] += 1
            current_rank = result.loc[idx, "exposure_selected_rank_min"]
            rank = float(window["selected_rank"])
            result.loc[idx, "exposure_selected_rank_min"] = np.where(current_rank.isna(), rank, np.minimum(current_rank, rank))

            current_return = result.loc[idx, "exposure_min_return_pct"]
            ret = float(window["return_pct"])
            result.loc[idx, "exposure_min_return_pct"] = np.where(current_return.isna(), ret, np.minimum(current_return, ret))

            start = window["start_date"]
            end = window["end_date"]
            current_start = result.loc[idx, "first_exposure_window_start"]
            current_end = result.loc[idx, "last_exposure_window_end"]
            result.loc[idx, "first_exposure_window_start"] = current_start.fillna(start).mask(
                current_start.notna() & (current_start > start), start
            )
            result.loc[idx, "last_exposure_window_end"] = current_end.fillna(end).mask(
                current_end.notna() & (current_end < end), end
            )

    result["inside_selected_worst_window"] = result["exposure_count"] > 0
    for column in ["first_exposure_window_start", "last_exposure_window_end"]:
        result[column] = pd.to_datetime(result[column], errors="coerce").dt.date.astype("string")
    return result


def _source_summary(entries: pd.DataFrame) -> pd.DataFrame:
    if entries.empty:
        return pd.DataFrame()
    rows = []
    for source, group in entries.groupby("requested_start_month"):
        bad = group["inside_selected_worst_window"].astype(bool)
        rows.append(
            {
                "requested_start_month": source,
                "opened_flat_entries": int(len(group)),
                "bad_window_entries": int(bad.sum()),
                "bad_window_entry_rate_pct": float(bad.mean() * 100.0) if len(group) else 0.0,
                "bad_window_exposure_count_sum": int(group["exposure_count"].sum()),
                "avg_selected_volume": float(pd.to_numeric(group["selected_volume"], errors="coerce").mean()),
                "bad_avg_selected_volume": float(pd.to_numeric(group.loc[bad, "selected_volume"], errors="coerce").mean()),
                "date_count": int(group["date"].nunique()),
                "bad_date_count": int(group.loc[bad, "date"].nunique()),
            }
        )
    return pd.DataFrame(rows).sort_values("bad_window_entry_rate_pct", ascending=False)


def _numeric_summary(entries: pd.DataFrame) -> pd.DataFrame:
    rows = []
    label = entries["inside_selected_worst_window"].astype(bool)
    skip = {
        "candidate_index",
        "is_opened",
        "exposure_count",
        "inside_selected_worst_window",
        "exposure_selected_rank_min",
        "exposure_min_return_pct",
    }
    for column in entries.columns:
        if column in skip:
            continue
        values = pd.to_numeric(entries[column], errors="coerce")
        if values.notna().sum() < 30:
            continue
        bad = values[label].dropna()
        other = values[~label].dropna()
        if len(bad) < 10 or len(other) < 10:
            continue
        bad_mean = float(bad.mean())
        other_mean = float(other.mean())
        pooled_std = float(np.sqrt((bad.var(ddof=1) + other.var(ddof=1)) / 2.0)) if len(bad) > 1 and len(other) > 1 else np.nan
        effect_size = (bad_mean - other_mean) / pooled_std if pooled_std and np.isfinite(pooled_std) and pooled_std > 0 else np.nan
        rows.append(
            {
                "feature": column,
                "bad_count": int(len(bad)),
                "nonbad_count": int(len(other)),
                "bad_mean": bad_mean,
                "nonbad_mean": other_mean,
                "mean_diff_bad_minus_nonbad": bad_mean - other_mean,
                "effect_size": effect_size,
                "bad_median": float(bad.median()),
                "nonbad_median": float(other.median()),
                "bad_p75": float(bad.quantile(0.75)),
                "nonbad_p75": float(other.quantile(0.75)),
            }
        )
    result = pd.DataFrame(rows)
    if result.empty:
        return result
    result["abs_effect_size"] = result["effect_size"].abs()
    return result.sort_values(["abs_effect_size", "bad_count"], ascending=[False, False]).drop(columns=["abs_effect_size"])


def _summarize_condition(
    entries: pd.DataFrame,
    name: str,
    description: str,
    mask: pd.Series,
    base_rate: float,
    candidate_eligible: bool = True,
) -> dict[str, Any]:
    mask = mask.fillna(False).astype(bool)
    subset = entries.loc[mask].copy()
    if subset.empty:
        return {
            "condition": name,
            "description": description,
            "candidate_eligible": bool(candidate_eligible),
            "count": 0,
            "source_count": 0,
            "date_count": 0,
            "bad_window_entry_count": 0,
            "bad_window_entry_rate_pct": 0.0,
            "lift_vs_base": np.nan,
            "bad_date_count": 0,
            "stable_candidate": False,
        }
    bad = subset["inside_selected_worst_window"].astype(bool)
    source_rates = subset.groupby("requested_start_month")["inside_selected_worst_window"].mean() * 100.0
    bad_source_count = int(subset.loc[bad, "requested_start_month"].nunique())
    rate = float(bad.mean())
    lift = rate / base_rate if base_rate > 0 else np.nan
    stable = (
        candidate_eligible
        and len(subset) >= MIN_CANDIDATE_COUNT
        and subset["requested_start_month"].nunique() >= MIN_CANDIDATE_SOURCE_COUNT
        and bad_source_count >= MIN_CANDIDATE_SOURCE_COUNT
        and subset.loc[bad, "date"].nunique() >= MIN_CANDIDATE_BAD_DATE_COUNT
        and np.isfinite(lift)
        and lift >= MIN_CANDIDATE_LIFT
    )
    selected_volume = pd.to_numeric(subset.get("selected_volume"), errors="coerce")
    return {
        "condition": name,
        "description": description,
        "candidate_eligible": bool(candidate_eligible),
        "count": int(len(subset)),
        "source_count": int(subset["requested_start_month"].nunique()),
        "bad_source_count": bad_source_count,
        "product_count": int(subset["product_vt_symbol"].nunique()) if "product_vt_symbol" in subset.columns else 0,
        "date_count": int(subset["date"].nunique()),
        "bad_window_entry_count": int(bad.sum()),
        "bad_window_entry_rate_pct": float(rate * 100.0),
        "lift_vs_base": float(lift) if np.isfinite(lift) else np.nan,
        "bad_window_exposure_count_sum": int(subset["exposure_count"].sum()),
        "bad_date_count": int(subset.loc[bad, "date"].nunique()),
        "avg_selected_volume": float(selected_volume.mean()),
        "median_selected_volume": float(selected_volume.median()),
        "selected_volume_gt1_rate_pct": float((selected_volume > 1).mean() * 100.0),
        "median_drawdown_abs_pct": float(pd.to_numeric(subset.get("portfolio_drawdown_abs_pct"), errors="coerce").median()),
        "median_broker10_before_pct": float(
            pd.to_numeric(subset.get("broker10_margin_to_equity_before_pct"), errors="coerce").median()
        ),
        "median_projected_broker10_after_pct": float(
            pd.to_numeric(subset.get("projected_broker10_margin_to_equity_after_pct"), errors="coerce").median()
        ),
        "median_active_positions_before": float(pd.to_numeric(subset.get("active_positions_before"), errors="coerce").median()),
        "median_ai_rank": float(pd.to_numeric(subset.get("ai_product_pool_rank"), errors="coerce").median()),
        "median_pairwise_rank": float(pd.to_numeric(subset.get("selection_pairwise_rank"), errors="coerce").median()),
        "source_bad_rate_min_pct": float(source_rates.min()),
        "source_bad_rate_median_pct": float(source_rates.median()),
        "source_bad_rate_max_pct": float(source_rates.max()),
        "stable_candidate": bool(stable),
    }


def _condition_summary(entries: pd.DataFrame) -> pd.DataFrame:
    base_rate = float(entries["inside_selected_worst_window"].mean()) if len(entries) else 0.0

    def num(column: str) -> pd.Series:
        if column not in entries.columns:
            return pd.Series(np.nan, index=entries.index)
        return pd.to_numeric(entries[column], errors="coerce")

    def bool_col(column: str) -> pd.Series:
        if column not in entries.columns:
            return pd.Series(False, index=entries.index)
        return _to_bool(entries[column])

    volume = num("selected_volume")
    drawdown = num("portfolio_drawdown_abs_pct")
    broker_before = num("broker10_margin_to_equity_before_pct")
    broker_after = num("projected_broker10_margin_to_equity_after_pct")
    active = num("active_positions_before")
    remaining = num("remaining_position_slots")
    ai_rank = num("ai_product_pool_rank")
    pair_rank = num("selection_pairwise_rank")
    corr_active = num("same_direction_correlation_active_count")
    corr_count = num("same_direction_correlation_corr_count")
    corr_max = num("same_direction_correlation_max_corr")
    risk_multiplier = num("risk_multiplier")
    loss_streak = num("loss_streak")

    conditions: list[tuple[str, str, pd.Series, bool]] = [
        ("all_opened_scope", "同 source/date 范围内全部 opened flat_entry；只作基准，不作交易条件", pd.Series(True, index=entries.index), False),
        ("pilot_like_selected_volume_eq1", "已是 1 手试探仓", volume.eq(1), False),
        ("normal_release_selected_volume_gt1", "新开仓释放到 1 手以上", volume.gt(1), True),
        ("normal_release_selected_volume_ge10", "新开仓释放到 10 手及以上", volume.ge(10), True),
        ("drawdown_abs_ge10", "入场前账户回撤绝对值 >=10%", drawdown.ge(10), True),
        ("drawdown_abs_ge20", "入场前账户回撤绝对值 >=20%", drawdown.ge(20), True),
        ("drawdown_abs_ge30", "入场前账户回撤绝对值 >=30%", drawdown.ge(30), True),
        ("drawdown_ge10_and_volume_gt1", "回撤 >=10% 且释放到 1 手以上", drawdown.ge(10) & volume.gt(1), True),
        ("drawdown_ge20_and_volume_gt1", "回撤 >=20% 且释放到 1 手以上", drawdown.ge(20) & volume.gt(1), True),
        ("broker10_before_ge30", "入场前 broker10 保证金/权益 >=30%", broker_before.ge(30), True),
        ("broker10_before_ge50", "入场前 broker10 保证金/权益 >=50%", broker_before.ge(50), True),
        ("broker10_before_ge70", "入场前 broker10 保证金/权益 >=70%", broker_before.ge(70), True),
        ("broker10_after_ge50", "入场后预测 broker10 保证金/权益 >=50%", broker_after.ge(50), True),
        ("broker10_after_ge70", "入场后预测 broker10 保证金/权益 >=70%", broker_after.ge(70), True),
        ("active_positions_ge2", "入场前已有活跃持仓 >=2", active.ge(2), True),
        ("active_positions_ge3", "入场前已有活跃持仓 >=3", active.ge(3), True),
        ("active_positions_ge4", "入场前已有活跃持仓 >=4", active.ge(4), True),
        ("active_ge3_and_volume_gt1", "入场前已有活跃持仓 >=3 且释放到 1 手以上", active.ge(3) & volume.gt(1), True),
        ("remaining_slots_le1", "剩余持仓槽位 <=1", remaining.le(1), True),
        ("same_direction_active_ge1", "同向相关 active count >=1", corr_active.ge(1), True),
        ("same_direction_corr_count_ge1", "同向相关有效相关计数 >=1", corr_count.ge(1), True),
        ("same_direction_max_corr_ge050", "同向最大相关性 >=0.50", corr_max.ge(0.50), True),
        ("ai_rank_le4", "AI 池 rank <=4", ai_rank.le(4), True),
        ("ai_rank_le8", "AI 池 rank <=8", ai_rank.le(8), True),
        ("ai_rank_missing", "AI rank 缺失", ai_rank.isna(), True),
        ("pairwise_rank_le1", "pairwise rank <=1", pair_rank.le(1), True),
        ("pairwise_rank_le2", "pairwise rank <=2", pair_rank.le(2), True),
        ("pairwise_rank_le4", "pairwise rank <=4", pair_rank.le(4), True),
        ("risk_multiplier_ge2", "风险 multiplier >=2", risk_multiplier.ge(2), True),
        ("loss_streak_ge2", "入场前 loss_streak >=2", loss_streak.ge(2), True),
        ("loss_streak_ge3", "入场前 loss_streak >=3", loss_streak.ge(3), True),
        ("recovery_sleeve_applied", "recovery_sleeve_applied 为真", bool_col("recovery_sleeve_applied"), True),
        (
            "normal_large_not_ai_top4",
            "释放到 1 手以上，且不是 AI top4",
            volume.gt(1) & (ai_rank.gt(4) | ai_rank.isna()),
            True,
        ),
        (
            "good_rank_high_risk_release",
            "AI top4 且 pairwise top2 且释放到 1 手以上",
            ai_rank.le(4) & pair_rank.le(2) & volume.gt(1),
            True,
        ),
        (
            "bad_account_normal_release",
            "回撤 >=10% 或 broker10 before >=50%，且释放到 1 手以上",
            (drawdown.ge(10) | broker_before.ge(50)) & volume.gt(1),
            True,
        ),
    ]

    rows = [
        _summarize_condition(entries, name, desc, mask, base_rate, candidate_eligible=eligible)
        for name, desc, mask, eligible in conditions
    ]
    result = pd.DataFrame(rows)
    return result.sort_values(["stable_candidate", "lift_vs_base", "count"], ascending=[False, False, False])


def _write_chart(condition_summary: pd.DataFrame) -> None:
    if condition_summary.empty:
        return
    chart_data = condition_summary[
        condition_summary["candidate_eligible"].astype(bool) & condition_summary["count"].ge(20)
    ].copy()
    if chart_data.empty:
        return
    chart_data = chart_data.sort_values("lift_vs_base", ascending=False).head(14).sort_values("lift_vs_base")
    plt.figure(figsize=(12, 7))
    colors = np.where(chart_data["stable_candidate"].astype(bool), "#c0392b", "#4c78a8")
    plt.barh(chart_data["condition"], chart_data["lift_vs_base"], color=colors)
    plt.axvline(1.0, color="#555555", linewidth=1)
    plt.axvline(MIN_CANDIDATE_LIFT, color="#c0392b", linewidth=1, linestyle="--")
    plt.xlabel("Bad-window entry rate lift vs opened-entry base")
    plt.ylabel("Entry-visible condition")
    plt.title("Stage028 Entry-State Condition Lift")
    plt.tight_layout()
    plt.savefig(CHART_PATH, dpi=180)
    plt.close()


def _decision(
    entries: pd.DataFrame,
    windows: pd.DataFrame,
    window_attr: pd.DataFrame,
    condition_summary: pd.DataFrame,
    source_summary: pd.DataFrame,
    feature_summary: pd.DataFrame,
) -> dict[str, Any]:
    bad = entries["inside_selected_worst_window"].astype(bool)
    stable = condition_summary.loc[
        condition_summary.get("stable_candidate", pd.Series(False, index=condition_summary.index)).astype(bool)
    ].copy()
    stable_names = stable["condition"].head(10).tolist() if not stable.empty else []
    if stable_names:
        decision = "stage028_has_entry_state_risk_release_candidates_needs_true_engine"
        decision_reason = (
            "存在跨 source/date、样本量足够且只用入场前字段的风险释放条件；只能作为真实引擎候选，不能直接当收益结论。"
        )
    else:
        decision = "stage028_no_stable_entry_state_condition_keep_readonly"
        decision_reason = "没有满足样本、跨 source/date 与 lift 门槛的低自由度入场前条件；继续交易化会偏过拟合。"

    window_attr_summary: dict[str, Any] = {}
    if not window_attr.empty:
        for column in [
            "opened_after_start_loss_share_pct",
            "opened_after_start_loss_abs",
            "all_holding_pnl",
            "all_net_pnl",
        ]:
            if column in window_attr.columns:
                window_attr_summary[f"{column}_sum_or_mean"] = (
                    float(pd.to_numeric(window_attr[column], errors="coerce").mean())
                    if column.endswith("_pct")
                    else float(pd.to_numeric(window_attr[column], errors="coerce").sum())
                )

    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "input_paths": {
            "stage024_entry_candidates": str(ENTRY_CANDIDATES_PATH.relative_to(PROJECT_DIR)),
            "stage027_selected_windows": str(SELECTED_WINDOWS_PATH.relative_to(PROJECT_DIR)),
            "stage027_window_attribution": str(WINDOW_ATTRIBUTION_PATH.relative_to(PROJECT_DIR)),
        },
        "output_paths": {
            "entry_exposure": str(ENTRY_EXPOSURE_PATH.relative_to(PROJECT_DIR)),
            "numeric_feature_summary": str(FEATURE_SUMMARY_PATH.relative_to(PROJECT_DIR)),
            "condition_summary": str(CONDITION_SUMMARY_PATH.relative_to(PROJECT_DIR)),
            "source_summary": str(SOURCE_SUMMARY_PATH.relative_to(PROJECT_DIR)),
            "condition_lift_chart": str(CHART_PATH.relative_to(PROJECT_DIR)),
            "report": str(REPORT_PATH.relative_to(PROJECT_DIR)),
            "decision": str(DECISION_PATH.relative_to(PROJECT_DIR)),
        },
        "analysis_scope": {
            "selected_window_count": int(len(windows)),
            "selected_source_count": int(windows["source_start_month"].nunique()),
            "selected_window_start_min": windows["start_date"].min(),
            "selected_window_end_max": windows["end_date"].max(),
            "opened_entry_date_min": entries["date"].min() if len(entries) else None,
            "opened_entry_date_max": entries["date"].max() if len(entries) else None,
            "opened_flat_entries_in_scope": int(len(entries)),
            "bad_window_entries": int(bad.sum()),
            "bad_window_entry_rate_pct": float(bad.mean() * 100.0) if len(entries) else 0.0,
            "bad_window_exposure_count_sum": int(entries["exposure_count"].sum()) if len(entries) else 0,
            "source_summary_rows": int(len(source_summary)),
            "numeric_feature_summary_rows": int(len(feature_summary)),
        },
        "stage027_context": window_attr_summary,
        "candidate_thresholds": {
            "min_count": MIN_CANDIDATE_COUNT,
            "min_source_count": MIN_CANDIDATE_SOURCE_COUNT,
            "min_bad_date_count": MIN_CANDIDATE_BAD_DATE_COUNT,
            "min_lift": MIN_CANDIDATE_LIFT,
        },
        "stable_candidate_conditions": stable_names,
        "decision": decision,
        "decision_reason": decision_reason,
        "official_live_impact": {
            "strategy_changed": False,
            "official_live_config_changed": False,
            "order_api_called": False,
            "ctp_connected": False,
            "research_only": True,
        },
    }


def _write_report(
    entries: pd.DataFrame,
    windows: pd.DataFrame,
    condition_summary: pd.DataFrame,
    source_summary: pd.DataFrame,
    feature_summary: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    bad = entries["inside_selected_worst_window"].astype(bool)
    top_conditions = condition_summary.loc[condition_summary["candidate_eligible"].astype(bool)].head(12)
    stable_conditions = condition_summary.loc[condition_summary["stable_candidate"].astype(bool)]
    top_features = feature_summary.head(15)
    text = f"""# Stage028 入场前账户状态/候选排序归因

- line_id：`{LINE_ID}`
- 阶段：`{STAGE}`
- 生成时间：`{decision['generated_at']}`
- 性质：只读归因；不改策略、不改实盘配置、不连接 CTP、不调用下单。

## 外部调研与判断

- Concretum 对趋势跟随 position sizing 的讨论强调波动目标、风险预算与 pyramiding 需要放在组合风险框架下比较，而不是单独优化某个窗口。
- pysystemtrade 的 backtesting 文档和 GitHub 实现思路强调 futures backtest 应该保留可复验参数与 walk-forward 口径。
- CFA/AQR/managed-futures 研究共同提示：趋势跟随长期价值来自跨市场、跨周期右尾，风控优化不能为了局部左尾切断主趋势右尾。
- 本阶段采纳：先看入场前可见的账户状态、保证金压力、活跃持仓、AI/pairwise 排序是否解释 Stage027 剩余左尾的新开仓风险释放。
- 本阶段否决：不按产品、方向、具体日期、单一年份或窗口收益结果直接写规则。

## 口径

- 输入：Stage024 `entry_candidates`、Stage027 `selected_windows/window_attribution`。
- 样本：仅取 Stage027 代表坏窗口涉及的 source，且日期不晚于 `{windows['end_date'].max().date().isoformat()}` 的全部 opened `flat_entry`；这样保留同 source 的正常开仓作对照，避免只截坏窗口日期导致基准坏窗口率过高。
- 标签：若开仓日期严格晚于某个代表坏窗口 start 且不晚于 end，则记为 `inside_selected_worst_window=True`；这是归因标签，不是交易收益标签。
- 候选晋级门槛：`count >= {MIN_CANDIDATE_COUNT}`，`source_count >= {MIN_CANDIDATE_SOURCE_COUNT}`，`bad_source_count >= {MIN_CANDIDATE_SOURCE_COUNT}`，`bad_date_count >= {MIN_CANDIDATE_BAD_DATE_COUNT}`，`lift >= {MIN_CANDIDATE_LIFT}`。

## 总览

- selected window 数：`{len(windows)}`
- source 数：`{windows['source_start_month'].nunique()}`
- opened flat_entry 样本：`{len(entries)}`
- 落入代表坏窗口的新开仓：`{int(bad.sum())}`
- 基准坏窗口开仓率：`{bad.mean() * 100.0:.4f}%`
- exposure 次数合计：`{int(entries['exposure_count'].sum())}`
- 决策：`{decision['decision']}`
- 理由：{decision['decision_reason']}

## source 层分布

{_md_table(source_summary, max_rows=12)}

## 条件归因

{_md_table(top_conditions, max_rows=12)}

## 满足晋级门槛的候选

{_md_table(stable_conditions, max_rows=20)}

## 数值特征差异

{_md_table(top_features, max_rows=15)}

## 结论

- 本阶段只证明哪些入场前字段与 Stage027 代表坏窗口内的新开仓重合度更高；不能证明任何规则一定提升收益。
- 如果有 stable candidate，下一步也必须写真实组合引擎 A/C 验证：保持 AI 月度池冻结、保证金/整数手/止损重试逻辑不变，只替换风险释放顺序。
- 如果没有 stable candidate，应停止从 Stage027 窗口继续反推交易规则，转向更外生的信息源或更低自由度账户层生存机制。

## 过拟合反思

- 运行前判断：有过拟合风险，因为标签来自已知最差窗口。
- 运行后判断：`{decision['decision']}`；稳定门槛用于过滤单日期、单 source 和小样本现象。
- 原因：本阶段没有用未来单笔盈亏定义规则，只用入场前可见字段做坏窗口重合归因，但仍必须通过真实引擎多起点验证才能交易化。

## 继续价值反思

- 运行前判断：有价值；Stage027 已把问题定位到窗口后新开/交易仓位。
- 运行后判断：{decision['decision_reason']}
- 下一步：只对 stable candidate 做一个冻结真实引擎版本；若 stable candidate 为空，则换外生信息源，不在窗口内扫参数。

## 输出文件

- entry exposure：`{ENTRY_EXPOSURE_PATH.relative_to(PROJECT_DIR)}`
- condition summary：`{CONDITION_SUMMARY_PATH.relative_to(PROJECT_DIR)}`
- numeric feature summary：`{FEATURE_SUMMARY_PATH.relative_to(PROJECT_DIR)}`
- source summary：`{SOURCE_SUMMARY_PATH.relative_to(PROJECT_DIR)}`
- chart：`{CHART_PATH.relative_to(PROJECT_DIR)}`
- decision：`{DECISION_PATH.relative_to(PROJECT_DIR)}`
"""
    REPORT_PATH.write_text(text, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    windows, window_attr = _prepare_windows()
    candidates = _prepare_candidates(windows)
    entries = _attach_window_exposure(candidates, windows)

    keep_columns = [column for column in KEEP_EXPOSURE_COLUMNS if column in entries.columns]
    entries[keep_columns].to_csv(ENTRY_EXPOSURE_PATH, index=False, encoding="utf-8-sig")

    source_summary = _source_summary(entries)
    feature_summary = _numeric_summary(entries)
    condition_summary = _condition_summary(entries)
    source_summary.to_csv(SOURCE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    feature_summary.to_csv(FEATURE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    condition_summary.to_csv(CONDITION_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    _write_chart(condition_summary)

    decision = _decision(entries, windows, window_attr, condition_summary, source_summary, feature_summary)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(entries, windows, condition_summary, source_summary, feature_summary, decision)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
