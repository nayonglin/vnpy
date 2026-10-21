"""New target-domain and shared52 wiring only. No actual research inputs."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
import pandas as pd

PATH=Path(__file__).with_name('stage100_log_utility_fit.py')


def module():
    if not PATH.exists():return None
    s=importlib.util.spec_from_file_location('test100_target',PATH);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m


def fixture():
    rows=[]
    for i,(day,known,state,y) in enumerate([
        ('2018-01-01','2018-01-02','closed_complete_bar_model',2.),
        ('2018-01-01','2018-01-03','closed_complete_bar_model',-1.),
        ('2020-01-01','2020-01-03','closed_complete_bar_model',-1000.),
        ('2020-01-02','','open_right_censored',np.nan)]):
        fam='A.X' if i%2==0 else 'B.X'
        rows.append(dict(sequence_index=i,event_id='e'+str(i),product_id=fam,family_id=fam,u_date=day,u_index=10+i,
            reference_epoch=fam+'2001',entry_index=11+i,exit_index=12+i,entry_date=day,exit_date=known,
            label_known_date=known,label_state=state,participation_state='filled',net_R_stress=y,label_history_ready20=1))
    f=pd.DataFrame(rows);x=np.arange(4*26,dtype=float).reshape(4,26)
    x[:,24]=[0.,.2,0.,np.nan];x[3,0]=np.nan
    return f,x


class LogUtilityBehavior(unittest.TestCase):
    def setUp(self):
        self.m=module();self.assertIsNotNone(self.m,'Stage100 implementation missing')

    def test_same_unit_linear_control_and_log1p_formula(self):
        y=np.array([-2.,0.,3.]);c=np.array([0.,.1,1.]);d=self.m.target_domain(y,c)
        a=1/(1+8*c);z=a*y
        np.testing.assert_array_equal(d.a,a);np.testing.assert_array_equal(d.L_target,z)
        np.testing.assert_allclose(d.G_target,np.log1p(.0025*z)/.0025,rtol=1e-15,atol=0)
        self.assertTrue(d.domain_state.eq('valid').all())

    def test_invalid_cost_a_or_y_keeps_rows_and_fails_whole_domain(self):
        for y,c in [([1.],[np.nan]),([1.],[-.1]),([1.],[np.inf]),([1.],[1e308]),([np.nan],[0.]),([np.inf],[0.])]:
            d=self.m.target_domain(np.array(y),np.array(c))
            self.assertEqual(len(d),1);self.assertFalse(d.domain_state.eq('valid').all())
            self.assertTrue(d.G_target.isna().all())

    def test_reference_ruin_boundary_has_no_epsilon_or_clipping(self):
        d=self.m.target_domain(np.array([-400.,-401.]),np.zeros(2))
        np.testing.assert_array_equal(d.L_target,[-400.,-401.])
        self.assertFalse(d.domain_state.eq('valid').any());self.assertTrue(d.G_target.isna().all())
        self.assertEqual(d.reference_wealth.iloc[0],0.)

    def test_small_valid_payoff_uses_log1p_without_rounding_to_zero(self):
        d=self.m.target_domain(np.array([1e-15]),np.zeros(1))
        self.assertEqual(d.domain_state.iloc[0],'valid');self.assertGreater(d.G_target.iloc[0],0.)
        self.assertAlmostEqual(d.G_target.iloc[0]/1e-15,1.,places=14)

    def test_shared52_train_only_design_does_not_precheck_future_targets(self):
        f,x=fixture();x[2,24]=-.1
        p=self.m.prepare_fold(f,x,'2020-01-01','2023-01-01')
        self.assertEqual(p['domain_report']['status'],'valid')
        self.assertEqual(p['train_head'].shape,(2,52));self.assertEqual(p['prediction_head'].shape,(2,52))
        self.assertEqual(len(p['prediction']),2)
        self.assertEqual(p['prediction_head'][1,26],1.)
        self.assertAlmostEqual(p['scaler']['common']['mean'][24],.1)

    def test_mature_training_domain_failure_makes_zero_fixture_fit(self):
        f,x=fixture();f.loc[0,'net_R_stress']=-401.;calls=[]
        with tempfile.TemporaryDirectory() as tmp:
            pred,records,domain=self.m.fit_cell(f,x,'2020-01-01','2023-01-01',Path(tmp)/'cell',on_fit=lambda *v:calls.append(v))
            self.assertIsNone(pred);self.assertEqual(records,[]);self.assertEqual(calls,[])
            self.assertEqual(domain['status'],'domain_failure')
            saved=pd.read_csv(Path(tmp)/'cell'/'training_identity_weights_targets.csv.gz')
            self.assertEqual(len(saved),2);self.assertEqual(set(saved.event_id),{'e0','e1'})
            self.assertFalse((Path(tmp)/'cell'/'L').exists())

    def test_two_fixture_fits_preserve_full_scores_then_oos_domain_fails(self):
        f,x=fixture();attempt=[];complete=[]
        with tempfile.TemporaryDirectory() as tmp:
            p,records,domain=self.m.fit_cell(f,x,'2020-01-01','2023-01-01',Path(tmp)/'cell',
                on_fit=lambda *v:attempt.append(v),on_completed=lambda *v:complete.append(v))
            self.assertEqual(len(attempt),2);self.assertEqual(len(complete),2)
            self.assertEqual(len(p),4);self.assertEqual(set(p.event_id),{'e2','e3'});self.assertEqual(set(p.arm),{'L','G'})
            self.assertEqual(records[0]['training_identity_sha256'],records[1]['training_identity_sha256'])
            portable=json.loads((Path(tmp)/'cell'/'G'/'portable_model.json').read_text())
            self.assertEqual(len(portable['coef']),52);self.assertEqual(len(portable['feature_names']),52)
            report,projection=self.m.oos_domain(f,x)
            self.assertEqual(report['status'],'domain_failure');self.assertEqual(report['invalid_rows'],1)
            self.assertEqual(len(projection),4);self.assertTrue(projection.loc[projection.event_id.eq('e3'),'G_target'].isna().all())
            self.assertFalse(any('head_cache' in q.name for q in Path(tmp).rglob('*')))


if __name__=='__main__':unittest.main()
