"""Abstract reachability boundaries; no strategy or account is instantiated."""
import unittest
try:import stage010_reachable_demand as module
except ImportError:module=None


class ReachableDemandTests(unittest.TestCase):
    def setUp(self):self.assertIsNotNone(module,'Stage010 not implemented')

    def test_first_mismatch_zero_sixth_due(self):
        state=module.State('p','old')
        for count in range(6):
            updated,due=module.advance(state,'new',5)
            self.assertEqual(due,count==5)
            if not due:self.assertEqual(updated.elapsed,count);state=updated

    def test_changed_target_resets_and_return_to_held_clears(self):
        state=module.State('p','old','new',4)
        changed,due=module.advance(state,'newer',5)
        self.assertFalse(due);self.assertEqual(changed.elapsed,0)
        self.assertEqual(changed.pending_target,'newer')
        original,due=module.advance(changed,'old',5)
        self.assertEqual(original,module.State('p','old'));self.assertFalse(due)

    def test_carry_close_seed_cross_mapping_and_next_batch_roll(self):
        days=[f'2020-01-{value:02d}'for value in range(1,9)]
        mapping={day:{'p':'new'}for day in days}
        seed=[dict(product_vt_symbol='p',vt_symbol='old',signal_date='2019-12-31',execution_trade_date=days[0])]
        real={('new',day)for day in days}
        demand,pending,diagnostics=module.enumerate_demand(days,mapping,seed,real,5)
        self.assertTrue(demand[('old',days[1])]['signal_carry_possible'])
        self.assertEqual(demand[('new',days[6])]['requirement_kind'],'full_session')
        self.assertTrue(demand[('new',days[6])]['need_rollover_open'])
        self.assertNotIn(('old',days[7]),demand)  # Mandatory close already filled on day 7.
        self.assertEqual(diagnostics['mandatory_close_states'],1)

    def test_terminal_events_pending_and_full_takes_priority(self):
        days=['2020-01-02','2020-01-03']
        seeds=[dict(product_vt_symbol='p',vt_symbol='x',signal_date=days[0],execution_trade_date=days[1]),
            dict(product_vt_symbol='p',vt_symbol='x',signal_date=days[1],execution_trade_date='')]
        demand,pending,_=module.enumerate_demand(days,{day:{'p':'x'}for day in days},seeds,{('x',day)for day in days},5)
        self.assertEqual(demand[('x',days[1])]['requirement_kind'],'full_session')
        self.assertTrue(any(row['reason']=='initial_open'for row in pending))
        self.assertTrue(any(row['reason']=='possible_close'for row in pending))


if __name__=='__main__':unittest.main()
