from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage778_stage777_2022_drawdown_forensics as s778
import analyze_qmt_roll_stage800_stage777_long_lower_high_block_yearly as s800
import analyze_qmt_roll_stage804_stage777_long_tighter_initial_stop_yearly as s804


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage813_stage804_rsi_partial_exit_ablation_yearly_v1"
OUTPUT_PREFIX = "qmt_roll_stage813_stage804_rsi_partial_exit_ablation_yearly"
LINE_ID = "futures_trend_2019_data_extension"

YEAR_STARTS = s800.YEAR_STARTS
MAX_WORKERS = max(1, min(4, int(os.environ.get("STAGE813_MAX_WORKERS", "4"))))

OFF_VARIANT = "stage813_stage804_rsi_off_yearly"
ON_VARIANT = "stage813_stage804_rsi_on_yearly"

OFF_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_off_summary_{MODEL_TAG}.csv"
ON_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_on_summary_{MODEL_TAG}.csv"
OFF_CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_off_curves_{MODEL_TAG}.csv"
ON_CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_on_curves_{MODEL_TAG}.csv"
OFF_RSI_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_off_rsi_events_{MODEL_TAG}.csv"
ON_RSI_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_on_rsi_events_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_on_vs_off_{MODEL_TAG}.csv"
AGG_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_aggregate_on_vs_off_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _year_start_text(start: pd.Timestamp) -> str:
    return pd.Timestamp(start).strftime("%Y-%m")


def _profile(metadata: dict[str, Any], start: pd.Timestamp, *, enabled: bool) -> dict[str, Any]:
    base = s804._profile(metadata, start)
    spec = base["spec"]
    start_text = _year_start_text(start)
    variant = ON_VARIANT if enabled else OFF_VARIANT
    label = "Stage813 Stage804 RSI ON" if enabled else "Stage813 Stage804 RSI OFF"
    capital = replace(
        spec.capital,
        variant=f"{variant}_{start_text.replace('-', '_')}",
        label=f"{label} {start_text}",
        note=(
            f"{spec.capital.note} | Stage813 corrected RSI ablation. "
            f"enable_rsi_partial_exit={enabled}."
        ),
    )
    overrides = {
        **spec.overrides,
        "long_tighter_initial_stop": True,
        "enable_rsi_partial_exit": bool(enabled),
        "rsi_partial_exit_threshold": 95.0,
        "rsi_partial_exit_ratio": 0.5,
    }
    profile = dict(base)
    profile["profile"] = "stage813_stage804_rsi_on" if enabled else "stage813_stage804_rsi_off"
    profile["strategy_cls"] = base["strategy_cls"]
    profile["spec"] = replace(spec, capital=capital, overrides=overrides, profile=profile["profile"])
    profile["note"] = (
        "Stage804 with RSI partial exit explicitly ON."
        if enabled
        else "Stage804 with RSI partial exit explicitly OFF."
    )
    return profile


def _run_profile_once(
    *,
    profile: dict[str, Any],
    start: pd.Timestamp,
    metadata: dict[str, Any],
    base_c3_overrides: dict[str, Any],
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    combined, frames = s778._run_profile(
        profile=profile,
        start=start,
        metadata=metadata,
        base_c3_overrides=base_c3_overrides,
    )
    summary, curve = s804._metric_from_combined(profile, combined, start)
    trade_events = frames.get("trade_events", pd.DataFrame()).copy()
    if trade_events.empty or "reason" not in trade_events.columns:
        rsi_events = pd.DataFrame()
    else:
        reason = trade_events["reason"].astype(str)
        rsi_events = trade_events[reason.str.contains("rsi_partial_exit", na=False)].copy()
    rsi_events["requested_start_month"] = _year_start_text(start)
    rsi_events["start_month"] = _year_start_text(start)

    row = summary.iloc[0].to_dict()
    row["rsi_partial_exit_count"] = int(len(rsi_events))
    row["rsi_partial_exit_volume"] = (
        int(pd.to_numeric(rsi_events.get("volume", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
        if not rsi_events.empty
        else 0
    )
    return row, curve, rsi_events


def _run_one(start_text: str) -> tuple[
    dict[str, Any],
    pd.DataFrame,
    pd.DataFrame,
    dict[str, Any],
    pd.DataFrame,
    pd.DataFrame,
]:
    start = pd.Timestamp(start_text).normalize()
    metadata = s513._metadata()
    base_c3_overrides = dict(s513._c3_overrides(pd.Timestamp("2018-01-01").to_pydatetime()))
    off_row, off_curve, off_events = _run_profile_once(
        profile=_profile(metadata, start, enabled=False),
        start=start,
        metadata=metadata,
        base_c3_overrides=base_c3_overrides,
    )
    on_row, on_curve, on_events = _run_profile_once(
        profile=_profile(metadata, start, enabled=True),
        start=start,
        metadata=metadata,
        base_c3_overrides=base_c3_overrides,
    )
    return off_row, off_curve, off_events, on_row, on_curve, on_events


def _comparison(candidate: pd.DataFrame, base: pd.DataFrame) -> pd.DataFrame:
    comparison = s800._comparison(candidate, base).sort_values("start_month").reset_index(drop=True)
    for prefix, frame in [("base", base), ("candidate", candidate)]:
        for column in ["rsi_partial_exit_count", "rsi_partial_exit_volume"]:
            value_map = frame.set_index("start_month")[column].to_dict() if column in frame.columns else {}
            comparison[f"{column}_{prefix}"] = comparison["start_month"].map(value_map).fillna(0).astype(int)
    comparison["lower_high_block_count"] = 0
    return comparison


def _aggregate(comparison: pd.DataFrame) -> pd.DataFrame:
    aggregate = s800._aggregate(comparison)
    aggregate.rename(columns={"total_blocked_long_signals": "unused_total_blocked_long_signals"}, inplace=True)
    for bucket in aggregate["bucket"].astype(str).tolist():
        mask = comparison["start_month"].lt("2026-01") if bucket == "mature_ex_2026" else pd.Series(True, index=comparison.index)
        frame = comparison[mask].copy()
        idx = aggregate["bucket"].astype(str).eq(bucket)
        aggregate.loc[idx, "total_rsi_partial_exit_count_base"] = int(frame.get("rsi_partial_exit_count_base", 0).sum())
        aggregate.loc[idx, "total_rsi_partial_exit_volume_base"] = int(frame.get("rsi_partial_exit_volume_base", 0).sum())
        aggregate.loc[idx, "total_rsi_partial_exit_count_candidate"] = int(
            frame.get("rsi_partial_exit_count_candidate", 0).sum()
        )
        aggregate.loc[idx, "total_rsi_partial_exit_volume_candidate"] = int(
            frame.get("rsi_partial_exit_volume_candidate", 0).sum()
        )
    return aggregate


def _write_report(comparison: pd.DataFrame, aggregate: pd.DataFrame, decision: dict[str, Any]) -> None:
    display_cols = [
        "start_month",
        "total_return_pct_base",
        "total_return_pct_candidate",
        "total_return_pct_delta",
        "max_dd_pct_base",
        "max_dd_pct_candidate",
        "max_dd_pct_delta",
        "sharpe_base",
        "sharpe_candidate",
        "sharpe_delta",
        "total_trade_count_base",
        "total_trade_count_candidate",
        "rsi_partial_exit_count_base",
        "rsi_partial_exit_count_candidate",
        "rsi_partial_exit_volume_candidate",
    ]
    lines = [
        "# Stage813 corrected Stage804 RSI partial-exit ablation",
        "",
        f"- line_id: `{LINE_ID}`",
        f"- model_tag: `{MODEL_TAG}`",
        "- Base: Stage804 with `enable_rsi_partial_exit=False` explicitly set.",
        "- Candidate: Stage804 with `enable_rsi_partial_exit=True`, threshold 95, ratio 0.5.",
        "- Why: Stage812 was invalid because Stage804 inherited `enable_rsi_partial_exit=True` from build_roll_setting defaults.",
        "",
        "## Aggregate ON vs OFF",
        "",
        _md_table(aggregate, max_rows=10),
        "",
        "## Yearly Comparison ON vs OFF",
        "",
        _md_table(comparison[display_cols], max_rows=20),
        "",
        "## Decision",
        "",
        f"- decision: `{decision['decision']}`",
        f"- judgment: {decision['judgment']}",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    tasks = [start.strftime("%Y-%m-%d") for start in YEAR_STARTS]
    off_rows: list[dict[str, Any]] = []
    on_rows: list[dict[str, Any]] = []
    off_curves: list[pd.DataFrame] = []
    on_curves: list[pd.DataFrame] = []
    off_events: list[pd.DataFrame] = []
    on_events: list[pd.DataFrame] = []

    print(f"[stage813] launching {len(tasks)} yearly corrected ablation runs workers={MAX_WORKERS}", flush=True)
    if MAX_WORKERS == 1:
        for idx, task in enumerate(tasks, start=1):
            print(f"[stage813] running {idx}/{len(tasks)} {task}", flush=True)
            off_row, off_curve, off_event, on_row, on_curve, on_event = _run_one(task)
            off_rows.append(off_row)
            off_curves.append(off_curve)
            off_events.append(off_event)
            on_rows.append(on_row)
            on_curves.append(on_curve)
            on_events.append(on_event)
    else:
        with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_map = {executor.submit(_run_one, task): task for task in tasks}
            for idx, future in enumerate(as_completed(future_map), start=1):
                task = future_map[future]
                off_row, off_curve, off_event, on_row, on_curve, on_event = future.result()
                off_rows.append(off_row)
                off_curves.append(off_curve)
                off_events.append(off_event)
                on_rows.append(on_row)
                on_curves.append(on_curve)
                on_events.append(on_event)
                print(f"[stage813] completed {idx}/{len(tasks)} {task}", flush=True)

    off_summary = s804.s772._add_month_fields(pd.DataFrame(off_rows)).sort_values("start_month").reset_index(drop=True)
    on_summary = s804.s772._add_month_fields(pd.DataFrame(on_rows)).sort_values("start_month").reset_index(drop=True)
    off_curve_df = pd.concat(off_curves, ignore_index=True, sort=False).sort_values(["start_month", "date"])
    on_curve_df = pd.concat(on_curves, ignore_index=True, sort=False).sort_values(["start_month", "date"])
    off_event_df = pd.concat(off_events, ignore_index=True, sort=False) if off_events else pd.DataFrame()
    on_event_df = pd.concat(on_events, ignore_index=True, sort=False) if on_events else pd.DataFrame()
    comparison = _comparison(on_summary, off_summary)
    aggregate = _aggregate(comparison)

    off_summary.to_csv(OFF_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    on_summary.to_csv(ON_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    off_curve_df.to_csv(OFF_CURVES_PATH, index=False, encoding="utf-8-sig")
    on_curve_df.to_csv(ON_CURVES_PATH, index=False, encoding="utf-8-sig")
    off_event_df.to_csv(OFF_RSI_EVENTS_PATH, index=False, encoding="utf-8-sig")
    on_event_df.to_csv(ON_RSI_EVENTS_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    aggregate.to_csv(AGG_PATH, index=False, encoding="utf-8-sig")

    mature = aggregate[aggregate["bucket"].eq("mature_ex_2026")].iloc[0].to_dict()
    decision_label = (
        "stage813_stage804_rsi_partial_exit_watch"
        if int(mature["candidate_return_win_count"]) >= 5 and int(mature["candidate_dd_win_count"]) >= 5
        else "stage813_stage804_rsi_partial_exit_not_promoted"
    )
    decision = {
        "stage": "Stage813",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "base": "Stage804 with RSI partial exit explicitly OFF",
        "candidate": "Stage804 with RSI partial exit explicitly ON",
        "decision": decision_label,
        "judgment": "Corrected ablation for the Stage812 baseline-contamination bug.",
        "aggregate_all": aggregate[aggregate["bucket"].eq("all")].iloc[0].to_dict(),
        "aggregate_mature_ex_2026": mature,
        "outputs": {
            "off_summary": str(OFF_SUMMARY_PATH),
            "on_summary": str(ON_SUMMARY_PATH),
            "comparison": str(COMPARISON_PATH),
            "aggregate": str(AGG_PATH),
            "report": str(REPORT_PATH),
        },
    }
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(comparison, aggregate, decision)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print("aggregate_on_vs_off")
    print(aggregate.to_string(index=False))
    print("comparison_on_vs_off")
    cols = [
        "start_month",
        "total_return_pct_base",
        "total_return_pct_candidate",
        "total_return_pct_delta",
        "max_dd_pct_base",
        "max_dd_pct_candidate",
        "max_dd_pct_delta",
        "sharpe_base",
        "sharpe_candidate",
        "sharpe_delta",
        "total_trade_count_base",
        "total_trade_count_candidate",
        "rsi_partial_exit_count_candidate",
        "rsi_partial_exit_volume_candidate",
    ]
    print(comparison[cols].to_string(index=False))


if __name__ == "__main__":
    main()
