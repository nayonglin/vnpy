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
import analyze_qmt_roll_stage748_half_risk_no_streak_500k as s748
import analyze_qmt_roll_stage772_am40_80_120_oi_monthly as s772
import analyze_qmt_roll_stage778_stage777_2022_drawdown_forensics as s778
import analyze_qmt_roll_stage804_stage777_long_tighter_initial_stop_yearly as s804
import analyze_qmt_roll_stage808_stage806_rolling3y as s808


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage809_stage804_rolling3y_v1"
OUTPUT_PREFIX = "qmt_roll_stage809_stage804_rolling3y"
LINE_ID = "futures_trend_2019_data_extension"

DATA_END = pd.Timestamp("2026-05-29")
ROLL_YEARS = 3
MONTH_STARTS = tuple(
    start
    for start in pd.date_range("2018-01-01", DATA_END, freq="MS")
    if (start + pd.DateOffset(years=ROLL_YEARS) - pd.Timedelta(days=1)) <= DATA_END
)
MAX_WORKERS = max(1, min(6, int(os.environ.get("STAGE809_MAX_WORKERS", "4"))))

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
AGG_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_aggregate_{MODEL_TAG}.csv"
YEAR_AGG_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_start_year_aggregate_{MODEL_TAG}.csv"
COMPARISON_806_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_vs_stage806_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
RETURN_HEATMAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_return_heatmap_{MODEL_TAG}.png"
DD_HEATMAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_dd_heatmap_{MODEL_TAG}.png"
EQUITY_SELECTED_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_selected_equity_curves_{MODEL_TAG}.png"
RETURN_DELTA_HEATMAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_return_delta_vs_stage806_heatmap_{MODEL_TAG}.png"
DD_DELTA_HEATMAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_dd_delta_vs_stage806_heatmap_{MODEL_TAG}.png"


_WORKER_METADATA: dict[str, Any] | None = None


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _month_text(start: pd.Timestamp) -> str:
    return pd.Timestamp(start).strftime("%Y-%m")


def _window_end(start: pd.Timestamp) -> pd.Timestamp:
    return (pd.Timestamp(start) + pd.DateOffset(years=ROLL_YEARS) - pd.Timedelta(days=1)).normalize()


def _window_name(start: pd.Timestamp, end: pd.Timestamp) -> str:
    return f"{_month_text(start)}_to_{end.strftime('%Y-%m-%d')}_rolling3y"


def _window_label(start: pd.Timestamp, end: pd.Timestamp) -> str:
    return f"{_month_text(start)} rolling 3y to {end.strftime('%Y-%m-%d')}"


def _profile(metadata: dict[str, Any], start: pd.Timestamp, end: pd.Timestamp) -> dict[str, Any]:
    profile = s804._profile(metadata, start)
    spec = profile["spec"]
    start_text = _month_text(start)
    end_text = end.strftime("%Y_%m_%d")
    capital = replace(
        spec.capital,
        variant=f"stage809_stage804_rolling3y_{start_text.replace('-', '_')}_to_{end_text}",
        label=f"Stage809 Stage804 rolling3y {start_text} to {end.strftime('%Y-%m-%d')}",
        note=(
            f"{spec.capital.note} | Stage809 rolling 3y validation. "
            "Stage804 keeps long risk-cluster heat deleverage enabled."
        ),
    )
    result = dict(profile)
    result["profile"] = "stage809_stage804_rolling3y"
    result["spec"] = replace(spec, capital=capital, profile=result["profile"])
    result["note"] = (
        "Stage804 rolling three-year validation; long risk-cluster heat deleverage enabled."
    )
    return result


def _metric_from_combined(
    profile: dict[str, Any],
    combined: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    spec = profile["spec"]
    row, curve, _costs = s748._metric_row(
        combined,
        spec=spec,
        window_name=_window_name(start, end),
        window_label=_window_label(start, end),
        window_group="rolling_3y",
        forced_events=pd.DataFrame(),
    )
    row = s772._metric_common(row)
    for key in ["profile", "oi_mode", "am_label", "declared_am_size", "note"]:
        row[key] = profile.get(key)
    row["requested_start_month"] = _month_text(start)
    row["start_month"] = _month_text(start)
    row["window_start"] = start.strftime("%Y-%m-%d")
    row["window_end"] = end.strftime("%Y-%m-%d")
    row["rolling_years"] = ROLL_YEARS
    summary = s772._add_month_fields(pd.DataFrame([row]))

    curve = s772._curve_common(curve)
    for key in ["profile", "oi_mode", "am_label", "declared_am_size"]:
        curve[key] = profile.get(key)
    curve["requested_start_month"] = _month_text(start)
    curve["start_month"] = _month_text(start)
    curve["window_start"] = start.strftime("%Y-%m-%d")
    curve["window_end"] = end.strftime("%Y-%m-%d")
    curve["rolling_years"] = ROLL_YEARS
    return summary, curve


def _run_one(start_text: str) -> tuple[dict[str, Any], pd.DataFrame]:
    global _WORKER_METADATA
    if _WORKER_METADATA is None:
        _WORKER_METADATA = s513._metadata()
    metadata = _WORKER_METADATA
    start = pd.Timestamp(start_text).normalize()
    end = _window_end(start)
    profile = _profile(metadata, start, end)
    base_c3_overrides = dict(s513._c3_overrides(MONTH_STARTS[0].to_pydatetime()))
    combined, frames = s808._run_profile(
        profile=profile,
        start=start,
        end=end,
        metadata=metadata,
        base_c3_overrides=base_c3_overrides,
    )
    summary, curve = _metric_from_combined(profile, combined, start, end)
    row = summary.iloc[0].to_dict()
    trade_events = frames.get("trade_events", pd.DataFrame()).copy()
    if trade_events.empty or "reason" not in trade_events.columns:
        row["long_heat_deleverage_exit_count"] = 0
        row["short_heat_deleverage_exit_count"] = 0
    else:
        reason = trade_events["reason"].astype(str)
        offset = trade_events.get("offset", pd.Series("", index=trade_events.index)).astype(str)
        row["long_heat_deleverage_exit_count"] = int(
            (reason.eq("long_risk_cluster_heat_deleverage") & offset.eq("Close")).sum()
        )
        row["short_heat_deleverage_exit_count"] = int(
            (reason.eq("short_risk_cluster_heat_deleverage") & offset.eq("Close")).sum()
        )
    return row, curve


def _aggregate(summary: pd.DataFrame) -> pd.DataFrame:
    aggregate = s808._aggregate(summary)
    aggregate["total_long_heat_deleverage_exits"] = int(
        pd.to_numeric(summary.get("long_heat_deleverage_exit_count", 0), errors="coerce").fillna(0).sum()
    )
    aggregate["total_short_heat_deleverage_exits"] = int(
        pd.to_numeric(summary.get("short_heat_deleverage_exit_count", 0), errors="coerce").fillna(0).sum()
    )
    return aggregate


def _year_aggregate(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    frame = summary.copy()
    for start_year, group in frame.groupby("start_year", sort=True):
        returns = pd.to_numeric(group["rebased_total_return_pct"], errors="coerce")
        dds = pd.to_numeric(group["rebased_max_dd_pct"], errors="coerce")
        rows.append(
            {
                "start_year": int(start_year),
                "window_count": int(len(group)),
                "positive_count": int((returns > 0).sum()),
                "median_return_pct": float(returns.median()),
                "min_return_pct": float(returns.min()),
                "p10_return_pct": float(returns.quantile(0.10)),
                "median_dd_pct": float(dds.median()),
                "worst_dd_pct": float(dds.min()),
                "dd40_fail_count": int((dds < -40.0).sum()),
                "dd50_fail_count": int((dds < -50.0).sum()),
                "dd60_fail_count": int((dds < -60.0).sum()),
                "median_sharpe": float(pd.to_numeric(group["rebased_sharpe"], errors="coerce").median()),
                "total_long_heat_deleverage_exits": int(
                    pd.to_numeric(group.get("long_heat_deleverage_exit_count", 0), errors="coerce").fillna(0).sum()
                ),
            }
        )
    return pd.DataFrame(rows)


def _plot_heatmap(summary: pd.DataFrame, value_column: str, path: Path, title: str, cmap: str, vcenter: float) -> None:
    pivot = summary.pivot_table(index="start_year", columns="start_month_num", values=value_column, aggfunc="first")
    values = pd.to_numeric(summary[value_column], errors="coerce")
    if value_column.endswith("delta"):
        vmin = float(np.nanpercentile(values, 5))
        vmax = float(np.nanpercentile(values, 95))
        spread = max(abs(vmin), abs(vmax), 1.0)
        vmin, vmax = -spread, spread
    elif value_column == "rebased_total_return_pct":
        vmin = min(-50.0, float(np.nanpercentile(values, 5)))
        vmax = max(300.0, float(np.nanpercentile(values, 95)))
    else:
        vmin = min(-65.0, float(np.nanpercentile(values, 3)))
        vmax = 0.0
    norm = TwoSlopeNorm(vcenter=vcenter, vmin=min(vmin, vcenter - 1e-6), vmax=max(vmax, vcenter + 1e-6))
    fig, ax = plt.subplots(figsize=(15, 6.8))
    im = ax.imshow(pivot.to_numpy(dtype=float), aspect="auto", cmap=cmap, norm=norm)
    ax.set_title(title)
    ax.set_xlabel("Start month")
    ax.set_ylabel("Start year")
    ax.set_xticks(range(12))
    ax.set_xticklabels(range(1, 13))
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels([str(int(item)) for item in pivot.index])
    for i, year in enumerate(pivot.index):
        for j, month in enumerate(pivot.columns):
            value = pivot.loc[year, month]
            if pd.notna(value):
                ax.text(j, i, f"{value:.0f}", ha="center", va="center", fontsize=8, color="#111827")
    fig.colorbar(im, ax=ax, shrink=0.85)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_selected_equity(curves: pd.DataFrame, summary: pd.DataFrame) -> None:
    selected: set[str] = set()
    for column, ascending, count in [
        ("rebased_total_return_pct", True, 3),
        ("rebased_total_return_pct", False, 3),
        ("rebased_max_dd_pct", True, 4),
    ]:
        for _, row in summary.sort_values(column, ascending=ascending).head(count).iterrows():
            selected.add(str(row["start_month"]))
    for month in ["2018-01", "2019-01", "2020-01", "2021-01", "2022-01", "2023-01", "2023-05"]:
        if month in set(summary["start_month"].astype(str)):
            selected.add(month)
    data = curves[curves["start_month"].astype(str).isin(sorted(selected))].copy()
    fig, ax = plt.subplots(figsize=(16, 8))
    colors = plt.cm.tab20.colors
    for idx, (start_month, group) in enumerate(data.groupby("start_month", sort=True)):
        group = group.sort_values("date")
        ax.plot(
            pd.to_datetime(group["date"]),
            pd.to_numeric(group["rebased_equity"], errors="coerce") / 1_000_000,
            label=f"{start_month} -> {str(group['window_end'].iloc[0])}",
            linewidth=1.5,
            color=colors[idx % len(colors)],
            alpha=0.9,
        )
    ax.axhline(0.5, color="#9ca3af", linestyle="--", linewidth=1)
    ax.set_title("Stage809 Stage804 selected rolling 3y equity curves")
    ax.set_xlabel("Date")
    ax.set_ylabel("Account equity")
    ax.yaxis.set_major_formatter(lambda x, pos: f"{x:.1f}M")
    ax.grid(alpha=0.25)
    ax.legend(ncol=3, fontsize=8)
    fig.tight_layout()
    fig.savefig(EQUITY_SELECTED_PATH, dpi=180)
    plt.close(fig)


def _comparison_vs_stage806(summary: pd.DataFrame) -> pd.DataFrame:
    if not s808.SUMMARY_PATH.exists():
        return pd.DataFrame()
    base = pd.read_csv(s808.SUMMARY_PATH)
    keys = ["start_month", "window_end"]
    left = summary.copy()
    right = base.copy()
    for key in keys:
        left[key] = left[key].astype(str)
        right[key] = right[key].astype(str)
    comparison = left.merge(
        right[
            [
                *keys,
                "rebased_total_return_pct",
                "rebased_max_dd_pct",
                "rebased_sharpe",
                "total_trade_count",
            ]
        ],
        on=keys,
        how="left",
        suffixes=("_stage804", "_stage806"),
    )
    comparison["return_pct_delta"] = (
        pd.to_numeric(comparison["rebased_total_return_pct_stage804"], errors="coerce")
        - pd.to_numeric(comparison["rebased_total_return_pct_stage806"], errors="coerce")
    )
    comparison["max_dd_pct_delta"] = (
        pd.to_numeric(comparison["rebased_max_dd_pct_stage804"], errors="coerce")
        - pd.to_numeric(comparison["rebased_max_dd_pct_stage806"], errors="coerce")
    )
    comparison["sharpe_delta"] = (
        pd.to_numeric(comparison["rebased_sharpe_stage804"], errors="coerce")
        - pd.to_numeric(comparison["rebased_sharpe_stage806"], errors="coerce")
    )
    return comparison


def _write_report(
    summary: pd.DataFrame,
    aggregate: pd.DataFrame,
    year_agg: pd.DataFrame,
    comparison: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    lines = [
        "# Stage809 Stage804滚动3年多周期回测",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 完整三年起点：`{MONTH_STARTS[0].strftime('%Y-%m')}` 到 `{MONTH_STARTS[-1].strftime('%Y-%m')}`，共 `{len(MONTH_STARTS)}` 个。",
        "- 口径：Stage804，即 Stage777 + 多头更紧初始止损；`long_risk_cluster_heat_deleverage` 重新打开。",
        "- 窗口定义：每个起点独立跑三年，结束日为 `start + 3 years - 1 day`。",
        "",
        "## Aggregate",
        "",
        _md_table(aggregate, max_rows=10),
        "",
        "## Start Year Aggregate",
        "",
        _md_table(year_agg, max_rows=20),
        "",
        "## Worst DD Windows",
        "",
        _md_table(
            summary.sort_values("rebased_max_dd_pct")[
                [
                    "start_month",
                    "window_end",
                    "rebased_total_return_pct",
                    "rebased_max_dd_pct",
                    "rebased_sharpe",
                    "total_trade_count",
                    "long_heat_deleverage_exit_count",
                ]
            ].head(12),
            max_rows=12,
        ),
        "",
        "## Worst Return Windows",
        "",
        _md_table(
            summary.sort_values("rebased_total_return_pct")[
                [
                    "start_month",
                    "window_end",
                    "rebased_total_return_pct",
                    "rebased_max_dd_pct",
                    "rebased_sharpe",
                    "total_trade_count",
                    "long_heat_deleverage_exit_count",
                ]
            ].head(12),
            max_rows=12,
        ),
    ]
    if not comparison.empty:
        lines.extend(
            [
                "",
                "## Comparison vs Stage806",
                "",
                _md_table(
                    comparison[
                        [
                            "start_month",
                            "window_end",
                            "rebased_total_return_pct_stage804",
                            "rebased_total_return_pct_stage806",
                            "return_pct_delta",
                            "rebased_max_dd_pct_stage804",
                            "rebased_max_dd_pct_stage806",
                            "max_dd_pct_delta",
                            "sharpe_delta",
                            "long_heat_deleverage_exit_count",
                        ]
                    ].sort_values("return_pct_delta").head(15),
                    max_rows=15,
                ),
            ]
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            f"- 决策：`{decision['decision']}`",
            f"- 判断：{decision['judgment']}",
            f"- 过拟合反思：{decision['overfit_judgment']}",
            f"- 继续价值：{decision['continue_value']}",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    tasks = [start.strftime("%Y-%m-%d") for start in MONTH_STARTS]
    rows: list[dict[str, Any]] = []
    curves: list[pd.DataFrame] = []
    print(f"[stage809] launching Stage804 rolling3y runs={len(tasks)} workers={MAX_WORKERS}", flush=True)
    if MAX_WORKERS == 1:
        for idx, task in enumerate(tasks, start=1):
            print(f"[stage809] running {idx}/{len(tasks)} {task}", flush=True)
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
                print(f"[stage809] completed {idx}/{len(tasks)} {task}", flush=True)

    summary = s772._add_month_fields(pd.DataFrame(rows)).sort_values("start_month").reset_index(drop=True)
    curves_all = pd.concat(curves, ignore_index=True, sort=False).sort_values(["start_month", "date"]).reset_index(drop=True)
    aggregate = _aggregate(summary)
    year_agg = _year_aggregate(summary)
    comparison = _comparison_vs_stage806(summary)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    curves_all.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    aggregate.to_csv(AGG_PATH, index=False, encoding="utf-8-sig")
    year_agg.to_csv(YEAR_AGG_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_806_PATH, index=False, encoding="utf-8-sig")
    _plot_heatmap(summary, "rebased_total_return_pct", RETURN_HEATMAP_PATH, "Stage809 Stage804 rolling 3y return %", "RdYlGn", 0.0)
    _plot_heatmap(summary, "rebased_max_dd_pct", DD_HEATMAP_PATH, "Stage809 Stage804 rolling 3y max DD %", "RdYlGn", -40.0)
    _plot_selected_equity(curves_all, summary)
    if not comparison.empty:
        _plot_heatmap(
            comparison.rename(columns={"return_pct_delta": "stage804_vs_806_delta"}),
            "stage804_vs_806_delta",
            RETURN_DELTA_HEATMAP_PATH,
            "Stage809 Stage804 - Stage806 rolling 3y return delta pp",
            "RdYlGn",
            0.0,
        )
        _plot_heatmap(
            comparison.rename(columns={"max_dd_pct_delta": "stage804_vs_806_delta"}),
            "stage804_vs_806_delta",
            DD_DELTA_HEATMAP_PATH,
            "Stage809 Stage804 - Stage806 rolling 3y max DD delta pp",
            "RdYlGn",
            0.0,
        )

    agg_row = aggregate.iloc[0].to_dict()
    comparison_stats: dict[str, Any] = {}
    if not comparison.empty:
        ret_delta = pd.to_numeric(comparison["return_pct_delta"], errors="coerce")
        dd_delta = pd.to_numeric(comparison["max_dd_pct_delta"], errors="coerce")
        comparison_stats = {
            "return_win_vs_stage806_count": int((ret_delta > 0).sum()),
            "dd_win_vs_stage806_count": int((dd_delta > 0).sum()),
            "median_return_delta_pp": float(ret_delta.median()),
            "median_dd_delta_pp": float(dd_delta.median()),
            "dd50_fail_stage804_count": int((pd.to_numeric(comparison["rebased_max_dd_pct_stage804"], errors="coerce") < -50.0).sum()),
            "dd50_fail_stage806_count": int((pd.to_numeric(comparison["rebased_max_dd_pct_stage806"], errors="coerce") < -50.0).sum()),
            "dd60_fail_stage804_count": int((pd.to_numeric(comparison["rebased_max_dd_pct_stage804"], errors="coerce") < -60.0).sum()),
            "dd60_fail_stage806_count": int((pd.to_numeric(comparison["rebased_max_dd_pct_stage806"], errors="coerce") < -60.0).sum()),
        }
    decision = {
        "stage": "Stage809",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "decision": "stage809_stage804_rolling3y_completed_not_promoted",
        "judgment": (
            "This validates Stage804 with long risk-cluster heat deleverage reopened on the same rolling "
            "three-year lifecycle used for Stage806. Promotion requires lower tail risk without destroying "
            "the right-tail participation."
        ),
        "aggregate": agg_row,
        "year_aggregate": year_agg.to_dict("records"),
        "comparison_vs_stage806": comparison_stats,
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "curves": str(CURVES_PATH),
            "aggregate": str(AGG_PATH),
            "year_aggregate": str(YEAR_AGG_PATH),
            "comparison_vs_stage806": str(COMPARISON_806_PATH),
            "return_heatmap": str(RETURN_HEATMAP_PATH),
            "dd_heatmap": str(DD_HEATMAP_PATH),
            "selected_equity": str(EQUITY_SELECTED_PATH),
            "return_delta_heatmap": str(RETURN_DELTA_HEATMAP_PATH),
            "dd_delta_heatmap": str(DD_DELTA_HEATMAP_PATH),
            "report": str(REPORT_PATH),
        },
        "overfit_judgment": (
            "low before results: this is the pre-existing Stage804 risk-control toggle rerun on the same "
            "rolling window, not a new parameter search."
        ),
        "continue_value": (
            "yes for comparing heat deleverage trade-offs; no value in tuning the toggle by specific year/month."
        ),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(summary, aggregate, year_agg, comparison, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print("aggregate")
    print(aggregate.to_string(index=False))
    print("start year aggregate")
    print(year_agg.to_string(index=False))
    if not comparison.empty:
        print("comparison vs stage806")
        print(pd.DataFrame([comparison_stats]).to_string(index=False))
    print("worst dd")
    print(
        summary.sort_values("rebased_max_dd_pct")[
            [
                "start_month",
                "window_end",
                "rebased_total_return_pct",
                "rebased_max_dd_pct",
                "rebased_sharpe",
                "total_trade_count",
                "long_heat_deleverage_exit_count",
            ]
        ]
        .head(12)
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
