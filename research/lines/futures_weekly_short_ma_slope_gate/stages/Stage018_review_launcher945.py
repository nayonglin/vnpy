"""Independent launcher source/calendar boundaries; never executes child process."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import copy,hashlib,json,sys,tempfile,unittest
from unittest import mock
ROOT=Path(__file__).resolve().parents[4];sys.path[:0]=[str(ROOT),str(ROOT/'tests'),str(ROOT/'examples/portfolio_backtesting')]
import tests.test_stage945_production_launcher as fixtures
import run_qmt_roll_stage945_official_live_production_session_launcher as launcher
from qmt_roll_official_execution_profile import WEEKLY19_15W_R150K_PROFILE
class Launcher945Independent(unittest.TestCase):
 def setUp(self):
  self.fx=fixtures.Weekly19TargetRoutingTest('test_weekly_target_never_calls_stage922_or_old_mapping_calendar');self.fx.setUp();self.addCleanup(self.fx.doCleanups)
 def test_1630_boundary_reselects_target_and_rejects_stale_pre_boundary_payload(self):
  early=self.fx.monday.replace(hour=16,minute=29,second=59);target,payload=self.fx.resolve(early);self.assertEqual(target,'2026-10-30')
  later=early.replace(minute=30,second=0);target2,_=self.fx.resolve(later);self.assertEqual(target2,'2026-11-02')
  with self.assertRaises(launcher.ProductionSessionLaunchError):launcher._validate_target_date_calendar_window(receipt=self.fx.receipt(),resolver_payload=payload,now=later)
 def test_context_cash_refs_can_change_but_account_release_mode_cannot_rebind_old_proof(self):
  target,payload=self.fx.resolve();self.fx.cfg['cash_sources']={'manual_reviews':[{'path':'UNADMITTED','sha256':'b'*64}]};self.fx.write_context();self.assertTrue(launcher._target_is_before_live_shadow_start(target_date=target,resolver_payload=payload))
  for key,value in [('account_key','f'*64),('material_release_id','other'),('cash_verification_mode','operator_manual_v1')]:
   old=copy.deepcopy(self.fx.cfg);self.fx.cfg[key]=value;self.fx.write_context()
   with self.subTest(key=key),self.assertRaises(launcher.ProductionSessionLaunchError):launcher._target_is_before_live_shadow_start(target_date=target,resolver_payload=payload)
   self.fx.cfg=old;self.fx.write_context()
 def test_all_five_source_pin_drift_and_future_or_naive_clock_are_rejected(self):
  for name in ('daily.sqlite','mapping.csv','physical_epoch_daily.csv','metadata.csv','receipt.json'):
   path=self.fx.assets/name;raw=path.read_bytes();path.write_bytes(raw+b' drift')
   with self.subTest(source=name),self.assertRaises(launcher.ProductionSessionLaunchError):self.fx.resolve()
   path.write_bytes(raw)
  _,payload=self.fx.resolve(self.fx.monday.replace(minute=1))
  with self.assertRaises(launcher.ProductionSessionLaunchError):launcher._validate_target_date_calendar_window(receipt=self.fx.receipt(),resolver_payload=payload,now=self.fx.monday)
  with self.assertRaises(launcher.ProductionSessionLaunchError):self.fx.resolve(self.fx.monday.replace(tzinfo=None))
 def test_forged_c9_receipt_or_next_session_cannot_authorize_weekly(self):
  _,payload=self.fx.resolve()
  for field,value in [('execution_profile','c9-15w'),('material_release_id','old-m8'),('target_cutoff_date','2026-10-29')]:
   bad=self.fx.receipt();bad[field]=value
   with self.subTest(field=field),self.assertRaises(launcher.ProductionSessionLaunchError):launcher._validate_target_date_calendar_window(receipt=bad,resolver_payload=payload,now=self.fx.monday)
  with mock.patch.object(launcher.subprocess,'run',side_effect=AssertionError('No Stage922/CTP subprocess')):self.fx.resolve()
 def test_expired_forward_calendar_cannot_be_replaced_with_weekday_guess(self):
  raw='date\n2026-10-29\n2026-10-30\n2026-11-02\n';self.fx.calendar.write_text(raw);self.fx.pins['forward_calendar.csv']=hashlib.sha256(raw.encode()).hexdigest();self.fx.write_context()
  with self.assertRaises(launcher.ProductionSessionLaunchError):self.fx.resolve()
 def test_actual_inactive_market_generation_resolves_monday_without_broker_or_legacy_source(self):
  proof=json.loads((ROOT/'research/lines/futures_weekly_short_ma_slope_gate/stages/Stage018_review_launcher945_source_proof.json').read_text());market=proof['actual_market_calendar']
  with tempfile.TemporaryDirectory(dir='/private/tmp')as temp:
   runtime=Path(temp).resolve();runtime.chmod(0o700);path=runtime/'weekly19/context.json';path.parent.mkdir(mode=0o700)
   cfg=dict(schema='weekly19.live-context.v1',execution_profile=WEEKLY19_15W_R150K_PROFILE.profile_key,account_key='a'*64,material_release_id='INDEPENDENT_ACTUAL_CALENDAR_NOT_ACCOUNT',cold_start_date='2026-11-01',market_data=market,cash_sources={});path.write_text(json.dumps(cfg));path.chmod(0o600)
   with mock.patch.object(launcher,'PRODUCTION_RUNTIME_ROOT',runtime),mock.patch.object(launcher.subprocess,'run',side_effect=AssertionError('No external calls')):
    target,payload=launcher._resolve_target_date({},now=self.fx.monday);self.assertEqual(target,'2026-10-30');self.assertTrue(launcher._target_is_before_live_shadow_start(target_date=target,resolver_payload=payload));self.assertEqual(payload['resolver_evidence']['next_trading_session_date'],'2026-11-02')
if __name__=='__main__':unittest.main(defaultTest='Launcher945Independent')
