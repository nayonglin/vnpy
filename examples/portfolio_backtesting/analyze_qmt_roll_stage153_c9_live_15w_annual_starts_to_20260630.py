from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import analyze_qmt_roll_stage650_stage526_200k_capital_reality_check as s650
import analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow as s901
from qmt_roll_official_live_config import (
    OFFICIAL_LIVE_AI_ELIGIBILITY_PATH,
    OFFICIAL_LIVE_ALIAS,
    OFFICIAL_LIVE_CAPITAL,
    OFFICIAL_LIVE_PROFILE_NAME,
    OFFICIAL_LIVE_VERSION,
)


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage153"
MODEL_TAG = "stage153_c9_live_15w_annual_starts_to_20260630_v1"
OUTPUT_PREFIX = "qmt_roll_stage153_c9_live_15w_annual_starts_to_20260630"

REQUESTED_START = pd.Timestamp("2018-01-01")
REQUESTED_END = pd.Timestamp("2026-06-30")
START_MONTHS = (1,)

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
STATS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stats_{MODEL_TAG}.csv"
CURVES_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_curves_{MODEL_TAG}.csv"
DECISION_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_decision_{MODEL_TAG}.json"
REPORT_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _json_safe(value: Any) -> Any:
    return s650._json_safe(value)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    return s650._md_table(frame, max_rows=max_rows)


def _date_text(value: Any) -> str:
    return pd.Timestamp(value).date().isoformat()


def _start_month_text(value: pd.Timestamp) -> str:
    return value.strftime("%Y-%m")


def _build_start_dates() -> list[pd.Timestamp]:
    starts: list[pd.Timestamp] = []
    for year in range(REQUESTED_START.year, REQUESTED_END.year + 1):
        for month in START_MONTHS:
            start = pd.Timestamp(year=year, month=month, day=1)
            if REQUESTED_START <= start <= REQUESTED_END:
                starts.append(start)
    return starts


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    values = pd.to_numeric(equity, errors="coerce").ffill()
    peak = values.cummax()
    return (values / peak.replace(0.0, np.nan) - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0) * 100.0


def _safe_sum(frame: pd.DataFrame, column: str) -> float:
    if column not in frame.columns:
        return 0.0
    return float(pd.to_numeric(frame[column], errors="coerce").fillna(0.0).sum())


def _safe_max(frame: pd.DataFrame, column: str) -> float:
    if column not in frame.columns:
        return 0.0
    series = pd.to_numeric(frame[column], errors="coerce").dropna()
    return float(series.max()) if len(series) else 0.0


def _daily_sharpe(nav: pd.Series) -> float:
    returns = pd.to_numeric(nav, errors="coerce").pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    if returns.empty:
        return 0.0
    std = float(returns.std(ddof=1))
    if std <= 0.0 or np.isnan(std):
        return 0.0
    return float(returns.mean() / std * np.sqrt(252.0))


def _nonzero_daily_win_rate_pct(nav: pd.Series) -> float:
    returns = pd.to_numeric(nav, errors="coerce").pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    nonzero = returns[returns.ne(0.0)]
    if nonzero.empty:
        return 0.0
    return float((nonzero > 0.0).mean() * 100.0)


def _summarize_curve(curve: pd.DataFrame, requested_start: pd.Timestamp) -> dict[str, Any]:
    frame = curve.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame = frame.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    if frame.empty:
        raise RuntimeError(f"empty curve for start {requested_start.date().isoformat()}")

    equity = pd.to_numeric(frame["account_equity"], errors="coerce").ffill()
    nav = equity / float(OFFICIAL_LIVE_CAPITAL)
    drawdown = _drawdown_pct(equity)
    end_equity = float(equity.iloc[-1])
    return_pct = (end_equity / float(OFFICIAL_LIVE_CAPITAL) - 1.0) * 100.0
    elapsed_days = max(1, int((frame["date"].iloc[-1] - frame["date"].iloc[0]).days))
    cagr_pct = ((end_equity / float(OFFICIAL_LIVE_CAPITAL)) ** (365.25 / elapsed_days) - 1.0) * 100.0

    return {
        "stage": STAGE,
        "model_tag": MODEL_TAG,
        "line_id": LINE_ID,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "official_live_profile_name": OFFICIAL_LIVE_PROFILE_NAME,
        "ai_pool_path": str(OFFICIAL_LIVE_AI_ELIGIBILITY_PATH),
        "requested_start": _date_text(requested_start),
        "requested_start_month": _start_month_text(requested_start),
        "requested_end": _date_text(REQUESTED_END),
        "actual_start": _date_text(frame["date"].iloc[0]),
        "actual_end": _date_text(frame["date"].iloc[-1]),
        "trading_days": int(len(frame)),
        "calendar_days": int(elapsed_days + 1),
        "account_capital": float(OFFICIAL_LIVE_CAPITAL),
        "end_equity": end_equity,
        "total_return_pct": float(return_pct),
        "cagr_pct": float(cagr_pct),
        "max_dd_pct": float(drawdown.min()) if len(drawdown) else 0.0,
        "min_equity": float(equity.min()) if len(equity) else end_equity,
        "max_equity": float(equity.max()) if len(equity) else end_equity,
        "sharpe": _daily_sharpe(nav),
        "total_slippage": _safe_sum(frame, "slippage"),
        "total_trade_count": _safe_sum(frame, "trade_count"),
        "nonzero_daily_win_rate_pct": _nonzero_daily_win_rate_pct(nav),
        "max_broker10_margin_to_equity_pct": _safe_max(frame, "broker10_margin_to_equity_pct"),
        "final_nav": float(nav.iloc[-1]),
        "min_nav": float(nav.min()) if len(nav) else float(nav.iloc[-1]),
        "max_nav": float(nav.max()) if len(nav) else float(nav.iloc[-1]),
    }


def _stats(summary: pd.DataFrame) -> pd.DataFrame:
    returns = pd.to_numeric(summary["total_return_pct"], errors="coerce")
    dds = pd.to_numeric(summary["max_dd_pct"], errors="coerce")
    sharpes = pd.to_numeric(summary["sharpe"], errors="coerce")
    end_equity = pd.to_numeric(summary["end_equity"], errors="coerce")
    broker10 = pd.to_numeric(summary["max_broker10_margin_to_equity_pct"], errors="coerce")
    min_idx = returns.idxmin()
    max_idx = returns.idxmax()
    worst_dd_idx = dds.idxmin()
    return pd.DataFrame(
        [
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "line_id": LINE_ID,
                "official_live_version": OFFICIAL_LIVE_VERSION,
                "sample_count": int(len(summary)),
                "requested_start": REQUESTED_START.date().isoformat(),
                "requested_end": REQUESTED_END.date().isoformat(),
                "positive_count": int((returns > 0.0).sum()),
                "positive_rate_pct": float((returns > 0.0).mean() * 100.0) if len(summary) else 0.0,
                "min_end_equity": float(end_equity.min()),
                "median_end_equity": float(end_equity.median()),
                "max_end_equity": float(end_equity.max()),
                "min_return_pct": float(returns.min()),
                "median_return_pct": float(returns.median()),
                "max_return_pct": float(returns.max()),
                "min_return_start": str(summary.loc[min_idx, "requested_start_month"]),
                "max_return_start": str(summary.loc[max_idx, "requested_start_month"]),
                "worst_max_dd_pct": float(dds.min()),
                "worst_max_dd_start": str(summary.loc[worst_dd_idx, "requested_start_month"]),
                "median_max_dd_pct": float(dds.median()),
                "min_sharpe": float(sharpes.min()),
                "median_sharpe": float(sharpes.median()),
                "max_sharpe": float(sharpes.max()),
                "peak_broker10_margin_to_equity_pct": float(broker10.max()),
                "median_broker10_margin_to_equity_pct": float(broker10.median()),
                "total_slippage_sum": float(pd.to_numeric(summary["total_slippage"], errors="coerce").fillna(0.0).sum()),
                "total_trade_count_sum": float(
                    pd.to_numeric(summary["total_trade_count"], errors="coerce").fillna(0.0).sum()
                ),
                "median_win_rate_pct": float(
                    pd.to_numeric(summary["nonzero_daily_win_rate_pct"], errors="coerce").median()
                ),
                "dd30_fail_count": int((dds < -30.0).sum()),
                "dd40_fail_count": int((dds < -40.0).sum()),
                "dd50_fail_count": int((dds < -50.0).sum()),
                "broker100_fail_count": int((broker10 > 100.0).sum()),
            }
        ]
    )


def _write_report(summary: pd.DataFrame, stats: pd.DataFrame, decision: dict[str, Any]) -> None:
    view_summary = summary[
        [
            "requested_start_month",
            "actual_start",
            "actual_end",
            "trading_days",
            "end_equity",
            "total_return_pct",
            "cagr_pct",
            "max_dd_pct",
            "sharpe",
            "max_broker10_margin_to_equity_pct",
            "total_trade_count",
            "nonzero_daily_win_rate_pct",
        ]
    ].copy()
    view_stats = stats[
        [
            "sample_count",
            "positive_count",
            "min_return_pct",
            "median_return_pct",
            "max_return_pct",
            "min_return_start",
            "max_return_start",
            "worst_max_dd_pct",
            "worst_max_dd_start",
            "median_sharpe",
            "peak_broker10_margin_to_equity_pct",
        ]
    ].copy()
    lines = [
        "# Stage153 C9当前重建版15万：2018起逐年冷启动到2026-06-30",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        f"- 当前实盘版本：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`。",
        f"- 当前实盘 profile：`{OFFICIAL_LIVE_PROFILE_NAME}`，账户资金 `{OFFICIAL_LIVE_CAPITAL:,.0f}`。",
        f"- AI 池：`{OFFICIAL_LIVE_AI_ELIGIBILITY_PATH}`。",
        f"- 起点：从 `{REQUESTED_START.date()}` 起，每年 `1月1日`。",
        f"- 请求结束日：`{REQUESTED_END.date()}`；实际结束日取回测曲线最后可用交易日。",
        "- 每个起点独立冷启动重跑，不用长曲线事后切片。",
        "- 不连接 CTP，不读取账户，不调用订单 API。",
        "",
        "## 汇总统计",
        "",
        _md_table(view_stats, max_rows=5),
        "",
        "## 起点明细",
        "",
        _md_table(view_summary, max_rows=80),
        "",
        "## 判断",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- 过拟合反思：{decision['overfit_reflection_after']}",
        f"- 继续价值反思：{decision['continue_value_after']}",
        "",
        "## 输出文件",
        "",
    ]
    for key, path in decision["outputs"].items():
        lines.append(f"- {key}: `{path}`")
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(
        f"[stage153] live={OFFICIAL_LIVE_VERSION} starts={REQUESTED_START.date()} "
        f"end={REQUESTED_END.date()}",
        flush=True,
    )
    metadata = s901.s513._metadata()
    starts = _build_start_dates()
    summary_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []

    for idx, start in enumerate(starts, start=1):
        print(f"[stage153] running {idx}/{len(starts)} start={_date_text(start)}", flush=True)
        combined, _frames, _spec = s901._run_live_c9(metadata, start, REQUESTED_END)
        curve = combined.copy()
        curve["stage"] = STAGE
        curve["model_tag"] = MODEL_TAG
        curve["line_id"] = LINE_ID
        curve["official_live_version"] = OFFICIAL_LIVE_VERSION
        curve["official_live_alias"] = OFFICIAL_LIVE_ALIAS
        curve["requested_start"] = _date_text(start)
        curve["requested_start_month"] = _start_month_text(start)
        curve["requested_end"] = _date_text(REQUESTED_END)
        curve["date"] = pd.to_datetime(curve["date"], errors="coerce").dt.normalize()
        curve = curve.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
        curve["nav"] = pd.to_numeric(curve["account_equity"], errors="coerce") / float(OFFICIAL_LIVE_CAPITAL)
        curve["drawdown_pct"] = _drawdown_pct(pd.to_numeric(curve["account_equity"], errors="coerce"))
        curve["days_since_start"] = np.arange(len(curve), dtype=int)
        curve_frames.append(curve)
        summary_rows.append(_summarize_curve(curve, start))

    summary = pd.DataFrame(summary_rows).sort_values("requested_start").reset_index(drop=True)
    curves = pd.concat(curve_frames, ignore_index=True, sort=False) if curve_frames else pd.DataFrame()
    stats = _stats(summary) if not summary.empty else pd.DataFrame()

    actual_end_min = str(summary["actual_end"].min()) if not summary.empty else ""
    actual_end_max = str(summary["actual_end"].max()) if not summary.empty else ""
    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "official_live_profile_name": OFFICIAL_LIVE_PROFILE_NAME,
        "capital": OFFICIAL_LIVE_CAPITAL,
        "ai_pool_path": str(OFFICIAL_LIVE_AI_ELIGIBILITY_PATH),
        "requested_start": REQUESTED_START.date().isoformat(),
        "requested_end": REQUESTED_END.date().isoformat(),
        "actual_end_min": actual_end_min,
        "actual_end_max": actual_end_max,
        "start_schedule": "Jan 1 every year",
        "sample_count": int(len(summary)),
        "stats": stats.to_dict(orient="records") if not stats.empty else [],
        "decision": "stage153_live_c9_15w_annual_starts_to_20260630_measured_no_order_api",
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "external_research_judgment": (
            "Skipped external search per operator constraint; use the existing repository live-wrapper "
            "because C9 has path-dependent sizing, retry, minute-stop, AI-pool, and broker10 state."
        ),
        "overfit_reflection_before": (
            "否。起点间隔、结束日、资金和当前 live override 都由用户请求固定；本次不调任何策略参数。"
        ),
        "continue_value_before": (
            "是。统一结束日的年度冷启动曲线能观察当前重建版在不同实盘启动年份下的路径差异。"
        ),
        "overfit_reflection_after": (
            "否。本次只对固定线上版本做多起点冷启动回放；不得用某个起点的好坏反向调整 AI 池或 C9 参数。"
        ),
        "continue_value_after": (
            "是。结果可作为当前重建版本的路径风险基准；下一步应固定 AI 池与关键派生产物 hash，而不是救参。"
        ),
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "stats": str(STATS_PATH),
            "curves": str(CURVES_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    stats.to_csv(STATS_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(summary, stats, decision)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    if not stats.empty:
        print("stats")
        print(stats.to_string(index=False))
    if not summary.empty:
        print("summary")
        print(
            summary[
                [
                    "requested_start_month",
                    "actual_start",
                    "actual_end",
                    "trading_days",
                    "end_equity",
                    "total_return_pct",
                    "max_dd_pct",
                    "sharpe",
                    "max_broker10_margin_to_equity_pct",
                ]
            ].to_string(index=False)
        )


if __name__ == "__main__":
    main()
