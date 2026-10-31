"""Offline CLI adversarial parsing; source gate fixtures are not qualification."""
from pathlib import Path
import contextlib,copy,io,json,sys,unittest
from unittest import mock
ROOT=Path(__file__).resolve().parents[4];sys.path[:0]=[str(ROOT),str(ROOT/'tests'),str(ROOT/'examples/portfolio_backtesting')]
import tests.test_weekly19_manual_cash as fixtures
import run_qmt_roll_weekly19_manual_cash as cli
class ManualCliIndependent(unittest.TestCase):
 def setUp(self):
  self.fx=fixtures.ManualPrivateEntryTests('test_prepared_record_is_private_and_only_cash_reference_is_published');self.fx.setUp();self.addCleanup(self.fx.doCleanups)
  self.base=['--execution-profile','weekly19-15w-r150k','--context-file',str(self.fx.ctx),'--release-manifest',str(self.fx.root/'release'),'--activation-receipt',str(self.fx.root/'activation'),'--production-qualification-evidence',str(self.fx.root/'qualification')]
  self.confirm=['--action','confirm','--review-input',str(self.fx.root/'input.json'),'--operator-id','offline','--review-id','cli-independent','--confirm',cli.OPERATOR_CASH_ASSERTION]
 def invoke(self,review):
  out=io.StringIO();fake_time=mock.Mock();fake_time.now.return_value=self.fx.at
  with contextlib.redirect_stdout(out),mock.patch.object(cli,'datetime',fake_time),mock.patch.object(cli,'LocalEvidenceBackend',return_value=self.fx.backend),mock.patch.object(cli,'private_json',side_effect=lambda p:review if p.name=='input.json'else self.fx.cfg):
   code=cli.main(self.base+self.confirm)
  return code,json.loads(out.getvalue())
 def test_malformed_topup_container_returns_redacted_blocked_without_publication(self):
  bad=copy.deepcopy(self.fx.input);bad['topups']=None;bad['notes']='PRIVATE_OPERATOR_NOTE_NOT_FOR_ERROR'
  try:code,result=self.invoke(bad)
  except BaseException as exc:self.fail('CLI leaked an uncaught '+type(exc).__name__+' for ordinary malformed JSON container')
  self.assertEqual(code,2);self.assertEqual(result['status'],'blocked');self.assertNotIn('PRIVATE_OPERATOR_NOTE_NOT_FOR_ERROR',json.dumps(result));self.assertEqual(list(self.fx.records.iterdir()),[])
if __name__=='__main__':unittest.main(defaultTest='ManualCliIndependent')
