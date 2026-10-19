"""Fixed 0.5% marked-total-equity sizing; synthetic native gates, no replay."""
from dataclasses import asdict, FrozenInstanceError, replace
from datetime import datetime
import importlib
import math
from pathlib import Path
import unittest
from unittest.mock import patch

VT='rb202005.SHFE'


class FractionalRiskTests(unittest.TestCase):
    def setUp(self):
        entry=Path(__file__).with_name('stage068_fractional_risk.py')
        self.assertTrue(entry.exists(),'fixed 0.5% fractional risk module is missing')
        from vnpy.trader.setting import SETTINGS
        SETTINGS['log.file']=False
        self.m=importlib.import_module('stage068_fractional_risk')

    def fixture(self,**kw):
        import test_stage039_risk_budget_candidate as old
        import stage039_risk_budget_candidate as old_module
        from stage003_candidate import FullMarketNoAIOneLot
        cls=type('FractionalNative',(self.m.FractionalRiskSizingMixin,FullMarketNoAIOneLot),{})
        t=old.RiskBudgetCandidateTest();t.setUp()
        settings=dict(fixed_size=0,max_position_size=self.m.UNBOUNDED_POSITION_SIZE,stage068_risk_fraction=.005)
        settings.update(kw)
        with patch.object(old_module,'FullMarketNativeRiskBudgetOneLot',cls):s,b,h=t.fixture(**settings)
        return t,s,b,h

    def receipt(self,**kw):
        values=dict(snapshot_id='signal-1',contract_vt_symbol=VT,product_vt_symbol='rb.SHFE',direction='long',signal='long_case2',
                    signal_datetime='2020-01-03T00:00:00',entry_context='flat_entry',signal_equity=1000000.,
                    risk_fraction=.005,target_risk_amount=5000.,risk_per_contract=100.,stop_price=100.,authorized_volume=50)
        values.update(kw)
        return self.m.FractionalSignalRiskReceipt(**values)

    def test_fixed_budget_and_exact_integer_floor_never_force_a_minimum_lot(self):
        self.assertEqual(self.m.fractional_budget(1000000),5000.)
        self.assertEqual(self.m.fractional_budget(800000),4000.)
        for eq in (0,-1,None,True,float('nan'),float('inf')):self.assertEqual(self.m.fractional_budget(eq),0.)
        for budget,risk,want in [(5000,100,50),(5000,100.00000001,49),(5000,5001,0),(5000,5000,1),(0,1,0),(1,0,0),(None,1,0),(True,1,0)]:
            self.assertEqual(self.m.whole_contracts(budget,risk),want)

    def test_overrides_remove_only_one_lot_and_currency_formula_limits(self):
        result=self.m.candidate_overrides(Path('/tmp/no_read.csv'))
        self.assertEqual(result['fixed_size'],0);self.assertEqual(result['max_position_size'],2147483647)
        self.assertEqual(result['min_position_size'],1);self.assertEqual(result['max_concurrent_positions'],93)
        self.assertEqual(result['stage068_risk_fraction'],.005)
        self.assertFalse(result['enable_add_position'])

    def test_native_risk_quantity_starts_from_exact_budget_before_env_gate(self):
        t,s,b,h=self.fixture(min_risk_per_trade=999999.,max_risk_per_trade=999999.,enable_weighted_env_gate=True)
        s.current_env_gate_snapshot={'env_gate_weight':.5}
        r=t.sizing(s,b,h)
        self.assertEqual(r['risk_amount'],5000.)
        self.assertEqual(r['contracts_by_risk'],250)
        self.assertEqual(r['selected_volume'],125)
        self.assertEqual(r['stage068_signal_equity'],1000000.)

    def test_streak_overheat_and_directional_currency_factors_do_not_change_budget(self):
        for multiplier in (.1,2.):
            t,s,b,h=self.fixture(min_risk_per_trade=1.,max_risk_per_trade=1.,streak_risk_multipliers=str(multiplier),
                enable_portfolio_overheat_cooldown=True,portfolio_overheat_cooldown_recovery_scale=3.,
                enable_directional_30d_risk_boost=True,directional_30d_risk_boost_multiplier=3.,directional_30d_risk_nonconfirmation_multiplier=.5)
            s.portfolio_overheat_cooldown_scale=multiplier
            r=t.sizing(s,b,h)
            self.assertEqual(r['risk_amount'],5000.)
            self.assertEqual(r['risk_multiplier'],1.)
            self.assertEqual(r['portfolio_overheat_cooldown_scale'],1.)
            self.assertEqual(r['directional_30d_risk_boost_multiplier'],1.)
            self.assertEqual(r['stage068_raw_risk_multiplier'],multiplier)
            self.assertEqual(r['stage068_raw_overheat_scale'],multiplier)
            self.assertEqual(r['stage068_raw_directional_multiplier'],.5)
            self.assertIn('estimated_equity',r['stage068_active_currency_formula'])

    def test_marked_total_equity_not_free_or_sizing_equity_drives_both_directions(self):
        t,s,b,h=self.fixture(sizing_equity_cap=100000.)
        s.total_margin_in_use=10000.;s.estimated_equity=1200000.
        for direction in ('long','short'):
            r=t.sizing(s,b,h,direction)
            self.assertEqual(r['risk_amount'],6000.)
            self.assertEqual(r['sizing_equity'],100000.)
            self.assertLess(r['limited_balance'],100000.)
        for eq in (0,-1,float('nan'),float('inf')):
            s.estimated_equity=eq
            r=t.sizing(s,b,h)
            self.assertEqual(r['risk_amount'],0.);self.assertEqual(r['selected_volume'],0)

    def test_native_zero_gates_are_not_revived_and_env_probe_has_no_old_cap(self):
        for settings,extra in [({'enable_weighted_env_gate':True},{'current_env_gate_snapshot':{'env_gate_weight':0.}}),
                               ({'max_single_trade_capital_usage_ratio':0.},{}),
                               ({'enable_risk_cluster_margin_cap':True,'risk_cluster_map':'rb.SHFE=ferrous','risk_cluster_margin_cap_ratio':0.},{})]:
            t,s,b,h=self.fixture(**settings)
            for k,v in extra.items():setattr(s,k,v)
            self.assertEqual(t.sizing(s,b,h)['selected_volume'],0)
        t,s,b,h=self.fixture()
        self.assertGreater(t.sizing(s,b,h,entry_context='env_probe')['selected_volume'],1)

    def test_receipt_binds_positive_integer_multi_lot_volume_and_is_immutable(self):
        t,s,b,h=self.fixture()
        from qmt_roll_portfolio_strategy import ProductState
        r=t.sizing(s,b,h);qty=r['selected_volume'];state=ProductState('rb.SHFE')
        s._open_position(state,VT,'long',qty,b,'long_case2',h,{'risk_mode':'regular'},sizing_snapshot=r)
        receipt=state.layers[0].stage068_signal_risk_budget
        self.assertGreater(qty,1);self.assertEqual(receipt.authorized_volume,qty)
        self.assertEqual(receipt.target_risk_amount,5000.)
        self.assertEqual(state.layers[0].volume,qty)
        with self.assertRaises(FrozenInstanceError):receipt.target_risk_amount=99999
        for bad in (0,-1,True,1.5,qty+1):
            empty=ProductState('rb.SHFE')
            s._open_position(empty,VT,'long',bad,b,'long_case2',h,{'risk_mode':'regular'},sizing_snapshot=r)
            self.assertEqual(empty.layers,[])

    def test_old_one_lot_mro_is_rejected_instead_of_silently_capping_new_sizing(self):
        from stage039_risk_budget_candidate import FullMarketNativeRiskBudgetOneLot
        cls=type('BadMixedPolicy',(self.m.FractionalRiskSizingMixin,FullMarketNativeRiskBudgetOneLot),{})
        t,s,b,h=self.fixture();s.__class__=cls
        with self.assertRaises(ValueError):t.sizing(s,b,h)

    def test_open_total_risk_is_inclusive_and_equity_cannot_expand_signal_authorization(self):
        args=dict(direction='long',open_price=110.,stop_price=100.,size=10.,tick=.1,volume=50,
                  receipt=self.receipt(),opening_equity=1000000.)
        r=self.m.assess_fractional_open(**args)
        self.assertTrue(r['allowed']);self.assertEqual(r['total_risk'],5000.);self.assertEqual(r['opening_budget'],5000.)
        self.assertFalse(self.m.assess_fractional_open(**dict(args,open_price=110.01))['allowed'])
        self.assertFalse(self.m.assess_fractional_open(**dict(args,opening_equity=999999.))['allowed'])
        self.assertEqual(self.m.assess_fractional_open(**dict(args,opening_equity=2000000.))['opening_budget'],5000.)
        self.assertTrue(self.m.assess_fractional_open(**dict(args,direction='short',open_price=90.,receipt=self.receipt(direction='short')))['allowed'])

    def test_invalid_or_smaller_order_quantities_and_mutated_stop_fail_closed(self):
        args=dict(direction='long',open_price=110.,stop_price=100.,size=10.,tick=.1,volume=50,
                  receipt=self.receipt(),opening_equity=1000000.)
        for volume in (0,-1,True,1.5,49,51):self.assertFalse(self.m.assess_fractional_open(**dict(args,volume=volume))['allowed'])
        for stop in (float('nan'),99.,110.,111.):self.assertFalse(self.m.assess_fractional_open(**dict(args,stop_price=stop))['allowed'])
        for eq in (0,-1,float('nan'),float('inf')):self.assertFalse(self.m.assess_fractional_open(**dict(args,opening_equity=eq))['allowed'])
        forged=replace(self.receipt(),target_risk_amount=7500.)
        self.assertFalse(self.m.assess_fractional_open(**dict(args,receipt=forged))['allowed'])


if __name__=='__main__':unittest.main()


class RealFractionalFillTests(unittest.TestCase):
    setUp=FractionalRiskTests.setUp
    receipt=FractionalRiskTests.receipt

    def fixture(self,price=110.,quantity=50,direction='long'):
        import test_stage041_open_risk as old
        from analyze_qmt_roll_stage502_confirmed_daily_next_real_open_replay import ConfirmedDailyNextRealOpenEngine
        e,s,vt,b,o,layer=old.RealEngineBudgetTests().fixture(price,direction)
        e.__class__=type('FractionalConfirmedEngine',(self.m.FractionalOpeningRiskMixin,ConfirmedDailyNextRealOpenEngine),{})
        from stage003_candidate import FullMarketNoAIOneLot
        class NativeFillStrategy(self.m.FractionalRiskSizingMixin,FullMarketNoAIOneLot):
            def update_trade(inner,trade):
                # Test-only signal stamping; production FeeStrategy is root070.
                trade.signal_datetime=datetime(2021,12,14)
                trade.trading_date=e.datetime.date()
                return super().update_trade(trade)
        s.__class__=NativeFillStrategy
        e.open_budget_audit=[];e.opening_equity=1000000.;e.open_execution_costs=0.
        o.volume=quantity;layer.volume=quantity
        s.set_target(vt,quantity if direction=='long' else -quantity)
        s.entry_risk_diagnostics[0]['volume']=quantity
        layer.stage068_signal_risk_budget=self.receipt(contract_vt_symbol=vt,product_vt_symbol='IC.CFFEX',direction=direction,
            signal=layer.signal,signal_datetime='2021-12-14T00:00:00',authorized_volume=quantity)
        return e,s,vt,b,o,layer

    def test_real_multi_lot_fill_binds_total_risk_and_original_receipt(self):
        for direction,price in [('long',110.),('short',90.)]:
            e,s,vt,b,o,layer=self.fixture(price,direction=direction)
            e.cross_delayed_orders()
            self.assertEqual(s.get_pos(vt),50 if direction=='long' else -50)
            trade=next(iter(e.trades.values()))
            self.assertEqual(trade.volume,50);self.assertEqual(trade.stage068_entry_risk,5000.)
            self.assertEqual(trade.stage068_risk_per_contract,100.)
            self.assertEqual(trade.stage068_budget,5000.)
            self.assertEqual(trade.stage068_signal_snapshot['authorized_volume'],50)

    def test_real_gap_entire_order_rejected_and_intent_cleared_without_resubmission(self):
        e,s,vt,b,o,layer=self.fixture(110.01)
        e.cross_delayed_orders()
        self.assertFalse(e.trades);self.assertEqual(s.get_target(vt),0)
        self.assertEqual(s.states['IC.CFFEX'].layers,[]);self.assertFalse(s.pending_active_products)
        self.assertFalse(s.pending_entry_diagnostics)
        self.assertFalse(e.open_budget_audit[-1]['filled'])
        self.assertNotIn(o.vt_orderid,e.active_limit_orders)

    def test_real_smaller_unbound_and_equity_drop_orders_cannot_fill(self):
        for mutation in ('smaller','missing','equity','stop'):
            e,s,vt,b,o,layer=self.fixture()
            if mutation=='smaller':o.volume=49
            elif mutation=='missing':del layer.stage068_signal_risk_budget
            elif mutation=='equity':e.opening_equity=999999.
            else:layer.stop_price=99.
            e.cross_delayed_orders();self.assertFalse(e.trades);self.assertEqual(s.get_target(vt),0)

    def test_malformed_nonfinite_receipt_rejects_without_audit_serialization_crash(self):
        e,s,vt,b,o,layer=self.fixture()
        layer.stage068_signal_risk_budget=replace(layer.stage068_signal_risk_budget,target_risk_amount=float('nan'))
        e.cross_delayed_orders()
        self.assertFalse(e.trades);self.assertEqual(s.get_target(vt),0)

    def test_reissued_order_keeps_original_signal_authority(self):
        e,s,vt,b,o,layer=self.fixture()
        o.datetime=datetime(2021,12,15)
        e.cross_delayed_orders()
        trade=next(iter(e.trades.values()))
        self.assertEqual(trade.stage068_signal_snapshot['signal_datetime'],'2021-12-14T00:00:00')
