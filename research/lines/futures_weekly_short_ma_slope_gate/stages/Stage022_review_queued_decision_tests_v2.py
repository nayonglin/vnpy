"""A same-source receipt is not evidence that queued bars were evaluated."""
from pathlib import Path
import sys,unittest
ROOT=Path(__file__).resolve().parents[4];sys.path[:0]=[str(ROOT/'examples/portfolio_backtesting'),str(ROOT/'tests')]
import qmt_roll_weekly19_daily_report as daily
from test_weekly19_daily_report import inputs,row,DAY
class QueuedDecision(unittest.TestCase):
 def test_pending_close_queued_bars_cannot_claim_no_new_heat_signal(self):
  args=inputs(rows=[row(signal_date='2026-10-30',next_execution_day=DAY)])
  args['decision'].update(bars_queued=True,reduce_only=True,blocked_reason='unresolved_execution_lifecycle')
  r=daily.build_daily_risk_report(**args)
  self.assertEqual(r['today_cluster_signal_status'],'unconfirmed','actual runtime queued decision has not run on_bars; source-ready must not mean evaluated-none')
  self.assertNotIn('今日风险组压力降仓新信号：无',r['body'])
 def test_queued_without_visible_lifecycles_is_still_unconfirmed(self):
  a=inputs();a['decision'].update(bars_queued=True,reduce_only=True,blocked_reason='unresolved_execution_lifecycle');r=daily.build_daily_risk_report(**a);self.assertEqual(r['today_cluster_signal_status'],'unconfirmed');self.assertIsNone(r['has_risk'])
 def test_exact_unresolved_flag_without_bars_field_is_unconfirmed(self):
  a=inputs(rows=[row()]);a['decision'].update(blocked_reason='unresolved_execution_lifecycle');r=daily.build_daily_risk_report(**a);self.assertEqual(r['today_cluster_signal_status'],'unconfirmed')
 def test_evaluated_reduce_only_retains_known_positive(self):
  a=inputs(rows=[row()]);a['decision'].update(reduce_only=True,bars_queued=False);r=daily.build_daily_risk_report(**a);self.assertEqual(r['today_cluster_signal_status'],'present');self.assertEqual(r['today_cluster_signal_count'],1)
if __name__=='__main__':unittest.main()
