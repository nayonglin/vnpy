"""Checkpoint identity and full-before-rolling guards; no engine runs."""
import json
from pathlib import Path
import tempfile
import unittest

try:
    import stage257_run_batch as runner
except ModuleNotFoundError:
    runner = None


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(runner)

    def test_checkpoint_requires_same_manifest_and_unchanged_artifacts(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d/'metrics.json').write_text('{"end_equity":150000}')
            (d/'stage257_account_provenance.json').write_text('{"account_id":"X"}')
            mark = dict(account_id='X',manifest_sha256='abc',returncode=0,
                        artifact_sha256={name:runner.sha(d/name) for name in ['metrics.json','stage257_account_provenance.json']})
            self.assertTrue(runner.valid_checkpoint(d, mark, 'X', 'abc'))
            self.assertFalse(runner.valid_checkpoint(d, mark, 'X', 'def'))
            (d/'metrics.json').write_text('{"end_equity":150001}')
            self.assertFalse(runner.valid_checkpoint(d, mark, 'X', 'abc'))

    def test_full_and_rolling_phases_partition_and_sort_controls_first(self):
        manifest = {'windows':[{'window_id':'F','group':'historical_full'}, {'window_id':'Y','group':'1y'}],
                    'accounts':{'F__R':{'window_id':'F','kind':'random_monthly'},
                                'Y__A':{'window_id':'Y','kind':'ai_fair'},
                                'F__A':{'window_id':'F','kind':'ai_fair'}}}
        self.assertEqual(runner.phase_ids(manifest,'full'),['F__A','F__R'])
        self.assertEqual(runner.phase_ids(manifest,'rolling'),['Y__A'])
        self.assertEqual(set(runner.phase_ids(manifest,'all')),set(manifest['accounts']))

    def test_audit_rejects_stale_manifest_or_failed_status(self):
        self.assertTrue(runner.valid_audit({'experiment_manifest_sha256':'x','status':'PASS_DIAGNOSTIC_GAPS'},'x'))
        self.assertFalse(runner.valid_audit({'experiment_manifest_sha256':'y','status':'PASS_DIAGNOSTIC_GAPS'},'x'))
        self.assertFalse(runner.valid_audit({'experiment_manifest_sha256':'x','status':'FAIL'},'x'))


if __name__=='__main__':unittest.main()
