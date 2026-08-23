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


LINE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = LINE_DIR / "artifacts" / "stage008"

DATA_START = s5.DATA_START
DATA_END = s5.DATA_END
DURATIONS_YEARS = s5.DURATIONS_YEARS
TERMINAL_TOLERANCE_DAYS = s5.TERMINAL_TOLERANCE_DAYS
WINDOWS = s5.WINDOWS
COHORTS = s7.COHORTS

SUMMARY_PATH = OUTPUT_DIR / "stage008_window_summary.csv"
COMPARISON_PATH = OUTPUT_DIR / "stage008_window_comparison.csv"
AGGREGATE_PATH = OUTPUT_DIR / "stage008_cycle_aggregate.csv"
CURVE_PATH = OUTPUT_DIR / "stage008_equity_curves.csv"
ENTRY_RISK_PATH = OUTPUT_DIR / "stage008_full_f_entry_risk.csv"
TRADES_PATH = OUTPUT_DIR / "stage008_full_f_trades.csv"
TRADE_EVENTS_PATH = OUTPUT_DIR / "stage008_full_f_trade_events.csv"
VOLUME_CONTRACT_PATH = OUTPUT_DIR / "stage008_full_f_volume_contract_summary.csv"
DECISION_PATH = OUTPUT_DIR / "stage008_decision.json"

CHART_FILES = {
    "full_period": "stage008_full_period_equity_acdf.png",
    "1y": "stage008_equity_curves_1y_acdf.png",
    "2y": "stage008_equity_curves_2y_acdf.png",
    "3y": "stage008_equity_curves_3y_acdf.png",
    "aggregate": "stage008_cycle_aggregate_acdf.png",
}

ARMS: tuple[dict[str, Any], ...] = (
    {
        "arm": "A",
        "rollover_candidate": False,
        "risk_boost": False,
        "volume_confirmation": False,
        "label": "A: Official C9/150k",
        "plot_label": "A Official",
        "color": "#2563eb",
    },
    {
        "arm": "C",
        "rollover_candidate": True,
        "risk_boost": False,
        "volume_confirmation": False,
        "label": "C: Official + rollover continuation",
        "plot_label": "C Rollover",
        "color": "#dc2626",
    },
    {
        "arm": "D",
        "rollover_candidate": True,
        "risk_boost": True,
        "volume_confirmation": False,
        "label": "D: C + directional 30D risk x1.2",
        "plot_label": "D Direction x1.2",
        "color": "#16a34a",
    },
    {
        "arm": "F",
        "rollover_candidate": True,
        "risk_boost": True,
        "volume_confirmation": True,
        "label": "F: C + 30D direction and 10D volume expansion risk x1.2",
        "plot_label": "F Direction + Volume x1.2",
        "color": "#9333ea",
    },
)

COMPARISONS: tuple[tuple[str, str, str], ...] = (
    ("A_vs_C", "A", "C"),
    ("A_vs_D", "A", "D"),
    ("C_vs_D", "C", "D"),
    ("A_vs_F", "A", "F"),
    ("C_vs_F", "C", "F"),
    ("D_vs_F", "D", "F"),
)


def _run_arm(
    metadata: dict[str, Any],
    arm: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame]]:
    original_overrides = s1._overrides

    def experiment_overrides(
        *,
        candidate: bool,
        volume_policy: str = "exact_or_skip",
        history_mode: str = "target_contract_only",
    ) -> dict[str, Any]:
        overrides = original_overrides(
            candidate=candidate,
            volume_policy=volume_policy,
            history_mode=history_mode,
        )
        overrides.update(
            {
                "enable_directional_30d_risk_boost": bool(arm["risk_boost"]),
                "directional_30d_risk_boost_lookback": 30,
                "directional_30d_risk_boost_multiplier": 1.2,
                "directional_30d_risk_boost_require_volume_expansion": bool(
                    arm["volume_confirmation"]
                ),
                "directional_30d_volume_recent_days": 10,
                "directional_30d_volume_prior_days": 10,
            }
        )
        return overrides

    try:
        s1._overrides = experiment_overrides
        summary, curve, frames = s1._run_arm(
            profile_name=str(arm["profile"]),
            candidate=bool(arm["rollover_candidate"]),
            metadata=metadata,
            volume_policy="shrink_to_allowed",
            history_mode=(
                "backwards_ratio_continuous"
                if bool(arm["rollover_candidate"])
                else "target_contract_only"
            ),
            label=str(arm["label"]),
        )
    finally:
        s1._overrides = original_overrides
    return summary, curve, frames


def _run_window(
    metadata: dict[str, Any],
    window: dict[str, Any],
    arm: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame]]:
    old_start, old_end = s1.START, s1.END
    runtime_arm = {**arm, "profile": f"stage008_{arm['arm']}_{window['window_id']}"}
    try:
        s1.START = pd.Timestamp(window["start"])
        s1.END = pd.Timestamp(window["end"])
        summary, curve, frames = _run_arm(metadata, runtime_arm)
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
    return result_summary, result_curve, frames


def _using_stage008_contract(function: Callable[..., Any], *args: Any) -> Any:
    original_arms, original_comparisons = s7.ARMS, s7.COMPARISONS
    try:
        s7.ARMS = ARMS
        s7.COMPARISONS = COMPARISONS
        return function(*args)
    finally:
        s7.ARMS, s7.COMPARISONS = original_arms, original_comparisons


def _validate_outputs(summary: pd.DataFrame, curves: pd.DataFrame) -> None:
    _using_stage008_contract(s7._validate_outputs, summary, curves)


def _comparison(summary: pd.DataFrame) -> pd.DataFrame:
    return _using_stage008_contract(s7._comparison, summary)


def _aggregate(comparison: pd.DataFrame) -> pd.DataFrame:
    return _using_stage008_contract(s7._aggregate, comparison)


def _volume_contract_summary(entry_risk: pd.DataFrame) -> pd.DataFrame:
    required = {
        "direction",
        "entry_context",
        "directional_30d_risk_boost_enabled",
        "directional_30d_volume_confirmation_enabled",
        "directional_30d_risk_boost_aligned",
        "directional_30d_volume_expanding",
        "directional_30d_risk_boost_applied",
        "directional_30d_risk_boost_multiplier",
        "risk_amount_before_directional_30d_boost",
        "target_risk_amount",
    }
    if entry_risk.empty or not required.issubset(entry_risk.columns):
        return pd.DataFrame(
            [
                {
                    "group_type": "total",
                    "group_value": "all",
                    "diagnostic_intent_count": 0,
                    "price_aligned_count": 0,
                    "volume_expanding_count": 0,
                    "boost_applied_count": 0,
                    "boost_suppressed_by_volume_count": 0,
                    "risk_amount_contract_pass": 0,
                }
            ]
        )

    frame = entry_risk.copy()
    for column in [
        "directional_30d_risk_boost_enabled",
        "directional_30d_volume_confirmation_enabled",
        "directional_30d_risk_boost_aligned",
        "directional_30d_volume_expanding",
        "directional_30d_risk_boost_applied",
        "directional_30d_risk_boost_multiplier",
        "risk_amount_before_directional_30d_boost",
        "target_risk_amount",
    ]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame[
        frame["directional_30d_risk_boost_enabled"].eq(1)
        & frame["directional_30d_volume_confirmation_enabled"].eq(1)
    ].copy()

    def summarize(group_type: str, group_value: str, group: pd.DataFrame) -> dict[str, Any]:
        aligned = group["directional_30d_risk_boost_aligned"].fillna(0).astype(int).eq(1)
        expanding = group["directional_30d_volume_expanding"].fillna(0).astype(int).eq(1)
        applied = group["directional_30d_risk_boost_applied"].fillna(0).astype(int).eq(1)
        expected_applied = aligned & expanding
        expected_multiplier = np.where(expected_applied, 1.2, 1.0)
        expected_risk = group["risk_amount_before_directional_30d_boost"] * expected_multiplier
        valid = (
            applied.eq(expected_applied)
            & group["risk_amount_before_directional_30d_boost"].notna()
            & group["target_risk_amount"].notna()
            & np.isclose(
                group["directional_30d_risk_boost_multiplier"].to_numpy(dtype="float64"),
                expected_multiplier,
                rtol=0.0,
                atol=1e-12,
            )
            & np.isclose(
                group["target_risk_amount"].to_numpy(dtype="float64"),
                expected_risk.to_numpy(dtype="float64"),
                rtol=1e-12,
                atol=1e-9,
            )
        )
        return {
            "group_type": group_type,
            "group_value": group_value,
            "diagnostic_intent_count": int(len(group)),
            "price_aligned_count": int(aligned.sum()),
            "volume_expanding_count": int(expanding.sum()),
            "boost_applied_count": int(applied.sum()),
            "boost_suppressed_by_volume_count": int((aligned & ~applied).sum()),
            "risk_amount_contract_pass": int(len(group) > 0 and bool(np.asarray(valid).all())),
        }

    rows = [summarize("total", "all", frame)]
    for column, group_type in (("direction", "direction"), ("entry_context", "entry_context")):
        for value, group in frame.groupby(column, sort=True, dropna=False):
            rows.append(summarize(group_type, str(value), group))
    return pd.DataFrame(rows)


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
    contract_gates = {
        "risk_amount_contract_pass": bool(int(total["risk_amount_contract_pass"]) == 1),
        "diagnostic_intents_present": bool(int(total["diagnostic_intent_count"]) > 0),
        "price_aligned_intents_present": bool(int(total["price_aligned_count"]) > 0),
        "volume_confirmed_boost_triggered": bool(int(total["boost_applied_count"]) > 0),
        "volume_gate_is_selective": bool(
            0 < int(total["boost_applied_count"]) < int(total["price_aligned_count"])
        ),
    }
    promotion_comparisons = {"A_vs_F", "C_vs_F"}
    promotion_full = [row for row in full_rows if row["comparison"] in promotion_comparisons]
    promotion_cycles = [row for row in cycle_rows if row["comparison"] in promotion_comparisons]
    all_pass = bool(
        all(contract_gates.values())
        and all(row["pass"] for row in promotion_full)
        and all(row["pass"] for row in promotion_cycles)
    )
    return {
        "line_id": "futures_trend_rollover_shape_same_volume",
        "stage": "Stage008",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "gate_contract": {
            "data_start": str(DATA_START.date()),
            "data_end": str(DATA_END.date()),
            "start_schedule": "January and June",
            "durations_years": list(DURATIONS_YEARS),
            "complete_windows_only_for_decision": True,
            "terminal_near_complete_tolerance_days": TERMINAL_TOLERANCE_DAYS,
            "F_rule": {
                "price_direction_lookback_days": 30,
                "recent_volume_window": "T-9 through T, includes signal day",
                "prior_volume_window": "T-19 through T-10",
                "volume_condition": "recent 10-day sum strictly greater than prior 10-day sum",
                "risk_multiplier_when_both_confirm": 1.2,
                "risk_multiplier_otherwise": 1.0,
                "invalid_or_insufficient_volume": "fail closed to no boost",
                "entry_context_scope": "flat, reverse, rollover reopen, regular add, donchian add, post-quality add",
            },
            "promotion_comparisons": sorted(promotion_comparisons),
        },
        "window_count": len(WINDOWS),
        "arm_run_count": len(WINDOWS) * len(ARMS),
        "comparison_row_count": len(comparison),
        "aggregate_row_count": len(aggregate),
        "volume_contract_gates": contract_gates,
        "full_period_gates": full_rows,
        "cycle_gates": cycle_rows,
        "volume_confirmed_candidate_all_gates_pass": all_pass,
        "decision": (
            "volume_confirmed_boost_candidate_supports_review"
            if all_pass
            else "volume_confirmed_boost_not_promotable"
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
            frame = window_curves[window_curves["promotion_arm"].eq(arm["arm"])].sort_values("date")
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
    fig.suptitle(f"Stage008 {years}-Year Independent Rolling Equity Curves", y=0.998, fontsize=15)
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 0.975), ncol=4)
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
            lw=1.45,
            label=arm["plot_label"],
        )
    ax.set_title("Stage008 Full-Period Equity: A Official vs C Rollover vs D Direction vs F Direction + Volume")
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
    fig.suptitle("Stage008 Multi-Cycle A/C/D/F Summary: Combined, January, June", fontsize=15)
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
    temporary_dir = Path(tempfile.mkdtemp(prefix=".stage008.tmp-", dir=OUTPUT_DIR.parent))
    backup_dir = OUTPUT_DIR.with_name(f".stage008.backup-{uuid4().hex}")
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
    full_f_frames: dict[str, pd.DataFrame] = {}
    for index, window in enumerate(WINDOWS, start=1):
        for arm in ARMS:
            print(
                f"[stage008] {index}/{len(WINDOWS)} {window['window_id']} arm={arm['arm']}",
                flush=True,
            )
            summary, curve, frames = _run_window(metadata, window, arm)
            summaries.append(summary)
            curves.append(curve)
            if str(window["window_id"]) == "full_2018_2026" and str(arm["arm"]) == "F":
                full_f_frames = {key: value.copy() for key, value in frames.items()}

    summary = pd.concat(summaries, ignore_index=True, sort=False)
    curve = pd.concat(curves, ignore_index=True, sort=False)
    _validate_outputs(summary, curve)
    comparison = _comparison(summary)
    aggregate = _aggregate(comparison)
    entry_risk = full_f_frames.get("entry_risk", pd.DataFrame()).copy()
    trades = full_f_frames.get("trades", pd.DataFrame()).copy()
    trade_events = full_f_frames.get("trade_events", pd.DataFrame()).copy()
    volume_contract = _volume_contract_summary(entry_risk)
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
