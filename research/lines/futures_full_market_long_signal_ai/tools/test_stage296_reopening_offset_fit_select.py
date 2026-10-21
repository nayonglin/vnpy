"""New296 synthetic contracts only: no original arrays, labels, fits or cash."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np
import pandas as pd

SPEC=importlib.util.spec_from_file_location('tiny296',Path(__file__).with_name('stage296_reopening_offset_fit_select.py'))
M=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(M)


def row(**extra):
    r=dict(sequence_index='0',action_id='a',product_id='DCE.C',family_id='DCE.C',u_date='2019-12-30',u_index='0',
        reference_epoch='DCE.C.202006',u_action_eligible='1',label_known_date='2019-12-31',
        label_state='closed_complete_bar_model',net_R_stress='2',sample_weight='0.10000000000000002')
    r.update(extra);return r


class Training(unittest.TestCase):
    # Treating legal zero q as missing, or assigning a nonzero missing delta, fails.
    def test_legal_zero_standardizes_and_missing_preserves_bits(self):
        model=dict(status='supported',mean=1.,scale=1.,gamma=2.)
        new,z,d=M.helpers().shift_scores(np.array([3.,-0.]),np.array([0.,np.nan]),model)
        np.testing.assert_array_equal(z,[-1.,0.]);np.testing.assert_array_equal(d,[-2.,0.])
        self.assertEqual(new[0],1.);self.assertEqual(new[1].hex(),float('-0.').hex())

    # Borrowing main gamma/base for held changes the literal six own-fold outputs.
    def test_each_scope_uses_its_own_residual_fit_and_date_support(self):
        q=np.array([0.,2.]);w=np.array([2.,2.]);dates=np.array(['2019-01-02','2019-01-03'])
        first,z=M.fit_scalar(q,dates,np.array([-2.,2.]),w)
        second,_=M.fit_scalar(q,dates,np.array([2.,-2.]),w)
        self.assertAlmostEqual(first['gamma'],1.6);self.assertAlmostEqual(second['gamma'],-1.6)
        self.assertEqual(first['distinct_u_dates'],2)
        bad,_=M.fit_scalar(q,np.array(['same','same']),np.array([-2.,2.]),w)
        self.assertEqual(bad['status'],'unsupported');self.assertEqual(bad['gamma'],0.)
        shifted=M.shift_row(dict(sequence_index='0',scope='holdout_0',cutoff='2020-01-01',score='-0.5'),
            np.array([2.]),{('main','2020-01-01'):first,('holdout_0','2020-01-01'):second})
        self.assertAlmostEqual(shifted['score'],-2.1)

    # A held family entering training, or weight rerounding, changes the contract.
    def test_held_exclusion_and_weight_restore(self):
        frame=pd.DataFrame([row()])
        result=M.validate_training(frame,'holdout_0','2020-01-01',1)
        self.assertEqual(result.sample_weight.iloc[0].hex(),float('0.10000000000000002').hex())
        with self.assertRaises(ValueError):M.validate_training(frame,'holdout_1','2020-01-01',1)

    # Row offsets or collapsing unavailable q and true zero would corrupt identity.
    def test_source_vector_sequence_and_availability(self):
        q=M.validate_vector(np.array([0,1,2]),np.array([0.,np.nan,-2.]),np.array([True,False,True]),3)
        self.assertEqual(q[0],0.);self.assertTrue(np.isnan(q[1]))
        np.testing.assert_array_equal(M.validate_vector(np.arange(3),q,np.array([1,0,1],dtype=np.uint8),3),q)
        with self.assertRaises(ValueError):M.validate_vector(np.array([0,2,1]),q,np.isfinite(q),3)
        with self.assertRaises(ValueError):M.validate_vector(np.arange(3),q,np.array([False,False,True]),3)
        with self.assertRaises(ValueError):M.validate_vector(np.arange(3),q,np.array([2,0,1],dtype=np.uint8),3)


class Selection(unittest.TestCase):
    # Lost private scope alias skips every held score; future K must precede max.
    def test_full_held_scope_keeps_no_child_and_month_K(self):
        mothers=[dict(sequence_index=0,event_id='p',product_id='DCE.C',family_id='DCE.C',u_date='2024-05-31',u_index=1,reference_epoch='DCE.C.202407'),
            dict(sequence_index=1,event_id='empty',product_id='DCE.C_F',family_id='DCE.C',u_date='2024-05-31',u_index=1,reference_epoch='DCE.C_F.202408')]
        score=dict(sequence_index=0,action_id='late',mother_sequence_index=0,mother_event_id='p',product_id='DCE.C',family_id='DCE.C',u_date='2024-05-31',u_index=1,reference_epoch='DCE.C.202407',anchor_epoch='DCE.C.202407',u_action_eligible=1,score=9.,scope='holdout_1',cutoff='2023-01-01')
        valid=dict(score,sequence_index=1,action_id='valid',reference_epoch='DCE.C.202408',score=.5)
        result=M.select_scope(mothers,iter([score,valid]),'holdout_1',['2024-05-30','2024-05-31','2024-06-03','2024-07-01'],'2024-06-03')
        self.assertEqual(len(result['choices']),2)
        self.assertEqual(result['choices'][0]['chosen_action_id'],'valid')
        self.assertEqual(result['choices'][1]['selection_state'],'no_observed_children')
        self.assertEqual(result['choices'][0]['scope'],'holdout_1')
        self.assertEqual(result['choices'][0]['candidate'],M.CANDIDATE)

    # Same unresolved action is increment zero; a different unknown is never zero.
    def test_held_unknown_semantics_and_known_date_cutoff(self):
        a=[];b=[]
        for i,(old,new) in enumerate([('same','same'),('known','unknown'),('','')]):
            common=dict(sequence_index=i,event_id='p'+str(i),family_id='F'+str(i),u_index=0,u_date='2026-10-16',scope='holdout_0',
                chosen_action_id=old,selected=int(bool(old)),arm='A')
            a.append(common);b.append(dict(common,arm='B',chosen_action_id=new,selected=int(bool(new))))
        actions=pd.DataFrame([dict(action_id='same',label_state='open_right_censored',participation_state='filled',net_R_stress=np.nan,label_known_date=''),
            dict(action_id='known',label_state='closed_complete_bar_model',participation_state='filled',net_R_stress=1.,label_known_date='2026-10-16'),
            dict(action_id='unknown',label_state='closed_complete_bar_model',participation_state='filled',net_R_stress=2.,label_known_date='2026-10-17')])
        diagnostic,daily,_=M.helpers().old_helper().held_diagnostics(pd.DataFrame(a+b),actions)
        g=diagnostic['groups']['holdout_0']
        self.assertEqual(g['full_family_u'],3);self.assertEqual(g['known_increment_family_u'],2)
        self.assertEqual(g['unknown_differential_selected_events'],1)
        self.assertEqual(g['common_unresolved_same_action'],1)
        self.assertEqual(g['known_u_equal_mean_increment_R'],0.)


if __name__=='__main__':unittest.main()
