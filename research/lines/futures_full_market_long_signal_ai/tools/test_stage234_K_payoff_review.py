"""Three independent tiny behaviors; no actual files or author tests."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np

SOURCE = Path(__file__).with_name('stage234_K_payoff_review.py')


class KPayoffIndependentTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SOURCE.exists(), 'independent reviewer not implemented')
        spec = importlib.util.spec_from_file_location('stage234_fixture', SOURCE)
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)

    def test_force_open_tick_fees_and_exact_epoch_point(self):
        # Wrong rounding, double-charged slip or using the old boundary breaks this.
        raw = dict(N_u='8', R0_points='2', cash_risk_unit='20', multiplier='10', tick_size='.2',
                   entry_reference='100', filled='1', base_entry_fill='100.2',
                   base_entry_fee_per_lot='2', base_entry_slippage_per_lot='2',
                   stress_entry_fill='100.6', stress_entry_fee_per_lot='6',
                   stress_entry_slippage_per_lot='6')
        base = self.m.new_payoff(raw, 106.1, 'base')
        stress = self.m.new_payoff(raw, 106.1, 'stress')
        self.assertEqual((base['fill_price'], base['fee_per_lot'], base['slippage_per_lot']), (105.8, 2., 3.))
        self.assertAlmostEqual(base['net_pnl'], 52.); self.assertAlmostEqual(base['net_R'], 2.6)
        self.assertAlmostEqual(base['net_R_common2N'], .325)
        self.assertAlmostEqual(stress['net_pnl'], 36.); self.assertAlmostEqual(stress['net_R'], 1.8)
        cache = dict(epochs=np.array(['X.a.202601', 'X.a.202602']), offsets=np.array([0, 2, 4]),
                     days=np.array([1, 3, 1, 3]), values=np.array([[10, 11, 9, 10, 1], [20, 21, 19, 20, 1],
                     [100, 110, 90, 105, 1], [106.1, 110, 100, 105, 1]]), valid=np.ones(4, bool))
        p = self.m.native_point(cache, 'X.a.202602', 3)
        self.assertEqual((p['epoch_slot'], p['local_row'], p['flat_row'], p['native_day'], p['native_open']), (1, 1, 3, 3, 106.1))
        with self.assertRaises(ValueError): self.m.native_point(cache, 'X.a.202602', 2)
        cache['valid'][3] = False
        with self.assertRaises(ValueError): self.m.native_point(cache, 'X.a.202602', 3)

    def test_only_unrepresentable_cost_is_unknown_and_gap_is_not_capped(self):
        raw = dict(N_u='4', R0_points='1', cash_risk_unit='10', multiplier='10', tick_size='1',
                   entry_reference='10', filled='1', base_entry_fill='11', base_entry_fee_per_lot='2',
                   base_entry_slippage_per_lot='10', stress_entry_fill='13', stress_entry_fee_per_lot='6',
                   stress_entry_slippage_per_lot='30')
        base = self.m.new_payoff(raw, 2.5, 'base')
        self.assertEqual(base['fill_price'], 1.); self.assertEqual(base['net_pnl'], -104.)
        self.assertEqual(base['net_R'], -10.4)
        with self.assertRaises(self.m.QuoteUnrepresentable): self.m.new_payoff(raw, 2.5, 'stress')
        self.assertEqual(self.m.new_payoff(raw, 2.5, 'base')['net_R'], -10.4)

    def test_copy_null_clocks_and_nochild_conservation(self):
        # Coercing unknown to zero, advancing cancellation to U or dropping nochild breaks this.
        copied = self.m.branch_contract(True, 'closed_before_K', 1, '2026-01-05', '2026-01-02')
        cancel = self.m.branch_contract(True, 'known_nonparticipation', 1, '2026-01-05', '2026-01-02')
        before = self.m.branch_contract(True, 'unknown_before_K', 1, '2026-01-05', '2026-01-02')
        on = self.m.branch_contract(True, 'unknown_on_K', 1, '2026-01-05', '2026-01-02')
        after = self.m.branch_contract(True, 'unknown_after_K', 1, '2026-01-05', '2026-01-02')
        self.assertEqual([v['mode'] for v in (copied, cancel, before, on, after)], ['copy', 'cancel', 'unknown', 'unknown', 'quote'])
        self.assertEqual(cancel['policy_known_date'], '2026-01-02')
        self.assertIsNone(before['policy_reward']); self.assertIsNone(on['policy_reward'])
        self.assertEqual(after['known_phase'], 'after_all_source_close')
        noaction = self.m.branch_contract(False, 'unknown_unclassified', None, '', '', '2026-01-01', u_eligible=False)
        self.assertEqual((noaction['policy_reward'], noaction['policy_known_date']), (0., '2026-01-01'))
        counts = self.m.parent_tally(4, [0, 1, 2, 2, 2])
        self.assertEqual(counts.tolist(), [1, 1, 3, 0])
        self.assertEqual(int((counts == 0).sum()), 1)
        copyrow = dict(label_state='closed_complete_bar_model', label_known_date='2026-01-02',
                       label_known_phase='after_all_source_close', exit_index='2.0', exit_date='2026-01-02', exit_reason='stop_boundary',
                       net_pnl_base_per_lot='123.00', net_R_base='1.2300', net_R_common2N_base='.15375',
                       K_base_known='1', K_base_state='known_original_before_K', K_base_net_pnl_per_lot='123.00',
                       K_base_net_R='1.2300', K_base_net_R_common2N='.15375', K_base_known_date='2026-01-02',
                       K_base_known_phase='after_all_source_close', K_base_exit_index='2.0', K_base_exit_date='2026-01-02',
                       K_base_exit_reason='stop_boundary')
        self.assertTrue(self.m.verify_cost(copyrow, 'base', 'copy_before_K')['known'])
        copyrow['K_base_net_pnl_per_lot']='123.0'
        with self.assertRaises(ValueError): self.m.verify_cost(copyrow, 'base', 'copy_before_K')


if __name__ == '__main__': unittest.main()
