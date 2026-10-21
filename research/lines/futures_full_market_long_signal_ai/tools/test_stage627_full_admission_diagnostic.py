"""Only synthetic behaviors for frozen625; never opens historical inputs."""
import importlib.util
import itertools
from pathlib import Path
import unittest
import numpy as np

SOURCE = Path(__file__).with_name('stage627_full_admission_diagnostic.py')


def module():
    assert SOURCE.exists(), 'new627 implementation is absent'
    spec = importlib.util.spec_from_file_location('new627', SOURCE)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def parent(seq, product='X.EX', family='X', u=0):
    return dict(sequence_index=str(seq), event_id='mother'+str(seq), product_id=product,
                family_id=family, u_date='2020-01-02', u_index=str(u), reference_epoch=product+'.202003')


def score(p, seq, value, month='202003', eligible=1):
    return dict(sequence_index=str(seq), action_id='action'+str(seq),
                mother_sequence_index=p['sequence_index'], mother_event_id=p['event_id'],
                product_id=p['product_id'], family_id=p['family_id'], u_date=p['u_date'],
                u_index=p['u_index'], reference_epoch=p['product_id']+'.'+month,
                anchor_epoch=p['reference_epoch'], u_action_eligible=str(eligible), score=str(value),
                scope='main', cutoff='2020-01-01')


def all_scopes(m, rows):
    result = []
    for r in rows:
        result += [r, dict(r, scope='holdout_'+str(m.family_group(r['family_id'])))]
    return result


class New627(unittest.TestCase):
    def test_positive_F_preserved_and_fallback_rank_without_sign(self):
        m = module(); ordinary = parent(0); deferred = parent(1, 'X_F.EX')
        # Product ordinary/F is represented by original product suffix, not exchange.
        ordinary['product_id']='X'; ordinary['reference_epoch']='X.202003'
        deferred['product_id']='X_F'; deferred['reference_epoch']='X_F.202003'
        other = parent(2, 'Y', 'Y'); other['reference_epoch']='Y.202003'
        rows = [score(ordinary,0,-.1),score(deferred,1,.2),score(other,2,-2),
                score(other,3,-1,'202004'),score(other,4,9,'202002')]
        result=m.select_domain([ordinary,deferred,other],all_scopes(m,rows),['2020-01-02','2020-01-03','2020-02-03'],'2026-10-16')
        selected={r['family_id']:r for r in result['choices'] if r['scope']=='main'}
        self.assertEqual(selected['X']['action_id'],'action1'); self.assertEqual(selected['X']['m'],1)
        self.assertEqual(selected['Y']['action_id'],'action3'); self.assertEqual(selected['Y']['m'],0)
        self.assertEqual(selected['Y']['pure_K_gate'],1)

    def test_main_preservation_and_original_anchor_validation(self):
        m=module();p=parent(0);r=score(p,0,.25)
        result=m.select_domain([p],all_scopes(m,[r]),['2020-01-02','2020-01-03'],'2026-10-16')
        accepted=dict(p,selected='1',chosen_action_id='action0',chosen_action_sequence_index='0',
                      chosen_epoch=r['reference_epoch'],anchor_epoch=p['reference_epoch'],score='.25',cutoff='2020-01-01')
        self.assertEqual(m.check_main(result['positive'],[accepted],[p]),1)
        with self.assertRaises(ValueError):m.check_main(result['positive'],[dict(accepted,score='.3')],[p])
        with self.assertRaises(ValueError):m.select_domain([p],all_scopes(m,[dict(r,anchor_epoch='X.EX.202004')]),['2020-01-02','2020-01-03'],'2026-10-16')

    def test_pure_calendar_unknown_is_not_known_absence(self):
        m=module();p=parent(0);r=score(p,0,-1,'202012')
        result=m.select_domain([p],all_scopes(m,[r]),['2020-01-02'],'2026-10-16')
        self.assertEqual(result['choices'],[])
        self.assertIn(('main','2020-01-02','X'),result['membership_unknown'])

    def test_K_trade_clock_cancel_zero_and_nonprimary_are_distinct(self):
        m=module();base=dict(primary_domain='1',branch='known_nonparticipation',K_stress_known='0',
            K_stress_net_R='',K_stress_known_date='',K_stress_known_phase='',policy_reward_known='1',
            policy_reward='0',policy_known_date='2020-01-02',policy_known_phase='after_all_source_close')
        self.assertEqual(m.label_outcome(base,'2026-10-16')['Y'],0)
        self.assertFalse(m.label_outcome(dict(base,primary_domain='0',branch='nonprimary_noaction'),'2026-10-16')['known'])
        self.assertFalse(m.label_outcome(dict(base,policy_known_date='2026-10-17'),'2026-10-16')['known'])
        trade=dict(base,K_stress_known='1',K_stress_net_R='2',net_R_stress='999',
                   K_stress_known_date='2020-01-06',K_stress_known_phase='after_all_source_close')
        self.assertEqual(m.label_outcome(trade,'2026-10-16')['Y'],2)

    def test_full_unknown_known_I_and_paired_binary_bounds(self):
        m=module();rows=[dict(m=1,Y=2.,known=True,family_id='a'),dict(m=0,Y=None,known=False,family_id='b')]
        d=m.day_statistics(rows)
        self.assertIsNone(d['Delta_E']);self.assertEqual(d['A_E'],1.)
        self.assertEqual(d['R_known_contribution'],.5)
        self.assertEqual(d['Delta_I'],0.);self.assertEqual(d['pI'],1.);self.assertEqual(d['p'],.5)
        self.assertEqual(d['Z_lower'],0.);self.assertEqual(d['Z_upper'],.25)
        for mark in (0,1):
            deg=m.day_statistics([dict(m=mark,Y=None,known=False,family_id='a')])
            self.assertEqual(deg['Delta_E'],0.);self.assertEqual(deg['Z_lower'],0.)
            self.assertEqual(deg['Z_upper'],0.)
        self.assertIsNone(m.day_statistics(rows,membership_unknown=1)['Delta_E'])

    def test_uniform_same_count_expectation_matches_enumeration(self):
        m=module();ys=[-1.,2.,4.];rows=[dict(m=int(i<2),Y=y,known=True,family_id=str(i)) for i,y in enumerate(ys)]
        expected=np.mean([sum(ys[i] for i in subset)/3 for subset in itertools.combinations(range(3),2)])
        d=m.day_statistics(rows)
        self.assertAlmostEqual(d['U_E'],expected)
        self.assertAlmostEqual(d['Delta_E'],sum(ys[:2])/3-expected)

    def test_fixed_indices_and_empty_source_days_keep_calendar_denominator(self):
        m=module();empty=m.day_statistics([]);self.assertEqual(empty['Delta_I'],0.)
        indices=np.array([[0,0],[1,1],[0,1],[1,0]])
        stat=m.mean_ci([2.,empty['Delta_I']],indices)
        self.assertEqual(stat['mean'],1.);self.assertEqual(stat['ci95'],[.07500000000000001,1.9249999999999998])
        self.assertIsNone(m.mean_ci([None,0.],indices)['ci95'])

    def test_conditional_gate_cannot_claim_full_E_with_unknown(self):
        m=module()
        def report():return dict(A_I={'mean':1.,'ci95':[.5,1.5]},Delta_I={'mean':.2,'ci95':[.1,.3]},
            A_E={'mean':None,'ci95':None},Delta_E={'mean':None,'ci95':None},
            support={'informative_dates':60,'selected_known_family_count':8,'membership_unknown_dates':0})
        windows={s+'/'+w:report() for s in m.SCOPES for w in ('primary_2020','cold_2023')}
        eras={s+'/'+e:report() for s in m.SCOPES for e in ('early_2020_2022','late_2023_plus')}
        gate=m.diagnostic_gates(windows,eras)
        self.assertTrue(gate['conditional_support']);self.assertEqual(gate['full_E_support'],'inconclusive')
        self.assertFalse(gate['production_qualified'])


if __name__=='__main__':unittest.main()
