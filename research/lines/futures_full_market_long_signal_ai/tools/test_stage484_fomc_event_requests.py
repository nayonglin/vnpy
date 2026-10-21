"""Only four new Stage484 synthetic checks; no old suite or real input reads."""
import csv
import gzip
import importlib.util
import io
import numpy as np
import json
from pathlib import Path
import tempfile
import unittest

MODULE = Path(__file__).with_name('stage484_fomc_event_requests.py')


def implementation():
    spec = importlib.util.spec_from_file_location('stage484', MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Stage484NewChecks(unittest.TestCase):
    def test_two_dst_anchors_and_25_elapsed_utc_hours(self):
        mod = implementation()
        cal = ['2025-06-18', '2025-06-19', '2025-06-20', '2025-12-10', '2025-12-11', '2025-12-12']
        events = [{'start': '2025-06-18 14:00:00', 'Event': 'summer'}, {'start': '2025-12-10 14:00:00', 'Event': 'winter'}]
        rows = mod.event_clocks(events, cal, '2025-01-01', '2025-12-31')
        self.assertEqual(rows[0]['announcement_utc'], '2025-06-18T18:00:00+00:00')
        self.assertEqual(rows[1]['announcement_utc'], '2025-12-10T19:00:00+00:00')
        self.assertEqual(rows[0]['deadline_utc'], '2025-06-19T19:00:00+00:00')
        self.assertEqual(rows[1]['deadline_utc'], '2025-12-11T20:00:00+00:00')
        self.assertEqual([r['u_date'] for r in rows], ['2025-06-20', '2025-12-12'])
        self.assertEqual([r['pre_date'] for r in rows], ['2025-06-18', '2025-12-10'])
        self.assertTrue(all(r['decision_elapsed_hours'] >= 25 for r in rows))

    def test_same_day_distinct_events_keep_original_ordinals(self):
        mod = implementation()
        rows = mod.event_clocks([{'start': '2025-06-18 14:00:00', 'Event': 'A'}, {'start': '2025-06-18 14:30:00', 'Event': ''}], ['2025-06-18', '2025-06-19', '2025-06-20', '2025-06-23'], '2025-01-01', '2025-12-31')
        self.assertEqual(len(rows), 2)
        self.assertEqual([r['fomc_ordinal'] for r in rows], [0, 1])
        self.assertNotEqual(rows[0]['fomc_event_id'], rows[1]['fomc_event_id'])
        self.assertEqual(rows[0]['u_date'], rows[1]['u_date'])
        self.assertEqual(rows[1]['source_event'], '')

    def test_calendar_study_and_no_future_D_do_not_wrap(self):
        mod = implementation()
        buf = io.BytesIO()
        np.save(buf, np.array([20250618, 20250619, 20250620, 20250623], dtype=np.int64), allow_pickle=False)
        cal = mod.calendar_days(buf.getvalue())
        self.assertEqual(cal, ['2025-06-18', '2025-06-19', '2025-06-20', '2025-06-23'])
        events = [{'start': s, 'Event': ''} for s in ['2025-06-16 14:00:00', '2025-06-19 14:00:00', '2025-06-23 14:00:00']]
        rows = mod.event_clocks(events, cal, cal[0], '2025-06-23')
        self.assertEqual(rows[0]['status'], 'before_source_calendar')
        self.assertEqual(rows[0]['u_date'], '')
        before_study = mod.event_clocks([{'start': '2025-06-17 14:00:00'}], cal, '2025-06-20', '2025-06-23')
        self.assertEqual(before_study[0]['status'], 'u_before_study')
        self.assertEqual(rows[0]['pre_date'], '')
        self.assertEqual(rows[1]['u_date'], '2025-06-23')
        self.assertEqual(rows[1]['D_date'], '')
        self.assertEqual(rows[1]['D_status'], 'no_future_source_day')
        self.assertEqual(rows[1]['eligible'], 1)
        self.assertEqual(rows[2]['status'], 'no_u_in_source_calendar')
        self.assertEqual(rows[2]['u_date'], '')
        self.assertEqual(rows[2]['D_date'], '')

    def test_tiny_full_roster_nochild_and_missing_pre_support_retained(self):
        mod = implementation()
        fixture = json.loads((Path(__file__).parents[1] / 'outputs/stage484_fomc_event_requests/tiny_fixture.json').read_text())
        with tempfile.TemporaryDirectory() as tmp:
            summary = mod.build_requests(fixture['calendar'], fixture['mothers'], iter(fixture['actions']), fixture['events'], fixture['scope'], Path(tmp))
            def read(name):
                with gzip.open(Path(tmp) / name, 'rt', newline='') as stream:
                    return list(csv.DictReader(stream))
            mothers = read('all_event_mother_requests.csv.gz')
            children = read('all_event_child_requests.csv.gz')
            keys = read('unique_epoch_pre_date_requests.csv.gz')
            self.assertEqual(len(mothers), 6)
            self.assertEqual(len(children), 6)
            self.assertEqual(len(keys), 2)
            self.assertEqual(sum(r['child_count_original'] == '0' for r in mothers), 2)
            self.assertEqual(sum(r['pre_observed_any_epoch'] == '0' for r in children), 2)
            self.assertEqual(sum(r['u_action_eligible'] == '0' for r in children), 4)
            self.assertEqual({r['product_id'] for r in children}, {'a.X', 'a.X_F'})
            self.assertEqual(sorted(int(r['child_link_count']) for r in keys), [2, 4])
            self.assertEqual(summary['full_original_mother_rows'], 9)
            self.assertEqual(summary['full_original_action_rows'], 5)
            self.assertEqual(summary['ordinary_F_preserved'], True)
            self.assertEqual(summary['expanded_child_requests'], 6)
            self.assertEqual(len(summary['full_action_metadata_sha256']), 64)


if __name__ == '__main__':
    unittest.main(verbosity=2)
