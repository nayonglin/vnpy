from __future__ import annotations

import json
import math
import sys
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from analyze_qmt_roll_official_stage78_sizing_cap_quarterly_walkforward import (
    CAPPED_HORIZON_REFERENCE_PATH,
    CAPPED_QUARTER_REFERENCE_PATH,
    HORIZON_DAYS,
    aggregate_horizons,
    quarter_starts,
    summarize_daily_slice,
)
from qmt_roll_official_stage78_config import OFFICIAL_STAGE78_CAPITAL, OFFICIAL_STAGE78_VERSION
from qmt_universe import END_DT
from run_qmt_roll_backtest import run_backtest
from run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest import to_markdown_table
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO
from run_qmt_roll_stage158_dynamic_sizing_soft_cap_backtest import PROFILE, _profile_overrides


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage158_dynamic_sizing_soft_cap_quarterly_wf_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage158_dynamic_sizing_soft_cap_quarterly_walkforward"

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
PROFILE_C: str = "C_stage78_dynamic_soft_cap_1m_to_1_5m_guarded"


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
    overrides = _profile_overrides(PROFILE)

    for analysis_start in quarter_starts():
        window_name = _window_name(analysis_start)
        print(
            f"[stage158-quarterly-wf] {window_name} / {PROFILE.profile_name}: "
            f"{analysis_start.date()} -> {END_DT.date()}"
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
    return comparison


def _aggregate_horizon_comparison(comparison: pd.DataFrame) -> pd.DataFrame:
    if comparison.empty:
        return pd.DataFrame()
    complete = comparison[pd.to_numeric(comparison.get("complete_horizon", 1), errors="coerce").fillna(1).astype(bool)]
    return (
        complete.groupby("horizon", as_index=False)
        .agg(
            window_count=("window_name", "count"),
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


def _build_report(
    quarter_comparison: pd.DataFrame,
    horizon_aggregate: pd.DataFrame,
    horizon_comparison_aggregate: pd.DataFrame,
) -> str:
    return "\n".join(
        [
            "# Stage158 Dynamic Sizing Soft Cap Quarterly Walk-Forward",
            "",
            "## Boundary",
            "",
            "- A = frozen Stage78 quarterly reference.",
            "- C = same Stage158 dynamic sizing soft-cap profile.",
            "- No parameter changes are made after the Stage158 multi-cycle result.",
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
            "## Judgment Rule",
            "",
            "- C can continue only if cold-start windows do not show broad drawdown or Sharpe deterioration.",
            "- If the benefit is concentrated in a few mature-equity windows while many cold starts degrade, do not promote.",
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

    candidate_quarter.to_csv(QUARTER_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    candidate_horizon.to_csv(HORIZON_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    horizon_aggregate.to_csv(HORIZON_AGGREGATE_PATH, index=False, encoding="utf-8-sig")
    quarter_comparison.to_csv(QUARTER_COMPARISON_PATH, index=False, encoding="utf-8-sig")
    horizon_comparison.to_csv(HORIZON_COMPARISON_PATH, index=False, encoding="utf-8-sig")
    horizon_comparison_aggregate.to_csv(HORIZON_COMPARISON_AGGREGATE_PATH, index=False, encoding="utf-8-sig")
    payload = {
        "model_tag": MODEL_TAG,
        "base_version": OFFICIAL_STAGE78_VERSION,
        "profile": PROFILE.__dict__,
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
    }
    SUMMARY_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    REPORT_PATH.write_text(
        _build_report(quarter_comparison, horizon_aggregate, horizon_comparison_aggregate),
        encoding="utf-8",
    )

    print(f"[stage158-quarterly-wf] quarter summary: {QUARTER_SUMMARY_PATH}")
    print(f"[stage158-quarterly-wf] horizon aggregate: {HORIZON_AGGREGATE_PATH}")
    print(f"[stage158-quarterly-wf] quarter comparison: {QUARTER_COMPARISON_PATH}")
    print(f"[stage158-quarterly-wf] horizon comparison aggregate: {HORIZON_COMPARISON_AGGREGATE_PATH}")
    print(f"[stage158-quarterly-wf] report: {REPORT_PATH}")
    print(quarter_comparison.to_string(index=False))
    print(horizon_comparison_aggregate.to_string(index=False))


if __name__ == "__main__":
    main()
