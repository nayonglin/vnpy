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
import analyze_qmt_roll_stage826_stage819_intraday_ac_overlay as s826
import qmt_roll_official_candidate_stage819_30w_config as stage819_cfg


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage834"
MODEL_TAG = "stage834_stage819_or15_confirmation_forensics_v1"
OUTPUT_PREFIX = "qmt_roll_stage834_stage819_or15_confirmation_forensics"

START = pd.Timestamp("2018-01-01")
END = pd.Timestamp("2026-05-29")
CAPITAL = stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_CAPITAL

OPENING_RANGE_BARS = 15
CONFIRM_HOLD_BARS = 5
MAX_ATTEMPTS = 2
ATLAS_RULE_ID = "C6_or15_close_confirm_retry2"
PER_PAGE = 4
MAX_ATLAS_PAGES = 8

STAGE825_FEATURES_PATH = OUTPUT_DIR / (
    "qmt_roll_stage825_stage819_intraday_rule_forensics_intraday_features_"
    "stage825_stage819_intraday_rule_forensics_v1.csv"
)
STAGE825_SUMMARY_PATH = OUTPUT_DIR / (
    "qmt_roll_stage825_stage819_intraday_rule_forensics_summary_"
    "stage825_stage819_intraday_rule_forensics_v1.csv"
)

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
LOT_OUTCOMES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_lot_outcomes_{MODEL_TAG}.csv"
EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_events_{MODEL_TAG}.csv"
ACTION_STATS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_action_stats_{MODEL_TAG}.csv"
YEARLY_DELTA_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_yearly_delta_{MODEL_TAG}.csv"
RULE_QUALITY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rule_quality_{MODEL_TAG}.csv"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_delta_chart_{MODEL_TAG}.png"
ATLAS_MANIFEST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"
CHART_PATH_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_page{{page:03d}}_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _safe_float(value: Any, default: float = np.nan) -> float:
    return s825._safe_float(value, default=default)


def _date(value: Any) -> pd.Timestamp:
    return pd.Timestamp(value).normalize()


def _direction_sign(direction: Any) -> float:
    return 1.0 if str(direction) == "long" else -1.0


def _load_stage825() -> tuple[pd.DataFrame, pd.DataFrame]:
    missing = [path for path in (STAGE825_FEATURES_PATH, STAGE825_SUMMARY_PATH) if not path.exists()]
    if missing:
        raise RuntimeError(
            "Stage825 outputs are required before Stage834. Missing: "
            + ", ".join(str(path) for path in missing)
        )
    features = pd.read_csv(STAGE825_FEATURES_PATH, encoding="utf-8-sig")
    summary = pd.read_csv(STAGE825_SUMMARY_PATH, encoding="utf-8-sig")
    for column in ("entry_date", "exit_date"):
        features[column] = pd.to_datetime(features[column], errors="coerce").dt.normalize()
    numeric_columns = [
        "entry_price",
        "exit_price",
        "volume",
        "size",
        "realized_pnl",
        "risk_amount",
        "r_multiple",
        "entry_risk_distance_pct",
        "risk_pct",
    ]
    for column in numeric_columns:
        if column in features.columns:
            features[column] = pd.to_numeric(features[column], errors="coerce")
    return features, summary


def _load_minute_bars(features: pd.DataFrame) -> pd.DataFrame:
    vt_symbols = set(features["vt_symbol"].astype(str).dropna().unique())
    return s825._load_minute_bars(vt_symbols)


def _entry_day_bars(row: pd.Series, minute_by_symbol: dict[str, pd.DataFrame]) -> pd.DataFrame:
    bars = minute_by_symbol.get(str(row["vt_symbol"]), pd.DataFrame())
    if bars.empty:
        return pd.DataFrame()
    entry_date = _date(row["entry_date"])
    return bars[bars["bar_date"].eq(entry_date)].copy().reset_index(drop=True)


def _outside_close(row: Any, direction: str, or_high: float, or_low: float) -> bool:
    close = float(row.close)
    return close >= or_high if direction == "long" else close <= or_low


def _inside_reclaim_close(row: Any, direction: str, or_high: float, or_low: float) -> bool:
    close = float(row.close)
    return close < or_high if direction == "long" else close > or_low


def _stop_hit(row: Any, direction: str, stop_price: float) -> bool:
    if direction == "long":
        return float(row.low) <= stop_price
    return float(row.high) >= stop_price


def _event(
    *,
    rule_id: str,
    row: pd.Series,
    event_type: str,
    event_time: Any,
    price: float,
    note: str,
    attempt: int,
) -> dict[str, Any]:
    return {
        "rule_id": rule_id,
        "lot_id": int(row["lot_id"]),
        "vt_symbol": str(row["vt_symbol"]),
        "direction": str(row["direction"]),
        "event_type": event_type,
        "event_time": pd.Timestamp(event_time).isoformat() if event_time is not None and event_time != "" else "",
        "event_date": _date(event_time).strftime("%Y-%m-%d") if event_time is not None and event_time != "" else "",
        "price": float(price) if np.isfinite(price) else np.nan,
        "attempt": int(attempt),
        "note": note,
    }


def _gross_trade_pnl(
    *,
    direction: str,
    entry_price: float,
    exit_price: float,
    size: float,
    volume: float,
) -> float:
    return s826._gross_trade_pnl(
        direction=direction,
        entry_price=entry_price,
        exit_price=exit_price,
        size=size,
        volume=volume,
    )


def _candidate_entry_price(item: Any, direction: str, or_high: float, or_low: float) -> float:
    # Use the confirming bar close. This is intentionally conservative versus
    # assuming a fill exactly at the range boundary after the bar has closed.
    return float(item.close)


def _simulate_or_rule(
    row: pd.Series,
    entry_day: pd.DataFrame,
    *,
    rule_id: str,
    mode: str,
    metadata: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    direction = str(row["direction"])
    entry_date = _date(row["entry_date"])
    original_exit_date = _date(row["exit_date"])
    original_exit_price = _safe_float(row.get("exit_price"))
    original_gross = _safe_float(row.get("realized_pnl"), 0.0)
    base_exec_cost = s826._exec_slippage(row, metadata)
    original_slippage = 2.0 * base_exec_cost
    original_net = original_gross - original_slippage
    size = _safe_float(row.get("size"), 1.0)
    volume = _safe_float(row.get("volume"), 0.0)

    if entry_day.empty:
        result = {
            "action": "missing_minutes_keep_original",
            "minute_covered": 0,
            "or_high": np.nan,
            "or_low": np.nan,
            "or_width_pct": np.nan,
            "attempt_count": 1,
            "stop_count": 0,
            "final_open": 1,
            "final_entry_price": _safe_float(row.get("entry_price")),
            "final_exit_date": original_exit_date,
            "final_exit_price": original_exit_price,
            "adjusted_gross": original_gross,
            "adjusted_slippage": original_slippage,
            "adjusted_net": original_net,
            "first_event_time": "",
        }
        return result, []

    if len(entry_day) <= OPENING_RANGE_BARS:
        result = {
            "action": "insufficient_opening_range_keep_original",
            "minute_covered": 1,
            "or_high": np.nan,
            "or_low": np.nan,
            "or_width_pct": np.nan,
            "attempt_count": 1,
            "stop_count": 0,
            "final_open": 1,
            "final_entry_price": _safe_float(row.get("entry_price")),
            "final_exit_date": original_exit_date,
            "final_exit_price": original_exit_price,
            "adjusted_gross": original_gross,
            "adjusted_slippage": original_slippage,
            "adjusted_net": original_net,
            "first_event_time": "",
        }
        return result, []

    opening = entry_day.head(OPENING_RANGE_BARS)
    after_opening = entry_day.iloc[OPENING_RANGE_BARS:].reset_index(drop=True)
    or_high = float(opening["high"].max())
    or_low = float(opening["low"].min())
    ref_price = _safe_float(row.get("entry_price"))
    or_width_pct = (or_high - or_low) / ref_price if ref_price > 0 else np.nan
    stop_price = or_low if direction == "long" else or_high

    events: list[dict[str, Any]] = []
    gross_parts: list[float] = []
    position_open = False
    current_entry = np.nan
    attempt_count = 0
    stop_count = 0
    final_open = False
    final_entry_price = np.nan
    first_event_time = ""
    pending_breakout: dict[str, Any] | None = None

    for item in after_opening.itertuples(index=False):
        if position_open:
            if _stop_hit(item, direction, stop_price):
                stop_count += 1
                pnl = _gross_trade_pnl(
                    direction=direction,
                    entry_price=float(current_entry),
                    exit_price=stop_price,
                    size=size,
                    volume=volume,
                )
                gross_parts.append(pnl)
                events.append(
                    _event(
                        rule_id=rule_id,
                        row=row,
                        event_type="stop",
                        event_time=item.bar_datetime,
                        price=stop_price,
                        note="opposite side of OR15 hit after confirmed entry",
                        attempt=attempt_count,
                    )
                )
                if not first_event_time:
                    first_event_time = pd.Timestamp(item.bar_datetime).isoformat()
                position_open = False
                current_entry = np.nan
                pending_breakout = None
            continue

        if attempt_count >= MAX_ATTEMPTS:
            continue

        if mode == "close":
            if _outside_close(item, direction, or_high, or_low):
                attempt_count += 1
                current_entry = _candidate_entry_price(item, direction, or_high, or_low)
                position_open = True
                events.append(
                    _event(
                        rule_id=rule_id,
                        row=row,
                        event_type="entry",
                        event_time=item.bar_datetime,
                        price=current_entry,
                        note="close confirmed outside OR15",
                        attempt=attempt_count,
                    )
                )
                if not first_event_time:
                    first_event_time = pd.Timestamp(item.bar_datetime).isoformat()
            continue

        if mode == "hold5":
            if pending_breakout is None:
                if _outside_close(item, direction, or_high, or_low):
                    pending_breakout = {"start": item.bar_datetime, "count": 1}
                continue
            if _inside_reclaim_close(item, direction, or_high, or_low):
                events.append(
                    _event(
                        rule_id=rule_id,
                        row=row,
                        event_type="reclaim_cancel",
                        event_time=item.bar_datetime,
                        price=float(item.close),
                        note="breakout close returned inside OR15 before hold confirmation",
                        attempt=attempt_count + 1,
                    )
                )
                pending_breakout = None
                continue
            pending_breakout["count"] = int(pending_breakout["count"]) + 1
            if int(pending_breakout["count"]) >= CONFIRM_HOLD_BARS:
                attempt_count += 1
                current_entry = _candidate_entry_price(item, direction, or_high, or_low)
                position_open = True
                events.append(
                    _event(
                        rule_id=rule_id,
                        row=row,
                        event_type="entry",
                        event_time=item.bar_datetime,
                        price=current_entry,
                        note=f"close stayed outside OR15 for {CONFIRM_HOLD_BARS} bars",
                        attempt=attempt_count,
                    )
                )
                if not first_event_time:
                    first_event_time = pd.Timestamp(item.bar_datetime).isoformat()
                pending_breakout = None
            continue

        raise ValueError(f"Unsupported OR confirmation mode: {mode}")

    if position_open and np.isfinite(current_entry):
        final_open = True
        final_entry_price = float(current_entry)
        gross_parts.append(
            _gross_trade_pnl(
                direction=direction,
                entry_price=final_entry_price,
                exit_price=original_exit_price,
                size=size,
                volume=volume,
            )
        )
        final_exit_date = original_exit_date
        final_exit_price = original_exit_price
    else:
        final_exit_date = entry_date if stop_count or attempt_count else pd.NaT
        final_exit_price = stop_price if stop_count else np.nan

    adjusted_gross = float(sum(gross_parts))
    adjusted_slippage = (attempt_count + stop_count + int(final_open)) * base_exec_cost
    adjusted_net = adjusted_gross - adjusted_slippage

    if attempt_count == 0:
        action = "no_confirm_no_trade"
    elif final_open and stop_count == 0:
        action = "confirmed_survived_to_original_exit"
    elif final_open and stop_count > 0:
        action = "stopped_reentered_survived"
    else:
        action = "confirmed_then_stopped_no_final_reentry"

    result = {
        "action": action,
        "minute_covered": 1,
        "or_high": or_high,
        "or_low": or_low,
        "or_width_pct": or_width_pct,
        "attempt_count": attempt_count,
        "stop_count": stop_count,
        "final_open": int(final_open),
        "final_entry_price": final_entry_price,
        "final_exit_date": final_exit_date,
        "final_exit_price": final_exit_price,
        "adjusted_gross": adjusted_gross,
        "adjusted_slippage": adjusted_slippage,
        "adjusted_net": adjusted_net,
        "first_event_time": first_event_time,
    }
    return result, events


def _simulate_all(features: pd.DataFrame, minute_bars: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    metadata = s513._metadata()
    minute_by_symbol = s825._minute_groups(minute_bars)
    specs = [
        ("C6_or15_close_confirm_retry2", "close"),
        ("C7_or15_hold5_confirm_retry2", "hold5"),
    ]
    lot_rows: list[dict[str, Any]] = []
    event_rows: list[dict[str, Any]] = []
    for _, row in features.iterrows():
        entry_day = _entry_day_bars(row, minute_by_symbol)
        for rule_id, mode in specs:
            result, events = _simulate_or_rule(row, entry_day, rule_id=rule_id, mode=mode, metadata=metadata)
            original_gross = _safe_float(row.get("realized_pnl"), 0.0)
            base_exec_cost = s826._exec_slippage(row, metadata)
            original_slippage = 2.0 * base_exec_cost
            original_net = original_gross - original_slippage
            risk_amount = _safe_float(row.get("risk_amount"))
            adjusted_r = result["adjusted_gross"] / risk_amount if risk_amount and risk_amount > 0 else np.nan
            lot_rows.append(
                {
                    "rule_id": rule_id,
                    "lot_id": int(row["lot_id"]),
                    "vt_symbol": str(row["vt_symbol"]),
                    "product": str(row.get("product", "")),
                    "direction": str(row["direction"]),
                    "entry_date": _date(row["entry_date"]).strftime("%Y-%m-%d"),
                    "exit_date": _date(row["exit_date"]).strftime("%Y-%m-%d"),
                    "entry_year": int(_date(row["entry_date"]).year),
                    "entry_price": _safe_float(row.get("entry_price")),
                    "exit_price": _safe_float(row.get("exit_price")),
                    "volume": _safe_float(row.get("volume"), 0.0),
                    "risk_amount": risk_amount,
                    "original_gross": original_gross,
                    "original_slippage": original_slippage,
                    "original_net": original_net,
                    "original_r_multiple": _safe_float(row.get("r_multiple")),
                    "adjusted_gross": result["adjusted_gross"],
                    "adjusted_slippage": result["adjusted_slippage"],
                    "adjusted_net": result["adjusted_net"],
                    "gross_delta": result["adjusted_gross"] - original_gross,
                    "net_delta": result["adjusted_net"] - original_net,
                    "adjusted_r_multiple": adjusted_r,
                    "action": result["action"],
                    "minute_covered": int(result["minute_covered"]),
                    "entry_day_minute_bars": int(len(entry_day)),
                    "or_high": result["or_high"],
                    "or_low": result["or_low"],
                    "or_width_pct": result["or_width_pct"],
                    "attempt_count": int(result["attempt_count"]),
                    "stop_count": int(result["stop_count"]),
                    "final_open": int(result["final_open"]),
                    "final_entry_price": result["final_entry_price"],
                    "final_exit_date": (
                        _date(result["final_exit_date"]).strftime("%Y-%m-%d")
                        if not pd.isna(result["final_exit_date"])
                        else ""
                    ),
                    "final_exit_price": result["final_exit_price"],
                    "first_event_time": result["first_event_time"],
                    "signal": str(row.get("signal", "")),
                    "exit_reason": str(row.get("exit_reason", "")),
                    "entry_day_first_1p0r_outcome": str(row.get("entry_day_first_1p0r_outcome", "")),
                    "opening_range_breakout_confirmed": row.get("opening_range_breakout_confirmed", np.nan),
                }
            )
            event_rows.extend(events)
    return pd.DataFrame(lot_rows), pd.DataFrame(event_rows)


def _summaries(lots: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    action_rows: list[dict[str, Any]] = []
    yearly_rows: list[dict[str, Any]] = []
    quality_rows: list[dict[str, Any]] = []
    for rule_id, group in lots.groupby("rule_id", sort=False):
        covered = group[group["minute_covered"].eq(1)]
        no_trade = covered[covered["action"].eq("no_confirm_no_trade")]
        avoided_loser = no_trade[no_trade["original_gross"].lt(0)]
        missed_winner = no_trade[no_trade["original_gross"].gt(0)]
        stopped = covered[covered["stop_count"].gt(0)]
        rows.append(
            {
                "rule_id": rule_id,
                "lots_total": int(len(group)),
                "minute_covered_lots": int(len(covered)),
                "missing_lots_kept_original": int(len(group) - len(covered)),
                "covered_pct": float(len(covered) / len(group) * 100.0) if len(group) else 0.0,
                "original_net_all": float(group["original_net"].sum()),
                "adjusted_net_all": float(group["adjusted_net"].sum()),
                "net_delta_all": float(group["net_delta"].sum()),
                "original_net_covered": float(covered["original_net"].sum()),
                "adjusted_net_covered": float(covered["adjusted_net"].sum()),
                "net_delta_covered": float(covered["net_delta"].sum()),
                "covered_delta_per_lot": float(covered["net_delta"].mean()) if len(covered) else np.nan,
                "no_confirm_lots": int(len(no_trade)),
                "no_confirm_pct_of_covered": float(len(no_trade) / len(covered) * 100.0) if len(covered) else 0.0,
                "avoided_loser_lots": int(len(avoided_loser)),
                "avoided_loser_original_net": float(avoided_loser["original_net"].sum()),
                "missed_winner_lots": int(len(missed_winner)),
                "missed_winner_original_net": float(missed_winner["original_net"].sum()),
                "stopped_lots": int(len(stopped)),
                "stop_count": int(stopped["stop_count"].sum()),
                "final_open_lots": int(covered["final_open"].sum()),
                "attempt_count": int(covered["attempt_count"].sum()),
                "mean_or_width_pct": float(covered["or_width_pct"].mean()) if len(covered) else np.nan,
                "decision": "diagnostic_only_not_promoted",
            }
        )
        for action, action_group in group.groupby("action", sort=False):
            action_rows.append(
                {
                    "rule_id": rule_id,
                    "action": action,
                    "lots": int(len(action_group)),
                    "original_net": float(action_group["original_net"].sum()),
                    "adjusted_net": float(action_group["adjusted_net"].sum()),
                    "net_delta": float(action_group["net_delta"].sum()),
                    "avg_net_delta": float(action_group["net_delta"].mean()) if len(action_group) else np.nan,
                    "median_original_r": float(action_group["original_r_multiple"].median()),
                    "median_adjusted_r": float(action_group["adjusted_r_multiple"].median()),
                }
            )
        for year, year_group in group.groupby("entry_year", sort=True):
            yearly_rows.append(
                {
                    "rule_id": rule_id,
                    "entry_year": int(year),
                    "lots": int(len(year_group)),
                    "minute_covered_lots": int(year_group["minute_covered"].sum()),
                    "original_net": float(year_group["original_net"].sum()),
                    "adjusted_net": float(year_group["adjusted_net"].sum()),
                    "net_delta": float(year_group["net_delta"].sum()),
                    "no_confirm_lots": int(year_group["action"].eq("no_confirm_no_trade").sum()),
                    "stopped_lots": int(year_group["stop_count"].gt(0).sum()),
                }
            )
        for key, quality_group in covered.groupby("entry_day_first_1p0r_outcome", dropna=False):
            quality_rows.append(
                {
                    "rule_id": rule_id,
                    "entry_day_first_1p0r_outcome": str(key),
                    "lots": int(len(quality_group)),
                    "original_net": float(quality_group["original_net"].sum()),
                    "adjusted_net": float(quality_group["adjusted_net"].sum()),
                    "net_delta": float(quality_group["net_delta"].sum()),
                    "no_confirm_lots": int(quality_group["action"].eq("no_confirm_no_trade").sum()),
                    "stopped_lots": int(quality_group["stop_count"].gt(0).sum()),
                }
            )
    return (
        pd.DataFrame(rows),
        pd.DataFrame(action_rows),
        pd.DataFrame(yearly_rows),
        pd.DataFrame(quality_rows),
    )


def _plot_delta_chart(summary: pd.DataFrame, action_stats: pd.DataFrame) -> None:
    if summary.empty:
        return
    fig, axes = plt.subplots(1, 2, figsize=(15, 5), constrained_layout=True)
    summary_plot = summary.set_index("rule_id")
    axes[0].bar(summary_plot.index, summary_plot["net_delta_covered"], color=["#2563eb", "#7c3aed"])
    axes[0].axhline(0, color="#111827", linewidth=0.8)
    axes[0].set_title("Covered-Lot Net Delta")
    axes[0].tick_params(axis="x", rotation=12)
    axes[0].grid(True, axis="y", alpha=0.2)
    pivot = action_stats.pivot_table(index="action", columns="rule_id", values="net_delta", aggfunc="sum").fillna(0.0)
    pivot.plot(kind="barh", ax=axes[1], color=["#2563eb", "#7c3aed"])
    axes[1].axvline(0, color="#111827", linewidth=0.8)
    axes[1].set_title("Net Delta By Action")
    axes[1].grid(True, axis="x", alpha=0.2)
    fig.suptitle("Stage834 OR15 confirmation diagnostic; lot-level overlay only", fontsize=13)
    fig.savefig(CHART_PATH, dpi=150)
    plt.close(fig)


def _plot_atlas(
    lots: pd.DataFrame,
    events: pd.DataFrame,
    minute_bars: pd.DataFrame,
) -> tuple[list[Path], pd.DataFrame]:
    rule_lots = lots[lots["rule_id"].eq(ATLAS_RULE_ID)].copy()
    if rule_lots.empty:
        return [], pd.DataFrame()
    rule_lots["abs_net_delta"] = pd.to_numeric(rule_lots["net_delta"], errors="coerce").abs()
    rule_lots = rule_lots[rule_lots["minute_covered"].eq(1)].sort_values("abs_net_delta", ascending=False)
    max_rows = PER_PAGE * MAX_ATLAS_PAGES
    rule_lots = rule_lots.head(max_rows)
    minute_by_symbol = s825._minute_groups(minute_bars)
    event_map = {
        int(lot_id): group.copy()
        for lot_id, group in events[events["rule_id"].eq(ATLAS_RULE_ID)].groupby("lot_id", sort=False)
    } if not events.empty else {}
    pages = int(math.ceil(len(rule_lots) / PER_PAGE)) if len(rule_lots) else 0
    paths: list[Path] = []
    records: list[dict[str, Any]] = []
    for page in range(1, pages + 1):
        part = rule_lots.iloc[(page - 1) * PER_PAGE : page * PER_PAGE].copy()
        fig, axes = plt.subplots(len(part), 1, figsize=(18, max(4, len(part) * 3.2)), constrained_layout=True)
        if len(part) == 1:
            axes = [axes]
        for ax, (_, row) in zip(axes, part.iterrows(), strict=False):
            lot_id = int(row["lot_id"])
            vt_symbol = str(row["vt_symbol"])
            entry_date = _date(row["entry_date"])
            bars = minute_by_symbol.get(vt_symbol, pd.DataFrame())
            entry_day = bars[bars["bar_date"].eq(entry_date)].copy().head(240).reset_index(drop=True)
            if entry_day.empty:
                ax.axis("off")
                continue
            s825._plot_candles(ax, entry_day)
            if len(entry_day) >= OPENING_RANGE_BARS:
                opening = entry_day.head(OPENING_RANGE_BARS)
                ax.axhline(float(opening["high"].max()), color="#7c3aed", linestyle="--", linewidth=0.85)
                ax.axhline(float(opening["low"].min()), color="#7c3aed", linestyle="--", linewidth=0.85)
                ax.axvspan(0, OPENING_RANGE_BARS - 1, color="#fef3c7", alpha=0.22)
            ax.axhline(float(row["entry_price"]), color="#2563eb", linewidth=0.85, alpha=0.75)
            lot_events = event_map.get(lot_id, pd.DataFrame())
            if not lot_events.empty:
                for event in lot_events.itertuples(index=False):
                    event_time = pd.to_datetime(event.event_time, errors="coerce")
                    if pd.isna(event_time):
                        continue
                    matches = entry_day.index[entry_day["bar_datetime"].eq(event_time)]
                    if len(matches) == 0:
                        continue
                    x = int(matches[0])
                    color = "#16a34a" if event.event_type == "entry" else "#dc2626"
                    marker = "^" if event.event_type == "entry" else "x"
                    ax.scatter([x], [float(event.price)], s=34, c=color, marker=marker, zorder=5)
                    ax.text(x, float(event.price), str(event.event_type), fontsize=7, color=color)
            ticks = np.linspace(0, len(entry_day) - 1, num=min(7, len(entry_day)), dtype=int)
            ax.set_xticks(ticks)
            ax.set_xticklabels([pd.Timestamp(entry_day.loc[pos, "bar_datetime"]).strftime("%H:%M") for pos in ticks], fontsize=7)
            ax.grid(True, alpha=0.18, linewidth=0.5)
            ax.tick_params(axis="y", labelsize=7)
            ax.set_title(
                (
                    f"lot{lot_id} {vt_symbol} {row['direction']} {entry_date:%Y-%m-%d} "
                    f"action={row['action']} original={row['original_net']:,.0f} "
                    f"adjusted={row['adjusted_net']:,.0f} delta={row['net_delta']:,.0f}"
                ),
                fontsize=8.5,
                loc="left",
            )
            records.append({"lot_id": lot_id, "chart_page": page, "chart_missing_minutes": 0})
        fig.suptitle(
            "Stage834 OR15 close-confirm atlas (purple=OR15, blue=original entry, green=confirmed entry, red=stop)",
            fontsize=13,
        )
        path = Path(str(CHART_PATH_TEMPLATE).format(page=page))
        fig.savefig(path, dpi=150)
        plt.close(fig)
        paths.append(path)
    return paths, pd.DataFrame(records)


def _write_report(
    stage825_summary: pd.DataFrame,
    summary: pd.DataFrame,
    action_stats: pd.DataFrame,
    yearly: pd.DataFrame,
    quality: pd.DataFrame,
    chart_paths: list[Path],
) -> None:
    base = stage825_summary.iloc[0].to_dict() if not stage825_summary.empty else {}
    lines = [
        "# Stage834 Stage819 OR15入场确认/假突破规避只读体检",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 源候选：`{stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION}`",
        f"- 区间：`{START.date()}` 到 `{END.date()}`",
        "- 阶段性质：只读 lot-level overlay；不改正式配置、不连接 CTP、不调用下单。",
        "",
        "## 外部调研判断",
        "",
        "- GitHub ORB 示例和公开资料常见结构是固定开盘区间、突破后入场、反侧止损、收盘前/日内退出。",
        "- Investopedia 对区间突破的提醒是：假突破和回抽很常见，等确认或回抽后再进比抢最早突破更符合稳健逻辑。",
        "- 本阶段只冻结 `OR15`、`close confirm`、`hold5 confirm`、`max_attempts=2` 两个规则形状，不做小数阈值扫描。",
        "",
        "## Stage819基准",
        "",
        _md_table(
            pd.DataFrame(
                [
                    {
                        "end_equity": base.get("end_equity"),
                        "total_return_pct": base.get("total_return_pct"),
                        "max_dd_pct": base.get("max_dd_pct"),
                        "sharpe": base.get("sharpe"),
                        "total_slippage": base.get("total_slippage"),
                        "total_trade_count": base.get("total_trade_count"),
                    }
                ]
            ),
            max_rows=5,
        ),
        "",
        "## 规则总体诊断",
        "",
        _md_table(summary, max_rows=20),
        "",
        "## Action Attribution",
        "",
        _md_table(action_stats, max_rows=50),
        "",
        "## Yearly Delta",
        "",
        _md_table(yearly, max_rows=40),
        "",
        "## Prior C2 Quality Bucket",
        "",
        _md_table(quality, max_rows=40),
        "",
        "## Charts",
        "",
        f"- delta chart：`{CHART_PATH}`",
        *[f"- atlas：`{path}`" for path in chart_paths],
        "",
        "## Judgment",
        "",
        "- 本阶段只证明 OR15 确认形状是否值得进入真实引擎，不产生正式候选。",
        "- 若规则主要靠 `no_confirm_no_trade` 避免少量亏损、同时漏掉更大赢家，则应淘汰。",
        "- 若 covered-lot 净增益为正且 missed winner 可控，下一步才考虑接入真实组合引擎做 A/C。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    features, stage825_summary = _load_stage825()
    minute_bars = _load_minute_bars(features)
    lots, events = _simulate_all(features, minute_bars)
    summary, action_stats, yearly, quality = _summaries(lots)
    _plot_delta_chart(summary, action_stats)
    chart_paths, atlas_manifest = _plot_atlas(lots, events, minute_bars)
    _write_report(stage825_summary, summary, action_stats, yearly, quality, chart_paths)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    lots.to_csv(LOT_OUTCOMES_PATH, index=False, encoding="utf-8-sig")
    events.to_csv(EVENTS_PATH, index=False, encoding="utf-8-sig")
    action_stats.to_csv(ACTION_STATS_PATH, index=False, encoding="utf-8-sig")
    yearly.to_csv(YEARLY_DELTA_PATH, index=False, encoding="utf-8-sig")
    quality.to_csv(RULE_QUALITY_PATH, index=False, encoding="utf-8-sig")
    atlas_manifest.to_csv(ATLAS_MANIFEST_PATH, index=False, encoding="utf-8-sig")

    best_rule = summary.sort_values("net_delta_covered", ascending=False).iloc[0].to_dict() if not summary.empty else {}
    decision_label = (
        "stage834_or15_confirmation_diagnostic_positive_needs_engine_ac"
        if float(best_rule.get("net_delta_covered", 0.0) or 0.0) > 0
        else "stage834_or15_confirmation_not_promoted"
    )
    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "source_candidate": stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION,
        "strategy_changed": False,
        "ctp_connected": False,
        "order_api_called": False,
        "rule_count": int(summary["rule_id"].nunique()) if not summary.empty else 0,
        "best_rule": best_rule,
        "decision": decision_label,
        "overfit_reflection": (
            "Stage834 uses two predeclared OR15 confirmation shapes. The diagnostic itself is not overfit, "
            "but continuing to tune OR length, hold bars, or attempt count from this output would be overfitting."
        ),
        "continue_value": (
            "Continue only if the positive rule has robust covered-lot delta and acceptable missed-winner cost; "
            "then move to full engine A/C. Otherwise abandon OR15 confirmation shape."
        ),
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "lot_outcomes": str(LOT_OUTCOMES_PATH),
            "events": str(EVENTS_PATH),
            "action_stats": str(ACTION_STATS_PATH),
            "yearly_delta": str(YEARLY_DELTA_PATH),
            "rule_quality": str(RULE_QUALITY_PATH),
            "chart": str(CHART_PATH),
            "atlas_manifest": str(ATLAS_MANIFEST_PATH),
            "report": str(REPORT_PATH),
            "atlas_pages": [str(path) for path in chart_paths],
        },
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print("summary")
    print(summary.to_string(index=False))
    print("action_stats")
    print(action_stats.to_string(index=False))


if __name__ == "__main__":
    main()
