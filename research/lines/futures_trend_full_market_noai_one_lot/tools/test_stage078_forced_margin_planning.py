"""Forced margin must separate unfilled intentions and projected real closes."""
from copy import deepcopy
from dataclasses import asdict, replace
from datetime import datetime
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_stage074_pending_close_quantity as close_fixtures
from stage068_fractional_risk import FractionalSignalRiskReceipt
from stage075_fractional_weekly import WeeklyEntryAuthorization
from vnpy.trader.constant import Direction, Offset, Status
from vnpy.trader.object import OrderData

try:
    from stage078_forced_margin_planning import ForcedMarginIntentMixin
except ModuleNotFoundError as exc:
    if exc.name != 'stage078_forced_margin_planning':
        raise
    class ForcedMarginIntentMixin:
        pass


class ForcedMarginPlanningTests(unittest.TestCase):
    strategy_base = None
    engine_base = None

    def fixture(self, direction='long'):
        helper = close_fixtures.ActualFractionalPendingCloseQuantityTests()
        if self.strategy_base is not None:
            helper.strategy_base, helper.engine_base = self.strategy_base, self.engine_base
        e, s, vt, b, state = helper.fixture(direction)
        if not isinstance(s, ForcedMarginIntentMixin):
            s.__class__ = type('ForcedPlanningStrategy', (ForcedMarginIntentMixin, s.__class__), {})
        s.enable_forced_margin_deleverage = True
        s.forced_margin_deleverage_trigger_ratio = .95
        s.forced_margin_deleverage_target_ratio = .8
        s.forced_margin_deleverage_broker_multiplier = 1.65
        s.forced_margin_deleverage_max_reductions_per_day = 20
        s.estimated_equity = s.settled_balance = 750.
        s.total_margin_in_use = 550.
        s.cluster_margin_usage = {'IC': 550.}
        return e, s, vt, b, state

    def intent(self, direction='long', quantity=17, price=110., equity=1000.):
        e, s, vt, b, state = self.fixture(direction)
        e.datetime = b.datetime = datetime(2021, 12, 10)
        b.open_price = b.high_price = b.low_price = b.close_price = price
        s.pos_data[vt] = 0
        s.equity_start_positions = {}
        s.estimated_equity = s.settled_balance = equity
        s.total_margin_in_use = 0.
        s.cluster_margin_usage = {}
        s._reset_intrabar_reservations()
        layer = state.layers[0]
        layer.volume, layer.entry_price, layer.entry_price_synced = quantity, price, False
        layer.stage068_signal_risk_budget = FractionalSignalRiskReceipt(
            'original-signal', vt, state.product_vt_symbol, direction, layer.signal,
            '2021-12-10T00:00:00', 'flat_entry', 1000000., .005, 5000., 100., price-10 if direction=='long' else price+10, quantity)
        layer.stage059_weekly_authorization = WeeklyEntryAuthorization(vt, state.product_vt_symbol,
            direction, layer.signal, '2021-12-10', '{"original":true}')
        s._reserve_intrabar_entry(state.product_vt_symbol, {'margin_per_contract': price}, quantity, count_active_position=True)
        s.pending_entry_diagnostics[(vt, direction)] = [0]
        s.entry_risk_diagnostics = [{'volume': quantity}]
        s.execution_price_overrides[vt] = price
        s.set_target(vt, quantity if direction=='long' else -quantity)
        s.forced_margin_deleverage_broker_multiplier = 1.
        s.rebalance_portfolio({vt:b})
        return e, s, vt, b, state, layer

    def test_exact_failed_unsynced_seventeen_is_cancelled_without_fake_close(self):
        for direction in ('long', 'short'):
            with self.subTest(direction=direction):
                e, s, vt, b, state, layer = self.intent(direction)
                receipt = layer.stage068_signal_risk_budget
                before = (s.realized_pnl, s.loss_streak, deepcopy(s.product_direction_outcome_history))
                s._process_forced_margin_deleverage({vt:b})
                self.assertEqual(s.get_pos(vt), 0)
                self.assertEqual(s.get_target(vt), 0)
                self.assertFalse(state.layers)
                self.assertFalse(e.active_limit_orders)
                self.assertFalse(e.trades)
                self.assertFalse(s.pending_close_lots)
                self.assertFalse(s.pending_close_reasons)
                self.assertEqual(s.forced_margin_deleverage_closed_volume, 0)
                self.assertEqual((s.realized_pnl, s.loss_streak, s.product_direction_outcome_history), before)
                self.assertEqual(s.forced_margin_pending_open_cancel_count, 1)
                self.assertEqual(s.forced_margin_pending_open_cancel_volume, 17)
                self.assertEqual(s.stage078_intent_cancellations[0]['risk_receipts'], [asdict(receipt)])
                self.assertIs(layer.stage068_signal_risk_budget, receipt)
                self.assertEqual(s.pending_margin_reservation, 0.)
                self.assertEqual(s.pending_cluster_margin_reservation.get('IC', 0.), 0.)
                self.assertNotIn('IC.CFFEX', s.pending_active_products)
                self.assertNotIn(vt, s.execution_price_overrides)
                self.assertNotIn((vt, direction), s.pending_entry_diagnostics)

    def test_actual_five_only_plans_two_closes_and_repeated_call_is_idempotent(self):
        for direction in ('long', 'short'):
            with self.subTest(direction=direction):
                e, s, vt, b, state = self.fixture(direction)
                s._process_forced_margin_deleverage({vt:b})
                s._process_forced_margin_deleverage({vt:b})
                self.assertEqual(s.get_pos(vt), 5 if direction=='long' else -5)
                self.assertEqual(s.get_target(vt), 3 if direction=='long' else -3)
                self.assertEqual(state.active_volume(), 3)
                self.assertEqual([x['volume'] for x in s.pending_close_lots[vt]], [2])
                self.assertEqual(s.forced_margin_deleverage_closed_volume, 2)
                self.assertEqual(s.forced_margin_deleverage_count, 1)
                self.assertGreaterEqual(s._estimate_margin_usage({vt:b}), 550.)
                self.assertFalse(e.trades)

    def test_existing_rsi_pending_close_is_counted_before_forced_reduction(self):
        e, s, vt, b, state = self.fixture()
        s._process_rsi_partial_exit(state, b, 99)
        s._apply_state_target(state)
        before = s.realized_pnl
        s._process_forced_margin_deleverage({vt:b})
        self.assertEqual([x['volume'] for x in s.pending_close_lots[vt]], [2])
        self.assertEqual(s.get_target(vt), 3)
        self.assertEqual(s.forced_margin_deleverage_closed_volume, 0)
        self.assertEqual(s.realized_pnl, before)

    def test_full_lifecycle_pending_close_is_not_reduced_again(self):
        e, s, vt, b, state = self.fixture()
        s._close_position_when_target_unavailable('IC.CFFEX', state=state, target_contract='', bars={vt:b}, reason='contract_lifecycle_exit')
        before = (s.realized_pnl, deepcopy(s.pending_close_lots))
        s._process_forced_margin_deleverage({vt:b})
        self.assertEqual((s.realized_pnl, s.pending_close_lots), before)
        self.assertEqual(s.forced_margin_deleverage_closed_volume, 0)
        self.assertGreaterEqual(s._estimate_margin_usage({vt:b}), 550.)

    def test_under_trigger_and_disabled_do_not_cancel_intent(self):
        for disabled in (False, True):
            e, s, vt, b, state, layer = self.intent(equity=3000.)
            s.enable_forced_margin_deleverage = not disabled
            s._process_forced_margin_deleverage({vt:b})
            self.assertEqual(state.active_volume(), 17)
            self.assertEqual(len(e.active_limit_orders), 1)
            self.assertEqual(s.get_target(vt), 17)

    def test_cancelled_old_open_cannot_reappear_on_next_real_bar(self):
        e, s, vt, b, state, layer = self.intent()
        s._process_forced_margin_deleverage({vt:b})
        e.datetime = b.datetime = datetime(2021, 12, 13)
        e.history_data[(e.datetime, vt)] = b
        e.prepare_opening_risk(e.datetime)
        e.cross_delayed_orders()
        s.rebalance_portfolio({vt:b})
        self.assertFalse(e.trades)
        self.assertFalse(e.active_limit_orders)

    def test_cached_quote_can_cancel_missing_today_pending_intent(self):
        e, s, vt, b, state, layer = self.intent()
        e.datetime = datetime(2021,12,13)
        other = deepcopy(b); other.symbol = 'OTHER'; other.vt_symbol = 'OTHER.CFFEX'
        other.datetime = e.datetime
        s._process_forced_margin_deleverage({other.vt_symbol:other})
        self.assertEqual(s.get_target(vt), 0)
        self.assertFalse(state.layers)
        self.assertFalse(e.active_limit_orders)
        self.assertEqual(s.stage078_intent_cancellations[0]['date'],'2021-12-13')

    def test_deferred_force_then_real_close_preserves_actual_margin_until_fill(self):
        e, s, vt, b, state = self.fixture()
        s._process_forced_margin_deleverage({vt:b})
        s.rebalance_portfolio({vt:b})
        e.datetime = datetime(2021, 12, 13)
        e.cross_delayed_orders()
        s._process_forced_margin_deleverage({vt:b})
        self.assertEqual(s.get_pos(vt), 5)
        self.assertEqual(sum(x['volume'] for x in s.pending_close_lots[vt]), 2)
        self.assertGreaterEqual(s._estimate_margin_usage({vt:b}), 550.)
        e.datetime = b.datetime = datetime(2021, 12, 14)
        e.history_data[(e.datetime, vt)] = b
        e.prepare_opening_risk(e.datetime)
        e.cross_delayed_orders()
        s._process_forced_margin_deleverage({vt:b})
        self.assertEqual(s.get_pos(vt), 3)
        self.assertEqual(state.active_volume(), 3)
        self.assertNotIn(vt, s.pending_close_lots)
        self.assertEqual(s._estimate_margin_usage({vt:b}), 330.)

    def add_intent(self, e, s, old_state, old_bar, *, product='IF.CFFEX', vt='IF202112.CFFEX', quantity=12, price=100.):
        state, bar = deepcopy(old_state), deepcopy(old_bar)
        state.product_vt_symbol, state.contract_vt_symbol = product, vt
        layer = state.layers[0]
        layer.volume, layer.entry_price = quantity, price
        layer.stage068_signal_risk_budget = replace(layer.stage068_signal_risk_budget,
            snapshot_id='second-signal', contract_vt_symbol=vt, product_vt_symbol=product,
            authorized_volume=quantity, stop_price=price-10.)
        bar.symbol, bar.vt_symbol = vt.split('.')[0], vt
        bar.open_price = bar.high_price = bar.low_price = bar.close_price = price
        s.states[product] = state
        s.source_symbol_by_contract[vt] = product
        s.product_symbols.append(product)
        s.pos_data[vt] = 0
        e.bars[vt] = bar
        e.history_data[(e.datetime, vt)] = bar
        e.sizes[vt], e.priceticks[vt], e.slippages[vt], e.rates[vt] = 10, 1, 0, 0
        e.research_metadata[vt] = deepcopy(e.research_metadata[old_bar.vt_symbol])
        e.research_metadata[vt]['product'] = product.split('.')[0]
        s._reserve_intrabar_entry(product, {'margin_per_contract':price}, quantity, count_active_position=True)
        s.set_target(vt, quantity)
        return state, bar

    def test_original_three_priorities_choose_intent_and_stop_at_target(self):
        for priority, expected in [('largest_margin','IC202112.CFFEX'),
                                   ('largest_volume','IF202112.CFFEX'),
                                   ('largest_unrealized_loss','IF202112.CFFEX')]:
            with self.subTest(priority=priority):
                e, s, vt, b, state, layer = self.intent(quantity=8, price=200., equity=2500.)
                second, second_bar = self.add_intent(e,s,state,b)
                if priority == 'largest_unrealized_loss':second.layers[0].entry_price = 120.
                s.forced_margin_deleverage_priority = priority
                s.forced_margin_deleverage_trigger_ratio = 1.
                s.forced_margin_deleverage_target_ratio = .7
                bars = {vt:b, second_bar.vt_symbol:second_bar}
                s.rebalance_portfolio(bars)
                s._process_forced_margin_deleverage(bars)
                self.assertEqual([x['vt_symbol'] for x in s.stage078_intent_cancellations], [expected])
                self.assertEqual(s.forced_margin_deleverage_closed_volume, 0)
                self.assertEqual(len(e.active_limit_orders), 1)
                self.assertEqual(sum(x.active_volume() for x in s.states.values()), 12 if expected==vt else 8)
                expected_reserve = 1200. if expected==vt else 1600.
                self.assertEqual(s.pending_margin_reservation, expected_reserve)

    def test_mixed_synced_layers_pending_close_and_unfilled_open_only_cancels_open(self):
        e, s, vt, b, state = self.fixture()
        s._process_rsi_partial_exit(state, b, 99)
        layer = deepcopy(state.layers[0]);layer.volume=17;layer.entry_price_synced=False
        state.layers.append(layer)
        s._reset_intrabar_reservations()
        s._reserve_intrabar_entry(state.product_vt_symbol, {'margin_per_contract':110.}, 17, count_active_position=True)
        s.set_target(vt, 20)
        for name, offset, direction, volume in [('new-open',Offset.OPEN,Direction.LONG,17), ('existing-close',Offset.CLOSE,Direction.SHORT,2)]:
            order=OrderData(symbol=b.symbol,exchange=b.exchange,orderid=name,direction=direction,offset=offset,
                            volume=volume,price=110.,status=Status.SUBMITTING,datetime=e.datetime,gateway_name='BACKTESTING')
            e.active_limit_orders[order.vt_orderid]=order;e.limit_orders[order.vt_orderid]=order;s.active_orderids.add(order.vt_orderid)
        before=(s.realized_pnl,deepcopy(s.pending_close_lots),deepcopy(s.pending_close_reasons))
        s._process_forced_margin_deleverage({vt:b})
        self.assertEqual(s.get_pos(vt),5);self.assertEqual(s.get_target(vt),3)
        self.assertEqual(state.active_volume(),3);self.assertTrue(all(x.entry_price_synced for x in state.layers))
        self.assertEqual((s.realized_pnl,s.pending_close_lots,s.pending_close_reasons),before)
        self.assertEqual([x.offset for x in e.active_limit_orders.values()],[Offset.CLOSE])
        self.assertEqual(s.pending_margin_reservation,0.)
        self.assertEqual(s.total_margin_in_use,550.)
        self.assertEqual(s.cluster_margin_usage,{'IC':550.})
        self.assertGreaterEqual(s._estimate_margin_usage({vt:b}),550.)

    def test_cancel_pending_then_native_deleverages_actual_without_changing_limits(self):
        e, s, vt, b, state, layer = self.intent()
        second, second_bar = self.add_intent(e,s,state,b,quantity=5,price=110.)
        second.layers[0].entry_price_synced=True
        s.pos_data[second_bar.vt_symbol]=5
        s.set_target(second_bar.vt_symbol,5)
        s.estimated_equity=s.settled_balance=750.
        s.forced_margin_deleverage_broker_multiplier=1.65
        settings=(s.forced_margin_deleverage_trigger_ratio,s.forced_margin_deleverage_target_ratio,
                  s.forced_margin_deleverage_priority,s.forced_margin_deleverage_max_reductions_per_day)
        s._process_forced_margin_deleverage({vt:b,second_bar.vt_symbol:second_bar})
        self.assertEqual(s.forced_margin_pending_open_cancel_volume,17)
        self.assertEqual(s.forced_margin_deleverage_closed_volume,2)
        self.assertEqual(s.get_target(second_bar.vt_symbol),3)
        self.assertEqual(s.get_pos(second_bar.vt_symbol),5)
        self.assertEqual(settings,(s.forced_margin_deleverage_trigger_ratio,s.forced_margin_deleverage_target_ratio,
                  s.forced_margin_deleverage_priority,s.forced_margin_deleverage_max_reductions_per_day))

    def test_projection_flag_is_restored_on_error_and_future_marks_fail_closed(self):
        e, s, vt, b, state = self.fixture()
        with patch.object(s,'_stage078_projected_margin',side_effect=RuntimeError('synthetic-failure')):
            with self.assertRaisesRegex(RuntimeError,'synthetic-failure'):
                s._process_forced_margin_deleverage({vt:b})
        self.assertFalse(s._stage078_forced_planning_active)
        self.assertGreaterEqual(s._estimate_margin_usage({vt:b}),550.)
        b.datetime=datetime(2021,12,11)
        with self.assertRaisesRegex(RuntimeError,'future_margin_mark'):
            s._process_forced_margin_deleverage({vt:b})
        self.assertFalse(s._stage078_forced_planning_active)

    def test_missing_mark_fails_closed_without_cancel_or_close(self):
        e, s, vt, b, state, layer=self.intent()
        e.bars={}
        with self.assertRaisesRegex(RuntimeError,'margin_mark_missing'):
            s._process_forced_margin_deleverage({'other':b})
        self.assertEqual(state.active_volume(),17)
        self.assertFalse(s.pending_close_lots)
        self.assertFalse(e.trades)

    def test_rollover_old_pending_close_survives_new_contract_intent_cancellation(self):
        e,s,old_vt,b,state,layer=self.intent()
        s._reset_intrabar_reservations()
        new_state,new_bar=self.add_intent(e,s,state,b,product='IC.CFFEX',vt='IC202203.CFFEX',quantity=17,price=110.)
        s.pos_data[old_vt]=5
        s.pending_close_lots[old_vt]=[dict(direction='long',entry_price=100.,provisional_exit_price=110.,volume=5)]
        s.pending_close_reasons[old_vt]=[dict(reason='rollover_close',volume=5)]
        s.set_target(old_vt,0)
        s.rebalance_portfolio({old_vt:b,new_bar.vt_symbol:new_bar})
        before=(deepcopy(s.pending_close_lots),deepcopy(s.pending_close_reasons),s.realized_pnl)
        s._process_forced_margin_deleverage({old_vt:b,new_bar.vt_symbol:new_bar})
        self.assertEqual(s.get_pos(old_vt),5);self.assertEqual(s.get_target(old_vt),0)
        self.assertEqual(s.get_pos(new_bar.vt_symbol),0);self.assertEqual(s.get_target(new_bar.vt_symbol),0)
        self.assertEqual((s.pending_close_lots,s.pending_close_reasons,s.realized_pnl),before)
        self.assertEqual([x.offset for x in e.active_limit_orders.values()],[Offset.CLOSE])
        self.assertFalse(new_state.layers)
        self.assertEqual(s.pending_margin_reservation,0.)
        self.assertGreaterEqual(s._estimate_margin_usage({old_vt:b,new_bar.vt_symbol:new_bar}),550.)


class FinalRunnerForcedMarginPlanningTests(ForcedMarginPlanningTests):
    import stage079_run_fractional_risk as final_runner
    strategy_base = final_runner.FeeStrategy
    engine_base = final_runner.FullMarketDailyEngine


class FinalRunnerPendingCloseTransitions(close_fixtures.PendingCloseQuantityTests):
    import stage079_run_fractional_risk as final_runner
    strategy_base = final_runner.FeeStrategy
    engine_base = final_runner.FullMarketDailyEngine


if __name__ == '__main__':
    unittest.main()
