"""Small new-behavior fixtures only; never open actual inputs or SQL."""
import importlib.util
import inspect
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
import pandas as pd

PATH = Path(__file__).with_name('stage086_oi_fit.py')


def module():
    if not PATH.exists():
        return None
    spec = importlib.util.spec_from_file_location('test086_target', PATH)
    value = importlib.util.module_from_spec(spec);spec.loader.exec_module(value)
    return value


def fixture():
    rows=[]
    for i,(day,fam,known,state) in enumerate([
        ('2018-01-01','A.X','2018-01-02','closed_complete_bar_model'),
        ('2018-01-01','B.X','2018-01-03','closed_complete_bar_model'),
        ('2019-01-01','A.X','2020-01-01','closed_complete_bar_model'),
        ('2020-01-02','A.X','','open_right_censored'),
        ('2020-01-02','B.X','','path_or_execution_unknown')]):
        rows.append(dict(sequence_index=i,event_id='e'+str(i),product_id=fam,family_id=fam,u_date=day,
            u_index=10+i,reference_epoch=fam+'2001',entry_index=11+i,exit_index=12+i,
            entry_date=day,exit_date=known,label_known_date=known,label_state=state,
            participation_state='filled',net_R_stress=[1.,-2.,3.,np.nan,np.nan][i],label_history_ready20=1))
    f=pd.DataFrame(rows)
    projection=f[['sequence_index','event_id','product_id','family_id','u_date','u_index','reference_epoch']].copy()
    projection['oi_scalar_raw']=[0.,2.,999.,1e9,np.nan]
    projection['oi_observed']=[1,1,1,1,0];projection['oi_missing']=1-projection.oi_observed
    projection['projection_state']=np.where(projection.oi_observed.eq(1),'observed_same_epoch_same_source_canonical','missing')
    projection['missing_reason']=np.where(projection.oi_observed.eq(1),'','missing_source')
    return f,np.arange(len(f)*26,dtype=float).reshape(len(f),26),projection


class NewFitBehavior(unittest.TestCase):
    def setUp(self):
        self.m=module();self.assertIsNotNone(self.m,'Stage086 implementation is missing')

    def test_shared_mask_zero_and_no_future_scaler_leak(self):
        f,x,p=fixture();x[1,0]=np.nan
        prepared=self.m.prepare_fold(f,x,p,'2020-01-01','2023-01-01','main')
        self.assertEqual(prepared['scaler']['scalar']['mean'],1.)
        self.assertEqual(prepared['scaler']['scalar']['scale'],1.)
        self.assertEqual(len(prepared['train']),2)
        control=self.m.design(prepared['prediction_base'],prepared['prediction_scalar'],'CONTROL')
        oi=self.m.design(prepared['prediction_base'],prepared['prediction_scalar'],'OI')
        np.testing.assert_array_equal(control[:,:53],oi[:,:53])
        self.assertEqual(control.shape,(2,54));self.assertTrue((control[:,-1]==0).all())
        self.assertEqual(oi[1,-1],0.);self.assertEqual(oi[1,52],1.)
        self.assertGreater(oi[0,-1],1e8)

    def test_held_excludes_training_family_and_retains_unknown_prediction(self):
        f,_,_=fixture();g=self.m.family_group('A.X')
        train,pred=self.m.fold_slices(f,'2020-01-01','2023-01-01','holdout_'+str(g))
        self.assertTrue(all(self.m.family_group(v)!=g for v in train.family_id))
        self.assertTrue(all(self.m.family_group(v)==g for v in pred.family_id))
        self.assertIn('e3',pred.event_id.tolist())
        self.assertTrue(pred.net_R_stress.isna().all())

    def test_projection_identity_mask_mismatch_rejected(self):
        f,_,p=fixture();self.m.validate_projection(f,p)
        bad=p.copy();bad.loc[0,'oi_missing']=1
        with self.assertRaisesRegex(ValueError,'mask'):
            self.m.validate_projection(f,bad)
        bad=p.copy();bad.loc[0,'event_id']='wrong'
        with self.assertRaisesRegex(ValueError,'identity'):
            self.m.validate_projection(f,bad)

    def test_completed_source_terminal_requires_zero_fit_and_cash(self):
        self.assertTrue(hasattr(self.m,'validate_source_manifest'),'source manifest validator missing')
        projection=dict(path='/projection',bytes=1,sha256='p');terminal_binding=dict(path='/terminal',bytes=2,sha256='t')
        clarifications=dict(path='/clarifications',bytes=3,sha256=self.m.CLARIFICATIONS_SHA)
        inputs=dict(oi_projection=projection,oi_terminal=terminal_binding,clarifications=clarifications)
        source=dict(schema='stage085_oi_projection_v1',status='completed',mode='actual',protocol=dict(sha256=self.m.PROTOCOL_SHA),
            mother_rows=399252,native_source_queries=1,actual_model_fit_calls=0,new_cash_accounts=0,new_labels=0,
            projection=projection,terminal=terminal_binding,implementation_clarifications=clarifications)
        terminal=dict(status='completed',exit_code=0,completed_projection_rows=399252,native_source_queries=1,
            actual_model_fit_calls=0,new_cash_accounts=0,new_labels=0)
        self.m.validate_source_manifest(source,terminal,inputs)
        for key in ('actual_model_fit_calls','new_cash_accounts','new_labels'):
            bad=dict(terminal);bad[key]=1
            with self.assertRaisesRegex(ValueError,'terminal'):
                self.m.validate_source_manifest(source,bad,inputs)

    def test_two_fixture_fits_write_portable_full_forward_scores(self):
        f,x,p=fixture();calls=[];completed=[]
        self.assertIn('on_completed',inspect.signature(self.m.fit_cell).parameters)
        with tempfile.TemporaryDirectory() as tmp:
            pred,records=self.m.fit_cell(f,x,p,'2020-01-01','2023-01-01','main',Path(tmp)/'cell',on_fit=lambda *v:calls.append(v),on_completed=lambda *v:completed.append(v))
            self.assertEqual(len(calls),2);self.assertEqual(len(records),2)
            self.assertEqual(len(completed),2)
            self.assertEqual(len(pred),4);self.assertEqual(set(pred.arm),{'CONTROL','OI'})
            self.assertEqual(set(pred.event_id),{'e3','e4'})
            self.assertTrue(pred.score.map(np.isfinite).all())
            self.assertTrue(pred.selected.eq((pred.history_ready20.eq(1)&pred.score.gt(0)).astype(int)).all())
            self.assertEqual(records[0]['training_identity_sha256'],records[1]['training_identity_sha256'])
            saved=json.loads((Path(tmp)/'cell'/'CONTROL'/'portable_model.json').read_text())
            self.assertEqual(saved['feature_names'][-2:],['oi_missing','oi_scalar'])

    def test_held_diagnostic_closed_only_unknown_not_zero(self):
        f,_,_=fixture();a=f.loc[[0,3],['event_id','family_id','u_date','u_index']].copy()
        parts=[]
        for arm,scores in [('CONTROL',[-1.,-1.]),('OI',[1.,1.])]:
            q=a.copy();q['arm']=arm;q['scope']='holdout_0';q['cutoff']='2020-01-01';q['score']=scores;q['history_ready20']=1;q['oi_missing']=0
            parts.append(q)
        report,daily,linked=self.m.held_diagnostics(pd.concat(parts),f)
        self.assertEqual(report['groups']['holdout_0']['known_u_equal_mean_increment_R'],1.)
        self.assertIn('prediction_u_equal_MSE_difference',report['groups']['holdout_0'])
        self.assertEqual(report['groups']['holdout_0']['prediction_u_equal_MSE_difference'],-4.)
        self.assertEqual(report['groups']['holdout_0']['unknown_differential_selected_events'],1)
        self.assertEqual(report['groups']['holdout_0']['status'],'unknown')
        self.assertTrue(linked.loc[linked.event_id.eq('e3'),'diagnostic_outcome_R'].isna().all())
        self.assertEqual(len(daily),1)


if __name__=='__main__':unittest.main()
