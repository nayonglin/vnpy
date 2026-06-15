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
STAGE = "Stage845"
MODEL_TAG = "stage845_stage844_reuse_cluster_forensics_v1"
OUTPUT_PREFIX = "qmt_roll_stage845_stage844_reuse_cluster_forensics"

START = pd.Timestamp("2018-01-01")
END = pd.Timestamp("2026-05-29")

STAGE844_PREFIX = "qmt_roll_stage844_stage843_c8_reuse_pressure_forensics"
STAGE844_TAG = "stage844_stage843_c8_reuse_pressure_forensics_v1"

REUSE_ATTRIBUTION_PATH = OUTPUT_DIR / f"{STAGE844_PREFIX}_reuse_attribution_{STAGE844_TAG}.csv"
EVENT_WINDOWS_PATH = OUTPUT_DIR / f"{STAGE844_PREFIX}_event_windows_{STAGE844_TAG}.csv"
DAILY_DELTA_PATH = OUTPUT_DIR / f"{STAGE844_PREFIX}_daily_delta_{STAGE844_TAG}.csv"

EVENT_CLUSTER_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_cluster_{MODEL_TAG}.csv"
EVENT_CLUSTER_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_cluster_summary_{MODEL_TAG}.csv"
ROW_PRESSURE_BUCKET_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_row_pressure_bucket_{MODEL_TAG}.csv"
ROW_PRESSURE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_row_pressure_summary_{MODEL_TAG}.csv"
PRESSURE_QUARTILE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_pressure_quartile_{MODEL_TAG}.csv"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
CLUSTER_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cluster_chart_{MODEL_TAG}.png"
ATLAS_MANIFEST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_reuse_entry_atlas_manifest_{MODEL_TAG}.csv"
ATLAS_TEMPLATE = OUTPUT_DIR / f"{OUTPUT_PREFIX}_reuse_entry_atlas_page{{page:03d}}_{MODEL_TAG}.png"

HORIZONS = [1, 3, 5, 10, 20]
MAX_HORIZON = max(HORIZONS)
PER_PAGE = 4
MAX_ATLAS_ROWS = 12


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


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"Missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


def _normal_date(value: Any) -> pd.Timestamp:
    if pd.isna(value):
        return pd.NaT
    text = str(value)
    if len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-":
        ts = pd.to_datetime(text[:10], errors="coerce")
    else:
        ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return pd.NaT
    if getattr(ts, "tzinfo", None) is not None:
        ts = pd.Timestamp(ts).tz_convert("Asia/Shanghai").tz_localize(None)
    return pd.Timestamp(ts).normalize()


def _numeric(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for column in columns:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame


def _prepare_reuse() -> pd.DataFrame:
    reuse = _load_csv(REUSE_ATTRIBUTION_PATH).copy()
    for column in ("entry_date", "exit_date", "nearest_event_hit_date"):
        if column in reuse.columns:
            reuse[column] = reuse[column].map(_normal_date)
    reuse["nearest_event_hit_time"] = pd.to_datetime(reuse.get("nearest_event_hit_time"), errors="coerce")
    numeric_cols = [
        "C8_entry_price",
        "C8_exit_price",
        "C8_stop_distance",
        "C8_volume",
        "C8_risk_amount",
        "C8_realized_pnl",
        "C4_volume",
        "C4_risk_amount",
        "C4_realized_pnl",
        "volume_delta_C8_minus_C4",
        "selected_volume_delta_C8_minus_C4",
        "risk_amount_delta_C8_minus_C4",
        "target_risk_amount_delta_C8_minus_C4",
        "realized_pnl_delta_C8_minus_C4",
        "r_multiple_delta_C8_minus_C4",
        "incremental_c8_exposure",
        "reduced_c8_exposure",
        "trading_days_after_event",
        "same_product_as_nearest_event",
        "same_direction_as_nearest_event",
        "same_product_direction_as_nearest_event",
    ]
    return _numeric(reuse, numeric_cols)


def _prepare_event_windows() -> pd.DataFrame:
    events = _load_csv(EVENT_WINDOWS_PATH).copy()
    for column in ("hit_date",):
        if column in events.columns:
            events[column] = events[column].map(_normal_date)
    events["hit_time"] = pd.to_datetime(events.get("hit_time"), errors="coerce")
    return _numeric(
        events,
        [
            "horizon_trading_days",
            "cum_net_pnl_delta_C8_minus_C4",
            "end_equity_delta_C8_minus_C4",
            "max_broker10_C8",
            "max_broker10_C4",
            "max_broker10_delta_C8_minus_C4",
            "min_drawdown_C8",
            "min_drawdown_C4",
            "min_drawdown_delta_C8_minus_C4",
            "trade_count_delta_sum",
            "slippage_delta_sum",
            "volume",
        ],
    )


def _prepare_daily() -> pd.DataFrame:
    daily = _load_csv(DAILY_DELTA_PATH).copy()
    daily["date"] = daily["date"].map(_normal_date)
    return _numeric(
        daily,
        [
            "td_index",
            "account_equity_C4",
            "account_equity_C8",
            "drawdown_pct_C4",
            "drawdown_pct_C8",
            "drawdown_pct_delta_C8_minus_C4",
            "broker10_margin_to_equity_pct_C4",
            "broker10_margin_to_equity_pct_C8",
            "broker10_margin_to_equity_pct_delta_C8_minus_C4",
            "net_pnl_delta_C8_minus_C4",
        ],
    )


def _share(numerator: float, denominator: float) -> float:
    return float(numerator / denominator * 100.0) if denominator > 0 else 0.0


def _risk_group_share(
    frame: pd.DataFrame,
    group_cols: list[str],
    risk_col: str = "risk_amount_delta_C8_minus_C4",
) -> tuple[str, float, int]:
    if frame.empty:
        return "", 0.0, 0
    data = frame.copy()
    data["_risk"] = pd.to_numeric(data[risk_col], errors="coerce").clip(lower=0.0).fillna(0.0)
    total = float(data["_risk"].sum())
    if total <= 0:
        return "", 0.0, int(data[group_cols].drop_duplicates().shape[0])
    grouped = data.groupby(group_cols, dropna=False)["_risk"].sum().sort_values(ascending=False)
    top_key = grouped.index[0]
    if not isinstance(top_key, tuple):
        top_key = (top_key,)
    label = " ".join(str(item) for item in top_key)
    return label, _share(float(grouped.iloc[0]), total), int(len(grouped))


def _event_cluster(reuse: pd.DataFrame, event_windows: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for event in event_windows.to_dict("records"):
        event_id = str(event["event_id"])
        horizon = int(event["horizon_trading_days"])
        group = reuse[
            reuse["nearest_event_id"].astype(str).eq(event_id)
            & pd.to_numeric(reuse["trading_days_after_event"], errors="coerce").le(horizon)
        ].copy()
        incremental = group[group["incremental_c8_exposure"].eq(1)].copy()
        reduced = group[group["reduced_c8_exposure"].eq(1)].copy()
        incremental["_risk"] = pd.to_numeric(incremental["risk_amount_delta_C8_minus_C4"], errors="coerce").clip(lower=0.0).fillna(0.0)
        risk_total = float(incremental["_risk"].sum()) if not incremental.empty else 0.0
        top_pd_label, top_pd_share, product_direction_count = _risk_group_share(incremental, ["product", "direction"])
        top_dir_label, top_dir_share, direction_count = _risk_group_share(incremental, ["direction"])
        top_product_label, top_product_share, product_count = _risk_group_share(incremental, ["product"])
        same_product_risk = float(
            incremental[incremental["same_product_as_nearest_event"].eq(1)]["_risk"].sum()
        ) if not incremental.empty else 0.0
        same_direction_risk = float(
            incremental[incremental["same_direction_as_nearest_event"].eq(1)]["_risk"].sum()
        ) if not incremental.empty else 0.0
        same_product_direction_risk = float(
            incremental[incremental["same_product_direction_as_nearest_event"].eq(1)]["_risk"].sum()
        ) if not incremental.empty else 0.0
        long_risk = float(incremental[incremental["direction"].astype(str).eq("long")]["_risk"].sum()) if not incremental.empty else 0.0
        short_risk = float(incremental[incremental["direction"].astype(str).eq("short")]["_risk"].sum()) if not incremental.empty else 0.0
        rows.append(
            {
                "event_id": event_id,
                "horizon_trading_days": horizon,
                "event_hit_date": event.get("hit_date"),
                "event_hit_time": event.get("hit_time"),
                "event_vt_symbol": event.get("vt_symbol", ""),
                "event_product": event.get("product_vt_symbol", ""),
                "event_direction": event.get("direction", ""),
                "reuse_rows": int(len(group)),
                "incremental_rows": int(len(incremental)),
                "reduced_rows": int(len(reduced)),
                "incremental_volume_delta_sum": float(pd.to_numeric(incremental["volume_delta_C8_minus_C4"], errors="coerce").sum()) if not incremental.empty else 0.0,
                "incremental_risk_delta_sum": risk_total,
                "incremental_pnl_delta_sum": float(pd.to_numeric(incremental["realized_pnl_delta_C8_minus_C4"], errors="coerce").sum()) if not incremental.empty else 0.0,
                "reduced_risk_delta_sum": float(pd.to_numeric(reduced["risk_amount_delta_C8_minus_C4"], errors="coerce").sum()) if not reduced.empty else 0.0,
                "reduced_pnl_delta_sum": float(pd.to_numeric(reduced["realized_pnl_delta_C8_minus_C4"], errors="coerce").sum()) if not reduced.empty else 0.0,
                "incremental_positive_rows": int(pd.to_numeric(incremental["realized_pnl_delta_C8_minus_C4"], errors="coerce").gt(0).sum()) if not incremental.empty else 0,
                "incremental_negative_rows": int(pd.to_numeric(incremental["realized_pnl_delta_C8_minus_C4"], errors="coerce").lt(0).sum()) if not incremental.empty else 0,
                "top_product_direction": top_pd_label,
                "top_product_direction_share_pct": top_pd_share,
                "top_direction": top_dir_label,
                "top_direction_share_pct": top_dir_share,
                "top_product": top_product_label,
                "top_product_share_pct": top_product_share,
                "product_direction_count": product_direction_count,
                "product_count": product_count,
                "direction_count": direction_count,
                "same_product_risk_share_pct": _share(same_product_risk, risk_total),
                "same_direction_risk_share_pct": _share(same_direction_risk, risk_total),
                "same_product_direction_risk_share_pct": _share(same_product_direction_risk, risk_total),
                "direction_bias_share_pct": _share(abs(long_risk - short_risk), risk_total),
                "cross_product_risk_share_pct": _share(risk_total - same_product_risk, risk_total),
                "cum_net_pnl_delta_C8_minus_C4": event.get("cum_net_pnl_delta_C8_minus_C4", np.nan),
                "max_broker10_C8": event.get("max_broker10_C8", np.nan),
                "max_broker10_delta_C8_minus_C4": event.get("max_broker10_delta_C8_minus_C4", np.nan),
                "min_drawdown_delta_C8_minus_C4": event.get("min_drawdown_delta_C8_minus_C4", np.nan),
                "events_with_c8_broker10_gt_100": int(_safe_float(event.get("max_broker10_C8")) > 100.0),
            }
        )
    return pd.DataFrame(rows)


def _corr(group: pd.DataFrame, left: str, right: str, method: str = "pearson") -> float:
    data = group[[left, right]].apply(pd.to_numeric, errors="coerce").dropna()
    if len(data) < 3 or data[left].nunique() < 2 or data[right].nunique() < 2:
        return np.nan
    return float(data[left].corr(data[right], method=method))


def _event_cluster_summary(cluster: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if cluster.empty:
        return pd.DataFrame()
    for horizon, group in cluster.groupby("horizon_trading_days", sort=True):
        with_incremental = group[group["incremental_rows"].gt(0)].copy()
        rows.append(
            {
                "horizon_trading_days": int(horizon),
                "events": int(len(group)),
                "events_with_incremental_reuse": int(len(with_incremental)),
                "incremental_rows_sum": int(pd.to_numeric(group["incremental_rows"], errors="coerce").sum()),
                "incremental_risk_delta_sum": float(pd.to_numeric(group["incremental_risk_delta_sum"], errors="coerce").sum()),
                "incremental_pnl_delta_sum": float(pd.to_numeric(group["incremental_pnl_delta_sum"], errors="coerce").sum()),
                "median_incremental_risk": float(pd.to_numeric(with_incremental["incremental_risk_delta_sum"], errors="coerce").median()) if not with_incremental.empty else 0.0,
                "median_incremental_pnl": float(pd.to_numeric(with_incremental["incremental_pnl_delta_sum"], errors="coerce").median()) if not with_incremental.empty else 0.0,
                "median_top_product_direction_share_pct": float(pd.to_numeric(with_incremental["top_product_direction_share_pct"], errors="coerce").median()) if not with_incremental.empty else 0.0,
                "median_top_direction_share_pct": float(pd.to_numeric(with_incremental["top_direction_share_pct"], errors="coerce").median()) if not with_incremental.empty else 0.0,
                "median_same_direction_risk_share_pct": float(pd.to_numeric(with_incremental["same_direction_risk_share_pct"], errors="coerce").median()) if not with_incremental.empty else 0.0,
                "median_cross_product_risk_share_pct": float(pd.to_numeric(with_incremental["cross_product_risk_share_pct"], errors="coerce").median()) if not with_incremental.empty else 0.0,
                "corr_risk_vs_broker10_delta": _corr(group, "incremental_risk_delta_sum", "max_broker10_delta_C8_minus_C4"),
                "spearman_risk_vs_broker10_delta": _corr(group, "incremental_risk_delta_sum", "max_broker10_delta_C8_minus_C4", method="spearman"),
                "corr_top_direction_share_vs_broker10_delta": _corr(with_incremental, "top_direction_share_pct", "max_broker10_delta_C8_minus_C4"),
                "corr_same_direction_share_vs_broker10_delta": _corr(with_incremental, "same_direction_risk_share_pct", "max_broker10_delta_C8_minus_C4"),
                "corr_top_product_direction_share_vs_drawdown_delta": _corr(with_incremental, "top_product_direction_share_pct", "min_drawdown_delta_C8_minus_C4"),
                "events_with_broker10_gt100": int(pd.to_numeric(group["max_broker10_C8"], errors="coerce").gt(100.0).sum()),
            }
        )
    return pd.DataFrame(rows)


def _entry_broker_bucket(value: Any) -> str:
    number = _safe_float(value)
    if not np.isfinite(number):
        return "missing"
    if number >= 100:
        return "broker_ge100"
    if number >= 80:
        return "broker_80_100"
    if number >= 60:
        return "broker_60_80"
    if number >= 30:
        return "broker_30_60"
    return "broker_lt30"


def _entry_drawdown_bucket(value: Any) -> str:
    number = _safe_float(value)
    if not np.isfinite(number):
        return "missing"
    if number <= -40:
        return "dd_le_minus40"
    if number <= -25:
        return "dd_minus40_to_minus25"
    if number <= -10:
        return "dd_minus25_to_minus10"
    return "dd_gt_minus10"


def _row_pressure_buckets(reuse: pd.DataFrame, daily: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    keep = [
        "date",
        "broker10_margin_to_equity_pct_C4",
        "broker10_margin_to_equity_pct_C8",
        "broker10_margin_to_equity_pct_delta_C8_minus_C4",
        "drawdown_pct_C4",
        "drawdown_pct_C8",
        "drawdown_pct_delta_C8_minus_C4",
        "account_equity_C4",
        "account_equity_C8",
    ]
    merged = reuse.merge(daily[keep], left_on="entry_date", right_on="date", how="left")
    merged["entry_broker_bucket_C8"] = merged["broker10_margin_to_equity_pct_C8"].map(_entry_broker_bucket)
    merged["entry_drawdown_bucket_C8"] = merged["drawdown_pct_C8"].map(_entry_drawdown_bucket)
    merged["entry_pressure_bucket"] = merged["entry_broker_bucket_C8"] + "|" + merged["entry_drawdown_bucket_C8"]
    incremental = merged[merged["incremental_c8_exposure"].eq(1)].copy()
    rows: list[dict[str, Any]] = []
    for bucket_col in ["entry_broker_bucket_C8", "entry_drawdown_bucket_C8", "entry_pressure_bucket"]:
        for bucket, group in incremental.groupby(bucket_col, dropna=False):
            rows.append(
                {
                    "bucket_type": bucket_col,
                    "bucket": bucket,
                    "rows": int(len(group)),
                    "risk_delta_sum": float(pd.to_numeric(group["risk_amount_delta_C8_minus_C4"], errors="coerce").sum()),
                    "pnl_delta_sum": float(pd.to_numeric(group["realized_pnl_delta_C8_minus_C4"], errors="coerce").sum()),
                    "median_pnl_delta": float(pd.to_numeric(group["realized_pnl_delta_C8_minus_C4"], errors="coerce").median()),
                    "positive_rows": int(pd.to_numeric(group["realized_pnl_delta_C8_minus_C4"], errors="coerce").gt(0).sum()),
                    "negative_rows": int(pd.to_numeric(group["realized_pnl_delta_C8_minus_C4"], errors="coerce").lt(0).sum()),
                    "avg_entry_broker10_C8": float(pd.to_numeric(group["broker10_margin_to_equity_pct_C8"], errors="coerce").mean()),
                    "avg_entry_drawdown_C8": float(pd.to_numeric(group["drawdown_pct_C8"], errors="coerce").mean()),
                    "same_direction_risk": float(
                        pd.to_numeric(
                            group[group["same_direction_as_nearest_event"].eq(1)]["risk_amount_delta_C8_minus_C4"],
                            errors="coerce",
                        ).sum()
                    ),
                }
            )
    summary = pd.DataFrame(rows)
    if not summary.empty:
        summary.sort_values(["bucket_type", "bucket"], inplace=True)
    return merged, summary


def _pressure_quartiles(cluster: pd.DataFrame) -> pd.DataFrame:
    data = cluster[cluster["horizon_trading_days"].eq(MAX_HORIZON)].copy()
    if data.empty:
        return pd.DataFrame()
    broker_q75 = pd.to_numeric(data["max_broker10_delta_C8_minus_C4"], errors="coerce").quantile(0.75)
    dd_q25 = pd.to_numeric(data["min_drawdown_delta_C8_minus_C4"], errors="coerce").quantile(0.25)
    risk_q75 = pd.to_numeric(data["incremental_risk_delta_sum"], errors="coerce").quantile(0.75)
    rows: list[dict[str, Any]] = []
    flags = {
        "broker_delta_top_quartile": data["max_broker10_delta_C8_minus_C4"].ge(broker_q75),
        "drawdown_delta_worst_quartile": data["min_drawdown_delta_C8_minus_C4"].le(dd_q25),
        "incremental_risk_top_quartile": data["incremental_risk_delta_sum"].ge(risk_q75),
        "other_events": pd.Series(True, index=data.index),
    }
    for label, mask in flags.items():
        group = data[mask].copy()
        if group.empty:
            continue
        rows.append(
            {
                "bucket": label,
                "events": int(len(group)),
                "incremental_risk_delta_sum": float(group["incremental_risk_delta_sum"].sum()),
                "incremental_pnl_delta_sum": float(group["incremental_pnl_delta_sum"].sum()),
                "median_top_product_direction_share_pct": float(group["top_product_direction_share_pct"].median()),
                "median_top_direction_share_pct": float(group["top_direction_share_pct"].median()),
                "median_same_direction_risk_share_pct": float(group["same_direction_risk_share_pct"].median()),
                "median_cross_product_risk_share_pct": float(group["cross_product_risk_share_pct"].median()),
                "median_max_broker10_delta": float(group["max_broker10_delta_C8_minus_C4"].median()),
                "median_min_drawdown_delta": float(group["min_drawdown_delta_C8_minus_C4"].median()),
                "positive_pnl_events": int(group["incremental_pnl_delta_sum"].gt(0).sum()),
                "negative_pnl_events": int(group["incremental_pnl_delta_sum"].lt(0).sum()),
            }
        )
    return pd.DataFrame(rows)


def _plot_cluster_chart(cluster: pd.DataFrame, summary: pd.DataFrame, pressure_quartile: pd.DataFrame) -> None:
    data = cluster[cluster["horizon_trading_days"].eq(MAX_HORIZON)].copy()
    if data.empty:
        return
    fig, axes = plt.subplots(2, 2, figsize=(18, 10), constrained_layout=True)
    scatter = axes[0, 0].scatter(
        data["incremental_risk_delta_sum"],
        data["max_broker10_delta_C8_minus_C4"],
        c=data["same_direction_risk_share_pct"],
        cmap="viridis",
        s=np.clip(data["incremental_rows"].fillna(0) * 12 + 20, 20, 160),
        alpha=0.8,
    )
    axes[0, 0].axhline(0, color="#6b7280", linewidth=0.8)
    axes[0, 0].set_title("20d incremental risk vs broker10 delta")
    axes[0, 0].set_xlabel("incremental risk delta")
    axes[0, 0].set_ylabel("max broker10 delta pp")
    fig.colorbar(scatter, ax=axes[0, 0], label="same direction risk share %")

    axes[0, 1].scatter(
        data["top_product_direction_share_pct"],
        data["min_drawdown_delta_C8_minus_C4"],
        c=np.where(data["incremental_pnl_delta_sum"].gt(0), "#2563eb", "#dc2626"),
        s=np.clip(data["incremental_risk_delta_sum"].fillna(0) / 4000 + 25, 20, 180),
        alpha=0.78,
    )
    axes[0, 1].axhline(0, color="#6b7280", linewidth=0.8)
    axes[0, 1].set_title("20d concentration vs drawdown delta")
    axes[0, 1].set_xlabel("top product-direction risk share %")
    axes[0, 1].set_ylabel("min drawdown delta pp")

    if not summary.empty:
        axes[1, 0].plot(summary["horizon_trading_days"], summary["incremental_pnl_delta_sum"], marker="o", label="incremental pnl")
        axes[1, 0].plot(summary["horizon_trading_days"], summary["incremental_risk_delta_sum"], marker="o", label="incremental risk")
        axes[1, 0].axhline(0, color="#6b7280", linewidth=0.8)
        axes[1, 0].set_title("Event cluster aggregate by horizon")
        axes[1, 0].set_xlabel("trading days")
        axes[1, 0].legend()

    if not pressure_quartile.empty:
        labels = pressure_quartile["bucket"].astype(str)
        y = np.arange(len(pressure_quartile))
        axes[1, 1].barh(y - 0.16, pressure_quartile["incremental_pnl_delta_sum"], height=0.32, color="#2563eb", label="pnl")
        axes[1, 1].barh(y + 0.16, pressure_quartile["incremental_risk_delta_sum"], height=0.32, color="#f59e0b", label="risk")
        axes[1, 1].set_yticks(y)
        axes[1, 1].set_yticklabels(labels, fontsize=8)
        axes[1, 1].axvline(0, color="#6b7280", linewidth=0.8)
        axes[1, 1].set_title("20d pressure quartile reuse totals")
        axes[1, 1].legend()

    for ax in axes.ravel():
        ax.grid(True, alpha=0.22)
    fig.suptitle("Stage845 C8 released-capital reuse cluster diagnostic", fontsize=13)
    fig.savefig(CLUSTER_CHART_PATH, dpi=150)
    plt.close(fig)


def _select_atlas_rows(reuse: pd.DataFrame, cluster: pd.DataFrame) -> pd.DataFrame:
    data20 = cluster[cluster["horizon_trading_days"].eq(MAX_HORIZON)].copy()
    if data20.empty:
        return pd.DataFrame()
    selected_ids = pd.concat(
        [
            data20.sort_values("max_broker10_delta_C8_minus_C4", ascending=False).head(4),
            data20.sort_values("min_drawdown_delta_C8_minus_C4", ascending=True).head(4),
            data20.sort_values("incremental_risk_delta_sum", ascending=False).head(4),
        ],
        ignore_index=True,
    )["event_id"].drop_duplicates()
    rows = reuse[
        reuse["nearest_event_id"].astype(str).isin(set(selected_ids))
        & reuse["incremental_c8_exposure"].eq(1)
    ].copy()
    if rows.empty:
        return rows
    rows = rows.merge(
        data20[
            [
                "event_id",
                "incremental_risk_delta_sum",
                "incremental_pnl_delta_sum",
                "top_product_direction",
                "top_product_direction_share_pct",
                "max_broker10_delta_C8_minus_C4",
                "min_drawdown_delta_C8_minus_C4",
            ]
        ],
        left_on="nearest_event_id",
        right_on="event_id",
        how="left",
        suffixes=("", "_event"),
    )
    rows["rank_score"] = (
        pd.to_numeric(rows["risk_amount_delta_C8_minus_C4"], errors="coerce").fillna(0.0).rank(ascending=False)
        + pd.to_numeric(rows["max_broker10_delta_C8_minus_C4"], errors="coerce").fillna(0.0).rank(ascending=False)
    )
    return rows.sort_values(["rank_score", "nearest_event_id"]).head(MAX_ATLAS_ROWS * 3)


def _plot_atlas(reuse: pd.DataFrame, cluster: pd.DataFrame) -> tuple[list[Path], pd.DataFrame]:
    selected = _select_atlas_rows(reuse, cluster)
    if selected.empty:
        return [], pd.DataFrame()
    vt_symbols = set(selected["vt_symbol"].astype(str).dropna().unique())
    minute_bars = s825._load_minute_bars(vt_symbols)
    minute_by_symbol = s825._minute_groups(minute_bars)
    covered_rows: list[pd.Series] = []
    for _, row in selected.iterrows():
        vt_symbol = str(row["vt_symbol"])
        entry_date = pd.Timestamp(row["entry_date"]).normalize()
        bars = minute_by_symbol.get(vt_symbol, pd.DataFrame())
        if not bars.empty and not bars[bars["bar_date"].eq(entry_date)].empty:
            covered_rows.append(row)
    selected = pd.DataFrame(covered_rows).head(MAX_ATLAS_ROWS)
    if selected.empty:
        return [], pd.DataFrame()
    pages = int(math.ceil(len(selected) / PER_PAGE))
    paths: list[Path] = []
    manifest_rows: list[dict[str, Any]] = []
    for page in range(1, pages + 1):
        part = selected.iloc[(page - 1) * PER_PAGE : page * PER_PAGE].copy()
        fig, axes = plt.subplots(len(part), 1, figsize=(18, max(4.0, 3.25 * len(part))), constrained_layout=True)
        axes_list = list(np.atleast_1d(axes))
        for ax, (_, row) in zip(axes_list, part.iterrows(), strict=False):
            vt_symbol = str(row["vt_symbol"])
            entry_date = pd.Timestamp(row["entry_date"]).normalize()
            direction = str(row["direction"])
            bars = minute_by_symbol.get(vt_symbol, pd.DataFrame())
            day = bars[bars["bar_date"].eq(entry_date)].copy().sort_values("bar_datetime").head(280).reset_index(drop=True) if not bars.empty else pd.DataFrame()
            if day.empty:
                ax.axis("off")
                ax.text(0.5, 0.5, f"missing minute bars {vt_symbol} {entry_date:%Y-%m-%d}", ha="center", va="center")
            else:
                s825._plot_candles(ax, day)
                entry_price = _safe_float(row.get("C8_entry_price"))
                stop_distance = _safe_float(row.get("C8_stop_distance"))
                sign = 1.0 if direction == "long" else -1.0
                stop_price = entry_price - sign * stop_distance if np.isfinite(entry_price) and np.isfinite(stop_distance) else np.nan
                if np.isfinite(entry_price):
                    ax.axhline(entry_price, color="#2563eb", linewidth=0.9, label="entry")
                if np.isfinite(stop_price):
                    ax.axhline(stop_price, color="#dc2626", linestyle="--", linewidth=0.85, label="initial stop")
                ticks = np.linspace(0, len(day) - 1, num=min(8, len(day)), dtype=int)
                ax.set_xticks(ticks)
                ax.set_xticklabels([pd.Timestamp(day.loc[pos, "bar_datetime"]).strftime("%H:%M") for pos in ticks], fontsize=7)
                handles, labels = ax.get_legend_handles_labels()
                if handles:
                    ax.legend(handles, labels, loc="best", fontsize=7)
                ax.grid(True, alpha=0.18)
            ax.set_title(
                (
                    f"{row['nearest_event_id']} -> {vt_symbol} {direction} {entry_date:%Y-%m-%d} "
                    f"after={int(row['trading_days_after_event'])}d risk={_safe_float(row.get('risk_amount_delta_C8_minus_C4')):,.0f} "
                    f"pnl={_safe_float(row.get('realized_pnl_delta_C8_minus_C4')):,.0f} "
                    f"event_top={row.get('top_product_direction', '')} "
                    f"top_share={_safe_float(row.get('top_product_direction_share_pct')):.1f}% "
                    f"broker_delta={_safe_float(row.get('max_broker10_delta_C8_minus_C4')):.2f}pp"
                ),
                fontsize=8.3,
                loc="left",
            )
            manifest_rows.append(
                {
                    "page": page,
                    "nearest_event_id": row["nearest_event_id"],
                    "vt_symbol": vt_symbol,
                    "entry_date": entry_date.strftime("%Y-%m-%d"),
                    "direction": direction,
                    "trading_days_after_event": int(row["trading_days_after_event"]),
                    "risk_delta": _safe_float(row.get("risk_amount_delta_C8_minus_C4")),
                    "pnl_delta": _safe_float(row.get("realized_pnl_delta_C8_minus_C4")),
                    "event_top_product_direction": row.get("top_product_direction", ""),
                    "event_top_share_pct": _safe_float(row.get("top_product_direction_share_pct")),
                    "event_max_broker10_delta": _safe_float(row.get("max_broker10_delta_C8_minus_C4")),
                }
            )
        fig.suptitle("Stage845 post-S3 incremental C8 reuse entry minute-K atlas", fontsize=13)
        path = Path(str(ATLAS_TEMPLATE).format(page=page))
        fig.savefig(path, dpi=150)
        plt.close(fig)
        paths.append(path)
    return paths, pd.DataFrame(manifest_rows)


def _write_report(
    cluster_summary: pd.DataFrame,
    pressure_quartile: pd.DataFrame,
    row_pressure_summary: pd.DataFrame,
    atlas_paths: list[Path],
) -> None:
    lines = [
        "# Stage845 C8释放资金复用压力簇归因",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 源候选：`{stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION}`",
        f"- 区间：`{START.date()}` 到 `{END.date()}`",
        "- 阶段性质：只读归因；读取 Stage844 输出，不改正式版、不改候选配置、不连接 CTP、不调用下单。",
        "",
        "## 外部调研判断",
        "",
        "- CME/CFTC 的风险管理资料支持把止损、再入场和仓位规模放在同一组合风险框架内评估。",
        "- vn.py 的组合策略结构也要求把信号、成交、持仓、风控分层；本阶段只看释放资金后新增暴露的流向，不把最坏事件直接写成策略规则。",
        "- 判断：若压力来自跨品种同方向堆叠或高 broker10 状态下继续加风险，下一步可以考虑低自由度复用闸门；若证据混杂，则继续转入场质量而不是组合冷却。",
        "",
        "## Event Cluster Summary",
        "",
        _md_table(cluster_summary, max_rows=30),
        "",
        "## 20d Pressure Quartile",
        "",
        _md_table(pressure_quartile, max_rows=20),
        "",
        "## Row Entry Pressure Summary",
        "",
        _md_table(row_pressure_summary, max_rows=80),
        "",
        "## Charts",
        "",
        f"- cluster chart：`{CLUSTER_CHART_PATH}`",
        *[f"- reuse entry atlas：`{path}`" for path in atlas_paths],
        "",
        "## Judgment",
        "",
        "- 本阶段只证明或反证一个 broad mechanism：释放资金后的新增暴露是否集中进入压力簇。",
        "- 入口日 broker/drawdown bucket 与事件级集中度只能作为下一步规则形状的证据，不能直接按最坏事件、品种或年份补丁化。",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    reuse = _prepare_reuse()
    event_windows = _prepare_event_windows()
    daily = _prepare_daily()
    cluster = _event_cluster(reuse, event_windows)
    cluster_summary = _event_cluster_summary(cluster)
    row_pressure, row_pressure_summary = _row_pressure_buckets(reuse, daily)
    pressure_quartile = _pressure_quartiles(cluster)

    _plot_cluster_chart(cluster, cluster_summary, pressure_quartile)
    atlas_paths, atlas_manifest = _plot_atlas(reuse, cluster)
    _write_report(cluster_summary, pressure_quartile, row_pressure_summary, atlas_paths)

    cluster.to_csv(EVENT_CLUSTER_PATH, index=False, encoding="utf-8-sig")
    cluster_summary.to_csv(EVENT_CLUSTER_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    row_pressure.to_csv(ROW_PRESSURE_BUCKET_PATH, index=False, encoding="utf-8-sig")
    row_pressure_summary.to_csv(ROW_PRESSURE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    pressure_quartile.to_csv(PRESSURE_QUARTILE_PATH, index=False, encoding="utf-8-sig")
    atlas_manifest.to_csv(ATLAS_MANIFEST_PATH, index=False, encoding="utf-8-sig")

    summary20 = cluster_summary[cluster_summary["horizon_trading_days"].eq(MAX_HORIZON)]
    row_broker_high = row_pressure_summary[
        row_pressure_summary["bucket_type"].eq("entry_broker_bucket_C8")
        & row_pressure_summary["bucket"].isin(["broker_ge100", "broker_80_100", "broker_60_80"])
    ]
    risk_corr = float(summary20["spearman_risk_vs_broker10_delta"].iloc[0]) if not summary20.empty else np.nan
    top_dir_corr = float(summary20["corr_top_direction_share_vs_broker10_delta"].iloc[0]) if not summary20.empty else np.nan
    high_broker_pnl = float(row_broker_high["pnl_delta_sum"].sum()) if not row_broker_high.empty else 0.0
    high_broker_risk = float(row_broker_high["risk_delta_sum"].sum()) if not row_broker_high.empty else 0.0
    pressure_bucket = pressure_quartile[pressure_quartile["bucket"].eq("broker_delta_top_quartile")]
    pressure_bucket_pnl = float(pressure_bucket["incremental_pnl_delta_sum"].iloc[0]) if not pressure_bucket.empty else np.nan
    pressure_bucket_risk = float(pressure_bucket["incremental_risk_delta_sum"].iloc[0]) if not pressure_bucket.empty else np.nan
    decision_label = (
        "stage845_reuse_cluster_shape_supported_not_promoted"
        if np.isfinite(risk_corr)
        and risk_corr > 0.25
        and np.isfinite(pressure_bucket_risk)
        and pressure_bucket_risk > 0
        else "stage845_reuse_cluster_evidence_mixed_no_rule"
    )
    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "source_candidate": stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION,
        "strategy_changed": False,
        "backtest_rerun": False,
        "ctp_connected": False,
        "order_api_called": False,
        "decision": decision_label,
        "risk_vs_broker10_spearman_20d": risk_corr,
        "top_direction_share_vs_broker10_corr_20d": top_dir_corr,
        "high_entry_broker_bucket_pnl_delta": high_broker_pnl,
        "high_entry_broker_bucket_risk_delta": high_broker_risk,
        "broker_delta_top_quartile_incremental_pnl": pressure_bucket_pnl,
        "broker_delta_top_quartile_incremental_risk": pressure_bucket_risk,
        "cluster_summary": cluster_summary.to_dict("records"),
        "pressure_quartile": pressure_quartile.to_dict("records"),
        "overfit_reflection": (
            "Stage845 is read-only and reuses frozen Stage844 attribution rows. It reports fixed horizons and broad "
            "cluster measures, not optimized product/year/direction filters. Any direct gate from top atlas events would overfit."
        ),
        "continue_value": (
            "Continue only if the cluster evidence is broad enough to define a live-feasible reuse gate. If correlations are weak "
            "or PnL remains positive in high-pressure buckets, move to entry-quality forensics instead of cooldown rules."
        ),
        "outputs": {
            "event_cluster": str(EVENT_CLUSTER_PATH),
            "event_cluster_summary": str(EVENT_CLUSTER_SUMMARY_PATH),
            "row_pressure_bucket": str(ROW_PRESSURE_BUCKET_PATH),
            "row_pressure_summary": str(ROW_PRESSURE_SUMMARY_PATH),
            "pressure_quartile": str(PRESSURE_QUARTILE_PATH),
            "report": str(REPORT_PATH),
            "cluster_chart": str(CLUSTER_CHART_PATH),
            "atlas_manifest": str(ATLAS_MANIFEST_PATH),
            "atlas_pages": [str(path) for path in atlas_paths],
        },
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print("cluster_summary")
    print(cluster_summary.to_string(index=False))
    print("pressure_quartile")
    print(pressure_quartile.to_string(index=False))
    print("row_pressure_summary")
    print(row_pressure_summary.to_string(index=False))


if __name__ == "__main__":
    main()
