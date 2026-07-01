from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any, Callable

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
    build_official_live_strategy_overrides,
)


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "backtest_outputs"

LINE_ID = "futures_trend_stage819_intraday_rules"
STAGE = "Stage155"
MODEL_TAG = "stage155_c9_live_15w_ai_on_off_annual_starts_v1"
OUTPUT_PREFIX = "qmt_roll_stage155_c9_live_15w_ai_on_off_annual_starts"

REQUESTED_START = pd.Timestamp("2018-01-01")
REQUESTED_END = pd.Timestamp("2026-06-30")
START_MONTHS = (1,)

SUMMARY_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.csv"
STATS_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_stats_{MODEL_TAG}.csv"
COMPARISON_PATH = OUTPUT_DIR / f"{OUTPUT_PREFIX}_comparison_{MODEL_TAG}.csv"
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


def _builder_ai_on() -> dict[str, Any]:
    overrides = dict(build_official_live_strategy_overrides())
    overrides["enable_ai_product_pool_filter"] = True
    overrides["ai_product_pool_eligibility_path"] = str(OFFICIAL_LIVE_AI_ELIGIBILITY_PATH)
    return overrides


def _builder_ai_off() -> dict[str, Any]:
    overrides = dict(build_official_live_strategy_overrides())
    overrides["enable_ai_product_pool_filter"] = False
    overrides["ai_product_pool_eligibility_path"] = ""
    overrides["ai_product_pool_strategy"] = ""
    return overrides


def _summarize_curve(curve: pd.DataFrame, requested_start: pd.Timestamp, variant: str) -> dict[str, Any]:
    frame = curve.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame = frame.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    if frame.empty:
        raise RuntimeError(f"empty curve for {variant} start {requested_start.date().isoformat()}")

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
        "variant": variant,
        "official_live_version": OFFICIAL_LIVE_VERSION,
        "official_live_alias": OFFICIAL_LIVE_ALIAS,
        "official_live_profile_name": OFFICIAL_LIVE_PROFILE_NAME,
        "ai_pool_path": str(OFFICIAL_LIVE_AI_ELIGIBILITY_PATH) if variant == "ai_on" else "",
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
    rows: list[dict[str, Any]] = []
    for variant, part in summary.groupby("variant", sort=True):
        returns = pd.to_numeric(part["total_return_pct"], errors="coerce")
        dds = pd.to_numeric(part["max_dd_pct"], errors="coerce")
        sharpes = pd.to_numeric(part["sharpe"], errors="coerce")
        broker10 = pd.to_numeric(part["max_broker10_margin_to_equity_pct"], errors="coerce")
        end_equity = pd.to_numeric(part["end_equity"], errors="coerce")
        rows.append(
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "line_id": LINE_ID,
                "variant": str(variant),
                "sample_count": int(len(part)),
                "positive_count": int((returns > 0.0).sum()),
                "min_end_equity": float(end_equity.min()),
                "median_end_equity": float(end_equity.median()),
                "max_end_equity": float(end_equity.max()),
                "min_return_pct": float(returns.min()),
                "median_return_pct": float(returns.median()),
                "max_return_pct": float(returns.max()),
                "worst_max_dd_pct": float(dds.min()),
                "median_max_dd_pct": float(dds.median()),
                "min_sharpe": float(sharpes.min()),
                "median_sharpe": float(sharpes.median()),
                "max_sharpe": float(sharpes.max()),
                "peak_broker10_margin_to_equity_pct": float(broker10.max()),
                "total_slippage_sum": float(pd.to_numeric(part["total_slippage"], errors="coerce").fillna(0.0).sum()),
                "total_trade_count_sum": float(
                    pd.to_numeric(part["total_trade_count"], errors="coerce").fillna(0.0).sum()
                ),
                "dd30_fail_count": int((dds < -30.0).sum()),
                "dd40_fail_count": int((dds < -40.0).sum()),
                "dd50_fail_count": int((dds < -50.0).sum()),
                "broker100_fail_count": int((broker10 > 100.0).sum()),
            }
        )
    return pd.DataFrame(rows).sort_values("variant").reset_index(drop=True)


def _comparison(summary: pd.DataFrame) -> pd.DataFrame:
    left = summary[summary["variant"].eq("ai_on")].copy()
    right = summary[summary["variant"].eq("ai_off")].copy()
    merged = left.merge(right, on="requested_start_month", suffixes=("_ai_on", "_ai_off"))
    rows: list[dict[str, Any]] = []
    for row in merged.itertuples(index=False):
        rows.append(
            {
                "requested_start_month": row.requested_start_month,
                "actual_end_ai_on": row.actual_end_ai_on,
                "actual_end_ai_off": row.actual_end_ai_off,
                "end_equity_ai_on": row.end_equity_ai_on,
                "end_equity_ai_off": row.end_equity_ai_off,
                "end_equity_diff_ai_on_minus_off": row.end_equity_ai_on - row.end_equity_ai_off,
                "return_pct_ai_on": row.total_return_pct_ai_on,
                "return_pct_ai_off": row.total_return_pct_ai_off,
                "return_pct_diff_ai_on_minus_off": row.total_return_pct_ai_on - row.total_return_pct_ai_off,
                "max_dd_pct_ai_on": row.max_dd_pct_ai_on,
                "max_dd_pct_ai_off": row.max_dd_pct_ai_off,
                "max_dd_improvement_ai_on_minus_off": row.max_dd_pct_ai_on - row.max_dd_pct_ai_off,
                "sharpe_ai_on": row.sharpe_ai_on,
                "sharpe_ai_off": row.sharpe_ai_off,
                "sharpe_diff_ai_on_minus_off": row.sharpe_ai_on - row.sharpe_ai_off,
                "trade_count_ai_on": row.total_trade_count_ai_on,
                "trade_count_ai_off": row.total_trade_count_ai_off,
                "trade_count_diff_ai_on_minus_off": row.total_trade_count_ai_on - row.total_trade_count_ai_off,
                "broker10_ai_on": row.max_broker10_margin_to_equity_pct_ai_on,
                "broker10_ai_off": row.max_broker10_margin_to_equity_pct_ai_off,
            }
        )
    return pd.DataFrame(rows)


def _write_report(summary: pd.DataFrame, stats: pd.DataFrame, comparison: pd.DataFrame, decision: dict[str, Any]) -> None:
    view_stats = stats[
        [
            "variant",
            "sample_count",
            "positive_count",
            "min_return_pct",
            "median_return_pct",
            "max_return_pct",
            "worst_max_dd_pct",
            "median_max_dd_pct",
            "median_sharpe",
            "peak_broker10_margin_to_equity_pct",
            "total_trade_count_sum",
        ]
    ].copy()
    view_comparison = comparison[
        [
            "requested_start_month",
            "return_pct_ai_on",
            "return_pct_ai_off",
            "return_pct_diff_ai_on_minus_off",
            "max_dd_pct_ai_on",
            "max_dd_pct_ai_off",
            "max_dd_improvement_ai_on_minus_off",
            "sharpe_ai_on",
            "sharpe_ai_off",
            "trade_count_diff_ai_on_minus_off",
        ]
    ].copy()
    lines = [
        "# Stage155 当前重建版 C9 15万 AI ON/OFF 年度起点消融",
        "",
        f"- 生成时间：`{datetime.now().strftime('%Y-%m-%d %H:%M CST')}`",
        f"- line_id：`{LINE_ID}`",
        f"- 当前实盘版本：`{OFFICIAL_LIVE_VERSION}` / `{OFFICIAL_LIVE_ALIAS}`。",
        f"- 当前实盘 profile：`{OFFICIAL_LIVE_PROFILE_NAME}`，账户资金 `{OFFICIAL_LIVE_CAPITAL:,.0f}`。",
        f"- AI ON 池：`{OFFICIAL_LIVE_AI_ELIGIBILITY_PATH}`。",
        "- 唯一变量：`enable_ai_product_pool_filter` 开/关；AI OFF 同时清空 AI eligibility/path/strategy。",
        f"- 起点：从 `{REQUESTED_START.date()}` 起，每年 `1月1日`；请求结束日 `{REQUESTED_END.date()}`。",
        "- 不连接 CTP，不读取账户，不调用订单 API。",
        "",
        "## 分支统计",
        "",
        _md_table(view_stats, max_rows=20),
        "",
        "## AI ON - AI OFF 起点对比",
        "",
        _md_table(view_comparison, max_rows=80),
        "",
        "## 判断",
        "",
        f"- 决策：`{decision['decision']}`",
        f"- AI ON 收益胜出：`{decision['ai_on_return_win_count']}/{decision['paired_count']}`",
        f"- AI ON 回撤胜出：`{decision['ai_on_drawdown_win_count']}/{decision['paired_count']}`",
        f"- AI ON Sharpe 胜出：`{decision['ai_on_sharpe_win_count']}/{decision['paired_count']}`",
        f"- 过拟合反思：{decision['overfit_reflection_after']}",
        f"- 继续价值反思：{decision['continue_value_after']}",
        "",
        "## 输出文件",
        "",
    ]
    for key, path in decision["outputs"].items():
        lines.append(f"- {key}: `{path}`")
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _run_variant(
    *,
    variant: str,
    builder: Callable[[], dict[str, Any]],
    metadata: dict[str, Any],
    starts: list[pd.Timestamp],
) -> tuple[list[dict[str, Any]], list[pd.DataFrame]]:
    original_builder = s901.build_official_live_strategy_overrides
    s901.build_official_live_strategy_overrides = builder
    summary_rows: list[dict[str, Any]] = []
    curve_frames: list[pd.DataFrame] = []
    try:
        for idx, start in enumerate(starts, start=1):
            print(f"[stage155] {variant} running {idx}/{len(starts)} start={_date_text(start)}", flush=True)
            combined, _frames, _spec = s901._run_live_c9(metadata, start, REQUESTED_END)
            curve = combined.copy()
            curve["stage"] = STAGE
            curve["model_tag"] = MODEL_TAG
            curve["line_id"] = LINE_ID
            curve["variant"] = variant
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
            summary_rows.append(_summarize_curve(curve, start, variant))
    finally:
        s901.build_official_live_strategy_overrides = original_builder
    return summary_rows, curve_frames


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(
        f"[stage155] live={OFFICIAL_LIVE_VERSION} starts={REQUESTED_START.date()} "
        f"end={REQUESTED_END.date()} variants=ai_on,ai_off",
        flush=True,
    )
    metadata = s901.s513._metadata()
    starts = _build_start_dates()

    all_summary_rows: list[dict[str, Any]] = []
    all_curve_frames: list[pd.DataFrame] = []
    for variant, builder in [("ai_on", _builder_ai_on), ("ai_off", _builder_ai_off)]:
        summary_rows, curve_frames = _run_variant(
            variant=variant,
            builder=builder,
            metadata=metadata,
            starts=starts,
        )
        all_summary_rows.extend(summary_rows)
        all_curve_frames.extend(curve_frames)

    summary = pd.DataFrame(all_summary_rows).sort_values(["variant", "requested_start"]).reset_index(drop=True)
    curves = pd.concat(all_curve_frames, ignore_index=True, sort=False) if all_curve_frames else pd.DataFrame()
    stats = _stats(summary) if not summary.empty else pd.DataFrame()
    comparison = _comparison(summary) if not summary.empty else pd.DataFrame()

    ai_on_return_win = int((comparison["return_pct_diff_ai_on_minus_off"] > 0.0).sum()) if not comparison.empty else 0
    ai_on_drawdown_win = (
        int((comparison["max_dd_improvement_ai_on_minus_off"] > 0.0).sum()) if not comparison.empty else 0
    )
    ai_on_sharpe_win = int((comparison["sharpe_diff_ai_on_minus_off"] > 0.0).sum()) if not comparison.empty else 0
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
        "paired_count": int(len(comparison)),
        "ai_on_return_win_count": ai_on_return_win,
        "ai_on_drawdown_win_count": ai_on_drawdown_win,
        "ai_on_sharpe_win_count": ai_on_sharpe_win,
        "stats": stats.to_dict(orient="records") if not stats.empty else [],
        "decision": "stage155_current_rebuild_ai_on_off_quality_audit_no_order_api",
        "order_api_called": False,
        "send_order_api_called_count": 0,
        "cancel_order_api_called_count": 0,
        "ctp_connected": False,
        "external_research_judgment": (
            "Skipped external search per operator constraint; this is a local ablation against the current rebuilt "
            "official live C9 profile."
        ),
        "overfit_reflection_before": (
            "否。唯一变量预先固定为 AI 产品池过滤开关，不根据结果选择年份、品种或参数。"
        ),
        "continue_value_before": (
            "是。历史 Stage404/784 都显示 AI 过滤是关键结构，当前重建版需要重新量化 AI 是否仍在过滤低质量机会。"
        ),
        "overfit_reflection_after": (
            "否。本阶段只做开关消融，不提出按结果调整 AI topN、品种或月份的规则。"
        ),
        "continue_value_after": (
            "是。对比结果可决定下一步是优先做 AI 拦截归因，还是转向 C9 账户/持仓层风险尾治理。"
        ),
        "outputs": {
            "summary": str(SUMMARY_PATH),
            "stats": str(STATS_PATH),
            "comparison": str(COMPARISON_PATH),
            "curves": str(CURVES_PATH),
            "decision": str(DECISION_PATH),
            "report": str(REPORT_PATH),
        },
    }

    summary.to_csv(SUMMARY_PATH, index=False, encoding="utf-8-sig")
    stats.to_csv(STATS_PATH, index=False, encoding="utf-8-sig")
    comparison.to_csv(COMPARISON_PATH, index=False, encoding="utf-8-sig")
    curves.to_csv(CURVES_PATH, index=False, encoding="utf-8-sig")
    DECISION_PATH.write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_report(summary, stats, comparison, decision)

    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))
    if not stats.empty:
        print("stats")
        print(stats.to_string(index=False))
    if not comparison.empty:
        print("comparison")
        print(comparison.to_string(index=False))


if __name__ == "__main__":
    main()
