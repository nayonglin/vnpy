from pathlib import Path
import sys
import unittest
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_stage249_prepare_replay as fixtures

class MergeTests(unittest.TestCase):
    def module(self):
        self.assertTrue(Path(__file__).with_name('stage249_merge_minutes.py').is_file(),'merge module required')
        import stage249_merge_minutes
        return stage249_merge_minutes

    def test_replace_only_requested_timestamps_retain_other_rows_and_columns(self):
        m=self.module();base=fixtures.Stage249Tests().bars();base['bar_id']=[40,41,42]
        base['tq_symbol']='SHFE.au2012';base['bar_date']='2020-06-06';base['minute_source']='original'
        patch=base.iloc[[1]].copy();patch.loc[patch.index[0],'volume']=99;patch['minute_source']='completed';patch['trading_day']='2020-06-08'
        merged,report=m.merge_frames(base,patch)
        self.assertEqual(merged.volume.tolist(),[1.,99.,3.]);self.assertEqual(merged.bar_id.tolist(),[40,41,42])
        self.assertEqual(list(merged.columns),list(base.columns));self.assertEqual(report['replaced_rows'],1)
        self.assertEqual(report['removed_timestamps'],0);self.assertEqual(report['changed_values']['volume'],1)

    def test_new_time_is_added_without_shrinking_old_timestamp_set(self):
        m=self.module();base=fixtures.Stage249Tests().bars().iloc[:1].copy();patch=fixtures.Stage249Tests().bars().iloc[1:].copy()
        merged,report=m.merge_frames(base,patch)
        self.assertEqual(len(merged),3);self.assertEqual(report['new_timestamps'],2);self.assertEqual(report['removed_timestamps'],0)

    def test_duplicate_base_or_patch_fails(self):
        m=self.module();frame=fixtures.Stage249Tests().bars()
        for base,patch in [(pd.concat([frame,frame.iloc[:1]]),frame),(frame,pd.concat([frame,frame.iloc[:1]]))]:
            with self.assertRaisesRegex(ValueError,'duplicate'):m.merge_frames(base,patch)

if __name__=='__main__':unittest.main()
