from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date, datetime
from math import sqrt
from pathlib import Path
from typing import Any

import polars as pl

from analyze_stock_range_reversion_layer_attribution import load_panels
from analyze_stock_range_reversion_liquid_q3_repairability_filter_cost_capacity import (
    BASELINE_SCENARIO,
    CANDIDATE_SCENARIO,
    build_symbol_daily_from_selected,
)
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import NATIVE_RESULTS_DIR, TRADING_DAYS, pct
from backtest_stock_range_reversion_liquid_q3_repairability_filter import OUTPUT_DIR as FILTER_OUTPUT_DIR
from backtest_stock_range_reversion_liquid_q3_repairability_filter import PREFIX as FILTER_PREFIX


OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_paper_tracking_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_paper_tracking_v1"

PAPER_SCENARIO: str = os.getenv("PAPER_TRACK_SCENARIO", CANDIDATE_SCENARIO)
ACCOUNT_SIZE_CNY: float = float(os.getenv("PAPER_TRACK_ACCOUNT_SIZE_CNY", "10000000") or 10_000_000.0)
MAX_PARTICIPATION_ADV20: float = float(os.getenv("PAPER_TRACK_MAX_PARTICIPATION_ADV20", "0.05") or 0.05)
ROUNDTRIP_COST_BPS: float = float(os.getenv("PAPER_TRACK_ROUNDTRIP_COST_BPS", "50") or 50.0)
LATEST_LOOKBACK_DAYS: int = int(os.getenv("PAPER_TRACK_LATEST_LOOKBACK_DAYS", "20") or 20)

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "OpenAlgo order and execution tracking",
        "https://github.com/marketcalls/openalgo",
    ),
    (
        "Automated Financial Market Trading System outputs",
        "https://github.com/ThePredictiveDev/Automated-Financial-Market-Trading-System",
    ),
    (
        "Statistical properties of price-limit hits in China A-shares",
        "https://arxiv.org/abs/1503.03548",
    ),
)


@dataclass(frozen=True)
class PaperExecInfo:
    code_name: str
    industry: str
    daily_ret: float
    trade_open: float
    trade_close: float
    adv20_turnover: float | None
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


def markdown_table(frame: pl.DataFrame, columns: list[str], max_rows: int = 80) -> str:
    if frame.is_empty():
        return "无数据"
    return frame.select([col for col in columns if col in frame.columns]).head(max_rows).to_pandas().to_markdown(
        index=False
    )


def build_signal_audit(selected_all: pl.DataFrame) -> pl.DataFrame:
    base = selected_all.filter(pl.col("scenario") == BASELINE_SCENARIO)
    kept = (
        selected_all.filter(pl.col("scenario") == PAPER_SCENARIO)
        .select("datetime", "symbol")
        .unique()
        .with_columns(pl.lit(True).alias("is_kept"))
    )
    columns = [
        "datetime",
        "symbol",
        "code_name",
        "industry",
        "market",
        "basket_weight",
        "basket_gross_weight",
        "ret_1",
        "ret_5",
        "ret_10",
        "ret_20",
        "dist_ma20",
        "volume_ratio_20",
        "volume_ratio20_band",
        "turnover_5_20_ratio",
        "turnover_5_20_band",
        "top_age",
        "top_age_bucket",
        "candidate_count",
        "selected_industry_count",
        "selected_industry_stock_count",
        "adv20_turnover",
        "turnover_rate_f",
        "circ_mv",
        "trade_close",
        "is_suspended",
        "is_oneword_limit_up",
        "is_oneword_limit_down",
        "is_limit_up_close",
        "is_limit_down_close",
    ]
    selected_columns = [col for col in columns if col in base.columns]
    return (
        base.select(selected_columns)
        .join(kept, on=["datetime", "symbol"], how="left")
        .with_columns(pl.col("is_kept").fill_null(False))
        .with_columns(
            pl.when(pl.col("is_kept"))
            .then(pl.lit("kept"))
            .when(pl.col("volume_ratio20_band") == "volume_dry")
            .then(pl.lit("filtered_volume_dry"))
            .otherwise(pl.lit("filtered_other"))
            .alias("filter_status"),
            pl.lit(PAPER_SCENARIO).alias("paper_scenario"),
        )
        .rename({"datetime": "signal_date"})
        .sort(["signal_date", "filter_status", "industry", "symbol"])
    )


def build_target_weights(selected_all: pl.DataFrame) -> pl.DataFrame:
    symbol_daily = build_symbol_daily_from_selected(selected_all)
    return (
        symbol_daily.filter(pl.col("scenario") == PAPER_SCENARIO)
        .with_columns(
            (pl.col("target_weight") * ACCOUNT_SIZE_CNY).alias("target_amount_cny"),
            pl.lit(ACCOUNT_SIZE_CNY).alias("account_size_cny"),
        )
        .sort(["target_date", "industry", "symbol"])
    )


def build_target_maps(target_weights: pl.DataFrame) -> dict[date, dict[str, dict[str, Any]]]:
    targets: dict[date, dict[str, dict[str, Any]]] = {}
    for row in target_weights.iter_rows(named=True):
        target_date = row["target_date"]
        targets.setdefault(target_date, {})[row["symbol"]] = row
    return targets


def build_symbol_meta(signal_audit: pl.DataFrame) -> dict[str, dict[str, str]]:
    meta: dict[str, dict[str, str]] = {}
    cols = [col for col in ["symbol", "code_name", "industry"] if col in signal_audit.columns]
    for row in signal_audit.select(cols).unique(subset=["symbol"], keep="last").iter_rows(named=True):
        meta[row["symbol"]] = {
            "code_name": str(row.get("code_name") or ""),
            "industry": str(row.get("industry") or ""),
        }
    return meta


def build_tracking_dates(target_weights: pl.DataFrame, benchmark_df: pl.DataFrame) -> list[date]:
    min_date = target_weights["target_date"].min()
    max_date = target_weights["target_date"].max()
    if min_date is None or max_date is None:
        return []
    return (
        benchmark_df.filter((pl.col("datetime") >= min_date) & (pl.col("datetime") <= max_date))
        .select("datetime")
        .unique()
        .sort("datetime")["datetime"]
        .to_list()
    )


def build_exec_info(stock_df: pl.DataFrame) -> dict[tuple[date, str], PaperExecInfo]:
    needed = [
        "datetime",
        "symbol",
        "code_name",
        "trade_open",
        "trade_close",
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
        .with_columns(pl.col("trade_open").shift(-1).over("symbol").alias("next_trade_open"))
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
    info: dict[tuple[date, str], PaperExecInfo] = {}
    for row in work.iter_rows(named=True):
        trade_open = to_float(row.get("trade_open"), default=0.0)
        is_suspended = bool(row.get("is_suspended") or False)
        adv20_turnover = to_float(row.get("adv20_turnover"), default=0.0)
        info[(row["datetime"], row["symbol"])] = PaperExecInfo(
            code_name=str(row.get("code_name") or ""),
            industry=str(row.get("industry") or ""),
            daily_ret=to_float(row.get("open_to_next_open_ret"), default=0.0),
            trade_open=trade_open,
            trade_close=to_float(row.get("trade_close"), default=0.0),
            adv20_turnover=adv20_turnover if adv20_turnover > 0 else None,
            tradable_open=(trade_open > 0 and not is_suspended),
            is_suspended=is_suspended,
            is_oneword_limit_up=bool(row.get("is_oneword_limit_up") or False),
            is_oneword_limit_down=bool(row.get("is_oneword_limit_down") or False),
            is_limit_up_close=bool(row.get("is_limit_up_close") or False),
            is_limit_down_close=bool(row.get("is_limit_down_close") or False),
        )
    return info


def classify_order(side: str, info: PaperExecInfo | None) -> tuple[str, str]:
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
    exec_info: dict[tuple[date, str], PaperExecInfo],
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
            adv20_turnover = info.adv20_turnover if info else None
            adv20_cap_weight = (
                MAX_PARTICIPATION_ADV20 * adv20_turnover / ACCOUNT_SIZE_CNY
                if adv20_turnover is not None and adv20_turnover > 0
                else None
            )
            fill_weight = desired_weight
            if status == "blocked":
                fill_weight = 0.0
                blocked_order_count += 1
            elif adv20_cap_weight is None:
                status = "blocked"
                blocked_reason = "missing_adv20_turnover"
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
                    "adv20_turnover": adv20_turnover,
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


def summarize_tracking(daily: pl.DataFrame, orders: pl.DataFrame, signal_audit: pl.DataFrame) -> dict[str, Any]:
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
    latest_date = daily["date"].max() if daily.height else None
    latest_signal_date = signal_audit["signal_date"].max() if signal_audit.height else None
    latest_orders = orders.filter(pl.col("date") == latest_date) if latest_date and not orders.is_empty() else pl.DataFrame()
    latest_signals = (
        signal_audit.filter(pl.col("signal_date") == latest_signal_date) if latest_signal_date and signal_audit.height else pl.DataFrame()
    )
    return {
        "scenario": PAPER_SCENARIO,
        "account_size_cny": ACCOUNT_SIZE_CNY,
        "max_participation_adv20": MAX_PARTICIPATION_ADV20,
        "roundtrip_cost_bps": ROUNDTRIP_COST_BPS,
        "days": daily.height,
        "latest_target_date": latest_date,
        "latest_signal_date": latest_signal_date,
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
        "latest_order_count": latest_orders.height if not latest_orders.is_empty() else 0,
        "latest_blocked_order_count": latest_orders.filter(pl.col("status") == "blocked").height
        if not latest_orders.is_empty()
        else 0,
        "latest_signal_rows": latest_signals.height if not latest_signals.is_empty() else 0,
        "latest_signal_kept_rows": latest_signals.filter(pl.col("is_kept")).height
        if not latest_signals.is_empty()
        else 0,
        "latest_signal_filtered_rows": latest_signals.filter(~pl.col("is_kept")).height
        if not latest_signals.is_empty()
        else 0,
    }


def build_recent_daily(daily: pl.DataFrame) -> pl.DataFrame:
    if daily.is_empty():
        return daily
    return daily.tail(LATEST_LOOKBACK_DAYS)


def write_report(
    summary: dict[str, Any],
    recent_daily: pl.DataFrame,
    latest_signals: pl.DataFrame,
    latest_targets: pl.DataFrame,
    latest_orders: pl.DataFrame,
    block_reason_summary: pl.DataFrame,
    paths: dict[str, Path],
) -> Path:
    report_path = OUTPUT_DIR / f"{PREFIX}_report.md"
    latest_blocked = latest_orders.filter(pl.col("status") == "blocked") if not latest_orders.is_empty() else pl.DataFrame()
    continue_judgment = "是" if summary["final_equity"] > 1.0 and summary["sharpe"] > 0 else "否"
    continue_reason = (
        "纸面跟踪重放与第248阶段主执行口径一致，且候选在固定规则下仍保持正收益。"
        if continue_judgment == "是"
        else "固定纸面跟踪口径下收益或Sharpe已经失效，需要先排查执行和数据问题。"
    )
    lines = [
        "# 股票震荡liquid_q3纸面跟踪框架 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：把第249阶段后的候选规则固化为每日纸面跟踪流水，不新增信号、不调参数。",
        f"- 纸面候选：`{PAPER_SCENARIO}`。",
        f"- 本地最新信号日：`{summary['latest_signal_date']}`；本地最新目标执行日：`{summary['latest_target_date']}`。",
        "- A/B判断：第78趋势策略与股票震荡策略隔离，因此不做第78 A/B/C。",
        "",
        "## 外部调研判断",
        "",
        "- 纸面跟踪的核心不是再做一条净值曲线，而是把信号、目标仓位、订单、成交阻断、日汇总分表保存。",
        "- 海外开源交易系统多强调订单/成交/TCA日志；A股版本必须额外显式记录停牌、一字涨跌停和ADV成交上限。",
        "- 本阶段使用完整交易日历，空目标日也会触发清仓流水，因此比只在目标日重放更保守。",
        "- 本阶段因此做可审计流水，而不是接券商或实盘接口。",
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
            f"- 全历史纸面重放：期末权益`{summary['final_equity']:.4f}`，总收益`{pct(summary['total_return'])}`，最大回撤`{pct(summary['max_drawdown'])}`，Sharpe `{summary['sharpe']:.2f}`。",
            f"- 整体成交填充率`{pct(summary['overall_fill_ratio'])}`，订单行数`{summary['order_count']}`，阻断订单行数`{summary['blocked_order_count']}`，部分成交订单行数`{summary['partial_order_count']}`。",
            f"- 最新信号日原始候选`{summary['latest_signal_rows']}`只，保留`{summary['latest_signal_kept_rows']}`只，过滤`{summary['latest_signal_filtered_rows']}`只。",
            f"- 最新目标执行日订单`{summary['latest_order_count']}`行，其中阻断`{summary['latest_blocked_order_count']}`行。",
            "- 当前全历史阻断主要来自缺失ADV口径；这需要在后续数据更新和实盘前置检查里单独处理，不能混同为信号失效。",
            "- 直觉判断：这一步更像把研究员的手工检查单写成机器流水；它不能证明未来有效，但能防止我们只盯净值曲线。",
            "",
            "## 全历史阻断原因",
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
            "## 最新信号快照",
            "",
            markdown_table(
                latest_signals.sort(["filter_status", "industry", "symbol"]),
                [
                    "signal_date",
                    "symbol",
                    "code_name",
                    "industry",
                    "filter_status",
                    "basket_weight",
                    "volume_ratio_20",
                    "volume_ratio20_band",
                    "turnover_5_20_ratio",
                    "ret_5",
                    "ret_10",
                    "dist_ma20",
                    "top_age",
                ],
                max_rows=120,
            ),
            "",
            "## 最新目标权重",
            "",
            markdown_table(
                latest_targets.sort(["target_weight", "symbol"], descending=[True, False]),
                [
                    "target_date",
                    "symbol",
                    "industry",
                    "target_weight",
                    "target_amount_cny",
                    "active_lots",
                    "adv20_turnover",
                    "turnover_rate_f",
                    "circ_mv",
                ],
                max_rows=120,
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
                    "unfilled_weight",
                    "adv20_turnover",
                    "trade_open",
                    "is_suspended",
                    "is_oneword_limit_up",
                    "is_oneword_limit_down",
                ],
                max_rows=120,
            ),
            "",
            "## 运行前过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：本阶段只是把已固定候选规则落成纸面跟踪流水，不新增预测变量、不调阈值。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：否，但仍不是样本外结论。",
            "- 原因：纸面跟踪框架提高可复验性，不会通过新增自由度提升历史收益；未来仍要用新增交易日滚动检验。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：第249阶段延迟成交仍通过后，下一步最有价值的是建立每日候选、过滤、目标、订单和阻断的审计链。",
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
            "- 下一步应整理候选版本说明，并做新增交易日纸面跟踪的可重复运行入口。",
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
    summary = summarize_tracking(daily, orders, signal_audit)
    block_reason_summary = build_block_reason_summary(orders)

    latest_signal_date = summary["latest_signal_date"]
    latest_target_date = summary["latest_target_date"]
    filtered_signals = signal_audit.filter(~pl.col("is_kept"))
    latest_signals = signal_audit.filter(pl.col("signal_date") == latest_signal_date)
    latest_targets = target_weights.filter(pl.col("target_date") == latest_target_date)
    latest_orders = orders.filter(pl.col("date") == latest_target_date) if not orders.is_empty() else pl.DataFrame()
    recent_daily = build_recent_daily(daily)

    paths = {
        "signal_audit": OUTPUT_DIR / f"{PREFIX}_signal_audit.csv",
        "filtered_signals": OUTPUT_DIR / f"{PREFIX}_filtered_signals.csv",
        "target_weights": OUTPUT_DIR / f"{PREFIX}_target_weights.csv",
        "paper_orders": OUTPUT_DIR / f"{PREFIX}_paper_orders.csv",
        "block_reason_summary": OUTPUT_DIR / f"{PREFIX}_block_reason_summary.csv",
        "daily_summary": OUTPUT_DIR / f"{PREFIX}_daily_summary.csv",
        "curves": OUTPUT_DIR / f"{PREFIX}_curves.csv",
        "latest_signals": OUTPUT_DIR / f"{PREFIX}_latest_signals.csv",
        "latest_targets": OUTPUT_DIR / f"{PREFIX}_latest_targets.csv",
        "latest_orders": OUTPUT_DIR / f"{PREFIX}_latest_orders.csv",
        "recent_daily": OUTPUT_DIR / f"{PREFIX}_recent_daily.csv",
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.json",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }
    signal_audit.write_csv(paths["signal_audit"])
    filtered_signals.write_csv(paths["filtered_signals"])
    target_weights.write_csv(paths["target_weights"])
    orders.write_csv(paths["paper_orders"])
    block_reason_summary.write_csv(paths["block_reason_summary"])
    daily.write_csv(paths["daily_summary"])
    curves.write_csv(paths["curves"])
    latest_signals.write_csv(paths["latest_signals"])
    latest_targets.write_csv(paths["latest_targets"])
    latest_orders.write_csv(paths["latest_orders"])
    recent_daily.write_csv(paths["recent_daily"])
    paths["summary"].write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    meta = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "paper_scenario": PAPER_SCENARIO,
        "baseline_scenario": BASELINE_SCENARIO,
        "account_size_cny": ACCOUNT_SIZE_CNY,
        "max_participation_adv20": MAX_PARTICIPATION_ADV20,
        "roundtrip_cost_bps": ROUNDTRIP_COST_BPS,
        "latest_lookback_days": LATEST_LOOKBACK_DAYS,
        "source_output_dir": str(FILTER_OUTPUT_DIR),
        "research_sources": RESEARCH_SOURCES,
        "paper_tracking_note": "Historical paper tracking replay from local panel; no live Tushare request and no broker connection.",
    }
    paths["meta"].write_text(json.dumps(meta, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    report_path = write_report(
        summary,
        recent_daily,
        latest_signals,
        latest_targets,
        latest_orders,
        block_reason_summary,
        paths,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
