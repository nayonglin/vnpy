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

MODEL_TAG: str = "stage126_peak_margin_guard_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage126_peak_margin_guard"

SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CANDIDATE_SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_candidate_summary_{MODEL_TAG}.csv"
BLOCKED_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_blocked_candidates_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


@dataclass(frozen=True)
class PeakGuardProfile:
    profile_name: str
    gate_usage_ratio: float
    min_openable_candidates: int = 2
    protected_selection_rank: int = 1


PROFILES: tuple[PeakGuardProfile, ...] = (
    PeakGuardProfile("stage78_peak_guard90_rank1", 0.90),
    PeakGuardProfile("stage78_peak_guard80_rank1", 0.80),
)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or math.isinf(result):
        return default
    return result


def _build_overrides(profile: PeakGuardProfile) -> dict[str, Any]:
    overrides = build_official_stage78_overrides()
    overrides.update(
        {
            "enable_incremental_margin_budget_gate": True,
            "incremental_margin_budget_gate_usage_ratio": profile.gate_usage_ratio,
            "incremental_margin_budget_gate_min_openable_candidates": profile.min_openable_candidates,
            "incremental_margin_budget_gate_protected_selection_rank": profile.protected_selection_rank,
        }
    )
    return overrides


def _candidate_summary(profile_name: str, candidates: pd.DataFrame) -> dict[str, Any]:
    base = {
        "profile_name": profile_name,
        "flat_candidate_count": 0,
        "opened_flat_entry_count": 0,
        "blocked_by_incremental_gate_count": 0,
        "blocked_by_concurrent_limit_count": 0,
        "blocked_by_ai_pool_count": 0,
        "protected_by_rank_count": 0,
        "protected_over_budget_count": 0,
        "blocked_incremental_median_rank": 0.0,
        "blocked_incremental_min_rank": 0.0,
        "opened_median_rank": 0.0,
        "opened_median_ai_rank": 0.0,
        "blocked_incremental_median_ai_rank": 0.0,
        "opened_median_selected_volume": 0.0,
        "blocked_incremental_median_selected_volume": 0.0,
    }
    if candidates.empty:
        return base

    flat = candidates[candidates["entry_context"].astype(str).eq("flat_entry")].copy()
    if flat.empty:
        return base

    for column in [
        "selection_pairwise_rank",
        "ai_product_pool_rank",
        "selected_volume",
        "incremental_margin_budget_gate_protected_by_rank",
        "incremental_margin_budget_gate_projected_margin_after",
        "incremental_margin_budget_gate_budget",
    ]:
        flat[column] = pd.to_numeric(flat.get(column, 0.0), errors="coerce").fillna(0.0)

    opened = flat[flat["candidate_status"].astype(str).eq("opened")]
    blocked_incremental = flat[flat["skip_reason"].astype(str).eq("incremental_margin_budget_gate")]
    blocked_concurrent = flat[flat["skip_reason"].astype(str).eq("concurrent_limit")]
    blocked_ai = flat[flat["skip_reason"].astype(str).eq("ai_product_pool_blocked")]
    protected = flat[flat["incremental_margin_budget_gate_protected_by_rank"] > 0]
    protected_over_budget = protected[
        protected["incremental_margin_budget_gate_projected_margin_after"]
        > protected["incremental_margin_budget_gate_budget"]
    ]

    base.update(
        {
            "flat_candidate_count": int(len(flat)),
            "opened_flat_entry_count": int(len(opened)),
            "blocked_by_incremental_gate_count": int(len(blocked_incremental)),
            "blocked_by_concurrent_limit_count": int(len(blocked_concurrent)),
            "blocked_by_ai_pool_count": int(len(blocked_ai)),
            "protected_by_rank_count": int(len(protected)),
            "protected_over_budget_count": int(len(protected_over_budget)),
            "blocked_incremental_median_rank": _safe_float(blocked_incremental["selection_pairwise_rank"].median()),
            "blocked_incremental_min_rank": _safe_float(blocked_incremental["selection_pairwise_rank"].min()),
            "opened_median_rank": _safe_float(opened["selection_pairwise_rank"].median()),
            "opened_median_ai_rank": _safe_float(opened["ai_product_pool_rank"].median()),
            "blocked_incremental_median_ai_rank": _safe_float(blocked_incremental["ai_product_pool_rank"].median()),
            "opened_median_selected_volume": _safe_float(opened["selected_volume"].median()),
            "blocked_incremental_median_selected_volume": _safe_float(blocked_incremental["selected_volume"].median()),
        }
    )
    return base


def _run_profile(profile: PeakGuardProfile) -> tuple[dict[str, Any], dict[str, Any], pd.DataFrame]:
    print(
        f"[stage126-peak-margin-guard] run {profile.profile_name}: "
        f"gate={profile.gate_usage_ratio:.2f}, "
        f"min_candidates={profile.min_openable_candidates}, "
        f"protected_rank={profile.protected_selection_rank}",
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

    margin_series = (
        pd.to_numeric(daily_margin["total_margin_to_balance_pct"], errors="coerce").fillna(0.0)
        if not daily_margin.empty
        else pd.Series(dtype="float64")
    )
    active_series = (
        pd.to_numeric(daily_margin["active_product_count"], errors="coerce").fillna(0.0)
        if not daily_margin.empty
        else pd.Series(dtype="float64")
    )

    summary_row = {
        "profile_name": profile.profile_name,
        "base_version": OFFICIAL_STAGE78_VERSION,
        "capital": OFFICIAL_STAGE78_CAPITAL,
        "gate_usage_ratio": profile.gate_usage_ratio,
        "min_openable_candidates": profile.min_openable_candidates,
        "protected_selection_rank": profile.protected_selection_rank,
        "end_balance": _safe_float(statistics.get("end_balance")),
        "total_return_pct": _safe_float(statistics.get("total_return")),
        "max_dd_percent": _safe_float(statistics.get("max_ddpercent")),
        "sharpe_ratio": _safe_float(statistics.get("sharpe_ratio")),
        "total_slippage": _safe_float(statistics.get("total_slippage")),
        "total_trade_count": int(_safe_float(statistics.get("total_trade_count"))),
        "win_ratio_pct": _safe_float(statistics.get("win_ratio")),
        "max_margin_to_balance_pct": _safe_float(margin_series.max()),
        "margin_days_gt_80pct": int((margin_series > 80.0).sum()),
        "margin_days_gt_100pct": int((margin_series > 100.0).sum()),
        "max_active_product_count": _safe_float(active_series.max()),
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
        "min_openable_candidates": 0,
        "protected_selection_rank": 0,
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
            "# Stage126 Peak Margin Guard",
            "",
            "## Boundary",
            "",
            "- Base version: `official_stage78_defensive_v1`.",
            "- Keep Stage78 universe, AI pool, ranking, sizing and exits unchanged.",
            "- Only change the Stage125 incremental budget gate into a peak guard: require crowded same-day candidates and protect rank-1 candidates.",
            "",
            "## Full Results",
            "",
            _to_markdown_table(
                summary,
                [
                    "profile_name",
                    "gate_usage_ratio",
                    "min_openable_candidates",
                    "protected_selection_rank",
                    "end_balance",
                    "total_return_pct",
                    "max_dd_percent",
                    "sharpe_ratio",
                    "total_trade_count",
                    "win_ratio_pct",
                    "max_margin_to_balance_pct",
                    "margin_days_gt_80pct",
                    "margin_days_gt_100pct",
                    "blocked_by_incremental_gate_count",
                    "protected_over_budget_count",
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
                    "protected_by_rank_count",
                    "protected_over_budget_count",
                    "opened_median_rank",
                    "blocked_incremental_median_rank",
                    "opened_median_ai_rank",
                    "blocked_incremental_median_ai_rank",
                ],
            ),
            "",
            "## Judgement",
            "",
            "- This branch is valuable only if rank-1 protection keeps return close to Stage78 while still removing margin spikes.",
            "- If the result is still worse than Stage78 or Stage125 gate90, the direction should stop rather than tune thresholds.",
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

    print(f"[stage126-peak-margin-guard] summary: {SUMMARY_CSV_PATH}")
    print(f"[stage126-peak-margin-guard] candidate summary: {CANDIDATE_SUMMARY_CSV_PATH}")
    print(f"[stage126-peak-margin-guard] blocked candidates: {BLOCKED_CSV_PATH}")
    print(f"[stage126-peak-margin-guard] report: {REPORT_PATH}")
    print(summary.to_string(index=False))
    print(candidate_summary.to_string(index=False))


if __name__ == "__main__":
    main()
