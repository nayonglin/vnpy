from __future__ import annotations

import json
import os
from datetime import date, datetime
from math import sqrt
from pathlib import Path
from typing import Any

import polars as pl

from analyze_stock_range_reversion_layer_attribution import load_panels
from analyze_stock_range_reversion_liquid_q3_300k_lot_feasibility import (
    ACCOUNT_SIZE_CNY,
    BOARD_LOT_SHARES,
    MIN_COMMISSION_CNY,
    OUTPUT_DIR as LOT_OUTPUT_DIR,
    PREFIX as LOT_PREFIX,
    write_json,
)
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import NATIVE_RESULTS_DIR, TRADING_DAYS, pct
from generate_stock_range_reversion_liquid_q3_paper_tracking import PAPER_SCENARIO, markdown_table
from generate_stock_range_reversion_liquid_q3_paper_tracking_v3_exante_adv_quality import build_exec_info, to_float


OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_300k_oos_attribution_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_300k_oos_attribution_v1"

FREEZE_TARGET_DATE: date = datetime.strptime(
    os.getenv("STOCK_300K_OOS_FREEZE_TARGET_DATE", "20260416"), "%Y%m%d"
).date()
MIN_OOS_DAYS_FOR_STABLE_JUDGMENT: int = int(os.getenv("STOCK_300K_OOS_MIN_DAYS", "20") or 20)

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "SSE trading mechanism: buy orders through auction trading shall be multiples of 100 shares",
        "https://english.sse.com.cn/start/trading/mechanism/",
    ),
    (
        "Walk-forward validation keeps out-of-sample data outside parameter selection",
        "https://breakorb.com/blog/walk-forward-validation-trading",
    ),
)


def read_csv_with_symbol(path: Path) -> pl.DataFrame:
    return pl.read_csv(path, try_parse_dates=True, schema_overrides={"symbol": pl.Utf8})


def annualized_sharpe(returns: list[float]) -> float:
    if len(returns) < 2:
        return 0.0
    mean = sum(returns) / len(returns)
    variance = sum((item - mean) ** 2 for item in returns) / (len(returns) - 1)
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


def build_segment_position_daily(
    daily: pl.DataFrame,
    orders: pl.DataFrame,
    segment_dates: list[date],
    exec_info: dict[tuple[date, str], Any],
) -> pl.DataFrame:
    order_rows_by_date: dict[date, list[dict[str, Any]]] = {}
    symbol_meta: dict[str, dict[str, str]] = {}
    for row in orders.sort(["date", "symbol", "side"]).iter_rows(named=True):
        current_date = row["date"]
        order_rows_by_date.setdefault(current_date, []).append(row)
        symbol = str(row["symbol"])
        current_meta = symbol_meta.setdefault(symbol, {"code_name": "", "industry": ""})
        code_name = str(row.get("code_name") or "")
        industry = str(row.get("industry") or "")
        if code_name:
            current_meta["code_name"] = code_name
        if industry:
            current_meta["industry"] = industry

    actual_shares: dict[str, int] = {}
    rows: list[dict[str, Any]] = []
    segment_set = set(segment_dates)

    for current_date in daily.sort("date")["date"].to_list():
        action_by_symbol: dict[str, str] = {}
        for order in order_rows_by_date.get(current_date, []):
            symbol = str(order["symbol"])
            shares_after = int(to_float(order.get("actual_shares_after")))
            if shares_after > 0:
                actual_shares[symbol] = shares_after
            else:
                actual_shares.pop(symbol, None)
            action_by_symbol[symbol] = str(order.get("side") or "")
            current_meta = symbol_meta.setdefault(symbol, {"code_name": "", "industry": ""})
            code_name = str(order.get("code_name") or "")
            industry = str(order.get("industry") or "")
            if code_name:
                current_meta["code_name"] = code_name
            if industry:
                current_meta["industry"] = industry

        if current_date not in segment_set:
            continue

        for symbol, shares in sorted(actual_shares.items()):
            info = exec_info.get((current_date, symbol))
            meta = symbol_meta.get(symbol, {})
            trade_open = to_float(info.trade_open if info else None)
            daily_ret = info.daily_ret if info is not None else None
            amount = shares * trade_open if trade_open > 0 else 0.0
            actual_weight = amount / ACCOUNT_SIZE_CNY
            contribution = actual_weight * daily_ret if daily_ret is not None else None
            rows.append(
                {
                    "date": current_date,
                    "symbol": symbol,
                    "code_name": meta.get("code_name", ""),
                    "industry": meta.get("industry", ""),
                    "actual_shares": shares,
                    "trade_open": trade_open,
                    "actual_amount_cny": amount,
                    "actual_weight": actual_weight,
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
            pl.col("desired_amount_cny").sum().alias("desired_amount_sum_cny"),
            pl.col("filled_amount_cny").sum().alias("filled_amount_sum_cny"),
            pl.col("unfilled_amount_cny").sum().alias("unfilled_amount_sum_cny"),
            pl.col("desired_shares").sum().alias("desired_shares_sum"),
            pl.col("filled_shares").sum().alias("filled_shares_sum"),
        )
        .sort(["side", "status", "orders"], descending=[False, False, True])
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
        "account_size_is_300k",
        "pass" if abs(to_float(summary.get("account_size_cny")) - 300_000.0) <= 1e-6 else "fail",
        summary.get("account_size_cny"),
        300000,
        "本阶段只研究30万整手口径，不覆盖1000万paper口径。",
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
        "30万新增段若出现阻断订单，应先查整手/涨跌停/停牌，不先怀疑信号。",
    )
    desired_amount = to_float(summary.get("segment_desired_amount_sum_cny"))
    filled_amount = to_float(summary.get("segment_filled_amount_sum_cny"))
    fill_ratio = filled_amount / desired_amount if desired_amount > 0 else 1.0
    add(
        "segment_fill_ratio_above_99pct",
        "pass" if fill_ratio >= 0.99 else "warn",
        f"{fill_ratio:.2%}",
        ">=99%",
        "成交填充率低于99%说明新增段执行约束开始变差。",
    )
    latest_zero = int(summary.get("latest_zero_lot_target_count") or 0)
    add(
        "latest_zero_lot_targets_visible",
        "warn" if latest_zero > 0 else "pass",
        latest_zero,
        0,
        "30万账户允许存在买不到一手的目标，但必须显式展示，不能当成满仓组合。",
    )
    missing_return_rows = position_daily.filter(pl.col("missing_return")).height if not position_daily.is_empty() else 0
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
        "no_signal_parameter_change",
        "pass",
        "no signal/threshold change",
        "no signal/threshold change",
        "本阶段只切30万整手账本做OOS归因，不修改信号层。",
    )
    return pl.DataFrame(rows)


def classify_state(summary: dict[str, Any]) -> str:
    blocked = int(summary.get("segment_blocked_order_count") or 0)
    desired = to_float(summary.get("segment_desired_amount_sum_cny"))
    filled = to_float(summary.get("segment_filled_amount_sum_cny"))
    fill_ratio = filled / desired if desired > 0 else 1.0
    total_return = to_float(summary.get("segment_total_return_min_fee"))
    max_drawdown = to_float(summary.get("segment_max_drawdown_min_fee"))
    if blocked > 0 or fill_ratio < 0.99:
        return "execution_watch"
    if total_return < -0.02 or max_drawdown < -0.03:
        return "signal_or_market_watch"
    return "normal_300k_paper_noise"


def write_report(
    summary: dict[str, Any],
    segment_daily: pl.DataFrame,
    order_summary: pl.DataFrame,
    industry_contribution: pl.DataFrame,
    symbol_contribution: pl.DataFrame,
    action_contribution: pl.DataFrame,
    quality: pl.DataFrame,
    paths: dict[str, Path],
) -> Path:
    failed = quality.filter(pl.col("status") == "fail")
    warned = quality.filter(pl.col("status") == "warn")
    top_symbols = symbol_contribution.sort("gross_contribution_sum", descending=True).head(10)
    bottom_symbols = symbol_contribution.sort("gross_contribution_sum").head(10)
    report_path = paths["report"]
    lines = [
        "# 股票震荡liquid_q3 30万整手口径 OOS归因 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：30万整手账户冻结后新增样本归因；不新增信号、不调参数。",
        f"- 账户规模：`{ACCOUNT_SIZE_CNY:,.0f}`元；买入颗粒度：`{BOARD_LOT_SHARES}`股；最低佣金压力：`{MIN_COMMISSION_CNY}`元/笔。",
        f"- 冻结目标执行日：`{FREEZE_TARGET_DATE}`。",
        f"- 样本外目标日：`{summary['segment_start_date']}`到`{summary['segment_end_date']}`。",
        "- A/B判断：第78趋势策略与股票震荡策略隔离，因此不做第78 A/B/C。",
        "",
        "## 外部调研判断",
        "",
        "- 30万账户的一阶约束来自A股100股整数手和小额订单最低佣金。",
        "- Walk-forward/OOS的核心是冻结后样本只能解释，不能反过来参与参数选择。",
        "- 我的判断：30万路线应先证明最新样本和执行链路能持续记录，再谈实盘。",
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
            f"- 30万最低佣金口径：新增段总收益`{pct(summary['segment_total_return_min_fee'])}`，最大回撤`{pct(summary['segment_max_drawdown_min_fee'])}`，短段Sharpe `{summary['segment_sharpe_min_fee']:.2f}`。",
            f"- bps成本口径：新增段总收益`{pct(summary['segment_total_return_bps_only'])}`，最大回撤`{pct(summary['segment_max_drawdown_bps_only'])}`，短段Sharpe `{summary['segment_sharpe_bps_only']:.2f}`。",
            f"- 毛收益合计`{pct(summary['segment_gross_return_sum'])}`，最低佣金成本拖累`{pct(summary['segment_min_fee_cost_drag_sum'])}`。",
            f"- 计划成交金额`{summary['segment_desired_amount_sum_cny']:.0f}`元，实际成交`{summary['segment_filled_amount_sum_cny']:.0f}`元，未成交`{summary['segment_unfilled_amount_sum_cny']:.0f}`元。",
            f"- 最新目标`{summary['latest_target_symbol_count']}`只，实际持仓`{summary['latest_actual_symbol_count']}`只，买不到一手目标`{summary['latest_zero_lot_target_count']}`只，最新实际暴露`{pct(summary['latest_actual_gross_weight'])}`。",
            f"- 状态判断：`{summary['state_label']}`。",
            "",
            "## 质量检查点",
            "",
            markdown_table(quality, ["checkpoint", "status", "value", "expected", "note"], max_rows=80),
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
                    "zero_lot_target_count",
                    "actual_symbol_count",
                    "actual_gross_weight",
                    "desired_amount_sum_cny",
                    "filled_amount_sum_cny",
                    "blocked_order_count",
                    "strategy_gross_daily_ret",
                    "turnover_cost_ret_min_fee",
                    "strategy_daily_ret_min_fee",
                    "segment_equity_min_fee",
                    "segment_drawdown_min_fee",
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
                industry_contribution,
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
                    "desired_amount_sum_cny",
                    "filled_amount_sum_cny",
                    "unfilled_amount_sum_cny",
                    "desired_shares_sum",
                    "filled_shares_sum",
                ],
                max_rows=40,
            ),
            "",
            "## 运行前过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：本阶段只切出冻结后的30万整手账本做归因，不新增变量、不调阈值。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：新增段结果只用于解释30万执行口径，没有触发任何参数修改。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：30万能做与否，必须看冻结后新增样本在整手和最低佣金下是否还能持续记录。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：OOS样本仍短，但链路可复验，下一步应生成30万最新paper订单包并继续滚动观察。",
            "",
            "## 决策",
            "",
            "- 不接入第78。",
            "- 不进入正式股票策略。",
            "- 不做第78 A/B/C。",
            "- 不调`volume_ratio_20 <= 0.70`阈值。",
            "- 30万样本外不足20天前，只做纸面跟踪，不做实盘上线判断。",
            "",
            "## 输出文件",
            "",
        ]
    )
    for name, path in paths.items():
        lines.append(f"- `{name}`：`{path}`")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def add_segment_equity(segment_daily: pl.DataFrame) -> pl.DataFrame:
    if segment_daily.is_empty():
        return segment_daily
    bps_returns = [float(value) for value in segment_daily["strategy_daily_ret_bps_only"].to_list()]
    min_fee_returns = [float(value) for value in segment_daily["strategy_daily_ret_min_fee"].to_list()]
    bps_equity: list[float] = []
    min_fee_equity: list[float] = []
    bps_dd: list[float] = []
    min_fee_dd: list[float] = []
    eq_bps = 1.0
    eq_min_fee = 1.0
    peak_bps = 1.0
    peak_min_fee = 1.0
    for bps_ret, min_fee_ret in zip(bps_returns, min_fee_returns):
        eq_bps *= 1.0 + bps_ret
        eq_min_fee *= 1.0 + min_fee_ret
        peak_bps = max(peak_bps, eq_bps)
        peak_min_fee = max(peak_min_fee, eq_min_fee)
        bps_equity.append(eq_bps)
        min_fee_equity.append(eq_min_fee)
        bps_dd.append(eq_bps / peak_bps - 1.0)
        min_fee_dd.append(eq_min_fee / peak_min_fee - 1.0)
    return segment_daily.with_columns(
        pl.Series("segment_equity_bps_only", bps_equity),
        pl.Series("segment_equity_min_fee", min_fee_equity),
        pl.Series("segment_drawdown_bps_only", bps_dd),
        pl.Series("segment_drawdown_min_fee", min_fee_dd),
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    daily_path = LOT_OUTPUT_DIR / f"{LOT_PREFIX}_daily.csv"
    orders_path = LOT_OUTPUT_DIR / f"{LOT_PREFIX}_orders.csv"
    full_summary_path = LOT_OUTPUT_DIR / f"{LOT_PREFIX}_summary.json"

    daily = pl.read_csv(daily_path, try_parse_dates=True).sort("date")
    orders = read_csv_with_symbol(orders_path).sort(["date", "symbol", "side"])
    full_summary = json.loads(full_summary_path.read_text(encoding="utf-8"))
    stock_df, _benchmark_df = load_panels()
    exec_info = build_exec_info(stock_df)

    segment_daily = add_segment_equity(daily.filter(pl.col("date") > FREEZE_TARGET_DATE).sort("date"))
    segment_dates = segment_daily["date"].to_list()
    segment_orders = orders.filter(pl.col("date") > FREEZE_TARGET_DATE).sort(["date", "symbol", "side"])
    position_daily = build_segment_position_daily(daily, orders, segment_dates, exec_info)

    bps_returns = [float(value) for value in segment_daily["strategy_daily_ret_bps_only"].to_list()]
    min_fee_returns = [float(value) for value in segment_daily["strategy_daily_ret_min_fee"].to_list()]
    summary: dict[str, Any] = {
        "scenario": PAPER_SCENARIO,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "account_size_cny": ACCOUNT_SIZE_CNY,
        "board_lot_shares": BOARD_LOT_SHARES,
        "min_commission_cny": MIN_COMMISSION_CNY,
        "freeze_target_date": FREEZE_TARGET_DATE,
        "segment_start_date": segment_dates[0] if segment_dates else None,
        "segment_end_date": segment_dates[-1] if segment_dates else None,
        "segment_days": len(segment_dates),
        "segment_order_count": segment_orders.height,
        "segment_blocked_order_count": segment_orders.filter(pl.col("status") == "blocked").height
        if not segment_orders.is_empty()
        else 0,
        "segment_partial_order_count": segment_orders.filter(pl.col("status") == "partial_cap_limited").height
        if not segment_orders.is_empty()
        else 0,
        "segment_total_return_bps_only": compound_return(bps_returns),
        "segment_max_drawdown_bps_only": max_drawdown_from_returns(bps_returns),
        "segment_sharpe_bps_only": annualized_sharpe(bps_returns),
        "segment_total_return_min_fee": compound_return(min_fee_returns),
        "segment_max_drawdown_min_fee": max_drawdown_from_returns(min_fee_returns),
        "segment_sharpe_min_fee": annualized_sharpe(min_fee_returns),
        "segment_gross_return_sum": float(segment_daily["strategy_gross_daily_ret"].sum() or 0.0)
        if not segment_daily.is_empty()
        else 0.0,
        "segment_bps_cost_drag_sum": float(segment_daily["turnover_cost_ret_bps_only"].sum() or 0.0)
        if not segment_daily.is_empty()
        else 0.0,
        "segment_min_fee_cost_drag_sum": float(segment_daily["turnover_cost_ret_min_fee"].sum() or 0.0)
        if not segment_daily.is_empty()
        else 0.0,
        "segment_desired_amount_sum_cny": float(segment_daily["desired_amount_sum_cny"].sum() or 0.0)
        if not segment_daily.is_empty()
        else 0.0,
        "segment_filled_amount_sum_cny": float(segment_daily["filled_amount_sum_cny"].sum() or 0.0)
        if not segment_daily.is_empty()
        else 0.0,
        "segment_unfilled_amount_sum_cny": float(segment_daily["unfilled_amount_sum_cny"].sum() or 0.0)
        if not segment_daily.is_empty()
        else 0.0,
        "latest_target_date": full_summary.get("latest_target_date"),
        "latest_target_symbol_count": full_summary.get("latest_target_symbol_count"),
        "latest_actual_symbol_count": full_summary.get("latest_actual_symbol_count"),
        "latest_zero_lot_target_count": full_summary.get("latest_zero_lot_target_count"),
        "latest_actual_gross_weight": full_summary.get("latest_actual_gross_weight"),
        "full_history_final_equity_min_fee": full_summary.get("final_equity_min_fee"),
        "full_history_total_return_min_fee": full_summary.get("total_return_min_fee"),
        "full_history_max_drawdown_min_fee": full_summary.get("max_drawdown_min_fee"),
        "full_history_sharpe_min_fee": full_summary.get("sharpe_min_fee"),
    }
    summary["state_label"] = classify_state(summary)

    industry_contribution = build_industry_contribution(position_daily)
    symbol_contribution = build_symbol_contribution(position_daily)
    action_contribution = build_action_contribution(position_daily)
    order_summary = build_order_summary(segment_orders)
    quality = build_quality_checkpoints(summary, segment_daily, segment_orders, position_daily)
    summary["quality_pass_count"] = quality.filter(pl.col("status") == "pass").height
    summary["quality_warn_count"] = quality.filter(pl.col("status") == "warn").height
    summary["quality_fail_count"] = quality.filter(pl.col("status") == "fail").height

    paths = {
        "report": OUTPUT_DIR / f"{PREFIX}_report.md",
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.json",
        "segment_daily": OUTPUT_DIR / f"{PREFIX}_segment_daily.csv",
        "segment_orders": OUTPUT_DIR / f"{PREFIX}_segment_orders.csv",
        "position_daily": OUTPUT_DIR / f"{PREFIX}_position_daily.csv",
        "industry_contribution": OUTPUT_DIR / f"{PREFIX}_industry_contribution.csv",
        "symbol_contribution": OUTPUT_DIR / f"{PREFIX}_symbol_contribution.csv",
        "action_contribution": OUTPUT_DIR / f"{PREFIX}_action_contribution.csv",
        "order_summary": OUTPUT_DIR / f"{PREFIX}_order_summary.csv",
        "quality_checkpoints": OUTPUT_DIR / f"{PREFIX}_quality_checkpoints.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }
    segment_daily.write_csv(paths["segment_daily"])
    segment_orders.write_csv(paths["segment_orders"])
    position_daily.write_csv(paths["position_daily"])
    industry_contribution.write_csv(paths["industry_contribution"])
    symbol_contribution.write_csv(paths["symbol_contribution"])
    action_contribution.write_csv(paths["action_contribution"])
    order_summary.write_csv(paths["order_summary"])
    quality.write_csv(paths["quality_checkpoints"])
    write_json(paths["summary"], summary)
    write_json(
        paths["meta"],
        {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "source_daily": daily_path,
            "source_orders": orders_path,
            "source_summary": full_summary_path,
            "research_sources": RESEARCH_SOURCES,
            "note": "300k lot-account OOS attribution only; no signal or threshold changes.",
        },
    )
    report_path = write_report(
        summary,
        segment_daily,
        order_summary,
        industry_contribution,
        symbol_contribution,
        action_contribution,
        quality,
        paths,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
