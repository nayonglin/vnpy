"""Frozen121 LONG_HISTORY CONTROL comparison: 12 fits only after exact root authorization.

Pure fixtures do no SQL or actual input reads. Accepted071 supplies mature
selection, concurrency weights and finite statistics without modification.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import time
import numpy as np
import pandas as pd

TOOLS=Path(__file__).resolve().parent
LINE=TOOLS.parent
PROTOCOL=LINE/'outputs/stage121_long_history_protocol/protocol.json'
PROTOCOL_SHA='c9a9538de0160266624c2bbfd8912964a44b2cfda97e639d1079fb1614bd7421'
STAGE_ROOT=LINE/'outputs/stage123_long_history_fit'
_spec=importlib.util.spec_from_file_location('stage123_accepted071',TOOLS/'stage071_settlement_narrow_fit.py')
legacy=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(legacy)
COMMON=legacy.COMMON
IDENTITY=legacy.IDENTITY
ARMS=('CONTROL','LONG_HISTORY')
SCOPES=('main','holdout_0','holdout_1')
CUTOFFS=('2020-01-01','2023-01-01')
END='2026-10-16'
PARAMETERS=dict(alpha=1.,fit_intercept=True,solver='cholesky')
FEATURE_NAMES=COMMON+[c+'_missing' for c in COMMON]+['external_missing','fixed12_calendar_month_return_chain']
LABEL_COLUMNS=list(dict.fromkeys(legacy.LABEL_COLUMNS+['participation_state']))
PROJECTION_COLUMNS=IDENTITY+['external_scalar_raw','external_missing','external_observed','projection_state','missing_reason']
INPUT_ROLES={'common_npz','common_identity','narrow_labels','narrow_manifest','projection_manifest','projection','projection_terminal'}
file_binding=legacy.file_binding
read_bound=legacy.read_bound
same_binding=legacy.same_binding
write_json=legacy.write_json
write_csv=legacy.write_csv
write_npz=legacy.write_npz


def family_group(value):
    return int(hashlib.sha256(value.encode()).hexdigest(),16)%2


def source_bundle():
    names=('stage123_long_history_fit.py','test_stage123_long_history_fit.py','stage071_settlement_narrow_fit.py')
    return sorted([file_binding(TOOLS/n) for n in names],key=lambda b:b['path'])


def fold_slices(frame,cutoff,next_cutoff,scope):
    if scope not in SCOPES:raise ValueError('unknown fixed scope')
    train=legacy.training_slice(frame,cutoff)
    prediction=legacy.prediction_slice(frame,cutoff,next_cutoff)
    if scope!='main':
        group=int(scope[-1])
        train=train.loc[train.family_id.map(family_group).ne(group)].copy()
        prediction=prediction.loc[prediction.family_id.map(family_group).eq(group)].copy()
    if train.empty or prediction.empty:raise ValueError('empty fixed fold')
    return train,prediction


def validate_projection(mother,projection):
    legacy._identity(mother,projection)
    p=projection.copy()
    legacy._numeric(p,['external_scalar_raw','external_missing','external_observed'])
    observed=p.external_observed.eq(1)
    if (not p.external_observed.isin([0,1]).all() or not p.external_missing.isin([0,1]).all()
            or not p.external_missing.eq(1-p.external_observed).all()
            or not np.array_equal(np.isfinite(p.external_scalar_raw),observed.to_numpy())
            or p.loc[observed,'external_scalar_raw'].lt(-1).any()):
        raise ValueError('LONG_HISTORY shared mask/scalar differs')
    if (not p.projection_state.eq('observed_fixed12_calendar_month_return_chain').eq(observed).all()
            or p.loc[~observed,'missing_reason'].eq('').any()):
        raise ValueError('LONG_HISTORY observed/missing provenance differs')
    # This consumes the accepted projection; it does not re-qualify raw units.
    return p


def scalar_stats(values,weights):
    q,w=np.asarray(values,float),np.asarray(weights,float);finite=np.isfinite(q)
    if finite.any() and np.equal(q[finite],q[finite][0]).all():
        return dict(mean=float(q[finite][0]),var=0.,scale=1.,finite_count=int(finite.sum()))
    return legacy.finite_stats(q,w)


def support_preflight(frame,common,projection):
    p=validate_projection(frame,projection);scalar=p.external_scalar_raw.to_numpy(float);cells=[]
    for scope in SCOPES:
        for i,cutoff in enumerate(CUTOFFS):
            train,_=fold_slices(frame,cutoff,CUTOFFS[i+1] if i+1<len(CUTOFFS) else None,scope)
            ti=train.sequence_index.to_numpy(int);q=scalar[ti];w=legacy.training_weights(train).sample_weight.to_numpy(float)
            finite=np.isfinite(q);stats=scalar_stats(q,w)
            positive=bool(finite.any() and np.min(q[finite])<np.max(q[finite]) and np.isfinite(stats['var']) and stats['var']>0)
            observed=train.loc[finite]
            cells.append(dict(scope=scope,cutoff=cutoff,training_rows=len(train),finite_rows=int(finite.sum()),
                nonzero_rows=int(np.count_nonzero(q[finite])),weighted_stats=stats,positive_weighted_variation=positive,
                observed_families=observed.family_id.value_counts().to_dict(),observed_months=observed.u_date.str[:7].value_counts().sort_index().to_dict()))
    supported=all(c['positive_weighted_variation'] for c in cells)
    return dict(schema='stage123_scalar_support_v1',status='supported' if supported else 'unsupported_scalar_support',
        cash_eligible=supported,cells=cells,checked_before_any_fit=True,availability_is_not_row_or_action_gate=True,
        finite_support_does_not_establish_sample_sufficiency=True)


def prepare_fold(frame,common,projection,cutoff,next_cutoff,scope):
    p=validate_projection(frame,projection)
    train,prediction=fold_slices(frame,cutoff,next_cutoff,scope)
    ti=train.sequence_index.to_numpy(int);pi=prediction.sequence_index.to_numpy(int)
    x=np.asarray(common,float)
    if x.shape!=(len(frame),26):raise ValueError('common26 shape differs')
    weights=legacy.training_weights(train);w=weights.sample_weight.to_numpy(float)
    scalar=p.external_scalar_raw.to_numpy(float);observed=p.external_observed.to_numpy(bool)
    stats=[legacy.finite_stats(x[ti,j],w) for j in range(26)]
    scaler=dict(common=dict(columns=COMMON,**{k:[s[k] for s in stats] for k in ('mean','var','scale','finite_count')}),
        scalar=scalar_stats(scalar[ti],w),feature_names=FEATURE_NAMES,
        scope=scope,cutoff=cutoff,weighting='own_policy_mature_train_only;family_concurrency_then_equal_u',
        missing='shared_external_missing; train_mean_imputation; standardized_missing_scalar_zero',
        common_units='accepted_original_2N')
    return dict(train=train,prediction=prediction,weights=weights,scaler=scaler,
        train_base=legacy.design_base(x[ti],observed[ti],scaler),
        prediction_base=legacy.design_base(x[pi],observed[pi],scaler),
        train_scalar=legacy.scalar_projection(scalar[ti],scaler),
        prediction_scalar=legacy.scalar_projection(scalar[pi],scaler),
        prediction_external_missing=p.external_missing.to_numpy(np.int8)[pi])


def design(base,scalar,arm):
    if arm not in ARMS:raise ValueError('unknown information arm')
    result=np.column_stack([base,np.zeros(len(base)) if arm=='CONTROL' else scalar])
    if result.shape!=(len(base),54) or not np.isfinite(result).all():
        raise ValueError('nonfinite or non54 LONG_HISTORY design')
    return result


def fit_cell(frame,common,projection,cutoff,next_cutoff,scope,directory,on_fit=None,on_completed=None):
    prepared=prepare_fold(frame,common,projection,cutoff,next_cutoff,scope)
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=False)
    train,prediction=prepared['train'],prepared['prediction']
    weights=prepared['weights'];w=weights.sample_weight.to_numpy(float)
    y=train.net_R_stress.to_numpy(float)
    write_json(directory/'scaler.json',prepared['scaler'])
    training=train[LABEL_COLUMNS].copy()
    for col in weights:training[col]=weights[col].to_numpy()
    training_binding=write_csv(directory/'training_identity_weights.csv.gz',training)
    prediction_binding=write_csv(directory/'prediction_identity.csv.gz',prediction[IDENTITY+['label_history_ready20']])
    normalized=write_npz(directory/'normalized_inputs.npz',train_base=prepared['train_base'],
        prediction_base=prepared['prediction_base'],train_scalar=prepared['train_scalar'],
        prediction_scalar=prepared['prediction_scalar'],y=y,sample_weight=w,
        train_sequence_index=train.sequence_index.to_numpy(int),prediction_sequence_index=prediction.sequence_index.to_numpy(int))
    identity_sha=hashlib.sha256(('\n'.join(train.event_id)+'\n').encode()).hexdigest()
    results=[];records=[]
    for arm in ARMS:
        target=directory/arm;target.mkdir()
        x=design(prepared['train_base'],prepared['train_scalar'],arm)
        xt=design(prepared['prediction_base'],prepared['prediction_scalar'],arm)
        estimator=legacy.Ridge(**PARAMETERS)
        if on_fit is not None:on_fit(scope,cutoff,arm)
        with legacy.threadpool_limits(limits=1):estimator.fit(x,y,sample_weight=w)
        if on_completed is not None:on_completed(scope,cutoff,arm)
        scores=estimator.predict(xt)
        portable=dict(schema='stage123_portable_ridge_v1',scope=scope,arm=arm,policy='NARROW',cutoff=cutoff,
            parameters=PARAMETERS,feature_names=FEATURE_NAMES,coef=estimator.coef_.tolist(),intercept=float(estimator.intercept_))
        write_json(target/'portable_model.json',portable)
        with (target/'model.joblib').open('xb') as stream:legacy.joblib.dump(estimator,stream,compress=3)
        z=np.column_stack([x,np.ones(len(x))]);lhs=z.T@(w[:,None]*z)
        lhs[np.arange(54),np.arange(54)]+=PARAMETERS['alpha'];rhs=z.T@(w*y)
        beta=np.r_[estimator.coef_,estimator.intercept_]
        if not np.allclose(lhs@beta,rhs,rtol=1e-8,atol=1e-7):raise ValueError('normal equations differ')
        ne=write_npz(target/'normal_equations.npz',lhs=lhs,rhs=rhs,coefficient_with_intercept=beta,weight_sum=np.array(w.sum()))
        if not np.allclose(scores,xt@np.asarray(portable['coef'])+portable['intercept'],rtol=1e-12,atol=1e-12):
            raise ValueError('portable predictions differ')
        out=legacy.prediction_frame(prediction,scores,'NARROW',arm,cutoff)
        out['scope']=scope;out['external_missing']=prepared['prediction_external_missing']
        results.append(out)
        records.append(dict(scope=scope,arm=arm,cutoff=cutoff,policy='NARROW',dimension=54,target='net_R_stress',
            training_rows=len(train),training_dates=int(train.u_date.nunique()),training_families=int(train.family_id.nunique()),
            training_label_states=train.label_state.value_counts().to_dict(),training_external_missing=int(projection.iloc[train.sequence_index].external_missing.sum()),
            prediction_rows=len(out),prediction_external_missing=int(out.external_missing.sum()),selected=int(out.selected.sum()),
            training_identity_sha256=identity_sha,max_u_date=str(train.u_date.max()),max_label_known_date=str(train.label_known_date.max()),
            training_identity_weights=training_binding,prediction_identity=prediction_binding,normalized_inputs=normalized,
            scaler=file_binding(directory/'scaler.json'),portable_model=file_binding(target/'portable_model.json'),
            model=file_binding(target/'model.joblib'),normal_equations=ne,normal_equation_max_abs_residual=float(np.max(np.abs(lhs@beta-rhs)))))
    return pd.concat(results,ignore_index=True),records


def held_diagnostics(predictions,labels,end=END):
    fields=['event_id','label_state','participation_state','net_R_stress','label_known_date']
    linked=predictions.merge(labels[fields],on='event_id',how='left',validate='many_to_one')
    if linked.label_state.isna().any():raise ValueError('prediction absent from labels')
    linked['selected']=(linked.history_ready20.eq(1)&np.isfinite(linked.score)&linked.score.gt(0)).astype(np.int8)
    known=(linked.label_state.eq('closed_complete_bar_model')&np.isfinite(linked.net_R_stress)
        &linked.label_known_date.ne('')&linked.label_known_date.le(end)&linked.history_ready20.eq(1))
    linked['diagnostic_known_domain']=known
    linked['diagnostic_outcome_R']=linked.net_R_stress.where(known,np.nan)
    groups={};daily_tables=[]
    for scope,group in linked.groupby('scope',sort=True):
        if group.duplicated(['event_id','arm']).any():raise ValueError('duplicate held forward event')
        by_arm={a:group.loc[group.arm.eq(a)].set_index('event_id') for a in ARMS}
        if any(set(v.index)!=set(by_arm['CONTROL'].index) for v in by_arm.values()):
            raise ValueError('held full mothers differ')
        control=by_arm['CONTROL'];oi=by_arm['LONG_HISTORY'].reindex(control.index)
        if not control.u_date.eq(oi.u_date).all() or not control.history_ready20.eq(oi.history_ready20).all():
            raise ValueError('held shared readiness identity differs')
        domain=control.diagnostic_known_domain&oi.diagnostic_known_domain
        delta=(oi.selected-control.selected)*control.net_R_stress
        mse_delta=(oi.score-control.net_R_stress)**2-(control.score-control.net_R_stress)**2
        known_rows=pd.DataFrame(dict(u_date=control.loc[domain,'u_date'],delta_R=delta.loc[domain],mse_difference=mse_delta.loc[domain]))
        daily=known_rows.groupby('u_date',sort=True).agg(delta_R=('delta_R','mean'),known_events=('delta_R','size'),
            mse_difference=('mse_difference','mean')).reset_index()
        daily['scope']=scope;daily_tables.append(daily)
        point=float(daily.delta_R.mean()) if len(daily) else None
        disagree=oi.selected.ne(control.selected)
        unresolved=~domain&~control.participation_state.eq('known_nonparticipation')
        unknown_difference=int((disagree&unresolved).sum())
        by_state=pd.DataFrame(dict(state=control.label_state,disagreement=disagree.astype(int))).groupby('state').agg(
            full_events=('disagreement','size'),action_disagreements=('disagreement','sum')).reset_index().to_dict('records')
        nominal=point is not None and point>=0
        groups[scope]=dict(nominal_pass=nominal,status='unsupported' if point is not None and point<0 else 'unknown' if point is None or unknown_difference else 'supported',
            known_u_equal_mean_increment_R=point,known_common_events=int(domain.sum()),known_source_days=len(daily),
            prediction_u_equal_MSE_difference=float(daily.mse_difference.mean()) if len(daily) else None,
            full_mother_events=len(control),unknown_differential_selected_events=unknown_difference,
            all_state_action_counts=by_state,unknown_R_bounds=None,
            annual=[dict(year=y,mean_delta_R=float(d.delta_R.mean()),prediction_u_equal_MSE_difference=float(d.mse_difference.mean()),known_source_days=len(d),known_events=int(d.known_events.sum()))
                    for y,d in daily.groupby(daily.u_date.str[:4],sort=True)],
            cold_2023_view_mean_delta_R=float(daily.loc[daily.u_date.ge('2023-01-01'),'delta_R'].mean()) if daily.u_date.ge('2023-01-01').any() else None,
            meaning='closed_complete_bar_model and ready20 only; within-u all known rows mean including equal-action zero, then equal u; not cash/full opportunity value')
    return dict(schema='stage123_held_closed_diagnostic_v1',contrast='LONG_HISTORY_minus_CONTROL',groups=groups,unknown_not_zero=True,
        cancellation_not_zero=True,full_policy_value_qualified=False,cash_return_qualified=False),pd.concat(daily_tables,ignore_index=True) if daily_tables else pd.DataFrame(),linked


def opportunity_metrics(predictions,labels):
    linked=predictions.merge(labels[['event_id','label_state','participation_state','net_R_stress','label_known_date']],on='event_id',validate='many_to_one')
    linked['year']=linked.u_date.str[:4]
    def rows(keys):
        result=[]
        for names,g in linked.groupby(keys,sort=True):
            if not isinstance(names,tuple):names=(names,)
            known=g.label_state.eq('closed_complete_bar_model')&g.history_ready20.eq(1)&g.label_known_date.ne('')&g.label_known_date.le(END)&np.isfinite(g.net_R_stress)
            selected=g.selected.eq(1)
            result.append(dict(zip(keys,names),rows=len(g),selected=int(selected.sum()),external_missing=int(g.external_missing.sum()),
                closed_action_ready_known=int(known.sum()),mse_closed_known=float(np.mean((g.loc[known,'score']-g.loc[known,'net_R_stress'])**2)) if known.any() else None,
                selected_nonclosed=int((selected&~g.label_state.eq('closed_complete_bar_model')).sum()),label_states=g.label_state.value_counts().to_dict()))
        return result
    return dict(schema='stage123_opportunity_metrics_v1',overall=rows(['scope','arm']),
        annual=rows(['scope','arm','year']),family_year=rows(['scope','arm','family_id','year']),
        predictive_error_is_not_cash_value=True)


def _csv(binding,columns=None):
    return pd.read_csv(io.BytesIO(read_bound(binding)),compression='gzip' if binding['path'].endswith('.gz') else None,
        usecols=columns,dtype=str,keep_default_na=False)


def validate_source_manifest(source,terminal,inputs):
    if (source.get('schema')!='stage122_long_history_projection_v1' or source.get('status')!='completed' or source.get('mode')!='actual'
            or source.get('protocol_sha256')!=PROTOCOL_SHA or source.get('mother_rows')!=399252
            or source.get('native_source_queries')!=1 or source.get('actual_model_fit_calls')!=0
            or source.get('new_cash_accounts')!=0 or source.get('new_labels')!=0
            or not same_binding(source.get('projection',{}),inputs['projection'])
            or not same_binding(source.get('terminal',{}),inputs['projection_terminal'])
            or not same_binding(source.get('input_bindings',{}).get('narrow_labels',{}),inputs['narrow_labels'])):
        raise ValueError('completed long history projection differs')
    required=dict(status='completed',exit_code=0,completed_projection_rows=399252,native_source_queries=1,
        actual_model_fit_calls=0,new_cash_accounts=0,new_labels=0)
    if any(terminal.get(k)!=v for k,v in required.items()):raise ValueError('long history projection terminal not complete')


def load_inputs(inputs,protocol):
    narrow_manifest=json.loads(read_bound(inputs['narrow_manifest']))
    if (narrow_manifest.get('schema')!='stage070_narrow_labels_v1' or narrow_manifest.get('status')!='completed'
            or narrow_manifest.get('mode')!='actual' or not same_binding(narrow_manifest.get('labels_narrow',{}),inputs['narrow_labels'])):
        raise ValueError('accepted narrow labels manifest differs')
    source=json.loads(read_bound(inputs['projection_manifest']));terminal=json.loads(read_bound(inputs['projection_terminal']))
    validate_source_manifest(source,terminal,inputs)
    frame=legacy.validate_labels(_csv(inputs['narrow_labels'],LABEL_COLUMNS),'NARROW')
    identity=json.loads(read_bound(inputs['common_identity']))
    if (identity.get('rows')!=399252 or identity.get('columns')!=COMMON
            or identity.get('event_ids_sha256')!=hashlib.sha256(('\n'.join(frame.event_id)+'\n').encode()).hexdigest()
            or not same_binding(identity.get('common',{}),inputs['common_npz']) or inputs['common_npz']['sha256']!=legacy.COMMON_SHA):
        raise ValueError('accepted common identity differs')
    with np.load(io.BytesIO(read_bound(inputs['common_npz'])),allow_pickle=False) as values:
        if values['columns'].tolist()!=COMMON or values['common'].shape!=(399252,26):raise ValueError('common26 schema differs')
        common=values['common'].astype(float)
    projection=_csv(inputs['projection'],PROJECTION_COLUMNS)
    legacy._numeric(projection,['sequence_index','u_index'])
    for col in ('sequence_index','u_index'):
        v=projection[col].to_numpy(float)
        if not np.isfinite(v).all() or not np.equal(v,np.floor(v)).all():raise ValueError('noninteger history identity')
        projection[col]=v.astype(np.int64)
    return frame,common,validate_projection(frame,projection)


def authorize(args):
    output=Path(args.output).resolve()
    if STAGE_ROOT.resolve() not in output.parents:raise ValueError('output outside Stage123 root')
    if output.exists():raise FileExistsError('fresh output required; no automatic retry')
    if args.protocol_sha256!=PROTOCOL_SHA or file_binding(PROTOCOL)['sha256']!=PROTOCOL_SHA:
        raise ValueError('exact frozen121 protocol required')
    protocol=json.loads(PROTOCOL.read_bytes())
    auth_binding=file_binding(args.authorization)
    if auth_binding['sha256']!=args.authorization_sha256:raise ValueError('authorization SHA differs')
    auth=json.loads(read_bound(auth_binding))
    required=dict(schema='stage121_exact_root_authorization_v1',authorized_by='root',stage='fit',exact_source_authorized=True,
        protocol_sha256=PROTOCOL_SHA,output=str(output))
    if any(auth.get(k)!=v for k,v in required.items()):raise ValueError('exact root fit authorization required')
    if sorted(auth.get('source_bundle',[]),key=lambda b:b['path'])!=source_bundle():raise ValueError('exact source/test binding differs')
    inputs=auth.get('input_bindings',{})
    if set(inputs)!=INPUT_ROLES:raise ValueError('fit input roles differ')
    for role in ('common_npz','common_identity','narrow_labels','narrow_manifest'):
        if not same_binding(inputs[role],protocol['inputs'][role]):raise ValueError('fixed121 input binding differs '+role)
    return output,protocol,auth,auth_binding


def run_actual(output,protocol,auth,authorization_binding):
    output.mkdir(parents=True,exist_ok=False);started=time.monotonic();bundle=source_bundle()
    attempted=completed=0
    write_json(output/'actual_started.json',dict(status='started',stage='fit',started_at=datetime.now(timezone.utc).isoformat(),
        source_bundle=bundle,authorization=authorization_binding,protocol=file_binding(PROTOCOL),fixture=False))
    write_json(output/'input_bindings.json',auth['input_bindings'])
    def on_fit(scope,cutoff,arm):
        nonlocal attempted
        attempted+=1
        with (output/'fit_attempts.jsonl').open('a') as stream:
            stream.write(json.dumps(dict(scope=scope,cutoff=cutoff,arm=arm,attempt=attempted))+'\n');stream.flush()
    def on_completed(scope,cutoff,arm):
        nonlocal completed
        completed+=1
        with (output/'fit_completed.jsonl').open('a') as stream:
            stream.write(json.dumps(dict(scope=scope,cutoff=cutoff,arm=arm,completed=completed))+'\n');stream.flush()
    try:
        frame,common,projection=load_inputs(auth['input_bindings'],protocol)
        support=support_preflight(frame,common,projection);write_json(output/'support_report.json',support)
        if not support['cash_eligible']:
            write_json(output/'actual_terminal.json',dict(status='unsupported_scalar_support',completed=False,execution_completed=True,exit_code=0,
                actual_fit_calls_attempted=0,actual_fit_calls_completed=0,native_source_queries=0,cash_replays=0,new_labels=0,
                cash_eligible=False,fixture=False,elapsed_seconds=time.monotonic()-started,automatic_retry=False))
            manifest=dict(schema='stage123_long_history_fit_v1',status='unsupported_scalar_support',mode='actual',completed=False,
                execution_completed=True,cash_eligible=False,protocol=file_binding(PROTOCOL),protocol_sha256=PROTOCOL_SHA,
                source_bundle=bundle,authorization=authorization_binding,input_bindings=auth['input_bindings'],
                terminal=file_binding(output/'actual_terminal.json'),support_report=file_binding(output/'support_report.json'),
                predictions=None,predictions_main=None,predictions_holdout=None,held_diagnostic=None,
                actual_fit_calls_attempted=0,actual_fit_calls_completed=0,native_source_queries=0,cash_replays=0,prediction_rows=0,
                goal_complete=False,production_qualified=False)
            write_json(output/'manifest.json',manifest);return manifest
        predictions=[];records=[]
        for scope in SCOPES:
            for i,cutoff in enumerate(CUTOFFS):
                pred,cell_records=fit_cell(frame,common,projection,cutoff,CUTOFFS[i+1] if i+1<len(CUTOFFS) else None,
                    scope,output/'folds'/scope/cutoff,on_fit=on_fit,on_completed=on_completed)
                predictions.append(pred);records.extend(cell_records)
                print(json.dumps(dict(phase='fit_cell_complete',scope=scope,cutoff=cutoff,completed=completed)),flush=True)
        predictions=pd.concat(predictions,ignore_index=True)
        main=predictions.loc[predictions.scope.eq('main')].copy();held=predictions.loc[predictions.scope.ne('main')].copy()
        expected=set(frame.loc[frame.u_date.ge(CUTOFFS[0]),'event_id'])
        for name,p in (('main',main),('held_combined',held)):
            if len(p)!=161014*2 or p.duplicated(['event_id','arm']).any() or set(p.arm)!=set(ARMS):raise ValueError('complete forward scores differ: '+name)
            for arm in ARMS:
                if set(p.loc[p.arm.eq(arm),'event_id'])!=expected:raise ValueError('full forward mother shrunk: '+name)
        if attempted!=12 or completed!=12:raise ValueError('fixed fit budget differs')
        if any(not all(p.family_id.map(family_group).eq(int(scope[-1]))) for scope,p in held.groupby('scope')):
            raise ValueError('held prediction family leakage')
        held_report,held_daily,held_linked=held_diagnostics(held,frame)
        prediction_binding=write_csv(output/'predictions.csv.gz',predictions)
        main_binding=write_csv(output/'predictions_main.csv.gz',main)
        held_binding=write_csv(output/'predictions_holdout.csv.gz',held)
        write_json(output/'held_diagnostic.json',held_report)
        held_daily_binding=write_csv(output/'held_daily.csv.gz',held_daily)
        held_linked_binding=write_csv(output/'held_score_linkage.csv.gz',held_linked)
        write_json(output/'opportunity_metrics.json',opportunity_metrics(predictions,frame))
        write_json(output/'fit_records.json',records)
        write_json(output/'summary.json',dict(schema='stage123_long_history_fit_summary_v1',completed=True,actual_fit_calls_completed=completed,
            full_prediction_rows=len(predictions),main_rows_per_arm=161014,held_combined_rows_per_arm=161014,
            mother_rows=len(frame),mother_label_states=frame.label_state.value_counts().to_dict(),
            external_observed=int(projection.external_observed.sum()),external_missing=int(projection.external_missing.sum()),strict_pit_claim=False,
            runtime=dict(python=sys.version,numpy=np.__version__,pandas=pd.__version__,sklearn=legacy.sklearn.__version__),
            goal_complete=False,formal_or_production=False))
        if source_bundle()!=bundle:raise ValueError('source changed during actual fit')
        write_json(output/'actual_terminal.json',dict(status='completed',completed=True,exit_code=0,
            actual_fit_calls_attempted=attempted,actual_fit_calls_completed=completed,cash_eligible=True,native_source_queries=0,cash_replays=0,new_labels=0,
            downloads=0,whole_database_hashes=0,fixture=False,elapsed_seconds=time.monotonic()-started))
        artifacts={str(p.relative_to(output)):file_binding(p) for p in sorted(output.rglob('*')) if p.is_file()}
        manifest=dict(schema='stage123_long_history_fit_v1',status='completed',mode='actual',completed=True,cash_eligible=True,protocol=file_binding(PROTOCOL),
            protocol_sha256=PROTOCOL_SHA,authorization=authorization_binding,
            terminal=file_binding(output/'actual_terminal.json'),source_bundle=bundle,input_bindings=auth['input_bindings'],
            predictions=prediction_binding,predictions_main=main_binding,predictions_holdout=held_binding,
            held_diagnostic=file_binding(output/'held_diagnostic.json'),held_daily=held_daily_binding,held_linkage=held_linked_binding,support_report=file_binding(output/'support_report.json'),
            artifacts=artifacts,actual_fit_calls_attempted=attempted,actual_fit_calls_completed=completed,native_source_queries=0,cash_replays=0,prediction_rows=len(predictions),
            goal_complete=False,production_qualified=False)
        write_json(output/'manifest.json',manifest);return manifest
    except BaseException as error:
        if not (output/'actual_terminal.json').exists():
            write_json(output/'actual_terminal.json',dict(status='failed',completed=False,exit_code=1,
                actual_fit_calls_attempted=attempted,actual_fit_calls_completed=completed,native_source_queries=0,cash_replays=0,
                error_type=type(error).__name__,error=str(error),elapsed_seconds=time.monotonic()-started,automatic_retry=False))
        raise


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('output','protocol-sha256','authorization','authorization-sha256'):parser.add_argument('--'+name,required=True)
    args=parser.parse_args(argv)
    output,protocol,auth,binding=authorize(args)
    if legacy.sklearn.__version__!='1.6.1':raise ValueError('accepted sklearn1.6.1 runtime required')
    result=run_actual(output,protocol,auth,binding)
    print(json.dumps(dict(status=result['status'],output=str(output),actual_fit_calls_completed=result['actual_fit_calls_completed'])),flush=True)


if __name__=='__main__':main()
