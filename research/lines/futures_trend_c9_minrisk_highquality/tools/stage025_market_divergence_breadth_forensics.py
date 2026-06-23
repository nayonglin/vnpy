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
STAGE = "Stage025"
MODEL_TAG = "stage025_market_divergence_breadth_forensics_v1"
OUTPUT_PREFIX = "qmt_roll_stage025_c9_minrisk_market_divergence_breadth_forensics"

TRADING_DAYS_PER_YEAR = 252

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
if str(EXAMPLE_DIR) not in sys.path:
    sys.path.insert(0, str(EXAMPLE_DIR))

from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
STAGE024_DIR = LINE_DIR / "outputs" / "stage024_preentry_risk_granularity_forensics"
OUTPUT_DIR = LINE_DIR / "outputs" / "stage025_market_divergence_breadth_forensics"
BACKTEST_OUTPUT_DIR = EXAMPLE_DIR / "backtest_outputs"

FEATURES_IN = (
    STAGE024_DIR
    / "qmt_roll_stage024_c9_minrisk_preentry_risk_granularity_forensics_features_"
    "stage024_preentry_risk_granularity_forensics_v1.csv"
)
DAILY_STATE_IN = (
    LINE_DIR
    / "outputs"
    / "stage022_path_risk_state_forensics"
    / "qmt_roll_stage022_c9_minrisk_path_risk_state_forensics_daily_state_"
    "stage022_path_risk_state_forensics_v1.csv"
)

MARKET_DAILY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_market_state_daily_{MODEL_TAG}.csv"
FEATURES_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_features_{MODEL_TAG}.csv"
BUCKET_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_summary_{MODEL_TAG}.csv"
BUCKET_YEAR_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_year_matrix_{MODEL_TAG}.csv"
COHORT_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cohort_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
STATE_PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_market_state_path_chart_{MODEL_TAG}.png"
CONTRIBUTION_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cohort_contribution_chart_{MODEL_TAG}.png"
BUCKET_YEAR_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_year_heatmap_{MODEL_TAG}.png"
STATE_SCATTER_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_state_scatter_{MODEL_TAG}.png"
PRODUCT_STATE_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_state_heatmap_{MODEL_TAG}.png"


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
    headers = [str(column) for column in display.columns]
    column_keys = list(display.columns)
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for _, row in display.iterrows():
        lines.append("| " + " | ".join(str(row[column]) for column in column_keys) + " |")
    return "\n".join(lines)


def _bucket_numeric(series: pd.Series, bins: list[float], labels: list[str], missing_label: str) -> pd.Series:
    bucket = pd.cut(series, bins=bins, labels=labels, include_lowest=True)
    out = bucket.astype(object)
    out[series.isna()] = missing_label
    return out.astype(str)


def _synthetic_preclose_files() -> list[Path]:
    patterns = [
        "qmt_roll_stage4*_completed_preclose_full*_synthetic_preclose_bars_*.csv",
        "qmt_roll_stage460_completed_preclose_full_bar_shard_synthetic_preclose_bars_*.csv",
    ]
    files: set[Path] = set()
    for pattern in patterns:
        files.update(BACKTEST_OUTPUT_DIR.glob(pattern))
    return sorted(files)


def _load_preclose_bars() -> pd.DataFrame:
    files = _synthetic_preclose_files()
    if not files:
        raise RuntimeError("missing synthetic preclose bar shards")
    columns = {
        "date",
        "product_vt_symbol",
        "vt_symbol",
        "exchange",
        "full_bar_ready",
        "valid_ohlc",
        "synthetic_close",
        "synthetic_volume",
        "synthetic_open_interest",
    }
    frames: list[pd.DataFrame] = []
    for path in files:
        frame = pd.read_csv(path, encoding="utf-8-sig", usecols=lambda column: column in columns)
        frame["source_file"] = path.name
        frames.append(frame)
    data = pd.concat(frames, ignore_index=True)
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    for column in ["synthetic_close", "synthetic_volume", "synthetic_open_interest", "full_bar_ready", "valid_ohlc"]:
        data[column] = pd.to_numeric(data.get(column, np.nan), errors="coerce")
    data["product_key"] = data["product_vt_symbol"].fillna("").astype(str)
    data = data[
        data["date"].notna()
        & data["product_key"].ne("")
        & data["synthetic_close"].notna()
        & data["synthetic_close"].gt(0.0)
    ].copy()
    data["ready_rank"] = data["full_bar_ready"].fillna(0.0) + data["valid_ohlc"].fillna(0.0)
    data = data.sort_values(
        ["product_key", "date", "ready_rank", "synthetic_volume", "synthetic_open_interest"],
        ascending=[True, True, False, False, False],
    )
    data = data.drop_duplicates(["product_key", "date"], keep="first").reset_index(drop=True)
    return data


def _build_market_state() -> pd.DataFrame:
    bars = _load_preclose_bars()
    rows: list[pd.DataFrame] = []
    for product, group in bars.groupby("product_key"):
        item = group.sort_values("date").copy()
        close = item["synthetic_close"].astype(float)
        log_close = np.log(close)
        ret_1d = log_close.diff()
        vol_20d_daily = ret_1d.rolling(20, min_periods=10).std(ddof=0)
        ret_20d = log_close - log_close.shift(20)
        ret_60d = log_close - log_close.shift(60)
        item["ret_1d"] = ret_1d
        item["ret_20d"] = ret_20d
        item["ret_60d"] = ret_60d
        item["vol_20d_daily"] = vol_20d_daily
        item["trend_score_20d"] = ret_20d / (vol_20d_daily * np.sqrt(20.0))
        item["trend_score_60d"] = ret_60d / (vol_20d_daily * np.sqrt(60.0))
        item["product_key"] = product
        rows.append(item)
    product_state = pd.concat(rows, ignore_index=True)
    product_state = product_state.replace([np.inf, -np.inf], np.nan)

    valid = product_state[product_state["trend_score_60d"].notna()].copy()
    daily_rows: list[dict[str, Any]] = []
    for date, group in valid.groupby("date"):
        scores = group["trend_score_60d"].astype(float)
        ret_60 = group["ret_60d"].astype(float)
        signs = np.sign(scores)
        daily_rows.append(
            {
                "date": date,
                "market_product_count": int(group["product_key"].nunique()),
                "mdi_abs_trend_60_mean": float(scores.abs().mean()),
                "mdi_signed_trend_60_mean": float(scores.mean()),
                "trend_participation_pct": float((scores.abs() >= 1.0).mean() * 100.0),
                "directional_balance_abs": float(abs(signs.mean())),
                "uptrend_pct": float((scores > 1.0).mean() * 100.0),
                "downtrend_pct": float((scores < -1.0).mean() * 100.0),
                "cross_sectional_ret60_dispersion": float(ret_60.std(ddof=0)),
                "median_abs_ret60_pct": float(ret_60.abs().median() * 100.0),
            }
        )
    daily = pd.DataFrame(daily_rows).sort_values("date").reset_index(drop=True)
    daily["mdi_abs_trend_60_mean_roll252_mean"] = daily["mdi_abs_trend_60_mean"].rolling(
        252, min_periods=80
    ).mean()
    daily["mdi_abs_trend_60_mean_roll252_std"] = daily["mdi_abs_trend_60_mean"].rolling(
        252, min_periods=80
    ).std(ddof=0)
    daily["mdi_abs_trend_60_z"] = (
        (daily["mdi_abs_trend_60_mean"] - daily["mdi_abs_trend_60_mean_roll252_mean"])
        / daily["mdi_abs_trend_60_mean_roll252_std"]
    ).replace([np.inf, -np.inf], np.nan)
    daily["trend_participation_roll252_mean"] = daily["trend_participation_pct"].rolling(
        252, min_periods=80
    ).mean()
    daily["trend_participation_roll252_std"] = daily["trend_participation_pct"].rolling(
        252, min_periods=80
    ).std(ddof=0)
    daily["trend_participation_z"] = (
        (daily["trend_participation_pct"] - daily["trend_participation_roll252_mean"])
        / daily["trend_participation_roll252_std"]
    ).replace([np.inf, -np.inf], np.nan)
    daily["mdi_z_bucket_stage025"] = _bucket_numeric(
        daily["mdi_abs_trend_60_z"],
        [-1_000_000.0, -0.75, 0.75, 1_000_000.0],
        ["mdi_z_low", "mdi_z_mid", "mdi_z_high"],
        "mdi_z_missing",
    )
    daily["participation_bucket_stage025"] = _bucket_numeric(
        daily["trend_participation_pct"],
        [-0.1, 25.0, 50.0, 75.0, 100.0],
        ["part_lt25", "part_25_50", "part_50_75", "part_ge75"],
        "part_missing",
    )
    daily["directional_balance_bucket_stage025"] = _bucket_numeric(
        daily["directional_balance_abs"],
        [-0.1, 0.20, 0.40, 0.70, 1.01],
        ["dir_bal_lt20", "dir_bal_20_40", "dir_bal_40_70", "dir_bal_ge70"],
        "dir_bal_missing",
    )
    daily["dispersion_bucket_stage025"] = _bucket_numeric(
        daily["cross_sectional_ret60_dispersion"],
        [-0.1, 0.05, 0.10, 0.20, 10.0],
        ["disp_lt5pct", "disp_5_10pct", "disp_10_20pct", "disp_ge20pct"],
        "disp_missing",
    )
    daily["broad_market_state_stage025"] = "normal_mixed"
    daily.loc[
        daily["mdi_z_bucket_stage025"].eq("mdi_z_low") & daily["participation_bucket_stage025"].isin(["part_lt25", "part_25_50"]),
        "broad_market_state_stage025",
    ] = "low_divergence_low_participation"
    daily.loc[
        daily["mdi_z_bucket_stage025"].eq("mdi_z_high") & daily["participation_bucket_stage025"].isin(["part_50_75", "part_ge75"]),
        "broad_market_state_stage025",
    ] = "high_divergence_high_participation"
    daily.loc[
        daily["directional_balance_bucket_stage025"].isin(["dir_bal_40_70", "dir_bal_ge70"])
        & daily["participation_bucket_stage025"].isin(["part_50_75", "part_ge75"]),
        "broad_market_state_stage025",
    ] = "one_sided_crowded_trend"
    daily.loc[daily["mdi_z_bucket_stage025"].eq("mdi_z_missing"), "broad_market_state_stage025"] = "market_state_missing"
    daily.insert(0, "stage", STAGE)
    return daily


def _prepare_features(market_daily: pd.DataFrame) -> pd.DataFrame:
    data = _read_csv(FEATURES_IN)
    for column in ["realized_pnl", "risk_amount", "selected_volume", "prev_drawdown_pct"]:
        data[column] = pd.to_numeric(data.get(column, np.nan), errors="coerce")
    data["entry_date"] = pd.to_datetime(data["entry_date"], errors="coerce")
    data["exit_date"] = pd.to_datetime(data["exit_date"], errors="coerce")
    data["prev_state_date"] = pd.to_datetime(data.get("prev_state_date"), errors="coerce")
    data["entry_year"] = data["entry_date"].dt.year
    data["exit_day"] = data["exit_date"].dt.normalize()
    data["product_key"] = data.get("product_key", data.get("product", "missing")).fillna("missing").astype(str)
    market_columns = [
        "date",
        "market_product_count",
        "mdi_abs_trend_60_mean",
        "mdi_signed_trend_60_mean",
        "mdi_abs_trend_60_z",
        "trend_participation_pct",
        "trend_participation_z",
        "directional_balance_abs",
        "uptrend_pct",
        "downtrend_pct",
        "cross_sectional_ret60_dispersion",
        "median_abs_ret60_pct",
        "mdi_z_bucket_stage025",
        "participation_bucket_stage025",
        "directional_balance_bucket_stage025",
        "dispersion_bucket_stage025",
        "broad_market_state_stage025",
    ]
    merged = data.merge(
        market_daily[market_columns],
        left_on=data["prev_state_date"].dt.normalize(),
        right_on=market_daily["date"].dt.normalize(),
        how="left",
        suffixes=("", "_market"),
    )
    if "date" in merged.columns:
        merged = merged.drop(columns=["date"])
    if "key_0" in merged.columns:
        merged = merged.rename(columns={"key_0": "market_state_date"})
    for column, missing_value in {
        "mdi_z_bucket_stage025": "mdi_z_missing",
        "participation_bucket_stage025": "part_missing",
        "directional_balance_bucket_stage025": "dir_bal_missing",
        "dispersion_bucket_stage025": "disp_missing",
        "broad_market_state_stage025": "market_state_missing",
    }.items():
        merged[column] = merged[column].fillna(missing_value).astype(str)
    merged["market_state_missing_stage025"] = merged["broad_market_state_stage025"].eq("market_state_missing")
    return merged


def _prepare_daily_state() -> pd.DataFrame:
    data = _read_csv(DAILY_STATE_IN)
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data = data.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    for column in ["account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]:
        data[column] = pd.to_numeric(data.get(column, np.nan), errors="coerce").fillna(0.0)
    return data


def _summary_for_group(data: pd.DataFrame, family: str, bucket: str, group: pd.DataFrame) -> dict[str, Any]:
    total_positive = float(data.loc[data["realized_pnl"] > 0.0, "realized_pnl"].sum())
    total_negative_abs = float((-data.loc[data["realized_pnl"] < 0.0, "realized_pnl"]).sum())
    positive = float(group.loc[group["realized_pnl"] > 0.0, "realized_pnl"].sum())
    negative_abs = float((-group.loc[group["realized_pnl"] < 0.0, "realized_pnl"]).sum())
    yearly = group.groupby("entry_year")["realized_pnl"].sum().dropna()
    return {
        "bucket_family": family,
        "bucket": str(bucket),
        "lot_count": int(len(group)),
        "product_count": int(group["product_key"].nunique()) if len(group) else 0,
        "year_count": int(group["entry_year"].nunique()) if len(group) else 0,
        "net_pnl": float(group["realized_pnl"].sum()) if len(group) else 0.0,
        "positive_pnl": positive,
        "negative_pnl_abs": negative_abs,
        "positive_coverage_pct": positive / total_positive * 100.0 if total_positive else 0.0,
        "negative_coverage_pct": negative_abs / total_negative_abs * 100.0 if total_negative_abs else 0.0,
        "positive_year_count": int((yearly > 0.0).sum()),
        "negative_year_count": int((yearly < 0.0).sum()),
        "mean_mdi_abs_trend_60_z": float(group["mdi_abs_trend_60_z"].mean()) if len(group) else 0.0,
        "mean_trend_participation_pct": float(group["trend_participation_pct"].mean()) if len(group) else 0.0,
        "mean_directional_balance_abs": float(group["directional_balance_abs"].mean()) if len(group) else 0.0,
        "mean_prev_drawdown_pct": float(group["prev_drawdown_pct"].mean()) if len(group) else 0.0,
    }


def _bucket_summary(data: pd.DataFrame) -> pd.DataFrame:
    families = {
        "mdi_z": "mdi_z_bucket_stage025",
        "participation": "participation_bucket_stage025",
        "directional_balance": "directional_balance_bucket_stage025",
        "dispersion": "dispersion_bucket_stage025",
        "broad_market_state": "broad_market_state_stage025",
    }
    rows: list[dict[str, Any]] = []
    for family, column in families.items():
        for bucket, group in data.groupby(column, dropna=False):
            rows.append(_summary_for_group(data, family, str(bucket), group))
    return pd.DataFrame(rows).sort_values(["bucket_family", "net_pnl"]).reset_index(drop=True)


def _bucket_year_matrix(data: pd.DataFrame) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for family, column in {
        "mdi_z": "mdi_z_bucket_stage025",
        "participation": "participation_bucket_stage025",
        "directional_balance": "directional_balance_bucket_stage025",
        "broad_market_state": "broad_market_state_stage025",
    }.items():
        item = data.groupby([column, "entry_year"])["realized_pnl"].sum().reset_index()
        item = item.rename(columns={column: "bucket"})
        item.insert(0, "bucket_family", family)
        rows.append(item)
    return pd.concat(rows, ignore_index=True)


def _cohort_masks(data: pd.DataFrame) -> dict[str, pd.Series]:
    return {
        "all_lots": pd.Series(True, index=data.index),
        "market_state_missing": data["market_state_missing_stage025"],
        "mdi_z_low": data["mdi_z_bucket_stage025"].eq("mdi_z_low"),
        "mdi_z_mid": data["mdi_z_bucket_stage025"].eq("mdi_z_mid"),
        "mdi_z_high": data["mdi_z_bucket_stage025"].eq("mdi_z_high"),
        "participation_lt25": data["participation_bucket_stage025"].eq("part_lt25"),
        "participation_ge50": data["participation_bucket_stage025"].isin(["part_50_75", "part_ge75"]),
        "low_divergence_low_participation": data["broad_market_state_stage025"].eq("low_divergence_low_participation"),
        "high_divergence_high_participation": data["broad_market_state_stage025"].eq("high_divergence_high_participation"),
        "one_sided_crowded_trend": data["broad_market_state_stage025"].eq("one_sided_crowded_trend"),
    }


def _cohort_summary(data: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for cohort, mask in _cohort_masks(data).items():
        rows.append(_summary_for_group(data, "cohort", cohort, data[mask.fillna(False)].copy()))
    return pd.DataFrame(rows)


def _cumulative_by_exit(data: pd.DataFrame, daily: pd.DataFrame, mask: pd.Series) -> pd.Series:
    group = data[mask.fillna(False) & data["exit_day"].notna()].copy()
    pnl_by_day = group.groupby("exit_day")["realized_pnl"].sum()
    index = pd.DatetimeIndex(daily["date"].dt.normalize())
    series = pnl_by_day.reindex(index, fill_value=0.0).cumsum()
    series.index = daily["date"].values
    return series


def _plot_state_path(daily: pd.DataFrame, market_daily: pd.DataFrame) -> None:
    merged = daily.merge(market_daily, on="date", how="left")
    fig, axes = plt.subplots(4, 1, figsize=(14, 12), sharex=True, gridspec_kw={"height_ratios": [2, 1, 1, 1]})
    axes[0].plot(merged["date"], merged["account_equity"], color="#2563eb", linewidth=1.4, label="official equity")
    axes[0].set_yscale("log")
    axes[0].grid(True, alpha=0.25)
    axes[0].set_ylabel("equity log")
    axes[0].legend(loc="upper left")

    axes[1].plot(merged["date"], merged["mdi_abs_trend_60_z"], color="#0f766e", linewidth=1.0, label="MDI z")
    axes[1].axhline(0.75, color="#16a34a", linestyle="--", linewidth=0.8)
    axes[1].axhline(-0.75, color="#dc2626", linestyle="--", linewidth=0.8)
    axes[1].grid(True, alpha=0.25)
    axes[1].set_ylabel("MDI z")
    axes[1].legend(loc="upper left")

    axes[2].plot(
        merged["date"],
        merged["trend_participation_pct"],
        color="#9333ea",
        linewidth=1.0,
        label="trend participation pct",
    )
    axes[2].plot(
        merged["date"],
        merged["directional_balance_abs"] * 100.0,
        color="#f97316",
        linewidth=0.9,
        label="direction balance abs x100",
    )
    axes[2].axhline(50.0, color="#64748b", linestyle=":", linewidth=0.8)
    axes[2].grid(True, alpha=0.25)
    axes[2].set_ylabel("pct")
    axes[2].legend(loc="upper left", ncol=2, fontsize=8)

    axes[3].plot(merged["date"], merged["drawdown_pct"], color="#334155", linewidth=1.1, label="official drawdown")
    axes[3].plot(
        merged["date"],
        merged["broker10_margin_to_equity_pct"],
        color="#a855f7",
        linewidth=0.9,
        label="broker10 pct",
    )
    axes[3].axhline(-40.0, color="#dc2626", linestyle="--", linewidth=0.8)
    axes[3].axhline(100.0, color="#a855f7", linestyle="--", linewidth=0.8)
    axes[3].grid(True, alpha=0.25)
    axes[3].set_ylabel("pct")
    axes[3].legend(loc="lower left", ncol=2, fontsize=8)
    fig.suptitle("Stage025 official path vs pre-entry market divergence state")
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig(STATE_PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_contribution(data: pd.DataFrame, daily: pd.DataFrame) -> None:
    masks = _cohort_masks(data)
    cohorts = [
        ("mdi_z_low", "#dc2626"),
        ("mdi_z_mid", "#64748b"),
        ("mdi_z_high", "#16a34a"),
        ("participation_lt25", "#f97316"),
        ("participation_ge50", "#2563eb"),
        ("one_sided_crowded_trend", "#9333ea"),
    ]
    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True, gridspec_kw={"height_ratios": [2, 1]})
    axes[0].plot(daily["date"], daily["account_equity"], color="#2563eb", linewidth=1.4, label="official equity")
    axes[0].set_yscale("log")
    axes[0].grid(True, alpha=0.25)
    axes[0].set_ylabel("equity log")
    axes[0].legend(loc="upper left")
    for cohort, color in cohorts:
        series = _cumulative_by_exit(data, daily, masks[cohort])
        axes[1].plot(series.index, series.values, label=cohort, linewidth=1.15, color=color)
    axes[1].axhline(0.0, color="#111827", linewidth=0.8)
    axes[1].grid(True, alpha=0.25)
    axes[1].set_ylabel("closed-lot cumulative pnl")
    axes[1].legend(loc="upper left", ncol=3, fontsize=8)
    fig.suptitle("Stage025 market divergence cohorts contribution")
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(CONTRIBUTION_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_bucket_year_heatmap(bucket_year: pd.DataFrame) -> None:
    focus = bucket_year[bucket_year["bucket_family"].isin(["mdi_z", "participation", "broad_market_state"])].copy()
    focus["row"] = focus["bucket_family"] + ":" + focus["bucket"].astype(str)
    order = focus.groupby("row")["realized_pnl"].sum().abs().sort_values(ascending=False).index.tolist()
    pivot = focus.pivot_table(index="row", columns="entry_year", values="realized_pnl", aggfunc="sum", fill_value=0.0)
    pivot = pivot.reindex(order)
    values = pivot.to_numpy(dtype=float)
    vmax = max(float(np.nanmax(np.abs(values))), 1.0)
    fig, ax = plt.subplots(figsize=(13, 8))
    image = ax.imshow(values, aspect="auto", cmap="RdBu", vmin=-vmax, vmax=vmax)
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=8)
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels([str(int(column)) for column in pivot.columns], fontsize=8)
    for y in range(values.shape[0]):
        for x in range(values.shape[1]):
            if abs(values[y, x]) >= vmax * 0.08:
                ax.text(x, y, f"{values[y, x] / 10000:.0f}w", ha="center", va="center", fontsize=7)
    ax.set_title("Stage025 market divergence bucket-year net pnl")
    fig.colorbar(image, ax=ax, fraction=0.025, pad=0.02, label="net pnl")
    fig.tight_layout()
    fig.savefig(BUCKET_YEAR_HEATMAP_OUT, dpi=160)
    plt.close(fig)


def _plot_state_scatter(data: pd.DataFrame) -> None:
    plot = data[data["mdi_abs_trend_60_z"].notna() & data["trend_participation_pct"].notna()].copy()
    fig, ax = plt.subplots(figsize=(11, 7))
    colors = np.where(plot["realized_pnl"] < 0.0, "#dc2626", "#2563eb")
    sizes = np.clip(np.abs(plot["realized_pnl"].fillna(0.0)) / 40000.0, 12.0, 280.0)
    ax.scatter(
        plot["mdi_abs_trend_60_z"],
        plot["trend_participation_pct"],
        s=sizes,
        c=colors,
        alpha=0.55,
        edgecolor="white",
        linewidth=0.35,
    )
    ax.axvline(-0.75, color="#dc2626", linestyle="--", linewidth=0.8)
    ax.axvline(0.75, color="#16a34a", linestyle="--", linewidth=0.8)
    ax.axhline(25.0, color="#64748b", linestyle=":", linewidth=0.8)
    ax.axhline(50.0, color="#64748b", linestyle=":", linewidth=0.8)
    ax.set_xlabel("market divergence abs-trend z")
    ax.set_ylabel("trend participation pct")
    ax.set_title("Stage025 entry lots in market divergence state space; size = abs pnl")
    ax.grid(True, alpha=0.25)
    handles = [
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor="#2563eb", markersize=8, label="winning lot"),
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor="#dc2626", markersize=8, label="losing lot"),
    ]
    ax.legend(handles=handles, loc="upper right")
    fig.tight_layout()
    fig.savefig(STATE_SCATTER_OUT, dpi=160)
    plt.close(fig)


def _plot_product_state_heatmap(data: pd.DataFrame) -> None:
    plot = data[~data["market_state_missing_stage025"]].copy()
    pivot = plot.pivot_table(
        index="product_key",
        columns="mdi_z_bucket_stage025",
        values="realized_pnl",
        aggfunc="sum",
        fill_value=0.0,
    )
    column_order = [column for column in ["mdi_z_low", "mdi_z_mid", "mdi_z_high"] if column in pivot.columns]
    pivot = pivot[column_order]
    pivot = pivot.reindex(pivot.sum(axis=1).abs().sort_values(ascending=False).index[:30])
    values = pivot.to_numpy(dtype=float)
    vmax = max(float(np.nanmax(np.abs(values))), 1.0)
    fig, ax = plt.subplots(figsize=(8, 10))
    image = ax.imshow(values, aspect="auto", cmap="RdBu", vmin=-vmax, vmax=vmax)
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(pivot.index, fontsize=8)
    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=20, ha="right", fontsize=8)
    for y in range(values.shape[0]):
        for x in range(values.shape[1]):
            if abs(values[y, x]) >= vmax * 0.08:
                ax.text(x, y, f"{values[y, x] / 10000:.0f}w", ha="center", va="center", fontsize=7)
    ax.set_title("Stage025 product x MDI-z bucket net pnl")
    fig.colorbar(image, ax=ax, fraction=0.04, pad=0.02, label="net pnl")
    fig.tight_layout()
    fig.savefig(PRODUCT_STATE_HEATMAP_OUT, dpi=160)
    plt.close(fig)


def _build_decision(cohort_summary: pd.DataFrame, features: pd.DataFrame, market_daily: pd.DataFrame) -> dict[str, Any]:
    def row(cohort: str) -> pd.Series:
        matched = cohort_summary[cohort_summary["bucket"].eq(cohort)]
        if matched.empty:
            return pd.Series(dtype=object)
        return matched.iloc[0]

    low = row("mdi_z_low")
    high = row("mdi_z_high")
    low_part = row("participation_lt25")
    high_part = row("participation_ge50")
    crowded = row("one_sided_crowded_trend")
    missing = row("market_state_missing")

    promising_low_divergence = (
        not low.empty
        and float(low.get("net_pnl", 0.0)) < 0.0
        and int(low.get("lot_count", 0)) >= 40
        and int(low.get("year_count", 0)) >= 4
        and not high.empty
        and float(high.get("net_pnl", 0.0)) > 0.0
    )
    if promising_low_divergence:
        decision = "stage025_market_divergence_low_state_promising_readonly_needs_proxy"
        reason = [
            "Low market divergence bucket is negative while high divergence is positive, but this is only a closed-lot attribution.",
            "The rule cannot be promoted without a predeclared proxy/true-engine test that preserves C9 right-tail exposure.",
            "Market divergence is exogenous and pre-entry visible, so it remains a valid hypothesis source.",
        ]
    else:
        decision = "stage025_market_divergence_no_candidate_nonmonotonic_or_incomplete"
        reason = [
            "Market divergence/breadth states do not yet form a sufficient promotable rule from closed-lot attribution.",
            "The 2018-2019 official entries have no local synthetic preclose breadth state, so coverage is incomplete.",
            "Any trading rule would still need a true engine; this stage is read-only forensics.",
        ]

    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "candidate_ready": 0,
        "ab_triggered": 0,
        "decision": decision,
        "reason": reason,
        "market_state_daily_rows": int(len(market_daily)),
        "market_state_date_min": market_daily["date"].min(),
        "market_state_date_max": market_daily["date"].max(),
        "market_state_product_count_median": float(market_daily["market_product_count"].median()),
        "feature_lot_count": int(len(features)),
        "market_state_missing_lot_count": int(features["market_state_missing_stage025"].sum()),
        "mdi_z_low_net_pnl": float(low.get("net_pnl", 0.0)) if not low.empty else 0.0,
        "mdi_z_low_lot_count": int(low.get("lot_count", 0)) if not low.empty else 0,
        "mdi_z_high_net_pnl": float(high.get("net_pnl", 0.0)) if not high.empty else 0.0,
        "mdi_z_high_lot_count": int(high.get("lot_count", 0)) if not high.empty else 0,
        "participation_lt25_net_pnl": float(low_part.get("net_pnl", 0.0)) if not low_part.empty else 0.0,
        "participation_ge50_net_pnl": float(high_part.get("net_pnl", 0.0)) if not high_part.empty else 0.0,
        "one_sided_crowded_trend_net_pnl": float(crowded.get("net_pnl", 0.0)) if not crowded.empty else 0.0,
        "market_state_missing_net_pnl": float(missing.get("net_pnl", 0.0)) if not missing.empty else 0.0,
        "output_files": {
            "market_state_daily": MARKET_DAILY_OUT,
            "features": FEATURES_OUT,
            "bucket_summary": BUCKET_SUMMARY_OUT,
            "bucket_year_matrix": BUCKET_YEAR_OUT,
            "cohort_summary": COHORT_SUMMARY_OUT,
            "report": REPORT_OUT,
            "state_path_chart": STATE_PATH_CHART_OUT,
            "cohort_contribution_chart": CONTRIBUTION_CHART_OUT,
            "bucket_year_heatmap": BUCKET_YEAR_HEATMAP_OUT,
            "state_scatter": STATE_SCATTER_OUT,
            "product_state_heatmap": PRODUCT_STATE_HEATMAP_OUT,
        },
    }


def _write_report(
    features: pd.DataFrame,
    market_daily: pd.DataFrame,
    bucket_summary: pd.DataFrame,
    bucket_year: pd.DataFrame,
    cohort_summary: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    focus_cohorts = cohort_summary[
        cohort_summary["bucket"].isin(
            [
                "market_state_missing",
                "mdi_z_low",
                "mdi_z_mid",
                "mdi_z_high",
                "participation_lt25",
                "participation_ge50",
                "low_divergence_low_participation",
                "high_divergence_high_participation",
                "one_sided_crowded_trend",
            ]
        )
    ].copy()
    weakest = bucket_summary.sort_values("net_pnl").head(12)
    strongest = bucket_summary.sort_values("net_pnl", ascending=False).head(12)
    mdi_year = bucket_year[bucket_year["bucket_family"].eq("mdi_z")].pivot_table(
        index="bucket", columns="entry_year", values="realized_pnl", aggfunc="sum", fill_value=0.0
    )
    lines = [
        f"# {STAGE} market divergence / breadth 入场前状态只读归因",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- 当前官方版本：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`",
        "- 阶段性质：只读法证；市场状态只使用入场前已完成交易日的合成 preclose 日线，不使用未来盈亏生成条件。",
        "- 候选状态：`candidate_ready=0`，不改正式配置、不连接 CTP、不调用订单 API。",
        "",
        "## 核心结论",
        "",
        f"- 决策：`{decision['decision']}`。",
        f"- market daily 覆盖 `{decision['market_state_daily_rows']}` 日，日期 `{decision['market_state_date_min']}` 到 `{decision['market_state_date_max']}`，中位产品数 `{decision['market_state_product_count_median']:.2f}`。",
        f"- official lots `{decision['feature_lot_count']}` 笔，其中 market state missing `{decision['market_state_missing_lot_count']}` 笔。",
        f"- `mdi_z_low` 净 PnL `{decision['mdi_z_low_net_pnl']:.2f}`，笔数 `{decision['mdi_z_low_lot_count']}`。",
        f"- `mdi_z_high` 净 PnL `{decision['mdi_z_high_net_pnl']:.2f}`，笔数 `{decision['mdi_z_high_lot_count']}`。",
        f"- `participation_lt25` 净 PnL `{decision['participation_lt25_net_pnl']:.2f}`。",
        f"- `participation_ge50` 净 PnL `{decision['participation_ge50_net_pnl']:.2f}`。",
        f"- `one_sided_crowded_trend` 净 PnL `{decision['one_sided_crowded_trend_net_pnl']:.2f}`。",
        "",
        "## 重点 cohort 摘要",
        "",
        _md_table(focus_cohorts),
        "",
        "## 最弱固定分桶",
        "",
        _md_table(weakest),
        "",
        "## 最强固定分桶",
        "",
        _md_table(strongest),
        "",
        "## MDI z 年度矩阵",
        "",
        _md_table(mdi_year.reset_index()),
        "",
        "## 输出文件",
        "",
    ]
    for key, value in decision["output_files"].items():
        lines.append(f"- {key}：`{value}`")
    lines.extend(
        [
            "",
            "## 视觉判断",
            "",
            "- state path chart 用官方权益曲线、MDI z、trend participation、directional balance、drawdown 和 broker10 放在同一张图，检查状态是否领先回撤。",
            "- cohort contribution chart 比较 `mdi_z_low/mid/high` 与参与度状态的累计 closed-lot PnL，判断是否只是局部年份下沉。",
            "- bucket-year heatmap 检查状态收益是否跨年稳定，避免把某一年压力写成规则。",
            "- state scatter 检查盈亏点在 market divergence 空间是否可分。",
            "- product-state heatmap 检查是否被少数产品主导；如果是，则不允许交易化。",
            "",
            "## 后续边界",
            "",
            "- 本阶段不是策略版本，不触发 A/B。",
            "- 若 market divergence 只在单一年度或少数产品有效，只能保留为解释标签。",
            "- 若后续要交易化，必须先冻结一个不扫阈值的 true-engine/proxy，并证明不切断 C9 右尾。",
        ]
    )
    REPORT_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    market_daily = _build_market_state()
    features = _prepare_features(market_daily)
    daily_state = _prepare_daily_state()
    bucket_summary = _bucket_summary(features)
    bucket_year = _bucket_year_matrix(features)
    cohort_summary = _cohort_summary(features)
    decision = _build_decision(cohort_summary, features, market_daily)

    market_daily.to_csv(MARKET_DAILY_OUT, index=False, encoding="utf-8-sig")
    features.to_csv(FEATURES_OUT, index=False, encoding="utf-8-sig")
    bucket_summary.to_csv(BUCKET_SUMMARY_OUT, index=False, encoding="utf-8-sig")
    bucket_year.to_csv(BUCKET_YEAR_OUT, index=False, encoding="utf-8-sig")
    cohort_summary.to_csv(COHORT_SUMMARY_OUT, index=False, encoding="utf-8-sig")
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    _plot_state_path(daily_state, market_daily)
    _plot_contribution(features, daily_state)
    _plot_bucket_year_heatmap(bucket_year)
    _plot_state_scatter(features)
    _plot_product_state_heatmap(features)
    _write_report(features, market_daily, bucket_summary, bucket_year, cohort_summary, decision)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
