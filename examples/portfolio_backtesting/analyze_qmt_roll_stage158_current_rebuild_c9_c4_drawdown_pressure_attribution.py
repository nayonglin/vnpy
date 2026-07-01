from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage156_current_rebuild_three_arm_annual_baseline as s156
import analyze_qmt_roll_stage157_current_rebuild_c9_stop_retry_attribution as s157


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage158"
MODEL_TAG = "stage158_current_rebuild_c9_c4_drawdown_pressure_attribution_v1"
OUTPUT_PREFIX = "qmt_roll_stage158_current_rebuild_c9_c4_drawdown_pressure_attribution"

DAILY_DELTA_PATH = s157.DAILY_DELTA_PATH
STOP_RETRY_EVENTS_PATH = s157.STOP_RETRY_EVENTS_PATH

WINDOW_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_window_summary_{MODEL_TAG}.csv"
PRESSURE_DAYS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_pressure_days_{MODEL_TAG}.csv"
EVENT_WINDOW_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_event_window_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _drawdown(equity: pd.Series) -> tuple[pd.Series, pd.Series]:
    values = pd.to_numeric(equity, errors="coerce").ffill()
    peak = values.cummax()
    dd = (values / peak.replace(0.0, np.nan) - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0) * 100.0
    return dd, peak


def _normalize_event_dates(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return events.copy()
    result = events.copy()
    result["event_date"] = s157._event_date_series(result["datetime"])
    return result


def _window_events(events: pd.DataFrame, start_month: str, start_date: pd.Timestamp, end_date: pd.Timestamp) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()
    frame = events[
        events["requested_start_month"].astype(str).eq(start_month)
        & pd.to_datetime(events["event_date"], errors="coerce").between(start_date, end_date)
    ].copy()
    return frame


def _window_event_summary(
    events: pd.DataFrame,
    *,
    start_month: str,
    window_name: str,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> dict[str, Any]:
    frame = _window_events(events, start_month, start_date, end_date)
    if frame.empty:
        return {
            "requested_start_month": start_month,
            "window_name": window_name,
            "window_start": start_date.date().isoformat(),
            "window_end": end_date.date().isoformat(),
            "event_count": 0,
            "retry_reentered_count": 0,
            "retry_failed_count": 0,
            "top_products": "",
            "state_counts": "",
        }
    products = frame["product_vt_symbol"].astype(str).value_counts().head(8)
    states = frame["final_state"].astype(str).value_counts()
    return {
        "requested_start_month": start_month,
        "window_name": window_name,
        "window_start": start_date.date().isoformat(),
        "window_end": end_date.date().isoformat(),
        "event_count": int(len(frame)),
        "retry_reentered_count": int(pd.to_numeric(frame["retry_reentered"], errors="coerce").fillna(0).sum()),
        "retry_failed_count": int(pd.to_numeric(frame["retry_failed"], errors="coerce").fillna(0).sum()),
        "top_products": ",".join(f"{key}:{int(value)}" for key, value in products.items()),
        "state_counts": ",".join(f"{key}:{int(value)}" for key, value in states.items()),
    }


def _peak_date_before(frame: pd.DataFrame, equity_col: str, trough_idx: int) -> pd.Timestamp:
    prefix = frame.iloc[: trough_idx + 1].copy()
    values = pd.to_numeric(prefix[equity_col], errors="coerce").ffill()
    max_value = values.max()
    peaks = prefix[values.eq(max_value)]
    if peaks.empty:
        return pd.Timestamp(prefix["date"].iloc[0])
    return pd.Timestamp(peaks["date"].iloc[-1]).normalize()


def _summarize_start(group: pd.DataFrame, events: pd.DataFrame) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    frame = group.copy().sort_values("date").reset_index(drop=True)
    start_month = str(frame["requested_start_month"].iloc[0])
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    c4_dd, c4_peak = _drawdown(frame["account_equity_c4"])
    c9_dd, c9_peak = _drawdown(frame["account_equity_c9"])
    frame["drawdown_c4_pct"] = c4_dd
    frame["drawdown_c9_pct"] = c9_dd
    frame["peak_equity_c4"] = c4_peak
    frame["peak_equity_c9"] = c9_peak
    frame["c9_minus_c4_dd_pct"] = frame["drawdown_c9_pct"] - frame["drawdown_c4_pct"]
    frame["c9_equity_over_c4"] = frame["account_equity_c9"] - frame["account_equity_c4"]
    frame["c9_peak_over_c4_peak"] = frame["peak_equity_c9"] - frame["peak_equity_c4"]

    c9_trough_idx = int(frame["drawdown_c9_pct"].idxmin())
    c4_trough_idx = int(frame["drawdown_c4_pct"].idxmin())
    dd_gap_idx = int(frame["c9_minus_c4_dd_pct"].idxmin())
    c9_peak_date = _peak_date_before(frame, "account_equity_c9", c9_trough_idx)
    c4_peak_date = _peak_date_before(frame, "account_equity_c4", c4_trough_idx)
    c9_trough_date = pd.Timestamp(frame.loc[c9_trough_idx, "date"]).normalize()
    c4_trough_date = pd.Timestamp(frame.loc[c4_trough_idx, "date"]).normalize()
    dd_gap_date = pd.Timestamp(frame.loc[dd_gap_idx, "date"]).normalize()

    c9_window = frame[frame["date"].between(c9_peak_date, c9_trough_date)].copy()
    c4_window = frame[frame["date"].between(c4_peak_date, c4_trough_date)].copy()
    gap_window_start = max(frame["date"].min(), dd_gap_date - pd.Timedelta(days=30))
    gap_window_end = min(frame["date"].max(), dd_gap_date + pd.Timedelta(days=30))
    gap_window = frame[frame["date"].between(gap_window_start, gap_window_end)].copy()

    def max_col(window: pd.DataFrame, column: str) -> float:
        if window.empty:
            return 0.0
        return float(pd.to_numeric(window[column], errors="coerce").fillna(0.0).max())

    def sum_col(window: pd.DataFrame, column: str) -> float:
        if window.empty:
            return 0.0
        return float(pd.to_numeric(window[column], errors="coerce").fillna(0.0).sum())

    c9_event_summary = _window_event_summary(
        events,
        start_month=start_month,
        window_name="c9_max_dd_peak_to_trough",
        start_date=c9_peak_date,
        end_date=c9_trough_date,
    )
    gap_event_summary = _window_event_summary(
        events,
        start_month=start_month,
        window_name="dd_gap_plusminus_30d",
        start_date=gap_window_start,
        end_date=gap_window_end,
    )
    event_rows = [c9_event_summary, gap_event_summary]

    trough = frame.loc[c9_trough_idx]
    gap = frame.loc[dd_gap_idx]
    if float(trough["account_equity_c9"]) >= float(trough["account_equity_c4"]):
        trough_shape = "c9_deeper_pct_but_abs_equity_higher"
    else:
        trough_shape = "c9_deeper_pct_and_abs_equity_lower"
    if float(gap["account_equity_c9"]) >= float(gap["account_equity_c4"]):
        gap_shape = "c9_worse_dd_pct_but_abs_equity_higher"
    else:
        gap_shape = "c9_worse_dd_pct_and_abs_equity_lower"

    summary = {
        "requested_start_month": start_month,
        "actual_start": pd.Timestamp(frame["date"].iloc[0]).date().isoformat(),
        "actual_end": pd.Timestamp(frame["date"].iloc[-1]).date().isoformat(),
        "c4_max_dd_pct": float(frame["drawdown_c4_pct"].min()),
        "c9_max_dd_pct": float(frame["drawdown_c9_pct"].min()),
        "c9_minus_c4_max_dd_pp": float(frame["drawdown_c9_pct"].min() - frame["drawdown_c4_pct"].min()),
        "c9_max_dd_peak_date": c9_peak_date.date().isoformat(),
        "c9_max_dd_trough_date": c9_trough_date.date().isoformat(),
        "c9_max_dd_duration_days": int((c9_trough_date - c9_peak_date).days),
        "c4_max_dd_peak_date": c4_peak_date.date().isoformat(),
        "c4_max_dd_trough_date": c4_trough_date.date().isoformat(),
        "c4_max_dd_duration_days": int((c4_trough_date - c4_peak_date).days),
        "dd_gap_min_pct": float(frame["c9_minus_c4_dd_pct"].min()),
        "dd_gap_min_date": dd_gap_date.date().isoformat(),
        "c9_dd_at_gap_pct": float(gap["drawdown_c9_pct"]),
        "c4_dd_at_gap_pct": float(gap["drawdown_c4_pct"]),
        "c9_equity_at_gap": float(gap["account_equity_c9"]),
        "c4_equity_at_gap": float(gap["account_equity_c4"]),
        "gap_shape": gap_shape,
        "c9_equity_at_trough": float(trough["account_equity_c9"]),
        "c4_equity_at_c9_trough": float(trough["account_equity_c4"]),
        "c9_peak_equity_before_trough": float(trough["peak_equity_c9"]),
        "c4_peak_equity_at_c9_trough": float(trough["peak_equity_c4"]),
        "trough_shape": trough_shape,
        "c9_window_net_pnl_delta_sum": sum_col(c9_window, "c9_minus_c4_net_pnl"),
        "c9_window_event_count": c9_event_summary["event_count"],
        "c9_window_retry_failed_count": c9_event_summary["retry_failed_count"],
        "c9_window_reentered_count": c9_event_summary["retry_reentered_count"],
        "c9_window_max_broker10_c4": max_col(c9_window, "broker10_margin_to_equity_pct_c4"),
        "c9_window_max_broker10_c9": max_col(c9_window, "broker10_margin_to_equity_pct_c9"),
        "c9_window_max_broker10_delta": max_col(c9_window, "c9_minus_c4_broker10"),
        "gap_window_net_pnl_delta_sum": sum_col(gap_window, "c9_minus_c4_net_pnl"),
        "gap_window_event_count": gap_event_summary["event_count"],
        "gap_window_retry_failed_count": gap_event_summary["retry_failed_count"],
        "gap_window_reentered_count": gap_event_summary["retry_reentered_count"],
        "gap_window_max_broker10_c4": max_col(gap_window, "broker10_margin_to_equity_pct_c4"),
        "gap_window_max_broker10_c9": max_col(gap_window, "broker10_margin_to_equity_pct_c9"),
        "gap_window_max_broker10_delta": max_col(gap_window, "c9_minus_c4_broker10"),
    }

    pressure_days = frame.nsmallest(20, "c9_minus_c4_dd_pct")[
        [
            "requested_start_month",
            "date",
            "drawdown_c4_pct",
            "drawdown_c9_pct",
            "c9_minus_c4_dd_pct",
            "account_equity_c4",
            "account_equity_c9",
            "c9_equity_over_c4",
            "peak_equity_c4",
            "peak_equity_c9",
            "c9_peak_over_c4_peak",
            "broker10_margin_to_equity_pct_c4",
            "broker10_margin_to_equity_pct_c9",
            "c9_minus_c4_broker10",
            "stop_retry_event_count",
            "retry_failed_count",
            "reentered_count",
            "c9_minus_c4_net_pnl",
        ]
    ].copy()
    pressure_days["date"] = pressure_days["date"].dt.date.astype(str)
    return summary, pressure_days.to_dict(orient="records"), event_rows


def _write_report(
    *,
    window_summary: pd.DataFrame,
    event_window_summary: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    view_cols = [
        "requested_start_month",
        "c4_max_dd_pct",
        "c9_max_dd_pct",
        "c9_minus_c4_max_dd_pp",
        "dd_gap_min_pct",
        "dd_gap_min_date",
        "gap_shape",
        "trough_shape",
        "c9_window_event_count",
        "c9_window_retry_failed_count",
        "c9_window_max_broker10_delta",
        "gap_window_event_count",
        "gap_window_retry_failed_count",
        "gap_window_max_broker10_delta",
    ]
    event_cols = [
        "requested_start_month",
        "window_name",
        "window_start",
        "window_end",
        "event_count",
        "retry_reentered_count",
        "retry_failed_count",
        "top_products",
        "state_counts",
    ]
    lines = [
        "# Stage158 当前重建版 C9/C4 回撤压力归因",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        f"- 输入 daily delta：`{DAILY_DELTA_PATH}`",
        f"- 输入 stop/retry events：`{STOP_RETRY_EVENTS_PATH}`",
        "- 性质：只读归因；不重跑策略、不连接 CTP、不调用订单 API。",
        "",
        "## Window Summary",
        "",
        _md_table(window_summary[view_cols], max_rows=80),
        "",
        "## Event Windows",
        "",
        _md_table(event_window_summary[event_cols], max_rows=80),
        "",
        "## Decision",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- 过拟合反思：{decision['overfit_reflection_after']}",
        f"- 继续价值反思：{decision['continue_value_after']}",
        "",
        "## Outputs",
        "",
    ]
    for key, path in decision["outputs"].items():
        lines.append(f"- {key}: `{path}`")
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    if not DAILY_DELTA_PATH.exists():
        raise FileNotFoundError(f"missing Stage157 daily delta: {DAILY_DELTA_PATH}")
    if not STOP_RETRY_EVENTS_PATH.exists():
        raise FileNotFoundError(f"missing Stage157 stop/retry events: {STOP_RETRY_EVENTS_PATH}")
    daily_delta = pd.read_csv(DAILY_DELTA_PATH, encoding="utf-8-sig")
    daily_delta["date"] = pd.to_datetime(daily_delta["date"], errors="coerce").dt.normalize()
    events = pd.read_csv(STOP_RETRY_EVENTS_PATH, encoding="utf-8-sig")
    events = _normalize_event_dates(events)

    summary_rows: list[dict[str, Any]] = []
    pressure_rows: list[dict[str, Any]] = []
    event_rows: list[dict[str, Any]] = []
    for start_month, group in daily_delta.groupby("requested_start_month", sort=True):
        summary, pressure, event_summary = _summarize_start(group, events)
        summary_rows.append(summary)
        pressure_rows.extend(pressure)
        event_rows.extend(event_summary)

    window_summary = pd.DataFrame(summary_rows)
    pressure_days = pd.DataFrame(pressure_rows)
    event_window_summary = pd.DataFrame(event_rows)

    worse_dd = window_summary[window_summary["c9_minus_c4_max_dd_pp"].lt(0.0)].copy()
    abs_equity_higher_gap = window_summary[
        window_summary["gap_shape"].astype(str).eq("c9_worse_dd_pct_but_abs_equity_higher")
    ].copy()
    event_heavy = window_summary.sort_values("c9_window_event_count", ascending=False).head(3)
    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_daily_delta": str(DAILY_DELTA_PATH),
        "source_stop_retry_events": str(STOP_RETRY_EVENTS_PATH),
        "sample_count": int(len(window_summary)),
        "c9_max_dd_worse_than_c4_count": int(len(worse_dd)),
        "c9_worse_dd_gap_but_abs_equity_higher_count": int(len(abs_equity_higher_gap)),
        "worst_dd_gap_row": (
            window_summary.sort_values("dd_gap_min_pct").head(1).to_dict(orient="records")[0]
            if not window_summary.empty
            else {}
        ),
        "top_event_count_rows": event_heavy.to_dict(orient="records"),
        "decision": "stage158_c9_c4_drawdown_pressure_readonly_no_new_rule",
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "external_research_judgment": (
            "Skipped external search per operator constraint; this is a local pressure-window attribution from Stage157 outputs."
        ),
        "overfit_reflection_before": (
            "否。只读 Stage157/156 固定输出，分析回撤窗口和账户状态，不改策略参数。"
        ),
        "continue_value_before": (
            "是。Stage157 显示 C9 优势主要在后续路径，必须定位回撤差是否来自绝对亏损、峰值回吐或保证金压力。"
        ),
        "overfit_reflection_after": (
            "否。本阶段只给压力标签和窗口，不生成产品、日期、状态过滤规则。"
        ),
        "continue_value_after": (
            "是。下一步应围绕 C9 回撤差窗口做账户层 survival/heat 只读反事实，而不是扫 C9 stop/retry 参数。"
        ),
        "outputs": {
            "window_summary": str(WINDOW_SUMMARY_PATH),
            "pressure_days": str(PRESSURE_DAYS_PATH),
            "event_window_summary": str(EVENT_WINDOW_SUMMARY_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }

    window_summary.to_csv(WINDOW_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    pressure_days.to_csv(PRESSURE_DAYS_PATH, index=False, encoding="utf-8-sig")
    event_window_summary.to_csv(EVENT_WINDOW_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(
        window_summary=window_summary,
        event_window_summary=event_window_summary,
        decision=decision,
    )
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print("window_summary")
    print(window_summary.to_string(index=False))
    print("event_window_summary")
    print(event_window_summary.to_string(index=False))


if __name__ == "__main__":
    main()
