import copy,hashlib,json,os,sys,tempfile,unittest
from pathlib import Path
from datetime import timedelta
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'examples/portfolio_backtesting'),str(ROOT/'tests')]
import qmt_roll_weekly19_funding as funding
from test_weekly19_external_funding import ACCOUNT,RELEASE,SOURCE,NOW,broker
from qmt_roll_weekly19_friday_report import build_friday_report, FridayMailOutbox, ReportError, report_digest

def account(balance='120000.00',at=NOW):
 return broker(balance=balance,at=at,Available='90000.00',CurrMargin='30000.00',PositionProfit='1000.00',query_last_seen=True,query_error_rows=0)

def inputs():
 state=funding.initial_state(ACCOUNT,RELEASE,'2026-10-30')
 result=funding.recommend_topup(state,account(),'2026-10-30',['native-1'],SOURCE,NOW)
 return dict(funding_state=result['state'],broker_account=account(),recommendation=result['recommendation'],
  decision=dict(material_release_id=RELEASE,target_date='2026-10-30',data_receipt_sha256=SOURCE,
   funding_admitted_ids=['native-1'],intents=[dict(vt_symbol='rb2701.SHFE',direction='long',offset='open',volume=2)]),
  data_receipt=dict(status='ready',material_release_id=RELEASE,target_date='2026-10-30',sha256=SOURCE),now=NOW)

class FridayReportTest(unittest.TestCase):
 def test_current_bound_advice_is_actionable_after_public_core_recheck(self):
  r=build_friday_report(**inputs(),preview=False);self.assertTrue(r['actionable']);self.assertEqual(r['blockers'],[])
 def test_old_advice_after_equity_changes_is_not_actionable(self):
  i=inputs();i['broker_account']=account('100000.00');r=build_friday_report(**i,preview=False)
  self.assertFalse(r['actionable']);self.assertEqual(r['current_recommendation_fen'],5000000)
  self.assertIn('recommendation_not_current',r['blockers'])
 def test_missing_explicit_actionability_and_foreign_request_fail_closed(self):
  i=inputs();i['recommendation'].pop('actionable',None);r=build_friday_report(**i,preview=False);self.assertFalse(r['actionable'])
  i=inputs();i['recommendation']['request_id']='b'*64;r=build_friday_report(**i,preview=False);self.assertFalse(r['actionable'])
 def test_current_receipt_cannot_reuse_request_from_other_source(self):
  i=inputs();i['decision']['data_receipt_sha256']='b'*64;i['data_receipt']['sha256']='b'*64
  r=build_friday_report(**i,preview=False);self.assertFalse(r['actionable'])
 def test_external_request_not_credited_or_called_profit(self):
  i=inputs();before=copy.deepcopy(i['funding_state']);r=build_friday_report(**i)
  self.assertEqual(i['funding_state'],before);self.assertEqual(r['equity_fen'],12000000)
  self.assertEqual(r['reserve_remaining_fen'],15000000);self.assertEqual(r['current_recommendation_fen'],3000000)
  self.assertFalse(r['funding_ready']);self.assertFalse(r['production_qualified'])
  for text in ['120,000.00','150,000.00','30,000.00','未到账','重新计算']:self.assertIn(text,r['body'])
  self.assertNotIn('test-account',r['body']);self.assertNotIn('9999',r['body'])
 def test_no_new_signal_still_exposes_old_pending(self):
  i=inputs();i['recommendation']={'status':'no_admitted_entry','amount_fen':0};i['decision']['funding_admitted_ids']=[];i['decision']['intents']=[]
  r=build_friday_report(**i);self.assertEqual(r['historical_pending_fen'],3000000);self.assertFalse(r['funding_ready'])
  self.assertIn('30,000.00',r['body']);self.assertIn('历史',r['body']);self.assertNotIn('无需补资，可开仓',r['body'])
 def test_expired_request_cannot_be_actionable(self):
  i=inputs();i['now']=NOW+timedelta(days=7);i['broker_account']=account(at=i['now']);i['recommendation']={'status':'request_expired','amount_fen':3000000}
  r=build_friday_report(**i);self.assertIn('过期',r['body']);self.assertFalse(r['funding_ready']);self.assertFalse(r['actionable'])
 def test_current_equity_recovery_does_not_force_old_debt(self):
  i=inputs();i['broker_account']=account('151000.00');i['recommendation']={'status':'equity_at_or_above_floor','amount_fen':0}
  r=build_friday_report(**i);self.assertEqual(r['current_recommendation_fen'],0);self.assertIn('不必补足旧建议',r['body'])
 def test_source_or_stale_account_is_blocked_not_false_zero(self):
  i=inputs();i['broker_account']=account(at=NOW-timedelta(seconds=301));r=build_friday_report(**i)
  self.assertIsNone(r['equity_fen']);self.assertFalse(r['actionable']);self.assertIn('无法可靠计算',r['body'])
 def test_missing_data_blocks_actionable_amount(self):
  i=inputs();i['data_receipt']['status']='blocked';r=build_friday_report(**i);self.assertFalse(r['actionable']);self.assertIn('数据尚未通过',r['body'])
 def test_last_week_signal_is_not_actionable_this_friday(self):
  i=inputs();i['now']=NOW+timedelta(days=7);i['broker_account']=account(at=i['now']);i['funding_state']=funding.initial_state(ACCOUNT,RELEASE,'2026-10-30');i['recommendation']={'status':'topup_recommended','amount_fen':3000000}
  r=build_friday_report(**i,preview=False);self.assertFalse(r['actionable']);self.assertIn('report_target_not_current_week',r['blockers']);self.assertNotIn('rb2701.SHFE',r['body'])
 def test_receipt_or_release_mismatch_rejected(self):
  i=inputs();i['decision']['material_release_id']='foreign'
  with self.assertRaises(ReportError):build_friday_report(**i)
  i=inputs();i['data_receipt']['sha256']='b'*64
  with self.assertRaises(ReportError):build_friday_report(**i)
 def test_nothing_is_due_when_no_new_or_pending(self):
  i=inputs();i['funding_state']=funding.initial_state(ACCOUNT,RELEASE,'2026-10-30');i['recommendation']={'status':'no_admitted_entry','amount_fen':0};i['decision']['funding_admitted_ids']=[];i['decision']['intents']=[]
  r=build_friday_report(**i);self.assertIn('没有有效新开候选',r['body']);self.assertEqual(r['historical_pending_fen'],0)
 def test_weekdays_and_unknown_pnl_are_explicit(self):
  i=inputs();i['now']=NOW-timedelta(days=1)
  with self.assertRaises(ReportError):build_friday_report(**i)
  i=inputs();raw=json.loads(i['broker_account']['raw_payload']);raw.pop('PositionProfit');t=json.dumps(raw,ensure_ascii=False,sort_keys=True,separators=(',',':'));i['broker_account']={'raw_payload':t,'raw_sha256':hashlib.sha256(t.encode()).hexdigest()}
  r=build_friday_report(**i);self.assertIn('未取得独立浮盈亏字段',r['body']);self.assertIsNone(r['unrealized_pnl_fen'])

class MailOutboxTest(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory(dir='/private/tmp');self.root=Path(self.t.name).resolve();os.chmod(self.root,0o700);self.out=FridayMailOutbox(self.root);self.r=build_friday_report(**inputs(),preview=False)
 def tearDown(self):self.t.cleanup()
 def test_sent_once_and_same_week_revision_not_resent(self):
  calls=[]
  def send(report):calls.append(report['report_sha256']);return {'email_status':'sent'}
  self.assertEqual(self.out.deliver(self.r,send)['status'],'sent');self.assertEqual(self.out.deliver(self.r,send)['status'],'already_sent');self.assertEqual(len(calls),1)
  r=copy.deepcopy(self.r);r['body']+=' revised';r['report_sha256']=report_digest(r)
  self.assertEqual(self.out.deliver(r,send)['status'],'already_sent');self.assertEqual(len(calls),1)
 def test_ambiguous_send_never_retries_blindly(self):
  calls=[]
  def uncertain(report):calls.append(1);raise OSError('transport connection lost')
  self.assertEqual(self.out.deliver(self.r,uncertain)['status'],'delivery_unknown');self.assertEqual(self.out.deliver(self.r,uncertain)['status'],'delivery_unknown');self.assertEqual(len(calls),1)
 def test_missing_config_is_retryable_and_preview_does_not_mark_sent(self):
  self.assertEqual(self.out.deliver(self.r,lambda _: {'email_status':'blocked_missing_config'})['status'],'blocked_before_send')
  self.assertEqual(self.out.deliver(self.r,lambda _: {'email_status':'dry_run_written'})['status'],'preview_written')
  self.assertEqual(self.out.deliver(self.r,lambda _: {'email_status':'sent'})['status'],'sent')
 def test_first_lock_cold_concurrency_has_one_send(self):
  from concurrent.futures import ThreadPoolExecutor
  import threading,time
  for n in range(8):
   parent=self.root/f'cold{n}';parent.mkdir(mode=0o700);barrier=threading.Barrier(2);calls=[]
   def worker():
    out=FridayMailOutbox(parent);barrier.wait()
    def send(_):calls.append(1);time.sleep(.002);return {'email_status':'sent'}
    return out.deliver(self.r,send)['status']
   with ThreadPoolExecutor(max_workers=2)as pool:
    futures=[pool.submit(worker)for _ in range(2)];statuses=[f.result()for f in futures]
   self.assertEqual(sorted(statuses),['already_sent','sent']);self.assertEqual(calls,[1])
 def test_preview_never_calls_transport(self):
  r=build_friday_report(**inputs());calls=[]
  self.assertEqual(self.out.deliver(r,lambda _:calls.append(1))['status'],'preview_only');self.assertEqual(calls,[])
 def test_bad_parent_or_symlink_is_rejected(self):
  p=self.root/'bad';p.mkdir(mode=0o755)
  with self.assertRaises(ReportError):FridayMailOutbox(p)
  link=self.root/'link';link.symlink_to(self.root,target_is_directory=True)
  with self.assertRaises(ReportError):FridayMailOutbox(link)
 def test_tampered_body_hash_rejected_before_send(self):
  r=copy.deepcopy(self.r);r['body']+='bad';calls=[]
  with self.assertRaises(ReportError):self.out.deliver(r,lambda _:calls.append(1))
  self.assertEqual(calls,[])
if __name__=='__main__':unittest.main()
