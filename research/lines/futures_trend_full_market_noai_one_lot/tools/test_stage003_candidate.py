import importlib
from pathlib import Path
import sys
import unittest

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))

class CandidateContract(unittest.TestCase):
    def test_fixed_policy_and_all_short_cases(self):
        self.assertTrue((HERE/'stage003_candidate.py').exists(), 'missing isolated candidate implementation')
        c=importlib.import_module('stage003_candidate')
        setting=c.candidate_overrides(Path('/tmp/universe.csv'))
        for key in ['enable_ai_product_pool_filter','enable_selection_pairwise_v2','enable_selection_pairwise_v2_catastrophic_veto','enable_selection_pairwise_v2_catastrophic_hard_filter','enable_selection_pairwise_v2_volume_tilt','enable_add_position','enable_donchian_add_position','enable_post_entry_quality_add']:
            self.assertFalse(setting[key],key)
        self.assertEqual(setting['fixed_size'],1)
        self.assertEqual(setting['max_position_size'],1)
        self.assertEqual(setting['account_capital'],1000000)
        self.assertEqual(setting['c3_capital'],1000000)
        self.assertTrue(setting['enable_long_signal_range_atr_filter'])
        self.assertTrue(setting['enable_short_signal_range_atr_filter'])
        self.assertEqual(setting['rollover_delay_trading_days'],5)
        self.assertTrue(setting['enable_stage847_half_r_stop_retry'])
        self.assertTrue(setting['stage827_require_complete_minutes'])
        strategy=object.__new__(c.FullMarketNoAIOneLot)
        for signal in ['short_case1a','short_case2','short_case3']:
            self.assertTrue(strategy._can_open_short_signal(signal),signal)
        for signal in ['', 'long_case1a','short_case_unknown']:
            self.assertFalse(strategy._can_open_short_signal(signal),signal)

    def test_fixed_and_value_fees_are_not_silently_dropped(self):
        c=importlib.import_module('stage003_candidate')
        self.assertTrue(hasattr(c,'research_fee'),'missing per-lot fee calculation')
        fixed=dict(fee_method='by_volume',fee_open=2,fee_close=3,fee_close_today=5,size=10)
        value=dict(fee_method='by_money',fee_open=0.0001,fee_close=0.0002,fee_close_today=0.0003,size=10)
        self.assertEqual(c.research_fee(fixed,price=1000,volume=1,offset='open',same_day=False),2)
        self.assertEqual(c.research_fee(fixed,price=1000,volume=1,offset='close',same_day=True),5)
        self.assertEqual(c.research_fee(value,price=1000,volume=1,offset='open',same_day=False),1)
        self.assertAlmostEqual(c.research_fee(value,price=1000,volume=1,offset='close',same_day=False),2)

    def test_missing_real_bar_defers_order_instead_of_stale_fill(self):
        self.assertTrue((HERE/'stage004_run.py').exists(),'missing clean execution adapter')
        from stage004_run import FullMarketDailyEngine
        from types import SimpleNamespace
        from datetime import datetime
        engine=FullMarketDailyEngine({})
        engine.datetime=datetime(2020,1,3)
        order=SimpleNamespace(vt_symbol='rb202005.SHFE',vt_orderid='test.1')
        engine.active_limit_orders={'test.1':order}
        engine.bars={'rb202005.SHFE':SimpleNamespace(open_price=3500,volume=0)}
        engine.history_data={}
        engine.cross_delayed_orders()
        self.assertEqual(list(engine.active_limit_orders),['test.1'])
        self.assertEqual(len(engine.deferred_orders),1)
        self.assertFalse(engine.trades)

    def test_night_fill_is_charged_to_trading_day(self):
        import stage004_run as run
        from types import SimpleNamespace
        from datetime import datetime,date
        self.assertTrue(hasattr(run,'accounting_date'),'missing trading-day fee binding')
        friday=SimpleNamespace(datetime=datetime(2020,1,3,21,0),trading_date=date(2020,1,6))
        self.assertEqual(run.accounting_date(friday),date(2020,1,6))
        monday=SimpleNamespace(datetime=datetime(2020,1,6,9,0))
        self.assertEqual(run.accounting_date(monday),date(2020,1,6))

    def test_missing_supply_input_never_silently_disables_filter(self):
        import stage004_run as run
        self.assertTrue(hasattr(run,'supply_settings'),'missing explicit external-input gate')
        s=dict(enable_supply_demand_headwind_filter=True,supply_demand_signal_path='/missing/frozen_supply.csv')
        with self.assertRaisesRegex(ValueError,'missing_frozen_supply'):
            run.supply_settings(s,'require-frozen')
        changed=run.supply_settings(s,'disabled-research')
        self.assertFalse(changed['enable_supply_demand_headwind_filter'])
        self.assertTrue(s['enable_supply_demand_headwind_filter'])

    def test_missing_old_bar_does_not_erase_actual_position_or_concurrency(self):
        from stage003_candidate import FullMarketNoAIOneLot
        from types import SimpleNamespace
        strategy=object.__new__(FullMarketNoAIOneLot)
        old,new='rb201905.SHFE','rb201910.SHFE'
        strategy.source_symbol_by_contract={old:'rb.SHFE',new:'rb.SHFE'}
        strategy.pos_data={old:1,new:0}
        state=SimpleNamespace(product_vt_symbol='rb.SHFE',contract_vt_symbol=new)
        strategy.states={'rb.SHFE':state};strategy.pending_active_products=set()
        actual,qty,bar=strategy._resolve_actual_position(state,new,{new:SimpleNamespace()})
        self.assertEqual((actual,qty,bar),(old,1,None))
        self.assertEqual(strategy._count_active_positions(),1)

    def test_old_missing_close_blocks_new_contract_open(self):
        from stage004_run import FullMarketDailyEngine
        from vnpy_portfoliostrategy.template import StrategyTemplate
        from vnpy.trader.object import BarData,OrderData
        from vnpy.trader.constant import Exchange,Direction,Offset,Status
        from datetime import datetime
        old,new='rb201905.SHFE','rb201910.SHFE'
        e=FullMarketDailyEngine({});e.datetime=datetime(2019,4,3)
        class FixtureStrategy(StrategyTemplate):
            def on_init(self):pass
            def on_bars(self,bars):pass
        s=FixtureStrategy(e,'fixture',[old,new],{})
        s.source_symbol_by_contract={old:'rb.SHFE',new:'rb.SHFE'}
        s.pos_data[old]=1;e.strategy=s
        e.bars={new:BarData(symbol='rb201910',exchange=Exchange.SHFE,datetime=e.datetime,open_price=3500,high_price=3510,low_price=3490,close_price=3500,volume=10,gateway_name='fixture')}
        e.history_data={(e.datetime,new):e.bars[new]}
        e.sizes={old:10,new:10};e.rates={old:0,new:0};e.slippages={old:1,new:1}
        order=OrderData(symbol='rb201910',exchange=Exchange.SHFE,orderid='1',direction=Direction.LONG,offset=Offset.OPEN,volume=1,price=3500,status=Status.SUBMITTING,datetime=datetime(2019,4,2),gateway_name='BACKTESTING')
        e.active_limit_orders={order.vt_orderid:order}
        e.cross_delayed_orders()
        self.assertEqual(s.get_pos(old),1)
        self.assertEqual(s.get_pos(new),0)
        self.assertFalse(e.trades)

    def test_missing_bar_position_still_reserves_total_and_cluster_margin(self):
        from stage003_candidate import FullMarketNoAIOneLot
        from types import SimpleNamespace
        strategy=object.__new__(FullMarketNoAIOneLot)
        vt='rb201905.SHFE'
        strategy.pos_data={vt:1};strategy.states={}
        strategy.source_symbol_by_contract={vt:'rb.SHFE'}
        strategy.strategy_engine=SimpleNamespace(bars={vt:SimpleNamespace(close_price=3500)},sizes={vt:10},get_size=lambda strategy,symbol:10)
        strategy.margin_ratio_overrides=f'{vt}=0.1';strategy.risk_cluster_map='rb.SHFE=ferrous'
        self.assertEqual(strategy._estimate_margin_usage({}),3500)
        self.assertEqual(strategy._estimate_margin_usage_by_cluster({}),{'ferrous':3500})
        strategy.strategy_engine.bars={}
        with self.assertRaisesRegex(RuntimeError,'margin_unknown'):
            strategy._estimate_margin_usage({})

if __name__=='__main__': unittest.main()
