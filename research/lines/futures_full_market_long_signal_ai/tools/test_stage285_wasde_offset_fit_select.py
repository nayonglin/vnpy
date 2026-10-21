"""Only new tiny285 boundaries; no old data, actual fits or cash."""
import copy
from collections import Counter
import importlib.util
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

PATH=Path(__file__).with_name('stage285_wasde_offset_fit_select.py')
SPEC=importlib.util.spec_from_file_location('tiny285',PATH)
M=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def report(day,q='0.2',number='1',**extra):
    return dict(WasdeNumber=number,release_date=day,release_month=day[:7],
        state='quantity_observed',unknown_reason='',q_raw=q,feature_eligible=True,
        correction_known_at='',sources='["wasde.csv"]',**extra)


class Pulse(unittest.TestCase):
    # Moving availability before the frozen NY boundary would leak this release.
    def test_release_delay_and_dst_use_complete_shanghai_close(self):
        months,_=M.build_months([report('2024-03-08'),report('2024-11-08',number='2')])
        self.assertEqual(months['2024-03']['available_at_utc'],'2024-03-10T05:00:00+00:00')
        self.assertEqual(months['2024-11']['available_at_utc'],'2024-11-10T05:00:00+00:00')
        spring,_=M.build_months([report('2024-03-09')])
        fall,_=M.build_months([report('2024-11-01')])
        self.assertEqual(spring['2024-03']['available_at_utc'],'2024-03-11T04:00:00+00:00')
        self.assertEqual(fall['2024-11']['available_at_utc'],'2024-11-03T04:00:00+00:00')
        summer,_=M.build_months([report('2024-06-10')])
        self.assertEqual(summer['2024-06']['available_at_utc'],'2024-06-12T04:00:00+00:00')
        self.assertFalse(M.pulse_at('DCE.C','2024-06-11',summer)['eligible'])
        self.assertTrue(M.pulse_at('DCE.C','2024-06-12',summer)['eligible'])

    # Carrying a prior report into a missing month would fail this test.
    def test_month_expiry_late_release_missing_and_unmapped(self):
        months,_=M.build_months([report('2024-06-10'),report('2024-07-31',number='2')])
        self.assertTrue(M.pulse_at('DCE.C','2024-06-30',months)['eligible'])
        self.assertFalse(M.pulse_at('DCE.C','2024-07-01',months)['eligible'])
        self.assertFalse(M.pulse_at('DCE.C','2024-08-02',months)['eligible'])
        self.assertFalse(M.pulse_at('DCE.C_F','2024-06-20',months)['eligible'])
        self.assertFalse(M.pulse_at('DCE.CS','2024-06-20',months)['eligible'])

    # A corrected V2, or choosing one of conflicting reports, must never add q.
    def test_v2_duplicate_and_month_conflict(self):
        v2=report('2024-07-10',number='2');v2.update(feature_eligible='False',state='unknown',correction_known_at='unknown',sources='["wasde-V2.csv"]')
        months,audit=M.build_months([report('2024-06-10'),report('2024-06-10',q='0.200',number='1'),v2])
        self.assertEqual(months['2024-06']['duplicate_rows'],1)
        self.assertNotIn('2024-07',months)
        self.assertTrue(any(r['state']=='excluded_projection' for r in audit))
        conflicting,_=M.build_months([report('2024-06-10'),report('2024-06-10',q='0.3',number='3')])
        self.assertEqual(conflicting['2024-06']['state'],'conflicting_publication_month')
        self.assertFalse(M.pulse_at('DCE.C','2024-06-20',conflicting)['eligible'])


class Offset(unittest.TestCase):
    # Fitting an intercept or renormalizing source-only weights changes 8/5.
    def test_weighted_single_scalar_solution_and_unsupported(self):
        fit,z=M.fit_scalar(np.array([1.,3.]),np.array(['r1','r2']),np.array([-2.,2.]),np.array([2.,2.]))
        self.assertEqual(fit['status'],'supported')
        self.assertEqual(fit['mean'],2.)
        self.assertEqual(fit['scale'],1.)
        np.testing.assert_array_equal(z,[-1.,1.])
        self.assertAlmostEqual(fit['gamma'],1.6)
        unsupported,z=M.fit_scalar(np.array([1.,3.]),np.array(['same','same']),np.array([-2.,2.]),np.array([2.,2.]))
        self.assertEqual(unsupported['gamma'],0.)
        self.assertEqual(unsupported['status'],'unsupported')
        constant,_=M.fit_scalar(np.array([2.,2.]),np.array(['r1','r2']),np.array([-2.,2.]),np.array([2.,2.]))
        self.assertEqual(constant['gamma'],0.)

    # Replacing immutable beta/intercept with a refit breaks the literal score.
    def test_frozen_52_score_and_residual_keep_original_base(self):
        scaler={'common':{'mean':[0.]*26,'scale':[2.]*26}}
        raw=np.zeros((2,26));raw[0,0]=4.;raw[1,0]=np.nan
        model={'coef':[3.]+[0.]*25+[7.]+[0.]*25,'intercept':5.}
        before=copy.deepcopy(model)
        s=M.frozen_scores(raw,scaler,model)
        np.testing.assert_array_equal(s,[11.,12.])
        np.testing.assert_array_equal(np.array([13.,9.])-s,[2.,-3.])
        self.assertEqual(model,before)

    # Adding floating zero can alter -0; non-C rows must retain exact old bits.
    def test_zero_design_preserves_old_bits_and_negative_can_turn_positive(self):
        old=np.array([-0.,-1.,2.,-0.5])
        q=np.array([np.nan,np.nan,np.nan,3.])
        fit=dict(status='supported',mean=2.,scale=1.,gamma=1.)
        new,z,delta=M.shift_scores(old,q,fit)
        np.testing.assert_array_equal(new[:3].view(np.uint64),old[:3].view(np.uint64))
        self.assertEqual(new[3],0.5)
        self.assertEqual(delta[3],1.)

    # Date-only maturity, changing weights and K-filtered training must fail.
    def test_training_identity_validation_restores_exact_weights(self):
        row=dict(sequence_index='0',action_id='a',product_id='DCE.C',family_id='DCE.C',
            u_date='2019-12-30',u_index='0',reference_epoch='DCE.C.202006',
            u_action_eligible='1',label_known_date='2019-12-31',label_state='closed_complete_bar_model',
            net_R_stress='1.25',sample_weight='0.10000000000000002')
        f=M.validate_training(pd.DataFrame([row]),'2020-01-01',1)
        self.assertEqual(f.sample_weight.iloc[0].hex(),float('0.10000000000000002').hex())
        bad=pd.DataFrame([dict(row,label_known_date='2020-01-01')])
        with self.assertRaises(ValueError):M.validate_training(bad,'2020-01-01',1)


class CompleteChoice(unittest.TestCase):
    # A prefilter on old positivity or accidental held reuse loses the new entry.
    def test_score_stream_shifts_full_main_and_skips_held(self):
        fields=M.old_helper(True).SCORE_FIELDS
        row=dict(zip(fields,['0','a','0','p0','DCE.C','DCE.C','2024-06-20','0',
            'DCE.C.202408','DCE.C.202408','1','-0.5','main','2023-01-01']))
        outside=dict(row,sequence_index='1',action_id='b',mother_sequence_index='1',mother_event_id='p1',
            product_id='DCE.X',family_id='DCE.X',reference_epoch='DCE.X.202408',anchor_epoch='DCE.X.202408',score='-0.0')
        months,_=M.build_months([report('2024-06-10')]);corn=[];counts=Counter()
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'tiny_scores.csv.gz'
            pd.DataFrame([row,outside,dict(row,scope='holdout_1')]).to_csv(path,index=False)
            values=list(M.forward_stream(path,{'2023-01-01':dict(status='supported',mean=.1,scale=.1,gamma=1.)},months,counts,corn.append))
        self.assertEqual(len(values),2)
        self.assertAlmostEqual(values[0]['score'],.5)
        self.assertEqual(float(values[1]['score']).hex(),float('-0.0').hex())
        self.assertEqual(counts['non_main_scores_skipped'],1)
        self.assertEqual(len(corn),1)

    # A filter over old winners misses the newly positive action; K must precede max.
    def test_full_new_pool_keeps_empty_parent_and_cross_month_D(self):
        cal=['2024-05-30','2024-05-31','2024-06-03','2024-07-01']
        mothers=[dict(sequence_index=0,event_id='p0',product_id='DCE.C',family_id='DCE.C',u_date='2024-05-31',u_index=1,reference_epoch='DCE.C.202407'),
            dict(sequence_index=1,event_id='p1',product_id='DCE.X',family_id='DCE.X',u_date='2024-05-31',u_index=1,reference_epoch='DCE.X.202408')]
        rows=[dict(sequence_index=0,action_id='expired',mother_sequence_index=0,mother_event_id='p0',product_id='DCE.C',family_id='DCE.C',u_date='2024-05-31',u_index=1,reference_epoch='DCE.C.202407',anchor_epoch='DCE.C.202407',u_action_eligible=1,score=9.,scope='main',cutoff='2023-01-01'),
            dict(sequence_index=1,action_id='new',mother_sequence_index=0,mother_event_id='p0',product_id='DCE.C',family_id='DCE.C',u_date='2024-05-31',u_index=1,reference_epoch='DCE.C.202408',anchor_epoch='DCE.C.202407',u_action_eligible=1,score=.5,scope='main',cutoff='2023-01-01')]
        result=M.select_full(mothers,iter(rows),cal,'2024-06-03')
        self.assertEqual(len(result['choices']),2)
        self.assertEqual(result['choices'][0]['chosen_action_id'],'new')
        self.assertEqual(result['choices'][1]['selection_state'],'no_observed_children')
        self.assertEqual(result['choices'][0]['candidate'],M.CANDIDATE)


if __name__=='__main__':unittest.main()
