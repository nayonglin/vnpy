import unittest
from types import SimpleNamespace
import pandas as pd
from stage012_ai_selection_off import disable_ai_selection,audit_ai_selection_off,AI_FLAGS
class AiOffTests(unittest.TestCase):
 def strategy(self):return SimpleNamespace(**{k:False for k in AI_FLAGS},selection_pairwise_runtime=None,ai_product_pool_load_status='disabled',ai_product_pool_eval_dates=[])
 def test_all_selection_flags_off_without_other_drift(self):
  original=dict(enable_selection_pairwise_v2=True,enable_selection_pairwise_v2_volume_tilt=True,risk_multiplier=.4)
  result=disable_ai_selection(original);self.assertTrue(original['enable_selection_pairwise_v2']);self.assertEqual(result['risk_multiplier'],.4);self.assertTrue(all(result[k] is False for k in AI_FLAGS))
 def test_clean_runtime_passes(self):self.assertTrue(audit_ai_selection_off(self.strategy(),{},0)['accepted'])
 def test_loaded_runtime_rejects(self):
  s=self.strategy();s.selection_pairwise_runtime=object();self.assertFalse(audit_ai_selection_off(s,{},0)['accepted'])
 def test_any_flag_rejects(self):
  for key in AI_FLAGS:
   s=self.strategy();setattr(s,key,True);self.assertFalse(audit_ai_selection_off(s,{},0)['accepted'])
 def test_score_rank_or_tilt_rejects(self):
  for col in ['selection_pairwise_score','selection_pairwise_rank','selection_pairwise_enabled','selection_pairwise_volume_tilt_applied']:
   self.assertFalse(audit_ai_selection_off(self.strategy(),{'candidates':pd.DataFrame({col:[1]})},0)['accepted'])
 def test_model_attempt_rejects(self):self.assertFalse(audit_ai_selection_off(self.strategy(),{},1)['accepted'])
 def test_monthly_snapshot_rejects(self):
  s=self.strategy();s.ai_product_pool_eval_dates=['2020-01-01'];self.assertFalse(audit_ai_selection_off(s,{},0)['accepted'])
if __name__=='__main__':unittest.main()
