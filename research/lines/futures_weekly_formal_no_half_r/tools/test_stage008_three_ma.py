"""Stage008 synthetic behavior tests; no financial backtest or private data."""
from datetime import datetime, timedelta
from types import SimpleNamespace
import unittest

import numpy as np
import pandas as pd
import talib
from vnpy.trader.utility import ArrayManager
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy
from weekly_adapter import WeeklyArrayManager, completed_weeks, weekly_strategy_class
try:
    from stage008_three_ma import ThreeMaWeeklyArrayManager, three_ma_weekly_strategy_class
except ImportError:
    ThreeMaWeeklyArrayManager = three_ma_weekly_strategy_class = None


def bar(day, close=100., volume=10.):
    return SimpleNamespace(datetime=datetime.fromisoformat(day), open_price=float(close),
        high_price=float(close)+2., low_price=float(close)-2., close_price=float(close),
        volume=float(volume), turnover=1000., open_interest=100.)


class Harness(QmtRollPortfolioStrategy):
    """Keep actual inherited methods while avoiding portfolio/data initialization."""
    def __init__(self):
        self.vt_symbols=['X.TEST']
        self.ams={'X.TEST':ArrayManager(41)}
        self.daily_mapping={}
        self.enable_rsi_filter=False
        self.long_entry_enabled=True
        self.short_entry_enabled=True
        self.filter_allows=True
        self.filter_calls=[]
    def on_bars(self, bars):
        for symbol,b in bars.items():
            self.ams[symbol].update_bar(b)
    def _passes_entry_filters(self, signal, history):
        self.filter_calls.append((signal,len(history)))
        return self.filter_allows


class ControlledMacdHarness(Harness):
    macd_sign=1
    def _calculate_macd(self, close):
        # Positive/negative histogram without a MACD crossover isolates MA cases.
        return (pd.Series(np.full(len(close),2.*self.macd_sign)),
                pd.Series(np.full(len(close),1.*self.macd_sign)),
                pd.Series(np.full(len(close),2.*self.macd_sign)))


class ThreeMaTests(unittest.TestCase):
    def require_api(self):
        self.assertTrue(callable(three_ma_weekly_strategy_class), 'Stage008 implementation missing')
        self.assertTrue(callable(ThreeMaWeeklyArrayManager), 'Stage008 manager missing')
    def strategy(self, base=Harness, weeks=None):
        self.require_api()
        return three_ma_weekly_strategy_class(base, {} if weeks is None else weeks)()
    def fill(self, strategy, close):
        am=strategy.ams['X.TEST']
        for i,value in enumerate(close):
            am.inner.update_bar(bar((datetime(2019,1,1)+timedelta(days=i)).isoformat(),value))
        am.fresh=True
        return am
    def history(self, close):
        close=np.asarray(close,dtype=float)
        return pd.DataFrame(dict(open=close,high=close+2,low=close-2,close=close,
            volume=np.ones(len(close)),open_interest=np.full(len(close),100.)))
    def test_ready_20_21_capacity_41(self):
        self.require_api()
        am=ThreeMaWeeklyArrayManager(ArrayManager(41),{})
        for i in range(20):am.inner.update_bar(bar('2020-01-01',100+i))
        self.assertFalse(am.inited); self.assertEqual(am.size,41); self.assertEqual(am.ready_need,21)
        am.inner.update_bar(bar('2020-01-01',120))
        self.assertTrue(am.inited); self.assertFalse(am.inner.inited)
    def test_wrong_storage_capacity_rejected(self):
        self.require_api()
        with self.assertRaises(ValueError):ThreeMaWeeklyArrayManager(ArrayManager(21),{})
    def test_empty_and_early_history_never_includes_zero_prefix(self):
        strategy=self.strategy();am=strategy.ams['X.TEST']
        self.assertEqual(len(strategy._build_history_df(am)),0)
        self.fill(strategy,np.arange(21)+100.)
        result=strategy._build_history_df(am)
        self.assertEqual(len(result),21);self.assertTrue(result.close.gt(0).all())
        np.testing.assert_array_equal(result.close.to_numpy(),np.arange(21)+100.)
    def test_early_rsi_uses_real_close_even_if_caller_passes_zero_prefix(self):
        strategy=self.strategy();close=100+np.sin(np.arange(21))*3+np.arange(21)*.1
        am=self.fill(strategy,close)
        unsafe=QmtRollPortfolioStrategy._build_history_df(strategy,am)
        got=strategy._generate_signal(am,unsafe)
        expected=float(talib.RSI(close,timeperiod=6)[-1])
        self.assertAlmostEqual(got['rsi_value'],expected,places=12)
        self.assertGreater(abs(float(am.inner.rsi(6))-expected),1e-5)
    def test_at_and_beyond_41_history_macd_rsi_equal_original(self):
        for count in [41,56]:
            strategy=self.strategy();close=100+np.sin(np.arange(count))*.7+np.arange(count)*.2
            am=self.fill(strategy,close)
            new=strategy._build_history_df(am)
            original=QmtRollPortfolioStrategy._build_history_df(strategy,am)
            pd.testing.assert_frame_equal(new,original)
            for a,b in zip(strategy._calculate_macd(new.close),QmtRollPortfolioStrategy._calculate_macd(original.close)):
                np.testing.assert_array_equal(a.to_numpy(),b.to_numpy())
            got=strategy._generate_signal(am,new)
            self.assertEqual(got['rsi_value'],float(am.inner.rsi(6)))
            old=QmtRollPortfolioStrategy._generate_signal(strategy,am,original)
            for key in ['ma_mid_value','ma_mid_prev_value','ma_long_value','ma_long_prev_value','rsi_value']:
                self.assertEqual(got[key],old[key])
    def test_three_ma_long_and_short_ignore_reversed_ma40(self):
        for sign in [1,-1]:
            strategy=self.strategy(ControlledMacdHarness);strategy.macd_sign=sign
            close=np.array([200.]*21+[90.]*19+[200.])
            if sign<0:close=400-close
            am=self.fill(strategy,close);h=strategy._build_history_df(am)
            old=QmtRollPortfolioStrategy._generate_signal(strategy,am,h)
            got=strategy._generate_signal(am,h)
            self.assertEqual(old['signal'],'')
            self.assertEqual(got['signal'],'long_case2' if sign>0 else 'short_case2')
            self.assertTrue(got['bullish_alignment'] if sign>0 else got['bearish_alignment'])
            self.assertAlmostEqual(got['ma_long_prev_value'],float(pd.Series(close).rolling(20).mean().iloc[-2]))
    def test_ma20_ma40_only_cross_does_not_trigger(self):
        strategy=self.strategy(ControlledMacdHarness)
        am=self.fill(strategy,[200.]+[90.]*35+[110.]*5);h=strategy._build_history_df(am)
        self.assertEqual(QmtRollPortfolioStrategy._generate_signal(strategy,am,h)['signal'],'long_case2')
        self.assertEqual(strategy._generate_signal(am,h)['signal'],'')
    def test_original_non_ma_entry_filter_still_blocks(self):
        strategy=self.strategy(ControlledMacdHarness);strategy.filter_allows=False
        am=self.fill(strategy,[200.]*21+[90.]*19+[200.]);h=strategy._build_history_df(am)
        self.assertEqual(strategy._generate_signal(am,h)['signal'],'')
        self.assertEqual(strategy.filter_calls,[('long_case2',41)])
    def test_weekly_signal_not_repeated_on_nonclosing_day(self):
        strategy=self.strategy(ControlledMacdHarness)
        am=self.fill(strategy,[200.]*21+[90.]*19+[200.]);h=strategy._build_history_df(am)
        self.assertEqual(strategy._generate_signal(am,h)['signal'],'long_case2')
        am.fresh=False;got=strategy._generate_signal(am,h)
        self.assertEqual(got['signal'],'');self.assertFalse(got['breakout']);self.assertTrue(got['bullish_alignment'])
    def test_simple_trend_24_25_long_short_and_unsupported(self):
        strategy=self.strategy()
        for direction,close in [('long',np.arange(25)+100.),('short',200.-np.arange(25))]:
            self.assertFalse(strategy._is_simple_ma_trend(self.history(close[:24]),direction,3))
            self.assertTrue(strategy._is_simple_ma_trend(self.history(close),direction,3))
        self.assertFalse(strategy._is_simple_ma_trend(self.history(np.arange(25)+100),'invalid',3))
    def test_directional_risk_30_31_preserves_insufficient_history(self):
        strategy=self.strategy()
        for key,value in dict(enable_directional_30d_risk_boost=True,directional_30d_risk_boost_lookback=30,
            directional_30d_risk_boost_multiplier=1.5,directional_30d_risk_nonconfirmation_multiplier=1.,
            directional_30d_risk_adjust_long_only=False,directional_30d_risk_boost_require_volume_expansion=True,
            directional_30d_volume_recent_days=10,directional_30d_volume_prior_days=10,
            directional_30d_volume_ratio_threshold=3.,enable_directional_30d_low_volume_risk_discount=True,
            directional_30d_low_volume_ratio_threshold=.5,directional_30d_low_volume_risk_multiplier=.5).items():setattr(strategy,key,value)
        h=self.history(np.arange(31)+100.);h.loc[21:,'volume']=100.
        early=strategy._directional_30d_risk_boost_snapshot('long',h.iloc[:30])
        self.assertEqual(early['directional_30d_risk_boost_reason'],'insufficient_history')
        self.assertEqual(early['directional_30d_risk_boost_multiplier'],1.)
        ready=strategy._directional_30d_risk_boost_snapshot('long',h)
        self.assertEqual(ready['directional_30d_risk_boost_reason'],'direction_and_volume_confirmed')
        self.assertEqual(ready['directional_30d_risk_boost_multiplier'],1.5)
    def test_rollover_shape_19_20_long_short(self):
        strategy=self.strategy(ControlledMacdHarness)
        for direction,sign,close in [('long',1,np.arange(20)+100.),('short',-1,200.-np.arange(20))]:
            strategy.macd_sign=sign
            self.assertEqual(strategy._rollover_shape_continuation_snapshot(direction,self.history(close[:19]))['reason'],'insufficient_indicator_history')
            got=strategy._rollover_shape_continuation_snapshot(direction,self.history(close))
            self.assertEqual(got['required_bar_count'],20);self.assertEqual(got['allowed'],1)
        self.assertEqual(strategy._rollover_shape_continuation_snapshot('invalid',self.history(close))['reason'],'unsupported_direction')
    def test_ma40_legacy_value_not_read_by_new_decisions(self):
        strategy=self.strategy(ControlledMacdHarness)
        class Poison:
            def __int__(self):raise AssertionError('legacy MA40 read')
            def __index__(self):raise AssertionError('legacy MA40 read')
        strategy.ma_extra_long=Poison()
        am=self.fill(strategy,[200.]*21+[90.]*19+[200.]);h=strategy._build_history_df(am)
        self.assertEqual(strategy._generate_signal(am,h)['signal'],'long_case2')
        self.assertTrue(strategy._is_simple_ma_trend(self.history(np.arange(25)+100),'long',3))
        self.assertEqual(strategy._rollover_shape_continuation_snapshot('long',self.history(np.arange(20)+100))['allowed'],1)
    def test_unknown_generate_signal_mro_rejected(self):
        self.require_api()
        class Hidden(Harness):
            def _generate_signal(self,*args):return super()._generate_signal(*args)
        with self.assertRaises(ValueError):three_ma_weekly_strategy_class(Hidden,{})
        with self.assertRaises(ValueError):three_ma_weekly_strategy_class(weekly_strategy_class(Harness,{}),{})
    def test_actual_formal_class_accepted_and_exit_methods_preserved(self):
        self.require_api()
        from analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine import QmtRollPortfolioStrategyStage847C9StopRetry as Base
        New=three_ma_weekly_strategy_class(Base,{})
        self.assertIs(New._process_rsi_partial_exit,Base._process_rsi_partial_exit)
        self.assertIs(New._entry_stop_price,Base._entry_stop_price)
        self.assertIs(New._process_layer_stops,Base._process_layer_stops)
    def test_factory_aggregates_once_not_nested(self):
        days=['2020-01-06','2020-01-07','2020-01-08','2020-01-09','2020-01-10']
        strategy=self.strategy(weeks=completed_weeks(days))
        for day in days:strategy.on_bars({'X.TEST':bar(day)})
        am=strategy.ams['X.TEST']
        self.assertEqual(am.count,1);self.assertIsInstance(am.inner,ArrayManager)
        self.assertNotIsInstance(am.inner,WeeklyArrayManager)
        self.assertEqual(am.completed[0]['volume'],50.)
    def test_missing_and_partial_weeks_do_not_increment(self):
        self.require_api();days=['2020-01-06','2020-01-07','2020-01-08','2020-01-09','2020-01-10','2020-01-13']
        am=ThreeMaWeeklyArrayManager(ArrayManager(41),completed_weeks(days))
        for day in [days[0],*days[2:]]:am.update_bar(bar(day))
        self.assertEqual(am.count,0);self.assertFalse(am.inited);self.assertEqual(len(am.rejected),1)
    def test_epoch_reset_discards_old_21_week_ready_state(self):
        self.require_api()
        old=[(datetime(2010,1,8)+timedelta(weeks=i)).strftime('%Y-%m-%d') for i in range(21)]
        new=[(datetime(2020,1,3)+timedelta(weeks=i)).strftime('%Y-%m-%d') for i in range(20)]
        am=ThreeMaWeeklyArrayManager(ArrayManager(41),completed_weeks(old+new))
        for day in old:am.update_bar(bar(day))
        self.assertTrue(am.inited)
        for day in new:am.update_bar(bar(day))
        self.assertEqual(am.count,20);self.assertEqual(am.size,41);self.assertFalse(am.inited)

    def test_formal_core_on_bars_and_rollover_remain_inherited(self):
        self.require_api()
        from unittest.mock import patch
        from analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine import QmtRollPortfolioStrategyStage847C9StopRetry as Base
        New=three_ma_weekly_strategy_class(Base,{})
        self.assertIs(Base.on_bars,QmtRollPortfolioStrategy.on_bars)
        self.assertIs(New._handle_rollover,Base._handle_rollover)
        self.assertIs(New._handle_rollover,QmtRollPortfolioStrategy._handle_rollover)
        obj=New.__new__(New);obj.daily_mapping={};obj.weekly_readiness=[]
        bars={'X.TEST':bar('2020-01-10')}
        sentinel=object()
        with patch.object(Base,'on_bars',autospec=True,return_value=sentinel) as original:
            self.assertIs(obj.on_bars(bars),sentinel)
            original.assert_called_once_with(obj,bars)
    def test_original_on_bars_calls_rollover_when_target_has_only_20_weeks(self):
        strategy=self.strategy(ControlledMacdHarness)
        day='2020-05-22';target='NEW.TEST';old='OLD.TEST'
        am=ThreeMaWeeklyArrayManager(ArrayManager(41),completed_weeks([day]))
        for i in range(19):am.inner.update_bar(bar('2020-01-01',100+i))
        strategy.ams={target:am};strategy.product_symbols=['X.TEST']
        state=SimpleNamespace(contract_vt_symbol=old,rollover_pending_target_contract='')
        strategy.states={'X.TEST':state};strategy.daily_mapping={day:{'X.TEST':target}}
        bars={target:bar(day,119),old:bar(day,100)};events=[]
        strategy._reset_intrabar_reservations=lambda:None
        strategy._refresh_risk_state=lambda bars:None
        strategy._resolve_actual_position=lambda state,target,bars:(old,1,bars[old])
        strategy._rollover_delay_applies=lambda state,target,pos:False
        strategy._reconcile_state_with_position=lambda state,pos,b:None
        strategy._handle_rollover=lambda state,target,bars:events.append((
            am.count,am.inited,strategy._rollover_shape_continuation_snapshot('long',strategy._build_history_df(am))['allowed']))
        strategy._build_daily_env_gate_snapshot=lambda contexts:{}
        strategy._entry_allowed_today=lambda day:False
        strategy.rebalance_portfolio=lambda bars:None
        strategy.forced_margin_deleverage_count=0
        strategy._process_forced_margin_deleverage=lambda bars:None
        strategy._record_portfolio_volatility_budget_daily_return=lambda:None
        strategy._record_portfolio_overheat_cooldown_daily_equity=lambda:None
        strategy.estimated_equity=150000.;strategy.pos_data={old:1};strategy.last_close_prices={}
        strategy._count_active_positions=lambda:1;strategy.put_event=lambda:None
        QmtRollPortfolioStrategy.on_bars(strategy,bars)
        self.assertEqual(events,[(20,False,1)])

if __name__=='__main__':unittest.main()
