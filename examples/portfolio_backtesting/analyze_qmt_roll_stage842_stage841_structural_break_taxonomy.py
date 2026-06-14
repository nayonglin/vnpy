from __future__ import annotations

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

import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage825_stage819_intraday_rule_forensics as s825
import qmt_roll_official_candidate_stage819_30w_config as stage819_cfg


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage842"
MODEL_TAG = "stage842_stage841_structural_break_taxonomy_v1"
OUTPUT_PREFIX = "qmt_roll_stage842_stage841_structural_break_taxonomy"

STAGE825_TAG = "stage825_stage819_intraday_rule_forensics_v1"
STAGE825_PREFIX = "qmt_roll_stage825_stage819_intraday_rule_forensics"
STAGE841_TAG = "stage841_stage840_c7_failfast_forensics_v1"
STAGE841_PREFIX = "qmt_roll_stage841_stage840_c7_failfast_forensics"

STAGE825_FEATURES_PATH = OUTPUT_DIR / f"{STAGE825_PREFIX}_intraday_features_{STAGE825_TAG}.csv"
STAGE841_EVENTS_PATH = OUTPUT_DIR / f"{STAGE841_PREFIX}_event_diagnostics_{STAGE841_TAG}.csv"

LOT_TAXONOMY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_lot_taxonomy_{MODEL_TAG}.csv"
RULE_STATS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rule_stats_{MODEL_TAG}.csv"
BUCKET_STATS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_stats_{MODEL_TAG}.csv"
SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
ATLAS_MANIFEST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"
CHART_PATH_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_page{{page:03d}}_{MODEL_TAG}.png"

OPENING_RANGE_BARS = 15
PER_PAGE = 4
MAX_ATLAS_ROWS = 32

RULE_SPECS = [
    {
        "rule_id": "S1_or15_adverse_touch_before_reclaim_or_dir",
        "trigger_col": "rule_s1_or15_adverse_touch_before_reclaim_or_dir",
        "price_col": "first_adverse_or15_touch_close",
        "time_col": "first_adverse_or15_touch_time",
        "rule_text": "0.5R逆向触发后，若价格先触碰OR15反向边界，且早于重新站回入场或重新突破信号方向OR15，则视为结构破坏。",
    },
    {
        "rule_id": "S2_or15_adverse_close_before_reclaim",
        "trigger_col": "rule_s2_or15_adverse_close_before_reclaim",
        "price_col": "first_adverse_or15_close_price",
        "time_col": "first_adverse_or15_close_time",
        "rule_text": "0.5R逆向触发后，若1分钟收盘价先收在OR15反向边界外，且早于重新站回入场，则视为结构破坏。",
    },
    {
        "rule_id": "S3_two_stop_side_closes_before_reclaim",
        "trigger_col": "rule_s3_two_stop_side_closes_before_reclaim",
        "price_col": "two_stop_side_closes_price",
        "time_col": "two_stop_side_closes_time",
        "rule_text": "0.5R逆向触发后，若连续两根1分钟K收在0.5R止损侧，且早于重新站回入场，则视为结构破坏。",
    },
    {
        "rule_id": "S4_no_prior_dir_or15_then_adverse_touch",
        "trigger_col": "rule_s4_no_prior_dir_or15_then_adverse_touch",
        "price_col": "first_adverse_or15_touch_close",
        "time_col": "first_adverse_or15_touch_time",
        "rule_text": "入场后尚未先突破信号方向OR15，就触发0.5R逆向并随后先触碰OR15反向边界，视为确认失败。",
    },
]


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


def _direction_sign(direction: Any) -> float:
    return 1.0 if str(direction) == "long" else -1.0


def _load_features() -> pd.DataFrame:
    if not STAGE825_FEATURES_PATH.exists():
        raise RuntimeError(f"missing required Stage825 features: {STAGE825_FEATURES_PATH}")
    frame = pd.read_csv(STAGE825_FEATURES_PATH, encoding="utf-8-sig")
    for column in ["entry_date", "exit_date"]:
        frame[column] = pd.to_datetime(frame[column], errors="coerce").dt.tz_localize(None).dt.normalize()
    numeric_columns = [
        "lot_id",
        "entry_price",
        "exit_price",
        "volume",
        "size",
        "realized_pnl",
        "risk_amount",
        "r_multiple",
        "risk_pct",
        "entry_day_close_return_pct",
        "entry_day_mfe_r",
        "entry_day_mae_r",
        "opening_range_high",
        "opening_range_low",
    ]
    for column in numeric_columns:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def _load_stage841_events() -> pd.DataFrame:
    if not STAGE841_EVENTS_PATH.exists():
        raise RuntimeError(f"missing required Stage841 diagnostics: {STAGE841_EVENTS_PATH}")
    events = pd.read_csv(STAGE841_EVENTS_PATH, encoding="utf-8-sig")
    for column in ["baseline_lot_id", "event_id", "c7_vs_c4_pnl_delta", "c4_realized_pnl", "c7_realized_pnl"]:
        if column in events.columns:
            events[column] = pd.to_numeric(events[column], errors="coerce")
    keep = [
        "baseline_lot_id",
        "event_id",
        "forensic_bucket",
        "recovered_after_stop_shape",
        "c7_vs_c4_pnl_delta",
        "c4_realized_pnl",
        "c7_realized_pnl",
    ]
    events = events[[column for column in keep if column in events.columns]].copy()
    events = events.dropna(subset=["baseline_lot_id"]).copy()
    events["baseline_lot_id"] = events["baseline_lot_id"].astype(int)
    rename = {
        "event_id": "stage841_event_id",
        "forensic_bucket": "stage841_forensic_bucket",
        "recovered_after_stop_shape": "stage841_recovered_after_stop_shape",
        "c7_vs_c4_pnl_delta": "stage841_c7_vs_c4_pnl_delta",
        "c4_realized_pnl": "stage841_c4_realized_pnl",
        "c7_realized_pnl": "stage841_c7_realized_pnl",
    }
    return events.rename(columns=rename).drop_duplicates("baseline_lot_id")


def _bar_time(bars: pd.DataFrame, idx: float | int | None) -> str:
    if idx is None or pd.isna(idx):
        return ""
    pos = int(idx)
    if pos < 0 or pos >= len(bars):
        return ""
    return pd.Timestamp(bars.loc[pos, "bar_datetime"]).strftime("%Y-%m-%d %H:%M")


def _close_at(bars: pd.DataFrame, idx: float | int | None) -> float:
    if idx is None or pd.isna(idx):
        return np.nan
    pos = int(idx)
    if pos < 0 or pos >= len(bars):
        return np.nan
    return _safe_float(bars.loc[pos, "close"])


def _first_after_idx(after: pd.DataFrame, predicate: pd.Series) -> float:
    hits = after[predicate.fillna(False)]
    if hits.empty:
        return np.nan
    return float(hits.index[0])


def _pnl_at_exit(row: pd.Series, exit_price: Any) -> float:
    price = _safe_float(exit_price)
    entry_price = _safe_float(row.get("entry_price"))
    size = _safe_float(row.get("size"), 1.0)
    volume = _safe_float(row.get("volume"), 0.0)
    if not np.isfinite(price * entry_price * size * volume):
        return np.nan
    return float(_direction_sign(row.get("direction")) * (price - entry_price) * size * volume)


def _first_stop_side_two_closes(entry_day: pd.DataFrame, stop_idx: int, *, direction: str, stop05: float) -> float:
    consecutive = 0
    for pos in range(stop_idx + 1, len(entry_day)):
        close = _safe_float(entry_day.loc[pos, "close"])
        if direction == "long":
            on_stop_side = close <= stop05
        else:
            on_stop_side = close >= stop05
        if on_stop_side:
            consecutive += 1
            if consecutive >= 2:
                return float(pos)
        else:
            consecutive = 0
    return np.nan


def _lot_taxonomy(row: pd.Series, minute_by_symbol: dict[str, pd.DataFrame]) -> dict[str, Any]:
    lot_id = int(row["lot_id"])
    vt_symbol = str(row["vt_symbol"])
    direction = str(row["direction"])
    entry_date = pd.Timestamp(row["entry_date"]).normalize()
    entry_price = _safe_float(row.get("entry_price"))
    risk_pct = _safe_float(row.get("risk_pct"))
    if not np.isfinite(risk_pct) or risk_pct <= 0:
        risk_amount = abs(_safe_float(row.get("risk_amount")))
        size = _safe_float(row.get("size"), 1.0)
        volume = _safe_float(row.get("volume"), 0.0)
        risk_pct = risk_amount / (entry_price * size * volume) if entry_price > 0 and size > 0 and volume > 0 else np.nan
    bars = minute_by_symbol.get(vt_symbol, pd.DataFrame())
    entry_day = bars[bars["bar_date"].eq(entry_date)].copy().reset_index(drop=True) if not bars.empty else pd.DataFrame()
    result: dict[str, Any] = {
        "lot_id": lot_id,
        "structure_coverage_state": "entry_day_covered" if not entry_day.empty else "missing_entry_day_minutes",
        "entry_day_minute_bars_stage842": int(len(entry_day)),
        "risk_pct_stage842": risk_pct,
        "stop05_hit": 0,
        "first_stop05_idx": np.nan,
        "first_stop05_time": "",
        "first_stop05_close": np.nan,
        "direction_or15_before_stop": 0,
        "fav05_before_stop": 0,
        "post_stop_reclaim_entry": 0,
        "post_stop_direction_or15_break": 0,
        "post_stop_adverse_or15_touch": 0,
        "post_stop_adverse_or15_close": 0,
        "post_stop_reach_05r": 0,
        "post_stop_reach_1r": 0,
        "first_reclaim_entry_idx": np.nan,
        "first_reclaim_entry_time": "",
        "first_direction_or15_idx": np.nan,
        "first_direction_or15_time": "",
        "first_adverse_or15_touch_idx": np.nan,
        "first_adverse_or15_touch_time": "",
        "first_adverse_or15_touch_close": np.nan,
        "first_adverse_or15_close_idx": np.nan,
        "first_adverse_or15_close_time": "",
        "first_adverse_or15_close_price": np.nan,
        "two_stop_side_closes_idx": np.nan,
        "two_stop_side_closes_time": "",
        "two_stop_side_closes_price": np.nan,
        "recovery_after_stop_shape_stage842": "no_stop05_hit",
        "no_reclaim_no_direction_or15_by_close": 0,
        "entry_day_close_return_r_stage842": np.nan,
        "rule_s1_or15_adverse_touch_before_reclaim_or_dir": 0,
        "rule_s2_or15_adverse_close_before_reclaim": 0,
        "rule_s3_two_stop_side_closes_before_reclaim": 0,
        "rule_s4_no_prior_dir_or15_then_adverse_touch": 0,
    }
    if entry_day.empty or entry_price <= 0 or not np.isfinite(risk_pct) or risk_pct <= 0:
        return result

    sign = _direction_sign(direction)
    stop05 = entry_price * (1.0 - sign * 0.5 * risk_pct)
    fav05 = entry_price * (1.0 + sign * 0.5 * risk_pct)
    fav1 = entry_price * (1.0 + sign * 1.0 * risk_pct)
    result["entry_day_close_return_r_stage842"] = sign * (_safe_float(entry_day["close"].iloc[-1]) - entry_price) / (
        entry_price * risk_pct
    )

    if direction == "long":
        stop_hits = entry_day[pd.to_numeric(entry_day["low"], errors="coerce").le(stop05)]
        fav05_hits_all = entry_day[pd.to_numeric(entry_day["high"], errors="coerce").ge(fav05)]
    else:
        stop_hits = entry_day[pd.to_numeric(entry_day["high"], errors="coerce").ge(stop05)]
        fav05_hits_all = entry_day[pd.to_numeric(entry_day["low"], errors="coerce").le(fav05)]
    if stop_hits.empty:
        return result

    stop_idx = int(stop_hits.index[0])
    result["stop05_hit"] = 1
    result["first_stop05_idx"] = stop_idx
    result["first_stop05_time"] = _bar_time(entry_day, stop_idx)
    result["first_stop05_close"] = _close_at(entry_day, stop_idx)
    result["fav05_before_stop"] = int(not fav05_hits_all.empty and int(fav05_hits_all.index[0]) <= stop_idx)

    if len(entry_day) >= OPENING_RANGE_BARS:
        opening = entry_day.head(OPENING_RANGE_BARS)
        or_high = _safe_float(opening["high"].max())
        or_low = _safe_float(opening["low"].min())
    else:
        or_high = np.nan
        or_low = np.nan

    before_stop = entry_day.iloc[: stop_idx + 1].copy()
    after = entry_day.iloc[stop_idx + 1 :].copy()
    if np.isfinite(or_high) and np.isfinite(or_low):
        if direction == "long":
            result["direction_or15_before_stop"] = int(pd.to_numeric(before_stop["high"], errors="coerce").ge(or_high).any())
        else:
            result["direction_or15_before_stop"] = int(pd.to_numeric(before_stop["low"], errors="coerce").le(or_low).any())
    if after.empty:
        return result

    if direction == "long":
        reclaim_idx = _first_after_idx(after, pd.to_numeric(after["high"], errors="coerce").ge(entry_price))
        fav05_idx = _first_after_idx(after, pd.to_numeric(after["high"], errors="coerce").ge(fav05))
        fav1_idx = _first_after_idx(after, pd.to_numeric(after["high"], errors="coerce").ge(fav1))
        direction_or_idx = (
            _first_after_idx(after, pd.to_numeric(after["high"], errors="coerce").ge(or_high)) if np.isfinite(or_high) else np.nan
        )
        adverse_or_touch_idx = (
            _first_after_idx(after, pd.to_numeric(after["low"], errors="coerce").le(or_low)) if np.isfinite(or_low) else np.nan
        )
        adverse_or_close_idx = (
            _first_after_idx(after, pd.to_numeric(after["close"], errors="coerce").le(or_low)) if np.isfinite(or_low) else np.nan
        )
    else:
        reclaim_idx = _first_after_idx(after, pd.to_numeric(after["low"], errors="coerce").le(entry_price))
        fav05_idx = _first_after_idx(after, pd.to_numeric(after["low"], errors="coerce").le(fav05))
        fav1_idx = _first_after_idx(after, pd.to_numeric(after["low"], errors="coerce").le(fav1))
        direction_or_idx = (
            _first_after_idx(after, pd.to_numeric(after["low"], errors="coerce").le(or_low)) if np.isfinite(or_low) else np.nan
        )
        adverse_or_touch_idx = (
            _first_after_idx(after, pd.to_numeric(after["high"], errors="coerce").ge(or_high)) if np.isfinite(or_high) else np.nan
        )
        adverse_or_close_idx = (
            _first_after_idx(after, pd.to_numeric(after["close"], errors="coerce").ge(or_high)) if np.isfinite(or_high) else np.nan
        )
    two_closes_idx = _first_stop_side_two_closes(entry_day, stop_idx, direction=direction, stop05=stop05)

    result["first_reclaim_entry_idx"] = reclaim_idx
    result["first_reclaim_entry_time"] = _bar_time(entry_day, reclaim_idx)
    result["post_stop_reclaim_entry"] = int(pd.notna(reclaim_idx))
    result["first_direction_or15_idx"] = direction_or_idx
    result["first_direction_or15_time"] = _bar_time(entry_day, direction_or_idx)
    result["post_stop_direction_or15_break"] = int(pd.notna(direction_or_idx))
    result["first_adverse_or15_touch_idx"] = adverse_or_touch_idx
    result["first_adverse_or15_touch_time"] = _bar_time(entry_day, adverse_or_touch_idx)
    result["first_adverse_or15_touch_close"] = _close_at(entry_day, adverse_or_touch_idx)
    result["post_stop_adverse_or15_touch"] = int(pd.notna(adverse_or_touch_idx))
    result["first_adverse_or15_close_idx"] = adverse_or_close_idx
    result["first_adverse_or15_close_time"] = _bar_time(entry_day, adverse_or_close_idx)
    result["first_adverse_or15_close_price"] = _close_at(entry_day, adverse_or_close_idx)
    result["post_stop_adverse_or15_close"] = int(pd.notna(adverse_or_close_idx))
    result["two_stop_side_closes_idx"] = two_closes_idx
    result["two_stop_side_closes_time"] = _bar_time(entry_day, two_closes_idx)
    result["two_stop_side_closes_price"] = _close_at(entry_day, two_closes_idx)
    result["post_stop_reach_05r"] = int(pd.notna(fav05_idx))
    result["post_stop_reach_1r"] = int(pd.notna(fav1_idx))
    result["no_reclaim_no_direction_or15_by_close"] = int(pd.isna(reclaim_idx) and pd.isna(direction_or_idx))
    result["recovery_after_stop_shape_stage842"] = np.select(
        [pd.notna(fav1_idx), pd.notna(fav05_idx), pd.notna(reclaim_idx), pd.notna(direction_or_idx)],
        ["post_stop_reached_1r", "post_stop_reached_0p5r", "post_stop_reclaimed_entry", "post_stop_direction_or15_break"],
        default="no_same_day_recovery",
    ).item()

    def _before(first: Any, second: Any) -> bool:
        return pd.notna(first) and (pd.isna(second) or float(first) < float(second))

    adverse_touch_before_reclaim = _before(adverse_or_touch_idx, reclaim_idx)
    adverse_touch_before_dir = _before(adverse_or_touch_idx, direction_or_idx)
    result["rule_s1_or15_adverse_touch_before_reclaim_or_dir"] = int(
        adverse_touch_before_reclaim and adverse_touch_before_dir
    )
    result["rule_s2_or15_adverse_close_before_reclaim"] = int(_before(adverse_or_close_idx, reclaim_idx))
    result["rule_s3_two_stop_side_closes_before_reclaim"] = int(_before(two_closes_idx, reclaim_idx))
    result["rule_s4_no_prior_dir_or15_then_adverse_touch"] = int(
        result["direction_or15_before_stop"] == 0 and result["rule_s1_or15_adverse_touch_before_reclaim_or_dir"] == 1
    )
    return result


def _build_lot_taxonomy() -> pd.DataFrame:
    features = _load_features()
    stage841 = _load_stage841_events()
    vt_symbols = set(features["vt_symbol"].astype(str).dropna().unique())
    minute_bars = s825._load_minute_bars(vt_symbols)
    minute_by_symbol = s825._minute_groups(minute_bars)
    taxonomy = pd.DataFrame([_lot_taxonomy(row, minute_by_symbol) for _, row in features.iterrows()])
    data = features.merge(taxonomy, on="lot_id", how="left")
    data = data.merge(stage841, left_on="lot_id", right_on="baseline_lot_id", how="left")
    data["stage841_forensic_bucket"] = data["stage841_forensic_bucket"].fillna("not_stage841_event")
    data["winner"] = pd.to_numeric(data["realized_pnl"], errors="coerce").gt(0).astype(int)
    data["loser"] = pd.to_numeric(data["realized_pnl"], errors="coerce").lt(0).astype(int)
    for spec in RULE_SPECS:
        trigger_col = spec["trigger_col"]
        price_col = spec["price_col"]
        pnl_col = f"{spec['rule_id']}_exit_pnl"
        delta_col = f"{spec['rule_id']}_delta_vs_baseline"
        data[pnl_col] = np.where(
            pd.to_numeric(data.get(trigger_col), errors="coerce").fillna(0).astype(int).eq(1),
            data.apply(lambda row: _pnl_at_exit(row, row.get(price_col)), axis=1),
            np.nan,
        )
        data[delta_col] = pd.to_numeric(data[pnl_col], errors="coerce") - pd.to_numeric(data["realized_pnl"], errors="coerce")
    return data


def _rule_stats(data: pd.DataFrame) -> pd.DataFrame:
    total_pnl = float(pd.to_numeric(data["realized_pnl"], errors="coerce").sum())
    rows: list[dict[str, Any]] = []
    for spec in RULE_SPECS:
        trigger_col = spec["trigger_col"]
        pnl_col = f"{spec['rule_id']}_exit_pnl"
        delta_col = f"{spec['rule_id']}_delta_vs_baseline"
        triggered = data[pd.to_numeric(data.get(trigger_col), errors="coerce").fillna(0).astype(int).eq(1)].copy()
        winners = triggered[pd.to_numeric(triggered["realized_pnl"], errors="coerce").gt(0)]
        losers = triggered[pd.to_numeric(triggered["realized_pnl"], errors="coerce").lt(0)]
        stage841 = triggered[triggered["stage841_forensic_bucket"].ne("not_stage841_event")]
        killed = triggered[triggered["stage841_forensic_bucket"].eq("killed_c4_winner")]
        saved = triggered[triggered["stage841_forensic_bucket"].eq("saved_c4_loser")]
        delta = pd.to_numeric(triggered.get(delta_col), errors="coerce")
        rows.append(
            {
                "rule_id": spec["rule_id"],
                "rule_text": spec["rule_text"],
                "triggered_lots": int(len(triggered)),
                "triggered_lot_pct": float(len(triggered) / len(data) * 100.0) if len(data) else 0.0,
                "triggered_baseline_pnl": float(pd.to_numeric(triggered["realized_pnl"], errors="coerce").sum()),
                "triggered_rule_exit_pnl": float(pd.to_numeric(triggered.get(pnl_col), errors="coerce").sum()),
                "gross_delta_vs_baseline": float(delta.sum()),
                "all_lots_baseline_pnl": total_pnl,
                "all_lots_after_overlay_gross_pnl": float(total_pnl + delta.sum()),
                "winner_triggered_lots": int(len(winners)),
                "winner_delta": float(pd.to_numeric(winners.get(delta_col), errors="coerce").sum()),
                "loser_triggered_lots": int(len(losers)),
                "loser_delta": float(pd.to_numeric(losers.get(delta_col), errors="coerce").sum()),
                "stage841_event_triggered_lots": int(len(stage841)),
                "stage841_killed_c4_winner_triggered": int(len(killed)),
                "stage841_saved_c4_loser_triggered": int(len(saved)),
                "stage841_triggered_delta_vs_baseline": float(pd.to_numeric(stage841.get(delta_col), errors="coerce").sum()),
                "diagnostic_judgment": "read_only_not_engine",
            }
        )
    result = pd.DataFrame(rows)
    if not result.empty:
        result.sort_values(["gross_delta_vs_baseline", "winner_delta"], ascending=[False, False], inplace=True)
    return result


def _bucket_stats(data: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    group_cols = [
        "structure_coverage_state",
        "stop05_hit",
        "recovery_after_stop_shape_stage842",
        "no_reclaim_no_direction_or15_by_close",
        "stage841_forensic_bucket",
        "direction",
    ]
    for group_col in group_cols:
        if group_col not in data.columns:
            continue
        for value, group in data.groupby(group_col, dropna=False):
            rows.append(
                {
                    "group_col": group_col,
                    "group_value": str(value),
                    "lots": int(len(group)),
                    "total_pnl": float(pd.to_numeric(group["realized_pnl"], errors="coerce").sum()),
                    "win_rate_pct": float(pd.to_numeric(group["winner"], errors="coerce").mean() * 100.0)
                    if len(group)
                    else np.nan,
                    "median_r": float(pd.to_numeric(group["r_multiple"], errors="coerce").median()),
                    "stage841_events": int(group["stage841_forensic_bucket"].ne("not_stage841_event").sum()),
                    "post_stop_reclaim_entry": int(pd.to_numeric(group.get("post_stop_reclaim_entry"), errors="coerce").fillna(0).sum()),
                    "post_stop_direction_or15_break": int(
                        pd.to_numeric(group.get("post_stop_direction_or15_break"), errors="coerce").fillna(0).sum()
                    ),
                    "post_stop_adverse_or15_touch": int(
                        pd.to_numeric(group.get("post_stop_adverse_or15_touch"), errors="coerce").fillna(0).sum()
                    ),
                }
            )
    result = pd.DataFrame(rows)
    if not result.empty:
        result.sort_values(["group_col", "total_pnl"], ascending=[True, True], inplace=True)
    return result


def _summary(data: pd.DataFrame, rule_stats: pd.DataFrame) -> pd.DataFrame:
    covered = data[data["structure_coverage_state"].eq("entry_day_covered")]
    stop_hit = data[pd.to_numeric(data["stop05_hit"], errors="coerce").fillna(0).astype(int).eq(1)]
    recoverable = stop_hit[
        pd.to_numeric(stop_hit[["post_stop_reclaim_entry", "post_stop_direction_or15_break", "post_stop_reach_05r", "post_stop_reach_1r"]].sum(axis=1), errors="coerce").gt(0)
    ]
    stage841 = data[data["stage841_forensic_bucket"].ne("not_stage841_event")]
    best = rule_stats.iloc[0].to_dict() if not rule_stats.empty else {}
    if best and _safe_float(best.get("gross_delta_vs_baseline"), 0.0) > 0 and _safe_float(
        best.get("stage841_triggered_delta_vs_baseline"), 0.0
    ) < 0:
        decision = "stage842_s3_positive_gross_but_stage841_negative_not_promoted_engine_watch"
    elif best and _safe_float(best.get("gross_delta_vs_baseline"), 0.0) > 0:
        decision = "stage842_structural_break_shape_has_positive_readonly_delta_requires_engine"
    else:
        decision = "stage842_structural_break_taxonomy_not_promoted_yet"
    return pd.DataFrame(
        [
            {
                "lots": int(len(data)),
                "entry_day_covered_lots": int(len(covered)),
                "stop05_hit_lots": int(len(stop_hit)),
                "recoverable_after_stop_lots": int(len(recoverable)),
                "stage841_event_lots": int(len(stage841)),
                "baseline_total_pnl": float(pd.to_numeric(data["realized_pnl"], errors="coerce").sum()),
                "best_rule_id": best.get("rule_id", ""),
                "best_rule_triggered_lots": int(best.get("triggered_lots", 0) or 0),
                "best_rule_gross_delta": float(best.get("gross_delta_vs_baseline", np.nan)) if best else np.nan,
                "best_rule_winner_delta": float(best.get("winner_delta", np.nan)) if best else np.nan,
                "best_rule_loser_delta": float(best.get("loser_delta", np.nan)) if best else np.nan,
                "decision": decision,
            }
        ]
    )


def _plot_taxonomy_lot(ax: plt.Axes, row: pd.Series, minute_by_symbol: dict[str, pd.DataFrame], best_rule: dict[str, Any]) -> dict[str, Any]:
    lot_id = int(row["lot_id"])
    vt_symbol = str(row["vt_symbol"])
    direction = str(row["direction"])
    entry_date = pd.Timestamp(row["entry_date"]).normalize()
    entry_price = _safe_float(row.get("entry_price"))
    risk_pct = _safe_float(row.get("risk_pct_stage842"))
    bars = minute_by_symbol.get(vt_symbol, pd.DataFrame())
    entry_day = bars[bars["bar_date"].eq(entry_date)].copy().reset_index(drop=True) if not bars.empty else pd.DataFrame()
    record = {
        "lot_id": lot_id,
        "vt_symbol": vt_symbol,
        "entry_date": entry_date.strftime("%Y-%m-%d"),
        "chart_missing_minutes": int(entry_day.empty),
        "best_rule_id": best_rule.get("rule_id", ""),
        "best_rule_triggered": int(_safe_float(row.get(best_rule.get("trigger_col", "")), 0.0) == 1.0) if best_rule else 0,
    }
    if entry_day.empty:
        ax.axis("off")
        ax.text(
            0.5,
            0.5,
            f"missing entry-day minutes\nlot{lot_id} {vt_symbol} {direction} {entry_date:%Y-%m-%d}",
            ha="center",
            va="center",
            color="#991b1b",
            fontsize=10,
        )
        return record

    window = entry_day.head(240).copy().reset_index(drop=True)
    s825._plot_candles(ax, window)
    x = np.arange(len(window))
    ax.plot(x, window["close"].rolling(5).mean(), color="#f59e0b", linewidth=0.8, alpha=0.8)
    ax.plot(x, window["close"].rolling(20).mean(), color="#2563eb", linewidth=0.8, alpha=0.75)
    ax.axhline(entry_price, color="#1d4ed8", linewidth=1.0, alpha=0.9)
    if entry_price > 0 and risk_pct > 0:
        sign = _direction_sign(direction)
        ax.axhline(entry_price * (1.0 - sign * 0.5 * risk_pct), color="#dc2626", linewidth=1.0, linestyle="--", alpha=0.9)
        ax.axhline(entry_price * (1.0 + sign * 0.5 * risk_pct), color="#16a34a", linewidth=0.9, linestyle=":", alpha=0.9)
        ax.axhline(entry_price * (1.0 + sign * 1.0 * risk_pct), color="#16a34a", linewidth=0.9, alpha=0.8)
    if len(window) >= OPENING_RANGE_BARS:
        opening = window.head(OPENING_RANGE_BARS)
        ax.axhline(float(opening["high"].max()), color="#7c3aed", linewidth=0.75, linestyle="--", alpha=0.7)
        ax.axhline(float(opening["low"].min()), color="#7c3aed", linewidth=0.75, linestyle="--", alpha=0.7)
        ax.axvspan(0, OPENING_RANGE_BARS - 1, color="#fef3c7", alpha=0.22)

    markers = [
        ("first_stop05_idx", "#dc2626", "-"),
        ("first_reclaim_entry_idx", "#1d4ed8", ":"),
        ("first_direction_or15_idx", "#16a34a", ":"),
        ("first_adverse_or15_touch_idx", "#111827", "--"),
        ("two_stop_side_closes_idx", "#9333ea", "--"),
    ]
    for column, color, style in markers:
        idx = row.get(column)
        if pd.notna(idx) and int(idx) < len(window):
            ax.axvline(int(idx), color=color, linewidth=1.0, linestyle=style, alpha=0.85)
    if best_rule:
        idx_col = {
            "first_adverse_or15_touch_close": "first_adverse_or15_touch_idx",
            "first_adverse_or15_close_price": "first_adverse_or15_close_idx",
            "two_stop_side_closes_price": "two_stop_side_closes_idx",
        }.get(best_rule.get("price_col", ""), "")
        idx = row.get(idx_col)
        if pd.notna(idx) and int(idx) < len(window):
            ax.axvline(int(idx), color="#000000", linewidth=1.6, alpha=0.9)
    ticks = np.linspace(0, len(window) - 1, num=min(7, len(window)), dtype=int)
    ax.set_xticks(ticks)
    ax.set_xticklabels([pd.Timestamp(window.loc[pos, "bar_datetime"]).strftime("%H:%M") for pos in ticks], fontsize=7)
    ax.grid(True, alpha=0.18, linewidth=0.5)
    ax.tick_params(axis="y", labelsize=7)
    best_delta = row.get(f"{best_rule.get('rule_id', '')}_delta_vs_baseline") if best_rule else np.nan
    title = (
        f"lot{lot_id} {vt_symbol} {direction} {entry_date:%Y-%m-%d} "
        f"pnl={_safe_float(row.get('realized_pnl')):,.0f} R={_safe_float(row.get('r_multiple')):.2f} "
        f"recover={row.get('recovery_after_stop_shape_stage842','')} "
        f"stage841={row.get('stage841_forensic_bucket','')} "
        f"best_delta={_safe_float(best_delta):,.0f}"
    )
    ax.set_title(title, fontsize=8.2, loc="left")
    return record


def _plot_atlas(data: pd.DataFrame, rule_stats: pd.DataFrame) -> tuple[list[Path], pd.DataFrame]:
    best_rule_id = str(rule_stats.iloc[0]["rule_id"]) if not rule_stats.empty else ""
    best_rule = next((item for item in RULE_SPECS if item["rule_id"] == best_rule_id), {})
    if not best_rule:
        return [], pd.DataFrame()
    delta_col = f"{best_rule_id}_delta_vs_baseline"
    trigger_col = best_rule["trigger_col"]
    triggered = data[pd.to_numeric(data.get(trigger_col), errors="coerce").fillna(0).astype(int).eq(1)].copy()
    stage841 = data[data["stage841_forensic_bucket"].ne("not_stage841_event")].copy()
    pieces = [
        triggered.sort_values(delta_col, ascending=False).head(10),
        triggered.sort_values(delta_col, ascending=True).head(10),
        stage841.sort_values("stage841_c7_vs_c4_pnl_delta", ascending=True).head(12),
    ]
    ordered = pd.concat(pieces, ignore_index=True, sort=False).drop_duplicates("lot_id").head(MAX_ATLAS_ROWS)
    if ordered.empty:
        return [], pd.DataFrame()
    vt_symbols = set(ordered["vt_symbol"].astype(str).dropna().unique())
    minute_bars = s825._load_minute_bars(vt_symbols)
    minute_by_symbol = s825._minute_groups(minute_bars)
    total_pages = int(math.ceil(len(ordered) / PER_PAGE))
    paths: list[Path] = []
    records: list[dict[str, Any]] = []
    for page in range(1, total_pages + 1):
        part = ordered.iloc[(page - 1) * PER_PAGE : page * PER_PAGE].copy()
        fig, axes = plt.subplots(len(part), 1, figsize=(18, max(4.0, 3.25 * len(part))), constrained_layout=True)
        if len(part) == 1:
            axes = [axes]
        for ax, (_, row) in zip(axes, part.iterrows(), strict=False):
            record = _plot_taxonomy_lot(ax, row, minute_by_symbol, best_rule)
            record["chart_page"] = page
            records.append(record)
        fig.suptitle(
            (
                f"Stage842 structural-break atlas, best={best_rule_id} "
                "(blue=entry/reclaim, red=-0.5R, green=favorable, purple=OR15, black=structural trigger)"
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
    rule_stats: pd.DataFrame,
    bucket_stats: pd.DataFrame,
    data: pd.DataFrame,
    atlas_paths: list[Path],
) -> None:
    best_rule_id = str(summary["best_rule_id"].iloc[0]) if not summary.empty else ""
    worst_harms = pd.DataFrame()
    best_saves = pd.DataFrame()
    if best_rule_id:
        delta_col = f"{best_rule_id}_delta_vs_baseline"
        trigger_col = next((item["trigger_col"] for item in RULE_SPECS if item["rule_id"] == best_rule_id), "")
        triggered = data[pd.to_numeric(data.get(trigger_col), errors="coerce").fillna(0).astype(int).eq(1)].copy()
        cols = [
            "lot_id",
            "vt_symbol",
            "direction",
            "entry_date",
            "realized_pnl",
            "r_multiple",
            "recovery_after_stop_shape_stage842",
            "stage841_forensic_bucket",
            delta_col,
        ]
        best_saves = triggered.sort_values(delta_col, ascending=False)[cols].head(12)
        worst_harms = triggered.sort_values(delta_col, ascending=True)[cols].head(12)
    lines = [
        "# Stage842 止损后结构破坏taxonomy",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 源候选：`{stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION}`",
        "- 阶段性质：只读 taxonomy + 分钟K视觉法证；不新增策略版本、不跑真实组合引擎、不连接 CTP、不调用下单。",
        "",
        "## 外部调研判断",
        "",
        "- CME 的订单与风险管理资料支持预定义止损、仓位和保证金管理；CFTC 对止损单的研究提醒止损触发与日内波动/订单簿结构有关，不能把一次触发直接解释为趋势失败。",
        "- 本阶段因此不再扫描 fail-fast 时间窗，而固定检查 OR15 结构、重新站回入场、连续止损侧收盘这类可实时观察的价格结构。",
        "",
        "## Summary",
        "",
        _md_table(summary, max_rows=5),
        "",
        "## Rule Stats",
        "",
        _md_table(rule_stats, max_rows=10),
        "",
        "## Bucket Stats",
        "",
        _md_table(bucket_stats, max_rows=40),
        "",
        f"## Best Rule Saves: {best_rule_id}",
        "",
        _md_table(best_saves, max_rows=12),
        "",
        f"## Best Rule Harms: {best_rule_id}",
        "",
        _md_table(worst_harms, max_rows=12),
        "",
        "## Atlas",
        "",
        *[f"- atlas：`{path}`" for path in atlas_paths],
        "",
        "## Judgment",
        "",
        "- 本阶段仍然只是 read-only；即使某个结构形状 gross delta 为正，也只能说明它值得进入冻结真实引擎反证，不能直接接官方候选。",
        "- 最佳 S3 全量 gross delta 为正，但 Stage841 事件子集为负且赢家误伤较大；结论应写为“正线索但不晋级”，而不是“已找到可用规则”。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    data = _build_lot_taxonomy()
    rule_stats = _rule_stats(data)
    bucket_stats = _bucket_stats(data)
    summary = _summary(data, rule_stats)
    atlas_paths, atlas_manifest = _plot_atlas(data, rule_stats)

    data.to_csv(LOT_TAXONOMY_PATH, index=False, encoding="utf-8-sig")
    rule_stats.to_csv(RULE_STATS_PATH, index=False, encoding="utf-8-sig")
    bucket_stats.to_csv(BUCKET_STATS_PATH, index=False, encoding="utf-8-sig")
    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    atlas_manifest.to_csv(ATLAS_MANIFEST_PATH, index=False, encoding="utf-8-sig")
    _write_report(summary, rule_stats, bucket_stats, data, atlas_paths)

    best = rule_stats.iloc[0].to_dict() if not rule_stats.empty else {}
    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "source_candidate": stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION,
        "strategy_changed": False,
        "formal_ab_triggered": False,
        "ctp_connected": False,
        "order_api_called": False,
        "decision": summary["decision"].iloc[0] if not summary.empty else "stage842_no_summary",
        "best_rule": best,
        "summary": summary.to_dict("records"),
        "overfit_reflection": (
            "Rules were fixed before running: OR15 adverse break, OR15 adverse close, two stop-side closes, "
            "and no-prior-direction-OR15 adverse break. No year/product/direction/window/R scan was performed."
        ),
        "continue_value": (
            "If a structural rule has positive gross delta with limited killed-winner damage, next step is a frozen full-path engine; "
            "otherwise keep taxonomy only and do not promote."
        ),
        "outputs": {
            "lot_taxonomy": str(LOT_TAXONOMY_PATH),
            "rule_stats": str(RULE_STATS_PATH),
            "bucket_stats": str(BUCKET_STATS_PATH),
            "summary": str(SUMMARY_PATH),
            "atlas_manifest": str(ATLAS_MANIFEST_PATH),
            "atlas_pages": [str(path) for path in atlas_paths],
            "report": str(REPORT_PATH),
            "decision": str(DECISION_PATH),
        },
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print("summary")
    print(summary.to_string(index=False))
    print("rule_stats")
    print(rule_stats.to_string(index=False))


if __name__ == "__main__":
    main()
