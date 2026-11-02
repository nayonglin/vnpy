"""Operator-manual cash facts, offline fixtures only; never broker qualification."""
import copy,json,os,sys,tempfile,unittest
from pathlib import Path
from datetime import timedelta,datetime
from unittest import mock
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'examples/portfolio_backtesting'),str(ROOT/'tests')]
from test_weekly19_external_funding import ACCOUNT,RELEASE,SOURCE,NOW,broker,envelope
import qmt_roll_weekly19_funding as funds
from qmt_roll_weekly19_funding_store import FundingStore

CALENDAR=['2026-10-30','2026-11-02','2026-11-03','2026-11-04','2026-11-05','2026-11-06','2026-11-09']
ASSERTION='I_HAVE_MANUALLY_VERIFIED_ACTUAL_CASHFLOWS_AND_OFFSITE_RESERVE'
def account(**kw):return broker(Available='90000.00',**kw)
def initial():
 result=funds.recommend_topup(funds.initial_state(ACCOUNT,RELEASE,'2026-10-30'),account(),'2026-10-30',['native-original-1'],SOURCE,NOW)
 return result['state'],result['recommendation']['request_id']
def review(state,current,*,rid='review-1',now=None,topups=(),closed=(),remaining=None):
 now=now or datetime.fromisoformat(json.loads(current['raw_payload'])['observed_at'])
 raw=dict(schema='weekly19.operator-cash-review.v1',source_kind='operator_manual',record_id=rid,operator_id='offline-operator',os_uid=os.geteuid(),os_user='offline-user',
  assertion=ASSERTION,notes='Literal fixture, not a bank/source qualification',created_at=now.isoformat(),expires_at=(now+timedelta(minutes=30)).isoformat(),
  account_key=ACCOUNT,material_release_id=RELEASE,before_funding_revision=state['revision'],before_funding_sha256=funds._hash(state),
  before_checkpoint=copy.deepcopy(state['cashflow_checkpoint']),before_checkpoint_sha256=funds._hash(state['cashflow_checkpoint']),
  reserve_remaining_fen_before=state['reserve_remaining_fen'],confirmed_topup_fen_before=state['confirmed_topup_fen'],reviewed_account=copy.deepcopy(current),
  topups=[],closed_days=copy.deepcopy(list(closed)),expected_reserve_remaining_fen=remaining if remaining is not None else state['reserve_remaining_fen']-sum(t['amount_fen']for t in topups),
  no_unlisted_cashflows=True,broker_automatically_verified=False,production_qualified=False)
 for t in topups:
  request=state['requests'][t['request_id']]
  raw['topups'].append(dict(t,admitted_entry_ids=copy.deepcopy(request['admitted_entry_ids']),target_week_end=request['target_week_end'],source_sha256=request['source_sha256']))
 return envelope(raw)
def topup(request,amount=3000000,receipt='manual-bank-reference-1',at=None,day='2026-10-30'):
 return dict(request_id=request,amount_fen=amount,receipt_id=receipt,occurred_at=(at or NOW+timedelta(seconds=30)).isoformat(),trading_day=day)
def close(day='2026-10-30',dep=0,withdraw=0,at=None):
 return dict(trading_day=day,final_deposit_fen=dep,final_withdraw_fen=withdraw,closed_at=(at or NOW+timedelta(hours=1)).isoformat(),statement_reference='operator-read-final-statement',cashflows_complete=True)

class ManualFundingTests(unittest.TestCase):
 def apply(self,state,record,current,now=None):
  self.assertTrue(callable(getattr(funds,'apply_operator_cash_review',None)),'manual funding transition missing')
  return funds.apply_operator_cash_review(state,record,current,now or datetime.fromisoformat(json.loads(current['raw_payload'])['observed_at']),trading_calendar=CALENDAR)
 def test_confirmed_actual_deposit_debits_reserve_only_and_keeps_raw_equity_untouched(self):
  state,rid=initial();at=NOW+timedelta(minutes=1);current=account(balance='150000.00',deposit='30000.00',at=at);original=copy.deepcopy((state,current))
  record=review(state,current,topups=[topup(rid)])
  updated=self.apply(state,record,current)
  self.assertEqual((updated['reserve_remaining_fen'],updated['confirmed_topup_fen']),(12000000,3000000))
  self.assertEqual((state,current),original);self.assertNotIn('equity',updated)
  receipt=updated['receipts']['manual-bank-reference-1'];self.assertEqual(receipt['source_kind'],'operator_manual');self.assertEqual(receipt['manual_review_id'],'review-1')
  self.assertFalse(updated['production_qualified']);self.assertEqual(updated['requests'][rid]['marked_equity_fen'],12000000)
  funds.assert_open_funding_ready(updated,current,at)
 def test_partial_then_full_and_replay_after_expiry_never_debits_twice(self):
  state,rid=initial();at=NOW+timedelta(minutes=1);one=account(balance='130000.00',deposit='10000.00',at=at)
  record=review(state,one,topups=[topup(rid,1000000)])
  partial=self.apply(state,record,one);self.assertEqual(partial['requests'][rid]['status'],'partially_confirmed')
  later=at+timedelta(hours=1);fresh=account(balance='135000.00',deposit='10000.00',at=later,generation_uuid='fresh-real-generation')
  self.assertEqual(self.apply(partial,record,fresh,later),partial)
  current=account(balance='150000.00',deposit='30000.00',at=later)
  full=self.apply(partial,review(partial,current,rid='review-2',topups=[topup(rid,2000000,'bank-second',later-timedelta(seconds=1))]),current,later)
  self.assertEqual(full['confirmed_topup_fen'],3000000);self.assertEqual(len(full['receipts']),2)
 def test_balance_profit_never_becomes_a_transfer(self):
  state,rid=initial();at=NOW+timedelta(minutes=1);profit=account(balance='150000.00',at=at)
  unchanged=self.apply(state,review(state,profit),profit)
  self.assertEqual(unchanged['confirmed_topup_fen'],0);self.assertEqual(unchanged['reserve_remaining_fen'],funds.INITIAL_FEN)
  funds.assert_open_funding_ready(unchanged,profit,at)
  with self.assertRaises(ValueError):self.apply(state,review(state,profit,topups=[topup(rid)]),profit)
 def test_unknown_deposit_or_counter_change_cannot_be_covered_by_a_manual_flag(self):
  state,rid=initial();at=NOW+timedelta(minutes=1);current=account(deposit='40000.00',at=at)
  with self.assertRaises(ValueError):self.apply(state,review(state,current,topups=[topup(rid)]),current)
  current=account(deposit='30000.00',at=at);record=review(state,current,topups=[topup(rid)])
  later=account(deposit='30001.00',at=at+timedelta(seconds=1))
  with self.assertRaises(ValueError):self.apply(state,record,later)
 def test_cross_day_manual_close_and_already_received_current_day_cash_need_no_auto_parser(self):
  state,rid=initial();at=NOW.replace(month=11,day=2,hour=9,minute=1);current=account(balance='150000.00',deposit='30000.00',day='2026-11-02',at=at)
  record=review(state,current,closed=[close()],topups=[topup(rid,at=at-timedelta(seconds=1),day='2026-11-02')])
  updated=self.apply(state,record,current)
  self.assertEqual(updated['cashflow_checkpoint']['trading_day'],'2026-11-02');self.assertEqual(updated['day_rolls'][0]['source_kind'],'operator_manual')
  self.assertEqual(updated['day_rolls'][0]['following']['deposit_fen'],3000000)
  funds.assert_open_funding_ready(updated,current,at)
 def test_missing_closed_day_and_unlisted_holiday_window_cash_fail_atomically(self):
  state,rid=initial();at=NOW.replace(month=11,day=3,hour=9,minute=1);current=account(balance='150000.00',deposit='10000.00',day='2026-11-03',at=at)
  transfers=[topup(rid,2000000,'mon',at-timedelta(days=1),day='2026-11-02'),topup(rid,1000000,'tue',at-timedelta(seconds=1),day='2026-11-03')]
  good=[close(),close('2026-11-02',2000000,at=at-timedelta(hours=16))]
  with self.assertRaises(ValueError):self.apply(state,review(state,current,closed=good[:1],topups=transfers),current)
  updated=self.apply(state,review(state,current,closed=good,topups=transfers),current)
  self.assertEqual(updated['confirmed_topup_fen'],3000000);self.assertEqual(len(updated['receipts']),2)
 def test_topup_cannot_be_assigned_to_a_day_closed_before_the_actual_transfer(self):
  state,rid=initial();at=NOW.replace(month=11,day=2,hour=9,minute=1);current=account(balance='150000.00',deposit='0.00',day='2026-11-02',at=at)
  wrong=topup(rid,at=at-timedelta(seconds=1),day='2026-10-30')
  with self.assertRaises(ValueError):self.apply(state,review(state,current,closed=[close(dep=3000000)],topups=[wrong]),current)
 def test_negative_regressing_gross_counters_and_withdrawal_never_refill_reserve(self):
  state,rid=initial();at=NOW+timedelta(minutes=1);current=account(withdraw='100.00',at=at)
  updated=self.apply(state,review(state,current),current)
  self.assertEqual(updated['reserve_remaining_fen'],funds.INITIAL_FEN)
  lower=account(withdraw='99.00',at=at+timedelta(seconds=1))
  with self.assertRaises(ValueError):self.apply(updated,review(updated,lower,rid='review-2'),lower)
  bad=account(withdraw='-1.00',at=at)
  with self.assertRaises(ValueError):self.apply(state,review(state,bad),bad)
 def test_duplicate_receipt_across_reviews_and_rewritten_record_are_rejected(self):
  state,rid=initial();at=NOW+timedelta(minutes=1);current=account(balance='130000.00',deposit='10000.00',at=at)
  record=review(state,current,topups=[topup(rid,1000000)]);updated=self.apply(state,record,current)
  next_current=account(deposit='20000.00',at=at+timedelta(minutes=1))
  with self.assertRaises(ValueError):self.apply(updated,review(updated,next_current,rid='review-2',topups=[topup(rid,1000000)]),next_current)
  raw=json.loads(record['raw_payload']);raw['notes']='rewrite'
  with self.assertRaises(ValueError):self.apply(updated,envelope(raw),current)
 def test_wrong_account_release_admission_mode_expired_stale_and_integer_contract(self):
  state,rid=initial();at=NOW+timedelta(minutes=1);current=account(deposit='30000.00',at=at);base=review(state,current,topups=[topup(rid)])
  edits=[('account_key','f'*64),('material_release_id','other'),('source_kind','broker_cashflow_receipt'),('expected_reserve_remaining_fen',1)]
  for key,value in edits:
   raw=json.loads(base['raw_payload']);raw[key]=value
   with self.subTest(key=key),self.assertRaises(ValueError):self.apply(state,envelope(raw),current)
  for value in (3000000.0,True,-1,15000001):
   raw=json.loads(base['raw_payload']);raw['topups'][0]['amount_fen']=value
   with self.subTest(value=value),self.assertRaises(ValueError):self.apply(state,envelope(raw),current)
  raw=json.loads(base['raw_payload']);raw['topups'][0]['admitted_entry_ids']=['other-native']
  with self.assertRaises(ValueError):self.apply(state,envelope(raw),current)
  with self.assertRaises(ValueError):self.apply(state,base,account(deposit='30000.00',at=at+timedelta(minutes=31)),at+timedelta(minutes=31))
  with self.assertRaises(ValueError):self.apply(state,base,current,at+timedelta(seconds=301))
 def test_stale_parent_hash_cannot_consume_any_amount_and_store_cannot_rollback_manual_history(self):
  state,rid=initial();at=NOW+timedelta(minutes=1);current=account(balance='150000.00',deposit='30000.00',at=at)
  record=review(state,current,topups=[topup(rid)])
  moved=copy.deepcopy(state);moved['revision']+=1
  with self.assertRaises(ValueError):self.apply(moved,record,current)
  updated=self.apply(state,record,current)
  with tempfile.TemporaryDirectory(dir='/private/tmp')as directory:
   root=Path(directory).resolve();root.chmod(0o700);store=FundingStore(root/'cash.json')
   start=funds.initial_state(ACCOUNT,RELEASE,'2026-10-30');store.create(start);store.commit(0,state);store.commit(state['revision'],updated)
   self.assertEqual(store.load(),updated)
   bad=copy.deepcopy(updated);bad['manual_cash_reviews'].clear();bad['revision']+=1
   with self.assertRaises(ValueError):store.commit(updated['revision'],bad)
   self.assertEqual(store.load(),updated)

 def test_persisted_manual_consumption_cannot_move_beyond_original_request_expiry(self):
  state,rid=initial();at=NOW+timedelta(days=7,minutes=-1);current=account(balance='150000.00',deposit='30000.00',at=at)
  record=review(state,current,now=at,topups=[topup(rid,at=at-timedelta(seconds=1))])
  updated=self.apply(state,record,current,at);bad=copy.deepcopy(updated)
  bad['manual_cash_reviews']['review-1']['applied_at']=(at+timedelta(minutes=2)).isoformat()
  with self.assertRaises(ValueError):funds.validate_state(bad)

 def test_original_decision_cash_history_can_cover_two_separate_manual_commits(self):
  state,rid=initial();at=NOW+timedelta(minutes=1);first=account(balance='130000.00',deposit='10000.00',at=at)
  partial=self.apply(state,review(state,first,topups=[topup(rid,1000000)]),first)
  later=at+timedelta(minutes=1);second=account(balance='150000.00',deposit='30000.00',at=later)
  full=self.apply(partial,review(partial,second,rid='review-2',topups=[topup(rid,2000000,'bank-second',later-timedelta(seconds=1))]),second)
  # The immutable signal-origin validator is a history check, not a claim that
  # both manual records were consumed by one CAS transition.
  FundingStore._forward_ledger(state,full)
  with self.assertRaises(ValueError):FundingStore._forward_ledger(state,full,strict_manual_parent=True)
  FundingStore._forward_ledger(partial,full,strict_manual_parent=True)

class ManualPrivateEntryTests(unittest.TestCase):
 def setUp(self):
  import qmt_roll_weekly19_local_backend as local
  try:import qmt_roll_weekly19_manual_cash as manual
  except ModuleNotFoundError:manual=None
  self.assertIsNotNone(manual,'manual private record component missing');self.manual=manual
  self.tmp=tempfile.TemporaryDirectory(dir='/private/tmp');self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name).resolve();self.root.chmod(0o700)
  self.records=self.root/'reviews';self.records.mkdir(mode=0o700);self.ctx=self.root/'context.json'
  self.state,self.rid=initial();self.at=NOW+timedelta(minutes=1);self.current=account(balance='150000.00',deposit='30000.00',at=self.at)
  self.cfg=dict(schema='weekly19.live-context.v1',execution_profile='weekly19-15w-r150k',cash_verification_mode='operator_manual_v1',manual_cash_review_root=str(self.records),
   account_key=ACCOUNT,material_release_id=RELEASE,state_path=str(self.root/'state.json'),market_data={'immutable_generation':'fixture'},cash_sources={'existing_pending_refs':['keep']})
  self.ctx.write_text(json.dumps(self.cfg));self.ctx.chmod(0o600)
  self.backend=local.LocalEvidenceBackend(self.cfg,repo_root=ROOT,release_manifest=self.root/'manifest',activation_receipt=self.root/'activation',qualification_evidence=self.root/'qualification')
  self.backend.context_file=self.ctx
  self.live=mock.patch.object(manual,'_live_inputs',return_value=(self.state,dict(account=self.current),CALENDAR));self.live.start();self.addCleanup(self.live.stop)
  self.backend.require_production=lambda:None
  self.clock=mock.patch.object(manual,'_now',return_value=self.at,create=True);self.clock.start();self.addCleanup(self.clock.stop)
  self.input=dict(topups=[dict(topup(self.rid))],closed_days=[],expected_reserve_remaining_fen=12000000,notes='operator checked literal fixture')
 def prepare(self,**kw):return self.manual.prepare_operator_review(self.backend,self.input,operator_id='offline',review_id='human-review-1',now=self.at,**kw)
 def test_prepared_record_is_private_and_only_cash_reference_is_published(self):
  record=self.prepare();before=copy.deepcopy(self.state);result=self.manual.write_and_publish_operator_review(self.backend,record)
  self.assertEqual(result['status'],'record_written_pending_actor_consumption');self.assertFalse(result['funding_consumed'])
  ref=result['reference'];path=Path(ref['path']);self.assertEqual(path.stat().st_mode&0o777,0o600)
  self.assertEqual(self.manual.load_private_manual_review(ref),record)
  cfg=json.loads(self.ctx.read_text());self.assertEqual(cfg['cash_sources']['existing_pending_refs'],['keep']);self.assertEqual(len(cfg['cash_sources']['manual_reviews']),1)
  self.assertEqual(self.state,before);self.assertFalse(Path(self.cfg['state_path']).exists())
 def test_repeat_reuses_bytes_without_extending_expiry_or_duplicate_ref(self):
  record=self.prepare();result=self.manual.write_and_publish_operator_review(self.backend,record)
  again=self.prepare();self.assertEqual(again,record)
  result2=self.manual.write_and_publish_operator_review(self.backend,again)
  self.assertEqual(result2['reference'],result['reference']);self.assertEqual(len(json.loads(self.ctx.read_text())['cash_sources']['manual_reviews']),1)
  self.input['notes']='different statement'
  with self.assertRaises(ValueError):self.prepare()
 def test_record_written_but_reference_cas_failure_is_explicit_and_retry_keeps_original_bytes(self):
  record=self.prepare();changed=copy.deepcopy(self.cfg);changed['market_data']={'immutable_generation':'new'};self.ctx.write_text(json.dumps(changed));self.ctx.chmod(0o600)
  result=self.manual.write_and_publish_operator_review(self.backend,record)
  self.assertEqual(result['status'],'record_written_reference_not_published');self.assertFalse(result['funding_consumed']);self.assertTrue(Path(result['reference']['path']).exists())
  self.assertNotIn('manual_reviews',json.loads(self.ctx.read_text())['cash_sources'])
  self.ctx.write_text(json.dumps(self.cfg));self.ctx.chmod(0o600)
  retried=self.manual.write_and_publish_operator_review(self.backend,self.prepare());self.assertEqual(retried['reference'],result['reference'])
 def test_reference_retry_repeats_failed_context_directory_durability_barrier(self):
  record=self.prepare();original=self.manual.os.fsync;parent=self.root.stat();barriers=[]
  def fail_first_context_barrier(fd):
   info=self.manual.os.fstat(fd)
   if(info.st_dev,info.st_ino)==(parent.st_dev,parent.st_ino):
    barriers.append(True)
    if len(barriers)==1:raise OSError('conditional context directory durability failure')
   return original(fd)
  with mock.patch.object(self.manual.os,'fsync',side_effect=fail_first_context_barrier):
   first=self.manual.write_and_publish_operator_review(self.backend,record)
   self.assertEqual(first['status'],'record_written_reference_publication_unconfirmed')
   second=self.manual.write_and_publish_operator_review(self.backend,record)
  self.assertTrue(second['reference_published']);self.assertGreaterEqual(len(barriers),2)
  self.assertFalse(second['funding_consumed']);self.assertEqual(len(json.loads(self.ctx.read_text())['cash_sources']['manual_reviews']),1)
 def test_record_parent_move_during_freeze_cannot_publish_a_missing_visible_path(self):
  record=self.prepare();original=self.manual.os.link
  def move_after_link(*args,**kwargs):
   result=original(*args,**kwargs);self.records.rename(self.root/'moved-reviews');self.records.mkdir(mode=0o700);return result
  with mock.patch.object(self.manual.os,'link',side_effect=move_after_link):
   with self.assertRaises((ValueError,OSError)):self.manual.write_and_publish_operator_review(self.backend,record)
  self.assertNotIn('manual_reviews',json.loads(self.ctx.read_text())['cash_sources'])
 def test_malformed_input_is_rejected_before_live_source_reads_or_record_expansion(self):
  cases=[('topups',None),('closed_days',None),('topups',[None]),('topups',[{}]*1001),('closed_days',[{}]*1001),
   ('expected_reserve_remaining_fen',True),('expected_reserve_remaining_fen',1.5),('notes',None),('notes','')]
  for key,value in cases:
   bad=copy.deepcopy(self.input);bad[key]=value;self.manual._live_inputs.reset_mock()
   with self.subTest(key=key,value_type=type(value).__name__),self.assertRaises(ValueError):
    self.manual.prepare_operator_review(self.backend,bad,operator_id='offline',review_id='bad-input',now=self.at)
   self.manual._live_inputs.assert_not_called();self.assertEqual(list(self.records.iterdir()),[])
 def test_publication_uses_current_acceptance_time_and_never_renews_expired_prepared_record(self):
  record=self.prepare()
  with mock.patch.object(self.manual,'_now',return_value=self.at+timedelta(minutes=31),create=True):
   with self.assertRaises(ValueError):self.manual.write_and_publish_operator_review(self.backend,record)
  self.assertEqual(list(self.records.iterdir()),[]);self.assertNotIn('manual_reviews',json.loads(self.ctx.read_text())['cash_sources'])
 def test_private_source_hash_permissions_symlinks_and_mode_are_enforced(self):
  record=self.prepare();result=self.manual.write_and_publish_operator_review(self.backend,record);ref=result['reference'];path=Path(ref['path'])
  with self.assertRaises(ValueError):self.manual.load_private_manual_review(dict(ref,sha256='0'*64))
  path.chmod(0o644)
  with self.assertRaises((ValueError,OSError)):self.manual.load_private_manual_review(ref)
  path.chmod(0o600);link=self.records/'link';link.symlink_to(path)
  with self.assertRaises((ValueError,OSError)):self.manual.load_private_manual_review(dict(ref,path=str(link)))
  self.backend.config['cash_verification_mode']='broker_automatic_v1'
  with self.assertRaises(ValueError):self.prepare()

class ManualBackendTests(unittest.TestCase):
 setUp=ManualPrivateEntryTests.setUp
 prepare=ManualPrivateEntryTests.prepare
 def test_actual_backend_consumes_record_and_never_calls_automatic_bank_or_vendor_parser(self):
  record=self.prepare();self.manual.write_and_publish_operator_review(self.backend,record)
  self.backend._market_cache={'calendar':CALENDAR}
  with mock.patch('qmt_roll_weekly19_broker_evidence.load_cashflow_day_close',side_effect=AssertionError('manual mode must not call auto parser')),mock.patch('qmt_roll_weekly19_broker_evidence.load_bank_cashflow_receipt',side_effect=AssertionError('manual mode must not call bank producer')):
   updated=self.backend.reconcile_cash(self.state,dict(account=self.current),self.at)
  self.assertEqual(updated['confirmed_topup_fen'],3000000);self.assertIsNone(self.backend.cash_source_blocker)
  self.assertEqual(self.backend.reconcile_cash(updated,dict(account=self.current),self.at),updated)
 def test_cross_day_without_review_is_readable_pending_then_manual_record_unblocks(self):
  self.at=NOW.replace(month=11,day=2,hour=9,minute=1);self.current=account(balance='150000.00',deposit='30000.00',day='2026-11-02',at=self.at)
  self.manual._live_inputs.return_value=(self.state,dict(account=self.current),CALENDAR);self.manual._now.return_value=self.at
  self.backend._market_cache={'calendar':CALENDAR}
  unchanged=self.backend.reconcile_cash(self.state,dict(account=self.current),self.at)
  self.assertEqual(unchanged,self.state);self.assertIn('manual_cash_review_pending',self.backend.cash_source_blocker)
  self.input.update(closed_days=[close()],topups=[topup(self.rid,at=self.at-timedelta(seconds=1),day='2026-11-02')])
  self.manual.write_and_publish_operator_review(self.backend,self.prepare())
  updated=self.backend.reconcile_cash(self.state,dict(account=self.current),self.at)
  self.assertEqual(updated['cashflow_checkpoint']['trading_day'],'2026-11-02');self.assertEqual(updated['confirmed_topup_fen'],3000000)
  self.assertIsNone(self.backend.cash_source_blocker)
 def test_good_then_bad_reference_never_partially_consumes_or_hides_the_bad_source(self):
  result=self.manual.write_and_publish_operator_review(self.backend,self.prepare());self.backend._market_cache={'calendar':CALENDAR}
  cfg=json.loads(self.ctx.read_text());cfg['cash_sources']['manual_reviews'].append(dict(path=str(self.records/'missing'),sha256='f'*64));self.ctx.write_text(json.dumps(cfg));self.ctx.chmod(0o600)
  actual=self.backend.reconcile_cash(self.state,dict(account=self.current),self.at)
  self.assertEqual(actual,self.state);self.assertIn('manual_cash_review_pending',self.backend.cash_source_blocker)
  self.assertEqual(actual['confirmed_topup_fen'],0)

 def test_mutable_cash_json_shapes_remain_readable_pending_without_partial_credit(self):
  self.manual.write_and_publish_operator_review(self.backend,self.prepare());self.backend._market_cache={'calendar':CALENDAR}
  good=json.loads(self.ctx.read_text())
  for badref in (None,1,{},dict(path=None,sha256='f'*64),dict(path=str(self.records/'none'))):
   cfg=copy.deepcopy(good);cfg['cash_sources']['manual_reviews'].append(badref);self.ctx.write_text(json.dumps(cfg));self.ctx.chmod(0o600)
   with self.subTest(badref_type=type(badref).__name__):
    output=self.backend.reconcile_cash(self.state,dict(account=self.current),self.at)
    self.assertEqual(output,self.state);self.assertIn('manual_cash_review_pending',self.backend.cash_source_blocker)
  for badsources in (None,[],1):
   cfg=copy.deepcopy(good);cfg['cash_sources']=badsources;self.ctx.write_text(json.dumps(cfg));self.ctx.chmod(0o600)
   with self.subTest(sources_type=type(badsources).__name__):
    output=self.backend.reconcile_cash(self.state,dict(account=self.current),self.at)
    self.assertEqual(output,self.state);self.assertIn('manual_cash_review_pending',self.backend.cash_source_blocker)

 def test_missing_manual_cash_review_blocks_new_exposure_but_not_actual_position_close_gate(self):
  from test_weekly19_execution import fixture as execution_fixture,NOW as session_now,query as execution_query
  import qmt_roll_weekly19_execution as execution
  intent,context=execution_fixture();intent.update(offset='close',source='weekly19_risk_reduce',intent_kind='risk_close')
  context['broker_snapshot']['positions']=execution_query('positions',[dict(vt_symbol=intent['vt_symbol'],direction='short',volume=1)])
  waiting=self.backend.reconcile_cash(self.state,context['broker_snapshot'],session_now)
  self.assertEqual(waiting,self.state);self.assertIn('manual_cash_review_pending',self.backend.cash_source_blocker)
  context['confirmed_cash_state']=waiting
  self.assertTrue(execution.evaluate_intent(intent,context,now=session_now)['allowed'])

class ManualActorIntegrationTests(unittest.TestCase):
 def test_existing_bridge_consumes_manual_day_review_with_same_actor_and_atomic_bundle(self):
  """Actual warm reader/store/actor chain; literal authority is NOT production."""
  import test_weekly19_session_bridge as bridge_tests
  import qmt_roll_weekly19_manual_cash as manual
  import qmt_roll_weekly19_warm_evidence as warm
  import qmt_roll_weekly19_local_backend as local
  fx=bridge_tests.SessionBridgeTests('test_forged_authority_cannot_create_bridge');fx.setUp();self.addCleanup(fx.doCleanups)
  root=fx.root;records=root/'manual-reviews';records.mkdir(mode=0o700)
  cfg=dict(schema='weekly19.live-context.v1',execution_profile='weekly19-15w-r150k',cash_verification_mode='operator_manual_v1',manual_cash_review_root=str(records),
   account_key=fx.actor.account,material_release_id=fx.actor.release,state_path=str(fx.store.path),cash_sources={})
  path=root/'manual-context.json';path.write_text(json.dumps(cfg));path.chmod(0o600)
  backend=local.LocalEvidenceBackend(cfg,repo_root=ROOT,release_manifest=root/'manifest',activation_receipt=root/'activation',qualification_evidence=root/'qualification')
  backend.context_file=path;backend._market_cache={'calendar':fx.actor.calendar}
  snapshot=warm.load_warm_broker_snapshot(fx.context,**dict(fx.authority.broker_policy,now=fx.clock.at,require_production_qualification=False))
  before=copy.deepcopy(fx.bundle);cp=before['funding']['cashflow_checkpoint']
  close_at=datetime.fromisoformat(cp['observed_at'])+timedelta(hours=1)
  data=dict(topups=[],closed_days=[close(at=close_at)],expected_reserve_remaining_fen=funds.INITIAL_FEN,notes='Conditional operator-reviewed zero-cash day close')
  with mock.patch.object(manual,'_live_inputs',return_value=(before['funding'],snapshot,fx.actor.calendar)),mock.patch.object(manual,'_now',return_value=fx.clock.at):
   record=manual.prepare_operator_review(backend,data,operator_id='offline',review_id='actor-review',now=fx.clock.at)
   published=manual.write_and_publish_operator_review(backend,record)
  self.assertFalse(published['funding_consumed']);self.assertEqual(fx.store.read(),before)
  bridge=fx.make(reconcile_cash=backend.reconcile_cash)
  with mock.patch.object(type(fx.actor.strategy),'on_bars',side_effect=AssertionError('manual review must not replay alpha')):
   native=bridge.native_capture_factory(transport_context=fx.context);native.admit_completed_startup(transport_context=fx.context)
  after=fx.store.read();self.assertIs(bridge.runtime_actor,fx.actor)
  self.assertEqual(after['funding'],fx.actor.confirmed_cash_state);self.assertEqual(after['runtime'],fx.actor.export_state())
  self.assertEqual(after['funding']['cashflow_checkpoint']['trading_day'],'2026-11-02');self.assertEqual(after['funding']['confirmed_topup_fen'],0)
  self.assertIn('actor-review',after['funding']['manual_cash_reviews']);self.assertEqual(after['decision'],before['decision']);self.assertEqual(after['decision_state'],before['decision_state'])
