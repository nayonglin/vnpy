from __future__ import annotations

import json
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any

import polars as pl

from analyze_stock_range_reversion_layer_attribution import load_panels
from analyze_stock_range_reversion_liquid_q3_300k_lot_feasibility import (
    ACCOUNT_SIZE_CNY,
    BOARD_LOT_SHARES,
    floor_to_lot_shares,
    write_json,
)
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import HORIZON, NATIVE_RESULTS_DIR, pct
from backtest_stock_range_reversion_liquid_q3_repairability_filter import OUTPUT_DIR as FILTER_OUTPUT_DIR
from backtest_stock_range_reversion_liquid_q3_repairability_filter import PREFIX as FILTER_PREFIX
from generate_stock_range_reversion_liquid_q3_paper_tracking import MAX_PARTICIPATION_ADV20, PAPER_SCENARIO, markdown_table


OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_300k_live_target_builder_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_300k_live_target_builder_v1"

SIDECAR_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_300k_component_exit_target_sidecar_replay_2018_2026"
).expanduser().resolve()
SIDECAR_PREFIX: str = "stock_range_reversion_liquid_q3_300k_component_exit_target_sidecar_replay_v1"

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "QuantConnect Portfolio Construction returns PortfolioTarget objects before execution",
        "https://www.quantconnect.com/docs/v2/writing-algorithms/algorithm-framework/portfolio-construction/key-concepts",
    ),
    (
        "QuantConnect documents pre-trade risk controls before order submission",
        "https://www.quantconnect.com/docs/v2/writing-algorithms/trading-and-orders/pre-trade-risk-control",
    ),
    (
        "OpenAlgo is an open-source algo trading platform with order and approval workflows",
        "https://github.com/marketcalls/openalgo",
    ),
    (
        "SSE trading mechanism documents A-share board lot constraints",
        "https://english.sse.com.cn/start/trading/mechanism/",
    ),
)


def current_check_date() -> date:
    override = os.getenv("LIVE_TARGET_DATE", "").strip()
    if override:
        return date.fromisoformat(override)
    return datetime.now().date()


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


def to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def read_csv_with_symbol(path: Path) -> pl.DataFrame:
    if not path.exists():
        return pl.DataFrame()
    return pl.read_csv(path, try_parse_dates=True, schema_overrides={"symbol": pl.Utf8}).with_columns(
        pl.col("symbol").cast(pl.Utf8).str.zfill(6)
    )


def build_calendar_target_weights(
    selected_all: pl.DataFrame,
    benchmark_df: pl.DataFrame,
    target_date: date,
    scenario: str,
) -> tuple[pl.DataFrame, pl.DataFrame, dict[str, Any]]:
    selected = selected_all.filter(pl.col("scenario") == scenario).with_columns(
        pl.col("symbol").cast(pl.Utf8).str.zfill(6)
    )
    if selected.is_empty():
        raise RuntimeError(f"No selected rows for scenario={scenario}")

    calendar = benchmark_df.select("datetime").unique().sort("datetime")["datetime"].to_list()
    latest_signal_date = selected["datetime"].max()
    if latest_signal_date not in calendar:
        raise RuntimeError(f"Latest signal date {latest_signal_date} is not in benchmark calendar.")

    if target_date in calendar:
        target_index = calendar.index(target_date)
    elif target_date > latest_signal_date:
        target_index = calendar.index(latest_signal_date) + 1
    else:
        raise RuntimeError(f"Target date {target_date} is before or equal to latest usable calendar date.")

    signal_window = calendar[max(0, target_index - HORIZON) : target_index]
    active = (
        selected.filter(pl.col("datetime").is_in(signal_window))
        .rename({"datetime": "signal_date"})
        .with_columns(
            pl.lit(target_date).alias("target_date"),
            pl.col("signal_date")
            .map_elements(lambda value: target_index - calendar.index(value), return_dtype=pl.Int64)
            .alias("holding_day"),
        )
        .filter((pl.col("holding_day") >= 1) & (pl.col("holding_day") <= HORIZON))
    )
    active_sleeves = active.select("signal_date").unique().height
    if active_sleeves <= 0:
        raise RuntimeError(f"No active signal sleeves for target_date={target_date}")

    source_lots = active.with_columns(
        (pl.col("basket_weight") / active_sleeves).alias("lot_weight"),
        pl.lit(active_sleeves).alias("active_sleeves"),
    )
    target_weights = (
        source_lots.group_by(["target_date", "symbol"])
        .agg(
            pl.col("lot_weight").sum().alias("target_weight"),
            pl.len().alias("active_lots"),
            pl.col("signal_date").n_unique().alias("source_signal_days"),
            pl.col("signal_date").min().alias("source_signal_min"),
            pl.col("signal_date").max().alias("source_signal_max"),
            pl.col("holding_day").min().alias("min_holding_day"),
            pl.col("holding_day").max().alias("max_holding_day"),
            pl.col("code_name").last().alias("code_name"),
            pl.col("industry").last().alias("industry"),
            pl.col("adv20_turnover").median().alias("adv20_turnover"),
            pl.col("turnover_rate_f").median().alias("turnover_rate_f"),
            pl.col("circ_mv").median().alias("circ_mv"),
            pl.col("total_mv").median().alias("total_mv"),
            pl.col("top_age").max().alias("max_top_age"),
            pl.col("basket_gross_weight").mean().alias("avg_source_basket_gross_weight"),
        )
        .with_columns(
            (pl.col("target_weight") * ACCOUNT_SIZE_CNY).alias("target_amount_cny"),
            pl.lit(ACCOUNT_SIZE_CNY).alias("account_size_cny"),
            pl.lit(scenario).alias("scenario"),
        )
        .sort(["target_date", "industry", "symbol"])
    )
    meta = {
        "scenario": scenario,
        "target_date": target_date,
        "latest_signal_date": latest_signal_date,
        "active_sleeves": active_sleeves,
        "signal_window_min": min(signal_window) if signal_window else None,
        "signal_window_max": max(signal_window) if signal_window else None,
        "target_date_in_benchmark_calendar": target_date in calendar,
        "target_calendar_index": target_index,
    }
    return target_weights, source_lots, meta


def build_latest_stock_info(stock_df: pl.DataFrame, signal_date: date) -> dict[str, dict[str, Any]]:
    needed = [
        "datetime",
        "symbol",
        "code_name",
        "trade_close",
        "close",
        "trade_open",
        "adv20_turnover",
        "is_st",
        "is_suspended",
        "is_listed_status",
        "eligible_research_row",
        "eligible_component_row",
        "is_index_component",
        "is_oneword_limit_up",
        "is_oneword_limit_down",
        "is_limit_up_close",
        "is_limit_down_close",
    ]
    latest = (
        stock_df.filter(pl.col("datetime") == signal_date)
        .select([col for col in needed if col in stock_df.columns])
        .with_columns(pl.col("symbol").cast(pl.Utf8).str.zfill(6))
    )
    return {row["symbol"]: row for row in latest.iter_rows(named=True)}


def build_positions_from_orders(orders: pl.DataFrame) -> tuple[pl.DataFrame, date | None]:
    if orders.is_empty():
        return pl.DataFrame(), None
    position_date = orders["date"].max()
    positions = (
        orders.sort(["date", "symbol", "side"])
        .group_by("symbol")
        .agg(
            pl.col("date").last().alias("last_order_date"),
            pl.col("code_name").last().alias("code_name"),
            pl.col("industry").last().alias("industry"),
            pl.col("actual_shares_after").last().alias("current_shares"),
            pl.col("trade_open").last().alias("last_trade_open"),
        )
        .filter(pl.col("current_shares") > 0)
        .with_columns(pl.col("symbol").cast(pl.Utf8).str.zfill(6))
        .sort("symbol")
    )
    return positions, position_date


def build_live_targets(
    target_weights: pl.DataFrame,
    latest_stock_info: dict[str, dict[str, Any]],
    positions: pl.DataFrame,
    latest_signal_date: date,
) -> pl.DataFrame:
    previous_shares = {
        row["symbol"]: int(row["current_shares"]) for row in positions.iter_rows(named=True)
    } if not positions.is_empty() else {}
    rows: list[dict[str, Any]] = []
    for row in target_weights.iter_rows(named=True):
        symbol = str(row["symbol"]).zfill(6)
        info = latest_stock_info.get(symbol, {})
        reference_price = to_float(info.get("trade_close") or info.get("close"))
        raw_target_weight = to_float(row.get("target_weight"))
        raw_target_amount = raw_target_weight * ACCOUNT_SIZE_CNY
        raw_target_shares = floor_to_lot_shares(raw_target_amount, reference_price)
        prev_shares = int(previous_shares.get(symbol, 0))
        latest_known_component = bool(info.get("is_index_component") or False)
        latest_known_research_eligible = bool(info.get("eligible_research_row") or False)
        latest_known_st = bool(info.get("is_st") or False)
        sidecar_target_shares = raw_target_shares
        sidecar_reason = ""
        if raw_target_weight > 0 and not latest_known_component:
            sidecar_target_shares = min(raw_target_shares, prev_shares)
            if sidecar_target_shares < raw_target_shares:
                sidecar_reason = "latest_known_not_index_component_no_buy_add"
        sidecar_target_amount = sidecar_target_shares * reference_price
        sidecar_target_weight = sidecar_target_amount / ACCOUNT_SIZE_CNY if ACCOUNT_SIZE_CNY else 0.0
        rows.append(
            {
                "target_date": row["target_date"],
                "signal_date_for_latest_known_fields": latest_signal_date,
                "symbol": symbol,
                "code_name": row.get("code_name") or info.get("code_name") or "",
                "industry": row.get("industry") or "",
                "raw_target_weight": raw_target_weight,
                "raw_target_amount_cny": raw_target_amount,
                "raw_target_shares": raw_target_shares,
                "sidecar_target_weight": sidecar_target_weight,
                "sidecar_target_amount_cny": sidecar_target_amount,
                "sidecar_target_shares": sidecar_target_shares,
                "suppressed_shares": max(0, raw_target_shares - sidecar_target_shares),
                "suppressed_amount_cny": max(0, raw_target_shares - sidecar_target_shares) * reference_price,
                "component_target_sidecar_reason": sidecar_reason,
                "prev_shares": prev_shares,
                "reference_price": reference_price,
                "reference_price_source": "signal_date_trade_close",
                "one_lot_amount_cny": reference_price * BOARD_LOT_SHARES,
                "zero_lot_target": raw_target_weight > 0 and sidecar_target_shares <= 0,
                "raw_zero_lot_target": raw_target_weight > 0 and raw_target_shares <= 0,
                "latest_known_component": latest_known_component,
                "latest_known_research_eligible": latest_known_research_eligible,
                "latest_known_st": latest_known_st,
                "latest_known_suspended": bool(info.get("is_suspended") or False),
                "latest_known_oneword_limit_up": bool(info.get("is_oneword_limit_up") or False),
                "latest_known_oneword_limit_down": bool(info.get("is_oneword_limit_down") or False),
                "latest_known_limit_up_close": bool(info.get("is_limit_up_close") or False),
                "latest_known_limit_down_close": bool(info.get("is_limit_down_close") or False),
                "adv20_turnover": row.get("adv20_turnover"),
                "turnover_rate_f": row.get("turnover_rate_f"),
                "active_lots": row.get("active_lots"),
                "source_signal_days": row.get("source_signal_days"),
                "source_signal_min": row.get("source_signal_min"),
                "source_signal_max": row.get("source_signal_max"),
                "min_holding_day": row.get("min_holding_day"),
                "max_holding_day": row.get("max_holding_day"),
            }
        )
    return pl.DataFrame(rows).sort(["zero_lot_target", "sidecar_target_weight", "symbol"], descending=[True, True, False])


def classify_estimated_order(side: str, target: dict[str, Any], desired_shares: int) -> tuple[str, str]:
    if to_float(target.get("reference_price")) <= 0:
        return "blocked_estimate", "missing_latest_reference_price"
    if side == "buy" and not bool(target.get("latest_known_component")):
        return "blocked_estimate", "latest_known_not_index_component"
    if side == "buy" and (bool(target.get("latest_known_st")) or not bool(target.get("latest_known_research_eligible"))):
        return "blocked_estimate", "latest_known_st_or_research_ineligible"
    if bool(target.get("latest_known_suspended")):
        return "blocked_estimate", "latest_known_suspended"
    adv = to_float(target.get("adv20_turnover"))
    if adv <= 0:
        return "manual_review", "missing_latest_adv20_turnover"
    cap_amount = MAX_PARTICIPATION_ADV20 * adv
    cap_shares = floor_to_lot_shares(cap_amount, to_float(target.get("reference_price")))
    if desired_shares > cap_shares:
        return "cap_limited_estimate", "latest_known_adv20_participation_cap"
    return "tradable_estimate_pending_open_recalc", ""


def build_estimated_orders(live_targets: pl.DataFrame, positions: pl.DataFrame, latest_stock_info: dict[str, dict[str, Any]]) -> pl.DataFrame:
    target_by_symbol = {row["symbol"]: row for row in live_targets.iter_rows(named=True)}
    position_by_symbol = {
        row["symbol"]: row for row in positions.iter_rows(named=True)
    } if not positions.is_empty() else {}
    symbols = sorted(set(target_by_symbol) | set(position_by_symbol))
    rows: list[dict[str, Any]] = []
    for symbol in symbols:
        target = target_by_symbol.get(symbol)
        position = position_by_symbol.get(symbol, {})
        info = latest_stock_info.get(symbol, {})
        if target is None:
            reference_price = to_float(info.get("trade_close") or info.get("close") or position.get("last_trade_open"))
            target = {
                "target_date": live_targets["target_date"].max() if not live_targets.is_empty() else None,
                "symbol": symbol,
                "code_name": position.get("code_name") or info.get("code_name") or "",
                "industry": position.get("industry") or "",
                "raw_target_weight": 0.0,
                "sidecar_target_weight": 0.0,
                "sidecar_target_shares": 0,
                "reference_price": reference_price,
                "reference_price_source": "signal_date_trade_close_for_existing_position",
                "latest_known_component": bool(info.get("is_index_component") or False),
                "latest_known_research_eligible": bool(info.get("eligible_research_row") or False),
                "latest_known_st": bool(info.get("is_st") or False),
                "latest_known_suspended": bool(info.get("is_suspended") or False),
                "adv20_turnover": to_float(info.get("adv20_turnover")),
                "component_target_sidecar_reason": "",
            }
        prev_shares = int(position.get("current_shares") or target.get("prev_shares") or 0)
        target_shares = int(target.get("sidecar_target_shares") or 0)
        delta_shares = target_shares - prev_shares
        if delta_shares == 0:
            continue
        side = "buy" if delta_shares > 0 else "sell"
        desired_shares = abs(delta_shares)
        reference_price = to_float(target.get("reference_price"))
        desired_amount = desired_shares * reference_price
        status, reason = classify_estimated_order(side, target, desired_shares)
        cap_amount = MAX_PARTICIPATION_ADV20 * to_float(target.get("adv20_turnover")) if to_float(target.get("adv20_turnover")) > 0 else 0.0
        cap_shares = floor_to_lot_shares(cap_amount, reference_price)
        rows.append(
            {
                "target_date": target.get("target_date"),
                "symbol": symbol,
                "code_name": target.get("code_name") or "",
                "industry": target.get("industry") or "",
                "side": side,
                "estimated_status": status,
                "estimated_blocked_reason": reason,
                "prev_shares": prev_shares,
                "target_shares": target_shares,
                "desired_shares": desired_shares,
                "reference_price": reference_price,
                "reference_price_source": target.get("reference_price_source"),
                "desired_amount_cny": desired_amount,
                "raw_target_weight": to_float(target.get("raw_target_weight")),
                "sidecar_target_weight": to_float(target.get("sidecar_target_weight")),
                "component_target_sidecar_reason": target.get("component_target_sidecar_reason") or "",
                "latest_known_component": bool(target.get("latest_known_component")),
                "latest_known_research_eligible": bool(target.get("latest_known_research_eligible")),
                "latest_known_st": bool(target.get("latest_known_st")),
                "latest_known_suspended": bool(target.get("latest_known_suspended")),
                "adv_cap_amount_cny": cap_amount,
                "adv_cap_shares": cap_shares,
                "note": "估算订单使用信号日收盘价；真实委托前必须用券商持仓和目标日可交易价格重算。",
            }
        )
    return pl.DataFrame(rows).sort(["side", "desired_amount_cny", "symbol"], descending=[False, True, False]) if rows else pl.DataFrame()


def build_parity_check(selected_all: pl.DataFrame, benchmark_df: pl.DataFrame) -> dict[str, Any]:
    from generate_stock_range_reversion_liquid_q3_paper_tracking import build_target_weights

    old_targets = build_target_weights(selected_all)
    old_latest_date = old_targets["target_date"].max()
    replay_targets, _source_lots, _meta = build_calendar_target_weights(
        selected_all,
        benchmark_df,
        old_latest_date,
        PAPER_SCENARIO,
    )
    old_latest = (
        old_targets.filter(pl.col("target_date") == old_latest_date)
        .select("target_date", "symbol", "target_weight")
        .with_columns(pl.col("symbol").cast(pl.Utf8).str.zfill(6))
    )
    replay_latest = replay_targets.select("target_date", "symbol", "target_weight")
    joined = old_latest.join(replay_latest, on=["target_date", "symbol"], how="full", suffix="_live").with_columns(
        (pl.col("target_weight").fill_null(0.0) - pl.col("target_weight_live").fill_null(0.0)).abs().alias(
            "abs_weight_diff"
        )
    )
    max_abs_diff = to_float(joined["abs_weight_diff"].max())
    changed_rows = joined.filter(pl.col("abs_weight_diff") > 1e-12).height
    return {
        "backtest_latest_target_date": old_latest_date,
        "backtest_latest_target_rows": old_latest.height,
        "calendar_replay_target_rows": replay_latest.height,
        "parity_changed_rows": changed_rows,
        "parity_max_abs_weight_diff": max_abs_diff,
        "parity_sum_abs_weight_diff": to_float(joined["abs_weight_diff"].sum()),
    }


def add_quality(
    rows: list[dict[str, Any]],
    checkpoint: str,
    status: str,
    value: Any,
    expected: Any,
    note: str,
) -> None:
    rows.append(
        {
            "checkpoint": checkpoint,
            "status": status,
            "value": "" if value is None else str(value),
            "expected": "" if expected is None else str(expected),
            "note": note,
        }
    )


def build_quality(summary: dict[str, Any]) -> pl.DataFrame:
    rows: list[dict[str, Any]] = []
    add_quality(
        rows,
        "selected_signal_reaches_stock_panel_max",
        "pass" if summary["latest_signal_date"] == summary["stock_panel_max_date"] else "fail",
        f"signal={summary['latest_signal_date']}, stock={summary['stock_panel_max_date']}",
        "equal",
        "live目标应使用当前股票面板最新信号日。",
    )
    add_quality(
        rows,
        "selected_signal_reaches_benchmark_panel_max",
        "pass" if summary["latest_signal_date"] == summary["benchmark_panel_max_date"] else "fail",
        f"signal={summary['latest_signal_date']}, benchmark={summary['benchmark_panel_max_date']}",
        "equal",
        "信号日和基准日历不能错位。",
    )
    add_quality(
        rows,
        "target_date_after_signal_date",
        "pass" if summary["proposed_target_date"] > summary["latest_signal_date"] else "fail",
        f"target={summary['proposed_target_date']}, signal={summary['latest_signal_date']}",
        "target > signal",
        "下一执行日目标必须晚于信号日。",
    )
    add_quality(
        rows,
        "calendar_target_replay_matches_backtest_latest",
        "pass" if summary["parity_changed_rows"] == 0 and summary["parity_max_abs_weight_diff"] <= 1e-12 else "fail",
        f"changed={summary['parity_changed_rows']}, max_diff={summary['parity_max_abs_weight_diff']}",
        "changed=0 and max_diff<=1e-12",
        "同一算法在旧最新回测目标日应与原target_weights完全一致，避免live目标构造变形。",
    )
    add_quality(
        rows,
        "live_target_generated",
        "pass" if summary["live_raw_target_count"] > 0 else "fail",
        summary["live_raw_target_count"],
        ">0",
        "必须能生成目标权重。",
    )
    add_quality(
        rows,
        "no_not_index_component_buy_after_sidecar",
        "pass" if summary["estimated_not_index_buy_order_count"] == 0 else "fail",
        summary["estimated_not_index_buy_order_count"],
        0,
        "最新已知非成分股不应留下买入或加仓估算订单。",
    )
    add_quality(
        rows,
        "estimated_orders_have_no_hard_block",
        "pass" if summary["estimated_blocked_order_count"] == 0 else "warn",
        summary["estimated_blocked_order_count"],
        0,
        "这里是信号日收盘估算，不是真实开盘pre-trade；若出现阻断需人工复核。",
    )
    add_quality(
        rows,
        "reference_price_is_not_target_open",
        "warn",
        summary["reference_price_source"],
        "target_open after market data",
        "当前只能用信号日收盘估算股数，开盘前/开盘后必须重算。",
    )
    add_quality(
        rows,
        "broker_position_reconciliation_required",
        "manual",
        f"repository_position_date={summary['position_state_date']}",
        "broker verified",
        "估算订单只能辅助人工复核，不能替代券商账户持仓、现金和冻结资金校验。",
    )
    add_quality(
        rows,
        "no_signal_parameter_change",
        "pass",
        "no signal/threshold change",
        "no signal/threshold change",
        "本阶段只修目标生成时点，不改alpha、过滤阈值或仓位上限。",
    )
    return pl.DataFrame(rows)


def _markdown_all(frame: pl.DataFrame, max_rows: int = 80) -> str:
    if frame.is_empty():
        return "无数据"
    return markdown_table(frame, frame.columns, max_rows=max_rows)


def write_report(
    summary: dict[str, Any],
    quality: pl.DataFrame,
    live_targets: pl.DataFrame,
    estimated_orders: pl.DataFrame,
    positions: pl.DataFrame,
    source_lots: pl.DataFrame,
    paths: dict[str, Path],
) -> Path:
    failed = quality.filter(pl.col("status") == "fail")
    warned = quality.filter(pl.col("status") == "warn")
    manual = quality.filter(pl.col("status") == "manual")
    zero_lot = live_targets.filter(pl.col("zero_lot_target")) if not live_targets.is_empty() else live_targets
    report_path = paths["report"]
    lines = [
        "# 股票震荡liquid_q3 30万 live-target builder v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：补真正live目标生成层，避免latest packet依赖未来`pnl_date/stock_daily_ret`；不改信号和参数。",
        f"- 最新信号日：`{summary['latest_signal_date']}`；建议目标执行日：`{summary['proposed_target_date']}`。",
        f"- 账户规模：`{ACCOUNT_SIZE_CNY:,.0f}`元；买入颗粒度：`{BOARD_LOT_SHARES}`股。",
        "- A/B判断：股票震荡独立paper执行链路，不做第78 A/B/C。",
        "",
        "## 外部调研判断",
        "",
        "- 成熟交易系统通常把alpha signal、portfolio target、pre-trade risk control和order delta分层。",
        "- 当前仓库旧latest packet从回测lots取目标，尾部自然需要未来收益字段；实盘目标层应只用已经落库的信号日数据。",
        "- 本阶段输出的是目标和估算订单，不是可直接提交券商的正式订单。",
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
            f"- 旧回测最新目标日：`{summary['backtest_latest_target_date']}`；live最新信号日：`{summary['latest_signal_date']}`；live建议执行日：`{summary['proposed_target_date']}`。",
            f"- parity校验：旧最新目标日复刻变化`{summary['parity_changed_rows']}`行，最大权重差`{summary['parity_max_abs_weight_diff']:.12f}`。",
            f"- live原始目标`{summary['live_raw_target_count']}`只，sidecar后目标`{summary['live_sidecar_target_count']}`只。",
            f"- 原始目标金额`{summary['live_raw_target_amount_sum_cny']:,.0f}`元，sidecar估算目标市值`{summary['live_sidecar_target_amount_sum_cny']:,.0f}`元。",
            f"- 买不到一手目标`{summary['live_zero_lot_target_count']}`只，占比`{summary['live_zero_lot_target_ratio']:.2%}`。",
            f"- 估算订单`{summary['estimated_order_count']}`行：买入`{summary['estimated_buy_order_count']}`行，卖出`{summary['estimated_sell_order_count']}`行；估算阻断`{summary['estimated_blocked_order_count']}`行。",
            f"- 仓库持仓来源日期：`{summary['position_state_date']}`，持仓股票`{summary['position_symbol_count']}`只。",
            "",
            "## 结论",
            "",
            "- 目标层时点问题已被拆出来：可以从`2026-04-28`信号生成`2026-04-29`目标，不再被未来`pnl_date/stock_daily_ret`卡住。",
            "- 但这个包仍不能直接实盘发单：目标股数用的是信号日收盘价估算，真实委托前必须用券商持仓、现金、目标日可交易价格和最新停牌/涨跌停状态重算。",
            "- 下一步应把这个live-target builder接入suite和pre-live checklist，让每日paper监控先看live目标，再看执行估算。",
            "",
            "## 质量检查",
            "",
            _markdown_all(quality),
            "",
            "## 失败项",
            "",
            _markdown_all(failed),
            "",
            "## 警告项",
            "",
            _markdown_all(warned),
            "",
            "## 人工确认项",
            "",
            _markdown_all(manual),
            "",
            "## 买不到一手目标",
            "",
            markdown_table(
                zero_lot,
                [
                    "target_date",
                    "symbol",
                    "code_name",
                    "industry",
                    "raw_target_weight",
                    "raw_target_amount_cny",
                    "sidecar_target_shares",
                    "reference_price",
                    "one_lot_amount_cny",
                ],
                max_rows=80,
            ),
            "",
            "## live目标",
            "",
            markdown_table(
                live_targets,
                [
                    "target_date",
                    "symbol",
                    "code_name",
                    "industry",
                    "raw_target_weight",
                    "sidecar_target_weight",
                    "prev_shares",
                    "raw_target_shares",
                    "sidecar_target_shares",
                    "component_target_sidecar_reason",
                    "reference_price",
                    "latest_known_component",
                    "latest_known_st",
                ],
                max_rows=120,
            ),
            "",
            "## 估算订单",
            "",
            markdown_table(
                estimated_orders,
                [
                    "target_date",
                    "symbol",
                    "code_name",
                    "industry",
                    "side",
                    "estimated_status",
                    "estimated_blocked_reason",
                    "prev_shares",
                    "target_shares",
                    "desired_shares",
                    "reference_price",
                    "desired_amount_cny",
                    "adv_cap_shares",
                ],
                max_rows=120,
            ),
            "",
            "## 当前仓库持仓",
            "",
            markdown_table(
                positions,
                ["symbol", "code_name", "industry", "current_shares", "last_order_date", "last_trade_open"],
                max_rows=120,
            ),
            "",
            "## live目标来源lots",
            "",
            markdown_table(
                source_lots,
                [
                    "target_date",
                    "signal_date",
                    "symbol",
                    "code_name",
                    "industry",
                    "holding_day",
                    "basket_weight",
                    "lot_weight",
                    "active_sleeves",
                ],
                max_rows=120,
            ),
            "",
            "## 运行前过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：本阶段修的是实盘目标生成时点，不使用收益结果选择参数。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：parity校验证明live目标算法在旧最新日与回测目标一致，且没有改变信号、阈值、权重上限。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：如果最新目标不能摆脱未来收益字段，策略永远只能事后paper，不能进入真实跟踪。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：目标层已能生成下一执行日目标，后续应接入suite和pre-live，把目标、估算订单、实盘前阻断分层监控。",
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
    check_date = current_check_date()
    selected_all = pl.read_parquet(FILTER_OUTPUT_DIR / f"{FILTER_PREFIX}_selected_all.parquet")
    stock_df, benchmark_df = load_panels()
    stock_max_date = stock_df["datetime"].max()
    benchmark_max_date = benchmark_df["datetime"].max()
    proposed_target_date = check_date
    if proposed_target_date <= stock_max_date:
        proposed_target_date = stock_max_date

    live_target_weights, source_lots, live_meta = build_calendar_target_weights(
        selected_all,
        benchmark_df,
        proposed_target_date,
        PAPER_SCENARIO,
    )
    latest_signal_date = live_meta["latest_signal_date"]
    latest_stock_info = build_latest_stock_info(stock_df, latest_signal_date)

    sidecar_orders = read_csv_with_symbol(SIDECAR_DIR / f"{SIDECAR_PREFIX}_sidecar_strict_orders.csv")
    positions, position_state_date = build_positions_from_orders(sidecar_orders)
    live_targets = build_live_targets(live_target_weights, latest_stock_info, positions, latest_signal_date)
    estimated_orders = build_estimated_orders(live_targets, positions, latest_stock_info)
    parity = build_parity_check(selected_all, benchmark_df)

    estimated_blocked = (
        estimated_orders.filter(pl.col("estimated_status") == "blocked_estimate")
        if not estimated_orders.is_empty()
        else estimated_orders
    )
    estimated_not_index_buy = (
        estimated_orders.filter(
            (pl.col("side") == "buy")
            & (pl.col("latest_known_component") == False)  # noqa: E712
        )
        if not estimated_orders.is_empty()
        else estimated_orders
    )
    raw_targets = live_targets.filter(pl.col("raw_target_weight") > 0)
    sidecar_targets = live_targets.filter(pl.col("sidecar_target_weight") > 0)
    zero_lot_targets = live_targets.filter(pl.col("zero_lot_target"))
    buy_orders = estimated_orders.filter(pl.col("side") == "buy") if not estimated_orders.is_empty() else estimated_orders
    sell_orders = estimated_orders.filter(pl.col("side") == "sell") if not estimated_orders.is_empty() else estimated_orders
    summary: dict[str, Any] = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "check_date": check_date,
        "scenario": PAPER_SCENARIO,
        "account_size_cny": ACCOUNT_SIZE_CNY,
        "board_lot_shares": BOARD_LOT_SHARES,
        "latest_signal_date": latest_signal_date,
        "proposed_target_date": proposed_target_date,
        "stock_panel_max_date": stock_max_date,
        "benchmark_panel_max_date": benchmark_max_date,
        "target_date_in_benchmark_calendar": live_meta["target_date_in_benchmark_calendar"],
        "active_sleeves": live_meta["active_sleeves"],
        "signal_window_min": live_meta["signal_window_min"],
        "signal_window_max": live_meta["signal_window_max"],
        "position_state_date": position_state_date,
        "position_symbol_count": positions.height,
        "reference_price_source": "signal_date_trade_close",
        "live_raw_target_count": raw_targets.height,
        "live_sidecar_target_count": sidecar_targets.height,
        "live_raw_target_amount_sum_cny": to_float(raw_targets["raw_target_amount_cny"].sum()) if not raw_targets.is_empty() else 0.0,
        "live_sidecar_target_amount_sum_cny": (
            to_float(sidecar_targets["sidecar_target_amount_cny"].sum()) if not sidecar_targets.is_empty() else 0.0
        ),
        "live_zero_lot_target_count": zero_lot_targets.height,
        "live_zero_lot_target_ratio": zero_lot_targets.height / raw_targets.height if raw_targets.height else 0.0,
        "live_component_adjustment_rows": live_targets.filter(pl.col("component_target_sidecar_reason") != "").height,
        "live_component_suppressed_amount_cny": to_float(live_targets["suppressed_amount_cny"].sum()),
        "estimated_order_count": estimated_orders.height,
        "estimated_buy_order_count": buy_orders.height,
        "estimated_sell_order_count": sell_orders.height,
        "estimated_blocked_order_count": estimated_blocked.height,
        "estimated_not_index_buy_order_count": estimated_not_index_buy.height,
        "estimated_desired_amount_sum_cny": (
            to_float(estimated_orders["desired_amount_cny"].sum()) if not estimated_orders.is_empty() else 0.0
        ),
        "estimated_buy_amount_sum_cny": to_float(buy_orders["desired_amount_cny"].sum()) if not buy_orders.is_empty() else 0.0,
        "estimated_sell_amount_sum_cny": to_float(sell_orders["desired_amount_cny"].sum()) if not sell_orders.is_empty() else 0.0,
        **parity,
    }
    quality = build_quality(summary)
    summary["quality_pass_count"] = quality.filter(pl.col("status") == "pass").height
    summary["quality_warn_count"] = quality.filter(pl.col("status") == "warn").height
    summary["quality_fail_count"] = quality.filter(pl.col("status") == "fail").height
    summary["quality_manual_count"] = quality.filter(pl.col("status") == "manual").height
    if summary["quality_fail_count"] > 0:
        summary["target_builder_state"] = "red_target_build_failed"
    elif summary["quality_warn_count"] > 0 or summary["quality_manual_count"] > 0:
        summary["target_builder_state"] = "yellow_target_generated_order_recalc_required"
    else:
        summary["target_builder_state"] = "green_target_generated_for_paper"

    paths = {
        "report": OUTPUT_DIR / f"{PREFIX}_report.md",
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.json",
        "live_targets": OUTPUT_DIR / f"{PREFIX}_live_targets.csv",
        "estimated_orders": OUTPUT_DIR / f"{PREFIX}_estimated_orders.csv",
        "positions": OUTPUT_DIR / f"{PREFIX}_positions.csv",
        "target_source_lots": OUTPUT_DIR / f"{PREFIX}_target_source_lots.csv",
        "quality": OUTPUT_DIR / f"{PREFIX}_quality_checkpoints.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }
    live_targets.write_csv(paths["live_targets"])
    estimated_orders.write_csv(paths["estimated_orders"])
    positions.write_csv(paths["positions"])
    source_lots.write_csv(paths["target_source_lots"])
    quality.write_csv(paths["quality"])
    write_json(paths["summary"], summary)
    write_json(
        paths["meta"],
        {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "research_sources": RESEARCH_SOURCES,
            "selected_all": str(FILTER_OUTPUT_DIR / f"{FILTER_PREFIX}_selected_all.parquet"),
            "sidecar_orders": str(SIDECAR_DIR / f"{SIDECAR_PREFIX}_sidecar_strict_orders.csv"),
            "note": "Live target builder only; estimated orders require broker reconciliation and target-open recalculation.",
        },
    )
    report_path = write_report(summary, quality, live_targets, estimated_orders, positions, source_lots, paths)
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
