"""Historical authorization/identity tests. No financial replay or downloads."""
from types import SimpleNamespace
from datetime import datetime
import unittest
import pandas as pd
try:
    from stage022_historical_safety import historical_strategy_class,clear_unowned_targets,check_epoch_transition,historical_engine_class
except ImportError:
    historical_strategy_class=clear_unowned_targets=check_epoch_transition=historical_engine_class=None

OLD='2014-10-20';NEW='2024-10-21';SYMBOL='CF505.CZCE'
def bar(day,volume=10.,symbol=SYMBOL):
    return SimpleNamespace(datetime=datetime.fromisoformat(day),vt_symbol=symbol,volume=volume)
def state(symbol=SYMBOL,layers=None,direction='long'):
    return SimpleNamespace(contract_vt_symbol=symbol,layers=[] if layers is None else layers,direction=direction)
def engine():
    strategy=SimpleNamespace(states={'CF.CZCE':state()},ams={},positions={},targets={})
    strategy.get_pos=lambda s:strategy.positions.get(s,0)
    strategy.get_target=lambda s:strategy.targets.get(s,0)
    return SimpleNamespace(strategy=strategy,active_limit_orders={},datetime=pd.Timestamp(OLD))
def lookup():return {(SYMBOL,OLD):'CZCE.CF.201505',(SYMBOL,NEW):'CZCE.CF.202505'}

class TargetTests(unittest.TestCase):
    def api(self):self.assertTrue(callable(clear_unowned_targets),'historical safety API missing')
    def fixture(self):
        st=engine().strategy;st.current_bar_date=pd.Timestamp('2015-01-05');st.targets={SYMBOL:3,'OLD.TEST':-4}
        st.states['CF.CZCE']=state(layers=[SimpleNamespace(volume=3)])
        st.set_target=lambda s,v:st.targets.__setitem__(s,v)
        st.target_data=st.targets
        return st
    def test_owned_pending_target_preserved_and_unowned_target_zeroed(self):
        self.api();st=self.fixture();clear_unowned_targets(st)
        self.assertEqual(st.targets,{SYMBOL:3,'OLD.TEST':0})
        self.assertEqual(st.historical_target_cleanup[0]['previous_target'],-4)
        self.assertEqual(st.historical_target_cleanup[0]['actual_position'],0)
    def test_unowned_real_position_only_gets_close_target_not_erased(self):
        self.api();st=self.fixture();st.positions['OLD.TEST']=-2
        clear_unowned_targets(st);self.assertEqual(st.get_pos('OLD.TEST'),-2)
        self.assertEqual(st.get_target('OLD.TEST'),0)
        self.assertEqual(st.historical_target_cleanup[0]['actual_position'],-2)
    def test_invalid_direction_cannot_authorize_target_and_zero_target_has_no_event(self):
        self.api();st=self.fixture();st.states['CF.CZCE'].direction='';st.targets['ZERO.TEST']=0
        clear_unowned_targets(st);self.assertEqual(st.get_target(SYMBOL),0)
        self.assertEqual(len(st.historical_target_cleanup),2)
    def test_rebalance_cleanup_precedes_original_and_original_called_once(self):
        self.api()
        class Base:
            def rebalance_portfolio(self,bars):
                self.calls+=1;self.seen=self.get_target('OLD.TEST');return 'original-result'
        New=historical_strategy_class(Base,'2015-01-01');s=New();s.__dict__.update(self.fixture().__dict__)
        # Bind fixture lambdas to this shared data, not to a mocked production method.
        s.calls=0
        self.assertEqual(s.rebalance_portfolio({}),'original-result');self.assertEqual(s.calls,1);self.assertEqual(s.seen,0)

class StrategyTests(unittest.TestCase):
    def api(self):self.assertTrue(callable(historical_strategy_class),'historical strategy API missing')
    def test_full_2015_readiness_and_parent_on_bars_once_without_2020_duplicates(self):
        self.api()
        class Base:
            def __init__(self):
                self.calls=0;self.ams={'A.TEST':SimpleNamespace(inited=True,fresh=False)};self.daily_mapping={};self.weekly_readiness=[]
            def on_bars(self,bars):
                self.calls+=1;day=next(iter(bars.values())).datetime.strftime('%Y-%m-%d')
                if day>='2020-01-01':self.weekly_readiness.append(dict(date=day))
                return self.calls
        New=historical_strategy_class(Base,'2015-01-01');s=New()
        for i,day in enumerate(['2014-12-31','2015-01-05','2015-01-09','2020-01-03']):
            s.daily_mapping[day]={'A.PRODUCT':'A.TEST'}
            self.assertEqual(s.on_bars({'A.TEST':bar(day,symbol='A.TEST')}),i+1)
        self.assertEqual(s.calls,4);self.assertEqual([r['date'] for r in s.historical_weekly_readiness],['2015-01-05','2015-01-09','2020-01-03'])
        self.assertEqual([r['date'] for r in s.weekly_readiness],['2020-01-03'])
        self.assertEqual(s.historical_weekly_readiness[0]['ready_target_contracts'],1)
        self.assertEqual(s.historical_weekly_readiness[0]['newly_completed_targets'],0)
    def test_empty_bars_do_not_create_fake_account_day(self):
        self.api()
        class Base:
            def on_bars(self,bars):self.calls+=1
        s=historical_strategy_class(Base,'2015-01-01')();s.calls=0;s.on_bars({})
        self.assertEqual(s.calls,1);self.assertEqual(s.historical_weekly_readiness,[])
    def test_real_M_alpha_and_AM_wrapper_are_inherited_once(self):
        self.api()
        from stage018_short_case2 import short_case2_weekly_strategy_class
        from test_stage008_three_ma import Harness
        from weekly_adapter import WeeklyArrayManager
        from vnpy.trader.utility import ArrayManager
        M=short_case2_weekly_strategy_class(Harness,{})
        New=historical_strategy_class(M,'2015-01-01');s=New();am=s.ams['X.TEST']
        self.assertIsInstance(am,WeeklyArrayManager);self.assertIsInstance(am.inner,ArrayManager)
        self.assertEqual(am.size,41);self.assertEqual(am.ready_need,21)
        for name in ['_generate_signal','_build_history_df','_is_simple_ma_trend','_can_open_short_signal','_rollover_shape_continuation_snapshot','_rollover_reopen_allowed','_entry_stop_price','_process_layer_stops','_process_rsi_partial_exit','_calculate_macd']:
            self.assertIs(getattr(New,name),getattr(M,name))
        self.assertTrue(s._can_open_short_signal('short_case2'));self.assertTrue(s.research_macd_disabled)
        self.assertTrue(s.research_short_case2_enabled)
        self.assertTrue(getattr(s,'research_historical_safety_enabled',False),'historical safety marker must be explicit')
        with self.assertRaisesRegex(RuntimeError,'MACD calculation forbidden'):s._calculate_macd(pd.Series([1.,2.]))

class RealAlphaTest(unittest.TestCase):
    def test_poison_MA40_and_forbidden_MACD_not_read_by_historical_M_signal(self):
        self.assertTrue(callable(historical_strategy_class),'historical strategy API missing')
        from stage018_short_case2 import short_case2_weekly_strategy_class
        from test_stage008_three_ma import Harness,bar as indicator_bar
        class Poison:
            def __int__(self):raise AssertionError('MA40 decision read')
            def __index__(self):raise AssertionError('MA40 decision read')
        M=short_case2_weekly_strategy_class(Harness,{})
        s=historical_strategy_class(M,'2015-01-01')();s.ma_extra_long=Poison();am=s.ams['X.TEST']
        for value in [200.]*21+[90.]*19+[200.]:am.inner.update_bar(indicator_bar('2014-01-01',value))
        am.fresh=True
        self.assertEqual(s._generate_signal(am,s._build_history_df(am))['signal'],'long_case2')
        self.assertEqual(s.research_macd_call_attempts,0)

class EpochTests(unittest.TestCase):
    def api(self):self.assertTrue(callable(check_epoch_transition),'epoch guard API missing')
    def seed(self,e):
        self.api();return check_epoch_transition(e,OLD,{SYMBOL:bar(OLD)},lookup())
    def test_flat_epoch_transition_passes_and_does_not_mutate_AM(self):
        e=engine();e.strategy.ams[SYMBOL]=SimpleNamespace(count=35)
        self.seed(e);e.datetime=pd.Timestamp(NEW);check_epoch_transition(e,NEW,{SYMBOL:bar(NEW)},lookup())
        self.assertEqual(len(e.historical_epoch_transitions),1);event=e.historical_epoch_transitions[0]
        self.assertEqual(event['old_epoch'],'CZCE.CF.201505');self.assertEqual(event['new_epoch'],'CZCE.CF.202505')
        self.assertGreater(event['gap_days'],366);self.assertEqual(event['old_week_count'],35)
        self.assertEqual(e.strategy.ams[SYMBOL].count,35)
    def test_old_position_target_order_and_layer_each_reject_before_authorization(self):
        for kind in ['position','target','order','layer']:
            with self.subTest(kind=kind):
                e=engine();self.seed(e);e.datetime=pd.Timestamp(NEW)
                if kind=='position':e.strategy.positions[SYMBOL]=1
                if kind=='target':e.strategy.targets[SYMBOL]=-1
                if kind=='order':e.active_limit_orders={'T1':SimpleNamespace(vt_symbol=SYMBOL,vt_orderid='T1')}
                if kind=='layer':e.strategy.states['CF.CZCE'].layers=[SimpleNamespace(volume=1)]
                with self.assertRaisesRegex(ValueError,'epoch_transition_not_flat'):check_epoch_transition(e,NEW,{SYMBOL:bar(NEW)},lookup())
                self.assertEqual(e.historical_epoch_state[SYMBOL]['epoch'],'CZCE.CF.201505')
                self.assertEqual(e.historical_epoch_transitions,[])
                self.assertEqual(e.strategy.get_pos(SYMBOL),1 if kind=='position' else 0)
                self.assertEqual(e.historical_epoch_failures[-1]['reason'],'epoch_transition_not_flat')
    def test_missing_physical_ledger_for_real_positive_bar_fails(self):
        self.api();e=engine()
        with self.assertRaisesRegex(ValueError,'physical_epoch_missing'):check_epoch_transition(e,OLD,{SYMBOL:bar(OLD)},{})
    def test_zero_volume_bar_without_ledger_cannot_initialize_an_epoch(self):
        self.api();e=engine();check_epoch_transition(e,OLD,{SYMBOL:bar(OLD,0.)},{})
        self.assertEqual(e.historical_epoch_state,{})
    def test_same_epoch_updates_date_without_fake_transition(self):
        e=engine();self.seed(e);day='2014-10-21';ledger={**lookup(),(SYMBOL,day):'CZCE.CF.201505'}
        e.datetime=pd.Timestamp(day);check_epoch_transition(e,day,{SYMBOL:bar(day)},ledger)
        self.assertEqual(e.historical_epoch_state[SYMBOL]['last_real_day'],day);self.assertEqual(e.historical_epoch_transitions,[])
    def test_short_gap_physical_change_rejected_as_AM_would_not_reset(self):
        for gap in [366,367]:
            with self.subTest(gap=gap):
                e=engine();self.seed(e);day=(pd.Timestamp(OLD)+pd.Timedelta(days=gap)).strftime('%Y-%m-%d')
                e.datetime=pd.Timestamp(day);ledger={**lookup(),(SYMBOL,day):'CZCE.CF.NEW'}
                if gap==366:
                    with self.assertRaisesRegex(ValueError,'epoch_gap_not_safely_reset'):check_epoch_transition(e,day,{SYMBOL:bar(day)},ledger)
                else:check_epoch_transition(e,day,{SYMBOL:bar(day)},ledger)
    def test_no_partial_epoch_commit_if_second_bar_has_no_identity(self):
        e=engine();self.seed(e);e.datetime=pd.Timestamp(NEW)
        with self.assertRaisesRegex(ValueError,'physical_epoch_missing'):
            check_epoch_transition(e,NEW,{SYMBOL:bar(NEW),'BAD.TEST':bar(NEW,symbol='BAD.TEST')},lookup())
        self.assertEqual(e.historical_epoch_state[SYMBOL]['epoch'],'CZCE.CF.201505')
        self.assertEqual(e.historical_epoch_transitions,[])
    def test_stale_bar_and_time_reversal_reject(self):
        self.api();e=engine()
        with self.assertRaisesRegex(ValueError,'epoch_bar_day_mismatch'):check_epoch_transition(e,OLD,{SYMBOL:bar('2014-10-19')},lookup())
        self.seed(e);day='2014-10-19';e.datetime=pd.Timestamp(day)
        with self.assertRaisesRegex(ValueError,'epoch_time_reversal'):check_epoch_transition(e,day,{SYMBOL:bar(day)},{(SYMBOL,day):'CZCE.CF.201505'})
    def test_engine_wrapper_guards_before_original_cross_and_preserves_context(self):
        self.api()
        class Base:
            def cross_delayed_orders(self):self.cross_calls+=1;return 'strict-original'
            def _stage827_order_context(self,*args):return 'strict-next-trading-day'
        New=historical_engine_class(Base,lookup());e=New();e.__dict__.update(engine().__dict__);e.cross_calls=0;e.vt_symbols=[SYMBOL]
        e.history_data={(pd.Timestamp(OLD),SYMBOL):bar(OLD),(pd.Timestamp(NEW),SYMBOL):bar(NEW)}
        self.assertIs(New._stage827_order_context,Base._stage827_order_context)
        self.assertEqual(e.cross_delayed_orders(),'strict-original');self.assertEqual(e.cross_calls,1)
        e.datetime=pd.Timestamp(NEW);e.strategy.targets[SYMBOL]=3
        with self.assertRaisesRegex(ValueError,'epoch_transition_not_flat'):e.cross_delayed_orders()
        self.assertEqual(e.cross_calls,1)
        self.assertIn('epoch_transition_not_flat',getattr(e,'intraday_execution_failure',''))

if __name__=='__main__':unittest.main()
