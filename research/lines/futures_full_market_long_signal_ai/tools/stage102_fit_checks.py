"""Independent100 own-policy maturity, weights, targets, 52-head equations."""
import io,json,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from stage102_cash_adapter import bound,compare
from stage102_target_math import targets,head52

ID=['sequence_index','event_id','product_id','family_id','u_date','u_index','reference_epoch']
LABEL_FIELDS=ID+['exchange','label_history_ready20','N_u','low20_u','u_close','history_run','lifecycle_index','entry_index','exit_index','entry_date','exit_date','label_known_date','label_state','participation_state','net_R_stress','tick_size','R0_points']

def table(binding,columns=None):
    return pd.read_csv(io.BytesIO(bound(binding)),compression='gzip'if binding['path'].endswith('.gz')else None,usecols=columns,dtype=str,keep_default_na=False)

def convert(f,columns):
    for c in columns:f[c]=pd.to_numeric(f[c].replace('',np.nan),errors='raise')
    return f

def load_labels(binding):
    f=table(binding,LABEL_FIELDS);convert(f,['sequence_index','u_index','label_history_ready20','N_u','low20_u','u_close','history_run','lifecycle_index','entry_index','exit_index','net_R_stress','tick_size','R0_points'])
    assert len(f)==399252 and f.event_id.is_unique and np.array_equal(f.sequence_index,np.arange(len(f)))
    assert f.family_id.eq(f.product_id.str.removesuffix('_F')).all()
    return f

def weights(train):
    starts=train.entry_index.to_numpy(float);ends=train.exit_index.to_numpy(float)
    assert np.isfinite(starts).all() and np.isfinite(ends).all() and np.equal(starts,np.floor(starts)).all() and np.equal(ends,np.floor(ends)).all()
    start=starts.astype(int);end=ends.astype(int);family=train.family_id.to_numpy();unique=np.empty(len(train))
    assert np.all(start>=0)and np.all(end>=start)
    for f in np.unique(family):
        rows=np.flatnonzero(family==f);change=np.zeros(int(end[rows].max())+2)
        np.add.at(change,start[rows],1);np.add.at(change,end[rows]+1,-1)
        concurrent=np.cumsum(change);inverse=np.divide(1.,concurrent,out=np.zeros_like(concurrent),where=concurrent>0);cs=np.r_[0.,np.cumsum(inverse)]
        unique[rows]=(cs[end[rows]+1]-cs[start[rows]])/(end[rows]-start[rows]+1)
    by_u=pd.Series(unique).groupby(train.u_date.to_numpy()).transform('sum').to_numpy();day=unique/by_u
    return unique,day,day/day.mean()

def stats(x,w):
    finite=np.isfinite(x)
    if not finite.any():return 0.,0.,1.,0
    m=np.sum(x[finite]*w[finite])/w[finite].sum();v=np.sum(w[finite]*(x[finite]-m)**2)/w[finite].sum()
    return m,v,np.sqrt(v)if v>0 else 1.,int(finite.sum())

def compare_dict(a,b,label):
    if isinstance(b,dict):
        assert set(a)==set(b),(label,set(a)^set(b))
        for k,v in b.items():compare_dict(a[k],v,label+'.'+str(k))
    elif isinstance(b,list):
        assert len(a)==len(b),(label,len(a),len(b))
        for i,(x,y)in enumerate(zip(a,b)):compare_dict(x,y,label+'.'+str(i))
    elif isinstance(b,(str,bool))or b is None:assert a==b,(label,a,b)
    else:compare(a,b,label.split('.')[0],atol=1e-9,rtol=2e-10)

def main_signal_diagnostics(labels,predictions,end):
    p=predictions.loc[predictions.scope.eq('main')]
    f=labels[['event_id','family_id','u_date','label_state','label_known_date','net_R_stress']].merge(p.pivot(index='event_id',columns='arm',values='selected'),on='event_id',validate='one_to_one',how='inner')
    f['actions_differ']=f.G.ne(f.L);f['closed_known']=f.label_state.eq('closed_complete_bar_model')&np.isfinite(f.net_R_stress)&f.label_known_date.ne('')&f.label_known_date.le(end);f['known_nonparticipation']=f.label_state.eq('known_nonparticipation');f['year']=f.u_date.str[:4]
    s=f.groupby(['year','label_state'],dropna=False).agg(rows=('event_id','size'),action_disagreements=('actions_differ','sum'),L_selected=('L','sum'),G_selected=('G','sum'),closed_known=('closed_known','sum')).reset_index()
    r=dict(main_prediction_rows_per_arm=len(f),full_mother_rows=len(labels),full_mother_label_states={str(k):int(v)for k,v in labels.label_state.value_counts(dropna=False).items()},unknown_differential_selected_events=int((f.actions_differ&~f.closed_known&~f.known_nonparticipation).sum()),known_nonparticipation_differential_selected_events=int((f.actions_differ&f.known_nonparticipation).sum()),unfilled_signal_label_uncertainty_is_not_cash_exposure=True)
    return r,s

def domain_result(frame,cost):
    r=targets(frame.net_R_stress.to_numpy(float),np.asarray(cost,float),np.ones(len(frame),bool))
    bad=~r['valid'];finite=lambda x: (float(np.asarray(x)[np.isfinite(x)].min()),float(np.asarray(x)[np.isfinite(x)].max())) if np.isfinite(x).any() else (None,None)
    summary=dict(rows=len(frame),valid_rows=int(r['valid'].sum()),invalid_rows=int(bad.sum()),invalid_event_ids_first10=frame.loc[bad,'event_id'].head(10).tolist(),invalid_event_ids_sha256=hashlib.sha256(('\n'.join(frame.loc[bad,'event_id'])+'\n').encode()).hexdigest(),states={str(k):int(v)for k,v in pd.Series(r['state']).value_counts().items()},a_range=finite(r['a']),raw_y_range=finite(frame.net_R_stress.to_numpy(float)),z_range=finite(r['z']),wealth_factor_range=finite(r['wealth']),G_range=finite(r['G']))
    return r,summary

def identity(saved,expected,label):
    assert saved.event_id.tolist()==expected.event_id.tolist(),label
    for key in ID:
        if key in ('sequence_index','u_index'):compare(pd.to_numeric(saved[key]),expected[key],label+'_'+key,atol=0,rtol=0)
        else:assert saved[key].tolist()==expected[key].tolist(),(label,key)

def normal_equations(path,x,w,y,coef,intercept):
    assert x.shape[1]==52 and len(coef)==52
    augmented=np.column_stack([x,np.ones(len(x))]);lhs=augmented.T@(w[:,None]*augmented);lhs[np.arange(52),np.arange(52)]+=1.
    rhs=augmented.T@(w*y);beta=np.r_[coef,intercept]
    with np.load(path,allow_pickle=False) as saved:
        compare(saved['lhs'],lhs,'normal_equation_lhs',atol=2e-7)
        compare(saved['rhs'],rhs,'normal_equation_rhs',atol=2e-7)
        compare(saved['coefficient_with_intercept'],beta,'portable_beta',atol=1e-12)
        compare(saved['weight_sum'],w.sum(),'normal_weight_sum',atol=1e-10)
    residual=float(np.max(np.abs(lhs@beta-rhs)))
    assert np.allclose(lhs@beta,rhs,atol=1e-7,rtol=1e-8),'Ridge coefficient violates independent normal equation'
    return residual

def preserved_predictions(saved,expected,label):
    assert set(saved.columns)==set(expected.columns) and len(saved)==len(expected)
    for key in expected.columns:
        if key in ('sequence_index','u_index','selected','history_ready20','score'):
            compare(pd.to_numeric(saved[key]),expected[key],label+'_'+key,atol=1e-12 if key=='score' else 0,rtol=0)
        else:assert saved[key].tolist()==expected[key].tolist(),(label,key)

STATE_MAP={'not_evaluated':'not_evaluated_original_state','valid':'valid','invalid_cost':'invalid_cost_c','invalid_a':'invalid_budget_a','invalid_raw_target':'nonfinite_raw_y','invalid_z':'nonfinite_z','nonpositive_wealth_factor':'nonpositive_or_nonfinite_reference_wealth','invalid_log_target':'nonfinite_log_utility'}

def summary_domain(result):
    state=pd.Series(result['state']).map(STATE_MAP);bad=~result['valid'];failed=bool(bad.any())
    return dict(status='domain_failure' if failed else 'valid',rows=len(state),valid_rows=int((~bad).sum()),invalid_rows=int(bad.sum()),reason_counts={str(k):int(v) for k,v in state.value_counts().sort_index().items()},failure_meaning='reference_ruin_or_domain_failure' if failed else None,drop_clip_epsilon_or_retry=False)

def compare_domain_columns(saved,result,y,c,label):
    names={'raw_y':y,'cost_c':c,'a':result['a'],'z':result['z'],'L_target':result['L'],'G_target':result['G'],'reference_wealth':result['wealth']}
    for name,value in names.items():compare(pd.to_numeric(saved[name].replace('',np.nan)),value,label+'_'+name,atol=1e-10)
    assert saved.domain_state.tolist()==pd.Series(result['state']).map(STATE_MAP).tolist(),label+' domain states'

def check_fits(manifest,labels):
    root=Path(manifest['domain_report']['path']).parent;inputs=manifest['input_bindings']
    with np.load(io.BytesIO(bound(inputs['common_npz'])),allow_pickle=False) as z:common=z['common'].copy();columns=z['columns'].tolist()
    identity_info=json.loads(bound(inputs['common_identity']))
    assert common.shape==(399252,26) and columns==identity_info['columns'] and len(columns)==26
    assert identity_info['event_ids_sha256']==hashlib.sha256(('\n'.join(labels.event_id)+'\n').encode()).hexdigest()
    ci=columns.index('stress_u_cost_R');names=columns+[c+'_missing' for c in columns]
    records=json.loads(bound(manifest['fit_records']));domain=json.loads(bound(manifest['domain_report']))
    assert domain['schema']=='stage100_log_utility_domain_v1' and domain['f']==.0025 and domain['whole_candidate_fail_stop'] is True and domain['unknown_not_zero'] is True and domain['automatic_retry'] is False
    assert domain['raw']=='net_R_stress' and domain['a']=='1/(1+8*stress_u_cost_R)' and domain['L']=='a*raw' and domain['G']=='log1p(f*L)/f'
    assert domain['interpretation']=='isolated_u_plan_continuous_budget_utility_proxy_not_actual_joint_cash_log'
    training_domains=[];models=[];expected_prediction_pieces=[];fold_failed=False
    for cutoff,stop in [('2020-01-01','2023-01-01'),('2023-01-01',None)]:
        mature=labels.label_state.eq('closed_complete_bar_model')&labels.u_date.lt(cutoff)&labels.label_known_date.ne('')&labels.label_known_date.lt(cutoff)
        future=labels.u_date.ge(cutoff)&(labels.u_date.lt(stop) if stop else True)
        train=labels.loc[mature].sort_values(['u_date','event_id']);test=labels.loc[future].sort_values(['u_date','event_id'])
        assert len(train)>0 and len(test)>0
        ti=train.sequence_index.to_numpy(int);pi=test.sequence_index.to_numpy(int)
        target,description=domain_result(train,common[ti,ci]);cell=root/'folds'/cutoff
        saved=pd.read_csv(cell/'training_identity_weights_targets.csv.gz',dtype=str,keep_default_na=False)
        identity(saved,train,'training_identity');assert saved.label_known_date.tolist()==train.label_known_date.tolist() and saved.label_state.eq('closed_complete_bar_model').all()
        unique,day,w=weights(train)
        for key,value in [('uniqueness',unique),('u_normalized_weight',day),('sample_weight',w)]:compare(pd.to_numeric(saved[key]),value,'training_'+key,atol=1e-10)
        compare_domain_columns(saved,target,train.net_R_stress.to_numpy(float),common[ti,ci],'training_target')
        td=dict(summary_domain(target),cutoff=cutoff,scope='main',max_u_date=train.u_date.max(),max_label_known_date=train.label_known_date.max(),training_identity_weights_targets=domain['training_folds'][len(training_domains)]['training_identity_weights_targets'])
        compare_dict(json.loads((cell/'training_domain.json').read_text()),td,'training_domain');training_domains.append(td)
        description.update(cutoff=cutoff,training=True)
        if not target['valid'].all():
            assert not (cell/'L').exists() and not (cell/'G').exists() and not (cell/'scaler.json').exists()
            fold_failed=True;failed_description=description
            if stop:assert not (root/'folds'/stop).exists(),'later cutoff must not run after domain failure'
            break
        st=np.asarray([stats(common[ti,j],w) for j in range(26)]);scaler=json.loads((cell/'scaler.json').read_text())
        for j,key in enumerate(('mean','var','scale','finite_count')):compare(scaler['common'][key],st[:,j],'train_scaler_'+key,atol=1e-10)
        assert scaler['common']['columns']==columns and scaler['feature_names']==names and scaler['head_dimension']==52 and scaler['scope']=='main' and scaler['cutoff']==cutoff
        pred_id=pd.read_csv(cell/'prediction_identity.csv.gz',dtype=str,keep_default_na=False);identity(pred_id,test,'prediction_identity')
        assert np.array_equal(pd.to_numeric(pred_id.label_history_ready20),test.label_history_ready20)
        # Independently derived stats above; exact saved floats preserve the
        # serialized public model's numerical input representation.
        x=head52(common[ti],scaler['common']);xt=head52(common[pi],scaler['common'])
        fold_pred=pd.read_csv(cell/'predictions_main.csv.gz',dtype=str,keep_default_na=False);convert(fold_pred,['sequence_index','u_index','score','selected','history_ready20'])
        assert len(fold_pred)==2*len(test) and set(fold_pred.arm)=={'L','G'} and not fold_pred.duplicated(['event_id','arm']).any()
        for arm in ('L','G'):
            model=json.loads((cell/arm/'portable_model.json').read_text());coef=np.asarray(model['coef']);intercept=model['intercept']
            assert model['schema']=='stage100_portable_ridge_v1' and model['parameters']==dict(alpha=1.,fit_intercept=True,solver='cholesky')
            assert model['scope']=='main' and model['cutoff']==cutoff and model['arm']==arm and model['policy']=='NARROW' and model['feature_names']==names and model['f']==.0025
            assert model['target']==('z' if arm=='L' else 'log1p(f*z)/f')
            residual=normal_equations(cell/arm/'normal_equations.npz',x,w,target[arm],coef,intercept)
            actual=fold_pred.loc[fold_pred.arm.eq(arm)];identity(actual,test,'fold_prediction')
            assert actual.scope.eq('main').all() and actual.policy.eq('NARROW').all() and actual.cutoff.eq(cutoff).all()
            scores=xt@coef+intercept;compare(actual.score,scores,'all_portable_scores',atol=1e-9)
            assert np.array_equal(actual.history_ready20,test.label_history_ready20)
            assert np.array_equal(actual.selected,(test.label_history_ready20.eq(1).to_numpy()&np.isfinite(scores)&(scores>0)).astype(int))
            rec=next(r for r in records if (r['cutoff'],r['arm'])==(cutoff,arm))
            assert rec['scope']=='main' and rec['policy']=='NARROW' and rec['dimension']==52 and rec['f']==.0025 and rec['full_head_cache_saved'] is False
            assert rec['training_rows']==len(train) and rec['prediction_rows']==len(test) and rec['selected']==int(actual.selected.sum())
            assert rec['training_dates']==train.u_date.nunique() and rec['training_families']==train.family_id.nunique()
            assert rec['max_u_date']==train.u_date.max() and rec['max_label_known_date']==train.label_known_date.max() and rec['training_identity_sha256']==hashlib.sha256(('\n'.join(train.event_id)+'\n').encode()).hexdigest()
            for role,path in [('training_identity_weights_targets',cell/'training_identity_weights_targets.csv.gz'),('scaler',cell/'scaler.json'),('training_domain',cell/'training_domain.json'),('prediction_identity',cell/'prediction_identity.csv.gz'),('portable_model',cell/arm/'portable_model.json'),('normal_equations',cell/arm/'normal_equations.npz')]:assert Path(rec[role]['path'])==path
            models.append(dict(cutoff=cutoff,arm=arm,train=len(train),predict=len(test),selected=int(actual.selected.sum()),normal_equation_max_residual=residual,target_domain=description))
        expected_prediction_pieces.append(fold_pred)
    compare_dict(domain['training_folds'],training_domains,'training_folds')
    assert len(records)==len(models)==manifest['actual_fit_calls_completed']==manifest['actual_fit_calls_attempted'] and len(models) in (0,2,4)
    predictions=pd.concat(expected_prediction_pieces,ignore_index=True) if expected_prediction_pieces else None
    assert manifest['prediction_rows']==(len(predictions) if predictions is not None else 0)
    if fold_failed:
        assert domain['oos_checked'] is False and domain['oos_domain'] is None and domain['oos_prediction_binding_before_check'] is None
        assert manifest['predictions_main'] is None and manifest['domain_projection'] is None and manifest['opportunity_metrics'] is None
        if predictions is not None:
            partial=table(manifest['partial_predictions_main']);preserved_predictions(partial,predictions,'partial_preserved')
        else:assert manifest['partial_predictions_main'] is None
        assert manifest['status']=='domain_failure' and domain['status']=='domain_failure' and domain['domain_pass'] is False and domain['cash_eligible'] is False
        report=dict(domain_pass=False,models=models,models_checked=len(models),predictions_checked=len(predictions) if predictions is not None else 0,training_domain_failure=failed_description,oos_checked=False,head_dimension=52,model_refits=0)
        return predictions,None,None,report
    assert len(models)==4 and predictions is not None and len(predictions)==322028
    complete=table(manifest['predictions_main']);preserved_predictions(complete,predictions,'complete_preserved')
    assert domain['oos_prediction_binding_before_check']==manifest['predictions_main'] and manifest['partial_predictions_main'] is None and domain['oos_checked'] is True
    assert not predictions.duplicated(['event_id','arm']).any() and predictions.groupby('arm').size().eq(161014).all()
    use=labels.u_date.ge('2020-01-01')&labels.u_date.le('2026-10-16')&labels.label_state.eq('closed_complete_bar_model')&labels.label_known_date.ne('')&labels.label_known_date.le('2026-10-16')
    target,oos_description=domain_result(labels.loc[use],common[labels.loc[use,'sequence_index'].to_numpy(int),ci])
    projection=table(manifest['domain_projection']);identity(projection,labels,'full_domain_projection')
    for key in ('label_state','label_known_date','participation_state'):assert projection[key].tolist()==labels[key].tolist(),('preserved mother state',key)
    compare(pd.to_numeric(projection.net_R_stress.replace('',np.nan)),labels.net_R_stress,'preserved_mother_raw_R',atol=1e-10,rtol=2e-11)
    assert np.array_equal(pd.to_numeric(projection.domain_evaluated),use.astype(int)) and projection.loc[~use,'domain_state'].eq('not_evaluated_original_state').all()
    compare_domain_columns(projection.loc[use],target,labels.loc[use,'net_R_stress'].to_numpy(float),common[labels.loc[use,'sequence_index'].to_numpy(int),ci],'OOS_target')
    for key in ('raw_y','cost_c','a','z','L_target','G_target','reference_wealth'):assert projection.loc[~use,key].eq('').all(),'non-evaluated targets must remain null'
    oos=dict(summary_domain(target),scope='forward_closed_known_by_end',start='2020-01-01',end='2026-10-16',checked_after_complete_predictions=True,full_mother_rows=len(labels),original_label_states=labels.label_state.value_counts().to_dict(),unevaluated_rows=int((~use).sum()),unknown_open_cancel_targets_remain_null=True,used_as_prediction_or_action_gate=False)
    compare_dict(domain['oos_domain'],oos,'OOS_domain')
    passed=bool(target['valid'].all());assert domain['domain_pass']==passed and domain['cash_eligible']==passed and domain['status']==('valid' if passed else 'domain_failure')
    linked=predictions.merge(projection[['event_id','domain_evaluated','domain_state','L_target','G_target']],on='event_id',validate='many_to_one').merge(labels[['event_id','label_state','participation_state']],on='event_id',validate='many_to_one');linked['year']=linked.u_date.str[:4]
    convert(linked,['domain_evaluated','L_target','G_target'])
    metrics=json.loads(bound(manifest['opportunity_metrics']));families=sorted(labels.family_id.unique());years=sorted(linked.year.unique())
    def one(g,arm,**keys):
        known=g.domain_evaluated.eq(1)&g.domain_state.eq('valid');sel=g.selected.eq(1);ready=known&g.history_ready20.eq(1)
        return dict(arm=arm,**keys,rows=len(g),selected=int(sel.sum()),closed_known_valid=int(known.sum()),closed_action_ready_known=int(ready.sum()),mse_own_target_closed_known=float(np.mean((g.loc[known,'score']-g.loc[known,arm+'_target'])**2)) if known.any() else None,selected_nonclosed=int((sel&~g.label_state.eq('closed_complete_bar_model')).sum()),selected_target_unknown_or_invalid=int((sel&~known).sum()),label_states=g.label_state.value_counts().to_dict())
    expected=dict(overall=[],annual=[],family_year=[])
    for arm in ('L','G'):
        a=linked.loc[linked.arm.eq(arm)];expected['overall'].append(one(a,arm,scope='main'))
        for year in years:
            v=a.loc[a.year.eq(year)];expected['annual'].append(one(v,arm,scope='main',year=year))
            for family in families:expected['family_year'].append(one(v.loc[v.family_id.eq(family)],arm,scope='main',family_id=family,year=year))
    for key,value in expected.items():compare_dict(metrics[key],value,'opportunity_'+key)
    assert metrics['schema']=='stage100_opportunity_metrics_v1' and metrics['all_families_including_zero'] is True and metrics['predictive_error_is_not_cash_value'] is True and metrics['same_budget_unit_but_different_curvature'] is True
    signal,states=main_signal_diagnostics(labels,predictions,'2026-10-16')
    report=dict(domain_pass=passed,models=models,models_checked=4,predictions_checked=322028,full_mother_domain_projection_rows=399252,oos_domain=oos_description,head_dimension=52,model_refits=0,family_holdout_performed=False,old_models_rechecked=0)
    return predictions,signal,states,report
