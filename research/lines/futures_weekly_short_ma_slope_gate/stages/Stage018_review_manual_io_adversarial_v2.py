"""Offline private-record parent identity and publication probe."""
from pathlib import Path
import copy,os,sys,unittest
from unittest import mock
ROOT=Path(__file__).resolve().parents[4];sys.path[:0]=[str(ROOT),str(ROOT/'tests'),str(ROOT/'examples/portfolio_backtesting')]
import tests.test_weekly19_manual_cash as fixture
class ManualIOIndependent(unittest.TestCase):
 def setUp(self):
  self.fx=fixture.ManualPrivateEntryTests('test_prepared_record_is_private_and_only_cash_reference_is_published');self.fx.setUp();self.addCleanup(self.fx.doCleanups)
 def test_renamed_record_parent_cannot_publish_success_for_a_missing_visible_record(self):
  record=self.fx.prepare();real_link=os.link;moved=self.fx.root/'moved-reviews';swapped=[]
  def move_after_link(*args,**kw):
   result=real_link(*args,**kw)
   if not swapped:
    self.fx.records.rename(moved);self.fx.records.mkdir(mode=0o700);swapped.append(True)
   return result
  with mock.patch.object(self.fx.manual.os,'link',side_effect=move_after_link):
   try:result=self.fx.manual.write_and_publish_operator_review(self.fx.backend,record)
   except (ValueError,OSError):return
  self.assertFalse(result.get('reference_published')is True and not Path(result['reference']['path']).is_file(),
    'CLI reported reference publication success for an already-missing visible manual record')
 def test_retry_after_context_directory_fsync_failure_retries_that_durability_barrier(self):
  record=self.fx.prepare();real_fsync=os.fsync;parent=os.stat(self.fx.root);root_sync=[]
  def fail_first_root_fsync(fd):
   info=os.fstat(fd)
   if (info.st_dev,info.st_ino)==(parent.st_dev,parent.st_ino):
    root_sync.append(True)
    if len(root_sync)==1:raise OSError('independent_context_directory_fsync_failure')
   return real_fsync(fd)
  with mock.patch.object(self.fx.manual.os,'fsync',side_effect=fail_first_root_fsync):
   first=self.fx.manual.write_and_publish_operator_review(self.fx.backend,record)
   self.assertEqual(first['status'],'record_written_reference_publication_unconfirmed')
   second=self.fx.manual.write_and_publish_operator_review(self.fx.backend,record)
  self.assertTrue(second['reference_published']);self.assertGreaterEqual(len(root_sync),2,
    'Existing reference retry skipped context directory fsync and falsely upgraded unknown durability to success')
if __name__=='__main__':unittest.main(defaultTest='ManualIOIndependent')
