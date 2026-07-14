from __future__ import annotations

import argparse
from datetime import datetime
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any, Callable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parents[4]
LINE_ID = "futures_trend_rebuilt_c9_15w_v2_optimization"
STAGE = "Stage135"
MODEL_TAG = "stage135_no_jd_stage208_true_carry_degraded_v1"
OUTPUT_PREFIX = "rebuilt_c9_v2_stage135_no_jd_stage208_true_carry_degraded"

LINE_DIR = PROJECT_DIR / "research" / "lines" / LINE_ID
OUTPUT_DIR = LINE_DIR / "outputs" / "stage135_no_jd_stage208_true_carry_degraded"
PORTFOLIO_DIR = PROJECT_DIR / "examples" / "portfolio_backtesting"
BACKTEST_OUTPUT_DIR = PORTFOLIO_DIR / "backtest_outputs"
MINUTE_ROOT = PORTFOLIO_DIR / "downloaded_futures"

C9_CURVES_PATH = (
    BACKTEST_OUTPUT_DIR
    / "qmt_roll_stage167_c9_live_15w_multiperiod_ai_audit_curves_"
    "stage167_c9_live_15w_multiperiod_ai_audit_v1.csv"
)
STAGE020_DIR = LINE_DIR / "outputs" / "stage020_sqlite_jd_repair_xsmom_inputs"
STAGE020_PREFIX = "rebuilt_c9_v2_stage020_sqlite_jd_repair_xsmom_inputs"
STAGE020_TAG = "stage020_sqlite_jd_repair_xsmom_inputs_v1"
PRODUCT_RETURNS_PATH = STAGE020_DIR / f"{STAGE020_PREFIX}_product_returns_{STAGE020_TAG}.csv"
SATELLITE_DAILY_PATH = STAGE020_DIR / f"{STAGE020_PREFIX}_satellite_daily_{STAGE020_TAG}.csv"

CAPITAL = 150_000.0
ANALYSIS_END = pd.Timestamp("2026-06-30")
SPEC_NAME = "mom_12m_skip1m"
EXCLUDED_PRODUCT = "jd.DCE"
VOL_LOOKBACK = 63
TARGET_VOL = 0.10
ROUND_HALF_THRESHOLD = 0.50
BROKER_MARGIN_MULTIPLIER = 1.10
COST_MULTIPLIERS = (1.0, 2.0, 3.0)
CANARY_STARTS = ("2020-01",)
FULL_STARTS = tuple(pd.date_range("2020-01-01", "2026-01-01", freq="6MS").strftime("%Y-%m"))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(result):
        return default
    return result


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return _safe_float(value, default=np.nan)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def _to_json(value: Any) -> str:
    return json.dumps(_json_safe(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _split_products(value: Any) -> list[str]:
    if pd.isna(value):
        return []
    return [item.strip() for item in str(value).split(",") if item.strip()]


def drop_jd_without_replacement(signals: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    data = signals.copy()
    removed = 0
    original_legs = 0
    remaining_legs = 0
    for column in ("long_products", "short_products"):
        if column not in data.columns:
            data[column] = ""
        cleaned: list[str] = []
        for raw in data[column].tolist():
            products = _split_products(raw)
            original_legs += len(products)
            removed += sum(product == EXCLUDED_PRODUCT for product in products)
            kept = [product for product in products if product != EXCLUDED_PRODUCT]
            remaining_legs += len(kept)
            cleaned.append(",".join(kept))
        data[column] = cleaned
    return data, {
        "excluded_product": EXCLUDED_PRODUCT,
        "original_leg_count": int(original_legs),
        "removed_jd_leg_count": int(removed),
        "remaining_leg_count": int(remaining_legs),
        "replacement_leg_count": 0,
        "reranked": False,
    }


def build_price_frame(
    product_returns: pd.DataFrame,
    *,
    sizes: dict[str, Any],
    margin_ratios: dict[str, Any],
    slippages: dict[str, Any],
) -> pd.DataFrame:
    required = {"date", "product_vt_symbol", "main_contract_vt", "main_close", "product_return"}
    missing = sorted(required - set(product_returns.columns))
    if missing:
        raise ValueError("missing_price_columns:" + ",".join(missing))
    data = product_returns.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce").dt.normalize()
    data["product_vt_symbol"] = data["product_vt_symbol"].fillna("").astype(str)
    data["main_contract_vt"] = data["main_contract_vt"].fillna("").astype(str)
    data["main_close"] = pd.to_numeric(data["main_close"], errors="coerce")
    data["product_return"] = pd.to_numeric(data["product_return"], errors="coerce")
    data = data[~data["product_vt_symbol"].eq(EXCLUDED_PRODUCT)].copy()
    if data.empty:
        raise ValueError("empty_non_jd_price_frame")
    if data["date"].isna().any():
        raise ValueError("invalid_price_date")
    if data.duplicated(["date", "product_vt_symbol"]).any():
        raise ValueError("duplicate_price_date_product")
    if data["main_contract_vt"].eq("").any():
        raise ValueError("missing_main_contract")
    if data["main_close"].isna().any() or data["main_close"].le(0.0).any():
        raise ValueError("invalid_main_close")
    if data["product_return"].isna().any() or ~np.isfinite(data["product_return"]).all():
        raise ValueError("invalid_product_return")

    products = sorted(data["product_vt_symbol"].unique().tolist())
    for product in products:
        values = {
            "size": _safe_float(sizes.get(product), 0.0),
            "margin_ratio": _safe_float(margin_ratios.get(product), 0.0),
            "slippage": _safe_float(slippages.get(product), -1.0),
        }
        invalid = [
            name
            for name, value in values.items()
            if (name != "slippage" and value <= 0.0) or (name == "slippage" and value < 0.0)
        ]
        if invalid:
            raise ValueError(f"missing_exact_spec:{product}:" + ",".join(invalid))

    data = data.sort_values(["product_vt_symbol", "date"]).reset_index(drop=True)
    data["previous_close_raw"] = data.groupby("product_vt_symbol")["main_close"].shift(1)
    data["previous_contract"] = data.groupby("product_vt_symbol")["main_contract_vt"].shift(1)
    same_contract = data["main_contract_vt"].eq(data["previous_contract"])
    data["prev_main_close"] = np.where(
        same_contract & data["previous_close_raw"].gt(0.0),
        data["previous_close_raw"],
        data["main_close"],
    )
    data["size"] = data["product_vt_symbol"].map(sizes).astype(float)
    data["margin_ratio"] = data["product_vt_symbol"].map(margin_ratios).astype(float)
    data["slippage"] = data["product_vt_symbol"].map(slippages).astype(float)
    data["margin_per_contract"] = data["main_close"] * data["size"] * data["margin_ratio"]
    return data[
        [
            "date",
            "product_vt_symbol",
            "main_contract_vt",
            "main_close",
            "product_return",
            "prev_main_close",
            "size",
            "margin_ratio",
            "slippage",
            "margin_per_contract",
        ]
    ].sort_values(["date", "product_vt_symbol"]).reset_index(drop=True)


def _desired_products(signal_row: Any) -> list[tuple[str, int]]:
    if signal_row is None:
        return []
    if isinstance(signal_row, dict):
        long_value = signal_row.get("long_products", "")
        short_value = signal_row.get("short_products", "")
    else:
        long_value = getattr(signal_row, "long_products", "")
        short_value = getattr(signal_row, "short_products", "")
    desired = [(product, 1) for product in _split_products(long_value)]
    desired.extend((product, -1) for product in _split_products(short_value))
    products = [item[0] for item in desired]
    if len(products) != len(set(products)):
        raise ValueError("duplicate_or_opposed_signal_product")
    if EXCLUDED_PRODUCT in products:
        raise ValueError("jd_present_after_exclusion")
    return desired


def build_frozen_one_lot_daily(price_frame: pd.DataFrame, signals: pd.DataFrame) -> pd.DataFrame:
    prices = price_frame.copy()
    prices["date"] = pd.to_datetime(prices["date"], errors="coerce").dt.normalize()
    signal_data = signals.copy()
    signal_data["date"] = pd.to_datetime(signal_data["date"], errors="coerce").dt.normalize()
    price_by_date_product = {
        (row.date, str(row.product_vt_symbol)): row for row in prices.itertuples(index=False)
    }
    previous_positions: dict[str, dict[str, Any]] = {}
    rows: list[dict[str, Any]] = []
    for signal_row in signal_data.sort_values("date").itertuples(index=False):
        date = pd.Timestamp(signal_row.date).normalize()
        targets: dict[str, int] = {}
        target_meta: dict[str, dict[str, Any]] = {}
        desired = _desired_products(signal_row)
        unavailable_signal_leg_count = 0
        for product, direction in desired:
            price_row = price_by_date_product.get((date, product))
            if price_row is None:
                unavailable_signal_leg_count += 1
                continue
            contract = str(price_row.main_contract_vt)
            targets[contract] = int(direction)
            target_meta[contract] = {
                "product": product,
                "size": _safe_float(price_row.size),
                "slippage": _safe_float(price_row.slippage),
                "main_close": _safe_float(price_row.main_close),
                "prev_main_close": _safe_float(price_row.prev_main_close),
                "product_return": _safe_float(price_row.product_return),
                "margin_per_contract": _safe_float(price_row.margin_per_contract),
            }

        gross_pnl = sum(
            lots
            * target_meta[contract]["prev_main_close"]
            * target_meta[contract]["size"]
            * target_meta[contract]["product_return"]
            for contract, lots in targets.items()
        )
        turnover = 0
        slippage_cost = 0.0
        for contract in sorted(set(previous_positions) | set(targets)):
            old_lots = int(previous_positions.get(contract, {}).get("lots", 0))
            new_lots = int(targets.get(contract, 0))
            delta = abs(new_lots - old_lots)
            if delta == 0:
                continue
            meta = target_meta.get(contract) or previous_positions.get(contract, {})
            turnover += delta
            slippage_cost += delta * _safe_float(meta.get("slippage")) * _safe_float(meta.get("size"), 1.0)
        rows.append(
            {
                "date": date,
                "gross_pnl": float(gross_pnl),
                "slippage_cost": float(slippage_cost),
                "daily_pnl": float(gross_pnl - slippage_cost),
                "turnover_contracts": int(turnover),
                "desired_leg_count": int(len(desired)),
                "executable_leg_count": int(len(targets)),
                "unavailable_signal_leg_count": int(unavailable_signal_leg_count),
                "required_min1_margin": float(
                    sum(abs(lots) * target_meta[contract]["margin_per_contract"] for contract, lots in targets.items())
                ),
            }
        )
        previous_positions = {
            contract: {**target_meta[contract], "lots": int(lots)} for contract, lots in targets.items()
        }
    return pd.DataFrame(rows)


def build_stage101_scale(frozen_daily: pd.DataFrame, *, capital: float = CAPITAL) -> pd.Series:
    data = frozen_daily.copy().sort_values("date").reset_index(drop=True)
    pnl = pd.to_numeric(data["daily_pnl"], errors="coerce")
    if pnl.isna().any() or capital <= 0.0:
        raise ValueError("invalid_scale_input")
    returns = pnl / float(capital)
    vol = returns.rolling(VOL_LOOKBACK, min_periods=VOL_LOOKBACK).std(ddof=1).mul(math.sqrt(252.0)).shift(1)
    base = (TARGET_VOL / vol).replace([np.inf, -np.inf], np.nan).clip(lower=0.0, upper=1.0).fillna(0.0)
    own_momentum = pnl.rolling(VOL_LOOKBACK, min_periods=VOL_LOOKBACK).sum().shift(1).gt(0.0).astype(float)
    result = (base * own_momentum).astype(float)
    result.index = pd.to_datetime(data["date"], errors="raise").dt.normalize()
    result.name = "stage101_scale"
    return result


def resolve_fill_price(
    vt_symbol: str,
    signal_date: pd.Timestamp | None,
    fill_date: pd.Timestamp,
    minute_loader: Callable[[str], pd.DataFrame],
) -> dict[str, Any]:
    bars = minute_loader(vt_symbol).copy()
    if "bar_datetime" not in bars.columns or "open" not in bars.columns:
        raise RuntimeError(f"missing_real_fill:{vt_symbol}:invalid_minute_columns")
    bars["bar_datetime"] = pd.to_datetime(bars["bar_datetime"], errors="coerce").dt.tz_localize(None)
    bars["open"] = pd.to_numeric(bars["open"], errors="coerce")
    bars = bars.dropna(subset=["bar_datetime", "open"])
    bars = bars[bars["open"].gt(0.0)].sort_values("bar_datetime")
    fill_date = pd.Timestamp(fill_date).normalize()
    windows: list[tuple[pd.Timestamp, pd.Timestamp, str]] = []
    if signal_date is not None and pd.notna(signal_date):
        signal = pd.Timestamp(signal_date).normalize()
        windows.append(
            (
                signal + pd.Timedelta(hours=21),
                signal + pd.Timedelta(hours=21, minutes=5),
                "raw_prev_signal_night_2100_2105_first_open",
            )
        )
    windows.append(
        (
            fill_date + pd.Timedelta(hours=9),
            fill_date + pd.Timedelta(hours=9, minutes=5),
            "raw_fill_day_0900_0905_first_open",
        )
    )
    for start, end, source in windows:
        window = bars[bars["bar_datetime"].ge(start) & bars["bar_datetime"].lt(end)]
        if window.empty:
            continue
        first = window.iloc[0]
        return {
            "fill_price": float(first["open"]),
            "price_source": source,
            "bar_count": int(len(window)),
            "first_time": pd.Timestamp(first["bar_datetime"]),
            "last_time": pd.Timestamp(window.iloc[-1]["bar_datetime"]),
            "source_file": str(first.get("source_file", "")),
        }
    raise RuntimeError(f"missing_real_fill:{vt_symbol}:{fill_date.date()}")


def _sign(value: int) -> int:
    return int(value > 0) - int(value < 0)


def _delta_pnl(lots: int, start_price: float, end_price: float, size: float) -> float:
    return float(lots) * (float(end_price) - float(start_price)) * float(size)


def replay_target_transition(
    *,
    old_positions: dict[str, dict[str, Any]],
    targets: dict[str, int],
    target_meta: dict[str, dict[str, Any]],
    date: pd.Timestamp,
    signal_date: pd.Timestamp | None,
    minute_loader: Callable[[str], pd.DataFrame],
    slippage_multiplier: float,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    if slippage_multiplier < 1.0:
        raise ValueError("slippage_multiplier_below_one")
    gross_pnl = 0.0
    base_slippage = 0.0
    turnover = 0
    orders: list[dict[str, Any]] = []
    new_positions: dict[str, dict[str, Any]] = {}
    for contract in sorted(set(old_positions) | set(targets)):
        old = old_positions.get(contract)
        old_lots = int((old or {}).get("lots", 0))
        new_lots = int(targets.get(contract, 0))
        if old_lots == 0 and new_lots == 0:
            continue
        meta = target_meta.get(contract, {})
        product = str(meta.get("product") or (old or {}).get("product") or "")
        size = _safe_float(meta.get("size", (old or {}).get("size", 0.0)))
        slippage = _safe_float(meta.get("slippage", (old or {}).get("slippage", 0.0)))
        if not product or size <= 0.0 or slippage < 0.0:
            raise ValueError(f"invalid_position_meta:{contract}")
        last_mark = _safe_float((old or {}).get("last_mark", meta.get("main_close", 0.0)))
        close_price = _safe_float(meta.get("main_close", last_mark), last_mark)
        delta_abs = abs(new_lots - old_lots)
        fill: dict[str, Any] | None = None
        if delta_abs > 0:
            fill = resolve_fill_price(contract, signal_date, date, minute_loader)
            fill_price = _safe_float(fill["fill_price"])
            turnover += delta_abs
            base_slippage += delta_abs * slippage * size
            orders.append(
                {
                    "date": pd.Timestamp(date).normalize(),
                    "signal_date": pd.Timestamp(signal_date).normalize() if signal_date is not None else pd.NaT,
                    "contract": contract,
                    "product": product,
                    "old_lots": old_lots,
                    "target_lots": new_lots,
                    "delta_lots": new_lots - old_lots,
                    "fill_price": fill_price,
                    "close_price": close_price,
                    "size": size,
                    "slippage": slippage,
                    "base_slippage_cost": delta_abs * slippage * size,
                    "price_source": str(fill["price_source"]),
                    "bar_count": int(fill["bar_count"]),
                    "first_time": fill["first_time"],
                    "last_time": fill["last_time"],
                    "source_file": str(fill["source_file"]),
                }
            )
        else:
            fill_price = last_mark

        old_sign = _sign(old_lots)
        new_sign = _sign(new_lots)
        if old_lots == new_lots:
            gross_pnl += _delta_pnl(old_lots, last_mark, close_price, size)
        elif old_sign != 0 and new_sign == old_sign:
            carry_abs = min(abs(old_lots), abs(new_lots))
            carry_lots = old_sign * carry_abs
            gross_pnl += _delta_pnl(carry_lots, last_mark, close_price, size)
            if abs(old_lots) > abs(new_lots):
                gross_pnl += _delta_pnl(old_sign * (abs(old_lots) - abs(new_lots)), last_mark, fill_price, size)
            else:
                gross_pnl += _delta_pnl(old_sign * (abs(new_lots) - abs(old_lots)), fill_price, close_price, size)
        else:
            if old_lots != 0:
                gross_pnl += _delta_pnl(old_lots, last_mark, fill_price, size)
            if new_lots != 0:
                gross_pnl += _delta_pnl(new_lots, fill_price, close_price, size)

        if new_lots != 0:
            new_positions[contract] = {
                "lots": new_lots,
                "product": product,
                "size": size,
                "margin_ratio": _safe_float(meta.get("margin_ratio", (old or {}).get("margin_ratio", 0.0))),
                "slippage": slippage,
                "last_mark": close_price,
            }
    slippage_cost = base_slippage * float(slippage_multiplier)
    return new_positions, {
        "gross_pnl": float(gross_pnl),
        "base_slippage_cost": float(base_slippage),
        "slippage_cost": float(slippage_cost),
        "net_pnl": float(gross_pnl - slippage_cost),
        "turnover_contracts": int(turnover),
        "raw_order_count": int(len(orders)),
        "fallback_order_count": 0,
    }, orders


def apply_aggregate_margin_gate(
    targets: dict[str, int],
    target_meta: dict[str, dict[str, Any]],
    *,
    c9_margin_exact: float,
    previous_combined_equity: float,
) -> tuple[dict[str, int], dict[str, dict[str, Any]], dict[str, Any]]:
    proposed_satellite_margin = float(
        sum(abs(int(lots)) * _safe_float(target_meta[contract].get("margin_per_contract")) for contract, lots in targets.items())
    )
    if c9_margin_exact < 0.0 or previous_combined_equity <= 0.0:
        proposed_ratio = math.inf
    else:
        proposed_ratio = (
            (float(c9_margin_exact) + proposed_satellite_margin)
            * BROKER_MARGIN_MULTIPLIER
            / float(previous_combined_equity)
            * 100.0
        )
    skipped = int(bool(targets) and proposed_ratio > 100.0 + 1e-12)
    if skipped:
        kept_targets: dict[str, int] = {}
        kept_meta: dict[str, dict[str, Any]] = {}
        actual_satellite_margin = 0.0
    else:
        kept_targets = dict(targets)
        kept_meta = dict(target_meta)
        actual_satellite_margin = proposed_satellite_margin
    actual_ratio = (
        (float(c9_margin_exact) + actual_satellite_margin)
        * BROKER_MARGIN_MULTIPLIER
        / float(previous_combined_equity)
        * 100.0
        if previous_combined_equity > 0.0
        else math.inf
    )
    return kept_targets, kept_meta, {
        "margin_gate_skipped": skipped,
        "proposed_satellite_margin": proposed_satellite_margin,
        "actual_satellite_margin": actual_satellite_margin,
        "proposed_broker10_margin_to_equity_pct": float(proposed_ratio),
        "actual_broker10_margin_to_equity_pct": float(actual_ratio),
    }


def reconcile_combo_daily(daily: pd.DataFrame, *, capital: float = CAPITAL) -> dict[str, Any]:
    data = daily.copy()
    c9_net = pd.to_numeric(data["c9_net_pnl"], errors="coerce").fillna(0.0)
    sat_net = pd.to_numeric(data["satellite_net_pnl"], errors="coerce").fillna(0.0)
    c9_equity = pd.to_numeric(data["c9_account_equity"], errors="coerce")
    combined = pd.to_numeric(data["combined_equity"], errors="coerce")
    sat_cumulative = sat_net.cumsum()
    expected_from_daily = float(capital) + (c9_net + sat_net).cumsum()
    expected_from_legs = c9_equity + sat_cumulative
    error_daily = float((combined - expected_from_daily).abs().max()) if len(data) else 0.0
    error_legs = float((combined - expected_from_legs).abs().max()) if len(data) else 0.0
    c9_error = float((c9_equity - (float(capital) + c9_net.cumsum())).abs().max()) if len(data) else 0.0
    tolerance = 1e-6
    return {
        "max_abs_error_from_daily_pnl": error_daily,
        "max_abs_error_from_c9_plus_satellite": error_legs,
        "max_abs_c9_source_equity_error": c9_error,
        "reconciliation_pass": bool(max(error_daily, error_legs, c9_error) <= tolerance),
        "tolerance": tolerance,
    }


def longest_underwater_days(equity: pd.Series) -> int:
    values = pd.to_numeric(equity, errors="coerce").dropna().to_numpy(dtype=float)
    if len(values) == 0:
        return 0
    peak = -math.inf
    current = 0
    longest = 0
    for value in values:
        if value >= peak - 1e-9:
            peak = max(peak, value)
            current = 0
        else:
            current += 1
            longest = max(longest, current)
    return int(longest)


def evaluate_canary(evidence: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "fallback_orders_zero": int(evidence.get("fallback_order_count", -1)) == 0,
        "reconciliation_within_1e_6": _safe_float(evidence.get("max_reconciliation_error"), math.inf) <= 1e-6,
        "aggregate_broker10_le_100pct": _safe_float(
            evidence.get("max_aggregate_broker10_margin_to_equity_pct"), math.inf
        )
        <= 100.0 + 1e-9,
        "return_retention_ge_70pct": _safe_float(evidence.get("return_retention_pct"), -math.inf) >= 70.0,
        "max_drawdown_strictly_better": _safe_float(evidence.get("c_max_drawdown_pct"), -math.inf)
        > _safe_float(evidence.get("a_max_drawdown_pct"), math.inf) + 1e-12,
        "longest_underwater_strictly_shorter": int(evidence.get("c_longest_underwater_days", 10**9))
        < int(evidence.get("a_longest_underwater_days", -1)),
        "b_not_bankrupt": _safe_float(evidence.get("b_min_equity"), -math.inf) > 0.0,
        "c_not_bankrupt": _safe_float(evidence.get("c_min_equity"), -math.inf) > 0.0,
    }
    failure_names = {
        "fallback_orders_zero": "fallback_orders_nonzero",
        "reconciliation_within_1e_6": "reconciliation_error_above_1e_6",
        "aggregate_broker10_le_100pct": "aggregate_broker10_above_100pct",
        "return_retention_ge_70pct": "return_retention_below_70pct",
        "max_drawdown_strictly_better": "max_drawdown_not_strictly_better",
        "longest_underwater_strictly_shorter": "longest_underwater_not_strictly_shorter",
        "b_not_bankrupt": "b_equity_bankrupt",
        "c_not_bankrupt": "c_equity_bankrupt",
    }
    failed = [failure_names[name] for name, passed in checks.items() if not passed]
    return {"canary_pass": not failed, "checks": checks, "failed_checks": failed}


class MinuteBarStore:
    def __init__(self, root: Path = MINUTE_ROOT) -> None:
        self.root = Path(root)
        self.paths_by_contract: dict[str, list[Path]] = {}

    def _paths(self, vt_symbol: str) -> list[Path]:
        if vt_symbol in self.paths_by_contract:
            return self.paths_by_contract[vt_symbol]
        if "." not in vt_symbol:
            raise ValueError(f"invalid_contract_vt:{vt_symbol}")
        symbol, exchange = vt_symbol.split(".", 1)
        candidates: set[Path] = set()
        for suffix in ("minute_backtest", "completed_minute_backtest"):
            candidates.update(self.root.rglob(f"{symbol}_{suffix}.csv"))
        paths = sorted(path for path in candidates if path.parent.name == exchange)
        self.paths_by_contract[vt_symbol] = paths
        return paths

    @lru_cache(maxsize=None)
    def __call__(self, vt_symbol: str) -> pd.DataFrame:
        frames: list[pd.DataFrame] = []
        for path in self._paths(vt_symbol):
            try:
                data = pd.read_csv(path, encoding="utf-8-sig")
            except Exception as exc:
                raise RuntimeError(f"minute_read_failed:{vt_symbol}:{path}:{exc}") from exc
            required = {"bar_datetime", "open"}
            if not required.issubset(data.columns):
                raise RuntimeError(f"minute_columns_missing:{vt_symbol}:{path}")
            if "vt_symbol" in data.columns:
                data = data[data["vt_symbol"].fillna("").astype(str).eq(vt_symbol)].copy()
            data["bar_datetime"] = pd.to_datetime(data["bar_datetime"], errors="coerce").dt.tz_localize(None)
            data["open"] = pd.to_numeric(data["open"], errors="coerce")
            data = data.dropna(subset=["bar_datetime", "open"])
            data = data[data["open"].gt(0.0)].copy()
            data["source_file"] = str(path)
            frames.append(data[["bar_datetime", "open", "source_file"]])
        if not frames:
            return pd.DataFrame(columns=["bar_datetime", "open", "source_file"])
        bars = pd.concat(frames, ignore_index=True).sort_values(["bar_datetime", "source_file"])
        duplicate = bars[bars.duplicated("bar_datetime", keep=False)]
        if not duplicate.empty:
            conflict = duplicate.groupby("bar_datetime")["open"].nunique(dropna=False).gt(1)
            if conflict.any():
                first_conflict = conflict[conflict].index[0]
                raise RuntimeError(f"conflicting_duplicate_minute_open:{vt_symbol}:{first_conflict}")
        return bars.drop_duplicates("bar_datetime", keep="first").reset_index(drop=True)


def _target_meta_for_date(
    date: pd.Timestamp,
    desired: list[tuple[str, int]],
    price_by_date_product: dict[tuple[pd.Timestamp, str], Any],
) -> tuple[dict[str, int], dict[str, dict[str, Any]]]:
    targets: dict[str, int] = {}
    target_meta: dict[str, dict[str, Any]] = {}
    for product, direction in desired:
        price_row = price_by_date_product.get((date, product))
        if price_row is None:
            continue
        contract = str(price_row.main_contract_vt)
        if contract in targets:
            raise ValueError(f"duplicate_target_contract:{date.date()}:{contract}")
        targets[contract] = int(direction)
        target_meta[contract] = {
            "product": product,
            "size": _safe_float(price_row.size),
            "margin_ratio": _safe_float(price_row.margin_ratio),
            "slippage": _safe_float(price_row.slippage),
            "main_close": _safe_float(price_row.main_close),
            "margin_per_contract": _safe_float(price_row.margin_per_contract),
        }
    return targets, target_meta


def _build_pretrade_margin_meta(
    targets: dict[str, int],
    target_meta: dict[str, dict[str, Any]],
    old_positions: dict[str, dict[str, Any]],
    *,
    date: pd.Timestamp,
    signal_date: pd.Timestamp | None,
    minute_loader: Callable[[str], pd.DataFrame],
) -> dict[str, dict[str, Any]]:
    known: dict[str, dict[str, Any]] = {}
    for contract, lots in targets.items():
        meta = target_meta[contract]
        size = _safe_float(meta.get("size"))
        margin_ratio = _safe_float(meta.get("margin_ratio"))
        if size <= 0.0 or margin_ratio <= 0.0:
            raise ValueError(f"invalid_pretrade_margin_meta:{contract}")
        old = old_positions.get(contract)
        if old is not None and int(old.get("lots", 0)) != 0:
            reference_price = _safe_float(old.get("last_mark"))
        else:
            fill = resolve_fill_price(contract, signal_date, date, minute_loader)
            reference_price = _safe_float(fill.get("fill_price"))
        if reference_price <= 0.0:
            raise ValueError(f"invalid_pretrade_margin_price:{contract}")
        known[contract] = {
            **meta,
            "margin_reference_price": reference_price,
            "margin_per_contract": reference_price * size * margin_ratio,
            "lots": int(lots),
        }
    return known


def simulate_window(
    c9_curve: pd.DataFrame,
    price_frame: pd.DataFrame,
    signals: pd.DataFrame,
    scale_by_date: pd.Series,
    *,
    requested_start_month: str,
    minute_loader: Callable[[str], pd.DataFrame],
    slippage_multiplier: float,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    required_c9 = {
        "date",
        "net_pnl",
        "total_slippage",
        "trade_count",
        "account_equity",
        "total_margin_exact",
    }
    missing = sorted(required_c9 - set(c9_curve.columns))
    if missing:
        raise ValueError("missing_c9_columns:" + ",".join(missing))
    if slippage_multiplier < 1.0:
        raise ValueError("slippage_multiplier_below_one")

    c9 = c9_curve.copy()
    c9["date"] = pd.to_datetime(c9["date"], errors="coerce").dt.normalize()
    c9 = c9.dropna(subset=["date"]).sort_values("date").drop_duplicates("date", keep="last")
    for column in ["net_pnl", "total_slippage", "trade_count", "account_equity", "total_margin_exact"]:
        c9[column] = pd.to_numeric(c9[column], errors="coerce")
    if c9.empty or c9[["net_pnl", "total_slippage", "account_equity", "total_margin_exact"]].isna().any().any():
        raise ValueError("invalid_c9_curve")
    if c9["total_margin_exact"].lt(0.0).any() or c9["total_slippage"].lt(0.0).any():
        raise ValueError("negative_c9_margin_or_slippage")
    c9["c9_source_net_pnl"] = c9["net_pnl"].astype(float)
    c9["c9_base_slippage"] = c9["total_slippage"].astype(float)
    c9["c9_net_pnl_stressed"] = c9["c9_source_net_pnl"] - (
        float(slippage_multiplier) - 1.0
    ) * c9["c9_base_slippage"]
    c9["c9_equity_stressed"] = CAPITAL + c9["c9_net_pnl_stressed"].cumsum()

    prices = price_frame.copy()
    prices["date"] = pd.to_datetime(prices["date"], errors="coerce").dt.normalize()
    price_by_date_product = {
        (row.date, str(row.product_vt_symbol)): row for row in prices.itertuples(index=False)
    }
    signal_data = signals.copy()
    signal_data["date"] = pd.to_datetime(signal_data["date"], errors="coerce").dt.normalize()
    signal_by_date = {row.date: row for row in signal_data.itertuples(index=False)}
    c9_dates = set(c9["date"])
    if c9_dates - set(signal_by_date):
        first = sorted(c9_dates - set(signal_by_date))[0]
        raise ValueError(f"missing_signal_date:{first.date()}")
    scale = scale_by_date.copy()
    scale.index = pd.to_datetime(scale.index, errors="raise").normalize()

    positions: dict[str, dict[str, Any]] = {}
    satellite_cumulative_pnl = 0.0
    previous_combined_equity = CAPITAL
    daily_rows: list[dict[str, Any]] = []
    target_rows: list[dict[str, Any]] = []
    order_rows: list[dict[str, Any]] = []
    dates = c9["date"].tolist()

    for index, c9_row in enumerate(c9.itertuples(index=False)):
        date = pd.Timestamp(c9_row.date).normalize()
        signal_date = pd.Timestamp(dates[index - 1]).normalize() if index > 0 else None
        signal_row = signal_by_date[date]
        desired = _desired_products(signal_row)
        stage101_scale = _safe_float(scale.get(date, 0.0))
        start_day_forced_flat = int(index == 0)
        if not start_day_forced_flat and stage101_scale >= ROUND_HALF_THRESHOLD:
            proposed_targets, proposed_meta = _target_meta_for_date(date, desired, price_by_date_product)
        else:
            proposed_targets, proposed_meta = {}, {}
        c9_margin_known_pretrade = (
            _safe_float(c9.iloc[index - 1]["total_margin_exact"]) if index > 0 else 0.0
        )

        if start_day_forced_flat:
            targets, target_meta = {}, {}
            margin_audit = {
                "margin_gate_skipped": 0,
                "proposed_satellite_margin": 0.0,
                "actual_satellite_margin": 0.0,
                "proposed_broker10_margin_to_equity_pct": 0.0,
                "actual_broker10_margin_to_equity_pct": 0.0,
            }
        else:
            pretrade_margin_meta = _build_pretrade_margin_meta(
                proposed_targets,
                proposed_meta,
                positions,
                date=date,
                signal_date=signal_date,
                minute_loader=minute_loader,
            )
            targets, _kept_pretrade_meta, margin_audit = apply_aggregate_margin_gate(
                proposed_targets,
                pretrade_margin_meta,
                c9_margin_exact=c9_margin_known_pretrade,
                previous_combined_equity=previous_combined_equity,
            )
            target_meta = {contract: proposed_meta[contract] for contract in targets}

        positions, replay, orders = replay_target_transition(
            old_positions=positions,
            targets=targets,
            target_meta=target_meta,
            date=date,
            signal_date=signal_date,
            minute_loader=minute_loader,
            slippage_multiplier=slippage_multiplier,
        )
        satellite_cumulative_pnl += _safe_float(replay["net_pnl"])
        c9_equity = _safe_float(c9_row.c9_equity_stressed)
        carried_leg_equity = CAPITAL + satellite_cumulative_pnl
        combined_equity = c9_equity + satellite_cumulative_pnl
        current_satellite_margin = float(
            sum(abs(int(targets[contract])) * _safe_float(target_meta[contract]["margin_per_contract"]) for contract in targets)
        )
        end_of_day_ratio = (
            (_safe_float(c9_row.total_margin_exact) + current_satellite_margin)
            * BROKER_MARGIN_MULTIPLIER
            / previous_combined_equity
            * 100.0
            if previous_combined_equity > 0.0
            else math.inf
        )
        daily_rows.append(
            {
                "date": date,
                "requested_start_month": requested_start_month,
                "slippage_multiplier": float(slippage_multiplier),
                "c9_net_pnl": _safe_float(c9_row.c9_net_pnl_stressed),
                "c9_source_net_pnl": _safe_float(c9_row.c9_source_net_pnl),
                "c9_base_slippage_cost": _safe_float(c9_row.c9_base_slippage),
                "c9_slippage_cost": _safe_float(c9_row.c9_base_slippage) * float(slippage_multiplier),
                "c9_trade_count": _safe_float(c9_row.trade_count),
                "c9_source_account_equity": _safe_float(c9_row.account_equity),
                "c9_account_equity": c9_equity,
                "c9_total_margin_exact": _safe_float(c9_row.total_margin_exact),
                "c9_margin_exact_known_pretrade": c9_margin_known_pretrade,
                "satellite_gross_pnl": _safe_float(replay["gross_pnl"]),
                "satellite_base_slippage_cost": _safe_float(replay["base_slippage_cost"]),
                "satellite_slippage_cost": _safe_float(replay["slippage_cost"]),
                "satellite_net_pnl": _safe_float(replay["net_pnl"]),
                "satellite_turnover_contracts": int(replay["turnover_contracts"]),
                "satellite_raw_order_count": int(replay["raw_order_count"]),
                "satellite_fallback_order_count": int(replay["fallback_order_count"]),
                "satellite_cumulative_pnl": satellite_cumulative_pnl,
                "carried_leg_equity": carried_leg_equity,
                "combined_equity": combined_equity,
                "previous_combined_equity": previous_combined_equity,
                "satellite_margin": current_satellite_margin,
                "satellite_margin_known_pretrade": _safe_float(margin_audit["actual_satellite_margin"]),
                "aggregate_broker10_margin_known_pretrade": (
                    c9_margin_known_pretrade + _safe_float(margin_audit["actual_satellite_margin"])
                )
                * BROKER_MARGIN_MULTIPLIER,
                "aggregate_broker10_margin_to_previous_equity_pct": _safe_float(
                    margin_audit["actual_broker10_margin_to_equity_pct"], math.inf
                ),
                "end_of_day_aggregate_broker10_margin_to_previous_equity_pct": end_of_day_ratio,
                "stage101_scale": stage101_scale,
                "margin_gate_skipped": int(margin_audit["margin_gate_skipped"]),
                "held_contract_count": int(len(targets)),
                "desired_signal_count": int(len(desired)),
                "start_day_forced_flat": start_day_forced_flat,
            }
        )
        target_rows.append(
            {
                "date": date,
                "signal_date": signal_date,
                "requested_start_month": requested_start_month,
                "slippage_multiplier": float(slippage_multiplier),
                "stage101_scale": stage101_scale,
                "scale_round_half_active": int(stage101_scale >= ROUND_HALF_THRESHOLD),
                "start_day_forced_flat": start_day_forced_flat,
                "desired_signal_count": int(len(desired)),
                "proposed_contract_count": int(len(proposed_targets)),
                "held_contract_count": int(len(targets)),
                "margin_gate_skipped": int(margin_audit["margin_gate_skipped"]),
                "proposed_satellite_margin": _safe_float(margin_audit["proposed_satellite_margin"]),
                "actual_satellite_margin": current_satellite_margin,
                "satellite_margin_known_pretrade": _safe_float(margin_audit["actual_satellite_margin"]),
                "c9_margin_exact_known_pretrade": c9_margin_known_pretrade,
                "proposed_broker10_margin_to_equity_pct": _safe_float(
                    margin_audit["proposed_broker10_margin_to_equity_pct"], math.inf
                ),
                "actual_broker10_margin_to_equity_pct": _safe_float(
                    margin_audit["actual_broker10_margin_to_equity_pct"], math.inf
                ),
                "end_of_day_broker10_margin_to_previous_equity_pct": end_of_day_ratio,
                "desired_products_json": _to_json(
                    [{"product": product, "direction": direction} for product, direction in desired]
                ),
                "targets_json": _to_json(targets),
                "target_meta_json": _to_json(target_meta),
            }
        )
        for order in orders:
            order_rows.append(
                {
                    **order,
                    "requested_start_month": requested_start_month,
                    "slippage_multiplier": float(slippage_multiplier),
                }
            )
        previous_combined_equity = combined_equity

    daily = pd.DataFrame(daily_rows)
    targets = pd.DataFrame(target_rows)
    orders = pd.DataFrame(order_rows)
    return daily, targets, orders


def _drawdown_pct(equity: pd.Series) -> pd.Series:
    values = pd.to_numeric(equity, errors="coerce").ffill()
    peak = values.cummax()
    return (values / peak.replace(0.0, np.nan) - 1.0).replace([np.inf, -np.inf], np.nan).fillna(0.0) * 100.0


def _sharpe(equity: pd.Series) -> float:
    values = pd.to_numeric(equity, errors="coerce").dropna()
    returns = values.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    if len(returns) < 2:
        return 0.0
    std = float(returns.std(ddof=1))
    return float(returns.mean() / std * math.sqrt(252.0)) if std > 0.0 else 0.0


def summarize_arms(daily: pd.DataFrame) -> pd.DataFrame:
    if daily.empty:
        return pd.DataFrame()
    data = daily.sort_values("date").copy()
    start_month = str(data["requested_start_month"].iloc[0])
    cost_multiplier = _safe_float(data["slippage_multiplier"].iloc[0], 1.0)
    arms = (
        (
            "A_c9_frozen",
            "c9_account_equity",
            pd.to_numeric(data["c9_net_pnl"], errors="coerce").fillna(0.0),
            pd.to_numeric(data["c9_slippage_cost"], errors="coerce").fillna(0.0),
            pd.to_numeric(data["c9_trade_count"], errors="coerce").fillna(0.0),
        ),
        (
            "B_no_jd_true_carried_leg",
            "carried_leg_equity",
            pd.to_numeric(data["satellite_net_pnl"], errors="coerce").fillna(0.0),
            pd.to_numeric(data["satellite_slippage_cost"], errors="coerce").fillna(0.0),
            pd.to_numeric(data["satellite_turnover_contracts"], errors="coerce").fillna(0.0),
        ),
        (
            "C_c9_plus_no_jd_true_carried",
            "combined_equity",
            pd.to_numeric(data["c9_net_pnl"], errors="coerce").fillna(0.0)
            + pd.to_numeric(data["satellite_net_pnl"], errors="coerce").fillna(0.0),
            pd.to_numeric(data["c9_slippage_cost"], errors="coerce").fillna(0.0)
            + pd.to_numeric(data["satellite_slippage_cost"], errors="coerce").fillna(0.0),
            pd.to_numeric(data["c9_trade_count"], errors="coerce").fillna(0.0)
            + pd.to_numeric(data["satellite_turnover_contracts"], errors="coerce").fillna(0.0),
        ),
    )
    rows: list[dict[str, Any]] = []
    for arm, equity_column, pnl, slippage, trade_count in arms:
        equity = pd.to_numeric(data[equity_column], errors="coerce")
        nonzero = pnl[pnl.ne(0.0)]
        rows.append(
            {
                "stage": STAGE,
                "model_tag": MODEL_TAG,
                "line_id": LINE_ID,
                "requested_start_month": start_month,
                "slippage_multiplier": cost_multiplier,
                "arm": arm,
                "start_date": pd.Timestamp(data["date"].iloc[0]).date().isoformat(),
                "end_date": pd.Timestamp(data["date"].iloc[-1]).date().isoformat(),
                "trading_days": int(len(data)),
                "start_equity": float(equity.iloc[0]),
                "end_equity": float(equity.iloc[-1]),
                "total_return_pct": float((equity.iloc[-1] / CAPITAL - 1.0) * 100.0),
                "max_drawdown_pct": float(_drawdown_pct(equity).min()),
                "sharpe": _sharpe(equity),
                "longest_underwater_days": longest_underwater_days(equity),
                "min_equity": float(equity.min()),
                "total_slippage": float(slippage.sum()),
                "total_trade_count": float(trade_count.sum()),
                "nonzero_day_count": int(len(nonzero)),
                "nonzero_day_win_rate_pct": float(nonzero.gt(0.0).mean() * 100.0) if len(nonzero) else 0.0,
            }
        )
    return pd.DataFrame(rows)


def build_canary_evidence(
    summary: pd.DataFrame,
    *,
    reconciliation: dict[str, Any],
    daily: pd.DataFrame,
    orders: pd.DataFrame,
) -> dict[str, Any]:
    by_arm = summary.set_index("arm")
    a = by_arm.loc["A_c9_frozen"]
    b = by_arm.loc["B_no_jd_true_carried_leg"]
    c = by_arm.loc["C_c9_plus_no_jd_true_carried"]
    a_return = _safe_float(a["total_return_pct"])
    c_return = _safe_float(c["total_return_pct"])
    retention = c_return / a_return * 100.0 if a_return > 0.0 else math.nan
    fallback_order_count = 0
    if not orders.empty and "price_source" in orders.columns:
        fallback_order_count = int(orders["price_source"].fillna("").astype(str).str.startswith("fallback").sum())
    elif "satellite_fallback_order_count" in daily.columns:
        fallback_order_count = int(pd.to_numeric(daily["satellite_fallback_order_count"], errors="coerce").fillna(0).sum())
    reconciliation_errors = [
        _safe_float(reconciliation.get("max_abs_error_from_daily_pnl"), math.inf),
        _safe_float(reconciliation.get("max_abs_error_from_c9_plus_satellite"), math.inf),
        _safe_float(reconciliation.get("max_abs_c9_source_equity_error"), math.inf),
    ]
    return {
        "requested_start_month": str(summary["requested_start_month"].iloc[0]),
        "slippage_multiplier": _safe_float(summary["slippage_multiplier"].iloc[0], 1.0),
        "fallback_order_count": fallback_order_count,
        "max_reconciliation_error": max(reconciliation_errors),
        "max_aggregate_broker10_margin_to_equity_pct": float(
            pd.to_numeric(
                daily["aggregate_broker10_margin_to_previous_equity_pct"], errors="coerce"
            ).max()
        ),
        "return_retention_pct": float(retention),
        "a_total_return_pct": a_return,
        "c_total_return_pct": c_return,
        "a_max_drawdown_pct": _safe_float(a["max_drawdown_pct"]),
        "c_max_drawdown_pct": _safe_float(c["max_drawdown_pct"]),
        "a_longest_underwater_days": int(a["longest_underwater_days"]),
        "c_longest_underwater_days": int(c["longest_underwater_days"]),
        "b_min_equity": _safe_float(b["min_equity"]),
        "c_min_equity": _safe_float(c["min_equity"]),
        "margin_gate_skip_days": int(pd.to_numeric(daily["margin_gate_skipped"], errors="coerce").fillna(0).sum()),
    }


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig", **kwargs)


def _load_qmt_specs() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    if str(PORTFOLIO_DIR) not in sys.path:
        sys.path.insert(0, str(PORTFOLIO_DIR))
    from qmt_universe import MARGIN_RATIOS, SIZES, SLIPPAGES

    return dict(SIZES), dict(MARGIN_RATIOS), dict(SLIPPAGES)


def _load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.Series, dict[str, Any]]:
    c9 = _read_csv(C9_CURVES_PATH)
    c9["requested_start_month"] = c9["requested_start_month"].astype(str)
    c9["date"] = pd.to_datetime(c9["date"], errors="coerce").dt.normalize()
    c9 = c9[c9["date"].le(ANALYSIS_END)].copy()
    product_returns = _read_csv(PRODUCT_RETURNS_PATH)
    satellite = _read_csv(SATELLITE_DAILY_PATH)
    satellite = satellite[satellite["spec"].fillna("").astype(str).eq(SPEC_NAME)].copy()
    satellite["date"] = pd.to_datetime(satellite["date"], errors="coerce").dt.normalize()
    signals, exclusion_audit = drop_jd_without_replacement(satellite)
    sizes, margin_ratios, slippages = _load_qmt_specs()
    price_frame = build_price_frame(
        product_returns,
        sizes=sizes,
        margin_ratios=margin_ratios,
        slippages=slippages,
    )
    frozen_daily = build_frozen_one_lot_daily(price_frame, signals)
    scale_by_date = build_stage101_scale(frozen_daily, capital=CAPITAL)
    return c9, product_returns, signals, price_frame, frozen_daily, scale_by_date, exclusion_audit


def audit_inputs(
    c9: pd.DataFrame,
    signals: pd.DataFrame,
    price_frame: pd.DataFrame,
    frozen_daily: pd.DataFrame,
    scale_by_date: pd.Series,
    exclusion_audit: dict[str, Any],
    *,
    starts: tuple[str, ...],
) -> dict[str, Any]:
    blocking: list[str] = []
    available_starts = set(c9["requested_start_month"].astype(str))
    missing_starts = sorted(set(starts) - available_starts)
    blocking.extend(f"missing_c9_start:{item}" for item in missing_starts)
    signal_dates = set(pd.to_datetime(signals["date"], errors="coerce").dropna().dt.normalize())
    price_dates = set(pd.to_datetime(price_frame["date"], errors="coerce").dropna().dt.normalize())
    c9_identity_max_error = 0.0
    c9_margin_relation_max_error = 0.0
    for start in starts:
        curve = c9[c9["requested_start_month"].astype(str).eq(start)].sort_values("date")
        if curve.empty:
            continue
        dates = set(curve["date"])
        missing_signal_dates = dates - signal_dates
        missing_price_dates = dates - price_dates
        if missing_signal_dates:
            blocking.append(f"missing_signal_dates:{start}:{len(missing_signal_dates)}")
        if missing_price_dates:
            blocking.append(f"missing_price_dates:{start}:{len(missing_price_dates)}")
        net = pd.to_numeric(curve["net_pnl"], errors="coerce")
        equity = pd.to_numeric(curve["account_equity"], errors="coerce")
        error = float((CAPITAL + net.cumsum() - equity).abs().max())
        c9_identity_max_error = max(c9_identity_max_error, error)
        if error > 1e-6:
            blocking.append(f"c9_equity_identity:{start}:{error:.9f}")
        if "broker10_total_margin_exact" in curve.columns:
            margin_error = float(
                (
                    pd.to_numeric(curve["total_margin_exact"], errors="coerce") * BROKER_MARGIN_MULTIPLIER
                    - pd.to_numeric(curve["broker10_total_margin_exact"], errors="coerce")
                )
                .abs()
                .max()
            )
            c9_margin_relation_max_error = max(c9_margin_relation_max_error, margin_error)
            if margin_error > 1e-6:
                blocking.append(f"c9_broker10_identity:{start}:{margin_error:.9f}")
    if signals[["long_products", "short_products"]].fillna("").astype(str).apply(
        lambda column: column.str.split(",").map(lambda values: EXCLUDED_PRODUCT in values)
    ).any().any():
        blocking.append("jd_present_after_exclusion")
    if int(exclusion_audit.get("replacement_leg_count", -1)) != 0:
        blocking.append("jd_replacement_detected")
    if len(frozen_daily) != len(signals) or len(scale_by_date) != len(signals):
        blocking.append("frozen_scale_date_count_mismatch")
    if pd.Series(scale_by_date).isna().any():
        blocking.append("scale_contains_nan")
    if ((pd.Series(scale_by_date) < 0.0) | (pd.Series(scale_by_date) > 1.0)).any():
        blocking.append("scale_out_of_range")
    return {
        "ready": not blocking,
        "blocking_reasons": blocking,
        "requested_starts": list(starts),
        "available_start_count": int(len(available_starts)),
        "signal_row_count": int(len(signals)),
        "signal_date_count": int(len(signal_dates)),
        "price_row_count": int(len(price_frame)),
        "price_product_count": int(price_frame["product_vt_symbol"].nunique()),
        "price_date_count": int(len(price_dates)),
        "frozen_daily_row_count": int(len(frozen_daily)),
        "scale_nonzero_day_count": int(pd.Series(scale_by_date).gt(0.0).sum()),
        "scale_round_half_active_day_count": int(pd.Series(scale_by_date).ge(ROUND_HALF_THRESHOLD).sum()),
        "unavailable_prelisting_signal_leg_count": int(
            pd.to_numeric(frozen_daily.get("unavailable_signal_leg_count", 0), errors="coerce").fillna(0).sum()
        ),
        "c9_identity_max_abs_error": c9_identity_max_error,
        "c9_broker10_relation_max_abs_error": c9_margin_relation_max_error,
        **exclusion_audit,
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_source_manifest(orders: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    primary = [C9_CURVES_PATH, PRODUCT_RETURNS_PATH, SATELLITE_DAILY_PATH, PORTFOLIO_DIR / "qmt_universe.py"]
    for path in primary:
        stat = path.stat()
        rows.append(
            {
                "source_type": "primary_hashed",
                "path": str(path),
                "size_bytes": int(stat.st_size),
                "mtime_ns": int(stat.st_mtime_ns),
                "sha256": _sha256(path),
            }
        )
    if not orders.empty and "source_file" in orders.columns:
        for raw in sorted(set(orders["source_file"].dropna().astype(str))):
            path = Path(raw)
            if not path.exists():
                rows.append(
                    {
                        "source_type": "minute_used_missing",
                        "path": raw,
                        "size_bytes": 0,
                        "mtime_ns": 0,
                        "sha256": "",
                    }
                )
                continue
            stat = path.stat()
            rows.append(
                {
                    "source_type": "minute_used_hashed",
                    "path": raw,
                    "size_bytes": int(stat.st_size),
                    "mtime_ns": int(stat.st_mtime_ns),
                    "sha256": _sha256(path),
                }
            )
    return pd.DataFrame(rows)


def build_full_evidence(
    summary: pd.DataFrame,
    reconciliation: pd.DataFrame,
    daily: pd.DataFrame,
    orders: pd.DataFrame,
) -> dict[str, Any]:
    pivot = summary.pivot_table(
        index=["requested_start_month", "slippage_multiplier"],
        columns="arm",
        values=["total_return_pct", "max_drawdown_pct", "longest_underwater_days", "min_equity"],
        aggfunc="last",
    )
    pivot.columns = [f"{metric}__{arm}" for metric, arm in pivot.columns]
    pivot = pivot.reset_index()
    pivot["return_retention_pct"] = (
        pivot["total_return_pct__C_c9_plus_no_jd_true_carried"]
        / pivot["total_return_pct__A_c9_frozen"].replace(0.0, np.nan)
        * 100.0
    )
    positive_base = pivot[pivot["total_return_pct__A_c9_frozen"].gt(0.0)].copy()
    one = pivot[pivot["slippage_multiplier"].eq(1.0)].copy()
    start_2022 = one[one["requested_start_month"].eq("2022-01")]
    cost_robust_checks: dict[str, bool] = {}
    for multiplier in (2.0, 3.0):
        group = positive_base[positive_base["slippage_multiplier"].eq(multiplier)]
        cost_robust_checks[f"cost{multiplier:g}_retention_all_ge70"] = bool(
            not group.empty and group["return_retention_pct"].ge(70.0).all()
        )
        cost_robust_checks[f"cost{multiplier:g}_worst_dd_not_worse"] = bool(
            not group.empty
            and group["max_drawdown_pct__C_c9_plus_no_jd_true_carried"].min()
            >= group["max_drawdown_pct__A_c9_frozen"].min() - 1e-12
        )
    fallback = 0
    if not orders.empty:
        fallback = int(orders["price_source"].fillna("").astype(str).str.startswith("fallback").sum())
    checks = {
        "fallback_zero": fallback == 0,
        "reconciliation_all_pass": bool(not reconciliation.empty and reconciliation["reconciliation_pass"].all()),
        "aggregate_broker10_all_le100": bool(
            pd.to_numeric(daily["aggregate_broker10_margin_to_previous_equity_pct"], errors="coerce")
            .le(100.0 + 1e-9)
            .all()
        ),
        "all_positive_base_starts_retention_ge70": bool(
            not positive_base.empty and positive_base["return_retention_pct"].ge(70.0).all()
        ),
        "worst_dd_strictly_better_1x": bool(
            not one.empty
            and one["max_drawdown_pct__C_c9_plus_no_jd_true_carried"].min()
            > one["max_drawdown_pct__A_c9_frozen"].min() + 1e-12
        ),
        "worst_underwater_strictly_shorter_1x": bool(
            not one.empty
            and one["longest_underwater_days__C_c9_plus_no_jd_true_carried"].max()
            < one["longest_underwater_days__A_c9_frozen"].max()
        ),
        "start2022_dd_strictly_better": bool(
            not start_2022.empty
            and float(start_2022["max_drawdown_pct__C_c9_plus_no_jd_true_carried"].iloc[0])
            > float(start_2022["max_drawdown_pct__A_c9_frozen"].iloc[0]) + 1e-12
        ),
        "start2022_underwater_strictly_shorter": bool(
            not start_2022.empty
            and int(start_2022["longest_underwater_days__C_c9_plus_no_jd_true_carried"].iloc[0])
            < int(start_2022["longest_underwater_days__A_c9_frozen"].iloc[0])
        ),
        "b_and_c_not_bankrupt": bool(
            pivot["min_equity__B_no_jd_true_carried_leg"].gt(0.0).all()
            and pivot["min_equity__C_c9_plus_no_jd_true_carried"].gt(0.0).all()
        ),
        **cost_robust_checks,
    }
    return {
        "full_pass": bool(all(checks.values())),
        "checks": checks,
        "failed_checks": [name for name, passed in checks.items() if not passed],
        "fallback_order_count": fallback,
        "max_reconciliation_error": float(
            reconciliation[
                [
                    "max_abs_error_from_daily_pnl",
                    "max_abs_error_from_c9_plus_satellite",
                    "max_abs_c9_source_equity_error",
                ]
            ].max().max()
        ),
        "max_aggregate_broker10_margin_to_equity_pct": float(
            pd.to_numeric(daily["aggregate_broker10_margin_to_previous_equity_pct"], errors="coerce").max()
        ),
        "min_return_retention_pct": float(positive_base["return_retention_pct"].min()),
        "comparison_table": pivot.to_dict(orient="records"),
    }


def _run_dense_goal_audit(daily: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    upstream_tools = PROJECT_DIR / "research" / "lines" / "futures_trend_rebuilt_c9_15w_optimization" / "tools"
    if str(upstream_tools) not in sys.path:
        sys.path.insert(0, str(upstream_tools))
    import stage009_dense_start_goal_audit as stage009

    one = daily[daily["slippage_multiplier"].eq(1.0)].copy()
    frames: list[pd.DataFrame] = []
    for variant, column in (
        ("A_c9_frozen", "c9_account_equity"),
        ("C_c9_plus_no_jd_true_carried", "combined_equity"),
    ):
        frame = one[["requested_start_month", "date", column]].rename(columns={column: "equity"})
        frame["variant"] = variant
        frames.append(frame)
    return stage009._run_audit(pd.concat(frames, ignore_index=True))


def _mode_paths(mode: str) -> dict[str, Path]:
    stem = f"{OUTPUT_PREFIX}_{mode}_{MODEL_TAG}"
    return {
        "daily": OUTPUT_DIR / f"{stem}_daily.csv",
        "targets": OUTPUT_DIR / f"{stem}_target_ledger.csv",
        "orders": OUTPUT_DIR / f"{stem}_order_ledger.csv",
        "summary": OUTPUT_DIR / f"{stem}_summary.csv",
        "reconciliation": OUTPUT_DIR / f"{stem}_reconciliation.csv",
        "fill_sources": OUTPUT_DIR / f"{stem}_fill_sources.csv",
        "source_manifest": OUTPUT_DIR / f"{stem}_source_manifest.csv",
        "input_audit": OUTPUT_DIR / f"{stem}_input_audit.json",
        "decision": OUTPUT_DIR / f"{stem}_decision.json",
        "report": OUTPUT_DIR / f"{stem}_report.md",
        "chart": OUTPUT_DIR / f"{stem}_chart.png",
        "goal_aggregate": OUTPUT_DIR / f"{stem}_goal_aggregate.csv",
        "goal_to_final": OUTPUT_DIR / f"{stem}_goal_to_final.csv",
        "goal_fixed_horizon": OUTPUT_DIR / f"{stem}_goal_fixed_horizon.csv",
        "goal_worst_windows": OUTPUT_DIR / f"{stem}_goal_worst_windows.csv",
    }


def _plot(mode: str, daily: pd.DataFrame, path: Path) -> None:
    one = daily[daily["slippage_multiplier"].eq(1.0)].copy()
    fig, axes = plt.subplots(2, 1, figsize=(18, 11), sharex=True, constrained_layout=True)
    for start, group in one.groupby("requested_start_month", sort=True):
        alpha = 0.9 if mode == "canary" else 0.36
        axes[0].plot(group["date"], group["c9_account_equity"], color="#4b5563", linewidth=0.9, alpha=alpha)
        axes[0].plot(group["date"], group["combined_equity"], color="#0f766e", linewidth=1.0, alpha=alpha)
        axes[1].plot(group["date"], _drawdown_pct(group["c9_account_equity"]), color="#4b5563", linewidth=0.9, alpha=alpha)
        axes[1].plot(group["date"], _drawdown_pct(group["combined_equity"]), color="#0f766e", linewidth=1.0, alpha=alpha)
        if mode == "canary":
            axes[0].plot(group["date"], group["carried_leg_equity"], color="#b45309", linewidth=0.9, alpha=0.8)
    axes[0].axhline(CAPITAL, color="#111827", linestyle="--", linewidth=0.8)
    axes[0].set_title(f"Stage135 {mode}: frozen C9 (gray) vs no-JD true-carried overlay (green)")
    axes[0].set_ylabel("absolute account equity")
    axes[1].set_title("Drawdown: frozen C9 (gray) vs overlay (green)")
    axes[1].set_ylabel("drawdown %")
    axes[1].set_xlabel("date")
    for axis in axes:
        axis.grid(True, alpha=0.25)
    fig.savefig(path, dpi=170)
    plt.close(fig)


def _md_table(frame: pd.DataFrame, max_rows: int | None = None) -> str:
    if frame.empty:
        return "_无记录_"
    view = frame.head(max_rows).copy() if max_rows else frame.copy()
    return view.to_markdown(index=False)


def _write_report(
    mode: str,
    paths: dict[str, Path],
    input_audit: dict[str, Any],
    summary: pd.DataFrame,
    evidence: dict[str, Any],
    reconciliation: pd.DataFrame,
    fill_sources: pd.DataFrame,
) -> None:
    one = summary[summary["slippage_multiplier"].eq(1.0)].copy()
    lines = [
        f"# Stage135 no-JD Stage208 真成交账本降级证伪 {mode}",
        "",
        f"- 生成时间：`{datetime.now().replace(microsecond=0).isoformat()}`",
        f"- 输入就绪：`{input_audit['ready']}`；阻塞：`{','.join(input_audit['blocking_reasons'])}`",
        f"- 决策：`{evidence.get('decision', '')}`",
        "- 性质：真实卫星成交/持仓账本叠加冻结 C9 路径；不是完整单体正式引擎，不含 JD，不可直接晋级实盘。",
        "- B 臂仅表示 C 臂聚合保证金闸门实际承载的卫星腿单独权益，不是另一套独立保证金路径。",
        "",
        "## 固定口径",
        "",
        "- `mom_12m_skip1m / 63日 / 10%目标波动 / 正63日PnL / scale>=0.5 / broker10`。",
        "- 从原 long/short 名单仅删除 `jd.DCE`，不递补、不重排。",
        "- 成交优先上一交易日 `21:00-21:05` 第一根 open，否则当日 `09:00-09:05` 第一根 open；fallback 必须为0。",
        "- 组合聚合闸门使用当前 C9 exact margin、卫星 proposed margin 和上一日组合权益。",
        "",
        "## 1x 汇总",
        "",
        _md_table(
            one[
                [
                    "requested_start_month",
                    "arm",
                    "end_equity",
                    "total_return_pct",
                    "max_drawdown_pct",
                    "sharpe",
                    "longest_underwater_days",
                    "total_slippage",
                    "total_trade_count",
                    "nonzero_day_win_rate_pct",
                ]
            ]
        ),
        "",
        "## 闸门证据",
        "",
        "```json",
        json.dumps(_json_safe(evidence), ensure_ascii=False, indent=2),
        "```",
        "",
        "## 会计重算",
        "",
        _md_table(reconciliation),
        "",
        "## 成交来源",
        "",
        _md_table(fill_sources),
        "",
        "## 反思",
        "",
        "- 运行后过拟合判断：否。本轮只执行预声明单规格，没有根据结果回调参数、品种或方向。",
        "- 继续价值判断由硬闸门决定：canary 失败即关闭；通过才允许扩展，full 通过也只允许继续补 JD 精确逐日保证金。",
        "",
        "## 输出",
        "",
    ]
    lines.extend(f"- {name}：`{path}`" for name, path in paths.items() if path.exists())
    paths["report"].write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(mode: str) -> dict[str, Any]:
    if mode not in {"canary", "full"}:
        raise ValueError(f"invalid_mode:{mode}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    paths = _mode_paths(mode)
    if mode == "full":
        canary_path = _mode_paths("canary")["decision"]
        if not canary_path.exists():
            raise RuntimeError("full_requires_existing_canary_decision")
        canary = json.loads(canary_path.read_text(encoding="utf-8"))
        if not bool(canary.get("canary_pass", False)):
            raise RuntimeError("full_requires_passing_canary")
    starts = CANARY_STARTS if mode == "canary" else FULL_STARTS
    costs = (1.0,) if mode == "canary" else COST_MULTIPLIERS
    c9, _product_returns, signals, price_frame, frozen_daily, scale, exclusion = _load_inputs()
    input_audit = audit_inputs(
        c9,
        signals,
        price_frame,
        frozen_daily,
        scale,
        exclusion,
        starts=starts,
    )
    if not input_audit["ready"]:
        raise RuntimeError("stage135_input_blocked:" + ",".join(input_audit["blocking_reasons"]))
    minute_store = MinuteBarStore()
    daily_parts: list[pd.DataFrame] = []
    target_parts: list[pd.DataFrame] = []
    order_parts: list[pd.DataFrame] = []
    summary_parts: list[pd.DataFrame] = []
    reconciliation_rows: list[dict[str, Any]] = []
    for start in starts:
        curve = c9[c9["requested_start_month"].astype(str).eq(start)].copy()
        for cost in costs:
            daily, targets, orders = simulate_window(
                curve,
                price_frame,
                signals,
                scale,
                requested_start_month=start,
                minute_loader=minute_store,
                slippage_multiplier=cost,
            )
            recon = reconcile_combo_daily(daily, capital=CAPITAL)
            reconciliation_rows.append(
                {"requested_start_month": start, "slippage_multiplier": cost, **recon}
            )
            daily_parts.append(daily)
            target_parts.append(targets)
            if not orders.empty:
                order_parts.append(orders)
            summary_parts.append(summarize_arms(daily))
    daily_all = pd.concat(daily_parts, ignore_index=True)
    targets_all = pd.concat(target_parts, ignore_index=True)
    orders_all = pd.concat(order_parts, ignore_index=True) if order_parts else pd.DataFrame()
    summary_all = pd.concat(summary_parts, ignore_index=True)
    reconciliation = pd.DataFrame(reconciliation_rows)
    if orders_all.empty:
        fill_sources = pd.DataFrame(columns=["price_source", "order_count", "contract_count", "delta_abs_sum"])
    else:
        fill = orders_all.copy()
        fill["delta_abs"] = pd.to_numeric(fill["delta_lots"], errors="coerce").abs()
        fill_sources = (
            fill.groupby("price_source", as_index=False)
            .agg(
                order_count=("contract", "size"),
                contract_count=("contract", "nunique"),
                delta_abs_sum=("delta_abs", "sum"),
            )
            .sort_values("order_count", ascending=False)
        )

    if mode == "canary":
        evidence = build_canary_evidence(
            summary_all,
            reconciliation=reconciliation.iloc[0].to_dict(),
            daily=daily_all,
            orders=orders_all,
        )
        gate = evaluate_canary(evidence)
        evidence.update(gate)
        evidence["decision"] = (
            "stage135_canary_pass_expand_full_degraded_audit"
            if gate["canary_pass"]
            else "stage135_canary_failed_close_current_stage208_route"
        )
    else:
        evidence = build_full_evidence(summary_all, reconciliation, daily_all, orders_all)
        evidence["decision"] = (
            "stage135_full_degraded_pass_pursue_exact_jd_margin_only"
            if evidence["full_pass"]
            else "stage135_full_degraded_failed_close_current_stage208_route"
        )

    decision = {
        "stage": STAGE,
        "line_id": LINE_ID,
        "model_tag": MODEL_TAG,
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "mode": mode,
        "capital": CAPITAL,
        "analysis_end": ANALYSIS_END.date().isoformat(),
        "requested_starts": list(starts),
        "cost_multipliers": list(costs),
        "spec": SPEC_NAME,
        "excluded_product": EXCLUDED_PRODUCT,
        "target_vol": TARGET_VOL,
        "vol_lookback": VOL_LOOKBACK,
        "round_half_threshold": ROUND_HALF_THRESHOLD,
        "broker_margin_multiplier": BROKER_MARGIN_MULTIPLIER,
        "is_degraded_no_jd": True,
        "is_full_monolithic_engine": False,
        "is_one_way_overlay_on_frozen_c9": True,
        "formal_live_strategy_changed": False,
        "order_api_called": False,
        "ctp_connected": False,
        "input_audit": input_audit,
        **evidence,
        "outputs": {name: str(path) for name, path in paths.items()},
    }

    daily_all.to_csv(paths["daily"], index=False, encoding="utf-8-sig")
    targets_all.to_csv(paths["targets"], index=False, encoding="utf-8-sig")
    orders_all.to_csv(paths["orders"], index=False, encoding="utf-8-sig")
    summary_all.to_csv(paths["summary"], index=False, encoding="utf-8-sig")
    reconciliation.to_csv(paths["reconciliation"], index=False, encoding="utf-8-sig")
    fill_sources.to_csv(paths["fill_sources"], index=False, encoding="utf-8-sig")
    build_source_manifest(orders_all).to_csv(paths["source_manifest"], index=False, encoding="utf-8-sig")
    paths["input_audit"].write_text(json.dumps(_json_safe(input_audit), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    paths["decision"].write_text(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if mode == "full":
        aggregate, to_final, fixed_horizon, worst = _run_dense_goal_audit(daily_all)
        aggregate.to_csv(paths["goal_aggregate"], index=False, encoding="utf-8-sig")
        to_final.to_csv(paths["goal_to_final"], index=False, encoding="utf-8-sig")
        fixed_horizon.to_csv(paths["goal_fixed_horizon"], index=False, encoding="utf-8-sig")
        worst.to_csv(paths["goal_worst_windows"], index=False, encoding="utf-8-sig")
    _plot(mode, daily_all, paths["chart"])
    _write_report(mode, paths, input_audit, summary_all, decision, reconciliation, fill_sources)
    return decision


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("canary", "full"), default="canary")
    args = parser.parse_args()
    decision = run(args.mode)
    print(json.dumps(_json_safe(decision), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
