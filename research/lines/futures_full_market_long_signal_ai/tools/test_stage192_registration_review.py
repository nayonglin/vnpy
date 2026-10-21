"""Five bounded reviewer fault injections; no real input, fit or cash replay."""
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
import numpy as np
import pandas as pd

SOURCE=Path(__file__).with_name('stage192_registration_review.py')


class IndependentReviewFixtures(unittest.TestCase):
    def setUp(self):
        spec=importlib.util.spec_from_file_location('fixture192',SOURCE)
        self.m=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.m)

    def test_streamed_new_file_and_ledger_copy_cache_reject_tampering(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'daily.csv.gz';pd.DataFrame(dict(date=['2020-01-02'],equity=[1000000.125],ever_insolvent=[False])).to_csv(path,index=False)
            pd.DataFrame(dict(date=['2020-01-03'],equity=[999999.875],ever_insolvent=[False])).to_csv(path,index=False,mode='a',header=False)
            b=self.m.binding(path);fakecash=SimpleNamespace(csv=lambda path:None);fakediag=SimpleNamespace(_read=lambda d,n:None)
            with self.m.ledger_cache(dict(ledgers=dict(daily=b)),fakecash,fakediag):
                first=fakecash.csv(path);first.loc[0,'equity']='wrong'
                self.assertEqual(fakecash.csv(path).equity.tolist(),['1000000.125','999999.875'])
                frame=fakediag._read(Path(folder),'daily');self.assertEqual(frame.equity.tolist(),[1000000.125,999999.875])
            self.assertEqual(self.m.DISK_READS[str(path.resolve())],1)
            raw=bytearray(path.read_bytes());raw[-1]^=1;path.write_bytes(raw)
            with self.assertRaises((AssertionError,OSError,EOFError)):
                self.m.table(b)

    def test_projection_clock_true_zero_missing_and_parent_identity_are_enforced(self):
        cal=['2020-01-02','2020-01-03','2020-01-06','2020-01-07']
        a=pd.DataFrame([dict(action_id='a'+str(i),event_id='a'+str(i),action_sequence_index=i,mother_sequence_index=i,mother_event_id='p'+str(i),product_id='SHFE.CU',family_id='F',u_date=cal[2],u_index=2,reference_epoch='SHFE.CU.202005',anchor_epoch='SHFE.CU.202005') for i in range(2)])
        p=a.copy();p['scalar_primary']=['0',''];p['scalar_missing']=['0','1'];p['feature_state']=['conditional_archive_scalar_known','report_pair_unavailable']
        for k,v in dict(decision_index='2',decision_date=cal[2],prospective_entry_index='3',prospective_entry_date=cal[3],report_v_index='1',report_v=cal[1],report_w_index='0',report_w=cal[0]).items():p[k]=v
        q=self.m.align_q(a,p,cal);self.assertEqual(q[0],0.);self.assertTrue(np.isnan(q[1]))
        changed=p.copy();changed.loc[1,'report_v_index']='2'
        with self.assertRaises(AssertionError):self.m.align_q(a,changed,cal)
        changed=p.copy();changed.loc[1,'scalar_primary']='0'
        with self.assertRaises(AssertionError):self.m.align_q(a,changed,cal)
        changed=p.copy();changed.loc[1,'mother_event_id']='other'
        with self.assertRaises(AssertionError):self.m.align_q(a,changed,cal)

    def test_control_zero_shared_missing_strict_maturity_and_equation_mutation(self):
        q=np.array([0.,1.,np.nan]);w=np.array([1.,3.,100.]);stat=self.m.q_statistics(q,w)
        self.assertEqual((stat['mean'],stat['var'],stat['finite_count']),(.75,.1875,2))
        x=np.zeros((3,26));scaler=dict(common=dict(mean=[0.]*26,scale=[1.]*26))
        c=self.m.design54(x,q,scaler,stat,'CONTROL54');a=self.m.design54(x,q,scaler,stat,'REGISTRATION54')
        np.testing.assert_array_equal(c[:,:53],a[:,:53]);np.testing.assert_array_equal(c[:,53],np.zeros(3));self.assertEqual(a[-1,52],1.);self.assertEqual(a[-1,53],0.)
        rows=pd.DataFrame([dict(u_action_eligible=1,label_state='closed_complete_bar_model',u_date='2019-01-01',label_known_date=d,net_R_stress=1.,family_id='F') for d in ('2019-12-31','2020-01-01','')])
        self.assertEqual(self.m.mature_mask(rows,'main','2020-01-01').tolist(),[True,False,False])
        X=np.zeros((2,54));X[:,53]=[-1.,1.];lhs,rhs=self.m.normal_equations(X,[-1.,1.],[1.,1.]);beta=np.zeros(55);beta[53]=2/3
        self.m.compare(lhs@beta,rhs,'fixture normal equation')
        beta[53]+=.01
        with self.assertRaises(AssertionError):self.m.compare(lhs@beta,rhs,'injected wrong beta')

    def test_full_K_preargmax_and_family_ordinary_priority_retain_empty_parent(self):
        cal=['2020-01-02','2020-01-03','2020-02-03','2020-03-02']
        parents=[dict(sequence_index=i,event_id='p'+str(i),product_id=p,family_id=f,u_date=cal[0],u_index=0,reference_epoch=e) for i,p,f,e in [(9,'SHFE.CU','F','SHFE.CU.202002'),(2,'SHFE.CU_F','F','SHFE.CU_F.202004'),(10,'DCE.S','S','')]]
        children=[dict(sequence_index=i,action_id='a'+str(i),mother_sequence_index=seq,mother_event_id='p'+str(seq),product_id=p,family_id='F',u_date=cal[0],u_index=0,reference_epoch=e,anchor_epoch='SHFE.CU.202002',u_action_eligible=1,score=score) for i,seq,p,e,score in [(0,9,'SHFE.CU','SHFE.CU.202002',10.),(1,9,'SHFE.CU','SHFE.CU.202004',2.),(2,2,'SHFE.CU_F','SHFE.CU_F.202004',99.)]]
        bounds={r['reference_epoch']:self.m.reuse().deadline(r['reference_epoch'],cal,'2026-10-16') for r in children}
        result=self.m.vector_choices(pd.DataFrame(parents),pd.DataFrame(children),bounds,cal,'holdout_1','REGISTRATION54','2020-01-01')
        self.assertEqual(result.chosen_action_id.tolist(),['a1','','']);self.assertEqual(result.selection_state.iloc[2],'no_observed_children')

    def test_fixed_gate_preserves_unknown_and_physical_completion_counts(self):
        points={(w,c):dict(active_total_return_pct=1.,return_percentage_point_difference=1.,drawdown_percentage_point_difference=1.,ci95_low=.01) for w in self.m.WINDOWS for c in self.m.COSTS}
        held=dict(groups={g:dict(known_u_equal_mean_increment_R=0.,nominal_pass=True,unknown_differential_selected_events=0,status='supported') for g in ('holdout_0','holdout_1')})
        self.assertTrue(self.m.fixed_gate(points,held,False,True,False)['nominal_pass'])
        held['groups']['holdout_1']['unknown_differential_selected_events']=1
        self.assertFalse(self.m.fixed_gate(points,held,False,True,False)['nominal_pass'])
        points['primary_2020','stress']['return_percentage_point_difference']=0.
        self.assertFalse(self.m.fixed_gate(points,held,False,True,False)['cash_nominal_pass'])
        points['cold_2023','base']['drawdown_percentage_point_difference']=None
        self.assertEqual(self.m.fixed_gate(points,held,False,True,False)['status'],'unknown_control_drawdown')
        terminal=dict(status='completed',cash_accounts_started=8,new_cash_accounts=8,raw_ledgers_checkpointed=8,native_source_queries=0,new_labels=0,old_control_book_replays=0,no_automatic_resume=True)
        self.m.financial_completion(terminal);terminal['new_cash_accounts']=7
        with self.assertRaises(AssertionError):self.m.financial_completion(terminal)


if __name__=='__main__':unittest.main()
