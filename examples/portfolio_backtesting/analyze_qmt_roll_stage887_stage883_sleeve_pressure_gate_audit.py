from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage825_stage819_intraday_rule_forensics as s825
import analyze_qmt_roll_stage883_stage882_progress_pyramid_sleeve1_engine as s883
import analyze_qmt_roll_stage885_stage884_holding_pressure_state_audit as s885
import qmt_roll_official_candidate_stage819_30w_config as stage819_cfg


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage887"
MODEL_TAG = "stage887_stage883_sleeve_pressure_gate_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage887_stage883_sleeve_pressure_gate_audit"

C17_ARM = s883.C17_ARM
PER_PAGE = 3
MAX_ATLAS_ROWS = 12

FEATURES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_features_{MODEL_TAG}.csv"
GATE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gate_summary_{MODEL_TAG}.csv"
PRESSURE_ATTRIBUTION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_pressure_attribution_{MODEL_TAG}.csv"
SUMMARY_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_chart_{MODEL_TAG}.png"
ATLAS_MANIFEST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_page{{page:03d}}_{MODEL_TAG}.png"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        if pd.isna(value):
            return default
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if np.isfinite(number) else default


def _load_required_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _parse_local_datetime(values: Any) -> pd.Series:
    series = pd.Series(values)

    def _one(value: Any) -> pd.Timestamp:
        item = pd.to_datetime(value, errors="coerce")
        if pd.isna(item):
            return pd.NaT
        if item.tzinfo is not None:
            return item.tz_convert("Asia/Shanghai").tz_localize(None)
        return item

    return series.map(_one)


def _event_key_columns(prefix: str) -> list[str]:
    if prefix == "event":
        return ["event_date_key", "vt_symbol", "direction", "pyramid_add_price", "pyramid_add_volume"]
    if prefix == "entry":
        return ["entry_date_key", "contract_vt_symbol", "direction", "planned_entry_price", "selected_volume"]
    return ["closed_entry_date_key", "vt_symbol", "direction", "entry_price", "volume"]


def _prepare_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    events = _load_required_csv(s883.PYRAMID_EVENTS_PATH)
    entry_risk = _load_required_csv(s883.ENTRY_RISK_PATH)
    closed_lots = _load_required_csv(s883.CLOSED_LOTS_PATH)
    daily_state = _load_required_csv(s885.DAILY_STATE_PATH)
    vt_symbols = set(events["vt_symbol"].astype(str).dropna().unique())
    minute_bars = s885._load_full_minute_bars(vt_symbols)

    events["event_date"] = _parse_local_datetime(events["datetime"]).dt.normalize()
    events["event_date_key"] = events["event_date"].dt.strftime("%Y-%m-%d")
    events["progress_datetime"] = _parse_local_datetime(events["progress_time"])
    for column in ["pyramid_add_price", "pyramid_add_volume", "estimated_add_pnl", "base_volume_snapshot"]:
        events[column] = pd.to_numeric(events.get(column), errors="coerce")

    entry = entry_risk[entry_risk["layer_kind"].astype(str).eq("stage883_pyramid")].copy()
    entry["entry_date"] = _parse_local_datetime(entry["datetime"]).dt.normalize()
    entry["entry_date_key"] = entry["entry_date"].dt.strftime("%Y-%m-%d")
    for column in [
        "planned_entry_price",
        "selected_volume",
        "estimated_equity",
        "total_margin_in_use_before",
        "actual_margin_amount",
        "projected_total_margin_after",
        "free_capital",
        "limited_balance",
    ]:
        entry[column] = pd.to_numeric(entry.get(column), errors="coerce")

    closed = closed_lots[closed_lots["layer_kind"].astype(str).eq("stage883_pyramid")].copy()
    closed["closed_entry_date"] = pd.to_datetime(closed["entry_date"], errors="coerce").dt.normalize()
    closed["closed_exit_date"] = pd.to_datetime(closed["exit_date"], errors="coerce").dt.normalize()
    closed["closed_entry_date_key"] = closed["closed_entry_date"].dt.strftime("%Y-%m-%d")
    for column in ["entry_price", "volume", "realized_pnl", "r_multiple"]:
        closed[column] = pd.to_numeric(closed.get(column), errors="coerce")

    daily_state["date"] = pd.to_datetime(daily_state["date"], errors="coerce").dt.normalize()
    return events, entry, closed, daily_state, minute_bars


def _product_direction(product: Any, direction: Any) -> str:
    return f"{product}:{direction}"


def _daily_state_with_prev(daily_state: pd.DataFrame) -> pd.DataFrame:
    c17 = daily_state[daily_state["arm"].eq(C17_ARM)].copy().sort_values("date").reset_index(drop=True)
    keep = [
        "date",
        "account_equity",
        "drawdown_pct",
        "curve_broker10_margin_to_equity_pct",
        "top_product_direction",
        "top1_product_direction_broker10_pct_scaled",
        "top3_product_direction_share",
        "holding_pressure_state",
        "next5_return_pct",
        "next20_return_pct",
        "future20_min_return_pct",
        "future20_max_broker10_pct",
    ]
    c17 = c17[keep].copy()
    rename_current = {
        "account_equity": "current_account_equity",
        "drawdown_pct": "current_drawdown_pct",
        "curve_broker10_margin_to_equity_pct": "current_broker10_pct",
        "top_product_direction": "current_top_product_direction",
        "top1_product_direction_broker10_pct_scaled": "current_top1_pct",
        "top3_product_direction_share": "current_top3_share",
        "holding_pressure_state": "current_holding_pressure_state",
    }
    c17 = c17.rename(columns=rename_current)
    prev_cols = [
        "current_account_equity",
        "current_drawdown_pct",
        "current_broker10_pct",
        "current_top_product_direction",
        "current_top1_pct",
        "current_top3_share",
        "current_holding_pressure_state",
    ]
    for column in prev_cols:
        c17[f"prev_{column.replace('current_', '')}"] = c17[column].shift(1)
    c17["prev_date"] = c17["date"].shift(1)
    return c17


def _merge_event_features(
    events: pd.DataFrame,
    entry: pd.DataFrame,
    closed: pd.DataFrame,
    daily_state: pd.DataFrame,
) -> pd.DataFrame:
    event_entry = events.merge(
        entry,
        left_on=_event_key_columns("event"),
        right_on=_event_key_columns("entry"),
        how="left",
        suffixes=("", "_entry"),
    )
    data = event_entry.merge(
        closed,
        left_on=_event_key_columns("event"),
        right_on=_event_key_columns("closed"),
        how="left",
        suffixes=("", "_closed"),
    )
    state = _daily_state_with_prev(daily_state)
    data = data.merge(state, left_on="event_date", right_on="date", how="left", suffixes=("", "_state"))

    data["event_product_direction"] = data.apply(
        lambda row: _product_direction(row.get("product_vt_symbol"), row.get("direction")),
        axis=1,
    )
    equity = pd.to_numeric(data["estimated_equity"], errors="coerce")
    multiplier = float(s885.BROKER_MARGIN_MULTIPLIER)
    data["pre_add_broker10_pct"] = (
        pd.to_numeric(data["total_margin_in_use_before"], errors="coerce") * multiplier / equity * 100.0
    )
    data["add_broker10_pct"] = pd.to_numeric(data["actual_margin_amount"], errors="coerce") * multiplier / equity * 100.0
    data["projected_after_add_broker10_pct"] = (
        pd.to_numeric(data["projected_total_margin_after"], errors="coerce") * multiplier / equity * 100.0
    )
    data["event_product_is_prev_top"] = data["event_product_direction"].eq(data["prev_top_product_direction"])
    data["event_product_is_current_top"] = data["event_product_direction"].eq(data["current_top_product_direction"])
    data["prev_holding_pressure_state"] = data["prev_holding_pressure_state"].map(lambda value: bool(value) if not pd.isna(value) else False)
    data["current_holding_pressure_state"] = data["current_holding_pressure_state"].map(
        lambda value: bool(value) if not pd.isna(value) else False
    )
    data["addon_realized_pnl"] = pd.to_numeric(data["realized_pnl"], errors="coerce")
    stopped_mask = data["addon_realized_pnl"].isna() & data["final_state"].astype(str).eq("pyramid_addon_stopped")
    data.loc[stopped_mask, "addon_realized_pnl"] = pd.to_numeric(data.loc[stopped_mask, "estimated_add_pnl"], errors="coerce")
    data["addon_pnl_source"] = np.where(data["realized_pnl"].notna(), "closed_lot", np.where(stopped_mask, "event_estimate", "unmatched"))
    data["addon_pnl_available"] = data["addon_realized_pnl"].notna()
    data["addon_winner"] = pd.to_numeric(data["addon_realized_pnl"], errors="coerce").gt(0)
    data["addon_loser"] = pd.to_numeric(data["addon_realized_pnl"], errors="coerce").lt(0)
    data["entry_day_stopped"] = data["final_state"].astype(str).eq("pyramid_addon_stopped")

    data["G0_prev_pressure"] = data["prev_holding_pressure_state"]
    data["G1_pre_add_heat80"] = data["pre_add_broker10_pct"].ge(s885.ACCOUNT_HEAT_WATCH_PCT)
    data["G2_projected_after_add_heat80"] = data["projected_after_add_broker10_pct"].ge(s885.ACCOUNT_HEAT_WATCH_PCT)
    data["G3_pre_or_projected_heat80"] = data["G1_pre_add_heat80"] | data["G2_projected_after_add_heat80"]
    data["G4_prev_pressure_or_projected_after_heat80"] = data["G0_prev_pressure"] | data["G2_projected_after_add_heat80"]
    data["G5_prev_pressure_same_product_direction"] = data["G0_prev_pressure"] & data["event_product_is_prev_top"]
    data["A0_current_day_pressure_attribution"] = data["current_holding_pressure_state"]
    data["A1_current_pressure_same_product_direction_attribution"] = (
        data["current_holding_pressure_state"] & data["event_product_is_current_top"]
    )

    pressure_dates = set(
        daily_state[
            daily_state["arm"].eq(C17_ARM) & daily_state["holding_pressure_state"].astype(bool)
        ]["date"]
        .dropna()
        .dt.normalize()
        .tolist()
    )
    pressure_direction_map = {
        pd.Timestamp(row.date).normalize(): str(row.top_product_direction)
        for row in daily_state[
            daily_state["arm"].eq(C17_ARM) & daily_state["holding_pressure_state"].astype(bool)
        ].itertuples(index=False)
    }
    active_pressure_count: list[int] = []
    active_same_direction_count: list[int] = []
    for row in data.itertuples(index=False):
        entry_date = pd.Timestamp(getattr(row, "event_date")).normalize()
        exit_value = getattr(row, "closed_exit_date")
        exit_date = pd.Timestamp(exit_value).normalize() if not pd.isna(exit_value) else entry_date
        dates = [item for item in pressure_dates if entry_date <= item <= exit_date]
        active_pressure_count.append(len(dates))
        active_same_direction_count.append(
            sum(1 for item in dates if pressure_direction_map.get(item) == getattr(row, "event_product_direction"))
        )
    data["active_on_pressure_days"] = active_pressure_count
    data["active_on_same_product_pressure_days"] = active_same_direction_count
    data["ever_active_on_pressure_day"] = data["active_on_pressure_days"].gt(0)
    data["ever_active_on_same_product_pressure_day"] = data["active_on_same_product_pressure_days"].gt(0)
    return data.sort_values(["event_date", "vt_symbol", "progress_datetime"]).reset_index(drop=True)


def _summarize_gate(name: str, data: pd.DataFrame, mask: pd.Series, gate_type: str) -> dict[str, Any]:
    selected = data[mask.fillna(False).astype(bool)].copy()
    pnl = pd.to_numeric(selected["addon_realized_pnl"], errors="coerce").dropna()
    all_pnl = pd.to_numeric(data["addon_realized_pnl"], errors="coerce").dropna()
    return {
        "gate": name,
        "gate_type": gate_type,
        "blocked_events": int(len(selected)),
        "blocked_with_pnl": int(len(pnl)),
        "blocked_event_share": float(len(selected) / len(data)) if len(data) else np.nan,
        "products": int(selected["product_vt_symbol"].nunique()) if not selected.empty else 0,
        "years": int(pd.to_datetime(selected["event_date"], errors="coerce").dt.year.nunique()) if not selected.empty else 0,
        "addon_pnl_blocked_sum": float(pnl.sum()) if len(pnl) else 0.0,
        "skip_proxy_delta": float((-pnl).sum()) if len(pnl) else 0.0,
        "loser_saved": float((-pnl[pnl < 0]).sum()) if len(pnl) else 0.0,
        "winner_cut": float((-pnl[pnl > 0]).sum()) if len(pnl) else 0.0,
        "positive_pnl_share": float(pnl.gt(0).mean()) if len(pnl) else np.nan,
        "entry_day_stopped_share": float(selected["entry_day_stopped"].mean()) if len(selected) else np.nan,
        "median_pre_add_broker10_pct": float(pd.to_numeric(selected["pre_add_broker10_pct"], errors="coerce").median()),
        "median_projected_after_add_broker10_pct": float(
            pd.to_numeric(selected["projected_after_add_broker10_pct"], errors="coerce").median()
        ),
        "active_on_pressure_events": int(selected["ever_active_on_pressure_day"].sum()) if not selected.empty else 0,
        "active_on_same_product_pressure_events": int(selected["ever_active_on_same_product_pressure_day"].sum())
        if not selected.empty
        else 0,
        "share_of_total_addon_pnl_removed": float(pnl.sum() / all_pnl.sum()) if len(pnl) and abs(all_pnl.sum()) > 1e-9 else np.nan,
    }


def _gate_summary(features: pd.DataFrame) -> pd.DataFrame:
    gate_specs = [
        ("G0_prev_pressure", "live_candidate"),
        ("G1_pre_add_heat80", "live_candidate"),
        ("G2_projected_after_add_heat80", "live_candidate"),
        ("G3_pre_or_projected_heat80", "live_candidate"),
        ("G4_prev_pressure_or_projected_after_heat80", "live_candidate"),
        ("G5_prev_pressure_same_product_direction", "live_candidate"),
        ("A0_current_day_pressure_attribution", "attribution_only"),
        ("A1_current_pressure_same_product_direction_attribution", "attribution_only"),
    ]
    rows = [_summarize_gate(name, features, features[name], gate_type) for name, gate_type in gate_specs]
    return pd.DataFrame(rows).sort_values(["gate_type", "skip_proxy_delta"], ascending=[False, False]).reset_index(drop=True)


def _pressure_attribution(features: pd.DataFrame) -> pd.DataFrame:
    if features.empty:
        return pd.DataFrame()
    grouped = (
        features.groupby(["ever_active_on_pressure_day", "ever_active_on_same_product_pressure_day"], dropna=False)
        .agg(
            events=("vt_symbol", "size"),
            products=("product_vt_symbol", "nunique"),
            addon_realized_pnl=("addon_realized_pnl", "sum"),
            positive_pnl_share=("addon_winner", "mean"),
            entry_day_stopped_share=("entry_day_stopped", "mean"),
            median_pre_add_broker10_pct=("pre_add_broker10_pct", "median"),
            median_projected_after_add_broker10_pct=("projected_after_add_broker10_pct", "median"),
            active_on_pressure_days=("active_on_pressure_days", "sum"),
            active_on_same_product_pressure_days=("active_on_same_product_pressure_days", "sum"),
        )
        .reset_index()
    )
    grouped["skip_all_group_proxy_delta"] = -grouped["addon_realized_pnl"]
    return grouped.sort_values("addon_realized_pnl").reset_index(drop=True)


def _plot_summary(features: pd.DataFrame, gate_summary: pd.DataFrame) -> None:
    if features.empty:
        return
    fig, axes = plt.subplots(3, 1, figsize=(16, 12), constrained_layout=True)
    colors = np.where(features["addon_realized_pnl"].fillna(0.0).ge(0), "#16a34a", "#dc2626")
    axes[0].scatter(
        features["pre_add_broker10_pct"],
        features["projected_after_add_broker10_pct"],
        c=colors,
        s=34,
        alpha=0.8,
    )
    axes[0].axhline(s885.ACCOUNT_HEAT_WATCH_PCT, color="#92400e", linestyle=":", linewidth=1.0)
    axes[0].axvline(s885.ACCOUNT_HEAT_WATCH_PCT, color="#92400e", linestyle=":", linewidth=1.0)
    axes[0].set_title("Stage887 sleeve trigger heat: green addon PnL positive, red negative")
    axes[0].set_xlabel("pre-add broker10 pct")
    axes[0].set_ylabel("projected-after-add broker10 pct")
    axes[0].grid(True, alpha=0.25)

    plot_gates = gate_summary.copy()
    x = np.arange(len(plot_gates))
    axes[1].bar(x, plot_gates["skip_proxy_delta"], color="#64748b", label="skip proxy delta")
    ax2 = axes[1].twinx()
    ax2.plot(x, plot_gates["blocked_events"], color="#2563eb", marker="o", label="blocked events")
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(plot_gates["gate"], rotation=25, ha="right")
    axes[1].set_ylabel("skip proxy delta")
    ax2.set_ylabel("blocked events")
    handles1, labels1 = axes[1].get_legend_handles_labels()
    handles2, labels2 = ax2.get_legend_handles_labels()
    axes[1].legend(handles1 + handles2, labels1 + labels2, loc="best", fontsize=8)
    axes[1].grid(True, alpha=0.25)

    time_data = features.sort_values("event_date").copy()
    axes[2].plot(time_data["event_date"], time_data["projected_after_add_broker10_pct"], color="#2563eb", linewidth=0.9)
    pressure_events = time_data[time_data["current_holding_pressure_state"].astype(bool)]
    axes[2].scatter(
        pressure_events["event_date"],
        pressure_events["projected_after_add_broker10_pct"],
        color="#dc2626",
        s=28,
        label="current-day pressure attribution",
    )
    axes[2].axhline(s885.ACCOUNT_HEAT_WATCH_PCT, color="#92400e", linestyle=":", linewidth=1.0)
    axes[2].set_title("Sleeve trigger projected heat over time")
    axes[2].set_ylabel("projected broker10 pct")
    axes[2].legend(loc="best", fontsize=8)
    axes[2].grid(True, alpha=0.25)
    fig.savefig(SUMMARY_CHART_PATH, dpi=150)
    plt.close(fig)


def _select_atlas_rows(features: pd.DataFrame) -> pd.DataFrame:
    if features.empty:
        return pd.DataFrame()
    risky_losers = features[
        features["G4_prev_pressure_or_projected_after_heat80"].astype(bool)
        & features["addon_loser"].astype(bool)
    ].copy()
    risky_losers["atlas_bucket"] = "live_gate_loser_saved"
    risky_losers = risky_losers.sort_values("addon_realized_pnl", ascending=True).head(MAX_ATLAS_ROWS // 2)

    risky_winners = features[
        features["G4_prev_pressure_or_projected_after_heat80"].astype(bool)
        & features["addon_winner"].astype(bool)
    ].copy()
    risky_winners["atlas_bucket"] = "live_gate_winner_cut"
    risky_winners = risky_winners.sort_values("addon_realized_pnl", ascending=False).head(MAX_ATLAS_ROWS // 2)

    if len(risky_losers) + len(risky_winners) < MAX_ATLAS_ROWS:
        later_pressure = features[
            features["ever_active_on_same_product_pressure_day"].astype(bool)
            & ~features.index.isin(risky_losers.index)
            & ~features.index.isin(risky_winners.index)
        ].copy()
        later_pressure["atlas_bucket"] = "later_same_product_pressure"
        later_pressure = later_pressure.sort_values("active_on_same_product_pressure_days", ascending=False).head(
            MAX_ATLAS_ROWS - len(risky_losers) - len(risky_winners)
        )
        selected = pd.concat([risky_losers, risky_winners, later_pressure], ignore_index=True, sort=False)
    else:
        selected = pd.concat([risky_losers, risky_winners], ignore_index=True, sort=False)
    return selected.drop_duplicates(["event_date", "vt_symbol", "pyramid_add_price", "atlas_bucket"]).reset_index(drop=True)


def _plot_atlas(atlas_rows: pd.DataFrame, minute_bars: pd.DataFrame) -> tuple[list[Path], pd.DataFrame]:
    if atlas_rows.empty:
        return [], pd.DataFrame()
    minute_by_symbol = {symbol: group.copy() for symbol, group in minute_bars.groupby("vt_symbol", sort=False)}
    paths: list[Path] = []
    manifest: list[dict[str, Any]] = []
    for page_start in range(0, len(atlas_rows), PER_PAGE):
        page_rows = atlas_rows.iloc[page_start : page_start + PER_PAGE]
        page = page_start // PER_PAGE + 1
        fig, axes = plt.subplots(PER_PAGE, 1, figsize=(16, 4.6 * PER_PAGE), constrained_layout=True)
        axes_arr = np.atleast_1d(axes)
        for ax, (_, row) in zip(axes_arr, page_rows.iterrows(), strict=False):
            event_date = pd.Timestamp(row["event_date"]).normalize()
            vt_symbol = str(row["vt_symbol"])
            bars = minute_by_symbol.get(vt_symbol, pd.DataFrame())
            day = pd.DataFrame()
            if not bars.empty:
                day = bars[bars["bar_date"].eq(event_date)].copy().sort_values("bar_datetime").reset_index(drop=True)
            if day.empty:
                ax.text(0.5, 0.5, f"missing minute bars {vt_symbol} {event_date:%Y-%m-%d}", ha="center", va="center")
                ax.set_axis_off()
            else:
                s825._plot_candles(ax, day)
                for label, price, color, linestyle in [
                    ("base entry", row.get("entry_price"), "#2563eb", "-"),
                    ("sleeve add", row.get("pyramid_add_price"), "#16a34a", "--"),
                    ("sleeve stop", row.get("pyramid_stop_price"), "#dc2626", ":"),
                    ("addon exit", row.get("exit_price"), "#7c3aed", "-."),
                ]:
                    value = _safe_float(price)
                    if np.isfinite(value):
                        ax.axhline(value, color=color, linestyle=linestyle, linewidth=0.9, label=label)
                progress_dt = pd.Timestamp(row["progress_datetime"]) if not pd.isna(row["progress_datetime"]) else None
                if progress_dt is not None:
                    matches = pd.to_datetime(day["bar_datetime"], errors="coerce").eq(progress_dt)
                    if matches.any():
                        ax.axvline(int(np.flatnonzero(matches.to_numpy())[0]), color="#16a34a", linewidth=0.9, alpha=0.8)
                ticks = np.linspace(0, len(day) - 1, num=min(8, len(day)), dtype=int)
                ax.set_xticks(ticks)
                ax.set_xticklabels([pd.Timestamp(day.loc[pos, "bar_datetime"]).strftime("%H:%M") for pos in ticks], fontsize=7)
                handles, labels = ax.get_legend_handles_labels()
                if handles:
                    dedup = dict(zip(labels, handles, strict=False))
                    ax.legend(dedup.values(), dedup.keys(), loc="best", fontsize=7)
                ax.grid(True, alpha=0.18)
            ax.set_title(
                f"{row.get('atlas_bucket')} | {event_date:%Y-%m-%d} {vt_symbol} {row.get('direction')} "
                f"PnL={row.get('addon_realized_pnl'):.0f} pre={row.get('pre_add_broker10_pct'):.1f}% "
                f"proj={row.get('projected_after_add_broker10_pct'):.1f}% prevPressure={bool(row.get('prev_holding_pressure_state'))}",
                fontsize=9,
            )
            manifest.append(
                {
                    "page": page,
                    "atlas_bucket": row.get("atlas_bucket"),
                    "event_date": event_date.date().isoformat(),
                    "vt_symbol": vt_symbol,
                    "product_vt_symbol": row.get("product_vt_symbol"),
                    "direction": row.get("direction"),
                    "addon_realized_pnl": _safe_float(row.get("addon_realized_pnl")),
                    "pre_add_broker10_pct": _safe_float(row.get("pre_add_broker10_pct")),
                    "projected_after_add_broker10_pct": _safe_float(row.get("projected_after_add_broker10_pct")),
                    "prev_holding_pressure_state": bool(row.get("prev_holding_pressure_state")),
                    "current_holding_pressure_state": bool(row.get("current_holding_pressure_state")),
                    "active_on_pressure_days": int(_safe_float(row.get("active_on_pressure_days"), 0.0)),
                    "active_on_same_product_pressure_days": int(
                        _safe_float(row.get("active_on_same_product_pressure_days"), 0.0)
                    ),
                }
            )
        for ax in axes_arr[len(page_rows) :]:
            ax.set_axis_off()
        path = Path(str(ATLAS_TEMPLATE).format(page=page))
        fig.suptitle("Stage887 sleeve trigger pressure-gate minute atlas", fontsize=13)
        fig.savefig(path, dpi=150)
        plt.close(fig)
        paths.append(path)
    return paths, pd.DataFrame(manifest)


def _decision(gate_summary: pd.DataFrame) -> str:
    live = gate_summary[gate_summary["gate_type"].eq("live_candidate")].copy()
    if live.empty:
        return "stage887_sleeve_pressure_gate_failed_no_live_gate"
    positive = live[live["skip_proxy_delta"].gt(0) & live["winner_cut"].abs().lt(live["loser_saved"])]
    if not positive.empty:
        return "stage887_sleeve_pressure_gate_readonly_signal_needs_true_engine"
    return "stage887_sleeve_pressure_gate_not_promoted_proxy_cost_or_too_blunt"


def _write_report(
    features: pd.DataFrame,
    gate_summary: pd.DataFrame,
    pressure_attribution: pd.DataFrame,
    atlas_paths: list[Path],
    decision: str,
) -> None:
    best_live = gate_summary[gate_summary["gate_type"].eq("live_candidate")].sort_values("skip_proxy_delta", ascending=False)
    worst_winner_cut = gate_summary[gate_summary["gate_type"].eq("live_candidate")].sort_values("winner_cut")
    lines = [
        "# Stage887 Stage883 sleeve 触发压力闸门只读审计",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 源候选：`{stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION}`",
        "- 阶段性质：Stage883 sleeve 触发前组合压力闸门只读审计；不新增交易规则、不改正式版、不改 Stage819 候选配置、不连接 CTP、不调用下单。",
        "- 输入：Stage883 pyramid events / entry risk / closed lots、Stage885 daily pressure state、Stage861 full minute bars。",
        "",
        "## 外部调研判断",
        "",
        "- vn.py/VeighNa 官方项目支持组合策略历史回测和实盘框架，因此本阶段继续按组合状态审计，而不是单笔路径代理直接晋级。",
        "- CME open interest 资料支持把 OI 和价格当作参与度辅助信息，但不能把 OI 或高参与度单独当作退出/禁入充分条件。",
        "- 趋势跟随 pyramiding 的通用经验是加仓必须被 portfolio heat 约束；Stage887 因此只看新增 sleeve 的前置风险预算，不回头砍已有右尾仓位。",
        "- 我的判断：Stage886 已反证高压持仓平仓；Stage887 的第一性问题是“新增 1 手 sleeve 是否在已热/将热时让分子继续膨胀”。",
        "",
        "## 固定 gate 定义",
        "",
        "- `G0_prev_pressure`：前一交易日已经是 Stage885 holding pressure state，严格可在触发前知道。",
        "- `G1_pre_add_heat80`：sleeve 触发前估算 broker10/equity 已经 `>=80%`，用 Stage885 既定账户 heat 阈值。",
        "- `G2_projected_after_add_heat80`：新增 1 手 sleeve 后估算 broker10/equity 将 `>=80%`。",
        "- `G3_pre_or_projected_heat80`：G1 或 G2。",
        "- `G4_prev_pressure_or_projected_after_heat80`：G0 或 G2。",
        "- `G5_prev_pressure_same_product_direction`：前一日 pressure 且本次 sleeve 的产品方向等于前一日 top product-direction。",
        "- `A0/A1` 为 current-day pressure 事后归因，只用于解释，不是实时 gate。",
        "- 不扫描 `75/85/90` heat、小数阈值、产品方向、年份、分钟窗口或 OI 阈值。",
        "",
        "## 样本概览",
        "",
        f"- Stage883 pyramid events：`{len(features)}`",
        f"- PnL available events：`{int(features['addon_pnl_available'].sum()) if not features.empty else 0}`",
        f"- addon PnL sum：`{pd.to_numeric(features['addon_realized_pnl'], errors='coerce').sum():,.2f}`",
        f"- entry-day stopped events：`{int(features['entry_day_stopped'].sum()) if not features.empty else 0}`",
        f"- ever active on later pressure day：`{int(features['ever_active_on_pressure_day'].sum()) if not features.empty else 0}`",
        f"- ever active on same-product pressure day：`{int(features['ever_active_on_same_product_pressure_day'].sum()) if not features.empty else 0}`",
        "",
        "## gate summary",
        "",
        _md_table(gate_summary, max_rows=20),
        "",
        "## pressure attribution",
        "",
        _md_table(pressure_attribution, max_rows=20),
        "",
        "## best live gates by proxy",
        "",
        _md_table(best_live, max_rows=8),
        "",
        "## largest live winner-cut risks",
        "",
        _md_table(worst_winner_cut, max_rows=8),
        "",
        "## 视觉复核",
        "",
        f"- summary chart：`{SUMMARY_CHART_PATH.name}`",
        f"- atlas pages：{', '.join(path.name for path in atlas_paths) if atlas_paths else '无'}",
        "- atlas 优先展示 live gate 会阻断的亏损/盈利 sleeve，以及后来参与 same-product pressure 的样本。",
        "",
        "## 决策",
        "",
        f"- decision：`{decision}`",
        "- 只有 live_candidate gate 的 skip proxy 为正、且 winner cut 小于 loser saved，才允许进入冻结真实引擎；否则不得推广。",
        "- A0/A1 current-day pressure 只作后验归因，不能作为实时规则。",
        "",
        "## 过拟合反思",
        "",
        "- 运行前判断：否。本阶段只使用 Stage885 固定 pressure 定义和 `80%` account heat，不扫阈值、不筛品种方向。",
        "- 运行后判断：见本报告决策。若继续用少数亏损 sleeve 反推年份、品种、方向或更高/更低 heat，就是过拟合。",
        "",
        "## 继续价值反思",
        "",
        "- 运行前判断：有价值。它直接检验 C17 的新增保证金分子是否能被前置组合压力约束，而不是砍已有右尾。",
        "- 运行后判断：见本报告决策。若 live gate 仍过钝，pyramiding/sleeve 方向应彻底停止；若只读 proxy 有低误伤信号，也只能做一次冻结真实引擎。",
        "",
        "## 输出文件",
        "",
        f"- features：`{FEATURES_PATH}`",
        f"- gate summary：`{GATE_SUMMARY_PATH}`",
        f"- pressure attribution：`{PRESSURE_ATTRIBUTION_PATH}`",
        f"- summary chart：`{SUMMARY_CHART_PATH}`",
        f"- atlas manifest：`{ATLAS_MANIFEST_PATH}`",
        f"- decision：`{DECISION_PATH}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    events, entry, closed, daily_state, minute_bars = _prepare_inputs()
    features = _merge_event_features(events, entry, closed, daily_state)
    gate_summary = _gate_summary(features)
    pressure_attribution = _pressure_attribution(features)
    _plot_summary(features, gate_summary)
    atlas_rows = _select_atlas_rows(features)
    atlas_paths, atlas_manifest = _plot_atlas(atlas_rows, minute_bars)

    features.to_csv(FEATURES_PATH, index=False, encoding="utf-8-sig")
    gate_summary.to_csv(GATE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    pressure_attribution.to_csv(PRESSURE_ATTRIBUTION_PATH, index=False, encoding="utf-8-sig")
    atlas_manifest.to_csv(ATLAS_MANIFEST_PATH, index=False, encoding="utf-8-sig")

    decision = _decision(gate_summary)
    decision_payload = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "decision": decision,
        "official_candidate": stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION,
        "inputs": {
            "pyramid_events": str(s883.PYRAMID_EVENTS_PATH),
            "entry_risk": str(s883.ENTRY_RISK_PATH),
            "closed_lots": str(s883.CLOSED_LOTS_PATH),
            "stage885_daily_state": str(s885.DAILY_STATE_PATH),
        },
        "counts": {
            "events": int(len(features)),
            "pnl_available_events": int(features["addon_pnl_available"].sum()) if not features.empty else 0,
            "entry_day_stopped_events": int(features["entry_day_stopped"].sum()) if not features.empty else 0,
            "active_on_pressure_events": int(features["ever_active_on_pressure_day"].sum()) if not features.empty else 0,
            "active_on_same_product_pressure_events": int(features["ever_active_on_same_product_pressure_day"].sum())
            if not features.empty
            else 0,
        },
        "total_addon_pnl_available": float(pd.to_numeric(features["addon_realized_pnl"], errors="coerce").sum())
        if not features.empty
        else 0.0,
        "gate_summary": gate_summary.to_dict("records"),
        "outputs": {
            "features": str(FEATURES_PATH),
            "gate_summary": str(GATE_SUMMARY_PATH),
            "pressure_attribution": str(PRESSURE_ATTRIBUTION_PATH),
            "summary_chart": str(SUMMARY_CHART_PATH),
            "atlas_manifest": str(ATLAS_MANIFEST_PATH),
            "atlas_pages": [str(path) for path in atlas_paths],
            "report": str(REPORT_PATH),
            "decision": str(DECISION_PATH),
        },
        "guardrails": {
            "strategy_changed": False,
            "official_stage372_changed": False,
            "official_candidate_config_changed": False,
            "ctp_connected": False,
            "order_api_called": False,
            "formal_ab_triggered": False,
            "readonly_only": True,
            "current_day_pressure_used_only_for_attribution": True,
        },
    }
    DECISION_PATH.write_text(
        json.dumps(_json_safe(decision_payload), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_report(features, gate_summary, pressure_attribution, atlas_paths, decision)
    print(json.dumps(_json_safe(decision_payload), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
