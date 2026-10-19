import importlib,json,unittest
from pathlib import Path
import pandas as pd
try:module=importlib.import_module('stage070_run_fractional_risk')
except ModuleNotFoundError as exc:
    if exc.name!='stage070_run_fractional_risk':raise
    module=importlib.import_module('stage060_run_contract_weekly_long')

class FractionalRunnerIntegration(unittest.TestCase):
    def test_only_fraction_and_max_lots_change_native_settings(self):
        baseline=module.LINE/'outputs/run_20261019_contract_weekly_long_v1'
        old=json.loads((baseline/'manifest.json').read_text())['parameters'];contracts=pd.read_csv(baseline/'contract_metadata.csv')
        settings=module.supply_settings(module.build_settings(module._metadata(contracts),module.LINE/'outputs/inputs/product_universe.csv'),'disabled-research')
        settings.update(enable_stage827_intraday_c2_stop=False,enable_stage847_half_r_stop_retry=False)
        changed={k:(old.get(k),v) for k,v in settings.items() if old.get(k)!=v}
        self.assertEqual(changed,{'max_position_size':(1,2147483647),'stage068_risk_fraction':(None,.005)})
        self.assertEqual(set(old)-set(settings),set())
    def test_actual_mro_removes_both_legacy_one_lot_guards(self):
        names={c.__name__ for c in module.FeeStrategy.__mro__}|{c.__name__ for c in module.FullMarketDailyEngine.__mro__}
        self.assertNotIn('NativeRiskBudgetSizingMixin',names);self.assertNotIn('OpeningRiskBudgetMixin',names)
        self.assertIn('FractionalRiskSizingMixin',names);self.assertIn('FractionalOpeningRiskMixin',names)
        self.assertIn('PendingCloseQuantityMixin',names)
    def fixture(self,price=110,direction='long',margin_ratio=.1):
        import test_stage041_open_risk as old
        from stage068_fractional_risk import FractionalSignalRiskReceipt
        from stage075_fractional_weekly import WeeklyEntryAuthorization
        import test_stage059_contract_weekly_candidate as weekly
        e,s,vt,b,o,layer=old.RealEngineBudgetTests().fixture(price,direction)
        e.__class__=module.FullMarketDailyEngine;s.__class__=module.FeeStrategy;e.weekly_execution_audit=[]
        e.weekly_contract=weekly.Provider(True,direction=='short')
        s.fixed_size=0;s.max_position_size=2147483647;s.min_position_size=1;s.stage068_risk_fraction=.005
        s.settled_balance=s.estimated_equity=1000000;s.equity_start_positions={}
        layer.volume=3;o.volume=3;s.set_target(vt,3 if direction=='long' else -3);s.entry_risk_diagnostics[0]['volume']=3
        layer.stage068_signal_risk_budget=FractionalSignalRiskReceipt('signal1',vt,'IC.CFFEX',direction,layer.signal,'2021-12-14','flat_entry',1000000,.005,5000,100,100,3)
        e.research_metadata[vt]['margin_ratio']=margin_ratio
        if direction=='long':layer.stage059_weekly_authorization=WeeklyEntryAuthorization(vt,'IC.CFFEX',direction,layer.signal,'2021-12-14',json.dumps(weekly.snapshot('IC.CFFEX','2021-12-14','signal_close',contract=vt)))
        e.prepare_opening_risk(e.datetime)
        return e,s,vt,b,o,layer
    def test_three_lot_real_fill_has_whole_entry_risk_and_exact_week_proof(self):
        e,s,vt,b,o,layer=self.fixture();e.cross_delayed_orders()
        self.assertEqual(s.get_pos(vt),3);self.assertEqual(len(e.trades),1)
        trade=next(iter(e.trades.values()));self.assertEqual(trade.volume,3)
        self.assertEqual(trade.stage068_entry_risk,300);self.assertEqual(trade.stage068_risk_per_contract,100)
        self.assertEqual(trade.stage068_budget,5000);self.assertTrue(trade.stage059_weekly_open_snapshot['allowed'])
    def test_actual_margin_gate_counts_three_lots_not_one(self):
        e,s,vt,b,o,layer=self.fixture(margin_ratio=200);e.cross_delayed_orders()
        self.assertFalse(e.trades);self.assertEqual(s.get_pos(vt),0);self.assertEqual(s.get_target(vt),0)
        self.assertTrue(any(x['reason']=='actual_broker_margin_cap' for x in e.blocked_open_orders))
    def test_total_gap_risk_rejects_entire_order_not_reduced_or_reissued(self):
        e,s,vt,b,o,layer=self.fixture(price=300);e.cross_delayed_orders()
        self.assertFalse(e.trades);self.assertEqual(s.get_target(vt),0);self.assertFalse(s.states['IC.CFFEX'].layers)
        self.assertIn('total_order_risk_exceeds',e.open_budget_audit[-1]['reason'])
    def test_short_three_lots_never_reads_weekly_provider(self):
        e,s,vt,b,o,layer=self.fixture(price=90,direction='short');e.cross_delayed_orders()
        self.assertEqual(s.get_pos(vt),-3);self.assertEqual(e.weekly_execution_audit,[])
    def test_small_real_bar_defers_whole_order_without_partial_fill_or_new_receipt(self):
        e,s,vt,b,o,layer=self.fixture();b.volume=2;receipt=layer.stage068_signal_risk_budget
        e.cross_delayed_orders()
        self.assertFalse(e.trades);self.assertEqual(s.get_pos(vt),0)
        self.assertIn(o.vt_orderid,e.active_limit_orders);self.assertIs(layer.stage068_signal_risk_budget,receipt)
        self.assertEqual(e.deferred_orders[-1]['volume'],3)
        b.volume=10;e.cross_delayed_orders()
        self.assertEqual(s.get_pos(vt),3);self.assertEqual(len(e.trades),1)
        self.assertEqual(next(iter(e.trades.values())).stage068_signal_snapshot['snapshot_id'],'signal1')

if __name__=='__main__':unittest.main()
