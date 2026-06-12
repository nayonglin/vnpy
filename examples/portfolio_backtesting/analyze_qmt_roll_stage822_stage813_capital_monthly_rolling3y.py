from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
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
import analyze_qmt_roll_stage748_half_risk_no_streak_500k as s748
import analyze_qmt_roll_stage772_am40_80_120_oi_monthly as s772
import analyze_qmt_roll_stage808_stage806_rolling3y as s808
import analyze_qmt_roll_stage813_stage804_rsi_partial_exit_ablation_yearly as s813


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage822_stage813_capital_monthly_rolling3y_v1"
OUTPUT_PREFIX = "qmt_roll_stage822_stage813_capital_monthly_rolling3y"
LINE_ID = "futures_trend_2019_data_extension"

DATA_END = pd.Timestamp("2026-05-29")
ROLL_YEARS = 3
MAX_WORKERS = max(1, min(8, int(os.environ.get("STAGE822_MAX_WORKERS", "6"))))

CAPITALS = [
    ("50w", 500_000.0, "Stage813 50w", "#1d4ed8"),
    ("30w", 300_000.0, "Stage819 30w", "#16a34a"),
    ("20w", 200_000.0, "Stage817 20w", "#dc2626"),
]

EXACT_MONTH_STARTS = tuple(
    start
    for start in pd.date_range("2018-01-01", DATA_END, freq="MS")
    if (start + pd.DateOffset(years=ROLL_YEARS) - pd.Timedelta(days=1)) <= DATA_END
)
TERMINAL_START = pd.Timestamp("2023-06-01")


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
PAIRWISE_AGG_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_pairwise_aggregate_{MODEL_TAG}.csv"
YEAR_AGG_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_start_year_aggregate_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
RETURN_HEATMAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_return_heatmap_{MODEL_TAG}.png"
DD_HEATMAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_dd_heatmap_{MODEL_TAG}.png"
SHARPE_HEATMAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_sharpe_heatmap_{MODEL_TAG}.png"
WINNER_HEATMAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_winner_heatmap_{MODEL_TAG}.png"

_WORKER_METADATA: dict[str, Any] | None = None


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _window_label(start: pd.Timestamp, end: pd.Timestamp, terminal_partial: bool) -> str:
    label = f"{_month_text(start)} to {end.strftime('%Y-%m-%d')}"
    return f"{label} terminal" if terminal_partial else label


def _capital_profile(
    metadata: dict[str, Any],
    *,
    capital_key: str,
    capital_value: float,
    display_label: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
    window_id: str,
    terminal_partial: bool,
) -> dict[str, Any]:
    base = s813._profile(metadata, start, enabled=True)
    spec = base["spec"]
    capital = replace(
        spec.capital,
        variant=f"stage822_stage813_{capital_key}_monthly_rolling3y_{window_id}",
        label=f"{display_label} monthly rolling3y {_window_label(start, end, terminal_partial)}",
        account_capital=capital_value,
        c3_capital=capital_value,
        note=(
            f"{spec.capital.note} | Stage822 monthly rolling 3y capital comparison. "
            f"account_capital/c3_capital={capital_value:.0f}; Stage813 logic unchanged."
        ),
    )
    profile = dict(base)
    profile["profile"] = f"stage822_stage813_{capital_key}_monthly_rolling3y"
    profile["spec"] = replace(spec, capital=capital, profile=profile["profile"])
    profile["capital_key"] = capital_key
    profile["display_label"] = display_label
    profile["note"] = (
        "Stage813 AM41/OI0.8/old-AI/maxpos4/long tighter stop/RSI95 partial exit; "
        f"capital only changed to {capital_value:.0f}."
    )
    return profile


def _metric_from_combined(
    profile: dict[str, Any],
    combined: pd.DataFrame,
    *,
    start: pd.Timestamp,
    end: pd.Timestamp,
    window_id: str,
    terminal_partial: bool,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    spec = profile["spec"]
    row, curve, _costs = s748._metric_row(
        combined,
        spec=spec,
        window_name=f"{window_id}_monthly_rolling3y",
        window_label=_window_label(start, end, terminal_partial),
        window_group="monthly_rolling_3y_capital",
        forced_events=pd.DataFrame(),
    )
    row = s772._metric_common(row)
    for key in ["profile", "oi_mode", "am_label", "declared_am_size", "note"]:
        row[key] = profile.get(key)
    row["capital_key"] = profile["capital_key"]
    row["series_label"] = profile["display_label"]
    row["requested_start_month"] = _month_text(start)
    row["start_month"] = _month_text(start)
    row["window_start"] = start.strftime("%Y-%m-%d")
    row["window_end"] = end.strftime("%Y-%m-%d")
    row["window_id"] = window_id
    row["rolling_years"] = ROLL_YEARS
    row["terminal_partial"] = int(terminal_partial)
    row["positive_return"] = int(float(row.get("rebased_total_return_pct", row.get("total_return_pct", 0.0))) > 0.0)
    summary = s772._add_month_fields(pd.DataFrame([row]))

    curve = s772._curve_common(curve)
    for key in ["profile", "oi_mode", "am_label", "declared_am_size"]:
        curve[key] = profile.get(key)
    curve["capital_key"] = profile["capital_key"]
    curve["series_label"] = profile["display_label"]
    curve["requested_start_month"] = _month_text(start)
    curve["start_month"] = _month_text(start)
    curve["window_start"] = start.strftime("%Y-%m-%d")
    curve["window_end"] = end.strftime("%Y-%m-%d")
    curve["window_id"] = window_id
    curve["rolling_years"] = ROLL_YEARS
    curve["terminal_partial"] = int(terminal_partial)
    return summary, curve


def _run_one(task: tuple[str, str]) -> tuple[dict[str, Any], pd.DataFrame]:
    global _WORKER_METADATA
    capital_key, window_id = task
    capital_map = {key: (value, label) for key, value, label, _color in CAPITALS}
    window_map = {item["window_id"]: item for item in WINDOWS}
    capital_value, display_label = capital_map[capital_key]
    window = window_map[window_id]
    start = pd.Timestamp(window["start"]).normalize()
    end = pd.Timestamp(window["end"]).normalize()
    terminal_partial = bool(window["terminal_partial"])
    if _WORKER_METADATA is None:
        _WORKER_METADATA = s513._metadata()
    metadata = _WORKER_METADATA
    base_c3_overrides = dict(s513._c3_overrides(pd.Timestamp("2018-01-01").to_pydatetime()))
    profile = _capital_profile(
        metadata,
        capital_key=capital_key,
        capital_value=capital_value,
        display_label=display_label,
        start=start,
        end=end,
        window_id=window_id,
        terminal_partial=terminal_partial,
    )
    combined, frames = s808._run_profile(
        profile=profile,
        start=start,
        end=end,
        metadata=metadata,
        base_c3_overrides=base_c3_overrides,
    )
    summary, curve = _metric_from_combined(
        profile,
        combined,
        start=start,
        end=end,
        window_id=window_id,
        terminal_partial=terminal_partial,
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
    row = summary.iloc[0].to_dict()
    row["rsi_partial_exit_count"] = rsi_count
    row["rsi_partial_exit_volume"] = rsi_volume
    return row, curve


def _aggregate(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for capital_key, group in summary.groupby("capital_key", sort=False):
        returns = pd.to_numeric(group["rebased_total_return_pct"], errors="coerce")
        dds = pd.to_numeric(group["rebased_max_dd_pct"], errors="coerce")
        sharpes = pd.to_numeric(group["rebased_sharpe"], errors="coerce")
        broker = pd.to_numeric(group["max_broker10_margin_to_rebased_equity_pct"], errors="coerce")
        min_equity = pd.to_numeric(group["rebased_min_equity"], errors="coerce")
        rows.append(
            {
                "capital_key": capital_key,
                "series_label": str(group["series_label"].iloc[0]),
                "window_count": int(len(group)),
                "exact_window_count": int((pd.to_numeric(group["terminal_partial"], errors="coerce").fillna(0) == 0).sum()),
                "terminal_window_count": int((pd.to_numeric(group["terminal_partial"], errors="coerce").fillna(0) == 1).sum()),
                "positive_count": int((returns > 0).sum()),
                "positive_rate_pct": float((returns > 0).mean() * 100.0),
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
                "total_rsi_partial_exit_count": int(
                    pd.to_numeric(group.get("rsi_partial_exit_count", 0), errors="coerce").fillna(0).sum()
                ),
            }
        )
    return pd.DataFrame(rows)


def _year_aggregate(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (capital_key, start_year), group in summary.groupby(["capital_key", "start_year"], sort=True):
        returns = pd.to_numeric(group["rebased_total_return_pct"], errors="coerce")
        dds = pd.to_numeric(group["rebased_max_dd_pct"], errors="coerce")
        sharpes = pd.to_numeric(group["rebased_sharpe"], errors="coerce")
        rows.append(
            {
                "capital_key": capital_key,
                "start_year": int(start_year),
                "window_count": int(len(group)),
                "positive_count": int((returns > 0).sum()),
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
    pairs = [("30w", "50w"), ("20w", "50w"), ("30w", "20w")]
    for window_id, group in summary.groupby("window_id", sort=False):
        item: dict[str, Any] = {
            "window_id": window_id,
            "window_start": str(group["window_start"].iloc[0]),
            "window_end": str(group["window_end"].iloc[0]),
            "start_month": str(group["start_month"].iloc[0]),
            "start_year": int(group["start_year"].iloc[0]),
            "start_month_num": int(group["start_month_num"].iloc[0]),
            "terminal_partial": int(group["terminal_partial"].iloc[0]),
        }
        indexed = group.set_index("capital_key")
        for key, _capital, _label, _color in CAPITALS:
            row = indexed.loc[key]
            for metric_name, column in metric_cols.items():
                item[f"{metric_name}_{key}"] = float(pd.to_numeric(pd.Series([row[column]]), errors="coerce").iloc[0])
        item["return_winner"] = max(CAPITALS, key=lambda c: item[f"return_{c[0]}"])[0]
        item["dd_winner"] = max(CAPITALS, key=lambda c: item[f"max_dd_{c[0]}"])[0]
        item["sharpe_winner"] = max(CAPITALS, key=lambda c: item[f"sharpe_{c[0]}"])[0]
        item["double_return_dd_winner"] = item["return_winner"] if item["return_winner"] == item["dd_winner"] else ""
        rows.append(item)
        for left, right in pairs:
            pairwise_rows.append(
                {
                    "window_id": window_id,
                    "window_start": item["window_start"],
                    "window_end": item["window_end"],
                    "start_month": item["start_month"],
                    "terminal_partial": item["terminal_partial"],
                    "left": left,
                    "right": right,
                    "return_delta_pp": item[f"return_{left}"] - item[f"return_{right}"],
                    "max_dd_delta_pp": item[f"max_dd_{left}"] - item[f"max_dd_{right}"],
                    "sharpe_delta": item[f"sharpe_{left}"] - item[f"sharpe_{right}"],
                    "left_return_win": int(item[f"return_{left}"] > item[f"return_{right}"]),
                    "left_dd_win": int(item[f"max_dd_{left}"] > item[f"max_dd_{right}"]),
                    "left_sharpe_win": int(item[f"sharpe_{left}"] > item[f"sharpe_{right}"]),
                    "left_double_win": int(
                        item[f"return_{left}"] > item[f"return_{right}"]
                        and item[f"max_dd_{left}"] > item[f"max_dd_{right}"]
                    ),
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
    fig, axes = plt.subplots(1, 3, figsize=(22, 6.2), sharey=True)
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
    for ax, (capital_key, _capital, label, _color) in zip(axes, CAPITALS, strict=True):
        data = summary[summary["capital_key"].eq(capital_key)].copy()
        pivot = data.pivot_table(index="start_year", columns="start_month_num", values=value_column, aggfunc="first")
        im = ax.imshow(pivot.to_numpy(dtype=float), aspect="auto", cmap=cmap, norm=norm)
        ax.set_title(label)
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
    fig.subplots_adjust(left=0.055, right=0.93, bottom=0.12, top=0.82, wspace=0.08)
    cbar_ax = fig.add_axes([0.945, 0.18, 0.012, 0.58])
    fig.colorbar(im, cax=cbar_ax)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_winner_heatmap(comparison: pd.DataFrame) -> None:
    color_map = {"50w": 0, "30w": 1, "20w": 2, "": np.nan}
    labels = ["50w", "30w", "20w"]
    metrics = [("return_winner", "Return winner"), ("dd_winner", "Drawdown winner"), ("sharpe_winner", "Sharpe winner")]
    fig, axes = plt.subplots(1, 3, figsize=(21, 6.2), sharey=True)
    cmap = matplotlib.colors.ListedColormap(["#1d4ed8", "#16a34a", "#dc2626"])
    for ax, (column, title) in zip(axes, metrics, strict=True):
        data = comparison.copy()
        data["winner_code"] = data[column].map(color_map)
        pivot = data.pivot_table(index="start_year", columns="start_month_num", values="winner_code", aggfunc="first")
        im = ax.imshow(pivot.to_numpy(dtype=float), aspect="auto", cmap=cmap, vmin=-0.5, vmax=2.5)
        ax.set_title(title)
        ax.set_xlabel("Start month")
        ax.set_xticks(range(12))
        ax.set_xticklabels(range(1, 13))
        ax.set_yticks(range(len(pivot.index)))
        ax.set_yticklabels([str(int(item)) for item in pivot.index])
        for i, year in enumerate(pivot.index):
            for j, month in enumerate(pivot.columns):
                raw = comparison[
                    comparison["start_year"].eq(year) & comparison["start_month_num"].eq(month)
                ][column]
                if not raw.empty:
                    ax.text(j, i, str(raw.iloc[0]), ha="center", va="center", fontsize=7, color="white")
    handles = [
        plt.Line2D([0], [0], color="#1d4ed8", lw=6, label=labels[0]),
        plt.Line2D([0], [0], color="#16a34a", lw=6, label=labels[1]),
        plt.Line2D([0], [0], color="#dc2626", lw=6, label=labels[2]),
    ]
    fig.suptitle("Stage822 monthly rolling 3y winners by start month", fontsize=15)
    fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 0.94), ncol=3, frameon=False)
    fig.subplots_adjust(left=0.055, right=0.99, bottom=0.12, top=0.78, wspace=0.08)
    fig.savefig(WINNER_HEATMAP_PATH, dpi=180)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    aggregate: pd.DataFrame,
    year_agg: pd.DataFrame,
    comparison: pd.DataFrame,
    pairwise_agg: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    best_worst = []
    for capital_key in [key for key, _capital, _label, _color in CAPITALS]:
        group = summary[summary["capital_key"].eq(capital_key)].copy()
        best = group.sort_values("rebased_total_return_pct", ascending=False).iloc[0]
        worst = group.sort_values("rebased_total_return_pct", ascending=True).iloc[0]
        ddworst = group.sort_values("rebased_max_dd_pct", ascending=True).iloc[0]
        best_worst.append(
            {
                "capital_key": capital_key,
                "best_return_window": best["window_id"],
                "best_return_pct": best["rebased_total_return_pct"],
                "worst_return_window": worst["window_id"],
                "worst_return_pct": worst["rebased_total_return_pct"],
                "worst_dd_window": ddworst["window_id"],
                "worst_dd_pct": ddworst["rebased_max_dd_pct"],
            }
        )
    best_worst_df = pd.DataFrame(best_worst)
    lines = [
        "# Stage822 Stage813 20w/30w/50w monthly rolling 3y capital comparison",
        "",
        f"- line_id: `{LINE_ID}`",
        f"- model_tag: `{MODEL_TAG}`",
        f"- exact monthly windows: `{len(EXACT_MONTH_STARTS)}` from `{_month_text(EXACT_MONTH_STARTS[0])}` to `{_month_text(EXACT_MONTH_STARTS[-1])}`",
        f"- terminal partial window: `{_month_text(TERMINAL_START)} to {DATA_END.strftime('%Y-%m-%d')}`",
        "- No official config change, no CTP connection, no order submission.",
        "",
        "## Aggregate By Capital",
        "",
        _md_table(aggregate, max_rows=10),
        "",
        "## Pairwise Aggregate",
        "",
        _md_table(pairwise_agg, max_rows=10),
        "",
        "## Best/Worst Windows",
        "",
        _md_table(best_worst_df, max_rows=10),
        "",
        "## Start-Year Aggregate",
        "",
        _md_table(year_agg, max_rows=30),
        "",
        "## Window Comparison Sample",
        "",
        _md_table(
            comparison[
                [
                    "window_id",
                    "window_start",
                    "window_end",
                    "return_50w",
                    "return_30w",
                    "return_20w",
                    "max_dd_50w",
                    "max_dd_30w",
                    "max_dd_20w",
                    "sharpe_50w",
                    "sharpe_30w",
                    "sharpe_20w",
                    "return_winner",
                    "dd_winner",
                    "sharpe_winner",
                ]
            ],
            max_rows=20,
        ),
        "",
        "## Outputs",
        "",
        f"- summary: `{SUMMARY_PATH}`",
        f"- curves: `{CURVES_PATH}`",
        f"- comparison: `{COMPARISON_PATH}`",
        f"- pairwise: `{PAIRWISE_PATH}`",
        f"- aggregate: `{AGG_PATH}`",
        f"- pairwise_aggregate: `{PAIRWISE_AGG_PATH}`",
        f"- year_aggregate: `{YEAR_AGG_PATH}`",
        f"- return_heatmap: `{RETURN_HEATMAP_PATH}`",
        f"- dd_heatmap: `{DD_HEATMAP_PATH}`",
        f"- sharpe_heatmap: `{SHARPE_HEATMAP_PATH}`",
        f"- winner_heatmap: `{WINNER_HEATMAP_PATH}`",
        "",
        "## Decision",
        "",
        f"- decision: `{decision['decision']}`",
        f"- judgment: {decision['judgment']}",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    tasks = [
        (capital_key, str(window["window_id"]))
        for capital_key, _capital, _label, _color in CAPITALS
        for window in WINDOWS
    ]
    rows: list[dict[str, Any]] = []
    curves: list[pd.DataFrame] = []
    print(
        f"[stage822] launching {len(tasks)} monthly rolling3y capital runs "
        f"windows={len(WINDOWS)} workers={MAX_WORKERS}",
        flush=True,
    )
    if MAX_WORKERS == 1:
        for idx, task in enumerate(tasks, start=1):
            print(f"[stage822] running {idx}/{len(tasks)} {task[0]} {task[1]}", flush=True)
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
                print(f"[stage822] completed {idx}/{len(tasks)} {task[0]} {task[1]}", flush=True)

    summary = (
        s772._add_month_fields(pd.DataFrame(rows))
        .sort_values(["window_start", "capital_key"])
        .reset_index(drop=True)
    )
    curve_df = (
        pd.concat(curves, ignore_index=True, sort=False)
        .sort_values(["window_start", "capital_key", "date"])
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
    pairwise_agg.to_csv(PAIRWISE_AGG_PATH, index=False, encoding="utf-8-sig")
    year_agg.to_csv(YEAR_AGG_PATH, index=False, encoding="utf-8-sig")

    _plot_metric_heatmap(
        summary,
        "rebased_total_return_pct",
        RETURN_HEATMAP_PATH,
        "Stage822 monthly rolling 3y return (%)",
        "RdYlGn",
        0.0,
    )
    _plot_metric_heatmap(
        summary,
        "rebased_max_dd_pct",
        DD_HEATMAP_PATH,
        "Stage822 monthly rolling 3y max drawdown (%)",
        "RdYlGn",
        -30.0,
    )
    _plot_metric_heatmap(
        summary,
        "rebased_sharpe",
        SHARPE_HEATMAP_PATH,
        "Stage822 monthly rolling 3y Sharpe",
        "RdYlGn",
        1.0,
    )
    _plot_winner_heatmap(comparison)

    agg_map = aggregate.set_index("capital_key").to_dict(orient="index")
    pair_map = {f"{row.left}_vs_{row.right}": row._asdict() for row in pairwise_agg.itertuples(index=False)}
    hard_fail_30w = (
        int(agg_map["30w"]["dd40_fail_count"]) > int(agg_map["50w"]["dd40_fail_count"])
        or int(agg_map["30w"]["broker100_fail_count"]) > 0
        or int(agg_map["30w"]["survival_fail_count"]) > 0
    )
    decision_label = "stage822_30w_watch_not_promoted" if hard_fail_30w else "stage822_30w_next_validation"
    decision = {
        "stage": "Stage822",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "window_count": len(WINDOWS),
        "exact_window_count": len(EXACT_MONTH_STARTS),
        "terminal_partial_window": {
            "start": TERMINAL_START.strftime("%Y-%m-%d"),
            "end": DATA_END.strftime("%Y-%m-%d"),
        },
        "arms": {
            "50w": "Stage813 official-candidate logic, account/c3 capital 500000",
            "30w": "Stage813 logic, account/c3 capital 300000",
            "20w": "Stage813 logic, account/c3 capital 200000",
        },
        "aggregate": aggregate.to_dict(orient="records"),
        "pairwise_aggregate": pairwise_agg.to_dict(orient="records"),
        "decision": decision_label,
        "judgment": (
            "Monthly rolling 3y capital comparison. This is a deployment sensitivity and path robustness check; "
            "capital-only leadership is not enough for formal promotion without drawdown robustness."
        ),
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "curves": str(CURVES_PATH),
            "comparison": str(COMPARISON_PATH),
            "pairwise": str(PAIRWISE_PATH),
            "aggregate": str(AGG_PATH),
            "pairwise_aggregate": str(PAIRWISE_AGG_PATH),
            "year_aggregate": str(YEAR_AGG_PATH),
            "report": str(REPORT_PATH),
            "return_heatmap": str(RETURN_HEATMAP_PATH),
            "dd_heatmap": str(DD_HEATMAP_PATH),
            "sharpe_heatmap": str(SHARPE_HEATMAP_PATH),
            "winner_heatmap": str(WINNER_HEATMAP_PATH),
        },
    }
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
