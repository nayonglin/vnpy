from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage022"
MODEL_TAG = "stage022_path_risk_state_forensics_v1"
OUTPUT_PREFIX = "qmt_roll_stage022_c9_minrisk_path_risk_state_forensics"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
if str(EXAMPLE_DIR) not in sys.path:
    sys.path.insert(0, str(EXAMPLE_DIR))

from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage022_path_risk_state_forensics"
STAGE016_DIR = LINE_DIR / "outputs" / "stage016_intersection_stability_audit"
STAGE019_DIR = LINE_DIR / "outputs" / "stage019_no_follow_light_shave_true_engine"

CAPITAL = 150_000.0
TRADING_DAYS_PER_YEAR = 252

CURVE_IN = (
    STAGE019_DIR
    / "qmt_roll_stage019_c9_minrisk_no_follow_light_shave_true_engine_curve_"
    "stage019_no_follow_light_shave_true_engine_v1.csv"
)
FEATURES_IN = (
    STAGE016_DIR
    / "qmt_roll_stage016_c9_minrisk_intersection_stability_audit_features_"
    "stage016_intersection_stability_audit_v1.csv"
)

DAILY_STATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_state_{MODEL_TAG}.csv"
EPISODES_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_drawdown_episodes_{MODEL_TAG}.csv"
ENTRY_STATE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_state_features_{MODEL_TAG}.csv"
BUCKET_ATTR_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_state_bucket_attribution_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
PATH_STATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_path_state_panel_{MODEL_TAG}.png"
CONTRIBUTION_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_state_contribution_{MODEL_TAG}.png"
SCATTER_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_entry_state_scatter_{MODEL_TAG}.png"
HEATMAP_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_year_bucket_heatmap_{MODEL_TAG}.png"
EPISODE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_drawdown_episode_bar_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        if np.isnan(value) or np.isinf(value):
            return None
        return float(value)
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise RuntimeError(f"missing required input: {path}")
    return pd.read_csv(path, encoding="utf-8-sig")


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
    headers = list(display.columns)
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for _, row in display.iterrows():
        lines.append("| " + " | ".join(str(row[column]) for column in headers) + " |")
    return "\n".join(lines)


def _normalize_day(value: Any) -> pd.Timestamp:
    ts = pd.to_datetime(value, errors="coerce", format="mixed")
    if pd.isna(ts):
        return pd.NaT
    ts = pd.Timestamp(ts)
    if ts.tzinfo is not None:
        ts = ts.tz_localize(None)
    return ts.normalize()


def _prepare_curve() -> pd.DataFrame:
    data = _read_csv(CURVE_IN)
    if "arm" in data.columns:
        data = data[data["arm"].eq("A_official_stage847_c9_15w")].copy()
    if data.empty:
        raise RuntimeError("Stage019 curve does not contain A_official_stage847_c9_15w")
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data = data.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    for column in [
        "account_equity",
        "net_pnl",
        "drawdown_pct",
        "broker10_margin_to_equity_pct",
        "broker10_total_margin_exact",
        "c3_active_contracts",
        "c3_active_products",
        "trade_count",
        "slippage",
    ]:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce").fillna(0.0)
        else:
            data[column] = 0.0
    data["daily_return"] = data["account_equity"].pct_change().replace([np.inf, -np.inf], np.nan).fillna(0.0)
    data["rolling20_ann_vol_pct"] = (
        data["daily_return"].rolling(20, min_periods=5).std(ddof=0).fillna(0.0) * np.sqrt(TRADING_DAYS_PER_YEAR) * 100.0
    )
    data["rolling60_ann_vol_pct"] = (
        data["daily_return"].rolling(60, min_periods=10).std(ddof=0).fillna(0.0) * np.sqrt(TRADING_DAYS_PER_YEAR) * 100.0
    )
    data["rolling20_return_pct"] = (data["account_equity"] / data["account_equity"].shift(20) - 1.0) * 100.0
    data["rolling20_return_pct"] = data["rolling20_return_pct"].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    data["hwm_equity"] = data["account_equity"].cummax()
    data["equity_denominator_compression_pct"] = (data["account_equity"] / data["hwm_equity"] - 1.0) * 100.0
    data["broker90_flag"] = data["broker10_margin_to_equity_pct"] >= 90.0
    data["broker100_flag"] = data["broker10_margin_to_equity_pct"] >= 100.0
    data["dd30_flag"] = data["drawdown_pct"] <= -30.0
    data["vol100_flag"] = data["rolling20_ann_vol_pct"] >= 100.0
    return data


def _drawdown_episodes(curve: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    active: dict[str, Any] | None = None
    last_high_date = pd.Timestamp(curve["date"].iloc[0])
    last_high_equity = float(curve["account_equity"].iloc[0])

    for _, row in curve.iterrows():
        date = pd.Timestamp(row["date"])
        equity = float(row["account_equity"])
        dd = float(row["drawdown_pct"])
        if dd >= -1e-12:
            if active is not None:
                active["recovery_date"] = date
                active["end_date"] = date
                active["recovered"] = True
                rows.append(active)
                active = None
            last_high_date = date
            last_high_equity = equity
            continue
        if active is None:
            active = {
                "episode_id": len(rows) + 1,
                "peak_date": last_high_date,
                "peak_equity": last_high_equity,
                "start_date": date,
                "trough_date": date,
                "trough_equity": equity,
                "max_dd_pct": dd,
                "recovery_date": pd.NaT,
                "end_date": date,
                "recovered": False,
            }
        else:
            active["end_date"] = date
        if dd < float(active["max_dd_pct"]):
            active["max_dd_pct"] = dd
            active["trough_date"] = date
            active["trough_equity"] = equity

    if active is not None:
        rows.append(active)
    episodes = pd.DataFrame(rows)
    if episodes.empty:
        curve["drawdown_episode_id"] = 0
        curve["top_drawdown_episode_rank"] = 0
        return curve, episodes

    episodes["drawdown_days"] = (
        pd.to_datetime(episodes["end_date"]) - pd.to_datetime(episodes["start_date"])
    ).dt.days + 1
    episodes["peak_to_trough_days"] = (
        pd.to_datetime(episodes["trough_date"]) - pd.to_datetime(episodes["peak_date"])
    ).dt.days
    episodes = episodes.sort_values("max_dd_pct").reset_index(drop=True)
    episodes["depth_rank"] = np.arange(1, len(episodes) + 1)
    episodes = episodes.sort_values("episode_id").reset_index(drop=True)

    assigned = curve.copy()
    assigned["drawdown_episode_id"] = 0
    assigned["top_drawdown_episode_rank"] = 0
    for _, episode in episodes.iterrows():
        mask = (assigned["date"] >= episode["start_date"]) & (assigned["date"] <= episode["end_date"])
        assigned.loc[mask, "drawdown_episode_id"] = int(episode["episode_id"])
        if int(episode["depth_rank"]) <= 5:
            assigned.loc[mask, "top_drawdown_episode_rank"] = int(episode["depth_rank"])
    return assigned, episodes


def _bucket_drawdown(value: float) -> str:
    if pd.isna(value):
        return "missing"
    if value <= -30.0:
        return "dd_ge30"
    if value <= -20.0:
        return "dd_20_30"
    if value <= -10.0:
        return "dd_10_20"
    return "dd_lt10"


def _bucket_broker(value: float) -> str:
    if pd.isna(value):
        return "missing"
    if value >= 90.0:
        return "broker_ge90"
    if value >= 50.0:
        return "broker_50_90"
    if value > 0.0:
        return "broker_0_50"
    return "broker_0"


def _bucket_vol(value: float) -> str:
    if pd.isna(value):
        return "missing"
    if value >= 100.0:
        return "vol_ge100"
    if value >= 50.0:
        return "vol_50_100"
    return "vol_lt50"


def _bucket_active(value: float) -> str:
    if pd.isna(value):
        return "missing"
    if value >= 3.0:
        return "active_ge3"
    if value >= 2.0:
        return "active_2"
    if value >= 1.0:
        return "active_1"
    return "active_0"


def _prepare_entries(curve: pd.DataFrame) -> pd.DataFrame:
    features = _read_csv(FEATURES_IN)
    features["entry_day"] = features["entry_date"].map(_normalize_day)
    features["exit_day"] = features["exit_date"].map(_normalize_day)
    for column in [
        "realized_pnl",
        "risk_amount",
        "volume",
        "size",
        "stop_distance",
        "active_positions_before",
        "portfolio_drawdown_pct",
        "same_direction_correlation_max_corr",
        "same_direction_correlation_active_count",
    ]:
        if column in features.columns:
            features[column] = pd.to_numeric(features[column], errors="coerce")
        else:
            features[column] = np.nan
    features["entry_year"] = pd.to_datetime(features["entry_day"], errors="coerce").dt.year
    features["positive_pnl"] = features["realized_pnl"].clip(lower=0.0).fillna(0.0)
    features["negative_pnl"] = features["realized_pnl"].clip(upper=0.0).fillna(0.0)
    features["risk_base"] = pd.to_numeric(features["risk_amount"], errors="coerce").abs()
    fallback = (
        pd.to_numeric(features["volume"], errors="coerce").abs()
        * pd.to_numeric(features["size"], errors="coerce").abs()
        * pd.to_numeric(features["stop_distance"], errors="coerce").abs()
    )
    features.loc[~np.isfinite(features["risk_base"]) | (features["risk_base"] <= 0.0), "risk_base"] = fallback
    features.loc[~np.isfinite(features["risk_base"]) | (features["risk_base"] <= 0.0), "risk_base"] = 1.0

    state_cols = [
        "date",
        "account_equity",
        "drawdown_pct",
        "broker10_margin_to_equity_pct",
        "broker10_total_margin_exact",
        "c3_active_contracts",
        "c3_active_products",
        "rolling20_ann_vol_pct",
        "rolling60_ann_vol_pct",
        "rolling20_return_pct",
        "equity_denominator_compression_pct",
        "drawdown_episode_id",
        "top_drawdown_episode_rank",
    ]
    states = curve[state_cols].copy().sort_values("date")
    lots = features.sort_values("entry_day").copy()
    merged = pd.merge_asof(
        lots,
        states,
        left_on="entry_day",
        right_on="date",
        direction="backward",
        allow_exact_matches=False,
        suffixes=("", "_prev_state"),
    )
    merged = merged.rename(
        columns={
            "date": "prev_state_date",
            "account_equity": "prev_account_equity",
            "drawdown_pct": "prev_drawdown_pct",
            "broker10_margin_to_equity_pct": "prev_broker10_margin_to_equity_pct",
            "broker10_total_margin_exact": "prev_broker10_total_margin_exact",
            "c3_active_contracts": "prev_c3_active_contracts",
            "c3_active_products": "prev_c3_active_products",
            "rolling20_ann_vol_pct": "prev_rolling20_ann_vol_pct",
            "rolling60_ann_vol_pct": "prev_rolling60_ann_vol_pct",
            "rolling20_return_pct": "prev_rolling20_return_pct",
            "equity_denominator_compression_pct": "prev_equity_denominator_compression_pct",
            "drawdown_episode_id": "prev_drawdown_episode_id",
            "top_drawdown_episode_rank": "prev_top_drawdown_episode_rank",
        }
    )
    merged["prev_drawdown_bucket"] = merged["prev_drawdown_pct"].map(_bucket_drawdown)
    merged["prev_broker_bucket"] = merged["prev_broker10_margin_to_equity_pct"].map(_bucket_broker)
    merged["prev_vol_bucket"] = merged["prev_rolling20_ann_vol_pct"].map(_bucket_vol)
    merged["prev_active_bucket"] = merged["prev_c3_active_contracts"].map(_bucket_active)
    merged["entry_in_top5_dd_episode"] = pd.to_numeric(merged["prev_top_drawdown_episode_rank"], errors="coerce").fillna(0).gt(0)
    merged["preentry_system_stress"] = (
        (merged["prev_drawdown_pct"] <= -20.0)
        | (merged["prev_broker10_margin_to_equity_pct"] >= 90.0)
        | (merged["prev_rolling20_ann_vol_pct"] >= 100.0)
    )
    merged["preentry_system_stress_bucket"] = np.where(
        merged["preentry_system_stress"], "preentry_stress", "preentry_non_stress"
    )
    merged["prev_state_missing"] = merged["prev_state_date"].isna()
    return merged


def _bucket_stats(data: pd.DataFrame, bucket_type: str, bucket_column: str) -> pd.DataFrame:
    total_pos = float(data["positive_pnl"].sum())
    total_neg_abs = float(-data["negative_pnl"].sum())
    rows: list[dict[str, Any]] = []
    for bucket, group in data.groupby(bucket_column, dropna=False):
        bucket_name = "missing" if pd.isna(bucket) else str(bucket)
        pnl = float(group["realized_pnl"].sum())
        pos = float(group["positive_pnl"].sum())
        neg = float(group["negative_pnl"].sum())
        year_pnl = group.groupby("entry_year")["realized_pnl"].sum()
        rows.append(
            {
                "bucket_type": bucket_type,
                "bucket": bucket_name,
                "lot_count": int(len(group)),
                "product_count": int(group["product"].nunique()),
                "year_count": int(group["entry_year"].nunique()),
                "net_pnl": pnl,
                "positive_pnl": pos,
                "negative_pnl": neg,
                "positive_coverage_pct": pos / total_pos * 100.0 if total_pos > 0 else np.nan,
                "negative_abs_coverage_pct": -neg / total_neg_abs * 100.0 if total_neg_abs > 0 else np.nan,
                "positive_years": int((year_pnl > 0).sum()),
                "negative_years": int((year_pnl < 0).sum()),
                "mean_prev_drawdown_pct": float(group["prev_drawdown_pct"].mean()),
                "mean_prev_broker10_pct": float(group["prev_broker10_margin_to_equity_pct"].mean()),
                "mean_prev_roll20_vol_pct": float(group["prev_rolling20_ann_vol_pct"].mean()),
                "mean_prev_active_contracts": float(group["prev_c3_active_contracts"].mean()),
            }
        )
    return pd.DataFrame(rows)


def _state_attribution(entries: pd.DataFrame) -> pd.DataFrame:
    pieces = [
        _bucket_stats(entries, "preentry_system_stress", "preentry_system_stress_bucket"),
        _bucket_stats(entries, "prev_drawdown_bucket", "prev_drawdown_bucket"),
        _bucket_stats(entries, "prev_broker_bucket", "prev_broker_bucket"),
        _bucket_stats(entries, "prev_vol_bucket", "prev_vol_bucket"),
        _bucket_stats(entries, "prev_active_bucket", "prev_active_bucket"),
    ]
    return pd.concat(pieces, ignore_index=True)


def _plot_path_state(curve: pd.DataFrame, episodes: pd.DataFrame) -> None:
    fig, axes = plt.subplots(4, 1, figsize=(14, 12), sharex=True)
    top = episodes.sort_values("max_dd_pct").head(3).copy() if not episodes.empty else pd.DataFrame()
    for _, episode in top.iterrows():
        for ax in axes:
            ax.axvspan(episode["start_date"], episode["end_date"], color="#f3c623", alpha=0.14)

    axes[0].plot(curve["date"], curve["account_equity"], color="#1f77b4", label="official equity")
    axes[0].set_yscale("log")
    axes[0].set_ylabel("equity log")
    axes[0].legend(loc="best")

    axes[1].plot(curve["date"], curve["drawdown_pct"], color="#d62728", label="drawdown")
    axes[1].axhline(-30.0, color="black", linestyle="--", linewidth=0.8)
    axes[1].set_ylabel("drawdown %")
    axes[1].legend(loc="best")

    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#ff7f0e", label="broker10")
    axes[2].axhline(90.0, color="black", linestyle=":", linewidth=0.8)
    axes[2].axhline(100.0, color="black", linestyle="--", linewidth=0.8)
    axes[2].set_ylabel("broker10 %")
    axes[2].legend(loc="best")

    axes[3].plot(curve["date"], curve["rolling20_ann_vol_pct"], color="#9467bd", label="20d ann vol")
    axes[3].plot(curve["date"], curve["c3_active_contracts"] * 25.0, color="#2ca02c", alpha=0.6, label="active contracts x25")
    axes[3].axhline(100.0, color="black", linestyle="--", linewidth=0.8)
    axes[3].set_ylabel("vol % / active")
    axes[3].legend(loc="best")
    axes[0].set_title("Stage022 official path with drawdown, broker10 and rolling volatility states")
    for ax in axes:
        ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(PATH_STATE_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_contribution(entries: pd.DataFrame) -> None:
    data = entries.sort_values(["exit_day", "lot_id"]).copy()
    data["pnl"] = data["realized_pnl"].fillna(0.0)
    data["stress_pnl"] = np.where(data["preentry_system_stress"], data["pnl"], 0.0)
    data["non_stress_pnl"] = np.where(~data["preentry_system_stress"], data["pnl"], 0.0)
    data["dd_ge20_pnl"] = np.where(data["prev_drawdown_pct"] <= -20.0, data["pnl"], 0.0)
    data["broker_ge90_pnl"] = np.where(data["prev_broker10_margin_to_equity_pct"] >= 90.0, data["pnl"], 0.0)
    fig, ax = plt.subplots(figsize=(13, 6))
    ax.plot(data["exit_day"], data["pnl"].cumsum(), color="#1f77b4", label="all lots")
    ax.plot(data["exit_day"], data["stress_pnl"].cumsum(), color="#d62728", label="preentry stress")
    ax.plot(data["exit_day"], data["non_stress_pnl"].cumsum(), color="#2ca02c", label="non stress")
    ax.plot(data["exit_day"], data["dd_ge20_pnl"].cumsum(), color="#ff7f0e", alpha=0.75, label="prev DD <= -20")
    ax.plot(data["exit_day"], data["broker_ge90_pnl"].cumsum(), color="#9467bd", alpha=0.75, label="prev broker >= 90")
    ax.axhline(0.0, color="black", linewidth=0.8)
    ax.set_title("Closed-lot contribution by pre-entry risk state")
    ax.set_ylabel("cumulative realized PnL")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(CONTRIBUTION_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_scatter(entries: pd.DataFrame) -> None:
    data = entries.dropna(subset=["prev_drawdown_pct", "prev_broker10_margin_to_equity_pct"]).copy()
    colors = np.where(data["realized_pnl"] >= 0.0, "#2ca02c", "#d62728")
    sizes = np.clip(data["risk_base"] / data["risk_base"].median(), 0.5, 8.0) * 18.0
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.scatter(
        data["prev_drawdown_pct"],
        data["prev_broker10_margin_to_equity_pct"],
        c=colors,
        s=sizes,
        alpha=0.6,
        edgecolors="none",
    )
    ax.axvline(-20.0, color="black", linestyle=":", linewidth=0.8)
    ax.axvline(-30.0, color="black", linestyle="--", linewidth=0.8)
    ax.axhline(90.0, color="black", linestyle="--", linewidth=0.8)
    ax.set_xlabel("previous trading day drawdown %")
    ax.set_ylabel("previous trading day broker10 %")
    ax.set_title("Entry-state scatter: green profitable, red losing")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(SCATTER_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_heatmap(entries: pd.DataFrame) -> None:
    data = entries.copy()
    data["year"] = pd.to_datetime(data["entry_day"], errors="coerce").dt.year
    pivot = data.pivot_table(
        index="preentry_system_stress_bucket",
        columns="year",
        values="realized_pnl",
        aggfunc="sum",
        fill_value=0.0,
    )
    if pivot.empty:
        return
    fig, ax = plt.subplots(figsize=(13, 3.8))
    values = pivot.to_numpy(dtype=float)
    max_abs = np.nanmax(np.abs(values)) if np.isfinite(values).any() else 1.0
    image = ax.imshow(values, cmap="RdYlGn", aspect="auto", vmin=-max_abs, vmax=max_abs)
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels([str(int(year)) for year in pivot.columns], rotation=45, ha="right")
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            ax.text(j, i, f"{values[i, j] / 1e6:.1f}m", ha="center", va="center", fontsize=8)
    ax.set_title("Year x pre-entry system stress realized PnL")
    fig.colorbar(image, ax=ax, fraction=0.025, pad=0.02)
    fig.tight_layout()
    fig.savefig(HEATMAP_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_episode_bar(episodes: pd.DataFrame) -> None:
    top = episodes.sort_values("max_dd_pct").head(12).copy()
    if top.empty:
        return
    labels = [f"{pd.Timestamp(row.peak_date).date()}\n->{pd.Timestamp(row.trough_date).date()}" for _, row in top.iterrows()]
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.bar(range(len(top)), top["max_dd_pct"], color="#d62728")
    ax.set_xticks(range(len(top)))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("episode max drawdown %")
    ax.set_title("Deepest official drawdown episodes")
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(EPISODE_CHART_OUT, dpi=160)
    plt.close(fig)


def _write_report(
    curve: pd.DataFrame,
    episodes: pd.DataFrame,
    entries: pd.DataFrame,
    attribution: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    top_episodes = episodes.sort_values("max_dd_pct").head(8).copy()
    stress_attr = attribution[attribution["bucket_type"].eq("preentry_system_stress")].copy()
    drawdown_attr = attribution[attribution["bucket_type"].eq("prev_drawdown_bucket")].copy()
    broker_attr = attribution[attribution["bucket_type"].eq("prev_broker_bucket")].copy()
    vol_attr = attribution[attribution["bucket_type"].eq("prev_vol_bucket")].copy()
    top_loss_stress = (
        entries[entries["preentry_system_stress"]]
        .sort_values("realized_pnl")
        [
            [
                "lot_id",
                "vt_symbol",
                "direction",
                "entry_date",
                "exit_date",
                "realized_pnl",
                "prev_drawdown_pct",
                "prev_broker10_margin_to_equity_pct",
                "prev_rolling20_ann_vol_pct",
                "prev_c3_active_contracts",
            ]
        ]
        .head(12)
    )
    lines = [
        f"# {STAGE} path risk state forensics",
        "",
        f"- line_id: `{LINE_ID}`",
        f"- model_tag: `{MODEL_TAG}`",
        f"- official_live_version: `{OFFICIAL_LIVE_VERSION}`",
        f"- official_live_alias: `{OFFICIAL_LIVE_ALIAS}`",
        f"- generated_at: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`",
        "- boundary: read-only path/state forensics; no trading rule; candidate_ready=0; no CTP/order API.",
        "",
        "## Question",
        "",
        "Can the main C9/15w drawdown be explained by pre-entry portfolio risk states visible on the previous trading day?",
        "",
        "## Deepest Drawdown Episodes",
        "",
        _md_table(
            top_episodes[
                [
                    "episode_id",
                    "depth_rank",
                    "peak_date",
                    "trough_date",
                    "recovery_date",
                    "max_dd_pct",
                    "drawdown_days",
                    "peak_to_trough_days",
                ]
            ],
            max_rows=8,
        ),
        "",
        "## State Attribution",
        "",
        "### Pre-entry system stress",
        "",
        _md_table(
            stress_attr[
                [
                    "bucket",
                    "lot_count",
                    "product_count",
                    "year_count",
                    "net_pnl",
                    "positive_coverage_pct",
                    "negative_abs_coverage_pct",
                    "positive_years",
                    "negative_years",
                    "mean_prev_drawdown_pct",
                    "mean_prev_broker10_pct",
                    "mean_prev_roll20_vol_pct",
                ]
            ]
        ),
        "",
        "### Previous drawdown bucket",
        "",
        _md_table(
            drawdown_attr[
                [
                    "bucket",
                    "lot_count",
                    "net_pnl",
                    "positive_coverage_pct",
                    "negative_abs_coverage_pct",
                    "positive_years",
                    "negative_years",
                ]
            ]
        ),
        "",
        "### Previous broker10 bucket",
        "",
        _md_table(
            broker_attr[
                [
                    "bucket",
                    "lot_count",
                    "net_pnl",
                    "positive_coverage_pct",
                    "negative_abs_coverage_pct",
                    "positive_years",
                    "negative_years",
                ]
            ]
        ),
        "",
        "### Previous rolling volatility bucket",
        "",
        _md_table(
            vol_attr[
                [
                    "bucket",
                    "lot_count",
                    "net_pnl",
                    "positive_coverage_pct",
                    "negative_abs_coverage_pct",
                    "positive_years",
                    "negative_years",
                ]
            ]
        ),
        "",
        "## Worst Stress Entries",
        "",
        _md_table(top_loss_stress, max_rows=12),
        "",
        "## Decision",
        "",
        f"- decision: `{decision['decision']}`",
        f"- candidate_ready: `{int(decision['candidate_ready'])}`",
        f"- stress_lot_count: `{decision['stress_lot_count']}`",
        f"- stress_net_pnl: `{decision['stress_net_pnl']:.2f}`",
        f"- stress_negative_abs_coverage_pct: `{decision['stress_negative_abs_coverage_pct']:.4f}`",
        "",
        "## Visual Outputs",
        "",
        f"- official path state panel: `{PATH_STATE_CHART_OUT}`",
        f"- entry-state contribution: `{CONTRIBUTION_CHART_OUT}`",
        f"- entry-state scatter: `{SCATTER_CHART_OUT}`",
        f"- year bucket heatmap: `{HEATMAP_CHART_OUT}`",
        f"- drawdown episode bar: `{EPISODE_CHART_OUT}`",
        "",
        "## Files",
        "",
        f"- daily_state: `{DAILY_STATE_OUT}`",
        f"- drawdown_episodes: `{EPISODES_OUT}`",
        f"- entry_state_features: `{ENTRY_STATE_OUT}`",
        f"- state_bucket_attribution: `{BUCKET_ATTR_OUT}`",
        f"- decision: `{DECISION_OUT}`",
    ]
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curve = _prepare_curve()
    curve, episodes = _drawdown_episodes(curve)
    entries = _prepare_entries(curve)
    attribution = _state_attribution(entries)

    stress_row = attribution[
        attribution["bucket_type"].eq("preentry_system_stress")
        & attribution["bucket"].eq("preentry_stress")
    ]
    stress = stress_row.iloc[0].to_dict() if not stress_row.empty else {}
    deepest = episodes.sort_values("max_dd_pct").iloc[0].to_dict() if not episodes.empty else {}
    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "candidate_ready": False,
        "ab_experiment_triggered": False,
        "boundary": "read_only_path_state_forensics_no_trading_rule",
        "decision": "stage022_preentry_system_state_forensics_no_candidate_keep_as_hypothesis_source",
        "reason": (
            "Fixed pre-entry stress states explain part of the weak path but are not yet a "
            "tradable rule. The deepest trough often occurs after positions are already flat, "
            "so any future rule must be tested at entry or active-risk timing rather than by "
            "post-trough exits."
        ),
        "deepest_episode": deepest,
        "stress_lot_count": int(stress.get("lot_count", 0)),
        "stress_net_pnl": float(stress.get("net_pnl", 0.0)),
        "stress_positive_coverage_pct": float(stress.get("positive_coverage_pct", np.nan)),
        "stress_negative_abs_coverage_pct": float(stress.get("negative_abs_coverage_pct", np.nan)),
        "stress_positive_years": int(stress.get("positive_years", 0)),
        "stress_negative_years": int(stress.get("negative_years", 0)),
        "inputs": {"curve": CURVE_IN, "features": FEATURES_IN},
        "outputs": {
            "report": REPORT_OUT,
            "daily_state": DAILY_STATE_OUT,
            "drawdown_episodes": EPISODES_OUT,
            "entry_state_features": ENTRY_STATE_OUT,
            "state_bucket_attribution": BUCKET_ATTR_OUT,
            "path_state_chart": PATH_STATE_CHART_OUT,
            "contribution_chart": CONTRIBUTION_CHART_OUT,
            "scatter_chart": SCATTER_CHART_OUT,
            "heatmap_chart": HEATMAP_CHART_OUT,
            "episode_chart": EPISODE_CHART_OUT,
        },
    }

    curve.to_csv(DAILY_STATE_OUT, index=False, encoding="utf-8-sig")
    episodes.to_csv(EPISODES_OUT, index=False, encoding="utf-8-sig")
    entries.to_csv(ENTRY_STATE_OUT, index=False, encoding="utf-8-sig")
    attribution.to_csv(BUCKET_ATTR_OUT, index=False, encoding="utf-8-sig")
    pd.DataFrame([_json_safe(decision)]).to_csv(SUMMARY_OUT, index=False, encoding="utf-8-sig")
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    _plot_path_state(curve, episodes)
    _plot_contribution(entries)
    _plot_scatter(entries)
    _plot_heatmap(entries)
    _plot_episode_bar(episodes)
    _write_report(curve, episodes, entries, attribution, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
