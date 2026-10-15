"""多shard分钟补丁来源闭环与缺口回归。"""
from pathlib import Path
import importlib.util
import json
import sys
import tempfile
import unittest
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parent))
from stage249_prepare_replay import save_patch,sha256
import test_stage249_prepare_replay as fixtures

class PatchManifestTests(unittest.TestCase):
    def module(self):
        path=Path(__file__).with_name('stage249_verify_patches.py')
        self.assertTrue(path.is_file(),'patch verifier must exist')
        import stage249_verify_patches
        return stage249_verify_patches

    def fixture(self,root):
        f=fixtures.Stage249Tests();frame=f.bars();raw=root/'raw.parquet'
        earlier=frame.iloc[:1].copy();earlier['bar_datetime']=pd.Timestamp('2020-06-05 23:59')
        later=frame.iloc[-1:].copy();later['bar_datetime']=pd.Timestamp('2020-06-06 02:29')
        pd.concat([earlier,frame,later],ignore_index=True).to_parquet(raw)
        source={'kind':'tqsdk_completed_snapshot','raw_path':str(raw),'source_sha256':sha256(raw),
            'snapshot_at':'2020-06-07T08:00:00','serial_bounds':{'au2012.SHFE':{
                'earliest':'2020-06-05 23:59:00','latest':'2020-06-06 02:29:00','rows':5}}}
        patch=save_patch(root/'shard/patches',[f.task()],frame,source)
        return f.task(),patch,raw

    def test_exact_requested_task_manifest_is_complete(self):
        m=self.module()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);task,_,_=self.fixture(root)
            report=m.audit_patches([task],root)
            self.assertEqual(report['status'],'complete');self.assertEqual(report['completed_segments'],1)
            self.assertEqual(report['rows'],3);self.assertEqual(report['errors'],[])

    def test_missing_task_is_partial(self):
        m=self.module()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);task,_,_=self.fixture(root);other={**task,'vt_symbol':'au2010.SHFE'}
            report=m.audit_patches([task,other],root)
            self.assertEqual(report['status'],'incomplete');self.assertEqual(report['missing_segments'],1)

    def test_raw_source_tamper_fails_even_when_patch_sha_passes(self):
        m=self.module()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);task,_,raw=self.fixture(root)
            with raw.open('ab') as handle:handle.write(b'tampered')
            report=m.audit_patches([task],root)
            self.assertEqual(report['status'],'failed')
            self.assertTrue(any('raw_sha256' in e for e in report['errors']))

if __name__=='__main__':unittest.main()
