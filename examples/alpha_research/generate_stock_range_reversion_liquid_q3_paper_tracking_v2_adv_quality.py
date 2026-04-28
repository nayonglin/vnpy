from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from math import sqrt
from pathlib import Path
from typing import Any

import polars as pl

from analyze_stock_range_reversion_layer_attribution import load_panels
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import NATIVE_RESULTS_DIR, TRADING_DAYS, pct
from backtest_stock_range_reversion_liquid_q3_repairability_filter import OUTPUT_DIR as FILTER_OUTPUT_DIR
from backtest_stock_range_reversion_liquid_q3_repairability_filter import PREFIX as FILTER_PREFIX
from generate_stock_range_reversion_liquid_q3_paper_tracking import (
    ACCOUNT_SIZE_CNY,
    LATEST_LOOKBACK_DAYS,
    MAX_PARTICIPATION_ADV20,
    PAPER_SCENARIO,
    ROUNDTRIP_COST_BPS,
    build_signal_audit,
    build_symbol_meta,
    build_target_maps,
    build_target_weights,
    build_tracking_dates,
    markdown_table,
)


OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_paper_tracking_v2_adv_quality_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_paper_tracking_v2_adv_quality"

FALLBACK_MIN_VALID_TURNOVER_DAYS: int = 5

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "ML4Trading data quality validation",
        "https://ml4trading.io/docs/data/tutorials/04_data_quality/",
    ),
    (
        "Backtesting Limitations: Slippage and Liquidity Explained",
        "https://www.luxalgo.com/blog/backtesting-limitations-slippage-and-liquidity-explained/",
    ),
    (
        "WealthLab low-liquidity filter discussion",
        "https://www.wealth-lab.com/Discussion/Low-liquidity-filter-10643",
    ),
)


@dataclass(frozen=True)
class AdvQualityExecInfo:
    code_name: str
    industry: str
    daily_ret: float
    trade_open: float
    trade_close: float
    adv_turnover_for_cap: float | None
    native_adv20_turnover: float | None
    fallback_adv_turnover: float | None
    adv_source: str
    adv_quality_flag: str
    fallback_allowed: bool
    turnover_valid_count_20: int
    tradable_open: bool
    is_suspended: bool
    is_oneword_limit_up: bool
    is_oneword_limit_down: bool
    is_limit_up_close: bool
    is_limit_down_close: bool


def to_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if result != result:
        return default
    return result


def build_exec_info(stock_df: pl.DataFrame) -> dict[tuple[date, str], AdvQualityExecInfo]:
    needed = [
        "datetime",
        "symbol",
        "code_name",
        "trade_open",
        "trade_close",
        "turnover",
        "volume",
        "adv20_turnover",
        "is_suspended",
        "is_oneword_limit_up",
        "is_oneword_limit_down",
        "is_limit_up_close",
        "is_limit_down_close",
    ]
    work = (
        stock_df.select([col for col in needed if col in stock_df.columns])
        .sort(["symbol", "datetime"])
        .with_columns(
            (pl.col("turnover").is_not_null() & (pl.col("turnover") > 0)).alias("has_positive_turnover"),
            pl.col("trade_open").shift(-1).over("symbol").alias("next_trade_open"),
        )
        .with_columns(
            pl.col("has_positive_turnover")
            .cast(pl.Int32)
            .rolling_sum(window_size=20, min_samples=1)
            .over("symbol")
            .alias("turnover_valid_count_20"),
            pl.col("turnover").rolling_mean(window_size=20, min_samples=1).over("symbol").alias(
                "turnover_ma20_min1"
            ),
            pl.col("turnover").rolling_mean(window_size=10, min_samples=1).over("symbol").alias(
                "turnover_ma10_min1"
            ),
            pl.col("turnover").rolling_mean(window_size=5, min_samples=1).over("symbol").alias(
                "turnover_ma5_min1"
            ),
        )
        .with_columns(
            pl.when(
                pl.col("trade_open").is_not_null()
                & (pl.col("trade_open") > 0)
                & pl.col("next_trade_open").is_not_null()
                & (pl.col("next_trade_open") > 0)
            )
            .then(pl.col("next_trade_open") / pl.col("trade_open") - 1)
            .otherwise(None)
            .alias("open_to_next_open_ret")
        )
    )
    info: dict[tuple[date, str], AdvQualityExecInfo] = {}
    for row in work.iter_rows(named=True):
        trade_open = to_float(row.get("trade_open"), default=0.0)
        is_suspended = bool(row.get("is_suspended") or False)
        native_adv = to_float(row.get("adv20_turnover"), default=0.0)
        turnover_count = int(to_float(row.get("turnover_valid_count_20"), default=0.0))
        fallback_adv = first_positive(
            row.get("turnover_ma20_min1"),
            row.get("turnover_ma10_min1"),
            row.get("turnover_ma5_min1"),
        )
        fallback_allowed = native_adv <= 0 and turnover_count >= FALLBACK_MIN_VALID_TURNOVER_DAYS and fallback_adv > 0
        if native_adv > 0:
            adv_for_cap: float | None = native_adv
            adv_source = "native_adv20_turnover"
            adv_quality_flag = "native_ok"
        elif fallback_allowed:
            adv_for_cap = fallback_adv
            adv_source = "fallback_turnover_ma_min1"
            adv_quality_flag = "fallback_partial_history" if turnover_count < 20 else "fallback_full_20d_history"
        else:
            adv_for_cap = None
            adv_source = "missing"
            adv_quality_flag = "missing_or_insufficient_turnover_history"
        info[(row["datetime"], row["symbol"])] = AdvQualityExecInfo(
            code_name=str(row.get("code_name") or ""),
            industry="",
            daily_ret=to_float(row.get("open_to_next_open_ret"), default=0.0),
            trade_open=trade_open,
            trade_close=to_float(row.get("trade_close"), default=0.0),
            adv_turnover_for_cap=adv_for_cap,
            native_adv20_turnover=native_adv if native_adv > 0 else None,
            fallback_adv_turnover=fallback_adv if fallback_adv > 0 else None,
            adv_source=adv_source,
            adv_quality_flag=adv_quality_flag,
            fallback_allowed=fallback_allowed,
            turnover_valid_count_20=turnover_count,
            tradable_open=(trade_open > 0 and not is_suspended),
            is_suspended=is_suspended,
            is_oneword_limit_up=bool(row.get("is_oneword_limit_up") or False),
            is_oneword_limit_down=bool(row.get("is_oneword_limit_down") or False),
            is_limit_up_close=bool(row.get("is_limit_up_close") or False),
            is_limit_down_close=bool(row.get("is_limit_down_close") or False),
        )
    return info


def first_positive(*values: Any) -> float:
    for value in values:
        parsed = to_float(value, default=0.0)
        if parsed > 0:
            return parsed
    return 0.0


def classify_order(side: str, info: AdvQualityExecInfo | None) -> tuple[str, str]:
    if info is None:
        return "blocked", "missing_info"
    if not info.tradable_open:
        return "blocked", "suspended_or_missing_open"
    if side == "buy" and info.is_oneword_limit_up:
        return "blocked", "oneword_limit_up_buy"
    if side == "sell" and info.is_oneword_limit_down:
        return "blocked", "oneword_limit_down_sell"
    return "tradable", ""


def replay_paper_orders(
    target_maps: dict[date, dict[str, dict[str, Any]]],
    dates: list[date],
    exec_info: dict[tuple[date, str], AdvQualityExecInfo],
    symbol_meta: dict[str, dict[str, str]],
) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    actual: dict[str, float] = {}
    order_rows: list[dict[str, Any]] = []
    daily_rows: list[dict[str, Any]] = []
    curve_rows: list[dict[str, Any]] = []
    equity = 1.0
    peak = 1.0
    one_way_cost = ROUNDTRIP_COST_BPS / 2.0 / 10000.0

    for current_date in dates:
        target = target_maps.get(current_date, {})
        symbols = set(actual) | set(target)
        next_actual = dict(actual)
        desired_abs_change = 0.0
        filled_abs_change = 0.0
        buy_weight = 0.0
        sell_weight = 0.0
        blocked_buy_weight = 0.0
        blocked_sell_weight = 0.0
        cap_limited_weight = 0.0
        filled_order_count = 0
        partial_order_count = 0
        blocked_order_count = 0
        buy_order_count = 0
        sell_order_count = 0

        for symbol in sorted(symbols):
            target_row = target.get(symbol, {})
            previous_weight = actual.get(symbol, 0.0)
            target_weight = to_float(target_row.get("target_weight"), default=0.0)
            delta = target_weight - previous_weight
            if abs(delta) <= 1e-12:
                continue
            side = "buy" if delta > 0 else "sell"
            desired_weight = abs(delta)
            desired_abs_change += desired_weight
            if side == "buy":
                buy_order_count += 1
            else:
                sell_order_count += 1

            info = exec_info.get((current_date, symbol))
            meta = symbol_meta.get(symbol, {})
            status, blocked_reason = classify_order(side, info)
            adv_for_cap = info.adv_turnover_for_cap if info else None
            adv20_cap_weight = (
                MAX_PARTICIPATION_ADV20 * adv_for_cap / ACCOUNT_SIZE_CNY
                if adv_for_cap is not None and adv_for_cap > 0
                else None
            )
            fill_weight = desired_weight
            if status == "blocked":
                fill_weight = 0.0
                blocked_order_count += 1
            elif adv20_cap_weight is None:
                status = "blocked"
                blocked_reason = "missing_or_unusable_adv_turnover"
                fill_weight = 0.0
                blocked_order_count += 1
            elif fill_weight > adv20_cap_weight:
                fill_weight = max(0.0, adv20_cap_weight)
                cap_limited_weight += desired_weight - fill_weight
                if fill_weight > 1e-12:
                    status = "partial_cap_limited"
                    partial_order_count += 1
                else:
                    status = "blocked"
                    blocked_reason = "zero_adv20_cap"
                    blocked_order_count += 1

            fill_delta = fill_weight if side == "buy" else -fill_weight
            if fill_weight > 1e-12:
                next_actual[symbol] = previous_weight + fill_delta
                if abs(next_actual[symbol]) <= 1e-12:
                    next_actual.pop(symbol, None)
                filled_abs_change += fill_weight
                filled_order_count += 1
                if side == "buy":
                    buy_weight += fill_weight
                else:
                    sell_weight += fill_weight
            else:
                if side == "buy":
                    blocked_buy_weight += desired_weight
                else:
                    blocked_sell_weight += desired_weight

            unfilled_weight = max(0.0, desired_weight - fill_weight)
            order_rows.append(
                {
                    "date": current_date,
                    "scenario": PAPER_SCENARIO,
                    "symbol": symbol,
                    "code_name": target_row.get("code_name") or (info.code_name if info else "") or meta.get("code_name"),
                    "industry": target_row.get("industry") or (info.industry if info else "") or meta.get("industry"),
                    "side": side,
                    "status": status,
                    "blocked_reason": blocked_reason,
                    "prev_actual_weight": previous_weight,
                    "target_weight": target_weight,
                    "target_weight_delta": delta,
                    "desired_weight": desired_weight,
                    "filled_weight": fill_weight,
                    "unfilled_weight": unfilled_weight,
                    "actual_weight_after": next_actual.get(symbol, 0.0),
                    "desired_amount_cny": desired_weight * ACCOUNT_SIZE_CNY,
                    "filled_amount_cny": fill_weight * ACCOUNT_SIZE_CNY,
                    "unfilled_amount_cny": unfilled_weight * ACCOUNT_SIZE_CNY,
                    "adv_turnover_for_cap": adv_for_cap,
                    "native_adv20_turnover": info.native_adv20_turnover if info else None,
                    "fallback_adv_turnover": info.fallback_adv_turnover if info else None,
                    "adv_source": info.adv_source if info else "missing_info",
                    "adv_quality_flag": info.adv_quality_flag if info else "missing_info",
                    "fallback_allowed": info.fallback_allowed if info else False,
                    "turnover_valid_count_20": info.turnover_valid_count_20 if info else None,
                    "adv20_cap_weight": adv20_cap_weight,
                    "adv20_cap_amount_cny": adv20_cap_weight * ACCOUNT_SIZE_CNY if adv20_cap_weight else None,
                    "trade_open": info.trade_open if info else None,
                    "trade_close": info.trade_close if info else None,
                    "is_suspended": info.is_suspended if info else None,
                    "is_oneword_limit_up": info.is_oneword_limit_up if info else None,
                    "is_oneword_limit_down": info.is_oneword_limit_down if info else None,
                    "is_limit_up_close": info.is_limit_up_close if info else None,
                    "is_limit_down_close": info.is_limit_down_close if info else None,
                    "active_lots": target_row.get("active_lots"),
                    "turnover_rate_f": target_row.get("turnover_rate_f"),
                    "circ_mv": target_row.get("circ_mv"),
                }
            )

        actual = {symbol: weight for symbol, weight in next_actual.items() if abs(weight) > 1e-12}
        gross_ret = 0.0
        missing_return_weight = 0.0
        for symbol, weight in actual.items():
            info = exec_info.get((current_date, symbol))
            if info is None:
                missing_return_weight += abs(weight)
                continue
            gross_ret += weight * info.daily_ret
        cost_ret = filled_abs_change * one_way_cost
        net_ret = gross_ret - cost_ret
        equity *= 1.0 + net_ret
        peak = max(peak, equity)
        drawdown = equity / peak - 1.0
        target_gross = sum(to_float(item.get("target_weight"), default=0.0) for item in target.values())
        actual_gross = sum(actual.values())
        daily_row = {
            "date": current_date,
            "scenario": PAPER_SCENARIO,
            "target_symbol_count": len([weight for weight in target.values() if to_float(weight.get("target_weight")) > 0]),
            "actual_symbol_count": len(actual),
            "target_gross_weight": target_gross,
            "actual_gross_weight": actual_gross,
            "desired_abs_change": desired_abs_change,
            "filled_abs_change": filled_abs_change,
            "unfilled_abs_change": max(0.0, desired_abs_change - filled_abs_change),
            "fill_ratio": filled_abs_change / desired_abs_change if desired_abs_change > 0 else 1.0,
            "buy_weight": buy_weight,
            "sell_weight": sell_weight,
            "blocked_buy_weight": blocked_buy_weight,
            "blocked_sell_weight": blocked_sell_weight,
            "cap_limited_weight": cap_limited_weight,
            "filled_order_count": filled_order_count,
            "partial_order_count": partial_order_count,
            "blocked_order_count": blocked_order_count,
            "buy_order_count": buy_order_count,
            "sell_order_count": sell_order_count,
            "strategy_gross_daily_ret": gross_ret,
            "turnover_cost_ret": cost_ret,
            "strategy_daily_ret": net_ret,
            "strategy_equity": equity,
            "strategy_drawdown": drawdown,
            "missing_return_weight": missing_return_weight,
        }
        daily_rows.append(daily_row)
        curve_rows.append(
            {
                "date": current_date,
                "scenario": PAPER_SCENARIO,
                "strategy_equity": equity,
                "strategy_daily_ret": net_ret,
                "strategy_drawdown": drawdown,
                "actual_gross_weight": actual_gross,
                "filled_abs_change": filled_abs_change,
                "fill_ratio": daily_row["fill_ratio"],
            }
        )

    return (
        pl.DataFrame(order_rows).sort(["date", "status", "side", "symbol"]) if order_rows else pl.DataFrame(),
        pl.DataFrame(daily_rows).sort("date") if daily_rows else pl.DataFrame(),
        pl.DataFrame(curve_rows).sort("date") if curve_rows else pl.DataFrame(),
    )


def build_block_reason_summary(orders: pl.DataFrame) -> pl.DataFrame:
    if orders.is_empty():
        return pl.DataFrame()
    return (
        orders.group_by(["status", "blocked_reason"])
        .agg(
            pl.len().alias("orders"),
            pl.col("desired_weight").sum().alias("desired_weight_sum"),
            pl.col("filled_weight").sum().alias("filled_weight_sum"),
            pl.col("unfilled_weight").sum().alias("unfilled_weight_sum"),
            pl.col("desired_amount_cny").sum().alias("desired_amount_cny_sum"),
            pl.col("filled_amount_cny").sum().alias("filled_amount_cny_sum"),
            pl.col("unfilled_amount_cny").sum().alias("unfilled_amount_cny_sum"),
        )
        .sort(["status", "orders"], descending=[False, True])
    )


def build_adv_quality_summary(orders: pl.DataFrame) -> pl.DataFrame:
    if orders.is_empty():
        return pl.DataFrame()
    return (
        orders.group_by(["adv_source", "adv_quality_flag"])
        .agg(
            pl.len().alias("orders"),
            pl.col("desired_weight").sum().alias("desired_weight_sum"),
            pl.col("filled_weight").sum().alias("filled_weight_sum"),
            pl.col("unfilled_weight").sum().alias("unfilled_weight_sum"),
            pl.col("fallback_allowed").sum().alias("fallback_allowed_orders"),
            pl.col("symbol").n_unique().alias("symbols"),
        )
        .with_columns(
            (pl.col("filled_weight_sum") / pl.col("desired_weight_sum")).alias("filled_weight_ratio"),
            (pl.col("fallback_allowed_orders") / pl.col("orders")).alias("fallback_allowed_order_ratio"),
        )
        .sort("desired_weight_sum", descending=True)
    )


def summarize_tracking(daily: pl.DataFrame, orders: pl.DataFrame) -> dict[str, Any]:
    returns = [float(value) for value in daily.sort("date")["strategy_daily_ret"].to_list()]
    mean = sum(returns) / len(returns) if returns else 0.0
    variance = sum((ret - mean) ** 2 for ret in returns) / (len(returns) - 1) if len(returns) > 1 else 0.0
    std = variance**0.5
    final_equity = float(daily["strategy_equity"][-1]) if daily.height else 1.0
    desired_sum = float(daily["desired_abs_change"].sum()) if daily.height else 0.0
    filled_sum = float(daily["filled_abs_change"].sum()) if daily.height else 0.0
    active = daily.filter((pl.col("actual_gross_weight") > 0) | (pl.col("filled_abs_change") > 0))
    blocked = orders.filter(pl.col("status") == "blocked") if not orders.is_empty() else pl.DataFrame()
    partial = orders.filter(pl.col("status") == "partial_cap_limited") if not orders.is_empty() else pl.DataFrame()
    fallback_orders = orders.filter(pl.col("fallback_allowed")) if not orders.is_empty() else pl.DataFrame()
    latest_date = daily["date"].max() if daily.height else None
    latest_orders = orders.filter(pl.col("date") == latest_date) if latest_date and not orders.is_empty() else pl.DataFrame()
    return {
        "scenario": PAPER_SCENARIO,
        "account_size_cny": ACCOUNT_SIZE_CNY,
        "max_participation_adv20": MAX_PARTICIPATION_ADV20,
        "roundtrip_cost_bps": ROUNDTRIP_COST_BPS,
        "fallback_min_valid_turnover_days": FALLBACK_MIN_VALID_TURNOVER_DAYS,
        "days": daily.height,
        "latest_target_date": latest_date,
        "final_equity": final_equity,
        "total_return": final_equity - 1.0,
        "max_drawdown": float(daily["strategy_drawdown"].min()) if daily.height else 0.0,
        "sharpe": mean / std * sqrt(TRADING_DAYS) if std > 0 else 0.0,
        "cost_drag_sum": float(daily["turnover_cost_ret"].sum()) if daily.height else 0.0,
        "overall_fill_ratio": filled_sum / desired_sum if desired_sum > 0 else 1.0,
        "desired_abs_change_sum": desired_sum,
        "filled_abs_change_sum": filled_sum,
        "active_day_win_rate": float((active["strategy_daily_ret"] > 0).mean() or 0.0) if not active.is_empty() else 0.0,
        "order_count": orders.height if not orders.is_empty() else 0,
        "blocked_order_count": blocked.height if not blocked.is_empty() else 0,
        "partial_order_count": partial.height if not partial.is_empty() else 0,
        "fallback_allowed_order_count": fallback_orders.height if not fallback_orders.is_empty() else 0,
        "fallback_filled_weight_sum": float(fallback_orders["filled_weight"].sum() or 0.0)
        if not fallback_orders.is_empty()
        else 0.0,
        "latest_order_count": latest_orders.height if not latest_orders.is_empty() else 0,
        "latest_blocked_order_count": latest_orders.filter(pl.col("status") == "blocked").height
        if not latest_orders.is_empty()
        else 0,
    }


def write_report(
    summary: dict[str, Any],
    recent_daily: pl.DataFrame,
    latest_orders: pl.DataFrame,
    block_reason_summary: pl.DataFrame,
    adv_quality_summary: pl.DataFrame,
    paths: dict[str, Path],
) -> Path:
    report_path = OUTPUT_DIR / f"{PREFIX}_report.md"
    latest_blocked = latest_orders.filter(pl.col("status") == "blocked") if not latest_orders.is_empty() else pl.DataFrame()
    continue_judgment = "是" if summary["final_equity"] > 1.0 and summary["sharpe"] > 0 else "否"
    continue_reason = (
        "ADV质量前置后填充率恢复，策略候选仍保持正收益和正Sharpe，值得整理候选版本说明。"
        if continue_judgment == "是"
        else "ADV质量前置后仍无法维持正收益或正Sharpe，需要先停下排查执行口径。"
    )
    lines = [
        "# 股票震荡liquid_q3纸面跟踪 v2 ADV质量前置",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：将第251阶段ADV缺失诊断转成预注册数据质量规则；不新增信号、不调参数。",
        f"- 纸面候选：`{PAPER_SCENARIO}`。",
        f"- 最新目标执行日：`{summary['latest_target_date']}`。",
        "- A/B判断：第78趋势策略与股票震荡策略隔离，因此不做第78 A/B/C。",
        "",
        "## 外部调研判断",
        "",
        "- 成交上限应使用平均成交额/成交量，但必须知道该字段来自原生数据还是fallback。",
        "- 数据质量规则要先写成标签，再进入订单模拟；不能为了改善结果在事后补字段。",
        "- 本阶段只修执行数据口径，不改变股票池、信号和成交干枯过滤阈值。",
        "",
        "参考资料：",
    ]
    for title, url in RESEARCH_SOURCES:
        lines.append(f"- [{title}]({url})")
    lines.extend(
        [
            "",
            "## 核心观察",
            "",
            f"- v2期末权益`{summary['final_equity']:.4f}`，总收益`{pct(summary['total_return'])}`，最大回撤`{pct(summary['max_drawdown'])}`，Sharpe `{summary['sharpe']:.2f}`。",
            f"- 整体成交填充率`{pct(summary['overall_fill_ratio'])}`，订单行数`{summary['order_count']}`，阻断订单行数`{summary['blocked_order_count']}`，部分成交订单行数`{summary['partial_order_count']}`。",
            f"- fallback允许订单`{summary['fallback_allowed_order_count']}`行，fallback成交权重`{summary['fallback_filled_weight_sum']:.4f}`。",
            f"- 最新目标执行日订单`{summary['latest_order_count']}`行，其中阻断`{summary['latest_blocked_order_count']}`行。",
            "- 直觉判断：这一步把第251阶段的“诊断可恢复”变成了明确、可审计的数据质量前置规则；它提升的是执行口径可信度，不是信号本身。",
            "",
            "## ADV质量来源",
            "",
            markdown_table(
                adv_quality_summary,
                [
                    "adv_source",
                    "adv_quality_flag",
                    "orders",
                    "symbols",
                    "desired_weight_sum",
                    "filled_weight_sum",
                    "unfilled_weight_sum",
                    "filled_weight_ratio",
                    "fallback_allowed_orders",
                    "fallback_allowed_order_ratio",
                ],
            ),
            "",
            "## 阻断原因",
            "",
            markdown_table(
                block_reason_summary,
                [
                    "status",
                    "blocked_reason",
                    "orders",
                    "desired_weight_sum",
                    "filled_weight_sum",
                    "unfilled_weight_sum",
                    "desired_amount_cny_sum",
                    "filled_amount_cny_sum",
                    "unfilled_amount_cny_sum",
                ],
            ),
            "",
            "## 最近日汇总",
            "",
            markdown_table(
                recent_daily,
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
                    "partial_order_count",
                    "strategy_equity",
                    "strategy_drawdown",
                ],
            ),
            "",
            "## 最新订单阻断",
            "",
            markdown_table(
                latest_blocked.sort(["blocked_reason", "side", "symbol"]) if not latest_blocked.is_empty() else latest_blocked,
                [
                    "date",
                    "symbol",
                    "code_name",
                    "industry",
                    "side",
                    "status",
                    "blocked_reason",
                    "desired_weight",
                    "filled_weight",
                    "adv_source",
                    "adv_quality_flag",
                    "fallback_allowed",
                    "turnover_valid_count_20",
                    "trade_open",
                    "is_suspended",
                ],
            ),
            "",
            "## 运行前过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：本阶段只前置数据质量规则，不新增信号、不调阈值。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：v2只改变ADV字段读取和质量标签，规则来自第251阶段预先审计，没有根据收益曲线挑参数。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：第251阶段显示最大阻断来自可恢复的数据字段缺失，必须修正纸面入口的质量标签。",
            "",
            "## 运行后继续价值反思",
            "",
            f"- 判断：{continue_judgment}。",
            f"- 原因：{continue_reason}",
            "",
            "## 决策",
            "",
            "- 不接入第78。",
            "- 不进入正式股票策略。",
            "- 不做第78 A/B/C。",
            "- 不调`volume_ratio_20 <= 0.70`阈值。",
            "- 下一步整理股票震荡候选版本说明，并保留v1/v2执行口径差异。",
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
    selected_all = pl.read_parquet(FILTER_OUTPUT_DIR / f"{FILTER_PREFIX}_selected_all.parquet")
    stock_df, benchmark_df = load_panels()
    signal_audit = build_signal_audit(selected_all)
    target_weights = build_target_weights(selected_all)
    target_maps = build_target_maps(target_weights)
    dates = build_tracking_dates(target_weights, benchmark_df)
    exec_info = build_exec_info(stock_df)
    symbol_meta = build_symbol_meta(signal_audit)
    orders, daily, curves = replay_paper_orders(target_maps, dates, exec_info, symbol_meta)
    block_reason_summary = build_block_reason_summary(orders)
    adv_quality_summary = build_adv_quality_summary(orders)
    summary = summarize_tracking(daily, orders)
    latest_target_date = summary["latest_target_date"]
    latest_orders = orders.filter(pl.col("date") == latest_target_date) if not orders.is_empty() else pl.DataFrame()
    recent_daily = daily.tail(LATEST_LOOKBACK_DAYS) if not daily.is_empty() else daily
    paths = {
        "paper_orders": OUTPUT_DIR / f"{PREFIX}_paper_orders.csv",
        "daily_summary": OUTPUT_DIR / f"{PREFIX}_daily_summary.csv",
        "curves": OUTPUT_DIR / f"{PREFIX}_curves.csv",
        "block_reason_summary": OUTPUT_DIR / f"{PREFIX}_block_reason_summary.csv",
        "adv_quality_summary": OUTPUT_DIR / f"{PREFIX}_adv_quality_summary.csv",
        "latest_orders": OUTPUT_DIR / f"{PREFIX}_latest_orders.csv",
        "recent_daily": OUTPUT_DIR / f"{PREFIX}_recent_daily.csv",
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.json",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }
    orders.write_csv(paths["paper_orders"])
    daily.write_csv(paths["daily_summary"])
    curves.write_csv(paths["curves"])
    block_reason_summary.write_csv(paths["block_reason_summary"])
    adv_quality_summary.write_csv(paths["adv_quality_summary"])
    latest_orders.write_csv(paths["latest_orders"])
    recent_daily.write_csv(paths["recent_daily"])
    paths["summary"].write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    meta = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "paper_scenario": PAPER_SCENARIO,
        "account_size_cny": ACCOUNT_SIZE_CNY,
        "max_participation_adv20": MAX_PARTICIPATION_ADV20,
        "roundtrip_cost_bps": ROUNDTRIP_COST_BPS,
        "fallback_min_valid_turnover_days": FALLBACK_MIN_VALID_TURNOVER_DAYS,
        "source_filter_output_dir": str(FILTER_OUTPUT_DIR),
        "research_sources": RESEARCH_SOURCES,
        "note": "ADV quality fallback is pre-registered from stage 251 audit; signal and filter rules are unchanged.",
    }
    paths["meta"].write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    report_path = write_report(summary, recent_daily, latest_orders, block_reason_summary, adv_quality_summary, paths)
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
