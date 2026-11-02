"""Native normalized terminal-order vocabulary probe; synthetic packets only."""
import json,sys,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[4];sys.path[:0]=[str(ROOT/'examples/portfolio_backtesting'),str(ROOT)]
from tests import test_weekly19_adoption as fx
class TerminalVocabulary(unittest.TestCase):
 def setUp(self):
  original=fx.broker
  def complete(**kwargs):
   s=original(**kwargs);a=json.loads(s['account']['raw_payload']);a.update(query_last_seen=True,query_error_rows=0);s['account']=fx.envelope(a);return s
  with patch.object(fx,'broker',side_effect=complete):self.v=fx.sources()
 def seed(self,status):
  c,f,b,m,s,r,q,d,cash=self.v;o=json.loads(s['orders']['raw_payload']);o['orders']=[dict(status=status)];s['orders']=fx.envelope(o)
  return fx.adoption.build_carry_in_seed(operator_decision=d,broker_snapshot=s,raw_position_evidence=r,contract_metadata_evidence=q,metadata=m,now=fx.NOW)
 def test_existing_terminal_alias_control(self):self.assertEqual(self.seed('filled')['positions'][0]['volume'],2)
 def test_native_provider_all_traded_is_terminal_not_working(self):self.assertEqual(self.seed('all_traded')['positions'][0]['volume'],2)
if __name__=='__main__':unittest.main(verbosity=2)
