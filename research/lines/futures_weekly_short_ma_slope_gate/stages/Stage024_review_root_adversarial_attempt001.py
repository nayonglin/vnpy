"""Independent malformed-input/CLI checks. Synthetic fixtures; no native services."""
import contextlib,copy,io,json,sys,types,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'examples/portfolio_backtesting'),str(ROOT/'tests')]
import qmt_roll_weekly19_startup as startup
import run_qmt_roll_weekly19_live as cli
from test_weekly19_startup_policy import StartupPolicyTests,PROFILE
class RootMalformedBoundary(unittest.TestCase):
 def setUp(self):
  self.case=StartupPolicyTests();self.case.setUp();self.addCleanup(self.case.doCleanups)
 def badconfig(self,value):
  cfg=copy.deepcopy(self.case.config);cfg['startup_authorization']=self.case.write('malformed-auth.json',value);return cfg
 def test_public_authorization_rejects_nonobject_with_valueerror(self):
  for value in (None,7,[],[{}]):
   with self.subTest(shape=type(value).__name__),self.assertRaises(ValueError):startup.load_startup_authorization(self.badconfig(value))
 def test_actual_cli_returns_sanitized_blocked_json_on_malformed_authorization(self):
  cfg=self.badconfig(None);out=io.StringIO()
  args=['--job','initialize-existing-account','--execution-profile',PROFILE,'--context-file','/private/tmp/synthetic-context.json','--release-manifest','/private/tmp/synthetic-manifest.json','--activation-receipt','/private/tmp/synthetic-activation.json','--production-qualification-evidence','/private/tmp/synthetic-qualification.json']
  # Constructor is replaced ONLY to exercise JSON boundary; no production or
  # provider capability is fabricated and no initializer is reached.
  with patch.object(cli,'private_json',return_value=cfg),patch.object(cli,'LocalEvidenceBackend',return_value=types.SimpleNamespace(external_action_started=False)),patch.object(cli,'initialize_weekly19_existing_account',side_effect=AssertionError('must not initialize')),contextlib.redirect_stdout(out):
   result=cli.main(args)
  self.assertEqual(result,2);body=json.loads(out.getvalue());self.assertEqual(body['status'],'blocked');self.assertNotIn('Traceback',out.getvalue())
 def test_valid_private_policy_and_snapshot_control(self):
  policy=startup.load_startup_authorization(self.case.config);self.assertEqual(policy['operator_decision_id'],self.case.config['startup_authorization']['sha256']);self.case.assert_snapshot(policy)
if __name__=='__main__':unittest.main(verbosity=2)
