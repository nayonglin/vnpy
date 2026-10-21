"""Independent094 maturity, weights, scaler, Ridge equations and all predictions."""
import io,json,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from stage096_cash_adapter import bound,compare
from stage096_feature_math import channel_stats,head,mapping

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

def family_group(s):return int.from_bytes(hashlib.sha256(s.encode()).digest(),'big')%2

def weights(train):
    start=train.entry_index.to_numpy(int);end=train.exit_index.to_numpy(int);family=train.family_id.to_numpy();unique=np.empty(len(train))
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

def held_diagnostics(predictions,labels,end):
    linked=predictions.loc[predictions.scope.ne('main')].merge(labels[['event_id','label_state','participation_state','net_R_stress','label_known_date']],on='event_id',validate='many_to_one',sort=False)
    known=linked.label_state.eq('closed_complete_bar_model')&np.isfinite(linked.net_R_stress)&linked.label_known_date.ne('')&linked.label_known_date.le(end)&linked.history_ready20.eq(1)
    linked['diagnostic_known_domain']=known;linked['diagnostic_outcome_R']=linked.net_R_stress.where(known,np.nan)
    groups={};daily=[]
    for scope,g in linked.groupby('scope',sort=True):
        a=g.loc[g.arm.eq('BAG')].set_index('event_id');b=g.loc[g.arm.eq('ORDER')].set_index('event_id').reindex(a.index)
        assert len(a)==len(b)and a.u_date.eq(b.u_date).all()
        domain=a.diagnostic_known_domain&b.diagnostic_known_domain
        z=pd.DataFrame(dict(u_date=a.loc[domain,'u_date'],delta_R=((b.selected-a.selected)*a.net_R_stress).loc[domain],mse_difference=((b.score-a.net_R_stress)**2-(a.score-a.net_R_stress)**2).loc[domain]))
        d=z.groupby('u_date',sort=True).agg(delta_R=('delta_R','mean'),known_events=('delta_R','size'),mse_difference=('mse_difference','mean')).reset_index();d['scope']=scope;daily.append(d)
        point=float(d.delta_R.mean())if len(d)else None;disagree=b.selected.ne(a.selected)
        unresolved=~domain&~a.participation_state.eq('known_nonparticipation');unknown=int((disagree&unresolved).sum())
        states=pd.DataFrame(dict(state=a.label_state,disagreement=disagree.astype(int))).groupby('state').agg(full_events=('disagreement','size'),action_disagreements=('disagreement','sum')).reset_index().to_dict('records')
        groups[scope]=dict(nominal_pass=point is not None and point>=0,status='unsupported'if point is not None and point<0 else'unknown'if point is None or unknown else'supported',known_u_equal_mean_increment_R=point,known_common_events=int(domain.sum()),known_source_days=len(d),prediction_u_equal_MSE_difference=float(d.mse_difference.mean())if len(d)else None,full_mother_events=len(a),unknown_differential_selected_events=unknown,all_state_action_counts=states,unknown_R_bounds=None,annual=[dict(year=y,mean_delta_R=float(v.delta_R.mean()),prediction_u_equal_MSE_difference=float(v.mse_difference.mean()),known_source_days=len(v),known_events=int(v.known_events.sum()))for y,v in d.groupby(d.u_date.str[:4],sort=True)],cold_2023_view_mean_delta_R=float(d.loc[d.u_date.ge('2023-01-01'),'delta_R'].mean())if d.u_date.ge('2023-01-01').any()else None,meaning='closed_complete_bar_model and ready20 only; within-u all known rows mean including equal-action zero, then equal u; not cash/full opportunity value')
    return dict(schema='stage094_held_closed_diagnostic_v1',groups=groups,unknown_not_zero=True,cancellation_not_zero=True,full_policy_value_qualified=False,cash_return_qualified=False,contrast='ORDER_minus_BAG',shared_missing='sequence_missing'),pd.concat(daily,ignore_index=True),linked

def main_signal_diagnostics(labels,predictions,end):
    p=predictions.loc[predictions.scope.eq('main')]
    f=labels[['event_id','family_id','u_date','label_state','label_known_date','net_R_stress']].merge(p.pivot(index='event_id',columns='arm',values='selected'),on='event_id',validate='one_to_one',how='inner')
    f['actions_differ']=f.ORDER.ne(f.BAG);f['closed_known']=f.label_state.eq('closed_complete_bar_model')&np.isfinite(f.net_R_stress)&f.label_known_date.ne('')&f.label_known_date.le(end);f['known_nonparticipation']=f.label_state.eq('known_nonparticipation');f['year']=f.u_date.str[:4]
    s=f.groupby(['year','label_state'],dropna=False).agg(rows=('event_id','size'),action_disagreements=('actions_differ','sum'),BAG_selected=('BAG','sum'),ORDER_selected=('ORDER','sum'),closed_known=('closed_known','sum')).reset_index()
    r=dict(main_prediction_rows_per_arm=len(f),full_mother_rows=len(labels),full_mother_label_states={str(k):int(v)for k,v in labels.label_state.value_counts(dropna=False).items()},unknown_differential_selected_events=int((f.actions_differ&~f.closed_known&~f.known_nonparticipation).sum()),known_nonparticipation_differential_selected_events=int((f.actions_differ&f.known_nonparticipation).sum()),unfilled_signal_label_uncertainty_is_not_cash_exposure=True)
    return r,s

def check_fits(manifest,labels,index,tensor):
    root=Path(manifest['predictions']['path']).parent;inputs=manifest['input_bindings']
    with np.load(io.BytesIO(bound(inputs['common_npz'])),allow_pickle=False)as z:common=z['common'].copy();columns=z['columns'].tolist()
    identity=json.loads(bound(inputs['common_identity']));assert common.shape==(399252,26)and columns==identity['columns']
    assert identity['event_ids_sha256']==hashlib.sha256(('\n'.join(labels.event_id)+'\n').encode()).hexdigest()
    W,b=mapping()
    with np.load(io.BytesIO(bound(manifest['rff_mapping'])),allow_pickle=False)as m:
        assert set(m.files)=={'W_base','b'}and np.array_equal(m['W_base'],W)and np.array_equal(m['b'],b)
    records=json.loads((root/'fit_records.json').read_text());assert len(records)==12
    predictions=table(manifest['predictions']);convert(predictions,['sequence_index','u_index','score','selected','history_ready20','sequence_missing'])
    assert len(predictions)==644056 and predictions.policy.eq('NARROW').all()and not predictions.duplicated(['scope','event_id','arm']).any()
    results=[];activity=[]
    for scope in ('main','holdout_0','holdout_1'):
        for cutoff,stop in [('2020-01-01','2023-01-01'),('2023-01-01',None)]:
            mature=labels.label_state.eq('closed_complete_bar_model')&labels.u_date.lt(cutoff)&labels.label_known_date.ne('')&labels.label_known_date.lt(cutoff)
            future=labels.u_date.ge(cutoff)&(labels.u_date.lt(stop)if stop else True)
            if scope!='main':
                group=labels.family_id.map(family_group);mature&=group.ne(int(scope[-1]));future&=group.eq(int(scope[-1]))
            train=labels.loc[mature].sort_values(['u_date','event_id']);test=labels.loc[future].sort_values(['u_date','event_id'])
            assert len(train)and len(test);unique,day,w=weights(train);ti=train.sequence_index.to_numpy(int);pi=test.sequence_index.to_numpy(int)
            cell=root/'folds'/scope/cutoff;saved=pd.read_csv(cell/'training_identity_weights.csv.gz',dtype=str,keep_default_na=False)
            assert saved.event_id.tolist()==train.event_id.tolist()
            for c in ID:
                if c in ('sequence_index','u_index'):compare(pd.to_numeric(saved[c]),train[c],'train_identity_'+c,atol=0,rtol=0)
                else:assert saved[c].tolist()==train[c].tolist()
            assert saved.label_known_date.tolist()==train.label_known_date.tolist()and saved.label_state.eq('closed_complete_bar_model').all()
            assert np.array_equal(pd.to_numeric(saved.legacy_tensor_index),index[ti])and np.array_equal(pd.to_numeric(saved.sequence_missing),index[ti]<0)
            for c,v in [('uniqueness',unique),('u_normalized_weight',day),('sample_weight',w)]:compare(pd.to_numeric(saved[c]),v,'train_'+c,atol=1e-10)
            pred_identity=pd.read_csv(cell/'prediction_identity.csv.gz',dtype=str,keep_default_na=False)
            assert pred_identity.event_id.tolist()==test.event_id.tolist()and np.array_equal(pd.to_numeric(pred_identity.legacy_tensor_index),index[pi])
            scaler=json.loads((cell/'scaler.json').read_text());st=np.asarray([stats(common[ti,j],w)for j in range(26)]);observed=index[ti]>=0
            ss=channel_stats(tensor[index[ti][observed]],w[observed])
            for j,key in enumerate(('mean','var','scale','finite_count')):
                compare(scaler['common'][key],st[:,j],'fold_common_'+key,atol=1e-10);compare(scaler['sequence'][key],ss[key],'fold_pooled_channel_'+key,atol=1e-10)
            assert scaler['sequence']['observed_events']==int(observed.sum());compare(scaler['sequence']['observed_weight_sum'],w[observed].sum(),'observed_weight_sum')
            names=columns+[c+'_missing'for c in columns]+['sequence_missing']+[f'rff_{i:03d}'for i in range(128)]
            assert scaler['feature_names']==names and scaler['common']['columns']==columns and scaler['head_dimension']==181 and scaler['background_dimension']==53
            assert scaler['tensor_normalizer']=='accepted_simple20TR_mean_ATR_not_Wilder'
            # Derivation above is independent; reconstruction uses exact saved
            # floats to avoid last-bit trigonometric phase drift.
            for arm in ('ORDER','BAG'):
                model=json.loads((cell/arm/'portable_model.json').read_text());coef=np.asarray(model['coef']);intercept=model['intercept'];assert len(coef)==181 and model['parameters']=={'alpha':1.,'fit_intercept':True,'solver':'cholesky'}
                assert model['scope']==scope and model['cutoff']==cutoff and model['arm']==arm and model['policy']=='NARROW'and model['feature_names']==names
                x=head(common[ti],tensor,index[ti],scaler['common'],scaler['sequence'],arm,W,b);xt=head(common[pi],tensor,index[pi],scaler['common'],scaler['sequence'],arm,W,b)
                a=np.column_stack([x,np.ones(len(x))]);lhs=a.T@(w[:,None]*a);lhs[np.arange(181),np.arange(181)]+=1.;rhs=a.T@(w*train.net_R_stress.to_numpy(float));beta=np.r_[coef,intercept]
                with np.load(cell/arm/'normal_equations.npz',allow_pickle=False)as ne:
                    compare(ne['lhs'],lhs,'normal_equation_lhs',atol=2e-7);compare(ne['rhs'],rhs,'normal_equation_rhs',atol=2e-7);compare(ne['coefficient_with_intercept'],beta,'portable_beta',atol=1e-12);compare(ne['weight_sum'],w.sum(),'normal_weight_sum',atol=1e-10)
                residual=float(np.max(np.abs(lhs@beta-rhs)));assert np.allclose(lhs@beta,rhs,atol=1e-7,rtol=1e-8)
                actual=predictions.loc[predictions.scope.eq(scope)&predictions.cutoff.eq(cutoff)&predictions.arm.eq(arm)]
                assert actual.event_id.tolist()==test.event_id.tolist()
                for c in ID:
                    if c in ('sequence_index','u_index'):compare(actual[c],test[c],'prediction_identity_'+c,atol=0,rtol=0)
                    else:assert actual[c].tolist()==test[c].tolist()
                scores=xt@coef+intercept;compare(actual.score,scores,'all644056_portable_scores',atol=1e-9)
                assert np.array_equal(actual.sequence_missing.to_numpy(),(index[pi]<0).astype(int))and np.array_equal(actual.history_ready20,test.label_history_ready20)
                assert np.array_equal(actual.selected,(test.label_history_ready20.eq(1).to_numpy()&np.isfinite(scores)&(scores>0)).astype(int))
                rec=next(r for r in records if(r['scope'],r['cutoff'],r['arm'])==(scope,cutoff,arm))
                assert rec['training_rows']==len(train)and rec['prediction_rows']==len(test)and rec['selected']==int(actual.selected.sum())and rec['dimension']==181 and rec['full_head_cache_saved']is False
                assert rec['training_sequence_missing']==int((index[ti]<0).sum())and rec['prediction_sequence_missing']==int((index[pi]<0).sum())
                assert rec['max_u_date']==train.u_date.max()and rec['max_label_known_date']==train.label_known_date.max()and rec['training_identity_sha256']==hashlib.sha256(('\n'.join(train.event_id)+'\n').encode()).hexdigest()
                results.append(dict(scope=scope,cutoff=cutoff,arm=arm,train=len(train),predict=len(test),selected=int(actual.selected.sum()),normal_equation_max_residual=residual,training_sequence_missing=int((index[ti]<0).sum())))
                activity.append(dict(scope=scope,cutoff=cutoff,arm=arm,selected=int(actual.selected.sum()),sequence_missing=int(actual.sequence_missing.sum())))
    for role,mask in [('predictions_main',predictions.scope.eq('main')),('predictions_holdout',predictions.scope.ne('main'))]:
        saved=table(manifest[role]);assert saved.event_id.tolist()==predictions.loc[mask,'event_id'].tolist()and saved.arm.tolist()==predictions.loc[mask,'arm'].tolist()and saved.scope.tolist()==predictions.loc[mask,'scope'].tolist();compare(pd.to_numeric(saved.score),predictions.loc[mask,'score'],'split_prediction_scores',atol=1e-12)
    for scope in ('main','held_combined'):
        subset=predictions.loc[predictions.scope.eq('main')if scope=='main'else predictions.scope.ne('main')]
        assert subset.groupby('arm').size().eq(161014).all()and not subset.duplicated(['event_id','arm']).any()
        if scope!='main':assert all(family_group(r.family_id)==int(r.scope[-1])for r in subset.itertuples())
    held,daily,linked=held_diagnostics(predictions,labels,'2026-10-16');compare_dict(json.loads(bound(manifest['held_diagnostic'])),held,'all_held_report')
    saved=table(manifest['held_daily']);assert saved[['u_date','scope']].equals(daily[['u_date','scope']]);compare(pd.to_numeric(saved.delta_R),daily.delta_R,'held_daily_R');compare(pd.to_numeric(saved.mse_difference),daily.mse_difference,'held_daily_MSE');assert np.array_equal(pd.to_numeric(saved.known_events),daily.known_events)
    saved=table(manifest['held_linkage']);assert saved.event_id.tolist()==linked.event_id.tolist()and saved.arm.tolist()==linked.arm.tolist()
    assert saved.diagnostic_known_domain.eq('True').to_numpy().tolist()==linked.diagnostic_known_domain.tolist();compare(pd.to_numeric(saved.diagnostic_outcome_R.replace('',np.nan)),linked.diagnostic_outcome_R,'held_unknown_not_zero')
    metrics=json.loads((root/'opportunity_metrics.json').read_text());g=predictions.merge(labels[['event_id','label_state','participation_state','net_R_stress','label_known_date']],on='event_id',validate='many_to_one');g['year']=g.u_date.str[:4]
    for role,keys in [('overall',['scope','arm']),('annual',['scope','arm','year']),('family_year',['scope','arm','family_id','year'])]:
        expected=[]
        for names,v in g.groupby(keys,sort=True):
            if not isinstance(names,tuple):names=(names,)
            known=v.label_state.eq('closed_complete_bar_model')&v.history_ready20.eq(1)&v.label_known_date.ne('')&v.label_known_date.le('2026-10-16')&np.isfinite(v.net_R_stress);sel=v.selected.eq(1)
            expected.append(dict(zip(keys,names),rows=len(v),selected=int(sel.sum()),sequence_missing=int(v.sequence_missing.sum()),closed_action_ready_known=int(known.sum()),mse_closed_known=float(np.mean((v.loc[known,'score']-v.loc[known,'net_R_stress'])**2))if known.any()else None,selected_nonclosed=int((sel&~v.label_state.eq('closed_complete_bar_model')).sum()),label_states=v.label_state.value_counts().to_dict()))
        compare_dict(metrics[role],expected,'opportunity_'+role)
    signal,states=main_signal_diagnostics(labels,predictions,'2026-10-16')
    return predictions,held,signal,states,dict(models=results,predictions_checked=len(predictions),activity=activity,held=held,head_dimension=181,RFF_input_dimension=91,old_model_rechecks=0,model_refits=0,head_cache_saved=False)

