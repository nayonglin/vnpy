import importlib.util,unittest
from test_stage009_reserve import Parent,History,size

class Reserve50Tests(unittest.TestCase):
 def subject(self):
  self.assertIsNotNone(importlib.util.find_spec('stage012_reserve'),'Stage012 reserve missing')
  import stage012_reserve as m
  return m
 def make(self,blocked=False):
  m=self.subject();return m.reserve_strategy_class(Parent,History(blocked),True,'2015-01-01')()
 def test_50k_cap_binds_before_unchanged_parent_sizing(self):
  s=self.make();s.mark_pnl=-70000.;r=size(s)
  self.assertEqual(s.reserve_cumulative_transfer,50000.);self.assertEqual(s.reserve_balance,0.);self.assertEqual(r['parent_equity_seen'],130000.)
  self.assertEqual(s.reserve_transfer_events[0]['total_account_equity'],130000.)
  s.mark_pnl=-200000.;r=size(s,'2015-01-06');self.assertEqual(r['selected_volume'],0);self.assertEqual(s._sizing_equity(),0.)
 def test_gate_rejection_and_profit_never_use_or_refill_50k(self):
  s=self.make(True);s.mark_pnl=-10000.;size(s,direction='short',signal='short_case1a');self.assertEqual(s.reserve_balance,50000.)
  s=self.make();s.mark_pnl=-10000.;size(s);s.mark_pnl=20000.;size(s,'2015-01-06');self.assertEqual(s.reserve_balance,40000.)
 def test_wrapper_source_diff_is_only_reserve_constant(self):
  self.subject()
  import ast
  from pathlib import Path
  p=Path(__file__).parent
  old=ast.parse((p/'stage009_reserve.py').read_text());new=ast.parse((p/'stage012_reserve.py').read_text())
  for node in new.body:
   if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='RESERVE_INITIAL' for t in node.targets):node.value.value=150000.
  self.assertEqual(ast.dump(new,include_attributes=False),ast.dump(old,include_attributes=False))
if __name__=='__main__':unittest.main()
