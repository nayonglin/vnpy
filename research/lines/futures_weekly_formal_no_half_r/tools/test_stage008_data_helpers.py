"""G数据下载控制边界；临时合成raw/proof，不联网、不运行金融引擎。"""
from pathlib import Path
import sys,tempfile,unittest,json
from unittest.mock import patch
import pandas as pd
sys.path.insert(0,str(Path(__file__).parent))
from stage008_data_helpers import canonical_task,group_tasks,select_missing,publish_snapshot,error_task

class DataTests(unittest.TestCase):
    def setUp(self):self.calendar=['2026-10-21','2026-10-22']
    def test_unknown_or_non19_rejected_and_no_time_switch(self):
        t=canonical_task('au2612.SHFE','2026-10-22',self.calendar)
        self.assertEqual((t['natural_date'],t['start']),('2026-10-21','21:00'))
        with self.assertRaisesRegex(ValueError,'original19'):canonical_task('eb2612.DCE','2026-10-22',self.calendar)
        with self.assertRaisesRegex(ValueError,'non_anchor_failure'):error_task({'error':'REJECT_EXECUTION_ZERO_VOLUME:au2612.SHFE:2026-10-22'},self.calendar)
    def test_zero_existing_key_never_becomes_missing(self):
        task=canonical_task('au2612.SHFE','2026-10-22',self.calendar)
        key=(task['vt_symbol'],pd.Timestamp('2026-10-21 21:00'))
        self.assertEqual(select_missing([task],{key}),[])
        self.assertEqual(select_missing([task,task],set()),[task])
    def test_group_span_is_strictly_less_than_14_natural_days(self):
        tasks=[{'vt_symbol':'au2612.SHFE','natural_date':d,'start':'21:00'} for d in ['2026-01-01','2026-01-14','2026-01-15']]
        self.assertEqual([len(g) for g in group_tasks(tasks)],[2,1])
    def test_complete_proof_is_published_once_atomically_zero_volume_retained(self):
        task=canonical_task('au2612.SHFE','2026-10-22',self.calendar)
        moments=pd.to_datetime(['2026-10-21 20:59','2026-10-21 21:00','2026-10-21 21:01'])
        raw=pd.DataFrame([dict(vt_symbol='au2612.SHFE',bar_datetime=t,open=100.,high=101.,low=99.,close=100.,volume=0.,open_oi=1.,close_oi=1.) for t in moments])
        source=dict(kind='tqsdk_completed_snapshot',snapshot_at='2026-10-22 08:00',serial_bounds={'au2612.SHFE':dict(earliest=str(moments[0]),latest=str(moments[-1]),rows=3)},order_api_calls=0,cancel_api_calls=0)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);destination=root/'stage008_minute_patches/test'
            import stage008_data_helpers as h
            rename=h.os.rename
            def check(a,b):
                self.assertFalse(destination.exists());self.assertTrue(list(Path(a).glob('*_proof.json')));self.assertTrue((Path(a)/'result.json').is_file());return rename(a,b)
            with patch.object(h.os,'rename',side_effect=check):record=publish_snapshot([task],raw,source,destination,self.calendar,root)
            self.assertTrue(destination.is_dir());proof=json.loads(Path(record['patch']['proof']).read_text())
            self.assertTrue(Path(proof['source']['raw_path']).is_file())
            self.assertEqual(pd.read_parquet(record['patch']['parquet']).volume.tolist(),[0.])
            with self.assertRaisesRegex(ValueError,'immutable'):publish_snapshot([task],raw,source,destination,self.calendar,root)

if __name__=='__main__':unittest.main()
