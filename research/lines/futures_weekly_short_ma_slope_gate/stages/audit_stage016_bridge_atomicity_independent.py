"""Offline independent injected post-replace directory-fsync failure probe."""
from pathlib import Path
import hashlib, json, os, stat, sys, unittest
from unittest import mock
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT),str(ROOT/'examples/portfolio_backtesting')]
from vnpy.trader.setting import SETTINGS
SETTINGS['log.file']=False
SETTINGS['log.console']=False
from tests.test_weekly19_session_bridge import SessionBridgeTests
import qmt_roll_weekly19_pipeline_state as state

class BridgeAtomicityIndependent(unittest.TestCase):
 def test_post_replace_fsync_failure_preserves_actor_store_consistency(self):
  fixture=SessionBridgeTests('test_forged_authority_cannot_create_bridge')
  fixture.setUp()
  try:
   bridge=fixture.make()
   actor=fixture.actor
   before=actor.export_state()
   original_fsync=os.fsync
   injected=[]
   def fsync(fd):
    if stat.S_ISDIR(os.fstat(fd).st_mode):
     injected.append('post_replace_directory_fsync')
     raise OSError('independent_post_replace_directory_fsync')
    return original_fsync(fd)
   def mutate(section):
    actor.open_block_reason='independent_post_replace_probe'
    actor.revision+=1
    section['independent_probe']='post_replace'
   with mock.patch.object(state.os,'fsync',side_effect=fsync):
    with self.assertRaisesRegex(OSError,'independent_post_replace_directory_fsync'):
     bridge._commit(mutate)
   actual=fixture.store.read()
   current=actor.export_state()
   self.assertEqual(injected,['post_replace_directory_fsync'])
   self.assertNotEqual(actual['runtime']['state_sha256'],before['state_sha256'])
   self.assertEqual(current['state_sha256'],actual['runtime']['state_sha256'],
    'Post-replace failure left durable new runtime but rolled actor back to old runtime')
  finally:
   fixture.doCleanups()

if __name__=='__main__':unittest.main()
