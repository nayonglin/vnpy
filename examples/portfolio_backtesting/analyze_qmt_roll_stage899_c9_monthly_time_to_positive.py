from __future__ import annotations

from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
import multiprocessing as mp
import os
from pathlib import Path
import shutil
from typing import Any

import numpy as np
import pandas as pd

import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage896_c9_vs_official_halfyear_rolling3y as s896
import qmt_roll_official_candidate_stage819_30w_config as stage819_cfg
import run_qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_backtest as fu_universe_cfg


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage899"
MODEL_TAG = "stage899_c9_monthly_time_to_positive_v1"
OUTPUT_PREFIX = "qmt_roll_stage899_c9_monthly_time_to_positive"

DATA_START = pd.Timestamp("2018-01-01")
DATA_END = pd.Timestamp("2026-05-29")
REQUESTED_TODAY = pd.Timestamp("2026-06-15")
C9_ARM = "c9_stage847_stage819_30w"
WINDOW_GROUP = "stage899_c9_monthly_start_to_latest"
DEFAULT_WORKERS = max(1, min(4, int(os.environ.get("STAGE899_WORKERS", "1"))))

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
AGG_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_aggregate_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHECKPOINT_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_checkpoint_summary_{MODEL_TAG}.csv"
WORKER_STATIC_DIR = OUTPUT_DIR / f"{OUTPUT_PREFIX}_worker_static_{MODEL_TAG}"


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _month_text(value: pd.Timestamp) -> str:
    return pd.Timestamp(value).strftime("%Y-%m")


def _window_id(start: pd.Timestamp) -> str:
    return f"{_month_text(start).replace('-', '_')}_to_{DATA_END.strftime('%Y_%m_%d')}"


def _build_windows() -> list[dict[str, Any]]:
    starts = pd.date_range(DATA_START, DATA_END, freq="MS")
    windows: list[dict[str, Any]] = []
    for start in starts:
        windows.append(
            {
                "window_id": _window_id(start),
                "start": pd.Timestamp(start).normalize(),
                "end": DATA_END.normalize(),
                "terminal_partial": True,
                # Reuse Stage896 runner internals. Here this flag only means enough data for one year.
                "complete_3y": int(pd.Timestamp(start).normalize() + pd.DateOffset(years=1) - pd.Timedelta(days=1) <= DATA_END),
            }
        )
    return windows


WINDOWS = _build_windows()

_WORKER_METADATA: dict[str, Any] | None = None


def _configure_runner() -> None:
    s896.STAGE = STAGE
    s896.MODEL_TAG = MODEL_TAG
    s896.ROLL_YEARS = 0
    s896.WINDOW_GROUP = WINDOW_GROUP
    s896.DATA_START = DATA_START
    s896.DATA_END = DATA_END


def _ensure_parent_stage819_static_files() -> None:
    for path in stage819_cfg.build_official_candidate_stage819_30w_paths():
        if not path.exists() or path.stat().st_size == 0:
            raise RuntimeError(f"Stage819 static input missing or empty: {path}")


def _install_worker_stage819_path_override() -> None:
    base_universe = fu_universe_cfg.UNIVERSE_PATH
    base_eligibility = fu_universe_cfg.AI_SATELLITE_POST_SIGNAL_ELIGIBILITY_PATH
    for path in [base_universe, base_eligibility]:
        if not path.exists() or path.stat().st_size == 0:
            raise RuntimeError(f"Stage819 parent static input missing or empty: {path}")

    worker_dir = WORKER_STATIC_DIR / f"pid_{os.getpid()}"
    worker_dir.mkdir(parents=True, exist_ok=True)
    worker_universe = worker_dir / base_universe.name
    worker_eligibility = worker_dir / base_eligibility.name
    shutil.copy2(base_universe, worker_universe)
    shutil.copy2(base_eligibility, worker_eligibility)

    def _worker_stage819_paths() -> tuple[Path, Path]:
        return worker_universe, worker_eligibility

    stage819_cfg.build_official_candidate_stage819_30w_paths = _worker_stage819_paths


def _curve_positive_stats(curve: pd.DataFrame, window: dict[str, Any]) -> dict[str, Any]:
    data = curve.copy().sort_values("date").reset_index(drop=True)
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    data["rebased_nav"] = pd.to_numeric(data["rebased_nav"], errors="coerce")
    start = pd.Timestamp(window["start"]).normalize()
    start_row_date = data["date"].dropna().min()
    positive = data[data["rebased_nav"] > 1.0 + 1e-12].copy()
    if positive.empty:
        elapsed_days = int((DATA_END.normalize() - start).days)
        elapsed_trading_days = int(len(data))
        return {
            "ever_positive": 0,
            "first_positive_date": "",
            "calendar_days_to_first_positive": np.nan,
            "trading_days_to_first_positive": np.nan,
            "months_to_first_positive_30d": np.nan,
            "unresolved_elapsed_calendar_days": elapsed_days,
            "unresolved_elapsed_trading_days": elapsed_trading_days,
            "positive_on_first_trading_day": 0,
        }
    first = positive.iloc[0]
    first_date = pd.Timestamp(first["date"]).normalize()
    trading_days = int(data.index[data["date"].eq(first_date)][0] + 1)
    days = int((first_date - start).days)
    return {
        "ever_positive": 1,
        "first_positive_date": first_date.strftime("%Y-%m-%d"),
        "calendar_days_to_first_positive": days,
        "trading_days_to_first_positive": trading_days,
        "months_to_first_positive_30d": float(days / 30.4375),
        "unresolved_elapsed_calendar_days": 0,
        "unresolved_elapsed_trading_days": 0,
        "positive_on_first_trading_day": int(days <= 1 and trading_days <= 2),
    }


def _empty_window_row(window: dict[str, Any], reason: str) -> tuple[dict[str, Any], pd.DataFrame]:
    start = pd.Timestamp(window["start"]).normalize()
    elapsed_days = int((DATA_END.normalize() - start).days)
    row: dict[str, Any] = {
        "variant": f"stage847_stage819_c4_05r_stop_retry_once_{window['window_id']}",
        "label": f"Stage847 C9 0.5R stop + retry once {window['window_id']}",
        "profile": s896.C9_ARM,
        "window_name": f"{window['window_id']}_monthly_to_latest",
        "window_label": f"{_month_text(start)} to {DATA_END.strftime('%Y-%m-%d')}",
        "window_group": WINDOW_GROUP,
        "analysis_start": start.strftime("%Y-%m-%d"),
        "analysis_end": DATA_END.strftime("%Y-%m-%d"),
        "account_capital": s896.C9_CAPITAL,
        "c3_capital": s896.C9_CAPITAL,
        "risk_multiplier": 0.4,
        "trading_days": 0,
        "end_equity": s896.C9_CAPITAL,
        "total_return_pct": 0.0,
        "cagr_pct": np.nan,
        "max_dd_pct": 0.0,
        "ulcer_pct": 0.0,
        "sharpe": np.nan,
        "min_equity": s896.C9_CAPITAL,
        "max_broker10_margin_to_equity_pct": 0.0,
        "p95_broker10_margin_to_equity_pct": 0.0,
        "days_over_100pct": 0,
        "days_over_90pct": 0,
        "days_equity_below_zero": 0,
        "total_slippage": 0.0,
        "total_trade_count": 0.0,
        "nonzero_daily_win_rate_pct": 0.0,
        "forced_margin_deleverage_count": 0,
        "forced_margin_deleverage_closed_volume": 0.0,
        "dd30_pass": 1,
        "dd40_pass": 1,
        "broker10_100_pass": 1,
        "account_survival_pass": 1,
        "deployable_pass": 0,
        "source_name": "stage772_am40_80_120_oi_monthly",
        "rebased_end_equity": s896.C9_CAPITAL,
        "rebased_total_return_pct": 0.0,
        "rebased_cagr_pct": np.nan,
        "rebased_max_dd_pct": 0.0,
        "rebased_sharpe": np.nan,
        "rebased_min_equity": s896.C9_CAPITAL,
        "max_broker10_margin_to_rebased_equity_pct": 0.0,
        "p95_broker10_margin_to_rebased_equity_pct": 0.0,
        "nav_end": 1.0,
        "stop_retry_event_count": 0,
        "broker10_cap_event_count": 0,
        "ever_positive": 0,
        "first_positive_date": "",
        "calendar_days_to_first_positive": np.nan,
        "trading_days_to_first_positive": np.nan,
        "months_to_first_positive_30d": np.nan,
        "unresolved_elapsed_calendar_days": elapsed_days,
        "unresolved_elapsed_trading_days": 0,
        "positive_on_first_trading_day": 0,
        "empty_result": 1,
        "empty_result_reason": reason,
    }
    curve = pd.DataFrame(
        [
            {
                "date": DATA_END.strftime("%Y-%m-%d"),
                "variant": row["variant"],
                "label": row["label"],
                "window_name": row["window_name"],
                "window_label": row["window_label"],
                "window_group": WINDOW_GROUP,
                "account_capital": s896.C9_CAPITAL,
                "account_equity": s896.C9_CAPITAL,
                "nav": 1.0,
                "drawdown_pct": 0.0,
                "broker10_margin_to_equity_pct": 0.0,
                "net_pnl": 0.0,
                "trade_count": 0,
                "total_slippage": 0.0,
                "source_name": "empty_result_placeholder",
                "rebased_equity": s896.C9_CAPITAL,
                "rebased_nav": 1.0,
                "broker10_margin_to_rebased_equity_pct": 0.0,
            }
        ]
    )
    return row, curve


def _run_monthly_windows() -> tuple[pd.DataFrame, pd.DataFrame]:
    _configure_runner()
    metadata = s896.s513._metadata()
    vt_symbols = set(str(item) for item in metadata["vt_symbols"])
    minute_bars = s896._load_stage861_full_minute_bars(vt_symbols)
    s896.s847.s827._GLOBAL_MINUTE_BY_SYMBOL = s896.s825._minute_groups(minute_bars)

    rows: list[dict[str, Any]] = []
    curves: list[pd.DataFrame] = []
    for idx, window in enumerate(WINDOWS, start=1):
        print(f"[stage899] running {idx}/{len(WINDOWS)} C9 {window['window_id']}", flush=True)
        try:
            row, curve = s896._run_c9(metadata, window)
            row.update(_curve_positive_stats(curve, window))
            row["empty_result"] = 0
            row["empty_result_reason"] = ""
        except RuntimeError as exc:
            if "empty daily result" not in str(exc):
                raise
            row, curve = _empty_window_row(window, str(exc))
            print(f"[stage899] empty_result {window['window_id']} {exc}", flush=True)
        row.update(
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "line_id": LINE_ID,
                "arm_key": C9_ARM,
                "window_group": WINDOW_GROUP,
                "window_id": str(window["window_id"]),
                "window_start": pd.Timestamp(window["start"]).strftime("%Y-%m-%d"),
                "window_end": DATA_END.strftime("%Y-%m-%d"),
                "start_month": _month_text(pd.Timestamp(window["start"])),
                "start_year": int(pd.Timestamp(window["start"]).year),
                "start_month_num": int(pd.Timestamp(window["start"]).month),
                "run_to_latest": 1,
                "complete_1y": int(bool(window["complete_3y"])),
                "latest_available_backtest_date": DATA_END.strftime("%Y-%m-%d"),
            }
        )
        curve = curve.copy()
        curve["stage"] = STAGE
        curve["model_tag"] = MODEL_TAG
        curve["line_id"] = LINE_ID
        curve["arm_key"] = C9_ARM
        curve["window_group"] = WINDOW_GROUP
        curve["window_id"] = str(window["window_id"])
        curve["window_start"] = pd.Timestamp(window["start"]).strftime("%Y-%m-%d")
        curve["window_end"] = DATA_END.strftime("%Y-%m-%d")
        curve["start_month"] = _month_text(pd.Timestamp(window["start"]))
        curve["start_year"] = int(pd.Timestamp(window["start"]).year)
        curve["start_month_num"] = int(pd.Timestamp(window["start"]).month)
        curve["run_to_latest"] = 1
        curve["complete_1y"] = int(bool(window["complete_3y"]))
        rows.append(row)
        curves.append(curve)
        pd.DataFrame(rows).sort_values(["window_start"]).reset_index(drop=True).to_csv(
            CHECKPOINT_SUMMARY_PATH, index=False, encoding="utf-8-sig"
        )

    summary = pd.DataFrame(rows).sort_values(["window_start"]).reset_index(drop=True)
    curve_df = pd.concat(curves, ignore_index=True, sort=False).sort_values(["window_start", "date"]).reset_index(drop=True)
    return summary, curve_df


def _init_worker() -> None:
    global _WORKER_METADATA
    _configure_runner()
    _install_worker_stage819_path_override()
    _WORKER_METADATA = s896.s513._metadata()
    vt_symbols = set(str(item) for item in _WORKER_METADATA["vt_symbols"])
    minute_bars = s896._load_stage861_full_minute_bars(vt_symbols)
    s896.s847.s827._GLOBAL_MINUTE_BY_SYMBOL = s896.s825._minute_groups(minute_bars)


def _run_window_worker(window: dict[str, Any]) -> tuple[dict[str, Any], pd.DataFrame]:
    if _WORKER_METADATA is None:
        _init_worker()
    assert _WORKER_METADATA is not None
    _configure_runner()
    try:
        row, curve = s896._run_c9(_WORKER_METADATA, window)
        row.update(_curve_positive_stats(curve, window))
        row["empty_result"] = 0
        row["empty_result_reason"] = ""
    except RuntimeError as exc:
        if "empty daily result" not in str(exc):
            raise
        row, curve = _empty_window_row(window, str(exc))
    row.update(
        {
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "arm_key": C9_ARM,
            "window_group": WINDOW_GROUP,
            "window_id": str(window["window_id"]),
            "window_start": pd.Timestamp(window["start"]).strftime("%Y-%m-%d"),
            "window_end": DATA_END.strftime("%Y-%m-%d"),
            "start_month": _month_text(pd.Timestamp(window["start"])),
            "start_year": int(pd.Timestamp(window["start"]).year),
            "start_month_num": int(pd.Timestamp(window["start"]).month),
            "run_to_latest": 1,
            "complete_1y": int(bool(window["complete_3y"])),
            "latest_available_backtest_date": DATA_END.strftime("%Y-%m-%d"),
        }
    )
    curve = curve.copy()
    curve["stage"] = STAGE
    curve["model_tag"] = MODEL_TAG
    curve["line_id"] = LINE_ID
    curve["arm_key"] = C9_ARM
    curve["window_group"] = WINDOW_GROUP
    curve["window_id"] = str(window["window_id"])
    curve["window_start"] = pd.Timestamp(window["start"]).strftime("%Y-%m-%d")
    curve["window_end"] = DATA_END.strftime("%Y-%m-%d")
    curve["start_month"] = _month_text(pd.Timestamp(window["start"]))
    curve["start_year"] = int(pd.Timestamp(window["start"]).year)
    curve["start_month_num"] = int(pd.Timestamp(window["start"]).month)
    curve["run_to_latest"] = 1
    curve["complete_1y"] = int(bool(window["complete_3y"]))
    return row, curve


def _run_monthly_windows_parallel(workers: int = DEFAULT_WORKERS) -> tuple[pd.DataFrame, pd.DataFrame]:
    _ensure_parent_stage819_static_files()
    if workers <= 1:
        return _run_monthly_windows()
    rows: list[dict[str, Any]] = []
    curves: list[pd.DataFrame] = []
    print(f"[stage899] parallel workers={workers} windows={len(WINDOWS)}", flush=True)
    context = mp.get_context("spawn")
    with ProcessPoolExecutor(max_workers=workers, mp_context=context, initializer=_init_worker) as executor:
        futures = {executor.submit(_run_window_worker, window): window for window in WINDOWS}
        completed = 0
        for future in as_completed(futures):
            window = futures[future]
            row, curve = future.result()
            rows.append(row)
            curves.append(curve)
            completed += 1
            print(f"[stage899] completed {completed}/{len(WINDOWS)} {window['window_id']}", flush=True)
    summary = pd.DataFrame(rows).sort_values(["window_start"]).reset_index(drop=True)
    curve_df = pd.concat(curves, ignore_index=True, sort=False).sort_values(["window_start", "date"]).reset_index(drop=True)
    return summary, curve_df


def _aggregate(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    scopes = [
        ("all_monthly_starts", summary),
        ("mature_1y_or_more", summary[pd.to_numeric(summary["complete_1y"], errors="coerce").fillna(0).eq(1)]),
    ]
    for scope, scoped in scopes:
        returns = pd.to_numeric(scoped["rebased_total_return_pct"], errors="coerce")
        dds = pd.to_numeric(scoped["rebased_max_dd_pct"], errors="coerce")
        positive_wait = pd.to_numeric(scoped["calendar_days_to_first_positive"], errors="coerce")
        positive_wait_trading = pd.to_numeric(scoped["trading_days_to_first_positive"], errors="coerce")
        unresolved = scoped[pd.to_numeric(scoped["ever_positive"], errors="coerce").fillna(0).eq(0)].copy()
        max_wait_rows = scoped[positive_wait.eq(positive_wait.max())].copy() if positive_wait.notna().any() else pd.DataFrame()
        rows.append(
            {
                "scope": scope,
                "window_count": int(len(scoped)),
                "ever_positive_count": int(pd.to_numeric(scoped["ever_positive"], errors="coerce").fillna(0).sum()),
                "unresolved_count": int(len(unresolved)),
                "empty_result_count": int(pd.to_numeric(scoped.get("empty_result", 0), errors="coerce").fillna(0).sum()),
                "positive_rate_pct": float(pd.to_numeric(scoped["ever_positive"], errors="coerce").fillna(0).mean() * 100.0)
                if len(scoped)
                else 0.0,
                "longest_calendar_days_to_first_positive": float(positive_wait.max()) if positive_wait.notna().any() else np.nan,
                "longest_trading_days_to_first_positive": float(positive_wait_trading.max())
                if positive_wait_trading.notna().any()
                else np.nan,
                "longest_months_to_first_positive_30d": float((positive_wait.max() or np.nan) / 30.4375)
                if positive_wait.notna().any()
                else np.nan,
                "median_calendar_days_to_first_positive": float(positive_wait.median()) if positive_wait.notna().any() else np.nan,
                "p90_calendar_days_to_first_positive": float(positive_wait.quantile(0.90)) if positive_wait.notna().any() else np.nan,
                "positive_on_first_trading_day_count": int(
                    pd.to_numeric(scoped["positive_on_first_trading_day"], errors="coerce").fillna(0).sum()
                ),
                "positive_return_count_at_latest": int((returns > 0.0).sum()),
                "latest_positive_return_rate_pct": float((returns > 0.0).mean() * 100.0) if len(scoped) else 0.0,
                "min_latest_return_pct": float(returns.min()) if returns.notna().any() else np.nan,
                "median_latest_return_pct": float(returns.median()) if returns.notna().any() else np.nan,
                "worst_dd_pct": float(dds.min()) if dds.notna().any() else np.nan,
                "longest_wait_window_ids": ",".join(max_wait_rows["window_id"].astype(str).tolist()) if not max_wait_rows.empty else "",
                "unresolved_window_ids": ",".join(unresolved["window_id"].astype(str).tolist()) if not unresolved.empty else "",
                "max_unresolved_elapsed_calendar_days": float(
                    pd.to_numeric(unresolved.get("unresolved_elapsed_calendar_days", pd.Series(dtype=float)), errors="coerce").max()
                )
                if not unresolved.empty
                else 0.0,
            }
        )
    return pd.DataFrame(rows)


def _decision(summary: pd.DataFrame, aggregate: pd.DataFrame) -> dict[str, Any]:
    exact = aggregate[aggregate["scope"].eq("all_monthly_starts")].iloc[0].to_dict()
    mature = aggregate[aggregate["scope"].eq("mature_1y_or_more")].iloc[0].to_dict()
    wait = pd.to_numeric(summary["calendar_days_to_first_positive"], errors="coerce")
    longest = summary[wait.eq(wait.max())].copy() if wait.notna().any() else pd.DataFrame()
    unresolved = summary[pd.to_numeric(summary["ever_positive"], errors="coerce").fillna(0).eq(0)].copy()
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "data_start": DATA_START.strftime("%Y-%m-%d"),
        "latest_available_backtest_date": DATA_END.strftime("%Y-%m-%d"),
        "requested_today": REQUESTED_TODAY.strftime("%Y-%m-%d"),
        "start_schedule": "monthly starts from 2018-01",
        "arm": {
            "arm_key": C9_ARM,
            "version": s896.C9_VERSION,
            "capital": s896.C9_CAPITAL,
        },
        "aggregate": aggregate.to_dict(orient="records"),
        "longest_wait_windows": longest[
            [
                "window_id",
                "window_start",
                "first_positive_date",
                "calendar_days_to_first_positive",
                "trading_days_to_first_positive",
                "months_to_first_positive_30d",
                "rebased_total_return_pct",
                "rebased_max_dd_pct",
            ]
        ].to_dict(orient="records"),
        "unresolved_windows": unresolved[
            [
                "window_id",
                "window_start",
                "window_end",
                "unresolved_elapsed_calendar_days",
                "rebased_total_return_pct",
                "rebased_max_dd_pct",
            ]
        ].to_dict(orient="records"),
        "decision": "stage899_c9_monthly_wait_time_audit_complete",
        "strategy_changed": False,
        "official_config_changed": False,
        "ctp_connected": False,
        "order_api_called": False,
        "formal_ab_triggered": False,
        "external_research_judgment": (
            "Monthly-start expanding backtests are a robustness audit for path dependency and investor waiting time. "
            "They do not remove C9's inherited data-coverage and execution-model limitations."
        ),
        "overfit_reflection_before": (
            "No: the monthly start schedule and first-positive metric are fixed before execution; no thresholds are tuned."
        ),
        "continue_value_before": (
            "Yes: time-to-positive directly answers whether a user could tolerate the strategy after a cold start."
        ),
        "overfit_reflection_after": (
            "No new overfit was introduced by this audit; residual risk remains from C9's historical discovery process."
        ),
        "continue_value_after": (
            "Yes, but only for risk-tail and recent-start attribution now that Stage898 entry-day minute gaps are closed."
        ),
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "curves": str(CURVES_PATH),
            "aggregate": str(AGG_PATH),
            "report": str(REPORT_PATH),
            "decision": str(DECISION_PATH),
        },
    }


def _write_report(summary: pd.DataFrame, aggregate: pd.DataFrame, decision: dict[str, Any]) -> None:
    longest = pd.DataFrame(decision["longest_wait_windows"])
    unresolved = pd.DataFrame(decision["unresolved_windows"])
    report = f"""# Stage899 C9 Monthly Start Time To Positive

- line_id：`{LINE_ID}`
- model_tag：`{MODEL_TAG}`
- 生成时间：`{datetime.now().isoformat(timespec="seconds")}`
- 阶段性质：只读多起点回测；不改 C9 策略参数、不连接 CTP、不调用下单。

## External Research Judgment

- Walk-forward / rolling-start validation is useful for exposing path dependency and cold-start waiting time.
- My judgment: this audit should be interpreted as a user-experience and robustness statistic. Stage898 has cleared the C9 open-trade entry-day minute coverage gate, so the remaining issue is risk-tail and recent-start behavior rather than known entry-day data omission.

## Aggregate

{_md_table(aggregate)}

## Longest Wait Windows

{_md_table(longest)}

## Unresolved Windows

{_md_table(unresolved)}

## Monthly Summary

{_md_table(summary[[
    "window_id",
    "window_start",
    "ever_positive",
    "first_positive_date",
    "calendar_days_to_first_positive",
    "trading_days_to_first_positive",
    "rebased_total_return_pct",
    "rebased_max_dd_pct",
    "rebased_sharpe",
]], max_rows=140)}

## Judgment

- Decision：`{decision["decision"]}`
- This run does not change strategy logic.
- If any window remains unresolved, longest time-to-positive should be read as at least its elapsed time, not as a completed recovery period.
"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary, curves = _run_monthly_windows_parallel(DEFAULT_WORKERS)
    aggregate = _aggregate(summary)
    decision = _decision(summary, aggregate)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    aggregate.to_csv(AGG_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(summary, aggregate, decision)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print("aggregate")
    print(aggregate.to_string(index=False))
    print("longest_wait_windows")
    print(pd.DataFrame(decision["longest_wait_windows"]).to_string(index=False))
    print("unresolved_windows")
    print(pd.DataFrame(decision["unresolved_windows"]).to_string(index=False))


if __name__ == "__main__":
    main()
