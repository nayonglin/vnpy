"""New weekly policy exercised through real native sizing and real next-open fills."""
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
import json,unittest
from types import SimpleNamespace
import pandas as pd
try:
    from stage051_weekly_long_candidate import WeeklyLongEntryMixin,WeeklyLongExecutionMixin,WeeklyEntryAuthorization
except ModuleNotFoundError as exc:
    if exc.name!='stage051_weekly_long_candidate':raise
    class WeeklyLongEntryMixin:pass
    class WeeklyLongExecutionMixin:pass
    WeeklyEntryAuthorization=None


def snapshot(product,asof,phase,allowed=True):
    return dict(product_vt_symbol=product,asof_date=str(pd.Timestamp(asof).date()),phase=phase,
                week_last_session='2019-12-27' if pd.Timestamp(asof).year<2021 else '2021-12-10',
                ma5=104. if allowed else 100.,ma10=103.,ma20=102.,ma40=101.,
                history_weeks=45,valid_weeks=40,allowed=allowed,reason='bullish' if allowed else 'not_bullish',evidence_id='known-weekly-evidence')

class Provider:
    def __init__(self,allowed=True,poison=False):self.allowed=allowed;self.poison=poison
    def lookup(self,product,asof,phase='signal_close'):
        if self.poison:raise AssertionError('weekly lookup touched a short/close/env-probe')
        return snapshot(product,asof,phase,self.allowed)

class NativeWeeklyTests(unittest.TestCase):
    def fixture(self,bullish=True,poison=False,**kw):
        import test_stage039_risk_budget_candidate as old
        import stage039_risk_budget_candidate as module
        cls=type('WithWeekly',(WeeklyLongEntryMixin,module.FullMarketNativeRiskBudgetOneLot),{})
        t=old.RiskBudgetCandidateTest();t.setUp()
        with patch.object(module,'FullMarketNativeRiskBudgetOneLot',cls):s,b,h=t.fixture(**kw)
        s.strategy_engine.weekly_main=Provider(bullish,poison)
        return t,s,b,h
    def test_native_flat_reverse_and_rollover_long_all_require_weekly_bull(self):
        for context in ('flat_entry','reverse_entry','rollover_reopen'):
            t,s,b,h=self.fixture(False);result=t.sizing(s,b,h,entry_context=context)
            self.assertEqual(result['selected_volume'],0,context)
    def test_weekly_bull_does_not_revive_native_risk_rejection(self):
        t,s,b,h=self.fixture(True,min_risk_per_trade=19.99,max_risk_per_trade=19.99)
        self.assertEqual(t.sizing(s,b,h)['selected_volume'],0)
    def test_short_native_sizing_and_env_probe_are_exactly_unchanged(self):
        from stage039_risk_budget_candidate import FullMarketNativeRiskBudgetOneLot as Base
        from stage040_run import safe
        for direction,context in [('short','flat_entry'),('long','env_probe'),('short','env_probe')]:
            t,s,b,h=self.fixture(False,True)
            native=Base._calculate_entry_sizing(s,'rb202005.SHFE',direction,b,h,{'signal':direction+'_case2','risk_mode':'regular'},entry_context=context)
            candidate=t.sizing(s,b,h,direction,entry_context=context)
            self.assertEqual(json.dumps(safe(native),sort_keys=True),json.dumps(safe(candidate),sort_keys=True))
    def test_bullish_long_still_gets_original_budget_and_week_receipt(self):
        t,s,b,h=self.fixture(True);size=t.sizing(s,b,h)
        from qmt_roll_portfolio_strategy import ProductState
        state=ProductState('rb.SHFE')
        s._open_position(state,'rb202005.SHFE','long',1,b,'long_case2',h,{'risk_mode':'regular'},sizing_snapshot=size)
        self.assertEqual(len(state.layers),1)
        self.assertTrue(hasattr(state.layers[0],'stage039_signal_risk_budget'))
        self.assertTrue(hasattr(state.layers[0],'stage051_weekly_authorization'))
    def test_open_position_does_not_accept_forged_native_size_when_week_bearish(self):
        t,s,b,h=self.fixture(True);size=t.sizing(s,b,h)
        from qmt_roll_portfolio_strategy import ProductState;s.strategy_engine.weekly_main=Provider(False)
        state=ProductState('rb.SHFE');s._open_position(state,'rb202005.SHFE','long',1,b,'long_case2',h,{'risk_mode':'regular'},sizing_snapshot=size)
        self.assertEqual(state.layers,[])
    def test_missing_weekly_provider_fails_closed_only_for_longs(self):
        t,s,b,h=self.fixture(True);del s.strategy_engine.weekly_main
        self.assertEqual(t.sizing(s,b,h,'long')['selected_volume'],0)
        self.assertEqual(t.sizing(s,b,h,'short')['selected_volume'],1)

class RealWeeklyFillTests(unittest.TestCase):
    def fixture(self,allowed=True,direction='long'):
        import test_stage041_open_risk as old
        e,s,vt,b,o,layer=old.RealEngineBudgetTests().fixture(110. if direction=='long' else 90.,direction)
        e.__class__=type('WeeklyEngine',(WeeklyLongExecutionMixin,e.__class__),{})
        e.weekly_execution_audit=[];e.weekly_main=Provider(allowed,direction=='short')
        if direction=='long' and WeeklyEntryAuthorization is not None:
            layer.stage051_weekly_authorization=WeeklyEntryAuthorization(vt,'IC.CFFEX','long',layer.signal,'2021-12-14',json.dumps(snapshot('IC.CFFEX','2021-12-14','signal_close'),sort_keys=True))
        return e,s,vt,b,o,layer
    def test_real_long_fill_requires_weekly_rule_and_cleans_rejected_intent(self):
        e,s,vt,b,o,layer=self.fixture(False);e.cross_delayed_orders()
        self.assertFalse(e.trades);self.assertEqual(s.get_target(vt),0)
        self.assertEqual(s.states['IC.CFFEX'].layers,[]);self.assertFalse(s.pending_active_products)
    def test_real_long_fill_has_original_risk_budget_plus_weekly_receipt(self):
        e,s,vt,b,o,layer=self.fixture(True);e.cross_delayed_orders()
        self.assertEqual(s.get_pos(vt),1);t=next(iter(e.trades.values()))
        self.assertEqual(t.stage041_entry_risk,100)
        self.assertTrue(hasattr(t,'stage051_weekly_open_snapshot'))
    def test_short_open_is_untouched_even_with_unusable_weekly_provider(self):
        e,s,vt,b,o,layer=self.fixture(False,'short');e.cross_delayed_orders()
        self.assertEqual(s.get_pos(vt),-1)
    def test_buy_to_close_a_short_never_checks_weekly_condition(self):
        from vnpy.trader.constant import Offset
        e,s,vt,b,o,layer=self.fixture(False,'short');e.cross_delayed_orders()
        o.offset=Offset.CLOSE;o.direction=__import__('vnpy.trader.constant',fromlist=['Direction']).Direction.LONG
        o.orderid='close2';e.active_limit_orders={o.vt_orderid:o};e.limit_orders[o.vt_orderid]=o
        e.cross_delayed_orders();self.assertEqual(s.get_pos(vt),0)
    def test_old_signal_not_replaced_by_reissue_and_new_bear_week_blocks(self):
        e,s,vt,b,o,layer=self.fixture(False);o.datetime=datetime(2021,12,15)
        e.cross_delayed_orders();self.assertFalse(e.trades)
    def test_missing_signal_weekly_receipt_never_bypasses_fill_gate(self):
        e,s,vt,b,o,layer=self.fixture(True)
        if hasattr(layer,'stage051_weekly_authorization'):del layer.stage051_weekly_authorization
        e.cross_delayed_orders();self.assertFalse(e.trades)

if __name__=='__main__':unittest.main()
