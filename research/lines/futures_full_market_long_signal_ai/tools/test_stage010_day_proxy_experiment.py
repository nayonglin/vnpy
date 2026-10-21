"""Four focused contracts; tiny sklearn fits are fixtures, not the real experiment."""
import hashlib
import importlib.util
from pathlib import Path
import unittest
import numpy as np
import pandas as pd

PATH = Path(__file__).with_name('stage010_day_proxy_experiment.py')
if PATH.exists():
    spec = importlib.util.spec_from_file_location('stage010', PATH)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
else:
    m = None

OWN = ['r1_atr','r5_atr','r20_atr','body_atr','range_atr','close_location','gap_atr',
       'compression5_20','log_volume_ratio20','breakout20_atr','atr_pct']
MARKET = ['market_lag_median_r1','market_lag_breadth','market_lag_iqr_r1','market_lag_missing']

def row(i, day, family='SHFE.CU', x=0., y=0., known=None):
    r = dict(event_id='event'+str(i), product_id=family, family_id=family, exchange=family.split('.')[0],
             u_date=day, reference_epoch=family+'.202612', planned_execution_date=known or day,
             feature_ready=1, history_state='ready', status='observed', label_identified=1,
             label_state='identified', label_known_date=known or day,path_ambiguous=0,
             gross_lower=y+.2,gross_upper=y+.2,proxy_lower=y,proxy_upper=y,atr20=1.)
    r.update({k:0. for k in OWN+MARKET}); r['r1_atr']=x
    return r

def predictions():
    data = pd.DataFrame([row(1,'2020-01-02'),row(2,'2020-01-02','DCE.L')])
    data['proxy_lower']=-1.2;data['proxy_upper']=3.8;data['path_ambiguous']=1
    data['pred_M1']=[.1,-.1];data['pred_M0']=[.1,.1]
    data['intercept_score']=0.;data['momentum_mask']=False
    return data

class ExperimentContracts(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(m, 'fixed experiment implementation has not been written')

    def test_maturity_family_holdout_and_scaler_ignore_future(self):
        # Break caught: inclusive maturity cutoff, held-family leakage, or scaler fitted on test rows.
        families=['SHFE.CU','DCE.L','CZCE.CF','CFFEX.IF','GFEX.LC']
        groups={f:int(hashlib.sha256(f.encode()).hexdigest(),16)%2 for f in families}
        held=groups['DCE.L'];other=next(f for f in families if groups[f]!=held)
        data=pd.DataFrame([row(1,'2014-12-25',other,0,1,'2014-12-26'),
                           row(2,'2014-12-26',other,2,3,'2014-12-29'),
                           row(3,'2014-12-30',other,900,900,'2015-01-05'),
                           row(4,'2014-12-29','DCE.L',800,800,'2014-12-30'),
                           row(5,'2014-12-29','DCE.L_F',700,700,'2014-12-30'),
                           row(6,'2015-01-05',other,1000,1000,'2015-01-06')])
        data.loc[data.product_id=='DCE.L_F','family_id']='DCE.L'
        train=m.training_slice(data,'2015-01-05',held)
        self.assertEqual(train.event_id.tolist(),['event1','event2'])
        a=m.fit_one(train,OWN,'fixture_a','2015-01-05',held)
        data.loc[data.event_id=='event6','r1_atr']=-1e12
        b=m.fit_one(m.training_slice(data,'2015-01-05',held),OWN,'fixture_b','2015-01-05',held)
        self.assertEqual(a['scaler']['mean'][0],1.)
        self.assertEqual(a['scaler'],b['scaler']);self.assertEqual(a['coef'],b['coef'])
        self.assertEqual(a['training_ids_sha256'],b['training_ids_sha256'])
        self.assertTrue(a['max_label_known_date']<'2015-01-05')

    def test_real_sklearn_weighted_fit_and_pure_coefficient_replay(self):
        # Break caught: row-equal weighting instead of date-equal weighting; replay requiring refit.
        data=pd.DataFrame([row(1,'2014-01-02',x=0,y=1),row(2,'2014-01-02','DCE.L',x=2,y=5),
                           row(3,'2014-01-03',x=4,y=9)])
        fit=m.fit_one(data,OWN,'fixture_fit','2015-01-05',None)
        np.testing.assert_allclose(fit['scaler']['mean'][0],2.5)
        np.testing.assert_allclose(fit['scaler']['var'][0],2.75)
        # Weighted standardized ridge: total weight=3, covariance=2*sqrt(2.75)*3; alpha=1.
        np.testing.assert_allclose(fit['coef'][0],1.5*np.sqrt(2.75),rtol=1e-12)
        np.testing.assert_allclose(fit['intercept'],6.,rtol=1e-12)
        out=m.predict_from_record(fit,data)
        np.testing.assert_allclose(out,[2.25,5.25,8.25],rtol=1e-12)
        self.assertEqual(fit['estimator'],'sklearn.linear_model.Ridge')
        self.assertEqual(fit['weights_by_date'],{'2014-01-02':.75,'2014-01-03':1.5})

    def test_paired_intervals_cancel_common_masks_and_keep_unknown_dates(self):
        # Break caught: subtracting lower endpoints or removing empty evaluation dates from bootstrap grid.
        data=predictions();daily=m.daily_metrics(data,['2020-01-02','2020-01-03'])
        self.assertAlmostEqual(daily.iloc[0].paired_lower,-1.9)
        self.assertAlmostEqual(daily.iloc[0].paired_upper,.6)
        data['pred_M1']=.1
        same=m.daily_metrics(data,['2020-01-02','2020-01-03'])
        self.assertEqual(same.iloc[0].paired_lower,0.);self.assertEqual(same.iloc[0].paired_upper,0.)
        self.assertTrue(np.isnan(same.iloc[1].paired_lower))
        unknown=row(3,'2020-01-03');unknown.update(label_identified=0,label_known_date='',
            label_state='missing_D',proxy_lower=np.nan,proxy_upper=np.nan,pred_M0=.1,pred_M1=.1,
            intercept_score=0.,momentum_mask=False)
        both=pd.concat([data,pd.DataFrame([unknown])],ignore_index=True)
        report=m.cohort_counts(both)
        self.assertEqual(report['feature_ready_predictions'],3)
        self.assertEqual(report['identified_rows'],2)
        self.assertEqual(report['unknown_M1_selection_rate'],1.)

    def test_participation_bound_same_mask_cost_and_shared_bootstrap(self):
        # Break caught: naive lower subtraction, selecting again under stress, or unpaired resamples.
        d=m.daily_metrics(predictions(),['2020-01-02'])
        self.assertAlmostEqual(d.iloc[0].participation_lower,-1.25)
        self.assertAlmostEqual(d.iloc[0].participation_upper,1.25)
        self.assertAlmostEqual(d.iloc[0].M1_lower,-.6)
        self.assertAlmostEqual(d.iloc[0].stress_M1_lower,-1.)
        self.assertEqual(d.iloc[0].M1_selection_rate,.5)
        v=np.arange(120,dtype=float);v[3]=np.nan
        result=m.bootstrap_intervals(pd.DataFrame({'a':v,'b':v}),['a','b'])
        self.assertEqual(result['metrics']['a'],result['metrics']['b'])
        self.assertEqual(result['repetitions'],2000)
        self.assertEqual(result['block_length'],60)

if __name__=='__main__': unittest.main()
