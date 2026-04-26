from __future__ import annotations

import json
import math
import sys
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any

import pandas as pd

from analyze_qmt_roll_stage105_margin_constraint_surface import _calculate_daily_risk, _calculate_margin_path
from qmt_roll_official_stage78_config import (
    OFFICIAL_STAGE78_CAPITAL,
    OFFICIAL_STAGE78_ROLE,
    OFFICIAL_STAGE78_VERSION,
    build_official_stage78_overrides,
)
from run_qmt_alignment_backtest import build_entry_risk_diagnostics_df, build_positions_df
from run_qmt_roll_backtest import build_summary_row, run_backtest
from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import CYCLE_WINDOWS, to_markdown_table
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage166_rollover_reopen_drawdown_guard_avc_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage166_rollover_reopen_drawdown_guard_avc"

SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COMPARISON_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
ROLLOVER_SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_rollover_summary_{MODEL_TAG}.csv"
DAILY_MARGIN_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_margin_{MODEL_TAG}.csv"
RUN_LOG_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_run_log_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

WINDOW_NAMES: tuple[str, ...] = (
    "full_2020_2026",
    "post_signal_2022_2026",
    "trend_rich_2024_2025",
    "latest_2026",
)

PROFILE_A: str = "A_official_stage78_reference"
PROFILE_C: str = "C_stage78_rollover_reopen_dd10_guard"

ROLLOVER_REOPEN_MAX_DRAWDOWN_PCT: float = 0.10


@dataclass(frozen=True)
class ExperimentArm:
    profile_name: str
    arm: str
    hypothesis: str
    strategy_overrides: dict[str, Any]


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or math.isinf(result):
        return default
    return result


def _target_windows() -> tuple[dict[str, Any], ...]:
    by_name = {str(window["window_name"]): window for window in CYCLE_WINDOWS}
    return tuple(by_name[name] for name in WINDOW_NAMES)


def _build_arms() -> tuple[ExperimentArm, ...]:
    base = build_official_stage78_overrides()
    candidate = dict(base)
    candidate.update(
        {
            "enable_rollover_reopen_drawdown_guard": True,
            "rollover_reopen_max_portfolio_drawdown_pct": ROLLOVER_REOPEN_MAX_DRAWDOWN_PCT,
        }
    )
    return (
        ExperimentArm(
            profile_name=PROFILE_A,
            arm="A",
            hypothesis="第78正式基准，冻结作为比较对象。",
            strategy_overrides=base,
        ),
        ExperimentArm(
            profile_name=PROFILE_C,
            arm="C",
            hypothesis=(
                "第78加换月同向重开回撤护栏；不改入场信号、不改品种池、不缩放普通新仓，"
                "只在组合回撤超过10%时取消换月后的同日机械重开。"
            ),
            strategy_overrides=candidate,
        ),
    )


def _slice_margin(daily_margin: pd.DataFrame, analysis_start: datetime, analysis_end: datetime) -> pd.DataFrame:
    if daily_margin.empty:
        return pd.DataFrame()
    frame = daily_margin.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    start = pd.Timestamp(analysis_start).normalize()
    end = pd.Timestamp(analysis_end).normalize()
    return frame[(frame["date"] >= start) & (frame["date"] <= end)].copy()


def _margin_summary(
    engine: Any,
    daily: pd.DataFrame,
    analysis_start: datetime,
    analysis_end: datetime,
    profile_name: str,
    window_name: str,
) -> tuple[dict[str, Any], pd.DataFrame]:
    daily_df = daily.copy() if daily is not None else pd.DataFrame()
    if not daily_df.empty:
        daily_df.sort_index(inplace=True)
    positions = build_positions_df(engine)
    daily_risk = _calculate_daily_risk(daily_df, OFFICIAL_STAGE78_CAPITAL)
    if daily_risk.empty:
        return {
            "max_margin_to_balance_pct": 0.0,
            "max_margin_date": "",
            "margin_days_gt_60pct": 0,
            "margin_days_gt_80pct": 0,
            "margin_days_gt_100pct": 0,
            "max_active_product_count": 0.0,
        }, pd.DataFrame()

    daily_margin, _ = _calculate_margin_path(positions, daily_risk, capital=OFFICIAL_STAGE78_CAPITAL)
    sliced = _slice_margin(daily_margin, analysis_start, analysis_end)
    if sliced.empty:
        return {
            "max_margin_to_balance_pct": 0.0,
            "max_margin_date": "",
            "margin_days_gt_60pct": 0,
            "margin_days_gt_80pct": 0,
            "margin_days_gt_100pct": 0,
            "max_active_product_count": 0.0,
        }, pd.DataFrame()

    margin = pd.to_numeric(sliced["total_margin_to_balance_pct"], errors="coerce").fillna(0.0)
    max_idx = margin.idxmax()
    sliced.insert(0, "window_name", window_name)
    sliced.insert(0, "profile_name", profile_name)
    return {
        "max_margin_to_balance_pct": _safe_float(margin.max()),
        "max_margin_date": str(sliced.loc[max_idx, "date"])[:10],
        "margin_days_gt_60pct": int((margin > 60.0).sum()),
        "margin_days_gt_80pct": int((margin > 80.0).sum()),
        "margin_days_gt_100pct": int((margin > 100.0).sum()),
        "max_active_product_count": _safe_float(
            pd.to_numeric(sliced.get("active_product_count", 0.0), errors="coerce").max()
        ),
    }, sliced


def _series_or_zero(frame: pd.DataFrame, column: str) -> pd.Series:
    if frame.empty or column not in frame:
        return pd.Series(dtype="float64")
    return pd.to_numeric(frame[column], errors="coerce").fillna(0.0)


def _rollover_summary(engine: Any, arm: ExperimentArm, window_name: str) -> dict[str, Any]:
    strategy = getattr(engine, "strategy", None)
    entry_risk = build_entry_risk_diagnostics_df(engine)
    rollover_entries = pd.DataFrame()
    if not entry_risk.empty and "signal" in entry_risk:
        rollover_entries = entry_risk[entry_risk["signal"].astype(str).eq("rollover_reopen")].copy()

    drawdown = _series_or_zero(rollover_entries, "portfolio_drawdown_pct")
    volume = _series_or_zero(rollover_entries, "volume")
    over_guard = drawdown > ROLLOVER_REOPEN_MAX_DRAWDOWN_PCT

    skipped_rows = getattr(strategy, "rollover_reopen_guard_diagnostics", []) if strategy else []
    skipped = pd.DataFrame(skipped_rows)
    skipped_drawdown = _series_or_zero(skipped, "portfolio_drawdown_pct")

    return {
        "profile_name": arm.profile_name,
        "arm": arm.arm,
        "window_name": window_name,
        "rollover_reopen_open_count": int(len(rollover_entries)),
        "rollover_reopen_open_volume": int(_safe_float(volume.sum())),
        "rollover_reopen_open_count_over_guard": int(over_guard.sum()) if not rollover_entries.empty else 0,
        "rollover_reopen_avg_drawdown_pct": _safe_float(drawdown.mean()) if not drawdown.empty else 0.0,
        "rollover_reopen_skipped_by_guard": int(len(skipped)),
        "rollover_reopen_skip_avg_drawdown_pct": _safe_float(skipped_drawdown.mean()) if not skipped_drawdown.empty else 0.0,
        "rollover_reopen_guard_threshold_pct": ROLLOVER_REOPEN_MAX_DRAWDOWN_PCT,
    }


def _run_one(
    arm: ExperimentArm,
    window: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], pd.DataFrame, pd.DataFrame]:
    window_name = str(window["window_name"])
    analysis_start: datetime = window["analysis_start"]
    analysis_end: datetime = window["analysis_end"]
    print(
        f"[stage166-rollover-reopen-dd-guard] {window_name} / {arm.profile_name}: "
        f"{analysis_start.date()} -> {analysis_end.date()}",
        flush=True,
    )

    log_buffer = StringIO()
    try:
        with redirect_stdout(log_buffer), redirect_stderr(log_buffer):
            engine, daily, statistics = run_backtest(
                risk_ratio=BASE_RISK_RATIO,
                strategy_overrides=arm.strategy_overrides,
                analysis_start=analysis_start,
                analysis_end=analysis_end,
                capital=OFFICIAL_STAGE78_CAPITAL,
                save_artifacts=False,
                include_start_year_sweep=False,
            )
    except Exception:
        sys.stderr.write(log_buffer.getvalue())
        raise

    margin_row, daily_margin = _margin_summary(
        engine,
        daily,
        analysis_start,
        analysis_end,
        arm.profile_name,
        window_name,
    )
    row = build_summary_row(
        statistics,
        analysis_start=analysis_start,
        analysis_end=analysis_end,
        model_tag=MODEL_TAG,
        arm=arm.arm,
        profile_name=arm.profile_name,
        hypothesis=arm.hypothesis,
        base_version=OFFICIAL_STAGE78_VERSION,
        official_role=OFFICIAL_STAGE78_ROLE,
        window_name=window_name,
        display_label=str(window["display_label"]),
        capital=OFFICIAL_STAGE78_CAPITAL,
        total_net_pnl=float(statistics.get("total_net_pnl", 0) or 0),
        total_slippage=float(statistics.get("total_slippage", 0) or 0),
        total_commission=float(statistics.get("total_commission", 0) or 0),
        profit_days=int(statistics.get("profit_days", 0) or 0),
        loss_days=int(statistics.get("loss_days", 0) or 0),
        strategy_overrides_json=json.dumps(arm.strategy_overrides, ensure_ascii=False, sort_keys=True),
        **margin_row,
    )
    rollover_row = _rollover_summary(engine, arm, window_name)
    run_log = pd.DataFrame(
        {
            "profile_name": [arm.profile_name],
            "window_name": [window_name],
            "log_line": ["\n".join(log_buffer.getvalue().splitlines()[-40:])],
        }
    )
    return row, rollover_row, daily_margin, run_log


def _build_comparison(summary: pd.DataFrame) -> pd.DataFrame:
    reference = summary[summary["profile_name"].astype(str).eq(PROFILE_A)].copy()
    candidate = summary[summary["profile_name"].astype(str).eq(PROFILE_C)].copy()
    if reference.empty or candidate.empty:
        return pd.DataFrame()

    compare_columns = [
        "window_name",
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
    ]
    merged = candidate.merge(
        reference[compare_columns],
        on="window_name",
        how="left",
        suffixes=("_c", "_a"),
    )
    for column in compare_columns[1:]:
        merged[f"{column}_diff"] = (
            pd.to_numeric(merged[f"{column}_c"], errors="coerce")
            - pd.to_numeric(merged[f"{column}_a"], errors="coerce")
        )
    return merged


def _experiment_decision(comparison: pd.DataFrame, rollover_summary: pd.DataFrame) -> str:
    if comparison.empty:
        return "fail_missing_comparison"
    full_rows = comparison[comparison["window_name"].astype(str).eq("full_2020_2026")]
    latest_rows = comparison[comparison["window_name"].astype(str).eq("latest_2026")]
    if full_rows.empty:
        return "fail_missing_full_window"

    full = full_rows.iloc[0]
    latest = latest_rows.iloc[0] if not latest_rows.empty else None
    c_rollover_full = rollover_summary[
        (rollover_summary["profile_name"].astype(str).eq(PROFILE_C))
        & (rollover_summary["window_name"].astype(str).eq("full_2020_2026"))
    ]
    skipped_count = int(_safe_float(c_rollover_full["rollover_reopen_skipped_by_guard"].sum()))
    if skipped_count <= 0:
        return "fail_no_material_deployment"

    full_return_diff = _safe_float(full.get("total_return_pct_diff"))
    full_dd_diff = _safe_float(full.get("max_dd_percent_diff"))
    full_sharpe_diff = _safe_float(full.get("sharpe_ratio_diff"))
    full_trade_count_diff = _safe_float(full.get("total_trade_count_diff"))
    full_slippage_diff = _safe_float(full.get("total_slippage_diff"))

    if full_return_diff < -250.0 or full_sharpe_diff < -0.08:
        return "fail_return_quality_damage"
    if full_trade_count_diff > 0 and full_slippage_diff > 0:
        return "fail_cost_pressure_increased"

    non_latest = comparison[~comparison["window_name"].astype(str).eq("latest_2026")].copy()
    window_damage = non_latest[
        (pd.to_numeric(non_latest["total_return_pct_diff"], errors="coerce") < -150.0)
        & (pd.to_numeric(non_latest["max_dd_percent_diff"], errors="coerce") < -2.0)
    ]
    if not window_damage.empty:
        return "fail_intermediate_window_path_damage"

    if full_dd_diff < 1.0 and full_sharpe_diff < 0.03:
        return "fail_no_material_curve_quality_improvement"
    if latest is not None and (
        _safe_float(latest.get("total_return_pct_diff")) < -10.0
        or _safe_float(latest.get("max_dd_percent_diff")) < -3.0
    ):
        return "fail_latest_window_damage"
    return "candidate_needs_start_year_and_quarterly_walkforward"


def _build_report(
    summary: pd.DataFrame,
    comparison: pd.DataFrame,
    rollover_summary: pd.DataFrame,
    decision: str,
) -> str:
    result_columns = [
        "profile_name",
        "window_name",
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
    ]
    comparison_columns = [
        "profile_name",
        "window_name",
        "end_balance_diff",
        "total_return_pct_diff",
        "max_dd_percent_diff",
        "sharpe_ratio_diff",
        "total_slippage_diff",
        "total_trade_count_diff",
        "max_margin_to_balance_pct_diff",
        "margin_days_gt_80pct_diff",
        "margin_days_gt_100pct_diff",
    ]
    rollover_columns = [
        "profile_name",
        "window_name",
        "rollover_reopen_open_count",
        "rollover_reopen_open_volume",
        "rollover_reopen_open_count_over_guard",
        "rollover_reopen_avg_drawdown_pct",
        "rollover_reopen_skipped_by_guard",
        "rollover_reopen_skip_avg_drawdown_pct",
    ]
    return "\n".join(
        [
            "# Stage166 Rollover Reopen Drawdown Guard A Vs C",
            "",
            "## Boundary",
            "",
            f"- A = `{PROFILE_A}`.",
            f"- C = `{PROFILE_C}`.",
            "- B is not meaningful because this is a narrow execution-continuity guard.",
            "- No product blacklist, no date patch, no signal change, and no threshold sweep is used.",
            "",
            "## Predeclared Candidate",
            "",
            f"- Guard threshold: `{ROLLOVER_REOPEN_MAX_DRAWDOWN_PCT:.2%}` portfolio drawdown.",
            "- Only same-day rollover reopen is blocked; normal flat-entry logic can compete again on later bars.",
            "",
            "## Results",
            "",
            to_markdown_table(summary[result_columns]),
            "",
            "## A Vs C",
            "",
            to_markdown_table(comparison[comparison_columns]) if not comparison.empty else "_empty_",
            "",
            "## Rollover Deployment",
            "",
            to_markdown_table(rollover_summary[rollover_columns]) if not rollover_summary.empty else "_empty_",
            "",
            "## Decision",
            "",
            f"- `{decision}`",
        ]
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    windows = _target_windows()
    arms = _build_arms()

    summary_rows: list[dict[str, Any]] = []
    rollover_rows: list[dict[str, Any]] = []
    margin_frames: list[pd.DataFrame] = []
    run_log_frames: list[pd.DataFrame] = []

    for window in windows:
        for arm in arms:
            row, rollover_row, daily_margin, run_log = _run_one(arm, window)
            summary_rows.append(row)
            rollover_rows.append(rollover_row)
            if not daily_margin.empty:
                margin_frames.append(daily_margin)
            run_log_frames.append(run_log)

    summary = pd.DataFrame(summary_rows).sort_values(["analysis_start", "profile_name"]).reset_index(drop=True)
    comparison = _build_comparison(summary)
    rollover_summary = pd.DataFrame(rollover_rows).sort_values(["window_name", "profile_name"]).reset_index(drop=True)
    daily_margin_all = pd.concat(margin_frames, ignore_index=True, sort=False) if margin_frames else pd.DataFrame()
    run_log_all = pd.concat(run_log_frames, ignore_index=True, sort=False) if run_log_frames else pd.DataFrame()
    decision = _experiment_decision(comparison, rollover_summary)

    summary.to_csv(SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_CSV_PATH, index=False, encoding="utf-8-sig")
    rollover_summary.to_csv(ROLLOVER_SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")
    daily_margin_all.to_csv(DAILY_MARGIN_CSV_PATH, index=False, encoding="utf-8-sig")
    run_log_all.to_csv(RUN_LOG_CSV_PATH, index=False, encoding="utf-8-sig")
    REPORT_PATH.write_text(_build_report(summary, comparison, rollover_summary, decision), encoding="utf-8")
    SUMMARY_JSON_PATH.write_text(
        json.dumps(
            {
                "model_tag": MODEL_TAG,
                "base_version": OFFICIAL_STAGE78_VERSION,
                "official_role": OFFICIAL_STAGE78_ROLE,
                "capital": OFFICIAL_STAGE78_CAPITAL,
                "base_risk_ratio": BASE_RISK_RATIO,
                "decision": decision,
                "rollover_reopen_drawdown_guard": {
                    "max_portfolio_drawdown_pct": ROLLOVER_REOPEN_MAX_DRAWDOWN_PCT,
                },
                "windows": [
                    {
                        "window_name": str(window["window_name"]),
                        "analysis_start": window["analysis_start"].date().isoformat(),
                        "analysis_end": window["analysis_end"].date().isoformat(),
                    }
                    for window in windows
                ],
                "arms": [
                    {
                        "profile_name": arm.profile_name,
                        "arm": arm.arm,
                        "hypothesis": arm.hypothesis,
                        "strategy_overrides": arm.strategy_overrides,
                    }
                    for arm in arms
                ],
                "summary": summary.to_dict(orient="records"),
                "comparison": comparison.to_dict(orient="records"),
                "rollover_summary": rollover_summary.to_dict(orient="records"),
                "output_paths": {
                    "summary": str(SUMMARY_CSV_PATH),
                    "comparison": str(COMPARISON_CSV_PATH),
                    "rollover_summary": str(ROLLOVER_SUMMARY_CSV_PATH),
                    "daily_margin": str(DAILY_MARGIN_CSV_PATH),
                    "run_log": str(RUN_LOG_CSV_PATH),
                    "report": str(REPORT_PATH),
                },
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    print(f"[stage166-rollover-reopen-dd-guard] summary: {SUMMARY_CSV_PATH}")
    print(f"[stage166-rollover-reopen-dd-guard] comparison: {COMPARISON_CSV_PATH}")
    print(f"[stage166-rollover-reopen-dd-guard] rollover summary: {ROLLOVER_SUMMARY_CSV_PATH}")
    print(f"[stage166-rollover-reopen-dd-guard] report: {REPORT_PATH}")
    print(f"[stage166-rollover-reopen-dd-guard] decision: {decision}")
    print(comparison.to_string(index=False))
    print(rollover_summary.to_string(index=False))


if __name__ == "__main__":
    main()
