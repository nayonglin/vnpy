"""Synthetic-only checks for frozen Stage071 behavior; never opens accepted data."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

MODULE = Path(__file__).with_name('stage071_settlement_narrow_fit.py')
if MODULE.exists():
    spec = importlib.util.spec_from_file_location('stage071', MODULE)
    fit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fit)
else:
    fit = None


class Stage071Behavior(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(fit, 'Stage071 implementation is missing')

    def test_own_policy_strict_maturity_and_complete_forward_universe(self):
        # Break caught: using wide maturity/Y, <= cutoff, or label-filtering scores.
        f = pd.DataFrame(dict(sequence_index=range(6), event_id=list('abcdef'),
            product_id=['DCE.A']*6, family_id=['DCE.A']*6,
            reference_epoch=['DCE.A.202001']*6,
            u_date=['2019-01-01','2019-02-01','2019-03-01','2020-01-01','2022-12-30','2023-01-02'],
            u_index=range(6), entry_index=range(1,7), exit_index=range(2,8),
            entry_date=['2019-01-02']*6,exit_date=['2019-01-03']*6,
            label_known_date=['2019-01-03','2020-01-01','','','',''],
            label_state=['closed_complete_bar_model']*2+['unknown']*4,
            net_R_stress=[3.,9.,np.nan,np.nan,np.nan,np.nan],label_history_ready20=[1,1,0,1,0,1]))
        train = fit.training_slice(f, '2020-01-01')
        self.assertEqual(train.event_id.tolist(), ['a'])
        narrow = f.copy(); narrow.loc[0,'net_R_stress'] = -.75
        self.assertEqual(fit.training_slice(narrow,'2020-01-01').net_R_stress.tolist(),[-.75])
        self.assertEqual(fit.prediction_slice(f,'2020-01-01','2023-01-01').event_id.tolist(),['d','e'])
        pred = fit.prediction_frame(fit.prediction_slice(f,'2020-01-01'),[1.,2.,-1.],'NARROW','COMMON','2020-01-01')
        self.assertEqual(pred.event_id.tolist(),['d','e','f'])
        self.assertEqual(pred.selected.tolist(),[1,0,0])

    def test_weights_use_own_mature_family_inclusive_intervals_then_u_equalize(self):
        # A's [1,2]/[2,3] overlap on boundary; B does not affect A concurrency.
        f = pd.DataFrame(dict(family_id=['A','A','B','A'],entry_index=[1,2,2,8],exit_index=[2,3,2,8],u_date=['u1','u1','u1','u2']))
        w = fit.training_weights(f)
        np.testing.assert_allclose(w.uniqueness,[.75,.75,1.,1.])
        np.testing.assert_allclose(w.u_normalized_weight,[.3,.3,.4,1.])
        np.testing.assert_allclose(w.sample_weight,[.6,.6,.8,2.])
        self.assertEqual(w.groupby(f.u_date).sample_weight.sum().tolist(),[2.,2.])
        f['entry_index']=f.entry_index.astype(float);f.loc[0,'entry_index']=1.5
        with self.assertRaisesRegex(ValueError,'interval'):
            fit.training_weights(f)

    def test_shared_scaler_54_slots_common_zero_and_missing_zero_after_scaling(self):
        x=np.tile(np.arange(26,dtype=float),(3,1));x[:,0]=[0,2,np.nan]
        q=np.array([0.,2.,np.nan]);proxy=np.array([2.,4.,np.nan]);w=np.array([1.,3.,1.])
        scaler=fit.fit_scalers(x,q,proxy,w)
        self.assertAlmostEqual(scaler['common']['mean'][0],1.5)
        self.assertAlmostEqual(scaler['scalar']['mean'],2.5)
        self.assertAlmostEqual(scaler['scalar']['var'],1.75)
        base=fit.design_base(x,np.array([True,True,False]),scaler)
        common=fit.design_matrix(base,q,'COMMON',scaler)
        settled=fit.design_matrix(base,q,'SETTLEMENT',scaler)
        proxied=fit.design_matrix(base,proxy,'OHLC_PROXY',scaler)
        self.assertEqual(common.shape,(3,54));np.testing.assert_array_equal(common[:,-1],0)
        np.testing.assert_array_equal(common[:,:53],settled[:,:53])
        np.testing.assert_array_equal(proxied[:,:53],settled[:,:53])
        self.assertEqual(settled[2,-1],0);self.assertEqual(proxied[2,-1],0)
        np.testing.assert_array_equal(common[:,-2],[0,0,1])
        self.assertLess(settled[0,-1],0) # true raw zero is observed, not missing
        with self.assertRaisesRegex(ValueError,'shared'):
            fit.fit_scalers(x,q,np.array([2.,np.nan,3.]),w)

    def test_observation_mask_accepts_default_rule_true_zero_and_rejects_conflicts(self):
        n=9
        mother=pd.DataFrame(dict(sequence_index=range(n),event_id=[str(i) for i in range(n)],product_id=['DCE.A']*n,
            family_id=['DCE.A']*n,u_date=['2020-02-04']*n,u_index=[22]*n,reference_epoch=['DCE.A.202005']*n))
        src=mother.copy();src['v_index']=21;src['v_date']='2020-02-03'
        for k,v in dict(projection_state='observed_historical_reconstruction',value_observed=1,N_state='N_v_ready20',
            ohlc_relation='equal_with_fixed_absolute_tolerance_1e-8',lifecycle_state='before_vendor_final_boundary',
            benchmark_family='dce_commodity_daily_default',rule_state='family_default_assumption_no_primary_rule_bound',
            rule_primary_bound=0,training_accepted=0,feature_available=0,strict_pit_accepted=0,
            candidate_quote_epoch='DCE.A.202005',candidate_quote_date='2020-02-03',accepted_C_v=100.,C_v=100.,S_v=100.,N_v=2.).items():src[k]=v
        proxy=mother.copy();proxy['v_index']=21;proxy['v_date']='2020-02-03'
        for k,v in dict(H_v=104.,L_v=96.,C_v=100.,N_v=2.,ohlc_proxy_raw=0.,proxy_state='valid_same_epoch_previous_source_day',N_state='N_v_ready20').items():proxy[k]=v
        src.loc[1,'N_state']='N_v_not_ready20';src.loc[2,'rule_state']='unknown'
        src.loc[3,'lifecycle_state']='vendor_lifecycle_unknown';src.loc[4,'candidate_quote_epoch']='DCE.A.202009'
        proxy.loc[5,'C_v']=100.0001;src.loc[6,'projection_state']='source_ohlc_conflict'
        src.loc[7,'N_v']=0.;src.loc[8,'v_index']=20
        obs=fit.observation_projection(mother,src,proxy)
        self.assertEqual(obs.research_observed.tolist(),[1,0,0,0,0,0,0,0,0])
        self.assertEqual(obs.q_settlement.iloc[0],0.)
        self.assertTrue(obs.q_settlement.iloc[1:].isna().all())
        self.assertTrue(obs.q_proxy.iloc[1:].isna().all())
        self.assertTrue(src.training_accepted.eq(0).all())
        changed=proxy.copy();changed.loc[0,'event_id']='wrong'
        with self.assertRaisesRegex(ValueError,'identity'):
            fit.observation_projection(mother,src,changed)
        with self.assertRaisesRegex(ValueError,'identity'):
            fit.observation_projection(mother,src,proxy.drop(columns='u_index'))
        bad=src.copy();bad.loc[0,'feature_available']=1
        with self.assertRaisesRegex(ValueError,'source.*flags'):
            fit.observation_projection(mother,bad,proxy)

    def test_three_arm_cell_artifacts_independently_reproduce_all_scores(self):
        # Break caught: 3 arm-specific preprocessors/rows, missing portability, or normal-equation errors.
        n=12
        f=pd.DataFrame(dict(sequence_index=range(n),event_id=[str(i) for i in range(n)],product_id=['DCE.A']*n,
            family_id=['DCE.A']*n,u_date=['2019-01-01']*6+['2020-01-02']*6,u_index=range(n),reference_epoch=['E']*n,
            entry_index=np.arange(n)+1,exit_index=np.arange(n)+2,entry_date=['2019-01-02']*n,exit_date=['2019-01-03']*n,
            label_known_date=['2019-01-03']*6+['']*6,label_state=['closed_complete_bar_model']*6+['unknown']*6,
            net_R_stress=[-1,1,-2,2,-3,3]+[np.nan]*6,label_history_ready20=[1]*n))
        common=np.arange(n*26,dtype=float).reshape(n,26)/10;common[0,3]=np.nan
        obs=f[['sequence_index']].copy();obs['q_settlement']=np.arange(n)/7;obs['q_proxy']=-np.arange(n)/11;obs['research_observed']=1
        obs.loc[1,['q_settlement','q_proxy']]=np.nan;obs.loc[1,'research_observed']=0
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'cell'
            predictions,records=fit.fit_cell(f,common,obs,'NARROW','2020-01-01',None,out)
            self.assertEqual(len(records),3);self.assertEqual(len(predictions),18)
            normalized=np.load(out/'normalized_inputs.npz',allow_pickle=False)
            self.assertEqual(normalized['train_base'].shape,(6,53))
            for arm in ('COMMON','SETTLEMENT','OHLC_PROXY'):
                model=json.loads((out/arm/'portable_model.json').read_text())
                q=np.zeros(6) if arm=='COMMON' else normalized['prediction_'+('settlement' if arm=='SETTLEMENT' else 'proxy')]
                x=np.column_stack([normalized['prediction_base'],q])
                score=x@np.array(model['coef'])+model['intercept']
                np.testing.assert_allclose(score,predictions.loc[predictions.arm.eq(arm),'score'],rtol=1e-12,atol=1e-12)
                ne=np.load(out/arm/'normal_equations.npz')
                beta=np.r_[model['coef'],model['intercept']]
                np.testing.assert_allclose(ne['lhs']@beta,ne['rhs'],rtol=1e-9,atol=1e-9)
            train=pd.read_csv(out/'training_identity_weights.csv.gz')
            np.testing.assert_allclose(train.net_R_stress,[-1,1,-2,2,-3,3])
            self.assertEqual(len({r['training_identity_sha256'] for r in records}),1)
            self.assertEqual(len({r['normalized_inputs']['sha256'] for r in records}),1)


    def test_source_receipt_binds_completed_projection_without_promoting_source_flags(self):
        source_binding=dict(path='/projection',bytes=12,sha256='p')
        terminal_binding=dict(path='/terminal',bytes=13,sha256='t')
        manifest_binding=dict(path='/manifest',bytes=14,sha256='m')
        source=dict(script_sha256=fit.SOURCE_SCRIPT_SHA,model_fits=0,cash_replays=0,
            artifacts=[source_binding,terminal_binding,dict(path='/protocol.json',bytes=1,sha256=fit.SOURCE_PROTOCOL_SHA)])
        terminal=dict(completed=True,native_source_queries=1,model_fits=0,cash_replays=0)
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);r=d/'receipt.json'
            receipt=dict(schema='stage069_settlement_source_acceptance_v1',status='accepted_for_fixed_research_reconstruction',
                training_accepted_in_source_unchanged=True,protocol_sha256=fit.PROTOCOL_SHA,
                rule_assumption='historical_reconstruction_one_source_day_lag_not_release_verified',
                accepted_rule_states=list(fit.RULE_STATES),source_manifest=manifest_binding,
                source_projection=source_binding,source_terminal=terminal_binding)
            r.write_text(json.dumps(receipt))
            inputs=dict(source_acceptance=fit.file_binding(r),settlement_manifest=manifest_binding,
                settlement_projection=source_binding,settlement_terminal=terminal_binding)
            self.assertEqual(fit.validate_source_acceptance(inputs,source,terminal)['status'],'accepted_for_fixed_research_reconstruction')
            receipt=copy.deepcopy(receipt);receipt['source_projection']['sha256']='wrong';r.write_text(json.dumps(receipt));inputs['source_acceptance']=fit.file_binding(r)
            with self.assertRaisesRegex(ValueError,'exact binding'):
                fit.validate_source_acceptance(inputs,source,terminal)

    def test_authorization_binds_every_source_protocol_output_and_input(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);s=d/'source.py';s.write_text('source');t=d/'test.py';t.write_text('test');inp=d/'input';inp.write_text('accepted')
            src=[fit.file_binding(s),fit.file_binding(t)]
            auth=dict(schema='stage069_exact_root_authorization_v1',authorized_by='root',stage='fit',
                exact_source_authorized=True,protocol_sha256=fit.PROTOCOL_SHA,source_bundle=src,input_bindings={'x':fit.file_binding(inp)},output=str((d/'fresh').resolve()))
            authp=d/'authorization.json';authp.write_text(json.dumps(auth));bound=fit.file_binding(authp)
            accepted=fit.authorize(authp,bound['sha256'],d/'fresh',src,required_roles={'x'})
            self.assertEqual(accepted['input_bindings']['x']['sha256'],fit.file_binding(inp)['sha256'])
            wrong=copy.deepcopy(auth);wrong['protocol_sha256']='0'*64;authp.write_text(json.dumps(wrong))
            with self.assertRaisesRegex(ValueError,'protocol'):
                fit.authorize(authp,fit.file_binding(authp)['sha256'],d/'fresh',src,required_roles={'x'})
            authp.write_text(json.dumps(auth));inp.write_text('tampered')
            with self.assertRaisesRegex(ValueError,'binding'):
                fit.authorize(authp,fit.file_binding(authp)['sha256'],d/'fresh',src,required_roles={'x'})


if __name__=='__main__':unittest.main()
