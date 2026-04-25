from __future__ import annotations

from dataclasses import dataclass, field
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from vnpy.trader.constant import Direction, Interval, Offset
from vnpy.trader.object import BarData, TradeData
from vnpy.trader.utility import ArrayManager
from vnpy_portfoliostrategy import StrategyEngine, StrategyTemplate

from main_contract_mapping import (
    build_contract_metadata,
    build_daily_mapping,
    get_preferred_mapping_path,
    load_product_universe_symbols,
)
from qmt_roll_ai_selection_pairwise_runtime import (
    DEFAULT_MODEL_PATH,
    DEFAULT_SUMMARY_PATH,
    SelectionPairwiseRuntimeModel,
    build_runtime_feature_row,
)


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
    entry_price_synced: bool = False
    profit_giveback_stop_active: bool = False


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


@dataclass
class DailyEntryContext:
    product_vt_symbol: str
    state: ProductState
    target_contract: str
    target_bar: BarData
    actual_bar: BarData | None
    current_pos: int
    history: pd.DataFrame
    signal_data: dict[str, Any]


class QmtRollPortfolioStrategy(StrategyTemplate):
    """
    Main-contract switching backtest version.

    Each product uses the daily dominant contract from mapping table, closes
    the old dominant contract when rollover happens, and optionally reopens
    on the new dominant contract in the same direction.
    """

    author: str = "GPT-5.4"

    mapping_csv_path: str = str(get_preferred_mapping_path())
    product_universe_csv_path: str = ""

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
    sizing_equity_cap: float = 1_000_000.0
    max_capital_usage_ratio: float = 0.9
    max_single_trade_capital_usage_ratio: float = 0.7
    enable_incremental_margin_budget_gate: bool = False
    incremental_margin_budget_gate_usage_ratio: float = -1.0
    incremental_margin_budget_gate_min_openable_candidates: int = 1
    incremental_margin_budget_gate_protected_selection_rank: int = 0
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
    streak_risk_state_excluded_products: str = ""
    streak_risk_state_exclusion_mode: str = "all"
    streak_profit_recovery_mode: str = "reset"
    streak_profit_recovery_confirm_wins: int = 1
    streak_profit_recovery_equity_confirm_drawdown_pct: float = -1.0
    enable_streak_entry_structure_risk_recovery: bool = False
    streak_entry_structure_recovery_signals: str = "long_case1a,short_case1a"
    streak_entry_structure_recovery_min_multiplier: float = 1.0
    streak_entry_structure_recovery_require_flat_portfolio: bool = True
    streak_entry_structure_recovery_max_same_direction_corr: float = 0.30
    streak_entry_structure_recovery_require_rsi_confirmation: bool = False
    streak_entry_structure_recovery_long_min_rsi: float = 60.0
    streak_entry_structure_recovery_short_max_rsi: float = 40.0
    streak_entry_structure_recovery_max_portfolio_drawdown_pct: float = -1.0
    enable_weighted_env_gate: bool = False
    enable_portfolio_env_gate: bool = False
    weighted_env_gate_close_position_good_max: float = 0.25
    weighted_env_gate_close_position_bad_min: float = 0.60
    weighted_env_gate_range_good_min: float = 0.60
    weighted_env_gate_range_bad_max: float = 0.00
    weighted_env_gate_selected_rate_good_max: float = 0.35
    weighted_env_gate_selected_rate_bad_min: float = 0.75
    weighted_env_gate_weight_floor: float = 0.35
    enable_portfolio_drawdown_gate: bool = False
    portfolio_drawdown_gate_start_pct: float = 0.10
    portfolio_drawdown_gate_full_pct: float = 0.25
    portfolio_drawdown_gate_weight_floor: float = 0.50
    enable_same_direction_correlation_gate: bool = False
    same_direction_correlation_gate_lookback: int = 20
    same_direction_correlation_gate_start: float = 0.60
    same_direction_correlation_gate_full: float = 0.80
    same_direction_correlation_gate_weight_floor: float = 0.50
    enable_selection_pairwise_v2: bool = False
    enable_selection_pairwise_v2_catastrophic_veto: bool = False
    enable_selection_pairwise_v2_catastrophic_hard_filter: bool = False
    enable_selection_pairwise_v2_volume_tilt: bool = False
    selection_pairwise_volume_tilt_strength: float = 0.25
    selection_pairwise_volume_tilt_long_strength: float = -1.0
    selection_pairwise_volume_tilt_short_strength: float = -1.0
    selection_pairwise_volume_tilt_min_score_gap: float = 0.0
    selection_pairwise_volume_tilt_cooldown_days: int = 0
    selection_pairwise_volume_tilt_long_max_avg_ret20_zscore: float = -1.0
    selection_pairwise_volume_tilt_long_max_avg_rsi: float = -1.0
    selection_pairwise_volume_tilt_long_score_gap_reference: float = -1.0
    selection_pairwise_volume_tilt_long_active_ratio_full_strength_max: float = -1.0
    selection_pairwise_volume_tilt_long_base_volume_reference: float = -1.0
    selection_pairwise_volume_tilt_long_active_positions_reference: float = -1.0
    selection_pairwise_volume_tilt_long_max_range_zscore_reference: float = -1.0
    selection_pairwise_model_path: str = str(DEFAULT_MODEL_PATH)
    selection_pairwise_summary_path: str = str(DEFAULT_SUMMARY_PATH)
    selection_pairwise_veto_penalty: float = 1.5
    enable_ai_product_pool_filter: bool = False
    ai_product_pool_eligibility_path: str = ""
    ai_product_pool_strategy: str = "ai_top8_entry_filter"
    array_manager_size_floor: int = 120

    stop_loss_pct: float = 0.02
    trailing_stop_enabled: bool = True
    trailing_stop_pct: float = 0.0
    enable_profit_giveback_stop: bool = False
    profit_giveback_trigger_pct: float = 0.08
    profit_giveback_retain_ratio: float = 0.70
    profit_giveback_min_lock_pct: float = 0.03
    profit_giveback_streak_update_mode: str = "normal"
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
        "product_universe_csv_path",
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
        "sizing_equity_cap",
        "max_capital_usage_ratio",
        "max_single_trade_capital_usage_ratio",
        "enable_incremental_margin_budget_gate",
        "incremental_margin_budget_gate_usage_ratio",
        "incremental_margin_budget_gate_min_openable_candidates",
        "incremental_margin_budget_gate_protected_selection_rank",
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
        "streak_risk_state_excluded_products",
        "streak_risk_state_exclusion_mode",
        "streak_profit_recovery_mode",
        "streak_profit_recovery_confirm_wins",
        "streak_profit_recovery_equity_confirm_drawdown_pct",
        "enable_streak_entry_structure_risk_recovery",
        "streak_entry_structure_recovery_signals",
        "streak_entry_structure_recovery_min_multiplier",
        "streak_entry_structure_recovery_require_flat_portfolio",
        "streak_entry_structure_recovery_max_same_direction_corr",
        "streak_entry_structure_recovery_require_rsi_confirmation",
        "streak_entry_structure_recovery_long_min_rsi",
        "streak_entry_structure_recovery_short_max_rsi",
        "streak_entry_structure_recovery_max_portfolio_drawdown_pct",
        "enable_weighted_env_gate",
        "enable_portfolio_env_gate",
        "weighted_env_gate_close_position_good_max",
        "weighted_env_gate_close_position_bad_min",
        "weighted_env_gate_range_good_min",
        "weighted_env_gate_range_bad_max",
        "weighted_env_gate_selected_rate_good_max",
        "weighted_env_gate_selected_rate_bad_min",
        "weighted_env_gate_weight_floor",
        "enable_portfolio_drawdown_gate",
        "portfolio_drawdown_gate_start_pct",
        "portfolio_drawdown_gate_full_pct",
        "portfolio_drawdown_gate_weight_floor",
        "enable_same_direction_correlation_gate",
        "same_direction_correlation_gate_lookback",
        "same_direction_correlation_gate_start",
        "same_direction_correlation_gate_full",
        "same_direction_correlation_gate_weight_floor",
        "enable_selection_pairwise_v2",
        "enable_selection_pairwise_v2_catastrophic_veto",
        "enable_selection_pairwise_v2_catastrophic_hard_filter",
        "enable_selection_pairwise_v2_volume_tilt",
        "selection_pairwise_volume_tilt_strength",
        "selection_pairwise_volume_tilt_long_strength",
        "selection_pairwise_volume_tilt_short_strength",
        "selection_pairwise_volume_tilt_min_score_gap",
        "selection_pairwise_volume_tilt_cooldown_days",
        "selection_pairwise_volume_tilt_long_max_avg_ret20_zscore",
        "selection_pairwise_volume_tilt_long_max_avg_rsi",
        "selection_pairwise_volume_tilt_long_score_gap_reference",
        "selection_pairwise_volume_tilt_long_active_ratio_full_strength_max",
        "selection_pairwise_volume_tilt_long_base_volume_reference",
        "selection_pairwise_volume_tilt_long_active_positions_reference",
        "selection_pairwise_volume_tilt_long_max_range_zscore_reference",
        "selection_pairwise_model_path",
        "selection_pairwise_summary_path",
        "selection_pairwise_veto_penalty",
        "enable_ai_product_pool_filter",
        "ai_product_pool_eligibility_path",
        "ai_product_pool_strategy",
        "array_manager_size_floor",
        "stop_loss_pct",
        "trailing_stop_enabled",
        "trailing_stop_pct",
        "enable_profit_giveback_stop",
        "profit_giveback_trigger_pct",
        "profit_giveback_retain_ratio",
        "profit_giveback_min_lock_pct",
        "profit_giveback_streak_update_mode",
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
        "profit_recovery_streak",
        "portfolio_equity_high_water",
        "portfolio_drawdown_pct",
        "profit_giveback_streak_neutral_count",
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
        supported_symbols = load_product_universe_symbols(self.product_universe_csv_path)
        self.daily_mapping: dict[str, dict[str, str]] = build_daily_mapping(
            mapping_path,
            supported_symbols=supported_symbols,
        )
        metadata: dict[str, Any] = build_contract_metadata(
            mapping_path,
            supported_symbols=supported_symbols,
        )
        self.product_symbols: list[str] = metadata["product_symbols"]
        self.source_symbol_by_contract: dict[str, str] = metadata["source_symbol_by_contract"]

        # Keep the core strategy history window stable; pairwise runtime loads deeper
        # contract history separately when it needs more than the shared AM provides.
        am_size_floor: int = max(int(self.array_manager_size_floor or 140), 1)
        am_size: int = max(self.ma_extra_long + self.donchian_entry_period + 20, am_size_floor)
        self.ams: dict[str, ArrayManager] = {
            vt_symbol: ArrayManager(am_size) for vt_symbol in self.vt_symbols
        }
        self.states: dict[str, ProductState] = {
            product_vt: ProductState(product_vt_symbol=product_vt) for product_vt in self.product_symbols
        }
        self.streak_risk_state_excluded_product_set: set[str] = self._parse_symbol_set(
            self.streak_risk_state_excluded_products
        )
        self.profit_recovery_streak: int = 0
        self.base_capital: float = self._resolve_base_capital()
        self.entry_risk_diagnostics: list[dict[str, Any]] = []
        self.entry_candidate_snapshots: list[dict[str, Any]] = []
        self.trade_event_diagnostics: list[dict[str, Any]] = []
        self.trade_reason_by_trade_id: dict[str, str] = {}
        self.execution_price_overrides: dict[str, float] = {}
        self.trade_costs_total: float = 0.0
        self.profit_giveback_stop_update_count: int = 0
        self.profit_giveback_streak_neutral_count: int = 0
        self.pending_close_lots: dict[str, list[dict[str, Any]]] = {}
        self.pending_close_reasons: dict[str, list[dict[str, Any]]] = {}
        self.pending_entry_diagnostics: dict[tuple[str, str], list[int]] = {}
        self.settled_balance: float = self.base_capital
        self.portfolio_equity_high_water: float = self.base_capital
        self.portfolio_drawdown_pct: float = 0.0
        self.last_close_prices: dict[str, float] = {}
        self.pending_margin_reservation: float = 0.0
        self.pending_active_products: set[str] = set()
        self.current_env_gate_snapshot: dict[str, Any] = {}
        self.selection_pairwise_volume_tilt_last_date_by_direction: dict[str, pd.Timestamp] = {}
        self.ai_product_pool_by_date: dict[pd.Timestamp, dict[str, dict[str, Any]]] = {}
        self.ai_product_pool_eval_dates: list[pd.Timestamp] = []
        if self.enable_ai_product_pool_filter:
            self._load_ai_product_pool_eligibility()
        self.selection_pairwise_runtime: SelectionPairwiseRuntimeModel | None = None
        if self.enable_selection_pairwise_v2:
            self.selection_pairwise_runtime = SelectionPairwiseRuntimeModel(
                model_path=self.selection_pairwise_model_path,
                summary_path=self.selection_pairwise_summary_path,
                enable_catastrophic_veto=self.enable_selection_pairwise_v2_catastrophic_veto,
                catastrophic_veto_penalty=self.selection_pairwise_veto_penalty,
            )

    def _load_ai_product_pool_eligibility(self) -> None:
        path = Path(str(self.ai_product_pool_eligibility_path or ""))
        if not path.exists():
            self.write_log(f"AI product pool eligibility file missing: {path}")
            return

        df = pd.read_csv(path)
        required_columns = {"strategy", "eval_date", "product_vt_symbol", "score", "score_rank", "top_n"}
        missing_columns = required_columns - set(df.columns)
        if missing_columns:
            self.write_log(f"AI product pool eligibility missing columns: {sorted(missing_columns)}")
            return

        df = df[df["strategy"].astype(str) == str(self.ai_product_pool_strategy)].copy()
        if df.empty:
            self.write_log(f"AI product pool strategy has no rows: {self.ai_product_pool_strategy}")
            return

        df["eval_date"] = pd.to_datetime(df["eval_date"]).dt.normalize()
        for column in ["score", "score_rank", "top_n"]:
            df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0.0)

        by_date: dict[pd.Timestamp, dict[str, dict[str, Any]]] = {}
        for eval_date, group in df.groupby("eval_date"):
            by_date[pd.Timestamp(eval_date)] = {
                str(row.product_vt_symbol): {
                    "score": float(row.score),
                    "rank": int(row.score_rank),
                    "top_n": int(row.top_n),
                }
                for row in group.itertuples(index=False)
            }
        self.ai_product_pool_by_date = by_date
        self.ai_product_pool_eval_dates = sorted(by_date)

    def _ai_product_pool_snapshot(self, product_vt_symbol: str, trade_date: pd.Timestamp) -> dict[str, Any]:
        if not self.enable_ai_product_pool_filter:
            return {
                "ai_product_pool_enabled": 0,
                "ai_product_pool_strategy": "",
                "ai_product_pool_allowed": 1,
                "ai_product_pool_signal_date": "",
                "ai_product_pool_score": 0.0,
                "ai_product_pool_rank": 0,
                "ai_product_pool_top_n": 0,
            }

        snapshot: dict[str, Any] = {
            "ai_product_pool_enabled": 1,
            "ai_product_pool_strategy": str(self.ai_product_pool_strategy),
            "ai_product_pool_allowed": 1,
            "ai_product_pool_signal_date": "",
            "ai_product_pool_score": 0.0,
            "ai_product_pool_rank": 0,
            "ai_product_pool_top_n": 0,
        }
        if not self.ai_product_pool_eval_dates:
            snapshot["ai_product_pool_allowed"] = 1
            return snapshot

        normalized_date = pd.Timestamp(trade_date)
        if normalized_date.tz is not None:
            normalized_date = normalized_date.tz_localize(None)
        normalized_date = normalized_date.normalize()
        eval_index = pd.DatetimeIndex(self.ai_product_pool_eval_dates)
        signal_index = int(eval_index.searchsorted(normalized_date, side="left") - 1)
        if signal_index < 0:
            # Before the first out-of-sample AI signal, keep the original strategy unchanged.
            return snapshot

        signal_date = pd.Timestamp(eval_index[signal_index])
        product_rows = self.ai_product_pool_by_date.get(signal_date, {})
        product_row = product_rows.get(product_vt_symbol)
        snapshot["ai_product_pool_signal_date"] = signal_date.date().isoformat()
        if product_row is None:
            snapshot["ai_product_pool_allowed"] = 0
            return snapshot

        snapshot["ai_product_pool_allowed"] = 1
        snapshot["ai_product_pool_score"] = float(product_row.get("score", 0.0) or 0.0)
        snapshot["ai_product_pool_rank"] = int(product_row.get("rank", 0) or 0)
        snapshot["ai_product_pool_top_n"] = int(product_row.get("top_n", 0) or 0)
        return snapshot

    def on_init(self) -> None:
        self.write_log("Roll portfolio strategy initialized")
        self.load_bars(self.warmup_days, interval=Interval.DAILY)

    def on_start(self) -> None:
        self.write_log("Roll portfolio strategy started")

    def on_stop(self) -> None:
        self.write_log("Roll portfolio strategy stopped")

    def update_trade(self, trade: TradeData) -> None:
        super().update_trade(trade)
        self.trade_costs_total += self._trade_cost(trade)

        if trade.offset == Offset.OPEN:
            self._sync_open_trade(trade)
            self._sync_entry_risk_diagnostic(trade)
        elif trade.offset == Offset.CLOSE:
            delta_realized: float = self._sync_close_trade(trade)
            if delta_realized:
                self.realized_pnl += delta_realized
            close_reason: str | None = self._consume_pending_close_reason(trade)
            if close_reason:
                self.trade_reason_by_trade_id[trade.vt_tradeid] = close_reason

        self.settled_balance += self._trade_to_close_pnl(trade)

        engine_bars: dict[str, BarData] = getattr(self.strategy_engine, "bars", {})
        if engine_bars:
            self.estimated_equity = self.settled_balance
            self.total_margin_in_use = self._estimate_margin_usage(engine_bars)

    def rebalance_portfolio(self, bars: dict[str, BarData]) -> None:
        super().rebalance_portfolio(bars)
        self.execution_price_overrides.clear()

    def on_bars(self, bars: dict[str, BarData]) -> None:
        if not bars:
            return

        self._reset_intrabar_reservations()

        for vt_symbol, bar in bars.items():
            if vt_symbol in self.ams:
                self.ams[vt_symbol].update_bar(bar)

        current_date: str = next(iter(bars.values())).datetime.strftime("%Y-%m-%d")
        mapping_today: dict[str, str] = self.daily_mapping.get(current_date, {})
        self._refresh_risk_state(bars)
        self.last_signal = ""

        day_contexts: list[DailyEntryContext] = []
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
            day_contexts.append(
                DailyEntryContext(
                    product_vt_symbol=product_vt,
                    state=state,
                    target_contract=target_contract,
                    target_bar=target_bar,
                    actual_bar=actual_bar,
                    current_pos=current_pos,
                    history=history,
                    signal_data=signal_data,
                )
            )

        self.current_env_gate_snapshot = self._build_daily_env_gate_snapshot(day_contexts)
        flat_entry_plans = self._plan_flat_entry_candidates(day_contexts)

        for context in day_contexts:
            product_vt = context.product_vt_symbol
            state = context.state
            target_contract = context.target_contract
            target_bar = context.target_bar
            actual_bar = context.actual_bar
            current_pos = context.current_pos
            history = context.history
            signal_data = context.signal_data
            signal: str = str(signal_data["signal"])
            bullish: bool = bool(signal_data["bullish_alignment"])
            bearish: bool = bool(signal_data["bearish_alignment"])
            ma_mid_value: float = float(signal_data["ma_mid_value"])
            ma_long_value: float = float(signal_data["ma_long_value"])
            ma_long_prev_value: float = float(signal_data["ma_long_prev_value"])
            rsi_value: float = float(signal_data["rsi_value"])

            reconcile_bar: BarData = actual_bar or target_bar
            self._reconcile_state_with_position(state, current_pos, reconcile_bar)

            if state.contract_vt_symbol and state.contract_vt_symbol != target_contract:
                self._handle_rollover(state, target_contract, bars)
                continue

            if current_pos == 0:
                if signal.startswith("long") or signal.startswith("short"):
                    plan = flat_entry_plans.get(product_vt)
                    if plan is None:
                        continue
                    sizing = dict(plan["sizing"])
                    direction = str(plan["direction"])
                    volume = int(plan["volume"])
                    candidate_status = str(plan["candidate_status"])
                    skip_reason = str(plan["skip_reason"])
                    active_positions_before = int(plan["active_positions_before"])

                    self._record_entry_candidate_snapshot(
                        product_vt_symbol=state.product_vt_symbol,
                        contract_vt_symbol=target_contract,
                        direction=direction,
                        bar=target_bar,
                        signal=signal,
                        entry_context="flat_entry",
                        candidate_status=candidate_status,
                        skip_reason=skip_reason,
                        signal_data=signal_data,
                        sizing_snapshot=sizing,
                        active_positions_before=active_positions_before,
                    )
                    if candidate_status != "opened":
                        continue

                    self._open_position(
                        state,
                        target_contract,
                        direction,
                        volume,
                        target_bar,
                        signal,
                        history,
                        signal_data,
                        sizing_snapshot=sizing,
                    )
                    self._reserve_intrabar_entry(state.product_vt_symbol, sizing, volume, count_active_position=True)
                    self._apply_state_target(state)
                    self.last_signal = f"{product_vt}:{signal}"
                continue

            if state.entry_date and state.entry_date != self._bar_date(target_bar):
                state.bars_since_entry += 1

            self._update_dynamic_stops(state, target_bar, history)

            prev2day_exit_reason: str = self._process_prev2day_stop(state, target_bar, history)
            if prev2day_exit_reason:
                self.last_signal = f"{product_vt}:{prev2day_exit_reason}"
                continue

            layer_exit_reason: str = self._process_layer_stops(state, target_bar)
            if layer_exit_reason:
                self.last_signal = f"{product_vt}:{layer_exit_reason}"
                continue

            rsi_partial_exit_reason: str = self._process_rsi_partial_exit(state, target_bar, rsi_value)
            if rsi_partial_exit_reason:
                self._apply_state_target(state)
                self.last_signal = f"{product_vt}:{rsi_partial_exit_reason}"
                continue

            if self.enable_ma_trend_stop:
                if state.direction == "long" and self._stop_triggered("long", target_bar, ma_long_prev_value):
                    exit_price = self._stop_execution_price("long", target_bar, ma_long_prev_value)
                    self._close_all_layers_and_set_flat_target(
                        state,
                        exit_price,
                        execution_price_override=exit_price,
                        exit_reason="long_ma_stop",
                    )
                    self.last_signal = f"{product_vt}:long_ma_stop"
                    continue
                if state.direction == "short" and self._stop_triggered("short", target_bar, ma_long_prev_value):
                    exit_price = self._stop_execution_price("short", target_bar, ma_long_prev_value)
                    self._close_all_layers_and_set_flat_target(
                        state,
                        exit_price,
                        execution_price_override=exit_price,
                        exit_reason="short_ma_stop",
                    )
                    self.last_signal = f"{product_vt}:short_ma_stop"
                    continue

            if state.direction == "long":
                if self.exit_on_alignment_break and not bullish:
                    self._close_all_layers_and_set_flat_target(
                        state,
                        float(target_bar.close_price),
                        exit_reason="long_exit_alignment",
                    )
                    self.last_signal = f"{product_vt}:long_exit_alignment"
                    continue

                if self.reverse_on_opposite_signal and signal.startswith("short"):
                    self._close_all_layers_and_set_flat_target(
                        state,
                        float(target_bar.close_price),
                        exit_reason="long_reverse_to_short",
                    )
                    if self.short_entry_enabled and self._can_open_short_signal(signal):
                        sizing = self._calculate_entry_sizing(
                            target_contract,
                            "short",
                            target_bar,
                            history,
                            signal_data,
                            entry_context="reverse_entry",
                        )
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
                            self._reserve_intrabar_entry(state.product_vt_symbol, sizing, volume, count_active_position=False)
                            self._apply_state_target(state)
                            self.last_signal = f"{product_vt}:{signal}"
                    continue
            else:
                if self.exit_on_alignment_break and not bearish:
                    self._close_all_layers_and_set_flat_target(
                        state,
                        float(target_bar.close_price),
                        exit_reason="short_exit_alignment",
                    )
                    self.last_signal = f"{product_vt}:short_exit_alignment"
                    continue

                if self.reverse_on_opposite_signal and signal.startswith("long"):
                    self._close_all_layers_and_set_flat_target(
                        state,
                        float(target_bar.close_price),
                        exit_reason="short_reverse_to_long",
                    )
                    if self.long_entry_enabled:
                        sizing = self._calculate_entry_sizing(
                            target_contract,
                            "long",
                            target_bar,
                            history,
                            signal_data,
                            entry_context="reverse_entry",
                        )
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
                            self._reserve_intrabar_entry(state.product_vt_symbol, sizing, volume, count_active_position=False)
                            self._apply_state_target(state)
                            self.last_signal = f"{product_vt}:{signal}"
                    continue

            can_add, add_type = self._check_regular_add_conditions(state, target_bar, history)
            if can_add and add_type:
                add_volume: int = self._calculate_regular_add_volume(state)
                if add_volume > 0 and self._can_allocate_margin(state.contract_vt_symbol, add_volume, target_bar.close_price):
                    self._execute_regular_add(state, target_bar, add_type, add_volume, history)
                    self._reserve_intrabar_margin(state.contract_vt_symbol, add_volume, float(target_bar.close_price))
                    self._apply_state_target(state)
                    self.last_signal = f"{product_vt}:{add_type}"
                    continue

            can_don_add, don_add_type = self._check_donchian_add_conditions(state, target_bar, history)
            if can_don_add and don_add_type:
                add_volume = self._calculate_donchian_add_volume(state)
                if add_volume > 0 and self._can_allocate_margin(state.contract_vt_symbol, add_volume, target_bar.close_price):
                    self._execute_donchian_add(state, target_bar, don_add_type, add_volume, history)
                    self._reserve_intrabar_margin(state.contract_vt_symbol, add_volume, float(target_bar.close_price))
                    self._apply_state_target(state)
                    self.last_signal = f"{product_vt}:{don_add_type}"

        self.rebalance_portfolio(bars)
        self.settled_balance = self.estimated_equity
        self.last_close_prices = {vt_symbol: float(bar.close_price) for vt_symbol, bar in bars.items()}
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
        override_price: float | None = self.execution_price_overrides.get(vt_symbol)
        if override_price is not None and override_price > 0:
            return override_price
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
        self._record_trade_event(
            bar=old_bar,
            contract_vt_symbol=old_contract,
            product_vt_symbol=state.product_vt_symbol,
            position_direction=old_direction,
            offset="Close",
            reason="rollover_close",
            volume=state.active_volume(),
            price=float(old_bar.close_price),
        )
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
            entry_context="rollover_reopen",
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
        self._refresh_portfolio_drawdown_state()
        self.total_margin_in_use = self._estimate_margin_usage(bars)
        limited_balance: float = self._limited_available_balance()
        self.current_risk_per_trade = self._risk_amount_from_ratio(self.risk_ratio_of_total_assets, limited_balance)
        self.risk_multiplier = self._current_streak_multiplier()

    def _refresh_portfolio_drawdown_state(self) -> None:
        equity: float = max(0.0, float(self.estimated_equity or self.base_capital))
        self.portfolio_equity_high_water = max(
            float(self.portfolio_equity_high_water or self.base_capital),
            equity,
            float(self.base_capital),
        )
        if self.portfolio_equity_high_water <= 0:
            self.portfolio_drawdown_pct = 0.0
            return
        self.portfolio_drawdown_pct = max(
            0.0,
            (self.portfolio_equity_high_water - equity) / self.portfolio_equity_high_water,
        )

    def _reset_intrabar_reservations(self) -> None:
        self.pending_margin_reservation = 0.0
        self.pending_active_products.clear()

    def _portfolio_env_gate_weight(self, entry_context: str) -> float:
        if not self.enable_portfolio_env_gate or entry_context != "flat_entry":
            return 1.0
        snapshot = self.current_env_gate_snapshot or {}
        return self._clip01(float(snapshot.get("env_gate_weight", 1.0)))

    def _portfolio_drawdown_gate_weight(self, entry_context: str) -> float:
        if not self.enable_portfolio_drawdown_gate or entry_context != "flat_entry":
            return 1.0

        drawdown_pct: float = max(0.0, float(self.portfolio_drawdown_pct or 0.0))
        start_pct: float = max(0.0, float(self.portfolio_drawdown_gate_start_pct or 0.0))
        full_pct: float = max(start_pct + 1e-9, float(self.portfolio_drawdown_gate_full_pct or 0.0))
        weight_floor: float = self._clip01(float(self.portfolio_drawdown_gate_weight_floor or 0.0))
        if drawdown_pct <= start_pct:
            return 1.0
        if drawdown_pct >= full_pct:
            return weight_floor

        relief_ratio: float = (full_pct - drawdown_pct) / max(1e-9, full_pct - start_pct)
        return self._clip01(weight_floor + (1.0 - weight_floor) * relief_ratio)

    def _same_direction_correlation_gate_snapshot(
        self,
        *,
        contract_vt_symbol: str,
        direction: str,
        history: pd.DataFrame,
        entry_context: str,
    ) -> dict[str, Any]:
        enabled = int(self.enable_same_direction_correlation_gate and entry_context == "flat_entry")
        snapshot: dict[str, Any] = {
            "same_direction_correlation_gate_enabled": enabled,
            "same_direction_correlation_gate_weight": 1.0,
            "same_direction_correlation_active_count": 0,
            "same_direction_correlation_corr_count": 0,
            "same_direction_correlation_max_corr": 0.0,
            "same_direction_correlation_avg_corr": 0.0,
        }
        if not enabled:
            return snapshot

        lookback = max(5, int(self.same_direction_correlation_gate_lookback or 20))
        candidate_returns = self._history_return_vector(history, lookback)
        if len(candidate_returns) < max(5, lookback // 2):
            return snapshot

        active_symbols: list[str] = []
        corr_values: list[float] = []
        for state in self.states.values():
            active_contract = state.contract_vt_symbol
            if not active_contract or active_contract == contract_vt_symbol:
                continue
            if state.direction != direction:
                continue
            if self.get_pos(active_contract) == 0:
                continue

            active_symbols.append(active_contract)
            active_am = self.ams.get(active_contract)
            if active_am is None or not active_am.inited:
                continue

            active_returns = self._history_return_vector(self._build_history_df(active_am), lookback)
            pair_length = min(len(candidate_returns), len(active_returns))
            if pair_length < max(5, lookback // 2):
                continue

            candidate_slice = candidate_returns[-pair_length:]
            active_slice = active_returns[-pair_length:]
            corr_matrix = np.corrcoef(candidate_slice, active_slice)
            corr_value = float(corr_matrix[0, 1])
            if math.isfinite(corr_value):
                corr_values.append(corr_value)

        max_corr = max(corr_values) if corr_values else 0.0
        avg_corr = float(np.mean(corr_values)) if corr_values else 0.0
        start = float(self.same_direction_correlation_gate_start)
        full = max(start + 1e-9, float(self.same_direction_correlation_gate_full))
        weight_floor = self._clip01(float(self.same_direction_correlation_gate_weight_floor))
        if max_corr <= start:
            weight = 1.0
        elif max_corr >= full:
            weight = weight_floor
        else:
            relief_ratio = (full - max_corr) / max(1e-9, full - start)
            weight = self._clip01(weight_floor + (1.0 - weight_floor) * relief_ratio)

        snapshot.update(
            {
                "same_direction_correlation_gate_weight": weight,
                "same_direction_correlation_active_count": len(active_symbols),
                "same_direction_correlation_corr_count": len(corr_values),
                "same_direction_correlation_max_corr": max_corr,
                "same_direction_correlation_avg_corr": avg_corr,
            }
        )
        return snapshot

    @staticmethod
    def _history_return_vector(history: pd.DataFrame, lookback: int) -> np.ndarray:
        if history is None or history.empty or "close" not in history:
            return np.array([], dtype="float64")
        close = pd.to_numeric(history["close"], errors="coerce").astype("float64")
        returns = close.pct_change().replace([math.inf, -math.inf], pd.NA).dropna()
        if returns.empty:
            return np.array([], dtype="float64")
        return returns.tail(max(1, int(lookback))).to_numpy(dtype="float64")

    def _apply_same_direction_correlation_gate_to_sizing(
        self,
        sizing: dict[str, Any],
        *,
        contract_vt_symbol: str,
        direction: str,
        history: pd.DataFrame,
        entry_context: str,
        correlation_snapshot: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        adjusted = dict(sizing)
        snapshot = correlation_snapshot or self._same_direction_correlation_gate_snapshot(
            contract_vt_symbol=contract_vt_symbol,
            direction=direction,
            history=history,
            entry_context=entry_context,
        )
        adjusted.update(snapshot)
        if not int(snapshot["same_direction_correlation_gate_enabled"]):
            return adjusted

        selected_volume = max(0, int(adjusted.get("selected_volume") or 0))
        weight = self._clip01(float(snapshot["same_direction_correlation_gate_weight"]))
        selected_volume = int(math.floor(selected_volume * weight))
        if 0 < selected_volume < self.min_position_size:
            selected_volume = 0
        adjusted["selected_volume"] = max(0, selected_volume)
        return adjusted

    def _effective_capital_usage_ratio(self, entry_context: str) -> float:
        return max(0.0, float(self.max_capital_usage_ratio) * self._portfolio_env_gate_weight(entry_context))

    def _effective_max_concurrent_positions(self, entry_context: str) -> int:
        base_limit = max(1, int(self.max_concurrent_positions))
        if not self.enable_portfolio_env_gate or entry_context != "flat_entry":
            return base_limit
        weighted_limit = int(math.floor(base_limit * self._portfolio_env_gate_weight(entry_context)))
        return max(1, min(base_limit, weighted_limit))

    def _allowed_capital(self, entry_context: str = "default") -> float:
        return max(0.0, self._sizing_equity() * self._effective_capital_usage_ratio(entry_context))

    def _incremental_margin_budget_gate_allowed_capital(self, entry_context: str = "flat_entry") -> float:
        ratio = float(self.incremental_margin_budget_gate_usage_ratio or 0.0)
        if ratio <= 0:
            ratio = self._effective_capital_usage_ratio(entry_context)
        return max(0.0, self._sizing_equity() * ratio)

    def _incremental_margin_budget_gate_fields(
        self,
        *,
        planned_intraday_margin_before: float,
        selected_volume: int,
        margin_per_contract: float,
        openable_candidate_count: int = 1,
        selection_pairwise_rank: int = 0,
        entry_context: str = "flat_entry",
    ) -> dict[str, Any]:
        min_candidates = max(1, int(self.incremental_margin_budget_gate_min_openable_candidates or 1))
        protected_rank = max(0, int(self.incremental_margin_budget_gate_protected_selection_rank or 0))
        selection_rank = max(0, int(selection_pairwise_rank or 0))
        protected_by_rank = int(protected_rank > 0 and 0 < selection_rank <= protected_rank)
        gate_enabled = int(
            self.enable_incremental_margin_budget_gate
            and entry_context == "flat_entry"
            and int(openable_candidate_count) >= min_candidates
        )
        reserved_margin_before = self._reserved_margin_in_use()
        planned_margin = max(0.0, float(margin_per_contract) * max(0, int(selected_volume)))
        budget = self._incremental_margin_budget_gate_allowed_capital(entry_context)
        projected_before = reserved_margin_before + max(0.0, float(planned_intraday_margin_before))
        projected_after = projected_before + planned_margin
        passed = (not gate_enabled) or bool(protected_by_rank) or projected_after <= budget + 1e-9
        return {
            "incremental_margin_budget_gate_enabled": gate_enabled,
            "incremental_margin_budget_gate_min_openable_candidates": min_candidates,
            "incremental_margin_budget_gate_openable_candidate_count": int(openable_candidate_count),
            "incremental_margin_budget_gate_protected_selection_rank": protected_rank,
            "incremental_margin_budget_gate_candidate_selection_rank": selection_rank,
            "incremental_margin_budget_gate_protected_by_rank": protected_by_rank,
            "incremental_margin_budget_gate_budget": budget,
            "incremental_margin_budget_gate_reserved_margin_before": reserved_margin_before,
            "incremental_margin_budget_gate_planned_intraday_margin_before": max(
                0.0,
                float(planned_intraday_margin_before),
            ),
            "incremental_margin_budget_gate_planned_entry_margin": planned_margin,
            "incremental_margin_budget_gate_projected_margin_before": projected_before,
            "incremental_margin_budget_gate_projected_margin_after": projected_after,
            "incremental_margin_budget_gate_passed": int(passed),
        }

    def _single_trade_capital_limit(self) -> float:
        return max(0.0, self._sizing_equity() * self.max_single_trade_capital_usage_ratio)

    def _reserved_margin_in_use(self) -> float:
        return max(0.0, self.total_margin_in_use + self.pending_margin_reservation)

    def _free_capital_after_reservations(self) -> float:
        return max(0.0, self._sizing_equity() - self._reserved_margin_in_use())

    def _remaining_capital_budget(self, entry_context: str = "default") -> float:
        return max(0.0, self._allowed_capital(entry_context) - self._reserved_margin_in_use())

    def _reserve_intrabar_entry(
        self,
        product_vt_symbol: str,
        sizing_snapshot: dict[str, Any],
        volume: int,
        *,
        count_active_position: bool,
    ) -> None:
        margin_per_contract = float(sizing_snapshot.get("margin_per_contract") or 0.0)
        self.pending_margin_reservation += max(0.0, margin_per_contract * max(0, int(volume)))
        if count_active_position:
            self.pending_active_products.add(product_vt_symbol)

    def _reserve_intrabar_margin(self, vt_symbol: str, volume: int, price: float) -> None:
        margin_ratio = self._margin_ratio_for_symbol(vt_symbol)
        projected_margin = float(price) * self.get_size(vt_symbol) * max(0, int(volume)) * margin_ratio
        self.pending_margin_reservation += max(0.0, projected_margin)

    def _resolve_base_capital(self) -> float:
        if self.capital_base > 0:
            return float(self.capital_base)
        capital: float | None = getattr(self.strategy_engine, "capital", None)
        if capital:
            return float(capital)
        return 1_000_000.0

    def _estimate_equity(self, bars: dict[str, BarData]) -> float:
        equity: float = self.settled_balance
        for vt_symbol, bar in bars.items():
            start_pos: int = int(self.get_pos(vt_symbol))
            if not start_pos:
                continue
            pre_close: float = float(self.last_close_prices.get(vt_symbol, float(bar.close_price)))
            close_price: float = float(bar.close_price)
            size: int = self.get_size(vt_symbol)
            equity += start_pos * (close_price - pre_close) * size
        return equity

    def _trade_cost(self, trade: TradeData) -> float:
        size: float = float(getattr(self.strategy_engine, "sizes", {}).get(trade.vt_symbol, self.get_size(trade.vt_symbol)))
        rate: float = float(getattr(self.strategy_engine, "rates", {}).get(trade.vt_symbol, 0.0))
        slippage: float = float(getattr(self.strategy_engine, "slippages", {}).get(trade.vt_symbol, 0.0))
        turnover: float = float(trade.volume) * size * float(trade.price)
        return turnover * rate + float(trade.volume) * size * slippage

    def _trade_to_close_pnl(self, trade: TradeData) -> float:
        engine_bars: dict[str, BarData] = getattr(self.strategy_engine, "bars", {})
        bar: BarData | None = engine_bars.get(trade.vt_symbol)
        if bar is None:
            return 0.0

        size: int = self.get_size(trade.vt_symbol)
        pos_change: float = float(trade.volume) if trade.direction == Direction.LONG else -float(trade.volume)
        trading_pnl: float = pos_change * (float(bar.close_price) - float(trade.price)) * size
        return trading_pnl - self._trade_cost(trade)

    def _find_state_by_contract(self, vt_symbol: str) -> ProductState | None:
        for state in self.states.values():
            if state.contract_vt_symbol == vt_symbol:
                return state
        return None

    def _sync_open_trade(self, trade: TradeData) -> None:
        state: ProductState | None = self._find_state_by_contract(trade.vt_symbol)
        if state is None or not state.layers:
            return

        actual_direction: str = "long" if trade.direction == Direction.LONG else "short"
        if state.direction != actual_direction:
            return

        trade_date: str = pd.Timestamp(trade.datetime).strftime("%Y-%m-%d")
        remaining: int = int(trade.volume)

        for layer in reversed(state.layers):
            if remaining <= 0:
                break
            if layer.direction != actual_direction:
                continue
            if layer.entry_date != trade_date or layer.entry_price_synced:
                continue

            if layer.volume == remaining:
                layer.entry_price = float(trade.price)
                layer.entry_price_synced = True
                remaining = 0
            elif layer.volume < remaining:
                layer.entry_price = float(trade.price)
                layer.entry_price_synced = True
                remaining -= layer.volume
            else:
                synced_layer = PositionLayer(
                    kind=layer.kind,
                    direction=layer.direction,
                    volume=remaining,
                    entry_price=float(trade.price),
                    stop_price=layer.stop_price,
                    highest_price=layer.highest_price,
                    lowest_price=layer.lowest_price,
                    signal=layer.signal,
                    entry_date=layer.entry_date,
                    max_profit_pct=layer.max_profit_pct,
                    margin_ratio=layer.margin_ratio,
                    entry_price_synced=True,
                    profit_giveback_stop_active=layer.profit_giveback_stop_active,
                )
                layer.volume -= remaining
                insert_index = state.layers.index(layer) + 1
                state.layers.insert(insert_index, synced_layer)
                remaining = 0

    def _sync_entry_risk_diagnostic(self, trade: TradeData) -> None:
        actual_direction: str = "long" if trade.direction == Direction.LONG else "short"
        pending_indexes: list[int] = self.pending_entry_diagnostics.get((trade.vt_symbol, actual_direction), [])
        if not pending_indexes:
            return

        selected_index: int | None = None
        for offset, diagnostic_index in enumerate(pending_indexes):
            row = self.entry_risk_diagnostics[diagnostic_index]
            if pd.Timestamp(row["datetime"]) != pd.Timestamp(trade.datetime):
                continue
            if int(row.get("selected_volume") or 0) != int(trade.volume):
                continue
            selected_index = offset
            break

        if selected_index is None:
            return

        diagnostic_index = pending_indexes.pop(selected_index)
        if not pending_indexes:
            self.pending_entry_diagnostics.pop((trade.vt_symbol, actual_direction), None)

        row = self.entry_risk_diagnostics[diagnostic_index]
        filled_entry_price: float = float(trade.price)
        stop_price: float = float(row["stop_price"])
        size: int = int(row["size"])
        margin_ratio: float = float(row["margin_ratio"])
        min_risk: float = max(float(self.get_pricetick(trade.vt_symbol)) * size, 1.0)
        risk_per_contract: float = max(abs(filled_entry_price - stop_price) * size, min_risk)
        margin_per_contract: float = filled_entry_price * size * margin_ratio
        volume: int = int(row["volume"])

        row["filled_entry_price"] = filled_entry_price
        row["entry_price"] = filled_entry_price
        row["stop_distance"] = abs(filled_entry_price - stop_price)
        row["risk_per_contract"] = risk_per_contract
        row["actual_risk_amount"] = risk_per_contract * volume
        row["margin_per_contract"] = margin_per_contract
        row["actual_margin_amount"] = margin_per_contract * volume
        row["projected_total_margin_after"] = float(row["total_margin_in_use_before"]) + float(row["actual_margin_amount"])

    def _sync_close_trade(self, trade: TradeData) -> float:
        pending_lots: list[dict[str, Any]] = self.pending_close_lots.get(trade.vt_symbol, [])
        if not pending_lots:
            return 0.0

        size: int = self.get_size(trade.vt_symbol)
        remaining: int = int(trade.volume)
        delta_realized: float = 0.0
        actual_exit_price: float = float(trade.price)

        while remaining > 0 and pending_lots:
            lot: dict[str, Any] = pending_lots[0]
            matched_volume: int = min(remaining, int(lot["volume"]))
            direction: str = str(lot["direction"])
            provisional_exit_price: float = float(lot["provisional_exit_price"])
            entry_price: float = float(lot["entry_price"])

            provisional_realized: float = (
                (provisional_exit_price - entry_price) * size * matched_volume
                if direction == "long"
                else (entry_price - provisional_exit_price) * size * matched_volume
            )
            actual_realized: float = (
                (actual_exit_price - entry_price) * size * matched_volume
                if direction == "long"
                else (entry_price - actual_exit_price) * size * matched_volume
            )
            delta_realized += actual_realized - provisional_realized

            lot["volume"] = int(lot["volume"]) - matched_volume
            remaining -= matched_volume
            if int(lot["volume"]) <= 0:
                pending_lots.pop(0)

        if not pending_lots:
            self.pending_close_lots.pop(trade.vt_symbol, None)

        return delta_realized

    def _queue_pending_close_reason(self, vt_symbol: str, reason: str, volume: int) -> None:
        if volume <= 0:
            return
        pending_reasons = self.pending_close_reasons.setdefault(vt_symbol, [])
        pending_reasons.append({"reason": reason, "volume": int(volume)})

    def _consume_pending_close_reason(self, trade: TradeData) -> str | None:
        pending_reasons: list[dict[str, Any]] = self.pending_close_reasons.get(trade.vt_symbol, [])
        if not pending_reasons:
            return None

        remaining: int = int(trade.volume)
        consumed_reasons: list[str] = []
        while remaining > 0 and pending_reasons:
            item = pending_reasons[0]
            matched_volume: int = min(remaining, int(item["volume"]))
            remaining -= matched_volume
            item["volume"] = int(item["volume"]) - matched_volume
            consumed_reasons.append(str(item["reason"]))
            if int(item["volume"]) <= 0:
                pending_reasons.pop(0)

        if not pending_reasons:
            self.pending_close_reasons.pop(trade.vt_symbol, None)

        if not consumed_reasons:
            return None
        return consumed_reasons[0]

    def _queue_pending_close_lot(self, vt_symbol: str, layer: PositionLayer, exit_price: float, volume: int) -> None:
        if volume <= 0:
            return
        pending_lots: list[dict[str, Any]] = self.pending_close_lots.setdefault(vt_symbol, [])
        pending_lots.append(
            {
                "direction": layer.direction,
                "entry_price": float(layer.entry_price),
                "provisional_exit_price": float(exit_price),
                "volume": int(volume),
            }
        )

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
        """Cap sizing equity while still de-risking on drawdown; non-positive cap disables the ceiling."""
        equity: float = max(0.0, float(self.estimated_equity))
        cap: float = float(self.sizing_equity_cap or 0.0)
        if cap <= 0:
            return equity
        return min(equity, cap)

    def _limited_available_balance(self, entry_context: str = "default") -> float:
        free_capital: float = self._free_capital_after_reservations()
        remaining_capital_budget: float = self._remaining_capital_budget(entry_context)
        return max(0.0, min(free_capital, remaining_capital_budget))

    def _risk_amount_from_ratio(
        self,
        risk_ratio: float,
        limited_balance: float,
        risk_multiplier_override: float | None = None,
    ) -> float:
        dynamic_risk: float = max(self.min_risk_per_trade, limited_balance * risk_ratio)
        dynamic_risk = min(self.max_risk_per_trade, dynamic_risk)
        multiplier = self._current_streak_multiplier() if risk_multiplier_override is None else risk_multiplier_override
        dynamic_risk *= max(0.0, float(multiplier))
        return max(0.0, dynamic_risk)

    def _current_streak_multiplier(self) -> float:
        multipliers: list[float] = self._parse_float_list(self.streak_risk_multipliers, [1.0, 1.0, 1.0, 0.1])
        tier: int = min(self.loss_streak, len(multipliers) - 1)
        return max(0.0, multipliers[tier])

    def _entry_structure_recovery_fields(
        self,
        *,
        signal: str,
        direction: str,
        entry_context: str,
        rsi_value: float | None,
        active_positions_before: int | None,
        correlation_snapshot: dict[str, Any] | None,
    ) -> dict[str, Any]:
        base_multiplier = self._current_streak_multiplier()
        rsi_number = self._safe_float_value(rsi_value, float("nan"))
        fields: dict[str, Any] = {
            "streak_entry_structure_risk_recovery_enabled": int(self.enable_streak_entry_structure_risk_recovery),
            "streak_entry_structure_risk_recovery_applied": 0,
            "streak_entry_structure_risk_recovery_reason": "",
            "streak_entry_structure_risk_recovery_base_multiplier": base_multiplier,
            "streak_entry_structure_risk_recovery_effective_multiplier": base_multiplier,
            "streak_entry_structure_risk_recovery_rsi_confirmation_enabled": int(
                self.streak_entry_structure_recovery_require_rsi_confirmation
            ),
            "streak_entry_structure_risk_recovery_rsi_value": rsi_number,
            "streak_entry_structure_risk_recovery_long_min_rsi": float(
                self.streak_entry_structure_recovery_long_min_rsi
            ),
            "streak_entry_structure_risk_recovery_short_max_rsi": float(
                self.streak_entry_structure_recovery_short_max_rsi
            ),
            "streak_entry_structure_risk_recovery_portfolio_drawdown_pct": float(
                self.portfolio_drawdown_pct or 0.0
            ),
            "streak_entry_structure_risk_recovery_max_portfolio_drawdown_pct": float(
                self.streak_entry_structure_recovery_max_portfolio_drawdown_pct
            ),
        }
        if not self.enable_streak_entry_structure_risk_recovery:
            return fields
        if entry_context != "flat_entry":
            fields["streak_entry_structure_risk_recovery_reason"] = "not_flat_entry"
            return fields
        allowed_signals = self._parse_symbol_set(self.streak_entry_structure_recovery_signals)
        if signal not in allowed_signals:
            fields["streak_entry_structure_risk_recovery_reason"] = "signal_not_allowed"
            return fields
        if bool(self.streak_entry_structure_recovery_require_flat_portfolio) and int(active_positions_before or 0) > 0:
            fields["streak_entry_structure_risk_recovery_reason"] = "portfolio_not_flat"
            return fields

        snapshot = correlation_snapshot or {}
        same_direction_active = int(snapshot.get("same_direction_correlation_active_count") or 0)
        max_corr = self._safe_float_value(snapshot.get("same_direction_correlation_max_corr"), 0.0)
        max_allowed_corr = max(0.0, float(self.streak_entry_structure_recovery_max_same_direction_corr or 0.0))
        if same_direction_active > 0 or max_corr > max_allowed_corr:
            fields["streak_entry_structure_risk_recovery_reason"] = "same_direction_crowding"
            return fields

        if bool(self.streak_entry_structure_recovery_require_rsi_confirmation):
            long_min_rsi = float(self.streak_entry_structure_recovery_long_min_rsi)
            short_max_rsi = float(self.streak_entry_structure_recovery_short_max_rsi)
            rsi_confirmed = (
                (direction == "long" and rsi_number >= long_min_rsi)
                or (direction == "short" and rsi_number <= short_max_rsi)
            )
            if not rsi_confirmed:
                fields["streak_entry_structure_risk_recovery_reason"] = "rsi_not_confirmed"
                return fields

        max_portfolio_drawdown = float(self.streak_entry_structure_recovery_max_portfolio_drawdown_pct)
        if max_portfolio_drawdown >= 0.0 and float(self.portfolio_drawdown_pct or 0.0) > max_portfolio_drawdown:
            fields["streak_entry_structure_risk_recovery_reason"] = "portfolio_drawdown_too_deep"
            return fields

        min_multiplier = max(0.0, float(self.streak_entry_structure_recovery_min_multiplier or 0.0))
        effective_multiplier = max(base_multiplier, min_multiplier)
        fields["streak_entry_structure_risk_recovery_effective_multiplier"] = effective_multiplier
        if effective_multiplier > base_multiplier + 1e-12:
            fields["streak_entry_structure_risk_recovery_applied"] = 1
            fields["streak_entry_structure_risk_recovery_reason"] = "early_cross_clean_book"
        else:
            fields["streak_entry_structure_risk_recovery_reason"] = "no_multiplier_lift"
        return fields

    @staticmethod
    def _safe_float_value(value: object, default: float = 0.0) -> float:
        try:
            result = float(value)
        except (TypeError, ValueError):
            return default
        if pd.isna(result) or math.isinf(result):
            return default
        return result

    @staticmethod
    def _series_safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
        denominator_series = denominator.astype("float64").replace(0.0, pd.NA)
        result = numerator.astype("float64") / denominator_series
        return result.replace([math.inf, -math.inf], pd.NA).fillna(0.0)

    @staticmethod
    def _rolling_zscore(series: pd.Series, window: int) -> pd.Series:
        rolling_mean = series.rolling(window).mean()
        rolling_std = series.rolling(window).std(ddof=0).replace(0.0, pd.NA)
        zscore = (series - rolling_mean) / rolling_std
        return zscore.replace([math.inf, -math.inf], pd.NA).fillna(0.0)

    @staticmethod
    def _clip01(value: float) -> float:
        return min(max(float(value), 0.0), 1.0)

    def _extract_env_gate_candidate_features(self, history: pd.DataFrame) -> dict[str, float]:
        if history is None or history.empty or len(history) < 60:
            return {}

        close = pd.to_numeric(history["close"], errors="coerce").astype("float64")
        high = pd.to_numeric(history["high"], errors="coerce").astype("float64")
        low = pd.to_numeric(history["low"], errors="coerce").astype("float64")
        if close.isna().all() or high.isna().all() or low.isna().all():
            return {}

        range_pct_series = self._series_safe_ratio(high - low, close)
        close_position_60d_series = self._series_safe_ratio(
            close - low.rolling(60).min(),
            high.rolling(60).max() - low.rolling(60).min(),
        )

        return {
            "feature_range_pct_zscore_120": self._safe_float_value(self._rolling_zscore(range_pct_series, 120).iloc[-1]),
            "feature_close_position_60d": self._safe_float_value(close_position_60d_series.iloc[-1], default=0.5),
        }

    def _is_native_openable_candidate(self, signal: str, direction: str, selected_volume: int) -> bool:
        if selected_volume <= 0:
            return False
        if direction == "long":
            return bool(self.long_entry_enabled)
        return bool(self.short_entry_enabled and self._can_open_short_signal(signal))

    def _build_flat_entry_candidate_plan(self, context: DailyEntryContext, base_active_positions: int) -> dict[str, Any] | None:
        signal: str = str(context.signal_data.get("signal", ""))
        if signal.startswith("long"):
            direction = "long"
        elif signal.startswith("short"):
            direction = "short"
        else:
            return None

        correlation_snapshot = self._same_direction_correlation_gate_snapshot(
            contract_vt_symbol=context.target_contract,
            direction=direction,
            history=context.history,
            entry_context="flat_entry",
        )
        sizing = self._calculate_entry_sizing(
            context.target_contract,
            direction,
            context.target_bar,
            context.history,
            context.signal_data,
            entry_context="flat_entry",
            active_positions_before=base_active_positions,
            correlation_snapshot=correlation_snapshot,
        )
        sizing = self._apply_same_direction_correlation_gate_to_sizing(
            sizing,
            contract_vt_symbol=context.target_contract,
            direction=direction,
            history=context.history,
            entry_context="flat_entry",
            correlation_snapshot=correlation_snapshot,
        )
        volume = int(sizing["selected_volume"])
        native_openable = self._is_native_openable_candidate(signal, direction, volume)
        skip_reason = ""
        ai_product_pool_snapshot = self._ai_product_pool_snapshot(
            context.product_vt_symbol,
            pd.Timestamp(context.target_bar.datetime).normalize(),
        )
        sizing.update(ai_product_pool_snapshot)
        if direction == "long" and not self.long_entry_enabled:
            skip_reason = "long_entry_disabled"
        elif direction == "short" and not self.short_entry_enabled:
            skip_reason = "short_entry_disabled"
        elif direction == "short" and not self._can_open_short_signal(signal):
            skip_reason = "short_signal_rejected"
        elif volume <= 0:
            skip_reason = "sizing_zero_volume"
        elif (
            self.enable_ai_product_pool_filter
            and int(ai_product_pool_snapshot.get("ai_product_pool_allowed", 1) or 0) == 0
        ):
            native_openable = False
            skip_reason = "ai_product_pool_blocked"

        effective_max_positions = int(sizing.get("effective_max_concurrent_positions") or self.max_concurrent_positions)
        remaining_slots = max(0, effective_max_positions - base_active_positions)
        candidate_plan = {
            "product_vt_symbol": context.product_vt_symbol,
            "state": context.state,
            "target_contract": context.target_contract,
            "target_bar": context.target_bar,
            "history": context.history,
            "signal_data": context.signal_data,
            "direction": direction,
            "signal": signal,
            "sizing": sizing,
            "volume": volume,
            "native_openable": native_openable,
            "skip_reason": skip_reason,
            "active_positions_before": base_active_positions,
            "remaining_position_slots": remaining_slots,
            "selection_pairwise_score": 0.0,
            "selection_pairwise_rank": 0,
            "selection_pairwise_veto_flag": 0,
            "selection_pairwise_model_tag": "",
            "selection_pairwise_enabled": 0,
            "selection_pairwise_veto_penalty": 0.0,
            "selection_pairwise_feature_ret_20d_zscore_120": 0.0,
            "selection_pairwise_feature_close_position_60d_cs_zscore_1d": 0.0,
            "selection_pairwise_feature_range_pct_zscore_120": 0.0,
            "selection_pairwise_runtime_veto_match_local": 0,
        }
        return candidate_plan

    def _apply_selection_pairwise_scores(self, candidate_plans: list[dict[str, Any]]) -> None:
        if not self.selection_pairwise_runtime:
            return

        scorable_candidates = [plan for plan in candidate_plans if plan["native_openable"]]
        if len(scorable_candidates) < 2:
            return

        runtime_rows: list[dict[str, Any]] = []
        candidate_date = pd.Timestamp(scorable_candidates[0]["target_bar"].datetime).normalize()
        for order_index, plan in enumerate(scorable_candidates, start=1):
            runtime_row = build_runtime_feature_row(
                history=plan["history"],
                contract_vt_symbol=(
                    str(getattr(plan["target_contract"], "vt_symbol", "") or plan["target_contract"])
                ),
                candidate_date=candidate_date,
                direction=str(plan["direction"]),
                signal=str(plan["signal"]),
                risk_mode=str(plan["sizing"].get("risk_mode", plan["signal_data"].get("risk_mode", "regular"))),
                risk_ratio=float(plan["sizing"].get("risk_ratio") or 0.0),
                remaining_position_slots=int(plan["remaining_position_slots"]),
                estimated_equity=float(plan["sizing"].get("limited_balance") or self.estimated_equity or self.base_capital),
                margin_per_contract=float(plan["sizing"].get("margin_per_contract") or 0.0),
            )
            if not runtime_row:
                continue
            runtime_row.update(
                {
                    "sample_id": f"runtime_{order_index}_{plan['product_vt_symbol']}",
                    "product_vt_symbol": plan["product_vt_symbol"],
                    "direction": plan["direction"],
                    "signal": plan["signal"],
                    "risk_mode": str(plan["sizing"].get("risk_mode", plan["signal_data"].get("risk_mode", "regular"))),
                }
            )
            runtime_rows.append(runtime_row)

        if len(runtime_rows) < 2:
            return

        scored_rows = self.selection_pairwise_runtime.score_candidate_pool(runtime_rows)
        score_by_product = {str(row["product_vt_symbol"]): row for row in scored_rows}
        for plan in scorable_candidates:
            scored_row = score_by_product.get(plan["product_vt_symbol"])
            if not scored_row:
                continue
            veto_flag = int(scored_row.get("selection_pairwise_veto_flag", 0))
            score = float(scored_row.get("predicted_pairwise_score", 0.0))
            if (
                veto_flag == 0
                and self.enable_selection_pairwise_v2_catastrophic_veto
                and self._selection_pairwise_catastrophic_veto_match(scored_row)
            ):
                veto_flag = 1
                score -= float(self.selection_pairwise_veto_penalty)
            plan["selection_pairwise_score"] = score
            plan["selection_pairwise_rank"] = int(scored_row.get("selection_pairwise_rank", 0))
            plan["selection_pairwise_veto_flag"] = veto_flag
            plan["selection_pairwise_model_tag"] = str(scored_row.get("selection_pairwise_model_tag", ""))
            plan["selection_pairwise_enabled"] = int(scored_row.get("selection_pairwise_enabled", 0))
            plan["selection_pairwise_veto_penalty"] = float(scored_row.get("selection_pairwise_veto_penalty", 0.0))
            plan["selection_pairwise_feature_ret_20d_zscore_120"] = float(
                scored_row.get("feature_ret_20d_zscore_120", 0.0) or 0.0
            )
            plan["selection_pairwise_feature_close_position_60d_cs_zscore_1d"] = float(
                scored_row.get("feature_close_position_60d_cs_zscore_1d", 0.0) or 0.0
            )
            plan["selection_pairwise_feature_range_pct_zscore_120"] = float(
                scored_row.get("feature_range_pct_zscore_120", 0.0) or 0.0
            )
            plan["selection_pairwise_runtime_veto_match_local"] = int(
                self._selection_pairwise_catastrophic_veto_match(scored_row)
            )
            if veto_flag and self.enable_selection_pairwise_v2_catastrophic_hard_filter:
                plan["native_openable"] = False
                plan["skip_reason"] = "selection_pairwise_catastrophic_veto"

    @staticmethod
    def _selection_pairwise_catastrophic_veto_match(candidate_row: dict[str, Any]) -> bool:
        return bool(
            str(candidate_row.get("direction", "")) == "short"
            and str(candidate_row.get("signal", "")) in {"short_case2", "short_case1a"}
            and float(candidate_row.get("feature_ret_20d_zscore_120", 0.0) or 0.0) < -0.3
            and float(candidate_row.get("feature_close_position_60d_cs_zscore_1d", 0.0) or 0.0) < 0.0
            and float(candidate_row.get("feature_range_pct_zscore_120", 0.0) or 0.0) > 0.5
        )

    def _apply_selection_pairwise_volume_tilt(self, opened_plans: list[dict[str, Any]]) -> None:
        if not self.enable_selection_pairwise_v2_volume_tilt:
            return
        if not self.selection_pairwise_runtime:
            return

        strength = max(0.0, float(self.selection_pairwise_volume_tilt_strength or 0.0))

        direction_strengths: dict[str, float] = {
            "long": (
                float(self.selection_pairwise_volume_tilt_long_strength)
                if float(self.selection_pairwise_volume_tilt_long_strength) >= 0.0
                else strength
            ),
            "short": (
                float(self.selection_pairwise_volume_tilt_short_strength)
                if float(self.selection_pairwise_volume_tilt_short_strength) >= 0.0
                else strength
            ),
        }
        if max(direction_strengths.values(), default=0.0) <= 0.0:
            return

        for direction in ("long", "short"):
            direction_strength = max(0.0, float(direction_strengths.get(direction, strength)))
            if direction_strength <= 0.0:
                continue
            direction_plans = [plan for plan in opened_plans if str(plan.get("direction", "")) == direction]
            if len(direction_plans) < 2:
                continue

            direction_date: pd.Timestamp | None = None
            first_plan_target_bar: BarData | None = direction_plans[0].get("target_bar")
            if first_plan_target_bar is not None:
                direction_date = pd.Timestamp(first_plan_target_bar.datetime.date())

            cooldown_days: int = max(0, int(self.selection_pairwise_volume_tilt_cooldown_days or 0))
            if cooldown_days > 0 and direction_date is not None:
                last_tilt_date: pd.Timestamp | None = self.selection_pairwise_volume_tilt_last_date_by_direction.get(direction)
                if last_tilt_date is not None and (direction_date - last_tilt_date).days <= cooldown_days:
                    continue

            direction_plans.sort(
                key=lambda item: (int(item.get("selection_pairwise_rank") or 0), str(item.get("product_vt_symbol", "")))
            )
            count = len(direction_plans)
            if count <= 1:
                continue

            score_values: list[float] = [float(plan.get("selection_pairwise_score") or 0.0) for plan in direction_plans]
            score_gap: float = max(score_values) - min(score_values)
            top_gap: float = score_values[0] - score_values[1] if len(score_values) >= 2 else 0.0
            min_score_gap: float = max(0.0, float(self.selection_pairwise_volume_tilt_min_score_gap or 0.0))
            if score_gap < min_score_gap:
                continue

            avg_ret20_zscore: float = float(
                np.mean(
                    [
                        float(plan.get("selection_pairwise_feature_ret_20d_zscore_120") or 0.0)
                        for plan in direction_plans
                    ]
                )
            )
            avg_rsi_value: float = float(
                np.mean([float(plan.get("rsi_value") or 0.0) for plan in direction_plans])
            )
            long_max_avg_ret20_zscore: float = float(
                self.selection_pairwise_volume_tilt_long_max_avg_ret20_zscore
            )
            long_max_avg_rsi: float = float(self.selection_pairwise_volume_tilt_long_max_avg_rsi)
            long_score_gap_reference: float = float(self.selection_pairwise_volume_tilt_long_score_gap_reference)
            long_active_ratio_full_strength_max: float = float(
                self.selection_pairwise_volume_tilt_long_active_ratio_full_strength_max
            )
            long_base_volume_reference: float = float(
                self.selection_pairwise_volume_tilt_long_base_volume_reference
            )
            long_active_positions_reference: float = float(
                self.selection_pairwise_volume_tilt_long_active_positions_reference
            )
            long_max_range_zscore_reference: float = float(
                self.selection_pairwise_volume_tilt_long_max_range_zscore_reference
            )
            max_range_zscore: float = float(
                np.max(
                    [
                        float(plan.get("selection_pairwise_feature_range_pct_zscore_120") or 0.0)
                        for plan in direction_plans
                    ]
                )
            )
            blocked_by_state: bool = bool(
                direction == "long"
                and (
                    (
                        long_max_avg_ret20_zscore >= 0.0
                        and avg_ret20_zscore > long_max_avg_ret20_zscore
                    )
                    or (long_max_avg_rsi >= 0.0 and avg_rsi_value > long_max_avg_rsi)
                )
            )
            confidence_scale: float = 1.0
            if direction == "long" and long_score_gap_reference > 0.0:
                confidence_scale = min(1.0, max(0.0, score_gap / long_score_gap_reference))
            active_ratio: float = float(
                np.mean(
                    [
                        float(plan.get("active_positions_before") or 0.0)
                        / max(1.0, float(plan.get("effective_max_concurrent_positions") or 0.0))
                        for plan in direction_plans
                    ]
                    )
            )
            avg_active_positions_before: float = float(
                np.mean([float(plan.get("active_positions_before") or 0.0) for plan in direction_plans])
            )
            avg_base_volume_before: float = float(
                np.mean(
                    [
                        max(0.0, float(plan["sizing"].get("selected_volume") or 0.0))
                        for plan in direction_plans
                    ]
                )
            )
            crowding_scale: float = 1.0
            if direction == "long" and 0.0 <= long_active_ratio_full_strength_max < 1.0:
                if active_ratio > long_active_ratio_full_strength_max:
                    crowding_scale = max(
                        0.0,
                        (1.0 - active_ratio) / max(1e-9, 1.0 - long_active_ratio_full_strength_max),
                    )
            base_volume_scale: float = 1.0
            if direction == "long" and long_base_volume_reference > 0.0:
                base_volume_scale = min(1.0, long_base_volume_reference / max(1e-9, avg_base_volume_before))
            active_positions_scale: float = 1.0
            if direction == "long" and long_active_positions_reference > 0.0:
                active_positions_scale = min(
                    1.0,
                    long_active_positions_reference / max(1e-9, avg_active_positions_before),
                )
            range_scale: float = 1.0
            if direction == "long" and long_max_range_zscore_reference > 0.0:
                range_scale = min(
                    1.0,
                    long_max_range_zscore_reference / max(1e-9, max_range_zscore),
                )
            effective_direction_strength: float = (
                direction_strength
                * confidence_scale
                * crowding_scale
                * base_volume_scale
                * active_positions_scale
                * range_scale
            )

            for plan in direction_plans:
                sizing = dict(plan["sizing"])
                sizing["selection_pairwise_volume_tilt_state_avg_ret20_zscore"] = avg_ret20_zscore
                sizing["selection_pairwise_volume_tilt_state_avg_rsi"] = avg_rsi_value
                sizing["selection_pairwise_volume_tilt_state_max_range_zscore"] = max_range_zscore
                sizing["selection_pairwise_volume_tilt_state_blocked"] = int(blocked_by_state)
                sizing["selection_pairwise_volume_tilt_active_ratio"] = active_ratio
                sizing["selection_pairwise_volume_tilt_avg_active_positions_before"] = avg_active_positions_before
                sizing["selection_pairwise_volume_tilt_crowding_scale"] = crowding_scale
                sizing["selection_pairwise_volume_tilt_avg_base_volume_before"] = avg_base_volume_before
                sizing["selection_pairwise_volume_tilt_base_volume_scale"] = base_volume_scale
                sizing["selection_pairwise_volume_tilt_active_positions_scale"] = active_positions_scale
                sizing["selection_pairwise_volume_tilt_range_scale"] = range_scale
                sizing["selection_pairwise_volume_tilt_confidence_scale"] = confidence_scale
                sizing["selection_pairwise_volume_tilt_effective_direction_strength"] = effective_direction_strength
                plan["sizing"] = sizing

            if blocked_by_state:
                continue

            center = (count - 1) / 2.0
            for index, plan in enumerate(direction_plans):
                base_volume = max(0, int(plan["sizing"].get("selected_volume") or 0))
                if base_volume <= 0:
                    continue

                relative_rank = (center - float(index)) / max(center, 1.0)
                multiplier = max(0.0, 1.0 + effective_direction_strength * relative_rank)
                tilted_volume = int(round(base_volume * multiplier))
                if 0 < tilted_volume < self.min_position_size:
                    tilted_volume = self.min_position_size

                sizing = dict(plan["sizing"])
                sizing["selection_pairwise_volume_tilt_applied"] = 1
                sizing["selection_pairwise_volume_tilt_direction_strength"] = direction_strength
                sizing["selection_pairwise_volume_tilt_effective_direction_strength"] = effective_direction_strength
                sizing["selection_pairwise_volume_tilt_confidence_scale"] = confidence_scale
                sizing["selection_pairwise_volume_tilt_active_ratio"] = active_ratio
                sizing["selection_pairwise_volume_tilt_avg_active_positions_before"] = avg_active_positions_before
                sizing["selection_pairwise_volume_tilt_crowding_scale"] = crowding_scale
                sizing["selection_pairwise_volume_tilt_avg_base_volume_before"] = avg_base_volume_before
                sizing["selection_pairwise_volume_tilt_base_volume_scale"] = base_volume_scale
                sizing["selection_pairwise_volume_tilt_active_positions_scale"] = active_positions_scale
                sizing["selection_pairwise_volume_tilt_multiplier"] = multiplier
                sizing["selection_pairwise_volume_tilt_volume_before"] = base_volume
                sizing["selection_pairwise_volume_tilt_group_size"] = count
                sizing["selection_pairwise_volume_tilt_score_gap"] = score_gap
                sizing["selection_pairwise_volume_tilt_top_gap"] = top_gap
                sizing["selection_pairwise_volume_tilt_state_avg_ret20_zscore"] = avg_ret20_zscore
                sizing["selection_pairwise_volume_tilt_state_avg_rsi"] = avg_rsi_value
                sizing["selection_pairwise_volume_tilt_state_max_range_zscore"] = max_range_zscore
                sizing["selection_pairwise_volume_tilt_state_blocked"] = 0
                sizing["selection_pairwise_volume_tilt_range_scale"] = range_scale
                sizing["selected_volume"] = max(0, tilted_volume)
                plan["sizing"] = sizing
                plan["volume"] = max(0, tilted_volume)

            if direction_date is not None:
                self.selection_pairwise_volume_tilt_last_date_by_direction[direction] = direction_date

    def _plan_flat_entry_candidates(self, day_contexts: list[DailyEntryContext]) -> dict[str, dict[str, Any]]:
        base_active_positions = self._count_active_positions()
        candidate_plans: list[dict[str, Any]] = []
        for context in day_contexts:
            if context.current_pos != 0:
                continue
            plan = self._build_flat_entry_candidate_plan(context, base_active_positions)
            if plan is not None:
                candidate_plans.append(plan)

        self._apply_selection_pairwise_scores(candidate_plans)

        openable_plans = [plan for plan in candidate_plans if plan["native_openable"]]
        if self.selection_pairwise_runtime:
            openable_plans.sort(
                key=lambda item: (-float(item["selection_pairwise_score"]), str(item["product_vt_symbol"]))
            )
            for rank, plan in enumerate(openable_plans, start=1):
                plan["selection_pairwise_rank"] = rank

        opened_count = 0
        for plan in openable_plans:
            sizing = dict(plan["sizing"])
            active_positions_before = base_active_positions + opened_count
            effective_max_positions = int(sizing.get("effective_max_concurrent_positions") or self.max_concurrent_positions)
            if active_positions_before >= effective_max_positions:
                plan["candidate_status"] = "skipped"
                plan["skip_reason"] = "concurrent_limit"
            else:
                plan["candidate_status"] = "opened"
                opened_count += 1

        opened_plans = [plan for plan in openable_plans if plan.get("candidate_status") == "opened"]
        self._apply_selection_pairwise_volume_tilt(opened_plans)

        opened_count = 0
        planned_intraday_margin = 0.0
        openable_candidate_count = len(openable_plans)
        for plan in openable_plans:
            sizing = dict(plan["sizing"])
            active_positions_before = base_active_positions + opened_count
            effective_max_positions = int(
                sizing.get("effective_max_concurrent_positions") or self.max_concurrent_positions
            )
            selected_volume = max(0, int(sizing.get("selected_volume") or plan.get("volume") or 0))
            margin_per_contract = float(sizing.get("margin_per_contract") or 0.0)
            gate_fields = self._incremental_margin_budget_gate_fields(
                planned_intraday_margin_before=planned_intraday_margin,
                selected_volume=selected_volume,
                margin_per_contract=margin_per_contract,
                openable_candidate_count=openable_candidate_count,
                selection_pairwise_rank=int(plan.get("selection_pairwise_rank") or 0),
                entry_context="flat_entry",
            )
            sizing.update(gate_fields)
            plan["active_positions_before"] = active_positions_before
            plan["remaining_position_slots"] = max(0, effective_max_positions - active_positions_before)
            plan["volume"] = selected_volume
            if selected_volume <= 0:
                plan["candidate_status"] = "skipped"
                plan["skip_reason"] = "sizing_zero_volume"
            elif active_positions_before >= effective_max_positions:
                plan["candidate_status"] = "skipped"
                plan["skip_reason"] = "concurrent_limit"
            elif int(gate_fields["incremental_margin_budget_gate_enabled"]) and not int(
                gate_fields["incremental_margin_budget_gate_passed"]
            ):
                plan["candidate_status"] = "skipped"
                plan["skip_reason"] = "incremental_margin_budget_gate"
            else:
                plan["candidate_status"] = "opened"
                opened_count += 1
                planned_intraday_margin += float(
                    gate_fields["incremental_margin_budget_gate_planned_entry_margin"]
                )
            plan["sizing"] = sizing

        for plan in openable_plans:
            sizing = dict(plan["sizing"])
            active_positions_before = int(plan.get("active_positions_before") or base_active_positions)
            effective_max_positions = int(
                sizing.get("effective_max_concurrent_positions") or self.max_concurrent_positions
            )
            plan["active_positions_before"] = active_positions_before
            plan["remaining_position_slots"] = max(0, effective_max_positions - active_positions_before)
            sizing["selection_pairwise_score"] = plan["selection_pairwise_score"]
            sizing["selection_pairwise_rank"] = plan["selection_pairwise_rank"]
            sizing["selection_pairwise_veto_flag"] = plan["selection_pairwise_veto_flag"]
            sizing["selection_pairwise_model_tag"] = plan["selection_pairwise_model_tag"]
            sizing["selection_pairwise_enabled"] = plan["selection_pairwise_enabled"]
            sizing["selection_pairwise_veto_penalty"] = plan["selection_pairwise_veto_penalty"]
            sizing["selection_pairwise_feature_ret_20d_zscore_120"] = plan["selection_pairwise_feature_ret_20d_zscore_120"]
            sizing["selection_pairwise_feature_close_position_60d_cs_zscore_1d"] = plan[
                "selection_pairwise_feature_close_position_60d_cs_zscore_1d"
            ]
            sizing["selection_pairwise_feature_range_pct_zscore_120"] = plan["selection_pairwise_feature_range_pct_zscore_120"]
            sizing["selection_pairwise_runtime_veto_match_local"] = plan["selection_pairwise_runtime_veto_match_local"]
            sizing["selection_pairwise_volume_tilt_applied"] = int(
                sizing.get("selection_pairwise_volume_tilt_applied", 0) or 0
            )
            sizing["selection_pairwise_volume_tilt_direction_strength"] = float(
                sizing.get("selection_pairwise_volume_tilt_direction_strength", 0.0) or 0.0
            )
            sizing["selection_pairwise_volume_tilt_multiplier"] = float(
                sizing.get("selection_pairwise_volume_tilt_multiplier", 1.0) or 1.0
            )
            sizing["selection_pairwise_volume_tilt_volume_before"] = int(
                sizing.get("selection_pairwise_volume_tilt_volume_before", sizing.get("selected_volume", 0)) or 0
            )
            sizing["selection_pairwise_volume_tilt_group_size"] = int(
                sizing.get("selection_pairwise_volume_tilt_group_size", 0) or 0
            )
            sizing["selection_pairwise_volume_tilt_score_gap"] = float(
                sizing.get("selection_pairwise_volume_tilt_score_gap", 0.0) or 0.0
            )
            sizing["selection_pairwise_volume_tilt_top_gap"] = float(
                sizing.get("selection_pairwise_volume_tilt_top_gap", 0.0) or 0.0
            )
            sizing["remaining_position_slots"] = plan["remaining_position_slots"]
            plan["sizing"] = sizing

        for plan in candidate_plans:
            if plan["native_openable"]:
                continue
            sizing = dict(plan["sizing"])
            sizing["selection_pairwise_score"] = plan["selection_pairwise_score"]
            sizing["selection_pairwise_rank"] = plan["selection_pairwise_rank"]
            sizing["selection_pairwise_veto_flag"] = plan["selection_pairwise_veto_flag"]
            sizing["selection_pairwise_model_tag"] = plan["selection_pairwise_model_tag"]
            sizing["selection_pairwise_enabled"] = plan["selection_pairwise_enabled"]
            sizing["selection_pairwise_veto_penalty"] = plan["selection_pairwise_veto_penalty"]
            sizing["selection_pairwise_feature_ret_20d_zscore_120"] = plan["selection_pairwise_feature_ret_20d_zscore_120"]
            sizing["selection_pairwise_feature_close_position_60d_cs_zscore_1d"] = plan[
                "selection_pairwise_feature_close_position_60d_cs_zscore_1d"
            ]
            sizing["selection_pairwise_feature_range_pct_zscore_120"] = plan["selection_pairwise_feature_range_pct_zscore_120"]
            sizing["selection_pairwise_runtime_veto_match_local"] = plan["selection_pairwise_runtime_veto_match_local"]
            sizing["selection_pairwise_volume_tilt_applied"] = int(
                sizing.get("selection_pairwise_volume_tilt_applied", 0) or 0
            )
            sizing["selection_pairwise_volume_tilt_direction_strength"] = float(
                sizing.get("selection_pairwise_volume_tilt_direction_strength", 0.0) or 0.0
            )
            sizing["selection_pairwise_volume_tilt_multiplier"] = float(
                sizing.get("selection_pairwise_volume_tilt_multiplier", 1.0) or 1.0
            )
            sizing["selection_pairwise_volume_tilt_volume_before"] = int(
                sizing.get("selection_pairwise_volume_tilt_volume_before", sizing.get("selected_volume", 0)) or 0
            )
            sizing["selection_pairwise_volume_tilt_group_size"] = int(
                sizing.get("selection_pairwise_volume_tilt_group_size", 0) or 0
            )
            sizing["selection_pairwise_volume_tilt_score_gap"] = float(
                sizing.get("selection_pairwise_volume_tilt_score_gap", 0.0) or 0.0
            )
            sizing["selection_pairwise_volume_tilt_top_gap"] = float(
                sizing.get("selection_pairwise_volume_tilt_top_gap", 0.0) or 0.0
            )
            sizing["remaining_position_slots"] = plan["remaining_position_slots"]
            plan["sizing"] = sizing
            plan["candidate_status"] = "skipped"
            plan["active_positions_before"] = base_active_positions

        return {str(plan["product_vt_symbol"]): plan for plan in candidate_plans}

    def _build_daily_env_gate_snapshot(self, day_contexts: list[DailyEntryContext]) -> dict[str, Any]:
        snapshot: dict[str, Any] = {
            "env_gate_enabled": int(self.enable_weighted_env_gate or self.enable_portfolio_env_gate),
            "env_gate_weight": 1.0,
            "env_candidate_count": 0,
            "env_native_selected_rate": 0.0,
            "env_native_selected_count": 0,
            "env_avg_close_position_60d": 0.0,
            "env_avg_range_pct_zscore_120": 0.0,
            "env_gate_close_component": 1.0,
            "env_gate_range_component": 1.0,
            "env_gate_selected_component": 1.0,
        }
        if not (self.enable_weighted_env_gate or self.enable_portfolio_env_gate):
            return snapshot

        candidate_rows: list[dict[str, float]] = []
        for context in day_contexts:
            if context.current_pos != 0:
                continue

            signal: str = str(context.signal_data.get("signal", ""))
            if signal.startswith("long"):
                direction = "long"
            elif signal.startswith("short"):
                direction = "short"
            else:
                continue

            feature_row = self._extract_env_gate_candidate_features(context.history)
            if not feature_row:
                continue

            sizing = self._calculate_entry_sizing(
                context.target_contract,
                direction,
                context.target_bar,
                context.history,
                context.signal_data,
                entry_context="env_probe",
                apply_env_gate=False,
            )
            base_volume = int(sizing["selected_volume"])
            candidate_rows.append(
                {
                    "feature_close_position_60d": float(feature_row["feature_close_position_60d"]),
                    "feature_range_pct_zscore_120": float(feature_row["feature_range_pct_zscore_120"]),
                    "native_selected_flag": float(self._is_native_openable_candidate(signal, direction, base_volume)),
                }
            )

        if not candidate_rows:
            return snapshot

        candidate_df = pd.DataFrame(candidate_rows)
        avg_close_position = self._safe_float_value(candidate_df["feature_close_position_60d"].mean())
        avg_range_zscore = self._safe_float_value(candidate_df["feature_range_pct_zscore_120"].mean())
        native_selected_rate = self._safe_float_value(candidate_df["native_selected_flag"].mean())

        close_good_max = float(self.weighted_env_gate_close_position_good_max)
        close_bad_min = float(self.weighted_env_gate_close_position_bad_min)
        range_good_min = float(self.weighted_env_gate_range_good_min)
        range_bad_max = float(self.weighted_env_gate_range_bad_max)
        selected_good_max = float(self.weighted_env_gate_selected_rate_good_max)
        selected_bad_min = float(self.weighted_env_gate_selected_rate_bad_min)
        weight_floor = self._clip01(float(self.weighted_env_gate_weight_floor))

        close_denominator = max(close_bad_min - close_good_max, 1e-9)
        range_denominator = max(range_good_min - range_bad_max, 1e-9)
        selected_denominator = max(selected_bad_min - selected_good_max, 1e-9)

        close_component = self._clip01((close_bad_min - avg_close_position) / close_denominator)
        range_component = self._clip01((avg_range_zscore - range_bad_max) / range_denominator)
        selected_component = self._clip01((selected_bad_min - native_selected_rate) / selected_denominator)
        base_weight = (close_component + range_component + selected_component) / 3.0
        env_gate_weight = weight_floor + (1.0 - weight_floor) * base_weight

        snapshot.update(
            {
                "env_gate_weight": self._clip01(env_gate_weight),
                "env_candidate_count": int(len(candidate_df)),
                "env_native_selected_rate": native_selected_rate,
                "env_native_selected_count": int(round(float(candidate_df["native_selected_flag"].sum()))),
                "env_avg_close_position_60d": avg_close_position,
                "env_avg_range_pct_zscore_120": avg_range_zscore,
                "env_gate_close_component": close_component,
                "env_gate_range_component": range_component,
                "env_gate_selected_component": selected_component,
            }
        )
        return snapshot

    def _apply_env_gate_to_volume(
        self,
        base_volume: int,
        *,
        entry_context: str,
        apply_env_gate: bool,
    ) -> dict[str, Any]:
        base_selected_volume = max(0, int(base_volume))
        snapshot = self.current_env_gate_snapshot or {}
        env_gate_enabled = int(self.enable_weighted_env_gate and entry_context == "flat_entry")
        env_gate_weight = 1.0
        selected_volume = base_selected_volume

        if env_gate_enabled:
            env_gate_weight = self._clip01(float(snapshot.get("env_gate_weight", 1.0)))
            if apply_env_gate:
                selected_volume = int(math.floor(base_selected_volume * env_gate_weight))
                if 0 < selected_volume < self.min_position_size:
                    selected_volume = 0

        portfolio_drawdown_gate_enabled = int(
            self.enable_portfolio_drawdown_gate and entry_context == "flat_entry"
        )
        portfolio_drawdown_gate_weight = self._portfolio_drawdown_gate_weight(entry_context)
        if portfolio_drawdown_gate_enabled and apply_env_gate:
            selected_volume = int(math.floor(selected_volume * portfolio_drawdown_gate_weight))
            if 0 < selected_volume < self.min_position_size:
                selected_volume = 0

        return {
            "selected_volume_ungated": base_selected_volume,
            "selected_volume": max(0, int(selected_volume)),
            "env_gate_enabled": env_gate_enabled,
            "env_gate_weight": env_gate_weight,
            "env_candidate_count": int(snapshot.get("env_candidate_count", 0)),
            "env_native_selected_rate": float(snapshot.get("env_native_selected_rate", 0.0)),
            "env_native_selected_count": int(snapshot.get("env_native_selected_count", 0)),
            "env_avg_close_position_60d": float(snapshot.get("env_avg_close_position_60d", 0.0)),
            "env_avg_range_pct_zscore_120": float(snapshot.get("env_avg_range_pct_zscore_120", 0.0)),
            "env_gate_close_component": float(snapshot.get("env_gate_close_component", 1.0)),
            "env_gate_range_component": float(snapshot.get("env_gate_range_component", 1.0)),
            "env_gate_selected_component": float(snapshot.get("env_gate_selected_component", 1.0)),
            "env_gate_entry_context": entry_context,
            "portfolio_drawdown_gate_enabled": portfolio_drawdown_gate_enabled,
            "portfolio_drawdown_gate_weight": portfolio_drawdown_gate_weight,
            "portfolio_drawdown_pct": float(self.portfolio_drawdown_pct or 0.0),
            "portfolio_equity_high_water": float(self.portfolio_equity_high_water or self.base_capital),
        }

    def _calculate_entry_sizing(
        self,
        vt_symbol: str,
        direction: str,
        bar: BarData,
        history: pd.DataFrame,
        signal_data: dict[str, Any],
        risk_mode_override: str | None = None,
        entry_context: str = "flat_entry",
        apply_env_gate: bool = True,
        active_positions_before: int | None = None,
        correlation_snapshot: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        signal = str(signal_data.get("signal", ""))
        recovery_fields = self._entry_structure_recovery_fields(
            signal=signal,
            direction=direction,
            entry_context=entry_context,
            rsi_value=signal_data.get("rsi_value"),
            active_positions_before=active_positions_before,
            correlation_snapshot=correlation_snapshot,
        )
        effective_risk_multiplier = float(
            recovery_fields.get(
                "streak_entry_structure_risk_recovery_effective_multiplier",
                self._current_streak_multiplier(),
            )
        )
        if self.fixed_size > 0:
            price: float = float(bar.close_price)
            stop_price: float = self._entry_stop_price(direction, bar, history, use_day_extreme=True)
            size: int = self.get_size(vt_symbol)
            margin_ratio: float = self._margin_ratio_for_symbol(vt_symbol)
            risk_per_contract: float = max(abs(price - stop_price) * size, max(float(self.get_pricetick(vt_symbol)) * size, 1.0))
            margin_per_contract: float = price * size * margin_ratio
            allowed_capital: float = self._allowed_capital(entry_context)
            single_trade_capital_limit: float = self._single_trade_capital_limit()
            free_capital: float = self._free_capital_after_reservations()
            limited_balance: float = self._limited_available_balance(entry_context)
            contracts_by_single_trade_cap: int | None = (
                int(single_trade_capital_limit // margin_per_contract) if margin_per_contract > 0 else None
            )
            volume: int = min(
                int(self.fixed_size),
                int(contracts_by_single_trade_cap or 0),
                self.max_position_size,
            )
            if 0 < volume < self.min_position_size:
                volume = 0
            env_gate_fields = self._apply_env_gate_to_volume(
                volume,
                entry_context=entry_context,
                apply_env_gate=apply_env_gate,
            )
            return {
                "risk_mode": risk_mode_override or str(signal_data.get("risk_mode", "regular")),
                "risk_ratio": None,
                "risk_amount": None,
                "limited_balance": limited_balance,
                "allowed_capital": allowed_capital,
                "single_trade_capital_limit": single_trade_capital_limit,
                "free_capital": free_capital,
                "reserved_margin_before": self._reserved_margin_in_use(),
                "stop_price": stop_price,
                "risk_per_contract": risk_per_contract,
                "margin_ratio": margin_ratio,
                "margin_per_contract": margin_per_contract,
                "contracts_by_risk": None,
                "contracts_by_margin": None,
                "contracts_by_single_trade_cap": contracts_by_single_trade_cap,
                "risk_multiplier": effective_risk_multiplier,
                "sizing_method": "fixed_size",
                "effective_capital_usage_ratio": self._effective_capital_usage_ratio(entry_context),
                "effective_max_concurrent_positions": self._effective_max_concurrent_positions(entry_context),
                **recovery_fields,
                **env_gate_fields,
            }

        limited_balance: float = self._limited_available_balance(entry_context)
        allowed_capital: float = self._allowed_capital(entry_context)
        single_trade_capital_limit: float = self._single_trade_capital_limit()
        free_capital: float = self._free_capital_after_reservations()
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

        risk_amount: float = self._risk_amount_from_ratio(
            risk_ratio,
            limited_balance,
            risk_multiplier_override=effective_risk_multiplier,
        )
        stop_price: float = self._entry_stop_price(direction, bar, history, use_day_extreme=True)
        size: int = self.get_size(vt_symbol)
        risk_per_contract: float = abs(float(bar.close_price) - stop_price) * size

        min_risk: float = max(float(self.get_pricetick(vt_symbol)) * size, 1.0)
        risk_per_contract = max(risk_per_contract, min_risk)

        contracts_by_risk: int = int(risk_amount // risk_per_contract) if risk_per_contract > 0 else 0
        margin_ratio: float = self._margin_ratio_for_symbol(vt_symbol)
        margin_per_contract: float = float(bar.close_price) * size * margin_ratio
        contracts_by_margin: int = int(limited_balance // margin_per_contract) if margin_per_contract > 0 else 0
        contracts_by_single_trade_cap: int = (
            int(single_trade_capital_limit // margin_per_contract) if margin_per_contract > 0 else 0
        )

        volume: int = min(
            contracts_by_risk,
            contracts_by_margin,
            contracts_by_single_trade_cap,
            self.max_position_size,
        )
        if 0 < volume < self.min_position_size:
            volume = 0
        env_gate_fields = self._apply_env_gate_to_volume(
            volume,
            entry_context=entry_context,
            apply_env_gate=apply_env_gate,
        )

        return {
            "risk_mode": risk_mode,
            "risk_ratio": risk_ratio,
            "risk_amount": risk_amount,
            "limited_balance": limited_balance,
            "allowed_capital": allowed_capital,
            "single_trade_capital_limit": single_trade_capital_limit,
            "free_capital": free_capital,
            "reserved_margin_before": self._reserved_margin_in_use(),
            "stop_price": stop_price,
            "risk_per_contract": risk_per_contract,
            "margin_ratio": margin_ratio,
            "margin_per_contract": margin_per_contract,
            "contracts_by_risk": contracts_by_risk,
            "contracts_by_margin": contracts_by_margin,
            "contracts_by_single_trade_cap": contracts_by_single_trade_cap,
            "risk_multiplier": effective_risk_multiplier,
            "sizing_method": "risk_budget",
            "effective_capital_usage_ratio": self._effective_capital_usage_ratio(entry_context),
            "effective_max_concurrent_positions": self._effective_max_concurrent_positions(entry_context),
            **recovery_fields,
            **env_gate_fields,
        }

    def _calculate_entry_volume(
        self,
        vt_symbol: str,
        direction: str,
        bar: BarData,
        history: pd.DataFrame,
        signal_data: dict[str, Any],
        risk_mode_override: str | None = None,
        entry_context: str = "flat_entry",
    ) -> int:
        sizing: dict[str, Any] = self._calculate_entry_sizing(
            vt_symbol,
            direction,
            bar,
            history,
            signal_data,
            risk_mode_override=risk_mode_override,
            entry_context=entry_context,
        )
        return int(sizing["selected_volume"])

    def _count_active_positions(self) -> int:
        count: int = 0
        for state in self.states.values():
            if state.contract_vt_symbol and self.get_pos(state.contract_vt_symbol) != 0:
                count += 1
        return count + len(self.pending_active_products)

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
                entry_price_synced=False,
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
                entry_price_synced=False,
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
                "allowed_capital": self._allowed_capital(),
                "free_capital": self._free_capital_after_reservations(),
                "reserved_margin_before": self._reserved_margin_in_use(),
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

    def _apply_state_target(self, state: ProductState, execution_price_override: float | None = None) -> None:
        if not state.contract_vt_symbol:
            return
        volume: int = state.active_volume()
        target: int = -volume if state.direction == "short" else volume
        if execution_price_override is not None and execution_price_override > 0:
            self.execution_price_overrides[state.contract_vt_symbol] = execution_price_override
        self.set_target(state.contract_vt_symbol, target)

    def _record_trade_event(
        self,
        *,
        bar: BarData | None,
        contract_vt_symbol: str,
        product_vt_symbol: str,
        position_direction: str,
        offset: str,
        reason: str,
        volume: int,
        price: float,
    ) -> None:
        if volume <= 0 or not contract_vt_symbol or bar is None:
            return

        if offset == "Close":
            trade_direction = Direction.SHORT.value if position_direction == "long" else Direction.LONG.value
        else:
            trade_direction = Direction.LONG.value if position_direction == "long" else Direction.SHORT.value

        self.trade_event_diagnostics.append(
            {
                "datetime": bar.datetime,
                "date": bar.datetime.date(),
                "vt_symbol": contract_vt_symbol,
                "product_vt_symbol": product_vt_symbol,
                "position_direction": position_direction,
                "direction": trade_direction,
                "offset": offset,
                "reason": reason,
                "volume": int(volume),
                "price": float(price),
            }
        )
        if offset == "Close":
            self._queue_pending_close_reason(contract_vt_symbol, reason, volume)

    def _record_entry_candidate_snapshot(
        self,
        *,
        product_vt_symbol: str,
        contract_vt_symbol: str,
        direction: str,
        bar: BarData,
        signal: str,
        entry_context: str,
        candidate_status: str,
        skip_reason: str,
        signal_data: dict[str, Any],
        sizing_snapshot: dict[str, Any],
        active_positions_before: int,
    ) -> None:
        entry_price: float = float(bar.close_price)
        stop_price: float = float(sizing_snapshot.get("stop_price") or entry_price)
        size: int = self.get_size(contract_vt_symbol)
        margin_ratio: float = float(sizing_snapshot.get("margin_ratio", self._margin_ratio_for_symbol(contract_vt_symbol)) or 0.0)
        risk_per_contract: float | None = sizing_snapshot.get("risk_per_contract")
        if risk_per_contract is None:
            min_risk: float = max(float(self.get_pricetick(contract_vt_symbol)) * size, 1.0)
            risk_per_contract = max(abs(entry_price - stop_price) * size, min_risk)

        margin_per_contract: float | None = sizing_snapshot.get("margin_per_contract")
        if margin_per_contract is None:
            margin_per_contract = entry_price * size * margin_ratio

        selected_volume: int = int(sizing_snapshot.get("selected_volume") or 0)
        estimated_equity: float = float(self.estimated_equity or self.base_capital)
        reserved_margin_before: float = float(sizing_snapshot.get("reserved_margin_before", self._reserved_margin_in_use()) or 0.0)
        projected_margin_after: float = reserved_margin_before + max(0, selected_volume) * float(margin_per_contract)
        effective_max_concurrent_positions: int = int(
            sizing_snapshot.get("effective_max_concurrent_positions") or self.max_concurrent_positions
        )
        remaining_slots: int = max(0, effective_max_concurrent_positions - active_positions_before)

        self.entry_candidate_snapshots.append(
            {
                "candidate_index": len(self.entry_candidate_snapshots) + 1,
                "datetime": bar.datetime,
                "date": bar.datetime.date(),
                "product_vt_symbol": product_vt_symbol,
                "contract_vt_symbol": contract_vt_symbol,
                "entry_context": entry_context,
                "direction": direction,
                "signal": signal,
                "candidate_status": candidate_status,
                "skip_reason": skip_reason,
                "passed_initial_filter": 1,
                "estimated_equity": estimated_equity,
                "total_margin_in_use_before": reserved_margin_before,
                "allowed_capital": float(sizing_snapshot.get("allowed_capital") or 0.0),
                "single_trade_capital_limit": float(sizing_snapshot.get("single_trade_capital_limit") or 0.0),
                "effective_capital_usage_ratio": float(
                    sizing_snapshot.get("effective_capital_usage_ratio") or self.max_capital_usage_ratio
                ),
                "free_capital": float(sizing_snapshot.get("free_capital") or 0.0),
                "limited_balance": float(sizing_snapshot.get("limited_balance") or 0.0),
                "effective_single_trade_capital_usage_ratio": float(self.max_single_trade_capital_usage_ratio),
                "effective_streak_risk_multipliers": self.streak_risk_multipliers,
                "risk_mode": str(sizing_snapshot.get("risk_mode", signal_data.get("risk_mode", "regular"))),
                "risk_ratio": sizing_snapshot.get("risk_ratio"),
                "risk_multiplier": float(sizing_snapshot.get("risk_multiplier") or self._current_streak_multiplier()),
                "streak_entry_structure_risk_recovery_enabled": int(
                    sizing_snapshot.get("streak_entry_structure_risk_recovery_enabled") or 0
                ),
                "streak_entry_structure_risk_recovery_applied": int(
                    sizing_snapshot.get("streak_entry_structure_risk_recovery_applied") or 0
                ),
                "streak_entry_structure_risk_recovery_reason": str(
                    sizing_snapshot.get("streak_entry_structure_risk_recovery_reason") or ""
                ),
                "streak_entry_structure_risk_recovery_base_multiplier": float(
                    sizing_snapshot.get("streak_entry_structure_risk_recovery_base_multiplier")
                    or self._current_streak_multiplier()
                ),
                "streak_entry_structure_risk_recovery_effective_multiplier": float(
                    sizing_snapshot.get("streak_entry_structure_risk_recovery_effective_multiplier")
                    or sizing_snapshot.get("risk_multiplier")
                    or self._current_streak_multiplier()
                ),
                "streak_entry_structure_risk_recovery_rsi_confirmation_enabled": int(
                    sizing_snapshot.get("streak_entry_structure_risk_recovery_rsi_confirmation_enabled") or 0
                ),
                "streak_entry_structure_risk_recovery_rsi_value": float(
                    sizing_snapshot.get("streak_entry_structure_risk_recovery_rsi_value")
                    if sizing_snapshot.get("streak_entry_structure_risk_recovery_rsi_value") is not None
                    else float("nan")
                ),
                "streak_entry_structure_risk_recovery_long_min_rsi": float(
                    sizing_snapshot.get("streak_entry_structure_risk_recovery_long_min_rsi")
                    or self.streak_entry_structure_recovery_long_min_rsi
                ),
                "streak_entry_structure_risk_recovery_short_max_rsi": float(
                    sizing_snapshot.get("streak_entry_structure_risk_recovery_short_max_rsi")
                    or self.streak_entry_structure_recovery_short_max_rsi
                ),
                "streak_entry_structure_risk_recovery_portfolio_drawdown_pct": float(
                    sizing_snapshot.get("streak_entry_structure_risk_recovery_portfolio_drawdown_pct")
                    or self.portfolio_drawdown_pct
                    or 0.0
                ),
                "streak_entry_structure_risk_recovery_max_portfolio_drawdown_pct": float(
                    sizing_snapshot.get("streak_entry_structure_risk_recovery_max_portfolio_drawdown_pct")
                    if sizing_snapshot.get("streak_entry_structure_risk_recovery_max_portfolio_drawdown_pct") is not None
                    else self.streak_entry_structure_recovery_max_portfolio_drawdown_pct
                ),
                "target_risk_amount": sizing_snapshot.get("risk_amount"),
                "planned_entry_price": entry_price,
                "stop_price": stop_price,
                "stop_distance": abs(entry_price - stop_price),
                "size": size,
                "risk_per_contract": risk_per_contract,
                "margin_ratio": margin_ratio,
                "margin_per_contract": margin_per_contract,
                "projected_total_margin_after": projected_margin_after,
                "incremental_margin_budget_gate_enabled": int(
                    sizing_snapshot.get("incremental_margin_budget_gate_enabled") or 0
                ),
                "incremental_margin_budget_gate_min_openable_candidates": int(
                    sizing_snapshot.get("incremental_margin_budget_gate_min_openable_candidates") or 0
                ),
                "incremental_margin_budget_gate_openable_candidate_count": int(
                    sizing_snapshot.get("incremental_margin_budget_gate_openable_candidate_count") or 0
                ),
                "incremental_margin_budget_gate_protected_selection_rank": int(
                    sizing_snapshot.get("incremental_margin_budget_gate_protected_selection_rank") or 0
                ),
                "incremental_margin_budget_gate_candidate_selection_rank": int(
                    sizing_snapshot.get("incremental_margin_budget_gate_candidate_selection_rank") or 0
                ),
                "incremental_margin_budget_gate_protected_by_rank": int(
                    sizing_snapshot.get("incremental_margin_budget_gate_protected_by_rank") or 0
                ),
                "incremental_margin_budget_gate_budget": float(
                    sizing_snapshot.get("incremental_margin_budget_gate_budget") or 0.0
                ),
                "incremental_margin_budget_gate_reserved_margin_before": float(
                    sizing_snapshot.get("incremental_margin_budget_gate_reserved_margin_before") or 0.0
                ),
                "incremental_margin_budget_gate_planned_intraday_margin_before": float(
                    sizing_snapshot.get("incremental_margin_budget_gate_planned_intraday_margin_before") or 0.0
                ),
                "incremental_margin_budget_gate_planned_entry_margin": float(
                    sizing_snapshot.get("incremental_margin_budget_gate_planned_entry_margin") or 0.0
                ),
                "incremental_margin_budget_gate_projected_margin_before": float(
                    sizing_snapshot.get("incremental_margin_budget_gate_projected_margin_before") or 0.0
                ),
                "incremental_margin_budget_gate_projected_margin_after": float(
                    sizing_snapshot.get("incremental_margin_budget_gate_projected_margin_after") or 0.0
                ),
                "incremental_margin_budget_gate_passed": int(
                    sizing_snapshot.get("incremental_margin_budget_gate_passed", 1) or 0
                ),
                "contracts_by_risk": sizing_snapshot.get("contracts_by_risk"),
                "contracts_by_margin": sizing_snapshot.get("contracts_by_margin"),
                "contracts_by_single_trade_cap": sizing_snapshot.get("contracts_by_single_trade_cap"),
                "selected_volume": selected_volume,
                "selected_volume_ungated": int(sizing_snapshot.get("selected_volume_ungated") or selected_volume),
                "env_gate_enabled": int(sizing_snapshot.get("env_gate_enabled") or 0),
                "env_gate_weight": float(sizing_snapshot.get("env_gate_weight") or 1.0),
                "env_candidate_count": int(sizing_snapshot.get("env_candidate_count") or 0),
                "env_native_selected_rate": float(sizing_snapshot.get("env_native_selected_rate") or 0.0),
                "env_native_selected_count": int(sizing_snapshot.get("env_native_selected_count") or 0),
                "env_avg_close_position_60d": float(sizing_snapshot.get("env_avg_close_position_60d") or 0.0),
                "env_avg_range_pct_zscore_120": float(sizing_snapshot.get("env_avg_range_pct_zscore_120") or 0.0),
                "env_gate_close_component": float(sizing_snapshot.get("env_gate_close_component") or 1.0),
                "env_gate_range_component": float(sizing_snapshot.get("env_gate_range_component") or 1.0),
                "env_gate_selected_component": float(sizing_snapshot.get("env_gate_selected_component") or 1.0),
                "env_gate_entry_context": str(sizing_snapshot.get("env_gate_entry_context") or ""),
                "portfolio_drawdown_gate_enabled": int(
                    sizing_snapshot.get("portfolio_drawdown_gate_enabled") or 0
                ),
                "portfolio_drawdown_gate_weight": float(
                    sizing_snapshot.get("portfolio_drawdown_gate_weight") or 1.0
                ),
                "portfolio_drawdown_pct": float(sizing_snapshot.get("portfolio_drawdown_pct") or 0.0),
                "portfolio_equity_high_water": float(
                    sizing_snapshot.get("portfolio_equity_high_water") or self.portfolio_equity_high_water
                ),
                "same_direction_correlation_gate_enabled": int(
                    sizing_snapshot.get("same_direction_correlation_gate_enabled") or 0
                ),
                "same_direction_correlation_gate_weight": float(
                    sizing_snapshot.get("same_direction_correlation_gate_weight") or 1.0
                ),
                "same_direction_correlation_active_count": int(
                    sizing_snapshot.get("same_direction_correlation_active_count") or 0
                ),
                "same_direction_correlation_corr_count": int(
                    sizing_snapshot.get("same_direction_correlation_corr_count") or 0
                ),
                "same_direction_correlation_max_corr": float(
                    sizing_snapshot.get("same_direction_correlation_max_corr") or 0.0
                ),
                "same_direction_correlation_avg_corr": float(
                    sizing_snapshot.get("same_direction_correlation_avg_corr") or 0.0
                ),
                "selection_pairwise_enabled": int(sizing_snapshot.get("selection_pairwise_enabled") or 0),
                "selection_pairwise_model_tag": str(sizing_snapshot.get("selection_pairwise_model_tag") or ""),
                "selection_pairwise_score": float(sizing_snapshot.get("selection_pairwise_score") or 0.0),
                "selection_pairwise_rank": int(sizing_snapshot.get("selection_pairwise_rank") or 0),
                "selection_pairwise_veto_flag": int(sizing_snapshot.get("selection_pairwise_veto_flag") or 0),
                "selection_pairwise_veto_penalty": float(sizing_snapshot.get("selection_pairwise_veto_penalty") or 0.0),
                "selection_pairwise_feature_ret_20d_zscore_120": float(
                    sizing_snapshot.get("selection_pairwise_feature_ret_20d_zscore_120") or 0.0
                ),
                "selection_pairwise_feature_close_position_60d_cs_zscore_1d": float(
                    sizing_snapshot.get("selection_pairwise_feature_close_position_60d_cs_zscore_1d") or 0.0
                ),
                "selection_pairwise_feature_range_pct_zscore_120": float(
                    sizing_snapshot.get("selection_pairwise_feature_range_pct_zscore_120") or 0.0
                ),
                "selection_pairwise_runtime_veto_match_local": int(
                    sizing_snapshot.get("selection_pairwise_runtime_veto_match_local") or 0
                ),
                "selection_pairwise_volume_tilt_applied": int(
                    sizing_snapshot.get("selection_pairwise_volume_tilt_applied") or 0
                ),
                "selection_pairwise_volume_tilt_direction_strength": float(
                    sizing_snapshot.get("selection_pairwise_volume_tilt_direction_strength") or 0.0
                ),
                "selection_pairwise_volume_tilt_multiplier": float(
                    sizing_snapshot.get("selection_pairwise_volume_tilt_multiplier") or 1.0
                ),
                "selection_pairwise_volume_tilt_volume_before": int(
                    sizing_snapshot.get("selection_pairwise_volume_tilt_volume_before") or selected_volume
                ),
                "selection_pairwise_volume_tilt_group_size": int(
                    sizing_snapshot.get("selection_pairwise_volume_tilt_group_size") or 0
                ),
                "selection_pairwise_volume_tilt_score_gap": float(
                    sizing_snapshot.get("selection_pairwise_volume_tilt_score_gap") or 0.0
                ),
                "selection_pairwise_volume_tilt_top_gap": float(
                    sizing_snapshot.get("selection_pairwise_volume_tilt_top_gap") or 0.0
                ),
                "selection_pairwise_volume_tilt_avg_active_positions_before": float(
                    sizing_snapshot.get("selection_pairwise_volume_tilt_avg_active_positions_before") or 0.0
                ),
                "selection_pairwise_volume_tilt_active_positions_scale": float(
                    sizing_snapshot.get("selection_pairwise_volume_tilt_active_positions_scale") or 1.0
                ),
                "selection_pairwise_volume_tilt_state_max_range_zscore": float(
                    sizing_snapshot.get("selection_pairwise_volume_tilt_state_max_range_zscore") or 0.0
                ),
                "selection_pairwise_volume_tilt_range_scale": float(
                    sizing_snapshot.get("selection_pairwise_volume_tilt_range_scale") or 1.0
                ),
                "ai_product_pool_enabled": int(sizing_snapshot.get("ai_product_pool_enabled") or 0),
                "ai_product_pool_strategy": str(sizing_snapshot.get("ai_product_pool_strategy") or ""),
                "ai_product_pool_allowed": int(sizing_snapshot.get("ai_product_pool_allowed") or 0),
                "ai_product_pool_signal_date": str(sizing_snapshot.get("ai_product_pool_signal_date") or ""),
                "ai_product_pool_score": float(sizing_snapshot.get("ai_product_pool_score") or 0.0),
                "ai_product_pool_rank": int(sizing_snapshot.get("ai_product_pool_rank") or 0),
                "ai_product_pool_top_n": int(sizing_snapshot.get("ai_product_pool_top_n") or 0),
                "active_positions_before": int(active_positions_before),
                "max_concurrent_positions": int(self.max_concurrent_positions),
                "effective_max_concurrent_positions": effective_max_concurrent_positions,
                "remaining_position_slots": int(remaining_slots),
                "bullish_alignment": int(bool(signal_data.get("bullish_alignment"))),
                "bearish_alignment": int(bool(signal_data.get("bearish_alignment"))),
                "breakout": int(bool(signal_data.get("breakout"))),
                "rsi_value": float(signal_data.get("rsi_value", float("nan"))),
                "ma_mid_value": signal_data.get("ma_mid_value"),
                "ma_long_value": signal_data.get("ma_long_value"),
                "ma_mid_prev_value": signal_data.get("ma_mid_prev_value"),
                "ma_long_prev_value": signal_data.get("ma_long_prev_value"),
                "is_opened": int(candidate_status == "opened"),
                "loss_streak": int(self.loss_streak),
                "profit_recovery_streak": int(self.profit_recovery_streak),
            }
        )

    @staticmethod
    def _stop_triggered(direction: str, bar: BarData, stop_price: float) -> bool:
        if stop_price <= 0:
            return False
        if direction == "long":
            return float(bar.close_price) <= stop_price
        return float(bar.close_price) >= stop_price

    @staticmethod
    def _stop_execution_price(direction: str, bar: BarData, stop_price: float) -> float:
        return float(bar.close_price)

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
        reserved_margin_before: float = float(sizing_snapshot.get("reserved_margin_before", self._reserved_margin_in_use()) or 0.0)

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
                "total_margin_in_use_before": reserved_margin_before,
                "allowed_capital": float(sizing_snapshot.get("allowed_capital") or 0.0),
                "single_trade_capital_limit": float(sizing_snapshot.get("single_trade_capital_limit") or 0.0),
                "free_capital": float(sizing_snapshot.get("free_capital") or 0.0),
                "limited_balance": float(sizing_snapshot.get("limited_balance") or 0.0),
                "effective_single_trade_capital_usage_ratio": float(self.max_single_trade_capital_usage_ratio),
                "effective_streak_risk_multipliers": self.streak_risk_multipliers,
                "risk_ratio": sizing_snapshot.get("risk_ratio"),
                "risk_multiplier": float(sizing_snapshot.get("risk_multiplier") or self._current_streak_multiplier()),
                "streak_entry_structure_risk_recovery_enabled": int(
                    sizing_snapshot.get("streak_entry_structure_risk_recovery_enabled") or 0
                ),
                "streak_entry_structure_risk_recovery_applied": int(
                    sizing_snapshot.get("streak_entry_structure_risk_recovery_applied") or 0
                ),
                "streak_entry_structure_risk_recovery_reason": str(
                    sizing_snapshot.get("streak_entry_structure_risk_recovery_reason") or ""
                ),
                "streak_entry_structure_risk_recovery_base_multiplier": float(
                    sizing_snapshot.get("streak_entry_structure_risk_recovery_base_multiplier")
                    or self._current_streak_multiplier()
                ),
                "streak_entry_structure_risk_recovery_effective_multiplier": float(
                    sizing_snapshot.get("streak_entry_structure_risk_recovery_effective_multiplier")
                    or sizing_snapshot.get("risk_multiplier")
                    or self._current_streak_multiplier()
                ),
                "streak_entry_structure_risk_recovery_rsi_confirmation_enabled": int(
                    sizing_snapshot.get("streak_entry_structure_risk_recovery_rsi_confirmation_enabled") or 0
                ),
                "streak_entry_structure_risk_recovery_rsi_value": float(
                    sizing_snapshot.get("streak_entry_structure_risk_recovery_rsi_value")
                    if sizing_snapshot.get("streak_entry_structure_risk_recovery_rsi_value") is not None
                    else float("nan")
                ),
                "streak_entry_structure_risk_recovery_long_min_rsi": float(
                    sizing_snapshot.get("streak_entry_structure_risk_recovery_long_min_rsi")
                    or self.streak_entry_structure_recovery_long_min_rsi
                ),
                "streak_entry_structure_risk_recovery_short_max_rsi": float(
                    sizing_snapshot.get("streak_entry_structure_risk_recovery_short_max_rsi")
                    or self.streak_entry_structure_recovery_short_max_rsi
                ),
                "streak_entry_structure_risk_recovery_portfolio_drawdown_pct": float(
                    sizing_snapshot.get("streak_entry_structure_risk_recovery_portfolio_drawdown_pct")
                    or self.portfolio_drawdown_pct
                    or 0.0
                ),
                "streak_entry_structure_risk_recovery_max_portfolio_drawdown_pct": float(
                    sizing_snapshot.get("streak_entry_structure_risk_recovery_max_portfolio_drawdown_pct")
                    if sizing_snapshot.get("streak_entry_structure_risk_recovery_max_portfolio_drawdown_pct") is not None
                    else self.streak_entry_structure_recovery_max_portfolio_drawdown_pct
                ),
                "target_risk_amount": sizing_snapshot.get("risk_amount"),
                "planned_entry_price": entry_price,
                "filled_entry_price": None,
                "entry_price": entry_price,
                "stop_price": stop_price,
                "stop_distance": abs(entry_price - stop_price),
                "size": size,
                "risk_per_contract": risk_per_contract,
                "actual_risk_amount": actual_risk_amount,
                "margin_ratio": margin_ratio,
                "margin_per_contract": margin_per_contract,
                "actual_margin_amount": actual_margin_amount,
                "projected_total_margin_after": reserved_margin_before + actual_margin_amount,
                "volume": int(volume),
                "contracts_by_risk": sizing_snapshot.get("contracts_by_risk"),
                "contracts_by_margin": sizing_snapshot.get("contracts_by_margin"),
                "contracts_by_single_trade_cap": sizing_snapshot.get("contracts_by_single_trade_cap"),
                "selected_volume": sizing_snapshot.get("selected_volume"),
                "selected_volume_ungated": sizing_snapshot.get("selected_volume_ungated"),
                "env_gate_enabled": int(sizing_snapshot.get("env_gate_enabled") or 0),
                "env_gate_weight": float(sizing_snapshot.get("env_gate_weight") or 1.0),
                "env_candidate_count": int(sizing_snapshot.get("env_candidate_count") or 0),
                "env_native_selected_rate": float(sizing_snapshot.get("env_native_selected_rate") or 0.0),
                "env_native_selected_count": int(sizing_snapshot.get("env_native_selected_count") or 0),
                "env_avg_close_position_60d": float(sizing_snapshot.get("env_avg_close_position_60d") or 0.0),
                "env_avg_range_pct_zscore_120": float(sizing_snapshot.get("env_avg_range_pct_zscore_120") or 0.0),
                "env_gate_close_component": float(sizing_snapshot.get("env_gate_close_component") or 1.0),
                "env_gate_range_component": float(sizing_snapshot.get("env_gate_range_component") or 1.0),
                "env_gate_selected_component": float(sizing_snapshot.get("env_gate_selected_component") or 1.0),
                "env_gate_entry_context": str(sizing_snapshot.get("env_gate_entry_context") or ""),
                "portfolio_drawdown_gate_enabled": int(
                    sizing_snapshot.get("portfolio_drawdown_gate_enabled") or 0
                ),
                "portfolio_drawdown_gate_weight": float(
                    sizing_snapshot.get("portfolio_drawdown_gate_weight") or 1.0
                ),
                "portfolio_drawdown_pct": float(sizing_snapshot.get("portfolio_drawdown_pct") or 0.0),
                "portfolio_equity_high_water": float(
                    sizing_snapshot.get("portfolio_equity_high_water") or self.portfolio_equity_high_water
                ),
                "same_direction_correlation_gate_enabled": int(
                    sizing_snapshot.get("same_direction_correlation_gate_enabled") or 0
                ),
                "same_direction_correlation_gate_weight": float(
                    sizing_snapshot.get("same_direction_correlation_gate_weight") or 1.0
                ),
                "same_direction_correlation_active_count": int(
                    sizing_snapshot.get("same_direction_correlation_active_count") or 0
                ),
                "same_direction_correlation_corr_count": int(
                    sizing_snapshot.get("same_direction_correlation_corr_count") or 0
                ),
                "same_direction_correlation_max_corr": float(
                    sizing_snapshot.get("same_direction_correlation_max_corr") or 0.0
                ),
                "same_direction_correlation_avg_corr": float(
                    sizing_snapshot.get("same_direction_correlation_avg_corr") or 0.0
                ),
                "loss_streak": int(self.loss_streak),
                "profit_recovery_streak": int(self.profit_recovery_streak),
            }
        )
        pending_key = (contract_vt_symbol, direction)
        pending_rows = self.pending_entry_diagnostics.setdefault(pending_key, [])
        pending_rows.append(len(self.entry_risk_diagnostics) - 1)

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
                    entry_price_synced=True,
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
            if self._stop_triggered("long", bar, final_stop):
                exit_price = self._stop_execution_price("long", bar, final_stop)
                self._close_all_layers_and_set_flat_target(
                    state,
                    exit_price,
                    execution_price_override=exit_price,
                    exit_reason="long_prev2day_stop",
                )
                return "long_prev2day_stop"
        else:
            raw_stop = float(prev2_window["high"].max())
            final_stop = raw_stop if state.prev2day_stop_price is None else min(state.prev2day_stop_price, raw_stop)
            state.prev2day_stop_price = final_stop
            if self._stop_triggered("short", bar, final_stop):
                exit_price = self._stop_execution_price("short", bar, final_stop)
                self._close_all_layers_and_set_flat_target(
                    state,
                    exit_price,
                    execution_price_override=exit_price,
                    exit_reason="short_prev2day_stop",
                )
                return "short_prev2day_stop"

        return ""

    def _process_layer_stops(self, state: ProductState, bar: BarData) -> str:
        direction: str = state.direction
        triggered_indexes: list[int] = []
        base_triggered: bool = False
        base_stop_price: float = 0.0
        base_profit_giveback_context: bool = False
        triggered_stop_prices: list[float] = []
        for index, layer in enumerate(state.layers):
            if self._stop_triggered(direction, bar, layer.stop_price):
                if layer.kind == "base":
                    base_triggered = True
                    base_stop_price = layer.stop_price
                    base_profit_giveback_context = bool(layer.profit_giveback_stop_active)
                    break
                triggered_indexes.append(index)
                triggered_stop_prices.append(layer.stop_price)

        if base_triggered:
            exit_price = self._stop_execution_price(direction, bar, base_stop_price)
            self._close_all_layers_and_set_flat_target(
                state,
                exit_price,
                execution_price_override=exit_price,
                exit_reason=f"{direction}_base_stop",
                profit_giveback_context=base_profit_giveback_context,
            )
            return f"{direction}_base_stop"

        if not triggered_indexes:
            return ""

        stop_reference = max(triggered_stop_prices) if direction == "long" else min(triggered_stop_prices)
        exit_price = self._stop_execution_price(direction, bar, stop_reference)
        closed_volume = sum(state.layers[index].volume for index in triggered_indexes)
        profit_giveback_context = all(
            bool(state.layers[index].profit_giveback_stop_active) for index in triggered_indexes
        )
        exit_reason = f"{direction}_layer_stop_partial" if len(state.layers) > len(triggered_indexes) else f"{direction}_layer_stop_all"
        self._close_layers(
            state,
            triggered_indexes,
            exit_price,
            exit_reason=exit_reason,
            profit_giveback_context=profit_giveback_context,
        )
        self._record_trade_event(
            bar=bar,
            contract_vt_symbol=state.contract_vt_symbol,
            product_vt_symbol=state.product_vt_symbol,
            position_direction=direction,
            offset="Close",
            reason=exit_reason,
            volume=closed_volume,
            price=exit_price,
        )
        if state.layers:
            self._apply_state_target(state, execution_price_override=exit_price)
        return exit_reason

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

        if self.enable_profit_giveback_stop:
            giveback_price = self._profit_giveback_stop_price(layer)
            if giveback_price is not None:
                previous_stop = layer.stop_price
                if layer.direction == "long":
                    layer.stop_price = max(layer.stop_price, giveback_price)
                    if layer.stop_price > previous_stop:
                        layer.profit_giveback_stop_active = True
                        self.profit_giveback_stop_update_count += 1
                else:
                    layer.stop_price = min(layer.stop_price, giveback_price)
                    if layer.stop_price < previous_stop:
                        layer.profit_giveback_stop_active = True
                        self.profit_giveback_stop_update_count += 1

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

    def _profit_giveback_stop_price(self, layer: PositionLayer) -> float | None:
        trigger_pct = max(float(self.profit_giveback_trigger_pct), 0.0)
        if layer.max_profit_pct < trigger_pct:
            return None

        retain_ratio = min(max(float(self.profit_giveback_retain_ratio), 0.0), 1.0)
        min_lock_pct = max(float(self.profit_giveback_min_lock_pct), 0.0)
        lock_pct = max(min_lock_pct, layer.max_profit_pct * retain_ratio)
        if lock_pct <= 0:
            return None

        if layer.direction == "long":
            return layer.entry_price * (1 + lock_pct)
        return layer.entry_price * (1 - lock_pct)

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
            self._close_all_layers_and_set_flat_target(
                state,
                float(bar.close_price),
                exit_reason=f"{exit_reason}_all",
            )
            state.rsi_partial_exit_done = True
            return f"{exit_reason}_all"

        self._record_trade_event(
            bar=bar,
            contract_vt_symbol=state.contract_vt_symbol,
            product_vt_symbol=state.product_vt_symbol,
            position_direction=state.direction,
            offset="Close",
            reason=f"{exit_reason}_half",
            volume=reduce_volume,
            price=float(bar.close_price),
        )
        self._reduce_position_to_target(state, target_volume, float(bar.close_price))
        state.rsi_partial_exit_done = True
        return f"{exit_reason}_half"

    def _can_open_short_signal(self, signal: str) -> bool:
        """Only allow fresh short entries from the MA5-down-cross bearish case."""
        return signal == "short_case1a"

    def _close_layers(
        self,
        state: ProductState,
        indexes: list[int],
        exit_price: float,
        *,
        exit_reason: str | None = None,
        profit_giveback_context: bool = False,
    ) -> None:
        if not state.contract_vt_symbol:
            return
        size: int = self.get_size(state.contract_vt_symbol)
        realized: float = 0.0
        for index in sorted(indexes, reverse=True):
            layer = state.layers[index]
            self._queue_pending_close_lot(state.contract_vt_symbol, layer, exit_price, layer.volume)
            realized += self._layer_realized_pnl(layer, exit_price, size)
            del state.layers[index]
        self.realized_pnl += realized
        self._update_streak_risk_state(
            realized,
            state.product_vt_symbol,
            exit_reason=exit_reason,
            profit_giveback_context=profit_giveback_context,
        )
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
            self._queue_pending_close_lot(state.contract_vt_symbol, last_layer, exit_price, closed_volume)
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
                    entry_price_synced=last_layer.entry_price_synced,
                    profit_giveback_stop_active=last_layer.profit_giveback_stop_active,
                ),
                exit_price,
                size,
            )
            last_layer.volume -= closed_volume
            reduce_volume -= closed_volume
            if last_layer.volume <= 0:
                state.layers.pop()

        self.realized_pnl += realized
        self._update_streak_risk_state(realized, state.product_vt_symbol)
        if not state.layers:
            state.reset()

    def _close_all_layers(
        self,
        state: ProductState,
        exit_price: float,
        *,
        exit_reason: str | None = None,
        profit_giveback_context: bool = False,
    ) -> None:
        if not state.layers:
            state.reset()
            return
        self._close_layers(
            state,
            list(range(len(state.layers))),
            exit_price,
            exit_reason=exit_reason,
            profit_giveback_context=profit_giveback_context,
        )
        state.reset()

    def _close_all_layers_and_set_flat_target(
        self,
        state: ProductState,
        exit_price: float,
        execution_price_override: float | None = None,
        exit_reason: str | None = None,
        profit_giveback_context: bool = False,
    ) -> None:
        contract_vt_symbol: str = state.contract_vt_symbol
        if not contract_vt_symbol:
            state.reset()
            return
        if exit_reason:
            engine_bars: dict[str, BarData] = getattr(self.strategy_engine, "bars", {})
            event_bar: BarData | None = engine_bars.get(contract_vt_symbol)
            self._record_trade_event(
                bar=event_bar,
                contract_vt_symbol=contract_vt_symbol,
                product_vt_symbol=state.product_vt_symbol,
                position_direction=state.direction,
                offset="Close",
                reason=exit_reason,
                volume=state.active_volume(),
                price=exit_price,
            )
        self._close_all_layers(
            state,
            exit_price,
            exit_reason=exit_reason,
            profit_giveback_context=profit_giveback_context,
        )
        if execution_price_override is not None and execution_price_override > 0:
            self.execution_price_overrides[contract_vt_symbol] = execution_price_override
        self.set_target(contract_vt_symbol, 0)

    def _layer_realized_pnl(self, layer: PositionLayer, exit_price: float, size: int) -> float:
        return (exit_price - layer.entry_price) * size * layer.volume if layer.direction == "long" else (layer.entry_price - exit_price) * size * layer.volume

    def _update_streak_risk_state(
        self,
        realized_pnl: float,
        product_vt_symbol: str | None = None,
        *,
        exit_reason: str | None = None,
        profit_giveback_context: bool = False,
    ) -> None:
        if self._skip_profit_giveback_streak_update(realized_pnl, exit_reason, profit_giveback_context):
            self.profit_giveback_streak_neutral_count += 1
            self.risk_multiplier = self._current_streak_multiplier()
            return
        if product_vt_symbol and product_vt_symbol in self.streak_risk_state_excluded_product_set:
            exclusion_mode = str(self.streak_risk_state_exclusion_mode or "all").strip().lower()
            if exclusion_mode in {"all", "both", "true", "1"}:
                self.risk_multiplier = self._current_streak_multiplier()
                return
            if realized_pnl > 0 and exclusion_mode in {"profit", "profit_only", "positive", "positive_only"}:
                equity_confirm_threshold = self._safe_float_value(
                    self.streak_profit_recovery_equity_confirm_drawdown_pct,
                    -1.0,
                )
                equity_confirmed = (
                    equity_confirm_threshold >= 0.0
                    and self.portfolio_drawdown_pct <= equity_confirm_threshold
                )
                if not equity_confirmed:
                    self.risk_multiplier = self._current_streak_multiplier()
                    return
            if realized_pnl < 0 and exclusion_mode in {"loss", "loss_only", "negative", "negative_only"}:
                self.risk_multiplier = self._current_streak_multiplier()
                return
        if realized_pnl < 0:
            self.loss_streak += 1
            self.profit_recovery_streak = 0
        elif realized_pnl > 0:
            recovery_mode = str(self.streak_profit_recovery_mode or "reset").strip().lower()
            if recovery_mode in {"decrement", "step", "gradual"}:
                self.loss_streak = max(0, self.loss_streak - 1)
                self.profit_recovery_streak = 0
            elif recovery_mode in {"confirm", "confirmed", "confirmation"}:
                required_wins = max(1, int(self._safe_float_value(self.streak_profit_recovery_confirm_wins, 1.0)))
                if self.loss_streak > 0:
                    self.profit_recovery_streak += 1
                    if self.profit_recovery_streak >= required_wins:
                        self.loss_streak = 0
                        self.profit_recovery_streak = 0
                else:
                    self.profit_recovery_streak = 0
            else:
                self.loss_streak = 0
                self.profit_recovery_streak = 0
        self.risk_multiplier = self._current_streak_multiplier()

    def _skip_profit_giveback_streak_update(
        self,
        realized_pnl: float,
        exit_reason: str | None,
        profit_giveback_context: bool,
    ) -> bool:
        if not self.enable_profit_giveback_stop or not profit_giveback_context:
            return False
        mode = str(self.profit_giveback_streak_update_mode or "normal").strip().lower()
        if mode in {"normal", "default", ""}:
            return False
        if mode in {"neutral", "all_neutral", "ignore", "skip"}:
            return True
        if mode in {"loss_neutral", "loss_only_neutral", "negative_neutral"}:
            return realized_pnl < 0
        return False

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
        allowed_capital = self._allowed_capital()
        return (self._reserved_margin_in_use() + projected_margin) <= allowed_capital

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

    @staticmethod
    def _parse_symbol_set(raw: str) -> set[str]:
        symbols: set[str] = set()
        normalized = str(raw or "").replace(";", ",").replace("|", ",")
        for part in normalized.split(","):
            symbol = part.strip()
            if symbol:
                symbols.add(symbol)
        return symbols

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
            return self._signal_result(
                "", False, False, float("nan"), float("nan"), float("nan"), float("nan"), "regular", False
            )

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
            float(ma_mid.iloc[-1]),
            float(ma_long.iloc[-1]),
            float(ma_long.iloc[-2]),
            float(ma_mid.iloc[-2]),
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

        if latest_two_sum > previous_two_sum * 1.2:
            return "open_interest_surge"
        if latest_two_sum < previous_two_sum * 0.9:
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
        ma_mid_value: float,
        ma_long_value: float,
        ma_long_prev_value: float,
        ma_mid_prev_value: float,
        risk_mode: str,
        breakout: bool,
        rsi_value: float = float("nan"),
    ) -> dict[str, Any]:
        return {
            "signal": signal,
            "bullish_alignment": bullish_alignment,
            "bearish_alignment": bearish_alignment,
            "ma_mid_value": ma_mid_value,
            "ma_long_value": ma_long_value,
            "ma_long_prev_value": ma_long_prev_value,
            "ma_mid_prev_value": ma_mid_prev_value,
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
