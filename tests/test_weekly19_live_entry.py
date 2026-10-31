"""Entry-gate, private-context and service-lifetime checks; no network."""
import json,os,sys,tempfile,unittest
from datetime import datetime,timedelta
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'examples/portfolio_backtesting'))
from qmt_roll_weekly19_local_backend import LocalEvidenceBackend,LocalBackendError,private_json
from qmt_roll_official_execution_profile import WEEKLY19_15W_R150K_PROFILE as PROFILE
import run_qmt_roll_weekly19_live as entry
TZ=ZoneInfo('Asia/Shanghai')
class EntryTest(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory(dir='/private/tmp');self.root=Path(self.t.name).resolve();self.root.chmod(0o700)
 def tearDown(self):self.t.cleanup()
 def backend(self,cfg=None,preview=False):
  return LocalEvidenceBackend(cfg or dict(schema='weekly19.live-context.v1',execution_profile=PROFILE.profile_key),repo_root=ROOT,
   release_manifest=self.root/'missing-release',activation_receipt=self.root/'missing-activation',qualification_evidence=self.root/'missing-qualification',preview=preview)
 def test_no_receipt_never_loads_broker_or_secret(self):
  b=self.backend()
  with patch('qmt_roll_weekly19_broker_evidence.load_broker_snapshot',side_effect=AssertionError('must not read')):
   with self.assertRaisesRegex(LocalBackendError,'missing_release_manifest'):b.require_production()
 def test_json_cannot_supply_qualification_or_callable_capability(self):
  for key in ['qualified','production_qualified','backend','context_provider','sender']:
   with self.assertRaisesRegex(LocalBackendError,'capability_injection'):self.backend(dict(schema='weekly19.live-context.v1',execution_profile=PROFILE.profile_key,**{key:True}))
 def test_preview_backend_cannot_cross_live_gate(self):
  with self.assertRaisesRegex(LocalBackendError,'preview_backend'):self.backend(preview=True).require_production()
 def test_context_private_owner_regular_and_unique_json_required(self):
  p=self.root/'context';p.write_text('{"a":1,"a":2}');p.chmod(0o600)
  with self.assertRaises(ValueError):private_json(p)
  p.write_text('{}');p.chmod(0o644)
  with self.assertRaises(LocalBackendError):private_json(p)
  p.chmod(0o600);q=self.root/'link';q.symlink_to(p)
  with self.assertRaises(OSError):private_json(q)
 def test_day_service_spans_lunch_but_ends_at_authoritative_close(self):
  now=datetime(2026,11,2,11,34,tzinfo=TZ)
  end=entry.session_end(now,['day_am','day_pm'],{'2026-11-02'});self.assertEqual(end.hour,15);self.assertEqual(end.minute,10)
 def test_friday_night_saturday_continuation_not_saturday_night(self):
  end=entry.session_end(datetime(2026,10,30,21,tzinfo=TZ),['night','late_night'],{'2026-10-30'})
  self.assertEqual(end,datetime(2026,10,31,2,35,tzinfo=TZ))
  self.assertEqual(entry.session_end(datetime(2026,10,31,1,tzinfo=TZ),['night','late_night'],{'2026-10-30'}),end)
  with self.assertRaisesRegex(LocalBackendError,'weekend'):entry.session_end(datetime(2026,10,31,21,tzinfo=TZ),['night','late_night'],{'2026-10-30'})
 def test_missing_calendar_mixed_sessions_and_before_start_are_rejected(self):
  now=datetime(2026,11,2,8,30,tzinfo=TZ)
  with self.assertRaises(LocalBackendError):entry.session_end(now,['day_am','day_pm'],{'2026-11-02'})
  with self.assertRaises(LocalBackendError):entry.session_end(now.replace(hour=9),['day_am','night'],{'2026-11-02'})
  with self.assertRaises(LocalBackendError):entry.session_end(now.replace(hour=9),['day_am'],set())
 def test_session_does_not_exit_after_single_blocked_cycle(self):
  class Clock:
   now=datetime(2026,11,2,9,tzinfo=TZ)
   def tick(self):return self.now
   def sleep(self,n):self.now+=timedelta(seconds=n)
  class Backend:
   closed=False
   def load_inputs(self,target,now):return {'calendar':['2026-11-02']}
   def close_session(self):self.closed=True
  b=Backend();clock=Clock();calls=[]
  with patch.object(entry,'run_weekly19_session_cycle',return_value={'status':'blocked'}):
   r=entry.run_session(dict(backend=b,target_date='2026-10-30',preview=True),duration_seconds=3,names=['day_am','day_pm'],clock=clock.tick,sleep=clock.sleep,on_cycle=calls.append)
  self.assertEqual(r['cycles'],3);self.assertEqual(len(calls),3);self.assertTrue(b.closed)
if __name__=='__main__':unittest.main()
