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

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage825_stage819_intraday_rule_forensics as s825
import analyze_qmt_roll_stage861_stage860_full_visual_atlas as s861
import analyze_qmt_roll_stage884_stage883_broker10_path_forensics as s884
import qmt_roll_official_candidate_stage819_30w_config as stage819_cfg


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage885"
MODEL_TAG = "stage885_stage884_holding_pressure_state_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage885_stage884_holding_pressure_state_audit"

C4_ARM = s884.C4_ARM
C9_ARM = s884.C9_ARM
C17_ARM = s884.C17_ARM
ARMS = [C4_ARM, C9_ARM, C17_ARM]

BROKER_MARGIN_MULTIPLIER = s884.BROKER_MARGIN_MULTIPLIER
ACCOUNT_HEAT_WATCH_PCT = 80.0
ACCOUNT_HEAT_DANGER_PCT = 100.0
TOP1_PRODUCT_DIRECTION_WATCH_PCT = 35.0
TOP3_PRODUCT_DIRECTION_SHARE_WATCH = 0.70
MAX_ATLAS_ROWS = 12
PER_PAGE = 3

CURVE_IN = s884.CURVE_IN
C17_CLOSED_LOTS_IN = s884.CLOSED_LOTS_IN
STAGE863_PREFIX = "qmt_roll_stage863_stage847_c10_budget_lock_engine"
STAGE863_TAG = "stage863_stage847_c10_budget_lock_engine_v1"
STAGE863_CLOSED_LOTS_IN = OUTPUT_DIR / f"{STAGE863_PREFIX}_closed_lots_{STAGE863_TAG}.csv"
DECISION_IN = s884.DECISION_PATH

DAILY_STATE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_state_{MODEL_TAG}.csv"
PRODUCT_DIRECTION_DAILY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_direction_daily_{MODEL_TAG}.csv"
PRESSURE_BUCKET_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_pressure_bucket_{MODEL_TAG}.csv"
C17_C9_DELTA_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_c17_c9_delta_{MODEL_TAG}.csv"
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


def _load_closed_lots_for_arms() -> pd.DataFrame:
    base = s884._prepare_closed_lots(_load_required_csv(STAGE863_CLOSED_LOTS_IN))
    base = base[base["arm"].isin([C4_ARM, C9_ARM])].copy()
    c17 = s884._prepare_closed_lots(_load_required_csv(C17_CLOSED_LOTS_IN))
    c17 = c17[c17["arm"].eq(C17_ARM)].copy()
    return pd.concat([base, c17], ignore_index=True, sort=False)


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


def _daily_price_table(minute_bars: pd.DataFrame) -> pd.DataFrame:
    if minute_bars.empty:
        return pd.DataFrame()
    ordered = minute_bars.sort_values(["vt_symbol", "bar_date", "bar_datetime"]).copy()
    daily = (
        ordered.groupby(["vt_symbol", "bar_date"], dropna=False)
        .agg(
            focus_price=("close", "last"),
            focus_day_high=("high", "max"),
            focus_day_low=("low", "min"),
            focus_day_minute_bars=("close", "size"),
        )
        .reset_index()
    )
    return daily


def _price_lookup(daily_price: pd.DataFrame) -> dict[tuple[str, pd.Timestamp], tuple[float, int, float, float]]:
    lookup: dict[tuple[str, pd.Timestamp], tuple[float, int, float, float]] = {}
    if daily_price.empty:
        return lookup
    for row in daily_price.itertuples(index=False):
        lookup[(str(row.vt_symbol), pd.Timestamp(row.bar_date).normalize())] = (
            float(row.focus_price),
            int(row.focus_day_minute_bars),
            float(row.focus_day_high),
            float(row.focus_day_low),
        )
    return lookup


def _future_outcomes(curve: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for arm, group in curve.sort_values(["arm", "date"]).groupby("arm", sort=False):
        data = group.reset_index(drop=True)
        equity = pd.to_numeric(data["account_equity"], errors="coerce").to_numpy(dtype=float)
        broker = pd.to_numeric(data["broker10_margin_to_equity_pct"], errors="coerce").to_numpy(dtype=float)
        dates = data["date"].tolist()
        for idx, item in data.iterrows():
            current = equity[idx]
            future_5 = equity[idx + 5] if idx + 5 < len(equity) else np.nan
            future_20 = equity[idx + 20] if idx + 20 < len(equity) else np.nan
            window_equity = equity[idx + 1 : min(len(equity), idx + 21)]
            window_broker = broker[idx + 1 : min(len(broker), idx + 21)]
            rows.append(
                {
                    "date": dates[idx],
                    "arm": arm,
                    "next5_return_pct": (future_5 / current - 1.0) * 100.0 if current > 0 else np.nan,
                    "next20_return_pct": (future_20 / current - 1.0) * 100.0 if current > 0 else np.nan,
                    "future20_min_return_pct": (
                        (np.nanmin(window_equity) / current - 1.0) * 100.0
                        if current > 0 and len(window_equity) > 0
                        else np.nan
                    ),
                    "future20_max_broker10_pct": np.nanmax(window_broker) if len(window_broker) > 0 else np.nan,
                }
            )
    return pd.DataFrame(rows)


def _build_daily_state(
    curve: pd.DataFrame,
    closed_lots: pd.DataFrame,
    price_map: dict[tuple[str, pd.Timestamp], tuple[float, int, float, float]],
    metadata: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    margin_ratios = metadata.get("margin_ratios", {})
    sizes = metadata.get("sizes", {})
    product_rows: list[dict[str, Any]] = []
    state_rows: list[dict[str, Any]] = []

    for arm, curve_group in curve.sort_values(["arm", "date"]).groupby("arm", sort=False):
        lots = closed_lots[closed_lots["arm"].eq(arm)].copy()
        for item in curve_group.itertuples(index=False):
            focus_date = pd.Timestamp(item.date).normalize()
            equity = _safe_float(item.account_equity)
            curve_broker10_pct = _safe_float(item.broker10_margin_to_equity_pct, 0.0)
            active = lots[lots["entry_date"].le(focus_date) & lots["exit_date"].ge(focus_date)].copy()
            lot_rows: list[dict[str, Any]] = []
            for _, lot in active.iterrows():
                vt_symbol = str(lot["vt_symbol"])
                size = _safe_float(lot.get("size"), _safe_float(sizes.get(vt_symbol), 0.0))
                margin_ratio = _safe_float(margin_ratios.get(vt_symbol), 0.0)
                volume = _safe_float(lot.get("volume"), 0.0)
                price, bars, high, low = price_map.get(
                    (vt_symbol, focus_date),
                    (_safe_float(lot.get("entry_price"), 0.0), 0, np.nan, np.nan),
                )
                exchange_margin = price * size * volume * margin_ratio if price > 0 and size > 0 else 0.0
                broker10_margin = exchange_margin * BROKER_MARGIN_MULTIPLIER
                broker10_pct = broker10_margin / equity * 100.0 if equity > 0 else np.nan
                lot_rows.append(
                    {
                        "date": focus_date,
                        "arm": arm,
                        "lot_id": lot.get("lot_id"),
                        "vt_symbol": vt_symbol,
                        "product_vt_symbol": str(lot.get("product", "")),
                        "direction": str(lot.get("direction", "")),
                        "entry_date": lot.get("entry_date"),
                        "exit_date": lot.get("exit_date"),
                        "volume": volume,
                        "focus_price": price,
                        "focus_day_minute_bars": bars,
                        "focus_day_high": high,
                        "focus_day_low": low,
                        "entry_price": _safe_float(lot.get("entry_price")),
                        "exit_price": _safe_float(lot.get("exit_price")),
                        "realized_pnl": _safe_float(lot.get("realized_pnl")),
                        "estimated_broker10_margin": broker10_margin,
                        "estimated_broker10_margin_to_equity_pct": broker10_pct,
                    }
                )
            if lot_rows:
                lot_frame = pd.DataFrame(lot_rows)
                grouped = (
                    lot_frame.groupby(["date", "arm", "product_vt_symbol", "direction"], dropna=False)
                    .agg(
                        active_lots=("lot_id", "count"),
                        volume=("volume", "sum"),
                        estimated_broker10_margin=("estimated_broker10_margin", "sum"),
                        estimated_broker10_margin_to_equity_pct=("estimated_broker10_margin_to_equity_pct", "sum"),
                        active_lot_realized_pnl=("realized_pnl", "sum"),
                        focus_day_minute_bars=("focus_day_minute_bars", "sum"),
                    )
                    .reset_index()
                    .sort_values("estimated_broker10_margin_to_equity_pct", ascending=False)
                )
                product_rows.extend(grouped.to_dict("records"))
                estimated_total_pct = float(grouped["estimated_broker10_margin_to_equity_pct"].sum())
                scale = curve_broker10_pct / estimated_total_pct if estimated_total_pct > 0 else np.nan
                scaled_values = grouped["estimated_broker10_margin_to_equity_pct"] * (scale if np.isfinite(scale) else 1.0)
                total_margin = float(grouped["estimated_broker10_margin"].sum())
                top1 = grouped.iloc[0]
                top1_scaled_pct = float(scaled_values.iloc[0]) if len(scaled_values) else 0.0
                top3_scaled_pct = float(scaled_values.head(3).sum()) if len(scaled_values) else 0.0
                top1_share = (
                    float(top1["estimated_broker10_margin"] / total_margin) if total_margin > 0 else np.nan
                )
                top3_share = (
                    float(grouped["estimated_broker10_margin"].head(3).sum() / total_margin)
                    if total_margin > 0
                    else np.nan
                )
                direction_share = (
                    grouped.groupby("direction")["estimated_broker10_margin"].sum().max() / total_margin
                    if total_margin > 0
                    else np.nan
                )
                active_lots = int(grouped["active_lots"].sum())
                product_direction_count = int(len(grouped))
                top_key = f"{top1['product_vt_symbol']}:{top1['direction']}"
            else:
                estimated_total_pct = 0.0
                scale = np.nan
                top1_scaled_pct = 0.0
                top3_scaled_pct = 0.0
                top1_share = np.nan
                top3_share = np.nan
                direction_share = np.nan
                active_lots = 0
                product_direction_count = 0
                top_key = ""
                top1 = pd.Series(dtype=object)
            pressure_state = bool(
                curve_broker10_pct >= ACCOUNT_HEAT_WATCH_PCT
                and top1_scaled_pct >= TOP1_PRODUCT_DIRECTION_WATCH_PCT
                and _safe_float(top3_share, 0.0) >= TOP3_PRODUCT_DIRECTION_SHARE_WATCH
            )
            state_rows.append(
                {
                    "date": focus_date,
                    "arm": arm,
                    "account_equity": equity,
                    "drawdown_pct": _safe_float(item.drawdown_pct),
                    "curve_broker10_margin_to_equity_pct": curve_broker10_pct,
                    "estimated_product_direction_total_broker10_pct": estimated_total_pct,
                    "estimate_to_curve_scale": scale,
                    "active_lots": active_lots,
                    "active_product_directions": product_direction_count,
                    "top_product_direction": top_key,
                    "top1_product_direction_broker10_pct_scaled": top1_scaled_pct,
                    "top3_product_direction_broker10_pct_scaled": top3_scaled_pct,
                    "top1_product_direction_share": top1_share,
                    "top3_product_direction_share": top3_share,
                    "dominant_direction_margin_share": direction_share,
                    "account_heat_watch": curve_broker10_pct >= ACCOUNT_HEAT_WATCH_PCT,
                    "account_heat_danger": curve_broker10_pct >= ACCOUNT_HEAT_DANGER_PCT,
                    "top1_product_direction_watch": top1_scaled_pct >= TOP1_PRODUCT_DIRECTION_WATCH_PCT,
                    "top3_cluster_watch": _safe_float(top3_share, 0.0) >= TOP3_PRODUCT_DIRECTION_SHARE_WATCH,
                    "holding_pressure_state": pressure_state,
                    "top_product_direction_active_lots": int(top1.get("active_lots", 0)) if not top1.empty else 0,
                    "top_product_direction_volume": _safe_float(top1.get("volume"), 0.0) if not top1.empty else 0.0,
                    "top_product_direction_bars": int(_safe_float(top1.get("focus_day_minute_bars"), 0.0))
                    if not top1.empty
                    else 0,
                }
            )
    state = pd.DataFrame(state_rows)
    products = pd.DataFrame(product_rows)
    if not products.empty:
        products["date"] = pd.to_datetime(products["date"], errors="coerce").dt.normalize()
    outcomes = _future_outcomes(curve)
    state = state.merge(outcomes, on=["date", "arm"], how="left")
    state["date"] = pd.to_datetime(state["date"], errors="coerce").dt.normalize()
    return state.sort_values(["arm", "date"]).reset_index(drop=True), products.reset_index(drop=True)


def _pressure_bucket(daily_state: pd.DataFrame) -> pd.DataFrame:
    if daily_state.empty:
        return pd.DataFrame()
    data = daily_state.copy()
    data["year"] = data["date"].dt.year
    grouped = (
        data.groupby(["arm", "holding_pressure_state"], dropna=False)
        .agg(
            days=("date", "count"),
            years=("year", "nunique"),
            median_broker10=("curve_broker10_margin_to_equity_pct", "median"),
            max_broker10=("curve_broker10_margin_to_equity_pct", "max"),
            median_top1_pct=("top1_product_direction_broker10_pct_scaled", "median"),
            median_top3_share=("top3_product_direction_share", "median"),
            median_next5_return_pct=("next5_return_pct", "median"),
            median_next20_return_pct=("next20_return_pct", "median"),
            mean_next20_return_pct=("next20_return_pct", "mean"),
            negative_next20_share=("next20_return_pct", lambda s: float(pd.to_numeric(s, errors="coerce").lt(0).mean())),
            worst_future20_min_return_pct=("future20_min_return_pct", "min"),
            median_future20_min_return_pct=("future20_min_return_pct", "median"),
        )
        .reset_index()
    )
    return grouped.sort_values(["arm", "holding_pressure_state"]).reset_index(drop=True)


def _c17_c9_delta(daily_state: pd.DataFrame) -> pd.DataFrame:
    keep = [
        "date",
        "arm",
        "curve_broker10_margin_to_equity_pct",
        "top1_product_direction_broker10_pct_scaled",
        "top3_product_direction_share",
        "dominant_direction_margin_share",
        "holding_pressure_state",
        "next20_return_pct",
        "future20_min_return_pct",
        "top_product_direction",
    ]
    data = daily_state[daily_state["arm"].isin([C9_ARM, C17_ARM])][keep].copy()
    wide = data.pivot(index="date", columns="arm")
    wide.columns = [f"{metric}__{arm}" for metric, arm in wide.columns]
    wide = wide.reset_index()
    for metric in keep:
        if metric == "date" or metric == "arm":
            continue
        for arm in [C9_ARM, C17_ARM]:
            column = f"{metric}__{arm}"
            if column not in wide.columns:
                wide[column] = np.nan
    wide["c17_minus_c9_broker10_pct"] = (
        pd.to_numeric(wide[f"curve_broker10_margin_to_equity_pct__{C17_ARM}"], errors="coerce")
        - pd.to_numeric(wide[f"curve_broker10_margin_to_equity_pct__{C9_ARM}"], errors="coerce")
    )
    wide["c17_minus_c9_top1_pct"] = (
        pd.to_numeric(wide[f"top1_product_direction_broker10_pct_scaled__{C17_ARM}"], errors="coerce")
        - pd.to_numeric(wide[f"top1_product_direction_broker10_pct_scaled__{C9_ARM}"], errors="coerce")
    )
    wide["c17_pressure_only"] = (
        wide[f"holding_pressure_state__{C17_ARM}"].astype(bool)
        & ~wide[f"holding_pressure_state__{C9_ARM}"].astype(bool)
    )
    wide["both_pressure"] = (
        wide[f"holding_pressure_state__{C17_ARM}"].astype(bool)
        & wide[f"holding_pressure_state__{C9_ARM}"].astype(bool)
    )
    return wide.sort_values(["c17_pressure_only", "c17_minus_c9_broker10_pct"], ascending=[False, False]).reset_index(drop=True)


def _plot_summary(daily_state: pd.DataFrame, pressure_bucket: pd.DataFrame, c17_c9_delta: pd.DataFrame) -> None:
    if daily_state.empty:
        return
    c9 = daily_state[daily_state["arm"].eq(C9_ARM)].copy()
    c17 = daily_state[daily_state["arm"].eq(C17_ARM)].copy()
    fig, axes = plt.subplots(3, 1, figsize=(16, 12), constrained_layout=True)
    for arm_data, label, color in [(c9, "C9", "#2563eb"), (c17, "C17", "#dc2626")]:
        axes[0].plot(arm_data["date"], arm_data["curve_broker10_margin_to_equity_pct"], label=f"{label} broker10", color=color)
        axes[0].plot(
            arm_data["date"],
            arm_data["top1_product_direction_broker10_pct_scaled"],
            label=f"{label} top1 product-direction",
            color=color,
            alpha=0.45,
            linestyle="--",
        )
    axes[0].axhline(ACCOUNT_HEAT_WATCH_PCT, color="#92400e", linestyle=":", linewidth=1.0, label="80% account heat")
    axes[0].set_title("Stage885 all-path holding pressure state")
    axes[0].set_ylabel("percent of equity")
    axes[0].legend(loc="best", fontsize=8)
    axes[0].grid(True, alpha=0.25)

    scatter = axes[1].scatter(
        c17["top1_product_direction_broker10_pct_scaled"],
        c17["curve_broker10_margin_to_equity_pct"],
        c=pd.to_numeric(c17["next20_return_pct"], errors="coerce"),
        cmap="RdYlGn",
        s=16,
        alpha=0.75,
    )
    axes[1].axhline(ACCOUNT_HEAT_WATCH_PCT, color="#92400e", linestyle=":", linewidth=1.0)
    axes[1].axvline(TOP1_PRODUCT_DIRECTION_WATCH_PCT, color="#92400e", linestyle=":", linewidth=1.0)
    axes[1].set_title("C17 pressure scatter, colored by next 20 trading-day return")
    axes[1].set_xlabel("top1 product-direction broker10 pct")
    axes[1].set_ylabel("account broker10 pct")
    fig.colorbar(scatter, ax=axes[1], label="next20 return pct")
    axes[1].grid(True, alpha=0.25)

    if not pressure_bucket.empty:
        bucket = pressure_bucket[pressure_bucket["arm"].isin([C9_ARM, C17_ARM])].copy()
        bucket["label"] = bucket["arm"].map({C9_ARM: "C9", C17_ARM: "C17"}) + ":" + bucket[
            "holding_pressure_state"
        ].astype(str)
        x = np.arange(len(bucket))
        axes[2].bar(x, bucket["negative_next20_share"] * 100.0, color="#64748b", label="negative next20 share")
        ax2 = axes[2].twinx()
        ax2.plot(x, bucket["median_next20_return_pct"], color="#16a34a", marker="o", label="median next20 return")
        axes[2].set_xticks(x)
        axes[2].set_xticklabels(bucket["label"], rotation=25, ha="right")
        axes[2].set_ylabel("negative next20 share %")
        ax2.set_ylabel("median next20 return %")
        handles1, labels1 = axes[2].get_legend_handles_labels()
        handles2, labels2 = ax2.get_legend_handles_labels()
        axes[2].legend(handles1 + handles2, labels1 + labels2, loc="best")
        axes[2].grid(True, alpha=0.25)
    fig.savefig(SUMMARY_CHART_PATH, dpi=150)
    plt.close(fig)


def _select_atlas_rows(daily_state: pd.DataFrame, product_daily: pd.DataFrame) -> pd.DataFrame:
    if daily_state.empty or product_daily.empty:
        return pd.DataFrame()
    c17_pressure = daily_state[
        daily_state["arm"].eq(C17_ARM)
        & daily_state["holding_pressure_state"].eq(True)
        & pd.to_numeric(daily_state["top_product_direction_bars"], errors="coerce").fillna(0).gt(0)
    ].copy()
    if c17_pressure.empty:
        c17_pressure = daily_state[daily_state["arm"].eq(C17_ARM)].copy()
    selected_days = c17_pressure.sort_values(
        ["curve_broker10_margin_to_equity_pct", "top1_product_direction_broker10_pct_scaled"],
        ascending=False,
    ).head(MAX_ATLAS_ROWS)
    rows: list[pd.DataFrame] = []
    for _, day in selected_days.iterrows():
        candidates = product_daily[
            product_daily["arm"].eq(C17_ARM)
            & product_daily["date"].eq(day["date"])
            & product_daily.apply(lambda r: f"{r['product_vt_symbol']}:{r['direction']}" == day["top_product_direction"], axis=1)
        ].copy()
        if not candidates.empty:
            rows.append(candidates.head(1))
    return pd.concat(rows, ignore_index=True, sort=False) if rows else pd.DataFrame()


def _representative_lot(
    closed_lots: pd.DataFrame,
    row: pd.Series,
    price_map: dict[tuple[str, pd.Timestamp], tuple[float, int, float, float]],
) -> pd.Series:
    focus_date = pd.Timestamp(row["date"]).normalize()
    active = closed_lots[
        closed_lots["arm"].eq(C17_ARM)
        & closed_lots["product"].astype(str).eq(str(row["product_vt_symbol"]))
        & closed_lots["direction"].astype(str).eq(str(row["direction"]))
        & closed_lots["entry_date"].le(focus_date)
        & closed_lots["exit_date"].ge(focus_date)
    ].copy()
    if active.empty:
        return pd.Series(dtype=object)
    active["focus_day_minute_bars"] = active["vt_symbol"].astype(str).map(
        lambda vt: price_map.get((vt, focus_date), (np.nan, 0, np.nan, np.nan))[1]
    )
    active = active.sort_values(["focus_day_minute_bars", "volume"], ascending=[False, False])
    return active.iloc[0]


def _plot_atlas(
    atlas_products: pd.DataFrame,
    closed_lots: pd.DataFrame,
    minute_by_symbol: dict[str, pd.DataFrame],
    price_map: dict[tuple[str, pd.Timestamp], tuple[float, int, float, float]],
) -> tuple[list[Path], pd.DataFrame]:
    if atlas_products.empty:
        return [], pd.DataFrame()
    paths: list[Path] = []
    manifest: list[dict[str, Any]] = []
    for page_start in range(0, len(atlas_products), PER_PAGE):
        page_rows = atlas_products.iloc[page_start : page_start + PER_PAGE]
        page = page_start // PER_PAGE + 1
        fig, axes = plt.subplots(PER_PAGE, 1, figsize=(16, 4.4 * PER_PAGE), constrained_layout=True)
        axes_arr = np.atleast_1d(axes)
        for ax, (_, row) in zip(axes_arr, page_rows.iterrows(), strict=False):
            lot = _representative_lot(closed_lots, row, price_map)
            focus_date = pd.Timestamp(row["date"]).normalize()
            vt_symbol = str(lot.get("vt_symbol", ""))
            bars = minute_by_symbol.get(vt_symbol, pd.DataFrame())
            day = pd.DataFrame()
            if not bars.empty:
                day = bars[bars["bar_date"].eq(focus_date)].copy().sort_values("bar_datetime").reset_index(drop=True)
            if day.empty:
                ax.text(
                    0.5,
                    0.5,
                    f"missing minute bars {vt_symbol} {focus_date:%Y-%m-%d}",
                    ha="center",
                    va="center",
                )
                ax.set_axis_off()
            else:
                s825._plot_candles(ax, day)
                for label, price, color, linestyle in [
                    ("entry", lot.get("entry_price"), "#2563eb", "-"),
                    ("focus close", price_map.get((vt_symbol, focus_date), (np.nan, 0, np.nan, np.nan))[0], "#0f766e", "--"),
                    ("exit", lot.get("exit_price"), "#dc2626", ":"),
                ]:
                    value = _safe_float(price)
                    if np.isfinite(value):
                        ax.axhline(value, color=color, linestyle=linestyle, linewidth=0.9, label=label)
                ticks = np.linspace(0, len(day) - 1, num=min(8, len(day)), dtype=int)
                ax.set_xticks(ticks)
                ax.set_xticklabels([pd.Timestamp(day.loc[pos, "bar_datetime"]).strftime("%H:%M") for pos in ticks], fontsize=7)
                handles, labels = ax.get_legend_handles_labels()
                if handles:
                    dedup = dict(zip(labels, handles, strict=False))
                    ax.legend(dedup.values(), dedup.keys(), loc="best", fontsize=7)
                ax.grid(True, alpha=0.18)
            ax.set_title(
                f"{focus_date:%Y-%m-%d} {row.get('product_vt_symbol')} {row.get('direction')} "
                f"C17 pressure {row.get('estimated_broker10_margin_to_equity_pct'):.2f}%",
                fontsize=9,
            )
            manifest.append(
                {
                    "page": page,
                    "date": focus_date.date().isoformat(),
                    "vt_symbol": vt_symbol,
                    "product_vt_symbol": row.get("product_vt_symbol"),
                    "direction": row.get("direction"),
                    "active_lots": int(_safe_float(row.get("active_lots"), 0.0)),
                    "volume": _safe_float(row.get("volume")),
                    "estimated_broker10_margin_to_equity_pct": _safe_float(
                        row.get("estimated_broker10_margin_to_equity_pct")
                    ),
                    "representative_lot_id": lot.get("lot_id"),
                    "focus_day_minute_bars": int(
                        price_map.get((vt_symbol, focus_date), (np.nan, 0, np.nan, np.nan))[1]
                    )
                    if vt_symbol
                    else 0,
                }
            )
        for ax in axes_arr[len(page_rows) :]:
            ax.set_axis_off()
        path = Path(str(ATLAS_TEMPLATE).format(page=page))
        fig.suptitle("Stage885 C17 holding-pressure product-direction minute-K atlas", fontsize=13)
        fig.savefig(path, dpi=150)
        plt.close(fig)
        paths.append(path)
    return paths, pd.DataFrame(manifest)


def _decision(pressure_bucket: pd.DataFrame, c17_c9_delta: pd.DataFrame) -> str:
    if pressure_bucket.empty:
        return "stage885_pressure_state_failed_no_state"
    c17_bucket = pressure_bucket[
        pressure_bucket["arm"].eq(C17_ARM) & pressure_bucket["holding_pressure_state"].eq(True)
    ]
    c17_only_days = int(c17_c9_delta.get("c17_pressure_only", pd.Series(dtype=bool)).astype(bool).sum())
    if c17_bucket.empty:
        return "stage885_pressure_state_too_sparse_no_rule"
    neg_share = _safe_float(c17_bucket["negative_next20_share"].iloc[0])
    median_next20 = _safe_float(c17_bucket["median_next20_return_pct"].iloc[0])
    if c17_only_days > 0 and (neg_share < 0.60 or median_next20 >= 0):
        return "stage885_pressure_state_real_but_not_trade_rule_mixed_outcomes"
    return "stage885_pressure_state_needs_readonly_followup_no_engine"


def _write_report(
    daily_state: pd.DataFrame,
    product_daily: pd.DataFrame,
    pressure_bucket: pd.DataFrame,
    c17_c9_delta: pd.DataFrame,
    atlas_paths: list[Path],
    decision: str,
) -> None:
    c17_pressure_days = daily_state[
        daily_state["arm"].eq(C17_ARM) & daily_state["holding_pressure_state"].eq(True)
    ].sort_values("curve_broker10_margin_to_equity_pct", ascending=False)
    c17_only = c17_c9_delta[c17_c9_delta["c17_pressure_only"].astype(bool)].head(12)
    top_products = product_daily[product_daily["arm"].eq(C17_ARM)].sort_values(
        "estimated_broker10_margin_to_equity_pct",
        ascending=False,
    ).head(12)
    lines = [
        "# Stage885 持仓压力状态只读审计",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 源候选：`{stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION}`",
        "- 阶段性质：全路径只读持仓压力状态审计；不新增交易规则、不改正式版、不改 Stage819 候选配置、不连接 CTP、不调用下单。",
        "- 输入说明：C4/C9 closed lots 读取 Stage863，C17 closed lots 读取 Stage883，避免把 Stage883 仅含 C17 的明细误当成 C9/C4 无持仓。",
        "",
        "## 外部调研判断",
        "",
        "- CME margin / open-interest 资料提示，敞口和流动性要在组合层判断，不能只看单笔交易。",
        "- 趋势跟随 pyramiding 资料强调 portfolio heat 和仓位集中度是硬约束，而不是收益之后就一定能加仓。",
        "- 我的判断：Stage884 已证明 C17 是分子扩张；Stage885 先看是否存在低自由度、实时可观测的 holding pressure state，不能直接写品种/年份补丁。",
        "",
        "## 压力状态定义",
        "",
        f"- account heat watch：broker10 margin/equity >= `{ACCOUNT_HEAT_WATCH_PCT}%`。",
        f"- top1 product-direction watch：top1 product-direction scaled broker10/equity >= `{TOP1_PRODUCT_DIRECTION_WATCH_PCT}%`。",
        f"- top3 cluster watch：top3 product-direction margin share >= `{TOP3_PRODUCT_DIRECTION_SHARE_WATCH}`。",
        "- holding pressure state：三项同时成立。后续收益/回撤只用于只读归因，不作为实时判断条件。",
        "",
        "## 分桶摘要",
        "",
        _md_table(pressure_bucket, max_rows=20),
        "",
        "## C17 压力日期",
        "",
        _md_table(c17_pressure_days.head(20), max_rows=20),
        "",
        "## C17 独有压力日期 vs C9",
        "",
        _md_table(c17_only, max_rows=12),
        "",
        "## C17 产品方向压力 Top",
        "",
        _md_table(top_products, max_rows=12),
        "",
        "## 视觉输出",
        "",
        f"- summary chart：`{SUMMARY_CHART_PATH}`",
        *[f"- atlas page：`{path}`" for path in atlas_paths],
        "",
        "## 判断",
        "",
        f"- 决策：`{decision}`。",
        "- 若 pressure state 后续结果仍然混杂或偏正，则不能把它改写为直接减仓/退出规则；它只能作为下一轮更细只读复盘的定位标签。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if not DECISION_IN.exists():
        raise RuntimeError(f"missing Stage884 decision: {DECISION_IN}")
    metadata = s513._metadata()
    curve = s884._prepare_curve(_load_required_csv(CURVE_IN))
    closed_lots = _load_closed_lots_for_arms()
    vt_symbols = set(str(item) for item in metadata["vt_symbols"])
    minute_bars = _load_full_minute_bars(vt_symbols)
    minute_by_symbol = s825._minute_groups(minute_bars)
    price_table = _daily_price_table(minute_bars)
    price_map = _price_lookup(price_table)

    daily_state, product_daily = _build_daily_state(curve, closed_lots, price_map, metadata)
    pressure_bucket = _pressure_bucket(daily_state)
    c17_c9_delta = _c17_c9_delta(daily_state)
    _plot_summary(daily_state, pressure_bucket, c17_c9_delta)
    atlas_products = _select_atlas_rows(daily_state, product_daily)
    atlas_paths, atlas_manifest = _plot_atlas(atlas_products, closed_lots, minute_by_symbol, price_map)

    decision = _decision(pressure_bucket, c17_c9_delta)

    daily_state.to_csv(DAILY_STATE_PATH, index=False, encoding="utf-8-sig")
    product_daily.to_csv(PRODUCT_DIRECTION_DAILY_PATH, index=False, encoding="utf-8-sig")
    pressure_bucket.to_csv(PRESSURE_BUCKET_PATH, index=False, encoding="utf-8-sig")
    c17_c9_delta.to_csv(C17_C9_DELTA_PATH, index=False, encoding="utf-8-sig")
    atlas_manifest.to_csv(ATLAS_MANIFEST_PATH, index=False, encoding="utf-8-sig")
    _write_report(daily_state, product_daily, pressure_bucket, c17_c9_delta, atlas_paths, decision)

    payload = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_stage884_decision": json.loads(DECISION_IN.read_text(encoding="utf-8")),
        "definition": {
            "account_heat_watch_pct": ACCOUNT_HEAT_WATCH_PCT,
            "account_heat_danger_pct": ACCOUNT_HEAT_DANGER_PCT,
            "top1_product_direction_watch_pct": TOP1_PRODUCT_DIRECTION_WATCH_PCT,
            "top3_product_direction_share_watch": TOP3_PRODUCT_DIRECTION_SHARE_WATCH,
            "holding_pressure_state": "account_heat_watch and top1_product_direction_watch and top3_cluster_watch",
            "no_parameter_scan": True,
        },
        "inputs": {
            "curve": str(CURVE_IN),
            "c4_c9_closed_lots": str(STAGE863_CLOSED_LOTS_IN),
            "c17_closed_lots": str(C17_CLOSED_LOTS_IN),
        },
        "decision": decision,
        "pressure_bucket": pressure_bucket.to_dict("records"),
        "c17_pressure_days": int(
            daily_state[daily_state["arm"].eq(C17_ARM)]["holding_pressure_state"].astype(bool).sum()
        ),
        "c17_only_pressure_days": int(c17_c9_delta["c17_pressure_only"].astype(bool).sum()),
        "strategy_changed": False,
        "ctp_connected": False,
        "order_api_called": False,
        "formal_ab_triggered": False,
        "outputs": {
            "report": str(REPORT_PATH),
            "daily_state": str(DAILY_STATE_PATH),
            "product_direction_daily": str(PRODUCT_DIRECTION_DAILY_PATH),
            "pressure_bucket": str(PRESSURE_BUCKET_PATH),
            "c17_c9_delta": str(C17_C9_DELTA_PATH),
            "summary_chart": str(SUMMARY_CHART_PATH),
            "atlas_manifest": str(ATLAS_MANIFEST_PATH),
            "atlas_pages": [str(path) for path in atlas_paths],
        },
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(payload), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
