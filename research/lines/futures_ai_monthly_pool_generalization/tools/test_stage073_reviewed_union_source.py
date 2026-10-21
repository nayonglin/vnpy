"""Two gates and finite known-value preservation for evidence-only augmentation."""
import copy,json,tempfile,unittest
from pathlib import Path
import numpy as np
import pandas as pd
from stage073_reviewed_union_source import reviewed_union,assert_known_preserved,sha

class TestUnion(unittest.TestCase):
 def test_both_exact_review_hashes_required_and_overlap_refused(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);a=d/'a.json';b=d/'b.json';ra=d/'ra.json';rb=d/'rb.json'
   a.write_text(json.dumps([{'requirement_id':'old','canonical_input_sha256':'x'}]));b.write_text(json.dumps([{'requirement_id':'new','canonical_input_sha256':'y'}]))
   old={'accepts_stage056_inputs':True,'qualified_inputs_manifest_sha256':sha(a),'unresolved_P0':0,'unresolved_P1':0,'unresolved_P2':0}
   new={'accepts_stage067_inputs':True,'qualified_inputs_manifest_sha256':sha(b),'unresolved_P0':0,'unresolved_P1':0,'unresolved_P2':0}
   ra.write_text(json.dumps(old));rb.write_text(json.dumps(new))
   self.assertEqual(len(reviewed_union(a,b,ra,rb)[0]),2)
   for field,value in [('unresolved_P1',1),('qualified_inputs_manifest_sha256','wrong'),('accepts_stage067_inputs',False)]:
    bad={**new,field:value};rb.write_text(json.dumps(bad))
    with self.assertRaises(ValueError):reviewed_union(a,b,ra,rb)
   b.write_text(a.read_text());new['qualified_inputs_manifest_sha256']=sha(b);rb.write_text(json.dumps(new))
   with self.assertRaises(ValueError):reviewed_union(a,b,ra,rb)
 def test_known_float_bits_and_unknown_not_zero(self):
  base=pd.DataFrame({'asof_eligible':[True,True],'maturity_clock_reached':[True,True],'all_paths_value_known':[True,False],'cumulative_net_r':[1.,np.nan],'cumulative_gross_r':[2.,np.nan],'net_r_min':[1.,np.nan],'net_r_max':[1.,np.nan],'status':['conditional_value_known','path_unknown'],'path_count':[1,1],'known_paths':[1,0],'episodes':[1,1]})
  expanded=base.copy();expanded.loc[1,['all_paths_value_known','cumulative_net_r']]=[True,-2.]
  self.assertEqual(assert_known_preserved(base,expanded,1)['old_known_preserved'],1)
  expanded.loc[0,'cumulative_net_r']=np.nextafter(1.,2.)
  with self.assertRaises(ValueError):assert_known_preserved(base,expanded,1)
 def test_known_state_cannot_be_rewritten(self):
  base=pd.DataFrame({'asof_eligible':[True],'maturity_clock_reached':[True],'all_paths_value_known':[True],'cumulative_net_r':[0.],'cumulative_gross_r':[0.],'net_r_min':[0.],'net_r_max':[0.],'status':['conditional_value_known'],'path_count':[1],'known_paths':[1],'episodes':[0]})
  changed=base.copy();changed.loc[0,'episodes']=1
  with self.assertRaises(ValueError):assert_known_preserved(base,changed,1)
if __name__=='__main__':unittest.main()
