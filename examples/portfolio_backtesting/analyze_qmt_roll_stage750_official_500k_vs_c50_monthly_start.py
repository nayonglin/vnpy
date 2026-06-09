from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
from datetime import datetime
import json
import os
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
import numpy as np
import pandas as pd

import analyze_qmt_roll_stage660_stage653_multiperiod_live_audit as s660
import analyze_qmt_roll_stage746_half_risk_no_streak_multiperiod as s746
import analyze_qmt_roll_stage748_half_risk_no_streak_500k as s748
import analyze_qmt_roll_stage749_half_risk_no_streak_500k_monthly_start_compare as s749


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage750_official_500k_vs_c50_monthly_start_v1"
OUTPUT_PREFIX = "qmt_roll_stage750_official_500k_vs_c50_monthly_start"
LINE_ID = "futures_trend_quarter_risk_no_streak"

ANALYSIS_END = s749.ANALYSIS_END
MONTH_STARTS = s749.MONTH_STARTS
CAPITAL_500K = s748.CAPITAL_500K
A50_VARIANT = "stage526_500k_force95_to80_recovery_sleeve_r080_pc25_maxpos4_stage750"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
A50_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_a50_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
COMPARISON_A20_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_a20_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
CHECKS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_checks_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"
HEATMAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_heatmap_{MODEL_TAG}.png"
A20_CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_a20_chart_{MODEL_TAG}.png"

A50_ARM = "A50_official"
C50_ARM = "C50_r040_no_streak"
MAX_WORKERS = max(1, min(4, int(os.environ.get("STAGE750_MAX_WORKERS", "4"))))


def _json_safe(value: Any) -> Any:
    return s749._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s749._md_table(frame, max_rows=max_rows)


def _window_name(start: pd.Timestamp) -> str:
    return f"mstart_{start.strftime('%Y_%m')}"


def _window_label(start: pd.Timestamp) -> str:
    return f"{start.strftime('%Y-%m')} independent start to {ANALYSIS_END.strftime('%Y-%m-%d')}"


def _official_500k_spec(metadata: dict[str, Any]) -> s660.s653.ForcedVariant:
    base = s660._official_spec(metadata)
    capital = replace(
        base.capital,
        variant=A50_VARIANT,
        label="Stage750 official Stage372 logic with 500k capital",
        account_capital=CAPITAL_500K,
        c3_capital=CAPITAL_500K,
        note=(
            "Official Stage372 signal/universe/risk logic unchanged, but account/c3 capital is 500k. "
            "Risk multiplier remains 0.80, loss-streak throttle and recovery sleeve remain enabled."
        ),
    )
    return replace(base, capital=capital, profile="official_stage372_500k_stage750")


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


def _run_a50_month(
    start_iso: str,
    metadata: dict[str, Any],
    spec: s660.s653.ForcedVariant,
    base_c3_overrides: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], pd.DataFrame]:
    s749._install_stable_c3_overrides(base_c3_overrides)
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
    row = _row_to_common(row, "stage750_official_500k_monthly_start")
    row["requested_start_month"] = start.strftime("%Y-%m")
    row["start_month"] = start.strftime("%Y-%m")
    row["arm"] = A50_ARM
    row["caveat"] = "fresh independent monthly start; official Stage372 logic; capital=500k"

    curve = _curve_to_common(curve, "stage750_official_500k_monthly_start")
    curve["requested_start_month"] = start.strftime("%Y-%m")
    curve["start_month"] = start.strftime("%Y-%m")
    curve["arm"] = A50_ARM

    for cost in costs:
        cost["requested_start_month"] = start.strftime("%Y-%m")
        cost["start_month"] = start.strftime("%Y-%m")
        cost["arm"] = A50_ARM
        cost["variant"] = spec.capital.variant
    return row, costs, curve


def _run_a50_monthly() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    metadata = s749.s744.s513._metadata()
    spec = _official_500k_spec(metadata)
    base_c3_overrides = dict(s749.ORIGINAL_C3_OVERRIDES(MONTH_STARTS[0].to_pydatetime()))
    start_items = [start.strftime("%Y-%m-%d") for start in MONTH_STARTS]

    summary_rows: list[dict[str, Any]] = []
    cost_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []
    print(f"[stage750] launching {len(start_items)} A50 monthly starts with workers={MAX_WORKERS}", flush=True)
    if MAX_WORKERS == 1:
        for idx, start_iso in enumerate(start_items, start=1):
            print(f"[stage750] running {idx}/{len(start_items)} {_window_name(pd.Timestamp(start_iso))}", flush=True)
            row, costs, curve = _run_a50_month(start_iso, metadata, spec, base_c3_overrides)
            summary_rows.append(row)
            cost_rows.extend(costs)
            curve_frames.append(curve)
    else:
        with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {
                executor.submit(_run_a50_month, start_iso, metadata, spec, base_c3_overrides): start_iso
                for start_iso in start_items
            }
            for idx, future in enumerate(as_completed(futures), start=1):
                start_iso = futures[future]
                row, costs, curve = future.result()
                summary_rows.append(row)
                cost_rows.extend(costs)
                curve_frames.append(curve)
                print(f"[stage750] completed {idx}/{len(start_items)} {_window_name(pd.Timestamp(start_iso))}", flush=True)

    summary = _add_month_fields(pd.DataFrame(summary_rows)).sort_values("start_month").reset_index(drop=True)
    cost = pd.DataFrame(cost_rows).sort_values(["start_month", "cost_multiplier"]).reset_index(drop=True)
    curves = (
        pd.concat(curve_frames, ignore_index=True, sort=False)
        .sort_values(["start_month", "date"])
        .reset_index(drop=True)
    )
    return summary, cost, curves


def _load_c50_summary() -> pd.DataFrame:
    if not s749.CANDIDATE_SUMMARY_PATH.exists():
        raise FileNotFoundError(f"missing Stage749 C50 monthly output: {s749.CANDIDATE_SUMMARY_PATH}")
    frame = pd.read_csv(s749.CANDIDATE_SUMMARY_PATH, encoding="utf-8-sig")
    frame["arm"] = C50_ARM
    return _add_month_fields(frame)


def _load_c50_curves() -> pd.DataFrame:
    if not s749.CURVES_PATH.exists():
        raise FileNotFoundError(f"missing Stage749 curves output: {s749.CURVES_PATH}")
    frame = pd.read_csv(s749.CURVES_PATH, encoding="utf-8-sig")
    frame = frame[frame["arm"].astype(str).eq(C50_ARM)].copy()
    return frame


def _load_a20_summary() -> pd.DataFrame:
    if not s749.s744.SUMMARY_PATH.exists():
        raise FileNotFoundError(f"missing Stage744 official monthly output: {s749.s744.SUMMARY_PATH}")
    frame = pd.read_csv(s749.s744.SUMMARY_PATH, encoding="utf-8-sig")
    frame = frame[frame["window_group"].astype(str).eq("monthly_start")].copy()
    frame["account_capital"] = float(s749.s744.OFFICIAL_LIVE_CAPITAL)
    frame["nav_end"] = pd.to_numeric(frame["rebased_end_equity"], errors="coerce") / float(s749.s744.OFFICIAL_LIVE_CAPITAL)
    return _add_month_fields(frame)


def _build_comparison(a50: pd.DataFrame, c50: pd.DataFrame) -> pd.DataFrame:
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
    left = a50[keep].copy().add_prefix("a50_")
    right = c50[keep].copy().add_prefix("c50_")
    merged = left.merge(right, left_on="a50_start_month", right_on="c50_start_month", how="inner")
    merged["start_month"] = merged["a50_start_month"]
    merged["start_ts"] = pd.to_datetime(merged["start_month"] + "-01", errors="coerce")
    merged["start_year"] = merged["a50_start_year"]
    merged["start_month_num"] = merged["a50_start_month_num"]
    merged["trading_days"] = merged["a50_trading_days"]
    merged["mature_63d"] = merged["a50_mature_63d"]
    merged["mature_126d"] = merged["a50_mature_126d"]
    merged["mature_252d"] = merged["a50_mature_252d"]
    merged["return_delta_pct"] = merged["c50_rebased_total_return_pct"] - merged["a50_rebased_total_return_pct"]
    merged["return_retention_pct"] = np.where(
        merged["a50_rebased_total_return_pct"].abs() > 1e-9,
        merged["c50_rebased_total_return_pct"] / merged["a50_rebased_total_return_pct"] * 100.0,
        np.nan,
    )
    merged["nav_delta"] = merged["c50_nav_end"] - merged["a50_nav_end"]
    merged["dd_delta_pp"] = merged["c50_rebased_max_dd_pct"] - merged["a50_rebased_max_dd_pct"]
    merged["sharpe_delta"] = merged["c50_rebased_sharpe"] - merged["a50_rebased_sharpe"]
    merged["trade_count_delta"] = merged["c50_total_trade_count"] - merged["a50_total_trade_count"]
    merged["slippage_delta"] = merged["c50_total_slippage"] - merged["a50_total_slippage"]
    merged["c50_return_wins"] = (merged["return_delta_pct"] > 0.0).astype(int)
    merged["c50_dd_wins"] = (merged["dd_delta_pp"] > 0.0).astype(int)
    merged["c50_both_return_dd_wins"] = (
        merged["c50_return_wins"].eq(1) & merged["c50_dd_wins"].eq(1)
    ).astype(int)
    merged["a50_both_return_dd_wins"] = (
        merged["return_delta_pct"].lt(0.0) & merged["dd_delta_pp"].lt(0.0)
    ).astype(int)
    merged["c50_positive_return"] = (merged["c50_rebased_total_return_pct"] > 0.0).astype(int)
    merged["a50_positive_return"] = (merged["a50_rebased_total_return_pct"] > 0.0).astype(int)
    merged["c50_dd30_fail"] = (merged["c50_rebased_max_dd_pct"] < -30.0).astype(int)
    merged["a50_dd30_fail"] = (merged["a50_rebased_max_dd_pct"] < -30.0).astype(int)
    merged["c50_dd40_fail"] = (merged["c50_rebased_max_dd_pct"] < -40.0).astype(int)
    merged["a50_dd40_fail"] = (merged["a50_rebased_max_dd_pct"] < -40.0).astype(int)
    return merged.sort_values("start_ts").reset_index(drop=True)


def _build_a20_comparison(a20: pd.DataFrame, a50: pd.DataFrame) -> pd.DataFrame:
    keep = [
        "start_month",
        "trading_days",
        "nav_end",
        "rebased_total_return_pct",
        "rebased_max_dd_pct",
        "rebased_sharpe",
        "total_trade_count",
        "total_slippage",
        "mature_252d",
        "start_year",
    ]
    left = a20[keep].copy().add_prefix("a20_")
    right = a50[keep].copy().add_prefix("a50_")
    merged = left.merge(right, left_on="a20_start_month", right_on="a50_start_month", how="inner")
    merged["start_month"] = merged["a50_start_month"]
    merged["start_ts"] = pd.to_datetime(merged["start_month"] + "-01", errors="coerce")
    merged["start_year"] = merged["a50_start_year"]
    merged["mature_252d"] = merged["a50_mature_252d"]
    merged["return_delta_pct"] = merged["a50_rebased_total_return_pct"] - merged["a20_rebased_total_return_pct"]
    merged["dd_delta_pp"] = merged["a50_rebased_max_dd_pct"] - merged["a20_rebased_max_dd_pct"]
    merged["sharpe_delta"] = merged["a50_rebased_sharpe"] - merged["a20_rebased_sharpe"]
    merged["trade_count_delta"] = merged["a50_total_trade_count"] - merged["a20_total_trade_count"]
    merged["slippage_delta"] = merged["a50_total_slippage"] - merged["a20_total_slippage"]
    merged["a50_return_wins"] = (merged["return_delta_pct"] > 0.0).astype(int)
    merged["a50_dd_wins"] = (merged["dd_delta_pp"] > 0.0).astype(int)
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
        "c50_return_win_count": int(frame["c50_return_wins"].sum()),
        "c50_return_win_rate_pct": float(frame["c50_return_wins"].mean() * 100.0),
        "c50_dd_win_count": int(frame["c50_dd_wins"].sum()),
        "c50_dd_win_rate_pct": float(frame["c50_dd_wins"].mean() * 100.0),
        "c50_both_return_dd_win_count": int(frame["c50_both_return_dd_wins"].sum()),
        "a50_both_return_dd_win_count": int(frame["a50_both_return_dd_wins"].sum()),
        "c50_positive_count": int(frame["c50_positive_return"].sum()),
        "a50_positive_count": int(frame["a50_positive_return"].sum()),
        "c50_dd30_fail_count": int(frame["c50_dd30_fail"].sum()),
        "a50_dd30_fail_count": int(frame["a50_dd30_fail"].sum()),
        "c50_dd40_fail_count": int(frame["c50_dd40_fail"].sum()),
        "a50_dd40_fail_count": int(frame["a50_dd40_fail"].sum()),
        "median_return_delta_pct": float(ret_delta.median()),
        "p10_return_delta_pct": float(ret_delta.quantile(0.10)),
        "median_return_retention_pct": float(retention.median()) if not retention.empty else np.nan,
        "median_dd_delta_pp": float(dd_delta.median()),
        "worst_dd_delta_pp": float(dd_delta.min()),
        "best_dd_delta_pp": float(dd_delta.max()),
        "worst_return_delta_start": str(frame.loc[ret_delta.idxmin(), "start_month"]),
        "best_return_delta_start": str(frame.loc[ret_delta.idxmax(), "start_month"]),
    }


def _checks(comparison: pd.DataFrame, a20_comparison: pd.DataFrame) -> pd.DataFrame:
    rows = [
        _bucket_stats("all_monthly_starts", comparison),
        _bucket_stats("mature_ge63_trading_days", comparison[comparison["mature_63d"].eq(1)]),
        _bucket_stats("mature_ge126_trading_days", comparison[comparison["mature_126d"].eq(1)]),
        _bucket_stats("mature_ge252_trading_days", comparison[comparison["mature_252d"].eq(1)]),
    ]
    for year, group in comparison.groupby("start_year", sort=True):
        rows.append(_bucket_stats(f"start_year_{int(year)}", group))
    checks = pd.DataFrame(rows)

    a20_all = {
        "bucket": "a50_vs_a20_all_monthly_starts",
        "start_count": int(len(a20_comparison)),
        "c50_return_win_count": int(a20_comparison["a50_return_wins"].sum()),
        "c50_return_win_rate_pct": float(a20_comparison["a50_return_wins"].mean() * 100.0),
        "c50_dd_win_count": int(a20_comparison["a50_dd_wins"].sum()),
        "c50_dd_win_rate_pct": float(a20_comparison["a50_dd_wins"].mean() * 100.0),
        "median_return_delta_pct": float(pd.to_numeric(a20_comparison["return_delta_pct"], errors="coerce").median()),
        "median_dd_delta_pp": float(pd.to_numeric(a20_comparison["dd_delta_pp"], errors="coerce").median()),
        "median_trade_count_delta": float(pd.to_numeric(a20_comparison["trade_count_delta"], errors="coerce").median()),
    }
    mature = a20_comparison[a20_comparison["mature_252d"].eq(1)]
    a20_mature = {
        "bucket": "a50_vs_a20_mature_ge252_trading_days",
        "start_count": int(len(mature)),
        "c50_return_win_count": int(mature["a50_return_wins"].sum()),
        "c50_return_win_rate_pct": float(mature["a50_return_wins"].mean() * 100.0),
        "c50_dd_win_count": int(mature["a50_dd_wins"].sum()),
        "c50_dd_win_rate_pct": float(mature["a50_dd_wins"].mean() * 100.0),
        "median_return_delta_pct": float(pd.to_numeric(mature["return_delta_pct"], errors="coerce").median()),
        "median_dd_delta_pp": float(pd.to_numeric(mature["dd_delta_pp"], errors="coerce").median()),
        "median_trade_count_delta": float(pd.to_numeric(mature["trade_count_delta"], errors="coerce").median()),
    }
    return pd.concat([checks, pd.DataFrame([a20_all, a20_mature])], ignore_index=True, sort=False)


def _decision(comparison: pd.DataFrame, checks: pd.DataFrame) -> dict[str, Any]:
    mature = checks[checks["bucket"].eq("mature_ge252_trading_days")].iloc[0]
    all_row = checks[checks["bucket"].eq("all_monthly_starts")].iloc[0]
    hard_fail: list[str] = []
    watch: list[str] = []
    if int(mature["c50_return_win_count"]) < int(mature["start_count"]) * 0.45:
        hard_fail.append("mature252_c50_return_wins_lt45pct")
    if float(mature["median_return_delta_pct"]) < 0.0:
        hard_fail.append("mature252_median_return_delta_negative")
    if int(mature["c50_positive_count"]) < int(mature["a50_positive_count"]):
        watch.append("mature252_c50_positive_count_less_than_a50")
    if int(mature["c50_dd40_fail_count"]) > int(mature["a50_dd40_fail_count"]):
        watch.append("mature252_c50_dd40_fail_more_than_a50")
    if int(all_row["c50_both_return_dd_win_count"]) <= int(all_row["a50_both_return_dd_win_count"]):
        watch.append("all_c50_both_wins_not_more_than_a50_both_wins")
    decision = "official_500k_vs_c50_monthly_start_c50_not_promoted" if hard_fail else "official_500k_vs_c50_monthly_start_watch"
    return {
        "stage": "Stage439",
        "script_stage": "Stage750",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "a50_variant": A50_VARIANT,
        "c50_variant": s748.CANDIDATE_500K_VARIANT,
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
            "a50_account_capital": CAPITAL_500K,
            "a50_risk_multiplier": 0.80,
            "a50_loss_streak_and_recovery_sleeve_enabled": True,
            "c50_results_reused_from_stage749": True,
            "c50_account_capital": CAPITAL_500K,
            "c50_risk_multiplier": s746.HALF_FORMAL_RISK_MULTIPLIER,
            "c50_loss_streak_and_recovery_sleeve_enabled": False,
        },
        "checks": checks.to_dict("records"),
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "a50_summary": str(A50_SUMMARY_PATH),
            "cost": str(COST_PATH),
            "comparison": str(COMPARISON_PATH),
            "comparison_a20": str(COMPARISON_A20_PATH),
            "curves": str(CURVES_PATH),
            "checks": str(CHECKS_PATH),
            "report": str(REPORT_PATH),
            "chart": str(CHART_PATH),
            "heatmap": str(HEATMAP_PATH),
            "a20_chart": str(A20_CHART_PATH),
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
    ax_ret.plot(x, data["a50_rebased_total_return_pct"], color="#7c3aed", linewidth=1.8, label="A50 official return")
    ax_ret.plot(x, data["c50_rebased_total_return_pct"], color="#059669", linewidth=1.8, label="C50 no-streak return")
    ax_ret.axhline(0.0, color="#111827", linewidth=0.8)
    ax_ret.set_ylabel("Total return %")
    ax_ret.set_title("Monthly independent starts to 2026-04-30: total return")
    ax_ret.grid(axis="y", alpha=0.25)
    ax_ret.legend(loc="upper right")

    colors = np.where(data["return_delta_pct"] >= 0.0, "#059669", "#dc2626")
    ax_delta.bar(x, data["return_delta_pct"], color=colors, alpha=0.88, width=0.82)
    ax_delta.axhline(0.0, color="#111827", linewidth=0.9)
    ax_delta.set_ylabel("C50 - A50 return pp")
    ax_delta.set_title("Return difference: green means C50 beats A50")
    ax_delta.grid(axis="y", alpha=0.22)

    ax_dd.plot(x, data["a50_rebased_max_dd_pct"], color="#7c3aed", linewidth=1.7, label="A50 max DD")
    ax_dd.plot(x, data["c50_rebased_max_dd_pct"], color="#059669", linewidth=1.7, label="C50 max DD")
    ax_dd.axhline(-30.0, color="#f97316", linestyle="--", linewidth=0.9, label="DD -30%")
    ax_dd.axhline(-40.0, color="#dc2626", linestyle="--", linewidth=0.9, label="DD -40%")
    ax_dd.set_ylabel("Max DD %")
    ax_dd.set_title("Max drawdown by start month")
    ax_dd.grid(axis="y", alpha=0.25)
    ax_dd.legend(loc="lower right", ncol=2)

    dd_colors = np.where(data["dd_delta_pp"] >= 0.0, "#059669", "#dc2626")
    ax_dd_delta.bar(x, data["dd_delta_pp"], color=dd_colors, alpha=0.88, width=0.82)
    ax_dd_delta.axhline(0.0, color="#111827", linewidth=0.9)
    ax_dd_delta.set_ylabel("C50 - A50 DD pp")
    ax_dd_delta.set_title("Drawdown difference: green means C50 is shallower")
    ax_dd_delta.grid(axis="y", alpha=0.22)
    ax_dd_delta.set_xticks(tick_idx)
    ax_dd_delta.set_xticklabels([labels[i] for i in tick_idx], rotation=45, ha="right")

    fig.suptitle(
        (
            "Stage750 A50 official vs C50 no-streak monthly-start comparison | "
            f"C50 return wins {int(data['c50_return_wins'].sum())}/{len(data)}, "
            f"C50 DD wins {int(data['c50_dd_wins'].sum())}/{len(data)}"
        ),
        fontsize=15,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.965))
    fig.savefig(CHART_PATH, dpi=170)
    plt.close(fig)


def _plot_heatmap(comparison: pd.DataFrame) -> None:
    def heat_values(column: str) -> pd.DataFrame:
        return (
            comparison.pivot_table(index="start_year", columns="start_month_num", values=column, aggfunc="first")
            .sort_index()
            .reindex(columns=list(range(1, 13)))
        )

    ret = heat_values("return_delta_pct")
    dd = heat_values("dd_delta_pp")
    fig, axes = plt.subplots(2, 1, figsize=(17, 8.5))
    specs = [
        (axes[0], ret, "C50 - A50 total return (percentage points)", "Return pp", "{:.0f}"),
        (axes[1], dd, "C50 - A50 max drawdown (pp; positive = C50 shallower)", "DD pp", "{:.1f}"),
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
    fig.suptitle("Stage750 monthly-start advantage heatmaps: green favors C50, red favors A50", fontsize=15)
    fig.tight_layout(rect=(0, 0, 1, 0.955))
    fig.savefig(HEATMAP_PATH, dpi=170)
    plt.close(fig)


def _plot_a20(a20_comparison: pd.DataFrame) -> None:
    data = a20_comparison.sort_values("start_ts").copy()
    x = np.arange(len(data))
    labels = data["start_month"].tolist()
    tick_idx = [idx for idx, label in enumerate(labels) if label.endswith("-01") or idx == len(labels) - 1]

    fig, axes = plt.subplots(3, 1, figsize=(18, 10), sharex=True)
    axes[0].plot(x, data["a20_rebased_total_return_pct"], color="#ea580c", linewidth=1.8, label="A20 return")
    axes[0].plot(x, data["a50_rebased_total_return_pct"], color="#7c3aed", linewidth=1.8, label="A50 return")
    axes[0].axhline(0.0, color="#111827", linewidth=0.8)
    axes[0].set_ylabel("Total return %")
    axes[0].set_title("A50 vs A20 total return by monthly start")
    axes[0].grid(axis="y", alpha=0.25)
    axes[0].legend(loc="upper right")

    colors = np.where(data["return_delta_pct"] >= 0.0, "#059669", "#dc2626")
    axes[1].bar(x, data["return_delta_pct"], color=colors, alpha=0.88, width=0.82)
    axes[1].axhline(0.0, color="#111827", linewidth=0.9)
    axes[1].set_ylabel("A50 - A20 return pp")
    axes[1].set_title("Return difference: green means 500k improves official")
    axes[1].grid(axis="y", alpha=0.22)

    dd_colors = np.where(data["dd_delta_pp"] >= 0.0, "#059669", "#dc2626")
    axes[2].bar(x, data["dd_delta_pp"], color=dd_colors, alpha=0.88, width=0.82)
    axes[2].axhline(0.0, color="#111827", linewidth=0.9)
    axes[2].set_ylabel("A50 - A20 DD pp")
    axes[2].set_title("Drawdown difference: green means A50 is shallower")
    axes[2].grid(axis="y", alpha=0.22)
    axes[2].set_xticks(tick_idx)
    axes[2].set_xticklabels([labels[i] for i in tick_idx], rotation=45, ha="right")
    fig.suptitle(
        (
            "Stage750 A50 vs Stage744 A20 monthly-start comparison | "
            f"A50 return wins {int(data['a50_return_wins'].sum())}/{len(data)}, "
            f"A50 DD wins {int(data['a50_dd_wins'].sum())}/{len(data)}"
        ),
        fontsize=15,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.955))
    fig.savefig(A20_CHART_PATH, dpi=170)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    a50: pd.DataFrame,
    cost: pd.DataFrame,
    comparison: pd.DataFrame,
    a20_comparison: pd.DataFrame,
    checks: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    columns = [
        "start_month",
        "trading_days",
        "a50_rebased_total_return_pct",
        "c50_rebased_total_return_pct",
        "return_delta_pct",
        "return_retention_pct",
        "a50_rebased_max_dd_pct",
        "c50_rebased_max_dd_pct",
        "dd_delta_pp",
        "a50_rebased_sharpe",
        "c50_rebased_sharpe",
        "sharpe_delta",
        "a50_total_trade_count",
        "c50_total_trade_count",
        "trade_count_delta",
    ]
    a20_columns = [
        "start_month",
        "a20_rebased_total_return_pct",
        "a50_rebased_total_return_pct",
        "return_delta_pct",
        "a20_rebased_max_dd_pct",
        "a50_rebased_max_dd_pct",
        "dd_delta_pp",
        "a20_total_trade_count",
        "a50_total_trade_count",
        "trade_count_delta",
    ]
    lines = [
        "# Stage439 / Script750 A50正式版逐月启动对比C50",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        f"- A50：`{A50_VARIANT}`，正式 Stage372 逻辑不变，仅本金和 `c3_capital` 改为 50万。",
        f"- C50：`{s748.CANDIDATE_500K_VARIANT}`，复用 Stage749，50万本金，`risk_multiplier=0.40`，关闭连败缩放和 recovery sleeve。",
        f"- A20：当前正式 Stage372/20万，复用 Stage744，仅用于本金粒度对照。",
        f"- 起点范围：`2020-01` 至 `{MONTH_STARTS[-1].strftime('%Y-%m')}`，共 `{len(comparison)}` 个逐月独立启动；统一终点 `{ANALYSIS_END.strftime('%Y-%m-%d')}`。",
        "- 不修改正式配置、不连接 CTP、不调用下单。",
        "",
        "## 外部调研判断",
        "",
        "- 多起点 / walk-forward 检验用于处理单一起点美化和起点耦合；固定风险 sizing 又会受到期货最小合约手数影响。",
        "- 本阶段是公平拆解：A50 与 C50 同为 50万，只比较风控/风险倍率逻辑，不让本金差异混入结论。",
        "",
        "## 检查聚合",
        "",
        _md_table(checks, max_rows=40),
        "",
        "## A50 vs C50 最伤C50收益的起点",
        "",
        _md_table(comparison.sort_values("return_delta_pct").head(15)[columns], max_rows=15),
        "",
        "## A50 vs C50 C50收益相对最好的起点",
        "",
        _md_table(comparison.sort_values("return_delta_pct", ascending=False).head(15)[columns], max_rows=15),
        "",
        "## A50 vs A20 逐月对比",
        "",
        _md_table(a20_comparison[a20_columns], max_rows=90),
        "",
        "## 全部 A50 vs C50 月起点明细",
        "",
        _md_table(comparison[columns], max_rows=90),
        "",
        "## A50 成本压力",
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
        f"- a20_chart：`{A20_CHART_PATH}`",
        f"- comparison：`{COMPARISON_PATH}`",
        f"- comparison_a20：`{COMPARISON_A20_PATH}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    a50, cost, a50_curves = _run_a50_monthly()
    c50 = _load_c50_summary()
    c50_curves = _load_c50_curves()
    a20 = _load_a20_summary()
    comparison = _build_comparison(a50, c50)
    a20_comparison = _build_a20_comparison(a20, a50)
    checks = _checks(comparison, a20_comparison)
    decision = _decision(comparison, checks)
    summary = pd.concat([a50, c50], ignore_index=True, sort=False)
    curves = pd.concat([a50_curves, c50_curves], ignore_index=True, sort=False)

    _plot_main(comparison)
    _plot_heatmap(comparison)
    _plot_a20(a20_comparison)
    _write_report(summary, a50, cost, comparison, a20_comparison, checks, decision)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    a50.to_csv(A50_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    a20_comparison.to_csv(COMPARISON_A20_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    checks.to_csv(CHECKS_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
