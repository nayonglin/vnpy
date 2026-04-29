from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
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
from analyze_stock_range_reversion_liquid_q3_industry_resid_core_30w_slow_regime_attribution import (
    RESEARCH_SOURCES,
)
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import NATIVE_RESULTS_DIR, TRADING_DAYS, pct
from generate_stock_range_reversion_liquid_q3_paper_tracking import markdown_table
from generate_stock_range_reversion_liquid_q3_paper_tracking_v3_exante_adv_quality import build_exec_info


SOURCE_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_industry_resid_core_30w_replay_2018_2026"
).expanduser().resolve()
SOURCE_PREFIX: str = "stock_range_reversion_liquid_q3_industry_resid_core_30w_replay_v1"

OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_industry_resid_core_30w_slow_rhythm_replay_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_industry_resid_core_30w_slow_rhythm_replay_v1"

ACCOUNT_SIZE_CNY: float = lot.ACCOUNT_SIZE_CNY


@dataclass(frozen=True)
class SlowRhythm:
    name: str
    description: str


SLOW_RHYTHMS: tuple[SlowRhythm, ...] = (
    SlowRhythm("base_rerun", "不做慢节奏暴露调整；用于复现第308阶段代表场景。"),
    SlowRhythm("strategy_ret60_up_half", "若本变体前一日自身60日收益>=5%，下一目标日目标权重乘0.50。"),
    SlowRhythm("strategy_ret60_up_zero", "若本变体前一日自身60日收益>=5%，下一目标日目标权重乘0.00。"),
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


def bucket_ret60(value: float | None) -> str:
    if value is None or value != value:
        return "missing"
    if value >= 0.05:
        return "ret60_up"
    if value >= -0.05:
        return "ret60_flat"
    return "ret60_down"


def calc_prev_ret60(equity_history: list[float]) -> float | None:
    if len(equity_history) < 61:
        return None
    base = equity_history[-61]
    if base <= 0:
        return None
    return equity_history[-1] / base - 1.0


def scale_for_rhythm(rhythm_name: str, prev_strategy_ret60_state: str) -> float:
    if rhythm_name == "base_rerun":
        return 1.0
    if rhythm_name == "strategy_ret60_up_half":
        return 0.5 if prev_strategy_ret60_state == "ret60_up" else 1.0
    if rhythm_name == "strategy_ret60_up_zero":
        return 0.0 if prev_strategy_ret60_state == "ret60_up" else 1.0
    raise ValueError(f"Unknown slow rhythm: {rhythm_name}")


def replay_lot_account_with_slow_rhythm(
    scenario: str,
    rhythm: SlowRhythm,
    target_maps: dict[Any, dict[str, dict[str, Any]]],
    dates: list[Any],
    exec_info: dict[tuple[Any, str], Any],
) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    actual_shares: dict[str, int] = {}
    order_rows: list[dict[str, Any]] = []
    daily_rows: list[dict[str, Any]] = []
    curve_rows: list[dict[str, Any]] = []
    scaled_target_rows: list[dict[str, Any]] = []
    equity_bps = 1.0
    equity_min_fee = 1.0
    peak_bps = 1.0
    peak_min_fee = 1.0
    equity_history: list[float] = []
    one_way_cost = lot.ROUNDTRIP_COST_BPS / 2.0 / 10000.0

    for current_date in dates:
        prev_strategy_ret_60 = calc_prev_ret60(equity_history)
        prev_strategy_ret60_state = bucket_ret60(prev_strategy_ret_60)
        rhythm_scale = scale_for_rhythm(rhythm.name, prev_strategy_ret60_state)
        raw_target = target_maps.get(current_date, {})
        target: dict[str, dict[str, Any]] = {}
        for symbol, row in raw_target.items():
            current = dict(row)
            base_target_weight = to_float(current.get("target_weight"))
            current["base_scenario"] = scenario
            current["slow_rhythm_name"] = rhythm.name
            current["slow_rhythm_description"] = rhythm.description
            current["prev_strategy_ret_60"] = prev_strategy_ret_60
            current["prev_strategy_ret60_state"] = prev_strategy_ret60_state
            current["rhythm_scale"] = rhythm_scale
            current["base_target_weight"] = base_target_weight
            current["target_weight"] = base_target_weight * rhythm_scale
            current["target_amount_cny"] = current["target_weight"] * ACCOUNT_SIZE_CNY
            target[symbol] = current
            scaled_target_rows.append(current)

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
                    "scenario": f"{scenario}_{rhythm.name}",
                    "base_scenario": scenario,
                    "slow_rhythm_name": rhythm.name,
                    "account_size_cny": ACCOUNT_SIZE_CNY,
                    "symbol": symbol,
                    "code_name": info.code_name if info else "",
                    "industry": target_row.get("industry") or "",
                    "side": side,
                    "status": status,
                    "blocked_reason": blocked_reason,
                    "prev_shares": int(item["prev_shares"]),
                    "base_target_weight": target_row.get("base_target_weight"),
                    "target_weight": item["target_weight"],
                    "rhythm_scale": rhythm_scale,
                    "prev_strategy_ret_60": prev_strategy_ret_60,
                    "prev_strategy_ret60_state": prev_strategy_ret60_state,
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
        for symbol, shares in actual_shares.items():
            info = exec_info.get((current_date, symbol))
            if info is None or info.trade_open <= 0:
                missing_return_amount += 0.0
                continue
            amount = shares * info.trade_open
            actual_market_value += amount
            gross_ret += (amount / ACCOUNT_SIZE_CNY) * info.daily_ret

        cost_ret_bps = bps_cost_cny / ACCOUNT_SIZE_CNY
        cost_ret_min_fee = min_fee_cost_cny / ACCOUNT_SIZE_CNY if lot.APPLY_MIN_COMMISSION_STRESS else cost_ret_bps
        daily_ret_bps = gross_ret - cost_ret_bps
        daily_ret_min_fee = gross_ret - cost_ret_min_fee
        equity_bps *= 1.0 + daily_ret_bps
        equity_min_fee *= 1.0 + daily_ret_min_fee
        peak_bps = max(peak_bps, equity_bps)
        peak_min_fee = max(peak_min_fee, equity_min_fee)
        equity_history.append(equity_min_fee)
        daily_rows.append(
            {
                "date": current_date,
                "scenario": f"{scenario}_{rhythm.name}",
                "base_scenario": scenario,
                "slow_rhythm_name": rhythm.name,
                "account_size_cny": ACCOUNT_SIZE_CNY,
                "prev_strategy_ret_60": prev_strategy_ret_60,
                "prev_strategy_ret60_state": prev_strategy_ret60_state,
                "rhythm_scale": rhythm_scale,
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
                "scenario": f"{scenario}_{rhythm.name}",
                "base_scenario": scenario,
                "slow_rhythm_name": rhythm.name,
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
    rhythm: SlowRhythm,
    orders: pl.DataFrame,
    daily: pl.DataFrame,
    scaled_targets: pl.DataFrame,
) -> dict[str, Any]:
    summary = lot.summarize_orders(orders, daily)
    summary = summarize_daily_extra(summary, daily)
    returns = [float(value) for value in daily["strategy_daily_ret_min_fee"].to_list()]
    scaled_days = daily.filter(pl.col("rhythm_scale") < 0.999999).height
    ret60_up_days = daily.filter(pl.col("prev_strategy_ret60_state") == "ret60_up").height
    ret60_down_days = daily.filter(pl.col("prev_strategy_ret60_state") == "ret60_down").height
    latest_date = daily["date"].max()
    latest = daily.filter(pl.col("date") == latest_date).row(0, named=True)
    summary.update(
        {
            "scenario": f"{base_scenario}_{rhythm.name}",
            "base_scenario": base_scenario,
            "slow_rhythm_name": rhythm.name,
            "slow_rhythm_description": rhythm.description,
            "annualized_vol_min_fee": annualized_vol(returns),
            "downside_vol_min_fee": downside_vol(returns),
            "annualized_sharpe_check": annualized_sharpe(returns),
            "worst_daily_ret_min_fee": min(returns) if returns else 0.0,
            "avg_rhythm_scale": to_float(daily["rhythm_scale"].mean()) if not daily.is_empty() else 1.0,
            "scaled_target_days": scaled_days,
            "scaled_target_day_ratio": scaled_days / daily.height if daily.height else 0.0,
            "ret60_up_target_days": ret60_up_days,
            "ret60_up_target_day_ratio": ret60_up_days / daily.height if daily.height else 0.0,
            "ret60_down_target_days": ret60_down_days,
            "ret60_down_target_day_ratio": ret60_down_days / daily.height if daily.height else 0.0,
            "latest_rhythm_scale": latest["rhythm_scale"],
            "latest_prev_strategy_ret_60": latest["prev_strategy_ret_60"],
            "latest_prev_strategy_ret60_state": latest["prev_strategy_ret60_state"],
        }
    )
    meta_cols = [
        "shape_horizon",
        "shape_top_k",
        "shape_basket_gross_weight",
        "shape_max_per_industry",
    ]
    meta = scaled_targets.select(meta_cols).row(0, named=True)
    summary.update(meta)
    return summary


def add_base_deltas(summary: pl.DataFrame) -> pl.DataFrame:
    base = (
        summary.filter(pl.col("slow_rhythm_name") == "base_rerun")
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
    return (
        daily.with_columns(pl.col("date").dt.year().alias("year"))
        .group_by(["base_scenario", "slow_rhythm_name", "scenario", "year"])
        .agg(
            ((1 + pl.col("strategy_daily_ret_min_fee")).product() - 1).alias("year_return_min_fee"),
            pl.col("drawdown_min_fee").min().alias("year_curve_drawdown_min_fee"),
            pl.col("actual_gross_weight").mean().alias("avg_actual_gross_weight"),
            pl.col("actual_symbol_count").mean().alias("avg_actual_symbol_count"),
            pl.col("rhythm_scale").mean().alias("avg_rhythm_scale"),
            (pl.col("rhythm_scale") < 0.999999).mean().alias("scaled_day_ratio"),
            pl.col("zero_lot_target_count").sum().alias("zero_lot_target_count"),
            pl.col("target_symbol_count").sum().alias("target_symbol_count"),
            pl.col("filled_amount_sum_cny").sum().alias("filled_amount_sum_cny"),
        )
        .with_columns(
            (pl.col("zero_lot_target_count") / pl.col("target_symbol_count")).fill_nan(0.0).alias(
                "zero_lot_target_ratio"
            )
        )
        .sort(["base_scenario", "slow_rhythm_name", "year"])
    )


def summarize_state_daily(daily: pl.DataFrame) -> pl.DataFrame:
    if daily.is_empty():
        return pl.DataFrame()
    return (
        daily.group_by(["base_scenario", "slow_rhythm_name", "prev_strategy_ret60_state"])
        .agg(
            pl.len().alias("days"),
            pl.col("strategy_daily_ret_min_fee").sum().alias("net_return_sum"),
            ((1 + pl.col("strategy_daily_ret_min_fee")).product() - 1).alias("compounded_return"),
            pl.col("strategy_daily_ret_min_fee").mean().alias("avg_daily_ret"),
            pl.col("strategy_daily_ret_min_fee").min().alias("worst_daily_ret"),
            (pl.col("strategy_daily_ret_min_fee") > 0).mean().alias("daily_win_rate"),
            pl.col("actual_gross_weight").mean().alias("avg_actual_gross_weight"),
            pl.col("actual_symbol_count").mean().alias("avg_actual_symbol_count"),
            pl.col("rhythm_scale").mean().alias("avg_rhythm_scale"),
            pl.col("turnover_cost_ret_min_fee").sum().alias("cost_drag_sum"),
        )
        .sort(["base_scenario", "slow_rhythm_name", "prev_strategy_ret60_state"])
    )


def build_quality(summary: pl.DataFrame, original_daily: pl.DataFrame) -> pl.DataFrame:
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
        "只运行第316阶段以来的四个代表形状，避免扩散扫参。",
    )
    add(
        "slow_rhythm_count",
        "pass" if summary["slow_rhythm_name"].n_unique() == len(SLOW_RHYTHMS) else "fail",
        summary["slow_rhythm_name"].n_unique(),
        len(SLOW_RHYTHMS),
        "只运行预注册的慢节奏规则。",
    )
    base = summary.filter(pl.col("slow_rhythm_name") == "base_rerun").select("base_scenario", "final_equity_min_fee")
    original = original_daily.filter(pl.col("scenario").is_in(FOCUS_SCENARIOS)).group_by("scenario").agg(
        pl.col("equity_min_fee").last().alias("original_final_equity_min_fee")
    )
    compare = base.join(original, left_on="base_scenario", right_on="scenario", how="left").with_columns(
        (pl.col("final_equity_min_fee") - pl.col("original_final_equity_min_fee")).abs().alias("diff")
    )
    max_base_diff = to_float(compare["diff"].max()) if not compare.is_empty() else None
    add(
        "base_rerun_matches_stage308",
        "pass" if max_base_diff is not None and max_base_diff <= 1e-12 else "fail",
        max_base_diff,
        "<=1e-12",
        "不调整变体必须复现第308阶段结果。",
    )
    best_dd = summary.select(pl.col("max_drawdown_min_fee").max()).item()
    best_return = summary.select(pl.col("total_return_min_fee").max()).item()
    improves_both = summary.filter(
        (pl.col("slow_rhythm_name") != "base_rerun")
        & (pl.col("delta_total_return_min_fee") > 0)
        & (pl.col("delta_max_drawdown_min_fee") > 0)
    )
    add(
        "any_slow_rhythm_improves_drawdown_and_return",
        "pass" if not improves_both.is_empty() else "warn",
        improves_both.height,
        ">0",
        "只有同时提高收益并改善回撤，才值得继续做稳健性反证。",
    )
    add(
        "best_drawdown_within_20pct",
        "pass" if best_dd >= MAX_DRAWDOWN_LIMIT else "warn",
        pct(best_dd),
        ">=-20%",
        "若没有进入20%以内，本阶段不能形成30万高收益候选。",
    )
    add(
        "high_return_target_seen",
        "pass" if best_return >= HIGH_RETURN_TARGET else "warn",
        pct(best_return),
        ">=100%",
        "用户目标是30万本金下高收益，需观察慢节奏是否过度牺牲收益。",
    )
    add(
        "path_dependent_state",
        "pass",
        "variant own previous equity",
        "variant own previous equity",
        "每天使用该变体自身截至前一日的权益曲线计算60日状态。",
    )
    add(
        "no_signal_threshold_change",
        "pass",
        "only target exposure scaling",
        "only target exposure scaling",
        "本阶段不改变选股信号、模型分数、top_k、持有期或行业上限。",
    )
    return pl.DataFrame(rows)


def write_report(
    summary: pl.DataFrame,
    yearly: pl.DataFrame,
    drawdowns: pl.DataFrame,
    state_daily: pl.DataFrame,
    quality: pl.DataFrame,
    paths: dict[str, Path],
) -> Path:
    report_path = paths["report"]
    failed = quality.filter(pl.col("status") == "fail")
    warned = quality.filter(pl.col("status") == "warn")
    pass_dd = summary.filter(pl.col("max_drawdown_min_fee") >= MAX_DRAWDOWN_LIMIT).sort(
        ["total_return_min_fee", "sharpe_min_fee"], descending=[True, True]
    )
    best_dd = summary.sort(["max_drawdown_min_fee", "total_return_min_fee"], descending=[True, True]).row(0, named=True)
    best_return = summary.sort(["total_return_min_fee", "max_drawdown_min_fee"], descending=[True, True]).row(
        0, named=True
    )
    best_delta = summary.filter(pl.col("slow_rhythm_name") != "base_rerun").sort(
        ["delta_max_drawdown_min_fee", "delta_total_return_min_fee"], descending=[True, True]
    )
    best_delta_row = best_delta.row(0, named=True) if not best_delta.is_empty() else None
    best_both = summary.filter(
        (pl.col("slow_rhythm_name") != "base_rerun")
        & (pl.col("delta_total_return_min_fee") > 0)
        & (pl.col("delta_max_drawdown_min_fee") > 0)
    ).sort(["total_return_min_fee", "max_drawdown_min_fee"], descending=[True, True])
    candidate_line = (
        "- 同时改善收益和回撤的慢节奏变体：无。"
        if best_both.is_empty()
        else (
            f"- 同时改善收益和回撤的最佳变体：`{best_both['scenario'][0]}`，总收益"
            f"`{pct(best_both['total_return_min_fee'][0])}`，最大回撤"
            f"`{pct(best_both['max_drawdown_min_fee'][0])}`，收益变化"
            f"`{pct(best_both['delta_total_return_min_fee'][0])}`，回撤变化"
            f"`{pct(best_both['delta_max_drawdown_min_fee'][0])}`。"
        )
    )
    delta_line = (
        "- 相对基准回撤改善最大：无。"
        if best_delta_row is None
        else (
            f"- 相对基准回撤改善最大：`{best_delta_row['scenario']}`，回撤改善"
            f"`{pct(best_delta_row['delta_max_drawdown_min_fee'])}`，收益变化"
            f"`{pct(best_delta_row['delta_total_return_min_fee'])}`。"
        )
    )
    lines = [
        "# 股票震荡industry_resid_core 30万路径依赖慢节奏暴露回放 v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前模式：day。",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：固定第308阶段信号和四个代表组合形状，只测试第319阶段归因指向的策略自身60日收益慢节奏暴露。",
        f"- 账户规模：`{ACCOUNT_SIZE_CNY:,.0f}`元；用户回撤目标：`20%`以内；高收益参考目标：`100%`以上。",
        "- A/B判断：股票震荡独立研究，不接入第78，不触发A/B。",
        "",
        "## 外部调研判断",
        "",
        "- 波动目标/风险预算在业界常用于降低状态切换下的组合风险，但需要平滑、低频和成本约束。",
        "- 第319阶段显示最坏状态不是弱市场本身，而是策略自身前60日刚上涨后的阶段；这更像均值回归收益节奏的拥挤/衰减。",
        "- 因此本阶段采用路径依赖状态：每天只使用该变体自己截至前一日的权益曲线，不用未来结果，也不改alpha。",
        "",
        "参考资料：",
        *[f"- [{title}]({url})" for title, url in RESEARCH_SOURCES],
        "",
        "## 核心摘要",
        "",
        "本阶段只回答一个问题：第319阶段识别的`prev_strategy_ret60_state=ret60_up`，是否能做成可交易的慢节奏暴露控制。",
        f"- 回撤20%以内候选：{'无' if pass_dd.is_empty() else pass_dd['scenario'][0]}",
        f"- 最大回撤最浅：`{best_dd['scenario']}`，总收益`{pct(best_dd['total_return_min_fee'])}`，最大回撤`{pct(best_dd['max_drawdown_min_fee'])}`，Sharpe `{best_dd['sharpe_min_fee']:.3f}`。",
        f"- 总收益最高：`{best_return['scenario']}`，总收益`{pct(best_return['total_return_min_fee'])}`，最大回撤`{pct(best_return['max_drawdown_min_fee'])}`，Sharpe `{best_return['sharpe_min_fee']:.3f}`。",
        candidate_line,
        delta_line,
        f"- 质量检查：fail `{failed.height}`项，warn `{warned.height}`项。",
        "",
        "## 场景汇总",
        "",
        markdown_table(
            summary,
            [
                "base_scenario",
                "slow_rhythm_name",
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
                "avg_rhythm_scale",
                "scaled_target_day_ratio",
                "ret60_up_target_day_ratio",
                "zero_lot_target_ratio",
                "latest_exposure_capture_ratio",
                "return_over_max_dd",
            ],
            max_rows=120,
        ),
        "",
        "## 最大回撤段",
        "",
        markdown_table(
            drawdowns,
            [
                "base_scenario",
                "slow_rhythm_name",
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
            max_rows=80,
        ),
        "",
        "## 策略自身60日状态拆分",
        "",
        markdown_table(
            state_daily,
            [
                "base_scenario",
                "slow_rhythm_name",
                "prev_strategy_ret60_state",
                "days",
                "net_return_sum",
                "compounded_return",
                "avg_daily_ret",
                "worst_daily_ret",
                "daily_win_rate",
                "avg_actual_gross_weight",
                "avg_actual_symbol_count",
                "avg_rhythm_scale",
                "cost_drag_sum",
            ],
            max_rows=160,
        ),
        "",
        "## 年度拆分",
        "",
        markdown_table(
            yearly,
            [
                "base_scenario",
                "slow_rhythm_name",
                "year",
                "year_return_min_fee",
                "year_curve_drawdown_min_fee",
                "avg_actual_gross_weight",
                "avg_actual_symbol_count",
                "avg_rhythm_scale",
                "scaled_day_ratio",
                "zero_lot_target_ratio",
            ],
            max_rows=260,
        ),
        "",
        "## 质量检查",
        "",
        markdown_table(quality, ["checkpoint", "status", "value", "expected", "note"], max_rows=80),
        "",
        "## 结论",
        "",
        "- 若慢节奏暴露能同时改善收益和回撤，下一步必须做分段/滚动反证，不能直接实盘。",
        "- 若收益改善来自少数年份或状态翻转后失效，则只保留为研究线索。",
        "",
        "## 运行前过拟合反思",
        "",
        "- 判断：否，但开始进入策略层验证，风险高于纯归因。",
        "- 原因：只使用第319阶段跨场景最强坏状态，且只测半仓/空仓两个粗粒度规则，不扫描阈值。",
        "",
        "## 运行后过拟合反思",
        "",
        "- 判断：需看是否跨四个代表场景一致，不允许只挑一个最好场景。",
        "- 原因：策略自身60日收益状态可能捕捉到真实收益节奏，也可能只是2022-2024样本内时序巧合。",
        "",
        "## 运行前继续价值反思",
        "",
        "- 判断：是。",
        "- 原因：第319阶段`ret60_up`在四个代表场景全部为负，且是前一日可见的低频状态。",
        "",
        "## 运行后继续价值反思",
        "",
        "- 判断：取决于本报告是否同时改善收益、回撤和分段稳定性。",
        "- 原因：慢节奏风控如果只降低暴露、不改善风险收益，就不应继续微调。",
        "",
        "## 输出文件",
        "",
    ]
    for name, path in paths.items():
        lines.append(f"- `{name}`：`{path}`")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {
        "report": OUTPUT_DIR / f"{PREFIX}_report.md",
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.csv",
        "yearly": OUTPUT_DIR / f"{PREFIX}_yearly.csv",
        "drawdowns": OUTPUT_DIR / f"{PREFIX}_drawdowns.csv",
        "state_daily": OUTPUT_DIR / f"{PREFIX}_state_daily.csv",
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
        for rhythm in SLOW_RHYTHMS:
            orders, daily, curves, scaled_targets = replay_lot_account_with_slow_rhythm(
                base_scenario,
                rhythm,
                target_maps,
                dates,
                exec_info,
            )
            if not orders.is_empty():
                orders_frames.append(orders)
            if not daily.is_empty():
                daily_frames.append(daily)
                curve_frames.append(curves)
                scaled_target_frames.append(scaled_targets.with_columns(pl.lit(f"{base_scenario}_{rhythm.name}").alias("scenario")))
                summary_rows.append(summarize_variant(base_scenario, rhythm, orders, daily, scaled_targets))
                drawdown_frames.append(
                    build_drawdown_episodes(daily)
                    .head(5)
                    .with_columns(
                        pl.lit(f"{base_scenario}_{rhythm.name}").alias("scenario"),
                        pl.lit(base_scenario).alias("base_scenario"),
                        pl.lit(rhythm.name).alias("slow_rhythm_name"),
                    )
                )

    summary = add_base_deltas(pl.DataFrame(summary_rows, infer_schema_length=None)).sort(
        ["base_scenario", "slow_rhythm_name"],
        descending=[False, False],
    )
    orders_all = pl.concat(orders_frames, how="diagonal_relaxed") if orders_frames else pl.DataFrame()
    daily_all = pl.concat(daily_frames, how="diagonal_relaxed") if daily_frames else pl.DataFrame()
    curves_all = pl.concat(curve_frames, how="diagonal_relaxed") if curve_frames else pl.DataFrame()
    scaled_targets_all = (
        pl.concat(scaled_target_frames, how="diagonal_relaxed") if scaled_target_frames else pl.DataFrame()
    )
    drawdowns = pl.concat(drawdown_frames, how="diagonal_relaxed") if drawdown_frames else pl.DataFrame()
    yearly = build_yearly(daily_all)
    state_daily = summarize_state_daily(daily_all)
    quality = build_quality(summary, original_daily)

    summary.write_csv(paths["summary"])
    yearly.write_csv(paths["yearly"])
    drawdowns.write_csv(paths["drawdowns"])
    state_daily.write_csv(paths["state_daily"])
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
            "account_size_cny": ACCOUNT_SIZE_CNY,
            "focus_scenarios": FOCUS_SCENARIOS,
            "slow_rhythms": [(item.name, item.description) for item in SLOW_RHYTHMS],
            "research_sources": RESEARCH_SOURCES,
            "outputs": {key: str(path) for key, path in paths.items()},
        },
    )
    report_path = write_report(summary, yearly, drawdowns, state_daily, quality, paths)
    print(f"report={report_path}")
    print(
        summary.select(
            [
                "base_scenario",
                "slow_rhythm_name",
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
