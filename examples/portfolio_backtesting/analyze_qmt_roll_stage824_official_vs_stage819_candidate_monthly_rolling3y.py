from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
from datetime import datetime
import json
import os
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage660_stage653_multiperiod_live_audit as s660
import analyze_qmt_roll_stage748_half_risk_no_streak_500k as s748
import analyze_qmt_roll_stage772_am40_80_120_oi_monthly as s772
import analyze_qmt_roll_stage808_stage806_rolling3y as s808
import analyze_qmt_roll_stage813_stage804_rsi_partial_exit_ablation_yearly as s813
from qmt_roll_official_candidate_stage819_30w_config import (
    OFFICIAL_CANDIDATE_STAGE819_30W_ALIAS,
    OFFICIAL_CANDIDATE_STAGE819_30W_CAPITAL,
    OFFICIAL_CANDIDATE_STAGE819_30W_VERSION,
    build_official_candidate_stage819_30w_manifest,
)
from qmt_roll_official_live_config import (
    OFFICIAL_LIVE_ALIAS,
    OFFICIAL_LIVE_CAPITAL,
    OFFICIAL_LIVE_VERSION,
)


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage824_official_vs_stage819_candidate_monthly_rolling3y_v1"
OUTPUT_PREFIX = "qmt_roll_stage824_official_vs_stage819_candidate_monthly_rolling3y"
LINE_ID = "futures_trend_2019_data_extension"

DATA_START = pd.Timestamp("2020-01-01")
DATA_END = pd.Timestamp("2026-05-29")
ROLL_YEARS = 3
TERMINAL_START = pd.Timestamp("2023-06-01")
MAX_WORKERS = max(1, min(8, int(os.environ.get("STAGE824_MAX_WORKERS", "6"))))

ARMS: tuple[dict[str, Any], ...] = (
    {
        "arm_key": "official_live_20w",
        "series_label": f"{OFFICIAL_LIVE_ALIAS} official live",
        "role": "A_official_live",
        "capital": OFFICIAL_LIVE_CAPITAL,
        "color": "#2563eb",
    },
    {
        "arm_key": "candidate_stage819_30w",
        "series_label": OFFICIAL_CANDIDATE_STAGE819_30W_ALIAS,
        "role": "C_primary_official_candidate",
        "capital": OFFICIAL_CANDIDATE_STAGE819_30W_CAPITAL,
        "color": "#16a34a",
    },
)

EXACT_MONTH_STARTS = tuple(
    start
    for start in pd.date_range(DATA_START, DATA_END, freq="MS")
    if (start + pd.DateOffset(years=ROLL_YEARS) - pd.Timedelta(days=1)) <= DATA_END
)


def _month_text(value: pd.Timestamp) -> str:
    return pd.Timestamp(value).strftime("%Y-%m")


def _window_end(start: pd.Timestamp) -> pd.Timestamp:
    return (pd.Timestamp(start) + pd.DateOffset(years=ROLL_YEARS) - pd.Timedelta(days=1)).normalize()


def _window_id(start: pd.Timestamp, end: pd.Timestamp, *, terminal: bool = False) -> str:
    suffix = "_terminal" if terminal else ""
    return f"{_month_text(start).replace('-', '_')}_to_{end.strftime('%Y_%m_%d')}{suffix}"


WINDOWS = [
    {
        "window_id": _window_id(start, _window_end(start)),
        "start": start,
        "end": _window_end(start),
        "terminal_partial": False,
    }
    for start in EXACT_MONTH_STARTS
]
WINDOWS.append(
    {
        "window_id": _window_id(TERMINAL_START, DATA_END, terminal=True),
        "start": TERMINAL_START,
        "end": DATA_END,
        "terminal_partial": True,
    }
)

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
PAIRWISE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_pairwise_{MODEL_TAG}.csv"
AGG_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_aggregate_{MODEL_TAG}.csv"
YEAR_AGG_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_start_year_aggregate_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
RETURN_HEATMAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_return_heatmap_{MODEL_TAG}.png"
DD_HEATMAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_dd_heatmap_{MODEL_TAG}.png"
SHARPE_HEATMAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_sharpe_heatmap_{MODEL_TAG}.png"
WINNER_HEATMAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_winner_heatmap_{MODEL_TAG}.png"
SELECTED_CURVE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_selected_curves_{MODEL_TAG}.png"

_WORKER_METADATA: dict[str, Any] | None = None


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _window_label(start: pd.Timestamp, end: pd.Timestamp, terminal_partial: bool) -> str:
    label = f"{_month_text(start)} to {end.strftime('%Y-%m-%d')}"
    return f"{label} terminal" if terminal_partial else label


def _candidate_profile(
    metadata: dict[str, Any],
    *,
    start: pd.Timestamp,
    end: pd.Timestamp,
    window_id: str,
    terminal_partial: bool,
) -> dict[str, Any]:
    base = s813._profile(metadata, start, enabled=True)
    spec = base["spec"]
    capital = replace(
        spec.capital,
        variant=f"stage824_{OFFICIAL_CANDIDATE_STAGE819_30W_VERSION}_{window_id}",
        label=f"{OFFICIAL_CANDIDATE_STAGE819_30W_ALIAS} {_window_label(start, end, terminal_partial)}",
        account_capital=OFFICIAL_CANDIDATE_STAGE819_30W_CAPITAL,
        c3_capital=OFFICIAL_CANDIDATE_STAGE819_30W_CAPITAL,
        note=(
            f"{spec.capital.note} | Stage824 official-vs-candidate monthly rolling 3y. "
            "Only account_capital/c3_capital are fixed to 300000; Stage813 logic is unchanged."
        ),
    )
    profile = dict(base)
    profile["profile"] = "stage824_stage819_30w_official_candidate_monthly_rolling3y"
    profile["spec"] = replace(spec, capital=capital, profile=profile["profile"])
    profile["arm_key"] = "candidate_stage819_30w"
    profile["series_label"] = OFFICIAL_CANDIDATE_STAGE819_30W_ALIAS
    profile["role"] = "C_primary_official_candidate"
    return profile


def _metric_from_combined(
    *,
    arm_key: str,
    series_label: str,
    role: str,
    combined: pd.DataFrame,
    spec: Any,
    forced_events: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
    window_id: str,
    terminal_partial: bool,
    rsi_count: int = 0,
    rsi_volume: int = 0,
) -> tuple[dict[str, Any], pd.DataFrame]:
    row, curve, _cost_rows = s748._metric_row(
        combined,
        spec=spec,
        window_name=f"{window_id}_monthly_rolling3y",
        window_label=_window_label(start, end, terminal_partial),
        window_group="official_vs_candidate_monthly_rolling_3y",
        forced_events=forced_events,
    )
    row = s772._metric_common(row)
    row["arm_key"] = arm_key
    row["series_label"] = series_label
    row["role"] = role
    row["official_live_version"] = OFFICIAL_LIVE_VERSION
    row["candidate_version"] = OFFICIAL_CANDIDATE_STAGE819_30W_VERSION
    row["requested_start_month"] = _month_text(start)
    row["start_month"] = _month_text(start)
    row["window_start"] = start.strftime("%Y-%m-%d")
    row["window_end"] = end.strftime("%Y-%m-%d")
    row["window_id"] = window_id
    row["rolling_years"] = ROLL_YEARS
    row["terminal_partial"] = int(terminal_partial)
    row["rsi_partial_exit_count"] = int(rsi_count)
    row["rsi_partial_exit_volume"] = int(rsi_volume)
    row["positive_return"] = int(float(row["rebased_total_return_pct"]) > 0.0)

    curve = s772._curve_common(curve)
    curve["arm_key"] = arm_key
    curve["series_label"] = series_label
    curve["role"] = role
    curve["requested_start_month"] = _month_text(start)
    curve["start_month"] = _month_text(start)
    curve["window_start"] = start.strftime("%Y-%m-%d")
    curve["window_end"] = end.strftime("%Y-%m-%d")
    curve["window_id"] = window_id
    curve["rolling_years"] = ROLL_YEARS
    curve["terminal_partial"] = int(terminal_partial)
    return row, curve


def _run_official(metadata: dict[str, Any], window: dict[str, Any]) -> tuple[dict[str, Any], pd.DataFrame]:
    start = pd.Timestamp(window["start"]).normalize()
    end = pd.Timestamp(window["end"]).normalize()
    terminal_partial = bool(window["terminal_partial"])
    spec = s660._official_spec(metadata)
    combined, forced_events = s660._run_independent_window(
        spec=spec,
        metadata=metadata,
        analysis_start=start,
        analysis_end=end,
    )
    return _metric_from_combined(
        arm_key="official_live_20w",
        series_label=f"{OFFICIAL_LIVE_ALIAS} official live",
        role="A_official_live",
        combined=combined,
        spec=spec,
        forced_events=forced_events,
        start=start,
        end=end,
        window_id=str(window["window_id"]),
        terminal_partial=terminal_partial,
    )


def _run_candidate(metadata: dict[str, Any], window: dict[str, Any]) -> tuple[dict[str, Any], pd.DataFrame]:
    start = pd.Timestamp(window["start"]).normalize()
    end = pd.Timestamp(window["end"]).normalize()
    terminal_partial = bool(window["terminal_partial"])
    profile = _candidate_profile(
        metadata,
        start=start,
        end=end,
        window_id=str(window["window_id"]),
        terminal_partial=terminal_partial,
    )
    base_c3_overrides = dict(s513._c3_overrides(pd.Timestamp("2018-01-01").to_pydatetime()))
    combined, frames = s808._run_profile(
        profile=profile,
        start=start,
        end=end,
        metadata=metadata,
        base_c3_overrides=base_c3_overrides,
    )
    trade_events = frames.get("trade_events", pd.DataFrame()).copy()
    if trade_events.empty or "reason" not in trade_events.columns:
        rsi_count = 0
        rsi_volume = 0
    else:
        reason = trade_events["reason"].astype(str)
        rsi_events = trade_events[reason.str.contains("rsi_partial_exit", na=False)].copy()
        rsi_count = int(len(rsi_events))
        rsi_volume = int(pd.to_numeric(rsi_events.get("volume", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
    return _metric_from_combined(
        arm_key="candidate_stage819_30w",
        series_label=OFFICIAL_CANDIDATE_STAGE819_30W_ALIAS,
        role="C_primary_official_candidate",
        combined=combined,
        spec=profile["spec"],
        forced_events=pd.DataFrame(),
        start=start,
        end=end,
        window_id=str(window["window_id"]),
        terminal_partial=terminal_partial,
        rsi_count=rsi_count,
        rsi_volume=rsi_volume,
    )


def _run_one(task: tuple[str, str]) -> tuple[dict[str, Any], pd.DataFrame]:
    global _WORKER_METADATA
    if _WORKER_METADATA is None:
        _WORKER_METADATA = s513._metadata()
    metadata = _WORKER_METADATA
    arm_key, window_id = task
    window_map = {str(item["window_id"]): item for item in WINDOWS}
    window = window_map[window_id]
    if arm_key == "official_live_20w":
        return _run_official(metadata, window)
    if arm_key == "candidate_stage819_30w":
        return _run_candidate(metadata, window)
    raise ValueError(f"unknown arm: {arm_key}")


def _aggregate(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for arm_key, group in summary.groupby("arm_key", sort=False):
        returns = pd.to_numeric(group["rebased_total_return_pct"], errors="coerce")
        dds = pd.to_numeric(group["rebased_max_dd_pct"], errors="coerce")
        sharpes = pd.to_numeric(group["rebased_sharpe"], errors="coerce")
        broker = pd.to_numeric(group["max_broker10_margin_to_rebased_equity_pct"], errors="coerce")
        min_equity = pd.to_numeric(group["rebased_min_equity"], errors="coerce")
        rows.append(
            {
                "arm_key": arm_key,
                "series_label": str(group["series_label"].iloc[0]),
                "role": str(group["role"].iloc[0]),
                "account_capital": float(group["account_capital"].iloc[0]),
                "window_count": int(len(group)),
                "exact_window_count": int((pd.to_numeric(group["terminal_partial"], errors="coerce").fillna(0) == 0).sum()),
                "terminal_window_count": int((pd.to_numeric(group["terminal_partial"], errors="coerce").fillna(0) == 1).sum()),
                "positive_count": int((returns > 0.0).sum()),
                "positive_rate_pct": float((returns > 0.0).mean() * 100.0),
                "median_return_pct": float(returns.median()),
                "p10_return_pct": float(returns.quantile(0.10)),
                "min_return_pct": float(returns.min()),
                "max_return_pct": float(returns.max()),
                "median_dd_pct": float(dds.median()),
                "worst_dd_pct": float(dds.min()),
                "dd30_fail_count": int((dds < -30.0).sum()),
                "dd40_fail_count": int((dds < -40.0).sum()),
                "dd50_fail_count": int((dds < -50.0).sum()),
                "median_sharpe": float(sharpes.median()),
                "p10_sharpe": float(sharpes.quantile(0.10)),
                "min_sharpe": float(sharpes.min()),
                "median_broker10_pct": float(broker.median()),
                "broker100_fail_count": int((broker > 100.0).sum()),
                "survival_fail_count": int((min_equity <= 0.0).sum()),
                "total_trade_count": int(pd.to_numeric(group["total_trade_count"], errors="coerce").fillna(0).sum()),
                "total_slippage": float(pd.to_numeric(group["total_slippage"], errors="coerce").fillna(0).sum()),
                "total_forced_count": int(
                    pd.to_numeric(group.get("forced_margin_deleverage_count", 0), errors="coerce").fillna(0).sum()
                ),
                "total_rsi_partial_exit_count": int(
                    pd.to_numeric(group.get("rsi_partial_exit_count", 0), errors="coerce").fillna(0).sum()
                ),
            }
        )
    return pd.DataFrame(rows)


def _year_aggregate(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (arm_key, start_year), group in summary.groupby(["arm_key", "start_year"], sort=True):
        returns = pd.to_numeric(group["rebased_total_return_pct"], errors="coerce")
        dds = pd.to_numeric(group["rebased_max_dd_pct"], errors="coerce")
        sharpes = pd.to_numeric(group["rebased_sharpe"], errors="coerce")
        rows.append(
            {
                "arm_key": arm_key,
                "start_year": int(start_year),
                "window_count": int(len(group)),
                "positive_count": int((returns > 0.0).sum()),
                "median_return_pct": float(returns.median()),
                "min_return_pct": float(returns.min()),
                "median_dd_pct": float(dds.median()),
                "worst_dd_pct": float(dds.min()),
                "dd40_fail_count": int((dds < -40.0).sum()),
                "dd50_fail_count": int((dds < -50.0).sum()),
                "median_sharpe": float(sharpes.median()),
                "min_sharpe": float(sharpes.min()),
            }
        )
    return pd.DataFrame(rows)


def _comparison(summary: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    pairwise_rows: list[dict[str, Any]] = []
    metric_cols = {
        "return": "rebased_total_return_pct",
        "max_dd": "rebased_max_dd_pct",
        "sharpe": "rebased_sharpe",
        "end_equity": "rebased_end_equity",
        "broker10": "max_broker10_margin_to_rebased_equity_pct",
        "trades": "total_trade_count",
        "slippage": "total_slippage",
    }
    left = "candidate_stage819_30w"
    right = "official_live_20w"
    for window_id, group in summary.groupby("window_id", sort=False):
        indexed = group.set_index("arm_key")
        item: dict[str, Any] = {
            "window_id": window_id,
            "window_start": str(group["window_start"].iloc[0]),
            "window_end": str(group["window_end"].iloc[0]),
            "start_month": str(group["start_month"].iloc[0]),
            "start_year": int(group["start_year"].iloc[0]),
            "start_month_num": int(group["start_month_num"].iloc[0]),
            "terminal_partial": int(group["terminal_partial"].iloc[0]),
        }
        for arm in ARMS:
            key = str(arm["arm_key"])
            row = indexed.loc[key]
            for metric_name, column in metric_cols.items():
                item[f"{metric_name}_{key}"] = float(pd.to_numeric(pd.Series([row[column]]), errors="coerce").iloc[0])
        item["return_delta_candidate_vs_official_pp"] = item[f"return_{left}"] - item[f"return_{right}"]
        item["max_dd_delta_candidate_vs_official_pp"] = item[f"max_dd_{left}"] - item[f"max_dd_{right}"]
        item["sharpe_delta_candidate_vs_official"] = item[f"sharpe_{left}"] - item[f"sharpe_{right}"]
        item["candidate_return_win"] = int(item[f"return_{left}"] > item[f"return_{right}"])
        item["candidate_dd_win"] = int(item[f"max_dd_{left}"] > item[f"max_dd_{right}"])
        item["candidate_sharpe_win"] = int(item[f"sharpe_{left}"] > item[f"sharpe_{right}"])
        item["candidate_double_win"] = int(item["candidate_return_win"] and item["candidate_dd_win"])
        item["return_winner"] = left if item["candidate_return_win"] else right
        item["dd_winner"] = left if item["candidate_dd_win"] else right
        item["sharpe_winner"] = left if item["candidate_sharpe_win"] else right
        rows.append(item)
        pairwise_rows.append(
            {
                "window_id": window_id,
                "window_start": item["window_start"],
                "window_end": item["window_end"],
                "start_month": item["start_month"],
                "terminal_partial": item["terminal_partial"],
                "left": left,
                "right": right,
                "return_delta_pp": item["return_delta_candidate_vs_official_pp"],
                "max_dd_delta_pp": item["max_dd_delta_candidate_vs_official_pp"],
                "sharpe_delta": item["sharpe_delta_candidate_vs_official"],
                "left_return_win": item["candidate_return_win"],
                "left_dd_win": item["candidate_dd_win"],
                "left_sharpe_win": item["candidate_sharpe_win"],
                "left_double_win": item["candidate_double_win"],
            }
        )
    return pd.DataFrame(rows).sort_values("window_start").reset_index(drop=True), pd.DataFrame(pairwise_rows)


def _pairwise_aggregate(pairwise: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (left, right), group in pairwise.groupby(["left", "right"], sort=False):
        rows.append(
            {
                "left": left,
                "right": right,
                "window_count": int(len(group)),
                "left_return_win_count": int(group["left_return_win"].sum()),
                "left_dd_win_count": int(group["left_dd_win"].sum()),
                "left_sharpe_win_count": int(group["left_sharpe_win"].sum()),
                "left_double_win_count": int(group["left_double_win"].sum()),
                "median_return_delta_pp": float(pd.to_numeric(group["return_delta_pp"], errors="coerce").median()),
                "median_dd_delta_pp": float(pd.to_numeric(group["max_dd_delta_pp"], errors="coerce").median()),
                "median_sharpe_delta": float(pd.to_numeric(group["sharpe_delta"], errors="coerce").median()),
                "p10_return_delta_pp": float(pd.to_numeric(group["return_delta_pp"], errors="coerce").quantile(0.10)),
                "p10_dd_delta_pp": float(pd.to_numeric(group["max_dd_delta_pp"], errors="coerce").quantile(0.10)),
            }
        )
    return pd.DataFrame(rows)


def _plot_metric_heatmap(summary: pd.DataFrame, value_column: str, path: Path, title: str, cmap: str, vcenter: float) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(15.5, 6.2), sharey=True)
    values = pd.to_numeric(summary[value_column], errors="coerce")
    if value_column == "rebased_total_return_pct":
        vmin = min(-50.0, float(np.nanpercentile(values, 3)))
        vmax = max(300.0, float(np.nanpercentile(values, 95)))
    elif value_column == "rebased_sharpe":
        vmin = min(-1.0, float(np.nanpercentile(values, 3)))
        vmax = max(2.5, float(np.nanpercentile(values, 95)))
    else:
        vmin = min(-65.0, float(np.nanpercentile(values, 3)))
        vmax = 0.0
    norm = TwoSlopeNorm(vcenter=vcenter, vmin=min(vmin, vcenter - 1e-6), vmax=max(vmax, vcenter + 1e-6))
    im = None
    for ax, arm in zip(axes, ARMS, strict=True):
        data = summary[summary["arm_key"].eq(arm["arm_key"])].copy()
        pivot = data.pivot_table(index="start_year", columns="start_month_num", values=value_column, aggfunc="first")
        im = ax.imshow(pivot.to_numpy(dtype=float), aspect="auto", cmap=cmap, norm=norm)
        ax.set_title(str(arm["series_label"]))
        ax.set_xlabel("Start month")
        ax.set_xticks(range(12))
        ax.set_xticklabels(range(1, 13))
        ax.set_yticks(range(len(pivot.index)))
        ax.set_yticklabels([str(int(item)) for item in pivot.index])
        for i, year in enumerate(pivot.index):
            for j, month in enumerate(pivot.columns):
                value = pivot.loc[year, month]
                if pd.notna(value):
                    ax.text(j, i, f"{value:.0f}", ha="center", va="center", fontsize=7, color="#111827")
    fig.suptitle(title, fontsize=15)
    fig.subplots_adjust(left=0.065, right=0.91, bottom=0.12, top=0.82, wspace=0.08)
    cbar_ax = fig.add_axes([0.93, 0.18, 0.014, 0.58])
    fig.colorbar(im, cax=cbar_ax)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_winner_heatmap(comparison: pd.DataFrame) -> None:
    codes = {"official_live_20w": 0, "candidate_stage819_30w": 1}
    cmap = matplotlib.colors.ListedColormap(["#2563eb", "#16a34a"])
    metrics = [("return_winner", "Return winner"), ("dd_winner", "Drawdown winner"), ("sharpe_winner", "Sharpe winner")]
    fig, axes = plt.subplots(1, 3, figsize=(20, 6.2), sharey=True)
    for ax, (column, title) in zip(axes, metrics, strict=True):
        data = comparison.copy()
        data["winner_code"] = data[column].map(codes)
        pivot = data.pivot_table(index="start_year", columns="start_month_num", values="winner_code", aggfunc="first")
        ax.imshow(pivot.to_numpy(dtype=float), aspect="auto", cmap=cmap, vmin=-0.5, vmax=1.5)
        ax.set_title(title)
        ax.set_xlabel("Start month")
        ax.set_xticks(range(12))
        ax.set_xticklabels(range(1, 13))
        ax.set_yticks(range(len(pivot.index)))
        ax.set_yticklabels([str(int(item)) for item in pivot.index])
        for i, year in enumerate(pivot.index):
            for j, month in enumerate(pivot.columns):
                raw = comparison[comparison["start_year"].eq(year) & comparison["start_month_num"].eq(month)][column]
                if not raw.empty:
                    ax.text(j, i, "C" if raw.iloc[0] == "candidate_stage819_30w" else "A", ha="center", va="center", fontsize=8, color="white")
    handles = [
        plt.Line2D([0], [0], color="#2563eb", lw=6, label="A official"),
        plt.Line2D([0], [0], color="#16a34a", lw=6, label="C candidate"),
    ]
    fig.suptitle("Stage824 official vs candidate monthly rolling 3y winners", fontsize=15)
    fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 0.94), ncol=2, frameon=False)
    fig.subplots_adjust(left=0.055, right=0.99, bottom=0.12, top=0.78, wspace=0.08)
    fig.savefig(WINNER_HEATMAP_PATH, dpi=180)
    plt.close(fig)


def _plot_selected_curves(curves: pd.DataFrame, comparison: pd.DataFrame) -> None:
    selected = ["2020_01_to_2022_12_31", "2021_01_to_2023_12_31", "2022_01_to_2024_12_31", "2023_01_to_2025_12_31"]
    if "2023_06_to_2026_05_29_terminal" in set(comparison["window_id"]):
        selected.append("2023_06_to_2026_05_29_terminal")
    worst_delta = comparison.sort_values("return_delta_candidate_vs_official_pp").head(1)["window_id"].tolist()
    for item in worst_delta:
        if item not in selected:
            selected.append(item)
    frame = curves[curves["window_id"].isin(selected)].copy()
    if frame.empty:
        return
    fig, axes = plt.subplots(2, 1, figsize=(15, 10), sharex=False)
    styles = ["-", "--", "-.", ":", (0, (3, 1, 1, 1)), (0, (5, 2))]
    style_map = {window_id: styles[idx % len(styles)] for idx, window_id in enumerate(selected)}
    color_map = {str(arm["arm_key"]): str(arm["color"]) for arm in ARMS}
    for (arm_key, window_id), group in frame.groupby(["arm_key", "window_id"], sort=False):
        group = group.sort_values("date")
        dates = pd.to_datetime(group["date"], errors="coerce")
        label = f"{'C' if arm_key == 'candidate_stage819_30w' else 'A'} {group['start_month'].iloc[0]}"
        axes[0].plot(
            dates,
            pd.to_numeric(group["rebased_equity"], errors="coerce"),
            label=label,
            color=color_map.get(str(arm_key), "#111827"),
            linestyle=style_map.get(str(window_id), "-"),
            linewidth=1.35,
        )
        axes[1].plot(
            dates,
            pd.to_numeric(group["rebased_nav"], errors="coerce"),
            label=label,
            color=color_map.get(str(arm_key), "#111827"),
            linestyle=style_map.get(str(window_id), "-"),
            linewidth=1.35,
        )
    axes[0].set_title("Selected rolling windows absolute equity")
    axes[0].set_ylabel("Equity")
    axes[1].set_title("Selected rolling windows normalized NAV")
    axes[1].set_ylabel("NAV")
    for ax in axes:
        ax.axhline(1.0, color="#94a3b8", linestyle="--", linewidth=0.8)
        ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.35)
        ax.legend(loc="upper left", ncol=3, fontsize=8)
    fig.suptitle("Stage824 selected monthly rolling 3y curves", fontsize=14)
    fig.tight_layout(rect=(0, 0, 1, 0.965))
    fig.savefig(SELECTED_CURVE_PATH, dpi=170)
    plt.close(fig)


def _decision(aggregate: pd.DataFrame, pairwise_agg: pd.DataFrame, comparison: pd.DataFrame) -> dict[str, Any]:
    agg_map = aggregate.set_index("arm_key").to_dict(orient="index")
    pair = pairwise_agg.iloc[0].to_dict() if not pairwise_agg.empty else {}
    window_count = int(pair.get("window_count", len(comparison)))
    candidate_hard_fail = (
        int(agg_map["candidate_stage819_30w"]["dd40_fail_count"]) > int(agg_map["official_live_20w"]["dd40_fail_count"])
        or int(agg_map["candidate_stage819_30w"]["dd50_fail_count"]) > int(agg_map["official_live_20w"]["dd50_fail_count"])
        or int(agg_map["candidate_stage819_30w"]["broker100_fail_count"]) > 0
        or int(agg_map["candidate_stage819_30w"]["survival_fail_count"]) > 0
    )
    majority = window_count / 2.0
    candidate_majority = (
        int(pair.get("left_return_win_count", 0)) > majority
        and int(pair.get("left_sharpe_win_count", 0)) > majority
        and int(pair.get("left_dd_win_count", 0)) >= majority
    )
    decision_label = (
        "stage824_candidate_next_validation_against_official"
        if candidate_majority and not candidate_hard_fail
        else "stage824_candidate_not_live_default_keep_stage372"
    )
    return {
        "stage": "Stage824",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "window_count": len(WINDOWS),
        "exact_window_count": len(EXACT_MONTH_STARTS),
        "terminal_partial_window": {
            "start": TERMINAL_START.strftime("%Y-%m-%d"),
            "end": DATA_END.strftime("%Y-%m-%d"),
        },
        "common_window_policy": "2020-01 onward common official-live comparable monthly rolling 3-year windows",
        "arms": {
            "A": {
                "arm_key": "official_live_20w",
                "version": OFFICIAL_LIVE_VERSION,
                "capital": OFFICIAL_LIVE_CAPITAL,
            },
            "C": {
                "arm_key": "candidate_stage819_30w",
                "version": OFFICIAL_CANDIDATE_STAGE819_30W_VERSION,
                "capital": OFFICIAL_CANDIDATE_STAGE819_30W_CAPITAL,
            },
        },
        "candidate_manifest": build_official_candidate_stage819_30w_manifest(),
        "aggregate": aggregate.to_dict(orient="records"),
        "pairwise_aggregate": pairwise_agg.to_dict(orient="records"),
        "decision": decision_label,
        "candidate_hard_fail": bool(candidate_hard_fail),
        "candidate_majority": bool(candidate_majority),
        "judgment": (
            "Same-window monthly rolling 3-year comparison. Capital-only or right-tail return wins are not enough; "
            "candidate must also avoid worse DD40/DD50 and broker/survival failures against current official live."
        ),
        "overfit_judgment_before": (
            "low-to-medium: the candidate was already registered and the windows/metrics were predefined; "
            "risk remains that capital sizing and Stage813 logic were selected from prior historical research."
        ),
        "continue_value_before": (
            "yes: this is the direct official-live versus primary-candidate common-window check required before live-default discussion."
        ),
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "curves": str(CURVES_PATH),
            "comparison": str(COMPARISON_PATH),
            "pairwise": str(PAIRWISE_PATH),
            "aggregate": str(AGG_PATH),
            "year_aggregate": str(YEAR_AGG_PATH),
            "report": str(REPORT_PATH),
            "return_heatmap": str(RETURN_HEATMAP_PATH),
            "dd_heatmap": str(DD_HEATMAP_PATH),
            "sharpe_heatmap": str(SHARPE_HEATMAP_PATH),
            "winner_heatmap": str(WINNER_HEATMAP_PATH),
            "selected_curves": str(SELECTED_CURVE_PATH),
            "decision": str(DECISION_PATH),
        },
    }


def _write_report(
    summary: pd.DataFrame,
    aggregate: pd.DataFrame,
    year_agg: pd.DataFrame,
    comparison: pd.DataFrame,
    pairwise_agg: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    best_worst = []
    for arm_key in [str(arm["arm_key"]) for arm in ARMS]:
        group = summary[summary["arm_key"].eq(arm_key)].copy()
        best = group.sort_values("rebased_total_return_pct", ascending=False).iloc[0]
        worst = group.sort_values("rebased_total_return_pct", ascending=True).iloc[0]
        ddworst = group.sort_values("rebased_max_dd_pct", ascending=True).iloc[0]
        best_worst.append(
            {
                "arm_key": arm_key,
                "best_return_window": best["window_id"],
                "best_return_pct": best["rebased_total_return_pct"],
                "worst_return_window": worst["window_id"],
                "worst_return_pct": worst["rebased_total_return_pct"],
                "worst_dd_window": ddworst["window_id"],
                "worst_dd_pct": ddworst["rebased_max_dd_pct"],
            }
        )
    view_cols = [
        "window_id",
        "window_start",
        "window_end",
        "return_official_live_20w",
        "return_candidate_stage819_30w",
        "return_delta_candidate_vs_official_pp",
        "max_dd_official_live_20w",
        "max_dd_candidate_stage819_30w",
        "max_dd_delta_candidate_vs_official_pp",
        "sharpe_official_live_20w",
        "sharpe_candidate_stage819_30w",
        "sharpe_delta_candidate_vs_official",
        "candidate_return_win",
        "candidate_dd_win",
        "candidate_sharpe_win",
    ]
    lines = [
        "# Stage824 线上版 vs Stage819 30万候选月度3年滚动对比",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        f"- A 线上版：`{OFFICIAL_LIVE_VERSION}`，本金 `{OFFICIAL_LIVE_CAPITAL:.0f}`。",
        f"- C 候选版：`{OFFICIAL_CANDIDATE_STAGE819_30W_VERSION}`，本金 `{OFFICIAL_CANDIDATE_STAGE819_30W_CAPITAL:.0f}`。",
        f"- 月度窗口：`{_month_text(EXACT_MONTH_STARTS[0])}` 到 `{_month_text(EXACT_MONTH_STARTS[-1])}` 的完整3年滚动窗口，共 `{len(EXACT_MONTH_STARTS)}` 个；另含 `{_month_text(TERMINAL_START)} -> {DATA_END.strftime('%Y-%m-%d')}` terminal partial。",
        "- 不修改正式配置、不连接 CTP、不调用下单。",
        "",
        "## Aggregate",
        "",
        _md_table(aggregate, max_rows=10),
        "",
        "## Pairwise",
        "",
        _md_table(pairwise_agg, max_rows=10),
        "",
        "## Best/Worst",
        "",
        _md_table(pd.DataFrame(best_worst), max_rows=10),
        "",
        "## Start-Year Aggregate",
        "",
        _md_table(year_agg, max_rows=20),
        "",
        "## Window Sample",
        "",
        _md_table(comparison[view_cols], max_rows=25),
        "",
        "## Decision",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- 判断：{decision['judgment']}",
        "",
        "## Outputs",
        "",
    ]
    for key, path in decision["outputs"].items():
        lines.append(f"- {key}: `{path}`")
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    tasks = [(str(arm["arm_key"]), str(window["window_id"])) for arm in ARMS for window in WINDOWS]
    rows: list[dict[str, Any]] = []
    curves: list[pd.DataFrame] = []
    print(
        f"[stage824] launching {len(tasks)} official-vs-candidate monthly rolling3y runs "
        f"windows={len(WINDOWS)} workers={MAX_WORKERS}",
        flush=True,
    )
    if MAX_WORKERS == 1:
        for idx, task in enumerate(tasks, start=1):
            print(f"[stage824] running {idx}/{len(tasks)} {task[0]} {task[1]}", flush=True)
            row, curve = _run_one(task)
            rows.append(row)
            curves.append(curve)
    else:
        with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_map = {executor.submit(_run_one, task): task for task in tasks}
            for idx, future in enumerate(as_completed(future_map), start=1):
                task = future_map[future]
                row, curve = future.result()
                rows.append(row)
                curves.append(curve)
                print(f"[stage824] completed {idx}/{len(tasks)} {task[0]} {task[1]}", flush=True)

    summary = (
        s772._add_month_fields(pd.DataFrame(rows))
        .sort_values(["window_start", "arm_key"])
        .reset_index(drop=True)
    )
    curve_df = (
        pd.concat(curves, ignore_index=True, sort=False)
        .sort_values(["window_start", "arm_key", "date"])
        .reset_index(drop=True)
    )
    aggregate = _aggregate(summary)
    year_agg = _year_aggregate(summary)
    comparison, pairwise = _comparison(summary)
    pairwise_agg = _pairwise_aggregate(pairwise)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    curve_df.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    pairwise.to_csv(PAIRWISE_PATH, index=False, encoding="utf-8-sig")
    aggregate.to_csv(AGG_PATH, index=False, encoding="utf-8-sig")
    year_agg.to_csv(YEAR_AGG_PATH, index=False, encoding="utf-8-sig")

    _plot_metric_heatmap(
        summary,
        "rebased_total_return_pct",
        RETURN_HEATMAP_PATH,
        "Stage824 monthly rolling 3y return (%)",
        "RdYlGn",
        0.0,
    )
    _plot_metric_heatmap(
        summary,
        "rebased_max_dd_pct",
        DD_HEATMAP_PATH,
        "Stage824 monthly rolling 3y max drawdown (%)",
        "RdYlGn",
        -30.0,
    )
    _plot_metric_heatmap(
        summary,
        "rebased_sharpe",
        SHARPE_HEATMAP_PATH,
        "Stage824 monthly rolling 3y Sharpe",
        "RdYlGn",
        1.0,
    )
    _plot_winner_heatmap(comparison)
    _plot_selected_curves(curve_df, comparison)

    decision = _decision(aggregate, pairwise_agg, comparison)
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(summary, aggregate, year_agg, comparison, pairwise_agg, decision)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print("aggregate")
    print(aggregate.to_string(index=False))
    print("pairwise_aggregate")
    print(pairwise_agg.to_string(index=False))
    print("year_aggregate")
    print(year_agg.to_string(index=False))


if __name__ == "__main__":
    main()
