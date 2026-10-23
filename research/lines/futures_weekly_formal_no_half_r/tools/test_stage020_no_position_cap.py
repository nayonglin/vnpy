"""Universe-capacity configuration and real planner behavior, no market replay."""
from collections import defaultdict
from types import SimpleNamespace
from dataclasses import dataclass,asdict
import unittest
from test_stage008_three_ma import Harness
try:
 from stage020_no_position_cap import universe_capacity_profile, require_only_position_cap_delta
except ImportError:
 universe_capacity_profile = require_only_position_cap_delta = None

@dataclass(frozen=True)
class Capital:
 max_concurrent_positions: int = 4
 account_capital: float = 150000.
 risk_multiplier: float = .4
@dataclass(frozen=True)
class Spec:
 capital: Capital
 overrides: dict
 profile: str = 'research'

class Planner(Harness):
 def __init__(self,cap,active):
  super().__init__();self.max_concurrent_positions=cap;self.active=active;self.selection_pairwise_runtime=None
 def _count_active_positions(self):return self.active
 def _build_flat_entry_candidate_plan(self,context,active):
  product,volume=context.product,context.volume
  return defaultdict(lambda:0,product_vt_symbol=product,native_openable=volume>0,sizing=dict(selected_volume=volume,margin_per_contract=100.,effective_max_concurrent_positions=self._effective_max_concurrent_positions('flat_entry')),volume=volume,candidate_status='skipped',skip_reason='sizing_zero_volume' if not volume else '')
 def _apply_selection_pairwise_scores(self,plans):pass
 def _apply_ai_path_damage_risk_discount(self,plans):pass
 def _apply_selection_pairwise_volume_tilt(self,plans):pass
 def _incremental_margin_budget_gate_fields(self,**kw):
  return dict(incremental_margin_budget_gate_enabled=0,incremental_margin_budget_gate_passed=1,incremental_margin_budget_gate_selected_volume_after=kw['selected_volume'],incremental_margin_budget_gate_planned_entry_margin=kw['selected_volume']*100.)

class Tests(unittest.TestCase):
 def api(self):self.assertTrue(callable(universe_capacity_profile),'no-position-cap implementation missing')
 def test_profile_changes_only_the_declared_count_and_keeps_control_immutable(self):
  self.api();old=dict(spec=Spec(Capital(),dict(max_concurrent_positions=4,stop_loss_pct=.02)),strategy_cls=Harness,profile='research')
  before=asdict(old['spec']);new=universe_capacity_profile(old,19)
  self.assertEqual(asdict(old['spec']),before);self.assertIs(new['strategy_cls'],Harness)
  self.assertEqual(new['spec'].capital.max_concurrent_positions,19);self.assertEqual(new['spec'].overrides['max_concurrent_positions'],19)
  require_only_position_cap_delta(before,asdict(new['spec']),4,19,[('capital','max_concurrent_positions'),('overrides','max_concurrent_positions')])
  with self.assertRaises(ValueError):universe_capacity_profile(old,0)
 def test_other_parameter_changes_fail_closed(self):
  self.api();old={'max_concurrent_positions':4,'stop':.02};new={'max_concurrent_positions':19,'stop':.03}
  with self.assertRaises(ValueError):require_only_position_cap_delta(old,new,4,19,[('max_concurrent_positions',)])
 def test_real_planner_admits_fifth_and_sixth_products_but_not_zero_size(self):
  self.api()
  for cap in [4,19]:
   s=Planner(cap,4);plans=s._plan_flat_entry_candidates([SimpleNamespace(current_pos=0,product=p,volume=v) for p,v in [('A.TEST',1),('B.TEST',1),('C.TEST',0)]])
   for product in ['A.TEST','B.TEST']:
    self.assertEqual(plans[product]['candidate_status'],'opened' if cap==19 else 'skipped')
    if cap==4:self.assertEqual(plans[product]['skip_reason'],'concurrent_limit')
   self.assertEqual(plans['C.TEST']['candidate_status'],'skipped');self.assertEqual(plans['C.TEST']['skip_reason'],'sizing_zero_volume')
  s=Planner(19,18);self.assertEqual(s._plan_flat_entry_candidates([SimpleNamespace(current_pos=0,product='LAST.TEST',volume=1)])['LAST.TEST']['candidate_status'],'opened')
 def test_zero_is_one_while_universe_capacity_is_19_in_all_contexts(self):
  self.api();s=Planner(19,4)
  for context in ['flat_entry','default','rollover_reopen']:self.assertEqual(s._effective_max_concurrent_positions(context),19)
  s.max_concurrent_positions=0;self.assertEqual(s._effective_max_concurrent_positions('flat_entry'),1)

if __name__=='__main__':unittest.main()
