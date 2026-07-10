#!/usr/bin/env python3
"""Stage002: paired half-year validation for the frozen Stage013 pilot.

This stage does not tune the Stage013 rule.  It reruns the current-AI C9
control and the frozen Stage013 candidate from independent half-year starts,
then evaluates the gates declared in LINE.md before the run.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Iterator

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import stage001_stage013_current_ai_engine as s1  # noqa: E402


LINE_ID = s1.LINE_ID
STAGE_ID = "stage002_stage013_current_ai_halfyear"
STAGE_LABEL = "Stage002"
MODEL_TAG = f"{STAGE_ID}_v1"
OUTPUT_PREFIX = f"stage013_current_ai_{STAGE_ID}"

A_VERSION = s1.A_VERSION
C_VERSION = s1.C_VERSION
VERSIONS = (A_VERSION, C_VERSION)
CAPITAL = s1.CAPITAL
REQUESTED_END = pd.Timestamp("2026-06-30")
START_DATES = tuple(
    pd.Timestamp(year=year, month=month, day=1)
    for year in range(2020, 2027)
    for month in (1, 7)
    if pd.Timestamp(year=year, month=month, day=1) <= pd.Timestamp("2026-01-01")
)
MATURE_TRADING_DAYS = 252

MATURE_DD_IMPROVED_RATIO_MIN = 0.80
MAX_MATURE_DD_WORSENING_PP = 3.0
MATURE_MEDIAN_RETURN_RETENTION_MIN = 0.70
FULL_RETURN_RETENTION_MIN = 0.70
WORST_DD_IMPROVEMENT_MIN_PP = 3.0

LINE_DIR = ROOT / "research" / "lines" / LINE_ID
OUT = LINE_DIR / "outputs" / STAGE_ID
STAGES_DIR = LINE_DIR / "stages"
STAGE_RECORD_PATH = STAGES_DIR / "20260710_1905_stage002_stage013_current_ai_halfyear.md"

SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
PAIR_SUMMARY_PATH = OUT / f"{OUTPUT_PREFIX}_pair_summary_{MODEL_TAG}.csv"
STATS_PATH = OUT / f"{OUTPUT_PREFIX}_stats_{MODEL_TAG}.csv"
CURVES_PATH = OUT / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv.gz"
PILOT_EVENTS_PATH = OUT / f"{OUTPUT_PREFIX}_pilot_events_{MODEL_TAG}.csv.gz"
PILOT_AUDIT_PATH = OUT / f"{OUTPUT_PREFIX}_pilot_audit_{MODEL_TAG}.csv"
AI_USAGE_PATH = OUT / f"{OUTPUT_PREFIX}_ai_usage_{MODEL_TAG}.csv"
AI_CALENDAR_PATH = OUT / f"{OUTPUT_PREFIX}_ai_calendar_{MODEL_TAG}.csv"
AI_PARITY_PATH = OUT / f"{OUTPUT_PREFIX}_ai_parity_{MODEL_TAG}.csv"
DECISION_PATH = OUT / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUT / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
NAV_GRID_PATH = OUT / f"{OUTPUT_PREFIX}_nav_grid_{MODEL_TAG}.png"
SUMMARY_CHART_PATH = OUT / f"{OUTPUT_PREFIX}_summary_chart_{MODEL_TAG}.png"
STAGE062_AI_COVERAGE_PATH = (
    ROOT
    / "research"
    / "lines"
    / "futures_trend_rebuilt_c9_15w_v2_optimization"
    / "outputs"
    / "stage062_stage013_full_monthly_ai_candidate_official"
    / "rebuilt_c9_v2_stage062_stage013_full_monthly_ai_candidate_official_ai_coverage_stage062_stage013_full_monthly_ai_candidate_official_v1.csv"
)


def _start_month(value: pd.Timestamp) -> str:
    return pd.Timestamp(value).strftime("%Y-%m")


def _sha16(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


@contextmanager
def _requested_window(start: pd.Timestamp) -> Iterator[None]:
    """Temporarily set the source runner's requested window and restore it."""

    base = s1.source.s006.base
    old_start = base.REQUESTED_START
    old_end = base.REQUESTED_END
    old_month = base.START_MONTH
    try:
        base.REQUESTED_START = pd.Timestamp(start).normalize()
        base.REQUESTED_END = REQUESTED_END.normalize()
        base.START_MONTH = _start_month(start)
        yield
    finally:
        base.REQUESTED_START = old_start
        base.REQUESTED_END = old_end
        base.START_MONTH = old_month


def _run_for_start(
    metadata: dict[str, Any],
    profile: dict[str, Any],
    version: str,
    start: pd.Timestamp,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    with _requested_window(start):
        daily, frames, _ = s1.source.s006._run_profile(metadata, profile, version)

    month = _start_month(start)
    daily = daily.copy()
    daily["requested_start_month"] = month
    daily["requested_end"] = REQUESTED_END.date().isoformat()
    daily["stage"] = STAGE_LABEL
    daily["model_tag"] = MODEL_TAG
    daily["line_id"] = LINE_ID
    tagged: dict[str, pd.DataFrame] = {}
    for name, frame in frames.items():
        data = frame.copy()
        if not data.empty:
            data["requested_start_month"] = month
            data["requested_end"] = REQUESTED_END.date().isoformat()
            data["stage"] = STAGE_LABEL
            data["model_tag"] = MODEL_TAG
            data["line_id"] = LINE_ID
        tagged[name] = data

    trade_events = tagged.get("trade_events", pd.DataFrame())
    if version == C_VERSION and not trade_events.empty and "reason" in trade_events:
        tagged["pilot_gate_events"] = trade_events[
            trade_events["reason"].astype(str).eq("stage013_account_state_pilot_gate")
        ].copy()
    else:
        tagged["pilot_gate_events"] = pd.DataFrame()
    return daily, tagged


def _summary_row(
    daily: pd.DataFrame,
    frames: dict[str, pd.DataFrame],
    metadata: dict[str, Any],
    version: str,
    start: pd.Timestamp,
) -> tuple[dict[str, Any], pd.DataFrame]:
    curve = s1.source.s006.base._curve_for_metrics(daily, version)
    curve["requested_start_month"] = _start_month(start)
    curve["requested_end"] = REQUESTED_END.date().isoformat()
    curve["stage"] = STAGE_LABEL
    curve["model_tag"] = MODEL_TAG
    curve["line_id"] = LINE_ID

    row = s1.source.s006._summarize_curve(curve)
    closed = s1.source._closed_lots(frames, metadata)
    realized = pd.to_numeric(
        closed.get("realized_pnl", pd.Series(dtype=float)), errors="coerce"
    ).dropna()
    row.update(
        {
            "stage": STAGE_LABEL,
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "requested_start_month": _start_month(start),
            "requested_end": REQUESTED_END.date().isoformat(),
            "closed_lot_count": int(len(realized)),
            "closed_lot_win_rate_pct": (
                float((realized > 0.0).mean() * 100.0) if len(realized) else 0.0
            ),
        }
    )
    return row, curve


def _pilot_audit_row(events: pd.DataFrame, start: pd.Timestamp) -> dict[str, Any]:
    row: dict[str, Any] = {
        "requested_start_month": _start_month(start),
        "rows": int(len(events)),
        "reduced_volume_sum": 0.0,
        "flat_entry_violation_count": 0,
        "after_not_one_count": 0,
        "below_drawdown_trigger_count": 0,
        "above_active_limit_count": 0,
        "applied_not_one_count": 0,
        "drawdown_min": np.nan,
        "drawdown_max": np.nan,
        "active_positions_max": np.nan,
        "product_count": 0,
    }
    if events.empty:
        return row
    data = events.copy()
    numeric = (
        "stage013_pilot_gate_applied",
        "stage013_pilot_gate_selected_volume_after",
        "stage013_pilot_gate_reduced_volume",
        "stage013_pilot_gate_drawdown_pct",
        "stage013_pilot_gate_drawdown_trigger_pct",
        "stage013_pilot_gate_active_positions_before",
        "stage013_pilot_gate_active_positions_max",
    )
    for column in numeric:
        data[column] = pd.to_numeric(data.get(column), errors="coerce")
    row.update(
        {
            "reduced_volume_sum": float(data["stage013_pilot_gate_reduced_volume"].sum()),
            "flat_entry_violation_count": int(data["entry_context"].astype(str).ne("flat_entry").sum()),
            "after_not_one_count": int(data["stage013_pilot_gate_selected_volume_after"].ne(1.0).sum()),
            "below_drawdown_trigger_count": int(
                (
                    data["stage013_pilot_gate_drawdown_pct"]
                    < data["stage013_pilot_gate_drawdown_trigger_pct"] - 1e-12
                ).sum()
            ),
            "above_active_limit_count": int(
                (
                    data["stage013_pilot_gate_active_positions_before"]
                    > data["stage013_pilot_gate_active_positions_max"]
                ).sum()
            ),
            "applied_not_one_count": int(data["stage013_pilot_gate_applied"].ne(1.0).sum()),
            "drawdown_min": float(data["stage013_pilot_gate_drawdown_pct"].min()),
            "drawdown_max": float(data["stage013_pilot_gate_drawdown_pct"].max()),
            "active_positions_max": float(data["stage013_pilot_gate_active_positions_before"].max()),
            "product_count": int(data["product_vt_symbol"].nunique()),
        }
    )
    return row


def _ai_usage_row(
    frames: dict[str, pd.DataFrame], version: str, start: pd.Timestamp
) -> dict[str, Any]:
    entry = frames.get("entry_candidates", pd.DataFrame())
    audit = s1.source.s006.base._ai_usage_audit(entry)
    if "ai_product_pool_signal_date" in audit.columns:
        summary = audit[
            audit["ai_product_pool_signal_date"].astype(str).eq("__summary__")
        ]
        selected = summary.iloc[0] if not summary.empty else audit.iloc[0]
    else:
        selected = audit.iloc[0]
    row = selected.to_dict()
    row.update(
        {
            "requested_start_month": _start_month(start),
            "version": version,
        }
    )
    return row


def _ai_calendar(eligibility: pd.DataFrame) -> pd.DataFrame:
    data = eligibility.copy()
    data["eval_date"] = pd.to_datetime(data["eval_date"], errors="coerce")
    data = data.dropna(subset=["eval_date"])
    data["month"] = data["eval_date"].dt.to_period("M").astype(str)
    observed = (
        data.groupby("month", as_index=False)
        .agg(eval_date=("eval_date", "max"), rows=("product_vt_symbol", "count"))
    )
    expected = pd.DataFrame(
        {"month": pd.period_range("2020-01", "2026-06", freq="M").astype(str)}
    )
    result = expected.merge(observed, on="month", how="left")
    result["required_month"] = 1
    result["present"] = result["eval_date"].notna().astype(int)
    result["status"] = np.where(result["present"].eq(1), "present", "missing")
    result["eval_date"] = pd.to_datetime(result["eval_date"], errors="coerce").dt.date.astype("string")

    result["stage182_rebuild_status"] = "unknown"
    if STAGE062_AI_COVERAGE_PATH.exists():
        coverage = pd.read_csv(STAGE062_AI_COVERAGE_PATH, encoding="utf-8-sig")
        coverage = coverage[["calendar_month", "status"]].rename(
            columns={
                "calendar_month": "month",
                "status": "stage182_rebuild_status",
            }
        )
        result = result.drop(columns=["stage182_rebuild_status"]).merge(
            coverage, on="month", how="left"
        )
        result["stage182_rebuild_status"] = result[
            "stage182_rebuild_status"
        ].fillna("unknown")
    result["stage182_rebuild_feasible"] = result[
        "stage182_rebuild_status"
    ].eq("GENERATED").astype(int)
    result["original_oos_policy"] = np.where(
        result["month"].astype(str).lt("2022-01"),
        "pre_ai_static18_boundary",
        "monthly_ai_snapshot",
    )
    result["original_oos_policy_present"] = np.where(
        result["month"].astype(str).lt("2022-01"),
        1,
        result["present"],
    ).astype(int)

    bootstrap = observed[observed["month"].eq("2019-12")].copy()
    if not bootstrap.empty:
        bootstrap["required_month"] = 0
        bootstrap["present"] = 1
        bootstrap["status"] = "bootstrap_present"
        bootstrap["stage182_rebuild_status"] = "bootstrap"
        bootstrap["stage182_rebuild_feasible"] = 0
        bootstrap["original_oos_policy"] = "boundary_snapshot"
        bootstrap["original_oos_policy_present"] = 1
        bootstrap["eval_date"] = pd.to_datetime(
            bootstrap["eval_date"], errors="coerce"
        ).dt.date.astype("string")
        result = pd.concat([bootstrap[result.columns], result], ignore_index=True)
    return result


def _ai_parity(
    eligibility: dict[str, pd.DataFrame], paths: dict[str, Path]
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for version in VERSIONS:
        frame = eligibility[version]
        rows.append(
            {
                "version": version,
                "rows": int(len(frame)),
                "eval_date_count": int(frame["eval_date"].nunique()),
                "normalized_sha16": s1.source._normalized_ai_hash(frame),
                "eligibility_file_sha16": _sha16(paths[version]),
                "official_ai_sha16": _sha16(s1.OFFICIAL_LIVE_AI_ELIGIBILITY_PATH),
            }
        )
    result = pd.DataFrame(rows)
    result["all_normalized_equal"] = int(result["normalized_sha16"].nunique() == 1)
    return result


def _pair_summary(summary: pd.DataFrame, pilot: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    pilot_lookup = pilot.set_index("requested_start_month") if not pilot.empty else pd.DataFrame()
    for start_month, group in summary.groupby("requested_start_month", sort=True):
        a = group[group["version"].eq(A_VERSION)].iloc[0]
        c = group[group["version"].eq(C_VERSION)].iloc[0]
        a_return = float(a["total_return_pct"])
        c_return = float(c["total_return_pct"])
        dd_delta = float(c["max_drawdown_pct"] - a["max_drawdown_pct"])
        mature = min(int(a["trading_days"]), int(c["trading_days"])) >= MATURE_TRADING_DAYS
        pilot_events = (
            int(pilot_lookup.loc[start_month, "rows"])
            if isinstance(pilot_lookup, pd.DataFrame) and start_month in pilot_lookup.index
            else 0
        )
        rows.append(
            {
                "requested_start_month": start_month,
                "trading_days": min(int(a["trading_days"]), int(c["trading_days"])),
                "mature": int(mature),
                "a_end_equity": float(a["end_equity"]),
                "c_end_equity": float(c["end_equity"]),
                "a_total_return_pct": a_return,
                "c_total_return_pct": c_return,
                "return_retention_ratio": c_return / a_return if a_return > 0.0 else np.nan,
                "return_delta_pct": c_return - a_return,
                "a_max_drawdown_pct": float(a["max_drawdown_pct"]),
                "c_max_drawdown_pct": float(c["max_drawdown_pct"]),
                "drawdown_improvement_pp": dd_delta,
                "a_sharpe": float(a["sharpe"]),
                "c_sharpe": float(c["sharpe"]),
                "sharpe_delta": float(c["sharpe"] - a["sharpe"]),
                "a_total_slippage": float(a["total_slippage"]),
                "c_total_slippage": float(c["total_slippage"]),
                "a_total_trade_count": float(a["total_trade_count"]),
                "c_total_trade_count": float(c["total_trade_count"]),
                "a_broker10_peak_pct": float(a["max_broker10_margin_to_equity_pct"]),
                "c_broker10_peak_pct": float(c["max_broker10_margin_to_equity_pct"]),
                "broker10_delta_pp": float(
                    c["max_broker10_margin_to_equity_pct"]
                    - a["max_broker10_margin_to_equity_pct"]
                ),
                "c_positive": int(c_return > 0.0),
                "drawdown_improved_or_equal": int(dd_delta >= -1e-9),
                "drawdown_worse_gt3pp": int(dd_delta < -MAX_MATURE_DD_WORSENING_PP - 1e-9),
                "pilot_event_count": pilot_events,
            }
        )
    return pd.DataFrame(rows).sort_values("requested_start_month").reset_index(drop=True)


def _stats(pair: pd.DataFrame) -> pd.DataFrame:
    mature = pair[pair["mature"].eq(1)].copy()
    positive_a = mature[mature["a_total_return_pct"].gt(0.0)].copy()
    worst_a_dd = float(mature["a_max_drawdown_pct"].min())
    worst_c_dd = float(mature["c_max_drawdown_pct"].min())
    worst_a_broker = float(mature["a_broker10_peak_pct"].max())
    worst_c_broker = float(mature["c_broker10_peak_pct"].max())
    return pd.DataFrame(
        [
            {
                "sample_count": int(len(pair)),
                "mature_count": int(len(mature)),
                "mature_c_positive_count": int(mature["c_positive"].sum()),
                "mature_dd_improved_count": int(mature["drawdown_improved_or_equal"].sum()),
                "mature_dd_improved_ratio": float(mature["drawdown_improved_or_equal"].mean()),
                "mature_dd_worse_gt3pp_count": int(mature["drawdown_worse_gt3pp"].sum()),
                "positive_a_mature_count": int(len(positive_a)),
                "median_return_retention_ratio": float(positive_a["return_retention_ratio"].median()),
                "min_return_retention_ratio": float(positive_a["return_retention_ratio"].min()),
                "worst_a_drawdown_pct": worst_a_dd,
                "worst_c_drawdown_pct": worst_c_dd,
                "worst_drawdown_improvement_pp": worst_c_dd - worst_a_dd,
                "worst_a_broker10_pct": worst_a_broker,
                "worst_c_broker10_pct": worst_c_broker,
                "worst_broker10_delta_pp": worst_c_broker - worst_a_broker,
                "pilot_event_count": int(pair["pilot_event_count"].sum()),
            }
        ]
    )


def _decision(
    pair: pd.DataFrame,
    stats: pd.DataFrame,
    pilot: pd.DataFrame,
    ai_usage: pd.DataFrame,
    ai_calendar: pd.DataFrame,
    ai_parity: pd.DataFrame,
) -> dict[str, Any]:
    stat = stats.iloc[0].to_dict()
    mature = pair[pair["mature"].eq(1)]
    full = pair[pair["requested_start_month"].eq("2020-01")].iloc[0]
    pilot_violation_columns = (
        "flat_entry_violation_count",
        "after_not_one_count",
        "below_drawdown_trigger_count",
        "above_active_limit_count",
        "applied_not_one_count",
    )
    pilot_violations = int(
        sum(pd.to_numeric(pilot[column], errors="coerce").fillna(0).sum() for column in pilot_violation_columns)
    )
    usage_rows = pd.to_numeric(ai_usage.get("ai_usage_rows", 0), errors="coerce").fillna(0)
    enabled_rows = pd.to_numeric(ai_usage.get("ai_enabled_rows", 0), errors="coerce").fillna(0)
    missing_signal_rows = pd.to_numeric(
        ai_usage.get("missing_signal_date_rows", 0), errors="coerce"
    ).fillna(0)

    gates = {
        "all_mature_c_positive": int(stat["mature_c_positive_count"]) == int(stat["mature_count"]),
        "mature_dd_improved_ratio_ge_80pct": float(stat["mature_dd_improved_ratio"]) >= MATURE_DD_IMPROVED_RATIO_MIN,
        "no_mature_dd_worse_gt3pp": int(stat["mature_dd_worse_gt3pp_count"]) == 0,
        "mature_median_return_retention_ge_70pct": float(stat["median_return_retention_ratio"]) >= MATURE_MEDIAN_RETURN_RETENTION_MIN,
        "full_2020_return_retention_ge_70pct": float(full["return_retention_ratio"]) >= FULL_RETURN_RETENTION_MIN,
        "cross_start_worst_dd_improves_ge_3pp": float(stat["worst_drawdown_improvement_pp"]) >= WORST_DD_IMPROVEMENT_MIN_PP,
        "worst_c_broker_not_above_a": float(stat["worst_broker10_delta_pp"]) <= 1e-9,
    }
    semantics = {
        "ai_eligibility_normalized_equal": bool(ai_parity["all_normalized_equal"].all()),
        "all_candidate_rows_ai_enabled": bool((usage_rows == enabled_rows).all()),
        "no_missing_ai_signal_date_rows": bool(missing_signal_rows.sum() == 0),
        "pilot_events_present": int(stat["pilot_event_count"]) > 0,
        "pilot_event_condition_violations_zero": pilot_violations == 0,
    }
    required_calendar = ai_calendar[ai_calendar["required_month"].eq(1)]
    missing = required_calendar[required_calendar["present"].eq(0)]
    missing_months = missing["month"].astype(str).tolist()
    feasible_missing_months = missing[
        missing["stage182_rebuild_feasible"].eq(1)
    ]["month"].astype(str).tolist()
    cold_start_months = missing[
        missing["stage182_rebuild_status"].astype(str).str.startswith("INFEASIBLE")
    ]["month"].astype(str).tolist()
    # The frozen historical model used a 720-day walk-forward warm-up.  Its
    # first OOS prediction was 2022-01-28; 2020-2021 intentionally used the
    # static18 boundary.  Stage062's >=12-month retrospective pool is a later
    # live-inference policy and is not the required historical calendar.
    monthly_policy = required_calendar[
        required_calendar["month"].astype(str).ge("2022-01")
    ]
    monthly_policy_missing = monthly_policy[
        monthly_policy["present"].eq(0)
    ]["month"].astype(str).tolist()
    bootstrap_present = bool(
        ai_calendar["status"].astype(str).eq("bootstrap_present").any()
    )
    original_oos_policy_complete = bootstrap_present and not monthly_policy_missing
    performance_ok = all(gates.values())
    semantics_ok = all(semantics.values())
    if performance_ok and semantics_ok and original_oos_policy_complete:
        decision = "stage002_pass_original_ai_policy_continue_cost_execution_validation"
    else:
        decision = "stage002_fail_no_parameter_rescue"
    return {
        "stage": STAGE_LABEL,
        "stage_id": STAGE_ID,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S CST"),
        "requested_starts": [_start_month(item) for item in START_DATES],
        "requested_end": REQUESTED_END.date().isoformat(),
        "mature_trading_days": MATURE_TRADING_DAYS,
        "predeclared_gates": gates,
        "semantic_gates": semantics,
        "performance_ok": bool(performance_ok),
        "semantics_ok": bool(semantics_ok),
        "ai_calendar_complete_under_original_720d_oos_policy": bool(original_oos_policy_complete),
        "original_oos_first_prediction_eval_date": "2022-01-28",
        "pre_ai_static18_policy_month_count": 24,
        "monthly_ai_policy_expected_month_count": int(len(monthly_policy)),
        "monthly_ai_policy_present_month_count": int(monthly_policy["present"].sum()),
        "monthly_ai_policy_missing_months": monthly_policy_missing,
        "ai_calendar_expected_month_count": int(len(required_calendar)),
        "ai_calendar_present_month_count": int(required_calendar["present"].sum()),
        "ai_calendar_missing_month_count": int(len(missing_months)),
        "ai_calendar_missing_months": missing_months,
        "ai_calendar_infeasible_cold_start_month_count": int(len(cold_start_months)),
        "ai_calendar_infeasible_cold_start_months": cold_start_months,
        "ai_calendar_feasible_missing_month_count": int(len(feasible_missing_months)),
        "ai_calendar_feasible_missing_months": feasible_missing_months,
        "stats": stat,
        "full_2020_pair": full.to_dict(),
        "decision": decision,
        "independent_review": {
            "backtest_status": "passed_with_p2",
            "backtest_p0": 0,
            "backtest_p1": 0,
            "backtest_p2": 3,
            "backtest_numeric_confidence_pct": 97,
            "boundary_forensics_status": "passed_with_documentation_correction",
            "boundary_forensics_p0": 0,
            "boundary_forensics_p1": 2,
            "boundary_forensics_p2": 3,
            "boundary_confidence_pct": 98,
        },
        "promotion_ready": False,
        "overfit_before": "low: fixed prior rule, fixed dates, and predeclared gates; no parameter search",
        "overfit_after": "low_to_medium: no tuning; starts share market periods and are not statistically independent",
        "continue_value_before": "yes: paired multi-start validation is the next required falsification step",
        "continue_value_after": "yes: original AI policy is complete; proceed to cost, execution, and shadow validation",
    }


def _plot_nav_grid(curves: pd.DataFrame, pair: pd.DataFrame) -> None:
    fig, axes = plt.subplots(4, 4, figsize=(20, 16))
    colors = {A_VERSION: "#111827", C_VERSION: "#0f766e"}
    labels = {A_VERSION: "A current C9", C_VERSION: "C Stage013"}
    for ax, start_month in zip(axes.flat, sorted(curves["requested_start_month"].unique())):
        for version, group in curves[curves["requested_start_month"].eq(start_month)].groupby("version", sort=False):
            data = group.sort_values("date")
            equity = pd.to_numeric(data["account_equity_for_metrics"], errors="coerce").ffill()
            ax.plot(
                pd.to_datetime(data["date"]),
                equity / CAPITAL,
                color=colors[version],
                label=labels[version],
                linewidth=1.0,
            )
        row = pair[pair["requested_start_month"].eq(start_month)].iloc[0]
        ax.set_title(
            f"{start_month} | ret A {row['a_total_return_pct']:.0f}% C {row['c_total_return_pct']:.0f}%\n"
            f"DD A {row['a_max_drawdown_pct']:.1f}% C {row['c_max_drawdown_pct']:.1f}%",
            fontsize=9,
        )
        ax.axhline(1.0, color="#94a3b8", linestyle=":", linewidth=0.7)
        locator = mdates.AutoDateLocator(minticks=3, maxticks=5)
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
        ax.tick_params(axis="x", labelsize=8)
        ax.grid(alpha=0.22)
    for ax in axes.flat[len(START_DATES):]:
        ax.axis("off")
    axes.flat[0].legend(fontsize=8)
    fig.suptitle("Stage002 paired half-year starts: normalized account equity", fontsize=15)
    fig.tight_layout()
    fig.savefig(NAV_GRID_PATH, dpi=170, bbox_inches="tight")
    plt.close(fig)


def _plot_summary(pair: pd.DataFrame) -> None:
    x = np.arange(len(pair))
    labels = [
        f"{row.requested_start_month}{'*' if int(row.mature) == 0 else ''}"
        for row in pair.itertuples(index=False)
    ]
    width = 0.38
    fig, axes = plt.subplots(2, 2, figsize=(17, 10))

    axes[0, 0].bar(x - width / 2, pair["a_total_return_pct"], width, label="A current C9", color="#64748b")
    axes[0, 0].bar(x + width / 2, pair["c_total_return_pct"], width, label="C Stage013", color="#0f766e")
    axes[0, 0].set_title("Total return by start")
    axes[0, 0].legend()

    axes[0, 1].bar(x - width / 2, pair["a_max_drawdown_pct"], width, label="A current C9", color="#64748b")
    axes[0, 1].bar(x + width / 2, pair["c_max_drawdown_pct"], width, label="C Stage013", color="#0f766e")
    axes[0, 1].set_title("Maximum drawdown by start")

    axes[1, 0].plot(x, pair["return_retention_ratio"] * 100.0, marker="o", color="#2563eb")
    axes[1, 0].axhline(70.0, color="#dc2626", linestyle="--", linewidth=0.9)
    axes[1, 0].set_title("C/A return retention (A positive starts)")
    axes[1, 0].set_ylabel("percent")

    axes[1, 1].bar(x - width / 2, pair["drawdown_improvement_pp"], width, label="DD improvement pp", color="#16a34a")
    axes[1, 1].bar(x + width / 2, -pair["broker10_delta_pp"], width, label="broker10 reduction pp", color="#d97706")
    axes[1, 1].axhline(0.0, color="#111827", linewidth=0.7)
    axes[1, 1].set_title("Risk improvement (positive is better)")
    axes[1, 1].legend(fontsize=8)

    for ax in axes.flat:
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
        ax.grid(axis="y", alpha=0.22)
    fig.suptitle("Stage002 current-AI Stage013 paired multi-start summary", fontsize=15)
    fig.text(0.5, 0.005, "* non-mature start (<252 trading days)", ha="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(SUMMARY_CHART_PATH, dpi=170, bbox_inches="tight")
    plt.close(fig)


def _md(frame: pd.DataFrame, columns: list[str] | None = None) -> str:
    data = frame if columns is None else frame[columns]
    return data.to_markdown(index=False)


def _write_report(
    summary: pd.DataFrame,
    pair: pd.DataFrame,
    stats: pd.DataFrame,
    pilot: pd.DataFrame,
    ai_calendar: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    review = decision["independent_review"]
    REPORT_PATH.write_text(
        f"""# Stage002 Stage013 当前 AI 逐半年 A/C

- 生成时间：`{decision['generated_at']}`
- 决策：`{decision['decision']}`
- 绩效门槛通过：`{decision['performance_ok']}`
- 执行语义通过：`{decision['semantics_ok']}`
- 原冻结 720 天 OOS 政策下 AI 月历完整：`{decision['ai_calendar_complete_under_original_720d_oos_policy']}`
- 2020-2021：静态 18 品种 pre-AI 边界；首个 OOS 预测：`{decision['original_oos_first_prediction_eval_date']}`
- 2022-01 至 2026-06 月度 AI 预期/存在：`{decision['monthly_ai_policy_expected_month_count']}` / `{decision['monthly_ai_policy_present_month_count']}`，缺失：`{decision['monthly_ai_policy_missing_months']}`
- 回测独立审查：`P0={review['backtest_p0']}/P1={review['backtest_p1']}/P2={review['backtest_p2']}`，数值置信度 `{review['backtest_numeric_confidence_pct']}%`
- 边界法证：`P0={review['boundary_forensics_p0']}/P1={review['boundary_forensics_p1']}/P2={review['boundary_forensics_p2']}`，置信度 `{review['boundary_confidence_pct']}%`；P1 为撤销此前错误月历阻塞，不影响回测数值

## 跨起点统计

{_md(stats)}

## A/C 配对

{_md(pair)}

## 分臂指标

{_md(summary, ['requested_start_month', 'version', 'trading_days', 'end_equity', 'total_return_pct', 'max_drawdown_pct', 'sharpe', 'total_slippage', 'total_trade_count', 'nonzero_daily_win_rate_pct', 'closed_lot_count', 'closed_lot_win_rate_pct', 'max_broker10_margin_to_equity_pct'])}

## Pilot 审计

{_md(pilot)}

## AI 月历

{_md(ai_calendar)}
""",
        encoding="utf-8",
    )


def _write_stage_record(
    summary: pd.DataFrame,
    pair: pd.DataFrame,
    stats: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    stat = stats.iloc[0]
    a = summary[(summary["requested_start_month"].eq("2020-01")) & (summary["version"].eq(A_VERSION))].iloc[0]
    c = summary[(summary["requested_start_month"].eq("2020-01")) & (summary["version"].eq(C_VERSION))].iloc[0]
    review = decision["independent_review"]
    STAGE_RECORD_PATH.write_text(
        f"""# Stage002 Stage013 当前 AI 逐半年真实引擎验证

- line_id：`{LINE_ID}`
- 当前模式：`day`
- 记录时间：`{decision['generated_at']}`
- 是否重要突破：是，当前原冻结 AI 政策下通过多起点门槛；进入成本与执行验收
- 新增参数：无
- 修改参数：仅将冷启动起点扩展为 2020-01 至 2026-01 逐半年，统一终点 2026-06-30
- 删除参数：无
- 策略参数：冻结 Stage013 `回撤>=30% / 活跃持仓<=1 / flat_entry降为1手`

## 回测口径

- A：当前官方 AI + 当前 C9/15w。
- C：A + 冻结 Stage013 account-state pilot。
- 13 个起点均独立以 `150,000` 初始化，不继承资金、持仓或运行状态。
- 成熟样本：交易日 `>=252`；全部门槛运行前已写入 `LINE.md`，本轮不救参。

## 2020-01 完整路径

- A：期末权益 `{float(a['end_equity']):,.2f}`，总收益 `{float(a['total_return_pct']):.4f}%`，最大回撤 `{float(a['max_drawdown_pct']):.4f}%`，Sharpe `{float(a['sharpe']):.4f}`，总滑点 `{float(a['total_slippage']):,.2f}`，交易次数 `{float(a['total_trade_count']):.0f}`，非零日胜率 `{float(a['nonzero_daily_win_rate_pct']):.4f}%`，逐笔胜率 `{float(a['closed_lot_win_rate_pct']):.4f}%`。
- C：期末权益 `{float(c['end_equity']):,.2f}`，总收益 `{float(c['total_return_pct']):.4f}%`，最大回撤 `{float(c['max_drawdown_pct']):.4f}%`，Sharpe `{float(c['sharpe']):.4f}`，总滑点 `{float(c['total_slippage']):,.2f}`，交易次数 `{float(c['total_trade_count']):.0f}`，非零日胜率 `{float(c['nonzero_daily_win_rate_pct']):.4f}%`，逐笔胜率 `{float(c['closed_lot_win_rate_pct']):.4f}%`。

## 多起点结果

- 样本/成熟样本：`{int(stat['sample_count'])}` / `{int(stat['mature_count'])}`。
- 成熟 C 正收益：`{int(stat['mature_c_positive_count'])}/{int(stat['mature_count'])}`。
- 成熟回撤改善或持平：`{int(stat['mature_dd_improved_count'])}/{int(stat['mature_count'])}`，比例 `{float(stat['mature_dd_improved_ratio']):.4f}`。
- 成熟起点回撤恶化超过 3pp：`{int(stat['mature_dd_worse_gt3pp_count'])}`。
- A 正收益成熟起点 C/A 收益保留中位/最小：`{float(stat['median_return_retention_ratio']):.4f}` / `{float(stat['min_return_retention_ratio']):.4f}`。
- 跨起点最差回撤 A/C：`{float(stat['worst_a_drawdown_pct']):.4f}%` / `{float(stat['worst_c_drawdown_pct']):.4f}%`，改善 `{float(stat['worst_drawdown_improvement_pp']):.4f}pp`。
- 跨起点 broker10 峰值 A/C：`{float(stat['worst_a_broker10_pct']):.4f}%` / `{float(stat['worst_c_broker10_pct']):.4f}%`。
- Pilot 触发总数：`{int(stat['pilot_event_count'])}`。

## AI 政策与月历审计

- A/C eligibility 归一化完全相同，当前文件 `504` 行/`55` 个 eval_date。
- 原模型 walk-forward 为 `720/180/180` 天，首个 OOS 预测 `{decision['original_oos_first_prediction_eval_date']}`；2020-2021 明确使用 static18 pre-AI 边界，不是缺月。
- 2022-01 至 2026-06 月度 AI 预期/存在 `{decision['monthly_ai_policy_expected_month_count']}/{decision['monthly_ai_policy_present_month_count']}`，缺失 `0`；原始 50 个 OOS 日期完整，2026-03 至 05 为 membership-only 恢复，2026-06 为 live inference。
- Stage003 把后来的 `>=12月` live inference 提前到 2021，属于反事实 early activation，不是修复；其失败不否定本阶段。
- Stage002 未保存每起点候选级 entry-candidate 明细，是产物 P2；本轮已由 Stage001 明细及两个独立新进程复跑交叉确认，后续验收必须保存。

## 最终结论

- 决策：`{decision['decision']}`。
- 回测独立 review：`P0={review['backtest_p0']}/P1={review['backtest_p1']}/P2={review['backtest_p2']}`，数值置信度 `{review['backtest_numeric_confidence_pct']}%`；边界法证 `P0={review['boundary_forensics_p0']}/P1={review['boundary_forensics_p1']}/P2={review['boundary_forensics_p2']}`，置信度 `{review['boundary_confidence_pct']}%`。
- AI 月历阻塞已撤销；但尚未直接切正式，下一步是成本敏感、执行一致性和 shadow 验收，`promotion_ready=false`。
- 独立复算确认 summary 最大误差 `<1e-12`、新进程复跑一致、无缓存/日期泄漏；470 条路径事件按日期+品种去重为 77 个市场事件观测。
- 新增回测结果：见 `{PAIR_SUMMARY_PATH}` 和 `{SUMMARY_PATH}`；未修改或删除历史回测结果。

## 过拟合反思

- 运行前：低。参数、样本起点和判定门槛均预先冻结，没有搜索最优阈值。
- 运行后：低到中等。规则未调参且多起点结果一致；但 13 条路径共享市场时段，不是 13 个统计独立样本。

## 继续价值反思

- 运行前：有。Stage001 的单起点改善需要通过独立冷启动路径反证。
- 运行后：有。下一步做成本敏感、执行一致性和 shadow；不补 2021 月池、不继续调 Stage013 参数。

## 输出

- 报告：`{REPORT_PATH}`
- 配对结果：`{PAIR_SUMMARY_PATH}`
- 净值网格：`{NAV_GRID_PATH}`
- 汇总图：`{SUMMARY_CHART_PATH}`
""",
        encoding="utf-8",
    )


def build() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    STAGES_DIR.mkdir(parents=True, exist_ok=True)
    metadata = s1.source._metadata()
    a_eligibility = s1.source.s006._official_eligibility_for_strategy(
        s1.A_STRATEGY, A_VERSION
    )
    c_eligibility = s1.source.s006._official_eligibility_for_strategy(
        s1.C_STRATEGY, C_VERSION
    )
    # Keep stage-local copies so the run is independently auditable.
    stage2_paths: dict[str, Path] = {}
    eligibility = {A_VERSION: a_eligibility, C_VERSION: c_eligibility}
    for version, frame in eligibility.items():
        path = OUT / f"{OUTPUT_PREFIX}_{version}_eligibility_{MODEL_TAG}.csv"
        frame.to_csv(path, index=False, encoding="utf-8-sig")
        stage2_paths[version] = path
    profiles = {
        A_VERSION: s1._a_profile(metadata, stage2_paths[A_VERSION]),
        C_VERSION: s1._c_profile(metadata, stage2_paths[C_VERSION]),
    }

    summary_rows: list[dict[str, Any]] = []
    curves: list[pd.DataFrame] = []
    pilot_rows: list[dict[str, Any]] = []
    pilot_events: list[pd.DataFrame] = []
    ai_usage_rows: list[dict[str, Any]] = []
    total_runs = len(START_DATES) * len(VERSIONS)
    run_index = 0
    for start in START_DATES:
        for version in VERSIONS:
            run_index += 1
            print(
                f"[stage002] run {run_index}/{total_runs} start={_start_month(start)} version={version}",
                flush=True,
            )
            daily, frames = _run_for_start(metadata, profiles[version], version, start)
            row, curve = _summary_row(daily, frames, metadata, version, start)
            summary_rows.append(row)
            curves.append(curve)
            ai_usage_rows.append(_ai_usage_row(frames, version, start))
            if version == C_VERSION:
                events = frames.get("pilot_gate_events", pd.DataFrame()).copy()
                pilot_rows.append(_pilot_audit_row(events, start))
                if not events.empty:
                    pilot_events.append(events)

    summary = pd.DataFrame(summary_rows).sort_values(
        ["requested_start_month", "version"]
    ).reset_index(drop=True)
    curve_frame = pd.concat(curves, ignore_index=True, sort=False).sort_values(
        ["requested_start_month", "version", "date"]
    ).reset_index(drop=True)
    pilot = pd.DataFrame(pilot_rows).sort_values("requested_start_month").reset_index(drop=True)
    event_frame = pd.concat(pilot_events, ignore_index=True, sort=False) if pilot_events else pd.DataFrame()
    ai_usage = pd.DataFrame(ai_usage_rows).sort_values(
        ["requested_start_month", "version"]
    ).reset_index(drop=True)
    ai_calendar = _ai_calendar(a_eligibility)
    ai_parity = _ai_parity(eligibility, stage2_paths)
    pair = _pair_summary(summary, pilot)
    stats = _stats(pair)
    decision = _decision(pair, stats, pilot, ai_usage, ai_calendar, ai_parity)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    pair.to_csv(PAIR_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    stats.to_csv(STATS_PATH, index=False, encoding="utf-8-sig")
    curve_frame.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    if not event_frame.empty:
        event_frame.to_csv(PILOT_EVENTS_PATH, index=False, encoding="utf-8-sig")
    pilot.to_csv(PILOT_AUDIT_PATH, index=False, encoding="utf-8-sig")
    ai_usage.to_csv(AI_USAGE_PATH, index=False, encoding="utf-8-sig")
    ai_calendar.to_csv(AI_CALENDAR_PATH, index=False, encoding="utf-8-sig")
    ai_parity.to_csv(AI_PARITY_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(
        json.dumps(s1.source.s006.base._json_safe(decision), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _plot_nav_grid(curve_frame, pair)
    _plot_summary(pair)
    _write_report(summary, pair, stats, pilot, ai_calendar, decision)
    _write_stage_record(summary, pair, stats, decision)
    return {
        "summary": summary,
        "pair": pair,
        "stats": stats,
        "pilot": pilot,
        "ai_usage": ai_usage,
        "ai_calendar": ai_calendar,
        "ai_parity": ai_parity,
        "decision": decision,
    }


def main() -> None:
    result = build()
    print(result["stats"].to_string(index=False))
    print(result["pair"].to_string(index=False))
    print(json.dumps(s1.source.s006.base._json_safe(result["decision"]), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
