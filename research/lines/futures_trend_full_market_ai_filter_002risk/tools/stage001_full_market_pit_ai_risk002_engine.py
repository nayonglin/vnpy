#!/usr/bin/env python3
"""Stage001: full-market PIT AI filter + 0.02 risk true-engine smoke A/C.

This stage intentionally runs the smallest valid experiment:

- A is read from the frozen current C9/15w Stage167 curve.
- C reuses the C9/15w true engine, swaps in a full-market PIT top8
  eligibility file, and sets all risk_ratio_* fields to 0.02.

The monthly selector uses only information available on or before eval_date.
Existing full-market suitability features are used only as PIT tie-breakers;
future labels are never read.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import itertools
import json
import math
from pathlib import Path
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
PORTFOLIO_DIR = ROOT / "examples" / "portfolio_backtesting"
if str(PORTFOLIO_DIR) not in sys.path:
    sys.path.insert(0, str(PORTFOLIO_DIR))

import analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine as s847  # noqa: E402
import analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow as s901  # noqa: E402
from main_contract_mapping import build_contract_metadata, load_product_universe_symbols  # noqa: E402
from qmt_roll_official_live_config import (  # noqa: E402
    OFFICIAL_LIVE_ALIAS,
    OFFICIAL_LIVE_CAPITAL,
    OFFICIAL_LIVE_PROFILE_NAME,
    OFFICIAL_LIVE_VERSION,
    build_official_live_strategy_overrides,
)
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import (  # noqa: E402
    BASE_RISK_RATIO,
)


LINE_ID = "futures_trend_full_market_ai_filter_002risk"
STAGE_ID = "stage001_full_market_pit_ai_risk002_engine"
STAGE_LABEL = "Stage001"
MODEL_TAG = f"{STAGE_ID}_v2_rankfix"
OUTPUT_PREFIX = f"full_market_ai002_{STAGE_ID}"

REQUESTED_START = pd.Timestamp("2020-01-01")
REQUESTED_END = pd.Timestamp("2026-06-30")
START_MONTH = "2020-01"
CAPITAL = float(OFFICIAL_LIVE_CAPITAL)
TARGET_BASE_RISK_RATIO = 0.02
RISK_MULTIPLIER_FOR_LABEL = TARGET_BASE_RISK_RATIO / float(BASE_RISK_RATIO)
TOP_N = 8
MIN_HISTORY_DAYS = 40
RECENT_PROFIT_DAYS = 126
RECENT_LOSS_DAYS = 63

STRATEGY_NAME = "full_market_pit_profit_memory_top8_risk002_entry_filter"
SCORE_TYPE = "pit_strategy_profit_memory_existing_features_no_future_labels"

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / STAGE_ID
STAGES_DIR = LINE_DIR / "stages"
STAGE_RECORD_PATH = STAGES_DIR / "20260709_1707_stage001_full_market_pit_ai_risk002_engine.md"

FULL_MARKET_UNIVERSE_PATH = (
    PORTFOLIO_DIR
    / "backtest_outputs"
    / "qmt_roll_full_market_tradable_universe_eligible_full_market_tradable_universe_v1.csv"
)
STAGE124_DAILY_DIR = (
    ROOT
    / "research"
    / "lines"
    / "futures_trend_rebuilt_c9_15w_v2_optimization"
    / "outputs"
    / "stage124_full_market_single_product_c9_replay"
    / "daily_by_product"
)
OLD_FEATURES_PATH = (
    PORTFOLIO_DIR
    / "backtest_outputs"
    / "qmt_roll_ai_product_suitability_full_market_walkforward_samples_product_suitability_full_market_wf_v1.csv"
)
OFFICIAL_CURVES_PATH = (
    PORTFOLIO_DIR
    / "backtest_outputs"
    / "qmt_roll_stage167_c9_live_15w_multiperiod_ai_audit_curves_stage167_c9_live_15w_multiperiod_ai_audit_v1.csv"
)
OFFICIAL_SUMMARY_PATH = (
    PORTFOLIO_DIR
    / "backtest_outputs"
    / "qmt_roll_stage167_c9_live_15w_multiperiod_ai_audit_summary_stage167_c9_live_15w_multiperiod_ai_audit_v1.csv"
)

FEATURE_PANEL_PATH = OUT / f"{OUTPUT_PREFIX}_feature_panel_{MODEL_TAG}.csv.gz"
ELIGIBILITY_PATH = OUT / f"{OUTPUT_PREFIX}_eligibility_{MODEL_TAG}.csv"
ELIGIBILITY_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_eligibility_audit_{MODEL_TAG}.csv"
CANDIDATE_DAILY_PATH = OUT / f"{OUTPUT_PREFIX}_candidate_daily_{MODEL_TAG}.csv.gz"
CANDIDATE_ENTRY_CANDIDATES_PATH = OUT / f"{OUTPUT_PREFIX}_candidate_entry_candidates_{MODEL_TAG}.csv.gz"
CANDIDATE_ENTRY_RISK_PATH = OUT / f"{OUTPUT_PREFIX}_candidate_entry_risk_{MODEL_TAG}.csv.gz"
CANDIDATE_TRADES_PATH = OUT / f"{OUTPUT_PREFIX}_candidate_trades_{MODEL_TAG}.csv.gz"
CANDIDATE_TRADE_EVENTS_PATH = OUT / f"{OUTPUT_PREFIX}_candidate_trade_events_{MODEL_TAG}.csv.gz"
CURVES_PATH = OUT / f"{OUTPUT_PREFIX}_ac_curves_{MODEL_TAG}.csv.gz"
SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_ac_summary_{MODEL_TAG}.csv"
AI_USAGE_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_ai_usage_audit_{MODEL_TAG}.csv"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUT / f"{OUTPUT_PREFIX}_equity_drawdown_{MODEL_TAG}.png"

OFFICIAL_VERSION = "official_c9_15w_reference"
CANDIDATE_VERSION = "full_market_pit_ai_top8_risk002"

OLD_FEATURE_COLUMNS: tuple[str, ...] = (
    "simple_trend_suitability_score",
    "market_trend_efficiency_60d",
    "market_trend_efficiency_120d",
    "market_breakout_rate_60d",
    "market_breakout_rate_120d",
    "market_volume_ratio_60d",
    "market_open_interest_change_60d",
    "market_volume_zscore_60d",
    "market_open_interest_zscore_60d",
)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        value = float(value)
    if isinstance(value, float):
        return None if not math.isfinite(value) else value
    try:
        if pd.isna(value) and not isinstance(value, str | bytes):
            return None
    except Exception:
        pass
    return value


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_无记录_"
    data = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    return data.to_markdown(index=False, floatfmt=".4f")


def _date_text(value: Any) -> str:
    return pd.Timestamp(value).date().isoformat()


def _slug(product_vt_symbol: str) -> str:
    return str(product_vt_symbol).replace(".", "_").replace("/", "_")


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    values = pd.to_numeric(equity, errors="coerce").ffill()
    peak = values.cummax()
    return (values / peak.replace(0.0, np.nan) - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0) * 100.0


def _rolling_dd_from_pnl(pnl: pd.Series) -> float:
    if pnl.empty:
        return 0.0
    equity = pnl.cumsum()
    dd = equity - equity.cummax()
    return float(dd.min()) if len(dd) else 0.0


def _daily_sharpe_from_equity(equity: pd.Series) -> float:
    returns = pd.to_numeric(equity, errors="coerce").pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    if returns.empty:
        return 0.0
    std = float(returns.std(ddof=1))
    if std <= 0.0 or not np.isfinite(std):
        return 0.0
    return float(returns.mean() / std * np.sqrt(252.0))


def _sharpe_like_from_pnl(pnl: pd.Series) -> float:
    values = pd.to_numeric(pnl, errors="coerce").fillna(0.0)
    if len(values) < 2:
        return 0.0
    std = float(values.std(ddof=1))
    if std <= 0.0 or not np.isfinite(std):
        return 0.0
    return float(values.mean() / std * np.sqrt(252.0))


def _safe_sum(frame: pd.DataFrame, column: str) -> float:
    if column not in frame.columns:
        return 0.0
    return float(pd.to_numeric(frame[column], errors="coerce").fillna(0.0).sum())


def _rank_pct(frame: pd.DataFrame, column: str, *, lower_is_better: bool = False) -> pd.Series:
    values = pd.to_numeric(frame[column], errors="coerce").replace([np.inf, -np.inf], np.nan)
    if values.notna().sum() <= 1:
        return pd.Series(0.5, index=frame.index, dtype="float64")
    filled = values.fillna(values.median())
    return filled.rank(method="average", pct=True, ascending=not lower_is_better).astype("float64")


def _max_consecutive_true(mask: pd.Series) -> int:
    runs = (len(list(group)) for value, group in itertools.groupby(mask.astype(bool).tolist()) if value)
    return int(max(runs, default=0))


def _load_universe() -> pd.DataFrame:
    frame = pd.read_csv(FULL_MARKET_UNIVERSE_PATH)
    frame["eligible"] = pd.to_numeric(frame.get("eligible", 0), errors="coerce").fillna(0).astype(int)
    frame = frame[frame["eligible"].eq(1)].copy()
    frame["product_vt_symbol"] = frame["product_vt_symbol"].astype(str)
    return frame.sort_values(["exchange", "product_vt_symbol"]).reset_index(drop=True)


def _load_trade_calendar() -> pd.DatetimeIndex:
    frame = pd.read_csv(OFFICIAL_CURVES_PATH, usecols=["date", "requested_start_month"])
    frame = frame[frame["requested_start_month"].astype(str).eq(START_MONTH)].copy()
    dates = pd.to_datetime(frame["date"], errors="coerce").dropna().dt.normalize()
    dates = dates[(dates >= REQUESTED_START) & (dates <= REQUESTED_END)]
    return pd.DatetimeIndex(sorted(dates.unique()))


def _build_eval_dates(calendar: pd.DatetimeIndex) -> list[pd.Timestamp]:
    eval_dates: list[pd.Timestamp] = []
    by_month = pd.Series(calendar).groupby(pd.Series(calendar).dt.to_period("M"))
    for _, group in by_month:
        value = pd.Timestamp(group.max()).normalize()
        if REQUESTED_START <= value <= REQUESTED_END:
            eval_dates.append(value)
    return eval_dates


def _load_product_daily(product_vt_symbol: str) -> pd.DataFrame:
    path = STAGE124_DAILY_DIR / f"{_slug(product_vt_symbol)}_daily.csv.gz"
    if not path.exists():
        return pd.DataFrame(columns=["date", "net_pnl", "trade_count", "slippage", "account_equity"])
    frame = pd.read_csv(path)
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame = frame.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    for column in ["net_pnl", "trade_count", "slippage", "account_equity"]:
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)
    return frame


def _product_features_at(product: str, daily: pd.DataFrame, eval_date: pd.Timestamp) -> dict[str, Any]:
    hist = daily[daily["date"].le(eval_date)].copy()
    if hist.empty:
        return {
            "product_vt_symbol": product,
            "eval_date": eval_date,
            "history_days": 0,
            "cumulative_net_pnl_to_date": 0.0,
            "recent_profit_126d": 0.0,
            "recent_net_pnl_63d": 0.0,
            "recent_loss_pressure_63d": 0.0,
            "recent_sharpe_126d": 0.0,
            "recent_drawdown_126d": 0.0,
            "active_days_126d": 0,
            "trade_count_126d": 0.0,
            "slippage_126d": 0.0,
            "data_available": 0,
        }
    pnl = pd.to_numeric(hist["net_pnl"], errors="coerce").fillna(0.0)
    recent126 = hist.tail(RECENT_PROFIT_DAYS).copy()
    recent63 = hist.tail(RECENT_LOSS_DAYS).copy()
    pnl126 = pd.to_numeric(recent126["net_pnl"], errors="coerce").fillna(0.0)
    pnl63 = pd.to_numeric(recent63["net_pnl"], errors="coerce").fillna(0.0)
    recent63_sum = float(pnl63.sum())
    return {
        "product_vt_symbol": product,
        "eval_date": eval_date,
        "history_days": int(len(hist)),
        "cumulative_net_pnl_to_date": float(pnl.sum()),
        "recent_profit_126d": float(pnl126.sum()),
        "recent_net_pnl_63d": recent63_sum,
        "recent_loss_pressure_63d": float(max(0.0, -recent63_sum)),
        "recent_sharpe_126d": _sharpe_like_from_pnl(pnl126),
        "recent_drawdown_126d": _rolling_dd_from_pnl(pnl126),
        "active_days_126d": int((pnl126.abs() > 1e-12).sum()),
        "trade_count_126d": float(pd.to_numeric(recent126.get("trade_count", 0.0), errors="coerce").fillna(0.0).sum()),
        "slippage_126d": float(pd.to_numeric(recent126.get("slippage", 0.0), errors="coerce").fillna(0.0).sum()),
        "data_available": int(len(hist) >= MIN_HISTORY_DAYS),
    }


def _load_old_features() -> pd.DataFrame:
    if not OLD_FEATURES_PATH.exists():
        return pd.DataFrame(columns=["eval_date", "product_vt_symbol"])
    usecols = ["eval_date", "product_vt_symbol", *OLD_FEATURE_COLUMNS]
    frame = pd.read_csv(OLD_FEATURES_PATH, usecols=lambda c: c in set(usecols))
    frame["eval_date"] = pd.to_datetime(frame["eval_date"], errors="coerce").dt.normalize()
    frame["product_vt_symbol"] = frame["product_vt_symbol"].astype(str)
    for column in OLD_FEATURE_COLUMNS:
        if column not in frame.columns:
            frame[column] = np.nan
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.dropna(subset=["eval_date", "product_vt_symbol"]).drop_duplicates(
        ["eval_date", "product_vt_symbol"],
        keep="last",
    )


def _build_feature_panel(universe: pd.DataFrame, eval_dates: list[pd.Timestamp]) -> pd.DataFrame:
    daily_by_product = {
        product: _load_product_daily(product) for product in universe["product_vt_symbol"].astype(str).tolist()
    }
    rows: list[dict[str, Any]] = []
    for eval_date in eval_dates:
        for product, daily in daily_by_product.items():
            rows.append(_product_features_at(product, daily, eval_date))
    panel = pd.DataFrame(rows)
    panel = panel.merge(
        universe[
            [
                "product_vt_symbol",
                "exchange",
                "product",
                "is_static_strategy_product",
                "recent_bar_coverage_ratio",
                "recent_median_volume",
                "estimated_margin_per_contract",
            ]
        ],
        on="product_vt_symbol",
        how="left",
    )
    old_features = _load_old_features()
    if not old_features.empty:
        panel = panel.merge(old_features, on=["eval_date", "product_vt_symbol"], how="left")
    else:
        for column in OLD_FEATURE_COLUMNS:
            panel[column] = np.nan

    score_frames: list[pd.DataFrame] = []
    for eval_date, group in panel.groupby("eval_date", sort=True):
        data = group.copy()
        data["rank_all_cycle_profit"] = _rank_pct(data, "cumulative_net_pnl_to_date")
        data["rank_recent_profit_126d"] = _rank_pct(data, "recent_profit_126d")
        data["rank_recent_profit_63d"] = _rank_pct(data, "recent_net_pnl_63d")
        data["rank_low_recent_loss_63d"] = _rank_pct(data, "recent_loss_pressure_63d", lower_is_better=True)
        data["rank_recent_sharpe_126d"] = _rank_pct(data, "recent_sharpe_126d")
        data["rank_low_drawdown_126d"] = _rank_pct(data, "recent_drawdown_126d")
        data["rank_activity_126d"] = _rank_pct(data, "active_days_126d")

        old_rank_columns: list[str] = []
        for column in OLD_FEATURE_COLUMNS:
            rank_column = f"rank_old_{column}"
            data[rank_column] = _rank_pct(data, column)
            old_rank_columns.append(rank_column)
        data["existing_feature_available_count"] = data[list(OLD_FEATURE_COLUMNS)].notna().sum(axis=1).astype(int)
        data["existing_feature_score"] = data[old_rank_columns].mean(axis=1).fillna(0.5)

        raw_score = (
            0.24 * data["rank_all_cycle_profit"]
            + 0.20 * data["rank_recent_profit_126d"]
            + 0.15 * data["rank_recent_profit_63d"]
            + 0.14 * data["rank_low_recent_loss_63d"]
            + 0.10 * data["rank_recent_sharpe_126d"]
            + 0.07 * data["rank_low_drawdown_126d"]
            + 0.06 * data["rank_activity_126d"]
            + 0.04 * data["existing_feature_score"]
        )
        data["score_before_history_gate"] = raw_score
        data["score"] = np.where(data["data_available"].eq(1), raw_score, raw_score * 0.25)
        data["score_rank_all_products"] = data["score"].rank(method="first", ascending=False).astype(int)
        eligible = data[data["data_available"].eq(1)].copy()
        eligible["score_rank"] = eligible["score"].rank(method="first", ascending=False).astype(int)
        selected_products = set(eligible.nsmallest(TOP_N, "score_rank")["product_vt_symbol"].astype(str).tolist())
        data["selected_topn"] = data["product_vt_symbol"].astype(str).isin(selected_products).astype(int)
        data["score_rank"] = data["score_rank_all_products"]
        score_frames.append(data)
    result = pd.concat(score_frames, ignore_index=True, sort=False)
    result["eval_date"] = pd.to_datetime(result["eval_date"], errors="coerce").dt.normalize()
    return result.sort_values(["eval_date", "score_rank_all_products", "product_vt_symbol"]).reset_index(drop=True)


def _build_eligibility(feature_panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    selected = feature_panel[feature_panel["selected_topn"].eq(1)].copy()
    selected = selected.sort_values(["eval_date", "score", "product_vt_symbol"], ascending=[True, False, True])
    selected["score_rank"] = selected.groupby("eval_date").cumcount() + 1
    selected["top_n"] = TOP_N
    selected["strategy"] = STRATEGY_NAME
    selected["score_type"] = SCORE_TYPE
    eligibility = selected[
        ["strategy", "score_type", "eval_date", "product_vt_symbol", "score", "score_rank", "top_n"]
    ].copy()
    eligibility["eval_date"] = eligibility["eval_date"].dt.date.astype(str)

    audit = (
        feature_panel.groupby("eval_date", as_index=False)
        .agg(
            all_product_count=("product_vt_symbol", "count"),
            data_available_count=("data_available", "sum"),
            selected_count=("selected_topn", "sum"),
            old_feature_rows=("existing_feature_available_count", lambda s: int((s > 0).sum())),
            min_score=("score", "min"),
            max_score=("score", "max"),
        )
        .sort_values("eval_date")
    )
    audit["eval_date"] = pd.to_datetime(audit["eval_date"], errors="coerce").dt.date.astype(str)
    return eligibility, audit


def _metadata() -> dict[str, Any]:
    supported_symbols = load_product_universe_symbols(str(FULL_MARKET_UNIVERSE_PATH))
    return build_contract_metadata(supported_symbols=supported_symbols)


def _candidate_profile(metadata: dict[str, Any]) -> dict[str, Any]:
    profile = s847._c9_profile(metadata)
    spec = profile["spec"]
    profile_name = "stage001_full_market_pit_ai_top8_risk002"
    capital = replace(
        spec.capital,
        variant=profile_name,
        label="Stage001 full-market PIT AI top8 + risk_ratio_0.02",
        account_capital=CAPITAL,
        c3_capital=CAPITAL,
        risk_multiplier=RISK_MULTIPLIER_FOR_LABEL,
        note=(
            f"{spec.capital.note} | Stage001 independent line. Full-market PIT top8 eligibility, "
            "no fixed satellite product, all risk_ratio_* fields set to 0.02."
        ),
    )
    live_overrides = dict(build_official_live_strategy_overrides())
    overrides = {
        **spec.overrides,
        **live_overrides,
        "product_universe_csv_path": str(FULL_MARKET_UNIVERSE_PATH),
        "enable_ai_product_pool_filter": True,
        "ai_product_pool_eligibility_path": str(ELIGIBILITY_PATH),
        "ai_product_pool_strategy": STRATEGY_NAME,
        "account_capital": CAPITAL,
        "c3_capital": CAPITAL,
        "risk_ratio_of_total_assets": TARGET_BASE_RISK_RATIO,
        "risk_ratio_breakout": TARGET_BASE_RISK_RATIO,
        "risk_ratio_ma_cross_breakout": TARGET_BASE_RISK_RATIO,
        "risk_ratio_open_interest_surge": TARGET_BASE_RISK_RATIO,
        "risk_ratio_open_interest_decline": TARGET_BASE_RISK_RATIO,
        "risk_ratio_volume_open_interest_surge": TARGET_BASE_RISK_RATIO,
    }
    result = dict(profile)
    result["profile"] = profile_name
    result["strategy_cls"] = s847.QmtRollPortfolioStrategyStage847C9StopRetry
    result["spec"] = replace(spec, capital=capital, overrides=overrides, profile=profile_name)
    return result


def _run_candidate(metadata: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, pd.DataFrame], Any]:
    original_start = s847.START
    original_end = s847.END
    original_minute_by_symbol = s847.s827._GLOBAL_MINUTE_BY_SYMBOL
    s901._ensure_c9_minute_bars(metadata)
    try:
        s847.START = REQUESTED_START.normalize()
        s847.END = REQUESTED_END.normalize()
        profile = _candidate_profile(metadata)
        combined, frames = s847._run_profile(profile, metadata)
        spec = profile["spec"]
    finally:
        s847.START = original_start
        s847.END = original_end
        s847.s827._GLOBAL_MINUTE_BY_SYMBOL = original_minute_by_symbol
    combined = combined.copy()
    combined["account_capital"] = CAPITAL
    combined["c3_capital"] = CAPITAL
    combined["profile"] = spec.profile
    combined["version"] = CANDIDATE_VERSION
    combined["requested_start_month"] = START_MONTH
    combined["stage"] = STAGE_LABEL
    combined["model_tag"] = MODEL_TAG
    combined["line_id"] = LINE_ID
    for frame in frames.values():
        if frame.empty:
            continue
        frame["account_capital"] = CAPITAL
        frame["c3_capital"] = CAPITAL
        frame["profile"] = spec.profile
        frame["version"] = CANDIDATE_VERSION
        frame["stage"] = STAGE_LABEL
        frame["model_tag"] = MODEL_TAG
        frame["line_id"] = LINE_ID
    return combined, frames, spec


def _read_official_curve() -> pd.DataFrame:
    frame = pd.read_csv(OFFICIAL_CURVES_PATH)
    frame = frame[frame["requested_start_month"].astype(str).eq(START_MONTH)].copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame = frame[(frame["date"] >= REQUESTED_START) & (frame["date"] <= REQUESTED_END)].copy()
    frame["version"] = OFFICIAL_VERSION
    frame["stage"] = STAGE_LABEL
    frame["model_tag"] = MODEL_TAG
    frame["line_id"] = LINE_ID
    return frame.sort_values("date").reset_index(drop=True)


def _curve_for_metrics(frame: pd.DataFrame, version: str) -> pd.DataFrame:
    data = frame.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    data = data.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    data["version"] = version
    data["account_capital_for_metrics"] = CAPITAL
    data["account_equity_for_metrics"] = pd.to_numeric(data["account_equity"], errors="coerce")
    return data


def _summarize_curve(frame: pd.DataFrame) -> dict[str, Any]:
    data = frame.sort_values("date").reset_index(drop=True)
    equity = pd.to_numeric(data["account_equity_for_metrics"], errors="coerce").ffill()
    net_pnl = pd.to_numeric(data.get("net_pnl", 0.0), errors="coerce").fillna(0.0)
    dd = _drawdown_pct(equity)
    below = equity < CAPITAL - 1e-9
    nonzero = net_pnl.abs() > 1e-12
    return {
        "stage": STAGE_LABEL,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "version": str(data["version"].iloc[0]),
        "requested_start_month": START_MONTH,
        "actual_start": _date_text(data["date"].iloc[0]),
        "actual_end": _date_text(data["date"].iloc[-1]),
        "trading_days": int(len(data)),
        "account_capital": CAPITAL,
        "end_equity": float(equity.iloc[-1]),
        "total_return_pct": float((equity.iloc[-1] / CAPITAL - 1.0) * 100.0),
        "max_drawdown_pct": float(dd.min()),
        "sharpe": _daily_sharpe_from_equity(equity),
        "total_slippage": _safe_sum(data, "slippage"),
        "total_trade_count": _safe_sum(data, "trade_count"),
        "nonzero_daily_win_rate_pct": float((net_pnl[nonzero] > 0.0).mean() * 100.0) if bool(nonzero.any()) else 0.0,
        "days_below_initial": int(below.sum()),
        "max_consecutive_below_initial_days": _max_consecutive_true(below),
        "max_broker10_margin_to_equity_pct": float(
            pd.to_numeric(data.get("broker10_margin_to_equity_pct", pd.Series(dtype=float)), errors="coerce").max()
        )
        if "broker10_margin_to_equity_pct" in data.columns
        else np.nan,
    }


def _ai_usage_audit(entry_candidates: pd.DataFrame) -> pd.DataFrame:
    if entry_candidates.empty:
        return pd.DataFrame(
            [
                {
                    "ai_usage_rows": 0,
                    "ai_enabled_rows": 0,
                    "ai_allowed_rows": 0,
                    "ai_blocked_rows": 0,
                    "signal_date_count": 0,
                    "missing_signal_date_rows": 0,
                }
            ]
        )
    data = entry_candidates.copy()
    for column in ["ai_product_pool_enabled", "ai_product_pool_allowed", "is_opened"]:
        data[column] = pd.to_numeric(data.get(column, 0), errors="coerce").fillna(0).astype(int)
    by_signal = (
        data.groupby("ai_product_pool_signal_date", dropna=False, as_index=False)
        .agg(
            candidate_rows=("product_vt_symbol", "count"),
            allowed_rows=("ai_product_pool_allowed", "sum"),
            opened_rows=("is_opened", "sum"),
            products=("product_vt_symbol", "nunique"),
        )
        .sort_values("ai_product_pool_signal_date")
    )
    summary = pd.DataFrame(
        [
            {
                "ai_product_pool_signal_date": "__summary__",
                "candidate_rows": int(len(data)),
                "allowed_rows": int(data["ai_product_pool_allowed"].sum()),
                "opened_rows": int(data["is_opened"].sum()),
                "products": int(data["product_vt_symbol"].nunique()) if "product_vt_symbol" in data.columns else 0,
                "ai_usage_rows": int(len(data)),
                "ai_enabled_rows": int(data["ai_product_pool_enabled"].sum()),
                "ai_allowed_rows": int(data["ai_product_pool_allowed"].sum()),
                "ai_blocked_rows": int((data["ai_product_pool_enabled"].eq(1) & data["ai_product_pool_allowed"].eq(0)).sum()),
                "signal_date_count": int(data["ai_product_pool_signal_date"].replace("", np.nan).dropna().nunique())
                if "ai_product_pool_signal_date" in data.columns
                else 0,
                "missing_signal_date_rows": int(data.get("ai_product_pool_signal_date", pd.Series([""] * len(data))).astype(str).eq("").sum()),
            }
        ]
    )
    for column in ["ai_usage_rows", "ai_enabled_rows", "ai_allowed_rows", "ai_blocked_rows", "signal_date_count", "missing_signal_date_rows"]:
        if column not in by_signal.columns:
            by_signal[column] = np.nan
    return pd.concat([summary, by_signal], ignore_index=True, sort=False)


def _plot(curves: pd.DataFrame) -> None:
    if curves.empty:
        return
    fig, axes = plt.subplots(2, 1, figsize=(13, 8), sharex=True)
    colors = {OFFICIAL_VERSION: "#111827", CANDIDATE_VERSION: "#2563eb"}
    labels = {OFFICIAL_VERSION: "Official C9/15w", CANDIDATE_VERSION: "Stage001 full-market AI + risk 0.02"}
    for version, group in curves.groupby("version", sort=False):
        data = group.sort_values("date")
        x = pd.to_datetime(data["date"])
        equity = pd.to_numeric(data["account_equity_for_metrics"], errors="coerce").ffill()
        axes[0].plot(x, equity, label=labels.get(version, version), color=colors.get(version), linewidth=1.1)
        axes[1].plot(x, _drawdown_pct(equity), label=labels.get(version, version), color=colors.get(version), linewidth=1.0)
    axes[0].axhline(CAPITAL, color="#64748b", linestyle="--", linewidth=0.9)
    axes[0].set_title("Stage001 A/C equity")
    axes[0].set_ylabel("account equity")
    axes[0].grid(alpha=0.25)
    axes[0].legend(loc="best")
    axes[1].axhline(-40.0, color="#111827", linestyle="--", linewidth=0.9)
    axes[1].set_title("Stage001 A/C drawdown")
    axes[1].set_ylabel("drawdown %")
    axes[1].grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(CHART_PATH, dpi=170)
    plt.close(fig)


def _decision(summary: pd.DataFrame, eligibility_audit: pd.DataFrame, ai_usage: pd.DataFrame) -> dict[str, Any]:
    a = summary[summary["version"].eq(OFFICIAL_VERSION)].iloc[0].to_dict()
    c = summary[summary["version"].eq(CANDIDATE_VERSION)].iloc[0].to_dict()
    min_selected = int(pd.to_numeric(eligibility_audit["selected_count"], errors="coerce").min()) if not eligibility_audit.empty else 0
    usage_summary = ai_usage[ai_usage["ai_product_pool_signal_date"].astype(str).eq("__summary__")]
    usage = usage_summary.iloc[0].to_dict() if not usage_summary.empty else {}
    return {
        "stage": STAGE_LABEL,
        "stage_id": STAGE_ID,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S CST"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "official_live_profile_name": OFFICIAL_LIVE_PROFILE_NAME,
        "hypothesis": "Full-market PIT product filtering can improve product opportunity selection while risk_ratio_* is normalized to 0.02.",
        "anti_lookahead": "Feature panel uses product daily rows <= eval_date and old PIT feature columns only; future_* labels are excluded.",
        "top_n": TOP_N,
        "target_base_risk_ratio": TARGET_BASE_RISK_RATIO,
        "base_risk_ratio_source": BASE_RISK_RATIO,
        "risk_multiplier_for_label": RISK_MULTIPLIER_FOR_LABEL,
        "a_official": a,
        "c_candidate": c,
        "return_delta_pct": float(c["total_return_pct"] - a["total_return_pct"]),
        "drawdown_delta_pct": float(c["max_drawdown_pct"] - a["max_drawdown_pct"]),
        "min_monthly_selected_count": min_selected,
        "ai_usage_summary": usage,
        "decision": (
            "stage001_continue_to_halfyear_if_review_passes"
            if c["total_return_pct"] > 0 and c["max_drawdown_pct"] > -65.0 and min_selected >= TOP_N
            else "stage001_stop_or_attribution_before_more_runs"
        ),
        "overfit_before": (
            "yes_high_risk: full-market selection and profit-memory features can chase historical winners; mitigated by PIT monthly snapshots, fixed top8, fixed weights, and no rescue tuning."
        ),
        "overfit_after": "pending_independent_review",
        "continue_value_before": "yes: tests a structurally different product-pool selector requested by user without touching live execution.",
        "continue_value_after": "pending_independent_review",
    }


def _write_report(summary: pd.DataFrame, eligibility: pd.DataFrame, eligibility_audit: pd.DataFrame, ai_usage: pd.DataFrame, decision: dict[str, Any]) -> None:
    latest_pool = eligibility[eligibility["eval_date"].astype(str).eq(str(eligibility["eval_date"].max()))].copy()
    top_counts = (
        eligibility.groupby("product_vt_symbol", as_index=False)
        .size()
        .rename(columns={"size": "selected_months"})
        .sort_values(["selected_months", "product_vt_symbol"], ascending=[False, True])
        .head(20)
    )
    lines = [
        "# Stage001 全市场 PIT AI 过滤 + 0.02 基础风险真实引擎",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        f"- 当前模式：`day`",
        "- 阶段性质：独立研究线最小真实引擎 A/C；不改官方实盘、CTP、邮件或 launchd。",
        "- 外部调研判断：meta-labeling/ML 过滤更适合作为 primary strategy 的机会过滤器，不应替代交易逻辑；managed futures 全市场横截面排序有理论基础，但必须做 PIT 和多周期验证。",
        "- 运行前过拟合判断：有风险。全市场扩池和收益记忆特征容易追历史赢家，本阶段用固定 top8、固定权重、PIT eval_date、单起点第一关控制自由度。",
        "- 运行前继续价值判断：有。它正面回答用户提出的“全市场 AI 过滤 + 0.02 风险”结构性问题。",
        "",
        "## A/C 结果",
        "",
        _md_table(
            summary[
                [
                    "version",
                    "end_equity",
                    "total_return_pct",
                    "max_drawdown_pct",
                    "sharpe",
                    "total_slippage",
                    "total_trade_count",
                    "nonzero_daily_win_rate_pct",
                    "days_below_initial",
                    "max_consecutive_below_initial_days",
                    "max_broker10_margin_to_equity_pct",
                ]
            ]
        ),
        "",
        "## 最新一期 AI 池",
        "",
        _md_table(latest_pool[["eval_date", "product_vt_symbol", "score", "score_rank", "top_n"]]),
        "",
        "## 入选月份最多的品种",
        "",
        _md_table(top_counts),
        "",
        "## AI 文件审计",
        "",
        _md_table(eligibility_audit.tail(12)),
        "",
        "## AI 使用审计",
        "",
        _md_table(ai_usage.head(20)),
        "",
        "## 决策",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- 输出图：`{CHART_PATH}`",
        "- 运行后过拟合判断：先标记为 pending，必须等待独立 agent 审计后再决定是否扩展逐半年多周期。",
        "- 运行后继续价值判断：先标记为 pending，必须等待独立 agent 审计后再决定。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_stage_record(summary: pd.DataFrame, decision: dict[str, Any]) -> None:
    c = summary[summary["version"].eq(CANDIDATE_VERSION)].iloc[0].to_dict()
    a = summary[summary["version"].eq(OFFICIAL_VERSION)].iloc[0].to_dict()
    lines = [
        "# Stage001 全市场 PIT AI 过滤 + 0.02 基础风险真实引擎",
        "",
        f"- line_id：`{LINE_ID}`",
        "- 当前模式：`day`",
        f"- 记录时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        "- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`",
        "- 阶段性质：独立研究线最小 A/C 真实引擎回测",
        "- 是否重要突破：否，第一关验证",
        "- 是否触发A/B：是，A=官方 C9/15w；C=全市场 PIT AI top8 + risk_ratio_* 0.02",
        "",
        "## 外部调研与判断",
        "",
        "- 参考资料：Hudson & Thames meta-labeling、AQR managed futures、QuantInsti cross-sectional momentum ML、stefan-jansen/machine-learning-for-trading。",
        "- 我的判断：AI/ML 更适合作为趋势策略外层过滤或排序，不应直接改趋势入场/退出；全市场排序必须 PIT、walk-forward、多起点验证。",
        "",
        "## 本次变更",
        "",
        f"- 新增脚本：`research/lines/{LINE_ID}/tools/stage001_full_market_pit_ai_risk002_engine.py`",
        "- 修改脚本：无",
        "- 删除脚本：无",
        "- 新增参数：`TOP_N=8`、`TARGET_BASE_RISK_RATIO=0.02`、`RECENT_PROFIT_DAYS=126`、`RECENT_LOSS_DAYS=63`、`MIN_HISTORY_DAYS=40`",
        "- 修改参数：候选 C 显式覆盖 `risk_ratio_of_total_assets/breakout/ma_cross/open_interest_surge/open_interest_decline/volume_open_interest_surge=0.02`；`product_universe_csv_path` 改为 full-market 57 品种；AI strategy 改为本阶段 PIT eligibility。",
        "- 删除参数：候选 C 不强制固定 `fu.SHFE` satellite。",
        "",
        "## 回测/归因参数",
        "",
        f"- 数据区间：`{REQUESTED_START.date()}` 到 `{REQUESTED_END.date()}`",
        f"- 账户规模：`{CAPITAL:,.0f}`",
        "- 成本口径：沿用 C9 真实引擎原成本/slippage 配置。",
        "- 样本过滤：当前 full-market eligible 57 品种，月度 PIT top8。",
        "- 策略/归因口径：A 复用 Stage167 官方 C9/15w 曲线；C 新跑真实引擎。",
        "",
        "## 结果",
        "",
        f"- A 期末权益：`{a['end_equity']:,.2f}`；总收益 `{a['total_return_pct']:.4f}%`；最大回撤 `{a['max_drawdown_pct']:.4f}%`；Sharpe `{a['sharpe']:.4f}`",
        f"- C 期末权益：`{c['end_equity']:,.2f}`",
        f"- C 总收益：`{c['total_return_pct']:.4f}%`",
        f"- C 最大回撤：`{c['max_drawdown_pct']:.4f}%`",
        f"- C Sharpe：`{c['sharpe']:.4f}`",
        f"- C 总滑点：`{c['total_slippage']:,.2f}`",
        f"- C 总交易次数：`{c['total_trade_count']:,.0f}`",
        f"- C 胜率：`{c['nonzero_daily_win_rate_pct']:.4f}%`，口径为非零交易日胜率，不是逐笔胜率。",
        f"- C 最大 broker10 保证金/权益：`{c['max_broker10_margin_to_equity_pct']:.4f}%`",
        f"- C 相对 A 收益差：`{decision['return_delta_pct']:.4f}` 百分点；回撤差：`{decision['drawdown_delta_pct']:.4f}` 百分点。",
        "",
        "## 输出文件",
        "",
        f"- report：`{REPORT_PATH}`",
        f"- summary：`{SUMMARY_PATH}`",
        f"- eligibility：`{ELIGIBILITY_PATH}`",
        f"- feature_panel：`{FEATURE_PANEL_PATH}`",
        f"- daily：`{CANDIDATE_DAILY_PATH}`",
        f"- quality：`{AI_USAGE_AUDIT_PATH}`",
        "",
        "## 结论",
        "",
        f"- 本阶段结论：`{decision['decision']}`",
        "- 是否进入下一步：等待独立 agent review 后决定。",
        "- 下一步：如果 review 通过且不是明显失败，再跑 2020-01 到 2026-06 逐半年多周期；否则先归因。",
        "",
        "## 过拟合反思",
        "",
        "- 运行前判断：是，有明显风险，因为全市场收益记忆可能追历史赢家。",
        "- 运行后判断：等待独立 review；本阶段没有根据结果调整 topN、窗口、权重或风险小数。",
        "- 原因：仅固定一个预声明形状，后续不能在失败后救参。",
        "",
        "## 继续价值反思",
        "",
        "- 运行前判断：有价值，因为它检验用户提出的结构性问题。",
        "- 运行后判断：等待独立 review；只有结果与审计都可接受才扩展多周期。",
        "- 原因：单起点只是第一关，不足以证明晋级。",
        "",
        "## 合入建议",
        "",
        "- 是否更新本线 `LINE.md`：是，记录 Stage001 状态。",
        "- 是否更新 `research/registry.md`：本阶段已在建线时新增索引，暂不进一步改。",
        "- 是否追加根目录 `memory.md/back_log.md`：已追加 `back_log.md`，不改 `memory.md`。",
    ]
    STAGE_RECORD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _append_back_log(summary: pd.DataFrame, decision: dict[str, Any]) -> None:
    c = summary[summary["version"].eq(CANDIDATE_VERSION)].iloc[0].to_dict()
    a = summary[summary["version"].eq(OFFICIAL_VERSION)].iloc[0].to_dict()
    log_path = ROOT / "back_log.md"
    text = (
        f"\n{datetime.now().strftime('%Y-%m-%d %H:%M CST')}：`{LINE_ID}` Stage001 完成全市场 PIT AI top8 + `risk_ratio_* = 0.02` "
        f"最小真实引擎 A/C，决策 `{decision['decision']}`。新增脚本 `research/lines/{LINE_ID}/tools/stage001_full_market_pit_ai_risk002_engine.py`；"
        f"新增 eligibility `{ELIGIBILITY_PATH}`，feature panel `{FEATURE_PANEL_PATH}`，report `{REPORT_PATH}`。"
        f"新增参数：`TOP_N=8`、`TARGET_BASE_RISK_RATIO=0.02`、`RECENT_PROFIT_DAYS=126`、`RECENT_LOSS_DAYS=63`、`MIN_HISTORY_DAYS=40`；"
        "修改参数：候选 C 使用 full-market 57 品种 universe，AI strategy 改为本阶段 PIT eligibility，"
        "`risk_ratio_of_total_assets/breakout/ma_cross/open_interest_surge/open_interest_decline/volume_open_interest_surge` 全部覆盖为 `0.02`；"
        "删除参数：候选 C 不固定追加 `fu.SHFE` satellite。"
        f"A 官方 C9/15w：期末权益 `{a['end_equity']:,.2f}`、总收益 `{a['total_return_pct']:.4f}%`、最大回撤 `{a['max_drawdown_pct']:.4f}%`、"
        f"Sharpe `{a['sharpe']:.4f}`、总滑点 `{a['total_slippage']:,.2f}`、总交易次数 `{a['total_trade_count']:,.0f}`、"
        f"非零交易日胜率 `{a['nonzero_daily_win_rate_pct']:.4f}%`。"
        f"C 候选：期末权益 `{c['end_equity']:,.2f}`、总收益 `{c['total_return_pct']:.4f}%`、最大回撤 `{c['max_drawdown_pct']:.4f}%`、"
        f"Sharpe `{c['sharpe']:.4f}`、总滑点 `{c['total_slippage']:,.2f}`、总交易次数 `{c['total_trade_count']:,.0f}`、"
        f"胜率 `{c['nonzero_daily_win_rate_pct']:.4f}%`（非零交易日胜率口径）。"
        f"新增结果：C 相对 A 收益差 `{decision['return_delta_pct']:.4f}` 百分点，回撤差 `{decision['drawdown_delta_pct']:.4f}` 百分点；"
        "删除结果：无。运行前过拟合反思：是，高风险，full-market 和收益记忆容易追历史赢家；本阶段用 PIT、固定 top8/窗口/权重/0.02 控制。"
        "运行后过拟合反思：待独立 agent review；本阶段没有根据结果救参。运行前继续价值反思：有，检验结构性全市场 AI 过滤问题。"
        "运行后继续价值反思：待独立 agent review 后决定是否扩展逐半年多周期。\n"
    )
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(text)


def _update_line(summary: pd.DataFrame, decision: dict[str, Any]) -> None:
    line_path = LINE_DIR / "LINE.md"
    if not line_path.exists():
        return
    c = summary[summary["version"].eq(CANDIDATE_VERSION)].iloc[0].to_dict()
    addition = (
        "\n## Stage001\n\n"
        f"- 时间: `{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`\n"
        f"- 决策: `{decision['decision']}`\n"
        f"- C 期末权益: `{c['end_equity']:,.2f}`，总收益 `{c['total_return_pct']:.4f}%`，最大回撤 `{c['max_drawdown_pct']:.4f}%`，Sharpe `{c['sharpe']:.4f}`。\n"
        "- 状态: 已跑单起点真实引擎，等待独立 agent review 后再决定是否扩展逐半年多周期。\n"
    )
    with line_path.open("a", encoding="utf-8") as fh:
        fh.write(addition)


def build() -> dict[str, pd.DataFrame]:
    OUT.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)

    universe = _load_universe()
    calendar = _load_trade_calendar()
    eval_dates = _build_eval_dates(calendar)
    feature_panel = _build_feature_panel(universe, eval_dates)
    eligibility, eligibility_audit = _build_eligibility(feature_panel)

    feature_panel.to_csv(FEATURE_PANEL_PATH, index=False, encoding="utf-8-sig")
    eligibility.to_csv(ELIGIBILITY_PATH, index=False, encoding="utf-8-sig")
    eligibility_audit.to_csv(ELIGIBILITY_AUDIT_PATH, index=False, encoding="utf-8-sig")

    metadata = _metadata()
    candidate_daily, frames, _spec = _run_candidate(metadata)
    candidate_daily.to_csv(CANDIDATE_DAILY_PATH, index=False, encoding="utf-8-sig")
    for name, path in (
        ("entry_candidates", CANDIDATE_ENTRY_CANDIDATES_PATH),
        ("entry_risk", CANDIDATE_ENTRY_RISK_PATH),
        ("trades", CANDIDATE_TRADES_PATH),
        ("trade_events", CANDIDATE_TRADE_EVENTS_PATH),
    ):
        frame = frames.get(name, pd.DataFrame()).copy()
        if not frame.empty:
            frame.to_csv(path, index=False, encoding="utf-8-sig")

    official_curve = _curve_for_metrics(_read_official_curve(), OFFICIAL_VERSION)
    candidate_curve = _curve_for_metrics(candidate_daily, CANDIDATE_VERSION)
    curves = pd.concat([official_curve, candidate_curve], ignore_index=True, sort=False)
    curves = curves.sort_values(["version", "date"]).reset_index(drop=True)
    summary = pd.DataFrame([_summarize_curve(group) for _, group in curves.groupby("version", sort=False)])
    ai_usage = _ai_usage_audit(frames.get("entry_candidates", pd.DataFrame()))
    decision = _decision(summary, eligibility_audit, ai_usage)

    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    ai_usage.to_csv(AI_USAGE_AUDIT_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _plot(curves)
    _write_report(summary, eligibility, eligibility_audit, ai_usage, decision)
    _write_stage_record(summary, decision)
    _append_back_log(summary, decision)
    _update_line(summary, decision)

    return {
        "feature_panel": feature_panel,
        "eligibility": eligibility,
        "eligibility_audit": eligibility_audit,
        "candidate_daily": candidate_daily,
        "curves": curves,
        "summary": summary,
        "ai_usage": ai_usage,
    }


def main() -> None:
    outputs = build()
    summary = outputs["summary"]
    print(summary.to_string(index=False))
    print(f"report={REPORT_PATH}")
    print(f"chart={CHART_PATH}")


if __name__ == "__main__":
    main()
