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
import analyze_qmt_roll_stage748_half_risk_no_streak_500k as s748
import analyze_qmt_roll_stage749_half_risk_no_streak_500k_monthly_start_compare as s749
import analyze_qmt_roll_stage757_c50_oi_confirm_risk_restore as s757
import analyze_qmt_roll_stage660_stage653_multiperiod_live_audit as s660


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

MODEL_TAG = "stage759_stage757_monthly_start_v1"
OUTPUT_PREFIX = "qmt_roll_stage759_stage757_monthly_start"
LINE_ID = "futures_trend_winner_trade_forensics"

ANALYSIS_END = s749.ANALYSIS_END
MONTH_STARTS = s749.MONTH_STARTS

STAGE748_ARM = "B_stage748_c50"
STAGE757_ARM = "C_stage757_oi_restore"
MAX_WORKERS = max(1, min(4, int(os.environ.get("STAGE759_MAX_WORKERS", "4"))))

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CANDIDATE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_candidate_summary_{MODEL_TAG}.csv"
COST_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_stage748_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
CHECKS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_checks_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
CHART_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_chart_{MODEL_TAG}.png"
RETURN_HEATMAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_return_heatmap_{MODEL_TAG}.png"
DELTA_HEATMAP_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_delta_heatmap_{MODEL_TAG}.png"


def _json_safe(value: Any) -> Any:
    return s749._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s749._md_table(frame, max_rows=max_rows)


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


def _candidate_row_to_common(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    out["source_name"] = "stage759_stage757_monthly_start"
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
        "fresh independent monthly start; Stage757 C50 capital=500k; "
        "risk_multiplier=0.40; loss-streak throttle and recovery sleeve disabled; "
        "OI price confirm restores effective risk to 0.80"
    )
    return out


def _candidate_curve_to_common(curve: pd.DataFrame) -> pd.DataFrame:
    frame = curve.copy()
    frame["source_name"] = "stage759_stage757_monthly_start"
    frame["rebased_equity"] = frame["account_equity"]
    frame["rebased_nav"] = frame["nav"]
    frame["broker10_margin_to_rebased_equity_pct"] = frame["broker10_margin_to_equity_pct"]
    return frame


def _run_candidate_month(
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
    row = _candidate_row_to_common(row)
    row["requested_start_month"] = start.strftime("%Y-%m")
    row["start_month"] = start.strftime("%Y-%m")
    row["arm"] = STAGE757_ARM

    curve = _candidate_curve_to_common(curve)
    curve["requested_start_month"] = start.strftime("%Y-%m")
    curve["start_month"] = start.strftime("%Y-%m")
    curve["arm"] = STAGE757_ARM

    for cost in costs:
        cost["requested_start_month"] = start.strftime("%Y-%m")
        cost["start_month"] = start.strftime("%Y-%m")
        cost["arm"] = STAGE757_ARM
        cost["variant"] = spec.capital.variant
    return row, costs, curve


def _run_candidate_monthly() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    metadata = s744.s513._metadata()
    spec = s757._candidate_spec(metadata)
    base_c3_overrides = dict(s749.ORIGINAL_C3_OVERRIDES(MONTH_STARTS[0].to_pydatetime()))
    start_items = [start.strftime("%Y-%m-%d") for start in MONTH_STARTS]

    summary_rows: list[dict[str, Any]] = []
    cost_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []
    print(f"[stage759] launching {len(start_items)} Stage757 monthly starts with workers={MAX_WORKERS}", flush=True)
    if MAX_WORKERS == 1:
        for idx, start_iso in enumerate(start_items, start=1):
            print(f"[stage759] running {idx}/{len(start_items)} {_window_name(pd.Timestamp(start_iso))}", flush=True)
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
                print(f"[stage759] completed {idx}/{len(start_items)} {_window_name(pd.Timestamp(start_iso))}", flush=True)

    candidate = _add_month_fields(pd.DataFrame(summary_rows)).sort_values("start_month").reset_index(drop=True)
    cost = pd.DataFrame(cost_rows).sort_values(["start_month", "cost_multiplier"]).reset_index(drop=True)
    curves = (
        pd.concat(curve_frames, ignore_index=True, sort=False)
        .sort_values(["start_month", "date"])
        .reset_index(drop=True)
    )
    return candidate, cost, curves


def _load_stage748_summary() -> pd.DataFrame:
    if not s749.CANDIDATE_SUMMARY_PATH.exists():
        raise FileNotFoundError(f"missing Stage749 C50 monthly output: {s749.CANDIDATE_SUMMARY_PATH}")
    frame = pd.read_csv(s749.CANDIDATE_SUMMARY_PATH, encoding="utf-8-sig")
    frame["arm"] = STAGE748_ARM
    return _add_month_fields(frame)


def _load_stage748_curves() -> pd.DataFrame:
    if not s749.CURVES_PATH.exists():
        raise FileNotFoundError(f"missing Stage749 curves output: {s749.CURVES_PATH}")
    frame = pd.read_csv(s749.CURVES_PATH, encoding="utf-8-sig")
    frame = frame[frame["arm"].astype(str).eq("C50_r040_no_streak")].copy()
    frame["arm"] = STAGE748_ARM
    return frame


def _build_comparison(stage748: pd.DataFrame, stage757: pd.DataFrame) -> pd.DataFrame:
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
    left = stage748[keep].copy().add_prefix("b_")
    right = stage757[keep].copy().add_prefix("c_")
    merged = left.merge(right, left_on="b_start_month", right_on="c_start_month", how="inner")
    merged["start_month"] = merged["b_start_month"]
    merged["start_ts"] = pd.to_datetime(merged["start_month"] + "-01", errors="coerce")
    merged["start_year"] = merged["b_start_year"]
    merged["start_month_num"] = merged["b_start_month_num"]
    merged["trading_days"] = merged["b_trading_days"]
    merged["mature_63d"] = merged["b_mature_63d"]
    merged["mature_126d"] = merged["b_mature_126d"]
    merged["mature_252d"] = merged["b_mature_252d"]
    merged["return_delta_pct"] = merged["c_rebased_total_return_pct"] - merged["b_rebased_total_return_pct"]
    merged["return_retention_pct"] = np.where(
        merged["b_rebased_total_return_pct"].abs() > 1e-9,
        merged["c_rebased_total_return_pct"] / merged["b_rebased_total_return_pct"] * 100.0,
        np.nan,
    )
    merged["nav_delta"] = merged["c_nav_end"] - merged["b_nav_end"]
    merged["dd_delta_pp"] = merged["c_rebased_max_dd_pct"] - merged["b_rebased_max_dd_pct"]
    merged["sharpe_delta"] = merged["c_rebased_sharpe"] - merged["b_rebased_sharpe"]
    merged["trade_count_delta"] = merged["c_total_trade_count"] - merged["b_total_trade_count"]
    merged["slippage_delta"] = merged["c_total_slippage"] - merged["b_total_slippage"]
    merged["c_return_wins"] = (merged["return_delta_pct"] > 0.0).astype(int)
    merged["c_dd_wins"] = (merged["dd_delta_pp"] > 0.0).astype(int)
    merged["c_sharpe_wins"] = (merged["sharpe_delta"] > 0.0).astype(int)
    merged["c_both_return_dd_wins"] = (merged["c_return_wins"].eq(1) & merged["c_dd_wins"].eq(1)).astype(int)
    merged["b_both_return_dd_wins"] = (
        merged["return_delta_pct"].lt(0.0) & merged["dd_delta_pp"].lt(0.0)
    ).astype(int)
    merged["c_positive_return"] = (merged["c_rebased_total_return_pct"] > 0.0).astype(int)
    merged["b_positive_return"] = (merged["b_rebased_total_return_pct"] > 0.0).astype(int)
    merged["c_dd30_fail"] = (merged["c_rebased_max_dd_pct"] < -30.0).astype(int)
    merged["b_dd30_fail"] = (merged["b_rebased_max_dd_pct"] < -30.0).astype(int)
    merged["c_dd40_fail"] = (merged["c_rebased_max_dd_pct"] < -40.0).astype(int)
    merged["b_dd40_fail"] = (merged["b_rebased_max_dd_pct"] < -40.0).astype(int)
    return merged.sort_values("start_ts").reset_index(drop=True)


def _candidate_stats(label: str, frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {"bucket": label, "start_count": 0}
    returns = pd.to_numeric(frame["rebased_total_return_pct"], errors="coerce")
    dd = pd.to_numeric(frame["rebased_max_dd_pct"], errors="coerce")
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
    return {
        "bucket": label,
        "start_count": int(len(frame)),
        "c_return_win_count": int(frame["c_return_wins"].sum()),
        "c_return_win_rate_pct": float(frame["c_return_wins"].mean() * 100.0),
        "c_dd_win_count": int(frame["c_dd_wins"].sum()),
        "c_dd_win_rate_pct": float(frame["c_dd_wins"].mean() * 100.0),
        "c_sharpe_win_count": int(frame["c_sharpe_wins"].sum()),
        "c_both_return_dd_win_count": int(frame["c_both_return_dd_wins"].sum()),
        "b_both_return_dd_win_count": int(frame["b_both_return_dd_wins"].sum()),
        "c_positive_count": int(frame["c_positive_return"].sum()),
        "b_positive_count": int(frame["b_positive_return"].sum()),
        "c_dd30_fail_count": int(frame["c_dd30_fail"].sum()),
        "b_dd30_fail_count": int(frame["b_dd30_fail"].sum()),
        "c_dd40_fail_count": int(frame["c_dd40_fail"].sum()),
        "b_dd40_fail_count": int(frame["b_dd40_fail"].sum()),
        "median_return_delta_pct": float(ret_delta.median()),
        "p10_return_delta_pct": float(ret_delta.quantile(0.10)),
        "median_return_retention_pct": float(retention.median()),
        "median_dd_delta_pp": float(dd_delta.median()),
        "worst_dd_delta_pp": float(dd_delta.min()),
        "best_dd_delta_pp": float(dd_delta.max()),
        "worst_return_delta_start": str(frame.loc[ret_delta.idxmin(), "start_month"]),
        "best_return_delta_start": str(frame.loc[ret_delta.idxmax(), "start_month"]),
    }


def _checks(stage757: pd.DataFrame, comparison: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = [
        _candidate_stats("stage757_all_monthly_starts", stage757),
        _candidate_stats("stage757_mature_ge63_trading_days", stage757[stage757["mature_63d"].eq(1)]),
        _candidate_stats("stage757_mature_ge126_trading_days", stage757[stage757["mature_126d"].eq(1)]),
        _candidate_stats("stage757_mature_ge252_trading_days", stage757[stage757["mature_252d"].eq(1)]),
        _comparison_stats("vs_stage748_all_monthly_starts", comparison),
        _comparison_stats("vs_stage748_mature_ge63_trading_days", comparison[comparison["mature_63d"].eq(1)]),
        _comparison_stats("vs_stage748_mature_ge126_trading_days", comparison[comparison["mature_126d"].eq(1)]),
        _comparison_stats("vs_stage748_mature_ge252_trading_days", comparison[comparison["mature_252d"].eq(1)]),
    ]
    for year, group in stage757.groupby("start_year", sort=True):
        rows.append(_candidate_stats(f"stage757_start_year_{int(year)}", group))
    for year, group in comparison.groupby("start_year", sort=True):
        rows.append(_comparison_stats(f"vs_stage748_start_year_{int(year)}", group))
    return pd.DataFrame(rows)


def _decision(comparison: pd.DataFrame, checks: pd.DataFrame) -> dict[str, Any]:
    all_abs = checks[checks["bucket"].eq("stage757_all_monthly_starts")].iloc[0]
    mature_abs = checks[checks["bucket"].eq("stage757_mature_ge252_trading_days")].iloc[0]
    mature_cmp = checks[checks["bucket"].eq("vs_stage748_mature_ge252_trading_days")].iloc[0]
    full = comparison[comparison["start_month"].eq("2020-01")].iloc[0]
    hard_fail: list[str] = []
    watch: list[str] = []
    if int(mature_cmp["c_return_win_count"]) < int(mature_cmp["start_count"]) * 0.50:
        hard_fail.append("mature252_stage757_return_wins_lt50pct_vs_stage748")
    if float(mature_cmp["median_return_delta_pct"]) < 0.0:
        hard_fail.append("mature252_median_return_delta_negative_vs_stage748")
    if int(mature_abs["dd40_fail_count"]) > 0:
        hard_fail.append("mature252_stage757_dd40_fail_exists")
    if int(all_abs["positive_count"]) < int(all_abs["start_count"]) * 0.90:
        watch.append("stage757_all_positive_rate_lt90pct")
    if int(mature_cmp["c_dd40_fail_count"]) > int(mature_cmp["b_dd40_fail_count"]):
        watch.append("mature252_stage757_dd40_fail_more_than_stage748")
    if float(full["return_delta_pct"]) <= 0.0:
        watch.append("full_2020_01_no_return_improvement_vs_stage748")
    decision = "stage757_monthly_start_not_promoted" if hard_fail else "stage757_monthly_start_watch"
    return {
        "stage": "Stage759",
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "stage748_variant": s748.CANDIDATE_500K_VARIANT,
        "stage757_variant": s757.CANDIDATE_VARIANT,
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
            "stage748_results_reused_from_stage749": True,
            "stage757_account_capital": s748.CAPITAL_500K,
            "stage757_base_risk_multiplier": 0.40,
            "stage757_restored_risk_multiplier": 0.80,
            "stage757_internal_restore_multiplier": 2.00,
            "streak_risk_multipliers": "1.0,1.0,1.0,1.0",
            "enable_recovery_sleeve": False,
            "enable_oi_price_confirm_risk_restore": True,
            "causal_timing": "latest_completed_daily_bar",
        },
        "checks": checks.to_dict("records"),
        "full_2020_01": full.to_dict(),
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "candidate_summary": str(CANDIDATE_SUMMARY_PATH),
            "cost": str(COST_PATH),
            "comparison": str(COMPARISON_PATH),
            "curves": str(CURVES_PATH),
            "checks": str(CHECKS_PATH),
            "report": str(REPORT_PATH),
            "chart": str(CHART_PATH),
            "return_heatmap": str(RETURN_HEATMAP_PATH),
            "delta_heatmap": str(DELTA_HEATMAP_PATH),
            "decision": str(DECISION_PATH),
        },
    }


def _plot_chart(comparison: pd.DataFrame) -> None:
    data = comparison.sort_values("start_ts").copy()
    x = np.arange(len(data))
    labels = data["start_month"].tolist()
    tick_idx = [idx for idx, label in enumerate(labels) if label.endswith("-01") or idx == len(labels) - 1]

    fig, axes = plt.subplots(4, 1, figsize=(18, 14), sharex=True)
    ax_ret, ax_delta, ax_dd, ax_dd_delta = axes
    ax_ret.plot(x, data["b_rebased_total_return_pct"], color="#2563eb", linewidth=1.8, label="Stage748 C50 return")
    ax_ret.plot(x, data["c_rebased_total_return_pct"], color="#059669", linewidth=1.8, label="Stage757 return")
    ax_ret.axhline(0.0, color="#111827", linewidth=0.8)
    ax_ret.set_ylabel("Total return %")
    ax_ret.set_title("Monthly independent starts to 2026-04-30: total return")
    ax_ret.grid(axis="y", alpha=0.25)
    ax_ret.legend(loc="upper right")

    colors = np.where(data["return_delta_pct"] >= 0.0, "#059669", "#dc2626")
    ax_delta.bar(x, data["return_delta_pct"], color=colors, alpha=0.88, width=0.82)
    ax_delta.axhline(0.0, color="#111827", linewidth=0.9)
    ax_delta.set_ylabel("Stage757 - 748 return pp")
    ax_delta.set_title("Return difference: green means Stage757 beats Stage748")
    ax_delta.grid(axis="y", alpha=0.22)

    ax_dd.plot(x, data["b_rebased_max_dd_pct"], color="#2563eb", linewidth=1.7, label="Stage748 max DD")
    ax_dd.plot(x, data["c_rebased_max_dd_pct"], color="#059669", linewidth=1.7, label="Stage757 max DD")
    ax_dd.axhline(-30.0, color="#f97316", linestyle="--", linewidth=0.9, label="DD -30%")
    ax_dd.axhline(-40.0, color="#dc2626", linestyle="--", linewidth=0.9, label="DD -40%")
    ax_dd.set_ylabel("Max DD %")
    ax_dd.set_title("Max drawdown by start month")
    ax_dd.grid(axis="y", alpha=0.25)
    ax_dd.legend(loc="lower right", ncol=2)

    dd_colors = np.where(data["dd_delta_pp"] >= 0.0, "#059669", "#dc2626")
    ax_dd_delta.bar(x, data["dd_delta_pp"], color=dd_colors, alpha=0.88, width=0.82)
    ax_dd_delta.axhline(0.0, color="#111827", linewidth=0.9)
    ax_dd_delta.set_ylabel("Stage757 - 748 DD pp")
    ax_dd_delta.set_title("Drawdown difference: green means Stage757 is shallower")
    ax_dd_delta.grid(axis="y", alpha=0.22)
    ax_dd_delta.set_xticks(tick_idx)
    ax_dd_delta.set_xticklabels([labels[i] for i in tick_idx], rotation=45, ha="right")

    fig.suptitle(
        (
            "Stage759 monthly-start audit: Stage757 vs Stage748 C50 | "
            f"Stage757 return wins {int(data['c_return_wins'].sum())}/{len(data)}, "
            f"DD wins {int(data['c_dd_wins'].sum())}/{len(data)}"
        ),
        fontsize=15,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.965))
    fig.savefig(CHART_PATH, dpi=170)
    plt.close(fig)


def _heat_values(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    return (
        frame.pivot_table(index="start_year", columns="start_month_num", values=column, aggfunc="first")
        .sort_index()
        .reindex(columns=list(range(1, 13)))
    )


def _plot_return_heatmap(stage757: pd.DataFrame) -> None:
    table = _heat_values(stage757, "rebased_total_return_pct")
    values = table.to_numpy(dtype=float)
    finite = values[np.isfinite(values)]
    vmax = max(float(np.nanpercentile(finite, 95)), 100.0) if finite.size else 100.0
    vmin = min(float(np.nanpercentile(finite, 5)), -30.0) if finite.size else -30.0
    norm = TwoSlopeNorm(vmin=vmin, vcenter=0.0, vmax=vmax)
    fig, ax = plt.subplots(figsize=(17, 5.8))
    image = ax.imshow(values, aspect="auto", cmap="RdYlGn", norm=norm)
    ax.set_title("Stage757 return heatmap by start year/month")
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
            text_color = "white" if abs(value) > max(abs(vmin), abs(vmax)) * 0.45 else "#111827"
            ax.text(x, y, f"{value:.0f}", ha="center", va="center", fontsize=8, color=text_color)
    fig.colorbar(image, ax=ax, fraction=0.018, pad=0.01, label="Return %")
    fig.tight_layout()
    fig.savefig(RETURN_HEATMAP_PATH, dpi=170)
    plt.close(fig)


def _plot_delta_heatmap(comparison: pd.DataFrame) -> None:
    ret = _heat_values(comparison, "return_delta_pct")
    dd = _heat_values(comparison, "dd_delta_pp")
    fig, axes = plt.subplots(2, 1, figsize=(17, 8.5))
    specs = [
        (axes[0], ret, "Stage757 - Stage748 total return (percentage points)", "Return pp", "{:.0f}"),
        (axes[1], dd, "Stage757 - Stage748 max drawdown (pp; positive = Stage757 shallower)", "DD pp", "{:.1f}"),
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
    fig.suptitle("Stage759 monthly-start deltas: green favors Stage757, red favors Stage748", fontsize=15)
    fig.tight_layout(rect=(0, 0, 1, 0.955))
    fig.savefig(DELTA_HEATMAP_PATH, dpi=170)
    plt.close(fig)


def _write_report(
    summary: pd.DataFrame,
    candidate: pd.DataFrame,
    cost: pd.DataFrame,
    comparison: pd.DataFrame,
    checks: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    columns = [
        "start_month",
        "trading_days",
        "b_rebased_total_return_pct",
        "c_rebased_total_return_pct",
        "return_delta_pct",
        "return_retention_pct",
        "b_rebased_max_dd_pct",
        "c_rebased_max_dd_pct",
        "dd_delta_pp",
        "b_rebased_sharpe",
        "c_rebased_sharpe",
        "sharpe_delta",
        "b_total_trade_count",
        "c_total_trade_count",
        "trade_count_delta",
    ]
    candidate_columns = [
        "start_month",
        "trading_days",
        "rebased_total_return_pct",
        "rebased_max_dd_pct",
        "rebased_sharpe",
        "total_trade_count",
        "total_slippage",
        "forced_margin_deleverage_count",
        "deployable_pass",
    ]
    lines = [
        "# Stage759 Stage757逐月启动审计",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        f"- B：Stage748 C50 `{s748.CANDIDATE_500K_VARIANT}`，复用 Stage749 逐月结果。",
        f"- C：Stage757 `{s757.CANDIDATE_VARIANT}`，50万，半风险关闭连败/recovery，命中 OI 确认恢复到 `0.80`。",
        f"- 起点范围：`2020-01` 至 `{MONTH_STARTS[-1].strftime('%Y-%m')}`，共 `{len(candidate)}` 个逐月独立启动；统一终点 `{ANALYSIS_END.strftime('%Y-%m-%d')}`。",
        "- 不修改正式配置、不连接 CTP、不调用下单。",
        "",
        "## 外部调研判断",
        "",
        "- CME 与 Britannica 均把 OI 上升配合价格同向视为趋势确认，但不是单独 alpha。",
        "- 本阶段是路径稳健性检验，不再优化 OI 阈值、窗口或恢复倍率。",
        "",
        "## 检查聚合",
        "",
        _md_table(checks, max_rows=40),
        "",
        "## Stage757 最低收益起点",
        "",
        _md_table(candidate.sort_values("rebased_total_return_pct").head(15)[candidate_columns], max_rows=15),
        "",
        "## Stage757 最高收益起点",
        "",
        _md_table(candidate.sort_values("rebased_total_return_pct", ascending=False).head(15)[candidate_columns], max_rows=15),
        "",
        "## Stage757 相对 Stage748 最差增量",
        "",
        _md_table(comparison.sort_values("return_delta_pct").head(15)[columns], max_rows=15),
        "",
        "## Stage757 相对 Stage748 最好增量",
        "",
        _md_table(comparison.sort_values("return_delta_pct", ascending=False).head(15)[columns], max_rows=15),
        "",
        "## 全部月起点明细",
        "",
        _md_table(comparison[columns], max_rows=90),
        "",
        "## Stage757 成本压力",
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
        f"- return_heatmap：`{RETURN_HEATMAP_PATH}`",
        f"- delta_heatmap：`{DELTA_HEATMAP_PATH}`",
        f"- comparison：`{COMPARISON_PATH}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    stage748 = _load_stage748_summary()
    stage748_curves = _load_stage748_curves()
    candidate, cost, candidate_curves = _run_candidate_monthly()
    comparison = _build_comparison(stage748, candidate)
    checks = _checks(candidate, comparison)
    decision = _decision(comparison, checks)

    summary = pd.concat([stage748, candidate], ignore_index=True, sort=False)
    curves = pd.concat([stage748_curves, candidate_curves], ignore_index=True, sort=False)

    _plot_chart(comparison)
    _plot_return_heatmap(candidate)
    _plot_delta_heatmap(comparison)
    _write_report(summary, candidate, cost, comparison, checks, decision)

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    candidate.to_csv(CANDIDATE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    cost.to_csv(COST_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    checks.to_csv(CHECKS_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
