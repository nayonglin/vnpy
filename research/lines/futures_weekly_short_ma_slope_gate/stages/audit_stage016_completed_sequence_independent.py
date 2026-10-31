"""Pure authoritative-calendar guards, no engine, IO or replay."""
import copy,sys,unittest
from pathlib import Path
R=Path('/Users/mac/.codex/worktrees/weekly19-official-20261031/fian');sys.path.insert(0,str(R/'examples/portfolio_backtesting'))
import qmt_roll_weekly19_live_pipeline as p
class CompletedSequenceIndependent(unittest.TestCase):
 def test_initial_missing_completed_day_is_explicitly_blocked_without_mutation(self):
  bundle={'funding':{'cold_start_date':'2026-10-29'},'runtime':None};data={'calendar':['2026-10-28','2026-10-29','2026-10-30','2026-11-02']};before=copy.deepcopy((bundle,data))
  with self.assertRaisesRegex(p.Weekly19PipelineError,'history_gap.*2026-10-29'):p._assert_completed_history_sequence(bundle,data,'2026-10-30')
  self.assertEqual((bundle,data),before)
 def test_recovery_requires_monday_before_tuesday_but_not_natural_weekend_days(self):
  bundle={'funding':{'cold_start_date':'2026-10-30'},'runtime':{'input_cursor':'2026-10-30'}};data={'calendar':['2026-10-30','2026-11-02','2026-11-03','2026-11-04']}
  p._assert_completed_history_sequence(bundle,data,'2026-11-02')
  with self.assertRaisesRegex(p.Weekly19PipelineError,'history_gap.*2026-11-02'):p._assert_completed_history_sequence(bundle,data,'2026-11-03')
 def test_pre_activation_history_and_future_calendar_do_not_force_theoretical_replay(self):
  bundle={'funding':{'cold_start_date':'2026-10-31'},'runtime':None};data={'calendar':['2015-01-05','2026-10-29','2026-10-30','2026-11-02','2026-11-03']}
  p._assert_completed_history_sequence(bundle,data,'2026-11-02')
if __name__=='__main__':unittest.main(verbosity=2)
