"""Four new target/clock/strict-policy behaviors; zero fixture fits or old suites."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np
import pandas as pd

p=Path(__file__).with_name('stage238_K_target_fit.py');s=importlib.util.spec_from_file_location('tiny238',p)
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)


def label(action,value='',known='0',state='unknown_before_K'):
    return dict(action_id=action,primary_domain=1,participation_state='filled',K_stress_known=known,
        K_stress_state=state,K_stress_net_R=value,K_stress_known_date='2020-02-01' if known=='1' else '',
        K_stress_known_phase='after_all_source_close' if known=='1' else '',policy_reward_known='0',
        policy_reward='',policy_known_date='',policy_known_phase='')


def choices(action='b',arm='K_TARGET52'):
    rows=[]
    for g in [0,1]:
        for j,day in enumerate(['2020-01-02','2023-01-02']):
            i=2*g+j
            rows.append(dict(sequence_index=i,event_id='p'+str(i),product_id='P'+str(g),family_id='F'+str(g),
                u_date=day,u_index=100+i,reference_epoch='anchor',anchor_epoch='anchor',chosen_action_id=action+str(i),
                chosen_action_sequence_index=i,chosen_epoch='chosen_'+action,selected=1,scope='holdout_'+str(g),
                cutoff='2020-01-01' if j==0 else '2023-01-01',arm=arm))
    return pd.DataFrame(rows)


class TestStage238(unittest.TestCase):
    def function(self,name):
        self.assertTrue(callable(getattr(m,name,None)),'new target-only behavior is not implemented')
        return getattr(m,name)

    def test_parser_copy_and_global_zero_fit_gate(self):
        build=self.function('candidate_target')
        old=np.array([np.nextafter(1.,0.),1.]);new,copy_ok=build(old,['1.0','1.0'],['1.0','2.0'],
            ['closed_before_K','closed_after_K'],[1,1])
        self.assertEqual(new[0].tobytes(),old[0].tobytes());self.assertEqual(new[1],2.);self.assertTrue(copy_ok.all())
        calls=[];cells=[dict(scope=s,cutoff=c,ready=True) for s in ['main','holdout_0','holdout_1'] for c in ['2020-01-01','2023-01-01']]
        cells[-1]['ready']=False
        self.assertIsNone(self.function('gated_fits')({'ready':False,'cells':cells},lambda:calls.append(1)))
        self.assertEqual(calls,[])

    def test_C_clock_and_support_do_not_expand_training(self):
        check=self.function('support_preflight')
        actions=pd.DataFrame(dict(sequence_index=[0,1,2],primary_domain=[1,0,1],net_R_stress=[1.,2.,np.nan],
            label_known_date=['2019-12-30','2019-12-31',''],label_known_phase=['after_all_source_close']*3,
            K_stress_known=['1','0','1'],K_stress_known_date=['2019-12-29','','2019-12-29'],
            K_stress_known_phase=['after_all_source_close','','after_all_source_close']))
        cache=dict(sequence_index=np.array([0,1]),admissible_mask=np.array([True,False]),
                   old_weight=np.array([1.,1.]),new_weight=np.array([2.,0.]))
        r,ti,w=check(actions,np.array([0,1]),cache,np.array([3.,2.,4.]),np.ones(3,bool),'2020-01-01')
        self.assertTrue(r['ready']);np.testing.assert_array_equal(ti,[0]);np.testing.assert_array_equal(w,[2.])
        self.assertEqual(r['C_rows'],1)
        actions.loc[0,'K_stress_known_date']='2019-12-31'
        r,_,_=check(actions,np.array([0,1]),cache,np.array([3.,2.,4.]),np.ones(3,bool),'2020-01-01')
        self.assertFalse(r['ready']);self.assertIn('K_clock_not_dominated',r['reasons'])

    def test_strict_policy_null_same_and_distinct_unknown(self):
        value=self.function('policy_value');unknown=label('a')
        self.assertTrue(np.isnan(value(dict(selected=1,chosen_action_id='a'),{'a':unknown})))
        self.assertEqual(value(dict(selected=0,chosen_action_id=''),{}),0.)
        cancel=label('c');cancel.update(participation_state='known_nonparticipation',policy_reward_known='1',
                                     policy_reward='0',policy_known_date='2020-02-01',policy_known_phase='after_all_source_close')
        self.assertEqual(value(dict(selected=1,chosen_action_id='c'),{'c':cancel}),0.)
        bad=dict(unknown,primary_domain=0)
        with self.assertRaises(ValueError):value(dict(selected=1,chosen_action_id='a'),{'a':bad})
        a=choices('a');b=a.copy();lookup={r['chosen_action_id']:label(r['chosen_action_id']) for r in a.to_dict('records')}
        report,_=self.function('held_compare')(b,a,lookup,'DOMAIN52')
        self.assertEqual(sum(c['common_unresolved_same_action'] for c in report.values()),4)
        self.assertEqual(sum(c['unknown_differential_selected_events'] for c in report.values()),0)
        b.loc[0,'chosen_action_id']='other';lookup['other']=label('other')
        report,_=m.held_compare(b,a,lookup,'DOMAIN52')
        self.assertEqual(report['holdout_0/2020-01-01']['unknown_differential_selected_events'],1)

    def test_eight_cells_and_both_main_identities_gate(self):
        compare=self.function('held_compare');candidate=choices('b');control=choices('a')
        lookup={}
        for i in range(4):lookup['a'+str(i)]=label('a'+str(i),'1','1','known_K_quote');lookup['b'+str(i)]=label('b'+str(i),'2','1','known_K_quote')
        groups={name:compare(candidate,control,lookup,name)[0] for name in ['DOMAIN52','COMMON52']}
        identity={name:dict(identical_actions=False) for name in groups}
        gate=self.function('after_selection_gate')(groups,identity)
        self.assertTrue(gate['all_eight_held_pass']);self.assertTrue(gate['cash_eligible'])
        groups['COMMON52']['holdout_1/2023-01-01']['nominal_pass']=False
        self.assertFalse(m.after_selection_gate(groups,identity)['cash_eligible'])
        groups['COMMON52']['holdout_1/2023-01-01']['nominal_pass']=True
        identity['DOMAIN52']['identical_actions']=True
        self.assertFalse(m.after_selection_gate(groups,identity)['cash_eligible'])


if __name__=='__main__':unittest.main()
