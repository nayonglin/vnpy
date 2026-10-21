"""Finite new semantic boundaries; no actual native data, fit, or cash run."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np
import pandas as pd

P=Path(__file__).with_name('stage132_contract_choice_review.py')

class ContractChoiceReviewBoundaries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec=importlib.util.spec_from_file_location('review132',P)
        cls.m=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.m)

    def test_roundtrip_capacity_integer_lots_and_missing(self):
        self.assertEqual(self.m.capacity(199.,1),(1,0))
        self.assertEqual(self.m.capacity(200.,1),(2,1))
        self.assertEqual(self.m.capacity(399.,2),(2,0))
        self.assertEqual(self.m.capacity(400.,2),(4,2))
        self.assertEqual(self.m.capacity(float('nan'),1),(None,None))
        self.assertEqual(self.m.capacity(1000.,0),(None,None))

    def test_anchor_persistence_and_no_off_anchor_DAY(self):
        self.assertIsNone(self.m.request(None,'near','near',5,100))
        self.assertEqual(self.m.request(None,'near','far',5,100),'anchor_canonical_changed')
        self.assertEqual(self.m.request('anchor_canonical_changed','near','near',6,100),'anchor_canonical_changed')
        self.assertEqual(self.m.request(None,'near','',5,100),'anchor_canonical_missing')
        self.assertEqual(self.m.request(None,'near','near',100,100),'held_lifecycle')

    def test_union_weights_do_not_multiply_month_mass(self):
        a=pd.DataFrame(dict(family_id=['f','g'],u_date=['2020-01-01']*2,entry_index=[1,1],exit_index=[3,3]))
        b=pd.concat([a,a.iloc[[0]]],ignore_index=True)
        wa=self.m.union_weights(a);wb=self.m.union_weights(b)
        self.assertAlmostEqual(wa['p_a'][0],wb['p_a'][0]+wb['p_a'][2])
        self.assertAlmostEqual(wb['sample_weight'].mean(),1.)
        c=pd.DataFrame(dict(family_id=['f','f'],u_date=['2020-01-01','2020-01-02'],entry_index=[1,2],exit_index=[3,4]))
        wc=self.m.union_weights(c)
        np.testing.assert_allclose(wc['group_uniqueness'],[2/3,2/3])
        self.assertEqual(wc['union_length'].tolist(),[3,3])

    def test_selection_is_product_month_then_normal_F(self):
        rows=pd.DataFrame(dict(action_id=['a','b','c','d'],actual_epoch=['X.P.202001','X.P.202002','X.P_F.202001','X.P.202003'],product_id=['X.P','X.P','X.P_F','X.P'],family_id=['X.P']*4,u_date=['2020-01-01']*4,anchor_epoch=['X.P.202001']*2+['X.P_F.202001','X.P.202001'],u_action_eligible=[1,1,1,0],score=[1.,2.,20.,100.]))
        a=self.m.choose(rows,'A');b=self.m.choose(rows,'B')
        self.assertEqual(a,{('X.P','2020-01-01'):'a'})
        self.assertEqual(b,{('X.P','2020-01-01'):'b'})
        rows.loc[1,'score']=float('nan');self.assertEqual(self.m.choose(rows,'B'),a)

    def test_capacity_gross_no_netting_exact_previous(self):
        f=pd.DataFrame(dict(account_id=['a']*3,epoch=['e']*3,date=['2020-01-02']*3,side=['BUY','SELL','SELL'],qty=[1,1,1]))
        bars={('e','2020-01-01'):(10.,11.,9.,10.,200.,'accepted')}
        q=self.m.audit_capacity_rows(f,bars,['2020-01-01','2020-01-02'],{'e':{'round_lot':1}})
        self.assertEqual([x['cumulative_gross_qty']for x in q],[1,2,3])
        self.assertEqual([x['execution_capacity_unknown']for x in q],[False,False,True])
        q=self.m.audit_capacity_rows(f,{('e','2019-12-31'):bars[('e','2020-01-01')]},['2020-01-01','2020-01-02'],{'e':{'round_lot':1}})
        self.assertTrue(all(x['execution_capacity_unknown']for x in q))

    def test_known_identical_zero_does_not_zero_unknown_differential(self):
        labels={'x':dict(label_state='path_or_execution_unknown',participation_state='filled',label_known_date='',net_R_stress=np.nan),'z':dict(label_state='closed_complete_bar_model',participation_state='filled',label_known_date='2020-01-02',net_R_stress=2.)}
        self.assertEqual(self.m.choice_increment('x','x',labels,'2026-10-16'),(0.,False,True))
        v,u,c=self.m.choice_increment('x','z',labels,'2026-10-16');self.assertTrue(u);self.assertIsNone(v)
        self.assertEqual(self.m.choice_increment('','z',labels,'2026-10-16'),(2.,False,False))

    def test_family_winner_belongs_to_one_exact_parent_not_empty_F_mother(self):
        for F_observed in (False,True):
            parents=pd.DataFrame(dict(sequence_index=[0,1],event_id=['m','mf'],product_id=['X.P','X.P_F'],family_id=['X.P']*2,u_date=['2020-01-01']*2,u_index=[10,10],reference_epoch=['X.P.203001','X.P_F.203001' if F_observed else '']))
            pred=pd.DataFrame([dict(sequence_index=0,action_id='a',event_id='a',mother_sequence_index=0,mother_event_id='m',actual_epoch='X.P.203001',reference_epoch='X.P.203001',product_id='X.P',family_id='X.P',u_date='2020-01-01',u_index=10,anchor_epoch='X.P.203001',u_action_eligible=1)])
            if F_observed:
                pred=pd.concat([pred,pd.DataFrame([dict(sequence_index=1,action_id='f',event_id='f',mother_sequence_index=1,mother_event_id='mf',actual_epoch='X.P_F.203001',reference_epoch='X.P_F.203001',product_id='X.P_F',family_id='X.P',u_date='2020-01-01',u_index=10,anchor_epoch='X.P_F.203001',u_action_eligible=1)])],ignore_index=True)
            rows=[]
            for arm in('A','B'):
                for m in parents.to_dict('records'):
                    chosen=m['sequence_index']==0;proposed='a' if chosen else 'f' if F_observed else ''
                    rows.append(dict(m,arm=arm,scope='main',cutoff='2020-01-01',policy='NARROW',anchor_epoch=m['reference_epoch'],chosen_action_id='a' if chosen else '',chosen_epoch='X.P.203001' if chosen else '',chosen_action_sequence_index=0 if chosen else -1,selected=int(chosen),score=1. if chosen else np.nan,proposed_action_id=proposed,proposed_epoch=m['reference_epoch'] if proposed else '',proposed_score=1. if proposed=='a' else 2. if proposed else np.nan,selection_state='selected' if chosen else 'family_priority_suppressed' if F_observed else 'no_observed_children'))
            self.assertEqual(self.m.check_choice_rows(pd.DataFrame(rows),parents,pred,np.array([1.,2.] if F_observed else [1.]),'main','2020-01-01'),4)

    def test_rejections_compare_values_not_in_memory_dtypes(self):
        budgets=pd.DataFrame(dict(budget_id=['b0','b1'],event_id=['a','b'],D_qty=[0.,1.],allocated_risk=[20.,30.],qty_cap=[float('nan'),1.],D_state=['entry_execution_unknown','entered'],pre_window_reservation=[True,False]))
        rejects=pd.DataFrame(dict(budget_id=['b0'],event_id=['a'],D_qty=['0'],allocated_risk=['20.000'],qty_cap=[''],D_state=['entry_execution_unknown'],pre_window_reservation=['true']))
        self.assertEqual(self.m.rejection_equivalence(budgets,rejects),[])
        with self.assertRaises(AssertionError):self.m.rejection_equivalence(budgets,rejects.assign(D_state='entered'))

    def test_writer_missing_all_empty_columns_is_equivalent(self):
        a=pd.DataFrame(dict(budget_id=['b'],D_qty=[0.],event_id=['a'],D_state=['no_fill'],D_unit_margin_plus_fee=[np.nan],root_id=['']))
        b=pd.DataFrame(dict(budget_id=['b'],D_qty=['0'],event_id=['a'],D_state=['no_fill']))
        self.assertEqual(self.m.rejection_equivalence(a,b),[])
        with self.assertRaises(AssertionError):self.m.rejection_equivalence(a.assign(D_unit_margin_plus_fee=1.),b)
        with self.assertRaises(AssertionError):self.m.rejection_equivalence(a.assign(root_id='real_root'),b)

    def test_native_gap_rewarm_and_own_atr_not_recursive_N(self):
        days=np.arange(30);x=np.array([[100.+k,102.+k,99.+k,101.+k,1000.]for k in days]);x[27,1]+=20.
        N,L,run=self.m.indicator_arrays(days,x,np.ones(30,bool))
        store=dict(days=days,values=x,valid=np.ones(30,bool),N=N,low20=L,run=run)
        own=self.m.own_features(store,29)
        self.assertNotAlmostEqual(own[10]*x[29,3],N[29])
        valid=np.ones(30,bool);valid[18]=False
        N,L,run=self.m.indicator_arrays(days,x,valid)
        self.assertTrue(np.isnan(N[29]));self.assertEqual(run[29],11)

    def test_full_child_path_keeps_off_anchor_until_anchor_change(self):
        from types import SimpleNamespace
        from datetime import date,timedelta
        import stage102_cash_adapter as cash
        days=[(date(2020,1,1)+timedelta(days=k)).isoformat()for k in range(30)]
        store=self.m.NativeBars(days)
        indexes=np.arange(30,dtype=np.int32)
        x=np.array([[100+.1*k,101+.1*k,99.9+.1*k,100.5+.1*k,1000.]for k in indexes])
        N,L,run=self.m.indicator_arrays(indexes,x,np.ones(30,bool))
        for epoch in('X.P.203001','X.P.203002'):store.series[epoch]=dict(days=indexes,values=x.copy(),accepted=np.ones(30,bool),valid=np.ones(30,bool),N=N,low20=L,run=run)
        row=SimpleNamespace(reference_epoch='X.P.203002',u_index=20,anchor_epoch='X.P.203001',product_id='X.P')
        e=dict(economics_status='exact_epoch_metadata_snapshot',contract_multiplier=10,round_lot=1,tick_size=None,listed_date='2019-01-01')
        refs={('X.P',k):'X.P.203001'if k<22 else'X.P.203002'for k in range(30)}
        state,result=self.m.audit_label_path(row,store,e,refs,29,cash)
        self.assertEqual(state,'closed_complete_bar_model');self.assertEqual(result['entry_index'],21);self.assertEqual(result['exit_index'],23)
        self.assertAlmostEqual(result['exit_reference'],102.3)

if __name__=='__main__':unittest.main()
