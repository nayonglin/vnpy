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
STAGE = "Stage836"
MODEL_TAG = "stage836_stage827_stop_reuse_forensics_v1"
OUTPUT_PREFIX = "qmt_roll_stage836_stage827_stop_reuse_forensics"

START = pd.Timestamp("2018-01-01")
END = pd.Timestamp("2026-05-29")

STAGE827_PREFIX = "qmt_roll_stage827_stage819_intraday_c2_engine_ac"
STAGE827_TAG = "stage827_stage819_intraday_c2_engine_ac_v1"
STAGE830_PREFIX = "qmt_roll_stage830_stage827_c2_broker10_margin_cap"
STAGE830_TAG = "stage830_stage827_c2_broker10_margin_cap_v1"

BASE_ARM = "stage827_stage819_baseline"
C2_ARM = "stage827_stage819_c2_engine"
C4_ARM = "stage830_stage819_c2_broker10_100_cap"

STAGE827_CLOSED_PATH = OUTPUT_DIR / f"{STAGE827_PREFIX}_closed_lots_{STAGE827_TAG}.csv"
STAGE827_EVENTS_PATH = OUTPUT_DIR / f"{STAGE827_PREFIX}_intraday_events_{STAGE827_TAG}.csv"
STAGE827_CURVE_PATH = OUTPUT_DIR / f"{STAGE827_PREFIX}_curve_{STAGE827_TAG}.csv"
STAGE830_CLOSED_PATH = OUTPUT_DIR / f"{STAGE830_PREFIX}_closed_lots_{STAGE830_TAG}.csv"
STAGE830_EVENTS_PATH = OUTPUT_DIR / f"{STAGE830_PREFIX}_intraday_events_{STAGE830_TAG}.csv"

NEAREST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_nearest_stop_attribution_{MODEL_TAG}.csv"
NEAREST_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_nearest_summary_{MODEL_TAG}.csv"
EVENT_WINDOW_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_window_attribution_{MODEL_TAG}.csv"
EVENT_WINDOW_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_window_summary_{MODEL_TAG}.csv"
EXPOSURE_BUCKET_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_exposure_bucket_{MODEL_TAG}.csv"
PRODUCT_BUCKET_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_bucket_{MODEL_TAG}.csv"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_reuse_chart_{MODEL_TAG}.png"
ATLAS_MANIFEST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_manifest_{MODEL_TAG}.csv"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_atlas_page{{page:03d}}_{MODEL_TAG}.png"

HORIZONS = [1, 3, 5, 10]
MAX_HORIZON = max(HORIZONS)
PER_PAGE = 4
MAX_ATLAS_PAGES = 3


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _safe_float(value: Any, default: float = np.nan) -> float:
    return s825._safe_float(value, default=default)


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"Missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _normal_date(value: Any) -> pd.Timestamp:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return pd.NaT
    if getattr(ts, "tzinfo", None) is not None:
        ts = ts.tz_convert("Asia/Shanghai").tz_localize(None)
    return pd.Timestamp(ts).normalize()


def _prepare_closed(path: Path, arm: str) -> pd.DataFrame:
    data = _load_csv(path)
    data = data[data["arm"].astype(str).eq(arm)].copy()
    for column in ("entry_date", "exit_date"):
        data[column] = pd.to_datetime(data[column], errors="coerce").dt.tz_localize(None).dt.normalize()
    numeric_cols = [
        "entry_price",
        "exit_price",
        "volume",
        "size",
        "realized_pnl",
        "risk_amount",
        "r_multiple",
        "selected_volume",
        "target_risk_amount",
        "stop_distance",
        "entry_risk_distance_pct",
    ]
    for column in numeric_cols:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    data["entry_price_key"] = pd.to_numeric(data.get("entry_price"), errors="coerce").round(6)
    data["open_key"] = (
        data["entry_date"].dt.strftime("%Y-%m-%d").fillna("")
        + "|"
        + data["vt_symbol"].astype(str)
        + "|"
        + data["direction"].astype(str)
        + "|"
        + data["signal"].astype(str)
        + "|"
        + data["entry_context"].astype(str)
        + "|"
        + data["layer_kind"].astype(str)
        + "|"
        + data["entry_price_key"].astype(str)
    )
    return data


def _open_aggregate(lots: pd.DataFrame, prefix: str) -> pd.DataFrame:
    agg_spec: dict[str, Any] = {
        "lot_id": lambda x: ",".join(str(int(v)) for v in x.dropna().astype(float)),
        "open_trade_id": lambda x: ",".join(str(v) for v in x.dropna().astype(str)),
        "entry_date": "min",
        "exit_date": "max",
        "vt_symbol": "first",
        "product": "first",
        "direction": "first",
        "signal": lambda x: "|".join(sorted(set(str(v) for v in x.dropna()))),
        "entry_context": lambda x: "|".join(sorted(set(str(v) for v in x.dropna()))),
        "layer_kind": lambda x: "|".join(sorted(set(str(v) for v in x.dropna()))),
        "exit_reason": lambda x: "|".join(sorted(set(str(v) for v in x.dropna()))),
        "entry_price": "mean",
        "exit_price": "mean",
        "stop_distance": "mean",
        "entry_risk_distance_pct": "mean",
        "volume": "sum",
        "selected_volume": "sum",
        "risk_amount": "sum",
        "target_risk_amount": "sum",
        "realized_pnl": "sum",
        "r_multiple": "sum",
    }
    available = {key: value for key, value in agg_spec.items() if key in lots.columns}
    result = lots.groupby("open_key", dropna=False).agg(available).reset_index()
    result = result.add_prefix(f"{prefix}_").rename(columns={f"{prefix}_open_key": "open_key"})
    return result


def _pair_open_delta(a_lots: pd.DataFrame, c_lots: pd.DataFrame, source_arm: str) -> pd.DataFrame:
    a = _open_aggregate(a_lots, "A")
    c = _open_aggregate(c_lots, "C")
    merged = a.merge(c, on="open_key", how="outer")
    for column in ("entry_date", "exit_date", "vt_symbol", "product", "direction", "signal", "entry_context", "layer_kind"):
        merged[column] = merged.get(f"C_{column}").combine_first(merged.get(f"A_{column}"))
    for column in ("volume", "selected_volume", "risk_amount", "target_risk_amount", "realized_pnl", "r_multiple"):
        merged[f"{column}_delta_C_minus_A"] = (
            pd.to_numeric(merged.get(f"C_{column}"), errors="coerce").fillna(0.0)
            - pd.to_numeric(merged.get(f"A_{column}"), errors="coerce").fillna(0.0)
        )
    merged["entry_date"] = pd.to_datetime(merged["entry_date"], errors="coerce").dt.normalize()
    merged["exit_date"] = pd.to_datetime(merged["exit_date"], errors="coerce").dt.normalize()
    merged["source_arm"] = source_arm
    a_exists = merged["A_vt_symbol"].notna()
    c_exists = merged["C_vt_symbol"].notna()
    vol_delta = pd.to_numeric(merged["volume_delta_C_minus_A"], errors="coerce").fillna(0.0)
    merged["exposure_type"] = np.select(
        [
            ~a_exists & c_exists,
            a_exists & ~c_exists,
            a_exists & c_exists & vol_delta.gt(0),
            a_exists & c_exists & vol_delta.lt(0),
            a_exists & c_exists & vol_delta.eq(0),
        ],
        ["C_only", "A_only", "C_larger", "C_smaller", "both_equal"],
        default="unknown",
    )
    merged["incremental_c_exposure"] = merged["exposure_type"].isin(["C_only", "C_larger"]).astype(int)
    merged["reduced_c_exposure"] = merged["exposure_type"].isin(["A_only", "C_smaller"]).astype(int)
    return merged


def _load_events(path: Path, source_arm: str) -> pd.DataFrame:
    events = _load_csv(path)
    events = events.copy()
    events["source_arm"] = source_arm
    events["hit_dt"] = pd.to_datetime(events.get("hit_time"), errors="coerce")
    missing = events["hit_dt"].isna()
    if missing.any():
        events.loc[missing, "hit_dt"] = pd.to_datetime(events.loc[missing, "datetime"], errors="coerce")
    events["hit_date"] = events["hit_dt"].map(_normal_date)
    events["event_id"] = [f"{source_arm}_stop_{idx:03d}" for idx in range(1, len(events) + 1)]
    for column in ("entry_price", "stop_price", "confirm_price", "risk_price", "volume"):
        if column in events.columns:
            events[column] = pd.to_numeric(events[column], errors="coerce")
    return events


def _trading_calendar() -> pd.DataFrame:
    curve = _load_csv(STAGE827_CURVE_PATH)
    dates = pd.to_datetime(curve["date"], errors="coerce").dt.normalize().dropna().drop_duplicates().sort_values()
    calendar = pd.DataFrame({"date": dates.reset_index(drop=True)})
    calendar["td_index"] = np.arange(len(calendar), dtype=int)
    return calendar


def _add_td_index(frame: pd.DataFrame, calendar: pd.DataFrame, date_col: str, out_col: str) -> pd.DataFrame:
    mapping = calendar.set_index("date")["td_index"]
    frame[out_col] = pd.to_datetime(frame[date_col], errors="coerce").dt.normalize().map(mapping)
    return frame


def _nearest_stop_attribution(delta: pd.DataFrame, events: pd.DataFrame, calendar: pd.DataFrame) -> pd.DataFrame:
    rows: list[pd.Series] = []
    events = _add_td_index(events.copy(), calendar, "hit_date", "hit_td_index")
    events = events.dropna(subset=["hit_td_index"]).sort_values("hit_td_index").reset_index(drop=True)
    delta = _add_td_index(delta.copy(), calendar, "entry_date", "entry_td_index")
    delta = delta.dropna(subset=["entry_td_index"]).sort_values("entry_td_index").reset_index(drop=True)
    if events.empty or delta.empty:
        return pd.DataFrame()
    event_indices = events["hit_td_index"].astype(int).to_numpy()
    for _, row in delta.iterrows():
        entry_idx = int(row["entry_td_index"])
        pos = np.searchsorted(event_indices, entry_idx, side="left") - 1
        if pos < 0:
            continue
        event = events.iloc[pos]
        trading_days_after = entry_idx - int(event["hit_td_index"])
        if trading_days_after <= 0 or trading_days_after > MAX_HORIZON:
            continue
        item = row.copy()
        item["nearest_event_id"] = event["event_id"]
        item["nearest_stop_hit_date"] = event["hit_date"]
        item["nearest_stop_hit_time"] = event["hit_dt"]
        item["nearest_stop_vt_symbol"] = event.get("vt_symbol", "")
        item["nearest_stop_product"] = event.get("product_vt_symbol", "")
        item["nearest_stop_direction"] = event.get("direction", "")
        item["nearest_stop_exit_reason"] = event.get("exit_reason", "")
        item["trading_days_after_stop"] = trading_days_after
        item["same_product_as_nearest_stop"] = int(str(row.get("product", "")) == str(event.get("product_vt_symbol", "")))
        item["same_direction_as_nearest_stop"] = int(str(row.get("direction", "")) == str(event.get("direction", "")))
        item["same_product_direction_as_nearest_stop"] = int(
            item["same_product_as_nearest_stop"] and item["same_direction_as_nearest_stop"]
        )
        rows.append(item)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def _nearest_summary(nearest: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if nearest.empty:
        return pd.DataFrame()
    for source, source_group in nearest.groupby("source_arm", sort=False):
        for horizon in HORIZONS:
            group = source_group[pd.to_numeric(source_group["trading_days_after_stop"], errors="coerce").le(horizon)].copy()
            incremental = group[group["incremental_c_exposure"].eq(1)]
            reduced = group[group["reduced_c_exposure"].eq(1)]
            rows.append(
                {
                    "source_arm": source,
                    "horizon_trading_days": horizon,
                    "rows": int(len(group)),
                    "incremental_rows": int(len(incremental)),
                    "reduced_rows": int(len(reduced)),
                    "volume_delta_sum": float(pd.to_numeric(group["volume_delta_C_minus_A"], errors="coerce").sum()),
                    "risk_amount_delta_sum": float(pd.to_numeric(group["risk_amount_delta_C_minus_A"], errors="coerce").sum()),
                    "realized_pnl_delta_sum": float(pd.to_numeric(group["realized_pnl_delta_C_minus_A"], errors="coerce").sum()),
                    "incremental_volume_delta_sum": float(pd.to_numeric(incremental["volume_delta_C_minus_A"], errors="coerce").sum()),
                    "incremental_risk_delta_sum": float(pd.to_numeric(incremental["risk_amount_delta_C_minus_A"], errors="coerce").sum()),
                    "incremental_pnl_delta_sum": float(pd.to_numeric(incremental["realized_pnl_delta_C_minus_A"], errors="coerce").sum()),
                    "reduced_volume_delta_sum": float(pd.to_numeric(reduced["volume_delta_C_minus_A"], errors="coerce").sum()),
                    "reduced_risk_delta_sum": float(pd.to_numeric(reduced["risk_amount_delta_C_minus_A"], errors="coerce").sum()),
                    "reduced_pnl_delta_sum": float(pd.to_numeric(reduced["realized_pnl_delta_C_minus_A"], errors="coerce").sum()),
                    "incremental_positive_rows": int(pd.to_numeric(incremental["realized_pnl_delta_C_minus_A"], errors="coerce").gt(0).sum()),
                    "incremental_negative_rows": int(pd.to_numeric(incremental["realized_pnl_delta_C_minus_A"], errors="coerce").lt(0).sum()),
                    "incremental_same_product_pnl": float(
                        pd.to_numeric(
                            incremental[incremental["same_product_as_nearest_stop"].eq(1)]["realized_pnl_delta_C_minus_A"],
                            errors="coerce",
                        ).sum()
                    ),
                    "incremental_cross_product_pnl": float(
                        pd.to_numeric(
                            incremental[incremental["same_product_as_nearest_stop"].eq(0)]["realized_pnl_delta_C_minus_A"],
                            errors="coerce",
                        ).sum()
                    ),
                }
            )
    return pd.DataFrame(rows)


def _event_window_attribution(delta: pd.DataFrame, events: pd.DataFrame, calendar: pd.DataFrame) -> pd.DataFrame:
    delta = _add_td_index(delta.copy(), calendar, "entry_date", "entry_td_index")
    events = _add_td_index(events.copy(), calendar, "hit_date", "hit_td_index")
    rows: list[dict[str, Any]] = []
    delta = delta.dropna(subset=["entry_td_index"]).copy()
    events = events.dropna(subset=["hit_td_index"]).copy()
    for _, event in events.iterrows():
        event_idx = int(event["hit_td_index"])
        for horizon in HORIZONS:
            group = delta[
                pd.to_numeric(delta["entry_td_index"], errors="coerce").gt(event_idx)
                & pd.to_numeric(delta["entry_td_index"], errors="coerce").le(event_idx + horizon)
            ].copy()
            incremental = group[group["incremental_c_exposure"].eq(1)]
            rows.append(
                {
                    "source_arm": event["source_arm"],
                    "event_id": event["event_id"],
                    "hit_date": event["hit_date"],
                    "hit_time": event["hit_dt"],
                    "vt_symbol": event.get("vt_symbol", ""),
                    "product_vt_symbol": event.get("product_vt_symbol", ""),
                    "direction": event.get("direction", ""),
                    "horizon_trading_days": horizon,
                    "window_rows": int(len(group)),
                    "incremental_rows": int(len(incremental)),
                    "volume_delta_sum": float(pd.to_numeric(group["volume_delta_C_minus_A"], errors="coerce").sum()),
                    "risk_amount_delta_sum": float(pd.to_numeric(group["risk_amount_delta_C_minus_A"], errors="coerce").sum()),
                    "realized_pnl_delta_sum": float(pd.to_numeric(group["realized_pnl_delta_C_minus_A"], errors="coerce").sum()),
                    "incremental_risk_delta_sum": float(pd.to_numeric(incremental["risk_amount_delta_C_minus_A"], errors="coerce").sum()),
                    "incremental_pnl_delta_sum": float(pd.to_numeric(incremental["realized_pnl_delta_C_minus_A"], errors="coerce").sum()),
                }
            )
    return pd.DataFrame(rows)


def _event_window_summary(event_windows: pd.DataFrame) -> pd.DataFrame:
    if event_windows.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for (source, horizon), group in event_windows.groupby(["source_arm", "horizon_trading_days"], sort=False):
        rows.append(
            {
                "source_arm": source,
                "horizon_trading_days": int(horizon),
                "events": int(len(group)),
                "events_with_incremental_rows": int(pd.to_numeric(group["incremental_rows"], errors="coerce").gt(0).sum()),
                "median_incremental_pnl": float(pd.to_numeric(group["incremental_pnl_delta_sum"], errors="coerce").median()),
                "sum_incremental_pnl_overlap_allowed": float(pd.to_numeric(group["incremental_pnl_delta_sum"], errors="coerce").sum()),
                "median_net_pnl": float(pd.to_numeric(group["realized_pnl_delta_sum"], errors="coerce").median()),
                "sum_net_pnl_overlap_allowed": float(pd.to_numeric(group["realized_pnl_delta_sum"], errors="coerce").sum()),
            }
        )
    return pd.DataFrame(rows)


def _bucket_stats(nearest: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if nearest.empty:
        return pd.DataFrame(), pd.DataFrame()
    max_h = nearest[pd.to_numeric(nearest["trading_days_after_stop"], errors="coerce").le(MAX_HORIZON)].copy()
    exposure_rows: list[dict[str, Any]] = []
    for (source, exposure), group in max_h.groupby(["source_arm", "exposure_type"], dropna=False):
        exposure_rows.append(
            {
                "source_arm": source,
                "exposure_type": exposure,
                "rows": int(len(group)),
                "volume_delta_sum": float(group["volume_delta_C_minus_A"].sum()),
                "risk_delta_sum": float(group["risk_amount_delta_C_minus_A"].sum()),
                "pnl_delta_sum": float(group["realized_pnl_delta_C_minus_A"].sum()),
                "positive_rows": int(group["realized_pnl_delta_C_minus_A"].gt(0).sum()),
                "negative_rows": int(group["realized_pnl_delta_C_minus_A"].lt(0).sum()),
            }
        )
    product_rows: list[dict[str, Any]] = []
    incremental = max_h[max_h["incremental_c_exposure"].eq(1)].copy()
    for (source, product, direction), group in incremental.groupby(["source_arm", "product", "direction"], dropna=False):
        if len(group) < 2:
            continue
        product_rows.append(
            {
                "source_arm": source,
                "product": product,
                "direction": direction,
                "rows": int(len(group)),
                "volume_delta_sum": float(group["volume_delta_C_minus_A"].sum()),
                "risk_delta_sum": float(group["risk_amount_delta_C_minus_A"].sum()),
                "pnl_delta_sum": float(group["realized_pnl_delta_C_minus_A"].sum()),
                "same_product_stop_rows": int(group["same_product_as_nearest_stop"].sum()),
            }
        )
    exposure = pd.DataFrame(exposure_rows).sort_values(["source_arm", "pnl_delta_sum"], ascending=[True, True])
    product = pd.DataFrame(product_rows)
    if not product.empty:
        product.sort_values(["source_arm", "pnl_delta_sum"], ascending=[True, True], inplace=True)
    return exposure, product


def _plot_chart(nearest_summary: pd.DataFrame, exposure_bucket: pd.DataFrame) -> None:
    if nearest_summary.empty:
        return
    fig, axes = plt.subplots(1, 3, figsize=(18, 5), constrained_layout=True)
    for source, group in nearest_summary.groupby("source_arm", sort=False):
        axes[0].plot(group["horizon_trading_days"], group["incremental_pnl_delta_sum"], marker="o", label=source)
        axes[1].plot(group["horizon_trading_days"], group["incremental_risk_delta_sum"], marker="o", label=source)
    axes[0].axhline(0, color="#111827", linewidth=0.8)
    axes[0].set_title("Nearest-stop incremental C exposure PnL")
    axes[0].set_xlabel("trading days after stop")
    axes[0].grid(True, alpha=0.2)
    axes[1].axhline(0, color="#111827", linewidth=0.8)
    axes[1].set_title("Nearest-stop incremental C exposure risk")
    axes[1].set_xlabel("trading days after stop")
    axes[1].grid(True, alpha=0.2)
    axes[0].legend()
    if not exposure_bucket.empty:
        pivot = exposure_bucket.pivot_table(
            index="exposure_type",
            columns="source_arm",
            values="pnl_delta_sum",
            aggfunc="sum",
        ).fillna(0.0)
        pivot.plot(kind="bar", ax=axes[2], color=["#2563eb", "#7c3aed"])
        axes[2].axhline(0, color="#111827", linewidth=0.8)
        axes[2].set_title("10-day nearest attribution by exposure type")
        axes[2].grid(True, axis="y", alpha=0.2)
    fig.suptitle("Stage836 stop-release reuse forensic diagnostic", fontsize=13)
    fig.savefig(CHART_PATH, dpi=150)
    plt.close(fig)


def _plot_atlas(nearest: pd.DataFrame) -> tuple[list[Path], pd.DataFrame]:
    if nearest.empty:
        return [], pd.DataFrame()
    incremental = nearest[nearest["incremental_c_exposure"].eq(1)].copy()
    if incremental.empty:
        return [], pd.DataFrame()
    incremental["abs_negative_rank"] = pd.to_numeric(incremental["realized_pnl_delta_C_minus_A"], errors="coerce")
    data = incremental.sort_values(["abs_negative_rank", "source_arm"], ascending=[True, True]).head(PER_PAGE * MAX_ATLAS_PAGES)
    vt_symbols = set(data["vt_symbol"].astype(str).dropna().unique())
    minute_bars = s825._load_minute_bars(vt_symbols)
    minute_by_symbol = s825._minute_groups(minute_bars)
    pages = int(math.ceil(len(data) / PER_PAGE)) if len(data) else 0
    paths: list[Path] = []
    manifest_rows: list[dict[str, Any]] = []
    for page in range(1, pages + 1):
        part = data.iloc[(page - 1) * PER_PAGE : page * PER_PAGE].copy()
        fig, axes = plt.subplots(len(part), 1, figsize=(18, max(4.0, 3.2 * len(part))), constrained_layout=True)
        if len(part) == 1:
            axes = [axes]
        for ax, (_, row) in zip(axes, part.iterrows(), strict=False):
            vt_symbol = str(row["vt_symbol"])
            entry_date = pd.Timestamp(row["entry_date"]).normalize()
            direction = str(row["direction"])
            bars = minute_by_symbol.get(vt_symbol, pd.DataFrame())
            entry_day = bars[bars["bar_date"].eq(entry_date)].copy().head(260).reset_index(drop=True)
            if entry_day.empty:
                ax.axis("off")
                ax.text(0.5, 0.5, f"missing minutes {vt_symbol} {entry_date:%Y-%m-%d}", ha="center", va="center")
            else:
                s825._plot_candles(ax, entry_day)
                entry_price = _safe_float(row.get("C_entry_price"), _safe_float(row.get("A_entry_price")))
                stop_distance = _safe_float(row.get("C_stop_distance"), _safe_float(row.get("A_stop_distance")))
                exit_price = _safe_float(row.get("C_exit_price"), _safe_float(row.get("A_exit_price")))
                sign = 1.0 if direction == "long" else -1.0
                stop_price = entry_price - sign * stop_distance if np.isfinite(stop_distance) else np.nan
                if np.isfinite(entry_price):
                    ax.axhline(entry_price, color="#2563eb", linewidth=0.9, alpha=0.9)
                if np.isfinite(stop_price):
                    ax.axhline(stop_price, color="#dc2626", linewidth=0.9, alpha=0.9)
                if np.isfinite(exit_price):
                    ax.axhline(exit_price, color="#7c3aed", linewidth=0.8, alpha=0.7)
                ticks = np.linspace(0, len(entry_day) - 1, num=min(7, len(entry_day)), dtype=int)
                ax.set_xticks(ticks)
                ax.set_xticklabels([pd.Timestamp(entry_day.loc[pos, "bar_datetime"]).strftime("%H:%M") for pos in ticks], fontsize=7)
                ax.tick_params(axis="y", labelsize=7)
                ax.grid(True, alpha=0.18, linewidth=0.5)
            ax.set_title(
                (
                    f"{row['source_arm']} {row['exposure_type']} {vt_symbol} {direction} {entry_date:%Y-%m-%d} "
                    f"after_stop={int(row['trading_days_after_stop'])}d "
                    f"pnl_delta={row['realized_pnl_delta_C_minus_A']:,.0f} "
                    f"risk_delta={row['risk_amount_delta_C_minus_A']:,.0f} "
                    f"nearest={row.get('nearest_stop_product', '')} {row.get('nearest_stop_direction', '')} "
                    f"{pd.Timestamp(row['nearest_stop_hit_date']).date()}"
                ),
                fontsize=8.5,
                loc="left",
            )
            manifest_rows.append(
                {
                    "page": page,
                    "source_arm": row["source_arm"],
                    "open_key": row["open_key"],
                    "vt_symbol": vt_symbol,
                    "entry_date": entry_date.strftime("%Y-%m-%d"),
                    "exposure_type": row["exposure_type"],
                    "pnl_delta": _safe_float(row.get("realized_pnl_delta_C_minus_A")),
                    "risk_delta": _safe_float(row.get("risk_amount_delta_C_minus_A")),
                    "trading_days_after_stop": int(row["trading_days_after_stop"]),
                    "nearest_stop_hit_date": pd.Timestamp(row["nearest_stop_hit_date"]).strftime("%Y-%m-%d"),
                    "nearest_stop_product": row.get("nearest_stop_product", ""),
                }
            )
        fig.suptitle(
            "Stage836 worst incremental C exposure atlas (blue=entry, red=initial stop, purple=exit)",
            fontsize=13,
        )
        path = Path(str(ATLAS_TEMPLATE).format(page=page))
        fig.savefig(path, dpi=150)
        plt.close(fig)
        paths.append(path)
    return paths, pd.DataFrame(manifest_rows)


def _write_report(
    nearest_summary: pd.DataFrame,
    event_window_summary: pd.DataFrame,
    exposure_bucket: pd.DataFrame,
    product_bucket: pd.DataFrame,
    chart_paths: list[Path],
) -> None:
    lines = [
        "# Stage836 止损后释放资金再使用归因",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 源候选：`{stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION}`",
        f"- 区间：`{START.date()}` 到 `{END.date()}`",
        "- 阶段性质：只读归因；不改正式策略、不改候选配置、不连接 CTP、不调用下单。",
        "",
        "## 外部调研判断",
        "",
        "- Stop-loss 必须和 re-entry / 再暴露规则一起评估；孤立止损容易误判。",
        "- Investopedia 对 stop-loss 的 re-entry risk 描述与本阶段问题一致：止损后若重新追入，可能形成反复止损和更差价格。",
        "- Klement 2013 的 stop-loss/re-entry 论文摘要也强调，止损价值只有与再入场规则共同评估才有意义。",
        "- 本阶段因此不扫止损倍数，只看 C2/C4 止损后 1/3/5/10 个交易日内，C 相对 A 的新增/放大仓位是否贡献为正。",
        "",
        "## Nearest Stop Summary",
        "",
        _md_table(nearest_summary, max_rows=30),
        "",
        "## Event Window Summary",
        "",
        _md_table(event_window_summary, max_rows=30),
        "",
        "## Exposure Bucket",
        "",
        _md_table(exposure_bucket, max_rows=40),
        "",
        "## Product Bucket",
        "",
        _md_table(product_bucket.head(80), max_rows=80),
        "",
        "## Charts",
        "",
        f"- reuse chart：`{CHART_PATH}`",
        *[f"- atlas：`{path}`" for path in chart_paths],
        "",
        "## Judgment",
        "",
        "- nearest-stop 口径避免同一个增量开仓被多个止损事件重复计数，作为主要判断口径。",
        "- event-window 口径允许重叠，只用于判断止损事件后的局部环境是否普遍危险。",
        "- 若 10 日 incremental C exposure PnL 为负，应优先研究低自由度冷却桶；若为正，则不要用冷却桶压制全部再使用。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    calendar = _trading_calendar()
    a_lots = _prepare_closed(STAGE827_CLOSED_PATH, BASE_ARM)
    c2_lots = _prepare_closed(STAGE827_CLOSED_PATH, C2_ARM)
    c4_lots = _prepare_closed(STAGE830_CLOSED_PATH, C4_ARM)
    c2_events = _load_events(STAGE827_EVENTS_PATH, "C2_engine")
    c4_events = _load_events(STAGE830_EVENTS_PATH, "C4_broker10_cap")

    c2_delta = _pair_open_delta(a_lots, c2_lots, "C2_engine")
    c4_delta = _pair_open_delta(a_lots, c4_lots, "C4_broker10_cap")
    c2_nearest = _nearest_stop_attribution(c2_delta, c2_events, calendar)
    c4_nearest = _nearest_stop_attribution(c4_delta, c4_events, calendar)
    nearest = pd.concat([c2_nearest, c4_nearest], ignore_index=True, sort=False)
    nearest_summary = _nearest_summary(nearest)

    c2_event_windows = _event_window_attribution(c2_delta, c2_events, calendar)
    c4_event_windows = _event_window_attribution(c4_delta, c4_events, calendar)
    event_windows = pd.concat([c2_event_windows, c4_event_windows], ignore_index=True, sort=False)
    event_window_summary = _event_window_summary(event_windows)

    exposure_bucket, product_bucket = _bucket_stats(nearest)
    _plot_chart(nearest_summary, exposure_bucket)
    chart_paths, atlas_manifest = _plot_atlas(nearest)
    _write_report(nearest_summary, event_window_summary, exposure_bucket, product_bucket, chart_paths)

    nearest.to_csv(NEAREST_PATH, index=False, encoding="utf-8-sig")
    nearest_summary.to_csv(NEAREST_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    event_windows.to_csv(EVENT_WINDOW_PATH, index=False, encoding="utf-8-sig")
    event_window_summary.to_csv(EVENT_WINDOW_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    exposure_bucket.to_csv(EXPOSURE_BUCKET_PATH, index=False, encoding="utf-8-sig")
    product_bucket.to_csv(PRODUCT_BUCKET_PATH, index=False, encoding="utf-8-sig")
    atlas_manifest.to_csv(ATLAS_MANIFEST_PATH, index=False, encoding="utf-8-sig")

    c2_10 = nearest_summary[
        nearest_summary["source_arm"].eq("C2_engine")
        & nearest_summary["horizon_trading_days"].eq(MAX_HORIZON)
    ]
    c4_10 = nearest_summary[
        nearest_summary["source_arm"].eq("C4_broker10_cap")
        & nearest_summary["horizon_trading_days"].eq(MAX_HORIZON)
    ]
    c2_incremental_pnl = float(c2_10["incremental_pnl_delta_sum"].iloc[0]) if not c2_10.empty else np.nan
    c4_incremental_pnl = float(c4_10["incremental_pnl_delta_sum"].iloc[0]) if not c4_10.empty else np.nan
    decision_label = (
        "stage836_reuse_incremental_positive_no_blanket_cooldown"
        if np.isfinite(c2_incremental_pnl)
        and np.isfinite(c4_incremental_pnl)
        and c2_incremental_pnl > 0
        and c4_incremental_pnl > 0
        else "stage836_reuse_incremental_mixed_consider_tight_cooldown"
    )
    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "source_candidate": stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION,
        "strategy_changed": False,
        "ctp_connected": False,
        "order_api_called": False,
        "decision": decision_label,
        "c2_10d_incremental_pnl_delta": c2_incremental_pnl,
        "c4_10d_incremental_pnl_delta": c4_incremental_pnl,
        "nearest_summary": nearest_summary.to_dict("records"),
        "overfit_reflection": (
            "Stage836 is read-only and uses fixed horizons 1/3/5/10 after frozen stop events. It does not filter by "
            "year, product, or intraday bucket. Converting negative product buckets into rules would overfit."
        ),
        "continue_value": (
            "Continue only if the attribution identifies a broad account-level reuse problem. If incremental reuse is "
            "positive, avoid a blanket cooldown and focus on full-path margin concentration."
        ),
        "outputs": {
            "nearest_attribution": str(NEAREST_PATH),
            "nearest_summary": str(NEAREST_SUMMARY_PATH),
            "event_window_attribution": str(EVENT_WINDOW_PATH),
            "event_window_summary": str(EVENT_WINDOW_SUMMARY_PATH),
            "exposure_bucket": str(EXPOSURE_BUCKET_PATH),
            "product_bucket": str(PRODUCT_BUCKET_PATH),
            "report": str(REPORT_PATH),
            "chart": str(CHART_PATH),
            "atlas_manifest": str(ATLAS_MANIFEST_PATH),
            "atlas_pages": [str(path) for path in chart_paths],
        },
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print("nearest_summary")
    print(nearest_summary.to_string(index=False))
    print("event_window_summary")
    print(event_window_summary.to_string(index=False))
    print("exposure_bucket")
    print(exposure_bucket.to_string(index=False))
    print("product_bucket")
    print(product_bucket.head(40).to_string(index=False))


if __name__ == "__main__":
    main()
