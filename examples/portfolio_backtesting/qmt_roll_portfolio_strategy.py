from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from vnpy.trader.constant import Direction, Interval
from vnpy.trader.object import BarData, TradeData
from vnpy.trader.utility import ArrayManager
from vnpy_portfoliostrategy import StrategyEngine, StrategyTemplate

from main_contract_mapping import DEFAULT_MAPPING_PATH, build_contract_metadata, build_daily_mapping


@dataclass
class PositionLayer:
    kind: str
    direction: str
    volume: int
    entry_price: float
    stop_price: float
    highest_price: float
    lowest_price: float
    signal: str
    entry_date: str
    max_profit_pct: float = 0.0
    margin_ratio: float = 0.1


@dataclass
class ProductState:
    product_vt_symbol: str
    contract_vt_symbol: str = ""
    direction: str = ""
    risk_mode: str = "regular"
    layers: list[PositionLayer] = field(default_factory=list)
    last_signal: str = ""
    entry_date: str = ""
    last_add_date: str = ""
    last_donchian_add_date: str = ""
    rollover_opened_today: str = ""
    bars_since_entry: int = 0
    prev2day_stop_price: float | None = None
    rsi_partial_exit_done: bool = False

    def reset(self) -> None:
        self.contract_vt_symbol = ""
        self.direction = ""
        self.risk_mode = "regular"
        self.layers.clear()
        self.last_signal = ""
        self.entry_date = ""
        self.last_add_date = ""
        self.last_donchian_add_date = ""
        self.rollover_opened_today = ""
        self.bars_since_entry = 0
        self.prev2day_stop_price = None
        self.rsi_partial_exit_done = False

    def active_volume(self) -> int:
        return sum(layer.volume for layer in self.layers)

    def base_volume(self) -> int:
        for layer in self.layers:
            if layer.kind == "base":
                return layer.volume
        return 0

    def avg_entry_price(self) -> float:
        total_volume: int = self.active_volume()
        if total_volume <= 0:
            return 0.0

        weighted_cost: float = sum(layer.entry_price * layer.volume for layer in self.layers)
        return weighted_cost / total_volume


class QmtRollPortfolioStrategy(StrategyTemplate):
    """
    Main-contract switching backtest version.

    Each product uses the daily dominant contract from mapping table, closes
    the old dominant contract when rollover happens, and optionally reopens
    on the new dominant contract in the same direction.
    """

    author: str = "GPT-5.4"

    mapping_csv_path: str = str(DEFAULT_MAPPING_PATH)

    ma_short: int = 5
    ma_mid: int = 10
    ma_long: int = 20
    ma_extra_long: int = 40

    rsi_length: int = 6
    enable_rsi_filter: bool = False
    rsi_long_max: float = 80.0
    rsi_short_min: float = 10.0

    long_entry_enabled: bool = True
    short_entry_enabled: bool = False
    exit_on_alignment_break: bool = True
    enable_ma_trend_stop: bool = True
    rollover_reopen_enabled: bool = True
    reverse_on_opposite_signal: bool = True
    enable_prev2day_stop: bool = False
    enable_rsi_partial_exit: bool = False
    rsi_partial_exit_threshold: float = 95.0
    rsi_partial_exit_ratio: float = 0.5

    fixed_size: int = 1
    min_position_size: int = 1
    max_position_size: int = 50000
    max_concurrent_positions: int = 10
    capital_base: float = 0.0
    max_capital_usage_ratio: float = 0.9
    risk_ratio_of_total_assets: float = 0.01
    risk_ratio_breakout: float = 0.01
    risk_ratio_ma_cross_breakout: float = 0.01
    risk_ratio_open_interest_surge: float = 0.06
    risk_ratio_open_interest_decline: float = 0.02
    risk_ratio_volume_open_interest_surge: float = 0.08
    min_risk_per_trade: float = 1000.0
    max_risk_per_trade: float = 50_000_000.0
    default_margin_ratio: float = 0.10
    margin_ratio_overrides: str = ""
    streak_risk_multipliers: str = "1.0,1.0,1.0,0.1"

    stop_loss_pct: float = 0.02
    trailing_stop_enabled: bool = True
    trailing_stop_pct: float = 0.0
    add_position_min_profit: float = 0.001
    atr_2x_mid_stop_enabled: bool = True

    enable_add_position: bool = True
    add_position_threshold: float = 0.01
    second_add_position_threshold: float = 0.01
    max_add_layers: int = 1
    regular_add_volume_multiplier: float = 0.5
    regular_add_use_day_extreme_stop: bool = True
    restrict_regular_add_to_first: bool = True
    require_reversal_for_add: bool = True
    ma5_extreme_filter_enabled: bool = True
    ma5_extreme_compare_days: int = 3
    ma5_angle_reversal_filter_enabled: bool = True
    ma5_angle_reversal_lookback_days: int = 10
    ma5_angle_reversal_angle_threshold_deg: float = 45.0
    short_ma5_slope_filter_enabled: bool = True
    wick_chop_filter_enabled: bool = False
    wick_chop_filter_lookback: int = 10
    wick_chop_filter_max_days: int = 4

    enable_donchian_add_position: bool = True
    donchian_entry_period: int = 20
    donchian_add_period: int = 20
    donchian_add_max_layers: int = 2
    donchian_add_volume_multipliers: str = "2.0,1.0"
    case2_requires_breakout: bool = True

    tick_add: int = 1
    warmup_days: int = 80

    active_count: int = 0
    last_signal: str = ""
    estimated_equity: float = 0.0
    realized_pnl: float = 0.0
    total_margin_in_use: float = 0.0
    current_risk_per_trade: float = 0.0
    risk_multiplier: float = 1.0
    loss_streak: int = 0

    parameters: list[str] = [
        "mapping_csv_path",
        "ma_short",
        "ma_mid",
        "ma_long",
        "ma_extra_long",
        "rsi_length",
        "enable_rsi_filter",
        "rsi_long_max",
        "rsi_short_min",
        "long_entry_enabled",
        "short_entry_enabled",
        "exit_on_alignment_break",
        "enable_ma_trend_stop",
        "rollover_reopen_enabled",
        "reverse_on_opposite_signal",
        "enable_prev2day_stop",
        "enable_rsi_partial_exit",
        "rsi_partial_exit_threshold",
        "rsi_partial_exit_ratio",
        "fixed_size",
        "min_position_size",
        "max_position_size",
        "max_concurrent_positions",
        "capital_base",
        "max_capital_usage_ratio",
        "risk_ratio_of_total_assets",
        "risk_ratio_breakout",
        "risk_ratio_ma_cross_breakout",
        "risk_ratio_open_interest_surge",
        "risk_ratio_open_interest_decline",
        "risk_ratio_volume_open_interest_surge",
        "min_risk_per_trade",
        "max_risk_per_trade",
        "default_margin_ratio",
        "margin_ratio_overrides",
        "streak_risk_multipliers",
        "stop_loss_pct",
        "trailing_stop_enabled",
        "trailing_stop_pct",
        "add_position_min_profit",
        "atr_2x_mid_stop_enabled",
        "enable_add_position",
        "add_position_threshold",
        "second_add_position_threshold",
        "max_add_layers",
        "regular_add_volume_multiplier",
        "regular_add_use_day_extreme_stop",
        "restrict_regular_add_to_first",
        "require_reversal_for_add",
        "ma5_extreme_filter_enabled",
        "ma5_extreme_compare_days",
        "ma5_angle_reversal_filter_enabled",
        "ma5_angle_reversal_lookback_days",
        "ma5_angle_reversal_angle_threshold_deg",
        "short_ma5_slope_filter_enabled",
        "wick_chop_filter_enabled",
        "wick_chop_filter_lookback",
        "wick_chop_filter_max_days",
        "enable_donchian_add_position",
        "donchian_entry_period",
        "donchian_add_period",
        "donchian_add_max_layers",
        "donchian_add_volume_multipliers",
        "case2_requires_breakout",
        "tick_add",
        "warmup_days",
    ]
    variables: list[str] = [
        "active_count",
        "last_signal",
        "estimated_equity",
        "realized_pnl",
        "total_margin_in_use",
        "current_risk_per_trade",
        "risk_multiplier",
        "loss_streak",
    ]

    def __init__(
        self,
        strategy_engine: StrategyEngine,
        strategy_name: str,
        vt_symbols: list[str],
        setting: dict,
    ) -> None:
        super().__init__(strategy_engine, strategy_name, vt_symbols, setting)

        mapping_path = Path(self.mapping_csv_path)
        self.daily_mapping: dict[str, dict[str, str]] = build_daily_mapping(mapping_path)
        metadata: dict[str, Any] = build_contract_metadata(mapping_path)
        self.product_symbols: list[str] = metadata["product_symbols"]
        self.source_symbol_by_contract: dict[str, str] = metadata["source_symbol_by_contract"]

        am_size: int = max(self.ma_extra_long + self.donchian_entry_period + 20, 120)
        self.ams: dict[str, ArrayManager] = {
            vt_symbol: ArrayManager(am_size) for vt_symbol in self.vt_symbols
        }
        self.states: dict[str, ProductState] = {
            product_vt: ProductState(product_vt_symbol=product_vt) for product_vt in self.product_symbols
        }
        self.base_capital: float = self._resolve_base_capital()
        self.entry_risk_diagnostics: list[dict[str, Any]] = []

    def on_init(self) -> None:
        self.write_log("Roll portfolio strategy initialized")
        self.load_bars(self.warmup_days, interval=Interval.DAILY)

    def on_start(self) -> None:
        self.write_log("Roll portfolio strategy started")

    def on_stop(self) -> None:
        self.write_log("Roll portfolio strategy stopped")

    def update_trade(self, trade: TradeData) -> None:
        super().update_trade(trade)

    def on_bars(self, bars: dict[str, BarData]) -> None:
        if not bars:
            return

        for vt_symbol, bar in bars.items():
            if vt_symbol in self.ams:
                self.ams[vt_symbol].update_bar(bar)

        current_date: str = next(iter(bars.values())).datetime.strftime("%Y-%m-%d")
        mapping_today: dict[str, str] = self.daily_mapping.get(current_date, {})
        self._refresh_risk_state(bars)
        self.last_signal = ""

        for product_vt in self.product_symbols:
            target_contract: str = mapping_today.get(product_vt, "")
            if not target_contract:
                continue

            state: ProductState = self.states[product_vt]
            target_bar: BarData | None = bars.get(target_contract)
            if target_bar is None:
                continue

            actual_contract, current_pos, actual_bar = self._resolve_actual_position(state, target_contract, bars)
            if actual_contract and current_pos != 0:
                state.contract_vt_symbol = actual_contract

            target_am: ArrayManager = self.ams[target_contract]
            if not target_am.inited:
                continue

            history: pd.DataFrame = self._build_history_df(target_am)
            signal_data: dict[str, Any] = self._generate_signal(target_am, history)
            signal: str = str(signal_data["signal"])
            bullish: bool = bool(signal_data["bullish_alignment"])
            bearish: bool = bool(signal_data["bearish_alignment"])
            ma_long_value: float = float(signal_data["ma_long_value"])
            rsi_value: float = float(signal_data["rsi_value"])

            reconcile_bar: BarData = actual_bar or target_bar
            self._reconcile_state_with_position(state, current_pos, reconcile_bar)

            if state.contract_vt_symbol and state.contract_vt_symbol != target_contract:
                self._handle_rollover(state, target_contract, bars)
                continue

            if current_pos == 0:
                if signal.startswith("long") and self.long_entry_enabled:
                    if self._count_active_positions() >= self.max_concurrent_positions:
                        continue

                    sizing: dict[str, Any] = self._calculate_entry_sizing(
                        target_contract, "long", target_bar, history, signal_data
                    )
                    volume: int = int(sizing["selected_volume"])
                    if volume <= 0:
                        continue

                    self._open_position(
                        state,
                        target_contract,
                        "long",
                        volume,
                        target_bar,
                        signal,
                        history,
                        signal_data,
                        sizing_snapshot=sizing,
                    )
                    self._apply_state_target(state)
                    self.last_signal = f"{product_vt}:{signal}"
                elif signal.startswith("short") and self.short_entry_enabled and self._can_open_short_signal(signal):
                    if self._count_active_positions() >= self.max_concurrent_positions:
                        continue

                    sizing = self._calculate_entry_sizing(target_contract, "short", target_bar, history, signal_data)
                    volume = int(sizing["selected_volume"])
                    if volume <= 0:
                        continue

                    self._open_position(
                        state,
                        target_contract,
                        "short",
                        volume,
                        target_bar,
                        signal,
                        history,
                        signal_data,
                        sizing_snapshot=sizing,
                    )
                    self._apply_state_target(state)
                    self.last_signal = f"{product_vt}:{signal}"
                continue

            if state.entry_date and state.entry_date != self._bar_date(target_bar):
                state.bars_since_entry += 1

            self._update_dynamic_stops(state, target_bar, history)

            layer_exit_reason: str = self._process_layer_stops(state, target_bar)
            if layer_exit_reason:
                self.last_signal = f"{product_vt}:{layer_exit_reason}"
                continue

            prev2day_exit_reason: str = self._process_prev2day_stop(state, target_bar, history)
            if prev2day_exit_reason:
                self.last_signal = f"{product_vt}:{prev2day_exit_reason}"
                continue

            rsi_partial_exit_reason: str = self._process_rsi_partial_exit(state, target_bar, rsi_value)
            if rsi_partial_exit_reason:
                self._apply_state_target(state)
                self.last_signal = f"{product_vt}:{rsi_partial_exit_reason}"
                continue

            if self.enable_ma_trend_stop:
                if state.direction == "long" and float(target_bar.close_price) < ma_long_value:
                    self._close_all_layers_and_set_flat_target(state, float(target_bar.close_price))
                    self.last_signal = f"{product_vt}:long_ma_stop"
                    continue
                if state.direction == "short" and float(target_bar.close_price) > ma_long_value:
                    self._close_all_layers_and_set_flat_target(state, float(target_bar.close_price))
                    self.last_signal = f"{product_vt}:short_ma_stop"
                    continue

            if state.direction == "long":
                if self.exit_on_alignment_break and not bullish:
                    self._close_all_layers_and_set_flat_target(state, float(target_bar.close_price))
                    self.last_signal = f"{product_vt}:long_exit_alignment"
                    continue

                if self.reverse_on_opposite_signal and signal.startswith("short"):
                    self._close_all_layers_and_set_flat_target(state, float(target_bar.close_price))
                    if self.short_entry_enabled and self._can_open_short_signal(signal):
                        sizing = self._calculate_entry_sizing(target_contract, "short", target_bar, history, signal_data)
                        volume = int(sizing["selected_volume"])
                        if volume > 0:
                            self._open_position(
                                state,
                                target_contract,
                                "short",
                                volume,
                                target_bar,
                                signal,
                                history,
                                signal_data,
                                sizing_snapshot=sizing,
                            )
                            self._apply_state_target(state)
                            self.last_signal = f"{product_vt}:{signal}"
                    continue
            else:
                if self.exit_on_alignment_break and not bearish:
                    self._close_all_layers_and_set_flat_target(state, float(target_bar.close_price))
                    self.last_signal = f"{product_vt}:short_exit_alignment"
                    continue

                if self.reverse_on_opposite_signal and signal.startswith("long"):
                    self._close_all_layers_and_set_flat_target(state, float(target_bar.close_price))
                    if self.long_entry_enabled:
                        sizing = self._calculate_entry_sizing(target_contract, "long", target_bar, history, signal_data)
                        volume = int(sizing["selected_volume"])
                        if volume > 0:
                            self._open_position(
                                state,
                                target_contract,
                                "long",
                                volume,
                                target_bar,
                                signal,
                                history,
                                signal_data,
                                sizing_snapshot=sizing,
                            )
                            self._apply_state_target(state)
                            self.last_signal = f"{product_vt}:{signal}"
                    continue

            can_add, add_type = self._check_regular_add_conditions(state, target_bar, history)
            if can_add and add_type:
                add_volume: int = self._calculate_regular_add_volume(state)
                if add_volume > 0 and self._can_allocate_margin(state.contract_vt_symbol, add_volume, target_bar.close_price):
                    self._execute_regular_add(state, target_bar, add_type, add_volume, history)
                    self._apply_state_target(state)
                    self.last_signal = f"{product_vt}:{add_type}"
                    continue

            can_don_add, don_add_type = self._check_donchian_add_conditions(state, target_bar, history)
            if can_don_add and don_add_type:
                add_volume = self._calculate_donchian_add_volume(state)
                if add_volume > 0 and self._can_allocate_margin(state.contract_vt_symbol, add_volume, target_bar.close_price):
                    self._execute_donchian_add(state, target_bar, don_add_type, add_volume, history)
                    self._apply_state_target(state)
                    self.last_signal = f"{product_vt}:{don_add_type}"

        self.rebalance_portfolio(bars)
        self.active_count = self._count_active_positions()
        self.put_event()

    def _resolve_actual_position(
        self,
        state: ProductState,
        target_contract: str,
        bars: dict[str, BarData],
    ) -> tuple[str, int, BarData | None]:
        candidates: list[str] = []

        def add_candidate(vt_symbol: str) -> None:
            if vt_symbol and vt_symbol not in candidates:
                candidates.append(vt_symbol)

        add_candidate(state.contract_vt_symbol)
        add_candidate(target_contract)

        for vt_symbol in bars:
            if self.source_symbol_by_contract.get(vt_symbol) == state.product_vt_symbol:
                add_candidate(vt_symbol)

        for vt_symbol in candidates:
            pos: int = int(self.get_pos(vt_symbol))
            if pos != 0:
                return vt_symbol, pos, bars.get(vt_symbol)

        return state.contract_vt_symbol or target_contract, 0, bars.get(state.contract_vt_symbol or target_contract)

    def calculate_price(self, vt_symbol: str, direction: Direction, reference: float) -> float:
        pricetick: float = self.get_pricetick(vt_symbol)
        if direction == Direction.LONG:
            return reference + self.tick_add * pricetick
        return reference - self.tick_add * pricetick

    def _handle_rollover(self, state: ProductState, target_contract: str, bars: dict[str, BarData]) -> None:
        if not state.contract_vt_symbol:
            return

        old_contract: str = state.contract_vt_symbol
        old_bar: BarData | None = bars.get(old_contract)
        new_bar: BarData | None = bars.get(target_contract)
        if not old_bar or not new_bar:
            return

        old_direction: str = state.direction
        old_risk_mode: str = state.risk_mode
        self._close_all_layers(state, float(old_bar.close_price))
        self.set_target(old_contract, 0)

        if not self.rollover_reopen_enabled:
            return

        target_am: ArrayManager = self.ams[target_contract]
        if not target_am.inited:
            return

        history: pd.DataFrame = self._build_history_df(target_am)
        signal_data: dict[str, Any] = self._generate_signal(target_am, history)
        if not self._rollover_reopen_allowed(old_direction, history, signal_data):
            return

        sizing: dict[str, Any] = self._calculate_entry_sizing(
            target_contract,
            old_direction,
            new_bar,
            history,
            signal_data,
            risk_mode_override=old_risk_mode,
        )
        volume: int = int(sizing["selected_volume"])
        if volume <= 0:
            return

        self._open_position(
            state,
            target_contract,
            old_direction,
            volume,
            new_bar,
            "rollover_reopen",
            history,
            signal_data,
            sizing_snapshot=sizing,
        )
        state.risk_mode = old_risk_mode
        state.rollover_opened_today = self._bar_date(new_bar)
        self._apply_state_target(state)

    def _refresh_risk_state(self, bars: dict[str, BarData]) -> None:
        self.estimated_equity = self._estimate_equity(bars)
        self.total_margin_in_use = self._estimate_margin_usage(bars)
        limited_balance: float = self._limited_available_balance()
        self.current_risk_per_trade = self._risk_amount_from_ratio(self.risk_ratio_of_total_assets, limited_balance)
        self.risk_multiplier = self._current_streak_multiplier()

    def _resolve_base_capital(self) -> float:
        if self.capital_base > 0:
            return float(self.capital_base)
        capital: float | None = getattr(self.strategy_engine, "capital", None)
        if capital:
            return float(capital)
        return 1_000_000.0

    def _estimate_equity(self, bars: dict[str, BarData]) -> float:
        equity: float = self.base_capital + self.realized_pnl
        for state in self.states.values():
            if not state.contract_vt_symbol or not state.layers:
                continue
            bar: BarData | None = bars.get(state.contract_vt_symbol)
            if not bar:
                continue
            size: int = self.get_size(state.contract_vt_symbol)
            close_price: float = float(bar.close_price)
            for layer in state.layers:
                pnl: float = (
                    (close_price - layer.entry_price) * size * layer.volume
                    if layer.direction == "long"
                    else (layer.entry_price - close_price) * size * layer.volume
                )
                equity += pnl
        return equity

    def _estimate_margin_usage(self, bars: dict[str, BarData]) -> float:
        total_margin: float = 0.0
        for state in self.states.values():
            if not state.contract_vt_symbol or not state.layers:
                continue
            bar: BarData | None = bars.get(state.contract_vt_symbol)
            if not bar:
                continue
            size: int = self.get_size(state.contract_vt_symbol)
            close_price: float = float(bar.close_price)
            margin_ratio: float = self._margin_ratio_for_symbol(state.contract_vt_symbol)
            total_margin += abs(close_price * size * state.active_volume() * margin_ratio)
        return total_margin

    def _sizing_equity(self) -> float:
        """Use current estimated equity for sizing, while still de-risking on drawdown."""
        return max(0.0, self.estimated_equity)

    def _limited_available_balance(self) -> float:
        sizing_equity: float = self._sizing_equity()
        allowed_capital: float = max(0.0, sizing_equity * self.max_capital_usage_ratio)
        free_capital: float = max(0.0, sizing_equity - self.total_margin_in_use)
        return max(0.0, min(free_capital, allowed_capital))

    def _risk_amount_from_ratio(self, risk_ratio: float, limited_balance: float) -> float:
        dynamic_risk: float = max(self.min_risk_per_trade, limited_balance * risk_ratio)
        dynamic_risk = min(self.max_risk_per_trade, dynamic_risk)
        dynamic_risk *= self._current_streak_multiplier()
        return max(0.0, dynamic_risk)

    def _current_streak_multiplier(self) -> float:
        multipliers: list[float] = self._parse_float_list(self.streak_risk_multipliers, [1.0, 1.0, 1.0, 0.1])
        tier: int = min(self.loss_streak, len(multipliers) - 1)
        return max(0.0, multipliers[tier])

    def _calculate_entry_sizing(
        self,
        vt_symbol: str,
        direction: str,
        bar: BarData,
        history: pd.DataFrame,
        signal_data: dict[str, Any],
        risk_mode_override: str | None = None,
    ) -> dict[str, Any]:
        if self.fixed_size > 0:
            volume: int = int(self.fixed_size)
            price: float = float(bar.close_price)
            stop_price: float = self._entry_stop_price(direction, bar, history, use_day_extreme=True)
            size: int = self.get_size(vt_symbol)
            margin_ratio: float = self._margin_ratio_for_symbol(vt_symbol)
            risk_per_contract: float = max(abs(price - stop_price) * size, max(float(self.get_pricetick(vt_symbol)) * size, 1.0))
            margin_per_contract: float = price * size * margin_ratio
            sizing_equity: float = self._sizing_equity()
            allowed_capital: float = max(0.0, sizing_equity * self.max_capital_usage_ratio)
            free_capital: float = max(0.0, sizing_equity - self.total_margin_in_use)
            limited_balance: float = max(0.0, min(free_capital, allowed_capital))
            return {
                "risk_mode": risk_mode_override or str(signal_data.get("risk_mode", "regular")),
                "risk_ratio": None,
                "risk_amount": None,
                "limited_balance": limited_balance,
                "allowed_capital": allowed_capital,
                "free_capital": free_capital,
                "stop_price": stop_price,
                "risk_per_contract": risk_per_contract,
                "margin_ratio": margin_ratio,
                "margin_per_contract": margin_per_contract,
                "contracts_by_risk": None,
                "contracts_by_margin": None,
                "selected_volume": volume,
                "risk_multiplier": self._current_streak_multiplier(),
                "sizing_method": "fixed_size",
            }

        limited_balance: float = self._limited_available_balance()
        sizing_equity: float = self._sizing_equity()
        allowed_capital: float = max(0.0, sizing_equity * self.max_capital_usage_ratio)
        free_capital: float = max(0.0, sizing_equity - self.total_margin_in_use)
        risk_mode: str = risk_mode_override or str(signal_data.get("risk_mode", "regular"))
        if risk_mode == "ma_cross_breakout":
            risk_ratio: float = self.risk_ratio_ma_cross_breakout
        elif risk_mode == "volume_open_interest_surge":
            risk_ratio = self.risk_ratio_volume_open_interest_surge
        elif risk_mode == "open_interest_surge":
            risk_ratio = self.risk_ratio_open_interest_surge
        elif risk_mode == "open_interest_decline":
            risk_ratio = self.risk_ratio_open_interest_decline
        elif risk_mode == "breakout":
            risk_ratio = self.risk_ratio_breakout
        else:
            risk_ratio = self.risk_ratio_of_total_assets

        risk_amount: float = self._risk_amount_from_ratio(risk_ratio, limited_balance)
        stop_price: float = self._entry_stop_price(direction, bar, history, use_day_extreme=True)
        size: int = self.get_size(vt_symbol)
        risk_per_contract: float = abs(float(bar.close_price) - stop_price) * size

        min_risk: float = max(float(self.get_pricetick(vt_symbol)) * size, 1.0)
        risk_per_contract = max(risk_per_contract, min_risk)

        contracts_by_risk: int = int(risk_amount // risk_per_contract) if risk_per_contract > 0 else 0
        margin_ratio: float = self._margin_ratio_for_symbol(vt_symbol)
        margin_per_contract: float = float(bar.close_price) * size * margin_ratio
        contracts_by_margin: int = int(limited_balance // margin_per_contract) if margin_per_contract > 0 else 0

        volume: int = min(contracts_by_risk, contracts_by_margin, self.max_position_size)
        if 0 < volume < self.min_position_size:
            volume = 0

        return {
            "risk_mode": risk_mode,
            "risk_ratio": risk_ratio,
            "risk_amount": risk_amount,
            "limited_balance": limited_balance,
            "allowed_capital": allowed_capital,
            "free_capital": free_capital,
            "stop_price": stop_price,
            "risk_per_contract": risk_per_contract,
            "margin_ratio": margin_ratio,
            "margin_per_contract": margin_per_contract,
            "contracts_by_risk": contracts_by_risk,
            "contracts_by_margin": contracts_by_margin,
            "selected_volume": max(0, volume),
            "risk_multiplier": self._current_streak_multiplier(),
            "sizing_method": "risk_budget",
        }

    def _calculate_entry_volume(
        self,
        vt_symbol: str,
        direction: str,
        bar: BarData,
        history: pd.DataFrame,
        signal_data: dict[str, Any],
        risk_mode_override: str | None = None,
    ) -> int:
        sizing: dict[str, Any] = self._calculate_entry_sizing(
            vt_symbol,
            direction,
            bar,
            history,
            signal_data,
            risk_mode_override=risk_mode_override,
        )
        return int(sizing["selected_volume"])

    def _count_active_positions(self) -> int:
        count: int = 0
        for state in self.states.values():
            if state.contract_vt_symbol and self.get_pos(state.contract_vt_symbol) != 0:
                count += 1
        return count

    def _open_position(
        self,
        state: ProductState,
        contract_vt_symbol: str,
        direction: str,
        volume: int,
        bar: BarData,
        signal: str,
        history: pd.DataFrame,
        signal_data: dict[str, Any],
        sizing_snapshot: dict[str, Any] | None = None,
    ) -> None:
        if sizing_snapshot is None:
            sizing_snapshot = self._calculate_entry_sizing(
                contract_vt_symbol,
                direction,
                bar,
                history,
                signal_data,
            )

        stop_price: float = float(sizing_snapshot["stop_price"])
        state.reset()
        state.contract_vt_symbol = contract_vt_symbol
        state.direction = direction
        state.risk_mode = str(signal_data.get("risk_mode", "regular"))
        state.entry_date = self._bar_date(bar)
        state.last_signal = signal
        state.layers.append(
            PositionLayer(
                kind="base",
                direction=direction,
                volume=max(1, int(volume)),
                entry_price=float(bar.close_price),
                stop_price=stop_price,
                highest_price=float(bar.high_price),
                lowest_price=float(bar.low_price),
                signal=signal,
                entry_date=state.entry_date,
                margin_ratio=self._margin_ratio_for_symbol(contract_vt_symbol),
            )
        )
        self._record_entry_risk_diagnostic(
            product_vt_symbol=state.product_vt_symbol,
            contract_vt_symbol=contract_vt_symbol,
            direction=direction,
            bar=bar,
            signal=signal,
            layer_kind="base",
            volume=max(1, int(volume)),
            stop_price=stop_price,
            risk_mode=str(sizing_snapshot.get("risk_mode", signal_data.get("risk_mode", "regular"))),
            sizing_snapshot=sizing_snapshot,
        )

    def _append_layer(
        self,
        state: ProductState,
        kind: str,
        volume: int,
        bar: BarData,
        signal: str,
        history: pd.DataFrame,
        use_day_extreme_stop: bool = True,
    ) -> None:
        stop_price: float = self._entry_stop_price(state.direction, bar, history, use_day_extreme=use_day_extreme_stop)
        state.layers.append(
            PositionLayer(
                kind=kind,
                direction=state.direction,
                volume=max(1, int(volume)),
                entry_price=float(bar.close_price),
                stop_price=stop_price,
                highest_price=float(bar.high_price),
                lowest_price=float(bar.low_price),
                signal=signal,
                entry_date=self._bar_date(bar),
                margin_ratio=self._margin_ratio_for_symbol(state.contract_vt_symbol),
            )
        )
        self._record_entry_risk_diagnostic(
            product_vt_symbol=state.product_vt_symbol,
            contract_vt_symbol=state.contract_vt_symbol,
            direction=state.direction,
            bar=bar,
            signal=signal,
            layer_kind=kind,
            volume=max(1, int(volume)),
            stop_price=stop_price,
            risk_mode=state.risk_mode,
            sizing_snapshot={
                "risk_mode": state.risk_mode,
                "risk_ratio": None,
                "risk_amount": None,
                "limited_balance": self._limited_available_balance(),
                "allowed_capital": max(0.0, self._sizing_equity() * self.max_capital_usage_ratio),
                "free_capital": max(0.0, self._sizing_equity() - self.total_margin_in_use),
                "stop_price": stop_price,
                "risk_per_contract": None,
                "margin_ratio": self._margin_ratio_for_symbol(state.contract_vt_symbol),
                "margin_per_contract": None,
                "contracts_by_risk": None,
                "contracts_by_margin": None,
                "selected_volume": max(1, int(volume)),
                "risk_multiplier": self._current_streak_multiplier(),
                "sizing_method": "add_multiplier" if kind == "add" else "donchian_multiplier",
            },
        )

    def _apply_state_target(self, state: ProductState) -> None:
        if not state.contract_vt_symbol:
            return
        volume: int = state.active_volume()
        target: int = -volume if state.direction == "short" else volume
        self.set_target(state.contract_vt_symbol, target)

    def _record_entry_risk_diagnostic(
        self,
        product_vt_symbol: str,
        contract_vt_symbol: str,
        direction: str,
        bar: BarData,
        signal: str,
        layer_kind: str,
        volume: int,
        stop_price: float,
        risk_mode: str,
        sizing_snapshot: dict[str, Any],
    ) -> None:
        entry_price: float = float(bar.close_price)
        size: int = self.get_size(contract_vt_symbol)
        margin_ratio: float = float(sizing_snapshot.get("margin_ratio", self._margin_ratio_for_symbol(contract_vt_symbol)) or 0.0)
        risk_per_contract: float = sizing_snapshot.get("risk_per_contract")
        if risk_per_contract is None:
            min_risk: float = max(float(self.get_pricetick(contract_vt_symbol)) * size, 1.0)
            risk_per_contract = max(abs(entry_price - stop_price) * size, min_risk)

        margin_per_contract: float = sizing_snapshot.get("margin_per_contract")
        if margin_per_contract is None:
            margin_per_contract = entry_price * size * margin_ratio

        actual_risk_amount: float = risk_per_contract * volume
        actual_margin_amount: float = margin_per_contract * volume
        estimated_equity: float = float(self.estimated_equity or self.base_capital)

        self.entry_risk_diagnostics.append(
            {
                "entry_index": len(self.entry_risk_diagnostics) + 1,
                "datetime": bar.datetime,
                "date": bar.datetime.date(),
                "product_vt_symbol": product_vt_symbol,
                "contract_vt_symbol": contract_vt_symbol,
                "direction": direction,
                "signal": signal,
                "layer_kind": layer_kind,
                "risk_mode": risk_mode,
                "sizing_method": sizing_snapshot.get("sizing_method", "unknown"),
                "estimated_equity": estimated_equity,
                "total_margin_in_use_before": float(self.total_margin_in_use),
                "allowed_capital": float(sizing_snapshot.get("allowed_capital") or 0.0),
                "free_capital": float(sizing_snapshot.get("free_capital") or 0.0),
                "limited_balance": float(sizing_snapshot.get("limited_balance") or 0.0),
                "risk_ratio": sizing_snapshot.get("risk_ratio"),
                "risk_multiplier": float(sizing_snapshot.get("risk_multiplier") or self._current_streak_multiplier()),
                "target_risk_amount": sizing_snapshot.get("risk_amount"),
                "entry_price": entry_price,
                "stop_price": stop_price,
                "stop_distance": abs(entry_price - stop_price),
                "size": size,
                "risk_per_contract": risk_per_contract,
                "actual_risk_amount": actual_risk_amount,
                "margin_ratio": margin_ratio,
                "margin_per_contract": margin_per_contract,
                "actual_margin_amount": actual_margin_amount,
                "projected_total_margin_after": float(self.total_margin_in_use) + actual_margin_amount,
                "volume": int(volume),
                "contracts_by_risk": sizing_snapshot.get("contracts_by_risk"),
                "contracts_by_margin": sizing_snapshot.get("contracts_by_margin"),
                "selected_volume": sizing_snapshot.get("selected_volume"),
                "loss_streak": int(self.loss_streak),
            }
        )

    def _reconcile_state_with_position(self, state: ProductState, current_pos: int, bar: BarData) -> None:
        if current_pos == 0:
            if state.layers:
                state.reset()
            return

        actual_direction: str = "long" if current_pos > 0 else "short"
        actual_volume: int = abs(int(current_pos))
        if not state.layers:
            state.contract_vt_symbol = bar.vt_symbol
            state.direction = actual_direction
            state.entry_date = self._bar_date(bar)
            state.layers.append(
                PositionLayer(
                    kind="base",
                    direction=actual_direction,
                    volume=actual_volume,
                    entry_price=float(bar.close_price),
                    stop_price=self._simple_stop_price(actual_direction, float(bar.close_price)),
                    highest_price=float(bar.high_price),
                    lowest_price=float(bar.low_price),
                    signal="reconciled",
                    entry_date=state.entry_date,
                    margin_ratio=self._margin_ratio_for_symbol(bar.vt_symbol),
                )
            )
            return

        layer_volume: int = state.active_volume()
        if layer_volume == actual_volume:
            return
        if layer_volume < actual_volume:
            state.layers[0].volume += actual_volume - layer_volume
            return

        reduce_volume: int = layer_volume - actual_volume
        while reduce_volume > 0 and state.layers:
            last_layer: PositionLayer = state.layers[-1]
            if last_layer.volume <= reduce_volume:
                reduce_volume -= last_layer.volume
                state.layers.pop()
            else:
                last_layer.volume -= reduce_volume
                reduce_volume = 0

        if not state.layers:
            state.reset()

    def _process_prev2day_stop(self, state: ProductState, bar: BarData, history: pd.DataFrame) -> str:
        if not self.enable_prev2day_stop or not state.layers:
            return ""
        if state.bars_since_entry < 2 or len(history) < 3:
            return ""

        prev2_window = history.iloc[-3:-1]
        if len(prev2_window) < 2:
            return ""

        if state.direction == "long":
            raw_stop = float(prev2_window["low"].min())
            final_stop = raw_stop if state.prev2day_stop_price is None else max(state.prev2day_stop_price, raw_stop)
            state.prev2day_stop_price = final_stop
            if float(bar.close_price) <= final_stop:
                self._close_all_layers_and_set_flat_target(state, float(bar.close_price))
                return "long_prev2day_stop"
        else:
            raw_stop = float(prev2_window["high"].max())
            final_stop = raw_stop if state.prev2day_stop_price is None else min(state.prev2day_stop_price, raw_stop)
            state.prev2day_stop_price = final_stop
            if float(bar.close_price) >= final_stop:
                self._close_all_layers_and_set_flat_target(state, float(bar.close_price))
                return "short_prev2day_stop"

        return ""

    def _process_layer_stops(self, state: ProductState, bar: BarData) -> str:
        direction: str = state.direction
        triggered_indexes: list[int] = []
        base_triggered: bool = False
        for index, layer in enumerate(state.layers):
            if direction == "long" and float(bar.close_price) <= layer.stop_price:
                if layer.kind == "base":
                    base_triggered = True
                    break
                triggered_indexes.append(index)
            elif direction == "short" and float(bar.close_price) >= layer.stop_price:
                if layer.kind == "base":
                    base_triggered = True
                    break
                triggered_indexes.append(index)

        if base_triggered:
            self._close_all_layers_and_set_flat_target(state, float(bar.close_price))
            return f"{direction}_base_stop"

        if not triggered_indexes:
            return ""

        self._close_layers(state, triggered_indexes, float(bar.close_price))
        if state.layers:
            self._apply_state_target(state)
        return f"{direction}_layer_stop_partial" if state.layers else f"{direction}_layer_stop_all"

    def _update_dynamic_stops(self, state: ProductState, bar: BarData, history: pd.DataFrame) -> None:
        for layer in state.layers:
            self._update_layer_stop(layer, bar)
        if self.atr_2x_mid_stop_enabled:
            self._apply_atr_mid_stop(state, bar, history)
        if state.active_volume() > state.base_volume():
            self._apply_add_position_profit_lock(state)

    def _update_layer_stop(self, layer: PositionLayer, bar: BarData) -> None:
        close_price: float = float(bar.close_price)
        layer.highest_price = max(layer.highest_price, float(bar.high_price))
        layer.lowest_price = min(layer.lowest_price, float(bar.low_price))

        pnl_pct: float
        if layer.direction == "long":
            pnl_pct = (close_price - layer.entry_price) / layer.entry_price if layer.entry_price else 0.0
        else:
            pnl_pct = (layer.entry_price - close_price) / layer.entry_price if layer.entry_price else 0.0
        layer.max_profit_pct = max(layer.max_profit_pct, pnl_pct)

        if layer.kind in {"add", "donchian"}:
            if layer.direction == "long":
                layer.stop_price = max(layer.stop_price, float(bar.low_price))
            else:
                layer.stop_price = min(layer.stop_price, float(bar.high_price))

        if self.trailing_stop_enabled:
            lock_price: float | None = self._profit_lock_price(layer)
            if lock_price is not None:
                if layer.direction == "long":
                    layer.stop_price = max(layer.stop_price, lock_price)
                else:
                    layer.stop_price = min(layer.stop_price, lock_price)

        if self.trailing_stop_pct > 0:
            if layer.direction == "long":
                layer.stop_price = max(layer.stop_price, layer.highest_price * (1 - self.trailing_stop_pct))
            else:
                layer.stop_price = min(layer.stop_price, layer.lowest_price * (1 + self.trailing_stop_pct))

    def _profit_lock_price(self, layer: PositionLayer) -> float | None:
        thresholds: list[tuple[float, float]] = [
            (0.30, 0.20),
            (0.20, 0.15),
            (0.10, 0.08),
            (0.05, 0.03),
            (0.03, 0.01),
            (0.02, 0.001),
        ]
        for trigger_pct, lock_pct in thresholds:
            if layer.max_profit_pct >= trigger_pct:
                return layer.entry_price * (1 + lock_pct) if layer.direction == "long" else layer.entry_price * (1 - lock_pct)
        return None

    def _apply_add_position_profit_lock(self, state: ProductState) -> None:
        avg_price: float = state.avg_entry_price()
        if avg_price <= 0:
            return
        if state.direction == "long":
            floor_stop: float = avg_price * (1 + self.add_position_min_profit)
            for layer in state.layers:
                layer.stop_price = max(layer.stop_price, floor_stop)
        else:
            ceil_stop: float = avg_price * (1 - self.add_position_min_profit)
            for layer in state.layers:
                layer.stop_price = min(layer.stop_price, ceil_stop)

    def _apply_atr_mid_stop(self, state: ProductState, bar: BarData, history: pd.DataFrame) -> None:
        if len(history) < 15:
            return
        closes = history["close"]
        highs = history["high"]
        lows = history["low"]
        prev_close = closes.shift(1)
        tr = pd.concat([(highs - lows).abs(), (highs - prev_close).abs(), (lows - prev_close).abs()], axis=1).max(axis=1)
        atr = tr.rolling(14).mean()
        atr_last: float = float(atr.iloc[-1]) if not pd.isna(atr.iloc[-1]) else 0.0
        close_last: float = float(closes.iloc[-1])
        close_prev: float = float(closes.iloc[-2])
        if atr_last <= 0 or abs(close_last - close_prev) < 2.0 * atr_last:
            return
        mid_price: float = 0.5 * (float(bar.high_price) + float(bar.low_price))
        for layer in state.layers:
            if layer.direction == "long":
                layer.stop_price = max(layer.stop_price, mid_price)
            else:
                layer.stop_price = min(layer.stop_price, mid_price)

    def _process_rsi_partial_exit(self, state: ProductState, bar: BarData, rsi_value: float) -> str:
        if not self.enable_rsi_partial_exit or state.rsi_partial_exit_done:
            return ""
        if not state.layers:
            return ""

        trigger_partial_exit: bool = False
        exit_reason: str = ""
        if state.direction == "long":
            trigger_partial_exit = rsi_value > self.rsi_partial_exit_threshold
            exit_reason = "long_rsi_partial_exit"
        elif state.direction == "short":
            trigger_partial_exit = rsi_value < (100.0 - self.rsi_partial_exit_threshold)
            exit_reason = "short_rsi_partial_exit"

        if not trigger_partial_exit:
            return ""

        current_volume: int = state.active_volume()
        reduce_volume: int = int(current_volume * self.rsi_partial_exit_ratio)
        if reduce_volume <= 0:
            return ""

        target_volume: int = current_volume - reduce_volume
        if target_volume <= 0:
            self._close_all_layers_and_set_flat_target(state, float(bar.close_price))
            state.rsi_partial_exit_done = True
            return f"{exit_reason}_all"

        self._reduce_position_to_target(state, target_volume, float(bar.close_price))
        state.rsi_partial_exit_done = True
        return f"{exit_reason}_half"

    def _can_open_short_signal(self, signal: str) -> bool:
        """Only allow fresh short entries from the MA5-down-cross bearish case."""
        return signal == "short_case1a"

    def _close_layers(self, state: ProductState, indexes: list[int], exit_price: float) -> None:
        if not state.contract_vt_symbol:
            return
        size: int = self.get_size(state.contract_vt_symbol)
        realized: float = 0.0
        for index in sorted(indexes, reverse=True):
            layer = state.layers[index]
            realized += self._layer_realized_pnl(layer, exit_price, size)
            del state.layers[index]
        self.realized_pnl += realized
        self._update_streak_risk_state(realized)
        if not state.layers:
            state.reset()

    def _reduce_position_to_target(self, state: ProductState, target_volume: int, exit_price: float) -> None:
        current_volume: int = state.active_volume()
        if target_volume >= current_volume:
            return
        if target_volume <= 0:
            self._close_all_layers(state, exit_price)
            return

        size: int = self.get_size(state.contract_vt_symbol)
        reduce_volume: int = current_volume - target_volume
        realized: float = 0.0

        while reduce_volume > 0 and state.layers:
            last_layer: PositionLayer = state.layers[-1]
            closed_volume: int = min(reduce_volume, last_layer.volume)
            realized += self._layer_realized_pnl(
                PositionLayer(
                    kind=last_layer.kind,
                    direction=last_layer.direction,
                    volume=closed_volume,
                    entry_price=last_layer.entry_price,
                    stop_price=last_layer.stop_price,
                    highest_price=last_layer.highest_price,
                    lowest_price=last_layer.lowest_price,
                    signal=last_layer.signal,
                    entry_date=last_layer.entry_date,
                    max_profit_pct=last_layer.max_profit_pct,
                    margin_ratio=last_layer.margin_ratio,
                ),
                exit_price,
                size,
            )
            last_layer.volume -= closed_volume
            reduce_volume -= closed_volume
            if last_layer.volume <= 0:
                state.layers.pop()

        self.realized_pnl += realized
        self._update_streak_risk_state(realized)
        if not state.layers:
            state.reset()

    def _close_all_layers(self, state: ProductState, exit_price: float) -> None:
        if not state.layers:
            state.reset()
            return
        self._close_layers(state, list(range(len(state.layers))), exit_price)
        state.reset()

    def _close_all_layers_and_set_flat_target(self, state: ProductState, exit_price: float) -> None:
        contract_vt_symbol: str = state.contract_vt_symbol
        if not contract_vt_symbol:
            state.reset()
            return
        self._close_all_layers(state, exit_price)
        self.set_target(contract_vt_symbol, 0)

    def _layer_realized_pnl(self, layer: PositionLayer, exit_price: float, size: int) -> float:
        return (exit_price - layer.entry_price) * size * layer.volume if layer.direction == "long" else (layer.entry_price - exit_price) * size * layer.volume

    def _update_streak_risk_state(self, realized_pnl: float) -> None:
        if realized_pnl < 0:
            self.loss_streak += 1
        elif realized_pnl > 0:
            self.loss_streak = 0
        self.risk_multiplier = self._current_streak_multiplier()

    def _check_regular_add_conditions(self, state: ProductState, bar: BarData, history: pd.DataFrame) -> tuple[bool, str | None]:
        if not self.enable_add_position:
            return False, None
        add_count = self._count_layers(state, "add")
        if add_count >= self.max_add_layers:
            return False, None
        if self.restrict_regular_add_to_first and add_count > 0:
            return False, None
        today_key = self._bar_date(bar)
        if state.last_add_date == today_key or state.entry_date == today_key or state.rollover_opened_today == today_key:
            return False, None
        avg_price = state.avg_entry_price()
        if avg_price <= 0:
            return False, None
        current_price = float(bar.close_price)
        profit_pct = (current_price - avg_price) / avg_price if state.direction == "long" else (avg_price - current_price) / avg_price
        threshold = self.add_position_threshold if add_count == 0 else self.second_add_position_threshold
        if profit_pct < threshold or len(history) < 2:
            return False, None
        if self.require_reversal_for_add:
            yesterday = history.iloc[-2]
            today = history.iloc[-1]
            reversal_ok = (
                float(yesterday["close"]) < float(yesterday["open"]) and float(today["close"]) > float(today["open"])
                if state.direction == "long"
                else float(yesterday["close"]) > float(yesterday["open"]) and float(today["close"]) < float(today["open"])
            )
            if not reversal_ok:
                return False, None
        if state.direction == "long" and float(bar.close_price) < float(bar.open_price):
            return False, None
        if state.direction == "short" and float(bar.close_price) > float(bar.open_price):
            return False, None
        if self.wick_chop_filter_enabled:
            ok, _, _ = self._wick_chop_filter_ok(history, self.wick_chop_filter_lookback, self.wick_chop_filter_max_days)
            if not ok:
                return False, None
        return True, ("first_add" if add_count == 0 else f"add_{add_count + 1}")

    def _calculate_regular_add_volume(self, state: ProductState) -> int:
        return min(max(1, int(round(state.base_volume() * self.regular_add_volume_multiplier))), self.max_position_size)

    def _execute_regular_add(self, state: ProductState, bar: BarData, signal: str, volume: int, history: pd.DataFrame) -> None:
        self._append_layer(state, "add", volume, bar, signal, history, self.regular_add_use_day_extreme_stop)
        state.last_add_date = self._bar_date(bar)
        state.last_signal = signal
        self._apply_add_position_profit_lock(state)

    def _check_donchian_add_conditions(self, state: ProductState, bar: BarData, history: pd.DataFrame) -> tuple[bool, str | None]:
        if not self.enable_donchian_add_position:
            return False, None
        add_count = self._count_layers(state, "donchian")
        if add_count >= self.donchian_add_max_layers:
            return False, None
        today_key = self._bar_date(bar)
        if state.last_donchian_add_date == today_key or state.rollover_opened_today == today_key:
            return False, None
        period = max(int(self.donchian_add_period), 1)
        if len(history) < period + 1:
            return False, None
        channel_source = history.iloc[:-1].tail(period)
        upper = float(channel_source["high"].max())
        lower = float(channel_source["low"].min())
        close_price = float(bar.close_price)
        if state.direction == "long" and close_price > upper:
            return True, f"donchian_add_{add_count + 1}"
        if state.direction == "short" and close_price < lower:
            return True, f"donchian_add_{add_count + 1}"
        return False, None

    def _calculate_donchian_add_volume(self, state: ProductState) -> int:
        base_volume = max(1, state.base_volume())
        multipliers = self._parse_float_list(self.donchian_add_volume_multipliers, [2.0, 1.0])
        add_index = self._count_layers(state, "donchian")
        multiplier = multipliers[add_index] if add_index < len(multipliers) else multipliers[-1]
        return min(max(1, int(round(base_volume * multiplier))), self.max_position_size)

    def _execute_donchian_add(self, state: ProductState, bar: BarData, signal: str, volume: int, history: pd.DataFrame) -> None:
        self._append_layer(state, "donchian", volume, bar, signal, history, True)
        state.last_donchian_add_date = self._bar_date(bar)
        state.last_signal = signal
        self._apply_add_position_profit_lock(state)

    def _can_allocate_margin(self, vt_symbol: str, volume: int, price: float) -> bool:
        margin_ratio = self._margin_ratio_for_symbol(vt_symbol)
        projected_margin = price * self.get_size(vt_symbol) * volume * margin_ratio
        allowed_capital = max(0.0, self._sizing_equity() * self.max_capital_usage_ratio)
        return (self.total_margin_in_use + projected_margin) <= allowed_capital

    def _build_history_df(self, am: ArrayManager) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "open": pd.Series(am.open_array, dtype="float64"),
                "high": pd.Series(am.high_array, dtype="float64"),
                "low": pd.Series(am.low_array, dtype="float64"),
                "close": pd.Series(am.close_array, dtype="float64"),
                "volume": pd.Series(am.volume_array, dtype="float64"),
                "open_interest": pd.Series(am.open_interest_array, dtype="float64"),
            }
        )

    def _entry_stop_price(self, direction: str, bar: BarData, history: pd.DataFrame, use_day_extreme: bool) -> float:
        basic_long = float(bar.close_price) * (1 - self.stop_loss_pct)
        basic_short = float(bar.close_price) * (1 + self.stop_loss_pct)
        close_price = float(bar.close_price)
        low_price = float(bar.low_price)
        high_price = float(bar.high_price)
        recent3 = history.tail(3) if len(history) >= 3 else history
        min_low = float(recent3["low"].min()) if not recent3.empty else low_price
        max_high = float(recent3["high"].max()) if not recent3.empty else high_price
        smart_long = max(basic_long, min_low)
        smart_short = min(basic_short, max_high)
        if use_day_extreme:
            if direction == "long":
                # When close is too close to the day's low, fall back to a minimum
                # stop distance based on close to avoid oversized positions.
                day_drop_ratio = (close_price - low_price) / close_price if close_price > 0 else 0.0
                if day_drop_ratio < self.stop_loss_pct:
                    return basic_long
                return low_price
            return min(high_price, smart_short)
        return smart_long if direction == "long" else smart_short

    def _simple_stop_price(self, direction: str, close_price: float) -> float:
        return close_price * (1 - self.stop_loss_pct) if direction == "long" else close_price * (1 + self.stop_loss_pct)

    def _count_layers(self, state: ProductState, kind: str) -> int:
        return sum(1 for layer in state.layers if layer.kind == kind)

    def _margin_ratio_for_symbol(self, vt_symbol: str) -> float:
        overrides = self._parse_mapping(self.margin_ratio_overrides)
        if vt_symbol in overrides:
            return overrides[vt_symbol]
        source_symbol = self.source_symbol_by_contract.get(vt_symbol, "")
        if source_symbol and source_symbol in overrides:
            return overrides[source_symbol]
        return max(0.0, self.default_margin_ratio)

    def _parse_mapping(self, raw: str) -> dict[str, float]:
        mapping: dict[str, float] = {}
        for item in str(raw or "").replace(";", ",").split(","):
            item = item.strip()
            if not item or "=" not in item:
                continue
            key, value = item.split("=", 1)
            try:
                mapping[key.strip()] = float(value.strip())
            except ValueError:
                continue
        return mapping

    def _parse_float_list(self, raw: str, default: list[float]) -> list[float]:
        values: list[float] = []
        for part in str(raw or "").split(","):
            part = part.strip()
            if not part:
                continue
            try:
                values.append(float(part))
            except ValueError:
                continue
        return values or default

    def _bar_date(self, bar: BarData) -> str:
        return bar.datetime.strftime("%Y%m%d")

    @staticmethod
    def _wick_chop_filter_ok(market_data_df: pd.DataFrame, lookback: int = 10, max_days: int = 4) -> tuple[bool, int, int]:
        df = market_data_df[["open", "high", "low", "close"]].tail(max(int(lookback), 1)).dropna()
        if len(df) < max(int(lookback), 1):
            return True, 0, len(df)
        count = 0
        for _, row in df.iterrows():
            o, h, l, c = float(row["open"]), float(row["high"]), float(row["low"]), float(row["close"])
            body = abs(c - o)
            upper = h - max(o, c)
            lower = min(o, c) - l
            if upper > body or lower > body:
                count += 1
        return count <= int(max_days), count, len(df)

    @staticmethod
    def _is_latest_ma_extreme(
        market_data_df: pd.DataFrame,
        period: int = 5,
        compare_days: int = 3,
        mode: str = "max",
    ) -> tuple[bool, float | None, list[float]]:
        try:
            period_i = max(int(period or 5), 1)
            compare_i = max(int(compare_days or 3), 1)
            if market_data_df is None or len(market_data_df) < period_i + compare_i - 1:
                return False, None, []
            close = pd.to_numeric(market_data_df["close"], errors="coerce")
            ma = close.rolling(window=period_i).mean().dropna()
            if len(ma) < compare_i:
                return False, None, []

            recent_vals = [float(x) for x in ma.iloc[-compare_i:].tolist() if pd.notna(x)]
            if len(recent_vals) < compare_i:
                return False, None, recent_vals

            latest_val = float(recent_vals[-1])
            if compare_i >= 3:
                prev1_val = float(recent_vals[-2])
                prev2_val = float(recent_vals[-3])
                if mode == "min":
                    should_block = (prev1_val < latest_val) and (prev2_val < prev1_val)
                    return (not should_block), latest_val, recent_vals
                should_block = (prev1_val > latest_val) and (prev2_val > prev1_val)
                return (not should_block), latest_val, recent_vals

            if mode == "min":
                return latest_val <= min(recent_vals), latest_val, recent_vals
            return latest_val >= max(recent_vals), latest_val, recent_vals
        except Exception:
            return False, None, []

    @staticmethod
    def _get_ma_slope_direction(market_data_df: pd.DataFrame, period: int = 5) -> float:
        try:
            period_i = int(period or 5)
            if market_data_df is None or len(market_data_df) < max(period_i, 2) + 1:
                return 0.0
            close = pd.to_numeric(market_data_df["close"], errors="coerce")
            ma = close.rolling(window=period_i).mean()
            if len(ma) < 2 or pd.isna(ma.iloc[-1]) or pd.isna(ma.iloc[-2]):
                return 0.0
            return float(ma.iloc[-1] - ma.iloc[-2])
        except Exception:
            return 0.0

    @staticmethod
    def _evaluate_ma5_angle_reversal_filter(
        market_data_df: pd.DataFrame,
        period: int = 5,
        lookback_days: int = 10,
        angle_threshold_deg: float = 30.0,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            "should_block": False,
            "recent_angles": [],
            "matched_prev_angle": None,
            "matched_curr_angle": None,
            "threshold_deg": float(angle_threshold_deg or 30.0),
        }
        try:
            period_i = max(int(period or 5), 1)
            lookback_i = max(int(lookback_days or 10), 2)
            threshold_f = float(angle_threshold_deg or 30.0)
            if market_data_df is None or len(market_data_df) < period_i + 2:
                return result
            close = pd.to_numeric(market_data_df["close"], errors="coerce")
            ma = close.rolling(window=period_i).mean().dropna()
            if len(ma) < 3:
                return result

            angles: list[float] = []
            for i in range(1, len(ma)):
                prev_v = ma.iloc[i - 1]
                curr_v = ma.iloc[i]
                if pd.isna(prev_v) or pd.isna(curr_v):
                    continue
                delta = float(curr_v) - float(prev_v)
                angle_deg = float(math.degrees(math.atan(delta)))
                angles.append(angle_deg)

            if len(angles) < 2:
                return result

            recent_angles = [float(x) for x in angles[-lookback_i:]]
            result["recent_angles"] = recent_angles
            for i in range(1, len(recent_angles)):
                prev_angle = float(recent_angles[i - 1])
                curr_angle = float(recent_angles[i])
                if prev_angle < -threshold_f and curr_angle > threshold_f:
                    result["should_block"] = True
                    result["matched_prev_angle"] = prev_angle
                    result["matched_curr_angle"] = curr_angle
                    break
            return result
        except Exception:
            return result

    def _is_simple_ma_trend(
        self,
        market_data_df: pd.DataFrame,
        direction: str,
        slope_lookback: int = 3,
    ) -> bool:
        try:
            if market_data_df is None:
                return False
            need = int(self.ma_extra_long) + int(slope_lookback) + 2
            if len(market_data_df) < need:
                return False
            close = market_data_df["close"]
            close_last = float(close.iloc[-1])

            ma_short = float(close.rolling(int(self.ma_short)).mean().iloc[-1])
            ma_mid = float(close.rolling(int(self.ma_mid)).mean().iloc[-1])
            ma_long = float(close.rolling(int(self.ma_long)).mean().iloc[-1])
            ma_extra = float(close.rolling(int(self.ma_extra_long)).mean().iloc[-1])
            ma_long_prev = float(close.rolling(int(self.ma_long)).mean().iloc[-1 - int(slope_lookback)])

            if direction == "long":
                return ma_short > ma_mid > ma_long > ma_extra and ma_long > ma_long_prev and close_last > ma_long
            if direction == "short":
                return ma_short < ma_mid < ma_long < ma_extra and ma_long < ma_long_prev and close_last < ma_long
            return False
        except Exception:
            return False

    def _passes_entry_filters(self, signal: str, history: pd.DataFrame) -> bool:
        if not signal:
            return False

        is_long = signal.startswith("long")
        is_short = signal.startswith("short")

        if self.ma5_extreme_filter_enabled:
            mode = "max" if is_long else "min"
            ok, _, _ = self._is_latest_ma_extreme(
                history,
                period=self.ma_short,
                compare_days=self.ma5_extreme_compare_days,
                mode=mode,
            )
            if not ok:
                return False

        if self.ma5_angle_reversal_filter_enabled:
            angle_filter = self._evaluate_ma5_angle_reversal_filter(
                history,
                period=self.ma_short,
                lookback_days=self.ma5_angle_reversal_lookback_days,
                angle_threshold_deg=self.ma5_angle_reversal_angle_threshold_deg,
            )
            if angle_filter.get("should_block"):
                return False

        if is_short and self.short_ma5_slope_filter_enabled:
            ma5_slope = self._get_ma_slope_direction(history, period=self.ma_short)
            if ma5_slope > 0:
                return False

        if self.wick_chop_filter_enabled:
            direction = "long" if is_long else "short"
            if not self._is_simple_ma_trend(history, direction, 3):
                ok, _, _ = self._wick_chop_filter_ok(
                    history,
                    self.wick_chop_filter_lookback,
                    self.wick_chop_filter_max_days,
                )
                if not ok:
                    return False

        return True

    def _rollover_reopen_allowed(
        self,
        old_direction: str,
        history: pd.DataFrame,
        signal_data: dict[str, Any],
    ) -> bool:
        bullish_alignment: bool = bool(signal_data.get("bullish_alignment"))
        bearish_alignment: bool = bool(signal_data.get("bearish_alignment"))
        close = pd.to_numeric(history["close"], errors="coerce")
        dif, dea, hist = self._calculate_macd(close)
        if hist.empty or pd.isna(hist.iloc[-1]):
            return False

        macd_hist_t: float = float(hist.iloc[-1])
        synthetic_signal: str = "long_rollover" if old_direction == "long" else "short_rollover"

        if old_direction == "long":
            reopen_allowed: bool = bool(self.long_entry_enabled and bullish_alignment and macd_hist_t > 0)
        else:
            reopen_allowed = bool(self.short_entry_enabled and bearish_alignment and macd_hist_t < 0)

        if not reopen_allowed:
            return False

        return self._passes_entry_filters(synthetic_signal, history)

    def _generate_signal(self, am: ArrayManager, history: pd.DataFrame) -> dict[str, Any]:
        close = pd.Series(am.close_array)
        ma_short = close.rolling(self.ma_short).mean()
        ma_mid = close.rolling(self.ma_mid).mean()
        ma_long = close.rolling(self.ma_long).mean()
        ma_extra_long = close.rolling(self.ma_extra_long).mean()
        rsi_value = float(am.rsi(self.rsi_length))
        dif, dea, hist = self._calculate_macd(close)

        breakout_up = False
        breakout_down = False
        if len(history) >= self.donchian_entry_period + 1:
            entry_source = history.iloc[:-1].tail(self.donchian_entry_period)
            upper = float(entry_source["high"].max())
            lower = float(entry_source["low"].min())
            close_last = float(history["close"].iloc[-1])
            breakout_up = close_last > upper
            breakout_down = close_last < lower

        required_values = [
            ma_short.iloc[-1],
            ma_mid.iloc[-1],
            ma_long.iloc[-1],
            ma_extra_long.iloc[-1],
            ma_short.iloc[-2],
            ma_mid.iloc[-2],
            ma_long.iloc[-2],
            ma_extra_long.iloc[-2],
            dif.iloc[-1],
            dif.iloc[-2],
            dea.iloc[-1],
            dea.iloc[-2],
            hist.iloc[-1],
        ]
        if any(pd.isna(value) for value in required_values):
            return self._signal_result("", False, False, float("nan"), "regular", False)

        short_y, short_t = float(ma_short.iloc[-2]), float(ma_short.iloc[-1])
        mid_y, mid_t = float(ma_mid.iloc[-2]), float(ma_mid.iloc[-1])
        long_y, long_t = float(ma_long.iloc[-2]), float(ma_long.iloc[-1])
        extra_y, extra_t = float(ma_extra_long.iloc[-2]), float(ma_extra_long.iloc[-1])

        golden_5_10 = short_y <= mid_y and short_t > mid_t
        death_5_10 = short_y >= mid_y and short_t < mid_t
        golden_10_20 = mid_y <= long_y and mid_t > long_t
        death_10_20 = mid_y >= long_y and mid_t < long_t
        golden_20_40 = long_y <= extra_y and long_t > extra_t
        death_20_40 = long_y >= extra_y and long_t < extra_t

        bullish_alignment = short_t > mid_t > long_t > extra_t
        bearish_alignment = short_t < mid_t < long_t < extra_t

        macd_hist_t = float(hist.iloc[-1])
        macd_golden = float(dif.iloc[-2]) <= float(dea.iloc[-2]) and float(dif.iloc[-1]) > float(dea.iloc[-1])
        macd_death = float(dif.iloc[-2]) >= float(dea.iloc[-2]) and float(dif.iloc[-1]) < float(dea.iloc[-1])

        allow_long = macd_hist_t > 0
        allow_short = macd_hist_t < 0
        if self.enable_rsi_filter:
            allow_long = allow_long and rsi_value <= self.rsi_long_max
            allow_short = allow_short and rsi_value >= self.rsi_short_min

        signal = ""
        risk_mode = "regular"
        breakout = False
        if (golden_5_10 or death_5_10) and not (golden_10_20 or death_10_20 or golden_20_40 or death_20_40):
            if golden_5_10 and bullish_alignment and allow_long:
                signal = "long_case1a"
                breakout = breakout_up
            elif death_5_10 and bearish_alignment and allow_short:
                signal = "short_case1a"
                breakout = breakout_down
        elif golden_10_20 or death_10_20 or golden_20_40 or death_20_40:
            if (golden_10_20 or golden_20_40) and bullish_alignment and allow_long:
                signal = "long_case2"
                breakout = breakout_up
            elif (death_10_20 or death_20_40) and bearish_alignment and allow_short:
                signal = "short_case2"
                breakout = breakout_down
        else:
            if macd_golden and bullish_alignment and allow_long:
                signal = "long_case3"
                breakout = breakout_up
            elif macd_death and bearish_alignment and allow_short:
                signal = "short_case3"
                breakout = breakout_down

        if signal and not self._passes_entry_filters(signal, history):
            signal = ""
            risk_mode = "regular"
            breakout = False

        if signal:
            volume_oi_risk_mode = self._volume_open_interest_risk_mode(history)
            if volume_oi_risk_mode:
                risk_mode = volume_oi_risk_mode
            else:
                open_interest_risk_mode = self._open_interest_risk_mode(history)
                if open_interest_risk_mode:
                    risk_mode = open_interest_risk_mode

        return self._signal_result(
            signal,
            bullish_alignment,
            bearish_alignment,
            float(ma_long.iloc[-1]),
            risk_mode,
            breakout,
            rsi_value,
        )

    def _open_interest_risk_mode(self, history: pd.DataFrame) -> str:
        if "open_interest" not in history.columns or len(history) < 4:
            return ""

        open_interest = pd.to_numeric(history["open_interest"], errors="coerce")
        if open_interest.iloc[-4:].isna().any():
            return ""

        latest_two_sum = float(open_interest.iloc[-1] + open_interest.iloc[-2])
        previous_two_sum = float(open_interest.iloc[-3] + open_interest.iloc[-4])
        if previous_two_sum <= 0:
            return ""

        if latest_two_sum > previous_two_sum:
            return "open_interest_surge"
        if latest_two_sum < previous_two_sum:
            return "open_interest_decline"
        return ""

    def _volume_open_interest_risk_mode(self, history: pd.DataFrame) -> str:
        if "volume" not in history.columns or "open_interest" not in history.columns or len(history) < 4:
            return ""

        volume = pd.to_numeric(history["volume"], errors="coerce")
        open_interest = pd.to_numeric(history["open_interest"], errors="coerce")
        if volume.iloc[-4:].isna().any() or open_interest.iloc[-4:].isna().any():
            return ""

        latest_volume_sum = float(volume.iloc[-1] + volume.iloc[-2])
        previous_volume_sum = float(volume.iloc[-3] + volume.iloc[-4])
        latest_oi_sum = float(open_interest.iloc[-1] + open_interest.iloc[-2])
        previous_oi_sum = float(open_interest.iloc[-3] + open_interest.iloc[-4])

        if previous_volume_sum <= 0 or previous_oi_sum <= 0:
            return ""

        if latest_volume_sum > previous_volume_sum * 2.0 and latest_oi_sum > previous_oi_sum:
            return "volume_open_interest_surge"
        return ""

    def _signal_result(
        self,
        signal: str,
        bullish_alignment: bool,
        bearish_alignment: bool,
        ma_long_value: float,
        risk_mode: str,
        breakout: bool,
        rsi_value: float = float("nan"),
    ) -> dict[str, Any]:
        return {
            "signal": signal,
            "bullish_alignment": bullish_alignment,
            "bearish_alignment": bearish_alignment,
            "ma_long_value": ma_long_value,
            "risk_mode": risk_mode,
            "breakout": breakout,
            "rsi_value": rsi_value,
        }

    @staticmethod
    def _calculate_macd(close: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
        ema_fast = close.ewm(span=12, adjust=False).mean()
        ema_slow = close.ewm(span=26, adjust=False).mean()
        dif = ema_fast - ema_slow
        dea = dif.ewm(span=9, adjust=False).mean()
        hist = (dif - dea) * 2
        return dif, dea, hist
