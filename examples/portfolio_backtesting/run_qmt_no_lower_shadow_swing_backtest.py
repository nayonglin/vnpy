from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = PROJECT_DIR / "backtest_outputs"
DEFAULT_UNIVERSE_PATH: Path = (
    OUTPUT_DIR / "qmt_roll_full_market_tradable_universe_eligible_full_market_tradable_universe_v1.csv"
)
DEFAULT_MAPPING_PATH: Path = OUTPUT_DIR / "tqsdk_all_futures_main_contract_mapping_2010_2026_04.csv"

MODEL_TAG: str = "no_lower_shadow_swing_v1"
DEFAULT_OUTPUT_PREFIX: str = "qmt_no_lower_shadow_swing_v1"
DEFAULT_SIGNAL_VARIANT: str = "strict"
SIGNAL_VARIANTS: tuple[str, ...] = ("strict", "lower_shadow_1tick", "lower_shadow_2tick_body10")
DEFAULT_START: datetime = datetime(2020, 1, 1)
DEFAULT_END: datetime = datetime(2026, 4, 30)
DEFAULT_CAPITAL: float = 500_000.0
DEFAULT_RISK_RATIO: float = 0.005
DEFAULT_MAX_CONCURRENT_POSITIONS: int = 8
MAX_CAPITAL_USAGE_RATIO: float = 0.90
MAX_SINGLE_TRADE_CAPITAL_USAGE_RATIO: float = 0.70
ANNUAL_TRADING_DAYS: int = 240


@dataclass(frozen=True)
class MarketBar:
    date: pd.Timestamp
    vt_symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


@dataclass
class Position:
    product_vt_symbol: str
    contract_vt_symbol: str
    entry_date: pd.Timestamp
    entry_price: float
    stop_price: float
    volume: int
    original_volume: int
    size: int
    pricetick: float
    margin_ratio: float
    rate: float
    slippage: float
    half_exit_done: bool = False
    lifecycle_pnl: float = 0.0
    lifecycle_slippage: float = 0.0
    lifecycle_commission: float = 0.0


@dataclass(frozen=True)
class BacktestConfig:
    start: datetime = DEFAULT_START
    end: datetime = DEFAULT_END
    capital: float = DEFAULT_CAPITAL
    risk_ratio: float = DEFAULT_RISK_RATIO
    max_concurrent_positions: int = DEFAULT_MAX_CONCURRENT_POSITIONS
    mapping_path: Path = DEFAULT_MAPPING_PATH
    universe_path: Path = DEFAULT_UNIVERSE_PATH
    output_prefix: str = DEFAULT_OUTPUT_PREFIX
    signal_variant: str = DEFAULT_SIGNAL_VARIANT
    save_outputs: bool = True


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(result) or math.isinf(result):
        return default
    return result


def _normalize_date(value: object) -> pd.Timestamp:
    return pd.Timestamp(value).tz_localize(None).normalize()


def _tick_units(price: float, pricetick: float) -> int:
    tick = pricetick if pricetick > 0 else 1.0
    return int(round(float(price) / tick))


def is_strict_no_lower_shadow_rising(bar: MarketBar, pricetick: float) -> bool:
    """Strict signal bar: rounded open equals low, and close is above open."""
    if min(bar.open, bar.low, bar.close) <= 0:
        return False
    open_units = _tick_units(bar.open, pricetick)
    low_units = _tick_units(bar.low, pricetick)
    close_units = _tick_units(bar.close, pricetick)
    return open_units == low_units and close_units > open_units


def is_no_lower_shadow_rising(bar: MarketBar, pricetick: float, signal_variant: str = DEFAULT_SIGNAL_VARIANT) -> bool:
    if min(bar.open, bar.low, bar.close) <= 0:
        return False
    open_units = _tick_units(bar.open, pricetick)
    low_units = _tick_units(bar.low, pricetick)
    close_units = _tick_units(bar.close, pricetick)
    if close_units <= open_units:
        return False

    lower_shadow = max(0.0, float(bar.open) - float(bar.low))
    if signal_variant == "strict":
        return open_units == low_units
    if signal_variant == "lower_shadow_1tick":
        return max(0, open_units - low_units) <= 1
    if signal_variant == "lower_shadow_2tick_body10":
        body = float(bar.close) - float(bar.open)
        if body <= 0:
            return False
        return lower_shadow <= min(2.0 * float(pricetick), 0.10 * body) + 1e-12
    raise ValueError(f"Unsupported signal_variant: {signal_variant}")


def calculate_position_size(
    *,
    equity: float,
    risk_ratio: float,
    entry_price: float,
    stop_price: float,
    size: int,
    pricetick: float,
    margin_ratio: float,
    active_margin: float,
    capital_usage_ratio: float = MAX_CAPITAL_USAGE_RATIO,
    single_trade_capital_usage_ratio: float = MAX_SINGLE_TRADE_CAPITAL_USAGE_RATIO,
) -> dict[str, Any]:
    risk_amount = max(0.0, equity * risk_ratio)
    risk_distance = entry_price - stop_price
    min_risk_per_contract = max(pricetick * size, 1.0)
    risk_per_contract = max(risk_distance * size, min_risk_per_contract)
    margin_per_contract = entry_price * size * max(margin_ratio, 0.0)
    allowed_margin = max(0.0, equity * capital_usage_ratio - active_margin)
    single_trade_margin = max(0.0, equity * single_trade_capital_usage_ratio)

    contracts_by_risk = int(risk_amount // risk_per_contract) if risk_per_contract > 0 else 0
    contracts_by_margin = int(allowed_margin // margin_per_contract) if margin_per_contract > 0 else 0
    contracts_by_single_trade_cap = int(single_trade_margin // margin_per_contract) if margin_per_contract > 0 else 0
    selected_volume = max(0, min(contracts_by_risk, contracts_by_margin, contracts_by_single_trade_cap))

    return {
        "risk_amount": risk_amount,
        "risk_distance": risk_distance,
        "risk_per_contract": risk_per_contract,
        "margin_per_contract": margin_per_contract,
        "allowed_margin": allowed_margin,
        "single_trade_margin": single_trade_margin,
        "contracts_by_risk": contracts_by_risk,
        "contracts_by_margin": contracts_by_margin,
        "contracts_by_single_trade_cap": contracts_by_single_trade_cap,
        "selected_volume": selected_volume,
    }


def update_trailing_stop_long(current_stop: float, previous_low: float) -> float:
    return max(float(current_stop), float(previous_low))


def stop_exit_price_long(bar: MarketBar, stop_price: float) -> float | None:
    if stop_price <= 0:
        return None
    if bar.open <= stop_price:
        return float(bar.open)
    if bar.low <= stop_price:
        return float(stop_price)
    return None


def first_day_half_exit_volume(volume: int) -> int:
    return max(0, int(math.floor(max(0, int(volume)) * 0.5)))


def _trade_cost(price: float, volume: int, *, size: int, rate: float, slippage: float) -> tuple[float, float, float]:
    turnover = float(price) * int(volume) * int(size)
    commission_cash = turnover * max(0.0, float(rate))
    slippage_cash = max(0.0, float(slippage)) * int(size) * int(volume)
    return commission_cash + slippage_cash, commission_cash, slippage_cash


def _parse_vt_symbol(vt_symbol: str) -> tuple[str, Any]:
    from vnpy.trader.constant import Exchange

    symbol, exchange_text = vt_symbol.split(".", 1)
    return symbol, Exchange(exchange_text)


def _load_bar_cache(
    vt_symbols: list[str],
    *,
    start: datetime,
    end: datetime,
) -> dict[str, dict[pd.Timestamp, MarketBar]]:
    from vnpy.trader.constant import Interval
    from vnpy.trader.database import get_database

    database = get_database()
    cache: dict[str, dict[pd.Timestamp, MarketBar]] = {}
    for vt_symbol in sorted(set(vt_symbols)):
        symbol, exchange = _parse_vt_symbol(vt_symbol)
        rows: dict[pd.Timestamp, MarketBar] = {}
        for bar in database.load_bar_data(symbol, exchange, Interval.DAILY, start, end):
            date = _normalize_date(bar.datetime)
            rows[date] = MarketBar(
                date=date,
                vt_symbol=vt_symbol,
                open=float(bar.open_price),
                high=float(bar.high_price),
                low=float(bar.low_price),
                close=float(bar.close_price),
                volume=float(getattr(bar, "volume", 0.0) or 0.0),
            )
        cache[vt_symbol] = rows
    return cache


def _bar(cache: dict[str, dict[pd.Timestamp, MarketBar]], vt_symbol: str, date: pd.Timestamp) -> MarketBar | None:
    return cache.get(vt_symbol, {}).get(_normalize_date(date))


def _load_inputs(config: BacktestConfig) -> tuple[pd.DataFrame, dict[str, Any], dict[str, dict[pd.Timestamp, MarketBar]]]:
    from main_contract_mapping import build_contract_metadata, load_product_universe_symbols
    from qmt_backtest_runtime_guard import assert_stage196_database_sentinels

    assert_stage196_database_sentinels()
    supported_symbols = load_product_universe_symbols(config.universe_path)
    metadata = build_contract_metadata(mapping_path=config.mapping_path, supported_symbols=supported_symbols)

    preload_start = config.start - timedelta(days=30)
    mapping = pd.read_csv(config.mapping_path)
    mapping["date"] = pd.to_datetime(mapping["date"]).dt.tz_localize(None).dt.normalize()
    mapping["main_contract_vt"] = mapping["main_contract_vt"].fillna("").astype(str)
    mapping = mapping[
        mapping["continuous_symbol_vt"].isin(set(metadata["product_symbols"]))
        & (mapping["date"] >= pd.Timestamp(preload_start))
        & (mapping["date"] <= pd.Timestamp(config.end))
        & (mapping["main_contract_vt"] != "")
    ].copy()
    mapping.sort_values(["continuous_symbol_vt", "date"], inplace=True)

    contracts = sorted(set(mapping["main_contract_vt"].astype(str)))
    bar_cache = _load_bar_cache(contracts, start=preload_start, end=config.end)
    return mapping, metadata, bar_cache


def _mapping_indexes(mapping: pd.DataFrame) -> tuple[dict[str, list[pd.Timestamp]], dict[tuple[str, pd.Timestamp], str]]:
    dates_by_product: dict[str, list[pd.Timestamp]] = {}
    contract_by_product_date: dict[tuple[str, pd.Timestamp], str] = {}
    for product, group in mapping.groupby("continuous_symbol_vt", sort=True):
        dates = [_normalize_date(value) for value in group["date"].tolist()]
        dates_by_product[str(product)] = dates
        for row in group.itertuples(index=False):
            contract_by_product_date[(str(row.continuous_symbol_vt), _normalize_date(row.date))] = str(
                row.main_contract_vt
            )
    return dates_by_product, contract_by_product_date


def _active_margin(positions: dict[str, Position], bar_cache: dict[str, dict[pd.Timestamp, MarketBar]], date: pd.Timestamp) -> float:
    total = 0.0
    for position in positions.values():
        bar = _bar(bar_cache, position.contract_vt_symbol, date)
        price = bar.close if bar is not None else position.entry_price
        total += price * position.size * position.volume * position.margin_ratio
    return total


def _position_unrealized(position: Position, bar_cache: dict[str, dict[pd.Timestamp, MarketBar]], date: pd.Timestamp) -> float:
    bar = _bar(bar_cache, position.contract_vt_symbol, date)
    price = bar.close if bar is not None else position.entry_price
    return (price - position.entry_price) * position.size * position.volume


class NoLowerShadowSwingBacktester:
    def __init__(
        self,
        config: BacktestConfig,
        mapping: pd.DataFrame,
        metadata: dict[str, Any],
        bar_cache: dict[str, dict[pd.Timestamp, MarketBar]],
    ) -> None:
        self.config = config
        self.mapping = mapping
        self.metadata = metadata
        self.bar_cache = bar_cache
        self.product_dates, self.contract_by_product_date = _mapping_indexes(mapping)
        self.priceticks: dict[str, float] = metadata["priceticks"]
        self.sizes: dict[str, int] = metadata["sizes"]
        self.margin_ratios: dict[str, float] = metadata["margin_ratios"]
        self.rates: dict[str, float] = metadata["rates"]
        self.slippages: dict[str, float] = metadata["slippages"]

        self.cash = float(config.capital)
        self.positions: dict[str, Position] = {}
        self.daily_rows: list[dict[str, Any]] = []
        self.trade_rows: list[dict[str, Any]] = []
        self.position_rows: list[dict[str, Any]] = []
        self.candidate_rows: list[dict[str, Any]] = []
        self.roundtrip_rows: list[dict[str, Any]] = []

    def run(self) -> dict[str, Any]:
        all_dates = sorted(
            {
                date
                for dates in self.product_dates.values()
                for date in dates
                if pd.Timestamp(self.config.start) <= date <= pd.Timestamp(self.config.end)
            }
        )
        previous_equity = float(self.config.capital)
        for date in all_dates:
            trade_count_before = len(self.trade_rows)
            self._prepare_stops_before_open(date)
            self._open_new_positions(date, previous_equity)
            self._process_open_positions(date)
            daily = self._build_daily_row(date, previous_equity, len(self.trade_rows) - trade_count_before)
            self.daily_rows.append(daily)
            previous_equity = float(daily["balance"])
            self._record_end_positions(date)
        return self._statistics()

    def _prepare_stops_before_open(self, date: pd.Timestamp) -> None:
        for product, position in list(self.positions.items()):
            if position.entry_date >= date:
                continue
            product_dates = self.product_dates.get(product, [])
            if date not in product_dates:
                continue
            index = product_dates.index(date)
            if index <= 0:
                continue
            previous_date = product_dates[index - 1]
            previous_contract = self.contract_by_product_date.get((product, previous_date), "")
            if previous_contract != position.contract_vt_symbol:
                continue
            previous_bar = _bar(self.bar_cache, position.contract_vt_symbol, previous_date)
            if previous_bar is None:
                continue
            position.stop_price = update_trailing_stop_long(position.stop_price, previous_bar.low)

    def _open_new_positions(self, date: pd.Timestamp, equity_before_open: float) -> None:
        if equity_before_open <= 0:
            return

        active_at_open = len(self.positions)
        active_margin = _active_margin(self.positions, self.bar_cache, date)
        for product in sorted(self.product_dates):
            if product in self.positions:
                continue
            product_dates = self.product_dates[product]
            if date not in product_dates:
                continue
            index = product_dates.index(date)
            if index < 2:
                continue

            signal_date_1 = product_dates[index - 2]
            signal_date_2 = product_dates[index - 1]
            entry_contract = self.contract_by_product_date.get((product, date), "")
            signal_contract_1 = self.contract_by_product_date.get((product, signal_date_1), "")
            signal_contract_2 = self.contract_by_product_date.get((product, signal_date_2), "")
            if not entry_contract or not signal_contract_1 or not signal_contract_2:
                continue

            pricetick = float(self.priceticks.get(entry_contract, 1.0) or 1.0)
            signal_bar_1 = _bar(self.bar_cache, signal_contract_1, signal_date_1)
            signal_bar_2 = _bar(self.bar_cache, signal_contract_2, signal_date_2)
            entry_bar = _bar(self.bar_cache, entry_contract, date)
            if signal_bar_1 is None or signal_bar_2 is None:
                continue
            if not (
                is_no_lower_shadow_rising(signal_bar_1, pricetick, self.config.signal_variant)
                and is_no_lower_shadow_rising(signal_bar_2, pricetick, self.config.signal_variant)
            ):
                continue

            base_row = {
                "candidate_index": len(self.candidate_rows) + 1,
                "date": date.date().isoformat(),
                "product_vt_symbol": product,
                "signal_date_1": signal_date_1.date().isoformat(),
                "signal_date_2": signal_date_2.date().isoformat(),
                "signal_contract_1": signal_contract_1,
                "signal_contract_2": signal_contract_2,
                "entry_contract_vt_symbol": entry_contract,
                "signal": f"two_{self.config.signal_variant}_no_lower_shadow_rising",
                "signal_variant": self.config.signal_variant,
                "direction": "long",
                "estimated_equity": equity_before_open,
                "active_positions_before": active_at_open,
                "max_concurrent_positions": self.config.max_concurrent_positions,
            }
            if signal_contract_1 != entry_contract or signal_contract_2 != entry_contract:
                self._record_candidate(base_row, "skipped", "rollover_between_signal_and_entry")
                continue
            if entry_bar is None:
                self._record_candidate(base_row, "skipped", "missing_entry_bar")
                continue
            if active_at_open >= self.config.max_concurrent_positions:
                self._record_candidate(base_row, "skipped", "max_concurrent_positions")
                continue

            entry_price = float(entry_bar.open)
            stop_price = float(signal_bar_2.low)
            size = int(self.sizes.get(entry_contract, 1) or 1)
            margin_ratio = float(self.margin_ratios.get(entry_contract, 0.15) or 0.15)
            sizing = calculate_position_size(
                equity=equity_before_open,
                risk_ratio=self.config.risk_ratio,
                entry_price=entry_price,
                stop_price=stop_price,
                size=size,
                pricetick=pricetick,
                margin_ratio=margin_ratio,
                active_margin=active_margin,
            )
            base_row.update(
                {
                    "entry_price": entry_price,
                    "stop_price": stop_price,
                    "stop_distance": entry_price - stop_price,
                    "size": size,
                    "pricetick": pricetick,
                    "margin_ratio": margin_ratio,
                    **sizing,
                }
            )
            if entry_price <= stop_price:
                self._record_candidate(base_row, "skipped", "entry_open_not_above_stop")
                continue
            volume = int(sizing["selected_volume"])
            if volume <= 0:
                reason = "risk_budget_below_one_contract"
                if int(sizing["contracts_by_risk"]) > 0 and int(sizing["contracts_by_margin"]) <= 0:
                    reason = "margin_budget_below_one_contract"
                elif int(sizing["contracts_by_risk"]) > 0 and int(sizing["contracts_by_single_trade_cap"]) <= 0:
                    reason = "single_trade_cap_below_one_contract"
                self._record_candidate(base_row, "skipped", reason)
                continue

            rate = float(self.rates.get(entry_contract, 0.0) or 0.0)
            slippage = float(self.slippages.get(entry_contract, pricetick) or pricetick)
            cost, commission_cash, slippage_cash = _trade_cost(
                entry_price,
                volume,
                size=size,
                rate=rate,
                slippage=slippage,
            )
            self.cash -= cost
            position = Position(
                product_vt_symbol=product,
                contract_vt_symbol=entry_contract,
                entry_date=date,
                entry_price=entry_price,
                stop_price=stop_price,
                volume=volume,
                original_volume=volume,
                size=size,
                pricetick=pricetick,
                margin_ratio=margin_ratio,
                rate=rate,
                slippage=slippage,
                lifecycle_pnl=-cost,
                lifecycle_slippage=slippage_cash,
                lifecycle_commission=commission_cash,
            )
            self.positions[product] = position
            active_at_open += 1
            active_margin += float(sizing["margin_per_contract"]) * volume
            base_row["planned_half_exit_volume"] = first_day_half_exit_volume(volume)
            self._record_candidate(base_row, "opened", "")
            self._record_trade(
                date=date,
                product=product,
                contract=entry_contract,
                direction="Long",
                offset="Open",
                reason="entry_open",
                price=entry_price,
                volume=volume,
                commission=commission_cash,
                slippage_cash=slippage_cash,
                pnl=0.0,
            )

    def _record_candidate(self, row: dict[str, Any], status: str, reason: str) -> None:
        item = dict(row)
        item["candidate_status"] = status
        item["skip_reason"] = reason
        self.candidate_rows.append(item)

    def _process_open_positions(self, date: pd.Timestamp) -> None:
        for product, position in list(self.positions.items()):
            target_contract = self.contract_by_product_date.get((product, date), "")
            bar = _bar(self.bar_cache, position.contract_vt_symbol, date)
            if target_contract and target_contract != position.contract_vt_symbol:
                exit_bar = bar or _bar(self.bar_cache, target_contract, date)
                if exit_bar is not None:
                    self._close_position(product, position, exit_bar.close, date, "rollover_forced_exit")
                continue
            if bar is None:
                continue

            exit_price = stop_exit_price_long(bar, position.stop_price)
            if exit_price is not None:
                reason = "long_initial_stop" if position.entry_date == date else "long_trailing_stop"
                if bar.open <= position.stop_price:
                    reason = "long_gap_stop"
                self._close_position(product, position, exit_price, date, reason)
                continue

            if position.entry_date == date and not position.half_exit_done:
                reduce_volume = first_day_half_exit_volume(position.volume)
                position.half_exit_done = True
                if reduce_volume <= 0:
                    continue
                self._reduce_position(product, position, reduce_volume, bar.close, date, "first_day_half_exit")

    def _reduce_position(
        self,
        product: str,
        position: Position,
        volume: int,
        price: float,
        date: pd.Timestamp,
        reason: str,
    ) -> None:
        close_volume = min(max(0, int(volume)), position.volume)
        if close_volume <= 0:
            return
        cost, commission_cash, slippage_cash = _trade_cost(
            price,
            close_volume,
            size=position.size,
            rate=position.rate,
            slippage=position.slippage,
        )
        pnl = (price - position.entry_price) * position.size * close_volume
        net_pnl = pnl - cost
        self.cash += net_pnl
        position.lifecycle_pnl += net_pnl
        position.lifecycle_slippage += slippage_cash
        position.lifecycle_commission += commission_cash
        position.volume -= close_volume
        self._record_trade(
            date=date,
            product=product,
            contract=position.contract_vt_symbol,
            direction="Short",
            offset="Close",
            reason=reason,
            price=price,
            volume=close_volume,
            commission=commission_cash,
            slippage_cash=slippage_cash,
            pnl=net_pnl,
        )
        if position.volume <= 0:
            self._record_roundtrip(position, date, reason)
            self.positions.pop(product, None)

    def _close_position(self, product: str, position: Position, price: float, date: pd.Timestamp, reason: str) -> None:
        self._reduce_position(product, position, position.volume, price, date, reason)

    def _record_roundtrip(self, position: Position, exit_date: pd.Timestamp, exit_reason: str) -> None:
        self.roundtrip_rows.append(
            {
                "product_vt_symbol": position.product_vt_symbol,
                "contract_vt_symbol": position.contract_vt_symbol,
                "entry_date": position.entry_date.date().isoformat(),
                "exit_date": exit_date.date().isoformat(),
                "exit_reason": exit_reason,
                "original_volume": position.original_volume,
                "entry_price": position.entry_price,
                "final_stop_price": position.stop_price,
                "net_pnl": position.lifecycle_pnl,
                "slippage": position.lifecycle_slippage,
                "commission": position.lifecycle_commission,
                "holding_days": int((exit_date - position.entry_date).days) + 1,
            }
        )

    def _record_trade(
        self,
        *,
        date: pd.Timestamp,
        product: str,
        contract: str,
        direction: str,
        offset: str,
        reason: str,
        price: float,
        volume: int,
        commission: float,
        slippage_cash: float,
        pnl: float,
    ) -> None:
        self.trade_rows.append(
            {
                "trade_index": len(self.trade_rows) + 1,
                "datetime": date.isoformat(),
                "date": date.date().isoformat(),
                "product_vt_symbol": product,
                "vt_symbol": contract,
                "direction": direction,
                "offset": offset,
                "reason": reason,
                "price": price,
                "volume": int(volume),
                "turnover": price * volume,
                "commission": commission,
                "slippage": slippage_cash,
                "net_pnl": pnl,
            }
        )

    def _build_daily_row(self, date: pd.Timestamp, previous_equity: float, trade_count: int) -> dict[str, Any]:
        unrealized = sum(_position_unrealized(position, self.bar_cache, date) for position in self.positions.values())
        balance = self.cash + unrealized
        net_pnl = balance - previous_equity
        active_margin = _active_margin(self.positions, self.bar_cache, date)
        peak = max([self.config.capital, *[float(row["balance"]) for row in self.daily_rows], balance])
        drawdown = balance - peak
        drawdown_pct = drawdown / peak * 100.0 if peak > 0 else 0.0
        todays_trades = [row for row in self.trade_rows if row["date"] == date.date().isoformat()]
        return {
            "date": date.date().isoformat(),
            "balance": balance,
            "net_pnl": net_pnl,
            "return_pct": net_pnl / previous_equity * 100.0 if previous_equity > 0 else 0.0,
            "drawdown": drawdown,
            "drawdown_pct": drawdown_pct,
            "active_positions": len(self.positions),
            "active_margin": active_margin,
            "trade_count": trade_count,
            "turnover": sum(float(row["turnover"]) for row in todays_trades),
            "commission": sum(float(row["commission"]) for row in todays_trades),
            "slippage": sum(float(row["slippage"]) for row in todays_trades),
        }

    def _record_end_positions(self, date: pd.Timestamp) -> None:
        for position in self.positions.values():
            bar = _bar(self.bar_cache, position.contract_vt_symbol, date)
            close_price = bar.close if bar is not None else position.entry_price
            self.position_rows.append(
                {
                    "date": date.date().isoformat(),
                    "product_vt_symbol": position.product_vt_symbol,
                    "contract_vt_symbol": position.contract_vt_symbol,
                    "direction": "long",
                    "volume": position.volume,
                    "entry_date": position.entry_date.date().isoformat(),
                    "entry_price": position.entry_price,
                    "close_price": close_price,
                    "stop_price": position.stop_price,
                    "unrealized_pnl": (close_price - position.entry_price) * position.size * position.volume,
                    "half_exit_done": int(position.half_exit_done),
                }
            )

    def _statistics(self) -> dict[str, Any]:
        daily = pd.DataFrame(self.daily_rows)
        trades = pd.DataFrame(self.trade_rows)
        roundtrips = pd.DataFrame(self.roundtrip_rows)
        if daily.empty:
            end_balance = self.config.capital
            returns = pd.Series(dtype="float64")
            max_drawdown = 0.0
            max_dd_percent = 0.0
        else:
            end_balance = float(daily["balance"].iloc[-1])
            returns = pd.to_numeric(daily["return_pct"], errors="coerce").fillna(0.0) / 100.0
            max_drawdown = float(pd.to_numeric(daily["drawdown"], errors="coerce").min())
            max_dd_percent = float(pd.to_numeric(daily["drawdown_pct"], errors="coerce").min())
        std = float(returns.std(ddof=0)) if not returns.empty else 0.0
        sharpe = float(returns.mean() / std * math.sqrt(ANNUAL_TRADING_DAYS)) if std > 0 else 0.0
        wins = int((roundtrips["net_pnl"] > 0).sum()) if not roundtrips.empty else 0
        total_roundtrips = int(len(roundtrips))
        win_ratio = wins / total_roundtrips * 100.0 if total_roundtrips else 0.0
        stats = {
            "model_tag": MODEL_TAG,
            "analysis_start": self.config.start.date().isoformat(),
            "analysis_end": self.config.end.date().isoformat(),
            "capital": self.config.capital,
            "risk_ratio": self.config.risk_ratio,
            "signal_variant": self.config.signal_variant,
            "end_balance": end_balance,
            "total_return_pct": (end_balance / self.config.capital - 1.0) * 100.0 if self.config.capital else 0.0,
            "max_drawdown": max_drawdown,
            "max_dd_percent": max_dd_percent,
            "sharpe_ratio": sharpe,
            "total_trade_count": int(len(trades)),
            "round_trip_count": total_roundtrips,
            "win_count": wins,
            "win_ratio_pct": win_ratio,
            "total_slippage": float(trades["slippage"].sum()) if not trades.empty else 0.0,
            "total_commission": float(trades["commission"].sum()) if not trades.empty else 0.0,
            "candidate_count": int(len(self.candidate_rows)),
            "opened_candidate_count": int(
                sum(1 for row in self.candidate_rows if row.get("candidate_status") == "opened")
            ),
            "open_positions_end": int(len(self.positions)),
        }
        return stats

    def output_frames(self) -> dict[str, pd.DataFrame]:
        return {
            "daily": pd.DataFrame(self.daily_rows),
            "trades": pd.DataFrame(self.trade_rows),
            "positions": pd.DataFrame(self.position_rows),
            "candidates": pd.DataFrame(self.candidate_rows),
            "roundtrips": pd.DataFrame(self.roundtrip_rows),
        }


def _summary_table(df: pd.DataFrame, group_column: str) -> pd.DataFrame:
    if df.empty or group_column not in df.columns:
        return pd.DataFrame()
    grouped = df.groupby(group_column, dropna=False)
    return grouped.agg(
        net_pnl=("net_pnl", "sum"),
        round_trip_count=("net_pnl", "size"),
        win_ratio_pct=("net_pnl", lambda values: float((values > 0).mean() * 100.0)),
        avg_holding_days=("holding_days", "mean"),
        slippage=("slippage", "sum"),
        commission=("commission", "sum"),
    ).reset_index()


def _write_outputs(config: BacktestConfig, stats: dict[str, Any], frames: dict[str, pd.DataFrame]) -> dict[str, str]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    prefix = config.output_prefix
    paths: dict[str, str] = {}
    for name, frame in frames.items():
        path = OUTPUT_DIR / f"{prefix}_{name}.csv"
        frame.to_csv(path, index=False, encoding="utf-8-sig")
        paths[name] = str(path)

    stats_path = OUTPUT_DIR / f"{prefix}_statistics.json"
    stats_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    paths["statistics"] = str(stats_path)

    roundtrips = frames["roundtrips"].copy()
    if not roundtrips.empty:
        roundtrips["entry_year"] = pd.to_datetime(roundtrips["entry_date"]).dt.year
    product_summary = _summary_table(roundtrips, "product_vt_symbol")
    year_summary = _summary_table(roundtrips, "entry_year")
    exit_summary = _summary_table(roundtrips, "exit_reason")

    for name, frame in {
        "product_summary": product_summary,
        "year_summary": year_summary,
        "exit_reason_summary": exit_summary,
    }.items():
        path = OUTPUT_DIR / f"{prefix}_{name}.csv"
        frame.to_csv(path, index=False, encoding="utf-8-sig")
        paths[name] = str(path)

    report_path = OUTPUT_DIR / f"{prefix}_attribution_report.md"
    report_path.write_text(_build_report(stats, product_summary, year_summary, exit_summary), encoding="utf-8")
    paths["report"] = str(report_path)
    return paths


def _markdown_table(df: pd.DataFrame, max_rows: int = 12) -> str:
    if df.empty:
        return "_empty_"
    view = df.head(max_rows).copy()
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(lambda value: f"{value:.4f}")
    header = "| " + " | ".join(view.columns) + " |"
    separator = "| " + " | ".join(["---"] * len(view.columns)) + " |"
    rows = ["| " + " | ".join(str(value) for value in row) + " |" for row in view.to_numpy()]
    return "\n".join([header, separator, *rows])


def _build_report(
    stats: dict[str, Any],
    product_summary: pd.DataFrame,
    year_summary: pd.DataFrame,
    exit_summary: pd.DataFrame,
) -> str:
    return "\n".join(
        [
            "# 期货无下影线波段 v1 归因报告",
            "",
            "## 总览",
            "",
            f"- 期末权益：`{stats['end_balance']:,.2f}`",
            f"- 总收益：`{stats['total_return_pct']:.4f}%`",
            f"- 最大回撤：`{stats['max_dd_percent']:.4f}%`",
            f"- Sharpe：`{stats['sharpe_ratio']:.4f}`",
            f"- 候选数/开仓数：`{stats['candidate_count']}` / `{stats['opened_candidate_count']}`",
            f"- 总交易次数：`{stats['total_trade_count']}`",
            f"- 胜率：`{stats['win_ratio_pct']:.4f}%`",
            f"- 总滑点：`{stats['total_slippage']:,.2f}`",
            "",
            "## 年度归因",
            "",
            _markdown_table(year_summary),
            "",
            "## 品种归因",
            "",
            _markdown_table(product_summary.sort_values("net_pnl", ascending=False) if not product_summary.empty else product_summary),
            "",
            "## 退出原因归因",
            "",
            _markdown_table(exit_summary),
            "",
        ]
    )


def run_backtest(config: BacktestConfig) -> tuple[dict[str, Any], dict[str, pd.DataFrame], dict[str, str]]:
    mapping, metadata, bar_cache = _load_inputs(config)
    backtester = NoLowerShadowSwingBacktester(config, mapping, metadata, bar_cache)
    stats = backtester.run()
    frames = backtester.output_frames()
    paths = _write_outputs(config, stats, frames) if config.save_outputs else {}
    return stats, frames, paths


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run no-lower-shadow futures swing v1 backtest.")
    parser.add_argument("--start", default=DEFAULT_START.date().isoformat())
    parser.add_argument("--end", default=DEFAULT_END.date().isoformat())
    parser.add_argument("--capital", type=float, default=DEFAULT_CAPITAL)
    parser.add_argument("--risk-ratio", type=float, default=DEFAULT_RISK_RATIO)
    parser.add_argument("--max-concurrent", type=int, default=DEFAULT_MAX_CONCURRENT_POSITIONS)
    parser.add_argument("--mapping-path", default=str(DEFAULT_MAPPING_PATH))
    parser.add_argument("--universe-path", default=str(DEFAULT_UNIVERSE_PATH))
    parser.add_argument("--output-prefix", default=DEFAULT_OUTPUT_PREFIX)
    parser.add_argument("--signal-variant", choices=SIGNAL_VARIANTS, default=DEFAULT_SIGNAL_VARIANT)
    parser.add_argument("--no-save", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = BacktestConfig(
        start=datetime.fromisoformat(args.start),
        end=datetime.fromisoformat(args.end),
        capital=float(args.capital),
        risk_ratio=float(args.risk_ratio),
        max_concurrent_positions=int(args.max_concurrent),
        mapping_path=Path(args.mapping_path),
        universe_path=Path(args.universe_path),
        output_prefix=str(args.output_prefix),
        signal_variant=str(args.signal_variant),
        save_outputs=not bool(args.no_save),
    )
    stats, _, paths = run_backtest(config)
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    if paths:
        print(json.dumps(paths, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
