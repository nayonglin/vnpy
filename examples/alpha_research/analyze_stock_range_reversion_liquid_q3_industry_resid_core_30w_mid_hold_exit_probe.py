from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from math import sqrt
from pathlib import Path
from typing import Any

import polars as pl

import analyze_stock_range_reversion_liquid_q3_300k_lot_feasibility as lot
from analyze_stock_range_reversion_layer_attribution import load_panels
from analyze_stock_range_reversion_liquid_q3_300k_curve_smoothness_attribution import (
    build_drawdown_episodes,
    downside_vol,
)
from analyze_stock_range_reversion_liquid_q3_30w_high_return_shape_grid import (
    HIGH_RETURN_TARGET,
    MAX_DRAWDOWN_LIMIT,
    summarize_daily_extra,
    to_float,
)
from analyze_stock_range_reversion_liquid_q3_industry_resid_core_30w_loss_sample_attribution import (
    FOCUS_SCENARIOS,
    read_csv_with_symbol,
)
from analyze_stock_range_reversion_liquid_q3_industry_resid_core_30w_slow_rhythm_replay import (
    SOURCE_DIR,
    SOURCE_PREFIX,
)
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import NATIVE_RESULTS_DIR, TRADING_DAYS, pct
from generate_stock_range_reversion_liquid_q3_paper_tracking import markdown_table
from generate_stock_range_reversion_liquid_q3_paper_tracking_v3_exante_adv_quality import build_exec_info


OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_industry_resid_core_30w_mid_hold_exit_probe_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_industry_resid_core_30w_mid_hold_exit_probe_v1"

PRIMARY_SCENARIO: str = "industry_resid_core_h10_top8_gross70_ind2"
CANDIDATE_BASE_SCENARIO: str = "industry_resid_core_h10_top5_gross70_ind1"
ROLLING_WINDOW_DAYS: int = 252
ROLLING_STEP_DAYS: int = 21

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "A Mean Reversion Strategy from First Principles Thinking",
        "https://www.quantitativo.com/p/a-mean-reversion-strategy-from-first",
    ),
    (
        "Optimal Mean Reversion Trading with Transaction Costs and Stop-Loss Exit",
        "https://arxiv.org/abs/1411.5062",
    ),
    (
        "Mean Reversion Trading with Sequential Deadlines and Transaction Costs",
        "https://arxiv.org/abs/1707.03498",
    ),
    (
        "Short-term reversals, returns to liquidity provision and immediacy costs",
        "https://www.sciencedirect.com/science/article/pii/S0378426622000309",
    ),
    (
        "GitHub mean-reversion-trading topic",
        "https://github.com/topics/mean-reversion-trading",
    ),
)


@dataclass(frozen=True)
class MidHoldRule:
    name: str
    description: str
    kind: str
    trigger_age: int | None = None
    prior_cum_lte: float | None = None
    prior_max_lt: float | None = None
    prior_new_low: bool = False
    reduced_scale: float = 1.0
    cooldown_until_absent: bool = False
    decay_start_age: int | None = None
    decay_end_age: int | None = None
    floor_scale: float = 1.0


@dataclass
class PositionState:
    days_held: int = 0
    cum_ret: float = 0.0
    max_cum_ret: float = 0.0
    min_cum_ret: float = 0.0
    episode_scale: float = 1.0
    trigger_name: str = ""


MID_HOLD_RULES: tuple[MidHoldRule, ...] = (
    MidHoldRule(
        name="base_rerun",
        description="不做中段持仓调整；用于复现源30万整手回放。",
        kind="base",
    ),
    MidHoldRule(
        name="age4_unrecovered_half",
        description="第4个持仓日开始，若此前开盘到开盘累计收益仍<=0，则该episode目标权重降到50%。",
        kind="once",
        trigger_age=4,
        prior_cum_lte=0.0,
        reduced_scale=0.50,
    ),
    MidHoldRule(
        name="age4_unrecovered_exit",
        description="第4个持仓日开始，若此前累计收益仍<=0，则退出，并在源目标连续入选期间不重新买回。",
        kind="once",
        trigger_age=4,
        prior_cum_lte=0.0,
        reduced_scale=0.0,
        cooldown_until_absent=True,
    ),
    MidHoldRule(
        name="age6_unrecovered_half",
        description="第6个持仓日开始，若此前累计收益仍<=0，则该episode目标权重降到50%。",
        kind="once",
        trigger_age=6,
        prior_cum_lte=0.0,
        reduced_scale=0.50,
    ),
    MidHoldRule(
        name="age6_unrecovered_exit",
        description="第6个持仓日开始，若此前累计收益仍<=0，则退出，并在源目标连续入选期间不重新买回。",
        kind="once",
        trigger_age=6,
        prior_cum_lte=0.0,
        reduced_scale=0.0,
        cooldown_until_absent=True,
    ),
    MidHoldRule(
        name="age4_no_bounce1pct_half",
        description="第4个持仓日开始，若此前最大开盘到开盘反弹不足1%，且当前累计收益<=0，则该episode降到50%。",
        kind="once",
        trigger_age=4,
        prior_cum_lte=0.0,
        prior_max_lt=0.01,
        reduced_scale=0.50,
    ),
    MidHoldRule(
        name="age8_no_bounce1pct_exit",
        description="第8个持仓日开始，若此前最大开盘到开盘反弹不足1%，则退出，并在源目标连续入选期间不重新买回。",
        kind="once",
        trigger_age=8,
        prior_max_lt=0.01,
        reduced_scale=0.0,
        cooldown_until_absent=True,
    ),
    MidHoldRule(
        name="age4_new_low_half",
        description="第4个持仓日开始，若此前累计收益仍为负且处于该episode新低附近，则该episode降到50%。",
        kind="once",
        trigger_age=4,
        prior_cum_lte=0.0,
        prior_new_low=True,
        reduced_scale=0.50,
    ),
    MidHoldRule(
        name="age_decay4_10_floor70",
        description="第4-10个持仓日线性衰减，目标权重从100%降到70%，之后保持70%。",
        kind="decay",
        decay_start_age=4,
        decay_end_age=10,
        floor_scale=0.70,
    ),
    MidHoldRule(
        name="age_decay4_10_floor50",
        description="第4-10个持仓日线性衰减，目标权重从100%降到50%，之后保持50%。",
        kind="decay",
        decay_start_age=4,
        decay_end_age=10,
        floor_scale=0.50,
    ),
)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def annualized_vol(values: list[float]) -> float:
    clean = [value for value in values if value == value]
    if len(clean) < 2:
        return 0.0
    mean = sum(clean) / len(clean)
    variance = sum((value - mean) ** 2 for value in clean) / (len(clean) - 1)
    return sqrt(max(variance, 0.0)) * sqrt(TRADING_DAYS)


def annualized_sharpe(values: list[float]) -> float:
    clean = [value for value in values if value == value]
    if len(clean) < 2:
        return 0.0
    mean = sum(clean) / len(clean)
    variance = sum((value - mean) ** 2 for value in clean) / (len(clean) - 1)
    if variance <= 0:
        return 0.0
    return mean / sqrt(variance) * sqrt(TRADING_DAYS)


def max_drawdown_from_returns(values: list[float]) -> float:
    equity = 1.0
    peak = 1.0
    worst = 0.0
    for value in values:
        equity *= 1.0 + value
        peak = max(peak, equity)
        worst = min(worst, equity / peak - 1.0)
    return worst


def compound_return(values: list[float]) -> float:
    equity = 1.0
    for value in values:
        equity *= 1.0 + value
    return equity - 1.0


def calc_decay_scale(rule: MidHoldRule, holding_age: int) -> float:
    start = rule.decay_start_age or 0
    end = rule.decay_end_age or start
    if holding_age < start:
        return 1.0
    if holding_age >= end or end <= start:
        return rule.floor_scale
    progress = (holding_age - start) / (end - start)
    return 1.0 - progress * (1.0 - rule.floor_scale)


def should_trigger_once(rule: MidHoldRule, state: PositionState, holding_age: int) -> bool:
    if rule.trigger_age is not None and holding_age < rule.trigger_age:
        return False
    if rule.prior_cum_lte is not None and state.cum_ret > rule.prior_cum_lte:
        return False
    if rule.prior_max_lt is not None and state.max_cum_ret >= rule.prior_max_lt:
        return False
    if rule.prior_new_low and state.cum_ret > state.min_cum_ret + 1e-12:
        return False
    return True


def scale_for_symbol(
    rule: MidHoldRule,
    symbol: str,
    prev_shares: int,
    raw_target_present: bool,
    states: dict[str, PositionState],
    cooldown_symbols: set[str],
) -> tuple[float, str, int, float, float, float]:
    if rule.kind == "base" or prev_shares <= 0:
        return 1.0, "", 1, 0.0, 0.0, 0.0
    state = states.get(symbol, PositionState())
    holding_age = state.days_held + 1
    if symbol in cooldown_symbols and raw_target_present:
        return 0.0, "cooldown_until_absent", holding_age, state.cum_ret, state.max_cum_ret, state.min_cum_ret
    if rule.kind == "decay":
        scale = calc_decay_scale(rule, holding_age)
        trigger = "age_decay" if scale < 0.999999 else ""
        return scale, trigger, holding_age, state.cum_ret, state.max_cum_ret, state.min_cum_ret
    if state.trigger_name:
        return state.episode_scale, state.trigger_name, holding_age, state.cum_ret, state.max_cum_ret, state.min_cum_ret
    if rule.kind == "once" and should_trigger_once(rule, state, holding_age):
        trigger = rule.name
        return rule.reduced_scale, trigger, holding_age, state.cum_ret, state.max_cum_ret, state.min_cum_ret
    return 1.0, "", holding_age, state.cum_ret, state.max_cum_ret, state.min_cum_ret


def replay_lot_account_with_mid_hold_rule(
    base_scenario: str,
    rule: MidHoldRule,
    target_maps: dict[Any, dict[str, dict[str, Any]]],
    dates: list[Any],
    exec_info: dict[tuple[Any, str], Any],
) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    actual_shares: dict[str, int] = {}
    states: dict[str, PositionState] = {}
    cooldown_symbols: set[str] = set()
    order_rows: list[dict[str, Any]] = []
    daily_rows: list[dict[str, Any]] = []
    curve_rows: list[dict[str, Any]] = []
    scaled_target_rows: list[dict[str, Any]] = []
    equity_bps = 1.0
    equity_min_fee = 1.0
    peak_bps = 1.0
    peak_min_fee = 1.0
    one_way_cost = lot.ROUNDTRIP_COST_BPS / 2.0 / 10000.0

    for current_date in dates:
        raw_target = target_maps.get(current_date, {})
        for symbol in list(cooldown_symbols):
            if symbol not in raw_target:
                cooldown_symbols.remove(symbol)

        target: dict[str, dict[str, Any]] = {}
        daily_scaled_rows = 0
        daily_exit_lock_rows = 0
        daily_cooldown_rows = 0
        daily_target_base_weight = 0.0
        daily_target_controlled_weight = 0.0
        symbols = set(actual_shares) | set(raw_target)

        for symbol in sorted(raw_target):
            row = dict(raw_target[symbol])
            base_weight = to_float(row.get("target_weight"))
            scale, trigger, holding_age, prior_cum, prior_max, prior_min = scale_for_symbol(
                rule,
                symbol,
                int(actual_shares.get(symbol, 0)),
                True,
                states,
                cooldown_symbols,
            )
            if trigger == rule.name and rule.kind == "once":
                state = states.setdefault(symbol, PositionState())
                state.episode_scale = scale
                state.trigger_name = trigger
                if rule.cooldown_until_absent and scale <= 0:
                    cooldown_symbols.add(symbol)
            controlled_weight = base_weight * scale
            row.update(
                {
                    "base_scenario": base_scenario,
                    "mid_hold_rule_name": rule.name,
                    "mid_hold_rule_description": rule.description,
                    "base_target_weight": base_weight,
                    "target_weight": controlled_weight,
                    "mid_hold_scale": scale,
                    "mid_hold_trigger": trigger,
                    "mid_hold_holding_age": holding_age,
                    "mid_hold_prior_cum_ret": prior_cum,
                    "mid_hold_prior_max_cum_ret": prior_max,
                    "mid_hold_prior_min_cum_ret": prior_min,
                    "target_amount_cny": controlled_weight * lot.ACCOUNT_SIZE_CNY,
                }
            )
            target[symbol] = row
            scaled_target_rows.append(row)
            daily_target_base_weight += base_weight
            daily_target_controlled_weight += controlled_weight
            if scale < 0.999999:
                daily_scaled_rows += 1
            if trigger == "cooldown_until_absent":
                daily_cooldown_rows += 1
            if scale <= 0 and trigger:
                daily_exit_lock_rows += 1

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
            target_amount = target_weight * lot.ACCOUNT_SIZE_CNY
            prev_shares = int(actual_shares.get(symbol, 0))
            target_shares = lot.floor_to_lot_shares(target_amount, trade_open)
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
            status, blocked_reason = lot.classify_order(side, info)
            adv_turnover = info.adv_turnover_for_cap if info is not None else None
            cap_amount = (
                lot.MAX_PARTICIPATION_ADV20 * adv_turnover if adv_turnover is not None and adv_turnover > 0 else None
            )
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
                    "scenario": f"{base_scenario}_{rule.name}",
                    "base_scenario": base_scenario,
                    "mid_hold_rule_name": rule.name,
                    "mid_hold_rule_description": rule.description,
                    "account_size_cny": lot.ACCOUNT_SIZE_CNY,
                    "symbol": symbol,
                    "code_name": info.code_name if info else "",
                    "industry": target_row.get("industry") or "",
                    "side": side,
                    "status": status,
                    "blocked_reason": blocked_reason,
                    "prev_shares": int(item["prev_shares"]),
                    "base_target_weight": target_row.get("base_target_weight"),
                    "target_weight": item["target_weight"],
                    "mid_hold_scale": target_row.get("mid_hold_scale"),
                    "mid_hold_trigger": target_row.get("mid_hold_trigger"),
                    "mid_hold_holding_age": target_row.get("mid_hold_holding_age"),
                    "mid_hold_prior_cum_ret": target_row.get("mid_hold_prior_cum_ret"),
                    "target_amount_cny": item["target_amount"],
                    "target_shares": int(item["target_shares"]),
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
        next_states: dict[str, PositionState] = {}
        for symbol, shares in actual_shares.items():
            info = exec_info.get((current_date, symbol))
            if info is None or info.trade_open <= 0:
                missing_return_amount += 0.0
                daily_ret = 0.0
                amount = 0.0
            else:
                amount = shares * info.trade_open
                daily_ret = to_float(info.daily_ret)
                actual_market_value += amount
                gross_ret += (amount / lot.ACCOUNT_SIZE_CNY) * daily_ret
            previous_state = states.get(symbol, PositionState()) if symbol in states else PositionState()
            if symbol not in states or int(actual_shares.get(symbol, 0)) <= 0:
                previous_state = PositionState()
            new_cum = (1.0 + previous_state.cum_ret) * (1.0 + daily_ret) - 1.0
            next_states[symbol] = PositionState(
                days_held=previous_state.days_held + 1,
                cum_ret=new_cum,
                max_cum_ret=max(previous_state.max_cum_ret, new_cum),
                min_cum_ret=min(previous_state.min_cum_ret, new_cum),
                episode_scale=previous_state.episode_scale,
                trigger_name=previous_state.trigger_name,
            )
        states = next_states

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
                "scenario": f"{base_scenario}_{rule.name}",
                "base_scenario": base_scenario,
                "mid_hold_rule_name": rule.name,
                "mid_hold_rule_description": rule.description,
                "account_size_cny": lot.ACCOUNT_SIZE_CNY,
                "target_symbol_count": target_symbol_count,
                "target_amount_sum_cny": target_amount_sum,
                "rounded_target_amount_sum_cny": rounded_target_amount_sum,
                "base_target_weight_sum": daily_target_base_weight,
                "controlled_target_weight_sum": daily_target_controlled_weight,
                "scaled_target_row_count": daily_scaled_rows,
                "exit_lock_target_row_count": daily_exit_lock_rows,
                "cooldown_target_row_count": daily_cooldown_rows,
                "zero_lot_target_count": zero_lot_target_count,
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
                "scenario": f"{base_scenario}_{rule.name}",
                "base_scenario": base_scenario,
                "mid_hold_rule_name": rule.name,
                "equity_bps_only": equity_bps,
                "equity_min_fee": equity_min_fee,
                "drawdown_bps_only": equity_bps / peak_bps - 1.0,
                "drawdown_min_fee": equity_min_fee / peak_min_fee - 1.0,
            }
        )

    return (
        pl.DataFrame(order_rows, infer_schema_length=None).sort(["date", "symbol", "side"])
        if order_rows
        else pl.DataFrame(),
        pl.DataFrame(daily_rows, infer_schema_length=None).sort("date") if daily_rows else pl.DataFrame(),
        pl.DataFrame(curve_rows, infer_schema_length=None).sort("date") if curve_rows else pl.DataFrame(),
        pl.DataFrame(scaled_target_rows, infer_schema_length=None).sort(["target_date", "symbol"])
        if scaled_target_rows
        else pl.DataFrame(),
    )


def summarize_variant(
    base_scenario: str,
    rule: MidHoldRule,
    orders: pl.DataFrame,
    daily: pl.DataFrame,
    scaled_targets: pl.DataFrame,
) -> dict[str, Any]:
    summary = lot.summarize_orders(orders, daily)
    summary = summarize_daily_extra(summary, daily)
    returns = [float(value) for value in daily["strategy_daily_ret_min_fee"].to_list()]
    scaled_days = daily.filter(pl.col("scaled_target_row_count") > 0).height
    exit_lock_days = daily.filter(pl.col("exit_lock_target_row_count") > 0).height
    cooldown_days = daily.filter(pl.col("cooldown_target_row_count") > 0).height
    latest_date = daily["date"].max()
    latest = daily.filter(pl.col("date") == latest_date).row(0, named=True)
    summary.update(
        {
            "scenario": f"{base_scenario}_{rule.name}",
            "base_scenario": base_scenario,
            "mid_hold_rule_name": rule.name,
            "mid_hold_rule_description": rule.description,
            "annualized_vol_min_fee": annualized_vol(returns),
            "downside_vol_min_fee": downside_vol(returns),
            "annualized_sharpe_check": annualized_sharpe(returns),
            "worst_daily_ret_min_fee": min(returns) if returns else 0.0,
            "scaled_target_days": scaled_days,
            "scaled_target_day_ratio": scaled_days / daily.height if daily.height else 0.0,
            "exit_lock_days": exit_lock_days,
            "exit_lock_day_ratio": exit_lock_days / daily.height if daily.height else 0.0,
            "cooldown_days": cooldown_days,
            "cooldown_day_ratio": cooldown_days / daily.height if daily.height else 0.0,
            "avg_scaled_rows": to_float(daily["scaled_target_row_count"].mean()),
            "avg_target_weight_retention": to_float(
                (
                    daily["controlled_target_weight_sum"].sum()
                    / daily["base_target_weight_sum"].sum()
                    if daily["base_target_weight_sum"].sum()
                    else 1.0
                )
            ),
            "latest_scaled_target_row_count": latest["scaled_target_row_count"],
            "latest_exit_lock_target_row_count": latest["exit_lock_target_row_count"],
            "latest_cooldown_target_row_count": latest["cooldown_target_row_count"],
        }
    )
    meta_cols = [
        "shape_horizon",
        "shape_top_k",
        "shape_basket_gross_weight",
        "shape_max_per_industry",
    ]
    if not scaled_targets.is_empty():
        meta = scaled_targets.select([col for col in meta_cols if col in scaled_targets.columns]).row(0, named=True)
        summary.update(meta)
    return summary


def add_base_deltas(summary: pl.DataFrame) -> pl.DataFrame:
    base = (
        summary.filter(pl.col("mid_hold_rule_name") == "base_rerun")
        .select(
            "base_scenario",
            pl.col("final_equity_min_fee").alias("base_final_equity_min_fee"),
            pl.col("total_return_min_fee").alias("base_total_return_min_fee"),
            pl.col("max_drawdown_min_fee").alias("base_max_drawdown_min_fee"),
            pl.col("sharpe_min_fee").alias("base_sharpe_min_fee"),
            pl.col("annualized_vol_min_fee").alias("base_annualized_vol_min_fee"),
            pl.col("downside_vol_min_fee").alias("base_downside_vol_min_fee"),
            pl.col("worst_daily_ret_min_fee").alias("base_worst_daily_ret_min_fee"),
            pl.col("avg_actual_gross_weight").alias("base_avg_actual_gross_weight"),
        )
    )
    return (
        summary.join(base, on="base_scenario", how="left")
        .with_columns(
            (pl.col("final_equity_min_fee") - pl.col("base_final_equity_min_fee")).alias("delta_final_equity_min_fee"),
            (pl.col("total_return_min_fee") - pl.col("base_total_return_min_fee")).alias("delta_total_return_min_fee"),
            (pl.col("max_drawdown_min_fee") - pl.col("base_max_drawdown_min_fee")).alias("delta_max_drawdown_min_fee"),
            (pl.col("sharpe_min_fee") - pl.col("base_sharpe_min_fee")).alias("delta_sharpe_min_fee"),
            (pl.col("annualized_vol_min_fee") - pl.col("base_annualized_vol_min_fee")).alias(
                "delta_annualized_vol_min_fee"
            ),
            (pl.col("downside_vol_min_fee") - pl.col("base_downside_vol_min_fee")).alias("delta_downside_vol_min_fee"),
            (pl.col("worst_daily_ret_min_fee") - pl.col("base_worst_daily_ret_min_fee")).alias(
                "delta_worst_daily_ret_min_fee"
            ),
            (pl.col("avg_actual_gross_weight") - pl.col("base_avg_actual_gross_weight")).alias(
                "delta_avg_actual_gross_weight"
            ),
        )
        .drop(
            [
                "base_final_equity_min_fee",
                "base_total_return_min_fee",
                "base_max_drawdown_min_fee",
                "base_sharpe_min_fee",
                "base_annualized_vol_min_fee",
                "base_downside_vol_min_fee",
                "base_worst_daily_ret_min_fee",
                "base_avg_actual_gross_weight",
            ]
        )
    )


def build_yearly(daily: pl.DataFrame) -> pl.DataFrame:
    if daily.is_empty():
        return pl.DataFrame()
    rows: list[dict[str, Any]] = []
    for key, frame in daily.with_columns(pl.col("date").dt.year().alias("year")).partition_by(
        ["base_scenario", "mid_hold_rule_name", "scenario", "year"], as_dict=True
    ).items():
        base_scenario, rule_name, scenario, year = key
        returns = [float(value) for value in frame.sort("date")["strategy_daily_ret_min_fee"].to_list()]
        rows.append(
            {
                "base_scenario": base_scenario,
                "mid_hold_rule_name": rule_name,
                "scenario": scenario,
                "year": year,
                "year_return_min_fee": compound_return(returns),
                "year_max_drawdown_min_fee": max_drawdown_from_returns(returns),
                "avg_actual_gross_weight": to_float(frame["actual_gross_weight"].mean()),
                "avg_actual_symbol_count": to_float(frame["actual_symbol_count"].mean()),
                "scaled_day_ratio": to_float((frame["scaled_target_row_count"] > 0).mean()),
                "exit_lock_day_ratio": to_float((frame["exit_lock_target_row_count"] > 0).mean()),
                "zero_lot_target_count": to_float(frame["zero_lot_target_count"].sum()),
                "target_symbol_count": to_float(frame["target_symbol_count"].sum()),
                "filled_amount_sum_cny": to_float(frame["filled_amount_sum_cny"].sum()),
            }
        )
    return pl.DataFrame(rows, infer_schema_length=None).with_columns(
        (pl.col("zero_lot_target_count") / pl.col("target_symbol_count")).fill_nan(0.0).alias(
            "zero_lot_target_ratio"
        )
    ).sort(["base_scenario", "mid_hold_rule_name", "year"])


def add_year_deltas(yearly: pl.DataFrame) -> pl.DataFrame:
    if yearly.is_empty():
        return yearly
    base = yearly.filter(pl.col("mid_hold_rule_name") == "base_rerun").select(
        "base_scenario",
        "year",
        pl.col("year_return_min_fee").alias("base_year_return_min_fee"),
        pl.col("year_max_drawdown_min_fee").alias("base_year_max_drawdown_min_fee"),
    )
    return yearly.join(base, on=["base_scenario", "year"], how="left").with_columns(
        (pl.col("year_return_min_fee") - pl.col("base_year_return_min_fee")).alias("delta_year_return_min_fee"),
        (pl.col("year_max_drawdown_min_fee") - pl.col("base_year_max_drawdown_min_fee")).alias(
            "delta_year_max_drawdown_min_fee"
        ),
    )


def build_year_scorecard(yearly: pl.DataFrame) -> pl.DataFrame:
    if yearly.is_empty():
        return pl.DataFrame()
    return (
        yearly.filter(pl.col("mid_hold_rule_name") != "base_rerun")
        .group_by(["base_scenario", "mid_hold_rule_name"])
        .agg(
            pl.len().alias("years"),
            (pl.col("delta_year_return_min_fee") > 0).sum().alias("improve_return_years"),
            (pl.col("delta_year_max_drawdown_min_fee") > 0).sum().alias("improve_drawdown_years"),
            (
                (pl.col("delta_year_return_min_fee") > 0) & (pl.col("delta_year_max_drawdown_min_fee") > 0)
            ).sum().alias("improve_both_years"),
            pl.col("delta_year_return_min_fee").mean().alias("avg_delta_year_return_min_fee"),
            pl.col("delta_year_max_drawdown_min_fee").mean().alias("avg_delta_year_max_drawdown_min_fee"),
        )
        .with_columns((pl.col("improve_both_years") / pl.col("years")).alias("improve_both_year_ratio"))
        .sort(["base_scenario", "mid_hold_rule_name"])
    )


def build_rolling_summary(daily: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
    if daily.is_empty():
        return pl.DataFrame(), pl.DataFrame()
    rolling_rows: list[dict[str, Any]] = []
    for key, frame in daily.sort("date").partition_by(["base_scenario", "mid_hold_rule_name", "scenario"], as_dict=True).items():
        base_scenario, rule_name, scenario = key
        rows = frame.to_dicts()
        for start_idx in range(0, max(0, len(rows) - ROLLING_WINDOW_DAYS + 1), ROLLING_STEP_DAYS):
            window = rows[start_idx : start_idx + ROLLING_WINDOW_DAYS]
            returns = [float(item["strategy_daily_ret_min_fee"]) for item in window]
            rolling_rows.append(
                {
                    "base_scenario": base_scenario,
                    "mid_hold_rule_name": rule_name,
                    "scenario": scenario,
                    "window_start": window[0]["date"],
                    "window_end": window[-1]["date"],
                    "window_days": len(window),
                    "rolling_return_min_fee": compound_return(returns),
                    "rolling_max_drawdown_min_fee": max_drawdown_from_returns(returns),
                    "rolling_sharpe_min_fee": annualized_sharpe(returns),
                }
            )
    rolling = pl.DataFrame(rolling_rows, infer_schema_length=None)
    if rolling.is_empty():
        return rolling, pl.DataFrame()
    base = rolling.filter(pl.col("mid_hold_rule_name") == "base_rerun").select(
        "base_scenario",
        "window_start",
        "window_end",
        pl.col("rolling_return_min_fee").alias("base_rolling_return_min_fee"),
        pl.col("rolling_max_drawdown_min_fee").alias("base_rolling_max_drawdown_min_fee"),
        pl.col("rolling_sharpe_min_fee").alias("base_rolling_sharpe_min_fee"),
    )
    rolling = rolling.join(base, on=["base_scenario", "window_start", "window_end"], how="left").with_columns(
        (pl.col("rolling_return_min_fee") - pl.col("base_rolling_return_min_fee")).alias(
            "delta_rolling_return_min_fee"
        ),
        (pl.col("rolling_max_drawdown_min_fee") - pl.col("base_rolling_max_drawdown_min_fee")).alias(
            "delta_rolling_max_drawdown_min_fee"
        ),
        (pl.col("rolling_sharpe_min_fee") - pl.col("base_rolling_sharpe_min_fee")).alias(
            "delta_rolling_sharpe_min_fee"
        ),
    )
    scorecard = (
        rolling.filter(pl.col("mid_hold_rule_name") != "base_rerun")
        .group_by(["base_scenario", "mid_hold_rule_name"])
        .agg(
            pl.len().alias("rolling_windows"),
            (pl.col("delta_rolling_return_min_fee") > 0).sum().alias("improve_return_windows"),
            (pl.col("delta_rolling_max_drawdown_min_fee") > 0).sum().alias("improve_drawdown_windows"),
            (
                (pl.col("delta_rolling_return_min_fee") > 0)
                & (pl.col("delta_rolling_max_drawdown_min_fee") > 0)
            ).sum().alias("improve_both_windows"),
            pl.col("delta_rolling_return_min_fee").mean().alias("avg_delta_rolling_return_min_fee"),
            pl.col("delta_rolling_max_drawdown_min_fee").mean().alias("avg_delta_rolling_max_drawdown_min_fee"),
            pl.col("delta_rolling_sharpe_min_fee").mean().alias("avg_delta_rolling_sharpe_min_fee"),
        )
        .with_columns((pl.col("improve_both_windows") / pl.col("rolling_windows")).alias("improve_both_window_ratio"))
        .sort(["base_scenario", "mid_hold_rule_name"])
    )
    return rolling, scorecard


def summarize_trigger_daily(daily: pl.DataFrame) -> pl.DataFrame:
    if daily.is_empty():
        return pl.DataFrame()
    return (
        daily.group_by(["base_scenario", "mid_hold_rule_name"])
        .agg(
            pl.len().alias("days"),
            (pl.col("scaled_target_row_count") > 0).sum().alias("scaled_days"),
            (pl.col("exit_lock_target_row_count") > 0).sum().alias("exit_lock_days"),
            (pl.col("cooldown_target_row_count") > 0).sum().alias("cooldown_days"),
            pl.col("scaled_target_row_count").sum().alias("scaled_target_rows"),
            pl.col("exit_lock_target_row_count").sum().alias("exit_lock_target_rows"),
            pl.col("cooldown_target_row_count").sum().alias("cooldown_target_rows"),
            pl.col("base_target_weight_sum").sum().alias("base_target_weight_sum"),
            pl.col("controlled_target_weight_sum").sum().alias("controlled_target_weight_sum"),
            pl.col("strategy_daily_ret_min_fee").sum().alias("net_return_sum"),
            pl.col("turnover_cost_ret_min_fee").sum().alias("cost_drag_sum"),
            pl.col("actual_gross_weight").mean().alias("avg_actual_gross_weight"),
        )
        .with_columns(
            (pl.col("scaled_days") / pl.col("days")).alias("scaled_day_ratio"),
            (pl.col("controlled_target_weight_sum") / pl.col("base_target_weight_sum")).alias(
                "target_weight_retention"
            ),
        )
        .sort(["base_scenario", "mid_hold_rule_name"])
    )


def build_quality(
    summary: pl.DataFrame,
    original_daily: pl.DataFrame,
    year_scorecard: pl.DataFrame,
    rolling_scorecard: pl.DataFrame,
) -> pl.DataFrame:
    rows: list[dict[str, Any]] = []

    def add(checkpoint: str, status: str, value: Any, expected: Any, note: str) -> None:
        rows.append(
            {
                "checkpoint": checkpoint,
                "status": status,
                "value": "" if value is None else str(value),
                "expected": "" if expected is None else str(expected),
                "note": note,
            }
        )

    add(
        "focus_scenario_count",
        "pass" if summary["base_scenario"].n_unique() == len(FOCUS_SCENARIOS) else "fail",
        summary["base_scenario"].n_unique(),
        len(FOCUS_SCENARIOS),
        "只运行四个代表形状。",
    )
    add(
        "mid_hold_rule_count",
        "pass" if summary["mid_hold_rule_name"].n_unique() == len(MID_HOLD_RULES) else "fail",
        summary["mid_hold_rule_name"].n_unique(),
        len(MID_HOLD_RULES),
        "只运行预注册中段路径规则。",
    )
    base = summary.filter(pl.col("mid_hold_rule_name") == "base_rerun").select(
        "base_scenario", "final_equity_min_fee"
    )
    original = original_daily.filter(pl.col("scenario").is_in(FOCUS_SCENARIOS)).group_by("scenario").agg(
        pl.col("equity_min_fee").last().alias("original_final_equity_min_fee")
    )
    compare = base.join(original, left_on="base_scenario", right_on="scenario", how="left").with_columns(
        (pl.col("final_equity_min_fee") - pl.col("original_final_equity_min_fee")).abs().alias("diff")
    )
    max_base_diff = to_float(compare["diff"].max()) if not compare.is_empty() else None
    add(
        "base_rerun_matches_source_replay",
        "pass" if max_base_diff is not None and max_base_diff <= 1e-12 else "fail",
        max_base_diff,
        "<=1e-12",
        "不调整版本必须复现源30万整手回放。",
    )
    improves_both = summary.filter(
        (pl.col("mid_hold_rule_name") != "base_rerun")
        & (pl.col("delta_total_return_min_fee") > 0)
        & (pl.col("delta_max_drawdown_min_fee") > 0)
    )
    add(
        "any_rule_improves_drawdown_and_return",
        "pass" if not improves_both.is_empty() else "warn",
        improves_both.height,
        ">0",
        "只有同时改善收益和回撤，才值得继续做稳定性反证。",
    )
    stable_year = year_scorecard.filter(pl.col("improve_both_year_ratio") >= 0.50)
    add(
        "any_rule_year_majority_improves_both",
        "pass" if not stable_year.is_empty() else "warn",
        stable_year.height,
        ">0",
        "年度同向改善过半才具备初步稳定性。",
    )
    stable_rolling = rolling_scorecard.filter(pl.col("improve_both_window_ratio") >= 0.50)
    add(
        "any_rule_rolling_majority_improves_both",
        "pass" if not stable_rolling.is_empty() else "warn",
        stable_rolling.height,
        ">0",
        "252日滚动窗口同向改善过半才继续。",
    )
    best_dd = summary.select(pl.col("max_drawdown_min_fee").max()).item()
    best_return = summary.select(pl.col("total_return_min_fee").max()).item()
    add(
        "best_drawdown_within_20pct",
        "pass" if best_dd >= MAX_DRAWDOWN_LIMIT else "warn",
        pct(best_dd),
        ">=-20%",
        "观察是否进入用户20%以内回撤目标。",
    )
    add(
        "high_return_target_seen",
        "pass" if best_return >= HIGH_RETURN_TARGET else "warn",
        pct(best_return),
        ">=100%",
        "观察是否保留30万高收益特征。",
    )
    add(
        "no_entry_signal_change",
        "pass",
        "mid-hold target scaling only",
        "mid-hold target scaling only",
        "不改变选股、行业上限、top_k、模型分数。",
    )
    return pl.DataFrame(rows)


def write_report(
    summary: pl.DataFrame,
    yearly: pl.DataFrame,
    year_scorecard: pl.DataFrame,
    rolling_scorecard: pl.DataFrame,
    drawdowns: pl.DataFrame,
    trigger_daily: pl.DataFrame,
    quality: pl.DataFrame,
    paths: dict[str, Path],
) -> Path:
    failed = quality.filter(pl.col("status") == "fail")
    warned = quality.filter(pl.col("status") == "warn")
    non_base = summary.filter(pl.col("mid_hold_rule_name") != "base_rerun")
    best_both = non_base.filter((pl.col("delta_total_return_min_fee") > 0) & (pl.col("delta_max_drawdown_min_fee") > 0))
    best_both = best_both.sort(["delta_total_return_min_fee", "delta_max_drawdown_min_fee"], descending=[True, True])
    best_dd = summary.sort(["max_drawdown_min_fee", "total_return_min_fee"], descending=[True, True]).row(0, named=True)
    best_return = summary.sort(["total_return_min_fee", "max_drawdown_min_fee"], descending=[True, True]).row(
        0, named=True
    )
    best_primary = non_base.filter(pl.col("base_scenario") == PRIMARY_SCENARIO).sort(
        ["delta_total_return_min_fee", "delta_max_drawdown_min_fee"], descending=[True, True]
    )
    primary_line = (
        "- 主低回撤场景无非基准规则。"
        if best_primary.is_empty()
        else (
            f"- 主低回撤场景收益改善最大：`{best_primary['mid_hold_rule_name'][0]}`，收益变化"
            f"`{pct(best_primary['delta_total_return_min_fee'][0])}`，回撤变化"
            f"`{pct(best_primary['delta_max_drawdown_min_fee'][0])}`，总收益"
            f"`{pct(best_primary['total_return_min_fee'][0])}`，最大回撤"
            f"`{pct(best_primary['max_drawdown_min_fee'][0])}`。"
        )
    )
    candidate_line = (
        "- 同时改善收益和回撤的规则：无。"
        if best_both.is_empty()
        else (
            f"- 同时改善收益和回撤的最佳规则：`{best_both['scenario'][0]}`，收益变化"
            f"`{pct(best_both['delta_total_return_min_fee'][0])}`，回撤变化"
            f"`{pct(best_both['delta_max_drawdown_min_fee'][0])}`，总收益"
            f"`{pct(best_both['total_return_min_fee'][0])}`，最大回撤"
            f"`{pct(best_both['max_drawdown_min_fee'][0])}`。"
        )
    )
    lines = [
        "# 股票震荡industry_resid_core 30万中段持仓退出/减仓探针 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前模式：day。",
        "- 当前研究线：股票震荡30万industry_resid_core独立研究线，不接入第78。",
        "- 本阶段性质：在源30万整手回放逻辑中加入预注册中段持仓路径规则；不改入场信号。",
        f"- 账户规模：`{lot.ACCOUNT_SIZE_CNY:,.0f}`元；最低佣金：`{lot.MIN_COMMISSION_CNY}`元；回撤目标参考：`20%`以内。",
        "- A/B判断：独立股票震荡研究，不触发第78 A/B。",
        "",
        "## 外部调研判断",
        "",
        "- 均值回归交易系统通常由入场、退出、时间约束和交易成本共同决定，单看入场信号容易误判。",
        "- 理论和工程实现都强调退出边界/有限持有期限；但传统硬止损可能截断反转收益，所以本阶段只做少量粗粒度路径规则。",
        "- 本阶段使用开盘前已知的episode历史收益路径触发，避免把最差中段事后切掉。",
        "",
        "参考资料：",
        *[f"- [{title}]({url})" for title, url in RESEARCH_SOURCES],
        "",
        "## 核心摘要",
        "",
        f"- 质量检查：fail `{failed.height}`项，warn `{warned.height}`项。",
        candidate_line,
        primary_line,
        f"- 最大回撤最浅：`{best_dd['scenario']}`，总收益`{pct(best_dd['total_return_min_fee'])}`，最大回撤`{pct(best_dd['max_drawdown_min_fee'])}`，Sharpe `{best_dd['sharpe_min_fee']:.3f}`。",
        f"- 总收益最高：`{best_return['scenario']}`，总收益`{pct(best_return['total_return_min_fee'])}`，最大回撤`{pct(best_return['max_drawdown_min_fee'])}`，Sharpe `{best_return['sharpe_min_fee']:.3f}`。",
        "",
        "## 全样本汇总",
        "",
        markdown_table(
            summary,
            [
                "base_scenario",
                "mid_hold_rule_name",
                "final_equity_min_fee",
                "total_return_min_fee",
                "max_drawdown_min_fee",
                "delta_total_return_min_fee",
                "delta_max_drawdown_min_fee",
                "sharpe_min_fee",
                "annualized_vol_min_fee",
                "downside_vol_min_fee",
                "worst_daily_ret_min_fee",
                "avg_actual_gross_weight",
                "avg_actual_symbol_count",
                "scaled_target_day_ratio",
                "exit_lock_day_ratio",
                "avg_target_weight_retention",
                "return_over_max_dd",
            ],
            max_rows=180,
        ),
        "",
        "## 年度稳定性",
        "",
        markdown_table(
            year_scorecard,
            [
                "base_scenario",
                "mid_hold_rule_name",
                "years",
                "improve_return_years",
                "improve_drawdown_years",
                "improve_both_years",
                "improve_both_year_ratio",
                "avg_delta_year_return_min_fee",
                "avg_delta_year_max_drawdown_min_fee",
            ],
            max_rows=180,
        ),
        "",
        "## 252日滚动稳定性",
        "",
        markdown_table(
            rolling_scorecard,
            [
                "base_scenario",
                "mid_hold_rule_name",
                "rolling_windows",
                "improve_return_windows",
                "improve_drawdown_windows",
                "improve_both_windows",
                "improve_both_window_ratio",
                "avg_delta_rolling_return_min_fee",
                "avg_delta_rolling_max_drawdown_min_fee",
                "avg_delta_rolling_sharpe_min_fee",
            ],
            max_rows=180,
        ),
        "",
        "## 触发强度",
        "",
        markdown_table(
            trigger_daily,
            [
                "base_scenario",
                "mid_hold_rule_name",
                "days",
                "scaled_days",
                "exit_lock_days",
                "cooldown_days",
                "scaled_target_rows",
                "exit_lock_target_rows",
                "target_weight_retention",
                "cost_drag_sum",
                "avg_actual_gross_weight",
            ],
            max_rows=180,
        ),
        "",
        "## 最大回撤段",
        "",
        markdown_table(
            drawdowns,
            [
                "base_scenario",
                "mid_hold_rule_name",
                "peak_date",
                "trough_date",
                "recovery_date",
                "recovered",
                "max_drawdown",
                "trading_days_to_trough",
                "trading_days_to_recovery_or_end",
                "avg_actual_gross_weight",
                "worst_daily_return",
            ],
            max_rows=120,
        ),
        "",
        "## 年度明细",
        "",
        markdown_table(
            yearly,
            [
                "base_scenario",
                "mid_hold_rule_name",
                "year",
                "year_return_min_fee",
                "year_max_drawdown_min_fee",
                "delta_year_return_min_fee",
                "delta_year_max_drawdown_min_fee",
                "avg_actual_gross_weight",
                "scaled_day_ratio",
                "exit_lock_day_ratio",
            ],
            max_rows=360,
        ),
        "",
        "## 质量检查",
        "",
        markdown_table(quality, ["checkpoint", "status", "value", "expected", "note"], max_rows=80),
        "",
        "## 结论",
        "",
        "- 若规则只是降低暴露但收益明显下降，则中段问题不能靠简单时间止损解决。",
        "- 若规则改善回撤但滚动/年度不过半，只能保留为风控监控线索，不能升级候选。",
        "- 若某规则同时提高收益、改善回撤，并且年度/滚动过半，再进入邻域和OOS反证。",
        "",
        "## 运行前过拟合反思",
        "",
        "- 判断：中等。",
        "- 原因：第329阶段已经指出中段亏损集中，本阶段容易事后裁剪；所以只测预注册粗规则，并加入年度/滚动反证。",
        "",
        "## 运行后过拟合反思",
        "",
        "- 判断：看是否跨形状、年度、滚动窗口一致；不能因单个规则全样本好看就升级。",
        "",
        "## 运行前继续价值反思",
        "",
        "- 判断：是。",
        "- 原因：亏损主通道明确在中段，且中段也是收益发动机，必须验证路径化退出能否保留弹性。",
        "",
        "## 运行后继续价值反思",
        "",
        "- 判断：如果没有规则通过年度/滚动多数同向改善，应停止简单时间止损，转向更本质的信号衰减/再确认。",
        "",
        "## 输出文件",
        "",
    ]
    for name, path in paths.items():
        lines.append(f"- `{name}`：`{path}`")
    paths["report"].write_text("\n".join(lines) + "\n", encoding="utf-8")
    return paths["report"]


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {
        "report": OUTPUT_DIR / f"{PREFIX}_report.md",
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.csv",
        "yearly": OUTPUT_DIR / f"{PREFIX}_yearly.csv",
        "year_scorecard": OUTPUT_DIR / f"{PREFIX}_year_scorecard.csv",
        "rolling": OUTPUT_DIR / f"{PREFIX}_rolling.csv",
        "rolling_scorecard": OUTPUT_DIR / f"{PREFIX}_rolling_scorecard.csv",
        "trigger_daily": OUTPUT_DIR / f"{PREFIX}_trigger_daily.csv",
        "drawdowns": OUTPUT_DIR / f"{PREFIX}_drawdowns.csv",
        "quality": OUTPUT_DIR / f"{PREFIX}_quality_checkpoints.csv",
        "scaled_targets": OUTPUT_DIR / f"{PREFIX}_scaled_targets.csv",
        "orders": OUTPUT_DIR / f"{PREFIX}_orders.csv",
        "daily": OUTPUT_DIR / f"{PREFIX}_daily.csv",
        "curves": OUTPUT_DIR / f"{PREFIX}_curves.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }

    target_weights = read_csv_with_symbol(SOURCE_DIR / f"{SOURCE_PREFIX}_target_weights.csv").filter(
        pl.col("scenario").is_in(FOCUS_SCENARIOS)
    )
    original_daily = pl.read_csv(SOURCE_DIR / f"{SOURCE_PREFIX}_daily.csv", try_parse_dates=True)
    stock_df, benchmark_df = load_panels()
    exec_info = build_exec_info(stock_df)

    summary_rows: list[dict[str, Any]] = []
    orders_frames: list[pl.DataFrame] = []
    daily_frames: list[pl.DataFrame] = []
    curve_frames: list[pl.DataFrame] = []
    scaled_target_frames: list[pl.DataFrame] = []
    drawdown_frames: list[pl.DataFrame] = []

    for base_scenario in FOCUS_SCENARIOS:
        scenario_targets = target_weights.filter(pl.col("scenario") == base_scenario).drop("scenario")
        target_maps = lot.build_target_maps(scenario_targets)
        dates = lot.build_tracking_dates(scenario_targets, benchmark_df)
        for rule in MID_HOLD_RULES:
            orders, daily, curves, scaled_targets = replay_lot_account_with_mid_hold_rule(
                base_scenario,
                rule,
                target_maps,
                dates,
                exec_info,
            )
            if not orders.is_empty():
                orders_frames.append(orders)
            if not daily.is_empty():
                daily_frames.append(daily)
                curve_frames.append(curves)
                scaled_target_frames.append(
                    scaled_targets.with_columns(pl.lit(f"{base_scenario}_{rule.name}").alias("scenario"))
                )
                summary_rows.append(summarize_variant(base_scenario, rule, orders, daily, scaled_targets))
                drawdown_frames.append(
                    build_drawdown_episodes(daily)
                    .head(5)
                    .with_columns(
                        pl.lit(f"{base_scenario}_{rule.name}").alias("scenario"),
                        pl.lit(base_scenario).alias("base_scenario"),
                        pl.lit(rule.name).alias("mid_hold_rule_name"),
                    )
                )

    summary = add_base_deltas(pl.DataFrame(summary_rows, infer_schema_length=None)).sort(
        ["base_scenario", "mid_hold_rule_name"]
    )
    orders_all = pl.concat(orders_frames, how="diagonal_relaxed") if orders_frames else pl.DataFrame()
    daily_all = pl.concat(daily_frames, how="diagonal_relaxed") if daily_frames else pl.DataFrame()
    curves_all = pl.concat(curve_frames, how="diagonal_relaxed") if curve_frames else pl.DataFrame()
    scaled_targets_all = (
        pl.concat(scaled_target_frames, how="diagonal_relaxed") if scaled_target_frames else pl.DataFrame()
    )
    drawdowns = pl.concat(drawdown_frames, how="diagonal_relaxed") if drawdown_frames else pl.DataFrame()
    yearly = add_year_deltas(build_yearly(daily_all))
    year_scorecard = build_year_scorecard(yearly)
    rolling, rolling_scorecard = build_rolling_summary(daily_all)
    trigger_daily = summarize_trigger_daily(daily_all)
    quality = build_quality(summary, original_daily, year_scorecard, rolling_scorecard)

    summary.write_csv(paths["summary"])
    yearly.write_csv(paths["yearly"])
    year_scorecard.write_csv(paths["year_scorecard"])
    rolling.write_csv(paths["rolling"])
    rolling_scorecard.write_csv(paths["rolling_scorecard"])
    trigger_daily.write_csv(paths["trigger_daily"])
    drawdowns.write_csv(paths["drawdowns"])
    quality.write_csv(paths["quality"])
    scaled_targets_all.write_csv(paths["scaled_targets"])
    orders_all.write_csv(paths["orders"])
    daily_all.write_csv(paths["daily"])
    curves_all.write_csv(paths["curves"])
    write_json(
        paths["meta"],
        {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "source_dir": str(SOURCE_DIR),
            "source_prefix": SOURCE_PREFIX,
            "account_size_cny": lot.ACCOUNT_SIZE_CNY,
            "focus_scenarios": FOCUS_SCENARIOS,
            "primary_scenario": PRIMARY_SCENARIO,
            "candidate_base_scenario": CANDIDATE_BASE_SCENARIO,
            "rolling_window_days": ROLLING_WINDOW_DAYS,
            "rolling_step_days": ROLLING_STEP_DAYS,
            "mid_hold_rules": [(item.name, item.description) for item in MID_HOLD_RULES],
            "research_sources": RESEARCH_SOURCES,
            "outputs": {key: str(path) for key, path in paths.items()},
        },
    )
    report_path = write_report(
        summary,
        yearly,
        year_scorecard,
        rolling_scorecard,
        drawdowns,
        trigger_daily,
        quality,
        paths,
    )
    print(f"report={report_path}")
    print(
        summary.select(
            [
                "base_scenario",
                "mid_hold_rule_name",
                "total_return_min_fee",
                "max_drawdown_min_fee",
                "delta_total_return_min_fee",
                "delta_max_drawdown_min_fee",
                "sharpe_min_fee",
            ]
        )
    )
    print(quality)


if __name__ == "__main__":
    main()
