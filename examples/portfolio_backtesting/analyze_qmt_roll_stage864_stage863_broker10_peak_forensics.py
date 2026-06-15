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

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage825_stage819_intraday_rule_forensics as s825
import analyze_qmt_roll_stage861_stage860_full_visual_atlas as s861
import qmt_roll_official_candidate_stage819_30w_config as stage819_cfg


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage864"
MODEL_TAG = "stage864_stage863_broker10_peak_forensics_v1"
OUTPUT_PREFIX = "qmt_roll_stage864_stage863_broker10_peak_forensics"

STAGE863_PREFIX = "qmt_roll_stage863_stage847_c10_budget_lock_engine"
STAGE863_TAG = "stage863_stage847_c10_budget_lock_engine_v1"
C4_ARM = "stage830_stage819_c2_broker10_100_cap"
C9_ARM = "stage847_stage819_c4_05r_stop_retry_once"

BROKER_MARGIN_MULTIPLIER = 1.65
TOP_PEAK_DATES_PER_ARM = 5
STOP_RETRY_LOOKBACK_DAYS = 90
PER_PAGE = 4
MAX_ATLAS_ROWS = 16

CURVE_IN = OUTPUT_DIR / f"{STAGE863_PREFIX}_curve_{STAGE863_TAG}.csv"
CLOSED_LOTS_IN = OUTPUT_DIR / f"{STAGE863_PREFIX}_closed_lots_{STAGE863_TAG}.csv"
TRADES_IN = OUTPUT_DIR / f"{STAGE863_PREFIX}_trades_{STAGE863_TAG}.csv"
ENTRY_RISK_IN = OUTPUT_DIR / f"{STAGE863_PREFIX}_entry_risk_{STAGE863_TAG}.csv"
STOP_RETRY_IN = OUTPUT_DIR / f"{STAGE863_PREFIX}_stop_retry_events_{STAGE863_TAG}.csv"
DECISION_IN = OUTPUT_DIR / f"{STAGE863_PREFIX}_decision_{STAGE863_TAG}.json"

PEAK_DATES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_peak_dates_{MODEL_TAG}.csv"
ACTIVE_LOTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_active_lots_{MODEL_TAG}.csv"
PRODUCT_DIRECTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_direction_attribution_{MODEL_TAG}.csv"
PAIR_DELTA_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_pair_delta_{MODEL_TAG}.csv"
ENTRY_SIZING_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_sizing_context_{MODEL_TAG}.csv"
STOP_RETRY_WINDOW_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stop_retry_before_peak_{MODEL_TAG}.csv"
ATLAS_MANIFEST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_page{{page:03d}}_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if np.isfinite(number) else default


def _load_required_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _normalize_date(value: Any) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    if ts.tzinfo is not None:
        ts = ts.tz_localize(None)
    return ts.normalize()


def _load_full_minute_bars(vt_symbols: set[str]) -> pd.DataFrame:
    if s861.FULL_MINUTE_BARS_PATH.exists():
        data = pd.read_csv(s861.FULL_MINUTE_BARS_PATH, encoding="utf-8-sig")
    else:
        data = s861._load_full_minute_bars(vt_symbols)
    data = data[data["vt_symbol"].astype(str).isin(vt_symbols)].copy()
    data["bar_datetime"] = pd.to_datetime(data["bar_datetime"], errors="coerce")
    if "bar_date" not in data.columns:
        data["bar_date"] = data["bar_datetime"].dt.normalize()
    else:
        data["bar_date"] = pd.to_datetime(data["bar_date"], errors="coerce").dt.normalize()
    for column in ["open", "high", "low", "close", "volume", "open_oi", "close_oi"]:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    return data.dropna(subset=["vt_symbol", "bar_datetime", "open", "high", "low", "close"]).reset_index(drop=True)


def _prepare_curve(curve: pd.DataFrame) -> pd.DataFrame:
    data = curve[curve["arm"].isin([C4_ARM, C9_ARM])].copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce", format="mixed").dt.normalize()
    for column in ["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct", "net_pnl", "trade_count"]:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    return data.dropna(subset=["date", "arm"]).reset_index(drop=True)


def _peak_dates(curve: pd.DataFrame) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for arm, group in curve.groupby("arm", sort=False):
        part = group.sort_values("broker10_margin_to_equity_pct", ascending=False).head(TOP_PEAK_DATES_PER_ARM).copy()
        part["peak_rank"] = range(1, len(part) + 1)
        part["peak_owner_arm"] = arm
        rows.append(part)
    if not rows:
        return pd.DataFrame()
    peaks = pd.concat(rows, ignore_index=True, sort=False)
    keep = [
        "peak_owner_arm",
        "peak_rank",
        "date",
        "account_equity",
        "drawdown_pct",
        "broker10_margin_to_equity_pct",
        "net_pnl",
        "trade_count",
    ]
    return peaks[keep].sort_values(["peak_owner_arm", "peak_rank"]).reset_index(drop=True)


def _prepare_closed_lots(closed_lots: pd.DataFrame) -> pd.DataFrame:
    data = closed_lots[closed_lots["arm"].isin([C4_ARM, C9_ARM])].copy()
    data["entry_date"] = pd.to_datetime(data["entry_date"], errors="coerce").dt.normalize()
    data["exit_date"] = pd.to_datetime(data["exit_date"], errors="coerce").dt.normalize()
    for column in ["volume", "size", "entry_price", "exit_price", "realized_pnl", "risk_amount", "r_multiple"]:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    if "product" not in data.columns:
        data["product"] = data["vt_symbol"].astype(str).str.extract(r"^([A-Za-z]+)")[0]
    return data.dropna(subset=["entry_date", "exit_date", "arm", "vt_symbol"]).reset_index(drop=True)


def _price_on_date(
    minute_by_symbol: dict[str, pd.DataFrame],
    vt_symbol: str,
    focus_date: pd.Timestamp,
    fallback_price: float,
) -> tuple[float, str, int, float, float]:
    bars = minute_by_symbol.get(vt_symbol, pd.DataFrame())
    if not bars.empty:
        day = bars[bars["bar_date"].eq(focus_date)].copy().sort_values("bar_datetime")
        if not day.empty:
            return (
                float(day["close"].iloc[-1]),
                "minute_last_close",
                int(len(day)),
                float(day["high"].max()),
                float(day["low"].min()),
            )
    return float(fallback_price), "entry_price_fallback", 0, np.nan, np.nan


def _curve_snapshot(curve: pd.DataFrame, arm: str, focus_date: pd.Timestamp) -> pd.Series:
    rows = curve[curve["arm"].eq(arm) & curve["date"].eq(focus_date)]
    if rows.empty:
        return pd.Series(dtype=object)
    return rows.iloc[0]


def _active_lots_for_focus(
    closed_lots: pd.DataFrame,
    curve: pd.DataFrame,
    peaks: pd.DataFrame,
    minute_by_symbol: dict[str, pd.DataFrame],
    metadata: dict[str, Any],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    margin_ratios = metadata.get("margin_ratios", {})
    sizes = metadata.get("sizes", {})
    focus_dates = sorted(set(pd.to_datetime(peaks["date"], errors="coerce").dropna().dt.normalize()))
    for focus_date in focus_dates:
        for arm in [C4_ARM, C9_ARM]:
            snapshot = _curve_snapshot(curve, arm, focus_date)
            account_equity = _safe_float(snapshot.get("account_equity"), np.nan)
            active = closed_lots[
                closed_lots["arm"].eq(arm)
                & closed_lots["entry_date"].le(focus_date)
                & closed_lots["exit_date"].ge(focus_date)
            ].copy()
            for _, row in active.iterrows():
                vt_symbol = str(row["vt_symbol"])
                size = _safe_float(row.get("size"), _safe_float(sizes.get(vt_symbol), 0.0))
                margin_ratio = _safe_float(margin_ratios.get(vt_symbol), 0.0)
                fallback = _safe_float(row.get("entry_price"), 0.0)
                price, price_source, minute_bars, day_high, day_low = _price_on_date(
                    minute_by_symbol,
                    vt_symbol,
                    focus_date,
                    fallback,
                )
                volume = _safe_float(row.get("volume"), 0.0)
                exchange_margin = price * size * volume * margin_ratio if price > 0 and size > 0 else np.nan
                broker10_margin = exchange_margin * BROKER_MARGIN_MULTIPLIER if np.isfinite(exchange_margin) else np.nan
                broker10_pct = broker10_margin / account_equity * 100.0 if account_equity > 0 else np.nan
                rows.append(
                    {
                        "focus_date": focus_date.date().isoformat(),
                        "arm": arm,
                        "peak_owner_arm": peaks.loc[peaks["date"].eq(focus_date), "peak_owner_arm"].iloc[0],
                        "account_equity": account_equity,
                        "curve_broker10_margin_to_equity_pct": _safe_float(
                            snapshot.get("broker10_margin_to_equity_pct")
                        ),
                        "lot_id": row.get("lot_id"),
                        "vt_symbol": vt_symbol,
                        "product_vt_symbol": str(row.get("product", "")),
                        "direction": str(row.get("direction", "")),
                        "entry_date": pd.Timestamp(row["entry_date"]).date().isoformat(),
                        "exit_date": pd.Timestamp(row["exit_date"]).date().isoformat(),
                        "volume": volume,
                        "size": size,
                        "margin_ratio": margin_ratio,
                        "focus_price": price,
                        "focus_price_source": price_source,
                        "focus_day_minute_bars": minute_bars,
                        "focus_day_high": day_high,
                        "focus_day_low": day_low,
                        "entry_price": _safe_float(row.get("entry_price")),
                        "exit_price": _safe_float(row.get("exit_price")),
                        "realized_pnl": _safe_float(row.get("realized_pnl")),
                        "risk_amount": _safe_float(row.get("risk_amount")),
                        "r_multiple": _safe_float(row.get("r_multiple")),
                        "signal": str(row.get("signal", "")),
                        "exit_reason": str(row.get("exit_reason", "")),
                        "estimated_exchange_margin": exchange_margin,
                        "estimated_broker10_margin": broker10_margin,
                        "estimated_broker10_margin_to_equity_pct": broker10_pct,
                    }
                )
    return pd.DataFrame(rows).sort_values(
        ["focus_date", "arm", "estimated_broker10_margin_to_equity_pct"],
        ascending=[True, True, False],
    ).reset_index(drop=True)


def _product_direction(active_lots: pd.DataFrame) -> pd.DataFrame:
    if active_lots.empty:
        return pd.DataFrame()
    data = active_lots.copy()
    for column in ["volume", "estimated_exchange_margin", "estimated_broker10_margin", "estimated_broker10_margin_to_equity_pct"]:
        data[column] = pd.to_numeric(data[column], errors="coerce").fillna(0.0)
    return (
        data.groupby(["focus_date", "arm", "product_vt_symbol", "direction"], dropna=False)
        .agg(
            active_lots=("lot_id", "size"),
            contracts=("vt_symbol", "nunique"),
            volume=("volume", "sum"),
            estimated_exchange_margin=("estimated_exchange_margin", "sum"),
            estimated_broker10_margin=("estimated_broker10_margin", "sum"),
            estimated_broker10_margin_to_equity_pct=("estimated_broker10_margin_to_equity_pct", "sum"),
        )
        .reset_index()
        .sort_values(["focus_date", "arm", "estimated_broker10_margin_to_equity_pct"], ascending=[True, True, False])
    )


def _pair_delta(active_lots: pd.DataFrame) -> pd.DataFrame:
    if active_lots.empty:
        return pd.DataFrame()
    grouped = (
        active_lots.groupby(["focus_date", "vt_symbol", "product_vt_symbol", "direction", "arm"], dropna=False)
        .agg(
            lot_ids=("lot_id", lambda s: ",".join(s.dropna().astype(str).tolist())),
            entry_date=("entry_date", "min"),
            exit_date=("exit_date", "max"),
            volume=("volume", "sum"),
            estimated_broker10_margin=("estimated_broker10_margin", "sum"),
            estimated_broker10_margin_to_equity_pct=("estimated_broker10_margin_to_equity_pct", "sum"),
            realized_pnl=("realized_pnl", "sum"),
            signal=("signal", lambda s: ",".join(sorted(set(s.dropna().astype(str))))),
            focus_day_minute_bars=("focus_day_minute_bars", "max"),
        )
        .reset_index()
    )
    rows: list[dict[str, Any]] = []
    for key, group in grouped.groupby(["focus_date", "vt_symbol", "product_vt_symbol", "direction"], dropna=False):
        item: dict[str, Any] = {
            "focus_date": key[0],
            "vt_symbol": key[1],
            "product_vt_symbol": key[2],
            "direction": key[3],
        }
        for arm, prefix in [(C4_ARM, "c4"), (C9_ARM, "c9")]:
            row = group[group["arm"].eq(arm)]
            if row.empty:
                values = {}
            else:
                values = row.iloc[0].to_dict()
            for column in [
                "lot_ids",
                "entry_date",
                "exit_date",
                "volume",
                "estimated_broker10_margin",
                "estimated_broker10_margin_to_equity_pct",
                "realized_pnl",
                "signal",
                "focus_day_minute_bars",
            ]:
                item[f"{prefix}_{column}"] = values.get(column, np.nan)
        item["volume_delta_c9_minus_c4"] = _safe_float(item.get("c9_volume"), 0.0) - _safe_float(
            item.get("c4_volume"), 0.0
        )
        item["broker10_margin_delta_c9_minus_c4"] = _safe_float(
            item.get("c9_estimated_broker10_margin"), 0.0
        ) - _safe_float(item.get("c4_estimated_broker10_margin"), 0.0)
        item["broker10_pct_delta_c9_minus_c4"] = _safe_float(
            item.get("c9_estimated_broker10_margin_to_equity_pct"), 0.0
        ) - _safe_float(item.get("c4_estimated_broker10_margin_to_equity_pct"), 0.0)
        rows.append(item)
    return pd.DataFrame(rows).sort_values(
        ["focus_date", "broker10_pct_delta_c9_minus_c4"],
        ascending=[True, False],
    ).reset_index(drop=True)


def _prepare_entry_risk(entry_risk: pd.DataFrame) -> pd.DataFrame:
    data = entry_risk[entry_risk["profile"].isin([C4_ARM, C9_ARM])].copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    for column in [
        "selected_volume",
        "selected_volume_ungated",
        "estimated_equity",
        "total_margin_in_use_before",
        "target_risk_amount",
        "actual_risk_amount",
        "margin_per_contract",
        "actual_margin_amount",
        "projected_total_margin_after",
        "risk_multiplier",
        "portfolio_drawdown_pct",
    ]:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    return data


def _match_entry_context(active_lots: pd.DataFrame, entry_risk: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if active_lots.empty or entry_risk.empty:
        return pd.DataFrame()
    for _, lot in active_lots.iterrows():
        entry_date = _normalize_date(lot["entry_date"])
        start = entry_date - pd.Timedelta(days=3)
        candidates = entry_risk[
            entry_risk["profile"].eq(lot["arm"])
            & entry_risk["contract_vt_symbol"].astype(str).eq(str(lot["vt_symbol"]))
            & entry_risk["direction"].astype(str).eq(str(lot["direction"]))
            & entry_risk["date"].between(start, entry_date)
        ].copy()
        if candidates.empty:
            continue
        candidates["volume_distance"] = (
            pd.to_numeric(candidates["selected_volume"], errors="coerce") - _safe_float(lot.get("volume"), 0.0)
        ).abs()
        candidates["date_distance"] = (entry_date - candidates["date"]).dt.days.abs()
        row = candidates.sort_values(["volume_distance", "date_distance"]).iloc[0]
        rows.append(
            {
                "focus_date": lot["focus_date"],
                "arm": lot["arm"],
                "lot_id": lot.get("lot_id"),
                "vt_symbol": lot["vt_symbol"],
                "product_vt_symbol": lot.get("product_vt_symbol", ""),
                "direction": lot["direction"],
                "lot_entry_date": lot["entry_date"],
                "entry_signal_date": pd.Timestamp(row["date"]).date().isoformat(),
                "signal": row.get("signal", ""),
                "entry_context": row.get("entry_context", ""),
                "lot_volume": _safe_float(lot.get("volume")),
                "selected_volume": _safe_float(row.get("selected_volume")),
                "selected_volume_ungated": _safe_float(row.get("selected_volume_ungated")),
                "estimated_equity": _safe_float(row.get("estimated_equity")),
                "total_margin_in_use_before": _safe_float(row.get("total_margin_in_use_before")),
                "target_risk_amount": _safe_float(row.get("target_risk_amount")),
                "actual_risk_amount": _safe_float(row.get("actual_risk_amount")),
                "margin_per_contract": _safe_float(row.get("margin_per_contract")),
                "actual_margin_amount": _safe_float(row.get("actual_margin_amount")),
                "projected_total_margin_after": _safe_float(row.get("projected_total_margin_after")),
                "risk_multiplier": _safe_float(row.get("risk_multiplier")),
                "portfolio_drawdown_pct": _safe_float(row.get("portfolio_drawdown_pct")),
                "volume_distance": _safe_float(row.get("volume_distance")),
            }
        )
    return pd.DataFrame(rows).sort_values(["focus_date", "arm", "actual_margin_amount"], ascending=[True, True, False])


def _stop_retry_before_peak(peaks: pd.DataFrame, stop_retry_events: pd.DataFrame) -> pd.DataFrame:
    if stop_retry_events.empty:
        return pd.DataFrame()
    events = stop_retry_events[stop_retry_events["profile"].eq(C9_ARM)].copy()
    events["event_date"] = pd.to_datetime(events["datetime"], errors="coerce", utc=True).dt.tz_convert(None).dt.normalize()
    rows: list[pd.DataFrame] = []
    for focus_date in sorted(set(pd.to_datetime(peaks["date"], errors="coerce").dropna().dt.normalize())):
        window = events[
            events["event_date"].between(focus_date - pd.Timedelta(days=STOP_RETRY_LOOKBACK_DAYS), focus_date)
        ].copy()
        if window.empty:
            continue
        window["focus_date"] = focus_date.date().isoformat()
        window["days_before_focus"] = (focus_date - window["event_date"]).dt.days
        rows.append(window)
    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True, sort=False).sort_values(["focus_date", "days_before_focus"])


def _find_stop_retry_event(
    events: pd.DataFrame,
    vt_symbol: str,
    direction: str,
    entry_date: Any,
) -> pd.Series | None:
    if events.empty:
        return None
    entry_ts = _normalize_date(entry_date)
    data = events[
        events["profile"].eq(C9_ARM)
        & events["vt_symbol"].astype(str).eq(str(vt_symbol))
        & events["direction"].astype(str).eq(str(direction))
    ].copy()
    if data.empty:
        return None
    data["event_date"] = pd.to_datetime(data["datetime"], errors="coerce", utc=True).dt.tz_convert(None).dt.normalize()
    data = data[data["event_date"].between(entry_ts - pd.Timedelta(days=3), entry_ts)]
    if data.empty:
        return None
    data["distance"] = (entry_ts - data["event_date"]).dt.days.abs()
    return data.sort_values("distance").iloc[0]


def _day_bars(minute_by_symbol: dict[str, pd.DataFrame], vt_symbol: str, date_value: Any) -> pd.DataFrame:
    bars = minute_by_symbol.get(str(vt_symbol), pd.DataFrame())
    if bars.empty:
        return pd.DataFrame()
    date = _normalize_date(date_value)
    return bars[bars["bar_date"].eq(date)].copy().sort_values("bar_datetime").head(360).reset_index(drop=True)


def _plot_day(
    ax: plt.Axes,
    minute_by_symbol: dict[str, pd.DataFrame],
    vt_symbol: str,
    date_value: Any,
    title: str,
    levels: dict[str, float] | None = None,
    markers: dict[str, Any] | None = None,
) -> int:
    day = _day_bars(minute_by_symbol, vt_symbol, date_value)
    if day.empty:
        ax.axis("off")
        ax.text(0.5, 0.5, f"missing minute bars\n{vt_symbol} {pd.Timestamp(date_value):%Y-%m-%d}", ha="center", va="center")
        ax.set_title(title, fontsize=8.5, loc="left")
        return 0
    s825._plot_candles(ax, day)
    if levels:
        for label, price in levels.items():
            value = _safe_float(price)
            if not np.isfinite(value):
                continue
            color = {"entry": "#2563eb", "stop": "#dc2626", "progress": "#16a34a", "focus_close": "#7c3aed"}.get(
                label,
                "#525252",
            )
            linestyle = "-" if label in {"entry", "focus_close"} else "--"
            ax.axhline(value, color=color, linestyle=linestyle, linewidth=0.9, label=label)
    if markers:
        for label, ts_value in markers.items():
            ts = pd.to_datetime(ts_value, errors="coerce")
            if pd.isna(ts):
                continue
            matches = day.index[pd.to_datetime(day["bar_datetime"], errors="coerce").eq(ts)]
            if len(matches):
                color = {"first_stop": "#dc2626", "reentry": "#2563eb", "retry_failed": "#7c2d12"}.get(label, "#525252")
                ax.axvline(int(matches[0]), color=color, linewidth=0.85, alpha=0.85, label=label)
    ticks = np.linspace(0, len(day) - 1, num=min(8, len(day)), dtype=int)
    ax.set_xticks(ticks)
    ax.set_xticklabels([pd.Timestamp(day.loc[pos, "bar_datetime"]).strftime("%H:%M") for pos in ticks], fontsize=7)
    handles, labels = ax.get_legend_handles_labels()
    if handles:
        dedup = dict(zip(labels, handles, strict=False))
        ax.legend(dedup.values(), dedup.keys(), loc="best", fontsize=7)
    ax.grid(True, alpha=0.18)
    ax.set_title(title, fontsize=8.5, loc="left")
    return int(len(day))


def _select_atlas_rows(pair_delta: pd.DataFrame) -> pd.DataFrame:
    if pair_delta.empty:
        return pd.DataFrame()
    data = pair_delta.copy()
    data["abs_pct_delta"] = pd.to_numeric(data["broker10_pct_delta_c9_minus_c4"], errors="coerce").abs()
    data["c9_pct"] = pd.to_numeric(data["c9_estimated_broker10_margin_to_equity_pct"], errors="coerce").fillna(0.0)
    selected = pd.concat(
        [
            data.sort_values("abs_pct_delta", ascending=False).head(MAX_ATLAS_ROWS // 2),
            data.sort_values("c9_pct", ascending=False).head(MAX_ATLAS_ROWS // 2),
        ],
        ignore_index=True,
        sort=False,
    )
    return selected.drop_duplicates(["focus_date", "vt_symbol", "direction"]).head(MAX_ATLAS_ROWS).reset_index(drop=True)


def _plot_atlas(
    pair_delta: pd.DataFrame,
    minute_by_symbol: dict[str, pd.DataFrame],
    stop_retry_events: pd.DataFrame,
) -> tuple[list[Path], pd.DataFrame]:
    selected = _select_atlas_rows(pair_delta)
    if selected.empty:
        return [], pd.DataFrame()
    pages = int(math.ceil(len(selected) / PER_PAGE))
    paths: list[Path] = []
    manifest: list[dict[str, Any]] = []
    for page in range(1, pages + 1):
        part = selected.iloc[(page - 1) * PER_PAGE : page * PER_PAGE].copy()
        fig, axes = plt.subplots(len(part), 2, figsize=(18, max(4.2, 3.2 * len(part))), constrained_layout=True)
        axes_array = np.atleast_2d(axes)
        for row_index, (_, row) in enumerate(part.iterrows()):
            vt_symbol = str(row["vt_symbol"])
            direction = str(row["direction"])
            focus_date = _normalize_date(row["focus_date"])
            entry_date = row.get("c9_entry_date") if pd.notna(row.get("c9_entry_date")) else row.get("c4_entry_date")
            event = _find_stop_retry_event(stop_retry_events, vt_symbol, direction, entry_date)
            if event is not None:
                first_stop_time = event.get("first_stop_time", "")
                entry_plot_date = _normalize_date(first_stop_time)
                levels = {
                    "entry": _safe_float(event.get("entry_price")),
                    "stop": _safe_float(event.get("stop_price")),
                    "progress": _safe_float(event.get("progress_price")),
                }
                markers = {
                    "first_stop": event.get("first_stop_time"),
                    "reentry": event.get("reentry_time"),
                    "retry_failed": event.get("retry_failed_time"),
                }
                event_state = str(event.get("final_state", ""))
            else:
                entry_plot_date = _normalize_date(entry_date)
                levels = {"entry": _safe_float(row.get("c9_entry_price"), np.nan)}
                markers = {}
                event_state = "no_c9_stop_retry_event"
            left_title = (
                f"entry day | {vt_symbol} {direction} entry={pd.Timestamp(entry_plot_date):%Y-%m-%d} "
                f"event={event_state}"
            )
            right_title = (
                f"focus day | {focus_date:%Y-%m-%d} C9vol={_safe_float(row.get('c9_volume'), 0):.0f} "
                f"C4vol={_safe_float(row.get('c4_volume'), 0):.0f} "
                f"dPct={_safe_float(row.get('broker10_pct_delta_c9_minus_c4'), 0):.2f}"
            )
            entry_bars = _plot_day(
                axes_array[row_index, 0],
                minute_by_symbol,
                vt_symbol,
                entry_plot_date,
                left_title,
                levels=levels,
                markers=markers,
            )
            focus_bars = _plot_day(
                axes_array[row_index, 1],
                minute_by_symbol,
                vt_symbol,
                focus_date,
                right_title,
                levels={"focus_close": np.nan},
            )
            manifest.append(
                {
                    "page": page,
                    "focus_date": focus_date.date().isoformat(),
                    "vt_symbol": vt_symbol,
                    "direction": direction,
                    "entry_plot_date": pd.Timestamp(entry_plot_date).date().isoformat(),
                    "entry_day_minute_bars": entry_bars,
                    "focus_day_minute_bars": focus_bars,
                    "c4_volume": _safe_float(row.get("c4_volume"), 0.0),
                    "c9_volume": _safe_float(row.get("c9_volume"), 0.0),
                    "volume_delta_c9_minus_c4": _safe_float(row.get("volume_delta_c9_minus_c4"), 0.0),
                    "broker10_pct_delta_c9_minus_c4": _safe_float(row.get("broker10_pct_delta_c9_minus_c4"), 0.0),
                    "event_state": event_state,
                }
            )
        fig.suptitle("Stage864 C9/C4 broker10 peak active-lot minute atlas", fontsize=13)
        path = Path(str(ATLAS_TEMPLATE).format(page=page))
        fig.savefig(path, dpi=150)
        plt.close(fig)
        paths.append(path)
    return paths, pd.DataFrame(manifest)


def _entry_pair_delta(entry_context: pd.DataFrame) -> pd.DataFrame:
    if entry_context.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    keys = ["focus_date", "vt_symbol", "direction", "lot_entry_date"]
    for key, group in entry_context.groupby(keys, dropna=False):
        item = dict(zip(keys, key, strict=False))
        for arm, prefix in [(C4_ARM, "c4"), (C9_ARM, "c9")]:
            part = group[group["arm"].eq(arm)]
            row = part.iloc[0].to_dict() if not part.empty else {}
            for column in [
                "selected_volume",
                "estimated_equity",
                "total_margin_in_use_before",
                "target_risk_amount",
                "actual_risk_amount",
                "actual_margin_amount",
                "projected_total_margin_after",
                "risk_multiplier",
                "portfolio_drawdown_pct",
            ]:
                item[f"{prefix}_{column}"] = row.get(column, np.nan)
        item["selected_volume_delta_c9_minus_c4"] = _safe_float(item.get("c9_selected_volume"), 0.0) - _safe_float(
            item.get("c4_selected_volume"), 0.0
        )
        item["estimated_equity_delta_c9_minus_c4"] = _safe_float(item.get("c9_estimated_equity"), 0.0) - _safe_float(
            item.get("c4_estimated_equity"), 0.0
        )
        item["actual_margin_delta_c9_minus_c4"] = _safe_float(item.get("c9_actual_margin_amount"), 0.0) - _safe_float(
            item.get("c4_actual_margin_amount"), 0.0
        )
        rows.append(item)
    return pd.DataFrame(rows).sort_values(["focus_date", "actual_margin_delta_c9_minus_c4"], ascending=[True, False])


def _write_report(
    peaks: pd.DataFrame,
    product_direction: pd.DataFrame,
    pair_delta: pd.DataFrame,
    entry_pair_delta: pd.DataFrame,
    stop_retry_window: pd.DataFrame,
    atlas_paths: list[Path],
) -> None:
    c9_peak = peaks[peaks["peak_owner_arm"].eq(C9_ARM)].sort_values("peak_rank").head(1)
    c4_peak = peaks[peaks["peak_owner_arm"].eq(C4_ARM)].sort_values("peak_rank").head(1)
    top_delta = pair_delta.reindex(pair_delta["broker10_pct_delta_c9_minus_c4"].abs().sort_values(ascending=False).index)
    stop_summary = pd.DataFrame()
    if not stop_retry_window.empty:
        stop_summary = (
            stop_retry_window.groupby(["focus_date", "final_state"], dropna=False)
            .agg(events=("vt_symbol", "size"), volume=("volume", "sum"))
            .reset_index()
            .sort_values(["focus_date", "events"], ascending=[True, False])
        )
    lines = [
        "# Stage864 C9/C4 broker10峰值只读归因",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 源候选：`{stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION}`",
        "- 阶段性质：只读归因与分钟K视觉复盘；不写新规则、不改正式版、不改候选配置、不连接 CTP、不调用下单。",
        "",
        "## 外部调研判断",
        "",
        "- vn.py GitHub：https://github.com/vnpy/vnpy",
        "- backtesting.py 逐 bar 回放文档：https://kernc.github.io/backtesting.py/doc/backtesting/backtesting.html",
        "- 我的判断：峰值归因必须按真实组合路径解释保证金分子、权益分母和成交事件顺序，不能用事后高风险日期直接写规则。",
        "",
        "## Peak Dates",
        "",
        _md_table(peaks, max_rows=12),
        "",
        "## First Peak Contrast",
        "",
        "- C9/C10 峰值来自 Stage863 全量分钟K同口径回放，C10 与 C9 完全重合，本阶段只比较 C4 vs C9。",
        f"- C4 top peak：`{c4_peak.iloc[0]['date'].date().isoformat() if not c4_peak.empty else ''}` "
        f"broker10 `{_safe_float(c4_peak.iloc[0]['broker10_margin_to_equity_pct']) if not c4_peak.empty else np.nan:.4f}%`。",
        f"- C9 top peak：`{c9_peak.iloc[0]['date'].date().isoformat() if not c9_peak.empty else ''}` "
        f"broker10 `{_safe_float(c9_peak.iloc[0]['broker10_margin_to_equity_pct']) if not c9_peak.empty else np.nan:.4f}%`。",
        "",
        "## Product Direction Attribution",
        "",
        _md_table(product_direction.head(30), max_rows=30),
        "",
        "## C9-C4 Active Lot Delta",
        "",
        _md_table(top_delta.head(30), max_rows=30),
        "",
        "## Entry Sizing Delta",
        "",
        _md_table(entry_pair_delta.head(30), max_rows=30),
        "",
        "## Stop/Retry Events Before Focus Dates",
        "",
        _md_table(stop_summary, max_rows=30),
        "",
        "## Visual Atlas",
        "",
        *[f"- atlas page：`{path}`" for path in atlas_paths],
        "",
        "## Judgment",
        "",
        "- Stage864 仍不产生新策略。当前证据显示 C9 的 broker10 峰值风险需要分解为：早期 stop/retry 改变权益/资金路径，随后相同信号在更高权益或更少约束下得到更大 sizing；这不是 C10 同品种加仓锁能拦截的路径。",
        "- 下一步若继续，应寻找一个实时可判定的账户层 sizing brake：只在 broker10 峰值形成前、且不误伤大部分右尾时触发；不得按峰值日期、品种或方向写黑名单。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curve = _prepare_curve(_load_required_csv(CURVE_IN))
    closed_lots = _prepare_closed_lots(_load_required_csv(CLOSED_LOTS_IN))
    entry_risk = _prepare_entry_risk(_load_required_csv(ENTRY_RISK_IN))
    stop_retry_events = _load_required_csv(STOP_RETRY_IN)
    metadata = s513._metadata()
    vt_symbols = set(closed_lots["vt_symbol"].dropna().astype(str).unique())
    minute_bars = _load_full_minute_bars(vt_symbols)
    minute_by_symbol = s825._minute_groups(minute_bars)

    peaks = _peak_dates(curve)
    active_lots = _active_lots_for_focus(closed_lots, curve, peaks, minute_by_symbol, metadata)
    product_direction = _product_direction(active_lots)
    pair_delta = _pair_delta(active_lots)
    entry_context = _match_entry_context(active_lots, entry_risk)
    entry_pair_delta = _entry_pair_delta(entry_context)
    stop_retry_window = _stop_retry_before_peak(peaks, stop_retry_events)
    atlas_paths, atlas_manifest = _plot_atlas(pair_delta, minute_by_symbol, stop_retry_events)

    peaks.to_csv(PEAK_DATES_PATH, index=False, encoding="utf-8-sig")
    active_lots.to_csv(ACTIVE_LOTS_PATH, index=False, encoding="utf-8-sig")
    product_direction.to_csv(PRODUCT_DIRECTION_PATH, index=False, encoding="utf-8-sig")
    pair_delta.to_csv(PAIR_DELTA_PATH, index=False, encoding="utf-8-sig")
    entry_context.to_csv(ENTRY_SIZING_PATH, index=False, encoding="utf-8-sig")
    stop_retry_window.to_csv(STOP_RETRY_WINDOW_PATH, index=False, encoding="utf-8-sig")
    atlas_manifest.to_csv(ATLAS_MANIFEST_PATH, index=False, encoding="utf-8-sig")
    _write_report(peaks, product_direction, pair_delta, entry_pair_delta, stop_retry_window, atlas_paths)

    c9_peak = peaks[peaks["peak_owner_arm"].eq(C9_ARM)].sort_values("peak_rank").head(1)
    c4_peak = peaks[peaks["peak_owner_arm"].eq(C4_ARM)].sort_values("peak_rank").head(1)
    top_delta = pair_delta.reindex(pair_delta["broker10_pct_delta_c9_minus_c4"].abs().sort_values(ascending=False).index)
    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "source_candidate": stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION,
        "strategy_changed": False,
        "ctp_connected": False,
        "order_api_called": False,
        "formal_ab_triggered": False,
        "inputs": {
            "stage863_decision": str(DECISION_IN),
            "stage861_full_minute_bars": str(s861.FULL_MINUTE_BARS_PATH),
            "loaded_minute_bars": int(len(minute_bars)),
            "loaded_symbols": int(minute_bars["vt_symbol"].astype(str).nunique()) if not minute_bars.empty else 0,
        },
        "c4_top_peak": c4_peak.to_dict("records"),
        "c9_top_peak": c9_peak.to_dict("records"),
        "top_active_lot_deltas": top_delta.head(10).to_dict("records"),
        "atlas_pages": [str(path) for path in atlas_paths],
        "decision": "stage864_peak_forensics_no_rule_yet",
        "overfit_reflection": (
            "不是过拟合。本阶段只读取 Stage863 固定输出与 Stage861 全量分钟K，按真实峰值日做归因和视觉复核，"
            "没有生成参数、阈值、品种、方向或年份过滤。"
        ),
        "continue_value": (
            "有继续价值，但下一步必须从峰值归因抽象实时账户层 sizing brake，先做只读反事实；"
            "不能直接用峰值日期或具体品种写规则。"
        ),
        "outputs": {
            "report": str(REPORT_PATH),
            "peak_dates": str(PEAK_DATES_PATH),
            "active_lots": str(ACTIVE_LOTS_PATH),
            "product_direction": str(PRODUCT_DIRECTION_PATH),
            "pair_delta": str(PAIR_DELTA_PATH),
            "entry_sizing": str(ENTRY_SIZING_PATH),
            "stop_retry_window": str(STOP_RETRY_WINDOW_PATH),
            "atlas_manifest": str(ATLAS_MANIFEST_PATH),
            "atlas_pages": [str(path) for path in atlas_paths],
        },
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print("peaks")
    print(peaks.to_string(index=False))
    print("top_pair_delta")
    print(top_delta.head(20).to_string(index=False))


if __name__ == "__main__":
    main()
