from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
from datetime import datetime
import json
import math
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
import analyze_qmt_roll_stage757_c50_oi_confirm_risk_restore as s757
import analyze_qmt_roll_stage772_am40_80_120_oi_monthly as s772
import analyze_qmt_roll_stage777_am41_oi08_monthly as s777
import analyze_qmt_roll_stage781_am41_oi08_streak8_monthly as s781


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage783_am41_oi08_dd20_half_monthly_v1"
OUTPUT_PREFIX = "qmt_roll_stage783_am41_oi08_dd20_half_monthly"
LINE_ID = "futures_trend_2019_data_extension"

ANALYSIS_END = pd.Timestamp("2026-05-29")
MONTH_STARTS = tuple(pd.date_range("2018-01-01", "2026-05-01", freq="MS"))
MAX_WORKERS = max(1, min(6, int(os.environ.get("STAGE783_MAX_WORKERS", "6"))))

CANDIDATE_VARIANT = "stage783_500k_am41_oi08_dd20_half_monthly"
CANDIDATE_LABEL = "Stage783 AM41 OI0.8 halves all entries when account DD > 20%"
PROFILE_NAME = "stage783_am41_oi08_dd20_half"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
PROFILE_AGG_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_profile_aggregate_{MODEL_TAG}.csv"
PHASE_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_phase_summary_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_vs_stage777_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
RETURN_HEATMAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_return_heatmap_{MODEL_TAG}.png"
DD_HEATMAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_dd_heatmap_{MODEL_TAG}.png"
DELTA_HEATMAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_delta_vs_stage777_heatmap_{MODEL_TAG}.png"
EQUITY_CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_equity_curves_selected_{MODEL_TAG}.png"

_WORKER_METADATA: dict[str, Any] | None = None
_WORKER_PROFILE: dict[str, Any] | None = None


class QmtRollPortfolioStrategyExactAmDD20Half(s772.QmtRollPortfolioStrategyExactAm):
    """Research-only wrapper: final entry/add size is halved when account DD is above 20%."""

    def _portfolio_drawdown_gate_weight_value(self) -> float:
        threshold = max(0.0, float(self.portfolio_drawdown_gate_start_pct or 0.0))
        floor = self._clip01(float(self.portfolio_drawdown_gate_weight_floor or 0.0))
        drawdown = max(0.0, float(self.portfolio_drawdown_pct or 0.0))
        return floor if drawdown > threshold + 1e-12 else 1.0

    def _calculate_entry_sizing(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        entry_context = str(kwargs.get("entry_context", "flat_entry"))
        if len(args) >= 8 and "entry_context" not in kwargs:
            entry_context = str(args[7])

        sizing = dict(super()._calculate_entry_sizing(*args, **kwargs))
        enabled = int(
            bool(self.enable_portfolio_drawdown_gate)
            and self._portfolio_drawdown_gate_context_applies(entry_context)
        )
        selected_before = max(0, int(sizing.get("selected_volume") or 0))
        weight = self._portfolio_drawdown_gate_weight_value() if enabled else 1.0
        selected_after = selected_before
        if enabled:
            selected_after = int(math.floor(selected_before * weight))
            if 0 < selected_after < self.min_position_size:
                selected_after = 0
            sizing["selected_volume"] = max(0, selected_after)
        sizing.update(
            {
                "portfolio_drawdown_gate_enabled": enabled,
                "portfolio_drawdown_gate_weight": float(weight),
                "portfolio_drawdown_gate_start_pct": float(self.portfolio_drawdown_gate_start_pct or 0.0),
                "portfolio_drawdown_gate_full_pct": float(self.portfolio_drawdown_gate_full_pct or 0.0),
                "portfolio_drawdown_gate_weight_floor": float(self.portfolio_drawdown_gate_weight_floor or 0.0),
                "portfolio_drawdown_gate_entry_context": entry_context,
                "portfolio_drawdown_gate_selected_volume_before": selected_before,
                "portfolio_drawdown_gate_selected_volume_after": max(0, selected_after),
                "portfolio_drawdown_gate_volume_reduced": int(max(0, selected_after) < selected_before),
                "portfolio_drawdown_pct": float(self.portfolio_drawdown_pct or 0.0),
            }
        )
        return sizing


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _candidate_profile(metadata: dict[str, Any]) -> dict[str, Any]:
    base = s757._candidate_spec(metadata)
    capital = replace(
        base.capital,
        variant=CANDIDATE_VARIANT,
        label=CANDIDATE_LABEL,
        note=(
            "Stage777 AM41/OI0.8 logic, plus account-level drawdown defense: when current account "
            "equity drawdown from high water mark is above 20%, every entry/add/rollover reopen "
            "volume is multiplied by 0.5 after the normal sizing and OI restore logic."
        ),
    )
    overrides = {
        **base.overrides,
        "array_manager_size_floor": 40,
        "research_exact_array_manager_size": 41,
        "enable_portfolio_drawdown_gate": True,
        "portfolio_drawdown_gate_start_pct": 0.20,
        "portfolio_drawdown_gate_full_pct": 0.20,
        "portfolio_drawdown_gate_weight_floor": 0.50,
        "portfolio_drawdown_gate_entry_contexts": "*",
        "streak_risk_multipliers": "1.0,1.0,1.0,1.0",
        "enable_streak_entry_structure_risk_recovery": False,
        "enable_recovery_sleeve": False,
    }
    spec = replace(base, capital=capital, overrides=overrides, profile=PROFILE_NAME)
    return {
        "profile": PROFILE_NAME,
        "oi_mode": "oi_restore",
        "am_label": "am40",
        "declared_am_size": 41,
        "strategy_cls": QmtRollPortfolioStrategyExactAmDD20Half,
        "spec": spec,
        "note": "Research-only AM41 plus OI0.8; final entry/add size is halved when account DD > 20%.",
    }


def _rewrite_outputs(
    row: dict[str, Any],
    costs: list[dict[str, Any]],
    curve: pd.DataFrame,
) -> tuple[dict[str, Any], list[dict[str, Any]], pd.DataFrame]:
    row = dict(row)
    row.update(
        {
            "variant": CANDIDATE_VARIANT,
            "label": CANDIDATE_LABEL,
            "profile": PROFILE_NAME,
            "source_name": "stage783_am41_oi08_dd20_half_monthly",
            "oi_mode": "oi_restore",
            "am_label": "am40",
            "declared_am_size": 41,
            "portfolio_drawdown_gate_threshold_pct": 20.0,
            "portfolio_drawdown_gate_weight_floor": 0.50,
            "portfolio_drawdown_gate_entry_contexts": "*",
            "note": "Stage777 plus final 0.5x entry/add size when account drawdown > 20%.",
        }
    )
    for cost in costs:
        cost.update(
            {
                "variant": CANDIDATE_VARIANT,
                "label": CANDIDATE_LABEL,
                "profile": PROFILE_NAME,
                "source_name": "stage783_am41_oi08_dd20_half_monthly",
                "oi_mode": "oi_restore",
                "am_label": "am40",
                "declared_am_size": 41,
            }
        )
    frame = curve.copy()
    frame["variant"] = CANDIDATE_VARIANT
    frame["label"] = CANDIDATE_LABEL
    frame["profile"] = PROFILE_NAME
    frame["source_name"] = "stage783_am41_oi08_dd20_half_monthly"
    frame["oi_mode"] = "oi_restore"
    frame["am_label"] = "am40"
    frame["declared_am_size"] = 41
    return row, costs, frame


def _run_one(task: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]], pd.DataFrame]:
    global _WORKER_METADATA, _WORKER_PROFILE
    if _WORKER_METADATA is None:
        _WORKER_METADATA = s513._metadata()
        _WORKER_PROFILE = _candidate_profile(_WORKER_METADATA)
    metadata = _WORKER_METADATA
    profile = _WORKER_PROFILE
    if profile is None:
        raise RuntimeError("missing worker profile")
    start = pd.Timestamp(task["start"])
    try:
        frame, forced_events = s772._run_engine(
            profile=profile,
            start=start,
            metadata=metadata,
            base_c3_overrides=dict(task["base_c3_overrides"]),
        )
    except RuntimeError as exc:
        if "empty daily result" not in str(exc):
            raise
        row, costs, curve = s781._flat_no_trade_result(task)
        return _rewrite_outputs(row, costs, curve)
    spec = profile["spec"]
    row, curve, costs = s772.s748._metric_row(
        frame,
        spec=spec,
        window_name=s772._window_name(start),
        window_label=s772._window_label(start),
        window_group="monthly_start",
        forced_events=forced_events,
    )
    row = s772._metric_common(row)
    row["requested_start_month"] = start.strftime("%Y-%m")
    row["start_month"] = start.strftime("%Y-%m")
    curve = s772._curve_common(curve)
    curve["requested_start_month"] = start.strftime("%Y-%m")
    curve["start_month"] = start.strftime("%Y-%m")
    for cost in costs:
        cost["requested_start_month"] = start.strftime("%Y-%m")
        cost["start_month"] = start.strftime("%Y-%m")
    return _rewrite_outputs(row, costs, curve)


def _run_all() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    metadata = s513._metadata()
    if not metadata:
        raise RuntimeError("empty metadata")
    base_c3_overrides = dict(s513._c3_overrides(MONTH_STARTS[0].to_pydatetime()))
    tasks = [{"start": start.strftime("%Y-%m-%d"), "base_c3_overrides": base_c3_overrides} for start in MONTH_STARTS]

    rows: list[dict[str, Any]] = []
    cost_rows: list[dict[str, Any]] = []
    curves: list[pd.DataFrame] = []
    print(f"[stage783] launching {len(tasks)} monthly runs workers={MAX_WORKERS}", flush=True)
    if MAX_WORKERS == 1:
        for idx, task in enumerate(tasks, start=1):
            print(f"[stage783] running {idx}/{len(tasks)} {task['start']}", flush=True)
            row, costs, curve = _run_one(task)
            rows.append(row)
            cost_rows.extend(costs)
            curves.append(curve)
    else:
        with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_map = {executor.submit(_run_one, task): task for task in tasks}
            for idx, future in enumerate(as_completed(future_map), start=1):
                task = future_map[future]
                row, costs, curve = future.result()
                rows.append(row)
                cost_rows.extend(costs)
                curves.append(curve)
                print(f"[stage783] completed {idx}/{len(tasks)} {task['start']}", flush=True)

    summary = s772._add_month_fields(pd.DataFrame(rows)).sort_values("start_month").reset_index(drop=True)
    cost = pd.DataFrame(cost_rows).sort_values(["start_month", "cost_multiplier"]).reset_index(drop=True)
    curves_all = (
        pd.concat(curves, ignore_index=True, sort=False)
        .sort_values(["start_month", "date"])
        .reset_index(drop=True)
    )
    return summary, cost, curves_all


def _profile_aggregate(summary: pd.DataFrame, cost: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for bucket, frame in [
        ("all", summary),
        ("mature_63d", summary[summary["mature_63d"].eq(1)]),
        ("mature_126d", summary[summary["mature_126d"].eq(1)]),
        ("mature_252d", summary[summary["mature_252d"].eq(1)]),
    ]:
        returns = pd.to_numeric(frame["rebased_total_return_pct"], errors="coerce")
        dds = pd.to_numeric(frame["rebased_max_dd_pct"], errors="coerce")
        sharpes = pd.to_numeric(frame["rebased_sharpe"], errors="coerce")
        rows.append(
            {
                "profile": PROFILE_NAME,
                "bucket": bucket,
                "start_count": int(len(frame)),
                "positive_count": int(frame["positive_return"].sum()) if len(frame) else 0,
                "positive_rate_pct": float(frame["positive_return"].mean() * 100.0) if len(frame) else 0.0,
                "median_return_pct": float(returns.median()) if len(frame) else 0.0,
                "p10_return_pct": float(returns.quantile(0.10)) if len(frame) else 0.0,
                "min_return_pct": float(returns.min()) if len(frame) else 0.0,
                "median_dd_pct": float(dds.median()) if len(frame) else 0.0,
                "worst_dd_pct": float(dds.min()) if len(frame) else 0.0,
                "dd30_fail_count": int((dds < -30.0).sum()) if len(frame) else 0,
                "dd40_fail_count": int(frame["dd40_fail"].sum()) if len(frame) else 0,
                "dd50_fail_count": int(frame["dd50_fail"].sum()) if len(frame) else 0,
                "median_sharpe": float(sharpes.median()) if len(frame) else 0.0,
                "trade_count_median": float(pd.to_numeric(frame["total_trade_count"], errors="coerce").median()) if len(frame) else 0.0,
                "trade_count_sum": float(pd.to_numeric(frame["total_trade_count"], errors="coerce").sum()) if len(frame) else 0.0,
            }
        )

    cost_view = cost[cost["cost_multiplier"].isin([2.0, 3.0])].copy()
    if not cost_view.empty:
        cost_view["dd40_fail"] = (pd.to_numeric(cost_view["max_dd_pct"], errors="coerce") < -40.0).astype(int)
        for multiplier, frame in cost_view.groupby("cost_multiplier", sort=True):
            rows.append(
                {
                    "profile": PROFILE_NAME,
                    "bucket": f"cost_{multiplier}x_all",
                    "start_count": int(summary.shape[0]),
                    "median_return_pct": float(pd.to_numeric(frame["total_return_pct"], errors="coerce").median()),
                    "dd40_fail_count": int(frame["dd40_fail"].sum()),
                }
            )
    return pd.DataFrame(rows)


def _phase_summary(summary: pd.DataFrame) -> pd.DataFrame:
    frame = summary.copy()
    frame["start_phase"] = pd.cut(
        pd.to_numeric(frame["start_year"], errors="coerce"),
        bins=[2017, 2019, 2021, 2023, 2025, 2026],
        labels=["2018-2019", "2020-2021", "2022-2023", "2024-2025", "2026"],
        include_lowest=True,
    ).astype(str)
    rows: list[dict[str, Any]] = []
    for phase, group in frame.groupby("start_phase", sort=True):
        rows.append(
            {
                "start_phase": phase,
                "start_count": int(len(group)),
                "mature_252d_count": int(group["mature_252d"].sum()),
                "positive_count": int(group["positive_return"].sum()),
                "median_return_pct": float(pd.to_numeric(group["rebased_total_return_pct"], errors="coerce").median()),
                "p10_return_pct": float(pd.to_numeric(group["rebased_total_return_pct"], errors="coerce").quantile(0.10)),
                "min_return_pct": float(pd.to_numeric(group["rebased_total_return_pct"], errors="coerce").min()),
                "median_dd_pct": float(pd.to_numeric(group["rebased_max_dd_pct"], errors="coerce").median()),
                "worst_dd_pct": float(pd.to_numeric(group["rebased_max_dd_pct"], errors="coerce").min()),
                "dd40_fail_count": int(group["dd40_fail"].sum()),
            }
        )
    return pd.DataFrame(rows)


def _comparison_vs_stage777(summary: pd.DataFrame) -> pd.DataFrame:
    base_path = s777.SUMMARY_PATH
    if not base_path.exists():
        raise FileNotFoundError(base_path)
    base = pd.read_csv(base_path, encoding="utf-8-sig")
    merged = base.merge(summary, on="start_month", suffixes=("_stage777", "_stage783"), how="inner")
    merged["return_delta_pct"] = (
        pd.to_numeric(merged["rebased_total_return_pct_stage783"], errors="coerce")
        - pd.to_numeric(merged["rebased_total_return_pct_stage777"], errors="coerce")
    )
    merged["dd_delta_pp"] = (
        pd.to_numeric(merged["rebased_max_dd_pct_stage783"], errors="coerce")
        - pd.to_numeric(merged["rebased_max_dd_pct_stage777"], errors="coerce")
    )
    merged["sharpe_delta"] = (
        pd.to_numeric(merged["rebased_sharpe_stage783"], errors="coerce")
        - pd.to_numeric(merged["rebased_sharpe_stage777"], errors="coerce")
    )
    merged["trade_count_delta"] = (
        pd.to_numeric(merged["total_trade_count_stage783"], errors="coerce")
        - pd.to_numeric(merged["total_trade_count_stage777"], errors="coerce")
    )
    merged["candidate_return_win"] = (merged["return_delta_pct"] > 0.0).astype(int)
    merged["candidate_dd_win"] = (merged["dd_delta_pp"] > 0.0).astype(int)
    merged["candidate_both_win"] = (
        merged["candidate_return_win"].eq(1) & merged["candidate_dd_win"].eq(1)
    ).astype(int)
    rows: list[dict[str, Any]] = []
    for bucket, frame in [("all", merged), ("mature_252d", merged[merged["mature_252d_stage777"].eq(1)])]:
        rows.append(
            {
                "bucket": bucket,
                "start_count": int(len(frame)),
                "return_win_count": int(frame["candidate_return_win"].sum()) if len(frame) else 0,
                "return_win_rate_pct": float(frame["candidate_return_win"].mean() * 100.0) if len(frame) else 0.0,
                "dd_win_count": int(frame["candidate_dd_win"].sum()) if len(frame) else 0,
                "dd_win_rate_pct": float(frame["candidate_dd_win"].mean() * 100.0) if len(frame) else 0.0,
                "both_win_count": int(frame["candidate_both_win"].sum()) if len(frame) else 0,
                "median_return_delta_pct": float(frame["return_delta_pct"].median()) if len(frame) else 0.0,
                "p10_return_delta_pct": float(frame["return_delta_pct"].quantile(0.10)) if len(frame) else 0.0,
                "min_return_delta_pct": float(frame["return_delta_pct"].min()) if len(frame) else 0.0,
                "median_dd_delta_pp": float(frame["dd_delta_pp"].median()) if len(frame) else 0.0,
                "worst_dd_delta_pp": float(frame["dd_delta_pp"].min()) if len(frame) else 0.0,
                "median_sharpe_delta": float(frame["sharpe_delta"].median()) if len(frame) else 0.0,
                "median_trade_count_delta": float(frame["trade_count_delta"].median()) if len(frame) else 0.0,
            }
        )
    comparison = pd.DataFrame(rows)
    detail_path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_detail_vs_stage777_{MODEL_TAG}.csv"
    merged.to_csv(detail_path, index=False, encoding="utf-8-sig")
    return comparison


def _plot_heatmap(summary: pd.DataFrame, value_column: str, path: Path, title: str, cmap: str, vcenter: float) -> None:
    pivot = summary.pivot_table(index="start_year", columns="start_month_num", values=value_column, aggfunc="first")
    values = pd.to_numeric(summary[value_column], errors="coerce")
    if value_column == "rebased_total_return_pct":
        vmin, vmax = -100.0, max(400.0, float(np.nanpercentile(values, 90)))
    else:
        vmin, vmax = float(np.nanpercentile(values, 5)), float(np.nanpercentile(values, 95))
    norm = TwoSlopeNorm(vcenter=vcenter, vmin=min(vmin, vcenter - 1e-6), vmax=max(vmax, vcenter + 1e-6))
    fig, ax = plt.subplots(figsize=(16, 6.8))
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


def _plot_delta_heatmap(summary: pd.DataFrame) -> None:
    base = pd.read_csv(s777.SUMMARY_PATH, encoding="utf-8-sig")
    merged = base.merge(summary, on="start_month", suffixes=("_stage777", "_stage783"), how="inner")
    merged["return_delta_pct"] = (
        pd.to_numeric(merged["rebased_total_return_pct_stage783"], errors="coerce")
        - pd.to_numeric(merged["rebased_total_return_pct_stage777"], errors="coerce")
    )
    pivot = merged.pivot_table(index="start_year_stage777", columns="start_month_num_stage777", values="return_delta_pct", aggfunc="first")
    values = pd.to_numeric(merged["return_delta_pct"], errors="coerce")
    limit = max(50.0, float(np.nanpercentile(np.abs(values), 90)))
    norm = TwoSlopeNorm(vcenter=0.0, vmin=-limit, vmax=limit)
    fig, ax = plt.subplots(figsize=(16, 6.8))
    im = ax.imshow(pivot.to_numpy(dtype=float), aspect="auto", cmap="RdYlGn", norm=norm)
    ax.set_title("Stage783 return delta vs Stage777 by monthly start")
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
    fig.savefig(DELTA_HEATMAP_PATH, dpi=180)
    plt.close(fig)


def _plot_selected_equity_curves(curves: pd.DataFrame, summary: pd.DataFrame) -> None:
    selected = {"2018-01", "2019-01", "2020-01", "2021-01", "2022-01", "2023-01", "2024-01", "2025-01", "2026-01"}
    for _, row in summary.nsmallest(3, "rebased_total_return_pct").iterrows():
        selected.add(str(row["start_month"]))
    for _, row in summary.nlargest(3, "rebased_total_return_pct").iterrows():
        selected.add(str(row["start_month"]))
    data = curves[curves["start_month"].astype(str).isin(sorted(selected))].copy()
    fig, ax = plt.subplots(figsize=(16, 8))
    colors = plt.cm.tab20.colors
    for idx, (start_month, group) in enumerate(data.groupby("start_month", sort=True)):
        group = group.sort_values("date")
        ax.plot(
            pd.to_datetime(group["date"]),
            pd.to_numeric(group["account_equity"], errors="coerce") / 1_000_000,
            label=start_month,
            color=colors[idx % len(colors)],
            linewidth=1.6,
            alpha=0.9,
        )
    ax.axhline(0.5, color="#9ca3af", linestyle="--", linewidth=1)
    ax.set_title("Stage783 selected monthly-start equity curves")
    ax.set_xlabel("Date")
    ax.set_ylabel("Account equity")
    ax.yaxis.set_major_formatter(lambda x, pos: f"{x:.1f}M")
    ax.grid(alpha=0.25)
    ax.legend(ncol=4, fontsize=8)
    fig.tight_layout()
    fig.savefig(EQUITY_CURVES_PATH, dpi=180)
    plt.close(fig)


def _build_decision(profile_agg: pd.DataFrame, comparison: pd.DataFrame) -> dict[str, Any]:
    mature = profile_agg[profile_agg["bucket"].eq("mature_252d")].iloc[0]
    comp_mature = comparison[comparison["bucket"].eq("mature_252d")].iloc[0]
    hard_fail: list[str] = []
    watch: list[str] = []
    if int(mature["dd40_fail_count"]) > 0:
        hard_fail.append("mature_dd40_fail_exists")
    if float(mature["worst_dd_pct"]) < -45.0:
        hard_fail.append("mature_worst_dd_below_45")
    if float(comp_mature["return_win_rate_pct"]) < 45.0:
        hard_fail.append("return_win_rate_vs_stage777_lt45pct")
    if float(comp_mature["median_return_delta_pct"]) < -25.0:
        hard_fail.append("median_return_delta_vs_stage777_lt_minus25pp")
    if float(comp_mature["dd_win_rate_pct"]) < 55.0:
        watch.append("dd_win_rate_vs_stage777_below55pct")
    decision = "am41_oi08_dd20_half_monthly_not_promoted" if hard_fail else "am41_oi08_dd20_half_monthly_candidate_watch"
    return {
        "stage": "Stage783",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "decision": decision,
        "hard_fail_checks": hard_fail,
        "watch_checks": watch,
        "analysis_start_first": MONTH_STARTS[0].date().isoformat(),
        "analysis_start_last": MONTH_STARTS[-1].date().isoformat(),
        "analysis_end": ANALYSIS_END.date().isoformat(),
        "monthly_start_count": len(MONTH_STARTS),
        "change": {
            "official_config_changed": False,
            "ctp_connected": False,
            "order_api_called": False,
            "base_stage": "Stage777 AM41 OI0.8",
            "base_effective_risk_multiplier": 0.40,
            "oi_hit_effective_risk_multiplier": 0.80,
            "drawdown_gate": "if account drawdown from high water mark > 20%, final entry/add volume *= 0.5",
            "drawdown_gate_entry_contexts": "*",
            "streak_risk_multipliers": "1.0,1.0,1.0,1.0",
            "enable_recovery_sleeve": False,
        },
        "profile_aggregate": profile_agg.to_dict("records"),
        "comparison_vs_stage777": comparison.to_dict("records"),
        "overfit_judgment": (
            "low-to-medium: account-level drawdown defense is structural, but the 20% threshold is still a "
            "single historical path parameter and must win across monthly starts."
        ),
        "continue_value": (
            "yes for this single validation; no threshold scanning if it only trades return for small drawdown relief."
        ),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }


def _write_report(profile_agg: pd.DataFrame, phase: pd.DataFrame, comparison: pd.DataFrame, decision: dict[str, Any]) -> None:
    lines = [
        "# Stage783 AM41 OI0.8 + 账户回撤20%后所有开仓半仓",
        "",
        f"- line_id：`{LINE_ID}`",
        f"- model_tag：`{MODEL_TAG}`",
        f"- 起点：`{MONTH_STARTS[0].strftime('%Y-%m')}` 到 `{MONTH_STARTS[-1].strftime('%Y-%m')}`；终点 `{ANALYSIS_END.date()}`。",
        "- 口径：Stage777 AM41/OI0.8；账户权益相对高水位回撤 `>20%` 时，所有 entry/add/rollover reopen 最终手数乘 `0.5`。",
        "",
        "## Profile Aggregate",
        "",
        _md_table(profile_agg, max_rows=20),
        "",
        "## Comparison vs Stage777",
        "",
        _md_table(comparison, max_rows=20),
        "",
        "## Phase Summary",
        "",
        _md_table(phase, max_rows=20),
        "",
        "## Decision",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- hard_fail：`{decision['hard_fail_checks']}`",
        f"- watch：`{decision['watch_checks']}`",
        f"- 过拟合判断：{decision['overfit_judgment']}",
        f"- 继续价值：{decision['continue_value']}",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary, cost, curves = _run_all()
    profile_agg = _profile_aggregate(summary, cost)
    phase = _phase_summary(summary)
    comparison = _comparison_vs_stage777(summary)
    decision = _build_decision(profile_agg, comparison)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    profile_agg.to_csv(PROFILE_AGG_PATH, index=False, encoding="utf-8-sig")
    phase.to_csv(PHASE_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _plot_heatmap(summary, "rebased_total_return_pct", RETURN_HEATMAP_PATH, "Stage783 return % by monthly start", "RdYlGn", 0.0)
    _plot_heatmap(summary, "rebased_max_dd_pct", DD_HEATMAP_PATH, "Stage783 max DD % by monthly start", "RdYlGn", -40.0)
    _plot_delta_heatmap(summary)
    _plot_selected_equity_curves(curves, summary)
    _write_report(profile_agg, phase, comparison, decision)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
