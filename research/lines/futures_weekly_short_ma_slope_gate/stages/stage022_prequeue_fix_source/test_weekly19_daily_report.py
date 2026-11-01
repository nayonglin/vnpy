"""Literal daily mail fixtures; never SMTP, CTP, funds or order permission."""
import copy,hashlib,json,os,sys,tempfile,unittest
from datetime import datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'examples/portfolio_backtesting'),str(ROOT/'tests')]
from test_weekly19_external_funding import ACCOUNT,RELEASE,SOURCE
from qmt_roll_weekly19_friday_report import FridayMailOutbox,ReportError,report_digest
try:import qmt_roll_weekly19_daily_report as daily
except ModuleNotFoundError:daily=None
NOW=datetime(2026,11,2,16,35,tzinfo=ZoneInfo('Asia/Shanghai'));DAY='2026-11-02'
def inputs(**kw):
 out=dict(decision=dict(schema='weekly19.runtime-decision.v1',trading_date=DAY,account_fingerprint=ACCOUNT,material_release_id=RELEASE,data_receipt_sha256=SOURCE,intents=[],production_qualified=False),
  data_receipt=dict(status='ready',target_date=DAY,material_release_id=RELEASE,sha256=SOURCE),account_key=ACCOUNT,material_release_id=RELEASE,rows=[],now=NOW)
 out.update(kw);return out
def row(**kw):
 out=dict(vt_symbol='rb2701.SHFE',position_direction='long',signal_date=DAY,next_execution_day='2026-11-03',reason_code='long_risk_cluster_heat_deleverage',
  planned_volume=2,filled_volume=0,status='pending',close_lifecycle_id='close-life-1',intent_ids=['native-close-1'],fill_trading_dates=[],fill_date_coverage='complete')
 out.update(kw);return out
class DailyReportTests(unittest.TestCase):
 def setUp(self):self.assertIsNotNone(daily,'daily renderer/outbox missing')
 def build(self,**kw):return daily.build_daily_risk_report(**inputs(**kw))
 def test_non_friday_zero_signal_requires_ready_matching_completed_source(self):
  result=self.build();self.assertEqual(result['schema'],'weekly19.daily-risk-report.v1');self.assertEqual(result['report_kind'],'daily_risk');self.assertEqual(result['target_date'],DAY)
  self.assertFalse(result['has_risk']);self.assertEqual(result['risk_status'],'no_risk_actions');self.assertIn('无新增风险',result['body']);self.assertFalse(result['production_qualified'])
 def test_daily_cluster_question_counts_only_new_cluster_signals(self):
  heat=self.build(rows=[row()]);self.assertEqual((heat.get('today_cluster_signal_status'),heat.get('today_cluster_signal_count')),('present',1));self.assertIn('今日风险组压力降仓新信号：有 1 项',heat['body'])
  technical=self.build(rows=[row(reason_code='long_ma_stop')]);self.assertEqual((technical.get('today_cluster_signal_status'),technical.get('today_cluster_signal_count')),('none',0));self.assertIn('今日风险组压力降仓新信号：无',technical['body'])
  historical=self.build(rows=[row(signal_date='2026-10-30',next_execution_day=DAY)]);self.assertTrue(historical['has_risk']);self.assertEqual((historical.get('today_cluster_signal_status'),historical.get('today_cluster_signal_count')),('none',0))
  forced=self.build(rows=[row(reason_code='forced_margin_deleverage')]);self.assertEqual(forced.get('today_cluster_signal_status'),'none')
 def test_unknown_new_reason_or_blocked_data_never_claim_no_cluster_signal(self):
  unknown=self.build(rows=[row(reason_code='unknown_new_reason')]);self.assertEqual(unknown.get('today_cluster_signal_status'),'unconfirmed');self.assertEqual(unknown.get('today_unknown_reason_count'),1)
  self.assertIn('今日风险组压力降仓新信号：未确认',unknown['body']);self.assertNotIn('今日风险组压力降仓新信号：无',unknown['body'])
  args=inputs();args['data_receipt']['status']='blocked';blocked=daily.build_daily_risk_report(**args);self.assertEqual(blocked.get('today_cluster_signal_status'),'unconfirmed')
  mixed=self.build(rows=[row(),row(close_lifecycle_id='unknown-new',intent_ids=['unknown'],reason_code='unknown_new_reason')]);self.assertEqual((mixed.get('today_cluster_signal_status'),mixed.get('today_cluster_signal_count'),mixed.get('today_unknown_reason_count')),('unconfirmed',1,1))
 def test_unknown_reason_remains_a_close_plan_and_never_becomes_no_risk(self):
  result=self.build(rows=[row(reason_code='unrecognized_future_exit')]);self.assertTrue(result['has_risk'])
  self.assertIn('原因未确认',result['body']);self.assertIn('unrecognized_future_exit',result['body']);self.assertNotIn('无新增风险',result['body'])
 def test_direction_is_original_holding_and_pressure_is_not_margin_ratio(self):
  result=self.build(rows=[row(),row(vt_symbol='fu2701.SHFE',position_direction='short',reason_code='forced_margin_deleverage',close_lifecycle_id='close-life-2',intent_ids=['close-fu'])])
  self.assertIn('持仓多头→卖平',result['body']);self.assertIn('持仓空头→买平',result['body'])
  self.assertIn('风险簇热度降仓',result['body']);self.assertIn('保证金压力强制降仓',result['body']);self.assertIn('0.4',result['body']);self.assertIn('不是保证金占比40%',result['body'])
 def test_retry_lifecycle_counts_once_and_labels_fills_as_cumulative(self):
  item=row(signal_date='2026-10-30',next_execution_day=DAY,filled_volume=1,status='retry_required',intent_ids=['original','retry-1'],fill_trading_dates=[DAY])
  result=self.build(rows=[item]);self.assertEqual(len(result['items']),1);actual=result['items'][0]
  self.assertEqual((actual['planned_volume'],actual['filled_volume'],actual['remaining_volume']),(2,1,1));self.assertTrue(actual['today_fill_update']);self.assertTrue(actual['historical_pending'])
  self.assertIn('累计已成交 1 手',result['body']);self.assertNotIn('今日成交 1 手',result['body']);self.assertIn('重试',result['body'])
 def test_pending_lifecycle_with_actual_partial_fills_displays_partial_execution(self):
  result=self.build(rows=[row(signal_date='2026-10-30',next_execution_day=DAY,filled_volume=1,status='pending',fill_trading_dates=[DAY])])
  self.assertIn('状态：部分成交',result['body']);self.assertIn('剩余待执行',result['body']);self.assertIn('累计已成交 1 手',result['body'])
  self.assertEqual(result['items'][0]['status'],'pending')
 def test_completed_prior_signal_with_true_fill_today_is_included_but_old_completed_is_excluded(self):
  current=row(signal_date='2026-10-30',next_execution_day=DAY,filled_volume=2,status='completed',fill_trading_dates=[DAY])
  past=row(signal_date='2026-10-28',next_execution_day='2026-10-29',filled_volume=2,status='completed',fill_trading_dates=['2026-10-29'],close_lifecycle_id='old-complete')
  result=self.build(rows=[current,past]);self.assertEqual(len(result['items']),1);self.assertTrue(result['items'][0]['today_fill_update']);self.assertIn('已完成',result['body'])
 def test_legacy_date_coverage_never_claims_today_from_accumulated_fills(self):
  item=row(signal_date='2026-10-30',next_execution_day=DAY,filled_volume=1,status='retry_required',fill_date_coverage='legacy_or_partial')
  result=self.build(rows=[item]);self.assertFalse(result['items'][0]['today_fill_update']);self.assertIn('成交日期证据不完整',result['body']);self.assertIn('不据此推定今日成交',result['body'])
 def test_duplicate_lifecycle_is_deduplicated_only_if_exactly_identical(self):
  item=row();result=self.build(rows=[item,copy.deepcopy(item)]);self.assertEqual(len(result['items']),1)
  with self.assertRaises(ReportError):self.build(rows=[item,dict(item,planned_volume=3)])
 def test_conflicting_lifecycle_cannot_be_hidden_by_old_completed_filter(self):
  old=row(signal_date='2026-10-28',next_execution_day='2026-10-29',filled_volume=2,status='completed',fill_trading_dates=['2026-10-29'])
  retry=dict(old,status='retry_required',filled_volume=1)
  with self.assertRaises(ReportError):self.build(rows=[old,retry])
 def test_blocked_data_never_claims_no_risk(self):
  args=inputs();args['data_receipt']['status']='blocked';result=daily.build_daily_risk_report(**args)
  self.assertIsNone(result['has_risk']);self.assertEqual(result['risk_status'],'unconfirmed');self.assertIn('不能确认',result['body']);self.assertNotIn('无新增风险',result['body'])
 def test_missing_decision_or_wrong_source_account_release_target_and_hash_are_rejected(self):
  for mutation in ('missing','schema','account','release','target','sha'):
   args=inputs()
   if mutation=='missing':args['decision']=None
   if mutation=='schema':args['decision']['schema']='legacy'
   if mutation=='account':args['decision']['account_fingerprint']='f'*64
   if mutation=='release':args['decision']['material_release_id']='other'
   if mutation=='target':args['data_receipt']['target_date']='2026-10-30'
   if mutation=='sha':args['data_receipt']['sha256']='f'*64
   with self.subTest(mutation=mutation),self.assertRaises(ReportError):daily.build_daily_risk_report(**args)
 def test_invalid_fill_volume_completed_status_and_row_dates_fail_before_any_no_signal_output(self):
  for change in (dict(planned_volume=True),dict(filled_volume=3),dict(status='completed'),dict(position_direction='unknown'),dict(position_direction=[]),dict(fill_date_coverage=[]),dict(signal_date='2026-11-03'),dict(fill_trading_dates=[DAY]),dict(reason_code='bad\nheader')):
   with self.subTest(change=change),self.assertRaises(ReportError):self.build(rows=[row(**change)])
 def test_fixed_weekly_protection_reason_labels_do_not_claim_daily_or_fixed_two_percent_stop(self):
  result=self.build(rows=[row(reason_code='long_prev2day_stop'),row(close_lifecycle_id='base',intent_ids=['base'],reason_code='short_base_stop')])
  self.assertIn('前两根已完成周线',result['body']);self.assertIn('完成周收盘确认',result['body']);self.assertIn('动态保护线',result['body']);self.assertNotIn('前两日',result['body']);self.assertNotIn('2%',result['body'])
 def test_inputs_are_unchanged_and_digest_covers_source_rows(self):
  args=inputs(rows=[row()]);before=copy.deepcopy(args);result=daily.build_daily_risk_report(**args)
  self.assertEqual(args,before);self.assertEqual(result['report_sha256'],report_digest(result))

class DailyOutboxTests(unittest.TestCase):
 def setUp(self):
  self.assertIsNotNone(daily,'daily renderer/outbox missing');self.tmp=tempfile.TemporaryDirectory(dir='/private/tmp');self.addCleanup(self.tmp.cleanup);self.parent=Path(self.tmp.name).resolve();self.parent.chmod(0o700)
  self.out=daily.DailyMailOutbox(self.parent);self.report=daily.build_daily_risk_report(**inputs(preview=False))
 def test_daily_sent_once_even_if_same_day_execution_status_updates(self):
  calls=[];sender=lambda r:calls.append(r)or{'email_status':'sent'}
  self.assertEqual(self.out.deliver(self.report,sender)['status'],'sent')
  revised=daily.build_daily_risk_report(**inputs(rows=[row()],preview=False))
  self.assertEqual(self.out.deliver(revised,sender)['status'],'already_sent');self.assertEqual(len(calls),1)
 def test_account_release_day_and_friday_topic_have_separate_keys(self):
  from test_weekly19_friday_report import inputs as friday_inputs
  from qmt_roll_weekly19_friday_report import build_friday_report
  calls=[];sender=lambda r:calls.append(r)or{'email_status':'sent'}
  self.out.deliver(self.report,sender)
  second=inputs(preview=False);second['account_key']='b'*64;second['decision']['account_fingerprint']='b'*64
  self.assertEqual(self.out.deliver(daily.build_daily_risk_report(**second),sender)['status'],'sent')
  third=inputs(preview=False,material_release_id='other');third['decision']['material_release_id']='other';third['data_receipt']['material_release_id']='other'
  self.assertEqual(self.out.deliver(daily.build_daily_risk_report(**third),sender)['status'],'sent')
  nextday=inputs(preview=False,now=NOW+timedelta(days=1));nextday['decision']['trading_date']='2026-11-03';nextday['data_receipt']['target_date']='2026-11-03'
  self.assertEqual(self.out.deliver(daily.build_daily_risk_report(**nextday),sender)['status'],'sent')
  friday=friday_inputs();friday_report=build_friday_report(**friday,preview=False)
  self.assertEqual(FridayMailOutbox(self.parent).deliver(friday_report,sender)['status'],'sent')
  same_friday=inputs(preview=False,now=friday['now']);same_friday['decision']['trading_date']='2026-10-30';same_friday['data_receipt']['target_date']='2026-10-30'
  same_friday_report=daily.build_daily_risk_report(**same_friday)
  self.assertEqual(self.out.deliver(same_friday_report,sender)['status'],'sent');self.assertEqual(len(calls),6)
  self.assertEqual(self.out.deliver(same_friday_report,sender)['status'],'already_sent')
  records=[json.loads(p.read_text())for p in self.parent.glob('*.json')]
  self.assertEqual(sum(r.get('target_date')=='2026-10-30'and r.get('report_kind')=='daily_risk'for r in records),1)
  self.assertEqual(sum(r.get('week_key')=='2026-10-30'for r in records),1)
 def test_preview_does_not_lock_write_or_send_and_unknown_does_not_retry_revised_body(self):
  calls=[];preview=daily.build_daily_risk_report(**inputs());self.assertEqual(self.out.deliver(preview,lambda r:calls.append(r))['status'],'preview_only');self.assertEqual(list(self.parent.iterdir()),[])
  def lost(_):calls.append('attempt');raise OSError('offline simulated ambiguous SMTP')
  self.assertEqual(self.out.deliver(self.report,lost)['status'],'delivery_unknown')
  changed=daily.build_daily_risk_report(**inputs(rows=[row()],preview=False))
  self.assertEqual(self.out.deliver(changed,lost)['status'],'delivery_unknown');self.assertEqual(calls,['attempt'])
 def test_friday_schema_tampered_body_and_header_are_rejected_before_sender(self):
  for change in (dict(schema='weekly19.friday-report.v1'),dict(body='tampered'),dict(subject='bad\nheader')):
   report=dict(self.report,**change)
   if 'body'not in change:report['report_sha256']=report_digest(report)
   with self.subTest(change=change),self.assertRaises(ReportError):self.out.deliver(report,lambda _:self.fail('sender called'))
 def test_private_permissions_and_concurrent_daily_attempts_keep_one_transport_call(self):
  from concurrent.futures import ThreadPoolExecutor
  import threading
  barrier=threading.Barrier(2);calls=[]
  def worker():
   out=daily.DailyMailOutbox(self.parent);barrier.wait();return out.deliver(self.report,lambda r:calls.append(1)or{'email_status':'sent'})['status']
  with ThreadPoolExecutor(2)as pool:results=[f.result()for f in[pool.submit(worker),pool.submit(worker)]]
  self.assertEqual(sorted(results),['already_sent','sent']);self.assertEqual(calls,[1])
  for path in self.parent.iterdir():self.assertEqual(path.stat().st_mode&0o777,0o600)
