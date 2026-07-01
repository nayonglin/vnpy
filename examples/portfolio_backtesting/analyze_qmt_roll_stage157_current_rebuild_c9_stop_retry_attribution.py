from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage156_current_rebuild_three_arm_annual_baseline as s156


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage157"
MODEL_TAG = "stage157_current_rebuild_c9_stop_retry_attribution_v1"
OUTPUT_PREFIX = "qmt_roll_stage157_current_rebuild_c9_stop_retry_attribution"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
DAILY_DELTA_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_daily_delta_{MODEL_TAG}.csv"
STOP_RETRY_EVENTS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stop_retry_events_{MODEL_TAG}.csv"
STATE_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_state_summary_{MODEL_TAG}.csv"
PRODUCT_SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_product_summary_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _date_text(value: Any) -> str:
    return pd.Timestamp(value).date().isoformat()


def _event_date_series(values: pd.Series) -> pd.Series:
    def normalize_one(value: Any) -> pd.Timestamp:
        ts = pd.Timestamp(value)
        if pd.isna(ts):
            return pd.NaT
        if ts.tzinfo is not None:
            ts = ts.tz_localize(None)
        return ts.normalize()

    return values.map(normalize_one)


def _normal_daily(frame: pd.DataFrame, arm: str) -> pd.DataFrame:
    result = frame.copy()
    result["date"] = pd.to_datetime(result["date"], errors="coerce").dt.normalize()
    result = result.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    keep = ["date", "account_equity", "net_pnl", "trade_count", "slippage", "broker10_margin_to_equity_pct"]
    for column in keep:
        if column not in result.columns:
            result[column] = 0.0
    result = result[keep].copy()
    for column in keep:
        if column != "date":
            result[column] = pd.to_numeric(result[column], errors="coerce").fillna(0.0)
    return result.rename(columns={column: f"{column}_{arm}" for column in keep if column != "date"})


def _daily_delta(
    *,
    c4: pd.DataFrame,
    c9: pd.DataFrame,
    events: pd.DataFrame,
    start: pd.Timestamp,
) -> pd.DataFrame:
    c4_daily = _normal_daily(c4, "c4")
    c9_daily = _normal_daily(c9, "c9")
    merged = c4_daily.merge(c9_daily, on="date", how="outer").sort_values("date").reset_index(drop=True)
    for column in merged.columns:
        if column != "date":
            merged[column] = pd.to_numeric(merged[column], errors="coerce").fillna(0.0)
    merged["requested_start"] = _date_text(start)
    merged["requested_start_month"] = start.strftime("%Y-%m")
    merged["requested_end"] = _date_text(s156.REQUESTED_END)
    merged["c9_minus_c4_equity"] = merged["account_equity_c9"] - merged["account_equity_c4"]
    merged["c9_minus_c4_net_pnl"] = merged["net_pnl_c9"] - merged["net_pnl_c4"]
    merged["c9_minus_c4_trade_count"] = merged["trade_count_c9"] - merged["trade_count_c4"]
    merged["c9_minus_c4_slippage"] = merged["slippage_c9"] - merged["slippage_c4"]
    merged["c9_minus_c4_broker10"] = (
        merged["broker10_margin_to_equity_pct_c9"] - merged["broker10_margin_to_equity_pct_c4"]
    )
    if events.empty:
        event_counts = pd.DataFrame(columns=["date", "stop_retry_event_count", "retry_failed_count", "reentered_count"])
    else:
        temp = events.copy()
        temp["date"] = _event_date_series(temp["datetime"])
        event_counts = (
            temp.dropna(subset=["date"])
            .groupby("date", as_index=False)
            .agg(
                stop_retry_event_count=("final_state", "size"),
                retry_failed_count=("retry_failed", "sum"),
                reentered_count=("retry_reentered", "sum"),
            )
        )
    merged = merged.merge(event_counts, on="date", how="left")
    for column in ["stop_retry_event_count", "retry_failed_count", "reentered_count"]:
        merged[column] = pd.to_numeric(merged.get(column, 0), errors="coerce").fillna(0).astype(int)
    merged["is_stop_retry_event_day"] = merged["stop_retry_event_count"].gt(0).astype(int)
    return merged


def _comparison(summary: pd.DataFrame) -> pd.DataFrame:
    c4 = summary[summary["arm"].eq(s156.ARM_C4)].copy()
    c9 = summary[summary["arm"].eq(s156.ARM_C9)].copy()
    merged = c4.merge(c9, on="requested_start_month", suffixes=("_c4", "_c9"))
    rows: list[dict[str, Any]] = []
    for row in merged.itertuples(index=False):
        rows.append(
            {
                "requested_start_month": row.requested_start_month,
                "return_c4": row.total_return_pct_c4,
                "return_c9": row.total_return_pct_c9,
                "c9_minus_c4_return_pp": row.total_return_pct_c9 - row.total_return_pct_c4,
                "dd_c4": row.max_dd_pct_c4,
                "dd_c9": row.max_dd_pct_c9,
                "c9_minus_c4_dd_pp": row.max_dd_pct_c9 - row.max_dd_pct_c4,
                "sharpe_c4": row.sharpe_c4,
                "sharpe_c9": row.sharpe_c9,
                "c9_minus_c4_sharpe": row.sharpe_c9 - row.sharpe_c4,
                "broker10_c4": row.max_broker10_margin_to_equity_pct_c4,
                "broker10_c9": row.max_broker10_margin_to_equity_pct_c9,
                "c9_minus_c4_broker10_pp": (
                    row.max_broker10_margin_to_equity_pct_c9 - row.max_broker10_margin_to_equity_pct_c4
                ),
                "trades_c4": row.total_trade_count_c4,
                "trades_c9": row.total_trade_count_c9,
                "c9_minus_c4_trades": row.total_trade_count_c9 - row.total_trade_count_c4,
                "stop_retry_event_count": row.stop_retry_event_count_c9,
            }
        )
    return pd.DataFrame(rows)


def _event_state_summary(events: pd.DataFrame, daily_delta: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()
    temp = events.copy()
    temp["date"] = _event_date_series(temp["datetime"])
    temp = temp.merge(
        daily_delta[
            [
                "requested_start_month",
                "date",
                "c9_minus_c4_net_pnl",
                "c9_minus_c4_equity",
                "c9_minus_c4_broker10",
            ]
        ],
        on=["requested_start_month", "date"],
        how="left",
    )
    return (
        temp.groupby(["final_state"], as_index=False)
        .agg(
            event_count=("final_state", "size"),
            volume_sum=("volume", "sum"),
            retry_reentered_count=("retry_reentered", "sum"),
            retry_failed_count=("retry_failed", "sum"),
            event_day_net_pnl_delta_sum_proxy=("c9_minus_c4_net_pnl", "sum"),
            event_day_net_pnl_delta_median_proxy=("c9_minus_c4_net_pnl", "median"),
            event_day_equity_delta_median_proxy=("c9_minus_c4_equity", "median"),
            event_day_broker10_delta_median_proxy=("c9_minus_c4_broker10", "median"),
        )
        .sort_values(["event_count", "event_day_net_pnl_delta_sum_proxy"], ascending=[False, False])
        .reset_index(drop=True)
    )


def _product_summary(events: pd.DataFrame, daily_delta: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame()
    temp = events.copy()
    temp["date"] = _event_date_series(temp["datetime"])
    temp = temp.merge(
        daily_delta[
            [
                "requested_start_month",
                "date",
                "c9_minus_c4_net_pnl",
                "c9_minus_c4_equity",
                "c9_minus_c4_broker10",
            ]
        ],
        on=["requested_start_month", "date"],
        how="left",
    )
    grouped = (
        temp.groupby(["product_vt_symbol", "direction", "final_state"], as_index=False)
        .agg(
            event_count=("final_state", "size"),
            volume_sum=("volume", "sum"),
            retry_reentered_count=("retry_reentered", "sum"),
            retry_failed_count=("retry_failed", "sum"),
            event_day_net_pnl_delta_sum_proxy=("c9_minus_c4_net_pnl", "sum"),
            event_day_net_pnl_delta_median_proxy=("c9_minus_c4_net_pnl", "median"),
            event_day_equity_delta_median_proxy=("c9_minus_c4_equity", "median"),
            event_day_broker10_delta_median_proxy=("c9_minus_c4_broker10", "median"),
        )
        .sort_values(["event_count", "event_day_net_pnl_delta_sum_proxy"], ascending=[False, False])
        .reset_index(drop=True)
    )
    return grouped


def _write_report(
    *,
    comparison: pd.DataFrame,
    state_summary: pd.DataFrame,
    product_summary: pd.DataFrame,
    decision: dict[str, Any],
) -> None:
    view_comparison = comparison[
        [
            "requested_start_month",
            "return_c4",
            "return_c9",
            "c9_minus_c4_return_pp",
            "dd_c4",
            "dd_c9",
            "c9_minus_c4_dd_pp",
            "sharpe_c4",
            "sharpe_c9",
            "c9_minus_c4_sharpe",
            "stop_retry_event_count",
        ]
    ].copy()
    lines = [
        "# Stage157 当前重建版 C9 stop/retry 归因",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        f"- 统一资金：`{s156.CAPITAL:,.0f}`。",
        f"- 统一 AI 池：`{s156.OFFICIAL_LIVE_AI_ELIGIBILITY_PATH}`。",
        f"- 起点：从 `{s156.REQUESTED_START.date()}` 起，每年 `1月1日`；请求结束日 `{s156.REQUESTED_END.date()}`。",
        "- 对比：Stage819/C4 broker10 cap vs Stage847/C9 stop/retry。",
        "- 不连接 CTP，不读取账户，不调用订单 API。",
        "",
        "## C9 - C4 起点对比",
        "",
        _md_table(view_comparison, max_rows=80),
        "",
        "## Stop/Retry 状态聚合",
        "",
        _md_table(state_summary, max_rows=20),
        "",
        "## 产品/方向/状态 Top30",
        "",
        _md_table(product_summary, max_rows=30),
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
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print("[stage157] C4/C9 annual stop-retry attribution", flush=True)
    metadata = s156.s901.s513._metadata()
    s156.s901._ensure_c9_minute_bars(metadata)
    starts = s156._build_start_dates()

    summary_rows: list[dict[str, Any]] = []
    daily_delta_frames: list[pd.DataFrame] = []
    event_frames: list[pd.DataFrame] = []
    for idx, start in enumerate(starts, start=1):
        print(f"[stage157] running {idx}/{len(starts)} {start.date()} C4", flush=True)
        c4_combined, c4_frames = s156._run_stage847_profile(
            profile=s156._stage819_c4_profile(metadata, start),
            start=start,
        )
        print(f"[stage157] running {idx}/{len(starts)} {start.date()} C9", flush=True)
        c9_combined, c9_frames = s156._run_stage847_profile(
            profile=s156._stage847_c9_profile(metadata, start),
            start=start,
        )
        c4_summary = s156._summarize(arm=s156.ARM_C4, combined=c4_combined, frames=c4_frames, start=start)
        c9_summary = s156._summarize(arm=s156.ARM_C9, combined=c9_combined, frames=c9_frames, start=start)
        summary_rows.extend([c4_summary, c9_summary])

        events = c9_frames.get("stop_retry_events", pd.DataFrame()).copy()
        if not events.empty:
            events["stage"] = STAGE
            events["model_tag"] = MODEL_TAG
            events["line_id"] = LINE_ID
            events["requested_start"] = _date_text(start)
            events["requested_start_month"] = start.strftime("%Y-%m")
            events["requested_end"] = _date_text(s156.REQUESTED_END)
        event_frames.append(events)
        daily_delta_frames.append(_daily_delta(c4=c4_combined, c9=c9_combined, events=events, start=start))

    summary = pd.DataFrame(summary_rows).sort_values(["requested_start", "arm"]).reset_index(drop=True)
    comparison = _comparison(summary)
    daily_delta = pd.concat(daily_delta_frames, ignore_index=True, sort=False) if daily_delta_frames else pd.DataFrame()
    events_all = (
        pd.concat([frame for frame in event_frames if not frame.empty], ignore_index=True, sort=False)
        if any(not frame.empty for frame in event_frames)
        else pd.DataFrame()
    )
    state_summary = _event_state_summary(events_all, daily_delta)
    product_summary = _product_summary(events_all, daily_delta)

    event_days = daily_delta[daily_delta["is_stop_retry_event_day"].eq(1)].copy()
    non_event_days = daily_delta[daily_delta["is_stop_retry_event_day"].eq(0)].copy()
    total_return_delta = float(comparison["c9_minus_c4_return_pp"].sum()) if not comparison.empty else 0.0
    event_day_net_delta_sum = (
        float(pd.to_numeric(event_days["c9_minus_c4_net_pnl"], errors="coerce").fillna(0.0).sum())
        if not event_days.empty
        else 0.0
    )
    non_event_day_net_delta_sum = (
        float(pd.to_numeric(non_event_days["c9_minus_c4_net_pnl"], errors="coerce").fillna(0.0).sum())
        if not non_event_days.empty
        else 0.0
    )
    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "capital": s156.CAPITAL,
        "ai_pool_path": str(s156.OFFICIAL_LIVE_AI_ELIGIBILITY_PATH),
        "requested_start": s156.REQUESTED_START.date().isoformat(),
        "requested_end": s156.REQUESTED_END.date().isoformat(),
        "sample_count": int(len(starts)),
        "stop_retry_event_count": int(len(events_all)),
        "stop_retry_event_day_count": int(len(event_days)),
        "c9_return_win_vs_c4_count": int((comparison["c9_minus_c4_return_pp"] > 0.0).sum()),
        "c9_dd_win_vs_c4_count": int((comparison["c9_minus_c4_dd_pp"] >= 0.0).sum()),
        "c9_sharpe_win_vs_c4_count": int((comparison["c9_minus_c4_sharpe"] > 0.0).sum()),
        "sum_return_delta_pp_proxy": total_return_delta,
        "event_day_net_pnl_delta_sum_proxy": event_day_net_delta_sum,
        "non_event_day_net_pnl_delta_sum_proxy": non_event_day_net_delta_sum,
        "state_summary": state_summary.to_dict(orient="records") if not state_summary.empty else [],
        "decision": "stage157_c9_stop_retry_attribution_no_new_rule_no_order_api",
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "external_research_judgment": (
            "Skipped external search per operator constraint; this is a local event attribution for existing C9."
        ),
        "overfit_reflection_before": (
            "否。只解释 Stage156 已固定 C9/C4 差异，不改 R 倍数、重试次数、品种或月份。"
        ),
        "continue_value_before": (
            "是。Stage156 显示 C9 是收益增强但非低风险替代，必须先解释 stop/retry 事件贡献和风险来源。"
        ),
        "overfit_reflection_after": (
            "否。本阶段输出只读事件归因，不产生交易过滤条件；不能用单个产品/年份直接写黑名单。"
        ),
        "continue_value_after": (
            "是。下一步应继续追 C9/C4 回撤差的压力窗口和账户层状态，而不是扫 C9 stop/retry 参数。"
        ),
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "comparison": str(COMPARISON_PATH),
            "daily_delta": str(DAILY_DELTA_PATH),
            "stop_retry_events": str(STOP_RETRY_EVENTS_PATH),
            "state_summary": str(STATE_SUMMARY_PATH),
            "product_summary": str(PRODUCT_SUMMARY_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    daily_delta.to_csv(DAILY_DELTA_PATH, index=False, encoding="utf-8-sig")
    events_all.to_csv(STOP_RETRY_EVENTS_PATH, index=False, encoding="utf-8-sig")
    state_summary.to_csv(STATE_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    product_summary.to_csv(PRODUCT_SUMMARY_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(
        comparison=comparison,
        state_summary=state_summary,
        product_summary=product_summary,
        decision=decision,
    )

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    print("comparison")
    print(comparison.to_string(index=False))
    print("state_summary")
    print(state_summary.to_string(index=False))
    print("product_summary")
    print(product_summary.head(30).to_string(index=False))


if __name__ == "__main__":
    main()
