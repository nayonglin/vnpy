import unittest
import pandas as pd
from stage005_merge import merge_verified_layers
C=['vt_symbol','bar_datetime','open','high','low','close','volume','open_oi','close_oi']
def frame(price=10.,time='2020-01-02 09:00:00'):
 return pd.DataFrame([['m2005.DCE',pd.Timestamp(time),price,price,price,price,100.,200.,200.]],columns=C)
class MergeTests(unittest.TestCase):
 def test_priority(self):
  got=merge_verified_layers(frame(),[frame()],C[2:]);self.assertEqual(len(got),1);self.assertEqual(got.open.iloc[0],10.)
 def test_conflict_rejected(self):
  with self.assertRaisesRegex(ValueError,'overlap_conflict'):merge_verified_layers(frame(),[frame(11)],C[2:])
 def test_first_reference_tolerance(self):
  self.assertEqual(len(merge_verified_layers(frame(),[frame(10+9e-9),frame(10-9e-9)],C[2:])),1)
 def test_duplicate_base_rejected(self):
  with self.assertRaisesRegex(ValueError,'base_duplicate'):merge_verified_layers(pd.concat([frame(),frame()]),[],C[2:])
 def test_nan_overlap_rejected(self):
  a=frame();a.loc[0,'volume']=float('nan')
  with self.assertRaisesRegex(ValueError,'overlap_conflict'):merge_verified_layers(a,[a.copy()],C[2:])
 def test_distinct_sorted(self):
  x=merge_verified_layers(frame(time='2020-01-03'),[frame()],C[2:]);self.assertEqual(len(x),2);self.assertEqual(x.bar_datetime.iloc[0],pd.Timestamp('2020-01-02 09:00'))
if __name__=='__main__':unittest.main()
