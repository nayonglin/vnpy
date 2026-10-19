"""Real runner MRO, raw weekly provider and saved native parameters, without financial replay."""
import json,unittest
from pathlib import Path
import pandas as pd
from stage050_weekly_main import WeeklyMainTrend
from stage051_weekly_long_candidate import WeeklyEntryAuthorization
import stage052_run_weekly_long as candidate

class IntegratedWeeklyRunnerTests(unittest.TestCase):
    def test_native_settings_are_identical_to_saved_baseline(self):
        saved=candidate.LINE/'outputs/run_20261019_native_budget_one_lot_v1'
        manifest=json.loads((saved/'manifest.json').read_text())
        contracts=pd.read_csv(saved/'contract_metadata.csv')
        settings=candidate.supply_settings(candidate.build_settings(candidate._metadata(contracts),candidate.LINE/'outputs/inputs/product_universe.csv'),'disabled-research')
        settings.update(enable_stage827_intraday_c2_stop=False,enable_stage847_half_r_stop_retry=False)
        self.assertEqual(candidate.safe(settings),manifest['parameters'])
    def fixture(self,falling=False):
        import test_stage041_open_risk as old
        e,s,vt,b,o,layer=old.RealEngineBudgetTests().fixture(110.)
        e.__class__=candidate.FullMarketDailyEngine;s.__class__=candidate.FeeStrategy
        e.weekly_execution_audit=[]
        weeks=pd.date_range(end='2021-12-10',periods=40,freq='W-FRI')
        prices=list(range(100,140))
        if falling:prices=list(reversed(prices))
        market=pd.DataFrame(dict(date=weeks,vt_symbol=vt,close=prices,volume=10.))
        mapping=pd.DataFrame(dict(date=weeks,continuous_symbol_vt='IC.CFFEX',main_contract_vt=vt,observation_date=weeks-pd.Timedelta(days=1)))
        e.weekly_main=WeeklyMainTrend(market,mapping,pd.bdate_range(weeks.min()-pd.Timedelta(days=4),'2021-12-17'))
        snap=e.weekly_main.lookup('IC.CFFEX','2021-12-14',phase='signal_close')
        layer.stage051_weekly_authorization=WeeklyEntryAuthorization(vt,'IC.CFFEX','long',layer.signal,'2021-12-14',json.dumps(snap,sort_keys=True))
        return e,s,vt
    def test_full_runner_raw_weekly_bull_fills_and_retains_budget_proof(self):
        e,s,vt=self.fixture();e.cross_delayed_orders()
        self.assertEqual(s.get_pos(vt),1)
        t=next(iter(e.trades.values()))
        self.assertEqual(t.stage041_entry_risk,100.)
        self.assertEqual(t.stage051_weekly_open_snapshot['week_last_session'],'2021-12-10')
        self.assertTrue(e.weekly_execution_audit[0]['filled'])
    def test_full_runner_raw_weekly_bear_cancels_without_cost_or_ghost(self):
        e,s,vt=self.fixture(True);e.cross_delayed_orders()
        self.assertFalse(e.trades);self.assertEqual(s.get_target(vt),0)
        self.assertFalse(s.pending_active_products);self.assertFalse(s.states['IC.CFFEX'].layers)

if __name__=='__main__':unittest.main()
