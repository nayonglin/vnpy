"""Pending partial CLOSE regression through real native strategy and daily fills."""
from datetime import datetime
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vnpy.trader.setting import SETTINGS
SETTINGS['log.file'] = False
import stage060_run_contract_weekly_long as old
import test_stage017_lifecycle_regressions as fixtures
from vnpy.trader.constant import Direction, Exchange, Offset, Status
from vnpy.trader.object import BarData, OrderData

try:
    from stage074_pending_close_quantity import PendingCloseQuantityMixin
except ModuleNotFoundError as exc:
    if exc.name != 'stage074_pending_close_quantity':
        raise
    class PendingCloseQuantityMixin:
        pass


class PendingCloseQuantityTests(unittest.TestCase):
    strategy_base = old.FeeStrategy
    engine_base = old.FullMarketDailyEngine

    def fixture(self, direction='long'):
        bases = (self.strategy_base,) if issubclass(self.strategy_base, PendingCloseQuantityMixin) else (PendingCloseQuantityMixin, self.strategy_base)
        cls = type('PendingQuantityStrategy', bases, {})
        with patch.object(fixtures, 'FullMarketDailyEngine', self.engine_base), \
             patch.object(fixtures, 'FullMarketNoAIOneLot', cls):
            engine, strategy, vt, bar = fixtures.LifecycleRegressions().held_index_fixture()
        engine.datetime = datetime(2021, 12, 10)
        bar.datetime = engine.datetime
        bar.open_price = bar.high_price = bar.low_price = bar.close_price = 110
        engine.history_data = {(engine.datetime, vt): bar}
        strategy.equity_settlement_date = '2021-12-09'
        signed = 5 if direction == 'long' else -5
        strategy.pos_data[vt] = signed
        strategy.equity_start_positions = {vt: signed}
        strategy.total_margin_in_use = 500
        strategy.cluster_margin_usage = {'IC': 500}
        state = strategy.states['IC.CFFEX']
        state.direction = direction
        state.layers[0].direction = direction
        state.layers[0].volume = 5
        strategy.set_target(vt, signed)
        strategy.enable_rsi_partial_exit = True
        strategy.rsi_partial_exit_ratio = .5
        strategy.rsi_partial_exit_threshold = 95
        return engine, strategy, vt, bar, state

    def partial(self, direction='long'):
        engine, strategy, vt, bar, state = self.fixture(direction)
        reason = strategy._process_rsi_partial_exit(state, bar, 99 if direction == 'long' else 1)
        self.assertIn('rsi_partial_exit_half', reason)
        strategy._apply_state_target(state)
        self.assertEqual(state.active_volume(), 3)
        self.assertEqual(sum(lot['volume'] for lot in strategy.pending_close_lots[vt]), 2)
        return engine, strategy, vt, bar, state

    def test_pending_rsi_partial_reconcile_does_not_reinflate_long_or_short(self):
        for direction, signed in [('long', 5), ('short', -5)]:
            with self.subTest(direction=direction):
                engine, strategy, vt, bar, state = self.partial(direction)
                strategy._reconcile_state_with_position(state, signed, bar)
                self.assertEqual(state.active_volume(), 3)
                self.assertEqual(strategy.get_pos(vt), signed)
                self.assertEqual(strategy.get_target(vt), 3 if direction == 'long' else -3)
                self.assertTrue(state.rsi_partial_exit_done)

    def test_lifecycle_after_partial_queues_only_residual_and_is_idempotent(self):
        engine, strategy, vt, bar, state = self.partial()
        engine.datetime = bar.datetime = datetime(2021, 12, 15)
        strategy.apply_lifecycle_targets({vt: bar})
        strategy.apply_lifecycle_targets({vt: bar})
        self.assertEqual([x['volume'] for x in strategy.pending_close_lots[vt]], [2, 3])
        self.assertEqual(strategy.get_target(vt), 0)
        self.assertEqual(state.active_volume(), 0)
        self.assertEqual(strategy.get_pos(vt), 5)
        self.assertEqual(strategy.realized_pnl, 500)
        self.assertFalse(engine.trades)

    def test_rollover_after_partial_does_not_queue_closed_contracts_twice(self):
        engine, strategy, vt, bar, state = self.partial()
        strategy.rollover_reopen_enabled = False
        strategy._reconcile_state_with_position(state, 5, bar)
        strategy._handle_rollover(state, 'IC202203.CFFEX', {vt: bar})
        strategy._handle_rollover(state, 'IC202203.CFFEX', {vt: bar})
        self.assertEqual([x['volume'] for x in strategy.pending_close_lots[vt]], [2, 3])
        self.assertEqual(strategy.realized_pnl, 500)
        self.assertEqual(strategy.get_target(vt), 0)

    def real_bar(self, engine, vt):
        engine.datetime = datetime(2021, 12, 14)
        bar = BarData(symbol='IC202112', exchange=Exchange.CFFEX, datetime=engine.datetime,
                      open_price=105, high_price=105, low_price=105, close_price=105,
                      volume=10, gateway_name='SYNTHETIC')
        engine.bars[vt] = bar
        engine.history_data[(engine.datetime, vt)] = bar
        engine.prepare_opening_risk(engine.datetime)
        return bar

    def test_deferred_reissued_partial_close_fills_real_two_and_leaves_three(self):
        engine, strategy, vt, bar, state = self.partial()
        strategy.rebalance_portfolio({vt: bar})
        self.assertEqual(next(iter(engine.active_limit_orders.values())).volume, 2)
        engine.datetime = datetime(2021, 12, 13)
        engine.cross_delayed_orders()
        self.assertFalse(engine.trades)
        strategy._reconcile_state_with_position(state, 5, bar)
        self.assertEqual(state.active_volume(), 3)
        strategy.rebalance_portfolio({vt: bar})
        self.assertEqual(next(iter(engine.active_limit_orders.values())).volume, 2)
        self.real_bar(engine, vt)
        engine.cross_delayed_orders()
        self.assertEqual(strategy.get_pos(vt), 3)
        self.assertEqual(strategy.get_target(vt), 3)
        self.assertEqual(state.active_volume(), 3)
        self.assertNotIn(vt, strategy.pending_close_lots)
        self.assertEqual(next(iter(engine.trades.values())).volume, 2)
        self.assertEqual(strategy.realized_pnl, 100)
        self.assertTrue(state.rsi_partial_exit_done)

    def test_partial_real_execution_keeps_one_pending_until_second_fill(self):
        engine, strategy, vt, bar, state = self.partial()
        real = self.real_bar(engine, vt)
        for number, want_actual, want_pending in [(1, 4, 1), (2, 3, 0)]:
            order = OrderData(symbol='IC202112', exchange=Exchange.CFFEX, orderid=f'partial-{number}',
                              direction=Direction.SHORT, offset=Offset.CLOSE, volume=1, price=105,
                              status=Status.SUBMITTING, datetime=datetime(2021, 12, 10), gateway_name='BACKTESTING')
            engine.limit_orders[order.vt_orderid] = order
            engine.active_limit_orders[order.vt_orderid] = order
            engine._fill_order(order, real)
            strategy._reconcile_state_with_position(state, want_actual, real)
            self.assertEqual(strategy.get_pos(vt), want_actual)
            self.assertEqual(state.active_volume(), 3)
            self.assertEqual(strategy.get_target(vt), 3)
            self.assertEqual(sum(x['volume'] for x in strategy.pending_close_lots.get(vt, [])), want_pending)
        self.assertEqual(strategy.realized_pnl, 100)

    def test_full_pending_with_reset_layers_does_not_rebuild_virtual_position(self):
        engine, strategy, vt, bar, state = self.partial()
        strategy._close_position_when_target_unavailable('IC.CFFEX', state=state, target_contract='',
                                                       bars={vt: bar}, reason='test_close_remaining')
        state.contract_vt_symbol = vt  # native on_bars binds the actual held contract before reconcile
        strategy._reconcile_state_with_position(state, 5, bar)
        self.assertEqual(state.active_volume(), 0)
        self.assertEqual(strategy.get_target(vt), 0)
        self.assertEqual(sum(x['volume'] for x in strategy.pending_close_lots[vt]), 5)

    def test_pending_larger_than_actual_is_rejected_instead_of_hidden(self):
        engine, strategy, vt, bar, state = self.partial()
        strategy.pending_close_lots[vt][0]['volume'] = 6
        with self.assertRaises(RuntimeError):
            strategy._reconcile_state_with_position(state, 5, bar)

    def test_inconsistent_remaining_layer_is_rejected_without_repair(self):
        engine, strategy, vt, bar, state = self.partial()
        state.layers[0].volume = 4
        with self.assertRaises(RuntimeError):
            strategy._reconcile_state_with_position(state, 5, bar)
        self.assertEqual(state.active_volume(), 4)
        self.assertEqual(strategy.get_pos(vt), 5)

    def test_lifecycle_full_close_after_partial_really_fills_five_on_both_sides(self):
        for direction in ['long', 'short']:
            with self.subTest(direction=direction):
                engine, strategy, vt, bar, state = self.partial(direction)
                engine.datetime = bar.datetime = datetime(2021, 12, 15)
                strategy.apply_lifecycle_targets({vt: bar})
                strategy.rebalance_portfolio({vt: bar})
                self.assertEqual(next(iter(engine.active_limit_orders.values())).volume, 5)
                real = self.real_bar(engine, vt)
                real.datetime = engine.datetime = datetime(2021, 12, 16)
                engine.history_data[(engine.datetime, vt)] = real
                engine.cross_delayed_orders()
                strategy._reconcile_state_with_position(state, 0, real)
                self.assertEqual(strategy.get_pos(vt), 0)
                self.assertEqual(strategy.get_target(vt), 0)
                self.assertEqual(state.active_volume(), 0)
                self.assertNotIn(vt, strategy.pending_close_lots)
                self.assertEqual(sum(x.volume for x in engine.trades.values()), 5)
                self.assertEqual(strategy.realized_pnl, 250 if direction == 'long' else -250)

    def test_queue_cannot_exceed_uncommitted_actual_quantity(self):
        engine, strategy, vt, bar, state = self.partial()
        with self.assertRaises(RuntimeError):
            strategy._queue_pending_close_lot(vt, state.layers[0], 110, 4)
        self.assertEqual(sum(x['volume'] for x in strategy.pending_close_lots[vt]), 2)
        self.assertEqual(state.active_volume(), 3)

    def test_normal_reconcile_without_pending_still_tracks_actual_position(self):
        engine, strategy, vt, bar, state = self.fixture()
        state.layers[0].volume = 3
        strategy._reconcile_state_with_position(state, 5, bar)
        self.assertEqual(state.active_volume(), 5)
        self.assertEqual(strategy.get_pos(vt), 5)

    def test_native_queue_before_layer_decrement_remains_valid(self):
        engine, strategy, vt, bar, state = self.partial()
        strategy._close_all_layers(state, 110)
        self.assertEqual([x['volume'] for x in strategy.pending_close_lots[vt]], [2, 3])
        self.assertEqual(strategy.realized_pnl, 500)

    def test_queue_rejects_fractional_boolean_and_wrong_side(self):
        for quantity in [1.5, True, -1]:
            with self.subTest(quantity=quantity):
                engine, strategy, vt, bar, state = self.fixture()
                with self.assertRaises((ValueError, RuntimeError)):
                    strategy._queue_pending_close_lot(vt, state.layers[0], 110, quantity)
        engine, strategy, vt, bar, state = self.fixture()
        state.layers[0].direction = 'short'
        with self.assertRaises(RuntimeError):
            strategy._queue_pending_close_lot(vt, state.layers[0], 110, 1)


class ActualFractionalPendingCloseQuantityTests(PendingCloseQuantityTests):
    """Repeat the exit transitions in the final research runner's real MRO."""
    import stage070_run_fractional_risk as fractional
    strategy_base = fractional.FeeStrategy
    engine_base = fractional.FullMarketDailyEngine


if __name__ == '__main__':
    unittest.main()
