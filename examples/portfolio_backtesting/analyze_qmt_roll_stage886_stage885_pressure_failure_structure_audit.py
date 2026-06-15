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
import analyze_qmt_roll_stage885_stage884_holding_pressure_state_audit as s885
import qmt_roll_official_candidate_stage819_30w_config as stage819_cfg


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage886"
MODEL_TAG = "stage886_stage885_pressure_failure_structure_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage886_stage885_pressure_failure_structure_audit"

C17_ARM = s885.C17_ARM
MAX_ATLAS_ROWS_PER_SIDE = 6
PER_PAGE = 3

DAILY_STATE_IN = s885.DAILY_STATE_PATH
PRODUCT_DIRECTION_DAILY_IN = s885.PRODUCT_DIRECTION_DAILY_PATH

FEATURES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_features_{MODEL_TAG}.csv"
DAY_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_day_summary_{MODEL_TAG}.csv"
STATE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_state_summary_{MODEL_TAG}.csv"
SHAPE_PROXY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_shape_proxy_{MODEL_TAG}.csv"
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
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if np.isfinite(number) else default


def _load_required_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _prepare_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    daily_state = _load_required_csv(DAILY_STATE_IN)
    product_daily = _load_required_csv(PRODUCT_DIRECTION_DAILY_IN)
    closed_lots = s885._load_closed_lots_for_arms()
    c17_lots = closed_lots[closed_lots["arm"].eq(C17_ARM)].copy()
    vt_symbols = set(c17_lots["vt_symbol"].astype(str).dropna().unique())
    minute_bars = s885._load_full_minute_bars(vt_symbols)

    daily_state["date"] = pd.to_datetime(daily_state["date"], errors="coerce").dt.normalize()
    product_daily["date"] = pd.to_datetime(product_daily["date"], errors="coerce").dt.normalize()
    for column in ["entry_date", "exit_date"]:
        c17_lots[column] = pd.to_datetime(c17_lots[column], errors="coerce").dt.normalize()
    return daily_state, product_daily, c17_lots, minute_bars


def _split_product_direction(key: Any) -> tuple[str, str]:
    text = str(key or "")
    if ":" not in text:
        return "", ""
    product, direction = text.split(":", 1)
    return product, direction


def _directional_metrics(day: pd.DataFrame, direction: str) -> dict[str, float]:
    ordered = day.sort_values("bar_datetime").reset_index(drop=True)
    first = ordered.iloc[0]
    last = ordered.iloc[-1]
    day_open = _safe_float(first.get("open"))
    day_close = _safe_float(last.get("close"))
    day_high = _safe_float(ordered["high"].max())
    day_low = _safe_float(ordered["low"].min())
    day_range = day_high - day_low
    if not (day_open > 0 and day_close > 0 and day_high >= day_low):
        return {}

    if direction == "short":
        directional_close_return_pct = (day_open / day_close - 1.0) * 100.0 if day_close > 0 else np.nan
        signal_side_progress_pct = (day_open - day_low) / day_open * 100.0
        adverse_excursion_pct = (day_high - day_open) / day_open * 100.0
        close_location_signal_side = (day_high - day_close) / day_range if day_range > 0 else 0.5
    else:
        directional_close_return_pct = (day_close / day_open - 1.0) * 100.0
        signal_side_progress_pct = (day_high - day_open) / day_open * 100.0
        adverse_excursion_pct = (day_open - day_low) / day_open * 100.0
        close_location_signal_side = (day_close - day_low) / day_range if day_range > 0 else 0.5

    oi_start = _safe_float(first.get("open_oi"))
    oi_end = _safe_float(last.get("close_oi"))
    oi_change = oi_end - oi_start if np.isfinite(oi_start) and np.isfinite(oi_end) else np.nan
    oi_change_pct = oi_change / oi_start * 100.0 if np.isfinite(oi_change) and oi_start > 0 else np.nan

    return {
        "day_open": day_open,
        "day_close": day_close,
        "day_high": day_high,
        "day_low": day_low,
        "day_range_pct": day_range / day_open * 100.0 if day_open > 0 else np.nan,
        "directional_close_return_pct": directional_close_return_pct,
        "signal_side_progress_pct": signal_side_progress_pct,
        "adverse_excursion_pct": adverse_excursion_pct,
        "close_location_signal_side": close_location_signal_side,
        "oi_start": oi_start,
        "oi_end": oi_end,
        "oi_change": oi_change,
        "oi_change_pct": oi_change_pct,
        "volume_sum": float(pd.to_numeric(ordered["volume"], errors="coerce").fillna(0.0).sum()),
        "minute_bars": int(len(ordered)),
    }


def _remaining_pnl_after_focus_close(lot: pd.Series, focus_date: pd.Timestamp, focus_close: float) -> float:
    exit_date = pd.Timestamp(lot.get("exit_date")).normalize()
    if not (exit_date > focus_date) or not np.isfinite(focus_close):
        return 0.0
    exit_price = _safe_float(lot.get("exit_price"))
    size = _safe_float(lot.get("size"), 0.0)
    volume = _safe_float(lot.get("volume"), 0.0)
    if not (exit_price > 0 and size > 0 and volume > 0):
        return 0.0
    if str(lot.get("direction")) == "short":
        return (focus_close - exit_price) * size * volume
    return (exit_price - focus_close) * size * volume


def _minute_state(directional_close_return_pct: float, oi_change: float) -> str:
    price_label = "signal_close" if directional_close_return_pct > 0 else "adverse_close"
    oi_label = "oi_up" if _safe_float(oi_change, 0.0) >= 0 else "oi_down"
    return f"{price_label}_{oi_label}"


def _build_features(
    daily_state: pd.DataFrame,
    c17_lots: pd.DataFrame,
    minute_bars: pd.DataFrame,
) -> pd.DataFrame:
    pressure_days = daily_state[
        daily_state["arm"].eq(C17_ARM) & daily_state["holding_pressure_state"].astype(bool)
    ].copy()
    minute_by_symbol = {symbol: group.copy() for symbol, group in minute_bars.groupby("vt_symbol", sort=False)}
    rows: list[dict[str, Any]] = []

    for day_row in pressure_days.sort_values("date").itertuples(index=False):
        focus_date = pd.Timestamp(day_row.date).normalize()
        product, direction = _split_product_direction(day_row.top_product_direction)
        if not product or not direction:
            continue
        active = c17_lots[
            c17_lots["product"].astype(str).eq(product)
            & c17_lots["direction"].astype(str).eq(direction)
            & c17_lots["entry_date"].le(focus_date)
            & c17_lots["exit_date"].ge(focus_date)
        ].copy()
        if active.empty:
            continue
        for _, lot in active.iterrows():
            vt_symbol = str(lot.get("vt_symbol"))
            bars = minute_by_symbol.get(vt_symbol, pd.DataFrame())
            day = pd.DataFrame()
            if not bars.empty:
                day = bars[bars["bar_date"].eq(focus_date)].copy()
            metrics = _directional_metrics(day, direction) if not day.empty else {}
            has_minutes = bool(metrics)
            directional_close_return_pct = _safe_float(metrics.get("directional_close_return_pct"))
            close_location_signal_side = _safe_float(metrics.get("close_location_signal_side"))
            signal_side_progress_pct = _safe_float(metrics.get("signal_side_progress_pct"))
            adverse_excursion_pct = _safe_float(metrics.get("adverse_excursion_pct"))
            oi_change = _safe_float(metrics.get("oi_change"))
            pressure_minute_state = (
                _minute_state(directional_close_return_pct, oi_change) if has_minutes else "missing_minutes"
            )
            no_net_signal_progress = bool(directional_close_return_pct <= 0) if has_minutes else False
            close_in_adverse_half = bool(close_location_signal_side < 0.5) if has_minutes else False
            adverse_dominates_progress = (
                bool(adverse_excursion_pct > signal_side_progress_pct) if has_minutes else False
            )
            price_failure_shape = bool(no_net_signal_progress and close_in_adverse_half and adverse_dominates_progress)
            adverse_price_oi_up_failure_shape = bool(price_failure_shape and oi_change >= 0)
            adverse_price_oi_down_failure_shape = bool(price_failure_shape and oi_change < 0)
            signal_resilience_shape = bool(
                directional_close_return_pct > 0
                and close_location_signal_side >= 0.5
                and signal_side_progress_pct >= adverse_excursion_pct
            ) if has_minutes else False
            focus_close = _safe_float(metrics.get("day_close"))
            remaining_pnl = _remaining_pnl_after_focus_close(lot, focus_date, focus_close)
            exit_date = pd.Timestamp(lot.get("exit_date")).normalize()
            entry_date = pd.Timestamp(lot.get("entry_date")).normalize()
            rows.append(
                {
                    "date": focus_date,
                    "arm": C17_ARM,
                    "lot_id": lot.get("lot_id"),
                    "vt_symbol": vt_symbol,
                    "product": product,
                    "direction": direction,
                    "entry_date": entry_date,
                    "exit_date": exit_date,
                    "entry_same_day": entry_date == focus_date,
                    "exit_same_day": exit_date == focus_date,
                    "held_beyond_focus_day": exit_date > focus_date,
                    "volume": _safe_float(lot.get("volume"), 0.0),
                    "size": _safe_float(lot.get("size"), 0.0),
                    "entry_price": _safe_float(lot.get("entry_price")),
                    "exit_price": _safe_float(lot.get("exit_price")),
                    "realized_pnl": _safe_float(lot.get("realized_pnl"), 0.0),
                    "risk_amount": _safe_float(lot.get("risk_amount"), 0.0),
                    "r_multiple": _safe_float(lot.get("r_multiple")),
                    "pressure_broker10_pct": _safe_float(day_row.curve_broker10_margin_to_equity_pct),
                    "pressure_top1_pct": _safe_float(day_row.top1_product_direction_broker10_pct_scaled),
                    "pressure_top3_share": _safe_float(day_row.top3_product_direction_share),
                    "next5_return_pct": _safe_float(day_row.next5_return_pct),
                    "next20_return_pct": _safe_float(day_row.next20_return_pct),
                    "future20_min_return_pct": _safe_float(day_row.future20_min_return_pct),
                    "future20_max_broker10_pct": _safe_float(day_row.future20_max_broker10_pct),
                    "has_minute_bars": has_minutes,
                    "pressure_minute_state": pressure_minute_state,
                    "price_failure_shape": price_failure_shape,
                    "adverse_price_oi_up_failure_shape": adverse_price_oi_up_failure_shape,
                    "adverse_price_oi_down_failure_shape": adverse_price_oi_down_failure_shape,
                    "signal_resilience_shape": signal_resilience_shape,
                    "no_net_signal_progress": no_net_signal_progress,
                    "close_in_adverse_half": close_in_adverse_half,
                    "adverse_dominates_progress": adverse_dominates_progress,
                    "remaining_pnl_after_focus_close": remaining_pnl,
                    "same_day_eod_exit_proxy_delta": -remaining_pnl,
                    **metrics,
                }
            )
    data = pd.DataFrame(rows)
    if not data.empty:
        data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
        for column in ["entry_date", "exit_date"]:
            data[column] = pd.to_datetime(data[column], errors="coerce").dt.normalize()
    return data.sort_values(["date", "product", "direction", "lot_id"]).reset_index(drop=True)


def _summarize_subset(name: str, data: pd.DataFrame) -> dict[str, Any]:
    if data.empty:
        return {
            "shape": name,
            "rows": 0,
            "days": 0,
            "held_beyond_rows": 0,
            "remaining_pnl_sum": 0.0,
            "same_day_eod_exit_proxy_delta": 0.0,
            "loser_saved": 0.0,
            "winner_cut": 0.0,
            "median_next20_return_pct": np.nan,
            "negative_next20_share": np.nan,
        }
    remaining = pd.to_numeric(data["remaining_pnl_after_focus_close"], errors="coerce").fillna(0.0)
    next20_by_day = data.drop_duplicates("date")["next20_return_pct"]
    return {
        "shape": name,
        "rows": int(len(data)),
        "days": int(data["date"].nunique()),
        "products": int(data["product"].nunique()),
        "held_beyond_rows": int(data["held_beyond_focus_day"].astype(bool).sum()),
        "median_directional_close_return_pct": float(
            pd.to_numeric(data["directional_close_return_pct"], errors="coerce").median()
        ),
        "median_close_location_signal_side": float(
            pd.to_numeric(data["close_location_signal_side"], errors="coerce").median()
        ),
        "median_oi_change_pct": float(pd.to_numeric(data["oi_change_pct"], errors="coerce").median()),
        "median_adverse_excursion_pct": float(
            pd.to_numeric(data["adverse_excursion_pct"], errors="coerce").median()
        ),
        "remaining_pnl_sum": float(remaining.sum()),
        "positive_remaining_share": float(remaining.gt(0).mean()) if len(remaining) else np.nan,
        "same_day_eod_exit_proxy_delta": float((-remaining).sum()),
        "loser_saved": float((-remaining[remaining < 0]).sum()),
        "winner_cut": float((-remaining[remaining > 0]).sum()),
        "median_next20_return_pct": float(pd.to_numeric(next20_by_day, errors="coerce").median()),
        "negative_next20_share": float(pd.to_numeric(next20_by_day, errors="coerce").lt(0).mean()),
        "worst_future20_min_return_pct": float(
            pd.to_numeric(data.drop_duplicates("date")["future20_min_return_pct"], errors="coerce").min()
        ),
    }


def _state_summary(features: pd.DataFrame) -> pd.DataFrame:
    if features.empty:
        return pd.DataFrame()
    rows = [
        _summarize_subset(str(state), group)
        for state, group in features.groupby("pressure_minute_state", dropna=False, sort=True)
    ]
    return pd.DataFrame(rows).sort_values("same_day_eod_exit_proxy_delta", ascending=False).reset_index(drop=True)


def _shape_proxy(features: pd.DataFrame) -> pd.DataFrame:
    if features.empty:
        return pd.DataFrame()
    specs = [
        ("all_pressure_top_product_lots", pd.Series(True, index=features.index)),
        ("price_failure_shape", features["price_failure_shape"].astype(bool)),
        ("adverse_price_oi_up_failure_shape", features["adverse_price_oi_up_failure_shape"].astype(bool)),
        ("adverse_price_oi_down_failure_shape", features["adverse_price_oi_down_failure_shape"].astype(bool)),
        ("signal_resilience_shape", features["signal_resilience_shape"].astype(bool)),
        ("no_net_signal_progress_only", features["no_net_signal_progress"].astype(bool)),
        ("close_in_adverse_half_only", features["close_in_adverse_half"].astype(bool)),
        ("adverse_dominates_progress_only", features["adverse_dominates_progress"].astype(bool)),
    ]
    rows = [_summarize_subset(name, features[mask].copy()) for name, mask in specs]
    return pd.DataFrame(rows).sort_values("same_day_eod_exit_proxy_delta", ascending=False).reset_index(drop=True)


def _day_summary(features: pd.DataFrame, daily_state: pd.DataFrame) -> pd.DataFrame:
    if features.empty:
        return pd.DataFrame()
    grouped = (
        features.groupby("date", dropna=False)
        .agg(
            rows=("lot_id", "count"),
            products=("product", "nunique"),
            top_product_direction=("pressure_minute_state", lambda s: ",".join(sorted(set(map(str, s))))),
            any_price_failure_shape=("price_failure_shape", "max"),
            price_failure_rows=("price_failure_shape", "sum"),
            any_signal_resilience_shape=("signal_resilience_shape", "max"),
            signal_resilience_rows=("signal_resilience_shape", "sum"),
            median_directional_close_return_pct=("directional_close_return_pct", "median"),
            min_close_location_signal_side=("close_location_signal_side", "min"),
            median_oi_change_pct=("oi_change_pct", "median"),
            remaining_pnl_after_focus_close=("remaining_pnl_after_focus_close", "sum"),
            same_day_eod_exit_proxy_delta=("same_day_eod_exit_proxy_delta", "sum"),
        )
        .reset_index()
    )
    keep = [
        "date",
        "curve_broker10_margin_to_equity_pct",
        "top_product_direction",
        "top1_product_direction_broker10_pct_scaled",
        "top3_product_direction_share",
        "next5_return_pct",
        "next20_return_pct",
        "future20_min_return_pct",
        "future20_max_broker10_pct",
    ]
    pressure_days = daily_state[
        daily_state["arm"].eq(C17_ARM) & daily_state["holding_pressure_state"].astype(bool)
    ][keep].copy()
    pressure_days = pressure_days.rename(
        columns={
            "top_product_direction": "stage885_top_product_direction",
            "curve_broker10_margin_to_equity_pct": "pressure_broker10_pct",
            "top1_product_direction_broker10_pct_scaled": "pressure_top1_pct",
            "top3_product_direction_share": "pressure_top3_share",
        }
    )
    merged = grouped.merge(pressure_days, on="date", how="left")
    merged["price_failure_share"] = merged["price_failure_rows"] / merged["rows"]
    merged["signal_resilience_share"] = merged["signal_resilience_rows"] / merged["rows"]
    return merged.sort_values(["any_price_failure_shape", "next20_return_pct"], ascending=[False, True]).reset_index(
        drop=True
    )


def _plot_summary(features: pd.DataFrame, day_summary: pd.DataFrame, shape_proxy: pd.DataFrame) -> None:
    if features.empty:
        return
    fig, axes = plt.subplots(3, 1, figsize=(16, 12), constrained_layout=True)

    days = day_summary.sort_values("date").copy()
    colors = np.where(days["any_price_failure_shape"].astype(bool), "#dc2626", "#2563eb")
    axes[0].bar(days["date"], days["pressure_broker10_pct"], color=colors, alpha=0.75, label="broker10 pct")
    axes[0].plot(days["date"], days["next20_return_pct"], color="#16a34a", marker="o", linewidth=1.0, label="next20 return pct")
    axes[0].axhline(s885.ACCOUNT_HEAT_WATCH_PCT, color="#92400e", linestyle=":", linewidth=1.0)
    axes[0].set_title("Stage886 C17 pressure days: red means price-failure shape present")
    axes[0].set_ylabel("percent")
    axes[0].legend(loc="best", fontsize=8)
    axes[0].grid(True, alpha=0.25)

    scatter = axes[1].scatter(
        features["directional_close_return_pct"],
        features["close_location_signal_side"],
        c=pd.to_numeric(features["remaining_pnl_after_focus_close"], errors="coerce"),
        cmap="RdYlGn",
        s=35,
        alpha=0.8,
    )
    axes[1].axvline(0.0, color="#111827", linestyle=":", linewidth=1.0)
    axes[1].axhline(0.5, color="#111827", linestyle=":", linewidth=1.0)
    axes[1].set_title("Top product-direction pressure lots: minute structure vs remaining PnL")
    axes[1].set_xlabel("signal-side close return pct")
    axes[1].set_ylabel("close location on signal side")
    fig.colorbar(scatter, ax=axes[1], label="remaining PnL after pressure-day close")
    axes[1].grid(True, alpha=0.25)

    plot_proxy = shape_proxy.head(8).copy()
    x = np.arange(len(plot_proxy))
    axes[2].bar(x, plot_proxy["same_day_eod_exit_proxy_delta"], color="#64748b", label="EOD exit proxy delta")
    ax2 = axes[2].twinx()
    ax2.plot(x, plot_proxy["negative_next20_share"] * 100.0, color="#dc2626", marker="o", label="negative next20 share")
    axes[2].set_xticks(x)
    axes[2].set_xticklabels(plot_proxy["shape"], rotation=25, ha="right")
    axes[2].set_ylabel("proxy delta")
    ax2.set_ylabel("negative next20 share %")
    handles1, labels1 = axes[2].get_legend_handles_labels()
    handles2, labels2 = ax2.get_legend_handles_labels()
    axes[2].legend(handles1 + handles2, labels1 + labels2, loc="best", fontsize=8)
    axes[2].grid(True, alpha=0.25)

    fig.savefig(SUMMARY_CHART_PATH, dpi=150)
    plt.close(fig)


def _select_atlas_rows(features: pd.DataFrame) -> pd.DataFrame:
    if features.empty:
        return pd.DataFrame()
    bad = features[
        features["price_failure_shape"].astype(bool)
        & features["held_beyond_focus_day"].astype(bool)
    ].copy()
    bad = bad.sort_values(["remaining_pnl_after_focus_close", "next20_return_pct"], ascending=[True, True]).head(
        MAX_ATLAS_ROWS_PER_SIDE
    )
    good = features[
        features["signal_resilience_shape"].astype(bool)
        & features["held_beyond_focus_day"].astype(bool)
    ].copy()
    good = good.sort_values(["remaining_pnl_after_focus_close", "next20_return_pct"], ascending=[False, False]).head(
        MAX_ATLAS_ROWS_PER_SIDE
    )
    bad["atlas_bucket"] = "bad_price_failure"
    good["atlas_bucket"] = "good_signal_resilience"
    selected = pd.concat([bad, good], ignore_index=True, sort=False)
    return selected.drop_duplicates(["date", "vt_symbol", "lot_id", "atlas_bucket"]).reset_index(drop=True)


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
            focus_date = pd.Timestamp(row["date"]).normalize()
            vt_symbol = str(row["vt_symbol"])
            bars = minute_by_symbol.get(vt_symbol, pd.DataFrame())
            day = pd.DataFrame()
            if not bars.empty:
                day = bars[bars["bar_date"].eq(focus_date)].copy().sort_values("bar_datetime").reset_index(drop=True)
            if day.empty:
                ax.text(0.5, 0.5, f"missing minute bars {vt_symbol} {focus_date:%Y-%m-%d}", ha="center", va="center")
                ax.set_axis_off()
            else:
                s825._plot_candles(ax, day)
                for label, price, color, linestyle in [
                    ("day open", row.get("day_open"), "#111827", "--"),
                    ("day close", row.get("day_close"), "#0f766e", "--"),
                    ("entry", row.get("entry_price"), "#2563eb", "-"),
                    ("exit", row.get("exit_price"), "#dc2626", ":"),
                ]:
                    value = _safe_float(price)
                    if np.isfinite(value):
                        ax.axhline(value, color=color, linestyle=linestyle, linewidth=0.9, label=label)
                ax2 = ax.twinx()
                ax2.plot(
                    np.arange(len(day)),
                    pd.to_numeric(day["close_oi"], errors="coerce"),
                    color="#64748b",
                    alpha=0.25,
                    linewidth=0.8,
                    label="close OI",
                )
                ax2.tick_params(axis="y", labelsize=7, colors="#64748b")
                ticks = np.linspace(0, len(day) - 1, num=min(8, len(day)), dtype=int)
                ax.set_xticks(ticks)
                ax.set_xticklabels([pd.Timestamp(day.loc[pos, "bar_datetime"]).strftime("%H:%M") for pos in ticks], fontsize=7)
                handles, labels = ax.get_legend_handles_labels()
                if handles:
                    dedup = dict(zip(labels, handles, strict=False))
                    ax.legend(dedup.values(), dedup.keys(), loc="best", fontsize=7)
                ax.grid(True, alpha=0.18)
            ax.set_title(
                f"{row.get('atlas_bucket')} | {focus_date:%Y-%m-%d} {vt_symbol} {row.get('direction')} "
                f"state={row.get('pressure_minute_state')} dir_close={row.get('directional_close_return_pct'):.2f}% "
                f"loc={row.get('close_location_signal_side'):.2f} remPnL={row.get('remaining_pnl_after_focus_close'):.0f}",
                fontsize=9,
            )
            manifest.append(
                {
                    "page": page,
                    "atlas_bucket": row.get("atlas_bucket"),
                    "date": focus_date.date().isoformat(),
                    "vt_symbol": vt_symbol,
                    "product": row.get("product"),
                    "direction": row.get("direction"),
                    "lot_id": row.get("lot_id"),
                    "pressure_minute_state": row.get("pressure_minute_state"),
                    "price_failure_shape": bool(row.get("price_failure_shape")),
                    "signal_resilience_shape": bool(row.get("signal_resilience_shape")),
                    "directional_close_return_pct": _safe_float(row.get("directional_close_return_pct")),
                    "close_location_signal_side": _safe_float(row.get("close_location_signal_side")),
                    "oi_change_pct": _safe_float(row.get("oi_change_pct")),
                    "remaining_pnl_after_focus_close": _safe_float(row.get("remaining_pnl_after_focus_close")),
                }
            )
        for ax in axes_arr[len(page_rows) :]:
            ax.set_axis_off()
        path = Path(str(ATLAS_TEMPLATE).format(page=page))
        fig.suptitle("Stage886 pressure-state minute failure/resilience atlas", fontsize=13)
        fig.savefig(path, dpi=150)
        plt.close(fig)
        paths.append(path)
    return paths, pd.DataFrame(manifest)


def _decision(shape_proxy: pd.DataFrame) -> str:
    if shape_proxy.empty:
        return "stage886_pressure_failure_audit_failed_no_features"
    price_failure = shape_proxy[shape_proxy["shape"].eq("price_failure_shape")]
    if price_failure.empty or int(price_failure["rows"].iloc[0]) == 0:
        return "stage886_pressure_failure_shape_absent_no_rule"
    delta = _safe_float(price_failure["same_day_eod_exit_proxy_delta"].iloc[0], 0.0)
    neg_share = _safe_float(price_failure["negative_next20_share"].iloc[0], 0.0)
    winner_cut = abs(_safe_float(price_failure["winner_cut"].iloc[0], 0.0))
    loser_saved = _safe_float(price_failure["loser_saved"].iloc[0], 0.0)
    if delta > 0 and neg_share >= 0.5 and loser_saved > winner_cut:
        return "stage886_pressure_failure_shape_has_readonly_signal_needs_frozen_engine_design"
    return "stage886_pressure_failure_shape_not_trade_rule_mixed_or_right_tail_cost"


def _write_report(
    features: pd.DataFrame,
    day_summary: pd.DataFrame,
    state_summary: pd.DataFrame,
    shape_proxy: pd.DataFrame,
    atlas_paths: list[Path],
    decision: str,
) -> None:
    price_failure = shape_proxy[shape_proxy["shape"].eq("price_failure_shape")].copy()
    signal_resilience = shape_proxy[shape_proxy["shape"].eq("signal_resilience_shape")].copy()
    worst_days = day_summary.sort_values("next20_return_pct", ascending=True).head(10)
    best_days = day_summary.sort_values("next20_return_pct", ascending=False).head(10)
    lines = [
        "# Stage886 pressure-state 内分钟级失败结构只读审计",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 源候选：`{stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION}`",
        "- 阶段性质：Stage885 后续只读结构审计；不新增交易规则、不改正式版、不改 Stage819 候选配置、不连接 CTP、不调用下单。",
        "- 输入：Stage885 C17 holding pressure days、Stage883 C17 closed lots、Stage861 full minute bars。",
        "",
        "## 外部调研判断",
        "",
        "- vn.py/VeighNa 官方项目定位支持组合策略回测和实盘框架，本阶段仍只做组合路径后的结构审计，不把单笔代理当正式结果。",
        "- CME open interest 资料支持把 OI 与价格共同看作参与度/资金流状态，但 OI 不能单独决定退出。",
        "- 趋势跟随 portfolio heat / units 资料提醒，持仓集中度是生存线问题；但趋势右尾通常也发生在高参与度和高持仓压力中。",
        "- Backtrader 成交语义资料提醒，真实止损/退出必须在当时可判定；所以本阶段所有 next20 和 remaining PnL 仅用于事后归因。",
        "- 我的判断：Stage885 已证明 pressure state 不能一刀切退出；Stage886 只检查固定分钟结构是否能把高压右尾和高压失败分开。",
        "",
        "## 固定结构定义",
        "",
        "- 样本：C17 pressure day 上 Stage885 top product-direction 的 active lots。",
        "- `directional_close_return_pct`：压力日从第一根分钟开盘到最后一根分钟收盘的信号方向收益；long 用 close/open，short 用 open/close。",
        "- `close_location_signal_side`：收盘位于当日区间的信号侧位置；long 越接近 1 越靠近高点，short 越接近 1 越靠近低点。",
        "- `price_failure_shape = no_net_signal_progress and close_in_adverse_half and adverse_dominates_progress`。",
        "- `signal_resilience_shape = directional_close_return_pct > 0 and close_location_signal_side >= 0.5 and signal_side_progress_pct >= adverse_excursion_pct`。",
        "- 以上阈值只使用 0 和 0.5 的方向/半区间判定，不扫描窗口、小数阈值、品种、方向或年份。",
        "",
        "## 样本概览",
        "",
        f"- pressure top-product active lot rows：`{len(features)}`",
        f"- pressure days covered：`{features['date'].nunique() if not features.empty else 0}`",
        f"- products covered：`{features['product'].nunique() if not features.empty else 0}`",
        f"- missing minute rows：`{int((~features['has_minute_bars'].astype(bool)).sum()) if not features.empty else 0}`",
        "",
        "## minute state summary",
        "",
        _md_table(state_summary, max_rows=20),
        "",
        "## shape proxy summary",
        "",
        _md_table(shape_proxy, max_rows=20),
        "",
        "## price failure vs signal resilience",
        "",
        _md_table(pd.concat([price_failure, signal_resilience], ignore_index=True, sort=False), max_rows=10),
        "",
        "## worst pressure days by next20",
        "",
        _md_table(worst_days, max_rows=10),
        "",
        "## best pressure days by next20",
        "",
        _md_table(best_days, max_rows=10),
        "",
        "## 视觉复核",
        "",
        f"- summary chart：`{SUMMARY_CHART_PATH.name}`",
        f"- atlas pages：{', '.join(path.name for path in atlas_paths) if atlas_paths else '无'}",
        "- atlas 前半部分选择 price_failure_shape 且后续 remaining PnL 差的压力样本；后半部分选择 signal_resilience_shape 且后续 remaining PnL 好的压力样本。",
        "",
        "## 决策",
        "",
        f"- decision：`{decision}`",
        "- 若 price_failure_shape 的 EOD exit proxy 不能同时满足低误伤和高负样本集中，就不得接真实引擎。",
        "- 即使 proxy 显示正贡献，也只能进入一次冻结规则设计；不得扫描更细分钟窗口、OI 阈值、成交量阈值、品种或方向。",
        "",
        "## 过拟合反思",
        "",
        "- 运行前判断：否。本阶段沿用 Stage885 pressure state，并只用方向收益、区间半位和 OI 正负这类结构标签，不对阈值做搜索。",
        "- 运行后判断：见本报告决策。若继续把 price_failure_shape 拆成年份、品种、方向、小数阈值或分钟窗口，就是过拟合。",
        "",
        "## 继续价值反思",
        "",
        "- 运行前判断：有价值。Stage885 已证明高压不是退出规则，但高压内仍可能存在分钟级失败结构。",
        "- 运行后判断：见本报告决策。只有固定结构能稳定隔离失败且右尾误伤可控，才有进入冻结真实引擎的价值。",
        "",
        "## 输出文件",
        "",
        f"- features：`{FEATURES_PATH}`",
        f"- day summary：`{DAY_SUMMARY_PATH}`",
        f"- state summary：`{STATE_SUMMARY_PATH}`",
        f"- shape proxy：`{SHAPE_PROXY_PATH}`",
        f"- summary chart：`{SUMMARY_CHART_PATH}`",
        f"- atlas manifest：`{ATLAS_MANIFEST_PATH}`",
        f"- decision：`{DECISION_PATH}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    daily_state, _product_daily, c17_lots, minute_bars = _prepare_inputs()
    features = _build_features(daily_state, c17_lots, minute_bars)
    day_summary = _day_summary(features, daily_state)
    state_summary = _state_summary(features)
    shape_proxy = _shape_proxy(features)
    _plot_summary(features, day_summary, shape_proxy)
    atlas_rows = _select_atlas_rows(features)
    atlas_paths, atlas_manifest = _plot_atlas(atlas_rows, minute_bars)

    features.to_csv(FEATURES_PATH, index=False, encoding="utf-8-sig")
    day_summary.to_csv(DAY_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    state_summary.to_csv(STATE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    shape_proxy.to_csv(SHAPE_PROXY_PATH, index=False, encoding="utf-8-sig")
    atlas_manifest.to_csv(ATLAS_MANIFEST_PATH, index=False, encoding="utf-8-sig")

    decision = _decision(shape_proxy)
    decision_payload = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "decision": decision,
        "official_candidate": stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION,
        "inputs": {
            "daily_state": str(DAILY_STATE_IN),
            "product_direction_daily": str(PRODUCT_DIRECTION_DAILY_IN),
            "stage885_decision": str(s885.DECISION_PATH),
        },
        "counts": {
            "feature_rows": int(len(features)),
            "pressure_days": int(features["date"].nunique()) if not features.empty else 0,
            "products": int(features["product"].nunique()) if not features.empty else 0,
            "missing_minute_rows": int((~features["has_minute_bars"].astype(bool)).sum()) if not features.empty else 0,
        },
        "price_failure": (
            shape_proxy[shape_proxy["shape"].eq("price_failure_shape")].iloc[0].to_dict()
            if not shape_proxy[shape_proxy["shape"].eq("price_failure_shape")].empty
            else {}
        ),
        "signal_resilience": (
            shape_proxy[shape_proxy["shape"].eq("signal_resilience_shape")].iloc[0].to_dict()
            if not shape_proxy[shape_proxy["shape"].eq("signal_resilience_shape")].empty
            else {}
        ),
        "outputs": {
            "features": str(FEATURES_PATH),
            "day_summary": str(DAY_SUMMARY_PATH),
            "state_summary": str(STATE_SUMMARY_PATH),
            "shape_proxy": str(SHAPE_PROXY_PATH),
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
        },
    }
    DECISION_PATH.write_text(
        json.dumps(_json_safe(decision_payload), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_report(features, day_summary, state_summary, shape_proxy, atlas_paths, decision)

    print(json.dumps(_json_safe(decision_payload), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
