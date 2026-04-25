from __future__ import annotations

import json
import math
import sys
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any

import pandas as pd

from analyze_qmt_roll_stage105_margin_constraint_surface import (
    _calculate_daily_risk,
    _calculate_margin_path,
    _to_markdown_table,
)
from qmt_roll_official_stage78_config import (
    OFFICIAL_STAGE78_CAPITAL,
    OFFICIAL_STAGE78_REFERENCE_METRICS,
    OFFICIAL_STAGE78_VERSION,
    build_official_stage78_overrides,
)
from qmt_universe import END_DT, START_DT
from run_qmt_alignment_backtest import build_positions_df
from run_qmt_roll_backtest import run_backtest
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage125_incremental_margin_budget_gate_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage125_incremental_margin_budget_gate"

SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CANDIDATE_SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_candidate_summary_{MODEL_TAG}.csv"
BLOCKED_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_blocked_candidates_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


@dataclass(frozen=True)
class GateProfile:
    profile_name: str
    gate_usage_ratio: float


PROFILES: tuple[GateProfile, ...] = (
    GateProfile("stage78_incremental_gate90", 0.90),
    GateProfile("stage78_incremental_gate80", 0.80),
)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or math.isinf(result):
        return default
    return result


def _build_overrides(profile: GateProfile) -> dict[str, Any]:
    overrides = build_official_stage78_overrides()
    overrides.update(
        {
            "enable_incremental_margin_budget_gate": True,
            "incremental_margin_budget_gate_usage_ratio": profile.gate_usage_ratio,
        }
    )
    return overrides


def _candidate_summary(profile_name: str, candidates: pd.DataFrame) -> dict[str, Any]:
    if candidates.empty:
        return {
            "profile_name": profile_name,
            "flat_candidate_count": 0,
            "opened_flat_entry_count": 0,
            "blocked_by_incremental_gate_count": 0,
            "blocked_by_concurrent_limit_count": 0,
            "blocked_by_ai_pool_count": 0,
            "blocked_incremental_median_rank": 0.0,
            "blocked_incremental_min_rank": 0.0,
            "opened_median_rank": 0.0,
            "opened_median_ai_rank": 0.0,
            "blocked_incremental_median_ai_rank": 0.0,
            "opened_median_selected_volume": 0.0,
            "blocked_incremental_median_selected_volume": 0.0,
        }

    flat = candidates[candidates["entry_context"].astype(str).eq("flat_entry")].copy()
    if flat.empty:
        return _candidate_summary(profile_name, pd.DataFrame())

    for column in ["selection_pairwise_rank", "ai_product_pool_rank", "selected_volume"]:
        flat[column] = pd.to_numeric(flat.get(column, 0.0), errors="coerce").fillna(0.0)

    opened = flat[flat["candidate_status"].astype(str).eq("opened")]
    blocked_incremental = flat[flat["skip_reason"].astype(str).eq("incremental_margin_budget_gate")]
    blocked_concurrent = flat[flat["skip_reason"].astype(str).eq("concurrent_limit")]
    blocked_ai = flat[flat["skip_reason"].astype(str).eq("ai_product_pool_blocked")]

    return {
        "profile_name": profile_name,
        "flat_candidate_count": int(len(flat)),
        "opened_flat_entry_count": int(len(opened)),
        "blocked_by_incremental_gate_count": int(len(blocked_incremental)),
        "blocked_by_concurrent_limit_count": int(len(blocked_concurrent)),
        "blocked_by_ai_pool_count": int(len(blocked_ai)),
        "blocked_incremental_median_rank": _safe_float(blocked_incremental["selection_pairwise_rank"].median()),
        "blocked_incremental_min_rank": _safe_float(blocked_incremental["selection_pairwise_rank"].min()),
        "opened_median_rank": _safe_float(opened["selection_pairwise_rank"].median()),
        "opened_median_ai_rank": _safe_float(opened["ai_product_pool_rank"].median()),
        "blocked_incremental_median_ai_rank": _safe_float(blocked_incremental["ai_product_pool_rank"].median()),
        "opened_median_selected_volume": _safe_float(opened["selected_volume"].median()),
        "blocked_incremental_median_selected_volume": _safe_float(blocked_incremental["selected_volume"].median()),
    }


def _run_profile(profile: GateProfile) -> tuple[dict[str, Any], dict[str, Any], pd.DataFrame]:
    print(
        f"[stage125-incremental-margin-gate] run {profile.profile_name}: "
        f"gate_usage_ratio={profile.gate_usage_ratio:.2f}",
        flush=True,
    )
    log_buffer = StringIO()
    try:
        with redirect_stdout(log_buffer), redirect_stderr(log_buffer):
            engine, daily, statistics = run_backtest(
                risk_ratio=BASE_RISK_RATIO,
                strategy_overrides=_build_overrides(profile),
                analysis_start=START_DT,
                analysis_end=END_DT,
                capital=OFFICIAL_STAGE78_CAPITAL,
                save_artifacts=False,
                include_start_year_sweep=False,
            )
    except Exception:
        sys.stderr.write(log_buffer.getvalue())
        raise

    daily_df = daily.copy() if daily is not None else pd.DataFrame()
    if not daily_df.empty:
        daily_df.sort_index(inplace=True)
    positions = build_positions_df(engine)
    daily_risk = _calculate_daily_risk(daily_df, OFFICIAL_STAGE78_CAPITAL)
    daily_margin, _ = _calculate_margin_path(positions, daily_risk, capital=OFFICIAL_STAGE78_CAPITAL)

    strategy = getattr(engine, "strategy", None)
    candidates = pd.DataFrame(getattr(strategy, "entry_candidate_snapshots", []) if strategy else [])
    candidate_row = _candidate_summary(profile.profile_name, candidates)

    max_margin_to_balance = (
        _safe_float(pd.to_numeric(daily_margin["total_margin_to_balance_pct"], errors="coerce").max())
        if not daily_margin.empty
        else 0.0
    )
    max_active_product_count = (
        _safe_float(pd.to_numeric(daily_margin["active_product_count"], errors="coerce").max())
        if not daily_margin.empty
        else 0.0
    )
    margin_days_gt_80pct = (
        int((pd.to_numeric(daily_margin["total_margin_to_balance_pct"], errors="coerce").fillna(0.0) > 80.0).sum())
        if not daily_margin.empty
        else 0
    )
    margin_days_gt_100pct = (
        int((pd.to_numeric(daily_margin["total_margin_to_balance_pct"], errors="coerce").fillna(0.0) > 100.0).sum())
        if not daily_margin.empty
        else 0
    )

    summary_row = {
        "profile_name": profile.profile_name,
        "base_version": OFFICIAL_STAGE78_VERSION,
        "capital": OFFICIAL_STAGE78_CAPITAL,
        "gate_usage_ratio": profile.gate_usage_ratio,
        "end_balance": _safe_float(statistics.get("end_balance")),
        "total_return_pct": _safe_float(statistics.get("total_return")),
        "max_dd_percent": _safe_float(statistics.get("max_ddpercent")),
        "sharpe_ratio": _safe_float(statistics.get("sharpe_ratio")),
        "total_slippage": _safe_float(statistics.get("total_slippage")),
        "total_trade_count": int(_safe_float(statistics.get("total_trade_count"))),
        "win_ratio_pct": _safe_float(statistics.get("win_ratio")),
        "max_margin_to_balance_pct": max_margin_to_balance,
        "margin_days_gt_80pct": margin_days_gt_80pct,
        "margin_days_gt_100pct": margin_days_gt_100pct,
        "max_active_product_count": max_active_product_count,
    }
    summary_row.update(candidate_row)

    blocked = pd.DataFrame()
    if not candidates.empty:
        blocked = candidates[candidates["skip_reason"].astype(str).eq("incremental_margin_budget_gate")].copy()
        if not blocked.empty:
            blocked.insert(0, "profile_name", profile.profile_name)
    return summary_row, candidate_row, blocked


def _reference_row() -> dict[str, Any]:
    reference = OFFICIAL_STAGE78_REFERENCE_METRICS["full_2020_2026"]
    return {
        "profile_name": "official_stage78_reference",
        "base_version": OFFICIAL_STAGE78_VERSION,
        "capital": OFFICIAL_STAGE78_CAPITAL,
        "gate_usage_ratio": 0.0,
        "end_balance": reference["end_balance"],
        "total_return_pct": reference["total_return_pct"],
        "max_dd_percent": reference["max_dd_percent"],
        "sharpe_ratio": reference["sharpe_ratio"],
        "total_slippage": reference["total_slippage"],
        "total_trade_count": int(reference["total_trade_count"]),
        "win_ratio_pct": 42.1053,
        "max_margin_to_balance_pct": 112.1465,
        "margin_days_gt_80pct": 11,
        "margin_days_gt_100pct": 3,
        "max_active_product_count": 8.0,
    }


def _build_report(summary: pd.DataFrame, candidate_summary: pd.DataFrame) -> str:
    return "\n".join(
        [
            "# Stage125 Incremental Margin Budget Gate",
            "",
            "## Boundary",
            "",
            "- Base version: `official_stage78_defensive_v1`.",
            "- Keep product universe, AI pool, pairwise ranking, correlation gate and trade sizing unchanged.",
            "- Only add a configurable sequential margin-budget gate for same-day flat-entry candidates.",
            "- Objective: reduce crowded incremental entries without reducing the size of earlier higher-ranked trades.",
            "",
            "## Full Results",
            "",
            _to_markdown_table(
                summary,
                [
                    "profile_name",
                    "gate_usage_ratio",
                    "end_balance",
                    "total_return_pct",
                    "max_dd_percent",
                    "sharpe_ratio",
                    "total_slippage",
                    "total_trade_count",
                    "win_ratio_pct",
                    "max_margin_to_balance_pct",
                    "margin_days_gt_80pct",
                    "margin_days_gt_100pct",
                    "max_active_product_count",
                    "blocked_by_incremental_gate_count",
                ],
            ),
            "",
            "## Candidate Attribution",
            "",
            _to_markdown_table(
                candidate_summary,
                [
                    "profile_name",
                    "flat_candidate_count",
                    "opened_flat_entry_count",
                    "blocked_by_incremental_gate_count",
                    "blocked_by_concurrent_limit_count",
                    "opened_median_rank",
                    "blocked_incremental_median_rank",
                    "opened_median_ai_rank",
                    "blocked_incremental_median_ai_rank",
                    "opened_median_selected_volume",
                    "blocked_incremental_median_selected_volume",
                ],
            ),
            "",
            "## Judgement",
            "",
            "- This is a structural risk-budget test, not a product/date/rank curve fit.",
            "- A profile is valuable only if it materially reduces margin spikes while preserving most of Stage78's return engine.",
        ]
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary_rows = [_reference_row()]
    candidate_rows: list[dict[str, Any]] = []
    blocked_frames: list[pd.DataFrame] = []

    for profile in PROFILES:
        summary_row, candidate_row, blocked = _run_profile(profile)
        summary_rows.append(summary_row)
        candidate_rows.append(candidate_row)
        if not blocked.empty:
            blocked_frames.append(blocked)

    summary = pd.DataFrame(summary_rows)
    candidate_summary = pd.DataFrame(candidate_rows)
    blocked_all = pd.concat(blocked_frames, ignore_index=True, sort=False) if blocked_frames else pd.DataFrame()

    summary.to_csv(SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")
    candidate_summary.to_csv(CANDIDATE_SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")
    blocked_all.to_csv(BLOCKED_CSV_PATH, index=False, encoding="utf-8-sig")
    payload = {
        "model_tag": MODEL_TAG,
        "base_version": OFFICIAL_STAGE78_VERSION,
        "profiles": [profile.__dict__ for profile in PROFILES],
        "summary": summary.to_dict(orient="records"),
        "candidate_summary": candidate_summary.to_dict(orient="records"),
        "output_paths": {
            "summary": str(SUMMARY_CSV_PATH),
            "candidate_summary": str(CANDIDATE_SUMMARY_CSV_PATH),
            "blocked_candidates": str(BLOCKED_CSV_PATH),
            "report": str(REPORT_PATH),
        },
    }
    SUMMARY_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(_build_report(summary, candidate_summary), encoding="utf-8")

    print(f"[stage125-incremental-margin-gate] summary: {SUMMARY_CSV_PATH}")
    print(f"[stage125-incremental-margin-gate] candidate summary: {CANDIDATE_SUMMARY_CSV_PATH}")
    print(f"[stage125-incremental-margin-gate] blocked candidates: {BLOCKED_CSV_PATH}")
    print(f"[stage125-incremental-margin-gate] report: {REPORT_PATH}")
    print(summary.to_string(index=False))
    print(candidate_summary.to_string(index=False))


if __name__ == "__main__":
    main()
