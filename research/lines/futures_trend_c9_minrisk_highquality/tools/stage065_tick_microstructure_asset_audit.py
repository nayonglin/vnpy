from __future__ import annotations

from dataclasses import dataclass
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


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage065"
MODEL_TAG = "stage065_tick_microstructure_asset_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage065_c9_minrisk_tick_microstructure_asset_audit"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage065_tick_microstructure_asset_audit"

STAGE057_DIR = LINE_DIR / "outputs" / "stage057_reentry_gap_tqsdk_backtest_refill"
RAW_TICK_DIR = STAGE057_DIR / "raw_tick"
STAGE058_EVENTS_IN = (
    LINE_DIR
    / "outputs/stage058_reentry_full_ohlcv_integration_audit/"
    "qmt_roll_stage058_c9_minrisk_reentry_full_ohlcv_integration_audit_integrated_events_"
    "stage058_reentry_full_ohlcv_integration_audit_v1.csv"
)
OFFICIAL_CURVE_IN = (
    LINE_DIR
    / "outputs/stage046_entry_day_confirmed_breakeven_true_engine/"
    "qmt_roll_stage046_c9_minrisk_entry_day_confirmed_breakeven_true_engine_curve_"
    "stage046_entry_day_confirmed_breakeven_true_engine_v1.csv"
)

SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
EVENT_FEATURES_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_microstructure_features_{MODEL_TAG}.csv"
CORR_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_feature_correlation_summary_{MODEL_TAG}.csv"
COVERAGE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_coverage_summary_{MODEL_TAG}.csv"
DOWNLOAD_PLAN_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_tick_expansion_download_plan_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_tick_coverage_chart_{MODEL_TAG}.png"
SCATTER_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_microstructure_scatter_{MODEL_TAG}.png"
HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_coverage_product_year_heatmap_{MODEL_TAG}.png"
ATLAS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_microstructure_atlas_{MODEL_TAG}.png"

OFFICIAL_LIVE_VERSION = "official_live_stage847_c9_15w_stage819_05r_stop_retry_once"
OFFICIAL_LIVE_ALIAS = "Stage847-C9-15w"


@dataclass(frozen=True)
class TickFileRef:
    event_key: str
    path: Path


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        result = float(value)
        return None if math.isnan(result) or math.isinf(result) else result
    if isinstance(value, (pd.Timestamp, datetime)):
        return pd.Timestamp(value).strftime("%Y-%m-%d %H:%M:%S")
    return value


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _to_timestamp(value: Any) -> pd.Timestamp:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return pd.NaT
    ts = pd.Timestamp(ts)
    if ts.tzinfo is not None:
        ts = ts.tz_localize(None)
    return ts


def _safe_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan)


def _normalize_product(vt_symbol: str) -> str:
    code, exchange = vt_symbol.split(".", 1)
    prefix = "".join(ch for ch in code if not ch.isdigit()).rstrip("_")
    return f"{prefix}.{exchange}"


def _discover_tick_files() -> dict[str, TickFileRef]:
    result: dict[str, TickFileRef] = {}
    if not RAW_TICK_DIR.exists():
        return result
    for path in sorted(RAW_TICK_DIR.rglob("*_tick_backtest.csv")):
        name = path.name
        if "BACKTESTING_" not in name:
            continue
        suffix = name.split("BACKTESTING_", 1)[1].split("_tick_backtest.csv", 1)[0]
        event_key = f"BACKTESTING.{suffix}"
        result[event_key] = TickFileRef(event_key=event_key, path=path)
    return result


def _load_events() -> pd.DataFrame:
    events = _read_csv(STAGE058_EVENTS_IN)
    events["event_key"] = events["event_key"].astype(str)
    events["reentry_time"] = pd.to_datetime(events["reentry_time"], errors="coerce")
    events["reentry_year"] = pd.to_numeric(events["reentry_year"], errors="coerce").astype("Int64")
    events["reentry_lot_pnl"] = pd.to_numeric(events["reentry_lot_pnl"], errors="coerce")
    events["risk_price"] = pd.to_numeric(events["risk_price"], errors="coerce")
    events["direction_sign"] = pd.to_numeric(events["direction_sign"], errors="coerce")
    events["normalized_product"] = events["vt_symbol"].astype(str).map(_normalize_product)
    return events.sort_values(["reentry_time", "event_key"]).reset_index(drop=True)


def _target_window(reentry_time: pd.Timestamp) -> tuple[pd.Timestamp, pd.Timestamp]:
    start = reentry_time.floor("min")
    return start, start + pd.Timedelta(minutes=1)


def _extract_features(row: pd.Series, tick_ref: TickFileRef | None) -> dict[str, Any]:
    base: dict[str, Any] = {
        "event_key": row["event_key"],
        "trade_id": row.get("trade_id", ""),
        "vt_symbol": row["vt_symbol"],
        "normalized_product": row["normalized_product"],
        "direction": row["direction"],
        "direction_sign": row["direction_sign"],
        "reentry_year": row["reentry_year"],
        "reentry_time": row["reentry_time"],
        "quality_bucket": row.get("quality_bucket", ""),
        "reentry_lot_pnl": row["reentry_lot_pnl"],
        "risk_price": row["risk_price"],
        "final_source": row.get("final_source", ""),
        "tick_file_exists": bool(tick_ref),
        "tick_file_path": str(tick_ref.path) if tick_ref else "",
        "tick_rows_total": 0,
        "tick_rows_target_minute": 0,
        "valid_top_book_rows": 0,
        "microstructure_ready": False,
        "median_spread": np.nan,
        "median_spread_r": np.nan,
        "p90_spread_r": np.nan,
        "median_depth1": np.nan,
        "median_depth1_log": np.nan,
        "median_book_imbalance": np.nan,
        "median_directional_book_imbalance": np.nan,
        "volume_delta_target": np.nan,
        "amount_delta_target": np.nan,
        "open_interest_delta_target": np.nan,
        "directional_mid_move_r": np.nan,
        "directional_last_move_r": np.nan,
        "median_mid_price": np.nan,
        "first_mid_price": np.nan,
        "last_mid_price": np.nan,
    }
    if not tick_ref:
        return base
    try:
        ticks = pd.read_csv(tick_ref.path, encoding="utf-8-sig")
    except Exception as exc:
        base["tick_read_error"] = f"{type(exc).__name__}:{exc}"
        return base
    if ticks.empty or "tick_datetime" not in ticks.columns:
        return base

    ticks["tick_datetime"] = pd.to_datetime(ticks["tick_datetime"], errors="coerce")
    ticks = ticks.dropna(subset=["tick_datetime"]).sort_values("tick_datetime")
    base["tick_rows_total"] = int(len(ticks))
    start, end = _target_window(row["reentry_time"])
    target = ticks[(ticks["tick_datetime"] >= start) & (ticks["tick_datetime"] < end)].copy()
    base["tick_rows_target_minute"] = int(len(target))
    if target.empty:
        return base

    for col in [
        "last_price",
        "ask_price1",
        "ask_volume1",
        "bid_price1",
        "bid_volume1",
        "volume",
        "amount",
        "open_interest",
    ]:
        if col in target.columns:
            target[col] = _safe_num(target[col])
        else:
            target[col] = np.nan

    valid = target[
        (target["ask_price1"] > 0)
        & (target["bid_price1"] > 0)
        & (target["ask_price1"] < 1e100)
        & (target["bid_price1"] < 1e100)
        & (target["ask_price1"] >= target["bid_price1"])
    ].copy()
    base["valid_top_book_rows"] = int(len(valid))
    if valid.empty:
        return base

    valid["spread"] = valid["ask_price1"] - valid["bid_price1"]
    valid["mid_price"] = (valid["ask_price1"] + valid["bid_price1"]) / 2.0
    valid["depth1"] = valid["ask_volume1"].fillna(0) + valid["bid_volume1"].fillna(0)
    depth_denom = valid["depth1"].replace(0, np.nan)
    valid["book_imbalance"] = (valid["bid_volume1"].fillna(0) - valid["ask_volume1"].fillna(0)) / depth_denom
    risk_price = float(row["risk_price"]) if pd.notna(row["risk_price"]) and float(row["risk_price"]) > 0 else np.nan
    direction_sign = float(row["direction_sign"]) if pd.notna(row["direction_sign"]) else np.nan
    if pd.notna(risk_price):
        valid["spread_r"] = valid["spread"] / risk_price
    else:
        valid["spread_r"] = np.nan

    base["microstructure_ready"] = True
    base["median_spread"] = float(valid["spread"].median())
    base["median_spread_r"] = float(valid["spread_r"].median()) if valid["spread_r"].notna().any() else np.nan
    base["p90_spread_r"] = float(valid["spread_r"].quantile(0.90)) if valid["spread_r"].notna().any() else np.nan
    base["median_depth1"] = float(valid["depth1"].median())
    base["median_depth1_log"] = float(np.log1p(valid["depth1"].median()))
    base["median_book_imbalance"] = float(valid["book_imbalance"].median())
    if pd.notna(direction_sign):
        base["median_directional_book_imbalance"] = float(direction_sign * valid["book_imbalance"].median())
    base["median_mid_price"] = float(valid["mid_price"].median())
    base["first_mid_price"] = float(valid["mid_price"].iloc[0])
    base["last_mid_price"] = float(valid["mid_price"].iloc[-1])
    if pd.notna(direction_sign) and pd.notna(risk_price):
        base["directional_mid_move_r"] = float(direction_sign * (valid["mid_price"].iloc[-1] - valid["mid_price"].iloc[0]) / risk_price)
        last_valid = target.dropna(subset=["last_price"])
        if len(last_valid) >= 2:
            base["directional_last_move_r"] = float(
                direction_sign * (last_valid["last_price"].iloc[-1] - last_valid["last_price"].iloc[0]) / risk_price
            )

    for source_col, out_col in [
        ("volume", "volume_delta_target"),
        ("amount", "amount_delta_target"),
        ("open_interest", "open_interest_delta_target"),
    ]:
        values = target[source_col].dropna()
        if len(values) >= 2:
            base[out_col] = float(values.iloc[-1] - values.iloc[0])
    return base


def _build_features(events: pd.DataFrame) -> pd.DataFrame:
    tick_files = _discover_tick_files()
    rows = [_extract_features(row, tick_files.get(str(row["event_key"]))) for _, row in events.iterrows()]
    features = pd.DataFrame(rows)
    features["microstructure_ready"] = features["microstructure_ready"].astype(bool)
    features["tick_file_exists"] = features["tick_file_exists"].astype(bool)
    return features


def _feature_correlations(features: pd.DataFrame) -> pd.DataFrame:
    ready = features[features["microstructure_ready"]].copy()
    cols = [
        "median_spread_r",
        "p90_spread_r",
        "median_depth1_log",
        "median_book_imbalance",
        "median_directional_book_imbalance",
        "volume_delta_target",
        "open_interest_delta_target",
        "directional_mid_move_r",
        "directional_last_move_r",
    ]
    rows: list[dict[str, Any]] = []
    for col in cols:
        sample = ready[[col, "reentry_lot_pnl"]].dropna()
        rows.append(
            {
                "feature": col,
                "n": int(len(sample)),
                "unique_count": int(sample[col].nunique()) if not sample.empty else 0,
                "spearman_to_reentry_pnl": sample[col].corr(sample["reentry_lot_pnl"], method="spearman")
                if len(sample) >= 3 and sample[col].nunique() > 1
                else np.nan,
                "pearson_to_reentry_pnl": sample[col].corr(sample["reentry_lot_pnl"], method="pearson")
                if len(sample) >= 3 and sample[col].nunique() > 1
                else np.nan,
            }
        )
    corr = pd.DataFrame(rows)
    corr["abs_spearman_to_reentry_pnl"] = corr["spearman_to_reentry_pnl"].abs()
    return corr.sort_values("abs_spearman_to_reentry_pnl", ascending=False, na_position="last")


def _coverage_summary(features: pd.DataFrame) -> pd.DataFrame:
    rows = []
    groups = [
        ("all_reentry_events", features),
        ("microstructure_ready", features[features["microstructure_ready"]]),
        ("microstructure_missing", features[~features["microstructure_ready"]]),
    ]
    for name, data in groups:
        rows.append(
            {
                "bucket": name,
                "event_count": int(len(data)),
                "product_count": int(data["normalized_product"].nunique()) if not data.empty else 0,
                "year_count": int(data["reentry_year"].nunique()) if not data.empty else 0,
                "net_reentry_lot_pnl": float(data["reentry_lot_pnl"].sum()) if not data.empty else 0.0,
                "positive_pnl": float(data.loc[data["reentry_lot_pnl"] > 0, "reentry_lot_pnl"].sum()) if not data.empty else 0.0,
                "negative_pnl_abs": float(-data.loc[data["reentry_lot_pnl"] < 0, "reentry_lot_pnl"].sum()) if not data.empty else 0.0,
                "median_spread_r": float(data["median_spread_r"].median()) if "median_spread_r" in data and data["median_spread_r"].notna().any() else np.nan,
                "median_directional_book_imbalance": float(data["median_directional_book_imbalance"].median())
                if "median_directional_book_imbalance" in data and data["median_directional_book_imbalance"].notna().any()
                else np.nan,
            }
        )
    return pd.DataFrame(rows)


def _download_plan(features: pd.DataFrame) -> pd.DataFrame:
    missing = features[~features["microstructure_ready"]].copy()
    if missing.empty:
        return missing
    missing["download_start_dt"] = pd.to_datetime(missing["reentry_time"]) - pd.Timedelta(minutes=3)
    missing["download_end_dt"] = pd.to_datetime(missing["reentry_time"]) + pd.Timedelta(minutes=3)
    missing["dur_sec"] = 0
    missing["reason"] = "expand_tick_microstructure_coverage_for_reentry_events"
    return missing[
        [
            "event_key",
            "vt_symbol",
            "normalized_product",
            "direction",
            "reentry_time",
            "reentry_lot_pnl",
            "download_start_dt",
            "download_end_dt",
            "dur_sec",
            "reason",
        ]
    ]


def _official_curve() -> pd.DataFrame:
    curve = _read_csv(OFFICIAL_CURVE_IN)
    arm_cols = [col for col in ["arm", "arm_key", "variant"] if col in curve.columns]
    mask = pd.Series(False, index=curve.index)
    for col in arm_cols:
        values = curve[col].astype(str)
        mask = mask | values.str.contains("A_official", na=False)
        mask = mask | values.str.contains("official_live_stage847_c9_15w", na=False)
    official = curve.loc[mask].copy()
    official["date"] = pd.to_datetime(official["date"], errors="coerce")
    return official.dropna(subset=["date"]).sort_values("date")


def _plot_path(features: pd.DataFrame) -> None:
    official = _official_curve()
    events = features.copy()
    events["reentry_time"] = pd.to_datetime(events["reentry_time"], errors="coerce")
    events = events.dropna(subset=["reentry_time"]).sort_values("reentry_time")
    events["cum_ready_pnl"] = events["reentry_lot_pnl"].where(events["microstructure_ready"], 0).cumsum()
    events["cum_missing_pnl"] = events["reentry_lot_pnl"].where(~events["microstructure_ready"], 0).cumsum()

    fig, axes = plt.subplots(3, 1, figsize=(14, 11), sharex=False)
    axes[0].plot(official["date"], official["account_equity"] / 1_000_000, color="#0072b2", linewidth=2.0)
    ready = events[events["microstructure_ready"]]
    missing = events[~events["microstructure_ready"]]
    axes[0].scatter(ready["reentry_time"], np.interp(ready["reentry_time"].astype("int64"), official["date"].astype("int64"), official["account_equity"] / 1_000_000), s=45, color="#009e73", label="tick microstructure ready", alpha=0.85)
    axes[0].scatter(missing["reentry_time"], np.interp(missing["reentry_time"].astype("int64"), official["date"].astype("int64"), official["account_equity"] / 1_000_000), s=32, color="#d55e00", label="tick missing", alpha=0.65)
    axes[0].set_title("Official equity path with C9 reentry tick microstructure coverage")
    axes[0].set_ylabel("Equity (million CNY)")
    axes[0].grid(alpha=0.25)
    axes[0].legend(loc="upper left", fontsize=8)

    axes[1].plot(events["reentry_time"], events["cum_ready_pnl"] / 10_000, color="#009e73", linewidth=2.0, label="ready cumulative reentry PnL")
    axes[1].plot(events["reentry_time"], events["cum_missing_pnl"] / 10_000, color="#d55e00", linewidth=2.0, label="missing cumulative reentry PnL")
    axes[1].axhline(0, color="black", linewidth=0.8)
    axes[1].set_title("Coverage contribution: ready sample is not enough to define a rule")
    axes[1].set_ylabel("Cumulative PnL (10k CNY)")
    axes[1].grid(alpha=0.25)
    axes[1].legend(loc="upper left", fontsize=8)

    if not ready.empty:
        axes[2].plot(ready["reentry_time"], ready["median_spread_r"], marker="o", color="#56b4e9", linewidth=1.2, label="median spread / risk")
        axes[2].plot(ready["reentry_time"], ready["median_directional_book_imbalance"], marker="o", color="#cc79a7", linewidth=1.2, label="directional book imbalance")
    axes[2].axhline(0, color="black", linewidth=0.8)
    axes[2].set_title("Point-in-time microstructure diagnostics")
    axes[2].set_ylabel("Feature value")
    axes[2].grid(alpha=0.25)
    axes[2].legend(loc="upper left", fontsize=8)

    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=180)
    plt.close(fig)


def _plot_scatter(features: pd.DataFrame) -> None:
    ready = features[features["microstructure_ready"]].copy()
    fig, axes = plt.subplots(2, 2, figsize=(13, 9))
    specs = [
        ("median_spread_r", "Median spread / risk"),
        ("median_directional_book_imbalance", "Directional book imbalance"),
        ("median_depth1_log", "Log top-book depth"),
        ("directional_mid_move_r", "Directional mid move / risk"),
    ]
    for ax, (col, title) in zip(axes.reshape(-1), specs):
        sample = ready[[col, "reentry_lot_pnl", "reentry_year", "normalized_product"]].dropna()
        if sample.empty:
            ax.text(0.5, 0.5, "no ready sample", ha="center", va="center")
        else:
            scatter = ax.scatter(
                sample[col],
                sample["reentry_lot_pnl"] / 10_000,
                c=sample["reentry_year"].astype(int),
                cmap="viridis",
                s=70,
                alpha=0.85,
                edgecolor="black",
                linewidth=0.35,
            )
            fig.colorbar(scatter, ax=ax, fraction=0.046, pad=0.04, label="year")
            for _, row in sample.nlargest(2, "reentry_lot_pnl").iterrows():
                ax.annotate(str(row["normalized_product"]), (row[col], row["reentry_lot_pnl"] / 10_000), fontsize=8)
            for _, row in sample.nsmallest(2, "reentry_lot_pnl").iterrows():
                ax.annotate(str(row["normalized_product"]), (row[col], row["reentry_lot_pnl"] / 10_000), fontsize=8)
        ax.axhline(0, color="black", linewidth=0.8)
        ax.set_title(title)
        ax.set_ylabel("Reentry lot PnL (10k CNY)")
        ax.grid(alpha=0.25)
    fig.suptitle("Stage065 tick microstructure features vs reentry PnL", fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig(SCATTER_OUT, dpi=180)
    plt.close(fig)


def _plot_heatmap(features: pd.DataFrame) -> None:
    table = (
        features.pivot_table(
            index="normalized_product",
            columns="reentry_year",
            values="microstructure_ready",
            aggfunc=lambda x: int(np.sum(x)),
            fill_value=0,
        )
        .sort_index()
    )
    fig, ax = plt.subplots(figsize=(12, max(5.5, 0.35 * len(table))))
    im = ax.imshow(table.to_numpy(), cmap="YlGnBu", aspect="auto")
    ax.set_xticks(np.arange(len(table.columns)))
    ax.set_xticklabels([str(int(col)) for col in table.columns], rotation=30, ha="right")
    ax.set_yticks(np.arange(len(table.index)))
    ax.set_yticklabels(table.index)
    for i in range(table.shape[0]):
        for j in range(table.shape[1]):
            value = int(table.iat[i, j])
            ax.text(j, i, str(value), ha="center", va="center", fontsize=8, color="black")
    ax.set_title("Stage065 microstructure-ready reentry count by product/year")
    fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    fig.tight_layout()
    fig.savefig(HEATMAP_OUT, dpi=180)
    plt.close(fig)


def _load_target_ticks(path: Path, event_time: pd.Timestamp) -> pd.DataFrame:
    ticks = pd.read_csv(path, encoding="utf-8-sig")
    ticks["tick_datetime"] = pd.to_datetime(ticks["tick_datetime"], errors="coerce")
    ticks = ticks.dropna(subset=["tick_datetime"]).sort_values("tick_datetime")
    start = event_time - pd.Timedelta(minutes=1)
    end = event_time + pd.Timedelta(minutes=2)
    for col in ["last_price", "ask_price1", "ask_volume1", "bid_price1", "bid_volume1", "volume", "open_interest"]:
        if col in ticks.columns:
            ticks[col] = _safe_num(ticks[col])
        else:
            ticks[col] = np.nan
    ticks = ticks[(ticks["tick_datetime"] >= start) & (ticks["tick_datetime"] < end)].copy()
    ticks = ticks[
        (ticks["ask_price1"] > 0)
        & (ticks["bid_price1"] > 0)
        & (ticks["ask_price1"] < 1e100)
        & (ticks["bid_price1"] < 1e100)
        & (ticks["ask_price1"] >= ticks["bid_price1"])
    ].copy()
    if ticks.empty:
        return ticks
    ticks["mid_price"] = (ticks["ask_price1"] + ticks["bid_price1"]) / 2
    ticks["depth1"] = ticks["ask_volume1"].fillna(0) + ticks["bid_volume1"].fillna(0)
    denom = ticks["depth1"].replace(0, np.nan)
    ticks["imbalance"] = (ticks["bid_volume1"].fillna(0) - ticks["ask_volume1"].fillna(0)) / denom
    return ticks


def _plot_atlas(features: pd.DataFrame) -> None:
    ready = features[features["microstructure_ready"]].copy()
    if ready.empty:
        return
    selected = pd.concat(
        [
            ready.nlargest(2, "reentry_lot_pnl"),
            ready.nsmallest(2, "reentry_lot_pnl"),
            ready.nlargest(1, "median_spread_r"),
            ready.nsmallest(1, "median_directional_book_imbalance"),
        ],
        ignore_index=True,
    ).drop_duplicates("event_key").head(6)

    fig, axes = plt.subplots(len(selected), 2, figsize=(14, max(3.2 * len(selected), 6)))
    if len(selected) == 1:
        axes = np.asarray([axes])
    for row_idx, (_, row) in enumerate(selected.iterrows()):
        event_time = _to_timestamp(row["reentry_time"])
        ticks = _load_target_ticks(Path(row["tick_file_path"]), event_time)
        ax_price, ax_depth = axes[row_idx]
        if ticks.empty:
            ax_price.text(0.5, 0.5, "no valid ticks", ha="center", va="center")
            ax_depth.axis("off")
            continue
        x = ticks["tick_datetime"]
        ax_price.plot(x, ticks["bid_price1"], color="#0072b2", linewidth=1.0, label="bid1")
        ax_price.plot(x, ticks["ask_price1"], color="#d55e00", linewidth=1.0, label="ask1")
        ax_price.plot(x, ticks["last_price"], color="#222222", linewidth=0.9, alpha=0.65, label="last")
        ax_price.axvline(event_time, color="#7a3db8", linestyle="--", linewidth=1.0, label="reentry")
        ax_price.set_title(
            f"{row['event_key']} {row['vt_symbol']} pnl={row['reentry_lot_pnl'] / 10000:.1f}w spreadR={row['median_spread_r']:.3f}"
        )
        ax_price.grid(alpha=0.25)
        ax_price.legend(loc="upper left", fontsize=7)

        ax_depth.plot(x, ticks["depth1"], color="#009e73", linewidth=1.0, label="depth1")
        ax_depth_twin = ax_depth.twinx()
        ax_depth_twin.plot(x, ticks["imbalance"], color="#cc79a7", linewidth=1.0, label="imbalance")
        ax_depth.axvline(event_time, color="#7a3db8", linestyle="--", linewidth=1.0)
        ax_depth.set_title("Top-book depth and imbalance")
        ax_depth.grid(alpha=0.25)
    fig.suptitle("Stage065 point-in-time tick microstructure atlas", fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, 0.985])
    fig.savefig(ATLAS_OUT, dpi=170)
    plt.close(fig)


def _write_report(summary: dict[str, Any], coverage: pd.DataFrame, corr: pd.DataFrame) -> None:
    lines = [
        f"# {STAGE} Tick Microstructure Asset Audit",
        "",
        f"- Created: {summary['created_at']}",
        f"- Official baseline: `{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`",
        f"- Decision: `{summary['decision']}`",
        "- This is a data-asset audit only. No trading rule, true engine, A/B test, CTP connection, or order API call was used.",
        "",
        "## External Research Conclusion",
        "",
        "- TqSdk exposes historical/strategy tick fields including bid/ask price and volume levels.",
        "- vn.py TickData and live monitor code already carry bid/ask fields, so a point-in-time microstructure route is technically compatible with the production stack.",
        "- Historical depth data is usually permissioned; local availability must be audited before any signal design.",
        "",
        "## Coverage",
        "",
        coverage.to_markdown(index=False),
        "",
        "## Feature Correlation",
        "",
        corr.to_markdown(index=False),
        "",
        "## Judgment",
        "",
        "- Existing Stage057 tick files prove that historical tick microstructure can be materialized for selected C9 reentry events.",
        "- Coverage is only partial and biased toward events that needed tick fallback, so no trading rule can be inferred from this sample.",
        "- The next valid step is an expansion download/collection plan for all C9 reentry events and then timestamp-ready initial entries, followed by the same fixed feature spec.",
        "",
        "## Outputs",
        "",
        f"- Summary: `{SUMMARY_OUT}`",
        f"- Event features: `{EVENT_FEATURES_OUT}`",
        f"- Coverage summary: `{COVERAGE_OUT}`",
        f"- Feature correlations: `{CORR_OUT}`",
        f"- Download plan: `{DOWNLOAD_PLAN_OUT}`",
        f"- Official path coverage chart: `{PATH_CHART_OUT}`",
        f"- Scatter chart: `{SCATTER_OUT}`",
        f"- Product/year heatmap: `{HEATMAP_OUT}`",
        f"- Microstructure atlas: `{ATLAS_OUT}`",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    events = _load_events()
    features = _build_features(events)
    corr = _feature_correlations(features)
    coverage = _coverage_summary(features)
    plan = _download_plan(features)

    features.to_csv(EVENT_FEATURES_OUT, index=False, encoding="utf-8-sig")
    corr.to_csv(CORR_OUT, index=False, encoding="utf-8-sig")
    coverage.to_csv(COVERAGE_OUT, index=False, encoding="utf-8-sig")
    plan.to_csv(DOWNLOAD_PLAN_OUT, index=False, encoding="utf-8-sig")

    _plot_path(features)
    _plot_scatter(features)
    _plot_heatmap(features)
    _plot_atlas(features)

    ready = features[features["microstructure_ready"]]
    missing = features[~features["microstructure_ready"]]
    max_abs_spearman = corr["abs_spearman_to_reentry_pnl"].max(skipna=True)
    if pd.isna(max_abs_spearman):
        max_abs_spearman = np.nan

    summary = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "created_at": f"{datetime.now():%Y-%m-%d %H:%M:%S}",
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "decision": "stage065_tick_microstructure_partial_data_asset_no_rule",
        "strategy_rule_created": False,
        "true_engine_run": False,
        "ab_triggered": False,
        "input_reentry_event_count": int(len(features)),
        "tick_file_exists_count": int(features["tick_file_exists"].sum()),
        "microstructure_ready_count": int(features["microstructure_ready"].sum()),
        "microstructure_ready_pct": float(features["microstructure_ready"].mean() * 100) if len(features) else 0.0,
        "microstructure_missing_count": int((~features["microstructure_ready"]).sum()),
        "ready_reentry_lot_pnl": float(ready["reentry_lot_pnl"].sum()) if not ready.empty else 0.0,
        "missing_reentry_lot_pnl": float(missing["reentry_lot_pnl"].sum()) if not missing.empty else 0.0,
        "ready_product_count": int(ready["normalized_product"].nunique()) if not ready.empty else 0,
        "ready_year_count": int(ready["reentry_year"].nunique()) if not ready.empty else 0,
        "max_abs_spearman_feature_pnl": float(max_abs_spearman) if pd.notna(max_abs_spearman) else np.nan,
        "download_plan_missing_event_count": int(len(plan)),
        "next_action": "Expand fixed tick microstructure collection to all 54 C9 reentry events; do not create a rule from the current partial fallback-biased sample.",
    }
    pd.DataFrame([summary]).to_csv(SUMMARY_OUT, index=False, encoding="utf-8-sig")
    decision = dict(summary)
    decision["outputs"] = {
        "summary": str(SUMMARY_OUT),
        "event_features": str(EVENT_FEATURES_OUT),
        "coverage_summary": str(COVERAGE_OUT),
        "feature_correlation_summary": str(CORR_OUT),
        "download_plan": str(DOWNLOAD_PLAN_OUT),
        "report": str(REPORT_OUT),
        "official_path_tick_coverage_chart": str(PATH_CHART_OUT),
        "microstructure_scatter": str(SCATTER_OUT),
        "coverage_product_year_heatmap": str(HEATMAP_OUT),
        "microstructure_atlas": str(ATLAS_OUT),
    }
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(summary, coverage, corr)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
