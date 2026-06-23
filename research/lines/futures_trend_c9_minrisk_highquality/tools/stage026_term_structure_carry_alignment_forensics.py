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
STAGE = "Stage026"
MODEL_TAG = "stage026_term_structure_carry_alignment_forensics_v1"
OUTPUT_PREFIX = "qmt_roll_stage026_c9_minrisk_term_structure_carry_alignment_forensics"
TRADING_DAYS_PER_YEAR = 252
ACCOUNT_CAPITAL = 150_000.0

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
if str(EXAMPLE_DIR) not in sys.path:
    sys.path.insert(0, str(EXAMPLE_DIR))

from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
STAGE024_DIR = LINE_DIR / "outputs" / "stage024_preentry_risk_granularity_forensics"
STAGE005_DIR = LINE_DIR / "outputs" / "stage005_signal_quality_visual_forensics"
OUTPUT_DIR = LINE_DIR / "outputs" / "stage026_term_structure_carry_alignment_forensics"
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
CURVE_FEATURES_IN = (
    BACKTEST_OUTPUT_DIR
    / "qmt_roll_stage368_curve_slope_dynamics_feasibility_curve_features_"
    "stage368_curve_slope_dynamics_feasibility_v1.csv"
)

FEATURES_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_features_{MODEL_TAG}.csv"
BUCKET_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_summary_{MODEL_TAG}.csv"
BUCKET_YEAR_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_year_matrix_{MODEL_TAG}.csv"
ACTIVE_SHARE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_active_share_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_path_carry_state_chart_{MODEL_TAG}.png"
CONTRIBUTION_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cohort_contribution_chart_{MODEL_TAG}.png"
BUCKET_YEAR_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_year_heatmap_{MODEL_TAG}.png"
SCATTER_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_carry_scatter_{MODEL_TAG}.png"
PRODUCT_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_carry_heatmap_{MODEL_TAG}.png"


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


def _direction_sign(series: pd.Series) -> pd.Series:
    direction = series.fillna("").astype(str).str.lower()
    return np.where(direction.eq("long"), 1.0, np.where(direction.eq("short"), -1.0, np.nan))


def _load_official_curve() -> pd.DataFrame:
    curve = _read_csv(OFFICIAL_CURVE_IN)
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    curve = curve.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    for column in [
        "account_equity",
        "drawdown_pct",
        "net_pnl",
        "total_slippage",
        "trade_count",
        "broker10_margin_to_equity_pct",
        "broker10_total_margin_exact",
    ]:
        curve[column] = pd.to_numeric(curve.get(column, 0.0), errors="coerce").fillna(0.0)
    prev_equity = curve["account_equity"].shift(1)
    prev_equity.iloc[0] = ACCOUNT_CAPITAL
    daily_return = curve["account_equity"] / prev_equity - 1.0
    curve["daily_return"] = daily_return.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return curve


def _load_curve_features() -> pd.DataFrame:
    curve = _read_csv(CURVE_FEATURES_IN)
    curve["curve_date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
    curve["product"] = curve["product_vt_symbol"].fillna("").astype(str)
    for column in [
        "curve_slope",
        "slope_change_20d",
        "signal",
        "near_close",
        "far_close",
        "near_oi",
        "far_oi",
        "month_gap",
        "candidate_count",
    ]:
        curve[column] = pd.to_numeric(curve.get(column, np.nan), errors="coerce")
    curve = curve.dropna(subset=["curve_date", "product", "curve_slope"]).copy()
    curve = curve[curve["product"].ne("")].copy()
    curve = curve.rename(columns={"signal": "curve_signal"})
    return curve.sort_values(["product", "curve_date"]).reset_index(drop=True)


def _bind_curve_to_lots(lots: pd.DataFrame, curve: pd.DataFrame) -> pd.DataFrame:
    lots = lots.copy()
    lots["entry_date"] = pd.to_datetime(lots["entry_date"], errors="coerce").dt.normalize()
    lots["exit_date"] = pd.to_datetime(lots["exit_date"], errors="coerce").dt.normalize()
    lots["prev_state_date"] = pd.to_datetime(lots["prev_state_date"], errors="coerce").dt.normalize()
    lots["curve_lookup_date"] = lots["prev_state_date"].fillna(lots["entry_date"] - pd.Timedelta(days=1))
    lots["product"] = lots["product"].fillna("").astype(str)
    lots["direction_sign"] = _direction_sign(lots["direction"])
    lots["_lot_order"] = np.arange(len(lots), dtype=int)

    bound_frames: list[pd.DataFrame] = []
    for product, product_lots in lots.groupby("product", sort=False):
        product_curve = curve[curve["product"].eq(product)].copy()
        left = product_lots.sort_values("curve_lookup_date").copy()
        if product_curve.empty:
            for column in [
                "curve_date",
                "near_contract",
                "far_contract",
                "near_close",
                "far_close",
                "curve_slope",
                "slope_change_20d",
                "curve_signal",
                "month_gap",
                "candidate_count",
                "near_oi",
                "far_oi",
            ]:
                left[column] = np.nan
            bound_frames.append(left)
            continue
        right = product_curve[
            [
                "curve_date",
                "product",
                "near_contract",
                "far_contract",
                "near_close",
                "far_close",
                "curve_slope",
                "slope_change_20d",
                "curve_signal",
                "month_gap",
                "candidate_count",
                "near_oi",
                "far_oi",
            ]
        ].sort_values("curve_date")
        merged = pd.merge_asof(
            left,
            right,
            left_on="curve_lookup_date",
            right_on="curve_date",
            by="product",
            direction="backward",
            tolerance=pd.Timedelta(days=7),
        )
        bound_frames.append(merged)

    out = pd.concat(bound_frames, ignore_index=True).sort_values("_lot_order").drop(columns=["_lot_order"])
    out["curve_state_lag_days"] = (out["curve_lookup_date"] - out["curve_date"]).dt.days
    out["curve_state_missing_stage026"] = out["curve_date"].isna()
    out["static_carry_score"] = -out["direction_sign"] * pd.to_numeric(out["curve_slope"], errors="coerce")
    out["dynamic_signal_alignment"] = out["direction_sign"] * pd.to_numeric(out["curve_signal"], errors="coerce")
    out["slope_change_alignment_score"] = -out["direction_sign"] * pd.to_numeric(
        out["slope_change_20d"], errors="coerce"
    )

    out["static_carry_bucket_stage026"] = "curve_missing"
    out.loc[out["static_carry_score"].gt(0.0), "static_carry_bucket_stage026"] = "static_carry_aligned"
    out.loc[out["static_carry_score"].lt(0.0), "static_carry_bucket_stage026"] = "static_carry_adverse"
    out.loc[out["static_carry_score"].eq(0.0), "static_carry_bucket_stage026"] = "static_carry_flat"

    out["dynamic_carry_bucket_stage026"] = "curve_missing"
    out.loc[out["dynamic_signal_alignment"].gt(0.0), "dynamic_carry_bucket_stage026"] = "dynamic_aligned"
    out.loc[out["dynamic_signal_alignment"].lt(0.0), "dynamic_carry_bucket_stage026"] = "dynamic_adverse"
    out.loc[out["dynamic_signal_alignment"].eq(0.0), "dynamic_carry_bucket_stage026"] = "dynamic_flat"

    out["carry_combo_bucket_stage026"] = "curve_missing"
    valid = ~out["curve_state_missing_stage026"]
    static_aligned = out["static_carry_bucket_stage026"].eq("static_carry_aligned")
    static_adverse = out["static_carry_bucket_stage026"].eq("static_carry_adverse")
    dynamic_aligned = out["dynamic_carry_bucket_stage026"].eq("dynamic_aligned")
    dynamic_adverse = out["dynamic_carry_bucket_stage026"].eq("dynamic_adverse")
    out.loc[valid & static_aligned & dynamic_aligned, "carry_combo_bucket_stage026"] = "static_dynamic_aligned"
    out.loc[valid & static_aligned & dynamic_adverse, "carry_combo_bucket_stage026"] = (
        "static_aligned_dynamic_adverse"
    )
    out.loc[valid & static_adverse & dynamic_aligned, "carry_combo_bucket_stage026"] = (
        "static_adverse_dynamic_aligned"
    )
    out.loc[valid & static_adverse & dynamic_adverse, "carry_combo_bucket_stage026"] = "static_dynamic_adverse"
    out.loc[
        valid & out["carry_combo_bucket_stage026"].eq("curve_missing"), "carry_combo_bucket_stage026"
    ] = "mixed_or_flat"
    return out


def _summarize_bucket(features: pd.DataFrame, bucket_column: str) -> pd.DataFrame:
    total_net = float(pd.to_numeric(features["realized_pnl"], errors="coerce").fillna(0.0).sum())
    total_pos = float(features["realized_pnl"].clip(lower=0.0).sum())
    total_neg_abs = abs(float(features["realized_pnl"].clip(upper=0.0).sum()))
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
                "avg_static_carry_score": float(pd.to_numeric(group["static_carry_score"], errors="coerce").mean()),
                "avg_slope_change_alignment_score": float(
                    pd.to_numeric(group["slope_change_alignment_score"], errors="coerce").mean()
                ),
                "curve_missing_rate_pct": float(group["curve_state_missing_stage026"].mean() * 100.0),
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
    )
    matrix = matrix.sort_index()
    matrix.columns = [str(int(column)) for column in matrix.columns]
    return matrix.reset_index().rename(columns={bucket_column: "bucket"})


def _build_daily_active_share(features: pd.DataFrame, official_curve: pd.DataFrame) -> pd.DataFrame:
    dates = official_curve[["date"]].copy()
    rows: list[dict[str, Any]] = []
    for row in dates.itertuples(index=False):
        date = pd.Timestamp(row.date)
        active = features[(features["entry_date"] <= date) & (features["exit_date"] >= date)].copy()
        total = int(len(active))
        if total == 0:
            rows.append(
                {
                    "date": date,
                    "active_lot_count": 0,
                    "static_aligned_share_pct": 0.0,
                    "static_adverse_share_pct": 0.0,
                    "dynamic_aligned_share_pct": 0.0,
                    "dynamic_adverse_share_pct": 0.0,
                    "curve_missing_share_pct": 0.0,
                }
            )
            continue
        rows.append(
            {
                "date": date,
                "active_lot_count": total,
                "static_aligned_share_pct": float(
                    active["static_carry_bucket_stage026"].eq("static_carry_aligned").mean() * 100.0
                ),
                "static_adverse_share_pct": float(
                    active["static_carry_bucket_stage026"].eq("static_carry_adverse").mean() * 100.0
                ),
                "dynamic_aligned_share_pct": float(
                    active["dynamic_carry_bucket_stage026"].eq("dynamic_aligned").mean() * 100.0
                ),
                "dynamic_adverse_share_pct": float(
                    active["dynamic_carry_bucket_stage026"].eq("dynamic_adverse").mean() * 100.0
                ),
                "curve_missing_share_pct": float(active["curve_state_missing_stage026"].mean() * 100.0),
            }
        )
    return pd.DataFrame(rows)


def _official_metrics(official_curve: pd.DataFrame, features: pd.DataFrame) -> dict[str, float]:
    returns = pd.to_numeric(official_curve["daily_return"], errors="coerce").fillna(0.0)
    std = float(returns.std(ddof=1)) if len(returns) > 1 else 0.0
    sharpe = float(returns.mean() / std * np.sqrt(TRADING_DAYS_PER_YEAR)) if std > 0.0 else 0.0
    start = float(official_curve["account_equity"].iloc[0]) if not official_curve.empty else ACCOUNT_CAPITAL
    end = float(official_curve["account_equity"].iloc[-1]) if not official_curve.empty else ACCOUNT_CAPITAL
    trade_count = float(pd.to_numeric(official_curve["trade_count"], errors="coerce").fillna(0.0).sum())
    total_slippage = float(pd.to_numeric(official_curve["slippage"], errors="coerce").fillna(0.0).sum())
    return {
        "end_equity": end,
        "total_return_pct": (end / start - 1.0) * 100.0 if start else np.nan,
        "max_drawdown_pct": float(pd.to_numeric(official_curve["drawdown_pct"], errors="coerce").min()),
        "sharpe": sharpe,
        "total_slippage": total_slippage,
        "total_trade_count": trade_count,
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
    axes[2].plot(
        merged["date"],
        merged["broker10_margin_to_equity_pct"],
        color="#9467bd",
        linewidth=1.1,
        label="broker10 margin/equity",
    )
    axes[2].axhline(100.0, color="#555555", linestyle="--", linewidth=0.8)
    axes[2].set_title("Broker10 margin pressure")
    axes[2].grid(True, alpha=0.25)
    axes[3].plot(
        merged["date"],
        merged["static_aligned_share_pct"],
        color="#2ca02c",
        linewidth=1.0,
        label="static aligned active share",
    )
    axes[3].plot(
        merged["date"],
        merged["static_adverse_share_pct"],
        color="#ff7f0e",
        linewidth=1.0,
        label="static adverse active share",
    )
    axes[3].plot(
        merged["date"],
        merged["curve_missing_share_pct"],
        color="#7f7f7f",
        linewidth=0.9,
        label="curve missing active share",
    )
    axes[3].set_title("Active lot carry-state share")
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
        "static_carry_aligned": "#2ca02c",
        "static_carry_adverse": "#ff7f0e",
        "static_carry_flat": "#17becf",
        "curve_missing": "#7f7f7f",
    }
    for bucket, color in colors.items():
        sub = features[features["static_carry_bucket_stage026"].eq(bucket)]
        if sub.empty:
            continue
        daily = sub.groupby("exit_date")["realized_pnl"].sum().reindex(calendar, fill_value=0.0).cumsum()
        ax.plot(calendar, daily, linewidth=1.25, label=bucket, color=color)
    ax.axhline(0.0, color="#555555", linewidth=0.8)
    ax.set_title("Closed-lot realized PnL contribution by static carry bucket")
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
    ax.set_title("Static carry bucket by entry year net PnL")
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            ax.text(j, i, f"{values[i, j] / 10000:.0f}w", ha="center", va="center", fontsize=8)
    fig.colorbar(image, ax=ax, fraction=0.025, pad=0.02)
    fig.tight_layout()
    fig.savefig(BUCKET_YEAR_HEATMAP_OUT, dpi=160)
    plt.close(fig)


def _plot_scatter(features: pd.DataFrame) -> None:
    valid = features[~features["curve_state_missing_stage026"]].copy()
    if valid.empty:
        return
    pnl = pd.to_numeric(valid["realized_pnl"], errors="coerce").fillna(0.0)
    size = np.asarray(
        np.clip(np.abs(pnl) / max(np.nanpercentile(np.abs(pnl), 80), 1.0) * 25.0, 10.0, 90.0)
    )
    color = np.asarray(np.where(pnl >= 0.0, "#2ca02c", "#d62728"))
    marker_map = {"long": "o", "short": "^"}
    fig, ax = plt.subplots(figsize=(11, 7))
    for direction, marker in marker_map.items():
        sub = valid[valid["direction"].astype(str).str.lower().eq(direction)]
        if sub.empty:
            continue
        idx = sub.index
        positions = valid.index.get_indexer(idx)
        ax.scatter(
            sub["curve_slope"],
            sub["slope_change_20d"],
            s=size[positions],
            c=color[positions],
            alpha=0.62,
            marker=marker,
            label=direction,
            edgecolors="none",
        )
    ax.axhline(0.0, color="#555555", linewidth=0.8)
    ax.axvline(0.0, color="#555555", linewidth=0.8)
    ax.set_title("Entry pre-state curve slope vs 20d slope change")
    ax.set_xlabel("curve_slope = log(far/near)/month_gap")
    ax.set_ylabel("slope_change_20d")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(SCATTER_OUT, dpi=160)
    plt.close(fig)


def _plot_product_heatmap(features: pd.DataFrame) -> None:
    valid = features[~features["curve_state_missing_stage026"]].copy()
    if valid.empty:
        return
    matrix = valid.pivot_table(
        index="product",
        columns="static_carry_bucket_stage026",
        values="realized_pnl",
        aggfunc="sum",
        fill_value=0.0,
    ).sort_index()
    values = matrix.to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=(8, max(6, 0.35 * len(matrix))))
    vmax = max(abs(np.nanmin(values)), abs(np.nanmax(values)), 1.0)
    image = ax.imshow(values, aspect="auto", cmap="RdYlGn", vmin=-vmax, vmax=vmax)
    ax.set_yticks(np.arange(len(matrix.index)))
    ax.set_yticklabels(matrix.index)
    ax.set_xticks(np.arange(len(matrix.columns)))
    ax.set_xticklabels(matrix.columns, rotation=35, ha="right")
    ax.set_title("Product x static carry bucket net PnL")
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
) -> dict[str, Any]:
    lot_count = int(len(features))
    curve_ready_count = int((~features["curve_state_missing_stage026"]).sum())
    static_summary = bucket_summary[bucket_summary["bucket_family"].eq("static_carry_bucket_stage026")]
    dynamic_summary = bucket_summary[bucket_summary["bucket_family"].eq("dynamic_carry_bucket_stage026")]
    combo_summary = bucket_summary[bucket_summary["bucket_family"].eq("carry_combo_bucket_stage026")]

    def bucket_row(summary: pd.DataFrame, bucket: str) -> dict[str, Any]:
        row = summary[summary["bucket"].eq(bucket)]
        return row.iloc[0].to_dict() if not row.empty else {}

    static_adverse = bucket_row(static_summary, "static_carry_adverse")
    dynamic_adverse = bucket_row(dynamic_summary, "dynamic_adverse")
    combo_adverse = bucket_row(combo_summary, "static_dynamic_adverse")

    candidate_like = []
    for name, row in [
        ("static_carry_adverse", static_adverse),
        ("dynamic_adverse", dynamic_adverse),
        ("static_dynamic_adverse", combo_adverse),
    ]:
        if not row:
            continue
        if (
            float(row.get("net_pnl", 0.0)) < 0.0
            and float(row.get("negative_abs_coverage_pct", 0.0)) >= 25.0
            and float(row.get("positive_coverage_pct", 100.0)) <= 15.0
            and int(row.get("product_count", 0)) >= 8
            and int(row.get("year_count", 0)) >= 5
        ):
            candidate_like.append(name)

    if curve_ready_count / lot_count < 0.65:
        decision = "stage026_term_structure_no_candidate_coverage_too_low"
        reason = "Curve state coverage is too low for a promotable C9 rule."
    elif candidate_like:
        decision = "stage026_term_structure_watch_only_requires_true_engine"
        reason = (
            "At least one adverse carry bucket is negative, but this stage is read-only attribution; "
            "a promotable rule would require a frozen true engine and multi-start validation."
        )
    else:
        decision = "stage026_term_structure_no_candidate_nonmonotonic_or_right_tail_dominant"
        reason = (
            "Static/dynamic carry adverse states do not isolate a broad, stable loss bucket without "
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
        "curve_ready_count": curve_ready_count,
        "curve_ready_rate_pct": curve_ready_count / lot_count * 100.0 if lot_count else 0.0,
        "candidate_like_readonly_buckets": candidate_like,
        "static_carry_adverse": static_adverse,
        "dynamic_adverse": dynamic_adverse,
        "static_dynamic_adverse": combo_adverse,
        "official_metrics": official_metrics,
        "guardrails": {
            "point_in_time_binding": "merge_asof backward by product on prev_state_date with max 7 calendar days lag",
            "no_parameter_sweep": True,
            "no_trade_rule": True,
            "no_ctp_or_order_api": True,
            "missing_curve_state_keeps_official_path": True,
        },
        "outputs": {
            "features": str(FEATURES_OUT),
            "bucket_summary": str(BUCKET_SUMMARY_OUT),
            "bucket_year_matrix": str(BUCKET_YEAR_OUT),
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
    official_metrics: dict[str, float],
    decision: dict[str, Any],
) -> None:
    static_summary = bucket_summary[bucket_summary["bucket_family"].eq("static_carry_bucket_stage026")]
    dynamic_summary = bucket_summary[bucket_summary["bucket_family"].eq("dynamic_carry_bucket_stage026")]
    combo_summary = bucket_summary[bucket_summary["bucket_family"].eq("carry_combo_bucket_stage026")]
    valid = features[~features["curve_state_missing_stage026"]].copy()
    report = f"""# {STAGE} 期限结构 carry 对齐只读法证

- line_id：`{LINE_ID}`
- 当前模式：day
- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M')} CST
- 阶段性质：点时化外生期限结构状态只读归因；不修改正式配置、不连接 CTP、不调用下单。
- 是否重要突破：否
- 是否触发A/B：否
- 当前官方正式版：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`

## 外部调研与判断

- Koijen/Moskowitz/Pedersen/Vrugt 的 carry 研究把 carry 定义为可提前观察的收益特征，并指出 carry 对跨资产和商品期货有预测信息，但也承认 carry 暴露会在流动性、波动率和宏观压力期承受损失。
- Moskowitz/Ooi/Pedersen 的 time-series momentum 研究表明趋势跟随跨资产稳健，且期货收益可拆成价格变化与 roll return/曲线形态相关部分。
- `pysystemtrade` 是公开的系统化期货研究/交易框架，说明把趋势、carry、风险和成本分层建模是成熟工程路径。
- 我的判断：期限结构是比亏损 cohort、年份、品种更外生的候选信息源，值得审计；但已有 Stage368/419 历史结果显示 basis/carry 卫星不一定能独立晋级，所以本阶段只做 C9 入场前对齐归因，不直接写规则。

## 回测/归因参数

- 数据区间：官方 C9/15w 曲线 `{features['entry_date'].min().date()}` 至 `{features['exit_date'].max().date()}`；期限结构特征来自 Stage368 合约日线曲线文件。
- 绑定口径：每笔 official closed lot 使用 `prev_state_date`，按产品向前 `merge_asof`，最大允许滞后 `7` 个自然日；不用未来曲线。
- 静态 carry：`curve_slope = log(far/near)/month_gap`；long 在 backwardation（slope<0）视为 carry 对齐，short 在 contango（slope>0）视为 carry 对齐。
- 动态 carry：沿用 Stage368 固定 `20` 日曲线斜率变化信号；方向与 C9 入场方向一致视为 dynamic aligned。
- 样本过滤：不删缺失样本；缺失单独归为 `curve_missing`。
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
- curve ready：`{decision['curve_ready_count']}`，覆盖率 `{decision['curve_ready_rate_pct']:.4f}%`
- 有效曲线产品数：`{valid['product'].nunique() if not valid.empty else 0}`
- 有效曲线年份数：`{valid['entry_year'].nunique() if not valid.empty else 0}`

## 静态 carry 分组

{_md_table(static_summary)}

## 动态 carry 分组

{_md_table(dynamic_summary)}

## 静态/动态交叉分组

{_md_table(combo_summary)}

## 静态 carry 年度矩阵

{_md_table(bucket_year)}

## 视觉观察

- path chart：`{PATH_CHART_OUT}`
  - 观察官方权益、回撤、broker10 与 active carry-state share；如果 static adverse share 在深回撤前后不稳定领先，就不能当作闸门。
- contribution chart：`{CONTRIBUTION_CHART_OUT}`
  - 观察 static aligned/adverse/missing 的 realized PnL 台阶；如果 adverse 也参与右尾，不能削仓。
- bucket-year heatmap：`{BUCKET_YEAR_HEATMAP_OUT}`
  - 观察 carry bucket 是否跨年单调；单一年份负贡献不构成普世规则。
- scatter：`{SCATTER_OUT}`
  - 观察曲线斜率与斜率变化空间中盈亏点是否可分。
- product heatmap：`{PRODUCT_HEATMAP_OUT}`
  - 观察是否由少数产品块主导；若是，不能做产品/交易所补丁。

## 决策

```json
{json.dumps(_json_safe(decision), ensure_ascii=False, indent=2)}
```

## 过拟合反思

- 运行前判断：否。规则来自外部 carry/term-structure 文献和点时化曲线状态，只用入场前可见信息，且不扫阈值、不按亏损年份/品种回推。
- 运行后判断：以决策为准；若 adversarial bucket 不稳定或覆盖不足，继续扫 slope 阈值、lookback、品种、方向就是过拟合。

## 继续价值反思

- 运行前判断：有价值。原因是 Stage025 排除了粗广度状态，期限结构属于更具体的外生风险/收益源。
- 运行后判断：以决策为准；若本阶段无候选，保留为风险解释标签，下一步应转向更直接的供需/库存/仓单/持仓结构或暂停历史内反推。
"""
    REPORT_OUT.write_text(report, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    features_in = _read_csv(FEATURES_IN)
    official_curve = _load_official_curve()
    curve_features = _load_curve_features()

    features = _bind_curve_to_lots(features_in, curve_features)
    bucket_summary = pd.concat(
        [
            _summarize_bucket(features, "static_carry_bucket_stage026"),
            _summarize_bucket(features, "dynamic_carry_bucket_stage026"),
            _summarize_bucket(features, "carry_combo_bucket_stage026"),
        ],
        ignore_index=True,
    )
    bucket_year = _bucket_year_matrix(features, "static_carry_bucket_stage026")
    daily_active = _build_daily_active_share(features, official_curve)
    official_metrics = _official_metrics(official_curve, features)
    decision = _build_decision(features, bucket_summary, official_metrics)

    features.to_csv(FEATURES_OUT, index=False, encoding="utf-8-sig")
    bucket_summary.to_csv(BUCKET_SUMMARY_OUT, index=False, encoding="utf-8-sig")
    bucket_year.to_csv(BUCKET_YEAR_OUT, index=False, encoding="utf-8-sig")
    daily_active.to_csv(ACTIVE_SHARE_OUT, index=False, encoding="utf-8-sig")
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")

    _plot_path(official_curve, daily_active)
    _plot_contribution(features)
    _plot_bucket_year_heatmap(bucket_year)
    _plot_scatter(features)
    _plot_product_heatmap(features)
    _write_report(features, bucket_summary, bucket_year, official_metrics, decision)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
