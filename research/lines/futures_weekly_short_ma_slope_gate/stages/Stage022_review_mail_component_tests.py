"""Independent notification contract/atomic outbox checks; injected transport only."""
from pathlib import Path
from copy import deepcopy
import json,sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[4];sys.path[:0]=[str(ROOT/'examples/portfolio_backtesting'),str(ROOT/'tests')]
import qmt_roll_weekly19_daily_report as daily
from qmt_roll_weekly19_friday_report import ReportError,report_digest
from test_weekly19_daily_report import inputs,row,DAY
class DailyContracts(unittest.TestCase):
 def build(self,rows=(),**changes):return daily.build_daily_risk_report(**inputs(rows=list(rows),**changes))
 def test_exact_today_heat_count_deduplicates_and_ignores_other_risks(self):
  heat=row();short=row(position_direction='short',reason_code='short_risk_cluster_heat_deleverage',close_lifecycle_id='heat-short',intent_ids=['short']);technical=row(reason_code='long_base_stop',close_lifecycle_id='technical',intent_ids=['technical']);forced=row(reason_code='forced_margin_deleverage',close_lifecycle_id='forced',intent_ids=['forced']);r=self.build([heat,deepcopy(heat),short,technical,forced]);self.assertEqual(r['today_cluster_signal_status'],'present');self.assertEqual(r['today_cluster_signal_count'],2);self.assertEqual(len(r['items']),4)
 def test_historical_heat_and_new_technical_do_not_become_today_heat(self):
  old=row(signal_date='2026-10-30',next_execution_day=DAY);technical=row(reason_code='short_base_stop',position_direction='short',close_lifecycle_id='technical',intent_ids=['technical']);r=self.build([old,technical]);self.assertTrue(r['has_risk']);self.assertEqual(r['today_cluster_signal_status'],'none');self.assertEqual(r['today_cluster_signal_count'],0)
 def test_current_unknown_is_unconfirmed_not_false_none(self):
  r=self.build([row(reason_code='not_a_known_exit')]);self.assertTrue(r['has_risk']);self.assertEqual(r['today_cluster_signal_status'],'unconfirmed');self.assertEqual(r['today_unknown_reason_count'],1);self.assertIn('原因未确认',r['body'])
 def test_foreign_or_incomplete_source_never_produces_proven_no_risk(self):
  a=inputs();a['data_receipt']['status']='blocked';r=daily.build_daily_risk_report(**a);self.assertIsNone(r['has_risk']);self.assertEqual(r['today_cluster_signal_status'],'unconfirmed');self.assertNotIn('本完成交易日无新增风险',r['body'])
 def test_legacy_completed_dates_remain_explicit_unknown(self):
  r=self.build([row(signal_date='2026-10-30',next_execution_day=DAY,filled_volume=2,status='completed',fill_date_coverage='legacy_or_partial')]);self.assertTrue(r['has_risk']);self.assertTrue(r['items'][0]['fill_date_unconfirmed']);self.assertFalse(r['items'][0]['today_fill_update'])
 def test_filtered_first_duplicate_cannot_hide_conflicting_lifecycle(self):
  old=row(signal_date='2026-10-28',next_execution_day='2026-10-29',filled_volume=2,status='completed',fill_trading_dates=['2026-10-29']);conflict=dict(old,status='retry_required',filled_volume=1)
  with self.assertRaises(ReportError):self.build([old,conflict])
class OutboxCrashBoundary(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(dir='/private/tmp');self.addCleanup(self.tmp.cleanup);self.parent=Path(self.tmp.name).resolve();self.parent.chmod(0o700);self.out=daily.DailyMailOutbox(self.parent);self.report=daily.build_daily_risk_report(**inputs(preview=False))
 def test_uncaught_process_loss_leaves_durable_sending_and_no_resend(self):
  class ProcessLoss(BaseException):pass
  calls=[]
  def die(_):calls.append(1);raise ProcessLoss()
  with self.assertRaises(ProcessLoss):self.out.deliver(self.report,die)
  record=json.loads(next(self.parent.glob('*.json')).read_text());self.assertEqual(record['status'],'sending')
  changed=daily.build_daily_risk_report(**inputs(rows=[row()],preview=False));r=self.out.deliver(changed,lambda _:calls.append(2));self.assertEqual(r['status'],'delivery_unknown');self.assertEqual(calls,[1])
 def test_sender_cannot_mutate_original_report(self):
  saved=deepcopy(self.report)
  def sender(received):received['body']='mutated transport copy';received['items'].append({'bogus':'copy'});return {'email_status':'sent'}
  self.assertEqual(self.out.deliver(self.report,sender)['status'],'sent');self.assertEqual(self.report,saved)
 def test_bad_digest_and_CRLF_fail_before_lock_or_transport(self):
  r=dict(self.report,subject='bad\r\nheader');r['report_sha256']=report_digest(r)
  with self.assertRaises(ReportError):self.out.deliver(r,lambda _:self.fail('transport called'))
  self.assertEqual(list(self.parent.iterdir()),[])
if __name__=='__main__':unittest.main()
