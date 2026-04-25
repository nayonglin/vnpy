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
    _build_delta_table,
    _build_roundtrips,
    _position_product_delta,
)
from qmt_roll_official_stage78_config import (
    OFFICIAL_STAGE78_CAPITAL,
    OFFICIAL_STAGE78_VERSION,
    build_official_stage78_overrides,
)
from qmt_universe import END_DT
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

MODEL_TAG: str = "stage131_profit_giveback_weak_window_attribution_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage131_profit_giveback_weak_window_attribution"

SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
PRODUCT_DELTA_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_delta_{MODEL_TAG}.csv"
DIRECTION_DELTA_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_direction_delta_{MODEL_TAG}.csv"
EXIT_REASON_DELTA_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_exit_reason_delta_{MODEL_TAG}.csv"
DAILY_DELTA_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_delta_{MODEL_TAG}.csv"
TOP_ROUNDTRIPS_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_top_roundtrips_{MODEL_TAG}.csv"
CANDIDATE_SUMMARY_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_candidate_summary_{MODEL_TAG}.csv"
SKIP_REASON_CSV_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_skip_reason_summary_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"

PROFILE_STAGE78: str = "official_stage78_reference"
PROFILE_STAGE128: str = "stage78_giveback10_retain80_min03"
WINDOW_NAME: str = "q2022_4"
ANALYSIS_START: datetime = datetime(2022, 10, 1)
HORIZON_DAYS: int = 252
TRADING_DAYS_PER_YEAR: int = 240


@dataclass(frozen=True)
class WindowRun:
    profile_name: str
    daily: pd.DataFrame
    positions: pd.DataFrame
    trades: pd.DataFrame
    roundtrips: pd.DataFrame
    candidates: pd.DataFrame
    entry_risk: pd.DataFrame
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


def _summarize_daily_slice(daily: pd.DataFrame) -> dict[str, float]:
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

    balance = pd.to_numeric(daily["balance"], errors="coerce").ffill().fillna(OFFICIAL_STAGE78_CAPITAL)
    net_pnl = pd.to_numeric(daily.get("net_pnl", pd.Series(0.0, index=daily.index)), errors="coerce").fillna(0.0)
    daily_return = net_pnl / balance.shift(1).fillna(OFFICIAL_STAGE78_CAPITAL).replace(0.0, np.nan)
    daily_return = daily_return.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    high_water = balance.cummax()
    dd_pct = (balance / high_water.replace(0.0, np.nan) - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0) * 100.0
    std = float(daily_return.std(ddof=1))
    sharpe = float(daily_return.mean() / std * math.sqrt(TRADING_DAYS_PER_YEAR)) if std > 1e-12 else 0.0
    end_balance = float(balance.iloc[-1])
    return {
        "end_balance": end_balance,
        "total_return_pct": (end_balance - OFFICIAL_STAGE78_CAPITAL) / OFFICIAL_STAGE78_CAPITAL * 100.0,
        "max_dd_percent": float(dd_pct.min()),
        "sharpe_ratio": sharpe,
        "total_slippage": float(pd.to_numeric(daily.get("slippage", 0.0), errors="coerce").fillna(0.0).sum()),
        "total_trade_count": float(pd.to_numeric(daily.get("trade_count", 0.0), errors="coerce").fillna(0.0).sum()),
        "day_count": float(len(daily)),
    }


def _run_window(profile_name: str, strategy_overrides: dict[str, Any]) -> WindowRun:
    print(f"[stage131-profit-giveback-weak-window] run {profile_name} / {WINDOW_NAME} {HORIZON_DAYS}d", flush=True)
    log_buffer = StringIO()
    try:
        with redirect_stdout(log_buffer), redirect_stderr(log_buffer):
            engine, analysis_df, _ = run_backtest(
                risk_ratio=BASE_RISK_RATIO,
                strategy_overrides=strategy_overrides,
                analysis_start=ANALYSIS_START,
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
    if daily.empty:
        horizon_end = pd.Timestamp(ANALYSIS_START)
    else:
        daily.sort_index(inplace=True)
        daily = daily.iloc[:HORIZON_DAYS].copy()
        horizon_end = pd.Timestamp(daily.index[-1])

    all_positions = _add_product_column(build_positions_df(engine), strategy)
    all_trades = build_trades_df(engine)
    all_roundtrips = _build_roundtrips(engine, all_trades)
    all_candidates = build_entry_candidate_snapshots_df(engine)
    all_entry_risk = build_entry_risk_diagnostics_df(engine)

    start_ts = pd.Timestamp(ANALYSIS_START)
    end_ts = horizon_end
    positions = all_positions.copy()
    if not positions.empty:
        pos_dates = pd.to_datetime(positions["date"])
        positions = positions[(pos_dates >= start_ts) & (pos_dates <= end_ts)].copy()
    trades = all_trades.copy()
    if not trades.empty:
        trade_dt = pd.to_datetime(trades["datetime"]).dt.tz_localize(None)
        trades = trades[(trade_dt >= start_ts) & (trade_dt <= end_ts)].copy()
    roundtrips = all_roundtrips.copy()
    if not roundtrips.empty:
        exit_dt = pd.to_datetime(roundtrips["exit_datetime"]).dt.tz_localize(None)
        roundtrips = roundtrips[(exit_dt >= start_ts) & (exit_dt <= end_ts)].copy()
    candidates = all_candidates.copy()
    if not candidates.empty:
        candidate_dt = pd.to_datetime(candidates["datetime"]).dt.tz_localize(None)
        candidates = candidates[(candidate_dt >= start_ts) & (candidate_dt <= end_ts)].copy()
    entry_risk = all_entry_risk.copy()
    if not entry_risk.empty:
        risk_dt = pd.to_datetime(entry_risk["datetime"]).dt.tz_localize(None)
        entry_risk = entry_risk[(risk_dt >= start_ts) & (risk_dt <= end_ts)].copy()

    for frame in (positions, trades, roundtrips, candidates, entry_risk):
        if not frame.empty:
            frame.insert(0, "profile_name", profile_name)

    return WindowRun(
        profile_name=profile_name,
        daily=daily,
        positions=positions,
        trades=trades,
        roundtrips=roundtrips,
        candidates=candidates,
        entry_risk=entry_risk,
        horizon_end=horizon_end,
    )


def _summary_row(run: WindowRun) -> dict[str, Any]:
    summary = _summarize_daily_slice(run.daily)
    roundtrip_gross = _safe_float(run.roundtrips["gross_pnl"].sum()) if not run.roundtrips.empty else 0.0
    return {
        "profile_name": run.profile_name,
        "base_version": OFFICIAL_STAGE78_VERSION,
        "window_name": WINDOW_NAME,
        "analysis_start": ANALYSIS_START.date().isoformat(),
        "horizon_end": run.horizon_end.date().isoformat(),
        "horizon_days": HORIZON_DAYS,
        **summary,
        "roundtrip_count": int(len(run.roundtrips)),
        "roundtrip_gross_pnl": roundtrip_gross,
        "roundtrip_win_ratio_pct": _safe_float((run.roundtrips["gross_pnl"] > 0).mean() * 100.0)
        if not run.roundtrips.empty
        else 0.0,
    }


def _build_daily_delta(base: WindowRun, candidate: WindowRun) -> pd.DataFrame:
    left = base.daily[["balance", "net_pnl", "drawdown", "ddpercent"]].copy().reset_index()
    right = candidate.daily[["balance", "net_pnl", "drawdown", "ddpercent"]].copy().reset_index()
    left.rename(
        columns={
            left.columns[0]: "date",
            "balance": "stage78_balance",
            "net_pnl": "stage78_net_pnl",
            "drawdown": "stage78_drawdown",
            "ddpercent": "stage78_ddpercent",
        },
        inplace=True,
    )
    right.rename(
        columns={
            right.columns[0]: "date",
            "balance": "stage128_balance",
            "net_pnl": "stage128_net_pnl",
            "drawdown": "stage128_drawdown",
            "ddpercent": "stage128_ddpercent",
        },
        inplace=True,
    )
    daily = left.merge(right, on="date", how="outer").sort_values("date").ffill().fillna(0.0)
    daily["balance_delta"] = daily["stage128_balance"] - daily["stage78_balance"]
    daily["net_pnl_delta"] = daily["stage128_net_pnl"] - daily["stage78_net_pnl"]
    daily["ddpercent_delta"] = daily["stage128_ddpercent"] - daily["stage78_ddpercent"]
    return daily


def _top_roundtrips(base: WindowRun, candidate: WindowRun) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for label, frame in [("stage78_top_loss", base.roundtrips), ("stage128_top_loss", candidate.roundtrips)]:
        if not frame.empty:
            loss = frame.sort_values("gross_pnl", ascending=True).head(12).copy()
            loss.insert(1, "bucket", label)
            frames.append(loss)
    for label, frame in [("stage78_top_win", base.roundtrips), ("stage128_top_win", candidate.roundtrips)]:
        if not frame.empty:
            win = frame.sort_values("gross_pnl", ascending=False).head(12).copy()
            win.insert(1, "bucket", label)
            frames.append(win)
    return pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()


def _median_numeric(df: pd.DataFrame, column: str) -> float:
    if df.empty or column not in df.columns:
        return 0.0
    return _safe_float(pd.to_numeric(df[column], errors="coerce").median())


def _sum_numeric(df: pd.DataFrame, column: str) -> float:
    if df.empty or column not in df.columns:
        return 0.0
    return _safe_float(pd.to_numeric(df[column], errors="coerce").fillna(0.0).sum())


def _candidate_summary(runs: list[WindowRun]) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, Any]] = []
    skip_rows: list[dict[str, Any]] = []
    for run in runs:
        candidates = run.candidates.copy()
        entry_risk = run.entry_risk.copy()
        flat = candidates[candidates.get("entry_context", "").astype(str).eq("flat_entry")].copy() if not candidates.empty else candidates
        opened = flat[flat.get("candidate_status", "").astype(str).eq("opened")].copy() if not flat.empty else flat
        rows.append(
            {
                "profile_name": run.profile_name,
                "candidate_count": int(len(candidates)),
                "flat_candidate_count": int(len(flat)),
                "opened_candidate_count": int(len(opened)),
                "entry_risk_open_count": int(len(entry_risk)),
                "flat_open_rate_pct": float(len(opened) / len(flat) * 100.0) if len(flat) else 0.0,
                "candidate_median_risk_multiplier": _median_numeric(flat, "risk_multiplier"),
                "candidate_median_selected_volume": _median_numeric(flat, "selected_volume"),
                "candidate_selected_volume_sum": _sum_numeric(flat, "selected_volume"),
                "opened_median_risk_multiplier": _median_numeric(opened, "risk_multiplier"),
                "opened_median_selected_volume": _median_numeric(opened, "selected_volume"),
                "opened_selected_volume_sum": _sum_numeric(opened, "selected_volume"),
                "entry_risk_median_risk_multiplier": _median_numeric(entry_risk, "risk_multiplier"),
                "entry_risk_selected_volume_sum": _sum_numeric(entry_risk, "selected_volume"),
                "candidate_median_loss_streak": _median_numeric(flat, "loss_streak"),
                "entry_risk_median_loss_streak": _median_numeric(entry_risk, "loss_streak"),
            }
        )
        if not flat.empty and "skip_reason" in flat.columns:
            counts = flat["skip_reason"].fillna("").astype(str).value_counts(dropna=False)
            for reason, count in counts.items():
                skip_rows.append({"profile_name": run.profile_name, "skip_reason": reason or "opened_or_blank", "count": int(count)})
    return pd.DataFrame(rows), pd.DataFrame(skip_rows)


def _build_report(
    summary: pd.DataFrame,
    product_delta: pd.DataFrame,
    direction_delta: pd.DataFrame,
    exit_reason_delta: pd.DataFrame,
    daily_delta: pd.DataFrame,
    top_roundtrips: pd.DataFrame,
    candidate_summary: pd.DataFrame,
    skip_reason_summary: pd.DataFrame,
) -> str:
    return "\n".join(
        [
            "# Stage131 Profit Giveback Weak Window Attribution",
            "",
            "## Boundary",
            "",
            f"- Weak window: `{WINDOW_NAME}` first `{HORIZON_DAYS}` trading days.",
            "- Base: `official_stage78_defensive_v1`.",
            "- Candidate: fixed `stage78_giveback10_retain80_min03`.",
            "- No parameter tuning; this is a failure-case attribution.",
            "",
            "## Window Summary",
            "",
            _to_markdown_table(
                summary,
                [
                    "profile_name",
                    "end_balance",
                    "total_return_pct",
                    "max_dd_percent",
                    "sharpe_ratio",
                    "total_slippage",
                    "total_trade_count",
                    "roundtrip_count",
                    "roundtrip_gross_pnl",
                    "roundtrip_win_ratio_pct",
                ],
            ),
            "",
            "## Product Delta",
            "",
            _to_markdown_table(
                product_delta,
                [
                    "product_vt_symbol",
                    "stage128_net_pnl",
                    "stage78_net_pnl",
                    "net_pnl_delta",
                    "stage128_trade_count",
                    "stage78_trade_count",
                    "trade_count_delta",
                ],
                max_rows=20,
            ),
            "",
            "## Direction Delta",
            "",
            _to_markdown_table(
                direction_delta,
                [
                    "position_direction",
                    "stage128_gross_pnl",
                    "stage78_gross_pnl",
                    "gross_pnl_delta",
                    "stage128_roundtrip_count",
                    "stage78_roundtrip_count",
                ],
            ),
            "",
            "## Exit Reason Delta",
            "",
            _to_markdown_table(
                exit_reason_delta,
                [
                    "exit_reason",
                    "stage128_gross_pnl",
                    "stage78_gross_pnl",
                    "gross_pnl_delta",
                    "stage128_roundtrip_count",
                    "stage78_roundtrip_count",
                ],
                max_rows=20,
            ),
            "",
            "## Worst Daily Deltas",
            "",
            _to_markdown_table(
                daily_delta.sort_values("net_pnl_delta").head(12),
                [
                    "date",
                    "stage128_net_pnl",
                    "stage78_net_pnl",
                    "net_pnl_delta",
                    "balance_delta",
                    "stage128_ddpercent",
                    "stage78_ddpercent",
                    "ddpercent_delta",
                ],
            ),
            "",
            "## Candidate And Risk State",
            "",
            _to_markdown_table(
                candidate_summary,
                [
                    "profile_name",
                    "flat_candidate_count",
                    "opened_candidate_count",
                    "entry_risk_open_count",
                    "flat_open_rate_pct",
                    "candidate_median_risk_multiplier",
                    "opened_median_risk_multiplier",
                    "candidate_selected_volume_sum",
                    "opened_selected_volume_sum",
                    "entry_risk_selected_volume_sum",
                    "candidate_median_loss_streak",
                ],
            ),
            "",
            "## Skip Reason Summary",
            "",
            _to_markdown_table(skip_reason_summary, ["profile_name", "skip_reason", "count"], max_rows=30),
            "",
            "## Top Roundtrips",
            "",
            _to_markdown_table(
                top_roundtrips,
                [
                    "bucket",
                    "product_vt_symbol",
                    "position_direction",
                    "entry_date",
                    "exit_date",
                    "gross_pnl",
                    "holding_days",
                    "exit_reason",
                ],
                max_rows=32,
            ),
            "",
            "## Judgement Rule",
            "",
            "- If the weak window is driven by one or two accidental exits, Stage128 can still proceed to slippage stress.",
            "- If the loss comes from systematically cutting trend continuation, Stage128 should not be formalized.",
        ]
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    base = _run_window(PROFILE_STAGE78, build_official_stage78_overrides())
    candidate = _run_window(PROFILE_STAGE128, _candidate_overrides())

    summary = pd.DataFrame([_summary_row(base), _summary_row(candidate)])
    product_delta = _position_product_delta(base.positions, candidate.positions)
    direction_delta = _build_delta_table(base.roundtrips, candidate.roundtrips, "position_direction")
    exit_reason_delta = _build_delta_table(base.roundtrips, candidate.roundtrips, "exit_reason")
    daily_delta = _build_daily_delta(base, candidate)
    top_roundtrips = _top_roundtrips(base, candidate)
    candidate_summary, skip_reason_summary = _candidate_summary([base, candidate])

    summary.to_csv(SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")
    product_delta.to_csv(PRODUCT_DELTA_CSV_PATH, index=False, encoding="utf-8-sig")
    direction_delta.to_csv(DIRECTION_DELTA_CSV_PATH, index=False, encoding="utf-8-sig")
    exit_reason_delta.to_csv(EXIT_REASON_DELTA_CSV_PATH, index=False, encoding="utf-8-sig")
    daily_delta.to_csv(DAILY_DELTA_CSV_PATH, index=False, encoding="utf-8-sig")
    top_roundtrips.to_csv(TOP_ROUNDTRIPS_CSV_PATH, index=False, encoding="utf-8-sig")
    candidate_summary.to_csv(CANDIDATE_SUMMARY_CSV_PATH, index=False, encoding="utf-8-sig")
    skip_reason_summary.to_csv(SKIP_REASON_CSV_PATH, index=False, encoding="utf-8-sig")

    payload = {
        "model_tag": MODEL_TAG,
        "base_version": OFFICIAL_STAGE78_VERSION,
        "window_name": WINDOW_NAME,
        "analysis_start": ANALYSIS_START.date().isoformat(),
        "horizon_days": HORIZON_DAYS,
        "candidate_params": CANDIDATE_PARAMS,
        "summary": summary.to_dict(orient="records"),
        "product_delta": product_delta.to_dict(orient="records"),
        "direction_delta": direction_delta.to_dict(orient="records"),
        "exit_reason_delta": exit_reason_delta.to_dict(orient="records"),
        "candidate_summary": candidate_summary.to_dict(orient="records"),
        "skip_reason_summary": skip_reason_summary.to_dict(orient="records"),
        "output_paths": {
            "summary": str(SUMMARY_CSV_PATH),
            "product_delta": str(PRODUCT_DELTA_CSV_PATH),
            "direction_delta": str(DIRECTION_DELTA_CSV_PATH),
            "exit_reason_delta": str(EXIT_REASON_DELTA_CSV_PATH),
            "daily_delta": str(DAILY_DELTA_CSV_PATH),
            "top_roundtrips": str(TOP_ROUNDTRIPS_CSV_PATH),
            "candidate_summary": str(CANDIDATE_SUMMARY_CSV_PATH),
            "skip_reason_summary": str(SKIP_REASON_CSV_PATH),
            "summary_json": str(SUMMARY_JSON_PATH),
            "report": str(REPORT_PATH),
        },
    }
    SUMMARY_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT_PATH.write_text(
        _build_report(
            summary,
            product_delta,
            direction_delta,
            exit_reason_delta,
            daily_delta,
            top_roundtrips,
            candidate_summary,
            skip_reason_summary,
        ),
        encoding="utf-8",
    )

    print(f"[stage131-profit-giveback-weak-window] summary: {SUMMARY_CSV_PATH}")
    print(f"[stage131-profit-giveback-weak-window] report: {REPORT_PATH}")
    print(summary.to_string(index=False))
    print(product_delta.to_string(index=False))
    print(direction_delta.to_string(index=False))
    print(exit_reason_delta.to_string(index=False))
    print(candidate_summary.to_string(index=False))
    print(skip_reason_summary.to_string(index=False))


if __name__ == "__main__":
    main()
