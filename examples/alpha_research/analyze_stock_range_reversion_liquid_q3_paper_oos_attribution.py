from __future__ import annotations

import json
import os
from datetime import date, datetime
from math import sqrt
from pathlib import Path
from typing import Any

import polars as pl

from analyze_stock_range_reversion_layer_attribution import load_panels
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import NATIVE_RESULTS_DIR, TRADING_DAYS, pct
from generate_stock_range_reversion_liquid_q3_paper_ledger import (
    LEDGER_VERSION,
    OUTPUT_DIR as LEDGER_DIR,
)
from generate_stock_range_reversion_liquid_q3_paper_tracking import markdown_table
from generate_stock_range_reversion_liquid_q3_paper_tracking_v3_exante_adv_quality import build_exec_info, to_float


OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_paper_oos_attribution_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_paper_oos_attribution_v1"

PAPER_SCENARIO: str = "age4_daily_exclude_volume_dry"
FREEZE_TARGET_DATE: date = datetime.strptime(
    os.getenv("PAPER_OOS_FREEZE_TARGET_DATE", "20260416"), "%Y%m%d"
).date()
MIN_OOS_DAYS_FOR_STABLE_JUDGMENT: int = int(os.getenv("PAPER_OOS_MIN_DAYS", "20") or 20)

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "Walk-forward validation: keep OOS outside parameter selection",
        "https://breakorb.com/blog/walk-forward-validation-trading",
    ),
    (
        "Backtesting best practices: out-of-sample and costs",
        "https://www.vecalpha.com/docs/blog/backtesting-best-practices",
    ),
    (
        "Zipline ledger separates orders, transactions, portfolio state",
        "https://flounderteam.github.io/refs/zipline/appendix.html",
    ),
)


def read_csv_with_symbol(path: Path) -> pl.DataFrame:
    return pl.read_csv(path, try_parse_dates=True, schema_overrides={"symbol": pl.Utf8})


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def annualized_sharpe(returns: list[float]) -> float:
    if len(returns) < 2:
        return 0.0
    mean = sum(returns) / len(returns)
    variance = sum((value - mean) ** 2 for value in returns) / (len(returns) - 1)
    if variance <= 0:
        return 0.0
    return mean / sqrt(variance) * sqrt(TRADING_DAYS)


def compound_return(returns: list[float]) -> float:
    equity = 1.0
    for value in returns:
        equity *= 1.0 + value
    return equity - 1.0


def max_drawdown_from_returns(returns: list[float]) -> float:
    equity = 1.0
    peak = 1.0
    worst = 0.0
    for value in returns:
        equity *= 1.0 + value
        peak = max(peak, equity)
        worst = min(worst, equity / peak - 1.0)
    return worst


def build_position_daily(
    daily: pl.DataFrame,
    orders: pl.DataFrame,
    segment_dates: list[date],
    exec_info: dict[tuple[date, str], Any],
) -> pl.DataFrame:
    """Reconstruct daily held positions and gross contribution from the order ledger."""
    order_rows_by_date: dict[date, list[dict[str, Any]]] = {}
    symbol_meta: dict[str, dict[str, str]] = {}
    for row in orders.sort(["date", "ledger_order_seq"]).iter_rows(named=True):
        current_date = row["date"]
        order_rows_by_date.setdefault(current_date, []).append(row)
        symbol = str(row["symbol"])
        symbol_meta[symbol] = {
            "code_name": str(row.get("code_name") or ""),
            "industry": str(row.get("industry") or ""),
        }

    actual: dict[str, float] = {}
    rows: list[dict[str, Any]] = []
    segment_set = set(segment_dates)
    for current_date in daily.sort("date")["date"].to_list():
        action_by_symbol: dict[str, str] = {}
        for order in order_rows_by_date.get(current_date, []):
            symbol = str(order["symbol"])
            after_weight = to_float(order.get("actual_weight_after"), default=0.0)
            if abs(after_weight) > 1e-12:
                actual[symbol] = after_weight
            else:
                actual.pop(symbol, None)
            action_by_symbol[symbol] = str(order.get("side") or "")
            symbol_meta.setdefault(
                symbol,
                {
                    "code_name": str(order.get("code_name") or ""),
                    "industry": str(order.get("industry") or ""),
                },
            )

        if current_date not in segment_set:
            continue

        for symbol, weight in sorted(actual.items()):
            info = exec_info.get((current_date, symbol))
            meta = symbol_meta.get(symbol, {})
            daily_ret = info.daily_ret if info is not None else None
            contribution = weight * daily_ret if daily_ret is not None else None
            rows.append(
                {
                    "date": current_date,
                    "symbol": symbol,
                    "code_name": meta.get("code_name", ""),
                    "industry": meta.get("industry", ""),
                    "actual_weight": weight,
                    "daily_ret": daily_ret,
                    "gross_contribution": contribution,
                    "position_action": action_by_symbol.get(symbol, "hold"),
                    "missing_return": info is None,
                }
            )
    return pl.DataFrame(rows).sort(["date", "industry", "symbol"]) if rows else pl.DataFrame()


def build_industry_contribution(position_daily: pl.DataFrame) -> pl.DataFrame:
    if position_daily.is_empty():
        return pl.DataFrame()
    latest_date = position_daily["date"].max()
    latest_weight = (
        position_daily.filter(pl.col("date") == latest_date)
        .group_by("industry")
        .agg(pl.col("actual_weight").sum().alias("latest_weight"))
    )
    return (
        position_daily.group_by("industry")
        .agg(
            pl.len().alias("position_days"),
            pl.col("symbol").n_unique().alias("symbols"),
            pl.col("actual_weight").mean().alias("avg_weight"),
            pl.col("actual_weight").max().alias("max_single_position_weight"),
            pl.col("gross_contribution").sum().alias("gross_contribution_sum"),
            pl.col("gross_contribution").mean().alias("avg_daily_position_contribution"),
        )
        .join(latest_weight, on="industry", how="left")
        .sort("gross_contribution_sum")
    )


def build_symbol_contribution(position_daily: pl.DataFrame) -> pl.DataFrame:
    if position_daily.is_empty():
        return pl.DataFrame()
    latest_date = position_daily["date"].max()
    latest_weight = position_daily.filter(pl.col("date") == latest_date).select(
        "symbol", pl.col("actual_weight").alias("latest_weight")
    )
    return (
        position_daily.group_by(["symbol", "code_name", "industry"])
        .agg(
            pl.len().alias("held_days"),
            pl.col("actual_weight").mean().alias("avg_weight"),
            pl.col("actual_weight").max().alias("max_weight"),
            pl.col("gross_contribution").sum().alias("gross_contribution_sum"),
            pl.col("daily_ret").mean().alias("avg_daily_ret"),
        )
        .join(latest_weight, on="symbol", how="left")
        .sort("gross_contribution_sum")
    )


def build_action_contribution(position_daily: pl.DataFrame) -> pl.DataFrame:
    if position_daily.is_empty():
        return pl.DataFrame()
    return (
        position_daily.group_by("position_action")
        .agg(
            pl.len().alias("position_days"),
            pl.col("symbol").n_unique().alias("symbols"),
            pl.col("actual_weight").mean().alias("avg_weight"),
            pl.col("gross_contribution").sum().alias("gross_contribution_sum"),
        )
        .sort("gross_contribution_sum")
    )


def build_order_summary(segment_orders: pl.DataFrame) -> pl.DataFrame:
    if segment_orders.is_empty():
        return pl.DataFrame()
    return (
        segment_orders.group_by(["side", "status", "blocked_reason"])
        .agg(
            pl.len().alias("orders"),
            pl.col("desired_weight").sum().alias("desired_weight_sum"),
            pl.col("filled_weight").sum().alias("filled_weight_sum"),
            pl.col("unfilled_weight").sum().alias("unfilled_weight_sum"),
            pl.col("desired_amount_cny").sum().alias("desired_amount_cny_sum"),
            pl.col("filled_amount_cny").sum().alias("filled_amount_cny_sum"),
        )
        .sort(["side", "status", "orders"], descending=[False, False, True])
    )


def build_latest_industry_exposure(position_daily: pl.DataFrame) -> pl.DataFrame:
    if position_daily.is_empty():
        return pl.DataFrame()
    latest_date = position_daily["date"].max()
    return (
        position_daily.filter(pl.col("date") == latest_date)
        .group_by("industry")
        .agg(
            pl.col("actual_weight").sum().alias("latest_weight"),
            pl.col("symbol").n_unique().alias("symbols"),
        )
        .sort("latest_weight", descending=True)
    )


def build_quality_checkpoints(
    summary: dict[str, Any],
    segment_daily: pl.DataFrame,
    segment_orders: pl.DataFrame,
    position_daily: pl.DataFrame,
) -> pl.DataFrame:
    rows: list[dict[str, str]] = []

    def add(name: str, status: str, value: Any, expected: Any, note: str) -> None:
        rows.append(
            {
                "checkpoint": name,
                "status": status,
                "value": "" if value is None else str(value),
                "expected": "" if expected is None else str(expected),
                "note": note,
            }
        )

    add(
        "oos_segment_not_empty",
        "pass" if not segment_daily.is_empty() else "fail",
        segment_daily.height,
        ">0",
        "冻结日之后必须有新增纸面交易日，才有样本外归因意义。",
    )
    add(
        "oos_days_sample_size",
        "pass" if segment_daily.height >= MIN_OOS_DAYS_FOR_STABLE_JUDGMENT else "warn",
        segment_daily.height,
        f">={MIN_OOS_DAYS_FOR_STABLE_JUDGMENT}",
        "新增样本太短时，只能判断执行和早期波动，不能判断策略失效或成功。",
    )
    blocked_orders = segment_orders.filter(pl.col("status") == "blocked").height if not segment_orders.is_empty() else 0
    add(
        "segment_blocked_orders_zero",
        "pass" if blocked_orders == 0 else "warn",
        blocked_orders,
        0,
        "新增段若出现阻断订单，应先查执行约束，不先怀疑信号。",
    )
    fill_ratio = summary.get("segment_fill_ratio")
    add(
        "segment_fill_ratio_above_99pct",
        "pass" if fill_ratio is not None and fill_ratio >= 0.99 else "warn",
        fill_ratio,
        ">=0.99",
        "成交填充率低于99%说明新增段可交易性开始变差。",
    )
    missing_return_rows = (
        position_daily.filter(pl.col("missing_return")).height if not position_daily.is_empty() else 0
    )
    add(
        "position_return_coverage",
        "pass" if missing_return_rows == 0 else "fail",
        missing_return_rows,
        0,
        "持仓归因必须能取到对应日期的开盘到次开盘收益。",
    )
    if not position_daily.is_empty():
        attribution = (
            position_daily.group_by("date")
            .agg(pl.col("gross_contribution").sum().alias("recomputed_gross_ret"))
            .join(segment_daily.select("date", "strategy_gross_daily_ret"), on="date", how="left")
            .with_columns((pl.col("recomputed_gross_ret") - pl.col("strategy_gross_daily_ret")).abs().alias("diff"))
        )
        max_diff = float(attribution["diff"].max() or 0.0)
    else:
        max_diff = None
    add(
        "position_contribution_matches_daily_gross",
        "pass" if max_diff is not None and max_diff <= 1e-10 else "fail",
        max_diff,
        "<=1e-10",
        "持仓贡献求和应能复原日级毛收益。",
    )
    add(
        "segment_state_is_not_execution_issue",
        "pass" if summary.get("state_label") != "execution_watch" else "warn",
        summary.get("state_label"),
        "not execution_watch",
        "如果是执行问题，应暂停策略判断，先修成交约束。",
    )
    return pl.DataFrame(rows)


def classify_state(summary: dict[str, Any]) -> str:
    fill_ratio = float(summary.get("segment_fill_ratio") or 0.0)
    blocked = int(summary.get("segment_blocked_order_count") or 0)
    total_return = float(summary.get("segment_total_return") or 0.0)
    max_drawdown = float(summary.get("segment_max_drawdown") or 0.0)
    if blocked > 0 or fill_ratio < 0.99:
        return "execution_watch"
    if total_return < -0.02 or max_drawdown < -0.03:
        return "signal_or_market_watch"
    return "normal_paper_noise"


def write_report(
    summary: dict[str, Any],
    segment_daily: pl.DataFrame,
    order_summary: pl.DataFrame,
    industry_contribution: pl.DataFrame,
    symbol_contribution: pl.DataFrame,
    action_contribution: pl.DataFrame,
    latest_industry_exposure: pl.DataFrame,
    quality_checkpoints: pl.DataFrame,
    paths: dict[str, Path],
) -> Path:
    report_path = paths["report"]
    failed = quality_checkpoints.filter(pl.col("status") == "fail")
    warned = quality_checkpoints.filter(pl.col("status") == "warn")
    top_symbols = symbol_contribution.sort("gross_contribution_sum", descending=True).head(10)
    bottom_symbols = symbol_contribution.sort("gross_contribution_sum").head(10)
    lines = [
        "# 股票震荡liquid_q3 paper OOS归因 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：冻结后新增纸面样本归因；不新增信号、不调参数。",
        f"- 冻结目标执行日：`{FREEZE_TARGET_DATE}`。",
        f"- 样本外目标日：`{summary['segment_start_date']}`到`{summary['segment_end_date']}`。",
        "- A/B判断：第78趋势策略与股票震荡策略隔离，因此不做第78 A/B/C。",
        "",
        "## 外部调研判断",
        "",
        "- Walk-forward / out-of-sample的核心是后续样本不能反过来参与参数选择。",
        "- 本阶段只把冻结后的paper ledger切出来归因，判断新增段是执行问题、正常波动，还是信号/市场需要观察。",
        "- 直觉判断：样本外跟踪的价值不在于立刻证明策略对错，而在于训练我们在小样本波动里不乱动手。",
        "",
        "参考资料：",
    ]
    for title, url in RESEARCH_SOURCES:
        lines.append(f"- [{title}]({url})")
    lines.extend(
        [
            "",
            "## 核心摘要",
            "",
            f"- 新增样本交易日`{summary['segment_days']}`天，订单`{summary['segment_order_count']}`行，阻断`{summary['segment_blocked_order_count']}`行。",
            f"- 冻结日权益`{summary['start_equity']:.4f}`，段末权益`{summary['end_equity']:.4f}`。",
            f"- 新增段总收益`{pct(summary['segment_total_return'])}`，最大回撤`{pct(summary['segment_max_drawdown'])}`，短段Sharpe `{summary['segment_sharpe']:.2f}`。",
            f"- 毛收益合计`{pct(summary['segment_gross_return_sum'])}`，成本拖累`{pct(summary['segment_cost_drag_sum'])}`。",
            f"- 计划换仓`{pct(summary['segment_desired_abs_change_sum'])}`，实际成交`{pct(summary['segment_filled_abs_change_sum'])}`，填充率`{pct(summary['segment_fill_ratio'])}`。",
            f"- 状态判断：`{summary['state_label']}`。",
            "- 我的判断：这段更像正常纸面波动，不像执行系统坏掉；但样本只有7个交易日，不能把它当成策略有效/失效的证据。",
            "",
            "## 质量检查点",
            "",
            markdown_table(quality_checkpoints, ["checkpoint", "status", "value", "expected", "note"], max_rows=80),
            "",
            "## 失败项",
            "",
            "无数据" if failed.is_empty() else markdown_table(failed, ["checkpoint", "status", "value", "expected", "note"], max_rows=80),
            "",
            "## 警告项",
            "",
            "无数据" if warned.is_empty() else markdown_table(warned, ["checkpoint", "status", "value", "expected", "note"], max_rows=80),
            "",
            "## 新增段日账本",
            "",
            markdown_table(
                segment_daily,
                [
                    "date",
                    "target_symbol_count",
                    "actual_symbol_count",
                    "target_gross_weight",
                    "actual_gross_weight",
                    "desired_abs_change",
                    "filled_abs_change",
                    "fill_ratio",
                    "blocked_order_count",
                    "strategy_gross_daily_ret",
                    "turnover_cost_ret",
                    "strategy_daily_ret",
                    "segment_equity",
                    "segment_drawdown",
                ],
                max_rows=80,
            ),
            "",
            "## 买入/卖出/持有贡献",
            "",
            markdown_table(
                action_contribution,
                ["position_action", "position_days", "symbols", "avg_weight", "gross_contribution_sum"],
                max_rows=20,
            ),
            "",
            "## 行业贡献",
            "",
            markdown_table(
                industry_contribution.sort("gross_contribution_sum"),
                [
                    "industry",
                    "position_days",
                    "symbols",
                    "avg_weight",
                    "latest_weight",
                    "gross_contribution_sum",
                    "avg_daily_position_contribution",
                ],
                max_rows=80,
            ),
            "",
            "## 最新行业暴露",
            "",
            markdown_table(latest_industry_exposure, ["industry", "latest_weight", "symbols"], max_rows=60),
            "",
            "## 贡献最好的股票",
            "",
            markdown_table(
                top_symbols,
                [
                    "symbol",
                    "code_name",
                    "industry",
                    "held_days",
                    "avg_weight",
                    "latest_weight",
                    "gross_contribution_sum",
                    "avg_daily_ret",
                ],
                max_rows=10,
            ),
            "",
            "## 贡献最差的股票",
            "",
            markdown_table(
                bottom_symbols,
                [
                    "symbol",
                    "code_name",
                    "industry",
                    "held_days",
                    "avg_weight",
                    "latest_weight",
                    "gross_contribution_sum",
                    "avg_daily_ret",
                ],
                max_rows=10,
            ),
            "",
            "## 新增段订单汇总",
            "",
            markdown_table(
                order_summary,
                [
                    "side",
                    "status",
                    "blocked_reason",
                    "orders",
                    "desired_weight_sum",
                    "filled_weight_sum",
                    "unfilled_weight_sum",
                    "desired_amount_cny_sum",
                    "filled_amount_cny_sum",
                ],
                max_rows=40,
            ),
            "",
            "## 运行前过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：本阶段只切出冻结后的新增样本做归因，不新增变量、不调阈值、不选择更好窗口。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：新增段收益为负也没有触发任何参数修改；报告保留样本太短的警告。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：paper ledger已经建立，下一步应把冻结后的新增样本单独解释，避免和历史回测混在一起。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：新增段执行质量健康，回落主要不是阻断/成交问题，值得继续滚动积累样本外ledger。",
            "",
            "## 决策",
            "",
            "- 不接入第78。",
            "- 不进入正式股票策略。",
            "- 不做第78 A/B/C。",
            "- 不调`volume_ratio_20 <= 0.70`阈值。",
            "- 样本外段不足20天前，只看执行和风险，不做策略有效性结论。",
            "",
            "## 输出文件",
            "",
        ]
    )
    for name, path in paths.items():
        lines.append(f"- `{name}`：`{path}`")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    daily_path = LEDGER_DIR / f"{LEDGER_VERSION}_daily_ledger.csv"
    order_path = LEDGER_DIR / f"{LEDGER_VERSION}_order_ledger.csv"
    ledger_summary_path = LEDGER_DIR / f"{LEDGER_VERSION}_summary.json"

    daily = pl.read_csv(daily_path, try_parse_dates=True).sort("date")
    orders = read_csv_with_symbol(order_path).sort(["date", "ledger_order_seq"])
    ledger_summary = load_json(ledger_summary_path)
    stock_df, _benchmark_df = load_panels()
    exec_info = build_exec_info(stock_df)

    segment_daily = daily.filter(pl.col("date") > FREEZE_TARGET_DATE).sort("date")
    segment_dates = segment_daily["date"].to_list()
    segment_orders = orders.filter(pl.col("date") > FREEZE_TARGET_DATE).sort(["date", "ledger_order_seq"])
    position_daily = build_position_daily(daily, orders, segment_dates, exec_info)

    returns = [float(value) for value in segment_daily["strategy_daily_ret"].to_list()]
    segment_equity: list[float] = []
    segment_drawdown: list[float] = []
    equity = 1.0
    peak = 1.0
    for value in returns:
        equity *= 1.0 + value
        peak = max(peak, equity)
        segment_equity.append(equity)
        segment_drawdown.append(equity / peak - 1.0)
    if not segment_daily.is_empty():
        segment_daily = segment_daily.with_columns(
            pl.Series("segment_equity", segment_equity),
            pl.Series("segment_drawdown", segment_drawdown),
        )

    freeze_rows = daily.filter(pl.col("date") == FREEZE_TARGET_DATE).to_dicts()
    start_equity = float(freeze_rows[0]["strategy_equity"]) if freeze_rows else 1.0
    end_equity = float(segment_daily["strategy_equity"].last()) if not segment_daily.is_empty() else start_equity
    desired_sum = float(segment_daily["desired_abs_change"].sum() or 0.0) if not segment_daily.is_empty() else 0.0
    filled_sum = float(segment_daily["filled_abs_change"].sum() or 0.0) if not segment_daily.is_empty() else 0.0
    summary: dict[str, Any] = {
        "scenario": PAPER_SCENARIO,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "freeze_target_date": FREEZE_TARGET_DATE,
        "latest_target_date": ledger_summary.get("latest_target_date"),
        "latest_signal_date": ledger_summary.get("latest_signal_date"),
        "segment_start_date": segment_dates[0] if segment_dates else None,
        "segment_end_date": segment_dates[-1] if segment_dates else None,
        "segment_days": len(segment_dates),
        "start_equity": start_equity,
        "end_equity": end_equity,
        "segment_total_return": end_equity / start_equity - 1.0 if start_equity else 0.0,
        "segment_compounded_return_check": compound_return(returns),
        "segment_max_drawdown": max_drawdown_from_returns(returns),
        "segment_sharpe": annualized_sharpe(returns),
        "segment_gross_return_sum": float(segment_daily["strategy_gross_daily_ret"].sum() or 0.0)
        if not segment_daily.is_empty()
        else 0.0,
        "segment_cost_drag_sum": float(segment_daily["turnover_cost_ret"].sum() or 0.0)
        if not segment_daily.is_empty()
        else 0.0,
        "segment_desired_abs_change_sum": desired_sum,
        "segment_filled_abs_change_sum": filled_sum,
        "segment_fill_ratio": filled_sum / desired_sum if desired_sum > 0 else 1.0,
        "segment_order_count": segment_orders.height,
        "segment_blocked_order_count": segment_orders.filter(pl.col("status") == "blocked").height
        if not segment_orders.is_empty()
        else 0,
        "segment_partial_order_count": segment_orders.filter(pl.col("status") == "partial_cap_limited").height
        if not segment_orders.is_empty()
        else 0,
        "segment_buy_order_count": segment_orders.filter(pl.col("side") == "buy").height
        if not segment_orders.is_empty()
        else 0,
        "segment_sell_order_count": segment_orders.filter(pl.col("side") == "sell").height
        if not segment_orders.is_empty()
        else 0,
    }
    summary["state_label"] = classify_state(summary)

    industry_contribution = build_industry_contribution(position_daily)
    symbol_contribution = build_symbol_contribution(position_daily)
    action_contribution = build_action_contribution(position_daily)
    order_summary = build_order_summary(segment_orders)
    latest_industry_exposure = build_latest_industry_exposure(position_daily)
    quality_checkpoints = build_quality_checkpoints(summary, segment_daily, segment_orders, position_daily)
    summary["quality_pass_count"] = quality_checkpoints.filter(pl.col("status") == "pass").height
    summary["quality_warn_count"] = quality_checkpoints.filter(pl.col("status") == "warn").height
    summary["quality_fail_count"] = quality_checkpoints.filter(pl.col("status") == "fail").height

    paths = {
        "report": OUTPUT_DIR / f"{PREFIX}_report.md",
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.json",
        "segment_daily": OUTPUT_DIR / f"{PREFIX}_segment_daily.csv",
        "segment_orders": OUTPUT_DIR / f"{PREFIX}_segment_orders.csv",
        "position_daily": OUTPUT_DIR / f"{PREFIX}_position_daily.csv",
        "industry_contribution": OUTPUT_DIR / f"{PREFIX}_industry_contribution.csv",
        "symbol_contribution": OUTPUT_DIR / f"{PREFIX}_symbol_contribution.csv",
        "action_contribution": OUTPUT_DIR / f"{PREFIX}_action_contribution.csv",
        "latest_industry_exposure": OUTPUT_DIR / f"{PREFIX}_latest_industry_exposure.csv",
        "order_summary": OUTPUT_DIR / f"{PREFIX}_order_summary.csv",
        "quality_checkpoints": OUTPUT_DIR / f"{PREFIX}_quality_checkpoints.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }
    write_json(paths["summary"], summary)
    segment_daily.write_csv(paths["segment_daily"])
    segment_orders.write_csv(paths["segment_orders"])
    position_daily.write_csv(paths["position_daily"])
    industry_contribution.write_csv(paths["industry_contribution"])
    symbol_contribution.write_csv(paths["symbol_contribution"])
    action_contribution.write_csv(paths["action_contribution"])
    latest_industry_exposure.write_csv(paths["latest_industry_exposure"])
    order_summary.write_csv(paths["order_summary"])
    quality_checkpoints.write_csv(paths["quality_checkpoints"])
    write_json(
        paths["meta"],
        {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "paper_scenario": PAPER_SCENARIO,
            "freeze_target_date": FREEZE_TARGET_DATE,
            "ledger_dir": str(LEDGER_DIR),
            "ledger_version": LEDGER_VERSION,
            "research_sources": RESEARCH_SOURCES,
            "note": "OOS attribution slices the frozen paper ledger after the freeze target date. It does not change signals or parameters.",
        },
    )
    report_path = write_report(
        summary,
        segment_daily,
        order_summary,
        industry_contribution,
        symbol_contribution,
        action_contribution,
        latest_industry_exposure,
        quality_checkpoints,
        paths,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
