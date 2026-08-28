from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
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
from qmt_roll_ai_path_damage_runtime import (
    DEFAULT_MODEL_PATH as DEFAULT_PATH_DAMAGE_MODEL_PATH,
    DEFAULT_SUMMARY_PATH as DEFAULT_PATH_DAMAGE_SUMMARY_PATH,
    PREDICTION_COLUMN as PATH_DAMAGE_PREDICTION_COLUMN,
    PathDamageRuntimeModel,
    build_path_damage_runtime_feature_row,
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
    last_post_quality_add_date: str = ""
    rollover_opened_today: str = ""
    rollover_pending_target_contract: str = ""
    rollover_pending_signal_date: str = ""
    rollover_pending_last_counted_date: str = ""
    rollover_pending_elapsed_trading_days: int = 0
    bars_since_entry: int = 0
    prev2day_stop_price: float | None = None
    post_quality_prev2day_relax_done: bool = False
    rsi_partial_exit_done: bool = False
    portfolio_drawdown_gate_reference_contract: str = ""
    portfolio_drawdown_gate_reference_volume: int = 0
    portfolio_volatility_budget_reference_contract: str = ""
    portfolio_volatility_budget_reference_volume: int = 0
    portfolio_overheat_cooldown_reference_contract: str = ""
    portfolio_overheat_cooldown_reference_volume: int = 0

    def reset(self) -> None:
        self.contract_vt_symbol = ""
        self.direction = ""
        self.risk_mode = "regular"
        self.layers.clear()
        self.last_signal = ""
        self.entry_date = ""
        self.last_add_date = ""
        self.last_donchian_add_date = ""
        self.last_post_quality_add_date = ""
        self.rollover_opened_today = ""
        self.rollover_pending_target_contract = ""
        self.rollover_pending_signal_date = ""
        self.rollover_pending_last_counted_date = ""
        self.rollover_pending_elapsed_trading_days = 0
        self.bars_since_entry = 0
        self.prev2day_stop_price = None
        self.post_quality_prev2day_relax_done = False
        self.rsi_partial_exit_done = False
        self.portfolio_drawdown_gate_reference_contract = ""
        self.portfolio_drawdown_gate_reference_volume = 0
        self.portfolio_volatility_budget_reference_contract = ""
        self.portfolio_volatility_budget_reference_volume = 0
        self.portfolio_overheat_cooldown_reference_contract = ""
        self.portfolio_overheat_cooldown_reference_volume = 0

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
    rollover_delay_active: bool = False


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
    trade_start_date: str = ""
    exit_on_alignment_break: bool = True
    enable_ma_trend_stop: bool = True
    rollover_reopen_enabled: bool = True
    enable_rollover_shape_same_volume_reopen: bool = False
    rollover_shape_volume_policy: str = "shrink_to_allowed"
    rollover_shape_history_mode: str = "target_contract_only"
    rollover_delay_trading_days: int = 0
    enable_directional_30d_risk_boost: bool = False
    directional_30d_risk_boost_lookback: int = 30
    directional_30d_risk_boost_multiplier: float = 1.2
    directional_30d_risk_nonconfirmation_multiplier: float = 1.0
    directional_30d_risk_adjust_long_only: bool = False
    directional_30d_risk_boost_require_volume_expansion: bool = False
    directional_30d_volume_recent_days: int = 10
    directional_30d_volume_prior_days: int = 10
    directional_30d_volume_ratio_threshold: float = 1.0
    enable_directional_30d_low_volume_risk_discount: bool = False
    directional_30d_low_volume_ratio_threshold: float = 0.5
    directional_30d_low_volume_risk_multiplier: float = 0.5
    enable_long_signal_atr_shock_filter: bool = False
    enable_short_signal_atr_shock_filter: bool = False
    long_signal_atr_shock_period: int = 5
    long_signal_atr_shock_multiplier: float = 2.0
    long_signal_atr_shock_entry_contexts: str = "flat_entry,reverse_entry,rollover_reopen"
    enable_long_signal_range_atr_filter: bool = False
    enable_short_signal_range_atr_filter: bool = False
    long_signal_range_lookback: int = 10
    long_signal_range_atr_period: int = 5
    long_signal_range_atr_multiplier: float = 3.0
    long_signal_range_atr_entry_contexts: str = "flat_entry,reverse_entry,rollover_reopen"
    long_signal_range_require_recent_stall: bool = False
    long_signal_range_recent_gain_lookback: int = 3
    long_signal_range_recent_gain_atr_multiplier: float = 0.5
    long_signal_range_enable_ordered_drawdown_filter: bool = False
    long_signal_range_ordered_drawdown_atr_multiplier: float = 3.0
    enable_rollover_reopen_drawdown_guard: bool = False
    rollover_reopen_max_portfolio_drawdown_pct: float = 0.10
    reverse_on_opposite_signal: bool = True
    enable_prev2day_stop: bool = False
    enable_profit_lock_trend_relaxed_prev2day_stop: bool = False
    profit_lock_trend_relax_trigger_pct: float = 0.05
    profit_lock_trend_relax_ma_fast: int = 20
    profit_lock_trend_relax_ma_slow: int = 40
    profit_lock_trend_relax_slope_days: int = 3
    enable_post_entry_quality_prev2day_relax: bool = False
    post_entry_quality_prev2day_relax_feature: str = "post1_smooth_directional_combo"
    enable_rsi_partial_exit: bool = False
    rsi_partial_exit_threshold: float = 95.0
    rsi_partial_exit_ratio: float = 0.5

    fixed_size: int = 1
    min_position_size: int = 1
    max_position_size: int = 50000
    max_concurrent_positions: int = 10
    capital_base: float = 0.0
    sizing_equity_cap: float = 1_000_000.0
    enable_dynamic_sizing_equity_soft_cap: bool = False
    dynamic_sizing_equity_soft_cap_base: float = 1_000_000.0
    dynamic_sizing_equity_soft_cap_max: float = 1_500_000.0
    dynamic_sizing_equity_soft_cap_participation: float = 0.25
    dynamic_sizing_equity_soft_cap_margin_start_ratio: float = 0.60
    dynamic_sizing_equity_soft_cap_margin_full_ratio: float = 0.80
    dynamic_sizing_equity_soft_cap_drawdown_start_ratio: float = 0.05
    dynamic_sizing_equity_soft_cap_drawdown_full_ratio: float = 0.20
    enable_layered_profit_lock_sizing: bool = False
    layered_profit_lock_base_equity: float = 1_000_000.0
    layered_profit_lock_start_equity: float = 2_000_000.0
    layered_profit_lock_ratio: float = 0.50
    layered_profit_lock_tiers: str = ""
    max_capital_usage_ratio: float = 0.9
    max_single_trade_capital_usage_ratio: float = 0.7
    enable_incremental_margin_budget_gate: bool = False
    incremental_margin_budget_gate_usage_ratio: float = -1.0
    incremental_margin_budget_gate_min_openable_candidates: int = 1
    incremental_margin_budget_gate_protected_selection_rank: int = 0
    incremental_margin_budget_gate_reduce_volume: bool = False
    incremental_margin_budget_gate_entry_contexts: str = "flat_entry"
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
    enable_risk_cluster_margin_cap: bool = False
    risk_cluster_margin_cap_ratio: float = 0.35
    risk_cluster_target_clusters: str = ""
    risk_cluster_map: str = ""
    enable_risk_cluster_heat_gate: bool = False
    risk_cluster_heat_gate_target_clusters: str = ""
    risk_cluster_heat_gate_entry_contexts: str = "flat_entry,reverse_entry,rollover_reopen,regular_add,donchian_add,post_quality_add"
    risk_cluster_heat_gate_drawdown_start_pct: float = 0.10
    risk_cluster_heat_gate_drawdown_full_pct: float = 0.25
    risk_cluster_heat_gate_margin_start_ratio: float = 0.15
    risk_cluster_heat_gate_margin_full_ratio: float = 0.35
    risk_cluster_heat_gate_unrealized_loss_start_ratio: float = 0.02
    risk_cluster_heat_gate_unrealized_loss_full_ratio: float = 0.08
    risk_cluster_heat_gate_weight_floor: float = 0.35
    enable_risk_cluster_heat_deleverage: bool = False
    risk_cluster_heat_deleverage_target_clusters: str = ""
    risk_cluster_heat_deleverage_layer_kinds: str = "add,donchian,post_quality"
    risk_cluster_heat_deleverage_min_pressure: float = 0.50
    risk_cluster_heat_deleverage_use_daily_snapshot: bool = False
    risk_cluster_heat_deleverage_snapshot_requires_same_direction_multi: bool = False
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
    streak_entry_structure_recovery_require_directional_edge60: bool = False
    streak_entry_structure_recovery_directional_edge_period: int = 60
    streak_entry_structure_recovery_long_close_position_min: float = 0.80
    streak_entry_structure_recovery_short_close_position_max: float = 0.20
    streak_entry_structure_recovery_max_portfolio_drawdown_pct: float = -1.0
    enable_recovery_sleeve: bool = False
    recovery_sleeve_base_multiplier_max: float = 0.1000001
    recovery_sleeve_broker_margin_multiplier: float = 1.65
    recovery_sleeve_max_single_contract_broker_margin_to_equity: float = 0.20
    recovery_sleeve_cooldown_days: int = 20
    recovery_sleeve_volume: int = 1
    recovery_sleeve_normal_risk_bypass_require_directional_edge60: bool = False
    recovery_sleeve_normal_risk_bypass_max_portfolio_drawdown_pct: float = -1.0
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
    portfolio_drawdown_gate_entry_contexts: str = "flat_entry"
    enable_portfolio_drawdown_deleverage: bool = False
    enable_portfolio_volatility_budget: bool = False
    portfolio_volatility_budget_lookback: int = 60
    portfolio_volatility_budget_target_annual_vol: float = 0.60
    portfolio_volatility_budget_min_scale: float = 0.0
    portfolio_volatility_budget_entry_contexts: str = "flat_entry,reverse_entry,rollover_reopen,regular_add,donchian_add,post_quality_add"
    enable_portfolio_volatility_budget_deleverage: bool = False
    enable_portfolio_margin_deleverage: bool = False
    portfolio_margin_deleverage_start_ratio: float = 0.90
    portfolio_margin_deleverage_full_ratio: float = 1.10
    portfolio_margin_deleverage_min_pressure: float = 0.50
    portfolio_margin_deleverage_layer_kinds: str = "add,donchian,post_quality"
    portfolio_margin_deleverage_broker_multiplier: float = 1.10
    enable_forced_margin_deleverage: bool = False
    forced_margin_deleverage_trigger_ratio: float = 0.95
    forced_margin_deleverage_target_ratio: float = 0.80
    forced_margin_deleverage_broker_multiplier: float = 1.10
    forced_margin_deleverage_priority: str = "largest_margin"
    forced_margin_deleverage_max_reductions_per_day: int = 100
    enable_portfolio_overheat_cooldown: bool = False
    portfolio_overheat_cooldown_near_high_drawdown_pct: float = 0.05
    portfolio_overheat_cooldown_hot20_threshold: float = 0.50
    portfolio_overheat_cooldown_hot60_threshold: float = -1.0
    portfolio_overheat_cooldown_brake_scale: float = 0.80
    portfolio_overheat_cooldown_recovery_drawdown_pct: float = 0.15
    portfolio_overheat_cooldown_recovery_ret20_threshold: float = 0.0
    portfolio_overheat_cooldown_recovery_scale: float = 1.10
    portfolio_overheat_cooldown_entry_contexts: str = "flat_entry,reverse_entry,rollover_reopen,regular_add,donchian_add,post_quality_add"
    enable_portfolio_overheat_cooldown_deleverage: bool = False
    enable_product_direction_failure_cooldown: bool = False
    product_direction_failure_cooldown_lookback_days: int = 252
    product_direction_failure_cooldown_min_consecutive_failures: int = 3
    product_direction_failure_cooldown_days: int = 90
    product_direction_failure_cooldown_entry_contexts: str = "flat_entry"
    enable_failure_memory_micro_sizing: bool = False
    failure_memory_micro_sizing_lookback_days: int = 252
    failure_memory_micro_sizing_min_consecutive_failures: int = 2
    failure_memory_micro_sizing_multiplier: float = 1.10
    failure_memory_micro_sizing_entry_contexts: str = "flat_entry"
    enable_oi_price_confirm_risk_restore: bool = False
    oi_price_confirm_risk_restore_multiplier: float = 0.80
    oi_price_confirm_risk_restore_entry_contexts: str = "flat_entry,reverse_entry,rollover_reopen"
    oi_price_confirm_risk_restore_require_recent_sum_ratio: bool = False
    oi_price_confirm_risk_restore_recent_sum_days: int = 5
    oi_price_confirm_risk_restore_recent_sum_min_ratio: float = 2.0
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
    enable_ai_path_damage_risk_discount: bool = False
    ai_path_damage_model_path: str = str(DEFAULT_PATH_DAMAGE_MODEL_PATH)
    ai_path_damage_summary_path: str = str(DEFAULT_PATH_DAMAGE_SUMMARY_PATH)
    ai_path_damage_discount_start_date: str = "2023-01-01"
    ai_path_damage_discount_probability_start: float = 0.25
    ai_path_damage_discount_probability_full: float = 0.75
    ai_path_damage_discount_weight_floor: float = 0.80
    enable_ai_product_pool_filter: bool = False
    ai_product_pool_eligibility_path: str = ""
    ai_product_pool_strategy: str = "ai_top8_entry_filter"
    ai_product_pool_use_next_trade_date_for_entry: bool = False
    enable_supply_demand_headwind_filter: bool = False
    supply_demand_signal_path: str = ""
    supply_demand_headwind_threshold: float = -0.35
    supply_demand_headwind_weight_floor: float = 0.0
    supply_demand_headwind_max_age_days: int = 7
    array_manager_size_floor: int = 120

    stop_loss_pct: float = 0.02
    trailing_stop_enabled: bool = True
    trailing_stop_pct: float = 0.0
    profit_lock_tiers: str = ""
    enable_profit_giveback_stop: bool = False
    profit_giveback_trigger_pct: float = 0.08
    profit_giveback_retain_ratio: float = 0.70
    profit_giveback_min_lock_pct: float = 0.03
    profit_giveback_streak_update_mode: str = "normal"
    add_position_min_profit: float = 0.001
    atr_2x_mid_stop_enabled: bool = True

    enable_post_entry_quality_add: bool = False
    post_entry_quality_add_feature: str = "post1_body60_ratio_ge50"
    post_entry_quality_add_volume_multiplier: float = 0.5
    post_entry_quality_add_max_layers: int = 1
    post_entry_quality_add_use_day_extreme_stop: bool = True
    post_entry_quality_add_triggers_add_profit_lock: bool = False
    post_entry_quality_add_body_pct_min: float = 0.60
    post_entry_quality_add_body_ratio_min: float = 0.50
    post_entry_quality_add_directional_close_strength_min: float = 0.60
    post_entry_quality_add_short_wick_ratio_min: float = 0.50
    post_entry_quality_add_long_wick_ratio_max: float = 0.20
    post_entry_quality_add_adverse_wick_pct_max: float = 0.25

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
    risk_cluster_margin_in_use: float = 0.0
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
        "trade_start_date",
        "exit_on_alignment_break",
        "enable_ma_trend_stop",
        "rollover_reopen_enabled",
        "enable_rollover_shape_same_volume_reopen",
        "rollover_shape_volume_policy",
        "rollover_shape_history_mode",
        "rollover_delay_trading_days",
        "enable_directional_30d_risk_boost",
        "directional_30d_risk_boost_lookback",
        "directional_30d_risk_boost_multiplier",
        "directional_30d_risk_nonconfirmation_multiplier",
        "directional_30d_risk_adjust_long_only",
        "directional_30d_risk_boost_require_volume_expansion",
        "directional_30d_volume_recent_days",
        "directional_30d_volume_prior_days",
        "directional_30d_volume_ratio_threshold",
        "enable_directional_30d_low_volume_risk_discount",
        "directional_30d_low_volume_ratio_threshold",
        "directional_30d_low_volume_risk_multiplier",
        "enable_long_signal_atr_shock_filter",
        "enable_short_signal_atr_shock_filter",
        "long_signal_atr_shock_period",
        "long_signal_atr_shock_multiplier",
        "long_signal_atr_shock_entry_contexts",
        "enable_long_signal_range_atr_filter",
        "enable_short_signal_range_atr_filter",
        "long_signal_range_lookback",
        "long_signal_range_atr_period",
        "long_signal_range_atr_multiplier",
        "long_signal_range_atr_entry_contexts",
        "long_signal_range_require_recent_stall",
        "long_signal_range_recent_gain_lookback",
        "long_signal_range_recent_gain_atr_multiplier",
        "long_signal_range_enable_ordered_drawdown_filter",
        "long_signal_range_ordered_drawdown_atr_multiplier",
        "enable_rollover_reopen_drawdown_guard",
        "rollover_reopen_max_portfolio_drawdown_pct",
        "reverse_on_opposite_signal",
        "enable_prev2day_stop",
        "enable_profit_lock_trend_relaxed_prev2day_stop",
        "profit_lock_trend_relax_trigger_pct",
        "profit_lock_trend_relax_ma_fast",
        "profit_lock_trend_relax_ma_slow",
        "profit_lock_trend_relax_slope_days",
        "enable_post_entry_quality_prev2day_relax",
        "post_entry_quality_prev2day_relax_feature",
        "enable_rsi_partial_exit",
        "rsi_partial_exit_threshold",
        "rsi_partial_exit_ratio",
        "fixed_size",
        "min_position_size",
        "max_position_size",
        "max_concurrent_positions",
        "capital_base",
        "sizing_equity_cap",
        "enable_dynamic_sizing_equity_soft_cap",
        "dynamic_sizing_equity_soft_cap_base",
        "dynamic_sizing_equity_soft_cap_max",
        "dynamic_sizing_equity_soft_cap_participation",
        "dynamic_sizing_equity_soft_cap_margin_start_ratio",
        "dynamic_sizing_equity_soft_cap_margin_full_ratio",
        "dynamic_sizing_equity_soft_cap_drawdown_start_ratio",
        "dynamic_sizing_equity_soft_cap_drawdown_full_ratio",
        "enable_layered_profit_lock_sizing",
        "layered_profit_lock_base_equity",
        "layered_profit_lock_start_equity",
        "layered_profit_lock_ratio",
        "layered_profit_lock_tiers",
        "max_capital_usage_ratio",
        "max_single_trade_capital_usage_ratio",
        "enable_incremental_margin_budget_gate",
        "incremental_margin_budget_gate_usage_ratio",
        "incremental_margin_budget_gate_min_openable_candidates",
        "incremental_margin_budget_gate_protected_selection_rank",
        "incremental_margin_budget_gate_reduce_volume",
        "incremental_margin_budget_gate_entry_contexts",
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
        "enable_risk_cluster_margin_cap",
        "risk_cluster_margin_cap_ratio",
        "risk_cluster_target_clusters",
        "risk_cluster_map",
        "enable_risk_cluster_heat_gate",
        "risk_cluster_heat_gate_target_clusters",
        "risk_cluster_heat_gate_entry_contexts",
        "risk_cluster_heat_gate_drawdown_start_pct",
        "risk_cluster_heat_gate_drawdown_full_pct",
        "risk_cluster_heat_gate_margin_start_ratio",
        "risk_cluster_heat_gate_margin_full_ratio",
        "risk_cluster_heat_gate_unrealized_loss_start_ratio",
        "risk_cluster_heat_gate_unrealized_loss_full_ratio",
        "risk_cluster_heat_gate_weight_floor",
        "enable_risk_cluster_heat_deleverage",
        "risk_cluster_heat_deleverage_target_clusters",
        "risk_cluster_heat_deleverage_layer_kinds",
        "risk_cluster_heat_deleverage_min_pressure",
        "risk_cluster_heat_deleverage_use_daily_snapshot",
        "risk_cluster_heat_deleverage_snapshot_requires_same_direction_multi",
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
        "streak_entry_structure_recovery_require_directional_edge60",
        "streak_entry_structure_recovery_directional_edge_period",
        "streak_entry_structure_recovery_long_close_position_min",
        "streak_entry_structure_recovery_short_close_position_max",
        "streak_entry_structure_recovery_max_portfolio_drawdown_pct",
        "enable_recovery_sleeve",
        "recovery_sleeve_base_multiplier_max",
        "recovery_sleeve_broker_margin_multiplier",
        "recovery_sleeve_max_single_contract_broker_margin_to_equity",
        "recovery_sleeve_cooldown_days",
        "recovery_sleeve_volume",
        "recovery_sleeve_normal_risk_bypass_require_directional_edge60",
        "recovery_sleeve_normal_risk_bypass_max_portfolio_drawdown_pct",
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
        "portfolio_drawdown_gate_entry_contexts",
        "enable_portfolio_drawdown_deleverage",
        "enable_portfolio_volatility_budget",
        "portfolio_volatility_budget_lookback",
        "portfolio_volatility_budget_target_annual_vol",
        "portfolio_volatility_budget_min_scale",
        "portfolio_volatility_budget_entry_contexts",
        "enable_portfolio_volatility_budget_deleverage",
        "enable_portfolio_margin_deleverage",
        "portfolio_margin_deleverage_start_ratio",
        "portfolio_margin_deleverage_full_ratio",
        "portfolio_margin_deleverage_min_pressure",
        "portfolio_margin_deleverage_layer_kinds",
        "portfolio_margin_deleverage_broker_multiplier",
        "enable_forced_margin_deleverage",
        "forced_margin_deleverage_trigger_ratio",
        "forced_margin_deleverage_target_ratio",
        "forced_margin_deleverage_broker_multiplier",
        "forced_margin_deleverage_priority",
        "forced_margin_deleverage_max_reductions_per_day",
        "enable_portfolio_overheat_cooldown",
        "portfolio_overheat_cooldown_near_high_drawdown_pct",
        "portfolio_overheat_cooldown_hot20_threshold",
        "portfolio_overheat_cooldown_hot60_threshold",
        "portfolio_overheat_cooldown_brake_scale",
        "portfolio_overheat_cooldown_recovery_drawdown_pct",
        "portfolio_overheat_cooldown_recovery_ret20_threshold",
        "portfolio_overheat_cooldown_recovery_scale",
        "portfolio_overheat_cooldown_entry_contexts",
        "enable_portfolio_overheat_cooldown_deleverage",
        "enable_product_direction_failure_cooldown",
        "product_direction_failure_cooldown_lookback_days",
        "product_direction_failure_cooldown_min_consecutive_failures",
        "product_direction_failure_cooldown_days",
        "product_direction_failure_cooldown_entry_contexts",
        "enable_failure_memory_micro_sizing",
        "failure_memory_micro_sizing_lookback_days",
        "failure_memory_micro_sizing_min_consecutive_failures",
        "failure_memory_micro_sizing_multiplier",
        "failure_memory_micro_sizing_entry_contexts",
        "enable_oi_price_confirm_risk_restore",
        "oi_price_confirm_risk_restore_multiplier",
        "oi_price_confirm_risk_restore_entry_contexts",
        "oi_price_confirm_risk_restore_require_recent_sum_ratio",
        "oi_price_confirm_risk_restore_recent_sum_days",
        "oi_price_confirm_risk_restore_recent_sum_min_ratio",
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
        "enable_ai_path_damage_risk_discount",
        "ai_path_damage_model_path",
        "ai_path_damage_summary_path",
        "ai_path_damage_discount_start_date",
        "ai_path_damage_discount_probability_start",
        "ai_path_damage_discount_probability_full",
        "ai_path_damage_discount_weight_floor",
        "enable_ai_product_pool_filter",
        "ai_product_pool_eligibility_path",
        "ai_product_pool_strategy",
        "ai_product_pool_use_next_trade_date_for_entry",
        "enable_supply_demand_headwind_filter",
        "supply_demand_signal_path",
        "supply_demand_headwind_threshold",
        "supply_demand_headwind_weight_floor",
        "supply_demand_headwind_max_age_days",
        "array_manager_size_floor",
        "stop_loss_pct",
        "trailing_stop_enabled",
        "trailing_stop_pct",
        "profit_lock_tiers",
        "enable_profit_giveback_stop",
        "profit_giveback_trigger_pct",
        "profit_giveback_retain_ratio",
        "profit_giveback_min_lock_pct",
        "profit_giveback_streak_update_mode",
        "add_position_min_profit",
        "atr_2x_mid_stop_enabled",
        "enable_post_entry_quality_add",
        "post_entry_quality_add_feature",
        "post_entry_quality_add_volume_multiplier",
        "post_entry_quality_add_max_layers",
        "post_entry_quality_add_use_day_extreme_stop",
        "post_entry_quality_add_triggers_add_profit_lock",
        "post_entry_quality_add_body_pct_min",
        "post_entry_quality_add_body_ratio_min",
        "post_entry_quality_add_directional_close_strength_min",
        "post_entry_quality_add_short_wick_ratio_min",
        "post_entry_quality_add_long_wick_ratio_max",
        "post_entry_quality_add_adverse_wick_pct_max",
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
        "risk_cluster_margin_in_use",
        "risk_cluster_unrealized_loss_in_use",
        "risk_cluster_heat_gate_weight",
        "risk_cluster_heat_deleverage_count",
        "portfolio_drawdown_deleverage_count",
        "portfolio_volatility_budget_scale",
        "portfolio_volatility_budget_realized_annual_vol",
        "portfolio_volatility_budget_deleverage_count",
        "portfolio_margin_deleverage_count",
        "portfolio_margin_deleverage_pressure",
        "portfolio_margin_deleverage_ratio",
        "forced_margin_deleverage_count",
        "forced_margin_deleverage_closed_volume",
        "forced_margin_deleverage_ratio",
        "forced_margin_deleverage_max_observed_ratio",
        "portfolio_overheat_cooldown_scale",
        "portfolio_overheat_cooldown_reason",
        "portfolio_overheat_cooldown_deleverage_count",
        "product_direction_failure_cooldown_count",
        "failure_memory_micro_sizing_count",
        "current_risk_per_trade",
        "risk_multiplier",
        "loss_streak",
        "profit_recovery_streak",
        "recovery_sleeve_open_count",
        "recovery_sleeve_last_open_date",
        "post_entry_quality_add_count",
        "post_entry_quality_add_signal_count",
        "post_entry_quality_add_zero_volume_count",
        "post_entry_quality_prev2day_relax_skip_count",
        "portfolio_equity_high_water",
        "portfolio_drawdown_pct",
        "profit_giveback_streak_neutral_count",
        "profit_lock_trend_relaxed_prev2day_skip_count",
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
        self.available_trade_dates: list[pd.Timestamp] = sorted(
            pd.Timestamp(item).normalize() for item in self.daily_mapping
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
        self.recovery_sleeve_open_count: int = 0
        self.recovery_sleeve_last_open_date: str = ""
        self._recovery_sleeve_last_open_timestamp: pd.Timestamp | None = None
        self.base_capital: float = self._resolve_base_capital()
        self.entry_risk_diagnostics: list[dict[str, Any]] = []
        self.entry_candidate_snapshots: list[dict[str, Any]] = []
        self.trade_event_diagnostics: list[dict[str, Any]] = []
        self.rollover_reopen_guard_diagnostics: list[dict[str, Any]] = []
        self.rollover_shape_same_volume_diagnostics: list[dict[str, Any]] = []
        self.rollover_delay_diagnostics: list[dict[str, Any]] = []
        self.long_signal_atr_shock_diagnostics: list[dict[str, Any]] = []
        self.long_signal_range_atr_diagnostics: list[dict[str, Any]] = []
        self.trade_reason_by_trade_id: dict[str, str] = {}
        self.execution_price_overrides: dict[str, float] = {}
        self.trade_costs_total: float = 0.0
        self.profit_giveback_stop_update_count: int = 0
        self.profit_giveback_streak_neutral_count: int = 0
        self.profit_lock_trend_relaxed_prev2day_skip_count: int = 0
        self.post_entry_quality_add_count: int = 0
        self.post_entry_quality_add_signal_count: int = 0
        self.post_entry_quality_add_zero_volume_count: int = 0
        self.post_entry_quality_prev2day_relax_skip_count: int = 0
        self.pending_close_lots: dict[str, list[dict[str, Any]]] = {}
        self.pending_close_reasons: dict[str, list[dict[str, Any]]] = {}
        self.pending_entry_diagnostics: dict[tuple[str, str], list[int]] = {}
        self.settled_balance: float = self.base_capital
        self.portfolio_equity_high_water: float = self.base_capital
        self.portfolio_drawdown_pct: float = 0.0
        self.last_close_prices: dict[str, float] = {}
        self.cluster_margin_usage: dict[str, float] = {}
        self.cluster_unrealized_pnl: dict[str, float] = {}
        self.risk_cluster_unrealized_loss_in_use: float = 0.0
        self.risk_cluster_heat_gate_weight: float = 1.0
        self.risk_cluster_heat_deleverage_count: int = 0
        self.risk_cluster_heat_pressure_snapshot: dict[str, float] = {}
        self.risk_cluster_same_direction_multi_snapshot: dict[str, bool] = {}
        self.portfolio_drawdown_deleverage_count: int = 0
        self.portfolio_volatility_budget_scale: float = 1.0
        self.portfolio_volatility_budget_realized_annual_vol: float = 0.0
        self.portfolio_volatility_budget_return_history: list[float] = []
        self.portfolio_volatility_budget_scale_history: list[dict[str, Any]] = []
        self.portfolio_volatility_budget_last_equity: float = self.base_capital
        self.portfolio_volatility_budget_deleverage_count: int = 0
        self.portfolio_margin_deleverage_count: int = 0
        self.portfolio_margin_deleverage_pressure: float = 0.0
        self.portfolio_margin_deleverage_ratio: float = 0.0
        self.forced_margin_deleverage_count: int = 0
        self.forced_margin_deleverage_closed_volume: int = 0
        self.forced_margin_deleverage_ratio: float = 0.0
        self.forced_margin_deleverage_max_observed_ratio: float = 0.0
        self.forced_margin_deleverage_events: list[dict[str, Any]] = []
        self.portfolio_overheat_cooldown_scale: float = 1.0
        self.portfolio_overheat_cooldown_reason: str = ""
        self.portfolio_overheat_cooldown_prior_drawdown_pct: float = 0.0
        self.portfolio_overheat_cooldown_prior_ret20: float = float("nan")
        self.portfolio_overheat_cooldown_prior_ret60: float = float("nan")
        self.portfolio_overheat_cooldown_equity_history: list[float] = []
        self.portfolio_overheat_cooldown_scale_history: list[dict[str, Any]] = []
        self.portfolio_overheat_cooldown_deleverage_count: int = 0
        self.product_direction_outcome_history: dict[tuple[str, str], list[dict[str, Any]]] = {}
        self.product_direction_failure_cooldown_count: int = 0
        self.product_direction_failure_cooldown_events: list[dict[str, Any]] = []
        self.failure_memory_micro_sizing_count: int = 0
        self.current_bar_date: pd.Timestamp | None = None
        self.pending_margin_reservation: float = 0.0
        self.pending_cluster_margin_reservation: dict[str, float] = {}
        self.pending_active_products: set[str] = set()
        self.current_env_gate_snapshot: dict[str, Any] = {}
        self.selection_pairwise_volume_tilt_last_date_by_direction: dict[str, pd.Timestamp] = {}
        self.ai_product_pool_by_date: dict[pd.Timestamp, dict[str, dict[str, Any]]] = {}
        self.ai_product_pool_eval_dates: list[pd.Timestamp] = []
        if self.enable_ai_product_pool_filter:
            self._load_ai_product_pool_eligibility()
        self.supply_demand_signals: pd.DataFrame = pd.DataFrame()
        self.supply_demand_signal_index: dict[tuple[str, str], pd.DataFrame] = {}
        if self.enable_supply_demand_headwind_filter:
            self._load_supply_demand_signals()
        self.selection_pairwise_runtime: SelectionPairwiseRuntimeModel | None = None
        if self.enable_selection_pairwise_v2:
            self.selection_pairwise_runtime = SelectionPairwiseRuntimeModel(
                model_path=self.selection_pairwise_model_path,
                summary_path=self.selection_pairwise_summary_path,
                enable_catastrophic_veto=self.enable_selection_pairwise_v2_catastrophic_veto,
                catastrophic_veto_penalty=self.selection_pairwise_veto_penalty,
            )
        self.ai_path_damage_runtime: PathDamageRuntimeModel | None = None
        if self.enable_ai_path_damage_risk_discount:
            self.ai_path_damage_runtime = PathDamageRuntimeModel(
                model_path=self.ai_path_damage_model_path,
                summary_path=self.ai_path_damage_summary_path,
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
        # eval_date is treated as a completed signal snapshot. On the exact
        # eval_date, keep using the prior snapshot; the new one is tradable
        # from the next trade date unless the caller explicitly shifts the
        # effective date via _ai_product_pool_entry_effective_date().
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

    def _ai_product_pool_entry_allowed(
        self,
        product_vt_symbol: str,
        trade_date: pd.Timestamp,
    ) -> tuple[bool, dict[str, Any]]:
        effective_date = self._ai_product_pool_entry_effective_date(trade_date)
        snapshot = self._ai_product_pool_snapshot(product_vt_symbol, effective_date)
        snapshot["ai_product_pool_use_next_trade_date_for_entry"] = int(
            bool(self.ai_product_pool_use_next_trade_date_for_entry)
        )
        snapshot["ai_product_pool_entry_effective_date"] = effective_date.date().isoformat()
        if not self.enable_ai_product_pool_filter:
            return True, snapshot
        return int(snapshot.get("ai_product_pool_allowed", 1) or 0) == 1, snapshot

    def _ai_product_pool_entry_effective_date(self, trade_date: pd.Timestamp) -> pd.Timestamp:
        normalized_date = pd.Timestamp(trade_date)
        if normalized_date.tz is not None:
            normalized_date = normalized_date.tz_localize(None)
        normalized_date = normalized_date.normalize()
        if not self.ai_product_pool_use_next_trade_date_for_entry:
            return normalized_date
        if not self.available_trade_dates:
            return normalized_date
        trade_index = pd.DatetimeIndex(self.available_trade_dates)
        next_index = int(trade_index.searchsorted(normalized_date, side="right"))
        if next_index >= len(trade_index):
            return normalized_date
        return pd.Timestamp(trade_index[next_index]).normalize()

    def _load_supply_demand_signals(self) -> None:
        path = Path(str(self.supply_demand_signal_path or ""))
        if not path.exists():
            self.write_log(f"Supply-demand signal file missing: {path}")
            return

        df = pd.read_csv(path)
        required_columns = {
            "available_datetime",
            "product_vt_symbol",
            "direction",
            "external_quality_score",
        }
        missing_columns = required_columns - set(df.columns)
        if missing_columns:
            self.write_log(f"Supply-demand signal file missing columns: {sorted(missing_columns)}")
            return

        frame = df.copy()
        frame["available_datetime"] = pd.to_datetime(frame["available_datetime"], errors="coerce")
        frame = frame[frame["available_datetime"].notna()].copy()
        if frame.empty:
            self.write_log(f"Supply-demand signal file has no valid rows: {path}")
            return

        frame["available_datetime"] = frame["available_datetime"].map(
            lambda value: pd.Timestamp(value).tz_localize(None)
        )
        frame["product_vt_symbol"] = frame["product_vt_symbol"].astype(str).str.strip()
        frame["direction"] = frame["direction"].astype(str).str.lower().str.strip()
        frame["external_quality_score"] = (
            pd.to_numeric(frame["external_quality_score"], errors="coerce").fillna(0.0).clip(-1.0, 1.0)
        )
        frame.sort_values(["product_vt_symbol", "direction", "available_datetime"], inplace=True)

        self.supply_demand_signals = frame
        self.supply_demand_signal_index = {
            (str(product), str(direction)): group.reset_index(drop=True)
            for (product, direction), group in frame.groupby(["product_vt_symbol", "direction"], sort=False)
        }

    def _supply_demand_headwind_snapshot(
        self,
        product_vt_symbol: str,
        direction: str,
        trade_datetime: pd.Timestamp,
    ) -> dict[str, Any]:
        if not self.enable_supply_demand_headwind_filter:
            return {
                "supply_demand_headwind_enabled": 0,
                "supply_demand_headwind_matched": 0,
                "supply_demand_headwind_score": 0.0,
                "supply_demand_headwind_weight": 1.0,
                "supply_demand_headwind_threshold": float(self.supply_demand_headwind_threshold),
                "supply_demand_headwind_signal_age_days": 0.0,
                "supply_demand_headwind_signal_datetime": "",
                "supply_demand_headwind_reason": "disabled",
            }

        snapshot = {
            "supply_demand_headwind_enabled": 1,
            "supply_demand_headwind_matched": 0,
            "supply_demand_headwind_score": 0.0,
            "supply_demand_headwind_weight": 1.0,
            "supply_demand_headwind_threshold": float(self.supply_demand_headwind_threshold),
            "supply_demand_headwind_signal_age_days": 0.0,
            "supply_demand_headwind_signal_datetime": "",
            "supply_demand_headwind_reason": "no_signal",
        }
        if self.supply_demand_signals.empty:
            return snapshot

        trade_dt = pd.Timestamp(trade_datetime).tz_localize(None)
        max_age_days = max(0, int(self.supply_demand_headwind_max_age_days or 0))
        min_dt = trade_dt - pd.Timedelta(days=max_age_days)

        candidate_frames: list[pd.DataFrame] = []
        for key in (
            (product_vt_symbol, direction),
            (product_vt_symbol, "both"),
            (product_vt_symbol, "all"),
            ("ALL", direction),
            ("ALL", "both"),
            ("all", direction),
            ("all", "both"),
        ):
            frame = self.supply_demand_signal_index.get(key)
            if frame is not None and not frame.empty:
                candidate_frames.append(frame)
        if not candidate_frames:
            return snapshot

        candidates = pd.concat(candidate_frames, ignore_index=True)
        candidates = candidates[
            (candidates["available_datetime"] <= trade_dt)
            & (candidates["available_datetime"] >= min_dt)
        ].copy()
        if candidates.empty:
            return snapshot

        candidates.sort_values(["available_datetime"], ascending=False, inplace=True)
        row = candidates.iloc[0]
        score = float(row.get("external_quality_score", 0.0) or 0.0)
        threshold = float(self.supply_demand_headwind_threshold)
        weight = 1.0 if score > threshold else self._clip01(float(self.supply_demand_headwind_weight_floor))
        age_days = (trade_dt - pd.Timestamp(row["available_datetime"])).total_seconds() / 86400.0
        snapshot.update(
            {
                "supply_demand_headwind_matched": 1,
                "supply_demand_headwind_score": score,
                "supply_demand_headwind_weight": weight,
                "supply_demand_headwind_signal_age_days": age_days,
                "supply_demand_headwind_signal_datetime": pd.Timestamp(row["available_datetime"]).isoformat(),
                "supply_demand_headwind_reason": "strong_headwind" if score <= threshold else "passed",
            }
        )
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
        rebalance_bars: dict[str, BarData] = dict(bars)
        engine_bars: dict[str, BarData] = getattr(self.strategy_engine, "bars", {})
        for vt_symbol, pos in list(self.pos_data.items()):
            if not pos or vt_symbol in rebalance_bars:
                continue
            if self.get_target(vt_symbol) == pos:
                continue
            bar = engine_bars.get(vt_symbol)
            if bar is not None:
                rebalance_bars[vt_symbol] = bar
        super().rebalance_portfolio(rebalance_bars)
        self.execution_price_overrides.clear()

    def on_bars(self, bars: dict[str, BarData]) -> None:
        if not bars:
            return

        self._reset_intrabar_reservations()

        for vt_symbol, bar in bars.items():
            if vt_symbol in self.ams:
                self.ams[vt_symbol].update_bar(bar)

        current_date: str = next(iter(bars.values())).datetime.strftime("%Y-%m-%d")
        self.current_bar_date = pd.Timestamp(current_date).normalize()
        mapping_today: dict[str, str] = self.daily_mapping.get(current_date, {})
        self._refresh_risk_state(bars)
        self.last_signal = ""

        day_contexts: list[DailyEntryContext] = []
        for product_vt in self.product_symbols:
            target_contract: str = mapping_today.get(product_vt, "")
            if not target_contract:
                self._close_position_when_target_unavailable(
                    product_vt,
                    state=self.states[product_vt],
                    target_contract="",
                    bars=bars,
                    reason="rollover_close_missing_target_contract",
                )
                continue

            state: ProductState = self.states[product_vt]
            actual_contract, current_pos, actual_bar = self._resolve_actual_position(state, target_contract, bars)
            if actual_contract and current_pos != 0:
                state.contract_vt_symbol = actual_contract

            target_bar: BarData | None = bars.get(target_contract)
            rollover_delay_active = False
            if self._rollover_delay_applies(state, target_contract, current_pos):
                actual_bar = self._same_day_bar(actual_contract, bars, current_date)
                delay_due = self._rollover_delay_due(
                    state=state,
                    target_contract=target_contract,
                    current_date=current_date,
                )
                if delay_due:
                    if actual_bar is None:
                        self._record_rollover_delay_diagnostic(
                            state=state,
                            target_contract=target_contract,
                            current_date=current_date,
                            status="due_old_bar_missing",
                        )
                        continue
                    if target_bar is None:
                        self._reconcile_state_with_position(state, current_pos, actual_bar)
                        rollover_bars = dict(bars)
                        rollover_bars[actual_contract] = actual_bar
                        self._handle_rollover(state, target_contract, rollover_bars)
                        continue
                else:
                    if actual_bar is None:
                        self._record_rollover_delay_diagnostic(
                            state=state,
                            target_contract=target_contract,
                            current_date=current_date,
                            status="waiting_old_bar_missing",
                        )
                        continue
                    target_contract = state.contract_vt_symbol
                    target_bar = actual_bar
                    rollover_delay_active = True
            elif state.rollover_pending_target_contract:
                self._clear_rollover_delay_state(state)

            if target_bar is None:
                self._close_position_when_target_unavailable(
                    product_vt,
                    state=state,
                    target_contract=target_contract,
                    bars=bars,
                    reason="rollover_close_missing_target_bar",
                )
                continue

            target_am: ArrayManager = self.ams[target_contract]
            if not target_am.inited:
                if current_pos != 0 and state.contract_vt_symbol and state.contract_vt_symbol != target_contract:
                    reconcile_bar = actual_bar or self._bar_from_current_or_engine(actual_contract, bars) or target_bar
                    self._reconcile_state_with_position(state, current_pos, reconcile_bar)
                    if state.contract_vt_symbol and state.contract_vt_symbol != target_contract:
                        self._handle_rollover(state, target_contract, bars)
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
                    rollover_delay_active=rollover_delay_active,
                )
            )

        self.current_env_gate_snapshot = self._build_daily_env_gate_snapshot(day_contexts)
        entry_allowed_today = self._entry_allowed_today(current_date)
        flat_entry_plans = self._plan_flat_entry_candidates(day_contexts) if entry_allowed_today else {}

        for context in day_contexts:
            product_vt = context.product_vt_symbol
            state = context.state
            target_contract = context.target_contract
            target_bar = context.target_bar
            actual_bar = context.actual_bar
            current_pos = context.current_pos
            history = context.history
            signal_data = context.signal_data
            rollover_delay_active = context.rollover_delay_active
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
                if not entry_allowed_today:
                    continue
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

            heat_deleverage_reason: str = self._process_risk_cluster_heat_deleverage(state, target_bar)
            if heat_deleverage_reason:
                self.last_signal = f"{product_vt}:{heat_deleverage_reason}"
                continue

            portfolio_margin_deleverage_reason: str = self._process_portfolio_margin_deleverage(state, target_bar)
            if portfolio_margin_deleverage_reason:
                self.last_signal = f"{product_vt}:{portfolio_margin_deleverage_reason}"
                continue

            portfolio_deleverage_reason: str = self._process_portfolio_drawdown_deleverage(state, target_bar)
            if portfolio_deleverage_reason:
                self.last_signal = f"{product_vt}:{portfolio_deleverage_reason}"
                continue

            portfolio_volatility_budget_deleverage_reason: str = self._process_portfolio_volatility_budget_deleverage(
                state,
                target_bar,
            )
            if portfolio_volatility_budget_deleverage_reason:
                self.last_signal = f"{product_vt}:{portfolio_volatility_budget_deleverage_reason}"
                continue

            portfolio_overheat_cooldown_deleverage_reason: str = self._process_portfolio_overheat_cooldown_deleverage(
                state,
                target_bar,
            )
            if portfolio_overheat_cooldown_deleverage_reason:
                self.last_signal = f"{product_vt}:{portfolio_overheat_cooldown_deleverage_reason}"
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
                    if (
                        not rollover_delay_active
                        and entry_allowed_today
                        and self.short_entry_enabled
                        and self._can_open_short_signal(signal)
                    ):
                        sizing = self._calculate_entry_sizing(
                            target_contract,
                            "short",
                            target_bar,
                            history,
                            signal_data,
                            entry_context="reverse_entry",
                        )
                        ai_allowed, ai_product_pool_snapshot = self._ai_product_pool_entry_allowed(
                            state.product_vt_symbol,
                            pd.Timestamp(target_bar.datetime).normalize(),
                        )
                        sizing.update(ai_product_pool_snapshot)
                        volume = int(sizing["selected_volume"])
                        if ai_allowed and volume > 0:
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
                    if not rollover_delay_active and entry_allowed_today and self.long_entry_enabled:
                        sizing = self._calculate_entry_sizing(
                            target_contract,
                            "long",
                            target_bar,
                            history,
                            signal_data,
                            entry_context="reverse_entry",
                        )
                        ai_allowed, ai_product_pool_snapshot = self._ai_product_pool_entry_allowed(
                            state.product_vt_symbol,
                            pd.Timestamp(target_bar.datetime).normalize(),
                        )
                        sizing.update(ai_product_pool_snapshot)
                        volume = int(sizing["selected_volume"])
                        if ai_allowed and volume > 0:
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

            if rollover_delay_active:
                continue

            can_post_quality_add, post_quality_signal, post_quality_stats = self._check_post_entry_quality_add_conditions(
                state,
                target_bar,
                history,
            )
            if entry_allowed_today and can_post_quality_add and post_quality_signal:
                self.post_entry_quality_add_signal_count += 1
                add_volume, add_sizing_snapshot = self._calculate_directional_boosted_add_sizing(
                    state,
                    target_bar,
                    history,
                    "post_quality_add",
                )
                if add_volume <= 0:
                    self.post_entry_quality_add_zero_volume_count += 1
                add_volume = self._risk_cluster_heat_gate_adjust_add_volume(
                    state.contract_vt_symbol,
                    add_volume,
                    target_bar.close_price,
                    "post_quality_add",
                )
                add_volume = self._portfolio_drawdown_gate_adjust_volume(add_volume, "post_quality_add")
                add_volume = self._portfolio_volatility_budget_adjust_volume(add_volume, "post_quality_add")
                add_volume = self._portfolio_overheat_cooldown_adjust_volume(add_volume, "post_quality_add")
                post_quality_margin_per_contract = (
                    float(target_bar.close_price)
                    * self.get_size(state.contract_vt_symbol)
                    * self._margin_ratio_for_symbol(state.contract_vt_symbol)
                )
                add_volume, _ = self._incremental_margin_budget_gate_adjust_volume(
                    selected_volume=add_volume,
                    margin_per_contract=post_quality_margin_per_contract,
                    entry_context="post_quality_add",
                )
                ai_allowed, _ = self._ai_product_pool_entry_allowed(
                    state.product_vt_symbol,
                    pd.Timestamp(target_bar.datetime).normalize(),
                )
                if (
                    ai_allowed
                    and add_volume > 0
                    and self._can_allocate_margin(state.contract_vt_symbol, add_volume, target_bar.close_price)
                ):
                    self._execute_post_entry_quality_add(
                        state,
                        target_bar,
                        post_quality_signal,
                        add_volume,
                        history,
                        post_quality_stats,
                        sizing_snapshot_extra=add_sizing_snapshot,
                    )
                    self._reserve_intrabar_margin(state.contract_vt_symbol, add_volume, float(target_bar.close_price))
                    self._apply_state_target(state)
                    self.last_signal = f"{product_vt}:{post_quality_signal}"
                    continue

            can_add, add_type = self._check_regular_add_conditions(state, target_bar, history)
            if entry_allowed_today and can_add and add_type:
                add_volume, add_sizing_snapshot = self._calculate_directional_boosted_add_sizing(
                    state,
                    target_bar,
                    history,
                    "regular_add",
                )
                add_volume = self._risk_cluster_heat_gate_adjust_add_volume(
                    state.contract_vt_symbol,
                    add_volume,
                    target_bar.close_price,
                    "regular_add",
                )
                add_volume = self._portfolio_drawdown_gate_adjust_volume(add_volume, "regular_add")
                add_volume = self._portfolio_volatility_budget_adjust_volume(add_volume, "regular_add")
                add_volume = self._portfolio_overheat_cooldown_adjust_volume(add_volume, "regular_add")
                regular_margin_per_contract = (
                    float(target_bar.close_price)
                    * self.get_size(state.contract_vt_symbol)
                    * self._margin_ratio_for_symbol(state.contract_vt_symbol)
                )
                add_volume, _ = self._incremental_margin_budget_gate_adjust_volume(
                    selected_volume=add_volume,
                    margin_per_contract=regular_margin_per_contract,
                    entry_context="regular_add",
                )
                ai_allowed, _ = self._ai_product_pool_entry_allowed(
                    state.product_vt_symbol,
                    pd.Timestamp(target_bar.datetime).normalize(),
                )
                if (
                    ai_allowed
                    and add_volume > 0
                    and self._can_allocate_margin(state.contract_vt_symbol, add_volume, target_bar.close_price)
                ):
                    self._execute_regular_add(
                        state,
                        target_bar,
                        add_type,
                        add_volume,
                        history,
                        sizing_snapshot_extra=add_sizing_snapshot,
                    )
                    self._reserve_intrabar_margin(state.contract_vt_symbol, add_volume, float(target_bar.close_price))
                    self._apply_state_target(state)
                    self.last_signal = f"{product_vt}:{add_type}"
                    continue

            can_don_add, don_add_type = self._check_donchian_add_conditions(state, target_bar, history)
            if entry_allowed_today and can_don_add and don_add_type:
                add_volume, add_sizing_snapshot = self._calculate_directional_boosted_add_sizing(
                    state,
                    target_bar,
                    history,
                    "donchian_add",
                )
                add_volume = self._risk_cluster_heat_gate_adjust_add_volume(
                    state.contract_vt_symbol,
                    add_volume,
                    target_bar.close_price,
                    "donchian_add",
                )
                add_volume = self._portfolio_drawdown_gate_adjust_volume(add_volume, "donchian_add")
                add_volume = self._portfolio_volatility_budget_adjust_volume(add_volume, "donchian_add")
                add_volume = self._portfolio_overheat_cooldown_adjust_volume(add_volume, "donchian_add")
                donchian_margin_per_contract = (
                    float(target_bar.close_price)
                    * self.get_size(state.contract_vt_symbol)
                    * self._margin_ratio_for_symbol(state.contract_vt_symbol)
                )
                add_volume, _ = self._incremental_margin_budget_gate_adjust_volume(
                    selected_volume=add_volume,
                    margin_per_contract=donchian_margin_per_contract,
                    entry_context="donchian_add",
                )
                ai_allowed, _ = self._ai_product_pool_entry_allowed(
                    state.product_vt_symbol,
                    pd.Timestamp(target_bar.datetime).normalize(),
                )
                if (
                    ai_allowed
                    and add_volume > 0
                    and self._can_allocate_margin(state.contract_vt_symbol, add_volume, target_bar.close_price)
                ):
                    self._execute_donchian_add(
                        state,
                        target_bar,
                        don_add_type,
                        add_volume,
                        history,
                        sizing_snapshot_extra=add_sizing_snapshot,
                    )
                    self._reserve_intrabar_margin(state.contract_vt_symbol, add_volume, float(target_bar.close_price))
                    self._apply_state_target(state)
                    self.last_signal = f"{product_vt}:{don_add_type}"

        self.rebalance_portfolio(bars)
        forced_count_before = self.forced_margin_deleverage_count
        self._process_forced_margin_deleverage(bars)
        if self.forced_margin_deleverage_count > forced_count_before:
            self.rebalance_portfolio(bars)
        self._record_portfolio_volatility_budget_daily_return()
        self._record_portfolio_overheat_cooldown_daily_equity()
        self.settled_balance = self.estimated_equity
        self.last_close_prices = {vt_symbol: float(bar.close_price) for vt_symbol, bar in bars.items()}
        self.active_count = self._count_active_positions()
        self.put_event()

    def _entry_allowed_today(self, current_date: str) -> bool:
        start_text = str(self.trade_start_date or "").strip()
        if not start_text:
            return True
        try:
            return pd.Timestamp(current_date).normalize() >= pd.Timestamp(start_text).normalize()
        except Exception:
            return True

    @staticmethod
    def _clear_rollover_delay_state(state: ProductState) -> None:
        state.rollover_pending_target_contract = ""
        state.rollover_pending_signal_date = ""
        state.rollover_pending_last_counted_date = ""
        state.rollover_pending_elapsed_trading_days = 0

    def _record_rollover_delay_diagnostic(
        self,
        *,
        state: ProductState,
        target_contract: str,
        current_date: str,
        status: str,
    ) -> None:
        self.rollover_delay_diagnostics.append(
            {
                "diagnostic_index": len(self.rollover_delay_diagnostics) + 1,
                "date": current_date,
                "product_vt_symbol": state.product_vt_symbol,
                "old_contract_vt_symbol": state.contract_vt_symbol,
                "target_contract_vt_symbol": target_contract,
                "signal_date": state.rollover_pending_signal_date,
                "elapsed_trading_days": int(state.rollover_pending_elapsed_trading_days),
                "required_trading_days": max(0, int(self.rollover_delay_trading_days or 0)),
                "status": status,
            }
        )

    def _rollover_delay_due(
        self,
        *,
        state: ProductState,
        target_contract: str,
        current_date: str,
    ) -> bool:
        required_days = max(0, int(self.rollover_delay_trading_days or 0))
        if required_days <= 0:
            self._clear_rollover_delay_state(state)
            return True

        if state.rollover_pending_target_contract != target_contract:
            if state.rollover_pending_target_contract:
                self._record_rollover_delay_diagnostic(
                    state=state,
                    target_contract=state.rollover_pending_target_contract,
                    current_date=current_date,
                    status="target_changed_reset",
                )
            state.rollover_pending_target_contract = target_contract
            state.rollover_pending_signal_date = current_date
            state.rollover_pending_last_counted_date = current_date
            state.rollover_pending_elapsed_trading_days = 0
            self._record_rollover_delay_diagnostic(
                state=state,
                target_contract=target_contract,
                current_date=current_date,
                status="scheduled",
            )
            return False

        if state.rollover_pending_last_counted_date != current_date:
            state.rollover_pending_elapsed_trading_days += 1
            state.rollover_pending_last_counted_date = current_date

        elapsed_days = state.rollover_pending_elapsed_trading_days
        due = elapsed_days >= required_days
        self._record_rollover_delay_diagnostic(
            state=state,
            target_contract=target_contract,
            current_date=current_date,
            status=("overdue" if elapsed_days > required_days else "due") if due else "waiting",
        )
        return due

    def _rollover_delay_applies(
        self,
        state: ProductState,
        target_contract: str,
        current_pos: int,
    ) -> bool:
        return bool(
            int(self.rollover_delay_trading_days or 0) > 0
            and current_pos != 0
            and state.contract_vt_symbol
            and state.contract_vt_symbol != target_contract
        )

    def _same_day_bar(
        self,
        vt_symbol: str,
        bars: dict[str, BarData],
        current_date: str,
    ) -> BarData | None:
        bar = self._bar_from_current_or_engine(vt_symbol, bars)
        if bar is None:
            return None
        if pd.Timestamp(bar.datetime).strftime("%Y-%m-%d") != current_date:
            return None
        return bar

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
        delayed_rollover = bool(
            int(self.rollover_delay_trading_days or 0) > 0
            and state.rollover_pending_target_contract == target_contract
        )
        if delayed_rollover:
            current_dates = [pd.Timestamp(bar.datetime).strftime("%Y-%m-%d") for bar in bars.values()]
            current_date = max(current_dates) if current_dates else ""
            old_bar = self._same_day_bar(old_contract, bars, current_date)
            new_bar = self._same_day_bar(target_contract, bars, current_date)
        else:
            old_bar = self._bar_from_current_or_engine(old_contract, bars)
            new_bar = self._bar_from_current_or_engine(target_contract, bars)
        if not old_bar:
            return

        old_direction: str = state.direction
        old_risk_mode: str = state.risk_mode
        previous_volume: int = state.active_volume()
        released_risk_snapshot: dict[str, Any] = {}
        if self.enable_rollover_shape_same_volume_reopen:
            released_risk_snapshot = self._rollover_released_risk_snapshot(
                state=state,
                old_contract=old_contract,
                old_bar=old_bar,
                risk_snapshot_includes_old_contract=old_contract in bars,
            )
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
        if self.enable_rollover_shape_same_volume_reopen:
            self._apply_rollover_released_risk_snapshot(released_risk_snapshot)

        if not self.rollover_reopen_enabled:
            return

        target_am: ArrayManager | None = self.ams.get(target_contract)
        shape_snapshot: dict[str, Any] | None = None
        if self.enable_rollover_shape_same_volume_reopen:
            current_bar_dates = [self._bar_date(bar) for bar in bars.values()]
            current_bar_date = max(current_bar_dates) if current_bar_dates else None
            history, history_snapshot = self._build_rollover_shape_history(
                old_contract=old_contract,
                target_contract=target_contract,
                old_bar=old_bar,
                new_bar=new_bar,
                target_am=target_am,
                target_bar_from_current=bool(
                    new_bar is not None
                    and target_contract in bars
                    and current_bar_date is not None
                    and self._bar_date(new_bar) == current_bar_date
                ),
            )
            shape_snapshot = self._rollover_shape_continuation_snapshot(old_direction, history)
            if not int(history_snapshot["history_input_ready"]):
                shape_snapshot["allowed"] = 0
                shape_snapshot["reason"] = str(history_snapshot["history_input_reason"])
            shape_snapshot.update(history_snapshot)
            if not int(shape_snapshot["allowed"]):
                self._record_rollover_shape_same_volume_diagnostic(
                    state=state,
                    old_contract=old_contract,
                    target_contract=target_contract,
                    old_direction=old_direction,
                    old_risk_mode=old_risk_mode,
                    bar=new_bar or old_bar,
                    target_am_inited=bool(target_am and target_am.inited),
                    previous_volume=previous_volume,
                    selected_volume=0,
                    final_volume=0,
                    status="skipped",
                    reason=str(shape_snapshot["reason"]),
                    shape_snapshot=shape_snapshot,
                )
                return
            signal_data = self._rollover_shape_signal_data(old_direction, old_risk_mode, shape_snapshot)
        else:
            if not new_bar or target_am is None:
                return
            if not target_am.inited:
                return
            history = self._build_history_df(target_am)
            signal_data = self._generate_signal(target_am, history)
            if not self._rollover_reopen_allowed(old_direction, history, signal_data):
                return

        if new_bar is None:
            return

        guard_fields = self._rollover_reopen_drawdown_guard_fields()
        if int(guard_fields["rollover_reopen_drawdown_guard_enabled"]) and not int(
            guard_fields["rollover_reopen_drawdown_guard_passed"]
        ):
            self._record_rollover_reopen_guard_skip(
                state=state,
                old_contract=old_contract,
                target_contract=target_contract,
                old_direction=old_direction,
                old_risk_mode=old_risk_mode,
                bar=new_bar,
                guard_fields=guard_fields,
            )
            if self.enable_rollover_shape_same_volume_reopen:
                self._record_rollover_shape_same_volume_diagnostic(
                    state=state,
                    old_contract=old_contract,
                    target_contract=target_contract,
                    old_direction=old_direction,
                    old_risk_mode=old_risk_mode,
                    bar=new_bar,
                    target_am_inited=bool(target_am and target_am.inited),
                    previous_volume=previous_volume,
                    selected_volume=0,
                    final_volume=0,
                    status="skipped",
                    reason="rollover_reopen_portfolio_drawdown_guard",
                    shape_snapshot=shape_snapshot or {},
                )
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
        sizing.update(guard_fields)
        sizing.update(released_risk_snapshot)
        selected_volume: int = int(sizing["selected_volume"])
        if self.enable_rollover_shape_same_volume_reopen:
            volume, volume_reason = self._rollover_shape_reopen_volume(
                previous_volume=previous_volume,
                sizing_snapshot=sizing,
                volume_policy=self.rollover_shape_volume_policy,
            )
            sizing.update(
                {
                    "rollover_previous_volume": previous_volume,
                    "rollover_selected_volume_before_policy": selected_volume,
                    "rollover_volume_policy": self.rollover_shape_volume_policy,
                    "rollover_final_volume": volume,
                    "rollover_volume_reason": volume_reason,
                }
            )
        else:
            volume = selected_volume
        if volume <= 0:
            if self.enable_rollover_shape_same_volume_reopen:
                self._record_rollover_shape_same_volume_diagnostic(
                    state=state,
                    old_contract=old_contract,
                    target_contract=target_contract,
                    old_direction=old_direction,
                    old_risk_mode=old_risk_mode,
                    bar=new_bar,
                    target_am_inited=bool(target_am and target_am.inited),
                    previous_volume=previous_volume,
                    selected_volume=selected_volume,
                    final_volume=0,
                    status="skipped",
                    reason=volume_reason,
                    shape_snapshot=shape_snapshot or {},
                )
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
        if self.enable_rollover_shape_same_volume_reopen:
            self._reserve_intrabar_entry(
                state.product_vt_symbol,
                sizing,
                volume,
                count_active_position=False,
            )
        self._apply_state_target(state)
        if self.enable_rollover_shape_same_volume_reopen:
            self._record_rollover_shape_same_volume_diagnostic(
                state=state,
                old_contract=old_contract,
                target_contract=target_contract,
                old_direction=old_direction,
                old_risk_mode=old_risk_mode,
                bar=new_bar,
                target_am_inited=bool(target_am and target_am.inited),
                previous_volume=previous_volume,
                selected_volume=selected_volume,
                final_volume=volume,
                status="targeted",
                reason=volume_reason,
                shape_snapshot=shape_snapshot or {},
            )

    def _close_position_when_target_unavailable(
        self,
        product_vt: str,
        *,
        state: ProductState,
        target_contract: str,
        bars: dict[str, BarData],
        reason: str,
    ) -> None:
        actual_contract, current_pos, actual_bar = self._resolve_actual_position(state, target_contract, bars)
        if actual_bar is None:
            actual_bar = self._bar_from_current_or_engine(actual_contract, bars)
        if current_pos == 0 or not actual_contract or actual_bar is None:
            return
        if target_contract and actual_contract == target_contract:
            return

        state.contract_vt_symbol = actual_contract
        self._reconcile_state_with_position(state, current_pos, actual_bar)
        self._record_trade_event(
            bar=actual_bar,
            contract_vt_symbol=actual_contract,
            product_vt_symbol=product_vt,
            position_direction=state.direction,
            offset="Close",
            reason=reason,
            volume=state.active_volume(),
            price=float(actual_bar.close_price),
        )
        self._close_all_layers(state, float(actual_bar.close_price))
        self.set_target(actual_contract, 0)

    def _bar_from_current_or_engine(self, vt_symbol: str, bars: dict[str, BarData]) -> BarData | None:
        if not vt_symbol:
            return None
        bar = bars.get(vt_symbol)
        if bar is not None:
            return bar
        engine_bars: dict[str, BarData] = getattr(self.strategy_engine, "bars", {})
        return engine_bars.get(vt_symbol)

    def _refresh_risk_state(self, bars: dict[str, BarData]) -> None:
        self.estimated_equity = self._estimate_equity(bars)
        self._refresh_portfolio_drawdown_state()
        self._refresh_portfolio_volatility_budget_state()
        self._record_portfolio_volatility_budget_scale_snapshot(bars)
        self._refresh_portfolio_overheat_cooldown_state()
        self._record_portfolio_overheat_cooldown_scale_snapshot(bars)
        self.total_margin_in_use = self._estimate_margin_usage(bars)
        self.cluster_margin_usage = self._estimate_margin_usage_by_cluster(bars)
        self.cluster_unrealized_pnl = self._estimate_unrealized_pnl_by_cluster(bars)
        self._refresh_portfolio_margin_deleverage_state()
        self.risk_cluster_margin_in_use = max(self.cluster_margin_usage.values(), default=0.0)
        self.risk_cluster_unrealized_loss_in_use = max(
            (max(0.0, -float(value)) for value in self.cluster_unrealized_pnl.values()),
            default=0.0,
        )
        self._refresh_risk_cluster_heat_pressure_snapshot()
        self.risk_cluster_heat_gate_weight = self._current_min_risk_cluster_heat_gate_weight()
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
        self.pending_cluster_margin_reservation.clear()
        self.pending_active_products.clear()

    def _portfolio_env_gate_weight(self, entry_context: str) -> float:
        if not self.enable_portfolio_env_gate or entry_context != "flat_entry":
            return 1.0
        snapshot = self.current_env_gate_snapshot or {}
        return self._clip01(float(snapshot.get("env_gate_weight", 1.0)))

    def _portfolio_drawdown_gate_context_set(self) -> set[str]:
        raw_contexts = str(self.portfolio_drawdown_gate_entry_contexts or "").strip()
        if not raw_contexts:
            return {"flat_entry"}
        contexts = {
            item.strip()
            for item in raw_contexts.split(",")
            if item.strip()
        }
        return contexts or {"flat_entry"}

    def _portfolio_drawdown_gate_context_applies(self, entry_context: str) -> bool:
        contexts = self._portfolio_drawdown_gate_context_set()
        return "*" in contexts or entry_context in contexts

    def _portfolio_drawdown_gate_weight_value(self) -> float:
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

    def _portfolio_drawdown_gate_weight(self, entry_context: str) -> float:
        if (
            not self.enable_portfolio_drawdown_gate
            or not self._portfolio_drawdown_gate_context_applies(entry_context)
        ):
            return 1.0
        return self._portfolio_drawdown_gate_weight_value()

    def _portfolio_drawdown_gate_adjust_volume(self, volume: int, entry_context: str) -> int:
        selected_volume = max(0, int(volume))
        if (
            not self.enable_portfolio_drawdown_gate
            or not self._portfolio_drawdown_gate_context_applies(entry_context)
        ):
            return selected_volume

        adjusted_volume = int(math.floor(selected_volume * self._portfolio_drawdown_gate_weight_value()))
        if 0 < adjusted_volume < self.min_position_size:
            adjusted_volume = 0
        return max(0, adjusted_volume)

    def _portfolio_volatility_budget_context_set(self) -> set[str]:
        raw_contexts = str(self.portfolio_volatility_budget_entry_contexts or "").strip()
        if not raw_contexts:
            return {"flat_entry"}
        contexts = {
            item.strip()
            for item in raw_contexts.split(",")
            if item.strip()
        }
        return contexts or {"flat_entry"}

    def _portfolio_volatility_budget_context_applies(self, entry_context: str) -> bool:
        contexts = self._portfolio_volatility_budget_context_set()
        return "*" in contexts or entry_context in contexts

    def _refresh_portfolio_volatility_budget_state(self) -> None:
        if not self.enable_portfolio_volatility_budget:
            self.portfolio_volatility_budget_scale = 1.0
            self.portfolio_volatility_budget_realized_annual_vol = 0.0
            return

        lookback = max(2, int(self.portfolio_volatility_budget_lookback or 0))
        if len(self.portfolio_volatility_budget_return_history) < lookback:
            self.portfolio_volatility_budget_scale = 1.0
            self.portfolio_volatility_budget_realized_annual_vol = 0.0
            return

        recent_returns = np.array(
            self.portfolio_volatility_budget_return_history[-lookback:],
            dtype="float64",
        )
        realized_daily_vol = float(np.std(recent_returns, ddof=1)) if len(recent_returns) > 1 else 0.0
        realized_annual_vol = realized_daily_vol * math.sqrt(252.0)
        self.portfolio_volatility_budget_realized_annual_vol = realized_annual_vol
        if not math.isfinite(realized_annual_vol) or realized_annual_vol <= 1e-12:
            self.portfolio_volatility_budget_scale = 1.0
            return

        target_vol = max(0.0, float(self.portfolio_volatility_budget_target_annual_vol or 0.0))
        min_scale = self._clip01(float(self.portfolio_volatility_budget_min_scale or 0.0))
        scale = target_vol / realized_annual_vol if target_vol > 0 else min_scale
        self.portfolio_volatility_budget_scale = min(1.0, max(min_scale, scale))

    def _record_portfolio_volatility_budget_daily_return(self) -> None:
        if not self.enable_portfolio_volatility_budget:
            self.portfolio_volatility_budget_last_equity = float(self.estimated_equity or self.base_capital)
            return

        previous_equity = float(self.portfolio_volatility_budget_last_equity or self.base_capital)
        current_equity = float(self.estimated_equity or previous_equity)
        if previous_equity > 1e-9 and math.isfinite(previous_equity) and math.isfinite(current_equity):
            daily_return = current_equity / previous_equity - 1.0
            if math.isfinite(daily_return):
                self.portfolio_volatility_budget_return_history.append(float(daily_return))
        self.portfolio_volatility_budget_last_equity = current_equity

    def _record_portfolio_volatility_budget_scale_snapshot(self, bars: dict[str, BarData]) -> None:
        if not self.enable_portfolio_volatility_budget or not bars:
            return
        current_date = next(iter(bars.values())).datetime.date()
        if (
            self.portfolio_volatility_budget_scale_history
            and self.portfolio_volatility_budget_scale_history[-1].get("date") == current_date
        ):
            return
        self.portfolio_volatility_budget_scale_history.append(
            {
                "date": current_date,
                "scale": float(self.portfolio_volatility_budget_scale or 1.0),
                "realized_annual_vol": float(self.portfolio_volatility_budget_realized_annual_vol or 0.0),
                "lookback": int(self.portfolio_volatility_budget_lookback or 0),
                "target_annual_vol": float(self.portfolio_volatility_budget_target_annual_vol or 0.0),
            }
        )

    def _portfolio_volatility_budget_weight(self, entry_context: str) -> float:
        if (
            not self.enable_portfolio_volatility_budget
            or not self._portfolio_volatility_budget_context_applies(entry_context)
        ):
            return 1.0
        return self._clip01(float(self.portfolio_volatility_budget_scale or 1.0))

    def _portfolio_volatility_budget_adjust_volume(self, volume: int, entry_context: str) -> int:
        selected_volume = max(0, int(volume))
        if (
            not self.enable_portfolio_volatility_budget
            or not self._portfolio_volatility_budget_context_applies(entry_context)
        ):
            return selected_volume

        adjusted_volume = int(math.floor(selected_volume * self._portfolio_volatility_budget_weight(entry_context)))
        if 0 < adjusted_volume < self.min_position_size:
            adjusted_volume = 0
        return max(0, adjusted_volume)

    def _portfolio_overheat_cooldown_context_set(self) -> set[str]:
        raw_contexts = str(self.portfolio_overheat_cooldown_entry_contexts or "").strip()
        if not raw_contexts:
            return {"flat_entry"}
        contexts = {
            item.strip()
            for item in raw_contexts.split(",")
            if item.strip()
        }
        return contexts or {"flat_entry"}

    def _portfolio_overheat_cooldown_context_applies(self, entry_context: str) -> bool:
        contexts = self._portfolio_overheat_cooldown_context_set()
        return "*" in contexts or entry_context in contexts

    def _portfolio_overheat_cooldown_scale_value(self) -> float:
        if not self.enable_portfolio_overheat_cooldown:
            return 1.0
        scale = float(self.portfolio_overheat_cooldown_scale or 1.0)
        max_scale = max(1.0, float(self.portfolio_overheat_cooldown_recovery_scale or 1.0))
        if not math.isfinite(scale):
            return 1.0
        return max(0.0, min(max_scale, scale))

    def _portfolio_overheat_cooldown_fields(self, entry_context: str) -> dict[str, Any]:
        enabled = int(
            self.enable_portfolio_overheat_cooldown
            and self._portfolio_overheat_cooldown_context_applies(entry_context)
        )
        scale = self._portfolio_overheat_cooldown_scale_value() if enabled else 1.0
        return {
            "portfolio_overheat_cooldown_enabled": enabled,
            "portfolio_overheat_cooldown_scale": scale,
            "portfolio_overheat_cooldown_reason": str(self.portfolio_overheat_cooldown_reason or ""),
            "portfolio_overheat_cooldown_prior_drawdown_pct": float(
                self.portfolio_overheat_cooldown_prior_drawdown_pct or 0.0
            ),
            "portfolio_overheat_cooldown_prior_ret20": float(self.portfolio_overheat_cooldown_prior_ret20),
            "portfolio_overheat_cooldown_prior_ret60": float(self.portfolio_overheat_cooldown_prior_ret60),
        }

    def _portfolio_overheat_cooldown_adjust_volume(self, volume: int, entry_context: str) -> int:
        selected_volume = max(0, int(volume))
        if (
            not self.enable_portfolio_overheat_cooldown
            or not self._portfolio_overheat_cooldown_context_applies(entry_context)
        ):
            return selected_volume

        scale = self._portfolio_overheat_cooldown_scale_value()
        adjusted_volume = int(math.floor(selected_volume * scale))
        if 0 < adjusted_volume < self.min_position_size:
            adjusted_volume = 0
        return max(0, adjusted_volume)

    def _refresh_portfolio_overheat_cooldown_state(self) -> None:
        if not self.enable_portfolio_overheat_cooldown:
            self.portfolio_overheat_cooldown_scale = 1.0
            self.portfolio_overheat_cooldown_reason = ""
            self.portfolio_overheat_cooldown_prior_drawdown_pct = 0.0
            self.portfolio_overheat_cooldown_prior_ret20 = float("nan")
            self.portfolio_overheat_cooldown_prior_ret60 = float("nan")
            return

        history = np.array(self.portfolio_overheat_cooldown_equity_history, dtype="float64")
        history = history[np.isfinite(history)]
        if len(history) < 2:
            self.portfolio_overheat_cooldown_scale = 1.0
            self.portfolio_overheat_cooldown_reason = "insufficient_history"
            self.portfolio_overheat_cooldown_prior_drawdown_pct = 0.0
            self.portfolio_overheat_cooldown_prior_ret20 = float("nan")
            self.portfolio_overheat_cooldown_prior_ret60 = float("nan")
            return

        last_equity = float(history[-1])
        high_equity = max(float(np.max(history)), float(self.base_capital), 1e-9)
        drawdown_ratio = max(0.0, (high_equity - last_equity) / high_equity)
        ret20 = float(last_equity / history[-21] - 1.0) if len(history) > 20 and history[-21] > 0 else float("nan")
        ret60 = float(last_equity / history[-61] - 1.0) if len(history) > 60 and history[-61] > 0 else float("nan")

        near_high = drawdown_ratio <= max(0.0, float(self.portfolio_overheat_cooldown_near_high_drawdown_pct or 0.0))
        hot20_threshold = float(self.portfolio_overheat_cooldown_hot20_threshold or 0.0)
        hot60_threshold = float(self.portfolio_overheat_cooldown_hot60_threshold or -1.0)
        hot20 = math.isfinite(ret20) and hot20_threshold >= 0.0 and ret20 > hot20_threshold
        hot60 = math.isfinite(ret60) and hot60_threshold >= 0.0 and ret60 > hot60_threshold
        recovery = (
            drawdown_ratio >= max(0.0, float(self.portfolio_overheat_cooldown_recovery_drawdown_pct or 0.0))
            and math.isfinite(ret20)
            and ret20 > float(self.portfolio_overheat_cooldown_recovery_ret20_threshold or 0.0)
        )

        if near_high and (hot20 or hot60):
            self.portfolio_overheat_cooldown_scale = max(
                0.0,
                min(1.0, float(self.portfolio_overheat_cooldown_brake_scale or 1.0)),
            )
            self.portfolio_overheat_cooldown_reason = "near_high_hot20_or_hot60"
        elif recovery:
            self.portfolio_overheat_cooldown_scale = max(1.0, float(self.portfolio_overheat_cooldown_recovery_scale or 1.0))
            self.portfolio_overheat_cooldown_reason = "deep_drawdown_ret20_recovery"
        else:
            self.portfolio_overheat_cooldown_scale = 1.0
            self.portfolio_overheat_cooldown_reason = "normal"

        self.portfolio_overheat_cooldown_prior_drawdown_pct = drawdown_ratio * 100.0
        self.portfolio_overheat_cooldown_prior_ret20 = ret20
        self.portfolio_overheat_cooldown_prior_ret60 = ret60

    def _record_portfolio_overheat_cooldown_daily_equity(self) -> None:
        if not self.enable_portfolio_overheat_cooldown:
            return
        equity = float(self.estimated_equity or self.base_capital)
        if math.isfinite(equity) and equity > 0:
            self.portfolio_overheat_cooldown_equity_history.append(equity)

    def _record_portfolio_overheat_cooldown_scale_snapshot(self, bars: dict[str, BarData]) -> None:
        if not self.enable_portfolio_overheat_cooldown or not bars:
            return
        current_date = next(iter(bars.values())).datetime.date()
        if (
            self.portfolio_overheat_cooldown_scale_history
            and self.portfolio_overheat_cooldown_scale_history[-1].get("date") == current_date
        ):
            return
        self.portfolio_overheat_cooldown_scale_history.append(
            {
                "date": current_date,
                "scale": float(self.portfolio_overheat_cooldown_scale or 1.0),
                "reason": str(self.portfolio_overheat_cooldown_reason or ""),
                "prior_drawdown_pct": float(self.portfolio_overheat_cooldown_prior_drawdown_pct or 0.0),
                "prior_ret20_pct": float(self.portfolio_overheat_cooldown_prior_ret20) * 100.0,
                "prior_ret60_pct": float(self.portfolio_overheat_cooldown_prior_ret60) * 100.0,
            }
        )

    def _product_direction_failure_cooldown_context_set(self) -> set[str]:
        raw_contexts = str(self.product_direction_failure_cooldown_entry_contexts or "").strip()
        if not raw_contexts:
            return {"flat_entry"}
        contexts = {
            item.strip()
            for item in raw_contexts.replace(";", ",").replace("|", ",").split(",")
            if item.strip()
        }
        return contexts or {"flat_entry"}

    def _product_direction_failure_cooldown_context_applies(self, entry_context: str) -> bool:
        contexts = self._product_direction_failure_cooldown_context_set()
        return "*" in contexts or entry_context in contexts

    def _failure_memory_micro_sizing_context_set(self) -> set[str]:
        raw_contexts = str(self.failure_memory_micro_sizing_entry_contexts or "").strip()
        if not raw_contexts:
            return {"flat_entry"}
        contexts = {
            item.strip()
            for item in raw_contexts.replace(";", ",").replace("|", ",").split(",")
            if item.strip()
        }
        return contexts or {"flat_entry"}

    def _failure_memory_micro_sizing_context_applies(self, entry_context: str) -> bool:
        contexts = self._failure_memory_micro_sizing_context_set()
        return "*" in contexts or entry_context in contexts

    def _oi_price_confirm_risk_restore_context_set(self) -> set[str]:
        raw_contexts = str(self.oi_price_confirm_risk_restore_entry_contexts or "").strip()
        if not raw_contexts:
            return {"flat_entry"}
        contexts = {
            item.strip()
            for item in raw_contexts.replace(";", ",").replace("|", ",").split(",")
            if item.strip()
        }
        return contexts or {"flat_entry"}

    def _oi_price_confirm_risk_restore_context_applies(self, entry_context: str) -> bool:
        contexts = self._oi_price_confirm_risk_restore_context_set()
        return "*" in contexts or entry_context in contexts

    @staticmethod
    def _product_direction_failure_cooldown_date(value: Any) -> pd.Timestamp:
        return pd.Timestamp(value).tz_localize(None).normalize()

    def _record_product_direction_outcome(
        self,
        product_vt_symbol: str,
        direction: str,
        realized_pnl: float,
    ) -> None:
        if not (self.enable_product_direction_failure_cooldown or self.enable_failure_memory_micro_sizing):
            return
        product = str(product_vt_symbol or "").strip()
        side = str(direction or "").strip()
        if not product or side not in {"long", "short"}:
            return
        exit_date = self.current_bar_date
        if exit_date is None:
            exit_date = pd.Timestamp(datetime.now()).normalize()
        exit_date = self._product_direction_failure_cooldown_date(exit_date)
        key = (product, side)
        history = self.product_direction_outcome_history.setdefault(key, [])
        history.append(
            {
                "exit_date": exit_date,
                "realized_pnl": float(realized_pnl),
            }
        )
        lookbacks: list[int] = []
        if self.enable_product_direction_failure_cooldown:
            lookbacks.append(max(1, int(self.product_direction_failure_cooldown_lookback_days or 252)))
        if self.enable_failure_memory_micro_sizing:
            lookbacks.append(max(1, int(self.failure_memory_micro_sizing_lookback_days or 252)))
        lookback = max(lookbacks or [252])
        prune_before = exit_date - pd.Timedelta(days=max(lookback * 3, lookback + 365))
        self.product_direction_outcome_history[key] = [
            item
            for item in history
            if self._product_direction_failure_cooldown_date(item["exit_date"]) >= prune_before
        ]

    def _product_direction_failure_cooldown_fields(
        self,
        *,
        product_vt_symbol: str,
        direction: str,
        entry_context: str,
        asof: pd.Timestamp,
    ) -> dict[str, Any]:
        enabled = int(
            self.enable_product_direction_failure_cooldown
            and self._product_direction_failure_cooldown_context_applies(entry_context)
        )
        lookback_days = max(1, int(self.product_direction_failure_cooldown_lookback_days or 252))
        min_failures = max(1, int(self.product_direction_failure_cooldown_min_consecutive_failures or 3))
        cooldown_days = max(1, int(self.product_direction_failure_cooldown_days or 90))
        fields: dict[str, Any] = {
            "product_direction_failure_cooldown_enabled": enabled,
            "product_direction_failure_cooldown_lookback_days": lookback_days,
            "product_direction_failure_cooldown_min_consecutive_failures": min_failures,
            "product_direction_failure_cooldown_days": cooldown_days,
            "product_direction_failure_cooldown_consecutive_failures": 0,
            "product_direction_failure_cooldown_last_failure_exit_date": "",
            "product_direction_failure_cooldown_until": "",
            "product_direction_failure_cooldown_days_since_last_failure": math.nan,
            "product_direction_failure_cooldown_blocked": 0,
            "product_direction_failure_cooldown_reason": "disabled" if not enabled else "no_recent_failures",
            "product_direction_failure_cooldown_selected_volume_before": 0,
            "product_direction_failure_cooldown_selected_volume_after": 0,
        }
        if not enabled:
            return fields

        product = str(product_vt_symbol or "").strip()
        side = str(direction or "").strip()
        if not product or side not in {"long", "short"}:
            fields["product_direction_failure_cooldown_reason"] = "invalid_product_or_direction"
            return fields

        asof_date = self._product_direction_failure_cooldown_date(asof)
        lookback_start = asof_date - pd.Timedelta(days=lookback_days)
        events = [
            item
            for item in self.product_direction_outcome_history.get((product, side), [])
            if lookback_start <= self._product_direction_failure_cooldown_date(item["exit_date"]) < asof_date
        ]
        if not events:
            return fields

        events.sort(key=lambda item: self._product_direction_failure_cooldown_date(item["exit_date"]))
        consecutive_failures = 0
        last_failure_date: pd.Timestamp | None = None
        for item in reversed(events):
            pnl = float(item.get("realized_pnl", 0.0) or 0.0)
            if pnl <= 0.0:
                consecutive_failures += 1
                if last_failure_date is None:
                    last_failure_date = self._product_direction_failure_cooldown_date(item["exit_date"])
                continue
            break

        fields["product_direction_failure_cooldown_consecutive_failures"] = int(consecutive_failures)
        if last_failure_date is None:
            fields["product_direction_failure_cooldown_reason"] = "last_trade_was_win"
            return fields

        cooldown_until = last_failure_date + pd.Timedelta(days=cooldown_days)
        days_since_last_failure = int((asof_date - last_failure_date).days)
        fields["product_direction_failure_cooldown_last_failure_exit_date"] = last_failure_date.date().isoformat()
        fields["product_direction_failure_cooldown_until"] = cooldown_until.date().isoformat()
        fields["product_direction_failure_cooldown_days_since_last_failure"] = days_since_last_failure
        if consecutive_failures >= min_failures and asof_date <= cooldown_until:
            fields["product_direction_failure_cooldown_blocked"] = 1
            fields["product_direction_failure_cooldown_reason"] = "consecutive_failures_cooldown"
        elif consecutive_failures >= min_failures:
            fields["product_direction_failure_cooldown_reason"] = "cooldown_expired"
        else:
            fields["product_direction_failure_cooldown_reason"] = "below_failure_threshold"
        return fields

    def _failure_memory_micro_sizing_fields(
        self,
        *,
        product_vt_symbol: str,
        direction: str,
        entry_context: str,
        asof: pd.Timestamp,
        base_multiplier: float,
    ) -> dict[str, Any]:
        enabled = int(
            self.enable_failure_memory_micro_sizing
            and self._failure_memory_micro_sizing_context_applies(entry_context)
        )
        lookback_days = max(1, int(self.failure_memory_micro_sizing_lookback_days or 252))
        min_failures = max(1, int(self.failure_memory_micro_sizing_min_consecutive_failures or 2))
        configured_multiplier = max(0.0, float(self.failure_memory_micro_sizing_multiplier or 1.0))
        base_multiplier = max(0.0, float(base_multiplier or 0.0))
        fields: dict[str, Any] = {
            "failure_memory_micro_sizing_enabled": enabled,
            "failure_memory_micro_sizing_applied": 0,
            "failure_memory_micro_sizing_reason": "disabled" if not enabled else "no_recent_failures",
            "failure_memory_micro_sizing_lookback_days": lookback_days,
            "failure_memory_micro_sizing_min_consecutive_failures": min_failures,
            "failure_memory_micro_sizing_multiplier": configured_multiplier,
            "failure_memory_micro_sizing_base_multiplier": base_multiplier,
            "failure_memory_micro_sizing_effective_multiplier": base_multiplier,
            "failure_memory_micro_sizing_consecutive_failures": 0,
            "failure_memory_micro_sizing_last_failure_exit_date": "",
            "failure_memory_micro_sizing_days_since_last_failure": math.nan,
        }
        if not enabled:
            return fields

        product = str(product_vt_symbol or "").strip()
        side = str(direction or "").strip()
        if not product or side not in {"long", "short"}:
            fields["failure_memory_micro_sizing_reason"] = "invalid_product_or_direction"
            return fields

        asof_date = self._product_direction_failure_cooldown_date(asof)
        lookback_start = asof_date - pd.Timedelta(days=lookback_days)
        events = [
            item
            for item in self.product_direction_outcome_history.get((product, side), [])
            if lookback_start <= self._product_direction_failure_cooldown_date(item["exit_date"]) < asof_date
        ]
        if not events:
            return fields

        events.sort(key=lambda item: self._product_direction_failure_cooldown_date(item["exit_date"]))
        consecutive_failures = 0
        last_failure_date: pd.Timestamp | None = None
        for item in reversed(events):
            pnl = float(item.get("realized_pnl", 0.0) or 0.0)
            if pnl <= 0.0:
                consecutive_failures += 1
                if last_failure_date is None:
                    last_failure_date = self._product_direction_failure_cooldown_date(item["exit_date"])
                continue
            break

        fields["failure_memory_micro_sizing_consecutive_failures"] = int(consecutive_failures)
        if last_failure_date is None:
            fields["failure_memory_micro_sizing_reason"] = "last_trade_was_win"
            return fields

        fields["failure_memory_micro_sizing_last_failure_exit_date"] = last_failure_date.date().isoformat()
        fields["failure_memory_micro_sizing_days_since_last_failure"] = int((asof_date - last_failure_date).days)
        if consecutive_failures >= min_failures:
            effective_multiplier = base_multiplier * configured_multiplier
            fields["failure_memory_micro_sizing_effective_multiplier"] = effective_multiplier
            fields["failure_memory_micro_sizing_applied"] = int(effective_multiplier > base_multiplier + 1e-12)
            fields["failure_memory_micro_sizing_reason"] = (
                "consecutive_failures_micro_sizing" if fields["failure_memory_micro_sizing_applied"] else "no_multiplier_lift"
            )
        else:
            fields["failure_memory_micro_sizing_reason"] = "below_failure_threshold"
        return fields

    def _oi_price_confirm_risk_restore_fields(
        self,
        *,
        history: pd.DataFrame,
        direction: str,
        entry_context: str,
        base_multiplier: float,
    ) -> dict[str, Any]:
        enabled = int(
            self.enable_oi_price_confirm_risk_restore
            and self._oi_price_confirm_risk_restore_context_applies(entry_context)
        )
        configured_multiplier = max(0.0, float(self.oi_price_confirm_risk_restore_multiplier or 0.0))
        base_multiplier = max(0.0, float(base_multiplier or 0.0))
        require_recent_sum_ratio = bool(self.oi_price_confirm_risk_restore_require_recent_sum_ratio)
        recent_sum_days = max(1, int(self.oi_price_confirm_risk_restore_recent_sum_days or 1))
        recent_sum_min_ratio = max(0.0, float(self.oi_price_confirm_risk_restore_recent_sum_min_ratio or 0.0))
        fields: dict[str, Any] = {
            "oi_price_confirm_risk_restore_enabled": enabled,
            "oi_price_confirm_risk_restore_applied": 0,
            "oi_price_confirm_risk_restore_reason": "disabled" if not enabled else "not_confirmed",
            "oi_price_confirm_risk_restore_base_multiplier": base_multiplier,
            "oi_price_confirm_risk_restore_multiplier": configured_multiplier,
            "oi_price_confirm_risk_restore_effective_multiplier": base_multiplier,
            "oi_price_confirm_recent_sum_ratio_required": int(require_recent_sum_ratio),
            "oi_price_confirm_recent_sum_days": recent_sum_days,
            "oi_price_confirm_recent_oi_sum": math.nan,
            "oi_price_confirm_prior_oi_sum": math.nan,
            "oi_price_confirm_recent_prior_oi_sum_ratio": math.nan,
            "oi_price_confirm_recent_sum_ratio_passed": int(not require_recent_sum_ratio),
            "oi_price_confirm_entry_close": math.nan,
            "oi_price_confirm_prev_close": math.nan,
            "oi_price_confirm_entry_oi": math.nan,
            "oi_price_confirm_prev_oi": math.nan,
            "oi_price_confirm_oi_up": 0,
            "oi_price_confirm_price_aligned": 0,
            "oi_price_confirm_passed": 0,
        }
        if not enabled:
            return fields

        if history is None or history.empty or len(history) < 2:
            fields["oi_price_confirm_risk_restore_reason"] = "insufficient_history"
            return fields
        if "close" not in history.columns or "open_interest" not in history.columns:
            fields["oi_price_confirm_risk_restore_reason"] = "missing_close_or_oi"
            return fields

        close = pd.to_numeric(history["close"], errors="coerce")
        open_interest = pd.to_numeric(history["open_interest"], errors="coerce")
        close0 = float(close.iloc[-1]) if len(close) else math.nan
        close1 = float(close.iloc[-2]) if len(close) >= 2 else math.nan
        oi0 = float(open_interest.iloc[-1]) if len(open_interest) else math.nan
        oi1 = float(open_interest.iloc[-2]) if len(open_interest) >= 2 else math.nan
        fields.update(
            {
                "oi_price_confirm_entry_close": close0,
                "oi_price_confirm_prev_close": close1,
                "oi_price_confirm_entry_oi": oi0,
                "oi_price_confirm_prev_oi": oi1,
            }
        )
        if not all(math.isfinite(value) for value in [close0, close1, oi0, oi1]) or oi1 <= 0.0:
            fields["oi_price_confirm_risk_restore_reason"] = "invalid_close_or_oi"
            return fields

        recent_sum_ratio_passed = True
        if require_recent_sum_ratio:
            required_history = recent_sum_days * 2
            if len(open_interest) < required_history:
                fields["oi_price_confirm_risk_restore_reason"] = "insufficient_recent_oi_sum_history"
                return fields
            prior_oi = open_interest.iloc[-required_history:-recent_sum_days]
            recent_oi = open_interest.iloc[-recent_sum_days:]
            prior_values = pd.to_numeric(prior_oi, errors="coerce").to_numpy(dtype=float)
            recent_values = pd.to_numeric(recent_oi, errors="coerce").to_numpy(dtype=float)
            if (
                len(prior_values) != recent_sum_days
                or len(recent_values) != recent_sum_days
                or not np.isfinite(prior_values).all()
                or not np.isfinite(recent_values).all()
            ):
                fields["oi_price_confirm_risk_restore_reason"] = "invalid_recent_oi_sum"
                return fields
            prior_sum = float(np.sum(prior_values))
            recent_sum = float(np.sum(recent_values))
            ratio = recent_sum / prior_sum if prior_sum > 0.0 else math.nan
            recent_sum_ratio_passed = bool(
                math.isfinite(ratio)
                and prior_sum > 0.0
                and recent_sum >= prior_sum * recent_sum_min_ratio
            )
            fields.update(
                {
                    "oi_price_confirm_recent_oi_sum": recent_sum,
                    "oi_price_confirm_prior_oi_sum": prior_sum,
                    "oi_price_confirm_recent_prior_oi_sum_ratio": ratio,
                    "oi_price_confirm_recent_sum_ratio_passed": int(recent_sum_ratio_passed),
                }
            )

        side = str(direction or "")
        price_aligned = close0 > close1 if side == "long" else close0 < close1 if side == "short" else False
        oi_up = oi0 > oi1
        passed = bool(price_aligned and oi_up and recent_sum_ratio_passed)
        effective_multiplier = max(base_multiplier, configured_multiplier) if passed else base_multiplier
        fields.update(
            {
                "oi_price_confirm_oi_up": int(oi_up),
                "oi_price_confirm_price_aligned": int(price_aligned),
                "oi_price_confirm_passed": int(passed),
                "oi_price_confirm_risk_restore_effective_multiplier": effective_multiplier,
                "oi_price_confirm_risk_restore_applied": int(effective_multiplier > base_multiplier + 1e-12),
                "oi_price_confirm_risk_restore_reason": (
                    "oi_price_confirm_restore"
                    if effective_multiplier > base_multiplier + 1e-12
                    else "confirmed_no_multiplier_lift"
                    if passed
                    else "recent_oi_sum_ratio_not_passed"
                    if price_aligned and oi_up and require_recent_sum_ratio and not recent_sum_ratio_passed
                    else "not_confirmed"
                ),
            }
        )
        return fields

    def _rollover_reopen_drawdown_guard_fields(self) -> dict[str, Any]:
        guard_enabled = int(bool(self.enable_rollover_reopen_drawdown_guard))
        max_drawdown_pct = max(0.0, float(self.rollover_reopen_max_portfolio_drawdown_pct or 0.0))
        current_drawdown_pct = max(0.0, float(self.portfolio_drawdown_pct or 0.0))
        passed = (not guard_enabled) or current_drawdown_pct <= max_drawdown_pct
        return {
            "rollover_reopen_drawdown_guard_enabled": guard_enabled,
            "rollover_reopen_drawdown_guard_passed": int(passed),
            "rollover_reopen_drawdown_guard_max_pct": max_drawdown_pct,
            "rollover_reopen_drawdown_guard_portfolio_drawdown_pct": current_drawdown_pct,
        }

    def _record_rollover_reopen_guard_skip(
        self,
        *,
        state: ProductState,
        old_contract: str,
        target_contract: str,
        old_direction: str,
        old_risk_mode: str,
        bar: BarData,
        guard_fields: dict[str, Any],
    ) -> None:
        self.rollover_reopen_guard_diagnostics.append(
            {
                "skip_index": len(self.rollover_reopen_guard_diagnostics) + 1,
                "datetime": bar.datetime,
                "date": bar.datetime.date(),
                "product_vt_symbol": state.product_vt_symbol,
                "old_contract_vt_symbol": old_contract,
                "target_contract_vt_symbol": target_contract,
                "direction": old_direction,
                "risk_mode": old_risk_mode,
                "skip_reason": "rollover_reopen_portfolio_drawdown_guard",
                "estimated_equity": float(self.estimated_equity or self.base_capital),
                "portfolio_equity_high_water": float(self.portfolio_equity_high_water or self.base_capital),
                "portfolio_drawdown_pct": float(
                    guard_fields.get("rollover_reopen_drawdown_guard_portfolio_drawdown_pct") or 0.0
                ),
                "rollover_reopen_max_portfolio_drawdown_pct": float(
                    guard_fields.get("rollover_reopen_drawdown_guard_max_pct") or 0.0
                ),
            }
        )

    def _record_rollover_shape_same_volume_diagnostic(
        self,
        *,
        state: ProductState,
        old_contract: str,
        target_contract: str,
        old_direction: str,
        old_risk_mode: str,
        bar: BarData,
        target_am_inited: bool,
        previous_volume: int,
        selected_volume: int,
        final_volume: int,
        status: str,
        reason: str,
        shape_snapshot: dict[str, Any],
    ) -> None:
        self.rollover_shape_same_volume_diagnostics.append(
            {
                "diagnostic_index": len(self.rollover_shape_same_volume_diagnostics) + 1,
                "datetime": bar.datetime,
                "date": bar.datetime.date(),
                "product_vt_symbol": state.product_vt_symbol,
                "old_contract_vt_symbol": old_contract,
                "target_contract_vt_symbol": target_contract,
                "direction": old_direction,
                "risk_mode": old_risk_mode,
                "target_am_inited": int(target_am_inited),
                "history_mode": str(shape_snapshot.get("history_mode") or ""),
                "history_source": str(shape_snapshot.get("history_source") or ""),
                "history_input_ready": int(shape_snapshot.get("history_input_ready") or 0),
                "history_input_reason": str(shape_snapshot.get("history_input_reason") or ""),
                "observed_bar_count": int(shape_snapshot.get("observed_bar_count") or 0),
                "required_bar_count": int(shape_snapshot.get("required_bar_count") or 0),
                "target_observed_bar_count": int(
                    shape_snapshot.get("target_observed_bar_count") or 0
                ),
                "old_contract_observed_bar_count": int(
                    shape_snapshot.get("old_contract_observed_bar_count") or 0
                ),
                "source_observed_bar_count": int(
                    shape_snapshot.get("source_observed_bar_count") or 0
                ),
                "roll_adjustment_ratio": float(
                    shape_snapshot.get("roll_adjustment_ratio", float("nan"))
                ),
                "target_bar_appended": int(shape_snapshot.get("target_bar_appended") or 0),
                "same_day_bar_ready": int(shape_snapshot.get("same_day_bar_ready") or 0),
                "market_data_ready": int(shape_snapshot.get("market_data_ready") or 0),
                "metadata_ready": int(shape_snapshot.get("metadata_ready") or 0),
                "target_contract_size": int(shape_snapshot.get("target_contract_size") or 0),
                "target_price_tick": float(
                    shape_snapshot.get("target_price_tick", float("nan"))
                ),
                "target_margin_ratio": float(
                    shape_snapshot.get("target_margin_ratio", float("nan"))
                ),
                "bullish_alignment": int(shape_snapshot.get("bullish_alignment") or 0),
                "bearish_alignment": int(shape_snapshot.get("bearish_alignment") or 0),
                "macd_hist": float(shape_snapshot.get("macd_hist", float("nan"))),
                "previous_volume": int(previous_volume),
                "selected_volume_before_exact_gate": int(selected_volume),
                "final_volume": int(final_volume),
                "volume_policy": str(self.rollover_shape_volume_policy),
                "volume_outcome": (
                    "skipped"
                    if int(final_volume) <= 0
                    else "reduced"
                    if int(final_volume) < int(previous_volume)
                    else "full"
                ),
                "was_reduced": int(0 < int(final_volume) < int(previous_volume)),
                "status": status,
                "reason": reason,
            }
        )

    def _rollover_released_risk_snapshot(
        self,
        *,
        state: ProductState,
        old_contract: str,
        old_bar: BarData,
        risk_snapshot_includes_old_contract: bool,
    ) -> dict[str, Any]:
        cluster = self._risk_cluster_for_symbol(state.product_vt_symbol or old_contract)
        if not risk_snapshot_includes_old_contract:
            return {
                "rollover_old_contract_in_risk_snapshot": 0,
                "rollover_released_margin": 0.0,
                "rollover_released_cluster": cluster,
                "rollover_released_cluster_margin": 0.0,
                "rollover_released_cluster_unrealized_pnl": 0.0,
            }

        previous_volume = max(0, int(state.active_volume()))
        size = max(0, int(self.get_size(old_contract)))
        close_price = max(0.0, float(old_bar.close_price))
        margin_ratio = max(0.0, float(self._margin_ratio_for_symbol(old_contract)))
        released_margin = close_price * size * previous_volume * margin_ratio
        released_unrealized_pnl = 0.0
        for layer in state.layers:
            layer_volume = max(0, int(layer.volume))
            if layer.direction == "short":
                released_unrealized_pnl += (float(layer.entry_price) - close_price) * size * layer_volume
            else:
                released_unrealized_pnl += (close_price - float(layer.entry_price)) * size * layer_volume
        return {
            "rollover_old_contract_in_risk_snapshot": 1,
            "rollover_released_margin": float(max(0.0, released_margin)),
            "rollover_released_cluster": cluster,
            "rollover_released_cluster_margin": float(max(0.0, released_margin)) if cluster else 0.0,
            "rollover_released_cluster_unrealized_pnl": float(released_unrealized_pnl) if cluster else 0.0,
        }

    def _apply_rollover_released_risk_snapshot(self, snapshot: dict[str, Any]) -> None:
        released_margin = max(0.0, float(snapshot.get("rollover_released_margin") or 0.0))
        self.total_margin_in_use = max(0.0, float(self.total_margin_in_use or 0.0) - released_margin)

        cluster = str(snapshot.get("rollover_released_cluster") or "")
        if cluster:
            released_cluster_margin = max(
                0.0,
                float(snapshot.get("rollover_released_cluster_margin") or 0.0),
            )
            remaining_cluster_margin = max(
                0.0,
                float(self.cluster_margin_usage.get(cluster, 0.0) or 0.0) - released_cluster_margin,
            )
            if remaining_cluster_margin > 0.0:
                self.cluster_margin_usage[cluster] = remaining_cluster_margin
            else:
                self.cluster_margin_usage.pop(cluster, None)

            released_cluster_pnl = float(
                snapshot.get("rollover_released_cluster_unrealized_pnl") or 0.0
            )
            remaining_cluster_pnl = float(
                self.cluster_unrealized_pnl.get(cluster, 0.0) or 0.0
            ) - released_cluster_pnl
            if abs(remaining_cluster_pnl) > 1e-9:
                self.cluster_unrealized_pnl[cluster] = remaining_cluster_pnl
            else:
                self.cluster_unrealized_pnl.pop(cluster, None)

        self.risk_cluster_margin_in_use = max(self.cluster_margin_usage.values(), default=0.0)
        self.risk_cluster_unrealized_loss_in_use = max(
            (max(0.0, -float(value)) for value in self.cluster_unrealized_pnl.values()),
            default=0.0,
        )

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

    def _incremental_margin_budget_gate_context_applies(self, entry_context: str) -> bool:
        contexts = {
            item.strip()
            for item in str(self.incremental_margin_budget_gate_entry_contexts or "").replace(";", ",").split(",")
            if item.strip()
        }
        return "*" in contexts or str(entry_context or "").strip() in contexts

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
            and self._incremental_margin_budget_gate_context_applies(entry_context)
            and int(openable_candidate_count) >= min_candidates
        )
        reserved_margin_before = self._reserved_margin_in_use()
        selected_volume_before = max(0, int(selected_volume))
        planned_margin_before = max(0.0, float(margin_per_contract) * selected_volume_before)
        budget = self._incremental_margin_budget_gate_allowed_capital(entry_context)
        projected_before = reserved_margin_before + max(0.0, float(planned_intraday_margin_before))
        projected_after_before = projected_before + planned_margin_before
        reduce_volume_enabled = int(
            gate_enabled
            and self.incremental_margin_budget_gate_reduce_volume
            and not protected_by_rank
        )
        remaining_budget = max(0.0, budget - projected_before)
        if gate_enabled and float(margin_per_contract) > 0.0:
            max_affordable_volume = int(remaining_budget // float(margin_per_contract))
        else:
            max_affordable_volume = selected_volume_before
        selected_volume_after = selected_volume_before
        if reduce_volume_enabled and projected_after_before > budget + 1e-9:
            selected_volume_after = min(selected_volume_before, max(0, max_affordable_volume))
            if 0 < selected_volume_after < self.min_position_size:
                selected_volume_after = 0
        planned_margin_after = max(0.0, float(margin_per_contract) * max(0, int(selected_volume_after)))
        projected_after = projected_before + planned_margin_after
        passed = (not gate_enabled) or bool(protected_by_rank) or projected_after <= budget + 1e-9
        return {
            "incremental_margin_budget_gate_enabled": gate_enabled,
            "incremental_margin_budget_gate_reduce_volume_enabled": reduce_volume_enabled,
            "incremental_margin_budget_gate_min_openable_candidates": min_candidates,
            "incremental_margin_budget_gate_openable_candidate_count": int(openable_candidate_count),
            "incremental_margin_budget_gate_protected_selection_rank": protected_rank,
            "incremental_margin_budget_gate_candidate_selection_rank": selection_rank,
            "incremental_margin_budget_gate_protected_by_rank": protected_by_rank,
            "incremental_margin_budget_gate_budget": budget,
            "incremental_margin_budget_gate_remaining_budget": remaining_budget,
            "incremental_margin_budget_gate_max_affordable_volume": max_affordable_volume,
            "incremental_margin_budget_gate_selected_volume_before": selected_volume_before,
            "incremental_margin_budget_gate_selected_volume_after": selected_volume_after,
            "incremental_margin_budget_gate_volume_reduced": int(selected_volume_after < selected_volume_before),
            "incremental_margin_budget_gate_reserved_margin_before": reserved_margin_before,
            "incremental_margin_budget_gate_planned_intraday_margin_before": max(
                0.0,
                float(planned_intraday_margin_before),
            ),
            "incremental_margin_budget_gate_planned_entry_margin_before": planned_margin_before,
            "incremental_margin_budget_gate_planned_entry_margin": planned_margin_after,
            "incremental_margin_budget_gate_projected_margin_before": projected_before,
            "incremental_margin_budget_gate_projected_margin_after_before_reduction": projected_after_before,
            "incremental_margin_budget_gate_projected_margin_after": projected_after,
            "incremental_margin_budget_gate_passed": int(passed),
        }

    def _incremental_margin_budget_gate_adjust_volume(
        self,
        *,
        selected_volume: int,
        margin_per_contract: float,
        entry_context: str,
        planned_intraday_margin_before: float = 0.0,
        openable_candidate_count: int = 1,
        selection_pairwise_rank: int = 0,
    ) -> tuple[int, dict[str, Any]]:
        gate_fields = self._incremental_margin_budget_gate_fields(
            planned_intraday_margin_before=planned_intraday_margin_before,
            selected_volume=max(0, int(selected_volume)),
            margin_per_contract=float(margin_per_contract or 0.0),
            openable_candidate_count=openable_candidate_count,
            selection_pairwise_rank=selection_pairwise_rank,
            entry_context=entry_context,
        )
        adjusted_volume = max(
            0,
            int(gate_fields.get("incremental_margin_budget_gate_selected_volume_after", selected_volume) or 0),
        )
        if int(gate_fields["incremental_margin_budget_gate_enabled"]) and not int(
            gate_fields["incremental_margin_budget_gate_passed"]
        ):
            adjusted_volume = 0
        return adjusted_volume, gate_fields

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
        projected_margin = max(0.0, margin_per_contract * max(0, int(volume)))
        self.pending_margin_reservation += projected_margin
        cluster = self._risk_cluster_for_symbol(product_vt_symbol)
        if cluster:
            self.pending_cluster_margin_reservation[cluster] = (
                self.pending_cluster_margin_reservation.get(cluster, 0.0) + projected_margin
            )
        if count_active_position:
            self.pending_active_products.add(product_vt_symbol)

    def _reserve_intrabar_margin(self, vt_symbol: str, volume: int, price: float) -> None:
        margin_ratio = self._margin_ratio_for_symbol(vt_symbol)
        projected_margin = float(price) * self.get_size(vt_symbol) * max(0, int(volume)) * margin_ratio
        projected_margin = max(0.0, projected_margin)
        self.pending_margin_reservation += projected_margin
        cluster = self._risk_cluster_for_symbol(vt_symbol)
        if cluster:
            self.pending_cluster_margin_reservation[cluster] = (
                self.pending_cluster_margin_reservation.get(cluster, 0.0) + projected_margin
            )

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

    def _estimate_margin_usage_by_cluster(self, bars: dict[str, BarData]) -> dict[str, float]:
        usage: dict[str, float] = {}
        for state in self.states.values():
            if not state.contract_vt_symbol or not state.layers:
                continue
            bar: BarData | None = bars.get(state.contract_vt_symbol)
            if not bar:
                continue
            cluster: str = self._risk_cluster_for_symbol(state.product_vt_symbol or state.contract_vt_symbol)
            if not cluster:
                continue
            size: int = self.get_size(state.contract_vt_symbol)
            close_price: float = float(bar.close_price)
            margin_ratio: float = self._margin_ratio_for_symbol(state.contract_vt_symbol)
            margin: float = abs(close_price * size * state.active_volume() * margin_ratio)
            usage[cluster] = usage.get(cluster, 0.0) + margin
        return usage

    def _estimate_unrealized_pnl_by_cluster(self, bars: dict[str, BarData]) -> dict[str, float]:
        pnl_by_cluster: dict[str, float] = {}
        for state in self.states.values():
            if not state.contract_vt_symbol or not state.layers:
                continue
            bar: BarData | None = bars.get(state.contract_vt_symbol)
            if not bar:
                continue
            cluster: str = self._risk_cluster_for_symbol(state.product_vt_symbol or state.contract_vt_symbol)
            if not cluster:
                continue
            size: int = self.get_size(state.contract_vt_symbol)
            close_price: float = float(bar.close_price)
            state_pnl: float = 0.0
            for layer in state.layers:
                volume = max(0, int(layer.volume))
                if state.direction == "short":
                    state_pnl += (float(layer.entry_price) - close_price) * size * volume
                else:
                    state_pnl += (close_price - float(layer.entry_price)) * size * volume
            pnl_by_cluster[cluster] = pnl_by_cluster.get(cluster, 0.0) + state_pnl
        return pnl_by_cluster

    def _sizing_equity_soft_cap_release_weight(self, value: float, start: float, full: float) -> float:
        start = max(0.0, float(start))
        full = max(start + 1e-9, float(full))
        value = max(0.0, float(value))
        if value <= start:
            return 1.0
        if value >= full:
            return 0.0
        return self._clip01((full - value) / max(1e-9, full - start))

    def _sizing_equity_snapshot(self) -> dict[str, float | int]:
        """Return the active sizing cap and diagnostics for static or dynamic cap modes."""
        equity: float = max(0.0, float(self.estimated_equity or self.base_capital))
        static_cap: float = float(self.sizing_equity_cap or 0.0)
        static_effective_cap: float = equity if static_cap <= 0 else min(equity, static_cap)

        base_cap: float = float(self.dynamic_sizing_equity_soft_cap_base or 0.0)
        if base_cap <= 0:
            base_cap = static_cap if static_cap > 0 else equity
        max_cap: float = float(self.dynamic_sizing_equity_soft_cap_max or 0.0)
        if max_cap <= 0:
            max_cap = equity
        max_cap = max(base_cap, max_cap)
        participation: float = self._clip01(float(self.dynamic_sizing_equity_soft_cap_participation or 0.0))

        reserved_margin: float = self._reserved_margin_in_use()
        margin_pressure_ratio: float = reserved_margin / equity if equity > 0 else 0.0
        drawdown_ratio: float = max(0.0, float(self.portfolio_drawdown_pct or 0.0))
        margin_weight = self._sizing_equity_soft_cap_release_weight(
            margin_pressure_ratio,
            float(self.dynamic_sizing_equity_soft_cap_margin_start_ratio),
            float(self.dynamic_sizing_equity_soft_cap_margin_full_ratio),
        )
        drawdown_weight = self._sizing_equity_soft_cap_release_weight(
            drawdown_ratio,
            float(self.dynamic_sizing_equity_soft_cap_drawdown_start_ratio),
            float(self.dynamic_sizing_equity_soft_cap_drawdown_full_ratio),
        )
        release_weight = min(margin_weight, drawdown_weight)

        raw_dynamic_cap: float = min(max_cap, base_cap + max(0.0, equity - base_cap) * participation)
        dynamic_effective_cap: float = base_cap + max(0.0, raw_dynamic_cap - base_cap) * release_weight
        dynamic_sizing_equity: float = min(equity, dynamic_effective_cap)

        enabled = int(bool(self.enable_dynamic_sizing_equity_soft_cap))
        sizing_equity = dynamic_sizing_equity if enabled else static_effective_cap
        effective_cap = dynamic_effective_cap if enabled else (static_cap if static_cap > 0 else equity)

        layered_enabled = int(bool(self.enable_layered_profit_lock_sizing))
        layered_base: float = max(0.0, float(self.layered_profit_lock_base_equity or 0.0))
        layered_start: float = max(layered_base, float(self.layered_profit_lock_start_equity or 0.0))
        layered_lock_ratio: float = self._clip01(float(self.layered_profit_lock_ratio or 0.0))
        layered_high_water: float = max(float(self.portfolio_equity_high_water or self.base_capital), equity, float(self.base_capital))
        layered_tiers: list[tuple[float, float]] = [(layered_start, layered_lock_ratio)]
        for raw_tier in str(self.layered_profit_lock_tiers or "").split(","):
            raw_tier = raw_tier.strip()
            if not raw_tier or ":" not in raw_tier:
                continue
            threshold_text, ratio_text = raw_tier.split(":", 1)
            try:
                threshold = max(layered_start, float(threshold_text.strip()))
                ratio = self._clip01(float(ratio_text.strip()))
            except ValueError:
                continue
            layered_tiers.append((threshold, ratio))
        layered_tiers = sorted({threshold: ratio for threshold, ratio in layered_tiers}.items())
        layered_locked_equity: float = 0.0
        for index, (threshold, ratio) in enumerate(layered_tiers):
            next_threshold = layered_tiers[index + 1][0] if index + 1 < len(layered_tiers) else float("inf")
            lockable_amount = max(0.0, min(layered_high_water, next_threshold) - threshold)
            layered_locked_equity += lockable_amount * ratio
        layered_raw_sizing_equity: float = max(0.0, equity - layered_locked_equity)
        layered_floor: float = min(equity, layered_base)
        layered_sizing_equity: float = min(equity, max(layered_floor, layered_raw_sizing_equity))
        if layered_enabled:
            sizing_equity = min(sizing_equity, layered_sizing_equity)
            effective_cap = min(effective_cap, layered_sizing_equity)

        return {
            "sizing_equity": sizing_equity,
            "static_sizing_equity_cap": static_cap,
            "effective_sizing_equity_cap": effective_cap,
            "dynamic_sizing_equity_soft_cap_enabled": enabled,
            "dynamic_sizing_equity_soft_cap_base": base_cap,
            "dynamic_sizing_equity_soft_cap_max": max_cap,
            "dynamic_sizing_equity_soft_cap_participation": participation,
            "dynamic_sizing_equity_soft_cap_raw_cap": raw_dynamic_cap,
            "dynamic_sizing_equity_soft_cap_margin_pressure_ratio": margin_pressure_ratio,
            "dynamic_sizing_equity_soft_cap_drawdown_ratio": drawdown_ratio,
            "dynamic_sizing_equity_soft_cap_margin_weight": margin_weight,
            "dynamic_sizing_equity_soft_cap_drawdown_weight": drawdown_weight,
            "dynamic_sizing_equity_soft_cap_release_weight": release_weight,
            "layered_profit_lock_sizing_enabled": layered_enabled,
            "layered_profit_lock_base_equity": layered_base,
            "layered_profit_lock_start_equity": layered_start,
            "layered_profit_lock_ratio": layered_lock_ratio,
            "layered_profit_lock_high_water": layered_high_water,
            "layered_profit_lock_locked_equity": layered_locked_equity,
            "layered_profit_lock_sizing_equity": layered_sizing_equity,
            "layered_profit_lock_tier_count": len(layered_tiers),
        }

    def _sizing_equity(self) -> float:
        """Cap sizing equity while still de-risking on drawdown; non-positive cap disables the ceiling."""
        return float(self._sizing_equity_snapshot()["sizing_equity"])

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

    def _directional_edge_close_position(self, history: pd.DataFrame) -> float:
        period = max(2, int(self.streak_entry_structure_recovery_directional_edge_period or 60))
        min_required = max(20, period // 2)
        if history is None or history.empty or len(history) < min_required:
            return float("nan")
        recent = history.tail(period)
        high = pd.to_numeric(recent["high"], errors="coerce")
        low = pd.to_numeric(recent["low"], errors="coerce")
        close = pd.to_numeric(recent["close"], errors="coerce")
        high_value = float(high.max()) if high.notna().any() else float("nan")
        low_value = float(low.min()) if low.notna().any() else float("nan")
        close_value = float(close.iloc[-1]) if not close.empty and pd.notna(close.iloc[-1]) else float("nan")
        if not (math.isfinite(high_value) and math.isfinite(low_value) and math.isfinite(close_value)):
            return float("nan")
        width = high_value - low_value
        if width <= 0.0:
            return float("nan")
        return (close_value - low_value) / width

    def _entry_structure_recovery_fields(
        self,
        *,
        signal: str,
        direction: str,
        entry_context: str,
        rsi_value: float | None,
        history: pd.DataFrame,
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
            "streak_entry_structure_risk_recovery_directional_edge_enabled": int(
                self.streak_entry_structure_recovery_require_directional_edge60
            ),
            "streak_entry_structure_risk_recovery_directional_edge_period": int(
                self.streak_entry_structure_recovery_directional_edge_period or 0
            ),
            "streak_entry_structure_risk_recovery_directional_edge_close_position": float("nan"),
            "streak_entry_structure_risk_recovery_directional_edge_long_min": float(
                self.streak_entry_structure_recovery_long_close_position_min
            ),
            "streak_entry_structure_risk_recovery_directional_edge_short_max": float(
                self.streak_entry_structure_recovery_short_close_position_max
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

        if bool(self.streak_entry_structure_recovery_require_directional_edge60):
            close_position = self._directional_edge_close_position(history)
            fields["streak_entry_structure_risk_recovery_directional_edge_close_position"] = close_position
            if not math.isfinite(close_position):
                fields["streak_entry_structure_risk_recovery_reason"] = "directional_edge_unavailable"
                return fields
            long_min = float(self.streak_entry_structure_recovery_long_close_position_min)
            short_max = float(self.streak_entry_structure_recovery_short_close_position_max)
            directional_edge_confirmed = (
                (direction == "long" and close_position >= long_min)
                or (direction == "short" and close_position <= short_max)
            )
            if not directional_edge_confirmed:
                fields["streak_entry_structure_risk_recovery_reason"] = "directional_edge_not_confirmed"
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

    def _recovery_sleeve_fields(
        self,
        sizing: dict[str, Any],
        bar: BarData,
        entry_context: str,
        direction: str,
        history: pd.DataFrame,
    ) -> dict[str, Any]:
        selected_before = int(sizing.get("selected_volume") or 0)
        fields: dict[str, Any] = {
            "recovery_sleeve_enabled": int(self.enable_recovery_sleeve),
            "recovery_sleeve_applied": 0,
            "recovery_sleeve_normal_risk_bypass_enabled": int(
                bool(self.recovery_sleeve_normal_risk_bypass_require_directional_edge60)
                or float(self.recovery_sleeve_normal_risk_bypass_max_portfolio_drawdown_pct or -1.0) >= 0.0
            ),
            "recovery_sleeve_normal_risk_bypassed": 0,
            "recovery_sleeve_reason": "",
            "recovery_sleeve_selected_volume_before": selected_before,
            "recovery_sleeve_selected_volume_after": selected_before,
            "recovery_sleeve_broker_margin_multiplier": float(self.recovery_sleeve_broker_margin_multiplier),
            "recovery_sleeve_single_contract_broker_margin_to_equity": 0.0,
            "recovery_sleeve_max_single_contract_broker_margin_to_equity": float(
                self.recovery_sleeve_max_single_contract_broker_margin_to_equity
            ),
            "recovery_sleeve_cooldown_days": int(self.recovery_sleeve_cooldown_days or 0),
        }
        if not self.enable_recovery_sleeve:
            return fields

        if entry_context != "flat_entry":
            fields["recovery_sleeve_reason"] = "not_flat_entry"
            return fields

        if int(sizing.get("streak_entry_structure_risk_recovery_applied") or 0) != 1:
            fields["recovery_sleeve_reason"] = str(
                sizing.get("streak_entry_structure_risk_recovery_reason") or "structure_recovery_not_applied"
            )
            return fields

        base_multiplier = float(sizing.get("streak_entry_structure_risk_recovery_base_multiplier") or 0.0)
        if base_multiplier > float(self.recovery_sleeve_base_multiplier_max or 0.0):
            sizing["selected_volume"] = 0
            fields["recovery_sleeve_reason"] = "not_throttle_floor"
            fields["recovery_sleeve_selected_volume_after"] = 0
            return fields

        candidate_date = pd.Timestamp(bar.datetime).tz_localize(None).normalize()
        last_open_date = self._recovery_sleeve_last_open_timestamp
        if last_open_date is not None:
            days_since = int((candidate_date - pd.Timestamp(last_open_date)).days)
            if days_since <= int(self.recovery_sleeve_cooldown_days or 0):
                sizing["selected_volume"] = 0
                fields["recovery_sleeve_reason"] = "cooldown"
                fields["recovery_sleeve_selected_volume_after"] = 0
                return fields

        if selected_before <= 0:
            fields["recovery_sleeve_reason"] = "zero_after_structure_recovery"
            return fields

        bypass_max_drawdown = float(self.recovery_sleeve_normal_risk_bypass_max_portfolio_drawdown_pct or -1.0)
        if int(fields["recovery_sleeve_normal_risk_bypass_enabled"]):
            drawdown_passed = bypass_max_drawdown < 0.0 or float(self.portfolio_drawdown_pct or 0.0) <= bypass_max_drawdown
            directional_passed = True
            if bool(self.recovery_sleeve_normal_risk_bypass_require_directional_edge60):
                close_position = self._directional_edge_close_position(history)
                long_min = float(self.streak_entry_structure_recovery_long_close_position_min)
                short_max = float(self.streak_entry_structure_recovery_short_close_position_max)
                directional_passed = (
                    math.isfinite(close_position)
                    and (
                        (direction == "long" and close_position >= long_min)
                        or (direction == "short" and close_position <= short_max)
                    )
                )
                fields["streak_entry_structure_risk_recovery_directional_edge_close_position"] = close_position
            if drawdown_passed and directional_passed:
                fields["recovery_sleeve_normal_risk_bypassed"] = 1
                fields["recovery_sleeve_reason"] = "structure_recovery_normal_risk_bypass"
                fields["recovery_sleeve_selected_volume_after"] = selected_before
                return fields

        sizing_equity = float(
            sizing.get("sizing_equity")
            or sizing.get("effective_sizing_equity_cap")
            or self.estimated_equity
            or self.base_capital
            or 0.0
        )
        margin_per_contract = float(sizing.get("margin_per_contract") or 0.0)
        broker_single_ratio = (
            margin_per_contract * float(self.recovery_sleeve_broker_margin_multiplier or 0.0) / sizing_equity
            if sizing_equity > 0.0 and margin_per_contract > 0.0
            else 999.0
        )
        fields["recovery_sleeve_single_contract_broker_margin_to_equity"] = broker_single_ratio
        if broker_single_ratio > float(self.recovery_sleeve_max_single_contract_broker_margin_to_equity or 0.0):
            sizing["selected_volume"] = 0
            fields["recovery_sleeve_reason"] = "single_contract_margin_too_high"
            fields["recovery_sleeve_selected_volume_after"] = 0
            return fields

        selected_after = max(1, int(self.recovery_sleeve_volume or 1))
        sizing["selected_volume"] = selected_after
        fields["recovery_sleeve_applied"] = 1
        fields["recovery_sleeve_reason"] = "structure_recovery_one_lot"
        fields["recovery_sleeve_selected_volume_after"] = selected_after
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
        ai_allowed, ai_product_pool_snapshot = self._ai_product_pool_entry_allowed(
            context.product_vt_symbol,
            pd.Timestamp(context.target_bar.datetime).normalize(),
        )
        sizing.update(ai_product_pool_snapshot)
        supply_demand_snapshot = self._supply_demand_headwind_snapshot(
            context.product_vt_symbol,
            direction,
            pd.Timestamp(context.target_bar.datetime),
        )
        sizing.update(supply_demand_snapshot)
        if int(supply_demand_snapshot.get("supply_demand_headwind_enabled", 0) or 0):
            headwind_weight = self._clip01(float(supply_demand_snapshot.get("supply_demand_headwind_weight", 1.0)))
            if headwind_weight < 1.0:
                volume_before = max(0, int(sizing.get("selected_volume") or volume))
                volume_after = int(math.floor(volume_before * headwind_weight))
                if 0 < volume_after < self.min_position_size:
                    volume_after = 0
                sizing["supply_demand_headwind_selected_volume_before"] = volume_before
                sizing["supply_demand_headwind_selected_volume_after"] = max(0, volume_after)
                sizing["selected_volume"] = max(0, volume_after)
                volume = max(0, volume_after)
                native_openable = self._is_native_openable_candidate(signal, direction, volume)
        cooldown_fields = self._product_direction_failure_cooldown_fields(
            product_vt_symbol=context.product_vt_symbol,
            direction=direction,
            entry_context="flat_entry",
            asof=pd.Timestamp(context.target_bar.datetime).normalize(),
        )
        sizing.update(cooldown_fields)
        if int(cooldown_fields["product_direction_failure_cooldown_blocked"]):
            volume_before_cooldown = max(0, int(sizing.get("selected_volume") or volume))
            sizing["product_direction_failure_cooldown_selected_volume_before"] = volume_before_cooldown
            sizing["product_direction_failure_cooldown_selected_volume_after"] = 0
            sizing["selected_volume"] = 0
            volume = 0
            native_openable = False
            skip_reason = "product_direction_failure_cooldown"
            self.product_direction_failure_cooldown_count += 1
            self.product_direction_failure_cooldown_events.append(
                {
                    "date": pd.Timestamp(context.target_bar.datetime).normalize(),
                    "product_vt_symbol": context.product_vt_symbol,
                    "contract_vt_symbol": context.target_contract,
                    "direction": direction,
                    "signal": signal,
                    "entry_context": "flat_entry",
                    "consecutive_failures": int(
                        cooldown_fields["product_direction_failure_cooldown_consecutive_failures"]
                    ),
                    "last_failure_exit_date": cooldown_fields["product_direction_failure_cooldown_last_failure_exit_date"],
                    "cooldown_until": cooldown_fields["product_direction_failure_cooldown_until"],
                    "selected_volume_before": volume_before_cooldown,
                }
            )
        if direction == "long" and not self.long_entry_enabled:
            skip_reason = "long_entry_disabled"
        elif direction == "short" and not self.short_entry_enabled:
            skip_reason = "short_entry_disabled"
        elif direction == "short" and not self._can_open_short_signal(signal):
            skip_reason = "short_signal_rejected"
        elif volume <= 0:
            if skip_reason:
                pass
            elif str(supply_demand_snapshot.get("supply_demand_headwind_reason", "")) == "strong_headwind":
                skip_reason = "supply_demand_headwind_blocked"
            else:
                skip_reason = "sizing_zero_volume"
        elif not ai_allowed:
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

    def _ai_path_damage_discount_weight(self, probability: float) -> float:
        start = self._clip01(float(self.ai_path_damage_discount_probability_start or 0.0))
        full = self._clip01(float(self.ai_path_damage_discount_probability_full or 0.0))
        if full <= start:
            full = min(1.0, start + 1e-9)
        floor = self._clip01(float(self.ai_path_damage_discount_weight_floor or 0.0))
        probability = self._clip01(float(probability))
        if probability <= start:
            return 1.0
        if probability >= full:
            return floor
        progress = (probability - start) / max(1e-9, full - start)
        return 1.0 - (1.0 - floor) * progress

    def _ai_path_damage_discount_start_timestamp(self) -> pd.Timestamp | None:
        start_text = str(self.ai_path_damage_discount_start_date or "").strip()
        if not start_text:
            return None
        try:
            return pd.Timestamp(start_text).normalize()
        except (TypeError, ValueError):
            return None

    def _apply_ai_path_damage_risk_discount(self, candidate_plans: list[dict[str, Any]]) -> None:
        if not self.enable_ai_path_damage_risk_discount:
            return
        if not self.ai_path_damage_runtime:
            return

        scorable_plans = [
            plan
            for plan in candidate_plans
            if plan["native_openable"] and int(plan["sizing"].get("selected_volume") or plan.get("volume") or 0) > 0
        ]
        if not scorable_plans:
            return

        start_timestamp = self._ai_path_damage_discount_start_timestamp()
        runtime_rows: list[dict[str, Any]] = []
        plan_by_sample_id: dict[str, dict[str, Any]] = {}
        cross_section_count = len(scorable_plans)
        for order_index, plan in enumerate(scorable_plans, start=1):
            sizing = dict(plan["sizing"])
            target_bar: BarData | None = plan.get("target_bar")
            candidate_date = (
                pd.Timestamp(target_bar.datetime).tz_localize(None).normalize()
                if target_bar is not None
                else pd.Timestamp.min
            )
            base_volume = max(0, int(sizing.get("selected_volume") or plan.get("volume") or 0))
            sizing.update(
                {
                    "ai_path_damage_enabled": 1,
                    "ai_path_damage_model_tag": self.ai_path_damage_runtime.model_tag,
                    "ai_path_damage_probability": 0.0,
                    "ai_path_damage_discount_weight": 1.0,
                    "ai_path_damage_discount_applied": 0,
                    "ai_path_damage_feature_available": 0,
                    "ai_path_damage_selected_volume_before": base_volume,
                    "ai_path_damage_selected_volume_after": base_volume,
                }
            )
            plan["sizing"] = sizing
            if start_timestamp is not None and candidate_date < start_timestamp:
                continue

            estimated_equity = float(self.estimated_equity or self.base_capital)
            runtime_row = build_path_damage_runtime_feature_row(
                history=plan["history"],
                contract_vt_symbol=str(plan.get("target_contract", "")),
                candidate_date=candidate_date,
                direction=str(plan["direction"]),
                signal=str(plan["signal"]),
                risk_mode=str(sizing.get("risk_mode", plan["signal_data"].get("risk_mode", "regular"))),
                risk_ratio=float(sizing.get("risk_ratio") or 0.0),
                risk_multiplier=float(sizing.get("risk_multiplier") or self._current_streak_multiplier()),
                active_positions_before=int(plan.get("active_positions_before") or 0),
                remaining_position_slots=int(plan.get("remaining_position_slots") or 0),
                loss_streak=int(self.loss_streak),
                estimated_equity=estimated_equity,
                margin_per_contract=float(sizing.get("margin_per_contract") or 0.0),
                risk_amount=float(sizing.get("risk_amount") or 0.0),
                allowed_capital=float(sizing.get("allowed_capital") or 0.0),
                single_trade_capital_limit=float(sizing.get("single_trade_capital_limit") or 0.0),
                feature_candidate_cross_section_count_1d=cross_section_count,
            )
            if not runtime_row:
                continue
            sample_id = f"path_damage_runtime_{order_index}_{plan['product_vt_symbol']}"
            runtime_row.update(
                {
                    "sample_id": sample_id,
                    "product_vt_symbol": plan["product_vt_symbol"],
                }
            )
            runtime_rows.append(runtime_row)
            plan_by_sample_id[sample_id] = plan

        if not runtime_rows:
            return

        scored_rows = self.ai_path_damage_runtime.score_candidate_pool(runtime_rows)
        for scored_row in scored_rows:
            plan = plan_by_sample_id.get(str(scored_row.get("sample_id", "")))
            if not plan:
                continue
            sizing = dict(plan["sizing"])
            base_volume = max(0, int(sizing.get("selected_volume") or plan.get("volume") or 0))
            probability = float(scored_row.get(PATH_DAMAGE_PREDICTION_COLUMN, 0.0) or 0.0)
            weight = self._ai_path_damage_discount_weight(probability)
            discounted_volume = int(round(base_volume * weight))
            if 0 < discounted_volume < self.min_position_size:
                discounted_volume = 0
            sizing.update(
                {
                    "ai_path_damage_probability": probability,
                    "ai_path_damage_discount_weight": weight,
                    "ai_path_damage_discount_applied": int(discounted_volume != base_volume),
                    "ai_path_damage_feature_available": 1,
                    "ai_path_damage_selected_volume_before": base_volume,
                    "ai_path_damage_selected_volume_after": max(0, discounted_volume),
                }
            )
            sizing["selected_volume"] = max(0, discounted_volume)
            plan["sizing"] = sizing
            plan["volume"] = max(0, discounted_volume)
            if discounted_volume <= 0:
                plan["native_openable"] = False
                plan["skip_reason"] = "ai_path_damage_risk_discount_zero_volume"

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
        self._apply_ai_path_damage_risk_discount(candidate_plans)

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
            selected_volume_before_gate = selected_volume
            selected_volume = max(
                0,
                int(gate_fields.get("incremental_margin_budget_gate_selected_volume_after", selected_volume) or 0),
            )
            sizing["selected_volume"] = selected_volume
            plan["active_positions_before"] = active_positions_before
            plan["remaining_position_slots"] = max(0, effective_max_positions - active_positions_before)
            plan["volume"] = selected_volume
            if selected_volume <= 0:
                plan["candidate_status"] = "skipped"
                if (
                    selected_volume_before_gate > 0
                    and int(gate_fields["incremental_margin_budget_gate_enabled"])
                    and int(gate_fields.get("incremental_margin_budget_gate_reduce_volume_enabled") or 0)
                ):
                    plan["skip_reason"] = "incremental_margin_budget_gate"
                else:
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
            if (
                plan.get("candidate_status") == "opened"
                and int(sizing.get("failure_memory_micro_sizing_applied") or 0)
            ):
                self.failure_memory_micro_sizing_count += 1

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

    def _apply_risk_cluster_heat_gate_to_volume(
        self,
        vt_symbol: str,
        selected_volume: int,
        margin_per_contract: float,
        entry_context: str,
    ) -> dict[str, Any]:
        cluster: str = self._risk_cluster_for_symbol(vt_symbol)
        enabled: int = int(
            bool(self.enable_risk_cluster_heat_gate)
            and self._risk_cluster_heat_gate_cluster_applies(cluster)
            and self._risk_cluster_heat_gate_context_applies(entry_context)
        )
        projected_margin: float = max(0.0, float(margin_per_contract or 0.0) * max(0, int(selected_volume)))
        heat_fields = self._risk_cluster_heat_pressure_fields(
            cluster,
            projected_margin=projected_margin,
            enabled=bool(enabled),
        )
        heat_pressure = float(heat_fields["risk_cluster_heat_pressure"])
        floor = self._clip01(float(self.risk_cluster_heat_gate_weight_floor or 0.0))
        weight = self._clip01(1.0 - (1.0 - floor) * heat_pressure) if enabled else 1.0

        selected_volume_before = max(0, int(selected_volume))
        selected_volume_after = int(math.floor(selected_volume_before * weight)) if enabled else selected_volume_before
        if 0 < selected_volume_after < self.min_position_size:
            selected_volume_after = 0
        return {
            "risk_cluster_heat_gate_enabled": enabled,
            "risk_cluster_heat_gate_cluster": cluster,
            "risk_cluster_heat_gate_entry_context": entry_context,
            "risk_cluster_heat_gate_weight": weight,
            "risk_cluster_heat_gate_pressure": heat_pressure if enabled else 0.0,
            "risk_cluster_heat_gate_drawdown_pressure": float(
                heat_fields["risk_cluster_heat_drawdown_pressure"]
            ),
            "risk_cluster_heat_gate_margin_pressure": float(heat_fields["risk_cluster_heat_margin_pressure"]),
            "risk_cluster_heat_gate_unrealized_loss_pressure": float(
                heat_fields["risk_cluster_heat_unrealized_loss_pressure"]
            ),
            "risk_cluster_heat_gate_margin_ratio": float(heat_fields["risk_cluster_heat_margin_ratio"]),
            "risk_cluster_heat_gate_unrealized_loss_ratio": float(
                heat_fields["risk_cluster_heat_unrealized_loss_ratio"]
            ),
            "risk_cluster_heat_gate_portfolio_drawdown_pct": float(
                heat_fields["risk_cluster_heat_portfolio_drawdown_pct"]
            ),
            "risk_cluster_heat_gate_selected_volume_before": selected_volume_before,
            "risk_cluster_heat_gate_selected_volume": max(0, selected_volume_after),
        }

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
            self.enable_portfolio_drawdown_gate
            and self._portfolio_drawdown_gate_context_applies(entry_context)
        )
        portfolio_drawdown_gate_weight = self._portfolio_drawdown_gate_weight(entry_context)
        if portfolio_drawdown_gate_enabled and apply_env_gate:
            selected_volume = int(math.floor(selected_volume * portfolio_drawdown_gate_weight))
            if 0 < selected_volume < self.min_position_size:
                selected_volume = 0

        portfolio_volatility_budget_enabled = int(
            self.enable_portfolio_volatility_budget
            and self._portfolio_volatility_budget_context_applies(entry_context)
        )
        portfolio_volatility_budget_weight = self._portfolio_volatility_budget_weight(entry_context)
        if portfolio_volatility_budget_enabled and apply_env_gate:
            selected_volume = int(math.floor(selected_volume * portfolio_volatility_budget_weight))
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
            "portfolio_volatility_budget_enabled": portfolio_volatility_budget_enabled,
            "portfolio_volatility_budget_weight": portfolio_volatility_budget_weight,
            "portfolio_volatility_budget_realized_annual_vol": float(
                self.portfolio_volatility_budget_realized_annual_vol or 0.0
            ),
            "portfolio_volatility_budget_lookback": int(self.portfolio_volatility_budget_lookback or 0),
            "portfolio_volatility_budget_target_annual_vol": float(
                self.portfolio_volatility_budget_target_annual_vol or 0.0
            ),
        }

    def _directional_30d_risk_boost_snapshot(
        self,
        direction: str,
        history: pd.DataFrame,
    ) -> dict[str, Any]:
        enabled = bool(self.enable_directional_30d_risk_boost)
        lookback = int(self.directional_30d_risk_boost_lookback or 0)
        configured_multiplier = float(self.directional_30d_risk_boost_multiplier or 0.0)
        nonconfirmation_multiplier = float(
            getattr(self, "directional_30d_risk_nonconfirmation_multiplier", 1.0) or 0.0
        )
        long_only = bool(getattr(self, "directional_30d_risk_adjust_long_only", False))
        require_volume_expansion = bool(
            getattr(self, "directional_30d_risk_boost_require_volume_expansion", False)
        )
        recent_volume_days = int(getattr(self, "directional_30d_volume_recent_days", 10) or 0)
        prior_volume_days = int(getattr(self, "directional_30d_volume_prior_days", 10) or 0)
        volume_ratio_threshold = float(
            getattr(self, "directional_30d_volume_ratio_threshold", 1.0)
        )
        low_volume_discount_enabled = bool(
            getattr(self, "enable_directional_30d_low_volume_risk_discount", False)
        )
        low_volume_ratio_threshold = float(
            getattr(self, "directional_30d_low_volume_ratio_threshold", 0.5)
        )
        low_volume_risk_multiplier = float(
            getattr(self, "directional_30d_low_volume_risk_multiplier", 0.5)
        )
        snapshot: dict[str, Any] = {
            "directional_30d_risk_boost_enabled": int(enabled),
            "directional_30d_risk_boost_lookback": lookback,
            "directional_30d_volume_confirmation_enabled": int(require_volume_expansion),
            "directional_30d_volume_recent_days": recent_volume_days,
            "directional_30d_volume_prior_days": prior_volume_days,
            "directional_30d_volume_ratio_threshold": volume_ratio_threshold,
            "directional_30d_low_volume_discount_enabled": int(low_volume_discount_enabled),
            "directional_30d_low_volume_ratio_threshold": low_volume_ratio_threshold,
            "directional_30d_low_volume_risk_multiplier": low_volume_risk_multiplier,
            "directional_30d_low_volume_discount_applied": 0,
            "directional_30d_recent_volume_sum": float("nan"),
            "directional_30d_prior_volume_sum": float("nan"),
            "directional_30d_volume_expanding": 0,
            "directional_30d_start_close": float("nan"),
            "directional_30d_end_close": float("nan"),
            "directional_30d_return": float("nan"),
            "directional_30d_risk_boost_aligned": 0,
            "directional_30d_risk_boost_applied": 0,
            "directional_30d_risk_nonconfirmation_multiplier": nonconfirmation_multiplier,
            "directional_30d_risk_adjust_long_only": int(long_only),
            "directional_30d_risk_boost_multiplier": 1.0,
            "directional_30d_risk_boost_reason": "disabled",
        }
        if not enabled:
            return snapshot
        if long_only and direction == "short":
            snapshot["directional_30d_risk_boost_reason"] = "direction_excluded"
            return snapshot
        if (
            lookback <= 0
            or not np.isfinite(configured_multiplier)
            or configured_multiplier < 1.0
            or not np.isfinite(nonconfirmation_multiplier)
            or nonconfirmation_multiplier <= 0.0
            or nonconfirmation_multiplier > 1.0
            or (
                low_volume_discount_enabled
                and (
                    not np.isfinite(low_volume_ratio_threshold)
                    or low_volume_ratio_threshold <= 0.0
                    or not np.isfinite(low_volume_risk_multiplier)
                    or low_volume_risk_multiplier <= 0.0
                    or low_volume_risk_multiplier > 1.0
                )
            )
        ):
            snapshot["directional_30d_risk_boost_reason"] = "invalid_configuration"
            return snapshot
        snapshot["directional_30d_risk_boost_multiplier"] = nonconfirmation_multiplier

        close = pd.to_numeric(history.get("close", pd.Series(dtype="float64")), errors="coerce")
        required_count = lookback + 1
        if len(close) < required_count:
            snapshot["directional_30d_risk_boost_reason"] = "insufficient_history"
            return snapshot

        window = close.tail(required_count).to_numpy(dtype="float64")
        if not np.isfinite(window).all() or window[0] <= 0 or window[-1] <= 0:
            snapshot["directional_30d_risk_boost_reason"] = "invalid_history"
            return snapshot

        start_close = float(window[0])
        end_close = float(window[-1])
        directional_return = end_close / start_close - 1.0
        snapshot.update(
            {
                "directional_30d_start_close": start_close,
                "directional_30d_end_close": end_close,
                "directional_30d_return": directional_return,
            }
        )
        if direction == "long":
            aligned = directional_return > 0
        elif direction == "short":
            aligned = directional_return < 0
        else:
            snapshot["directional_30d_risk_boost_reason"] = "unsupported_direction"
            return snapshot

        if aligned:
            snapshot["directional_30d_risk_boost_aligned"] = 1
        if not require_volume_expansion:
            if not aligned:
                snapshot["directional_30d_risk_boost_reason"] = "direction_not_aligned"
                return snapshot
            snapshot.update(
                {
                    "directional_30d_risk_boost_applied": 1,
                    "directional_30d_risk_boost_multiplier": configured_multiplier,
                    "directional_30d_risk_boost_reason": "direction_aligned",
                }
            )
            return snapshot

        low_volume_direction_allowed = direction == "long" or not long_only
        if not aligned and not (
            low_volume_discount_enabled and low_volume_direction_allowed
        ):
            snapshot["directional_30d_risk_boost_reason"] = "direction_not_aligned"
            return snapshot

        if (
            recent_volume_days <= 0
            or prior_volume_days <= 0
            or not np.isfinite(volume_ratio_threshold)
            or volume_ratio_threshold <= 0
        ):
            snapshot["directional_30d_risk_boost_reason"] = "invalid_volume_configuration"
            return snapshot
        volume = pd.to_numeric(history.get("volume", pd.Series(dtype="float64")), errors="coerce")
        volume_required_count = recent_volume_days + prior_volume_days
        if len(volume) < volume_required_count:
            snapshot["directional_30d_risk_boost_reason"] = "insufficient_volume_history"
            return snapshot
        volume_window = volume.tail(volume_required_count).to_numpy(dtype="float64")
        if not np.isfinite(volume_window).all() or (volume_window < 0).any():
            snapshot["directional_30d_risk_boost_reason"] = "invalid_volume_history"
            return snapshot
        prior_volume_sum = float(volume_window[:prior_volume_days].sum())
        recent_volume_sum = float(volume_window[prior_volume_days:].sum())
        snapshot.update(
            {
                "directional_30d_prior_volume_sum": prior_volume_sum,
                "directional_30d_recent_volume_sum": recent_volume_sum,
            }
        )
        if prior_volume_sum <= 0 or recent_volume_sum <= 0:
            snapshot["directional_30d_risk_boost_reason"] = "invalid_volume_history"
            return snapshot
        if (
            low_volume_discount_enabled
            and low_volume_direction_allowed
            and recent_volume_sum < prior_volume_sum * low_volume_ratio_threshold
        ):
            snapshot.update(
                {
                    "directional_30d_low_volume_discount_applied": 1,
                    "directional_30d_risk_boost_multiplier": low_volume_risk_multiplier,
                    "directional_30d_risk_boost_reason": "low_volume_discount",
                }
            )
            return snapshot
        if not aligned:
            snapshot["directional_30d_risk_boost_reason"] = "direction_not_aligned"
            return snapshot
        if recent_volume_sum <= prior_volume_sum * volume_ratio_threshold:
            snapshot["directional_30d_risk_boost_reason"] = "volume_not_expanding"
            return snapshot
        snapshot.update(
            {
                "directional_30d_volume_expanding": 1,
                "directional_30d_risk_boost_applied": 1,
                "directional_30d_risk_boost_multiplier": configured_multiplier,
                "directional_30d_risk_boost_reason": "direction_and_volume_confirmed",
            }
        )
        return snapshot

    def _long_signal_atr_shock_snapshot(
        self,
        direction: str,
        history: pd.DataFrame,
        entry_context: str,
    ) -> dict[str, Any]:
        long_enabled = bool(self.enable_long_signal_atr_shock_filter)
        short_enabled = bool(self.enable_short_signal_atr_shock_filter)
        enabled = bool(long_enabled or short_enabled)
        period = int(self.long_signal_atr_shock_period or 0)
        multiplier = float(self.long_signal_atr_shock_multiplier or 0.0)
        contexts = {
            item.strip()
            for item in str(self.long_signal_atr_shock_entry_contexts or "").replace(";", ",").split(",")
            if item.strip()
        }
        snapshot: dict[str, Any] = {
            "long_signal_atr_shock_enabled": int(enabled),
            "short_signal_atr_shock_enabled": int(short_enabled),
            "long_signal_atr_shock_period": period,
            "long_signal_atr_shock_multiplier": multiplier,
            "long_signal_atr_shock_entry_context": entry_context,
            "long_signal_atr_shock_direction": direction,
            "long_signal_atr_shock_prior_close": float("nan"),
            "long_signal_atr_shock_signal_close": float("nan"),
            "long_signal_atr_shock_drop": float("nan"),
            "short_signal_atr_shock_rise": float("nan"),
            "signal_atr_shock_adverse_move": float("nan"),
            "signal_atr_shock_move_kind": "",
            "long_signal_atr_shock_atr": float("nan"),
            "long_signal_atr_shock_threshold": float("nan"),
            "long_signal_atr_shock_blocked": 0,
            "long_signal_atr_shock_reason": "disabled",
        }
        if not enabled:
            return snapshot
        if direction not in {"long", "short"}:
            snapshot["long_signal_atr_shock_reason"] = "direction_excluded"
            return snapshot
        direction_enabled = long_enabled if direction == "long" else short_enabled
        if not direction_enabled:
            snapshot["long_signal_atr_shock_reason"] = "direction_excluded"
            return snapshot
        if entry_context not in contexts:
            snapshot["long_signal_atr_shock_reason"] = "entry_context_excluded"
            return snapshot
        if period <= 0 or not np.isfinite(multiplier) or multiplier <= 0:
            snapshot["long_signal_atr_shock_reason"] = "invalid_configuration"
            return snapshot

        required_count = period + 2
        if history is None or len(history) < required_count:
            snapshot["long_signal_atr_shock_reason"] = "insufficient_prior_history"
            return snapshot
        if not {"close", "high", "low"}.issubset(history.columns):
            snapshot["long_signal_atr_shock_reason"] = "invalid_history"
            return snapshot
        window = history.tail(required_count)
        close = pd.to_numeric(window["close"], errors="coerce")
        high = pd.to_numeric(window["high"], errors="coerce")
        low = pd.to_numeric(window["low"], errors="coerce")
        if (
            len(close) != required_count
            or len(high) != required_count
            or len(low) != required_count
            or not np.isfinite(close.to_numpy(dtype="float64")).all()
            or not np.isfinite(high.to_numpy(dtype="float64")).all()
            or not np.isfinite(low.to_numpy(dtype="float64")).all()
            or (close <= 0).any()
            or (high <= 0).any()
            or (low <= 0).any()
            or (high < low).any()
        ):
            snapshot["long_signal_atr_shock_reason"] = "invalid_history"
            return snapshot

        completed = window.iloc[:-1]
        completed_close = pd.to_numeric(completed["close"], errors="coerce")
        completed_high = pd.to_numeric(completed["high"], errors="coerce")
        completed_low = pd.to_numeric(completed["low"], errors="coerce")
        previous_close = completed_close.shift(1)
        true_range = pd.concat(
            [
                (completed_high - completed_low).abs(),
                (completed_high - previous_close).abs(),
                (completed_low - previous_close).abs(),
            ],
            axis=1,
        ).max(axis=1).iloc[1:]
        if len(true_range) != period or not np.isfinite(true_range.to_numpy(dtype="float64")).all():
            snapshot["long_signal_atr_shock_reason"] = "invalid_prior_true_range"
            return snapshot

        atr = float(true_range.mean())
        prior_close = float(completed_close.iloc[-1])
        signal_close = float(close.iloc[-1])
        adverse_move = prior_close - signal_close if direction == "long" else signal_close - prior_close
        move_kind = "signal_day_drop" if direction == "long" else "signal_day_rise"
        threshold = multiplier * atr
        snapshot.update(
            {
                "long_signal_atr_shock_prior_close": prior_close,
                "long_signal_atr_shock_signal_close": signal_close,
                "long_signal_atr_shock_drop": adverse_move if direction == "long" else float("nan"),
                "short_signal_atr_shock_rise": adverse_move if direction == "short" else float("nan"),
                "signal_atr_shock_adverse_move": adverse_move,
                "signal_atr_shock_move_kind": move_kind,
                "long_signal_atr_shock_atr": atr,
                "long_signal_atr_shock_threshold": threshold,
            }
        )
        if atr <= 0:
            snapshot["long_signal_atr_shock_reason"] = "invalid_prior_atr"
            return snapshot
        reason_prefix = "drop" if direction == "long" else "rise"
        if adverse_move > threshold:
            snapshot["long_signal_atr_shock_blocked"] = 1
            snapshot["long_signal_atr_shock_reason"] = f"{reason_prefix}_strictly_above_threshold"
            return snapshot
        snapshot["long_signal_atr_shock_reason"] = f"{reason_prefix}_not_above_threshold"
        return snapshot

    def _apply_long_signal_atr_shock_to_sizing(
        self,
        sizing: dict[str, Any],
        snapshot: dict[str, Any],
        *,
        vt_symbol: str,
        direction: str,
        bar: BarData,
        entry_context: str,
    ) -> dict[str, Any]:
        selected_before = max(0, int(sizing.get("selected_volume") or 0))
        blocked = int(snapshot.get("long_signal_atr_shock_blocked") or 0)
        selected_after = 0 if blocked else selected_before
        sizing.update(snapshot)
        sizing["long_signal_atr_shock_selected_volume_before"] = selected_before
        sizing["long_signal_atr_shock_selected_volume_after"] = selected_after
        sizing["selected_volume"] = selected_after
        diagnostics = getattr(self, "long_signal_atr_shock_diagnostics", None)
        if diagnostics is not None and int(snapshot.get("long_signal_atr_shock_enabled") or 0):
            diagnostics.append(
                {
                    "diagnostic_index": len(diagnostics) + 1,
                    "datetime": bar.datetime,
                    "date": bar.datetime.date(),
                    "contract_vt_symbol": vt_symbol,
                    "product_vt_symbol": self.source_symbol_by_contract.get(
                        vt_symbol,
                        self._product_vt_symbol(vt_symbol),
                    ),
                    "direction": direction,
                    "entry_context": entry_context,
                    **snapshot,
                    "long_signal_atr_shock_selected_volume_before": selected_before,
                    "long_signal_atr_shock_selected_volume_after": selected_after,
                }
            )
        return sizing

    def _long_signal_range_atr_snapshot(
        self,
        direction: str,
        history: pd.DataFrame,
        entry_context: str,
    ) -> dict[str, Any]:
        long_enabled = bool(self.enable_long_signal_range_atr_filter)
        short_enabled = bool(
            getattr(self, "enable_short_signal_range_atr_filter", False)
        )
        enabled = bool(long_enabled or short_enabled)
        lookback = int(self.long_signal_range_lookback or 0)
        atr_period = int(self.long_signal_range_atr_period or 0)
        multiplier = float(self.long_signal_range_atr_multiplier or 0.0)
        require_recent_stall = bool(self.long_signal_range_require_recent_stall)
        recent_gain_lookback = int(self.long_signal_range_recent_gain_lookback or 0)
        recent_gain_atr_multiplier = float(
            self.long_signal_range_recent_gain_atr_multiplier or 0.0
        )
        enable_ordered_drawdown = bool(
            self.long_signal_range_enable_ordered_drawdown_filter
        )
        ordered_drawdown_atr_multiplier = float(
            getattr(self, "long_signal_range_ordered_drawdown_atr_multiplier", 3.0)
            or 0.0
        )
        contexts = {
            item.strip()
            for item in str(self.long_signal_range_atr_entry_contexts or "").replace(";", ",").split(",")
            if item.strip()
        }
        snapshot: dict[str, Any] = {
            "long_signal_range_atr_enabled": int(enabled),
            "long_signal_range_atr_long_enabled": int(long_enabled),
            "long_signal_range_atr_short_enabled": int(short_enabled),
            "long_signal_range_lookback": lookback,
            "long_signal_range_atr_period": atr_period,
            "long_signal_range_atr_multiplier": multiplier,
            "long_signal_range_require_recent_stall": int(require_recent_stall),
            "long_signal_range_recent_gain_lookback": recent_gain_lookback,
            "long_signal_range_recent_gain_atr_multiplier": recent_gain_atr_multiplier,
            "long_signal_range_enable_ordered_drawdown_filter": int(
                enable_ordered_drawdown
            ),
            "long_signal_range_ordered_drawdown_atr_multiplier": (
                ordered_drawdown_atr_multiplier
            ),
            "long_signal_range_atr_entry_context": entry_context,
            "long_signal_range_atr_direction": direction,
            "long_signal_range_high": float("nan"),
            "long_signal_range_low": float("nan"),
            "long_signal_range_value": float("nan"),
            "long_signal_range_prior_atr": float("nan"),
            "long_signal_range_atr_threshold": float("nan"),
            "long_signal_range_recent_gain": float("nan"),
            "long_signal_range_directional_recent_move": float("nan"),
            "long_signal_range_recent_gain_atr_threshold": float("nan"),
            "long_signal_range_recent_stall_condition_met": 0,
            "long_signal_range_expansion_stall_condition_met": 0,
            "long_signal_range_ordered_drawdown_peak": float("nan"),
            "long_signal_range_ordered_drawdown_trough": float("nan"),
            "long_signal_range_ordered_drawdown_value": float("nan"),
            "long_signal_range_ordered_drawdown_atr_threshold": float("nan"),
            "long_signal_range_ordered_drawdown_peak_index": -1,
            "long_signal_range_ordered_drawdown_trough_index": -1,
            "long_signal_range_ordered_drawdown_peak_history_index": "",
            "long_signal_range_ordered_drawdown_trough_history_index": "",
            "long_signal_range_ordered_drawdown_condition_met": 0,
            "long_signal_range_ordered_move_kind": "",
            "long_signal_range_atr_condition_met": 0,
            "long_signal_range_atr_reason": "disabled",
        }
        if not enabled:
            return snapshot
        if direction not in {"long", "short"}:
            snapshot["long_signal_range_atr_reason"] = "direction_excluded"
            return snapshot
        if (direction == "long" and not long_enabled) or (
            direction == "short" and not short_enabled
        ):
            snapshot["long_signal_range_atr_reason"] = "direction_excluded"
            return snapshot
        if entry_context not in contexts:
            snapshot["long_signal_range_atr_reason"] = "entry_context_excluded"
            return snapshot
        if (
            lookback <= 0
            or atr_period <= 0
            or not np.isfinite(multiplier)
            or multiplier <= 0
            or (
                enable_ordered_drawdown
                and (
                    not np.isfinite(ordered_drawdown_atr_multiplier)
                    or ordered_drawdown_atr_multiplier <= 0
                )
            )
            or (
                require_recent_stall
                and (
                    recent_gain_lookback <= 0
                    or not np.isfinite(recent_gain_atr_multiplier)
                    or recent_gain_atr_multiplier < 0
                )
            )
        ):
            snapshot["long_signal_range_atr_reason"] = "invalid_configuration"
            return snapshot

        required_count = max(
            lookback,
            atr_period + 2,
            recent_gain_lookback + 1 if require_recent_stall else 0,
        )
        if history is None or len(history) < required_count:
            snapshot["long_signal_range_atr_reason"] = "insufficient_history"
            return snapshot
        if not {"close", "high", "low"}.issubset(history.columns):
            snapshot["long_signal_range_atr_reason"] = "invalid_history"
            return snapshot

        range_window = history.tail(lookback)
        range_high = pd.to_numeric(range_window["high"], errors="coerce")
        range_low = pd.to_numeric(range_window["low"], errors="coerce")
        atr_window = history.tail(atr_period + 2)
        atr_close = pd.to_numeric(atr_window["close"], errors="coerce")
        atr_high = pd.to_numeric(atr_window["high"], errors="coerce")
        atr_low = pd.to_numeric(atr_window["low"], errors="coerce")
        numeric_series = (range_high, range_low, atr_close, atr_high, atr_low)
        if (
            any(not np.isfinite(series.to_numpy(dtype="float64")).all() for series in numeric_series)
            or (range_high <= 0).any()
            or (range_low <= 0).any()
            or (atr_close <= 0).any()
            or (atr_high <= 0).any()
            or (atr_low <= 0).any()
            or (range_high < range_low).any()
            or (atr_high < atr_low).any()
        ):
            snapshot["long_signal_range_atr_reason"] = "invalid_history"
            return snapshot

        completed_close = atr_close.iloc[:-1]
        completed_high = atr_high.iloc[:-1]
        completed_low = atr_low.iloc[:-1]
        previous_close = completed_close.shift(1)
        true_range = pd.concat(
            [
                (completed_high - completed_low).abs(),
                (completed_high - previous_close).abs(),
                (completed_low - previous_close).abs(),
            ],
            axis=1,
        ).max(axis=1).iloc[1:]
        if (
            len(true_range) != atr_period
            or not np.isfinite(true_range.to_numpy(dtype="float64")).all()
        ):
            snapshot["long_signal_range_atr_reason"] = "invalid_prior_true_range"
            return snapshot

        prior_atr = float(true_range.mean())
        high_value = float(range_high.max())
        low_value = float(range_low.min())
        range_value = high_value - low_value
        threshold = multiplier * prior_atr
        ordered_drawdown_threshold = ordered_drawdown_atr_multiplier * prior_atr
        recent_gain = float("nan")
        directional_recent_move = float("nan")
        recent_gain_threshold = float("nan")
        recent_stall_condition_met = 0
        if require_recent_stall:
            recent_close = pd.to_numeric(
                history["close"].tail(recent_gain_lookback + 1),
                errors="coerce",
            )
            if (
                len(recent_close) != recent_gain_lookback + 1
                or not np.isfinite(recent_close.to_numpy(dtype="float64")).all()
                or (recent_close <= 0).any()
            ):
                snapshot["long_signal_range_atr_reason"] = "invalid_recent_close_history"
                return snapshot
            recent_gain = float(recent_close.iloc[-1] - recent_close.iloc[0])
            directional_recent_move = (
                recent_gain if direction == "long" else -recent_gain
            )
            recent_gain_threshold = recent_gain_atr_multiplier * prior_atr
            recent_stall_condition_met = int(
                directional_recent_move < recent_gain_threshold
            )
        ordered_drawdown_peak = float("nan")
        ordered_drawdown_trough = float("nan")
        ordered_drawdown_value = float("nan")
        ordered_drawdown_peak_index = -1
        ordered_drawdown_trough_index = -1
        ordered_drawdown_peak_history_index = ""
        ordered_drawdown_trough_history_index = ""
        ordered_drawdown_condition_met = 0
        if enable_ordered_drawdown:
            high_values = range_high.to_numpy(dtype="float64")
            low_values = range_low.to_numpy(dtype="float64")
            best_value = float("-inf")
            best_peak_index = -1
            best_trough_index = -1
            if direction == "long":
                running_peak = float(high_values[0])
                running_peak_index = 0
                for trough_index in range(1, len(range_window)):
                    candidate_value = running_peak - float(low_values[trough_index])
                    if candidate_value > best_value:
                        best_value = candidate_value
                        best_peak_index = running_peak_index
                        best_trough_index = trough_index
                    if float(high_values[trough_index]) > running_peak:
                        running_peak = float(high_values[trough_index])
                        running_peak_index = trough_index
            else:
                running_trough = float(low_values[0])
                running_trough_index = 0
                for peak_index in range(1, len(range_window)):
                    candidate_value = float(high_values[peak_index]) - running_trough
                    if candidate_value > best_value:
                        best_value = candidate_value
                        best_peak_index = peak_index
                        best_trough_index = running_trough_index
                    if float(low_values[peak_index]) < running_trough:
                        running_trough = float(low_values[peak_index])
                        running_trough_index = peak_index
            ordered_indices_valid = (
                best_peak_index >= 0
                and best_trough_index >= 0
                and (
                    best_peak_index < best_trough_index
                    if direction == "long"
                    else best_trough_index < best_peak_index
                )
            )
            if ordered_indices_valid:
                ordered_drawdown_peak = float(high_values[best_peak_index])
                ordered_drawdown_trough = float(low_values[best_trough_index])
                ordered_drawdown_value = float(best_value)
                ordered_drawdown_peak_index = int(best_peak_index)
                ordered_drawdown_trough_index = int(best_trough_index)
                ordered_drawdown_peak_history_index = str(
                    range_window.index[best_peak_index]
                )
                ordered_drawdown_trough_history_index = str(
                    range_window.index[best_trough_index]
                )
                ordered_drawdown_condition_met = int(
                    ordered_drawdown_value > ordered_drawdown_threshold
                )
        expansion_stall_condition_met = int(
            range_value > threshold
            and (not require_recent_stall or recent_stall_condition_met)
        )
        snapshot.update(
            {
                "long_signal_range_high": high_value,
                "long_signal_range_low": low_value,
                "long_signal_range_value": range_value,
                "long_signal_range_prior_atr": prior_atr,
                "long_signal_range_atr_threshold": threshold,
                "long_signal_range_recent_gain": recent_gain,
                "long_signal_range_directional_recent_move": (
                    directional_recent_move
                ),
                "long_signal_range_recent_gain_atr_threshold": recent_gain_threshold,
                "long_signal_range_recent_stall_condition_met": recent_stall_condition_met,
                "long_signal_range_expansion_stall_condition_met": (
                    expansion_stall_condition_met
                ),
                "long_signal_range_ordered_drawdown_peak": ordered_drawdown_peak,
                "long_signal_range_ordered_drawdown_trough": ordered_drawdown_trough,
                "long_signal_range_ordered_drawdown_value": ordered_drawdown_value,
                "long_signal_range_ordered_drawdown_atr_threshold": (
                    ordered_drawdown_threshold
                ),
                "long_signal_range_ordered_drawdown_peak_index": (
                    ordered_drawdown_peak_index
                ),
                "long_signal_range_ordered_drawdown_trough_index": (
                    ordered_drawdown_trough_index
                ),
                "long_signal_range_ordered_drawdown_peak_history_index": (
                    ordered_drawdown_peak_history_index
                ),
                "long_signal_range_ordered_drawdown_trough_history_index": (
                    ordered_drawdown_trough_history_index
                ),
                "long_signal_range_ordered_drawdown_condition_met": (
                    ordered_drawdown_condition_met
                ),
                "long_signal_range_ordered_move_kind": (
                    "drawdown" if direction == "long" else "rebound"
                ),
            }
        )
        if prior_atr <= 0 or range_value < 0:
            snapshot["long_signal_range_atr_reason"] = "invalid_prior_atr_or_range"
            return snapshot
        if expansion_stall_condition_met or ordered_drawdown_condition_met:
            snapshot["long_signal_range_atr_condition_met"] = 1
            if expansion_stall_condition_met and ordered_drawdown_condition_met:
                snapshot["long_signal_range_atr_reason"] = (
                    "range_stall_and_ordered_drawdown_both"
                    if direction == "long"
                    else "short_range_stall_and_ordered_rebound_both"
                )
            elif ordered_drawdown_condition_met:
                snapshot["long_signal_range_atr_reason"] = (
                    "ordered_drawdown_strictly_above_threshold"
                    if direction == "long"
                    else "short_ordered_rebound_strictly_above_threshold"
                )
            else:
                snapshot["long_signal_range_atr_reason"] = (
                    (
                        "range_strictly_above_and_recent_gain_below_threshold"
                        if direction == "long"
                        else "short_range_strictly_above_and_recent_decline_below_threshold"
                    )
                    if require_recent_stall
                    else "range_strictly_above_threshold"
                )
            return snapshot
        if range_value > threshold and require_recent_stall:
            snapshot["long_signal_range_atr_reason"] = (
                "range_above_but_recent_gain_not_stalled"
                if direction == "long"
                else "short_range_above_but_recent_decline_not_stalled"
            )
            return snapshot
        snapshot["long_signal_range_atr_reason"] = "range_not_above_threshold"
        return snapshot

    def _apply_long_signal_range_atr_to_sizing(
        self,
        sizing: dict[str, Any],
        snapshot: dict[str, Any],
        *,
        vt_symbol: str,
        direction: str,
        bar: BarData,
        entry_context: str,
    ) -> dict[str, Any]:
        selected_before = max(0, int(sizing.get("selected_volume") or 0))
        condition_met = int(snapshot.get("long_signal_range_atr_condition_met") or 0)
        actually_blocked = int(bool(condition_met and selected_before > 0))
        selected_after = 0 if actually_blocked else selected_before
        sizing.update(snapshot)
        sizing["long_signal_range_atr_blocked"] = actually_blocked
        sizing["long_signal_range_atr_selected_volume_before"] = selected_before
        sizing["long_signal_range_atr_selected_volume_after"] = selected_after
        sizing["selected_volume"] = selected_after
        diagnostics = getattr(self, "long_signal_range_atr_diagnostics", None)
        if diagnostics is not None and int(snapshot.get("long_signal_range_atr_enabled") or 0):
            diagnostics.append(
                {
                    "diagnostic_index": len(diagnostics) + 1,
                    "datetime": bar.datetime,
                    "date": bar.datetime.date(),
                    "contract_vt_symbol": vt_symbol,
                    "product_vt_symbol": self.source_symbol_by_contract.get(
                        vt_symbol,
                        self._product_vt_symbol(vt_symbol),
                    ),
                    "direction": direction,
                    "entry_context": entry_context,
                    **snapshot,
                    "long_signal_range_atr_blocked": actually_blocked,
                    "long_signal_range_atr_selected_volume_before": selected_before,
                    "long_signal_range_atr_selected_volume_after": selected_after,
                }
            )
        return sizing

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
            history=history,
            active_positions_before=active_positions_before,
            correlation_snapshot=correlation_snapshot,
        )
        effective_risk_multiplier = float(
            recovery_fields.get(
                "streak_entry_structure_risk_recovery_effective_multiplier",
                self._current_streak_multiplier(),
            )
        )
        product_vt_symbol = self.source_symbol_by_contract.get(vt_symbol, self._product_vt_symbol(vt_symbol))
        failure_memory_fields = self._failure_memory_micro_sizing_fields(
            product_vt_symbol=product_vt_symbol,
            direction=direction,
            entry_context=entry_context,
            asof=pd.Timestamp(bar.datetime).normalize(),
            base_multiplier=effective_risk_multiplier,
        )
        effective_risk_multiplier = float(
            failure_memory_fields.get(
                "failure_memory_micro_sizing_effective_multiplier",
                effective_risk_multiplier,
            )
            or effective_risk_multiplier
        )
        oi_price_confirm_fields = self._oi_price_confirm_risk_restore_fields(
            history=history,
            direction=direction,
            entry_context=entry_context,
            base_multiplier=effective_risk_multiplier,
        )
        effective_risk_multiplier = float(
            oi_price_confirm_fields.get(
                "oi_price_confirm_risk_restore_effective_multiplier",
                effective_risk_multiplier,
            )
            or effective_risk_multiplier
        )
        overheat_cooldown_fields = self._portfolio_overheat_cooldown_fields(entry_context)
        overheat_cooldown_scale = float(overheat_cooldown_fields["portfolio_overheat_cooldown_scale"])
        directional_30d_risk_boost_fields = self._directional_30d_risk_boost_snapshot(direction, history)
        long_signal_atr_shock_fields = self._long_signal_atr_shock_snapshot(
            direction,
            history,
            entry_context,
        )
        long_signal_range_atr_fields = self._long_signal_range_atr_snapshot(
            direction,
            history,
            entry_context,
        )
        sizing_equity_fields = self._sizing_equity_snapshot()
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
            cluster_cap_fields = self._risk_cluster_cap_fields(vt_symbol, volume, margin_per_contract)
            volume = int(cluster_cap_fields["risk_cluster_selected_volume"])
            heat_gate_fields = self._apply_risk_cluster_heat_gate_to_volume(
                vt_symbol,
                volume,
                margin_per_contract,
                entry_context,
            )
            volume = int(heat_gate_fields["risk_cluster_heat_gate_selected_volume"])
            volume = self._portfolio_overheat_cooldown_adjust_volume(volume, entry_context)
            if 0 < volume < self.min_position_size:
                volume = 0
            env_gate_fields = self._apply_env_gate_to_volume(
                volume,
                entry_context=entry_context,
                apply_env_gate=apply_env_gate,
            )
            incremental_gate_fields: dict[str, Any] = {}
            if entry_context != "flat_entry":
                adjusted_volume, incremental_gate_fields = self._incremental_margin_budget_gate_adjust_volume(
                    selected_volume=int(env_gate_fields["selected_volume"]),
                    margin_per_contract=margin_per_contract,
                    entry_context=entry_context,
                )
                env_gate_fields["selected_volume"] = adjusted_volume
            sizing_result: dict[str, Any] = {
                "risk_mode": risk_mode_override or str(signal_data.get("risk_mode", "regular")),
                "entry_context": entry_context,
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
                **sizing_equity_fields,
                **recovery_fields,
                **failure_memory_fields,
                **oi_price_confirm_fields,
                **overheat_cooldown_fields,
                **directional_30d_risk_boost_fields,
                **cluster_cap_fields,
                **heat_gate_fields,
                **env_gate_fields,
                **incremental_gate_fields,
            }
            sizing_result.update(self._recovery_sleeve_fields(sizing_result, bar, entry_context, direction, history))
            sizing_result = self._apply_long_signal_atr_shock_to_sizing(
                sizing_result,
                long_signal_atr_shock_fields,
                vt_symbol=vt_symbol,
                direction=direction,
                bar=bar,
                entry_context=entry_context,
            )
            return self._apply_long_signal_range_atr_to_sizing(
                sizing_result,
                long_signal_range_atr_fields,
                vt_symbol=vt_symbol,
                direction=direction,
                bar=bar,
                entry_context=entry_context,
            )

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
        risk_amount *= max(0.0, overheat_cooldown_scale)
        risk_amount_before_directional_30d_boost = risk_amount
        risk_amount *= float(directional_30d_risk_boost_fields["directional_30d_risk_boost_multiplier"])
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
        cluster_cap_fields = self._risk_cluster_cap_fields(vt_symbol, volume, margin_per_contract)
        volume = int(cluster_cap_fields["risk_cluster_selected_volume"])
        heat_gate_fields = self._apply_risk_cluster_heat_gate_to_volume(
            vt_symbol,
            volume,
            margin_per_contract,
            entry_context,
        )
        volume = int(heat_gate_fields["risk_cluster_heat_gate_selected_volume"])
        if 0 < volume < self.min_position_size:
            volume = 0
        env_gate_fields = self._apply_env_gate_to_volume(
            volume,
            entry_context=entry_context,
            apply_env_gate=apply_env_gate,
        )
        incremental_gate_fields = {}
        if entry_context != "flat_entry":
            adjusted_volume, incremental_gate_fields = self._incremental_margin_budget_gate_adjust_volume(
                selected_volume=int(env_gate_fields["selected_volume"]),
                margin_per_contract=margin_per_contract,
                entry_context=entry_context,
            )
            env_gate_fields["selected_volume"] = adjusted_volume

        sizing_result = {
            "risk_mode": risk_mode,
            "entry_context": entry_context,
            "risk_ratio": risk_ratio,
            "risk_amount": risk_amount,
            "risk_amount_before_directional_30d_boost": risk_amount_before_directional_30d_boost,
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
            **sizing_equity_fields,
            **recovery_fields,
            **failure_memory_fields,
            **oi_price_confirm_fields,
            **overheat_cooldown_fields,
            **directional_30d_risk_boost_fields,
            **cluster_cap_fields,
            **heat_gate_fields,
            **env_gate_fields,
            **incremental_gate_fields,
        }
        sizing_result.update(self._recovery_sleeve_fields(sizing_result, bar, entry_context, direction, history))
        sizing_result = self._apply_long_signal_atr_shock_to_sizing(
            sizing_result,
            long_signal_atr_shock_fields,
            vt_symbol=vt_symbol,
            direction=direction,
            bar=bar,
            entry_context=entry_context,
        )
        return self._apply_long_signal_range_atr_to_sizing(
            sizing_result,
            long_signal_range_atr_fields,
            vt_symbol=vt_symbol,
            direction=direction,
            bar=bar,
            entry_context=entry_context,
        )

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

        if int(sizing_snapshot.get("recovery_sleeve_applied") or 0) == 1:
            sleeve_open_date = pd.Timestamp(bar.datetime).tz_localize(None).normalize()
            self._recovery_sleeve_last_open_timestamp = sleeve_open_date
            self.recovery_sleeve_last_open_date = sleeve_open_date.date().isoformat()
            self.recovery_sleeve_open_count += 1

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
        sizing_snapshot_extra: dict[str, Any] | None = None,
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
        sizing_method = {
            "add": "add_multiplier",
            "donchian": "donchian_multiplier",
            "post_quality": "post_entry_quality_add",
        }.get(kind, f"{kind}_multiplier")
        entry_context = {
            "add": "regular_add",
            "donchian": "donchian_add",
            "post_quality": "post_quality_add",
        }.get(kind, kind)
        sizing_snapshot = {
            "risk_mode": state.risk_mode,
            "entry_context": entry_context,
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
            "sizing_method": sizing_method,
        }
        if sizing_snapshot_extra:
            sizing_snapshot.update(sizing_snapshot_extra)
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
            sizing_snapshot=sizing_snapshot,
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
                "sizing_equity": float(sizing_snapshot.get("sizing_equity") or 0.0),
                "effective_sizing_equity_cap": float(sizing_snapshot.get("effective_sizing_equity_cap") or 0.0),
                "dynamic_sizing_equity_soft_cap_enabled": int(
                    sizing_snapshot.get("dynamic_sizing_equity_soft_cap_enabled") or 0
                ),
                "dynamic_sizing_equity_soft_cap_base": float(
                    sizing_snapshot.get("dynamic_sizing_equity_soft_cap_base") or 0.0
                ),
                "dynamic_sizing_equity_soft_cap_max": float(
                    sizing_snapshot.get("dynamic_sizing_equity_soft_cap_max") or 0.0
                ),
                "dynamic_sizing_equity_soft_cap_raw_cap": float(
                    sizing_snapshot.get("dynamic_sizing_equity_soft_cap_raw_cap") or 0.0
                ),
                "dynamic_sizing_equity_soft_cap_margin_pressure_ratio": float(
                    sizing_snapshot.get("dynamic_sizing_equity_soft_cap_margin_pressure_ratio") or 0.0
                ),
                "dynamic_sizing_equity_soft_cap_drawdown_ratio": float(
                    sizing_snapshot.get("dynamic_sizing_equity_soft_cap_drawdown_ratio") or 0.0
                ),
                "dynamic_sizing_equity_soft_cap_release_weight": float(
                    sizing_snapshot.get("dynamic_sizing_equity_soft_cap_release_weight") or 0.0
                ),
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
                "oi_price_confirm_risk_restore_enabled": int(
                    sizing_snapshot.get("oi_price_confirm_risk_restore_enabled") or 0
                ),
                "oi_price_confirm_risk_restore_applied": int(
                    sizing_snapshot.get("oi_price_confirm_risk_restore_applied") or 0
                ),
                "oi_price_confirm_risk_restore_reason": str(
                    sizing_snapshot.get("oi_price_confirm_risk_restore_reason") or ""
                ),
                "oi_price_confirm_risk_restore_base_multiplier": float(
                    sizing_snapshot.get("oi_price_confirm_risk_restore_base_multiplier")
                    if sizing_snapshot.get("oi_price_confirm_risk_restore_base_multiplier") is not None
                    else self._current_streak_multiplier()
                ),
                "oi_price_confirm_risk_restore_multiplier": float(
                    sizing_snapshot.get("oi_price_confirm_risk_restore_multiplier")
                    if sizing_snapshot.get("oi_price_confirm_risk_restore_multiplier") is not None
                    else self.oi_price_confirm_risk_restore_multiplier
                ),
                "oi_price_confirm_risk_restore_effective_multiplier": float(
                    sizing_snapshot.get("oi_price_confirm_risk_restore_effective_multiplier")
                    or sizing_snapshot.get("risk_multiplier")
                    or self._current_streak_multiplier()
                ),
                "oi_price_confirm_entry_close": float(
                    sizing_snapshot.get("oi_price_confirm_entry_close")
                    if sizing_snapshot.get("oi_price_confirm_entry_close") is not None
                    else float("nan")
                ),
                "oi_price_confirm_prev_close": float(
                    sizing_snapshot.get("oi_price_confirm_prev_close")
                    if sizing_snapshot.get("oi_price_confirm_prev_close") is not None
                    else float("nan")
                ),
                "oi_price_confirm_entry_oi": float(
                    sizing_snapshot.get("oi_price_confirm_entry_oi")
                    if sizing_snapshot.get("oi_price_confirm_entry_oi") is not None
                    else float("nan")
                ),
                "oi_price_confirm_prev_oi": float(
                    sizing_snapshot.get("oi_price_confirm_prev_oi")
                    if sizing_snapshot.get("oi_price_confirm_prev_oi") is not None
                    else float("nan")
                ),
                "oi_price_confirm_oi_up": int(sizing_snapshot.get("oi_price_confirm_oi_up") or 0),
                "oi_price_confirm_price_aligned": int(
                    sizing_snapshot.get("oi_price_confirm_price_aligned") or 0
                ),
                "oi_price_confirm_recent_sum_ratio_required": int(
                    sizing_snapshot.get("oi_price_confirm_recent_sum_ratio_required") or 0
                ),
                "oi_price_confirm_recent_sum_days": int(
                    sizing_snapshot.get("oi_price_confirm_recent_sum_days") or 0
                ),
                "oi_price_confirm_recent_oi_sum": float(
                    sizing_snapshot.get("oi_price_confirm_recent_oi_sum")
                    if sizing_snapshot.get("oi_price_confirm_recent_oi_sum") is not None
                    else float("nan")
                ),
                "oi_price_confirm_prior_oi_sum": float(
                    sizing_snapshot.get("oi_price_confirm_prior_oi_sum")
                    if sizing_snapshot.get("oi_price_confirm_prior_oi_sum") is not None
                    else float("nan")
                ),
                "oi_price_confirm_recent_prior_oi_sum_ratio": float(
                    sizing_snapshot.get("oi_price_confirm_recent_prior_oi_sum_ratio")
                    if sizing_snapshot.get("oi_price_confirm_recent_prior_oi_sum_ratio") is not None
                    else float("nan")
                ),
                "oi_price_confirm_recent_sum_ratio_passed": int(
                    sizing_snapshot.get("oi_price_confirm_recent_sum_ratio_passed") or 0
                ),
                "oi_price_confirm_passed": int(sizing_snapshot.get("oi_price_confirm_passed") or 0),
                "failure_memory_micro_sizing_enabled": int(
                    sizing_snapshot.get("failure_memory_micro_sizing_enabled") or 0
                ),
                "failure_memory_micro_sizing_applied": int(
                    sizing_snapshot.get("failure_memory_micro_sizing_applied") or 0
                ),
                "failure_memory_micro_sizing_reason": str(
                    sizing_snapshot.get("failure_memory_micro_sizing_reason") or ""
                ),
                "failure_memory_micro_sizing_lookback_days": int(
                    sizing_snapshot.get("failure_memory_micro_sizing_lookback_days") or 0
                ),
                "failure_memory_micro_sizing_min_consecutive_failures": int(
                    sizing_snapshot.get("failure_memory_micro_sizing_min_consecutive_failures") or 0
                ),
                "failure_memory_micro_sizing_multiplier": float(
                    sizing_snapshot.get("failure_memory_micro_sizing_multiplier") or 1.0
                ),
                "failure_memory_micro_sizing_base_multiplier": float(
                    sizing_snapshot.get("failure_memory_micro_sizing_base_multiplier")
                    or self._current_streak_multiplier()
                ),
                "failure_memory_micro_sizing_effective_multiplier": float(
                    sizing_snapshot.get("failure_memory_micro_sizing_effective_multiplier")
                    or sizing_snapshot.get("risk_multiplier")
                    or self._current_streak_multiplier()
                ),
                "failure_memory_micro_sizing_consecutive_failures": int(
                    sizing_snapshot.get("failure_memory_micro_sizing_consecutive_failures") or 0
                ),
                "failure_memory_micro_sizing_last_failure_exit_date": str(
                    sizing_snapshot.get("failure_memory_micro_sizing_last_failure_exit_date") or ""
                ),
                "failure_memory_micro_sizing_days_since_last_failure": float(
                    sizing_snapshot.get("failure_memory_micro_sizing_days_since_last_failure")
                    if sizing_snapshot.get("failure_memory_micro_sizing_days_since_last_failure") is not None
                    else float("nan")
                ),
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
                "streak_entry_structure_risk_recovery_directional_edge_enabled": int(
                    sizing_snapshot.get("streak_entry_structure_risk_recovery_directional_edge_enabled") or 0
                ),
                "streak_entry_structure_risk_recovery_directional_edge_period": int(
                    sizing_snapshot.get("streak_entry_structure_risk_recovery_directional_edge_period")
                    or self.streak_entry_structure_recovery_directional_edge_period
                    or 0
                ),
                "streak_entry_structure_risk_recovery_directional_edge_close_position": float(
                    sizing_snapshot.get("streak_entry_structure_risk_recovery_directional_edge_close_position")
                    if sizing_snapshot.get("streak_entry_structure_risk_recovery_directional_edge_close_position")
                    is not None
                    else float("nan")
                ),
                "streak_entry_structure_risk_recovery_directional_edge_long_min": float(
                    sizing_snapshot.get("streak_entry_structure_risk_recovery_directional_edge_long_min")
                    if sizing_snapshot.get("streak_entry_structure_risk_recovery_directional_edge_long_min") is not None
                    else self.streak_entry_structure_recovery_long_close_position_min
                ),
                "streak_entry_structure_risk_recovery_directional_edge_short_max": float(
                    sizing_snapshot.get("streak_entry_structure_risk_recovery_directional_edge_short_max")
                    if sizing_snapshot.get("streak_entry_structure_risk_recovery_directional_edge_short_max") is not None
                    else self.streak_entry_structure_recovery_short_close_position_max
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
                "recovery_sleeve_enabled": int(sizing_snapshot.get("recovery_sleeve_enabled") or 0),
                "recovery_sleeve_applied": int(sizing_snapshot.get("recovery_sleeve_applied") or 0),
                "recovery_sleeve_normal_risk_bypass_enabled": int(
                    sizing_snapshot.get("recovery_sleeve_normal_risk_bypass_enabled") or 0
                ),
                "recovery_sleeve_normal_risk_bypassed": int(
                    sizing_snapshot.get("recovery_sleeve_normal_risk_bypassed") or 0
                ),
                "recovery_sleeve_reason": str(sizing_snapshot.get("recovery_sleeve_reason") or ""),
                "recovery_sleeve_selected_volume_before": int(
                    sizing_snapshot.get("recovery_sleeve_selected_volume_before") or 0
                ),
                "recovery_sleeve_selected_volume_after": int(
                    sizing_snapshot.get("recovery_sleeve_selected_volume_after") or 0
                ),
                "recovery_sleeve_broker_margin_multiplier": float(
                    sizing_snapshot.get("recovery_sleeve_broker_margin_multiplier")
                    or self.recovery_sleeve_broker_margin_multiplier
                ),
                "recovery_sleeve_single_contract_broker_margin_to_equity": float(
                    sizing_snapshot.get("recovery_sleeve_single_contract_broker_margin_to_equity") or 0.0
                ),
                "recovery_sleeve_max_single_contract_broker_margin_to_equity": float(
                    sizing_snapshot.get("recovery_sleeve_max_single_contract_broker_margin_to_equity")
                    or self.recovery_sleeve_max_single_contract_broker_margin_to_equity
                ),
                "recovery_sleeve_cooldown_days": int(
                    sizing_snapshot.get("recovery_sleeve_cooldown_days") or self.recovery_sleeve_cooldown_days or 0
                ),
                "post_entry_quality_add_enabled": int(
                    sizing_snapshot.get("post_entry_quality_add_enabled") or 0
                ),
                "post_entry_quality_add_feature": str(
                    sizing_snapshot.get("post_entry_quality_add_feature") or ""
                ),
                "post_entry_quality_add_passed": int(sizing_snapshot.get("post_entry_quality_add_passed") or 0),
                "post_entry_quality_add_observation_bars": int(
                    sizing_snapshot.get("post_entry_quality_add_observation_bars") or 0
                ),
                "post_entry_quality_add_volume_multiplier": float(
                    sizing_snapshot.get("post_entry_quality_add_volume_multiplier") or 0.0
                ),
                "post_entry_quality_add_triggers_add_profit_lock": int(
                    sizing_snapshot.get("post_entry_quality_add_triggers_add_profit_lock") or 0
                ),
                "post_entry_quality_add_body60_ratio": float(
                    sizing_snapshot.get("post_entry_quality_add_body60_ratio") or 0.0
                ),
                "post_entry_quality_add_avg_body_pct": float(
                    sizing_snapshot.get("post_entry_quality_add_avg_body_pct") or 0.0
                ),
                "post_entry_quality_add_avg_directional_close_strength": float(
                    sizing_snapshot.get("post_entry_quality_add_avg_directional_close_strength") or 0.0
                ),
                "post_entry_quality_add_short30_ratio": float(
                    sizing_snapshot.get("post_entry_quality_add_short30_ratio") or 0.0
                ),
                "post_entry_quality_add_long60_ratio": float(
                    sizing_snapshot.get("post_entry_quality_add_long60_ratio") or 0.0
                ),
                "post_entry_quality_add_avg_adverse_wick_pct": float(
                    sizing_snapshot.get("post_entry_quality_add_avg_adverse_wick_pct") or 0.0
                ),
                "directional_30d_risk_boost_enabled": int(
                    sizing_snapshot.get("directional_30d_risk_boost_enabled") or 0
                ),
                "directional_30d_risk_boost_lookback": int(
                    sizing_snapshot.get("directional_30d_risk_boost_lookback") or 0
                ),
                "directional_30d_volume_confirmation_enabled": int(
                    sizing_snapshot.get("directional_30d_volume_confirmation_enabled") or 0
                ),
                "directional_30d_volume_recent_days": int(
                    sizing_snapshot.get("directional_30d_volume_recent_days") or 0
                ),
                "directional_30d_volume_prior_days": int(
                    sizing_snapshot.get("directional_30d_volume_prior_days") or 0
                ),
                "directional_30d_volume_ratio_threshold": sizing_snapshot.get(
                    "directional_30d_volume_ratio_threshold"
                ),
                "directional_30d_low_volume_discount_enabled": int(
                    sizing_snapshot.get("directional_30d_low_volume_discount_enabled") or 0
                ),
                "directional_30d_low_volume_ratio_threshold": sizing_snapshot.get(
                    "directional_30d_low_volume_ratio_threshold"
                ),
                "directional_30d_low_volume_risk_multiplier": sizing_snapshot.get(
                    "directional_30d_low_volume_risk_multiplier"
                ),
                "directional_30d_low_volume_discount_applied": int(
                    sizing_snapshot.get("directional_30d_low_volume_discount_applied") or 0
                ),
                "directional_30d_recent_volume_sum": sizing_snapshot.get(
                    "directional_30d_recent_volume_sum"
                ),
                "directional_30d_prior_volume_sum": sizing_snapshot.get(
                    "directional_30d_prior_volume_sum"
                ),
                "directional_30d_volume_expanding": int(
                    sizing_snapshot.get("directional_30d_volume_expanding") or 0
                ),
                "directional_30d_start_close": float(
                    sizing_snapshot.get("directional_30d_start_close")
                    if sizing_snapshot.get("directional_30d_start_close") is not None
                    else float("nan")
                ),
                "directional_30d_end_close": float(
                    sizing_snapshot.get("directional_30d_end_close")
                    if sizing_snapshot.get("directional_30d_end_close") is not None
                    else float("nan")
                ),
                "directional_30d_return": float(
                    sizing_snapshot.get("directional_30d_return")
                    if sizing_snapshot.get("directional_30d_return") is not None
                    else float("nan")
                ),
                "directional_30d_risk_boost_aligned": int(
                    sizing_snapshot.get("directional_30d_risk_boost_aligned") or 0
                ),
                "directional_30d_risk_boost_applied": int(
                    sizing_snapshot.get("directional_30d_risk_boost_applied") or 0
                ),
                "directional_30d_risk_nonconfirmation_multiplier": float(
                    sizing_snapshot.get("directional_30d_risk_nonconfirmation_multiplier") or 1.0
                ),
                "directional_30d_risk_adjust_long_only": int(
                    sizing_snapshot.get("directional_30d_risk_adjust_long_only") or 0
                ),
                "directional_30d_risk_boost_multiplier": float(
                    sizing_snapshot.get("directional_30d_risk_boost_multiplier") or 1.0
                ),
                "directional_30d_risk_boost_reason": str(
                    sizing_snapshot.get("directional_30d_risk_boost_reason") or ""
                ),
                "risk_amount_before_directional_30d_boost": sizing_snapshot.get(
                    "risk_amount_before_directional_30d_boost"
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
                "risk_cluster_cap_enabled": int(sizing_snapshot.get("risk_cluster_cap_enabled") or 0),
                "risk_cluster_name": str(sizing_snapshot.get("risk_cluster_name") or ""),
                "risk_cluster_cap_ratio": float(sizing_snapshot.get("risk_cluster_cap_ratio") or 0.0),
                "risk_cluster_cap_amount": float(sizing_snapshot.get("risk_cluster_cap_amount") or 0.0),
                "risk_cluster_reserved_margin_before": float(
                    sizing_snapshot.get("risk_cluster_reserved_margin_before") or 0.0
                ),
                "risk_cluster_max_volume": int(sizing_snapshot.get("risk_cluster_max_volume") or 0),
                "risk_cluster_selected_volume_before": int(
                    sizing_snapshot.get("risk_cluster_selected_volume_before") or 0
                ),
                "risk_cluster_selected_volume": int(sizing_snapshot.get("risk_cluster_selected_volume") or 0),
                "risk_cluster_heat_gate_enabled": int(
                    sizing_snapshot.get("risk_cluster_heat_gate_enabled") or 0
                ),
                "risk_cluster_heat_gate_weight": float(
                    sizing_snapshot.get("risk_cluster_heat_gate_weight") or 1.0
                ),
                "risk_cluster_heat_gate_pressure": float(
                    sizing_snapshot.get("risk_cluster_heat_gate_pressure") or 0.0
                ),
                "risk_cluster_heat_gate_selected_volume_before": int(
                    sizing_snapshot.get("risk_cluster_heat_gate_selected_volume_before") or 0
                ),
                "risk_cluster_heat_gate_selected_volume": int(
                    sizing_snapshot.get("risk_cluster_heat_gate_selected_volume") or 0
                ),
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
                "incremental_margin_budget_gate_reduce_volume_enabled": int(
                    sizing_snapshot.get("incremental_margin_budget_gate_reduce_volume_enabled") or 0
                ),
                "incremental_margin_budget_gate_budget": float(
                    sizing_snapshot.get("incremental_margin_budget_gate_budget") or 0.0
                ),
                "incremental_margin_budget_gate_remaining_budget": float(
                    sizing_snapshot.get("incremental_margin_budget_gate_remaining_budget") or 0.0
                ),
                "incremental_margin_budget_gate_max_affordable_volume": int(
                    sizing_snapshot.get("incremental_margin_budget_gate_max_affordable_volume") or 0
                ),
                "incremental_margin_budget_gate_selected_volume_before": int(
                    sizing_snapshot.get("incremental_margin_budget_gate_selected_volume_before") or selected_volume
                ),
                "incremental_margin_budget_gate_selected_volume_after": int(
                    sizing_snapshot.get("incremental_margin_budget_gate_selected_volume_after") or selected_volume
                ),
                "incremental_margin_budget_gate_volume_reduced": int(
                    sizing_snapshot.get("incremental_margin_budget_gate_volume_reduced") or 0
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
                "incremental_margin_budget_gate_projected_margin_after_before_reduction": float(
                    sizing_snapshot.get("incremental_margin_budget_gate_projected_margin_after_before_reduction") or 0.0
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
                "portfolio_volatility_budget_enabled": int(
                    sizing_snapshot.get("portfolio_volatility_budget_enabled") or 0
                ),
                "portfolio_volatility_budget_weight": float(
                    sizing_snapshot.get("portfolio_volatility_budget_weight") or 1.0
                ),
                "portfolio_volatility_budget_realized_annual_vol": float(
                    sizing_snapshot.get("portfolio_volatility_budget_realized_annual_vol") or 0.0
                ),
                "portfolio_volatility_budget_lookback": int(
                    sizing_snapshot.get("portfolio_volatility_budget_lookback") or 0
                ),
                "portfolio_volatility_budget_target_annual_vol": float(
                    sizing_snapshot.get("portfolio_volatility_budget_target_annual_vol") or 0.0
                ),
                "portfolio_overheat_cooldown_enabled": int(
                    sizing_snapshot.get("portfolio_overheat_cooldown_enabled") or 0
                ),
                "portfolio_overheat_cooldown_scale": float(
                    sizing_snapshot.get("portfolio_overheat_cooldown_scale") or 1.0
                ),
                "portfolio_overheat_cooldown_reason": str(
                    sizing_snapshot.get("portfolio_overheat_cooldown_reason") or ""
                ),
                "portfolio_overheat_cooldown_prior_drawdown_pct": float(
                    sizing_snapshot.get("portfolio_overheat_cooldown_prior_drawdown_pct") or 0.0
                ),
                "portfolio_overheat_cooldown_prior_ret20": float(
                    sizing_snapshot.get("portfolio_overheat_cooldown_prior_ret20")
                    if sizing_snapshot.get("portfolio_overheat_cooldown_prior_ret20") is not None
                    else float("nan")
                ),
                "portfolio_overheat_cooldown_prior_ret60": float(
                    sizing_snapshot.get("portfolio_overheat_cooldown_prior_ret60")
                    if sizing_snapshot.get("portfolio_overheat_cooldown_prior_ret60") is not None
                    else float("nan")
                ),
                "rollover_reopen_drawdown_guard_enabled": int(
                    sizing_snapshot.get("rollover_reopen_drawdown_guard_enabled") or 0
                ),
                "rollover_reopen_drawdown_guard_passed": int(
                    sizing_snapshot.get("rollover_reopen_drawdown_guard_passed", 1) or 0
                ),
                "rollover_reopen_drawdown_guard_max_pct": float(
                    sizing_snapshot.get("rollover_reopen_drawdown_guard_max_pct") or 0.0
                ),
                "rollover_reopen_drawdown_guard_portfolio_drawdown_pct": float(
                    sizing_snapshot.get("rollover_reopen_drawdown_guard_portfolio_drawdown_pct")
                    or sizing_snapshot.get("portfolio_drawdown_pct")
                    or 0.0
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
                "ai_path_damage_enabled": int(sizing_snapshot.get("ai_path_damage_enabled") or 0),
                "ai_path_damage_model_tag": str(sizing_snapshot.get("ai_path_damage_model_tag") or ""),
                "ai_path_damage_probability": float(sizing_snapshot.get("ai_path_damage_probability") or 0.0),
                "ai_path_damage_discount_weight": float(
                    sizing_snapshot.get("ai_path_damage_discount_weight") or 1.0
                ),
                "ai_path_damage_discount_applied": int(
                    sizing_snapshot.get("ai_path_damage_discount_applied") or 0
                ),
                "ai_path_damage_feature_available": int(
                    sizing_snapshot.get("ai_path_damage_feature_available") or 0
                ),
                "ai_path_damage_selected_volume_before": int(
                    sizing_snapshot.get("ai_path_damage_selected_volume_before") or selected_volume
                ),
                "ai_path_damage_selected_volume_after": int(
                    sizing_snapshot.get("ai_path_damage_selected_volume_after") or selected_volume
                ),
                "product_direction_failure_cooldown_enabled": int(
                    sizing_snapshot.get("product_direction_failure_cooldown_enabled") or 0
                ),
                "product_direction_failure_cooldown_blocked": int(
                    sizing_snapshot.get("product_direction_failure_cooldown_blocked") or 0
                ),
                "product_direction_failure_cooldown_reason": str(
                    sizing_snapshot.get("product_direction_failure_cooldown_reason") or ""
                ),
                "product_direction_failure_cooldown_consecutive_failures": int(
                    sizing_snapshot.get("product_direction_failure_cooldown_consecutive_failures") or 0
                ),
                "product_direction_failure_cooldown_lookback_days": int(
                    sizing_snapshot.get("product_direction_failure_cooldown_lookback_days") or 0
                ),
                "product_direction_failure_cooldown_min_consecutive_failures": int(
                    sizing_snapshot.get("product_direction_failure_cooldown_min_consecutive_failures") or 0
                ),
                "product_direction_failure_cooldown_days": int(
                    sizing_snapshot.get("product_direction_failure_cooldown_days") or 0
                ),
                "product_direction_failure_cooldown_last_failure_exit_date": str(
                    sizing_snapshot.get("product_direction_failure_cooldown_last_failure_exit_date") or ""
                ),
                "product_direction_failure_cooldown_until": str(
                    sizing_snapshot.get("product_direction_failure_cooldown_until") or ""
                ),
                "product_direction_failure_cooldown_days_since_last_failure": float(
                    sizing_snapshot.get("product_direction_failure_cooldown_days_since_last_failure")
                    if sizing_snapshot.get("product_direction_failure_cooldown_days_since_last_failure") is not None
                    else float("nan")
                ),
                "product_direction_failure_cooldown_selected_volume_before": int(
                    sizing_snapshot.get("product_direction_failure_cooldown_selected_volume_before") or selected_volume
                ),
                "product_direction_failure_cooldown_selected_volume_after": int(
                    sizing_snapshot.get("product_direction_failure_cooldown_selected_volume_after") or selected_volume
                ),
                "ai_product_pool_enabled": int(sizing_snapshot.get("ai_product_pool_enabled") or 0),
                "ai_product_pool_strategy": str(sizing_snapshot.get("ai_product_pool_strategy") or ""),
                "ai_product_pool_allowed": int(sizing_snapshot.get("ai_product_pool_allowed") or 0),
                "ai_product_pool_use_next_trade_date_for_entry": int(
                    sizing_snapshot.get("ai_product_pool_use_next_trade_date_for_entry") or 0
                ),
                "ai_product_pool_entry_effective_date": str(
                    sizing_snapshot.get("ai_product_pool_entry_effective_date") or ""
                ),
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
                "entry_context": str(
                    sizing_snapshot.get("entry_context")
                    or sizing_snapshot.get("env_gate_entry_context")
                    or ""
                ),
                "risk_mode": risk_mode,
                "sizing_method": sizing_snapshot.get("sizing_method", "unknown"),
                "estimated_equity": estimated_equity,
                "total_margin_in_use_before": reserved_margin_before,
                "allowed_capital": float(sizing_snapshot.get("allowed_capital") or 0.0),
                "single_trade_capital_limit": float(sizing_snapshot.get("single_trade_capital_limit") or 0.0),
                "sizing_equity": float(sizing_snapshot.get("sizing_equity") or 0.0),
                "effective_sizing_equity_cap": float(sizing_snapshot.get("effective_sizing_equity_cap") or 0.0),
                "dynamic_sizing_equity_soft_cap_enabled": int(
                    sizing_snapshot.get("dynamic_sizing_equity_soft_cap_enabled") or 0
                ),
                "dynamic_sizing_equity_soft_cap_base": float(
                    sizing_snapshot.get("dynamic_sizing_equity_soft_cap_base") or 0.0
                ),
                "dynamic_sizing_equity_soft_cap_max": float(
                    sizing_snapshot.get("dynamic_sizing_equity_soft_cap_max") or 0.0
                ),
                "dynamic_sizing_equity_soft_cap_raw_cap": float(
                    sizing_snapshot.get("dynamic_sizing_equity_soft_cap_raw_cap") or 0.0
                ),
                "dynamic_sizing_equity_soft_cap_margin_pressure_ratio": float(
                    sizing_snapshot.get("dynamic_sizing_equity_soft_cap_margin_pressure_ratio") or 0.0
                ),
                "dynamic_sizing_equity_soft_cap_drawdown_ratio": float(
                    sizing_snapshot.get("dynamic_sizing_equity_soft_cap_drawdown_ratio") or 0.0
                ),
                "dynamic_sizing_equity_soft_cap_release_weight": float(
                    sizing_snapshot.get("dynamic_sizing_equity_soft_cap_release_weight") or 0.0
                ),
                "free_capital": float(sizing_snapshot.get("free_capital") or 0.0),
                "limited_balance": float(sizing_snapshot.get("limited_balance") or 0.0),
                "effective_single_trade_capital_usage_ratio": float(self.max_single_trade_capital_usage_ratio),
                "effective_streak_risk_multipliers": self.streak_risk_multipliers,
                "risk_ratio": sizing_snapshot.get("risk_ratio"),
                "risk_multiplier": float(sizing_snapshot.get("risk_multiplier") or self._current_streak_multiplier()),
                "oi_price_confirm_risk_restore_enabled": int(
                    sizing_snapshot.get("oi_price_confirm_risk_restore_enabled") or 0
                ),
                "oi_price_confirm_risk_restore_applied": int(
                    sizing_snapshot.get("oi_price_confirm_risk_restore_applied") or 0
                ),
                "oi_price_confirm_risk_restore_reason": str(
                    sizing_snapshot.get("oi_price_confirm_risk_restore_reason") or ""
                ),
                "oi_price_confirm_risk_restore_base_multiplier": float(
                    sizing_snapshot.get("oi_price_confirm_risk_restore_base_multiplier")
                    if sizing_snapshot.get("oi_price_confirm_risk_restore_base_multiplier") is not None
                    else self._current_streak_multiplier()
                ),
                "oi_price_confirm_risk_restore_multiplier": float(
                    sizing_snapshot.get("oi_price_confirm_risk_restore_multiplier")
                    if sizing_snapshot.get("oi_price_confirm_risk_restore_multiplier") is not None
                    else self.oi_price_confirm_risk_restore_multiplier
                ),
                "oi_price_confirm_risk_restore_effective_multiplier": float(
                    sizing_snapshot.get("oi_price_confirm_risk_restore_effective_multiplier")
                    or sizing_snapshot.get("risk_multiplier")
                    or self._current_streak_multiplier()
                ),
                "oi_price_confirm_entry_close": float(
                    sizing_snapshot.get("oi_price_confirm_entry_close")
                    if sizing_snapshot.get("oi_price_confirm_entry_close") is not None
                    else float("nan")
                ),
                "oi_price_confirm_prev_close": float(
                    sizing_snapshot.get("oi_price_confirm_prev_close")
                    if sizing_snapshot.get("oi_price_confirm_prev_close") is not None
                    else float("nan")
                ),
                "oi_price_confirm_entry_oi": float(
                    sizing_snapshot.get("oi_price_confirm_entry_oi")
                    if sizing_snapshot.get("oi_price_confirm_entry_oi") is not None
                    else float("nan")
                ),
                "oi_price_confirm_prev_oi": float(
                    sizing_snapshot.get("oi_price_confirm_prev_oi")
                    if sizing_snapshot.get("oi_price_confirm_prev_oi") is not None
                    else float("nan")
                ),
                "oi_price_confirm_oi_up": int(sizing_snapshot.get("oi_price_confirm_oi_up") or 0),
                "oi_price_confirm_price_aligned": int(
                    sizing_snapshot.get("oi_price_confirm_price_aligned") or 0
                ),
                "oi_price_confirm_recent_sum_ratio_required": int(
                    sizing_snapshot.get("oi_price_confirm_recent_sum_ratio_required") or 0
                ),
                "oi_price_confirm_recent_sum_days": int(
                    sizing_snapshot.get("oi_price_confirm_recent_sum_days") or 0
                ),
                "oi_price_confirm_recent_oi_sum": float(
                    sizing_snapshot.get("oi_price_confirm_recent_oi_sum")
                    if sizing_snapshot.get("oi_price_confirm_recent_oi_sum") is not None
                    else float("nan")
                ),
                "oi_price_confirm_prior_oi_sum": float(
                    sizing_snapshot.get("oi_price_confirm_prior_oi_sum")
                    if sizing_snapshot.get("oi_price_confirm_prior_oi_sum") is not None
                    else float("nan")
                ),
                "oi_price_confirm_recent_prior_oi_sum_ratio": float(
                    sizing_snapshot.get("oi_price_confirm_recent_prior_oi_sum_ratio")
                    if sizing_snapshot.get("oi_price_confirm_recent_prior_oi_sum_ratio") is not None
                    else float("nan")
                ),
                "oi_price_confirm_recent_sum_ratio_passed": int(
                    sizing_snapshot.get("oi_price_confirm_recent_sum_ratio_passed") or 0
                ),
                "oi_price_confirm_passed": int(sizing_snapshot.get("oi_price_confirm_passed") or 0),
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
                "streak_entry_structure_risk_recovery_directional_edge_enabled": int(
                    sizing_snapshot.get("streak_entry_structure_risk_recovery_directional_edge_enabled") or 0
                ),
                "streak_entry_structure_risk_recovery_directional_edge_period": int(
                    sizing_snapshot.get("streak_entry_structure_risk_recovery_directional_edge_period")
                    or self.streak_entry_structure_recovery_directional_edge_period
                    or 0
                ),
                "streak_entry_structure_risk_recovery_directional_edge_close_position": float(
                    sizing_snapshot.get("streak_entry_structure_risk_recovery_directional_edge_close_position")
                    if sizing_snapshot.get("streak_entry_structure_risk_recovery_directional_edge_close_position")
                    is not None
                    else float("nan")
                ),
                "streak_entry_structure_risk_recovery_directional_edge_long_min": float(
                    sizing_snapshot.get("streak_entry_structure_risk_recovery_directional_edge_long_min")
                    if sizing_snapshot.get("streak_entry_structure_risk_recovery_directional_edge_long_min") is not None
                    else self.streak_entry_structure_recovery_long_close_position_min
                ),
                "streak_entry_structure_risk_recovery_directional_edge_short_max": float(
                    sizing_snapshot.get("streak_entry_structure_risk_recovery_directional_edge_short_max")
                    if sizing_snapshot.get("streak_entry_structure_risk_recovery_directional_edge_short_max") is not None
                    else self.streak_entry_structure_recovery_short_close_position_max
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
                "recovery_sleeve_enabled": int(sizing_snapshot.get("recovery_sleeve_enabled") or 0),
                "recovery_sleeve_applied": int(sizing_snapshot.get("recovery_sleeve_applied") or 0),
                "recovery_sleeve_normal_risk_bypass_enabled": int(
                    sizing_snapshot.get("recovery_sleeve_normal_risk_bypass_enabled") or 0
                ),
                "recovery_sleeve_normal_risk_bypassed": int(
                    sizing_snapshot.get("recovery_sleeve_normal_risk_bypassed") or 0
                ),
                "recovery_sleeve_reason": str(sizing_snapshot.get("recovery_sleeve_reason") or ""),
                "recovery_sleeve_selected_volume_before": int(
                    sizing_snapshot.get("recovery_sleeve_selected_volume_before") or 0
                ),
                "recovery_sleeve_selected_volume_after": int(
                    sizing_snapshot.get("recovery_sleeve_selected_volume_after") or 0
                ),
                "recovery_sleeve_broker_margin_multiplier": float(
                    sizing_snapshot.get("recovery_sleeve_broker_margin_multiplier")
                    or self.recovery_sleeve_broker_margin_multiplier
                ),
                "recovery_sleeve_single_contract_broker_margin_to_equity": float(
                    sizing_snapshot.get("recovery_sleeve_single_contract_broker_margin_to_equity") or 0.0
                ),
                "recovery_sleeve_max_single_contract_broker_margin_to_equity": float(
                    sizing_snapshot.get("recovery_sleeve_max_single_contract_broker_margin_to_equity")
                    or self.recovery_sleeve_max_single_contract_broker_margin_to_equity
                ),
                "recovery_sleeve_cooldown_days": int(
                    sizing_snapshot.get("recovery_sleeve_cooldown_days") or self.recovery_sleeve_cooldown_days or 0
                ),
                "post_entry_quality_add_enabled": int(
                    sizing_snapshot.get("post_entry_quality_add_enabled") or 0
                ),
                "post_entry_quality_add_feature": str(
                    sizing_snapshot.get("post_entry_quality_add_feature") or ""
                ),
                "post_entry_quality_add_passed": int(sizing_snapshot.get("post_entry_quality_add_passed") or 0),
                "post_entry_quality_add_observation_bars": int(
                    sizing_snapshot.get("post_entry_quality_add_observation_bars") or 0
                ),
                "post_entry_quality_add_volume_multiplier": float(
                    sizing_snapshot.get("post_entry_quality_add_volume_multiplier") or 0.0
                ),
                "post_entry_quality_add_triggers_add_profit_lock": int(
                    sizing_snapshot.get("post_entry_quality_add_triggers_add_profit_lock") or 0
                ),
                "post_entry_quality_add_body60_ratio": float(
                    sizing_snapshot.get("post_entry_quality_add_body60_ratio") or 0.0
                ),
                "post_entry_quality_add_avg_body_pct": float(
                    sizing_snapshot.get("post_entry_quality_add_avg_body_pct") or 0.0
                ),
                "post_entry_quality_add_avg_directional_close_strength": float(
                    sizing_snapshot.get("post_entry_quality_add_avg_directional_close_strength") or 0.0
                ),
                "post_entry_quality_add_short30_ratio": float(
                    sizing_snapshot.get("post_entry_quality_add_short30_ratio") or 0.0
                ),
                "post_entry_quality_add_long60_ratio": float(
                    sizing_snapshot.get("post_entry_quality_add_long60_ratio") or 0.0
                ),
                "post_entry_quality_add_avg_adverse_wick_pct": float(
                    sizing_snapshot.get("post_entry_quality_add_avg_adverse_wick_pct") or 0.0
                ),
                "directional_30d_risk_boost_enabled": int(
                    sizing_snapshot.get("directional_30d_risk_boost_enabled") or 0
                ),
                "directional_30d_risk_boost_lookback": int(
                    sizing_snapshot.get("directional_30d_risk_boost_lookback") or 0
                ),
                "directional_30d_volume_confirmation_enabled": int(
                    sizing_snapshot.get("directional_30d_volume_confirmation_enabled") or 0
                ),
                "directional_30d_volume_recent_days": int(
                    sizing_snapshot.get("directional_30d_volume_recent_days") or 0
                ),
                "directional_30d_volume_prior_days": int(
                    sizing_snapshot.get("directional_30d_volume_prior_days") or 0
                ),
                "directional_30d_volume_ratio_threshold": sizing_snapshot.get(
                    "directional_30d_volume_ratio_threshold"
                ),
                "directional_30d_low_volume_discount_enabled": int(
                    sizing_snapshot.get("directional_30d_low_volume_discount_enabled") or 0
                ),
                "directional_30d_low_volume_ratio_threshold": sizing_snapshot.get(
                    "directional_30d_low_volume_ratio_threshold"
                ),
                "directional_30d_low_volume_risk_multiplier": sizing_snapshot.get(
                    "directional_30d_low_volume_risk_multiplier"
                ),
                "directional_30d_low_volume_discount_applied": int(
                    sizing_snapshot.get("directional_30d_low_volume_discount_applied") or 0
                ),
                "directional_30d_recent_volume_sum": sizing_snapshot.get(
                    "directional_30d_recent_volume_sum"
                ),
                "directional_30d_prior_volume_sum": sizing_snapshot.get(
                    "directional_30d_prior_volume_sum"
                ),
                "directional_30d_volume_expanding": int(
                    sizing_snapshot.get("directional_30d_volume_expanding") or 0
                ),
                "directional_30d_start_close": float(
                    sizing_snapshot.get("directional_30d_start_close")
                    if sizing_snapshot.get("directional_30d_start_close") is not None
                    else float("nan")
                ),
                "directional_30d_end_close": float(
                    sizing_snapshot.get("directional_30d_end_close")
                    if sizing_snapshot.get("directional_30d_end_close") is not None
                    else float("nan")
                ),
                "directional_30d_return": float(
                    sizing_snapshot.get("directional_30d_return")
                    if sizing_snapshot.get("directional_30d_return") is not None
                    else float("nan")
                ),
                "directional_30d_risk_boost_aligned": int(
                    sizing_snapshot.get("directional_30d_risk_boost_aligned") or 0
                ),
                "directional_30d_risk_boost_applied": int(
                    sizing_snapshot.get("directional_30d_risk_boost_applied") or 0
                ),
                "directional_30d_risk_nonconfirmation_multiplier": float(
                    sizing_snapshot.get("directional_30d_risk_nonconfirmation_multiplier") or 1.0
                ),
                "directional_30d_risk_adjust_long_only": int(
                    sizing_snapshot.get("directional_30d_risk_adjust_long_only") or 0
                ),
                "directional_30d_risk_boost_multiplier": float(
                    sizing_snapshot.get("directional_30d_risk_boost_multiplier") or 1.0
                ),
                "directional_30d_risk_boost_reason": str(
                    sizing_snapshot.get("directional_30d_risk_boost_reason") or ""
                ),
                "risk_amount_before_directional_30d_boost": sizing_snapshot.get(
                    "risk_amount_before_directional_30d_boost"
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
                "risk_cluster_cap_enabled": int(sizing_snapshot.get("risk_cluster_cap_enabled") or 0),
                "risk_cluster_name": str(sizing_snapshot.get("risk_cluster_name") or ""),
                "risk_cluster_cap_ratio": float(sizing_snapshot.get("risk_cluster_cap_ratio") or 0.0),
                "risk_cluster_cap_amount": float(sizing_snapshot.get("risk_cluster_cap_amount") or 0.0),
                "risk_cluster_reserved_margin_before": float(
                    sizing_snapshot.get("risk_cluster_reserved_margin_before") or 0.0
                ),
                "risk_cluster_max_volume": int(sizing_snapshot.get("risk_cluster_max_volume") or 0),
                "risk_cluster_selected_volume_before": int(
                    sizing_snapshot.get("risk_cluster_selected_volume_before") or 0
                ),
                "risk_cluster_selected_volume": int(sizing_snapshot.get("risk_cluster_selected_volume") or 0),
                "risk_cluster_heat_gate_enabled": int(
                    sizing_snapshot.get("risk_cluster_heat_gate_enabled") or 0
                ),
                "risk_cluster_heat_gate_weight": float(
                    sizing_snapshot.get("risk_cluster_heat_gate_weight") or 1.0
                ),
                "risk_cluster_heat_gate_pressure": float(
                    sizing_snapshot.get("risk_cluster_heat_gate_pressure") or 0.0
                ),
                "risk_cluster_heat_gate_selected_volume_before": int(
                    sizing_snapshot.get("risk_cluster_heat_gate_selected_volume_before") or 0
                ),
                "risk_cluster_heat_gate_selected_volume": int(
                    sizing_snapshot.get("risk_cluster_heat_gate_selected_volume") or 0
                ),
                "contracts_by_risk": sizing_snapshot.get("contracts_by_risk"),
                "contracts_by_margin": sizing_snapshot.get("contracts_by_margin"),
                "contracts_by_single_trade_cap": sizing_snapshot.get("contracts_by_single_trade_cap"),
                "selected_volume": sizing_snapshot.get("selected_volume"),
                "selected_volume_ungated": sizing_snapshot.get("selected_volume_ungated"),
                "incremental_margin_budget_gate_reduce_volume_enabled": int(
                    sizing_snapshot.get("incremental_margin_budget_gate_reduce_volume_enabled") or 0
                ),
                "incremental_margin_budget_gate_budget": float(
                    sizing_snapshot.get("incremental_margin_budget_gate_budget") or 0.0
                ),
                "incremental_margin_budget_gate_remaining_budget": float(
                    sizing_snapshot.get("incremental_margin_budget_gate_remaining_budget") or 0.0
                ),
                "incremental_margin_budget_gate_max_affordable_volume": int(
                    sizing_snapshot.get("incremental_margin_budget_gate_max_affordable_volume") or 0
                ),
                "incremental_margin_budget_gate_selected_volume_before": int(
                    sizing_snapshot.get("incremental_margin_budget_gate_selected_volume_before") or 0
                ),
                "incremental_margin_budget_gate_selected_volume_after": int(
                    sizing_snapshot.get("incremental_margin_budget_gate_selected_volume_after") or 0
                ),
                "incremental_margin_budget_gate_volume_reduced": int(
                    sizing_snapshot.get("incremental_margin_budget_gate_volume_reduced") or 0
                ),
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
                "portfolio_volatility_budget_enabled": int(
                    sizing_snapshot.get("portfolio_volatility_budget_enabled") or 0
                ),
                "portfolio_volatility_budget_weight": float(
                    sizing_snapshot.get("portfolio_volatility_budget_weight") or 1.0
                ),
                "portfolio_volatility_budget_realized_annual_vol": float(
                    sizing_snapshot.get("portfolio_volatility_budget_realized_annual_vol") or 0.0
                ),
                "portfolio_volatility_budget_lookback": int(
                    sizing_snapshot.get("portfolio_volatility_budget_lookback") or 0
                ),
                "portfolio_volatility_budget_target_annual_vol": float(
                    sizing_snapshot.get("portfolio_volatility_budget_target_annual_vol") or 0.0
                ),
                "rollover_reopen_drawdown_guard_enabled": int(
                    sizing_snapshot.get("rollover_reopen_drawdown_guard_enabled") or 0
                ),
                "rollover_reopen_drawdown_guard_passed": int(
                    sizing_snapshot.get("rollover_reopen_drawdown_guard_passed", 1) or 0
                ),
                "rollover_reopen_drawdown_guard_max_pct": float(
                    sizing_snapshot.get("rollover_reopen_drawdown_guard_max_pct") or 0.0
                ),
                "rollover_reopen_drawdown_guard_portfolio_drawdown_pct": float(
                    sizing_snapshot.get("rollover_reopen_drawdown_guard_portfolio_drawdown_pct")
                    or sizing_snapshot.get("portfolio_drawdown_pct")
                    or 0.0
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

        if self._should_relax_prev2day_stop_for_locked_trend(state, bar, history):
            self.profit_lock_trend_relaxed_prev2day_skip_count += 1
            return ""

        prev2_window = history.iloc[-3:-1]
        if len(prev2_window) < 2:
            return ""

        if state.direction == "long":
            raw_stop = float(prev2_window["low"].min())
            final_stop = raw_stop if state.prev2day_stop_price is None else max(state.prev2day_stop_price, raw_stop)
            state.prev2day_stop_price = final_stop
            if self._stop_triggered("long", bar, final_stop):
                if self._should_relax_prev2day_stop_for_post_quality(state, history):
                    state.post_quality_prev2day_relax_done = True
                    self.post_entry_quality_prev2day_relax_skip_count += 1
                    return ""
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
                if self._should_relax_prev2day_stop_for_post_quality(state, history):
                    state.post_quality_prev2day_relax_done = True
                    self.post_entry_quality_prev2day_relax_skip_count += 1
                    return ""
                exit_price = self._stop_execution_price("short", bar, final_stop)
                self._close_all_layers_and_set_flat_target(
                    state,
                    exit_price,
                    execution_price_override=exit_price,
                    exit_reason="short_prev2day_stop",
                )
                return "short_prev2day_stop"

        return ""

    def _should_relax_prev2day_stop_for_locked_trend(
        self,
        state: ProductState,
        bar: BarData,
        history: pd.DataFrame,
    ) -> bool:
        if not self.enable_profit_lock_trend_relaxed_prev2day_stop:
            return False
        if not state.layers:
            return False

        trigger_pct = max(float(self.profit_lock_trend_relax_trigger_pct or 0.0), 0.0)
        max_layer_profit = max(float(layer.max_profit_pct or 0.0) for layer in state.layers)
        if max_layer_profit < trigger_pct:
            return False

        fast_window = max(int(self.profit_lock_trend_relax_ma_fast or 0), 1)
        slow_window = max(int(self.profit_lock_trend_relax_ma_slow or 0), fast_window + 1)
        slope_days = max(int(self.profit_lock_trend_relax_slope_days or 0), 1)
        if len(history) < slow_window + slope_days + 1:
            return False

        closes = pd.to_numeric(history["close"], errors="coerce")
        fast_ma = closes.rolling(fast_window).mean()
        slow_ma = closes.rolling(slow_window).mean()
        fast_now = float(fast_ma.iloc[-1]) if not pd.isna(fast_ma.iloc[-1]) else float("nan")
        fast_prev = float(fast_ma.iloc[-1 - slope_days]) if not pd.isna(fast_ma.iloc[-1 - slope_days]) else float("nan")
        slow_now = float(slow_ma.iloc[-1]) if not pd.isna(slow_ma.iloc[-1]) else float("nan")
        close_price = float(bar.close_price)
        if not all(math.isfinite(value) for value in [fast_now, fast_prev, slow_now, close_price]):
            return False

        if state.direction == "long":
            return close_price > fast_now > slow_now and fast_now > fast_prev
        if state.direction == "short":
            return close_price < fast_now < slow_now and fast_now < fast_prev
        return False

    def _should_relax_prev2day_stop_for_post_quality(
        self,
        state: ProductState,
        history: pd.DataFrame,
    ) -> bool:
        if not self.enable_post_entry_quality_prev2day_relax:
            return False
        if state.post_quality_prev2day_relax_done or not state.layers or not state.direction:
            return False
        feature = str(self.post_entry_quality_prev2day_relax_feature or "").strip().lower()
        window = self._post_entry_quality_feature_window(feature)
        observed_history = history.iloc[:-1] if len(history) > 1 else history.iloc[0:0]
        if len(observed_history) < window:
            return False
        stats = self._post_entry_quality_candle_stats(observed_history, state.direction, window)
        return self._post_entry_quality_feature_passes(stats, feature=feature)

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

    def _process_risk_cluster_heat_deleverage(self, state: ProductState, bar: BarData) -> str:
        if not self.enable_risk_cluster_heat_deleverage:
            return ""
        if not state.layers or not state.contract_vt_symbol:
            return ""

        cluster: str = self._risk_cluster_for_symbol(state.contract_vt_symbol)
        if not self._risk_cluster_heat_deleverage_cluster_applies(cluster):
            return ""

        use_snapshot = bool(self.risk_cluster_heat_deleverage_use_daily_snapshot)
        if use_snapshot and self.risk_cluster_heat_deleverage_snapshot_requires_same_direction_multi:
            use_snapshot = bool(self.risk_cluster_same_direction_multi_snapshot.get(cluster, False))

        if use_snapshot:
            heat_pressure = float(self.risk_cluster_heat_pressure_snapshot.get(cluster, 0.0) or 0.0)
        else:
            heat_fields = self._risk_cluster_heat_pressure_fields(cluster, projected_margin=0.0, enabled=True)
            heat_pressure = float(heat_fields["risk_cluster_heat_pressure"] or 0.0)
        if heat_pressure < max(0.0, float(self.risk_cluster_heat_deleverage_min_pressure or 0.0)):
            return ""

        layer_kinds = self._risk_cluster_heat_deleverage_layer_kind_set()
        triggered_indexes = [index for index, layer in enumerate(state.layers) if layer.kind in layer_kinds]
        if not triggered_indexes:
            return ""

        contract_vt_symbol = state.contract_vt_symbol
        product_vt_symbol = state.product_vt_symbol
        direction = state.direction
        exit_price = float(bar.close_price)
        closed_volume = sum(state.layers[index].volume for index in triggered_indexes)
        exit_reason = f"{direction}_risk_cluster_heat_deleverage"
        self._close_layers(state, triggered_indexes, exit_price, exit_reason=exit_reason)
        self.risk_cluster_heat_deleverage_count += 1
        self._record_trade_event(
            bar=bar,
            contract_vt_symbol=contract_vt_symbol,
            product_vt_symbol=product_vt_symbol,
            position_direction=direction,
            offset="Close",
            reason=exit_reason,
            volume=closed_volume,
            price=exit_price,
        )
        if state.layers:
            self._apply_state_target(state, execution_price_override=exit_price)
        else:
            if exit_price > 0:
                self.execution_price_overrides[contract_vt_symbol] = exit_price
            self.set_target(contract_vt_symbol, 0)
        return exit_reason

    def _refresh_portfolio_margin_deleverage_state(self) -> None:
        if not self.enable_portfolio_margin_deleverage:
            self.portfolio_margin_deleverage_pressure = 0.0
            self.portfolio_margin_deleverage_ratio = 0.0
            return
        equity = max(1e-9, float(self.estimated_equity or self.base_capital))
        broker_multiplier = max(0.0, float(self.portfolio_margin_deleverage_broker_multiplier or 1.0))
        margin_ratio = max(0.0, float(self.total_margin_in_use or 0.0)) * broker_multiplier / equity
        self.portfolio_margin_deleverage_ratio = margin_ratio
        self.portfolio_margin_deleverage_pressure = self._linear_pressure(
            margin_ratio,
            float(self.portfolio_margin_deleverage_start_ratio or 0.0),
            float(self.portfolio_margin_deleverage_full_ratio or 0.0),
        )

    def _portfolio_margin_deleverage_layer_kind_set(self) -> set[str]:
        kinds = {
            item.strip()
            for item in str(self.portfolio_margin_deleverage_layer_kinds or "").replace(";", ",").split(",")
            if item.strip()
        }
        return kinds or {"add", "donchian", "post_quality"}

    def _forced_margin_deleverage_candidates(self, bars: dict[str, BarData]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for state in self.states.values():
            if not state.layers or not state.contract_vt_symbol:
                continue
            bar: BarData | None = bars.get(state.contract_vt_symbol)
            if bar is None:
                continue
            volume: int = state.active_volume()
            if volume <= 0:
                continue
            size: int = self.get_size(state.contract_vt_symbol)
            close_price: float = float(bar.close_price)
            margin_ratio: float = self._margin_ratio_for_symbol(state.contract_vt_symbol)
            margin_per_contract: float = max(0.0, close_price * size * margin_ratio)
            if margin_per_contract <= 0:
                continue
            unrealized_pnl: float = 0.0
            for layer in state.layers:
                if layer.direction == "long":
                    unrealized_pnl += (close_price - float(layer.entry_price)) * size * int(layer.volume)
                else:
                    unrealized_pnl += (float(layer.entry_price) - close_price) * size * int(layer.volume)
            rows.append(
                {
                    "state": state,
                    "bar": bar,
                    "volume": volume,
                    "margin_per_contract": margin_per_contract,
                    "margin": margin_per_contract * volume,
                    "unrealized_pnl": unrealized_pnl,
                }
            )
        priority = str(self.forced_margin_deleverage_priority or "largest_margin").strip().lower()
        if priority == "largest_unrealized_loss":
            rows.sort(key=lambda row: (float(row["unrealized_pnl"]), -float(row["margin"])))
        elif priority == "largest_volume":
            rows.sort(key=lambda row: (-int(row["volume"]), -float(row["margin"])))
        else:
            rows.sort(key=lambda row: (-float(row["margin"]), float(row["unrealized_pnl"])))
        return rows

    def _process_forced_margin_deleverage(self, bars: dict[str, BarData]) -> None:
        if not self.enable_forced_margin_deleverage:
            self.forced_margin_deleverage_ratio = 0.0
            return
        if not bars:
            return

        trigger_ratio: float = max(0.0, float(self.forced_margin_deleverage_trigger_ratio or 0.0))
        target_ratio: float = max(0.0, float(self.forced_margin_deleverage_target_ratio or 0.0))
        if trigger_ratio <= 0.0 or target_ratio <= 0.0:
            return
        target_ratio = min(target_ratio, trigger_ratio)
        broker_multiplier: float = max(0.0, float(self.forced_margin_deleverage_broker_multiplier or 1.0))
        if broker_multiplier <= 0.0:
            return

        equity: float = max(1e-9, float(self.estimated_equity or self.base_capital))
        max_reductions: int = max(1, int(self.forced_margin_deleverage_max_reductions_per_day or 1))
        reductions: int = 0

        while reductions < max_reductions:
            current_margin: float = self._estimate_margin_usage(bars)
            current_ratio: float = current_margin * broker_multiplier / equity
            self.forced_margin_deleverage_ratio = current_ratio
            self.forced_margin_deleverage_max_observed_ratio = max(
                self.forced_margin_deleverage_max_observed_ratio,
                current_ratio,
            )
            if current_ratio <= trigger_ratio + 1e-12:
                break

            target_margin: float = equity * target_ratio / broker_multiplier
            margin_to_release: float = max(0.0, current_margin - target_margin)
            candidates = self._forced_margin_deleverage_candidates(bars)
            if not candidates:
                break

            candidate = candidates[0]
            state: ProductState = candidate["state"]
            bar: BarData = candidate["bar"]
            volume: int = int(candidate["volume"])
            margin_per_contract: float = max(1e-9, float(candidate["margin_per_contract"]))
            reduce_volume: int = min(volume, max(1, int(math.ceil(margin_to_release / margin_per_contract))))
            target_volume: int = max(0, volume - reduce_volume)
            close_price: float = float(bar.close_price)
            direction: str = state.direction
            contract_vt_symbol: str = state.contract_vt_symbol
            product_vt_symbol: str = state.product_vt_symbol
            reason = "forced_margin_deleverage"

            self._record_trade_event(
                bar=bar,
                contract_vt_symbol=contract_vt_symbol,
                product_vt_symbol=product_vt_symbol,
                position_direction=direction,
                offset="Close",
                reason=reason,
                volume=reduce_volume,
                price=close_price,
            )
            ratio_before = current_ratio
            self._reduce_position_to_target(state, target_volume, close_price)
            if state.layers:
                self._apply_state_target(state, execution_price_override=close_price)
            else:
                if close_price > 0:
                    self.execution_price_overrides[contract_vt_symbol] = close_price
                self.set_target(contract_vt_symbol, 0)

            ratio_after: float = self._estimate_margin_usage(bars) * broker_multiplier / equity
            reductions += 1
            self.forced_margin_deleverage_count += 1
            self.forced_margin_deleverage_closed_volume += reduce_volume
            self.forced_margin_deleverage_ratio = ratio_after
            self.forced_margin_deleverage_events.append(
                {
                    "datetime": bar.datetime,
                    "date": bar.datetime.date(),
                    "vt_symbol": contract_vt_symbol,
                    "product_vt_symbol": product_vt_symbol,
                    "direction": direction,
                    "priority": str(self.forced_margin_deleverage_priority or "largest_margin"),
                    "trigger_ratio": trigger_ratio,
                    "target_ratio": target_ratio,
                    "broker_multiplier": broker_multiplier,
                    "equity": equity,
                    "margin_before": current_margin,
                    "ratio_before": ratio_before,
                    "margin_per_contract": margin_per_contract,
                    "reduce_volume": reduce_volume,
                    "volume_before": volume,
                    "volume_after": target_volume,
                    "price": close_price,
                    "margin_after": self._estimate_margin_usage(bars),
                    "ratio_after": ratio_after,
                }
            )

    def _process_portfolio_margin_deleverage(self, state: ProductState, bar: BarData) -> str:
        if not self.enable_portfolio_margin_deleverage:
            return ""
        if not state.layers or not state.contract_vt_symbol:
            return ""
        pressure = float(self.portfolio_margin_deleverage_pressure or 0.0)
        if pressure < max(0.0, float(self.portfolio_margin_deleverage_min_pressure or 0.0)):
            return ""

        layer_kinds = self._portfolio_margin_deleverage_layer_kind_set()
        triggered_indexes = [index for index, layer in enumerate(state.layers) if layer.kind in layer_kinds]
        if not triggered_indexes:
            return ""

        contract_vt_symbol = state.contract_vt_symbol
        product_vt_symbol = state.product_vt_symbol
        direction = state.direction
        exit_price = float(bar.close_price)
        closed_volume = sum(state.layers[index].volume for index in triggered_indexes)
        exit_reason = f"{direction}_portfolio_margin_deleverage"
        self._close_layers(state, triggered_indexes, exit_price, exit_reason=exit_reason)
        self.portfolio_margin_deleverage_count += 1
        self._record_trade_event(
            bar=bar,
            contract_vt_symbol=contract_vt_symbol,
            product_vt_symbol=product_vt_symbol,
            position_direction=direction,
            offset="Close",
            reason=exit_reason,
            volume=closed_volume,
            price=exit_price,
        )
        if state.layers:
            self._apply_state_target(state, execution_price_override=exit_price)
        else:
            if exit_price > 0:
                self.execution_price_overrides[contract_vt_symbol] = exit_price
            self.set_target(contract_vt_symbol, 0)
        return exit_reason

    def _process_portfolio_drawdown_deleverage(self, state: ProductState, bar: BarData) -> str:
        if not self.enable_portfolio_drawdown_deleverage:
            return ""
        if not state.layers or not state.contract_vt_symbol:
            return ""

        weight = self._portfolio_drawdown_gate_weight_value()
        if weight >= 0.999:
            state.portfolio_drawdown_gate_reference_contract = ""
            state.portfolio_drawdown_gate_reference_volume = 0
            return ""

        current_volume = state.active_volume()
        if current_volume <= 0:
            return ""

        if state.portfolio_drawdown_gate_reference_contract != state.contract_vt_symbol:
            state.portfolio_drawdown_gate_reference_contract = state.contract_vt_symbol
            state.portfolio_drawdown_gate_reference_volume = current_volume
        elif state.portfolio_drawdown_gate_reference_volume < current_volume:
            state.portfolio_drawdown_gate_reference_volume = current_volume

        reference_volume = max(current_volume, int(state.portfolio_drawdown_gate_reference_volume or 0))
        target_volume = int(math.floor(reference_volume * weight))
        if 0 < target_volume < self.min_position_size:
            target_volume = 0
        if target_volume >= current_volume:
            return ""

        contract_vt_symbol = state.contract_vt_symbol
        product_vt_symbol = state.product_vt_symbol
        direction = state.direction
        exit_price = float(bar.close_price)
        closed_volume = current_volume - max(0, target_volume)
        exit_reason = f"{direction}_portfolio_drawdown_deleverage"
        self._record_trade_event(
            bar=bar,
            contract_vt_symbol=contract_vt_symbol,
            product_vt_symbol=product_vt_symbol,
            position_direction=direction,
            offset="Close",
            reason=exit_reason,
            volume=closed_volume,
            price=exit_price,
        )
        self._reduce_position_to_target(state, max(0, target_volume), exit_price)
        self.portfolio_drawdown_deleverage_count += 1
        if state.layers:
            self._apply_state_target(state, execution_price_override=exit_price)
        else:
            if exit_price > 0:
                self.execution_price_overrides[contract_vt_symbol] = exit_price
            self.set_target(contract_vt_symbol, 0)
        return exit_reason

    def _process_portfolio_volatility_budget_deleverage(self, state: ProductState, bar: BarData) -> str:
        if not (self.enable_portfolio_volatility_budget and self.enable_portfolio_volatility_budget_deleverage):
            return ""
        if not state.layers or not state.contract_vt_symbol:
            return ""

        weight = self._clip01(float(self.portfolio_volatility_budget_scale or 1.0))
        if weight >= 0.999:
            state.portfolio_volatility_budget_reference_contract = ""
            state.portfolio_volatility_budget_reference_volume = 0
            return ""

        current_volume = state.active_volume()
        if current_volume <= 0:
            return ""

        if state.portfolio_volatility_budget_reference_contract != state.contract_vt_symbol:
            state.portfolio_volatility_budget_reference_contract = state.contract_vt_symbol
            state.portfolio_volatility_budget_reference_volume = current_volume
        elif state.portfolio_volatility_budget_reference_volume < current_volume:
            state.portfolio_volatility_budget_reference_volume = current_volume

        reference_volume = max(current_volume, int(state.portfolio_volatility_budget_reference_volume or 0))
        target_volume = int(math.floor(reference_volume * weight))
        if 0 < target_volume < self.min_position_size:
            target_volume = 0
        if target_volume >= current_volume:
            return ""

        contract_vt_symbol = state.contract_vt_symbol
        product_vt_symbol = state.product_vt_symbol
        direction = state.direction
        exit_price = float(bar.close_price)
        closed_volume = current_volume - max(0, target_volume)
        exit_reason = f"{direction}_portfolio_volatility_budget_deleverage"
        self._record_trade_event(
            bar=bar,
            contract_vt_symbol=contract_vt_symbol,
            product_vt_symbol=product_vt_symbol,
            position_direction=direction,
            offset="Close",
            reason=exit_reason,
            volume=closed_volume,
            price=exit_price,
        )
        self._reduce_position_to_target(state, max(0, target_volume), exit_price)
        self.portfolio_volatility_budget_deleverage_count += 1
        if state.layers:
            self._apply_state_target(state, execution_price_override=exit_price)
        else:
            if exit_price > 0:
                self.execution_price_overrides[contract_vt_symbol] = exit_price
            self.set_target(contract_vt_symbol, 0)
        return exit_reason

    def _process_portfolio_overheat_cooldown_deleverage(self, state: ProductState, bar: BarData) -> str:
        if not (self.enable_portfolio_overheat_cooldown and self.enable_portfolio_overheat_cooldown_deleverage):
            return ""
        if not state.layers or not state.contract_vt_symbol:
            return ""

        weight = self._portfolio_overheat_cooldown_scale_value()
        if weight >= 0.999:
            state.portfolio_overheat_cooldown_reference_contract = ""
            state.portfolio_overheat_cooldown_reference_volume = 0
            return ""

        current_volume = state.active_volume()
        if current_volume <= 0:
            return ""

        if state.portfolio_overheat_cooldown_reference_contract != state.contract_vt_symbol:
            state.portfolio_overheat_cooldown_reference_contract = state.contract_vt_symbol
            state.portfolio_overheat_cooldown_reference_volume = current_volume
        elif state.portfolio_overheat_cooldown_reference_volume < current_volume:
            state.portfolio_overheat_cooldown_reference_volume = current_volume

        reference_volume = max(current_volume, int(state.portfolio_overheat_cooldown_reference_volume or 0))
        target_volume = int(math.floor(reference_volume * weight))
        if 0 < target_volume < self.min_position_size:
            target_volume = 0
        if target_volume >= current_volume:
            return ""

        contract_vt_symbol = state.contract_vt_symbol
        product_vt_symbol = state.product_vt_symbol
        direction = state.direction
        exit_price = float(bar.close_price)
        closed_volume = current_volume - max(0, target_volume)
        exit_reason = f"{direction}_portfolio_overheat_cooldown_deleverage"
        self._record_trade_event(
            bar=bar,
            contract_vt_symbol=contract_vt_symbol,
            product_vt_symbol=product_vt_symbol,
            position_direction=direction,
            offset="Close",
            reason=exit_reason,
            volume=closed_volume,
            price=exit_price,
        )
        self._reduce_position_to_target(state, max(0, target_volume), exit_price)
        self.portfolio_overheat_cooldown_deleverage_count += 1
        if state.layers:
            self._apply_state_target(state, execution_price_override=exit_price)
        else:
            if exit_price > 0:
                self.execution_price_overrides[contract_vt_symbol] = exit_price
            self.set_target(contract_vt_symbol, 0)
        return exit_reason

    def _update_dynamic_stops(self, state: ProductState, bar: BarData, history: pd.DataFrame) -> None:
        for layer in state.layers:
            self._update_layer_stop(layer, bar)
        if self.atr_2x_mid_stop_enabled:
            self._apply_atr_mid_stop(state, bar, history)
        profit_lock_layer_kinds = {"add", "donchian"}
        if self.post_entry_quality_add_triggers_add_profit_lock:
            profit_lock_layer_kinds.add("post_quality")
        has_profit_lock_layer = any(layer.kind in profit_lock_layer_kinds for layer in state.layers)
        if has_profit_lock_layer and state.active_volume() > state.base_volume():
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

        if layer.kind in {"add", "donchian", "post_quality"}:
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
        thresholds: list[tuple[float, float]] = self._profit_lock_thresholds()
        for trigger_pct, lock_pct in thresholds:
            if layer.max_profit_pct >= trigger_pct:
                return layer.entry_price * (1 + lock_pct) if layer.direction == "long" else layer.entry_price * (1 - lock_pct)
        return None

    def _profit_lock_thresholds(self) -> list[tuple[float, float]]:
        default_thresholds: list[tuple[float, float]] = [
            (0.30, 0.20),
            (0.20, 0.15),
            (0.10, 0.08),
            (0.05, 0.03),
            (0.03, 0.01),
            (0.02, 0.001),
        ]
        raw_tiers = str(self.profit_lock_tiers or "").strip()
        if not raw_tiers:
            return default_thresholds

        parsed: list[tuple[float, float]] = []
        for raw_item in raw_tiers.split(","):
            raw_item = raw_item.strip()
            if not raw_item or ":" not in raw_item:
                continue
            trigger_text, lock_text = raw_item.split(":", 1)
            try:
                trigger_pct = max(0.0, float(trigger_text.strip()))
                lock_pct = max(0.0, float(lock_text.strip()))
            except ValueError:
                continue
            if trigger_pct <= 0 or lock_pct <= 0 or lock_pct > trigger_pct:
                continue
            parsed.append((trigger_pct, lock_pct))

        if not parsed:
            return default_thresholds
        parsed = sorted(set(parsed), key=lambda item: item[0], reverse=True)
        return parsed

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
            layer_realized = self._layer_realized_pnl(layer, exit_price, size)
            realized += layer_realized
            self._record_product_direction_outcome(
                state.product_vt_symbol,
                layer.direction,
                layer_realized,
            )
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
            closed_layer = PositionLayer(
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
            )
            layer_realized = self._layer_realized_pnl(
                closed_layer,
                exit_price,
                size,
            )
            realized += layer_realized
            self._record_product_direction_outcome(
                state.product_vt_symbol,
                closed_layer.direction,
                layer_realized,
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

    def _post_entry_quality_feature_window(self, feature: str) -> int:
        text = str(feature or "").strip().lower()
        if not text.startswith("post"):
            return 1
        digits = []
        for char in text[4:]:
            if char.isdigit():
                digits.append(char)
            else:
                break
        if not digits:
            return 1
        return max(1, int("".join(digits)))

    def _post_entry_quality_add_window(self) -> int:
        return self._post_entry_quality_feature_window(str(self.post_entry_quality_add_feature or ""))

    def _post_entry_quality_candle_stats(
        self,
        history: pd.DataFrame,
        direction: str,
        window: int,
    ) -> dict[str, float]:
        if len(history) < window:
            return {}
        bars = history.tail(window).copy()
        open_price = pd.to_numeric(bars["open"], errors="coerce")
        high_price = pd.to_numeric(bars["high"], errors="coerce")
        low_price = pd.to_numeric(bars["low"], errors="coerce")
        close_price = pd.to_numeric(bars["close"], errors="coerce")
        bar_range = (high_price - low_price).replace(0.0, np.nan)
        body_pct = (close_price - open_price).abs() / bar_range
        close_position = (close_price - low_price) / bar_range
        upper_wick_pct = (high_price - pd.concat([open_price, close_price], axis=1).max(axis=1)) / bar_range
        lower_wick_pct = (pd.concat([open_price, close_price], axis=1).min(axis=1) - low_price) / bar_range
        total_wick_pct = upper_wick_pct + lower_wick_pct
        if direction == "long":
            directional_close_strength = close_position
            adverse_wick_pct = upper_wick_pct
        elif direction == "short":
            directional_close_strength = 1.0 - close_position
            adverse_wick_pct = lower_wick_pct
        else:
            return {}
        return {
            "observation_bars": float(window),
            "body60_ratio": float(body_pct.ge(float(self.post_entry_quality_add_body_pct_min)).mean()),
            "avg_body_pct": float(body_pct.mean()),
            "avg_directional_close_strength": float(directional_close_strength.mean()),
            "short30_ratio": float(total_wick_pct.le(0.30).mean()),
            "long60_ratio": float(total_wick_pct.ge(0.60).mean()),
            "avg_adverse_wick_pct": float(adverse_wick_pct.mean()),
        }

    def _post_entry_quality_feature_passes(self, stats: dict[str, float], feature: str | None = None) -> bool:
        if not stats:
            return False
        if feature is None:
            feature = str(self.post_entry_quality_add_feature or "")
        feature = str(feature or "").strip().lower()
        suffix = feature
        window = self._post_entry_quality_feature_window(feature)
        prefix = f"post{window}_"
        if suffix.startswith(prefix):
            suffix = suffix[len(prefix) :]

        body_ratio = float(stats.get("body60_ratio", 0.0) or 0.0)
        avg_body = float(stats.get("avg_body_pct", 0.0) or 0.0)
        avg_strength = float(stats.get("avg_directional_close_strength", 0.0) or 0.0)
        short30_ratio = float(stats.get("short30_ratio", 0.0) or 0.0)
        long60_ratio = float(stats.get("long60_ratio", 0.0) or 0.0)
        adverse_wick = float(stats.get("avg_adverse_wick_pct", 0.0) or 0.0)

        if suffix == "body60_ratio_ge50":
            return body_ratio >= float(self.post_entry_quality_add_body_ratio_min)
        if suffix == "avg_directional_close_strength_ge60":
            return avg_strength >= float(self.post_entry_quality_add_directional_close_strength_min)
        if suffix == "short30_ratio_ge50":
            return short30_ratio >= float(self.post_entry_quality_add_short_wick_ratio_min)
        if suffix == "long60_ratio_le20":
            return long60_ratio <= float(self.post_entry_quality_add_long_wick_ratio_max)
        if suffix == "avg_adverse_wick_le25":
            return adverse_wick <= float(self.post_entry_quality_add_adverse_wick_pct_max)
        if suffix == "smooth_directional_combo":
            return (
                body_ratio >= float(self.post_entry_quality_add_body_ratio_min)
                and avg_strength >= float(self.post_entry_quality_add_directional_close_strength_min)
                and adverse_wick <= float(self.post_entry_quality_add_adverse_wick_pct_max)
            )
        if suffix == "clean_shadow_combo":
            return (
                short30_ratio >= float(self.post_entry_quality_add_short_wick_ratio_min)
                and long60_ratio <= float(self.post_entry_quality_add_long_wick_ratio_max)
                and avg_body >= float(self.post_entry_quality_add_body_pct_min)
            )
        return False

    def _check_post_entry_quality_add_conditions(
        self,
        state: ProductState,
        bar: BarData,
        history: pd.DataFrame,
    ) -> tuple[bool, str | None, dict[str, float]]:
        if not self.enable_post_entry_quality_add or not state.layers or not state.direction:
            return False, None, {}
        add_count = self._count_layers(state, "post_quality")
        if add_count >= max(1, int(self.post_entry_quality_add_max_layers)):
            return False, None, {}
        window = self._post_entry_quality_add_window()
        if state.bars_since_entry != window or len(history) < window:
            return False, None, {}
        today_key = self._bar_date(bar)
        if (
            state.entry_date == today_key
            or state.rollover_opened_today == today_key
            or state.last_post_quality_add_date == today_key
        ):
            return False, None, {}
        stats = self._post_entry_quality_candle_stats(history, state.direction, window)
        if not self._post_entry_quality_feature_passes(stats):
            return False, None, stats
        feature = str(self.post_entry_quality_add_feature or "").strip().lower()
        signal = f"post_quality_add_{feature or 'unknown'}"
        return True, signal, stats

    def _calculate_post_entry_quality_add_volume(self, state: ProductState) -> int:
        base_volume = max(0, int(state.base_volume()))
        multiplier = max(0.0, float(self.post_entry_quality_add_volume_multiplier or 0.0))
        volume = int(math.floor(base_volume * multiplier + 1e-12))
        return min(max(0, volume), self.max_position_size)

    def _calculate_directional_boosted_add_sizing(
        self,
        state: ProductState,
        bar: BarData,
        history: pd.DataFrame,
        entry_context: str,
    ) -> tuple[int, dict[str, Any]]:
        if entry_context == "post_quality_add":
            base_volume = self._calculate_post_entry_quality_add_volume(state)
            use_day_extreme_stop = bool(self.post_entry_quality_add_use_day_extreme_stop)
        elif entry_context == "regular_add":
            base_volume = self._calculate_regular_add_volume(state)
            use_day_extreme_stop = bool(self.regular_add_use_day_extreme_stop)
        elif entry_context == "donchian_add":
            base_volume = self._calculate_donchian_add_volume(state)
            use_day_extreme_stop = True
        else:
            raise ValueError(f"unsupported directional boost add context: {entry_context}")

        snapshot = self._directional_30d_risk_boost_snapshot(state.direction, history)
        contract_vt_symbol = state.contract_vt_symbol
        stop_price = self._entry_stop_price(
            state.direction,
            bar,
            history,
            use_day_extreme=use_day_extreme_stop,
        )
        size = self.get_size(contract_vt_symbol)
        min_risk = max(float(self.get_pricetick(contract_vt_symbol)) * size, 1.0)
        risk_per_contract = max(abs(float(bar.close_price) - stop_price) * size, min_risk)
        risk_amount_before_boost = float(base_volume) * risk_per_contract
        target_risk_amount = risk_amount_before_boost * float(
            snapshot["directional_30d_risk_boost_multiplier"]
        )
        boosted_volume = (
            int(math.floor(target_risk_amount / risk_per_contract + 1e-12))
            if risk_per_contract > 0
            else 0
        )
        boosted_volume = min(max(0, boosted_volume), self.max_position_size)
        margin_ratio = self._margin_ratio_for_symbol(contract_vt_symbol)
        margin_per_contract = float(bar.close_price) * size * margin_ratio
        snapshot.update(
            {
                "entry_context": entry_context,
                "risk_amount_before_directional_30d_boost": risk_amount_before_boost,
                "risk_amount": target_risk_amount,
                "risk_per_contract": risk_per_contract,
                "margin_ratio": margin_ratio,
                "margin_per_contract": margin_per_contract,
                "selected_volume_before_directional_30d_boost": int(base_volume),
                "selected_volume_after_directional_30d_boost": int(boosted_volume),
            }
        )
        return boosted_volume, snapshot

    def _execute_post_entry_quality_add(
        self,
        state: ProductState,
        bar: BarData,
        signal: str,
        volume: int,
        history: pd.DataFrame,
        stats: dict[str, float],
        *,
        sizing_snapshot_extra: dict[str, Any] | None = None,
    ) -> None:
        snapshot_extra = {
            "post_entry_quality_add_enabled": int(self.enable_post_entry_quality_add),
            "post_entry_quality_add_feature": str(self.post_entry_quality_add_feature or ""),
            "post_entry_quality_add_passed": 1,
            "post_entry_quality_add_observation_bars": int(stats.get("observation_bars", 0.0) or 0.0),
            "post_entry_quality_add_volume_multiplier": float(self.post_entry_quality_add_volume_multiplier or 0.0),
            "post_entry_quality_add_triggers_add_profit_lock": int(
                self.post_entry_quality_add_triggers_add_profit_lock
            ),
            "post_entry_quality_add_body60_ratio": float(stats.get("body60_ratio", 0.0) or 0.0),
            "post_entry_quality_add_avg_body_pct": float(stats.get("avg_body_pct", 0.0) or 0.0),
            "post_entry_quality_add_avg_directional_close_strength": float(
                stats.get("avg_directional_close_strength", 0.0) or 0.0
            ),
            "post_entry_quality_add_short30_ratio": float(stats.get("short30_ratio", 0.0) or 0.0),
            "post_entry_quality_add_long60_ratio": float(stats.get("long60_ratio", 0.0) or 0.0),
            "post_entry_quality_add_avg_adverse_wick_pct": float(stats.get("avg_adverse_wick_pct", 0.0) or 0.0),
        }
        if sizing_snapshot_extra:
            snapshot_extra.update(sizing_snapshot_extra)
        self._append_layer(
            state,
            "post_quality",
            volume,
            bar,
            signal,
            history,
            self.post_entry_quality_add_use_day_extreme_stop,
            sizing_snapshot_extra=snapshot_extra,
        )
        state.last_post_quality_add_date = self._bar_date(bar)
        state.last_signal = signal
        self.post_entry_quality_add_count += 1
        if self.post_entry_quality_add_triggers_add_profit_lock:
            self._apply_add_position_profit_lock(state)

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

    def _execute_regular_add(
        self,
        state: ProductState,
        bar: BarData,
        signal: str,
        volume: int,
        history: pd.DataFrame,
        *,
        sizing_snapshot_extra: dict[str, Any] | None = None,
    ) -> None:
        self._append_layer(
            state,
            "add",
            volume,
            bar,
            signal,
            history,
            self.regular_add_use_day_extreme_stop,
            sizing_snapshot_extra=sizing_snapshot_extra,
        )
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

    def _execute_donchian_add(
        self,
        state: ProductState,
        bar: BarData,
        signal: str,
        volume: int,
        history: pd.DataFrame,
        *,
        sizing_snapshot_extra: dict[str, Any] | None = None,
    ) -> None:
        self._append_layer(
            state,
            "donchian",
            volume,
            bar,
            signal,
            history,
            True,
            sizing_snapshot_extra=sizing_snapshot_extra,
        )
        state.last_donchian_add_date = self._bar_date(bar)
        state.last_signal = signal
        self._apply_add_position_profit_lock(state)

    def _can_allocate_margin(self, vt_symbol: str, volume: int, price: float) -> bool:
        margin_ratio = self._margin_ratio_for_symbol(vt_symbol)
        projected_margin = price * self.get_size(vt_symbol) * volume * margin_ratio
        allowed_capital = self._allowed_capital()
        if (self._reserved_margin_in_use() + projected_margin) > allowed_capital:
            return False
        if not self.enable_risk_cluster_margin_cap:
            return True
        cluster = self._risk_cluster_for_symbol(vt_symbol)
        if not self._cluster_cap_applies(cluster):
            return True
        cap = max(0.0, self._sizing_equity() * float(self.risk_cluster_margin_cap_ratio or 0.0))
        return (self._reserved_cluster_margin(cluster) + projected_margin) <= cap

    def _risk_cluster_heat_gate_adjust_add_volume(
        self,
        vt_symbol: str,
        volume: int,
        price: float,
        entry_context: str,
    ) -> int:
        if not self.enable_risk_cluster_heat_gate:
            return max(0, int(volume))
        margin_ratio = self._margin_ratio_for_symbol(vt_symbol)
        margin_per_contract = float(price) * self.get_size(vt_symbol) * margin_ratio
        fields = self._apply_risk_cluster_heat_gate_to_volume(
            vt_symbol,
            max(0, int(volume)),
            margin_per_contract,
            entry_context,
        )
        return max(0, int(fields["risk_cluster_heat_gate_selected_volume"]))

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

    def _build_observed_array_manager_history(self, am: ArrayManager) -> pd.DataFrame:
        history = self._build_history_df(am)
        observed_count = min(max(0, int(getattr(am, "count", 0) or 0)), len(history))
        if observed_count <= 0:
            return history.iloc[0:0].copy()
        return history.tail(observed_count).reset_index(drop=True)

    def _rollover_target_readiness_snapshot(
        self,
        *,
        target_contract: str,
        new_bar: BarData | None,
        target_bar_from_current: bool,
    ) -> dict[str, Any]:
        same_day_bar_ready = bool(new_bar is not None and target_bar_from_current)
        market_data_ready = False
        if new_bar is not None:
            prices = [
                float(new_bar.open_price),
                float(new_bar.high_price),
                float(new_bar.low_price),
                float(new_bar.close_price),
            ]
            market_data_ready = bool(
                all(np.isfinite(value) and value > 0 for value in prices)
                and prices[1] >= max(prices[0], prices[2], prices[3])
                and prices[2] <= min(prices[0], prices[1], prices[3])
                and np.isfinite(float(new_bar.volume))
                and float(new_bar.volume) > 0
            )

        try:
            contract_size = int(self.get_size(target_contract))
        except Exception:
            contract_size = 0
        try:
            price_tick = float(self.get_pricetick(target_contract))
        except Exception:
            price_tick = 0.0
        try:
            margin_ratio = float(self._margin_ratio_for_symbol(target_contract))
        except Exception:
            margin_ratio = 0.0
        metadata_ready = bool(
            contract_size > 0
            and np.isfinite(price_tick)
            and price_tick > 0
            and np.isfinite(margin_ratio)
            and margin_ratio > 0
        )

        if new_bar is None:
            readiness_reason = "target_same_day_bar_missing"
        elif not same_day_bar_ready:
            readiness_reason = "target_bar_not_same_day"
        elif not market_data_ready:
            readiness_reason = "target_same_day_market_not_tradable"
        elif not metadata_ready:
            readiness_reason = "target_contract_metadata_incomplete"
        else:
            readiness_reason = "ready"
        return {
            "same_day_bar_ready": int(same_day_bar_ready),
            "market_data_ready": int(market_data_ready),
            "metadata_ready": int(metadata_ready),
            "target_contract_size": int(contract_size),
            "target_price_tick": float(price_tick),
            "target_margin_ratio": float(margin_ratio),
            "target_readiness_reason": readiness_reason,
        }

    def _build_rollover_shape_history(
        self,
        *,
        old_contract: str,
        target_contract: str,
        old_bar: BarData,
        new_bar: BarData | None,
        target_am: ArrayManager | None,
        target_bar_from_current: bool,
    ) -> tuple[pd.DataFrame, dict[str, Any]]:
        history_mode = str(self.rollover_shape_history_mode or "").strip().lower()
        target_history = (
            self._build_observed_array_manager_history(target_am)
            if target_am is not None
            else pd.DataFrame(columns=["open", "high", "low", "close", "volume", "open_interest"])
        )
        old_am: ArrayManager | None = self.ams.get(old_contract)
        old_history = (
            self._build_observed_array_manager_history(old_am)
            if old_am is not None
            else pd.DataFrame(columns=target_history.columns)
        )
        readiness = self._rollover_target_readiness_snapshot(
            target_contract=target_contract,
            new_bar=new_bar,
            target_bar_from_current=target_bar_from_current,
        )
        snapshot: dict[str, Any] = {
            "history_mode": history_mode,
            "history_source": "",
            "target_observed_bar_count": int(len(target_history)),
            "old_contract_observed_bar_count": int(len(old_history)),
            "source_observed_bar_count": 0,
            "roll_adjustment_ratio": float("nan"),
            "target_bar_appended": 0,
            "history_input_ready": 0,
            "history_input_reason": "invalid_rollover_shape_history_mode",
            **readiness,
        }

        if history_mode == "target_contract_only":
            snapshot.update(
                {
                    "history_source": "target_contract_observed",
                    "source_observed_bar_count": int(len(target_history)),
                    "roll_adjustment_ratio": 1.0,
                    "history_input_reason": str(readiness["target_readiness_reason"]),
                }
            )
            if str(readiness["target_readiness_reason"]) != "ready" or new_bar is None:
                return target_history.iloc[0:0].copy(), snapshot
            if target_am is None:
                snapshot["history_input_reason"] = "target_contract_history_unavailable"
                return target_history.iloc[0:0].copy(), snapshot
            snapshot.update(
                {
                    "history_input_ready": 1,
                    "history_input_reason": "ready",
                }
            )
            return target_history, snapshot

        if history_mode != "backwards_ratio_continuous":
            return target_history.iloc[0:0].copy(), snapshot

        snapshot.update(
            {
                "history_source": "old_contract_backwards_ratio_with_target_current_bar",
                "source_observed_bar_count": int(len(old_history)),
                "history_input_reason": str(readiness["target_readiness_reason"]),
            }
        )
        if str(readiness["target_readiness_reason"]) != "ready" or new_bar is None:
            return old_history.iloc[0:0].copy(), snapshot
        if old_history.empty:
            snapshot["history_input_reason"] = "old_contract_history_unavailable"
            return old_history, snapshot

        old_close = float(old_bar.close_price)
        new_close = float(new_bar.close_price)
        if not np.isfinite(old_close) or old_close <= 0 or not np.isfinite(new_close) or new_close <= 0:
            snapshot["history_input_reason"] = "invalid_roll_adjustment_anchor"
            return old_history.iloc[0:0].copy(), snapshot
        roll_adjustment_ratio = new_close / old_close
        if not np.isfinite(roll_adjustment_ratio) or roll_adjustment_ratio <= 0:
            snapshot["history_input_reason"] = "invalid_roll_adjustment_ratio"
            return old_history.iloc[0:0].copy(), snapshot

        history = old_history.copy().reset_index(drop=True)
        price_columns = ["open", "high", "low", "close"]
        for column in price_columns:
            history[column] = pd.to_numeric(history[column], errors="coerce") * roll_adjustment_ratio
        if history[price_columns].isna().any().any() or not np.isfinite(
            history[price_columns].to_numpy(dtype="float64")
        ).all():
            snapshot["history_input_reason"] = "continuous_history_non_finite"
            return history.iloc[0:0].copy(), snapshot

        target_row = {
            "open": float(new_bar.open_price),
            "high": float(new_bar.high_price),
            "low": float(new_bar.low_price),
            "close": float(new_bar.close_price),
            "volume": float(new_bar.volume),
            "open_interest": float(new_bar.open_interest),
        }
        target_bar_appended = int(self._bar_date(old_bar) != self._bar_date(new_bar))
        if target_bar_appended:
            history = pd.concat([history, pd.DataFrame([target_row])], ignore_index=True)
        else:
            last_index = history.index[-1]
            history.loc[last_index, list(target_row)] = list(target_row.values())
        snapshot.update(
            {
                "roll_adjustment_ratio": float(roll_adjustment_ratio),
                "target_bar_appended": target_bar_appended,
                "history_input_ready": 1,
                "history_input_reason": "ready",
            }
        )
        return history, snapshot

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

    def _risk_cluster_for_symbol(self, vt_symbol: str) -> str:
        mapping: dict[str, str] = self._parse_string_mapping(self.risk_cluster_map)
        source_symbol: str = self.source_symbol_by_contract.get(vt_symbol, "")
        product_symbol: str = source_symbol or self._product_vt_symbol(vt_symbol)
        normalized_product: str = product_symbol
        if "." in product_symbol:
            symbol, exchange = product_symbol.split(".", 1)
            normalized_product = f"{symbol.lower()}.{exchange.upper()}"
        keys: list[str] = [str(vt_symbol), source_symbol, product_symbol, normalized_product]
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

    def _risk_cluster_heat_gate_cluster_applies(self, cluster: str) -> bool:
        if not cluster:
            return False
        targets = {
            item.strip()
            for item in str(self.risk_cluster_heat_gate_target_clusters or "").replace(";", ",").split(",")
            if item.strip()
        }
        return not targets or cluster in targets

    def _risk_cluster_heat_gate_context_applies(self, entry_context: str) -> bool:
        contexts = {
            item.strip()
            for item in str(self.risk_cluster_heat_gate_entry_contexts or "").replace(";", ",").split(",")
            if item.strip()
        }
        return not contexts or str(entry_context or "").strip() in contexts

    def _risk_cluster_heat_deleverage_cluster_applies(self, cluster: str) -> bool:
        if not cluster:
            return False
        targets = {
            item.strip()
            for item in str(self.risk_cluster_heat_deleverage_target_clusters or "").replace(";", ",").split(",")
            if item.strip()
        }
        return not targets or cluster in targets

    def _risk_cluster_heat_deleverage_layer_kind_set(self) -> set[str]:
        kinds = {
            item.strip()
            for item in str(self.risk_cluster_heat_deleverage_layer_kinds or "").replace(";", ",").split(",")
            if item.strip()
        }
        return kinds or {"add", "donchian", "post_quality"}

    def _refresh_risk_cluster_heat_pressure_snapshot(self) -> None:
        self.risk_cluster_heat_pressure_snapshot = {}
        self.risk_cluster_same_direction_multi_snapshot = self._risk_cluster_same_direction_multi_flags()
        if not self.enable_risk_cluster_heat_deleverage:
            return
        for cluster in set(self.cluster_margin_usage) | set(self.cluster_unrealized_pnl):
            if not self._risk_cluster_heat_deleverage_cluster_applies(cluster):
                continue
            heat_fields = self._risk_cluster_heat_pressure_fields(cluster, projected_margin=0.0, enabled=True)
            self.risk_cluster_heat_pressure_snapshot[cluster] = float(
                heat_fields["risk_cluster_heat_pressure"] or 0.0
            )

    def _risk_cluster_same_direction_multi_flags(self) -> dict[str, bool]:
        cluster_products: dict[str, set[str]] = {}
        cluster_directions: dict[str, set[str]] = {}
        for state in self.states.values():
            if state.active_volume() <= 0 or not state.contract_vt_symbol:
                continue
            if state.direction not in {"long", "short"}:
                continue
            cluster = self._risk_cluster_for_symbol(state.contract_vt_symbol)
            if not cluster:
                continue
            cluster_products.setdefault(cluster, set()).add(state.product_vt_symbol)
            cluster_directions.setdefault(cluster, set()).add(state.direction)
        return {
            cluster: len(cluster_products.get(cluster, set())) >= 2 and len(cluster_directions.get(cluster, set())) == 1
            for cluster in set(cluster_products) | set(cluster_directions)
        }

    def _risk_cluster_heat_pressure_fields(
        self,
        cluster: str,
        *,
        projected_margin: float = 0.0,
        enabled: bool = True,
    ) -> dict[str, float]:
        if not enabled or not cluster:
            return {
                "risk_cluster_heat_pressure": 0.0,
                "risk_cluster_heat_drawdown_pressure": 0.0,
                "risk_cluster_heat_margin_pressure": 0.0,
                "risk_cluster_heat_unrealized_loss_pressure": 0.0,
                "risk_cluster_heat_margin_ratio": 0.0,
                "risk_cluster_heat_unrealized_loss_ratio": 0.0,
                "risk_cluster_heat_portfolio_drawdown_pct": 0.0,
            }

        sizing_equity = max(1e-9, float(self._sizing_equity() or self.base_capital))
        margin_before = self._reserved_cluster_margin(cluster)
        margin_ratio = (margin_before + max(0.0, float(projected_margin or 0.0))) / sizing_equity
        unrealized_pnl = float(self.cluster_unrealized_pnl.get(cluster, 0.0) or 0.0)
        unrealized_loss_ratio = max(0.0, -unrealized_pnl) / sizing_equity
        drawdown_ratio = max(0.0, float(self.portfolio_drawdown_pct or 0.0))

        drawdown_pressure = self._linear_pressure(
            drawdown_ratio,
            float(self.risk_cluster_heat_gate_drawdown_start_pct),
            float(self.risk_cluster_heat_gate_drawdown_full_pct),
        )
        margin_pressure = self._linear_pressure(
            margin_ratio,
            float(self.risk_cluster_heat_gate_margin_start_ratio),
            float(self.risk_cluster_heat_gate_margin_full_ratio),
        )
        unrealized_loss_pressure = self._linear_pressure(
            unrealized_loss_ratio,
            float(self.risk_cluster_heat_gate_unrealized_loss_start_ratio),
            float(self.risk_cluster_heat_gate_unrealized_loss_full_ratio),
        )
        heat_pressure = drawdown_pressure * max(margin_pressure, unrealized_loss_pressure)
        return {
            "risk_cluster_heat_pressure": heat_pressure,
            "risk_cluster_heat_drawdown_pressure": drawdown_pressure,
            "risk_cluster_heat_margin_pressure": margin_pressure,
            "risk_cluster_heat_unrealized_loss_pressure": unrealized_loss_pressure,
            "risk_cluster_heat_margin_ratio": margin_ratio,
            "risk_cluster_heat_unrealized_loss_ratio": unrealized_loss_ratio,
            "risk_cluster_heat_portfolio_drawdown_pct": drawdown_ratio,
        }

    def _current_min_risk_cluster_heat_gate_weight(self) -> float:
        if not self.enable_risk_cluster_heat_gate:
            return 1.0
        weights: list[float] = []
        for cluster in set(self.cluster_margin_usage) | set(self.cluster_unrealized_pnl):
            if not self._risk_cluster_heat_gate_cluster_applies(cluster):
                continue
            heat_fields = self._risk_cluster_heat_pressure_fields(cluster, enabled=True)
            pressure = float(heat_fields["risk_cluster_heat_pressure"])
            floor = self._clip01(float(self.risk_cluster_heat_gate_weight_floor or 0.0))
            weights.append(self._clip01(1.0 - (1.0 - floor) * pressure))
        return min(weights) if weights else 1.0

    def _reserved_cluster_margin(self, cluster: str) -> float:
        return max(
            0.0,
            float(self.cluster_margin_usage.get(cluster, 0.0) or 0.0)
            + float(self.pending_cluster_margin_reservation.get(cluster, 0.0) or 0.0),
        )

    def _risk_cluster_cap_fields(
        self,
        vt_symbol: str,
        selected_volume: int,
        margin_per_contract: float,
    ) -> dict[str, Any]:
        cluster: str = self._risk_cluster_for_symbol(vt_symbol)
        enabled: int = int(bool(self.enable_risk_cluster_margin_cap) and self._cluster_cap_applies(cluster))
        cap: float = max(0.0, self._sizing_equity() * float(self.risk_cluster_margin_cap_ratio or 0.0))
        current: float = self._reserved_cluster_margin(cluster) if cluster else 0.0
        margin_per_contract = max(0.0, float(margin_per_contract or 0.0))
        max_volume: int = int(max(0.0, cap - current) // margin_per_contract) if enabled and margin_per_contract > 0 else int(selected_volume)
        capped_volume: int = min(max(0, int(selected_volume)), max(0, max_volume)) if enabled else max(0, int(selected_volume))
        return {
            "risk_cluster_cap_enabled": enabled,
            "risk_cluster_name": cluster,
            "risk_cluster_cap_ratio": float(self.risk_cluster_margin_cap_ratio or 0.0),
            "risk_cluster_cap_amount": cap if enabled else 0.0,
            "risk_cluster_reserved_margin_before": current if enabled else 0.0,
            "risk_cluster_max_volume": max_volume if enabled else int(selected_volume),
            "risk_cluster_selected_volume_before": max(0, int(selected_volume)),
            "risk_cluster_selected_volume": capped_volume,
        }

    @staticmethod
    def _linear_pressure(value: float, start: float, full: float) -> float:
        start = max(0.0, float(start))
        full = max(start + 1e-9, float(full))
        value = max(0.0, float(value))
        if value <= start:
            return 0.0
        if value >= full:
            return 1.0
        return (value - start) / max(1e-9, full - start)

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

    def _rollover_shape_continuation_snapshot(
        self,
        old_direction: str,
        history: pd.DataFrame,
    ) -> dict[str, Any]:
        close = pd.to_numeric(history.get("close", pd.Series(dtype="float64")), errors="coerce")
        close = close.replace([np.inf, -np.inf], np.nan).dropna().astype("float64")
        required_bar_count = max(self.ma_short, self.ma_mid, self.ma_long, self.ma_extra_long)
        snapshot: dict[str, Any] = {
            "observed_bar_count": int(len(close)),
            "required_bar_count": int(required_bar_count),
            "bullish_alignment": 0,
            "bearish_alignment": 0,
            "ma_short_value": float("nan"),
            "ma_mid_value": float("nan"),
            "ma_long_value": float("nan"),
            "ma_extra_long_value": float("nan"),
            "macd_hist": float("nan"),
            "allowed": 0,
            "reason": "insufficient_indicator_history",
        }
        if len(close) < required_bar_count:
            return snapshot

        ma_short = float(close.tail(self.ma_short).mean())
        ma_mid = float(close.tail(self.ma_mid).mean())
        ma_long = float(close.tail(self.ma_long).mean())
        ma_extra_long = float(close.tail(self.ma_extra_long).mean())
        _dif, _dea, hist = self._calculate_macd(close)
        macd_hist = float(hist.iloc[-1]) if not hist.empty else float("nan")
        if not all(np.isfinite(value) for value in [ma_short, ma_mid, ma_long, ma_extra_long, macd_hist]):
            snapshot["reason"] = "non_finite_indicator"
            return snapshot

        bullish_alignment = ma_short > ma_mid > ma_long > ma_extra_long
        bearish_alignment = ma_short < ma_mid < ma_long < ma_extra_long
        snapshot.update(
            {
                "bullish_alignment": int(bullish_alignment),
                "bearish_alignment": int(bearish_alignment),
                "ma_short_value": ma_short,
                "ma_mid_value": ma_mid,
                "ma_long_value": ma_long,
                "ma_extra_long_value": ma_extra_long,
                "macd_hist": macd_hist,
            }
        )
        if old_direction == "long":
            allowed = bool(self.long_entry_enabled and bullish_alignment and macd_hist > 0)
        elif old_direction == "short":
            allowed = bool(self.short_entry_enabled and bearish_alignment and macd_hist < 0)
        else:
            snapshot["reason"] = "unsupported_direction"
            return snapshot

        snapshot["allowed"] = int(allowed)
        snapshot["reason"] = "shape_and_macd_aligned" if allowed else "shape_or_macd_not_aligned"
        return snapshot

    @staticmethod
    def _rollover_shape_signal_data(
        old_direction: str,
        old_risk_mode: str,
        shape_snapshot: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "signal": f"{old_direction}_rollover",
            "bullish_alignment": bool(shape_snapshot.get("bullish_alignment")),
            "bearish_alignment": bool(shape_snapshot.get("bearish_alignment")),
            "ma_mid_value": float(shape_snapshot.get("ma_mid_value", float("nan"))),
            "ma_long_value": float(shape_snapshot.get("ma_long_value", float("nan"))),
            "ma_mid_prev_value": float("nan"),
            "ma_long_prev_value": float("nan"),
            "risk_mode": old_risk_mode,
            "breakout": False,
            "rsi_value": float("nan"),
        }

    @staticmethod
    def _rollover_shape_reopen_volume(
        *,
        previous_volume: int,
        sizing_snapshot: dict[str, Any],
        volume_policy: str,
    ) -> tuple[int, str]:
        previous_volume = max(0, int(previous_volume))
        allowed_volume = max(0, int(sizing_snapshot.get("selected_volume") or 0))
        if previous_volume <= 0:
            return 0, "previous_volume_not_positive"
        if allowed_volume <= 0:
            return 0, "no_positive_volume_allowed"
        if volume_policy == "exact_or_skip" and allowed_volume < previous_volume:
            return 0, "previous_volume_not_fully_allowed"
        if volume_policy == "shrink_to_allowed":
            final_volume = min(previous_volume, allowed_volume)
            if final_volume < previous_volume:
                return final_volume, "reduced_to_allowed_volume"
            return final_volume, "previous_volume_fully_allowed"
        if volume_policy == "exact_or_skip":
            return previous_volume, "previous_volume_fully_allowed"
        return 0, "invalid_rollover_volume_policy"

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
