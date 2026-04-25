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

from qmt_roll_official_stage78_config import (
    OFFICIAL_STAGE78_ROLE,
    OFFICIAL_STAGE78_VERSION,
    build_official_stage78_overrides,
)
from qmt_universe import END_DT, START_DT
from run_qmt_roll_backtest import run_backtest
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage78_400k_cap_ladder_quarterly_wf_v1"
OUTPUT_PREFIX: str = "qmt_roll_official_stage78_400k_cap_ladder_quarterly_walkforward"

QUARTER_SUMMARY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_quarter_summary_{MODEL_TAG}.csv"
HORIZON_SUMMARY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_summary_{MODEL_TAG}.csv"
HORIZON_AGGREGATE_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_aggregate_{MODEL_TAG}.csv"
HORIZON_COMPARISON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_comparison_{MODEL_TAG}.csv"
HORIZON_COMPARISON_AGGREGATE_PATH: Path = (
    OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_comparison_aggregate_{MODEL_TAG}.csv"
)
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

CAPITAL: float = 400_000.0
CAP_MULTIPLIERS: tuple[float, ...] = (2.5, 5.0, 7.5)
REFERENCE_MULTIPLIER: float = 2.5
TRADING_DAYS_PER_YEAR: int = 240
HORIZON_DAYS: tuple[int, ...] = (63, 126, 252)


def cap_label(multiplier: float) -> str:
    return f"cap_{f'{multiplier:g}'.replace('.', '_')}x"


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


def profile_overrides(multiplier: float) -> dict[str, Any]:
    sizing_equity_cap = CAPITAL * multiplier
    return {
        **build_official_stage78_overrides(),
        "sizing_equity_cap": sizing_equity_cap,
    }


def run_quarterly_profile(multiplier: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    profile_name = f"capital_40w_{cap_label(multiplier)}"
    sizing_equity_cap = CAPITAL * multiplier
    overrides = profile_overrides(multiplier)
    quarter_rows: list[dict[str, Any]] = []
    horizon_rows: list[dict[str, Any]] = []

    for analysis_start in quarter_starts():
        window_name = f"q{analysis_start.year}_{((analysis_start.month - 1) // 3) + 1}"
        print(
            f"[stage78-400k-cap-wf] {profile_name} / {window_name}: "
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
                "profile_name": profile_name,
                "cap_multiplier": multiplier,
                "sizing_equity_cap": sizing_equity_cap,
                "capital": CAPITAL,
                "window_name": window_name,
                "analysis_start": analysis_start.date().isoformat(),
                "analysis_end": END_DT.date().isoformat(),
                "horizon": "to_end",
                **to_end,
            }
        )

        for horizon_days in HORIZON_DAYS:
            horizon_df = analysis_df.iloc[:horizon_days].copy()
            horizon = summarize_daily_slice(horizon_df, capital=CAPITAL)
            horizon_rows.append(
                {
                    "profile_name": profile_name,
                    "cap_multiplier": multiplier,
                    "sizing_equity_cap": sizing_equity_cap,
                    "capital": CAPITAL,
                    "window_name": window_name,
                    "analysis_start": analysis_start.date().isoformat(),
                    "analysis_end": END_DT.date().isoformat(),
                    "horizon": f"{horizon_days}d",
                    "horizon_days": horizon_days,
                    "complete_horizon": int(horizon["day_count"] >= horizon_days),
                    **horizon,
                }
            )

    return pd.DataFrame(quarter_rows), pd.DataFrame(horizon_rows)


def aggregate_horizons(horizon_df: pd.DataFrame) -> pd.DataFrame:
    complete_df = horizon_df[horizon_df["complete_horizon"].astype(bool)].copy()
    if complete_df.empty:
        return pd.DataFrame()
    aggregate_df = (
        complete_df.groupby(["profile_name", "cap_multiplier", "horizon"], as_index=False)
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
        .sort_values(["horizon", "cap_multiplier"])
        .reset_index(drop=True)
    )
    aggregate_df["positive_return_rate_pct"] = (
        aggregate_df["positive_return_count"] / aggregate_df["window_count"].replace(0, np.nan) * 100.0
    ).fillna(0.0)
    return aggregate_df


def build_horizon_comparison(horizon_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    complete_df = horizon_df[horizon_df["complete_horizon"].astype(bool)].copy()
    reference_name = f"capital_40w_{cap_label(REFERENCE_MULTIPLIER)}"
    pivot_keys = ["window_name", "analysis_start", "horizon", "horizon_days"]
    value_columns = [
        "end_balance",
        "total_return_pct",
        "max_dd_percent",
        "sharpe_ratio",
        "total_slippage",
        "total_trade_count",
    ]
    reference = complete_df[complete_df["profile_name"] == reference_name][pivot_keys + value_columns].copy()
    comparisons: list[pd.DataFrame] = []
    for multiplier in CAP_MULTIPLIERS:
        profile_name = f"capital_40w_{cap_label(multiplier)}"
        if profile_name == reference_name:
            continue
        candidate = complete_df[complete_df["profile_name"] == profile_name][pivot_keys + value_columns].copy()
        merged = reference.merge(candidate, on=pivot_keys, suffixes=("_reference", "_candidate"), how="inner")
        merged["candidate_profile_name"] = profile_name
        merged["candidate_cap_multiplier"] = multiplier
        for column in value_columns:
            merged[f"{column}_diff"] = merged[f"{column}_candidate"] - merged[f"{column}_reference"]
        merged["candidate_return_better"] = (merged["total_return_pct_diff"] > 1e-9).astype(int)
        merged["candidate_return_worse"] = (merged["total_return_pct_diff"] < -1e-9).astype(int)
        merged["candidate_drawdown_worse"] = (merged["max_dd_percent_diff"] < -1e-9).astype(int)
        merged["candidate_sharpe_worse"] = (merged["sharpe_ratio_diff"] < -1e-9).astype(int)
        comparisons.append(merged)

    comparison = pd.concat(comparisons, ignore_index=True) if comparisons else pd.DataFrame()
    if comparison.empty:
        return comparison, pd.DataFrame()
    aggregate = (
        comparison.groupby(["candidate_profile_name", "candidate_cap_multiplier", "horizon"], as_index=False)
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
        .sort_values(["horizon", "candidate_cap_multiplier"])
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
            "# Stage78 400k Cap Ladder Quarterly Walk-Forward",
            "",
            "## Purpose",
            "",
            "- Validate whether 400,000 capital should use a higher sizing cap than the fixed 1,000,000 reference.",
            "- Only three structural cap levels are tested: 2.5x, 5x, 7.5x.",
            "",
            "## Parameters",
            "",
            f"- Capital: `{CAPITAL:,.0f}`",
            f"- Base risk ratio: `{BASE_RISK_RATIO}`",
            f"- Cap multipliers: `{', '.join(cap_label(value) for value in CAP_MULTIPLIERS)}`",
            f"- Reference: `{cap_label(REFERENCE_MULTIPLIER)}`",
            f"- Horizons: `{', '.join(f'{value}d' for value in HORIZON_DAYS)}`",
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
            "## Difference Versus 2.5x",
            "",
            to_markdown_table(
                comparison_aggregate,
                [
                    "candidate_profile_name",
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
                max_rows=20,
            ),
            "",
            "## Judgement Rules",
            "",
            "- A higher cap must improve complete quarterly windows, not just full-cycle compounding.",
            "- If higher cap worsens worst return, drawdown, or Sharpe across horizons, keep the fixed 1,000,000 cap for 400,000 capital.",
            "- If 5x improves median and worst return without more tail damage, it can become a 400k research candidate.",
        ]
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    quarter_frames: list[pd.DataFrame] = []
    horizon_frames: list[pd.DataFrame] = []
    for multiplier in CAP_MULTIPLIERS:
        quarter_df, horizon_df = run_quarterly_profile(multiplier)
        quarter_frames.append(quarter_df)
        horizon_frames.append(horizon_df)

    quarter_summary = pd.concat(quarter_frames, ignore_index=True)
    horizon_summary = pd.concat(horizon_frames, ignore_index=True)
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
        "base_risk_ratio": BASE_RISK_RATIO,
        "capital": CAPITAL,
        "cap_multipliers": list(CAP_MULTIPLIERS),
        "reference_multiplier": REFERENCE_MULTIPLIER,
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
    print(f"[stage78-400k-cap-wf] report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
