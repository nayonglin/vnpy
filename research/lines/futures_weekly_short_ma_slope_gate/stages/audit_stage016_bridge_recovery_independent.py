"""Offline independent bridge recovery/poison tests. No native API calls."""
from pathlib import Path
import os, stat, sys, unittest
from unittest import mock
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT),str(ROOT/'tests'),str(ROOT/'examples/portfolio_backtesting')]
from vnpy.trader.setting import SETTINGS
SETTINGS['log.file']=False;SETTINGS['log.console']=False
import tests.test_weekly19_session_bridge as fixtures
import qmt_roll_weekly19_pipeline_state as state
import qmt_roll_weekly19_warm_evidence as warm

class BridgeRecoveryIndependent(unittest.TestCase):
 def setUp(self):
  self.fx=fixtures.SessionBridgeTests('test_forged_authority_cannot_create_bridge');self.fx.setUp();self.addCleanup(self.fx.doCleanups)
  self.bridge=self.fx.make();self.actor=self.fx.actor
 def mutate(self,section):
  self.actor.open_block_reason='independent_recovery_probe';self.actor.revision+=1;section['independent_probe']=True
 def test_pretransaction_failure_reads_actual_old_state_and_remains_usable(self):
  before=self.actor.export_state()
  with mock.patch.object(self.fx.store,'transact',side_effect=OSError('pre_transaction_failure')):
   with self.assertRaisesRegex(OSError,'pre_transaction_failure'):self.bridge._commit(self.mutate)
  self.assertEqual(self.actor.export_state(),before)
  self.assertEqual(self.bridge.last_bundle,self.fx.store.read())
  self.assertIsNone(self.bridge._poison_reason)
  self.bridge._commit(self.mutate)
  self.assertEqual(self.actor.export_state(),self.fx.store.read()['runtime'])
 def test_postreplace_failure_reads_actual_new_state_but_never_acknowledges_success(self):
  before=self.actor.export_state();fsync=os.fsync;injected=[]
  def fail_directory(fd):
   if stat.S_ISDIR(os.fstat(fd).st_mode):injected.append(True);raise OSError('post_replace_directory_fsync')
   return fsync(fd)
  with mock.patch.object(state.os,'fsync',side_effect=fail_directory):
   with self.assertRaisesRegex(OSError,'post_replace_directory_fsync'):self.bridge._commit(self.mutate)
  actual=self.fx.store.read();self.assertEqual(injected,[True]);self.assertNotEqual(actual['runtime'],before)
  self.assertEqual(self.actor.export_state(),actual['runtime']);self.assertEqual(self.bridge.last_bundle,actual)
  self.assertIsNone(self.bridge._poison_reason)
  self.bridge._commit(lambda section:section.update(after_recovery=True))
  self.assertTrue(self.fx.store.read()['session_bridge']['after_recovery'])
 def test_failed_readback_preserves_original_error_and_poison_stops_commit_source_and_native(self):
  with mock.patch.object(self.fx.store,'transact',side_effect=OSError('original_failure')),mock.patch.object(self.fx.store,'read',side_effect=OSError('readback_failure')):
   with self.assertRaisesRegex(OSError,'original_failure'):self.bridge._commit(self.mutate)
  operation=mock.Mock()
  with self.assertRaisesRegex(ValueError,'owner_poisoned'):self.bridge._commit(operation)
  operation.assert_not_called()
  with mock.patch.object(warm,'load_warm_broker_snapshot',side_effect=AssertionError('must_not_admit'))as loader:
   with self.assertRaisesRegex(ValueError,'owner_poisoned'):self.bridge._snapshot(self.fx.context)
  loader.assert_not_called()
  with self.assertRaisesRegex(ValueError,'owner_poisoned'):self.bridge.native_capture_factory(transport_context=self.fx.context)
  self.assertIsNone(self.bridge.native)
 def test_failed_restore_also_poisoned(self):
  with mock.patch.object(self.fx.store,'transact',side_effect=OSError('original_failure')),mock.patch.object(self.actor,'_restore',side_effect=ValueError('restore_failure')):
   with self.assertRaisesRegex(OSError,'original_failure'):self.bridge._commit(self.mutate)
  with self.assertRaisesRegex(ValueError,'owner_poisoned'):self.bridge._assert_authority()

if __name__=='__main__':unittest.main(defaultTest='BridgeRecoveryIndependent')
