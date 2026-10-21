"""Four synthetic behavior checks only; no old financial input or network."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np
import pandas as pd

_spec = importlib.util.spec_from_file_location('pmi567_tested',Path(__file__).with_name('stage567_pmi_residual_fit.py'))
m = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(m)

class TestPMIResidual(unittest.TestCase):
    def test_each_report_equal_despite_many_contract_rows(self):
        macro = pd.DataFrame(dict(u_index=[0,1],u_date=['2019-01-02','2019-02-04'],macro_available=[1,1],report_month=['2019-01','2019-02'],NO=[51.,52.],FG=[47.,46.],pair_source_id=['a','b']))
        records=[]
        for i in range(11):
            u=0 if i<10 else 1
            records.append(dict(action_id=f'a{i}',family_id='x',u_date=macro.u_date[u],u_index=u,u_action_eligible=1,label_state='closed_complete_bar_model',label_known_date='2019-03-01',sample_weight=1.,Ahat=1.,net_R_stress=3. if u==0 else -1.))
        monthly=m.aggregate_reports(pd.DataFrame(records),macro,'2020-01-01')
        self.assertEqual(monthly.row_count.tolist(),[10,1])
        self.assertEqual(monthly.residual_R.tolist(),[2.,-2.])
        self.assertEqual(float(monthly.residual_R.mean()),0.)
        self.assertNotEqual(float((pd.DataFrame(records).net_R_stress-1).mean()),0.)

    def test_center_shared_intercept_and_ridge_mean_loss(self):
        t=np.arange(40,dtype=float)
        frame=pd.DataFrame(dict(report_month=[f'{2000+i//12}-{i%12+1:02d}' for i in range(40)],NO=50+np.sin(t),FG=47+np.cos(t/3),residual_R=.4+.2*np.sin(t)-.1*np.cos(t/3)))
        b=m.fit_head(frame,'B');c=m.fit_head(frame,'C')
        self.assertEqual(b['a'],c['a'])
        z=(frame[['NO','FG']].to_numpy()-np.array(c['feature_mean']))/np.array(c['feature_scale'])
        expected=np.linalg.solve(z.T@z/40+np.eye(2),z.T@(frame.residual_R.to_numpy()-c['a'])/40)
        np.testing.assert_allclose(c['beta'],expected,rtol=0,atol=1e-15)
        self.assertLessEqual(c['effective_slope_df'],1+1e-12)
        self.assertAlmostEqual(float((c['a']+z@np.array(c['beta'])).mean()),b['a'],places=13)

    def test_missing_is_bitwise_original_even_negative_zero(self):
        macro=pd.DataFrame(dict(macro_available=[0,1,0],NO=[np.nan,51.,np.nan],FG=[np.nan,47.,np.nan]))
        head=dict(arm='C',a=.25,feature_mean=[50.,46.],feature_scale=[1.,1.],beta=[.1,-.05])
        delta=m.predict_delta(macro,head);base=np.array([-0.,-.2,3.])
        output=m.apply_delta(base,delta,[False,True,False])
        np.testing.assert_array_equal(delta[[0,2]],[0.,0.])
        np.testing.assert_array_equal(output[[0,2]].view(np.uint64),base[[0,2]].view(np.uint64))
        self.assertAlmostEqual(output[1],.1)

    def test_whitelist_and_calendar_month_gate(self):
        frame=pd.DataFrame([{c:'x' for c in m.FORWARD}]);frame['score']=-.25
        frame['B_offset']=999.;frame['C_offset']=-999.;frame['extra_future_column']=123
        result=m.clean_forward(frame)
        self.assertEqual(result.columns.tolist(),m.FORWARD)
        self.assertEqual(result.score.iloc[0],-.25)
        days=['2020-01-02','2020-02-03','2020-02-04','2023-01-03'];records=[]
        for scope in ['main','holdout_0','holdout_1']:
            for contrast in ['C_minus_A','C_minus_B','B_minus_A']:
                for day,v in zip(days,[-3.,2.,2.,1.]):
                    records.append(dict(scope=scope,contrast=contrast,u_date=day,delta_R=v if scope=='main' else 1.,known_family_u=1,unknown_family_u=0))
        macro=pd.DataFrame(dict(u_date=days,report_month=[d[:7] for d in days],macro_available=1))
        report,_,monthly,_,_=m.monthly_diagnostics({},pd.DataFrame(records),macro)
        self.assertFalse(report['nominal_cash_prerequisite'])
        self.assertEqual(report['main_era_means'][0]['equal_calendar_month_mean_increment_R'],-.5)
        self.assertEqual(len(monthly),27)

if __name__=='__main__':unittest.main()
