from __future__ import annotations

import json
import math
import sys
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from analyze_qmt_roll_stage105_margin_constraint_surface import _to_markdown_table
from analyze_qmt_roll_stage129_profit_giveback_trade_attribution import (
    CANDIDATE_PARAMS,
    _add_product_column,
    _build_roundtrips,
)
from analyze_qmt_roll_stage131_profit_giveback_weak_window_attribution import _candidate_summary
from qmt_roll_official_stage78_config import (
    OFFICIAL_STAGE78_CAPITAL,
    OFFICIAL_STAGE78_VERSION,
    build_official_stage78_overrides,
)
from qmt_universe import END_DT, START_DT
from run_qmt_alignment_backtest import (
    build_entry_candidate_snapshots_df,
    build_entry_risk_diagnostics_df,
    build_positions_df,
    build_trades_df,
)
from run_qmt_roll_backtest import run_backtest
from run_qmt_roll_selection_pairwise_long015_volref30_corr_crowding_formal_backtest import BASE_RISK_RATIO


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage132_profit_giveback_streak_decouple_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage132_profit_giveback_streak_decouple"

SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COMPARISON_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
CANDIDATE_SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_candidate_summary_{MODEL_TAG}.csv"
SKIP_REASON_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_skip_reason_summary_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

PROFILE_STAGE78: str = "official_stage78_reference"
PROFILE_STAGE128: str = "stage128_giveback_normal"
PROFILE_STAGE132: str = "stage132_giveback_loss_neutral"

WEAK_WINDOW_NAME: str = "q2022_4_252d"
WEAK_WINDOW_START: datetime = datetime(2022, 10, 1)
WEAK_WINDOW_HORIZON_DAYS: int = 252
TRADING_DAYS_PER_YEAR: int = 240


@dataclass(frozen=True)
class ScopeRun:
    profile_name: str
    scope_name: str
    daily: pd.DataFrame
    positions: pd.DataFrame
    trades: pd.DataFrame
    roundtrips: pd.DataFrame
    candidates: pd.DataFrame
    entry_risk: pd.DataFrame
    statistics: dict[str, Any]
    profit_giveback_stop_update_count: int
    profit_giveback_streak_neutral_count: int
    horizon_end: pd.Timestamp


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or math.isinf(result):
        return default
    return result


def _candidate_overrides() -> dict[str, Any]:
    overrides = build_official_stage78_overrides()
    overrides.update(CANDIDATE_PARAMS)
    return overrides


def _decoupled_overrides() -> dict[str, Any]:
    overrides = _candidate_overrides()
    overrides["profit_giveback_streak_update_mode"] = "loss_neutral"
    return overrides


def _summarize_daily(daily: pd.DataFrame, capital: float) -> dict[str, float]:
    if daily.empty:
        return {
            "end_balance": 0.0,
            "total_return_pct": 0.0,
            "max_dd_percent": 0.0,
            "sharpe_ratio": 0.0,
            "total_slippage": 0.0,
            "total_trade_count": 0.0,
            "day_count": 0.0,
        }

    balance = pd.to_numeric(daily["balance"], errors="coerce").ffill().fillna(capital)
    net_pnl = pd.to_numeric(daily.get("net_pnl", pd.Series(0.0, index=daily.index)), errors="coerce").fillna(0.0)
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
        "total_slippage": float(pd.to_numeric(daily.get("slippage", 0.0), errors="coerce").fillna(0.0).sum()),
        "total_trade_count": float(pd.to_numeric(daily.get("trade_count", 0.0), errors="coerce").fillna(0.0).sum()),
        "day_count": float(len(daily)),
    }


def _filter_by_window(frame: pd.DataFrame, column: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    if frame.empty or column not in frame.columns:
        return frame.copy()
    dt = pd.to_datetime(frame[column]).dt.tz_localize(None)
    return frame[(dt >= start) & (dt <= end)].copy()


def _run_scope(
    profile_name: str,
    scope_name: str,
    strategy_overrides: dict[str, Any],
    *,
    analysis_start: datetime,
    horizon_days: int | None = None,
) -> ScopeRun:
    print(f"[stage132-profit-giveback-decouple] run {profile_name} / {scope_name}", flush=True)
    log_buffer = StringIO()
    try:
        with redirect_stdout(log_buffer), redirect_stderr(log_buffer):
            engine, analysis_df, statistics = run_backtest(
                risk_ratio=BASE_RISK_RATIO,
                strategy_overrides=strategy_overrides,
                analysis_start=analysis_start,
                analysis_end=END_DT,
                capital=OFFICIAL_STAGE78_CAPITAL,
                save_artifacts=False,
                include_start_year_sweep=False,
            )
    except Exception:
        sys.stderr.write(log_buffer.getvalue())
        raise

    strategy = getattr(engine, "strategy", None)
    daily = analysis_df.copy() if analysis_df is not None else pd.DataFrame()
    if not daily.empty:
        daily.sort_index(inplace=True)
    if horizon_days is not None and not daily.empty:
        daily = daily.iloc[:horizon_days].copy()
    horizon_end = pd.Timestamp(daily.index[-1]) if not daily.empty else pd.Timestamp(analysis_start)

    positions = _add_product_column(build_positions_df(engine), strategy)
    trades = build_trades_df(engine)
    roundtrips = _build_roundtrips(engine, trades)
    candidates = build_entry_candidate_snapshots_df(engine)
    entry_risk = build_entry_risk_diagnostics_df(engine)

    start_ts = pd.Timestamp(analysis_start)
    end_ts = horizon_end
    if horizon_days is not None:
        positions = _filter_by_window(positions, "date", start_ts, end_ts)
        trades = _filter_by_window(trades, "datetime", start_ts, end_ts)
        roundtrips = _filter_by_window(roundtrips, "exit_datetime", start_ts, end_ts)
        candidates = _filter_by_window(candidates, "datetime", start_ts, end_ts)
        entry_risk = _filter_by_window(entry_risk, "datetime", start_ts, end_ts)

    for frame in (positions, trades, roundtrips, candidates, entry_risk):
        if not frame.empty:
            frame.insert(0, "scope_name", scope_name)
            frame.insert(0, "profile_name", profile_name)

    return ScopeRun(
        profile_name=profile_name,
        scope_name=scope_name,
        daily=daily,
        positions=positions,
        trades=trades,
        roundtrips=roundtrips,
        candidates=candidates,
        entry_risk=entry_risk,
        statistics=statistics or {},
        profit_giveback_stop_update_count=int(getattr(strategy, "profit_giveback_stop_update_count", 0) if strategy else 0),
        profit_giveback_streak_neutral_count=int(
            getattr(strategy, "profit_giveback_streak_neutral_count", 0) if strategy else 0
        ),
        horizon_end=horizon_end,
    )


def _summary_row(run: ScopeRun) -> dict[str, Any]:
    if run.scope_name == "full_2020_2026":
        summary = {
            "end_balance": _safe_float(run.statistics.get("end_balance")),
            "total_return_pct": _safe_float(run.statistics.get("total_return")),
            "max_dd_percent": _safe_float(run.statistics.get("max_ddpercent")),
            "sharpe_ratio": _safe_float(run.statistics.get("sharpe_ratio")),
            "total_slippage": _safe_float(run.statistics.get("total_slippage")),
            "total_trade_count": _safe_float(run.statistics.get("total_trade_count")),
            "day_count": float(len(run.daily)),
        }
        win_ratio_pct = _safe_float(run.statistics.get("win_ratio"))
    else:
        summary = _summarize_daily(run.daily, OFFICIAL_STAGE78_CAPITAL)
        win_ratio_pct = (
            _safe_float((run.roundtrips["gross_pnl"] > 0).mean() * 100.0) if not run.roundtrips.empty else 0.0
        )

    roundtrip_gross = _safe_float(run.roundtrips["gross_pnl"].sum()) if not run.roundtrips.empty else 0.0
    return {
        "profile_name": run.profile_name,
        "scope_name": run.scope_name,
        "base_version": OFFICIAL_STAGE78_VERSION,
        "capital": OFFICIAL_STAGE78_CAPITAL,
        "analysis_start": START_DT.date().isoformat()
        if run.scope_name == "full_2020_2026"
        else WEAK_WINDOW_START.date().isoformat(),
        "horizon_end": run.horizon_end.date().isoformat(),
        "horizon_days": 0 if run.scope_name == "full_2020_2026" else WEAK_WINDOW_HORIZON_DAYS,
        **summary,
        "win_ratio_pct": win_ratio_pct,
        "roundtrip_count": int(len(run.roundtrips)),
        "roundtrip_gross_pnl": roundtrip_gross,
        "roundtrip_win_ratio_pct": win_ratio_pct if run.scope_name != "full_2020_2026" else 0.0,
        "profit_giveback_stop_update_count": int(run.profit_giveback_stop_update_count),
        "profit_giveback_streak_neutral_count": int(run.profit_giveback_streak_neutral_count),
    }


def _build_comparison(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    metrics = [
        "end_balance",
        "total_return_pct",
        "max_dd_percent",
        "sharpe_ratio",
        "total_slippage",
        "total_trade_count",
        "win_ratio_pct",
        "roundtrip_count",
        "roundtrip_gross_pnl",
        "profit_giveback_streak_neutral_count",
    ]
    for scope_name, scope_frame in summary.groupby("scope_name", sort=False):
        indexed = scope_frame.set_index("profile_name")
        for left_name, right_name, comparison_name in [
            (PROFILE_STAGE132, PROFILE_STAGE128, "stage132_vs_stage128"),
            (PROFILE_STAGE132, PROFILE_STAGE78, "stage132_vs_stage78"),
            (PROFILE_STAGE128, PROFILE_STAGE78, "stage128_vs_stage78"),
        ]:
            if left_name not in indexed.index or right_name not in indexed.index:
                continue
            row: dict[str, Any] = {
                "scope_name": scope_name,
                "comparison_name": comparison_name,
                "left_profile": left_name,
                "right_profile": right_name,
            }
            for metric in metrics:
                row[f"{metric}_left"] = indexed.at[left_name, metric]
                row[f"{metric}_right"] = indexed.at[right_name, metric]
                row[f"{metric}_delta"] = indexed.at[left_name, metric] - indexed.at[right_name, metric]
            rows.append(row)
    return pd.DataFrame(rows)


def _build_report(summary: pd.DataFrame, comparison: pd.DataFrame, candidate_summary: pd.DataFrame) -> str:
    summary_columns = [
        "scope_name",
        "profile_name",
        "end_balance",
        "total_return_pct",
        "max_dd_percent",
        "sharpe_ratio",
        "total_slippage",
        "total_trade_count",
        "win_ratio_pct",
        "roundtrip_count",
        "profit_giveback_streak_neutral_count",
    ]
    comparison_columns = [
        "scope_name",
        "comparison_name",
        "end_balance_delta",
        "total_return_pct_delta",
        "max_dd_percent_delta",
        "sharpe_ratio_delta",
        "total_trade_count_delta",
        "profit_giveback_streak_neutral_count_delta",
    ]
    candidate_columns = [
        "profile_name",
        "candidate_count",
        "opened_candidate_count",
        "flat_open_rate_pct",
        "opened_median_risk_multiplier",
        "entry_risk_open_count",
        "entry_risk_median_risk_multiplier",
    ]
    return "\n".join(
        [
            "# Stage132 Profit Giveback Streak Decouple",
            "",
            "## 设计",
            "",
            "- 固定Stage128利润回吐参数，不继续调`trigger/retain/min_lock`。",
            "- 只新增`profit_giveback_streak_update_mode=loss_neutral`，验证保护性止损若滑成亏损，是否不应进入连亏惩罚。",
            "- 同时比较全周期与Stage130暴露出的`q2022_4 252d`弱窗口。",
            "",
            "## Summary",
            "",
            _to_markdown_table(summary, summary_columns, max_rows=20),
            "",
            "## Comparison",
            "",
            _to_markdown_table(comparison, comparison_columns, max_rows=20),
            "",
            "## Weak Window Candidate State",
            "",
            _to_markdown_table(candidate_summary, candidate_columns, max_rows=20),
            "",
        ]
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    profiles: list[tuple[str, dict[str, Any]]] = [
        (PROFILE_STAGE78, build_official_stage78_overrides()),
        (PROFILE_STAGE128, _candidate_overrides()),
        (PROFILE_STAGE132, _decoupled_overrides()),
    ]

    runs: list[ScopeRun] = []
    for profile_name, overrides in profiles:
        runs.append(
            _run_scope(
                profile_name,
                "full_2020_2026",
                overrides,
                analysis_start=START_DT,
                horizon_days=None,
            )
        )
    weak_runs: list[ScopeRun] = []
    for profile_name, overrides in profiles:
        weak_run = _run_scope(
            profile_name,
            WEAK_WINDOW_NAME,
            overrides,
            analysis_start=WEAK_WINDOW_START,
            horizon_days=WEAK_WINDOW_HORIZON_DAYS,
        )
        weak_runs.append(weak_run)
        runs.append(weak_run)

    summary = pd.DataFrame([_summary_row(run) for run in runs])
    comparison = _build_comparison(summary)
    candidate_summary, skip_reason_summary = _candidate_summary(weak_runs)  # type: ignore[arg-type]

    summary.to_csv(SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_CSV_PATH, index=False, encoding="utf-8-sig")
    candidate_summary.to_csv(CANDIDATE_SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")
    skip_reason_summary.to_csv(SKIP_REASON_CSV_PATH, index=False, encoding="utf-8-sig")

    payload = {
        "model_tag": MODEL_TAG,
        "profiles": [name for name, _ in profiles],
        "candidate_params": CANDIDATE_PARAMS,
        "decoupled_params": {"profit_giveback_streak_update_mode": "loss_neutral"},
        "summary": summary.to_dict(orient="records"),
        "comparison": comparison.to_dict(orient="records"),
        "candidate_summary": candidate_summary.to_dict(orient="records"),
        "skip_reason_summary": skip_reason_summary.to_dict(orient="records"),
        "outputs": {
            "summary": str(SUMMARY_CSV_PATH),
            "comparison": str(COMPARISON_CSV_PATH),
            "candidate_summary": str(CANDIDATE_SUMMARY_CSV_PATH),
            "skip_reason_summary": str(SKIP_REASON_CSV_PATH),
            "report": str(REPORT_PATH),
        },
    }
    SUMMARY_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(_build_report(summary, comparison, candidate_summary), encoding="utf-8")

    print(f"[stage132-profit-giveback-decouple] summary: {SUMMARY_CSV_PATH}")
    print(f"[stage132-profit-giveback-decouple] comparison: {COMPARISON_CSV_PATH}")
    print(f"[stage132-profit-giveback-decouple] report: {REPORT_PATH}")
    print(summary.to_string(index=False))
    print(comparison.to_string(index=False))
    print(candidate_summary.to_string(index=False))


if __name__ == "__main__":
    main()
