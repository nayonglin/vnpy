from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import pandas as pd

import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage896_c9_vs_official_halfyear_rolling3y as s896


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage897"
MODEL_TAG = "stage897_c9_janjun_rolling1y_v1"
OUTPUT_PREFIX = "qmt_roll_stage897_c9_janjun_rolling1y"

DATA_START = pd.Timestamp("2018-01-01")
DATA_END = pd.Timestamp("2026-05-29")
REQUESTED_TODAY = pd.Timestamp("2026-06-15")
ROLL_YEARS = 1
START_MONTHS = (1, 6)

C9_ARM = "c9_stage847_stage819_30w"

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
AGG_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_aggregate_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _window_end(start: pd.Timestamp) -> pd.Timestamp:
    return (pd.Timestamp(start) + pd.DateOffset(years=ROLL_YEARS) - pd.Timedelta(days=1)).normalize()


def _month_text(value: pd.Timestamp) -> str:
    return pd.Timestamp(value).strftime("%Y-%m")


def _window_id(start: pd.Timestamp, end: pd.Timestamp, partial: bool) -> str:
    suffix = "_partial_to_latest" if partial else ""
    return f"{_month_text(start).replace('-', '_')}_to_{end.strftime('%Y_%m_%d')}{suffix}"


def _build_windows() -> list[dict[str, Any]]:
    starts: list[pd.Timestamp] = []
    for year in range(DATA_START.year, DATA_END.year + 1):
        for month in START_MONTHS:
            start = pd.Timestamp(year=year, month=month, day=1)
            if DATA_START <= start <= DATA_END:
                starts.append(start)
    windows: list[dict[str, Any]] = []
    for start in starts:
        natural_end = _window_end(start)
        complete = natural_end <= DATA_END
        end = natural_end if complete else DATA_END
        windows.append(
            {
                "window_id": _window_id(start, end, partial=not complete),
                "start": start,
                "end": end,
                "terminal_partial": not complete,
                # Reuse Stage896 C9 runner internals. In Stage897 this flag means complete 1Y.
                "complete_3y": complete,
                "complete_1y": complete,
            }
        )
    return windows


WINDOWS = _build_windows()


def _configure_runner() -> None:
    s896.STAGE = STAGE
    s896.MODEL_TAG = MODEL_TAG
    s896.ROLL_YEARS = ROLL_YEARS
    s896.WINDOW_GROUP = "stage897_c9_janjun_rolling_1y"
    s896.DATA_START = DATA_START
    s896.DATA_END = DATA_END


def _run_c9_windows() -> tuple[pd.DataFrame, pd.DataFrame]:
    _configure_runner()
    metadata = s896.s513._metadata()
    vt_symbols = set(str(item) for item in metadata["vt_symbols"])
    minute_bars = s896._load_stage861_full_minute_bars(vt_symbols)
    s896.s847.s827._GLOBAL_MINUTE_BY_SYMBOL = s896.s825._minute_groups(minute_bars)

    rows: list[dict[str, Any]] = []
    curves: list[pd.DataFrame] = []
    for idx, window in enumerate(WINDOWS, start=1):
        print(f"[stage897] running {idx}/{len(WINDOWS)} C9 {window['window_id']}", flush=True)
        row, curve = s896._run_c9(metadata, window)
        rows.append(row)
        curves.append(curve)

    summary = (
        s896.s772._add_month_fields(pd.DataFrame(rows))
        .sort_values(["window_start", "arm_key"])
        .reset_index(drop=True)
    )
    curve_df = (
        pd.concat(curves, ignore_index=True, sort=False)
        .sort_values(["window_start", "arm_key", "date"])
        .reset_index(drop=True)
    )
    for frame in (summary, curve_df):
        frame["stage"] = STAGE
        frame["model_tag"] = MODEL_TAG
        frame["roll_years"] = ROLL_YEARS
        frame["start_schedule"] = "Jan and Jun"
        frame["complete_1y"] = pd.to_numeric(frame["complete_3y"], errors="coerce").fillna(0).astype(int)
    return summary, curve_df


def _aggregate(summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for scope, scoped in [
        ("complete_1y", summary[summary["complete_1y"].eq(1)]),
        ("all_including_partials", summary),
    ]:
        returns = pd.to_numeric(scoped["rebased_total_return_pct"], errors="coerce")
        dds = pd.to_numeric(scoped["rebased_max_dd_pct"], errors="coerce")
        sharpes = pd.to_numeric(scoped["rebased_sharpe"], errors="coerce")
        broker = pd.to_numeric(scoped["max_broker10_margin_to_rebased_equity_pct"], errors="coerce")
        min_equity = pd.to_numeric(scoped["rebased_min_equity"], errors="coerce")
        rows.append(
            {
                "scope": scope,
                "arm_key": C9_ARM,
                "window_count": int(len(scoped)),
                "positive_count": int((returns > 0.0).sum()),
                "positive_rate_pct": float((returns > 0.0).mean() * 100.0) if len(scoped) else 0.0,
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
                "total_trade_count": int(pd.to_numeric(scoped["total_trade_count"], errors="coerce").fillna(0).sum()),
                "total_slippage": float(pd.to_numeric(scoped["total_slippage"], errors="coerce").fillna(0).sum()),
                "total_stop_retry_event_count": int(
                    pd.to_numeric(scoped.get("stop_retry_event_count", 0), errors="coerce").fillna(0).sum()
                ),
                "total_broker10_cap_event_count": int(
                    pd.to_numeric(scoped.get("broker10_cap_event_count", 0), errors="coerce").fillna(0).sum()
                ),
            }
        )
    return pd.DataFrame(rows)


def _decision(summary: pd.DataFrame, aggregate: pd.DataFrame) -> dict[str, Any]:
    complete = summary[summary["complete_1y"].eq(1)].copy()
    exact = aggregate[aggregate["scope"].eq("complete_1y")].iloc[0].to_dict()
    negative = complete[pd.to_numeric(complete["rebased_total_return_pct"], errors="coerce") <= 0.0].copy()
    if int(exact["positive_count"]) == int(exact["window_count"]) and int(exact["broker100_fail_count"]) == 0:
        label = "stage897_c9_rolling1y_all_positive_no_broker100_watch_risk"
    elif int(exact["positive_count"]) == int(exact["window_count"]):
        label = "stage897_c9_rolling1y_all_positive_but_risk_tail_watch"
    else:
        label = "stage897_c9_rolling1y_has_negative_windows_not_annual_all_positive"
    return {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "data_start": DATA_START.strftime("%Y-%m-%d"),
        "latest_available_backtest_date": DATA_END.strftime("%Y-%m-%d"),
        "requested_today": REQUESTED_TODAY.strftime("%Y-%m-%d"),
        "roll_years": ROLL_YEARS,
        "start_schedule": "Jan and Jun each year",
        "complete_window_count": int(complete.shape[0]),
        "partial_window_count": int((summary["terminal_partial"] == 1).sum()),
        "decision_basis": "complete_1y_windows_only",
        "arm": {
            "arm_key": C9_ARM,
            "version": s896.C9_VERSION,
            "capital": s896.C9_CAPITAL,
        },
        "aggregate": aggregate.to_dict(orient="records"),
        "negative_complete_windows": negative[
            ["window_id", "window_start", "window_end", "rebased_total_return_pct", "rebased_max_dd_pct", "rebased_sharpe"]
        ].to_dict(orient="records"),
        "complete_windows": complete.to_dict(orient="records"),
        "decision": label,
        "strategy_changed": False,
        "official_config_changed": False,
        "ctp_connected": False,
        "order_api_called": False,
        "formal_ab_triggered": False,
        "external_research_judgment": (
            "Rolling-window validation is useful here as a robustness audit; implementation uses the repository's "
            "vn.py portfolio engine because C9 has path-dependent equity, position, retry, and margin state."
        ),
        "overfit_reflection_before": (
            "No: the user fixed the 1-year horizon and Jan/Jun start schedule before execution; no thresholds are tuned."
        ),
        "continue_value_before": (
            "Yes: 1-year windows can directly answer whether C9 has annual cold-start negative periods."
        ),
        "overfit_reflection_after": "",
        "continue_value_after": "",
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "curves": str(CURVES_PATH),
            "aggregate": str(AGG_PATH),
            "report": str(REPORT_PATH),
            "decision": str(DECISION_PATH),
        },
    }


def _write_report(summary: pd.DataFrame, aggregate: pd.DataFrame, decision: dict[str, Any]) -> None:
    view_cols = [
        "window_id",
        "window_start",
        "window_end",
        "complete_1y",
        "terminal_partial",
        "rebased_total_return_pct",
        "rebased_max_dd_pct",
        "rebased_sharpe",
        "max_broker10_margin_to_rebased_equity_pct",
        "total_trade_count",
        "total_slippage",
        "stop_retry_event_count",
        "broker10_cap_event_count",
    ]
    lines = [
        "# Stage897 C9 Jan/Jun 1年滚动测试",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M')}`",
        f"- line_id：`{LINE_ID}`",
        f"- 数据最新可用日期：`{DATA_END.date()}`；用户请求的今天为 `{REQUESTED_TODAY.date()}`，本地尚无之后可回测数据。",
        f"- 起点：每年 `1月1日` 与 `6月1日`，从 `{DATA_START.date()}` 到 `{DATA_END.date()}`。",
        f"- 完整1年窗口：`{decision['complete_window_count']}` 个；不足1年 partial：`{decision['partial_window_count']}` 个。",
        "- 本阶段只跑 C9；正式版 Stage372/20w 在 `2018-01` 起点返回空结果，不能覆盖本次 2018 起点要求。",
        "- 不修改正式配置、不连接 CTP、不调用订单 API。",
        "",
        "## Aggregate",
        "",
        _md_table(aggregate, max_rows=10),
        "",
        "## Windows",
        "",
        _md_table(summary[view_cols], max_rows=30),
        "",
        "## Decision",
        "",
        f"- 决策：`{decision['decision']}`",
        "- 主判断只按完整1年窗口；partial 仅观察最近未满一年路径。",
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
        f"[stage897] C9 windows={len(WINDOWS)} complete_1y={sum(int(w['complete_1y']) for w in WINDOWS)} "
        f"partials={sum(int(w['terminal_partial']) for w in WINDOWS)} data_end={DATA_END.date()}",
        flush=True,
    )
    summary, curves = _run_c9_windows()
    aggregate = _aggregate(summary)
    decision = _decision(summary, aggregate)
    exact = aggregate[aggregate["scope"].eq("complete_1y")].iloc[0].to_dict()
    if int(exact["positive_count"]) == int(exact["window_count"]):
        decision["overfit_reflection_after"] = (
            "No new overfit signal in the annual-positive claim itself: all complete Jan/Jun 1-year windows are positive. "
            "Risk-tail metrics still need separate judgment."
        )
        decision["continue_value_after"] = (
            "Yes: continue with risk-tail diagnostics only, because annual positive windows do not prove broker/margin safety."
        )
    else:
        decision["overfit_reflection_after"] = (
            "Yes for the annual-positive claim: at least one complete window is negative, so the visual conclusion was too broad."
        )
        decision["continue_value_after"] = "Continue only if the negative windows reveal a structural, non-fitted risk-control issue."

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    aggregate.to_csv(AGG_PATH, index=False, encoding="utf-8-sig")
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
                "complete_1y",
                "terminal_partial",
                "rebased_total_return_pct",
                "rebased_max_dd_pct",
                "rebased_sharpe",
                "max_broker10_margin_to_rebased_equity_pct",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
