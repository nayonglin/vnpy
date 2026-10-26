"""Hand-computed Stage030 contracts, with actual inherited layer bookkeeping."""
from copy import deepcopy
from datetime import datetime, timedelta
from types import SimpleNamespace
import unittest
import pandas as pd
from vnpy.trader.setting import SETTINGS
SETTINGS.update({'log.active':False,'log.file':False,'log.console':False})
from vnpy.trader.constant import Direction, Offset
from vnpy.trader.object import TradeData
from qmt_roll_portfolio_strategy import ProductState
from test_stage029_week_close_exits import Harness as ParentHarness, bar, SYMBOL, OTHER
from stage029_week_close_exits_v2 import week_close_exit_strategy_class
try:
    from stage030_profit5_half import profit_half_strategy_class, audit_profit_half
except ImportError:
    # The initial RED exercises the actual frozen behavior, not a missing import.
    def profit_half_strategy_class(base,weeks,frequency,enabled=True):
        return week_close_exit_strategy_class(base,weeks)
    audit_profit_half=None

class Harness(ParentHarness):
    def __init__(self):
        super().__init__()
        self.positions={}; self.enable_ma_trend_stop=False; self.ma_long=20
        self.strategy_engine=SimpleNamespace(bars={},active_limit_orders={})
        self.trade_event_diagnostics=[]
    def get_pos(self,symbol): return self.positions.get(symbol,0)
    def get_target(self,symbol): return self.targets.get(symbol,0)

class ProfitHalfTests(unittest.TestCase):
    def strategy(self,frequency='daily',enabled=True,base=Harness):
        return profit_half_strategy_class(base,{},frequency,enabled)()
    def accepted(self,s,day='2026-01-02',close=100.,symbol=SYMBOL):
        b=bar(day,close,max(130.,close),min(80.,close),symbol)
        s.ams[symbol].weeks[tuple(b.datetime.date().isocalendar()[:2])]=(day,)
        s.ams[symbol].update_bar(b);s.current_bar_date=pd.Timestamp(day)
        return b
    def opening(self,s,direction='long',volume=4,cost=100.,symbol=SYMBOL,day='2026-01-05',state=None):
        if not s.ams[symbol].completed:self.accepted(s,symbol=symbol)
        st=state or ProductState('rb.SHFE');b=bar(day,100.,110.,90.,symbol)
        s.current_bar_date=pd.Timestamp(day)
        # The actual parent open creates the native-contract episode; fill sync is explicit.
        stop=s._entry_stop_price(direction,b,s._build_history_df(s.ams[symbol]),True)
        s._open_position(st,symbol,direction,volume,b,'long_case2' if direction=='long' else 'short_case1a',
            s._build_history_df(s.ams[symbol]),{},sizing_snapshot={'stop_price':stop})
        for layer in st.layers:layer.entry_price=cost;layer.entry_price_synced=True
        s.positions[symbol]=volume if direction=='long' else -volume
        s.states[st.product_vt_symbol]=st
        return st
    def decision(self,s,st,close=106.,day='2026-01-07',high=None):
        b=bar(day,close,high or max(130.,close),min(80.,close),st.contract_vt_symbol)
        s.current_bar_date=pd.Timestamp(day)
        return s._process_rsi_partial_exit(st,b,100.)
    def fill_frames(self,s,day='2026-01-08',price=104.):
        return {'trades':pd.DataFrame([dict(order_id='T1',vt_symbol=SYMBOL,direction='short',offset='Close',volume=2,price=price,trading_date=day)]),
            'execution_anchor_requests':pd.DataFrame([dict(order_id='T1',vt_symbol=SYMBOL,offset='Close',signal_date='2026-01-07',trading_date=day,daily_open=price,price=price,source='declared_daily_bar_open_model',execution_model='declared_daily_bar_open_model',daily_bar_present=True,daily_volume=10.)]),
            'trade_events':pd.DataFrame([dict(date='2026-01-07',vt_symbol=SYMBOL,reason='long_profit5_half',volume=2,price=106.,direction='short',offset='Close')])}
    def test_long_daily_close_strictly_above_five_reduces_four_to_two(self):
        s=self.strategy();st=self.opening(s)
        self.assertEqual(self.decision(s,st),'long_profit5_half')
        self.assertEqual(st.active_volume(),2);self.assertEqual(s.targets[SYMBOL],2)
        self.assertEqual(s.events[-1]['volume'],2);self.assertEqual(s.events[-1]['price'],106.)
        self.assertEqual(s.execution_price_overrides,{})
        before=(deepcopy(s.targets),st.active_volume(),deepcopy(s.execution_price_overrides))
        s._apply_state_target(st)  # The inherited caller repeats the same target assignment.
        self.assertEqual((s.targets,st.active_volume(),s.execution_price_overrides),before)
    def test_short_strict_boundary_and_high_does_not_substitute_close(self):
        for direction,close,want in [('long',105.,4),('long',104.,4),('long',105.00001,2),
                                     ('short',95.,4),('short',96.,4),('short',94.99999,2)]:
            with self.subTest(direction=direction,close=close):
                s=self.strategy();st=self.opening(s,direction=direction)
                self.decision(s,st,close,high=200.)
                self.assertEqual(st.active_volume(),want)
    def test_weighted_actual_fill_cost_replaces_planned_close(self):
        s=self.strategy();st=self.opening(s,cost=110.)
        self.assertEqual(self.decision(s,st,106.),'');self.assertEqual(st.active_volume(),4)
        self.assertEqual(self.decision(s,st,116.),'long_profit5_half')
        self.assertAlmostEqual(s.profit_half_triggers[-1]['cost'],110.)
    def test_odd_lot_floor_one_lot_remains_eligible_and_no_rsi_done(self):
        for volume,want in [(1,1),(2,1),(3,2),(5,3)]:
            with self.subTest(volume=volume):
                s=self.strategy();st=self.opening(s,volume=volume)
                self.decision(s,st);self.assertEqual(st.active_volume(),want)
                self.assertFalse(st.rsi_partial_exit_done)
                self.assertEqual(len(s.profit_half_triggers),0 if volume==1 else 1)
    def test_episode_is_once_and_preserves_remainder_stop_cost_extrema(self):
        s=self.strategy();st=self.opening(s);before=deepcopy(st.layers[0])
        self.decision(s,st);s.positions[SYMBOL]=2
        self.assertEqual(self.decision(s,st,120.,'2026-01-08'),'')
        layer=st.layers[0]
        for key in ['entry_price','stop_price','highest_price','lowest_price','entry_price_synced']:
            self.assertEqual(getattr(layer,key),getattr(before,key))
        self.assertEqual(len(s.profit_half_triggers),1)
        self.assertEqual(s.profit_half_decisions[-1]['action'],'already_done')
    def test_close_reopen_and_rollover_get_distinct_monotonic_episodes(self):
        s=self.strategy();st=self.opening(s);self.decision(s,st)
        first=s.profit_half_triggers[-1]['episode_id'];st.reset();s.positions[SYMBOL]=0
        st=self.opening(s,state=st,day='2026-01-08');self.decision(s,st,106.,'2026-01-09')
        second=s.profit_half_triggers[-1]['episode_id']
        st.reset();s.positions[SYMBOL]=0
        st=self.opening(s,symbol=OTHER,state=st,day='2026-01-12');self.decision(s,st,106.,'2026-01-13')
        third=s.profit_half_triggers[-1]['episode_id']
        self.assertTrue(first<second<third);self.assertEqual(len(s.profit_half_triggers),3)
    def test_weekly_only_fresh_completed_week_close_and_not_daily_high(self):
        s=self.strategy('weekly');st=self.opening(s)
        self.assertEqual(self.decision(s,st,110.),'');self.assertEqual(st.active_volume(),4)
        self.accepted(s,'2026-01-09',104.)
        self.assertEqual(self.decision(s,st,104.,'2026-01-09',high=200.),'')
        self.accepted(s,'2026-01-16',106.)
        self.assertEqual(self.decision(s,st,106.,'2026-01-16'),'long_profit5_half')
        self.assertEqual(s.profit_half_triggers[-1]['week_end'],'2026-01-16')
    def test_disabled_matches_frozen_parent_and_records_no_new_decision(self):
        for factory in [lambda:self.strategy(enabled=False),lambda:week_close_exit_strategy_class(Harness,{})()]:
            s=factory();st=self.opening(s)
            self.assertEqual(self.decision(s,st),'');self.assertEqual(st.active_volume(),4)
            self.assertEqual(s.events,[]);self.assertEqual(s.targets,{})
        s=self.strategy(enabled=False);self.assertEqual(s.profit_half_decisions,[])
    def test_corrupt_actual_basis_and_episode_fail_closed(self):
        mutations=[lambda s,st:setattr(st.layers[0],'entry_price_synced',False),
                   lambda s,st:setattr(st.layers[0],'entry_price',float('nan')),
                   lambda s,st:s.positions.update({SYMBOL:3}),
                   lambda s,st:setattr(st,'direction','unknown'),
                   lambda s,st:setattr(st,'entry_date','2026-01-06')]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                s=self.strategy();st=self.opening(s);mutate(s,st)
                with self.assertRaises(ValueError):self.decision(s,st)
                self.assertEqual(s.targets,{});self.assertEqual(len(s.profit_half_guard_failures),1)
    def test_wrong_contract_nonpositive_close_missing_epoch_and_stale_day_fail(self):
        for kind in ['symbol','close','epoch','day']:
            with self.subTest(kind=kind):
                s=self.strategy();st=self.opening(s);b=bar('2026-01-07',106.)
                s.current_bar_date=pd.Timestamp('2026-01-07')
                if kind=='symbol':b=bar('2026-01-07',106.,symbol=OTHER)
                if kind=='close':b.close_price=0.
                if kind=='epoch':s.ams[SYMBOL].inner.count=0
                if kind=='day':s.current_bar_date=pd.Timestamp('2026-01-08')
                with self.assertRaises(ValueError):s._process_rsi_partial_exit(st,b,100.)
                self.assertEqual(s.targets,{})
    def test_ma20_prior_full_stop_defers_without_generate_signal_side_effect(self):
        for direction,last in [('long',106.),('short',94.)]:
            with self.subTest(direction=direction):
                s=self.strategy();st=self.opening(s,direction=direction)
                # Twenty observed prior closes yield MA20_prev=120 (long) /80 (short).
                for i in range(20):
                    day=(datetime(2025,1,3)+timedelta(days=7*i)).date().isoformat()
                    self.accepted(s,day,120. if direction=='long' else 80.)
                b=self.accepted(s,'2026-01-09',last)
                s.enable_ma_trend_stop=True
                before=s.research_macd_call_attempts
                self.assertEqual(s._process_rsi_partial_exit(st,b,100.),'')
                self.assertEqual(st.active_volume(),4)
                self.assertEqual(s.profit_half_decisions[-1]['action'],'defer_ma_full_stop')
                self.assertEqual(s.research_macd_call_attempts,before)
                self.assertTrue(s._stop_triggered(direction,b,120. if direction=='long' else 80.))
    def test_prior_full_exit_and_daily_margin_safety_are_inherited(self):
        s=self.strategy();st=self.opening(s);b=self.accepted(s,'2026-01-09',70.)
        self.assertEqual(s._process_layer_stops(st,b),'long_base_stop')
        self.assertEqual(s.profit_half_triggers,[])
        s=self.strategy();st=self.opening(s);b=bar('2026-01-07',106.)
        s.current_bar_date=pd.Timestamp('2026-01-07');s.enable_portfolio_margin_deleverage=True
        s.portfolio_margin_deleverage_pressure=2.;s.portfolio_margin_deleverage_min_pressure=1.
        s.portfolio_margin_deleverage_layer_kinds='base'
        self.assertEqual(s._process_portfolio_margin_deleverage(st,b),'long_portfolio_margin_deleverage')
        self.assertEqual(st.layers,[]);self.assertEqual(s.profit_half_triggers,[])
    def test_actual_formal_mro_sync_uses_trade_price_and_keeps_stop_modules(self):
        from analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine import QmtRollPortfolioStrategyStage847C9StopRetry as Formal
        class FormalHarness(Formal,Harness):
            __init__=Harness.__init__
            _record_entry_risk_diagnostic=Harness._record_entry_risk_diagnostic
            _record_trade_event=Harness._record_trade_event
        s=self.strategy(base=FormalHarness);st=self.opening(s,cost=100.)
        st.layers[0].entry_price_synced=False
        trade=TradeData(symbol=SYMBOL.split('.')[0],exchange=bar('2026-01-05').exchange,orderid='1',tradeid='1',
            direction=Direction.LONG,offset=Offset.OPEN,price=110.,volume=4,datetime=datetime(2026,1,6),gateway_name='TEST')
        trade.signal_datetime=datetime(2026,1,5)
        s._sync_open_trade(trade)
        self.assertEqual(st.layers[0].entry_price,110.)
        self.assertEqual(self.decision(s,st,106.),'')
        self.assertEqual(self.decision(s,st,116.),'long_profit5_half')
        self.assertFalse(s.enable_rsi_partial_exit)
        self.assertEqual(st.active_volume(),2)
    def test_audit_requires_anchor_fill_evidence_and_accepts_gap_below_threshold(self):
        s=self.strategy();st=self.opening(s);self.decision(s,st)
        self.assertTrue(callable(audit_profit_half))
        with self.assertRaisesRegex(ValueError,'evidence_missing'):audit_profit_half(s)
        result=audit_profit_half(s,self.fill_frames(s))
        self.assertTrue(result['accepted']);self.assertEqual(result['filled_trigger_count'],1)
        self.assertEqual(result['terminal_pending_trigger_count'],0)
    def test_audit_rejects_missing_wrong_volume_direction_and_same_day_fill(self):
        for kind in ['missing','volume','direction','same_day']:
            with self.subTest(kind=kind):
                s=self.strategy();st=self.opening(s);self.decision(s,st);frames=self.fill_frames(s)
                if kind=='missing':frames['execution_anchor_requests']=frames['execution_anchor_requests'].iloc[:0]
                if kind=='volume':frames['trades'].loc[0,'volume']=1
                if kind=='direction':frames['trades'].loc[0,'direction']='long'
                if kind=='same_day':frames['trades'].loc[0,'trading_date']='2026-01-07';frames['execution_anchor_requests'].loc[0,'trading_date']='2026-01-07'
                with self.assertRaises(ValueError):audit_profit_half(s,frames)
    def test_terminal_pending_is_explicit_actual_order_only_and_only_terminal_day(self):
        s=self.strategy();st=self.opening(s);self.decision(s,st)
        order=SimpleNamespace(vt_orderid='P1',vt_symbol=SYMBOL,datetime=datetime(2026,1,7),offset=Offset.CLOSE,
            direction=Direction.SHORT,volume=2,traded=0)
        s.strategy_engine.active_limit_orders={'P1':order}
        frames={'trades':pd.DataFrame(columns=['order_id','vt_symbol','direction','offset','volume']),
            'execution_anchor_requests':pd.DataFrame(columns=['order_id','signal_date','vt_symbol','offset']),
            'trade_events':self.fill_frames(s)['trade_events']}
        result=audit_profit_half(s,frames)
        self.assertEqual(result['terminal_pending_trigger_count'],1)
        s.current_bar_date=pd.Timestamp('2026-01-08')
        with self.assertRaises(ValueError):audit_profit_half(s,frames)
    def test_multilayer_actual_weighted_cost_and_decimal_five_boundary(self):
        s=self.strategy();st=self.opening(s,cost=100.)
        second=deepcopy(st.layers[0]);second.volume=1;second.entry_price=140.
        st.layers[0].volume=3;st.layers.append(second)
        self.assertEqual(self.decision(s,st,115.5),'')
        self.assertEqual(self.decision(s,st,115.5001),'long_profit5_half')
        self.assertEqual(s.profit_half_triggers[0]['cost'],110.)
        self.assertEqual(st.active_volume(),2)
        self.assertEqual(st.layers[0].entry_price,100.)
    def test_audit_rejects_missing_event_wrong_anchor_source_and_fill_price(self):
        for kind in ['missing_event','event_quantity','anchor_source','anchor_price','fill_price','layer_cost']:
            with self.subTest(kind=kind):
                s=self.strategy();st=self.opening(s);self.decision(s,st);frames=self.fill_frames(s)
                if kind=='missing_event':del frames['trade_events']
                if kind=='event_quantity':frames['trade_events'].loc[0,'volume']=3
                if kind=='anchor_source':frames['execution_anchor_requests'].loc[0,'source']='minute_proxy'
                if kind=='anchor_price':frames['execution_anchor_requests'].loc[0,'daily_open']=999.
                if kind=='fill_price':frames['trades'].loc[0,'price']=999.
                if kind=='layer_cost':s.profit_half_triggers[0]['cost']=99.
                with self.assertRaises(ValueError):audit_profit_half(s,frames)

    def test_final_forced_margin_keeps_exact_reason_volumes_in_net_close(self):
        s=self.strategy();st=self.opening(s);self.decision(s,st)
        s.enable_forced_margin_deleverage=True;s.estimated_equity=200.;s.base_capital=150000.
        s.forced_margin_deleverage_trigger_ratio=1.5;s.forced_margin_deleverage_target_ratio=1.
        s.forced_margin_deleverage_broker_multiplier=1.65;s.forced_margin_deleverage_max_reductions_per_day=10
        s.forced_margin_deleverage_priority='largest_margin';s.forced_margin_deleverage_count=0
        s.forced_margin_deleverage_closed_volume=0;s.forced_margin_deleverage_max_observed_ratio=0.
        s.forced_margin_deleverage_events=[]
        s._process_forced_margin_deleverage({SYMBOL:bar('2026-01-07',106.)})
        self.assertEqual(st.active_volume(),1);self.assertEqual(s.targets[SYMBOL],1)
        self.assertEqual(s.events[-1]['reason'],'forced_margin_deleverage');self.assertEqual(s.events[-1]['volume'],1)
        frames=self.fill_frames(s);frames['trades'].loc[0,'volume']=3
        frames['trade_events']=pd.concat([frames['trade_events'],pd.DataFrame([dict(date='2026-01-07',vt_symbol=SYMBOL,
            reason='forced_margin_deleverage',volume=1,price=106.,direction='short',offset='Close')])],ignore_index=True)
        try:result=audit_profit_half(s,frames)
        except ValueError as exc:self.fail('exact half+forced event quantities must reconcile: '+str(exc))
        self.assertEqual(result['executed_trigger_count'],1)
        self.assertEqual(result['execution_allocations'][0]['profit_half_volume'],2)
        self.assertEqual(result['execution_allocations'][0]['forced_margin_deleverage_volume'],1)
        frames['trade_events']=frames['trade_events'].iloc[:1]
        with self.assertRaises(ValueError):audit_profit_half(s,frames)

    def test_audit_rejects_duplicate_episode_trigger_and_rsi_event(self):
        s=self.strategy();st=self.opening(s);self.decision(s,st)
        s.profit_half_triggers.append(deepcopy(s.profit_half_triggers[0]))
        with self.assertRaises(ValueError):audit_profit_half(s,self.fill_frames(s))
        s.profit_half_triggers.pop();frames=self.fill_frames(s);frames['trade_events'].loc[0,'reason']='long_rsi_partial_exit_half'
        with self.assertRaisesRegex(ValueError,'forbidden'):audit_profit_half(s,frames)

if __name__=='__main__':unittest.main()
