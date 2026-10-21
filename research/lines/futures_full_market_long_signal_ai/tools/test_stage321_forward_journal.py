"""One clock/receipt group; synthetic metadata only, no market or finance."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


PATH = Path(__file__).with_name('stage321_forward_journal.py')
engine = None
if PATH.exists():
    spec = importlib.util.spec_from_file_location('tiny321', PATH)
    engine = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(engine)


class ClockJournalTest(unittest.TestCase):
    def test_forward_clock_and_immutable_reception_chain(self):
        self.assertIsNotNone(engine, 'new clock/journal behavior is missing')
        fields = dict(frozen_at='2026-10-20T02:00:00+08:00',
            source_completed_at='2026-10-20T15:00:00+08:00',
            received_at='2026-10-20T16:00:00+08:00',
            decision_sealed_at='2026-10-20T17:00:00+08:00',
            D_open_at='2026-10-20T21:00:00+08:00')
        gate = engine.evaluate_clock(**fields)
        self.assertEqual(gate['status'], 'timely_forward_decision')
        self.assertTrue(gate['forward_observation'])
        self.assertTrue(gate['timely_decision'])
        cases = [
            ({'frozen_at': None}, 'not_frozen'),
            ({'source_completed_at': '2026-10-19T15:00:00+08:00'}, 'historical_before_freeze'),
            ({'source_completed_at': fields['frozen_at']}, 'historical_before_freeze'),
            ({'source_completed_at': None}, 'completion_clock_unknown'),
            ({'D_open_at': None}, 'D_clock_unknown'),
            ({'received_at': None}, 'receipt_clock_unknown'),
            ({'decision_sealed_at': None}, 'decision_not_sealed'),
            ({'received_at': '2026-10-20T21:00:00+08:00',
              'decision_sealed_at': '2026-10-20T21:01:00+08:00'}, 'late_input'),
            ({'decision_sealed_at': '2026-10-20T21:00:00+08:00'}, 'late_decision'),
            ({'received_at': '2026-10-20T14:59:00+08:00'}, 'received_before_completion'),
        ]
        for changes, expected in cases:
            with self.subTest(expected=expected):
                result = engine.evaluate_clock(**dict(fields, **changes))
                self.assertEqual(result['status'], expected)
                self.assertFalse(result['timely_decision'])
        with self.assertRaisesRegex(ValueError, 'timezone'):
            engine.evaluate_clock(**dict(fields, received_at='2026-10-20T16:00:00'))
        with self.assertRaisesRegex(ValueError, 'before receipt'):
            engine.evaluate_clock(**dict(fields, decision_sealed_at='2026-10-20T15:59:00+08:00'))
        # Same instant in UTC; no natural-date/night-session approximation.
        utc = engine.evaluate_clock(**dict(fields, D_open_at='2026-10-20T13:00:00Z'))
        self.assertEqual(utc['status'], gate['status'])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            identity = {'policy': 'fixed52_synthetic', 'frozen_at': None}
            journal = engine.ForwardJournal(root, identity)
            original = {'source': 'synthetic', 'u_date': '2026-10-20', 'value': None,
                'status': 'unavailable', 'completion': fields['source_completed_at']}
            first = journal.append('input', original, key='source/u/v1')
            self.assertEqual(journal.append('input', original, key='source/u/v1'), first)
            self.assertEqual(len(journal.entries()), 1)
            changed = dict(original, value=12.5, status='revised')
            with self.assertRaisesRegex(ValueError, 'different content'):
                journal.append('input', changed, key='source/u/v1')
            second = journal.append('input', dict(changed, revises=first['entry_hash']), key='source/u/v2')
            self.assertEqual(second['previous_entry_hash'], first['entry_hash'])
            rows = engine.ForwardJournal(root, identity).entries()
            self.assertEqual(len(rows), 2)
            self.assertIsNone(rows[0]['payload']['value'])
            self.assertEqual(rows[1]['payload']['value'], 12.5)
            self.assertIsNotNone(first['recorded_at'])
            with self.assertRaisesRegex(ValueError, 'policy identity'):
                engine.ForwardJournal(root, dict(identity, frozen_at=fields['frozen_at']))
            with self.assertRaises(ValueError):
                journal.append('decision', {'unknown': float('nan')}, key='invalid')
            # Existing evidence is not silently repaired or overwritten.
            object_path = root / 'objects' / (first['payload_sha256'] + '.json')
            original_bytes = object_path.read_bytes()
            object_path.unlink()
            with self.assertRaisesRegex(ValueError, 'object'):
                journal.append('input', original, key='source/u/v1')
            self.assertFalse(object_path.exists())
            object_path.write_bytes(original_bytes)
            object_path.write_text(json.dumps({'corrupted': True}))
            with self.assertRaisesRegex(ValueError, 'object'):
                journal.entries()
        with tempfile.TemporaryDirectory() as temporary:
            journal = engine.ForwardJournal(temporary, {'policy': 'torn_synthetic'})
            journal.append('state', {'D': 1}, key='D/1')
            with (Path(temporary) / 'journal.jsonl').open('a') as stream:
                stream.write('{"torn":')
            with self.assertRaisesRegex(ValueError, 'index'):
                journal.entries()


if __name__ == '__main__':
    unittest.main()
