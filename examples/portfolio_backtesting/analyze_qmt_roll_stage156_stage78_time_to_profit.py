from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from qmt_roll_official_stage78_config import (
    OFFICIAL_STAGE78_CAPITAL,
    OFFICIAL_STAGE78_REFERENCE_METRICS,
    OFFICIAL_STAGE78_ROLE,
    OFFICIAL_STAGE78_VERSION,
)


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"

MODEL_TAG: str = "stage156_stage78_time_to_profit_v1"
OUTPUT_PREFIX: str = "qmt_roll_stage156_stage78_time_to_profit"
FORMAL_PREFIX: str = "qmt_roll_official_stage78_defensive_formal"

DAILY_PATH: Path = OUTPUT_DIR / f"{FORMAL_PREFIX}_daily.csv"

BEGIN_DAY_WAIT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_begin_day_wait_{MODEL_TAG}.csv"
CLOSE_DAY_WAIT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_close_day_wait_{MODEL_TAG}.csv"
NEW_HIGH_GAPS_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_new_high_gaps_{MODEL_TAG}.csv"
UNDERWATER_PERIODS_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_underwater_periods_{MODEL_TAG}.csv"
SUMMARY_JSON_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_summary_{MODEL_TAG}.json"
REPORT_PATH: Path = OUTPUT_DIR / f"{OUTPUT_PREFIX}_report_{MODEL_TAG}.md"


def _require(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"missing required artifact: {path}")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or math.isinf(result):
        return default
    return result


def _fmt(value: Any, digits: int = 4) -> str:
    if isinstance(value, (int, np.integer)):
        return f"{int(value):,}"
    numeric = _safe_float(value, default=float("nan"))
    if math.isnan(numeric):
        return str(value)
    if abs(numeric) >= 1000:
        return f"{numeric:,.0f}"
    return f"{numeric:.{digits}f}"


def _to_markdown_table(df: pd.DataFrame, columns: list[str] | None = None, max_rows: int = 20) -> str:
    if df.empty:
        return "_No rows._"
    view = df.copy()
    if columns is not None:
        view = view.loc[:, [column for column in columns if column in view.columns]]
    view = view.head(max_rows).copy()
    for column in view.columns:
        if column.endswith("_date") or column == "date":
            view[column] = pd.to_datetime(view[column], errors="coerce").dt.strftime("%Y-%m-%d")
        elif pd.api.types.is_numeric_dtype(view[column]):
            view[column] = view[column].map(_fmt)
    return "\n".join(
        [
            "| " + " | ".join(view.columns) + " |",
            "| " + " | ".join(["---"] * len(view.columns)) + " |",
            *["| " + " | ".join(map(str, row)) + " |" for row in view.to_numpy()],
        ]
    )


def _read_daily() -> pd.DataFrame:
    _require(DAILY_PATH)
    daily = pd.read_csv(DAILY_PATH, encoding="utf-8-sig")
    daily["date"] = pd.to_datetime(daily["date"], errors="coerce").dt.tz_localize(None).dt.normalize()
    daily["balance"] = pd.to_numeric(daily["balance"], errors="coerce")
    daily["net_pnl"] = pd.to_numeric(daily.get("net_pnl", 0.0), errors="coerce").fillna(0.0)
    daily["ddpercent"] = pd.to_numeric(daily.get("ddpercent", 0.0), errors="coerce").fillna(0.0)
    return daily.dropna(subset=["date", "balance"]).sort_values("date").reset_index(drop=True)


def _build_begin_day_wait(daily: pd.DataFrame) -> pd.DataFrame:
    balances = daily["balance"].to_numpy(float)
    dates = daily["date"]
    rows: list[dict[str, Any]] = []
    end_date = dates.iloc[-1]
    for index in range(len(daily)):
        baseline = OFFICIAL_STAGE78_CAPITAL if index == 0 else balances[index - 1]
        future = np.where(balances[index:] > baseline)[0]
        if len(future):
            profit_index = index + int(future[0])
            profit_date = dates.iloc[profit_index]
            resolved = 1
            trading_days = profit_index - index + 1
            calendar_days = (profit_date - dates.iloc[index]).days
        else:
            profit_date = pd.NaT
            resolved = 0
            trading_days = len(daily) - index
            calendar_days = (end_date - dates.iloc[index]).days
        rows.append(
            {
                "start_date": dates.iloc[index].date().isoformat(),
                "baseline_balance": baseline,
                "profit_date": profit_date.date().isoformat() if not pd.isna(profit_date) else "",
                "trading_days_to_profit": trading_days,
                "calendar_days_to_profit": calendar_days,
                "resolved": resolved,
                "end_date": end_date.date().isoformat(),
            }
        )
    return pd.DataFrame(rows)


def _build_close_day_wait(daily: pd.DataFrame) -> pd.DataFrame:
    balances = daily["balance"].to_numpy(float)
    dates = daily["date"]
    rows: list[dict[str, Any]] = []
    end_date = dates.iloc[-1]
    for index in range(len(daily) - 1):
        baseline = balances[index]
        future = np.where(balances[index + 1 :] > baseline)[0]
        if len(future):
            profit_index = index + 1 + int(future[0])
            profit_date = dates.iloc[profit_index]
            resolved = 1
            trading_days = profit_index - index
            calendar_days = (profit_date - dates.iloc[index]).days
        else:
            profit_date = pd.NaT
            resolved = 0
            trading_days = len(daily) - 1 - index
            calendar_days = (end_date - dates.iloc[index]).days
        rows.append(
            {
                "start_date": dates.iloc[index].date().isoformat(),
                "baseline_balance": baseline,
                "profit_date": profit_date.date().isoformat() if not pd.isna(profit_date) else "",
                "trading_days_to_profit": trading_days,
                "calendar_days_to_profit": calendar_days,
                "resolved": resolved,
                "end_date": end_date.date().isoformat(),
            }
        )
    return pd.DataFrame(rows)


def _build_new_high_gaps(daily: pd.DataFrame) -> pd.DataFrame:
    balances = daily["balance"].to_numpy(float)
    dates = daily["date"]
    peak = -float("inf")
    highs: list[dict[str, Any]] = []
    for index, (date, balance) in enumerate(zip(dates, balances, strict=False)):
        if balance > peak:
            if highs:
                highs[-1]["next_high_date"] = date.date().isoformat()
                highs[-1]["trading_days_to_next_high"] = index - int(highs[-1]["index"])
                highs[-1]["calendar_days_to_next_high"] = (date - pd.Timestamp(highs[-1]["date"])).days
                highs[-1]["resolved"] = 1
            peak = balance
            highs.append(
                {
                    "index": index,
                    "date": date.date().isoformat(),
                    "balance": balance,
                    "next_high_date": "",
                    "trading_days_to_next_high": len(daily) - 1 - index,
                    "calendar_days_to_next_high": (dates.iloc[-1] - date).days,
                    "resolved": 0,
                }
            )
    return pd.DataFrame(highs)


def _build_underwater_periods(daily: pd.DataFrame) -> pd.DataFrame:
    balances = daily["balance"].to_numpy(float)
    dates = daily["date"]
    periods: list[dict[str, Any]] = []
    peak = balances[0]
    peak_date = dates.iloc[0]
    in_drawdown = False
    start_index = 0
    start_date = dates.iloc[0]
    start_peak = peak
    start_peak_date = peak_date

    for index in range(1, len(daily)):
        balance = balances[index]
        date = dates.iloc[index]
        if balance > peak:
            if in_drawdown:
                drawdown_window = daily.loc[start_index:index]
                trough_index = drawdown_window["balance"].idxmin()
                periods.append(
                    {
                        "peak_date": start_peak_date.date().isoformat(),
                        "peak_balance": start_peak,
                        "underwater_start": start_date.date().isoformat(),
                        "recovery_date": date.date().isoformat(),
                        "trading_days_underwater": index - start_index + 1,
                        "calendar_days_underwater": (date - start_date).days,
                        "recovered": 1,
                        "trough_date": daily.loc[trough_index, "date"].date().isoformat(),
                        "trough_balance": float(daily.loc[trough_index, "balance"]),
                        "trough_drawdown_pct": (float(daily.loc[trough_index, "balance"]) / start_peak - 1.0) * 100.0,
                    }
                )
                in_drawdown = False
            peak = balance
            peak_date = date
        elif balance < peak and not in_drawdown:
            in_drawdown = True
            start_index = index
            start_date = date
            start_peak = peak
            start_peak_date = peak_date

    if in_drawdown:
        drawdown_window = daily.loc[start_index:]
        trough_index = drawdown_window["balance"].idxmin()
        periods.append(
            {
                "peak_date": start_peak_date.date().isoformat(),
                "peak_balance": start_peak,
                "underwater_start": start_date.date().isoformat(),
                "recovery_date": "",
                "trading_days_underwater": len(daily) - start_index,
                "calendar_days_underwater": (dates.iloc[-1] - start_date).days,
                "recovered": 0,
                "trough_date": daily.loc[trough_index, "date"].date().isoformat(),
                "trough_balance": float(daily.loc[trough_index, "balance"]),
                "trough_drawdown_pct": (float(daily.loc[trough_index, "balance"]) / start_peak - 1.0) * 100.0,
            }
        )
    return pd.DataFrame(periods)


def _quantiles(frame: pd.DataFrame, column: str) -> dict[str, float]:
    resolved = frame.loc[frame["resolved"] == 1, column].astype(float)
    return {
        "p50": float(resolved.quantile(0.50)),
        "p75": float(resolved.quantile(0.75)),
        "p90": float(resolved.quantile(0.90)),
        "p95": float(resolved.quantile(0.95)),
        "max": float(resolved.max()),
    }


def _threshold_rates(frame: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    total = len(frame)
    for days in [1, 5, 10, 20, 40, 60, 120, 250]:
        resolved_by_days = int(((frame["resolved"] == 1) & (frame["trading_days_to_profit"] <= days)).sum())
        rows.append(
            {
                "threshold_trading_days": days,
                "resolved_count": resolved_by_days,
                "total_start_count": total,
                "resolved_rate_pct": resolved_by_days / total * 100.0 if total else 0.0,
            }
        )
    return rows


def _build_summary(
    daily: pd.DataFrame,
    begin_wait: pd.DataFrame,
    close_wait: pd.DataFrame,
    new_high_gaps: pd.DataFrame,
    underwater_periods: pd.DataFrame,
) -> dict[str, Any]:
    begin_resolved = begin_wait[begin_wait["resolved"] == 1]
    begin_unresolved = begin_wait[begin_wait["resolved"] == 0]
    close_resolved = close_wait[close_wait["resolved"] == 1]
    close_unresolved = close_wait[close_wait["resolved"] == 0]
    longest_begin = begin_resolved.sort_values(
        ["trading_days_to_profit", "calendar_days_to_profit"], ascending=False
    ).iloc[0].to_dict()
    longest_close = close_resolved.sort_values(
        ["trading_days_to_profit", "calendar_days_to_profit"], ascending=False
    ).iloc[0].to_dict()
    longest_recovered_underwater = underwater_periods[underwater_periods["recovered"] == 1].sort_values(
        ["trading_days_underwater", "calendar_days_underwater"], ascending=False
    ).iloc[0].to_dict()
    open_underwater = underwater_periods[underwater_periods["recovered"] == 0].tail(1)
    current_open = open_underwater.iloc[0].to_dict() if not open_underwater.empty else {}
    current_open_high_gap = new_high_gaps[new_high_gaps["resolved"] == 0].tail(1)

    return {
        "model_tag": MODEL_TAG,
        "official_version": OFFICIAL_STAGE78_VERSION,
        "official_role": OFFICIAL_STAGE78_ROLE,
        "is_strategy_change": False,
        "is_backtest": False,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "date_start": daily["date"].iloc[0].date().isoformat(),
        "date_end": daily["date"].iloc[-1].date().isoformat(),
        "reference_metrics": OFFICIAL_STAGE78_REFERENCE_METRICS,
        "official_start_time_to_profit": begin_wait.iloc[0].to_dict(),
        "begin_day": {
            "description": "Assume the user starts before the trading day; baseline is previous balance, or initial capital on the first day.",
            "resolved_count": int(begin_wait["resolved"].sum()),
            "unresolved_count": int((begin_wait["resolved"] == 0).sum()),
            "longest_resolved": longest_begin,
            "oldest_unresolved": begin_unresolved.sort_values("start_date").head(1).to_dict(orient="records"),
            "trading_day_quantiles": _quantiles(begin_wait, "trading_days_to_profit"),
            "threshold_rates": _threshold_rates(begin_wait),
        },
        "close_day": {
            "description": "Assume the user joins after the trading day close; baseline is current close balance.",
            "resolved_count": int(close_wait["resolved"].sum()),
            "unresolved_count": int((close_wait["resolved"] == 0).sum()),
            "longest_resolved": longest_close,
            "oldest_unresolved": close_unresolved.sort_values("start_date").head(1).to_dict(orient="records"),
            "trading_day_quantiles": _quantiles(close_wait, "trading_days_to_profit"),
            "threshold_rates": _threshold_rates(close_wait),
        },
        "new_high_gap": {
            "new_high_count": int(len(new_high_gaps)),
            "longest_resolved": new_high_gaps[new_high_gaps["resolved"] == 1]
            .sort_values(["trading_days_to_next_high", "calendar_days_to_next_high"], ascending=False)
            .head(1)
            .to_dict(orient="records"),
            "current_open": current_open_high_gap.to_dict(orient="records"),
        },
        "underwater": {
            "period_count": int(len(underwater_periods)),
            "open_period_count": int((underwater_periods["recovered"] == 0).sum()),
            "longest_recovered": longest_recovered_underwater,
            "current_open": current_open,
        },
        "judgement": {
            "overfit_before": "否。只统计Stage78冻结正式日权益曲线的等待时间，不修改策略规则。",
            "continue_before": "是。等待盈利时间和创新高等待期直接对应实盘资金与心理承受能力。",
            "overfit_after": "否。统计结果没有反向用于筛日期、改参数或包装收益。",
            "continue_after": "是。下一步应把这个等待时间纳入模拟盘验收标准，而不是期待实盘立刻盈利。",
        },
        "outputs": {
            "begin_day_wait": str(BEGIN_DAY_WAIT_PATH),
            "close_day_wait": str(CLOSE_DAY_WAIT_PATH),
            "new_high_gaps": str(NEW_HIGH_GAPS_PATH),
            "underwater_periods": str(UNDERWATER_PERIODS_PATH),
            "summary": str(SUMMARY_JSON_PATH),
            "report": str(REPORT_PATH),
        },
    }


def _write_report(
    summary: dict[str, Any],
    begin_wait: pd.DataFrame,
    close_wait: pd.DataFrame,
    new_high_gaps: pd.DataFrame,
    underwater_periods: pd.DataFrame,
) -> None:
    reference = OFFICIAL_STAGE78_REFERENCE_METRICS["full_2020_2026"]
    begin_longest = pd.DataFrame([summary["begin_day"]["longest_resolved"]])
    begin_unresolved = pd.DataFrame(summary["begin_day"]["oldest_unresolved"])
    close_longest = pd.DataFrame([summary["close_day"]["longest_resolved"]])
    high_gap = pd.DataFrame(summary["new_high_gap"]["longest_resolved"])
    underwater_longest = pd.DataFrame([summary["underwater"]["longest_recovered"]])
    current_underwater = pd.DataFrame([summary["underwater"]["current_open"]]) if summary["underwater"]["current_open"] else pd.DataFrame()
    threshold_df = pd.DataFrame(summary["begin_day"]["threshold_rates"])
    top_begin = begin_wait[begin_wait["resolved"] == 1].sort_values(
        ["trading_days_to_profit", "calendar_days_to_profit"], ascending=False
    ).head(10)

    lines = [
        "# Stage156 Stage78从开始运行到盈利的最长等待统计",
        "",
        "## 定位",
        "",
        "- 本阶段不是新策略，不修改Stage78正式参数。",
        "- 目标是回答：如果某一天开始跟随78版本，历史上最长多久才首次浮盈，以及权益创新高可能等待多久。",
        "- 该统计只能说明历史路径的资金/心理承受要求，不能证明未来一定盈利。",
        "",
        "## Stage78冻结基准",
        "",
        f"- 版本：`{OFFICIAL_STAGE78_VERSION}`",
        f"- 角色：`{OFFICIAL_STAGE78_ROLE}`",
        (
            f"- 全周期：期末权益 `{reference['end_balance']:,.0f}`，"
            f"总收益 `{reference['total_return_pct']:.4f}%`，"
            f"最大回撤 `{reference['max_dd_percent']:.4f}%`，"
            f"Sharpe `{reference['sharpe_ratio']:.4f}`，"
            f"总滑点 `{reference['total_slippage']:,.0f}`，"
            f"交易 `{reference['total_trade_count']:,.0f}`。"
        ),
        "",
        "## 关键结论",
        "",
        (
            f"- 正式起点 `{summary['official_start_time_to_profit']['start_date']}` 开始，"
            f"首次盈利发生在 `{summary['official_start_time_to_profit']['profit_date']}`，"
            f"等待 `{summary['official_start_time_to_profit']['trading_days_to_profit']}` 个交易日。"
        ),
        (
            f"- 任意交易日前开始跟随的已恢复样本中，最长首次盈利等待为 "
            f"`{summary['begin_day']['longest_resolved']['trading_days_to_profit']}` 个交易日，"
            f"`{summary['begin_day']['longest_resolved']['calendar_days_to_profit']}` 个自然日。"
        ),
        (
            f"- 收盘后按当前净值开始跟随的已恢复样本中，最长首次盈利等待为 "
            f"`{summary['close_day']['longest_resolved']['trading_days_to_profit']}` 个交易日，"
            f"`{summary['close_day']['longest_resolved']['calendar_days_to_profit']}` 个自然日。"
        ),
        (
            f"- 最长已恢复水下期为 `{summary['underwater']['longest_recovered']['trading_days_underwater']}` 个交易日，"
            f"`{summary['underwater']['longest_recovered']['calendar_days_underwater']}` 个自然日。"
        ),
        (
            f"- 截至 `{summary['date_end']}`，当前仍处在从 `{summary['underwater']['current_open'].get('peak_date', '')}` "
            f"开始的未恢复水下期，已持续 `{summary['underwater']['current_open'].get('trading_days_underwater', 0)}` 个交易日。"
        ),
        "",
        "## 最长首次盈利等待样本",
        "",
        _to_markdown_table(
            begin_longest,
            ["start_date", "baseline_balance", "profit_date", "trading_days_to_profit", "calendar_days_to_profit"],
            max_rows=5,
        ),
        "",
        "## 收盘后加入的最长等待样本",
        "",
        _to_markdown_table(
            close_longest,
            ["start_date", "baseline_balance", "profit_date", "trading_days_to_profit", "calendar_days_to_profit"],
            max_rows=5,
        ),
        "",
        "## 未恢复的右侧截尾样本",
        "",
        _to_markdown_table(
            begin_unresolved,
            ["start_date", "baseline_balance", "profit_date", "trading_days_to_profit", "calendar_days_to_profit"],
            max_rows=5,
        ),
        "",
        "## 首次盈利等待分布",
        "",
        _to_markdown_table(threshold_df, ["threshold_trading_days", "resolved_count", "total_start_count", "resolved_rate_pct"], max_rows=20),
        "",
        "## 最长权益创新高等待",
        "",
        _to_markdown_table(
            high_gap,
            ["date", "balance", "next_high_date", "trading_days_to_next_high", "calendar_days_to_next_high"],
            max_rows=5,
        ),
        "",
        "## 最长已恢复水下期",
        "",
        _to_markdown_table(
            underwater_longest,
            [
                "peak_date",
                "peak_balance",
                "underwater_start",
                "recovery_date",
                "trading_days_underwater",
                "calendar_days_underwater",
                "trough_date",
                "trough_balance",
                "trough_drawdown_pct",
            ],
            max_rows=5,
        ),
        "",
        "## 当前未恢复水下期",
        "",
        _to_markdown_table(
            current_underwater,
            [
                "peak_date",
                "peak_balance",
                "underwater_start",
                "recovery_date",
                "trading_days_underwater",
                "calendar_days_underwater",
                "trough_date",
                "trough_balance",
                "trough_drawdown_pct",
            ],
            max_rows=5,
        ),
        "",
        "## 等待时间最长的10个开始日",
        "",
        _to_markdown_table(
            top_begin,
            ["start_date", "baseline_balance", "profit_date", "trading_days_to_profit", "calendar_days_to_profit", "resolved"],
            max_rows=10,
        ),
        "",
        "## 反思",
        "",
        f"- 运行前过拟合反思：{summary['judgement']['overfit_before']}",
        f"- 运行前继续价值反思：{summary['judgement']['continue_before']}",
        f"- 运行后过拟合反思：{summary['judgement']['overfit_after']}",
        f"- 运行后继续价值反思：{summary['judgement']['continue_after']}",
        "",
        "## 我的判断",
        "",
        "- 78版本历史上可以赚钱，但不能承诺实盘从任意一天开始都很快盈利。",
        "- 更真实的预期是：即使策略长期有效，也可能出现半年到一年级别的等待盈利或等待创新高阶段。",
        "- 判断实盘是否真的可盈利，不能靠跑几天或几周；至少要用模拟盘/影子盘验证30、60、120、250个交易日的执行偏差、持仓偏差和资金曲线。",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    daily = _read_daily()
    begin_wait = _build_begin_day_wait(daily)
    close_wait = _build_close_day_wait(daily)
    new_high_gaps = _build_new_high_gaps(daily)
    underwater_periods = _build_underwater_periods(daily)
    summary = _build_summary(daily, begin_wait, close_wait, new_high_gaps, underwater_periods)

    begin_wait.to_csv(BEGIN_DAY_WAIT_PATH, index=False, encoding="utf-8-sig")
    close_wait.to_csv(CLOSE_DAY_WAIT_PATH, index=False, encoding="utf-8-sig")
    new_high_gaps.to_csv(NEW_HIGH_GAPS_PATH, index=False, encoding="utf-8-sig")
    underwater_periods.to_csv(UNDERWATER_PERIODS_PATH, index=False, encoding="utf-8-sig")
    SUMMARY_JSON_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    _write_report(summary, begin_wait, close_wait, new_high_gaps, underwater_periods)

    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    print(f"wrote: {REPORT_PATH}")


if __name__ == "__main__":
    main()
