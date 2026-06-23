from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
from typing import Any
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage005"
MODEL_TAG = "stage005_signal_quality_visual_forensics_v1"
OUTPUT_PREFIX = "qmt_roll_stage005_c9_minrisk_signal_quality_visual_forensics"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
TOOL_DIR = SCRIPT_PATH.parent
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
for item in [str(TOOL_DIR), str(EXAMPLE_DIR)]:
    if item not in sys.path:
        sys.path.insert(0, item)

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage825_stage819_intraday_rule_forensics as s825
import analyze_qmt_roll_stage827_stage819_intraday_c2_engine_ac as s827
from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage005_signal_quality_visual_forensics"
STAGE004_DIR = LINE_DIR / "outputs" / "stage004_cap_only_delayed_restore"

START = pd.Timestamp("2018-01-01")
END = pd.Timestamp("2026-06-15")
FULL_WINDOW_ID = "2018_01_to_2026_06_15"
CAPITAL = 150_000.0
PER_PAGE = 4
MAX_ATLAS_ROWS = 24

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CURVE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_curve_{MODEL_TAG}.csv"
TRADES_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_trades_{MODEL_TAG}.csv"
ENTRY_RISK_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_entry_risk_{MODEL_TAG}.csv"
TRADE_EVENTS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_trade_events_{MODEL_TAG}.csv"
CLOSED_LOTS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_closed_lots_{MODEL_TAG}.csv"
EVENTS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_features_{MODEL_TAG}.csv"
BUCKET_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_stats_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_path_marker_chart_{MODEL_TAG}.png"
ATLAS_MANIFEST_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_page{{page:03d}}_{MODEL_TAG}.png"

STAGE004_RESTORE_EVENTS = (
    STAGE004_DIR / "qmt_roll_stage004_c9_minrisk_cap_only_delayed_restore_restore_events_stage004_cap_only_delayed_restore_v1.csv"
)
STAGE004_OPEN_ADJUSTMENTS = (
    STAGE004_DIR / "qmt_roll_stage004_c9_minrisk_cap_only_delayed_restore_open_adjustments_stage004_cap_only_delayed_restore_v1.csv"
)
STAGE004_OFFICIAL_CURVE = (
    STAGE004_DIR / "qmt_roll_stage004_c9_minrisk_cap_only_delayed_restore_curve_stage004_cap_only_delayed_restore_v1.csv"
)
STAGE004_CAP_EVENTS = (
    STAGE004_DIR / "qmt_roll_stage004_c9_minrisk_cap_only_delayed_restore_cap_delay_eligible_events_stage004_cap_only_delayed_restore_v1.csv"
)
STAGE004_ENTRY_RISK = (
    STAGE004_DIR / "qmt_roll_stage004_c9_minrisk_cap_only_delayed_restore_entry_risk_stage004_cap_only_delayed_restore_v1.csv"
)
STAGE847_CORE_CLOSED_LOTS = (
    EXAMPLE_DIR
    / "backtest_outputs"
    / "qmt_roll_stage847_stage830_c4_stop_retry_engine_closed_lots_stage847_stage830_c4_stop_retry_engine_v1.csv"
)


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    data = frame.copy()
    if max_rows is not None:
        data = data.head(max_rows)
    return data.to_markdown(index=False)


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        if pd.isna(value):
            return default
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if np.isfinite(result) else default


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    values = pd.to_numeric(equity, errors="coerce").ffill()
    peak = values.cummax()
    return (values / peak.replace(0.0, np.nan) - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0) * 100.0


def _normalize_day(value: Any) -> pd.Timestamp:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return pd.NaT
    try:
        if ts.tzinfo is not None:
            ts = ts.tz_localize(None)
    except AttributeError:
        pass
    return pd.Timestamp(ts).normalize()


def _load_official_curve() -> pd.DataFrame:
    if not STAGE004_OFFICIAL_CURVE.exists():
        raise RuntimeError(f"missing official curve input: {STAGE004_OFFICIAL_CURVE}")
    curve = pd.read_csv(STAGE004_OFFICIAL_CURVE, encoding="utf-8-sig")
    if "arm" in curve.columns:
        curve = curve[curve["arm"].astype(str).eq("A_official_stage847_c9_15w")].copy()
    if curve.empty:
        raise RuntimeError("missing A official curve rows in Stage004 output")
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    curve["stage"] = STAGE
    curve["model_tag"] = MODEL_TAG
    curve["line_id"] = LINE_ID
    curve["arm"] = "A_official_stage847_c9_15w"
    curve["window_id"] = FULL_WINDOW_ID
    curve["account_capital"] = CAPITAL
    curve["nav"] = pd.to_numeric(curve["account_equity"], errors="coerce") / CAPITAL
    curve["drawdown_pct"] = _drawdown_pct(curve["account_equity"])
    return curve


def _load_core_closed_lots() -> pd.DataFrame:
    if not STAGE847_CORE_CLOSED_LOTS.exists():
        raise RuntimeError(f"missing C9 core closed lots input: {STAGE847_CORE_CLOSED_LOTS}")
    closed = pd.read_csv(STAGE847_CORE_CLOSED_LOTS, encoding="utf-8-sig")
    for column in ("entry_date", "exit_date"):
        if column in closed.columns:
            closed[column] = pd.to_datetime(closed[column], errors="coerce").dt.normalize()
    closed = closed[
        closed["entry_date"].ge(START.normalize())
        & closed["entry_date"].le(END.normalize())
        & closed["exit_date"].le(END.normalize())
    ].copy()
    closed["source_note"] = "Stage847/C9 core 30w closed_lots; used only as minute-shape reference, not 15w official metric"
    return closed.reset_index(drop=True)


def _nearest_entry_risk(entry_risk: pd.DataFrame) -> dict[tuple[str, str, str], dict[str, Any]]:
    result: dict[tuple[str, str, str], dict[str, Any]] = {}
    if entry_risk.empty:
        return result
    data = entry_risk.copy()
    data["date_key"] = pd.to_datetime(data["datetime"], errors="coerce").dt.normalize().dt.strftime("%Y-%m-%d")
    for _, row in data.iterrows():
        key = (str(row.get("date_key")), str(row.get("contract_vt_symbol")), str(row.get("direction")))
        result[key] = row.to_dict()
    return result


def _cap_events_from_stage004() -> pd.DataFrame:
    if not STAGE004_CAP_EVENTS.exists():
        raise RuntimeError(f"missing Stage004 cap events: {STAGE004_CAP_EVENTS}")
    caps = pd.read_csv(STAGE004_CAP_EVENTS, encoding="utf-8-sig")
    if caps.empty:
        return pd.DataFrame()
    entry_map: dict[tuple[str, str, str], dict[str, Any]] = {}
    if STAGE004_ENTRY_RISK.exists():
        entry_risk = pd.read_csv(STAGE004_ENTRY_RISK, encoding="utf-8-sig")
        entry_map = _nearest_entry_risk(entry_risk)
    rows: list[dict[str, Any]] = []
    for _, row in caps.iterrows():
        dt = pd.to_datetime(row.get("datetime"), errors="coerce")
        day = _normalize_day(row.get("datetime"))
        date_key = day.strftime("%Y-%m-%d") if not pd.isna(day) else ""
        vt_symbol = str(row.get("vt_symbol"))
        direction = str(row.get("direction"))
        risk = entry_map.get((date_key, vt_symbol, direction), {})
        entry_price = _safe_float(risk.get("entry_price"), _safe_float(row.get("price")))
        stop_price = _safe_float(risk.get("stop_price"))
        risk_price = abs(entry_price - stop_price) if np.isfinite(entry_price) and np.isfinite(stop_price) else np.nan
        rows.append(
            {
                "event_type": "broker10_cap",
                "event_priority": 1,
                "datetime": dt,
                "date": day,
                "vt_symbol": vt_symbol,
                "product_vt_symbol": row.get("product_vt_symbol"),
                "direction": direction,
                "signal": row.get("signal"),
                "entry_price": entry_price,
                "stop_price": stop_price,
                "risk_price": risk_price,
                "volume": _safe_float(row.get("selected_volume_after"), _safe_float(row.get("volume"), 0.0)),
                "selected_volume_before": _safe_float(row.get("selected_volume_before")),
                "selected_volume_after": _safe_float(row.get("selected_volume_after")),
                "reduced_volume": _safe_float(row.get("reduced_volume"), 0.0),
                "projected_broker10_before": _safe_float(row.get("projected_broker10_margin_to_equity_before")),
                "projected_broker10_after": _safe_float(row.get("projected_broker10_margin_to_equity_after")),
                "realized_pnl": np.nan,
                "r_multiple": np.nan,
                "exit_reason": "",
                "source": "stage004_cap_context",
                "note": "Stage004 cap context event; used as account-pressure visual evidence",
            }
        )
    return pd.DataFrame(rows)


def _lot_events(closed: pd.DataFrame) -> pd.DataFrame:
    if closed.empty:
        return pd.DataFrame()
    data = closed.copy()
    data["r_multiple_num"] = pd.to_numeric(data.get("r_multiple"), errors="coerce")
    data["realized_pnl_num"] = pd.to_numeric(data.get("realized_pnl"), errors="coerce")
    winners = data.sort_values(["r_multiple_num", "realized_pnl_num"], ascending=False).head(8).copy()
    losers = data.sort_values(["r_multiple_num", "realized_pnl_num"], ascending=True).head(8).copy()
    rows: list[dict[str, Any]] = []
    for event_type, priority, frame in [
        ("top_winner", 2, winners),
        ("top_loser", 3, losers),
    ]:
        for _, row in frame.iterrows():
            dt = pd.to_datetime(row.get("entry_date"), errors="coerce")
            day = _normalize_day(row.get("entry_date"))
            entry_price = _safe_float(row.get("entry_price"))
            stop_distance = _safe_float(row.get("stop_distance"))
            direction = str(row.get("direction"))
            if np.isfinite(entry_price) and np.isfinite(stop_distance):
                stop_price = entry_price - stop_distance if direction == "long" else entry_price + stop_distance
                risk_price = abs(entry_price - stop_price)
            else:
                stop_price = np.nan
                risk_price = np.nan
            rows.append(
                {
                    "event_type": event_type,
                    "event_priority": priority,
                    "datetime": dt,
                    "date": day,
                    "vt_symbol": row.get("vt_symbol"),
                    "product_vt_symbol": row.get("product", ""),
                    "direction": direction,
                    "signal": row.get("signal"),
                    "entry_price": entry_price,
                    "stop_price": stop_price,
                    "risk_price": risk_price,
                    "volume": _safe_float(row.get("volume"), 0.0),
                    "selected_volume_before": np.nan,
                    "selected_volume_after": _safe_float(row.get("selected_volume"), _safe_float(row.get("volume"), 0.0)),
                    "reduced_volume": np.nan,
                    "projected_broker10_before": np.nan,
                    "projected_broker10_after": np.nan,
                    "realized_pnl": _safe_float(row.get("realized_pnl")),
                    "r_multiple": _safe_float(row.get("r_multiple")),
                    "exit_reason": row.get("exit_reason", ""),
                    "source": "official_closed_lots",
                    "note": f"official closed lot {event_type}",
                }
            )
    return pd.DataFrame(rows)


def _stage004_restore_events() -> pd.DataFrame:
    if not STAGE004_RESTORE_EVENTS.exists():
        return pd.DataFrame()
    data = pd.read_csv(STAGE004_RESTORE_EVENTS, encoding="utf-8-sig")
    if data.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for _, row in data.iterrows():
        dt = pd.to_datetime(row.get("datetime"), errors="coerce")
        day = _normalize_day(row.get("datetime"))
        rows.append(
            {
                "event_type": "stage004_restore_failure" if str(row.get("final_state")) == "restore_stopped" else "stage004_restore_open",
                "event_priority": 4,
                "datetime": dt,
                "date": day,
                "vt_symbol": row.get("vt_symbol"),
                "product_vt_symbol": row.get("product_vt_symbol"),
                "direction": row.get("direction"),
                "signal": "",
                "entry_price": _safe_float(row.get("entry_price")),
                "stop_price": _safe_float(row.get("original_stop_price")),
                "risk_price": _safe_float(row.get("risk_price")),
                "volume": _safe_float(row.get("restore_volume")),
                "selected_volume_before": _safe_float(row.get("original_volume")),
                "selected_volume_after": _safe_float(row.get("restore_volume")),
                "reduced_volume": np.nan,
                "projected_broker10_before": np.nan,
                "projected_broker10_after": np.nan,
                "realized_pnl": _safe_float(row.get("estimated_restore_pnl")),
                "r_multiple": np.nan,
                "exit_reason": row.get("exit_reason", ""),
                "source": "stage004_failed_candidate",
                "progress_time": row.get("progress_time"),
                "stop_time": row.get("stop_time"),
                "final_state": row.get("final_state"),
                "restore_stop_state": row.get("restore_stop_state"),
                "note": "Stage004 restore evidence for visual contrast only",
            }
        )
    return pd.DataFrame(rows)


def _line_prices(row: pd.Series) -> dict[str, float]:
    entry = _safe_float(row.get("entry_price"))
    stop = _safe_float(row.get("stop_price"))
    risk = _safe_float(row.get("risk_price"))
    if not np.isfinite(risk) or risk <= 0:
        risk = abs(entry - stop) if np.isfinite(entry) and np.isfinite(stop) else np.nan
    direction = str(row.get("direction"))
    if not np.isfinite(entry) or not np.isfinite(risk) or risk <= 0:
        return {"entry": entry, "stop": stop, "progress_05r": np.nan, "adverse_05r": np.nan}
    if direction == "short":
        progress = entry - 0.5 * risk
        adverse = entry + 0.5 * risk
    else:
        progress = entry + 0.5 * risk
        adverse = entry - 0.5 * risk
    return {"entry": entry, "stop": stop, "progress_05r": progress, "adverse_05r": adverse}


def _first_touch(day: pd.DataFrame, row: pd.Series) -> dict[str, Any]:
    prices = _line_prices(row)
    entry = prices["entry"]
    risk = _safe_float(row.get("risk_price"))
    direction = str(row.get("direction"))
    if day.empty or not np.isfinite(entry) or not np.isfinite(risk) or risk <= 0:
        return {
            "minute_coverage": int(len(day)),
            "first_touch": "missing",
            "progress_bar_index": np.nan,
            "adverse_bar_index": np.nan,
            "first_30m_directional_r": np.nan,
            "entry_day_mfe_r": np.nan,
            "entry_day_mae_r": np.nan,
        }
    progress = prices["progress_05r"]
    adverse = prices["adverse_05r"]
    if direction == "short":
        progress_hits = day.index[pd.to_numeric(day["low"], errors="coerce").le(progress)]
        adverse_hits = day.index[pd.to_numeric(day["high"], errors="coerce").ge(adverse)]
        close_30 = _safe_float(day.iloc[min(29, len(day) - 1)]["close"])
        first_30 = (entry - close_30) / risk if np.isfinite(close_30) else np.nan
        mfe = (entry - pd.to_numeric(day["low"], errors="coerce").min()) / risk
        mae = (pd.to_numeric(day["high"], errors="coerce").max() - entry) / risk
    else:
        progress_hits = day.index[pd.to_numeric(day["high"], errors="coerce").ge(progress)]
        adverse_hits = day.index[pd.to_numeric(day["low"], errors="coerce").le(adverse)]
        close_30 = _safe_float(day.iloc[min(29, len(day) - 1)]["close"])
        first_30 = (close_30 - entry) / risk if np.isfinite(close_30) else np.nan
        mfe = (pd.to_numeric(day["high"], errors="coerce").max() - entry) / risk
        mae = (entry - pd.to_numeric(day["low"], errors="coerce").min()) / risk
    progress_idx = int(progress_hits[0]) if len(progress_hits) else -1
    adverse_idx = int(adverse_hits[0]) if len(adverse_hits) else -1
    if progress_idx < 0 and adverse_idx < 0:
        first = "none"
    elif progress_idx >= 0 and adverse_idx >= 0 and progress_idx == adverse_idx:
        first = "both_same_bar"
    elif progress_idx >= 0 and (adverse_idx < 0 or progress_idx < adverse_idx):
        first = "progress_first"
    else:
        first = "adverse_first"
    return {
        "minute_coverage": int(len(day)),
        "first_touch": first,
        "progress_bar_index": progress_idx if progress_idx >= 0 else np.nan,
        "adverse_bar_index": adverse_idx if adverse_idx >= 0 else np.nan,
        "first_30m_directional_r": first_30,
        "entry_day_mfe_r": mfe,
        "entry_day_mae_r": mae,
    }


def _add_intraday_features(events: pd.DataFrame, minute_by_symbol: dict[str, pd.DataFrame]) -> pd.DataFrame:
    if events.empty:
        return events
    rows: list[dict[str, Any]] = []
    for _, row in events.iterrows():
        vt_symbol = str(row.get("vt_symbol"))
        date = _normalize_day(row.get("date"))
        day = minute_by_symbol.get(vt_symbol, pd.DataFrame())
        if not day.empty and not pd.isna(date):
            day = day[day["bar_date"].eq(date)].copy().sort_values("bar_datetime").reset_index(drop=True)
        else:
            day = pd.DataFrame()
        feature = _first_touch(day, row)
        item = row.to_dict()
        item.update(feature)
        rows.append(item)
    return pd.DataFrame(rows)


def _event_sample(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()
    data = events.copy()
    data["rank_metric"] = 0.0
    cap_mask = data["event_type"].eq("broker10_cap")
    data.loc[cap_mask, "rank_metric"] = pd.to_numeric(data.loc[cap_mask, "projected_broker10_before"], errors="coerce").fillna(0)
    winner_mask = data["event_type"].eq("top_winner")
    data.loc[winner_mask, "rank_metric"] = pd.to_numeric(data.loc[winner_mask, "r_multiple"], errors="coerce").fillna(0)
    loser_mask = data["event_type"].eq("top_loser")
    data.loc[loser_mask, "rank_metric"] = -pd.to_numeric(data.loc[loser_mask, "r_multiple"], errors="coerce").fillna(0)
    restore_mask = data["event_type"].astype(str).str.startswith("stage004_restore")
    data.loc[restore_mask, "rank_metric"] = pd.to_numeric(data.loc[restore_mask, "volume"], errors="coerce").fillna(0)
    selected: list[pd.DataFrame] = []
    for event_type, limit in [
        ("broker10_cap", 8),
        ("top_winner", 6),
        ("top_loser", 6),
        ("stage004_restore_failure", 4),
    ]:
        part = data[data["event_type"].eq(event_type)].sort_values("rank_metric", ascending=False).head(limit)
        if not part.empty:
            selected.append(part)
    if not selected:
        return data.head(MAX_ATLAS_ROWS)
    return (
        pd.concat(selected, ignore_index=True, sort=False)
        .drop_duplicates(["event_type", "vt_symbol", "date", "direction"])
        .head(MAX_ATLAS_ROWS)
    )


def _plot_path(curve: pd.DataFrame, events: pd.DataFrame) -> None:
    data = curve.copy().sort_values("date")
    fig, axes = plt.subplots(3, 1, figsize=(18, 11), sharex=True, constrained_layout=True)
    axes[0].plot(data["date"], data["account_equity"], color="#2563eb", label="A official C9/15w")
    axes[1].plot(data["date"], data["drawdown_pct"], color="#2563eb", label="drawdown")
    axes[2].plot(data["date"], data["broker10_margin_to_equity_pct"], color="#2563eb", label="broker10")
    colors = {
        "broker10_cap": "#dc2626",
        "top_winner": "#16a34a",
        "top_loser": "#7c2d12",
        "stage004_restore_failure": "#7c3aed",
        "stage004_restore_open": "#a855f7",
    }
    labels_seen: set[str] = set()
    markers = _event_sample(events)
    for _, row in markers.iterrows():
        dt = _normalize_day(row.get("date"))
        if pd.isna(dt):
            continue
        event_type = str(row.get("event_type"))
        label = event_type if event_type not in labels_seen else None
        labels_seen.add(event_type)
        for ax in axes:
            ax.axvline(dt, color=colors.get(event_type, "#64748b"), alpha=0.22, linewidth=1.0, label=label)
            label = None
    axes[0].set_title("Stage005 official C9/15w equity with event markers")
    axes[1].set_title("Drawdown")
    axes[2].set_title("Broker10 margin to equity pct")
    axes[2].axhline(100.0, color="#dc2626", linestyle="--", linewidth=0.9, alpha=0.75)
    for ax in axes:
        ax.grid(True, alpha=0.24)
        ax.legend(loc="best")
    fig.savefig(PATH_CHART_OUT, dpi=170)
    plt.close(fig)


def _plot_atlas(events: pd.DataFrame, minute_by_symbol: dict[str, pd.DataFrame]) -> tuple[list[Path], pd.DataFrame]:
    selected = _event_sample(events)
    if selected.empty:
        return [], pd.DataFrame()
    pages = int(math.ceil(len(selected) / PER_PAGE))
    paths: list[Path] = []
    manifest: list[dict[str, Any]] = []
    colors = {
        "entry": "#2563eb",
        "stop": "#dc2626",
        "progress_05r": "#16a34a",
        "adverse_05r": "#7c2d12",
    }
    for page in range(1, pages + 1):
        part = selected.iloc[(page - 1) * PER_PAGE : page * PER_PAGE].copy()
        fig, axes = plt.subplots(len(part), 1, figsize=(18, max(4.2, 3.4 * len(part))), constrained_layout=True)
        axes_list = list(np.atleast_1d(axes))
        for ax, (_, row) in zip(axes_list, part.iterrows(), strict=False):
            vt_symbol = str(row.get("vt_symbol"))
            date = _normalize_day(row.get("date"))
            day = minute_by_symbol.get(vt_symbol, pd.DataFrame())
            if not day.empty and not pd.isna(date):
                day = day[day["bar_date"].eq(date)].copy().sort_values("bar_datetime").head(520).reset_index(drop=True)
            else:
                day = pd.DataFrame()
            if day.empty:
                ax.axis("off")
                ax.text(0.5, 0.5, f"missing minute bars {vt_symbol} {date}", ha="center", va="center")
            else:
                s825._plot_candles(ax, day)
                line_prices = _line_prices(row)
                for key, price in line_prices.items():
                    if np.isfinite(price):
                        linestyle = "-" if key == "entry" else "--" if key == "progress_05r" else ":" if key == "adverse_05r" else "-."
                        ax.axhline(price, color=colors.get(key, "#64748b"), linestyle=linestyle, linewidth=0.9, label=key)
                for idx_col, color, label in [
                    ("progress_bar_index", "#16a34a", "progress first/touch"),
                    ("adverse_bar_index", "#dc2626", "adverse touch"),
                ]:
                    idx = _safe_float(row.get(idx_col))
                    if np.isfinite(idx) and idx >= 0:
                        ax.axvline(int(idx), color=color, linewidth=1.0, alpha=0.8, label=label)
                ticks = np.linspace(0, len(day) - 1, num=min(8, len(day)), dtype=int)
                ax.set_xticks(ticks)
                ax.set_xticklabels([pd.Timestamp(day.loc[pos, "bar_datetime"]).strftime("%H:%M") for pos in ticks], fontsize=7)
                handles, labels = ax.get_legend_handles_labels()
                if handles:
                    dedup = dict(zip(labels, handles))
                    ax.legend(dedup.values(), dedup.keys(), fontsize=7, loc="best")
                ax.grid(True, alpha=0.18)
            ax.set_title(
                (
                    f"{row.get('event_type')} {vt_symbol} {row.get('direction')} "
                    f"{pd.Timestamp(date).date().isoformat() if not pd.isna(date) else 'NA'} "
                    f"first={row.get('first_touch')} r={_safe_float(row.get('r_multiple'), 0):.2f} "
                    f"pnl={_safe_float(row.get('realized_pnl'), 0):.0f} vol={_safe_float(row.get('volume'), 0):.0f}"
                ),
                fontsize=8.2,
                loc="left",
            )
            manifest.append(
                {
                    "page": page,
                    "event_type": row.get("event_type"),
                    "vt_symbol": vt_symbol,
                    "date": pd.Timestamp(date).date().isoformat() if not pd.isna(date) else "",
                    "direction": row.get("direction"),
                    "first_touch": row.get("first_touch"),
                    "r_multiple": _safe_float(row.get("r_multiple")),
                    "realized_pnl": _safe_float(row.get("realized_pnl")),
                    "png": str(ATLAS_TEMPLATE.with_name(ATLAS_TEMPLATE.name.format(page=page))),
                }
            )
        path = ATLAS_TEMPLATE.with_name(ATLAS_TEMPLATE.name.format(page=page))
        fig.savefig(path, dpi=170)
        plt.close(fig)
        paths.append(path)
    return paths, pd.DataFrame(manifest)


def _bucket_stats(events: pd.DataFrame, closed: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if not events.empty:
        for event_type, group in events.groupby("event_type"):
            rows.append(
                {
                    "sample": event_type,
                    "rows": int(len(group)),
                    "products": int(group["product_vt_symbol"].astype(str).nunique()),
                    "years": int(pd.to_datetime(group["date"], errors="coerce").dt.year.nunique()),
                    "progress_first_pct": float(group["first_touch"].eq("progress_first").mean() * 100.0),
                    "adverse_first_pct": float(group["first_touch"].eq("adverse_first").mean() * 100.0),
                    "none_or_missing_pct": float(group["first_touch"].isin(["none", "missing"]).mean() * 100.0),
                    "median_first_30m_directional_r": float(pd.to_numeric(group["first_30m_directional_r"], errors="coerce").median()),
                    "median_entry_day_mfe_r": float(pd.to_numeric(group["entry_day_mfe_r"], errors="coerce").median()),
                    "median_entry_day_mae_r": float(pd.to_numeric(group["entry_day_mae_r"], errors="coerce").median()),
                    "total_realized_pnl": float(pd.to_numeric(group["realized_pnl"], errors="coerce").fillna(0).sum()),
                    "median_r_multiple": float(pd.to_numeric(group["r_multiple"], errors="coerce").median()),
                }
            )
    if not closed.empty:
        closed_data = closed.copy()
        closed_data["r_multiple_num"] = pd.to_numeric(closed_data.get("r_multiple"), errors="coerce")
        closed_data["realized_pnl_num"] = pd.to_numeric(closed_data.get("realized_pnl"), errors="coerce")
        for sample, frame in [
            ("official_all_closed_lots", closed_data),
            ("official_r_ge_3", closed_data[closed_data["r_multiple_num"].ge(3.0)]),
            ("official_r_le_minus_1", closed_data[closed_data["r_multiple_num"].le(-1.0)]),
        ]:
            rows.append(
                {
                    "sample": sample,
                    "rows": int(len(frame)),
                    "products": int(frame["product"].astype(str).nunique()) if not frame.empty and "product" in frame.columns else 0,
                    "years": int(pd.to_datetime(frame["entry_date"], errors="coerce").dt.year.nunique()) if not frame.empty else 0,
                    "progress_first_pct": np.nan,
                    "adverse_first_pct": np.nan,
                    "none_or_missing_pct": np.nan,
                    "median_first_30m_directional_r": np.nan,
                    "median_entry_day_mfe_r": np.nan,
                    "median_entry_day_mae_r": np.nan,
                    "total_realized_pnl": float(frame["realized_pnl_num"].fillna(0).sum()) if not frame.empty else 0.0,
                    "median_r_multiple": float(frame["r_multiple_num"].median()) if not frame.empty else np.nan,
                }
            )
    return pd.DataFrame(rows)


def _summary(curve: pd.DataFrame, closed: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    cap_count = int(events["event_type"].eq("broker10_cap").sum()) if not events.empty else 0
    row = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "window_id": FULL_WINDOW_ID,
        "start": START.date().isoformat(),
        "end": END.date().isoformat(),
        "end_equity": float(pd.to_numeric(curve["account_equity"], errors="coerce").iloc[-1]),
        "total_return_pct": float((pd.to_numeric(curve["account_equity"], errors="coerce").iloc[-1] / CAPITAL - 1.0) * 100.0),
        "max_dd_pct": float(pd.to_numeric(curve["drawdown_pct"], errors="coerce").min()),
        "max_broker10_margin_to_equity_pct": float(pd.to_numeric(curve["broker10_margin_to_equity_pct"], errors="coerce").max()),
        "broker10_cap_events": cap_count,
        "closed_lots": int(len(closed)),
        "top_winner_events": int(events["event_type"].eq("top_winner").sum()) if not events.empty else 0,
        "top_loser_events": int(events["event_type"].eq("top_loser").sum()) if not events.empty else 0,
        "stage004_restore_events": int(events["event_type"].astype(str).str.startswith("stage004_restore").sum()) if not events.empty else 0,
        "decision": "stage005_readonly_no_trade_rule_yet",
    }
    return pd.DataFrame([row])


def _decision(summary: pd.DataFrame, bucket_stats: pd.DataFrame, atlas_paths: list[Path]) -> dict[str, Any]:
    row = summary.iloc[0].to_dict()
    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "decision": "stage005_readonly_no_trade_rule_yet",
        "why": (
            "This stage is visual attribution only. It produced evidence for cap events, top winners, "
            "top losers and Stage004 restore failures, but no new trading rule is promoted."
        ),
        "summary": {key: _json_safe(value) for key, value in row.items()},
        "bucket_stats": bucket_stats.to_dict(orient="records") if not bucket_stats.empty else [],
        "paths": {
            "summary": str(SUMMARY_OUT),
            "curve": str(CURVE_OUT),
            "closed_lots": str(CLOSED_LOTS_OUT),
            "event_features": str(EVENTS_OUT),
            "bucket_stats": str(BUCKET_OUT),
            "path_chart": str(PATH_CHART_OUT),
            "atlas_manifest": str(ATLAS_MANIFEST_OUT),
            "atlas_pages": [str(path) for path in atlas_paths],
            "report": str(REPORT_OUT),
        },
        "next_step": (
            "Read the atlas by category. Only if a cross-product, cross-year, entry-time-visible "
            "structure appears should a new frozen candidate be written."
        ),
    }
    return decision


def _write_report(summary: pd.DataFrame, bucket_stats: pd.DataFrame, events: pd.DataFrame, atlas_paths: list[Path], decision: dict[str, Any]) -> None:
    lines = [
        f"# {STAGE} C9/15w signal-quality visual forensics",
        "",
        f"- line_id: `{LINE_ID}`",
        f"- model_tag: `{MODEL_TAG}`",
        f"- official live: `{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`",
        "- stage nature: read-only attribution, no A/B candidate, no trading rule.",
        f"- decision: `{decision['decision']}`",
        "",
        "## Summary",
        "",
        _md_table(summary, max_rows=10),
        "",
        "## Bucket Stats",
        "",
        _md_table(bucket_stats, max_rows=20) if not bucket_stats.empty else "No bucket stats.",
        "",
        "## Selected Event Evidence",
        "",
        _md_table(
            _event_sample(events)[
                [
                    "event_type",
                    "date",
                    "vt_symbol",
                    "direction",
                    "first_touch",
                    "first_30m_directional_r",
                    "entry_day_mfe_r",
                    "entry_day_mae_r",
                    "r_multiple",
                    "realized_pnl",
                    "volume",
                ]
            ],
            max_rows=30,
        )
        if not events.empty
        else "No selected events.",
        "",
        "## Visual Outputs",
        "",
        f"- path marker chart: `{PATH_CHART_OUT}`",
        f"- atlas pages: `{len(atlas_paths)}`",
        "",
        "## Judgment",
        "",
        "- This stage intentionally does not create a candidate rule.",
        "- Any next rule must come from a visible structure that is present across products and years, not from a single failed window.",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    metadata = s513._metadata()
    vt_symbols = set(str(item) for item in metadata["vt_symbols"])
    minute_bars = s825._load_minute_bars(vt_symbols)
    minute_by_symbol = s825._minute_groups(minute_bars)
    s827._GLOBAL_MINUTE_BY_SYMBOL = minute_by_symbol

    curve = _load_official_curve()
    closed = _load_core_closed_lots()

    cap_events = _cap_events_from_stage004()
    lot_events = _lot_events(closed)
    restore_events = _stage004_restore_events()
    event_parts = [frame for frame in [cap_events, lot_events, restore_events] if not frame.empty]
    events = pd.concat(event_parts, ignore_index=True, sort=False) if event_parts else pd.DataFrame()
    events = _add_intraday_features(events, minute_by_symbol)
    bucket_stats = _bucket_stats(events, closed)
    summary = _summary(curve, closed, events)

    _plot_path(curve, events)
    atlas_paths, atlas_manifest = _plot_atlas(events, minute_by_symbol)
    decision = _decision(summary, bucket_stats, atlas_paths)

    summary.to_csv(SUMMARY_OUT, index=False, encoding="utf-8-sig")
    curve.to_csv(CURVE_OUT, index=False, encoding="utf-8-sig")
    pd.DataFrame([{"note": "Stage005 uses Stage004 A curve as official path; no fresh official trade replay was written."}]).to_csv(
        TRADES_OUT, index=False, encoding="utf-8-sig"
    )
    pd.DataFrame([{"note": "Stage005 uses Stage847/C9 core closed_lots only for minute-shape reference."}]).to_csv(
        ENTRY_RISK_OUT, index=False, encoding="utf-8-sig"
    )
    cap_events.to_csv(TRADE_EVENTS_OUT, index=False, encoding="utf-8-sig")
    closed.to_csv(CLOSED_LOTS_OUT, index=False, encoding="utf-8-sig")
    events.to_csv(EVENTS_OUT, index=False, encoding="utf-8-sig")
    bucket_stats.to_csv(BUCKET_OUT, index=False, encoding="utf-8-sig")
    atlas_manifest.to_csv(ATLAS_MANIFEST_OUT, index=False, encoding="utf-8-sig")
    DECISION_OUT.write_text(json.dumps(decision, ensure_ascii=False, indent=2, default=_json_safe), encoding="utf-8")
    _write_report(summary, bucket_stats, events, atlas_paths, decision)
    print(json.dumps(decision, ensure_ascii=False, indent=2, default=_json_safe))


if __name__ == "__main__":
    main()
