"""Coverage counting and conservative universe boundaries, without accounts."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import numpy as np
import pandas as pd

try:import stage004_minute_coverage as module
except ImportError:module=None


class CoverageTests(unittest.TestCase):
    def setUp(self):self.assertIsNotNone(module,'Stage004 coverage audit is not implemented')

    def test_one_missing_minute_is_not_full_coverage(self):
        expected=np.arange(100,105,dtype=np.int64)
        result=module.coverage_counts(np.array([99,100,101,103,104,110]),expected)
        self.assertEqual(result['available_minutes'],4)
        self.assertEqual(result['missing_minutes'],1)
        self.assertTrue(result['anchor_present'])
        self.assertFalse(result['complete'])

    def test_vectorized_counts_match_small_exhaustive_enumeration(self):
        expected=np.arange(101,130,dtype=np.int64)
        for available in [[],[101],[100,101,105,110,129,130],list(range(90,140))]:
            result=module.coverage_counts(np.array(available,dtype=np.int64),expected)
            brute=sum(int(x)in set(available)for x in expected)
            self.assertEqual(result['available_minutes'],brute)
            self.assertEqual(result['anchor_present'],101 in available)

    def test_duplicate_keys_across_base_and_overlay_are_rejected(self):
        with TemporaryDirectory()as folder:
            paths=[Path(folder)/name for name in ['base.csv','overlay.csv']]
            for path in paths:path.write_text('vt_symbol,bar_datetime\nrb2010.SHFE,2020-05-15 21:00:00\n')
            with self.assertRaisesRegex(ValueError,'duplicate_available_minute_key'):module.index_minutes(paths)

    def test_old_main_beyond_adjacent_previous_is_in_upper_bound(self):
        calendar=pd.to_datetime(['2020-05-18','2020-05-19','2020-05-20'])
        mapping=pd.DataFrame(dict(date=calendar,continuous_symbol_vt=['rb.SHFE']*3,
            main_contract_vt=['rb2001.SHFE','rb2005.SHFE','rb2010.SHFE']))
        real=pd.DataFrame(dict(vt_symbol=['rb2001.SHFE'],trade_date=[calendar[0]]))
        req=module.build_requirements(mapping,real,calendar)
        row=module.classify_requirement(req['rb2001.SHFE'],2)
        self.assertTrue(row['ever_main_upper'])
        self.assertFalse(row['main_plus_previous'])
        self.assertEqual(row['mapping_role'],'earlier_prior_main')
        self.assertTrue(row['carry_risk'])

    def test_missing_real_bar_is_not_an_actionable_real_minute_gap(self):
        self.assertFalse(module.real_data_gap(dict(real_daily_present=False,missing_minutes=345)))
        self.assertTrue(module.real_data_gap(dict(real_daily_present=True,missing_minutes=1)))

    def test_friday_night_grid_belongs_to_monday(self):
        calendar=pd.to_datetime(['2020-05-15','2020-05-18'])
        grid=module.source_session_grid('rb.SHFE',1,calendar)
        self.assertEqual(len(grid),345)
        self.assertEqual(pd.Timestamp(grid[0]),pd.Timestamp('2020-05-15 21:00'))
        self.assertEqual(pd.Timestamp(grid[-1]),pd.Timestamp('2020-05-18 14:59'))


if __name__=='__main__':unittest.main()
