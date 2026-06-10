from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
from datetime import datetime
import json
import os
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage748_half_risk_no_streak_500k as s748
import analyze_qmt_roll_stage749_half_risk_no_streak_500k_monthly_start_compare as s749
import analyze_qmt_roll_stage751_cash_reserve_bucket_monthly_start as s751
import analyze_qmt_roll_stage757_c50_oi_confirm_risk_restore as s757
import analyze_qmt_roll_stage660_stage653_multiperiod_live_audit as s660


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage764_stage757_cash_reserve_45w5w_monthly_start_v1"
OUTPUT_PREFIX = "qmt_roll_stage764_stage757_cash_reserve_45w5w_monthly_start"
LINE_ID = "futures_trend_cash_reserve_bucket"

ANALYSIS_END = pd.Timestamp("2026-05-29")
MONTH_STARTS = tuple(pd.date_range("2020-01-01", ANALYSIS_END.normalize(), freq="MS"))

TOTAL_CAPITAL = 500_000.0
TRADING_BUCKET_CAPITAL = 450_000.0
RESERVE_CAPITAL = TOTAL_CAPITAL - TRADING_BUCKET_CAPITAL

BASE_ARM = "A_stage757_no_reserve"
C_ARM = "C_stage757_cash_reserve_45w5w"
BASE_SOURCE = "stage764_stage757_monthly_start_to_20260529"
C_SOURCE = "stage764_stage757_cash_reserve_45w5w_monthly_start"
CANDIDATE_VARIANT = "stage526_500k_total_450k_bucket_50k_reserve_oi_restore_stage764"
MAX_WORKERS = max(1, min(4, int(os.environ.get("STAGE764_MAX_WORKERS", "4"))))
MONTH_LIMIT = max(0, int(os.environ.get("STAGE764_MONTH_LIMIT", "0")))
MONTH_FILTER = {
    item.strip()
    for item in str(os.environ.get("STAGE764_MONTHS", "")).split(",")
    if item.strip()
}

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
BASELINE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_baseline_summary_{MODEL_TAG}.csv"
CANDIDATE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_candidate_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
RESERVE_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_reserve_events_{MODEL_TAG}.csv"
CHECKS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_checks_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"
HEATMAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_heatmap_{MODEL_TAG}.png"


def _patch_stage751_cash_bucket_globals() -> None:
    s751.ANALYSIS_END = ANALYSIS_END
    s751.MONTH_STARTS = MONTH_STARTS
    s751.TOTAL_CAPITAL = TOTAL_CAPITAL
    s751.TRADING_BUCKET_CAPITAL = TRADING_BUCKET_CAPITAL
    s751.RESERVE_CAPITAL = RESERVE_CAPITAL


_patch_stage751_cash_bucket_globals()


def _json_safe(value: Any) -> Any:
    return s749._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s749._md_table(frame, max_rows=max_rows)


def _window_name(start: pd.Timestamp) -> str:
    return f"mstart_{start.strftime('%Y_%m')}"


def _window_label(start: pd.Timestamp) -> str:
    return f"{start.strftime('%Y-%m')} independent start to {ANALYSIS_END.strftime('%Y-%m-%d')}"


def _selected_month_starts() -> list[pd.Timestamp]:
    starts = list(MONTH_STARTS)
    if MONTH_FILTER:
        starts = [item for item in starts if item.strftime("%Y-%m") in MONTH_FILTER]
    if MONTH_LIMIT > 0:
        starts = starts[:MONTH_LIMIT]
    return starts


def _add_month_fields(summary: pd.DataFrame) -> pd.DataFrame:
    frame = summary.copy()
    if "requested_start_month" in frame.columns:
        frame["start_month"] = frame["requested_start_month"].astype(str)
    else:
        frame["start_month"] = pd.to_datetime(frame["analysis_start"], errors="coerce").dt.to_period("M").astype(str)
    start_ts = pd.to_datetime(frame["start_month"] + "-01", errors="coerce")
    frame["start_year"] = start_ts.dt.year
    frame["start_month_num"] = start_ts.dt.month
    frame["positive_return"] = (pd.to_numeric(frame["rebased_total_return_pct"], errors="coerce") > 0.0).astype(int)
    frame["mature_63d"] = (pd.to_numeric(frame["trading_days"], errors="coerce") >= 63).astype(int)
    frame["mature_126d"] = (pd.to_numeric(frame["trading_days"], errors="coerce") >= 126).astype(int)
    frame["mature_252d"] = (pd.to_numeric(frame["trading_days"], errors="coerce") >= 252).astype(int)
    return frame


def _row_to_common(row: dict[str, Any], source_name: str) -> dict[str, Any]:
    out = dict(row)
    out["source_name"] = source_name
    out["rebased_end_equity"] = out["end_equity"]
    out["rebased_total_return_pct"] = out["total_return_pct"]
    out["rebased_cagr_pct"] = out["cagr_pct"]
    out["rebased_max_dd_pct"] = out["max_dd_pct"]
    out["rebased_sharpe"] = out["sharpe"]
    out["rebased_min_equity"] = out["min_equity"]
    out["max_broker10_margin_to_rebased_equity_pct"] = out["max_broker10_margin_to_equity_pct"]
    out["p95_broker10_margin_to_rebased_equity_pct"] = out["p95_broker10_margin_to_equity_pct"]
    out["dd40_pass"] = int(float(out["max_dd_pct"]) >= -40.0)
    out["broker10_90_watch_pass"] = int(float(out["max_broker10_margin_to_equity_pct"]) < 90.0)
    out["nav_end"] = float(out["end_equity"]) / float(out["account_capital"])
    return out


def _curve_to_common(curve: pd.DataFrame, source_name: str) -> pd.DataFrame:
    frame = curve.copy()
    frame["source_name"] = source_name
    frame["rebased_equity"] = frame["account_equity"]
    frame["rebased_nav"] = frame["nav"]
    frame["broker10_margin_to_rebased_equity_pct"] = frame["broker10_margin_to_equity_pct"]
    return frame


def _cash_reserve_spec(metadata: dict[str, Any]) -> Any:
    base = s757._candidate_spec(metadata)
    capital = replace(
        base.capital,
        variant=CANDIDATE_VARIANT,
        label="Stage764 Stage757 OI restore with 450k trading bucket and 50k reserve",
        account_capital=TOTAL_CAPITAL,
        c3_capital=TRADING_BUCKET_CAPITAL,
        risk_multiplier=0.40,
        note=(
            "Stage757 signal/risk restore logic unchanged. The strategy sizes from a 450k trading bucket; "
            "a 50k reserve bucket tops the trading bucket back toward 450k after losses."
        ),
    )
    overrides = dict(base.overrides)
    overrides.update(
        {
            "enable_cash_reserve_bucket": True,
            "cash_reserve_bucket_trading_target": TRADING_BUCKET_CAPITAL,
            "cash_reserve_bucket_initial_reserve": RESERVE_CAPITAL,
            "cash_reserve_bucket_only_after_trade_start": True,
        }
    )
    return replace(base, capital=capital, overrides=overrides, profile="stage757_cash_reserve_45w5w_stage764")


def _run_stage757_month(
    start: pd.Timestamp,
    metadata: dict[str, Any],
    spec: Any,
) -> tuple[dict[str, Any], list[dict[str, Any]], pd.DataFrame]:
    frame, forced_events = s660._run_independent_window(
        spec=spec,
        metadata=metadata,
        analysis_start=start,
        analysis_end=ANALYSIS_END,
    )
    row, curve, costs = s748._metric_row(
        frame,
        spec=spec,
        window_name=_window_name(start),
        window_label=_window_label(start),
        window_group="monthly_start",
        forced_events=forced_events,
    )
    row = _row_to_common(row, BASE_SOURCE)
    row["requested_start_month"] = start.strftime("%Y-%m")
    row["start_month"] = start.strftime("%Y-%m")
    row["arm"] = BASE_ARM
    row["caveat"] = (
        "fresh independent monthly start; Stage757 C50 capital=500k; "
        "risk_multiplier=0.40; loss-streak throttle and recovery sleeve disabled; "
        "OI price confirm restores effective risk to 0.80; unified end=2026-05-29"
    )
    curve = _curve_to_common(curve, BASE_SOURCE)
    curve["requested_start_month"] = start.strftime("%Y-%m")
    curve["start_month"] = start.strftime("%Y-%m")
    curve["arm"] = BASE_ARM
    for cost in costs:
        cost["requested_start_month"] = start.strftime("%Y-%m")
        cost["start_month"] = start.strftime("%Y-%m")
        cost["arm"] = BASE_ARM
        cost["variant"] = spec.capital.variant
    return row, costs, curve


def _run_cash_reserve_month(
    start: pd.Timestamp,
    metadata: dict[str, Any],
    spec: Any,
) -> tuple[dict[str, Any], list[dict[str, Any]], pd.DataFrame, pd.DataFrame]:
    _patch_stage751_cash_bucket_globals()
    frame, forced_events, reserve_events = s751._run_cash_reserve_variant(
        spec=spec,
        metadata=metadata,
        analysis_start=start,
        analysis_end=ANALYSIS_END,
    )
    row, curve, costs = s751._metric_row_cash(
        frame,
        spec=spec,
        window_name=_window_name(start),
        window_label=_window_label(start),
        window_group="monthly_start",
        forced_events=forced_events,
    )
    row = _row_to_common(row, C_SOURCE)
    row["requested_start_month"] = start.strftime("%Y-%m")
    row["start_month"] = start.strftime("%Y-%m")
    row["arm"] = C_ARM
    row["caveat"] = (
        "fresh independent monthly start; Stage757 logic; total capital=500k, "
        "trading bucket=450k, reserve top-up=50k; unified end=2026-05-29"
    )
    curve = _curve_to_common(curve, C_SOURCE)
    curve["requested_start_month"] = start.strftime("%Y-%m")
    curve["start_month"] = start.strftime("%Y-%m")
    curve["arm"] = C_ARM
    for cost in costs:
        cost["requested_start_month"] = start.strftime("%Y-%m")
        cost["start_month"] = start.strftime("%Y-%m")
        cost["arm"] = C_ARM
        cost["variant"] = spec.capital.variant
    return row, costs, curve, reserve_events


def _run_month_pair(
    start_iso: str,
    metadata: dict[str, Any],
    base_spec: Any,
    cash_spec: Any,
    base_c3_overrides: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]], pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    _patch_stage751_cash_bucket_globals()
    s749._install_stable_c3_overrides(base_c3_overrides)
    start = pd.Timestamp(start_iso)
    base_row, base_costs, base_curve = _run_stage757_month(start, metadata, base_spec)
    cash_row, cash_costs, cash_curve, reserve_events = _run_cash_reserve_month(start, metadata, cash_spec)
    return base_row, cash_row, base_costs + cash_costs, base_curve, cash_curve, reserve_events


def _run_monthly_with_retry() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    metadata = s749.s744.s513._metadata()
    base_spec = s757._candidate_spec(metadata)
    cash_spec = _cash_reserve_spec(metadata)
    base_c3_overrides = dict(s749.ORIGINAL_C3_OVERRIDES(MONTH_STARTS[0].to_pydatetime()))
    start_items = [start.strftime("%Y-%m-%d") for start in _selected_month_starts()]

    base_rows: list[dict[str, Any]] = []
    cash_rows: list[dict[str, Any]] = []
    cost_rows: list[dict[str, Any]] = []
    base_curves: list[pd.DataFrame] = []
    cash_curves: list[pd.DataFrame] = []
    reserve_frames: list[pd.DataFrame] = []
    failed: list[tuple[str, str]] = []

    print(
        f"[stage764] launching {len(start_items)} Stage757/base and 45w5w reserve starts "
        f"with workers={MAX_WORKERS}",
        flush=True,
    )
    if MAX_WORKERS == 1:
        for idx, start_iso in enumerate(start_items, start=1):
            try:
                result = _run_month_pair(start_iso, metadata, base_spec, cash_spec, base_c3_overrides)
            except Exception as exc:  # noqa: BLE001
                failed.append((start_iso, repr(exc)))
                print(f"[stage764] failed {idx}/{len(start_items)} {start_iso}: {exc!r}", flush=True)
                continue
            base_row, cash_row, costs, base_curve, cash_curve, reserve_events = result
            base_rows.append(base_row)
            cash_rows.append(cash_row)
            cost_rows.extend(costs)
            base_curves.append(base_curve)
            cash_curves.append(cash_curve)
            if not reserve_events.empty:
                reserve_frames.append(reserve_events)
            print(f"[stage764] completed {idx}/{len(start_items)} {start_iso}", flush=True)
    else:
        with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {
                executor.submit(_run_month_pair, start_iso, metadata, base_spec, cash_spec, base_c3_overrides): start_iso
                for start_iso in start_items
            }
            for idx, future in enumerate(as_completed(futures), start=1):
                start_iso = futures[future]
                try:
                    result = future.result()
                except Exception as exc:  # noqa: BLE001
                    failed.append((start_iso, repr(exc)))
                    print(f"[stage764] failed {idx}/{len(start_items)} {start_iso}: {exc!r}", flush=True)
                    continue
                base_row, cash_row, costs, base_curve, cash_curve, reserve_events = result
                base_rows.append(base_row)
                cash_rows.append(cash_row)
                cost_rows.extend(costs)
                base_curves.append(base_curve)
                cash_curves.append(cash_curve)
                if not reserve_events.empty:
                    reserve_frames.append(reserve_events)
                print(f"[stage764] completed {idx}/{len(start_items)} {start_iso}", flush=True)

    if failed:
        print(f"[stage764] retrying {len(failed)} failed starts serially", flush=True)
    still_failed: list[tuple[str, str]] = []
    completed_months = {str(row.get("start_month", "")) for row in cash_rows}
    for start_iso, _reason in failed:
        start_month = pd.Timestamp(start_iso).strftime("%Y-%m")
        if start_month in completed_months:
            continue
        try:
            result = _run_month_pair(start_iso, metadata, base_spec, cash_spec, base_c3_overrides)
        except Exception as exc:  # noqa: BLE001
            still_failed.append((start_iso, repr(exc)))
            print(f"[stage764] retry failed {start_iso}: {exc!r}", flush=True)
            continue
        base_row, cash_row, costs, base_curve, cash_curve, reserve_events = result
        base_rows.append(base_row)
        cash_rows.append(cash_row)
        cost_rows.extend(costs)
        base_curves.append(base_curve)
        cash_curves.append(cash_curve)
        if not reserve_events.empty:
            reserve_frames.append(reserve_events)
        completed_months.add(start_month)
        print(f"[stage764] retry completed {start_iso}", flush=True)

    if still_failed:
        raise RuntimeError(f"Stage764 starts still failed: {still_failed}")

    baseline = _add_month_fields(pd.DataFrame(base_rows)).sort_values("start_month").reset_index(drop=True)
    candidate = _add_month_fields(pd.DataFrame(cash_rows)).sort_values("start_month").reset_index(drop=True)
    cost = pd.DataFrame(cost_rows).sort_values(["arm", "start_month", "cost_multiplier"]).reset_index(drop=True)
    curves = (
        pd.concat(base_curves + cash_curves, ignore_index=True, sort=False)
        .sort_values(["arm", "start_month", "date"])
        .reset_index(drop=True)
    )
    reserve_events = (
        pd.concat(reserve_frames, ignore_index=True, sort=False)
        .sort_values(["requested_start_month", "date"])
        .reset_index(drop=True)
        if reserve_frames
        else pd.DataFrame()
    )
    return baseline, candidate, cost, curves, reserve_events


def _build_comparison(baseline: pd.DataFrame, candidate: pd.DataFrame) -> pd.DataFrame:
    keep = [
        "start_month",
        "window_name",
        "analysis_start",
        "analysis_end",
        "trading_days",
        "account_capital",
        "nav_end",
        "rebased_end_equity",
        "rebased_total_return_pct",
        "rebased_cagr_pct",
        "rebased_max_dd_pct",
        "rebased_sharpe",
        "max_broker10_margin_to_rebased_equity_pct",
        "p95_broker10_margin_to_rebased_equity_pct",
        "days_over_100pct",
        "days_over_90pct",
        "total_slippage",
        "total_trade_count",
        "nonzero_daily_win_rate_pct",
        "forced_margin_deleverage_count",
        "forced_margin_deleverage_closed_volume",
        "deployable_pass",
        "mature_63d",
        "mature_126d",
        "mature_252d",
        "start_year",
        "start_month_num",
    ]
    candidate_extra = [
        "trading_bucket_capital",
        "reserve_initial_capital",
        "reserve_deployed_end",
        "reserve_remaining_end",
        "reserve_topup_count",
        "first_reserve_topup_date",
        "trading_bucket_end_equity",
        "trading_bucket_max_dd_pct",
        "max_broker10_margin_to_bucket_equity_pct",
    ]
    left = baseline[keep].copy().add_prefix("a_")
    right = candidate[keep + candidate_extra].copy().add_prefix("c_")
    merged = left.merge(right, left_on="a_start_month", right_on="c_start_month", how="inner")
    merged["start_month"] = merged["a_start_month"]
    merged["start_ts"] = pd.to_datetime(merged["start_month"] + "-01", errors="coerce")
    merged["start_year"] = merged["a_start_year"]
    merged["start_month_num"] = merged["a_start_month_num"]
    merged["trading_days"] = merged["a_trading_days"]
    merged["mature_63d"] = merged["a_mature_63d"]
    merged["mature_126d"] = merged["a_mature_126d"]
    merged["mature_252d"] = merged["a_mature_252d"]
    merged["return_delta_pct"] = merged["c_rebased_total_return_pct"] - merged["a_rebased_total_return_pct"]
    merged["return_retention_pct"] = np.where(
        merged["a_rebased_total_return_pct"].abs() > 1e-9,
        merged["c_rebased_total_return_pct"] / merged["a_rebased_total_return_pct"] * 100.0,
        np.nan,
    )
    merged["nav_delta"] = merged["c_nav_end"] - merged["a_nav_end"]
    merged["dd_delta_pp"] = merged["c_rebased_max_dd_pct"] - merged["a_rebased_max_dd_pct"]
    merged["sharpe_delta"] = merged["c_rebased_sharpe"] - merged["a_rebased_sharpe"]
    merged["trade_count_delta"] = merged["c_total_trade_count"] - merged["a_total_trade_count"]
    merged["slippage_delta"] = merged["c_total_slippage"] - merged["a_total_slippage"]
    merged["c_return_wins"] = (merged["return_delta_pct"] > 0.0).astype(int)
    merged["c_dd_wins"] = (merged["dd_delta_pp"] > 0.0).astype(int)
    merged["c_sharpe_wins"] = (merged["sharpe_delta"] > 0.0).astype(int)
    merged["c_both_return_dd_wins"] = (merged["c_return_wins"].eq(1) & merged["c_dd_wins"].eq(1)).astype(int)
    merged["a_both_return_dd_wins"] = (
        merged["return_delta_pct"].lt(0.0) & merged["dd_delta_pp"].lt(0.0)
    ).astype(int)
    merged["c_positive_return"] = (merged["c_rebased_total_return_pct"] > 0.0).astype(int)
    merged["a_positive_return"] = (merged["a_rebased_total_return_pct"] > 0.0).astype(int)
    merged["c_dd30_fail"] = (merged["c_rebased_max_dd_pct"] < -30.0).astype(int)
    merged["a_dd30_fail"] = (merged["a_rebased_max_dd_pct"] < -30.0).astype(int)
    merged["c_dd40_fail"] = (merged["c_rebased_max_dd_pct"] < -40.0).astype(int)
    merged["a_dd40_fail"] = (merged["a_rebased_max_dd_pct"] < -40.0).astype(int)
    return merged.sort_values("start_ts").reset_index(drop=True)


def _candidate_stats(label: str, frame: pd.DataFrame, prefix: str) -> dict[str, Any]:
    if frame.empty:
        return {"bucket": label, "start_count": 0}
    returns = pd.to_numeric(frame[f"{prefix}_rebased_total_return_pct"], errors="coerce")
    dd = pd.to_numeric(frame[f"{prefix}_rebased_max_dd_pct"], errors="coerce")
    return {
        "bucket": label,
        "start_count": int(len(frame)),
        "positive_count": int((returns > 0.0).sum()),
        "positive_rate_pct": float((returns > 0.0).mean() * 100.0),
        "median_return_pct": float(returns.median()),
        "p10_return_pct": float(returns.quantile(0.10)),
        "min_return_pct": float(returns.min()),
        "max_return_pct": float(returns.max()),
        "worst_return_start": str(frame.loc[returns.idxmin(), "start_month"]),
        "best_return_start": str(frame.loc[returns.idxmax(), "start_month"]),
        "median_max_dd_pct": float(dd.median()),
        "worst_max_dd_pct": float(dd.min()),
        "dd30_fail_count": int((dd < -30.0).sum()),
        "dd40_fail_count": int((dd < -40.0).sum()),
    }


def _comparison_stats(label: str, frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {"bucket": label, "start_count": 0}
    ret_delta = pd.to_numeric(frame["return_delta_pct"], errors="coerce")
    dd_delta = pd.to_numeric(frame["dd_delta_pp"], errors="coerce")
    retention = pd.to_numeric(frame["return_retention_pct"], errors="coerce")
    reserve_deployed = pd.to_numeric(frame["c_reserve_deployed_end"], errors="coerce").fillna(0.0)
    return {
        "bucket": label,
        "start_count": int(len(frame)),
        "c_return_win_count": int(frame["c_return_wins"].sum()),
        "c_return_win_rate_pct": float(frame["c_return_wins"].mean() * 100.0),
        "c_dd_win_count": int(frame["c_dd_wins"].sum()),
        "c_dd_win_rate_pct": float(frame["c_dd_wins"].mean() * 100.0),
        "c_sharpe_win_count": int(frame["c_sharpe_wins"].sum()),
        "c_both_return_dd_win_count": int(frame["c_both_return_dd_wins"].sum()),
        "a_both_return_dd_win_count": int(frame["a_both_return_dd_wins"].sum()),
        "c_positive_count": int(frame["c_positive_return"].sum()),
        "a_positive_count": int(frame["a_positive_return"].sum()),
        "c_dd30_fail_count": int(frame["c_dd30_fail"].sum()),
        "a_dd30_fail_count": int(frame["a_dd30_fail"].sum()),
        "c_dd40_fail_count": int(frame["c_dd40_fail"].sum()),
        "a_dd40_fail_count": int(frame["a_dd40_fail"].sum()),
        "median_return_delta_pct": float(ret_delta.median()),
        "p10_return_delta_pct": float(ret_delta.quantile(0.10)),
        "median_return_retention_pct": float(retention.median()),
        "median_dd_delta_pp": float(dd_delta.median()),
        "worst_dd_delta_pp": float(dd_delta.min()),
        "best_dd_delta_pp": float(dd_delta.max()),
        "reserve_used_count": int(reserve_deployed.gt(0.0).sum()),
        "median_reserve_deployed": float(reserve_deployed.median()),
        "max_reserve_deployed": float(reserve_deployed.max()),
        "worst_return_delta_start": str(frame.loc[ret_delta.idxmin(), "start_month"]),
        "best_return_delta_start": str(frame.loc[ret_delta.idxmax(), "start_month"]),
    }


def _checks(comparison: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = [
        _candidate_stats("a_stage757_all_monthly_starts", comparison, "a"),
        _candidate_stats("c_45w5w_all_monthly_starts", comparison, "c"),
        _candidate_stats("a_stage757_mature_ge252_trading_days", comparison[comparison["mature_252d"].eq(1)], "a"),
        _candidate_stats("c_45w5w_mature_ge252_trading_days", comparison[comparison["mature_252d"].eq(1)], "c"),
        _comparison_stats("vs_stage757_all_monthly_starts", comparison),
        _comparison_stats("vs_stage757_mature_ge63_trading_days", comparison[comparison["mature_63d"].eq(1)]),
        _comparison_stats("vs_stage757_mature_ge126_trading_days", comparison[comparison["mature_126d"].eq(1)]),
        _comparison_stats("vs_stage757_mature_ge252_trading_days", comparison[comparison["mature_252d"].eq(1)]),
    ]
    for year, group in comparison.groupby("start_year", sort=True):
        rows.append(_comparison_stats(f"vs_stage757_start_year_{int(year)}", group))
    focus = comparison[comparison["start_month"].eq("2022-05")]
    if not focus.empty:
        row = focus.iloc[0]
        rows.append(
            {
                "bucket": "focus_2022_05",
                "start_count": 1,
                "c_return_win_count": int(row["c_return_wins"]),
                "c_dd_win_count": int(row["c_dd_wins"]),
                "median_return_delta_pct": float(row["return_delta_pct"]),
                "median_return_retention_pct": float(row["return_retention_pct"]),
                "median_dd_delta_pp": float(row["dd_delta_pp"]),
                "reserve_used_count": int(float(row["c_reserve_deployed_end"]) > 0.0),
                "median_reserve_deployed": float(row["c_reserve_deployed_end"]),
                "max_reserve_deployed": float(row["c_reserve_deployed_end"]),
            }
        )
    return pd.DataFrame(rows)


def _decision(comparison: pd.DataFrame, checks: pd.DataFrame) -> dict[str, Any]:
    mature_cmp = checks[checks["bucket"].eq("vs_stage757_mature_ge252_trading_days")].iloc[0]
    all_cmp = checks[checks["bucket"].eq("vs_stage757_all_monthly_starts")].iloc[0]
    c_all = checks[checks["bucket"].eq("c_45w5w_all_monthly_starts")].iloc[0]
    hard_fail: list[str] = []
    watch: list[str] = []
    if int(mature_cmp["c_return_win_count"]) < int(mature_cmp["start_count"]) * 0.45:
        hard_fail.append("mature252_c_return_wins_lt45pct_vs_stage757")
    if float(mature_cmp["median_return_delta_pct"]) < 0.0:
        hard_fail.append("mature252_median_return_delta_negative_vs_stage757")
    if int(mature_cmp["c_dd40_fail_count"]) > int(mature_cmp["a_dd40_fail_count"]):
        watch.append("mature252_c_dd40_fail_more_than_stage757")
    if int(all_cmp["c_both_return_dd_win_count"]) <= int(all_cmp["a_both_return_dd_win_count"]):
        watch.append("all_c_both_wins_not_more_than_stage757_both_wins")
    if int(c_all["positive_count"]) < int(c_all["start_count"]) * 0.85:
        watch.append("c_all_positive_rate_lt85pct")
    decision = "stage757_cash_reserve_45w5w_not_promoted" if hard_fail else "stage757_cash_reserve_45w5w_watch"
    return {
        "stage": "Stage764",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "baseline": s757.CANDIDATE_VARIANT,
        "candidate": CANDIDATE_VARIANT,
        "analysis_start_first": _selected_month_starts()[0].strftime("%Y-%m-%d"),
        "analysis_start_last": _selected_month_starts()[-1].strftime("%Y-%m-%d"),
        "analysis_end": ANALYSIS_END.strftime("%Y-%m-%d"),
        "monthly_start_count": len(comparison),
        "decision": decision,
        "hard_fail_checks": hard_fail,
        "watch_checks": watch,
        "change": {
            "official_config_changed": False,
            "ctp_connected": False,
            "order_api_called": False,
            "baseline_account_capital": TOTAL_CAPITAL,
            "baseline_c3_capital": TOTAL_CAPITAL,
            "candidate_total_capital": TOTAL_CAPITAL,
            "candidate_trading_bucket_capital": TRADING_BUCKET_CAPITAL,
            "candidate_reserve_capital": RESERVE_CAPITAL,
            "base_risk_multiplier": 0.40,
            "oi_confirm_restored_effective_multiplier": 0.80,
            "loss_streak_throttle_enabled": False,
            "recovery_sleeve_enabled": False,
            "enable_oi_price_confirm_risk_restore": True,
        },
        "checks": checks.to_dict("records"),
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "baseline_summary": str(BASELINE_SUMMARY_PATH),
            "candidate_summary": str(CANDIDATE_SUMMARY_PATH),
            "cost": str(COST_PATH),
            "comparison": str(COMPARISON_PATH),
            "curves": str(CURVES_PATH),
            "reserve_events": str(RESERVE_EVENTS_PATH),
            "checks": str(CHECKS_PATH),
            "report": str(REPORT_PATH),
            "chart": str(CHART_PATH),
            "heatmap": str(HEATMAP_PATH),
            "decision": str(DECISION_PATH),
        },
    }


def _heat_values(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    return (
        frame.pivot_table(index="start_year", columns="start_month_num", values=column, aggfunc="first")
        .sort_index()
        .reindex(columns=list(range(1, 13)))
    )


def _plot_heatmap(comparison: pd.DataFrame) -> None:
    specs = [
        (_heat_values(comparison, "c_rebased_total_return_pct"), "C 45w/5w total return %", "Return %", "{:.0f}"),
        (_heat_values(comparison, "return_delta_pct"), "C - Stage757 total return pp", "Return pp", "{:.0f}"),
        (_heat_values(comparison, "c_reserve_deployed_end"), "C reserve deployed by end", "Reserve", "{:.0f}"),
    ]
    fig, axes = plt.subplots(3, 1, figsize=(17, 12))
    for ax, (table, title, cbar_label, fmt) in zip(axes, specs):
        values = table.to_numpy(dtype=float)
        finite = values[np.isfinite(values)]
        if "C - Stage757" in title:
            limit = max(float(np.nanpercentile(np.abs(finite), 90)), 1.0) if finite.size else 1.0
            norm = TwoSlopeNorm(vmin=-limit, vcenter=0.0, vmax=limit)
            cmap = "RdYlGn"
        elif "reserve" in title.lower():
            norm = None
            cmap = "Blues"
        else:
            vmax = max(float(np.nanpercentile(finite, 95)), 100.0) if finite.size else 100.0
            vmin = min(float(np.nanpercentile(finite, 5)), -30.0) if finite.size else -30.0
            norm = TwoSlopeNorm(vmin=vmin, vcenter=0.0, vmax=vmax)
            cmap = "RdYlGn"
        image = ax.imshow(values, aspect="auto", cmap=cmap, norm=norm)
        ax.set_title(title)
        ax.set_yticks(np.arange(len(table.index)))
        ax.set_yticklabels([str(int(item)) for item in table.index])
        ax.set_xticks(np.arange(12))
        ax.set_xticklabels([str(i) for i in range(1, 13)])
        ax.set_xlabel("Start month")
        ax.set_ylabel("Start year")
        for y in range(values.shape[0]):
            for x in range(values.shape[1]):
                value = values[y, x]
                if not np.isfinite(value):
                    continue
                ax.text(x, y, fmt.format(value), ha="center", va="center", fontsize=8, color="#111827")
        fig.colorbar(image, ax=ax, fraction=0.018, pad=0.01, label=cbar_label)
    fig.suptitle("Stage764 monthly-start heatmaps to 2026-05-29", fontsize=15)
    fig.tight_layout(rect=(0, 0, 1, 0.955))
    fig.savefig(HEATMAP_PATH, dpi=170)
    plt.close(fig)


def _plot_chart(comparison: pd.DataFrame) -> None:
    data = comparison.sort_values("start_ts").copy()
    x = np.arange(len(data))
    labels = data["start_month"].tolist()
    tick_idx = [idx for idx, label in enumerate(labels) if label.endswith("-01") or idx == len(labels) - 1]

    fig, axes = plt.subplots(5, 1, figsize=(18, 16), sharex=True)
    ax_ret, ax_delta, ax_dd, ax_reserve, ax_margin = axes
    ax_ret.plot(x, data["a_rebased_total_return_pct"], color="#2563eb", linewidth=1.8, label="A Stage757 return")
    ax_ret.plot(x, data["c_rebased_total_return_pct"], color="#059669", linewidth=1.8, label="C 45w/5w return")
    ax_ret.axhline(0.0, color="#111827", linewidth=0.8)
    ax_ret.set_ylabel("Total return %")
    ax_ret.set_title("Monthly independent starts to 2026-05-29: total return")
    ax_ret.grid(axis="y", alpha=0.25)
    ax_ret.legend(loc="upper right")

    colors = np.where(data["return_delta_pct"] >= 0.0, "#059669", "#dc2626")
    ax_delta.bar(x, data["return_delta_pct"], color=colors, alpha=0.88, width=0.82)
    ax_delta.axhline(0.0, color="#111827", linewidth=0.9)
    ax_delta.set_ylabel("C - A return pp")
    ax_delta.set_title("Return difference: green means 45w/5w beats Stage757")
    ax_delta.grid(axis="y", alpha=0.22)

    ax_dd.plot(x, data["a_rebased_max_dd_pct"], color="#2563eb", linewidth=1.7, label="A Stage757 max DD")
    ax_dd.plot(x, data["c_rebased_max_dd_pct"], color="#059669", linewidth=1.7, label="C 45w/5w max DD")
    ax_dd.axhline(-30.0, color="#f97316", linestyle="--", linewidth=0.9, label="DD -30%")
    ax_dd.axhline(-40.0, color="#dc2626", linestyle="--", linewidth=0.9, label="DD -40%")
    ax_dd.set_ylabel("Max DD %")
    ax_dd.set_title("Account-level max drawdown by start month")
    ax_dd.grid(axis="y", alpha=0.25)
    ax_dd.legend(loc="lower right", ncol=2)

    ax_reserve.bar(x, data["c_reserve_deployed_end"], color="#2563eb", alpha=0.82, width=0.82)
    ax_reserve.axhline(RESERVE_CAPITAL, color="#64748b", linestyle="--", linewidth=0.9)
    ax_reserve.set_ylabel("Reserve used")
    ax_reserve.set_title("Reserve deployed by end of each independent start")
    ax_reserve.grid(axis="y", alpha=0.22)

    ax_margin.plot(
        x,
        data["a_max_broker10_margin_to_rebased_equity_pct"],
        color="#2563eb",
        linewidth=1.6,
        label="A account margin peak",
    )
    ax_margin.plot(
        x,
        data["c_max_broker10_margin_to_rebased_equity_pct"],
        color="#059669",
        linewidth=1.6,
        label="C account margin peak",
    )
    ax_margin.plot(
        x,
        data["c_max_broker10_margin_to_bucket_equity_pct"],
        color="#ea580c",
        linewidth=1.2,
        linestyle="--",
        label="C bucket margin peak",
    )
    ax_margin.axhline(100.0, color="#dc2626", linestyle="--", linewidth=0.9)
    ax_margin.set_ylabel("Broker10 margin %")
    ax_margin.set_title("Margin pressure: account level vs active trading bucket")
    ax_margin.grid(axis="y", alpha=0.22)
    ax_margin.legend(loc="upper right", ncol=3)
    ax_margin.set_xticks(tick_idx)
    ax_margin.set_xticklabels([labels[i] for i in tick_idx], rotation=45, ha="right")

    mature = data[data["mature_252d"].eq(1)]
    fig.suptitle(
        (
            "Stage764 Stage757 + 45w/5w reserve | "
            f"C return wins {int(data['c_return_wins'].sum())}/{len(data)}, "
            f"mature wins {int(mature['c_return_wins'].sum())}/{len(mature)}, "
            f"median reserve used {data['c_reserve_deployed_end'].median():,.0f}"
        ),
        fontsize=15,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.965))
    fig.savefig(CHART_PATH, dpi=170)
    plt.close(fig)


def _write_report(
    baseline: pd.DataFrame,
    candidate: pd.DataFrame,
    cost: pd.DataFrame,
    comparison: pd.DataFrame,
    checks: pd.DataFrame,
    reserve_events: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    columns = [
        "start_month",
        "trading_days",
        "a_nav_end",
        "c_nav_end",
        "a_rebased_total_return_pct",
        "c_rebased_total_return_pct",
        "return_delta_pct",
        "return_retention_pct",
        "a_rebased_max_dd_pct",
        "c_rebased_max_dd_pct",
        "dd_delta_pp",
        "a_rebased_sharpe",
        "c_rebased_sharpe",
        "sharpe_delta",
        "a_total_trade_count",
        "c_total_trade_count",
        "trade_count_delta",
        "c_reserve_deployed_end",
        "c_reserve_topup_count",
        "c_first_reserve_topup_date",
    ]
    reserve_cols = [
        "requested_start_month",
        "date",
        "estimated_equity_before",
        "injection",
        "estimated_equity_after",
        "reserve_remaining_after",
        "topup_count",
    ]
    lines = [
        "# Stage764 Stage757 + 45万交易桶/5万备用金逐月启动验证",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        f"- A：`{s757.CANDIDATE_VARIANT}`，Stage757 原始 50万 C50，统一终点 `{ANALYSIS_END.strftime('%Y-%m-%d')}`。",
        f"- C：`{CANDIDATE_VARIANT}`，Stage757 信号和 OI 风险恢复不变；只把资金结构改为 45万交易桶 + 5万备用桶。",
        f"- 起点范围：`{_selected_month_starts()[0].strftime('%Y-%m')}` 至 `{_selected_month_starts()[-1].strftime('%Y-%m')}`，共 `{len(comparison)}` 个逐月独立启动。",
        "- 不修改正式配置、不连接 CTP、不调用下单。",
        "",
        "## 外部调研判断",
        "",
        "- 固定比例/固定风险 sizing 会把早期亏损机械传导到后续风险预算和整数手数。",
        "- 备用金是资金管理和路径风险工具，不是 alpha；它的合理性必须通过多起点验证，而不是单一路径胜出。",
        "- 本次只验证用户指定的 `45/5` 结构，不继续扫比例，防止用红框窗口救参数。",
        "",
        "## 检查聚合",
        "",
        _md_table(checks, max_rows=60),
        "",
        "## 2022-05 重点起点",
        "",
        _md_table(comparison[comparison["start_month"].eq("2022-05")][columns], max_rows=5),
        "",
        "## 最伤收益的起点",
        "",
        _md_table(comparison.sort_values("return_delta_pct").head(15)[columns], max_rows=15),
        "",
        "## 收益相对最好的起点",
        "",
        _md_table(comparison.sort_values("return_delta_pct", ascending=False).head(15)[columns], max_rows=15),
        "",
        "## 全部月起点明细",
        "",
        _md_table(comparison[columns], max_rows=90),
        "",
        "## 成本压力",
        "",
        _md_table(cost, max_rows=120),
        "",
        "## 备用桶事件样例",
        "",
        _md_table(reserve_events[reserve_cols].head(80) if not reserve_events.empty else reserve_events, max_rows=80),
        "",
        "## 决策",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- hard_fail_checks：`{', '.join(decision['hard_fail_checks']) or '无'}`",
        f"- watch_checks：`{', '.join(decision['watch_checks']) or '无'}`",
        "",
        "## 输出",
        "",
        f"- chart：`{CHART_PATH}`",
        f"- heatmap：`{HEATMAP_PATH}`",
        f"- comparison：`{COMPARISON_PATH}`",
        f"- reserve_events：`{RESERVE_EVENTS_PATH}`",
        f"- baseline_rows：`{len(baseline)}`；candidate_rows：`{len(candidate)}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    baseline, candidate, cost, curves, reserve_events = _run_monthly_with_retry()
    comparison = _build_comparison(baseline, candidate)
    checks = _checks(comparison)
    decision = _decision(comparison, checks)

    summary = pd.concat([baseline, candidate], ignore_index=True, sort=False)
    _plot_chart(comparison)
    _plot_heatmap(comparison)
    _write_report(baseline, candidate, cost, comparison, checks, reserve_events, decision)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    baseline.to_csv(BASELINE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    candidate.to_csv(CANDIDATE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    reserve_events.to_csv(RESERVE_EVENTS_PATH, index=False, encoding="utf-8-sig")
    checks.to_csv(CHECKS_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("CHECKS")
    print(checks.to_string(index=False))
    print("\nDECISION")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
