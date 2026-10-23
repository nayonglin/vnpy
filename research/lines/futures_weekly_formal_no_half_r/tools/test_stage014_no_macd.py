"""Synthetic MACD ablation tests; no private data or financial replay."""
from datetime import datetime,timedelta
import unittest
import numpy as np
import pandas as pd
import talib
from test_stage008_three_ma import Harness,ControlledMacdHarness,bar
from stage008_three_ma import three_ma_weekly_strategy_class
try:
    from stage014_no_macd import no_macd_weekly_strategy_class
except ImportError:
    no_macd_weekly_strategy_class=None

class MacdCrossHarness(Harness):
    def _calculate_macd(self,close):
        dif=pd.Series(np.r_[np.full(len(close)-1,-1.),1.]);dea=pd.Series(np.zeros(len(close)))
        return dif,dea,2*(dif-dea)

class NoMacdTests(unittest.TestCase):
    def strategy(self,base=ControlledMacdHarness):
        self.assertTrue(callable(no_macd_weekly_strategy_class),'MACD-off implementation missing')
        return no_macd_weekly_strategy_class(base,{})()
    def fill(self,s,close,fresh=True):
        am=s.ams['X.TEST']
        for i,v in enumerate(close):am.inner.update_bar(bar((datetime(2019,1,1)+timedelta(days=i)).isoformat(),v))
        am.fresh=fresh
        return am,s._build_history_df(am)
    def history(self,close):
        x=np.asarray(close,dtype=float)
        return pd.DataFrame(dict(open=x,high=x+2,low=x-2,close=x,volume=np.ones(len(x)),open_interest=np.full(len(x),100.)))
    def test_ma_case2_long_short_no_macd_direction_veto(self):
        for sign in [1,-1]:
            x=np.array([200.]*21+[90.]*19+[200.]);x=x if sign==1 else 400-x
            old=three_ma_weekly_strategy_class(ControlledMacdHarness,{})();old.macd_sign=-sign
            am,h=self.fill(old,x);self.assertEqual(old._generate_signal(am,h)['signal'],'')
            s=self.strategy();s.macd_sign=-sign;am,h=self.fill(s,x)
            self.assertEqual(s._generate_signal(am,h)['signal'],'long_case2' if sign==1 else 'short_case2')
            self.assertEqual(s.research_macd_call_attempts,0)
    def test_ma_case1a_long_short_remain_cross_driven(self):
        for sign in [1,-1]:
            x=np.array([50.]*21+[120.]*15+[110.]*4+[200.]);x=x if sign==1 else 400-x
            s=self.strategy();am,h=self.fill(s,x)
            self.assertEqual(s._generate_signal(am,h)['signal'],'long_case1a' if sign==1 else 'short_case1a')
    def test_macd_only_case3_removed_without_replacement_signal(self):
        x=np.arange(41)+100.
        old=three_ma_weekly_strategy_class(MacdCrossHarness,{})();am,h=self.fill(old,x)
        self.assertEqual(old._generate_signal(am,h)['signal'],'long_case3')
        s=self.strategy(MacdCrossHarness);am,h=self.fill(s,x)
        self.assertEqual(s._generate_signal(am,h)['signal'],'');self.assertEqual(s.research_macd_call_attempts,0)
    def test_fresh_false_and_non_macd_entry_filter_preserved(self):
        s=self.strategy();x=[200.]*21+[90.]*19+[200.];am,h=self.fill(s,x,False)
        self.assertEqual(s._generate_signal(am,h)['signal'],'')
        am.fresh=True;s.filter_allows=False
        self.assertEqual(s._generate_signal(am,h)['signal'],'');self.assertIn(('long_case2',41),s.filter_calls)
    def test_21_ready_41_storage_and_early_rsi_unchanged(self):
        s=self.strategy();x=100+np.sin(np.arange(21))*3+np.arange(21)*.1;am,h=self.fill(s,x)
        self.assertTrue(am.inited);self.assertEqual(am.size,41);self.assertEqual(am.ready_need,21)
        r=s._generate_signal(am,h);self.assertAlmostEqual(r['rsi_value'],float(talib.RSI(x,timeperiod=6)[-1]))
        self.assertEqual(s.research_macd_call_attempts,0)
    def test_shape_rollover_removes_macd_but_keeps_history_direction(self):
        s=self.strategy()
        for direction,close in [('long',np.arange(20)+100.),('short',200.-np.arange(20))]:
            self.assertEqual(s._rollover_shape_continuation_snapshot(direction,self.history(close[:19]))['allowed'],0)
            r=s._rollover_shape_continuation_snapshot(direction,self.history(close))
            self.assertEqual(r['allowed'],1);self.assertEqual(r['required_bar_count'],20);self.assertTrue(np.isnan(r['macd_hist']))
        self.assertEqual(s._rollover_shape_continuation_snapshot('invalid',self.history(close))['allowed'],0)
        s.short_entry_enabled=False;self.assertEqual(s._rollover_shape_continuation_snapshot('short',self.history(close))['allowed'],0)
        self.assertEqual(s.research_macd_call_attempts,0)
    def test_nonshape_rollover_preserves_direction_and_other_filters(self):
        s=self.strategy();h=self.history(np.arange(21)+100.)
        self.assertTrue(s._rollover_reopen_allowed('long',h,dict(bullish_alignment=True,bearish_alignment=False)))
        self.assertFalse(s._rollover_reopen_allowed('short',h,dict(bullish_alignment=True,bearish_alignment=False)))
        s.filter_allows=False
        self.assertFalse(s._rollover_reopen_allowed('long',h,dict(bullish_alignment=True)))
        self.assertEqual(s.research_macd_call_attempts,0)
    def test_any_future_macd_consumer_fails_closed(self):
        s=self.strategy()
        with self.assertRaisesRegex(RuntimeError,'MACD'):s._calculate_macd(pd.Series([1.,2.]))
        self.assertEqual(s.research_macd_call_attempts,1)
    def test_actual_formal_risk_exit_methods_unchanged(self):
        self.assertTrue(callable(no_macd_weekly_strategy_class),'MACD-off implementation missing')
        from analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine import QmtRollPortfolioStrategyStage847C9StopRetry as Base
        New=no_macd_weekly_strategy_class(Base,{})
        for name in ['_process_rsi_partial_exit','_entry_stop_price','_process_layer_stops','_handle_rollover','_directional_30d_risk_boost_snapshot']:
            self.assertIs(getattr(New,name),getattr(Base,name))
        self.assertTrue(New.research_macd_disabled)

if __name__=='__main__':unittest.main()
