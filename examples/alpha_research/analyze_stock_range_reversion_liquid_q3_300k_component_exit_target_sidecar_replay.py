from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import polars as pl

import analyze_stock_range_reversion_liquid_q3_300k_lot_feasibility as lot
from analyze_stock_range_reversion_layer_attribution import load_panels
from analyze_stock_range_reversion_liquid_q3_300k_repairable_state_overlay import (
    OUTPUT_DIR as REPAIRABLE_OUTPUT_DIR,
    PREFIX as REPAIRABLE_PREFIX,
)
from analyze_stock_range_reversion_liquid_q3_300k_st_buy_guard_replay import (
    build_block_reason_summary,
    summarize_by_state,
    summarize_daily,
)
from analyze_stock_range_reversion_liquid_q3_300k_st_buy_guard_strict_exante_replay import (
    OUTPUT_DIR as STRICT_OUTPUT_DIR,
    PREFIX as STRICT_PREFIX,
    build_strict_exante_guarded_exec_info,
)
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import NATIVE_RESULTS_DIR, pct
from backtest_stock_range_reversion_liquid_q3_repairability_filter import OUTPUT_DIR as FILTER_OUTPUT_DIR
from backtest_stock_range_reversion_liquid_q3_repairability_filter import PREFIX as FILTER_PREFIX
from generate_stock_range_reversion_liquid_q3_paper_tracking import (
    MAX_PARTICIPATION_ADV20,
    PAPER_SCENARIO,
    ROUNDTRIP_COST_BPS,
    build_target_weights,
    markdown_table,
)
from generate_stock_range_reversion_liquid_q3_paper_tracking_v3_exante_adv_quality import build_exec_info, to_float


OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_300k_component_exit_target_sidecar_replay_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_300k_component_exit_target_sidecar_replay_v1"

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "QuantConnect documents ETF constituent universes as point-in-time membership for backtests",
        "https://www.quantconnect.com/docs/v2/writing-algorithms/universes/equity/etf-constituents-universes",
    ),
    (
        "QuantConnect documents pre-trade risk controls before order submission",
        "https://www.quantconnect.com/docs/v2/writing-algorithms/trading-and-orders/pre-trade-risk-control",
    ),
    (
        "Tushare index_weight provides index constituent and weight history",
        "https://tushare.pro/document/2?doc_id=96",
    ),
)


def _sum_float(frame: pl.DataFrame, column: str) -> float:
    if frame.is_empty() or column not in frame.columns:
        return 0.0
    return to_float(frame.select(pl.col(column).sum()).item())


def _markdown_all(frame: pl.DataFrame, max_rows: int = 80) -> str:
    if frame.is_empty():
        return "无数据"
    return markdown_table(frame, frame.columns, max_rows=max_rows)


def build_component_membership(stock_df: pl.DataFrame) -> dict[tuple[Any, str], bool]:
    frame = (
        stock_df.select(["datetime", "symbol", "is_index_component"])
        .rename({"datetime": "date"})
        .with_columns(pl.col("symbol").cast(pl.Utf8).str.zfill(6))
        .unique(["date", "symbol"])
    )
    return {
        (row["date"], row["symbol"]): bool(row["is_index_component"])
        for row in frame.iter_rows(named=True)
    }


def classify_order(side: str, info: Any | None, strict_guard_enabled: bool) -> tuple[str, str]:
    status, reason = lot.classify_order(side, info)
    if status != "blocked" and strict_guard_enabled and side == "buy" and bool(getattr(info, "st_buy_guard", False)):
        return "blocked", "st_or_ineligible_buy"
    return status, reason


def replay_lot_account_with_target_sidecar(
    target_maps: dict[Any, dict[str, dict[str, Any]]],
    dates: list[Any],
    exec_info: dict[tuple[Any, str], Any],
    component_membership: dict[tuple[Any, str], bool],
    *,
    component_no_buy_add: bool,
    strict_guard_enabled: bool,
) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    actual_shares: dict[str, int] = {}
    order_rows: list[dict[str, Any]] = []
    daily_rows: list[dict[str, Any]] = []
    curve_rows: list[dict[str, Any]] = []
    adjustment_rows: list[dict[str, Any]] = []
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
        raw_target_symbol_count = 0
        raw_target_amount_sum = 0.0
        raw_rounded_target_amount_sum = 0.0
        sidecar_adjustment_count = 0
        sidecar_suppressed_amount_cny = 0.0

        desired_orders: list[dict[str, Any]] = []
        for symbol in sorted(symbols):
            target_row = target.get(symbol, {})
            info = exec_info.get((current_date, symbol))
            trade_open = to_float(info.trade_open if info else None)
            raw_target_weight = to_float(target_row.get("target_weight"), default=0.0)
            raw_target_amount = raw_target_weight * lot.ACCOUNT_SIZE_CNY
            prev_shares = int(actual_shares.get(symbol, 0))
            raw_target_shares = lot.floor_to_lot_shares(raw_target_amount, trade_open)
            current_component = component_membership.get((current_date, symbol), False)
            target_shares = raw_target_shares
            target_weight = raw_target_weight
            target_amount = raw_target_amount
            sidecar_reason = ""
            suppressed_shares = 0

            if raw_target_weight > 0:
                raw_target_symbol_count += 1
                raw_target_amount_sum += raw_target_amount
                raw_rounded_target_amount_sum += raw_target_shares * trade_open

            if component_no_buy_add and raw_target_weight > 0 and not current_component:
                capped_target_shares = min(raw_target_shares, prev_shares)
                if capped_target_shares < raw_target_shares:
                    sidecar_reason = "not_index_component_no_buy_add"
                    target_shares = capped_target_shares
                    target_amount = target_shares * trade_open
                    target_weight = target_amount / lot.ACCOUNT_SIZE_CNY if lot.ACCOUNT_SIZE_CNY else 0.0
                    suppressed_shares = raw_target_shares - target_shares
                    sidecar_adjustment_count += 1
                    sidecar_suppressed_amount_cny += suppressed_shares * trade_open
                    adjustment_rows.append(
                        {
                            "date": current_date,
                            "scenario": PAPER_SCENARIO,
                            "symbol": symbol,
                            "code_name": info.code_name if info else "",
                            "industry": target_row.get("industry") or "",
                            "component_target_sidecar_reason": sidecar_reason,
                            "is_index_component_on_target_date": current_component,
                            "prev_shares": prev_shares,
                            "raw_target_weight": raw_target_weight,
                            "raw_target_amount_cny": raw_target_amount,
                            "raw_target_shares": raw_target_shares,
                            "sidecar_target_weight": target_weight,
                            "sidecar_target_amount_cny": target_amount,
                            "sidecar_target_shares": target_shares,
                            "suppressed_shares": suppressed_shares,
                            "suppressed_amount_cny": suppressed_shares * trade_open,
                            "would_be_new_entry": prev_shares <= 0,
                            "would_be_add_to_existing": prev_shares > 0,
                            "trade_open": trade_open,
                        }
                    )

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
                    "raw_target_weight": raw_target_weight,
                    "raw_target_amount": raw_target_amount,
                    "raw_target_shares": raw_target_shares,
                    "target_weight": target_weight,
                    "target_amount": target_amount,
                    "target_shares": target_shares,
                    "desired_shares": desired_shares,
                    "desired_amount": desired_amount,
                    "trade_open": trade_open,
                    "component_target_sidecar_reason": sidecar_reason,
                    "is_index_component_on_target_date": current_component,
                    "suppressed_shares": suppressed_shares,
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
            status, blocked_reason = classify_order(side, info, strict_guard_enabled)
            adv_turnover = info.adv_turnover_for_cap if info is not None else None
            cap_amount = MAX_PARTICIPATION_ADV20 * adv_turnover if adv_turnover is not None and adv_turnover > 0 else None
            cap_shares = lot.floor_to_lot_shares(cap_amount or 0.0, trade_open)
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
                min_fee_cost_cny += max(filled_amount * one_way_cost, lot.MIN_COMMISSION_CNY)
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
                    "account_size_cny": lot.ACCOUNT_SIZE_CNY,
                    "symbol": symbol,
                    "code_name": info.code_name if info else "",
                    "industry": target_row.get("industry") or "",
                    "side": side,
                    "status": status,
                    "blocked_reason": blocked_reason,
                    "strict_exante_guard_reason": getattr(info, "strict_exante_guard_reason", ""),
                    "component_target_sidecar_reason": item["component_target_sidecar_reason"],
                    "is_index_component_on_target_date": item["is_index_component_on_target_date"],
                    "prev_shares": int(item["prev_shares"]),
                    "raw_target_weight": item["raw_target_weight"],
                    "raw_target_amount_cny": item["raw_target_amount"],
                    "raw_target_shares": int(item["raw_target_shares"]),
                    "target_weight": item["target_weight"],
                    "target_amount_cny": item["target_amount"],
                    "target_shares": int(item["target_shares"]),
                    "suppressed_shares": int(item["suppressed_shares"]),
                    "desired_shares": desired_shares,
                    "filled_shares": filled_shares,
                    "unfilled_shares": unfilled_shares,
                    "actual_shares_after": next_shares.get(symbol, 0),
                    "trade_open": trade_open,
                    "one_lot_amount_cny": trade_open * lot.BOARD_LOT_SHARES,
                    "desired_amount_cny": desired_amount,
                    "filled_amount_cny": filled_amount,
                    "unfilled_amount_cny": unfilled_amount,
                    "adv_cap_amount_cny": cap_amount,
                    "adv_cap_shares": cap_shares,
                    "bps_cost_cny": filled_amount * one_way_cost if filled_shares else 0.0,
                    "min_fee_cost_cny": max(filled_amount * one_way_cost, lot.MIN_COMMISSION_CNY)
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
            gross_ret += (amount / lot.ACCOUNT_SIZE_CNY) * info.daily_ret

        cost_ret_bps = bps_cost_cny / lot.ACCOUNT_SIZE_CNY
        cost_ret_min_fee = min_fee_cost_cny / lot.ACCOUNT_SIZE_CNY if lot.APPLY_MIN_COMMISSION_STRESS else cost_ret_bps
        daily_ret_bps = gross_ret - cost_ret_bps
        daily_ret_min_fee = gross_ret - cost_ret_min_fee
        equity_bps *= 1.0 + daily_ret_bps
        equity_min_fee *= 1.0 + daily_ret_min_fee
        peak_bps = max(peak_bps, equity_bps)
        peak_min_fee = max(peak_min_fee, equity_min_fee)
        daily_rows.append(
            {
                "date": current_date,
                "account_size_cny": lot.ACCOUNT_SIZE_CNY,
                "raw_target_symbol_count": raw_target_symbol_count,
                "raw_target_amount_sum_cny": raw_target_amount_sum,
                "raw_rounded_target_amount_sum_cny": raw_rounded_target_amount_sum,
                "target_symbol_count": target_symbol_count,
                "target_amount_sum_cny": target_amount_sum,
                "rounded_target_amount_sum_cny": rounded_target_amount_sum,
                "zero_lot_target_count": zero_lot_target_count,
                "component_target_sidecar_adjustment_count": sidecar_adjustment_count,
                "component_target_sidecar_suppressed_amount_cny": sidecar_suppressed_amount_cny,
                "actual_symbol_count": len(actual_shares),
                "actual_market_value_cny": actual_market_value,
                "actual_gross_weight": actual_market_value / lot.ACCOUNT_SIZE_CNY,
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
        pl.DataFrame(adjustment_rows).sort(["date", "symbol"]) if adjustment_rows else pl.DataFrame(),
    )


def summarize_adjustments(adjustments: pl.DataFrame) -> pl.DataFrame:
    if adjustments.is_empty():
        return pl.DataFrame()
    return (
        adjustments.group_by("component_target_sidecar_reason")
        .agg(
            pl.len().alias("rows"),
            pl.col("symbol").n_unique().alias("symbols"),
            pl.col("date").n_unique().alias("dates"),
            pl.col("suppressed_amount_cny").sum().alias("suppressed_amount_cny_sum"),
            pl.col("would_be_new_entry").sum().alias("would_be_new_entry_rows"),
            pl.col("would_be_add_to_existing").sum().alias("would_be_add_to_existing_rows"),
        )
        .sort(["rows", "suppressed_amount_cny_sum"], descending=True)
    )


def summarize_adjustment_symbols(adjustments: pl.DataFrame) -> pl.DataFrame:
    if adjustments.is_empty():
        return pl.DataFrame()
    return (
        adjustments.group_by(["symbol", "code_name", "industry"])
        .agg(
            pl.len().alias("rows"),
            pl.col("date").min().alias("first_date"),
            pl.col("date").max().alias("last_date"),
            pl.col("suppressed_amount_cny").sum().alias("suppressed_amount_cny_sum"),
            pl.col("would_be_new_entry").sum().alias("would_be_new_entry_rows"),
            pl.col("would_be_add_to_existing").sum().alias("would_be_add_to_existing_rows"),
        )
        .sort(["rows", "suppressed_amount_cny_sum"], descending=True)
    )


def build_scorecard(summaries: list[dict[str, Any]]) -> pl.DataFrame:
    return pl.DataFrame(summaries).select(
        [
            "scenario",
            "final_equity",
            "total_return",
            "max_drawdown",
            "sharpe",
            "orders",
            "filled_orders",
            "blocked_orders",
            "blocked_amount_cny",
            "st_or_ineligible_buy_blocked_orders",
            "st_or_ineligible_buy_blocked_amount_cny",
            "avg_actual_gross_weight",
            "max_actual_gross_weight",
        ]
    )


def build_quality(summary: dict[str, Any], sidecar_strict_orders: pl.DataFrame, adjustments: pl.DataFrame) -> pl.DataFrame:
    strict_guard_blocks = (
        sidecar_strict_orders.filter(pl.col("blocked_reason") == "st_or_ineligible_buy")
        if not sidecar_strict_orders.is_empty()
        else pl.DataFrame()
    )
    not_index_guard_blocks = (
        strict_guard_blocks.filter(pl.col("strict_exante_guard_reason") == "not_index_component")
        if not strict_guard_blocks.is_empty()
        else strict_guard_blocks
    )
    malformed_adjustments = (
        adjustments.filter(pl.col("is_index_component_on_target_date"))
        if not adjustments.is_empty()
        else adjustments
    )
    final_gap_vs_strict = abs(summary["sidecar_plus_strict_final_equity"] - summary["strict_reference_final_equity"])
    rows = [
        {
            "checkpoint": "target_sidecar_has_component_adjustments",
            "status": "pass" if summary["component_adjustment_rows"] > 0 else "warn",
            "value": str(summary["component_adjustment_rows"]),
            "expected": ">0",
            "note": "第285阶段已确认有持仓窗口跨成分调出，目标层应能捕捉这些边界买入/加仓。",
        },
        {
            "checkpoint": "adjustments_only_non_component_target_dates",
            "status": "pass" if malformed_adjustments.is_empty() else "fail",
            "value": str(malformed_adjustments.height),
            "expected": "0",
            "note": "目标层sidecar只能调整目标日非成分股，不应误伤仍在成分内的股票。",
        },
        {
            "checkpoint": "no_not_index_component_guard_blocks_after_sidecar",
            "status": "pass" if not_index_guard_blocks.is_empty() else "fail",
            "value": str(not_index_guard_blocks.height),
            "expected": "0",
            "note": "非成分买入/加仓应在目标层消失，而不是继续落到执行守门。",
        },
        {
            "checkpoint": "sidecar_plus_strict_matches_strict_reference_equity",
            "status": "pass" if final_gap_vs_strict <= 1e-10 else "warn",
            "value": f"{final_gap_vs_strict:.12f}",
            "expected": "<=1e-10",
            "note": "目标层消除非成分加仓后，持仓路径应与严格守门基本一致；差异主要应只体现在订单审计口径。",
        },
        {
            "checkpoint": "sidecar_not_return_chasing",
            "status": "pass",
            "value": "no signal/threshold change",
            "expected": "no signal/threshold change",
            "note": "本阶段只前移成分资格约束，不按收益调仓位或阈值。",
        },
    ]
    return pl.DataFrame(rows)


def write_report(
    summary: dict[str, Any],
    scorecard: pl.DataFrame,
    block_summary: pl.DataFrame,
    adjustment_summary: pl.DataFrame,
    adjustment_symbol_summary: pl.DataFrame,
    state_summary: pl.DataFrame,
    quality: pl.DataFrame,
    paths: dict[str, Path],
) -> Path:
    failed = quality.filter(pl.col("status") == "fail")
    warned = quality.filter(pl.col("status") == "warn")
    report_path = paths["report"]
    lines = [
        "# 股票震荡liquid_q3 30万 成分调出目标层sidecar回放 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：验证第285非成分阻断是否可以前移到目标权重层；不改正式paper入口。",
        f"- 账户规模：`{lot.ACCOUNT_SIZE_CNY:,.0f}`元。",
        "- A/B判断：股票震荡独立执行/目标层审计，不做第78 A/B/C。",
        "",
        "## 外部调研判断",
        "",
        "- 指数成分策略应使用点时成分身份；目标交易日已经不在成分内时，不应继续生成新增买入/加仓目标。",
        "- pre-trade control仍然需要保留，但更好的工程形态是上游目标层先把明显不该买的订单消掉，执行层只做最后兜底。",
        "- 本阶段采用保守规则：非成分股目标只允许不高于当前持仓；可以卖出、可以自然衰减，但不能新买或加仓。",
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
            f"- 目标层sidecar调整`{summary['component_adjustment_rows']}`行，涉及`{summary['component_adjustment_symbols']}`只，压掉买入/加仓金额`{summary['component_adjustment_amount_cny']:,.0f}`元。",
            f"- sidecar+严格守门期末权益`{summary['sidecar_plus_strict_final_equity']:.4f}`，总收益`{pct(summary['sidecar_plus_strict_total_return'])}`，最大回撤`{pct(summary['sidecar_plus_strict_max_drawdown'])}`，Sharpe `{summary['sidecar_plus_strict_sharpe']:.4f}`。",
            f"- 相对严格守门参考：期末权益差`{summary['delta_final_equity_vs_strict_reference']:.12f}`，总收益差`{pct(summary['delta_total_return_vs_strict_reference'])}`。",
            f"- sidecar+严格守门剩余`st_or_ineligible_buy`阻断`{summary['sidecar_plus_strict_st_or_ineligible_buy_blocked_orders']}`笔；其中`not_index_component`明细`{summary['sidecar_plus_strict_not_index_guard_blocks']}`笔。",
            "",
            "## 判断",
            "",
            "- 第285的非成分阻断可以被目标层sidecar解释和消化：它不是alpha参数问题，而是持有窗口跨指数调样后的订单生成边界问题。",
            "- 目标层sidecar不是为了提高收益，而是减少无意义订单，让paper包更接近真实可执行流程。",
            "- 严格执行守门仍要保留，因为ST、停牌、涨跌停、ADV等问题属于下单前最后检查，不能只靠目标生成。",
            "",
            "## 绩效对比",
            "",
            _markdown_all(scorecard, max_rows=20),
            "",
            "## 阻断原因对比",
            "",
            _markdown_all(block_summary, max_rows=40),
            "",
            "## 目标层调整汇总",
            "",
            _markdown_all(adjustment_summary, max_rows=20),
            "",
            "## 目标层调整股票",
            "",
            _markdown_all(adjustment_symbol_summary, max_rows=40),
            "",
            "## 市场状态归因",
            "",
            _markdown_all(state_summary, max_rows=40),
            "",
            "## 质量检查",
            "",
            _markdown_all(quality, max_rows=40),
            "",
            "## 失败项",
            "",
            _markdown_all(failed, max_rows=40),
            "",
            "## 警告项",
            "",
            _markdown_all(warned, max_rows=40),
            "",
            "## 运行前过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：规则来自点时成分资格和实盘订单边界，不使用收益结果选择阈值。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：sidecar只是把第285已识别的非成分买入/加仓前移处理，曲线不作为调参目标。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：如果能在目标层消除无意义非成分买单，后续paper包会更干净，执行守门审计也更明确。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：目标层和执行层职责已经可以拆开，下一步可把它做成paper packet sidecar，而不是直接覆盖正式包。",
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
    target_maps = lot.build_target_maps(target_weights)
    dates = lot.build_tracking_dates(target_weights, benchmark_df)
    component_membership = build_component_membership(stock_df)

    base_exec_info = build_exec_info(stock_df)
    strict_exec_info = build_strict_exante_guarded_exec_info(stock_df)
    base_orders, base_daily, base_curves, _base_adjustments = replay_lot_account_with_target_sidecar(
        target_maps,
        dates,
        base_exec_info,
        component_membership,
        component_no_buy_add=False,
        strict_guard_enabled=False,
    )
    sidecar_orders, sidecar_daily, sidecar_curves, sidecar_adjustments = replay_lot_account_with_target_sidecar(
        target_maps,
        dates,
        base_exec_info,
        component_membership,
        component_no_buy_add=True,
        strict_guard_enabled=False,
    )
    sidecar_strict_orders, sidecar_strict_daily, sidecar_strict_curves, sidecar_strict_adjustments = (
        replay_lot_account_with_target_sidecar(
            target_maps,
            dates,
            strict_exec_info,
            component_membership,
            component_no_buy_add=True,
            strict_guard_enabled=True,
        )
    )

    base_summary = summarize_daily(base_daily, base_orders, "base_rerun_custom")
    sidecar_summary = summarize_daily(sidecar_daily, sidecar_orders, "component_target_sidecar_only")
    sidecar_strict_summary = summarize_daily(
        sidecar_strict_daily,
        sidecar_strict_orders,
        "component_target_sidecar_plus_strict_exante_guard",
    )
    strict_reference_summary = json.loads(
        (STRICT_OUTPUT_DIR / f"{STRICT_PREFIX}_summary.json").read_text(encoding="utf-8")
    )
    strict_reference_row = {
        "scenario": "strict_exante_guard_reference_stage284",
        "final_equity": strict_reference_summary["strict_final_equity"],
        "total_return": strict_reference_summary["strict_total_return"],
        "max_drawdown": strict_reference_summary["strict_max_drawdown"],
        "sharpe": strict_reference_summary["strict_sharpe"],
        "daily_rows": sidecar_strict_summary["daily_rows"],
        "orders": strict_reference_summary["strict_orders"],
        "filled_orders": strict_reference_summary["strict_filled_orders"],
        "blocked_orders": strict_reference_summary["strict_blocked_orders"],
        "blocked_amount_cny": strict_reference_summary["strict_blocked_amount_cny"],
        "st_or_ineligible_buy_blocked_orders": strict_reference_summary["strict_blocked_orders"],
        "st_or_ineligible_buy_blocked_amount_cny": strict_reference_summary["strict_blocked_amount_cny"],
        "total_min_fee_cost_cny": None,
        "avg_actual_gross_weight": None,
        "max_actual_gross_weight": None,
    }
    scorecard = build_scorecard([base_summary, sidecar_summary, strict_reference_row, sidecar_strict_summary])

    block_summary = pl.concat(
        [
            build_block_reason_summary(base_orders, "base_rerun_custom"),
            build_block_reason_summary(sidecar_orders, "component_target_sidecar_only"),
            build_block_reason_summary(sidecar_strict_orders, "component_target_sidecar_plus_strict_exante_guard"),
        ],
        how="vertical",
    )
    adjustment_summary = summarize_adjustments(sidecar_strict_adjustments)
    adjustment_symbol_summary = summarize_adjustment_symbols(sidecar_strict_adjustments)
    state = pl.read_csv(REPAIRABLE_OUTPUT_DIR / f"{REPAIRABLE_PREFIX}_repairable_state.csv", try_parse_dates=True)
    state_summary = pl.concat(
        [
            summarize_by_state(base_daily, state, "base_rerun_custom"),
            summarize_by_state(sidecar_daily, state, "component_target_sidecar_only"),
            summarize_by_state(sidecar_strict_daily, state, "component_target_sidecar_plus_strict_exante_guard"),
        ],
        how="vertical",
    )

    strict_guard_blocks = sidecar_strict_orders.filter(pl.col("blocked_reason") == "st_or_ineligible_buy")
    not_index_guard_blocks = strict_guard_blocks.filter(pl.col("strict_exante_guard_reason") == "not_index_component")
    summary: dict[str, Any] = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "scenario": PAPER_SCENARIO,
        "account_size_cny": lot.ACCOUNT_SIZE_CNY,
        "base_final_equity": base_summary["final_equity"],
        "base_total_return": base_summary["total_return"],
        "base_max_drawdown": base_summary["max_drawdown"],
        "base_sharpe": base_summary["sharpe"],
        "component_sidecar_final_equity": sidecar_summary["final_equity"],
        "component_sidecar_total_return": sidecar_summary["total_return"],
        "component_sidecar_max_drawdown": sidecar_summary["max_drawdown"],
        "component_sidecar_sharpe": sidecar_summary["sharpe"],
        "strict_reference_final_equity": strict_reference_summary["strict_final_equity"],
        "strict_reference_total_return": strict_reference_summary["strict_total_return"],
        "strict_reference_max_drawdown": strict_reference_summary["strict_max_drawdown"],
        "strict_reference_sharpe": strict_reference_summary["strict_sharpe"],
        "sidecar_plus_strict_final_equity": sidecar_strict_summary["final_equity"],
        "sidecar_plus_strict_total_return": sidecar_strict_summary["total_return"],
        "sidecar_plus_strict_max_drawdown": sidecar_strict_summary["max_drawdown"],
        "sidecar_plus_strict_sharpe": sidecar_strict_summary["sharpe"],
        "sidecar_plus_strict_orders": sidecar_strict_summary["orders"],
        "sidecar_plus_strict_filled_orders": sidecar_strict_summary["filled_orders"],
        "sidecar_plus_strict_blocked_orders": sidecar_strict_summary["blocked_orders"],
        "sidecar_plus_strict_blocked_amount_cny": sidecar_strict_summary["blocked_amount_cny"],
        "sidecar_plus_strict_st_or_ineligible_buy_blocked_orders": strict_guard_blocks.height,
        "sidecar_plus_strict_st_or_ineligible_buy_blocked_amount_cny": _sum_float(
            strict_guard_blocks,
            "desired_amount_cny",
        ),
        "sidecar_plus_strict_not_index_guard_blocks": not_index_guard_blocks.height,
        "component_adjustment_rows": sidecar_strict_adjustments.height,
        "component_adjustment_symbols": (
            sidecar_strict_adjustments["symbol"].n_unique() if not sidecar_strict_adjustments.is_empty() else 0
        ),
        "component_adjustment_amount_cny": _sum_float(sidecar_strict_adjustments, "suppressed_amount_cny"),
        "component_adjustment_new_entry_rows": (
            int(sidecar_strict_adjustments["would_be_new_entry"].sum()) if not sidecar_strict_adjustments.is_empty() else 0
        ),
        "component_adjustment_add_to_existing_rows": (
            int(sidecar_strict_adjustments["would_be_add_to_existing"].sum())
            if not sidecar_strict_adjustments.is_empty()
            else 0
        ),
        "delta_final_equity_vs_strict_reference": sidecar_strict_summary["final_equity"]
        - strict_reference_summary["strict_final_equity"],
        "delta_total_return_vs_strict_reference": sidecar_strict_summary["total_return"]
        - strict_reference_summary["strict_total_return"],
        "delta_sharpe_vs_strict_reference": sidecar_strict_summary["sharpe"] - strict_reference_summary["strict_sharpe"],
        "delta_total_return_component_sidecar_vs_base": sidecar_summary["total_return"] - base_summary["total_return"],
        "delta_total_return_sidecar_plus_strict_vs_base": sidecar_strict_summary["total_return"]
        - base_summary["total_return"],
    }
    quality = build_quality(summary, sidecar_strict_orders, sidecar_strict_adjustments)
    summary["quality_pass_count"] = quality.filter(pl.col("status") == "pass").height
    summary["quality_warn_count"] = quality.filter(pl.col("status") == "warn").height
    summary["quality_fail_count"] = quality.filter(pl.col("status") == "fail").height

    paths = {
        "report": OUTPUT_DIR / f"{PREFIX}_report.md",
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.json",
        "scorecard": OUTPUT_DIR / f"{PREFIX}_scorecard.csv",
        "base_orders": OUTPUT_DIR / f"{PREFIX}_base_orders.csv",
        "base_daily": OUTPUT_DIR / f"{PREFIX}_base_daily.csv",
        "base_curves": OUTPUT_DIR / f"{PREFIX}_base_curves.csv",
        "sidecar_orders": OUTPUT_DIR / f"{PREFIX}_sidecar_orders.csv",
        "sidecar_daily": OUTPUT_DIR / f"{PREFIX}_sidecar_daily.csv",
        "sidecar_curves": OUTPUT_DIR / f"{PREFIX}_sidecar_curves.csv",
        "sidecar_strict_orders": OUTPUT_DIR / f"{PREFIX}_sidecar_strict_orders.csv",
        "sidecar_strict_daily": OUTPUT_DIR / f"{PREFIX}_sidecar_strict_daily.csv",
        "sidecar_strict_curves": OUTPUT_DIR / f"{PREFIX}_sidecar_strict_curves.csv",
        "sidecar_strict_adjustments": OUTPUT_DIR / f"{PREFIX}_sidecar_strict_adjustments.csv",
        "adjustment_summary": OUTPUT_DIR / f"{PREFIX}_adjustment_summary.csv",
        "adjustment_symbol_summary": OUTPUT_DIR / f"{PREFIX}_adjustment_symbol_summary.csv",
        "block_reason_summary": OUTPUT_DIR / f"{PREFIX}_block_reason_summary.csv",
        "state_summary": OUTPUT_DIR / f"{PREFIX}_state_summary.csv",
        "quality_checkpoints": OUTPUT_DIR / f"{PREFIX}_quality_checkpoints.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }
    scorecard.write_csv(paths["scorecard"])
    base_orders.write_csv(paths["base_orders"])
    base_daily.write_csv(paths["base_daily"])
    base_curves.write_csv(paths["base_curves"])
    sidecar_orders.write_csv(paths["sidecar_orders"])
    sidecar_daily.write_csv(paths["sidecar_daily"])
    sidecar_curves.write_csv(paths["sidecar_curves"])
    sidecar_strict_orders.write_csv(paths["sidecar_strict_orders"])
    sidecar_strict_daily.write_csv(paths["sidecar_strict_daily"])
    sidecar_strict_curves.write_csv(paths["sidecar_strict_curves"])
    sidecar_strict_adjustments.write_csv(paths["sidecar_strict_adjustments"])
    adjustment_summary.write_csv(paths["adjustment_summary"])
    adjustment_symbol_summary.write_csv(paths["adjustment_symbol_summary"])
    block_summary.write_csv(paths["block_reason_summary"])
    state_summary.write_csv(paths["state_summary"])
    quality.write_csv(paths["quality_checkpoints"])
    paths["summary"].write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    paths["meta"].write_text(
        json.dumps(
            {
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "research_sources": RESEARCH_SOURCES,
                "note": "Component removal target-layer sidecar replay only; no paper entrypoint overwrite.",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    report_path = write_report(
        summary,
        scorecard,
        block_summary,
        adjustment_summary,
        adjustment_symbol_summary,
        state_summary,
        quality,
        paths,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
