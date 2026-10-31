"""Synthetic CAS/journal/advice audit. No real market, broker or SMTP."""
import copy,json,os,sys,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
from vnpy.trader.setting import SETTINGS
SETTINGS['log.file']=False;SETTINGS['log.console']=False
R=Path('/Users/mac/.codex/worktrees/weekly19-official-20261031/fian');sys.path[:0]=[str(R/'examples/portfolio_backtesting'),str(R/'tests')]
import qmt_roll_weekly19_context_update as update
import qmt_roll_weekly19_quote_spool as quotes
import qmt_roll_weekly19_friday_advice as advice
import qmt_roll_weekly19_friday_report as report
import qmt_roll_weekly19_live_pipeline as pipeline
import qmt_roll_weekly19_local_backend as local
import test_weekly19_context_update as cf
import test_weekly19_quote_spool as qf
import test_weekly19_friday_advice as af
import test_weekly19_live_pipeline as lf
from qmt_roll_official_live_tick_types import DurableTickCursor

class ContextIndependent(unittest.TestCase):
 def setUp(self):
  self.fx=cf.ContextUpdateTests();self.fx.setUp();self.addCleanup(self.fx.tearDown)
 def test_renamed_parent_at_actual_replace_fails_and_visible_context_stays_original(self):
  path=self.fx.path;parent=self.fx.root;moved=parent.with_name(parent.name+'-moved');self.addCleanup(lambda:__import__('shutil').rmtree(moved,ignore_errors=True));real=update.os.replace;before=path.read_bytes();called=[]
  def swap(*a,**kw):
   parent.rename(moved);parent.mkdir(mode=0o700);path.write_bytes(before);path.chmod(0o600);called.append(True);return real(*a,**kw)
  with patch.object(update.os,'replace',side_effect=swap):
   with self.assertRaisesRegex(update.ContextUpdateError,'parent_identity_changed'):self.fx.advance()
  self.assertTrue(called);self.assertEqual(path.read_bytes(),before)
 def test_parent_replaced_at_leaf_open_fails_before_any_visible_advance(self):
  path=self.fx.path;parent=self.fx.root;moved=parent.with_name(parent.name+'-moved-read');self.addCleanup(lambda:__import__('shutil').rmtree(moved,ignore_errors=True));real=update.os.open;before=path.read_bytes();called=[]
  def swap(name,flags,*a,**kw):
   if name==path.name and kw.get('dir_fd')is not None and not called:
    parent.rename(moved);parent.mkdir(mode=0o700);path.write_bytes(before);path.chmod(0o600);called.append(True)
   return real(name,flags,*a,**kw)
  with patch.object(update.os,'open',side_effect=swap):
   with self.assertRaisesRegex(update.ContextUpdateError,'parent_identity_changed'):self.fx.advance()
  self.assertTrue(called);self.assertEqual(path.read_bytes(),before)
 def test_stale_expected_market_is_cas_failure_but_latest_cash_fields_are_preserved(self):
  current=copy.deepcopy(self.fx.cfg);current['cash_sources']={'deposits':[{'native_receipt':'latest'}]};current['mail_outbox']='newest-private-outbox';self.fx.write(current)
  out=self.fx.advance();self.assertEqual(out['cash_sources'],current['cash_sources']);self.assertEqual(out['mail_outbox'],current['mail_outbox'])
  before=self.fx.path.read_bytes()
  with self.assertRaisesRegex(update.ContextUpdateError,'market_generation_changed'):self.fx.advance()
  self.assertEqual(before,self.fx.path.read_bytes())
 def test_concurrent_same_generation_has_one_winner_without_lost_cash(self):
  current=copy.deepcopy(self.fx.cfg);current['cash_sources']={'source':'newest'};self.fx.write(current);barrier=threading.Barrier(3);result=[]
  def worker(label):
   barrier.wait()
   try:self.fx.advance(new_market={'asset_root':label});result.append(('ok',label))
   except update.ContextUpdateError as e:result.append(('blocked',str(e)))
  threads=[threading.Thread(target=worker,args=(label,))for label in ['generation-A','generation-B']]
  for t in threads:t.start()
  barrier.wait()
  for t in threads:t.join(5);self.assertFalse(t.is_alive())
  self.assertEqual(sum(r[0]=='ok'for r in result),1,result);self.assertEqual(sum(r[0]=='blocked'for r in result),1,result)
  self.assertEqual(local.private_json(self.fx.path)['cash_sources'],{'source':'newest'})
 def test_context_and_lock_hardlinks_or_duplicate_json_cannot_be_admitted(self):
  alias=self.fx.root/'alias';os.link(self.fx.path,alias)
  with self.assertRaises(update.ContextUpdateError):self.fx.advance()
  alias.unlink();self.fx.path.write_text('{"schema":"a","schema":"b"}');self.fx.path.chmod(0o600)
  with self.assertRaises(ValueError):self.fx.advance()

class QuoteIndependent(unittest.TestCase):
 def setUp(self):
  self.fx=qf.Weekly19QuoteSpoolTest();self.fx.setUp();self.addCleanup(self.fx.doCleanups);quotes._QUOTE_CACHE.clear()
 def read(self,cursor=None):return quotes.read_weekly19_quote_snapshot(self.fx.path,durable_through=cursor or self.fx.cursor,symbol='rb2701.SHFE',clock=self.fx.clock,trading_date='2026-11-02',session={'trading_date':'2026-11-02','session_id':'offline-fixture'})
 def test_cache_hit_rehashes_actual_bytes_and_does_not_decode_again(self):
  first=self.read();original=quotes._prefix_digest;calls=[]
  def measured(*a):calls.append(a[1]);return original(*a)
  with patch.object(quotes,'_prefix_digest',side_effect=measured),patch.object(quotes.TickStreamJournalReader,'read_after',side_effect=AssertionError('should reuse decoded rows')):
   again=self.read()
  self.assertTrue(calls);self.assertEqual(first,again);again['ask']=-1;self.assertEqual(self.read()['ask'],4000.)
 def test_same_size_mtime_restored_rewrite_cannot_pass_cached_prefix(self):
  self.read();before=self.fx.path.stat();raw=self.fx.path.read_bytes();index=raw.index(b'4000.0')
  with self.fx.path.open('r+b')as stream:stream.seek(index);stream.write(b'4001.0');stream.flush();os.fsync(stream.fileno())
  os.utime(self.fx.path,ns=(before.st_atime_ns,before.st_mtime_ns));after=self.fx.path.stat();self.assertEqual(after.st_size,before.st_size);self.assertEqual(after.st_mtime_ns,before.st_mtime_ns)
  with self.assertRaisesRegex(ValueError,'journal_changed'):self.read()
 def test_committed_old_cursor_ignores_tail_but_tail_cannot_become_durable(self):
  initial=self.read()
  with self.fx.path.open('ab')as stream:stream.write(b'{not-a-completed-commit');stream.flush();os.fsync(stream.fileno())
  self.assertEqual(self.read(),initial)
  forged=DurableTickCursor(self.fx.cursor.feed_session_id,self.fx.cursor.ingress_sequence+1,self.fx.path.stat().st_size,self.fx.cursor.journal_schema)
  with self.assertRaises(ValueError):self.read(forged)
 def test_new_cursor_checks_old_admitted_prefix_before_incremental_reuse(self):
  self.read();tick=SimpleNamespace(vt_symbol='rb2701.SHFE',symbol='rb2701',exchange='SHFE',datetime=qf.NOW,last_price=4001.,bid_price_1=4000.,ask_price_1=4001.,bid_volume_1=10,ask_volume_1=10)
  self.fx.pipeline.capture_ingress(tick);self.assertTrue(self.fx.pipeline.wait_until_durable(2,timeout_seconds=2));snap=self.fx.pipeline.durable_snapshot();new=DurableTickCursor(snap.feed_session_id,snap.durable_ingress_sequence,snap.durable_journal_byte_offset,snap.journal_schema)
  raw=self.fx.path.read_bytes();index=raw.index(b'4000.0')
  with self.fx.path.open('r+b')as stream:stream.seek(index);stream.write(b'3999.0')
  with self.assertRaisesRegex(ValueError,'journal_changed'):self.read(new)
 def test_monotonic_expiry_still_rejects_valid_cached_epoch_quote(self):
  self.read();self.fx.clock.mono+=10**12
  with self.assertRaises(ValueError):self.read()

class AdviceIndependent(unittest.TestCase):
 def test_changed_gap_retires_only_unpaid_offer_without_mutating_origin_or_credit(self):
  bundle,_=af.make_bundle();before=copy.deepcopy(bundle);account=af.broker(balance='130000.00',now=af.NOW)['account'];out=advice.refresh_friday_advice(bundle,account,af.NOW)
  self.assertEqual(bundle,before);self.assertEqual(out['recommendation']['amount_fen'],2000000);self.assertEqual(len(out['funding']['requests']),2)
  self.assertEqual(out['funding']['confirmed_topup_fen'],0);self.assertEqual(out['funding']['reserve_remaining_fen'],15000000);self.assertEqual(set(out['funding']['retirements']),set(bundle['funding']['requests']))
 def test_confirmed_portfolio_batch_does_not_offer_again_after_market_loss(self):
  bundle,obj=af.make_bundle(two=True);paid,_,at=af.confirm(bundle,obj,amount='30000.00',equity='150000.00');later=at+af.timedelta(minutes=1);snapshot=af.broker(balance='120000.00',now=later);raw=json.loads(snapshot['account']['raw_payload']);raw['Deposit']='30000.00';snapshot['account']=af.envelope(raw)
  out=advice.refresh_friday_advice(paid,snapshot['account'],later);self.assertEqual(out['recommendation']['amount_fen'],0);self.assertFalse(out['recommendation']['actionable']);self.assertEqual(len(out['funding']['requests']),1);self.assertEqual(out['funding']['confirmed_topup_fen'],3000000)
 def test_unknown_day_close_blocks_advice_with_original_cash_unchanged(self):
  bundle,_=af.make_bundle(holiday=True);before=copy.deepcopy(bundle);account=af.broker(day='2026-10-30',now=af.NOW)['account'];out=advice.refresh_friday_advice(bundle,account,af.NOW)
  self.assertEqual(out['status'],'blocked');self.assertEqual(out['funding'],before['funding']);self.assertEqual(bundle,before);self.assertFalse(out['recommendation']['actionable'])
 def test_holiday_advice_origin_never_reruns_strategy_or_changes_decision(self):
  bundle,obj=af.make_bundle(holiday=True);before=copy.deepcopy(bundle);account=af.broker(balance='120000.00',day='2026-10-29',now=af.NOW)['account']
  with patch.object(type(obj.strategy),'on_bars',side_effect=AssertionError('no replay')):out=advice.refresh_friday_advice(bundle,account,af.NOW)
  self.assertEqual(out['status'],'ready');self.assertEqual(out['source_bindings']['original_target_date'],'2026-10-29');self.assertEqual(bundle,before);self.assertEqual(out['recommendation']['amount_fen'],3000000)
if __name__=='__main__':unittest.main(verbosity=2)
