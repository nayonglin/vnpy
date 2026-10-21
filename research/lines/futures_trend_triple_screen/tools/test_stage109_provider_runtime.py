"""One three-generation offline runtime regression; no SDK/API/credentials."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode=True
LINE=Path(__file__).resolve().parents[1]
TOOLS=LINE/'tools';ROOT=LINE.parents[2]
LAUNCHER=TOOLS/'stage109_provider_runtime_launcher.py'
BOOT=TOOLS/'stage109_provider_runtime'
OWNER=LINE/'outputs/stage087_off_data_scope/B_OFF/81ffc8f704ce4c5eb701e97e0397b12a/owner.json'
OWNER_SHA='ce61dcf3cbe0696cfbc12f1ebcf0f12436ee0dfb84662623e91fce36ec957efb'
ENDPOINTS=('TQ_AUTH_URL','TQ_MD_URL','TQ_INS_URL','TQ_TD_URL')


class ProviderRuntimeSelectionTest(unittest.TestCase):
    def test_three_generations_real_identity_and_fail_closed_inputs(self):
        env=os.environ.copy()
        for key in (*ENDPOINTS,'PYTHONPATH','STAGE109_MANIFEST','STAGE109_MANIFEST_SHA256'):env.pop(key,None)
        env['PYTHONDONTWRITEBYTECODE']='1'
        with tempfile.TemporaryDirectory(prefix='stage109_baseline_') as folder:
            # Real original initialization reproduces the wrong SDK metadata.
            code="""import sys,json
from pathlib import Path
from importlib import metadata
sys.path.insert(0,sys.argv[1])
import stage022_run_c0_qualified_wait as runtime
runtime.OUTPUT=Path(sys.argv[2])/'runtime'
runtime.configure_runtime(Path(sys.argv[2])/'shared')
print(json.dumps({'version':metadata.version('tqsdk'),'sdk_imported':'tqsdk'in sys.modules}))
"""
            baseline=subprocess.run([sys.executable,'-c',code,str(TOOLS),str(Path(folder).resolve())],
                cwd=ROOT,env=env,capture_output=True,text=True,timeout=30)
            self.assertEqual(baseline.returncode,0,baseline.stderr)
            original=json.loads(baseline.stdout.splitlines()[-1])
            self.assertEqual(original,dict(version='3.9.4',sdk_imported=False))
        self.assertTrue(LAUNCHER.is_file(),'real baseline is SDK3.9.4; dedicated selector is not implemented')
        command=[sys.executable,str(LAUNCHER),'--owner',str(OWNER),'--owner-sha256',OWNER_SHA,'--probe-only']
        result=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True,timeout=45)
        self.assertEqual(result.returncode,0,result.stderr)
        selected=json.loads(result.stdout.splitlines()[-1]);generations=selected['generations']
        self.assertEqual(len(generations),3)
        self.assertEqual(len({row['pid']for row in generations}),3)
        for index,row in enumerate(generations):
            self.assertEqual(row['generation'],index)
            self.assertEqual(row['sdk_version'],'3.10.2')
            self.assertTrue(row['numeric_runtime_is_frozen'])
            self.assertTrue(row['deps_sys_path_unchanged'])
            self.assertTrue(row['original_version_endpoint_guard_passed'])
            self.assertFalse(row['credentials_read'])
            self.assertFalse(row['sdk_imported'])
            self.assertEqual(row['network_calls'],0)
            self.assertEqual(row['sdk_package'],str(ROOT/'.py311/lib/python3.11/site-packages/tqsdk'))
            self.assertEqual(len(row['sdk_accepted_source_bindings']),5)
            self.assertEqual(set(row['numeric_modules']),{'numpy','pandas','scipy','sklearn','joblib'})
            for item in row['numeric_modules'].values():self.assertTrue(item['file'].startswith(row['frozen_site']+'/'))
            if index:self.assertEqual(row['ppid'],generations[index-1]['pid'])
        for key,value in [('TQ_AUTH_URL','invalid://offline-test')]:
            bad=env.copy();bad[key]=value
            rejected=subprocess.run(command,cwd=ROOT,env=bad,capture_output=True,text=True,timeout=10)
            self.assertNotEqual(rejected.returncode,0)
        wrong=command.copy();wrong[wrong.index('--owner-sha256')+1]='0'*64
        rejected=subprocess.run(wrong,cwd=ROOT,env=env,capture_output=True,text=True,timeout=10)
        self.assertNotEqual(rejected.returncode,0)
        # A startup exception must stop before the Python body, rather than be
        # swallowed by ordinary sitecustomize error handling.
        bad=env.copy();bad.update(PYTHONPATH=str(BOOT),STAGE109_MANIFEST=selected['manifest_path'],
            STAGE109_MANIFEST_SHA256=selected['manifest_sha256'],TQ_MD_URL='invalid://offline-test')
        rejected=subprocess.run([sys.executable,'-c',"print('main_must_not_run')"],cwd=ROOT,env=bad,
            capture_output=True,text=True,timeout=10)
        self.assertNotEqual(rejected.returncode,0)
        self.assertNotIn('main_must_not_run',rejected.stdout)
        self.assertIn('stage109_bootstrap_failed',rejected.stderr)
        evidence=LINE/'outputs/stage109_provider_runtime_selection'
        evidence.mkdir(parents=True,exist_ok=True)
        (evidence/'finite_test_evidence.json').write_text(json.dumps(dict(schema='stage109_finite_runtime_test_v1',
            baseline=original,selected=selected,startup_failure_returncode=rejected.returncode,
            provider_packets_created=0,network_calls=0,financial_runs=0,credentials_read=False),indent=2)+'\n')


if __name__=='__main__':unittest.main(verbosity=2)
