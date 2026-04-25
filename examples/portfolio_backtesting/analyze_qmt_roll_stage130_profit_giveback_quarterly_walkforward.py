from __future__ import annotations

import json
import math
import sys
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from analyze_qmt_roll_stage105_margin_constraint_surface import _to_markdown_table
from qmt_roll_official_stage78_config import (
    OFFICIAL_STAGE78_CAPITAL,
    OFFICIAL_STAGE78_VERSION,
    build_official_stage78_overrides,
)
from qmt_universe import END_DT, START_DT
from run_qmt_roll_backtest import run_backtest
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage130_profit_giveback_quarterly_wf_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage130_profit_giveback_quarterly_walkforward"

QUARTER_SUMMARY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_quarter_summary_{MODEL_TAG}.csv"
HORIZON_SUMMARY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_summary_{MODEL_TAG}.csv"
HORIZON_AGGREGATE_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_aggregate_{MODEL_TAG}.csv"
HORIZON_COMPARISON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_comparison_{MODEL_TAG}.csv"
HORIZON_COMPARISON_AGGREGATE_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_comparison_aggregate_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

STAGE78_QUARTER_REFERENCE_PATH: Path = (
    OUTPUT_DIR
    / "qmt_roll_official_stage78_defensive_quarterly_walkforward_liquidity_quarter_summary_quarterly_wf_liquidity_v1.csv"
)
STAGE78_HORIZON_REFERENCE_PATH: Path = (
    OUTPUT_DIR
    / "qmt_roll_official_stage78_defensive_quarterly_walkforward_liquidity_horizon_summary_quarterly_wf_liquidity_v1.csv"
)

PROFILE_STAGE78: str = "official_stage78_reference"
PROFILE_STAGE128: str = "stage78_giveback10_retain80_min03"
CANDIDATE_PARAMS: dict[str, Any] = {
    "enable_profit_giveback_stop": True,
    "profit_giveback_trigger_pct": 0.10,
    "profit_giveback_retain_ratio": 0.80,
    "profit_giveback_min_lock_pct": 0.03,
}

TRADING_DAYS_PER_YEAR: int = 240
HORIZON_DAYS: tuple[int, ...] = (63, 126, 252)


def quarter_starts() -> list[datetime]:
    starts = pd.date_range(START_DT, END_DT, freq="QS")
    if not starts.empty and starts[0].to_pydatetime() != START_DT:
        starts = pd.DatetimeIndex([pd.Timestamp(START_DT), *starts])
    return [ts.to_pydatetime() for ts in starts if ts.to_pydatetime() <= END_DT]


def _window_name(analysis_start: datetime) -> str:
    return f"q{analysis_start.year}_{((analysis_start.month - 1) // 3) + 1}"


def _candidate_overrides() -> dict[str, Any]:
    overrides = build_official_stage78_overrides()
    overrides.update(CANDIDATE_PARAMS)
    return overrides


def _summarize_daily_slice(df: pd.DataFrame, *, capital: float) -> dict[str, float]:
    if df.empty:
        return {
            "end_balance": 0.0,
            "total_return_pct": 0.0,
            "max_dd_percent": 0.0,
            "sharpe_ratio": 0.0,
            "total_slippage": 0.0,
            "total_trade_count": 0.0,
            "day_count": 0.0,
        }

    balance = pd.to_numeric(df["balance"], errors="coerce").ffill().fillna(capital)
    net_pnl = pd.to_numeric(df.get("net_pnl", pd.Series(0.0, index=df.index)), errors="coerce").fillna(0.0)
    daily_return = net_pnl / balance.shift(1).fillna(capital).replace(0.0, np.nan)
    daily_return = daily_return.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    high_water = balance.cummax()
    dd_pct = (balance / high_water.replace(0.0, np.nan) - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0) * 100.0
    std = float(daily_return.std(ddof=1))
    sharpe = float(daily_return.mean() / std * math.sqrt(TRADING_DAYS_PER_YEAR)) if std > 1e-12 else 0.0
    end_balance = float(balance.iloc[-1])
    return {
        "end_balance": end_balance,
        "total_return_pct": (end_balance - capital) / capital * 100.0,
        "max_dd_percent": float(dd_pct.min()),
        "sharpe_ratio": sharpe,
        "total_slippage": float(pd.to_numeric(df.get("slippage", 0.0), errors="coerce").fillna(0.0).sum()),
        "total_trade_count": float(pd.to_numeric(df.get("trade_count", 0.0), errors="coerce").fillna(0.0).sum()),
        "day_count": float(len(df)),
    }


def _run_candidate_window(analysis_start: datetime) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    window_name = _window_name(analysis_start)
    print(
        f"[stage130-profit-giveback-quarterly] {window_name} / {PROFILE_STAGE128}: "
        f"{analysis_start.date()} -> {END_DT.date()}",
        flush=True,
    )
    log_buffer = StringIO()
    try:
        with redirect_stdout(log_buffer), redirect_stderr(log_buffer):
            _, analysis_df, _ = run_backtest(
                risk_ratio=BASE_RISK_RATIO,
                strategy_overrides=_candidate_overrides(),
                analysis_start=analysis_start,
                analysis_end=END_DT,
                capital=OFFICIAL_STAGE78_CAPITAL,
                save_artifacts=False,
                include_start_year_sweep=False,
            )
    except Exception:
        sys.stderr.write(log_buffer.getvalue())
        raise

    daily = analysis_df.copy() if analysis_df is not None else pd.DataFrame()
    if not daily.empty:
        daily.sort_index(inplace=True)

    base_fields = {
        "profile_name": PROFILE_STAGE128,
        "base_version": OFFICIAL_STAGE78_VERSION,
        "capital": OFFICIAL_STAGE78_CAPITAL,
        "window_name": window_name,
        "analysis_start": analysis_start.date().isoformat(),
        "analysis_end": END_DT.date().isoformat(),
    }
    quarter_row = {
        **base_fields,
        "horizon": "to_end",
        **_summarize_daily_slice(daily, capital=OFFICIAL_STAGE78_CAPITAL),
    }
    horizon_rows: list[dict[str, Any]] = []
    for horizon_days in HORIZON_DAYS:
        horizon_df = daily.iloc[:horizon_days].copy()
        horizon = _summarize_daily_slice(horizon_df, capital=OFFICIAL_STAGE78_CAPITAL)
        horizon_rows.append(
            {
                **base_fields,
                "horizon": f"{horizon_days}d",
                "horizon_days": horizon_days,
                "complete_horizon": int(horizon["day_count"] >= horizon_days),
                **horizon,
            }
        )
    return quarter_row, horizon_rows


def _load_stage78_reference() -> tuple[pd.DataFrame, pd.DataFrame]:
    if not STAGE78_QUARTER_REFERENCE_PATH.exists() or not STAGE78_HORIZON_REFERENCE_PATH.exists():
        raise FileNotFoundError("missing Stage78 quarterly reference outputs")

    quarter = pd.read_csv(STAGE78_QUARTER_REFERENCE_PATH)
    horizon = pd.read_csv(STAGE78_HORIZON_REFERENCE_PATH)
    quarter.insert(0, "profile_name", PROFILE_STAGE78)
    quarter.insert(1, "base_version", OFFICIAL_STAGE78_VERSION)
    quarter.insert(2, "capital", OFFICIAL_STAGE78_CAPITAL)
    horizon.insert(0, "profile_name", PROFILE_STAGE78)
    horizon.insert(1, "base_version", OFFICIAL_STAGE78_VERSION)
    horizon.insert(2, "capital", OFFICIAL_STAGE78_CAPITAL)
    return quarter, horizon


def _aggregate_horizons(horizon_df: pd.DataFrame) -> pd.DataFrame:
    complete = horizon_df[horizon_df["complete_horizon"].astype(bool)].copy()
    if complete.empty:
        return pd.DataFrame()
    aggregate = (
        complete.groupby(["profile_name", "horizon"], as_index=False)
        .agg(
            window_count=("window_name", "count"),
            positive_return_count=("total_return_pct", lambda s: int((s > 0).sum())),
            non_positive_return_count=("total_return_pct", lambda s: int((s <= 0).sum())),
            median_return_pct=("total_return_pct", "median"),
            worst_return_pct=("total_return_pct", "min"),
            best_return_pct=("total_return_pct", "max"),
            median_max_dd_percent=("max_dd_percent", "median"),
            worst_max_dd_percent=("max_dd_percent", "min"),
            median_sharpe=("sharpe_ratio", "median"),
            worst_sharpe=("sharpe_ratio", "min"),
            median_trade_count=("total_trade_count", "median"),
            median_slippage=("total_slippage", "median"),
        )
        .sort_values(["horizon", "profile_name"])
        .reset_index(drop=True)
    )
    aggregate["positive_return_rate_pct"] = (
        aggregate["positive_return_count"] / aggregate["window_count"].replace(0, np.nan) * 100.0
    ).fillna(0.0)
    return aggregate


def _build_horizon_comparison(horizon_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    complete = horizon_df[horizon_df["complete_horizon"].astype(bool)].copy()
    keys = ["window_name", "analysis_start", "horizon", "horizon_days"]
    values = ["end_balance", "total_return_pct", "max_dd_percent", "sharpe_ratio", "total_slippage", "total_trade_count"]

    base = complete[complete["profile_name"] == PROFILE_STAGE78][keys + values].copy()
    candidate = complete[complete["profile_name"] == PROFILE_STAGE128][keys + values].copy()
    comparison = base.merge(candidate, on=keys, how="inner", suffixes=("_stage78", "_stage128"))
    for column in values:
        comparison[f"{column}_diff"] = comparison[f"{column}_stage128"] - comparison[f"{column}_stage78"]

    comparison["stage128_return_better"] = (comparison["total_return_pct_diff"] > 1e-9).astype(int)
    comparison["stage128_return_worse"] = (comparison["total_return_pct_diff"] < -1e-9).astype(int)
    comparison["stage128_drawdown_better"] = (comparison["max_dd_percent_diff"] > 1e-9).astype(int)
    comparison["stage128_drawdown_worse"] = (comparison["max_dd_percent_diff"] < -1e-9).astype(int)
    comparison["stage128_sharpe_better"] = (comparison["sharpe_ratio_diff"] > 1e-9).astype(int)
    comparison["stage128_sharpe_worse"] = (comparison["sharpe_ratio_diff"] < -1e-9).astype(int)

    if comparison.empty:
        aggregate = pd.DataFrame()
    else:
        aggregate = (
            comparison.groupby("horizon", as_index=False)
            .agg(
                window_count=("window_name", "count"),
                return_win_count=("stage128_return_better", "sum"),
                return_loss_count=("stage128_return_worse", "sum"),
                drawdown_win_count=("stage128_drawdown_better", "sum"),
                drawdown_loss_count=("stage128_drawdown_worse", "sum"),
                sharpe_win_count=("stage128_sharpe_better", "sum"),
                sharpe_loss_count=("stage128_sharpe_worse", "sum"),
                median_return_diff=("total_return_pct_diff", "median"),
                worst_return_diff=("total_return_pct_diff", "min"),
                best_return_diff=("total_return_pct_diff", "max"),
                median_max_dd_diff=("max_dd_percent_diff", "median"),
                worst_max_dd_diff=("max_dd_percent_diff", "min"),
                median_sharpe_diff=("sharpe_ratio_diff", "median"),
                worst_sharpe_diff=("sharpe_ratio_diff", "min"),
                median_slippage_diff=("total_slippage_diff", "median"),
                median_trade_count_diff=("total_trade_count_diff", "median"),
            )
            .sort_values("horizon")
            .reset_index(drop=True)
        )
        for metric in ["return", "drawdown", "sharpe"]:
            aggregate[f"{metric}_win_rate_pct"] = (
                aggregate[f"{metric}_win_count"] / aggregate["window_count"].replace(0, np.nan) * 100.0
            ).fillna(0.0)
    return comparison, aggregate


def _build_report(
    horizon_aggregate: pd.DataFrame,
    comparison_aggregate: pd.DataFrame,
    comparison: pd.DataFrame,
) -> str:
    return "\n".join(
        [
            "# Stage130 Profit Giveback Quarterly Walk-Forward",
            "",
            "## Boundary",
            "",
            "- Base: `official_stage78_defensive_v1` quarterly reference.",
            "- Candidate: fixed `stage78_giveback10_retain80_min03`.",
            "- No parameter search; every quarter is treated as a cold-start point.",
            "",
            "## Horizon Aggregate",
            "",
            _to_markdown_table(
                horizon_aggregate,
                [
                    "profile_name",
                    "horizon",
                    "window_count",
                    "positive_return_rate_pct",
                    "worst_return_pct",
                    "median_return_pct",
                    "worst_max_dd_percent",
                    "median_sharpe",
                    "worst_sharpe",
                    "median_trade_count",
                    "median_slippage",
                ],
            ),
            "",
            "## Comparison Aggregate",
            "",
            _to_markdown_table(
                comparison_aggregate,
                [
                    "horizon",
                    "window_count",
                    "return_win_rate_pct",
                    "drawdown_win_rate_pct",
                    "sharpe_win_rate_pct",
                    "median_return_diff",
                    "worst_return_diff",
                    "median_max_dd_diff",
                    "worst_max_dd_diff",
                    "median_sharpe_diff",
                    "worst_sharpe_diff",
                ],
            ),
            "",
            "## Worst Candidate Windows",
            "",
            _to_markdown_table(
                comparison.sort_values("total_return_pct_diff").head(12),
                [
                    "window_name",
                    "analysis_start",
                    "horizon",
                    "total_return_pct_stage128",
                    "total_return_pct_stage78",
                    "total_return_pct_diff",
                    "max_dd_percent_stage128",
                    "max_dd_percent_stage78",
                    "max_dd_percent_diff",
                    "sharpe_ratio_diff",
                ],
            ),
            "",
            "## Judgement Rule",
            "",
            "- A candidate remains alive only if median return and Sharpe improve without materially worsening worst windows.",
            "- If quarterly cold starts degrade, the full-cycle breakthrough is not enough.",
        ]
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    stage78_quarter, stage78_horizon = _load_stage78_reference()

    candidate_quarter_rows: list[dict[str, Any]] = []
    candidate_horizon_rows: list[dict[str, Any]] = []
    for analysis_start in quarter_starts():
        quarter_row, horizon_rows = _run_candidate_window(analysis_start)
        candidate_quarter_rows.append(quarter_row)
        candidate_horizon_rows.extend(horizon_rows)

    candidate_quarter = pd.DataFrame(candidate_quarter_rows)
    candidate_horizon = pd.DataFrame(candidate_horizon_rows)
    quarter_summary = pd.concat([stage78_quarter, candidate_quarter], ignore_index=True, sort=False)
    horizon_summary = pd.concat([stage78_horizon, candidate_horizon], ignore_index=True, sort=False)
    horizon_aggregate = _aggregate_horizons(horizon_summary)
    comparison, comparison_aggregate = _build_horizon_comparison(horizon_summary)

    quarter_summary.to_csv(QUARTER_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    horizon_summary.to_csv(HORIZON_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    horizon_aggregate.to_csv(HORIZON_AGGREGATE_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(HORIZON_COMPARISON_PATH, index=False, encoding="utf-8-sig")
    comparison_aggregate.to_csv(HORIZON_COMPARISON_AGGREGATE_PATH, index=False, encoding="utf-8-sig")

    payload = {
        "model_tag": MODEL_TAG,
        "base_version": OFFICIAL_STAGE78_VERSION,
        "capital": OFFICIAL_STAGE78_CAPITAL,
        "base_risk_ratio": BASE_RISK_RATIO,
        "candidate_params": CANDIDATE_PARAMS,
        "horizon_aggregate": horizon_aggregate.to_dict(orient="records"),
        "comparison_aggregate": comparison_aggregate.to_dict(orient="records"),
        "output_paths": {
            "quarter_summary": str(QUARTER_SUMMARY_PATH),
            "horizon_summary": str(HORIZON_SUMMARY_PATH),
            "horizon_aggregate": str(HORIZON_AGGREGATE_PATH),
            "horizon_comparison": str(HORIZON_COMPARISON_PATH),
            "horizon_comparison_aggregate": str(HORIZON_COMPARISON_AGGREGATE_PATH),
            "summary_json": str(SUMMARY_JSON_PATH),
            "report": str(REPORT_PATH),
        },
    }
    SUMMARY_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(_build_report(horizon_aggregate, comparison_aggregate, comparison), encoding="utf-8")

    print(f"[stage130-profit-giveback-quarterly] summary: {SUMMARY_JSON_PATH}")
    print(f"[stage130-profit-giveback-quarterly] report: {REPORT_PATH}")
    print(comparison_aggregate.to_string(index=False))


if __name__ == "__main__":
    main()
