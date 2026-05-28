from __future__ import annotations

import importlib.util
import json
import math
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from analyze_qmt_roll_stage324_true_combo_capital_margin import (
    TOTAL_CAPITAL as FUTURES_CAPITAL,
    _c3_overrides,
    _to_builtin,
)
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy
from qmt_universe import END_DT, PRELOAD_START_DT, START_DT
from run_qmt_alignment_backtest import (
    OUTPUT_DIR,
    build_entry_candidate_snapshots_df,
    build_positions_df,
)
from run_qmt_roll_backtest import (
    build_backtest_engine,
    build_roll_setting,
    compute_round_trip_win_ratio,
)
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


PROJECT_DIR = Path(__file__).resolve().parent
STAGE087_SCRIPT = PROJECT_DIR / "analyze_qmt_roll_stage387_stage079_short_holding_candidates.py"
MODEL_TAG = "stage396_stage079_breadth_crowding_state_diagnostic_v1"
OUTPUT_PREFIX = "qmt_roll_stage396_stage079_breadth_crowding_state_diagnostic"
LINE_ID = "futures_trend_drawdown30_preserve_return"

ACCOUNT_CAPITAL = 615_000.0
STAGE079_CASH = 115_000.0
BASELINE_VARIANT = "stage079"

DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_{MODEL_TAG}.csv"
POSITIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_positions_{MODEL_TAG}.csv"
SNAPSHOT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_candidate_snapshots_{MODEL_TAG}.csv"
STATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_state_daily_{MODEL_TAG}.csv"
WINDOW_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_state_{MODEL_TAG}.csv"
BUCKET_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_summary_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_state_chart_{MODEL_TAG}.png"


def _load_stage087_module():
    spec = importlib.util.spec_from_file_location("stage087_gate_for_stage396", STAGE087_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {STAGE087_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["stage087_gate_for_stage396"] = module
    spec.loader.exec_module(module)
    return module


s087 = _load_stage087_module()


@dataclass(frozen=True)
class StateBucket:
    name: str
    label: str
    predicate: Callable[[pd.DataFrame], pd.Series]
    reason: str


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(result) or math.isinf(result):
        return default
    return result


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "无数据。"
    view = frame.copy()
    if max_rows is not None:
        view = view.head(max_rows)
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: f"{x:.4f}" if pd.notna(x) else "")
    return view.to_markdown(index=False)


def _product_from_vt_symbol(vt_symbol: object) -> str:
    raw = str(vt_symbol or "")
    if "." not in raw:
        return raw
    symbol, exchange = raw.split(".", 1)
    product = "".join(ch for ch in symbol if ch.isalpha()) or symbol
    return f"{product}.{exchange}"


def _stage079_probe_overrides() -> dict[str, Any]:
    overrides = dict(_c3_overrides(START_DT))
    # Weight floor 1.0 makes the env gate a no-op but records broad daily candidate-state fields.
    overrides.update(
        {
            "enable_weighted_env_gate": True,
            "weighted_env_gate_weight_floor": 1.0,
        }
    )
    return overrides


def _run_stage079_probe() -> tuple[pd.DataFrame, dict[str, Any], pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    preload_start = max(PRELOAD_START_DT, START_DT - timedelta(days=365))
    overrides = _stage079_probe_overrides()
    print("[stage396] run Stage079 env-probe no-op engine", flush=True)
    engine, metadata = build_backtest_engine(
        preload_start=preload_start,
        backtest_end=END_DT,
        capital=FUTURES_CAPITAL,
        product_universe_csv_path=str(overrides.get("product_universe_csv_path", "") or ""),
    )
    setting = build_roll_setting(
        metadata["margin_ratios"],
        risk_ratio=BASE_RISK_RATIO,
        strategy_overrides=overrides,
    )
    setting["capital_base"] = FUTURES_CAPITAL
    engine.add_strategy(QmtRollPortfolioStrategy, setting)
    engine.load_data()
    engine.run_backtesting()
    daily_df = engine.calculate_result()
    if daily_df is None or daily_df.empty:
        raise RuntimeError("empty Stage079 probe daily result")
    analysis_df = daily_df.copy()
    analysis_df = analysis_df.loc[
        (analysis_df.index >= START_DT.date())
        & (analysis_df.index <= END_DT.date())
    ]
    statistics = dict(engine.calculate_statistics(analysis_df))
    win_ratio_pct, win_count, round_trip_count = compute_round_trip_win_ratio(engine)
    statistics["win_ratio"] = win_ratio_pct
    statistics["win_count"] = win_count
    statistics["round_trip_count"] = round_trip_count
    positions = build_positions_df(engine)
    snapshots = build_entry_candidate_snapshots_df(engine)
    return analysis_df, statistics, positions, snapshots, metadata


def _daily_equity(analysis_df: pd.DataFrame) -> pd.DataFrame:
    frame = analysis_df.copy().reset_index().rename(columns={"index": "date"})
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame = frame.dropna(subset=["date"]).sort_values("date").drop_duplicates("date", keep="last")
    frame["active_balance"] = pd.to_numeric(frame.get("balance", FUTURES_CAPITAL), errors="coerce").ffill().fillna(FUTURES_CAPITAL)
    frame["active_net_pnl"] = pd.to_numeric(frame.get("net_pnl", 0.0), errors="coerce").fillna(0.0)
    frame["active_slippage"] = pd.to_numeric(frame.get("slippage", 0.0), errors="coerce").fillna(0.0)
    frame["equity"] = frame["active_balance"] + STAGE079_CASH
    return frame[["date", "active_balance", "active_net_pnl", "active_slippage", "equity"]]


def _position_state(positions: pd.DataFrame, daily: pd.DataFrame, metadata: dict[str, Any] | None = None) -> pd.DataFrame:
    if positions.empty:
        return pd.DataFrame({"date": daily["date"]})
    frame = positions.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame["product_vt_symbol"] = frame["vt_symbol"].map(_product_from_vt_symbol)
    for column in ("end_pos", "close_price"):
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)
    sizes = metadata.get("sizes", {}) if metadata else {}
    margin_ratios = metadata.get("margin_ratios", {}) if metadata else {}
    frame["size"] = frame["vt_symbol"].map(lambda x: sizes.get(str(x), 1.0) if isinstance(sizes, dict) else 1.0).fillna(1.0)
    frame["margin_ratio"] = frame["vt_symbol"].map(
        lambda x: margin_ratios.get(str(x), 0.15) if isinstance(margin_ratios, dict) else 0.15
    ).fillna(0.15)
    frame["abs_pos"] = frame["end_pos"].abs()
    frame["position_margin"] = frame["abs_pos"] * frame["close_price"].clip(lower=0.0) * frame["size"] * frame["margin_ratio"]
    active = frame[frame["abs_pos"] > 0].copy()
    if active.empty:
        result = pd.DataFrame({"date": pd.to_datetime(daily["date"])})
        return result

    product = (
        active.groupby(["date", "product_vt_symbol"], as_index=False)
        .agg(
            product_margin=("position_margin", "sum"),
            product_net_pos=("end_pos", "sum"),
        )
    )
    product["product_direction"] = np.where(product["product_net_pos"] > 0, "long", "short")
    daily_state = (
        product.groupby("date")
        .agg(
            active_product_count=("product_vt_symbol", "nunique"),
            total_margin_proxy=("product_margin", "sum"),
            top_product_margin_proxy=("product_margin", "max"),
            long_product_count=("product_direction", lambda x: int((x == "long").sum())),
            short_product_count=("product_direction", lambda x: int((x == "short").sum())),
            long_margin_proxy=("product_margin", lambda x: float(x[product.loc[x.index, "product_direction"].eq("long")].sum())),
            short_margin_proxy=("product_margin", lambda x: float(x[product.loc[x.index, "product_direction"].eq("short")].sum())),
        )
        .reset_index()
    )
    total_margin = daily_state["total_margin_proxy"].replace(0.0, np.nan)
    daily_state["top_product_margin_share"] = (daily_state["top_product_margin_proxy"] / total_margin).fillna(0.0)
    daily_state["direction_margin_imbalance"] = (
        (daily_state["long_margin_proxy"] - daily_state["short_margin_proxy"]).abs() / total_margin
    ).fillna(0.0)
    equity = daily[["date", "equity"]].copy()
    daily_state = daily_state.merge(equity, on="date", how="left")
    daily_state["margin_to_equity_proxy"] = (
        daily_state["total_margin_proxy"] / daily_state["equity"].replace(0.0, np.nan)
    ).fillna(0.0)
    return daily_state.drop(columns=["equity"])


def _snapshot_state(snapshots: pd.DataFrame) -> pd.DataFrame:
    if snapshots.empty:
        return pd.DataFrame()
    frame = snapshots.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame = frame.dropna(subset=["date"])
    frame["is_opened_flag"] = (
        pd.to_numeric(frame.get("is_opened", 0), errors="coerce").fillna(0).astype(int).eq(1)
        | frame.get("candidate_status", "").astype(str).eq("opened")
    ).astype(int)
    frame["selected_volume"] = pd.to_numeric(frame.get("selected_volume", 0), errors="coerce").fillna(0.0)
    frame["native_selected"] = pd.to_numeric(frame.get("selected_volume_ungated", 0), errors="coerce").fillna(0.0).gt(0).astype(int)
    frame["long_candidate"] = frame["direction"].astype(str).eq("long").astype(int)
    frame["short_candidate"] = frame["direction"].astype(str).eq("short").astype(int)
    frame["long_opened_volume"] = np.where(frame["direction"].astype(str).eq("long"), frame["selected_volume"], 0.0)
    frame["short_opened_volume"] = np.where(frame["direction"].astype(str).eq("short"), frame["selected_volume"], 0.0)
    numeric_mean_cols = [
        "env_candidate_count",
        "env_native_selected_rate",
        "env_avg_close_position_60d",
        "env_avg_range_pct_zscore_120",
        "same_direction_correlation_active_count",
        "same_direction_correlation_corr_count",
        "same_direction_correlation_max_corr",
        "same_direction_correlation_avg_corr",
        "active_positions_before",
    ]
    for col in numeric_mean_cols:
        frame[col] = pd.to_numeric(frame.get(col, 0.0), errors="coerce").fillna(0.0)
    state = (
        frame.groupby("date")
        .agg(
            entry_candidate_snapshot_count=("candidate_index", "count"),
            opened_candidate_count=("is_opened_flag", "sum"),
            native_selected_count=("native_selected", "sum"),
            long_candidate_count=("long_candidate", "sum"),
            short_candidate_count=("short_candidate", "sum"),
            opened_volume_sum=("selected_volume", "sum"),
            long_opened_volume=("long_opened_volume", "sum"),
            short_opened_volume=("short_opened_volume", "sum"),
            env_candidate_count_mean=("env_candidate_count", "mean"),
            env_native_selected_rate_mean=("env_native_selected_rate", "mean"),
            env_avg_close_position_60d_mean=("env_avg_close_position_60d", "mean"),
            env_avg_range_pct_zscore_120_mean=("env_avg_range_pct_zscore_120", "mean"),
            same_direction_correlation_active_count_max=("same_direction_correlation_active_count", "max"),
            same_direction_correlation_corr_count_max=("same_direction_correlation_corr_count", "max"),
            same_direction_correlation_max_corr_max=("same_direction_correlation_max_corr", "max"),
            same_direction_correlation_avg_corr_mean=("same_direction_correlation_avg_corr", "mean"),
            active_positions_before_max=("active_positions_before", "max"),
        )
        .reset_index()
    )
    total_opened = (state["long_opened_volume"] + state["short_opened_volume"]).replace(0.0, np.nan)
    state["opened_direction_imbalance"] = (
        (state["long_opened_volume"] - state["short_opened_volume"]).abs() / total_opened
    ).fillna(0.0)
    state["candidate_direction_imbalance"] = (
        (state["long_candidate_count"] - state["short_candidate_count"]).abs()
        / (state["long_candidate_count"] + state["short_candidate_count"]).replace(0, np.nan)
    ).fillna(0.0)
    return state


def _build_state_daily(
    daily: pd.DataFrame,
    positions: pd.DataFrame,
    snapshots: pd.DataFrame,
    metadata: dict[str, Any] | None = None,
) -> pd.DataFrame:
    calendar = pd.date_range(daily["date"].min(), daily["date"].max(), freq="D")
    state = pd.DataFrame({"date": calendar})
    pos_state = _position_state(positions, daily, metadata)
    snap_state = _snapshot_state(snapshots)
    if not pos_state.empty:
        state = state.merge(pos_state, on="date", how="left")
    if not snap_state.empty:
        state = state.merge(snap_state, on="date", how="left")

    ffill_cols = [
        "active_product_count",
        "total_margin_proxy",
        "top_product_margin_proxy",
        "long_product_count",
        "short_product_count",
        "long_margin_proxy",
        "short_margin_proxy",
        "top_product_margin_share",
        "direction_margin_imbalance",
        "margin_to_equity_proxy",
    ]
    zero_cols = [col for col in state.columns if col != "date" and col not in ffill_cols]
    state[ffill_cols] = state[ffill_cols].ffill().fillna(0.0)
    state[zero_cols] = state[zero_cols].fillna(0.0)
    return state


def _equity_series(daily: pd.DataFrame) -> pd.Series:
    frame = daily[["date", "equity"]].copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame = frame.dropna(subset=["date"]).sort_values("date").drop_duplicates("date", keep="last")
    equity = pd.Series(frame["equity"].to_numpy(dtype=float), index=frame["date"])
    calendar = pd.date_range(equity.index.min(), equity.index.max(), freq="D")
    return equity.reindex(calendar).ffill().dropna()


def _longest_underwater_days(values: pd.Series) -> int:
    high = values.cummax()
    underwater = values.lt(high)
    longest = 0
    current = 0
    for flag in underwater.to_numpy(dtype=bool):
        if flag:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return int(longest)


def _future_window_metrics(equity: pd.Series, horizon_days: int) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    values = equity.astype(float)
    for start_date in values.index:
        end_date = start_date + pd.Timedelta(days=horizon_days)
        if end_date > values.index.max():
            continue
        window = values.loc[start_date:end_date]
        if len(window) < 2:
            continue
        start_equity = float(window.iloc[0])
        end_equity = float(window.iloc[-1])
        nav = window / start_equity
        high = nav.cummax()
        dd = nav / high - 1.0
        max_dd_pct = float(dd.min() * 100.0)
        ulcer_pct = float(np.sqrt(np.mean(np.square(np.minimum(dd.to_numpy(dtype=float), 0.0)))) * 100.0)
        ret_pct = float((end_equity / start_equity - 1.0) * 100.0)
        ann_return_pct = float((end_equity / start_equity) ** (365.0 / horizon_days) - 1.0) * 100.0
        rows.append(
            {
                "date": start_date,
                "horizon_days": horizon_days,
                "future_return_pct": ret_pct,
                "future_annualized_return_pct": ann_return_pct,
                "future_positive": int(ret_pct > 0.0),
                "future_annualized_below_5pct": int(ann_return_pct < 5.0),
                "future_max_dd_pct": max_dd_pct,
                "future_dd20_breach": int(max_dd_pct <= -20.0),
                "future_dd30_breach": int(max_dd_pct <= -30.0),
                "future_ulcer_pct": ulcer_pct,
                "future_longest_underwater_days": _longest_underwater_days(window),
            }
        )
    return pd.DataFrame(rows)


def _bucket_definitions() -> list[StateBucket]:
    return [
        StateBucket(
            "no_active_position",
            "无持仓启动",
            lambda df: df["active_product_count"].le(0),
            "检验短体验是否主要来自空仓后重新进场，而不是持仓期水下。",
        ),
        StateBucket(
            "single_active_product",
            "单品种持仓启动",
            lambda df: df["active_product_count"].eq(1),
            "检验单品种路径风险是否影响启动体验。",
        ),
        StateBucket(
            "broad_active_3plus",
            "3个及以上品种持仓启动",
            lambda df: df["active_product_count"].ge(3),
            "检验多品种持仓是否比单腿路径更稳定。",
        ),
        StateBucket(
            "top_margin_share_ge70",
            "头部品种保证金占比>=70%",
            lambda df: df["top_product_margin_share"].ge(0.70) & df["active_product_count"].ge(1),
            "检验持仓收益来源过于集中时的后续体验。",
        ),
        StateBucket(
            "direction_imbalance_ge80",
            "持仓方向保证金偏向>=80%",
            lambda df: df["direction_margin_imbalance"].ge(0.80) & df["active_product_count"].ge(1),
            "检验方向拥挤是否带来反转回撤。",
        ),
        StateBucket(
            "entry_candidates_3plus",
            "当日入场候选>=3",
            lambda df: df["entry_candidate_snapshot_count"].ge(3),
            "检验信号广度较宽是否改善后续体验。",
        ),
        StateBucket(
            "opened_candidates_2plus",
            "当日实际开仓候选>=2",
            lambda df: df["opened_candidate_count"].ge(2),
            "检验集中开新仓日是否带来后续水下。",
        ),
        StateBucket(
            "opened_direction_imbalance_ge80",
            "当日开仓方向偏向>=80%",
            lambda df: df["opened_direction_imbalance"].ge(0.80) & df["opened_candidate_count"].ge(2),
            "检验同向集中开仓是否是坏启动日来源。",
        ),
        StateBucket(
            "same_direction_corr_ge60",
            "同向相关最高>=0.60",
            lambda df: df["same_direction_correlation_max_corr_max"].ge(0.60)
            & df["same_direction_correlation_corr_count_max"].ge(1),
            "检验同向高相关候选是否恶化短体验。",
        ),
        StateBucket(
            "margin_to_equity_ge60",
            "保证金/权益代理>=60%",
            lambda df: df["margin_to_equity_proxy"].ge(0.60),
            "检验高资金占用状态是否解释短窗口体验。",
        ),
    ]


def _window_state(daily: pd.DataFrame, state: pd.DataFrame) -> pd.DataFrame:
    equity = _equity_series(daily)
    windows = pd.concat([_future_window_metrics(equity, 90), _future_window_metrics(equity, 180)], ignore_index=True)
    merged = windows.merge(state, on="date", how="left")
    merged.sort_values(["horizon_days", "date"], inplace=True)
    return merged


def _summarize_bucket(window_state: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    buckets = _bucket_definitions()
    for horizon_days, horizon_df in window_state.groupby("horizon_days"):
        baseline_bad_return_threshold = -8.0 if int(horizon_days) == 90 else 0.0
        horizon_df = horizon_df.copy()
        horizon_df["target_bad_experience"] = (
            horizon_df["future_return_pct"].lt(baseline_bad_return_threshold)
            | horizon_df["future_dd20_breach"].eq(1)
            | horizon_df["future_annualized_below_5pct"].eq(1)
        ).astype(int)
        total_bad = int(horizon_df["target_bad_experience"].sum())
        for bucket in buckets:
            mask = bucket.predicate(horizon_df).fillna(False).astype(bool)
            for side_name, side_mask in (("bucket", mask), ("complement", ~mask)):
                subset = horizon_df[side_mask]
                if subset.empty:
                    continue
                rows.append(
                    {
                        "bucket": bucket.name,
                        "bucket_label": bucket.label,
                        "side": side_name,
                        "horizon_days": int(horizon_days),
                        "support_days": int(len(subset)),
                        "coverage_rate": float(len(subset) / max(len(horizon_df), 1)),
                        "bad_experience_rate": float(subset["target_bad_experience"].mean()),
                        "bad_experience_capture_rate": float(
                            subset["target_bad_experience"].sum() / total_bad if total_bad else 0.0
                        ),
                        "return_p05_pct": float(subset["future_return_pct"].quantile(0.05)),
                        "return_median_pct": float(subset["future_return_pct"].median()),
                        "positive_return_rate": float(subset["future_positive"].mean()),
                        "annualized_below_5pct_rate": float(subset["future_annualized_below_5pct"].mean()),
                        "max_dd_worst_pct": float(subset["future_max_dd_pct"].min()),
                        "dd20_breach_rate": float(subset["future_dd20_breach"].mean()),
                        "dd30_breach_rate": float(subset["future_dd30_breach"].mean()),
                        "ulcer_p95_pct": float(subset["future_ulcer_pct"].quantile(0.95)),
                        "longest_underwater_p95_days": float(subset["future_longest_underwater_days"].quantile(0.95)),
                        "reason": bucket.reason,
                    }
                )
    summary = pd.DataFrame(rows)
    if summary.empty:
        return summary
    bucket_side = summary.pivot(index=["bucket", "bucket_label", "horizon_days"], columns="side")
    rows2: list[dict[str, Any]] = []
    metrics = [
        "support_days",
        "coverage_rate",
        "bad_experience_rate",
        "bad_experience_capture_rate",
        "return_p05_pct",
        "return_median_pct",
        "positive_return_rate",
        "annualized_below_5pct_rate",
        "max_dd_worst_pct",
        "dd20_breach_rate",
        "dd30_breach_rate",
        "ulcer_p95_pct",
        "longest_underwater_p95_days",
    ]
    for idx in bucket_side.index:
        row: dict[str, Any] = {
            "bucket": idx[0],
            "bucket_label": idx[1],
            "horizon_days": idx[2],
        }
        for metric in metrics:
            bucket_col = (metric, "bucket")
            complement_col = (metric, "complement")
            bucket_value = bucket_side.loc[idx, bucket_col] if bucket_col in bucket_side.columns else np.nan
            complement_value = bucket_side.loc[idx, complement_col] if complement_col in bucket_side.columns else np.nan
            row[f"{metric}_bucket"] = _safe_float(bucket_value, np.nan)
            row[f"{metric}_complement"] = _safe_float(complement_value, np.nan)
        row["bad_experience_rate_lift"] = row["bad_experience_rate_bucket"] - row["bad_experience_rate_complement"]
        row["return_p05_delta_vs_complement"] = row["return_p05_pct_bucket"] - row["return_p05_pct_complement"]
        row["dd20_breach_rate_lift"] = row["dd20_breach_rate_bucket"] - row["dd20_breach_rate_complement"]
        row["ulcer_p95_delta_vs_complement"] = row["ulcer_p95_pct_bucket"] - row["ulcer_p95_pct_complement"]
        rows2.append(row)
    result = pd.DataFrame(rows2)
    result.sort_values(
        ["horizon_days", "bad_experience_rate_lift", "bad_experience_capture_rate_bucket"],
        ascending=[True, False, False],
        inplace=True,
    )
    return result.reset_index(drop=True)


def _summary_from_stats(statistics: dict[str, Any], daily: pd.DataFrame) -> pd.DataFrame:
    equity = _equity_series(daily)
    candidate = s087.Candidate(
        BASELINE_VARIANT,
        "Stage079 env-probe no-op baseline",
        equity,
        ACCOUNT_CAPITAL,
        "baseline_probe",
        True,
        "用于导出状态变量；weighted_env_gate floor=1.0，不改变交易。",
    )
    stats = s087._stats(candidate)
    stats.update(
        {
            "engine_total_slippage": _safe_float(statistics.get("total_slippage")),
            "engine_total_trade_count": _safe_float(statistics.get("total_trade_count")),
            "engine_win_ratio": _safe_float(statistics.get("win_ratio")),
        }
    )
    return pd.DataFrame([stats])


def _decision(bucket_summary: pd.DataFrame, snapshots: pd.DataFrame) -> dict[str, Any]:
    strong = pd.DataFrame()
    if not bucket_summary.empty:
        strong = bucket_summary[
            bucket_summary["support_days_bucket"].ge(120)
            & bucket_summary["bad_experience_capture_rate_bucket"].ge(0.25)
            & (
                bucket_summary["bad_experience_rate_lift"].ge(0.08)
                | bucket_summary["dd20_breach_rate_lift"].ge(0.08)
            )
            & bucket_summary["return_p05_delta_vs_complement"].lt(0.0)
        ].copy()
    strong_buckets = sorted(strong["bucket"].unique().tolist()) if not strong.empty else []
    return {
        "stage": "Stage096",
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": "diagnostic_only_no_candidate",
        "strong_state_buckets": strong_buckets,
        "entry_snapshot_rows": int(len(snapshots)),
        "note": (
            "只读诊断；若 strong_state_buckets 非空，也只能冻结一个粗结构候选做下一阶段验证，"
            "不得围绕阈值小数扫描。"
        ),
    }


def _plot_state(daily: pd.DataFrame, state: pd.DataFrame, bucket_summary: pd.DataFrame) -> None:
    equity = _equity_series(daily)
    nav = equity / ACCOUNT_CAPITAL
    dd = nav / nav.cummax() - 1.0
    state_i = state.set_index("date").reindex(equity.index).ffill().fillna(0.0)
    fig, axes = plt.subplots(4, 1, figsize=(18, 14), sharex=True)
    axes[0].plot(nav.index, nav.values, label="Stage079 NAV", color="#1f77b4", linewidth=1.5)
    axes[0].set_title("Stage096 Stage079 state diagnostic")
    axes[0].set_ylabel("NAV")
    axes[0].grid(True, alpha=0.25)
    axes[0].legend(loc="upper left")

    axes[1].plot(dd.index, dd.values * 100.0, label="Drawdown %", color="#d62728", linewidth=1.0)
    axes[1].axhline(-20.0, color="#777777", linestyle="--", linewidth=0.8)
    axes[1].axhline(-30.0, color="#333333", linestyle="--", linewidth=0.8)
    axes[1].set_ylabel("DD %")
    axes[1].grid(True, alpha=0.25)
    axes[1].legend(loc="lower left")

    axes[2].plot(state_i.index, state_i["active_product_count"], label="active products", color="#2ca02c")
    axes[2].plot(state_i.index, state_i["top_product_margin_share"], label="top margin share", color="#ff7f0e", alpha=0.8)
    axes[2].plot(state_i.index, state_i["direction_margin_imbalance"], label="direction imbalance", color="#9467bd", alpha=0.8)
    axes[2].set_ylabel("Position state")
    axes[2].grid(True, alpha=0.25)
    axes[2].legend(loc="upper left")

    axes[3].plot(state_i.index, state_i["entry_candidate_snapshot_count"], label="entry candidates", color="#17becf")
    axes[3].plot(state_i.index, state_i["opened_candidate_count"], label="opened candidates", color="#bcbd22")
    axes[3].plot(state_i.index, state_i["same_direction_correlation_max_corr_max"], label="same-dir max corr", color="#8c564b")
    axes[3].set_ylabel("Entry state")
    axes[3].grid(True, alpha=0.25)
    axes[3].legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=150)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    bucket_summary: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    focus_cols = [
        "bucket",
        "bucket_label",
        "horizon_days",
        "support_days_bucket",
        "bad_experience_rate_bucket",
        "bad_experience_rate_lift",
        "bad_experience_capture_rate_bucket",
        "return_p05_pct_bucket",
        "return_p05_delta_vs_complement",
        "dd20_breach_rate_bucket",
        "dd20_breach_rate_lift",
        "ulcer_p95_pct_bucket",
    ]
    top_rows = bucket_summary[focus_cols].head(16) if not bucket_summary.empty else pd.DataFrame(columns=focus_cols)
    lines = [
        "# Stage096 Stage079趋势广度/拥挤度状态诊断",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "- 阶段性质：只读状态变量归因；不修改默认交易规则。",
        f"- 图表：`{CHART_PATH}`",
        "",
        "## 外部调研与判断",
        "",
        "- 趋势跟随文献和CTA实践更重视风险预算、趋势强度、组合分散度和波动状态，而不是单一入场信号胜率。",
        "- 但仓库内 Stage034/035 已反证常规波动预算真引擎，Stage090-092 已反证权益暴涨冷却真引擎，因此本阶段只做广度/拥挤度只读诊断，不直接形成交易规则。",
        "",
        "## 决策",
        "",
        "```json",
        json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2),
        "```",
        "",
        "## Stage079探针复验",
        "",
        _md_table(summary),
        "",
        "## 状态桶诊断 Top",
        "",
        _md_table(top_rows, max_rows=16),
        "",
        "## 反过拟合说明",
        "",
        "- 本阶段只使用启动日前已经可观察的持仓/候选状态，并在全样本所有启动日上做关联。",
        "- 只使用预声明粗桶：单品种、3品种以上、头部保证金70%、方向80%、候选3个、开仓2个、相关0.60、保证金60%。",
        "- 如果没有跨90/180天同时成立的强状态桶，不会继续调阈值救援。",
        "",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    analysis_df, statistics, positions, snapshots, metadata = _run_stage079_probe()
    daily = _daily_equity(analysis_df)
    state = _build_state_daily(daily, positions, snapshots, metadata)
    window_state = _window_state(daily, state)
    bucket_summary = _summarize_bucket(window_state)
    summary = _summary_from_stats(statistics, daily)
    decision = _decision(bucket_summary, snapshots)

    daily.to_csv(DAILY_PATH, index=False, encoding="utf-8-sig")
    positions.to_csv(POSITIONS_PATH, index=False, encoding="utf-8-sig")
    snapshots.to_csv(SNAPSHOT_PATH, index=False, encoding="utf-8-sig")
    state.to_csv(STATE_PATH, index=False, encoding="utf-8-sig")
    window_state.to_csv(WINDOW_PATH, index=False, encoding="utf-8-sig")
    bucket_summary.to_csv(BUCKET_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _plot_state(daily, state, bucket_summary)
    _write_report(summary, bucket_summary, decision)
    print(json.dumps(_to_builtin(decision), ensure_ascii=False, indent=2))
    print(f"[stage396] report={REPORT_PATH}")
    print(f"[stage396] chart={CHART_PATH}")


if __name__ == "__main__":
    main()
