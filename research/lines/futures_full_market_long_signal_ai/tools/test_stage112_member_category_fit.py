"""New shared-scalar statistics/held isolation and six-cell support only."""
import importlib.util
from pathlib import Path
import unittest
import numpy as np
import pandas as pd

SOURCE=Path(__file__).with_name('stage112_member_category_fit.py')
def load():
    if not SOURCE.exists():return None
    s=importlib.util.spec_from_file_location('test112',SOURCE);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def fixture(m):
    names={g:[s for s in ['A.X','B.X','C.X','D.X','E.X','F.X','G.X','H.X'] if m.family_group(s)==g][:2] for g in (0,1)}
    rows=[];values=[]
    for group in (0,1):
        for j,fam in enumerate(names[group]):
            i=len(rows);rows.append(dict(sequence_index=i,event_id='e'+str(i),product_id=fam,family_id=fam,u_date='2018-01-01',u_index=10+i,
                reference_epoch='same',entry_index=11+i,exit_index=12+i,entry_date='2018-01-02',exit_date='2018-01-03',
                label_known_date='2018-01-03',label_state='closed_complete_bar_model',net_R_stress=float(i),label_history_ready20=1,participation_state='filled'))
            values.append([-.4,-.3][j] if group==0 else [.1,.3][j])
    for group in (0,1):
        for year in ('2020','2023'):
            i=len(rows);fam=names[group][0];rows.append(dict(rows[group*2],sequence_index=i,event_id='e'+str(i),u_date=year+'-01-02',u_index=10+i,label_known_date='',label_state='open_right_censored',net_R_stress=np.nan));values.append(np.nan)
    f=pd.DataFrame(rows);x=np.arange(len(f)*26,dtype=float).reshape(len(f),26)
    p=f[m.IDENTITY].copy();p['external_scalar_raw']=values;p['external_observed']=np.isfinite(values).astype(int);p['external_missing']=1-p.external_observed
    p['projection_state']=np.where(p.external_observed.eq(1),'observed_archive_member_categories_lag1','missing');p['missing_reason']=np.where(p.external_observed.eq(1),'','source_date_unavailable')
    return f,x,p

class CategoryFitWiring(unittest.TestCase):
    def setUp(self):self.m=load();self.assertIsNotNone(self.m,'Stage112 source missing')
    def test_train_only_scaler_held_exclusion_full_missing_predictions_shared54(self):
        f,x,p=fixture(self.m);q=self.m.prepare_fold(f,x,p,'2020-01-01','2023-01-01','holdout_0')
        self.assertAlmostEqual(q['scaler']['scalar']['mean'],.2)
        self.assertTrue(q['train'].family_id.map(self.m.family_group).eq(1).all())
        self.assertTrue(q['prediction'].family_id.map(self.m.family_group).eq(0).all());self.assertEqual(len(q['prediction']),1)
        self.assertEqual(q['prediction_external_missing'].tolist(),[1]);self.assertEqual(q['prediction_scalar'].tolist(),[0.])
        c=self.m.design(q['train_base'],q['train_scalar'],'CONTROL');n=self.m.design(q['train_base'],q['train_scalar'],'NFC')
        self.assertEqual(c.shape,(2,54));np.testing.assert_array_equal(c[:,:53],n[:,:53]);np.testing.assert_array_equal(c[:,-1],0.)
    def test_any_constant_cell_stops_whole_six_cell_package_before_fit(self):
        f,x,p=fixture(self.m);p.loc[f.family_id.map(self.m.family_group).eq(1)&p.external_observed.eq(1),'external_scalar_raw']=.2
        report=self.m.support_preflight(f,x,p)
        self.assertEqual(report['status'],'unsupported_scalar_support');self.assertFalse(report['cash_eligible']);self.assertEqual(len(report['cells']),6)
        self.assertTrue(any(c['scope']=='holdout_0' and not c['positive_weighted_variation'] for c in report['cells']))

if __name__=='__main__':unittest.main()
