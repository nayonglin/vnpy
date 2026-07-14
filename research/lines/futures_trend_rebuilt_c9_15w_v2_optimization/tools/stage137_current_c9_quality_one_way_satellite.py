from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import date, datetime
from enum import Enum
import hashlib
import importlib
import io
import json
import math
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd


_SELECTOR_REQUIRED_COLUMNS = {
    "requested_start_month",
    "open_trade_id",
    "close_trade_id",
    "vt_symbol",
    "direction",
    "entry_date",
    "entry_price",
    "exit_date",
    "exit_price",
    "entry_context",
    "layer_kind",
    "ai_product_pool_allowed",
    "ai_product_pool_rank",
    "selected_volume",
    "volume",
}
_SELECTOR_NUMERIC_COLUMNS = (
    "ai_product_pool_allowed",
    "ai_product_pool_rank",
    "selected_volume",
    "volume",
)
_OPEN_GROUP_IDENTITY_COLUMNS = (
    "vt_symbol",
    "direction",
    "entry_date",
    "entry_price",
    "entry_context",
    "layer_kind",
    "ai_product_pool_allowed",
    "ai_product_pool_rank",
    "selected_volume",
)
_REQUESTED_START_MONTH_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_OPEN_GROUP_OUTPUT_COLUMNS = [
    "requested_start_month",
    "open_trade_id",
    "vt_symbol",
    "direction",
    "entry_date",
    "entry_price",
    "base_open_volume",
    "close_trade_ids",
    "close_matched_volumes",
    "satellite_open_volume",
]
_ORDER_OUTPUT_COLUMNS = [
    "requested_start_month",
    "open_trade_id",
    "base_open_trade_id",
    "base_close_trade_id",
    "base_trade_id",
    "vt_symbol",
    "direction",
    "trade_datetime",
    "trade_price",
    "satellite_delta",
    "base_matched_volume",
    "base_remaining_volume",
    "satellite_target_volume",
]
_OPEN_MARGIN_GATE_REQUIRED_COLUMNS = {
    "requested_satellite_delta",
    "c9_projected_total_margin_after",
    "satellite_margin_after_proposed",
    "is_open_event",
}
_LEDGER_BASE_REQUIRED_COLUMNS = {"date", "account_equity", "total_margin_exact"}
_LEDGER_PRICE_REQUIRED_COLUMNS = {"date", "vt_symbol", "pre_close", "close_price"}
_SATELLITE_DAILY_ADDITIONAL_COLUMNS = [
    "satellite_gross_pnl",
    "satellite_slippage",
    "satellite_commission",
    "satellite_net_pnl",
    "satellite_cumulative_net_pnl",
    "satellite_equity",
    "combined_equity",
    "prior_combined_equity",
    "satellite_margin",
    "aggregate_broker10_margin",
    "aggregate_broker10_to_prior_combined_equity_pct",
    "aggregate_broker10_to_current_combined_equity_pct",
    "satellite_held_contract_count",
    "satellite_requested_order_count",
    "satellite_executed_order_count",
]
_REPLAYED_ORDER_ADDITIONAL_COLUMNS = [
    "requested_satellite_delta",
    "is_open_event",
    "executed_satellite_delta",
    "satellite_margin_after_proposed",
    "proposed_broker10_pct",
    "margin_gate_blocked",
    "blocked_lifecycle",
    "slippage",
    "commission",
]
_LEDGER_ORDER_BASE_REQUIRED_COLUMNS = {
    "requested_start_month",
    "base_trade_id",
    "open_trade_id",
    "vt_symbol",
    "direction",
    "trade_datetime",
    "trade_price",
    "satellite_delta",
}
_LEDGER_ORDER_REQUIRED_COLUMNS = _LEDGER_ORDER_BASE_REQUIRED_COLUMNS | {
    "c9_projected_total_margin_after",
    "estimated_equity",
}
_LEDGER_SPEC_FIELDS = ("size", "margin_ratio", "slippage", "rate")
_LEDGER_CAPITAL = 150_000.0
_LEDGER_BROKER_MULTIPLIER = 1.10

CANARY_STARTS = ("2020-01", "2022-01", "2022-07", "2026-01")
ANALYSIS_END = pd.Timestamp("2026-06-30")
COST_MULTIPLIERS = (1.0,)
IDENTITY_TOLERANCE = 1e-6

_REPO_ROOT = Path(__file__).resolve().parents[4]
_EXAMPLES_DIR = _REPO_ROOT / "examples" / "portfolio_backtesting"
_LINE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = _LINE_DIR / "outputs" / "stage137_current_c9_quality_one_way_satellite"
FAILURE_DIR = _LINE_DIR / "outputs" / "stage137_current_c9_quality_one_way_satellite_failures"
_FAILURE_CONTEXT: dict[str, str] = {
    "requested_start_month": "",
    "phase": "startup",
}
CURRENT_AI_PATH = (
    _EXAMPLES_DIR
    / "backtest_outputs"
    / "qmt_roll_stage182_ai_product_pool_live_inference_combined_stage78_eligibility_stage182_ai_product_pool_live_inference_v1.csv"
)
_FULL_MARKET_LINE_DIR = (
    _REPO_ROOT / "research" / "lines" / "futures_trend_full_market_ai_filter_002risk"
)
CURRENT_AI_GOLDEN_DAILY_PATH = (
    _FULL_MARKET_LINE_DIR
    / "outputs"
    / "stage006_current_ai_paired_bottom_veto_engine"
    / "full_market_ai002_stage006_current_ai_paired_bottom_veto_engine_a0_daily_stage006_current_ai_paired_bottom_veto_engine_v1.csv.gz"
)
CURRENT_AI_GOLDEN_ELIGIBILITY_PATH = (
    _FULL_MARKET_LINE_DIR
    / "outputs"
    / "stage006_current_ai_paired_bottom_veto_engine"
    / "full_market_ai002_stage006_current_ai_paired_bottom_veto_engine_a0_eligibility_stage006_current_ai_paired_bottom_veto_engine_v1.csv"
)
CURRENT_AI_EXPECTED_SHA256 = "fc50e035cd66b65e94261ef70476747daa94ae73071d0f4d7206ff7b644271fc"
CURRENT_AI_EXPECTED_ROWS = 504
CURRENT_AI_EXPECTED_EVAL_DATES = (
    "2019-12-31",
    "2022-01-28", "2022-02-28", "2022-03-31", "2022-04-29", "2022-05-31", "2022-06-30",
    "2022-07-29", "2022-08-31", "2022-09-30", "2022-10-31", "2022-11-30", "2022-12-30",
    "2023-01-31", "2023-02-28", "2023-03-31", "2023-04-28", "2023-05-31", "2023-06-30",
    "2023-07-31", "2023-08-31", "2023-09-28", "2023-10-31", "2023-11-30", "2023-12-29",
    "2024-01-31", "2024-02-29", "2024-03-29", "2024-04-30", "2024-05-31", "2024-06-28",
    "2024-07-31", "2024-08-30", "2024-09-30", "2024-10-31", "2024-11-29", "2024-12-31",
    "2025-01-27", "2025-02-28", "2025-03-31", "2025-04-30", "2025-05-30", "2025-06-30",
    "2025-07-31", "2025-08-29", "2025-09-30", "2025-10-31", "2025-11-28", "2025-12-31",
    "2026-01-30", "2026-02-27", "2026-03-31", "2026-04-30", "2026-05-29", "2026-06-30",
)
_STATIC_SOURCE_PATHS = (
    CURRENT_AI_PATH,
    CURRENT_AI_GOLDEN_DAILY_PATH,
    CURRENT_AI_GOLDEN_ELIGIBILITY_PATH,
    _EXAMPLES_DIR / "analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow.py",
    _EXAMPLES_DIR / "analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine.py",
    _EXAMPLES_DIR / "analyze_qmt_roll_stage830_stage827_c2_broker10_margin_cap.py",
    _EXAMPLES_DIR / "analyze_qmt_roll_stage513_stage208_exact_position_margin_audit.py",
    _EXAMPLES_DIR / "analyze_qmt_roll_stage719_official_winner_trade_forensics.py",
    _EXAMPLES_DIR / "qmt_roll_portfolio_strategy.py",
    _EXAMPLES_DIR / "qmt_roll_official_live_config.py",
    _EXAMPLES_DIR / "qmt_universe.py",
    _EXAMPLES_DIR / "contract_metadata.py",
    _EXAMPLES_DIR / "main_contract_mapping.py",
    Path(__file__).resolve(),
)


def _require_columns(frame: pd.DataFrame, required: set[str]) -> None:
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"missing required columns: {', '.join(missing)}")


def _require_finite(frame: pd.DataFrame, columns: tuple[str, ...]) -> None:
    for column in columns:
        values = pd.to_numeric(frame[column], errors="coerce")
        if not np.isfinite(values).all():
            raise ValueError(f"non-finite required value: {column}")


def _require_nonempty_text(frame: pd.DataFrame, columns: tuple[str, ...]) -> None:
    for column in columns:
        values = frame[column]
        if values.isna().any() or values.astype(str).str.strip().eq("").any():
            raise ValueError(f"missing required identity: {column}")


def _require_requested_start_month(frame: pd.DataFrame) -> None:
    for value in frame["requested_start_month"].tolist():
        if not isinstance(value, str) or _REQUESTED_START_MONTH_PATTERN.fullmatch(value) is None:
            raise ValueError("invalid requested_start_month")


def _group_open_trade_lifecycle(closed_lots: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    group_columns = ("requested_start_month", "open_trade_id")
    for key, group in closed_lots.groupby(list(group_columns), sort=False, dropna=False):
        structural = group["entry_context"].eq("flat_entry") & group["layer_kind"].eq("base")
        if not structural.any():
            continue
        _require_nonempty_text(group, ("open_trade_id", "close_trade_id", "vt_symbol", "direction"))
        _require_finite(group, _SELECTOR_NUMERIC_COLUMNS)
        for column in _OPEN_GROUP_IDENTITY_COLUMNS:
            if group[column].nunique(dropna=False) != 1:
                raise ValueError(f"inconsistent open group identity: {column} for {key[1]}")
        if group["close_trade_id"].duplicated().any():
            raise ValueError(f"duplicate close_trade_id within open group: {key[1]}")
        group = group.sort_values(["exit_date", "close_trade_id"], kind="stable")

        selected_volume = _require_integer_scalar(group["selected_volume"].iloc[0], "selected_volume")
        close_volumes = [
            _require_integer_scalar(value, "closed-lot volume") for value in group["volume"].tolist()
        ]
        if sum(close_volumes) != selected_volume:
            raise ValueError(f"sum(volume) does not equal selected_volume for {key[1]}")
        allowed = float(pd.to_numeric(group["ai_product_pool_allowed"], errors="raise").iloc[0])
        rank = float(pd.to_numeric(group["ai_product_pool_rank"], errors="raise").iloc[0])
        if not (allowed == 1 and 1 <= rank <= 8 and selected_volume > 1):
            continue
        rows.append(
            {
                "requested_start_month": str(key[0]),
                "open_trade_id": str(key[1]),
                "vt_symbol": str(group["vt_symbol"].iloc[0]),
                "direction": str(group["direction"].iloc[0]),
                "entry_date": pd.Timestamp(group["entry_date"].iloc[0]),
                "entry_price": float(group["entry_price"].iloc[0]),
                "base_open_volume": sum(close_volumes),
                "close_trade_ids": group["close_trade_id"].astype(str).tolist(),
                "close_matched_volumes": close_volumes,
            }
        )
    result = pd.DataFrame(rows)
    if result.empty:
        return result
    return result.sort_values(["requested_start_month", "open_trade_id"], kind="stable").reset_index(drop=True)


def select_quality_open_groups(closed_lots: pd.DataFrame) -> pd.DataFrame:
    """Select qualified flat/base open groups and aggregate their close lifecycle."""
    if len(closed_lots.index) == 0:
        return pd.DataFrame(columns=_OPEN_GROUP_OUTPUT_COLUMNS)
    _require_columns(closed_lots, _SELECTOR_REQUIRED_COLUMNS)
    data = closed_lots.copy()
    _require_requested_start_month(data)
    grouped = _group_open_trade_lifecycle(data)
    if grouped.empty:
        return pd.DataFrame(columns=_OPEN_GROUP_OUTPUT_COLUMNS)
    grouped["satellite_open_volume"] = np.floor(grouped["base_open_volume"] * 0.25).astype(int)
    return grouped.loc[grouped["satellite_open_volume"].gt(0), _OPEN_GROUP_OUTPUT_COLUMNS].reset_index(drop=True)


_OPEN_GROUP_REQUIRED_COLUMNS = {
    "requested_start_month",
    "open_trade_id",
    "vt_symbol",
    "direction",
    "base_open_volume",
    "satellite_open_volume",
    "close_trade_ids",
    "close_matched_volumes",
}
_TRADE_REQUIRED_COLUMNS = {"trade_id", "datetime", "vt_symbol", "direction", "offset", "price", "volume"}


def _require_finite_scalar(value: Any, label: str) -> float:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if not np.isfinite(numeric):
        raise ValueError(f"non-finite required value: {label}")
    return float(numeric)


def _require_integer_scalar(value: Any, label: str, *, allow_zero: bool = False) -> int:
    numeric = _require_finite_scalar(value, label)
    minimum_valid = numeric >= 0 if allow_zero else numeric > 0
    if not minimum_valid or not numeric.is_integer():
        qualifier = "non-negative" if allow_zero else "positive"
        raise ValueError(f"{qualifier} integer {label} required")
    return int(numeric)


def apply_open_margin_gate(
    candidate_orders: pd.DataFrame,
    prior_combined_equity: float,
    broker_multiplier: float = 1.10,
) -> pd.DataFrame:
    """Apply the frozen broker-margin limit to exactly one proposed open event."""
    _require_columns(candidate_orders, _OPEN_MARGIN_GATE_REQUIRED_COLUMNS)
    if len(candidate_orders.index) != 1 or candidate_orders.iloc[0]["is_open_event"] != 1:
        raise ValueError("apply_open_margin_gate requires exactly one open event")

    prior_equity = _require_finite_scalar(prior_combined_equity, "PIT margin input: prior_combined_equity")
    multiplier = _require_finite_scalar(broker_multiplier, "PIT margin input: broker_multiplier")
    row = candidate_orders.iloc[0]
    requested_delta = _require_integer_scalar(
        abs(_require_finite_scalar(row["requested_satellite_delta"], "requested_satellite_delta")),
        "requested_satellite_delta",
    )
    if float(row["requested_satellite_delta"]) < 0:
        requested_delta = -requested_delta
    c9_margin = _require_finite_scalar(
        row["c9_projected_total_margin_after"], "PIT margin input: c9_projected_total_margin_after"
    )
    satellite_margin = _require_finite_scalar(
        row["satellite_margin_after_proposed"], "PIT margin input: satellite_margin_after_proposed"
    )
    if prior_equity <= 0.0 or multiplier <= 0.0 or c9_margin < 0.0 or satellite_margin < 0.0:
        raise ValueError("non-finite PIT margin input")

    proposed_pct = (c9_margin + satellite_margin) * multiplier / prior_equity * 100.0
    if not np.isfinite(proposed_pct):
        raise ValueError("non-finite PIT margin input")
    blocked = int(proposed_pct > 100.0 and not math.isclose(proposed_pct, 100.0, rel_tol=0.0, abs_tol=1e-12))
    result = candidate_orders.copy()
    result["executed_satellite_delta"] = 0 if blocked else requested_delta
    result["margin_gate_blocked"] = blocked
    result["proposed_broker10_pct"] = float(proposed_pct)
    return result


def _parse_timezone_aware_datetime(value: Any) -> pd.Timestamp:
    try:
        timestamp = pd.Timestamp(value)
    except (TypeError, ValueError):
        raise ValueError("missing or invalid trade datetime") from None
    if pd.isna(timestamp):
        raise ValueError("missing or invalid trade datetime")
    if timestamp.tzinfo is None:
        raise ValueError("trade datetime must be timezone-aware")
    return timestamp.tz_convert("UTC")


def _trade_lookup(trades: pd.DataFrame) -> dict[str, dict[str, Any]]:
    _require_columns(trades, _TRADE_REQUIRED_COLUMNS)
    data = trades.copy()
    if data["trade_id"].isna().any() or data["trade_id"].astype(str).str.strip().eq("").any():
        raise ValueError("missing trade_id")
    if data["trade_id"].astype(str).duplicated().any():
        raise ValueError("trade_id is not unique")
    data["trade_datetime"] = data["datetime"].map(_parse_timezone_aware_datetime)
    _require_finite(data, ("price", "volume"))
    data["trade_direction"] = data["direction"].astype(str).str.strip().str.lower()
    if not data["trade_direction"].isin({"long", "short"}).all():
        raise ValueError("invalid trade direction")
    data["trade_offset"] = data["offset"].astype(str).str.strip().str.lower()
    if not data["trade_offset"].isin({"open", "close"}).all():
        raise ValueError("invalid trade offset")
    volumes = pd.to_numeric(data["volume"], errors="raise")
    if volumes.le(0).any() or volumes.mod(1).ne(0).any():
        raise ValueError("positive integer trade volume required")
    return {str(row["trade_id"]): row for row in data.to_dict("records")}


def _validate_raw_trade_inputs(trades: pd.DataFrame) -> None:
    _require_columns(trades, _TRADE_REQUIRED_COLUMNS)
    for row in trades.to_dict("records"):
        try:
            price = _require_finite_scalar(row["price"], "raw trade price")
        except ValueError:
            raise ValueError("positive finite raw trade price required") from None
        if price <= 0.0:
            raise ValueError("positive finite raw trade price required")
        _require_integer_scalar(row["volume"], "raw trade volume")


def _trade_for_group(
    trade_by_id: dict[str, dict[str, Any]],
    trade_id: str,
    *,
    vt_symbol: str,
    expected_open: bool,
    group_direction: str,
) -> dict[str, Any]:
    trade = trade_by_id.get(str(trade_id))
    if trade is None:
        raise ValueError(f"missing base trade: {trade_id}")
    if str(trade["vt_symbol"]) != vt_symbol:
        raise ValueError(f"base trade vt_symbol mismatch: {trade_id}")
    is_open = str(trade["trade_offset"]) == "open"
    if is_open != expected_open:
        raise ValueError(f"base trade offset mismatch: {trade_id}")
    expected_direction = group_direction if expected_open else ("short" if group_direction == "long" else "long")
    if str(trade["trade_direction"]) != expected_direction:
        raise ValueError(f"base trade direction mismatch: {trade_id}")
    return trade


def allocate_floor_mirror_orders(
    open_groups: pd.DataFrame,
    trades: pd.DataFrame,
    fraction: float = 0.25,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Allocate one floor-sized satellite sleeve over each selected FIFO lifecycle."""
    if len(open_groups.index) == 0:
        return pd.DataFrame(columns=_ORDER_OUTPUT_COLUMNS), {
            "selected_open_group_count": 0,
            "satellite_order_count": 0,
            "overclose_count": 0,
            "nonflat_final_open_group_count": 0,
            "expected_terminal_position_count": 0,
            "unexpected_terminal_position_count": 0,
            "max_terminal_position_reconciliation_error": 0.0,
            "expected_terminal_positions": {},
        }
    _require_columns(open_groups, _OPEN_GROUP_REQUIRED_COLUMNS)
    _require_requested_start_month(open_groups)
    fraction = _require_finite_scalar(fraction, "fraction")
    if not 0.0 < fraction <= 1.0:
        raise ValueError("fraction must be in (0, 1]")
    trade_by_id = _trade_lookup(trades)
    seen_open_groups: set[tuple[str, str]] = set()
    shared_close_usage: dict[tuple[str, str], float] = {}
    shared_close_groups: dict[tuple[str, str], set[tuple[str, str]]] = {}
    for group in open_groups.to_dict("records"):
        group_key = (str(group["requested_start_month"]), str(group["open_trade_id"]))
        if group_key in seen_open_groups:
            raise ValueError(f"duplicate open group identity: {group_key[1]}")
        seen_open_groups.add(group_key)
        close_ids = group["close_trade_ids"]
        close_volumes = group["close_matched_volumes"]
        if not isinstance(close_ids, list) or not isinstance(close_volumes, list) or len(close_ids) != len(close_volumes):
            raise ValueError(f"invalid close lifecycle: {group_key[1]}")
        for close_trade_id, matched_volume in zip(close_ids, close_volumes, strict=True):
            close_key = (group_key[0], str(close_trade_id))
            shared_close_usage[close_key] = shared_close_usage.get(close_key, 0.0) + _require_integer_scalar(
                matched_volume, f"close_matched_volume:{close_trade_id}"
            )
            shared_close_groups.setdefault(close_key, set()).add(group_key)
    for (_requested_start_month, close_trade_id), matched_volume in shared_close_usage.items():
        if len(shared_close_groups[(_requested_start_month, close_trade_id)]) < 2:
            continue
        close_trade = trade_by_id.get(close_trade_id)
        if close_trade is None:
            raise ValueError(f"missing base trade: {close_trade_id}")
        available_close_volume = _require_finite_scalar(
            close_trade["volume"], f"close trade volume:{close_trade_id}"
        )
        if matched_volume > available_close_volume + 1e-9:
            raise ValueError(f"shared close matched volume exceeds base close volume: {close_trade_id}")
    order_rows: list[dict[str, Any]] = []
    overclose_count = 0
    nonflat_final_open_group_count = 0
    expected_terminal_positions: dict[str, int] = {}

    for group in open_groups.to_dict("records"):
        open_trade_id = str(group["open_trade_id"])
        vt_symbol = str(group["vt_symbol"])
        direction = str(group["direction"]).strip().lower()
        if direction not in {"long", "short"}:
            raise ValueError(f"invalid open group direction: {open_trade_id}")
        base_open_volume = _require_integer_scalar(group["base_open_volume"], "base_open_volume")
        satellite_open_volume = _require_integer_scalar(
            group["satellite_open_volume"], "satellite_open_volume", allow_zero=True
        )
        expected_satellite_open = math.floor(base_open_volume * fraction)
        if satellite_open_volume != expected_satellite_open:
            raise ValueError(f"satellite open volume mismatch: {open_trade_id}")

        close_ids = group["close_trade_ids"]
        close_volumes = group["close_matched_volumes"]
        if not isinstance(close_ids, list) or not isinstance(close_volumes, list) or len(close_ids) != len(close_volumes):
            raise ValueError(f"invalid close lifecycle: {open_trade_id}")
        if len(set(map(str, close_ids))) != len(close_ids):
            raise ValueError(f"duplicate close_trade_id within open group: {open_trade_id}")
        matched_close_volumes = [
            _require_integer_scalar(value, f"close_matched_volume:{trade_id}")
            for trade_id, value in zip(close_ids, close_volumes, strict=True)
        ]
        total_matched_close_volume = sum(matched_close_volumes)
        if total_matched_close_volume > base_open_volume:
            overclose_count += 1
            raise ValueError(f"overclose open group: {open_trade_id}")
        expected_base_remaining = _require_integer_scalar(
            group.get("base_remaining_volume", 0),
            "base_remaining_volume",
            allow_zero=True,
        )
        if total_matched_close_volume + expected_base_remaining != base_open_volume:
            nonflat_final_open_group_count += 1
            raise ValueError(
                "matched close volume does not equal selected base volume; "
                f"nonflat final open group: {open_trade_id}"
            )

        open_trade = _trade_for_group(
            trade_by_id,
            open_trade_id,
            vt_symbol=vt_symbol,
            expected_open=True,
            group_direction=direction,
        )
        actual_open_volume = _require_integer_scalar(open_trade["volume"], f"open trade volume:{open_trade_id}")
        if actual_open_volume != base_open_volume:
            raise ValueError(f"base open volume mismatch: {open_trade_id}")

        sign = 1 if direction == "long" else -1
        expected_terminal_numeric = _require_finite_scalar(
            group.get("expected_terminal_satellite_position", 0),
            "expected_terminal_satellite_position",
        )
        if not expected_terminal_numeric.is_integer():
            raise ValueError(f"integer terminal satellite target required: {open_trade_id}")
        expected_terminal_position = int(expected_terminal_numeric)
        if expected_terminal_position != sign * math.floor(expected_base_remaining * fraction):
            raise ValueError(f"terminal satellite target mismatch: {open_trade_id}")
        if expected_terminal_position:
            expected_terminal_positions[open_trade_id] = expected_terminal_position
        if satellite_open_volume:
            order_rows.append(
                {
                    "requested_start_month": str(group["requested_start_month"]),
                    "open_trade_id": open_trade_id,
                    "base_open_trade_id": open_trade_id,
                    "base_close_trade_id": None,
                    "base_trade_id": open_trade_id,
                    "vt_symbol": vt_symbol,
                    "direction": direction,
                    "trade_datetime": open_trade["trade_datetime"],
                    "trade_price": float(open_trade["price"]),
                    "satellite_delta": int(sign * satellite_open_volume),
                    "base_matched_volume": base_open_volume,
                    "base_remaining_volume": base_open_volume,
                    "satellite_target_volume": int(satellite_open_volume),
                    "event_type_order": 0,
                }
            )

        close_events: list[tuple[pd.Timestamp, str, float, dict[str, Any]]] = []
        for close_trade_id, matched_volume in zip(close_ids, matched_close_volumes, strict=True):
            close_trade = _trade_for_group(
                trade_by_id,
                str(close_trade_id),
                vt_symbol=vt_symbol,
                expected_open=False,
                group_direction=direction,
            )
            available_close_volume = _require_integer_scalar(
                close_trade["volume"], f"close trade volume:{close_trade_id}"
            )
            if available_close_volume < matched_volume:
                raise ValueError(f"close trade volume below matched volume: {close_trade_id}")
            close_events.append(
                (pd.Timestamp(close_trade["trade_datetime"]), str(close_trade_id), matched_volume, close_trade)
            )
        close_events.sort(key=lambda item: (item[0], item[1]))

        remaining_base = base_open_volume
        previous_satellite_target = int(satellite_open_volume)
        for _trade_datetime, close_trade_id, matched_volume, close_trade in close_events:
            if _trade_datetime < pd.Timestamp(open_trade["trade_datetime"]):
                raise ValueError(f"close before open: {open_trade_id}")
            remaining_base -= matched_volume
            if remaining_base < 0:
                overclose_count += 1
                raise ValueError(f"overclose open group: {open_trade_id}")
            is_last_close = remaining_base == 0
            target_satellite = 0 if is_last_close else math.floor(remaining_base * fraction)
            if target_satellite > previous_satellite_target:
                raise ValueError(f"satellite target increased during close: {open_trade_id}")
            satellite_close_volume = previous_satellite_target - target_satellite
            if satellite_close_volume:
                order_rows.append(
                    {
                        "requested_start_month": str(group["requested_start_month"]),
                        "open_trade_id": open_trade_id,
                        "base_open_trade_id": open_trade_id,
                        "base_close_trade_id": close_trade_id,
                        "base_trade_id": close_trade_id,
                        "vt_symbol": vt_symbol,
                        "direction": direction,
                        "trade_datetime": close_trade["trade_datetime"],
                        "trade_price": float(close_trade["price"]),
                        "satellite_delta": int(-sign * satellite_close_volume),
                        "base_matched_volume": matched_volume,
                        "base_remaining_volume": max(remaining_base, 0.0),
                        "satellite_target_volume": int(target_satellite),
                        "event_type_order": 1,
                    }
                )
            previous_satellite_target = int(target_satellite)

        terminal_error = max(
            abs(remaining_base - expected_base_remaining),
            abs(sign * previous_satellite_target - expected_terminal_position),
        )
        if terminal_error != 0:
            nonflat_final_open_group_count += 1
            raise ValueError(f"nonflat final open group: {open_trade_id}")

    if order_rows:
        orders = pd.DataFrame(order_rows)
        orders = orders.sort_values(
            ["trade_datetime", "requested_start_month", "open_trade_id", "event_type_order", "base_trade_id"],
            kind="stable",
        ).reset_index(drop=True)
        orders = orders.drop(columns="event_type_order")
    else:
        orders = pd.DataFrame(columns=_ORDER_OUTPUT_COLUMNS)
    return orders, {
        "selected_open_group_count": int(len(open_groups)),
        "satellite_order_count": int(len(orders)),
        "overclose_count": overclose_count,
        "nonflat_final_open_group_count": nonflat_final_open_group_count,
        "expected_terminal_position_count": int(len(expected_terminal_positions)),
        "unexpected_terminal_position_count": 0,
        "max_terminal_position_reconciliation_error": 0.0,
        "expected_terminal_positions": expected_terminal_positions,
    }


def _normalize_ledger_date(value: Any, label: str) -> pd.Timestamp:
    try:
        timestamp = pd.Timestamp(value)
    except (TypeError, ValueError):
        raise ValueError(f"invalid {label}") from None
    if pd.isna(timestamp):
        raise ValueError(f"invalid {label}")
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_convert("Asia/Shanghai").tz_localize(None)
    return timestamp.normalize()


def _local_trade_date(timestamp: pd.Timestamp) -> pd.Timestamp:
    return timestamp.tz_convert("Asia/Shanghai").tz_localize(None).normalize()


def _aggregate_contract_positions(
    lifecycle_positions: dict[str, int],
    lifecycle_contracts: dict[str, str],
) -> dict[str, int]:
    aggregate: dict[str, int] = {}
    for open_trade_id, position in lifecycle_positions.items():
        if position:
            contract = lifecycle_contracts[open_trade_id]
            aggregate[contract] = aggregate.get(contract, 0) + int(position)
    return {contract: position for contract, position in aggregate.items() if position}


def _portfolio_margin(
    aggregate_positions: dict[str, int],
    marks: dict[str, float],
    specs: dict[str, dict[str, float]],
) -> float:
    margin = 0.0
    for contract, position in aggregate_positions.items():
        if contract not in marks:
            raise ValueError(f"missing price for held contract: {contract}")
        spec = specs[contract]
        margin += abs(position) * marks[contract] * spec["size"] * spec["margin_ratio"]
    if not np.isfinite(margin):
        raise ValueError("non-finite satellite margin")
    return float(margin)


def reconcile_sleeve_cashflow(
    replayed_orders: pd.DataFrame,
    terminal_contract_positions: dict[str, int],
    final_marks: dict[str, float],
    specs: dict[str, dict[str, float]],
    *,
    daily_cumulative_net_pnl: float,
) -> dict[str, float]:
    """Recompute sleeve PnL from independent trade cashflows and terminal asset value."""
    required = {
        "vt_symbol",
        "executed_satellite_delta",
        "trade_price",
        "slippage",
        "commission",
    }
    _require_columns(replayed_orders, required)
    trade_notional = 0.0
    replayed_costs = 0.0
    for order in replayed_orders.to_dict("records"):
        contract = str(order["vt_symbol"])
        raw_spec = specs.get(contract)
        if raw_spec is None or "size" not in raw_spec:
            raise ValueError(f"cashflow reconciliation missing size: {contract}")
        size = _require_finite_scalar(raw_spec["size"], f"cashflow size:{contract}")
        delta = _require_finite_scalar(
            order["executed_satellite_delta"], "cashflow executed delta"
        )
        if not delta.is_integer() or size <= 0.0:
            raise ValueError("cashflow reconciliation requires integer delta and positive size")
        price = _require_finite_scalar(order["trade_price"], "cashflow trade price")
        slippage = _require_finite_scalar(order["slippage"], "cashflow slippage")
        commission = _require_finite_scalar(order["commission"], "cashflow commission")
        if price <= 0.0 or slippage < 0.0 or commission < 0.0:
            raise ValueError("cashflow reconciliation invalid price or cost")
        trade_notional += delta * price * size
        replayed_costs += slippage + commission
    terminal_mark_value = 0.0
    for contract, raw_position in terminal_contract_positions.items():
        position = _require_finite_scalar(raw_position, f"cashflow terminal position:{contract}")
        if not position.is_integer():
            raise ValueError(f"cashflow integer terminal position required: {contract}")
        if int(position) == 0:
            continue
        raw_spec = specs.get(str(contract))
        if raw_spec is None or "size" not in raw_spec:
            raise ValueError(f"cashflow reconciliation missing size: {contract}")
        size = _require_finite_scalar(raw_spec["size"], f"cashflow size:{contract}")
        mark = _require_finite_scalar(final_marks.get(str(contract)), f"cashflow final mark:{contract}")
        if size <= 0.0 or mark <= 0.0:
            raise ValueError(f"cashflow positive size/final mark required: {contract}")
        terminal_mark_value += int(position) * mark * size
    cashflow_net_pnl = terminal_mark_value - trade_notional - replayed_costs
    daily_cumulative = _require_finite_scalar(
        daily_cumulative_net_pnl, "daily cumulative net PnL"
    )
    return {
        "terminal_mark_value": float(terminal_mark_value),
        "executed_trade_notional": float(trade_notional),
        "replayed_costs": float(replayed_costs),
        "cashflow_net_pnl": float(cashflow_net_pnl),
        "daily_cumulative_net_pnl": float(daily_cumulative),
        "max_terminal_pnl_reconciliation_error": float(
            abs(cashflow_net_pnl - daily_cumulative)
        ),
    }


def _max_abs(values: pd.Series) -> float:
    return float(values.abs().max()) if len(values.index) else 0.0


def replay_satellite_ledger(
    base_daily: pd.DataFrame,
    price_table: pd.DataFrame,
    candidate_orders: pd.DataFrame,
    specs: dict[str, dict[str, float]],
    cost_multiplier: float,
    expected_terminal_positions: dict[str, int] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Replay the satellite sleeve chronologically without feeding PnL back into C9."""
    _require_columns(base_daily, _LEDGER_BASE_REQUIRED_COLUMNS)
    if base_daily.empty:
        raise ValueError("empty base_daily")
    _require_columns(price_table, _LEDGER_PRICE_REQUIRED_COLUMNS)
    order_required_columns = (
        _LEDGER_ORDER_BASE_REQUIRED_COLUMNS if candidate_orders.empty else _LEDGER_ORDER_REQUIRED_COLUMNS
    )
    _require_columns(candidate_orders, order_required_columns)

    cost_multiplier = _require_finite_scalar(cost_multiplier, "cost_multiplier")
    if cost_multiplier <= 0.0:
        raise ValueError("positive cost_multiplier required")
    explicit_terminal_contract = expected_terminal_positions is not None
    terminal_targets: dict[str, int] = {}
    for open_trade_id, value in (expected_terminal_positions or {}).items():
        numeric = _require_finite_scalar(value, f"expected terminal position:{open_trade_id}")
        if not numeric.is_integer():
            raise ValueError(f"integer expected terminal position required: {open_trade_id}")
        if int(numeric):
            terminal_targets[str(open_trade_id)] = int(numeric)

    base = base_daily.copy()
    base["date"] = base["date"].map(lambda value: _normalize_ledger_date(value, "base date"))
    if base["date"].duplicated().any():
        raise ValueError("duplicate base date")
    _require_finite(base, ("account_equity", "total_margin_exact"))
    if pd.to_numeric(base["total_margin_exact"], errors="raise").lt(0.0).any():
        raise ValueError("non-finite base margin")
    base = base.sort_values("date", kind="stable").reset_index(drop=True)
    base_dates = set(base["date"].tolist())

    prices = price_table.copy()
    prices["date"] = prices["date"].map(lambda value: _normalize_ledger_date(value, "price date"))
    if prices.duplicated(["date", "vt_symbol"]).any():
        raise ValueError("duplicate price key")
    price_by_key = {
        (row["date"], str(row["vt_symbol"])): row for row in prices.to_dict("records")
    }

    orders = candidate_orders.copy()
    _require_requested_start_month(orders)
    _require_nonempty_text(
        orders,
        ("requested_start_month", "base_trade_id", "open_trade_id", "vt_symbol", "direction"),
    )
    if orders.duplicated(["requested_start_month", "open_trade_id", "base_trade_id"]).any():
        raise ValueError("duplicate order key")
    orders["trade_datetime"] = orders["trade_datetime"].map(_parse_timezone_aware_datetime)
    orders["trade_date"] = orders["trade_datetime"].map(_local_trade_date)
    if not set(orders["trade_date"].tolist()).issubset(base_dates):
        raise ValueError("order outside base dates")
    _require_finite(orders, ("trade_price", "satellite_delta"))
    if pd.to_numeric(orders["trade_price"], errors="raise").le(0.0).any():
        raise ValueError("non-finite trade_price")
    deltas = pd.to_numeric(orders["satellite_delta"], errors="raise")
    if deltas.eq(0.0).any() or deltas.mod(1).ne(0).any():
        raise ValueError("non-zero integer satellite_delta required")
    orders["satellite_delta"] = deltas.astype(int)
    orders["direction"] = orders["direction"].astype(str).str.strip().str.lower()
    if not orders["direction"].isin({"long", "short"}).all():
        raise ValueError("invalid order direction")
    orders = orders.sort_values(
        ["trade_datetime", "base_trade_id", "requested_start_month", "open_trade_id"], kind="stable"
    ).reset_index(drop=True)

    related_contracts = set(orders["vt_symbol"].astype(str).tolist())
    validated_specs: dict[str, dict[str, float]] = {}
    for contract in sorted(related_contracts):
        raw_spec = specs.get(contract)
        if raw_spec is None:
            raise ValueError(f"missing spec: {contract}")
        spec: dict[str, float] = {}
        for field in _LEDGER_SPEC_FIELDS:
            if field not in raw_spec:
                raise ValueError(f"missing spec field: {field} for {contract}")
            spec[field] = _require_finite_scalar(raw_spec[field], f"spec {contract}.{field}")
        for field in ("size", "slippage", "margin_ratio"):
            if spec[field] <= 0.0:
                raise ValueError(f"positive spec value: {field} for {contract}")
        if spec["rate"] < 0.0:
            raise ValueError(f"non-negative spec value: rate for {contract}")
        validated_specs[contract] = spec

    lifecycle_positions: dict[str, int] = {}
    lifecycle_requested_positions: dict[str, int] = {}
    lifecycle_contracts: dict[str, str] = {}
    lifecycle_directions: dict[str, str] = {}
    seen_open_trade_ids: set[str] = set()
    blocked_open_trade_ids: set[str] = set()
    replayed_order_rows: list[dict[str, Any]] = []
    daily_rows: list[dict[str, Any]] = []
    cumulative_net = 0.0
    prior_combined_equity = _LEDGER_CAPITAL
    overclose_count = 0
    missing_price_count = 0

    for base_row in base.to_dict("records"):
        date = base_row["date"]
        day_orders = orders.loc[orders["trade_date"].eq(date)]
        held_before = set(_aggregate_contract_positions(lifecycle_positions, lifecycle_contracts))
        required_contracts = held_before | set(day_orders["vt_symbol"].astype(str).tolist())
        marks: dict[str, float] = {}
        close_prices: dict[str, float] = {}
        for contract in sorted(required_contracts):
            price_row = price_by_key.get((date, contract))
            if price_row is None:
                missing_price_count += 1
                raise ValueError(f"missing price for {date.date()} {contract}")
            pre_close = _require_finite_scalar(price_row["pre_close"], f"price {date.date()} {contract}.pre_close")
            close_price = _require_finite_scalar(price_row["close_price"], f"price {date.date()} {contract}.close_price")
            if pre_close <= 0.0 or close_price <= 0.0:
                raise ValueError(f"non-finite price for {date.date()} {contract}")
            marks[contract] = pre_close
            close_prices[contract] = close_price

        if not np.isfinite(prior_combined_equity) or prior_combined_equity <= 0.0:
            raise ValueError("non-finite prior combined equity")
        day_gross = 0.0
        day_slippage = 0.0
        day_commission = 0.0
        day_executed_order_count = 0

        for order in day_orders.to_dict("records"):
            contract = str(order["vt_symbol"])
            open_trade_id = str(order["open_trade_id"])
            direction = str(order["direction"])
            requested_delta = int(order["satellite_delta"])
            spec = validated_specs[contract]
            aggregate_before = _aggregate_contract_positions(lifecycle_positions, lifecycle_contracts)
            day_gross += aggregate_before.get(contract, 0) * (float(order["trade_price"]) - marks[contract]) * spec["size"]
            marks[contract] = float(order["trade_price"])

            direction_sign = 1 if direction == "long" else -1
            is_open_event = int(requested_delta * direction_sign > 0)
            margin_gate_blocked = 0
            proposed_broker10_pct = math.nan
            satellite_margin_after_proposed = math.nan

            if is_open_event:
                estimated_equity = _require_finite_scalar(order["estimated_equity"], "estimated_equity")
                c9_projected_margin = _require_finite_scalar(
                    order["c9_projected_total_margin_after"], "c9_projected_total_margin_after"
                )
                if estimated_equity <= 0.0 or c9_projected_margin < 0.0:
                    raise ValueError("non-finite PIT margin input")
                if open_trade_id in seen_open_trade_ids:
                    raise ValueError(f"duplicate open event: {open_trade_id}")
                seen_open_trade_ids.add(open_trade_id)
                lifecycle_contracts[open_trade_id] = contract
                lifecycle_directions[open_trade_id] = direction
                lifecycle_positions[open_trade_id] = 0
                lifecycle_requested_positions[open_trade_id] = requested_delta

                proposed_lifecycle_positions = dict(lifecycle_positions)
                proposed_lifecycle_positions[open_trade_id] = requested_delta
                proposed_aggregate = _aggregate_contract_positions(
                    proposed_lifecycle_positions, lifecycle_contracts
                )
                satellite_margin_after_proposed = _portfolio_margin(
                    proposed_aggregate, marks, validated_specs
                )
                gate_input = pd.DataFrame(
                    [
                        {
                            "requested_satellite_delta": requested_delta,
                            "c9_projected_total_margin_after": c9_projected_margin,
                            "satellite_margin_after_proposed": satellite_margin_after_proposed,
                            "is_open_event": 1,
                        }
                    ]
                )
                gated = apply_open_margin_gate(
                    gate_input,
                    prior_combined_equity=prior_combined_equity,
                    broker_multiplier=_LEDGER_BROKER_MULTIPLIER,
                ).iloc[0]
                executed_delta = int(gated["executed_satellite_delta"])
                margin_gate_blocked = int(gated["margin_gate_blocked"])
                proposed_broker10_pct = float(gated["proposed_broker10_pct"])
                if margin_gate_blocked:
                    blocked_open_trade_ids.add(open_trade_id)
                else:
                    lifecycle_positions[open_trade_id] = executed_delta
            else:
                if open_trade_id not in seen_open_trade_ids:
                    overclose_count += 1
                    raise ValueError(f"overclose without open: {open_trade_id}")
                if lifecycle_contracts[open_trade_id] != contract or lifecycle_directions[open_trade_id] != direction:
                    raise ValueError(f"lifecycle identity mismatch: {open_trade_id}")
                requested_position = lifecycle_requested_positions[open_trade_id]
                if requested_position == 0 or requested_position * requested_delta >= 0 or abs(requested_delta) > abs(requested_position):
                    overclose_count += 1
                    raise ValueError(f"overclose lifecycle: {open_trade_id}")
                lifecycle_requested_positions[open_trade_id] = requested_position + requested_delta
                if open_trade_id in blocked_open_trade_ids:
                    executed_delta = 0
                else:
                    current_position = lifecycle_positions[open_trade_id]
                    executed_delta = requested_delta
                    lifecycle_positions[open_trade_id] = current_position + executed_delta

            order_slippage = abs(executed_delta) * spec["slippage"] * spec["size"] * cost_multiplier
            order_commission = abs(executed_delta) * float(order["trade_price"]) * spec["size"] * spec["rate"]
            if not np.isfinite(order_slippage) or not np.isfinite(order_commission):
                raise ValueError("non-finite order cost")
            day_slippage += order_slippage
            day_commission += order_commission
            day_executed_order_count += int(executed_delta != 0)
            replayed_order_rows.append(
                {
                    **{key: value for key, value in order.items() if key != "trade_date"},
                    "requested_satellite_delta": requested_delta,
                    "is_open_event": is_open_event,
                    "executed_satellite_delta": executed_delta,
                    "satellite_margin_after_proposed": satellite_margin_after_proposed,
                    "proposed_broker10_pct": proposed_broker10_pct,
                    "margin_gate_blocked": margin_gate_blocked,
                    "blocked_lifecycle": int(open_trade_id in blocked_open_trade_ids),
                    "slippage": float(order_slippage),
                    "commission": float(order_commission),
                }
            )

        aggregate_at_close = _aggregate_contract_positions(lifecycle_positions, lifecycle_contracts)
        for contract, position in aggregate_at_close.items():
            day_gross += position * (close_prices[contract] - marks[contract]) * validated_specs[contract]["size"]
            marks[contract] = close_prices[contract]

        day_net = day_gross - day_slippage - day_commission
        cumulative_net += day_net
        satellite_equity = _LEDGER_CAPITAL + cumulative_net
        combined_equity = float(base_row["account_equity"]) + cumulative_net
        if not np.isfinite(satellite_equity):
            raise ValueError("non-finite satellite equity")
        if satellite_equity <= 0.0:
            raise ValueError("non-positive satellite equity")
        if not np.isfinite(combined_equity):
            raise ValueError("non-finite combined equity")
        if combined_equity <= 0.0:
            raise ValueError("non-positive combined equity")
        satellite_margin = _portfolio_margin(aggregate_at_close, marks, validated_specs)
        aggregate_broker10_margin = (
            float(base_row["total_margin_exact"]) + satellite_margin
        ) * _LEDGER_BROKER_MULTIPLIER
        if not np.isfinite(aggregate_broker10_margin):
            raise ValueError("non-finite EOD broker margin")
        daily_rows.append(
            {
                **base_row,
                "satellite_gross_pnl": float(day_gross),
                "satellite_slippage": float(day_slippage),
                "satellite_commission": float(day_commission),
                "satellite_net_pnl": float(day_net),
                "satellite_cumulative_net_pnl": float(cumulative_net),
                "satellite_equity": float(satellite_equity),
                "combined_equity": float(combined_equity),
                "prior_combined_equity": float(prior_combined_equity),
                "satellite_margin": float(satellite_margin),
                "aggregate_broker10_margin": float(aggregate_broker10_margin),
                "aggregate_broker10_to_prior_combined_equity_pct": float(
                    aggregate_broker10_margin / prior_combined_equity * 100.0
                ),
                "aggregate_broker10_to_current_combined_equity_pct": float(
                    aggregate_broker10_margin / combined_equity * 100.0
                ),
                "satellite_held_contract_count": int(len(aggregate_at_close)),
                "satellite_requested_order_count": int(len(day_orders.index)),
                "satellite_executed_order_count": int(day_executed_order_count),
            }
        )
        prior_combined_equity = combined_equity

    all_terminal_ids = set(lifecycle_positions) | set(terminal_targets)
    terminal_errors: dict[str, int] = {}
    for open_trade_id in sorted(all_terminal_ids):
        requested_expected = terminal_targets.get(open_trade_id, 0)
        executed_expected = 0 if open_trade_id in blocked_open_trade_ids else requested_expected
        requested_actual = lifecycle_requested_positions.get(open_trade_id, 0)
        executed_actual = lifecycle_positions.get(open_trade_id, 0)
        error = max(abs(requested_actual - requested_expected), abs(executed_actual - executed_expected))
        if error:
            terminal_errors[open_trade_id] = int(error)
    max_terminal_error = max(terminal_errors.values(), default=0)
    if terminal_errors:
        if explicit_terminal_contract:
            raise ValueError(f"terminal position reconciliation failed: {terminal_errors}")
        raise ValueError(f"nonflat final holdings: {sorted(terminal_errors)}")
    expected_executed_positions = {
        open_trade_id: (0 if open_trade_id in blocked_open_trade_ids else terminal_targets.get(open_trade_id, 0))
        for open_trade_id in lifecycle_positions
    }
    expected_terminal_aggregate = _aggregate_contract_positions(
        expected_executed_positions, lifecycle_contracts
    )
    actual_terminal_aggregate = _aggregate_contract_positions(
        lifecycle_positions, lifecycle_contracts
    )
    expected_terminal_margin = _portfolio_margin(expected_terminal_aggregate, marks, validated_specs)
    actual_terminal_margin = _portfolio_margin(actual_terminal_aggregate, marks, validated_specs)
    terminal_margin_error = abs(actual_terminal_margin - expected_terminal_margin)

    daily = pd.DataFrame(daily_rows)
    replayed_order_columns = [column for column in orders.columns if column != "trade_date"] + [
        "requested_satellite_delta",
        "is_open_event",
        "executed_satellite_delta",
        "satellite_margin_after_proposed",
        "proposed_broker10_pct",
        "margin_gate_blocked",
        "blocked_lifecycle",
        "slippage",
        "commission",
    ]
    replayed_orders = pd.DataFrame(replayed_order_rows, columns=replayed_order_columns)
    expected_cumulative = daily["satellite_net_pnl"].cumsum()
    net_error = _max_abs(
        daily["satellite_net_pnl"]
        - (daily["satellite_gross_pnl"] - daily["satellite_slippage"] - daily["satellite_commission"])
    )
    cumulative_error = _max_abs(daily["satellite_cumulative_net_pnl"] - expected_cumulative)
    cashflow_audit = reconcile_sleeve_cashflow(
        replayed_orders,
        actual_terminal_aggregate,
        marks,
        validated_specs,
        daily_cumulative_net_pnl=float(daily["satellite_cumulative_net_pnl"].iloc[-1]),
    )
    terminal_pnl_error = cashflow_audit["max_terminal_pnl_reconciliation_error"]
    b_error = _max_abs(daily["satellite_equity"] - (_LEDGER_CAPITAL + expected_cumulative))
    c_error = _max_abs(daily["combined_equity"] - (daily["account_equity"] + expected_cumulative))
    reconciliation_error = max(net_error, cumulative_error, b_error, c_error)
    if reconciliation_error > 1e-9:
        raise ValueError(f"reconciliation error: {reconciliation_error}")

    proposed_values = pd.to_numeric(
        replayed_orders.loc[replayed_orders["is_open_event"].eq(1), "proposed_broker10_pct"],
        errors="raise",
    )
    audit = {
        "blocked_open_trade_id_count": int(len(blocked_open_trade_ids)),
        "overclose_count": int(overclose_count),
        "missing_price_count": int(missing_price_count),
        "missing_spec_count": 0,
        "nonflat_final_open_group_count": 0,
        "expected_terminal_position_count": int(len(terminal_targets)),
        "unexpected_terminal_position_count": int(len(terminal_errors)),
        "max_terminal_position_reconciliation_error": float(max_terminal_error),
        "max_terminal_margin_reconciliation_error": float(terminal_margin_error),
        "max_terminal_pnl_reconciliation_error": float(terminal_pnl_error),
        "terminal_mark_value": cashflow_audit["terminal_mark_value"],
        "executed_trade_notional": cashflow_audit["executed_trade_notional"],
        "replayed_costs": cashflow_audit["replayed_costs"],
        "cashflow_net_pnl": cashflow_audit["cashflow_net_pnl"],
        "max_net_identity_error": float(net_error),
        "max_b_equity_error": float(b_error),
        "max_c_equity_error": float(c_error),
        "max_reconciliation_error": float(reconciliation_error),
        "max_proposed_broker10_pct": float(proposed_values.max()) if len(proposed_values.index) else 0.0,
        "max_eod_broker10_prior_pct": float(
            daily["aggregate_broker10_to_prior_combined_equity_pct"].max()
        ) if len(daily.index) else 0.0,
        "max_eod_broker10_current_pct": float(
            daily["aggregate_broker10_to_current_combined_equity_pct"].max()
        ) if len(daily.index) else 0.0,
    }
    return daily, replayed_orders, audit


def assert_current_ai_golden_curve(
    base_daily: pd.DataFrame,
    golden_curve: pd.DataFrame,
    *,
    requested_start_month: str,
    tolerance: float = IDENTITY_TOLERANCE,
) -> dict[str, Any]:
    """Require exact current-AI golden dates and micro-unit daily equality."""
    required = {"requested_start_month", "date", "account_equity", "net_pnl", "total_margin_exact"}
    _require_columns(base_daily, required)
    _require_columns(golden_curve, required)
    tolerance = _require_finite_scalar(tolerance, "current-AI golden curve tolerance")
    if tolerance < 0.0:
        raise ValueError("current-AI golden curve tolerance must be non-negative")
    if not _REQUESTED_START_MONTH_PATTERN.fullmatch(str(requested_start_month)):
        raise ValueError("current-AI golden curve invalid requested start month")

    def normalize(frame: pd.DataFrame, label: str) -> pd.DataFrame:
        data = frame.loc[
            frame["requested_start_month"].astype(str).eq(str(requested_start_month)),
            sorted(required),
        ].copy()
        _require_requested_start_month(data)
        data["date"] = data["date"].map(lambda value: _normalize_ledger_date(value, f"{label} date"))
        if data.duplicated(["requested_start_month", "date"]).any():
            raise ValueError(f"current-AI golden curve duplicate {label} date")
        _require_finite(data, ("account_equity", "net_pnl", "total_margin_exact"))
        return data.sort_values(["requested_start_month", "date"], kind="stable").reset_index(drop=True)

    actual = normalize(base_daily, "fresh")
    golden = normalize(golden_curve, "golden")
    if actual.empty or golden.empty:
        raise ValueError("current-AI golden curve empty requested start")
    actual_keys = set(map(tuple, actual[["requested_start_month", "date"]].to_numpy()))
    golden_keys = set(map(tuple, golden[["requested_start_month", "date"]].to_numpy()))
    date_drift = len(actual_keys.symmetric_difference(golden_keys))
    if date_drift:
        raise ValueError(f"current-AI golden curve date coverage drift: {date_drift}")
    merged = actual.merge(
        golden,
        on=["requested_start_month", "date"],
        how="inner",
        suffixes=("_fresh", "_golden"),
        validate="one_to_one",
    )
    audit: dict[str, Any] = {
        "current_ai_golden_curve_applicable": 1,
        "current_ai_golden_curve_pass": 1,
        "current_ai_golden_curve_date_drift_count": 0,
        "current_ai_golden_curve_compared_date_count": int(len(merged.index)),
    }
    violations: list[str] = []
    for field in ("account_equity", "net_pnl", "total_margin_exact"):
        error = _max_abs(merged[f"{field}_fresh"] - merged[f"{field}_golden"])
        audit[f"current_ai_golden_curve_max_{field}_error"] = float(error)
        if error > tolerance:
            violations.append(f"{field}={error:.12g}")
    if violations:
        raise ValueError(f"current-AI golden curve drift: {', '.join(violations)}")
    return audit


def audit_current_ai_snapshot(
    path: Path,
    *,
    expected_sha256: str,
    expected_rows: int,
    expected_eval_dates: tuple[str, ...],
    observed_source_paths: dict[Path, dict[str, Any]] | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Freeze the exact current official AI bytes and complete monthly date set."""
    path = Path(path).expanduser().resolve()
    before = _file_snapshot(path)
    observed = observed_source_paths if observed_source_paths is not None else {}
    with capture_pandas_read_csv_paths(observed):
        frame = pd.read_csv(path, encoding="utf-8-sig")
    after = _file_snapshot(path)
    if (before["size"], before["sha256"]) != (after["size"], after["sha256"]):
        raise ValueError("current AI snapshot changed during audit")
    if after["sha256"] != str(expected_sha256):
        raise ValueError("current AI snapshot SHA256 mismatch")
    if int(len(frame.index)) != int(expected_rows):
        raise ValueError("current AI snapshot row count mismatch")
    required = {
        "strategy", "score_type", "eval_date", "product_vt_symbol", "score", "score_rank", "top_n"
    }
    _require_columns(frame, required)
    data = frame.copy()
    if data["eval_date"].isna().any() or data["product_vt_symbol"].isna().any():
        raise ValueError("current AI snapshot missing membership key")
    dates = pd.to_datetime(data["eval_date"], errors="raise").dt.strftime("%Y-%m-%d")
    products = data["product_vt_symbol"].astype(str).str.strip()
    if products.eq("").any():
        raise ValueError("current AI snapshot blank membership key")
    actual_dates = tuple(sorted(dates.drop_duplicates().tolist()))
    expected_dates = tuple(sorted(str(value) for value in expected_eval_dates))
    if actual_dates != expected_dates:
        raise ValueError("current AI snapshot eval-date set mismatch")
    keys = pd.DataFrame(
        {
            "eval_date": dates,
            "product_vt_symbol": products,
        }
    )
    if keys.isna().any().any() or keys.duplicated().any():
        raise ValueError("current AI snapshot duplicate or missing membership key")
    _require_finite(data, ("score", "score_rank", "top_n"))
    return frame, {
        "current_ai_snapshot_pass": 1,
        "current_ai_snapshot_size": int(after["size"]),
        "current_ai_snapshot_sha256": str(after["sha256"]),
        "current_ai_snapshot_row_count": int(len(frame.index)),
        "current_ai_snapshot_eval_date_count": int(len(actual_dates)),
        "current_ai_snapshot_min_eval_date": actual_dates[0],
        "current_ai_snapshot_max_eval_date": actual_dates[-1],
    }


def assert_current_ai_golden_membership(
    current: pd.DataFrame,
    golden: pd.DataFrame,
    *,
    tolerance: float = 0.0,
) -> dict[str, Any]:
    """Bind the Stage006 golden curve to the same AI membership and ranks."""
    required = {
        "strategy", "score_type", "eval_date", "product_vt_symbol", "score", "score_rank", "top_n"
    }
    _require_columns(current, required)
    _require_columns(golden, required)
    tolerance = _require_finite_scalar(tolerance, "current-AI golden membership tolerance")
    if tolerance < 0.0:
        raise ValueError("current-AI golden membership tolerance must be non-negative")

    def normalize(frame: pd.DataFrame, label: str) -> pd.DataFrame:
        data = frame.loc[:, sorted(required)].copy()
        if data["eval_date"].isna().any() or data["product_vt_symbol"].isna().any():
            raise ValueError(f"current-AI golden membership missing {label} key")
        if data["strategy"].isna().any() or data["score_type"].isna().any():
            raise ValueError(f"current-AI golden membership missing {label} label")
        data["eval_date"] = pd.to_datetime(data["eval_date"], errors="raise").dt.strftime("%Y-%m-%d")
        data["product_vt_symbol"] = data["product_vt_symbol"].astype(str).str.strip()
        if data["product_vt_symbol"].eq("").any():
            raise ValueError(f"current-AI golden membership blank {label} key")
        if data.duplicated(["eval_date", "product_vt_symbol"]).any():
            raise ValueError(f"current-AI golden membership duplicate {label} key")
        _require_finite(data, ("score", "score_rank", "top_n"))
        return data.sort_values(["eval_date", "product_vt_symbol"], kind="stable").reset_index(drop=True)

    left = normalize(current, "current")
    right = normalize(golden, "golden")
    left_keys = set(map(tuple, left[["eval_date", "product_vt_symbol"]].to_numpy()))
    right_keys = set(map(tuple, right[["eval_date", "product_vt_symbol"]].to_numpy()))
    if left_keys != right_keys:
        raise ValueError("current-AI golden membership key drift")
    merged = left.merge(
        right,
        on=["eval_date", "product_vt_symbol"],
        suffixes=("_current", "_golden"),
        validate="one_to_one",
    )
    violations: list[str] = []
    for field in ("score", "score_rank", "top_n"):
        error = _max_abs(
            pd.to_numeric(merged[f"{field}_current"], errors="raise")
            - pd.to_numeric(merged[f"{field}_golden"], errors="raise")
        )
        if error > tolerance:
            violations.append(f"{field}={error:.12g}")
    if violations:
        raise ValueError(f"current-AI golden membership drift: {', '.join(violations)}")
    label_differences = (
        merged["strategy_current"].astype(str).ne(merged["strategy_golden"].astype(str))
        | merged["score_type_current"].astype(str).ne(merged["score_type_golden"].astype(str))
    )
    return {
        "current_ai_golden_membership_pass": 1,
        "current_ai_golden_membership_row_count": int(len(merged.index)),
        "current_ai_golden_ignored_label_difference_count": int(label_differences.sum()),
    }


def _canonical_scalar(value: Any) -> Any:
    if value is None or value is pd.NA or value is pd.NaT:
        return {"type": "null"}
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, Enum):
        return {
            "type": f"enum:{value.__class__.__module__}.{value.__class__.__qualname__}",
            "value": _canonical_scalar(value.value),
        }
    if isinstance(value, (pd.Timestamp, datetime, date, np.datetime64)):
        timestamp = pd.Timestamp(value)
        if pd.isna(timestamp):
            return {"type": "null"}
        if timestamp.tzinfo is None:
            return {"type": "datetime-naive", "value": timestamp.isoformat()}
        return {"type": "datetime-utc", "value": timestamp.tz_convert("UTC").isoformat()}
    if isinstance(value, pd.Timedelta):
        return {"type": "timedelta-ns", "value": int(value.value)}
    if isinstance(value, bool):
        return {"type": "bool", "value": value}
    if isinstance(value, int):
        return {"type": "int", "value": str(value)}
    if isinstance(value, float):
        if math.isnan(value):
            return {"type": "null"}
        if math.isinf(value):
            return {"type": "float", "value": "inf" if value > 0 else "-inf"}
        return {"type": "float", "value": value.hex()}
    if isinstance(value, str):
        return {"type": "str", "value": value}
    if isinstance(value, bytes):
        return {"type": "bytes", "value": value.hex()}
    if isinstance(value, dict):
        pairs = [
            [_canonical_scalar(key), _canonical_scalar(item)]
            for key, item in value.items()
        ]
        pairs.sort(
            key=lambda pair: json.dumps(
                pair[0], sort_keys=True, separators=(",", ":")
            )
        )
        return {
            "type": "dict",
            "value": pairs,
        }
    if isinstance(value, (list, tuple)):
        return {"type": type(value).__name__, "value": [_canonical_scalar(item) for item in value]}
    return {
        "type": f"object:{value.__class__.__module__}.{value.__class__.__qualname__}",
        "value": str(value),
    }


def canonical_frame_identity(
    frame: pd.DataFrame,
    frame_name: str,
    *,
    key_columns: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Hash a frame after explicit stable-key sorting with schema and dtype identity."""
    data = frame.copy()
    keys = tuple(str(column) for column in key_columns)
    if keys:
        _require_columns(data, set(keys))
        if not data.empty:
            if data.loc[:, list(keys)].isna().any().any():
                raise ValueError(f"canonical identity missing key: {frame_name}")
            blank_key = data.loc[:, list(keys)].apply(
                lambda column: column.map(
                    lambda value: isinstance(value, str) and not value.strip()
                )
            )
            if blank_key.any().any():
                raise ValueError(f"canonical identity blank key: {frame_name}")
            if data.duplicated(list(keys)).any():
                raise ValueError(f"canonical identity duplicate key: {frame_name}")
            data = data.sort_values(list(keys), kind="stable").reset_index(drop=True)
    columns = sorted(str(column) for column in data.columns)
    data = data.loc[:, columns]
    schema = [
        {"column": column, "dtype": str(data[column].dtype)}
        for column in columns
    ]
    digest = hashlib.sha256()
    header = {"frame_name": str(frame_name), "key_columns": list(keys), "schema": schema}
    digest.update(json.dumps(header, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    digest.update(b"\n")
    for row in data.itertuples(index=False, name=None):
        canonical = [_canonical_scalar(value) for value in row]
        digest.update(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8"))
        digest.update(b"\n")
    return {
        "frame_name": str(frame_name),
        "key_columns": "|".join(keys),
        "row_count": int(len(data.index)),
        "column_count": int(len(columns)),
        "schema_sha256": hashlib.sha256(
            json.dumps(schema, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
        "content_sha256": digest.hexdigest(),
    }


_REPEAT_ARTIFACT_KEYS: dict[str, tuple[str, ...]] = {
    "base_daily": ("date",),
    "positions": ("date", "vt_symbol"),
    "trades": ("trade_id",),
    "entry_risk": ("entry_index",),
    "entry_candidates": ("candidate_index",),
    "closed_lots": ("open_trade_id", "close_trade_id"),
    "pit_source_ledger": ("raw_risk_row_index",),
    "pit_candidate_audit": ("raw_candidate_row_index",),
    "actual_open_audit": ("raw_trade_row_index",),
    "pit_binding_audit": ("open_trade_id",),
    "selected_lifecycle": ("open_trade_id",),
    "candidate_orders": ("requested_start_month", "open_trade_id", "base_trade_id"),
    "price_audit": ("requested_start_month", "date", "vt_symbol"),
    "contract_specs": ("vt_symbol",),
}


def compare_repeat_artifacts(
    first: dict[str, pd.DataFrame],
    second: dict[str, pd.DataFrame],
    requested_start_month: str,
) -> tuple[dict[str, Any], pd.DataFrame]:
    """Require canonical identity for every frozen raw and derived artifact."""
    expected = set(_REPEAT_ARTIFACT_KEYS)
    for label, artifacts in (("first", first), ("second", second)):
        missing = sorted(expected.difference(artifacts))
        if missing:
            raise ValueError(f"repeat artifact identity missing {label} frames: {missing}")
    rows: list[dict[str, Any]] = []
    drifted: list[str] = []
    for name in sorted(expected):
        left = canonical_frame_identity(first[name], name, key_columns=_REPEAT_ARTIFACT_KEYS[name])
        right = canonical_frame_identity(second[name], name, key_columns=_REPEAT_ARTIFACT_KEYS[name])
        matched = int(
            left["row_count"] == right["row_count"]
            and left["column_count"] == right["column_count"]
            and left["schema_sha256"] == right["schema_sha256"]
            and left["content_sha256"] == right["content_sha256"]
        )
        if not matched:
            drifted.append(name)
        rows.append({
            "requested_start_month": str(requested_start_month),
            "frame_name": name,
            "key_columns": left["key_columns"],
            "first_row_count": left["row_count"],
            "second_row_count": right["row_count"],
            "first_column_count": left["column_count"],
            "second_column_count": right["column_count"],
            "first_schema_sha256": left["schema_sha256"],
            "second_schema_sha256": right["schema_sha256"],
            "first_content_sha256": left["content_sha256"],
            "second_content_sha256": right["content_sha256"],
            "identity_match": matched,
        })
    if drifted:
        raise ValueError(f"repeat artifact identity drift: {', '.join(drifted)}")
    return {
        "current_c9_repeat_identity_pass": 1,
        "current_c9_repeat_compared_frame_count": int(len(rows)),
        "current_c9_repeat_mismatch_frame_count": 0,
    }, pd.DataFrame(rows)


def compare_repeat_source_manifests(
    first: pd.DataFrame,
    second: pd.DataFrame,
    requested_start_month: str,
) -> tuple[dict[str, Any], pd.DataFrame]:
    """Require identical path/size/SHA while retaining mtime-only rewrite evidence."""
    required = {"path", "size", "mtime_ns", "sha256"}
    _require_columns(first, required)
    _require_columns(second, required)
    for label, frame in (("first", first), ("second", second)):
        if frame["path"].astype(str).duplicated().any():
            raise ValueError(f"repeat source manifest duplicate {label} path")
    merged = first.loc[:, sorted(required)].merge(
        second.loc[:, sorted(required)],
        on="path",
        how="outer",
        suffixes=("_first", "_second"),
        indicator=True,
        validate="one_to_one",
    )
    complete = merged["_merge"].eq("both")
    content_match = (
        complete
        & pd.to_numeric(merged["size_first"], errors="coerce").eq(
            pd.to_numeric(merged["size_second"], errors="coerce")
        )
        & merged["sha256_first"].astype(str).eq(merged["sha256_second"].astype(str))
    )
    if not content_match.all():
        left_only = merged.loc[merged["_merge"].eq("left_only"), "path"].astype(str).tolist()
        right_only = merged.loc[merged["_merge"].eq("right_only"), "path"].astype(str).tolist()
        both = merged["_merge"].eq("both")
        size_mismatch = merged.loc[
            both
            & ~pd.to_numeric(merged["size_first"], errors="coerce").eq(
                pd.to_numeric(merged["size_second"], errors="coerce")
            ),
            "path",
        ].astype(str).tolist()
        sha_mismatch = merged.loc[
            both
            & ~merged["sha256_first"].astype(str).eq(
                merged["sha256_second"].astype(str)
            ),
            "path",
        ].astype(str).tolist()
        detail = {
            "comparison": str(requested_start_month),
            "left_only": left_only,
            "right_only": right_only,
            "size_mismatch": size_mismatch,
            "sha_mismatch": sha_mismatch,
        }
        raise ValueError(
            "repeat source manifest drift: "
            + json.dumps(detail, ensure_ascii=False, sort_keys=True)
        )
    ledger = pd.DataFrame({
        "requested_start_month": str(requested_start_month),
        "path": merged["path"].astype(str),
        "size": pd.to_numeric(merged["size_first"], errors="raise").astype("int64"),
        "sha256": merged["sha256_first"].astype(str),
        "first_mtime_ns": pd.to_numeric(merged["mtime_ns_first"], errors="raise").astype("int64"),
        "second_mtime_ns": pd.to_numeric(merged["mtime_ns_second"], errors="raise").astype("int64"),
    })
    ledger["mtime_only_rewrite"] = ledger["first_mtime_ns"].ne(ledger["second_mtime_ns"]).astype(int)
    ledger["content_identity_match"] = 1
    return {
        "repeat_source_manifest_pass": 1,
        "repeat_source_manifest_path_count": int(len(ledger.index)),
        "repeat_source_manifest_mtime_only_rewrite_count": int(ledger["mtime_only_rewrite"].sum()),
    }, ledger


def _load_runtime_bridge() -> SimpleNamespace:
    """Import the backtest stack only when a fresh run is explicitly requested."""
    examples = str(_EXAMPLES_DIR)
    if examples not in sys.path:
        sys.path.insert(0, examples)
    s901 = importlib.import_module("analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow")
    s719 = importlib.import_module("analyze_qmt_roll_stage719_official_winner_trade_forensics")
    s513 = importlib.import_module("analyze_qmt_roll_stage513_stage208_exact_position_margin_audit")
    trader_utility = importlib.import_module("vnpy.trader.utility")
    source_paths = list(_STATIC_SOURCE_PATHS)
    source_paths.extend(collect_loaded_local_source_paths())
    source_paths.extend(trader_state_source_paths(Path(trader_utility.TRADER_DIR)))
    minute_path = getattr(getattr(s901, "s861", None), "FULL_MINUTE_BARS_PATH", None)
    if minute_path is not None:
        source_paths.append(Path(minute_path))
    mapping_path = getattr(s901, "ALL_FUTURES_MAPPING_PATH", None)
    if mapping_path is not None:
        source_paths.append(Path(mapping_path))
    eligibility_path = getattr(s901, "OFFICIAL_LIVE_AI_ELIGIBILITY_PATH", None)
    if eligibility_path is not None:
        source_paths.append(Path(eligibility_path))
    if eligibility_path is None or Path(eligibility_path).expanduser().resolve() != CURRENT_AI_PATH.resolve():
        raise ValueError("official current AI path drift")
    overrides = s513._c3_overrides(s513.START_DT)
    universe_path = str(overrides.get("product_universe_csv_path", "") or "").strip()
    if universe_path:
        source_paths.append(Path(universe_path))
    return SimpleNamespace(
        load_metadata=s513._metadata,
        run_live_c9=s901._run_live_c9,
        build_closed_lots=s719._build_closed_lots,
        source_paths=source_paths,
        current_ai_path=Path(eligibility_path),
    )


def collect_loaded_local_source_paths(
    *,
    modules: Any | None = None,
    repo_root: Path = _REPO_ROOT,
) -> list[Path]:
    """Collect loaded local Python sources without copying module contents."""
    root = Path(repo_root).expanduser().resolve()
    allowed_roots = (
        root / "examples" / "portfolio_backtesting",
        root / "vnpy",
    )
    loaded = list(sys.modules.values()) if modules is None else list(modules)
    paths: set[Path] = set()
    for module in loaded:
        raw_path = getattr(module, "__file__", None)
        if not raw_path:
            continue
        path = Path(raw_path).expanduser().resolve()
        if not path.is_file():
            continue
        if any(path.is_relative_to(allowed.resolve()) for allowed in allowed_roots):
            paths.add(path)
    return sorted(paths, key=str)


def trader_state_source_paths(trader_dir: Path) -> list[Path]:
    runtime_dir = Path(trader_dir).expanduser().resolve() / ".vntrader"
    return [runtime_dir / "database.db", runtime_dir / "vt_setting.json"]


def _snapshot_path(path: Path) -> Path:
    raw = Path(path).expanduser()
    absolute = raw if raw.is_absolute() else Path.cwd() / raw
    if absolute.is_symlink():
        raise ValueError(f"source snapshot symlink is forbidden: {absolute}")
    try:
        return absolute.resolve(strict=True)
    except FileNotFoundError:
        raise ValueError(f"source snapshot missing file: {absolute}") from None


def _read_file_bytes_snapshot(path: Path) -> tuple[bytes, dict[str, Any]]:
    path = _snapshot_path(path)
    if not path.is_file():
        raise ValueError(f"source snapshot missing file: {path}")
    with path.open("rb") as handle:
        before = os.fstat(handle.fileno())
        payload = handle.read()
        after = os.fstat(handle.fileno())
    identity_fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
    if tuple(getattr(before, field) for field in identity_fields) != tuple(
        getattr(after, field) for field in identity_fields
    ):
        raise ValueError(f"source changed while hashing: {path}")
    return payload, {
        "path": str(path),
        "size": int(after.st_size),
        "mtime_ns": int(after.st_mtime_ns),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def _file_snapshot(path: Path) -> dict[str, Any]:
    path = _snapshot_path(path)
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        before = os.fstat(handle.fileno())
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
        after = os.fstat(handle.fileno())
    identity_fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
    if tuple(getattr(before, field) for field in identity_fields) != tuple(
        getattr(after, field) for field in identity_fields
    ):
        raise ValueError(f"source changed while hashing: {path}")
    return {
        "path": str(path),
        "size": int(after.st_size),
        "mtime_ns": int(after.st_mtime_ns),
        "sha256": digest.hexdigest(),
    }


def _compression_from_path(path: Path) -> str | None:
    suffix = path.suffix.lower()
    return {
        ".gz": "gzip",
        ".bz2": "bz2",
        ".zip": "zip",
        ".xz": "xz",
        ".zst": "zstd",
    }.get(suffix)


@contextmanager
def capture_pandas_read_csv_paths(observed_paths: dict[Path, dict[str, Any]]):
    """Snapshot successful local pandas CSV reads and always restore the reader."""
    original_read_csv = pd.read_csv

    def observed_read_csv(filepath_or_buffer: Any, *args: Any, **kwargs: Any) -> Any:
        path: Path | None = None
        read_snapshot: dict[str, Any] | None = None
        frozen_payload: bytes | None = None
        if isinstance(filepath_or_buffer, (str, os.PathLike)):
            raw_path = str(filepath_or_buffer)
            if "://" not in raw_path:
                candidate = Path(filepath_or_buffer).expanduser()
                absolute = candidate if candidate.is_absolute() else Path.cwd() / candidate
                if absolute.exists() or absolute.is_symlink():
                    frozen_payload, read_snapshot = _read_file_bytes_snapshot(absolute)
                    path = Path(read_snapshot["path"])
        read_target = io.BytesIO(frozen_payload) if frozen_payload is not None else filepath_or_buffer
        read_kwargs = dict(kwargs)
        if path is not None and "compression" not in read_kwargs:
            compression = _compression_from_path(path)
            if compression is not None:
                read_kwargs["compression"] = compression
        result = original_read_csv(read_target, *args, **read_kwargs)
        if path is not None and read_snapshot is not None:
            snapshot = _file_snapshot(path)
            if (snapshot["size"], snapshot["sha256"]) != (
                read_snapshot["size"],
                read_snapshot["sha256"],
            ):
                raise ValueError(f"observed source changed during read: {path}")
            previous = observed_paths.get(path)
            read_rewrite_count = int(
                int(read_snapshot["mtime_ns"]) != int(snapshot["mtime_ns"])
            )
            if previous is not None:
                if (previous["size"], previous["sha256"]) != (
                    snapshot["size"],
                    snapshot["sha256"],
                ):
                    raise ValueError(f"observed source snapshot changed across reads: {path}")
                snapshot["first_read_mtime_ns"] = int(
                    previous.get("first_read_mtime_ns", previous["mtime_ns"])
                )
                snapshot["same_content_rewrite_count"] = int(
                    previous.get("same_content_rewrite_count", 0)
                ) + int(previous["mtime_ns"] != read_snapshot["mtime_ns"]) + read_rewrite_count
            else:
                snapshot["first_read_mtime_ns"] = int(read_snapshot["mtime_ns"])
                snapshot["same_content_rewrite_count"] = read_rewrite_count
            snapshot["last_read_mtime_ns"] = int(snapshot["mtime_ns"])
            observed_paths[path] = snapshot
        return result

    pd.read_csv = observed_read_csv
    try:
        yield
    finally:
        pd.read_csv = original_read_csv


def load_runtime_metadata(
    runtime: Any,
    observed_source_paths: dict[Path, dict[str, Any]],
) -> dict[str, Any]:
    with capture_pandas_read_csv_paths(observed_source_paths):
        return runtime.load_metadata()


def _run_base_with_metadata(
    start: pd.Timestamp,
    end: pd.Timestamp,
    runtime: Any,
    metadata: dict[str, Any],
    observed_source_paths: dict[Path, dict[str, Any]] | None = None,
) -> dict[str, pd.DataFrame]:
    start = pd.Timestamp(start).normalize()
    end = min(pd.Timestamp(end).normalize(), ANALYSIS_END)
    if start > end:
        raise ValueError("fresh base start is after analysis end")
    observed = observed_source_paths if observed_source_paths is not None else {}
    with capture_pandas_read_csv_paths(observed):
        combined, raw_frames, _spec = runtime.run_live_c9(metadata, start, end)
    base = combined.copy()
    _require_columns(base, _LEDGER_BASE_REQUIRED_COLUMNS | {"net_pnl"})
    base["date"] = base["date"].map(lambda value: _normalize_ledger_date(value, "fresh base date"))
    base = base.loc[base["date"].between(start, end)].copy()
    if base.empty:
        raise ValueError("empty fresh base daily")
    if base["date"].duplicated().any():
        raise ValueError("duplicate fresh base date")
    requested_start_month = start.strftime("%Y-%m")
    base["requested_start_month"] = requested_start_month
    base = base.sort_values("date", kind="stable").reset_index(drop=True)
    base_dates = set(base["date"].tolist())

    frames: dict[str, pd.DataFrame] = {"base_daily": base}
    for name in ("positions", "trades", "entry_risk", "entry_candidates"):
        frame = raw_frames.get(name, pd.DataFrame()).copy()
        if not frame.empty:
            if name in {"positions", "trades"}:
                _require_columns(frame, {"date"})
                frame["date"] = frame["date"].map(lambda value: _normalize_ledger_date(value, f"{name} date"))
                frame = frame.loc[frame["date"].isin(base_dates)].copy()
            frame["requested_start_month"] = requested_start_month
        frames[name] = frame.reset_index(drop=True)
    trimmed_risk, trimmed_candidates, pit_window_audit = trim_pit_frames_to_open_windows(
        frames["trades"], frames["entry_risk"], frames["entry_candidates"]
    )
    frames["entry_risk"] = trimmed_risk
    frames["entry_candidates"] = trimmed_candidates
    frames["pit_window_audit"] = pd.DataFrame(
        [{"requested_start_month": requested_start_month, **pit_window_audit}]
    )
    if hasattr(runtime, "build_closed_lots"):
        closed = runtime.build_closed_lots(
            frames["trades"], frames["entry_risk"], frames["entry_candidates"], metadata
        )
        closed = closed.copy()
        if not closed.empty:
            closed["requested_start_month"] = requested_start_month
        frames["closed_lots"] = closed
    return frames


def run_base_start(
    start: pd.Timestamp,
    end: pd.Timestamp,
    *,
    runtime: Any | None = None,
    observed_source_paths: dict[Path, dict[str, Any]] | None = None,
) -> dict[str, pd.DataFrame]:
    """Run one fresh C9 anchor and remove all preload rows from accounting frames."""
    bridge = runtime if runtime is not None else _load_runtime_bridge()
    observed = observed_source_paths if observed_source_paths is not None else {}
    metadata = load_runtime_metadata(bridge, observed)
    return _run_base_with_metadata(
        start,
        end,
        bridge,
        metadata,
        observed_source_paths=observed,
    )


def _pit_timestamp(value: Any, label: str) -> pd.Timestamp:
    try:
        timestamp = pd.Timestamp(value)
    except (TypeError, ValueError):
        raise ValueError(f"PIT binding invalid {label}") from None
    if pd.isna(timestamp) or timestamp.tzinfo is None:
        raise ValueError(f"PIT binding timezone required: {label}")
    return timestamp.tz_convert("UTC")


def _normal_pit_direction(value: Any) -> str:
    direction = str(value).strip().lower()
    if direction not in {"long", "short"}:
        raise ValueError("PIT binding invalid direction")
    return direction


_PIT_SELECTOR_FIELDS = (
    "entry_context",
    "layer_kind",
    "ai_product_pool_allowed",
    "ai_product_pool_rank",
    "selected_volume",
)
_PIT_TEXT_FIELDS = {"entry_context", "layer_kind"}


def _pit_value_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _validate_unique_raw_identifier(frame: pd.DataFrame, column: str) -> None:
    _require_columns(frame, {column})
    if frame[column].map(_pit_value_missing).any():
        raise ValueError(f"nonempty {column} required")
    if frame[column].duplicated(keep=False).any():
        raise ValueError(f"duplicate {column}")


def _normalized_pit_value(field: str, value: Any) -> str | float:
    if field in _PIT_TEXT_FIELDS:
        return str(value).strip().lower()
    return _require_finite_scalar(value, f"PIT binding {field}")


def _resolve_pit_field(risk: pd.Series, candidate: pd.Series, field: str, open_id: str) -> str | float:
    risk_value = risk.get(field)
    candidate_value = candidate.get(field)
    risk_missing = _pit_value_missing(risk_value)
    candidate_missing = _pit_value_missing(candidate_value)
    if risk_missing and candidate_missing:
        raise ValueError(f"PIT binding missing selector field: {field} for {open_id}")
    if not risk_missing and not candidate_missing:
        normalized_risk = _normalized_pit_value(field, risk_value)
        normalized_candidate = _normalized_pit_value(field, candidate_value)
        if normalized_risk != normalized_candidate:
            raise ValueError(f"PIT binding field conflict: {field} for {open_id}")
    return _normalized_pit_value(field, candidate_value if risk_missing else risk_value)


def _pit_identity_mask(frame: pd.DataFrame, contract: str, direction: str, volume: int, volume_field: str) -> pd.Series:
    return (
        frame["contract_vt_symbol"].astype(str).eq(contract)
        & frame["direction"].map(_normal_pit_direction).eq(direction)
        & pd.to_numeric(frame[volume_field], errors="coerce").eq(float(volume))
    )


def _match_pit_rows_for_open(
    trade: dict[str, Any],
    risks: pd.DataFrame,
    candidates: pd.DataFrame,
    used_risks: set[int],
    used_candidates: set[int],
) -> tuple[dict[str, Any], dict[str, Any]]:
    open_id = str(trade["trade_id"])
    trade_dt = _pit_timestamp(trade["datetime"], "trade datetime")
    contract = str(trade["vt_symbol"])
    direction = _normal_pit_direction(trade["direction"])
    volume = _require_integer_scalar(trade["volume"], "PIT trade volume")
    available_risks = risks.loc[~risks["source_index"].isin(used_risks)].copy()
    available_candidates = candidates.loc[
        ~candidates["source_index"].isin(used_candidates)
    ].copy()
    risk_identity = available_risks.loc[
        _pit_identity_mask(available_risks, contract, direction, volume, "volume")
    ].copy()
    candidate_identity = available_candidates.loc[
        available_candidates["candidate_status"].astype(str).str.strip().str.lower().eq("opened")
        & _pit_identity_mask(
            available_candidates, contract, direction, volume, "selected_volume"
        )
    ].copy()
    risk_identity["pit_datetime"] = risk_identity["datetime"].map(
        lambda value: _pit_timestamp(value, "risk datetime")
    )
    candidate_identity["pit_datetime"] = candidate_identity["datetime"].map(
        lambda value: _pit_timestamp(value, "candidate datetime")
    )
    lower = trade_dt - pd.Timedelta(days=5)
    upper = trade_dt + pd.Timedelta(days=5)
    risk_future = int(risk_identity["pit_datetime"].gt(trade_dt).mul(risk_identity["pit_datetime"].le(upper)).sum())
    candidate_future = int(
        candidate_identity["pit_datetime"].gt(trade_dt).mul(candidate_identity["pit_datetime"].le(upper)).sum()
    )
    risk_matches = risk_identity.loc[risk_identity["pit_datetime"].between(lower, trade_dt)]
    candidate_matches = candidate_identity.loc[candidate_identity["pit_datetime"].between(lower, trade_dt)]
    if len(risk_matches.index) == 0 and risk_future:
        raise ValueError(f"PIT binding future match: {open_id}")
    if len(candidate_matches.index) == 0 and candidate_future:
        raise ValueError(f"PIT binding future match: {open_id}")
    if len(risk_matches.index) != 1:
        raise ValueError(f"PIT binding risk_match_count={len(risk_matches.index)}: {open_id}")
    if len(candidate_matches.index) != 1:
        raise ValueError(f"PIT binding candidate_match_count={len(candidate_matches.index)}: {open_id}")
    risk = risk_matches.iloc[0]
    candidate = candidate_matches.iloc[0]
    risk_source = int(risk["source_index"])
    candidate_source = int(candidate["source_index"])
    if risk_source in used_risks or candidate_source in used_candidates:
        raise ValueError(f"PIT binding source row reuse: {open_id}")
    used_risks.add(risk_source)
    used_candidates.add(candidate_source)
    resolved = {field: _resolve_pit_field(risk, candidate, field, open_id) for field in _PIT_SELECTOR_FIELDS}
    projected = _resolve_pit_field(risk, candidate, "projected_total_margin_after", open_id)
    estimated = _resolve_pit_field(risk, candidate, "estimated_equity", open_id)
    if float(projected) < 0.0 or float(estimated) <= 0.0:
        raise ValueError(f"PIT binding invalid margin/equity: {open_id}")
    binding = {
        "entry_index": risk["entry_index"],
        "candidate_index": candidate["candidate_index"],
        "risk_datetime": risk["pit_datetime"],
        "candidate_datetime": candidate["pit_datetime"],
        "trade_datetime": trade_dt,
        "contract_vt_symbol": contract,
        "direction": direction,
        "volume": volume,
        "c9_projected_total_margin_after": float(projected),
        "estimated_equity": float(estimated),
        **resolved,
    }
    audit = {
        "open_trade_id": open_id,
        "risk_match_count": 1,
        "candidate_match_count": 1,
        "future_match_count": 0,
        "risk_source_index": risk_source,
        "candidate_source_index": candidate_source,
        **binding,
    }
    return binding, audit


def trim_pit_frames_to_open_windows(
    trades: pd.DataFrame,
    entry_risk: pd.DataFrame,
    entry_candidates: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, int]]:
    """Retain complete PIT frames; calendar mapping classifies sources without actual Opens."""
    del trades
    return entry_risk.copy().reset_index(drop=True), entry_candidates.copy().reset_index(drop=True), {
        "entry_risk_excluded_row_count": 0,
        "entry_candidate_excluded_row_count": 0,
    }


_PIT_SOURCE_LEDGER_COLUMNS = [
    "requested_start_month",
    "source_id",
    "raw_risk_row_index",
    "risk_source_index",
    "candidate_source_index",
    "entry_index",
    "candidate_index",
    "risk_datetime",
    "risk_local_date",
    "expected_execution_date",
    "candidate_datetime",
    "contract_vt_symbol",
    "direction",
    "risk_volume",
    "entry_context",
    "layer_kind",
    "ai_product_pool_allowed",
    "ai_product_pool_rank",
    "selected_volume",
    "c9_projected_total_margin_after",
    "estimated_equity",
    "source_classification",
    "quality_eligible",
    "source_sequence",
]
_PIT_CANDIDATE_AUDIT_COLUMNS = [
    "requested_start_month",
    "raw_candidate_row_index",
    "candidate_source_index",
    "candidate_index",
    "candidate_datetime",
    "contract_vt_symbol",
    "direction",
    "candidate_status",
    "selected_volume",
    "entry_context",
    "layer_kind",
    "ai_product_pool_allowed",
    "ai_product_pool_rank",
    "projected_total_margin_after",
    "estimated_equity",
    "mapping_status",
    "matched_risk_source_id",
    "matched_risk_source_index",
    "matched_entry_index",
]
_ACTUAL_OPEN_AUDIT_COLUMNS = [
    "requested_start_month",
    "raw_trade_row_index",
    "trade_id",
    "order_id",
    "trade_datetime",
    "trade_date",
    "vt_symbol",
    "direction",
    "actual_open_volume",
    "classification",
    "source_id",
    "entry_index",
    "entry_context",
    "layer_kind",
    "source_classification",
    "risk_volume",
    "volume_drift",
    "source_sequence",
    "actual_sequence",
    "source_order_match",
]


def _base_trading_calendar(base_dates: pd.Series | list[Any]) -> list[pd.Timestamp]:
    calendar = sorted({_normalize_ledger_date(value, "base trading calendar date") for value in base_dates})
    if not calendar:
        raise ValueError("empty base trading calendar")
    return calendar


def _entry_index_sort_key(value: Any) -> tuple[int, float, str]:
    numeric = pd.to_numeric(value, errors="coerce")
    if not pd.isna(numeric) and np.isfinite(float(numeric)):
        return 0, float(numeric), ""
    return 1, 0.0, str(value)


def build_pit_risk_source_ledger(
    entry_risk: pd.DataFrame,
    entry_candidates: pd.DataFrame,
    *,
    base_dates: pd.Series | list[Any],
    requested_start_month: str,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Build one auditable row for every PIT risk source before reading actual Opens."""
    calendar = _base_trading_calendar(base_dates)
    candidate_required = {
        "candidate_index",
        "datetime",
        "contract_vt_symbol",
        "direction",
        "candidate_status",
        "selected_volume",
    }
    if entry_candidates.empty:
        candidates = pd.DataFrame(columns=["candidate_source_index", *sorted(candidate_required)])
    else:
        _require_columns(entry_candidates, candidate_required)
        _validate_unique_raw_identifier(entry_candidates, "candidate_index")
        if entry_candidates["candidate_status"].map(_pit_value_missing).any():
            raise ValueError("candidate_status must be opened or skipped")
        normalized_status = (
            entry_candidates["candidate_status"].astype(str).str.strip().str.lower()
        )
        if not normalized_status.isin({"opened", "skipped"}).all():
            raise ValueError("candidate_status must be opened or skipped")
        candidates = entry_candidates.copy().reset_index(drop=True)
        candidates["candidate_status"] = normalized_status.to_numpy()
        candidates.insert(0, "candidate_source_index", range(len(candidates.index)))
        candidates["candidate_datetime"] = candidates["datetime"].map(
            lambda value: _pit_timestamp(value, "candidate datetime")
        )
    candidate_rows: list[dict[str, Any]] = []
    for candidate in candidates.to_dict("records"):
        status = str(candidate["candidate_status"]).strip().lower()
        candidate_rows.append(
            {
                "requested_start_month": str(requested_start_month),
                "raw_candidate_row_index": int(candidate["candidate_source_index"]),
                "candidate_source_index": int(candidate["candidate_source_index"]),
                "candidate_index": candidate["candidate_index"],
                "candidate_datetime": candidate["candidate_datetime"],
                "contract_vt_symbol": str(candidate["contract_vt_symbol"]),
                "direction": _normal_pit_direction(candidate["direction"]),
                "candidate_status": status,
                "selected_volume": candidate["selected_volume"],
                "entry_context": candidate.get("entry_context", np.nan),
                "layer_kind": candidate.get("layer_kind", np.nan),
                "ai_product_pool_allowed": candidate.get(
                    "ai_product_pool_allowed", np.nan
                ),
                "ai_product_pool_rank": candidate.get("ai_product_pool_rank", np.nan),
                "projected_total_margin_after": candidate.get(
                    "projected_total_margin_after", np.nan
                ),
                "estimated_equity": candidate.get("estimated_equity", np.nan),
                "mapping_status": (
                    "opened_candidate_without_risk"
                    if status == "opened"
                    else "skipped_candidate"
                ),
                "matched_risk_source_id": "",
                "matched_risk_source_index": pd.NA,
                "matched_entry_index": pd.NA,
            }
        )
    candidate_audit = pd.DataFrame(
        candidate_rows, columns=_PIT_CANDIDATE_AUDIT_COLUMNS
    )

    if entry_risk.empty:
        risks = pd.DataFrame()
    else:
        _require_columns(
            entry_risk,
            {
                "entry_index",
                "datetime",
                "contract_vt_symbol",
                "direction",
                "volume",
                "entry_context",
                "layer_kind",
            },
        )
        _validate_unique_raw_identifier(entry_risk, "entry_index")
        risks = entry_risk.copy().reset_index(drop=True)
        risks.insert(0, "raw_risk_row_index", range(len(risks.index)))
        risks["risk_source_index"] = risks["raw_risk_row_index"]
        risks["risk_datetime"] = risks["datetime"].map(
            lambda value: _pit_timestamp(value, "risk datetime")
        )
        risk_records = risks.to_dict("records")
        risk_records.sort(
            key=lambda row: (
                pd.Timestamp(row["risk_datetime"]),
                _entry_index_sort_key(row["entry_index"]),
                int(row["raw_risk_row_index"]),
            )
        )
        risks = pd.DataFrame(risk_records)
    used_candidates: set[int] = set()
    rows: list[dict[str, Any]] = []
    for risk in risks.to_dict("records"):
        entry_id = str(risk["entry_index"])
        source_id = f"risk:{entry_id}|row:{int(risk['raw_risk_row_index'])}"
        if _pit_value_missing(risk.get("entry_context")) or _pit_value_missing(
            risk.get("layer_kind")
        ):
            raise ValueError(f"PIT risk missing entry context/layer: {entry_id}")
        entry_context = str(_normalized_pit_value("entry_context", risk["entry_context"]))
        layer_kind = str(_normalized_pit_value("layer_kind", risk["layer_kind"]))
        contract = str(risk["contract_vt_symbol"])
        direction = _normal_pit_direction(risk["direction"])
        risk_volume = _require_integer_scalar(risk["volume"], "PIT source risk volume")
        risk_datetime = pd.Timestamp(risk["risk_datetime"])
        risk_local_date = _local_trade_date(risk_datetime)
        expected_execution_date = next(
            (date for date in calendar if date > risk_local_date), pd.NaT
        )
        is_flat_base = entry_context == "flat_entry" and layer_kind == "base"
        candidate_source_index: Any = pd.NA
        candidate_index: Any = pd.NA
        candidate_datetime: Any = pd.NaT
        resolved: dict[str, str | float]
        projected: float | Any = np.nan
        estimated: float | Any = np.nan
        if is_flat_base:
            available = candidates.loc[
                ~candidates["candidate_source_index"].isin(used_candidates)
                & candidates["candidate_status"].astype(str).str.strip().str.lower().eq("opened")
                & _pit_identity_mask(
                    candidates, contract, direction, risk_volume, "selected_volume"
                )
            ].copy()
            if not available.empty:
                available = available.loc[available["candidate_datetime"].eq(risk_datetime)]
            if len(available.index) != 1:
                raise ValueError(
                    f"PIT source candidate_match_count={len(available.index)}: {entry_id}"
                )
            candidate = available.iloc[0]
            candidate_source_index = int(candidate["candidate_source_index"])
            used_candidates.add(candidate_source_index)
            candidate_audit.loc[
                candidate_audit["candidate_source_index"].eq(candidate_source_index),
                [
                    "mapping_status",
                    "matched_risk_source_id",
                    "matched_risk_source_index",
                    "matched_entry_index",
                ],
            ] = [
                "matched_risk_source",
                source_id,
                int(risk["risk_source_index"]),
                risk["entry_index"],
            ]
            candidate_index = candidate["candidate_index"]
            candidate_datetime = candidate["candidate_datetime"]
            risk_series = pd.Series(risk)
            resolved = {
                field: _resolve_pit_field(risk_series, candidate, field, entry_id)
                for field in _PIT_SELECTOR_FIELDS
            }
            projected = float(
                _resolve_pit_field(
                    risk_series, candidate, "projected_total_margin_after", entry_id
                )
            )
            estimated = float(
                _resolve_pit_field(risk_series, candidate, "estimated_equity", entry_id)
            )
            selected_volume = _require_integer_scalar(
                resolved["selected_volume"], "PIT source selected_volume"
            )
            if selected_volume != risk_volume:
                raise ValueError(f"PIT source selected volume mismatch: {entry_id}")
            quality_eligible = int(
                float(resolved["ai_product_pool_allowed"]) == 1.0
                and 1.0 <= float(resolved["ai_product_pool_rank"]) <= 8.0
                and selected_volume > 1
            )
            source_classification = (
                "quality_eligible" if quality_eligible else "quality_ineligible"
            )
        else:
            def optional_number(field: str) -> float:
                value = risk.get(field)
                return (
                    np.nan
                    if _pit_value_missing(value)
                    else _require_finite_scalar(value, f"PIT source {field}")
                )

            resolved = {
                "entry_context": entry_context,
                "layer_kind": layer_kind,
                "ai_product_pool_allowed": optional_number("ai_product_pool_allowed"),
                "ai_product_pool_rank": optional_number("ai_product_pool_rank"),
                "selected_volume": risk.get("selected_volume", risk_volume),
            }
            projected = optional_number("projected_total_margin_after")
            estimated = optional_number("estimated_equity")
            quality_eligible = 0
            source_classification = "non_flat_base"
        rows.append(
            {
                "requested_start_month": str(requested_start_month),
                "source_id": source_id,
                "raw_risk_row_index": int(risk["raw_risk_row_index"]),
                "risk_source_index": int(risk["risk_source_index"]),
                "candidate_source_index": candidate_source_index,
                "entry_index": risk["entry_index"],
                "candidate_index": candidate_index,
                "risk_datetime": risk_datetime,
                "risk_local_date": risk_local_date,
                "expected_execution_date": expected_execution_date,
                "candidate_datetime": candidate_datetime,
                "contract_vt_symbol": contract,
                "direction": direction,
                "risk_volume": risk_volume,
                "entry_context": entry_context,
                "layer_kind": layer_kind,
                "ai_product_pool_allowed": resolved["ai_product_pool_allowed"],
                "ai_product_pool_rank": resolved["ai_product_pool_rank"],
                "selected_volume": resolved["selected_volume"],
                "c9_projected_total_margin_after": projected,
                "estimated_equity": estimated,
                "source_classification": source_classification,
                "quality_eligible": quality_eligible,
                "source_sequence": pd.NA,
            }
        )
    ledger = pd.DataFrame(rows, columns=_PIT_SOURCE_LEDGER_COLUMNS)
    if not ledger.empty:
        ledger["source_sequence"] = pd.Series(
            [pd.NA] * len(ledger.index), dtype="Int64"
        )
        sequenced = ledger.loc[ledger["expected_execution_date"].notna()]
        for _key, group in sequenced.groupby(
            ["expected_execution_date", "contract_vt_symbol", "direction"],
            sort=False,
            dropna=False,
        ):
            ordered_indexes = sorted(
                group.index,
                key=lambda index: (
                    pd.Timestamp(ledger.loc[index, "risk_datetime"]),
                    _entry_index_sort_key(ledger.loc[index, "entry_index"]),
                    int(ledger.loc[index, "raw_risk_row_index"]),
                ),
            )
            for sequence, index in enumerate(ordered_indexes, start=1):
                ledger.loc[index, "source_sequence"] = sequence
    classifications = ledger["source_classification"]
    opened = candidate_audit["candidate_status"].eq("opened")
    skipped = ~opened
    opened_without_risk = candidate_audit["mapping_status"].eq(
        "opened_candidate_without_risk"
    )
    return ledger, candidate_audit, {
        "risk_input_count": int(len(entry_risk.index)),
        "pit_source_ledger_row_count": int(len(ledger.index)),
        "pit_risk_source_count": int(len(ledger.index)),
        "quality_eligible_source_count": int(classifications.eq("quality_eligible").sum()),
        "non_flat_base_source_count": int(classifications.eq("non_flat_base").sum()),
        "quality_ineligible_source_count": int(classifications.eq("quality_ineligible").sum()),
        "candidate_input_count": int(len(entry_candidates.index)),
        "pit_candidate_audit_row_count": int(len(candidate_audit.index)),
        "opened_candidate_count": int(opened.sum()),
        "skipped_candidate_count": int(skipped.sum()),
        "opened_candidate_without_risk_count": int(opened_without_risk.sum()),
        "candidate_without_risk_count": int(opened_without_risk.sum()),
    }


def _is_synthetic_retry_open(trade: dict[str, Any]) -> bool:
    order_id = str(trade.get("order_id", "")).strip().lower()
    return ".stage847_c9." in order_id


def map_pit_risk_sources_to_actual_opens(
    pit_source_ledger: pd.DataFrame,
    trades: pd.DataFrame,
    *,
    requested_start_month: str,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    """Map every non-retry actual Open to the complete risk ledger one-to-one."""
    _validate_raw_trade_inputs(trades)
    required_source = {
        "source_id",
        "entry_index",
        "expected_execution_date",
        "contract_vt_symbol",
        "direction",
        "risk_volume",
        "entry_context",
        "layer_kind",
        "source_classification",
        "quality_eligible",
        "raw_risk_row_index",
        "source_sequence",
    }
    _require_columns(pit_source_ledger, required_source)
    ledger = pit_source_ledger.copy().reset_index(drop=True)
    ledger["mapping_status"] = "source_without_actual"
    ledger["actual_open_trade_id"] = ""
    ledger["actual_open_datetime"] = pd.Series(
        [None] * len(ledger.index), dtype="object"
    )
    ledger["actual_open_date"] = pd.NaT
    ledger["actual_open_price"] = np.nan
    ledger["actual_open_volume"] = np.nan
    ledger["volume_drift"] = 0
    ledger["actual_sequence"] = pd.Series(
        [pd.NA] * len(ledger.index), dtype="Int64"
    )
    ledger["source_order_match"] = 1

    raw_trades = trades.copy().reset_index(drop=True)
    raw_trades.insert(0, "raw_trade_row_index", range(len(raw_trades.index)))
    opens = raw_trades.loc[
        raw_trades["offset"].astype(str).str.strip().str.lower().eq("open")
    ].copy()
    if opens["trade_id"].astype(str).duplicated().any():
        raise ValueError("duplicate actual Open trade_id")
    opens["trade_datetime"] = opens["datetime"].map(_parse_timezone_aware_datetime)
    opens["trade_date"] = opens["trade_datetime"].map(_local_trade_date)
    opens["normal_direction"] = opens["direction"].map(_normal_pit_direction)
    opens["actual_volume"] = opens["volume"].map(
        lambda value: _require_integer_scalar(value, "actual Open volume")
    )
    opens = opens.sort_values(
        ["trade_datetime", "raw_trade_row_index"], kind="stable"
    )
    for trade in opens.to_dict("records"):
        local_datetime = pd.Timestamp(trade["trade_datetime"]).tz_convert("Asia/Shanghai")
        local_midnight = (
            local_datetime.hour == 0
            and local_datetime.minute == 0
            and local_datetime.second == 0
            and local_datetime.microsecond == 0
        )
        retry_marker = _is_synthetic_retry_open(trade)
        if retry_marker and local_midnight:
            raise ValueError(f"retry marker at local midnight: {trade['trade_id']}")
        if not retry_marker and not local_midnight:
            raise ValueError(
                f"non-midnight Open missing retry marker: {trade['trade_id']}"
            )
    retry_mask = pd.Series(
        [_is_synthetic_retry_open(row) for row in opens.to_dict("records")],
        index=opens.index,
        dtype=bool,
    )
    retries = opens.loc[retry_mask].copy()
    nonretry = opens.loc[~retry_mask].copy()
    nonretry["actual_sequence"] = (
        nonretry.groupby(
            ["trade_date", "vt_symbol", "normal_direction"], sort=False
        ).cumcount()
        + 1
    )

    actual_rows: list[dict[str, Any]] = []
    future_match_count = 0
    unmapped_actual_open_count = 0
    source_order_mismatch_count = 0
    positive_volume_drift_count = 0
    for trade in retries.to_dict("records"):
        actual_rows.append(
            {
                "requested_start_month": str(requested_start_month),
                "raw_trade_row_index": int(trade["raw_trade_row_index"]),
                "trade_id": str(trade["trade_id"]),
                "order_id": str(trade.get("order_id", "")),
                "trade_datetime": trade["trade_datetime"],
                "trade_date": trade["trade_date"],
                "vt_symbol": str(trade["vt_symbol"]),
                "direction": trade["normal_direction"],
                "actual_open_volume": int(trade["actual_volume"]),
                "classification": "synthetic_retry",
                "source_id": "",
                "entry_index": pd.NA,
                "entry_context": "",
                "layer_kind": "",
                "source_classification": "",
                "risk_volume": np.nan,
                "volume_drift": 0,
                "source_sequence": pd.NA,
                "actual_sequence": pd.NA,
                "source_order_match": 1,
            }
        )

    def source_key(row: pd.Series) -> tuple[pd.Timestamp, str, str] | None:
        if pd.isna(row["expected_execution_date"]):
            return None
        return (
            _normalize_ledger_date(row["expected_execution_date"], "expected execution date"),
            str(row["contract_vt_symbol"]),
            _normal_pit_direction(row["direction"]),
        )

    source_groups: dict[tuple[pd.Timestamp, str, str], list[int]] = {}
    for index, source in ledger.iterrows():
        key = source_key(source)
        if key is not None:
            source_groups.setdefault(key, []).append(int(index))
    actual_groups: dict[tuple[pd.Timestamp, str, str], list[dict[str, Any]]] = {}
    for trade in nonretry.to_dict("records"):
        key = (trade["trade_date"], str(trade["vt_symbol"]), trade["normal_direction"])
        actual_groups.setdefault(key, []).append(trade)

    def bind(source_index: int, trade: dict[str, Any]) -> None:
        nonlocal source_order_mismatch_count, positive_volume_drift_count
        source = ledger.loc[source_index]
        if pd.isna(source["source_sequence"]) or pd.isna(trade["actual_sequence"]):
            source_order_mismatch_count += 1
            raise ValueError("missing source_sequence or actual_sequence")
        source_sequence = int(source["source_sequence"])
        actual_sequence = int(trade["actual_sequence"])
        if source_sequence != actual_sequence:
            source_order_mismatch_count += 1
            raise ValueError(
                f"source order mismatch: source_sequence={source_sequence} "
                f"actual_sequence={actual_sequence}"
            )
        actual_volume = int(trade["actual_volume"])
        risk_volume = int(source["risk_volume"])
        drift = actual_volume - risk_volume
        if drift > 0:
            positive_volume_drift_count += 1
            raise ValueError(
                f"positive volume drift: {source['source_id']} actual={actual_volume} "
                f"risk={risk_volume}"
            )
        ledger.loc[source_index, "mapping_status"] = "mapped"
        ledger.loc[source_index, "actual_open_trade_id"] = str(trade["trade_id"])
        ledger.loc[source_index, "actual_open_datetime"] = trade["trade_datetime"]
        ledger.loc[source_index, "actual_open_date"] = trade["trade_date"]
        ledger.loc[source_index, "actual_open_price"] = float(trade["price"])
        ledger.loc[source_index, "actual_open_volume"] = actual_volume
        ledger.loc[source_index, "volume_drift"] = drift
        ledger.loc[source_index, "actual_sequence"] = actual_sequence
        ledger.loc[source_index, "source_order_match"] = 1
        source_classification = str(source["source_classification"])
        classification = (
            "mapped_non_flat_base"
            if source_classification == "non_flat_base"
            else f"mapped_{source_classification}"
        )
        actual_rows.append(
            {
                "requested_start_month": str(requested_start_month),
                "raw_trade_row_index": int(trade["raw_trade_row_index"]),
                "trade_id": str(trade["trade_id"]),
                "order_id": str(trade.get("order_id", "")),
                "trade_datetime": trade["trade_datetime"],
                "trade_date": trade["trade_date"],
                "vt_symbol": str(trade["vt_symbol"]),
                "direction": trade["normal_direction"],
                "actual_open_volume": actual_volume,
                "classification": classification,
                "source_id": source["source_id"],
                "entry_index": source["entry_index"],
                "entry_context": source["entry_context"],
                "layer_kind": source["layer_kind"],
                "source_classification": source_classification,
                "risk_volume": risk_volume,
                "volume_drift": drift,
                "source_sequence": source_sequence,
                "actual_sequence": actual_sequence,
                "source_order_match": 1,
            }
        )

    for key in sorted(set(source_groups) | set(actual_groups)):
        source_indexes = list(source_groups.get(key, []))
        actual_records = list(actual_groups.get(key, []))
        if not actual_records:
            continue
        if not source_indexes:
            actual = actual_records[0]
            same_identity = ledger.loc[
                ledger["contract_vt_symbol"].astype(str).eq(str(actual["vt_symbol"]))
                & ledger["direction"].map(_normal_pit_direction).eq(actual["normal_direction"])
            ]
            future = same_identity.loc[
                pd.to_datetime(same_identity["expected_execution_date"], errors="coerce").gt(
                    actual["trade_date"]
                )
            ]
            if not future.empty:
                future_match_count += 1
                raise ValueError(
                    f"future PIT source for actual Open: {actual['trade_id']} "
                    f"future_match_count={future_match_count}"
                )
            unmapped_actual_open_count += 1
            raise ValueError(
                f"unmapped nonretry actual Open: {actual['trade_id']} "
                f"unmapped_actual_open_count={unmapped_actual_open_count}"
            )

        if len(source_indexes) != len(actual_records):
            source_order_mismatch_count += 1
            if len(actual_records) > len(source_indexes):
                unmapped_actual_open_count += len(actual_records) - len(source_indexes)
            raise ValueError(
                "source/actual count mismatch for key "
                f"{key}: source={len(source_indexes)} actual={len(actual_records)}"
            )
        source_sequences = [ledger.loc[index, "source_sequence"] for index in source_indexes]
        if (
            any(pd.isna(value) for value in source_sequences)
            or len({int(value) for value in source_sequences}) != len(source_sequences)
            or sorted(int(value) for value in source_sequences)
            != list(range(1, len(source_sequences) + 1))
        ):
            source_order_mismatch_count += 1
            raise ValueError(f"source_sequence is not unique and contiguous for key {key}")
        actual_sequences = [int(row["actual_sequence"]) for row in actual_records]
        if (
            len(set(actual_sequences)) != len(actual_sequences)
            or sorted(actual_sequences) != list(range(1, len(actual_sequences) + 1))
        ):
            source_order_mismatch_count += 1
            raise ValueError(f"actual_sequence is not unique and contiguous for key {key}")
        ordered_sources = sorted(
            source_indexes, key=lambda index: int(ledger.loc[index, "source_sequence"])
        )
        ordered_actual = sorted(
            actual_records, key=lambda row: int(row["actual_sequence"])
        )
        for source_index, trade in zip(ordered_sources, ordered_actual, strict=True):
            bind(source_index, trade)

    actual_audit = pd.DataFrame(actual_rows, columns=_ACTUAL_OPEN_AUDIT_COLUMNS)
    if not actual_audit.empty:
        actual_audit = actual_audit.sort_values(
            ["trade_datetime", "trade_id"], kind="stable"
        ).reset_index(drop=True)
    mapped = ledger["mapping_status"].eq("mapped")
    source_without_actual = ~mapped
    mapped_classification = ledger.loc[mapped, "source_classification"]
    return ledger, actual_audit, {
        "actual_open_count": int(len(opens.index)),
        "actual_open_input_count": int(len(opens.index)),
        "actual_open_audit_row_count": int(len(actual_audit.index)),
        "mapped_nonretry_open_count": int(mapped.sum()),
        "unmapped_actual_open_count": int(unmapped_actual_open_count),
        "future_match_count": int(future_match_count),
        "retry_open_count": int(len(retries.index)),
        "source_without_actual_open_count": int(source_without_actual.sum()),
        "quality_source_without_actual_open_count": int(
            (source_without_actual & ledger["quality_eligible"].eq(1)).sum()
        ),
        "mapped_quality_eligible_open_count": int(
            mapped_classification.eq("quality_eligible").sum()
        ),
        "mapped_eligible_open_count": int(
            mapped_classification.eq("quality_eligible").sum()
        ),
        "mapped_quality_ineligible_open_count": int(
            mapped_classification.eq("quality_ineligible").sum()
        ),
        "mapped_non_flat_base_open_count": int(
            mapped_classification.eq("non_flat_base").sum()
        ),
        "mapped_rollover_open_count": int(
            (mapped & ledger["entry_context"].eq("rollover_reopen")).sum()
        ),
        "volume_drift_count": int((mapped & ledger["volume_drift"].ne(0)).sum()),
        "positive_volume_drift_count": int(positive_volume_drift_count),
        "source_order_mismatch_count": int(source_order_mismatch_count),
    }


def build_selected_lifecycle_from_mapped_sources(
    mapped_source: pd.DataFrame,
    closed_lots: pd.DataFrame,
    *,
    analysis_end: pd.Timestamp,
) -> pd.DataFrame:
    end = pd.Timestamp(analysis_end).normalize()
    observed_lots = closed_lots.copy()
    if not observed_lots.empty:
        _require_columns(
            observed_lots,
            {"open_trade_id", "close_trade_id", "vt_symbol", "direction", "exit_date", "volume"},
        )
        observed_lots["exit_date"] = pd.to_datetime(
            observed_lots["exit_date"], errors="raise"
        ).dt.normalize()
        observed_lots = observed_lots.loc[observed_lots["exit_date"].le(end)].copy()
    group_rows: list[dict[str, Any]] = []
    for source in mapped_source.to_dict("records"):
        open_id = str(source["open_trade_id"])
        open_volume = _require_integer_scalar(source["trade_volume"], "entry-time open volume")
        lots = (
            observed_lots.loc[
                observed_lots["open_trade_id"].astype(str).eq(open_id)
            ].copy()
            if not observed_lots.empty
            else pd.DataFrame()
        )
        if not lots.empty:
            lots = lots.sort_values(["exit_date", "close_trade_id"], kind="stable")
            if lots["close_trade_id"].astype(str).duplicated().any():
                raise ValueError(f"duplicate close_trade_id within open group: {open_id}")
            close_ids = lots["close_trade_id"].astype(str).tolist()
            close_volumes = [
                _require_integer_scalar(value, f"closed-lot volume:{open_id}")
                for value in lots["volume"]
            ]
        else:
            close_ids = []
            close_volumes = []
        closed_volume = sum(close_volumes)
        if closed_volume > open_volume:
            raise ValueError(f"overclose open group: {open_id}")
        remaining = open_volume - closed_volume
        direction = _normal_pit_direction(source["direction"])
        sign = 1 if direction == "long" else -1
        group_rows.append(
            {
                "requested_start_month": str(source["requested_start_month"]),
                "open_trade_id": open_id,
                "vt_symbol": str(source["vt_symbol"]),
                "direction": direction,
                "entry_date": pd.Timestamp(source["trade_date"]),
                "entry_price": float(source["trade_price"]),
                "base_open_volume": open_volume,
                "close_trade_ids": close_ids,
                "close_matched_volumes": close_volumes,
                "satellite_open_volume": math.floor(open_volume * 0.25),
                "base_remaining_volume": remaining,
                "is_open_at_end": int(remaining > 0),
                "expected_terminal_satellite_position": sign * math.floor(remaining * 0.25),
            }
        )
    groups = pd.DataFrame(group_rows)
    if not groups.empty:
        groups = groups.sort_values(
            ["requested_start_month", "open_trade_id"], kind="stable"
        ).reset_index(drop=True)
    return groups


def mapped_quality_binding_audit(pit_source_ledger: pd.DataFrame) -> pd.DataFrame:
    """Project mapped quality sources into the order/lifecycle binding contract."""
    required = {
        "mapping_status",
        "quality_eligible",
        "actual_open_trade_id",
        "actual_open_datetime",
        "actual_open_date",
        "actual_open_price",
        "actual_open_volume",
        "contract_vt_symbol",
        "direction",
        "source_id",
    }
    _require_columns(pit_source_ledger, required)
    selected = pit_source_ledger.loc[
        pit_source_ledger["mapping_status"].eq("mapped")
        & pd.to_numeric(pit_source_ledger["quality_eligible"], errors="coerce").eq(1)
    ].copy()
    if selected["actual_open_trade_id"].astype(str).duplicated().any():
        raise ValueError("duplicate mapped quality actual Open")
    if selected.empty:
        return pd.DataFrame(
            columns=list(pit_source_ledger.columns)
            + [
                "source_eligible_id",
                "open_trade_id",
                "trade_datetime",
                "trade_date",
                "trade_price",
                "trade_volume",
                "vt_symbol",
                "risk_match_count",
                "candidate_match_count",
                "future_match_count",
            ]
        )
    selected = selected.assign(
        source_eligible_id=selected["source_id"],
        open_trade_id=selected["actual_open_trade_id"].astype(str),
        trade_datetime=selected["actual_open_datetime"],
        trade_date=pd.to_datetime(selected["actual_open_date"]).dt.normalize(),
        trade_price=pd.to_numeric(selected["actual_open_price"], errors="raise"),
        trade_volume=pd.to_numeric(selected["actual_open_volume"], errors="raise").astype(int),
        vt_symbol=selected["contract_vt_symbol"].astype(str),
        risk_match_count=1,
        candidate_match_count=1,
        future_match_count=0,
    )
    return selected.sort_values(
        ["requested_start_month", "trade_datetime", "open_trade_id"], kind="stable"
    ).reset_index(drop=True)


def audit_entry_time_coverage(
    mapped_eligible_source: pd.DataFrame,
    selected_lifecycle: pd.DataFrame,
) -> dict[str, Any]:
    if not mapped_eligible_source.empty:
        _require_columns(mapped_eligible_source, {"open_trade_id"})
    if not selected_lifecycle.empty:
        _require_columns(selected_lifecycle, {"open_trade_id"})
    eligible_ids = (
        set(mapped_eligible_source["open_trade_id"].astype(str))
        if "open_trade_id" in mapped_eligible_source
        else set()
    )
    selected_ids = (
        set(selected_lifecycle["open_trade_id"].astype(str))
        if "open_trade_id" in selected_lifecycle
        else set()
    )
    missing_ids = sorted(eligible_ids - selected_ids)
    unexpected_ids = sorted(selected_ids - eligible_ids)
    return {
        "eligible_open_count": int(len(eligible_ids)),
        "mapped_eligible_open_count": int(len(eligible_ids)),
        "selected_open_count": int(len(selected_ids)),
        "missing_selected_open_count": int(len(missing_ids)),
        "missing_selected_open_ids": missing_ids,
        "unexpected_selected_open_count": int(len(unexpected_ids)),
        "unexpected_selected_open_ids": unexpected_ids,
        "open_at_end_count": int(selected_lifecycle.get("is_open_at_end", pd.Series(dtype=float)).sum()),
        "expected_terminal_position_count": int(
            selected_lifecycle.get(
                "expected_terminal_satellite_position", pd.Series(dtype=float)
            ).ne(0).sum()
        ),
    }


def build_entry_time_open_groups(
    trades: pd.DataFrame,
    entry_risk: pd.DataFrame,
    entry_candidates: pd.DataFrame,
    closed_lots: pd.DataFrame,
    *,
    base_dates: pd.Series | list[Any],
    requested_start_month: str,
    analysis_end: pd.Timestamp,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    dict[str, Any],
]:
    """Build the eligible open universe at entry time, then attach observed FIFO closes."""
    _validate_raw_trade_inputs(trades)
    if not _REQUESTED_START_MONTH_PATTERN.fullmatch(str(requested_start_month)):
        raise ValueError("invalid requested_start_month")
    end = pd.Timestamp(analysis_end).normalize()
    data = trades.copy()
    data["trade_datetime"] = data["datetime"].map(_parse_timezone_aware_datetime)
    data["trade_date"] = data["trade_datetime"].map(_local_trade_date)
    data = data.loc[data["trade_date"].le(end)].copy()
    source_ledger, candidate_audit, source_audit = build_pit_risk_source_ledger(
        entry_risk,
        entry_candidates,
        base_dates=base_dates,
        requested_start_month=str(requested_start_month),
    )
    mapped_source, actual_open_audit, mapping_audit = map_pit_risk_sources_to_actual_opens(
        source_ledger,
        data,
        requested_start_month=str(requested_start_month),
    )
    binding_audit = mapped_quality_binding_audit(mapped_source)
    groups = build_selected_lifecycle_from_mapped_sources(
        binding_audit, closed_lots, analysis_end=end
    )
    coverage = audit_entry_time_coverage(binding_audit, groups)
    coverage.update(source_audit)
    coverage.update(mapping_audit)
    if (
        int(coverage["unmapped_actual_open_count"]) != 0
        or int(coverage["future_match_count"]) != 0
        or int(coverage["source_order_mismatch_count"]) != 0
        or int(coverage["positive_volume_drift_count"]) != 0
        or int(coverage["opened_candidate_without_risk_count"]) != 0
        or int(coverage["risk_input_count"])
        != int(coverage["pit_source_ledger_row_count"])
        or int(coverage["candidate_input_count"])
        != int(coverage["pit_candidate_audit_row_count"])
        or int(coverage["actual_open_input_count"])
        != int(coverage["actual_open_audit_row_count"])
        or int(coverage["eligible_open_count"])
        != int(coverage["mapped_eligible_open_count"])
        or int(coverage["eligible_open_count"]) != int(coverage["selected_open_count"])
        or coverage["missing_selected_open_count"]
        or coverage["unexpected_selected_open_count"]
    ):
        raise ValueError(
            "entry-time coverage anti-join failed: "
            f"missing={coverage['missing_selected_open_ids']} "
            f"unexpected={coverage['unexpected_selected_open_ids']}"
        )
    return (
        groups,
        binding_audit,
        mapped_source,
        candidate_audit,
        actual_open_audit,
        coverage,
    )


def build_pit_binding_audit(
    selected_open_groups: pd.DataFrame,
    closed_lots: pd.DataFrame,
    trades: pd.DataFrame,
    entry_risk: pd.DataFrame,
    entry_candidates: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, dict[str, Any]]]:
    """Independently prove unique, nonfuture risk/candidate bindings for selected opens."""
    if selected_open_groups.empty:
        return pd.DataFrame(columns=["requested_start_month", "open_trade_id"]), {}
    _require_columns(
        selected_open_groups,
        {"requested_start_month", "open_trade_id", "vt_symbol", "direction", "base_open_volume"},
    )
    _require_columns(closed_lots, {"requested_start_month", "open_trade_id", *_PIT_SELECTOR_FIELDS})
    _require_columns(trades, {"trade_id", "datetime", "vt_symbol", "direction", "offset", "volume"})
    _require_columns(
        entry_risk,
        {"entry_index", "datetime", "contract_vt_symbol", "direction", "volume", "projected_total_margin_after", "estimated_equity"},
    )
    _require_columns(
        entry_candidates,
        {"candidate_index", "datetime", "contract_vt_symbol", "direction", "candidate_status", "selected_volume"},
    )
    risks = entry_risk.copy().reset_index(drop=False).rename(columns={"index": "source_index"})
    candidates = entry_candidates.copy().reset_index(drop=False).rename(columns={"index": "source_index"})
    trade_by_id = {str(row["trade_id"]): row for row in trades.to_dict("records")}
    used_risks: set[int] = set()
    used_candidates: set[int] = set()
    audit_rows: list[dict[str, Any]] = []
    bindings: dict[str, dict[str, Any]] = {}

    for group in selected_open_groups.to_dict("records"):
        requested = str(group["requested_start_month"])
        open_id = str(group["open_trade_id"])
        trade = trade_by_id.get(open_id)
        if trade is None or str(trade.get("offset", "")).strip().lower() != "open":
            raise ValueError(f"PIT binding missing open trade: {open_id}")
        contract = str(group["vt_symbol"])
        direction = _normal_pit_direction(group["direction"])
        volume = _require_integer_scalar(group["base_open_volume"], "PIT binding volume")
        if (
            str(trade["vt_symbol"]) != contract
            or _normal_pit_direction(trade["direction"]) != direction
            or _require_integer_scalar(trade["volume"], "PIT trade volume") != volume
        ):
            raise ValueError(f"PIT binding trade identity mismatch: {open_id}")

        lots = closed_lots.loc[
            closed_lots["requested_start_month"].astype(str).eq(requested)
            & closed_lots["open_trade_id"].astype(str).eq(open_id)
        ]
        if lots.empty:
            raise ValueError(f"PIT binding missing selector lifecycle: {open_id}")
        selector: dict[str, Any] = {}
        for field in _PIT_SELECTOR_FIELDS:
            if lots[field].nunique(dropna=False) != 1:
                raise ValueError(f"PIT binding selector mismatch: {field} for {open_id}")
            selector[field] = _normalized_pit_value(field, lots[field].iloc[0])

        binding, audit = _match_pit_rows_for_open(
            trade, risks, candidates, used_risks, used_candidates
        )
        if int(audit["future_match_count"]) > 0:
            raise ValueError(f"PIT binding future match: {open_id}")
        for field, expected in selector.items():
            if binding[field] != expected:
                raise ValueError(f"PIT binding selector mismatch: {field} for {open_id}")
        bindings[open_id] = binding
        audit_rows.append({"requested_start_month": requested, **audit})
    return pd.DataFrame(audit_rows), bindings


def attach_pit_margin_to_orders(
    candidate_orders: pd.DataFrame,
    bindings: dict[str, dict[str, Any]],
) -> pd.DataFrame:
    result = candidate_orders.copy()
    result["c9_projected_total_margin_after"] = np.nan
    result["estimated_equity"] = np.nan
    for index, row in result.iterrows():
        open_id = str(row["open_trade_id"])
        if str(row["base_trade_id"]) != open_id:
            continue
        binding = bindings.get(open_id)
        if binding is None:
            raise ValueError(f"PIT binding missing for open order: {open_id}")
        result.at[index, "c9_projected_total_margin_after"] = _require_finite_scalar(
            binding["c9_projected_total_margin_after"], "c9_projected_total_margin_after"
        )
        result.at[index, "estimated_equity"] = _require_finite_scalar(
            binding["estimated_equity"], "estimated_equity"
        )
    return result


def build_contract_specs(
    metadata: dict[str, Any],
    contracts: set[str],
) -> tuple[dict[str, dict[str, float]], dict[str, Any]]:
    source_fields = {
        "size": "sizes",
        "margin_ratio": "margin_ratios",
        "slippage": "slippages",
        "rate": "rates",
    }
    specs: dict[str, dict[str, float]] = {}
    universe = set(map(str, metadata.get("vt_symbols", metadata.get("rates", {}).keys())))
    zero_counts = {"zero_rate_count": 0, "zero_slippage_count": 0, "zero_margin_ratio_count": 0}
    for contract in sorted(universe):
        for target, source in (("rate", "rates"), ("slippage", "slippages"), ("margin_ratio", "margin_ratios")):
            mapping = metadata.get(source)
            if not isinstance(mapping, dict) or contract not in mapping:
                raise ValueError(f"metadata audit missing {source}: {contract}")
            value = _require_finite_scalar(mapping[contract], f"metadata audit {contract}.{target}")
            if target == "rate":
                if value < 0.0:
                    raise ValueError(f"metadata audit invalid rate: {contract}")
                zero_counts["zero_rate_count"] += int(value == 0.0)
            else:
                zero_counts[f"zero_{target}_count"] += int(value == 0.0)
                if value <= 0.0:
                    raise ValueError(f"metadata audit invalid positive {target}: {contract}")
    for contract in sorted(contracts):
        spec: dict[str, float] = {}
        for target, source in source_fields.items():
            mapping = metadata.get(source)
            if not isinstance(mapping, dict) or contract not in mapping:
                raise ValueError(f"metadata audit missing {source}: {contract}")
            spec[target] = _require_finite_scalar(mapping[contract], f"metadata audit {contract}.{target}")
        if spec["size"] <= 0.0 or spec["slippage"] <= 0.0 or spec["margin_ratio"] <= 0.0 or spec["rate"] < 0.0:
            raise ValueError(f"metadata audit invalid positive spec: {contract}")
        specs[contract] = spec
    return specs, {
        "metadata_contract_count": len(specs),
        "metadata_universe_contract_count": len(universe),
        **zero_counts,
    }


_CANARY_SUMMARY_COLUMNS = {
    "requested_start_month",
    "cost_multiplier",
    "a_total_return_pct",
    "c_total_return_pct",
    "return_retention_pct",
    "a_max_drawdown_pct",
    "c_max_drawdown_pct",
    "a_longest_underwater_days",
    "c_longest_underwater_days",
    "b_cumulative_net_pnl",
    "b_bankrupt",
    "c_bankrupt",
}
for _summary_prefix in ("a", "b", "c"):
    _CANARY_SUMMARY_COLUMNS.update(
        {
            f"{_summary_prefix}_final_equity",
            f"{_summary_prefix}_total_return_pct",
            f"{_summary_prefix}_max_drawdown_pct",
            f"{_summary_prefix}_sharpe",
            f"{_summary_prefix}_total_slippage",
            f"{_summary_prefix}_total_commission",
            f"{_summary_prefix}_total_trade_count",
            f"{_summary_prefix}_nonzero_daily_win_rate_pct",
            f"{_summary_prefix}_longest_underwater_days",
        }
    )
_CANARY_AUDIT_COLUMNS = {
    "requested_start_month",
    "cost_multiplier",
    "current_ai_snapshot_pass",
    "current_ai_golden_membership_pass",
    "current_ai_golden_curve_applicable",
    "current_ai_golden_curve_pass",
    "current_c9_repeat_identity_pass",
    "repeat_source_manifest_pass",
    "repeat_worker_environment_pass",
    "pit_binding_fail_count",
    "future_match_count",
    "duplicate_satellite_open_count",
    "overclose_count",
    "nonflat_final_open_group_count",
    "missing_price_count",
    "fallback_count",
    "silent_default_count",
    "max_reconciliation_error",
    "max_proposed_broker10_pct",
    "max_eod_broker10_prior_pct",
    "max_eod_broker10_current_pct",
    "replay_bankrupt_count",
    "input_audit_pass",
    "eligible_open_count",
    "mapped_eligible_open_count",
    "selected_open_count",
    "missing_selected_open_count",
    "unexpected_selected_open_count",
    "actual_open_count",
    "actual_open_input_count",
    "actual_open_audit_row_count",
    "mapped_nonretry_open_count",
    "unmapped_actual_open_count",
    "retry_open_count",
    "pit_risk_source_count",
    "risk_input_count",
    "pit_source_ledger_row_count",
    "source_without_actual_open_count",
    "candidate_input_count",
    "pit_candidate_audit_row_count",
    "opened_candidate_count",
    "skipped_candidate_count",
    "opened_candidate_without_risk_count",
    "source_order_mismatch_count",
    "positive_volume_drift_count",
    "open_at_end_count",
    "expected_terminal_position_count",
    "unexpected_terminal_position_count",
    "max_terminal_position_reconciliation_error",
    "max_terminal_margin_reconciliation_error",
    "max_terminal_pnl_reconciliation_error",
}

_STATIC_AUDIT_COLUMNS = {
    "requested_start_month",
    "cost_multiplier",
    "input_audit_pass",
    "current_ai_snapshot_pass",
    "current_ai_golden_membership_pass",
    "current_ai_golden_curve_applicable",
    "current_ai_golden_curve_pass",
    "current_c9_repeat_identity_pass",
    "repeat_source_manifest_pass",
    "repeat_worker_environment_pass",
    "pit_binding_fail_count",
    "future_match_count",
    "actual_open_count",
    "actual_open_input_count",
    "actual_open_audit_row_count",
    "mapped_nonretry_open_count",
    "unmapped_actual_open_count",
    "retry_open_count",
    "pit_risk_source_count",
    "risk_input_count",
    "pit_source_ledger_row_count",
    "source_without_actual_open_count",
    "candidate_input_count",
    "pit_candidate_audit_row_count",
    "opened_candidate_count",
    "skipped_candidate_count",
    "opened_candidate_without_risk_count",
    "source_order_mismatch_count",
    "positive_volume_drift_count",
    "eligible_open_count",
    "mapped_eligible_open_count",
    "selected_open_count",
    "missing_selected_open_count",
    "unexpected_selected_open_count",
}


_IDENTITY_FAILURE_FIELDS = {
    "current_ai_snapshot_pass": "current_ai_snapshot_failed",
    "current_ai_golden_membership_pass": "current_ai_golden_membership_failed",
    "current_ai_golden_curve_pass": "current_ai_golden_curve_failed",
    "current_c9_repeat_identity_pass": "current_c9_repeat_identity_failed",
    "repeat_source_manifest_pass": "repeat_source_manifest_failed",
    "repeat_worker_environment_pass": "repeat_worker_environment_failed",
}


def _append_current_identity_failures(
    data: pd.DataFrame,
    failed: list[str],
) -> None:
    for field, failure in _IDENTITY_FAILURE_FIELDS.items():
        if not pd.to_numeric(data[field]).eq(1).all():
            failed.append(failure)
    applicable = pd.to_numeric(data["current_ai_golden_curve_applicable"], errors="raise")
    expected = pd.Series(
        [int(str(index) == "2020-01") for index in data.index],
        index=data.index,
        dtype="int64",
    )
    if not applicable.astype("int64").eq(expected).all():
        failed.append("current_ai_golden_curve_scope_failed")


def evaluate_static_audit(audits: pd.DataFrame) -> dict[str, Any]:
    """Evaluate only static identity, source mapping, and lifecycle coverage gates."""
    _require_columns(audits, _STATIC_AUDIT_COLUMNS)
    audits = audits.loc[
        pd.to_numeric(audits["cost_multiplier"], errors="coerce").eq(1.0)
    ].copy()
    if (
        audits["requested_start_month"].duplicated().any()
        or set(audits["requested_start_month"]) != set(CANARY_STARTS)
    ):
        raise ValueError("audit requires exactly four unique starts")
    data = audits.set_index("requested_start_month").loc[list(CANARY_STARTS)]
    _require_finite(data, tuple(_STATIC_AUDIT_COLUMNS - {"requested_start_month"}))
    failed: list[str] = []
    if not pd.to_numeric(data["input_audit_pass"]).eq(1).all():
        failed.append("input_audit_failed")
    _append_current_identity_failures(data, failed)
    if pd.to_numeric(data["pit_binding_fail_count"]).ne(0).any():
        failed.append("pit_binding_failed")
    if pd.to_numeric(data["future_match_count"]).ne(0).any():
        failed.append("future_pit_match")
    if pd.to_numeric(data["unmapped_actual_open_count"]).ne(0).any():
        failed.append("actual_open_mapping_failed")
    if pd.to_numeric(data["source_order_mismatch_count"]).ne(0).any():
        failed.append("source_order_mismatch")
    if pd.to_numeric(data["positive_volume_drift_count"]).ne(0).any():
        failed.append("positive_volume_drift")
    if pd.to_numeric(data["opened_candidate_without_risk_count"]).ne(0).any():
        failed.append("opened_candidate_without_risk")
    if (
        not pd.to_numeric(data["actual_open_input_count"]).eq(
            pd.to_numeric(data["actual_open_audit_row_count"])
        ).all()
        or not pd.to_numeric(data["actual_open_input_count"]).eq(
            pd.to_numeric(data["actual_open_count"])
        ).all()
    ):
        failed.append("actual_open_audit_incomplete")
    if not pd.to_numeric(data["actual_open_count"]).eq(
        pd.to_numeric(data["actual_open_audit_row_count"])
    ).all():
        if "actual_open_audit_incomplete" not in failed:
            failed.append("actual_open_audit_incomplete")
    if not pd.to_numeric(data["actual_open_count"]).eq(
        pd.to_numeric(data["mapped_nonretry_open_count"])
        + pd.to_numeric(data["retry_open_count"])
    ).all():
        failed.append("actual_open_classification_incomplete")
    if not pd.to_numeric(data["pit_risk_source_count"]).eq(
        pd.to_numeric(data["mapped_nonretry_open_count"])
        + pd.to_numeric(data["source_without_actual_open_count"])
    ).all():
        failed.append("source_ledger_incomplete")
    if (
        not pd.to_numeric(data["risk_input_count"]).eq(
            pd.to_numeric(data["pit_source_ledger_row_count"])
        ).all()
        or not pd.to_numeric(data["risk_input_count"]).eq(
            pd.to_numeric(data["pit_risk_source_count"])
        ).all()
    ):
        failed.append("risk_ledger_incomplete")
    if (
        not pd.to_numeric(data["candidate_input_count"]).eq(
            pd.to_numeric(data["pit_candidate_audit_row_count"])
        ).all()
        or not pd.to_numeric(data["candidate_input_count"]).eq(
            pd.to_numeric(data["opened_candidate_count"])
            + pd.to_numeric(data["skipped_candidate_count"])
        ).all()
    ):
        failed.append("candidate_audit_incomplete")
    if (
        pd.to_numeric(data["missing_selected_open_count"]).ne(0).any()
        or pd.to_numeric(data["unexpected_selected_open_count"]).ne(0).any()
        or not pd.to_numeric(data["eligible_open_count"]).eq(
            pd.to_numeric(data["mapped_eligible_open_count"])
        ).all()
        or not pd.to_numeric(data["eligible_open_count"]).eq(
            pd.to_numeric(data["selected_open_count"])
        ).all()
    ):
        failed.append("coverage_failed")
    return {
        "mode": "audit",
        "audit_pass": not failed,
        "canary_pass": False,
        "failed_checks": failed or ["canary_not_run"],
        "full_allowed": False,
    }


def evaluate_canary(summary: pd.DataFrame, audits: pd.DataFrame) -> dict[str, Any]:
    """Evaluate every frozen 1x canary condition as one conjunctive decision."""
    _require_columns(summary, _CANARY_SUMMARY_COLUMNS)
    _require_columns(audits, _CANARY_AUDIT_COLUMNS)
    summary = summary.loc[pd.to_numeric(summary["cost_multiplier"], errors="coerce").eq(1.0)].copy()
    audits = audits.loc[pd.to_numeric(audits["cost_multiplier"], errors="coerce").eq(1.0)].copy()
    for frame, label in ((summary, "summary"), (audits, "audit")):
        if frame["requested_start_month"].duplicated().any() or set(frame["requested_start_month"]) != set(CANARY_STARTS):
            raise ValueError(f"canary requires exactly four unique starts in {label}")
    s = summary.set_index("requested_start_month").loc[list(CANARY_STARTS)]
    a = audits.set_index("requested_start_month").loc[list(CANARY_STARTS)]
    numeric_summary = tuple(_CANARY_SUMMARY_COLUMNS - {"requested_start_month"})
    numeric_audit = tuple(_CANARY_AUDIT_COLUMNS - {"requested_start_month"})
    _require_finite(s, numeric_summary)
    _require_finite(a, numeric_audit)

    failed: list[str] = []
    if not pd.to_numeric(a["input_audit_pass"]).eq(1).all():
        failed.append("input_audit_failed")
    _append_current_identity_failures(a, failed)
    if (
        pd.to_numeric(a["missing_selected_open_count"]).gt(0).any()
        or pd.to_numeric(a["unexpected_selected_open_count"]).gt(0).any()
        or not pd.to_numeric(a["eligible_open_count"]).eq(
            pd.to_numeric(a["mapped_eligible_open_count"])
        ).all()
        or not pd.to_numeric(a["eligible_open_count"]).eq(
            pd.to_numeric(a["selected_open_count"])
        ).all()
    ):
        failed.append("coverage_failed")
    if pd.to_numeric(a["unmapped_actual_open_count"]).gt(0).any():
        failed.append("actual_open_mapping_failed")
    if pd.to_numeric(a["source_order_mismatch_count"]).ne(0).any():
        failed.append("source_order_mismatch")
    if pd.to_numeric(a["positive_volume_drift_count"]).ne(0).any():
        failed.append("positive_volume_drift")
    if pd.to_numeric(a["opened_candidate_without_risk_count"]).ne(0).any():
        failed.append("opened_candidate_without_risk")
    if (
        not pd.to_numeric(a["actual_open_input_count"]).eq(
            pd.to_numeric(a["actual_open_audit_row_count"])
        ).all()
        or not pd.to_numeric(a["actual_open_input_count"]).eq(
            pd.to_numeric(a["actual_open_count"])
        ).all()
    ):
        failed.append("actual_open_audit_incomplete")
    if not pd.to_numeric(a["actual_open_count"]).eq(
        pd.to_numeric(a["actual_open_audit_row_count"])
    ).all():
        if "actual_open_audit_incomplete" not in failed:
            failed.append("actual_open_audit_incomplete")
    if not pd.to_numeric(a["actual_open_count"]).eq(
        pd.to_numeric(a["mapped_nonretry_open_count"])
        + pd.to_numeric(a["retry_open_count"])
    ).all():
        failed.append("actual_open_classification_incomplete")
    if not pd.to_numeric(a["pit_risk_source_count"]).eq(
        pd.to_numeric(a["mapped_nonretry_open_count"])
        + pd.to_numeric(a["source_without_actual_open_count"])
    ).all():
        failed.append("source_ledger_incomplete")
    if (
        not pd.to_numeric(a["risk_input_count"]).eq(
            pd.to_numeric(a["pit_source_ledger_row_count"])
        ).all()
        or not pd.to_numeric(a["risk_input_count"]).eq(
            pd.to_numeric(a["pit_risk_source_count"])
        ).all()
    ):
        failed.append("risk_ledger_incomplete")
    if (
        not pd.to_numeric(a["candidate_input_count"]).eq(
            pd.to_numeric(a["pit_candidate_audit_row_count"])
        ).all()
        or not pd.to_numeric(a["candidate_input_count"]).eq(
            pd.to_numeric(a["opened_candidate_count"])
            + pd.to_numeric(a["skipped_candidate_count"])
        ).all()
    ):
        failed.append("candidate_audit_incomplete")
    if (
        pd.to_numeric(a["unexpected_terminal_position_count"]).gt(0).any()
        or pd.to_numeric(a["max_terminal_position_reconciliation_error"]).gt(IDENTITY_TOLERANCE).any()
    ):
        failed.append("terminal_reconciliation_failed")
    if pd.to_numeric(a["max_terminal_margin_reconciliation_error"]).gt(IDENTITY_TOLERANCE).any():
        failed.append("terminal_margin_reconciliation_failed")
    if pd.to_numeric(a["max_terminal_pnl_reconciliation_error"]).gt(IDENTITY_TOLERANCE).any():
        failed.append("terminal_pnl_reconciliation_failed")
    if pd.to_numeric(a["pit_binding_fail_count"]).gt(0).any():
        failed.append("pit_binding_failed")
    if pd.to_numeric(a["future_match_count"]).gt(0).any():
        failed.append("future_pit_match")
    if a[["duplicate_satellite_open_count", "overclose_count", "nonflat_final_open_group_count"]].apply(pd.to_numeric).gt(0).any().any():
        failed.append("order_lifecycle_failed")
    if a[["missing_price_count", "fallback_count", "silent_default_count"]].apply(pd.to_numeric).gt(0).any().any():
        failed.append("missing_or_defaulted_input")
    if pd.to_numeric(a["max_reconciliation_error"]).gt(IDENTITY_TOLERANCE).any():
        failed.append("reconciliation_failed")
    broker_columns = ["max_proposed_broker10_pct", "max_eod_broker10_prior_pct", "max_eod_broker10_current_pct"]
    if a[broker_columns].apply(pd.to_numeric).gt(100.0 + 1e-12).any().any():
        failed.append("broker10_exceeded")
    if (
        pd.to_numeric(a["replay_bankrupt_count"]).gt(0).any()
        or pd.to_numeric(s["b_bankrupt"]).gt(0).any()
        or pd.to_numeric(s["c_bankrupt"]).gt(0).any()
    ):
        failed.append("bankrupt")
    if pd.to_numeric(s["return_retention_pct"]).lt(70.0).any():
        failed.append("return_retention_below_70")
    historical = s.loc[["2020-01", "2022-01", "2022-07"]]
    if not (pd.to_numeric(historical["c_max_drawdown_pct"]) > pd.to_numeric(historical["a_max_drawdown_pct"])).all():
        failed.append("historical_drawdown_not_strictly_better")
    drawdowns_2022 = s.loc[["2022-01", "2022-07"]]
    if not (pd.to_numeric(drawdowns_2022["c_max_drawdown_pct"]) > pd.to_numeric(drawdowns_2022["a_max_drawdown_pct"])).all():
        failed.append("2022_drawdown_not_strictly_better")
    latest = s.loc["2026-01"]
    if float(latest["c_max_drawdown_pct"]) < float(latest["a_max_drawdown_pct"]) - 1.0:
        failed.append("latest_drawdown_worse_over_1pp")
    starts_2022 = s.loc[["2022-01", "2022-07"]]
    c_uw = pd.to_numeric(starts_2022["c_longest_underwater_days"])
    a_uw = pd.to_numeric(starts_2022["a_longest_underwater_days"])
    if (c_uw > a_uw).any():
        failed.append("2022_underwater_worse")
    if not (c_uw < a_uw).any():
        failed.append("2022_underwater_no_strict_improvement")
    b_positive = pd.to_numeric(s["b_cumulative_net_pnl"]).gt(0.0)
    if int(b_positive.sum()) < 3:
        failed.append("b_positive_below_3_of_4")
    if not b_positive.loc[["2022-01", "2022-07"]].all():
        failed.append("b_2022_not_both_positive")
    reasons = [str(value) for value in a.get("replay_bankrupt_reason", pd.Series(dtype=str)).dropna() if str(value)]
    return {
        "mode": "canary",
        "canary_pass": not failed,
        "failed_checks": failed,
        "bankrupt_reasons": reasons,
        "full_allowed": False,
        "cost_stress_allowed": not failed,
    }


def bankrupt_failure_audit(
    requested_start_month: str,
    cost_multiplier: float,
    error: Exception,
) -> dict[str, Any]:
    message = str(error)
    if "non-positive satellite equity" not in message and "non-positive combined equity" not in message:
        raise error
    return {
        "requested_start_month": requested_start_month,
        "cost_multiplier": float(cost_multiplier),
        "replay_bankrupt_count": 1,
        "replay_bankrupt_reason": message,
    }


def _drawdown_pct(equity: pd.Series, initial_capital: float = _LEDGER_CAPITAL) -> pd.Series:
    values = pd.to_numeric(equity, errors="raise").astype(float)
    capital = _require_finite_scalar(initial_capital, "initial capital")
    if capital <= 0.0 or not np.isfinite(values).all():
        raise ValueError("positive finite equity path required")
    highs = np.maximum.accumulate(np.concatenate(([capital], values.to_numpy())))[1:]
    return pd.Series((values.to_numpy() / highs - 1.0) * 100.0, index=values.index)


def _longest_underwater_days(
    dates: pd.Series,
    equity: pd.Series,
    initial_capital: float = _LEDGER_CAPITAL,
) -> int:
    frame = pd.DataFrame({"date": pd.to_datetime(dates), "equity": pd.to_numeric(equity, errors="raise")})
    underwater_start: pd.Timestamp | None = None
    longest = 0
    high = _require_finite_scalar(initial_capital, "initial capital")
    if high <= 0.0:
        raise ValueError("positive initial capital required")
    for row in frame.sort_values("date").itertuples(index=False):
        if float(row.equity) >= high:
            high = max(high, float(row.equity))
            if underwater_start is not None:
                longest = max(longest, int((pd.Timestamp(row.date) - underwater_start).days))
                underwater_start = None
        elif underwater_start is None:
            underwater_start = pd.Timestamp(row.date)
    if underwater_start is not None and len(frame.index):
        longest = max(longest, int((frame["date"].max() - underwater_start).days))
    return longest


def _equity_daily_changes(equity: pd.Series, initial_capital: float = _LEDGER_CAPITAL) -> pd.Series:
    values = pd.to_numeric(equity, errors="raise").astype(float)
    previous = np.concatenate(([_require_finite_scalar(initial_capital, "initial capital")], values.to_numpy()[:-1]))
    return pd.Series(values.to_numpy() - previous, index=values.index)


def _equity_daily_returns(equity: pd.Series, initial_capital: float = _LEDGER_CAPITAL) -> pd.Series:
    values = pd.to_numeric(equity, errors="raise").astype(float)
    previous = np.concatenate(([_require_finite_scalar(initial_capital, "initial capital")], values.to_numpy()[:-1]))
    if (previous <= 0.0).any():
        raise ValueError("positive prior equity required")
    return pd.Series(values.to_numpy() / previous - 1.0, index=values.index)


def _daily_sharpe(equity: pd.Series) -> float:
    returns = _equity_daily_returns(equity)
    if len(returns.index) < 2:
        return 0.0
    standard_deviation = float(returns.std(ddof=1))
    if math.isclose(standard_deviation, 0.0, abs_tol=1e-15):
        return 0.0
    return float(returns.mean() / standard_deviation * math.sqrt(252.0))


def _nonzero_daily_win_rate_pct(equity: pd.Series) -> float:
    changes = _equity_daily_changes(equity)
    nonzero = changes.loc[changes.ne(0.0)]
    return float(nonzero.gt(0.0).mean() * 100.0) if len(nonzero.index) else 0.0


def summarize_start(daily: pd.DataFrame, requested_start_month: str, cost_multiplier: float) -> dict[str, Any]:
    required = {
        "date",
        "account_equity",
        "satellite_equity",
        "combined_equity",
        "satellite_cumulative_net_pnl",
        "slippage",
        "commission",
        "trade_count",
        "satellite_slippage",
        "satellite_commission",
        "satellite_executed_order_count",
    }
    _require_columns(daily, required)
    if daily.empty:
        raise ValueError("empty daily summary")
    first_capital = _LEDGER_CAPITAL
    curves = {
        "a": pd.to_numeric(daily["account_equity"], errors="raise"),
        "b": pd.to_numeric(daily["satellite_equity"], errors="raise"),
        "c": pd.to_numeric(daily["combined_equity"], errors="raise"),
    }
    a_return = (float(curves["a"].iloc[-1]) / first_capital - 1.0) * 100.0
    c_return = (float(curves["c"].iloc[-1]) / first_capital - 1.0) * 100.0
    retention = c_return / a_return * 100.0 if not math.isclose(a_return, 0.0) else (-math.inf if c_return < 0 else math.inf)
    if not np.isfinite(retention):
        raise ValueError("non-finite return retention")
    result: dict[str, Any] = {
        "requested_start_month": requested_start_month,
        "cost_multiplier": float(cost_multiplier),
        "return_retention_pct": retention,
        "b_cumulative_net_pnl": float(daily["satellite_cumulative_net_pnl"].iloc[-1]),
        "b_bankrupt": 0,
        "c_bankrupt": 0,
    }
    slippages = {
        "a": pd.to_numeric(daily["slippage"], errors="raise"),
        "b": pd.to_numeric(daily["satellite_slippage"], errors="raise"),
    }
    commissions = {
        "a": pd.to_numeric(daily["commission"], errors="raise"),
        "b": pd.to_numeric(daily["satellite_commission"], errors="raise"),
    }
    trade_counts = {
        "a": pd.to_numeric(daily["trade_count"], errors="raise"),
        "b": pd.to_numeric(daily["satellite_executed_order_count"], errors="raise"),
    }
    slippages["c"] = slippages["a"] + slippages["b"]
    commissions["c"] = commissions["a"] + commissions["b"]
    trade_counts["c"] = trade_counts["a"] + trade_counts["b"]
    for prefix, curve in curves.items():
        result.update({
            f"{prefix}_final_equity": float(curve.iloc[-1]),
            f"{prefix}_total_return_pct": float((curve.iloc[-1] / first_capital - 1.0) * 100.0),
            f"{prefix}_max_drawdown_pct": float(_drawdown_pct(curve).min()),
            f"{prefix}_sharpe": _daily_sharpe(curve),
            f"{prefix}_total_slippage": float(slippages[prefix].sum()),
            f"{prefix}_total_commission": float(commissions[prefix].sum()),
            f"{prefix}_total_trade_count": int(trade_counts[prefix].sum()),
            f"{prefix}_nonzero_daily_win_rate_pct": _nonzero_daily_win_rate_pct(curve),
            f"{prefix}_longest_underwater_days": _longest_underwater_days(daily["date"], curve),
        })
    return result


_SOURCE_MANIFEST_INTEGER_COLUMNS = (
    "size",
    "mtime_ns",
    "observed_read",
    "first_read_mtime_ns",
    "last_read_mtime_ns",
    "same_content_rewrite_count",
    "post_read_same_content_rewrite",
)


def _coerce_source_manifest_integer_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Keep nanosecond lineage exact across CSV round-trips."""
    result = frame.copy()
    for column in _SOURCE_MANIFEST_INTEGER_COLUMNS:
        if column in result.columns:
            try:
                result[column] = pd.array(result[column], dtype="Int64")
            except (TypeError, ValueError):
                raise ValueError(f"source manifest invalid integer column: {column}") from None
    return result


def read_source_manifest_csv(path: Path) -> pd.DataFrame:
    """Read worker lineage without converting nullable nanoseconds to float."""
    try:
        frame = pd.read_csv(
            Path(path),
            encoding="utf-8-sig",
            dtype={column: "Int64" for column in _SOURCE_MANIFEST_INTEGER_COLUMNS},
        )
    except (TypeError, ValueError) as error:
        raise ValueError(f"source manifest CSV invalid: {error}") from None
    return _coerce_source_manifest_integer_columns(frame)


def build_source_manifest(
    paths: list[Path] | tuple[Path, ...],
    *,
    observed_snapshots: dict[Path, dict[str, Any]] | None = None,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    seen: set[Path] = set()
    observed = {
        Path(path).expanduser().resolve(): dict(snapshot)
        for path, snapshot in (observed_snapshots or {}).items()
    }
    for raw_path in paths:
        path = Path(raw_path).expanduser().resolve()
        if path in seen:
            continue
        seen.add(path)
        try:
            current = _file_snapshot(path)
        except ValueError:
            if path in observed:
                raise ValueError(f"observed source changed after read: {path}") from None
            raise ValueError(f"source manifest missing file: {path}") from None
        if path in observed:
            expected = observed[path]
            if (current["size"], current["sha256"]) != (
                expected["size"],
                expected["sha256"],
            ):
                raise ValueError(f"observed source changed after read: {path}")
            rows.append(
                {
                    **current,
                    "observed_read": 1,
                    "first_read_mtime_ns": int(
                        expected.get("first_read_mtime_ns", expected["mtime_ns"])
                    ),
                    "last_read_mtime_ns": int(
                        expected.get("last_read_mtime_ns", expected["mtime_ns"])
                    ),
                    "same_content_rewrite_count": int(
                        expected.get("same_content_rewrite_count", 0)
                    ),
                    "post_read_same_content_rewrite": int(
                        current["mtime_ns"] != expected["mtime_ns"]
                    ),
                }
            )
        else:
            rows.append(
                {
                    **current,
                    "observed_read": 0,
                    "first_read_mtime_ns": int(current["mtime_ns"]),
                    "last_read_mtime_ns": int(current["mtime_ns"]),
                    "same_content_rewrite_count": 0,
                    "post_read_same_content_rewrite": 0,
                }
            )
    frame = pd.DataFrame(
        rows,
        columns=[
            "path",
            "size",
            "mtime_ns",
            "sha256",
            "observed_read",
            "first_read_mtime_ns",
            "last_read_mtime_ns",
            "same_content_rewrite_count",
            "post_read_same_content_rewrite",
        ],
    )
    return _coerce_source_manifest_integer_columns(frame)


def worker_environment_contract() -> dict[str, str]:
    """Return a secret-free runtime contract that must match across workers."""
    sanitized_environment = effective_identity_worker_environment()
    environment_json = json.dumps(
        sanitized_environment, sort_keys=True, separators=(",", ":")
    )
    return {
        "python_executable": str(Path(sys.executable).resolve()),
        "python_version": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "pandas_version": str(pd.__version__),
        "numpy_version": str(np.__version__),
        "timezone": str(sanitized_environment.get("TZ", "")),
        "lang": str(sanitized_environment.get("LANG", "")),
        "lc_all": str(sanitized_environment.get("LC_ALL", "")),
        "pythonhashseed": str(sanitized_environment.get("PYTHONHASHSEED", "")),
        "process_environment_json": environment_json,
        "process_environment_sha256": hashlib.sha256(
            environment_json.encode("utf-8")
        ).hexdigest(),
    }


_IDENTITY_WORKER_INHERITED_ENV_KEYS = (
    "PATH",
    "HOME",
    "TMPDIR",
    "LANG",
    "LC_ALL",
    "TZ",
    "PYTHONPATH",
    "DYLD_LIBRARY_PATH",
    "DYLD_FALLBACK_LIBRARY_PATH",
)


def identity_worker_subprocess_environment() -> dict[str, str]:
    """Build the complete, secret-free environment inherited by worker subprocesses."""
    environment = {
        key: str(os.environ[key])
        for key in _IDENTITY_WORKER_INHERITED_ENV_KEYS
        if key in os.environ
    }
    environment.setdefault("PATH", os.defpath)
    environment.setdefault("HOME", str(Path.home()))
    environment.setdefault("TMPDIR", tempfile.gettempdir())
    environment.update(
        {
            "PYTHONHASHSEED": "0",
            "PYTHONNOUSERSITE": "1",
            "MPLBACKEND": "Agg",
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "VECLIB_MAXIMUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
            "QMT_BACKTEST_ORIGINAL_CWD": str(_REPO_ROOT),
            "QMT_BACKTEST_PROJECT_ROOT_GUARD": "1",
        }
    )
    return environment


def effective_identity_worker_environment() -> dict[str, str]:
    """Expected worker environment after the local Python runtime startup hook."""
    environment = identity_worker_subprocess_environment()
    environment["_RJEM_MALLOC_CONF"] = "dirty_decay_ms:500,muzzy_decay_ms:-1"
    return environment


def validate_worker_environment_contract(contract: dict[str, Any]) -> None:
    """Require the complete expected sanitized worker environment and runtime identity."""
    if not isinstance(contract, dict):
        raise ValueError("worker environment contract must be a mapping")
    expected = worker_environment_contract()
    if set(contract) != set(expected):
        raise ValueError("worker environment contract fields incomplete")
    environment_json = str(contract.get("process_environment_json", ""))
    try:
        parsed_environment = json.loads(environment_json)
    except json.JSONDecodeError:
        raise ValueError("worker environment contract JSON invalid") from None
    if not isinstance(parsed_environment, dict):
        raise ValueError("worker environment contract JSON must be an object")
    expected_environment = effective_identity_worker_environment()
    if parsed_environment != expected_environment:
        raise ValueError("worker environment contract sanitized environment drift")
    digest = hashlib.sha256(environment_json.encode("utf-8")).hexdigest()
    if str(contract.get("process_environment_sha256", "")) != digest:
        raise ValueError("worker environment contract SHA256 mismatch")
    if contract != expected:
        raise ValueError("worker environment contract runtime drift")


def require_sanitized_identity_worker_process_environment() -> None:
    """Reject direct worker invocation with inherited or unknown environment keys."""
    actual = {key: str(value) for key, value in os.environ.items()}
    expected = effective_identity_worker_environment()
    if actual != expected:
        raise ValueError("identity worker process environment is not sanitized")


def write_identity_worker_snapshot(
    requested_start_month: str,
    output_dir: Path,
) -> None:
    """Run one isolated current C9 anchor and atomically publish its audit payload."""
    if not _REQUESTED_START_MONTH_PATTERN.fullmatch(str(requested_start_month)):
        raise ValueError("identity worker invalid requested start month")
    output_dir = Path(output_dir).expanduser().resolve()
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    if output_dir.exists():
        raise ValueError("identity worker output already exists")
    require_sanitized_identity_worker_process_environment()

    runtime = _load_runtime_bridge()
    runtime_ai_path = Path(getattr(runtime, "current_ai_path", CURRENT_AI_PATH)).expanduser().resolve()
    if runtime_ai_path != Path(CURRENT_AI_PATH).expanduser().resolve():
        raise ValueError("identity worker official current AI path drift")
    observed: dict[Path, dict[str, Any]] = {}
    current_ai, ai_audit = audit_current_ai_snapshot(
        CURRENT_AI_PATH,
        expected_sha256=CURRENT_AI_EXPECTED_SHA256,
        expected_rows=CURRENT_AI_EXPECTED_ROWS,
        expected_eval_dates=CURRENT_AI_EXPECTED_EVAL_DATES,
        observed_source_paths=observed,
    )
    with capture_pandas_read_csv_paths(observed):
        golden_ai = pd.read_csv(CURRENT_AI_GOLDEN_ELIGIBILITY_PATH, encoding="utf-8-sig")
    membership_audit = assert_current_ai_golden_membership(current_ai, golden_ai)
    metadata = load_runtime_metadata(runtime, observed)
    start = pd.Timestamp(f"{requested_start_month}-01")
    frames = _run_base_with_metadata(
        start,
        ANALYSIS_END,
        runtime,
        metadata,
        observed_source_paths=observed,
    )
    manifest = build_source_manifest(
        [*runtime.source_paths, *sorted(observed, key=str)],
        observed_snapshots=observed,
    )
    environment = worker_environment_contract()
    payload = {
        "requested_start_month": str(requested_start_month),
        "analysis_end": ANALYSIS_END.date().isoformat(),
        "metadata": metadata,
        "frames": frames,
        "ai_audit": ai_audit,
        "membership_audit": membership_audit,
        "environment": environment,
    }

    temporary = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.", dir=output_dir.parent))
    try:
        pd.to_pickle(payload, temporary / "payload.pkl")
        manifest.to_csv(temporary / "source_manifest.csv", index=False, encoding="utf-8-sig")
        (temporary / "worker.json").write_text(
            json.dumps(
                {
                    "requested_start_month": str(requested_start_month),
                    "analysis_end": ANALYSIS_END.date().isoformat(),
                    "environment": environment,
                    "ai_audit": ai_audit,
                    "membership_audit": membership_audit,
                    "performance_metrics_run": False,
                },
                ensure_ascii=False,
                indent=2,
                allow_nan=False,
            ),
            encoding="utf-8",
        )
        os.replace(temporary, output_dir)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def launch_identity_worker(
    requested_start_month: str,
    output_dir: Path,
) -> None:
    """Launch a fresh Python process so Stage901 module caches cannot be shared."""
    output_dir = Path(output_dir).expanduser().resolve()
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--mode",
        "identity-worker",
        "--start-month",
        str(requested_start_month),
        "--worker-output",
        str(output_dir),
    ]
    try:
        subprocess.run(
            command,
            cwd=str(_REPO_ROOT),
            check=True,
            capture_output=True,
            text=True,
            timeout=1_800,
            env=identity_worker_subprocess_environment(),
        )
    except subprocess.CalledProcessError as error:
        stderr = str(error.stderr or "").strip()
        tail = stderr[-4_000:]
        raise RuntimeError(
            f"identity worker failed for {requested_start_month}: {tail}"
        ) from None
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(
            f"identity worker timed out for {requested_start_month} after {error.timeout}s"
        ) from None


def _load_identity_worker_snapshot(
    output_dir: Path,
    requested_start_month: str,
) -> dict[str, Any]:
    output_dir = Path(output_dir).expanduser().resolve()
    required_files = {
        "payload": output_dir / "payload.pkl",
        "manifest": output_dir / "source_manifest.csv",
        "worker": output_dir / "worker.json",
    }
    missing = [name for name, path in required_files.items() if not path.is_file()]
    if missing:
        raise ValueError(f"identity worker missing outputs: {missing}")
    payload = pd.read_pickle(required_files["payload"])
    if not isinstance(payload, dict):
        raise ValueError("identity worker invalid payload")
    worker = json.loads(required_files["worker"].read_text(encoding="utf-8"))
    manifest = read_source_manifest_csv(required_files["manifest"])
    for label, value in (("payload", payload), ("worker", worker)):
        if str(value.get("requested_start_month", "")) != str(requested_start_month):
            raise ValueError(f"identity worker {label} start drift")
        if str(value.get("analysis_end", "")) != ANALYSIS_END.date().isoformat():
            raise ValueError(f"identity worker {label} end drift")
    if bool(worker.get("performance_metrics_run", True)):
        raise ValueError("identity worker must not run performance metrics")
    for field in ("environment", "ai_audit", "membership_audit"):
        if payload.get(field) != worker.get(field):
            raise ValueError(f"identity worker {field} evidence drift")
    validate_worker_environment_contract(payload.get("environment", {}))
    if int(payload.get("ai_audit", {}).get("current_ai_snapshot_pass", 0)) != 1:
        raise ValueError("identity worker current AI snapshot failed")
    if int(
        payload.get("membership_audit", {}).get("current_ai_golden_membership_pass", 0)
    ) != 1:
        raise ValueError("identity worker current-AI golden membership failed")
    if not isinstance(payload.get("frames"), dict) or not isinstance(payload.get("metadata"), dict):
        raise ValueError("identity worker missing frames or metadata")
    return {
        **payload,
        "source_manifest": manifest,
        "worker_evidence": worker,
        "output_dir": output_dir,
    }


def load_repeat_worker_pair(
    requested_start_month: str,
    root: Path,
    *,
    launcher: Any | None = None,
) -> dict[str, Any]:
    """Launch and validate two isolated current-C9 worker snapshots."""
    if not _REQUESTED_START_MONTH_PATTERN.fullmatch(str(requested_start_month)):
        raise ValueError("repeat worker invalid requested start month")
    root = Path(root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    resolved_launcher = launch_identity_worker if launcher is None else launcher
    outputs = [
        root / f"{requested_start_month}-worker-a",
        root / f"{requested_start_month}-worker-b",
    ]
    if outputs[0] == outputs[1]:
        raise ValueError("repeat workers require distinct output directories")
    snapshots: list[dict[str, Any]] = []
    for output in outputs:
        resolved_launcher(str(requested_start_month), output)
        snapshots.append(_load_identity_worker_snapshot(output, str(requested_start_month)))
    first, second = snapshots
    if first["environment"] != second["environment"]:
        raise ValueError("repeat worker environment drift")
    if first["ai_audit"] != second["ai_audit"]:
        raise ValueError("repeat worker current AI audit drift")
    if first["membership_audit"] != second["membership_audit"]:
        raise ValueError("repeat worker golden membership audit drift")
    manifest_audit, manifest_ledger = compare_repeat_source_manifests(
        first["source_manifest"],
        second["source_manifest"],
        str(requested_start_month),
    )
    return {
        "first": first,
        "second": second,
        "manifest_audit": manifest_audit,
        "manifest_ledger": manifest_ledger,
    }


def finalize_worker_source_manifest(
    manifests_by_anchor: dict[str, list[pd.DataFrame]],
) -> pd.DataFrame:
    """Rehash the cross-anchor input union while preserving pair-level identity."""
    if not isinstance(manifests_by_anchor, dict) or not manifests_by_anchor:
        raise ValueError("worker source manifest anchors are empty")
    if set(map(str, manifests_by_anchor)) != set(CANARY_STARTS):
        raise ValueError("worker source manifest four-anchor coverage incomplete")
    manifest_rows: list[pd.DataFrame] = []
    for requested_start_month, pair in manifests_by_anchor.items():
        if not _REQUESTED_START_MONTH_PATTERN.fullmatch(str(requested_start_month)):
            raise ValueError("worker source manifest invalid anchor")
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise ValueError("worker source manifest anchor requires exactly two workers")
        first, second = (
            _coerce_source_manifest_integer_columns(pair[0]),
            _coerce_source_manifest_integer_columns(pair[1]),
        )
        compare_repeat_source_manifests(first, second, str(requested_start_month))
        manifest_rows.extend(
            [
                manifest.assign(
                    requested_start_month=str(requested_start_month),
                    worker_snapshot_index=worker_index,
                )
                for worker_index, manifest in enumerate(pair)
            ]
        )
    all_rows = pd.concat(manifest_rows, ignore_index=True, sort=False)
    all_rows = _coerce_source_manifest_integer_columns(all_rows)
    _require_columns(all_rows, {"path", "size", "mtime_ns", "sha256"})
    if all_rows["path"].isna().any() or all_rows["path"].astype(str).str.strip().eq("").any():
        raise ValueError("worker source manifest missing path")
    sizes = pd.to_numeric(all_rows["size"], errors="coerce")
    if (
        not np.isfinite(sizes).all()
        or sizes.lt(0).any()
        or not sizes.eq(np.floor(sizes)).all()
        or not all_rows["sha256"].astype(str).str.fullmatch(r"[0-9a-f]{64}").all()
    ):
        raise ValueError("worker source manifest invalid content identity")
    all_rows = all_rows.assign(size=sizes.astype("int64"))
    drifted: list[dict[str, Any]] = []
    for path, group in all_rows.groupby("path", sort=False):
        if group["size"].nunique(dropna=False) != 1 or group["sha256"].astype(str).nunique() != 1:
            drifted.append(
                {
                    "path": str(path),
                    "sizes": sorted(set(int(value) for value in group["size"])),
                    "sha256": sorted(set(group["sha256"].astype(str))),
                    "anchors": sorted(set(group["requested_start_month"].astype(str))),
                }
            )
    if drifted:
        raise ValueError(
            "cross-anchor source manifest drift: "
            + json.dumps(drifted, ensure_ascii=False, sort_keys=True)
        )
    expected = (
        all_rows.sort_values(
            ["path", "requested_start_month", "worker_snapshot_index"],
            kind="mergesort",
        )
        .drop_duplicates("path", keep="first")
        .loc[:, ["path", "size", "mtime_ns", "sha256"]]
        .reset_index(drop=True)
    )
    paths = [Path(value) for value in expected["path"].astype(str).tolist()]
    final = build_source_manifest(paths)
    compare_repeat_source_manifests(expected, final, "final-source-union-snapshot")
    grouped = {str(path): group for path, group in all_rows.groupby("path", sort=False)}
    for index, row in final.iterrows():
        path = str(row["path"])
        group = grouped[path]
        observed = (
            group["observed_read"].astype("Int64")
            if "observed_read" in group
            else pd.Series(0, index=group.index, dtype="Int64")
        )
        final.at[index, "observed_read"] = int(observed.max())
        first_values = (
            group["first_read_mtime_ns"].astype("Int64")
            if "first_read_mtime_ns" in group
            else group["mtime_ns"].astype("Int64")
        )
        last_values = (
            group["last_read_mtime_ns"].astype("Int64")
            if "last_read_mtime_ns" in group
            else group["mtime_ns"].astype("Int64")
        )
        rewrite_values = (
            group["same_content_rewrite_count"].astype("Int64")
            if "same_content_rewrite_count" in group
            else pd.Series(0, index=group.index, dtype="Int64")
        )
        final.at[index, "first_read_mtime_ns"] = int(first_values.min())
        final.at[index, "last_read_mtime_ns"] = int(last_values.max())
        final.at[index, "same_content_rewrite_count"] = int(rewrite_values.sum())
        final.at[index, "post_read_same_content_rewrite"] = int(
            len(last_values.index) > 0 and int(row["mtime_ns"]) != int(last_values.max())
        )
        final.at[index, "worker_snapshot_count"] = int(len(group.index))
        final.at[index, "worker_anchor_count"] = int(
            group["requested_start_month"].astype(str).nunique()
        )
        final.at[index, "worker_distinct_mtime_count"] = int(
            group["mtime_ns"].astype("Int64").nunique()
        )
    final = _coerce_source_manifest_integer_columns(final)
    for column in (
        "worker_snapshot_count",
        "worker_anchor_count",
        "worker_distinct_mtime_count",
    ):
        final[column] = pd.array(final[column], dtype="Int64")
    return final


def write_failure_diagnostic(
    mode: str,
    error: Exception,
    *,
    failure_dir: Path = FAILURE_DIR,
    requested_start_month: str = "",
    phase: str = "",
) -> Path:
    """Atomically persist fail-close evidence outside the complete output directory."""
    failure_dir = Path(failure_dir).expanduser().resolve()
    failure_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now().astimezone()
    current_ai_snapshot: dict[str, Any] | None = None
    try:
        current_ai_snapshot = _file_snapshot(CURRENT_AI_PATH)
    except ValueError:
        current_ai_snapshot = None
    payload = {
        "generated_at": now.isoformat(timespec="microseconds"),
        "mode": str(mode),
        "requested_start_month": str(requested_start_month),
        "phase": str(phase),
        "error_type": error.__class__.__name__,
        "error_message": str(error),
        "current_ai_snapshot": current_ai_snapshot,
        "performance_metrics_run": False,
        "stage137_output_written": False,
        "official_live_or_ctp_touched": False,
    }
    filename = f"{now.strftime('%Y%m%d_%H%M%S_%f')}_{os.getpid()}_{mode}_failclose.json"
    destination = failure_dir / filename
    temporary = destination.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    os.replace(temporary, destination)
    return destination


_PERSISTED_FRAME_FILES = {
    "base_daily": "base_daily.csv",
    "selected_lifecycle": "selected_lifecycle.csv",
    "pit_source_ledger": "pit_source_ledger.csv",
    "pit_candidate_audit": "pit_candidate_audit.csv",
    "actual_open_audit": "actual_open_audit.csv",
    "pit_binding_audit": "pit_binding_audit.csv",
    "candidate_orders": "candidate_orders.csv",
    "replayed_orders": "replayed_orders.csv",
    "satellite_daily": "satellite_daily.csv",
    "price_audit": "price_audit.csv",
    "summary": "summary.csv",
    "input_audit": "input_audit.csv",
    "reconciliation": "reconciliation.csv",
    "fifo_audit": "fifo_audit.csv",
    "margin_audit": "margin_audit.csv",
    "current_ai_audit": "current_ai_audit.csv",
    "repeat_identity_audit": "repeat_identity_audit.csv",
    "repeat_source_manifest": "repeat_source_manifest.csv",
    "source_manifest": "source_manifest.csv",
}


def chart_contract() -> dict[str, dict[str, Any]]:
    return {
        "equity.png": {
            "columns": ("account_equity", "satellite_equity", "combined_equity"),
            "title": "Absolute equity: full anchor paths through 2026-06-30",
            "requested_start_months": None,
            "calendar_date_filter": None,
        },
        "drawdown.png": {
            "columns": ("account_equity", "combined_equity"),
            "title": "Drawdown from 150,000 initial capital: full anchor paths",
            "requested_start_months": None,
            "calendar_date_filter": None,
        },
        "focus_2022.png": {
            "columns": ("account_equity", "combined_equity"),
            "title": "2022 start anchors: full paths through 2026-06-30",
            "requested_start_months": ("2022-01", "2022-07"),
            "calendar_date_filter": None,
        },
    }


def _write_charts(bundle: dict[str, Any], output_dir: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    daily = bundle["satellite_daily"].copy()
    if not daily.empty:
        daily["date"] = pd.to_datetime(daily["date"])
    for filename, contract in chart_contract().items():
        columns = contract["columns"]
        figure, axis = plt.subplots(figsize=(10, 5))
        plotted = False
        data = daily
        requested_starts = contract["requested_start_months"]
        if requested_starts is not None and not daily.empty:
            data = daily.loc[daily["requested_start_month"].astype(str).isin(requested_starts)]
        for start, group in data.groupby("requested_start_month") if not data.empty else []:
            for column in columns:
                if column not in group:
                    continue
                values = _drawdown_pct(group[column]) if filename == "drawdown.png" else group[column]
                axis.plot(group["date"], values, label=f"{start} {column}")
                plotted = True
        if plotted:
            axis.legend(fontsize=7, ncol=2)
        else:
            axis.text(0.5, 0.5, "No canary return data", ha="center", va="center")
        axis.set_title(contract["title"])
        axis.grid(alpha=0.25)
        figure.tight_layout()
        figure.savefig(output_dir / filename, dpi=140)
        plt.close(figure)


def _report_text(bundle: dict[str, Any]) -> str:
    audit = bundle["input_audit"]
    zero_rate_values = pd.to_numeric(
        audit.get("zero_rate_count", pd.Series(dtype=float)), errors="coerce"
    ).dropna()
    zero_rate = int(zero_rate_values.max()) if len(zero_rate_values.index) else 0
    decision = bundle["decision"]
    summary = bundle["summary"]
    summary_csv = summary.to_csv(index=False).strip() if not summary.empty else "canary metrics not run"
    return "\n".join(
        [
            "# Stage137 当前 C9 质量单向卫星",
            "",
            f"- 模式：`{decision.get('mode', '')}`",
            f"- Canary：`{'PASS' if decision.get('canary_pass') else 'FAIL/NOT RUN'}`",
            f"- 失败闸门：`{', '.join(decision.get('failed_checks', [])) or '无'}`",
            f"- metadata 显式零 rate 合约计数：`{zero_rate}`",
            "- 成本限制：正式 metadata 当前 rate 可显式为 0；本报告不声称覆盖了非零手续费。",
            "- 磁盘约束：未持久化全量 positions、minute bars、entry-risk 或 entry-candidates；manifest 仅哈希静态 producer 与本次实际访问文件，不复制或扫描整个目录。",
            "",
            "## A/B/C 完整指标",
            "",
            "```csv",
            summary_csv,
            "```",
            "",
        ]
    )


def validate_identity_output_evidence(bundle: dict[str, Any]) -> None:
    """Require complete four-anchor identity evidence before atomic publication."""
    input_audit = bundle["input_audit"]
    identity_columns = {
        "requested_start_month",
        "current_ai_snapshot_pass",
        "current_ai_golden_membership_pass",
        "current_ai_golden_curve_applicable",
        "current_ai_golden_curve_pass",
        "current_c9_repeat_identity_pass",
        "repeat_source_manifest_pass",
        "repeat_worker_environment_pass",
    }
    _require_columns(input_audit, identity_columns)
    if (
        input_audit["requested_start_month"].astype(str).duplicated().any()
        or set(input_audit["requested_start_month"].astype(str)) != set(CANARY_STARTS)
    ):
        raise ValueError("identity output requires exactly four input-audit starts")
    indexed_input = input_audit.set_index(
        input_audit["requested_start_month"].astype(str)
    ).loc[list(CANARY_STARTS)]
    identity_failures: list[str] = []
    _append_current_identity_failures(indexed_input, identity_failures)
    if identity_failures:
        raise ValueError(f"identity input audit failed: {identity_failures}")

    current_ai = bundle["current_ai_audit"]
    current_columns = {
        "requested_start_month",
        "current_ai_snapshot_pass",
        "current_ai_snapshot_sha256",
        "current_ai_snapshot_row_count",
        "current_ai_snapshot_eval_date_count",
        "current_ai_golden_membership_pass",
        "current_ai_golden_curve_applicable",
        "current_ai_golden_curve_pass",
        "repeat_worker_environment_pass",
        "repeat_worker_environment_sha256",
    }
    try:
        _require_columns(current_ai, current_columns)
    except ValueError as error:
        raise ValueError(f"current AI audit incomplete: {error}") from None
    if (
        current_ai.empty
        or current_ai["requested_start_month"].astype(str).duplicated().any()
        or set(current_ai["requested_start_month"].astype(str)) != set(CANARY_STARTS)
    ):
        raise ValueError("current AI audit requires exactly four unique starts")
    current = current_ai.set_index(current_ai["requested_start_month"].astype(str)).loc[
        list(CANARY_STARTS)
    ]
    for field in (
        "current_ai_snapshot_pass",
        "current_ai_golden_membership_pass",
        "current_ai_golden_curve_pass",
        "repeat_worker_environment_pass",
    ):
        if not pd.to_numeric(current[field], errors="coerce").eq(1).all():
            raise ValueError(f"current AI audit failed: {field}")
    expected_scope = pd.Series(
        [int(start == "2020-01") for start in CANARY_STARTS],
        index=list(CANARY_STARTS),
    )
    if not pd.to_numeric(
        current["current_ai_golden_curve_applicable"], errors="coerce"
    ).astype("int64").eq(expected_scope).all():
        raise ValueError("current AI golden curve scope incomplete")
    if not current["current_ai_snapshot_sha256"].astype(str).eq(
        CURRENT_AI_EXPECTED_SHA256
    ).all():
        raise ValueError("current AI audit SHA256 drift")
    if not pd.to_numeric(current["current_ai_snapshot_row_count"], errors="coerce").eq(
        CURRENT_AI_EXPECTED_ROWS
    ).all():
        raise ValueError("current AI audit row count drift")
    if not pd.to_numeric(
        current["current_ai_snapshot_eval_date_count"], errors="coerce"
    ).eq(len(CURRENT_AI_EXPECTED_EVAL_DATES)).all():
        raise ValueError("current AI audit eval-date count drift")
    environment_hashes = current["repeat_worker_environment_sha256"].astype(str)
    if (
        not environment_hashes.str.fullmatch(r"[0-9a-f]{64}").all()
        or environment_hashes.nunique() != 1
    ):
        raise ValueError("repeat worker environment SHA256 drift")

    repeat_identity = bundle["repeat_identity_audit"]
    repeat_identity_columns = {
        "requested_start_month",
        "frame_name",
        "first_row_count",
        "second_row_count",
        "first_column_count",
        "second_column_count",
        "first_schema_sha256",
        "second_schema_sha256",
        "first_content_sha256",
        "second_content_sha256",
        "identity_match",
    }
    try:
        _require_columns(repeat_identity, repeat_identity_columns)
    except ValueError as error:
        raise ValueError(f"repeat identity audit incomplete: {error}") from None
    if repeat_identity.empty or repeat_identity.duplicated(
        ["requested_start_month", "frame_name"]
    ).any():
        raise ValueError("repeat identity audit empty or duplicate")
    expected_pairs = {
        (start, frame_name)
        for start in CANARY_STARTS
        for frame_name in _REPEAT_ARTIFACT_KEYS
    }
    actual_pairs = set(
        map(
            tuple,
            repeat_identity[["requested_start_month", "frame_name"]]
            .astype(str)
            .to_numpy(),
        )
    )
    if actual_pairs != expected_pairs:
        raise ValueError("repeat identity audit four-anchor frame coverage incomplete")
    if not pd.to_numeric(repeat_identity["identity_match"], errors="coerce").eq(1).all():
        raise ValueError("repeat identity audit contains mismatch")
    for first_field, second_field in (
        ("first_row_count", "second_row_count"),
        ("first_column_count", "second_column_count"),
    ):
        first_values = pd.to_numeric(repeat_identity[first_field], errors="coerce")
        second_values = pd.to_numeric(repeat_identity[second_field], errors="coerce")
        if (
            not np.isfinite(first_values).all()
            or not np.isfinite(second_values).all()
            or first_values.lt(0).any()
            or second_values.lt(0).any()
            or not first_values.eq(np.floor(first_values)).all()
            or not second_values.eq(np.floor(second_values)).all()
            or not first_values.eq(second_values).all()
        ):
            raise ValueError("repeat identity audit count mismatch")
    for first_field, second_field in (
        ("first_schema_sha256", "second_schema_sha256"),
        ("first_content_sha256", "second_content_sha256"),
    ):
        first_hashes = repeat_identity[first_field].astype(str)
        second_hashes = repeat_identity[second_field].astype(str)
        if (
            not first_hashes.str.fullmatch(r"[0-9a-f]{64}").all()
            or not second_hashes.str.fullmatch(r"[0-9a-f]{64}").all()
            or not first_hashes.eq(second_hashes).all()
        ):
            raise ValueError("repeat identity audit hash mismatch")

    repeat_source = bundle["repeat_source_manifest"]
    _require_columns(
        repeat_source,
        {
            "requested_start_month",
            "path",
            "size",
            "sha256",
            "content_identity_match",
        },
    )
    if (
        repeat_source.empty
        or repeat_source.duplicated(["requested_start_month", "path"]).any()
        or set(repeat_source["requested_start_month"].astype(str)) != set(CANARY_STARTS)
    ):
        raise ValueError("repeat source manifest four-anchor coverage incomplete")
    if repeat_source["path"].isna().any() or repeat_source["path"].astype(str).str.strip().eq("").any():
        raise ValueError("repeat source manifest missing path")
    if not pd.to_numeric(
        repeat_source["content_identity_match"], errors="coerce"
    ).eq(1).all():
        raise ValueError("repeat source manifest contains content drift")
    repeat_sizes = pd.to_numeric(repeat_source["size"], errors="coerce")
    if (
        not np.isfinite(repeat_sizes).all()
        or repeat_sizes.lt(0).any()
        or not repeat_sizes.eq(np.floor(repeat_sizes)).all()
    ):
        raise ValueError("repeat source manifest invalid size")
    if not repeat_source["sha256"].astype(str).str.fullmatch(r"[0-9a-f]{64}").all():
        raise ValueError("repeat source manifest invalid SHA256")

    source_manifest = bundle["source_manifest"]
    _require_columns(source_manifest, {"path", "size", "mtime_ns", "sha256"})
    if (
        source_manifest.empty
        or source_manifest["path"].isna().any()
        or source_manifest["path"].astype(str).str.strip().eq("").any()
        or source_manifest["path"].astype(str).duplicated().any()
    ):
        raise ValueError("final source manifest empty or invalid")
    if not source_manifest["sha256"].astype(str).str.fullmatch(r"[0-9a-f]{64}").all():
        raise ValueError("final source manifest invalid SHA256")
    final_sizes = pd.to_numeric(source_manifest["size"], errors="coerce")
    final_mtimes = pd.to_numeric(source_manifest["mtime_ns"], errors="coerce")
    if (
        not np.isfinite(final_sizes).all()
        or not np.isfinite(final_mtimes).all()
        or final_sizes.lt(0).any()
        or final_mtimes.le(0).any()
        or not final_sizes.eq(np.floor(final_sizes)).all()
        or not final_mtimes.eq(np.floor(final_mtimes)).all()
    ):
        raise ValueError("final source manifest invalid numeric identity")
    final_by_path = source_manifest.set_index(source_manifest["path"].astype(str))
    final_paths = set(final_by_path.index)
    grouped_repeat = repeat_source.groupby("path", sort=False)
    for path, rows in grouped_repeat:
        if (
            pd.to_numeric(rows["size"], errors="raise").nunique(dropna=False) != 1
            or rows["sha256"].astype(str).nunique() != 1
        ):
            raise ValueError(f"cross-anchor source manifest drift: {path}")
    repeat_paths_union: set[str] = set()
    for start in CANARY_STARTS:
        rows = repeat_source.loc[
            repeat_source["requested_start_month"].astype(str).eq(start)
        ]
        repeat_paths = set(rows["path"].astype(str))
        repeat_paths_union.update(repeat_paths)
        if not repeat_paths.issubset(final_paths):
            raise ValueError(
                "repeat source manifest path coverage: anchor is not a final source subset"
            )
        for row in rows.itertuples(index=False):
            final_row = final_by_path.loc[str(row.path)]
            if (
                int(row.size) != int(final_row["size"])
                or str(row.sha256) != str(final_row["sha256"])
            ):
                raise ValueError("repeat source manifest identity differs from final source manifest")
    if repeat_paths_union != final_paths:
        raise ValueError(
            "repeat source manifest path coverage: path union differs from final source manifest"
        )
    current_path = str(CURRENT_AI_PATH.resolve())
    current_rows = source_manifest.loc[
        source_manifest["path"].astype(str).eq(current_path)
    ]
    if len(current_rows.index) != 1 or str(current_rows.iloc[0]["sha256"]) != CURRENT_AI_EXPECTED_SHA256:
        raise ValueError("final source manifest missing fixed current AI")
    assert_source_manifest_matches_bytes(source_manifest)


def assert_source_manifest_matches_bytes(source_manifest: pd.DataFrame) -> None:
    """Rehash final bytes and retain mtime-only rewrites as lineage evidence."""
    _require_columns(source_manifest, {"path", "size", "mtime_ns", "sha256"})
    if "last_validated_mtime_ns" not in source_manifest.columns:
        source_manifest["last_validated_mtime_ns"] = pd.Series(
            [pd.NA] * len(source_manifest.index),
            index=source_manifest.index,
            dtype="Int64",
        )
    if "post_finalization_mtime_only_rewrite" not in source_manifest.columns:
        source_manifest["post_finalization_mtime_only_rewrite"] = 0
    for index, row in source_manifest.iterrows():
        try:
            current = _file_snapshot(Path(str(row["path"])))
        except ValueError as error:
            raise ValueError(f"final source manifest byte drift: {error}") from None
        if (
            int(row["size"]) != int(current["size"])
            or str(row["sha256"]) != str(current["sha256"])
        ):
            raise ValueError(f"final source manifest byte drift: {row['path']}")
        previous_rewrite = pd.to_numeric(
            pd.Series([row.get("post_finalization_mtime_only_rewrite", 0)]),
            errors="coerce",
        ).fillna(0).iloc[0]
        mtime_only_rewrite = int(
            int(row["mtime_ns"]) != int(current["mtime_ns"])
        )
        source_manifest.at[index, "last_validated_mtime_ns"] = int(
            current["mtime_ns"]
        )
        source_manifest.at[index, "post_finalization_mtime_only_rewrite"] = max(
            int(previous_rewrite),
            mtime_only_rewrite,
        )


def static_audit_empty_performance_schemas(
    bundle: dict[str, Any],
) -> dict[str, list[str]]:
    """Return the exact ordered schemas implied by audited base artifacts."""
    for key in ("base_daily", "candidate_orders"):
        if key not in bundle or not isinstance(bundle[key], pd.DataFrame):
            raise ValueError(f"static audit missing frame: {key}")
    daily_columns = list(bundle["base_daily"].columns)
    daily_columns.extend(
        column
        for column in _SATELLITE_DAILY_ADDITIONAL_COLUMNS
        if column not in daily_columns
    )
    replayed_columns = [
        column for column in bundle["candidate_orders"].columns if column != "trade_date"
    ]
    replayed_columns.extend(
        column
        for column in _REPLAYED_ORDER_ADDITIONAL_COLUMNS
        if column not in replayed_columns
    )
    return {
        "satellite_daily": daily_columns,
        "replayed_orders": replayed_columns,
    }


def attach_static_audit_empty_performance_schemas(bundle: dict[str, Any]) -> None:
    """Represent deliberately unrun replay outputs as readable zero-row tables."""
    for key in ("satellite_daily", "replayed_orders"):
        if key not in bundle or not isinstance(bundle[key], pd.DataFrame):
            raise ValueError(f"static audit missing frame: {key}")
        if not bundle[key].empty:
            raise ValueError("static audit performance frames must be empty")
    for key, columns in static_audit_empty_performance_schemas(bundle).items():
        bundle[key] = pd.DataFrame(columns=columns)


def validate_output_bundle_evidence(bundle: dict[str, Any]) -> None:
    """Revalidate every publication gate after rendering and before atomic swap."""
    missing = sorted(set(_PERSISTED_FRAME_FILES).difference(bundle))
    if missing or "decision" not in bundle:
        raise ValueError(f"missing output bundle keys: {', '.join(missing)}")
    input_audit = bundle["input_audit"]
    mode = str(bundle["decision"].get("mode", ""))
    if mode not in {"audit", "canary"}:
        raise ValueError("output decision mode must be audit or canary")
    if mode == "audit":
        expected_schemas = static_audit_empty_performance_schemas(bundle)
        for key, expected_columns in expected_schemas.items():
            frame = bundle[key]
            if not isinstance(frame, pd.DataFrame) or not frame.empty:
                raise ValueError(f"static audit {key} must be a zero-row frame")
            if list(frame.columns) != expected_columns:
                raise ValueError(f"static audit {key} schema mismatch")
    coverage_columns = {
        "input_audit_pass",
        "eligible_open_count",
        "mapped_eligible_open_count",
        "selected_open_count",
        "missing_selected_open_count",
        "unexpected_selected_open_count",
        "unmapped_actual_open_count",
        "future_match_count",
        "source_order_mismatch_count",
        "positive_volume_drift_count",
        "opened_candidate_without_risk_count",
        "risk_input_count",
        "pit_source_ledger_row_count",
        "candidate_input_count",
        "pit_candidate_audit_row_count",
        "opened_candidate_count",
        "skipped_candidate_count",
        "actual_open_input_count",
        "actual_open_audit_row_count",
        "open_at_end_count",
        "expected_terminal_position_count",
    }
    if mode == "canary":
        coverage_columns.update(
            {
                "unexpected_terminal_position_count",
                "max_terminal_position_reconciliation_error",
                "max_terminal_margin_reconciliation_error",
                "max_terminal_pnl_reconciliation_error",
            }
        )
    try:
        _require_columns(input_audit, coverage_columns)
    except ValueError as error:
        raise ValueError(f"coverage audit incomplete: {error}") from None
    if input_audit.empty or not pd.to_numeric(
        input_audit["input_audit_pass"], errors="coerce"
    ).eq(1).all():
        raise ValueError("input audit must pass before writing outputs")
    if (
        pd.to_numeric(input_audit["missing_selected_open_count"], errors="coerce").ne(0).any()
        or pd.to_numeric(input_audit["unexpected_selected_open_count"], errors="coerce").ne(0).any()
        or pd.to_numeric(input_audit["unmapped_actual_open_count"], errors="coerce").ne(0).any()
        or pd.to_numeric(input_audit["future_match_count"], errors="coerce").ne(0).any()
        or pd.to_numeric(input_audit["source_order_mismatch_count"], errors="coerce").ne(0).any()
        or pd.to_numeric(input_audit["positive_volume_drift_count"], errors="coerce").ne(0).any()
        or pd.to_numeric(input_audit["opened_candidate_without_risk_count"], errors="coerce").ne(0).any()
        or not pd.to_numeric(input_audit["risk_input_count"], errors="coerce").eq(
            pd.to_numeric(input_audit["pit_source_ledger_row_count"], errors="coerce")
        ).all()
        or not pd.to_numeric(input_audit["candidate_input_count"], errors="coerce").eq(
            pd.to_numeric(input_audit["pit_candidate_audit_row_count"], errors="coerce")
        ).all()
        or not pd.to_numeric(input_audit["candidate_input_count"], errors="coerce").eq(
            pd.to_numeric(input_audit["opened_candidate_count"], errors="coerce")
            + pd.to_numeric(input_audit["skipped_candidate_count"], errors="coerce")
        ).all()
        or not pd.to_numeric(input_audit["actual_open_input_count"], errors="coerce").eq(
            pd.to_numeric(input_audit["actual_open_audit_row_count"], errors="coerce")
        ).all()
        or not pd.to_numeric(input_audit["eligible_open_count"], errors="coerce").eq(
            pd.to_numeric(input_audit["mapped_eligible_open_count"], errors="coerce")
        ).all()
        or not pd.to_numeric(input_audit["eligible_open_count"], errors="coerce").eq(
            pd.to_numeric(input_audit["selected_open_count"], errors="coerce")
        ).all()
    ):
        raise ValueError("coverage audit must pass before writing outputs")
    if mode == "canary" and (
        pd.to_numeric(
            input_audit["max_terminal_position_reconciliation_error"], errors="coerce"
        ).gt(IDENTITY_TOLERANCE).any()
        or pd.to_numeric(
            input_audit["max_terminal_margin_reconciliation_error"], errors="coerce"
        ).gt(IDENTITY_TOLERANCE).any()
        or pd.to_numeric(
            input_audit["max_terminal_pnl_reconciliation_error"], errors="coerce"
        ).gt(IDENTITY_TOLERANCE).any()
    ):
        raise ValueError("canary terminal reconciliation must pass before writing outputs")
    forbidden = {"positions", "minute_bars", "entry_risk", "entry_candidates"}
    if forbidden.intersection(bundle):
        raise ValueError("forbidden bulk frame in output bundle")
    validate_identity_output_evidence(bundle)


def _dataframe_csv_bytes(frame: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    frame.to_csv(buffer, index=False, encoding="utf-8-sig")
    return buffer.getvalue()


def staged_output_evidence_payloads(bundle: dict[str, Any]) -> dict[str, bytes]:
    """Serialize every non-chart artifact that must survive rendering unchanged."""
    payloads = {
        filename: _dataframe_csv_bytes(bundle[key])
        for key, filename in _PERSISTED_FRAME_FILES.items()
    }
    payloads["decision.json"] = json.dumps(
        bundle["decision"],
        ensure_ascii=False,
        indent=2,
        allow_nan=False,
    ).encode("utf-8")
    payloads["report.md"] = _report_text(bundle).encode("utf-8")
    return payloads


def _write_staged_output_evidence(
    output_dir: Path,
    payloads: dict[str, bytes],
) -> None:
    for filename, payload in payloads.items():
        (Path(output_dir) / filename).write_bytes(payload)


def assert_staged_output_evidence_unchanged(
    bundle: dict[str, Any],
    output_dir: Path,
    expected_payloads: dict[str, bytes],
) -> None:
    """Bind both memory and staged bytes before an atomic directory swap."""
    current_payloads = staged_output_evidence_payloads(bundle)
    if set(current_payloads) != set(expected_payloads):
        raise ValueError("staged output evidence drift: artifact set")
    drifted: list[str] = []
    for filename, expected in expected_payloads.items():
        path = Path(output_dir) / filename
        if path.is_symlink() or not path.is_file():
            drifted.append(filename)
            continue
        try:
            staged = path.read_bytes()
        except OSError:
            drifted.append(filename)
            continue
        if current_payloads[filename] != expected or staged != expected:
            drifted.append(filename)
    if drifted:
        raise ValueError(f"staged output evidence drift: {sorted(drifted)}")


def write_stage_outputs(bundle: dict[str, Any], output_dir: Path = OUTPUT_DIR) -> None:
    """Atomically persist only the audited minimal Stage137 output contract."""
    missing = sorted(set(_PERSISTED_FRAME_FILES).difference(bundle))
    if missing or "decision" not in bundle:
        raise ValueError(f"missing output bundle keys: {', '.join(missing)}")
    input_audit = bundle["input_audit"]
    mode = str(bundle["decision"].get("mode", ""))
    if mode not in {"audit", "canary"}:
        raise ValueError("output decision mode must be audit or canary")
    if mode == "audit":
        attach_static_audit_empty_performance_schemas(bundle)
    coverage_columns = {
        "input_audit_pass",
        "eligible_open_count",
        "mapped_eligible_open_count",
        "selected_open_count",
        "missing_selected_open_count",
        "unexpected_selected_open_count",
        "unmapped_actual_open_count",
        "future_match_count",
        "source_order_mismatch_count",
        "positive_volume_drift_count",
        "opened_candidate_without_risk_count",
        "risk_input_count",
        "pit_source_ledger_row_count",
        "candidate_input_count",
        "pit_candidate_audit_row_count",
        "opened_candidate_count",
        "skipped_candidate_count",
        "actual_open_input_count",
        "actual_open_audit_row_count",
        "open_at_end_count",
        "expected_terminal_position_count",
    }
    if mode == "canary":
        coverage_columns.update(
            {
                "unexpected_terminal_position_count",
                "max_terminal_position_reconciliation_error",
                "max_terminal_margin_reconciliation_error",
                "max_terminal_pnl_reconciliation_error",
            }
        )
    try:
        _require_columns(input_audit, coverage_columns)
    except ValueError as error:
        raise ValueError(f"coverage audit incomplete: {error}") from None
    if input_audit.empty or not pd.to_numeric(input_audit["input_audit_pass"], errors="coerce").eq(1).all():
        raise ValueError("input audit must pass before writing outputs")
    if (
        pd.to_numeric(input_audit["missing_selected_open_count"], errors="coerce").ne(0).any()
        or pd.to_numeric(input_audit["unexpected_selected_open_count"], errors="coerce").ne(0).any()
        or pd.to_numeric(input_audit["unmapped_actual_open_count"], errors="coerce").ne(0).any()
        or pd.to_numeric(input_audit["future_match_count"], errors="coerce").ne(0).any()
        or pd.to_numeric(input_audit["source_order_mismatch_count"], errors="coerce").ne(0).any()
        or pd.to_numeric(input_audit["positive_volume_drift_count"], errors="coerce").ne(0).any()
        or pd.to_numeric(input_audit["opened_candidate_without_risk_count"], errors="coerce").ne(0).any()
        or not pd.to_numeric(input_audit["risk_input_count"], errors="coerce").eq(
            pd.to_numeric(input_audit["pit_source_ledger_row_count"], errors="coerce")
        ).all()
        or not pd.to_numeric(input_audit["candidate_input_count"], errors="coerce").eq(
            pd.to_numeric(input_audit["pit_candidate_audit_row_count"], errors="coerce")
        ).all()
        or not pd.to_numeric(input_audit["candidate_input_count"], errors="coerce").eq(
            pd.to_numeric(input_audit["opened_candidate_count"], errors="coerce")
            + pd.to_numeric(input_audit["skipped_candidate_count"], errors="coerce")
        ).all()
        or not pd.to_numeric(input_audit["actual_open_input_count"], errors="coerce").eq(
            pd.to_numeric(input_audit["actual_open_audit_row_count"], errors="coerce")
        ).all()
        or not pd.to_numeric(input_audit["eligible_open_count"], errors="coerce").eq(
            pd.to_numeric(input_audit["mapped_eligible_open_count"], errors="coerce")
        ).all()
        or not pd.to_numeric(input_audit["eligible_open_count"], errors="coerce").eq(
            pd.to_numeric(input_audit["selected_open_count"], errors="coerce")
        ).all()
    ):
        raise ValueError("coverage audit must pass before writing outputs")
    validate_identity_output_evidence(bundle)
    if mode == "canary" and (
        pd.to_numeric(
            input_audit["max_terminal_position_reconciliation_error"], errors="coerce"
        ).gt(IDENTITY_TOLERANCE).any()
        or pd.to_numeric(
            input_audit["max_terminal_margin_reconciliation_error"], errors="coerce"
        ).gt(IDENTITY_TOLERANCE).any()
        or pd.to_numeric(
            input_audit["max_terminal_pnl_reconciliation_error"], errors="coerce"
        ).gt(IDENTITY_TOLERANCE).any()
    ):
        raise ValueError("canary terminal reconciliation must pass before writing outputs")
    forbidden = {"positions", "minute_bars", "entry_risk", "entry_candidates"}
    if forbidden.intersection(bundle):
        raise ValueError("forbidden bulk frame in output bundle")

    output_dir = Path(output_dir)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.", dir=output_dir.parent))
    backup = temporary.with_name(f"{temporary.name}.backup")
    try:
        pre_render_payloads = staged_output_evidence_payloads(bundle)
        _write_staged_output_evidence(temporary, pre_render_payloads)
        _write_charts(bundle, temporary)
        assert_staged_output_evidence_unchanged(
            bundle,
            temporary,
            pre_render_payloads,
        )
        validate_output_bundle_evidence(bundle)
        final_payloads = staged_output_evidence_payloads(bundle)
        _write_staged_output_evidence(temporary, final_payloads)
        assert_staged_output_evidence_unchanged(
            bundle,
            temporary,
            final_payloads,
        )
        if output_dir.exists():
            os.replace(output_dir, backup)
        try:
            os.replace(temporary, output_dir)
        except Exception:
            if backup.exists():
                os.replace(backup, output_dir)
            raise
        if backup.exists():
            shutil.rmtree(backup)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        if backup.exists() and not output_dir.exists():
            os.replace(backup, output_dir)
        raise


def _fresh_input_audit(
    frames: dict[str, pd.DataFrame],
    candidate_orders: pd.DataFrame,
    binding_audit: pd.DataFrame,
    metadata_audit: dict[str, Any],
    identity_audit: dict[str, Any],
    coverage_audit: dict[str, Any],
) -> dict[str, Any]:
    base = frames["base_daily"]
    trades = frames["trades"]
    positions = frames["positions"]
    if base["date"].duplicated().any():
        raise ValueError("input audit duplicate base date")
    if not trades.empty:
        _require_columns(trades, {"trade_id", "datetime"})
        if trades["trade_id"].astype(str).duplicated().any():
            raise ValueError("input audit duplicate trade id")
        trades["datetime"].map(lambda value: _pit_timestamp(value, "trade datetime"))
    if not positions.empty and positions.duplicated(["date", "vt_symbol"]).any():
        raise ValueError("input audit duplicate price key")
    if not candidate_orders.empty and candidate_orders.duplicated(
        ["requested_start_month", "open_trade_id", "base_trade_id"]
    ).any():
        raise ValueError("input audit duplicate order key")
    if not candidate_orders.empty:
        candidate_orders["trade_datetime"].map(lambda value: _pit_timestamp(value, "order datetime"))
    pit_window_rows = frames.get("pit_window_audit", pd.DataFrame())
    if len(pit_window_rows.index) != 1:
        raise ValueError("input audit requires one PIT window audit row")
    pit_window_audit = pit_window_rows.iloc[0].to_dict()
    required_coverage = {
        "eligible_open_count",
        "mapped_eligible_open_count",
        "selected_open_count",
        "missing_selected_open_count",
        "unexpected_selected_open_count",
        "unmapped_actual_open_count",
        "future_match_count",
        "source_order_mismatch_count",
        "positive_volume_drift_count",
        "opened_candidate_without_risk_count",
        "risk_input_count",
        "pit_source_ledger_row_count",
        "candidate_input_count",
        "pit_candidate_audit_row_count",
        "actual_open_input_count",
        "actual_open_audit_row_count",
    }
    missing_coverage = sorted(required_coverage.difference(coverage_audit))
    if missing_coverage:
        raise ValueError(f"input audit missing coverage fields: {missing_coverage}")
    coverage_pass = (
        int(coverage_audit["missing_selected_open_count"]) == 0
        and int(coverage_audit["unexpected_selected_open_count"]) == 0
        and int(coverage_audit["unmapped_actual_open_count"]) == 0
        and int(coverage_audit["future_match_count"]) == 0
        and int(coverage_audit["source_order_mismatch_count"]) == 0
        and int(coverage_audit["positive_volume_drift_count"]) == 0
        and int(coverage_audit["opened_candidate_without_risk_count"]) == 0
        and int(coverage_audit["risk_input_count"])
        == int(coverage_audit["pit_source_ledger_row_count"])
        and int(coverage_audit["candidate_input_count"])
        == int(coverage_audit["pit_candidate_audit_row_count"])
        and int(coverage_audit["actual_open_input_count"])
        == int(coverage_audit["actual_open_audit_row_count"])
        and int(coverage_audit["eligible_open_count"])
        == int(coverage_audit["mapped_eligible_open_count"])
        and int(coverage_audit["eligible_open_count"])
        == int(coverage_audit["selected_open_count"])
    )
    if not coverage_pass:
        raise ValueError("input audit coverage failed")
    return {
        "requested_start_month": str(base["requested_start_month"].iloc[0]),
        "cost_multiplier": 1.0,
        "input_audit_pass": 1,
        "base_date_duplicate_count": 0,
        "trade_id_duplicate_count": 0,
        "trade_datetime_timezone_invalid_count": 0,
        "price_key_duplicate_count": 0,
        "order_key_duplicate_count": 0,
        "order_datetime_timezone_invalid_count": 0,
        "pit_binding_fail_count": 0,
        "future_match_count": int(coverage_audit["future_match_count"]),
        "duplicate_satellite_open_count": int(candidate_orders.loc[candidate_orders["base_trade_id"].eq(candidate_orders["open_trade_id"]), "open_trade_id"].duplicated().sum()) if not candidate_orders.empty else 0,
        "fallback_count": 0,
        "silent_default_count": 0,
        **{
            key: value
            for key, value in pit_window_audit.items()
            if key != "requested_start_month"
        },
        **coverage_audit,
        **metadata_audit,
        **identity_audit,
    }


def _minimal_price_audit(
    positions: pd.DataFrame,
    candidate_orders: pd.DataFrame,
    *,
    base_dates: pd.Series | None = None,
    expected_terminal_positions: dict[str, int] | None = None,
) -> pd.DataFrame:
    columns = ["requested_start_month", "date", "vt_symbol", "pre_close", "close_price"]
    if candidate_orders.empty:
        return pd.DataFrame(columns=columns)
    _require_columns(candidate_orders, {"requested_start_month"})
    requested_starts = candidate_orders["requested_start_month"].astype(str).drop_duplicates()
    if len(requested_starts.index) != 1:
        raise ValueError("price audit requires one requested start")
    requested_start_month = str(requested_starts.iloc[0])
    if not _REQUESTED_START_MONTH_PATTERN.fullmatch(requested_start_month):
        raise ValueError("price audit invalid requested start")
    price_columns = ["date", "vt_symbol", "pre_close", "close_price"]
    _require_columns(positions, set(price_columns))
    required_keys: set[tuple[pd.Timestamp, str]] = set()
    normalized_base_dates = sorted(
        set(pd.to_datetime(base_dates).map(pd.Timestamp).map(lambda value: value.normalize()))
    ) if base_dates is not None else sorted(
        set(pd.to_datetime(positions["date"]).map(pd.Timestamp).map(lambda value: value.normalize()))
    )
    terminal_targets = expected_terminal_positions or {}
    for (_requested, open_id), lifecycle in candidate_orders.groupby(
        ["requested_start_month", "open_trade_id"], sort=False
    ):
        datetimes = lifecycle["trade_datetime"].map(_parse_timezone_aware_datetime)
        start = _local_trade_date(datetimes.min())
        if terminal_targets.get(str(open_id), 0):
            if not normalized_base_dates:
                raise ValueError(f"missing base dates for terminal price audit: {open_id}")
            end = normalized_base_dates[-1]
        else:
            end = _local_trade_date(datetimes.max())
        contract = str(lifecycle["vt_symbol"].iloc[0])
        for date in normalized_base_dates:
            if start <= date <= end:
                required_keys.add((date, contract))
    normalized_positions = positions.copy()
    normalized_positions["date"] = pd.to_datetime(normalized_positions["date"]).map(pd.Timestamp).map(lambda value: value.normalize())
    if normalized_positions.duplicated(["date", "vt_symbol"]).any():
        raise ValueError("input audit duplicate price key")
    actual_keys = {
        (row.date, str(row.vt_symbol))
        for row in normalized_positions[["date", "vt_symbol"]].itertuples(index=False)
    }
    missing_keys = sorted(required_keys - actual_keys, key=lambda item: (item[0], item[1]))
    if missing_keys:
        formatted = [f"{date.date()}:{contract}" for date, contract in missing_keys]
        raise ValueError(f"missing required price keys: {formatted}")
    mask = [
        (row.date, str(row.vt_symbol)) in required_keys
        for row in normalized_positions[["date", "vt_symbol"]].itertuples(index=False)
    ]
    prices = normalized_positions.loc[mask, price_columns].copy()
    for column in ("pre_close", "close_price"):
        values = pd.to_numeric(prices[column], errors="coerce")
        if not np.isfinite(values).all() or values.le(0.0).any():
            raise ValueError(f"positive finite price required: {column}")
    prices.insert(0, "requested_start_month", requested_start_month)
    return prices.sort_values(
        ["requested_start_month", "date", "vt_symbol"], kind="stable"
    ).reset_index(drop=True)


def prepare_anchor_artifacts(
    frames: dict[str, pd.DataFrame],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    """Build every static Stage137 artifact from one isolated current-C9 payload."""
    base = frames.get("base_daily", pd.DataFrame())
    if base.empty:
        raise ValueError("prepare anchor artifacts requires base daily")
    _require_columns(base, {"requested_start_month", "date"})
    start_values = base["requested_start_month"].astype(str).drop_duplicates().tolist()
    if len(start_values) != 1:
        raise ValueError("prepare anchor artifacts requires one requested start")
    requested_start_month = start_values[0]
    (
        selected,
        binding_audit,
        pit_source_ledger,
        pit_candidate_audit,
        actual_open_audit,
        coverage_audit,
    ) = build_entry_time_open_groups(
        frames["trades"],
        frames["entry_risk"],
        frames["entry_candidates"],
        frames["closed_lots"],
        base_dates=base["date"],
        requested_start_month=requested_start_month,
        analysis_end=ANALYSIS_END,
    )
    bindings = {
        str(row["open_trade_id"]): row for row in binding_audit.to_dict("records")
    }
    orders, fifo_audit = allocate_floor_mirror_orders(selected, frames["trades"])
    expected_terminal_positions = dict(fifo_audit["expected_terminal_positions"])
    if int(fifo_audit["expected_terminal_position_count"]) != int(
        coverage_audit["expected_terminal_position_count"]
    ):
        raise ValueError("terminal coverage and FIFO counts disagree")
    fifo_public = {
        key: value
        for key, value in fifo_audit.items()
        if key != "expected_terminal_positions"
    }
    static_fifo_public = {
        key: value
        for key, value in fifo_public.items()
        if key
        not in {
            "unexpected_terminal_position_count",
            "max_terminal_position_reconciliation_error",
            "max_terminal_margin_reconciliation_error",
            "max_terminal_pnl_reconciliation_error",
        }
    }
    orders = attach_pit_margin_to_orders(orders, bindings)
    contracts = set(orders["vt_symbol"].astype(str))
    specs, metadata_audit = build_contract_specs(metadata, contracts)
    price_audit = _minimal_price_audit(
        frames["positions"],
        orders,
        base_dates=base["date"],
        expected_terminal_positions=expected_terminal_positions,
    )
    contract_specs = pd.DataFrame(
        [
            {"vt_symbol": contract, **values}
            for contract, values in sorted(specs.items())
        ],
        columns=["vt_symbol", *_LEDGER_SPEC_FIELDS],
    )
    artifact_frames = {
        "base_daily": frames["base_daily"],
        "positions": frames["positions"],
        "trades": frames["trades"],
        "entry_risk": frames["entry_risk"],
        "entry_candidates": frames["entry_candidates"],
        "closed_lots": frames["closed_lots"],
        "pit_source_ledger": pit_source_ledger,
        "pit_candidate_audit": pit_candidate_audit,
        "actual_open_audit": actual_open_audit,
        "pit_binding_audit": binding_audit,
        "selected_lifecycle": selected,
        "candidate_orders": orders,
        "price_audit": price_audit,
        "contract_specs": contract_specs,
    }
    return {
        "requested_start_month": requested_start_month,
        "artifact_frames": artifact_frames,
        "selected_lifecycle": selected,
        "pit_source_ledger": pit_source_ledger,
        "pit_candidate_audit": pit_candidate_audit,
        "actual_open_audit": actual_open_audit,
        "pit_binding_audit": binding_audit,
        "candidate_orders": orders,
        "price_audit": price_audit,
        "bindings": bindings,
        "expected_terminal_positions": expected_terminal_positions,
        "fifo_public": fifo_public,
        "static_fifo_public": static_fifo_public,
        "specs": specs,
        "metadata_audit": metadata_audit,
        "coverage_audit": coverage_audit,
    }


def nonapplicable_current_ai_golden_curve_audit() -> dict[str, Any]:
    return {
        "current_ai_golden_curve_applicable": 0,
        "current_ai_golden_curve_pass": 1,
        "current_ai_golden_curve_date_drift_count": 0,
        "current_ai_golden_curve_compared_date_count": 0,
        "current_ai_golden_curve_max_account_equity_error": 0.0,
        "current_ai_golden_curve_max_net_pnl_error": 0.0,
        "current_ai_golden_curve_max_total_margin_exact_error": 0.0,
    }


def _margin_audit_frame(
    requested_start_month: str,
    candidate_orders: pd.DataFrame,
    replayed_orders: pd.DataFrame | None = None,
    daily: pd.DataFrame | None = None,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    order_source = replayed_orders if replayed_orders is not None and not replayed_orders.empty else candidate_orders
    if not order_source.empty:
        for row in order_source.loc[order_source["base_trade_id"].eq(order_source["open_trade_id"])].to_dict("records"):
            rows.append({
                "requested_start_month": requested_start_month,
                "audit_type": "open_event",
                "date": _local_trade_date(_parse_timezone_aware_datetime(row["trade_datetime"])),
                "open_trade_id": row["open_trade_id"],
                "vt_symbol": row["vt_symbol"],
                "c9_projected_total_margin_after": row.get("c9_projected_total_margin_after"),
                "estimated_equity": row.get("estimated_equity"),
                "satellite_margin_after_proposed": row.get("satellite_margin_after_proposed"),
                "proposed_broker10_pct": row.get("proposed_broker10_pct"),
                "aggregate_broker10_to_prior_combined_equity_pct": np.nan,
                "aggregate_broker10_to_current_combined_equity_pct": np.nan,
            })
    if daily is not None and not daily.empty:
        for row in daily.to_dict("records"):
            rows.append({
                "requested_start_month": requested_start_month,
                "audit_type": "eod",
                "date": row["date"],
                "open_trade_id": "",
                "vt_symbol": "",
                "c9_projected_total_margin_after": np.nan,
                "estimated_equity": np.nan,
                "satellite_margin_after_proposed": np.nan,
                "proposed_broker10_pct": np.nan,
                "aggregate_broker10_to_prior_combined_equity_pct": row["aggregate_broker10_to_prior_combined_equity_pct"],
                "aggregate_broker10_to_current_combined_equity_pct": row["aggregate_broker10_to_current_combined_equity_pct"],
            })
    return pd.DataFrame(rows)


def build_reconciliation_row(
    requested_start_month: str,
    cost_multiplier: float,
    audit: dict[str, Any],
) -> dict[str, Any]:
    fields = (
        "max_reconciliation_error",
        "max_terminal_position_reconciliation_error",
        "max_terminal_margin_reconciliation_error",
        "max_terminal_pnl_reconciliation_error",
    )
    row: dict[str, Any] = {
        "requested_start_month": str(requested_start_month),
        "cost_multiplier": _require_finite_scalar(cost_multiplier, "reconciliation cost multiplier"),
    }
    for field in fields:
        if field not in audit:
            raise ValueError(f"missing reconciliation audit field: {field}")
        row[field] = _require_finite_scalar(audit[field], f"reconciliation {field}")
    return row


def _bankrupt_summary(
    base_daily: pd.DataFrame,
    requested_start_month: str,
    cost_multiplier: float,
    error: Exception,
) -> dict[str, Any]:
    _require_columns(base_daily, {"date", "account_equity", "slippage", "commission", "trade_count"})
    a_curve = pd.to_numeric(base_daily["account_equity"], errors="raise")
    result: dict[str, Any] = {
        "requested_start_month": requested_start_month,
        "cost_multiplier": float(cost_multiplier),
        "return_retention_pct": -1e300,
        "b_cumulative_net_pnl": -_LEDGER_CAPITAL,
        "b_bankrupt": int("satellite" in str(error)),
        "c_bankrupt": int("combined" in str(error)),
        "metrics_valid": 0,
        "a_final_equity": float(a_curve.iloc[-1]),
        "a_total_return_pct": float((a_curve.iloc[-1] / _LEDGER_CAPITAL - 1.0) * 100.0),
        "a_max_drawdown_pct": float(_drawdown_pct(a_curve).min()),
        "a_sharpe": _daily_sharpe(a_curve),
        "a_total_slippage": float(pd.to_numeric(base_daily["slippage"], errors="raise").sum()),
        "a_total_commission": float(pd.to_numeric(base_daily["commission"], errors="raise").sum()),
        "a_total_trade_count": int(pd.to_numeric(base_daily["trade_count"], errors="raise").sum()),
        "a_nonzero_daily_win_rate_pct": _nonzero_daily_win_rate_pct(a_curve),
        "a_longest_underwater_days": _longest_underwater_days(base_daily["date"], a_curve),
    }
    terminal_days = int((pd.to_datetime(base_daily["date"]).max() - pd.to_datetime(base_daily["date"]).min()).days)
    for prefix in ("b", "c"):
        result.update({
            f"{prefix}_final_equity": 0.0,
            f"{prefix}_total_return_pct": -100.0,
            f"{prefix}_max_drawdown_pct": -100.0,
            f"{prefix}_sharpe": 0.0,
            f"{prefix}_total_slippage": 0.0,
            f"{prefix}_total_commission": 0.0,
            f"{prefix}_total_trade_count": 0,
            f"{prefix}_nonzero_daily_win_rate_pct": 0.0,
            f"{prefix}_longest_underwater_days": terminal_days,
        })
    return result


def run_stage(mode: str) -> dict[str, Any]:
    """Execute audit or four-anchor 1x canary; full remains mechanically unavailable."""
    if mode not in {"audit", "canary"}:
        raise ValueError("full mode is closed by the Task3 gate")
    _FAILURE_CONTEXT.update({"requested_start_month": "", "phase": "startup"})
    OUTPUT_DIR.parent.mkdir(parents=True, exist_ok=True)
    collected: dict[str, list[pd.DataFrame]] = {key: [] for key in _PERSISTED_FRAME_FILES if key != "source_manifest"}
    summary_rows: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []
    worker_manifests: dict[str, list[pd.DataFrame]] = {}

    with tempfile.TemporaryDirectory(
        prefix=".stage137-current-c9-workers-", dir=OUTPUT_DIR.parent
    ) as worker_temp:
        worker_root = Path(worker_temp)
        for start_month in CANARY_STARTS:
            _FAILURE_CONTEXT.update(
                {"requested_start_month": start_month, "phase": "launch_repeat_workers"}
            )
            print(f"[stage137] isolated current-C9 identity start={start_month}", flush=True)
            pair = load_repeat_worker_pair(start_month, worker_root)
            first = pair["first"]
            second = pair["second"]
            _FAILURE_CONTEXT["phase"] = "prepare_repeat_artifacts"
            first_prepared = prepare_anchor_artifacts(first["frames"], first["metadata"])
            second_prepared = prepare_anchor_artifacts(second["frames"], second["metadata"])
            repeat_audit, repeat_ledger = compare_repeat_artifacts(
                first_prepared["artifact_frames"],
                second_prepared["artifact_frames"],
                start_month,
            )
            _FAILURE_CONTEXT["phase"] = "current_ai_golden_curve"
            if start_month == "2020-01":
                golden_daily = pd.read_csv(
                    CURRENT_AI_GOLDEN_DAILY_PATH, encoding="utf-8-sig"
                )
                golden_audit = assert_current_ai_golden_curve(
                    first["frames"]["base_daily"],
                    golden_daily,
                    requested_start_month=start_month,
                )
            else:
                golden_audit = nonapplicable_current_ai_golden_curve_audit()
            identity = {
                **first["ai_audit"],
                **first["membership_audit"],
                **golden_audit,
                **repeat_audit,
                **pair["manifest_audit"],
                "repeat_worker_environment_pass": 1,
            }
            environment_sha256 = hashlib.sha256(
                json.dumps(
                    first["environment"], sort_keys=True, separators=(",", ":")
                ).encode("utf-8")
            ).hexdigest()
            collected["current_ai_audit"].append(
                pd.DataFrame(
                    [{
                        "requested_start_month": start_month,
                        **first["ai_audit"],
                        **first["membership_audit"],
                        **golden_audit,
                        "repeat_worker_environment_pass": 1,
                        "repeat_worker_environment_sha256": environment_sha256,
                        **{
                            f"worker_environment_{key}": value
                            for key, value in sorted(first["environment"].items())
                        },
                    }]
                )
            )
            collected["repeat_identity_audit"].append(repeat_ledger)
            collected["repeat_source_manifest"].append(pair["manifest_ledger"])
            worker_manifests[start_month] = [
                first["source_manifest"],
                second["source_manifest"],
            ]

            frames = first["frames"]
            selected = first_prepared["selected_lifecycle"]
            pit_source_ledger = first_prepared["pit_source_ledger"]
            pit_candidate_audit = first_prepared["pit_candidate_audit"]
            actual_open_audit = first_prepared["actual_open_audit"]
            binding_audit = first_prepared["pit_binding_audit"]
            orders = first_prepared["candidate_orders"]
            price_audit = first_prepared["price_audit"]
            coverage_audit = first_prepared["coverage_audit"]
            metadata_audit = first_prepared["metadata_audit"]
            expected_terminal_positions = first_prepared["expected_terminal_positions"]
            fifo_public = first_prepared["fifo_public"]
            static_fifo_public = first_prepared["static_fifo_public"]
            specs = first_prepared["specs"]
            _FAILURE_CONTEXT["phase"] = "input_audit"
            input_audit = _fresh_input_audit(
                frames,
                orders,
                binding_audit,
                metadata_audit,
                identity,
                coverage_audit,
            )
            input_audit.update(static_fifo_public)
            collected["base_daily"].append(frames["base_daily"])
            collected["selected_lifecycle"].append(selected)
            collected["pit_source_ledger"].append(pit_source_ledger)
            collected["pit_candidate_audit"].append(pit_candidate_audit)
            collected["actual_open_audit"].append(actual_open_audit)
            collected["pit_binding_audit"].append(binding_audit)
            collected["candidate_orders"].append(orders)
            collected["price_audit"].append(price_audit)
            collected["fifo_audit"].append(pd.DataFrame([{
                "requested_start_month": start_month,
                "cost_multiplier": 1.0,
                **static_fifo_public,
            }]))

            if mode == "audit":
                audit_rows.append(input_audit)
                collected["margin_audit"].append(_margin_audit_frame(start_month, orders))
                continue
            _FAILURE_CONTEXT["phase"] = "satellite_replay"
            try:
                daily, replayed_orders, replay_audit = replay_satellite_ledger(
                    frames["base_daily"],
                    price_audit,
                    orders,
                    specs,
                    1.0,
                    expected_terminal_positions=expected_terminal_positions,
                )
                row_audit = {
                    **input_audit,
                    **replay_audit,
                    "replay_bankrupt_count": 0,
                    "replay_bankrupt_reason": "",
                }
                summary_rows.append(summarize_start(daily, start_month, 1.0))
            except ValueError as error:
                bankruptcy = bankrupt_failure_audit(start_month, 1.0, error)
                row_audit = {**input_audit, **bankruptcy}
                row_audit.update({
                    "missing_price_count": 0,
                    "max_reconciliation_error": 0.0,
                    "max_proposed_broker10_pct": 0.0,
                    "max_eod_broker10_prior_pct": 0.0,
                    "max_eod_broker10_current_pct": 0.0,
                    "unexpected_terminal_position_count": 1,
                    "max_terminal_position_reconciliation_error": 1.0,
                    "max_terminal_margin_reconciliation_error": 1.0,
                    "max_terminal_pnl_reconciliation_error": 1.0,
                })
                summary_rows.append(
                    _bankrupt_summary(frames["base_daily"], start_month, 1.0, error)
                )
                daily = pd.DataFrame()
                replayed_orders = pd.DataFrame()
            audit_rows.append(row_audit)
            collected["satellite_daily"].append(daily)
            collected["replayed_orders"].append(replayed_orders)
            collected["margin_audit"].append(
                _margin_audit_frame(start_month, orders, replayed_orders, daily)
            )
            collected["reconciliation"].append(
                pd.DataFrame([build_reconciliation_row(start_month, 1.0, row_audit)])
            )

    _FAILURE_CONTEXT.update({"requested_start_month": "", "phase": "decision"})
    input_audit_frame = pd.DataFrame(audit_rows)
    if mode == "audit":
        decision = evaluate_static_audit(input_audit_frame)
    else:
        decision = evaluate_canary(pd.DataFrame(summary_rows), input_audit_frame)
    frames_out = {
        key: pd.concat(values, ignore_index=True) if values else pd.DataFrame()
        for key, values in collected.items()
    }
    frames_out["summary"] = (
        pd.DataFrame(summary_rows)
        if summary_rows
        else pd.DataFrame(columns=sorted(_CANARY_SUMMARY_COLUMNS))
    )
    if mode == "audit":
        frames_out["reconciliation"] = pd.DataFrame(
            columns=[
                "requested_start_month",
                "cost_multiplier",
                "max_reconciliation_error",
                "max_terminal_position_reconciliation_error",
                "max_terminal_margin_reconciliation_error",
                "max_terminal_pnl_reconciliation_error",
            ]
        )
    frames_out["input_audit"] = input_audit_frame
    _FAILURE_CONTEXT["phase"] = "final_source_manifest"
    frames_out["source_manifest"] = finalize_worker_source_manifest(worker_manifests)
    frames_out["decision"] = decision
    _FAILURE_CONTEXT["phase"] = "write_outputs"
    write_stage_outputs(frames_out, OUTPUT_DIR)
    return frames_out


def main(
    mode: str = "canary",
    *,
    start_month: str | None = None,
    worker_output: Path | None = None,
) -> None:
    if mode == "identity-worker":
        if start_month is None or worker_output is None:
            raise ValueError("identity-worker requires start month and output")
        write_identity_worker_snapshot(start_month, worker_output)
        return
    if mode == "full":
        raise ValueError("full mode is closed by the Task3 gate")
    run_stage(mode)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stage137 current C9 quality one-way satellite")
    parser.add_argument(
        "--mode", choices=("audit", "canary", "full", "identity-worker"), default="canary"
    )
    parser.add_argument("--start-month")
    parser.add_argument("--worker-output", type=Path)
    arguments = parser.parse_args()
    try:
        main(
            arguments.mode,
            start_month=arguments.start_month,
            worker_output=arguments.worker_output,
        )
    except Exception as error:
        if arguments.mode in {"audit", "canary"}:
            diagnostic = write_failure_diagnostic(
                arguments.mode,
                error,
                requested_start_month=_FAILURE_CONTEXT["requested_start_month"],
                phase=_FAILURE_CONTEXT["phase"],
            )
            print(f"[stage137] fail-close diagnostic: {diagnostic}", file=sys.stderr)
        raise
