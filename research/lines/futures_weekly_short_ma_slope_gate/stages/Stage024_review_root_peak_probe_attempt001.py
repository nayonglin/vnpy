"""Independent carry-in high-water probe; pure synthetic Runtime only."""
import copy,json,sys,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[4];sys.path[:0]=[str(ROOT/'examples/portfolio_backtesting'),str(ROOT)]
from tests import test_weekly19_adoption as fx
import qmt_roll_weekly19_runtime as runtime

class OpeningPeak(unittest.TestCase):
 def setUp(self):
  original=fx.broker
  def complete(**kwargs):
   snapshot=original(**kwargs);raw=json.loads(snapshot['account']['raw_payload']);raw.update(query_last_seen=True,query_error_rows=0);snapshot['account']=fx.envelope(raw);return snapshot
  with patch.object(fx,'broker',side_effect=complete):self.values=fx.sources()
 def actor(self):
  c,f,b,m,s,r,q,d,cash=self.values
  seed=fx.adoption.build_carry_in_seed(operator_decision=d,broker_snapshot=s,raw_position_evidence=r,contract_metadata_evidence=q,metadata=m,now=fx.NOW)
  return runtime.bootstrap_weekly19_runtime(runtime.DEFAULT_SETTINGS_ASSET,m,c,f,s,cash,carry_in_seed=seed,warmup_batches=[b[day]for day in sorted(b)],clock=lambda:fx.NOW)
 def test_positive_control_real_cash_and_original_stop(self):
  a=self.actor();self.assertEqual(a.broker_equity,170000);self.assertTrue(a.strategy.states['rb.SHFE'].layers[0].stop_price>0);self.assertEqual(a.engine.intents,[])
 def test_new_cohort_known_opening_equity_is_its_initial_high_water(self):
  a=self.actor();self.assertEqual(a.strategy.portfolio_equity_high_water,170000)
 def test_first_post_cutover_equity_decline_is_not_erased(self):
  a=self.actor();a.strategy.estimated_equity=150000;a.strategy._refresh_portfolio_drawdown_state()
  self.assertAlmostEqual(a.strategy.portfolio_drawdown_pct,20000/170000)
if __name__=='__main__':unittest.main(verbosity=2)
