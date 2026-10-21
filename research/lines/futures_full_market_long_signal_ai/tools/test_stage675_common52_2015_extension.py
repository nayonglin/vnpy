"""Bounded synthetic contract tests; no real model, price cache or cash books."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np
import pandas as pd

P=Path(__file__).with_name('stage675_common52_2015_extension.py')

class ExtensionContract(unittest.TestCase):
    def setUp(self):
        self.assertTrue(P.exists(), 'Stage675 implementation missing')
        spec=importlib.util.spec_from_file_location('fixture675', P)
        self.m=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.m)

    def fixture(self):
        dates=['2014-12-31','2015-01-05','2015-02-02','2020-01-02','2023-01-03']
        parents=pd.DataFrame([dict(sequence_index=i,event_id=f'p{i}',product_id='P.X',family_id='P.X',u_date=d,u_index=i,reference_epoch='P.X.201503' if i<3 else 'P.X.202004' if i==3 else 'P.X.202304') for i,d in enumerate(dates)])
        rows=[]
        for i,p in enumerate(parents.to_dict('records')):
            rows.append(dict(p, sequence_index=i,action_sequence_index=i,event_id=f'a{i}',action_id=f'a{i}',mother_sequence_index=i,mother_event_id=p['event_id'],actual_epoch=p['reference_epoch'],anchor_epoch=p['reference_epoch'],u_action_eligible=1,entry_capacity_qty=1,label_history_ready20=1,label_state='closed_complete_bar_model',label_known_date='2014-12-31' if i==0 else '2026-01-01',net_R_stress=1.,entry_index=i,exit_index=i+1))
        return dates,parents,pd.DataFrame(rows)

    def scores(self):
        dates,p,a=self.fixture();a=a.loc[a.u_date.ge('2015-01-01')].copy()
        a['scope']='main';a['score']=1.;a['cutoff']=[self.m.cutoff_for(d) for d in a.u_date]
        return dates,p,a

    def test_two_clock_train_mask_and_unresolved_predictions(self):
        _,p,a=self.fixture()
        late=a.iloc[[0]].copy();late['sequence_index']=9;late['action_id']='late';late['label_known_date']='2015-01-01'
        a=pd.concat([a,late],ignore_index=True);a.loc[a.u_date.eq('2015-01-05'),'label_state']='path_or_execution_unknown'
        train,pred,_=self.m.training_support(a,p)
        self.assertEqual(train.action_id.tolist(),['a0'])
        self.assertEqual(pred.action_id.tolist(),['a1','a2'])

    def test_exact_three_era_score_schedule_rejects_wrong_cutoff_or_held(self):
        _,_,s=self.scores();self.m.validate_score_schedule(s)
        self.assertEqual(s.cutoff.tolist(),['2015-01-01','2015-01-01','2020-01-01','2023-01-01'])
        bad=s.copy();bad.loc[bad.u_date.lt('2020-01-01'),'cutoff']='2020-01-01'
        with self.assertRaisesRegex(ValueError,'cutoff'):self.m.validate_score_schedule(bad)
        bad=s.copy();bad.iloc[0,bad.columns.get_loc('scope')]='holdout_0'
        with self.assertRaisesRegex(ValueError,'main'):self.m.validate_score_schedule(bad)

    def test_historical_K_and_corrected_cutoff_keep_complete_parents_and_overlap(self):
        dates,p,s=self.scores();forward=p.loc[p.u_date.ge('2015-01-01')]
        result=self.m.select_choices(forward,s,dates,'2026-10-16')
        choices=pd.DataFrame(result['choices'])
        self.assertEqual(len(choices),len(forward))
        self.assertEqual(choices.cutoff.tolist(),s.cutoff.tolist())
        self.assertEqual(result['boundaries']['P.X.201503']['K_index'],2)
        self.assertEqual(choices.iloc[0].selected,0) # D equals K, still retain parent.
        old=choices.loc[choices.u_date.ge('2020-01-01')].copy()
        self.assertEqual(self.m.check_overlap(choices,old)['parent_rows'],2)
        bad=old.copy();bad.iloc[0,bad.columns.get_loc('chosen_action_id')]='counterfeit'
        with self.assertRaisesRegex(ValueError,'overlap'):self.m.check_overlap(choices,bad)

    def test_union_weight_duplicate_mass_and_equal_u_contract(self):
        f=pd.DataFrame(dict(family_id=['x','x','x','y'],u_date=['d0','d0','d1','d1'],entry_index=[1,1,2,2],exit_index=[3,2,3,2]))
        w,g=self.m.fit.training_weights(f)
        self.assertAlmostEqual(w.sample_weight.iloc[0],w.sample_weight.iloc[1])
        self.assertTrue(np.allclose(w.groupby(f.u_date).sample_weight.sum(),2.))
        self.assertAlmostEqual(g.loc[g.u_date.eq('d0'),'uniqueness'].iloc[0],2/3)

    def test_dataset_alias_schema_and_full_canonical_identity(self):
        _,p,a=self.fixture();common=np.zeros((len(a),26))
        self.m.validate_dataset_arrays(a,p,common,full=False)
        bad=a.copy();bad.loc[0,'mother_event_id']='other'
        with self.assertRaisesRegex(ValueError,'parent'):self.m.validate_dataset_arrays(bad,p,common,full=False)
        with self.assertRaisesRegex(ValueError,'COMMON'):self.m.validate_dataset_arrays(a,p,np.zeros((len(a),25)),full=False)
        sig=pd.DataFrame([dict(u_index=1,u_date=p.iloc[1].u_date,event_id='a1')])
        _,refs=self.m.cash.author.organize(sig,p,p.u_date.tolist())
        self.assertEqual(refs[2]['P.X'],'P.X.201503')

if __name__=='__main__':unittest.main()
