import unittest
from copy import deepcopy
try:
 from stage029_metadata_delta import normalize_metadata_maps,normalize_margin_override
except ModuleNotFoundError:
 def normalize_metadata_maps(*a,**k):raise NotImplementedError('metadata_delta_missing')
 def normalize_margin_override(*a,**k):raise NotImplementedError('metadata_delta_missing')

class MetadataDeltaTests(unittest.TestCase):
 def rows(self):
  old={'sizes':{'cu2611.SHFE':5},'slippages':{'cu2611.SHFE':10.},'rates':{'cu2611.SHFE':0.},'spec':{'risk':.018}}
  new=deepcopy(old)
  for k,v in [('sizes',5),('slippages',10.),('rates',0.)]:new[k]['cu2612.SHFE']=v
  return old,new
 def test_only_fixed_new_copper_normalizes_with_no_input_mutation(self):
  old,new=self.rows();saved=deepcopy(new);self.assertEqual(normalize_metadata_maps(new,old,'2026-10-26'),old);self.assertEqual(new,saved)
 def test_changed_old_size_never_allowed(self):
  old,new=self.rows();new['sizes']['cu2611.SHFE']=10
  with self.assertRaisesRegex(ValueError,'existing_metadata_changed'):normalize_metadata_maps(new,old,'2026-10-26')
 def test_unknown_new_contract_never_allowed(self):
  old,new=self.rows();new['sizes']['cu2701.SHFE']=5
  with self.assertRaisesRegex(ValueError,'metadata_additions'):normalize_metadata_maps(new,old,'2026-10-26')
 def test_new_contract_exact_specs_required(self):
  old,new=self.rows();new['slippages']['cu2612.SHFE']=0
  with self.assertRaisesRegex(ValueError,'new_metadata_value'):normalize_metadata_maps(new,old,'2026-10-26')
 def test_frozen_end_does_not_allow_addition(self):
  old,new=self.rows()
  with self.assertRaisesRegex(ValueError,'metadata_additions'):normalize_metadata_maps(new,old,'2026-10-23')
 def test_margin_only_new_fixed_key_is_normalized(self):
  self.assertEqual(normalize_margin_override('cu2611.SHFE=0.12,cu2612.SHFE=0.12','cu2611.SHFE=0.12','2026-10-26'),'cu2611.SHFE=0.12')
 def test_margin_old_change_and_new_wrong_value_rejected(self):
  for text in ['cu2611.SHFE=0.13,cu2612.SHFE=0.12','cu2611.SHFE=0.12,cu2612.SHFE=0.13']:
   with self.assertRaises(ValueError):normalize_margin_override(text,'cu2611.SHFE=0.12','2026-10-26')
 def test_duplicate_margin_keys_rejected(self):
  with self.assertRaisesRegex(ValueError,'duplicate_margin_key'):normalize_margin_override('cu2611.SHFE=0.12,cu2611.SHFE=0.12,cu2612.SHFE=0.12','cu2611.SHFE=0.12','2026-10-26')
if __name__=='__main__':unittest.main()
