from __future__ import annotations

from dataclasses import replace
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

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage719_official_winner_trade_forensics as s719
import analyze_qmt_roll_stage752_theoretical_winner_kline_atlas as s752
import analyze_qmt_roll_stage757_c50_oi_confirm_risk_restore as s757
import analyze_qmt_roll_stage778_stage777_2022_drawdown_forensics as s778
import analyze_qmt_roll_stage804_stage777_long_tighter_initial_stop_yearly as s804
import analyze_qmt_roll_stage813_stage804_rsi_partial_exit_ablation_yearly as s813
import qmt_roll_official_candidate_stage819_30w_config as stage819_cfg


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage825_stage819_intraday_rule_forensics_v1"
OUTPUT_PREFIX = "qmt_roll_stage825_stage819_intraday_rule_forensics"
LINE_ID = "futures_trend_stage819_intraday_rules"

START = pd.Timestamp("2018-01-01")
END = pd.Timestamp("2026-05-29")
CAPITAL = stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_CAPITAL
VARIANT = "stage825_stage819_30w_intraday_rule_forensics_2018"

MINUTE_SOURCE_PATHS = (
    OUTPUT_DIR / "qmt_roll_stage449_minute_session_rebuild_full_minute_bars_stage449_minute_session_rebuild_full_v1.csv",
    OUTPUT_DIR / "qmt_roll_stage498_actual_trade_fill_key_readiness_completed_minute_bars_stage498_actual_trade_fill_key_readiness_v1.csv",
)

PER_PAGE = 4
MAX_ATLAS_PAGES = int(0)  # 0 means all pages.
OPENING_RANGE_BARS = 15
FAST_WINDOWS = (15, 30, 60, 120)
RISK_R_MULTIPLES = (0.5, 1.0, 2.0)

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CURVE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curve_{MODEL_TAG}.csv"
TRADES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trades_{MODEL_TAG}.csv"
ENTRY_RISK_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_risk_{MODEL_TAG}.csv"
ENTRY_CANDIDATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_candidates_{MODEL_TAG}.csv"
TRADE_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_trade_events_{MODEL_TAG}.csv"
CLOSED_LOTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_closed_lots_{MODEL_TAG}.csv"
INTRADAY_FEATURES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_intraday_features_{MODEL_TAG}.csv"
BUCKET_STATS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_stats_{MODEL_TAG}.csv"
RULE_CANDIDATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rule_candidates_{MODEL_TAG}.csv"
COVERAGE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_minute_coverage_{MODEL_TAG}.csv"
ATLAS_MANIFEST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
CHART_PATH_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_page{{page:03d}}_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or np.isinf(result):
        return default
    return result


def _profile(metadata: dict[str, Any]) -> dict[str, Any]:
    profile = s813._profile(metadata, START, enabled=True)
    spec = profile["spec"]
    overrides = stage819_cfg.build_official_candidate_stage819_30w_overrides()
    capital = replace(
        spec.capital,
        variant=VARIANT,
        label="Stage825 Stage819 30w intraday rule forensics 2018 start",
        account_capital=CAPITAL,
        c3_capital=CAPITAL,
        note=(
            f"{spec.capital.note} | Stage825 read-only intraday forensics. "
            f"source={stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION}."
        ),
    )
    profile = dict(profile)
    profile["profile"] = "stage825_stage819_30w_intraday_rule_forensics"
    profile["spec"] = replace(
        spec,
        capital=capital,
        overrides={**spec.overrides, **overrides},
        profile=profile["profile"],
    )
    profile["note"] = "Stage819 official candidate full-period replay for intraday rule forensics."
    return profile


def _run_full() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame], pd.DataFrame]:
    metadata = s513._metadata()
    profile = _profile(metadata)
    base_c3_overrides = dict(s513._c3_overrides(pd.Timestamp("2018-01-01").to_pydatetime()))
    combined, frames = s778._run_profile(
        profile=profile,
        start=START,
        metadata=metadata,
        base_c3_overrides=base_c3_overrides,
    )
    summary, curve = s804._metric_from_combined(profile, combined, START)
    trades = frames.get("trades", pd.DataFrame()).copy()
    entry_risk = frames.get("entry_risk", pd.DataFrame()).copy()
    entry_candidates = frames.get("entry_candidates", pd.DataFrame()).copy()
    closed = s719._build_closed_lots(trades, entry_risk, entry_candidates, metadata)
    if closed.empty:
        raise RuntimeError("Stage819 closed lots are empty")
    closed = s757._add_lot_features(closed, trades, entry_risk)
    for column in ("entry_date", "exit_date"):
        closed[column] = pd.to_datetime(closed[column], errors="coerce").dt.normalize()
    closed = closed[
        closed["entry_date"].ge(START.normalize())
        & closed["exit_date"].le(END.normalize())
    ].copy()
    return summary, curve, frames, closed.reset_index(drop=True)


def _load_minute_bars(vt_symbols: set[str]) -> pd.DataFrame:
    usecols = [
        "vt_symbol",
        "bar_datetime",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "open_oi",
        "close_oi",
    ]
    frames: list[pd.DataFrame] = []
    for path in MINUTE_SOURCE_PATHS:
        if not path.exists():
            continue
        frame = pd.read_csv(path, usecols=lambda col: col in usecols, encoding="utf-8-sig")
        if frame.empty or "vt_symbol" not in frame.columns:
            continue
        frame = frame[frame["vt_symbol"].astype(str).isin(vt_symbols)].copy()
        if frame.empty:
            continue
        frame["bar_datetime"] = pd.to_datetime(frame["bar_datetime"], errors="coerce")
        frame["minute_source"] = path.name
        frames.append(frame)
    if not frames:
        return pd.DataFrame(columns=usecols + ["bar_date", "minute_source"])
    data = pd.concat(frames, ignore_index=True, sort=False)
    for column in ["open", "high", "low", "close", "volume", "open_oi", "close_oi"]:
        data[column] = pd.to_numeric(data.get(column), errors="coerce")
    data["bar_date"] = data["bar_datetime"].dt.normalize()
    data = data.dropna(subset=["vt_symbol", "bar_datetime", "open", "high", "low", "close"])
    data = data.drop_duplicates(["vt_symbol", "bar_datetime"]).sort_values(["vt_symbol", "bar_datetime"])
    return data.reset_index(drop=True)


def _minute_groups(minute_bars: pd.DataFrame) -> dict[str, pd.DataFrame]:
    if minute_bars.empty:
        return {}
    return {
        str(symbol): group.sort_values("bar_datetime").reset_index(drop=True)
        for symbol, group in minute_bars.groupby("vt_symbol", sort=False)
    }


def _direction_sign(direction: Any) -> float:
    return 1.0 if str(direction) == "long" else -1.0


def _first_level_outcome(
    bars: pd.DataFrame,
    *,
    direction: str,
    entry_price: float,
    risk_pct: float,
    multiple: float,
) -> tuple[str, str]:
    if bars.empty or entry_price <= 0 or risk_pct <= 0:
        return "no_data", ""
    sign = _direction_sign(direction)
    target = entry_price * (1.0 + sign * risk_pct * multiple)
    stop = entry_price * (1.0 - sign * risk_pct * multiple)
    for row in bars.itertuples(index=False):
        dt = pd.Timestamp(row.bar_datetime).strftime("%Y-%m-%d %H:%M")
        if direction == "long":
            stop_hit = float(row.low) <= stop
            target_hit = float(row.high) >= target
        else:
            stop_hit = float(row.high) >= stop
            target_hit = float(row.low) <= target
        if stop_hit and target_hit:
            return "ambiguous_same_bar", dt
        if stop_hit:
            return "stop_first", dt
        if target_hit:
            return "target_first", dt
    return "neither", ""


def _intraday_features_for_lot(row: pd.Series, minute_by_symbol: dict[str, pd.DataFrame]) -> dict[str, Any]:
    lot_id = int(row["lot_id"])
    vt_symbol = str(row["vt_symbol"])
    direction = str(row["direction"])
    entry_date = pd.Timestamp(row["entry_date"]).normalize()
    exit_date = pd.Timestamp(row["exit_date"]).normalize()
    entry_price = _safe_float(row.get("entry_price"))
    exit_price = _safe_float(row.get("exit_price"))
    risk_pct = _safe_float(row.get("entry_risk_distance_pct"))
    risk_pct = risk_pct if risk_pct > 0 else abs(exit_price - entry_price) / entry_price if entry_price > 0 else np.nan
    sign = _direction_sign(direction)
    bars = minute_by_symbol.get(vt_symbol, pd.DataFrame())
    base: dict[str, Any] = {
        "lot_id": lot_id,
        "vt_symbol": vt_symbol,
        "direction": direction,
        "entry_date": entry_date.strftime("%Y-%m-%d"),
        "exit_date": exit_date.strftime("%Y-%m-%d"),
        "entry_price": entry_price,
        "exit_price": exit_price,
        "risk_pct": risk_pct,
        "minute_bars_total_for_symbol": int(len(bars)),
        "entry_day_minute_bars": 0,
        "exit_day_minute_bars": 0,
        "holding_window_minute_bars": 0,
        "minute_coverage_state": "missing_symbol_minutes" if bars.empty else "missing_entry_day_minutes",
    }
    if bars.empty or entry_price <= 0:
        return base

    holding = bars[(bars["bar_date"] >= entry_date) & (bars["bar_date"] <= exit_date)].copy()
    entry_day = bars[bars["bar_date"].eq(entry_date)].copy()
    exit_day = bars[bars["bar_date"].eq(exit_date)].copy()
    base["entry_day_minute_bars"] = int(len(entry_day))
    base["exit_day_minute_bars"] = int(len(exit_day))
    base["holding_window_minute_bars"] = int(len(holding))
    if entry_day.empty:
        base["minute_coverage_state"] = "missing_entry_day_minutes"
        return base
    base["minute_coverage_state"] = "entry_day_covered"

    def _mfe_mae(frame: pd.DataFrame) -> tuple[float, float]:
        if frame.empty:
            return np.nan, np.nan
        if direction == "long":
            mfe = (pd.to_numeric(frame["high"], errors="coerce").max() - entry_price) / entry_price
            mae = (entry_price - pd.to_numeric(frame["low"], errors="coerce").min()) / entry_price
        else:
            mfe = (entry_price - pd.to_numeric(frame["low"], errors="coerce").min()) / entry_price
            mae = (pd.to_numeric(frame["high"], errors="coerce").max() - entry_price) / entry_price
        return float(mfe), float(mae)

    full_mfe_pct, full_mae_pct = _mfe_mae(entry_day)
    base["entry_day_mfe_pct"] = full_mfe_pct
    base["entry_day_mae_pct"] = full_mae_pct
    base["entry_day_mfe_r"] = full_mfe_pct / risk_pct if risk_pct > 0 else np.nan
    base["entry_day_mae_r"] = full_mae_pct / risk_pct if risk_pct > 0 else np.nan
    base["entry_day_close_return_pct"] = (
        sign * (float(entry_day["close"].iloc[-1]) - entry_price) / entry_price
    )

    opening = entry_day.head(OPENING_RANGE_BARS)
    after_opening = entry_day.iloc[OPENING_RANGE_BARS:]
    if len(opening):
        or_high = float(opening["high"].max())
        or_low = float(opening["low"].min())
        base["opening_range_high"] = or_high
        base["opening_range_low"] = or_low
        base["opening_range_width_pct"] = (or_high - or_low) / entry_price if entry_price > 0 else np.nan
        if after_opening.empty:
            base["opening_range_breakout_confirmed"] = 0
            base["opening_range_breakout_time"] = ""
        elif direction == "long":
            hits = after_opening[after_opening["high"].ge(or_high)]
            base["opening_range_breakout_confirmed"] = int(not hits.empty)
            base["opening_range_breakout_time"] = (
                pd.Timestamp(hits["bar_datetime"].iloc[0]).strftime("%Y-%m-%d %H:%M") if not hits.empty else ""
            )
        else:
            hits = after_opening[after_opening["low"].le(or_low)]
            base["opening_range_breakout_confirmed"] = int(not hits.empty)
            base["opening_range_breakout_time"] = (
                pd.Timestamp(hits["bar_datetime"].iloc[0]).strftime("%Y-%m-%d %H:%M") if not hits.empty else ""
            )

    for n_bars in FAST_WINDOWS:
        frame = entry_day.head(n_bars)
        mfe_pct, mae_pct = _mfe_mae(frame)
        base[f"mfe_{n_bars}m_r"] = mfe_pct / risk_pct if risk_pct > 0 else np.nan
        base[f"mae_{n_bars}m_r"] = mae_pct / risk_pct if risk_pct > 0 else np.nan
        base[f"fail_fast_{n_bars}m_05r"] = int(
            risk_pct > 0 and mae_pct >= 0.5 * risk_pct and mfe_pct < 0.5 * risk_pct
        )
        base[f"confirm_fast_{n_bars}m_1r"] = int(risk_pct > 0 and mfe_pct >= 1.0 * risk_pct)

    for multiple in RISK_R_MULTIPLES:
        outcome, hit_time = _first_level_outcome(
            entry_day,
            direction=direction,
            entry_price=entry_price,
            risk_pct=risk_pct,
            multiple=multiple,
        )
        key = str(multiple).replace(".", "p")
        base[f"entry_day_first_{key}r_outcome"] = outcome
        base[f"entry_day_first_{key}r_time"] = hit_time

    if risk_pct > 0:
        stopped = False
        reentries = 0
        entry_level = entry_price
        stop_level = entry_price * (1.0 - sign * 0.5 * risk_pct)
        for item in entry_day.itertuples(index=False):
            if direction == "long":
                if not stopped and float(item.low) <= stop_level:
                    stopped = True
                elif stopped and float(item.high) >= entry_level:
                    reentries += 1
                    stopped = False
            else:
                if not stopped and float(item.high) >= stop_level:
                    stopped = True
                elif stopped and float(item.low) <= entry_level:
                    reentries += 1
                    stopped = False
        base["reentry_cross_count_after_05r_stop"] = int(reentries)
    return base


def _build_intraday_features(closed: pd.DataFrame, minute_bars: pd.DataFrame) -> pd.DataFrame:
    minute_by_symbol = _minute_groups(minute_bars)
    rows = [_intraday_features_for_lot(row, minute_by_symbol) for _, row in closed.iterrows()]
    feature_frame = pd.DataFrame(rows)
    duplicate_cols = [
        column
        for column in ["vt_symbol", "direction", "entry_date", "exit_date", "entry_price", "exit_price"]
        if column in feature_frame.columns
    ]
    feature_frame = feature_frame.drop(columns=duplicate_cols)
    return closed.merge(feature_frame, on="lot_id", how="left")


def _bucket_stats(features: pd.DataFrame) -> pd.DataFrame:
    specs = [
        ("minute_coverage_state", None),
        ("direction", None),
        ("signal", None),
        ("exit_reason", None),
        ("opening_range_breakout_confirmed", None),
        ("entry_day_first_0p5r_outcome", None),
        ("entry_day_first_1p0r_outcome", None),
        ("fail_fast_30m_05r", None),
        ("confirm_fast_60m_1r", None),
        ("reentry_cross_count_after_05r_stop", "clip3"),
    ]
    rows: list[dict[str, Any]] = []
    data = features.copy()
    data["realized_pnl"] = pd.to_numeric(data["realized_pnl"], errors="coerce")
    data["r_multiple"] = pd.to_numeric(data["r_multiple"], errors="coerce")
    data["winner"] = data["realized_pnl"].gt(0).astype(int)
    positive = data[data["r_multiple"].gt(0)]["r_multiple"].dropna()
    big_threshold = float(positive.quantile(0.80)) if len(positive) else np.nan
    data["stage825_big_winner"] = data["r_multiple"].ge(big_threshold).fillna(False).astype(int)
    base_win = float(data["winner"].mean()) if len(data) else 0.0
    base_avg_r = float(data["r_multiple"].mean()) if len(data) else 0.0
    base_big = float(data["stage825_big_winner"].mean()) if len(data) else 0.0

    for feature, mode in specs:
        if feature not in data.columns:
            continue
        series = data[feature].copy()
        if mode == "clip3":
            series = pd.to_numeric(series, errors="coerce").fillna(-1).clip(upper=3).astype(int).astype(str)
        for value, group in data.groupby(series, dropna=False):
            if len(group) < 8:
                continue
            win_rate = float(group["winner"].mean())
            avg_r = float(group["r_multiple"].mean())
            big_rate = float(group["stage825_big_winner"].mean())
            rows.append(
                {
                    "feature": feature,
                    "feature_value": str(value),
                    "count": int(len(group)),
                    "win_rate_pct": win_rate * 100.0,
                    "big_winner_rate_pct": big_rate * 100.0,
                    "avg_r": avg_r,
                    "median_r": float(group["r_multiple"].median()),
                    "total_r": float(group["r_multiple"].sum()),
                    "total_pnl": float(group["realized_pnl"].sum()),
                    "median_entry_day_mfe_r": float(pd.to_numeric(group.get("entry_day_mfe_r"), errors="coerce").median()),
                    "median_entry_day_mae_r": float(pd.to_numeric(group.get("entry_day_mae_r"), errors="coerce").median()),
                    "diagnostic_score": (win_rate - base_win) + 0.15 * (avg_r - base_avg_r) + 0.5 * (big_rate - base_big),
                }
            )
    result = pd.DataFrame(rows)
    if not result.empty:
        result.sort_values(["diagnostic_score", "count"], ascending=[False, False], inplace=True)
    return result


def _rule_candidates(features: pd.DataFrame, bucket_stats: pd.DataFrame) -> pd.DataFrame:
    data = features.copy()
    data["realized_pnl"] = pd.to_numeric(data["realized_pnl"], errors="coerce")
    data["r_multiple"] = pd.to_numeric(data["r_multiple"], errors="coerce")
    data["winner"] = data["realized_pnl"].gt(0).astype(int)

    def _series(column: str, default: Any) -> pd.Series:
        if column in data.columns:
            return data[column]
        return pd.Series(default, index=data.index)

    candidates = [
        {
            "rule_id": "R1_or15_confirm_then_enter",
            "rule_family": "opening_range_breakout",
            "rule_text": "开仓日先观察前15根1分钟K，只有价格突破开盘区间的信号方向后才允许入场；止损放在开盘区间另一侧。",
            "mask": _series("opening_range_breakout_confirmed", 0).fillna(0).astype(int).eq(1),
        },
        {
            "rule_id": "R2_failfast30_stop_retry",
            "rule_family": "fail_fast_reentry",
            "rule_text": "入场后30分钟内若先出现0.5R逆向且未出现0.5R顺向，立即止损；之后重新突破入场价可最多重试。",
            "mask": _series("fail_fast_30m_05r", 0).fillna(0).astype(int).eq(0),
        },
        {
            "rule_id": "R3_first1r_target_before_stop",
            "rule_family": "real_time_stop_sequence",
            "rule_text": "开仓日1R目标必须先于1R止损被触发；否则视为日内质量不足，不死扛。",
            "mask": _series("entry_day_first_1p0r_outcome", "").astype(str).isin(["target_first", "neither"]),
        },
        {
            "rule_id": "R4_confirm60_1r_trail",
            "rule_family": "confirm_then_trail",
            "rule_text": "入场后60分钟内达到1R顺向，才进入趋势持有；之后用日内低/高点或0.5R追踪止损保护利润。",
            "mask": _series("confirm_fast_60m_1r", 0).fillna(0).astype(int).eq(1),
        },
        {
            "rule_id": "R5_allow_reentry_after_05r_stop",
            "rule_family": "multi_attempt",
            "rule_text": "若0.5R实时止损后，价格重新穿越原入场价，允许有限多次尝试；记录可重试次数而非一次错过趋势。",
            "mask": pd.to_numeric(_series("reentry_cross_count_after_05r_stop", 0), errors="coerce").fillna(0).gt(0),
        },
    ]
    rows: list[dict[str, Any]] = []
    all_rows = len(data)
    all_pnl = float(data["realized_pnl"].sum()) if all_rows else 0.0
    all_r = float(data["r_multiple"].sum()) if all_rows else 0.0
    for item in candidates:
        mask = item["mask"].fillna(False)
        subset = data[mask].copy()
        rejected = data[~mask].copy()
        rows.append(
            {
                "rule_id": item["rule_id"],
                "rule_family": item["rule_family"],
                "rule_text": item["rule_text"],
                "covered_lots": int(len(subset)),
                "covered_lot_pct": float(len(subset) / all_rows * 100.0) if all_rows else 0.0,
                "covered_total_pnl": float(subset["realized_pnl"].sum()) if len(subset) else 0.0,
                "covered_total_r": float(subset["r_multiple"].sum()) if len(subset) else 0.0,
                "covered_win_rate_pct": float(subset["winner"].mean() * 100.0) if len(subset) else np.nan,
                "rejected_lots": int(len(rejected)),
                "rejected_total_pnl": float(rejected["realized_pnl"].sum()) if len(rejected) else 0.0,
                "rejected_total_r": float(rejected["r_multiple"].sum()) if len(rejected) else 0.0,
                "all_total_pnl": all_pnl,
                "all_total_r": all_r,
                "stage001_judgment": "diagnostic_only_not_promoted",
            }
        )
    return pd.DataFrame(rows)


def _coverage(features: pd.DataFrame) -> pd.DataFrame:
    if features.empty:
        return pd.DataFrame()
    data = features.copy()
    data["entry_year"] = pd.to_datetime(data["entry_date"], errors="coerce").dt.year
    rows: list[dict[str, Any]] = []
    for keys, group in data.groupby(["entry_year", "minute_coverage_state"], dropna=False):
        rows.append(
            {
                "entry_year": int(keys[0]) if not pd.isna(keys[0]) else 0,
                "minute_coverage_state": str(keys[1]),
                "lots": int(len(group)),
                "total_pnl": float(pd.to_numeric(group["realized_pnl"], errors="coerce").sum()),
                "avg_entry_day_bars": float(pd.to_numeric(group["entry_day_minute_bars"], errors="coerce").mean()),
            }
        )
    return pd.DataFrame(rows).sort_values(["entry_year", "minute_coverage_state"]).reset_index(drop=True)


def _plot_candles(ax: plt.Axes, bars: pd.DataFrame) -> None:
    width = 0.64
    for idx, row in enumerate(bars.itertuples(index=False)):
        open_price = float(row.open)
        high_price = float(row.high)
        low_price = float(row.low)
        close_price = float(row.close)
        color = "#dc2626" if close_price >= open_price else "#059669"
        ax.vlines(idx, low_price, high_price, color=color, linewidth=0.7, alpha=0.9)
        lower = min(open_price, close_price)
        height = abs(close_price - open_price)
        if height <= 0:
            height = max(high_price - low_price, 1.0) * 0.006
            lower -= height / 2.0
        ax.add_patch(
            plt.Rectangle(
                (idx - width / 2.0, lower),
                width,
                height,
                facecolor=color,
                edgecolor=color,
                linewidth=0.35,
                alpha=0.75,
            )
        )


def _plot_lot(ax: plt.Axes, row: pd.Series, minute_by_symbol: dict[str, pd.DataFrame]) -> dict[str, Any]:
    lot_id = int(row["lot_id"])
    vt_symbol = str(row["vt_symbol"])
    entry_date = pd.Timestamp(row["entry_date"]).normalize()
    direction = str(row["direction"])
    entry_price = _safe_float(row.get("entry_price"))
    risk_pct = _safe_float(row.get("risk_pct"))
    bars = minute_by_symbol.get(vt_symbol, pd.DataFrame())
    entry_day = bars[bars["bar_date"].eq(entry_date)].copy() if not bars.empty else pd.DataFrame()
    record = {"lot_id": lot_id, "chart_missing_minutes": int(entry_day.empty), "chart_page": 0}
    if entry_day.empty:
        ax.axis("off")
        ax.text(
            0.5,
            0.5,
            (
                f"missing entry-day minute bars\nlot{lot_id} {vt_symbol} {direction}\n"
                f"{entry_date:%Y-%m-%d} pnl={_safe_float(row.get('realized_pnl')):,.0f} "
                f"R={_safe_float(row.get('r_multiple')):.2f}"
            ),
            ha="center",
            va="center",
            fontsize=10,
            color="#991b1b",
        )
        return record

    window = entry_day.head(240).copy().reset_index(drop=True)
    _plot_candles(ax, window)
    x = np.arange(len(window))
    ax.plot(x, window["close"].rolling(5).mean(), color="#f59e0b", linewidth=0.8, alpha=0.8)
    ax.plot(x, window["close"].rolling(20).mean(), color="#2563eb", linewidth=0.8, alpha=0.75)
    ax.axhline(entry_price, color="#1d4ed8", linewidth=1.0, alpha=0.85)
    if risk_pct > 0 and entry_price > 0:
        sign = _direction_sign(direction)
        ax.axhline(entry_price * (1.0 - sign * 0.5 * risk_pct), color="#ef4444", linewidth=0.9, alpha=0.8)
        ax.axhline(entry_price * (1.0 + sign * 1.0 * risk_pct), color="#16a34a", linewidth=0.9, alpha=0.8)
    if len(window) >= OPENING_RANGE_BARS:
        opening = window.head(OPENING_RANGE_BARS)
        ax.axhline(float(opening["high"].max()), color="#7c3aed", linewidth=0.75, linestyle="--", alpha=0.7)
        ax.axhline(float(opening["low"].min()), color="#7c3aed", linewidth=0.75, linestyle="--", alpha=0.7)
        ax.axvspan(0, OPENING_RANGE_BARS - 1, color="#fef3c7", alpha=0.22)
    ticks = np.linspace(0, len(window) - 1, num=min(7, len(window)), dtype=int)
    labels = [pd.Timestamp(window.loc[pos, "bar_datetime"]).strftime("%H:%M") for pos in ticks]
    ax.set_xticks(ticks)
    ax.set_xticklabels(labels, rotation=0, fontsize=7)
    ax.grid(True, alpha=0.18, linewidth=0.5)
    ax.tick_params(axis="y", labelsize=7)
    title = (
        f"lot{lot_id} {vt_symbol} {direction} {entry_date:%Y-%m-%d} "
        f"pnl={_safe_float(row.get('realized_pnl')):,.0f} R={_safe_float(row.get('r_multiple')):.2f} "
        f"OR={int(_safe_float(row.get('opening_range_breakout_confirmed'), 0))} "
        f"1R={row.get('entry_day_first_1p0r_outcome', '')}"
    )
    ax.set_title(title, fontsize=8.5, loc="left")
    return record


def _plot_atlas(features: pd.DataFrame, minute_bars: pd.DataFrame) -> tuple[list[Path], pd.DataFrame]:
    minute_by_symbol = _minute_groups(minute_bars)
    ordered = features.copy()
    ordered["abs_r"] = pd.to_numeric(ordered["r_multiple"], errors="coerce").abs()
    ordered.sort_values(["abs_r", "entry_date", "lot_id"], ascending=[False, True, True], inplace=True)
    total_pages = int(math.ceil(len(ordered) / PER_PAGE)) if len(ordered) else 0
    if MAX_ATLAS_PAGES > 0:
        total_pages = min(total_pages, MAX_ATLAS_PAGES)
    paths: list[Path] = []
    records: list[dict[str, Any]] = []
    for page in range(1, total_pages + 1):
        part = ordered.iloc[(page - 1) * PER_PAGE : page * PER_PAGE].copy()
        fig, axes = plt.subplots(len(part), 1, figsize=(18, max(4.0, 3.2 * len(part))), constrained_layout=True)
        if len(part) == 1:
            axes = [axes]
        for ax, (_, row) in zip(axes, part.iterrows(), strict=False):
            rec = _plot_lot(ax, row, minute_by_symbol)
            rec["chart_page"] = page
            records.append(rec)
        fig.suptitle(
            (
                "Stage825 Stage819 intraday entry-day atlas "
                f"(sorted by |R|, page {page}/{total_pages}; blue=entry, red=0.5R stop, green=1R target, purple=OR15)"
            ),
            fontsize=13,
        )
        path = Path(str(CHART_PATH_TEMPLATE).format(page=page))
        fig.savefig(path, dpi=150)
        plt.close(fig)
        paths.append(path)
    return paths, pd.DataFrame(records)


def _write_report(
    summary: pd.DataFrame,
    features: pd.DataFrame,
    bucket_stats: pd.DataFrame,
    rule_candidates: pd.DataFrame,
    coverage: pd.DataFrame,
    chart_paths: list[Path],
) -> None:
    row = summary.iloc[0].to_dict()
    lines = [
        "# Stage825 Stage819候选分钟级规则逐笔法证",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 源候选：`{stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION}`",
        f"- 区间：`{START.date()}` 到 `{END.date()}`",
        "- 阶段性质：只读法证；不改正式配置、不连接 CTP、不调用下单。",
        "",
        "## 外部调研判断",
        "",
        "- GitHub/公开资料中常见的日内规则集中在开盘区间突破、固定止损/止盈、ATR或区间止损、收盘前平仓。",
        "- 本阶段只吸收这些低自由度规则形状；不使用 AI，不复制外部参数，不在 Stage819 上扫分钟阈值。",
        "",
        "## Full-Period Result",
        "",
        _md_table(
            pd.DataFrame(
                [
                    {
                        "end_equity": row.get("end_equity"),
                        "total_return_pct": row.get("total_return_pct"),
                        "max_dd_pct": row.get("max_dd_pct"),
                        "sharpe": row.get("sharpe"),
                        "total_slippage": row.get("total_slippage"),
                        "total_trade_count": row.get("total_trade_count"),
                        "win_rate_pct": row.get("nonzero_daily_win_rate_pct"),
                    }
                ]
            ),
            max_rows=5,
        ),
        "",
        "## Closed-Lot And Minute Coverage",
        "",
        _md_table(
            pd.DataFrame(
                [
                    {
                        "closed_lots": len(features),
                        "entry_day_covered_lots": int(features["minute_coverage_state"].eq("entry_day_covered").sum()),
                        "missing_entry_day_lots": int((~features["minute_coverage_state"].eq("entry_day_covered")).sum()),
                        "covered_pct": float(features["minute_coverage_state"].eq("entry_day_covered").mean() * 100.0)
                        if len(features)
                        else 0.0,
                    }
                ]
            ),
            max_rows=5,
        ),
        "",
        "## Coverage By Year",
        "",
        _md_table(coverage, max_rows=50),
        "",
        "## Rule Shape Diagnostics",
        "",
        _md_table(rule_candidates, max_rows=20),
        "",
        "## Best Buckets",
        "",
        _md_table(bucket_stats.head(30), max_rows=30),
        "",
        "## Atlas",
        "",
        *[f"- `{path}`" for path in chart_paths[:20]],
        "",
        "## Judgment",
        "",
        "- 本阶段没有发现可直接上线的规则，只形成规则候选的证据台账。",
        "- 过拟合判断：本阶段本身不是过拟合，因为规则形状预声明且没有接入策略；但如果按本表继续扫 `15/30/60/120`、`0.5R/1R/2R` 的小数变体，就会过拟合。",
        "- 继续价值判断：有。下一步应固定 1-2 个规则候选进入分钟级真实 A/C，而不是继续扩大特征表。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary, curve, frames, closed = _run_full()
    vt_symbols = set(closed["vt_symbol"].astype(str).dropna().unique())
    minute_bars = _load_minute_bars(vt_symbols)
    features = _build_intraday_features(closed, minute_bars)
    bucket_stats = _bucket_stats(features)
    rule_candidates = _rule_candidates(features, bucket_stats)
    coverage = _coverage(features)
    chart_paths, atlas_records = _plot_atlas(features, minute_bars)
    if not atlas_records.empty:
        features = features.merge(atlas_records, on="lot_id", how="left")

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    curve.to_csv(CURVE_PATH, index=False, encoding="utf-8-sig")
    frames.get("trades", pd.DataFrame()).to_csv(TRADES_PATH, index=False, encoding="utf-8-sig")
    frames.get("entry_risk", pd.DataFrame()).to_csv(ENTRY_RISK_PATH, index=False, encoding="utf-8-sig")
    frames.get("entry_candidates", pd.DataFrame()).to_csv(ENTRY_CANDIDATES_PATH, index=False, encoding="utf-8-sig")
    frames.get("trade_events", pd.DataFrame()).to_csv(TRADE_EVENTS_PATH, index=False, encoding="utf-8-sig")
    closed.to_csv(CLOSED_LOTS_PATH, index=False, encoding="utf-8-sig")
    features.to_csv(INTRADAY_FEATURES_PATH, index=False, encoding="utf-8-sig")
    bucket_stats.to_csv(BUCKET_STATS_PATH, index=False, encoding="utf-8-sig")
    rule_candidates.to_csv(RULE_CANDIDATES_PATH, index=False, encoding="utf-8-sig")
    coverage.to_csv(COVERAGE_PATH, index=False, encoding="utf-8-sig")
    atlas_records.to_csv(ATLAS_MANIFEST_PATH, index=False, encoding="utf-8-sig")
    _write_report(summary, features, bucket_stats, rule_candidates, coverage, chart_paths)

    row = summary.iloc[0].to_dict()
    decision = {
        "stage": "Stage825",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "source_candidate": stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION,
        "strategy_changed": False,
        "ctp_connected": False,
        "order_api_called": False,
        "closed_lots": int(len(features)),
        "entry_day_covered_lots": int(features["minute_coverage_state"].eq("entry_day_covered").sum()),
        "minute_coverage_pct": float(features["minute_coverage_state"].eq("entry_day_covered").mean() * 100.0)
        if len(features)
        else 0.0,
        "full_period_result": {
            "end_equity": row.get("end_equity"),
            "total_return_pct": row.get("total_return_pct"),
            "max_dd_pct": row.get("max_dd_pct"),
            "sharpe": row.get("sharpe"),
            "total_slippage": row.get("total_slippage"),
            "total_trade_count": row.get("total_trade_count"),
            "win_rate_pct": row.get("nonzero_daily_win_rate_pct"),
        },
        "rule_candidates": rule_candidates.drop(columns=["rule_text"], errors="ignore").to_dict("records"),
        "decision": "diagnostic_only_rules_not_promoted",
        "overfit_reflection": (
            "No rule is promoted in Stage825. The analysis uses fixed rule shapes from intraday trading practice; "
            "continuing to tune minute windows or R multiples from these results would be overfitting."
        ),
        "continue_value": (
            "Yes. The next useful step is a frozen minute-level A/C for one or two rule shapes with real-time stop and retry semantics."
        ),
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "curve": str(CURVE_PATH),
            "trades": str(TRADES_PATH),
            "entry_risk": str(ENTRY_RISK_PATH),
            "entry_candidates": str(ENTRY_CANDIDATES_PATH),
            "trade_events": str(TRADE_EVENTS_PATH),
            "closed_lots": str(CLOSED_LOTS_PATH),
            "intraday_features": str(INTRADAY_FEATURES_PATH),
            "bucket_stats": str(BUCKET_STATS_PATH),
            "rule_candidates": str(RULE_CANDIDATES_PATH),
            "coverage": str(COVERAGE_PATH),
            "atlas_manifest": str(ATLAS_MANIFEST_PATH),
            "report": str(REPORT_PATH),
            "atlas_pages": [str(path) for path in chart_paths],
        },
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print("rule_candidates")
    print(rule_candidates.to_string(index=False))
    print("coverage")
    print(coverage.to_string(index=False))


if __name__ == "__main__":
    main()
