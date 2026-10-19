"""Preserve the original OPEN authorization through real daily defer/reconcile."""
from copy import deepcopy
from dataclasses import asdict, replace
from datetime import datetime, timedelta
import importlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
from vnpy.trader.setting import SETTINGS
SETTINGS['log.file']=False
import stage079_run_fractional_risk as frozen
import test_stage070_fractional_integration as old
from vnpy.trader.constant import Direction,Offset
from vnpy.trader.utility import ArrayManager
try:
    from stage085_pending_open_lifecycle import PendingOpenLifecycleMixin,PendingOpenLifecycleEngineMixin
except ModuleNotFoundError as exc:
    if exc.name!='stage085_pending_open_lifecycle':raise
    class PendingOpenLifecycleMixin:pass
    class PendingOpenLifecycleEngineMixin:pass


class PendingOpenLifecycleTests(unittest.TestCase):
    runner=frozen

    def fixture(self,direction='short',volume=2):
        e,s,vt,b,o,layer=old.FractionalRunnerIntegration().fixture(price=90 if direction=='short' else 110,direction=direction)
        engine_class=self.runner.FullMarketDailyEngine
        if not issubclass(engine_class,PendingOpenLifecycleEngineMixin):
            engine_class=type('PendingLifecycleEngine',(PendingOpenLifecycleEngineMixin,engine_class),{})
        e.__class__=engine_class
        strategy_class=self.runner.FeeStrategy
        if not issubclass(strategy_class,PendingOpenLifecycleMixin):
            strategy_class=type('PendingLifecycleStrategy',(PendingOpenLifecycleMixin,strategy_class),{})
        s.__class__=strategy_class
        e.datetime=b.datetime=datetime(2021,12,10)
        b.close_price=b.open_price;b.high_price=b.close_price+1;b.low_price=b.close_price-1;b.volume=volume
        e.bars={vt:b};e.history_data={(e.datetime,vt):b}
        e.vt_symbols=[vt]
        s.last_close_prices={vt:b.close_price}
        s.equity_settlement_date='2021-12-09'
        state=s.states['IC.CFFEX'];state.entry_date=layer.entry_date='2021-12-09'
        o.datetime=datetime(2021,12,9)
        layer.stage068_signal_risk_budget=replace(layer.stage068_signal_risk_budget,signal_datetime='2021-12-09T00:00:00')
        if direction=='long':
            auth=layer.stage059_weekly_authorization
            snap=json.loads(auth.snapshot_json);snap['asof_date']='2021-12-09'
            snap['week_last_session']='2021-12-03'
            layer.stage059_weekly_authorization=replace(auth,signal_date='2021-12-09',snapshot_json=json.dumps(snap))
        s.daily_mapping={day:{'IC.CFFEX':vt} for day in ['2021-12-10','2021-12-13','2021-12-14']}
        am=ArrayManager(300)
        for i in range(300):
            sample=deepcopy(b);sample.datetime=datetime(2020,1,1)+timedelta(days=i);sample.volume=100
            am.update_bar(sample)
        s.ams={vt:am}
        s.enable_forced_margin_deleverage=False
        s.enable_weighted_env_gate=s.enable_portfolio_env_gate=False
        s.short_entry_enabled=s.long_entry_enabled=True
        e.prepare_opening_risk(e.datetime)
        return e,s,vt,b,o,layer,state

    def defer(self,missing=False,direction='short'):
        e,s,vt,b,o,layer,state=self.fixture(direction)
        if missing:e.history_data={}
        e.cross_delayed_orders()
        self.assertFalse(e.trades);self.assertEqual(len(e.active_limit_orders),1)
        return e,s,vt,b,o,layer,state

    def later_fill(self,e,s,vt,b,volume=100,price=None):
        real=deepcopy(b);e.datetime=real.datetime=datetime(2021,12,13)
        real.volume=volume
        if price is not None:real.open_price=price
        e.bars[vt]=real;e.history_data[(e.datetime,vt)]=real
        e.prepare_opening_risk(e.datetime);e.cross_delayed_orders()
        return real

    def test_real_low_volume_then_reconcile_then_later_fill_keeps_same_receipt(self):
        for direction in ('short','long'):
            with self.subTest(direction=direction):
                e,s,vt,b,o,layer,state=self.defer(direction=direction)
                receipt=layer.stage068_signal_risk_budget;before=asdict(receipt)
                s._reconcile_state_with_position(state,0,b)
                self.assertEqual(state.layers,[layer]);self.assertIs(state.layers[0].stage068_signal_risk_budget,receipt)
                self.later_fill(e,s,vt,b)
                self.assertEqual(s.get_pos(vt),-3 if direction=='short' else 3)
                self.assertEqual(len(e.trades),1)
                trade=next(iter(e.trades.values()))
                self.assertEqual(trade.signal_datetime.date().isoformat(),'2021-12-09')
                self.assertEqual(json.loads(e.open_budget_audit[-1]['signal_snapshot']),before)

    def test_full_native_on_bars_low_volume_preserves_receipt_and_skips_new_signal_plan(self):
        e,s,vt,b,o,layer,state=self.defer()
        receipt=layer.stage068_signal_risk_budget
        signal=dict(signal='short_case1a',bullish_alignment=False,bearish_alignment=True,ma_mid_value=90.,
                    ma_long_value=90.,ma_long_prev_value=90.,ma_mid_prev_value=90.,risk_mode='regular',breakout=False,rsi_value=50.)
        with patch.object(s,'_generate_signal',return_value=signal),patch.object(s,'_calculate_entry_sizing',wraps=s._calculate_entry_sizing) as sizing:
            s.on_bars({vt:b})
        self.assertIs(state.layers[0],layer);self.assertIs(layer.stage068_signal_risk_budget,receipt)
        self.assertEqual(sizing.call_count,0,'pending intention cannot be reauthorized from a fresh signal')
        self.assertEqual(s.get_target(vt),-3);self.assertEqual(len(e.active_limit_orders),1)
        self.later_fill(e,s,vt,b)
        self.assertEqual(s.get_pos(vt),-3)

    def test_full_native_missing_bar_keeps_order_and_authorization_until_real_fill(self):
        e,s,vt,b,o,layer,state=self.defer(missing=True)
        receipt=layer.stage068_signal_risk_budget
        other=deepcopy(b);other.symbol='OTHER';other.vt_symbol='OTHER.CFFEX'
        s.on_bars({other.vt_symbol:other})
        self.assertEqual(state.layers,[layer]);self.assertIs(layer.stage068_signal_risk_budget,receipt)
        self.assertEqual(len(e.active_limit_orders),1)
        self.assertEqual(s.total_margin_in_use,270.)
        self.assertEqual(s.cluster_margin_usage,{'IC':270.})
        self.assertFalse(e.trades)
        self.later_fill(e,s,vt,b)
        self.assertEqual(s.get_pos(vt),-3)

    def test_unfilled_open_never_contributes_cluster_unrealized_pnl(self):
        e,s,vt,b,o,layer,state=self.defer()
        layer.entry_price=100.
        self.assertEqual(s._estimate_unrealized_pnl_by_cluster({vt:b}).get('IC',0.),0.)

    def test_actual_full_pending_close_plus_unfilled_open_funds_add_and_pnl_is_actual_only(self):
        from qmt_roll_portfolio_strategy import ProductState
        e,s,vt,b,o,layer,state=self.defer()
        other='IF202112.CFFEX';product='IF.CFFEX'
        real=deepcopy(b);real.symbol='IF202112';real.vt_symbol=other
        real.open_price=real.high_price=real.low_price=real.close_price=100.
        s.source_symbol_by_contract[other]=product;s.product_symbols.append(product);s.pos_data[other]=5;s.set_target(other,0)
        s.states[product]=ProductState(product_vt_symbol=product,contract_vt_symbol=other,direction='long',layers=[])
        s.pending_close_lots[other]=[dict(volume=5,direction='long',entry_price=95.,provisional_exit_price=100.)]
        s.risk_cluster_map='IC.CFFEX=shared;IF.CFFEX=shared'
        e.sizes[other]=10;e.bars[other]=real
        bars={vt:b,other:real}
        self.assertEqual(s._estimate_margin_usage(bars),770.)
        self.assertEqual(s._estimate_margin_usage_by_cluster(bars),{'shared':770.})
        self.assertEqual(s._estimate_unrealized_pnl_by_cluster(bars),{'shared':250.})
        s.total_margin_in_use=770.;s.cluster_margin_usage={'shared':770.}
        s._reserve_intrabar_entry(state.product_vt_symbol,{'margin_per_contract':90.},3,count_active_position=True)
        self.assertEqual(s._reserved_margin_in_use(),770.)
        self.assertEqual(s._reserved_cluster_margin('shared'),770.)
        s.pending_margin_reservation+=7.;s.pending_cluster_margin_reservation['shared']+=7.
        self.assertEqual(s._reserved_margin_in_use(),777.)
        self.assertEqual(s._reserved_cluster_margin('shared'),777.)
        s._stage078_forced_planning_active=True
        try:self.assertEqual(s._estimate_margin_usage(bars),270.)
        finally:s._stage078_forced_planning_active=False

    def test_fresh_rollover_funding_counts_new_intent_and_old_actual_separately(self):
        e,s,vt,b,o,layer,state=self.defer()
        previous='IC202109.CFFEX'
        oldbar=deepcopy(b);oldbar.symbol='IC202109';oldbar.vt_symbol=previous;oldbar.close_price=100.
        s.source_symbol_by_contract[previous]='IC.CFFEX';s.pos_data[previous]=-5
        s.pending_close_lots[previous]=[dict(volume=5,direction='short',entry_price=105.,provisional_exit_price=100.)]
        e.sizes[previous]=10;e.bars[previous]=oldbar
        s._stage085_fresh_layers={vt:(layer,layer.stage068_signal_risk_budget)}
        self.assertFalse(s._stage085_status(state)[0],'old deferred intent does not bypass actual product guard')
        self.assertEqual(s._estimate_margin_usage({previous:oldbar,vt:b}),770.)
        s._reserve_intrabar_entry(state.product_vt_symbol,{'margin_per_contract':90.},3,count_active_position=False)
        self.assertEqual(s._reserved_margin_in_use(),770.)

    def test_fresh_native_signal_can_create_first_order_and_original_receipt(self):
        e,s,vt,b,o,layer,state=self.fixture()
        e.cancel_order(s,o.vt_orderid);state.reset();s.set_target(vt,0);s.pending_entry_diagnostics={}
        signal=dict(signal='short_case1a',bullish_alignment=False,bearish_alignment=True,ma_mid_value=90.,
                    ma_long_value=90.,ma_long_prev_value=90.,ma_mid_prev_value=90.,risk_mode='regular',breakout=False,rsi_value=50.)
        with patch.object(s,'_generate_signal',return_value=signal):
            s.on_bars({vt:b})
        self.assertEqual(len(state.layers),1)
        self.assertTrue(hasattr(state.layers[0],'stage068_signal_risk_budget'))
        self.assertEqual(len(e.active_limit_orders),1)
        self.assertGreater(abs(s.get_target(vt)),0)

    def test_new_event_day_mapping_change_cancels_old_without_fake_close(self):
        for mapped in ('','IC202203.CFFEX'):
            e,s,vt,b,o,layer,state=self.defer()
            e.datetime=b.datetime=datetime(2021,12,13)
            s.daily_mapping['2021-12-13']={'IC.CFFEX':mapped} if mapped else {}
            if mapped:
                e.lifecycle_policy.rows[mapped]=dict(e.lifecycle_policy.rows[vt],vt_symbol=mapped)
            before=(s.realized_pnl,deepcopy(s.pending_close_lots))
            s.on_bars({vt:b})
            self.assertEqual(s.get_target(vt),0);self.assertFalse(state.layers);self.assertFalse(e.active_limit_orders)
            self.assertEqual((s.realized_pnl,s.pending_close_lots),before)
            self.assertFalse(e.trades)

    def test_truly_deferred_order_checks_changed_mapping_before_new_day_fill(self):
        e,s,vt,b,o,layer,state=self.defer()
        s.on_bars({vt:b})
        dt=datetime(2021,12,13);real=deepcopy(b);real.datetime=dt;real.volume=100
        s.daily_mapping['2021-12-13']={};e.history_data[(dt,vt)]=real
        e.new_bars(dt)
        self.assertFalse(e.trades);self.assertEqual(s.get_target(vt),0)
        self.assertFalse(s.pending_close_lots);self.assertFalse(state.layers)

    def test_first_normal_next_open_does_not_gain_a_new_mapping_gate(self):
        e,s,vt,b,o,layer,state=self.fixture(volume=100)
        s.daily_mapping['2021-12-10']={}
        e.new_bars(e.datetime)
        opens=[trade for trade in e.trades.values() if trade.offset==Offset.OPEN]
        self.assertEqual(len(opens),1)
        self.assertEqual(opens[0].volume,3)

    def test_status_reads_do_not_duplicate_daily_preservation_audit(self):
        e,s,vt,b,o,layer,state=self.defer()
        s.on_bars({vt:b})
        rows=[x for x in s.stage085_pending_open_events if x['event']=='preserve']
        self.assertEqual(len(rows),1)
        self.assertEqual(json.loads(rows[0]['receipt_json']),asdict(layer.stage068_signal_risk_budget))
        before=len(s.stage085_pending_open_events)
        s._stage085_status(state);s._stage085_status(state)
        self.assertEqual(len(s.stage085_pending_open_events),before)

    def test_no_real_order_does_not_resurrect_orphan_layer_or_target(self):
        e,s,vt,b,o,layer,state=self.fixture()
        e.cancel_order(s,o.vt_orderid)
        s._reconcile_state_with_position(state,0,b)
        self.assertFalse(state.layers);self.assertEqual(s.get_target(vt),0)
        s.rebalance_portfolio({vt:b})
        self.assertFalse(e.active_limit_orders)

    def test_orphan_target_without_layer_or_order_clears_only_open_diagnostics(self):
        e,s,vt,b,o,layer,state=self.fixture()
        e.cancel_order(s,o.vt_orderid);state.reset()
        s.pending_close_reasons['OTHER.CFFEX']=[dict(reason='existing_real_close',volume=1)]
        s._reset_intrabar_reservations()
        self.assertEqual(s.get_target(vt),0)
        self.assertNotIn((vt,'short'),s.pending_entry_diagnostics)
        self.assertEqual(s.pending_close_reasons['OTHER.CFFEX'],[dict(reason='existing_real_close',volume=1)])

    def test_invalid_receipt_and_zero_quantity_cancel_without_authorization_replacement(self):
        for kind in ('missing','wrong_contract','changed_stop','zero','fractional','boolean','nan'):
            e,s,vt,b,o,layer,state=self.defer()
            if kind=='missing':del layer.stage068_signal_risk_budget
            if kind=='wrong_contract':layer.stage068_signal_risk_budget=replace(layer.stage068_signal_risk_budget,contract_vt_symbol='OTHER')
            if kind=='changed_stop':layer.stop_price=101.
            if kind=='zero':layer.volume=o.volume=0
            if kind=='fractional':layer.volume=o.volume=1.5
            if kind=='boolean':layer.volume=o.volume=True
            if kind=='nan':layer.volume=o.volume=float('nan')
            s._reconcile_state_with_position(state,0,b)
            self.assertFalse(state.layers);self.assertEqual(s.get_target(vt),0);self.assertFalse(e.active_limit_orders)
            self.assertFalse(s.pending_close_lots);self.assertFalse(e.trades)

    def test_budget_stop_and_weekly_opening_gates_still_reject_original_intent(self):
        for kind in ('equity','stop','weekly'):
            e,s,vt,b,o,layer,state=self.defer(direction='long')
            s._reconcile_state_with_position(state,0,b)
            if kind=='equity':s.settled_balance=1000.
            if kind=='weekly':e.weekly_contract.allowed=False
            self.later_fill(e,s,vt,b,price=99. if kind=='stop' else None)
            self.assertFalse(e.trades);self.assertEqual(s.get_target(vt),0)

    def test_forced_cancelled_intention_is_not_restored_by_reconcile_or_rebalance(self):
        e,s,vt,b,o,layer,state=self.defer()
        s.enable_forced_margin_deleverage=True
        s.estimated_equity=100.;s.forced_margin_deleverage_trigger_ratio=.95;s.forced_margin_deleverage_target_ratio=.8
        s._process_forced_margin_deleverage({vt:b})
        s._reconcile_state_with_position(state,0,b);s.rebalance_portfolio({vt:b})
        self.assertFalse(state.layers);self.assertEqual(s.get_target(vt),0);self.assertFalse(e.active_limit_orders)

    def test_deadline_uses_existing_lifecycle_gate_without_extra_early_day(self):
        e,s,vt,b,o,layer,state=self.defer()
        s.on_bars({vt:b})
        self.assertEqual(state.layers,[layer])
        e.datetime=b.datetime=datetime(2021,12,15)
        s.daily_mapping['2021-12-15']={'IC.CFFEX':vt}
        s.on_bars({vt:b})
        self.assertFalse(state.layers);self.assertEqual(s.get_target(vt),0)
        self.assertFalse(e.active_limit_orders);self.assertFalse(s.pending_close_lots)

    def test_missing_real_bar_at_lifecycle_cutoff_still_cancels_and_archives_receipt(self):
        e,s,vt,b,o,layer,state=self.defer(missing=True)
        receipt=asdict(layer.stage068_signal_risk_budget)
        e.datetime=datetime(2021,12,15)
        other=deepcopy(b);other.vt_symbol='OTHER.CFFEX';other.datetime=e.datetime
        s.daily_mapping['2021-12-15']={'IC.CFFEX':vt}
        s.on_bars({other.vt_symbol:other})
        self.assertEqual(s.get_target(vt),0);self.assertFalse(state.layers);self.assertFalse(e.active_limit_orders)
        self.assertEqual(json.loads(s.stage085_pending_open_events[-1]['receipt_json']),[receipt])


class Final086PendingOpenLifecycleTests(PendingOpenLifecycleTests):
    import stage086_run_fractional_risk as runner


import test_stage078_forced_margin_planning as forced_fixtures
class Final086ForcedMarginTests(forced_fixtures.ForcedMarginPlanningTests):
    import stage086_run_fractional_risk as final_runner
    strategy_base=final_runner.FeeStrategy
    engine_base=final_runner.FullMarketDailyEngine

    def intent(self,*args,**kwargs):
        # Frozen078 fixtures predate delayed-authorization preservation. Give
        # their synthetic intentions the same complete binding required in085.
        e,s,vt,b,state,layer=super().intent(*args,**kwargs)
        from stage075_fractional_weekly import WeeklyEntryAuthorization
        import test_stage059_contract_weekly_candidate as weekly
        receipt=layer.stage068_signal_risk_budget
        layer.entry_date=state.entry_date=receipt.signal_datetime[:10]
        layer.stop_price=receipt.stop_price
        s.daily_mapping={e.datetime.date().isoformat():{state.product_vt_symbol:vt}}
        if layer.direction=='long':
            snap=weekly.snapshot(state.product_vt_symbol,e.datetime,'signal_close',contract=vt)
            layer.stage059_weekly_authorization=WeeklyEntryAuthorization(vt,state.product_vt_symbol,'long',layer.signal,
                layer.entry_date,json.dumps(snap))
        return e,s,vt,b,state,layer


import test_stage074_pending_close_quantity as close_fixtures
class Final086PendingCloseTests(close_fixtures.PendingCloseQuantityTests):
    import stage086_run_fractional_risk as final_runner
    strategy_base=final_runner.FeeStrategy
    engine_base=final_runner.FullMarketDailyEngine


if __name__=='__main__':unittest.main()
