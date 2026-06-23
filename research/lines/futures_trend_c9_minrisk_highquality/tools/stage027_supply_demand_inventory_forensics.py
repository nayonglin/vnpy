from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage027"
MODEL_TAG = "stage027_supply_demand_inventory_forensics_v1"
OUTPUT_PREFIX = "qmt_roll_stage027_c9_minrisk_supply_demand_inventory_forensics"
TRADING_DAYS_PER_YEAR = 252
ACCOUNT_CAPITAL = 150_000.0
MAX_SIGNAL_AGE_DAYS = 7

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
if str(EXAMPLE_DIR) not in sys.path:
    sys.path.insert(0, str(EXAMPLE_DIR))

from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
STAGE024_DIR = LINE_DIR / "outputs" / "stage024_preentry_risk_granularity_forensics"
STAGE005_DIR = LINE_DIR / "outputs" / "stage005_signal_quality_visual_forensics"
OUTPUT_DIR = LINE_DIR / "outputs" / "stage027_supply_demand_inventory_forensics"
BACKTEST_OUTPUT_DIR = EXAMPLE_DIR / "backtest_outputs"

FEATURES_IN = (
    STAGE024_DIR
    / "qmt_roll_stage024_c9_minrisk_preentry_risk_granularity_forensics_features_"
    "stage024_preentry_risk_granularity_forensics_v1.csv"
)
OFFICIAL_CURVE_IN = (
    STAGE005_DIR
    / "qmt_roll_stage005_c9_minrisk_signal_quality_visual_forensics_official_curve_"
    "stage005_signal_quality_visual_forensics_v1.csv"
)
SIGNAL_2020_2022_IN = (
    BACKTEST_OUTPUT_DIR
    / "qmt_roll_stage358_supply_demand_backfill_2020_2022_external_signals_"
    "stage358_supply_demand_backfill_2020_2022_v1.csv"
)
SIGNAL_2023_2026_IN = (
    BACKTEST_OUTPUT_DIR
    / "qmt_roll_stage316_supply_demand_quality_probe_external_signals_"
    "stage316_supply_demand_quality_probe_v1.csv"
)

FEATURES_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_features_{MODEL_TAG}.csv"
COMBINED_SIGNALS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_combined_external_signals_{MODEL_TAG}.csv"
BUCKET_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_summary_{MODEL_TAG}.csv"
BUCKET_YEAR_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_year_matrix_{MODEL_TAG}.csv"
PRODUCT_BUCKET_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_bucket_matrix_{MODEL_TAG}.csv"
ACTIVE_SHARE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_active_share_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_path_supply_state_chart_{MODEL_TAG}.png"
CONTRIBUTION_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cohort_contribution_chart_{MODEL_TAG}.png"
BUCKET_YEAR_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_year_heatmap_{MODEL_TAG}.png"
SCATTER_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_supply_score_scatter_{MODEL_TAG}.png"
PRODUCT_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_supply_heatmap_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        if np.isnan(value) or np.isinf(value):
            return None
        return float(value)
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
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
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for _, row in display.iterrows():
        lines.append("| " + " | ".join(str(row[column]) for column in display.columns) + " |")
    return "\n".join(lines)


def _load_official_curve() -> pd.DataFrame:
    curve = _read_csv(OFFICIAL_CURVE_IN)
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    curve = curve.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    for column in [
        "account_equity",
        "drawdown_pct",
        "net_pnl",
        "slippage",
        "trade_count",
        "broker10_margin_to_equity_pct",
        "broker10_total_margin_exact",
    ]:
        curve[column] = pd.to_numeric(curve.get(column, 0.0), errors="coerce").fillna(0.0)
    prev_equity = curve["account_equity"].shift(1)
    prev_equity.iloc[0] = ACCOUNT_CAPITAL
    curve["daily_return"] = (curve["account_equity"] / prev_equity - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return curve


def _load_supply_signals() -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for source_window, path in [
        ("stage358_2020_2022", SIGNAL_2020_2022_IN),
        ("stage316_2023_2026", SIGNAL_2023_2026_IN),
    ]:
        signal = _read_csv(path)
        signal["signal_source_window"] = source_window
        frames.append(signal)
    out = pd.concat(frames, ignore_index=True)
    out["available_datetime"] = pd.to_datetime(out["available_datetime"], errors="coerce")
    out["product"] = out["product_vt_symbol"].fillna("").astype(str)
    out["direction"] = out["direction"].fillna("").astype(str).str.lower()
    out["external_quality_score"] = pd.to_numeric(out["external_quality_score"], errors="coerce")
    out["confidence"] = pd.to_numeric(out["confidence"], errors="coerce")
    out["suggested_volume_multiplier"] = pd.to_numeric(out["suggested_volume_multiplier"], errors="coerce")
    out["veto_flag"] = pd.to_numeric(out["veto_flag"], errors="coerce").fillna(0).astype(int)
    out = out[
        out["available_datetime"].notna()
        & out["product"].ne("")
        & out["direction"].isin(["long", "short"])
        & out["external_quality_score"].notna()
    ].copy()
    out = out.sort_values(["product", "direction", "available_datetime", "signal_source_window"])
    out = out.drop_duplicates(["product", "direction", "available_datetime", "source_type", "text_hash"], keep="last")
    out.to_csv(COMBINED_SIGNALS_OUT, index=False, encoding="utf-8-sig")
    return out.reset_index(drop=True)


def _normalize_lot_product(product: Any, vt_symbol: Any) -> str:
    product_text = "" if pd.isna(product) else str(product).strip()
    if "." in product_text:
        return product_text
    vt_text = "" if pd.isna(vt_symbol) else str(vt_symbol).strip()
    if "." not in vt_text:
        return product_text
    contract, exchange = vt_text.rsplit(".", 1)
    match = re.match(r"([A-Za-z]+)", contract)
    if not match:
        return product_text
    code = match.group(1)
    return f"{code}.{exchange}"


def _bind_supply_to_lots(lots: pd.DataFrame, signals: pd.DataFrame) -> pd.DataFrame:
    lots = lots.copy()
    lots["entry_date"] = pd.to_datetime(lots["entry_date"], errors="coerce").dt.normalize()
    lots["exit_date"] = pd.to_datetime(lots["exit_date"], errors="coerce").dt.normalize()
    lots["prev_state_date"] = pd.to_datetime(lots["prev_state_date"], errors="coerce").dt.normalize()
    lots["supply_lookup_datetime"] = lots["prev_state_date"].fillna(lots["entry_date"] - pd.Timedelta(days=1))
    lots["supply_lookup_datetime"] = lots["supply_lookup_datetime"] + pd.Timedelta(hours=23, minutes=59)
    lots["product_raw_stage027"] = lots["product"].fillna("").astype(str)
    lots["product"] = [
        _normalize_lot_product(product, vt_symbol)
        for product, vt_symbol in zip(lots["product_raw_stage027"], lots["vt_symbol"], strict=False)
    ]
    lots["direction"] = lots["direction"].fillna("").astype(str).str.lower()
    lots["_lot_order"] = np.arange(len(lots), dtype=int)

    bound_frames: list[pd.DataFrame] = []
    signal_cols = [
        "available_datetime",
        "source_type",
        "source_name",
        "external_quality_score",
        "suggested_volume_multiplier",
        "veto_flag",
        "confidence",
        "source_url",
        "text_hash",
        "notes",
        "signal_source_window",
    ]
    for (product, direction), product_lots in lots.groupby(["product", "direction"], sort=False):
        product_signals = signals[signals["product"].eq(product) & signals["direction"].eq(direction)].copy()
        left = product_lots.sort_values("supply_lookup_datetime").copy()
        if product_signals.empty:
            for column in signal_cols:
                left[f"supply_{column}"] = np.nan
            bound_frames.append(left)
            continue
        right = product_signals[signal_cols].sort_values("available_datetime").copy()
        merged = pd.merge_asof(
            left,
            right,
            left_on="supply_lookup_datetime",
            right_on="available_datetime",
            direction="backward",
            tolerance=pd.Timedelta(days=MAX_SIGNAL_AGE_DAYS),
        )
        rename = {column: f"supply_{column}" for column in signal_cols}
        merged = merged.rename(columns=rename)
        bound_frames.append(merged)

    out = pd.concat(bound_frames, ignore_index=True).sort_values("_lot_order").drop(columns=["_lot_order"])
    out["supply_signal_missing_stage027"] = out["supply_available_datetime"].isna()
    out["supply_signal_age_days"] = (
        out["supply_lookup_datetime"] - pd.to_datetime(out["supply_available_datetime"], errors="coerce")
    ).dt.total_seconds() / 86400.0
    score = pd.to_numeric(out["supply_external_quality_score"], errors="coerce")
    confidence = pd.to_numeric(out["supply_confidence"], errors="coerce")
    out["supply_score"] = score
    out["supply_confidence_score"] = confidence
    out["supply_score_confidence_weighted"] = score * confidence
    out["supply_bucket_stage027"] = "supply_missing"
    out.loc[score.ge(0.35), "supply_bucket_stage027"] = "supply_supportive"
    out.loc[score.le(-0.35), "supply_bucket_stage027"] = "supply_headwind"
    out.loc[score.gt(-0.35) & score.lt(0.35), "supply_bucket_stage027"] = "supply_neutral"

    out["supply_confidence_bucket_stage027"] = "supply_missing"
    out.loc[confidence.ge(0.70), "supply_confidence_bucket_stage027"] = "confidence_high"
    out.loc[confidence.ge(0.60) & confidence.lt(0.70), "supply_confidence_bucket_stage027"] = "confidence_mid"
    out.loc[confidence.lt(0.60), "supply_confidence_bucket_stage027"] = "confidence_low"

    out["supply_headwind_high_conf_stage027"] = "not_high_conf_headwind"
    out.loc[score.le(-0.35) & confidence.ge(0.70), "supply_headwind_high_conf_stage027"] = "high_conf_headwind"
    out.loc[out["supply_signal_missing_stage027"], "supply_headwind_high_conf_stage027"] = "supply_missing"
    return out


def _summarize_bucket(features: pd.DataFrame, bucket_column: str) -> pd.DataFrame:
    pnl_all = pd.to_numeric(features["realized_pnl"], errors="coerce").fillna(0.0)
    total_net = float(pnl_all.sum())
    total_pos = float(pnl_all.clip(lower=0.0).sum())
    total_neg_abs = abs(float(pnl_all.clip(upper=0.0).sum()))
    rows: list[dict[str, Any]] = []
    for bucket, group in features.groupby(bucket_column, dropna=False):
        pnl = pd.to_numeric(group["realized_pnl"], errors="coerce").fillna(0.0)
        pos = float(pnl.clip(lower=0.0).sum())
        neg = float(pnl.clip(upper=0.0).sum())
        rows.append(
            {
                "bucket_family": bucket_column,
                "bucket": str(bucket),
                "lot_count": int(len(group)),
                "product_count": int(group["product"].nunique()),
                "year_count": int(group["entry_year"].nunique()),
                "net_pnl": float(pnl.sum()),
                "positive_pnl": pos,
                "negative_pnl": neg,
                "net_pnl_share_pct": float(pnl.sum() / total_net * 100.0) if total_net else np.nan,
                "positive_coverage_pct": float(pos / total_pos * 100.0) if total_pos else np.nan,
                "negative_abs_coverage_pct": float(abs(neg) / total_neg_abs * 100.0) if total_neg_abs else np.nan,
                "win_rate_pct": float((pnl > 0.0).mean() * 100.0) if len(pnl) else np.nan,
                "median_r_multiple": float(pd.to_numeric(group["r_multiple"], errors="coerce").median()),
                "avg_supply_score": float(pd.to_numeric(group["supply_score"], errors="coerce").mean()),
                "avg_confidence": float(pd.to_numeric(group["supply_confidence_score"], errors="coerce").mean()),
                "missing_rate_pct": float(group["supply_signal_missing_stage027"].mean() * 100.0),
            }
        )
    return pd.DataFrame(rows).sort_values(["bucket_family", "net_pnl"], ascending=[True, False])


def _bucket_year_matrix(features: pd.DataFrame, bucket_column: str) -> pd.DataFrame:
    matrix = features.pivot_table(
        index=bucket_column,
        columns="entry_year",
        values="realized_pnl",
        aggfunc="sum",
        fill_value=0.0,
    ).sort_index()
    matrix.columns = [str(int(column)) for column in matrix.columns]
    return matrix.reset_index().rename(columns={bucket_column: "bucket"})


def _product_bucket_matrix(features: pd.DataFrame) -> pd.DataFrame:
    matrix = features.pivot_table(
        index="product",
        columns="supply_bucket_stage027",
        values="realized_pnl",
        aggfunc="sum",
        fill_value=0.0,
    ).sort_index()
    return matrix.reset_index()


def _build_daily_active_share(features: pd.DataFrame, official_curve: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for date in official_curve["date"]:
        active = features[(features["entry_date"] <= date) & (features["exit_date"] >= date)].copy()
        total = int(len(active))
        if total == 0:
            rows.append(
                {
                    "date": date,
                    "active_lot_count": 0,
                    "supply_supportive_share_pct": 0.0,
                    "supply_neutral_share_pct": 0.0,
                    "supply_headwind_share_pct": 0.0,
                    "supply_missing_share_pct": 0.0,
                    "active_avg_supply_score": np.nan,
                }
            )
            continue
        rows.append(
            {
                "date": date,
                "active_lot_count": total,
                "supply_supportive_share_pct": float(active["supply_bucket_stage027"].eq("supply_supportive").mean() * 100.0),
                "supply_neutral_share_pct": float(active["supply_bucket_stage027"].eq("supply_neutral").mean() * 100.0),
                "supply_headwind_share_pct": float(active["supply_bucket_stage027"].eq("supply_headwind").mean() * 100.0),
                "supply_missing_share_pct": float(active["supply_signal_missing_stage027"].mean() * 100.0),
                "active_avg_supply_score": float(pd.to_numeric(active["supply_score"], errors="coerce").mean()),
            }
        )
    return pd.DataFrame(rows)


def _official_metrics(official_curve: pd.DataFrame, features: pd.DataFrame) -> dict[str, float]:
    returns = pd.to_numeric(official_curve["daily_return"], errors="coerce").fillna(0.0)
    std = float(returns.std(ddof=1)) if len(returns) > 1 else 0.0
    sharpe = float(returns.mean() / std * np.sqrt(TRADING_DAYS_PER_YEAR)) if std > 0.0 else 0.0
    start = float(official_curve["account_equity"].iloc[0]) if not official_curve.empty else ACCOUNT_CAPITAL
    end = float(official_curve["account_equity"].iloc[-1]) if not official_curve.empty else ACCOUNT_CAPITAL
    return {
        "end_equity": end,
        "total_return_pct": (end / start - 1.0) * 100.0 if start else np.nan,
        "max_drawdown_pct": float(pd.to_numeric(official_curve["drawdown_pct"], errors="coerce").min()),
        "sharpe": sharpe,
        "total_slippage": float(pd.to_numeric(official_curve["slippage"], errors="coerce").fillna(0.0).sum()),
        "total_trade_count": float(pd.to_numeric(official_curve["trade_count"], errors="coerce").fillna(0.0).sum()),
        "closed_lot_win_rate_pct": float(
            (pd.to_numeric(features["realized_pnl"], errors="coerce").fillna(0.0) > 0.0).mean() * 100.0
        ),
        "closed_lot_count": float(len(features)),
    }


def _plot_path(official_curve: pd.DataFrame, daily_active: pd.DataFrame) -> None:
    merged = official_curve.merge(daily_active, on="date", how="left")
    fig, axes = plt.subplots(4, 1, figsize=(15, 12), sharex=True)
    axes[0].plot(merged["date"], merged["account_equity"], color="#1f77b4", linewidth=1.6)
    axes[0].set_title("Official C9/15w equity")
    axes[0].grid(True, alpha=0.25)
    axes[1].plot(merged["date"], merged["drawdown_pct"], color="#d62728", linewidth=1.1)
    axes[1].set_title("Official drawdown pct")
    axes[1].grid(True, alpha=0.25)
    axes[2].plot(merged["date"], merged["broker10_margin_to_equity_pct"], color="#9467bd", linewidth=1.1)
    axes[2].axhline(100.0, color="#555555", linestyle="--", linewidth=0.8)
    axes[2].set_title("Broker10 margin pressure")
    axes[2].grid(True, alpha=0.25)
    axes[3].plot(merged["date"], merged["supply_supportive_share_pct"], color="#2ca02c", linewidth=1.0, label="supportive")
    axes[3].plot(merged["date"], merged["supply_headwind_share_pct"], color="#ff7f0e", linewidth=1.0, label="headwind")
    axes[3].plot(merged["date"], merged["supply_missing_share_pct"], color="#7f7f7f", linewidth=0.9, label="missing")
    axes[3].set_title("Active lot supply-demand state share")
    axes[3].legend(loc="upper left", ncol=3, fontsize=8)
    axes[3].grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_contribution(features: pd.DataFrame) -> None:
    calendar = pd.date_range(features["exit_date"].min(), features["exit_date"].max(), freq="D")
    fig, ax = plt.subplots(figsize=(15, 7))
    all_daily = features.groupby("exit_date")["realized_pnl"].sum().reindex(calendar, fill_value=0.0).cumsum()
    ax.plot(calendar, all_daily, color="#1f77b4", linewidth=1.8, label="all closed lots")
    colors = {
        "supply_supportive": "#2ca02c",
        "supply_neutral": "#17becf",
        "supply_headwind": "#ff7f0e",
        "supply_missing": "#7f7f7f",
    }
    for bucket, color in colors.items():
        sub = features[features["supply_bucket_stage027"].eq(bucket)]
        if sub.empty:
            continue
        daily = sub.groupby("exit_date")["realized_pnl"].sum().reindex(calendar, fill_value=0.0).cumsum()
        ax.plot(calendar, daily, linewidth=1.25, label=bucket, color=color)
    ax.axhline(0.0, color="#555555", linewidth=0.8)
    ax.set_title("Closed-lot realized PnL contribution by supply-demand bucket")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="upper left")
    fig.tight_layout()
    fig.savefig(CONTRIBUTION_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_bucket_year_heatmap(matrix: pd.DataFrame) -> None:
    if matrix.empty:
        return
    data = matrix.set_index("bucket")
    values = data.to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=(13, max(4, 0.55 * len(data))))
    vmax = max(abs(np.nanmin(values)), abs(np.nanmax(values)), 1.0)
    image = ax.imshow(values, aspect="auto", cmap="RdYlGn", vmin=-vmax, vmax=vmax)
    ax.set_yticks(np.arange(len(data.index)))
    ax.set_yticklabels(data.index)
    ax.set_xticks(np.arange(len(data.columns)))
    ax.set_xticklabels(data.columns, rotation=45, ha="right")
    ax.set_title("Supply-demand bucket by entry year net PnL")
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            ax.text(j, i, f"{values[i, j] / 10000:.0f}w", ha="center", va="center", fontsize=8)
    fig.colorbar(image, ax=ax, fraction=0.025, pad=0.02)
    fig.tight_layout()
    fig.savefig(BUCKET_YEAR_HEATMAP_OUT, dpi=160)
    plt.close(fig)


def _plot_scatter(features: pd.DataFrame) -> None:
    valid = features[~features["supply_signal_missing_stage027"]].copy()
    if valid.empty:
        return
    pnl = pd.to_numeric(valid["realized_pnl"], errors="coerce").fillna(0.0)
    size = np.asarray(np.clip(np.abs(pnl) / max(np.nanpercentile(np.abs(pnl), 80), 1.0) * 25.0, 10.0, 90.0))
    color = np.asarray(np.where(pnl >= 0.0, "#2ca02c", "#d62728"))
    marker_map = {"long": "o", "short": "^"}
    fig, ax = plt.subplots(figsize=(11, 7))
    for direction, marker in marker_map.items():
        sub = valid[valid["direction"].eq(direction)]
        if sub.empty:
            continue
        positions = valid.index.get_indexer(sub.index)
        ax.scatter(
            sub["supply_score"],
            sub["supply_confidence_score"],
            s=size[positions],
            c=color[positions],
            alpha=0.62,
            marker=marker,
            label=direction,
            edgecolors="none",
        )
    ax.axvline(-0.35, color="#ff7f0e", linestyle="--", linewidth=0.9)
    ax.axvline(0.35, color="#2ca02c", linestyle="--", linewidth=0.9)
    ax.set_title("Entry pre-state supply-demand score vs confidence")
    ax.set_xlabel("external_quality_score aligned to C9 direction")
    ax.set_ylabel("signal confidence")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(SCATTER_OUT, dpi=160)
    plt.close(fig)


def _plot_product_heatmap(matrix: pd.DataFrame) -> None:
    if matrix.empty:
        return
    data = matrix.set_index("product")
    values = data.to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=(8, max(6, 0.35 * len(data))))
    vmax = max(abs(np.nanmin(values)), abs(np.nanmax(values)), 1.0)
    image = ax.imshow(values, aspect="auto", cmap="RdYlGn", vmin=-vmax, vmax=vmax)
    ax.set_yticks(np.arange(len(data.index)))
    ax.set_yticklabels(data.index)
    ax.set_xticks(np.arange(len(data.columns)))
    ax.set_xticklabels(data.columns, rotation=35, ha="right")
    ax.set_title("Product x supply-demand bucket net PnL")
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            ax.text(j, i, f"{values[i, j] / 10000:.0f}w", ha="center", va="center", fontsize=7)
    fig.colorbar(image, ax=ax, fraction=0.03, pad=0.02)
    fig.tight_layout()
    fig.savefig(PRODUCT_HEATMAP_OUT, dpi=160)
    plt.close(fig)


def _build_decision(
    features: pd.DataFrame,
    bucket_summary: pd.DataFrame,
    official_metrics: dict[str, float],
    signal_count: int,
) -> dict[str, Any]:
    lot_count = int(len(features))
    supply_ready_count = int((~features["supply_signal_missing_stage027"]).sum())
    bucket_rows = bucket_summary[bucket_summary["bucket_family"].eq("supply_bucket_stage027")]

    def row(bucket: str) -> dict[str, Any]:
        hit = bucket_rows[bucket_rows["bucket"].eq(bucket)]
        return hit.iloc[0].to_dict() if not hit.empty else {}

    supportive = row("supply_supportive")
    headwind = row("supply_headwind")
    neutral = row("supply_neutral")
    missing = row("supply_missing")

    candidate_like = []
    if headwind:
        if (
            float(headwind.get("net_pnl", 0.0)) < 0.0
            and float(headwind.get("negative_abs_coverage_pct", 0.0)) >= 25.0
            and float(headwind.get("positive_coverage_pct", 100.0)) <= 15.0
            and int(headwind.get("product_count", 0)) >= 8
            and int(headwind.get("year_count", 0)) >= 5
        ):
            candidate_like.append("supply_headwind")

    if supply_ready_count / lot_count < 0.55:
        decision = "stage027_supply_demand_no_candidate_coverage_too_low"
        reason = "Supply-demand signal coverage is too low for a promotable C9 rule."
    elif candidate_like:
        decision = "stage027_supply_demand_watch_only_requires_true_engine"
        reason = (
            "A broad negative headwind bucket exists in read-only attribution, but a promotable rule "
            "would require a frozen true engine, multi-start validation, and slippage stress."
        )
    else:
        decision = "stage027_supply_demand_no_candidate_nonmonotonic_or_right_tail_dominant"
        reason = (
            "Basis/warehouse supply-demand states do not isolate a broad stable loss bucket without "
            "also carrying meaningful positive/right-tail contribution."
        )

    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "decision": decision,
        "candidate_ready": 0,
        "ab_triggered": 0,
        "reason": reason,
        "lot_count": lot_count,
        "supply_signal_rows": int(signal_count),
        "supply_ready_count": supply_ready_count,
        "supply_ready_rate_pct": supply_ready_count / lot_count * 100.0 if lot_count else 0.0,
        "candidate_like_readonly_buckets": candidate_like,
        "supply_supportive": supportive,
        "supply_neutral": neutral,
        "supply_headwind": headwind,
        "supply_missing": missing,
        "official_metrics": official_metrics,
        "guardrails": {
            "point_in_time_binding": (
                "merge_asof backward by product and direction on prev_state_date end-of-day with max "
                f"{MAX_SIGNAL_AGE_DAYS} calendar days lag"
            ),
            "source": "Stage358 2020-2022 + Stage316 2023-2026 AKShare basis and warehouse receipt signals",
            "no_parameter_sweep": True,
            "no_trade_rule": True,
            "no_ctp_or_order_api": True,
            "missing_supply_state_keeps_official_path": True,
        },
        "outputs": {
            "features": str(FEATURES_OUT),
            "combined_signals": str(COMBINED_SIGNALS_OUT),
            "bucket_summary": str(BUCKET_SUMMARY_OUT),
            "bucket_year_matrix": str(BUCKET_YEAR_OUT),
            "product_bucket_matrix": str(PRODUCT_BUCKET_OUT),
            "daily_active_share": str(ACTIVE_SHARE_OUT),
            "report": str(REPORT_OUT),
            "path_chart": str(PATH_CHART_OUT),
            "contribution_chart": str(CONTRIBUTION_CHART_OUT),
            "bucket_year_heatmap": str(BUCKET_YEAR_HEATMAP_OUT),
            "scatter": str(SCATTER_OUT),
            "product_heatmap": str(PRODUCT_HEATMAP_OUT),
        },
    }


def _write_report(
    features: pd.DataFrame,
    bucket_summary: pd.DataFrame,
    bucket_year: pd.DataFrame,
    product_bucket: pd.DataFrame,
    official_metrics: dict[str, float],
    decision: dict[str, Any],
) -> None:
    supply_summary = bucket_summary[bucket_summary["bucket_family"].eq("supply_bucket_stage027")]
    confidence_summary = bucket_summary[bucket_summary["bucket_family"].eq("supply_confidence_bucket_stage027")]
    headwind_conf_summary = bucket_summary[
        bucket_summary["bucket_family"].eq("supply_headwind_high_conf_stage027")
    ]
    valid = features[~features["supply_signal_missing_stage027"]].copy()
    report = f"""# {STAGE} 供需/库存/仓单外生状态只读法证

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M')} CST
- 阶段性质：点时化外生供需状态只读归因；不修改正式配置、不连接 CTP、不调用下单。
- 是否重要突破：否
- 是否触发A/B：否
- 当前官方正式版：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`

## 外部调研与判断

- Gorton/Hayashi/Rouwenhorst 的库存理论实证显示，商品期货风险溢价会随实物库存状态变化，低库存、基差和动量信号之间存在经济联系。
- Hong/Yogo 的 open interest 研究说明持仓变化可含有宏观活动与资产价格未完全反映的信息，供需/持仓数据不应只看价格本身。
- AKShare/fushare/GitHub 生态已经把中国商品期货的注册仓单、基差、持仓排名等作为公开可取的日级基本面数据；同时文档明确提示仓单变化有季节性和交割日噪声。
- 我的判断：供需/库存/仓单是比历史亏损 cohort 更外生、更接近第一性原则的信息源，值得绑定到 C9 入场前状态做视觉审计；但 Stage359 曾证明“供需逆风硬过滤”会在旧正式线严重伤收益，所以本阶段只读，不写阈值交易规则。

## 回测/归因参数

- 官方 C9/15w closed-lot 区间：`{features['entry_date'].min().date()}` 至 `{features['exit_date'].max().date()}`。
- 外生信号：Stage358 `2020-2022` + Stage316 `2023-2026`，AKShare `futures_spot_price` 与交易所仓单接口构造的供需质量分。
- 点时化：仓单和基差信号按交易日 `20:00` 可见，只允许影响下一交易日及之后；本阶段按每笔 `prev_state_date` 日终向前绑定。
- 绑定口径：`product + direction`，向前 `merge_asof`，最大滞后 `{MAX_SIGNAL_AGE_DAYS}` 个自然日；不用未来信号。
- 固定分桶：`score >= 0.35` 为 supportive，`score <= -0.35` 为 headwind，其余 neutral；这是 Stage316 原始质量分的粗解释分桶，不做阈值扫描。
- 样本过滤：不删缺失样本；缺失单独归为 `supply_missing`。
- 策略口径：只读 closed-lot 归因和官方资金曲线视觉审计，不是交易引擎。

## 官方基准指标

- 期末权益：`{official_metrics['end_equity']:,.2f}`
- 总收益：`{official_metrics['total_return_pct']:.4f}%`
- 最大回撤：`{official_metrics['max_drawdown_pct']:.4f}%`
- Sharpe：`{official_metrics['sharpe']:.4f}`
- 总滑点：`{official_metrics['total_slippage']:,.0f}`
- 总交易次数：`{official_metrics['total_trade_count']:,.0f}`
- closed-lot 胜率：`{official_metrics['closed_lot_win_rate_pct']:.4f}%`

## 覆盖

- official closed lots：`{len(features)}`
- supply ready：`{decision['supply_ready_count']}`，覆盖率 `{decision['supply_ready_rate_pct']:.4f}%`
- 有效供需产品数：`{valid['product'].nunique() if not valid.empty else 0}`
- 有效供需年份数：`{valid['entry_year'].nunique() if not valid.empty else 0}`
- 外生信号行数：`{decision['supply_signal_rows']}`

## 供需分组

{_md_table(supply_summary)}

## 置信度分组

{_md_table(confidence_summary)}

## 高置信逆风分组

{_md_table(headwind_conf_summary)}

## 供需年度矩阵

{_md_table(bucket_year)}

## 产品-供需矩阵

{_md_table(product_bucket, max_rows=40)}

## 视觉观察

- path chart：`{PATH_CHART_OUT}`
  - 观察官方权益、回撤、broker10 与 active supply state share；如果 headwind share 不稳定领先深回撤，就不能作为闸门。
- contribution chart：`{CONTRIBUTION_CHART_OUT}`
  - 观察 supportive/neutral/headwind/missing 的 realized PnL 台阶；如果 headwind 也参与右尾，不能削仓。
- bucket-year heatmap：`{BUCKET_YEAR_HEATMAP_OUT}`
  - 观察供需 bucket 是否跨年单调；单一年份负贡献不构成普世规则。
- scatter：`{SCATTER_OUT}`
  - 观察供需质量分与置信度空间中盈亏点是否可分。
- product heatmap：`{PRODUCT_HEATMAP_OUT}`
  - 观察是否由少数产品块主导；若是，不能做产品/交易所补丁。

## 决策

```json
{json.dumps(_json_safe(decision), ensure_ascii=False, indent=2)}
```

## 过拟合反思

- 运行前判断：否。信息源来自外部库存/仓单/基差理论和公开日级数据，绑定只用入场前可见信号，不按亏损年份、品种、方向或具体交易调参。
- 运行后判断：以决策为准；若 headwind 桶不能稳定隔离亏损，继续扫分数阈值、组件权重、产品、方向或年份就是过拟合。

## 继续价值反思

- 运行前判断：有价值。此前内部分钟形态、账户层和粗 regime 多数被反证，直接供需/库存是少数仍符合第一性原则的外生路径。
- 运行后判断：以决策为准；若本阶段无候选，应停止库存/仓单粗质量分阈值分支，只保留为风险解释标签，下一步转向更细的官方仓单源覆盖、会员持仓结构或 forward watch。
"""
    REPORT_OUT.write_text(report, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    lots = _read_csv(FEATURES_IN)
    official_curve = _load_official_curve()
    signals = _load_supply_signals()

    features = _bind_supply_to_lots(lots, signals)
    bucket_summary = pd.concat(
        [
            _summarize_bucket(features, "supply_bucket_stage027"),
            _summarize_bucket(features, "supply_confidence_bucket_stage027"),
            _summarize_bucket(features, "supply_headwind_high_conf_stage027"),
        ],
        ignore_index=True,
    )
    bucket_year = _bucket_year_matrix(features, "supply_bucket_stage027")
    product_bucket = _product_bucket_matrix(features)
    daily_active = _build_daily_active_share(features, official_curve)
    official_metrics = _official_metrics(official_curve, features)
    decision = _build_decision(features, bucket_summary, official_metrics, len(signals))

    features.to_csv(FEATURES_OUT, index=False, encoding="utf-8-sig")
    bucket_summary.to_csv(BUCKET_SUMMARY_OUT, index=False, encoding="utf-8-sig")
    bucket_year.to_csv(BUCKET_YEAR_OUT, index=False, encoding="utf-8-sig")
    product_bucket.to_csv(PRODUCT_BUCKET_OUT, index=False, encoding="utf-8-sig")
    daily_active.to_csv(ACTIVE_SHARE_OUT, index=False, encoding="utf-8-sig")
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")

    _plot_path(official_curve, daily_active)
    _plot_contribution(features)
    _plot_bucket_year_heatmap(bucket_year)
    _plot_scatter(features)
    _plot_product_heatmap(product_bucket)
    _write_report(features, bucket_summary, bucket_year, product_bucket, official_metrics, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
