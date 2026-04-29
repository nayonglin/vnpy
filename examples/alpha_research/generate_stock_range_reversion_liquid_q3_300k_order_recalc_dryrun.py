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
from backtest_stock_range_reversion_industry_neutral_merged_portfolio import NATIVE_RESULTS_DIR, pct
from generate_stock_range_reversion_liquid_q3_paper_tracking import MAX_PARTICIPATION_ADV20, markdown_table


OUTPUT_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_300k_order_recalc_dryrun_2018_2026"
).expanduser().resolve()
PREFIX: str = "stock_range_reversion_liquid_q3_300k_order_recalc_dryrun_v1"

LIVE_TARGET_DIR: Path = (
    NATIVE_RESULTS_DIR / "stock_range_reversion_liquid_q3_300k_live_target_builder_2018_2026"
).expanduser().resolve()
LIVE_TARGET_PREFIX: str = "stock_range_reversion_liquid_q3_300k_live_target_builder_v1"

CASH_BUFFER_RATIO: float = float(os.getenv("ORDER_RECALC_CASH_BUFFER_RATIO", "0.01") or 0.01)
PRICE_SNAPSHOT_PATH: str = os.getenv("ORDER_RECALC_PRICE_SNAPSHOT", "").strip()
BROKER_CASH_CNY: str = os.getenv("ORDER_RECALC_BROKER_CASH_CNY", "").strip()
POSITION_SHARE_COLUMNS: tuple[str, ...] = ("broker_position_shares", "current_shares", "position_shares")
BROKER_CASH_COLUMNS: tuple[str, ...] = ("broker_cash_cny", "cash_available_cny", "available_cash_cny")

RESEARCH_SOURCES: tuple[tuple[str, str], ...] = (
    (
        "QuantConnect SetHoldings calculates quantity from current price and fees",
        "https://www.quantconnect.com/docs/v1/algorithm-reference/trading-and-orders",
    ),
    (
        "QuantConnect ExecutionModel receives PortfolioTarget objects and executes them",
        "https://www.quantconnect.com/docs/v2/writing-algorithms/algorithm-framework/execution/key-concepts",
    ),
    (
        "OpenAlgo supports basket orders, smart orders and position sizing",
        "https://github.com/marketcalls/openalgo",
    ),
)


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


def to_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y"}:
        return True
    if text in {"0", "false", "no", "n"}:
        return False
    return default


def parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def first_positive(row: dict[str, Any], columns: list[str]) -> tuple[float, str]:
    for column in columns:
        if column in row:
            value = to_float(row.get(column))
            if value > 0:
                return value, column
    return 0.0, ""


def read_csv_with_symbol(path: Path) -> pl.DataFrame:
    return pl.read_csv(path, try_parse_dates=True, schema_overrides={"symbol": pl.Utf8}).with_columns(
        pl.col("symbol").cast(pl.Utf8).str.zfill(6)
    )


def read_optional_snapshot() -> tuple[pl.DataFrame, dict[str, dict[str, Any]], str]:
    if not PRICE_SNAPSHOT_PATH:
        return pl.DataFrame(), {}, "missing"
    path = Path(PRICE_SNAPSHOT_PATH).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(path)
    frame = pl.read_csv(path, try_parse_dates=True, schema_overrides={"symbol": pl.Utf8}).with_columns(
        pl.col("symbol").cast(pl.Utf8).str.zfill(6)
    )
    return frame, {row["symbol"]: row for row in frame.iter_rows(named=True)}, str(path)


def first_existing_column(frame: pl.DataFrame, columns: tuple[str, ...]) -> str:
    for column in columns:
        if column in frame.columns:
            return column
    return ""


def build_positions_from_snapshot(snapshot_frame: pl.DataFrame, fallback_positions: pl.DataFrame) -> tuple[pl.DataFrame, str]:
    position_column = first_existing_column(snapshot_frame, POSITION_SHARE_COLUMNS)
    if snapshot_frame.is_empty() or not position_column:
        return fallback_positions, "live_builder_repository_positions"
    rows: list[dict[str, Any]] = []
    for row in snapshot_frame.iter_rows(named=True):
        current_shares = int(to_float(row.get(position_column)))
        if current_shares <= 0:
            continue
        rows.append(
            {
                "symbol": str(row["symbol"]).zfill(6),
                "last_order_date": parse_date(row.get("snapshot_date")) or parse_date(row.get("date")),
                "code_name": str(row.get("code_name") or ""),
                "industry": str(row.get("industry") or ""),
                "current_shares": current_shares,
                "last_trade_open": first_positive(row, ["price", "last_price", "trade_open", "open", "reference_price"])[0],
            }
        )
    return (
        pl.DataFrame(rows).sort("symbol") if rows else pl.DataFrame(schema=fallback_positions.schema),
        f"external_snapshot:{position_column}",
    )


def extract_snapshot_cash(snapshot_frame: pl.DataFrame) -> tuple[float | None, str]:
    cash_column = first_existing_column(snapshot_frame, BROKER_CASH_COLUMNS)
    if snapshot_frame.is_empty() or not cash_column:
        return None, ""
    values = [
        to_float(value)
        for value in snapshot_frame[cash_column].to_list()
        if to_float(value) > 0
    ]
    if not values:
        return None, cash_column
    return values[0], cash_column


def build_stock_lookup(stock_df: pl.DataFrame, target_date: date | None, signal_date: date | None) -> tuple[dict[str, Any], dict[str, Any]]:
    columns = [
        "datetime",
        "symbol",
        "code_name",
        "trade_open",
        "trade_close",
        "close",
        "adv20_turnover",
        "is_st",
        "is_suspended",
        "eligible_research_row",
        "is_index_component",
        "is_oneword_limit_up",
        "is_oneword_limit_down",
        "is_limit_up_close",
        "is_limit_down_close",
    ]
    work = stock_df.select([col for col in columns if col in stock_df.columns]).with_columns(
        pl.col("symbol").cast(pl.Utf8).str.zfill(6)
    )
    target_lookup = {}
    latest_lookup = {}
    if target_date is not None:
        target_lookup = {
            row["symbol"]: row for row in work.filter(pl.col("datetime") == target_date).iter_rows(named=True)
        }
    if signal_date is not None:
        latest_lookup = {
            row["symbol"]: row for row in work.filter(pl.col("datetime") == signal_date).iter_rows(named=True)
        }
    return target_lookup, latest_lookup


def choose_price_and_state(
    symbol: str,
    target: dict[str, Any],
    snapshot_lookup: dict[str, dict[str, Any]],
    target_lookup: dict[str, dict[str, Any]],
    latest_lookup: dict[str, dict[str, Any]],
    position: dict[str, Any] | None = None,
) -> dict[str, Any]:
    price_columns = ["price", "last_price", "trade_open", "open", "reference_price", "trade_close", "close"]
    if symbol in snapshot_lookup:
        row = snapshot_lookup[symbol]
        price, column = first_positive(row, price_columns)
        return {
            "price": price,
            "price_source": f"external_snapshot:{column}" if column else "external_snapshot:missing_price",
            "row": row,
            "state_source": "external_snapshot",
        }
    if symbol in target_lookup:
        row = target_lookup[symbol]
        price, column = first_positive(row, ["trade_open", "open", "trade_close", "close"])
        return {
            "price": price,
            "price_source": f"stock_panel_target_date:{column}" if column else "stock_panel_target_date:missing_price",
            "row": row,
            "state_source": "stock_panel_target_date",
        }
    if symbol in latest_lookup:
        row = latest_lookup[symbol]
        price = to_float(target.get("reference_price")) or to_float(row.get("trade_close")) or to_float(row.get("close"))
        return {
            "price": price,
            "price_source": "live_signal_date_trade_close_fallback",
            "row": row,
            "state_source": "latest_known_signal_date",
        }
    price = to_float(target.get("reference_price")) or to_float((position or {}).get("last_trade_open"))
    return {
        "price": price,
        "price_source": "live_target_or_position_fallback",
        "row": {},
        "state_source": "fallback_only",
    }


def bool_from_sources(target: dict[str, Any], row: dict[str, Any], target_column: str, row_column: str, default: bool) -> bool:
    if row_column in row:
        return to_bool(row.get(row_column), default=default)
    if target_column in target:
        return to_bool(target.get(target_column), default=default)
    return default


def build_recalc_targets(
    live_targets: pl.DataFrame,
    positions: pl.DataFrame,
    snapshot_lookup: dict[str, dict[str, Any]],
    target_lookup: dict[str, dict[str, Any]],
    latest_lookup: dict[str, dict[str, Any]],
) -> pl.DataFrame:
    position_by_symbol = {row["symbol"]: row for row in positions.iter_rows(named=True)} if not positions.is_empty() else {}
    rows: list[dict[str, Any]] = []
    for target in live_targets.iter_rows(named=True):
        symbol = str(target["symbol"]).zfill(6)
        position = position_by_symbol.get(symbol, {})
        state = choose_price_and_state(symbol, target, snapshot_lookup, target_lookup, latest_lookup, position)
        row = state["row"]
        recalc_price = to_float(state["price"])
        raw_target_weight = to_float(target.get("raw_target_weight"))
        raw_target_amount = raw_target_weight * ACCOUNT_SIZE_CNY
        raw_target_shares = floor_to_lot_shares(raw_target_amount, recalc_price)
        prev_shares = int(position.get("current_shares") or target.get("prev_shares") or 0)
        is_component = bool_from_sources(target, row, "latest_known_component", "is_index_component", True)
        is_research_eligible = bool_from_sources(
            target,
            row,
            "latest_known_research_eligible",
            "eligible_research_row",
            True,
        )
        is_st = bool_from_sources(target, row, "latest_known_st", "is_st", False)
        is_suspended = bool_from_sources(target, row, "latest_known_suspended", "is_suspended", False)
        target_shares = raw_target_shares
        sidecar_reason = ""
        if raw_target_weight > 0 and not is_component:
            target_shares = min(raw_target_shares, prev_shares)
            if target_shares < raw_target_shares:
                sidecar_reason = "not_index_component_no_buy_add_recalc"
        rows.append(
            {
                "target_date": target.get("target_date"),
                "symbol": symbol,
                "code_name": target.get("code_name") or row.get("code_name") or position.get("code_name") or "",
                "industry": target.get("industry") or position.get("industry") or "",
                "prev_shares": prev_shares,
                "raw_target_weight": raw_target_weight,
                "raw_target_amount_cny": raw_target_amount,
                "raw_target_shares_recalc": raw_target_shares,
                "target_shares_recalc": target_shares,
                "target_amount_recalc_cny": target_shares * recalc_price,
                "target_weight_recalc": (target_shares * recalc_price / ACCOUNT_SIZE_CNY) if ACCOUNT_SIZE_CNY else 0.0,
                "live_sidecar_target_shares": int(target.get("sidecar_target_shares") or 0),
                "live_sidecar_target_weight": to_float(target.get("sidecar_target_weight")),
                "shares_delta_vs_live_target": target_shares - int(target.get("sidecar_target_shares") or 0),
                "component_target_sidecar_reason_recalc": sidecar_reason,
                "recalc_price": recalc_price,
                "recalc_price_source": state["price_source"],
                "state_source": state["state_source"],
                "one_lot_amount_cny": recalc_price * BOARD_LOT_SHARES,
                "zero_lot_target_recalc": raw_target_weight > 0 and target_shares <= 0,
                "is_component_for_recalc": is_component,
                "is_research_eligible_for_recalc": is_research_eligible,
                "is_st_for_recalc": is_st,
                "is_suspended_for_recalc": is_suspended,
                "is_oneword_limit_up_for_recalc": bool_from_sources(
                    target, row, "latest_known_oneword_limit_up", "is_oneword_limit_up", False
                ),
                "is_oneword_limit_down_for_recalc": bool_from_sources(
                    target, row, "latest_known_oneword_limit_down", "is_oneword_limit_down", False
                ),
                "adv20_turnover_for_recalc": to_float(row.get("adv20_turnover")) or to_float(target.get("adv20_turnover")),
            }
        )
    return pl.DataFrame(rows).sort(["zero_lot_target_recalc", "target_weight_recalc", "symbol"], descending=[True, True, False])


def build_orders_before_cash(recalc_targets: pl.DataFrame, positions: pl.DataFrame) -> pl.DataFrame:
    target_by_symbol = {row["symbol"]: row for row in recalc_targets.iter_rows(named=True)}
    position_by_symbol = {row["symbol"]: row for row in positions.iter_rows(named=True)} if not positions.is_empty() else {}
    symbols = sorted(set(target_by_symbol) | set(position_by_symbol))
    rows: list[dict[str, Any]] = []
    for symbol in symbols:
        target = target_by_symbol.get(symbol)
        position = position_by_symbol.get(symbol, {})
        if target is None:
            price = to_float(position.get("last_trade_open"))
            target = {
                "target_date": recalc_targets["target_date"].max() if not recalc_targets.is_empty() else None,
                "symbol": symbol,
                "code_name": position.get("code_name") or "",
                "industry": position.get("industry") or "",
                "prev_shares": int(position.get("current_shares") or 0),
                "target_shares_recalc": 0,
                "recalc_price": price,
                "recalc_price_source": "position_last_trade_open_fallback",
                "state_source": "position_only",
                "is_component_for_recalc": False,
                "is_research_eligible_for_recalc": True,
                "is_st_for_recalc": False,
                "is_suspended_for_recalc": False,
                "is_oneword_limit_up_for_recalc": False,
                "is_oneword_limit_down_for_recalc": False,
                "adv20_turnover_for_recalc": 0.0,
                "component_target_sidecar_reason_recalc": "",
            }
        prev_shares = int(position.get("current_shares") or target.get("prev_shares") or 0)
        target_shares = int(target.get("target_shares_recalc") or 0)
        delta = target_shares - prev_shares
        if delta == 0:
            continue
        side = "buy" if delta > 0 else "sell"
        desired_shares = abs(delta)
        price = to_float(target.get("recalc_price"))
        desired_amount = desired_shares * price
        status = "tradable_recalc_estimate"
        reason = ""
        risk_cap_shares = desired_shares
        adv = to_float(target.get("adv20_turnover_for_recalc"))
        adv_cap_amount = MAX_PARTICIPATION_ADV20 * adv if adv > 0 else 0.0
        adv_cap_shares = floor_to_lot_shares(adv_cap_amount, price)
        if price <= 0:
            status, reason, risk_cap_shares = "blocked_recalc", "missing_recalc_price", 0
        elif bool(target.get("is_suspended_for_recalc")):
            status, reason, risk_cap_shares = "blocked_recalc", "suspended_or_missing_open", 0
        elif side == "buy" and not bool(target.get("is_component_for_recalc")):
            status, reason, risk_cap_shares = "blocked_recalc", "not_index_component_buy", 0
        elif side == "buy" and (
            bool(target.get("is_st_for_recalc")) or not bool(target.get("is_research_eligible_for_recalc"))
        ):
            status, reason, risk_cap_shares = "blocked_recalc", "st_or_research_ineligible_buy", 0
        elif side == "buy" and bool(target.get("is_oneword_limit_up_for_recalc")):
            status, reason, risk_cap_shares = "blocked_recalc", "oneword_limit_up_buy", 0
        elif side == "sell" and bool(target.get("is_oneword_limit_down_for_recalc")):
            status, reason, risk_cap_shares = "blocked_recalc", "oneword_limit_down_sell", 0
        elif side == "buy" and adv <= 0:
            status, reason = "manual_review", "missing_adv20_turnover_for_cap"
        elif side == "buy" and desired_shares > adv_cap_shares:
            risk_cap_shares = adv_cap_shares
            if risk_cap_shares > 0:
                status, reason = "cap_limited_recalc", "adv20_participation_cap"
            else:
                status, reason, risk_cap_shares = "blocked_recalc", "zero_lot_adv_cap", 0
        rows.append(
            {
                "target_date": target.get("target_date"),
                "symbol": symbol,
                "code_name": target.get("code_name") or "",
                "industry": target.get("industry") or "",
                "side": side,
                "status_before_cash": status,
                "blocked_reason_before_cash": reason,
                "prev_shares": prev_shares,
                "target_shares_recalc": target_shares,
                "desired_shares": desired_shares,
                "risk_cap_shares": risk_cap_shares,
                "recalc_price": price,
                "recalc_price_source": target.get("recalc_price_source"),
                "state_source": target.get("state_source"),
                "desired_amount_cny": desired_amount,
                "risk_cap_amount_cny": risk_cap_shares * price,
                "adv_cap_amount_cny": adv_cap_amount,
                "adv_cap_shares": adv_cap_shares,
                "is_component_for_recalc": bool(target.get("is_component_for_recalc")),
                "is_research_eligible_for_recalc": bool(target.get("is_research_eligible_for_recalc")),
                "is_st_for_recalc": bool(target.get("is_st_for_recalc")),
                "is_suspended_for_recalc": bool(target.get("is_suspended_for_recalc")),
                "component_target_sidecar_reason_recalc": target.get("component_target_sidecar_reason_recalc") or "",
            }
        )
    return pl.DataFrame(rows).sort(["side", "desired_amount_cny", "symbol"], descending=[False, True, False]) if rows else pl.DataFrame()


def apply_cash_limit(
    orders: pl.DataFrame,
    positions: pl.DataFrame,
    recalc_targets: pl.DataFrame,
    *,
    snapshot_cash_cny: float | None = None,
    snapshot_cash_column: str = "",
) -> tuple[pl.DataFrame, dict[str, Any]]:
    if orders.is_empty():
        return orders, {
            "cash_source": "none",
            "cash_start_cny": 0.0,
            "cash_after_sells_cny": 0.0,
            "cash_buffer_cny": ACCOUNT_SIZE_CNY * CASH_BUFFER_RATIO,
            "buy_budget_after_buffer_cny": 0.0,
        }
    target_price = {row["symbol"]: to_float(row["recalc_price"]) for row in recalc_targets.iter_rows(named=True)}
    current_value = 0.0
    for row in positions.iter_rows(named=True):
        price = target_price.get(row["symbol"], to_float(row.get("last_trade_open")))
        current_value += int(row.get("current_shares") or 0) * price
    if BROKER_CASH_CNY:
        cash_start = to_float(BROKER_CASH_CNY)
        cash_source = "broker_cash_env_override"
    elif snapshot_cash_cny is not None and snapshot_cash_cny > 0:
        cash_start = snapshot_cash_cny
        cash_source = f"external_snapshot:{snapshot_cash_column}"
    else:
        cash_start = max(0.0, ACCOUNT_SIZE_CNY - current_value)
        cash_source = "synthetic_account_minus_marked_positions"

    rows = [dict(row) for row in orders.iter_rows(named=True)]
    sell_proceeds = sum(
        to_float(row["risk_cap_amount_cny"])
        for row in rows
        if row["side"] == "sell" and row["status_before_cash"] != "blocked_recalc"
    )
    cash_after_sells = cash_start + sell_proceeds
    cash_buffer = ACCOUNT_SIZE_CNY * CASH_BUFFER_RATIO
    remaining_buy_budget = max(0.0, cash_after_sells - cash_buffer)

    for row in sorted(rows, key=lambda item: (item["side"] != "sell", -to_float(item["desired_amount_cny"]), item["symbol"])):
        row["cash_source"] = cash_source
        row["cash_start_cny"] = cash_start
        row["cash_after_sells_cny"] = cash_after_sells
        row["cash_buffer_cny"] = cash_buffer
        row["buy_budget_before_order_cny"] = remaining_buy_budget if row["side"] == "buy" else None
        final_status = row["status_before_cash"]
        final_reason = row["blocked_reason_before_cash"]
        final_shares = int(row["risk_cap_shares"])
        if row["side"] == "buy" and final_status != "blocked_recalc":
            price = to_float(row["recalc_price"])
            wanted_amount = final_shares * price
            if wanted_amount > remaining_buy_budget:
                cash_shares = floor_to_lot_shares(remaining_buy_budget, price)
                cash_shares = min(cash_shares, final_shares)
                if cash_shares > 0:
                    final_status = "cash_limited_recalc"
                    final_reason = "cash_after_buffer_limited"
                    final_shares = cash_shares
                else:
                    final_status = "blocked_recalc"
                    final_reason = "insufficient_cash_after_buffer"
                    final_shares = 0
            remaining_buy_budget -= final_shares * price
        row["final_status"] = final_status
        row["final_blocked_reason"] = final_reason
        row["final_shares"] = final_shares
        row["final_amount_cny"] = final_shares * to_float(row["recalc_price"])
        row["unfilled_shares_recalc"] = max(0, int(row["desired_shares"]) - final_shares)
        row["unfilled_amount_cny"] = row["unfilled_shares_recalc"] * to_float(row["recalc_price"])
        row["buy_budget_after_order_cny"] = remaining_buy_budget if row["side"] == "buy" else None

    out = pl.DataFrame(rows).sort(["side", "final_amount_cny", "symbol"], descending=[False, True, False])
    cash_summary = {
        "cash_source": cash_source,
        "cash_start_cny": cash_start,
        "current_position_value_cny": current_value,
        "sell_proceeds_estimate_cny": sell_proceeds,
        "cash_after_sells_cny": cash_after_sells,
        "cash_buffer_ratio": CASH_BUFFER_RATIO,
        "cash_buffer_cny": cash_buffer,
        "buy_budget_after_buffer_cny": max(0.0, cash_after_sells - cash_buffer),
        "buy_final_amount_cny": to_float(out.filter(pl.col("side") == "buy").select(pl.col("final_amount_cny").sum()).item())
        if not out.filter(pl.col("side") == "buy").is_empty()
        else 0.0,
    }
    return out, cash_summary


def compare_orders(recalc_orders: pl.DataFrame, live_estimated_orders: pl.DataFrame) -> pl.DataFrame:
    if recalc_orders.is_empty() and live_estimated_orders.is_empty():
        return pl.DataFrame()
    left = recalc_orders.select(
        "target_date",
        "symbol",
        "side",
        pl.col("target_shares_recalc").alias("recalc_target_shares"),
        pl.col("desired_shares").alias("recalc_desired_shares"),
        pl.col("final_shares").alias("recalc_final_shares"),
        pl.col("recalc_price"),
        pl.col("final_status"),
        pl.col("final_blocked_reason"),
    )
    right = live_estimated_orders.select(
        "target_date",
        "symbol",
        "side",
        pl.col("target_shares").alias("live_target_shares"),
        pl.col("desired_shares").alias("live_desired_shares"),
        pl.col("reference_price").alias("live_reference_price"),
        pl.col("estimated_status").alias("live_status"),
        pl.col("estimated_blocked_reason").alias("live_blocked_reason"),
    )
    return (
        left.join(right, on=["target_date", "symbol", "side"], how="full")
        .with_columns(
            (pl.col("recalc_target_shares").fill_null(0) - pl.col("live_target_shares").fill_null(0)).alias(
                "target_shares_diff"
            ),
            (pl.col("recalc_desired_shares").fill_null(0) - pl.col("live_desired_shares").fill_null(0)).alias(
                "desired_shares_diff"
            ),
            (pl.col("recalc_price").fill_null(0.0) - pl.col("live_reference_price").fill_null(0.0)).alias(
                "price_diff"
            ),
        )
        .with_columns(
            (
                (pl.col("target_shares_diff") != 0)
                | (pl.col("desired_shares_diff") != 0)
                | (pl.col("price_diff").abs() > 1e-9)
            ).alias("share_or_price_changed")
        )
        .sort(["share_or_price_changed", "symbol"], descending=[True, False])
    )


def summarize_status(orders: pl.DataFrame) -> pl.DataFrame:
    if orders.is_empty():
        return pl.DataFrame()
    return (
        orders.group_by(["side", "final_status", "final_blocked_reason"])
        .agg(
            pl.len().alias("orders"),
            pl.col("desired_amount_cny").sum().alias("desired_amount_cny_sum"),
            pl.col("final_amount_cny").sum().alias("final_amount_cny_sum"),
            pl.col("unfilled_amount_cny").sum().alias("unfilled_amount_cny_sum"),
        )
        .sort(["side", "orders"], descending=[False, True])
    )


def build_quality(summary: dict[str, Any]) -> pl.DataFrame:
    rows = [
        {
            "checkpoint": "live_target_inputs_available",
            "status": "pass" if summary["live_target_count"] > 0 else "fail",
            "value": str(summary["live_target_count"]),
            "expected": ">0",
            "note": "订单重算必须有live target输入。",
        },
        {
            "checkpoint": "target_date_matches_live",
            "status": "pass" if summary["target_date"] == summary["live_proposed_target_date"] else "fail",
            "value": f"{summary['target_date']} vs {summary['live_proposed_target_date']}",
            "expected": "equal",
            "note": "重算订单必须对应live建议执行日。",
        },
        {
            "checkpoint": "price_snapshot_available",
            "status": "pass" if summary["price_snapshot_available"] else "warn",
            "value": summary["price_snapshot_source"],
            "expected": "external or target-date panel snapshot",
            "note": "没有目标日价格快照时，本阶段仍是估算重算，不能发真实委托。",
        },
        {
            "checkpoint": "no_blocked_recalc_orders",
            "status": "pass" if summary["blocked_order_count"] == 0 else "warn",
            "value": str(summary["blocked_order_count"]),
            "expected": "0",
            "note": "阻断订单需要人工复核；若是实盘前快照，不能提交。",
        },
        {
            "checkpoint": "no_cash_limited_orders",
            "status": "pass" if summary["cash_limited_order_count"] == 0 else "warn",
            "value": str(summary["cash_limited_order_count"]),
            "expected": "0",
            "note": "现金限制意味着目标组合无法完整落地。",
        },
        {
            "checkpoint": "no_not_index_component_buy",
            "status": "pass" if summary["not_index_component_buy_order_count"] == 0 else "fail",
            "value": str(summary["not_index_component_buy_order_count"]),
            "expected": "0",
            "note": "目标层sidecar后不应存在最新已知非成分买入/加仓。",
        },
        {
            "checkpoint": "compare_to_live_estimated_clean_without_snapshot",
            "status": "pass" if summary["price_snapshot_available"] or summary["changed_vs_live_estimated_rows"] == 0 else "warn",
            "value": str(summary["changed_vs_live_estimated_rows"]),
            "expected": "0 if no external snapshot",
            "note": "没有外部快照时，重算结果应与live估算订单基本一致。",
        },
        {
            "checkpoint": "broker_cash_position_manual_required",
            "status": "manual",
            "value": summary["cash_source"],
            "expected": "broker verified",
            "note": "现金和持仓仍需券商账户或人工确认，本脚本只做dry-run。",
        },
        {
            "checkpoint": "no_signal_parameter_change",
            "status": "pass",
            "value": "no signal/threshold change",
            "expected": "no signal/threshold change",
            "note": "本阶段只重算订单，不改alpha、过滤阈值或仓位上限。",
        },
    ]
    return pl.DataFrame(rows)


def _markdown_all(frame: pl.DataFrame, max_rows: int = 80) -> str:
    if frame.is_empty():
        return "无数据"
    return markdown_table(frame, frame.columns, max_rows=max_rows)


def write_report(
    summary: dict[str, Any],
    quality: pl.DataFrame,
    recalc_targets: pl.DataFrame,
    recalc_orders: pl.DataFrame,
    status_summary: pl.DataFrame,
    order_compare: pl.DataFrame,
    paths: dict[str, Path],
) -> Path:
    failed = quality.filter(pl.col("status") == "fail")
    warned = quality.filter(pl.col("status") == "warn")
    manual = quality.filter(pl.col("status") == "manual")
    changed = order_compare.filter(pl.col("share_or_price_changed")) if not order_compare.is_empty() else order_compare
    report_path = paths["report"]
    lines = [
        "# 股票震荡liquid_q3 30万 order recalculation dry-run v1",
        "",
        f"- 记录时间：{datetime.now().strftime('%Y-%m-%d %H:%M CST')}",
        "- 当前研究线：股票震荡独立策略研究，不接入第78。",
        "- 本阶段性质：把live target按可用价格/持仓/现金重新计算订单；不新增信号、不调参数、不发真实委托。",
        f"- live建议执行日：`{summary['target_date']}`。",
        f"- 价格来源状态：`{summary['price_snapshot_state']}`。",
        f"- recalc状态：`{summary['order_recalc_state']}`。",
        "- A/B判断：执行链路dry-run，不做第78 A/B/C。",
        "",
        "## 外部调研判断",
        "",
        "- 成熟框架不会直接把目标权重当订单，而是用当前价格、费用/现金约束和持仓差额重算订单。",
        "- 没有目标日真实快照时，重算只能作为paper估算，不能作为券商委托。",
        "- 本阶段因此保留价格来源和现金来源标签，让pre-live能识别黄灯原因。",
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
            f"- live目标`{summary['live_target_count']}`只，重算后目标`{summary['recalc_target_count']}`只。",
            f"- 重算订单`{summary['order_count']}`行，买入`{summary['buy_order_count']}`行，卖出`{summary['sell_order_count']}`行。",
            f"- 阻断`{summary['blocked_order_count']}`行，现金限制`{summary['cash_limited_order_count']}`行，手数/价格变化`{summary['changed_vs_live_estimated_rows']}`行。",
            f"- 估算成交金额`{summary['final_amount_sum_cny']:,.0f}`元，其中买入`{summary['buy_final_amount_cny']:,.0f}`元、卖出`{summary['sell_final_amount_cny']:,.0f}`元。",
            f"- 现金来源：`{summary['cash_source']}`；起始现金`{summary['cash_start_cny']:,.0f}`元，卖出后现金`{summary['cash_after_sells_cny']:,.0f}`元，现金缓冲`{summary['cash_buffer_cny']:,.0f}`元。",
            "",
            "## 结论",
            "",
            "- 当前结论：订单重算链路可以跑通，但仍不是可实盘订单。",
            "- 主要原因：当前没有外部/目标日价格快照，价格来源仍回落到信号日收盘或持仓最后开盘价。",
            "- 下一步如果要更接近真实交易，需要接入券商/行情快照文件，至少包含`symbol, price, is_suspended, is_st, is_index_component, eligible_research_row, adv20_turnover`。",
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
            "## 订单状态汇总",
            "",
            _markdown_all(status_summary),
            "",
            "## 与live估算订单差异",
            "",
            _markdown_all(changed),
            "",
            "## 重算订单",
            "",
            markdown_table(
                recalc_orders,
                [
                    "target_date",
                    "symbol",
                    "code_name",
                    "industry",
                    "side",
                    "final_status",
                    "final_blocked_reason",
                    "prev_shares",
                    "target_shares_recalc",
                    "desired_shares",
                    "final_shares",
                    "recalc_price",
                    "final_amount_cny",
                    "unfilled_amount_cny",
                ],
                max_rows=120,
            ),
            "",
            "## 重算目标",
            "",
            markdown_table(
                recalc_targets,
                [
                    "target_date",
                    "symbol",
                    "code_name",
                    "industry",
                    "raw_target_weight",
                    "prev_shares",
                    "target_shares_recalc",
                    "live_sidecar_target_shares",
                    "shares_delta_vs_live_target",
                    "recalc_price",
                    "recalc_price_source",
                    "is_component_for_recalc",
                    "is_st_for_recalc",
                ],
                max_rows=120,
            ),
            "",
            "## 运行前过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：本阶段只做订单重算，不改变策略信号、阈值或仓位上限。",
            "",
            "## 运行后过拟合反思",
            "",
            "- 判断：否。",
            "- 原因：重算结果只暴露价格/现金/可交易状态约束，不按收益调参。",
            "",
            "## 运行前继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：live target若不能重算成订单，策略仍停留在目标层，不能进入准实盘审计。",
            "",
            "## 运行后继续价值反思",
            "",
            "- 判断：是。",
            "- 原因：dry-run已经把价格快照缺失、现金来源、阻断状态和订单差异显式化，下一步可以接券商/行情快照。",
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
    live_summary = json.loads((LIVE_TARGET_DIR / f"{LIVE_TARGET_PREFIX}_summary.json").read_text(encoding="utf-8"))
    live_targets = read_csv_with_symbol(LIVE_TARGET_DIR / f"{LIVE_TARGET_PREFIX}_live_targets.csv")
    live_estimated_orders = read_csv_with_symbol(LIVE_TARGET_DIR / f"{LIVE_TARGET_PREFIX}_estimated_orders.csv")
    repository_positions = read_csv_with_symbol(LIVE_TARGET_DIR / f"{LIVE_TARGET_PREFIX}_positions.csv")
    stock_df, _benchmark_df = load_panels()
    snapshot_frame, snapshot_lookup, snapshot_source = read_optional_snapshot()
    positions, position_source = build_positions_from_snapshot(snapshot_frame, repository_positions)
    snapshot_cash_cny, snapshot_cash_column = extract_snapshot_cash(snapshot_frame)
    target_date = parse_date(live_summary.get("proposed_target_date"))
    signal_date = parse_date(live_summary.get("latest_signal_date"))
    target_lookup, latest_lookup = build_stock_lookup(stock_df, target_date, signal_date)
    recalc_targets = build_recalc_targets(live_targets, positions, snapshot_lookup, target_lookup, latest_lookup)
    orders_before_cash = build_orders_before_cash(recalc_targets, positions)
    recalc_orders, cash_summary = apply_cash_limit(
        orders_before_cash,
        positions,
        recalc_targets,
        snapshot_cash_cny=snapshot_cash_cny,
        snapshot_cash_column=snapshot_cash_column,
    )
    order_compare = compare_orders(recalc_orders, live_estimated_orders)
    status_summary = summarize_status(recalc_orders)
    price_source_summary = (
        recalc_targets.group_by(["recalc_price_source", "state_source"])
        .agg(pl.len().alias("targets"), pl.col("target_amount_recalc_cny").sum().alias("target_amount_cny_sum"))
        .sort("targets", descending=True)
    )

    blocked = recalc_orders.filter(pl.col("final_status") == "blocked_recalc") if not recalc_orders.is_empty() else recalc_orders
    cash_limited = recalc_orders.filter(pl.col("final_status") == "cash_limited_recalc") if not recalc_orders.is_empty() else recalc_orders
    buy_orders = recalc_orders.filter(pl.col("side") == "buy") if not recalc_orders.is_empty() else recalc_orders
    sell_orders = recalc_orders.filter(pl.col("side") == "sell") if not recalc_orders.is_empty() else recalc_orders
    not_index_buy = (
        recalc_orders.filter((pl.col("side") == "buy") & (pl.col("is_component_for_recalc") == False))  # noqa: E712
        if not recalc_orders.is_empty()
        else recalc_orders
    )
    changed = order_compare.filter(pl.col("share_or_price_changed")) if not order_compare.is_empty() else order_compare
    has_snapshot = bool(snapshot_lookup) or bool(target_lookup)
    price_snapshot_state = "snapshot_or_target_panel_available" if has_snapshot else "missing_target_date_snapshot"
    summary: dict[str, Any] = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "target_date": target_date,
        "live_proposed_target_date": parse_date(live_summary.get("proposed_target_date")),
        "live_latest_signal_date": parse_date(live_summary.get("latest_signal_date")),
        "account_size_cny": ACCOUNT_SIZE_CNY,
        "cash_buffer_ratio": CASH_BUFFER_RATIO,
        "price_snapshot_source": snapshot_source,
        "price_snapshot_available": has_snapshot,
        "price_snapshot_state": price_snapshot_state,
        "external_snapshot_rows": snapshot_frame.height if not snapshot_frame.is_empty() else 0,
        "position_source": position_source,
        "position_count": positions.height,
        "repository_position_count": repository_positions.height,
        "snapshot_cash_column": snapshot_cash_column,
        "snapshot_cash_cny": snapshot_cash_cny,
        "target_date_panel_rows": len(target_lookup),
        "live_target_count": live_targets.height,
        "recalc_target_count": recalc_targets.filter(pl.col("target_weight_recalc") > 0).height,
        "zero_lot_target_count": recalc_targets.filter(pl.col("zero_lot_target_recalc")).height,
        "target_shares_changed_vs_live_rows": recalc_targets.filter(pl.col("shares_delta_vs_live_target") != 0).height,
        "order_count": recalc_orders.height,
        "buy_order_count": buy_orders.height,
        "sell_order_count": sell_orders.height,
        "blocked_order_count": blocked.height,
        "cash_limited_order_count": cash_limited.height,
        "not_index_component_buy_order_count": not_index_buy.height,
        "changed_vs_live_estimated_rows": changed.height,
        "desired_amount_sum_cny": to_float(recalc_orders["desired_amount_cny"].sum()) if not recalc_orders.is_empty() else 0.0,
        "final_amount_sum_cny": to_float(recalc_orders["final_amount_cny"].sum()) if not recalc_orders.is_empty() else 0.0,
        "unfilled_amount_sum_cny": to_float(recalc_orders["unfilled_amount_cny"].sum()) if not recalc_orders.is_empty() else 0.0,
        "buy_final_amount_cny": to_float(buy_orders["final_amount_cny"].sum()) if not buy_orders.is_empty() else 0.0,
        "sell_final_amount_cny": to_float(sell_orders["final_amount_cny"].sum()) if not sell_orders.is_empty() else 0.0,
        **cash_summary,
    }
    quality = build_quality(summary)
    summary["quality_pass_count"] = quality.filter(pl.col("status") == "pass").height
    summary["quality_warn_count"] = quality.filter(pl.col("status") == "warn").height
    summary["quality_fail_count"] = quality.filter(pl.col("status") == "fail").height
    summary["quality_manual_count"] = quality.filter(pl.col("status") == "manual").height
    if summary["quality_fail_count"] > 0:
        summary["order_recalc_state"] = "red_recalc_failed"
    elif not summary["price_snapshot_available"]:
        summary["order_recalc_state"] = "yellow_recalc_needs_target_snapshot"
    elif summary["quality_warn_count"] > 0 or summary["quality_manual_count"] > 0:
        summary["order_recalc_state"] = "yellow_recalc_manual_review"
    else:
        summary["order_recalc_state"] = "green_recalc_clean_for_paper"

    paths = {
        "report": OUTPUT_DIR / f"{PREFIX}_report.md",
        "summary": OUTPUT_DIR / f"{PREFIX}_summary.json",
        "recalc_targets": OUTPUT_DIR / f"{PREFIX}_recalc_targets.csv",
        "recalc_orders": OUTPUT_DIR / f"{PREFIX}_recalc_orders.csv",
        "orders_before_cash": OUTPUT_DIR / f"{PREFIX}_orders_before_cash.csv",
        "order_compare": OUTPUT_DIR / f"{PREFIX}_order_compare.csv",
        "status_summary": OUTPUT_DIR / f"{PREFIX}_status_summary.csv",
        "price_source_summary": OUTPUT_DIR / f"{PREFIX}_price_source_summary.csv",
        "quality": OUTPUT_DIR / f"{PREFIX}_quality_checkpoints.csv",
        "meta": OUTPUT_DIR / f"{PREFIX}_meta.json",
    }
    recalc_targets.write_csv(paths["recalc_targets"])
    recalc_orders.write_csv(paths["recalc_orders"])
    orders_before_cash.write_csv(paths["orders_before_cash"])
    order_compare.write_csv(paths["order_compare"])
    status_summary.write_csv(paths["status_summary"])
    price_source_summary.write_csv(paths["price_source_summary"])
    quality.write_csv(paths["quality"])
    write_json(paths["summary"], summary)
    write_json(
        paths["meta"],
        {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "live_summary": str(LIVE_TARGET_DIR / f"{LIVE_TARGET_PREFIX}_summary.json"),
            "price_snapshot_path": PRICE_SNAPSHOT_PATH,
            "research_sources": RESEARCH_SOURCES,
            "note": "Order recalculation dry-run only; no broker order is submitted.",
        },
    )
    report_path = write_report(summary, quality, recalc_targets, recalc_orders, status_summary, order_compare, paths)
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
