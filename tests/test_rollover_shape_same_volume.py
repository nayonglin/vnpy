from __future__ import annotations

import unittest
from datetime import datetime
from types import SimpleNamespace

import pandas as pd

from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.object import BarData

from qmt_roll_portfolio_strategy import PositionLayer, ProductState, QmtRollPortfolioStrategy


def _history_from_closes(
    closes: list[float],
    *,
    volumes: list[float] | None = None,
) -> pd.DataFrame:
    history_volumes = volumes if volumes is not None else [100.0] * len(closes)
    if len(history_volumes) != len(closes):
        raise ValueError("volumes must match closes")
    return pd.DataFrame(
        {
            "open": closes,
            "high": [value + 0.5 for value in closes],
            "low": [value - 0.5 for value in closes],
            "close": closes,
            "volume": history_volumes,
            "open_interest": [1000.0] * len(closes),
        }
    )


def _bar(
    symbol: str,
    close_price: float,
    *,
    volume: float = 100,
    bar_datetime: datetime | None = None,
) -> BarData:
    return BarData(
        gateway_name="test",
        symbol=symbol,
        exchange=Exchange.DCE,
        datetime=bar_datetime or datetime(2026, 8, 20, 15, 0),
        interval=Interval.DAILY,
        open_price=close_price,
        high_price=close_price + 0.5,
        low_price=close_price - 0.5,
        close_price=close_price,
        volume=volume,
        open_interest=1000,
    )


def _short_history_array_manager(closes: list[float]) -> SimpleNamespace:
    return SimpleNamespace(
        inited=False,
        count=len(closes),
        open_array=list(closes),
        high_array=[value + 0.5 for value in closes],
        low_array=[value - 0.5 for value in closes],
        close_array=list(closes),
        volume_array=[100.0] * len(closes),
        open_interest_array=[1000.0] * len(closes),
    )


def _state(volume: int = 2) -> ProductState:
    return ProductState(
        product_vt_symbol="jm.DCE",
        contract_vt_symbol="jm2609.DCE",
        direction="long",
        risk_mode="regular",
        layers=[
            PositionLayer(
                kind="base",
                direction="long",
                volume=volume,
                entry_price=100.0,
                stop_price=98.0,
                highest_price=105.0,
                lowest_price=97.0,
                signal="long_case1a",
                entry_date="2026-08-01",
            )
        ],
    )


class _RolloverHarness(QmtRollPortfolioStrategy):
    def __init__(
        self,
        allowed_volume: int,
        *,
        candidate_enabled: bool = True,
        guard_passed: bool = True,
        engine_bars: dict[str, BarData] | None = None,
        volume_policy: str = "shrink_to_allowed",
        history_mode: str = "target_contract_only",
        target_closes: list[float] | None = None,
        target_price_tick: float = 1.0,
    ) -> None:
        self.enable_rollover_shape_same_volume_reopen = candidate_enabled
        self.rollover_shape_volume_policy = volume_policy
        self.rollover_shape_history_mode = history_mode
        self.rollover_reopen_enabled = True
        self.enable_rollover_reopen_drawdown_guard = not guard_passed
        self.rollover_reopen_max_portfolio_drawdown_pct = 0.10
        self.long_entry_enabled = True
        self.short_entry_enabled = True
        self.ma_short = 5
        self.ma_mid = 10
        self.ma_long = 20
        self.ma_extra_long = 40
        self.estimated_equity = 150000.0
        self.base_capital = 150000.0
        self.portfolio_equity_high_water = 150000.0
        self.portfolio_drawdown_pct = 0.0
        self.ams = {
            "jm2609.DCE": _short_history_array_manager([float(value) for value in range(60, 101)]),
            "jm2701.DCE": _short_history_array_manager(
                target_closes
                if target_closes is not None
                else [float(value) for value in range(1, 41)]
            ),
        }
        self.allowed_volume = allowed_volume
        self.guard_passed = guard_passed
        self.opened: list[dict[str, object]] = []
        self.targets: list[tuple[str, int]] = []
        self.reservations: list[tuple[str, int, bool]] = []
        self.rollover_shape_same_volume_diagnostics: list[dict[str, object]] = []
        self.rollover_reopen_guard_diagnostics: list[dict[str, object]] = []
        self.total_margin_in_use = 250.0
        self.cluster_margin_usage = {"ferrous": 250.0}
        self.cluster_unrealized_pnl = {"ferrous": 0.0}
        self.risk_cluster_margin_in_use = 250.0
        self.risk_cluster_unrealized_loss_in_use = 0.0
        self.pending_margin_reservation = 0.0
        self.pending_cluster_margin_reservation: dict[str, float] = {}
        self.pending_active_products: set[str] = set()
        self.sizing_margin_seen: float | None = None
        self.sizing_cluster_margin_seen: float | None = None
        self.target_price_tick = target_price_tick
        self.strategy_engine = SimpleNamespace(bars=dict(engine_bars or {}))

    def _bar_from_current_or_engine(
        self,
        vt_symbol: str,
        bars: dict[str, BarData],
    ) -> BarData | None:
        return bars.get(vt_symbol) or self.strategy_engine.bars.get(vt_symbol)

    def _record_trade_event(self, **kwargs: object) -> None:
        return None

    def _close_all_layers(self, state: ProductState, exit_price: float, **kwargs: object) -> None:
        state.reset()

    def set_target(self, vt_symbol: str, target: int) -> None:
        self.targets.append((vt_symbol, target))

    def _rollover_reopen_drawdown_guard_fields(self) -> dict[str, object]:
        return {
            "rollover_reopen_drawdown_guard_enabled": int(not self.guard_passed),
            "rollover_reopen_drawdown_guard_passed": int(self.guard_passed),
            "rollover_reopen_drawdown_guard_max_pct": 0.10,
            "rollover_reopen_drawdown_guard_portfolio_drawdown_pct": 0.0,
        }

    def _calculate_entry_sizing(self, *args: object, **kwargs: object) -> dict[str, object]:
        self.sizing_margin_seen = float(self.total_margin_in_use)
        self.sizing_cluster_margin_seen = float(self.cluster_margin_usage.get("ferrous", 0.0))
        return {
            "selected_volume": self.allowed_volume,
            "stop_price": 39.0,
            "risk_mode": "regular",
        }

    def _open_position(
        self,
        state: ProductState,
        contract_vt_symbol: str,
        direction: str,
        volume: int,
        bar: BarData,
        signal: str,
        history: pd.DataFrame,
        signal_data: dict[str, object],
        sizing_snapshot: dict[str, object] | None = None,
    ) -> None:
        self.opened.append(
            {
                "contract": contract_vt_symbol,
                "direction": direction,
                "volume": volume,
                "history_count": len(history),
                "sizing": dict(sizing_snapshot or {}),
            }
        )

    def _apply_state_target(self, state: ProductState, execution_price_override: float | None = None) -> None:
        return None

    def _risk_cluster_for_symbol(self, vt_symbol: str) -> str:
        return "ferrous"

    def get_size(self, vt_symbol: str) -> int:
        return 10

    def get_pricetick(self, vt_symbol: str) -> float:
        return self.target_price_tick

    def _margin_ratio_for_symbol(self, vt_symbol: str) -> float:
        return 0.10

    def _reserve_intrabar_entry(
        self,
        product_vt_symbol: str,
        sizing_snapshot: dict[str, object],
        volume: int,
        *,
        count_active_position: bool,
    ) -> None:
        self.reservations.append((product_vt_symbol, volume, count_active_position))


class _DirectionalBoostSizingHarness(QmtRollPortfolioStrategy):
    def __init__(self) -> None:
        self.enable_directional_30d_risk_boost = True
        self.directional_30d_risk_boost_lookback = 30
        self.directional_30d_risk_boost_multiplier = 1.2
        self.directional_30d_risk_boost_require_volume_expansion = False
        self.directional_30d_volume_recent_days = 10
        self.directional_30d_volume_prior_days = 10
        self.fixed_size = 0
        self.source_symbol_by_contract: dict[str, str] = {}
        self.risk_ratio_of_total_assets = 0.01
        self.max_position_size = 100
        self.min_position_size = 1
        self.estimated_equity = 100_000.0
        self.base_capital = 100_000.0
        self.portfolio_drawdown_pct = 0.0
        self.portfolio_equity_high_water = 100_000.0
        self.loss_streak = 0
        self.profit_recovery_streak = 0
        self.pending_entry_diagnostics: dict[tuple[str, str, str], list[dict[str, object]]] = {}
        self.entry_risk_diagnostics: list[dict[str, object]] = []

    def _entry_structure_recovery_fields(self, **kwargs: object) -> dict[str, object]:
        return {"streak_entry_structure_risk_recovery_effective_multiplier": 1.0}

    def _current_streak_multiplier(self) -> float:
        return 1.0

    def _product_vt_symbol(self, vt_symbol: str) -> str:
        return "rb.SHFE"

    def _failure_memory_micro_sizing_fields(self, **kwargs: object) -> dict[str, object]:
        return {}

    def _oi_price_confirm_risk_restore_fields(self, **kwargs: object) -> dict[str, object]:
        return {}

    def _portfolio_overheat_cooldown_fields(self, entry_context: str) -> dict[str, object]:
        return {"portfolio_overheat_cooldown_scale": 1.0}

    def _sizing_equity_snapshot(self) -> dict[str, object]:
        return {}

    def _limited_available_balance(self, entry_context: str) -> float:
        return 100_000.0

    def _allowed_capital(self, entry_context: str) -> float:
        return 100_000.0

    def _single_trade_capital_limit(self) -> float:
        return 100_000.0

    def _free_capital_after_reservations(self) -> float:
        return 100_000.0

    def _risk_amount_from_ratio(self, *args: object, **kwargs: object) -> float:
        return 1_000.0

    def _entry_stop_price(
        self,
        direction: str,
        bar: BarData,
        history: pd.DataFrame,
        use_day_extreme: bool,
    ) -> float:
        return 90.0

    def get_size(self, vt_symbol: str) -> int:
        return 10

    def get_pricetick(self, vt_symbol: str) -> float:
        return 1.0

    def _margin_ratio_for_symbol(self, vt_symbol: str) -> float:
        return 0.1

    def _risk_cluster_cap_fields(
        self,
        vt_symbol: str,
        volume: int,
        margin_per_contract: float,
    ) -> dict[str, object]:
        return {"risk_cluster_selected_volume": volume}

    def _apply_risk_cluster_heat_gate_to_volume(
        self,
        vt_symbol: str,
        volume: int,
        margin_per_contract: float,
        entry_context: str,
    ) -> dict[str, object]:
        return {"risk_cluster_heat_gate_selected_volume": volume}

    def _apply_env_gate_to_volume(
        self,
        base_volume: int,
        *,
        entry_context: str,
        apply_env_gate: bool,
    ) -> dict[str, object]:
        return {"selected_volume": base_volume}

    def _incremental_margin_budget_gate_adjust_volume(
        self,
        *,
        selected_volume: int,
        margin_per_contract: float,
        entry_context: str,
    ) -> tuple[int, dict[str, object]]:
        return selected_volume, {}

    def _reserved_margin_in_use(self) -> float:
        return 0.0

    def _effective_capital_usage_ratio(self, entry_context: str) -> float:
        return 1.0

    def _effective_max_concurrent_positions(self, entry_context: str) -> int:
        return 10

    def _recovery_sleeve_fields(self, *args: object, **kwargs: object) -> dict[str, object]:
        return {}


class _DirectionalBoostAddHarness(QmtRollPortfolioStrategy):
    def __init__(self) -> None:
        self.enable_directional_30d_risk_boost = True
        self.directional_30d_risk_boost_lookback = 30
        self.directional_30d_risk_boost_multiplier = 1.2
        self.directional_30d_risk_boost_require_volume_expansion = False
        self.directional_30d_volume_recent_days = 10
        self.directional_30d_volume_prior_days = 10
        self.post_entry_quality_add_volume_multiplier = 0.5
        self.post_entry_quality_add_use_day_extreme_stop = True
        self.regular_add_volume_multiplier = 0.5
        self.regular_add_use_day_extreme_stop = True
        self.donchian_add_volume_multipliers = "2.0,1.0"
        self.max_position_size = 100

    def _entry_stop_price(
        self,
        direction: str,
        bar: BarData,
        history: pd.DataFrame,
        use_day_extreme: bool,
    ) -> float:
        return 90.0 if direction == "long" else 110.0

    def get_size(self, vt_symbol: str) -> int:
        return 10

    def get_pricetick(self, vt_symbol: str) -> float:
        return 1.0

    def _margin_ratio_for_symbol(self, vt_symbol: str) -> float:
        return 0.1


class RolloverShapeSameVolumeTest(unittest.TestCase):
    @staticmethod
    def _volume_confirmed_strategy() -> QmtRollPortfolioStrategy:
        strategy = object.__new__(QmtRollPortfolioStrategy)
        strategy.enable_directional_30d_risk_boost = True
        strategy.directional_30d_risk_boost_lookback = 30
        strategy.directional_30d_risk_boost_multiplier = 1.2
        strategy.directional_30d_risk_nonconfirmation_multiplier = 1.0
        strategy.directional_30d_risk_boost_require_volume_expansion = True
        strategy.directional_30d_volume_recent_days = 10
        strategy.directional_30d_volume_prior_days = 10
        strategy.directional_30d_volume_ratio_threshold = 1.0
        return strategy

    @staticmethod
    def _asymmetric_double_volume_strategy() -> QmtRollPortfolioStrategy:
        strategy = RolloverShapeSameVolumeTest._volume_confirmed_strategy()
        strategy.directional_30d_risk_boost_multiplier = 1.5
        strategy.directional_30d_risk_nonconfirmation_multiplier = 0.5
        strategy.directional_30d_volume_ratio_threshold = 2.0
        return strategy

    @staticmethod
    def _long_triple_volume_with_low_volume_discount_strategy() -> QmtRollPortfolioStrategy:
        strategy = RolloverShapeSameVolumeTest._volume_confirmed_strategy()
        strategy.directional_30d_risk_boost_multiplier = 1.5
        strategy.directional_30d_risk_nonconfirmation_multiplier = 1.0
        strategy.directional_30d_risk_adjust_long_only = True
        strategy.directional_30d_volume_ratio_threshold = 3.0
        strategy.enable_directional_30d_low_volume_risk_discount = True
        strategy.directional_30d_low_volume_ratio_threshold = 0.5
        strategy.directional_30d_low_volume_risk_multiplier = 0.5
        return strategy

    @staticmethod
    def _symmetric_triple_volume_with_low_volume_discount_strategy() -> QmtRollPortfolioStrategy:
        strategy = (
            RolloverShapeSameVolumeTest
            ._long_triple_volume_with_low_volume_discount_strategy()
        )
        strategy.directional_30d_risk_adjust_long_only = False
        return strategy

    @staticmethod
    def _long_signal_atr_shock_strategy() -> QmtRollPortfolioStrategy:
        strategy = object.__new__(QmtRollPortfolioStrategy)
        strategy.enable_long_signal_atr_shock_filter = True
        strategy.long_signal_atr_shock_period = 5
        strategy.long_signal_atr_shock_multiplier = 2.0
        strategy.long_signal_atr_shock_entry_contexts = (
            "flat_entry,reverse_entry,rollover_reopen"
        )
        return strategy

    def test_long_signal_atr_shock_excludes_signal_day_and_uses_strict_boundary(self) -> None:
        strategy = self._long_signal_atr_shock_strategy()
        above = strategy._long_signal_atr_shock_snapshot(
            "long",
            _history_from_closes([100.0] * 6 + [97.9]),
            "flat_entry",
        )
        exact = strategy._long_signal_atr_shock_snapshot(
            "long",
            _history_from_closes([100.0] * 6 + [98.0]),
            "flat_entry",
        )

        self.assertEqual(1.0, above["long_signal_atr_shock_atr"])
        self.assertAlmostEqual(2.1, above["long_signal_atr_shock_drop"])
        self.assertEqual(1, above["long_signal_atr_shock_blocked"])
        self.assertEqual("drop_strictly_above_threshold", above["long_signal_atr_shock_reason"])
        self.assertEqual(0, exact["long_signal_atr_shock_blocked"])
        self.assertEqual("drop_not_above_threshold", exact["long_signal_atr_shock_reason"])

    def test_short_signal_atr_shock_blocks_strict_rise_and_allows_exact_boundary(self) -> None:
        strategy = self._long_signal_atr_shock_strategy()
        strategy.enable_short_signal_atr_shock_filter = True
        strategy.long_signal_atr_shock_multiplier = 1.0
        above = strategy._long_signal_atr_shock_snapshot(
            "short",
            _history_from_closes([100.0] * 6 + [101.1]),
            "flat_entry",
        )
        exact = strategy._long_signal_atr_shock_snapshot(
            "short",
            _history_from_closes([100.0] * 6 + [101.0]),
            "rollover_reopen",
        )

        self.assertEqual(1.0, above["long_signal_atr_shock_atr"])
        self.assertAlmostEqual(1.1, above["signal_atr_shock_adverse_move"])
        self.assertEqual("signal_day_rise", above["signal_atr_shock_move_kind"])
        self.assertEqual(1, above["long_signal_atr_shock_blocked"])
        self.assertEqual("rise_strictly_above_threshold", above["long_signal_atr_shock_reason"])
        self.assertEqual(0, exact["long_signal_atr_shock_blocked"])
        self.assertEqual("rise_not_above_threshold", exact["long_signal_atr_shock_reason"])

    def test_long_signal_atr_shock_blocks_only_approved_long_entry_contexts(self) -> None:
        strategy = _DirectionalBoostSizingHarness()
        strategy.enable_long_signal_atr_shock_filter = True
        strategy.long_signal_atr_shock_period = 5
        strategy.long_signal_atr_shock_multiplier = 2.0
        strategy.long_signal_atr_shock_entry_contexts = (
            "flat_entry,reverse_entry,rollover_reopen"
        )
        history = _history_from_closes([100.0] * 31 + [97.9])
        bar = _bar("rb2605", 97.9)

        for entry_context in ["flat_entry", "reverse_entry", "rollover_reopen"]:
            with self.subTest(entry_context=entry_context):
                sizing = strategy._calculate_entry_sizing(
                    "rb2605.SHFE",
                    "long",
                    bar,
                    history,
                    {"signal": "long_case1a", "risk_mode": "regular"},
                    entry_context=entry_context,
                )
                self.assertGreater(sizing["long_signal_atr_shock_selected_volume_before"], 0)
                self.assertEqual(0, sizing["selected_volume"])
                self.assertEqual(1, sizing["long_signal_atr_shock_blocked"])

        add_sizing = strategy._calculate_entry_sizing(
            "rb2605.SHFE",
            "long",
            bar,
            history,
            {"signal": "long_case1a", "risk_mode": "regular"},
            entry_context="regular_add",
        )
        short_sizing = strategy._calculate_entry_sizing(
            "rb2605.SHFE",
            "short",
            bar,
            history,
            {"signal": "short_case1a", "risk_mode": "regular"},
            entry_context="flat_entry",
        )
        self.assertGreater(add_sizing["selected_volume"], 0)
        self.assertEqual("entry_context_excluded", add_sizing["long_signal_atr_shock_reason"])
        self.assertGreater(short_sizing["selected_volume"], 0)
        self.assertEqual("direction_excluded", short_sizing["long_signal_atr_shock_reason"])

    def test_long_signal_atr_shock_keeps_m_behavior_when_history_is_insufficient(self) -> None:
        strategy = self._long_signal_atr_shock_strategy()

        snapshot = strategy._long_signal_atr_shock_snapshot(
            "long",
            _history_from_closes([100.0] * 5 + [90.0]),
            "flat_entry",
        )

        self.assertEqual(0, snapshot["long_signal_atr_shock_blocked"])
        self.assertEqual("insufficient_prior_history", snapshot["long_signal_atr_shock_reason"])

    def test_symmetric_low_volume_discount_applies_to_short_without_30d_alignment(self) -> None:
        strategy = self._symmetric_triple_volume_with_low_volume_discount_strategy()
        history = _history_from_closes(
            [90.0] + [95.0] * 29 + [110.0],
            volumes=[100.0] * 11 + [100.0] * 10 + [49.0] * 9 + [58.0],
        )

        snapshot = strategy._directional_30d_risk_boost_snapshot("short", history)

        self.assertEqual(0, snapshot["directional_30d_risk_boost_aligned"])
        self.assertEqual(1, snapshot["directional_30d_low_volume_discount_applied"])
        self.assertEqual(0.5, snapshot["directional_30d_risk_boost_multiplier"])
        self.assertEqual("low_volume_discount", snapshot["directional_30d_risk_boost_reason"])

    def test_symmetric_short_high_volume_requires_alignment_and_strict_threshold(self) -> None:
        strategy = self._symmetric_triple_volume_with_low_volume_discount_strategy()
        closes = [110.0] + [105.0] * 29 + [90.0]
        high = strategy._directional_30d_risk_boost_snapshot(
            "short",
            _history_from_closes(
                closes,
                volumes=[100.0] * 11 + [100.0] * 10 + [299.0] * 9 + [310.0],
            ),
        )
        exact_half = strategy._directional_30d_risk_boost_snapshot(
            "short",
            _history_from_closes(
                closes,
                volumes=[100.0] * 11 + [100.0] * 10 + [50.0] * 10,
            ),
        )

        self.assertEqual(1, high["directional_30d_risk_boost_aligned"])
        self.assertEqual(1, high["directional_30d_risk_boost_applied"])
        self.assertEqual(1.5, high["directional_30d_risk_boost_multiplier"])
        self.assertEqual(0, exact_half["directional_30d_low_volume_discount_applied"])
        self.assertEqual(1.0, exact_half["directional_30d_risk_boost_multiplier"])

    def test_long_low_volume_discount_applies_without_30d_direction_alignment(self) -> None:
        strategy = self._long_triple_volume_with_low_volume_discount_strategy()
        history = _history_from_closes(
            [110.0] + [105.0] * 29 + [100.0],
            volumes=[100.0] * 11 + [100.0] * 10 + [49.0] * 9 + [58.0],
        )

        snapshot = strategy._directional_30d_risk_boost_snapshot("long", history)

        self.assertEqual(1_000.0, snapshot["directional_30d_prior_volume_sum"])
        self.assertEqual(499.0, snapshot["directional_30d_recent_volume_sum"])
        self.assertEqual(1, snapshot["directional_30d_low_volume_discount_applied"])
        self.assertEqual(0.5, snapshot["directional_30d_risk_boost_multiplier"])
        self.assertEqual("low_volume_discount", snapshot["directional_30d_risk_boost_reason"])

    def test_long_low_volume_discount_requires_strictly_less_than_half(self) -> None:
        strategy = self._long_triple_volume_with_low_volume_discount_strategy()
        history = _history_from_closes(
            [100.0] + [95.0] * 29 + [110.0],
            volumes=[100.0] * 11 + [100.0] * 10 + [50.0] * 10,
        )

        snapshot = strategy._directional_30d_risk_boost_snapshot("long", history)

        self.assertEqual(500.0, snapshot["directional_30d_recent_volume_sum"])
        self.assertEqual(0, snapshot["directional_30d_low_volume_discount_applied"])
        self.assertEqual(1.0, snapshot["directional_30d_risk_boost_multiplier"])
        self.assertEqual("volume_not_expanding", snapshot["directional_30d_risk_boost_reason"])

    def test_long_low_volume_discount_bypasses_short_direction(self) -> None:
        strategy = self._long_triple_volume_with_low_volume_discount_strategy()
        history = _history_from_closes(
            [110.0] + [105.0] * 29 + [90.0],
            volumes=[100.0] * 11 + [100.0] * 10 + [49.0] * 9 + [58.0],
        )

        snapshot = strategy._directional_30d_risk_boost_snapshot("short", history)

        self.assertEqual(1.0, snapshot["directional_30d_risk_boost_multiplier"])
        self.assertEqual(0, snapshot["directional_30d_low_volume_discount_applied"])
        self.assertEqual("direction_excluded", snapshot["directional_30d_risk_boost_reason"])

    def test_asymmetric_double_volume_risk_uses_1_5_on_hit_and_0_5_otherwise(self) -> None:
        strategy = self._asymmetric_double_volume_strategy()
        long_closes = [100.0] + [95.0] * 29 + [110.0]
        hit_history = _history_from_closes(
            long_closes,
            volumes=[100.0] * 11 + [100.0] * 10 + [199.0] * 9 + [210.0],
        )
        exact_two_history = _history_from_closes(
            long_closes,
            volumes=[100.0] * 11 + [100.0] * 10 + [200.0] * 10,
        )

        hit = strategy._directional_30d_risk_boost_snapshot("long", hit_history)
        exact_two = strategy._directional_30d_risk_boost_snapshot("long", exact_two_history)
        direction_miss = strategy._directional_30d_risk_boost_snapshot("short", hit_history)

        self.assertEqual(1.5, hit["directional_30d_risk_boost_multiplier"])
        self.assertEqual(1, hit["directional_30d_risk_boost_applied"])
        self.assertEqual(0.5, exact_two["directional_30d_risk_boost_multiplier"])
        self.assertEqual(0, exact_two["directional_30d_risk_boost_applied"])
        self.assertEqual(0.5, direction_miss["directional_30d_risk_boost_multiplier"])
        self.assertEqual("direction_not_aligned", direction_miss["directional_30d_risk_boost_reason"])

    def test_asymmetric_double_volume_risk_treats_missing_history_as_nonconfirmation(self) -> None:
        strategy = self._asymmetric_double_volume_strategy()

        snapshot = strategy._directional_30d_risk_boost_snapshot(
            "long",
            _history_from_closes([100.0] * 20, volumes=[100.0] * 20),
        )

        self.assertEqual(0.5, snapshot["directional_30d_risk_boost_multiplier"])
        self.assertEqual(0, snapshot["directional_30d_risk_boost_applied"])
        self.assertEqual("insufficient_history", snapshot["directional_30d_risk_boost_reason"])

    def test_asymmetric_double_volume_risk_reaches_real_entry_and_add_sizing(self) -> None:
        entry_strategy = _DirectionalBoostSizingHarness()
        entry_strategy.directional_30d_risk_boost_multiplier = 1.5
        entry_strategy.directional_30d_risk_nonconfirmation_multiplier = 0.5
        entry_strategy.directional_30d_risk_boost_require_volume_expansion = True
        entry_strategy.directional_30d_volume_ratio_threshold = 2.0
        add_strategy = _DirectionalBoostAddHarness()
        add_strategy.directional_30d_risk_boost_multiplier = 1.5
        add_strategy.directional_30d_risk_nonconfirmation_multiplier = 0.5
        add_strategy.directional_30d_risk_boost_require_volume_expansion = True
        add_strategy.directional_30d_volume_ratio_threshold = 2.0
        closes = [100.0] + [95.0] * 29 + [110.0]
        miss_history = _history_from_closes(closes, volumes=[100.0] * 31)
        hit_history = _history_from_closes(
            closes,
            volumes=[100.0] * 11 + [100.0] * 10 + [199.0] * 9 + [210.0],
        )
        bar = _bar("rb2605", 100.0)

        miss_entry = entry_strategy._calculate_entry_sizing(
            "rb2605.SHFE",
            "long",
            bar,
            miss_history,
            {"signal": "long_case1a", "risk_mode": "regular"},
        )
        hit_entry = entry_strategy._calculate_entry_sizing(
            "rb2605.SHFE",
            "long",
            bar,
            hit_history,
            {"signal": "long_case1a", "risk_mode": "regular"},
        )
        miss_add, _ = add_strategy._calculate_directional_boosted_add_sizing(
            _state(volume=10), bar, miss_history, "regular_add"
        )
        hit_add, _ = add_strategy._calculate_directional_boosted_add_sizing(
            _state(volume=10), bar, hit_history, "regular_add"
        )

        self.assertEqual(500.0, miss_entry["risk_amount"])
        self.assertEqual(5, miss_entry["selected_volume"])
        self.assertEqual(1_500.0, hit_entry["risk_amount"])
        self.assertEqual(15, hit_entry["selected_volume"])
        self.assertEqual(2, miss_add)
        self.assertEqual(7, hit_add)

    def test_asymmetric_double_volume_long_only_bypasses_short_entry_and_add(self) -> None:
        snapshot_strategy = self._asymmetric_double_volume_strategy()
        snapshot_strategy.directional_30d_risk_adjust_long_only = True
        short_history = _history_from_closes(
            [110.0] + [105.0] * 29 + [90.0],
            volumes=[100.0] * 11 + [100.0] * 10 + [199.0] * 9 + [210.0],
        )

        short_snapshot = snapshot_strategy._directional_30d_risk_boost_snapshot(
            "short", short_history
        )

        self.assertEqual(1, short_snapshot.get("directional_30d_risk_adjust_long_only", 0))
        self.assertEqual(1.0, short_snapshot["directional_30d_risk_boost_multiplier"])
        self.assertEqual(0, short_snapshot["directional_30d_risk_boost_applied"])
        self.assertEqual(
            "direction_excluded",
            short_snapshot["directional_30d_risk_boost_reason"],
        )

        entry_strategy = _DirectionalBoostSizingHarness()
        entry_strategy.directional_30d_risk_boost_multiplier = 1.5
        entry_strategy.directional_30d_risk_nonconfirmation_multiplier = 0.5
        entry_strategy.directional_30d_risk_boost_require_volume_expansion = True
        entry_strategy.directional_30d_volume_ratio_threshold = 2.0
        entry_strategy.directional_30d_risk_adjust_long_only = True
        entry = entry_strategy._calculate_entry_sizing(
            "rb2605.SHFE",
            "short",
            _bar("rb2605", 100.0),
            short_history,
            {"signal": "short_case1a", "risk_mode": "regular"},
        )

        add_strategy = _DirectionalBoostAddHarness()
        add_strategy.directional_30d_risk_boost_multiplier = 1.5
        add_strategy.directional_30d_risk_nonconfirmation_multiplier = 0.5
        add_strategy.directional_30d_risk_boost_require_volume_expansion = True
        add_strategy.directional_30d_volume_ratio_threshold = 2.0
        add_strategy.directional_30d_risk_adjust_long_only = True
        short_state = _state(volume=10)
        short_state.direction = "short"
        for layer in short_state.layers:
            layer.direction = "short"
        add_volume, add_snapshot = add_strategy._calculate_directional_boosted_add_sizing(
            short_state,
            _bar("jm2609", 100.0),
            short_history,
            "regular_add",
        )

        self.assertEqual(1_000.0, entry["risk_amount"])
        self.assertEqual(10, entry["selected_volume"])
        self.assertEqual(5, add_volume)
        self.assertEqual(1.0, add_snapshot["directional_30d_risk_boost_multiplier"])

    def test_asymmetric_double_volume_long_only_still_scales_long_hit_and_miss(self) -> None:
        strategy = self._asymmetric_double_volume_strategy()
        strategy.directional_30d_risk_adjust_long_only = True
        closes = [100.0] + [95.0] * 29 + [110.0]
        miss_history = _history_from_closes(closes, volumes=[100.0] * 31)
        hit_history = _history_from_closes(
            closes,
            volumes=[100.0] * 11 + [100.0] * 10 + [199.0] * 9 + [210.0],
        )

        miss = strategy._directional_30d_risk_boost_snapshot("long", miss_history)
        hit = strategy._directional_30d_risk_boost_snapshot("long", hit_history)

        self.assertEqual(0.5, miss["directional_30d_risk_boost_multiplier"])
        self.assertEqual(0, miss["directional_30d_risk_boost_applied"])
        self.assertEqual(1.5, hit["directional_30d_risk_boost_multiplier"])
        self.assertEqual(1, hit["directional_30d_risk_boost_applied"])

    def test_volume_confirmation_includes_signal_day_and_applies_boost(self) -> None:
        strategy = self._volume_confirmed_strategy()
        closes = [100.0] + [95.0] * 29 + [110.0]
        volumes = [100.0] * 11 + [50.0] * 10 + [60.0] * 9 + [600.0]
        history = _history_from_closes(closes, volumes=volumes)

        snapshot = strategy._directional_30d_risk_boost_snapshot("long", history)

        self.assertEqual(500.0, snapshot["directional_30d_prior_volume_sum"])
        self.assertEqual(1_140.0, snapshot["directional_30d_recent_volume_sum"])
        self.assertEqual(1, snapshot["directional_30d_volume_expanding"])
        self.assertEqual(1, snapshot["directional_30d_risk_boost_applied"])
        self.assertEqual(1.2, snapshot["directional_30d_risk_boost_multiplier"])
        self.assertEqual(
            "direction_and_volume_confirmed",
            snapshot["directional_30d_risk_boost_reason"],
        )

    def test_volume_confirmation_equal_or_lower_volume_keeps_base_risk(self) -> None:
        strategy = self._volume_confirmed_strategy()
        history = _history_from_closes(
            [100.0] + [95.0] * 29 + [110.0],
            volumes=[100.0] * 31,
        )

        snapshot = strategy._directional_30d_risk_boost_snapshot("long", history)

        self.assertEqual(1, snapshot["directional_30d_risk_boost_aligned"])
        self.assertEqual(0, snapshot["directional_30d_volume_expanding"])
        self.assertEqual(0, snapshot["directional_30d_risk_boost_applied"])
        self.assertEqual(1.0, snapshot["directional_30d_risk_boost_multiplier"])
        self.assertEqual("volume_not_expanding", snapshot["directional_30d_risk_boost_reason"])

    def test_volume_confirmation_requires_strictly_more_than_configured_ratio(self) -> None:
        strategy = self._volume_confirmed_strategy()
        strategy.directional_30d_volume_ratio_threshold = 2.0
        closes = [100.0] + [95.0] * 29 + [110.0]

        equal_snapshot = strategy._directional_30d_risk_boost_snapshot(
            "long",
            _history_from_closes(
                closes,
                volumes=[100.0] * 11 + [100.0] * 10 + [200.0] * 10,
            ),
        )
        above_snapshot = strategy._directional_30d_risk_boost_snapshot(
            "long",
            _history_from_closes(
                closes,
                volumes=[100.0] * 11 + [100.0] * 10 + [199.0] * 9 + [210.0],
            ),
        )

        self.assertEqual(2.0, equal_snapshot["directional_30d_volume_ratio_threshold"])
        self.assertEqual(2_000.0, equal_snapshot["directional_30d_recent_volume_sum"])
        self.assertEqual(1_000.0, equal_snapshot["directional_30d_prior_volume_sum"])
        self.assertEqual(0, equal_snapshot["directional_30d_risk_boost_applied"])
        self.assertEqual("volume_not_expanding", equal_snapshot["directional_30d_risk_boost_reason"])
        self.assertEqual(2_001.0, above_snapshot["directional_30d_recent_volume_sum"])
        self.assertEqual(1, above_snapshot["directional_30d_risk_boost_applied"])
        self.assertEqual(1.2, above_snapshot["directional_30d_risk_boost_multiplier"])

    def test_volume_confirmation_fails_closed_for_invalid_ratio_threshold(self) -> None:
        strategy = self._volume_confirmed_strategy()
        strategy.directional_30d_volume_ratio_threshold = 0.0
        history = _history_from_closes(
            [100.0] + [95.0] * 29 + [110.0],
            volumes=[100.0] * 11 + [50.0] * 10 + [200.0] * 10,
        )

        snapshot = strategy._directional_30d_risk_boost_snapshot("long", history)

        self.assertEqual(0, snapshot["directional_30d_risk_boost_applied"])
        self.assertEqual("invalid_volume_configuration", snapshot["directional_30d_risk_boost_reason"])

    def test_volume_confirmation_fails_closed_for_invalid_volume(self) -> None:
        strategy = self._volume_confirmed_strategy()
        volumes = [100.0] * 31
        volumes[-1] = float("nan")
        history = _history_from_closes(
            [100.0] + [95.0] * 29 + [110.0],
            volumes=volumes,
        )

        snapshot = strategy._directional_30d_risk_boost_snapshot("long", history)

        self.assertEqual(1, snapshot["directional_30d_risk_boost_aligned"])
        self.assertEqual(0, snapshot["directional_30d_risk_boost_applied"])
        self.assertEqual(1.0, snapshot["directional_30d_risk_boost_multiplier"])
        self.assertEqual("invalid_volume_history", snapshot["directional_30d_risk_boost_reason"])

    def test_volume_confirmation_is_applied_by_real_add_sizing_entrypoint(self) -> None:
        strategy = _DirectionalBoostAddHarness()
        strategy.directional_30d_risk_boost_require_volume_expansion = True
        state = _state(volume=10)
        bar = _bar("jm2609", 100.0)
        closes = [100.0] + [95.0] * 29 + [110.0]

        no_expansion, no_expansion_sizing = strategy._calculate_directional_boosted_add_sizing(
            state,
            bar,
            _history_from_closes(closes, volumes=[100.0] * 31),
            "regular_add",
        )
        expansion_volumes = [100.0] * 11 + [50.0] * 10 + [100.0] * 10
        expansion, expansion_sizing = strategy._calculate_directional_boosted_add_sizing(
            state,
            bar,
            _history_from_closes(closes, volumes=expansion_volumes),
            "regular_add",
        )

        self.assertEqual(5, no_expansion)
        self.assertEqual(0, no_expansion_sizing["directional_30d_risk_boost_applied"])
        self.assertEqual(6, expansion)
        self.assertEqual(1, expansion_sizing["directional_30d_risk_boost_applied"])

    def test_directional_30d_boost_applies_to_real_add_sizing_entrypoint(self) -> None:
        strategy = _DirectionalBoostAddHarness()
        state = _state(volume=10)
        history = _history_from_closes([100.0] + [95.0] * 29 + [110.0])
        bar = _bar("jm2609", 100.0)

        expected = {
            "post_quality_add": (5, 6),
            "regular_add": (5, 6),
            "donchian_add": (20, 24),
        }
        for entry_context, (before, after) in expected.items():
            with self.subTest(entry_context=entry_context):
                volume, sizing = strategy._calculate_directional_boosted_add_sizing(
                    state,
                    bar,
                    history,
                    entry_context,
                )

                self.assertEqual(before, sizing["selected_volume_before_directional_30d_boost"])
                self.assertEqual(after, volume)
                self.assertEqual(after, sizing["selected_volume_after_directional_30d_boost"])
                self.assertEqual(1, sizing["directional_30d_risk_boost_aligned"])
                self.assertEqual(1.2, sizing["directional_30d_risk_boost_multiplier"])
                self.assertEqual(
                    sizing["risk_amount_before_directional_30d_boost"] * 1.2,
                    sizing["risk_amount"],
                )

    def test_directional_30d_add_sizing_rounds_down_and_keeps_hard_position_cap(self) -> None:
        strategy = _DirectionalBoostAddHarness()
        state = _state(volume=1)
        history = _history_from_closes([100.0] + [95.0] * 29 + [110.0])
        bar = _bar("jm2609", 100.0)

        volume, sizing = strategy._calculate_directional_boosted_add_sizing(
            state,
            bar,
            history,
            "regular_add",
        )
        self.assertEqual(1, volume)
        self.assertEqual(1, sizing["selected_volume_before_directional_30d_boost"])

        state.layers[0].volume = 100
        volume, sizing = strategy._calculate_directional_boosted_add_sizing(
            state,
            bar,
            history,
            "donchian_add",
        )
        self.assertEqual(100, volume)
        self.assertEqual(100, sizing["selected_volume_after_directional_30d_boost"])

    def test_directional_30d_boost_is_recorded_in_entry_risk_diagnostics(self) -> None:
        strategy = _DirectionalBoostSizingHarness()
        history = _history_from_closes([100.0] + [95.0] * 29 + [110.0])
        bar = _bar("rb2605", 100.0)
        sizing = strategy._calculate_entry_sizing(
            "rb2605.SHFE",
            "long",
            bar,
            history,
            {"signal": "long_case1a", "risk_mode": "regular"},
        )

        strategy._record_entry_risk_diagnostic(
            product_vt_symbol="rb.SHFE",
            contract_vt_symbol="rb2605.SHFE",
            direction="long",
            bar=bar,
            signal="long_case1a",
            layer_kind="base",
            volume=int(sizing["selected_volume"]),
            stop_price=float(sizing["stop_price"]),
            risk_mode="regular",
            sizing_snapshot=sizing,
        )

        diagnostic = strategy.entry_risk_diagnostics[0]
        self.assertEqual(1, diagnostic["directional_30d_risk_boost_aligned"])
        self.assertEqual(1.2, diagnostic["directional_30d_risk_boost_multiplier"])
        self.assertEqual(1_000.0, diagnostic["risk_amount_before_directional_30d_boost"])
        self.assertEqual(1_200.0, diagnostic["target_risk_amount"])

    def test_low_volume_discount_is_recorded_in_entry_risk_diagnostics(self) -> None:
        strategy = _DirectionalBoostSizingHarness()
        strategy.directional_30d_risk_boost_multiplier = 1.5
        strategy.directional_30d_risk_nonconfirmation_multiplier = 1.0
        strategy.directional_30d_risk_adjust_long_only = True
        strategy.directional_30d_risk_boost_require_volume_expansion = True
        strategy.directional_30d_volume_ratio_threshold = 3.0
        strategy.enable_directional_30d_low_volume_risk_discount = True
        strategy.directional_30d_low_volume_ratio_threshold = 0.5
        strategy.directional_30d_low_volume_risk_multiplier = 0.5
        history = _history_from_closes(
            [110.0] + [105.0] * 29 + [100.0],
            volumes=[100.0] * 11 + [100.0] * 10 + [49.0] * 9 + [58.0],
        )
        bar = _bar("rb2605", 100.0)
        sizing = strategy._calculate_entry_sizing(
            "rb2605.SHFE",
            "long",
            bar,
            history,
            {"signal": "long_case1a", "risk_mode": "regular"},
        )

        strategy._record_entry_risk_diagnostic(
            product_vt_symbol="rb.SHFE",
            contract_vt_symbol="rb2605.SHFE",
            direction="long",
            bar=bar,
            signal="long_case1a",
            layer_kind="base",
            volume=int(sizing["selected_volume"]),
            stop_price=float(sizing["stop_price"]),
            risk_mode="regular",
            sizing_snapshot=sizing,
        )

        diagnostic = strategy.entry_risk_diagnostics[0]
        self.assertEqual(1, diagnostic["directional_30d_low_volume_discount_enabled"])
        self.assertEqual(0.5, diagnostic["directional_30d_low_volume_ratio_threshold"])
        self.assertEqual(1, diagnostic["directional_30d_low_volume_discount_applied"])
        self.assertEqual(0.5, diagnostic["directional_30d_risk_boost_multiplier"])
        self.assertEqual(500.0, diagnostic["target_risk_amount"])

    def test_directional_30d_boost_applies_to_every_risk_budget_entry_context(self) -> None:
        strategy = _DirectionalBoostSizingHarness()
        history = _history_from_closes([100.0] + [95.0] * 29 + [110.0])
        bar = _bar("rb2605", 100.0)

        for entry_context in [
            "flat_entry",
            "reverse_entry",
            "rollover_reopen",
            "regular_add",
            "donchian_add",
        ]:
            with self.subTest(entry_context=entry_context):
                sizing = strategy._calculate_entry_sizing(
                    "rb2605.SHFE",
                    "long",
                    bar,
                    history,
                    {"signal": "long_case1a", "risk_mode": "regular"},
                    entry_context=entry_context,
                )

                self.assertEqual(1_000.0, sizing["risk_amount_before_directional_30d_boost"])
                self.assertEqual(1_200.0, sizing["risk_amount"])
                self.assertEqual(12, sizing["contracts_by_risk"])
                self.assertEqual(12, sizing["selected_volume"])

    def test_directional_30d_boost_multiplies_long_risk_for_net_rise(self) -> None:
        strategy = object.__new__(QmtRollPortfolioStrategy)
        strategy.enable_directional_30d_risk_boost = True
        strategy.directional_30d_risk_boost_lookback = 30
        strategy.directional_30d_risk_boost_multiplier = 1.2
        history = _history_from_closes([100.0] + [95.0] * 29 + [110.0])

        snapshot = strategy._directional_30d_risk_boost_snapshot("long", history)

        self.assertAlmostEqual(0.10, snapshot["directional_30d_return"])
        self.assertEqual(1, snapshot["directional_30d_risk_boost_aligned"])
        self.assertEqual(1.2, snapshot["directional_30d_risk_boost_multiplier"])
        self.assertEqual("direction_aligned", snapshot["directional_30d_risk_boost_reason"])

    def test_directional_30d_boost_multiplies_short_risk_for_net_fall(self) -> None:
        strategy = object.__new__(QmtRollPortfolioStrategy)
        strategy.enable_directional_30d_risk_boost = True
        strategy.directional_30d_risk_boost_lookback = 30
        strategy.directional_30d_risk_boost_multiplier = 1.2
        history = _history_from_closes([100.0] + [105.0] * 29 + [90.0])

        snapshot = strategy._directional_30d_risk_boost_snapshot("short", history)

        self.assertAlmostEqual(-0.10, snapshot["directional_30d_return"])
        self.assertEqual(1, snapshot["directional_30d_risk_boost_aligned"])
        self.assertEqual(1.2, snapshot["directional_30d_risk_boost_multiplier"])

    def test_directional_30d_boost_keeps_base_risk_for_opposite_or_flat_move(self) -> None:
        strategy = object.__new__(QmtRollPortfolioStrategy)
        strategy.enable_directional_30d_risk_boost = True
        strategy.directional_30d_risk_boost_lookback = 30
        strategy.directional_30d_risk_boost_multiplier = 1.2

        for direction, end_close in [("long", 90.0), ("short", 110.0), ("long", 100.0)]:
            with self.subTest(direction=direction, end_close=end_close):
                history = _history_from_closes([100.0] + [100.0] * 29 + [end_close])
                snapshot = strategy._directional_30d_risk_boost_snapshot(direction, history)

                self.assertEqual(0, snapshot["directional_30d_risk_boost_aligned"])
                self.assertEqual(1.0, snapshot["directional_30d_risk_boost_multiplier"])
                self.assertEqual("direction_not_aligned", snapshot["directional_30d_risk_boost_reason"])

    def test_directional_30d_boost_fails_closed_without_31_valid_closes(self) -> None:
        strategy = object.__new__(QmtRollPortfolioStrategy)
        strategy.enable_directional_30d_risk_boost = True
        strategy.directional_30d_risk_boost_lookback = 30
        strategy.directional_30d_risk_boost_multiplier = 1.2
        history = _history_from_closes([100.0] * 30)

        snapshot = strategy._directional_30d_risk_boost_snapshot("long", history)

        self.assertEqual(0, snapshot["directional_30d_risk_boost_aligned"])
        self.assertEqual(1.0, snapshot["directional_30d_risk_boost_multiplier"])
        self.assertEqual("insufficient_history", snapshot["directional_30d_risk_boost_reason"])

    def test_long_rollover_accepts_40_observed_bars_without_full_am_initialization(self) -> None:
        strategy = object.__new__(QmtRollPortfolioStrategy)
        strategy.ma_short = 5
        strategy.ma_mid = 10
        strategy.ma_long = 20
        strategy.ma_extra_long = 40
        strategy.long_entry_enabled = True
        strategy.short_entry_enabled = True
        history = _history_from_closes([float(value) for value in range(1, 41)])

        snapshot = strategy._rollover_shape_continuation_snapshot("long", history)

        self.assertEqual(40, snapshot["observed_bar_count"])
        self.assertEqual(40, snapshot["required_bar_count"])
        self.assertEqual(1, snapshot["bullish_alignment"])
        self.assertGreater(snapshot["macd_hist"], 0.0)
        self.assertEqual(1, snapshot["allowed"])
        self.assertEqual("shape_and_macd_aligned", snapshot["reason"])

    def test_short_rollover_accepts_bearish_alignment_and_negative_macd(self) -> None:
        strategy = object.__new__(QmtRollPortfolioStrategy)
        strategy.ma_short = 5
        strategy.ma_mid = 10
        strategy.ma_long = 20
        strategy.ma_extra_long = 40
        strategy.long_entry_enabled = True
        strategy.short_entry_enabled = True
        history = _history_from_closes([float(value) for value in range(40, 0, -1)])

        snapshot = strategy._rollover_shape_continuation_snapshot("short", history)

        self.assertEqual(1, snapshot["bearish_alignment"])
        self.assertLess(snapshot["macd_hist"], 0.0)
        self.assertEqual(1, snapshot["allowed"])

    def test_rollover_shape_requires_40_real_observations_not_zero_padding(self) -> None:
        strategy = object.__new__(QmtRollPortfolioStrategy)
        strategy.ma_short = 5
        strategy.ma_mid = 10
        strategy.ma_long = 20
        strategy.ma_extra_long = 40
        strategy.long_entry_enabled = True
        strategy.short_entry_enabled = True
        padded = [0.0] * 81 + [float(value) for value in range(1, 40)]
        am = _short_history_array_manager(padded)
        am.count = 39

        history = strategy._build_observed_array_manager_history(am)
        snapshot = strategy._rollover_shape_continuation_snapshot("long", history)

        self.assertEqual(39, len(history))
        self.assertEqual(39, snapshot["observed_bar_count"])
        self.assertEqual(0, snapshot["allowed"])
        self.assertEqual("insufficient_indicator_history", snapshot["reason"])

    def test_shrink_policy_keeps_previous_volume_when_capacity_is_sufficient(self) -> None:
        strategy = object.__new__(QmtRollPortfolioStrategy)

        volume, reason = strategy._rollover_shape_reopen_volume(
            previous_volume=2,
            sizing_snapshot={"selected_volume": 5},
            volume_policy="shrink_to_allowed",
        )

        self.assertEqual(2, volume)
        self.assertEqual("previous_volume_fully_allowed", reason)

    def test_shrink_policy_reduces_to_allowed_positive_volume(self) -> None:
        strategy = object.__new__(QmtRollPortfolioStrategy)

        volume, reason = strategy._rollover_shape_reopen_volume(
            previous_volume=2,
            sizing_snapshot={"selected_volume": 1},
            volume_policy="shrink_to_allowed",
        )

        self.assertEqual(1, volume)
        self.assertEqual("reduced_to_allowed_volume", reason)

    def test_exact_policy_remains_reproducible_and_skips_partial_capacity(self) -> None:
        strategy = object.__new__(QmtRollPortfolioStrategy)

        volume, reason = strategy._rollover_shape_reopen_volume(
            previous_volume=2,
            sizing_snapshot={"selected_volume": 1},
            volume_policy="exact_or_skip",
        )

        self.assertEqual(0, volume)
        self.assertEqual("previous_volume_not_fully_allowed", reason)

    def test_unknown_volume_policy_fails_closed(self) -> None:
        strategy = object.__new__(QmtRollPortfolioStrategy)

        volume, reason = strategy._rollover_shape_reopen_volume(
            previous_volume=2,
            sizing_snapshot={"selected_volume": 2},
            volume_policy="unknown",
        )

        self.assertEqual(0, volume)
        self.assertEqual("invalid_rollover_volume_policy", reason)

    def test_rollover_reopens_exact_previous_volume_with_non_inited_40_bar_contract(self) -> None:
        strategy = _RolloverHarness(allowed_volume=5)
        state = _state(volume=2)
        bars = {
            "jm2609.DCE": _bar("jm2609", 100.0),
            "jm2701.DCE": _bar("jm2701", 40.0),
        }

        strategy._handle_rollover(state, "jm2701.DCE", bars)

        self.assertEqual([("jm2609.DCE", 0)], strategy.targets)
        self.assertEqual(1, len(strategy.opened))
        self.assertEqual("jm2701.DCE", strategy.opened[0]["contract"])
        self.assertEqual(2, strategy.opened[0]["volume"])
        self.assertEqual(40, strategy.opened[0]["history_count"])
        self.assertEqual("targeted", strategy.rollover_shape_same_volume_diagnostics[0]["status"])
        self.assertEqual("full", strategy.rollover_shape_same_volume_diagnostics[0]["volume_outcome"])
        self.assertEqual([("jm.DCE", 2, False)], strategy.reservations)

    def test_continuous_mode_uses_one_target_bar_and_old_contract_indicator_history(self) -> None:
        strategy = _RolloverHarness(
            allowed_volume=5,
            history_mode="backwards_ratio_continuous",
            target_closes=[40.0],
        )
        state = _state(volume=2)
        bars = {
            "jm2609.DCE": _bar("jm2609", 100.0),
            "jm2701.DCE": _bar("jm2701", 40.0),
        }

        strategy._handle_rollover(state, "jm2701.DCE", bars)

        self.assertEqual(1, len(strategy.opened))
        self.assertEqual(2, strategy.opened[0]["volume"])
        self.assertEqual(41, strategy.opened[0]["history_count"])
        diagnostic = strategy.rollover_shape_same_volume_diagnostics[0]
        self.assertEqual("backwards_ratio_continuous", diagnostic["history_mode"])
        self.assertEqual(1, diagnostic["target_observed_bar_count"])
        self.assertEqual(41, diagnostic["source_observed_bar_count"])
        self.assertEqual(1, diagnostic["same_day_bar_ready"])
        self.assertEqual(1, diagnostic["market_data_ready"])
        self.assertEqual(1, diagnostic["metadata_ready"])
        self.assertAlmostEqual(0.4, diagnostic["roll_adjustment_ratio"])
        self.assertEqual("targeted", diagnostic["status"])

    def test_continuous_mode_rejects_target_bar_without_trading_volume(self) -> None:
        strategy = _RolloverHarness(
            allowed_volume=5,
            history_mode="backwards_ratio_continuous",
            target_closes=[40.0],
        )
        state = _state(volume=2)
        bars = {
            "jm2609.DCE": _bar("jm2609", 100.0),
            "jm2701.DCE": _bar("jm2701", 40.0, volume=0),
        }

        strategy._handle_rollover(state, "jm2701.DCE", bars)

        self.assertEqual([], strategy.opened)
        diagnostic = strategy.rollover_shape_same_volume_diagnostics[0]
        self.assertEqual("skipped", diagnostic["status"])
        self.assertEqual("target_same_day_market_not_tradable", diagnostic["reason"])
        self.assertEqual(0, diagnostic["market_data_ready"])

    def test_continuous_mode_appends_target_bar_when_old_contract_stopped_previous_day(self) -> None:
        strategy = _RolloverHarness(
            allowed_volume=5,
            history_mode="backwards_ratio_continuous",
            target_closes=[40.0],
            engine_bars={
                "jm2609.DCE": _bar(
                    "jm2609",
                    100.0,
                    bar_datetime=datetime(2026, 8, 19, 15, 0),
                )
            },
        )
        state = _state(volume=2)
        bars = {"jm2701.DCE": _bar("jm2701", 40.0)}

        strategy._handle_rollover(state, "jm2701.DCE", bars)

        self.assertEqual(1, len(strategy.opened))
        self.assertEqual(42, strategy.opened[0]["history_count"])
        diagnostic = strategy.rollover_shape_same_volume_diagnostics[0]
        self.assertEqual(1, diagnostic["target_bar_appended"])
        self.assertEqual(41, diagnostic["source_observed_bar_count"])
        self.assertEqual(42, diagnostic["observed_bar_count"])

    def test_continuous_mode_rejects_incomplete_target_contract_metadata(self) -> None:
        strategy = _RolloverHarness(
            allowed_volume=5,
            history_mode="backwards_ratio_continuous",
            target_closes=[40.0],
            target_price_tick=0.0,
        )
        state = _state(volume=2)
        bars = {
            "jm2609.DCE": _bar("jm2609", 100.0),
            "jm2701.DCE": _bar("jm2701", 40.0),
        }

        strategy._handle_rollover(state, "jm2701.DCE", bars)

        self.assertEqual([], strategy.opened)
        diagnostic = strategy.rollover_shape_same_volume_diagnostics[0]
        self.assertEqual("skipped", diagnostic["status"])
        self.assertEqual("target_contract_metadata_incomplete", diagnostic["reason"])
        self.assertEqual(0, diagnostic["metadata_ready"])

    def test_rollover_releases_old_margin_before_exact_capacity_sizing(self) -> None:
        strategy = _RolloverHarness(allowed_volume=5)
        state = _state(volume=2)
        bars = {
            "jm2609.DCE": _bar("jm2609", 100.0),
            "jm2701.DCE": _bar("jm2701", 40.0),
        }

        strategy._handle_rollover(state, "jm2701.DCE", bars)

        self.assertEqual(50.0, strategy.sizing_margin_seen)
        self.assertEqual(50.0, strategy.sizing_cluster_margin_seen)

    def test_rollover_does_not_release_old_margin_when_old_bar_only_comes_from_engine(self) -> None:
        strategy = _RolloverHarness(
            allowed_volume=5,
            engine_bars={"jm2609.DCE": _bar("jm2609", 100.0)},
        )
        strategy.total_margin_in_use = 50.0
        strategy.cluster_margin_usage = {"ferrous": 50.0}
        strategy.risk_cluster_margin_in_use = 50.0
        state = _state(volume=2)
        bars = {"jm2701.DCE": _bar("jm2701", 40.0)}

        strategy._handle_rollover(state, "jm2701.DCE", bars)

        self.assertEqual(50.0, strategy.sizing_margin_seen)
        self.assertEqual(50.0, strategy.sizing_cluster_margin_seen)
        sizing = strategy.opened[0]["sizing"]
        self.assertEqual(0, sizing["rollover_old_contract_in_risk_snapshot"])
        self.assertEqual(0.0, sizing["rollover_released_margin"])

    def test_default_off_keeps_non_inited_rollover_close_only(self) -> None:
        strategy = _RolloverHarness(allowed_volume=5, candidate_enabled=False)
        state = _state(volume=2)
        bars = {
            "jm2609.DCE": _bar("jm2609", 100.0),
            "jm2701.DCE": _bar("jm2701", 40.0),
        }

        strategy._handle_rollover(state, "jm2701.DCE", bars)

        self.assertEqual([("jm2609.DCE", 0)], strategy.targets)
        self.assertEqual([], strategy.opened)
        self.assertEqual([], strategy.rollover_shape_same_volume_diagnostics)

    def test_drawdown_guard_skip_is_in_candidate_diagnostics(self) -> None:
        strategy = _RolloverHarness(allowed_volume=5, guard_passed=False)
        state = _state(volume=2)
        bars = {
            "jm2609.DCE": _bar("jm2609", 100.0),
            "jm2701.DCE": _bar("jm2701", 40.0),
        }

        strategy._handle_rollover(state, "jm2701.DCE", bars)

        self.assertEqual([], strategy.opened)
        self.assertEqual(1, len(strategy.rollover_shape_same_volume_diagnostics))
        self.assertEqual(
            "rollover_reopen_portfolio_drawdown_guard",
            strategy.rollover_shape_same_volume_diagnostics[0]["reason"],
        )

    def test_rollover_reduces_to_allowed_volume_when_full_previous_volume_is_not_allowed(self) -> None:
        strategy = _RolloverHarness(allowed_volume=1)
        state = _state(volume=2)
        bars = {
            "jm2609.DCE": _bar("jm2609", 100.0),
            "jm2701.DCE": _bar("jm2701", 40.0),
        }

        strategy._handle_rollover(state, "jm2701.DCE", bars)

        self.assertEqual([("jm2609.DCE", 0)], strategy.targets)
        self.assertEqual(1, len(strategy.opened))
        self.assertEqual(1, strategy.opened[0]["volume"])
        self.assertEqual([("jm.DCE", 1, False)], strategy.reservations)
        diagnostic = strategy.rollover_shape_same_volume_diagnostics[0]
        self.assertEqual("targeted", diagnostic["status"])
        self.assertEqual("reduced", diagnostic["volume_outcome"])
        self.assertEqual(1, diagnostic["was_reduced"])
        self.assertEqual("reduced_to_allowed_volume", diagnostic["reason"])

    def test_rollover_skips_when_no_positive_volume_is_allowed(self) -> None:
        strategy = _RolloverHarness(allowed_volume=0)
        state = _state(volume=2)
        bars = {
            "jm2609.DCE": _bar("jm2609", 100.0),
            "jm2701.DCE": _bar("jm2701", 40.0),
        }

        strategy._handle_rollover(state, "jm2701.DCE", bars)

        self.assertEqual([], strategy.opened)
        diagnostic = strategy.rollover_shape_same_volume_diagnostics[0]
        self.assertEqual("skipped", diagnostic["status"])
        self.assertEqual("no_positive_volume_allowed", diagnostic["reason"])


if __name__ == "__main__":
    unittest.main()
