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

from qmt_roll_official_stage78_config import OFFICIAL_STAGE78_ROLE, OFFICIAL_STAGE78_VERSION
from qmt_universe import END_DT, START_DT
from run_qmt_roll_backtest import run_backtest
from run_qmt_roll_official_stage78_fu_sn_satellite_candidate_backtest import (
    CAPITAL,
    EXPERIMENT_NAME,
    MODEL_TAG as CANDIDATE_MODEL_TAG,
    SATELLITE_PRODUCTS,
    SIZING_EQUITY_CAP,
    build_strategy_overrides,
)
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage78_fu_sn_satellite_quarterly_wf_v1"
OUTPUT_PREFIX: str = "qmt_roll_official_stage78_fu_sn_satellite_quarterly_walkforward"

QUARTER_SUMMARY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_quarter_summary_{MODEL_TAG}.csv"
HORIZON_SUMMARY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_summary_{MODEL_TAG}.csv"
HORIZON_AGGREGATE_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_aggregate_{MODEL_TAG}.csv"
HORIZON_COMPARISON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_comparison_{MODEL_TAG}.csv"
HORIZON_COMPARISON_AGGREGATE_PATH: Path = (
    OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_comparison_aggregate_{MODEL_TAG}.csv"
)
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

PROFILE_STAGE78: str = "official_stage78_defensive_v1"
PROFILE_CANDIDATE: str = "stage78_plus_fu_sn_satellite"
TRADING_DAYS_PER_YEAR: int = 240
HORIZON_DAYS: tuple[int, ...] = (63, 126, 252)


def quarter_starts() -> list[datetime]:
    starts = pd.date_range(START_DT, END_DT, freq="QS")
    if not starts.empty and starts[0].to_pydatetime() != START_DT:
        starts = pd.DatetimeIndex([pd.Timestamp(START_DT), *starts])
    return [ts.to_pydatetime() for ts in starts if ts.to_pydatetime() <= END_DT]


def summarize_daily_slice(df: pd.DataFrame, *, capital: float) -> dict[str, float]:
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
    dd_pct = (balance / high_water.replace(0.0, np.nan) - 1.0).replace(
        [np.inf, -np.inf],
        np.nan,
    ).fillna(0.0) * 100.0
    std = float(daily_return.std(ddof=1))
    sharpe = float(daily_return.mean() / std * math.sqrt(TRADING_DAYS_PER_YEAR)) if std > 1e-12 else 0.0
    end_balance = float(balance.iloc[-1])
    return {
        "end_balance": end_balance,
        "total_return_pct": (end_balance - capital) / capital * 100.0,
        "max_dd_percent": float(dd_pct.min()),
        "sharpe_ratio": sharpe,
        "total_slippage": float(pd.to_numeric(df.get("slippage", 0.0), errors="coerce").fillna(0.0).sum()),
        "total_trade_count": float(
            pd.to_numeric(df.get("trade_count", 0.0), errors="coerce").fillna(0.0).sum()
        ),
        "day_count": float(len(df)),
    }


def run_candidate_quarterly() -> tuple[pd.DataFrame, pd.DataFrame]:
    overrides = build_strategy_overrides()
    quarter_rows: list[dict[str, Any]] = []
    horizon_rows: list[dict[str, Any]] = []
    for analysis_start in quarter_starts():
        window_name = f"q{analysis_start.year}_{((analysis_start.month - 1) // 3) + 1}"
        print(
            f"[stage78-fu-sn-quarterly] {window_name}: "
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
                    capital=CAPITAL,
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

        to_end = summarize_daily_slice(analysis_df, capital=CAPITAL)
        quarter_rows.append(
            {
                "profile_name": PROFILE_CANDIDATE,
                "window_name": window_name,
                "analysis_start": analysis_start.date().isoformat(),
                "analysis_end": END_DT.date().isoformat(),
                "horizon": "to_end",
                "capital": CAPITAL,
                "sizing_equity_cap": SIZING_EQUITY_CAP,
                **to_end,
            }
        )
        for horizon_days in HORIZON_DAYS:
            horizon_df = analysis_df.iloc[:horizon_days].copy()
            horizon = summarize_daily_slice(horizon_df, capital=CAPITAL)
            horizon_rows.append(
                {
                    "profile_name": PROFILE_CANDIDATE,
                    "window_name": window_name,
                    "analysis_start": analysis_start.date().isoformat(),
                    "analysis_end": END_DT.date().isoformat(),
                    "horizon": f"{horizon_days}d",
                    "horizon_days": horizon_days,
                    "complete_horizon": int(horizon["day_count"] >= horizon_days),
                    "capital": CAPITAL,
                    "sizing_equity_cap": SIZING_EQUITY_CAP,
                    **horizon,
                }
            )
    return pd.DataFrame(quarter_rows), pd.DataFrame(horizon_rows)


def load_stage78_reference() -> tuple[pd.DataFrame, pd.DataFrame]:
    if not STAGE78_QUARTER_REFERENCE_PATH.exists():
        raise FileNotFoundError(STAGE78_QUARTER_REFERENCE_PATH)
    if not STAGE78_HORIZON_REFERENCE_PATH.exists():
        raise FileNotFoundError(STAGE78_HORIZON_REFERENCE_PATH)
    quarter = pd.read_csv(STAGE78_QUARTER_REFERENCE_PATH)
    horizon = pd.read_csv(STAGE78_HORIZON_REFERENCE_PATH)
    quarter.insert(0, "profile_name", PROFILE_STAGE78)
    horizon.insert(0, "profile_name", PROFILE_STAGE78)
    return quarter, horizon


def aggregate_horizons(horizon_df: pd.DataFrame) -> pd.DataFrame:
    complete_df = horizon_df[horizon_df["complete_horizon"].astype(bool)].copy()
    if complete_df.empty:
        return pd.DataFrame()
    aggregate_df = (
        complete_df.groupby(["profile_name", "horizon"], as_index=False)
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
    aggregate_df["positive_return_rate_pct"] = (
        aggregate_df["positive_return_count"] / aggregate_df["window_count"].replace(0, np.nan) * 100.0
    ).fillna(0.0)
    return aggregate_df


def build_horizon_comparison(horizon_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    complete_df = horizon_df[horizon_df["complete_horizon"].astype(bool)].copy()
    pivot_keys = ["window_name", "analysis_start", "horizon", "horizon_days"]
    value_columns = [
        "end_balance",
        "total_return_pct",
        "max_dd_percent",
        "sharpe_ratio",
        "total_slippage",
        "total_trade_count",
    ]
    reference = complete_df[complete_df["profile_name"] == PROFILE_STAGE78][pivot_keys + value_columns].copy()
    candidate = complete_df[complete_df["profile_name"] == PROFILE_CANDIDATE][pivot_keys + value_columns].copy()
    comparison = reference.merge(candidate, on=pivot_keys, suffixes=("_stage78", "_candidate"), how="inner")
    for column in value_columns:
        comparison[f"{column}_diff"] = comparison[f"{column}_candidate"] - comparison[f"{column}_stage78"]
    comparison["candidate_return_better"] = (comparison["total_return_pct_diff"] > 1e-9).astype(int)
    comparison["candidate_return_worse"] = (comparison["total_return_pct_diff"] < -1e-9).astype(int)
    comparison["candidate_drawdown_worse"] = (comparison["max_dd_percent_diff"] < -1e-9).astype(int)
    comparison["candidate_sharpe_worse"] = (comparison["sharpe_ratio_diff"] < -1e-9).astype(int)

    if comparison.empty:
        aggregate = pd.DataFrame()
    else:
        aggregate = (
            comparison.groupby("horizon", as_index=False)
            .agg(
                window_count=("window_name", "count"),
                return_better_count=("candidate_return_better", "sum"),
                return_worse_count=("candidate_return_worse", "sum"),
                drawdown_worse_count=("candidate_drawdown_worse", "sum"),
                sharpe_worse_count=("candidate_sharpe_worse", "sum"),
                median_return_diff_pct=("total_return_pct_diff", "median"),
                worst_return_diff_pct=("total_return_pct_diff", "min"),
                best_return_diff_pct=("total_return_pct_diff", "max"),
                median_max_dd_diff_pct=("max_dd_percent_diff", "median"),
                worst_max_dd_diff_pct=("max_dd_percent_diff", "min"),
                median_sharpe_diff=("sharpe_ratio_diff", "median"),
                worst_sharpe_diff=("sharpe_ratio_diff", "min"),
                median_slippage_diff=("total_slippage_diff", "median"),
            )
            .sort_values("horizon")
            .reset_index(drop=True)
        )
    return comparison, aggregate


def to_markdown_table(df: pd.DataFrame, columns: list[str] | None = None, max_rows: int = 40) -> str:
    if df.empty:
        return "_empty_"
    view = df[columns].copy() if columns else df.copy()
    view = view.head(max_rows)
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda value: f"{value:.4f}")
    header = "| " + " | ".join(view.columns) + " |"
    separator = "| " + " | ".join(["---"] * len(view.columns)) + " |"
    rows = ["| " + " | ".join(map(str, row)) + " |" for row in view.to_numpy()]
    return "\n".join([header, separator, *rows])


def build_report(horizon_aggregate: pd.DataFrame, comparison_aggregate: pd.DataFrame) -> str:
    return "\n".join(
        [
            "# Stage78 + fu/sn Satellite Quarterly Walk-Forward",
            "",
            "## Purpose",
            "",
            "- Verify whether adding `sn.SHFE` as a second post-signal satellite survives quarterly cold starts.",
            "- Stage78 reference rows reuse the frozen quarterly liquidity output.",
            "",
            "## Parameters",
            "",
            f"- Candidate model tag: `{CANDIDATE_MODEL_TAG}`",
            f"- Capital: `{CAPITAL:,.0f}`",
            f"- Sizing equity cap: `{SIZING_EQUITY_CAP:,.0f}`",
            f"- Base risk ratio: `{BASE_RISK_RATIO}`",
            f"- Satellite products: `{', '.join(SATELLITE_PRODUCTS)}`",
            "",
            "## Horizon Aggregate",
            "",
            to_markdown_table(
                horizon_aggregate,
                [
                    "profile_name",
                    "horizon",
                    "window_count",
                    "positive_return_count",
                    "positive_return_rate_pct",
                    "median_return_pct",
                    "worst_return_pct",
                    "worst_max_dd_percent",
                    "median_sharpe",
                    "worst_sharpe",
                ],
                max_rows=20,
            ),
            "",
            "## Candidate Difference",
            "",
            to_markdown_table(
                comparison_aggregate,
                [
                    "horizon",
                    "window_count",
                    "return_better_count",
                    "return_worse_count",
                    "drawdown_worse_count",
                    "sharpe_worse_count",
                    "median_return_diff_pct",
                    "worst_return_diff_pct",
                    "best_return_diff_pct",
                    "worst_max_dd_diff_pct",
                    "worst_sharpe_diff",
                    "median_slippage_diff",
                ],
            ),
            "",
            "## Judgement Rules",
            "",
            "- Full-cycle improvement is not enough; the candidate must not damage the short-window cold-start profile.",
            "- If 63d/126d worst windows worsen materially, `sn` stays research-only even if full-cycle improves.",
            "- If 252d and latest tail both improve while short windows remain acceptable, this becomes a promotion candidate.",
        ]
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    reference_quarter, reference_horizon = load_stage78_reference()
    candidate_quarter, candidate_horizon = run_candidate_quarterly()

    quarter_summary = pd.concat([reference_quarter, candidate_quarter], ignore_index=True)
    horizon_summary = pd.concat([reference_horizon, candidate_horizon], ignore_index=True)
    horizon_aggregate = aggregate_horizons(horizon_summary)
    comparison, comparison_aggregate = build_horizon_comparison(horizon_summary)

    quarter_summary.to_csv(QUARTER_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    horizon_summary.to_csv(HORIZON_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    horizon_aggregate.to_csv(HORIZON_AGGREGATE_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(HORIZON_COMPARISON_PATH, index=False, encoding="utf-8-sig")
    comparison_aggregate.to_csv(HORIZON_COMPARISON_AGGREGATE_PATH, index=False, encoding="utf-8-sig")

    payload = {
        "model_tag": MODEL_TAG,
        "official_version": OFFICIAL_STAGE78_VERSION,
        "official_role": OFFICIAL_STAGE78_ROLE,
        "experiment_name": EXPERIMENT_NAME,
        "base_risk_ratio": BASE_RISK_RATIO,
        "capital": CAPITAL,
        "sizing_equity_cap": SIZING_EQUITY_CAP,
        "satellite_products": list(SATELLITE_PRODUCTS),
        "horizon_aggregate": horizon_aggregate.to_dict(orient="records"),
        "comparison_aggregate": comparison_aggregate.to_dict(orient="records"),
        "outputs": {
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
    REPORT_PATH.write_text(build_report(horizon_aggregate, comparison_aggregate), encoding="utf-8")
    print(comparison_aggregate.to_string(index=False))
    print(f"[stage78-fu-sn-quarterly] report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
