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
import analyze_qmt_roll_stage653_stage526_200k_forced_margin_deleverage as s653
import analyze_qmt_roll_stage660_stage653_multiperiod_live_audit as s660
import analyze_qmt_roll_stage825_stage819_intraday_rule_forensics as s825
import analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine as s847
import analyze_qmt_roll_stage861_stage860_full_visual_atlas as s861
from qmt_roll_official_live_config import OFFICIAL_LIVE_ALIAS, OFFICIAL_LIVE_VERSION


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage928"
MODEL_TAG = "stage928_c9_15w_halfyear_to_latest_v1"
OUTPUT_PREFIX = "qmt_roll_stage928_c9_15w_halfyear_to_latest"

CAPITAL = 150_000.0
CAPITAL_LABEL = "15w"
DATA_START = pd.Timestamp("2018-01-01")
DEFAULT_ANALYSIS_END = pd.Timestamp("2026-06-15")
START_MONTHS = (1, 6)
C9_ARM = "official_live_stage847_c9_15w"
C9_VERSION = "official_live_stage847_c9_30w_stage819_05r_stop_retry_once__capital_15w"

LEGACY_STAGE372_PROFILE_NAME = "stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4"
LEGACY_STAGE372_BASE_PROFILE_NAME = "stage526_200k_force95_to80_largest_margin_r080_pc25_maxpos4"
LEGACY_STAGE372_STRATEGY_OVERRIDES: dict[str, Any] = {
    "enable_streak_entry_structure_risk_recovery": True,
    "streak_entry_structure_recovery_signals": "long_case1a,short_case1a",
    "streak_entry_structure_recovery_min_multiplier": 1.0,
    "streak_entry_structure_recovery_require_flat_portfolio": True,
    "streak_entry_structure_recovery_max_same_direction_corr": 0.30,
    "streak_entry_structure_recovery_require_rsi_confirmation": False,
    "enable_recovery_sleeve": True,
    "recovery_sleeve_base_multiplier_max": 0.1000001,
    "recovery_sleeve_broker_margin_multiplier": 1.65,
    "recovery_sleeve_max_single_contract_broker_margin_to_equity": 0.20,
    "recovery_sleeve_cooldown_days": 20,
    "recovery_sleeve_volume": 1,
}

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
AGG_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_aggregate_{MODEL_TAG}.csv"
COST_STRESS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_cost_stress_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _month_text(value: pd.Timestamp) -> str:
    return pd.Timestamp(value).strftime("%Y-%m")


def _date_text(value: pd.Timestamp) -> str:
    return pd.Timestamp(value).strftime("%Y-%m-%d")


def _window_id(start: pd.Timestamp, end: pd.Timestamp) -> str:
    return f"{_month_text(start).replace('-', '_')}_to_{end.strftime('%Y_%m_%d')}"


def _build_windows(analysis_end: pd.Timestamp) -> list[dict[str, Any]]:
    starts: list[pd.Timestamp] = []
    for year in range(DATA_START.year, analysis_end.year + 1):
        for month in START_MONTHS:
            start = pd.Timestamp(year=year, month=month, day=1)
            if DATA_START <= start <= analysis_end:
                starts.append(start)
    windows: list[dict[str, Any]] = []
    for start in starts:
        windows.append(
            {
                "window_id": _window_id(start, analysis_end),
                "start": start.normalize(),
                "end": analysis_end.normalize(),
                "start_month": _month_text(start),
            }
        )
    return windows


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


def _with_legacy_stage372_spec() -> dict[str, Any]:
    state = {
        "OFFICIAL_LIVE_PROFILE_NAME": s660.OFFICIAL_LIVE_PROFILE_NAME,
        "OFFICIAL_LIVE_BASE_PROFILE_NAME": s660.OFFICIAL_LIVE_BASE_PROFILE_NAME,
        "OFFICIAL_LIVE_ALIAS": s660.OFFICIAL_LIVE_ALIAS,
        "OFFICIAL_LIVE_CAPITAL": s660.OFFICIAL_LIVE_CAPITAL,
        "OFFICIAL_LIVE_STRATEGY_OVERRIDES": s660.OFFICIAL_LIVE_STRATEGY_OVERRIDES,
    }
    s660.OFFICIAL_LIVE_PROFILE_NAME = LEGACY_STAGE372_PROFILE_NAME
    s660.OFFICIAL_LIVE_BASE_PROFILE_NAME = LEGACY_STAGE372_BASE_PROFILE_NAME
    s660.OFFICIAL_LIVE_ALIAS = "Stage372-20w"
    s660.OFFICIAL_LIVE_CAPITAL = 200_000.0
    s660.OFFICIAL_LIVE_STRATEGY_OVERRIDES = dict(LEGACY_STAGE372_STRATEGY_OVERRIDES)
    return state


def _restore_legacy_state(state: dict[str, Any]) -> None:
    for key, value in state.items():
        setattr(s660, key, value)


def _c9_15w_profile(metadata: dict[str, Any], window: dict[str, Any]) -> dict[str, Any]:
    profile = s847._c9_profile(metadata)
    spec = profile["spec"]
    variant = f"{C9_ARM}_{str(window['start_month']).replace('-', '_')}"
    capital = replace(
        spec.capital,
        variant=variant,
        label=f"{CAPITAL_LABEL} {OFFICIAL_LIVE_ALIAS} halfyear cold-start {_month_text(window['start'])}",
        account_capital=CAPITAL,
        c3_capital=CAPITAL,
        note=(
            f"{spec.capital.note} | Stage928 15w cold-start audit. "
            "Only account_capital/c3_capital and independent backtest start are changed; C9 rules are unchanged."
        ),
    )
    result = dict(profile)
    result["profile"] = C9_ARM
    result["spec"] = replace(spec, capital=capital, profile=C9_ARM)
    return result


def _run_window(metadata: dict[str, Any], window: dict[str, Any]) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    original_start = s847.START
    original_end = s847.END
    legacy_state = _with_legacy_stage372_spec()
    try:
        s847.START = pd.Timestamp(window["start"]).normalize()
        s847.END = pd.Timestamp(window["end"]).normalize()
        profile = _c9_15w_profile(metadata, window)
        combined, frames = s847._run_profile(profile, metadata)
        spec = profile["spec"]
    finally:
        s847.START = original_start
        s847.END = original_end
        _restore_legacy_state(legacy_state)

    summary = s650._metrics(combined, spec.capital, cost_multiplier=1.0)
    trades = frames.get("trades", pd.DataFrame()).copy()
    trade_events = frames.get("trade_events", pd.DataFrame()).copy()
    stop_retry_events = frames.get("stop_retry_events", pd.DataFrame()).copy()
    broker10_cap_event_count = 0
    if not trade_events.empty and "reason" in trade_events.columns:
        broker10_cap_event_count = int(
            trade_events["reason"].astype(str).str.startswith("broker10_margin_cap", na=False).sum()
        )
    summary.update(
        {
            "stage": STAGE,
            "model_tag": MODEL_TAG,
            "line_id": LINE_ID,
            "arm_key": C9_ARM,
            "official_live_version": OFFICIAL_LIVE_VERSION,
            "official_live_alias": OFFICIAL_LIVE_ALIAS,
            "capital_label": CAPITAL_LABEL,
            "c9_version": C9_VERSION,
            "window_id": window["window_id"],
            "requested_start_month": window["start_month"],
            "window_start": _date_text(window["start"]),
            "window_end": _date_text(window["end"]),
            "actual_start": pd.to_datetime(combined["date"], errors="coerce").min().date().isoformat(),
            "actual_end": pd.to_datetime(combined["date"], errors="coerce").max().date().isoformat(),
            "trading_days": int(len(combined)),
            "calendar_days": int((pd.Timestamp(window["end"]) - pd.Timestamp(window["start"])).days + 1),
            "positive_return": int(float(summary["total_return_pct"]) > 0.0),
            "dd30_pass": int(float(summary["max_dd_pct"]) >= -30.0),
            "dd40_pass": int(float(summary["max_dd_pct"]) >= -40.0),
            "dd50_pass": int(float(summary["max_dd_pct"]) >= -50.0),
            "broker100_pass": int(float(summary["max_broker10_margin_to_equity_pct"]) <= 100.0 + 1e-9),
            "stop_retry_event_count": int(len(stop_retry_events)),
            "broker10_cap_event_count": broker10_cap_event_count,
            "closed_trade_rows": int(len(trades)),
        }
    )
    curves = combined.copy()
    curves["stage"] = STAGE
    curves["model_tag"] = MODEL_TAG
    curves["arm_key"] = C9_ARM
    curves["window_id"] = window["window_id"]
    curves["requested_start_month"] = window["start_month"]
    curves["window_start"] = _date_text(window["start"])
    curves["window_end"] = _date_text(window["end"])
    curves["account_capital"] = CAPITAL
    curves["nav"] = pd.to_numeric(curves["account_equity"], errors="coerce") / CAPITAL
    curves["drawdown_pct"] = _drawdown_pct(pd.to_numeric(curves["account_equity"], errors="coerce"))
    curves["broker10_margin_to_equity_pct"] = pd.to_numeric(
        curves.get("broker10_margin_to_equity_pct", 0.0),
        errors="coerce",
    ).fillna(0.0)

    cost_rows: list[dict[str, Any]] = []
    for multiplier in s653.COST_MULTIPLIERS:
        row = s650._metrics(combined, spec.capital, cost_multiplier=float(multiplier))
        row.update(
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "line_id": LINE_ID,
                "arm_key": C9_ARM,
                "window_id": window["window_id"],
                "requested_start_month": window["start_month"],
                "window_start": _date_text(window["start"]),
                "window_end": _date_text(window["end"]),
            }
        )
        cost_rows.append(row)
    return summary, curves, pd.DataFrame(cost_rows)


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    values = pd.to_numeric(equity, errors="coerce").ffill()
    peak = values.cummax()
    return (values / peak.replace(0.0, np.nan) - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0) * 100.0


def _aggregate(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    scopes = [
        ("all_windows", summary),
        ("mature_252d_plus", summary[pd.to_numeric(summary["trading_days"], errors="coerce").fillna(0).ge(252)]),
        ("mature_504d_plus", summary[pd.to_numeric(summary["trading_days"], errors="coerce").fillna(0).ge(504)]),
    ]
    for scope, group in scopes:
        returns = pd.to_numeric(group["total_return_pct"], errors="coerce")
        dds = pd.to_numeric(group["max_dd_pct"], errors="coerce")
        sharpes = pd.to_numeric(group["sharpe"], errors="coerce")
        broker = pd.to_numeric(group["max_broker10_margin_to_equity_pct"], errors="coerce")
        min_equity = pd.to_numeric(group["min_equity"], errors="coerce")
        rows.append(
            {
                "scope": scope,
                "window_count": int(len(group)),
                "positive_count": int((returns > 0.0).sum()),
                "positive_rate_pct": float((returns > 0.0).mean() * 100.0) if len(group) else 0.0,
                "median_return_pct": float(returns.median()) if len(group) else np.nan,
                "p10_return_pct": float(returns.quantile(0.10)) if len(group) else np.nan,
                "min_return_pct": float(returns.min()) if len(group) else np.nan,
                "max_return_pct": float(returns.max()) if len(group) else np.nan,
                "median_dd_pct": float(dds.median()) if len(group) else np.nan,
                "worst_dd_pct": float(dds.min()) if len(group) else np.nan,
                "dd30_fail_count": int((dds < -30.0).sum()),
                "dd40_fail_count": int((dds < -40.0).sum()),
                "dd50_fail_count": int((dds < -50.0).sum()),
                "median_sharpe": float(sharpes.median()) if len(group) else np.nan,
                "min_sharpe": float(sharpes.min()) if len(group) else np.nan,
                "peak_broker10_pct": float(broker.max()) if len(group) else np.nan,
                "broker100_fail_count": int((broker > 100.0).sum()),
                "survival_fail_count": int((min_equity <= 0.0).sum()),
                "deployable_pass_count": int(pd.to_numeric(group["deployable_pass"], errors="coerce").fillna(0).sum()),
                "total_trade_count": float(pd.to_numeric(group["total_trade_count"], errors="coerce").fillna(0).sum()),
                "total_slippage": float(pd.to_numeric(group["total_slippage"], errors="coerce").fillna(0).sum()),
                "total_stop_retry_event_count": int(
                    pd.to_numeric(group["stop_retry_event_count"], errors="coerce").fillna(0).sum()
                ),
                "total_broker10_cap_event_count": int(
                    pd.to_numeric(group["broker10_cap_event_count"], errors="coerce").fillna(0).sum()
                ),
            }
        )
    return pd.DataFrame(rows)


def _decision(summary: pd.DataFrame, aggregate: pd.DataFrame, analysis_end: pd.Timestamp) -> dict[str, Any]:
    mature = summary[pd.to_numeric(summary["trading_days"], errors="coerce").fillna(0).ge(252)].copy()
    all_agg = aggregate[aggregate["scope"].eq("all_windows")].iloc[0].to_dict()
    mature_agg = aggregate[aggregate["scope"].eq("mature_252d_plus")].iloc[0].to_dict()
    negative = summary[pd.to_numeric(summary["total_return_pct"], errors="coerce").le(0.0)].copy()
    dd40_fail = summary[pd.to_numeric(summary["max_dd_pct"], errors="coerce").lt(-40.0)].copy()
    broker_fail = summary[pd.to_numeric(summary["max_broker10_margin_to_equity_pct"], errors="coerce").gt(100.0)].copy()
    if int(mature_agg["positive_count"]) == int(mature_agg["window_count"]) and int(mature_agg["broker100_fail_count"]) == 0:
        label = "stage928_c9_15w_mature_windows_all_positive_no_broker100_watch_dd_tail"
    elif int(mature_agg["positive_count"]) == int(mature_agg["window_count"]):
        label = "stage928_c9_15w_mature_windows_all_positive_but_margin_tail"
    else:
        label = "stage928_c9_15w_has_negative_mature_windows"
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "c9_version": C9_VERSION,
        "strategy_rules_changed": False,
        "capital_changed_to": CAPITAL,
        "data_start": DATA_START.date().isoformat(),
        "analysis_end": analysis_end.date().isoformat(),
        "requested_today": "2026-06-16",
        "start_schedule": "Jan 1 and Jun 1 each year",
        "window_count": int(len(summary)),
        "mature_252d_window_count": int(len(mature)),
        "decision_basis": "independent halfyear cold-start windows to latest available completed trading day",
        "aggregate": aggregate.to_dict(orient="records"),
        "negative_windows": negative[
            ["window_id", "window_start", "window_end", "trading_days", "total_return_pct", "max_dd_pct", "sharpe"]
        ].to_dict(orient="records"),
        "dd40_fail_windows": dd40_fail[
            ["window_id", "window_start", "window_end", "trading_days", "total_return_pct", "max_dd_pct", "sharpe"]
        ].to_dict(orient="records"),
        "broker100_fail_windows": broker_fail[
            [
                "window_id",
                "window_start",
                "window_end",
                "trading_days",
                "total_return_pct",
                "max_broker10_margin_to_equity_pct",
                "days_over_100pct",
            ]
        ].to_dict(orient="records"),
        "all_windows_key_metrics": summary[
            [
                "window_id",
                "window_start",
                "window_end",
                "trading_days",
                "end_equity",
                "total_return_pct",
                "max_dd_pct",
                "sharpe",
                "max_broker10_margin_to_equity_pct",
                "total_trade_count",
                "deployable_pass",
            ]
        ].to_dict(orient="records"),
        "decision": label,
        "order_api_called": False,
        "ctp_connected": False,
        "external_research_judgment": (
            "Use the local vn.py/C9 engine for path-dependent cold-start testing; external material supports rolling or "
            "walk-forward validation as a robustness check, not as a new signal source."
        ),
        "overfit_reflection_before": (
            "No: start schedule, 15w capital and latest end date are fixed by the user; no C9 parameters are tuned."
        ),
        "continue_value_before": (
            "Yes: 15w is materially smaller than the prior 30w live capital profile and can expose integer-lot, margin and drawdown tails."
        ),
        "overfit_reflection_after": "",
        "continue_value_after": "",
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "curves": str(CURVES_PATH),
            "aggregate": str(AGG_PATH),
            "cost_stress": str(COST_STRESS_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
        "all_windows_aggregate": all_agg,
        "mature_252d_aggregate": mature_agg,
    }


def _write_report(summary: pd.DataFrame, aggregate: pd.DataFrame, decision: dict[str, Any]) -> None:
    view_cols = [
        "window_id",
        "window_start",
        "window_end",
        "trading_days",
        "end_equity",
        "total_return_pct",
        "max_dd_pct",
        "sharpe",
        "max_broker10_margin_to_equity_pct",
        "days_over_100pct",
        "total_trade_count",
        "total_slippage",
        "stop_retry_event_count",
        "broker10_cap_event_count",
        "deployable_pass",
    ]
    lines = [
        "# Stage928 C9 15w 半年度起点到最新日回测",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M')}`",
        f"- line_id：`{LINE_ID}`",
        f"- 当前官方正式版本：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`。",
        f"- 本次口径：只把初始资金改为 `{CAPITAL:,.0f}`；C9 规则不变。",
        f"- 窗口：从 `{DATA_START.date()}` 起，每年 `1月1日` 和 `6月1日` 独立冷启动，到 `{decision['analysis_end']}`。",
        "- 不连接 CTP，不调用订单 API。",
        "",
        "## Aggregate",
        "",
        _md_table(aggregate, max_rows=10),
        "",
        "## Windows",
        "",
        _md_table(summary[view_cols], max_rows=40),
        "",
        "## Decision",
        "",
        f"- 决策：`{decision['decision']}`",
        "- 所有窗口都是独立回测，不是把 2018 全路径简单截取重算。",
        "- 2026-06 起点只有少量交易日，只能作为最新短样本观察，不作为成熟结论。",
        "",
        "## Outputs",
        "",
    ]
    for key, path in decision["outputs"].items():
        lines.append(f"- {key}: `{path}`")
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    analysis_end = DEFAULT_ANALYSIS_END
    windows = _build_windows(analysis_end)
    print(
        f"[stage928] C9 15w halfyear starts={len(windows)} "
        f"range={DATA_START.date()}->{analysis_end.date()}",
        flush=True,
    )

    metadata = s513._metadata()
    vt_symbols = set(str(item) for item in metadata["vt_symbols"])
    minute_bars = _load_stage861_full_minute_bars(vt_symbols)
    s847.s827._GLOBAL_MINUTE_BY_SYMBOL = s825._minute_groups(minute_bars)

    summary_rows: list[dict[str, Any]] = []
    curves: list[pd.DataFrame] = []
    cost_frames: list[pd.DataFrame] = []
    for idx, window in enumerate(windows, start=1):
        print(f"[stage928] running {idx}/{len(windows)} {window['window_id']}", flush=True)
        row, curve, cost = _run_window(metadata, window)
        summary_rows.append(row)
        curves.append(curve)
        cost_frames.append(cost)

    summary = pd.DataFrame(summary_rows).sort_values("window_start").reset_index(drop=True)
    curves_df = pd.concat(curves, ignore_index=True, sort=False).sort_values(["window_start", "date"]).reset_index(drop=True)
    cost_df = pd.concat(cost_frames, ignore_index=True, sort=False).sort_values(
        ["window_start", "cost_multiplier"]
    ).reset_index(drop=True)
    aggregate = _aggregate(summary)
    decision = _decision(summary, aggregate, analysis_end)

    mature_agg = decision["mature_252d_aggregate"]
    if int(mature_agg["positive_count"]) < int(mature_agg["window_count"]):
        decision["overfit_reflection_after"] = (
            "Yes for treating C9 as capital-agnostic: 15w mature windows include negative outcomes, so the 30w result "
            "cannot be naively scaled down."
        )
        decision["continue_value_after"] = (
            "Yes, but next work should be 15w feasibility/risk attribution, not tuning C9 parameters to these windows."
        )
    elif int(mature_agg["broker100_fail_count"]) > 0 or int(mature_agg["dd40_fail_count"]) > 0:
        decision["overfit_reflection_after"] = (
            "Partial: returns survive the fixed cold starts, but 15w still has margin or drawdown tail fragility."
        )
        decision["continue_value_after"] = (
            "Yes, continue only with capital feasibility and account-risk attribution; do not scan C9 stop/retry parameters."
        )
    else:
        decision["overfit_reflection_after"] = (
            "No immediate overfit signal from this fixed 15w cold-start audit, though C9's historical search origin still "
            "requires forward monitoring."
        )
        decision["continue_value_after"] = "Yes, as a 15w feasibility candidate, subject to execution and margin stress review."

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    curves_df.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    aggregate.to_csv(AGG_PATH, index=False, encoding="utf-8-sig")
    cost_df.to_csv(COST_STRESS_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(summary, aggregate, decision)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print("aggregate")
    print(aggregate.to_string(index=False))
    print("summary")
    print(
        summary[
            [
                "window_id",
                "window_start",
                "window_end",
                "trading_days",
                "end_equity",
                "total_return_pct",
                "max_dd_pct",
                "sharpe",
                "max_broker10_margin_to_equity_pct",
                "deployable_pass",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
