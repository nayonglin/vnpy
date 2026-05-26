from __future__ import annotations

import json
import math
import re
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd

from analyze_qmt_roll_stage324_true_combo_capital_margin import (
    TOTAL_CAPITAL,
    _c3_overrides,
    _metadata,
    _path_metrics,
    _safe_float,
    _to_builtin,
    _to_markdown_table,
)
from qmt_roll_official_stage78_config import OFFICIAL_STAGE78_ROLE, OFFICIAL_STAGE78_VERSION
from qmt_universe import END_DT, PRELOAD_START_DT, START_DT
from run_qmt_alignment_backtest import (
    OUTPUT_DIR,
    build_entry_candidate_snapshots_df,
    build_entry_risk_diagnostics_df,
    build_positions_df,
    build_trades_df,
)
from run_qmt_roll_backtest import run_backtest as run_roll_backtest
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO
from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.database import get_database


MODEL_TAG = "stage328_c3_single_path_loss_attribution_v1"
OUTPUT_PREFIX = "qmt_roll_stage328_c3_single_path_loss_attribution"
LINE_ID = "futures_trend_drawdown30_preserve_return"


def _product_from_vt_symbol(vt_symbol: object) -> str:
    raw = str(vt_symbol)
    if "." not in raw:
        return raw
    symbol, exchange = raw.split(".", 1)
    match = re.match(r"^[A-Za-z]+", symbol)
    product = match.group(0) if match else symbol
    return f"{product}.{exchange}"


def _parse_vt_symbol(vt_symbol: str) -> tuple[str, Exchange]:
    symbol, exchange = str(vt_symbol).split(".", 1)
    return symbol, Exchange(exchange)


def _daily_from_analysis(analysis_df: pd.DataFrame | None) -> pd.DataFrame:
    if analysis_df is None or analysis_df.empty:
        return pd.DataFrame(columns=["date", "balance", "net_pnl", "trade_count", "slippage", "commission"])
    frame = analysis_df.copy().reset_index().rename(columns={"index": "date"})
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    frame = frame.sort_values("date").drop_duplicates("date", keep="last")
    frame["balance"] = pd.to_numeric(frame.get("balance", TOTAL_CAPITAL), errors="coerce").ffill().fillna(TOTAL_CAPITAL)
    for column in ["net_pnl", "trade_count", "slippage", "commission"]:
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce").fillna(0.0)
    return frame[["date", "balance", "net_pnl", "trade_count", "slippage", "commission"]]


def _drawdown_window(daily: pd.DataFrame) -> dict[str, Any]:
    curve = daily[["date", "balance"]].copy().sort_values("date")
    curve["highlevel"] = curve["balance"].cummax()
    curve["ddpercent"] = (curve["balance"] / curve["highlevel"].replace(0.0, np.nan) - 1.0) * 100.0
    curve["ddpercent"] = curve["ddpercent"].fillna(0.0)
    trough_row = curve.loc[curve["ddpercent"].idxmin()]
    peak_candidates = curve[curve["date"] <= trough_row["date"]]
    peak_row = peak_candidates.loc[peak_candidates["balance"].idxmax()]
    return {
        "peak_date": pd.Timestamp(peak_row["date"]).normalize(),
        "trough_date": pd.Timestamp(trough_row["date"]).normalize(),
        "peak_balance": float(peak_row["balance"]),
        "trough_balance": float(trough_row["balance"]),
        "max_dd_percent": float(trough_row["ddpercent"]),
        "curve": curve,
    }


def _run_c3() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    preload_start = max(PRELOAD_START_DT, START_DT - timedelta(days=365))
    print("[stage328] run C3 full-sample 50w for single-path attribution", flush=True)
    engine, analysis_df, statistics = run_roll_backtest(
        risk_ratio=BASE_RISK_RATIO,
        strategy_overrides=_c3_overrides(START_DT),
        analysis_start=START_DT,
        analysis_end=END_DT,
        preload_start=preload_start,
        capital=TOTAL_CAPITAL,
        save_artifacts=False,
        include_start_year_sweep=False,
        file_prefix=f"{OUTPUT_PREFIX}_c3_base",
        chart_title="Stage328 C3 single path loss attribution",
    )
    return (
        _daily_from_analysis(analysis_df),
        build_positions_df(engine),
        build_trades_df(engine),
        build_entry_candidate_snapshots_df(engine),
        build_entry_risk_diagnostics_df(engine),
        statistics,
    )


def _position_direction(direction: str, offset: str) -> str | None:
    direction = str(direction)
    offset = str(offset)
    if offset == "Open":
        return "long" if direction == "Long" else "short"
    if offset == "Close":
        return "long" if direction == "Short" else "short"
    return None


def _build_round_trips(trades: pd.DataFrame, metadata: dict[str, Any]) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()

    frame = trades.copy()
    frame["datetime"] = pd.to_datetime(frame["datetime"]).dt.tz_localize(None)
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    frame.sort_values(["datetime", "vt_symbol", "trade_id"], inplace=True)

    open_queues: dict[tuple[str, str], list[dict[str, Any]]] = {}
    rows: list[dict[str, Any]] = []
    leg_index = 0

    for trade in frame.to_dict("records"):
        vt_symbol = str(trade["vt_symbol"])
        pos_direction = _position_direction(str(trade["direction"]), str(trade["offset"]))
        if pos_direction is None:
            continue
        key = (vt_symbol, pos_direction)
        volume = float(trade["volume"])
        if str(trade["offset"]) == "Open":
            open_queues.setdefault(key, []).append(
                {
                    "entry_trade_id": str(trade["trade_id"]),
                    "entry_order_id": str(trade["order_id"]),
                    "entry_datetime": pd.Timestamp(trade["datetime"]),
                    "entry_date": pd.Timestamp(trade["date"]),
                    "entry_price": float(trade["price"]),
                    "direction": pos_direction,
                    "remaining_volume": volume,
                    "original_volume": volume,
                }
            )
            continue

        queue = open_queues.get(key, [])
        remaining = volume
        while remaining > 1e-8 and queue:
            entry = queue[0]
            used = min(float(entry["remaining_volume"]), remaining)
            size = float(metadata["sizes"].get(vt_symbol, 1.0))
            sign = 1.0 if pos_direction == "long" else -1.0
            exit_price = float(trade["price"])
            pnl = (exit_price - float(entry["entry_price"])) * sign * used * size
            leg_index += 1
            rows.append(
                {
                    "leg_id": leg_index,
                    "vt_symbol": vt_symbol,
                    "product_vt_symbol": _product_from_vt_symbol(vt_symbol),
                    "direction": pos_direction,
                    "entry_trade_id": entry["entry_trade_id"],
                    "exit_trade_id": str(trade["trade_id"]),
                    "entry_datetime": entry["entry_datetime"],
                    "exit_datetime": pd.Timestamp(trade["datetime"]),
                    "entry_date": entry["entry_date"],
                    "exit_date": pd.Timestamp(trade["date"]),
                    "entry_price": float(entry["entry_price"]),
                    "exit_price": exit_price,
                    "volume": used,
                    "size": size,
                    "gross_pnl": pnl,
                    "gross_return_pct": (exit_price / float(entry["entry_price"]) - 1.0) * sign * 100.0
                    if float(entry["entry_price"]) > 0
                    else math.nan,
                    "exit_reason": trade.get("exit_reason"),
                }
            )
            entry["remaining_volume"] = float(entry["remaining_volume"]) - used
            remaining -= used
            if float(entry["remaining_volume"]) <= 1e-8:
                queue.pop(0)

    if not rows:
        return pd.DataFrame()
    result = pd.DataFrame(rows)
    result["holding_days"] = (result["exit_date"] - result["entry_date"]).dt.days.astype(int)
    return result


def _load_bars_for_round_trips(round_trips: pd.DataFrame) -> dict[str, pd.DataFrame]:
    if round_trips.empty:
        return {}
    database = get_database()
    bars_by_symbol: dict[str, pd.DataFrame] = {}
    for vt_symbol, group in round_trips.groupby("vt_symbol"):
        symbol, exchange = _parse_vt_symbol(str(vt_symbol))
        start_dt = pd.Timestamp(group["entry_date"].min()).to_pydatetime() - timedelta(days=180)
        end_dt = pd.Timestamp(group["exit_date"].max()).to_pydatetime() + timedelta(days=10)
        bars = database.load_bar_data(symbol, exchange, Interval.DAILY, start_dt, end_dt)
        rows: list[dict[str, Any]] = []
        for bar in bars:
            rows.append(
                {
                    "date": pd.Timestamp(bar.datetime).tz_localize(None).normalize(),
                    "open": float(bar.open_price),
                    "high": float(bar.high_price),
                    "low": float(bar.low_price),
                    "close": float(bar.close_price),
                    "volume": float(bar.volume),
                }
            )
        if rows:
            bars_by_symbol[str(vt_symbol)] = (
                pd.DataFrame(rows).drop_duplicates("date").sort_values("date").reset_index(drop=True)
            )
    return bars_by_symbol


def _atr_pct(prior: pd.DataFrame, window: int = 20) -> float:
    if len(prior) < 2:
        return math.nan
    high = prior["high"].astype(float)
    low = prior["low"].astype(float)
    close = prior["close"].astype(float)
    prev_close = close.shift(1)
    true_range = pd.concat([(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    atr = true_range.tail(window).mean()
    last_close = close.iloc[-1]
    if not np.isfinite(atr) or last_close <= 0:
        return math.nan
    return float(atr / last_close * 100.0)


def _directional_return(prior: pd.DataFrame, direction: str, lookback: int) -> float:
    if len(prior) <= lookback:
        return math.nan
    entry_close = float(prior["close"].iloc[-1])
    past_close = float(prior["close"].iloc[-lookback - 1])
    if past_close <= 0:
        return math.nan
    sign = 1.0 if direction == "long" else -1.0
    return float((entry_close / past_close - 1.0) * sign * 100.0)


def _days_since_extreme(prior: pd.DataFrame, direction: str, window: int) -> float:
    if prior.empty:
        return math.nan
    slice_df = prior.tail(window).reset_index(drop=True)
    if slice_df.empty:
        return math.nan
    if direction == "long":
        idx = int(slice_df["high"].astype(float).idxmax())
    else:
        idx = int(slice_df["low"].astype(float).idxmin())
    return float(len(slice_df) - idx - 1)


def _entry_features(row: dict[str, Any], bars: pd.DataFrame | None) -> dict[str, Any]:
    if bars is None or bars.empty:
        return {}
    entry_date = pd.Timestamp(row["entry_date"]).normalize()
    prior = bars[bars["date"] <= entry_date].copy()
    if prior.empty:
        return {}
    direction = str(row["direction"])
    sign = 1.0 if direction == "long" else -1.0
    entry_close = float(prior["close"].iloc[-1])
    atr20_pct = _atr_pct(prior, 20)
    atr_value = entry_close * atr20_pct / 100.0 if np.isfinite(atr20_pct) else math.nan
    recent60 = prior.tail(60)
    if np.isfinite(atr_value) and atr_value > 0 and not recent60.empty:
        if direction == "long":
            extension_60_atr = (entry_close - float(recent60["low"].min())) / atr_value
            pullback_20_atr = (float(prior.tail(20)["high"].max()) - entry_close) / atr_value
        else:
            extension_60_atr = (float(recent60["high"].max()) - entry_close) / atr_value
            pullback_20_atr = (entry_close - float(prior.tail(20)["low"].min())) / atr_value
    else:
        extension_60_atr = math.nan
        pullback_20_atr = math.nan

    close = prior["close"].astype(float)
    ret = close.pct_change().tail(20).dropna()
    vol20_pct = float(ret.std() * math.sqrt(252) * 100.0) if len(ret) >= 5 else math.nan
    ma20 = close.tail(20).mean() if len(close) >= 20 else math.nan
    ma40 = close.tail(40).mean() if len(close) >= 40 else math.nan
    ma60 = close.tail(60).mean() if len(close) >= 60 else math.nan
    return {
        "entry_close": entry_close,
        "atr20_pct": atr20_pct,
        "vol20_annual_pct": vol20_pct,
        "dir_return_20d_pct": _directional_return(prior, direction, 20),
        "dir_return_40d_pct": _directional_return(prior, direction, 40),
        "dir_return_60d_pct": _directional_return(prior, direction, 60),
        "dir_return_120d_pct": _directional_return(prior, direction, 120),
        "extension_60_atr": float(extension_60_atr) if np.isfinite(extension_60_atr) else math.nan,
        "pullback_20_atr": float(pullback_20_atr) if np.isfinite(pullback_20_atr) else math.nan,
        "days_since_extreme_20": _days_since_extreme(prior, direction, 20),
        "days_since_extreme_60": _days_since_extreme(prior, direction, 60),
        "dist_ma20_pct": float((entry_close / ma20 - 1.0) * sign * 100.0) if np.isfinite(ma20) and ma20 > 0 else math.nan,
        "dist_ma40_pct": float((entry_close / ma40 - 1.0) * sign * 100.0) if np.isfinite(ma40) and ma40 > 0 else math.nan,
        "dist_ma60_pct": float((entry_close / ma60 - 1.0) * sign * 100.0) if np.isfinite(ma60) and ma60 > 0 else math.nan,
    }


def _path_features(row: dict[str, Any], bars: pd.DataFrame | None) -> dict[str, Any]:
    if bars is None or bars.empty:
        return {}
    entry_date = pd.Timestamp(row["entry_date"]).normalize()
    exit_date = pd.Timestamp(row["exit_date"]).normalize()
    path = bars[(bars["date"] >= entry_date) & (bars["date"] <= exit_date)].copy()
    if path.empty:
        return {}
    entry_price = float(row["entry_price"])
    if entry_price <= 0:
        return {}
    direction = str(row["direction"])
    if direction == "long":
        favorable = (path["high"].astype(float) / entry_price - 1.0) * 100.0
        adverse = (path["low"].astype(float) / entry_price - 1.0) * 100.0
    else:
        favorable = (entry_price / path["low"].astype(float) - 1.0) * 100.0
        adverse = (entry_price / path["high"].astype(float) - 1.0) * 100.0
    mae_value = float(adverse.min())
    mfe_value = float(favorable.max())
    mae_idx = int(adverse.idxmin()) if not adverse.empty else -1
    mfe_idx = int(favorable.idxmax()) if not favorable.empty else -1
    return {
        "bar_count": int(len(path)),
        "mae_pct": mae_value,
        "mfe_pct": mfe_value,
        "mfe_to_mae_abs_ratio": float(mfe_value / abs(mae_value)) if abs(mae_value) > 1e-9 else math.nan,
        "days_to_mae": int((pd.Timestamp(path.loc[mae_idx, "date"]) - entry_date).days) if mae_idx >= 0 else math.nan,
        "days_to_mfe": int((pd.Timestamp(path.loc[mfe_idx, "date"]) - entry_date).days) if mfe_idx >= 0 else math.nan,
    }


def _merge_candidate_features(round_trips: pd.DataFrame, candidates: pd.DataFrame, risks: pd.DataFrame) -> pd.DataFrame:
    result = round_trips.copy()
    result["entry_date"] = pd.to_datetime(result["entry_date"]).dt.normalize()
    if not candidates.empty:
        c = candidates.copy()
        c["date"] = pd.to_datetime(c["date"]).dt.normalize()
        c["direction_key"] = c["direction"].astype(str).str.lower()
        c = c[pd.to_numeric(c.get("is_opened", 0), errors="coerce").fillna(0).astype(int).eq(1)].copy()
        candidate_columns = [
            "date",
            "contract_vt_symbol",
            "direction_key",
            "entry_context",
            "signal",
            "portfolio_drawdown_pct",
            "active_positions_before",
            "remaining_position_slots",
            "risk_mode",
            "risk_ratio",
            "risk_multiplier",
            "selection_pairwise_score",
            "selection_pairwise_rank",
            "ai_product_pool_score",
            "ai_product_pool_rank",
            "rsi_value",
            "breakout",
            "loss_streak",
            "profit_recovery_streak",
        ]
        c = c[[column for column in candidate_columns if column in c.columns]].copy()
        c.sort_values(["date", "contract_vt_symbol", "direction_key"], inplace=True)
        c = c.drop_duplicates(["date", "contract_vt_symbol", "direction_key"], keep="last")
        result["direction_key"] = result["direction"].astype(str)
        result = result.merge(
            c,
            left_on=["entry_date", "vt_symbol", "direction_key"],
            right_on=["date", "contract_vt_symbol", "direction_key"],
            how="left",
        )
    if not risks.empty:
        r = risks.copy()
        if "datetime" in r.columns:
            r["risk_date"] = pd.to_datetime(r["datetime"]).dt.tz_localize(None).dt.normalize()
        risk_columns = [
            "risk_date",
            "contract_vt_symbol",
            "direction",
            "target_risk",
            "actual_risk",
            "margin_required",
            "available_capital",
            "stop_price",
            "entry_price",
            "planned_entry_price",
            "single_unit_risk",
            "related_exit_reason",
        ]
        r = r[[column for column in risk_columns if column in r.columns]].copy()
        if {"risk_date", "contract_vt_symbol", "direction"}.issubset(r.columns):
            r["direction_key"] = r["direction"].astype(str).str.lower()
            r.sort_values(["risk_date", "contract_vt_symbol", "direction_key"], inplace=True)
            r = r.drop_duplicates(["risk_date", "contract_vt_symbol", "direction_key"], keep="last")
            result = result.merge(
                r.drop(columns=["direction"], errors="ignore"),
                left_on=["entry_date", "vt_symbol", "direction_key"],
                right_on=["risk_date", "contract_vt_symbol", "direction_key"],
                how="left",
                suffixes=("", "_risk"),
            )
    return result


def _enrich_round_trips(
    round_trips: pd.DataFrame,
    bars_by_symbol: dict[str, pd.DataFrame],
    candidates: pd.DataFrame,
    risks: pd.DataFrame,
    drawdown: dict[str, Any],
) -> pd.DataFrame:
    if round_trips.empty:
        return round_trips
    rows: list[dict[str, Any]] = []
    for row in round_trips.to_dict("records"):
        vt_symbol = str(row["vt_symbol"])
        bars = bars_by_symbol.get(vt_symbol)
        enriched = dict(row)
        enriched.update(_entry_features(row, bars))
        enriched.update(_path_features(row, bars))
        rows.append(enriched)
    frame = pd.DataFrame(rows)
    frame = _merge_candidate_features(frame, candidates, risks)
    peak_date = pd.Timestamp(drawdown["peak_date"]).normalize()
    trough_date = pd.Timestamp(drawdown["trough_date"]).normalize()
    frame["overlaps_max_dd_window"] = (
        (pd.to_datetime(frame["entry_date"]) <= trough_date) & (pd.to_datetime(frame["exit_date"]) >= peak_date)
    ).astype(int)
    frame["entry_in_max_dd_window"] = (
        (pd.to_datetime(frame["entry_date"]) > peak_date) & (pd.to_datetime(frame["entry_date"]) <= trough_date)
    ).astype(int)
    return frame


def _bucket_extension(value: Any) -> str:
    value = _safe_float(value, math.nan)
    if pd.isna(value):
        return "unknown"
    if value <= 2.0:
        return "extension_le_2atr"
    if value <= 5.0:
        return "extension_2_5atr"
    if value <= 8.0:
        return "extension_5_8atr"
    return "extension_gt_8atr"


def _bucket_pullback(value: Any) -> str:
    value = _safe_float(value, math.nan)
    if pd.isna(value):
        return "unknown"
    if value <= 0.5:
        return "near_extreme_le_0_5atr"
    if value <= 2.0:
        return "shallow_pullback_0_5_2atr"
    return "deep_pullback_gt_2atr"


def _bucket_vol(value: Any) -> str:
    value = _safe_float(value, math.nan)
    if pd.isna(value):
        return "unknown"
    if value <= 15:
        return "vol_le_15"
    if value <= 30:
        return "vol_15_30"
    if value <= 50:
        return "vol_30_50"
    return "vol_gt_50"


def _bucket_dir_return(value: Any) -> str:
    value = _safe_float(value, math.nan)
    if pd.isna(value):
        return "unknown"
    if value < 0:
        return "prior_against"
    if value <= 8:
        return "prior_mild_0_8"
    if value <= 20:
        return "prior_strong_8_20"
    return "prior_extreme_gt_20"


def _bucket_days(value: Any) -> str:
    value = _safe_float(value, math.nan)
    if pd.isna(value):
        return "unknown"
    if value <= 5:
        return "hold_0_5d"
    if value <= 20:
        return "hold_6_20d"
    if value <= 60:
        return "hold_21_60d"
    return "hold_gt_60d"


def _bucket_mae(value: Any) -> str:
    value = _safe_float(value, math.nan)
    if pd.isna(value):
        return "unknown"
    if value >= -2:
        return "mae_ge_minus2"
    if value >= -5:
        return "mae_minus5_minus2"
    if value >= -10:
        return "mae_minus10_minus5"
    return "mae_lt_minus10"


def _add_buckets(round_trips: pd.DataFrame) -> pd.DataFrame:
    frame = round_trips.copy()
    frame["entry_year"] = pd.to_datetime(frame["entry_date"]).dt.year
    frame["entry_month"] = pd.to_datetime(frame["entry_date"]).dt.month
    frame["holding_bucket"] = frame["holding_days"].map(_bucket_days)
    frame["extension_bucket"] = frame["extension_60_atr"].map(_bucket_extension)
    frame["pullback_bucket"] = frame["pullback_20_atr"].map(_bucket_pullback)
    frame["vol20_bucket"] = frame["vol20_annual_pct"].map(_bucket_vol)
    frame["dir_return60_bucket"] = frame["dir_return_60d_pct"].map(_bucket_dir_return)
    frame["mae_bucket"] = frame["mae_pct"].map(_bucket_mae)
    frame["dd_overlap_bucket"] = np.where(frame["overlaps_max_dd_window"].astype(int).eq(1), "overlap_max_dd", "outside_max_dd")
    frame["rsi_bucket"] = pd.cut(
        pd.to_numeric(frame.get("rsi_value", np.nan), errors="coerce"),
        bins=[-np.inf, 40, 60, 80, 95, np.inf],
        labels=["rsi_le_40", "rsi_40_60", "rsi_60_80", "rsi_80_95", "rsi_gt_95"],
    ).astype(str)
    frame["entry_context"] = frame.get("entry_context", pd.Series("unknown", index=frame.index)).fillna("unknown")
    frame["signal"] = frame.get("signal", pd.Series("unknown", index=frame.index)).fillna("unknown")
    frame["risk_mode"] = frame.get("risk_mode", pd.Series("unknown", index=frame.index)).fillna("unknown")
    frame["exit_reason"] = frame.get("exit_reason", pd.Series("unknown", index=frame.index)).fillna("unknown")
    return frame


def _summarize_group(frame: pd.DataFrame, group_type: str, column: str) -> pd.DataFrame:
    if frame.empty or column not in frame.columns:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for value, group in frame.groupby(column, dropna=False):
        pnl = pd.to_numeric(group["gross_pnl"], errors="coerce").fillna(0.0)
        gross_return = pd.to_numeric(group.get("gross_return_pct", np.nan), errors="coerce")
        mae = pd.to_numeric(group.get("mae_pct", np.nan), errors="coerce")
        mfe = pd.to_numeric(group.get("mfe_pct", np.nan), errors="coerce")
        holding = pd.to_numeric(group.get("holding_days", np.nan), errors="coerce")
        rows.append(
            {
                "group_type": group_type,
                "group_value": "missing" if pd.isna(value) else str(value),
                "sample_count": int(len(group)),
                "total_pnl": float(pnl.sum()),
                "mean_pnl": float(pnl.mean()) if len(group) else 0.0,
                "median_pnl": float(pnl.median()) if len(group) else 0.0,
                "mean_return_pct": float(gross_return.mean()) if gross_return.notna().any() else math.nan,
                "median_return_pct": float(gross_return.median()) if gross_return.notna().any() else math.nan,
                "win_rate_pct": float((pnl > 0).mean() * 100.0) if len(group) else 0.0,
                "median_mae_pct": float(mae.median()) if mae.notna().any() else math.nan,
                "median_mfe_pct": float(mfe.median()) if mfe.notna().any() else math.nan,
                "median_holding_days": float(holding.median()) if holding.notna().any() else math.nan,
                "dd_overlap_count": int(pd.to_numeric(group["overlaps_max_dd_window"], errors="coerce").fillna(0).sum()),
                "dd_entry_count": int(pd.to_numeric(group["entry_in_max_dd_window"], errors="coerce").fillna(0).sum()),
            }
        )
    return pd.DataFrame(rows)


def _build_bucket_summary(round_trips: pd.DataFrame) -> pd.DataFrame:
    group_specs = [
        ("product", "product_vt_symbol"),
        ("direction", "direction"),
        ("entry_year", "entry_year"),
        ("entry_month", "entry_month"),
        ("entry_context", "entry_context"),
        ("signal", "signal"),
        ("risk_mode", "risk_mode"),
        ("exit_reason", "exit_reason"),
        ("holding_bucket", "holding_bucket"),
        ("extension_bucket", "extension_bucket"),
        ("pullback_bucket", "pullback_bucket"),
        ("vol20_bucket", "vol20_bucket"),
        ("dir_return60_bucket", "dir_return60_bucket"),
        ("rsi_bucket", "rsi_bucket"),
        ("mae_bucket", "mae_bucket"),
        ("dd_overlap", "dd_overlap_bucket"),
    ]
    frames = [_summarize_group(round_trips, group_type, column) for group_type, column in group_specs]
    frames = [frame for frame in frames if not frame.empty]
    if not frames:
        return pd.DataFrame()
    summary = pd.concat(frames, ignore_index=True)
    summary["loss_per_trade"] = summary["total_pnl"] / summary["sample_count"].replace(0, np.nan)
    summary.sort_values(["total_pnl", "sample_count"], ascending=[True, False], inplace=True)
    return summary.reset_index(drop=True)


def _dd_window_position_summary(positions: pd.DataFrame, drawdown: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    if positions.empty:
        return pd.DataFrame(), pd.DataFrame()
    frame = positions.copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    frame["product_vt_symbol"] = frame["vt_symbol"].map(_product_from_vt_symbol)
    window = frame[(frame["date"] > drawdown["peak_date"]) & (frame["date"] <= drawdown["trough_date"])].copy()
    if window.empty:
        return pd.DataFrame(), pd.DataFrame()
    for column in ["net_pnl", "holding_pnl", "trading_pnl", "slippage", "turnover", "trade_count", "end_pos"]:
        window[column] = pd.to_numeric(window.get(column, 0.0), errors="coerce").fillna(0.0)
    by_product = (
        window.groupby("product_vt_symbol", as_index=False)
        .agg(
            net_pnl=("net_pnl", "sum"),
            holding_pnl=("holding_pnl", "sum"),
            trading_pnl=("trading_pnl", "sum"),
            slippage=("slippage", "sum"),
            turnover=("turnover", "sum"),
            trade_count=("trade_count", "sum"),
            active_days=("end_pos", lambda values: int((values != 0).sum())),
            max_abs_pos=("end_pos", lambda values: float(values.abs().max())),
        )
        .sort_values("net_pnl")
    )
    by_day = (
        window.groupby("date", as_index=False)
        .agg(net_pnl=("net_pnl", "sum"), holding_pnl=("holding_pnl", "sum"), trading_pnl=("trading_pnl", "sum"), slippage=("slippage", "sum"))
        .sort_values("net_pnl")
    )
    return by_product, by_day


def _build_report(
    statistics: dict[str, Any],
    drawdown: dict[str, Any],
    round_trips: pd.DataFrame,
    bucket_summary: pd.DataFrame,
    dd_product_summary: pd.DataFrame,
    dd_day_summary: pd.DataFrame,
    paths: dict[str, Any],
) -> str:
    baseline_metrics = {
        "end_balance": _safe_float(statistics.get("end_balance")),
        "total_return_pct": _safe_float(statistics.get("total_return")),
        "max_dd_percent": _safe_float(statistics.get("max_ddpercent")),
        "sharpe_ratio": _safe_float(statistics.get("sharpe_ratio")),
        "total_slippage": _safe_float(statistics.get("total_slippage")),
        "total_trade_count": _safe_float(statistics.get("total_trade_count")),
        "win_ratio": _safe_float(statistics.get("win_ratio")),
    }
    worst_buckets = bucket_summary[
        bucket_summary["sample_count"].astype(int).ge(10)
        & ~bucket_summary["group_value"].astype(str).isin({"unknown", "missing", "nan"})
    ].head(20)
    normalized_worst_buckets = (
        bucket_summary[
            bucket_summary["sample_count"].astype(int).ge(10)
            & ~bucket_summary["group_value"].astype(str).isin({"unknown", "missing", "nan"})
        ]
        .sort_values(["median_return_pct", "total_pnl"], ascending=[True, True])
        .head(20)
    )
    top_loss_trades = round_trips.sort_values("gross_pnl").head(20)
    dd_overlap_trades = (
        round_trips[round_trips["overlaps_max_dd_window"].astype(int).eq(1)]
        .sort_values("gross_pnl")
        .head(20)
    )
    lines = [
        "# Stage028 C3单品种路径亏损归因",
        "",
        "## 定位",
        "",
        "- 本阶段是只读归因，不修改 C3，也不新增交易规则。",
        "- Stage027 已反证保证金/持仓广度不是剩余核心回撤来源，本阶段转向单品种单合约路径。",
        "- 外部调研判断：趋势策略降回撤的低过拟合方向通常是波动率缩放、状态/拐点识别、MAE/MFE路径归因；本阶段先做归因，不直接把历史坏桶变成过滤器。",
        "",
        "## C3基准",
        "",
        f"- 期末权益：`{baseline_metrics['end_balance']:,.0f}`",
        f"- 总收益：`{baseline_metrics['total_return_pct']:.4f}%`",
        f"- 最大回撤：`{baseline_metrics['max_dd_percent']:.4f}%`",
        f"- Sharpe：`{baseline_metrics['sharpe_ratio']:.4f}`",
        f"- 总滑点：`{baseline_metrics['total_slippage']:,.0f}`",
        f"- 总交易次数：`{baseline_metrics['total_trade_count']:,.0f}`",
        f"- 胜率：`{baseline_metrics['win_ratio']:.4f}%`",
        "",
        "## 最大回撤窗口",
        "",
        f"- 峰值日：`{pd.Timestamp(drawdown['peak_date']).date()}`，权益 `{drawdown['peak_balance']:,.2f}`。",
        f"- 谷底日：`{pd.Timestamp(drawdown['trough_date']).date()}`，权益 `{drawdown['trough_balance']:,.2f}`。",
        f"- 最大回撤：`{drawdown['max_dd_percent']:.4f}%`。",
        "",
        "## 最大回撤窗口品种贡献",
        "",
        _to_markdown_table(
            dd_product_summary.head(15),
            ["product_vt_symbol", "net_pnl", "holding_pnl", "trading_pnl", "slippage", "trade_count", "active_days", "max_abs_pos"],
            max_rows=15,
        ),
        "",
        "## 最差路径桶（绝对盈亏口径）",
        "",
        _to_markdown_table(
            worst_buckets,
            [
                "group_type",
                "group_value",
                "sample_count",
                "total_pnl",
                "median_return_pct",
                "win_rate_pct",
                "median_mae_pct",
                "median_mfe_pct",
                "dd_overlap_count",
                "loss_per_trade",
            ],
            max_rows=20,
        ),
        "",
        "## 最差路径桶（归一化收益口径）",
        "",
        _to_markdown_table(
            normalized_worst_buckets,
            [
                "group_type",
                "group_value",
                "sample_count",
                "total_pnl",
                "median_return_pct",
                "mean_return_pct",
                "win_rate_pct",
                "median_mae_pct",
                "median_mfe_pct",
                "dd_overlap_count",
            ],
            max_rows=20,
        ),
        "",
        "## 最差持仓回合",
        "",
        _to_markdown_table(
            top_loss_trades,
            [
                "leg_id",
                "product_vt_symbol",
                "vt_symbol",
                "direction",
                "entry_date",
                "exit_date",
                "holding_days",
                "gross_pnl",
                "mae_pct",
                "mfe_pct",
                "extension_bucket",
                "pullback_bucket",
                "dir_return60_bucket",
                "exit_reason",
            ],
            max_rows=20,
        ),
        "",
        "## 最大回撤窗口相关持仓回合",
        "",
        _to_markdown_table(
            dd_overlap_trades,
            [
                "leg_id",
                "product_vt_symbol",
                "vt_symbol",
                "direction",
                "entry_date",
                "exit_date",
                "holding_days",
                "gross_pnl",
                "mae_pct",
                "mfe_pct",
                "extension_bucket",
                "pullback_bucket",
                "dir_return60_bucket",
                "exit_reason",
            ],
            max_rows=20,
        ),
        "",
        "## 最差单日",
        "",
        _to_markdown_table(dd_day_summary.head(15), ["date", "net_pnl", "holding_pnl", "trading_pnl", "slippage"], max_rows=15),
        "",
        "## 判断",
        "",
        "- 本阶段不产生可晋级版本；任何看起来差的桶都必须先经过下一阶段冻结规则、多周期和滑点压力验证。",
        "- 若差桶集中在趋势过度延伸、极近新高/新低、或 MAE 早期快速扩大，下一阶段才考虑低自由度状态覆盖层。",
        "- 若差桶主要是单一年份或单一黑色建材品种贡献，则不做品种黑名单，优先寻找状态解释或独立收益源。",
        "",
        "## 输出",
        "",
        f"- 持仓回合明细：`{paths['round_trips'].name}`",
        f"- 分桶归因：`{paths['bucket_summary'].name}`",
        f"- 回撤窗口品种贡献：`{paths['dd_product_summary'].name}`",
        f"- 决策文件：`{paths['decision'].name}`",
        "",
        "## 反思",
        "",
        "- 是否过拟合：否。本阶段只做已冻结 C3 的路径归因，没有根据结果修改参数。",
        "- 是否还有价值继续：有。它把下一步从大而泛的风险预算，推进到具体可检验的单路径状态变量。",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    metadata = _metadata()
    daily, positions, trades, candidates, risks, statistics = _run_c3()
    if daily.empty:
        raise RuntimeError("C3 daily analysis is empty")
    drawdown = _drawdown_window(daily)
    round_trips = _build_round_trips(trades, metadata)
    bars_by_symbol = _load_bars_for_round_trips(round_trips)
    enriched = _enrich_round_trips(round_trips, bars_by_symbol, candidates, risks, drawdown)
    enriched = _add_buckets(enriched)
    bucket_summary = _build_bucket_summary(enriched)
    dd_product_summary, dd_day_summary = _dd_window_position_summary(positions, drawdown)

    output_paths = {
        "round_trips": OUTPUT_DIR / f"{OUTPUT_PREFIX}_round_trips_{MODEL_TAG}.csv",
        "bucket_summary": OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_summary_{MODEL_TAG}.csv",
        "dd_product_summary": OUTPUT_DIR / f"{OUTPUT_PREFIX}_dd_product_summary_{MODEL_TAG}.csv",
        "dd_day_summary": OUTPUT_DIR / f"{OUTPUT_PREFIX}_dd_day_summary_{MODEL_TAG}.csv",
        "report": OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md",
        "decision": OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json",
    }
    enriched.to_csv(output_paths["round_trips"], index=False, encoding="utf-8-sig")
    bucket_summary.to_csv(output_paths["bucket_summary"], index=False, encoding="utf-8-sig")
    dd_product_summary.to_csv(output_paths["dd_product_summary"], index=False, encoding="utf-8-sig")
    dd_day_summary.to_csv(output_paths["dd_day_summary"], index=False, encoding="utf-8-sig")

    decision = {
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "official_version": OFFICIAL_STAGE78_VERSION,
        "official_role": OFFICIAL_STAGE78_ROLE,
        "baseline": {
            "end_balance": _safe_float(statistics.get("end_balance")),
            "total_return_pct": _safe_float(statistics.get("total_return")),
            "max_dd_percent": _safe_float(statistics.get("max_ddpercent")),
            "sharpe_ratio": _safe_float(statistics.get("sharpe_ratio")),
            "total_slippage": _safe_float(statistics.get("total_slippage")),
            "total_trade_count": int(_safe_float(statistics.get("total_trade_count"))),
            "win_ratio_pct": _safe_float(statistics.get("win_ratio")),
        },
        "drawdown": {key: _to_builtin(value) for key, value in drawdown.items() if key != "curve"},
        "round_trip_count": int(len(enriched)),
        "decision": "diagnostic_only_no_promotion",
        "overfit_judgement": "否。只做冻结C3的路径归因，没有根据结果修改参数。",
        "continue_value_judgement": "有。下一阶段可基于归因结果预注册低自由度状态覆盖层。",
        "outputs": {key: str(value) for key, value in output_paths.items()},
    }
    output_paths["decision"].write_text(json.dumps(decision, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    output_paths["report"].write_text(
        _build_report(statistics, drawdown, enriched, bucket_summary, dd_product_summary, dd_day_summary, output_paths),
        encoding="utf-8",
    )

    print(json.dumps({k: decision[k] for k in ("decision", "round_trip_count", "drawdown")}, ensure_ascii=False, indent=2))
    print(f"[stage328] report: {output_paths['report']}")


if __name__ == "__main__":
    main()
