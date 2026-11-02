"""Read-only weekly capture uses formal env/framework and quoted fixed args."""
import sys,unittest,shlex
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'examples/portfolio_backtesting'))
import run_qmt_roll_stage907_official_live_readonly_refresh_gate as refresh
class ReadonlyCommandTest(unittest.TestCase):
 def test_weekly_native_capture_preserves_production_environment_and_escaping(self):
  opts=('--weekly19-material-release-id','weekly-release','--weekly19-execution-profile','weekly19-15w-r150k','--weekly19-private-capture-dir','/private/tmp/space dir/$(not-shell)')
  cmd,plan=refresh._command_for_profile('production-live',30,'fixture-invocation',weekly19_capture_options=opts)
  self.assertEqual(cmd[:2],['bash','-lc']);self.assertIn('ctp_live.local.env',plan);self.assertIn('vnpy_ctp/api/libs',plan)
  last=shlex.split(plan.splitlines()[-1]);self.assertEqual(last[-6:],list(opts));self.assertNotIn('ctp_broker_test.local.env',plan)
 def test_optional_raw_settlement_query_keeps_same_readonly_firewall_and_private_capture(self):
  opts=('--weekly19-material-release-id','candidate','--weekly19-execution-profile','weekly19-15w-r150k','--weekly19-private-capture-dir','/private/tmp/private','--weekly19-settlement-trading-day','20261030')
  cmd,plan=refresh._command_for_profile('production-live',45,'literal-fixture',weekly19_capture_options=opts)
  self.assertEqual(shlex.split(plan.splitlines()[-1])[-8:],list(opts));self.assertIn('--connect',plan)
 def test_weekly_capture_cannot_enter_simnow_or_broker_test_wrapper(self):
  for profile in ['simnow','broker-test']:
   with self.assertRaisesRegex(ValueError,'requires_production_live_env'):refresh._command_for_profile(profile,30,'fixture',weekly19_capture_options=('--weekly19-execution-profile','weekly19-15w-r150k'))
 def test_unknown_option_or_odd_tuple_cannot_enable_mutation(self):
  for opts in [('--connect','1'),('--send-order','1'),('--weekly19-material-release-id',)]:
   with self.assertRaisesRegex(ValueError,'capture_options_invalid'):refresh._production_live_command(30,'fixture',weekly19_capture_options=opts)
 def test_existing_non_weekly_command_bytes_stay_identical(self):
  self.assertEqual(refresh._production_live_command(30,'fixture'),refresh._production_live_command(30,'fixture',weekly19_capture_options=()))
if __name__=='__main__':unittest.main()
