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
STAGE = "Stage047"
MODEL_TAG = "stage047_vol_participation_joint_state_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage047_c9_minrisk_vol_participation_joint_state_audit"

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
if str(EXAMPLE_DIR) not in sys.path:
    sys.path.insert(0, str(EXAMPLE_DIR))

from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage047_vol_participation_joint_state_audit"

STAGE025_DIR = LINE_DIR / "outputs" / "stage025_market_divergence_breadth_forensics"
STAGE046_DIR = LINE_DIR / "outputs" / "stage046_entry_day_confirmed_breakeven_true_engine"

FEATURES_IN = (
    STAGE025_DIR
    / "qmt_roll_stage025_c9_minrisk_market_divergence_breadth_forensics_features_"
    "stage025_market_divergence_breadth_forensics_v1.csv"
)
MARKET_DAILY_IN = (
    STAGE025_DIR
    / "qmt_roll_stage025_c9_minrisk_market_divergence_breadth_forensics_market_state_daily_"
    "stage025_market_divergence_breadth_forensics_v1.csv"
)
OFFICIAL_CURVE_IN = (
    STAGE046_DIR
    / "qmt_roll_stage046_c9_minrisk_entry_day_confirmed_breakeven_true_engine_curve_"
    "stage046_entry_day_confirmed_breakeven_true_engine_v1.csv"
)

FEATURES_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_features_{MODEL_TAG}.csv"
COHORT_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cohort_summary_{MODEL_TAG}.csv"
YEAR_MATRIX_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_year_matrix_{MODEL_TAG}.csv"
PRODUCT_MATRIX_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_product_matrix_{MODEL_TAG}.csv"
COHORT_CURVES_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cohort_curves_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
PATH_STATE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_official_path_state_chart_{MODEL_TAG}.png"
COHORT_CURVE_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cohort_curve_chart_{MODEL_TAG}.png"
YEAR_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_year_heatmap_{MODEL_TAG}.png"
STATE_SCATTER_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_state_scatter_{MODEL_TAG}.png"
PRODUCT_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_product_heatmap_{MODEL_TAG}.png"


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


def _read_required_csv(path: Path) -> pd.DataFrame:
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


def _official_curve() -> pd.DataFrame:
    curve = _read_required_csv(OFFICIAL_CURVE_IN)
    curve["date"] = pd.to_datetime(curve["date"], errors="coerce")
    curve = curve[curve["arm"].eq("A_official_stage847_c9_15w")].copy()
    curve = curve.sort_values("date").reset_index(drop=True)
    if curve.empty:
        raise RuntimeError("official curve arm is empty")
    return curve


def _official_metrics(curve: pd.DataFrame) -> dict[str, float]:
    equity = curve["account_equity"].astype(float)
    returns = equity.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    sharpe = float(returns.mean() / returns.std(ddof=0) * np.sqrt(252.0)) if returns.std(ddof=0) > 0 else np.nan
    nonzero = curve[curve["net_pnl"].ne(0)]
    win_rate = float((nonzero["net_pnl"] > 0).mean() * 100.0) if len(nonzero) else np.nan
    return {
        "end_equity": float(equity.iloc[-1]),
        "total_return_pct": float((equity.iloc[-1] / 150_000.0 - 1.0) * 100.0),
        "max_dd_pct": float(curve["drawdown_pct"].min()),
        "sharpe": sharpe,
        "total_slippage": float(curve["slippage"].sum()),
        "total_trade_count": float(curve["trade_count"].sum()),
        "win_rate_pct": win_rate,
        "max_broker10_margin_to_equity_pct": float(curve["broker10_margin_to_equity_pct"].max()),
        "days_over_100pct": float((curve["broker10_margin_to_equity_pct"] > 100.0).sum()),
    }


def _vol_bucket(value: Any) -> str:
    if pd.isna(value):
        return "vol_missing"
    value = float(value)
    if value < 50.0:
        return "vol_low_lt50"
    if value < 100.0:
        return "vol_mid_50_100"
    return "vol_high_ge100"


def _participation_bucket(value: Any, missing: bool) -> str:
    if missing or pd.isna(value):
        return "part_missing"
    value = float(value)
    if value < 25.0:
        return "part_low_lt25"
    if value < 50.0:
        return "part_mid_25_50"
    return "part_high_ge50"


def _same_dir_corr_bucket(corr: Any, active_count: Any) -> str:
    active = 0.0 if pd.isna(active_count) else float(active_count)
    if active <= 0:
        return "corr_no_active"
    if pd.isna(corr):
        return "corr_missing_active"
    corr = float(corr)
    if corr < 0.60:
        return "corr_low_lt60"
    if corr < 0.80:
        return "corr_mid_60_80"
    return "corr_high_ge80"


def _vol_part_joint(vol_bucket: str, part_bucket: str) -> str:
    if part_bucket == "part_missing" or vol_bucket == "vol_missing":
        return "joint_missing"
    if vol_bucket == "vol_high_ge100" and part_bucket == "part_high_ge50":
        return "joint_high_vol_high_participation"
    if vol_bucket == "vol_high_ge100" and part_bucket == "part_low_lt25":
        return "joint_high_vol_low_participation"
    if vol_bucket == "vol_low_lt50" and part_bucket == "part_high_ge50":
        return "joint_low_vol_high_participation"
    if vol_bucket == "vol_low_lt50" and part_bucket == "part_low_lt25":
        return "joint_low_vol_low_participation"
    if vol_bucket == "vol_mid_50_100" and part_bucket == "part_mid_25_50":
        return "joint_mid_vol_mid_participation"
    return "joint_mixed_vol_participation"


def _vol_corr_joint(vol_bucket: str, corr_bucket: str) -> str:
    if vol_bucket == "vol_missing" or corr_bucket == "corr_missing_active":
        return "joint_corr_missing"
    high_corr = corr_bucket in {"corr_mid_60_80", "corr_high_ge80"}
    if vol_bucket == "vol_high_ge100" and high_corr:
        return "joint_high_vol_high_same_dir_corr"
    if vol_bucket == "vol_high_ge100" and not high_corr:
        return "joint_high_vol_low_same_dir_corr"
    if vol_bucket == "vol_low_lt50" and high_corr:
        return "joint_low_vol_high_same_dir_corr"
    if vol_bucket == "vol_low_lt50" and not high_corr:
        return "joint_low_vol_low_same_dir_corr"
    return "joint_mid_vol_corr_mixed"


def _joint_three_way(vol_bucket: str, part_bucket: str, corr_bucket: str) -> str:
    if vol_bucket == "vol_missing" or part_bucket == "part_missing":
        return "three_way_missing"
    high_corr = corr_bucket in {"corr_mid_60_80", "corr_high_ge80"}
    high_part = part_bucket == "part_high_ge50"
    low_part = part_bucket == "part_low_lt25"
    if vol_bucket == "vol_high_ge100" and low_part and high_corr:
        return "three_way_high_vol_low_part_high_corr"
    if vol_bucket == "vol_high_ge100" and high_part and high_corr:
        return "three_way_high_vol_high_part_high_corr"
    if vol_bucket == "vol_high_ge100" and low_part and not high_corr:
        return "three_way_high_vol_low_part_low_corr"
    if vol_bucket == "vol_low_lt50" and high_part and high_corr:
        return "three_way_low_vol_high_part_high_corr"
    return "three_way_other"


def _prepare_features() -> pd.DataFrame:
    features = _read_required_csv(FEATURES_IN)
    features["entry_date"] = pd.to_datetime(features["entry_date"], errors="coerce")
    features["exit_date"] = pd.to_datetime(features["exit_date"], errors="coerce")
    features["exit_day"] = pd.to_datetime(features.get("exit_day", features["exit_date"]), errors="coerce")
    features["entry_year"] = features["entry_date"].dt.year.astype("Int64")
    features["realized_pnl"] = pd.to_numeric(features["realized_pnl"], errors="coerce").fillna(0.0)
    features["positive_pnl"] = features["realized_pnl"].clip(lower=0.0)
    features["negative_pnl_abs"] = (-features["realized_pnl"].clip(upper=0.0))
    features["market_state_missing_stage025"] = features["market_state_missing_stage025"].fillna(False).astype(bool)

    features["stage047_vol_bucket"] = features["prev_rolling20_ann_vol_pct"].map(_vol_bucket)
    features["stage047_participation_bucket"] = [
        _participation_bucket(value, missing)
        for value, missing in zip(
            features["trend_participation_pct"],
            features["market_state_missing_stage025"],
        )
    ]
    features["stage047_same_dir_corr_bucket"] = [
        _same_dir_corr_bucket(corr, active)
        for corr, active in zip(
            features["same_direction_correlation_max_corr"],
            features["same_direction_correlation_active_count"],
        )
    ]
    features["stage047_vol_part_joint"] = [
        _vol_part_joint(vol_bucket, part_bucket)
        for vol_bucket, part_bucket in zip(features["stage047_vol_bucket"], features["stage047_participation_bucket"])
    ]
    features["stage047_vol_corr_joint"] = [
        _vol_corr_joint(vol_bucket, corr_bucket)
        for vol_bucket, corr_bucket in zip(features["stage047_vol_bucket"], features["stage047_same_dir_corr_bucket"])
    ]
    features["stage047_three_way_joint"] = [
        _joint_three_way(vol_bucket, part_bucket, corr_bucket)
        for vol_bucket, part_bucket, corr_bucket in zip(
            features["stage047_vol_bucket"],
            features["stage047_participation_bucket"],
            features["stage047_same_dir_corr_bucket"],
        )
    ]
    return features


def _cohort_summary(features: pd.DataFrame, family: str, column: str) -> pd.DataFrame:
    total_positive = float(features["positive_pnl"].sum())
    total_negative = float(features["negative_pnl_abs"].sum())
    rows: list[dict[str, Any]] = []
    for bucket, group in features.groupby(column, dropna=False):
        year_pnl = group.groupby("entry_year")["realized_pnl"].sum()
        rows.append(
            {
                "bucket_family": family,
                "bucket": str(bucket),
                "lot_count": int(len(group)),
                "product_count": int(group["product"].nunique()),
                "year_count": int(group["entry_year"].nunique()),
                "net_pnl": float(group["realized_pnl"].sum()),
                "positive_pnl": float(group["positive_pnl"].sum()),
                "negative_pnl_abs": float(group["negative_pnl_abs"].sum()),
                "positive_coverage_pct": float(group["positive_pnl"].sum() / total_positive * 100.0)
                if total_positive
                else np.nan,
                "negative_coverage_pct": float(group["negative_pnl_abs"].sum() / total_negative * 100.0)
                if total_negative
                else np.nan,
                "positive_year_count": int((year_pnl > 0).sum()),
                "negative_year_count": int((year_pnl < 0).sum()),
                "mean_prev_roll20_vol_pct": float(group["prev_rolling20_ann_vol_pct"].mean()),
                "mean_trend_participation_pct": float(group["trend_participation_pct"].mean()),
                "mean_directional_balance_abs": float(group["directional_balance_abs"].mean()),
                "mean_same_dir_corr": float(group["same_direction_correlation_max_corr"].mean()),
                "mean_prev_drawdown_pct": float(group["prev_drawdown_pct"].mean()),
            }
        )
    return pd.DataFrame(rows)


def _all_cohort_summaries(features: pd.DataFrame) -> pd.DataFrame:
    pieces = [
        _cohort_summary(features, "stage047_vol_bucket", "stage047_vol_bucket"),
        _cohort_summary(features, "stage047_participation_bucket", "stage047_participation_bucket"),
        _cohort_summary(features, "stage047_same_dir_corr_bucket", "stage047_same_dir_corr_bucket"),
        _cohort_summary(features, "stage047_vol_part_joint", "stage047_vol_part_joint"),
        _cohort_summary(features, "stage047_vol_corr_joint", "stage047_vol_corr_joint"),
        _cohort_summary(features, "stage047_three_way_joint", "stage047_three_way_joint"),
    ]
    summary = pd.concat(pieces, ignore_index=True)
    return summary.sort_values(["bucket_family", "net_pnl", "bucket"]).reset_index(drop=True)


def _year_matrix(features: pd.DataFrame) -> pd.DataFrame:
    matrix = (
        features.pivot_table(
            index="stage047_vol_part_joint",
            columns="entry_year",
            values="realized_pnl",
            aggfunc="sum",
            fill_value=0.0,
        )
        .sort_index()
        .reset_index()
    )
    matrix = matrix.rename(columns={"stage047_vol_part_joint": "bucket"})
    return matrix


def _product_matrix(features: pd.DataFrame) -> pd.DataFrame:
    top_products = (
        features.groupby("product")["realized_pnl"].sum().abs().sort_values(ascending=False).head(18).index.tolist()
    )
    subset = features[features["product"].isin(top_products)].copy()
    matrix = (
        subset.pivot_table(
            index="stage047_vol_part_joint",
            columns="product",
            values="realized_pnl",
            aggfunc="sum",
            fill_value=0.0,
        )
        .sort_index()
        .reset_index()
    )
    matrix = matrix.rename(columns={"stage047_vol_part_joint": "bucket"})
    return matrix


def _cohort_curves(features: pd.DataFrame, official_curve: pd.DataFrame) -> pd.DataFrame:
    dates = pd.DataFrame({"date": official_curve["date"].dropna().sort_values().unique()})
    rows: list[pd.DataFrame] = []
    buckets = [
        "all_lots",
        "joint_missing",
        "joint_high_vol_high_participation",
        "joint_high_vol_low_participation",
        "joint_low_vol_high_participation",
        "joint_low_vol_low_participation",
        "joint_mid_vol_mid_participation",
        "joint_mixed_vol_participation",
    ]
    for bucket in buckets:
        if bucket == "all_lots":
            part = features.copy()
        else:
            part = features[features["stage047_vol_part_joint"].eq(bucket)].copy()
        pnl_by_day = part.groupby("exit_day")["realized_pnl"].sum().rename("daily_realized_pnl").reset_index()
        pnl_by_day = pnl_by_day.rename(columns={"exit_day": "date"})
        merged = dates.merge(pnl_by_day, on="date", how="left")
        merged["daily_realized_pnl"] = merged["daily_realized_pnl"].fillna(0.0)
        merged["cumulative_realized_pnl"] = merged["daily_realized_pnl"].cumsum()
        merged["bucket"] = bucket
        rows.append(merged)
    return pd.concat(rows, ignore_index=True)


def _plot_path_state(curve: pd.DataFrame, market_daily: pd.DataFrame, features: pd.DataFrame) -> None:
    market = market_daily.copy()
    market["date"] = pd.to_datetime(market["date"], errors="coerce")
    fig, axes = plt.subplots(4, 1, figsize=(14, 11), sharex=True)
    axes[0].plot(curve["date"], curve["account_equity"] / 150_000.0, color="#1f77b4", linewidth=1.4)
    axes[0].set_yscale("log")
    axes[0].set_ylabel("NAV log")
    axes[0].set_title("Stage047 official C9/15w path with pre-entry volatility/participation state")
    axes[1].plot(curve["date"], curve["drawdown_pct"], color="#d62728", linewidth=1.2)
    axes[1].axhline(-40.0, color="#8c564b", linestyle="--", linewidth=0.9)
    axes[1].set_ylabel("DD %")
    axes[2].plot(curve["date"], curve["broker10_margin_to_equity_pct"], color="#ff7f0e", linewidth=1.1)
    axes[2].axhline(100.0, color="#8c564b", linestyle="--", linewidth=0.9)
    axes[2].set_ylabel("broker10 %")
    axes[3].plot(market["date"], market["trend_participation_pct"], color="#2ca02c", linewidth=1.0, label="trend participation")
    axes[3].plot(market["date"], market["mdi_abs_trend_60_z"], color="#9467bd", linewidth=0.9, label="MDI z")
    high_vol = features[features["stage047_vol_bucket"].eq("vol_high_ge100")]
    axes[3].scatter(
        high_vol["entry_date"],
        np.full(len(high_vol), 105.0),
        s=np.clip(high_vol["realized_pnl"].abs() / 4000.0, 12.0, 120.0),
        c=np.where(high_vol["realized_pnl"] >= 0, "#2ca02c", "#d62728"),
        alpha=0.55,
        label="high-vol entries",
    )
    axes[3].set_ylabel("state")
    axes[3].legend(loc="upper left", ncol=3, fontsize=8)
    for ax in axes:
        ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(PATH_STATE_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_cohort_curves(curves: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(14, 7))
    colors = {
        "all_lots": "#111111",
        "joint_missing": "#7f7f7f",
        "joint_high_vol_high_participation": "#d62728",
        "joint_high_vol_low_participation": "#ff7f0e",
        "joint_low_vol_high_participation": "#2ca02c",
        "joint_low_vol_low_participation": "#1f77b4",
        "joint_mid_vol_mid_participation": "#9467bd",
        "joint_mixed_vol_participation": "#17becf",
    }
    for bucket, group in curves.groupby("bucket"):
        ax.plot(group["date"], group["cumulative_realized_pnl"], linewidth=1.2, label=bucket, color=colors.get(bucket))
    ax.axhline(0.0, color="#444444", linewidth=0.8)
    ax.set_title("Stage047 cumulative closed-lot contribution by fixed vol/participation joint state")
    ax.set_ylabel("cumulative realized PnL")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout()
    fig.savefig(COHORT_CURVE_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_heatmap(matrix: pd.DataFrame, output: Path, title: str, figsize: tuple[int, int]) -> None:
    data = matrix.set_index("bucket")
    values = data.to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=figsize)
    max_abs = np.nanmax(np.abs(values)) if values.size else 1.0
    im = ax.imshow(values, cmap="RdYlGn", aspect="auto", vmin=-max_abs, vmax=max_abs)
    ax.set_xticks(range(len(data.columns)))
    ax.set_xticklabels([str(item) for item in data.columns], rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(len(data.index)))
    ax.set_yticklabels([str(item) for item in data.index], fontsize=8)
    ax.set_title(title)
    fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    fig.tight_layout()
    fig.savefig(output, dpi=160)
    plt.close(fig)


def _plot_state_scatter(features: pd.DataFrame) -> None:
    plot = features[
        features["prev_rolling20_ann_vol_pct"].notna()
        & features["trend_participation_pct"].notna()
        & features["realized_pnl"].notna()
    ].copy()
    fig, ax = plt.subplots(figsize=(10, 7))
    sizes = np.clip(plot["realized_pnl"].abs() / 4500.0, 18.0, 220.0)
    colors = np.where(plot["realized_pnl"] >= 0, "#2ca02c", "#d62728")
    ax.scatter(
        plot["prev_rolling20_ann_vol_pct"],
        plot["trend_participation_pct"],
        s=sizes,
        c=colors,
        alpha=0.55,
        edgecolors="none",
    )
    ax.axvline(50.0, color="#666666", linestyle="--", linewidth=0.8)
    ax.axvline(100.0, color="#666666", linestyle="--", linewidth=0.8)
    ax.axhline(25.0, color="#666666", linestyle="--", linewidth=0.8)
    ax.axhline(50.0, color="#666666", linestyle="--", linewidth=0.8)
    ax.set_title("Stage047 PnL scatter: previous 20d vol vs market trend participation")
    ax.set_xlabel("previous 20d annualized portfolio vol %")
    ax.set_ylabel("trend participation %")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(STATE_SCATTER_OUT, dpi=160)
    plt.close(fig)


def _render_report(
    metrics: dict[str, float],
    summary: pd.DataFrame,
    year_matrix: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    key_rows = summary[summary["bucket_family"].eq("stage047_vol_part_joint")].sort_values("net_pnl")
    corr_rows = summary[summary["bucket_family"].eq("stage047_vol_corr_joint")].sort_values("net_pnl")
    text = f"""# Stage047 volatility / participation joint-state read-only audit

- line_id: `{LINE_ID}`
- model_tag: `{MODEL_TAG}`
- official_live_version: `{OFFICIAL_LIVE_VERSION}`
- official_live_alias: `{OFFICIAL_LIVE_ALIAS}`
- generated_at: `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`
- boundary: read-only cohort/path audit; no trading rule; candidate_ready=0; no CTP/order API.

## External Research Judgment

- AQR's managed-futures paper frames diversified trend following as implementable time-series momentum and explicitly discusses risk management, allocation, costs, and rebalancing.
- Baltas/Kosowski show volatility estimation and signal design matter for futures time-series momentum, especially net-of-cost turnover; this supports state audits, but not intraday micromanagement.
- CME's managed-futures digest warns trend following is not simply long volatility; volatility and correlation/market co-movement should be considered jointly.
- My judgment: a universal rule, if any, should appear in a pre-entry joint state such as high volatility plus poor trend participation, not in post-hoc loser cohorts or a single product/year window.

## Official Baseline

| metric | value |
| --- | --- |
| end_equity | {metrics['end_equity']:.2f} |
| total_return_pct | {metrics['total_return_pct']:.4f} |
| max_dd_pct | {metrics['max_dd_pct']:.4f} |
| sharpe | {metrics['sharpe']:.4f} |
| total_slippage | {metrics['total_slippage']:.2f} |
| total_trade_count | {metrics['total_trade_count']:.0f} |
| win_rate_pct | {metrics['win_rate_pct']:.4f} |
| max_broker10_margin_to_equity_pct | {metrics['max_broker10_margin_to_equity_pct']:.4f} |

## Fixed Vol / Participation Joint Buckets

{_md_table(key_rows, max_rows=20)}

## Fixed Vol / Same-Direction Correlation Buckets

{_md_table(corr_rows, max_rows=20)}

## Year Matrix: Vol / Participation Joint Buckets

{_md_table(year_matrix, max_rows=20)}

## Decision

- decision: `{decision['decision']}`
- candidate_ready: `{int(decision['candidate_ready'])}`
- reason: {decision['reason']}

## Visual Outputs

- official path state chart: `{PATH_STATE_CHART_OUT}`
- cohort curve chart: `{COHORT_CURVE_CHART_OUT}`
- bucket-year heatmap: `{YEAR_HEATMAP_OUT}`
- state scatter: `{STATE_SCATTER_OUT}`
- product heatmap: `{PRODUCT_HEATMAP_OUT}`

## Visual Reading

- The official path chart keeps the actual C9/15w equity, drawdown, and broker10 path as the anchor; high-vol entries are overlaid so we can see whether they precede drawdown repair or damage.
- The cohort curve chart checks whether any predeclared state persistently falls before the main drawdown, rather than only ending negative in one product/year block.
- The year and product heatmaps are the overfitting guard: a tradable state must be broad across years/products, not a disguised 2022 or AP/fu/jm/lh patch.
- The scatter checks separability in the two first-principle dimensions. Heavy overlap between winners and losers means no execution rule should be written yet.

## Boundary

- This stage is not a strategy candidate and does not trigger A/B.
- Missing market state is kept as its own bucket; it is not filled or converted into a trade rule.
- No thresholds were swept. We reuse prior coarse buckets: 20d vol `<50 / 50-100 / >=100`, participation `<25 / 25-50 / >=50`, same-direction corr `<0.60 / 0.60-0.80 / >=0.80`.
"""
    REPORT_OUT.write_text(text, encoding="utf-8")


def run() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    features = _prepare_features()
    market_daily = _read_required_csv(MARKET_DAILY_IN)
    official_curve = _official_curve()
    metrics = _official_metrics(official_curve)

    cohort_summary = _all_cohort_summaries(features)
    year_matrix = _year_matrix(features)
    product_matrix = _product_matrix(features)
    cohort_curves = _cohort_curves(features, official_curve)

    vol_part = cohort_summary[cohort_summary["bucket_family"].eq("stage047_vol_part_joint")].copy()
    negative_candidates = vol_part[
        (vol_part["net_pnl"] < 0.0)
        & (vol_part["lot_count"] >= 20)
        & (vol_part["year_count"] >= 4)
        & (vol_part["negative_year_count"] >= 3)
        & (vol_part["positive_coverage_pct"] <= 10.0)
    ].copy()
    candidate_ready = False
    if negative_candidates.empty:
        reason = (
            "No predeclared vol/participation joint bucket has enough broad, cross-year negative "
            "separation while preserving right-tail evidence. This remains an explanatory state audit."
        )
    else:
        reason = (
            "A weak negative bucket exists by accounting, but this stage is read-only and still needs "
            "independent true-engine design before any candidate claim."
        )

    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "candidate_ready": candidate_ready,
        "ab_experiment_triggered": False,
        "boundary": "read_only_joint_state_audit_no_trade_rule",
        "decision": "stage047_vol_participation_joint_state_no_candidate",
        "reason": reason,
        "negative_candidate_bucket_count": int(len(negative_candidates)),
        "official_metrics": metrics,
        "inputs": {
            "features": FEATURES_IN,
            "market_daily": MARKET_DAILY_IN,
            "official_curve": OFFICIAL_CURVE_IN,
        },
        "outputs": {
            "features": FEATURES_OUT,
            "cohort_summary": COHORT_SUMMARY_OUT,
            "year_matrix": YEAR_MATRIX_OUT,
            "product_matrix": PRODUCT_MATRIX_OUT,
            "cohort_curves": COHORT_CURVES_OUT,
            "summary": SUMMARY_OUT,
            "report": REPORT_OUT,
            "path_state_chart": PATH_STATE_CHART_OUT,
            "cohort_curve_chart": COHORT_CURVE_CHART_OUT,
            "year_heatmap": YEAR_HEATMAP_OUT,
            "state_scatter": STATE_SCATTER_OUT,
            "product_heatmap": PRODUCT_HEATMAP_OUT,
            "decision": DECISION_OUT,
        },
    }

    summary_row = pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "line_id": LINE_ID,
                "official_live_version": OFFICIAL_LIVE_VERSION,
                "official_live_alias": OFFICIAL_LIVE_ALIAS,
                "candidate_ready": candidate_ready,
                "decision": decision["decision"],
                "reason": reason,
                **metrics,
            }
        ]
    )

    features.to_csv(FEATURES_OUT, index=False, encoding="utf-8-sig")
    cohort_summary.to_csv(COHORT_SUMMARY_OUT, index=False, encoding="utf-8-sig")
    year_matrix.to_csv(YEAR_MATRIX_OUT, index=False, encoding="utf-8-sig")
    product_matrix.to_csv(PRODUCT_MATRIX_OUT, index=False, encoding="utf-8-sig")
    cohort_curves.to_csv(COHORT_CURVES_OUT, index=False, encoding="utf-8-sig")
    summary_row.to_csv(SUMMARY_OUT, index=False, encoding="utf-8-sig")
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")

    _plot_path_state(official_curve, market_daily, features)
    _plot_cohort_curves(cohort_curves)
    _plot_heatmap(year_matrix, YEAR_HEATMAP_OUT, "Stage047 vol/participation joint bucket yearly PnL", (13, 6))
    _plot_state_scatter(features)
    _plot_heatmap(product_matrix, PRODUCT_HEATMAP_OUT, "Stage047 top-product PnL by vol/participation joint bucket", (13, 6))
    _render_report(metrics, cohort_summary, year_matrix, decision)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    run()
