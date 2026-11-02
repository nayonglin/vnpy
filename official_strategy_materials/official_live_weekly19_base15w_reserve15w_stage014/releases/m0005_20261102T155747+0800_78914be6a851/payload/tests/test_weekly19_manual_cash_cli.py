"""Manual CLI dispatch fixtures; no production, CTP, bank, SMTP or orders."""
import contextlib
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock,patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'examples/portfolio_backtesting'))
import run_qmt_roll_weekly19_manual_cash as cli

class ManualCashCliTest(unittest.TestCase):
 def setUp(self):
  self.backend=Mock()
  self.cfg=dict(schema='weekly19.live-context.v1',cash_verification_mode='operator_manual_v1')
  self.base=['--execution-profile','weekly19-15w-r150k','--context-file','/literal/private/context.json',
   '--release-manifest','/literal/private/release.json','--activation-receipt','/literal/private/activation.json',
   '--production-qualification-evidence','/literal/private/qualification.json']
 def run_cli(self,extra,*,read=None):
  output=io.StringIO()
  with contextlib.redirect_stdout(output),patch.object(cli,'private_json',side_effect=read or(lambda p:self.cfg))as reader,\
   patch.object(cli,'LocalEvidenceBackend',return_value=self.backend)as factory:
   code=cli.main(self.base+extra)
  return code,json.loads(output.getvalue()),reader,factory
 def test_status_binds_actual_source_paths_and_does_not_publish(self):
  with patch.object(cli,'manual_cash_status',return_value={'status':'manual_cash_review_pending'})as status,\
   patch.object(cli,'prepare_operator_review')as prepare,patch.object(cli,'write_and_publish_operator_review')as publish:
   code,result,reader,factory=self.run_cli(['--action','status'])
  self.assertEqual(code,0);self.assertEqual(result['status'],'manual_cash_review_pending')
  self.assertEqual(self.backend.context_file,Path('/literal/private/context.json'))
  self.assertFalse(factory.call_args.kwargs['preview'])
  self.assertEqual(factory.call_args.kwargs['repo_root'],ROOT)
  self.assertEqual(factory.call_args.kwargs['release_manifest'],Path('/literal/private/release.json'))
  self.assertEqual(status.call_count,1);self.assertIs(status.call_args.args[0],self.backend)
  self.assertIsNotNone(status.call_args.kwargs['now'].tzinfo)
  prepare.assert_not_called();publish.assert_not_called();self.assertEqual(reader.call_count,1)
 def confirm_args(self):
  return ['--action','confirm','--review-input','/literal/private/review-input.json','--operator-id','operator-fixture',
   '--review-id','review-fixture','--confirm',cli.OPERATOR_CASH_ASSERTION]
 def test_confirm_reads_private_input_and_reports_pending_actor_only(self):
  review={'topups':[],'closed_days':[],'expected_reserve_remaining_fen':15000000,'notes':'fixture'}
  envelope={'schema':'weekly19.operator-cash-review.v1','raw_sha256':'a'*64}
  response=dict(status='record_written_pending_actor_consumption',reference={'path':'/literal/record.json','sha256':'a'*64},funding_consumed=False)
  with patch.object(cli,'prepare_operator_review',return_value=envelope)as prepare,\
   patch.object(cli,'write_and_publish_operator_review',return_value=response)as publish:
   code,result,reader,_=self.run_cli(self.confirm_args(),read=lambda p:review if p.name=='review-input.json'else self.cfg)
  self.assertEqual(code,0);self.assertEqual(result,response);self.assertFalse(result['funding_consumed'])
  self.assertEqual(prepare.call_args.args,(self.backend,review))
  self.assertEqual(prepare.call_args.kwargs['operator_id'],'operator-fixture')
  self.assertEqual(prepare.call_args.kwargs['review_id'],'review-fixture')
  publish.assert_called_once_with(self.backend,envelope)
  self.assertEqual(reader.call_args_list[-1].args,(Path('/literal/private/review-input.json'),))
 def test_incomplete_or_wrong_confirmation_never_opens_private_context(self):
  cases=[['--action','confirm'],self.confirm_args()[:-1]+['wrong-confirmation'],
   ['--action','confirm','--confirm',cli.OPERATOR_CASH_ASSERTION]]
  for extra in cases:
   with self.subTest(extra=extra),patch.object(cli,'write_and_publish_operator_review')as publish:
    code,result,reader,factory=self.run_cli(extra)
    self.assertEqual(code,2);self.assertEqual(result['status'],'blocked')
    reader.assert_not_called();factory.assert_not_called();publish.assert_not_called()
 def test_private_input_failure_never_prepares_or_publishes_and_does_not_leak(self):
  def read(path):
   if path.name=='review-input.json':raise ValueError('SECRET_ACCOUNT_OR_NOTES')
   return self.cfg
  with patch.object(cli,'prepare_operator_review')as prepare,patch.object(cli,'write_and_publish_operator_review')as publish:
   code,result,_,_=self.run_cli(self.confirm_args(),read=read)
  self.assertEqual(code,2);self.assertNotIn('SECRET_ACCOUNT_OR_NOTES',json.dumps(result))
  prepare.assert_not_called();publish.assert_not_called()
 def test_status_exception_never_claims_ready_or_cash_consumed(self):
  with patch.object(cli,'manual_cash_status',side_effect=RuntimeError('SECRET_RAW_SOURCE')):
   code,result,_,_=self.run_cli(['--action','status'])
  self.assertEqual(code,2);self.assertEqual(result['status'],'blocked')
  self.assertNotIn('SECRET_RAW_SOURCE',json.dumps(result));self.assertNotIn('funding_consumed',result)
 def test_malformed_nested_review_is_blocked_without_traceback_or_private_text(self):
  with patch.object(cli,'prepare_operator_review',side_effect=TypeError('SECRET_NESTED_INPUT'))as prepare,\
   patch.object(cli,'write_and_publish_operator_review')as publish:
   code,result,_,_=self.run_cli(self.confirm_args())
  self.assertEqual(code,2);self.assertEqual(result['status'],'blocked')
  self.assertNotIn('SECRET_NESTED_INPUT',json.dumps(result));self.assertEqual(prepare.call_count,1)
  publish.assert_not_called()
 def test_relative_context_or_input_is_rejected_before_loading(self):
  with patch.object(cli,'private_json')as reader,contextlib.redirect_stdout(io.StringIO()):
   args=list(self.base);args[3]='relative-context.json'
   self.assertEqual(cli.main(args+['--action','status']),2)
   extra=self.confirm_args();extra[3]='relative-input.json'
   self.assertEqual(cli.main(self.base+extra),2)
  reader.assert_not_called()

if __name__=='__main__':unittest.main()
