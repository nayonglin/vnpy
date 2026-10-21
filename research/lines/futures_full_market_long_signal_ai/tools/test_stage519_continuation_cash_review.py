"""Small synthetic causal-clock/adapter checks; no historical reads or books."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np
import pandas as pd

path=Path(__file__).with_name('stage519_continuation_cash_review.py')
spec=importlib.util.spec_from_file_location('test519_subject',path)
v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)


class ContinuationCashReview(unittest.TestCase):
    def test_priority_and_zero_reduction(self):
        self.assertEqual(v.next_exit_reason('lifecycle_exit',True,True,90,80,95),'lifecycle_exit')
        self.assertEqual(v.next_exit_reason(None,True,True,90,80,95),'risk_margin_joint_reduction')
        self.assertEqual(v.next_exit_reason(None,False,True,90,80,95),'ai_continuation_next_open_exit')
        self.assertTrue(v.free_close(False,None,False,5,5))
        self.assertFalse(v.free_close(False,None,False,4,5))
        self.assertFalse(v.free_close(False,None,True,None,5))

    def test_current_date_selects_head_and_missing_flags(self):
        models={}
        for cut,intercept in [('2020-01-01',1.),('2023-01-01',-1.)]:
            models['main|'+cut]=dict(mean=[0.]*6,scale=[1.]*6,coef=[intercept]+[0.]*11+[2.])
        state=dict(mark=11,SL0=9,boundary_next=10,close=11,previous_close=10,N_t=1,R0=.5,age_source_days=2,
            source_lifecycle_target_date='2023-02-01',K_target_date='2023-01-10',t_date='2023-01-03')
        self.assertEqual(v.portable_prediction(models,'2022-12-30',state)[:2],(1.,'2020-01-01'))
        self.assertEqual(v.portable_prediction(models,'2023-01-03',state)[:2],(-1.,'2023-01-01'))
        state['K_target_date']=''
        self.assertEqual(v.portable_prediction(models,'2023-01-03',state)[0],1.)
        self.assertEqual(v.portable_prediction(models,'2019-12-31',state)[0],None)

    def test_terminal_date_never_a_calendar_sentinel(self):
        state=dict(mark=10,SL0=9,boundary_next=9.5,close=10,previous_close=9,N_t=1,R0=.25,age_source_days=1,
            source_lifecycle_target_date='2027-02-01',K_target_date='2027-01-01',t_date='2026-10-16')
        x=v.raw_features(state)
        self.assertEqual(x.tolist(),[4.,2.,4.,4.,1.,77.])
        state['K_target_date']='5587'
        self.assertTrue(np.isnan(v.raw_features(state)[5]))

    def test_empty_optional_adapter_does_not_hide_nonempty_absence(self):
        a=v.schema(pd.DataFrame(),['root_id','date'])
        self.assertEqual(set(a),{'root_id','date'})
        with self.assertRaises(AssertionError):v.schema(pd.DataFrame([{'root_id':'x'}]),['root_id','date'])
        v.compare_fields({'flag':'False','value':'','qty':'2'},dict(flag=False,value=None,qty=2),'synthetic schema')

    def test_strict_primary_gate_and_unknowns_remain(self):
        points=[]
        for w in v.WINDOWS:
            for c in v.COSTS:points.append(dict(window=w,cost=c,active_total_return_pct=1.,
                return_percentage_point_difference=1.,drawdown_percentage_point_difference=1.,ci95_low=.001))
        gate=v.fixed_gate(points,False,True,False);self.assertTrue(gate['nominal_pass'])
        self.assertFalse(v.fixed_gate(points,True,True,False)['nominal_pass'])
        next(x for x in points if (x['window'],x['cost'])==('primary_2020','stress'))['drawdown_percentage_point_difference']=0.
        self.assertFalse(v.fixed_gate(points,False,True,False)['cash_nominal_pass'])

    def test_signal_date_adapter_uses_original_D_index(self):
        frame=pd.DataFrame(dict(u_index=[0.,1.],D_index=['1','2']))
        got=v.signal_execution_dates(frame,['2020-01-02','2020-01-03','2020-01-06'])
        self.assertEqual(got.planned_execution_date.tolist(),['2020-01-03','2020-01-06'])
        bad=frame.copy();bad['D_index']=['2','2']
        with self.assertRaises(AssertionError):v.signal_execution_dates(bad,['2020-01-02','2020-01-03','2020-01-06'])


if __name__=='__main__':unittest.main()
