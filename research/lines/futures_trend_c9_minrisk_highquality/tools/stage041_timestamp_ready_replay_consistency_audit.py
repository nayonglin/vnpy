from __future__ import annotations

from datetime import datetime
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


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage041"
MODEL_TAG = "stage041_timestamp_ready_replay_consistency_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage041_c9_minrisk_timestamp_ready_replay_consistency_audit"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
TOOL_DIR = SCRIPT_PATH.parent
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
for item in [str(TOOL_DIR), str(EXAMPLE_DIR)]:
    if item not in sys.path:
        sys.path.insert(0, item)

import stage038_order_event_replay_prototype_audit as s038
from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
STAGE040_DIR = LINE_DIR / "outputs" / "stage040_open_proxy_timestamp_reconstruction_audit"
OUTPUT_DIR = LINE_DIR / "outputs" / "stage041_timestamp_ready_replay_consistency_audit"

STAGE040_PROXY_LEDGER_IN = (
    STAGE040_DIR
    / "qmt_roll_stage040_c9_minrisk_open_proxy_timestamp_reconstruction_audit_open_proxy_ledger_"
    "stage040_open_proxy_timestamp_reconstruction_audit_v1.csv"
)

TIMESTAMP_ALIGNMENT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_timestamp_alignment_{MODEL_TAG}.csv"
REPLAY_LEDGER_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_replay_ledger_{MODEL_TAG}.csv"
VARIANT_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_variant_summary_{MODEL_TAG}.csv"
EVENT_CONFUSION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_confusion_{MODEL_TAG}.csv"
SENSITIVITY_CURVE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_same_exit_sensitivity_curve_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_same_exit_path_chart_{MODEL_TAG}.png"
ALIGNMENT_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_timestamp_alignment_chart_{MODEL_TAG}.png"
MATCH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_match_chart_{MODEL_TAG}.png"
ATLAS_MANIFEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_timestamp_replay_atlas_manifest_{MODEL_TAG}.csv"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_timestamp_replay_atlas_page{{page:03d}}_{MODEL_TAG}.png"

CAPITAL = 150_000.0
TRADING_DAYS_PER_YEAR = 252
ATLAS_ROWS = 12
ATLAS_PER_PAGE = 4


VARIANTS = [
    {
        "variant_id": "official_date_first_stage861_open_subset",
        "fill_mode": "official_date_first_stage861_open",
        "description": "Timestamp-ready subset, official open date Stage861 first bar open. This is the Stage038 sensitivity baseline restricted to the ready subset.",
    },
    {
        "variant_id": "official_date_official_open_anchor_subset",
        "fill_mode": "official_date_official_open_anchor",
        "description": "Timestamp-ready subset, official open price but Stage861 official-date scan convention. This is the Stage039 semantic anchor restricted to the ready subset.",
    },
    {
        "variant_id": "raw_timestamp_calendar_day_anchor",
        "fill_mode": "raw_timestamp_calendar_day",
        "description": "Use raw proxy price and start scanning only from the raw timestamp calendar date. Tests whether raw timestamp can stand alone without trading-day stitching.",
    },
    {
        "variant_id": "raw_timestamp_stitched_to_official_date_anchor",
        "fill_mode": "raw_timestamp_stitched_to_official_date",
        "description": "Use raw proxy price and stitch bars from raw timestamp through the official open date. Tests whether a deterministic raw timestamp replay can reproduce official events.",
    },
]


def _json_safe(value: Any) -> Any:
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        if np.isnan(value) or np.isinf(value):
            return None
        return float(value)
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if np.isfinite(result) else default


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    data = frame.copy()
    if max_rows is not None:
        data = data.head(max_rows)
    display = data.copy()
    for column in display.columns:
        if pd.api.types.is_float_dtype(display[column]):
            display[column] = display[column].map(lambda value: "" if pd.isna(value) else f"{value:.4f}")
    headers = [str(column) for column in display.columns]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for _, row in display.iterrows():
        lines.append("| " + " | ".join(str(row[column]) for column in display.columns) + " |")
    return "\n".join(lines)


def _time_text(value: Any) -> str:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return ""
    return pd.Timestamp(ts).strftime("%Y-%m-%dT%H:%M:%S")


def _hhmm(value: Any) -> str:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return ""
    return pd.Timestamp(ts).strftime("%H:%M")


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    equity = pd.to_numeric(equity, errors="coerce").ffill()
    hwm = equity.cummax()
    return (equity / hwm - 1.0) * 100.0


def _curve_metrics(frame: pd.DataFrame, equity_col: str) -> dict[str, float]:
    equity = pd.to_numeric(frame[equity_col], errors="coerce").ffill()
    previous = equity.shift(1)
    previous.iloc[0] = CAPITAL
    returns = (equity / previous - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    std = float(returns.std(ddof=1)) if len(returns) > 1 else 0.0
    return {
        "end_equity": float(equity.iloc[-1]),
        "total_return_pct": float((equity.iloc[-1] / CAPITAL - 1.0) * 100.0),
        "max_drawdown_pct": float(_drawdown_pct(equity).min()),
        "sharpe": float(returns.mean() / std * np.sqrt(TRADING_DAYS_PER_YEAR)) if std > 0 else 0.0,
    }


def _load_ready_ledger() -> pd.DataFrame:
    data = pd.read_csv(STAGE040_PROXY_LEDGER_IN, encoding="utf-8-sig")
    data = data[pd.to_numeric(data["timestamp_ready"], errors="coerce").eq(1)].copy()
    for column in [
        "candidate_date",
        "official_open_date",
        "timestamp_first_time",
        "timestamp_last_time",
        "raw_first_time",
        "raw_last_time",
        "stage861_first_open_time",
    ]:
        if column in data.columns:
            data[f"{column}_ts"] = pd.to_datetime(data[column], errors="coerce")
    for column in [
        "official_open_price",
        "planned_stop_price",
        "official_open_volume",
        "candidate_selected_volume",
        "raw_price",
        "stage861_first_open_price",
    ]:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    return data.reset_index(drop=True)


def _bars_for_symbol(groups: dict[str, pd.DataFrame], vt_symbol: str) -> pd.DataFrame:
    bars = groups.get(str(vt_symbol), pd.DataFrame()).copy()
    if bars.empty:
        return bars
    bars["bar_datetime_ts"] = pd.to_datetime(bars["bar_datetime"], errors="coerce")
    bars["bar_date_ts"] = pd.to_datetime(bars["bar_date"], errors="coerce").dt.normalize()
    return bars.sort_values("bar_datetime_ts").reset_index(drop=True)


def _bars_on_date(bars: pd.DataFrame, day: Any) -> pd.DataFrame:
    norm = s038._normalize_day(day)
    if bars.empty or pd.isna(norm):
        return pd.DataFrame()
    return bars[bars["bar_date_ts"].eq(norm)].copy().sort_values("bar_datetime_ts").reset_index(drop=True)


def _build_timestamp_alignment(ready: pd.DataFrame, groups: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, row in ready.iterrows():
        vt_symbol = str(row["vt_symbol"])
        bars = _bars_for_symbol(groups, vt_symbol)
        timestamp = pd.to_datetime(row.get("timestamp_first_time"), errors="coerce")
        candidate_day = s038._normalize_day(row.get("candidate_date"))
        official_day = s038._normalize_day(row.get("official_open_date"))
        item = row.to_dict()
        item.update(
            {
                "timestamp_bar_ready_any_symbol_date": 0,
                "timestamp_bar_ready_candidate_date": 0,
                "timestamp_bar_ready_official_date": 0,
                "timestamp_alignment_class": "missing_stage861_timestamp_bar",
                "candidate_date_bar_count": 0,
                "official_date_bar_count": 0,
                "stitched_bar_count": 0,
                "timestamp_raw_date": timestamp.normalize().date().isoformat() if pd.notna(timestamp) else "",
            }
        )
        if not bars.empty and pd.notna(timestamp):
            dts = pd.to_datetime(bars["bar_datetime_ts"], errors="coerce")
            item["timestamp_bar_ready_any_symbol_date"] = int(dts.eq(timestamp).any())
            candidate_bars = _bars_on_date(bars, candidate_day)
            official_bars = _bars_on_date(bars, official_day)
            item["candidate_date_bar_count"] = int(len(candidate_bars))
            item["official_date_bar_count"] = int(len(official_bars))
            item["timestamp_bar_ready_candidate_date"] = int(
                not candidate_bars.empty and candidate_bars["bar_datetime_ts"].eq(timestamp).any()
            )
            item["timestamp_bar_ready_official_date"] = int(
                not official_bars.empty and official_bars["bar_datetime_ts"].eq(timestamp).any()
            )
            if item["timestamp_bar_ready_official_date"]:
                item["timestamp_alignment_class"] = "raw_timestamp_in_official_date"
            elif item["timestamp_bar_ready_candidate_date"]:
                item["timestamp_alignment_class"] = "raw_timestamp_in_candidate_date_not_official"
            elif item["timestamp_bar_ready_any_symbol_date"]:
                item["timestamp_alignment_class"] = "raw_timestamp_in_other_bar_date"
            end_time = official_bars["bar_datetime_ts"].max() if not official_bars.empty else pd.NaT
            if pd.notna(end_time):
                stitched = bars[(bars["bar_datetime_ts"].ge(timestamp)) & (bars["bar_datetime_ts"].le(end_time))]
                item["stitched_bar_count"] = int(len(stitched))
        rows.append(item)
    return pd.DataFrame(rows)


def _select_variant_bars(row: pd.Series, groups: dict[str, pd.DataFrame], fill_mode: str) -> tuple[pd.DataFrame, float, str, str]:
    bars = _bars_for_symbol(groups, str(row.get("vt_symbol", "")))
    if bars.empty:
        return pd.DataFrame(), np.nan, "", "missing_stage861_symbol"
    official_day = s038._normalize_day(row.get("official_open_date"))
    timestamp = pd.to_datetime(row.get("timestamp_first_time"), errors="coerce")
    official_day_bars = _bars_on_date(bars, official_day)

    if fill_mode == "official_date_first_stage861_open":
        if official_day_bars.empty:
            return pd.DataFrame(), np.nan, "", "missing_official_date_stage861_bars"
        first = official_day_bars.iloc[0]
        price = _safe_float(first.get("open"))
        if not np.isfinite(price) or price <= 0:
            price = _safe_float(first.get("close"))
        return official_day_bars, price, _time_text(first.get("bar_datetime_ts")), "first_stage861_bar_open"

    if fill_mode == "official_date_official_open_anchor":
        if official_day_bars.empty:
            return pd.DataFrame(), np.nan, "", "missing_official_date_stage861_bars"
        first = official_day_bars.iloc[0]
        return official_day_bars, _safe_float(row.get("official_open_price")), _time_text(first.get("bar_datetime_ts")), "official_open_trade_price_anchor"

    if pd.isna(timestamp):
        return pd.DataFrame(), np.nan, "", "missing_raw_proxy_timestamp"

    if fill_mode == "raw_timestamp_calendar_day":
        raw_day = timestamp.normalize()
        day_bars = _bars_on_date(bars, raw_day)
        start = day_bars[day_bars["bar_datetime_ts"].ge(timestamp)].copy()
        return start, _safe_float(row.get("raw_price")), _time_text(timestamp), "raw_proxy_price_calendar_day_start"

    if fill_mode == "raw_timestamp_stitched_to_official_date":
        if official_day_bars.empty:
            return pd.DataFrame(), np.nan, "", "missing_official_date_stage861_bars"
        if not bars["bar_datetime_ts"].eq(timestamp).any():
            return pd.DataFrame(), _safe_float(row.get("raw_price")), _time_text(timestamp), "raw_proxy_timestamp_not_in_stage861_bars"
        end_time = official_day_bars["bar_datetime_ts"].max()
        stitched = bars[(bars["bar_datetime_ts"].ge(timestamp)) & (bars["bar_datetime_ts"].le(end_time))].copy()
        return stitched, _safe_float(row.get("raw_price")), _time_text(timestamp), "raw_proxy_price_stitched_to_official_date"

    return pd.DataFrame(), np.nan, "", "unknown_fill_mode"


def _event_fields_from_row(row: pd.Series) -> dict[str, Any]:
    return {
        "official_event_family": row.get("official_event_family", "no_intraday_event"),
        "official_exit_reason": row.get("official_exit_reason", ""),
        "official_first_stop_time": _time_text(row.get("official_first_stop_time")),
        "official_reentry_time": _time_text(row.get("official_reentry_time")),
        "official_retry_failed_time": _time_text(row.get("official_retry_failed_time")),
        "official_hit_time": _time_text(row.get("official_hit_time")),
        "official_final_state": row.get("official_final_state", ""),
        "official_final_exit_price": _safe_float(row.get("official_final_exit_price")),
    }


def _replay_one(row: pd.Series, groups: dict[str, pd.DataFrame], variant: dict[str, str]) -> dict[str, Any]:
    fill_mode = str(variant["fill_mode"])
    variant_id = str(variant["variant_id"])
    bars, replay_open, replay_time, price_source = _select_variant_bars(row, groups, fill_mode)
    direction = s038._direction_text(row.get("direction"))
    official_entry = _safe_float(row.get("official_open_price"))
    planned_stop = _safe_float(row.get("planned_stop_price"))
    base = row.to_dict()
    base.update(
        {
            "variant_id": variant_id,
            "fill_mode": fill_mode,
            "stage861_replay_ready": 0,
            "replay_bar_count": 0,
            "replay_open_datetime": replay_time,
            "replay_open_time": _hhmm(replay_time),
            "replay_open_price": replay_open,
            "replay_open_price_source": price_source,
            "replay_open_minus_official": replay_open - official_entry if np.isfinite(replay_open) and np.isfinite(official_entry) else np.nan,
            "replay_open_abs_delta": abs(replay_open - official_entry) if np.isfinite(replay_open) and np.isfinite(official_entry) else np.nan,
            "replay_risk_price": np.nan,
            "replay_c9_stop_price": np.nan,
            "replay_c9_progress_price": np.nan,
            "replay_c2_stop_price": np.nan,
            "replay_c2_confirm_price": np.nan,
            "replay_event_family": "missing_stage861_replay_bars",
            "replay_first_stop_time": "",
            "replay_reentry_time": "",
            "replay_retry_failed_time": "",
            "replay_c2_hit_time": "",
            "event_family_match": 0,
            "first_stop_time_match": 0,
            "reentry_time_match": 0,
            "retry_failed_time_match": 0,
            "c2_hit_time_match": 0,
            **_event_fields_from_row(row),
        }
    )
    if bars.empty:
        base["replay_event_family"] = price_source
        return base

    bars = bars.sort_values("bar_datetime_ts").reset_index(drop=True)
    risk_price = abs(replay_open - planned_stop) if np.isfinite(replay_open) and np.isfinite(planned_stop) else np.nan
    base.update(
        {
            "stage861_replay_ready": 1,
            "replay_bar_count": int(len(bars)),
            "replay_risk_price": risk_price,
            "replay_c2_stop_price": planned_stop,
            "replay_c2_confirm_price": replay_open + s038._direction_sign(direction) * risk_price
            if np.isfinite(risk_price)
            else np.nan,
        }
    )
    min_risk = max(1e-9, abs(replay_open) * 1e-12)
    if not np.isfinite(risk_price) or risk_price < min_risk:
        base["replay_event_family"] = "invalid_replay_risk"
        return base

    c9 = s038._first_c9_stop_or_progress(bars, entry_price=replay_open, risk_price=risk_price, direction=direction)
    base.update(
        {
            "replay_c9_stop_price": c9["stop_price"],
            "replay_c9_progress_price": c9["progress_price"],
        }
    )
    if c9["event"] == "stop":
        retry = s038._reentry_after_stop(
            bars,
            direction=direction,
            entry_price=replay_open,
            stop_price=float(c9["stop_price"]),
            stop_idx=int(c9["idx"]),
        )
        family = "c9_flat_no_reentry"
        if int(retry["reentry_idx"]) >= 0:
            family = "c9_open_after_reentry"
            if int(retry["retry_failed_idx"]) >= 0:
                family = "c9_flat_retry_failed"
        base.update(
            {
                "replay_event_family": family,
                "replay_first_stop_time": str(c9["time"]),
                "replay_reentry_time": str(retry["reentry_time"]),
                "replay_retry_failed_time": str(retry["retry_failed_time"]),
                "replay_same_bar_progress": int(c9.get("same_bar_progress", 0)),
            }
        )
    else:
        c2 = s038._first_c2_stop_or_confirm(
            bars,
            entry_price=replay_open,
            stop_price=planned_stop,
            risk_price=risk_price,
            direction=direction,
        )
        if c2["event"] == "c2_stop":
            family = "c2_stop"
            hit_time = str(c2["time"])
        else:
            family = "open_no_intraday_event"
            hit_time = ""
        base.update(
            {
                "replay_event_family": family,
                "replay_c2_hit_time": hit_time,
                "replay_c2_same_bar_confirm": int(c2.get("same_bar_confirm", 0)),
            }
        )

    official_family = str(base.get("official_event_family", "no_intraday_event"))
    replay_family = str(base.get("replay_event_family", ""))
    base["event_family_match"] = int(
        (official_family == "no_intraday_event" and replay_family == "open_no_intraday_event")
        or official_family == replay_family
    )
    base["first_stop_time_match"] = int(
        bool(base.get("official_first_stop_time")) and base.get("official_first_stop_time") == base.get("replay_first_stop_time")
    )
    base["reentry_time_match"] = int(
        bool(base.get("official_reentry_time")) and base.get("official_reentry_time") == base.get("replay_reentry_time")
    )
    base["retry_failed_time_match"] = int(
        bool(base.get("official_retry_failed_time"))
        and base.get("official_retry_failed_time") == base.get("replay_retry_failed_time")
    )
    base["c2_hit_time_match"] = int(
        bool(base.get("official_hit_time")) and base.get("official_hit_time") == base.get("replay_c2_hit_time")
    )
    return base


def _build_replay(ready: pd.DataFrame, groups: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for variant in VARIANTS:
        for _, row in ready.iterrows():
            rows.append(_replay_one(row, groups, variant))
    replay = pd.DataFrame(rows)
    for column in [
        "official_open_price",
        "official_open_volume",
        "candidate_selected_volume",
        "replay_open_price",
        "replay_open_minus_official",
        "replay_open_abs_delta",
        "replay_risk_price",
        "event_family_match",
        "first_stop_time_match",
        "reentry_time_match",
        "retry_failed_time_match",
        "c2_hit_time_match",
        "stage861_replay_ready",
    ]:
        if column in replay.columns:
            replay[column] = pd.to_numeric(replay[column], errors="coerce")
    return replay


def _event_confusion(replay: pd.DataFrame) -> pd.DataFrame:
    data = replay.copy()
    data["official_event_family"] = data["official_event_family"].fillna("no_intraday_event")
    data["replay_event_family"] = data["replay_event_family"].fillna("missing")
    return (
        data.groupby(["variant_id", "official_event_family", "replay_event_family"], dropna=False)
        .agg(
            orders=("candidate_index", "count"),
            replay_ready=("stage861_replay_ready", "sum"),
            abs_price_delta_median=("replay_open_abs_delta", "median"),
            event_family_match=("event_family_match", "sum"),
            first_stop_time_match=("first_stop_time_match", "sum"),
            reentry_time_match=("reentry_time_match", "sum"),
            retry_failed_time_match=("retry_failed_time_match", "sum"),
            c2_hit_time_match=("c2_hit_time_match", "sum"),
        )
        .reset_index()
        .sort_values(["variant_id", "official_event_family", "orders"], ascending=[True, True, False])
    )


def _variant_summary(replay: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for variant in VARIANTS:
        variant_id = str(variant["variant_id"])
        data = replay[replay["variant_id"].eq(variant_id)].copy()
        ready = data[pd.to_numeric(data["stage861_replay_ready"], errors="coerce").eq(1)].copy()
        rows.append(
            {
                "variant_id": variant_id,
                "fill_mode": variant["fill_mode"],
                "description": variant["description"],
                "timestamp_ready_orders": int(len(data)),
                "stage861_replay_ready_orders": int(len(ready)),
                "missing_replay_orders": int(len(data) - len(ready)),
                "median_replay_open_abs_delta": float(pd.to_numeric(ready["replay_open_abs_delta"], errors="coerce").median())
                if len(ready)
                else np.nan,
                "p90_replay_open_abs_delta": float(pd.to_numeric(ready["replay_open_abs_delta"], errors="coerce").quantile(0.9))
                if len(ready)
                else np.nan,
                "max_replay_open_abs_delta": float(pd.to_numeric(ready["replay_open_abs_delta"], errors="coerce").max())
                if len(ready)
                else np.nan,
                "event_family_match_rate_pct": float(pd.to_numeric(ready["event_family_match"], errors="coerce").fillna(0).mean() * 100.0)
                if len(ready)
                else 0.0,
                "event_family_mismatch_orders": int(pd.to_numeric(ready["event_family_match"], errors="coerce").fillna(0).eq(0).sum()),
                "first_stop_time_match_count": int(pd.to_numeric(ready.get("first_stop_time_match", 0), errors="coerce").fillna(0).sum()),
                "reentry_time_match_count": int(pd.to_numeric(ready.get("reentry_time_match", 0), errors="coerce").fillna(0).sum()),
                "retry_failed_time_match_count": int(pd.to_numeric(ready.get("retry_failed_time_match", 0), errors="coerce").fillna(0).sum()),
                "c2_hit_time_match_count": int(pd.to_numeric(ready.get("c2_hit_time_match", 0), errors="coerce").fillna(0).sum()),
            }
        )
    return pd.DataFrame(rows)


def _variant_lot_sensitivity(lots: pd.DataFrame, replay: pd.DataFrame) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for variant in VARIANTS:
        variant_id = str(variant["variant_id"])
        subset = replay[replay["variant_id"].eq(variant_id)].copy()
        sensitivity = s038._closed_lot_sensitivity(lots, subset)
        sensitivity["variant_id"] = variant_id
        frames.append(sensitivity)
    return pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()


def _same_exit_curve(curve: pd.DataFrame, lot_sensitivity: pd.DataFrame) -> pd.DataFrame:
    out = curve[["date", "account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]].copy()
    for variant in VARIANTS:
        variant_id = str(variant["variant_id"])
        lots = lot_sensitivity[lot_sensitivity["variant_id"].eq(variant_id)].copy()
        lots["exit_date_ts"] = pd.to_datetime(lots["exit_date_ts"], errors="coerce").dt.normalize()
        delta = pd.to_numeric(lots["entry_price_delta_pnl_same_exit"], errors="coerce").fillna(0.0)
        daily_delta = delta.groupby(lots["exit_date_ts"]).sum()
        safe = variant_id.replace("-", "_")
        out[f"{safe}_delta"] = out["date"].map(daily_delta).fillna(0.0)
        out[f"{safe}_cum_delta"] = out[f"{safe}_delta"].cumsum()
        out[f"{safe}_equity"] = out["account_equity"] + out[f"{safe}_cum_delta"]
        out[f"{safe}_drawdown_pct"] = _drawdown_pct(out[f"{safe}_equity"])
    return out


def _summary(
    curve: pd.DataFrame,
    lots: pd.DataFrame,
    ready: pd.DataFrame,
    alignment: pd.DataFrame,
    variant_summary: pd.DataFrame,
    sensitivity_curve: pd.DataFrame,
) -> pd.DataFrame:
    official = s038._official_metrics(curve, lots)
    raw_stitched = variant_summary[
        variant_summary["variant_id"].eq("raw_timestamp_stitched_to_official_date_anchor")
    ].iloc[0]
    official_anchor = variant_summary[
        variant_summary["variant_id"].eq("official_date_official_open_anchor_subset")
    ].iloc[0]
    first_stage861 = variant_summary[
        variant_summary["variant_id"].eq("official_date_first_stage861_open_subset")
    ].iloc[0]
    first_metrics = _curve_metrics(sensitivity_curve, "official_date_first_stage861_open_subset_equity")
    raw_metrics = _curve_metrics(sensitivity_curve, "raw_timestamp_stitched_to_official_date_anchor_equity")
    return pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "line_id": LINE_ID,
                "official_live_version": OFFICIAL_LIVE_VERSION,
                "official_live_alias": OFFICIAL_LIVE_ALIAS,
                **official,
                "timestamp_ready_orders": int(len(ready)),
                "raw_timestamp_in_official_date_orders": int(
                    alignment["timestamp_alignment_class"].eq("raw_timestamp_in_official_date").sum()
                ),
                "raw_timestamp_in_candidate_date_not_official_orders": int(
                    alignment["timestamp_alignment_class"].eq("raw_timestamp_in_candidate_date_not_official").sum()
                ),
                "raw_timestamp_missing_stage861_timestamp_orders": int(
                    alignment["timestamp_alignment_class"].eq("missing_stage861_timestamp_bar").sum()
                ),
                "official_anchor_subset_event_match_rate_pct": float(official_anchor["event_family_match_rate_pct"]),
                "official_anchor_subset_mismatch_orders": int(official_anchor["event_family_mismatch_orders"]),
                "first_stage861_subset_event_match_rate_pct": float(first_stage861["event_family_match_rate_pct"]),
                "first_stage861_subset_mismatch_orders": int(first_stage861["event_family_mismatch_orders"]),
                "raw_stitched_replay_ready_orders": int(raw_stitched["stage861_replay_ready_orders"]),
                "raw_stitched_event_match_rate_pct": float(raw_stitched["event_family_match_rate_pct"]),
                "raw_stitched_mismatch_orders": int(raw_stitched["event_family_mismatch_orders"]),
                "first_stage861_same_exit_end_equity": first_metrics["end_equity"],
                "first_stage861_same_exit_max_drawdown_pct": first_metrics["max_drawdown_pct"],
                "raw_stitched_same_exit_end_equity": raw_metrics["end_equity"],
                "raw_stitched_same_exit_max_drawdown_pct": raw_metrics["max_drawdown_pct"],
                "decision": "stage041_timestamp_ready_replay_convention_not_yet_trade_rule",
                "candidate_ready": 0,
                "ab_triggered": 0,
            }
        ]
    )


def _plot_path(curve: pd.DataFrame) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(16, 12), sharex=True, constrained_layout=True)
    axes[0].plot(curve["date"], curve["account_equity"], color="#111827", linewidth=1.2, label="official equity")
    for variant_id, color, label, style in [
        ("official_date_first_stage861_open_subset", "#dc2626", "timestamp-ready first Stage861 open", "-"),
        ("official_date_official_open_anchor_subset", "#16a34a", "timestamp-ready official open anchor", "--"),
        ("raw_timestamp_stitched_to_official_date_anchor", "#2563eb", "raw timestamp stitched anchor", ":"),
    ]:
        axes[0].plot(curve["date"], curve[f"{variant_id}_equity"], color=color, linewidth=1.0, linestyle=style, label=label)
    axes[0].set_title("Same-exit sensitivity on timestamp-ready initial orders")
    axes[0].grid(True, alpha=0.25)
    axes[0].legend(loc="best")

    axes[1].plot(curve["date"], curve["drawdown_pct"], color="#111827", linewidth=1.0, label="official DD")
    for variant_id, color, label, style in [
        ("official_date_first_stage861_open_subset", "#dc2626", "first Stage861 subset DD", "-"),
        ("raw_timestamp_stitched_to_official_date_anchor", "#2563eb", "raw stitched subset DD", ":"),
    ]:
        axes[1].plot(curve["date"], curve[f"{variant_id}_drawdown_pct"], color=color, linewidth=1.0, linestyle=style, label=label)
    axes[1].set_title("Drawdown sensitivity, audit only")
    axes[1].grid(True, alpha=0.25)
    axes[1].legend(loc="best")

    for variant_id, color, label, style in [
        ("official_date_first_stage861_open_subset", "#dc2626", "cum delta: first Stage861 subset", "-"),
        ("official_date_official_open_anchor_subset", "#16a34a", "cum delta: official anchor subset", "--"),
        ("raw_timestamp_stitched_to_official_date_anchor", "#2563eb", "cum delta: raw stitched subset", ":"),
    ]:
        axes[2].plot(curve["date"], curve[f"{variant_id}_cum_delta"], color=color, linewidth=1.0, linestyle=style, label=label)
    axes[2].axhline(0, color="#6b7280", linewidth=0.8)
    axes[2].set_title("Cumulative same-exit PnL delta from fill anchor")
    axes[2].grid(True, alpha=0.25)
    axes[2].legend(loc="best")
    fig.suptitle("Stage041 timestamp-ready replay consistency audit", fontsize=14)
    fig.savefig(PATH_CHART_OUT, dpi=150)
    plt.close(fig)


def _plot_alignment(alignment: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(14, 9), constrained_layout=True)
    counts = (
        alignment.groupby(["raw_source", "timestamp_alignment_class"], dropna=False)
        .size()
        .reset_index(name="orders")
        .pivot_table(index="raw_source", columns="timestamp_alignment_class", values="orders", aggfunc="sum", fill_value=0)
    )
    colors = {
        "raw_timestamp_in_official_date": "#16a34a",
        "raw_timestamp_in_candidate_date_not_official": "#f59e0b",
        "missing_stage861_timestamp_bar": "#dc2626",
        "raw_timestamp_in_other_bar_date": "#64748b",
    }
    x = np.arange(len(counts))
    bottom = np.zeros(len(counts))
    for column in counts.columns:
        values = counts[column].to_numpy()
        axes[0].bar(x, values, bottom=bottom, color=colors.get(column, "#64748b"), label=column)
        bottom += values
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(counts.index, rotation=0)
    axes[0].set_ylabel("orders")
    axes[0].set_title("Raw proxy timestamp alignment with Stage861 bar dates")
    axes[0].grid(True, axis="y", alpha=0.25)
    axes[0].legend(loc="best", fontsize=8)

    yearly = (
        alignment.groupby(["open_year", "timestamp_alignment_class"], dropna=False)
        .size()
        .reset_index(name="orders")
        .pivot_table(index="open_year", columns="timestamp_alignment_class", values="orders", aggfunc="sum", fill_value=0)
        .sort_index()
    )
    x2 = np.arange(len(yearly))
    bottom = np.zeros(len(yearly))
    for column in yearly.columns:
        values = yearly[column].to_numpy()
        axes[1].bar(x2, values, bottom=bottom, color=colors.get(column, "#64748b"), label=column)
        bottom += values
    axes[1].set_xticks(x2)
    axes[1].set_xticklabels([str(int(item)) for item in yearly.index], rotation=0)
    axes[1].set_ylabel("orders")
    axes[1].set_title("Timestamp convention coverage by year")
    axes[1].grid(True, axis="y", alpha=0.25)
    axes[1].legend(loc="best", fontsize=8)
    fig.savefig(ALIGNMENT_CHART_OUT, dpi=150)
    plt.close(fig)


def _plot_match(variant_summary: pd.DataFrame) -> None:
    data = variant_summary.copy()
    fig, axes = plt.subplots(2, 1, figsize=(14, 9), constrained_layout=True)
    x = np.arange(len(data))
    axes[0].bar(x, data["event_family_match_rate_pct"], color="#2563eb")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(data["variant_id"], rotation=12, ha="right", fontsize=8)
    axes[0].set_ylabel("event match %")
    axes[0].set_ylim(0, 105)
    axes[0].set_title("Event family match rate by replay fill convention")
    axes[0].grid(True, axis="y", alpha=0.25)
    for idx, value in enumerate(data["event_family_match_rate_pct"]):
        axes[0].text(idx, value + 1, f"{value:.1f}%", ha="center", fontsize=8)

    width = 0.35
    axes[1].bar(x - width / 2, data["stage861_replay_ready_orders"], width=width, color="#16a34a", label="replay ready")
    axes[1].bar(x + width / 2, data["event_family_mismatch_orders"], width=width, color="#dc2626", label="event mismatch")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(data["variant_id"], rotation=12, ha="right", fontsize=8)
    axes[1].set_ylabel("orders")
    axes[1].set_title("Ready and mismatch counts")
    axes[1].grid(True, axis="y", alpha=0.25)
    axes[1].legend(loc="best")
    fig.savefig(MATCH_CHART_OUT, dpi=150)
    plt.close(fig)


def _select_atlas_rows(replay: pd.DataFrame) -> pd.DataFrame:
    stitched = replay[replay["variant_id"].eq("raw_timestamp_stitched_to_official_date_anchor")].copy()
    stitched["event_family_match"] = pd.to_numeric(stitched["event_family_match"], errors="coerce").fillna(0)
    stitched["stage861_replay_ready"] = pd.to_numeric(stitched["stage861_replay_ready"], errors="coerce").fillna(0)
    mismatch = stitched[stitched["stage861_replay_ready"].eq(1) & stitched["event_family_match"].eq(0)].copy()
    missing = stitched[stitched["stage861_replay_ready"].eq(0)].copy()
    parts: list[pd.DataFrame] = []
    if not mismatch.empty:
        parts.append(mismatch.sort_values(["official_event_family", "official_open_date"]).head(ATLAS_ROWS // 2))
    if not missing.empty:
        parts.append(missing.sort_values(["raw_source", "official_open_date"]).head(ATLAS_ROWS // 2))
    if not parts:
        parts.append(stitched.head(ATLAS_ROWS))
    return pd.concat(parts, ignore_index=True, sort=False).drop_duplicates("candidate_index").head(ATLAS_ROWS).reset_index(drop=True)


def _variant_bars_for_plot(row: pd.Series, groups: dict[str, pd.DataFrame]) -> pd.DataFrame:
    bars, _price, _time, _source = _select_variant_bars(row, groups, "raw_timestamp_stitched_to_official_date")
    if bars.empty:
        official_bars = _bars_on_date(_bars_for_symbol(groups, str(row.get("vt_symbol", ""))), row.get("official_open_date"))
        return official_bars
    return bars


def _plot_atlas(replay: pd.DataFrame, groups: dict[str, pd.DataFrame]) -> tuple[list[Path], pd.DataFrame]:
    selected = _select_atlas_rows(replay)
    if selected.empty:
        _write_csv(pd.DataFrame(), ATLAS_MANIFEST_OUT)
        return [], pd.DataFrame()
    pages: list[Path] = []
    manifest_rows: list[dict[str, Any]] = []
    for page_idx, start in enumerate(range(0, len(selected), ATLAS_PER_PAGE), start=1):
        page_rows = selected.iloc[start : start + ATLAS_PER_PAGE].reset_index(drop=True)
        fig, axes = plt.subplots(len(page_rows), 1, figsize=(14, 3.6 * len(page_rows)), sharex=False, constrained_layout=True)
        if len(page_rows) == 1:
            axes = [axes]
        for ax, (_, row) in zip(axes, page_rows.iterrows()):
            bars = _variant_bars_for_plot(row, groups)
            if bars.empty:
                ax.text(0.5, 0.5, "missing Stage861 bars", ha="center", va="center")
                ax.set_axis_off()
            else:
                bars = bars.sort_values("bar_datetime_ts").reset_index(drop=True)
                x = np.arange(len(bars))
                ax.plot(x, pd.to_numeric(bars["close"], errors="coerce"), color="#2563eb", linewidth=0.9, label="Stage861 close")
                for column, color, label, style in [
                    ("official_open_price", "#111827", "official open", "--"),
                    ("raw_price", "#16a34a", "raw proxy", "-."),
                    ("planned_stop_price", "#dc2626", "planned stop", ":"),
                    ("replay_c9_stop_price", "#f97316", "replay C9 stop", ":"),
                    ("replay_c9_progress_price", "#22c55e", "replay C9 progress", ":"),
                ]:
                    value = _safe_float(row.get(column))
                    if np.isfinite(value):
                        ax.axhline(value, color=color, linewidth=0.8, linestyle=style, label=label)
                for column, color, label in [
                    ("timestamp_first_time", "#16a34a", "raw timestamp"),
                    ("stage861_first_open_time", "#7c3aed", "official-date first bar"),
                    ("official_first_stop_time", "#f97316", "official first stop"),
                    ("replay_first_stop_time", "#dc2626", "replay first stop"),
                    ("official_hit_time", "#0f766e", "official C2 hit"),
                    ("replay_c2_hit_time", "#0891b2", "replay C2 hit"),
                ]:
                    text = str(row.get(column, ""))
                    if not text or text == "nan":
                        continue
                    ts = pd.to_datetime(text, errors="coerce")
                    if pd.isna(ts):
                        continue
                    matches = np.flatnonzero(pd.to_datetime(bars["bar_datetime_ts"], errors="coerce").eq(ts).to_numpy())
                    if len(matches):
                        ax.axvline(int(matches[0]), color=color, linewidth=0.8, alpha=0.75, label=label)
                tick_positions = np.linspace(0, max(len(bars) - 1, 0), num=min(6, len(bars)), dtype=int)
                ax.set_xticks(tick_positions)
                ax.set_xticklabels([_hhmm(bars.loc[pos, "bar_datetime_ts"]) for pos in tick_positions], fontsize=8)
                ax.grid(True, alpha=0.25)
            title = (
                f"{row.get('official_open_trade_id')} {row.get('vt_symbol')} {row.get('official_open_date')} "
                f"{row.get('direction')} align={row.get('timestamp_alignment_class')} "
                f"official={row.get('official_event_family')} replay={row.get('replay_event_family')}"
            )
            ax.set_title(title, fontsize=9)
            handles, labels = ax.get_legend_handles_labels()
            if handles:
                by_label = dict(zip(labels, handles))
                ax.legend(by_label.values(), by_label.keys(), loc="best", fontsize=7)
            manifest_rows.append(
                {
                    "page": page_idx,
                    "candidate_index": row.get("candidate_index"),
                    "official_open_trade_id": row.get("official_open_trade_id"),
                    "vt_symbol": row.get("vt_symbol"),
                    "official_open_date": row.get("official_open_date"),
                    "raw_source": row.get("raw_source"),
                    "timestamp_alignment_class": row.get("timestamp_alignment_class"),
                    "official_event_family": row.get("official_event_family"),
                    "replay_event_family": row.get("replay_event_family"),
                    "event_family_match": row.get("event_family_match"),
                    "timestamp_first_time": row.get("timestamp_first_time"),
                    "replay_open_datetime": row.get("replay_open_datetime"),
                    "replay_open_price": row.get("replay_open_price"),
                }
            )
        output = Path(str(ATLAS_TEMPLATE).format(page=page_idx))
        fig.savefig(output, dpi=150)
        plt.close(fig)
        pages.append(output)
    manifest = pd.DataFrame(manifest_rows)
    _write_csv(manifest, ATLAS_MANIFEST_OUT)
    return pages, manifest


def _write_report(
    summary: pd.DataFrame,
    alignment: pd.DataFrame,
    variant_summary: pd.DataFrame,
    confusion: pd.DataFrame,
    atlas_paths: list[Path],
) -> None:
    row = summary.iloc[0].to_dict()
    alignment_summary = (
        alignment.groupby(["raw_source", "timestamp_alignment_class"], dropna=False)
        .agg(orders=("candidate_index", "count"), stitched_bar_count_median=("stitched_bar_count", "median"))
        .reset_index()
        .sort_values(["raw_source", "orders"], ascending=[True, False])
    )
    lines = [
        "# Stage041 timestamp-ready replay 一致性审计",
        "",
        "## 结论",
        "",
        "- 决策：`stage041_timestamp_ready_replay_convention_not_yet_trade_rule`。",
        "- 本阶段只做 Stage040 `timestamp_ready=1` 子集的 replay convention 审计，不新增交易规则、不改正式配置、不连接 CTP、不调用订单 API、不触发 A/B。",
        f"- timestamp-ready initial orders `{int(row['timestamp_ready_orders'])}`；raw timestamp 在 official date 内 `{int(row['raw_timestamp_in_official_date_orders'])}` 笔，在 candidate date 但不在 official date 内 `{int(row['raw_timestamp_in_candidate_date_not_official_orders'])}` 笔，Stage861 找不到 raw timestamp `{int(row['raw_timestamp_missing_stage861_timestamp_orders'])}` 笔。",
        f"- official-date official-open anchor 子集 event match `{row['official_anchor_subset_event_match_rate_pct']:.4f}%`，mismatch `{int(row['official_anchor_subset_mismatch_orders'])}`。",
        f"- raw timestamp stitched replay ready `{int(row['raw_stitched_replay_ready_orders'])}`，event match `{row['raw_stitched_event_match_rate_pct']:.4f}%`，mismatch `{int(row['raw_stitched_mismatch_orders'])}`。",
        "- 判断：Stage040 证明 raw proxy 能解释成交价，但 Stage041 证明 timestamp convention 仍未统一，尤其夜盘 raw timestamp 与 official-date Stage861 replay day 不在同一日分组。不能直接把 raw timestamp anchor 当成可交易分钟规则底座。",
        "",
        "## 官方基准",
        "",
        f"- 期末权益：`{row['end_equity']:.2f}`",
        f"- 总收益：`{row['total_return_pct']:.4f}%`",
        f"- 最大回撤：`{row['max_drawdown_pct']:.4f}%`",
        f"- Sharpe：`{row['sharpe']:.4f}`",
        f"- 总滑点：`{row['total_slippage']:.0f}`",
        f"- 总交易次数：`{row['total_trade_count']:.0f}`",
        f"- closed-lot 胜率：`{row['closed_lot_win_rate_pct']:.4f}%`",
        "",
        "## 外部调研与判断",
        "",
        "- Backtrader 文档说明 market order 在回测里按下一 bar open 成交；QuantConnect 文档强调 Time Frontier 之前的数据才可见以避免 look-ahead；NautilusTrader 把 fill model 作为回测成交模拟核心。",
        "- 本阶段判断：只有成交价格、成交时间、bar timestamp convention 三者同时前向一致，replay 账本才可用于分钟级规则测试。现在价格可解释，但夜盘 timestamp 与 official-date event replay convention 仍冲突。",
        "",
        "## Timestamp Alignment",
        "",
        _md_table(alignment_summary, max_rows=None),
        "",
        "## Variant Summary",
        "",
        _md_table(variant_summary, max_rows=None),
        "",
        "## Event Confusion",
        "",
        _md_table(confusion, max_rows=60),
        "",
        "## Visuals",
        "",
        f"- same-exit path chart：`{PATH_CHART_OUT}`",
        f"- timestamp alignment chart：`{ALIGNMENT_CHART_OUT}`",
        f"- event match chart：`{MATCH_CHART_OUT}`",
        *[f"- timestamp replay atlas：`{path}`" for path in atlas_paths],
        "",
        "## Files",
        "",
        f"- timestamp alignment：`{TIMESTAMP_ALIGNMENT_OUT}`",
        f"- replay ledger：`{REPLAY_LEDGER_OUT}`",
        f"- variant summary：`{VARIANT_SUMMARY_OUT}`",
        f"- event confusion：`{EVENT_CONFUSION_OUT}`",
        f"- sensitivity curve：`{SENSITIVITY_CURVE_OUT}`",
        f"- summary：`{SUMMARY_OUT}`",
        f"- decision：`{DECISION_OUT}`",
        "",
        "## 视觉观察",
        "",
        "- alignment chart 显示 day proxy 的 `64` 笔全部落在 official date `09:00` 窗口，而 night proxy 的多数样本落在 candidate date `21:00`，不是 official date。",
        "- same-exit path chart 中 raw/official anchor 的资金曲线与官方基本重合，是因为 raw proxy 价格等于 official open price；这只能证明价格锚点，不证明事件时间轴已可交易化。",
        "- atlas 中 raw stitched replay 的 mismatch 多来自把 night timestamp 纳入扫描后，事件顺序与 official intraday diagnostics 的日期口径不同；这属于账本 convention 问题，不是信号质量。",
        "",
        "## 后续",
        "",
        "- 下一步不要写新开仓/恢复/降仓规则；先建立 trading-day stitched minute ledger：把 candidate date 夜盘、official date 日盘、bar timestamp 和 official intraday diagnostics 的事件时间统一到同一 trading session。",
        "- 如果不能统一 session convention，则只能把 raw proxy timestamp 用作成交价来源解释，不能把它作为分钟事件 replay 起点。",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curve, _open_trades, _candidates, lots, _intraday, _trades = s038._prepare_inputs()
    ready = _load_ready_ledger()
    groups = s038._load_minute_groups(ready)
    alignment = _build_timestamp_alignment(ready, groups)
    replay_input = ready.drop(
        columns=[col for col in alignment.columns if col in ready.columns and col.startswith("timestamp_bar_ready_")],
        errors="ignore",
    ).merge(
        alignment[
            [
                "candidate_index",
                "timestamp_alignment_class",
                "timestamp_bar_ready_any_symbol_date",
                "timestamp_bar_ready_candidate_date",
                "timestamp_bar_ready_official_date",
                "candidate_date_bar_count",
                "official_date_bar_count",
                "stitched_bar_count",
            ]
        ],
        on="candidate_index",
        how="left",
    )
    replay = _build_replay(replay_input, groups)
    confusion = _event_confusion(replay)
    variant_summary = _variant_summary(replay)
    lot_sensitivity = _variant_lot_sensitivity(lots, replay)
    sensitivity_curve = _same_exit_curve(curve, lot_sensitivity)
    summary = _summary(curve, lots, ready, alignment, variant_summary, sensitivity_curve)

    _write_csv(alignment, TIMESTAMP_ALIGNMENT_OUT)
    _write_csv(replay, REPLAY_LEDGER_OUT)
    _write_csv(variant_summary, VARIANT_SUMMARY_OUT)
    _write_csv(confusion, EVENT_CONFUSION_OUT)
    _write_csv(sensitivity_curve, SENSITIVITY_CURVE_OUT)
    _write_csv(summary, SUMMARY_OUT)

    _plot_path(sensitivity_curve)
    _plot_alignment(alignment)
    _plot_match(variant_summary)
    atlas_paths, _manifest = _plot_atlas(replay, groups)
    _write_report(summary, alignment, variant_summary, confusion, atlas_paths)

    row = summary.iloc[0].to_dict()
    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "decision": row["decision"],
        "candidate_ready": 0,
        "ab_triggered": 0,
        "rule_added": 0,
        "official_config_changed": 0,
        "timestamp_ready_orders": int(row["timestamp_ready_orders"]),
        "raw_timestamp_in_official_date_orders": int(row["raw_timestamp_in_official_date_orders"]),
        "raw_timestamp_in_candidate_date_not_official_orders": int(row["raw_timestamp_in_candidate_date_not_official_orders"]),
        "raw_timestamp_missing_stage861_timestamp_orders": int(row["raw_timestamp_missing_stage861_timestamp_orders"]),
        "official_anchor_subset_event_match_rate_pct": float(row["official_anchor_subset_event_match_rate_pct"]),
        "raw_stitched_replay_ready_orders": int(row["raw_stitched_replay_ready_orders"]),
        "raw_stitched_event_match_rate_pct": float(row["raw_stitched_event_match_rate_pct"]),
        "raw_stitched_mismatch_orders": int(row["raw_stitched_mismatch_orders"]),
        "judgment": (
            "Stage040 timestamp-ready prices are useful, but Stage041 finds unresolved timestamp convention risk: "
            "night-session raw timestamps usually live on candidate_date while official replay diagnostics are keyed by official_open_date."
        ),
        "overfit_guard": (
            "No timestamp alignment class is promoted as a trading filter. Alignment only defines replay data usability."
        ),
        "next_step": (
            "Build a trading-day stitched minute ledger before any raw timestamp anchored minute-entry/exit rule is tested."
        ),
        "outputs": {
            "timestamp_alignment": TIMESTAMP_ALIGNMENT_OUT,
            "replay_ledger": REPLAY_LEDGER_OUT,
            "variant_summary": VARIANT_SUMMARY_OUT,
            "event_confusion": EVENT_CONFUSION_OUT,
            "sensitivity_curve": SENSITIVITY_CURVE_OUT,
            "summary": SUMMARY_OUT,
            "report": REPORT_OUT,
            "decision": DECISION_OUT,
            "path_chart": PATH_CHART_OUT,
            "alignment_chart": ALIGNMENT_CHART_OUT,
            "match_chart": MATCH_CHART_OUT,
            "atlas_manifest": ATLAS_MANIFEST_OUT,
            "atlas_pages": atlas_paths,
        },
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
