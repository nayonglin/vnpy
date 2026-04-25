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

from analyze_qmt_roll_stage105_margin_constraint_surface import (
    MARGIN_EXTREME_BALANCE_PCT,
    MARGIN_REJECT_BALANCE_PCT,
    _calculate_daily_risk,
    _calculate_margin_path,
    _to_markdown_table,
)
from qmt_roll_stage111_400k_margin_safe_config import STAGE111_MARGIN_PROFILE, build_stage111_overrides
from qmt_universe import END_DT, START_DT
from run_qmt_alignment_backtest import build_positions_df
from run_qmt_roll_backtest import run_backtest
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage114_stage111_200k_granularity_quarterly_wf_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage111_200k_granularity_quarterly_walkforward"
CAPITAL: float = 200_000.0
TRADING_DAYS_PER_YEAR: int = 240
HORIZON_DAYS: tuple[int, ...] = (63, 126, 252)
THRESHOLD_PCT: float = 20.0
UNIVERSE_PATH: Path = (
    OUTPUT_DIR
    / "qmt_roll_stage111_200k_contract_granularity_filter_universe_threshold_20p0_"
    "stage113_stage111_200k_contract_granularity_filter_v1.csv"
)

QUARTER_SUMMARY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_quarter_summary_{MODEL_TAG}.csv"
HORIZON_SUMMARY_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_summary_{MODEL_TAG}.csv"
HORIZON_AGGREGATE_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_horizon_aggregate_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def quarter_starts() -> list[datetime]:
    starts = pd.date_range(START_DT, END_DT, freq="QS")
    if not starts.empty and starts[0].to_pydatetime() != START_DT:
        starts = pd.DatetimeIndex([pd.Timestamp(START_DT), *starts])
    return [ts.to_pydatetime() for ts in starts if ts.to_pydatetime() <= END_DT]


def _window_name(analysis_start: datetime) -> str:
    return f"q{analysis_start.year}_{((analysis_start.month - 1) // 3) + 1}"


def _run_window(analysis_start: datetime) -> tuple[pd.DataFrame, pd.DataFrame]:
    overrides = build_stage111_overrides()
    overrides["product_universe_csv_path"] = str(UNIVERSE_PATH)
    window = _window_name(analysis_start)
    print(f"[stage111-200k-granularity-quarterly] {window}: {analysis_start.date()} -> {END_DT.date()}", flush=True)
    log_buffer = StringIO()
    try:
        with redirect_stdout(log_buffer), redirect_stderr(log_buffer):
            engine, analysis_df, _ = run_backtest(
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

    daily = analysis_df.copy() if analysis_df is not None else pd.DataFrame()
    if not daily.empty:
        daily.sort_index(inplace=True)
    positions = build_positions_df(engine)
    return daily, positions


def _summarize_slice(daily_slice: pd.DataFrame, margin_slice: pd.DataFrame) -> dict[str, float]:
    if daily_slice.empty:
        return {
            "end_balance": 0.0,
            "total_return_pct": 0.0,
            "max_dd_percent": 0.0,
            "sharpe_ratio": 0.0,
            "total_slippage": 0.0,
            "total_trade_count": 0.0,
            "day_count": 0.0,
            "max_margin_to_balance_pct": 0.0,
            "margin_days_gt_80pct": 0.0,
            "margin_days_gt_100pct": 0.0,
            "worst_5d_pct_capital": 0.0,
            "worst_20d_pct_capital": 0.0,
        }

    balance = pd.to_numeric(daily_slice["balance"], errors="coerce").ffill().fillna(CAPITAL)
    net_pnl = pd.to_numeric(daily_slice.get("net_pnl", pd.Series(0.0, index=daily_slice.index)), errors="coerce").fillna(0.0)
    previous_balance = balance.shift(1).fillna(CAPITAL).replace(0.0, np.nan)
    daily_return = (net_pnl / previous_balance).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    high_water = balance.cummax()
    dd_pct = (balance / high_water.replace(0.0, np.nan) - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0) * 100.0
    std = float(daily_return.std(ddof=1))
    sharpe = float(daily_return.mean() / std * math.sqrt(TRADING_DAYS_PER_YEAR)) if std > 1e-12 else 0.0
    end_balance = float(balance.iloc[-1])

    max_margin = 0.0
    margin_days_gt_80 = 0
    margin_days_gt_100 = 0
    if not margin_slice.empty:
        margin_to_balance = pd.to_numeric(margin_slice["total_margin_to_balance_pct"], errors="coerce").fillna(0.0)
        max_margin = float(margin_to_balance.max())
        margin_days_gt_80 = int((margin_to_balance > MARGIN_EXTREME_BALANCE_PCT).sum())
        margin_days_gt_100 = int((margin_to_balance > MARGIN_REJECT_BALANCE_PCT).sum())

    return {
        "end_balance": end_balance,
        "total_return_pct": (end_balance - CAPITAL) / CAPITAL * 100.0,
        "max_dd_percent": float(dd_pct.min()),
        "sharpe_ratio": sharpe,
        "total_slippage": float(pd.to_numeric(daily_slice.get("slippage", 0.0), errors="coerce").fillna(0.0).sum()),
        "total_trade_count": float(pd.to_numeric(daily_slice.get("trade_count", 0.0), errors="coerce").fillna(0.0).sum()),
        "day_count": float(len(daily_slice)),
        "max_margin_to_balance_pct": max_margin,
        "margin_days_gt_80pct": float(margin_days_gt_80),
        "margin_days_gt_100pct": float(margin_days_gt_100),
        "worst_5d_pct_capital": float(net_pnl.rolling(5, min_periods=1).sum().min() / CAPITAL * 100.0),
        "worst_20d_pct_capital": float(net_pnl.rolling(20, min_periods=1).sum().min() / CAPITAL * 100.0),
    }


def _summarize_window(analysis_start: datetime, daily: pd.DataFrame, positions: pd.DataFrame) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    daily_risk = _calculate_daily_risk(daily, CAPITAL)
    daily_margin, _ = _calculate_margin_path(positions, daily_risk, capital=CAPITAL)
    window = _window_name(analysis_start)
    base_fields = {
        "model_tag": MODEL_TAG,
        "profile_name": "stage111_200k_single_margin_le_20pct",
        "capital": CAPITAL,
        "threshold_pct": THRESHOLD_PCT,
        "base_risk_ratio": BASE_RISK_RATIO,
        "max_capital_usage_ratio": STAGE111_MARGIN_PROFILE["max_capital_usage_ratio"],
        "max_single_trade_capital_usage_ratio": STAGE111_MARGIN_PROFILE["max_single_trade_capital_usage_ratio"],
        "window_name": window,
        "analysis_start": analysis_start.date().isoformat(),
        "analysis_end": END_DT.date().isoformat(),
    }
    quarter_row = {**base_fields, "horizon": "to_end", **_summarize_slice(daily, daily_margin)}
    horizon_rows: list[dict[str, Any]] = []
    for horizon_days in HORIZON_DAYS:
        daily_slice = daily.iloc[:horizon_days].copy()
        if daily_slice.empty:
            margin_slice = daily_margin.iloc[:0].copy()
        else:
            slice_dates = pd.to_datetime(daily_slice.index).normalize()
            margin_slice = daily_margin[daily_margin["date"].isin(slice_dates)].copy()
        horizon = _summarize_slice(daily_slice, margin_slice)
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
            max_margin_to_balance_pct=("max_margin_to_balance_pct", "max"),
            windows_margin_gt_80pct=("margin_days_gt_80pct", lambda s: int((s > 0).sum())),
            windows_margin_gt_100pct=("margin_days_gt_100pct", lambda s: int((s > 0).sum())),
            worst_5d_pct_capital=("worst_5d_pct_capital", "min"),
            worst_20d_pct_capital=("worst_20d_pct_capital", "min"),
            median_trade_count=("total_trade_count", "median"),
        )
        .sort_values(["horizon", "profile_name"])
        .reset_index(drop=True)
    )
    aggregate["positive_return_rate_pct"] = (
        aggregate["positive_return_count"] / aggregate["window_count"].replace(0, np.nan) * 100.0
    ).fillna(0.0)
    return aggregate


def _build_report(horizon_aggregate: pd.DataFrame) -> str:
    columns = [
        "profile_name",
        "horizon",
        "window_count",
        "positive_return_rate_pct",
        "worst_return_pct",
        "median_return_pct",
        "worst_max_dd_percent",
        "median_sharpe",
        "max_margin_to_balance_pct",
        "windows_margin_gt_80pct",
        "windows_margin_gt_100pct",
        "worst_5d_pct_capital",
        "worst_20d_pct_capital",
    ]
    return "\n".join(
        [
            "# Stage111 200k Granularity Quarterly Walkforward",
            "",
            "## Boundary",
            "",
            "- This validates the Stage113 20% single-contract margin filter.",
            "- Stage111 trading rules and capital ratios are unchanged.",
            "- Every quarter is treated as a cold-start point.",
            "",
            "## Horizon Aggregate",
            "",
            _to_markdown_table(horizon_aggregate, columns, max_rows=20),
            "",
            "## Judgement",
            "",
            "- A full-window result is not enough; this table decides whether the granularity-filtered 200k profile deserves a formal config.",
            "- If all complete horizons have zero >80% and >100% margin windows, margin is no longer the blocker.",
        ]
    )


def main() -> None:
    if not UNIVERSE_PATH.exists():
        raise FileNotFoundError(UNIVERSE_PATH)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    quarter_rows: list[dict[str, Any]] = []
    horizon_rows: list[dict[str, Any]] = []
    starts = quarter_starts()
    for analysis_start in starts:
        daily, positions = _run_window(analysis_start)
        quarter_row, rows = _summarize_window(analysis_start, daily, positions)
        quarter_rows.append(quarter_row)
        horizon_rows.extend(rows)
        print(
            f"[stage111-200k-granularity-quarterly] {_window_name(analysis_start)} done: "
            f"to_end_return={quarter_row['total_return_pct']:.4f}%, "
            f"max_margin={quarter_row['max_margin_to_balance_pct']:.4f}%",
            flush=True,
        )

    quarter_df = pd.DataFrame(quarter_rows)
    horizon_df = pd.DataFrame(horizon_rows)
    horizon_aggregate = _aggregate_horizons(horizon_df)
    quarter_df.to_csv(QUARTER_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    horizon_df.to_csv(HORIZON_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    horizon_aggregate.to_csv(HORIZON_AGGREGATE_PATH, index=False, encoding="utf-8-sig")
    SUMMARY_JSON_PATH.write_text(
        json.dumps(
            {
                "model_tag": MODEL_TAG,
                "capital": CAPITAL,
                "threshold_pct": THRESHOLD_PCT,
                "quarter_count": len(starts),
                "horizon_days": HORIZON_DAYS,
                "horizon_aggregate": horizon_aggregate.to_dict(orient="records"),
                "outputs": {
                    "quarter_summary": str(QUARTER_SUMMARY_PATH),
                    "horizon_summary": str(HORIZON_SUMMARY_PATH),
                    "horizon_aggregate": str(HORIZON_AGGREGATE_PATH),
                    "summary_json": str(SUMMARY_JSON_PATH),
                    "report": str(REPORT_PATH),
                },
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    REPORT_PATH.write_text(_build_report(horizon_aggregate), encoding="utf-8")
    print(json.dumps(horizon_aggregate.to_dict(orient="records"), ensure_ascii=False, indent=2, default=str))
    print(f"[stage111-200k-granularity-quarterly] report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
