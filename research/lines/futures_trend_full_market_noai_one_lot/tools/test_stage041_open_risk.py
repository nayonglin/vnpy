"""Behavioral regressions for next-open budget enforcement; no market replay."""
from types import SimpleNamespace as NS
import unittest
from stage041_open_risk import assess_open_risk, opening_budget

class OpenRiskTests(unittest.TestCase):
    def snapshot(self,**kwargs):
        return dict(target_risk_amount=100.,risk_ratio=.1,risk_multiplier=1.,portfolio_overheat_cooldown_scale=1.,
          directional_30d_risk_boost_multiplier=1.,min_risk_per_trade=0.,max_risk_per_trade=1000.,
          effective_capital_usage_ratio=1.,sizing_equity=1000.,**kwargs)
    def assess(self,price=110.,stop=100.,direction='long',budget=None,**kwargs):
        return assess_open_risk(direction=direction,open_price=price,stop_price=stop,size=10.,tick=.1,
            snapshot=self.snapshot() if budget is None else budget,opening_equity=1000.,reserved_margin=0.,**kwargs)
    def test_inclusive_boundary_and_next_open_gap(self):
        self.assertTrue(self.assess()['allowed'])
        self.assertFalse(self.assess(price=110.01)['allowed'])
    def test_short_gap_and_invalid_stop_direction(self):
        self.assertTrue(self.assess(price=90.,direction='short')['allowed'])
        self.assertFalse(self.assess(price=89.99,direction='short')['allowed'])
        self.assertFalse(self.assess(price=99.)['allowed'])
        self.assertFalse(self.assess(price=101.,direction='short')['allowed'])
    def test_invalid_or_unknown_budget_is_not_one_lot(self):
        for snapshot in ({},dict(self.snapshot(),target_risk_amount=float('nan')),dict(self.snapshot(),target_risk_amount=0)):
            self.assertFalse(self.assess(budget=snapshot)['allowed'])
    def test_minimum_tick_risk_still_consumes_budget(self):
        self.assertFalse(self.assess(price=100.01,budget=dict(self.snapshot(),target_risk_amount=.5))['allowed'])
    def test_opening_budget_shrinks_without_expanding_signal_authorization(self):
        s=self.snapshot()
        self.assertEqual(opening_budget(s,opening_equity=2000,reserved_margin=0),100)
        self.assertEqual(opening_budget(s,opening_equity=800,reserved_margin=300),50)
        self.assertFalse(assess_open_risk(direction='long',open_price=110,stop_price=100,size=10,tick=.1,
            snapshot=s,opening_equity=800,reserved_margin=300)['allowed'])
    def test_native_currency_floor_and_factor_order_preserved(self):
        s=dict(self.snapshot(),min_risk_per_trade=50,max_risk_per_trade=70,risk_multiplier=.5,portfolio_overheat_cooldown_scale=.8,directional_30d_risk_boost_multiplier=1.2)
        self.assertAlmostEqual(opening_budget(s,opening_equity=300,reserved_margin=0),24)
        self.assertAlmostEqual(opening_budget(s,opening_equity=1000,reserved_margin=0),33.6)
    def test_no_positive_equity_never_opens_despite_currency_floor(self):
        self.assertFalse(assess_open_risk(direction='long',open_price=110,stop_price=100,size=10,tick=.1,
            snapshot=dict(self.snapshot(),min_risk_per_trade=500),opening_equity=0,reserved_margin=0)['allowed'])
    def test_nonfinite_prices_and_margin_fail_closed(self):
        self.assertFalse(self.assess(price=float('nan'))['allowed'])
        self.assertEqual(opening_budget(self.snapshot(),opening_equity=1000,reserved_margin=float('nan')),0)



class RealEngineBudgetTests(unittest.TestCase):
    def fixture(self,price=110,direction='long'):
        import test_stage017_lifecycle_regressions as old
        from unittest.mock import patch
        from stage040_run import FullMarketDailyEngine,FeeStrategy
        from vnpy.trader.object import OrderData
        from vnpy.trader.constant import Direction,Offset,Exchange,Status
        from datetime import datetime
        with patch.object(old,'FullMarketDailyEngine',FullMarketDailyEngine),patch.object(old,'FullMarketNoAIOneLot',FeeStrategy):
            e,s,vt,b=old.LifecycleRegressions().held_index_fixture()
        s.pos_data[vt]=0;s.equity_start_positions={};s.total_margin_in_use=0
        s.pending_active_products={'IC.CFFEX'};s.fixed_size=0;s.max_position_size=1
        s.pending_entry_diagnostics={(vt,direction):[0]};s.entry_risk_diagnostics=[dict(datetime='2021-12-14',volume=1,size=10,margin_ratio=.1,stop_price=100,total_margin_in_use_before=0)]
        layer=s.states['IC.CFFEX'].layers[0];s.states['IC.CFFEX'].direction=direction
        layer.direction=direction;layer.entry_price_synced=False;layer.entry_date='2021-12-14';layer.stop_price=100
        layer.stage039_signal_risk_budget=dict(OpenRiskTests().snapshot(),contract_vt_symbol=vt,product_vt_symbol='IC.CFFEX',signal=layer.signal,direction=direction,signal_datetime='2021-12-14',snapshot_id='original-signal')
        e.research_metadata[vt]['pricetick']=.1;b.open_price=price;b.close_price=999
        e.priceticks[vt]=.1
        o=OrderData(symbol='IC202112',exchange=Exchange.CFFEX,orderid='1',direction=Direction.LONG if direction=='long' else Direction.SHORT,
            offset=Offset.OPEN,volume=1,price=price,status=Status.SUBMITTING,datetime=datetime(2021,12,14),gateway_name='BACKTESTING')
        e.limit_orders={o.vt_orderid:o};e.active_limit_orders={o.vt_orderid:o};s.active_orderids.add(o.vt_orderid)
        e.prepare_opening_risk(e.datetime)
        return e,s,vt,b,o,layer
    def test_actual_gap_rejects_and_cleans_unfilled_state(self):
        e,s,vt,b,o,layer=self.fixture(110.01)
        e.cross_delayed_orders()
        self.assertFalse(e.trades);self.assertEqual(s.get_pos(vt),0);self.assertEqual(s.get_target(vt),0)
        self.assertNotIn(o.vt_orderid,e.active_limit_orders);self.assertFalse(s.pending_active_products)
        self.assertEqual(s.states['IC.CFFEX'].layers,[]);self.assertFalse(s.pending_entry_diagnostics)
        self.assertIn('exceeds_native',e.open_budget_audit[-1]['reason'])
    def test_actual_boundary_fill_uses_open_not_future_close(self):
        e,s,vt,b,o,layer=self.fixture()
        e.cross_delayed_orders()
        self.assertEqual(s.get_pos(vt),1);self.assertEqual(len(e.trades),1)
        trade=next(iter(e.trades.values()))
        self.assertEqual(trade.price,110);self.assertEqual(trade.stage041_entry_risk,100)
        self.assertEqual(trade.stage041_budget,100);self.assertTrue(e.open_budget_audit[-1]['filled'])
    def test_actual_short_boundary_and_gap(self):
        for price,expected in [(90,-1),(89.99,0)]:
            e,s,vt,b,o,layer=self.fixture(price,'short');e.cross_delayed_orders()
            self.assertEqual(s.get_pos(vt),expected)
    def test_reissued_order_does_not_replace_original_signal_budget(self):
        from datetime import datetime
        e,s,vt,b,o,layer=self.fixture(110.01)
        o.datetime=datetime(2021,12,15)
        e.cross_delayed_orders();self.assertFalse(e.trades)
        import json
        self.assertEqual(json.loads(e.open_budget_audit[-1]['signal_snapshot'])['snapshot_id'],'original-signal')
    def test_missing_bound_snapshot_fails_closed(self):
        e,s,vt,b,o,layer=self.fixture();del layer.stage039_signal_risk_budget
        e.cross_delayed_orders();self.assertFalse(e.trades);self.assertEqual(s.get_target(vt),0)
    def test_ambiguous_unfilled_layers_do_not_leave_ghost_margin_intents(self):
        from copy import copy
        e,s,vt,b,o,layer=self.fixture();s.states['IC.CFFEX'].layers.append(copy(layer))
        e.cross_delayed_orders();self.assertFalse(e.trades)
        self.assertEqual(s.states['IC.CFFEX'].layers,[]);self.assertFalse(s.pending_active_products)
    def test_mismatched_budget_identity_rejects(self):
        e,s,vt,b,o,layer=self.fixture();layer.stage039_signal_risk_budget['contract_vt_symbol']='OTHER'
        e.cross_delayed_orders();self.assertFalse(e.trades)
        self.assertEqual(e.open_budget_audit[-1]['reason'],'unbound_signal_risk_budget')
    def test_reject_helper_preserves_actual_position_and_synced_layer(self):
        e,s,vt,b,o,layer=self.fixture();layer.entry_price_synced=True;s.pos_data[vt]=1
        e._cancel_budget_open(o,None,'synthetic_stale_order')
        self.assertEqual(s.get_pos(vt),1);self.assertEqual(s.get_target(vt),1)
        self.assertIs(s.states['IC.CFFEX'].layers[0],layer)

if __name__=='__main__':unittest.main()
