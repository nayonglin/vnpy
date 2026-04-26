from __future__ import annotations

import json
import math
import sys
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Any

import pandas as pd

from analyze_qmt_roll_official_stage78_sizing_cap_quarterly_walkforward import (
    CAPPED_HORIZON_REFERENCE_PATH,
    CAPPED_QUARTER_REFERENCE_PATH,
    HORIZON_DAYS,
    aggregate_horizons,
    quarter_starts,
    summarize_daily_slice,
)
from qmt_roll_official_stage78_config import (
    OFFICIAL_STAGE78_CAPITAL,
    OFFICIAL_STAGE78_VERSION,
    build_official_stage78_overrides,
)
from qmt_universe import END_DT
from run_qmt_roll_backtest import run_backtest
from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import to_markdown_table
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage161_peak_guard_quarterly_wf_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage161_peak_guard_quarterly_walkforward"

QUARTER_SUMMARY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_quarter_summary_{MODEL_TAG}.csv"
HORIZON_SUMMARY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_summary_{MODEL_TAG}.csv"
HORIZON_AGGREGATE_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_aggregate_{MODEL_TAG}.csv"
QUARTER_COMPARISON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_quarter_comparison_{MODEL_TAG}.csv"
HORIZON_COMPARISON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_comparison_{MODEL_TAG}.csv"
HORIZON_COMPARISON_AGGREGATE_PATH: Path = (
    OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_comparison_aggregate_{MODEL_TAG}.csv"
)
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

PROFILE_A: str = "A_official_stage78_reference"
PROFILE_C: str = "C_peak_guard90_rank1"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or math.isinf(result):
        return default
    return result


def _window_name(analysis_start: Any) -> str:
    ts = pd.Timestamp(analysis_start)
    return f"q{ts.year}_{((ts.month - 1) // 3) + 1}"


def _profile_overrides() -> dict[str, Any]:
    overrides = build_official_stage78_overrides()
    overrides.update(
        {
            "enable_incremental_margin_budget_gate": True,
            "incremental_margin_budget_gate_usage_ratio": 0.90,
            "incremental_margin_budget_gate_min_openable_candidates": 2,
            "incremental_margin_budget_gate_protected_selection_rank": 1,
        }
    )
    return overrides


def _load_reference(path: Path, *, horizon: bool) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"missing Stage78 quarterly reference: {path}")
    frame = pd.read_csv(path)
    frame = frame.copy()
    frame["profile_name"] = PROFILE_A
    frame["model_tag"] = "official_stage78_quarterly_reference"
    frame["base_version"] = OFFICIAL_STAGE78_VERSION
    if horizon:
        frame["complete_horizon"] = pd.to_numeric(frame.get("complete_horizon", 1), errors="coerce").fillna(1).astype(int)
    return frame


def _run_candidate_quarterly() -> tuple[pd.DataFrame, pd.DataFrame]:
    quarter_rows: list[dict[str, Any]] = []
    horizon_rows: list[dict[str, Any]] = []
    overrides = _profile_overrides()

    for analysis_start in quarter_starts():
        window_name = _window_name(analysis_start)
        print(
            f"[stage161-peak-guard-quarterly] {window_name} / {PROFILE_C}: "
            f"{analysis_start.date()} -> {END_DT.date()}",
            flush=True,
        )
        log_buffer = StringIO()
        try:
            with redirect_stdout(log_buffer), redirect_stderr(log_buffer):
                _, analysis_df, _ = run_backtest(
                    risk_ratio=BASE_RISK_RATIO,
                    strategy_overrides=overrides,
                    analysis_start=analysis_start,
                    analysis_end=END_DT,
                    capital=OFFICIAL_STAGE78_CAPITAL,
                    save_artifacts=False,
                    include_start_year_sweep=False,
                )
        except Exception:
            sys.stderr.write(log_buffer.getvalue())
            raise

        if analysis_df is None:
            analysis_df = pd.DataFrame()
        analysis_df = analysis_df.copy()
        if not analysis_df.empty:
            analysis_df.sort_index(inplace=True)

        to_end = summarize_daily_slice(analysis_df, capital=OFFICIAL_STAGE78_CAPITAL)
        quarter_rows.append(
            {
                "profile_name": PROFILE_C,
                "model_tag": MODEL_TAG,
                "base_version": OFFICIAL_STAGE78_VERSION,
                "window_name": window_name,
                "analysis_start": analysis_start.date().isoformat(),
                "analysis_end": END_DT.date().isoformat(),
                "horizon": "to_end",
                **to_end,
            }
        )

        for horizon_days in HORIZON_DAYS:
            horizon_df = analysis_df.iloc[:horizon_days].copy()
            horizon_result = summarize_daily_slice(horizon_df, capital=OFFICIAL_STAGE78_CAPITAL)
            horizon_rows.append(
                {
                    "profile_name": PROFILE_C,
                    "model_tag": MODEL_TAG,
                    "base_version": OFFICIAL_STAGE78_VERSION,
                    "window_name": window_name,
                    "analysis_start": analysis_start.date().isoformat(),
                    "analysis_end": END_DT.date().isoformat(),
                    "horizon": f"{horizon_days}d",
                    "horizon_days": horizon_days,
                    "complete_horizon": int(horizon_result["day_count"] >= horizon_days),
                    **horizon_result,
                }
            )

    return pd.DataFrame(quarter_rows), pd.DataFrame(horizon_rows)


def _build_comparison(reference: pd.DataFrame, candidate: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    value_columns = [
        "end_balance",
        "total_return_pct",
        "max_dd_percent",
        "sharpe_ratio",
        "total_slippage",
        "total_trade_count",
    ]
    left = reference[keys + value_columns].copy()
    right = candidate[keys + value_columns].copy()
    comparison = left.merge(right, on=keys, suffixes=("_a", "_c"), how="inner")
    for column in value_columns:
        comparison[f"{column}_diff"] = (
            pd.to_numeric(comparison[f"{column}_c"], errors="coerce")
            - pd.to_numeric(comparison[f"{column}_a"], errors="coerce")
        )
    comparison["c_return_better"] = (comparison["total_return_pct_diff"] > 1e-9).astype(int)
    comparison["c_return_worse"] = (comparison["total_return_pct_diff"] < -1e-9).astype(int)
    comparison["c_drawdown_worse"] = (comparison["max_dd_percent_diff"] < -1e-9).astype(int)
    comparison["c_sharpe_worse"] = (comparison["sharpe_ratio_diff"] < -1e-9).astype(int)
    comparison["c_changed"] = (
        comparison[["end_balance_diff", "max_dd_percent_diff", "sharpe_ratio_diff"]].abs().sum(axis=1) > 1e-9
    ).astype(int)
    return comparison


def _aggregate_horizon_comparison(comparison: pd.DataFrame) -> pd.DataFrame:
    if comparison.empty:
        return pd.DataFrame()
    complete = comparison[pd.to_numeric(comparison.get("complete_horizon", 1), errors="coerce").fillna(1).astype(bool)]
    return (
        complete.groupby("horizon", as_index=False)
        .agg(
            window_count=("window_name", "count"),
            changed_count=("c_changed", "sum"),
            c_return_better_count=("c_return_better", "sum"),
            c_return_worse_count=("c_return_worse", "sum"),
            c_drawdown_worse_count=("c_drawdown_worse", "sum"),
            c_sharpe_worse_count=("c_sharpe_worse", "sum"),
            median_return_diff_pct=("total_return_pct_diff", "median"),
            worst_return_diff_pct=("total_return_pct_diff", "min"),
            best_return_diff_pct=("total_return_pct_diff", "max"),
            median_max_dd_diff_pct=("max_dd_percent_diff", "median"),
            worst_max_dd_diff_pct=("max_dd_percent_diff", "min"),
            median_sharpe_diff=("sharpe_ratio_diff", "median"),
            worst_sharpe_diff=("sharpe_ratio_diff", "min"),
            median_slippage_diff=("total_slippage_diff", "median"),
            max_trade_count_diff=("total_trade_count_diff", "max"),
        )
        .sort_values("horizon")
        .reset_index(drop=True)
    )


def _quarter_decision(quarter_comparison: pd.DataFrame, horizon_aggregate: pd.DataFrame) -> str:
    if quarter_comparison.empty:
        return "fail_missing_comparison"
    changed = int(pd.to_numeric(quarter_comparison.get("c_changed", 0), errors="coerce").fillna(0).sum())
    return_worse = int(pd.to_numeric(quarter_comparison.get("c_return_worse", 0), errors="coerce").fillna(0).sum())
    sharpe_worse = int(pd.to_numeric(quarter_comparison.get("c_sharpe_worse", 0), errors="coerce").fillna(0).sum())
    median_to_end_return = _safe_float(quarter_comparison["total_return_pct_diff"].median())
    worst_to_end_return = _safe_float(quarter_comparison["total_return_pct_diff"].min())

    horizon_bad = False
    if not horizon_aggregate.empty:
        horizon_bad = bool(
            (
                pd.to_numeric(horizon_aggregate["c_return_worse_count"], errors="coerce").fillna(0)
                > pd.to_numeric(horizon_aggregate["c_return_better_count"], errors="coerce").fillna(0)
            ).any()
        )

    if return_worse > max(3, changed // 2) or sharpe_worse > max(3, changed // 2):
        return "fail_quarterly_cold_start_broad_damage"
    if median_to_end_return < -10.0 or worst_to_end_return < -120.0:
        return "fail_quarterly_return_drag"
    if horizon_bad:
        return "fail_short_horizon_distribution"
    return "candidate_for_shadow_ab_only"


def _build_report(
    quarter_comparison: pd.DataFrame,
    horizon_aggregate: pd.DataFrame,
    horizon_comparison_aggregate: pd.DataFrame,
    decision: str,
) -> str:
    return "\n".join(
        [
            "# Stage161 Peak Guard Quarterly Walk-Forward",
            "",
            "## Boundary",
            "",
            "- A = frozen Stage78 quarterly reference.",
            "- C = Stage160 `C_peak_guard90_rank1` with no parameter changes.",
            "- This is a cold-start robustness test, not a new optimization sweep.",
            "",
            "## Quarter To End Comparison",
            "",
            to_markdown_table(
                quarter_comparison[
                    [
                        "window_name",
                        "total_return_pct_a",
                        "total_return_pct_c",
                        "total_return_pct_diff",
                        "max_dd_percent_a",
                        "max_dd_percent_c",
                        "max_dd_percent_diff",
                        "sharpe_ratio_a",
                        "sharpe_ratio_c",
                        "sharpe_ratio_diff",
                        "total_trade_count_diff",
                    ]
                ]
            ),
            "",
            "## Horizon Aggregate",
            "",
            to_markdown_table(horizon_aggregate),
            "",
            "## Horizon A Vs C Aggregate",
            "",
            to_markdown_table(horizon_comparison_aggregate),
            "",
            "## Decision",
            "",
            f"- `{decision}`",
            "- If C shows broad cold-start return or Sharpe damage, it cannot replace Stage78 even though full-period margin peaks improve.",
            "- If C passes, it should still be treated as a shadow A/B deployment layer before formal promotion.",
        ]
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    reference_quarter = _load_reference(CAPPED_QUARTER_REFERENCE_PATH, horizon=False)
    reference_horizon = _load_reference(CAPPED_HORIZON_REFERENCE_PATH, horizon=True)
    candidate_quarter, candidate_horizon = _run_candidate_quarterly()

    all_horizon = pd.concat([reference_horizon, candidate_horizon], ignore_index=True, sort=False)
    horizon_aggregate = aggregate_horizons(all_horizon)
    quarter_comparison = _build_comparison(
        reference_quarter,
        candidate_quarter,
        ["window_name", "analysis_start", "horizon"],
    )
    horizon_comparison = _build_comparison(
        reference_horizon,
        candidate_horizon,
        ["window_name", "analysis_start", "horizon", "horizon_days", "complete_horizon"],
    )
    horizon_comparison_aggregate = _aggregate_horizon_comparison(horizon_comparison)
    decision = _quarter_decision(quarter_comparison, horizon_comparison_aggregate)

    candidate_quarter.to_csv(QUARTER_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    candidate_horizon.to_csv(HORIZON_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    horizon_aggregate.to_csv(HORIZON_AGGREGATE_PATH, index=False, encoding="utf-8-sig")
    quarter_comparison.to_csv(QUARTER_COMPARISON_PATH, index=False, encoding="utf-8-sig")
    horizon_comparison.to_csv(HORIZON_COMPARISON_PATH, index=False, encoding="utf-8-sig")
    horizon_comparison_aggregate.to_csv(HORIZON_COMPARISON_AGGREGATE_PATH, index=False, encoding="utf-8-sig")
    REPORT_PATH.write_text(
        _build_report(quarter_comparison, horizon_aggregate, horizon_comparison_aggregate, decision),
        encoding="utf-8",
    )
    SUMMARY_JSON_PATH.write_text(
        json.dumps(
            {
                "model_tag": MODEL_TAG,
                "base_version": OFFICIAL_STAGE78_VERSION,
                "profile_c": PROFILE_C,
                "strategy_overrides": _profile_overrides(),
                "decision": decision,
                "quarter_comparison": quarter_comparison.to_dict(orient="records"),
                "horizon_comparison_aggregate": horizon_comparison_aggregate.to_dict(orient="records"),
                "output_paths": {
                    "quarter_summary": str(QUARTER_SUMMARY_PATH),
                    "horizon_summary": str(HORIZON_SUMMARY_PATH),
                    "horizon_aggregate": str(HORIZON_AGGREGATE_PATH),
                    "quarter_comparison": str(QUARTER_COMPARISON_PATH),
                    "horizon_comparison": str(HORIZON_COMPARISON_PATH),
                    "horizon_comparison_aggregate": str(HORIZON_COMPARISON_AGGREGATE_PATH),
                    "report": str(REPORT_PATH),
                },
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    print(f"[stage161-peak-guard-quarterly] quarter summary: {QUARTER_SUMMARY_PATH}")
    print(f"[stage161-peak-guard-quarterly] horizon aggregate: {HORIZON_AGGREGATE_PATH}")
    print(f"[stage161-peak-guard-quarterly] quarter comparison: {QUARTER_COMPARISON_PATH}")
    print(f"[stage161-peak-guard-quarterly] horizon comparison aggregate: {HORIZON_COMPARISON_AGGREGATE_PATH}")
    print(f"[stage161-peak-guard-quarterly] report: {REPORT_PATH}")
    print(f"[stage161-peak-guard-quarterly] decision: {decision}")
    print(horizon_comparison_aggregate.to_string(index=False))


if __name__ == "__main__":
    main()
