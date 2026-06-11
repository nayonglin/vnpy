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
import analyze_qmt_roll_stage777_am41_oi08_monthly as s777
import analyze_qmt_roll_stage778_stage777_2022_drawdown_forensics as s778
import analyze_qmt_roll_stage804_stage777_long_tighter_initial_stop_yearly as s804
import analyze_qmt_roll_stage806_stage804_no_long_heat_deleverage_yearly as s806


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage807_stage777_804_806_monthly_v1"
OUTPUT_PREFIX = "qmt_roll_stage807_stage777_804_806_monthly"
LINE_ID = "futures_trend_2019_data_extension"

ANALYSIS_END = pd.Timestamp("2026-05-29")
MONTH_STARTS = s777.MONTH_STARTS
MAX_WORKERS = max(1, min(6, int(os.environ.get("STAGE807_MAX_WORKERS", "4"))))

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
AGG_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_aggregate_{MODEL_TAG}.csv"
PAIRWISE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_pairwise_{MODEL_TAG}.csv"
BEST_ARM_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_best_arm_counts_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
RETURN_HEATMAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_return_heatmaps_{MODEL_TAG}.png"
DD_HEATMAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_dd_heatmaps_{MODEL_TAG}.png"
AGG_BAR_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_aggregate_bar_{MODEL_TAG}.png"
YEARLY_OVERLAY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_yearly_start_equity_overlay_{MODEL_TAG}.png"


_WORKER_METADATA: dict[str, Any] | None = None


ARM_DEFINITIONS: dict[str, dict[str, Any]] = {
    "A777": {
        "label": "A Stage777 official candidate",
        "profile": "stage777_am41_oi08",
        "summary_path": s777.SUMMARY_PATH,
        "curves_path": s777.CURVES_PATH,
        "profile_fn": None,
    },
    "B804": {
        "label": "B Stage804 long tighter stop",
        "profile": "stage804_long_tighter_stop",
        "profile_fn": s804._profile,
    },
    "C806": {
        "label": "C Stage806 no long heat deleverage",
        "profile": "stage806_no_long_heat_deleverage",
        "profile_fn": s806._profile,
    },
}


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _month_text(start: pd.Timestamp) -> str:
    return pd.Timestamp(start).strftime("%Y-%m")


def _load_stage777() -> tuple[pd.DataFrame, pd.DataFrame]:
    summary = pd.read_csv(s777.SUMMARY_PATH)
    summary["start_month"] = summary["start_month"].astype(str)
    summary = summary[summary["start_month"].isin({_month_text(start) for start in MONTH_STARTS})].copy()
    summary["arm"] = "A777"
    summary["arm_label"] = ARM_DEFINITIONS["A777"]["label"]

    curves = pd.read_csv(s777.CURVES_PATH, parse_dates=["date"])
    curves["start_month"] = curves["start_month"].astype(str)
    curves = curves[curves["start_month"].isin(set(summary["start_month"]))].copy()
    curves["arm"] = "A777"
    curves["arm_label"] = ARM_DEFINITIONS["A777"]["label"]
    return (
        summary.sort_values("start_month").reset_index(drop=True),
        curves.sort_values(["start_month", "date"]).reset_index(drop=True),
    )


def _profile_for_arm(arm: str, metadata: dict[str, Any], start: pd.Timestamp) -> dict[str, Any]:
    profile_fn = ARM_DEFINITIONS[arm]["profile_fn"]
    if profile_fn is None:
        raise ValueError(f"{arm} is loaded from cache")
    profile = profile_fn(metadata, start)
    spec = profile["spec"]
    start_text = _month_text(start)
    capital = replace(
        spec.capital,
        variant=f"{spec.capital.variant}_stage807_monthly_{start_text.replace('-', '_')}",
        label=f"{ARM_DEFINITIONS[arm]['label']} monthly {start_text}",
        note=f"{spec.capital.note} | Stage807 monthly-start validation.",
    )
    profile = dict(profile)
    profile["profile"] = ARM_DEFINITIONS[arm]["profile"]
    profile["spec"] = replace(spec, capital=capital, profile=profile["profile"])
    profile["note"] = f"{ARM_DEFINITIONS[arm]['label']} in Stage807 monthly-start validation."
    return profile


def _flat_no_trade_result(arm: str, profile: dict[str, Any], start: pd.Timestamp) -> tuple[dict[str, Any], pd.DataFrame]:
    spec = profile["spec"]
    capital = float(spec.capital.account_capital)
    start_month = _month_text(start)
    row: dict[str, Any] = {
        "variant": spec.capital.variant,
        "label": spec.capital.label,
        "profile": profile["profile"],
        "window_name": s772._window_name(start),
        "window_label": s772._window_label(start),
        "window_group": "monthly_start",
        "analysis_start": start.date().isoformat(),
        "analysis_end": ANALYSIS_END.date().isoformat(),
        "account_capital": capital,
        "c3_capital": capital,
        "risk_multiplier": 0.40,
        "trading_days": 0,
        "end_equity": capital,
        "total_return_pct": 0.0,
        "cagr_pct": 0.0,
        "max_dd_pct": 0.0,
        "ulcer_pct": 0.0,
        "sharpe": 0.0,
        "min_equity": capital,
        "max_broker10_margin_to_equity_pct": 0.0,
        "p95_broker10_margin_to_equity_pct": 0.0,
        "days_over_100pct": 0,
        "days_over_90pct": 0,
        "days_equity_below_zero": 0,
        "total_slippage": 0.0,
        "total_trade_count": 0.0,
        "nonzero_daily_win_rate_pct": 0.0,
        "forced_margin_deleverage_count": 0,
        "forced_margin_deleverage_closed_volume": 0.0,
        "dd30_pass": 1,
        "dd40_pass": 1,
        "broker10_100_pass": 1,
        "account_survival_pass": 1,
        "deployable_pass": 1,
        "source_name": OUTPUT_PREFIX,
        "rebased_end_equity": capital,
        "rebased_total_return_pct": 0.0,
        "rebased_cagr_pct": 0.0,
        "rebased_max_dd_pct": 0.0,
        "rebased_sharpe": 0.0,
        "rebased_min_equity": capital,
        "max_broker10_margin_to_rebased_equity_pct": 0.0,
        "p95_broker10_margin_to_rebased_equity_pct": 0.0,
        "nav_end": 1.0,
        "oi_mode": profile.get("oi_mode"),
        "am_label": profile.get("am_label"),
        "declared_am_size": profile.get("declared_am_size"),
        "note": "No daily result/no trade short window; treated as flat capital for monthly-start audit.",
        "requested_start_month": start_month,
        "start_month": start_month,
        "arm": arm,
        "arm_label": ARM_DEFINITIONS[arm]["label"],
    }
    curve = pd.DataFrame(
        [
            {
                "date": start,
                "variant": spec.capital.variant,
                "label": spec.capital.label,
                "window_name": s772._window_name(start),
                "window_label": s772._window_label(start),
                "window_group": "monthly_start",
                "account_capital": capital,
                "account_equity": capital,
                "nav": 1.0,
                "drawdown_pct": 0.0,
                "broker10_margin_to_equity_pct": 0.0,
                "net_pnl": 0.0,
                "trade_count": 0,
                "total_slippage": 0.0,
                "source_name": OUTPUT_PREFIX,
                "rebased_equity": capital,
                "rebased_nav": 1.0,
                "broker10_margin_to_rebased_equity_pct": 0.0,
                "profile": profile["profile"],
                "oi_mode": profile.get("oi_mode"),
                "am_label": profile.get("am_label"),
                "declared_am_size": profile.get("declared_am_size"),
                "requested_start_month": start_month,
                "start_month": start_month,
                "arm": arm,
                "arm_label": ARM_DEFINITIONS[arm]["label"],
            }
        ]
    )
    return row, curve


def _metric_from_combined(
    arm: str,
    profile: dict[str, Any],
    combined: pd.DataFrame,
    start: pd.Timestamp,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    spec = profile["spec"]
    row, curve, _costs = s748._metric_row(
        combined,
        spec=spec,
        window_name=s772._window_name(start),
        window_label=s772._window_label(start),
        window_group="monthly_start",
        forced_events=pd.DataFrame(),
    )
    row = s772._metric_common(row)
    for key in ["profile", "oi_mode", "am_label", "declared_am_size", "note"]:
        row[key] = profile.get(key)
    row["requested_start_month"] = _month_text(start)
    row["start_month"] = _month_text(start)
    row["arm"] = arm
    row["arm_label"] = ARM_DEFINITIONS[arm]["label"]
    summary = s772._add_month_fields(pd.DataFrame([row]))

    curve = s772._curve_common(curve)
    for key in ["profile", "oi_mode", "am_label", "declared_am_size"]:
        curve[key] = profile.get(key)
    curve["requested_start_month"] = _month_text(start)
    curve["start_month"] = _month_text(start)
    curve["arm"] = arm
    curve["arm_label"] = ARM_DEFINITIONS[arm]["label"]
    return summary, curve


def _run_task(task: dict[str, str]) -> tuple[dict[str, Any], pd.DataFrame]:
    global _WORKER_METADATA
    if _WORKER_METADATA is None:
        _WORKER_METADATA = s513._metadata()
    metadata = _WORKER_METADATA
    arm = task["arm"]
    start = pd.Timestamp(task["start"]).normalize()
    profile = _profile_for_arm(arm, metadata, start)
    base_c3_overrides = dict(task["base_c3_overrides"])
    try:
        combined, _frames = s778._run_profile(
            profile=profile,
            start=start,
            metadata=metadata,
            base_c3_overrides=base_c3_overrides,
        )
        summary, curve = _metric_from_combined(arm, profile, combined, start)
        return summary.iloc[0].to_dict(), curve
    except RuntimeError as exc:
        if "empty daily result" not in str(exc):
            raise
        return _flat_no_trade_result(arm, profile, start)


def _run_monthly_arm(arm: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    base_c3_overrides = dict(s513._c3_overrides(MONTH_STARTS[0].to_pydatetime()))
    tasks = [
        {
            "arm": arm,
            "start": start.strftime("%Y-%m-%d"),
            "base_c3_overrides": base_c3_overrides,
        }
        for start in MONTH_STARTS
    ]
    rows: list[dict[str, Any]] = []
    curves: list[pd.DataFrame] = []
    print(f"[stage807] launching {arm} {len(tasks)} monthly runs workers={MAX_WORKERS}", flush=True)
    if MAX_WORKERS == 1:
        for idx, task in enumerate(tasks, start=1):
            print(f"[stage807] running {arm} {idx}/{len(tasks)} {task['start']}", flush=True)
            row, curve = _run_task(task)
            rows.append(row)
            curves.append(curve)
    else:
        with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_map = {executor.submit(_run_task, task): task for task in tasks}
            for idx, future in enumerate(as_completed(future_map), start=1):
                task = future_map[future]
                row, curve = future.result()
                rows.append(row)
                curves.append(curve)
                print(f"[stage807] completed {arm} {idx}/{len(tasks)} {task['start']}", flush=True)
    summary = s772._add_month_fields(pd.DataFrame(rows)).sort_values("start_month").reset_index(drop=True)
    curves_all = pd.concat(curves, ignore_index=True, sort=False).sort_values(["start_month", "date"]).reset_index(drop=True)
    return summary, curves_all


def _aggregate(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    buckets = [
        ("all", summary),
        ("mature_63d", summary[summary["mature_63d"].eq(1)]),
        ("mature_126d", summary[summary["mature_126d"].eq(1)]),
        ("mature_252d", summary[summary["mature_252d"].eq(1)]),
    ]
    for bucket, frame in buckets:
        for arm, group in frame.groupby("arm", sort=True):
            returns = pd.to_numeric(group["rebased_total_return_pct"], errors="coerce")
            dds = pd.to_numeric(group["rebased_max_dd_pct"], errors="coerce")
            sharpes = pd.to_numeric(group["rebased_sharpe"], errors="coerce")
            trades = pd.to_numeric(group["total_trade_count"], errors="coerce")
            rows.append(
                {
                    "arm": arm,
                    "arm_label": ARM_DEFINITIONS[arm]["label"],
                    "bucket": bucket,
                    "start_count": int(len(group)),
                    "positive_count": int((returns > 0).sum()),
                    "positive_rate_pct": float((returns > 0).mean() * 100.0) if len(group) else 0.0,
                    "median_return_pct": float(returns.median()) if len(group) else 0.0,
                    "p10_return_pct": float(returns.quantile(0.10)) if len(group) else 0.0,
                    "min_return_pct": float(returns.min()) if len(group) else 0.0,
                    "median_dd_pct": float(dds.median()) if len(group) else 0.0,
                    "worst_dd_pct": float(dds.min()) if len(group) else 0.0,
                    "dd30_fail_count": int((dds < -30.0).sum()) if len(group) else 0,
                    "dd40_fail_count": int((dds < -40.0).sum()) if len(group) else 0,
                    "dd50_fail_count": int((dds < -50.0).sum()) if len(group) else 0,
                    "dd60_fail_count": int((dds < -60.0).sum()) if len(group) else 0,
                    "median_sharpe": float(sharpes.median()) if len(group) else 0.0,
                    "trade_count_median": float(trades.median()) if len(group) else 0.0,
                    "trade_count_sum": float(trades.sum()) if len(group) else 0.0,
                    "median_slippage": float(pd.to_numeric(group["total_slippage"], errors="coerce").median())
                    if len(group)
                    else 0.0,
                }
            )
    return pd.DataFrame(rows).sort_values(["bucket", "arm"]).reset_index(drop=True)


def _pairwise(summary: pd.DataFrame) -> pd.DataFrame:
    metrics = [
        "rebased_end_equity",
        "rebased_total_return_pct",
        "rebased_max_dd_pct",
        "rebased_sharpe",
        "total_trade_count",
        "total_slippage",
        "nonzero_daily_win_rate_pct",
    ]
    arms = ["A777", "B804", "C806"]
    base = summary[summary["arm"].eq("A777")].copy()
    rows: list[dict[str, Any]] = []
    for candidate_arm in ["B804", "C806"]:
        candidate = summary[summary["arm"].eq(candidate_arm)].copy()
        merged = base.merge(candidate, on="start_month", suffixes=("_base", "_candidate"), how="inner")
        for bucket, frame in [("all", merged), ("mature_252d", merged[merged["mature_252d_base"].eq(1)])]:
            record: dict[str, Any] = {
                "base_arm": "A777",
                "candidate_arm": candidate_arm,
                "bucket": bucket,
                "start_count": int(len(frame)),
            }
            for metric in metrics:
                base_values = pd.to_numeric(frame[f"{metric}_base"], errors="coerce")
                cand_values = pd.to_numeric(frame[f"{metric}_candidate"], errors="coerce")
                delta = cand_values - base_values
                record[f"{metric}_win_count"] = int(delta.gt(0).sum())
                record[f"{metric}_median_delta"] = float(delta.median()) if len(delta) else 0.0
                record[f"{metric}_min_delta"] = float(delta.min()) if len(delta) else 0.0
                record[f"{metric}_max_delta"] = float(delta.max()) if len(delta) else 0.0
            rows.append(record)

    base = summary[summary["arm"].eq("B804")].copy()
    candidate = summary[summary["arm"].eq("C806")].copy()
    merged = base.merge(candidate, on="start_month", suffixes=("_base", "_candidate"), how="inner")
    for bucket, frame in [("all", merged), ("mature_252d", merged[merged["mature_252d_base"].eq(1)])]:
        record = {
            "base_arm": "B804",
            "candidate_arm": "C806",
            "bucket": bucket,
            "start_count": int(len(frame)),
        }
        for metric in metrics:
            base_values = pd.to_numeric(frame[f"{metric}_base"], errors="coerce")
            cand_values = pd.to_numeric(frame[f"{metric}_candidate"], errors="coerce")
            delta = cand_values - base_values
            record[f"{metric}_win_count"] = int(delta.gt(0).sum())
            record[f"{metric}_median_delta"] = float(delta.median()) if len(delta) else 0.0
            record[f"{metric}_min_delta"] = float(delta.min()) if len(delta) else 0.0
            record[f"{metric}_max_delta"] = float(delta.max()) if len(delta) else 0.0
        rows.append(record)
    return pd.DataFrame(rows)


def _best_arm_counts(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for bucket, frame in [
        ("all", summary),
        ("mature_252d", summary[summary["mature_252d"].eq(1)]),
    ]:
        for metric, ascending in [
            ("rebased_total_return_pct", False),
            ("rebased_max_dd_pct", False),
            ("rebased_sharpe", False),
        ]:
            counts = {arm: 0 for arm in ARM_DEFINITIONS}
            for _start_month, group in frame.groupby("start_month", sort=True):
                values = pd.to_numeric(group[metric], errors="coerce")
                if values.notna().any():
                    best_idx = values.idxmin() if ascending else values.idxmax()
                    counts[str(group.loc[best_idx, "arm"])] += 1
            for arm, count in counts.items():
                rows.append({"bucket": bucket, "metric": metric, "arm": arm, "best_count": count})
    return pd.DataFrame(rows)


def _plot_three_heatmaps(summary: pd.DataFrame, value_column: str, path: Path, title: str, cmap: str, vcenter: float) -> None:
    values = pd.to_numeric(summary[value_column], errors="coerce")
    if value_column == "rebased_total_return_pct":
        vmin = -100.0
        vmax = max(400.0, float(np.nanpercentile(values, 90)))
    else:
        vmin = min(-65.0, float(np.nanpercentile(values, 3)))
        vmax = 0.0
    norm = TwoSlopeNorm(vcenter=vcenter, vmin=min(vmin, vcenter - 1e-6), vmax=max(vmax, vcenter + 1e-6))
    fig, axes = plt.subplots(3, 1, figsize=(17, 13), constrained_layout=True)
    for ax, arm in zip(axes, ["A777", "B804", "C806"], strict=False):
        data = summary[summary["arm"].eq(arm)].copy()
        pivot = data.pivot_table(index="start_year", columns="start_month_num", values=value_column, aggfunc="first")
        im = ax.imshow(pivot.to_numpy(dtype=float), aspect="auto", cmap=cmap, norm=norm)
        ax.set_title(ARM_DEFINITIONS[arm]["label"])
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
                    ax.text(j, i, f"{value:.0f}", ha="center", va="center", fontsize=7, color="#111827")
    fig.suptitle(title)
    fig.colorbar(im, ax=axes.ravel().tolist(), shrink=0.78)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _plot_aggregate_bar(aggregate: pd.DataFrame) -> None:
    view = aggregate[aggregate["bucket"].eq("mature_252d")].copy()
    x = np.arange(len(view))
    fig, axes = plt.subplots(2, 2, figsize=(14, 9), constrained_layout=True)
    labels = view["arm"].tolist()
    axes[0, 0].bar(x, view["median_return_pct"], color="#2563eb")
    axes[0, 0].set_title("Mature median return %")
    axes[0, 1].bar(x, view["p10_return_pct"], color="#0f766e")
    axes[0, 1].set_title("Mature p10 return %")
    axes[1, 0].bar(x, view["worst_dd_pct"], color="#dc2626")
    axes[1, 0].set_title("Mature worst max DD %")
    axes[1, 1].bar(x, view["dd50_fail_count"], color="#9333ea")
    axes[1, 1].set_title("Mature DD50 fail count")
    for ax in axes.ravel():
        ax.set_xticks(x)
        ax.set_xticklabels(labels)
        ax.grid(axis="y", alpha=0.25)
    fig.suptitle("Stage807 mature monthly-start aggregate")
    fig.savefig(AGG_BAR_PATH, dpi=180)
    plt.close(fig)


def _plot_yearly_overlay(curves: pd.DataFrame) -> None:
    starts = [f"{year}-01" for year in range(2018, 2027)]
    fig, axes = plt.subplots(3, 3, figsize=(18, 12), sharex=False)
    axes = axes.ravel()
    for ax, start_month in zip(axes, starts, strict=False):
        for arm, color in [("A777", "#1f77b4"), ("B804", "#ff7f0e"), ("C806", "#2ca02c")]:
            frame = curves[curves["arm"].eq(arm) & curves["start_month"].astype(str).eq(start_month)].copy()
            if frame.empty:
                continue
            ax.plot(
                pd.to_datetime(frame["date"]),
                pd.to_numeric(frame["rebased_equity"], errors="coerce") / 1_000_000,
                label=arm,
                linewidth=1.15,
                color=color,
            )
        ax.axhline(0.5, color="#9ca3af", linestyle="--", linewidth=0.8)
        ax.set_title(start_month)
        ax.grid(alpha=0.22)
        ax.tick_params(axis="x", labelrotation=25, labelsize=8)
        ax.tick_params(axis="y", labelsize=8)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=3)
    fig.suptitle("Stage807 yearly-start equity overlay from monthly run", y=0.995)
    fig.tight_layout(rect=[0, 0, 1, 0.965])
    fig.savefig(YEARLY_OVERLAY_PATH, dpi=170)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    aggregate: pd.DataFrame,
    pairwise: pd.DataFrame,
    best: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    mature = aggregate[aggregate["bucket"].eq("mature_252d")].copy()
    lines = [
        "# Stage807 Stage777/804/806 逐月启动验证",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 起点：`{MONTH_STARTS[0].strftime('%Y-%m')}` 到 `{MONTH_STARTS[-1].strftime('%Y-%m')}`；终点 `{ANALYSIS_END.date()}`。",
        "- A：Stage777 官方候选月度缓存。",
        "- B：Stage804，即 Stage777 + 多头更紧初始止损。",
        "- C：Stage806，即 Stage804 + 关闭多头 risk-cluster heat deleverage。",
        "",
        "## Mature Aggregate",
        "",
        _md_table(mature, max_rows=20),
        "",
        "## Pairwise",
        "",
        _md_table(pairwise, max_rows=20),
        "",
        "## Best Arm Counts",
        "",
        _md_table(best, max_rows=30),
        "",
        "## Decision",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- 判断：{decision['judgment']}",
        f"- 过拟合反思：{decision['overfit_judgment']}",
        f"- 继续价值：{decision['continue_value']}",
        "",
        "## Worst 10 by Return",
        "",
        _md_table(
            summary.sort_values("rebased_total_return_pct")[
                ["arm", "start_month", "rebased_total_return_pct", "rebased_max_dd_pct", "rebased_sharpe", "total_trade_count"]
            ].head(10),
            max_rows=10,
        ),
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    a_summary, a_curves = _load_stage777()
    b_summary, b_curves = _run_monthly_arm("B804")
    c_summary, c_curves = _run_monthly_arm("C806")
    summary = pd.concat([a_summary, b_summary, c_summary], ignore_index=True, sort=False)
    summary = s772._add_month_fields(summary).sort_values(["arm", "start_month"]).reset_index(drop=True)
    curves = (
        pd.concat([a_curves, b_curves, c_curves], ignore_index=True, sort=False)
        .sort_values(["arm", "start_month", "date"])
        .reset_index(drop=True)
    )
    aggregate = _aggregate(summary)
    pairwise = _pairwise(summary)
    best = _best_arm_counts(summary)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    aggregate.to_csv(AGG_PATH, index=False, encoding="utf-8-sig")
    pairwise.to_csv(PAIRWISE_PATH, index=False, encoding="utf-8-sig")
    best.to_csv(BEST_ARM_PATH, index=False, encoding="utf-8-sig")
    _plot_three_heatmaps(summary, "rebased_total_return_pct", RETURN_HEATMAP_PATH, "Stage807 monthly start final return %", "RdYlGn", 0.0)
    _plot_three_heatmaps(summary, "rebased_max_dd_pct", DD_HEATMAP_PATH, "Stage807 monthly start max DD %", "RdYlGn", -40.0)
    _plot_aggregate_bar(aggregate)
    _plot_yearly_overlay(curves)

    mature = aggregate[aggregate["bucket"].eq("mature_252d")].copy()
    decision_label = "stage807_monthly_804_806_not_promoted"
    decision = {
        "stage": "Stage807",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "decision": decision_label,
        "judgment": (
            "Monthly starts validate whether Stage804/806 improve Stage777 broadly. Promotion requires return breadth "
            "without materially expanding DD50/DD60 failures."
        ),
        "mature_aggregate": mature.to_dict("records"),
        "pairwise": pairwise.to_dict("records"),
        "best_arm_counts": best.to_dict("records"),
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "curves": str(CURVES_PATH),
            "aggregate": str(AGG_PATH),
            "pairwise": str(PAIRWISE_PATH),
            "best": str(BEST_ARM_PATH),
            "return_heatmap": str(RETURN_HEATMAP_PATH),
            "dd_heatmap": str(DD_HEATMAP_PATH),
            "aggregate_bar": str(AGG_BAR_PATH),
            "yearly_overlay": str(YEARLY_OVERLAY_PATH),
            "report": str(REPORT_PATH),
        },
        "overfit_judgment": (
            "medium before results: Stage804/806 came from a concrete stop/heat-deleverage interaction, but also from "
            "observed 2025 right-tail behavior. Monthly starts are the anti-overfit check."
        ),
        "continue_value": (
            "yes for validation; further parameter rescue is valuable only if monthly results show broad risk-adjusted "
            "improvement instead of isolated right-tail repair."
        ),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(summary, aggregate, pairwise, best, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print("mature aggregate")
    print(mature.to_string(index=False))
    print("pairwise")
    print(pairwise.to_string(index=False))
    print("best")
    print(best.to_string(index=False))


if __name__ == "__main__":
    main()
