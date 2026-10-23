"""G planner边界：原19池固定、AM41容量、真实完成周21门与无策略构造器。"""
from pathlib import Path
from types import SimpleNamespace
import importlib.util,sys,unittest
import pandas as pd
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT),'/Users/mac/Documents/Codex/fian-handoff-20261014/vnpy_handoff_20261014/vendor',str(ROOT/'examples/portfolio_backtesting'),str(Path(__file__).parent)]
from stage008_signal_anchor_plan import ORIGINAL19,assert_original19,assert_g_setting,build_pure_reader,scan_raw_candidates

class PlanTests(unittest.TestCase):
    def test_original19_exact_match_required(self):
        expected=dict(universe_product_count=19,universe_products=sorted(ORIGINAL19))
        self.assertEqual(assert_original19(sorted(ORIGINAL19),expected),sorted(ORIGINAL19))
        changed=(ORIGINAL19-{'AP.CZCE'})|{'eb.DCE'}
        with self.assertRaisesRegex(ValueError,'original19'):assert_original19(sorted(changed),expected)
    def test_g_contract_capacity_is_41_not_21(self):
        setting=dict(ma_short=5,ma_mid=10,ma_long=20,research_exact_array_manager_size=41,capital_base=150000,
          enable_stage847_half_r_stop_retry=False,enable_stage827_intraday_c2_stop=False,enable_ai_product_pool_filter=False)
        assert_g_setting(setting)
        with self.assertRaisesRegex(ValueError,'capacity'):assert_g_setting(dict(setting,research_exact_array_manager_size=21))
        with self.assertRaisesRegex(ValueError,'disabled'):assert_g_setting(dict(setting,enable_ai_product_pool_filter=True))
    @unittest.skipUnless(importlib.util.find_spec('stage008_three_ma'),'G adapter not published yet')
    def test_actual_g_manager_scanner_opens_at_21_real_weeks(self):
        from vnpy.trader.utility import ArrayManager
        from stage008_three_ma import ThreeMaWeeklyArrayManager
        from weekly_adapter import completed_weeks
        dates=pd.bdate_range('2019-06-03',periods=22*5)
        calendar=[d.strftime('%Y-%m-%d') for d in dates]
        class Signals:
            parameters=['enabled'];enabled=False
            def __init__(self,*args,**kwargs):raise AssertionError('strategy constructor forbidden')
            def _build_history_df(self,am):return pd.DataFrame({'close':am.close_array})
            def _generate_signal(self,am,history):return dict(signal='long_case1a' if self.enabled else '')
        reader,_=build_pure_reader(Signals,{'enabled':True})
        am=ThreeMaWeeklyArrayManager(ArrayManager(41),completed_weeks(calendar))
        bars=[SimpleNamespace(datetime=d.to_pydatetime(),open_price=10.,high_price=12.,low_price=9.,close_price=11.,volume=100.,turnover=1000.,open_interest=1000.) for d in dates]
        rows=list(scan_raw_candidates('au2006.SHFE',bars,am,reader,{d:'au2006.SHFE' for d in calendar},calendar[0],calendar[-1]))
        self.assertEqual(am.size,41)
        self.assertEqual([r['observed_weeks'] for r in rows],[21,22])
        self.assertEqual(rows[0]['signal_date'],calendar[104])
        self.assertEqual(set(reader.__dict__),{'enabled'})

if __name__=='__main__':unittest.main()
