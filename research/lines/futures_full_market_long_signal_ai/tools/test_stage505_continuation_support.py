"""Stage505 five value-bearing clock fixtures; no historical payload I/O."""
import importlib.util
from pathlib import Path
import sys
import unittest

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
spec=importlib.util.spec_from_file_location('s505',HERE/'stage505_continuation_support.py')
s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)

class ContinuationClockTests(unittest.TestCase):
    def setUp(self):
        self.cal=['2019-01-28','2019-01-29','2019-01-30','2019-01-31','2019-02-01','2019-02-11','2019-02-12','2019-02-13']
    def row(self,e=1,x=5,**updates):
        r=dict(sequence_index='0',action_id='a',mother_sequence_index='0',mother_event_id='m',
          product_id='SHFE.X',family_id='SHFE.X',reference_epoch='SHFE.X.201904',anchor_epoch='SHFE.X.201904',
          u_date=self.cal[e-1],u_index=str(e-1),D_index=str(e),u_action_eligible='1',filled='1',
          participation_state='filled',label_state='closed_complete_bar_model',entry_index=str(e),entry_date=self.cal[e],
          exit_index=str(x),exit_date=self.cal[x],label_known_date=self.cal[x],label_known_phase='after_all_source_close',
          family_hash_group=str(s.family_group('SHFE.X')),c2020_state='closed',c2023_state='closed')
        r.update(updates);return r
    def test_same_and_next_day_terminal_do_not_create_strict_support(self):
        p=s.parse_metadata(self.row(e=1,x=1),self.cal)
        self.assertEqual(s.path_interval(p,self.cal)['strict_count'],0)
        self.assertEqual(s.path_interval(p,self.cal)['ambiguous_terminal_day_count'],0)
        p=s.parse_metadata(self.row(e=1,x=2),self.cal)
        z=s.path_interval(p,self.cal)
        self.assertEqual(z['strict_count'],0)
        self.assertEqual(z['ambiguous_terminal_day_count'],1)
        p=s.parse_metadata(self.row(e=1,x=5),self.cal)
        z=s.path_interval(p,self.cal)
        self.assertEqual((z['strict_start'],z['strict_end'],z['strict_count']),(1,3,3))
    def test_K_and_cutoff_equality_and_family_complement(self):
        p=s.parse_metadata(self.row(e=1,x=5,reference_epoch='SHFE.X.201903'),self.cal)
        z=s.path_interval(p,self.cal)
        self.assertEqual(z['K_index'],4)
        self.assertEqual((z['strict_start'],z['strict_end'],z['strict_count']),(1,2,2))
        self.assertEqual(z['ambiguous_terminal_day_count'],0)
        self.assertTrue(s.mature_for(p,'2020-01-01'))
        self.assertFalse(s.mature_for(p,p['label_known_date']))
        self.assertTrue(s.in_training_family('main',p['family_hash_group']))
        self.assertFalse(s.in_training_family('holdout_'+str(p['family_hash_group']),p['family_hash_group']))
        self.assertTrue(s.in_training_family('holdout_'+str(1-p['family_hash_group']),p['family_hash_group']))
    def test_overlap_union_does_not_count_cohorts_independently(self):
        a=s.UnionAccumulator(self.cal)
        a.add('F',1,3);a.add('F',2,4);a.add('G',2,3)
        z=a.result()
        self.assertEqual(z['opportunity_rows_upper'],8)
        self.assertEqual(z['source_day_union'],4)
        self.assertEqual(z['family_day_union'],6)
        self.assertEqual(z['families_with_strict_prefix'],2)
        self.assertEqual(z['age_counts'],[3,3,2])
    def test_unknown_and_future_are_isolated_not_zeros(self):
        r=self.row();r.update(label_state='path_or_execution_unknown',exit_index='',exit_date='',label_known_date='',label_known_phase='',c2020_state='held_missing',c2023_state='held_missing')
        p=s.parse_metadata(r,self.cal)
        self.assertFalse(s.mature_for(p,'2020-01-01'))
        self.assertIsNone(s.path_interval(p,self.cal))
        p=s.parse_metadata(self.row(),self.cal)
        self.assertFalse(s.mature_for(p,p['u_date']))
        with self.assertRaises(ValueError):s.parse_metadata(self.row(family_hash_group=str(1-s.family_group('SHFE.X'))),self.cal)
    def test_K_unavailable_preserves_original_semantics(self):
        p=s.parse_metadata(self.row(reference_epoch='SHFE.X.202001'),self.cal)
        z=s.path_interval(p,self.cal)
        self.assertEqual(z['K_state'],'after_calendar_pending')
        self.assertIsNone(z['K_index'])
        self.assertTrue(z['entry_before_K'])
        self.assertEqual(z['strict_count'],3)
        p=s.parse_metadata(self.row(reference_epoch='SHFE.X.201901'),self.cal)
        z=s.path_interval(p,self.cal)
        self.assertEqual(z['K_state'],'before_calendar_blocked')
        self.assertFalse(z['entry_before_K'])
        self.assertEqual(z['strict_count'],0)

if __name__=='__main__':unittest.main()
