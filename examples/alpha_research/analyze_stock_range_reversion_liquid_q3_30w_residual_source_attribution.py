from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import polars as pl

from analyze_stock_range_reversion_layer_attribution import load_panels
from analyze_stock_range_reversion_liquid_q3_300k_curve_smoothness_attribution import build_full_position_daily
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import NATIVE_RESULTS_DIR, pct
from generate_stock_range_reversion_liquid_q3_paper_tracking_v3_exante_adv_quality import build_exec_info


SOURCE_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_30w_residual_increment_layer_2018_2026"
).expanduser().resolve()
SOURCE_PREFIX: str = "stock_range_reversion_liquid_q3_30w_residual_increment_layer_v1"

OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_30w_residual_source_attribution_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_30w_residual_source_attribution_v1"

ACCOUNT_SIZE_CNY: float = 300_000.0
USER_RETURN_TARGET: float = 1.0
USER_MAX_DRAWDOWN_LIMIT: float = -0.20

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "Short-term residual reversal",
        "https://www.sciencedirect.com/science/article/pii/S1386418112000468",
    ),
    (
        "Residual reversal and liquidity provision",
        "https://www.efmaefm.org/0EFMSYMPOSIUM/2012/papers/017_update.pdf",
    ),
    (
        "Portfolio performance attribution overview",
        "https://en.wikipedia.org/wiki/Performance_attribution",
    ),
    (
        "Cross-sectional mean reversion implementation",
        "https://teddykoker.com/2019/04/backtesting-a-cross-sectional-mean-reversion-strategy-in-python/",
    ),
)


@dataclass(frozen=True)
class PairSpec:
    pair_id: str
    shape_id: str
    variant_label: str
    base_scenario: str
    variant_scenario: str


PAIR_SPECS: tuple[PairSpec, ...] = (
    PairSpec(
        pair_id="top8_industry_vs_simple",
        shape_id="top8_gross50_ind2",
        variant_label="industry_resid20",
        base_scenario="simple_ret20__top8_gross50_ind2",
        variant_scenario="industry_resid20__top8_gross50_ind2",
    ),
    PairSpec(
        pair_id="top8_blend_vs_simple",
        shape_id="top8_gross50_ind2",
        variant_label="blend_simple_industry_resid20",
        base_scenario="simple_ret20__top8_gross50_ind2",
        variant_scenario="blend_simple_industry_resid20__top8_gross50_ind2",
    ),
    PairSpec(
        pair_id="top5_industry_vs_simple",
        shape_id="top5_gross50_ind2",
        variant_label="industry_resid20",
        base_scenario="simple_ret20__top5_gross50_ind2",
        variant_scenario="industry_resid20__top5_gross50_ind2",
    ),
    PairSpec(
        pair_id="top5_blend_vs_simple",
        shape_id="top5_gross50_ind2",
        variant_label="blend_simple_industry_resid20",
        base_scenario="simple_ret20__top5_gross50_ind2",
        variant_scenario="blend_simple_industry_resid20__top5_gross50_ind2",
    ),
)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def compound_return(values: pd.Series | np.ndarray | list[float]) -> float:
    clean = pd.Series(values).dropna().astype(float)
    if clean.empty:
        return 0.0
    return float((1.0 + clean).prod() - 1.0)


def max_drawdown_from_returns(values: pd.Series | np.ndarray | list[float]) -> float:
    clean = pd.Series(values).dropna().astype(float)
    if clean.empty:
        return 0.0
    equity = (1.0 + clean).cumprod()
    high = equity.cummax()
    return float((equity / high - 1.0).min())


def markdown_table(frame: pd.DataFrame, columns: list[str], limit: int = 30) -> str:
    if frame.empty:
        return "\n无数据。\n"
    existing = [col for col in columns if col in frame.columns]
    if not existing:
        return "\n无匹配列。\n"
    return frame[existing].head(limit).to_markdown(index=False)


def add_pct_columns(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    out = frame.copy()
    for column in columns:
        if column in out.columns:
            out[f"{column}_pct"] = out[column].map(lambda value: pct(safe_float(value, float("nan"))))
    return out


def read_source_csv(name: str, parse_dates: list[str] | None = None) -> pd.DataFrame:
    path = SOURCE_DIR / f"{SOURCE_PREFIX}_{name}.csv"
    dtype = {"symbol": str, "bs_code": str, "vt_symbol": str, "code": str}
    return pd.read_csv(path, dtype=dtype, parse_dates=parse_dates or [])


def build_pair_daily(daily: pd.DataFrame) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for spec in PAIR_SPECS:
        base = daily[daily["scenario"].eq(spec.base_scenario)].copy()
        variant = daily[daily["scenario"].eq(spec.variant_scenario)].copy()
        base = base.add_suffix("_base").rename(columns={"date_base": "date"})
        variant = variant.add_suffix("_variant").rename(columns={"date_variant": "date"})
        joined = base.merge(variant, on="date", how="inner")
        joined["pair_id"] = spec.pair_id
        joined["shape_id"] = spec.shape_id
        joined["variant_label"] = spec.variant_label
        joined["base_scenario"] = spec.base_scenario
        joined["variant_scenario"] = spec.variant_scenario
        joined["daily_ret_delta"] = (
            joined["strategy_daily_ret_min_fee_variant"] - joined["strategy_daily_ret_min_fee_base"]
        )
        joined["gross_ret_delta"] = joined["strategy_gross_daily_ret_variant"] - joined["strategy_gross_daily_ret_base"]
        joined["cost_ret_delta"] = joined["turnover_cost_ret_min_fee_variant"] - joined["turnover_cost_ret_min_fee_base"]
        joined["equity_gap"] = joined["equity_min_fee_variant"] - joined["equity_min_fee_base"]
        joined["drawdown_gap"] = joined["drawdown_min_fee_variant"] - joined["drawdown_min_fee_base"]
        joined["actual_gross_weight_delta"] = joined["actual_gross_weight_variant"] - joined["actual_gross_weight_base"]
        joined["actual_symbol_count_delta"] = joined["actual_symbol_count_variant"] - joined["actual_symbol_count_base"]
        joined["zero_lot_target_count_delta"] = (
            joined["zero_lot_target_count_variant"] - joined["zero_lot_target_count_base"]
        )
        joined["date"] = pd.to_datetime(joined["date"])
        joined = joined.sort_values("date")
        joined["base_pair_equity"] = (1.0 + joined["strategy_daily_ret_min_fee_base"]).cumprod()
        joined["variant_pair_equity"] = (1.0 + joined["strategy_daily_ret_min_fee_variant"]).cumprod()
        joined["relative_equity_gap"] = joined["variant_pair_equity"] / joined["base_pair_equity"] - 1.0
        frames.append(joined)
    return pd.concat(frames, ignore_index=True)


def build_pair_overall(delta: pd.DataFrame, pair_daily: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for spec in PAIR_SPECS:
        matched = delta[delta["scenario"].eq(spec.variant_scenario)]
        daily = pair_daily[pair_daily["pair_id"].eq(spec.pair_id)]
        row = matched.iloc[0].to_dict() if not matched.empty else {}
        rows.append(
            {
                "pair_id": spec.pair_id,
                "shape_id": spec.shape_id,
                "variant_label": spec.variant_label,
                "base_scenario": spec.base_scenario,
                "variant_scenario": spec.variant_scenario,
                "variant_total_return": row.get("total_return_min_fee"),
                "base_total_return": row.get("base_total_return_min_fee"),
                "delta_total_return": row.get("delta_total_return_min_fee"),
                "variant_max_drawdown": row.get("max_drawdown_min_fee"),
                "base_max_drawdown": row.get("base_max_drawdown_min_fee"),
                "delta_max_drawdown": row.get("delta_max_drawdown_min_fee"),
                "variant_sharpe": row.get("sharpe_min_fee"),
                "base_sharpe": row.get("base_sharpe_min_fee"),
                "delta_sharpe": row.get("delta_sharpe_min_fee"),
                "positive_delta_day_ratio": float((daily["daily_ret_delta"] > 0).mean()) if not daily.empty else 0.0,
                "avg_daily_ret_delta": daily["daily_ret_delta"].mean() if not daily.empty else 0.0,
                "worst_daily_ret_delta": daily["daily_ret_delta"].min() if not daily.empty else 0.0,
                "best_daily_ret_delta": daily["daily_ret_delta"].max() if not daily.empty else 0.0,
                "final_relative_equity_gap": daily["relative_equity_gap"].iloc[-1] if not daily.empty else 0.0,
                "avg_actual_gross_weight_delta": daily["actual_gross_weight_delta"].mean() if not daily.empty else 0.0,
                "avg_actual_symbol_count_delta": daily["actual_symbol_count_delta"].mean() if not daily.empty else 0.0,
                "avg_zero_lot_target_count_delta": daily["zero_lot_target_count_delta"].mean() if not daily.empty else 0.0,
            }
        )
    return pd.DataFrame(rows)


def build_year_attribution(pair_daily: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (pair_id, year), group in pair_daily.groupby(["pair_id", pair_daily["date"].dt.year]):
        first = group.iloc[0]
        base_return = compound_return(group["strategy_daily_ret_min_fee_base"])
        variant_return = compound_return(group["strategy_daily_ret_min_fee_variant"])
        base_dd = max_drawdown_from_returns(group["strategy_daily_ret_min_fee_base"])
        variant_dd = max_drawdown_from_returns(group["strategy_daily_ret_min_fee_variant"])
        rows.append(
            {
                "pair_id": pair_id,
                "shape_id": first["shape_id"],
                "variant_label": first["variant_label"],
                "year": int(year),
                "base_year_return": base_return,
                "variant_year_return": variant_return,
                "delta_year_return": variant_return - base_return,
                "base_year_drawdown": base_dd,
                "variant_year_drawdown": variant_dd,
                "delta_year_drawdown": variant_dd - base_dd,
                "positive_delta_day_ratio": float((group["daily_ret_delta"] > 0).mean()),
                "daily_delta_sum": group["daily_ret_delta"].sum(),
                "avg_actual_gross_weight_delta": group["actual_gross_weight_delta"].mean(),
                "avg_actual_symbol_count_delta": group["actual_symbol_count_delta"].mean(),
                "avg_zero_lot_target_count_delta": group["zero_lot_target_count_delta"].mean(),
                "return_improved": variant_return > base_return,
                "drawdown_improved": variant_dd >= base_dd,
                "return_and_drawdown_improved": (variant_return > base_return) and (variant_dd >= base_dd),
            }
        )
    return pd.DataFrame(rows).sort_values(["pair_id", "year"]).reset_index(drop=True)


def build_drawdown_episodes_from_pair(frame: pd.DataFrame, equity_col: str) -> pd.DataFrame:
    work = frame.sort_values("date").reset_index(drop=True)
    if work.empty:
        return pd.DataFrame()
    peak_equity = safe_float(work.loc[0, equity_col])
    peak_date = work.loc[0, "date"]
    current: dict[str, Any] | None = None
    rows: list[dict[str, Any]] = []
    for _, row in work.iloc[1:].iterrows():
        equity = safe_float(row[equity_col])
        current_date = row["date"]
        if equity >= peak_equity - 1e-12:
            if current is not None:
                current["recovery_date"] = current_date
                current["recovered"] = True
                rows.append(current)
                current = None
            peak_equity = equity
            peak_date = current_date
            continue
        if current is None:
            current = {
                "peak_date": peak_date,
                "start_date": current_date,
                "peak_equity": peak_equity,
                "trough_date": current_date,
                "trough_equity": equity,
                "recovery_date": pd.NaT,
                "recovered": False,
            }
        if equity < safe_float(current["trough_equity"]):
            current["trough_date"] = current_date
            current["trough_equity"] = equity
    if current is not None:
        rows.append(current)
    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows)
    out["max_drawdown"] = out["trough_equity"] / out["peak_equity"] - 1.0
    out["days_to_trough"] = [
        int(((work["date"] >= row.start_date) & (work["date"] <= row.trough_date)).sum()) for row in out.itertuples()
    ]
    return out.sort_values("max_drawdown").reset_index(drop=True)


def window_stats(frame: pd.DataFrame, start_date: Any, end_date: Any, return_col: str) -> tuple[float, float, int]:
    segment = frame[(frame["date"] >= start_date) & (frame["date"] <= end_date)].copy()
    if segment.empty:
        return 0.0, 0.0, 0
    return compound_return(segment[return_col]), max_drawdown_from_returns(segment[return_col]), int(len(segment))


def build_drawdown_window_attribution(pair_daily: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for spec in PAIR_SPECS:
        frame = pair_daily[pair_daily["pair_id"].eq(spec.pair_id)].sort_values("date").copy()
        episodes = build_drawdown_episodes_from_pair(frame, "equity_min_fee_base")
        if episodes.empty:
            continue
        episodes = episodes[(episodes["max_drawdown"] <= -0.03)].head(12)
        for idx, episode in episodes.iterrows():
            base_return, base_segment_dd, days = window_stats(
                frame, episode["start_date"], episode["trough_date"], "strategy_daily_ret_min_fee_base"
            )
            variant_return, variant_segment_dd, _ = window_stats(
                frame, episode["start_date"], episode["trough_date"], "strategy_daily_ret_min_fee_variant"
            )
            segment = frame[(frame["date"] >= episode["start_date"]) & (frame["date"] <= episode["trough_date"])]
            rows.append(
                {
                    "pair_id": spec.pair_id,
                    "shape_id": spec.shape_id,
                    "variant_label": spec.variant_label,
                    "window_rank": idx + 1,
                    "base_peak_date": episode["peak_date"],
                    "base_start_date": episode["start_date"],
                    "base_trough_date": episode["trough_date"],
                    "base_recovery_date": episode["recovery_date"],
                    "base_episode_max_drawdown": episode["max_drawdown"],
                    "base_segment_return_to_trough": base_return,
                    "variant_segment_return_same_window": variant_return,
                    "delta_segment_return": variant_return - base_return,
                    "base_segment_drawdown": base_segment_dd,
                    "variant_segment_drawdown_same_window": variant_segment_dd,
                    "delta_segment_drawdown": variant_segment_dd - base_segment_dd,
                    "days_to_trough": days,
                    "daily_delta_sum": segment["daily_ret_delta"].sum(),
                    "positive_delta_day_ratio": float((segment["daily_ret_delta"] > 0).mean()) if not segment.empty else 0.0,
                    "avg_actual_gross_weight_delta": segment["actual_gross_weight_delta"].mean() if not segment.empty else 0.0,
                    "avg_actual_symbol_count_delta": segment["actual_symbol_count_delta"].mean() if not segment.empty else 0.0,
                    "avg_zero_lot_target_count_delta": segment["zero_lot_target_count_delta"].mean() if not segment.empty else 0.0,
                }
            )
    return pd.DataFrame(rows).sort_values(["pair_id", "base_episode_max_drawdown"]).reset_index(drop=True)


def selected_small(selected: pd.DataFrame, scenario: str) -> pd.DataFrame:
    cols = [
        "datetime",
        "symbol",
        "code_name",
        "industry",
        "market_state_20d",
        "basket_weight",
        "ret_20",
        "market_resid_ret20",
        "industry_resid_ret20",
        "score_oversold_ret_20",
        "rank_score",
        "fwd_ret_10",
        "fwd_excess_ret_10",
        "mfe_close_10",
        "mae_close_10",
        "adv20_turnover",
        *[f"path_close_ret_{idx}" for idx in range(1, 11)],
    ]
    out = selected[selected["scenario"].eq(scenario)][[col for col in cols if col in selected.columns]].copy()
    out["datetime"] = pd.to_datetime(out["datetime"])
    out["symbol"] = out["symbol"].astype(str)
    out["_key"] = out["datetime"].dt.strftime("%Y-%m-%d") + "|" + out["symbol"]
    return out


def build_selection_overlap_and_swaps(selected: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    overlap_rows: list[dict[str, Any]] = []
    swap_rows: list[pd.DataFrame] = []
    for spec in PAIR_SPECS:
        base = selected_small(selected, spec.base_scenario)
        variant = selected_small(selected, spec.variant_scenario)
        base_keys = set(base["_key"])
        variant_keys = set(variant["_key"])
        overlap_keys = base_keys & variant_keys
        base_only = base[~base["_key"].isin(variant_keys)].copy()
        variant_only = variant[~variant["_key"].isin(base_keys)].copy()
        base_only["change_type"] = "base_only"
        variant_only["change_type"] = "variant_only"
        base_only["signed_side"] = -1.0
        variant_only["signed_side"] = 1.0
        swapped = pd.concat([base_only, variant_only], ignore_index=True)
        swapped["pair_id"] = spec.pair_id
        swapped["shape_id"] = spec.shape_id
        swapped["variant_label"] = spec.variant_label
        swap_rows.append(swapped)

        base_by_date = base.groupby("datetime")["_key"].agg(lambda item: set(item))
        variant_by_date = variant.groupby("datetime")["_key"].agg(lambda item: set(item))
        all_dates = sorted(set(base_by_date.index) | set(variant_by_date.index))
        for current_date in all_dates:
            base_set = base_by_date.get(current_date, set())
            variant_set = variant_by_date.get(current_date, set())
            union_count = len(base_set | variant_set)
            overlap_count = len(base_set & variant_set)
            overlap_rows.append(
                {
                    "pair_id": spec.pair_id,
                    "shape_id": spec.shape_id,
                    "variant_label": spec.variant_label,
                    "datetime": current_date,
                    "base_count": len(base_set),
                    "variant_count": len(variant_set),
                    "overlap_count": overlap_count,
                    "base_only_count": len(base_set - variant_set),
                    "variant_only_count": len(variant_set - base_set),
                    "union_count": union_count,
                    "overlap_ratio": overlap_count / union_count if union_count else 0.0,
                }
            )
    overlap = pd.DataFrame(overlap_rows)
    swaps = pd.concat(swap_rows, ignore_index=True) if swap_rows else pd.DataFrame()
    return overlap, swaps


def summarize_selection_overlap(overlap: pd.DataFrame) -> pd.DataFrame:
    if overlap.empty:
        return pd.DataFrame()
    return (
        overlap.groupby(["pair_id", "shape_id", "variant_label"], as_index=False)
        .agg(
            signal_days=("datetime", "count"),
            avg_overlap_ratio=("overlap_ratio", "mean"),
            median_overlap_ratio=("overlap_ratio", "median"),
            p10_overlap_ratio=("overlap_ratio", lambda item: float(item.quantile(0.10))),
            avg_base_only_count=("base_only_count", "mean"),
            avg_variant_only_count=("variant_only_count", "mean"),
            avg_base_count=("base_count", "mean"),
            avg_variant_count=("variant_count", "mean"),
        )
        .sort_values(["shape_id", "variant_label"])
        .reset_index(drop=True)
    )


def summarize_swaps(swaps: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    if swaps.empty:
        return pd.DataFrame()
    work = swaps.copy()
    work["weighted_fwd_excess_10"] = work["basket_weight"] * work["fwd_excess_ret_10"]
    work["signed_weighted_fwd_excess_10"] = work["signed_side"] * work["weighted_fwd_excess_10"]
    work["is_positive_excess_10"] = work["fwd_excess_ret_10"] > 0
    agg = (
        work.groupby(group_cols, dropna=False)
        .agg(
            selected_rows=("symbol", "count"),
            basket_weight_sum=("basket_weight", "sum"),
            avg_ret_20=("ret_20", "mean"),
            avg_industry_resid_ret20=("industry_resid_ret20", "mean"),
            avg_fwd_excess_ret_10=("fwd_excess_ret_10", "mean"),
            positive_excess_10_ratio=("is_positive_excess_10", "mean"),
            avg_mfe_close_10=("mfe_close_10", "mean"),
            avg_mae_close_10=("mae_close_10", "mean"),
            signed_weighted_fwd_excess_10=("signed_weighted_fwd_excess_10", "sum"),
            median_adv20_turnover=("adv20_turnover", "median"),
        )
        .reset_index()
    )
    return agg.sort_values(group_cols + ["signed_weighted_fwd_excess_10"]).reset_index(drop=True)


def build_path_proxy(selected: pd.DataFrame, swaps: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    path_cols = [f"path_close_ret_{idx}" for idx in range(1, 11)]
    rows: list[dict[str, Any]] = []
    for spec in PAIR_SPECS:
        for scenario, side in ((spec.base_scenario, "base"), (spec.variant_scenario, "variant")):
            frame = selected[selected["scenario"].eq(scenario)].copy()
            total_weight = frame["basket_weight"].sum()
            row: dict[str, Any] = {
                "pair_id": spec.pair_id,
                "shape_id": spec.shape_id,
                "variant_label": spec.variant_label,
                "side": side,
                "scenario": scenario,
                "selected_rows": len(frame),
                "basket_weight_sum": total_weight,
                "avg_mfe_close_10": np.average(frame["mfe_close_10"], weights=frame["basket_weight"])
                if total_weight > 0
                else np.nan,
                "avg_mae_close_10": np.average(frame["mae_close_10"], weights=frame["basket_weight"])
                if total_weight > 0
                else np.nan,
            }
            for col in path_cols:
                if col in frame.columns and total_weight > 0:
                    row[f"weighted_{col}"] = np.average(frame[col], weights=frame["basket_weight"])
            rows.append(row)
    full_path = pd.DataFrame(rows)
    base = full_path[full_path["side"].eq("base")].add_suffix("_base")
    variant = full_path[full_path["side"].eq("variant")].add_suffix("_variant")
    joined = base.merge(
        variant,
        left_on="pair_id_base",
        right_on="pair_id_variant",
        how="inner",
    )
    delta_rows: list[dict[str, Any]] = []
    for _, row in joined.iterrows():
        out: dict[str, Any] = {
            "pair_id": row["pair_id_base"],
            "shape_id": row["shape_id_base"],
            "variant_label": row["variant_label_base"],
            "selected_rows_base": row["selected_rows_base"],
            "selected_rows_variant": row["selected_rows_variant"],
            "avg_mfe_delta": row["avg_mfe_close_10_variant"] - row["avg_mfe_close_10_base"],
            "avg_mae_delta": row["avg_mae_close_10_variant"] - row["avg_mae_close_10_base"],
        }
        for col in path_cols:
            base_col = f"weighted_{col}_base"
            variant_col = f"weighted_{col}_variant"
            if base_col in row.index and variant_col in row.index:
                out[f"delta_{col}"] = row[variant_col] - row[base_col]
        delta_rows.append(out)
    path_delta = pd.DataFrame(delta_rows)

    if swaps.empty:
        return path_delta, pd.DataFrame()
    swap_path_rows: list[dict[str, Any]] = []
    for (pair_id, change_type), group in swaps.groupby(["pair_id", "change_type"]):
        total_weight = group["basket_weight"].sum()
        row = {
            "pair_id": pair_id,
            "change_type": change_type,
            "selected_rows": len(group),
            "basket_weight_sum": total_weight,
            "avg_mfe_close_10": np.average(group["mfe_close_10"], weights=group["basket_weight"])
            if total_weight > 0
            else np.nan,
            "avg_mae_close_10": np.average(group["mae_close_10"], weights=group["basket_weight"])
            if total_weight > 0
            else np.nan,
        }
        for col in path_cols:
            if col in group.columns and total_weight > 0:
                row[f"weighted_{col}"] = np.average(group[col], weights=group["basket_weight"])
        swap_path_rows.append(row)
    return path_delta, pd.DataFrame(swap_path_rows)


def build_position_contribution(daily: pd.DataFrame, orders: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    scenario_names = sorted({spec.base_scenario for spec in PAIR_SPECS} | {spec.variant_scenario for spec in PAIR_SPECS})
    stock_df, _benchmark_df = load_panels()
    exec_info = build_exec_info(stock_df)
    frames: list[pl.DataFrame] = []
    daily_pl = pl.from_pandas(daily).with_columns(pl.col("date").cast(pl.Date))
    orders_pl = pl.from_pandas(orders).with_columns(pl.col("date").cast(pl.Date))
    for scenario in scenario_names:
        scenario_daily = daily_pl.filter(pl.col("scenario") == scenario).sort("date")
        scenario_orders = orders_pl.filter(pl.col("scenario") == scenario).sort(["date", "symbol", "side"])
        position_daily = build_full_position_daily(scenario_daily, scenario_orders, exec_info)
        if position_daily.is_empty():
            continue
        frames.append(position_daily.with_columns(pl.lit(scenario).alias("scenario")))
    if not frames:
        return pd.DataFrame(), pd.DataFrame()
    positions = pl.concat(frames, how="vertical").to_pandas()
    positions["date"] = pd.to_datetime(positions["date"])
    positions["year"] = positions["date"].dt.year
    positions["gross_contribution"] = positions["gross_contribution"].astype(float)
    agg = (
        positions.groupby(["scenario", "year", "industry"], dropna=False)
        .agg(
            position_days=("symbol", "count"),
            trade_days=("date", "nunique"),
            symbols=("symbol", "nunique"),
            gross_contribution_sum=("gross_contribution", "sum"),
            negative_contribution_sum=("gross_contribution", lambda item: item[item < 0].sum()),
            positive_contribution_sum=("gross_contribution", lambda item: item[item > 0].sum()),
            avg_actual_weight=("actual_weight", "mean"),
            max_actual_weight=("actual_weight", "max"),
            avg_daily_ret=("daily_ret", "mean"),
        )
        .reset_index()
    )
    pair_rows: list[pd.DataFrame] = []
    for spec in PAIR_SPECS:
        base = agg[agg["scenario"].eq(spec.base_scenario)].add_suffix("_base")
        variant = agg[agg["scenario"].eq(spec.variant_scenario)].add_suffix("_variant")
        joined = base.merge(
            variant,
            left_on=["year_base", "industry_base"],
            right_on=["year_variant", "industry_variant"],
            how="outer",
        )
        joined["pair_id"] = spec.pair_id
        joined["shape_id"] = spec.shape_id
        joined["variant_label"] = spec.variant_label
        joined["year"] = joined["year_base"].combine_first(joined["year_variant"])
        joined["industry"] = joined["industry_base"].combine_first(joined["industry_variant"])
        for col in [
            "gross_contribution_sum",
            "negative_contribution_sum",
            "positive_contribution_sum",
            "position_days",
            "trade_days",
            "symbols",
            "avg_actual_weight",
        ]:
            joined[f"{col}_base"] = joined[f"{col}_base"].fillna(0)
            joined[f"{col}_variant"] = joined[f"{col}_variant"].fillna(0)
            joined[f"delta_{col}"] = joined[f"{col}_variant"] - joined[f"{col}_base"]
        pair_rows.append(joined)
    pair_contribution = pd.concat(pair_rows, ignore_index=True) if pair_rows else pd.DataFrame()
    return positions, pair_contribution


def build_quality(
    pair_overall: pd.DataFrame,
    yearly: pd.DataFrame,
    drawdown_windows: pd.DataFrame,
    overlap_summary: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    def add(checkpoint: str, status: str, value: Any, expected: str, judgement: str) -> None:
        rows.append(
            {
                "checkpoint": checkpoint,
                "status": status,
                "value": str(value),
                "expected": expected,
                "judgement": judgement,
            }
        )

    top8_blend = pair_overall[pair_overall["pair_id"].eq("top8_blend_vs_simple")]
    top5_blend = pair_overall[pair_overall["pair_id"].eq("top5_blend_vs_simple")]
    top8_years = yearly[yearly["pair_id"].eq("top8_blend_vs_simple")]
    top8_windows = drawdown_windows[drawdown_windows["pair_id"].eq("top8_blend_vs_simple")]
    top8_overlap = overlap_summary[overlap_summary["pair_id"].eq("top8_blend_vs_simple")]

    top8_delta_return = safe_float(top8_blend["delta_total_return"].iloc[0]) if not top8_blend.empty else 0.0
    top8_delta_dd = safe_float(top8_blend["delta_max_drawdown"].iloc[0]) if not top8_blend.empty else 0.0
    top5_delta_dd = safe_float(top5_blend["delta_max_drawdown"].iloc[0]) if not top5_blend.empty else 0.0
    top8_both_years = int(top8_years["return_and_drawdown_improved"].sum()) if not top8_years.empty else 0
    top8_worst_window_delta = safe_float(top8_windows["delta_segment_drawdown"].max()) if not top8_windows.empty else 0.0
    top8_avg_overlap = safe_float(top8_overlap["avg_overlap_ratio"].iloc[0]) if not top8_overlap.empty else 0.0

    add(
        "stage333_top8_increment_confirmed",
        "pass" if (top8_delta_return > 0 and top8_delta_dd > 0) else "fail",
        f"return_delta={pct(top8_delta_return)}, dd_delta={pct(top8_delta_dd)}",
        "top8混合排序收益和回撤都优于简单母本",
        "确认Stage333不是报告误读。",
    )
    add(
        "top8_yearly_breadth",
        "pass" if top8_both_years >= 3 else "warn",
        f"both_improved_years={top8_both_years}",
        "至少3个年份收益和回撤同向改善",
        "若只靠一两个年份，需要降级为风险段线索。",
    )
    add(
        "top8_base_drawdown_window_relief",
        "pass" if top8_worst_window_delta > 0 else "fail",
        pct(top8_worst_window_delta),
        "最坏基准回撤窗口内变体回撤更浅",
        "判断残差层是不是确实削掉最坏回撤段。",
    )
    add(
        "top5_guard_divergence",
        "warn" if top5_delta_dd < 0 else "pass",
        pct(top5_delta_dd),
        "top5护栏不应恶化回撤",
        "top5恶化说明当前不能升级正式候选。",
    )
    add(
        "selection_change_material",
        "pass" if top8_avg_overlap < 0.80 else "warn",
        pct(top8_avg_overlap),
        "平均重叠率低于80%，说明排序实际换股",
        "若重叠过高，改善可能来自很少数股票；当前需要看换股质量。",
    )
    add(
        "formal_candidate_status",
        "warn",
        "not_formal_candidate",
        "需要收益目标、top5护栏和walk-forward一起确认",
        "本阶段只归因，不触发A/B、不接paper、不接第78。",
    )
    add(
        "overfit_status",
        "pass",
        "attribution_only",
        "不新增交易阈值、不扩网格",
        "本阶段只解释已有结果，过拟合风险低于策略搜索。",
    )
    return pd.DataFrame(rows)


def build_report(
    pair_overall: pd.DataFrame,
    yearly: pd.DataFrame,
    drawdown_windows: pd.DataFrame,
    overlap_summary: pd.DataFrame,
    swap_by_industry: pd.DataFrame,
    swap_by_state: pd.DataFrame,
    path_delta: pd.DataFrame,
    position_contribution: pd.DataFrame,
    quality: pd.DataFrame,
    paths: dict[str, Path],
) -> Path:
    report_path = paths["report"]
    overall_display = add_pct_columns(
        pair_overall,
        [
            "variant_total_return",
            "base_total_return",
            "delta_total_return",
            "variant_max_drawdown",
            "base_max_drawdown",
            "delta_max_drawdown",
            "positive_delta_day_ratio",
            "final_relative_equity_gap",
            "avg_actual_gross_weight_delta",
        ],
    )
    yearly_display = add_pct_columns(
        yearly,
        [
            "base_year_return",
            "variant_year_return",
            "delta_year_return",
            "base_year_drawdown",
            "variant_year_drawdown",
            "delta_year_drawdown",
            "positive_delta_day_ratio",
        ],
    )
    drawdown_display = add_pct_columns(
        drawdown_windows,
        [
            "base_episode_max_drawdown",
            "base_segment_return_to_trough",
            "variant_segment_return_same_window",
            "delta_segment_return",
            "base_segment_drawdown",
            "variant_segment_drawdown_same_window",
            "delta_segment_drawdown",
            "positive_delta_day_ratio",
        ],
    )
    overlap_display = add_pct_columns(
        overlap_summary,
        ["avg_overlap_ratio", "median_overlap_ratio", "p10_overlap_ratio"],
    )
    swap_ind_display = add_pct_columns(
        swap_by_industry,
        [
            "avg_fwd_excess_ret_10",
            "positive_excess_10_ratio",
            "avg_mfe_close_10",
            "avg_mae_close_10",
            "signed_weighted_fwd_excess_10",
        ],
    )
    swap_state_display = add_pct_columns(
        swap_by_state,
        [
            "avg_fwd_excess_ret_10",
            "positive_excess_10_ratio",
            "avg_mfe_close_10",
            "avg_mae_close_10",
            "signed_weighted_fwd_excess_10",
        ],
    )
    path_display = add_pct_columns(
        path_delta,
        ["avg_mfe_delta", "avg_mae_delta", *[f"delta_path_close_ret_{idx}" for idx in range(1, 11)]],
    )
    position_display = add_pct_columns(
        position_contribution,
        [
            "delta_gross_contribution_sum",
            "gross_contribution_sum_base",
            "gross_contribution_sum_variant",
            "delta_negative_contribution_sum",
            "delta_positive_contribution_sum",
        ],
    )
    top8_position = position_display[position_display["pair_id"].eq("top8_blend_vs_simple")].sort_values(
        "delta_gross_contribution_sum"
    )
    top5_position = position_display[position_display["pair_id"].eq("top5_blend_vs_simple")].sort_values(
        "delta_gross_contribution_sum"
    )
    failed = quality[quality["status"].eq("fail")]
    warned = quality[quality["status"].eq("warn")]
    best_pair = pair_overall.sort_values(["delta_max_drawdown", "delta_total_return"], ascending=[False, False]).iloc[0]
    lines = [
        "# 股票震荡30万残差改善来源归因 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前模式：day",
        "- line_id：`stock_range_30w_industry_resid_core`",
        "- 阶段性质：第334阶段，读取第333阶段结果做来源归因，不新增交易规则，不触发A/B。",
        "- 账户规模：`300,000 CNY`。",
        "",
        "## 外部调研与判断",
        "",
        "- 残差反转文献支持用市场/行业残差替代裸收益排序，但核心问题是改善是否来自稳定风险暴露变化，而不是单一年份或单行业偶然收益。",
        "- 组合绩效归因框架强调按时间、风险暴露、持仓来源拆解；本阶段用年度、回撤段、换股、行业、市场状态和真实持仓贡献拆分Stage333结果。",
        "- 我的判断：如果残差层主要削2018/2022这类风险段，适合进入状态预算层；如果只来自个别行业换股，就只能当监控特征。",
        "",
        "参考资料：",
        *[f"- [{title}]({url})" for title, url in RESEARCH_SOURCES],
        "",
        "## 核心摘要",
        "",
        f"- 回撤改善最明显组合：`{best_pair['pair_id']}`，收益差`{pct(best_pair['delta_total_return'])}`，最大回撤差`{pct(best_pair['delta_max_drawdown'])}`。",
        f"- 质量检查：fail `{len(failed)}`项，warn `{len(warned)}`项。",
        "- 解释：本阶段不追求新高收益，而是判断Stage333的回撤改善是不是可解释、可继续。",
        "",
        "## 总体归因",
        "",
        markdown_table(
            overall_display,
            [
                "pair_id",
                "shape_id",
                "variant_label",
                "base_total_return_pct",
                "variant_total_return_pct",
                "delta_total_return_pct",
                "base_max_drawdown_pct",
                "variant_max_drawdown_pct",
                "delta_max_drawdown_pct",
                "positive_delta_day_ratio_pct",
                "final_relative_equity_gap_pct",
                "avg_actual_symbol_count_delta",
                "avg_zero_lot_target_count_delta",
            ],
            limit=20,
        ),
        "",
        "## 年度归因",
        "",
        markdown_table(
            yearly_display,
            [
                "pair_id",
                "year",
                "base_year_return_pct",
                "variant_year_return_pct",
                "delta_year_return_pct",
                "base_year_drawdown_pct",
                "variant_year_drawdown_pct",
                "delta_year_drawdown_pct",
                "return_and_drawdown_improved",
                "avg_zero_lot_target_count_delta",
            ],
            limit=60,
        ),
        "",
        "## 基准回撤窗口归因",
        "",
        markdown_table(
            drawdown_display,
            [
                "pair_id",
                "window_rank",
                "base_start_date",
                "base_trough_date",
                "base_episode_max_drawdown_pct",
                "base_segment_return_to_trough_pct",
                "variant_segment_return_same_window_pct",
                "delta_segment_return_pct",
                "delta_segment_drawdown_pct",
                "positive_delta_day_ratio_pct",
                "avg_actual_symbol_count_delta",
            ],
            limit=80,
        ),
        "",
        "## 换股重叠率",
        "",
        markdown_table(
            overlap_display,
            [
                "pair_id",
                "signal_days",
                "avg_overlap_ratio_pct",
                "median_overlap_ratio_pct",
                "p10_overlap_ratio_pct",
                "avg_base_only_count",
                "avg_variant_only_count",
                "avg_base_count",
                "avg_variant_count",
            ],
            limit=20,
        ),
        "",
        "## 换股市场状态归因",
        "",
        markdown_table(
            swap_state_display.sort_values(["pair_id", "change_type", "signed_weighted_fwd_excess_10"]),
            [
                "pair_id",
                "change_type",
                "market_state_20d",
                "selected_rows",
                "avg_fwd_excess_ret_10_pct",
                "positive_excess_10_ratio_pct",
                "signed_weighted_fwd_excess_10_pct",
                "avg_mfe_close_10_pct",
                "avg_mae_close_10_pct",
            ],
            limit=80,
        ),
        "",
        "## 换股行业归因",
        "",
        markdown_table(
            swap_ind_display.sort_values(["pair_id", "signed_weighted_fwd_excess_10"]),
            [
                "pair_id",
                "change_type",
                "industry",
                "selected_rows",
                "avg_fwd_excess_ret_10_pct",
                "positive_excess_10_ratio_pct",
                "signed_weighted_fwd_excess_10_pct",
                "avg_mfe_close_10_pct",
                "avg_mae_close_10_pct",
            ],
            limit=100,
        ),
        "",
        "## 信号持有路径代理",
        "",
        markdown_table(
            path_display,
            [
                "pair_id",
                "avg_mfe_delta_pct",
                "avg_mae_delta_pct",
                "delta_path_close_ret_1_pct",
                "delta_path_close_ret_3_pct",
                "delta_path_close_ret_5_pct",
                "delta_path_close_ret_10_pct",
            ],
            limit=20,
        ),
        "",
        "## 真实持仓行业贡献Delta",
        "",
        "### top8混合 vs 简单：最差行业/年份",
        "",
        markdown_table(
            top8_position,
            [
                "pair_id",
                "year",
                "industry",
                "gross_contribution_sum_base_pct",
                "gross_contribution_sum_variant_pct",
                "delta_gross_contribution_sum_pct",
                "delta_negative_contribution_sum_pct",
                "delta_positive_contribution_sum_pct",
                "delta_position_days",
                "delta_avg_actual_weight",
            ],
            limit=40,
        ),
        "",
        "### top5混合 vs 简单：最差行业/年份",
        "",
        markdown_table(
            top5_position,
            [
                "pair_id",
                "year",
                "industry",
                "gross_contribution_sum_base_pct",
                "gross_contribution_sum_variant_pct",
                "delta_gross_contribution_sum_pct",
                "delta_negative_contribution_sum_pct",
                "delta_positive_contribution_sum_pct",
                "delta_position_days",
                "delta_avg_actual_weight",
            ],
            limit=40,
        ),
        "",
        "## 质量检查",
        "",
        markdown_table(quality, ["checkpoint", "status", "value", "expected", "judgement"], limit=50),
        "",
        "## 过拟合反思",
        "",
        "- 运行前判断：否。",
        "- 运行前原因：本阶段只解释第333阶段固定结果，不新增交易阈值、不扩网格。",
        "- 运行后判断：否。",
        "- 运行后原因：输出是归因审计，不会直接形成新策略；后续是否进入状态预算，要看归因是否分散而非集中。",
        "",
        "## 继续价值反思",
        "",
        "- 运行前判断：是。",
        "- 运行前原因：残差层已把top8回撤压进20%以内，必须判断改善来源。",
        "- 运行后判断：见本报告结论；如果改善可解释且不只靠单一行业/年份，继续进入状态预算，否则降级为监控特征。",
        "",
        "## 输出文件",
        "",
    ]
    for name, path in paths.items():
        lines.append(f"- `{name}`：`{path}`")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary = read_source_csv("summary", parse_dates=["date_start", "date_end", "latest_target_date"])
    delta = read_source_csv("delta_vs_simple")
    daily = read_source_csv("daily", parse_dates=["date"])
    selected = read_source_csv("selected", parse_dates=["datetime"])
    orders = read_source_csv("orders", parse_dates=["date"])

    pair_daily = build_pair_daily(daily)
    pair_overall = build_pair_overall(delta, pair_daily)
    yearly = build_year_attribution(pair_daily)
    drawdown_windows = build_drawdown_window_attribution(pair_daily)
    overlap, swaps = build_selection_overlap_and_swaps(selected)
    overlap_summary = summarize_selection_overlap(overlap)
    swap_by_industry = summarize_swaps(swaps, ["pair_id", "shape_id", "variant_label", "change_type", "industry"])
    swap_by_state = summarize_swaps(swaps, ["pair_id", "shape_id", "variant_label", "change_type", "market_state_20d"])
    path_delta, swap_path = build_path_proxy(selected, swaps)
    positions, position_contribution = build_position_contribution(daily, orders)
    quality = build_quality(pair_overall, yearly, drawdown_windows, overlap_summary)

    paths: dict[str, Path] = {
        "report": OUTPUT_DIR / f"{PREFIX}_report.md",
        "pair_overall": OUTPUT_DIR / f"{PREFIX}_pair_overall.csv",
        "pair_daily": OUTPUT_DIR / f"{PREFIX}_pair_daily.csv",
        "yearly": OUTPUT_DIR / f"{PREFIX}_yearly.csv",
        "drawdown_windows": OUTPUT_DIR / f"{PREFIX}_drawdown_windows.csv",
        "selection_overlap": OUTPUT_DIR / f"{PREFIX}_selection_overlap.csv",
        "selection_overlap_summary": OUTPUT_DIR / f"{PREFIX}_selection_overlap_summary.csv",
        "swap_by_industry": OUTPUT_DIR / f"{PREFIX}_swap_by_industry.csv",
        "swap_by_state": OUTPUT_DIR / f"{PREFIX}_swap_by_state.csv",
        "path_delta": OUTPUT_DIR / f"{PREFIX}_path_delta.csv",
        "swap_path": OUTPUT_DIR / f"{PREFIX}_swap_path.csv",
        "positions": OUTPUT_DIR / f"{PREFIX}_positions.csv",
        "position_contribution": OUTPUT_DIR / f"{PREFIX}_position_contribution.csv",
        "quality": OUTPUT_DIR / f"{PREFIX}_quality_checkpoints.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }
    pair_overall.to_csv(paths["pair_overall"], index=False)
    pair_daily.to_csv(paths["pair_daily"], index=False)
    yearly.to_csv(paths["yearly"], index=False)
    drawdown_windows.to_csv(paths["drawdown_windows"], index=False)
    overlap.to_csv(paths["selection_overlap"], index=False)
    overlap_summary.to_csv(paths["selection_overlap_summary"], index=False)
    swap_by_industry.to_csv(paths["swap_by_industry"], index=False)
    swap_by_state.to_csv(paths["swap_by_state"], index=False)
    path_delta.to_csv(paths["path_delta"], index=False)
    swap_path.to_csv(paths["swap_path"], index=False)
    positions.to_csv(paths["positions"], index=False)
    position_contribution.to_csv(paths["position_contribution"], index=False)
    quality.to_csv(paths["quality"], index=False)
    write_json(
        paths["meta"],
        {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "source_dir": str(SOURCE_DIR),
            "source_prefix": SOURCE_PREFIX,
            "account_size_cny": ACCOUNT_SIZE_CNY,
            "line_id": "stock_range_30w_industry_resid_core",
            "stage": 334,
            "pair_specs": [spec.__dict__ for spec in PAIR_SPECS],
            "summary_rows": len(summary),
            "research_sources": RESEARCH_SOURCES,
            "ab_triggered": False,
        },
    )
    report_path = build_report(
        pair_overall,
        yearly,
        drawdown_windows,
        overlap_summary,
        swap_by_industry,
        swap_by_state,
        path_delta,
        position_contribution,
        quality,
        paths,
    )
    print(f"report={report_path}")
    print(pair_overall)
    print(quality)


if __name__ == "__main__":
    main()
