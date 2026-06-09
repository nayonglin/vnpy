from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
import json
import os
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage744_official_monthly_start_audit as s744
import analyze_qmt_roll_stage747_half_risk_no_streak_monthly_start_compare as s747
import analyze_qmt_roll_stage748_half_risk_no_streak_500k as s748
import analyze_qmt_roll_stage746_half_risk_no_streak_multiperiod as s746
import analyze_qmt_roll_stage660_stage653_multiperiod_live_audit as s660


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage749_half_risk_no_streak_500k_monthly_start_compare_v1"
OUTPUT_PREFIX = "qmt_roll_stage749_half_risk_no_streak_500k_monthly_start_compare"
LINE_ID = "futures_trend_quarter_risk_no_streak"

ANALYSIS_END = s744.ANALYSIS_END
MONTH_STARTS = s744.MONTH_STARTS

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CANDIDATE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_candidate_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
COMPARISON_C20_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_c20_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
CHECKS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_checks_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"
HEATMAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_heatmap_{MODEL_TAG}.png"
C20_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_c20_chart_{MODEL_TAG}.png"

A_ARM = "A_official_20w"
C_ARM = "C50_r040_no_streak"
MAX_WORKERS = max(1, min(4, int(os.environ.get("STAGE749_MAX_WORKERS", "4"))))
ORIGINAL_C3_OVERRIDES = s660.s653.s513._c3_overrides


def _json_safe(value: Any) -> Any:
    return s744._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s744._md_table(frame, max_rows=max_rows)


def _window_name(start: pd.Timestamp) -> str:
    return f"mstart_{start.strftime('%Y_%m')}"


def _window_label(start: pd.Timestamp) -> str:
    return f"{start.strftime('%Y-%m')} independent start to {ANALYSIS_END.strftime('%Y-%m-%d')}"


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


def _official_summary() -> pd.DataFrame:
    for path in (s744.SUMMARY_PATH, s744.CURVES_PATH):
        if not path.exists():
            raise FileNotFoundError(f"missing Stage744 official monthly output: {path}")
    frame = pd.read_csv(s744.SUMMARY_PATH, encoding="utf-8-sig")
    frame = frame[frame["window_group"].astype(str).eq("monthly_start")].copy()
    frame["arm"] = A_ARM
    frame["variant"] = s746.BASE_VARIANT
    frame["account_capital"] = float(s744.OFFICIAL_LIVE_CAPITAL)
    frame["nav_end"] = pd.to_numeric(frame["rebased_end_equity"], errors="coerce") / float(s744.OFFICIAL_LIVE_CAPITAL)
    return _add_month_fields(frame)


def _official_curves() -> pd.DataFrame:
    frame = pd.read_csv(s744.CURVES_PATH, encoding="utf-8-sig")
    frame["arm"] = A_ARM
    frame["variant"] = s746.BASE_VARIANT
    frame["account_capital"] = float(s744.OFFICIAL_LIVE_CAPITAL)
    frame["start_month"] = frame["requested_start_month"].astype(str)
    return frame


def _candidate_row_to_common(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    out["source_name"] = "stage749_half_risk_no_streak_500k_monthly_start"
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
    out["caveat"] = (
        "fresh independent monthly start; Stage748 C50 capital=500k; "
        "risk_multiplier=0.40; loss-streak throttle and recovery sleeve disabled"
    )
    return out


def _candidate_curve_to_common(curve: pd.DataFrame) -> pd.DataFrame:
    frame = curve.copy()
    frame["source_name"] = "stage749_half_risk_no_streak_500k_monthly_start"
    frame["rebased_equity"] = frame["account_equity"]
    frame["rebased_nav"] = frame["nav"]
    frame["broker10_margin_to_rebased_equity_pct"] = frame["broker10_margin_to_equity_pct"]
    return frame


def _install_stable_c3_overrides(base_overrides: dict[str, Any]) -> None:
    # The original helper rebuilds shared universe/eligibility CSV files.
    # In ProcessPool workers that can race with strategy startup reads, so
    # workers reuse prebuilt paths and only update the start-date field.
    def stable_overrides(analysis_start: Any) -> dict[str, Any]:
        overrides = dict(base_overrides)
        start = pd.Timestamp(analysis_start)
        overrides["trade_start_date"] = start.date().isoformat()
        return overrides

    s660.s653.s513._c3_overrides = stable_overrides
    s660.s513._c3_overrides = stable_overrides


def _run_candidate_month(
    start_iso: str,
    metadata: dict[str, Any],
    spec: s660.s653.ForcedVariant,
    base_c3_overrides: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], pd.DataFrame]:
    _install_stable_c3_overrides(base_c3_overrides)
    start = pd.Timestamp(start_iso)
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
    row = _candidate_row_to_common(row)
    row["requested_start_month"] = start.strftime("%Y-%m")
    row["start_month"] = start.strftime("%Y-%m")
    row["arm"] = C_ARM

    curve = _candidate_curve_to_common(curve)
    curve["requested_start_month"] = start.strftime("%Y-%m")
    curve["start_month"] = start.strftime("%Y-%m")
    curve["arm"] = C_ARM

    for cost in costs:
        cost["requested_start_month"] = start.strftime("%Y-%m")
        cost["start_month"] = start.strftime("%Y-%m")
        cost["arm"] = C_ARM
        cost["variant"] = spec.capital.variant
    return row, costs, curve


def _run_candidate_monthly() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    metadata = s744.s513._metadata()
    spec = s748._candidate_500k_spec(metadata)
    base_c3_overrides = dict(ORIGINAL_C3_OVERRIDES(MONTH_STARTS[0].to_pydatetime()))
    summary_rows: list[dict[str, Any]] = []
    cost_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []

    start_items = [start.strftime("%Y-%m-%d") for start in MONTH_STARTS]
    print(f"[stage749] launching {len(start_items)} monthly starts with workers={MAX_WORKERS}", flush=True)
    if MAX_WORKERS == 1:
        for idx, start_iso in enumerate(start_items, start=1):
            print(f"[stage749] running {idx}/{len(start_items)} {_window_name(pd.Timestamp(start_iso))}", flush=True)
            row, costs, curve = _run_candidate_month(start_iso, metadata, spec, base_c3_overrides)
            summary_rows.append(row)
            cost_rows.extend(costs)
            curve_frames.append(curve)
    else:
        with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {
                executor.submit(_run_candidate_month, start_iso, metadata, spec, base_c3_overrides): start_iso
                for start_iso in start_items
            }
            for idx, future in enumerate(as_completed(futures), start=1):
                start_iso = futures[future]
                row, costs, curve = future.result()
                summary_rows.append(row)
                cost_rows.extend(costs)
                curve_frames.append(curve)
                print(f"[stage749] completed {idx}/{len(start_items)} {_window_name(pd.Timestamp(start_iso))}", flush=True)

    candidate = _add_month_fields(pd.DataFrame(summary_rows)).sort_values("start_month").reset_index(drop=True)
    cost = pd.DataFrame(cost_rows).sort_values(["start_month", "cost_multiplier"]).reset_index(drop=True)
    curves = (
        pd.concat(curve_frames, ignore_index=True, sort=False)
        .sort_values(["start_month", "date"])
        .reset_index(drop=True)
    )
    return candidate, cost, curves


def _build_comparison(official: pd.DataFrame, candidate: pd.DataFrame) -> pd.DataFrame:
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
    left = official[keep].copy().add_prefix("a_")
    right = candidate[keep].copy().add_prefix("c_")
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
    merged["margin_peak_delta_pp"] = (
        merged["c_max_broker10_margin_to_rebased_equity_pct"]
        - merged["a_max_broker10_margin_to_rebased_equity_pct"]
    )
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


def _build_c20_comparison(candidate_50: pd.DataFrame) -> pd.DataFrame:
    if not s747.CANDIDATE_SUMMARY_PATH.exists():
        raise FileNotFoundError(f"missing Stage747 C20 monthly output: {s747.CANDIDATE_SUMMARY_PATH}")
    c20 = pd.read_csv(s747.CANDIDATE_SUMMARY_PATH, encoding="utf-8-sig")
    c20 = _add_month_fields(c20)
    c20["account_capital"] = 200_000.0
    c20["nav_end"] = pd.to_numeric(c20["rebased_end_equity"], errors="coerce") / 200_000.0

    keep = [
        "start_month",
        "trading_days",
        "account_capital",
        "nav_end",
        "rebased_total_return_pct",
        "rebased_max_dd_pct",
        "rebased_sharpe",
        "total_trade_count",
        "total_slippage",
        "max_broker10_margin_to_rebased_equity_pct",
        "mature_252d",
        "start_year",
    ]
    left = c20[keep].copy().add_prefix("c20_")
    right = candidate_50[keep].copy().add_prefix("c50_")
    merged = left.merge(right, left_on="c20_start_month", right_on="c50_start_month", how="inner")
    merged["start_month"] = merged["c50_start_month"]
    merged["start_ts"] = pd.to_datetime(merged["start_month"] + "-01", errors="coerce")
    merged["start_year"] = merged["c50_start_year"]
    merged["mature_252d"] = merged["c50_mature_252d"]
    merged["return_delta_pct"] = merged["c50_rebased_total_return_pct"] - merged["c20_rebased_total_return_pct"]
    merged["dd_delta_pp"] = merged["c50_rebased_max_dd_pct"] - merged["c20_rebased_max_dd_pct"]
    merged["sharpe_delta"] = merged["c50_rebased_sharpe"] - merged["c20_rebased_sharpe"]
    merged["trade_count_delta"] = merged["c50_total_trade_count"] - merged["c20_total_trade_count"]
    merged["slippage_delta"] = merged["c50_total_slippage"] - merged["c20_total_slippage"]
    merged["c50_return_wins"] = (merged["return_delta_pct"] > 0.0).astype(int)
    merged["c50_dd_wins"] = (merged["dd_delta_pp"] > 0.0).astype(int)
    return merged.sort_values("start_ts").reset_index(drop=True)


def _bucket_stats(label: str, frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {"bucket": label, "start_count": 0}
    ret_delta = pd.to_numeric(frame["return_delta_pct"], errors="coerce")
    dd_delta = pd.to_numeric(frame["dd_delta_pp"], errors="coerce")
    retention = pd.to_numeric(frame["return_retention_pct"], errors="coerce") if "return_retention_pct" in frame else pd.Series(dtype=float)
    return {
        "bucket": label,
        "start_count": int(len(frame)),
        "c_return_win_count": int(frame["c_return_wins"].sum()),
        "c_return_win_rate_pct": float(frame["c_return_wins"].mean() * 100.0),
        "c_dd_win_count": int(frame["c_dd_wins"].sum()),
        "c_dd_win_rate_pct": float(frame["c_dd_wins"].mean() * 100.0),
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
        "median_return_retention_pct": float(retention.median()) if not retention.empty else np.nan,
        "median_dd_delta_pp": float(dd_delta.median()),
        "worst_dd_delta_pp": float(dd_delta.min()),
        "best_dd_delta_pp": float(dd_delta.max()),
        "worst_return_delta_start": str(frame.loc[ret_delta.idxmin(), "start_month"]),
        "best_return_delta_start": str(frame.loc[ret_delta.idxmax(), "start_month"]),
    }


def _checks(comparison: pd.DataFrame, c20_comparison: pd.DataFrame) -> pd.DataFrame:
    rows = [
        _bucket_stats("all_monthly_starts", comparison),
        _bucket_stats("mature_ge63_trading_days", comparison[comparison["mature_63d"].eq(1)]),
        _bucket_stats("mature_ge126_trading_days", comparison[comparison["mature_126d"].eq(1)]),
        _bucket_stats("mature_ge252_trading_days", comparison[comparison["mature_252d"].eq(1)]),
    ]
    for year, group in comparison.groupby("start_year", sort=True):
        rows.append(_bucket_stats(f"start_year_{int(year)}", group))
    checks = pd.DataFrame(rows)

    c20_all = {
        "bucket": "c50_vs_c20_all_monthly_starts",
        "start_count": int(len(c20_comparison)),
        "c_return_win_count": int(c20_comparison["c50_return_wins"].sum()),
        "c_return_win_rate_pct": float(c20_comparison["c50_return_wins"].mean() * 100.0),
        "c_dd_win_count": int(c20_comparison["c50_dd_wins"].sum()),
        "c_dd_win_rate_pct": float(c20_comparison["c50_dd_wins"].mean() * 100.0),
        "median_return_delta_pct": float(pd.to_numeric(c20_comparison["return_delta_pct"], errors="coerce").median()),
        "median_dd_delta_pp": float(pd.to_numeric(c20_comparison["dd_delta_pp"], errors="coerce").median()),
        "median_trade_count_delta": float(pd.to_numeric(c20_comparison["trade_count_delta"], errors="coerce").median()),
    }
    c20_mature = c20_comparison[c20_comparison["mature_252d"].eq(1)]
    c20_mature_row = {
        "bucket": "c50_vs_c20_mature_ge252_trading_days",
        "start_count": int(len(c20_mature)),
        "c_return_win_count": int(c20_mature["c50_return_wins"].sum()),
        "c_return_win_rate_pct": float(c20_mature["c50_return_wins"].mean() * 100.0),
        "c_dd_win_count": int(c20_mature["c50_dd_wins"].sum()),
        "c_dd_win_rate_pct": float(c20_mature["c50_dd_wins"].mean() * 100.0),
        "median_return_delta_pct": float(pd.to_numeric(c20_mature["return_delta_pct"], errors="coerce").median()),
        "median_dd_delta_pp": float(pd.to_numeric(c20_mature["dd_delta_pp"], errors="coerce").median()),
        "median_trade_count_delta": float(pd.to_numeric(c20_mature["trade_count_delta"], errors="coerce").median()),
    }
    return pd.concat([checks, pd.DataFrame([c20_all, c20_mature_row])], ignore_index=True, sort=False)


def _decision(comparison: pd.DataFrame, checks: pd.DataFrame) -> dict[str, Any]:
    all_row = checks[checks["bucket"].eq("all_monthly_starts")].iloc[0]
    mature_row = checks[checks["bucket"].eq("mature_ge252_trading_days")].iloc[0]
    full = comparison[comparison["start_month"].eq("2020-01")].iloc[0]
    hard_fail: list[str] = []
    watch: list[str] = []
    if float(full["return_retention_pct"]) < 35.0:
        hard_fail.append("full_2020_01_return_retention_lt35")
    if int(full["c_dd30_fail"]) == 1:
        hard_fail.append("full_2020_01_c_dd30_fail")
    if int(mature_row["c_return_win_count"]) < int(mature_row["start_count"]) * 0.45:
        hard_fail.append("mature252_c_return_wins_lt45pct")
    if float(mature_row["median_return_delta_pct"]) < 0.0:
        hard_fail.append("mature252_median_return_delta_negative")
    if int(mature_row["c_dd30_fail_count"]) > int(mature_row["a_dd30_fail_count"]):
        watch.append("mature252_c_dd30_fail_more_than_official")
    if int(all_row["c_both_return_dd_win_count"]) <= int(all_row["a_both_return_dd_win_count"]):
        watch.append("all_c_both_wins_not_more_than_a_both_wins")
    decision = "half_risk_no_streak_500k_monthly_start_not_promoted" if hard_fail else "half_risk_no_streak_500k_monthly_start_watch"
    return {
        "stage": "Stage438",
        "script_stage": "Stage749",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "baseline": s746.BASE_VARIANT,
        "candidate_500k": s748.CANDIDATE_500K_VARIANT,
        "analysis_start_first": MONTH_STARTS[0].strftime("%Y-%m-%d"),
        "analysis_start_last": MONTH_STARTS[-1].strftime("%Y-%m-%d"),
        "analysis_end": ANALYSIS_END.strftime("%Y-%m-%d"),
        "monthly_start_count": len(comparison),
        "decision": decision,
        "hard_fail_checks": hard_fail,
        "watch_checks": watch,
        "change": {
            "official_config_changed": False,
            "ctp_connected": False,
            "order_api_called": False,
            "official_results_reused_from_stage744": True,
            "c20_results_reused_from_stage747": True,
            "account_capital_before": 200_000.0,
            "account_capital_after": s748.CAPITAL_500K,
            "risk_multiplier": s746.HALF_FORMAL_RISK_MULTIPLIER,
            "streak_risk_multipliers": s746.NO_STREAK_MULTIPLIERS,
            "enable_streak_entry_structure_risk_recovery": False,
            "enable_recovery_sleeve": False,
        },
        "checks": checks.to_dict("records"),
        "full_2020_01": full.to_dict(),
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "candidate_summary": str(CANDIDATE_SUMMARY_PATH),
            "cost": str(COST_PATH),
            "comparison": str(COMPARISON_PATH),
            "comparison_c20": str(COMPARISON_C20_PATH),
            "curves": str(CURVES_PATH),
            "checks": str(CHECKS_PATH),
            "report": str(REPORT_PATH),
            "chart": str(CHART_PATH),
            "heatmap": str(HEATMAP_PATH),
            "c20_chart": str(C20_CHART_PATH),
            "decision": str(DECISION_PATH),
        },
    }


def _plot_main(comparison: pd.DataFrame) -> None:
    data = comparison.sort_values("start_ts").copy()
    x = np.arange(len(data))
    labels = data["start_month"].tolist()
    tick_idx = [idx for idx, label in enumerate(labels) if label.endswith("-01") or idx == len(labels) - 1]

    fig, axes = plt.subplots(4, 1, figsize=(18, 14), sharex=True)
    ax_ret, ax_delta, ax_dd, ax_dd_delta = axes

    ax_ret.plot(x, data["a_rebased_total_return_pct"], color="#ea580c", linewidth=1.8, label="A official 20w return")
    ax_ret.plot(x, data["c_rebased_total_return_pct"], color="#059669", linewidth=1.8, label="C50 return")
    ax_ret.axhline(0.0, color="#111827", linewidth=0.8)
    ax_ret.set_ylabel("Total return %")
    ax_ret.set_title("Monthly independent starts to 2026-04-30: total return")
    ax_ret.grid(axis="y", alpha=0.25)
    ax_ret.legend(loc="upper right")

    colors = np.where(data["return_delta_pct"] >= 0.0, "#059669", "#dc2626")
    ax_delta.bar(x, data["return_delta_pct"], color=colors, alpha=0.88, width=0.82)
    ax_delta.axhline(0.0, color="#111827", linewidth=0.9)
    ax_delta.set_ylabel("C50 - A return pp")
    ax_delta.set_title("Return difference: green means C50 beats official")
    ax_delta.grid(axis="y", alpha=0.22)

    ax_dd.plot(x, data["a_rebased_max_dd_pct"], color="#ea580c", linewidth=1.7, label="A official max DD")
    ax_dd.plot(x, data["c_rebased_max_dd_pct"], color="#059669", linewidth=1.7, label="C50 max DD")
    ax_dd.axhline(-30.0, color="#f97316", linestyle="--", linewidth=0.9, label="DD -30%")
    ax_dd.axhline(-40.0, color="#dc2626", linestyle="--", linewidth=0.9, label="DD -40%")
    ax_dd.set_ylabel("Max DD %")
    ax_dd.set_title("Max drawdown by start month")
    ax_dd.grid(axis="y", alpha=0.25)
    ax_dd.legend(loc="lower right", ncol=2)

    dd_colors = np.where(data["dd_delta_pp"] >= 0.0, "#059669", "#dc2626")
    ax_dd_delta.bar(x, data["dd_delta_pp"], color=dd_colors, alpha=0.88, width=0.82)
    ax_dd_delta.axhline(0.0, color="#111827", linewidth=0.9)
    ax_dd_delta.set_ylabel("C50 - A DD pp")
    ax_dd_delta.set_title("Drawdown difference: green means C50 is shallower")
    ax_dd_delta.grid(axis="y", alpha=0.22)
    ax_dd_delta.set_xticks(tick_idx)
    ax_dd_delta.set_xticklabels([labels[i] for i in tick_idx], rotation=45, ha="right")

    full = data[data["start_month"].eq("2020-01")].iloc[0]
    fig.suptitle(
        (
            "Stage749 A official vs C50 half-risk no-streak monthly-start comparison | "
            f"2020-01 retention {full['return_retention_pct']:.1f}% | "
            f"C50 return wins {int(data['c_return_wins'].sum())}/{len(data)}, "
            f"C50 DD wins {int(data['c_dd_wins'].sum())}/{len(data)}"
        ),
        fontsize=15,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.965))
    fig.savefig(CHART_PATH, dpi=170)
    plt.close(fig)


def _heat_values(comparison: pd.DataFrame, column: str) -> pd.DataFrame:
    return (
        comparison.pivot_table(index="start_year", columns="start_month_num", values=column, aggfunc="first")
        .sort_index()
        .reindex(columns=list(range(1, 13)))
    )


def _plot_heatmap(comparison: pd.DataFrame) -> None:
    ret = _heat_values(comparison, "return_delta_pct")
    dd = _heat_values(comparison, "dd_delta_pp")
    fig, axes = plt.subplots(2, 1, figsize=(17, 8.5))
    specs = [
        (axes[0], ret, "C50 - A total return (percentage points)", "Return pp", "{:.0f}"),
        (axes[1], dd, "C50 - A max drawdown (pp; positive = C50 shallower)", "DD pp", "{:.1f}"),
    ]
    for ax, table, title, cbar_label, fmt in specs:
        values = table.to_numpy(dtype=float)
        finite = values[np.isfinite(values)]
        limit = max(float(np.nanpercentile(np.abs(finite), 90)), 1.0) if finite.size else 1.0
        norm = TwoSlopeNorm(vmin=-limit, vcenter=0.0, vmax=limit)
        image = ax.imshow(values, aspect="auto", cmap="RdYlGn", norm=norm)
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
                text_color = "white" if abs(value) > limit * 0.55 else "#111827"
                ax.text(x, y, fmt.format(value), ha="center", va="center", fontsize=8, color=text_color)
        fig.colorbar(image, ax=ax, fraction=0.018, pad=0.01, label=cbar_label)
    fig.suptitle("Stage749 monthly-start advantage heatmaps: green favors C50, red favors official", fontsize=15)
    fig.tight_layout(rect=(0, 0, 1, 0.955))
    fig.savefig(HEATMAP_PATH, dpi=170)
    plt.close(fig)


def _plot_c20(c20_comparison: pd.DataFrame) -> None:
    data = c20_comparison.sort_values("start_ts").copy()
    x = np.arange(len(data))
    labels = data["start_month"].tolist()
    tick_idx = [idx for idx, label in enumerate(labels) if label.endswith("-01") or idx == len(labels) - 1]

    fig, axes = plt.subplots(3, 1, figsize=(18, 10), sharex=True)
    axes[0].plot(x, data["c20_rebased_total_return_pct"], color="#2563eb", linewidth=1.8, label="C20 return")
    axes[0].plot(x, data["c50_rebased_total_return_pct"], color="#059669", linewidth=1.8, label="C50 return")
    axes[0].axhline(0.0, color="#111827", linewidth=0.8)
    axes[0].set_ylabel("Total return %")
    axes[0].set_title("C50 vs C20 total return by monthly start")
    axes[0].grid(axis="y", alpha=0.25)
    axes[0].legend(loc="upper right")

    colors = np.where(data["return_delta_pct"] >= 0.0, "#059669", "#dc2626")
    axes[1].bar(x, data["return_delta_pct"], color=colors, alpha=0.88, width=0.82)
    axes[1].axhline(0.0, color="#111827", linewidth=0.9)
    axes[1].set_ylabel("C50 - C20 return pp")
    axes[1].set_title("Return difference: green means 500k capital improves C")
    axes[1].grid(axis="y", alpha=0.22)

    dd_colors = np.where(data["dd_delta_pp"] >= 0.0, "#059669", "#dc2626")
    axes[2].bar(x, data["dd_delta_pp"], color=dd_colors, alpha=0.88, width=0.82)
    axes[2].axhline(0.0, color="#111827", linewidth=0.9)
    axes[2].set_ylabel("C50 - C20 DD pp")
    axes[2].set_title("Drawdown difference: green means C50 is shallower")
    axes[2].grid(axis="y", alpha=0.22)
    axes[2].set_xticks(tick_idx)
    axes[2].set_xticklabels([labels[i] for i in tick_idx], rotation=45, ha="right")

    fig.suptitle(
        (
            "Stage749 C50 vs Stage747 C20 monthly-start comparison | "
            f"C50 return wins {int(data['c50_return_wins'].sum())}/{len(data)}, "
            f"C50 DD wins {int(data['c50_dd_wins'].sum())}/{len(data)}"
        ),
        fontsize=15,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.955))
    fig.savefig(C20_CHART_PATH, dpi=170)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    candidate: pd.DataFrame,
    cost: pd.DataFrame,
    comparison: pd.DataFrame,
    c20_comparison: pd.DataFrame,
    checks: pd.DataFrame,
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
    ]
    c20_columns = [
        "start_month",
        "c20_rebased_total_return_pct",
        "c50_rebased_total_return_pct",
        "return_delta_pct",
        "c20_rebased_max_dd_pct",
        "c50_rebased_max_dd_pct",
        "dd_delta_pp",
        "c20_rebased_sharpe",
        "c50_rebased_sharpe",
        "sharpe_delta",
        "c20_total_trade_count",
        "c50_total_trade_count",
        "trade_count_delta",
    ]
    lines = [
        "# Stage438 / Script749 C50逐月启动对比正式版",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        f"- A：当前正式 Stage372/20w `{s746.BASE_VARIANT}`，复用 Stage744 逐月结果。",
        f"- C50：`{s748.CANDIDATE_500K_VARIANT}`，50万本金，`risk_multiplier=0.40`，关闭连败缩放和 recovery sleeve。",
        f"- C20 对照：`{s746.CANDIDATE_VARIANT}`，复用 Stage747 逐月结果。",
        f"- 起点范围：`2020-01` 至 `{MONTH_STARTS[-1].strftime('%Y-%m')}`，共 `{len(comparison)}` 个逐月独立启动；统一终点 `{ANALYSIS_END.strftime('%Y-%m-%d')}`。",
        "- 不修改正式配置、不连接 CTP、不调用下单。",
        "",
        "## 外部调研判断",
        "",
        "- 固定比例/固定风险 sizing 的核心是按账户权益和止损距离决定合约数；期货整数手会让小本金账户出现颗粒度误差。",
        "- 多起点 walk-forward 检验能降低单一路径依赖误判；本阶段只改本金并扰动启动月份，不新增信号参数。",
        "",
        "## 检查聚合",
        "",
        _md_table(checks, max_rows=40),
        "",
        "## A vs C50 最伤收益的起点",
        "",
        _md_table(comparison.sort_values("return_delta_pct").head(15)[columns], max_rows=15),
        "",
        "## A vs C50 收益相对最好的起点",
        "",
        _md_table(comparison.sort_values("return_delta_pct", ascending=False).head(15)[columns], max_rows=15),
        "",
        "## C50 vs C20 逐月对比",
        "",
        _md_table(c20_comparison[c20_columns], max_rows=90),
        "",
        "## 全部 A vs C50 月起点明细",
        "",
        _md_table(comparison[columns], max_rows=90),
        "",
        "## C50 成本压力",
        "",
        _md_table(cost, max_rows=90),
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
        f"- c20_chart：`{C20_CHART_PATH}`",
        f"- comparison：`{COMPARISON_PATH}`",
        f"- comparison_c20：`{COMPARISON_C20_PATH}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    official = _official_summary()
    official_curves = _official_curves()
    candidate, cost, candidate_curves = _run_candidate_monthly()
    comparison = _build_comparison(official, candidate)
    c20_comparison = _build_c20_comparison(candidate)
    checks = _checks(comparison, c20_comparison)
    decision = _decision(comparison, checks)

    summary = pd.concat([official, candidate], ignore_index=True, sort=False)
    curves = pd.concat([official_curves, candidate_curves], ignore_index=True, sort=False)

    _plot_main(comparison)
    _plot_heatmap(comparison)
    _plot_c20(c20_comparison)
    _write_report(summary, candidate, cost, comparison, c20_comparison, checks, decision)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    candidate.to_csv(CANDIDATE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    c20_comparison.to_csv(COMPARISON_C20_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    checks.to_csv(CHECKS_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
