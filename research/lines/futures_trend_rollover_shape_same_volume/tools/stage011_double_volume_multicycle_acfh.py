from __future__ import annotations

from datetime import datetime
from io import BytesIO
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any, Callable
from uuid import uuid4

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import stage001_rollover_shape_same_volume_ac as s1
import stage005_multicycle_equity_comparison as s5
import stage007_directional_boost_multicycle_acd as s7
import stage008_directional_volume_confirmed_multicycle_acdf as s8
import stage010_directional_double_volume_full_period_acfh as s10


LINE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = LINE_DIR / "artifacts" / "stage011"

DATA_START = s5.DATA_START
DATA_END = s5.DATA_END
DURATIONS_YEARS = s5.DURATIONS_YEARS
TERMINAL_TOLERANCE_DAYS = s5.TERMINAL_TOLERANCE_DAYS
WINDOWS = s5.WINDOWS
COHORTS = s7.COHORTS

SUMMARY_PATH = OUTPUT_DIR / "stage011_window_summary.csv"
COMPARISON_PATH = OUTPUT_DIR / "stage011_window_comparison.csv"
AGGREGATE_PATH = OUTPUT_DIR / "stage011_cycle_aggregate.csv"
CURVE_PATH = OUTPUT_DIR / "stage011_equity_curves.csv"
ENTRY_RISK_PATH = OUTPUT_DIR / "stage011_full_h_entry_risk.csv"
TRADES_PATH = OUTPUT_DIR / "stage011_full_h_trades.csv"
TRADE_EVENTS_PATH = OUTPUT_DIR / "stage011_full_h_trade_events.csv"
VOLUME_CONTRACT_PATH = OUTPUT_DIR / "stage011_full_h_volume_contract_summary.csv"
DECISION_PATH = OUTPUT_DIR / "stage011_decision.json"

CHART_FILES = {
    "full_period": "stage011_full_period_equity_acfh.png",
    "1y": "stage011_equity_curves_1y_acfh.png",
    "2y": "stage011_equity_curves_2y_acfh.png",
    "3y": "stage011_equity_curves_3y_acfh.png",
    "aggregate": "stage011_cycle_aggregate_acfh.png",
}

ARMS: tuple[dict[str, Any], ...] = (
    {
        "arm": "A",
        "rollover_candidate": False,
        "risk_boost": False,
        "volume_confirmation": False,
        "volume_ratio_threshold": 1.0,
        "label": "A: Official C9/150k",
        "plot_label": "A Official",
        "color": "#2563eb",
    },
    {
        "arm": "C",
        "rollover_candidate": True,
        "risk_boost": False,
        "volume_confirmation": False,
        "volume_ratio_threshold": 1.0,
        "label": "C: Official + rollover continuation",
        "plot_label": "C Rollover",
        "color": "#dc2626",
    },
    {
        "arm": "F",
        "rollover_candidate": True,
        "risk_boost": True,
        "volume_confirmation": True,
        "volume_ratio_threshold": 1.0,
        "label": "F: C + direction and recent volume > 1x prior risk x1.2",
        "plot_label": "F Volume >1x",
        "color": "#9333ea",
    },
    {
        "arm": "H",
        "rollover_candidate": True,
        "risk_boost": True,
        "volume_confirmation": True,
        "volume_ratio_threshold": 2.0,
        "label": "H: C + direction and recent volume > 2x prior risk x1.2",
        "plot_label": "H Volume >2x",
        "color": "#ea580c",
    },
)

REUSED_ARMS = {"A", "C", "F"}
NEW_RUN_ARMS = {"H"}
BASELINE_SOURCE_STAGE = "Stage008"
BASELINE_SOURCE_COMMIT = "ce9e9c5d7"

COMPARISONS: tuple[tuple[str, str, str], ...] = (
    ("A_vs_C", "A", "C"),
    ("A_vs_F", "A", "F"),
    ("C_vs_F", "C", "F"),
    ("A_vs_H", "A", "H"),
    ("C_vs_H", "C", "H"),
    ("F_vs_H", "F", "H"),
)


def _run_h_window(
    metadata: dict[str, Any],
    window: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame]]:
    arm = next(item for item in ARMS if item["arm"] == "H")
    runtime_arm = {
        **arm,
        "profile": f"stage011_H_{window['window_id']}",
    }
    old_start, old_end = s1.START, s1.END
    try:
        s1.START = pd.Timestamp(window["start"])
        s1.END = pd.Timestamp(window["end"])
        summary, curve, frames = s10._run_arm(metadata, runtime_arm)
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
        "promotion_arm": "H",
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
    return result_summary, result_curve, frames


def _load_reused_baselines() -> tuple[pd.DataFrame, pd.DataFrame]:
    summary = pd.read_csv(s8.SUMMARY_PATH)
    curve = pd.read_csv(s8.CURVE_PATH)
    summary = summary[summary["promotion_arm"].astype(str).isin(REUSED_ARMS)].copy()
    curve = curve[curve["promotion_arm"].astype(str).isin(REUSED_ARMS)].copy()
    expected_pairs = {
        (str(window["window_id"]), arm)
        for window in WINDOWS
        for arm in REUSED_ARMS
    }
    actual_summary_pairs = set(
        zip(summary["window_id"].astype(str), summary["promotion_arm"].astype(str), strict=False)
    )
    actual_curve_pairs = set(
        zip(curve["window_id"].astype(str), curve["promotion_arm"].astype(str), strict=False)
    )
    if len(summary) != len(WINDOWS) * len(REUSED_ARMS) or actual_summary_pairs != expected_pairs:
        raise RuntimeError("stage011_reused_summary_identity_mismatch")
    if actual_curve_pairs != expected_pairs:
        raise RuntimeError("stage011_reused_curve_identity_mismatch")
    return summary, curve


def _verify_reused_full_identity(summary: pd.DataFrame, curve: pd.DataFrame) -> None:
    stage010_summary = pd.read_csv(s10.SUMMARY_PATH).set_index("experiment_arm")
    stage010_curve = pd.read_csv(s10.CURVE_PATH)
    full_summary = summary[summary["window_id"].astype(str).eq("full_2018_2026")].set_index(
        "promotion_arm"
    )
    metrics = [
        "end_equity",
        "total_return_pct",
        "max_dd_pct",
        "sharpe",
        "total_slippage",
        "total_trade_count",
        "nonzero_daily_win_rate_pct",
        "max_broker10_margin_to_equity_pct",
        "days_over_100pct",
    ]
    for arm in sorted(REUSED_ARMS):
        left = full_summary.loc[arm, metrics].to_numpy(dtype="float64")
        right = stage010_summary.loc[arm, metrics].to_numpy(dtype="float64")
        if not np.allclose(left, right, rtol=0.0, atol=0.0):
            raise RuntimeError(f"stage011_reused_full_summary_drift:{arm}")
        left_curve = curve[
            curve["window_id"].astype(str).eq("full_2018_2026")
            & curve["promotion_arm"].astype(str).eq(arm)
        ].sort_values("date")
        right_curve = stage010_curve[
            stage010_curve["experiment_arm"].astype(str).eq(arm)
        ].sort_values("date")
        if left_curve["date"].astype(str).tolist() != right_curve["date"].astype(str).tolist():
            raise RuntimeError(f"stage011_reused_full_curve_date_drift:{arm}")
        if not np.allclose(
            pd.to_numeric(left_curve["account_equity"], errors="coerce"),
            pd.to_numeric(right_curve["account_equity"], errors="coerce"),
            rtol=0.0,
            atol=0.0,
        ):
            raise RuntimeError(f"stage011_reused_full_curve_equity_drift:{arm}")


def _using_contract(function: Callable[..., Any], *args: Any) -> Any:
    original_arms, original_comparisons = s7.ARMS, s7.COMPARISONS
    try:
        s7.ARMS = ARMS
        s7.COMPARISONS = COMPARISONS
        return function(*args)
    finally:
        s7.ARMS, s7.COMPARISONS = original_arms, original_comparisons


def _validate_outputs(summary: pd.DataFrame, curves: pd.DataFrame) -> None:
    _using_contract(s7._validate_outputs, summary, curves)


def _comparison(summary: pd.DataFrame) -> pd.DataFrame:
    return _using_contract(s7._comparison, summary)


def _aggregate(comparison: pd.DataFrame) -> pd.DataFrame:
    return _using_contract(s7._aggregate, comparison)


def _decision(
    comparison: pd.DataFrame,
    aggregate: pd.DataFrame,
    volume_contract: pd.DataFrame,
) -> dict[str, Any]:
    full_rows: list[dict[str, Any]] = []
    for comparison_name, _, _ in COMPARISONS:
        row = comparison[
            comparison["window_group"].eq("full_period")
            & comparison["comparison"].eq(comparison_name)
        ].iloc[0]
        gates = s7._full_period_gates(row)
        full_rows.append(
            {"comparison": comparison_name, "gates": gates, "pass": bool(all(gates.values()))}
        )

    cycle_rows: list[dict[str, Any]] = []
    for row in aggregate.to_dict(orient="records"):
        gates = s7._cycle_gates(row)
        cycle_rows.append(
            {
                "comparison": str(row["comparison"]),
                "duration_years": int(row["duration_years"]),
                "start_cohort": str(row["start_cohort"]),
                "gates": gates,
                "pass": bool(all(gates.values())),
            }
        )

    total = volume_contract[volume_contract["group_type"].astype(str).eq("total")].iloc[0]
    aligned_count = int(total["price_aligned_count"])
    applied_count = int(total["boost_applied_count"])
    contract_gates = {
        "threshold_contract_pass": bool(int(total["threshold_contract_pass"]) == 1),
        "risk_amount_contract_pass": bool(int(total["risk_amount_contract_pass"]) == 1),
        "diagnostic_intents_present": bool(int(total["diagnostic_intent_count"]) > 0),
        "price_aligned_intents_present": bool(aligned_count > 0),
        "double_volume_boost_triggered": bool(applied_count > 0),
        "double_volume_gate_selective_le_30pct": bool(
            aligned_count > 0 and applied_count / aligned_count <= 0.30
        ),
    }
    promotion_comparisons = {"A_vs_H", "C_vs_H"}
    promotion_full = [row for row in full_rows if row["comparison"] in promotion_comparisons]
    promotion_cycles = [row for row in cycle_rows if row["comparison"] in promotion_comparisons]
    all_pass = bool(
        all(contract_gates.values())
        and all(row["pass"] for row in promotion_full)
        and all(row["pass"] for row in promotion_cycles)
    )
    return {
        "line_id": "futures_trend_rollover_shape_same_volume",
        "stage": "Stage011",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "diagnostic_override_reason": "user_requested_multicycle_after_stage010_full_period_gate_failure",
        "gate_contract": {
            "data_start": str(DATA_START.date()),
            "data_end": str(DATA_END.date()),
            "start_schedule": "January and June",
            "durations_years": list(DURATIONS_YEARS),
            "complete_windows_only_for_decision": True,
            "terminal_near_complete_tolerance_days": TERMINAL_TOLERANCE_DAYS,
            "H_rule": {
                "price_direction_lookback_days": 30,
                "recent_volume_window": "T-9 through T, includes signal day",
                "prior_volume_window": "T-19 through T-10",
                "volume_condition": "recent 10-day sum strictly greater than 2.0 times prior 10-day sum",
                "risk_multiplier_when_both_confirm": 1.2,
                "risk_multiplier_otherwise": 1.0,
            },
            "promotion_comparisons": sorted(promotion_comparisons),
        },
        "run_provenance": {
            "reused_baseline_source_stage": BASELINE_SOURCE_STAGE,
            "reused_baseline_source_commit": BASELINE_SOURCE_COMMIT,
            "reused_arms": sorted(REUSED_ARMS),
            "reused_independent_run_count": len(WINDOWS) * len(REUSED_ARMS),
            "new_arms": sorted(NEW_RUN_ARMS),
            "new_independent_run_count": len(WINDOWS) * len(NEW_RUN_ARMS),
            "logical_arm_window_count": len(WINDOWS) * len(ARMS),
            "full_period_reuse_identity_verified_against_stage010": True,
        },
        "window_count": len(WINDOWS),
        "comparison_row_count": len(comparison),
        "aggregate_row_count": len(aggregate),
        "volume_contract_gates": contract_gates,
        "full_period_gates": full_rows,
        "cycle_gates": cycle_rows,
        "double_volume_all_multicycle_gates_pass": all_pass,
        "decision": (
            "double_volume_multicycle_evidence_supports_reopening_review"
            if all_pass
            else "confirm_double_volume_not_promotable_after_multicycle"
        ),
        "order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
    }


def _plot_window_grid(curves: pd.DataFrame, comparison: pd.DataFrame, years: int) -> bytes:
    selected = comparison[
        comparison["duration_years"].eq(years) & comparison["comparison"].eq("A_vs_C")
    ].sort_values(["requested_start", "window_id"])
    rows = int(np.ceil(len(selected) / 4.0))
    fig, axes = plt.subplots(rows, 4, figsize=(18, 3.5 * rows), squeeze=False)
    for ax, (_, window) in zip(axes.ravel(), selected.iterrows(), strict=False):
        window_curves = curves[curves["window_id"].eq(window["window_id"])]
        for arm in ARMS:
            frame = window_curves[
                window_curves["promotion_arm"].eq(arm["arm"])
            ].sort_values("date")
            ax.plot(
                pd.to_datetime(frame["date"]),
                frame["account_equity"] / 10_000.0,
                color=arm["color"],
                lw=1.1,
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
    fig.suptitle(f"Stage011 {years}-Year Independent Rolling Equity Curves", y=0.998, fontsize=15)
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 0.975), ncol=4)
    fig.text(
        0.995,
        0.005,
        "* near-complete terminal window; observation only",
        ha="right",
        fontsize=8,
    )
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
            lw=1.45,
            label=arm["plot_label"],
        )
    ax.set_title("Stage011 Full-Period Equity: A Official vs C Rollover vs F >1x Volume vs H >2x Volume")
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
    fig, axes = plt.subplots(2, 2, figsize=(16, 15))
    for ax, (column, title, cmap, fixed_min, fixed_max) in zip(
        axes.ravel(), metrics, strict=True
    ):
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
        vmin, vmax = fixed_min, fixed_max
        if column == "median_return_delta_pct":
            bound = max(float(np.abs(values).max()), 1.0)
            vmin, vmax = -bound, bound
        image = ax.imshow(values, aspect="auto", cmap=cmap, vmin=vmin, vmax=vmax)
        for row_index in range(values.shape[0]):
            for col_index in range(values.shape[1]):
                ax.text(
                    col_index,
                    row_index,
                    f"{values[row_index, col_index]:.1f}",
                    ha="center",
                    va="center",
                    fontsize=7,
                )
        ax.set_title(title)
        ax.set_xticks(range(len(DURATIONS_YEARS)), [f"{years}Y" for years in DURATIONS_YEARS])
        ax.set_yticks(range(len(row_labels)), row_labels, fontsize=7)
        fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    fig.suptitle("Stage011 Multi-Cycle A/C/F/H Summary: Combined, January, June", fontsize=15)
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
    temporary_dir = Path(tempfile.mkdtemp(prefix=".stage011.tmp-", dir=OUTPUT_DIR.parent))
    backup_dir = OUTPUT_DIR.with_name(f".stage011.backup-{uuid4().hex}")
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
    reused_summary, reused_curve = _load_reused_baselines()
    _verify_reused_full_identity(reused_summary, reused_curve)
    h_summaries: list[pd.DataFrame] = []
    h_curves: list[pd.DataFrame] = []
    full_h_frames: dict[str, pd.DataFrame] = {}
    for index, window in enumerate(WINDOWS, start=1):
        print(f"[stage011] {index}/{len(WINDOWS)} {window['window_id']} arm=H", flush=True)
        summary, curve, frames = _run_h_window(metadata, window)
        h_summaries.append(summary)
        h_curves.append(curve)
        if str(window["window_id"]) == "full_2018_2026":
            full_h_frames = {key: value.copy() for key, value in frames.items()}

    summary = pd.concat([reused_summary, *h_summaries], ignore_index=True, sort=False)
    curve = pd.concat([reused_curve, *h_curves], ignore_index=True, sort=False)
    window_order = {str(window["window_id"]): index for index, window in enumerate(WINDOWS)}
    arm_order = {str(arm["arm"]): index for index, arm in enumerate(ARMS)}
    summary["_window_order"] = summary["window_id"].astype(str).map(window_order)
    summary["_arm_order"] = summary["promotion_arm"].astype(str).map(arm_order)
    summary = summary.sort_values(["_window_order", "_arm_order"]).drop(
        columns=["_window_order", "_arm_order"]
    )
    curve["_window_order"] = curve["window_id"].astype(str).map(window_order)
    curve["_arm_order"] = curve["promotion_arm"].astype(str).map(arm_order)
    curve = curve.sort_values(["_window_order", "_arm_order", "date"]).drop(
        columns=["_window_order", "_arm_order"]
    )
    _validate_outputs(summary, curve)
    comparison = _comparison(summary)
    aggregate = _aggregate(comparison)
    entry_risk = full_h_frames.get("entry_risk", pd.DataFrame()).copy()
    trades = full_h_frames.get("trades", pd.DataFrame()).copy()
    trade_events = full_h_frames.get("trade_events", pd.DataFrame()).copy()
    volume_contract = s10._volume_contract_summary(entry_risk)
    decision = _decision(comparison, aggregate, volume_contract)
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
            ENTRY_RISK_PATH.name: entry_risk,
            TRADES_PATH.name: trades,
            TRADE_EVENTS_PATH.name: trade_events,
            VOLUME_CONTRACT_PATH.name: volume_contract,
        },
        decision,
        charts,
    )
    print(json.dumps(decision, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
