from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from vnpy.trader.constant import Direction, Interval
from vnpy.trader.object import BarData, TradeData
from vnpy.trader.utility import ArrayManager
from vnpy_portfoliostrategy import StrategyEngine, StrategyTemplate


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
class SymbolState:
    direction: str = ""
    layers: list[PositionLayer] = field(default_factory=list)
    last_signal: str = ""
    entry_date: str = ""
    last_add_date: str = ""
    last_donchian_add_date: str = ""

    def reset(self) -> None:
        self.direction = ""
        self.layers.clear()
        self.last_signal = ""
        self.entry_date = ""
        self.last_add_date = ""
        self.last_donchian_add_date = ""

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


class QmtAlignmentPortfolioStrategy(StrategyTemplate):
    """
    vn.py portfolio migration of the user's QMT futures CTA.

    Current migrated scope:
    - multi-symbol daily portfolio processing
    - MA/MACD/RSI driven entries
    - risk-based position sizing
    - layered regular add-ons and Donchian add-ons
    - fixed stop, profit-lock trailing stop, MA stop and 2ATR stop lift
    - portfolio capital usage cap and loss-streak risk multiplier

    Remaining gaps to reach closer 1:1 parity:
    - QMT account/trade-detail recovery and persistence
    - live order model differences and external notification pipeline
    - exchange-specific contract rollover controls and QMT-only metadata
    """

    author: str = "GPT-5.4"

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

    fixed_size: int = 1
    min_position_size: int = 1
    max_position_size: int = 50000
    max_concurrent_positions: int = 10
    capital_base: float = 0.0
    max_capital_usage_ratio: float = 0.9
    risk_ratio_of_total_assets: float = 0.01
    risk_ratio_breakout: float = 0.01
    risk_ratio_ma_cross_breakout: float = 0.01
    min_risk_per_trade: float = 1000.0
    max_risk_per_trade: float = 50_000_000.0
    default_margin_ratio: float = 0.10
    margin_ratio_overrides: str = ""
    streak_risk_multipliers: str = "1.0,1.0,1.0,0.1"
    enable_risk_cluster_margin_cap: bool = False
    risk_cluster_margin_cap_ratio: float = 0.35
    risk_cluster_target_clusters: str = ""
    risk_cluster_map: str = ""

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
    risk_cluster_margin_in_use: float = 0.0
    current_risk_per_trade: float = 0.0
    risk_multiplier: float = 1.0
    loss_streak: int = 0

    parameters: list[str] = [
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
        "fixed_size",
        "min_position_size",
        "max_position_size",
        "max_concurrent_positions",
        "capital_base",
        "max_capital_usage_ratio",
        "risk_ratio_of_total_assets",
        "risk_ratio_breakout",
        "risk_ratio_ma_cross_breakout",
        "min_risk_per_trade",
        "max_risk_per_trade",
        "default_margin_ratio",
        "margin_ratio_overrides",
        "streak_risk_multipliers",
        "enable_risk_cluster_margin_cap",
        "risk_cluster_margin_cap_ratio",
        "risk_cluster_target_clusters",
        "risk_cluster_map",
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
        "risk_cluster_margin_in_use",
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

        am_size: int = max(self.ma_extra_long + self.donchian_entry_period + 20, 120)
        self.ams: dict[str, ArrayManager] = {
            vt_symbol: ArrayManager(am_size) for vt_symbol in self.vt_symbols
        }
        self.states: dict[str, SymbolState] = {
            vt_symbol: SymbolState() for vt_symbol in self.vt_symbols
        }
        self.base_capital: float = self._resolve_base_capital()
        self.cluster_margin_usage: dict[str, float] = {}

    def on_init(self) -> None:
        self.write_log("Portfolio migration strategy initialized")
        self.load_bars(self.warmup_days, interval=Interval.DAILY)

    def on_start(self) -> None:
        self.write_log("Portfolio migration strategy started")

    def on_stop(self) -> None:
        self.write_log("Portfolio migration strategy stopped")

    def update_trade(self, trade: TradeData) -> None:
        super().update_trade(trade)

    def on_bars(self, bars: dict[str, BarData]) -> None:
        for vt_symbol, bar in bars.items():
            self.ams[vt_symbol].update_bar(bar)

        self._refresh_risk_state(bars)
        planned_active_count: int = self._count_active_positions()
        self.last_signal = ""

        for vt_symbol, bar in bars.items():
            am: ArrayManager = self.ams[vt_symbol]
            if not am.inited:
                continue

            history: pd.DataFrame = self._build_history_df(am)
            signal_data: dict[str, Any] = self._generate_signal(am, history)
            signal: str = str(signal_data["signal"])
            bullish: bool = bool(signal_data["bullish_alignment"])
            bearish: bool = bool(signal_data["bearish_alignment"])
            ma_long_value: float = float(signal_data["ma_long_value"])

            current_pos: int = self.get_pos(vt_symbol)
            state: SymbolState = self.states[vt_symbol]
            self._reconcile_state_with_position(state, current_pos, bar)

            if current_pos == 0:
                state.reset()

                if signal.startswith("long") and self.long_entry_enabled:
                    if planned_active_count >= self.max_concurrent_positions:
                        continue

                    volume: int = self._calculate_entry_volume(vt_symbol, "long", bar, history, signal_data)
                    if volume <= 0:
                        continue

                    self._open_position(state, "long", volume, bar, signal, history)
                    self._apply_state_target(vt_symbol, state)
                    self.last_signal = f"{vt_symbol}:{signal}"
                    planned_active_count += 1
                elif signal.startswith("short") and self.short_entry_enabled:
                    if planned_active_count >= self.max_concurrent_positions:
                        continue

                    volume = self._calculate_entry_volume(vt_symbol, "short", bar, history, signal_data)
                    if volume <= 0:
                        continue

                    self._open_position(state, "short", volume, bar, signal, history)
                    self._apply_state_target(vt_symbol, state)
                    self.last_signal = f"{vt_symbol}:{signal}"
                    planned_active_count += 1
                continue

            if not state.layers:
                continue

            self._update_dynamic_stops(state, bar, history)

            layer_exit_reason: str = self._process_layer_stops(vt_symbol, state, bar)
            if layer_exit_reason:
                self._apply_state_target(vt_symbol, state)
                self.last_signal = f"{vt_symbol}:{layer_exit_reason}"
                if state.active_volume() == 0:
                    planned_active_count -= 1
                continue

            if self.enable_ma_trend_stop:
                if state.direction == "long" and float(bar.close_price) < ma_long_value:
                    self._close_all_layers(vt_symbol, state, float(bar.close_price), "long_ma_stop")
                    self.set_target(vt_symbol, 0)
                    self.last_signal = f"{vt_symbol}:long_ma_stop"
                    planned_active_count -= 1
                    continue
                if state.direction == "short" and float(bar.close_price) > ma_long_value:
                    self._close_all_layers(vt_symbol, state, float(bar.close_price), "short_ma_stop")
                    self.set_target(vt_symbol, 0)
                    self.last_signal = f"{vt_symbol}:short_ma_stop"
                    planned_active_count -= 1
                    continue

            if state.direction == "long":
                if self.exit_on_alignment_break and not bullish:
                    self._close_all_layers(vt_symbol, state, float(bar.close_price), "long_exit_alignment")
                    self.set_target(vt_symbol, 0)
                    self.last_signal = f"{vt_symbol}:long_exit_alignment"
                    planned_active_count -= 1
                    continue

                if signal.startswith("short"):
                    self._close_all_layers(vt_symbol, state, float(bar.close_price), "long_exit_reverse")
                    if self.short_entry_enabled:
                        volume = self._calculate_entry_volume(vt_symbol, "short", bar, history, signal_data)
                        if volume > 0:
                            self._open_position(state, "short", volume, bar, signal, history)
                            self._apply_state_target(vt_symbol, state)
                            self.last_signal = f"{vt_symbol}:{signal}"
                        else:
                            self.set_target(vt_symbol, 0)
                    else:
                        self.set_target(vt_symbol, 0)
                        planned_active_count -= 1
                        self.last_signal = f"{vt_symbol}:long_exit_reverse"
                    continue
            else:
                if self.exit_on_alignment_break and not bearish:
                    self._close_all_layers(vt_symbol, state, float(bar.close_price), "short_exit_alignment")
                    self.set_target(vt_symbol, 0)
                    self.last_signal = f"{vt_symbol}:short_exit_alignment"
                    planned_active_count -= 1
                    continue

                if signal.startswith("long"):
                    self._close_all_layers(vt_symbol, state, float(bar.close_price), "short_exit_reverse")
                    if self.long_entry_enabled:
                        volume = self._calculate_entry_volume(vt_symbol, "long", bar, history, signal_data)
                        if volume > 0:
                            self._open_position(state, "long", volume, bar, signal, history)
                            self._apply_state_target(vt_symbol, state)
                            self.last_signal = f"{vt_symbol}:{signal}"
                        else:
                            self.set_target(vt_symbol, 0)
                    else:
                        self.set_target(vt_symbol, 0)
                        planned_active_count -= 1
                        self.last_signal = f"{vt_symbol}:short_exit_reverse"
                    continue

            can_add, add_type = self._check_regular_add_conditions(state, bar, history)
            if can_add and add_type:
                add_volume: int = self._calculate_regular_add_volume(vt_symbol, state, bar)
                if add_volume > 0 and self._can_allocate_margin(vt_symbol, add_volume, bar.close_price, state.direction):
                    self._execute_regular_add(state, bar, signal=add_type, volume=add_volume, history=history)
                    self._apply_state_target(vt_symbol, state)
                    self.last_signal = f"{vt_symbol}:{add_type}"
                    continue

            can_don_add, don_add_type = self._check_donchian_add_conditions(state, bar, history)
            if can_don_add and don_add_type:
                add_volume = self._calculate_donchian_add_volume(vt_symbol, state)
                if add_volume > 0 and self._can_allocate_margin(vt_symbol, add_volume, bar.close_price, state.direction):
                    self._execute_donchian_add(state, bar, signal=don_add_type, volume=add_volume, history=history)
                    self._apply_state_target(vt_symbol, state)
                    self.last_signal = f"{vt_symbol}:{don_add_type}"

        self.rebalance_portfolio(bars)
        self.active_count = self._count_active_positions()
        self.put_event()

    def calculate_price(
        self,
        vt_symbol: str,
        direction: Direction,
        reference: float,
    ) -> float:
        pricetick: float = self.get_pricetick(vt_symbol)

        if direction == Direction.LONG:
            return reference + self.tick_add * pricetick
        return reference - self.tick_add * pricetick

    def _refresh_risk_state(self, bars: dict[str, BarData]) -> None:
        self.estimated_equity = self._estimate_equity(bars)
        self.total_margin_in_use = self._estimate_margin_usage(bars)
        self.cluster_margin_usage = self._estimate_margin_usage_by_cluster(bars)
        self.risk_cluster_margin_in_use = max(self.cluster_margin_usage.values(), default=0.0)
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

        for vt_symbol, state in self.states.items():
            bar: BarData | None = bars.get(vt_symbol)
            if not bar or not state.layers:
                continue

            size: int = self.get_size(vt_symbol)
            close_price: float = float(bar.close_price)
            for layer in state.layers:
                if layer.direction == "long":
                    pnl: float = (close_price - layer.entry_price) * size * layer.volume
                else:
                    pnl = (layer.entry_price - close_price) * size * layer.volume
                equity += pnl

        return equity

    def _estimate_margin_usage(self, bars: dict[str, BarData]) -> float:
        total_margin: float = 0.0

        for vt_symbol, state in self.states.items():
            bar: BarData | None = bars.get(vt_symbol)
            if not bar or not state.layers:
                continue

            size: int = self.get_size(vt_symbol)
            close_price: float = float(bar.close_price)
            margin_ratio: float = self._margin_ratio_for_symbol(vt_symbol)
            total_margin += abs(close_price * size * state.active_volume() * margin_ratio)

        return total_margin

    def _estimate_margin_usage_by_cluster(self, bars: dict[str, BarData]) -> dict[str, float]:
        usage: dict[str, float] = {}
        for vt_symbol, state in self.states.items():
            bar: BarData | None = bars.get(vt_symbol)
            if not bar or not state.layers:
                continue

            cluster: str = self._risk_cluster_for_symbol(vt_symbol)
            if not cluster:
                continue

            size: int = self.get_size(vt_symbol)
            close_price: float = float(bar.close_price)
            margin_ratio: float = self._margin_ratio_for_symbol(vt_symbol)
            margin: float = abs(close_price * size * state.active_volume() * margin_ratio)
            usage[cluster] = usage.get(cluster, 0.0) + margin
        return usage

    def _limited_available_balance(self) -> float:
        allowed_capital: float = max(0.0, self.estimated_equity * self.max_capital_usage_ratio)
        free_capital: float = max(0.0, self.estimated_equity - self.total_margin_in_use)
        return max(0.0, min(free_capital, allowed_capital))

    def _risk_amount_from_ratio(self, risk_ratio: float, limited_balance: float) -> float:
        dynamic_risk: float = limited_balance * risk_ratio
        dynamic_risk = max(self.min_risk_per_trade, dynamic_risk)
        dynamic_risk = min(self.max_risk_per_trade, dynamic_risk)
        dynamic_risk *= self._current_streak_multiplier()
        return max(0.0, dynamic_risk)

    def _current_streak_multiplier(self) -> float:
        multipliers: list[float] = self._parse_float_list(self.streak_risk_multipliers, [1.0, 1.0, 1.0, 0.1])
        tier: int = min(self.loss_streak, len(multipliers) - 1)
        return max(0.0, multipliers[tier])

    def _calculate_entry_volume(
        self,
        vt_symbol: str,
        direction: str,
        bar: BarData,
        history: pd.DataFrame,
        signal_data: dict[str, Any],
    ) -> int:
        if self.fixed_size > 0:
            return int(self.fixed_size)

        limited_balance: float = self._limited_available_balance()
        risk_mode: str = str(signal_data.get("risk_mode", "regular"))
        if risk_mode == "ma_cross_breakout":
            risk_ratio: float = self.risk_ratio_ma_cross_breakout
        elif risk_mode == "breakout":
            risk_ratio = self.risk_ratio_breakout
        else:
            risk_ratio = self.risk_ratio_of_total_assets

        risk_amount: float = self._risk_amount_from_ratio(risk_ratio, limited_balance)
        stop_price: float = self._entry_stop_price(direction, bar, history, use_day_extreme=True)
        size: int = self.get_size(vt_symbol)
        risk_per_contract: float = abs(float(bar.close_price) - stop_price) * size

        min_risk: float = max(float(self.get_pricetick(vt_symbol)) * size, 1.0)
        if risk_per_contract < min_risk:
            risk_per_contract = min_risk

        contracts_by_risk: int = int(risk_amount // risk_per_contract) if risk_per_contract > 0 else 0

        margin_ratio: float = self._margin_ratio_for_symbol(vt_symbol)
        margin_per_contract: float = float(bar.close_price) * size * margin_ratio
        contracts_by_margin: int = int(limited_balance // margin_per_contract) if margin_per_contract > 0 else 0

        volume: int = min(contracts_by_risk, contracts_by_margin, self.max_position_size)
        volume = min(volume, self._max_volume_by_cluster_margin_cap(vt_symbol, float(bar.close_price), direction))
        if 0 < volume < self.min_position_size:
            return 0
        return max(0, volume)

    def _count_active_positions(self) -> int:
        return sum(1 for vt_symbol in self.vt_symbols if self.get_pos(vt_symbol) != 0)

    def _open_position(
        self,
        state: SymbolState,
        direction: str,
        volume: int,
        bar: BarData,
        signal: str,
        history: pd.DataFrame,
    ) -> None:
        state.reset()
        state.direction = direction
        state.entry_date = self._bar_date(bar)
        state.last_signal = signal
        state.layers.append(
            PositionLayer(
                kind="base",
                direction=direction,
                volume=max(1, int(volume)),
                entry_price=float(bar.close_price),
                stop_price=self._entry_stop_price(direction, bar, history, use_day_extreme=True),
                highest_price=float(bar.high_price),
                lowest_price=float(bar.low_price),
                signal=signal,
                entry_date=state.entry_date,
                margin_ratio=self._margin_ratio_for_symbol(bar.vt_symbol),
            )
        )

    def _append_layer(
        self,
        state: SymbolState,
        kind: str,
        volume: int,
        bar: BarData,
        signal: str,
        history: pd.DataFrame,
        use_day_extreme_stop: bool = True,
    ) -> None:
        direction: str = state.direction
        entry_date: str = self._bar_date(bar)
        stop_price: float = self._entry_stop_price(direction, bar, history, use_day_extreme=use_day_extreme_stop)

        state.layers.append(
            PositionLayer(
                kind=kind,
                direction=direction,
                volume=max(1, int(volume)),
                entry_price=float(bar.close_price),
                stop_price=stop_price,
                highest_price=float(bar.high_price),
                lowest_price=float(bar.low_price),
                signal=signal,
                entry_date=entry_date,
                margin_ratio=self._margin_ratio_for_symbol(bar.vt_symbol),
            )
        )

    def _apply_state_target(self, vt_symbol: str, state: SymbolState) -> None:
        volume: int = state.active_volume()
        if state.direction == "short":
            self.set_target(vt_symbol, -volume)
        else:
            self.set_target(vt_symbol, volume)

    def _reconcile_state_with_position(
        self,
        state: SymbolState,
        current_pos: int,
        bar: BarData,
    ) -> None:
        if current_pos == 0:
            if state.layers:
                state.reset()
            return

        actual_direction: str = "long" if current_pos > 0 else "short"
        actual_volume: int = abs(int(current_pos))

        if not state.layers or state.direction != actual_direction:
            state.reset()
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

    def _process_layer_stops(self, vt_symbol: str, state: SymbolState, bar: BarData) -> str:
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
            self._close_all_layers(vt_symbol, state, float(bar.close_price), f"{direction}_base_stop")
            return f"{direction}_base_stop"

        if not triggered_indexes:
            return ""

        self._close_layers(vt_symbol, state, triggered_indexes, float(bar.close_price), f"{direction}_layer_stop")
        if not state.layers:
            return f"{direction}_layer_stop_all"
        return f"{direction}_layer_stop_partial"

    def _update_dynamic_stops(self, state: SymbolState, bar: BarData, history: pd.DataFrame) -> None:
        for layer in state.layers:
            self._update_layer_stop(layer, bar)

        if self.atr_2x_mid_stop_enabled:
            self._apply_atr_mid_stop(state, bar, history)

        if state.active_volume() > state.base_volume():
            self._apply_add_position_profit_lock(state)

    def _update_layer_stop(self, layer: PositionLayer, bar: BarData) -> None:
        close_price: float = float(bar.close_price)

        if layer.direction == "long":
            layer.highest_price = max(layer.highest_price, float(bar.high_price))
            layer.lowest_price = min(layer.lowest_price, float(bar.low_price))
            pnl_pct: float = (close_price - layer.entry_price) / layer.entry_price if layer.entry_price else 0.0
        else:
            layer.highest_price = max(layer.highest_price, float(bar.high_price))
            layer.lowest_price = min(layer.lowest_price, float(bar.low_price))
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
                trailing_stop: float = layer.highest_price * (1 - self.trailing_stop_pct)
                layer.stop_price = max(layer.stop_price, trailing_stop)
            else:
                trailing_stop = layer.lowest_price * (1 + self.trailing_stop_pct)
                layer.stop_price = min(layer.stop_price, trailing_stop)

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
                if layer.direction == "long":
                    return layer.entry_price * (1 + lock_pct)
                return layer.entry_price * (1 - lock_pct)
        return None

    def _apply_add_position_profit_lock(self, state: SymbolState) -> None:
        avg_price: float = state.avg_entry_price()
        if avg_price <= 0:
            return

        if state.direction == "long":
            min_stop_price: float = avg_price * (1 + self.add_position_min_profit)
            for layer in state.layers:
                layer.stop_price = max(layer.stop_price, min_stop_price)
        else:
            min_stop_price = avg_price * (1 - self.add_position_min_profit)
            for layer in state.layers:
                layer.stop_price = min(layer.stop_price, min_stop_price)

    def _apply_atr_mid_stop(self, state: SymbolState, bar: BarData, history: pd.DataFrame) -> None:
        if len(history) < 15:
            return

        closes: pd.Series = history["close"]
        highs: pd.Series = history["high"]
        lows: pd.Series = history["low"]
        prev_close: pd.Series = closes.shift(1)
        tr: pd.Series = pd.concat(
            [(highs - lows).abs(), (highs - prev_close).abs(), (lows - prev_close).abs()],
            axis=1,
        ).max(axis=1)
        atr: pd.Series = tr.rolling(14).mean()

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

    def _close_layers(
        self,
        vt_symbol: str,
        state: SymbolState,
        indexes: list[int],
        exit_price: float,
        reason: str,
    ) -> None:
        size: int = self.get_size(vt_symbol)
        realized: float = 0.0
        for index in sorted(indexes, reverse=True):
            layer: PositionLayer = state.layers[index]
            realized += self._layer_realized_pnl(layer, exit_price, size)
            del state.layers[index]

        self.realized_pnl += realized
        self._update_streak_risk_state(realized)
        if not state.layers:
            state.reset()

    def _close_all_layers(
        self,
        vt_symbol: str,
        state: SymbolState,
        exit_price: float,
        reason: str,
    ) -> None:
        indexes: list[int] = list(range(len(state.layers)))
        if indexes:
            self._close_layers(vt_symbol, state, indexes, exit_price, reason)
        state.reset()

    def _layer_realized_pnl(self, layer: PositionLayer, exit_price: float, size: int) -> float:
        if layer.direction == "long":
            return (exit_price - layer.entry_price) * size * layer.volume
        return (layer.entry_price - exit_price) * size * layer.volume

    def _update_streak_risk_state(self, realized_pnl: float) -> None:
        if realized_pnl < 0:
            self.loss_streak += 1
        elif realized_pnl > 0:
            self.loss_streak = 0
        self.risk_multiplier = self._current_streak_multiplier()

    def _check_regular_add_conditions(
        self,
        state: SymbolState,
        bar: BarData,
        history: pd.DataFrame,
    ) -> tuple[bool, str | None]:
        if not self.enable_add_position:
            return False, None

        add_count: int = self._count_layers(state, "add")
        if add_count >= self.max_add_layers:
            return False, None

        if self.restrict_regular_add_to_first and add_count > 0:
            return False, None

        today_key: str = self._bar_date(bar)
        if state.last_add_date == today_key or state.entry_date == today_key:
            return False, None

        avg_price: float = state.avg_entry_price()
        if avg_price <= 0:
            return False, None

        current_price: float = float(bar.close_price)
        if state.direction == "long":
            profit_pct: float = (current_price - avg_price) / avg_price
        else:
            profit_pct = (avg_price - current_price) / avg_price

        threshold: float = (
            self.add_position_threshold
            if add_count == 0
            else self.second_add_position_threshold
        )
        if profit_pct < threshold:
            return False, None

        if len(history) < 2:
            return False, None

        if self.require_reversal_for_add:
            yesterday = history.iloc[-2]
            today = history.iloc[-1]
            if state.direction == "long":
                reversal_ok: bool = (
                    float(yesterday["close"]) < float(yesterday["open"])
                    and float(today["close"]) > float(today["open"])
                )
            else:
                reversal_ok = (
                    float(yesterday["close"]) > float(yesterday["open"])
                    and float(today["close"]) < float(today["open"])
                )
            if not reversal_ok:
                return False, None

        if state.direction == "long" and float(bar.close_price) < float(bar.open_price):
            return False, None
        if state.direction == "short" and float(bar.close_price) > float(bar.open_price):
            return False, None

        if self.wick_chop_filter_enabled:
            ok, _, _ = self._wick_chop_filter_ok(
                history,
                lookback=self.wick_chop_filter_lookback,
                max_days=self.wick_chop_filter_max_days,
            )
            if not ok:
                return False, None

        add_type: str = "first_add" if add_count == 0 else f"add_{add_count + 1}"
        return True, add_type

    def _calculate_regular_add_volume(self, vt_symbol: str, state: SymbolState, bar: BarData) -> int:
        base_volume: int = max(1, state.base_volume())
        add_volume: int = max(1, int(round(base_volume * self.regular_add_volume_multiplier)))
        return min(add_volume, self.max_position_size)

    def _execute_regular_add(
        self,
        state: SymbolState,
        bar: BarData,
        signal: str,
        volume: int,
        history: pd.DataFrame,
    ) -> None:
        self._append_layer(
            state,
            kind="add",
            volume=volume,
            bar=bar,
            signal=signal,
            history=history,
            use_day_extreme_stop=self.regular_add_use_day_extreme_stop,
        )
        state.last_add_date = self._bar_date(bar)
        state.last_signal = signal
        self._apply_add_position_profit_lock(state)

    def _check_donchian_add_conditions(
        self,
        state: SymbolState,
        bar: BarData,
        history: pd.DataFrame,
    ) -> tuple[bool, str | None]:
        if not self.enable_donchian_add_position:
            return False, None

        add_count: int = self._count_layers(state, "donchian")
        if add_count >= self.donchian_add_max_layers:
            return False, None

        today_key: str = self._bar_date(bar)
        if state.last_donchian_add_date == today_key:
            return False, None

        period: int = max(int(self.donchian_add_period), 1)
        if len(history) < period + 1:
            return False, None

        channel_source: pd.DataFrame = history.iloc[:-1].tail(period)
        upper: float = float(channel_source["high"].max())
        lower: float = float(channel_source["low"].min())
        close_price: float = float(bar.close_price)

        if state.direction == "long" and close_price > upper:
            return True, f"donchian_add_{add_count + 1}"
        if state.direction == "short" and close_price < lower:
            return True, f"donchian_add_{add_count + 1}"
        return False, None

    def _calculate_donchian_add_volume(self, vt_symbol: str, state: SymbolState) -> int:
        base_volume: int = max(1, state.base_volume())
        multipliers: list[float] = self._parse_float_list(self.donchian_add_volume_multipliers, [2.0, 1.0])
        add_index: int = self._count_layers(state, "donchian")
        multiplier: float = multipliers[add_index] if add_index < len(multipliers) else multipliers[-1]
        add_volume: int = max(1, int(round(base_volume * multiplier)))
        return min(add_volume, self.max_position_size)

    def _execute_donchian_add(
        self,
        state: SymbolState,
        bar: BarData,
        signal: str,
        volume: int,
        history: pd.DataFrame,
    ) -> None:
        self._append_layer(
            state,
            kind="donchian",
            volume=volume,
            bar=bar,
            signal=signal,
            history=history,
            use_day_extreme_stop=True,
        )
        state.last_donchian_add_date = self._bar_date(bar)
        state.last_signal = signal
        self._apply_add_position_profit_lock(state)

    def _can_allocate_margin(self, vt_symbol: str, volume: int, price: float, direction: str) -> bool:
        margin_ratio: float = self._margin_ratio_for_symbol(vt_symbol)
        projected_margin: float = price * self.get_size(vt_symbol) * volume * margin_ratio
        allowed_capital: float = max(0.0, self.estimated_equity * self.max_capital_usage_ratio)
        if (self.total_margin_in_use + projected_margin) > allowed_capital:
            return False

        if not self.enable_risk_cluster_margin_cap:
            return True

        cluster: str = self._risk_cluster_for_symbol(vt_symbol)
        if not self._cluster_cap_applies(cluster):
            return True

        cap: float = max(0.0, self.estimated_equity * float(self.risk_cluster_margin_cap_ratio))
        current: float = float(self.cluster_margin_usage.get(cluster, 0.0) or 0.0)
        return (current + projected_margin) <= cap

    def _build_history_df(self, am: ArrayManager) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "open": pd.Series(am.open_array, dtype="float64"),
                "high": pd.Series(am.high_array, dtype="float64"),
                "low": pd.Series(am.low_array, dtype="float64"),
                "close": pd.Series(am.close_array, dtype="float64"),
            }
        )

    def _entry_stop_price(
        self,
        direction: str,
        bar: BarData,
        history: pd.DataFrame,
        use_day_extreme: bool,
    ) -> float:
        basic_long: float = float(bar.close_price) * (1 - self.stop_loss_pct)
        basic_short: float = float(bar.close_price) * (1 + self.stop_loss_pct)

        recent3: pd.DataFrame = history.tail(3) if len(history) >= 3 else history
        if not recent3.empty:
            min_low: float = float(recent3["low"].min())
            max_high: float = float(recent3["high"].max())
        else:
            min_low = float(bar.low_price)
            max_high = float(bar.high_price)

        smart_long: float = max(basic_long, min_low)
        smart_short: float = min(basic_short, max_high)

        if use_day_extreme:
            if direction == "long":
                return max(float(bar.low_price), smart_long)
            return min(float(bar.high_price), smart_short)

        if direction == "long":
            return smart_long
        return smart_short

    def _simple_stop_price(self, direction: str, close_price: float) -> float:
        if direction == "long":
            return close_price * (1 - self.stop_loss_pct)
        return close_price * (1 + self.stop_loss_pct)

    def _count_layers(self, state: SymbolState, kind: str) -> int:
        return sum(1 for layer in state.layers if layer.kind == kind)

    def _margin_ratio_for_symbol(self, vt_symbol: str) -> float:
        overrides: dict[str, float] = self._parse_mapping(self.margin_ratio_overrides)
        if vt_symbol in overrides:
            return overrides[vt_symbol]
        return max(0.0, self.default_margin_ratio)

    def _risk_cluster_for_symbol(self, vt_symbol: str) -> str:
        mapping: dict[str, str] = self._parse_string_mapping(self.risk_cluster_map)
        product_symbol: str = self._product_vt_symbol(vt_symbol)
        normalized_product: str = product_symbol
        if "." in product_symbol:
            symbol, exchange = product_symbol.split(".", 1)
            normalized_product = f"{symbol.lower()}.{exchange.upper()}"
        keys: list[str] = [str(vt_symbol), product_symbol, normalized_product]
        for key in keys:
            if key and key in mapping:
                return mapping[key]
        return ""

    def _cluster_cap_applies(self, cluster: str) -> bool:
        if not cluster:
            return False
        targets = {
            item.strip()
            for item in str(self.risk_cluster_target_clusters or "").replace(";", ",").split(",")
            if item.strip()
        }
        return not targets or cluster in targets

    def _max_volume_by_cluster_margin_cap(self, vt_symbol: str, price: float, direction: str) -> int:
        if not self.enable_risk_cluster_margin_cap:
            return self.max_position_size

        cluster: str = self._risk_cluster_for_symbol(vt_symbol)
        if not self._cluster_cap_applies(cluster):
            return self.max_position_size

        margin_ratio: float = self._margin_ratio_for_symbol(vt_symbol)
        margin_per_contract: float = float(price) * self.get_size(vt_symbol) * margin_ratio
        if margin_per_contract <= 0:
            return 0

        cap: float = max(0.0, self.estimated_equity * float(self.risk_cluster_margin_cap_ratio))
        current: float = float(self.cluster_margin_usage.get(cluster, 0.0) or 0.0)
        remaining: float = max(0.0, cap - current)
        return max(0, int(remaining // margin_per_contract))

    @staticmethod
    def _product_vt_symbol(vt_symbol: str) -> str:
        text = str(vt_symbol or "")
        if "." not in text:
            return text
        symbol, exchange = text.split(".", 1)
        product = "".join(ch for ch in symbol if not ch.isdigit())
        return f"{product}.{exchange}"

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

    def _parse_string_mapping(self, raw: str) -> dict[str, str]:
        mapping: dict[str, str] = {}
        for item in str(raw or "").replace(";", ",").split(","):
            item = item.strip()
            if not item or "=" not in item:
                continue
            key, value = item.split("=", 1)
            key = key.strip()
            value = value.strip()
            if key and value:
                mapping[key] = value
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
    def _wick_chop_filter_ok(
        market_data_df: pd.DataFrame,
        lookback: int = 10,
        max_days: int = 4,
    ) -> tuple[bool, int, int]:
        df: pd.DataFrame = market_data_df[["open", "high", "low", "close"]].tail(max(int(lookback), 1)).dropna()
        if len(df) < max(int(lookback), 1):
            return True, 0, len(df)

        count: int = 0
        for _, row in df.iterrows():
            o: float = float(row["open"])
            h: float = float(row["high"])
            l: float = float(row["low"])
            c: float = float(row["close"])
            body: float = abs(c - o)
            upper: float = h - max(o, c)
            lower: float = min(o, c) - l
            if upper > body or lower > body:
                count += 1

        return count <= int(max_days), count, len(df)

    def _generate_signal(self, am: ArrayManager, history: pd.DataFrame) -> dict[str, Any]:
        close: pd.Series = pd.Series(am.close_array)

        ma_short: pd.Series = close.rolling(self.ma_short).mean()
        ma_mid: pd.Series = close.rolling(self.ma_mid).mean()
        ma_long: pd.Series = close.rolling(self.ma_long).mean()
        ma_extra_long: pd.Series = close.rolling(self.ma_extra_long).mean()

        rsi_value: float = float(am.rsi(self.rsi_length))
        dif, dea, hist = self._calculate_macd(close)

        breakout_up: bool = False
        breakout_down: bool = False
        if len(history) >= self.donchian_entry_period + 1:
            entry_source: pd.DataFrame = history.iloc[:-1].tail(self.donchian_entry_period)
            upper: float = float(entry_source["high"].max())
            lower: float = float(entry_source["low"].min())
            close_last: float = float(history["close"].iloc[-1])
            breakout_up = close_last > upper
            breakout_down = close_last < lower

        required_values: list[float] = [
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

        golden_5_10: bool = short_y <= mid_y and short_t > mid_t
        death_5_10: bool = short_y >= mid_y and short_t < mid_t
        golden_10_20: bool = mid_y <= long_y and mid_t > long_t
        death_10_20: bool = mid_y >= long_y and mid_t < long_t
        golden_20_40: bool = long_y <= extra_y and long_t > extra_t
        death_20_40: bool = long_y >= extra_y and long_t < extra_t

        bullish_alignment: bool = short_t > mid_t > long_t > extra_t
        bearish_alignment: bool = short_t < mid_t < long_t < extra_t

        macd_hist_t: float = float(hist.iloc[-1])
        macd_golden: bool = float(dif.iloc[-2]) <= float(dea.iloc[-2]) and float(dif.iloc[-1]) > float(dea.iloc[-1])
        macd_death: bool = float(dif.iloc[-2]) >= float(dea.iloc[-2]) and float(dif.iloc[-1]) < float(dea.iloc[-1])

        allow_long: bool = macd_hist_t > 0
        allow_short: bool = macd_hist_t < 0

        if self.enable_rsi_filter:
            allow_long = allow_long and rsi_value <= self.rsi_long_max
            allow_short = allow_short and rsi_value >= self.rsi_short_min

        signal: str = ""
        risk_mode: str = "regular"
        breakout: bool = False

        if (
            (golden_5_10 or death_5_10)
            and not (golden_10_20 or death_10_20 or golden_20_40 or death_20_40)
        ):
            if golden_5_10 and bullish_alignment and allow_long:
                signal = "long_case1a"
                risk_mode = "breakout" if breakout_up else "regular"
                breakout = breakout_up
            elif death_5_10 and bearish_alignment and allow_short:
                signal = "short_case1a"
                risk_mode = "breakout" if breakout_down else "regular"
                breakout = breakout_down

        elif golden_10_20 or death_10_20 or golden_20_40 or death_20_40:
            if (golden_10_20 or golden_20_40) and bullish_alignment and allow_long:
                if (not self.case2_requires_breakout) or breakout_up:
                    signal = "long_case2"
                    risk_mode = "ma_cross_breakout"
                    breakout = breakout_up
            elif (death_10_20 or death_20_40) and bearish_alignment and allow_short:
                if (not self.case2_requires_breakout) or breakout_down:
                    signal = "short_case2"
                    risk_mode = "ma_cross_breakout"
                    breakout = breakout_down

        else:
            if macd_golden and bullish_alignment and allow_long:
                signal = "long_case3"
                risk_mode = "breakout" if breakout_up else "regular"
                breakout = breakout_up
            elif macd_death and bearish_alignment and allow_short:
                signal = "short_case3"
                risk_mode = "breakout" if breakout_down else "regular"
                breakout = breakout_down

        return self._signal_result(
            signal=signal,
            bullish_alignment=bullish_alignment,
            bearish_alignment=bearish_alignment,
            ma_long_value=float(ma_long.iloc[-1]),
            risk_mode=risk_mode,
            breakout=breakout,
        )

    def _signal_result(
        self,
        signal: str,
        bullish_alignment: bool,
        bearish_alignment: bool,
        ma_long_value: float,
        risk_mode: str,
        breakout: bool,
    ) -> dict[str, Any]:
        return {
            "signal": signal,
            "bullish_alignment": bullish_alignment,
            "bearish_alignment": bearish_alignment,
            "ma_long_value": ma_long_value,
            "risk_mode": risk_mode,
            "breakout": breakout,
        }

    @staticmethod
    def _calculate_macd(close: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
        ema_fast: pd.Series = close.ewm(span=12, adjust=False).mean()
        ema_slow: pd.Series = close.ewm(span=26, adjust=False).mean()
        dif: pd.Series = ema_fast - ema_slow
        dea: pd.Series = dif.ewm(span=9, adjust=False).mean()
        hist: pd.Series = (dif - dea) * 2
        return dif, dea, hist
