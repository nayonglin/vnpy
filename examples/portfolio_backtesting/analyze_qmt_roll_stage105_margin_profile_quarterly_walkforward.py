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
    CAPITAL,
    MARGIN_EXTREME_BALANCE_PCT,
    MARGIN_REJECT_BALANCE_PCT,
    MARGIN_WARN_BALANCE_PCT,
    MarginProfile,
    _calculate_daily_risk,
    _calculate_margin_path,
    _safe_float,
    _to_markdown_table,
)
from qmt_roll_stage105_fu_sn_config import (
    STAGE105_ROLE,
    STAGE105_SIZING_EQUITY_CAP,
    STAGE105_VERSION,
    build_stage105_overrides,
)
from qmt_universe import END_DT, START_DT
from run_qmt_alignment_backtest import build_positions_df
from run_qmt_roll_backtest import run_backtest
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage110_margin_profile_quarterly_wf_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage105_margin_profile_quarterly_walkforward"
TRADING_DAYS_PER_YEAR: int = 240
HORIZON_DAYS: tuple[int, ...] = (63, 126, 252)

PROFILES: tuple[MarginProfile, ...] = (
    MarginProfile("cap60_single30", 0.60, 0.30),
    MarginProfile("cap45_single20", 0.45, 0.20),
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


def _run_window(profile: MarginProfile, analysis_start: datetime) -> tuple[pd.DataFrame, pd.DataFrame]:
    overrides = build_stage105_overrides()
    overrides.update(
        {
            "max_capital_usage_ratio": profile.max_capital_usage_ratio,
            "max_single_trade_capital_usage_ratio": profile.max_single_trade_capital_usage_ratio,
        }
    )

    print(
        f"[stage105-margin-quarterly] {profile.profile_name} / {_window_name(analysis_start)}: "
        f"{analysis_start.date()} -> {END_DT.date()}",
        flush=True,
    )
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


def _summarize_slice(
    daily_slice: pd.DataFrame,
    margin_slice: pd.DataFrame,
    *,
    capital: float,
) -> dict[str, float]:
    if daily_slice.empty:
        return {
            "end_balance": 0.0,
            "total_return_pct": 0.0,
            "max_dd_percent": 0.0,
            "sharpe_ratio": 0.0,
            "total_slippage": 0.0,
            "total_trade_count": 0.0,
            "day_count": 0.0,
            "max_total_margin_to_balance_pct": 0.0,
            "max_total_margin_to_initial_capital_pct": 0.0,
            "warn_margin_days_gt_60pct": 0.0,
            "extreme_margin_days_gt_80pct": 0.0,
            "reject_margin_days_gt_100pct": 0.0,
            "worst_daily_pct_prev_balance": 0.0,
            "worst_5d_pct_capital": 0.0,
            "worst_20d_pct_capital": 0.0,
        }

    balance = pd.to_numeric(daily_slice["balance"], errors="coerce").ffill().fillna(capital)
    net_pnl = pd.to_numeric(daily_slice.get("net_pnl", pd.Series(0.0, index=daily_slice.index)), errors="coerce").fillna(0.0)
    previous_balance = balance.shift(1).fillna(capital).replace(0.0, np.nan)
    daily_return = (net_pnl / previous_balance).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    high_water = balance.cummax()
    dd_pct = (balance / high_water.replace(0.0, np.nan) - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0) * 100.0
    std = float(daily_return.std(ddof=1))
    sharpe = float(daily_return.mean() / std * math.sqrt(TRADING_DAYS_PER_YEAR)) if std > 1e-12 else 0.0
    end_balance = float(balance.iloc[-1])

    daily_loss_pct = (net_pnl / previous_balance * 100.0).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    rolling_5d = net_pnl.rolling(5, min_periods=1).sum() / capital * 100.0
    rolling_20d = net_pnl.rolling(20, min_periods=1).sum() / capital * 100.0

    max_margin_to_balance = 0.0
    max_margin_to_initial = 0.0
    warn_days = 0
    extreme_days = 0
    reject_days = 0
    if not margin_slice.empty:
        margin_to_balance = pd.to_numeric(
            margin_slice["total_margin_to_balance_pct"],
            errors="coerce",
        ).fillna(0.0)
        margin_to_initial = pd.to_numeric(
            margin_slice["total_margin_to_initial_capital_pct"],
            errors="coerce",
        ).fillna(0.0)
        max_margin_to_balance = float(margin_to_balance.max())
        max_margin_to_initial = float(margin_to_initial.max())
        warn_days = int((margin_to_balance > MARGIN_WARN_BALANCE_PCT).sum())
        extreme_days = int((margin_to_balance > MARGIN_EXTREME_BALANCE_PCT).sum())
        reject_days = int((margin_to_balance > MARGIN_REJECT_BALANCE_PCT).sum())

    return {
        "end_balance": end_balance,
        "total_return_pct": (end_balance - capital) / capital * 100.0,
        "max_dd_percent": float(dd_pct.min()),
        "sharpe_ratio": sharpe,
        "total_slippage": float(pd.to_numeric(daily_slice.get("slippage", 0.0), errors="coerce").fillna(0.0).sum()),
        "total_trade_count": float(pd.to_numeric(daily_slice.get("trade_count", 0.0), errors="coerce").fillna(0.0).sum()),
        "day_count": float(len(daily_slice)),
        "max_total_margin_to_balance_pct": max_margin_to_balance,
        "max_total_margin_to_initial_capital_pct": max_margin_to_initial,
        "warn_margin_days_gt_60pct": float(warn_days),
        "extreme_margin_days_gt_80pct": float(extreme_days),
        "reject_margin_days_gt_100pct": float(reject_days),
        "worst_daily_pct_prev_balance": float(daily_loss_pct.min()),
        "worst_5d_pct_capital": float(rolling_5d.min()),
        "worst_20d_pct_capital": float(rolling_20d.min()),
    }


def _summarize_window(
    profile: MarginProfile,
    analysis_start: datetime,
    daily: pd.DataFrame,
    positions: pd.DataFrame,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    daily_risk = _calculate_daily_risk(daily, CAPITAL)
    daily_margin, _ = _calculate_margin_path(positions, daily_risk, capital=CAPITAL)
    window = _window_name(analysis_start)

    quarter_row = {
        "model_tag": MODEL_TAG,
        "version": STAGE105_VERSION,
        "role": STAGE105_ROLE,
        "profile_name": profile.profile_name,
        "capital": CAPITAL,
        "sizing_equity_cap": STAGE105_SIZING_EQUITY_CAP,
        "base_risk_ratio": BASE_RISK_RATIO,
        "max_capital_usage_ratio": profile.max_capital_usage_ratio,
        "max_single_trade_capital_usage_ratio": profile.max_single_trade_capital_usage_ratio,
        "window_name": window,
        "analysis_start": analysis_start.date().isoformat(),
        "analysis_end": END_DT.date().isoformat(),
        "horizon": "to_end",
        **_summarize_slice(daily, daily_margin, capital=CAPITAL),
    }

    horizon_rows: list[dict[str, Any]] = []
    for horizon_days in HORIZON_DAYS:
        daily_slice = daily.iloc[:horizon_days].copy()
        if daily_slice.empty:
            margin_slice = daily_margin.iloc[:0].copy()
        else:
            slice_dates = pd.to_datetime(daily_slice.index).normalize()
            margin_slice = daily_margin[daily_margin["date"].isin(slice_dates)].copy()
        horizon = _summarize_slice(daily_slice, margin_slice, capital=CAPITAL)
        horizon_rows.append(
            {
                "model_tag": MODEL_TAG,
                "version": STAGE105_VERSION,
                "role": STAGE105_ROLE,
                "profile_name": profile.profile_name,
                "capital": CAPITAL,
                "sizing_equity_cap": STAGE105_SIZING_EQUITY_CAP,
                "base_risk_ratio": BASE_RISK_RATIO,
                "max_capital_usage_ratio": profile.max_capital_usage_ratio,
                "max_single_trade_capital_usage_ratio": profile.max_single_trade_capital_usage_ratio,
                "window_name": window,
                "analysis_start": analysis_start.date().isoformat(),
                "analysis_end": END_DT.date().isoformat(),
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
            max_margin_to_balance_pct=("max_total_margin_to_balance_pct", "max"),
            windows_margin_gt_80pct=("extreme_margin_days_gt_80pct", lambda s: int((s > 0).sum())),
            windows_margin_gt_100pct=("reject_margin_days_gt_100pct", lambda s: int((s > 0).sum())),
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


def _build_report(quarter_df: pd.DataFrame, horizon_aggregate: pd.DataFrame) -> str:
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
        "worst_20d_pct_capital",
    ]

    to_end_columns = [
        "profile_name",
        "window_name",
        "analysis_start",
        "total_return_pct",
        "max_dd_percent",
        "sharpe_ratio",
        "max_total_margin_to_balance_pct",
        "extreme_margin_days_gt_80pct",
        "reject_margin_days_gt_100pct",
    ]
    worst_to_end = (
        quarter_df.sort_values(["profile_name", "total_return_pct"], ascending=[True, True])
        .groupby("profile_name", as_index=False)
        .head(5)
    )

    judgement_lines: list[str] = []
    for profile_name in sorted(horizon_aggregate["profile_name"].unique()):
        profile = horizon_aggregate[horizon_aggregate["profile_name"] == profile_name]
        margin_breaks = int(profile["windows_margin_gt_100pct"].sum())
        extreme_breaks = int(profile["windows_margin_gt_80pct"].sum())
        worst_return = float(profile["worst_return_pct"].min())
        if margin_breaks > 0:
            judgement_lines.append(f"- `{profile_name}` fails: at least one complete horizon has margin / balance > 100%.")
        elif extreme_breaks > 0:
            judgement_lines.append(f"- `{profile_name}` is only watch-list: margin / balance exceeds 80% in some complete horizons.")
        elif worst_return <= -30:
            judgement_lines.append(
                f"- `{profile_name}` passes margin but remains path-risk heavy: worst complete-horizon return is `{worst_return:.4f}%`."
            )
        else:
            judgement_lines.append(f"- `{profile_name}` passes the margin gate and has no deep negative complete-horizon return.")

    return "\n".join(
        [
            "# Stage105 Margin Profile Quarterly Walkforward",
            "",
            "## Boundary",
            "",
            "- Validate only two candidates from the Stage109 capital surface.",
            "- Every quarter is treated as a cold-start point and tested to end plus 63/126/252 trading-day horizons.",
            "- This is validation, not a new parameter search.",
            "",
            "## Horizon Aggregate",
            "",
            _to_markdown_table(horizon_aggregate, columns, max_rows=20),
            "",
            "## Worst To-End Windows",
            "",
            _to_markdown_table(worst_to_end, to_end_columns, max_rows=10),
            "",
            "## Judgement",
            "",
            *judgement_lines,
            "- A deployable formal profile should prefer stable margin/path behavior over maximum full-cycle return.",
        ]
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    quarter_rows: list[dict[str, Any]] = []
    horizon_rows: list[dict[str, Any]] = []

    starts = quarter_starts()
    for profile in PROFILES:
        for analysis_start in starts:
            daily, positions = _run_window(profile, analysis_start)
            quarter_row, profile_horizon_rows = _summarize_window(profile, analysis_start, daily, positions)
            quarter_rows.append(quarter_row)
            horizon_rows.extend(profile_horizon_rows)
            print(
                f"[stage105-margin-quarterly] {profile.profile_name} / {_window_name(analysis_start)} done: "
                f"to_end_return={quarter_row['total_return_pct']:.4f}%, "
                f"max_margin/balance={quarter_row['max_total_margin_to_balance_pct']:.4f}%",
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
                "version": STAGE105_VERSION,
                "capital": CAPITAL,
                "profiles": [profile.__dict__ for profile in PROFILES],
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
    REPORT_PATH.write_text(_build_report(quarter_df, horizon_aggregate), encoding="utf-8")
    print(json.dumps(horizon_aggregate.to_dict(orient="records"), ensure_ascii=False, indent=2, default=str))
    print(f"[stage105-margin-quarterly] report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
