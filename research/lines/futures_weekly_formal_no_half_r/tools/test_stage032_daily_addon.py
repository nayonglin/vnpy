"""Hand-calculated adapter contracts; no financial replay."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
import pandas as pd
from vnpy.trader.constant import Direction, Offset
from qmt_roll_portfolio_strategy import QmtRollPortfolioStrategy, ProductState, PositionLayer
from test_stage029_week_close_exits_v2 import SizingHarness
from test_stage029_week_close_exits import bar
try:
    from stage032_daily_addon import daily_addon_strategy_class, daily_addon_engine_class, audit_daily_addon, KIND
except ImportError:
    daily_addon_strategy_class = None
    KIND = 'stage032_daily_addon'
S='rb1510.SHFE'; P='rb.SHFE'; DAYS=pd.bdate_range('2020-01-01',periods=18).strftime('%Y-%m-%d').tolist()

class Harness(SizingHarness):
    def __init__(self):
        super().__init__(); self.pos_data={S:2}; self.targets[S]=2; self.pending_close_lots={}
        self.strategy_engine=SimpleNamespace(bars={},active_limit_orders={},datetime=pd.Timestamp(DAYS[0]))
        self.states={P:ProductState(P,S,'long',layers=[PositionLayer('base','long',2,100.,70.,100.,70.,'long_case2',DAYS[0],entry_price_synced=True)],entry_date=DAYS[0])}
        self.free=100000.; self.budget=10000.; self.trade_reason_by_trade_id={}; self.pending_close_reasons={}
        self.total_margin_in_use=200.; self.trade_costs_total=0.; self.estimated_equity=150000.
        self.enable_risk_cluster_heat_gate=False; self.enable_forced_margin_deleverage=False
    def get_pos(self,s): return self.pos_data.get(s,0)
    def _daily_addon_admission(self,state,b,stop,price=None):
        price=float(b.close_price if price is None else price); risk=(price-stop)*10
        return {'accepted':self.free>=price and risk<=self.budget,'reason':'accepted' if self.free>=price and risk<=self.budget else 'budget_rejected','margin_per_contract':price,'risk_per_contract':risk}
    def _reserve_intrabar_margin(self,s,n,p): self.pending_margin_reservation+=n*p
    def _queue_pending_close_lot(self,*a): return QmtRollPortfolioStrategy._queue_pending_close_lot(self,*a)
    def _sync_close_trade(self,t): return QmtRollPortfolioStrategy._sync_close_trade(self,t)
    def update_trade(self,t):
        self.pos_data[t.vt_symbol]=self.get_pos(t.vt_symbol)+(1 if t.direction==Direction.LONG else -1)*int(t.volume)
        if t.offset==Offset.OPEN:
            self._sync_open_trade(t)
        else:self.realized_pnl+=self._sync_close_trade(t)
    def _sync_open_trade(self,t):
        for l in self._find_state_by_contract(t.vt_symbol).layers:
            if not l.entry_price_synced:l.entry_price=float(t.price);l.entry_price_synced=True
    def rebalance_portfolio(self,bars):pass
    def _handle_rollover(self,state,target,bars):
        volume=state.active_volume();self.roll_volume=volume
        self._close_all_layers(state,bars[S].close_price);self.set_target(S,0)
        state.contract_vt_symbol=target;state.direction='long';state.entry_date=DAYS[5]
        state.layers=[PositionLayer('base','long',volume,110.,70.,110.,70.,'rollover_reopen',DAYS[5])]
        self._apply_state_target(state)

class DailyAddonTests(unittest.TestCase):
    def setUp(self):self.assertIsNotNone(daily_addon_strategy_class,'Stage032 adapter is not implemented')
    def make(self,enabled=True):
        cls=daily_addon_strategy_class(Harness,{},DAYS,{(S,d):'rb1510-2015' for d in DAYS},enabled=enabled)
        if enabled:
            class IsolatedAdmissionHarness(cls):
                _daily_addon_admission=Harness._daily_addon_admission
            cls=IsolatedAdmissionHarness
        result=cls()
        if enabled and hasattr(result,'_da_inventory'):
            result._da_inventory[S]=[dict(inventory_id='fixture-base',sleeve='base',volume=2,reserved=0,position_direction='long',entry_price=100.,stop_price=70.,round_id=0,addon_id='',product_vt_symbol=P)]
        return result
    def day(self,s,i,close,low=90,volume=10,symbol=S):
        b=bar(DAYS[i],close,max(close,120),min(low,close),symbol,volume)
        s.current_bar_date=pd.Timestamp(DAYS[i]);s.strategy_engine.datetime=b.datetime;s.strategy_engine.bars={symbol:b}
        (s._daily_addon_after_bars({symbol:b}) if s.research_daily_addon_enabled else s.on_bars({symbol:b}));return b
    def fill(self,s,i,price,open=True,volume=1):
        t=SimpleNamespace(vt_symbol=S,vt_tradeid='T'+str(len(s.daily_addon_allocations)),vt_orderid='O'+str(i),datetime=pd.Timestamp(DAYS[i]),trading_date=DAYS[i],signal_datetime=pd.Timestamp(DAYS[i-1]),price=price,volume=volume,direction=Direction.LONG if open else Direction.SHORT,offset=Offset.OPEN if open else Offset.CLOSE)
        s.update_trade(t);return t
    def signal(self,s):self.day(s,0,100);self.day(s,1,101,92);self.day(s,2,103,94)
    def test_two_completed_up_days_plan_single_lot_without_consuming_count(self):
        s=self.make();self.signal(s);st=s.states[P]
        self.assertEqual([l.volume for l in st.layers],[2,1]);self.assertEqual(st.layers[-1].stop_price,92)
        self.assertEqual(s.daily_addon_rounds[-1]['actual_add_count'],0);self.assertEqual(s.get_target(S),3)
        self.day(s,3,104);self.assertEqual(len(st.layers),2)
    def test_actual_fill_syncs_only_addon_and_consumes_once(self):
        s=self.make();self.signal(s);self.fill(s,3,106)
        self.assertEqual([l.entry_price for l in s.states[P].layers],[100,106]);self.assertEqual(s.daily_addon_rounds[-1]['actual_add_count'],1)
        self.assertEqual(s.daily_addon_allocations[-1]['sleeve'],'daily_addon');self.assertEqual(s.get_pos(S),3)
    def test_strict_close_stop_including_entry_day_and_fixed_stop(self):
        s=self.make();self.signal(s);self.fill(s,3,106);self.day(s,3,92,80)
        self.assertEqual(s.get_target(S),3);self.day(s,4,91,70)
        self.assertEqual(s.get_target(S),2);self.assertEqual(s.get_pos(S),3)
        self.fill(s,5,89,False);self.assertEqual(s.daily_addon_allocations[-1]['entry_price'],106)
        self.assertEqual(s.daily_addon_allocations[-1]['stop_price'],92);self.assertEqual(s.states[P].layers[0].volume,2)
    def test_close_fill_day_can_restart_and_second_exit_exhausts_round(self):
        s=self.make();self.signal(s);self.fill(s,3,106);self.day(s,3,91);self.fill(s,4,90,False)
        self.day(s,4,94);self.day(s,5,96);self.assertEqual(s.get_target(S),3)
        self.fill(s,6,98);self.day(s,6,80);self.fill(s,7,78,False)
        self.day(s,7,90);self.day(s,8,100);self.day(s,9,110)
        self.assertEqual(s.get_target(S),2);self.assertEqual(s.daily_addon_rounds[-1]['actual_add_count'],2)
    def test_equal_down_missing_and_zero_volume_break_streak(self):
        for issue in ('equal','zero','gap','epoch'):
            with self.subTest(issue=issue):
                s=self.make();self.day(s,0,100);self.day(s,1,101)
                if issue=='equal':self.day(s,2,101)
                elif issue=='zero':self.day(s,2,103,volume=0)
                elif issue=='gap':self.day(s,3,103)
                else:s._daily_addon_epoch_lookup[(S,DAYS[2])]='different';self.day(s,2,103)
                self.assertEqual(len(s.states[P].layers),1)
    def test_disabled_and_short_never_add(self):
        for enabled,direction in ((False,'long'),(True,'short')):
            s=self.make(enabled);s.states[P].direction=direction;self.signal(s)
            self.assertEqual(len(s.states[P].layers),1);self.assertEqual(s.get_target(S),2)
    def test_capital_rejection_no_count_then_reassess_recent_pair(self):
        s=self.make();s.free=0;self.signal(s)
        self.assertEqual(len(s.states[P].layers),1);self.assertEqual(s.daily_addon_rounds[-1]['actual_add_count'],0)
        s.free=100000;self.day(s,3,104);self.assertEqual(len(s.states[P].layers),2)
    def test_reconcile_does_not_absorb_addon_into_base(self):
        s=self.make();self.signal(s);self.fill(s,3,106)
        s._reconcile_state_with_position(s.states[P],3,bar(DAYS[3],106,symbol=S))
        self.assertEqual([l.volume for l in s.states[P].layers],[2,1])
    def test_forced_reduction_closes_addon_first_and_preserves_actual_until_fill(self):
        s=self.make();self.signal(s);self.fill(s,3,106)
        s._reduce_position_to_target(s.states[P],2,105);s._apply_state_target(s.states[P])
        self.assertEqual([l.kind for l in s.states[P].layers],['base']);self.assertEqual(s.get_pos(S),3)
        self.fill(s,4,104,False);self.assertEqual(s.daily_addon_allocations[-1]['sleeve'],'daily_addon')
    def test_parent_full_exit_closes_both_owners_and_allocations_conserve(self):
        s=self.make();self.signal(s);self.fill(s,3,106)
        s._close_all_layers_and_set_flat_target(s.states[P],105,exit_reason='long_ma_stop')
        self.fill(s,4,104,False,3)
        rows=[r for r in s.daily_addon_allocations if r['offset']=='close']
        self.assertEqual(sum(r['volume'] for r in rows),3);self.assertEqual(sorted(r['sleeve'] for r in rows),['base','daily_addon']);self.assertEqual(s.daily_addon_rounds[-1]['status'],'closed')
    def test_roll_reopens_parent_only_and_inherits_round_count(self):
        s=self.make();self.signal(s);self.fill(s,3,106);roundid=s.daily_addon_rounds[-1]['round_id']
        s._handle_rollover(s.states[P],'rb1511.SHFE',{S:bar(DAYS[5],110,symbol=S)})
        self.assertEqual(s.roll_volume,2);self.assertEqual(s.daily_addon_rounds[-1]['round_id'],roundid)
        self.assertEqual(s.daily_addon_rounds[-1]['actual_add_count'],1)
    def test_open_at_or_below_fixed_stop_cancels_without_consuming(self):
        s=self.make();self.signal(s)
        order=SimpleNamespace(vt_symbol=S,vt_orderid='O3',offset=Offset.OPEN,volume=1,traded=0,datetime=pd.Timestamp(DAYS[2]))
        b=bar(DAYS[3],92,symbol=S);s.strategy_engine.active_limit_orders={'O3':order}
        self.assertFalse(s._daily_addon_before_fill(order,b))
        self.assertEqual(s.get_target(S),2);self.assertEqual(s.daily_addon_rounds[-1]['actual_add_count'],0)
    def test_stop_layer_is_hidden_from_weekly_technical_mutation(self):
        s=self.make();self.signal(s);self.fill(s,3,106);st=s.states[P];addon=st.layers[-1]
        b=bar(DAYS[3],120,150,50,S);s.current_bar_date=pd.Timestamp(DAYS[3]);s.ams[S].weeks[tuple(b.datetime.date().isocalendar()[:2])]=(DAYS[3],);s.ams[S].update_bar(b);before=deepcopy(addon.__dict__)
        s._update_dynamic_stops(st,b,pd.DataFrame())
        self.assertEqual(addon.__dict__,before)

    def test_disabled_factory_has_original_methods_and_no_addon_callbacks(self):
        from stage029_week_close_exits_v2 import week_close_exit_strategy_class
        original=week_close_exit_strategy_class(Harness,{})
        disabled=daily_addon_strategy_class(Harness,{},DAYS,{},enabled=False)
        self.assertEqual(disabled.__name__,original.__name__)
        self.assertNotIn('_daily_addon_after_bars',disabled.__dict__)
        self.assertIs(disabled.update_trade,Harness.update_trade)
        self.assertTrue(audit_daily_addon(disabled())['accepted'])
    def test_engine_cancels_rejected_addon_without_parent_fill(self):
        s=self.make();self.signal(s)
        class E:
            def __init__(self):self.strategy=s;self.fills=0;self.cancelled=[]
            def cancel_order(self,strategy,oid):self.cancelled.append(oid)
            def _fill_order(self,order,b):self.fills+=1
        e=daily_addon_engine_class(E)();order=SimpleNamespace(vt_symbol=S,vt_orderid='O',offset=Offset.OPEN,volume=1,traded=0)
        e._fill_order(order,bar(DAYS[3],90,symbol=S))
        self.assertEqual(e.fills,0);self.assertEqual(e.cancelled,['O']);self.assertEqual(s.states[P].active_volume(),2)
    def test_open_budget_uses_signal_capacity_and_open_not_future_close(self):
        s=self.make();self.signal(s)
        item=s._da_active[S];item['admission']={'risk_amount':150.,'limited_balance':1000.,'free_capital':1000.,'single_trade_capital_limit':1000.,'margin_per_contract':103.}
        b=bar(DAYS[3],1000,1200,10,S);b.open_price=106
        order=SimpleNamespace(vt_symbol=S,vt_orderid='O',offset=Offset.OPEN,volume=1,traded=0)
        self.assertTrue(s._daily_addon_before_fill(order,b))
        s=self.make();self.signal(s);s._da_active[S]['admission']=dict(item['admission'])
        b.open_price=108
        self.assertFalse(s._daily_addon_before_fill(order,b))
    def test_technical_full_close_restores_hidden_addon_before_exit(self):
        s=self.make();self.signal(s);self.fill(s,3,106);st=s.states[P]
        with s._da_base_only(st):
            self.assertEqual(st.active_volume(),2)
            s._close_all_layers_and_set_flat_target(st,95.,exit_reason='long_base_stop')
        self.assertEqual(st.layers,[]);self.assertEqual(s.get_target(S),0)
        self.fill(s,4,94,False,3)
        rows=[r for r in s.daily_addon_allocations if r['offset']=='close'];self.assertEqual(sum(r['volume'] for r in rows),3)
    def test_daily_risk_estimator_sees_actual_addon_layer(self):
        s=self.make();self.signal(s);self.fill(s,3,106)
        self.assertEqual(s._estimate_margin_usage({S:bar(DAYS[3],110,symbol=S)}),330.)
    def test_audit_rejects_counter_and_allocation_tampering(self):
        s=self.make();self.signal(s);self.fill(s,3,106)
        s.daily_addon_allocations.insert(0,dict(trade_id='initial',order_id='initial',vt_symbol=S,product_vt_symbol=P,trading_date=DAYS[0],datetime=DAYS[0],direction='long',offset='open',volume=2,price=100.,sleeve='base',round_id=0,addon_id='',reason='fixture_actual_open',entry_price=100.,stop_price=70.))
        frame=pd.DataFrame([{'trade_id':'initial','volume':2},{'trade_id':'T0','volume':1}])
        self.assertTrue(audit_daily_addon(s,{'trades':frame})['accepted'])
        with self.assertRaisesRegex(ValueError,'not_conserved'):audit_daily_addon(s,{'trades':pd.DataFrame([{'trade_id':'T0','volume':2}])})
        s.daily_addon_rounds[-1]['actual_add_count']=2
        with self.assertRaisesRegex(ValueError,'count_mismatch'):audit_daily_addon(s)

    def formal(self):
        import json
        from pathlib import Path
        from analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine import QmtRollPortfolioStrategyStage847C9StopRetry as Formal
        setting=json.loads((Path(__file__).parents[1]/'outputs/R_attempt003/actual_strategy_settings.json').read_text())[0]['setting']
        e=SimpleNamespace(capital=150000,get_size=lambda *a:10,get_pricetick=lambda *a:1,bars={},write_log=lambda *a:None)
        s=daily_addon_strategy_class(Formal,{},DAYS,{(S,d):'epoch' for d in DAYS})(e,'TEST',[S],setting)
        s.current_bar_date=pd.Timestamp(DAYS[2]);s.estimated_equity=150000;s.total_margin_in_use=200
        s.states[P]=ProductState(P,S,'long',layers=[PositionLayer('base','long',2,100,70,100,70,'long_case2',DAYS[0],entry_price_synced=True)])
        s.ams[S].update_bar(bar(DAYS[2],103,symbol=S))
        return s
    def test_real_formal_budget_chain_and_stop_override(self):
        s=self.formal();r=s._daily_addon_admission(s.states[P],bar(DAYS[2],103,symbol=S),92)
        self.assertTrue(r['accepted']);self.assertEqual(r['stop_price'],92)
        self.assertEqual(r['risk_per_contract'],110);self.assertTrue(r['stage830_broker10_margin_cap_enabled'])
        self.assertEqual(s.initial_stop_audit,[])
        s.total_margin_in_use=149999
        self.assertFalse(s._daily_addon_admission(s.states[P],bar(DAYS[2],103,symbol=S),92)['accepted'])
    def test_actual_single_lot_heat_gate_not_larger_sizing_proxy(self):
        s=self.formal();s.enable_risk_cluster_heat_gate=True;s.risk_cluster_heat_gate_entry_contexts='regular_add'
        s.risk_cluster_heat_gate_target_clusters='';s.risk_cluster_map='rb.SHFE=black';s.portfolio_drawdown_pct=.2
        s.cluster_margin_usage={'black':30000.};s.risk_cluster_heat_gate_margin_start_ratio=.1;s.risk_cluster_heat_gate_margin_full_ratio=.3
        r=s._daily_addon_admission(s.states[P],bar(DAYS[2],103,symbol=S),92)
        self.assertFalse(r['accepted'])
    def test_open_rechecks_frozen_broker_and_incremental_cap(self):
        for field in ('broker_margin_capacity','incremental_margin_capacity','heat_margin_capacity'):
            s=self.make();self.signal(s);s._da_active[S]['admission'][field]=104.
            order=SimpleNamespace(vt_symbol=S,vt_orderid='O',offset=Offset.OPEN,volume=1,traded=0)
            self.assertFalse(s._daily_addon_before_fill(order,bar(DAYS[3],106,symbol=S)))

    def test_fill_and_cancel_events_use_trading_day_not_previous_callback_day(self):
        s=self.make();self.signal(s);self.fill(s,3,106)
        self.assertEqual(s.daily_addon_events[-1]['date'],DAYS[3])
        self.day(s,3,91);self.fill(s,4,90,False)
        self.assertEqual(s.daily_addon_events[-1]['date'],DAYS[4])
        s=self.make();self.signal(s)
        order=SimpleNamespace(vt_symbol=S,vt_orderid='O',offset=Offset.OPEN,volume=1,traded=0)
        s._daily_addon_before_fill(order,bar(DAYS[3],90,symbol=S))
        self.assertEqual(s.daily_addon_events[-1]['date'],DAYS[3])

    def shared_pending(self):
        s=self.make();self.signal(s);other='cu1510.SHFE'
        a=s._da_active[S];a['admission']={'risk_amount':100000,'allowed_capital':206.,'reserved_margin_before':0.,'margin_per_contract':103.}
        b=deepcopy(a);b.update(vt_symbol=other,addon_id='2:1',product_vt_symbol='cu.SHFE')
        b['admission']={'risk_amount':100000,'allowed_capital':206.,'reserved_margin_before':103.,'margin_per_contract':103.}
        s._da_active[other]=b;s._daily_addon_epoch_lookup[(other,DAYS[3])]=a['epoch']
        return s,other
    def order(self,symbol):return SimpleNamespace(vt_symbol=symbol,vt_orderid=symbol,offset=Offset.OPEN,volume=1,traded=0)
    def test_shared_pending_budget_rejects_joint_overallocation_in_either_fill_order(self):
        for reverse in (False,True):
            s,other=self.shared_pending();pairs=[(S,104.),(other,103.)]
            if reverse:pairs.reverse()
            results=[s._daily_addon_before_fill(self.order(sym),bar(DAYS[3],price,symbol=sym)) for sym,price in pairs]
            self.assertFalse(all(results));self.assertLessEqual(sum(price for (_,price),ok in zip(pairs,results) if ok),206.)
    def test_cancelled_pending_releases_frozen_reservation_for_later_sibling(self):
        s,other=self.shared_pending()
        self.assertFalse(s._daily_addon_before_fill(self.order(S),bar(DAYS[3],90,symbol=S)))
        self.assertTrue(s._daily_addon_before_fill(self.order(other),bar(DAYS[3],150,symbol=other)))
    def test_parent_open_gap_consumes_addon_budget_without_parent_interception(self):
        s=self.make();self.signal(s);a=s._da_active[S]
        a['admission']={'risk_amount':100000,'allowed_capital':206.,'reserved_margin_before':103.,'margin_per_contract':103.}
        s._da_begin_open_batch(DAYS[3]);s._da_record_parent_open_gap('parent','black',20.)
        self.assertFalse(s._daily_addon_before_fill(self.order(S),bar(DAYS[3],103,symbol=S)))

    def test_explicit_close_reason_reaches_both_owner_queues_before_event(self):
        s=self.make();self.signal(s);self.fill(s,3,106)
        s._da_last_close_reason[S]='stale_old_reason'
        s._close_layers(s.states[P],[0,1],105,exit_reason='long_risk_cluster_heat_deleverage')
        self.fill(s,4,104,False,3)
        self.assertEqual({r['reason'] for r in s.daily_addon_allocations if r['offset']=='close'},{'long_risk_cluster_heat_deleverage'})

    def test_known_same_contract_open_reprices_held_base_for_addon_budget(self):
        s=self.make();self.signal(s)
        s._da_active[S]['admission']={'risk_amount':10000.,'allowed_capital':310.,'reserved_margin_before':206.,'margin_per_contract':103.}
        self.assertFalse(s._daily_addon_before_fill(self.order(S),bar(DAYS[3],104,symbol=S)))

    def actual_owner_sequence(self,symbol,planned,removed,base_volume,base_price,addon_price,exit_price,mode):
        s=self.make();product=s._product_vt_symbol(symbol)
        state=ProductState(product,symbol,'long',layers=[PositionLayer('base','long',planned,1812.,1700.,1900.,1700.,'long_case2',DAYS[0])],entry_date=DAYS[0])
        s.states={product:state};s.pos_data={symbol:0};s.targets={symbol:planned};s.target_data=s.targets
        if hasattr(s,'_da_inventory'):s._da_inventory={}
        s.current_bar_date=pd.Timestamp(DAYS[0]);s._da_last_close_reason[symbol]='forced_margin_deleverage'
        s._reduce_position_to_target(state,planned-removed,1812.)
        if not state.layers:
            state.contract_vt_symbol=symbol;state.direction='long';state.entry_date=DAYS[1]
            state.layers=[PositionLayer('base','long',base_volume,base_price,1700.,1900.,1700.,'long_case2',DAYS[1])]
        state.layers[0].volume=base_volume
        r=s._da_new_round(state,DAYS[1]);counter=[0]
        def fill(price,volume,opened,day):
            counter[0]+=1
            t=SimpleNamespace(vt_symbol=symbol,vt_tradeid=f'actual.{counter[0]}',vt_orderid=f'actual.{counter[0]}',datetime=pd.Timestamp(day),trading_date=day,signal_datetime=pd.Timestamp(DAYS[0]),price=price,volume=volume,direction=Direction.LONG if opened else Direction.SHORT,offset=Offset.OPEN if opened else Offset.CLOSE)
            s.update_trade(t)
        fill(base_price,base_volume,True,DAYS[1])
        addon=dict(addon_id=f"{r['round_id']}:1",round_id=r['round_id'],product_vt_symbol=product,vt_symbol=symbol,status='pending_open',signal_date=DAYS[2],stop_price=addon_price-100.,epoch='fixture')
        s._da_active[symbol]=addon
        state.layers.append(PositionLayer(KIND,'long',1,addon_price,addon_price-100.,addon_price,addon_price-100.,'daily_addon',DAYS[2]))
        fill(addon_price,1,True,DAYS[3]);s.current_bar_date=pd.Timestamp(DAYS[4])
        if mode=='addon_then_base':
            s._da_close_layer(state,state.layers[-1],exit_price,'daily_addon_fixed_stop')
            fill(exit_price,1,False,DAYS[5])
            self.assertEqual(s.daily_addon_allocations[-1]['sleeve'],'daily_addon')
            s._close_all_layers(state,exit_price-166.,exit_reason='long_risk_cluster_heat_deleverage')
            fill(exit_price-166.,base_volume,False,DAYS[6])
        else:
            s._close_all_layers(state,exit_price,exit_reason='rollover' if mode=='rollover' else 'long_base_stop')
            fill(exit_price,base_volume+1,False,DAYS[5])
        self.assertTrue(audit_daily_addon(s)['owner_inventory_verified'])
        return s,symbol
    def test_fg401_unfilled22_does_not_consume_later10base_plus1addon_close(self):
        s,symbol=self.actual_owner_sequence('FG401.CZCE',22,22,10,1731.,1898.,1853.,'full')
        closed=[r for r in s.daily_addon_allocations if r['offset']=='close']
        self.assertEqual(sum(r['volume'] for r in closed if r['sleeve']=='base'),10)
        self.assertEqual([r['entry_price'] for r in closed if r['sleeve']=='base'],[1731.])
        self.assertEqual(sum(r['volume'] for r in closed if r['sleeve']=='daily_addon'),1)
        self.assertNotIn(symbol,s._da_active)
    def test_sm505_unfilled28_does_not_steal_actual_stop1_then_base27(self):
        s,symbol=self.actual_owner_sequence('SM505.CZCE',55,28,27,6870.,7354.,6592.,'addon_then_base')
        closed=[r for r in s.daily_addon_allocations if r['offset']=='close']
        self.assertEqual([(r['sleeve'],r['volume']) for r in closed],[('daily_addon',1),('base',27)])
        self.assertNotIn(symbol,s._da_active)
    def test_cu2509_unfilled4_does_not_steal_rollover2base_plus1addon(self):
        s,symbol=self.actual_owner_sequence('cu2509.SHFE',6,4,2,79060.,79640.,79580.,'rollover')
        closed=[r for r in s.daily_addon_allocations if r['offset']=='close']
        self.assertEqual(sum(r['volume'] for r in closed if r['sleeve']=='daily_addon'),1)
        self.assertEqual(sum(r['volume'] for r in closed if r['sleeve']=='base'),2)
        self.assertNotIn(symbol,s._da_active)
    def test_unfilled_base_close_keeps_parent_queue_but_not_owner_queue(self):
        s=self.make();s.pos_data[S]=0
        layer=PositionLayer('base','long',22,1812.,1700.,1900.,1700.,'long_case2',DAYS[0])
        s._queue_pending_close_lot(S,layer,1812.,22)
        self.assertEqual(sum(x['volume'] for x in s.pending_close_lots[S]),22)
        self.assertFalse(s._da_close_queue.get(S))
    def test_actual_inventory_cannot_be_reserved_twice(self):
        s=self.make();layer=s.states[P].layers[0]
        s._queue_pending_close_lot(S,layer,105.,2);s._queue_pending_close_lot(S,layer,105.,2)
        self.assertEqual(sum(x['volume'] for x in s._da_close_queue[S]),2)
        self.assertEqual(sum(x['volume'] for x in s.pending_close_lots[S]),4)
    def test_c001_raw_allocations_are_rejected_even_with_per_fill_volume_conservation(self):
        from pathlib import Path
        out=Path(__file__).parents[1]/'outputs/stage032_C_attempt001'
        s=self.make();s.daily_addon_allocations=pd.read_csv(out/'daily_addon_allocations.csv').fillna('').to_dict('records')
        s.daily_addon_rounds=pd.read_csv(out/'daily_addon_rounds.csv').fillna('').to_dict('records')
        with self.assertRaisesRegex(ValueError,'owner_inventory_overclose'):audit_daily_addon(s)

if __name__=='__main__':unittest.main()
