"""Lifecycle policy and natural universe capacity; synthetic tests, no financial replay."""
from datetime import datetime
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parent))
from vnpy.trader.setting import SETTINGS
SETTINGS['log.file']=False
try:
    from stage018_run import FullMarketDailyEngine,candidate_overrides,FeeStrategy as FullMarketNoAIOneLot
except ModuleNotFoundError as exc:
    if exc.name!='stage018_run':raise
    from stage003_candidate import FullMarketNoAIOneLot,candidate_overrides
    from stage004_run import FullMarketDailyEngine
from vnpy_portfoliostrategy.template import StrategyTemplate
from vnpy.trader.object import BarData,OrderData
from vnpy.trader.constant import Direction,Offset,Exchange,Status
from qmt_roll_portfolio_strategy import ProductState,PositionLayer
try:
    from stage016_contract_lifecycle import LifecyclePolicy
except ModuleNotFoundError as exc:
    if exc.name!='stage016_contract_lifecycle':raise
    LifecyclePolicy=None


class LifecycleRegressions(unittest.TestCase):
    def calendar(self):
        return pd.bdate_range('2021-11-01','2022-02-01').strftime('%Y-%m-%d').tolist()

    def policy(self,metadata=None,calendar=None):
        self.assertIsNotNone(LifecyclePolicy,'lifecycle policy is required before replay')
        return LifecyclePolicy(metadata or {'IC202112.CFFEX':dict(
            maturity_date='2021-12-17',contract_yyyymm='202112',product='IC',product_class='Index')},
            calendar if calendar is not None else self.calendar())

    def test_index_deadline_precedes_maturity_and_close_intent_is_one_session_earlier(self):
        p=self.policy()
        self.assertEqual(str(pd.Timestamp(p.deadline('IC202112.CFFEX')).date()),'2021-12-16')
        self.assertFalse(p.exit_due('IC202112.CFFEX','2021-12-14'))
        self.assertTrue(p.exit_due('IC202112.CFFEX','2021-12-15'))
        self.assertTrue(p.exit_due('IC202112.CFFEX','2021-12-16'))

    def test_nonindex_research_buffer_precedes_delivery_month_and_maturity(self):
        p=self.policy({'rb202201.SHFE':dict(maturity_date='2022-01-17',
            contract_yyyymm='202201',product='RB',product_class='Commodity')})
        self.assertEqual(str(pd.Timestamp(p.deadline('rb202201.SHFE')).date()),'2021-12-30')
        self.assertTrue(p.exit_due('rb202201.SHFE','2021-12-29'))

    def test_earlier_maturity_controls_monthly_average_family(self):
        p=self.policy({'l_F202202.DCE':dict(maturity_date='2022-01-04',
            contract_yyyymm='202202',product='L_F',product_class='Commodity')})
        self.assertEqual(str(pd.Timestamp(p.deadline('l_F202202.DCE')).date()),'2021-12-21')

    def test_entry_on_or_after_deadline_is_rejected(self):
        p=self.policy()
        self.assertTrue(p.entry_allowed('IC202112.CFFEX','2021-12-15'))
        self.assertFalse(p.entry_allowed('IC202112.CFFEX','2021-12-16'))
        self.assertFalse(p.entry_allowed('IC202112.CFFEX','2021-12-20'))

    def test_calendar_gap_uses_sessions_not_calendar_day_arithmetic(self):
        calendar=[d for d in self.calendar() if d!='2021-12-16']
        p=self.policy(calendar=calendar)
        self.assertEqual(str(pd.Timestamp(p.deadline('IC202112.CFFEX')).date()),'2021-12-15')
        self.assertTrue(p.exit_due('IC202112.CFFEX','2021-12-14'))

    def test_deadline_position_is_a_hard_failure_until_real_close(self):
        p=self.policy()
        p.assert_flat_by_deadline({'IC202112.CFFEX':1},'2021-12-15')
        p.assert_flat_by_deadline({},'2021-12-16')
        for day in ['2021-12-16','2021-12-17','2022-01-04']:
            with self.subTest(day=day),self.assertRaises(RuntimeError):
                p.assert_flat_by_deadline({'IC202112.CFFEX':1},day)

    def test_hindsight_last_bar_does_not_change_deadline(self):
        common=dict(maturity_date='2021-12-17',contract_yyyymm='202112',product='IC',product_class='Index')
        early=self.policy({'IC202112.CFFEX':dict(common,last_bar_date='2021-11-01')})
        late=self.policy({'IC202112.CFFEX':dict(common,last_bar_date='2022-01-20')})
        self.assertEqual(early.deadline('IC202112.CFFEX'),late.deadline('IC202112.CFFEX'))

    def test_missing_maturity_or_calendar_support_fails_closed(self):
        self.assertIsNotNone(LifecyclePolicy,'lifecycle policy is required before replay')
        for metadata,calendar in [
            ({'IC202112.CFFEX':dict(contract_yyyymm='202112',product='IC',product_class='Index')},self.calendar()),
            ({'IC202112.CFFEX':dict(maturity_date='2021-12-17',contract_yyyymm='202112',product='IC',product_class='Index')},['2021-12-17']),
        ]:
            with self.subTest(metadata=metadata,calendar=calendar),self.assertRaises((ValueError,RuntimeError)):
                LifecyclePolicy(metadata,calendar).deadline('IC202112.CFFEX')


    def test_unknown_class_nonindex_index_code_or_missing_month_fails_closed(self):
        self.assertIsNotNone(LifecyclePolicy,'lifecycle policy is required before replay')
        base=dict(maturity_date='2021-12-17',contract_yyyymm='202112',
                  product='IC',product_class='Index')
        for change in [dict(product_class='Unknown'),dict(product='XYZ'),dict(contract_yyyymm='')]:
            with self.subTest(change=change),self.assertRaises((ValueError,RuntimeError)):
                LifecyclePolicy({'IC202112.CFFEX':dict(base,**change)},self.calendar()).deadline('IC202112.CFFEX')

    def test_government_uses_same_declared_nonindex_research_buffer(self):
        p=self.policy({'T202201.CFFEX':dict(maturity_date='2022-01-17',
            contract_yyyymm='202201',product='T',product_class='Government')})
        self.assertEqual(str(pd.Timestamp(p.deadline('T202201.CFFEX')).date()),'2021-12-30')

    def fifth_open(self,equity):
        symbols=['rb202205.SHFE','i202205.DCE','cu202205.SHFE','m202205.DCE','a202205.DCE']
        dt=datetime(2021,12,1)
        e=FullMarketDailyEngine({});e.datetime=dt
        class Fixture(StrategyTemplate):
            def on_init(self):pass
            def on_bars(self,bars):pass
        s=Fixture(e,'synthetic',symbols,{});e.strategy=s
        s.source_symbol_by_contract={vt:vt.split('202205')[0]+'.'+vt.split('.')[1] for vt in symbols}
        for vt in symbols[:-1]:s.pos_data[vt]=1
        s.max_concurrent_positions=candidate_overrides(Path('/tmp/unused-universe.csv'))['max_concurrent_positions']
        s.settled_balance=equity;s.estimated_equity=equity
        s.last_close_prices={vt:100 for vt in symbols[:-1]}
        s.stage830_broker_margin_multiplier=1
        s.stage830_projected_broker10_margin_to_equity_cap=1
        e.sizes={vt:10 for vt in symbols};e.slippages={vt:0 for vt in symbols};e.rates={vt:0 for vt in symbols}
        e.bars={vt:BarData(symbol=vt.split('.')[0],exchange=Exchange(vt.split('.')[1]),datetime=dt,
            open_price=100,high_price=100,low_price=100,close_price=100,volume=10,gateway_name='SYNTHETIC') for vt in symbols}
        e.history_data={(dt,vt):b for vt,b in e.bars.items()}
        e.research_metadata={vt:dict(size=10,margin_ratio=.1,fee_method='by_volume',fee_open=0,
            fee_close=0,fee_close_today=0,maturity_date='2022-05-16',contract_yyyymm='202205',product_class='Commodity') for vt in symbols}
        if LifecyclePolicy is not None:
            e.lifecycle_policy=LifecyclePolicy(e.research_metadata,pd.bdate_range('2021-11-01','2022-06-30').strftime('%Y-%m-%d').tolist())
        vt=symbols[-1]
        o=OrderData(symbol=vt.split('.')[0],exchange=Exchange.DCE,orderid='1',direction=Direction.LONG,
            offset=Offset.OPEN,volume=1,price=100,status=Status.SUBMITTING,datetime=datetime(2021,11,30),gateway_name='BACKTESTING')
        e.limit_orders={o.vt_orderid:o};e.active_limit_orders={o.vt_orderid:o}
        e.prepare_opening_risk(dt);e.cross_delayed_orders()
        return s.get_pos(vt),e.blocked_open_orders

    def test_more_than_four_actual_products_can_open_with_margin_available(self):
        pos,blocked=self.fifth_open(10000)
        self.assertEqual(pos,1,'fifth distinct product must not be blocked by an arbitrary count cap')
        self.assertEqual(blocked,[])

    def test_removing_count_limit_preserves_actual_margin_gate(self):
        pos,blocked=self.fifth_open(450)
        self.assertEqual(pos,0)
        self.assertEqual(blocked[-1]['reason'],'actual_broker_margin_cap')

    def test_natural_capacity_is_not_shrunk_by_environment_count_weight(self):
        s=object.__new__(FullMarketNoAIOneLot)
        s.product_symbols=[f'p{i}.DCE' for i in range(93)]
        s.max_concurrent_positions=candidate_overrides(Path('/tmp/unused-universe.csv'))['max_concurrent_positions']
        s.enable_portfolio_env_gate=True;s.current_env_gate_snapshot={'env_gate_weight':.2}
        self.assertEqual(s._effective_max_concurrent_positions('flat_entry'),93)


    def held_index_fixture(self):
        vt='IC202112.CFFEX';dt=datetime(2021,12,15)
        e=FullMarketDailyEngine({});e.datetime=dt
        e.sizes={vt:10};e.priceticks={vt:1};e.slippages={vt:0};e.rates={vt:0}
        metadata=dict(product_symbols=['IC.CFFEX'],source_symbol_by_contract={vt:'IC.CFFEX'})
        with patch('qmt_roll_portfolio_strategy.load_product_universe_symbols',return_value=set()), \
             patch('qmt_roll_portfolio_strategy.build_daily_mapping',return_value={}), \
             patch('qmt_roll_portfolio_strategy.build_contract_metadata',return_value=metadata):
            s=FullMarketNoAIOneLot(e,'synthetic',[vt],dict(capital_base=1000,
                enable_ai_product_pool_filter=False,enable_selection_pairwise_v2=False,
                enable_supply_demand_headwind_filter=False,risk_cluster_map='IC.CFFEX=IC'))
        e.strategy=s;s.trading=True;s.pos_data[vt]=1;s.equity_start_positions={vt:1}
        s.settled_balance=1000;s.estimated_equity=1000;s.last_close_prices={vt:100}
        s.equity_settlement_date='2021-12-14';s.total_margin_in_use=100
        s.cluster_margin_usage={'IC':100}
        s.states={'IC.CFFEX':ProductState(product_vt_symbol='IC.CFFEX',contract_vt_symbol=vt,
            direction='long',layers=[PositionLayer('base','long',1,100,95,100,100,
                'long_case1a','20211201',entry_price_synced=True)])}
        s.set_target(vt,1)
        e.research_metadata={vt:dict(size=10,margin_ratio=.1,fee_method='by_volume',fee_open=0,
            fee_close=0,fee_close_today=0,maturity_date='2021-12-17',contract_yyyymm='202112',
            product='IC',product_class='Index')}
        e.lifecycle_policy=self.policy(e.research_metadata)
        e.research_sessions=self.calendar()
        b=BarData(symbol='IC202112',exchange=Exchange.CFFEX,datetime=dt,
            open_price=100,high_price=100,low_price=100,close_price=100,volume=10,gateway_name='SYNTHETIC')
        e.bars={vt:b};e.history_data={(dt,vt):b}
        return e,s,vt,b

    def test_forced_exit_intent_is_real_pending_close_and_margin_stays_reserved(self):
        e,s,vt,b=self.held_index_fixture()
        apply=getattr(s,'apply_lifecycle_targets',None)
        if apply is not None:
            apply({vt:b});apply({vt:b})
        self.assertEqual(s.get_target(vt),0)
        self.assertEqual(s.get_pos(vt),1,'target zero is not a filled close')
        self.assertEqual(sum(x['volume'] for x in s.pending_close_lots[vt]),1)
        self.assertGreaterEqual(s.total_margin_in_use,100)
        self.assertGreaterEqual(s._estimate_margin_usage({vt:b}),100)
        self.assertFalse(e.trades)

    def test_exit_due_closes_at_next_real_open_before_deadline_assertion(self):
        e,s,vt,b=self.held_index_fixture()
        apply=getattr(s,'apply_lifecycle_targets',None)
        if apply is not None:apply({vt:b})
        s.rebalance_portfolio({vt:b})
        dt=datetime(2021,12,16);e.datetime=dt
        real=BarData(symbol='IC202112',exchange=Exchange.CFFEX,datetime=dt,
            open_price=105,high_price=106,low_price=104,close_price=105,volume=10,gateway_name='SYNTHETIC')
        e.bars={vt:real};e.history_data[(dt,vt)]=real
        e.prepare_opening_risk(dt);e.cross_delayed_orders()
        self.assertEqual(s.get_pos(vt),0)
        self.assertEqual(len(e.trades),1)
        self.assertEqual(next(iter(e.trades.values())).offset,Offset.CLOSE)
        check=getattr(e,'check_lifecycle_positions',None)
        if check is not None:check(dt,after_fills=True)

    def test_missing_deadline_quote_hard_fails_without_fake_close(self):
        e,s,vt,b=self.held_index_fixture()
        apply=getattr(s,'apply_lifecycle_targets',None)
        if apply is not None:apply({vt:b})
        s.rebalance_portfolio({vt:b})
        dt=datetime(2021,12,16);e.datetime=dt
        e.prepare_opening_risk(dt);e.cross_delayed_orders()
        self.assertEqual(s.get_pos(vt),1)
        self.assertFalse(e.trades)
        check=getattr(e,'check_lifecycle_positions',None)
        with self.assertRaises(RuntimeError):
            if check is not None:check(dt,after_fills=True)


    def test_cancelled_lifecycle_open_clears_only_unfilled_matching_intent(self):
        e,s,vt,b=self.held_index_fixture()
        s.pos_data[vt]=0;s.equity_start_positions={}
        state=s.states['IC.CFFEX'];state.layers[0].entry_price_synced=False
        s.pending_active_products={'IC.CFFEX'}
        o=OrderData(symbol='IC202112',exchange=Exchange.CFFEX,orderid='9',
            direction=Direction.LONG,offset=Offset.OPEN,volume=1,price=100,
            status=Status.SUBMITTING,datetime=datetime(2021,12,14),gateway_name='BACKTESTING')
        e.limit_orders={o.vt_orderid:o};e.active_limit_orders={o.vt_orderid:o}
        s.active_orderids.add(o.vt_orderid)
        apply=getattr(s,'apply_lifecycle_targets',None)
        if apply is not None:apply({vt:b})
        self.assertEqual(s.get_pos(vt),0)
        self.assertEqual(s.get_target(vt),0)
        self.assertNotIn(o.vt_orderid,e.active_limit_orders)
        self.assertEqual(state.contract_vt_symbol,'','cancelled intent is not a position')
        self.assertEqual(state.layers,[])
        self.assertNotIn('IC.CFFEX',s.pending_active_products)

    def test_cancel_open_helper_never_erases_an_actual_position(self):
        e,s,vt,b=self.held_index_fixture()
        state=s.states['IC.CFFEX'];original_layer=state.layers[0]
        o=OrderData(symbol='IC202112',exchange=Exchange.CFFEX,orderid='9',
            direction=Direction.LONG,offset=Offset.OPEN,volume=1,price=100,
            status=Status.SUBMITTING,datetime=datetime(2021,12,14),gateway_name='BACKTESTING')
        e.limit_orders={o.vt_orderid:o};e.active_limit_orders={o.vt_orderid:o}
        cancel=getattr(e,'cancel_lifecycle_open',None)
        if cancel is not None:cancel(o)
        else:
            s.set_target(vt,0);e.cancel_order(s,o.vt_orderid)
        self.assertEqual(s.get_pos(vt),1)
        self.assertEqual(state.contract_vt_symbol,vt)
        self.assertEqual(state.layers,[original_layer])


    def test_deadline_fill_gate_cancels_open_and_unfilled_state_before_mutation(self):
        e,s,vt,b=self.held_index_fixture()
        s.pos_data[vt]=0;s.equity_start_positions={};s.states['IC.CFFEX'].layers[0].entry_price_synced=False
        s.pending_active_products={'IC.CFFEX'}
        dt=datetime(2021,12,16);e.datetime=dt;b.datetime=dt
        e.bars={vt:b};e.history_data={(dt,vt):b}
        o=OrderData(symbol='IC202112',exchange=Exchange.CFFEX,orderid='9',direction=Direction.LONG,
            offset=Offset.OPEN,volume=1,price=100,status=Status.SUBMITTING,
            datetime=datetime(2021,12,15),gateway_name='BACKTESTING')
        e.limit_orders={o.vt_orderid:o};e.active_limit_orders={o.vt_orderid:o}
        s.active_orderids.add(o.vt_orderid)
        e.prepare_opening_risk(dt);e.cross_delayed_orders()
        self.assertEqual(s.get_pos(vt),0)
        self.assertFalse(e.trades)
        self.assertEqual(s.get_target(vt),0)
        self.assertNotIn(o.vt_orderid,e.active_limit_orders)
        self.assertEqual(s.states['IC.CFFEX'].layers,[])
        self.assertNotIn('IC.CFFEX',s.pending_active_products)


    def test_execution_only_signal_day_still_queues_real_lifecycle_close(self):
        e,s,vt,b=self.held_index_fixture()
        b.execution_only=True
        s.on_bars({vt:b})
        self.assertEqual(s.get_target(vt),0)
        self.assertEqual(s.get_pos(vt),1,'exit intent must not manufacture a fill')
        self.assertEqual(sum(x['volume'] for x in s.pending_close_lots[vt]),1)
        self.assertTrue(e.active_limit_orders,'quote-only batch must still dispatch lifecycle close')
        for order in e.active_limit_orders.values():
            self.assertEqual(order.vt_symbol,vt)
            self.assertEqual(order.offset,Offset.CLOSE)
            self.assertEqual(order.direction,Direction.SHORT)
            self.assertEqual(order.volume,1)
        self.assertGreaterEqual(s._estimate_margin_usage({vt:b}),100)
        self.assertFalse(e.trades)


    def test_quote_only_exit_dispatch_does_not_materialize_unheld_open_target(self):
        e,s,vt,b=self.held_index_fixture()
        b.execution_only=True
        other='IC202203.CFFEX'
        unheld=BarData(symbol='IC202203',exchange=Exchange.CFFEX,datetime=b.datetime,
            open_price=100,high_price=100,low_price=100,close_price=100,volume=10,gateway_name='SYNTHETIC')
        unheld.execution_only=True
        s.pos_data[other]=0;s.set_target(other,1)
        e.bars[other]=unheld
        s.on_bars({vt:b,other:unheld})
        self.assertTrue(e.active_limit_orders)
        self.assertTrue(all(o.vt_symbol==vt and o.offset==Offset.CLOSE for o in e.active_limit_orders.values()))
        self.assertEqual(s.get_pos(other),0)
        self.assertFalse(e.trades)


if __name__=='__main__':unittest.main()
