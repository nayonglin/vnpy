from __future__ import annotations

from collections import deque
from dataclasses import replace
from datetime import datetime, timedelta
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage653_stage526_200k_forced_margin_deleverage as s653
import analyze_qmt_roll_stage660_stage653_multiperiod_live_audit as s660
from qmt_roll_official_live_config import OFFICIAL_LIVE_CAPITAL, OFFICIAL_LIVE_PROFILE_NAME, OFFICIAL_LIVE_VERSION
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy
from run_qmt_alignment_backtest import (
    _match_entry_risk_to_trades,
    build_entry_candidate_snapshots_df,
    build_entry_risk_diagnostics_df,
    build_positions_df,
    build_trades_df,
)


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"
CONTRACT_ROOT = PROJECT_DIR / "downloaded_futures" / "tqsdk_daily_2010_2026_04"

MODEL_TAG = "stage719_official_winner_trade_forensics_v1"
OUTPUT_PREFIX = "qmt_roll_stage719_official_winner_trade_forensics"
LINE_ID = "futures_trend_winner_trade_forensics"

TRADES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trades_{MODEL_TAG}.csv"
ENTRY_RISK_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_risk_{MODEL_TAG}.csv"
ENTRY_CANDIDATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_candidates_{MODEL_TAG}.csv"
TRADE_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_events_{MODEL_TAG}.csv"
POSITIONS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_positions_{MODEL_TAG}.csv"
CLOSED_LOTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_closed_lots_{MODEL_TAG}.csv"
FEATURE_QUALITY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_quality_{MODEL_TAG}.csv"
YEAR_STABILITY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_stability_{MODEL_TAG}.csv"
TOP_WINNERS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_top_winners_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"

BIG_WINNER_QUANTILE = 0.80
MIN_FEATURE_COUNT = 8


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _infer_product(vt_symbol: Any) -> str:
    text = str(vt_symbol or "").split(".", 1)[0]
    product = ""
    for char in text:
        if char.isalpha():
            product += char
        else:
            break
    return product


def _position_direction(direction: Any, offset: Any) -> str | None:
    direction_text = str(direction)
    offset_text = str(offset)
    if offset_text == "Open":
        return "long" if direction_text == "Long" else "short"
    if offset_text == "Close":
        return "long" if direction_text == "Short" else "short"
    return None


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if np.isnan(result) or np.isinf(result):
        return default
    return result


def _bucket_rank(value: Any) -> str:
    rank = _safe_float(value)
    if np.isnan(rank) or rank <= 0:
        return "missing"
    if rank <= 3:
        return "rank_1_3"
    if rank <= 6:
        return "rank_4_6"
    if rank <= 9:
        return "rank_7_9"
    return "rank_gt9"


def _bucket_active_positions(value: Any) -> str:
    count = _safe_float(value)
    if np.isnan(count):
        return "missing"
    if count <= 0:
        return "active_0"
    if count <= 1:
        return "active_1"
    if count <= 2:
        return "active_2"
    if count <= 3:
        return "active_3"
    return "active_ge4"


def _bucket_loss_streak(value: Any) -> str:
    count = _safe_float(value)
    if np.isnan(count):
        return "missing"
    if count <= 0:
        return "loss_streak_0"
    if count <= 2:
        return "loss_streak_1_2"
    return "loss_streak_ge3"


def _bucket_risk_multiplier(value: Any) -> str:
    multiplier = _safe_float(value)
    if np.isnan(multiplier):
        return "missing"
    if multiplier <= 0.100001:
        return "risk_floor_01"
    if multiplier < 0.8:
        return "risk_mid"
    return "risk_normal"


def _bucket_rsi(value: Any, direction: Any) -> str:
    rsi = _safe_float(value)
    if np.isnan(rsi):
        return "missing"
    side = str(direction)
    if side == "long":
        if rsi < 50:
            return "long_rsi_lt50"
        if rsi < 60:
            return "long_rsi_50_60"
        if rsi < 70:
            return "long_rsi_60_70"
        return "long_rsi_ge70"
    if rsi > 50:
        return "short_rsi_gt50"
    if rsi > 40:
        return "short_rsi_40_50"
    if rsi > 30:
        return "short_rsi_30_40"
    return "short_rsi_le30"


def _bucket_stop_distance_pct(value: Any) -> str:
    pct = _safe_float(value)
    if np.isnan(pct):
        return "missing"
    if pct <= 0.01:
        return "stop_le1pct"
    if pct <= 0.02:
        return "stop_1_2pct"
    if pct <= 0.04:
        return "stop_2_4pct"
    return "stop_gt4pct"


def _read_contract_bars(vt_symbol: Any) -> pd.DataFrame:
    text = str(vt_symbol or "")
    if "." not in text:
        return pd.DataFrame()
    contract_symbol, exchange = text.split(".", 1)
    path = CONTRACT_ROOT / exchange / f"{contract_symbol}.csv"
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(path, encoding="utf-8-sig")
    if frame.empty:
        return pd.DataFrame()
    if "trade_date" in frame.columns:
        frame["date"] = pd.to_datetime(frame["trade_date"], errors="coerce").dt.normalize()
    else:
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    rename = {
        "open_price": "open",
        "high_price": "high",
        "low_price": "low",
        "close_price": "close",
    }
    frame.rename(columns={k: v for k, v in rename.items() if k in frame.columns}, inplace=True)
    for column in ["open", "high", "low", "close"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.dropna(subset=["date", "high", "low", "close"]).drop_duplicates("date").sort_values("date")


def _run_official_engine() -> tuple[Any, s653.ForcedVariant, dict[str, Any]]:
    metadata = s513._metadata()
    spec = s660._official_spec(metadata)

    s653.s517.assert_stage196_database_sentinels()
    s653.s517.s506._patch_stage506_raw_roots()
    c3_overrides = s513._c3_overrides(s653.s517.START_DT)
    preload_start = max(s653.s517.PRELOAD_START_DT, s653.s517.START_DT - timedelta(days=365))
    _, open_map = s653.s517.s506.s501._seed_proxy_maps()
    engine = s653.s517.s506.s502.ConfirmedDailyNextRealOpenEngine(open_map)
    engine.output = lambda msg: None
    engine.set_parameters(
        vt_symbols=metadata["vt_symbols"],
        interval=s653.s517.Interval.DAILY,
        start=preload_start,
        end=s653.s517.END_DT,
        rates=metadata["rates"],
        slippages=metadata["slippages"],
        sizes=metadata["sizes"],
        priceticks=metadata["priceticks"],
        capital=spec.capital.c3_capital,
    )
    setting = s653.s517.build_roll_setting(
        metadata["margin_ratios"],
        risk_ratio=s653.s517.BASE_RISK_RATIO * float(spec.capital.risk_multiplier),
        strategy_overrides=c3_overrides,
    )
    setting["capital_base"] = spec.capital.c3_capital
    setting.update(spec.overrides)
    engine.add_strategy(QmtRollPortfolioStrategy, setting)
    engine.load_data()
    engine.run_backtesting()
    engine.calculate_result()
    return engine, replace(spec), metadata


def _extract_raw_frames(engine: Any, spec: s653.ForcedVariant) -> dict[str, pd.DataFrame]:
    strategy = getattr(engine, "strategy", None)
    frames = {
        "trades": build_trades_df(engine),
        "positions": build_positions_df(engine),
        "entry_risk": build_entry_risk_diagnostics_df(engine),
        "entry_candidates": build_entry_candidate_snapshots_df(engine),
        "trade_events": pd.DataFrame(getattr(strategy, "trade_event_diagnostics", []) if strategy else []),
    }
    for name, frame in frames.items():
        if frame.empty:
            continue
        frame["variant"] = spec.capital.variant
        frame["official_live_version"] = OFFICIAL_LIVE_VERSION
    return frames


def _candidate_match_frame(entry_candidates: pd.DataFrame) -> pd.DataFrame:
    if entry_candidates.empty:
        return pd.DataFrame()
    opened = entry_candidates[entry_candidates["candidate_status"].astype(str).eq("opened")].copy()
    if opened.empty:
        return pd.DataFrame()
    opened["volume"] = pd.to_numeric(opened.get("selected_volume", 0), errors="coerce").fillna(0.0)
    if "entry_index" not in opened.columns:
        opened["entry_index"] = opened.get("candidate_index", range(1, len(opened) + 1))
    return opened


def _first_available(primary: dict[str, Any], secondary: dict[str, Any], key: str, default: Any = "") -> Any:
    value = primary.get(key)
    if value is None or (isinstance(value, float) and np.isnan(value)) or value == "":
        value = secondary.get(key)
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return default
    return value


def _build_closed_lots(
    trades: pd.DataFrame,
    entry_risk: pd.DataFrame,
    entry_candidates: pd.DataFrame,
    metadata: dict[str, Any],
) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()

    data = trades.copy()
    data["datetime"] = pd.to_datetime(data["datetime"], errors="coerce")
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    data.sort_values(["datetime", "vt_symbol", "trade_id"], inplace=True)
    risk_by_open_id = _match_entry_risk_to_trades(data, entry_risk) if not entry_risk.empty else {}
    candidate_match = _candidate_match_frame(entry_candidates)
    candidate_by_open_id = (
        _match_entry_risk_to_trades(data, candidate_match) if not candidate_match.empty else {}
    )

    open_queues: dict[tuple[str, str], deque[dict[str, Any]]] = {}
    rows: list[dict[str, Any]] = []

    for trade in data.to_dict("records"):
        pos_direction = _position_direction(trade.get("direction"), trade.get("offset"))
        if pos_direction is None:
            continue
        vt_symbol = str(trade["vt_symbol"])
        key = (vt_symbol, pos_direction)
        volume = float(trade.get("volume") or 0.0)
        if volume <= 0:
            continue

        if str(trade.get("offset")) == "Open":
            risk_row = risk_by_open_id.get(str(trade.get("trade_id")), {})
            candidate_row = candidate_by_open_id.get(str(trade.get("trade_id")), {})
            size = int(_safe_float(risk_row.get("size"), metadata["sizes"].get(vt_symbol, 1)))
            stop_price = _safe_float(risk_row.get("stop_price"))
            risk_per_contract = _safe_float(risk_row.get("risk_per_contract"))
            if np.isnan(risk_per_contract) and not np.isnan(stop_price):
                risk_per_contract = max(abs(float(trade["price"]) - stop_price) * size, 1.0)
            open_queues.setdefault(key, deque()).append(
                {
                    "open_trade": trade,
                    "remaining_volume": volume,
                    "risk_row": risk_row,
                    "candidate_row": candidate_row,
                    "size": size,
                    "risk_per_contract": risk_per_contract,
                }
            )
            continue

        queue = open_queues.get(key, deque())
        remaining = volume
        while remaining > 1e-8 and queue:
            item = queue[0]
            matched_volume = min(float(item["remaining_volume"]), remaining)
            open_trade = item["open_trade"]
            risk_row = item["risk_row"]
            candidate_row = item.get("candidate_row", {})
            size = int(item["size"])
            entry_price = float(open_trade["price"])
            exit_price = float(trade["price"])
            realized = (
                (exit_price - entry_price) * size * matched_volume
                if pos_direction == "long"
                else (entry_price - exit_price) * size * matched_volume
            )
            risk_per_contract = _safe_float(item.get("risk_per_contract"))
            risk_amount = risk_per_contract * matched_volume if not np.isnan(risk_per_contract) else np.nan
            entry_date = pd.Timestamp(open_trade["date"]).normalize()
            exit_date = pd.Timestamp(trade["date"]).normalize()
            bars = _read_contract_bars(vt_symbol)
            path_metrics = _path_metrics(
                bars,
                direction=pos_direction,
                entry_date=entry_date,
                exit_date=exit_date,
                entry_price=entry_price,
                size=size,
                volume=matched_volume,
                risk_amount=risk_amount,
            )
            entry_risk_distance_pct = (
                abs(entry_price - _safe_float(risk_row.get("stop_price"))) / entry_price
                if entry_price > 0 and not np.isnan(_safe_float(risk_row.get("stop_price")))
                else np.nan
            )
            row = {
                "lot_id": len(rows) + 1,
                "open_trade_id": open_trade.get("trade_id"),
                "close_trade_id": trade.get("trade_id"),
                "vt_symbol": vt_symbol,
                "product": str(risk_row.get("product_vt_symbol") or _infer_product(vt_symbol)),
                "direction": pos_direction,
                "entry_date": entry_date,
                "exit_date": exit_date,
                "holding_calendar_days": int((exit_date - entry_date).days),
                "entry_price": entry_price,
                "exit_price": exit_price,
                "volume": matched_volume,
                "size": size,
                "realized_pnl": realized,
                "risk_amount": risk_amount,
                "r_multiple": realized / risk_amount if risk_amount and not np.isnan(risk_amount) else np.nan,
                "exit_reason": trade.get("exit_reason"),
                "signal": _first_available(risk_row, candidate_row, "signal"),
                "risk_mode": _first_available(risk_row, candidate_row, "risk_mode"),
                "entry_context": _first_available(risk_row, candidate_row, "entry_context"),
                "layer_kind": _first_available(risk_row, candidate_row, "layer_kind"),
                "risk_multiplier": _safe_float(_first_available(risk_row, candidate_row, "risk_multiplier", np.nan)),
                "loss_streak": _safe_float(_first_available(risk_row, candidate_row, "loss_streak", np.nan)),
                "active_positions_before": _safe_float(
                    _first_available(risk_row, candidate_row, "active_positions_before", np.nan)
                ),
                "ai_product_pool_allowed": _safe_float(
                    _first_available(risk_row, candidate_row, "ai_product_pool_allowed", np.nan)
                ),
                "ai_product_pool_rank": _safe_float(
                    _first_available(risk_row, candidate_row, "ai_product_pool_rank", np.nan)
                ),
                "ai_product_pool_score": _safe_float(
                    _first_available(risk_row, candidate_row, "ai_product_pool_score", np.nan)
                ),
                "rsi_value": _safe_float(_first_available(risk_row, candidate_row, "rsi_value", np.nan)),
                "breakout": _safe_float(_first_available(risk_row, candidate_row, "breakout", np.nan)),
                "bullish_alignment": _safe_float(
                    _first_available(risk_row, candidate_row, "bullish_alignment", np.nan)
                ),
                "bearish_alignment": _safe_float(
                    _first_available(risk_row, candidate_row, "bearish_alignment", np.nan)
                ),
                "portfolio_drawdown_pct": _safe_float(
                    _first_available(risk_row, candidate_row, "portfolio_drawdown_pct", np.nan)
                ),
                "same_direction_correlation_max_corr": _safe_float(
                    _first_available(risk_row, candidate_row, "same_direction_correlation_max_corr", np.nan)
                ),
                "same_direction_correlation_active_count": _safe_float(
                    _first_available(risk_row, candidate_row, "same_direction_correlation_active_count", np.nan)
                ),
                "streak_entry_structure_risk_recovery_applied": _safe_float(
                    _first_available(
                        risk_row,
                        candidate_row,
                        "streak_entry_structure_risk_recovery_applied",
                        np.nan,
                    )
                ),
                "recovery_sleeve_applied": _safe_float(
                    _first_available(risk_row, candidate_row, "recovery_sleeve_applied", np.nan)
                ),
                "target_risk_amount": _safe_float(
                    _first_available(risk_row, candidate_row, "target_risk_amount", np.nan)
                ),
                "selected_volume": _safe_float(_first_available(risk_row, candidate_row, "selected_volume", np.nan)),
                "contracts_by_risk": _safe_float(
                    _first_available(risk_row, candidate_row, "contracts_by_risk", np.nan)
                ),
                "contracts_by_margin": _safe_float(
                    _first_available(risk_row, candidate_row, "contracts_by_margin", np.nan)
                ),
                "stop_distance": _safe_float(_first_available(risk_row, candidate_row, "stop_distance", np.nan)),
                "entry_risk_distance_pct": entry_risk_distance_pct,
            }
            row.update(path_metrics)
            rows.append(row)

            item["remaining_volume"] = float(item["remaining_volume"]) - matched_volume
            remaining -= matched_volume
            if float(item["remaining_volume"]) <= 1e-8:
                queue.popleft()

    result = pd.DataFrame(rows)
    if result.empty:
        return result
    result["entry_year"] = pd.to_datetime(result["entry_date"]).dt.year
    result["winner"] = result["realized_pnl"].gt(0.0).astype(int)
    positive_r = result.loc[result["r_multiple"].gt(0.0), "r_multiple"].dropna()
    big_threshold = float(positive_r.quantile(BIG_WINNER_QUANTILE)) if len(positive_r) else np.nan
    result["big_winner_threshold_r"] = big_threshold
    result["big_winner"] = (
        result["r_multiple"].ge(big_threshold).fillna(False).astype(int) if not np.isnan(big_threshold) else 0
    )
    result["risk_multiplier_bucket"] = result["risk_multiplier"].map(_bucket_risk_multiplier)
    result["loss_streak_bucket"] = result["loss_streak"].map(_bucket_loss_streak)
    result["active_positions_bucket"] = result["active_positions_before"].map(_bucket_active_positions)
    result["ai_rank_bucket"] = result["ai_product_pool_rank"].map(_bucket_rank)
    result["rsi_bucket"] = [
        _bucket_rsi(value, direction)
        for value, direction in zip(result["rsi_value"], result["direction"], strict=False)
    ]
    result["stop_distance_bucket"] = result["entry_risk_distance_pct"].map(_bucket_stop_distance_pct)
    result["recovery_bucket"] = np.where(result["recovery_sleeve_applied"].fillna(0).gt(0), "recovery", "non_recovery")
    result["streak_recovery_bucket"] = np.where(
        result["streak_entry_structure_risk_recovery_applied"].fillna(0).gt(0),
        "streak_recovery",
        "non_streak_recovery",
    )
    result["breakout_bucket"] = np.where(result["breakout"].fillna(0).gt(0), "breakout", "no_breakout")
    return result.sort_values(["entry_date", "lot_id"]).reset_index(drop=True)


def _path_metrics(
    bars: pd.DataFrame,
    *,
    direction: str,
    entry_date: pd.Timestamp,
    exit_date: pd.Timestamp,
    entry_price: float,
    size: int,
    volume: float,
    risk_amount: float,
) -> dict[str, Any]:
    empty = {
        "path_bar_count": 0,
        "mfe_cash": np.nan,
        "mae_cash": np.nan,
        "mfe_r": np.nan,
        "mae_r": np.nan,
        "exit_efficiency": np.nan,
        "days_to_mfe": np.nan,
        "days_to_mae": np.nan,
    }
    if bars.empty or entry_price <= 0:
        return empty
    window = bars[(bars["date"] >= entry_date) & (bars["date"] <= exit_date)].copy()
    if window.empty:
        return empty
    if direction == "long":
        favorable = (window["high"] - entry_price) * size * volume
        adverse = (entry_price - window["low"]) * size * volume
    else:
        favorable = (entry_price - window["low"]) * size * volume
        adverse = (window["high"] - entry_price) * size * volume
    mfe_cash = float(favorable.max())
    mae_cash = float(adverse.max())
    mfe_idx = int(favorable.idxmax()) if favorable.notna().any() else None
    mae_idx = int(adverse.idxmax()) if adverse.notna().any() else None
    days_to_mfe = (
        int((pd.Timestamp(window.loc[mfe_idx, "date"]) - entry_date).days)
        if mfe_idx is not None
        else np.nan
    )
    days_to_mae = (
        int((pd.Timestamp(window.loc[mae_idx, "date"]) - entry_date).days)
        if mae_idx is not None
        else np.nan
    )
    return {
        "path_bar_count": int(len(window)),
        "mfe_cash": mfe_cash,
        "mae_cash": mae_cash,
        "mfe_r": mfe_cash / risk_amount if risk_amount and not np.isnan(risk_amount) else np.nan,
        "mae_r": mae_cash / risk_amount if risk_amount and not np.isnan(risk_amount) else np.nan,
        "exit_efficiency": np.nan,
        "days_to_mfe": days_to_mfe,
        "days_to_mae": days_to_mae,
    }


def _finalize_path_efficiency(closed: pd.DataFrame) -> pd.DataFrame:
    if closed.empty:
        return closed
    data = closed.copy()
    data["exit_efficiency"] = np.where(
        data["mfe_cash"].gt(0),
        data["realized_pnl"].clip(lower=0) / data["mfe_cash"],
        np.nan,
    )
    data["quality_winner"] = (
        data["winner"].eq(1)
        & data["mfe_r"].ge(2.0)
        & data["mae_r"].le(1.2)
        & data["exit_efficiency"].ge(0.35)
    ).astype(int)
    return data


FEATURE_COLUMNS = (
    "direction",
    "signal",
    "risk_mode",
    "entry_context",
    "risk_multiplier_bucket",
    "loss_streak_bucket",
    "active_positions_bucket",
    "ai_rank_bucket",
    "rsi_bucket",
    "stop_distance_bucket",
    "recovery_bucket",
    "streak_recovery_bucket",
    "breakout_bucket",
)


def _feature_quality(closed: pd.DataFrame) -> pd.DataFrame:
    if closed.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    base_win = float(closed["winner"].mean())
    base_big = float(closed["big_winner"].mean())
    base_avg_r = float(closed["r_multiple"].mean())

    for feature in FEATURE_COLUMNS:
        if feature not in closed.columns:
            continue
        for value, group in closed.groupby(feature, dropna=False):
            count = int(len(group))
            if count < MIN_FEATURE_COUNT:
                continue
            yearly = group.groupby("entry_year")["r_multiple"].sum()
            years_count = int(yearly.count())
            years_positive = int(yearly.gt(0.0).sum())
            win_rate = float(group["winner"].mean())
            big_rate = float(group["big_winner"].mean())
            avg_r = float(group["r_multiple"].mean())
            quality_rate = float(group["quality_winner"].mean())
            score = (big_rate - base_big) + 0.5 * (win_rate - base_win) + 0.15 * (avg_r - base_avg_r)
            rows.append(
                {
                    "feature": feature,
                    "feature_value": str(value),
                    "count": count,
                    "win_rate_pct": win_rate * 100.0,
                    "big_winner_rate_pct": big_rate * 100.0,
                    "quality_winner_rate_pct": quality_rate * 100.0,
                    "avg_r": avg_r,
                    "median_r": float(group["r_multiple"].median()),
                    "total_r": float(group["r_multiple"].sum()),
                    "total_pnl": float(group["realized_pnl"].sum()),
                    "median_mfe_r": float(group["mfe_r"].median()),
                    "median_mae_r": float(group["mae_r"].median()),
                    "median_exit_efficiency": float(group["exit_efficiency"].median()),
                    "years_count": years_count,
                    "years_positive": years_positive,
                    "years_positive_rate_pct": (years_positive / years_count * 100.0) if years_count else 0.0,
                    "diagnostic_score": score,
                }
            )
    result = pd.DataFrame(rows)
    if result.empty:
        return result
    return result.sort_values(["diagnostic_score", "count"], ascending=[False, False]).reset_index(drop=True)


def _year_stability(closed: pd.DataFrame) -> pd.DataFrame:
    if closed.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    group_cols = ["entry_year", "direction"]
    for keys, group in closed.groupby(group_cols):
        year, direction = keys
        rows.append(
            {
                "entry_year": int(year),
                "direction": direction,
                "count": int(len(group)),
                "win_rate_pct": float(group["winner"].mean() * 100.0),
                "big_winner_count": int(group["big_winner"].sum()),
                "avg_r": float(group["r_multiple"].mean()),
                "total_r": float(group["r_multiple"].sum()),
                "total_pnl": float(group["realized_pnl"].sum()),
                "median_mfe_r": float(group["mfe_r"].median()),
                "median_mae_r": float(group["mae_r"].median()),
            }
        )
    return pd.DataFrame(rows).sort_values(["entry_year", "direction"]).reset_index(drop=True)


def _summary(closed: pd.DataFrame, trades: pd.DataFrame, entry_risk: pd.DataFrame, candidates: pd.DataFrame) -> pd.DataFrame:
    if closed.empty:
        return pd.DataFrame(
            [
                {
                    "metric": "closed_lot_count",
                    "value": 0,
                }
            ]
        )
    rows = [
        ("closed_lot_count", len(closed)),
        ("trade_count_raw", len(trades)),
        ("entry_risk_count", len(entry_risk)),
        ("entry_candidate_count", len(candidates)),
        ("winner_count", int(closed["winner"].sum())),
        ("winner_rate_pct", float(closed["winner"].mean() * 100.0)),
        ("big_winner_count", int(closed["big_winner"].sum())),
        ("big_winner_threshold_r", float(closed["big_winner_threshold_r"].dropna().iloc[0])),
        ("quality_winner_count", int(closed["quality_winner"].sum())),
        ("total_realized_pnl", float(closed["realized_pnl"].sum())),
        ("avg_r", float(closed["r_multiple"].mean())),
        ("median_r", float(closed["r_multiple"].median())),
        ("p90_r", float(closed["r_multiple"].quantile(0.90))),
        ("p10_r", float(closed["r_multiple"].quantile(0.10))),
        ("median_mfe_r", float(closed["mfe_r"].median())),
        ("median_mae_r", float(closed["mae_r"].median())),
        ("median_exit_efficiency", float(closed["exit_efficiency"].median())),
    ]
    return pd.DataFrame([{"metric": key, "value": value} for key, value in rows])


def _plot(closed: pd.DataFrame, feature_quality: pd.DataFrame) -> None:
    if closed.empty:
        return
    fig, axes = plt.subplots(2, 2, figsize=(15, 10), dpi=160)
    ax_r, ax_scatter, ax_feature, ax_year = axes.flatten()

    clipped_r = closed["r_multiple"].clip(lower=-5, upper=10)
    ax_r.hist(clipped_r.dropna(), bins=40, color="#2563eb", alpha=0.75)
    ax_r.axvline(0.0, color="#111827", linewidth=0.8)
    ax_r.set_title("Closed lots R distribution (clipped -5R..10R)")
    ax_r.grid(alpha=0.25)

    colors = np.where(closed["big_winner"].eq(1), "#dc2626", np.where(closed["winner"].eq(1), "#16a34a", "#64748b"))
    ax_scatter.scatter(closed["mae_r"], closed["mfe_r"], c=colors, alpha=0.75, s=28)
    ax_scatter.set_xlabel("MAE R")
    ax_scatter.set_ylabel("MFE R")
    ax_scatter.set_title("Path quality: MFE vs MAE")
    ax_scatter.grid(alpha=0.25)

    top = feature_quality.head(12).iloc[::-1] if not feature_quality.empty else pd.DataFrame()
    if not top.empty:
        labels = top["feature"].astype(str) + "=" + top["feature_value"].astype(str)
        ax_feature.barh(labels, top["diagnostic_score"], color="#f97316", alpha=0.8)
        ax_feature.set_title("Top diagnostic feature buckets")
    ax_feature.grid(axis="x", alpha=0.25)

    yearly = closed.groupby("entry_year")["realized_pnl"].sum()
    ax_year.bar(yearly.index.astype(str), yearly.values, color="#059669")
    ax_year.axhline(0.0, color="#111827", linewidth=0.8)
    ax_year.set_title("Closed-lot realized PnL by entry year")
    ax_year.tick_params(axis="x", rotation=30)
    ax_year.grid(axis="y", alpha=0.25)

    fig.suptitle("Stage719 Official Winner Trade Forensics", fontsize=14)
    fig.tight_layout()
    fig.savefig(CHART_PATH)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    closed: pd.DataFrame,
    feature_quality: pd.DataFrame,
    year_stability: pd.DataFrame,
    top_winners: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    lines = [
        "# Stage719 Official Winner Trade Forensics",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        f"- 当前 official live：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_PROFILE_NAME}`",
        "- 本阶段只读复盘，不修改正式配置、不连接 CTP、不调用下单。",
        "- 逐笔口径：真实成交 FIFO 配对成 closed lots，再合并入场 risk diagnostic；若部分成交/换月跨层，首版仍可能有近似误差。",
        "- 过拟合约束：本报告只列观察特征，不把 winner 共同点直接交易化。",
        "",
        "## Summary",
        "",
        _md_table(summary, max_rows=50),
        "",
        "## Top Diagnostic Feature Buckets",
        "",
        _md_table(feature_quality.head(30), max_rows=30),
        "",
        "## Year Direction Stability",
        "",
        _md_table(year_stability, max_rows=40),
        "",
        "## Top Winners",
        "",
        _md_table(top_winners, max_rows=30),
        "",
        "## Decision",
        "",
        f"- 决策：`{decision['decision']}`。",
        f"- 主要判断：{decision['judgement']}",
        f"- 下一步：{decision['next_step']}",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    engine, spec, metadata = _run_official_engine()
    frames = _extract_raw_frames(engine, spec)
    trades = frames["trades"]
    entry_risk = frames["entry_risk"]
    candidates = frames["entry_candidates"]
    positions = frames["positions"]
    events = frames["trade_events"]

    closed = _build_closed_lots(trades, entry_risk, candidates, metadata)
    closed = _finalize_path_efficiency(closed)
    feature_quality = _feature_quality(closed)
    year_stability = _year_stability(closed)
    summary = _summary(closed, trades, entry_risk, candidates)
    top_winners = (
        closed.sort_values("r_multiple", ascending=False)
        .head(30)[
            [
                "lot_id",
                "product",
                "vt_symbol",
                "direction",
                "entry_date",
                "exit_date",
                "holding_calendar_days",
                "realized_pnl",
                "r_multiple",
                "mfe_r",
                "mae_r",
                "exit_efficiency",
                "signal",
                "risk_multiplier_bucket",
                "loss_streak_bucket",
                "ai_rank_bucket",
                "exit_reason",
            ]
        ]
        if not closed.empty
        else pd.DataFrame()
    )

    for frame, path in [
        (trades, TRADES_PATH),
        (entry_risk, ENTRY_RISK_PATH),
        (candidates, ENTRY_CANDIDATES_PATH),
        (events, TRADE_EVENTS_PATH),
        (positions, POSITIONS_PATH),
        (closed, CLOSED_LOTS_PATH),
        (feature_quality, FEATURE_QUALITY_PATH),
        (year_stability, YEAR_STABILITY_PATH),
        (top_winners, TOP_WINNERS_PATH),
        (summary, SUMMARY_PATH),
    ]:
        frame.to_csv(path, index=False, encoding="utf-8-sig")

    _plot(closed, feature_quality)

    decision = {
        "stage": "Stage001",
        "script_stage": "Stage719",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_profile": OFFICIAL_LIVE_PROFILE_NAME,
        "capital": OFFICIAL_LIVE_CAPITAL,
        "decision": "winner_forensics_readonly_first_pass_no_promotion",
        "judgement": (
            "首版只读法证表可用于观察赢家特征，但所有特征仍是事后归因；不得直接转成交易规则。"
        ),
        "next_step": (
            "检查 top feature 是否跨年份、跨方向、跨品种稳定；若稳定，再做预声明 walk-forward selector。"
        ),
        "outputs": {
            "trades": str(TRADES_PATH),
            "entry_risk": str(ENTRY_RISK_PATH),
            "entry_candidates": str(ENTRY_CANDIDATES_PATH),
            "trade_events": str(TRADE_EVENTS_PATH),
            "positions": str(POSITIONS_PATH),
            "closed_lots": str(CLOSED_LOTS_PATH),
            "feature_quality": str(FEATURE_QUALITY_PATH),
            "year_stability": str(YEAR_STABILITY_PATH),
            "top_winners": str(TOP_WINNERS_PATH),
            "summary": str(SUMMARY_PATH),
            "report": str(REPORT_PATH),
            "chart": str(CHART_PATH),
        },
    }
    _write_report(summary, closed, feature_quality, year_stability, top_winners, decision)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print(f"chart={CHART_PATH}")


if __name__ == "__main__":
    main()
