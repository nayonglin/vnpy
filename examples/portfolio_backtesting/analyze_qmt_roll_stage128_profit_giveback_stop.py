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
from run_qmt_roll_backtest import START_YEAR_WINDOWS, run_backtest
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage128_profit_giveback_stop_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage128_profit_giveback_stop"

SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
START_YEAR_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_start_year_summary_{MODEL_TAG}.csv"
START_YEAR_COMPARISON_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_start_year_comparison_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
STAGE78_START_YEAR_COMPARISON_PATH: Path = (
    OUTPUT_DIR / "qmt_roll_selection_long015_volref30_corr_fu_satellite_profit_shield_start_year_robustness_comparison.csv"
)


@dataclass(frozen=True)
class GivebackProfile:
    profile_name: str
    trigger_pct: float
    retain_ratio: float
    min_lock_pct: float


PROFILES: tuple[GivebackProfile, ...] = (
    GivebackProfile("stage78_giveback08_retain70_min03", 0.08, 0.70, 0.03),
    GivebackProfile("stage78_giveback10_retain80_min03", 0.10, 0.80, 0.03),
)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or math.isinf(result):
        return default
    return result


def _build_overrides(profile: GivebackProfile) -> dict[str, Any]:
    overrides = build_official_stage78_overrides()
    overrides.update(
        {
            "enable_profit_giveback_stop": True,
            "profit_giveback_trigger_pct": profile.trigger_pct,
            "profit_giveback_retain_ratio": profile.retain_ratio,
            "profit_giveback_min_lock_pct": profile.min_lock_pct,
        }
    )
    return overrides


def _reference_row() -> dict[str, Any]:
    reference = OFFICIAL_STAGE78_REFERENCE_METRICS["full_2020_2026"]
    return {
        "profile_name": "official_stage78_reference",
        "base_version": OFFICIAL_STAGE78_VERSION,
        "capital": OFFICIAL_STAGE78_CAPITAL,
        "trigger_pct": 0.0,
        "retain_ratio": 0.0,
        "min_lock_pct": 0.0,
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
        "profit_giveback_stop_update_count": 0,
    }


def _run_profile(
    profile: GivebackProfile,
    *,
    analysis_start: Any = START_DT,
    analysis_end: Any = END_DT,
    window_name: str = "full_2020_2026",
) -> dict[str, Any]:
    print(
        f"[stage128-profit-giveback] run {profile.profile_name} / {window_name}: "
        f"trigger={profile.trigger_pct:.2%}, retain={profile.retain_ratio:.0%}, "
        f"min_lock={profile.min_lock_pct:.2%}",
        flush=True,
    )
    log_buffer = StringIO()
    try:
        with redirect_stdout(log_buffer), redirect_stderr(log_buffer):
            engine, daily, statistics = run_backtest(
                risk_ratio=BASE_RISK_RATIO,
                strategy_overrides=_build_overrides(profile),
                analysis_start=analysis_start,
                analysis_end=analysis_end,
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
    strategy = getattr(engine, "strategy", None)

    return {
        "profile_name": profile.profile_name,
        "base_version": OFFICIAL_STAGE78_VERSION,
        "capital": OFFICIAL_STAGE78_CAPITAL,
        "window_name": window_name,
        "analysis_start": analysis_start.date().isoformat(),
        "analysis_end": analysis_end.date().isoformat(),
        "trigger_pct": profile.trigger_pct,
        "retain_ratio": profile.retain_ratio,
        "min_lock_pct": profile.min_lock_pct,
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
        "profit_giveback_stop_update_count": int(
            getattr(strategy, "profit_giveback_stop_update_count", 0) if strategy else 0
        ),
    }


def _run_start_year_windows(profile: GivebackProfile) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for window_name, _, analysis_start, analysis_end in START_YEAR_WINDOWS:
        rows.append(
            _run_profile(
                profile,
                analysis_start=analysis_start,
                analysis_end=analysis_end,
                window_name=window_name,
            )
        )
    return pd.DataFrame(rows)


def _build_stage78_start_year_comparison(start_year: pd.DataFrame) -> pd.DataFrame:
    if not STAGE78_START_YEAR_COMPARISON_PATH.exists():
        return pd.DataFrame()

    stage78_raw = pd.read_csv(STAGE78_START_YEAR_COMPARISON_PATH)
    stage78 = stage78_raw[
        [
            "window_name",
            "end_balance_shield",
            "total_return_pct_shield",
            "max_dd_percent_shield",
            "sharpe_ratio_shield",
            "total_trade_count_shield",
            "win_ratio_pct_shield",
        ]
    ].rename(
        columns={
            "end_balance_shield": "stage78_end_balance",
            "total_return_pct_shield": "stage78_total_return_pct",
            "max_dd_percent_shield": "stage78_max_dd_percent",
            "sharpe_ratio_shield": "stage78_sharpe_ratio",
            "total_trade_count_shield": "stage78_total_trade_count",
            "win_ratio_pct_shield": "stage78_win_ratio_pct",
        }
    )
    comparison = start_year.merge(stage78, on="window_name", how="left")
    comparison["end_balance_diff_vs_stage78"] = comparison["end_balance"] - comparison["stage78_end_balance"]
    comparison["total_return_pct_diff_vs_stage78"] = (
        comparison["total_return_pct"] - comparison["stage78_total_return_pct"]
    )
    comparison["max_dd_percent_diff_vs_stage78"] = comparison["max_dd_percent"] - comparison["stage78_max_dd_percent"]
    comparison["sharpe_ratio_diff_vs_stage78"] = comparison["sharpe_ratio"] - comparison["stage78_sharpe_ratio"]
    comparison["trade_count_diff_vs_stage78"] = comparison["total_trade_count"] - comparison["stage78_total_trade_count"]
    return comparison


def _build_report(summary: pd.DataFrame, start_year: pd.DataFrame, start_year_comparison: pd.DataFrame) -> str:
    comparison_section = ""
    if not start_year_comparison.empty:
        comparison_section = "\n".join(
            [
                "",
                "## Start-Year Comparison Vs Stage78",
                "",
                _to_markdown_table(
                    start_year_comparison,
                    [
                        "window_name",
                        "end_balance",
                        "stage78_end_balance",
                        "end_balance_diff_vs_stage78",
                        "max_dd_percent",
                        "stage78_max_dd_percent",
                        "max_dd_percent_diff_vs_stage78",
                        "sharpe_ratio",
                        "stage78_sharpe_ratio",
                        "sharpe_ratio_diff_vs_stage78",
                    ],
                ),
            ]
        )

    return "\n".join(
        [
            "# Stage128 Profit Giveback Stop",
            "",
            "## Boundary",
            "",
            "- Base version: `official_stage78_defensive_v1`.",
            "- Keep product universe, AI product pool, entry ranking, position sizing and existing stops unchanged.",
            "- Only add a default-off profit giveback stop: once a layer has enough max close-profit, lock a coarse fraction of that profit.",
            "",
            "## Full Results",
            "",
            _to_markdown_table(
                summary,
                [
                    "profile_name",
                    "trigger_pct",
                    "retain_ratio",
                    "min_lock_pct",
                    "end_balance",
                    "total_return_pct",
                    "max_dd_percent",
                    "sharpe_ratio",
                    "total_trade_count",
                    "win_ratio_pct",
                    "profit_giveback_stop_update_count",
                    "max_margin_to_balance_pct",
                ],
            ),
            "",
            "## Start-Year Robustness",
            "",
            _to_markdown_table(
                start_year,
                [
                    "profile_name",
                    "window_name",
                    "end_balance",
                    "total_return_pct",
                    "max_dd_percent",
                    "sharpe_ratio",
                    "total_trade_count",
                    "profit_giveback_stop_update_count",
                ],
            ),
            comparison_section,
            "",
            "## Judgement Rule",
            "",
            "- Valuable only if drawdown improves without materially reducing long-cycle return and start-year robustness.",
            "- If it merely cuts winners and lowers Sharpe, stop this direction instead of tuning tighter thresholds.",
        ]
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    full_rows = [_reference_row()]
    for profile in PROFILES:
        full_rows.append(_run_profile(profile))
    summary = pd.DataFrame(full_rows)

    best_profile_name = str(
        summary[summary["profile_name"].ne("official_stage78_reference")]
        .sort_values(["sharpe_ratio", "end_balance"], ascending=False)
        .iloc[0]["profile_name"]
    )
    best_profile = next(profile for profile in PROFILES if profile.profile_name == best_profile_name)
    start_year = _run_start_year_windows(best_profile)
    start_year_comparison = _build_stage78_start_year_comparison(start_year)

    summary.to_csv(SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")
    start_year.to_csv(START_YEAR_CSV_PATH, index=False, encoding="utf-8-sig")
    start_year_comparison.to_csv(START_YEAR_COMPARISON_CSV_PATH, index=False, encoding="utf-8-sig")
    payload = {
        "model_tag": MODEL_TAG,
        "base_version": OFFICIAL_STAGE78_VERSION,
        "profiles": [profile.__dict__ for profile in PROFILES],
        "best_profile_by_full_sharpe": best_profile_name,
        "summary": summary.to_dict(orient="records"),
        "start_year_summary": start_year.to_dict(orient="records"),
        "start_year_comparison": start_year_comparison.to_dict(orient="records"),
        "output_paths": {
            "summary": str(SUMMARY_CSV_PATH),
            "start_year_summary": str(START_YEAR_CSV_PATH),
            "start_year_comparison": str(START_YEAR_COMPARISON_CSV_PATH),
            "report": str(REPORT_PATH),
        },
    }
    SUMMARY_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(_build_report(summary, start_year, start_year_comparison), encoding="utf-8")

    print(f"[stage128-profit-giveback] summary: {SUMMARY_CSV_PATH}")
    print(f"[stage128-profit-giveback] start-year: {START_YEAR_CSV_PATH}")
    print(f"[stage128-profit-giveback] start-year comparison: {START_YEAR_COMPARISON_CSV_PATH}")
    print(f"[stage128-profit-giveback] report: {REPORT_PATH}")
    print(summary.to_string(index=False))
    print(start_year.to_string(index=False))
    if not start_year_comparison.empty:
        print(start_year_comparison.to_string(index=False))


if __name__ == "__main__":
    main()
