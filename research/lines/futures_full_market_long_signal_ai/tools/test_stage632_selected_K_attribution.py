"""Eight new synthetic accounting behaviors; no historical source reads."""
import importlib.util
from pathlib import Path
import unittest

SOURCE=Path(__file__).with_name('stage632_selected_K_attribution.py')


def module():
    assert SOURCE.exists(),'new632 implementation absent'
    spec=importlib.util.spec_from_file_location('new632',SOURCE);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    return m


def trade():
    e=dict(m='1',known='True',Y='2.5',score='4',family_id='X')
    old=dict(N_u='4',R0_points='1',cash_risk_unit='10',multiplier='10',tick_size='1',entry_reference='100',
        exit_reference='105',gross_points_reference='5',gross_R_reference='5',stress_entry_fill='101',
        stress_exit_fill='104',stress_entry_fee_per_lot='2',stress_exit_fee_per_lot='3',stress_total_fee_per_lot='5',
        stress_entry_slippage_per_lot='10',stress_exit_slippage_per_lot='10',stress_total_slippage_per_lot='20',
        net_pnl_stress_per_lot='25',net_R_stress='2.5',entry_index='1',exit_index='2',entry_date='2020-01-03',
        exit_date='2020-01-06',exit_reason='stop_boundary',exit_boundary='105',label_state='closed_complete_bar_model',
        label_known_date='2020-01-06',label_known_phase='after_all_source_close')
    k=dict(branch='copy_before_K',K_stress_known='1',K_stress_net_R='2.5',K_stress_known_date='2020-01-06',
        K_stress_known_phase='after_all_source_close',K_stress_exit_index='2',K_stress_exit_date='2020-01-06',
        K_stress_exit_reason='stop_boundary',entry_date='2020-01-03',primary_domain='1',
        policy_reward_known='0',policy_reward='',policy_known_date='',policy_known_phase='')
    return e,k,old


class New632(unittest.TestCase):
    def test_reference_fill_fee_slip_are_not_subtracted_twice(self):
        m=module();e,k,old=trade();a=m.attribute_action(e,k,old,None,'2026-10-16')
        self.assertTrue(a['J']);self.assertEqual((a['G'],a['Fee'],a['Slip']),(5.,.5,2.))
        self.assertEqual(a['G']-a['Fee']-a['Slip'],2.5);self.assertEqual(a['accounting_residual'],0.)

    def test_quote_K_uses_its_own_exit_instead_of_later_original_exit(self):
        m=module();e,k,old=trade();e['Y']='7.5';k.update(branch='quote_K',K_stress_net_R='7.5',
            K_stress_exit_index='5',K_stress_exit_date='2020-02-03',K_stress_known_date='2020-02-03',K_stress_exit_reason='K_deadline_open')
        q=dict(old,native_open='110',native_valid='1',K_stress_sell_fill='109',K_stress_sell_fee_per_lot='3',
            K_stress_sell_slippage_per_lot='10',K_stress_net_pnl_per_lot='75')
        a=m.attribute_action(e,k,old,q,'2026-10-16')
        self.assertTrue(a['J']);self.assertEqual(a['G'],10.);self.assertEqual(a['gap_state'],'quote_K_boundary_unknown')
        self.assertIsNone(a['gap_overshoot_R'])

    def test_true_cancel_zero_and_K_unknown_have_different_components(self):
        m=module();e,k,old=trade();e['Y']='0';k.update(branch='known_nonparticipation',K_stress_known='0',
            policy_reward_known='1',policy_reward='0',policy_known_date='2020-01-03',policy_known_phase='after_all_source_close')
        a=m.attribute_action(e,k,dict(old,label_state='known_nonparticipation'),None,'2026-10-16')
        self.assertTrue(a['J']);self.assertEqual(a['G'],0.);self.assertFalse(a['H'])
        b=m.attribute_action(dict(e,known='False',Y=''),k,old,None,'2026-10-16')
        self.assertFalse(b['J']);self.assertIsNone(b['G']);self.assertIsNone(b['YK'])

    def test_original_full_nI_and_empty_day_are_preserved(self):
        m=module();e,k,old=trade();a=m.attribute_action(e,k,old,None,'2026-10-16')
        d=m.daily_accounting([dict(known='True'),dict(known='True')],[a])
        self.assertEqual(d['nI'],2);self.assertEqual(d['A_I'],1.25);self.assertEqual(d['G_J'],2.5)
        empty=m.daily_accounting([],[]);self.assertEqual(empty['A_I'],0.)
        self.assertEqual((d['A_I']+empty['A_I'])/2,.625)

    def test_incomplete_J_retains_known_net_leftover(self):
        m=module();e,k,old=trade();del old['stress_exit_fee_per_lot']
        a=m.attribute_action(e,k,old,None,'2026-10-16');self.assertFalse(a['J'])
        d=m.daily_accounting([e],[a]);self.assertEqual(d['known_net_unattributed'],2.5)
        self.assertEqual(d['accounting_identity_residual'],0.)

    def test_H_bridge_and_remaining_error_use_original_nI(self):
        m=module();e,k,old=trade();a=m.attribute_action(e,k,old,None,'2026-10-16')
        b=m.attribute_action(dict(e,Y='2.5',score='1'),k,dict(old,label_known_date='2026-10-17'),None,'2026-10-16')
        self.assertTrue(a['H']);self.assertFalse(b['H'])
        d=m.daily_accounting([e,e,dict(known='True')],[a,b])
        self.assertAlmostEqual(d['S_I'],5/3);self.assertAlmostEqual(d['old_error_H'],-.5)
        self.assertAlmostEqual(d['remaining_error_I_minus_H'],.5);self.assertAlmostEqual(d['bridge_identity_residual'],0.)

    def test_old_target_after_END_cannot_be_inferred_from_known_K(self):
        m=module();e,k,old=trade();a=m.attribute_action(e,k,dict(old,label_known_date='2026-10-17'),None,'2026-10-16')
        self.assertFalse(a['H']);self.assertIsNone(a['oldY'])
        b=m.attribute_action(e,k,dict(old,label_state='open_right_censored',net_R_stress='nan'),None,'2026-10-16')
        self.assertFalse(b['H'])

    def test_entryday_later_gap_and_quote_boundary_are_separate(self):
        m=module();e,k,old=trade();old.update(exit_reason='gap_stop',exit_boundary='107');k['K_stress_exit_reason']='gap_stop'
        later=m.attribute_action(e,k,old,None,'2026-10-16')
        self.assertEqual(later['gap_state'],'held_day_gap_stop');self.assertEqual(later['gap_overshoot_R'],2.)
        old.update(exit_index='1',exit_date='2020-01-03');k.update(K_stress_exit_index='1',K_stress_exit_date='2020-01-03')
        first=m.attribute_action(e,k,old,None,'2026-10-16');self.assertEqual(first['gap_state'],'entry_day_gap_stop')
        self.assertEqual(first['gap_overshoot_R'],2.)


if __name__=='__main__':unittest.main()
