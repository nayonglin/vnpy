import unittest
from stage064_remaining_c2_local_repair import classify
class RepairTests(unittest.TestCase):
 def test_rejected_old_event_not_newly_repairable(self):
  x=classify(True,False,['daily_ohlc_mismatch','no_rows_in_reference_session_envelope'],4,False)
  self.assertEqual(x,'previously_audited_rejected')
 def test_unsupported_has_no_qualification_despite_cached_files(self):
  self.assertEqual(classify(False,False,[],4,True),'historical_session_research_required')
 def test_accepted_residual_is_blocking_invariant(self):
  with self.assertRaisesRegex(ValueError,'accepted'):classify(True,True,[],2,False)
 def test_old_scope_no_files_is_not_called_new_event(self):
  self.assertEqual(classify(True,False,[],0,False,previous_scope=True),
   "previous_reference_scope_no_local_native_candidate")
 def test_new_native_files_only_candidates(self):
  self.assertEqual(classify(True,False,[],4,False),'new_event_local_candidates_not_audited')
 def test_new_sqlite_only_candidate_and_empty_distinct(self):
  self.assertEqual(classify(True,False,[],0,True),'new_event_local_candidates_not_audited')
  self.assertEqual(classify(True,False,[],0,False),'new_event_no_local_native_candidate')
