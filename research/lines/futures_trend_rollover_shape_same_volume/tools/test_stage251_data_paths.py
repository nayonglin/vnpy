"""Stage251 actual-path contracts; literal expected grids catch calendar widening."""
import importlib
import importlib.util
from pathlib import Path
import tempfile
import unittest


class ActualPathTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.find_spec('stage251_data_paths')
        self.assertIsNotNone(spec, 'Stage251 actual-path adapter must exist')
        self.mod = importlib.import_module('stage251_data_paths')
        self.calendar = ['2025-12-04', '2025-12-05', '2025-12-08', '2025-12-09']
        helper = Path(__file__).resolve().parents[4] / 'examples/portfolio_backtesting/qmt_roll_intraday_execution.py'
        self.session = self.mod.load_session_helper(helper)

    def anchor(self, symbol='au2602.SHFE', day='2025-12-08', start='2025-12-05T21:00:00'):
        return {'vt_symbol': symbol, 'trading_date': day, 'expected_start': start}

    def test_empty_disabled_entry_keeps_real_first_minute_anchor(self):
        plan = self.mod.build_tasks([], [self.anchor()], self.calendar, self.session, allow_empty_entry=True)
        self.assertEqual(plan['entry_tasks'], [])
        self.assertEqual(plan['anchor_tasks'], [{'vt_symbol':'au2602.SHFE', 'trading_day':'2025-12-08', 'natural_date':'2025-12-05', 'start':'21:00', 'end_exclusive':'21:01', 'session':'night'}])

    def test_unexpected_empty_entry_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'empty_entry'):
            self.mod.build_tasks([], [self.anchor()], self.calendar, self.session)

    def test_weekend_suffix_keeps_saturday_early_hours_and_only_target_day_session(self):
        entry = {'vt_symbol':'au2602.SHFE','trading_date':'2025-12-08','requested_start':'2025-12-06T00:00:00','expected_bar_count':'375'}
        plan = self.mod.build_tasks([entry], [], self.calendar, self.session)
        observed = [(t['natural_date'],t['start'],t['end_exclusive']) for t in plan['entry_tasks']]
        self.assertEqual(observed, [('2025-12-06','00:00','02:30'),('2025-12-08','09:00','10:15'),('2025-12-08','10:30','11:30'),('2025-12-08','13:30','15:00')])
        self.assertEqual(plan['entry_tasks'][0]['session'], 'early')

    def test_wrong_entry_count_cannot_silently_expand_data_request(self):
        entry = {'vt_symbol':'au2602.SHFE','trading_date':'2025-12-08','requested_start':'2025-12-06T00:00:00','expected_bar_count':'225'}
        with self.assertRaisesRegex(ValueError, 'entry_count'):
            self.mod.build_tasks([entry], [], self.calendar, self.session)

    def test_wrong_anchor_clock_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'anchor_start'):
            self.mod.build_tasks([], [self.anchor(start='2025-12-08T09:00:00')], self.calendar, self.session, allow_empty_entry=True)

    def test_anchor_timezone_and_duplicates_do_not_duplicate_downloads(self):
        plan = self.mod.build_tasks([], [self.anchor(), self.anchor(start='2025-12-05T13:00:00Z')], self.calendar, self.session, allow_empty_entry=True)
        self.assertEqual(len(plan['anchor_tasks']), 1)

    def test_entry_and_anchor_union_requests_each_minute_once(self):
        task = {'vt_symbol':'SM601.CZCE','trading_day':'2025-12-08','natural_date':'2025-12-08','start':'09:00','end_exclusive':'09:03','session':'day'}
        single = {**task,'start':'09:01','end_exclusive':'09:02'}
        self.assertEqual(self.mod.union_tasks([task,single]), [task])

    def test_empty_source_validation_is_explicit_and_hash_bound(self):
        with tempfile.TemporaryDirectory() as folder:
            cache=Path(folder)/'cache.csv';cache.write_text('vt_symbol,bar_datetime\n')
            report=self.mod.validate_optional(cache,[],Path(folder)/'unused',[])
            self.assertEqual(report['status'],'complete')
            self.assertEqual(report['segments'],0)
            self.assertEqual(report['cache_sha256'],self.mod.sha256(cache))
            self.assertEqual(report['empty_reason'],'no_actual_requests')

    def test_blank_csv_only_allowed_for_explicitly_empty_entry(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'entry.csv';path.write_text('\n')
            self.assertEqual(self.mod.read_request_rows(path,{'vt_symbol'},allow_empty=True),[])
            with self.assertRaisesRegex(ValueError,'columns'):
                self.mod.read_request_rows(path,{'vt_symbol'})


if __name__ == '__main__':
    unittest.main()
