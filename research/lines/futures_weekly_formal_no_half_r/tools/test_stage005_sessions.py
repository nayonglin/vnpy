"""全市场研究首分钟规则：先于实现编写的边界/兼容性测试。"""
from pathlib import Path
import sys, unittest
from types import SimpleNamespace
sys.path[:0] = [str(Path(__file__).resolve().parents[4] / 'examples/portfolio_backtesting')]
import pandas as pd
import qmt_roll_intraday_execution as execution
from stage005_sessions import canonical_open_timestamp, session_minutes, install_open_anchor_adapter

class SessionTests(unittest.TestCase):
    def test_original_19_full_grid_unchanged(self):
        samples = ['AP201.CZCE','CF201.CZCE','FG201.CZCE','MA201.CZCE','OI201.CZCE','SA201.CZCE','SH201.CZCE','SM201.CZCE','jm2001.DCE','lh2001.DCE','lc2001.GFEX','si2001.GFEX','au2001.SHFE','cu2001.SHFE','fu2001.SHFE','hc2001.SHFE','rb2001.SHFE','ru2001.SHFE','sp2001.SHFE']
        for day, cal in [('2020-01-06',['2020-01-03','2020-01-06']),('2020-04-07',['2020-04-03','2020-04-07']),('2020-05-07',['2020-05-06','2020-05-07'])]:
            for symbol in samples:
                with self.subTest(symbol=symbol, day=day):
                    self.assertTrue(session_minutes(symbol,day,cal).equals(execution.session_minutes(symbol,day,cal)))
    def test_new_commodity_night_covid_and_holiday(self):
        cases = [('2020-01-06',['2020-01-03','2020-01-06'],'2020-01-03 21:00'),('2020-04-08',['2020-04-07','2020-04-08'],'2020-04-08 09:00'),('2020-10-09',['2020-09-30','2020-10-09'],'2020-10-09 09:00')]
        for day,cal,expected in cases:
            self.assertEqual(canonical_open_timestamp('al2012.SHFE',day,cal),pd.Timestamp(expected))
            self.assertEqual(len(session_minutes('al2012.SHFE',day,cal)),1)
    def test_cffex_historical_bond_change(self):
        self.assertEqual(str(canonical_open_timestamp('T2009.CFFEX','2020-07-17',['2020-07-16','2020-07-17'])),'2020-07-17 09:15:00')
        self.assertEqual(str(canonical_open_timestamp('T2009.CFFEX','2020-07-20',['2020-07-17','2020-07-20'])),'2020-07-20 09:30:00')
        self.assertEqual(str(canonical_open_timestamp('IF2007.CFFEX','2020-07-17',['2020-07-16','2020-07-17'])),'2020-07-17 09:30:00')
    def test_listing_day_does_not_get_previous_night(self):
        self.assertEqual(str(canonical_open_timestamp('PF105.CZCE','2020-10-12',['2020-10-09','2020-10-12'])),'2020-10-12 09:00:00')
        self.assertEqual(str(canonical_open_timestamp('PF105.CZCE','2020-10-13',['2020-10-12','2020-10-13'])),'2020-10-12 21:00:00')
        with self.assertRaisesRegex(ValueError,'before_listing'):
            canonical_open_timestamp('PF105.CZCE','2020-10-09',['2020-10-08','2020-10-09'])
    def test_new_day_only_products(self):
        for symbol in ['UR601.CZCE','lg2601.DCE','ps2601.GFEX','pt2606.GFEX','pd2606.GFEX','ec2601.INE']:
            self.assertEqual(str(canonical_open_timestamp(symbol,'2025-11-28',['2025-11-27','2025-11-28'])),'2025-11-28 09:00:00')
    def test_average_price_suffix_is_preserved(self):
        for symbol in ['l2601F.DCE','v2601F.DCE','pp2601F.DCE']:
            self.assertEqual(str(canonical_open_timestamp(symbol,'2025-10-29',['2025-10-28','2025-10-29'])),'2025-10-28 21:00:00')
            with self.assertRaisesRegex(ValueError,'before_listing'):
                canonical_open_timestamp(symbol,'2025-10-28',['2025-10-27','2025-10-28'])
    def test_unknown_wrong_exchange_and_missing_calendar_fail(self):
        for symbol in ['XYZ2601.SHFE','al2601.DCE','l_F2601.DCE','al.CZCE']:
            with self.assertRaises(ValueError): canonical_open_timestamp(symbol,'2026-10-22',['2026-10-21','2026-10-22'])
        with self.assertRaisesRegex(ValueError,'calendar_missing'):
            canonical_open_timestamp('al2612.SHFE','2026-10-22',['2026-10-21'])
    def test_install_rejects_intraday_and_prevents_new_product_scan(self):
        settings = dict(enable_stage847_half_r_stop_retry=False,enable_stage827_intraday_c2_stop=False,enable_ai_product_pool_filter=False)
        with self.assertRaisesRegex(ValueError,'disabled'):
            install_open_anchor_adapter(dict(settings, enable_stage827_intraday_c2_stop=True))
        original = execution.session_minutes
        restore = install_open_anchor_adapter(settings)
        try:
            self.assertEqual(len(execution.session_minutes('al2612.SHFE','2026-10-22',['2026-10-21','2026-10-22'])),1)
            with self.assertRaisesRegex(ValueError,'anchor_only'):
                execution.entry_session(SimpleNamespace(),SimpleNamespace(vt_symbol='al2612.SHFE'))
        finally: restore()
        self.assertIs(execution.session_minutes,original)

if __name__ == '__main__':unittest.main()
