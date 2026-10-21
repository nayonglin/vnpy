import importlib.util
import pathlib
import types
import unittest

PATH = pathlib.Path(__file__).with_name('stage116_source_recovery.py')
if PATH.exists():
    spec = importlib.util.spec_from_file_location('recovery116', PATH)
    recovery = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(recovery)
else:
    recovery = types.SimpleNamespace()


class RecoveryPlanTest(unittest.TestCase):
    def test_completed_and_interrupted_are_never_requeued(self):
        self.assertTrue(callable(getattr(recovery, 'partition_dates', None)), 'recovery planner missing')
        p = recovery.partition_dates(['1', '2', '3', '4'], ['1', '2'], {'1': {'date': '1'}}, set(), [])
        self.assertEqual(p['remaining'], ['3', '4'])
        self.assertEqual(p['interrupted'], ['2'])
        self.assertEqual(p['completed'], ['1'])

    def test_orphan_raw_is_not_redownloaded(self):
        self.assertTrue(callable(getattr(recovery, 'partition_dates', None)), 'recovery planner missing')
        with self.assertRaisesRegex(AssertionError, 'orphan raw'):
            recovery.partition_dates(['1', '2'], ['1'], {}, {'2'}, [])

    def test_duplicate_started_or_unstarted_completed_rejected(self):
        self.assertTrue(callable(getattr(recovery, 'partition_dates', None)), 'recovery planner missing')
        with self.assertRaisesRegex(AssertionError, 'duplicate'):
            recovery.partition_dates(['1'], ['1', '1'], {}, set(), [])
        with self.assertRaisesRegex(AssertionError, 'unstarted'):
            recovery.partition_dates(['1'], [], {'1': {'date': '1'}}, set(), [])


if __name__ == '__main__':
    unittest.main()
