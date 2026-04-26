from __future__ import annotations

import argparse
import json
import math
import sys
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import asdict, dataclass
from io import StringIO
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from analyze_qmt_roll_stage105_margin_constraint_surface import _calculate_daily_risk, _calculate_margin_path
from qmt_roll_official_stage78_config import (
    OFFICIAL_STAGE78_CAPITAL,
    OFFICIAL_STAGE78_REFERENCE_METRICS,
    OFFICIAL_STAGE78_ROLE,
    OFFICIAL_STAGE78_VERSION,
    build_official_stage78_overrides,
)
from qmt_universe import END_DT, START_DT
from run_qmt_alignment_backtest import build_positions_df
from run_qmt_roll_backtest import build_summary_row, run_backtest
from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import (
    CYCLE_WINDOWS,
    to_markdown_table,
)
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage158_dynamic_sizing_soft_cap_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage158_dynamic_sizing_soft_cap"

SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COMPARISON_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
CANDIDATE_SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_candidate_summary_{MODEL_TAG}.csv"
CANDIDATE_SNAPSHOTS_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_candidate_snapshots_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CACHED_MULTICYCLE_REFERENCE_PATH: Path = (
    OUTPUT_DIR / "qmt_roll_official_stage78_sizing_cap_multicycle_summary_stage78_sizing_cap_multicycle_v1.csv"
)

DEFAULT_WINDOW_NAMES: tuple[str, ...] = ("full_2020_2026", "latest_2026")
REFERENCE_WIN_RATIO_BY_WINDOW: dict[str, float] = {
    "full_2020_2026": 42.1053,
}


@dataclass(frozen=True)
class DynamicSoftCapProfile:
    profile_name: str
    base_cap: float = 1_000_000.0
    max_cap: float = 1_500_000.0
    participation: float = 0.25
    margin_start_ratio: float = 0.60
    margin_full_ratio: float = 0.80
    drawdown_start_ratio: float = 0.05
    drawdown_full_ratio: float = 0.20


PROFILE: DynamicSoftCapProfile = DynamicSoftCapProfile(
    profile_name="stage78_dynamic_soft_cap_1m_to_1_5m_guarded",
)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or math.isinf(result):
        return default
    return result


def _target_windows(run_cycles: bool) -> tuple[dict[str, Any], ...]:
    if run_cycles:
        return CYCLE_WINDOWS
    by_name = {str(window["window_name"]): window for window in CYCLE_WINDOWS}
    return tuple(by_name[name] for name in DEFAULT_WINDOW_NAMES)


def _profile_overrides(profile: DynamicSoftCapProfile) -> dict[str, Any]:
    overrides = build_official_stage78_overrides()
    overrides.update(
        {
            "sizing_equity_cap": profile.base_cap,
            "enable_dynamic_sizing_equity_soft_cap": True,
            "dynamic_sizing_equity_soft_cap_base": profile.base_cap,
            "dynamic_sizing_equity_soft_cap_max": profile.max_cap,
            "dynamic_sizing_equity_soft_cap_participation": profile.participation,
            "dynamic_sizing_equity_soft_cap_margin_start_ratio": profile.margin_start_ratio,
            "dynamic_sizing_equity_soft_cap_margin_full_ratio": profile.margin_full_ratio,
            "dynamic_sizing_equity_soft_cap_drawdown_start_ratio": profile.drawdown_start_ratio,
            "dynamic_sizing_equity_soft_cap_drawdown_full_ratio": profile.drawdown_full_ratio,
        }
    )
    return overrides


def _load_cached_reference_by_window() -> dict[str, dict[str, Any]]:
    if not CACHED_MULTICYCLE_REFERENCE_PATH.exists():
        return {}

    reference = pd.read_csv(CACHED_MULTICYCLE_REFERENCE_PATH)
    reference = reference[reference["profile_name"].astype(str).eq("stage78_capped_1m")].copy()
    rows: dict[str, dict[str, Any]] = {}
    for row in reference.to_dict(orient="records"):
        rows[str(row.get("window_name"))] = row
    return rows


def _reference_row(window: dict[str, Any], cached_reference: dict[str, dict[str, Any]]) -> dict[str, Any]:
    window_name = str(window["window_name"])
    metrics = dict(cached_reference.get(window_name, {}))
    frozen_metrics = OFFICIAL_STAGE78_REFERENCE_METRICS.get(window_name, {})
    if not metrics and frozen_metrics:
        metrics = {
            "end_balance": frozen_metrics.get("end_balance"),
            "total_return_pct": frozen_metrics.get("total_return_pct"),
            "max_dd_percent": frozen_metrics.get("max_dd_percent"),
            "sharpe_ratio": frozen_metrics.get("sharpe_ratio"),
            "total_slippage": frozen_metrics.get("total_slippage"),
            "total_trade_count": frozen_metrics.get("total_trade_count"),
            "win_ratio_pct": REFERENCE_WIN_RATIO_BY_WINDOW.get(window_name, np.nan),
        }
    return {
        "profile_name": "A_official_stage78_reference",
        "model_tag": "official_reference",
        "base_version": OFFICIAL_STAGE78_VERSION,
        "official_role": OFFICIAL_STAGE78_ROLE,
        "window_name": window_name,
        "display_label": str(window["display_label"]),
        "analysis_start": window["analysis_start"].date().isoformat(),
        "analysis_end": window["analysis_end"].date().isoformat(),
        "capital": OFFICIAL_STAGE78_CAPITAL,
        "end_balance": _safe_float(metrics.get("end_balance")),
        "total_return_pct": _safe_float(metrics.get("total_return_pct")),
        "max_dd_percent": _safe_float(metrics.get("max_dd_percent")),
        "sharpe_ratio": _safe_float(metrics.get("sharpe_ratio")),
        "total_slippage": _safe_float(metrics.get("total_slippage")),
        "total_trade_count": int(_safe_float(metrics.get("total_trade_count"))),
        "win_ratio_pct": _safe_float(
            metrics.get("win_ratio_pct"),
            REFERENCE_WIN_RATIO_BY_WINDOW.get(window_name, np.nan),
        ),
        "max_margin_to_balance_pct": np.nan,
        "margin_days_gt_80pct": np.nan,
        "margin_days_gt_100pct": np.nan,
        "strategy_overrides_json": str(metrics.get("strategy_overrides_json", "")),
        "annual_return_pct": _safe_float(metrics.get("annual_return_pct"), np.nan),
        "max_drawdown": _safe_float(metrics.get("max_drawdown"), np.nan),
        "max_drawdown_duration": _safe_float(metrics.get("max_drawdown_duration"), np.nan),
        "return_drawdown_ratio": _safe_float(metrics.get("return_drawdown_ratio"), np.nan),
        "daily_trade_count": _safe_float(metrics.get("daily_trade_count"), np.nan),
        "total_net_pnl": _safe_float(metrics.get("total_net_pnl"), np.nan),
        "total_commission": _safe_float(metrics.get("total_commission"), np.nan),
        "profit_days": _safe_float(metrics.get("profit_days"), np.nan),
        "loss_days": _safe_float(metrics.get("loss_days"), np.nan),
    }


def _candidate_snapshot_summary(profile_name: str, window_name: str, candidates: pd.DataFrame) -> dict[str, Any]:
    row: dict[str, Any] = {
        "profile_name": profile_name,
        "window_name": window_name,
        "flat_candidate_count": 0,
        "opened_flat_entry_count": 0,
        "expanded_cap_candidate_count": 0,
        "expanded_cap_opened_count": 0,
        "max_effective_sizing_equity_cap": 0.0,
        "median_effective_sizing_equity_cap": 0.0,
        "median_release_weight": 0.0,
        "median_margin_pressure_ratio": 0.0,
        "median_drawdown_ratio": 0.0,
    }
    if candidates.empty:
        return row

    flat = candidates[candidates["entry_context"].astype(str).eq("flat_entry")].copy()
    if flat.empty:
        return row

    numeric_columns = [
        "effective_sizing_equity_cap",
        "dynamic_sizing_equity_soft_cap_base",
        "dynamic_sizing_equity_soft_cap_release_weight",
        "dynamic_sizing_equity_soft_cap_margin_pressure_ratio",
        "dynamic_sizing_equity_soft_cap_drawdown_ratio",
    ]
    for column in numeric_columns:
        flat[column] = pd.to_numeric(flat.get(column, 0.0), errors="coerce").fillna(0.0)

    opened = flat[flat["candidate_status"].astype(str).eq("opened")]
    expanded = flat["effective_sizing_equity_cap"] > flat["dynamic_sizing_equity_soft_cap_base"] + 1e-9
    row.update(
        {
            "flat_candidate_count": int(len(flat)),
            "opened_flat_entry_count": int(len(opened)),
            "expanded_cap_candidate_count": int(expanded.sum()),
            "expanded_cap_opened_count": int(expanded.loc[opened.index].sum()) if not opened.empty else 0,
            "max_effective_sizing_equity_cap": _safe_float(flat["effective_sizing_equity_cap"].max()),
            "median_effective_sizing_equity_cap": _safe_float(flat["effective_sizing_equity_cap"].median()),
            "median_release_weight": _safe_float(flat["dynamic_sizing_equity_soft_cap_release_weight"].median()),
            "median_margin_pressure_ratio": _safe_float(
                flat["dynamic_sizing_equity_soft_cap_margin_pressure_ratio"].median()
            ),
            "median_drawdown_ratio": _safe_float(flat["dynamic_sizing_equity_soft_cap_drawdown_ratio"].median()),
        }
    )
    return row


def _margin_summary(engine: Any, daily: pd.DataFrame, analysis_start: Any, analysis_end: Any) -> dict[str, Any]:
    if daily is None or daily.empty:
        return {
            "max_margin_to_balance_pct": 0.0,
            "margin_days_gt_80pct": 0,
            "margin_days_gt_100pct": 0,
        }

    daily_df = daily.copy()
    daily_df.sort_index(inplace=True)
    positions = build_positions_df(engine)
    daily_risk = _calculate_daily_risk(daily_df, OFFICIAL_STAGE78_CAPITAL)
    daily_margin, _ = _calculate_margin_path(positions, daily_risk, capital=OFFICIAL_STAGE78_CAPITAL)
    if daily_margin.empty:
        return {
            "max_margin_to_balance_pct": 0.0,
            "margin_days_gt_80pct": 0,
            "margin_days_gt_100pct": 0,
        }

    daily_margin["date"] = pd.to_datetime(daily_margin["date"], errors="coerce").dt.normalize()
    start = pd.Timestamp(analysis_start).normalize()
    end = pd.Timestamp(analysis_end).normalize()
    sliced = daily_margin[(daily_margin["date"] >= start) & (daily_margin["date"] <= end)].copy()
    margin = pd.to_numeric(sliced.get("total_margin_to_balance_pct", 0.0), errors="coerce").fillna(0.0)
    return {
        "max_margin_to_balance_pct": _safe_float(margin.max()),
        "margin_days_gt_80pct": int((margin > 80.0).sum()),
        "margin_days_gt_100pct": int((margin > 100.0).sum()),
    }


def _run_candidate(profile: DynamicSoftCapProfile, window: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], pd.DataFrame]:
    window_name = str(window["window_name"])
    analysis_start = window["analysis_start"]
    analysis_end = window["analysis_end"]
    overrides = _profile_overrides(profile)
    print(
        f"[stage158-dynamic-soft-cap] {window_name} / {profile.profile_name}: "
        f"{analysis_start.date()} -> {analysis_end.date()}"
    )
    log_buffer = StringIO()
    try:
        with redirect_stdout(log_buffer), redirect_stderr(log_buffer):
            engine, daily, statistics = run_backtest(
                risk_ratio=BASE_RISK_RATIO,
                strategy_overrides=overrides,
                analysis_start=analysis_start,
                analysis_end=analysis_end,
                capital=OFFICIAL_STAGE78_CAPITAL,
                save_artifacts=False,
                include_start_year_sweep=False,
            )
    except Exception:
        sys.stderr.write(log_buffer.getvalue())
        raise

    strategy = getattr(engine, "strategy", None)
    candidates = pd.DataFrame(getattr(strategy, "entry_candidate_snapshots", []) if strategy else [])
    if not candidates.empty:
        candidates.insert(0, "window_name", window_name)
        candidates.insert(0, "profile_name", profile.profile_name)

    margin = _margin_summary(engine, daily, analysis_start, analysis_end)
    summary_row = build_summary_row(
        statistics,
        analysis_start=analysis_start,
        analysis_end=analysis_end,
        profile_name=f"C_{profile.profile_name}",
        model_tag=MODEL_TAG,
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
        strategy_overrides_json=json.dumps(overrides, ensure_ascii=False, sort_keys=True),
        **margin,
    )
    candidate_summary = _candidate_snapshot_summary(profile.profile_name, window_name, candidates)
    return summary_row, candidate_summary, candidates


def _run_reference_backtest(window: dict[str, Any]) -> dict[str, Any]:
    window_name = str(window["window_name"])
    analysis_start = window["analysis_start"]
    analysis_end = window["analysis_end"]
    overrides = build_official_stage78_overrides()
    print(
        f"[stage158-dynamic-soft-cap] reference {window_name}: "
        f"{analysis_start.date()} -> {analysis_end.date()}"
    )
    log_buffer = StringIO()
    try:
        with redirect_stdout(log_buffer), redirect_stderr(log_buffer):
            engine, daily, statistics = run_backtest(
                risk_ratio=BASE_RISK_RATIO,
                strategy_overrides=overrides,
                analysis_start=analysis_start,
                analysis_end=analysis_end,
                capital=OFFICIAL_STAGE78_CAPITAL,
                save_artifacts=False,
                include_start_year_sweep=False,
            )
    except Exception:
        sys.stderr.write(log_buffer.getvalue())
        raise

    margin = _margin_summary(engine, daily, analysis_start, analysis_end)
    return build_summary_row(
        statistics,
        analysis_start=analysis_start,
        analysis_end=analysis_end,
        profile_name="A_official_stage78_reference",
        model_tag=f"{MODEL_TAG}_reference_backtest",
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
        strategy_overrides_json=json.dumps(overrides, ensure_ascii=False, sort_keys=True),
        **margin,
    )


def _build_comparison(summary: pd.DataFrame) -> pd.DataFrame:
    reference = summary[summary["profile_name"].astype(str).eq("A_official_stage78_reference")].copy()
    candidate = summary[summary["profile_name"].astype(str).str.startswith("C_")].copy()
    if reference.empty or candidate.empty:
        return pd.DataFrame()

    columns = [
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
    merged = reference[columns].merge(candidate[columns], on="window_name", suffixes=("_a", "_c"), how="inner")
    for column in columns[1:]:
        merged[f"{column}_diff"] = (
            pd.to_numeric(merged[f"{column}_c"], errors="coerce")
            - pd.to_numeric(merged[f"{column}_a"], errors="coerce")
        )
    return merged


def _build_report(summary: pd.DataFrame, comparison: pd.DataFrame, candidate_summary: pd.DataFrame) -> str:
    return "\n".join(
        [
            "# Stage158 Dynamic Sizing Soft Cap",
            "",
            "## Boundary",
            "",
            "- A = `official_stage78_defensive_v1` frozen reference.",
            "- C = Stage78 plus default-off dynamic sizing-equity soft cap.",
            "- This test does not change product universe, AI pool, entry/exit logic, correlation gate or streak rule.",
            "- The cap can only expand above the old 1,000,000 base when equity is high, margin pressure is low and drawdown is shallow.",
            "",
            "## Predeclared Profile",
            "",
            f"- Profile: `{PROFILE.profile_name}`",
            f"- Base cap: `{PROFILE.base_cap:,.0f}`",
            f"- Max cap: `{PROFILE.max_cap:,.0f}`",
            f"- Equity participation above base: `{PROFILE.participation:.2f}`",
            f"- Margin release band: `{PROFILE.margin_start_ratio:.2f}` to `{PROFILE.margin_full_ratio:.2f}`",
            f"- Drawdown release band: `{PROFILE.drawdown_start_ratio:.2f}` to `{PROFILE.drawdown_full_ratio:.2f}`",
            "",
            "## Results",
            "",
            to_markdown_table(
                summary[
                    [
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
                ]
            ),
            "",
            "## A Vs C",
            "",
            to_markdown_table(comparison) if not comparison.empty else "_empty_",
            "",
            "## Cap Diagnostics",
            "",
            to_markdown_table(candidate_summary),
            "",
            "## Judgment Rule",
            "",
            "- C is not promotable unless it improves or preserves Stage78 full-period path while not worsening latest-window risk.",
            "- If full-period gains come with materially worse drawdown, margin days above 80%, or latest-window degradation, this branch stops.",
        ]
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Stage158 dynamic sizing soft-cap A vs C test.")
    parser.add_argument("--cycles", action="store_true", help="Run all formal cycle windows instead of full/latest only.")
    parser.add_argument(
        "--run-reference",
        action="store_true",
        help="Re-run Stage78 reference windows to compute same-method margin diagnostics.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    windows = _target_windows(run_cycles=bool(args.cycles))
    cached_reference = _load_cached_reference_by_window()

    summary_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    candidate_frames: list[pd.DataFrame] = []
    for window in windows:
        if args.run_reference:
            summary_rows.append(_run_reference_backtest(window))
        else:
            summary_rows.append(_reference_row(window, cached_reference))
        summary_row, candidate_row, candidates = _run_candidate(PROFILE, window)
        summary_rows.append(summary_row)
        candidate_rows.append(candidate_row)
        if not candidates.empty:
            candidate_frames.append(candidates)

    summary = pd.DataFrame(summary_rows)
    comparison = _build_comparison(summary)
    candidate_summary = pd.DataFrame(candidate_rows)
    candidate_snapshots = (
        pd.concat(candidate_frames, ignore_index=True, sort=False) if candidate_frames else pd.DataFrame()
    )

    summary.to_csv(SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_CSV_PATH, index=False, encoding="utf-8-sig")
    candidate_summary.to_csv(CANDIDATE_SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")
    candidate_snapshots.to_csv(CANDIDATE_SNAPSHOTS_CSV_PATH, index=False, encoding="utf-8-sig")
    payload = {
        "model_tag": MODEL_TAG,
        "base_version": OFFICIAL_STAGE78_VERSION,
        "profile": asdict(PROFILE),
        "run_cycles": bool(args.cycles),
        "windows": [
            {
                "window_name": str(window["window_name"]),
                "analysis_start": window["analysis_start"].date().isoformat(),
                "analysis_end": window["analysis_end"].date().isoformat(),
            }
            for window in windows
        ],
        "summary": summary.to_dict(orient="records"),
        "comparison": comparison.to_dict(orient="records"),
        "candidate_summary": candidate_summary.to_dict(orient="records"),
        "output_paths": {
            "summary": str(SUMMARY_CSV_PATH),
            "comparison": str(COMPARISON_CSV_PATH),
            "candidate_summary": str(CANDIDATE_SUMMARY_CSV_PATH),
            "candidate_snapshots": str(CANDIDATE_SNAPSHOTS_CSV_PATH),
            "report": str(REPORT_PATH),
        },
    }
    SUMMARY_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    REPORT_PATH.write_text(_build_report(summary, comparison, candidate_summary), encoding="utf-8")

    print(f"[stage158-dynamic-soft-cap] summary: {SUMMARY_CSV_PATH}")
    print(f"[stage158-dynamic-soft-cap] comparison: {COMPARISON_CSV_PATH}")
    print(f"[stage158-dynamic-soft-cap] candidate summary: {CANDIDATE_SUMMARY_CSV_PATH}")
    print(f"[stage158-dynamic-soft-cap] report: {REPORT_PATH}")
    print(summary.to_string(index=False))
    print(candidate_summary.to_string(index=False))


if __name__ == "__main__":
    main()
