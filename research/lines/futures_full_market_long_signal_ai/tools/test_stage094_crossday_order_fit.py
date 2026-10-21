"""Only new 181/RFF/scaler wiring fixtures; actual research fit is forbidden."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
import pandas as pd

PATH=Path(__file__).with_name('stage094_crossday_order_fit.py')


def module():
    if not PATH.exists():return None
    s=importlib.util.spec_from_file_location('test094_target',PATH);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m


def fixture():
    f=pd.DataFrame([dict(sequence_index=i,event_id='e'+str(i),product_id=fam,family_id=fam,u_date=day,
        u_index=10+i,reference_epoch=fam+'2001',entry_index=11+i,exit_index=12+i,entry_date=day,
        exit_date=known,label_known_date=known,label_state=state,participation_state='filled',net_R_stress=y,label_history_ready20=1)
        for i,(fam,day,known,state,y) in enumerate([
            ('A.X','2018-01-01','2018-01-03','closed_complete_bar_model',1.),
            ('B.X','2018-01-01','2018-01-04','closed_complete_bar_model',-2.),
            ('A.X','2020-01-01','','open_right_censored',np.nan),
            ('B.X','2020-01-02','','path_or_execution_unknown',np.nan)])])
    x=np.arange(4*26,dtype=float).reshape(4,26);x[[1,3],:11]=np.nan
    alignment=f[['sequence_index','event_id','product_id','family_id','u_date','u_index','reference_epoch']].copy()
    alignment['legacy_tensor_index']=[0,-1,1,-1];alignment['sequence_missing']=[0,1,0,1]
    tensor=np.zeros((2,20,4),dtype='<f4')
    tensor[0]=np.arange(80,dtype=float).reshape(20,4)[::-1]+10
    tensor[1]=1e8
    return f,x,alignment,tensor


class BridgeBehavior(unittest.TestCase):
    def setUp(self):
        self.m=module();self.assertIsNotNone(self.m,'Stage094 implementation missing')

    def test_fold_scaler_observed_training_only_and_no_future_tensor_leak(self):
        f,x,a,t=fixture();p=self.m.prepare_fold(f,x,a,t,'2020-01-01','2023-01-01','main')
        expected=t[0].astype(float).mean(axis=0)
        np.testing.assert_allclose(p['scaler']['sequence']['mean'],expected,rtol=1e-14,atol=1e-14)
        self.assertEqual(p['scaler']['sequence']['observed_events'],1)
        self.assertEqual(p['scaler']['sequence']['finite_count'],[20]*4)
        self.assertEqual(len(p['train']),2)
        np.testing.assert_array_equal(p['scaler']['common']['mean'][:11],x[0,:11])

    def test_181_shared_background_and_missing_standardized_sequence_zero(self):
        f,x,a,t=fixture();p=self.m.prepare_fold(f,x,a,t,'2020-01-01','2023-01-01','main');mapping=self.m.make_mapping()
        order=self.m.head(p['prediction_base'],p['prediction_tensor_index'],t,'ORDER',p['scaler'],mapping)
        bag=self.m.head(p['prediction_base'],p['prediction_tensor_index'],t,'BAG',p['scaler'],mapping)
        self.assertEqual(order.shape,(2,181));np.testing.assert_array_equal(order[:,:53],bag[:,:53])
        np.testing.assert_array_equal(order[1],bag[1])
        z=np.r_[p['prediction_base'][1,:11],np.zeros(80)]
        expected=np.sqrt(2/128)*np.cos(z@(mapping['W_base']/np.sqrt(91))+mapping['b'])
        np.testing.assert_allclose(order[1,53:],expected,rtol=1e-14,atol=1e-14)
        self.assertEqual(order[1,52],1.)

    def test_all_missing_or_constant_channel_scaler_keeps_mean_and_unit_scale(self):
        _,x,a,t=fixture();w=np.array([1.,1.]);none=np.array([-1,-1])
        s=self.m.fit_scalers(x[:2],none,t,w)
        self.assertEqual(s['sequence']['mean'],[0.]*4);self.assertEqual(s['sequence']['scale'],[1.]*4)
        t=t.copy();t[0]=7.;s=self.m.fit_scalers(x[:2],np.array([0,-1]),t,w)
        self.assertEqual(s['sequence']['mean'],[7.]*4);self.assertEqual(s['sequence']['scale'],[1.]*4)

    def test_two_fixture_fits_portable_181_and_no_big_head_cache(self):
        f,x,a,t=fixture();attempted=[];completed=[]
        with tempfile.TemporaryDirectory() as tmp:
            pred,records=self.m.fit_cell(f,x,a,t,'2020-01-01','2023-01-01','main',Path(tmp)/'cell',self.m.make_mapping(),
                on_fit=lambda *v:attempted.append(v),on_completed=lambda *v:completed.append(v))
            self.assertEqual(len(attempted),2);self.assertEqual(len(completed),2)
            self.assertEqual(set(pred.arm),{'ORDER','BAG'});self.assertEqual(set(pred.event_id),{'e2','e3'})
            self.assertEqual(len(pred),4);self.assertEqual(records[0]['dimension'],181)
            self.assertEqual(records[0]['training_identity_sha256'],records[1]['training_identity_sha256'])
            portable=json.loads((Path(tmp)/'cell'/'ORDER'/'portable_model.json').read_text())
            self.assertEqual(len(portable['coef']),181);self.assertEqual(portable['feature_names'][52],'sequence_missing')
            self.assertFalse(any('normalized_inputs' in p.name or 'head_cache' in p.name for p in Path(tmp).rglob('*')))


if __name__=='__main__':unittest.main()
