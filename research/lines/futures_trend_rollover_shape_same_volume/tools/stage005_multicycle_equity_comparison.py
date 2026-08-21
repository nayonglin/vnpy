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


LINE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = LINE_DIR / "artifacts" / "stage005"

DATA_START = pd.Timestamp("2018-01-01")
DATA_END = pd.Timestamp("2026-05-29")
START_MONTHS = (1, 6)
DURATIONS_YEARS = (1, 2, 3)
TERMINAL_TOLERANCE_DAYS = 7

SUMMARY_PATH = OUTPUT_DIR / "stage005_window_summary.csv"
COMPARISON_PATH = OUTPUT_DIR / "stage005_window_comparison.csv"
AGGREGATE_PATH = OUTPUT_DIR / "stage005_cycle_aggregate.csv"
CURVE_PATH = OUTPUT_DIR / "stage005_equity_curves.csv"
DECISION_PATH = OUTPUT_DIR / "stage005_decision.json"

CHART_FILES = {
    "full_period": "stage005_full_period_equity.png",
    "1y": "stage005_equity_curves_1y.png",
    "2y": "stage005_equity_curves_2y.png",
    "3y": "stage005_equity_curves_3y.png",
    "aggregate": "stage005_cycle_aggregate.png",
}

ARMS: tuple[dict[str, Any], ...] = (
    {
        "arm": "A",
        "candidate": False,
        "history_mode": "target_contract_only",
        "label": "A Official C9/150k",
    },
    {
        "arm": "C",
        "candidate": True,
        "history_mode": "backwards_ratio_continuous",
        "label": "C Official + rollover continuation",
    },
)


def _build_windows() -> tuple[dict[str, Any], ...]:
    windows: list[dict[str, Any]] = [
        {
            "window_id": "full_2018_2026",
            "window_group": "full_period",
            "duration_years": 0,
            "start": DATA_START,
            "end": DATA_END,
            "complete": True,
            "terminal_near_complete": False,
        }
    ]
    for years in DURATIONS_YEARS:
        for year in range(DATA_START.year, DATA_END.year + 1):
            for month in START_MONTHS:
                start = pd.Timestamp(year=year, month=month, day=1)
                if start < DATA_START or start > DATA_END:
                    continue
                natural_end = (start + pd.DateOffset(years=years) - pd.Timedelta(days=1)).normalize()
                complete = natural_end <= DATA_END
                terminal_gap_days = int((natural_end - DATA_END).days)
                terminal_near_complete = (
                    not complete and 0 < terminal_gap_days <= TERMINAL_TOLERANCE_DAYS
                )
                if not complete and not terminal_near_complete:
                    continue
                end = natural_end if complete else DATA_END
                window_id = (
                    f"roll_{years}y_{start.strftime('%Y_%m')}"
                    + ("_near_complete" if terminal_near_complete else "")
                )
                windows.append(
                    {
                        "window_id": window_id,
                        "window_group": f"rolling_{years}y",
                        "duration_years": years,
                        "start": start,
                        "end": end,
                        "complete": complete,
                        "terminal_near_complete": terminal_near_complete,
                    }
                )
    return tuple(windows)


WINDOWS = _build_windows()


def _run_window(
    metadata: dict[str, Any],
    window: dict[str, Any],
    arm: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    old_start, old_end = s1.START, s1.END
    profile = f"stage005_{arm['arm']}_{window['window_id']}"
    try:
        s1.START = pd.Timestamp(window["start"])
        s1.END = pd.Timestamp(window["end"])
        summary, curve, _frames = s1._run_arm(
            profile_name=profile,
            candidate=bool(arm["candidate"]),
            metadata=metadata,
            volume_policy="shrink_to_allowed",
            history_mode=str(arm["history_mode"]),
            label=str(arm["label"]),
        )
    finally:
        s1.START, s1.END = old_start, old_end

    start = pd.Timestamp(window["start"])
    end = pd.Timestamp(window["end"])
    start_month = start.strftime("%Y-%m")
    label = f"{start.date()} independent start to {end.date()}"
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
        "window_label": label,
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
        raise RuntimeError("stage005_window_arm_identity_mismatch")
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
    ]
    critical_values = summary[critical].apply(pd.to_numeric, errors="coerce")
    if not np.isfinite(critical_values.to_numpy(dtype=float)).all():
        raise RuntimeError("stage005_critical_metric_missing")
    curve_equity = pd.to_numeric(curves["account_equity"], errors="coerce")
    if curves.empty or not np.isfinite(curve_equity.to_numpy(dtype=float)).all():
        raise RuntimeError("stage005_curve_missing")
    curve_pairs = set(
        zip(curves["window_id"].astype(str), curves["promotion_arm"].astype(str), strict=False)
    )
    if curve_pairs != expected_pairs:
        raise RuntimeError("stage005_curve_window_arm_identity_mismatch")


def _comparison(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for window_id, group in summary.groupby("window_id", sort=False):
        by_arm = group.set_index("promotion_arm")
        a = by_arm.loc["A"]
        c = by_arm.loc["C"]
        rows.append(
            {
                "window_id": window_id,
                "window_group": str(c["window_group"]),
                "duration_years": int(c["duration_years"]),
                "requested_start": str(c["requested_start"]),
                "requested_end": str(c["requested_end"]),
                "complete_window": int(c["complete_window"]),
                "terminal_near_complete": int(c["terminal_near_complete"]),
                "A_end_equity": float(a["end_equity"]),
                "C_end_equity": float(c["end_equity"]),
                "A_return_pct": float(a["total_return_pct"]),
                "C_return_pct": float(c["total_return_pct"]),
                "delta_return_pct": float(c["total_return_pct"] - a["total_return_pct"]),
                "A_max_dd_pct": float(a["max_dd_pct"]),
                "C_max_dd_pct": float(c["max_dd_pct"]),
                "dd_worsening_pp": max(0.0, float(a["max_dd_pct"] - c["max_dd_pct"])),
                "A_sharpe": float(a["sharpe"]),
                "C_sharpe": float(c["sharpe"]),
                "delta_sharpe": float(c["sharpe"] - a["sharpe"]),
                "A_slippage": float(a["total_slippage"]),
                "C_slippage": float(c["total_slippage"]),
                "A_trades": int(a["total_trade_count"]),
                "C_trades": int(c["total_trade_count"]),
                "A_win_rate_pct": float(a["nonzero_daily_win_rate_pct"]),
                "C_win_rate_pct": float(c["nonzero_daily_win_rate_pct"]),
                "A_survival_pass": int(a["account_survival_pass"]),
                "C_survival_pass": int(c["account_survival_pass"]),
                "A_broker100_pass": int(a["broker10_100_pass"]),
                "C_broker100_pass": int(c["broker10_100_pass"]),
                "return_win": int(float(c["total_return_pct"]) >= float(a["total_return_pct"])),
                "C_positive": int(float(c["total_return_pct"]) > 0.0),
                "A_positive": int(float(a["total_return_pct"]) > 0.0),
                "dd_noninferior_2pp": int(
                    max(0.0, float(a["max_dd_pct"] - c["max_dd_pct"])) <= 2.0
                ),
                "sharpe_noninferior_005": int(
                    float(c["sharpe"]) >= float(a["sharpe"]) - 0.05
                ),
                "A_dd40_fail": int(float(a["max_dd_pct"]) < -40.0),
                "C_dd40_fail": int(float(c["max_dd_pct"]) < -40.0),
                "A_dd50_fail": int(float(a["max_dd_pct"]) < -50.0),
                "C_dd50_fail": int(float(c["max_dd_pct"]) < -50.0),
            }
        )
    return pd.DataFrame(rows)


def _aggregate(comparison: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    complete = comparison[
        comparison["complete_window"].eq(1) & comparison["duration_years"].isin(DURATIONS_YEARS)
    ]
    for years, group in complete.groupby("duration_years", sort=True):
        a_slippage = float(group["A_slippage"].sum())
        c_slippage = float(group["C_slippage"].sum())
        rows.append(
            {
                "duration_years": int(years),
                "window_count": int(len(group)),
                "return_win_count": int(group["return_win"].sum()),
                "return_win_rate_pct": float(group["return_win"].mean() * 100.0),
                "median_return_delta_pct": float(group["delta_return_pct"].median()),
                "A_positive_count": int(group["A_positive"].sum()),
                "C_positive_count": int(group["C_positive"].sum()),
                "A_worst_return_pct": float(group["A_return_pct"].min()),
                "C_worst_return_pct": float(group["C_return_pct"].min()),
                "dd_noninferior_2pp_count": int(group["dd_noninferior_2pp"].sum()),
                "dd_noninferior_2pp_rate_pct": float(group["dd_noninferior_2pp"].mean() * 100.0),
                "A_dd40_fail_count": int(group["A_dd40_fail"].sum()),
                "C_dd40_fail_count": int(group["C_dd40_fail"].sum()),
                "A_dd50_fail_count": int(group["A_dd50_fail"].sum()),
                "C_dd50_fail_count": int(group["C_dd50_fail"].sum()),
                "sharpe_noninferior_005_count": int(group["sharpe_noninferior_005"].sum()),
                "sharpe_noninferior_005_rate_pct": float(
                    group["sharpe_noninferior_005"].mean() * 100.0
                ),
                "A_slippage": a_slippage,
                "C_slippage": c_slippage,
                "slippage_ratio": float(c_slippage / a_slippage) if a_slippage > 0 else np.nan,
                "A_trades": int(group["A_trades"].sum()),
                "C_trades": int(group["C_trades"].sum()),
                "all_candidate_survival": int(group["C_survival_pass"].eq(1).all()),
                "A_broker100_fail_count": int(group["A_broker100_pass"].eq(0).sum()),
                "C_broker100_fail_count": int(group["C_broker100_pass"].eq(0).sum()),
            }
        )
    return pd.DataFrame(rows)


def _decision(comparison: pd.DataFrame, aggregate: pd.DataFrame) -> dict[str, Any]:
    full = comparison[comparison["window_group"].eq("full_period")].iloc[0]
    full_gates = {
        "return_not_below_A": bool(full["C_return_pct"] >= full["A_return_pct"]),
        "dd_worsening_le_1pp": bool(full["dd_worsening_pp"] <= 1.0),
        "sharpe_noninferior_001": bool(full["delta_sharpe"] >= -0.01),
        "slippage_ratio_le_105pct": bool(
            full["C_slippage"] <= full["A_slippage"] * 1.05
        ),
        "candidate_survival": bool(full["C_survival_pass"] == 1),
    }
    cycle_gates: list[dict[str, Any]] = []
    for row in aggregate.to_dict(orient="records"):
        gates = {
            "return_win_rate_ge_50pct": bool(row["return_win_rate_pct"] >= 50.0),
            "median_return_delta_nonnegative": bool(row["median_return_delta_pct"] >= 0.0),
            "dd_noninferior_2pp_rate_ge_80pct": bool(
                row["dd_noninferior_2pp_rate_pct"] >= 80.0
            ),
            "dd50_fail_count_not_above_A": bool(
                row["C_dd50_fail_count"] <= row["A_dd50_fail_count"]
            ),
            "sharpe_noninferior_005_rate_ge_80pct": bool(
                row["sharpe_noninferior_005_rate_pct"] >= 80.0
            ),
            "slippage_ratio_le_105pct": bool(row["slippage_ratio"] <= 1.05),
            "all_candidate_survival": bool(row["all_candidate_survival"] == 1),
            "broker100_fail_count_not_above_A": bool(
                row["C_broker100_fail_count"] <= row["A_broker100_fail_count"]
            ),
        }
        cycle_gates.append(
            {
                "duration_years": int(row["duration_years"]),
                "gates": gates,
                "pass": bool(all(gates.values())),
            }
        )
    all_pass = bool(all(full_gates.values()) and all(item["pass"] for item in cycle_gates))
    return {
        "line_id": "futures_trend_rollover_shape_same_volume",
        "stage": "Stage005",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "gate_contract": {
            "data_start": str(DATA_START.date()),
            "data_end": str(DATA_END.date()),
            "start_schedule": "January and June",
            "durations_years": list(DURATIONS_YEARS),
            "complete_windows_only_for_decision": True,
            "terminal_near_complete_tolerance_days": TERMINAL_TOLERANCE_DAYS,
            "candidate": {
                "enable_rollover_shape_same_volume_reopen": True,
                "rollover_shape_history_mode": "backwards_ratio_continuous",
                "rollover_shape_volume_policy": "shrink_to_allowed",
            },
        },
        "window_count": len(WINDOWS),
        "arm_run_count": len(WINDOWS) * len(ARMS),
        "predeclared_windows": [
            {
                **{
                    key: value
                    for key, value in window.items()
                    if key not in {"start", "end"}
                },
                "start": str(pd.Timestamp(window["start"]).date()),
                "end": str(pd.Timestamp(window["end"]).date()),
            }
            for window in WINDOWS
        ],
        "full_period_gates": full_gates,
        "cycle_gates": cycle_gates,
        "all_multicycle_gates_pass": all_pass,
        "decision": (
            "reopen_official_promotion_review"
            if all_pass
            else "confirm_do_not_promote_after_multicycle"
        ),
        "order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
    }


def _plot_window_grid(curves: pd.DataFrame, comparison: pd.DataFrame, years: int) -> bytes:
    selected = comparison[comparison["duration_years"].eq(years)].copy()
    rows = int(np.ceil(len(selected) / 4.0))
    fig, axes = plt.subplots(rows, 4, figsize=(18, 3.5 * rows), squeeze=False)
    for ax, (_, window) in zip(axes.ravel(), selected.iterrows(), strict=False):
        window_curves = curves[curves["window_id"].eq(window["window_id"])]
        for arm, color, label in [("A", "#2563eb", "A Official"), ("C", "#dc2626", "C Rollover")]:
            frame = window_curves[window_curves["promotion_arm"].eq(arm)].sort_values("date")
            ax.plot(pd.to_datetime(frame["date"]), frame["account_equity"] / 10_000.0, color=color, lw=1.25, label=label)
        suffix = " *" if int(window["terminal_near_complete"]) else ""
        ax.set_title(f"{window['requested_start']}  ({years}Y){suffix}", fontsize=10)
        ax.set_ylabel("Equity (10k CNY)")
        ax.grid(alpha=0.22)
        ax.tick_params(axis="x", rotation=25, labelsize=8)
    for ax in axes.ravel()[len(selected):]:
        ax.axis("off")
    handles, labels = axes.ravel()[0].get_legend_handles_labels()
    fig.suptitle(f"Stage005 {years}-Year Independent Rolling Equity Curves", y=0.998, fontsize=15)
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 0.975), ncol=2)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=150)
    plt.close(fig)
    return buffer.getvalue()


def _plot_full(curves: pd.DataFrame) -> bytes:
    frame = curves[curves["window_id"].eq("full_2018_2026")]
    fig, ax = plt.subplots(figsize=(14, 6))
    for arm, color, label in [("A", "#2563eb", "A Official"), ("C", "#dc2626", "C Rollover")]:
        item = frame[frame["promotion_arm"].eq(arm)].sort_values("date")
        ax.plot(pd.to_datetime(item["date"]), item["account_equity"] / 10_000.0, color=color, lw=1.5, label=label)
    ax.set_title("Stage005 Full-Period Equity: Official vs Rollover Candidate")
    ax.set_ylabel("Equity (10k CNY)")
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=170)
    plt.close(fig)
    return buffer.getvalue()


def _plot_aggregate(aggregate: pd.DataFrame) -> bytes:
    x = np.arange(len(aggregate))
    labels = [f"{int(value)}Y" for value in aggregate["duration_years"]]
    fig, axes = plt.subplots(2, 2, figsize=(13, 9))
    axes[0, 0].bar(x, aggregate["return_win_rate_pct"], color="#16a34a")
    axes[0, 0].axhline(50, color="#111827", ls="--", lw=1)
    axes[0, 0].set_title("C Return Win Rate vs A")
    axes[0, 0].set_ylabel("Percent")
    axes[0, 1].bar(x, aggregate["median_return_delta_pct"], color="#2563eb")
    axes[0, 1].axhline(0, color="#111827", lw=1)
    axes[0, 1].set_title("Median Return Delta (C-A)")
    axes[0, 1].set_ylabel("Percentage points")
    axes[1, 0].bar(x, aggregate["dd_noninferior_2pp_rate_pct"], color="#f59e0b")
    axes[1, 0].axhline(80, color="#111827", ls="--", lw=1)
    axes[1, 0].set_title("DD Non-Inferior <=2pp Rate")
    axes[1, 0].set_ylabel("Percent")
    axes[1, 1].bar(x, aggregate["slippage_ratio"] * 100.0, color="#dc2626")
    axes[1, 1].axhline(105, color="#111827", ls="--", lw=1)
    axes[1, 1].set_title("Aggregate Slippage Ratio C/A")
    axes[1, 1].set_ylabel("Percent")
    for ax in axes.ravel():
        ax.set_xticks(x, labels)
        ax.grid(axis="y", alpha=0.2)
    fig.suptitle("Stage005 Multi-Cycle A/C Summary", fontsize=15)
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
    temporary_dir = Path(tempfile.mkdtemp(prefix=".stage005.tmp-", dir=OUTPUT_DIR.parent))
    backup_dir = OUTPUT_DIR.with_name(f".stage005.backup-{uuid4().hex}")
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
                f"[stage005] {index}/{len(WINDOWS)} {window['window_id']} arm={arm['arm']}",
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
