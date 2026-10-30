import ast,importlib.util,unittest
from pathlib import Path
from test_stage009_reserve import Parent,History,size

class Reserve150UnchangedTests(unittest.TestCase):
 def subject(self):
  self.assertIsNotNone(importlib.util.find_spec('stage014_reserve'),'Stage014 reserve missing')
  import stage014_reserve as m
  return m
 def test_all_reserve_economic_ast_and_150k_cap_unchanged(self):
  m=self.subject();p=Path(m.__file__)
  self.assertEqual(ast.dump(ast.parse(p.read_text()),include_attributes=False),ast.dump(ast.parse(p.with_name('stage009_reserve.py').read_text()),include_attributes=False))
  self.assertEqual((m.TRADING_INITIAL,m.RESERVE_INITIAL),(150000.,150000.))
 def test_new_month_funds_before_sizing_and_negative_equity_has_no_purchase_power(self):
  m=self.subject();s=m.reserve_strategy_class(Parent,History(False),True,'2015-03-01')();s.mark_pnl=-20000.;r=size(s,'2015-03-02');self.assertEqual(r['parent_equity_seen'],150000.);self.assertEqual(s.reserve_balance,130000.)
  s.mark_pnl=-300000.;r=size(s,'2015-03-03');self.assertEqual(s.reserve_balance,0.);self.assertEqual(r['selected_volume'],0)
if __name__=='__main__':unittest.main()
