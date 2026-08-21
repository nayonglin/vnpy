from __future__ import annotations

import unittest
from datetime import datetime
from types import SimpleNamespace

import pandas as pd

from vnpy.trader.constant import Exchange, Interval
from vnpy.trader.object import BarData

from qmt_roll_portfolio_strategy import PositionLayer, ProductState, QmtRollPortfolioStrategy


def _history_from_closes(closes: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open": closes,
            "high": [value + 0.5 for value in closes],
            "low": [value - 0.5 for value in closes],
            "close": closes,
            "volume": [100.0] * len(closes),
            "open_interest": [1000.0] * len(closes),
        }
    )


def _bar(symbol: str, close_price: float) -> BarData:
    return BarData(
        gateway_name="test",
        symbol=symbol,
        exchange=Exchange.DCE,
        datetime=datetime(2026, 8, 20, 15, 0),
        interval=Interval.DAILY,
        open_price=close_price,
        high_price=close_price + 0.5,
        low_price=close_price - 0.5,
        close_price=close_price,
        volume=100,
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
    ) -> None:
        self.enable_rollover_shape_same_volume_reopen = candidate_enabled
        self.rollover_shape_volume_policy = volume_policy
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
            "jm2701.DCE": _short_history_array_manager([float(value) for value in range(1, 41)])
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


class RolloverShapeSameVolumeTest(unittest.TestCase):
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
