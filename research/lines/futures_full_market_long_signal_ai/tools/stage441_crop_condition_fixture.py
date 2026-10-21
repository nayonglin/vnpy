"""One synthetic fixture for frozen Stage441 clock and shared-support behavior."""
from datetime import datetime
import importlib
from pathlib import Path
import sys
import unittest

import numpy as np


class FrozenClockFixture(unittest.TestCase):
    def test_clock_latest_release_common_support_and_undefined_prices(self):
        script = Path(__file__).with_name('stage441_crop_condition_timing.py')
        self.assertTrue(script.exists(), 'Stage441 implementation is required')
        sys.path.insert(0, str(script.parent))
        m = importlib.import_module(script.stem)
        summer = m.availability_clock('2023-07-03')
        winter = m.availability_clock('2023-01-09')
        self.assertEqual(summer['availability_shanghai'], '2023-07-04T12:00:00+08:00')
        self.assertEqual(winter['availability_shanghai'], '2023-01-10T13:00:00+08:00')
        calendar = [{'u_index': i, 'u_date': day} for i, day in enumerate(
            ['2023-09-25', '2023-10-09', '2023-10-10'])]
        def event(key, release, q, source='known'):
            return dict(event_key=key, crop='Soybeans', body_release_date=release,
                        reference_week=None, q=q, source_state=source,
                        historical_first_seen='unknown', source_evidence={})
        projected = m.project_events([
            event('old', '2023-09-25', 2), event('new', '2023-10-02', -1),
            event('unknown', None, None, 'missing_release'),
            event('tail', '2023-10-09', 1)], calendar)
        by_key = {r['event_key']: r for r in projected}
        self.assertEqual(by_key['old']['projection_state'], 'superseded')
        self.assertEqual(by_key['old']['superseded_by'], 'new')
        self.assertEqual(by_key['new']['projection_state'], 'active')
        self.assertEqual(by_key['new']['u_date'], '2023-10-09')
        self.assertEqual(by_key['new']['D_date'], '2023-10-10')
        self.assertEqual(by_key['new']['D_open_lower_bound_shanghai'], '2023-10-09T21:00:00+08:00')
        self.assertGreater(datetime.fromisoformat(by_key['new']['D_open_lower_bound_shanghai']),
                           datetime.fromisoformat(by_key['new']['availability_shanghai']))
        self.assertTrue(by_key['new']['exact_session_time_unknown'])
        self.assertEqual(by_key['unknown']['projection_state'], 'missing_release')
        self.assertEqual(by_key['tail']['projection_state'], 'censored_no_D')
        self.assertTrue(all(r['historical_first_seen'] == 'unknown' for r in projected))
        # The latest report supersedes even when its source q is unknown.
        missing = m.project_events([event('old', '2023-09-25', 2),
                                    event('new', '2023-10-02', None, 'missing_GE')], calendar)
        self.assertEqual([r['event_key'] for r in missing if r['projection_state'] == 'active'], ['new'])
        self.assertIsNone(missing[1]['q'])
        summer_calendar = [{'u_index': i, 'u_date': day} for i, day in enumerate(
            ['2023-07-03', '2023-07-04', '2023-07-05'])]
        summer_event = m.project_events([event('summer', '2023-07-03', 1)], summer_calendar)[0]
        self.assertEqual(summer_event['u_date'], '2023-07-04')
        self.assertEqual(summer_event['D_open_lower_bound_shanghai'], '2023-07-04T21:00:00+08:00')
        self.assertNotEqual(summer_event['D_open_lower_bound_shanghai'], '2023-07-03T21:00:00+08:00')
        # Synthetic cache only, never a real price file.
        cache = {'E': (np.array([0, 1, 2]),
                       np.array([[100, 100, 100, 100, 1], [101, 102, 100, 102, 1],
                                 [103, 105, 102, 104, 1]], float), np.ones(3, bool))}
        priced = m.attach_timing([summer_event], {1: {'reference_epoch': 'E'}}, cache)[0]
        self.assertEqual(priced['timing_state'], 'known')
        self.assertAlmostEqual(priced['total'], priced['gap'] + priced['after_open'], places=12)
        no_D = {'E': (cache['E'][0][:2], cache['E'][1][:2], cache['E'][2][:2])}
        missing_price = m.attach_timing([summer_event], {1: {'reference_epoch': 'E'}}, no_D)[0]
        self.assertEqual(missing_price['timing_state'], 'missing_exact_day')
        self.assertIsNone(missing_price['after_open'])
        q = np.array([1, 2, 0, -1, 3, -2], float)
        own = np.array([.1, .3, -.2, .4, -.1, .2])
        after = np.array([.03, .01, -.01, -.02, .05, 0])
        gap = np.array([.01, -.01, .02, -.02, .01, -.01])
        rows = np.column_stack([q, own, gap, after, gap + after])
        with_missing = np.vstack([rows, [100, 100, np.nan, 999, 999]])
        stats = m.statistics(with_missing)
        self.assertEqual(stats['joint_count'], 6)
        self.assertEqual(stats['q_worsening_joint'], 3)
        self.assertEqual(stats['q_nonworsening_joint'], 3)
        self.assertAlmostEqual(stats['after_open_worsening_minus_nonworsening_mean'], .04)
        self.assertAlmostEqual(stats['q_own_u_correlation'], m.corr(q, own))
        self.assertEqual(stats, m.statistics(rows) | {'nonjoint_calendar_dates': 1})
        zero_after = rows.copy(); zero_after[:, 3] = 0
        self.assertIsNone(m.statistics(zero_after)['after_open_correlation'])
        self.assertIsNone(m.statistics(zero_after)['after_open_partial_correlation'])
        zero_own = rows.copy(); zero_own[:, 1] = 0
        self.assertIsNone(m.statistics(zero_own)['after_open_partial_correlation'])
        grid = m.calendar_matrix(calendar, projected)
        self.assertEqual(grid.shape, (3, 5))
        self.assertTrue(np.isnan(grid[0]).all())
        self.assertEqual(grid[1, 0], -1)
        self.assertTrue(np.isnan(grid[2, 1:]).all())
        self.assertTrue(hasattr(m, 'source_events'), 'explicit 438 source adapter is required')
        raw = dict(crop='Soybeans', metadata_release_date='2023-07-03',
                   body_release={'status': 'known', 'body_release_date': '2023-07-03'},
                   reference_week_date='2023-07-02', current={'status': 'known', 'good_plus_excellent': 55},
                   source={'path': 'synthetic_only', 'bytes': 1, 'sha256': 'a'*64},
                   adjacent_change={'status': 'known', 'value_pp': -2, 'previous_original_GE': 57,
                                    'previous_metadata_release_date': '2023-06-26',
                                    'previous_reference_week_date': '2023-06-25',
                                    'previous_source': {'path': 'synthetic_previous'}, 'reference_gap_days': 7,
                                    'same_report_previous_week_used_as_original': False},
                   historical_first_seen='unknown', unknown_reasons=[])
        converted = m.source_events([raw])[0]
        self.assertEqual(converted['q'], 2)
        self.assertEqual(converted['source_state'], 'known')
        self.assertEqual(converted['source_evidence'], raw)
        self.assertEqual(m.BOOTSTRAP, {'resamples': 2000, 'block_global_trade_dates': 252, 'seed': 20261020})


if __name__ == '__main__':
    unittest.main()
