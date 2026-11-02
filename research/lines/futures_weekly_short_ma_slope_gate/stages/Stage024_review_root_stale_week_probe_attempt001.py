"""Independent pre-cutover stale weekly protection probe; synthetic source only."""
import json,sys,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[4];sys.path[:0]=[str(ROOT/'examples/portfolio_backtesting'),str(ROOT)]
from tests import test_weekly19_adoption as fx
import qmt_roll_weekly19_runtime as runtime
class LatestProtection(unittest.TestCase):
 def setUp(self):
  original=fx.broker
  def complete(**kwargs):
   snapshot=original(**kwargs);raw=json.loads(snapshot['account']['raw_payload']);raw.update(query_last_seen=True,query_error_rows=0);snapshot['account']=fx.envelope(raw);return snapshot
  with patch.object(fx,'broker',side_effect=complete):self.v=fx.sources()
 def bootstrap(self,completed):
  c,f,b,m,s,r,q,d,cash=self.v;d=dict(d,completed_day=completed)
  seed=fx.adoption.build_carry_in_seed(operator_decision=d,broker_snapshot=s,raw_position_evidence=r,contract_metadata_evidence=q,metadata=m,now=fx.NOW)
  return runtime.bootstrap_weekly19_runtime(runtime.DEFAULT_SETTINGS_ASSET,m,c,f,s,cash,carry_in_seed=seed,warmup_batches=[b[day]for day in sorted(b)if day<=completed],clock=lambda:fx.NOW)
 def test_latest_pre_cutover_completed_week_control(self):self.assertEqual(self.bootstrap('2026-10-30').warmup_cursor,'2026-10-30')
 def test_one_week_stale_protection_rejected_when_calendar_knows_later_completed_week(self):
  self.assertIn('2026-10-30',self.v[0])
  with self.assertRaises(ValueError):self.bootstrap('2026-10-23')
if __name__=='__main__':unittest.main(verbosity=2)
