from __future__ import annotations

from datetime import datetime
from io import BytesIO
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Callable
from uuid import uuid4

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import stage001_rollover_shape_same_volume_ac as s1
import stage007_directional_boost_multicycle_acd as s7
import stage013_long_only_asymmetric_double_volume_multicycle_achij as s13
import stage020_n_long_atr_shock_filter_full_period_acnp as s20
import stage021_p_symmetric_atr_shock_filter_full_period_acpq as s21


LINE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = LINE_DIR / "artifacts" / "stage022"
DATA_START = s13.DATA_START
DATA_END = s13.DATA_END
DURATIONS_YEARS = s13.DURATIONS_YEARS
TERMINAL_TOLERANCE_DAYS = s13.TERMINAL_TOLERANCE_DAYS
WINDOWS = s13.WINDOWS
COHORTS = s13.COHORTS

SUMMARY_PATH = OUTPUT_DIR / "stage022_window_summary.csv"
COMPARISON_PATH = OUTPUT_DIR / "stage022_window_comparison.csv"
AGGREGATE_PATH = OUTPUT_DIR / "stage022_cycle_aggregate.csv"
CURVE_PATH = OUTPUT_DIR / "stage022_equity_curves.csv"
Q_ENTRY_RISK_PATH = OUTPUT_DIR / "stage022_full_q_entry_risk.csv"
Q_TRADES_PATH = OUTPUT_DIR / "stage022_full_q_trades.csv"
Q_TRADE_EVENTS_PATH = OUTPUT_DIR / "stage022_full_q_trade_events.csv"
Q_ATR_FILTER_PATH = OUTPUT_DIR / "stage022_full_q_signal_atr_shock.csv"
Q_ATR_CONTRACT_PATH = OUTPUT_DIR / "stage022_full_q_atr_filter_contract_summary.csv"
DECISION_PATH = OUTPUT_DIR / "stage022_decision.json"
CHART_FILES = {
    "full_period": "stage022_full_period_equity_acpq.png",
    "1y": "stage022_equity_curves_1y_acpq.png",
    "2y": "stage022_equity_curves_2y_acpq.png",
    "3y": "stage022_equity_curves_3y_acpq.png",
    "aggregate": "stage022_cycle_aggregate_acpq.png",
}

ARMS: tuple[dict[str, Any], ...] = (
    {"arm": "A", "profile": "stage022_A_official_live_c9_15w", "label": "A: Official C9/150k", "plot_label": "A Official", "color": "#2563eb"},
    {"arm": "C", "profile": "stage022_C_rollover_continuation", "label": "C: Official + rollover continuation", "plot_label": "C Rollover", "color": "#dc2626"},
    {"arm": "P", "profile": "stage022_P_n_plus_long_atr5_1x_shock_filter", "label": "P: N + long adverse move >1x ATR5 blocked", "plot_label": "P Long ATR", "color": "#7c3aed", "enable_short_filter": False},
    {"arm": "Q", "profile": "stage022_Q_p_plus_short_atr5_1x_shock_filter", "label": "Q: P + symmetric short adverse move >1x ATR5 blocked", "plot_label": "Q Long + Short ATR", "color": "#f59e0b", "enable_short_filter": True},
)
REUSED_ARMS = {"A", "C"}
NEW_RUN_ARMS = {"P", "Q"}
REUSED_SOURCE_STAGE = "Stage013"
REUSED_SOURCE_COMMIT = "9554adf7e9d02979af90557387a790ff7e46815e"
COMPARISONS: tuple[tuple[str, str, str], ...] = (
    ("A_vs_C", "A", "C"),
    ("A_vs_P", "A", "P"),
    ("C_vs_P", "C", "P"),
    ("A_vs_Q", "A", "Q"),
    ("C_vs_Q", "C", "Q"),
    ("P_vs_Q", "P", "Q"),
)
PROMOTION_COMPARISONS = {"A_vs_Q", "C_vs_Q"}


def _git_head() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=LINE_DIR.parents[2], text=True
    ).strip()


def _csv_equity_values_match(left: np.ndarray, right: np.ndarray) -> bool:
    left_values = np.asarray(left, dtype="float64")
    right_values = np.asarray(right, dtype="float64")
    if left_values.shape != right_values.shape:
        return False
    if not np.isfinite(left_values).all() or not np.isfinite(right_values).all():
        return False
    difference = np.abs(left_values - right_values)
    scale = np.maximum(np.maximum(np.abs(left_values), np.abs(right_values)), 1.0)
    return bool((difference <= 1e-9 + scale * 1e-15).all())


def _load_reused_arms() -> tuple[pd.DataFrame, pd.DataFrame]:
    summary = pd.read_csv(s13.SUMMARY_PATH)
    curve = pd.read_csv(s13.CURVE_PATH)
    summary = summary[summary["promotion_arm"].astype(str).isin(REUSED_ARMS)].copy()
    curve = curve[curve["promotion_arm"].astype(str).isin(REUSED_ARMS)].copy()
    expected = {(str(window["window_id"]), arm) for window in WINDOWS for arm in REUSED_ARMS}
    summary_pairs = set(zip(summary["window_id"].astype(str), summary["promotion_arm"].astype(str), strict=False))
    curve_pairs = set(zip(curve["window_id"].astype(str), curve["promotion_arm"].astype(str), strict=False))
    if len(summary) != len(expected) or summary_pairs != expected:
        raise RuntimeError("stage022_reused_summary_identity_mismatch")
    if curve_pairs != expected:
        raise RuntimeError("stage022_reused_curve_identity_mismatch")
    return summary, curve


def _candidate_overrides(arm: str, original_overrides: Callable[..., dict[str, Any]], **kwargs: Any) -> dict[str, Any]:
    if arm == "P":
        return s20._p_overrides(base_overrides=original_overrides, **kwargs)
    if arm == "Q":
        return s21._q_overrides(base_overrides=original_overrides, **kwargs)
    raise ValueError(f"unsupported_candidate_arm:{arm}")


def _run_candidate_window(
    metadata: dict[str, Any], window: dict[str, Any], arm: dict[str, Any]
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame]]:
    arm_name = str(arm["arm"])
    original_overrides = s1._overrides
    old_start, old_end = s1.START, s1.END

    def experiment_overrides(
        *, candidate: bool, volume_policy: str = "exact_or_skip", history_mode: str = "target_contract_only"
    ) -> dict[str, Any]:
        return _candidate_overrides(
            arm_name,
            original_overrides,
            candidate=candidate,
            volume_policy=volume_policy,
            history_mode=history_mode,
        )

    try:
        s1.START = pd.Timestamp(window["start"])
        s1.END = pd.Timestamp(window["end"])
        s1._overrides = experiment_overrides
        summary, curve, frames = s1._run_arm(
            profile_name=f"{arm['profile']}_{window['window_id']}",
            candidate=True,
            metadata=metadata,
            volume_policy="shrink_to_allowed",
            history_mode="backwards_ratio_continuous",
            label=str(arm["label"]),
        )
    finally:
        s1._overrides = original_overrides
        s1.START, s1.END = old_start, old_end

    start, end = pd.Timestamp(window["start"]), pd.Timestamp(window["end"])
    start_month = start.strftime("%Y-%m")
    common = {
        "window_id": str(window["window_id"]),
        "window_group": str(window["window_group"]),
        "duration_years": int(window["duration_years"]),
        "requested_start": str(start.date()),
        "requested_end": str(end.date()),
        "complete_window": int(bool(window["complete"])),
        "terminal_near_complete": int(bool(window["terminal_near_complete"])),
        "promotion_arm": arm_name,
        "experiment_arm": arm_name,
        "window_name": str(window["window_id"]),
        "window_label": f"{start.date()} independent start to {end.date()}",
        "requested_start_month": start_month,
        "start_month": start_month,
        "start_year": int(start.year),
        "start_month_num": int(start.month),
    }
    result_summary, result_curve = summary.copy(), curve.copy()
    for key, value in common.items():
        result_summary[key] = value
        result_curve[key] = value
    return result_summary, result_curve, frames


def _using_contract(function: Callable[..., Any], *args: Any) -> Any:
    original_arms, original_comparisons = s7.ARMS, s7.COMPARISONS
    try:
        s7.ARMS, s7.COMPARISONS = ARMS, COMPARISONS
        return function(*args)
    finally:
        s7.ARMS, s7.COMPARISONS = original_arms, original_comparisons


def _validate_outputs(summary: pd.DataFrame, curve: pd.DataFrame) -> None:
    _using_contract(s7._validate_outputs, summary, curve)


def _comparison(summary: pd.DataFrame) -> pd.DataFrame:
    result = _using_contract(s7._comparison, summary)
    near_equal = pd.to_numeric(result["delta_return_pct"], errors="coerce").abs().le(1e-9)
    result.loc[near_equal, "delta_return_pct"] = 0.0
    result.loc[near_equal, "return_win"] = 1
    return result


def _aggregate(comparison: pd.DataFrame) -> pd.DataFrame:
    return _using_contract(s7._aggregate, comparison)


def _verify_full_identity(summary: pd.DataFrame, curve: pd.DataFrame) -> None:
    source_summary = pd.read_csv(s21.SUMMARY_PATH).set_index("experiment_arm")
    source_curve = pd.read_csv(s21.CURVE_PATH)
    full = summary[summary["window_id"].astype(str).eq("full_2018_2026")].set_index("promotion_arm")
    metrics = [
        "end_equity", "total_return_pct", "max_dd_pct", "sharpe", "total_slippage",
        "total_trade_count", "nonzero_daily_win_rate_pct",
        "max_broker10_margin_to_equity_pct", "days_over_100pct",
    ]
    for arm in ("A", "C", "P", "Q"):
        if not np.allclose(
            full.loc[arm, metrics].to_numpy(dtype="float64"),
            source_summary.loc[arm, metrics].to_numpy(dtype="float64"),
            rtol=0.0,
            atol=1e-9,
        ):
            raise RuntimeError(f"stage022_full_summary_drift:{arm}")
        left = curve[
            curve["window_id"].astype(str).eq("full_2018_2026")
            & curve["promotion_arm"].astype(str).eq(arm)
        ].sort_values("date")
        right = source_curve[source_curve["experiment_arm"].astype(str).eq(arm)].sort_values("date")
        if s13._date_keys(left["date"]) != s13._date_keys(right["date"]):
            raise RuntimeError(f"stage022_full_curve_date_drift:{arm}")
        if not _csv_equity_values_match(left["account_equity"], right["account_equity"]):
            raise RuntimeError(f"stage022_full_curve_equity_drift:{arm}")


def _decision(comparison: pd.DataFrame, aggregate: pd.DataFrame, contract: pd.DataFrame) -> dict[str, Any]:
    full_rows: list[dict[str, Any]] = []
    for comparison_name, _, _ in COMPARISONS:
        row = comparison[
            comparison["window_group"].eq("full_period")
            & comparison["comparison"].eq(comparison_name)
        ].iloc[0]
        gates = s7._full_period_gates(row)
        full_rows.append({"comparison": comparison_name, "gates": gates, "pass": bool(all(gates.values()))})
    cycle_rows: list[dict[str, Any]] = []
    for row in aggregate.to_dict(orient="records"):
        gates = s7._cycle_gates(row)
        cycle_rows.append({
            "comparison": str(row["comparison"]),
            "duration_years": int(row["duration_years"]),
            "start_cohort": str(row["start_cohort"]),
            "gates": gates,
            "pass": bool(all(gates.values())),
        })
    total = contract[contract["group_type"].astype(str).eq("total")].iloc[0]
    contract_gates = {
        "configuration_contract_pass": bool(int(total["configuration_contract_pass"]) == 1),
        "blocking_contract_pass": bool(int(total["blocking_contract_pass"]) == 1),
        "long_block_present": bool(int(total["long_blocked_count"]) > 0),
        "short_block_present": bool(int(total["short_blocked_count"]) > 0),
    }
    promotion_full = [row for row in full_rows if row["comparison"] in PROMOTION_COMPARISONS]
    promotion_cycles = [row for row in cycle_rows if row["comparison"] in PROMOTION_COMPARISONS]
    full_pass = bool(all(row["pass"] for row in promotion_full))
    all_pass = bool(all(contract_gates.values()) and full_pass and all(row["pass"] for row in promotion_cycles))
    return {
        "line_id": "futures_trend_rollover_shape_same_volume",
        "stage": "Stage022",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "diagnostic_override_reason": "user_requested_q_multicycle_after_stage021_full_period_gate_failure",
        "gate_contract": {
            "data_start": str(DATA_START.date()),
            "data_end": str(DATA_END.date()),
            "start_schedule": "January and June",
            "durations_years": list(DURATIONS_YEARS),
            "complete_windows_only_for_decision": True,
            "terminal_near_complete_tolerance_days": TERMINAL_TOLERANCE_DAYS,
            "P_rule": "N symmetric volume scaling; block long adverse move strictly above prior ATR5",
            "Q_rule": "P plus block short adverse move strictly above prior ATR5",
            "promotion_comparisons": sorted(PROMOTION_COMPARISONS),
            "full_period_failure_remains_binding": True,
        },
        "run_provenance": {
            "candidate_freeze_commit": _git_head(),
            "reused_source_stage": REUSED_SOURCE_STAGE,
            "reused_source_commit": REUSED_SOURCE_COMMIT,
            "reused_arms": sorted(REUSED_ARMS),
            "reused_independent_run_count": len(WINDOWS) * len(REUSED_ARMS),
            "new_arms": sorted(NEW_RUN_ARMS),
            "new_independent_run_count": len(WINDOWS) * len(NEW_RUN_ARMS),
            "logical_arm_window_count": len(WINDOWS) * len(ARMS),
            "full_period_identity_verified_against_stage021": True,
        },
        "window_count": len(WINDOWS),
        "comparison_row_count": len(comparison),
        "aggregate_row_count": len(aggregate),
        "atr_filter_contract_gates": contract_gates,
        "full_period_gates": full_rows,
        "cycle_gates": cycle_rows,
        "full_period_failure_is_binding": not full_pass,
        "q_all_multicycle_gates_pass": all_pass,
        "decision": "q_multicycle_supports_formal_review" if all_pass else "confirm_q_not_promotable_after_multicycle",
        "order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
    }


def _plot_full(curves: pd.DataFrame) -> bytes:
    frame = curves[curves["window_id"].eq("full_2018_2026")]
    fig, ax = plt.subplots(figsize=(14, 6))
    for arm in ARMS:
        item = frame[frame["promotion_arm"].eq(arm["arm"])].sort_values("date")
        ax.plot(pd.to_datetime(item["date"]), item["account_equity"] / 10_000.0, color=arm["color"], lw=1.4, label=arm["plot_label"])
    ax.set_title("Stage022 Full-Period Equity: A / C / P / Q")
    ax.set_ylabel("Equity (10k CNY)")
    ax.grid(alpha=0.25)
    ax.legend(fontsize=9)
    fig.tight_layout()
    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=170)
    plt.close(fig)
    return buffer.getvalue()


def _plot_window_grid(curves: pd.DataFrame, comparison: pd.DataFrame, years: int) -> bytes:
    selected = comparison[
        comparison["duration_years"].eq(years) & comparison["comparison"].eq("A_vs_C")
    ].sort_values(["requested_start", "window_id"])
    rows = int(np.ceil(len(selected) / 4.0))
    fig, axes = plt.subplots(rows, 4, figsize=(18, 3.5 * rows), squeeze=False)
    for ax, (_, window) in zip(axes.ravel(), selected.iterrows(), strict=False):
        window_curves = curves[curves["window_id"].eq(window["window_id"])]
        for arm in ARMS:
            frame = window_curves[window_curves["promotion_arm"].eq(arm["arm"])].sort_values("date")
            ax.plot(pd.to_datetime(frame["date"]), frame["account_equity"] / 10_000.0, color=arm["color"], lw=1.0, label=arm["plot_label"])
        suffix = " *" if int(window["terminal_near_complete"]) else ""
        ax.set_title(f"{window['requested_start']}  ({years}Y){suffix}", fontsize=10)
        ax.set_ylabel("Equity (10k CNY)")
        ax.grid(alpha=0.22)
        ax.tick_params(axis="x", rotation=25, labelsize=8)
    for ax in axes.ravel()[len(selected):]:
        ax.axis("off")
    handles, labels = axes.ravel()[0].get_legend_handles_labels()
    fig.suptitle(f"Stage022 {years}-Year Independent Equity Curves: January + June Starts", y=0.998, fontsize=15)
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 0.975), ncol=4, fontsize=8)
    fig.text(0.995, 0.005, "* near-complete terminal window; observation only", ha="right", fontsize=8)
    fig.tight_layout(rect=[0, 0.015, 1, 0.935])
    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=150)
    plt.close(fig)
    return buffer.getvalue()


def _plot_aggregate(aggregate: pd.DataFrame) -> bytes:
    row_keys = [(comparison, cohort) for comparison, _, _ in COMPARISONS for cohort, _ in COHORTS]
    row_labels = [f"{comparison} {cohort}" for comparison, cohort in row_keys]
    metrics = [
        ("return_win_rate_pct", "Return Win Rate (%)", "YlGn", 0.0, 100.0),
        ("median_return_delta_pct", "Median Return Delta (pp)", "coolwarm", None, None),
        ("dd_noninferior_2pp_rate_pct", "DD Non-Inferior <=2pp (%)", "YlOrBr", 0.0, 100.0),
        ("slippage_ratio", "Aggregate Slippage Ratio (%)", "Reds", None, None),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(18, 16))
    for ax, (column, title, cmap, fixed_min, fixed_max) in zip(axes.ravel(), metrics, strict=True):
        values = np.empty((len(row_keys), len(DURATIONS_YEARS)), dtype=float)
        for row_index, (comparison_name, cohort) in enumerate(row_keys):
            for col_index, years in enumerate(DURATIONS_YEARS):
                row = aggregate[
                    aggregate["comparison"].eq(comparison_name)
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
                ax.text(col_index, row_index, f"{values[row_index, col_index]:.1f}", ha="center", va="center", fontsize=7)
        ax.set_title(title)
        ax.set_xticks(range(len(DURATIONS_YEARS)), [f"{years}Y" for years in DURATIONS_YEARS])
        ax.set_yticks(range(len(row_labels)), row_labels, fontsize=7)
        fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    fig.suptitle("Stage022 Multi-Cycle A/C/P/Q: Combined, January, June", fontsize=15)
    fig.tight_layout(rect=[0, 0, 1, 0.98])
    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=170)
    plt.close(fig)
    return buffer.getvalue()


def _charts(curve: pd.DataFrame, comparison: pd.DataFrame, aggregate: pd.DataFrame) -> dict[str, bytes]:
    return {
        CHART_FILES["full_period"]: _plot_full(curve),
        CHART_FILES["1y"]: _plot_window_grid(curve, comparison, 1),
        CHART_FILES["2y"]: _plot_window_grid(curve, comparison, 2),
        CHART_FILES["3y"]: _plot_window_grid(curve, comparison, 3),
        CHART_FILES["aggregate"]: _plot_aggregate(aggregate),
    }


def _publish_atomically(frames: dict[str, pd.DataFrame], decision: dict[str, Any], charts: dict[str, bytes]) -> None:
    OUTPUT_DIR.parent.mkdir(parents=True, exist_ok=True)
    temporary_dir = Path(tempfile.mkdtemp(prefix=".stage022.tmp-", dir=OUTPUT_DIR.parent))
    backup_dir = OUTPUT_DIR.with_name(f".stage022.backup-{uuid4().hex}")
    try:
        for filename, frame in frames.items():
            frame.to_csv(temporary_dir / filename, index=False, encoding="utf-8-sig")
        (temporary_dir / DECISION_PATH.name).write_text(json.dumps(decision, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
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


def _assemble(
    reused_summary: pd.DataFrame,
    reused_curve: pd.DataFrame,
    new_summaries: list[pd.DataFrame],
    new_curves: list[pd.DataFrame],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    summary = pd.concat([reused_summary, *new_summaries], ignore_index=True, sort=False)
    curve = pd.concat([reused_curve, *new_curves], ignore_index=True, sort=False)
    window_order = {str(window["window_id"]): index for index, window in enumerate(WINDOWS)}
    arm_order = {str(arm["arm"]): index for index, arm in enumerate(ARMS)}
    summary["_window_order"] = summary["window_id"].astype(str).map(window_order)
    summary["_arm_order"] = summary["promotion_arm"].astype(str).map(arm_order)
    summary = summary.sort_values(["_window_order", "_arm_order"]).drop(columns=["_window_order", "_arm_order"])
    curve["_window_order"] = curve["window_id"].astype(str).map(window_order)
    curve["_arm_order"] = curve["promotion_arm"].astype(str).map(arm_order)
    curve = curve.sort_values(["_window_order", "_arm_order", "date"]).drop(columns=["_window_order", "_arm_order"])
    return summary, curve


def main() -> None:
    metadata = s513._metadata()
    reused_summary, reused_curve = _load_reused_arms()
    new_summaries: list[pd.DataFrame] = []
    new_curves: list[pd.DataFrame] = []
    full_q_frames: dict[str, pd.DataFrame] = {}
    run_total = len(WINDOWS) * len(NEW_RUN_ARMS)
    run_index = 0
    for window in WINDOWS:
        for arm in ARMS:
            if str(arm["arm"]) not in NEW_RUN_ARMS:
                continue
            run_index += 1
            print(f"[stage022] {run_index}/{run_total} {window['window_id']} arm={arm['arm']}", flush=True)
            summary, curve, frames = _run_candidate_window(metadata, window, arm)
            new_summaries.append(summary)
            new_curves.append(curve)
            if str(window["window_id"]) == "full_2018_2026" and str(arm["arm"]) == "Q":
                full_q_frames = {key: value.copy() for key, value in frames.items()}
    summary, curve = _assemble(reused_summary, reused_curve, new_summaries, new_curves)
    _validate_outputs(summary, curve)
    _verify_full_identity(summary, curve)
    comparison = _comparison(summary)
    aggregate = _aggregate(comparison)
    diagnostics = full_q_frames.get("long_signal_atr_shock", pd.DataFrame()).copy()
    contract = s21._atr_filter_contract_summary(diagnostics)
    decision = _decision(comparison, aggregate, contract)
    _publish_atomically(
        {
            SUMMARY_PATH.name: summary,
            COMPARISON_PATH.name: comparison,
            AGGREGATE_PATH.name: aggregate,
            CURVE_PATH.name: curve,
            Q_ENTRY_RISK_PATH.name: full_q_frames.get("entry_risk", pd.DataFrame()).copy(),
            Q_TRADES_PATH.name: full_q_frames.get("trades", pd.DataFrame()).copy(),
            Q_TRADE_EVENTS_PATH.name: full_q_frames.get("trade_events", pd.DataFrame()).copy(),
            Q_ATR_FILTER_PATH.name: diagnostics,
            Q_ATR_CONTRACT_PATH.name: contract,
        },
        decision,
        _charts(curve, comparison, aggregate),
    )
    print(json.dumps(decision, ensure_ascii=False, indent=2))


def rebuild_from_published() -> None:
    summary = pd.read_csv(SUMMARY_PATH)
    curve = pd.read_csv(CURVE_PATH)
    _validate_outputs(summary, curve)
    _verify_full_identity(summary, curve)
    comparison = _comparison(summary)
    aggregate = _aggregate(comparison)
    diagnostics = pd.read_csv(Q_ATR_FILTER_PATH)
    contract = s21._atr_filter_contract_summary(diagnostics)
    decision = _decision(comparison, aggregate, contract)
    _publish_atomically(
        {
            SUMMARY_PATH.name: summary,
            COMPARISON_PATH.name: comparison,
            AGGREGATE_PATH.name: aggregate,
            CURVE_PATH.name: curve,
            Q_ENTRY_RISK_PATH.name: pd.read_csv(Q_ENTRY_RISK_PATH),
            Q_TRADES_PATH.name: pd.read_csv(Q_TRADES_PATH),
            Q_TRADE_EVENTS_PATH.name: pd.read_csv(Q_TRADE_EVENTS_PATH),
            Q_ATR_FILTER_PATH.name: diagnostics,
            Q_ATR_CONTRACT_PATH.name: contract,
        },
        decision,
        _charts(curve, comparison, aggregate),
    )
    print(json.dumps(decision, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if "--rebuild-from-published" in sys.argv:
        rebuild_from_published()
    else:
        main()
