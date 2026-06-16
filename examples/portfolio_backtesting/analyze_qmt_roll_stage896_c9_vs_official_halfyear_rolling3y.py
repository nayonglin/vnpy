from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import analyze_qmt_roll_stage513_stage208_exact_position_margin_audit as s513
import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage660_stage653_multiperiod_live_audit as s660
import analyze_qmt_roll_stage748_half_risk_no_streak_500k as s748
import analyze_qmt_roll_stage772_am40_80_120_oi_monthly as s772
import analyze_qmt_roll_stage825_stage819_intraday_rule_forensics as s825
import analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine as s847
import analyze_qmt_roll_stage861_stage860_full_visual_atlas as s861
import qmt_roll_official_candidate_stage819_30w_config as stage819_cfg
from qmt_roll_official_live_config import (
    OFFICIAL_LIVE_ALIAS,
    OFFICIAL_LIVE_CAPITAL,
    OFFICIAL_LIVE_VERSION,
)


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage896"
MODEL_TAG = "stage896_c9_vs_official_halfyear_rolling3y_v1"
OUTPUT_PREFIX = "qmt_roll_stage896_c9_vs_official_halfyear_rolling3y"

DATA_START = pd.Timestamp("2020-01-01")
DATA_END = pd.Timestamp("2026-05-29")
ROLL_YEARS = 3

C9_ARM = s847.C9_ARM
C9_LABEL = "Stage847 C9 0.5R stop + retry once"
C9_CAPITAL = stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_CAPITAL
C9_VERSION = "stage847_stage819_c4_05r_stop_retry_once"

OFFICIAL_ARM = "official_live_stage372_20w"
WINDOW_GROUP = "stage896_halfyear_rolling_3y"


def _window_end(start: pd.Timestamp) -> pd.Timestamp:
    return (pd.Timestamp(start) + pd.DateOffset(years=ROLL_YEARS) - pd.Timedelta(days=1)).normalize()


def _month_text(value: pd.Timestamp) -> str:
    return pd.Timestamp(value).strftime("%Y-%m")


def _window_id(start: pd.Timestamp, end: pd.Timestamp, terminal_partial: bool = False) -> str:
    suffix = "_terminal_partial" if terminal_partial else ""
    return f"{_month_text(start).replace('-', '_')}_to_{end.strftime('%Y_%m_%d')}{suffix}"


HALF_YEAR_STARTS = tuple(pd.date_range(DATA_START, DATA_END, freq="6MS"))
EXACT_STARTS = tuple(start for start in HALF_YEAR_STARTS if _window_end(start) <= DATA_END)
TERMINAL_START = next((start for start in HALF_YEAR_STARTS if start > EXACT_STARTS[-1]), None)

WINDOWS: list[dict[str, Any]] = [
    {
        "window_id": _window_id(start, _window_end(start)),
        "start": start,
        "end": _window_end(start),
        "terminal_partial": False,
        "complete_3y": True,
    }
    for start in EXACT_STARTS
]
if TERMINAL_START is not None and TERMINAL_START < DATA_END:
    WINDOWS.append(
        {
            "window_id": _window_id(TERMINAL_START, DATA_END, terminal_partial=True),
            "start": TERMINAL_START,
            "end": DATA_END,
            "terminal_partial": True,
            "complete_3y": False,
        }
    )

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
PAIRWISE_AGG_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_pairwise_aggregate_{MODEL_TAG}.csv"
AGG_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_aggregate_{MODEL_TAG}.csv"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _window_label(window: dict[str, Any]) -> str:
    start = pd.Timestamp(window["start"])
    end = pd.Timestamp(window["end"])
    suffix = " terminal partial" if bool(window["terminal_partial"]) else ""
    return f"{_month_text(start)} to {end.strftime('%Y-%m-%d')}{suffix}"


def _metric_from_combined(
    *,
    arm_key: str,
    series_label: str,
    role: str,
    capital_label: str,
    combined: pd.DataFrame,
    spec: Any,
    forced_events: pd.DataFrame,
    window: dict[str, Any],
    extra_metrics: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], pd.DataFrame]:
    start = pd.Timestamp(window["start"]).normalize()
    end = pd.Timestamp(window["end"]).normalize()
    row, curve, _ = s748._metric_row(
        combined,
        spec=spec,
        window_name=f"{window['window_id']}_halfyear_rolling3y",
        window_label=_window_label(window),
        window_group=WINDOW_GROUP,
        forced_events=forced_events,
    )
    row = s772._metric_common(row)
    row.update(extra_metrics or {})
    row.update(
        {
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "arm_key": arm_key,
            "series_label": series_label,
            "role": role,
            "capital_label": capital_label,
            "official_live_version": OFFICIAL_LIVE_VERSION,
            "c9_version": C9_VERSION,
            "requested_start_month": _month_text(start),
            "start_month": _month_text(start),
            "window_start": start.strftime("%Y-%m-%d"),
            "window_end": end.strftime("%Y-%m-%d"),
            "window_id": str(window["window_id"]),
            "rolling_years": ROLL_YEARS,
            "terminal_partial": int(bool(window["terminal_partial"])),
            "complete_3y": int(bool(window["complete_3y"])),
            "positive_return": int(float(row["rebased_total_return_pct"]) > 0.0),
        }
    )

    curve = s772._curve_common(curve)
    curve["stage"] = STAGE
    curve["model_tag"] = MODEL_TAG
    curve["arm_key"] = arm_key
    curve["series_label"] = series_label
    curve["role"] = role
    curve["capital_label"] = capital_label
    curve["requested_start_month"] = _month_text(start)
    curve["start_month"] = _month_text(start)
    curve["window_start"] = start.strftime("%Y-%m-%d")
    curve["window_end"] = end.strftime("%Y-%m-%d")
    curve["window_id"] = str(window["window_id"])
    curve["rolling_years"] = ROLL_YEARS
    curve["terminal_partial"] = int(bool(window["terminal_partial"]))
    curve["complete_3y"] = int(bool(window["complete_3y"]))
    return row, curve


def _run_official(metadata: dict[str, Any], window: dict[str, Any]) -> tuple[dict[str, Any], pd.DataFrame]:
    spec = s660._official_spec(metadata)
    combined, forced_events = s660._run_independent_window(
        spec=spec,
        metadata=metadata,
        analysis_start=pd.Timestamp(window["start"]).normalize(),
        analysis_end=pd.Timestamp(window["end"]).normalize(),
    )
    return _metric_from_combined(
        arm_key=OFFICIAL_ARM,
        series_label=f"{OFFICIAL_LIVE_ALIAS} official live",
        role="A_official_live",
        capital_label="20w",
        combined=combined,
        spec=spec,
        forced_events=forced_events,
        window=window,
        extra_metrics={"stop_retry_event_count": 0, "broker10_cap_event_count": 0},
    )


def _c9_window_profile(metadata: dict[str, Any], window: dict[str, Any]) -> dict[str, Any]:
    profile = s847._c9_profile(metadata)
    spec = profile["spec"]
    capital = replace(
        spec.capital,
        variant=f"{C9_ARM}_{window['window_id']}",
        label=f"{C9_LABEL} {_window_label(window)}",
        account_capital=C9_CAPITAL,
        c3_capital=C9_CAPITAL,
        note=(
            f"{spec.capital.note} | Stage896 half-year rolling 3y audit. "
            "No parameter changes; only the independent backtest start/end are moved."
        ),
    )
    result = dict(profile)
    result["profile"] = C9_ARM
    result["spec"] = replace(spec, capital=capital, profile=C9_ARM)
    return result


def _run_c9(metadata: dict[str, Any], window: dict[str, Any]) -> tuple[dict[str, Any], pd.DataFrame]:
    original_start = s847.START
    original_end = s847.END
    try:
        s847.START = pd.Timestamp(window["start"]).normalize()
        s847.END = pd.Timestamp(window["end"]).normalize()
        profile = _c9_window_profile(metadata, window)
        combined, frames = s847._run_profile(profile, metadata)
    finally:
        s847.START = original_start
        s847.END = original_end

    trade_events = frames.get("trade_events", pd.DataFrame()).copy()
    stop_retry_events = frames.get("stop_retry_events", pd.DataFrame()).copy()
    broker10_cap_event_count = 0
    if not trade_events.empty and "reason" in trade_events.columns:
        broker10_cap_event_count = int(
            trade_events["reason"].astype(str).str.startswith("broker10_margin_cap", na=False).sum()
        )
    extra = {
        "stop_retry_event_count": int(len(stop_retry_events)),
        "broker10_cap_event_count": broker10_cap_event_count,
    }
    return _metric_from_combined(
        arm_key="c9_stage847_stage819_30w",
        series_label=C9_LABEL,
        role="C_c9_intraday_rule_candidate",
        capital_label="30w",
        combined=combined,
        spec=profile["spec"],
        forced_events=pd.DataFrame(),
        window=window,
        extra_metrics=extra,
    )


def _load_stage861_full_minute_bars(vt_symbols: set[str]) -> pd.DataFrame:
    if s861.FULL_MINUTE_BARS_PATH.exists():
        data = pd.read_csv(s861.FULL_MINUTE_BARS_PATH, encoding="utf-8-sig")
    else:
        data = s861._load_full_minute_bars(vt_symbols)
    data = data[data["vt_symbol"].astype(str).isin(vt_symbols)].copy()
    data["bar_datetime"] = pd.to_datetime(data["bar_datetime"], errors="coerce")
    if "bar_date" not in data.columns:
        data["bar_date"] = data["bar_datetime"].dt.normalize()
    else:
        data["bar_date"] = pd.to_datetime(data["bar_date"], errors="coerce").dt.normalize()
    for column in ["open", "high", "low", "close", "volume", "open_oi", "close_oi"]:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
    return data.dropna(subset=["vt_symbol", "bar_datetime", "open", "high", "low", "close"]).reset_index(drop=True)


def _run_all() -> tuple[pd.DataFrame, pd.DataFrame]:
    metadata = s513._metadata()
    vt_symbols = set(str(item) for item in metadata["vt_symbols"])
    minute_bars = _load_stage861_full_minute_bars(vt_symbols)
    s847.s827._GLOBAL_MINUTE_BY_SYMBOL = s825._minute_groups(minute_bars)

    rows: list[dict[str, Any]] = []
    curves: list[pd.DataFrame] = []
    tasks = [(OFFICIAL_ARM, window) for window in WINDOWS] + [("c9_stage847_stage819_30w", window) for window in WINDOWS]
    for idx, (arm_key, window) in enumerate(tasks, start=1):
        print(f"[stage896] running {idx}/{len(tasks)} {arm_key} {window['window_id']}", flush=True)
        if arm_key == OFFICIAL_ARM:
            row, curve = _run_official(metadata, window)
        else:
            row, curve = _run_c9(metadata, window)
        rows.append(row)
        curves.append(curve)

    summary = (
        s772._add_month_fields(pd.DataFrame(rows))
        .sort_values(["window_start", "arm_key"])
        .reset_index(drop=True)
    )
    curve_df = (
        pd.concat(curves, ignore_index=True, sort=False)
        .sort_values(["window_start", "arm_key", "date"])
        .reset_index(drop=True)
    )
    return summary, curve_df


def _aggregate(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for scope, scoped in [
        ("complete_3y", summary[pd.to_numeric(summary["complete_3y"], errors="coerce").fillna(0).eq(1)]),
        ("all_including_terminal_partial", summary),
    ]:
        for arm_key, group in scoped.groupby("arm_key", sort=False):
            returns = pd.to_numeric(group["rebased_total_return_pct"], errors="coerce")
            dds = pd.to_numeric(group["rebased_max_dd_pct"], errors="coerce")
            sharpes = pd.to_numeric(group["rebased_sharpe"], errors="coerce")
            broker = pd.to_numeric(group["max_broker10_margin_to_rebased_equity_pct"], errors="coerce")
            min_equity = pd.to_numeric(group["rebased_min_equity"], errors="coerce")
            rows.append(
                {
                    "scope": scope,
                    "arm_key": arm_key,
                    "series_label": str(group["series_label"].iloc[0]),
                    "role": str(group["role"].iloc[0]),
                    "account_capital": float(group["account_capital"].iloc[0]),
                    "window_count": int(len(group)),
                    "positive_count": int((returns > 0.0).sum()),
                    "positive_rate_pct": float((returns > 0.0).mean() * 100.0),
                    "median_return_pct": float(returns.median()),
                    "p10_return_pct": float(returns.quantile(0.10)),
                    "min_return_pct": float(returns.min()),
                    "max_return_pct": float(returns.max()),
                    "median_dd_pct": float(dds.median()),
                    "worst_dd_pct": float(dds.min()),
                    "dd30_fail_count": int((dds < -30.0).sum()),
                    "dd40_fail_count": int((dds < -40.0).sum()),
                    "dd50_fail_count": int((dds < -50.0).sum()),
                    "median_sharpe": float(sharpes.median()),
                    "p10_sharpe": float(sharpes.quantile(0.10)),
                    "min_sharpe": float(sharpes.min()),
                    "peak_broker10_pct": float(broker.max()),
                    "median_broker10_pct": float(broker.median()),
                    "broker100_fail_count": int((broker > 100.0).sum()),
                    "survival_fail_count": int((min_equity <= 0.0).sum()),
                    "total_trade_count": int(pd.to_numeric(group["total_trade_count"], errors="coerce").fillna(0).sum()),
                    "total_slippage": float(pd.to_numeric(group["total_slippage"], errors="coerce").fillna(0).sum()),
                    "total_stop_retry_event_count": int(
                        pd.to_numeric(group.get("stop_retry_event_count", 0), errors="coerce").fillna(0).sum()
                    ),
                    "total_broker10_cap_event_count": int(
                        pd.to_numeric(group.get("broker10_cap_event_count", 0), errors="coerce").fillna(0).sum()
                    ),
                }
            )
    return pd.DataFrame(rows)


def _comparison(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for window_id, group in summary.groupby("window_id", sort=False):
        indexed = group.set_index("arm_key")
        official = indexed.loc[OFFICIAL_ARM]
        c9 = indexed.loc["c9_stage847_stage819_30w"]
        row = {
            "window_id": window_id,
            "window_start": str(group["window_start"].iloc[0]),
            "window_end": str(group["window_end"].iloc[0]),
            "start_month": str(group["start_month"].iloc[0]),
            "start_year": int(group["start_year"].iloc[0]),
            "start_month_num": int(group["start_month_num"].iloc[0]),
            "complete_3y": int(group["complete_3y"].iloc[0]),
            "terminal_partial": int(group["terminal_partial"].iloc[0]),
            "return_official_pct": float(official["rebased_total_return_pct"]),
            "return_c9_pct": float(c9["rebased_total_return_pct"]),
            "max_dd_official_pct": float(official["rebased_max_dd_pct"]),
            "max_dd_c9_pct": float(c9["rebased_max_dd_pct"]),
            "sharpe_official": float(official["rebased_sharpe"]),
            "sharpe_c9": float(c9["rebased_sharpe"]),
            "broker10_official_pct": float(official["max_broker10_margin_to_rebased_equity_pct"]),
            "broker10_c9_pct": float(c9["max_broker10_margin_to_rebased_equity_pct"]),
            "end_equity_official": float(official["rebased_end_equity"]),
            "end_equity_c9": float(c9["rebased_end_equity"]),
            "trades_official": float(official["total_trade_count"]),
            "trades_c9": float(c9["total_trade_count"]),
            "slippage_official": float(official["total_slippage"]),
            "slippage_c9": float(c9["total_slippage"]),
            "stop_retry_event_count_c9": int(float(c9.get("stop_retry_event_count", 0) or 0)),
            "broker10_cap_event_count_c9": int(float(c9.get("broker10_cap_event_count", 0) or 0)),
        }
        row["return_delta_c9_vs_official_pp"] = row["return_c9_pct"] - row["return_official_pct"]
        row["max_dd_delta_c9_vs_official_pp"] = row["max_dd_c9_pct"] - row["max_dd_official_pct"]
        row["sharpe_delta_c9_vs_official"] = row["sharpe_c9"] - row["sharpe_official"]
        row["broker10_delta_c9_vs_official_pp"] = row["broker10_c9_pct"] - row["broker10_official_pct"]
        row["c9_return_win"] = int(row["return_c9_pct"] > row["return_official_pct"])
        row["c9_dd_win"] = int(row["max_dd_c9_pct"] > row["max_dd_official_pct"])
        row["c9_sharpe_win"] = int(row["sharpe_c9"] > row["sharpe_official"])
        row["c9_broker10_win"] = int(row["broker10_c9_pct"] < row["broker10_official_pct"])
        row["c9_return_dd_double_win"] = int(row["c9_return_win"] and row["c9_dd_win"])
        rows.append(row)
    return pd.DataFrame(rows).sort_values("window_start").reset_index(drop=True)


def _pairwise_aggregate(comparison: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for scope, group in [
        ("complete_3y", comparison[pd.to_numeric(comparison["complete_3y"], errors="coerce").fillna(0).eq(1)]),
        ("all_including_terminal_partial", comparison),
    ]:
        rows.append(
            {
                "scope": scope,
                "window_count": int(len(group)),
                "c9_return_win_count": int(group["c9_return_win"].sum()),
                "c9_dd_win_count": int(group["c9_dd_win"].sum()),
                "c9_sharpe_win_count": int(group["c9_sharpe_win"].sum()),
                "c9_broker10_win_count": int(group["c9_broker10_win"].sum()),
                "c9_return_dd_double_win_count": int(group["c9_return_dd_double_win"].sum()),
                "median_return_delta_pp": float(pd.to_numeric(group["return_delta_c9_vs_official_pp"], errors="coerce").median()),
                "p10_return_delta_pp": float(pd.to_numeric(group["return_delta_c9_vs_official_pp"], errors="coerce").quantile(0.10)),
                "min_return_delta_pp": float(pd.to_numeric(group["return_delta_c9_vs_official_pp"], errors="coerce").min()),
                "median_dd_delta_pp": float(pd.to_numeric(group["max_dd_delta_c9_vs_official_pp"], errors="coerce").median()),
                "p10_dd_delta_pp": float(pd.to_numeric(group["max_dd_delta_c9_vs_official_pp"], errors="coerce").quantile(0.10)),
                "min_dd_delta_pp": float(pd.to_numeric(group["max_dd_delta_c9_vs_official_pp"], errors="coerce").min()),
                "median_sharpe_delta": float(pd.to_numeric(group["sharpe_delta_c9_vs_official"], errors="coerce").median()),
                "median_broker10_delta_pp": float(pd.to_numeric(group["broker10_delta_c9_vs_official_pp"], errors="coerce").median()),
            }
        )
    return pd.DataFrame(rows)


def _decision(aggregate: pd.DataFrame, pairwise_agg: pd.DataFrame, comparison: pd.DataFrame) -> dict[str, Any]:
    exact_agg = aggregate[aggregate["scope"].eq("complete_3y")].set_index("arm_key").to_dict(orient="index")
    exact_pair = pairwise_agg[pairwise_agg["scope"].eq("complete_3y")].iloc[0].to_dict()
    window_count = int(exact_pair["window_count"])
    majority = window_count / 2.0
    c9_hard_fail = (
        int(exact_agg["c9_stage847_stage819_30w"]["dd40_fail_count"]) > int(exact_agg[OFFICIAL_ARM]["dd40_fail_count"])
        or int(exact_agg["c9_stage847_stage819_30w"]["dd50_fail_count"]) > int(exact_agg[OFFICIAL_ARM]["dd50_fail_count"])
        or int(exact_agg["c9_stage847_stage819_30w"]["broker100_fail_count"]) > 0
        or int(exact_agg["c9_stage847_stage819_30w"]["survival_fail_count"]) > 0
    )
    c9_majority = (
        int(exact_pair["c9_return_win_count"]) > majority
        and int(exact_pair["c9_sharpe_win_count"]) > majority
        and int(exact_pair["c9_dd_win_count"]) >= majority
    )
    if c9_majority and not c9_hard_fail:
        label = "stage896_c9_halfyear_rolling3y_has_candidate_value_needs_ab_sop"
    elif int(exact_pair["c9_return_win_count"]) > majority and c9_hard_fail:
        label = "stage896_c9_right_tail_with_risk_tail_not_official_replacement"
    else:
        label = "stage896_c9_not_official_replacement_keep_stage372_default"

    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "data_start": DATA_START.strftime("%Y-%m-%d"),
        "data_end": DATA_END.strftime("%Y-%m-%d"),
        "roll_years": ROLL_YEARS,
        "step": "6 months",
        "complete_window_count": int(sum(1 for item in WINDOWS if bool(item["complete_3y"]))),
        "terminal_partial_count": int(sum(1 for item in WINDOWS if bool(item["terminal_partial"]))),
        "decision_basis": "complete_3y_windows_only",
        "arms": {
            "A": {
                "arm_key": OFFICIAL_ARM,
                "version": OFFICIAL_LIVE_VERSION,
                "capital": OFFICIAL_LIVE_CAPITAL,
            },
            "C": {
                "arm_key": "c9_stage847_stage819_30w",
                "version": C9_VERSION,
                "source_candidate": stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION,
                "capital": C9_CAPITAL,
            },
        },
        "aggregate": aggregate.to_dict(orient="records"),
        "pairwise_aggregate": pairwise_agg.to_dict(orient="records"),
        "complete_windows": comparison[comparison["complete_3y"].eq(1)].to_dict(orient="records"),
        "decision": label,
        "c9_hard_fail": bool(c9_hard_fail),
        "c9_majority": bool(c9_majority),
        "strategy_changed": False,
        "official_config_changed": False,
        "ctp_connected": False,
        "order_api_called": False,
        "formal_ab_triggered": False,
        "external_research_judgment": (
            "Walk-forward or rolling-window validation is useful here only as a robustness audit; "
            "the implementation remains the repository's vn.py portfolio engine to preserve path-dependent state."
        ),
        "overfit_reflection_before": (
            "No: this run does not tune thresholds; windows and metrics are fixed before execution. "
            "Residual overfit risk is inherited from the historical creation of C9."
        ),
        "continue_value_before": (
            "Yes: C9 had prior full-cycle value versus C4, and a half-year rolling audit can expose whether that value "
            "survives cold starts and path dependence."
        ),
        "overfit_reflection_after": "",
        "continue_value_after": "",
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "curves": str(CURVES_PATH),
            "comparison": str(COMPARISON_PATH),
            "aggregate": str(AGG_PATH),
            "pairwise_aggregate": str(PAIRWISE_AGG_PATH),
            "report": str(REPORT_PATH),
            "decision": str(DECISION_PATH),
        },
    }


def _write_report(
    summary: pd.DataFrame,
    aggregate: pd.DataFrame,
    comparison: pd.DataFrame,
    pairwise_agg: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    exact_view_cols = [
        "window_id",
        "window_start",
        "window_end",
        "return_official_pct",
        "return_c9_pct",
        "return_delta_c9_vs_official_pp",
        "max_dd_official_pct",
        "max_dd_c9_pct",
        "max_dd_delta_c9_vs_official_pp",
        "sharpe_official",
        "sharpe_c9",
        "sharpe_delta_c9_vs_official",
        "broker10_official_pct",
        "broker10_c9_pct",
        "broker10_delta_c9_vs_official_pp",
        "c9_return_win",
        "c9_dd_win",
        "c9_sharpe_win",
    ]
    lines = [
        "# Stage896 C9 vs 正式版半年步进3年滚动测试",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M')}`",
        f"- line_id：`{LINE_ID}`",
        f"- A 正式版：`{OFFICIAL_LIVE_VERSION}`，本金 `{OFFICIAL_LIVE_CAPITAL:.0f}`。",
        f"- C9：`{C9_VERSION}`，来源候选 `{stage819_cfg.OFFICIAL_CANDIDATE_STAGE819_30W_VERSION}`，本金 `{C9_CAPITAL:.0f}`。",
        f"- 窗口：从 `{DATA_START.date()}` 开始，半年一个起点，完整 `3` 年窗口 `{len(EXACT_STARTS)}` 个；末端不足3年的 `{TERMINAL_START.date() if TERMINAL_START is not None else 'none'} -> {DATA_END.date()}` 仅作补充。",
        "- 本阶段不修改正式配置、不连接 CTP、不调用订单 API。",
        "",
        "## Aggregate",
        "",
        _md_table(aggregate, max_rows=20),
        "",
        "## Pairwise Aggregate",
        "",
        _md_table(pairwise_agg, max_rows=10),
        "",
        "## Complete 3Y Windows",
        "",
        _md_table(comparison[comparison["complete_3y"].eq(1)][exact_view_cols], max_rows=20),
        "",
        "## Terminal Partial",
        "",
        _md_table(comparison[comparison["terminal_partial"].eq(1)][exact_view_cols], max_rows=5),
        "",
        "## Decision",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- 主结论只按完整3年窗口判断；terminal partial 仅作为最近路径观察。",
        "- 绝对期末权益因 A/C 本金不同只作旁证，核心比较使用收益率、回撤率、Sharpe 和 broker10 保证金占权益。",
        "",
        "## Outputs",
        "",
    ]
    for key, path in decision["outputs"].items():
        lines.append(f"- {key}: `{path}`")
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(
        f"[stage896] windows={len(WINDOWS)} complete_3y={len(EXACT_STARTS)} "
        f"terminal_partial={sum(int(bool(item['terminal_partial'])) for item in WINDOWS)}",
        flush=True,
    )
    summary, curves = _run_all()
    aggregate = _aggregate(summary)
    comparison = _comparison(summary)
    pairwise_agg = _pairwise_aggregate(comparison)
    decision = _decision(aggregate, pairwise_agg, comparison)

    exact_pair = pairwise_agg[pairwise_agg["scope"].eq("complete_3y")].iloc[0]
    c9_exact = aggregate[
        aggregate["scope"].eq("complete_3y") & aggregate["arm_key"].eq("c9_stage847_stage819_30w")
    ].iloc[0]
    official_exact = aggregate[
        aggregate["scope"].eq("complete_3y") & aggregate["arm_key"].eq(OFFICIAL_ARM)
    ].iloc[0]
    if bool(decision["c9_majority"]) and not bool(decision["c9_hard_fail"]):
        decision["overfit_reflection_after"] = (
            "No immediate overfit signal from this audit, but C9 would still need formal A/B discipline because it was born "
            "from prior intraday-rule search."
        )
        decision["continue_value_after"] = "Yes: the rolling result is strong enough to justify A/B SOP review, not live promotion."
    elif int(exact_pair["c9_return_win_count"]) > int(exact_pair["window_count"]) / 2:
        decision["overfit_reflection_after"] = (
            "Partial: C9 shows return value, but risk-tail weakness means the historical rule may be harvesting right-tail "
            "while accepting path fragility."
        )
        decision["continue_value_after"] = "Yes, but only for risk-tail attribution; not for immediate official replacement."
    else:
        decision["overfit_reflection_after"] = (
            "Yes as a promotion candidate: C9 does not dominate the fixed rolling windows, so its prior full-cycle edge is "
            "too path-dependent to treat as robust."
        )
        decision["continue_value_after"] = "Limited: continue only if attribution reveals a simple non-fitted risk-control issue."

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    aggregate.to_csv(AGG_PATH, index=False, encoding="utf-8-sig")
    pairwise_agg.to_csv(PAIRWISE_AGG_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(summary, aggregate, comparison, pairwise_agg, decision)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print("aggregate")
    print(aggregate.to_string(index=False))
    print("pairwise_aggregate")
    print(pairwise_agg.to_string(index=False))
    print("complete_window_comparison")
    print(comparison[comparison["complete_3y"].eq(1)].to_string(index=False))
    print(
        "official_complete",
        official_exact[["median_return_pct", "worst_dd_pct", "median_sharpe", "peak_broker10_pct"]].to_dict(),
    )
    print(
        "c9_complete",
        c9_exact[["median_return_pct", "worst_dd_pct", "median_sharpe", "peak_broker10_pct"]].to_dict(),
    )


if __name__ == "__main__":
    main()
