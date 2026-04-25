from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from qmt_roll_official_stage78_config import (
    OFFICIAL_STAGE78_CAPITAL,
    OFFICIAL_STAGE78_ROLE,
    OFFICIAL_STAGE78_VERSION,
    build_official_stage78_overrides,
)
from qmt_universe import END_DT, START_DT
from run_qmt_roll_backtest import run_backtest
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage78_sizing_cap_quarterly_wf_v1"
OUTPUT_PREFIX: str = "qmt_roll_official_stage78_sizing_cap_quarterly_walkforward"

QUARTER_SUMMARY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_quarter_summary_{MODEL_TAG}.csv"
HORIZON_SUMMARY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_summary_{MODEL_TAG}.csv"
HORIZON_AGGREGATE_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_aggregate_{MODEL_TAG}.csv"
HORIZON_COMPARISON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_comparison_{MODEL_TAG}.csv"
HORIZON_COMPARISON_AGGREGATE_PATH: Path = (
    OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_comparison_aggregate_{MODEL_TAG}.csv"
)
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

CAPPED_QUARTER_REFERENCE_PATH: Path = (
    OUTPUT_DIR
    / "qmt_roll_official_stage78_defensive_quarterly_walkforward_liquidity_quarter_summary_quarterly_wf_liquidity_v1.csv"
)
CAPPED_HORIZON_REFERENCE_PATH: Path = (
    OUTPUT_DIR
    / "qmt_roll_official_stage78_defensive_quarterly_walkforward_liquidity_horizon_summary_quarterly_wf_liquidity_v1.csv"
)

PROFILE_CAPPED: str = "stage78_capped_1m"
PROFILE_NO_CAP: str = "stage78_sizing_cap_off"
DEFAULT_SIZING_EQUITY_CAP: float = 1_000_000.0
DISABLED_SIZING_EQUITY_CAP: float = 0.0

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
        [np.inf, -np.inf], np.nan
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


def profile_overrides(sizing_equity_cap: float) -> dict[str, Any]:
    return {
        **build_official_stage78_overrides(),
        "sizing_equity_cap": sizing_equity_cap,
    }


def run_quarterly_profile(profile_name: str, sizing_equity_cap: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    quarter_rows: list[dict[str, Any]] = []
    horizon_rows: list[dict[str, Any]] = []
    overrides = profile_overrides(sizing_equity_cap)

    for analysis_start in quarter_starts():
        window_name = f"q{analysis_start.year}_{((analysis_start.month - 1) // 3) + 1}"
        print(
            f"[stage78-sizing-cap-quarterly] {window_name} / {profile_name}: "
            f"{analysis_start.date()} -> {END_DT.date()}"
        )
        _, analysis_df, _ = run_backtest(
            risk_ratio=BASE_RISK_RATIO,
            strategy_overrides=overrides,
            analysis_start=analysis_start,
            analysis_end=END_DT,
            capital=OFFICIAL_STAGE78_CAPITAL,
            save_artifacts=False,
            include_start_year_sweep=False,
        )
        if analysis_df is None:
            analysis_df = pd.DataFrame()
        analysis_df = analysis_df.copy()
        if not analysis_df.empty:
            analysis_df.sort_index(inplace=True)

        to_end = summarize_daily_slice(analysis_df, capital=OFFICIAL_STAGE78_CAPITAL)
        quarter_rows.append(
            {
                "profile_name": profile_name,
                "sizing_equity_cap": sizing_equity_cap,
                "window_name": window_name,
                "analysis_start": analysis_start.date().isoformat(),
                "analysis_end": END_DT.date().isoformat(),
                "horizon": "to_end",
                **to_end,
            }
        )

        for horizon_days in HORIZON_DAYS:
            horizon_df = analysis_df.iloc[:horizon_days].copy()
            horizon = summarize_daily_slice(horizon_df, capital=OFFICIAL_STAGE78_CAPITAL)
            horizon_rows.append(
                {
                    "profile_name": profile_name,
                    "sizing_equity_cap": sizing_equity_cap,
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


def load_capped_reference() -> tuple[pd.DataFrame, pd.DataFrame]:
    if not CAPPED_QUARTER_REFERENCE_PATH.exists() or not CAPPED_HORIZON_REFERENCE_PATH.exists():
        return run_quarterly_profile(PROFILE_CAPPED, DEFAULT_SIZING_EQUITY_CAP)

    quarter_df = pd.read_csv(CAPPED_QUARTER_REFERENCE_PATH)
    horizon_df = pd.read_csv(CAPPED_HORIZON_REFERENCE_PATH)
    quarter_df.insert(0, "sizing_equity_cap", DEFAULT_SIZING_EQUITY_CAP)
    quarter_df.insert(0, "profile_name", PROFILE_CAPPED)
    horizon_df.insert(0, "sizing_equity_cap", DEFAULT_SIZING_EQUITY_CAP)
    horizon_df.insert(0, "profile_name", PROFILE_CAPPED)
    return quarter_df, horizon_df


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

    capped = complete_df[complete_df["profile_name"] == PROFILE_CAPPED][pivot_keys + value_columns].copy()
    no_cap = complete_df[complete_df["profile_name"] == PROFILE_NO_CAP][pivot_keys + value_columns].copy()
    comparison = capped.merge(no_cap, on=pivot_keys, suffixes=("_capped", "_no_cap"), how="inner")
    for column in value_columns:
        comparison[f"{column}_diff"] = comparison[f"{column}_no_cap"] - comparison[f"{column}_capped"]

    comparison["no_cap_return_better"] = (comparison["total_return_pct_diff"] > 1e-9).astype(int)
    comparison["no_cap_return_worse"] = (comparison["total_return_pct_diff"] < -1e-9).astype(int)
    comparison["no_cap_drawdown_worse"] = (comparison["max_dd_percent_diff"] < -1e-9).astype(int)
    comparison["no_cap_sharpe_worse"] = (comparison["sharpe_ratio_diff"] < -1e-9).astype(int)
    comparison["no_cap_changed"] = (
        comparison[["end_balance_diff", "max_dd_percent_diff", "sharpe_ratio_diff"]].abs().sum(axis=1) > 1e-9
    ).astype(int)

    if comparison.empty:
        aggregate = pd.DataFrame()
    else:
        aggregate = (
            comparison.groupby("horizon", as_index=False)
            .agg(
                window_count=("window_name", "count"),
                changed_count=("no_cap_changed", "sum"),
                no_cap_return_better_count=("no_cap_return_better", "sum"),
                no_cap_return_worse_count=("no_cap_return_worse", "sum"),
                no_cap_drawdown_worse_count=("no_cap_drawdown_worse", "sum"),
                no_cap_sharpe_worse_count=("no_cap_sharpe_worse", "sum"),
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


def to_markdown_table(df: pd.DataFrame, columns: list[str] | None = None, max_rows: int = 30) -> str:
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


def build_report(
    horizon_aggregate: pd.DataFrame,
    comparison_aggregate: pd.DataFrame,
    comparison: pd.DataFrame,
) -> str:
    changed = comparison[comparison["no_cap_changed"].astype(bool)].copy() if not comparison.empty else pd.DataFrame()
    worst_no_cap = (
        comparison.sort_values("total_return_pct_no_cap").head(12) if not comparison.empty else pd.DataFrame()
    )
    return "\n".join(
        [
            f"# {OFFICIAL_STAGE78_VERSION} Sizing Cap Quarterly Walk-Forward",
            "",
            "## Purpose",
            "",
            "- Test whether disabling the 1,000,000 sizing-equity cap improves quarterly cold starts.",
            "- Capped rows reuse the Stage78 quarterly reference if available; no-cap rows are freshly backtested.",
            "",
            "## Parameters",
            "",
            f"- Capital: `{OFFICIAL_STAGE78_CAPITAL:,.0f}`",
            f"- Base risk ratio: `{BASE_RISK_RATIO}`",
            f"- Capped sizing equity cap: `{DEFAULT_SIZING_EQUITY_CAP:,.0f}`",
            f"- No-cap sizing equity cap: `{DISABLED_SIZING_EQUITY_CAP:,.0f}`",
            f"- Official role: `{OFFICIAL_STAGE78_ROLE}`",
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
            ),
            "",
            "## No-Cap Difference Aggregate",
            "",
            to_markdown_table(
                comparison_aggregate,
                [
                    "horizon",
                    "window_count",
                    "changed_count",
                    "no_cap_return_better_count",
                    "no_cap_return_worse_count",
                    "no_cap_drawdown_worse_count",
                    "no_cap_sharpe_worse_count",
                    "median_return_diff_pct",
                    "worst_return_diff_pct",
                    "best_return_diff_pct",
                    "worst_max_dd_diff_pct",
                    "worst_sharpe_diff",
                    "median_slippage_diff",
                ],
            ),
            "",
            "## Changed Windows",
            "",
            to_markdown_table(
                changed.sort_values(["horizon_days", "analysis_start"]),
                [
                    "window_name",
                    "analysis_start",
                    "horizon",
                    "end_balance_capped",
                    "end_balance_no_cap",
                    "total_return_pct_diff",
                    "max_dd_percent_diff",
                    "sharpe_ratio_diff",
                    "total_slippage_diff",
                ],
                max_rows=30,
            ),
            "",
            "## Worst No-Cap Windows",
            "",
            to_markdown_table(
                worst_no_cap,
                [
                    "window_name",
                    "analysis_start",
                    "horizon",
                    "end_balance_no_cap",
                    "total_return_pct_no_cap",
                    "max_dd_percent_no_cap",
                    "sharpe_ratio_no_cap",
                    "total_return_pct_diff",
                ],
                max_rows=12,
            ),
            "",
            "## Judgement Rules",
            "",
            "- Full-cycle compounding is not enough; quarterly cold starts must also improve.",
            "- If no-cap only changes windows after equity already compounds above 1,000,000, it is leverage expansion, not edge improvement.",
            "- A formal promotion would require better median/worst return without worse drawdown and Sharpe.",
        ]
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    capped_quarter, capped_horizon = load_capped_reference()
    no_cap_quarter, no_cap_horizon = run_quarterly_profile(PROFILE_NO_CAP, DISABLED_SIZING_EQUITY_CAP)

    quarter_summary = pd.concat([capped_quarter, no_cap_quarter], ignore_index=True)
    horizon_summary = pd.concat([capped_horizon, no_cap_horizon], ignore_index=True)
    horizon_aggregate = aggregate_horizons(horizon_summary)
    horizon_comparison, horizon_comparison_aggregate = build_horizon_comparison(horizon_summary)

    quarter_summary.to_csv(QUARTER_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    horizon_summary.to_csv(HORIZON_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    horizon_aggregate.to_csv(HORIZON_AGGREGATE_PATH, index=False, encoding="utf-8-sig")
    horizon_comparison.to_csv(HORIZON_COMPARISON_PATH, index=False, encoding="utf-8-sig")
    horizon_comparison_aggregate.to_csv(HORIZON_COMPARISON_AGGREGATE_PATH, index=False, encoding="utf-8-sig")

    payload = {
        "model_tag": MODEL_TAG,
        "official_version": OFFICIAL_STAGE78_VERSION,
        "official_role": OFFICIAL_STAGE78_ROLE,
        "base_risk_ratio": BASE_RISK_RATIO,
        "capital": OFFICIAL_STAGE78_CAPITAL,
        "capped_reference_path": str(CAPPED_HORIZON_REFERENCE_PATH),
        "horizon_aggregate": horizon_aggregate.to_dict(orient="records"),
        "horizon_comparison_aggregate": horizon_comparison_aggregate.to_dict(orient="records"),
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
    REPORT_PATH.write_text(
        build_report(horizon_aggregate, horizon_comparison_aggregate, horizon_comparison),
        encoding="utf-8",
    )

    print(horizon_comparison_aggregate.to_string(index=False))
    print(f"[stage78-sizing-cap-quarterly] report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
