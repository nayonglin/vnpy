"""Independent unsupported carry-in hedge flag probe; synthetic raw packets."""
import json,sys,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[4];sys.path[:0]=[str(ROOT/'examples/portfolio_backtesting'),str(ROOT)]
from tests import test_weekly19_adoption as fx
class HedgeCompatibility(unittest.TestCase):
 def setUp(self):
  original=fx.broker
  def complete(**kwargs):
   snapshot=original(**kwargs);raw=json.loads(snapshot['account']['raw_payload']);raw.update(query_last_seen=True,query_error_rows=0);snapshot['account']=fx.envelope(raw);return snapshot
  with patch.object(fx,'broker',side_effect=complete):self.v=fx.sources()
 def seed(self):
  c,f,b,m,s,r,q,d,cash=self.v
  return fx.adoption.build_carry_in_seed(operator_decision=d,broker_snapshot=s,raw_position_evidence=r,contract_metadata_evidence=q,metadata=m,now=fx.NOW)
 def change_flag(self,flag):
  raw=json.loads(self.v[5]['raw_payload'])
  for row in raw['native_positions']:row['HedgeFlag']=flag
  self.v[5].update(fx.envelope(raw));self.v[7]['raw_carry_in_positions_sha256']=self.v[5]['raw_sha256']
 def test_speculation_positive_control(self):self.assertEqual(self.seed()['positions'][0]['volume'],2)
 def test_hedge_position_is_not_adopted_by_speculation_only_executor(self):
  self.change_flag('3')
  with self.assertRaises(ValueError):self.seed()
 def test_arbitrage_position_is_not_adopted_by_speculation_only_executor(self):
  self.change_flag('2')
  with self.assertRaises(ValueError):self.seed()
if __name__=='__main__':unittest.main(verbosity=2)
