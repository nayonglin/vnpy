"""Only the new pure-X ID alignment; no actual files, tensors or SQL."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np
import pandas as pd

PATH=Path(__file__).with_name('stage093_sequence_alignment.py')


def module():
    if not PATH.exists():return None
    s=importlib.util.spec_from_file_location('test093_target',PATH);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m


def mother():
    return pd.DataFrame([dict(sequence_index=i,event_id=v,product_id='P.X',family_id='P.X',u_date='2020-01-0'+str(i+1),
        u_index=10+i,reference_epoch='P.X2001') for i,v in enumerate(['a','b','c'])])


class AlignmentBehavior(unittest.TestCase):
    def setUp(self):
        self.m=module();self.assertIsNotNone(self.m,'Stage093 implementation missing')

    def test_join_by_event_id_retains_full_mother_and_original_old_row_index(self):
        f=mother();a=self.m.align_by_event_id(f,['c','a'])
        self.assertEqual(a.event_id.tolist(),['a','b','c'])
        self.assertEqual(a.sequence_index.tolist(),[0,1,2])
        self.assertEqual(a.legacy_tensor_index.tolist(),[1,-1,0])
        self.assertEqual(a.sequence_missing.tolist(),[0,1,0])
        self.m.validate_alignment(f,a,2)

    def test_duplicate_or_nonmother_old_id_is_rejected(self):
        for old in (['a','a'],['a','outside']):
            with self.assertRaises(ValueError):self.m.align_by_event_id(mother(),old)

    def test_alignment_mask_index_and_identity_tampering_rejected(self):
        f=mother();a=self.m.align_by_event_id(f,['c','a'])
        for col,value in [('sequence_missing',1),('legacy_tensor_index',2),('event_id','wrong')]:
            bad=a.copy();bad.loc[0,col]=value
            with self.assertRaises(ValueError):self.m.validate_alignment(f,bad,2)


if __name__=='__main__':unittest.main()
