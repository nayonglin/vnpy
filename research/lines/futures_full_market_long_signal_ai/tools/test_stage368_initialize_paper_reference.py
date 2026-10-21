"""One bounded initialization fixture; no financial replay or actual account."""
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

SOURCE = Path(__file__).with_name('stage368_initialize_paper_reference.py')


class InitializationFixture(unittest.TestCase):
    def test_signed_empty_scenarios_without_market_or_cash_and_reject_reuse(self):
        # Catches importing a runner, executing cash, loading raw data, sharing
        # scenario state, unsigned initial state, mutable bindings or overwrite.
        self.assertTrue(SOURCE.exists(), 'bounded initializer is not implemented')
        spec = importlib.util.spec_from_file_location('fixture368', SOURCE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        original_load = np.load
        blocked = {'run_cash_account', 'load_market_bridge', 'load_all_inputs',
                   'load_native_once', 'execute', 'main', 'seal_u', 'advance_D'}

        def profile(frame, event, arg):
            if event == 'call' and frame.f_code.co_name in blocked:
                name = Path(frame.f_code.co_filename).name
                if name.startswith(('stage042_', 'stage070_', 'stage131_', 'stage322_')):
                    raise AssertionError('forbidden financial/data call: '+name)

        with tempfile.TemporaryDirectory(prefix='stage368_fixture_') as folder:
            folder = Path(folder)
            prepared = module.prepare(folder/'prepared')
            auth = json.loads(Path(prepared['authorization_template']['path']).read_text())
            self.assertIs(auth['authorized'], False)
            with self.assertRaisesRegex(ValueError, 'root authorization'):
                module.initialize(auth, folder/'unauthorized')
            auth.update(authorized=True, authorized_by='root')
            bundle = json.loads(Path(prepared['source_bundle']['path']).read_text())
            calendar_sha = bundle['frozen_inputs']['source_calendar']['sha256']

            def calendar_only(file, *args, **kwargs):
                if not isinstance(file, io.BytesIO):
                    raise AssertionError('only bound calendar BytesIO may use np.load')
                self.assertEqual(hashlib.sha256(file.getvalue()).hexdigest(), calendar_sha)
                return original_load(file, *args, **kwargs)

            old_profile = sys.getprofile()
            try:
                sys.setprofile(profile)
                with patch.object(sqlite3, 'connect', side_effect=AssertionError('SQL forbidden')):
                    with patch.object(np, 'load', side_effect=calendar_only):
                        result = module.initialize(auth, folder/'initialized')
            finally:
                sys.setprofile(old_profile)
            self.assertEqual(result['status'], 'initialized_inactive')
            self.assertFalse(result['active'])
            self.assertEqual(result['counts']['new_state_calls'], 2)
            self.assertEqual(result['counts']['new_cash'], 0)
            self.assertEqual(result['parameters']['start_u'], 5290)
            self.assertEqual(result['T0'], '2026-10-19T20:21:56.703789+00:00')
            self.assertGreater(result['T_init'], result['T0'])
            envelope = json.loads(Path(result['initialization_envelope']['path']).read_text())
            event = envelope['event']
            self.assertEqual(event['kind'], 'paper_state_initialized')
            self.assertEqual(result['T_init'], event['recorded_at'])
            object_file = folder/'initialized'/'model_journal'/'objects'/(event['payload_sha256']+'.json')
            payload = json.loads(object_file.read_text())
            policy_hash = event['policy_sha256']
            for scenario in ('base', 'stress'):
                state = payload['states'][scenario]
                self.assertEqual(state['scenario'], scenario)
                self.assertEqual(state['ledger']['initial'], 1000000.)
                self.assertEqual(state['phase'], 'awaiting_u')
                self.assertIsNone(state['last_u'])
                self.assertIsNone(state['last_D'])
                self.assertIsNone(state['sealed'])
                self.assertEqual(state['ledger']['positions'], {})
                self.assertEqual(state['pending'], [])
                self.assertEqual(state['caller_policy_sha256'], policy_hash)
                saved = json.loads(Path(payload['state_files'][scenario]['path']).read_text())
                self.assertEqual(saved['state'], state)
            self.assertNotEqual(payload['states']['base']['account_id'], payload['states']['stress']['account_id'])
            payload['states']['base']['ledger']['realized'] = 7
            self.assertEqual(payload['states']['stress']['ledger']['realized'], 0)
            self.assertNotIn('decision_proposal', (folder/'initialized'/'model_journal'/'journal.jsonl').read_text())
            self.assertEqual(envelope['reference']['freeze_event'], bundle['reference']['freeze_event'])
            self.assertEqual(set(envelope['policy_identity']), {'schema', 'policy', 'frozen_at',
                'model_content_sha256', 'scaler_content_sha256', 'source_sha256'})
            with self.assertRaises(FileExistsError):
                module.initialize(auth, folder/'initialized')
            bad = copy.deepcopy(auth)
            bad['source_bundle']['sha256'] = '0'*64
            with self.assertRaisesRegex(ValueError, 'binding'):
                module.initialize(bad, folder/'bad_binding')
            self.assertFalse((folder/'bad_binding').exists())


if __name__ == '__main__':
    unittest.main()
