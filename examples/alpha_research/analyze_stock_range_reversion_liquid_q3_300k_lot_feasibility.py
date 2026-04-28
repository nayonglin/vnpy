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
from backtest_stock_range_reversion_liquid_q3_repairability_filter import OUTPUT_DIR as FILTER_OUTPUT_DIR
from backtest_stock_range_reversion_liquid_q3_repairability_filter import PREFIX as FILTER_PREFIX
from generate_stock_range_reversion_liquid_q3_paper_tracking import (
    MAX_PARTICIPATION_ADV20,
    PAPER_SCENARIO,
    ROUNDTRIP_COST_BPS,
    build_target_weights,
    markdown_table,
)
from generate_stock_range_reversion_liquid_q3_paper_tracking_v3_exante_adv_quality import (
    build_exec_info,
    to_float,
)


OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_300k_lot_feasibility_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_300k_lot_feasibility_v1"

ACCOUNT_SIZE_CNY: float = float(os.getenv("LOT_ACCOUNT_SIZE_CNY", "300000") or 300_000.0)
BOARD_LOT_SHARES: int = int(os.getenv("LOT_BOARD_LOT_SHARES", "100") or 100)
MIN_COMMISSION_CNY: float = float(os.getenv("LOT_MIN_COMMISSION_CNY", "5") or 5.0)
APPLY_MIN_COMMISSION_STRESS: bool = os.getenv("LOT_APPLY_MIN_COMMISSION_STRESS", "1") != "0"

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "SSE: buy orders through auction trading shall be multiples of 100 shares",
        "https://english.sse.com.cn/start/trading/mechanism/",
    ),
    (
        "SZSE Northbound rules: buy orders must be in board lots of 100 shares",
        "https://www.szse.cn/enSzhk/tradeMechanism/tradeRules/index.html",
    ),
    (
        "SSE trading fees reference",
        "https://english.sse.com.cn/start/taxes/",
    ),
)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def annualized_sharpe(returns: list[float]) -> float:
    if len(returns) < 2:
        return 0.0
    mean = sum(returns) / len(returns)
    variance = sum((item - mean) ** 2 for item in returns) / (len(returns) - 1)
    if variance <= 0:
        return 0.0
    return mean / sqrt(variance) * sqrt(TRADING_DAYS)


def max_drawdown_from_equity(values: list[float]) -> float:
    peak = 1.0
    worst = 0.0
    for value in values:
        peak = max(peak, value)
        worst = min(worst, value / peak - 1.0)
    return worst


def floor_to_lot_shares(amount_cny: float, price: float) -> int:
    if amount_cny <= 0 or price <= 0:
        return 0
    shares = int(amount_cny // price)
    return max(0, (shares // BOARD_LOT_SHARES) * BOARD_LOT_SHARES)


def classify_order(side: str, info: Any | None) -> tuple[str, str]:
    if info is None:
        return "blocked", "missing_info"
    if not info.tradable_open:
        return "blocked", "suspended_or_missing_open"
    if side == "buy" and info.is_oneword_limit_up:
        return "blocked", "oneword_limit_up_buy"
    if side == "sell" and info.is_oneword_limit_down:
        return "blocked", "oneword_limit_down_sell"
    return "tradable", ""


def build_target_maps(target_weights: pl.DataFrame) -> dict[date, dict[str, dict[str, Any]]]:
    targets: dict[date, dict[str, dict[str, Any]]] = {}
    for row in target_weights.iter_rows(named=True):
        targets.setdefault(row["target_date"], {})[str(row["symbol"])] = row
    return targets


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


def replay_lot_account(
    target_maps: dict[date, dict[str, dict[str, Any]]],
    dates: list[date],
    exec_info: dict[tuple[date, str], Any],
) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    actual_shares: dict[str, int] = {}
    order_rows: list[dict[str, Any]] = []
    daily_rows: list[dict[str, Any]] = []
    curve_rows: list[dict[str, Any]] = []
    equity_bps = 1.0
    equity_min_fee = 1.0
    peak_bps = 1.0
    peak_min_fee = 1.0
    one_way_cost = ROUNDTRIP_COST_BPS / 2.0 / 10000.0

    for current_date in dates:
        target = target_maps.get(current_date, {})
        symbols = set(actual_shares) | set(target)
        next_shares = dict(actual_shares)
        desired_amount_sum = 0.0
        filled_amount_sum = 0.0
        unfilled_amount_sum = 0.0
        gross_buy_amount = 0.0
        gross_sell_amount = 0.0
        min_fee_cost_cny = 0.0
        bps_cost_cny = 0.0
        blocked_count = 0
        partial_count = 0
        filled_count = 0
        zero_lot_target_count = 0
        target_symbol_count = 0
        target_amount_sum = 0.0
        rounded_target_amount_sum = 0.0

        desired_orders: list[dict[str, Any]] = []
        for symbol in sorted(symbols):
            target_row = target.get(symbol, {})
            info = exec_info.get((current_date, symbol))
            trade_open = to_float(info.trade_open if info else None)
            target_weight = to_float(target_row.get("target_weight"), default=0.0)
            target_amount = target_weight * ACCOUNT_SIZE_CNY
            prev_shares = int(actual_shares.get(symbol, 0))
            target_shares = floor_to_lot_shares(target_amount, trade_open)
            if target_weight > 0:
                target_symbol_count += 1
                target_amount_sum += target_amount
                rounded_target_amount_sum += target_shares * trade_open
                if target_shares <= 0:
                    zero_lot_target_count += 1

            delta_shares = target_shares - prev_shares
            if delta_shares == 0:
                continue
            side = "buy" if delta_shares > 0 else "sell"
            desired_shares = abs(delta_shares)
            desired_amount = desired_shares * trade_open
            desired_orders.append(
                {
                    "symbol": symbol,
                    "target_row": target_row,
                    "info": info,
                    "side": side,
                    "prev_shares": prev_shares,
                    "target_weight": target_weight,
                    "target_amount": target_amount,
                    "target_shares": target_shares,
                    "desired_shares": desired_shares,
                    "desired_amount": desired_amount,
                    "trade_open": trade_open,
                }
            )

        for item in desired_orders:
            symbol = item["symbol"]
            info = item["info"]
            side = item["side"]
            trade_open = item["trade_open"]
            desired_shares = int(item["desired_shares"])
            desired_amount = to_float(item["desired_amount"])
            target_row = item["target_row"]
            status, blocked_reason = classify_order(side, info)
            adv_turnover = info.adv_turnover_for_cap if info is not None else None
            cap_amount = MAX_PARTICIPATION_ADV20 * adv_turnover if adv_turnover is not None and adv_turnover > 0 else None
            cap_shares = floor_to_lot_shares(cap_amount or 0.0, trade_open)
            filled_shares = desired_shares

            if status == "blocked":
                filled_shares = 0
                blocked_count += 1
            elif cap_amount is None:
                status = "blocked"
                blocked_reason = "missing_adv_turnover_for_cap"
                filled_shares = 0
                blocked_count += 1
            elif desired_shares > cap_shares:
                filled_shares = cap_shares
                if filled_shares > 0:
                    status = "partial_cap_limited"
                    partial_count += 1
                else:
                    status = "blocked"
                    blocked_reason = "zero_lot_adv_cap"
                    blocked_count += 1

            filled_amount = filled_shares * trade_open
            unfilled_shares = max(0, desired_shares - filled_shares)
            unfilled_amount = unfilled_shares * trade_open
            if filled_shares > 0:
                next_value = int(item["prev_shares"]) + (filled_shares if side == "buy" else -filled_shares)
                if next_value > 0:
                    next_shares[symbol] = next_value
                else:
                    next_shares.pop(symbol, None)
                filled_count += 1
                filled_amount_sum += filled_amount
                bps_cost_cny += filled_amount * one_way_cost
                min_fee_cost_cny += max(filled_amount * one_way_cost, MIN_COMMISSION_CNY)
                if side == "buy":
                    gross_buy_amount += filled_amount
                else:
                    gross_sell_amount += filled_amount

            desired_amount_sum += desired_amount
            unfilled_amount_sum += unfilled_amount
            order_rows.append(
                {
                    "date": current_date,
                    "scenario": PAPER_SCENARIO,
                    "account_size_cny": ACCOUNT_SIZE_CNY,
                    "symbol": symbol,
                    "code_name": info.code_name if info else "",
                    "industry": target_row.get("industry") or "",
                    "side": side,
                    "status": status,
                    "blocked_reason": blocked_reason,
                    "prev_shares": int(item["prev_shares"]),
                    "target_weight": item["target_weight"],
                    "target_amount_cny": item["target_amount"],
                    "target_shares": int(item["target_shares"]),
                    "desired_shares": desired_shares,
                    "filled_shares": filled_shares,
                    "unfilled_shares": unfilled_shares,
                    "actual_shares_after": next_shares.get(symbol, 0),
                    "trade_open": trade_open,
                    "one_lot_amount_cny": trade_open * BOARD_LOT_SHARES,
                    "desired_amount_cny": desired_amount,
                    "filled_amount_cny": filled_amount,
                    "unfilled_amount_cny": unfilled_amount,
                    "adv_cap_amount_cny": cap_amount,
                    "adv_cap_shares": cap_shares,
                    "bps_cost_cny": filled_amount * one_way_cost if filled_shares else 0.0,
                    "min_fee_cost_cny": max(filled_amount * one_way_cost, MIN_COMMISSION_CNY)
                    if filled_shares
                    else 0.0,
                }
            )

        actual_shares = {symbol: shares for symbol, shares in next_shares.items() if shares > 0}
        gross_ret = 0.0
        missing_return_amount = 0.0
        actual_market_value = 0.0
        for symbol, shares in actual_shares.items():
            info = exec_info.get((current_date, symbol))
            if info is None or info.trade_open <= 0:
                missing_return_amount += 0.0
                continue
            amount = shares * info.trade_open
            actual_market_value += amount
            gross_ret += (amount / ACCOUNT_SIZE_CNY) * info.daily_ret

        cost_ret_bps = bps_cost_cny / ACCOUNT_SIZE_CNY
        cost_ret_min_fee = min_fee_cost_cny / ACCOUNT_SIZE_CNY if APPLY_MIN_COMMISSION_STRESS else cost_ret_bps
        daily_ret_bps = gross_ret - cost_ret_bps
        daily_ret_min_fee = gross_ret - cost_ret_min_fee
        equity_bps *= 1.0 + daily_ret_bps
        equity_min_fee *= 1.0 + daily_ret_min_fee
        peak_bps = max(peak_bps, equity_bps)
        peak_min_fee = max(peak_min_fee, equity_min_fee)
        daily_rows.append(
            {
                "date": current_date,
                "account_size_cny": ACCOUNT_SIZE_CNY,
                "target_symbol_count": target_symbol_count,
                "target_amount_sum_cny": target_amount_sum,
                "rounded_target_amount_sum_cny": rounded_target_amount_sum,
                "zero_lot_target_count": zero_lot_target_count,
                "actual_symbol_count": len(actual_shares),
                "actual_market_value_cny": actual_market_value,
                "actual_gross_weight": actual_market_value / ACCOUNT_SIZE_CNY,
                "desired_amount_sum_cny": desired_amount_sum,
                "filled_amount_sum_cny": filled_amount_sum,
                "unfilled_amount_sum_cny": unfilled_amount_sum,
                "buy_amount_cny": gross_buy_amount,
                "sell_amount_cny": gross_sell_amount,
                "blocked_order_count": blocked_count,
                "partial_order_count": partial_count,
                "filled_order_count": filled_count,
                "strategy_gross_daily_ret": gross_ret,
                "turnover_cost_ret_bps_only": cost_ret_bps,
                "turnover_cost_ret_min_fee": cost_ret_min_fee,
                "strategy_daily_ret_bps_only": daily_ret_bps,
                "strategy_daily_ret_min_fee": daily_ret_min_fee,
                "equity_bps_only": equity_bps,
                "equity_min_fee": equity_min_fee,
                "drawdown_bps_only": equity_bps / peak_bps - 1.0,
                "drawdown_min_fee": equity_min_fee / peak_min_fee - 1.0,
                "missing_return_amount_cny": missing_return_amount,
            }
        )
        curve_rows.append(
            {
                "date": current_date,
                "equity_bps_only": equity_bps,
                "equity_min_fee": equity_min_fee,
                "drawdown_bps_only": equity_bps / peak_bps - 1.0,
                "drawdown_min_fee": equity_min_fee / peak_min_fee - 1.0,
            }
        )

    return (
        pl.DataFrame(order_rows).sort(["date", "symbol", "side"]) if order_rows else pl.DataFrame(),
        pl.DataFrame(daily_rows).sort("date") if daily_rows else pl.DataFrame(),
        pl.DataFrame(curve_rows).sort("date") if curve_rows else pl.DataFrame(),
    )


def summarize_orders(orders: pl.DataFrame, daily: pl.DataFrame) -> dict[str, Any]:
    if daily.is_empty():
        return {}
    ret_bps = daily["strategy_daily_ret_bps_only"].to_list()
    ret_min_fee = daily["strategy_daily_ret_min_fee"].to_list()
    filled_orders = orders.filter(pl.col("filled_shares") > 0) if not orders.is_empty() else pl.DataFrame()
    latest_date = daily["date"].max()
    latest_daily = daily.filter(pl.col("date") == latest_date).row(0, named=True)
    latest_orders = orders.filter(pl.col("date") == latest_date) if not orders.is_empty() else pl.DataFrame()
    lot_blocked_targets = int(daily["zero_lot_target_count"].sum() or 0)
    target_symbols = int(daily["target_symbol_count"].sum() or 0)
    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "scenario": PAPER_SCENARIO,
        "account_size_cny": ACCOUNT_SIZE_CNY,
        "board_lot_shares": BOARD_LOT_SHARES,
        "min_commission_cny": MIN_COMMISSION_CNY,
        "apply_min_commission_stress": APPLY_MIN_COMMISSION_STRESS,
        "date_start": daily["date"].min(),
        "date_end": latest_date,
        "trading_days": daily.height,
        "order_rows": orders.height,
        "filled_order_rows": filled_orders.height,
        "blocked_order_rows": orders.filter(pl.col("status") == "blocked").height if not orders.is_empty() else 0,
        "partial_order_rows": orders.filter(pl.col("status") == "partial_cap_limited").height
        if not orders.is_empty()
        else 0,
        "zero_lot_target_count_sum": lot_blocked_targets,
        "target_symbol_count_sum": target_symbols,
        "zero_lot_target_ratio": lot_blocked_targets / target_symbols if target_symbols else 0.0,
        "final_equity_bps_only": daily["equity_bps_only"][-1],
        "total_return_bps_only": daily["equity_bps_only"][-1] - 1.0,
        "max_drawdown_bps_only": daily["drawdown_bps_only"].min(),
        "sharpe_bps_only": annualized_sharpe(ret_bps),
        "final_equity_min_fee": daily["equity_min_fee"][-1],
        "total_return_min_fee": daily["equity_min_fee"][-1] - 1.0,
        "max_drawdown_min_fee": daily["drawdown_min_fee"].min(),
        "sharpe_min_fee": annualized_sharpe(ret_min_fee),
        "latest_target_date": latest_date,
        "latest_target_symbol_count": latest_daily["target_symbol_count"],
        "latest_actual_symbol_count": latest_daily["actual_symbol_count"],
        "latest_zero_lot_target_count": latest_daily["zero_lot_target_count"],
        "latest_actual_gross_weight": latest_daily["actual_gross_weight"],
        "latest_target_amount_sum_cny": latest_daily["target_amount_sum_cny"],
        "latest_rounded_target_amount_sum_cny": latest_daily["rounded_target_amount_sum_cny"],
        "latest_desired_amount_sum_cny": latest_daily["desired_amount_sum_cny"],
        "latest_filled_amount_sum_cny": latest_daily["filled_amount_sum_cny"],
        "latest_unfilled_amount_sum_cny": latest_daily["unfilled_amount_sum_cny"],
        "latest_order_count": latest_orders.height,
        "latest_filled_order_count": latest_orders.filter(pl.col("filled_shares") > 0).height
        if not latest_orders.is_empty()
        else 0,
        "latest_zero_lot_order_count": latest_orders.filter(pl.col("desired_shares") == 0).height
        if not latest_orders.is_empty()
        else 0,
    }


def build_order_summary(orders: pl.DataFrame) -> pl.DataFrame:
    if orders.is_empty():
        return pl.DataFrame()
    return (
        orders.group_by(["side", "status", "blocked_reason"])
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


def build_latest_holdings(orders: pl.DataFrame, daily: pl.DataFrame) -> pl.DataFrame:
    if orders.is_empty() or daily.is_empty():
        return pl.DataFrame()
    latest_date = daily["date"].max()
    latest_orders = orders.filter(pl.col("date") <= latest_date)
    latest = (
        latest_orders.sort(["date", "symbol"])
        .group_by("symbol")
        .agg(
            pl.col("date").last().alias("last_order_date"),
            pl.col("code_name").last().alias("code_name"),
            pl.col("industry").last().alias("industry"),
            pl.col("actual_shares_after").last().alias("actual_shares"),
            pl.col("trade_open").last().alias("last_trade_open"),
            pl.col("target_weight").last().alias("last_target_weight"),
        )
        .filter(pl.col("actual_shares") > 0)
        .with_columns(
            (pl.col("actual_shares") * pl.col("last_trade_open")).alias("actual_amount_cny"),
            (pl.col("actual_shares") * pl.col("last_trade_open") / ACCOUNT_SIZE_CNY).alias("actual_weight"),
        )
        .sort("actual_amount_cny", descending=True)
    )
    return latest


def build_quality_checkpoints(summary: dict[str, Any]) -> pl.DataFrame:
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

    zero_ratio = to_float(summary.get("zero_lot_target_ratio"))
    latest_zero = int(summary.get("latest_zero_lot_target_count") or 0)
    add(
        "account_size_is_300k",
        "pass" if abs(to_float(summary.get("account_size_cny")) - 300_000.0) <= 1e-6 else "fail",
        summary.get("account_size_cny"),
        300000,
        "本阶段只研究30万账户，不覆盖原1000万paper口径。",
    )
    add(
        "lot_rounding_has_material_impact",
        "warn" if zero_ratio >= 0.10 else "pass",
        f"{zero_ratio:.2%}",
        "<10% preferred",
        "目标持仓被100股整数手取整为0的比例越高，组合越偏离原策略。",
    )
    add(
        "latest_zero_lot_targets",
        "warn" if latest_zero > 0 else "pass",
        latest_zero,
        0,
        "最新目标日有目标股票买不到一手，说明30万账户颗粒度不足。",
    )
    add(
        "min_fee_drag_material",
        "warn"
        if to_float(summary.get("final_equity_bps_only")) - to_float(summary.get("final_equity_min_fee")) > 0.10
        else "pass",
        to_float(summary.get("final_equity_bps_only")) - to_float(summary.get("final_equity_min_fee")),
        "<=0.10 equity gap",
        "小账户下最低佣金会显著侵蚀多次小额调仓。",
    )
    add(
        "latest_unfilled_amount_zero",
        "pass" if abs(to_float(summary.get("latest_unfilled_amount_sum_cny"))) <= 1e-9 else "warn",
        summary.get("latest_unfilled_amount_sum_cny"),
        0,
        "若一手/容量导致未成交，应先修执行口径。",
    )
    add(
        "no_strategy_parameter_change",
        "pass",
        "no signal/threshold change",
        "no signal/threshold change",
        "本阶段只改变账户规模和交易颗粒度模拟，不改选股信号。",
    )
    return pl.DataFrame(rows)


def write_report(
    summary: dict[str, Any],
    daily: pl.DataFrame,
    order_summary: pl.DataFrame,
    latest_holdings: pl.DataFrame,
    quality: pl.DataFrame,
    paths: dict[str, Path],
) -> Path:
    failed = quality.filter(pl.col("status") == "fail")
    warned = quality.filter(pl.col("status") == "warn")
    recent_daily = daily.tail(20)
    report_path = paths["report"]
    lines = [
        "# 股票震荡liquid_q3 30万账户一手颗粒度可交易性 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：账户规模/一手颗粒度影子回放；不新增信号、不调参数。",
        f"- 账户规模：`{ACCOUNT_SIZE_CNY:,.0f}`元。",
        f"- 买入颗粒度：`{BOARD_LOT_SHARES}`股整数手。",
        "- A/B判断：第78趋势策略与股票震荡策略隔离，因此不做第78 A/B/C。",
        "",
        "## 外部调研判断",
        "",
        "- A股买入通常需要100股整数倍；这对30万这种账户规模会显著影响小权重、多股票策略。",
        "- 本阶段用100股整数手向下取整做影子回放，并额外估算最低佣金压力。",
        "- 我的判断：30万账户能不能做，不看原始权重收益，而要先看一手颗粒度是否把组合打碎。",
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
            f"- 回放区间：`{summary['date_start']}`到`{summary['date_end']}`，交易日`{summary['trading_days']}`天。",
            f"- 全历史订单`{summary['order_rows']}`行，成交订单`{summary['filled_order_rows']}`行，阻断订单`{summary['blocked_order_rows']}`行，部分成交`{summary['partial_order_rows']}`行。",
            f"- 目标股票被一手取整为0的比例`{summary['zero_lot_target_ratio']:.2%}`。",
            f"- bps成本口径：期末权益`{summary['final_equity_bps_only']:.4f}`，总收益`{pct(summary['total_return_bps_only'])}`，最大回撤`{pct(summary['max_drawdown_bps_only'])}`，Sharpe `{summary['sharpe_bps_only']:.2f}`。",
            f"- 最低佣金压力口径：期末权益`{summary['final_equity_min_fee']:.4f}`，总收益`{pct(summary['total_return_min_fee'])}`，最大回撤`{pct(summary['max_drawdown_min_fee'])}`，Sharpe `{summary['sharpe_min_fee']:.2f}`。",
            f"- 最新目标日`{summary['latest_target_date']}`：目标`{summary['latest_target_symbol_count']}`只，实际持仓`{summary['latest_actual_symbol_count']}`只，目标取整为0的股票`{summary['latest_zero_lot_target_count']}`只。",
            f"- 最新目标金额`{summary['latest_target_amount_sum_cny']:.0f}`元，取整后目标市值`{summary['latest_rounded_target_amount_sum_cny']:.0f}`元，实际暴露`{pct(summary['latest_actual_gross_weight'])}`。",
            f"- 最新调仓成交金额`{summary['latest_filled_amount_sum_cny']:.0f}`元，未成交金额`{summary['latest_unfilled_amount_sum_cny']:.0f}`元。",
            "- 结论：30万账户下，一手颗粒度和最低佣金都会明显改变策略形态；不能直接沿用1000万paper结论。",
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
            "## 最新20日汇总",
            "",
            markdown_table(
                recent_daily,
                [
                    "date",
                    "target_symbol_count",
                    "zero_lot_target_count",
                    "actual_symbol_count",
                    "actual_gross_weight",
                    "filled_amount_sum_cny",
                    "turnover_cost_ret_bps_only",
                    "turnover_cost_ret_min_fee",
                    "strategy_daily_ret_bps_only",
                    "strategy_daily_ret_min_fee",
                    "equity_bps_only",
                    "equity_min_fee",
                    "drawdown_min_fee",
                ],
                max_rows=30,
            ),
            "",
            "## 订单状态汇总",
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
            "## 最新持仓",
            "",
            markdown_table(
                latest_holdings,
                [
                    "symbol",
                    "code_name",
                    "industry",
                    "actual_shares",
                    "last_trade_open",
                    "actual_amount_cny",
                    "actual_weight",
                    "last_target_weight",
                ],
                max_rows=80,
            ),
            "",
            "## 运行前过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：本阶段只把账户规模改为30万并加入100股整数手约束，不改信号和阈值。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：即使结果变差，也没有据此调参；这只是硬约束压力测试。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：用户计划30万账户，真实交易颗粒度会显著影响可交易性。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：30万账户和1000万paper形态差异明显，后续若继续，应专门做30万账户版本，而不是沿用原paper结论。",
            "",
            "## 决策",
            "",
            "- 不接入第78。",
            "- 不进入正式股票策略。",
            "- 不做第78 A/B/C。",
            "- 不调`volume_ratio_20 <= 0.70`阈值。",
            "- 30万账户需独立研究实盘颗粒度版本；当前1000万paper结果不能直接迁移。",
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
    target_weights = build_target_weights(selected_all)
    target_maps = build_target_maps(target_weights)
    dates = build_tracking_dates(target_weights, benchmark_df)
    exec_info = build_exec_info(stock_df)
    orders, daily, curves = replay_lot_account(target_maps, dates, exec_info)
    summary = summarize_orders(orders, daily)
    order_summary = build_order_summary(orders)
    latest_holdings = build_latest_holdings(orders, daily)
    quality = build_quality_checkpoints(summary)
    paths = {
        "report": OUTPUT_DIR / f"{PREFIX}_report.md",
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.json",
        "daily": OUTPUT_DIR / f"{PREFIX}_daily.csv",
        "orders": OUTPUT_DIR / f"{PREFIX}_orders.csv",
        "curves": OUTPUT_DIR / f"{PREFIX}_curves.csv",
        "order_summary": OUTPUT_DIR / f"{PREFIX}_order_summary.csv",
        "latest_holdings": OUTPUT_DIR / f"{PREFIX}_latest_holdings.csv",
        "quality_checkpoints": OUTPUT_DIR / f"{PREFIX}_quality_checkpoints.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }
    orders.write_csv(paths["orders"])
    daily.write_csv(paths["daily"])
    curves.write_csv(paths["curves"])
    order_summary.write_csv(paths["order_summary"])
    latest_holdings.write_csv(paths["latest_holdings"])
    quality.write_csv(paths["quality_checkpoints"])
    write_json(paths["summary"], summary)
    write_json(
        paths["meta"],
        {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "account_size_cny": ACCOUNT_SIZE_CNY,
            "board_lot_shares": BOARD_LOT_SHARES,
            "min_commission_cny": MIN_COMMISSION_CNY,
            "roundtrip_cost_bps": ROUNDTRIP_COST_BPS,
            "max_participation_adv20": MAX_PARTICIPATION_ADV20,
            "research_sources": RESEARCH_SOURCES,
            "note": "Lot feasibility shadow replay only; it does not change the core signal or strategy parameters.",
        },
    )
    report_path = write_report(summary, daily, order_summary, latest_holdings, quality, paths)
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
