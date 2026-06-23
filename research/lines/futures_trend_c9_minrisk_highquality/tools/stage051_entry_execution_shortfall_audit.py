from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import re
import sys
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


LINE_ID = "futures_trend_c9_minrisk_highquality"
STAGE = "Stage051"
MODEL_TAG = "stage051_entry_execution_shortfall_audit_v1"
OUTPUT_PREFIX = "qmt_roll_stage051_c9_minrisk_entry_execution_shortfall_audit"

OFFICIAL_ARM = "A_official_stage847_c9_15w"
INITIAL_CAPITAL = 150_000.0
TARGET_GAP_R = 0.5
TARGET_COHORT = "adverse_entry_gap_ge_0_5r"
ATLAS_ROWS = 8
ATLAS_BARS = 120

SCRIPT_PATH = Path(__file__).resolve()
REPO_DIR = SCRIPT_PATH.parents[4]
TOOL_DIR = SCRIPT_PATH.parent
EXAMPLE_DIR = REPO_DIR / "examples" / "portfolio_backtesting"
for item in [str(TOOL_DIR), str(EXAMPLE_DIR)]:
    if item not in sys.path:
        sys.path.insert(0, item)

import stage038_order_event_replay_prototype_audit as s038
import stage041_timestamp_ready_replay_consistency_audit as s041
from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION


LINE_DIR = REPO_DIR / "research" / "lines" / LINE_ID
STAGE043_DIR = LINE_DIR / "outputs" / "stage043_official_open_scan_replay_repair_audit"
OUTPUT_DIR = LINE_DIR / "outputs" / "stage051_entry_execution_shortfall_audit"

STAGE043_REPLAY_IN = (
    STAGE043_DIR
    / "qmt_roll_stage043_c9_minrisk_official_open_scan_replay_repair_audit_repair_replay_ledger_"
    "stage043_official_open_scan_replay_repair_audit_v1.csv"
)

FEATURES_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_features_{MODEL_TAG}.csv"
BUCKET_SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_summary_{MODEL_TAG}.csv"
TARGET_LOTS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_target_orders_{MODEL_TAG}.csv"
LEAVE_ONE_YEAR_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_leave_one_year_{MODEL_TAG}.csv"
LEAVE_ONE_PRODUCT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_leave_one_product_{MODEL_TAG}.csv"
BUCKET_YEAR_MATRIX_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_year_matrix_{MODEL_TAG}.csv"
UPPER_BOUND_CURVE_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_upper_bound_curve_{MODEL_TAG}.csv"
SUMMARY_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
DECISION_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

PATH_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_upper_bound_path_chart_{MODEL_TAG}.png"
CONTRIBUTION_CHART_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_contribution_chart_{MODEL_TAG}.png"
SCATTER_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_gap_scatter_{MODEL_TAG}.png"
BUCKET_YEAR_HEATMAP_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_bucket_year_heatmap_{MODEL_TAG}.png"
ATLAS_OUT = OUTPUT_DIR / f"{OUTPUT_PREFIX}_minute_atlas_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        if not np.isfinite(value):
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


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def _safe_float(value: Any, default: float = np.nan) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if np.isfinite(out) else default


def _fmt_float(value: Any, digits: int = 4) -> str:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return "NA"
    return f"{out:.{digits}f}" if np.isfinite(out) else "NA"


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_empty_"
    display = frame.head(max_rows).copy() if max_rows is not None else frame.copy()
    for column in display.columns:
        if pd.api.types.is_float_dtype(display[column]):
            display[column] = display[column].map(lambda value: "" if pd.isna(value) else f"{value:.4f}")
    lines = [
        "| " + " | ".join(str(column) for column in display.columns) + " |",
        "| " + " | ".join(["---"] * len(display.columns)) + " |",
    ]
    for _, row in display.iterrows():
        lines.append("| " + " | ".join(str(row[column]) for column in display.columns) + " |")
    return "\n".join(lines)


def _normalize_product(vt_symbol: Any, fallback: Any = "") -> str:
    symbol = "" if pd.isna(vt_symbol) else str(vt_symbol)
    if "." in symbol:
        code, exchange = symbol.split(".", 1)
        match = re.match(r"^([A-Za-z]+)", code)
        if match:
            return f"{match.group(1)}.{exchange}"
    raw = "" if pd.isna(fallback) else str(fallback)
    if "." in raw:
        return raw
    match = re.match(r"^([A-Za-z]+)", raw)
    if match:
        return match.group(1)
    return raw or "UNKNOWN"


def _direction_sign(direction: Any) -> float:
    text = str(direction).lower()
    if text == "long":
        return 1.0
    if text == "short":
        return -1.0
    return np.nan


def _equity_metrics(equity: pd.Series, dates: pd.Series | None = None) -> dict[str, Any]:
    equity = pd.to_numeric(equity, errors="coerce").astype(float).reset_index(drop=True)
    running_max = equity.cummax()
    drawdown = (equity / running_max - 1.0) * 100.0
    returns = equity.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    std = returns.std(ddof=1)
    sharpe = float(returns.mean() / std * np.sqrt(252.0)) if std and std > 0 else np.nan
    trough_idx = int(drawdown.idxmin()) if len(drawdown) else -1
    out: dict[str, Any] = {
        "end_equity": float(equity.iloc[-1]) if len(equity) else np.nan,
        "total_return_pct": float((equity.iloc[-1] / INITIAL_CAPITAL - 1.0) * 100.0) if len(equity) else np.nan,
        "max_dd_pct": float(drawdown.min()) if len(drawdown) else np.nan,
        "sharpe": sharpe,
    }
    if dates is not None and len(dates) and trough_idx >= 0:
        date_values = pd.to_datetime(dates, errors="coerce").reset_index(drop=True)
        out["max_dd_date"] = date_values.iloc[trough_idx].strftime("%Y-%m-%d")
    return out


def _load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame]]:
    curve, _open_trades, _candidates, lots, _intraday, _trades = s038._prepare_inputs()
    replay = _read_csv(STAGE043_REPLAY_IN)
    groups = s038._load_minute_groups(replay)
    return curve, lots, replay, _intraday, groups


def _lot_aggregation(lots: pd.DataFrame) -> pd.DataFrame:
    lots = lots.copy()
    lots["entry_date"] = pd.to_datetime(lots["entry_date"], errors="coerce")
    lots["exit_date"] = pd.to_datetime(lots["exit_date"], errors="coerce")
    lots["realized_pnl"] = pd.to_numeric(lots["realized_pnl"], errors="coerce").fillna(0.0)
    return (
        lots.groupby("open_trade_id", dropna=False)
        .agg(
            realized_pnl=("realized_pnl", "sum"),
            lot_count=("lot_id", "count"),
            matched_volume=("volume", "sum"),
            entry_date=("entry_date", "min"),
            exit_date=("exit_date", "max"),
            lot_vt_symbol=("vt_symbol", "first"),
            lot_direction=("direction", "first"),
        )
        .reset_index()
    )


def _gap_bucket(value: float) -> str:
    if not np.isfinite(value):
        return "gap_missing"
    if value >= TARGET_GAP_R:
        return TARGET_COHORT
    if value >= 0.25:
        return "adverse_entry_gap_0_25_0_5r"
    if value > -0.25:
        return "near_decision_price_abs_lt_0_25r"
    if value > -0.5:
        return "favorable_entry_gap_0_25_0_5r"
    return "favorable_entry_gap_le_minus_0_5r"


def _build_features(replay: pd.DataFrame, lots: pd.DataFrame) -> pd.DataFrame:
    keep = [
        "candidate_index",
        "official_open_trade_id",
        "vt_symbol",
        "product_vt_symbol",
        "direction",
        "candidate_date",
        "official_open_date",
        "planned_entry_price",
        "planned_stop_price",
        "planned_stop_distance",
        "official_open_price",
        "official_open_volume",
        "candidate_selected_volume",
        "timestamp_ready",
        "stage861_day_ready",
        "official_event_family",
        "official_exit_reason",
        "official_first_stop_time",
        "official_reentry_time",
        "official_retry_failed_time",
        "official_hit_time",
        "stage042_session_convention_status",
    ]
    features = replay[[col for col in keep if col in replay.columns]].copy()
    for column in [
        "planned_entry_price",
        "planned_stop_price",
        "planned_stop_distance",
        "official_open_price",
        "official_open_volume",
        "candidate_selected_volume",
        "timestamp_ready",
        "stage861_day_ready",
    ]:
        if column in features.columns:
            features[column] = pd.to_numeric(features[column], errors="coerce")
    features = features[
        features["timestamp_ready"].eq(1)
        & features["stage861_day_ready"].eq(1)
        & features["planned_stop_distance"].gt(0.0)
        & features["official_open_price"].notna()
        & features["planned_entry_price"].notna()
    ].copy()
    lot_agg = _lot_aggregation(lots)
    features = features.merge(lot_agg, left_on="official_open_trade_id", right_on="open_trade_id", how="left")
    features["entry_date"] = pd.to_datetime(features["entry_date"], errors="coerce")
    features["exit_date"] = pd.to_datetime(features["exit_date"], errors="coerce")
    features["entry_year"] = features["entry_date"].dt.year.astype("Int64")
    features["exit_year"] = features["exit_date"].dt.year.astype("Int64")
    features["realized_pnl"] = pd.to_numeric(features["realized_pnl"], errors="coerce").fillna(0.0)
    features["direction_sign"] = features["direction"].map(_direction_sign)
    features["signed_open_minus_plan"] = features["official_open_price"] - features["planned_entry_price"]
    features["entry_gap_r"] = (
        features["direction_sign"] * features["signed_open_minus_plan"] / features["planned_stop_distance"]
    )
    features["abs_entry_gap_r"] = features["entry_gap_r"].abs()
    features["actual_risk_to_planned_stop"] = (
        features["official_open_price"] - features["planned_stop_price"]
    ).abs()
    features["actual_risk_ratio_to_plan"] = features["actual_risk_to_planned_stop"] / features["planned_stop_distance"]
    features["gap_bucket"] = features["entry_gap_r"].map(_gap_bucket)
    features["is_stage051_target"] = features["gap_bucket"].eq(TARGET_COHORT)
    features["normalized_product"] = [
        _normalize_product(vt_symbol, product)
        for vt_symbol, product in zip(features["vt_symbol"], features.get("product_vt_symbol", ""))
    ]
    features["order_notional_proxy"] = (
        features["official_open_price"].abs()
        * features["official_open_volume"].fillna(0.0)
    )
    features["decision_to_execution_shortfall_r"] = features["entry_gap_r"]
    return features.sort_values(["entry_date", "official_open_trade_id"]).reset_index(drop=True)


def _bucket_summary(features: pd.DataFrame) -> pd.DataFrame:
    total_positive = float(features["realized_pnl"].clip(lower=0).sum())
    total_negative_abs = float((-features["realized_pnl"].clip(upper=0)).sum())
    grouped = (
        features.groupby("gap_bucket", dropna=False)
        .agg(
            order_count=("candidate_index", "count"),
            lot_count=("lot_count", "sum"),
            product_count=("normalized_product", "nunique"),
            year_count=("entry_year", "nunique"),
            net_pnl=("realized_pnl", "sum"),
            positive_pnl=("realized_pnl", lambda s: float(s.clip(lower=0).sum())),
            negative_pnl=("realized_pnl", lambda s: float(s.clip(upper=0).sum())),
            median_entry_gap_r=("entry_gap_r", "median"),
            max_entry_gap_r=("entry_gap_r", "max"),
            median_actual_risk_ratio=("actual_risk_ratio_to_plan", "median"),
            mean_actual_risk_ratio=("actual_risk_ratio_to_plan", "mean"),
        )
        .reset_index()
    )
    grouped["positive_coverage_pct"] = (
        grouped["positive_pnl"] / total_positive * 100.0 if total_positive else np.nan
    )
    grouped["negative_abs_coverage_pct"] = (
        -grouped["negative_pnl"] / total_negative_abs * 100.0 if total_negative_abs else np.nan
    )
    order = {
        "adverse_entry_gap_ge_0_5r": 0,
        "adverse_entry_gap_0_25_0_5r": 1,
        "near_decision_price_abs_lt_0_25r": 2,
        "favorable_entry_gap_0_25_0_5r": 3,
        "favorable_entry_gap_le_minus_0_5r": 4,
        "gap_missing": 5,
    }
    grouped["sort_key"] = grouped["gap_bucket"].map(order).fillna(99)
    return grouped.sort_values("sort_key").drop(columns=["sort_key"]).reset_index(drop=True)


def _build_upper_bound_curve(curve: pd.DataFrame, target: pd.DataFrame) -> pd.DataFrame:
    cashflow = (
        target.dropna(subset=["exit_date"])
        .groupby("exit_date", as_index=False)
        .agg(target_realized_pnl=("realized_pnl", "sum"), target_order_count=("candidate_index", "count"))
        .rename(columns={"exit_date": "date"})
    )
    out = curve[["date", "account_equity", "drawdown_pct", "broker10_margin_to_equity_pct"]].copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.normalize()
    cashflow["date"] = pd.to_datetime(cashflow["date"], errors="coerce").dt.normalize()
    out = out.merge(cashflow, on="date", how="left")
    out["target_realized_pnl"] = out["target_realized_pnl"].fillna(0.0)
    out["target_order_count"] = out["target_order_count"].fillna(0).astype(int)
    out["skipped_target_pnl_cumsum"] = out["target_realized_pnl"].cumsum()
    out["upper_bound_skip_target_equity"] = out["account_equity"] - out["skipped_target_pnl_cumsum"]
    out["upper_bound_drawdown_pct"] = (
        out["upper_bound_skip_target_equity"] / out["upper_bound_skip_target_equity"].cummax() - 1.0
    ) * 100.0
    out["equity_gap_vs_official"] = out["upper_bound_skip_target_equity"] - out["account_equity"]
    return out


def _leave_one(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    total_pnl = float(frame["realized_pnl"].sum())
    total_count = int(len(frame))
    grouped = (
        frame.groupby(column, dropna=False)
        .agg(removed_count=("realized_pnl", "size"), removed_pnl=("realized_pnl", "sum"))
        .reset_index()
        .rename(columns={column: "removed_key"})
    )
    grouped["remaining_count"] = total_count - grouped["removed_count"]
    grouped["remaining_pnl"] = total_pnl - grouped["removed_pnl"]
    return grouped.sort_values("remaining_pnl").reset_index(drop=True)


def _bucket_year_matrix(features: pd.DataFrame) -> pd.DataFrame:
    matrix = (
        features.pivot_table(
            index="gap_bucket",
            columns="entry_year",
            values="realized_pnl",
            aggfunc="sum",
            fill_value=0.0,
        )
        .reset_index()
    )
    return matrix


def _summary(
    curve: pd.DataFrame,
    lots: pd.DataFrame,
    features: pd.DataFrame,
    bucket_summary: pd.DataFrame,
    upper: pd.DataFrame,
) -> pd.DataFrame:
    official = s038._official_metrics(curve, lots)
    target = features[features["is_stage051_target"]].copy()
    upper_metrics = _equity_metrics(upper["upper_bound_skip_target_equity"], upper["date"])
    official_total_return = official["total_return_pct"]
    official_dd = official["max_drawdown_pct"]
    target_summary = bucket_summary[bucket_summary["gap_bucket"].eq(TARGET_COHORT)].iloc[0].to_dict()
    return_retention = (
        upper_metrics["total_return_pct"] / official_total_return * 100.0 if official_total_return else np.nan
    )
    dd_improvement = upper_metrics["max_dd_pct"] - official_dd
    decision = "stage051_entry_shortfall_target_is_right_tail_no_engine"
    if target_summary["net_pnl"] < 0 and dd_improvement >= 5.0 and return_retention >= 80.0:
        decision = "stage051_entry_shortfall_upper_bound_worth_true_engine_review"
    return pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "line_id": LINE_ID,
                "official_live_version": OFFICIAL_LIVE_VERSION,
                "official_live_alias": OFFICIAL_LIVE_ALIAS,
                "official_end_equity": official["end_equity"],
                "official_total_return_pct": official_total_return,
                "official_max_dd_pct": official_dd,
                "official_sharpe": official["sharpe"],
                "official_total_slippage": official["total_slippage"],
                "official_total_trade_count": official["total_trade_count"],
                "official_closed_lot_win_rate_pct": official["closed_lot_win_rate_pct"],
                "official_broker10_peak_pct": official["max_broker10_margin_to_equity_pct"],
                "timestamp_ready_order_count": int(len(features)),
                "target_cohort": TARGET_COHORT,
                "target_gap_r": TARGET_GAP_R,
                "target_order_count": int(len(target)),
                "target_product_count": int(target["normalized_product"].nunique()),
                "target_year_count": int(target["entry_year"].nunique()),
                "target_net_pnl": float(target["realized_pnl"].sum()),
                "target_positive_pnl": float(target["realized_pnl"].clip(lower=0).sum()),
                "target_negative_pnl": float(target["realized_pnl"].clip(upper=0).sum()),
                "target_median_entry_gap_r": float(target["entry_gap_r"].median()) if len(target) else np.nan,
                "target_max_entry_gap_r": float(target["entry_gap_r"].max()) if len(target) else np.nan,
                "upper_bound_end_equity": upper_metrics["end_equity"],
                "upper_bound_total_return_pct": upper_metrics["total_return_pct"],
                "upper_bound_max_dd_pct": upper_metrics["max_dd_pct"],
                "upper_bound_max_dd_date": upper_metrics.get("max_dd_date", ""),
                "upper_bound_sharpe": upper_metrics["sharpe"],
                "upper_bound_return_retention_pct": return_retention,
                "upper_bound_max_dd_improvement_pp": dd_improvement,
                "decision": decision,
                "candidate_ready": 0,
                "ab_triggered": 0,
            }
        ]
    )


def _plot_upper_bound_path(upper: pd.DataFrame, summary: pd.Series) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(15, 12), sharex=True, gridspec_kw={"height_ratios": [2.0, 1.2, 1.0]})
    axes[0].plot(upper["date"], upper["account_equity"], color="#2563eb", linewidth=1.4, label="official C9/15w")
    axes[0].plot(
        upper["date"],
        upper["upper_bound_skip_target_equity"],
        color="#dc2626",
        linewidth=1.2,
        label="optimistic skip adverse gap >=0.5R",
    )
    axes[0].set_yscale("log")
    axes[0].set_ylabel("equity (log)")
    axes[1].plot(upper["date"], upper["drawdown_pct"], color="#2563eb", linewidth=1.2, label="official DD")
    axes[1].plot(
        upper["date"],
        upper["upper_bound_drawdown_pct"],
        color="#dc2626",
        linewidth=1.2,
        label="skip target DD",
    )
    axes[1].set_ylabel("drawdown %")
    axes[2].plot(upper["date"], upper["equity_gap_vs_official"], color="#7f1d1d", linewidth=1.2)
    axes[2].axhline(0.0, color="black", linewidth=0.8)
    axes[2].set_ylabel("equity gap")
    title = (
        f"Stage051 entry shortfall upper bound | target pnl {_fmt_float(summary['target_net_pnl'], 1)} | "
        f"retention {_fmt_float(summary['upper_bound_return_retention_pct'], 2)}% | "
        f"DD improvement {_fmt_float(summary['upper_bound_max_dd_improvement_pp'], 2)}pp"
    )
    axes[0].set_title(title)
    for ax in axes:
        ax.grid(True, alpha=0.25)
        handles, labels = ax.get_legend_handles_labels()
        if labels:
            ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(PATH_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_contribution(features: pd.DataFrame) -> None:
    data = features.dropna(subset=["exit_date"]).copy()
    data["exit_date"] = pd.to_datetime(data["exit_date"], errors="coerce").dt.normalize()
    daily = (
        data.groupby(["exit_date", "gap_bucket"], as_index=False)["realized_pnl"]
        .sum()
        .sort_values("exit_date")
    )
    pivot = daily.pivot_table(index="exit_date", columns="gap_bucket", values="realized_pnl", aggfunc="sum", fill_value=0.0)
    pivot = pivot.sort_index().cumsum()
    fig, ax = plt.subplots(figsize=(14, 7))
    preferred = [
        TARGET_COHORT,
        "adverse_entry_gap_0_25_0_5r",
        "near_decision_price_abs_lt_0_25r",
        "favorable_entry_gap_0_25_0_5r",
        "favorable_entry_gap_le_minus_0_5r",
    ]
    colors = {
        TARGET_COHORT: "#dc2626",
        "adverse_entry_gap_0_25_0_5r": "#f97316",
        "near_decision_price_abs_lt_0_25r": "#64748b",
        "favorable_entry_gap_0_25_0_5r": "#22c55e",
        "favorable_entry_gap_le_minus_0_5r": "#16a34a",
    }
    for column in preferred:
        if column in pivot.columns:
            ax.plot(pivot.index, pivot[column], linewidth=1.4, label=column, color=colors.get(column))
    ax.axhline(0.0, color="black", linewidth=0.8)
    ax.set_title("Stage051 cumulative realized PnL by entry shortfall bucket")
    ax.set_ylabel("cumulative realized PnL")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best", fontsize=8)
    fig.tight_layout()
    fig.savefig(CONTRIBUTION_CHART_OUT, dpi=160)
    plt.close(fig)


def _plot_scatter(features: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(12, 7))
    colors = np.where(features["is_stage051_target"], "#dc2626", "#2563eb")
    sizes = np.clip(features["official_open_volume"].fillna(1.0).to_numpy(dtype=float), 1.0, 80.0) * 5
    ax.scatter(features["entry_gap_r"], features["realized_pnl"], s=sizes, c=colors, alpha=0.72, edgecolor="white", linewidth=0.5)
    ax.axvline(TARGET_GAP_R, color="#dc2626", linestyle="--", linewidth=1.1, label="target +0.5R adverse gap")
    ax.axvline(0.0, color="black", linewidth=0.9)
    ax.axhline(0.0, color="black", linewidth=0.9)
    ax.set_title("Stage051 entry shortfall vs realized PnL")
    ax.set_xlabel("directional adverse entry gap vs planned entry (R)")
    ax.set_ylabel("realized PnL by initial open trade")
    ax.grid(True, alpha=0.25)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(SCATTER_OUT, dpi=160)
    plt.close(fig)


def _plot_bucket_year_heatmap(matrix: pd.DataFrame) -> None:
    data = matrix.set_index("gap_bucket")
    years = [col for col in data.columns if str(col) != "gap_bucket"]
    values = data[years].to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=(12, 5.8))
    vmax = np.nanmax(np.abs(values)) if values.size else 1.0
    im = ax.imshow(values, aspect="auto", cmap="RdYlGn", vmin=-vmax, vmax=vmax)
    ax.set_xticks(np.arange(len(years)))
    ax.set_xticklabels([str(year) for year in years], rotation=45, ha="right")
    ax.set_yticks(np.arange(len(data.index)))
    ax.set_yticklabels(data.index)
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            ax.text(j, i, f"{values[i, j] / 10000:.0f}w", ha="center", va="center", fontsize=7)
    ax.set_title("Stage051 gap bucket x entry year realized PnL")
    fig.colorbar(im, ax=ax, label="realized PnL")
    fig.tight_layout()
    fig.savefig(BUCKET_YEAR_HEATMAP_OUT, dpi=160)
    plt.close(fig)


def _bars_for_order(row: pd.Series, groups: dict[str, pd.DataFrame]) -> pd.DataFrame:
    bars = s041._bars_for_symbol(groups, str(row.get("vt_symbol", "")))
    if bars.empty:
        return pd.DataFrame()
    day = s041._bars_on_date(bars, s038._normalize_day(row.get("official_open_date")))
    if day.empty:
        return pd.DataFrame()
    day = day.sort_values("bar_datetime_ts").reset_index(drop=True)
    start = pd.to_datetime(row.get("replay_open_datetime", row.get("official_open_date")), errors="coerce")
    if pd.notna(start) and "bar_datetime_ts" in day.columns:
        day = day[pd.to_datetime(day["bar_datetime_ts"], errors="coerce").ge(pd.Timestamp(start))].copy()
    return day.head(ATLAS_BARS).reset_index(drop=True)


def _plot_atlas(features: pd.DataFrame, groups: dict[str, pd.DataFrame]) -> None:
    target = features[features["is_stage051_target"]].copy()
    if target.empty:
        target = features.sort_values("entry_gap_r", ascending=False).head(ATLAS_ROWS).copy()
    target["abs_pnl"] = target["realized_pnl"].abs()
    atlas_rows = target.sort_values(["abs_pnl", "entry_gap_r"], ascending=[False, False]).head(ATLAS_ROWS)
    rows = len(atlas_rows)
    fig, axes = plt.subplots(rows, 1, figsize=(15, max(2.4 * rows, 4.0)), squeeze=False)
    for ax, (_, row) in zip(axes[:, 0], atlas_rows.iterrows()):
        bars = _bars_for_order(row, groups)
        title = (
            f"{row['vt_symbol']} {row['direction']} gapR={_fmt_float(row['entry_gap_r'], 2)} "
            f"pnl={_fmt_float(row['realized_pnl'], 0)} event={row.get('official_event_family', '')}"
        )
        if bars.empty:
            ax.set_title(title + " | missing bars")
            ax.axis("off")
            continue
        times = pd.to_datetime(bars["bar_datetime_ts"], errors="coerce")
        ax.plot(times, bars["close"], color="#111827", linewidth=1.0, label="close")
        ax.fill_between(times, bars["low"].astype(float), bars["high"].astype(float), color="#cbd5e1", alpha=0.35, label="high-low")
        planned_entry = _safe_float(row.get("planned_entry_price"))
        official_open = _safe_float(row.get("official_open_price"))
        planned_stop = _safe_float(row.get("planned_stop_price"))
        risk = _safe_float(row.get("planned_stop_distance"))
        sign = _direction_sign(row.get("direction"))
        if np.isfinite(planned_entry):
            ax.axhline(planned_entry, color="#64748b", linestyle="--", linewidth=0.8, label="planned entry")
        if np.isfinite(official_open):
            ax.axhline(official_open, color="#dc2626", linestyle="-", linewidth=0.9, label="official open")
        if np.isfinite(planned_stop):
            ax.axhline(planned_stop, color="#991b1b", linestyle=":", linewidth=0.9, label="planned stop")
        if np.isfinite(official_open) and np.isfinite(risk) and np.isfinite(sign):
            ax.axhline(official_open + sign * 0.5 * risk, color="#f97316", linestyle=":", linewidth=0.8, label="0.5R progress")
        for field, color, label in [
            ("official_first_stop_time", "#991b1b", "first stop"),
            ("official_reentry_time", "#2563eb", "reentry"),
            ("official_retry_failed_time", "#7c2d12", "retry failed"),
            ("official_hit_time", "#16a34a", "C2 hit"),
        ]:
            ts = pd.to_datetime(row.get(field), errors="coerce")
            if pd.notna(ts):
                ax.axvline(ts, color=color, linestyle="--", linewidth=0.8, label=label)
        ax.set_title(title, fontsize=9)
        ax.grid(True, alpha=0.25)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    unique: dict[str, Any] = {}
    for handle, label in zip(handles, labels):
        unique.setdefault(label, handle)
    fig.legend(unique.values(), unique.keys(), loc="upper right", fontsize=8)
    fig.tight_layout(rect=(0, 0, 0.88, 1))
    fig.savefig(ATLAS_OUT, dpi=160)
    plt.close(fig)


def _write_report(
    summary: pd.Series,
    bucket_summary: pd.DataFrame,
    leave_year: pd.DataFrame,
    leave_product: pd.DataFrame,
) -> None:
    report = f"""# Stage051 entry execution shortfall audit

## Positioning

- Official version: `{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`.
- This is a read-only execution-price quality audit on the Stage045 timestamp-ready replay base. It is not a new trading rule, not a true engine, not an A/B candidate, and not a live rule.
- Fixed predeclared target: `{TARGET_COHORT}`, meaning the actual official open is at least `{TARGET_GAP_R:.1f}R` worse than the planned entry price in the trade direction.
- `fallback/no-proxy` initial orders remain outside this audit. They are not backfilled with Stage861 first bars or final PnL.

## External Research Judgment

- Implementation shortfall literature treats the gap between decision price and execution price as a real execution cost/risk source.
- Almgren-Chriss style execution thinking frames trading as a tradeoff between execution cost and price risk, not as a search for ex-post losing trades.
- Rob Carver / systematic execution examples favor simple, replicable execution rules such as passive limits, but only after testing whether the execution signal has stable meaning.
- Judgment for this repo: an adverse entry gap relative to planned stop distance is a universal candidate risk source. But it must first prove it does not carry trend right-tail.

## Headline

- Timestamp-ready orders audited: `{int(summary['timestamp_ready_order_count'])}`.
- Target orders: `{int(summary['target_order_count'])}`, products `{int(summary['target_product_count'])}`, years `{int(summary['target_year_count'])}`.
- Target net PnL: `{_fmt_float(summary['target_net_pnl'], 2)}`.
- Optimistic skip target end equity: `{_fmt_float(summary['upper_bound_end_equity'], 2)}`.
- Optimistic skip target return retention: `{_fmt_float(summary['upper_bound_return_retention_pct'], 4)}%`.
- Optimistic skip target max DD: `{_fmt_float(summary['upper_bound_max_dd_pct'], 4)}%`, improvement `{_fmt_float(summary['upper_bound_max_dd_improvement_pp'], 4)}pp`.
- Decision: `{summary['decision']}`.

## Bucket Summary

{_md_table(bucket_summary, max_rows=20)}

## Leave-One Checks For Target Cohort

### By Year

{_md_table(leave_year, max_rows=20)}

### By Product

{_md_table(leave_product, max_rows=20)}

## Visual Outputs

- Upper-bound path chart: `{PATH_CHART_OUT}`
- Bucket contribution chart: `{CONTRIBUTION_CHART_OUT}`
- Gap scatter: `{SCATTER_OUT}`
- Bucket-year heatmap: `{BUCKET_YEAR_HEATMAP_OUT}`
- Minute atlas: `{ATLAS_OUT}`

## Judgment

The target cohort is not a bad-signal set. It is net positive and spans multiple years/products. The optimistic skip curve therefore cuts right-tail compounding instead of repairing the official max-drawdown problem. This closes the direct "do not chase adverse entry gap >= 0.5R" route as a trading rule.

The useful lesson is narrower: entry implementation shortfall should remain an execution TCA monitor, not a standalone C9/15w risk filter, unless future point-in-time data proves a separate liquidity or order-book mechanism.
"""
    REPORT_OUT.write_text(report, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    curve, lots, replay, _intraday, groups = _load_inputs()
    features = _build_features(replay, lots)
    bucket_summary = _bucket_summary(features)
    target = features[features["is_stage051_target"]].copy()
    upper = _build_upper_bound_curve(curve, target)
    leave_year = _leave_one(target, "entry_year")
    leave_product = _leave_one(target, "normalized_product")
    bucket_year = _bucket_year_matrix(features)
    summary = _summary(curve, lots, features, bucket_summary, upper)

    _write_csv(features, FEATURES_OUT)
    _write_csv(bucket_summary, BUCKET_SUMMARY_OUT)
    _write_csv(target, TARGET_LOTS_OUT)
    _write_csv(leave_year, LEAVE_ONE_YEAR_OUT)
    _write_csv(leave_product, LEAVE_ONE_PRODUCT_OUT)
    _write_csv(bucket_year, BUCKET_YEAR_MATRIX_OUT)
    _write_csv(upper, UPPER_BOUND_CURVE_OUT)
    _write_csv(summary, SUMMARY_OUT)

    row = summary.iloc[0]
    decision = {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "created_at": row["created_at"],
        "line_id": LINE_ID,
        "decision": row["decision"],
        "target_cohort": TARGET_COHORT,
        "target_gap_r": TARGET_GAP_R,
        "timestamp_ready_order_count": int(row["timestamp_ready_order_count"]),
        "target_order_count": int(row["target_order_count"]),
        "target_net_pnl": float(row["target_net_pnl"]),
        "upper_bound_return_retention_pct": float(row["upper_bound_return_retention_pct"]),
        "upper_bound_max_dd_improvement_pp": float(row["upper_bound_max_dd_improvement_pp"]),
        "candidate_ready": int(row["candidate_ready"]),
        "ab_triggered": int(row["ab_triggered"]),
        "outputs": {
            "features": FEATURES_OUT,
            "bucket_summary": BUCKET_SUMMARY_OUT,
            "target_orders": TARGET_LOTS_OUT,
            "upper_bound_curve": UPPER_BOUND_CURVE_OUT,
            "summary": SUMMARY_OUT,
            "report": REPORT_OUT,
            "path_chart": PATH_CHART_OUT,
            "contribution_chart": CONTRIBUTION_CHART_OUT,
            "scatter": SCATTER_OUT,
            "bucket_year_heatmap": BUCKET_YEAR_HEATMAP_OUT,
            "minute_atlas": ATLAS_OUT,
        },
    }
    DECISION_OUT.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")

    _plot_upper_bound_path(upper, row)
    _plot_contribution(features)
    _plot_scatter(features)
    _plot_bucket_year_heatmap(bucket_year)
    _plot_atlas(features, groups)
    _write_report(row, bucket_summary, leave_year, leave_product)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
