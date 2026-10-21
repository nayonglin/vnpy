import json,tempfile,unittest
from pathlib import Path
import numpy as np
import pandas as pd
from stage093_reviewed_union_source import reviewed_union,assert_previous_preserved,sha

class UnionTests(unittest.TestCase):
 def test_exact_review_gate_and_no_replacement(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);a=d/'a';b=d/'b';ra=d/'ra';rb=d/'rb'
   a.write_text(json.dumps([{'requirement_id':'old'}]));b.write_text(json.dumps([{'requirement_id':'new'}]));oldsha=sha(a)
   old=dict(accepts_stage073_source=True,unresolved_P0=0,unresolved_P1=0,unresolved_P2=0);new=dict(accepts_stage089_inputs=True,qualified_inputs_manifest_sha256=sha(b),unresolved_P0=0,unresolved_P1=0,unresolved_P2=0)
   ra.write_text(json.dumps(old));rb.write_text(json.dumps(new));self.assertEqual(len(reviewed_union(a,b,ra,rb,oldsha)[0]),2)
   for field,value in [('unresolved_P2',1),('qualified_inputs_manifest_sha256','wrong'),('accepts_stage089_inputs',False)]:
    rb.write_text(json.dumps({**new,field:value}))
    with self.assertRaises(ValueError):reviewed_union(a,b,ra,rb,oldsha)
   rb.write_text(json.dumps(new));a.write_text(json.dumps([{'requirement_id':'tampered'}]))
   with self.assertRaises(ValueError):reviewed_union(a,b,ra,rb,oldsha)
   a.write_text(json.dumps([{'requirement_id':'old'}]));b.write_text(a.read_text());new['qualified_inputs_manifest_sha256']=sha(b);rb.write_text(json.dumps(new))
   with self.assertRaises(ValueError):reviewed_union(a,b,ra,rb,oldsha)
 def test_duplicate_in_one_manifest_is_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);a=d/'a';b=d/'b';ra=d/'ra';rb=d/'rb';a.write_text(json.dumps([{'requirement_id':'old'}]));b.write_text(json.dumps([{'requirement_id':'new'},{'requirement_id':'new'}]));ra.write_text(json.dumps(dict(accepts_stage073_source=True,unresolved_P0=0,unresolved_P1=0,unresolved_P2=0)));rb.write_text(json.dumps(dict(accepts_stage089_inputs=True,qualified_inputs_manifest_sha256=sha(b),unresolved_P0=0,unresolved_P1=0,unresolved_P2=0)))
   with self.assertRaises(ValueError):reviewed_union(a,b,ra,rb,sha(a))
 def fixture(self):
  d=dict(exchange=['X','X'],product=['A','A'],product_vt_symbol=['A.X','A.X'],eval_date=['2020-01-31','2020-02-28'],row_role=['ordinary','ordinary'],asof_eligible=[True,True],asof_status=['ready','ready'],reference_epoch=['X.A.202006']*2,target_day=['2020-04-30','2020-05-29'],observed_through=['2020-04-30','2020-05-29'],maturity_clock_reached=[True,True],conditional_economics=[True,True],training_eligible=[False,False],net_60d_training_label=[False,False],cumulative_net_r=[-0.,np.nan],cumulative_gross_r=[1.,np.nan],net_r_min=[-0.,np.nan],net_r_max=[-0.,np.nan],all_paths_value_known=[True,False],status=['conditional_value_known','path_unknown'],path_count=[1,1],known_paths=[1,0],episodes=[1,1]);return pd.DataFrame(d)
 def test_full_identity_clock_and_known_bits_guard(self):
  old=self.fixture();new=old.copy();new.loc[1,['all_paths_value_known','cumulative_net_r']]=[True,2.];self.assertEqual(assert_previous_preserved(old,new,1)['old_known_preserved'],1)
  for col,value in [('eval_date','2021-01-01'),('row_role','fixed'),('asof_eligible',False),('observed_through','2021-01-01')]:
   altered=new.copy();altered.loc[1,col]=value
   with self.assertRaises(ValueError):assert_previous_preserved(old,altered,1)
  altered=new.copy();altered.loc[0,'cumulative_net_r']=0.
  with self.assertRaises(ValueError):assert_previous_preserved(old,altered,1)
  altered=new.copy();altered.loc[0,'episodes']=2
  with self.assertRaises(ValueError):assert_previous_preserved(old,altered,1)
