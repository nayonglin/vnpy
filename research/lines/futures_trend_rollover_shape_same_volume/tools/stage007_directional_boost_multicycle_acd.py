from __future__ import annotations

from datetime import datetime
from io import BytesIO
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any
from uuid import uuid4

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import stage001_rollover_shape_same_volume_ac as s1
import stage005_multicycle_equity_comparison as s5
import stage006_directional_30d_risk_boost_acd as s6


LINE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = LINE_DIR / "artifacts" / "stage007"

DATA_START = s5.DATA_START
DATA_END = s5.DATA_END
START_MONTHS = s5.START_MONTHS
DURATIONS_YEARS = s5.DURATIONS_YEARS
TERMINAL_TOLERANCE_DAYS = s5.TERMINAL_TOLERANCE_DAYS
WINDOWS = s5.WINDOWS

SUMMARY_PATH = OUTPUT_DIR / "stage007_window_summary.csv"
COMPARISON_PATH = OUTPUT_DIR / "stage007_window_comparison.csv"
AGGREGATE_PATH = OUTPUT_DIR / "stage007_cycle_aggregate.csv"
CURVE_PATH = OUTPUT_DIR / "stage007_equity_curves.csv"
DECISION_PATH = OUTPUT_DIR / "stage007_decision.json"

CHART_FILES = {
    "full_period": "stage007_full_period_equity_acd.png",
    "1y": "stage007_equity_curves_1y_acd.png",
    "2y": "stage007_equity_curves_2y_acd.png",
    "3y": "stage007_equity_curves_3y_acd.png",
    "aggregate": "stage007_cycle_aggregate_acd.png",
}

ARMS: tuple[dict[str, Any], ...] = (
    {
        "arm": "A",
        "rollover_candidate": False,
        "risk_boost": False,
        "label": "A: Official C9/150k",
        "plot_label": "A Official",
        "color": "#2563eb",
    },
    {
        "arm": "C",
        "rollover_candidate": True,
        "risk_boost": False,
        "label": "C: Official + rollover continuation",
        "plot_label": "C Rollover",
        "color": "#dc2626",
    },
    {
        "arm": "D",
        "rollover_candidate": True,
        "risk_boost": True,
        "label": "D: C + directional 30D risk x1.2",
        "plot_label": "D Rollover + 30D x1.2",
        "color": "#16a34a",
    },
)

COMPARISONS: tuple[tuple[str, str, str], ...] = (
    ("A_vs_C", "A", "C"),
    ("A_vs_D", "A", "D"),
    ("C_vs_D", "C", "D"),
)
COHORTS: tuple[tuple[str, int | None], ...] = (
    ("combined", None),
    ("january", 1),
    ("june", 6),
)


def _run_window(
    metadata: dict[str, Any],
    window: dict[str, Any],
    arm: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    old_start, old_end = s1.START, s1.END
    runtime_arm = {
        **arm,
        "profile": f"stage007_{arm['arm']}_{window['window_id']}",
    }
    try:
        s1.START = pd.Timestamp(window["start"])
        s1.END = pd.Timestamp(window["end"])
        summary, curve, _frames = s6._run_arm(metadata, runtime_arm)
    finally:
        s1.START, s1.END = old_start, old_end

    start = pd.Timestamp(window["start"])
    end = pd.Timestamp(window["end"])
    start_month = start.strftime("%Y-%m")
    common = {
        "window_id": str(window["window_id"]),
        "window_group": str(window["window_group"]),
        "duration_years": int(window["duration_years"]),
        "requested_start": str(start.date()),
        "requested_end": str(end.date()),
        "complete_window": int(bool(window["complete"])),
        "terminal_near_complete": int(bool(window["terminal_near_complete"])),
        "promotion_arm": str(arm["arm"]),
        "window_name": str(window["window_id"]),
        "window_label": f"{start.date()} independent start to {end.date()}",
        "requested_start_month": start_month,
        "start_month": start_month,
        "start_year": int(start.year),
        "start_month_num": int(start.month),
    }
    result_summary = summary.copy()
    result_curve = curve.copy()
    for key, value in common.items():
        result_summary[key] = value
        result_curve[key] = value
    return result_summary, result_curve


def _validate_outputs(summary: pd.DataFrame, curves: pd.DataFrame) -> None:
    expected_pairs = {
        (str(window["window_id"]), str(arm["arm"]))
        for window in WINDOWS
        for arm in ARMS
    }
    actual_pairs = set(
        zip(summary["window_id"].astype(str), summary["promotion_arm"].astype(str), strict=False)
    )
    if len(summary) != len(expected_pairs) or actual_pairs != expected_pairs:
        raise RuntimeError("stage007_window_arm_identity_mismatch")
    critical = [
        "end_equity",
        "total_return_pct",
        "max_dd_pct",
        "sharpe",
        "total_slippage",
        "total_trade_count",
        "nonzero_daily_win_rate_pct",
        "account_survival_pass",
        "broker10_100_pass",
        "max_broker10_margin_to_equity_pct",
        "days_over_100pct",
    ]
    critical_values = summary[critical].apply(pd.to_numeric, errors="coerce")
    if not np.isfinite(critical_values.to_numpy(dtype=float)).all():
        raise RuntimeError("stage007_critical_metric_missing")
    curve_equity = pd.to_numeric(curves["account_equity"], errors="coerce")
    if curves.empty or not np.isfinite(curve_equity.to_numpy(dtype=float)).all():
        raise RuntimeError("stage007_curve_missing")
    curve_pairs = set(
        zip(curves["window_id"].astype(str), curves["promotion_arm"].astype(str), strict=False)
    )
    if curve_pairs != expected_pairs:
        raise RuntimeError("stage007_curve_window_arm_identity_mismatch")


def _comparison(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for window_id, group in summary.groupby("window_id", sort=False):
        by_arm = group.set_index("promotion_arm")
        for comparison_name, left_arm, right_arm in COMPARISONS:
            left = by_arm.loc[left_arm]
            right = by_arm.loc[right_arm]
            rows.append(
                {
                    "window_id": window_id,
                    "window_group": str(right["window_group"]),
                    "duration_years": int(right["duration_years"]),
                    "requested_start": str(right["requested_start"]),
                    "requested_end": str(right["requested_end"]),
                    "start_month_num": int(right["start_month_num"]),
                    "complete_window": int(right["complete_window"]),
                    "terminal_near_complete": int(right["terminal_near_complete"]),
                    "comparison": comparison_name,
                    "left_arm": left_arm,
                    "right_arm": right_arm,
                    "left_end_equity": float(left["end_equity"]),
                    "right_end_equity": float(right["end_equity"]),
                    "left_return_pct": float(left["total_return_pct"]),
                    "right_return_pct": float(right["total_return_pct"]),
                    "delta_return_pct": float(right["total_return_pct"] - left["total_return_pct"]),
                    "left_max_dd_pct": float(left["max_dd_pct"]),
                    "right_max_dd_pct": float(right["max_dd_pct"]),
                    "dd_worsening_pp": max(0.0, float(left["max_dd_pct"] - right["max_dd_pct"])),
                    "left_sharpe": float(left["sharpe"]),
                    "right_sharpe": float(right["sharpe"]),
                    "delta_sharpe": float(right["sharpe"] - left["sharpe"]),
                    "left_slippage": float(left["total_slippage"]),
                    "right_slippage": float(right["total_slippage"]),
                    "left_trades": int(left["total_trade_count"]),
                    "right_trades": int(right["total_trade_count"]),
                    "left_win_rate_pct": float(left["nonzero_daily_win_rate_pct"]),
                    "right_win_rate_pct": float(right["nonzero_daily_win_rate_pct"]),
                    "left_survival_pass": int(left["account_survival_pass"]),
                    "right_survival_pass": int(right["account_survival_pass"]),
                    "left_broker100_pass": int(left["broker10_100_pass"]),
                    "right_broker100_pass": int(right["broker10_100_pass"]),
                    "left_broker10_peak_pct": float(left["max_broker10_margin_to_equity_pct"]),
                    "right_broker10_peak_pct": float(right["max_broker10_margin_to_equity_pct"]),
                    "left_days_over_100pct": int(left["days_over_100pct"]),
                    "right_days_over_100pct": int(right["days_over_100pct"]),
                    "return_win": int(float(right["total_return_pct"]) >= float(left["total_return_pct"])),
                    "right_positive": int(float(right["total_return_pct"]) > 0.0),
                    "left_positive": int(float(left["total_return_pct"]) > 0.0),
                    "dd_noninferior_2pp": int(
                        max(0.0, float(left["max_dd_pct"] - right["max_dd_pct"])) <= 2.0
                    ),
                    "sharpe_noninferior_005": int(
                        float(right["sharpe"]) >= float(left["sharpe"]) - 0.05
                    ),
                    "left_dd40_fail": int(float(left["max_dd_pct"]) < -40.0),
                    "right_dd40_fail": int(float(right["max_dd_pct"]) < -40.0),
                    "left_dd50_fail": int(float(left["max_dd_pct"]) < -50.0),
                    "right_dd50_fail": int(float(right["max_dd_pct"]) < -50.0),
                }
            )
    return pd.DataFrame(rows)


def _aggregate_row(
    comparison_name: str,
    years: int,
    cohort: str,
    group: pd.DataFrame,
) -> dict[str, Any]:
    left_slippage = float(group["left_slippage"].sum())
    right_slippage = float(group["right_slippage"].sum())
    return {
        "comparison": comparison_name,
        "duration_years": int(years),
        "start_cohort": cohort,
        "window_count": int(len(group)),
        "return_win_count": int(group["return_win"].sum()),
        "return_win_rate_pct": float(group["return_win"].mean() * 100.0),
        "median_return_delta_pct": float(group["delta_return_pct"].median()),
        "left_positive_count": int(group["left_positive"].sum()),
        "right_positive_count": int(group["right_positive"].sum()),
        "left_worst_return_pct": float(group["left_return_pct"].min()),
        "right_worst_return_pct": float(group["right_return_pct"].min()),
        "dd_noninferior_2pp_count": int(group["dd_noninferior_2pp"].sum()),
        "dd_noninferior_2pp_rate_pct": float(group["dd_noninferior_2pp"].mean() * 100.0),
        "left_dd40_fail_count": int(group["left_dd40_fail"].sum()),
        "right_dd40_fail_count": int(group["right_dd40_fail"].sum()),
        "left_dd50_fail_count": int(group["left_dd50_fail"].sum()),
        "right_dd50_fail_count": int(group["right_dd50_fail"].sum()),
        "sharpe_noninferior_005_count": int(group["sharpe_noninferior_005"].sum()),
        "sharpe_noninferior_005_rate_pct": float(
            group["sharpe_noninferior_005"].mean() * 100.0
        ),
        "left_slippage": left_slippage,
        "right_slippage": right_slippage,
        "slippage_ratio": float(right_slippage / left_slippage) if left_slippage > 0 else np.nan,
        "left_trades": int(group["left_trades"].sum()),
        "right_trades": int(group["right_trades"].sum()),
        "all_right_survival": int(group["right_survival_pass"].eq(1).all()),
        "left_broker100_fail_count": int(group["left_broker100_pass"].eq(0).sum()),
        "right_broker100_fail_count": int(group["right_broker100_pass"].eq(0).sum()),
    }


def _aggregate(comparison: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    complete = comparison[
        comparison["complete_window"].eq(1)
        & comparison["duration_years"].isin(DURATIONS_YEARS)
    ]
    for comparison_name, _, _ in COMPARISONS:
        comparison_group = complete[complete["comparison"].eq(comparison_name)]
        for years in DURATIONS_YEARS:
            duration_group = comparison_group[comparison_group["duration_years"].eq(years)]
            for cohort, month in COHORTS:
                group = (
                    duration_group
                    if month is None
                    else duration_group[duration_group["start_month_num"].eq(month)]
                )
                if group.empty:
                    raise RuntimeError("stage007_missing_complete_cohort")
                rows.append(_aggregate_row(comparison_name, years, cohort, group))
    return pd.DataFrame(rows)


def _full_period_gates(row: pd.Series) -> dict[str, bool]:
    return {
        "return_not_below_left": bool(row["right_return_pct"] >= row["left_return_pct"]),
        "dd_worsening_le_1pp": bool(row["dd_worsening_pp"] <= 1.0),
        "sharpe_noninferior_001": bool(row["delta_sharpe"] >= -0.01),
        "slippage_ratio_le_105pct": bool(
            row["right_slippage"] <= row["left_slippage"] * 1.05
        ),
        "right_survival": bool(row["right_survival_pass"] == 1),
        "broker100_not_worse": bool(
            row["right_broker10_peak_pct"] <= row["left_broker10_peak_pct"] + 1e-12
            and row["right_days_over_100pct"] <= row["left_days_over_100pct"]
        ),
    }


def _cycle_gates(row: dict[str, Any]) -> dict[str, bool]:
    return {
        "return_win_rate_ge_50pct": bool(row["return_win_rate_pct"] >= 50.0),
        "median_return_delta_nonnegative": bool(row["median_return_delta_pct"] >= 0.0),
        "dd_noninferior_2pp_rate_ge_80pct": bool(row["dd_noninferior_2pp_rate_pct"] >= 80.0),
        "dd50_fail_count_not_above_left": bool(
            row["right_dd50_fail_count"] <= row["left_dd50_fail_count"]
        ),
        "sharpe_noninferior_005_rate_ge_80pct": bool(
            row["sharpe_noninferior_005_rate_pct"] >= 80.0
        ),
        "slippage_ratio_le_105pct": bool(row["slippage_ratio"] <= 1.05),
        "all_right_survival": bool(row["all_right_survival"] == 1),
        "broker100_fail_count_not_above_left": bool(
            row["right_broker100_fail_count"] <= row["left_broker100_fail_count"]
        ),
    }


def _decision(comparison: pd.DataFrame, aggregate: pd.DataFrame) -> dict[str, Any]:
    full_rows: list[dict[str, Any]] = []
    for comparison_name, _, _ in COMPARISONS:
        row = comparison[
            comparison["window_group"].eq("full_period")
            & comparison["comparison"].eq(comparison_name)
        ].iloc[0]
        gates = _full_period_gates(row)
        full_rows.append(
            {"comparison": comparison_name, "gates": gates, "pass": bool(all(gates.values()))}
        )

    cycle_rows: list[dict[str, Any]] = []
    for row in aggregate.to_dict(orient="records"):
        gates = _cycle_gates(row)
        cycle_rows.append(
            {
                "comparison": str(row["comparison"]),
                "duration_years": int(row["duration_years"]),
                "start_cohort": str(row["start_cohort"]),
                "gates": gates,
                "pass": bool(all(gates.values())),
            }
        )

    directional_comparisons = {"A_vs_D", "C_vs_D"}
    directional_full = [row for row in full_rows if row["comparison"] in directional_comparisons]
    directional_cycles = [row for row in cycle_rows if row["comparison"] in directional_comparisons]
    directional_pass = bool(
        all(row["pass"] for row in directional_full)
        and all(row["pass"] for row in directional_cycles)
    )
    return {
        "line_id": "futures_trend_rollover_shape_same_volume",
        "stage": "Stage007",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "diagnostic_override_reason": "user_requested_multicycle_after_stage006_minimal_gate_failure",
        "gate_contract": {
            "data_start": str(DATA_START.date()),
            "data_end": str(DATA_END.date()),
            "start_schedule": "January and June",
            "durations_years": list(DURATIONS_YEARS),
            "complete_windows_only_for_decision": True,
            "terminal_near_complete_tolerance_days": TERMINAL_TOLERANCE_DAYS,
            "arms": {
                "A": "official C9/150k",
                "C": "A + rollover continuation",
                "D": "C + directional 30D risk x1.2 for all entry contexts",
            },
        },
        "window_count": len(WINDOWS),
        "arm_run_count": len(WINDOWS) * len(ARMS),
        "comparison_row_count": len(comparison),
        "aggregate_row_count": len(aggregate),
        "predeclared_windows": [
            {
                **{key: value for key, value in window.items() if key not in {"start", "end"}},
                "start": str(pd.Timestamp(window["start"]).date()),
                "end": str(pd.Timestamp(window["end"]).date()),
            }
            for window in WINDOWS
        ],
        "full_period_gates": full_rows,
        "cycle_gates": cycle_rows,
        "directional_boost_all_multicycle_gates_pass": directional_pass,
        "decision": (
            "directional_boost_multicycle_evidence_supports_reopening_review"
            if directional_pass
            else "confirm_directional_boost_not_promotable_after_multicycle"
        ),
        "order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
    }


def _plot_window_grid(curves: pd.DataFrame, comparison: pd.DataFrame, years: int) -> bytes:
    selected = comparison[
        comparison["duration_years"].eq(years)
        & comparison["comparison"].eq("A_vs_C")
    ].sort_values(["requested_start", "window_id"])
    rows = int(np.ceil(len(selected) / 4.0))
    fig, axes = plt.subplots(rows, 4, figsize=(18, 3.5 * rows), squeeze=False)
    for ax, (_, window) in zip(axes.ravel(), selected.iterrows(), strict=False):
        window_curves = curves[curves["window_id"].eq(window["window_id"])]
        for arm in ARMS:
            frame = window_curves[window_curves["promotion_arm"].eq(arm["arm"])].sort_values("date")
            ax.plot(
                pd.to_datetime(frame["date"]),
                frame["account_equity"] / 10_000.0,
                color=arm["color"],
                lw=1.15,
                label=arm["plot_label"],
            )
        suffix = " *" if int(window["terminal_near_complete"]) else ""
        ax.set_title(f"{window['requested_start']}  ({years}Y){suffix}", fontsize=10)
        ax.set_ylabel("Equity (10k CNY)")
        ax.grid(alpha=0.22)
        ax.tick_params(axis="x", rotation=25, labelsize=8)
    for ax in axes.ravel()[len(selected):]:
        ax.axis("off")
    handles, labels = axes.ravel()[0].get_legend_handles_labels()
    fig.suptitle(f"Stage007 {years}-Year Independent Rolling Equity Curves", y=0.998, fontsize=15)
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 0.975), ncol=3)
    fig.text(0.995, 0.005, "* near-complete terminal window; observation only", ha="right", fontsize=8)
    fig.tight_layout(rect=[0, 0.015, 1, 0.94])
    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=150)
    plt.close(fig)
    return buffer.getvalue()


def _plot_full(curves: pd.DataFrame) -> bytes:
    frame = curves[curves["window_id"].eq("full_2018_2026")]
    fig, ax = plt.subplots(figsize=(14, 6))
    for arm in ARMS:
        item = frame[frame["promotion_arm"].eq(arm["arm"])].sort_values("date")
        ax.plot(
            pd.to_datetime(item["date"]),
            item["account_equity"] / 10_000.0,
            color=arm["color"],
            lw=1.5,
            label=arm["plot_label"],
        )
    ax.set_title("Stage007 Full-Period Equity: A Official vs C Rollover vs D 30D Risk x1.2")
    ax.set_ylabel("Equity (10k CNY)")
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=170)
    plt.close(fig)
    return buffer.getvalue()


def _plot_aggregate(aggregate: pd.DataFrame) -> bytes:
    row_keys = [
        (comparison, cohort)
        for comparison, _, _ in COMPARISONS
        for cohort, _ in COHORTS
    ]
    row_labels = [f"{comparison} {cohort}" for comparison, cohort in row_keys]
    metrics = [
        ("return_win_rate_pct", "Return Win Rate (%)", "YlGn", 0.0, 100.0),
        ("median_return_delta_pct", "Median Return Delta (pp)", "coolwarm", None, None),
        ("dd_noninferior_2pp_rate_pct", "DD Non-Inferior <=2pp (%)", "YlOrBr", 0.0, 100.0),
        ("slippage_ratio", "Aggregate Slippage Ratio (%)", "Reds", None, None),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(15, 12))
    for ax, (column, title, cmap, fixed_min, fixed_max) in zip(axes.ravel(), metrics, strict=True):
        values = np.empty((len(row_keys), len(DURATIONS_YEARS)), dtype=float)
        for row_index, (comparison, cohort) in enumerate(row_keys):
            for col_index, years in enumerate(DURATIONS_YEARS):
                row = aggregate[
                    aggregate["comparison"].eq(comparison)
                    & aggregate["start_cohort"].eq(cohort)
                    & aggregate["duration_years"].eq(years)
                ].iloc[0]
                value = float(row[column])
                values[row_index, col_index] = value * 100.0 if column == "slippage_ratio" else value
        vmin = fixed_min
        vmax = fixed_max
        if column == "median_return_delta_pct":
            bound = max(float(np.abs(values).max()), 1.0)
            vmin, vmax = -bound, bound
        image = ax.imshow(values, aspect="auto", cmap=cmap, vmin=vmin, vmax=vmax)
        for row_index in range(values.shape[0]):
            for col_index in range(values.shape[1]):
                ax.text(col_index, row_index, f"{values[row_index, col_index]:.1f}", ha="center", va="center", fontsize=8)
        ax.set_title(title)
        ax.set_xticks(range(len(DURATIONS_YEARS)), [f"{years}Y" for years in DURATIONS_YEARS])
        ax.set_yticks(range(len(row_labels)), row_labels, fontsize=8)
        fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    fig.suptitle("Stage007 Multi-Cycle A/C/D Summary: Combined, January, June", fontsize=15)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=170)
    plt.close(fig)
    return buffer.getvalue()


def _publish_atomically(
    frames: dict[str, pd.DataFrame],
    decision: dict[str, Any],
    charts: dict[str, bytes],
) -> None:
    OUTPUT_DIR.parent.mkdir(parents=True, exist_ok=True)
    temporary_dir = Path(tempfile.mkdtemp(prefix=".stage007.tmp-", dir=OUTPUT_DIR.parent))
    backup_dir = OUTPUT_DIR.with_name(f".stage007.backup-{uuid4().hex}")
    try:
        for filename, frame in frames.items():
            frame.to_csv(temporary_dir / filename, index=False, encoding="utf-8-sig")
        (temporary_dir / DECISION_PATH.name).write_text(
            json.dumps(decision, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        for filename, payload in charts.items():
            (temporary_dir / filename).write_bytes(payload)
        if OUTPUT_DIR.exists():
            os.replace(OUTPUT_DIR, backup_dir)
        try:
            os.replace(temporary_dir, OUTPUT_DIR)
        except Exception:
            if backup_dir.exists() and not OUTPUT_DIR.exists():
                os.replace(backup_dir, OUTPUT_DIR)
            raise
        if backup_dir.exists():
            shutil.rmtree(backup_dir, ignore_errors=True)
    finally:
        if temporary_dir.exists():
            shutil.rmtree(temporary_dir, ignore_errors=True)


def main() -> None:
    metadata = s513._metadata()
    summaries: list[pd.DataFrame] = []
    curves: list[pd.DataFrame] = []
    for index, window in enumerate(WINDOWS, start=1):
        for arm in ARMS:
            print(
                f"[stage007] {index}/{len(WINDOWS)} {window['window_id']} arm={arm['arm']}",
                flush=True,
            )
            summary, curve = _run_window(metadata, window, arm)
            summaries.append(summary)
            curves.append(curve)
    summary = pd.concat(summaries, ignore_index=True, sort=False)
    curve = pd.concat(curves, ignore_index=True, sort=False)
    _validate_outputs(summary, curve)
    comparison = _comparison(summary)
    aggregate = _aggregate(comparison)
    decision = _decision(comparison, aggregate)
    charts = {
        CHART_FILES["full_period"]: _plot_full(curve),
        CHART_FILES["1y"]: _plot_window_grid(curve, comparison, 1),
        CHART_FILES["2y"]: _plot_window_grid(curve, comparison, 2),
        CHART_FILES["3y"]: _plot_window_grid(curve, comparison, 3),
        CHART_FILES["aggregate"]: _plot_aggregate(aggregate),
    }
    _publish_atomically(
        {
            SUMMARY_PATH.name: summary,
            COMPARISON_PATH.name: comparison,
            AGGREGATE_PATH.name: aggregate,
            CURVE_PATH.name: curve,
        },
        decision,
        charts,
    )
    print(json.dumps(decision, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
